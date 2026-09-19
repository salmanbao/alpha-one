# 08 — BRG: Trading Platform Bridge

> Covers PRD module **BRG** (46 requirements). The bridge is the platform's only
> door into the broker world: it provisions MT5 accounts, keeps our copy of
> trading state fresh by polling, and **executes** enforcement commands issued by
> LCC/EVL. It is also the platform's **highest-risk external dependency** (MetaApi
> — sign up day 1 of Phase 0, per the PRD).

## 1. Purpose & scope

Alpha One is **not an execution venue**: traders trade on their own MT5 accounts
that live on a broker server we operate contracts for; Alpha One monitors and
enforces. The research report's LP-routing/SOR/hedging-engine sections are
therefore **out of scope** — they belong to a market-making prop firm, not to
PFaaS. What we keep from it: the adapter pattern, MT5 connectivity options
(MetaApi chosen), normalized data models, and the reconciliation discipline.

V1 = **MT5 via MetaApi only** (PRD: MetaApi vs Brokeree decision in Week 2; cTrader
is the fallback only if no suitable MT5 route is found). MT4/cTrader/DXtrade
adapters are V3 (BRG-24/25) behind the same interface.

Requirement coverage: `BRG-01,02,05,06,07,08,09,10,11,12,14,43,44` (V1) +
`03,04,13,15,16,18,19,20,22,27,29,30,31,32,33,34,35,37,42,45,46` (V2) +
`21,23,26,36,38,39,40,41,47` (V3).

## 2. Architecture

```
 LCC (commands: provision, disable, close, enable, archive)
 EVL (reads sync snapshots; verdicts back to LCC)
        │  account_commands (PG) / broker_executions
        ▼
┌──────────────────────── bridge service (Go, 1 instance V1) ───────────────────────┐
│  scheduler ── per-tenant poll budget (max 50% slots to one tenant)                │
│   ├── poll account (equity/balance/margin/freeMargin/leverage)                    │
│   ├── poll positions (open)                                                       │
│   └── poll deals (incremental since last deal ticket)                             │
│  normalizer ── MetaApi model → internal canonical (symbol, side, lots, px, time)  │
│  sync writer ── PG tx: snapshots + deals + bridge.tick event (outbox)             │
│  executor   ── commands: retry, circuit-break per account, confirm (re-read)      │
│  reconciler ── nightly: full fetch vs stored state → exceptions                   │
│  health     ── per-account failure counters → ops.provider_health                 │
└───────────────────────────────────────────────────────────────────────────────────┘
        │ REST (https, API key)
        ▼
   MetaApi cloud ──► MT5 broker servers (server groups: BRG-12)
```

**MetaApi model (V1 facts):** one **MetaApi account** (our platform key) can
manage many MT5 logins on many servers; per-login REST: account info, positions,
orders, deals, history deals, symbol info, server time. Webhooks exist but V1 is
**poll-only** (deterministic, testable, no webhook-verify surface; streaming is
BRG-21 V3). Cost: ~$50–100/mo **per MT5 account** (PRD estimate) — this is why
account caps are hard limits (TEN limits) and why funded accounts dominate cost
(00 §2).

## 3. System design

### 3.1 Adapter interface (BRG-01) — the contract that makes V3 platforms cheap

```go
type Connector interface {
  Name() string                                   // "metaapi-mt5"
  Capabilities() Capabilities                     // BRG-04 (V2): polling, streaming,
                                                  // credit, position-close, disable,
                                                  // password-reset, investor-mode, sandbox
  CreateAccount(ctx, req CreateReq) (CreateResult, error)      // BRG-05
  GetAccountInfo(ctx, login) (AccountInfo, error)              // equity etc.
  GetPositions(ctx, login) ([]Position, error)
  GetDealsSince(ctx, login, lastDealTicket int64) ([]Deal, error)
  ClosePosition(ctx, login, positionID) error
  SetTradingEnabled(ctx, login, enabled bool) error            // BRG-14
  Credit(ctx, login, amountCents int64, memo string) error    // V2 BRG-22 (audited)
  ResetPasswords(ctx, login, which) error                      // V2 BRG-13/30
  Archive(ctx, login) error                                    // V2 BRG-35
}
```

`Capabilities()` lets LCC/EVL degrade gracefully per platform (a platform without
`credit` can't do audited credits — the UI and rule engine hide the feature).

### 3.2 Provisioning (BRG-05/06)

1. LCC command `provision_account {program, size, leverage, server_group}`.
2. BRG picks a server from the tenant's broker group (BRG-12: `broker_groups`
   table: id, tenant_id, name, platform, server_id, timezone — timezone is the
   day-boundary authority, ADR-12), calls MetaApi account create
   (name pattern `{tenant_slug}_{program}_{seq}`), sets leverage, symbols (per
   program allowlist).
3. MetaApi returns login + generated trading/investor passwords → **field-
   encrypted** (BRG-44, AUTH §10.2 envelope) → `broker_accounts.credentials_enc`.
4. BRG reports `broker.created` → LCC activates account → credentials email
   (NOT + DOC template, one-time reveal in TD).
5. Failure: attempts ≤ 2, then `broker.failed` (LCC state) + CON alert.

### 3.3 Sync (BRG-07/08/09) — the hot path

Per active account, staggered poll every **60 s** (configurable per tenant 30–300 s;
burst after known events: after any command, immediate re-poll):

```
tx:
  UPSERT broker_accounts(login) SET equity, balance, margin, free_margin,
         leverage, server_time, last_synced_at, last_deal_ticket
  UPSERT broker_positions (open set; delete closed rows → into history)
  INSERT broker_deals (new deals since last ticket; ON CONFLICT (login, deal_id) DO NOTHING)
  INSERT outbox: bridge.tick {account, equity, margin, positions[...], deals_count, broker_time}
```

- **Canonical model** (BRG-19 core): amounts Decimal(18,8) for prices, lots
  Decimal(10,2), broker `time` (ms) as the trading clock, platform-side
  `received_at`. Normalization is a pure function — property-tested against
  fixture feeds (BRG-43 contract suite runs the same fixtures per adapter).
- **Gap detection (V1 basic, BRG-33 V2 full):** deal-ticket continuity: if
  `min(new_tickets) > last_ticket + 1` → `bridge.sync_gap` event + WARN alert
  (missing deals = potentially missing trades; EVL treats the gap as *evidence
  unavailable* — it does not assume, and ADM is paged for manual review).
- **Equity snapshots:** every tick updates `account_snapshots` (downsampled: 1
  row/account/min, 14-day rolling in PG, daily rollup to ANA read model;
  multi-resolution = LCC-42 V2).
- **Slot alerts (BRG-34):** poll backlog > 2 min → WARN; > 10 min → CRITICAL
  (evaluation fairness at risk — documented in the SLOs, 29 §4).

### 3.4 Enforcement execution (BRG-10/11) + trading on/off (BRG-14)

LCC `account_commands` are consumed by the executor:

| Command | MetaApi action | Confirm (BRG-11) |
|---|---|---|
| `disable_trading` | set account trading disabled (investor-only mode) | re-read account → flag off |
| `enable_trading` | re-enable | re-read → flag on |
| `close_positions` | close each open position at market (sequential, one retry each) | re-read positions → empty (within 30 s) |
| `archive_broker_account` (V2) | close all + close account | account gone |
| `credit` (V2, BRG-22) | deposit with memo | balance delta matches ±1 tick |

Execution rules: per-account **circuit breaker** (5 consecutive failures → open
30 s, halving; BRG-18 V2 formalizes reconnect semantics); retries 3 with backoff;
terminal failure → command `dead` + CRITICAL alert + LCC-27 monitor backs it up.
**Never** auto-retry `credit` (money op) — dead = human.

### 3.5 Reconciliation (BRG-15; V1 nightly basic, V2 full)

Nightly per server group: full history-deals fetch for active accounts vs stored
`broker_deals` (count + hash of (deal_id, profit, time) tuples); account info vs
last snapshot (balance delta explainable by last sync? else exception).
Exceptions → `bridge.reconciliation_exception` → ADM finance queue + AUD.
This is the last line proving "our copy == broker truth" (00 §8 non-negotiable 5).

### 3.6 Provider health (BRG-16)

Per MetaApi account (our platform key): 1-min success rate, p95 latency,
consecutive-failure counter; `ops.provider_health` every 5 min; degradation
levels: `degraded` (p95 > 2 s) → poll interval widens ×2 (fairness preserved by
backlog alert), `down` (5% success over 5 min) → CRITICAL + all enforcement
commands queue (not dropped) + CON banner.

## 4. Events (topic `bridge`)

| Event | When | Key fields | Consumers |
|---|---|---|---|
| `bridge.tick` | every sync tx | account, equity, balance, margin, positions, deals_count, broker_time | EVL (trigger eval), ANA (equity points), web SSE fan-out (TD live) |
| `bridge.account_created` / `bridge.account_create_failed` | provisioning | login, server, reason | LCC, NOT, CON |
| `bridge.trading_disabled` / `bridge.trading_enabled` | after confirmed command | account, by (command ref) | LCC (confirm transition), AUD |
| `bridge.positions_closed` | after confirmed close-all | closed_count, total_pnl_cents, broker_time | LCC, AUD, NOT (breach evidence) |
| `bridge.sync_gap` | ticket discontinuity | account, expected_from, got_from | ADM (manual review), AUD |
| `bridge.reconciliation_exception` | nightly mismatch | account, kind, delta | ADM, AUD, CON |
| `bridge.command_dead` | terminal command failure | command_id, reason | CON (CRITICAL), AUD |
| `ops.provider_health` | 5 min | success_rate, p95_ms, state | CON, dashboards |

## 5. Lifecycles

- **Broker account:** `created → active (syncing) → disabled (trading off) →
  archived (V2)`. Mirrors LCC account state but broker-side; `bridge_state`
  column on `broker_accounts` + nightly comparison with LCC state (LCC-33).
- **Sync cycle:** `scheduled → polled → written → (gap? | clean)` — per account,
  monotonic `last_deal_ticket`.
- **Command:** `pending → executing → confirmed | failed(retry) → dead` (attempts
  ≤ 3 for non-money, ≤ 1 for `credit`).
- **Circuit breaker:** `closed → open (5 fails) → half-open (probe) → closed`.
- **Server group:** active / degraded (poll budget halved) / disabled (no new
  accounts; existing keep syncing).

## 6. Error taxonomy

Namespace `BRG` (provider-safe strings only — MetaApi error codes mapped to ours):

| Code | HTTP/internal | Meaning |
|---|---|---|
| `brg.provider_auth` | internal CRITICAL | Our MetaApi key rejected (rotated? revoked?) |
| `brg.provider_unavailable` | internal WARN (escalates) | MetaApi 5xx/timeout; circuit handles |
| `brg.account_not_found` | internal | Login gone broker-side (closed manually? → page ops) |
| `brg.account_exists` | internal | Provisioning got "already exists" (idempotent path: adopt or fail) |
| `brg.capacity` | 503 (to LCC) | Server group full / MetaApi quota — account cap guard |
| `brg.command_failed` | internal | Execution failed after retries (reason in command result) |
| `brg.command_conflict` | internal | Broker state contradicted preconditions (e.g. position already closed) → confirm path |
| `brg.sync_gap` | internal WARN | Deal discontinuity (event + ADM review) |
| `brg.credentials_missing` | internal CRITICAL | Provisioned account missing creds (should never happen) |
| `brg.symbol_unknown` | internal | Normalization hit unmapped symbol (BRG-32 V2 mapping mgmt; V1: alert + skip with log) |

## 7. API endpoints
### 7.1 V1 baseline — `brg` (see `contracts/api/brg.md`)

**No HTTP surface in V1** — this is an internal/service contract. The internal contracts (what other modules call, what workers run, what is enforced) are in `contracts/api/brg.md`.

### 7.2 Extended (post-V1) surface — provisional

> Not in the V1 execution sheet. Design-level; paths beyond the V1 baseline are provisional until the URL-plan decision (`contracts/api/gw.md`, open question). Shown for platform completeness (V2/V3 phases, docs/99).

Internal (service tokens): `POST /internal/v1/bridge/commands/{id}/retry` (CON
tooling), `GET /internal/v1/bridge/accounts/{login}/state` (debug),
`POST /internal/v1/bridge/reconcile` (manual run).

Staff (ADM V2 broker management, BRG-26/34 surfaces): `GET /v1/admin/broker/groups`,
`GET /v1/admin/broker/accounts?state=`, `GET /v1/admin/broker/accounts/{login}/positions`,
`GET /v1/admin/broker/health`.

Trader (TD): no direct BRG endpoints — all via LCC/ANA surfaces (positions &
history = TD-08 reads ANA read model fed by `bridge.tick`/deals).
## 8. Schema (key shapes)

```jsonc
// bridge.tick (event payload.data)
{ "account_id": "01J9ACC...", "broker_login": "50001234",
  "equity_cents": 10412000, "balance_cents": 10412000, "margin_cents": 212000,
  "free_margin_cents": 10200000, "leverage": 1:500,
  "positions": [ { "position_id": "50001234-1", "symbol": "EURUSD", "side": "buy",
                   "lots": 0.50, "open_price": 1.08420, "current_price": 1.08510,
                   "sl": 1.08120, "tp": null, "opened_at": 1758275000000,
                   "profit_cents": 45000, "swap_cents": -1200, "commission_cents": -300 } ],
  "deals_count": 2, "last_deal_ticket": 88231, "broker_time": 1758278400000 }

// GET /v1/admin/broker/health
{ "data": { "provider": "metaapi", "state": "healthy", "success_rate_1m": 0.999,
    "p95_ms": 420, "accounts_syncing": 431, "backlog_seconds_p95": 7,
    "groups": [ { "name": "fb-live-1", "accounts": 300, "state": "active" } ] } }
```

## 9. Database design

```sql
CREATE TABLE broker_groups (
  id            ULID PRIMARY KEY,
  tenant_id     ULID NOT NULL REFERENCES tenants(id),
  name          TEXT NOT NULL,
  platform      TEXT NOT NULL DEFAULT 'mt5',
  server_id     TEXT NOT NULL,              -- MetaApi server identifier
  timezone      TEXT NOT NULL,              -- day-boundary authority (ADR-12)
  poll_interval_s INT NOT NULL DEFAULT 60,
  state         TEXT NOT NULL DEFAULT 'active' CHECK (state IN ('active','degraded','disabled')),
  UNIQUE (tenant_id, name)
);

CREATE TABLE broker_accounts (
  id                 ULID PRIMARY KEY,
  tenant_id          ULID NOT NULL,
  account_id         ULID NOT NULL REFERENCES accounts(id),   -- LCC 1:1
  login              TEXT NOT NULL,                           -- MT5 login
  server_id          TEXT NOT NULL,
  group_id           ULID REFERENCES broker_groups(id),
  state              TEXT NOT NULL DEFAULT 'creating',
                     CHECK (state IN ('creating','active','disabled','archived')),
  credentials_enc    JSONB,                -- {trading, investor} AES-256-GCM (BRG-44)
  cred_key_version   INT NOT NULL DEFAULT 1,
  leverage           TEXT,
  last_equity_cents  BIGINT, last_balance_cents BIGINT,
  last_margin_cents  BIGINT,
  last_deal_ticket   BIGINT NOT NULL DEFAULT 0,
  last_synced_at     TIMESTAMPTZ,
  server_time        TIMESTAMPTZ,          -- last broker-attested time
  fail_streak        INT NOT NULL DEFAULT 0,
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  archived_at        TIMESTAMPTZ,
  UNIQUE (login)
);
CREATE INDEX idx_bacc_tenant_state ON broker_accounts(tenant_id, state);
CREATE INDEX idx_bacc_sync ON broker_accounts(state, last_synced_at) WHERE state = 'active';

CREATE TABLE broker_positions (
  position_id   TEXT NOT NULL,             -- login-positionId canonical
  login         TEXT NOT NULL,
  tenant_id     ULID NOT NULL,
  symbol        TEXT NOT NULL,
  side          TEXT NOT NULL CHECK (side IN ('buy','sell')),
  lots          NUMERIC(10,2) NOT NULL,
  open_price    NUMERIC(18,8) NOT NULL,
  sl            NUMERIC(18,8), tp NUMERIC(18,8),
  opened_at     TIMESTAMPTZ NOT NULL,      -- broker time
  closed_at     TIMESTAMPTZ,
  profit_cents  BIGINT, swap_cents BIGINT, commission_cents BIGINT,
  PRIMARY KEY (position_id)
);
CREATE INDEX idx_bpos_open ON broker_positions(login) WHERE closed_at IS NULL;

CREATE TABLE broker_deals (
  deal_id       BIGINT NOT NULL,           -- MT5 deal ticket (per login)
  login         TEXT NOT NULL,
  tenant_id     ULID NOT NULL,
  position_id   TEXT,
  entry         TEXT NOT NULL,             -- in/out
  symbol        TEXT NOT NULL, side TEXT NOT NULL,
  lots          NUMERIC(10,2) NOT NULL,
  price         NUMERIC(18,8) NOT NULL,
  profit_cents  BIGINT, swap_cents BIGINT, commission_cents BIGINT,
  deal_time     TIMESTAMPTZ NOT NULL,      -- broker time
  received_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (login, deal_id)
) PARTITION BY RANGE (received_at);
-- monthly partitions (high-volume table; same pattern as events)

CREATE TABLE broker_executions (
  id            ULID PRIMARY KEY,
  command_id    ULID NOT NULL,             -- LCC account_commands id
  login         TEXT NOT NULL,
  action        TEXT NOT NULL,
  attempt       INT NOT NULL,
  request_hash  TEXT,                      -- idempotency evidence
  status        TEXT NOT NULL,             -- sent|confirmed|failed|dead
  provider_resp JSONB,                     -- redacted
  broker_time   TIMESTAMPTZ,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_bexec_cmd ON broker_executions(command_id, attempt);
```

## 10. Security & compliance

- **Credentials (BRG-44):** AES-256-GCM envelope (per-tenant DEK); decrypted only
  inside the bridge process for MetaApi auth (MetaApi authenticates with *our*
  platform key, not per-account — the MT5 login/password pair is what we store for
  the trader's own MT5 terminal use); never serialized in logs/events/errors
  (log-scanner test); rotation = broker-side reset (V2 BRG-13) + re-encrypt.
- **Least privilege:** MetaApi platform key scoped to our servers only; tenant
  isolation at the group level (a tenant's bridge calls only touch its server
  groups — enforced by the scheduler's group→tenant map, not by request params).
- **Money ops:** `credit` is dual-controlled (LCC command requires 2FA origin),
  never auto-retried, audited critical-tier (LED-06 fee/credit postings V2).
- **Data residency/trading data:** broker_time everywhere; gap policy = *evidence
  unavailable, not assumed* (compliance-safe default for breach disputes, LCC-38).
- **Provider trust boundary:** MetaApi responses are untrusted input — schema-
  validated, size-capped; a malformed response never panics (fail = `provider_resp`
  kept, alert raised).

## 11. Scalability considerations

| Surface | V1 | V2 headroom / action |
|---|---|---|
| Poll throughput | 431 accounts × 1/min ≈ 7.2 req/s to MetaApi | 5k accounts ≈ 83 req/s — 1 bridge instance + MetaApi concurrency (cap 20) → **add bridge replicas** (stateless; scheduler sharding by server group); MetaApi rate limits are the binding constraint → poll interval widens automatically (fairness: backlog alerts, SLO) |
| Sync tx size | 1 tx/account/poll (small) | PG write capacity fine to 10× |
| Deals table | ~50 deals/day/account → ~21k/day | partitioned; 90 d hot, archive to R2 (V2) |
| Snapshots | 1 row/min/account → ~620k rows/day | downsample to 1/min min, 14 d rolling + daily rollups; ANA owns long-term |
| Command latency | p95 < 2 s (confirm included) | same; CRITICAL if p95 > 10 s over 15 min (enforcement lag = risk) |
| MetaApi outage | queue commands, widen polls, backlog alerts | failover server group (V3 BRG-26): groups span 2 MetaApi servers from day 1 (config), second server activated by CON flip |
| Cost | per-account pricing → account caps are cost control (TEN limits) | BRG-47 cost tracking (V3) feeds CON |

## 12. Open-source solutions

| Option | Verdict |
|---|---|
| **MetaApi** (commercial, register must-integrate) | **CHOSEN V1** — only realistic MT5 management API without a MetaQuotes partnership; ~$50–100/account/mo |
| MetaQuotes Manager API (C++) | Requires partnership + C++ wrapper service — V2+ option if cost/limits bite |
| mql-zmq / MQL5-JSON-API (self-hosted EA bridge) | V2+ option for direct server access (research-validated); rejected V1 (ops weight, no multi-tenant story) |
| FIX engines (quickfix, etc.) | Out of scope — Alpha One is not an execution venue (research §4.1 applies to LP-routing firms) |
| cTrader Open API (protobuf) | V3 adapter (BRG-24); spec is open, SDKs exist |
| Nautilus Trader / full OSS platforms (research §4.9) | Rejected — they solve order execution, not prop-firm ops |
| Hyperswitch/Stripe (payments) | Not BRG (CHK/PAY) |

## 13. Technology stack

Go bridge service (REST client, scheduler, executor); Postgres (snapshots/deals/
executions, partitioned); Redis (scheduler dedupe, circuit-breaker state);
MetaApi (REST); Prometheus (poll backlog, provider health); Sentry (normalization
panics = P1); Uptime Kuma (MetaApi status page cross-check).

## 14. Integration — internal modules (glue)

| Module | How |
|---|---|
| **LCC** | consumes `account_commands` (provision/disable/close/enable/archive); reports `broker.created/failed` + confirms back (LCC transition preconditions) |
| **EVL** | consumes `bridge.tick` → verdicts; EVL never calls MetaApi; reads positions/equity from PG snapshots (or gets them in the tick payload) |
| **RSK (V2)** | consumes deals/positions for anti-gaming patterns (news trading, hedging, latency) |
| **ANA** | equity points, trade history read model (TD-06/08/21/23) |
| **PAY** | payout eligibility reads latest equity/balance snapshot (funded accounts) |
| **MIG** | cutover: FunderBlu's existing MT5 accounts are **adopted** (not recreated) — `broker_accounts` rows seeded from TTS export + MetaApi verify (LCC-22, MIG-xx) |
| **CON** | broker group mgmt, health, command retry, reconciliation runs |
| **AUD** | every command execution + credential reveal + reconciliation exceptions |

## 15. Integration — external tools

**MetaApi** (the whole world in V1: account mgmt, data, execution), broker
server(s) underlying MetaApi, Prometheus/Grafana, Sentry, Uptime Kuma, R2 (deal
archive V2).

## 16. Implementation blueprint

| Step | Owner | Est | Depends | Exit criteria |
|---|---|---|---|---|
| 0. **MetaApi account + first MT5 server + 3 test accounts** (PRD: day 1) | Tech Lead | 1 d (waiting on signup) | — | manual REST round-trip logged in `ops/notes` |
| 1. Schemas (groups, accounts, positions, deals, executions) + envelope types | BE-1 | 2 d | OPS | migrations green |
| 2. MetaApi client + connector (info/positions/deals-since/create) + normalizer + **fixture corpus** | BE-1 | 4 d | 0, 1 | unit: 200 recorded MetaApi responses normalize deterministically |
| 3. Scheduler (per-tenant budget, stagger, re-poll after commands) + sync writer + gap detection + `bridge.tick` | BE-1 | 4 d | 2 | 3 test accounts sync 24 h clean; injected gap → event + alert |
| 4. Provisioning (create → creds encrypt → broker.created) + credentials email path | BE-1 | 3 d | 2, LCC | end-to-end: LCC command → real MT5 account → trader gets creds email (staging) |
| 5. Executor (disable/enable/close-all) + confirm re-reads + circuit breaker + command_dead | BE-1 | 3 d | 3, LCC | breach on sandbox: positions closed < 10 s, confirmed empty |
| 6. BRG-43 **adapter contract test suite** (fixtures + lifecycle scenarios, runnable per adapter) | BE-1 | 2 d | 2–5 | CI job `bridge-contract` green; a fake broken adapter fails it |
| 7. Reconciliation (nightly) + provider health + dashboards + alerts | BE-2 | 3 d | 3, 5 | injected mismatch detected; MetaApi 500s → degraded state visible in CON |
| 8. BRG-44 credential encryption + log-scanner test + reveal integration with LCC | BE-2 | 1.5 d | 4 | scan: zero credential material in logs/events (property test) |
| 9. V2: MatchTrader adapter (BRG-03) behind same contract; capability declarations; reconciliation full; symbol mapping; multi-server; archive; password reset | BE-1 | 3 wks | 6 | adapter #2 passes BRG-43 with zero core changes |
| 10. V3: cTrader/DXtrade adapters + optional streaming (BRG-21) + cost tracking (BRG-47) | BE-1 | 4 wks | 9 | — |

**Risks (the platform's riskiest):** MetaApi cost/limits/pricing change →
mitigation: account caps, per-tenant poll budgets, adapter interface keeps escape
hatches (direct EA bridge, second provider) warm; MetaApi outage → mitigation:
command queueing + failover group config from day 1; sync lag during MetaApi
degradation → mitigation: SLO on enforcement latency + backlog alerts +
documented risk acceptance in 29 §5.

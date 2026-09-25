# 08 — BRG: Trading Platform Bridge

> Covers PRD module **BRG** (47 requirements). The bridge is the platform's only
> door into the broker world: it provisions MT5 accounts, keeps our copy of
> trading state fresh by **streaming** it from MetaApi (D78, docs/63 — REST
> polling is the fallback), and **executes** enforcement commands issued by
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

Requirement coverage: `BRG-01,02,05,06,07,08,09,10,11,12,14,43,44` (V1.0) +
`03,04,13,15,16,17,18,19,20,22,23,27,29,30,31,32,33,34,35,37,42,45,46` (V2.0) +
`21,24,25,26,36,38,39,40,41,47` (V3.0) + `28` **unassigned** —
`BRG-28` (broker server time-drift detection) carries no release in the
workbook: it is the PRD backlog audit's one ERROR finding (placeholder
requirement, `docs/39-prd-change-log.md` §2) and must be defined into a
train or deleted before the Phase-1 contract freeze. It is therefore
*not* counted in any release above.

**Release pull-forward (D78, docs/63, 2026-09-25):** `BRG-21` (broker
streaming, workbook V3.0) is delivered in **V1** as the primary ingest path —
the 60-s poll plan breaks MetaApi's per-server CPU-credit limit at V1 scale
and cannot reach V2 at all (docs/63 F1). The workbook row is unchanged; the
pull-forward is recorded here, in docs/63 §5 and docs/99. The V3.0 count
above still lists it for workbook parity.

## 2. Architecture

```
 LCC (commands: provision, disable, close, enable, archive)
 EVL (verdicts back to LCC; publishes advisory floor hints → bridge, docs/09 §3.8)
        │  account_commands (PG) / broker_executions
        ▼
┌──────────────────────── bridge service (Go, 1 instance V1) ───────────────────────┐
│  stream ingest ── gRPC (UDS) frames from bridge-stream: equity/account/positions/ │
│                   deals/sync/health; per-account hot state + stream_seq (D33)     │
│  normalizer ── decimal strings → canonical (symbol, side, lots, px, cents, time)  │
│  conflator  ── trigger rules → bridge.tick candidates (docs/63 §4.4, D79)         │
│  group-commit writer ── PG tx ≤25 ms: snapshots + deals + outbox + NOTIFY         │
│  fallback poller ── REST, credit-budgeted, only accounts whose stream is `stale`  │
│  executor   ── commands: retry, circuit-break per account, confirm (re-read)      │
│  reconciler ── nightly: full fetch vs stored state → exceptions                   │
│  health     ── stream states + failure counters → ops.provider_health             │
└───────────────────────────────────────────────────────────────────────────────────┘
        ▲ gRPC bidi over Unix socket               │ REST (https, API key): commands,
        │                                          │ fallback, D33 checks, reconciler
┌─ bridge-stream (Node/TS sidecar, official metaapi.cloud-sdk, D77) × S shards ─┐
│  SynchronizationListener per account · no money math · no persistence         │
└───────────────┬───────────────────────────────────────────────────────────────┘
                │ socket.io streaming (0 CPU credits)
                ▼
   MetaApi cloud ──► MT5 broker servers (server groups: BRG-12)
```

**MetaApi model (V1 facts, docs/63 §2):** one **MetaApi account** (our platform
key) can manage many MT5 logins on many servers. Per login there are two data
channels:
- **Streaming (primary, D78).** Server-push terminal-state sync: account
  information, positions, orders, deals, and `prices` packets that carry
  **broker-computed equity/margin/freeMargin/marginLevel**. Packets are
  sequence-numbered, and the channel costs zero CPU credits. It is reachable
  in practice only through MetaApi's SDK (JS/Python/Java), hence the Node
  sidecar (D77).
- **REST/RPC (fallback, commands, reconciliation).** Account info, positions,
  orders, deals/history, symbols, server time. Metered in CPU credits: 50 per
  state read; 18k/min per MetaApi front-end server.

There are no account-state webhooks (docs/63 F8). Cost: ~$50–100/mo **per MT5 account** (PRD estimate) — this is why
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
  Stream(ctx, logins <-chan Subscription) (<-chan Frame, error) // BRG-21 (V1 per D78):
                                                  // ordered per-login frames (equity,
                                                  // account, positions, deal, sync, health);
                                                  // polling-only adapters return ErrNoStream
                                                  // and the bridge polls (docs/63 §4.7)
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
4. BRG reports `broker.created` → LCC activates account → credential delivery (D74, docs/62: no automated email in V1 — staff copy from the ADM detail view, sensitive-read audited; automated V2 template later)
   (NOT + DOC template, one-time reveal in TD).
5. Failure: attempts ≤ 2, then `broker.failed` (LCC state) + CON alert.
6. **MetaApi account settings (docs/63 §4.9):**
   - `reliability`: `high` for funded accounts; per program for challenges,
     default `regular`. The ×2 slot cost is passed through (docs/22 §3.4).
   - `region`: `broker_groups.metaapi_region`.
   - `resourceSlots`: 1.
   - `riskManagementApiEnabled`: `false`, unless the D80 V2 watchdog is on.
   - `metastatsApiEnabled`: `false`.

   BRG subscribes the stream only once the account is `DEPLOYED` and
   `CONNECTED`. G2 infrastructure is required: G1 throttles quotes to one
   per 2.5 s.

### 3.3 Sync (BRG-07/08/09/21) — the hot path: streaming ingest (D78/D79, docs/63)

**Primary: streaming.** The `bridge-stream` sidecar (D77) holds one MetaApi
streaming subscription per active account and forwards ordered frames to
the bridge over local gRPC. The bridge keeps per-account **hot state** in
memory and runs the **conflator** (docs/63 §4.4). A `bridge.tick` is
emitted only on these triggers:

| Trigger | Fires on | Flush |
|---|---|---|
| `deal` | any new deal | urgent |
| `position` | open-position set changed | urgent |
| `guard` | equity inside the guard band (default 50 bps of initial balance) above an **EVL floor hint** (docs/09 §3.8); ≤ 4/s per account | urgent |
| `guard` (crossing) | equity ≤ a floor hint — **never rate-capped** (I-21) | urgent |
| `material` | \|Δequity\| ≥ 10 bps of initial balance since the last tick; ≤ 1 per 10 s per account | normal |
| `heartbeat` | 60 s with open positions / 300 s when flat, **only while the stream is `live`** | normal |
| `resync` | synchronization completed / broker reconnected | urgent |

**The group-commit writer** flushes on the first of three: 25 ms, 500
rows, or an urgent tick. Each flush is **one transaction** (ADR-6 intact):

```
tx:
  UPSERT broker_accounts(login) SET equity, balance, margin, free_margin,
         leverage, server_time, last_synced_at, last_deal_ticket, stream_state, last_stream_seq
  UPSERT broker_positions (open set; delete closed rows → into history)
  INSERT broker_deals (new deals; ON CONFLICT (login, deal_id) DO NOTHING)
  UPSERT account_snapshots (minute bucket; equity_low/high widened with LEAST/GREATEST)
  INSERT outbox: bridge.tick {account, equity, margin, positions[...], deals_count, broker_time,
                              trigger, source, stream_seq, equity_low_cents, equity_high_cents}
  SELECT pg_notify('outbox_doorbell', '')      -- relay wake-up only (docs/04 §3.3)
```

**Hard rules:**
- Equity is the broker's number, taken from the raw `prices` /
  `accountInformation` packet. The SDK's local recompute is never used
  (docs/63 F5; docs/09 §3.3).
- Numbers cross the sidecar boundary as decimal strings. The rounding to
  cents happens here, per the docs/09 table.
- A floor hint only changes *when* a tick is emitted, never what EVL
  decides.

**Fallback: polling** (the pre-D78 poll loop, demoted). An account whose
stream is `stale` for > 30 s (§3.6) gets REST-polled every 60 s,
configurable per tenant 30–300 s, producing ticks with `source = poll`.
- **Budget:** a hard CPU-credit budget per MetaApi `client-id` (≤ 80 % of
  the 18k credits/min per-server limit; one poll ≈ 176 credits), with
  client-ids rotated across front-end servers.
- **Overflow** (a MetaApi-wide outage): funded and open-position accounts
  are polled first; the rest ride `evl.tick_stale`.
- **After any command** an immediate refresh runs: the hot state if the
  stream is `live`, else a REST re-poll.

**Resync** (on every stream (re)synchronization):
- The SDK's `HistoryStorage` is PG-backed: `lastDealTime()` =
  `max(broker_deals.deal_time) − 5 min`, so MetaApi replays only the recent
  deals.
- After `dealsSynchronized` the D33 history-window check (below) runs,
  then a `resync` tick is emitted.
- Resubscribe order after a restart: guard-band accounts → funded → open
  positions → the rest. Cold resync takes < 30 s at V1 and ≈ 1–2 min at
  10k accounts; **≈ 10–20 min at the corrected V2 target of 100k accounts
  — so a fleet-wide resync is never performed: it is rolling per shard
  (2,000 accounts, ≈ 12–24 s of `evl.tick_stale` blindness, 2 % blast
  radius), and a simultaneous restart of all ≈ 50 shards is a declared
  maintenance window announced per tenant via CON-15 (docs/63 §4.7).**

- **Canonical model** (BRG-19 core): amounts Decimal(18,8) for prices, lots
  Decimal(10,2), broker `time` (ms) as the trading clock, platform-side
  `received_at`. Normalization is a pure function — property-tested against
  fixture feeds (BRG-43 contract suite runs the same fixtures per adapter).
- **Gap detection (V1, D33 — eleventh pass, docs/51):** MT5 deal tickets are
  **server-global** counters, not per-login contiguous, so ticket arithmetic
  (`min(new) > last + 1`) would alarm on nearly every poll. The V1 check is a
  **history-window count**: per account, deals in `[last_synced_at − overlap, now]`
  fetched from the history API vs rows written this window. Under D78 the
  check runs **at every stream (re)synchronization**, plus an hourly sweep,
  plus the nightly reconciler — not "per poll" (docs/63 F9). The fallback
  poller keeps the per-poll check; count mismatch →
  `bridge.sync_gap` event + WARN alert (missing deals = potentially missing
  trades; EVL treats the gap as *evidence unavailable* — it does not assume,
  and ADM is paged for manual review). `last_deal_ticket` stays the incremental
  fetch **cursor** only — never a continuity oracle. (BRG-33 V2 adds per-deal
  hash reconciliation on top. The bridge-assigned per-account `seq` in the
  pf-platform scaffold is the same lesson: ordering cursors must be ours, not
  the broker's.)
- **Equity snapshots:** every ingested equity frame updates the
  `account_snapshots` minute bucket (last value + `equity_low_cents` /
  `equity_high_cents` observed in the minute — honest candles, D79;
  downsampled: 1 row/account/min, 14-day rolling in PG, daily rollup to ANA read model;
  multi-resolution = LCC-42 V2).
- **Slot alerts (BRG-34):** fallback-poll backlog > 2 min → WARN; > 10 min →
  CRITICAL. Stream analogues: `bridge`-topic relay lag > 5 s → WARN, > 30 s →
  CRITICAL (docs/63 F6); > 5 % of accounts `stale` → WARN, > 20 % →
  CRITICAL (evaluation fairness at risk — documented in the SLOs, 29 §4).

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

**Stream health (D78, docs/63 §4.7).** Each account's stream state is
`subscribing → syncing → live → stale`, stored as
`broker_accounts.stream_state`.
- **`stale` triggers:** SDK `onDisconnected` / `onStreamClosed`,
  `connectedToBroker = false`, or no data or `Health` frame for 90 s. (The
  SDK itself declares a disconnect after 60 s without a `status` packet.)
- **While `stale`:** no heartbeat ticks are emitted, so EVL's
  `evl.tick_stale` engages. After 30 s the fallback poller takes the
  account.
- **Metrics** (into `ops.provider_health`): stream-state counts; SDK
  `latencyMonitor` price/update latency p95; `seq_regression`;
  resyncs/min; fallback-poll credit burn.
- **MetaApi 429s** (`TooManyRequestsError`) honour `recommendedRetryTime`
  (`brg.rate_limited`). A subscription-server-full response switches
  `client-id`.

## 4. Events (topic `bridge`)

### 4.1 V1 baseline events — authoritative (tenth pass D28)

| Event | Producer (V1) | V1 consumers |
|---|---|---|
| `bridge.tick` | BRG (streaming conflator, per account, event-driven — deal/position/guard/material/resync triggers + heartbeat ≤ 60 s with open positions, ≤ 300 s flat; fallback poll 60 s — D78/D79, docs/63 §4.4) | EVL (evaluate), ANA (equity points) — the observed record per EVL-49; no audit mirror (docs/05 §14) |
| `bridge.sync_gap` | BRG (history-window count mismatch — D33) | ADM (manual review), AUD, EVL (gap_flagged verdict) |

### 4.2 Extended (post-V1) event model — design-level

| Event | When | Key fields | Consumers |
|---|---|---|---|
| `bridge.account_created` / `bridge.account_create_failed` | provisioning | login, server, reason | LCC, NOT, CON |
| `bridge.trading_disabled` / `bridge.trading_enabled` | after confirmed command | account, by (command ref) | LCC (confirm transition), AUD |
| `bridge.positions_closed` | after confirmed close-all | closed_count, total_pnl_cents, broker_time | LCC, AUD, NOT (breach evidence) |
| `bridge.sync_gap` | deals-count mismatch in the sync window (D33) | account, window_start, expected_count, got_count | ADM (manual review), AUD, EVL (gap_flagged verdicts) |
| `bridge.reconciliation_exception` | nightly mismatch | account, kind, delta | ADM, AUD, CON |
| `bridge.command_dead` | terminal command failure | command_id, reason | CON (CRITICAL), AUD |
| `ops.provider_health` | 5 min | success_rate, p95_ms, state, streams_live, streams_stale, stream_latency_p95_ms | CON, dashboards |
| `bridge.watchdog_divergence` | V2, D80: a MetaApi risk-management tracker event with no matching EVL breach within 30 s (live stream) | account, tracker_id, period, absolute_drawdown, broker_time | ADM (review), CON — **never** LCC (BVR-28) |

## 5. Lifecycles

- **Broker account:** `created → active (syncing) → disabled (trading off) →
  archived (V2)`. Mirrors LCC account state but broker-side; `bridge_state`
  column on `broker_accounts` + nightly comparison with LCC state (LCC-33).
- **Stream session (D78):** `subscribing → syncing → live ⇄ stale →
  (fallback polling) → syncing …` per account. Every entry to `syncing`
  resumes from the PG deal cursor. Every exit to `live` runs the D33
  history-window check and emits a `resync` tick.
- **Fallback sync cycle:** `scheduled → polled → written → (gap? | clean)`,
  per `stale` account only. `last_deal_ticket` is the incremental cursor
  (monotonic); gap judgment is the D33 history-window count.
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
| `brg.sync_gap` | internal WARN | Deals-count mismatch in the sync window (event + ADM review) |
| `brg.credentials_missing` | internal CRITICAL | Provisioned account missing creds (should never happen) |
| `brg.symbol_unknown` | internal | Normalization hit unmapped symbol (BRG-32 V2 mapping mgmt; V1: alert + skip with log) |
| `brg.stream_stale` | internal WARN | Account stream not `live` (disconnect / broker offline / 90 s silence) — no heartbeat ticks; fallback poll after 30 s (docs/63 §4.7) |
| `brg.stream_desync` | internal WARN | Stream ordering failure, sequence regression, or critical-frame queue overflow at the sidecar boundary → forced resync (never silent loss, I-23) |
| `brg.rate_limited` | internal WARN | MetaApi 429 (`TooManyRequestsError`) on REST or subscribe — back off to `recommendedRetryTime`; rotate `client-id` for per-server limits |

## 7. API endpoints
### 7.1 V1 baseline — `brg` (see `contracts/api/brg.md`)

**No HTTP surface in V1** — this is an internal/service contract. The internal contracts (what other modules call, what workers run, what is enforced) are in `contracts/api/brg.md`.

### 7.2 Extended (post-V1) surface — provisional

> Not in the V1 execution sheet. Design-level; paths beyond the V1 baseline are provisional until the URL-plan decision (`contracts/api/gw.md`, open question). Shown for platform completeness (V2/V3 phases, docs/99).

Internal (service tokens):

- `POST /internal/v1/bridge/commands/{id}/retry` — retry a failed enforcement command from CON tooling.
- `GET /internal/v1/bridge/accounts/{login}/state` — debug read of a broker account's bridge-side state.
- `POST /internal/v1/bridge/reconcile` — trigger a manual BRG↔broker reconciliation run.

Staff (ADM V2 broker management, BRG-26/34 surfaces):

- `GET /v1/admin/broker/groups` — list broker server groups with account counts.
- `GET /v1/admin/broker/accounts` — list broker accounts, filterable by `?state=`.
- `GET /v1/admin/broker/accounts/{login}/positions` — read live positions for one broker account.
- `GET /v1/admin/broker/health` — provider health: success rate, p95, syncing accounts, backlog.

Trader (TD): no direct BRG endpoints — all via LCC/ANA surfaces (positions &
history = TD-08 reads ANA read model fed by `bridge.tick`/deals).
## 8. Schema (key shapes)

```jsonc
// bridge.tick (event payload.data)
{ "account_id": "01J9ACC...", "broker_login": "50001234",
  "equity_cents": 10412000, "balance_cents": 10412000, "margin_cents": 212000,
  "free_margin_cents": 10200000, "leverage": "1:500",
  "positions": [ { "position_id": "50001234-1", "symbol": "EURUSD", "side": "buy",
                   "lots": 0.50, "open_price": 1.08420, "current_price": 1.08510,
                   "sl": 1.08120, "tp": null, "opened_at": 1758275000000,
                   "profit_cents": 45000, "swap_cents": -1200, "commission_cents": -300 } ],
  "deals_count": 2, "last_deal_ticket": 88231, "broker_time": 1758278400000,
  // D79 additive, optional (docs/63 §4.4) — absent on pre-D78 producers
  "trigger": "material",            // deal|position|guard|material|heartbeat|resync
  "source": "stream",               // stream|poll|resync
  "stream_seq": 482113,             // bridge-assigned per-account monotonic (D33)
  "equity_low_cents": 10398000,     // observed extremes since the previous tick —
  "equity_high_cents": 10415500 }   // dispute evidence; EVL V1 decides at equity_cents

// GET /v1/admin/broker/health
{ "data": { "provider": "metaapi", "state": "healthy", "success_rate_1m": 0.999,
    "p95_ms": 420, "accounts_syncing": 431, "backlog_seconds_p95": 7,
    "streams": { "live": 429, "syncing": 1, "stale": 1, "price_latency_p95_ms": 180 },
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
  poll_interval_s INT NOT NULL DEFAULT 60,     -- fallback poll cadence (D78: stream is primary)
  metaapi_region  TEXT,                        -- MetaApi region for this group (docs/63 §4.9)
  quote_interval_ms INT NOT NULL DEFAULT 1000 CHECK (quote_interval_ms >= 250), -- stream quotes
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
  last_margin_cents  BIGINT, last_free_margin_cents BIGINT,
  last_deal_ticket   BIGINT NOT NULL DEFAULT 0,
  last_synced_at     TIMESTAMPTZ,
  server_time        TIMESTAMPTZ,          -- last broker-attested time
  fail_streak        INT NOT NULL DEFAULT 0,
  stream_state       TEXT NOT NULL DEFAULT 'subscribing'      -- D78, docs/63 §4.7
                     CHECK (stream_state IN ('subscribing','syncing','live','stale','unsubscribed')),
  stream_state_at    TIMESTAMPTZ,
  last_stream_seq    BIGINT NOT NULL DEFAULT 0,               -- bridge-assigned (D33)
  metaapi_reliability TEXT NOT NULL DEFAULT 'regular' CHECK (metaapi_reliability IN ('regular','high')),
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  archived_at        TIMESTAMPTZ,
  UNIQUE (login)
);
CREATE INDEX idx_bacc_tenant_state ON broker_accounts(tenant_id, state);
CREATE INDEX idx_bacc_sync ON broker_accounts(state, last_synced_at) WHERE state = 'active';
CREATE INDEX idx_bacc_stale ON broker_accounts(stream_state_at) WHERE stream_state = 'stale'; -- fallback poller

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

CREATE TABLE account_snapshots (              -- §3.3: 1 row/account/min, 14-day rolling (D35)
  account_id      ULID NOT NULL,
  bucket_ts       TIMESTAMPTZ NOT NULL,       -- minute bucket (UTC)
  tenant_id       ULID NOT NULL,
  login           TEXT NOT NULL,
  equity_cents    BIGINT NOT NULL,
  balance_cents   BIGINT NOT NULL,
  margin_cents    BIGINT,
  free_margin_cents BIGINT,
  equity_low_cents  BIGINT,                   -- D79: observed min/max broker equity in the
  equity_high_cents BIGINT,                   -- minute (streaming; NULL on fallback-poll rows)
  broker_time     TIMESTAMPTZ,                -- broker-attested time of the tick
  received_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (account_id, bucket_ts)
) PARTITION BY RANGE (bucket_ts);
-- daily partitions; retention = 14-day rolling (partition DROP; BRG job) with the
-- daily rollup exported to the ANA read model first (docs/19). PAY eligibility and
-- TD intraday equity curves read here (BRG-09 refreshes the latest row on demand).

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
| Ingest (D78) | streaming: ≈ 431 accounts, ≤ 862 subscriptions (high reliability = 2 instances), ~10 sockets, 1 sidecar shard; **0 CPU credits** steady-state | **v1.1 corrected — 100k accounts (10 tenants × 10k):** ≤ 200k subscriptions (quota 10 × deployed = 1M ⇒ 5× headroom), **~2,000 sockets, ≈ 50 shards** (≤ 2k accounts each, **5 per tenant — the shard hash is `(tenant_id, account_id)`**, docs/63 §4.2), **≥ 334 `client-id` slots (≤ 300 accounts/user/server ⇒ ≥ 28 MetaApi user accounts)**; inbound equity frames **≈ 30k/s (burst 100k/s)** absorbed in memory. **≈ 75 GB of shard RSS at the 1.5 GB/shard alarm ⇒ docs/63 F12: this tier does not fit the ADR-9 single box; a 2nd box is a V2 prerequisite and takes `bridge-stream` first** (docs/29 §3.1) |
| Tick emission (D79) | ≈ 10/s sustained, ≈ 100/s burst | **≤ 2,500/s sustained, ≤ 10k/s burst** — still the same *order* as the old 60-s poll plan (100k × 1/min = 1,667/s) at sub-second latency on verdict-relevant moves, but the *magnitude* breaks 13-month PG retention (docs/63 F13: ≈ 85 B rows over the ≈ 395-day window ≈ 34 TB ⇒ ≤ 7 d hot + R2 columnar archive). Per-row derivation: docs/63 §4.4 |
| REST credit budget | fallback + resync D33 checks + reconciler only; one poll ≈ 176 credits; per-server limit 18k/min ⇒ ≈ 100 polled accounts/min per `client-id` (rotate across servers) | the old poll-everything plan would need **≈ 17.6M credits/min vs ≈ 216k/min for all MetaApi servers (≈ 81× over)** — **why D78 exists, and why the correction strengthens rather than changes it** (docs/63 F1). The fallback budget itself is **12 × 80 = 960 accounts/min platform-wide if MetaApi's per-server limit is global, or 9,600/min if it is per (`Client-Id`, server)** — docs/63 §4.7/Q8; plan against the pessimistic reading |
| Sync tx size | group commit: ≤ 40 tx/s per bridge instance, ≤ 500 rows each | **≈ 4,300 rows/s sustained, ≈ 11,800 rows/s burst ⇒ ≈ 9 tx/s and ≈ 24 tx/s — inside the cap, but ≥ 2 bridge instances partitioned per tenant for the 30k frames/s ingest** (docs/63 §4.11). PG write capacity is *not* "fine to 10×": the evaluation path is ≈ 20k q/s at burst against a ≈ 10k q/s primary — docs/29 §3.4 |
| Deals table | ~50 deals/day/account → ~21k/day | **~5M/day → ~450M rows in the 90 d hot window (~150 GB at ~330 B/row)**; partitioned by `(tenant_id, day)` so retention is `DROP PARTITION`, archive to R2 |
| Snapshots | 1 row/min/account → ~620k rows/day | **~144M/day → ~2.0 B rows in the 14 d rolling window (~400 GB at ~180 B/row heap + PK index)**; partitioned by `(tenant_id, day)`; downsample to 1/min min + daily rollups; ANA owns long-term and **reads the replica, never the primary** (docs/29 §3.4.3) |
| Cold resync (v1.1) | < 30 s | **≈ 10–20 min fleet-wide ⇒ never performed fleet-wide.** Rolling **per shard**: 2,000 accounts (one tenant's 1/5) at a time, ≈ 12–24 s of `evl.tick_stale` blindness, 2 % blast radius. A simultaneous 50-shard restart is a declared maintenance window announced per tenant via CON-15 (docs/63 §4.7) |
| Tenant fairness (v1.1) | n/a (one tenant) | **Per-tenant `bridge` streams (`topic.bridge.{tenant_id}`) + tenant-owned `workers` lane sets (D82, docs/63 §4.13), and per-tenant load-shed levels published as `evl.load_shed` (D84, docs/63 §4.14).** One tenant = one shard set = one stream = one lane set = one credit budget: a single isolation unit an operator can reason about |
| Command latency | p95 < 2 s (confirm included) | same; CRITICAL if p95 > 10 s over 15 min (enforcement lag = risk) |
| MetaApi outage | streams `stale` → credit-budgeted fallback poll (funded/open-position first), others `evl.tick_stale`; queue commands, backlog alerts | failover server group (V3 BRG-26): groups span 2 MetaApi servers from day 1 (config), second server activated by CON flip |
| Cost | per-account pricing → account caps are cost control (TEN limits) | BRG-47 cost tracking (V3) feeds CON |

## 12. Open-source solutions

| Option | Verdict |
|---|---|
| **MetaApi** (commercial, register must-integrate) | **CHOSEN V1** — only realistic MT5 management API without a MetaQuotes partnership; ~$50–100/account/mo |
| MetaApi **streaming API** via official `metaapi.cloud-sdk` (JS; source-available licence, docs/34) | **CHOSEN V1 ingest (D77/D78)** — zero CPU credits, broker equity on every price packet, sequence-numbered; hosted in the `bridge-stream` Node sidecar |
| MetaApi REST/RPC | **V1 fallback + commands + reconciliation** — credit-metered (F1 of docs/63 rules it out as the steady-state feed) |
| MetaApi **risk-management API** (trackers, tracker-event stream) | **V2 optional watchdog, off by default (D80)** — alarm + stale-stream refresh trigger; never a verdict source (BVR-28); billed per account-hour; no MT5 netting |
| MetaApi MetaStats / CopyFactory | Not on the ingest path (docs/63 §2); MetaStats = possible V2 TD/ANA enrichment; CopyFactory = TRD V3 only |
| MetaQuotes Manager API (C++) | Requires partnership + C++ wrapper service — V2+ option if cost/limits bite |
| mql-zmq / MQL5-JSON-API (self-hosted EA bridge) | V2+ option for direct server access (research-validated); rejected V1 (ops weight, no multi-tenant story) |
| FIX engines (quickfix, etc.) | Out of scope — Alpha One is not an execution venue (research §4.1 applies to LP-routing firms) |
| cTrader Open API (protobuf) | V3 adapter (BRG-24); spec is open, SDKs exist |
| Nautilus Trader / full OSS platforms (research §4.9) | Rejected — they solve order execution, not prop-firm ops |
| Hyperswitch/Stripe (payments) | Not BRG (CHK/PAY) |

## 13. Technology stack

Go bridge service (stream ingest, conflator, group-commit writer, REST client,
fallback scheduler, executor); **`bridge-stream` sidecar — Node 22 LTS /
TypeScript + `metaapi.cloud-sdk` pinned 29.3.3** (D77; frames only, no money
math, gRPC over a Unix socket to the bridge); Postgres (snapshots/deals/
executions, partitioned; `NOTIFY` doorbell to the relay); Redis (scheduler
dedupe, circuit-breaker state, `evl.floors` hint pub/sub); MetaApi (streaming +
REST); Prometheus (stream states, SDK latency monitor, fallback backlog,
provider health); Sentry (normalization
panics = P1); Uptime Kuma (MetaApi status page cross-check).

## 14. Integration — internal modules (glue)

| Module | How |
|---|---|
| **LCC** | consumes `account_commands` (provision/disable/close/enable/archive); reports `broker.created/failed` + confirms back (LCC transition preconditions) |
| **EVL** | consumes `bridge.tick` → verdicts; EVL never calls MetaApi; reads positions/equity from PG snapshots (or gets them in the tick payload). **Return path (D79):** EVL persists advisory floor hints (`evaluation_state.floor_*`, docs/09 §3.8) + `evl.floors` pub/sub; the conflator reads them to decide *when* to emit — never *what* is decided |
| **RSK (V2)** | consumes deals/positions for anti-gaming patterns (news trading, hedging, latency) from PG — deals now land within one group commit (≤ 25 ms) of the broker event; RSK still never subscribes to ticks (docs/10 §3) |
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
| 2. MetaApi client + connector (info/positions/deals-since/create) + normalizer + **fixture corpus** (REST responses **and** SDK `packetLogger` stream recordings) | BE-1 | 4 d | 0, 1 | unit: 200 recorded MetaApi responses normalize deterministically |
| 2a. **`bridge-stream` sidecar (D77)**: SDK listener per account → `bridge.ingest.v1` frames over gRPC/UDS; `PgHistoryStorage` cursor; primary-instance pinning; bounded queues (equity latest-wins, critical frames never dropped); latency monitor → Prometheus | BE-1 | 5 d | 2 | 3 demo accounts stream 24 h; a `prices` fixture without `equity` yields no equity update (F5); forced disconnect → `stale` → resync from cursor with no duplicate deals |
| 3. Stream ingest + conflator (docs/63 §4.4) + group-commit writer + NOTIFY doorbell + fallback poller (per-tenant credit budget, stagger, re-poll after commands) + gap detection + `bridge.tick` | BE-1 | 5 d | 2a | 3 test accounts sync 24 h clean; I-21 property test green (no floor crossing conflated away); injected gap → event + alert; stream kill → fallback poll within 30 s |
| 4. Provisioning (create → creds encrypt → broker.created) + the credential-delivery path (D74, docs/62: the ADM sensitive-read reveal, staff-delivered in V1) | BE-1 | 3 d | 2, LCC | end-to-end: LCC command → real MT5 account → staff reveal is audited and the trader receives credentials through the firm's channel (staging) |
| 5. Executor (disable/enable/close-all) + confirm re-reads + circuit breaker + command_dead | BE-1 | 3 d | 3, LCC | breach on sandbox: positions closed < 10 s, confirmed empty |
| 6. BRG-43 **adapter contract test suite** (fixtures + lifecycle scenarios, runnable per adapter) | BE-1 | 2 d | 2–5 | CI job `bridge-contract` green; a fake broken adapter fails it |
| 7. Reconciliation (nightly) + provider health + dashboards + alerts | BE-2 | 3 d | 3, 5 | injected mismatch detected; MetaApi 500s → degraded state visible in CON |
| 8. BRG-44 credential encryption + log-scanner test + reveal integration with LCC | BE-2 | 1.5 d | 4 | scan: zero credential material in logs/events (property test) |
| 9. V2: MatchTrader adapter (BRG-03) behind same contract; capability declarations; reconciliation full; symbol mapping; multi-server; archive; password reset | BE-1 | 3 wks | 6 | adapter #2 passes BRG-43 with zero core changes |
| 9a. V2 (D80, optional): MetaApi risk-management watchdog — tracker provisioning mirrored from the rule pack, tracker-event long-poll cursor, `bridge.watchdog_divergence` | BE-1 | 1 wk | 3 | off by default; divergence surfaced to ADM; never transitions LCC |
| 10. V3: cTrader/DXtrade adapters (streaming where the platform offers it, BRG-21 via `Connector.Stream`) + cost tracking (BRG-47) | BE-1 | 4 wks | 9 | — |

**Risks (the platform's riskiest):** MetaApi cost/limits/pricing change →
mitigation: account caps, streaming ingest (0 CPU credits) with credit-budgeted
fallback polling (D78), SDK pinned + recorded-packet replay gate on upgrades,
adapter interface keeps escape
hatches (direct EA bridge, second provider) warm; MetaApi outage → mitigation:
command queueing + failover group config from day 1; sync lag during MetaApi
degradation → mitigation: SLO on enforcement latency + backlog alerts +
documented risk acceptance in 29 §5.

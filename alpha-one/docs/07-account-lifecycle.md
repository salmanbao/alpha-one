# 07 — LCC: Account Lifecycle

> Covers PRD module **LCC** (44 requirements). LCC owns **the trader account
> aggregate** — the thing a trader buys, trades, passes, gets funded on, pays out
> from, and (possibly) fails. Every other core module (BRG, EVL, PAY, KYC, DOC,
> NOT) hangs off LCC state. If LCC's state machine is wrong, everything downstream
> is wrong, so this document is the most important one after 01.

## 1. Purpose & scope

One **trader account** = one program enrollment (a challenge or a funded account)
for one trader at one tenant, 1:1 with one **broker account** (created by BRG).
LCC decides *what state the account is in and what may happen next*; EVL decides
*whether a tick/verdict justifies a transition*; BRG *executes broker-side
effects*; PAY *moves money*.

Requirement coverage: `LCC-01,02,03,05,06,07,11,20,23,27,41,43,44` (V1.0/V1.1: 11 is V1.1) +
`04,08..10,12..19,21,22,24..26,28,29,31..40,42` (V2.0) + `30` (V3.0: scaling plans).

## 2. Architecture

```
 CHK order.paid ──────────────┐
 ADM manual actions (V2) ─────┤
 EVL verdict (ok|breach|hit) ─┼─► LCC transition engine  (single function, versioned rows)
 KYC gates ───────────────────┤        │
 PAY eligibility reads ───────┘        ▼
                          account_state_history (append-only) + outbox events
                                           │
                     ┌─────────────────────┼──────────────────────┐
                     ▼                     ▼                      ▼
                 BRG (execute)         NOT/DOC (notify)        ANA (read models)
              provision/suspend/       emails, certs,          KPIs, equity
              close positions          statements              curves
```

Rules:
- **One transition function.** Every state change — automated or manual — goes
  through `lcc.Transition(ctx, accountID, event, actor)`. There is no second path
  (this *is* LCC-41: no module flips state directly; BRG "enforcement" is BRG
  executing a command *issued by* LCC after transition).
- **Versioned rows (optimistic base, LCC-04 formal in V2):** every transition
  `UPDATE ... WHERE id=? AND version=?`; conflict → retry with fresh read, max 3,
  then `lcc.conflict` + alert (indicates a logic bug, not user error).
- **Deterministic terms (LCC-20):** at purchase, a **terms snapshot** (challenge
  template config + pricing + rule pack ref + payout terms) is frozen on the
  account. Template edits never touch live accounts. Funding freezes a second
  snapshot (funded terms).

## 3. System design

### 3.1 The state machine (LCC-02, V1 — binding)

States are exactly those named by LCC-02 (the V1 execution sheet; the
machine in `contracts/diagrams/account-state.md`, rendered PNG alongside).
Every transition is recorded with prior state, new state, trigger, actor,
inputs (LCC-03; AUD-01 storage).

```mermaid
stateDiagram-v2
    [*] --> CREATED: purchase paid (LCC-05, CHK-09)
    CREATED --> ACTIVE: broker account provisioned + credentials delivered (BRG-05, BRG-06)
    ACTIVE --> PASS_PENDING: objectives met (EVL-19)
    ACTIVE --> BREACH_DETECTED: hard breach (EVL-17)
    BREACH_DETECTED --> ACTIVE: breach override (EVL-20, V1.1 — D29)
    FAILED --> ACTIVE: breach override (EVL-20, V1.1 — D29)
    ACTIVE --> SUSPENDED: admin suspend (LCC-11, V1.1)
    PASS_PENDING --> VERIFICATION: queued for verification per config (EVL-19)
    PASS_PENDING --> AWAITING_ACTIVATION: activation fee configured (LCC-08)
    VERIFICATION --> AWAITING_ACTIVATION: approved, fee due (LCC-06 + LCC-08)
    VERIFICATION --> TERMINATED: verification rejected
    AWAITING_ACTIVATION --> TERMINATED: payment window elapsed, no fee
    BREACH_DETECTED --> CLOSING: disable-then-close commands enqueued (EVL-17, BRG-10)
    CLOSING --> FAILED: broker confirms closure (BRG-11)
    FUNDED --> SUSPENDED: admin suspend (LCC-11, V1.1)
    SUSPENDED --> ACTIVE: resume from evaluation-phase suspend (LCC-11)
    SUSPENDED --> FUNDED: resume from funded-phase suspend (LCC-11)
    FUNDED --> TERMINATED: end of engagement (LCC-27)
    FAILED --> TERMINATED: archival (LCC-27)
    FAILED --> [*]: terminal; cleanup done (LCC-27)
    TERMINATED --> [*]: terminal-only; no outgoing edges (LCC-27)
```

Admin force-terminate (LCC-27): `<any> → TERMINATED`.

`TERMINATED` is **terminal-only** — no outgoing edges. LCC-27 cleanup
guarantees no orphaned broker state (close open positions, disable at the
broker, broker confirmations written back, audit); a dead account cannot
transition. `FAILED` is terminal **except** for the breach-override reversal (EVL-20,
V1.1 — the two edges above; tenth pass D29): the only way out is a validated
override record. The funded stage is `status = FUNDED`, not a phase
(`data/dictionary.md` §1–2).

**Spawn edges** — the passing account terminates at `PASS_PENDING`,
`VERIFICATION`, or `AWAITING_ACTIVATION` and a **new account** is created
(not a transition of the same row):

- Next-phase creation (mid-challenge pass): new `CREATED` with
  `parent_account_id` set (LCC-06).
- Funded creation (final-phase pass, no activation fee): new `FUNDED`.
- Funded creation (activation fee paid): new `FUNDED`.

(When KYC timing gates funding, the spawned funded row is created on
`kyc.approved`; the waiting row carries the `funding_pending` status — a row
status, not a machine state.)

**KYC timing enum** (per challenge config, LCC-07 / KYC-07 / KYC-08
gating): `{at_creation, after_evaluation, at_first_payout, skipped}`
(`data/dictionary.md` §3). KYC-03 (the config UI row) is V2.0 — V1
challenges may only use the subset their V1 gates can enforce.

> Citation note (from the research): the `AWAITING_ACTIVATION` hold-and-pay
> flow traces to LCC-08, which is **V2.0** in the Master Backlog — the state
> itself is fixed by LCC-02 (V1). Whether a V1 activation-fee product is
> intended is an open question (contracts/diagrams/account-state.md).

### 3.2 Transition table (V1 — the LCC-02 edge list)

| From | To | Trigger (owner) | Preconditions | Side effects (ordered) |
|---|---|---|---|---|
| CREATED | ACTIVE | broker account provisioned + credentials delivered (BRG-05, BRG-06) | broker create idempotent (idempotency key, BRG-05) | (tx) state + `AccountCreated` (LCC-23, outbox); credentials stored encrypted (BRG-44), delivered portal + email (BRG-06, NOT-03) |
| ACTIVE | PASS_PENDING | objectives met (EVL-19) | all objectives + day requirements | `PhaseAdvanced` / `AccountPassed` (LCC-23) per phase; DOC certificate on pass (DOC-04) |
| ACTIVE | SUSPENDED | admin suspend (LCC-11, V1.1) | guard per current state | BRG-14 disable trading; `Suspended` (LCC-23); payouts blocked (PAY-04) |
| ACTIVE | BREACH_DETECTED | hard breach (EVL-17) | verdict on fresh snapshot (EVL-05) | enqueue disable-then-close commands (EVL-17, EVT-20, `command_queue`); `AccountBreached` (LCC-23) |
| BREACH_DETECTED | CLOSING | disable-then-close enqueued (BRG-10) | — | enforcement worker executes with retries/backoff (BRG-10) |
| CLOSING | FAILED | broker confirms closure (BRG-11) | confirmation written back | FAILED recorded only after real closure (BRG-11); `AccountFailed` (LCC-23) |
| BREACH_DETECTED | ACTIVE | breach override (EVL-20, V1.1 — D29) | override record exists (`evaluation_overrides.id`, kind `clear_breach`) + step-up satisfied | (tx) state + history; BRG `enable_trading` command (closed positions stay closed); `account.state_changed` mirror; AUD critical |
| FAILED | ACTIVE | breach override (EVL-20, V1.1 — D29) | same guard; account not yet archived (LCC-27 archival not run) | same as BREACH_DETECTED → ACTIVE |
| PASS_PENDING | VERIFICATION | manual verification required per config (EVL-19) | config: verification queue | queue entry; audit |
| PASS_PENDING | AWAITING_ACTIVATION | activation fee configured (LCC-08) | config: fee + payment window | payment window starts (LCC-08) |
| VERIFICATION | AWAITING_ACTIVATION | approved, fee due (LCC-06 + LCC-08) | verification approved | fee window starts; `AccountPassed` (LCC-23) |
| VERIFICATION | TERMINATED | verification rejected | — | LCC-27 cleanup; `AccountFailed` (LCC-23) |
| AWAITING_ACTIVATION | TERMINATED | payment window elapsed, no fee | — | LCC-27 cleanup |
| SUSPENDED | ACTIVE | resume from evaluation-phase suspend (LCC-11) | account was suspended in evaluation phase | BRG-14 enable; `Resumed` (LCC-23) |
| SUSPENDED | FUNDED | resume from funded-phase suspend (LCC-11) | account was suspended in funded phase | BRG-14 enable; `Resumed` (LCC-23) |
| FUNDED | SUSPENDED | admin suspend (LCC-11, V1.1) | guard per current state | BRG-14 disable; `Suspended` (LCC-23); payouts blocked (PAY-04) |
| FUNDED | TERMINATED | end of engagement (LCC-27) | no in-flight payouts | LCC-27 cleanup (close positions, disable, confirm, audit) |
| FAILED | TERMINATED | archival (LCC-27) | — | archive (retention: trade history 7 yr, PII per GDPR — extended) |
| `<any>` | TERMINATED | admin force-terminate (LCC-27) | — | LCC-27 cleanup + critical audit |

State attributes (not states): `phase` (per-challenge ordinal,
`data/dictionary.md` §2), `parent_account_id` (phase lineage, LCC-06),
`terms_snapshot` (JSONB, frozen at creation), `funded_terms_snapshot`
(JSONB, LCC-20 at funded creation), `broker_account_id` (NULL until
provisioned), `failed_reason` (enum + details), `suspended_at/resumed_at`.

### 3.3 Clock semantics (day boundaries & time limits)

- Evaluation "days" and daily limits use **broker server time** (ADR-12, BRG-12):
  the rollover job runs at the broker server's midnight (per server group) and
  emits `account.day_rolled` (EVL consumes to reset daily counters).
- **Suspend/resume** (LCC-11): `max_trading_days` clock is a **duration**
  (trading_time_left seconds) decremented by rollover only while `ACTIVE`;
  `SUSPENDED` freezes it. No wall-clock expiry during suspension.
- Expiry check: rollover job + pre-expiry warnings (V2 LCC-26: 3d/1d/24h emails).
- **Suspension freezes everything (D31):** the rollover job skips accounts in
  `SUSPENDED` (and terminal) states — no `account.day_rolled`, no
  `trading_time_left`/calendar movement; EVL skips their ticks (no verdicts
  while frozen). On resume, the next fresh tick re-evaluates. (V1-Plus pause
  behaves the same via `paused_at`.)

### 3.4 Double-enforcement prevention (LCC-41) & breach idempotency (LCC-43)

1. Enforcement commands (close positions, disable trading) exist **only** as
   LCC-issued commands to BRG (command table, idempotency key =
   `enforce:{account}:{transition_id}`).
2. BRG sync loop **never** decides enforcement — it reports; it executes commands.
3. EVL verdicts carry `verdict_id`; `Transition` dedupes on
   `(account_id, verdict_id)` — a redelivered breach event (at-least-once bus)
   transitions at most once.
4. Post-condition monitor (V1, LCC-27): nightly job scans for accounts in
   `FAILED`/`SUSPENDED`/`CLOSING` states **with open positions on the
   broker** → alert + auto close-positions command (the "no orphaned open
   positions" guarantee).

### 3.5 Read side

`GET /v1/trader/accounts` (trader: own) and `GET /v1/admin/accounts`
(staff: all, filterable by status/phase/challenge/broker — ADM-05) return the
aggregate: state, phase, balances (from BRG snapshots), progress (from EVL),
credentials (reveal = audited sensitive read), terms (plain-language rendering
— TD-27), history (last N transitions). Equity curve & P&L come from ANA read models (LCC
does not store tick data — BRG snapshots + events are the source; LCC-18/42
V2 formalize snapshot policy).

## 4. Events (topic `account`)

### 4.1 V1 baseline events — authoritative

From `contracts/events/catalog.md` (the V1 execution sheet). Envelope EVT-03 (`id`, `type`, `version`, `tenant_id`, `occurred_at`, `payload`); schemas in `contracts/events/payloads/`. Producers write the outbox (EVT-01); consumers are idempotent by event id (EVT-05).

| Event | Producer (V1) | V1 consumers |
|---|---|---|
| `AccountCreated` | LCC-23 | NOT-01 (template: account created), ANA-01 |
| `PhaseAdvanced` | LCC-23 | ANA-01 |
| `AccountPassed` | LCC-23 | NOT-01 (template: phase passed), DOC-04 (certificate), ANA-01 |
| `AccountBreached` | LCC-23 | NOT-01 (template: breach), ANA-01 |
| `AccountFailed` | LCC-23 | NOT-01 (template: phase failed), ANA-01 |
| `FundedCreated` | LCC-23 | DOC-04 (certificate), ANA-01 |
| `Suspended` | LCC-23 | PAY-04 (payout hold while open), ANA-01 |
| `Resumed` | LCC-23 | ANA-01 |
| `account.activated` | LCC (CREATED → ACTIVE on `broker.created`) | BRG (start sync), EVL (start evaluation + create `evaluation_state`), NOT-01, AUD |
| `account.day_rolled` | LCC (rollover job at broker-server midnight, ADR-12; skips SUSPENDED — D31) | EVL (daily reset), ANA |

**Mapping to the extended model below:** V1 emits the single `AccountCreated` when the account exists in the lifecycle (the extended `account.purchased` stays internal V2 granularity (`account.activated` joined the V1 catalog in the tenth pass — D28, docs/50)); `AccountPassed` = the extended `account.phase_completed`; `AccountBreached` = `account.breached`; `AccountFailed` = `account.expired` / `account.closed`; `FundedCreated` = `account.funded`; `Suspended` / `Resumed` = `account.suspended` / `account.resumed`.

### 4.2 Extended (post-V1) event model — design-level

> The extended event set for V2/V3 (and internal V1 detail where marked); see the mapping above for how it relates to the V1 baseline. Topic, dedupe, and transport rules unchanged (docs/04 §5).

| Event | Produced on | Key fields | Consumers |
|---|---|---|---|
| `account.purchased` | order.paid | account_id, challenge, size, price | NOT, ANA, CON |
| `account.provisioning_failed` | broker.failed | reason, attempts | NOT, CON (manual retry), AUD |
| `account.activated` | broker.created | broker_account_id, server, phase | BRG (start sync), EVL (start eval), NOT, DOC, AUD |
| `account.day_rolled` | rollover job | broker_date, server | EVL (reset dailies) |
| `account.breached` | verdict.breach | rule_id, verdict_id, evidence_ref, broker_time | NOT, AUD (critical), RSK (case open V2), BRG (enforce cmd), TD (breach report) |
| `account.phase_completed` | target_hit | phase, metrics | NOT, DOC (cert), ANA |
| `account.funded` | funded.activated | funded_terms | NOT, DOC, ANA, PAY (eligibility on) |
| `account.paused` / `account.resumed` | tenant | reason | NOT, BRG, AUD |
| `account.suspended` / `account.reinstated` (V2) | admin suspend (LCC-11, V1.1); risk (V2 reinstate) | reason | NOT, BRG, PAY (block), AUD (critical) |
| `account.expired` | time-limit expiry (mirror of the `breach(time_limit)` verdict — D30) | rule_id | NOT, ANA |
| `account.closed` / `account.archived` (V2) | close | final_state | BRG (archive), NOT, AUD |
| `account.state_changed` (catch-all mirror) | every transition | from, to, actor, correlation | AUD (mirror), ANA |
## 5. Lifecycles

- **Account:** the LCC-02 state machine above (§3.1). Terminal states:
  `TERMINATED` (terminal-only, LCC-27 cleanup) reached from `FAILED`, `FUNDED`,
  `VERIFICATION`, or `AWAITING_ACTIVATION` (and force-terminate from any);
  `FAILED` itself is reversible only via the EVL-20 breach override (D29).
  Extended (V2/V3): archival with retention per LCC-36 (trade history 7 yr
  financial, PII per GDPR).
- **Credentials:** issued at `account.activated` (trading + investor passwords,
  encrypted BRG-06/44); resend (V2 LCC-17) rotates the **investor** password only
  (trading password reset is broker-side V2 BRG-13); reveal in UI = audited.
- **Terms snapshots:** immutable; "effective from" is the snapshot time.
- **Phase lineage (V2 LCC-10):** `account.phase_history[]` records each phase's
  start/end/metrics — multi-phase journeys (TD-29) render from it.

## 6. Error taxonomy
### 6.1 V1 baseline codes — authoritative

From `contracts/errors/taxonomy.md` (the V1 execution sheet; module LCC). These are the exact codes the V1 surfaces return; the envelope is GW-18 (`code`, `message`, `correlation_id`).
| Code | HTTP | Meaning | User-facing message |
|---|---|---|---|
| `account.not_found` | 404 | Account unknown or not owned by caller | "Account not found." |
| `account.not_active` | 409 | Action invalid from current state | "This action is not available for this account." |
| `account.terminal_state` | 409 | Operation on FAILED/TERMINATED account | "This account is closed." |
| `account.not_suspended` | 409 | Resume on non-suspended account | "This account is not suspended." |


Namespace `LCC`:
### 6.2 Extended (post-V1) codes — design-level

> Below the V1 baseline (6.1); names in the GW-18 dotted convention. Rows duplicating a V1 baseline code were folded into the baseline table (the merged registry: docs/30).


| Code | HTTP | Meaning |
|---|---|---|
| `lcc.account_not_found` | 404 | (cross-tenant probe → same 404) |
| `lcc.state_conflict` | 409 | Transition not allowed from current state (`details.from`, `details.event`) |
| `lcc.transition_conflict` | 409 | Optimistic-lock conflict after retries (alerted internally) |
| `lcc.broker_provisioning_failed` | 502 | Broker-side create failed (`details.reason` provider-safe) |
| `lcc.kyc_gate` | 422 | Funding/payout blocked by KYC level (`details.required`) |
| `lcc.paused` | 422 | Action not allowed while paused |
| `lcc.suspended` | 403 | Account suspended (risk) |
| `lcc.terms_frozen` | 409 | Attempt to modify live-account terms |
| `lcc.time_limit` | 422 | (V2) Time extension unavailable (already used) |
| `lcc.enforcement_duplicate` | — | Internal: duplicate enforcement command (idempotent no-op, logged) |

## 7. API endpoints
### 7.1 V1 baseline — `lcc` (authoritative: `contracts/api/lcc.md`)

| Method + path | Auth | Permission | Idempotency | V1 errors |
|---|---|---|---|---|
| `GET /v1/trader/accounts` | Trader — TD-03 | `self` — own accounts (AUTH-13 model; no registry key) | n/a | standard |
| `GET /v1/trader/accounts/{account_id}` | Trader (owner) — TD-03 | `self` — own account | n/a | `account.not_found` |
| `GET /v1/admin/accounts` | Staff — ADM-05 | `account.read` # AUTH-13, key derived from ADM-05 | n/a | standard |
| `POST /v1/admin/accounts/{account_id}/suspend` | Tenant Admin (V1.1) — LCC-11 | `account.suspend` # LCC-11 | required | `account.not_found`, `account.not_active` |
| `POST /v1/admin/accounts/{account_id}/resume` | Tenant Admin (V1.1) — LCC-11 | `account.suspend` (resume is the paired action) # LCC-11 | required | `account.not_suspended` |

Scope, request/response shapes, and per-endpoint notes: `contracts/api/lcc.md` (field values in the research are owner TODOs until contract freeze; canonical JSON is fixed at freeze, per the docs/99 §12 rules).

### 7.2 Extended (post-V1) surface — provisional

> Not in the V1 execution sheet. Design-level; paths beyond the V1 baseline are provisional until the URL-plan decision (`contracts/api/gw.md`, open question). Shown for platform completeness (V2/V3 phases, docs/99).

Trader (TD): `GET /v1/accounts` (own, incl. progress), `GET /v1/accounts/{id}`,
`GET /v1/accounts/{id}/history`, `GET /v1/accounts/{id}/credentials` (reveal,
audited), `POST /v1/accounts/{id}/pause` (V2 self-serve if tenant allows),
`GET /v1/accounts/{id}/statement` (DOC).

Staff (ADM): `GET /v1/admin/accounts?state=&phase=&q=`,
`POST /v1/admin/accounts/{id}/pause | /resume` (LCC-11, V1-Plus),
`POST /v1/admin/accounts/{id}/suspend | /reinstate` (V2 risk queue),
`POST /v1/admin/accounts/{id}/extend` (V2 LCC-14),
`POST /v1/admin/accounts/{id}/override-transition` (V2 LCC-12: manual, reason
required, 2FA, critical audit — the escape hatch; transition table validates it).

Internal: `POST /internal/v1/accounts/{id}/provision` (CHK → LCC on order.paid),
command endpoints for BRG (LCC → BRG; BRG → LCC `broker.created/failed`).
## 8. Schema (key shapes)

```jsonc
// GET /v1/accounts/{id} (trader view)
{ "data": { "id": "01J9ACC...", "kind": "challenge", "phase": 1, "state": "active",
    "program": { "name": "FunderBlu 100k", "size_cents": 10000000, "currency": "USD" },
    "broker": { "platform": "mt5", "server": "MetaApi-Demo-1", "account_number": "50001234" },
    "progress": { "profit_target_cents": 800000, "profit_cents": 412000,
                  "daily_loss_limit_cents": 500000, "daily_loss_used_cents": 90000,
                  "max_loss_limit_cents": 1000000, "max_loss_used_cents": 120000,
                  "min_trading_days": 5, "trading_days": 3, "time_left_days": 27 },
    "balances": { "equity_cents": 10412000, "balance_cents": 10412000,
                  "as_of": 1758278400000 },
    "credentials": { "trading": { "revealed": false, "last_reset": null },
                     "investor": { "revealed": false } },
    "history": [ { "to": "active", "at": 1758192000000, "by": "system" } ] } }
```

## 9. Database design

```sql
CREATE TABLE accounts (
  id                  ULID PRIMARY KEY,
  tenant_id           ULID NOT NULL REFERENCES tenants(id),
  identity_id         ULID NOT NULL REFERENCES identities(id),   -- the trader
  kind                TEXT NOT NULL CHECK (kind IN ('challenge','funded')),
  state               TEXT NOT NULL DEFAULT 'pending_payment',
  state_version       BIGINT NOT NULL DEFAULT 0,      -- optimistic lock
  phase               SMALLINT NOT NULL DEFAULT 1,
  phase_history       JSONB NOT NULL DEFAULT '[]',    -- V2 lineage
  program_id          ULID NOT NULL,                  -- challenge template (CHK/LCC catalog)
  program_name        TEXT NOT NULL,
  size_cents          BIGINT NOT NULL,
  currency            CHAR(3) NOT NULL DEFAULT 'USD',
  order_id            ULID UNIQUE,                    -- CHK order
  terms_snapshot      JSONB NOT NULL,                 -- frozen at purchase
  funded_terms_snapshot JSONB,                        -- frozen at funding
  broker_account_id   ULID,                           -- BRG.broker_accounts id (1:1)
  broker_status       TEXT,                           -- last broker-side state (sync)
  paused_at           TIMESTAMPTZ, resumed_at TIMESTAMPTZ,
  trading_time_left_s BIGINT,                         -- clock (§3.3)
  started_at          TIMESTAMPTZ,
  expires_at          TIMESTAMPTZ,
  failed_reason       TEXT,                           -- 'breach:{rule}' | 'expired'
  failed_at           TIMESTAMPTZ,
  closed_at           TIMESTAMPTZ, archived_at TIMESTAMPTZ,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_accounts_tenant_state ON accounts(tenant_id, state);
CREATE INDEX idx_accounts_identity ON accounts(tenant_id, identity_id, state);
CREATE INDEX idx_accounts_expires ON accounts(expires_at) WHERE state IN ('active','funded');

CREATE TABLE account_state_history (
  id            ULID PRIMARY KEY,
  account_id    ULID NOT NULL REFERENCES accounts(id),
  tenant_id     ULID NOT NULL,
  from_state    TEXT, to_state TEXT NOT NULL,
  event         TEXT NOT NULL,
  actor_kind    TEXT NOT NULL, actor_id ULID,
  detail        JSONB,                               -- e.g. breach rule, reason
  correlation_id ULID,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_acchist_account ON account_state_history(account_id, created_at);
-- (append-only; app role INSERT-only like audit)

CREATE TABLE account_commands (              -- LCC → BRG enforcement/provision commands
  id            ULID PRIMARY KEY,
  account_id    ULID NOT NULL,
  tenant_id     ULID NOT NULL,
  type          TEXT NOT NULL,   -- provision_account | disable_trading | close_positions
                                     -- | enable_trading | archive_broker_account
  idempotency_key TEXT NOT NULL UNIQUE,
  payload       JSONB NOT NULL,
  status        TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','executed','failed','dead')),
  attempts      INT NOT NULL DEFAULT 0,
  result        JSONB,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(), executed_at TIMESTAMPTZ
);
CREATE INDEX idx_acmcmd_pending ON account_commands(status, created_at) WHERE status IN ('pending','failed');
```

## 10. Security & compliance

- **Credential handling:** trading/investor passwords are field-encrypted (AUTH
  §10.2 envelope), stored once (BRG-06), revealed only behind an authenticated
  sensitive-read (AUD-23) with step-up for staff; never logged, never in events
  (events carry `broker_account_id` only).
- **Breach evidence (LCC-38 V2 hash chain):** the breach transition stores a
  pointer to the EVL evidence snapshot (verdict input: tick data, rule state) —
  the "why did my account fail" answer is reproducible from stored data; V2 adds
  the hash chain for tamper evidence (feeds TD-25 breach report + dispute
  reversal LCC-40).
- **Manual overrides** are the highest-risk surface in LCC: 2FA + reason +
  critical-tier audit + CON visibility + (V2) tenant-level enable/disable flag.
- **GDPR:** account closure keeps financial history (ledger references) but
  anonymizes identity on deletion per AUTH §10.4; credentials are destroyed at
  broker archive (BRG-35) — the last place the trader's trading password exists.
- **Compliance:** the state history + audit mirror is the regulator-grade answer
  to "what happened to account X" (MIG cutover evidence uses it).

## 11. Scalability considerations

- Transition throughput: purchases ~200/day + verdict transitions ~1k/day (V1) →
  trivial; the hot path is the **verdict → transition → command** chain, budgeted
  < 100 ms end-to-end (same machine, one PG tx + one command insert).
- Accounts table grows ~1 account/month/trader → ~100k rows at V2 scale:
  `tenant_id, state` index handles all queue views; terminal states are
  partitionable by year if needed (V2).
- Sync snapshots (BRG) are the high-volume tables, not LCC — LCC stores
  **point-in-time** balances only in events/history (LCC-18/42 snapshot policy:
  daily equity point per account in ANA read model; raw ticks never in LCC).
- Rollover job: one transaction per account group per server midnight; at 10k
  accounts → ~10k small updates, batched 200/tx, off-peak (< 30 s total).

## 12. Open-source solutions

| Option | Verdict |
|---|---|
| XState (FSM library) | **Rejected for server FSM**: our machine is the 11 binding V1 states of §3.1 (names like `pending_payment`/`provisioning`/`funding_pending` in code are row-level statuses, not machine states), a validated Go table beats a JS library dependency; XState stays useful for TD's client-side view rendering |
| Temporal (workflow) | Rejected V1 (ops weight); the command table + worker retry is the pragmatic equivalent; revisit if provisioning steps grow |
| Statemachine Python / go-state | Not needed — 50 lines of Go + tests is the library |
| Everything else (IAM, workflow, etc. in the research's OSS list) | Covered by their module docs (AUTH/EVT/BRG) |

## 13. Technology stack

Go domain package in `api`; rollover/monitor jobs in `workers`; Postgres
(transitions, history, commands); Redis only for the command worker's dedupe set;
NOT/DOC/EVT/BRG as described; Sentry on transition conflicts.

## 14. Integration — internal modules (glue)

| Module | How |
|---|---|
| **CHK** | `order.paid` → `account.purchased` → LCC creates row (LCC-05); `order.expired` → cancel; activation fee orders (V2 LCC-08) |
| **BRG** | LCC issues commands (`account_commands`); BRG reports `broker.created/failed` + sync snapshots; LCC-33 broker reconciliation (V2) compares LCC state vs broker state nightly |
| **EVL** | EVL consumes `account.activated/day_rolled/sync` → verdicts → LCC transitions; LCC never evaluates rules itself |
| **PAY** | eligibility reads `state == funded` + KYC gate + no open risk case (PRD default); `account.breached` blocks in-flight payouts |
| **KYC** | `kyc.approved` unblocks `funding_pending → funded` (KYC-07 gate) |
| **DOC** | phase certificates on `phase_completed`, funded cert on `account.funded`, breach report on `breached` (TD-25) |
| **NOT** | all lifecycle events → template emails (credentials, breach, funding, expiry warnings V2) |
| **ANA** | state history + events → funnel KPIs, equity curves (ANA-01 read model) |
| **MIG** | cutover imports FunderBlu accounts into correct states (LCC-22) with state history seeded from TTS data + opening ledger entries (LED-26) |
| **TD** | renders the aggregate; polling refresh (TD-18) hits `GET /v1/accounts` (SSE in V2) |
| **ADM** | account list (ADM-05 V1), pause/resume (LCC-11), queues |

## 15. Integration — external tools

MetaApi (via BRG — account create/config/disable/close), Postmark (via NOT),
R2 (certificate/statement PDFs via DOC), Sentry. No direct provider SDKs in LCC.

## 16. Implementation blueprint

| Step | Owner | Est | Depends | Exit criteria |
|---|---|---|---|---|
| 1. Schemas (accounts, history, commands) + transition table + versioned `Transition()` | BE-1 | 3 d | OPS, AUTH, TEN | unit: every illegal transition rejected; legal path green |
| 2. Purchase path: CHK order.paid → account row → provisioning command | BE-1 | 2 d | 1, CHK-08 | staging purchase creates account in `provisioning` |
| 3. Broker callback path: broker.created → active + terms freeze + events + creds | BE-1 | 2 d | 2, BRG-05 | end-to-end on staging broker sandbox: purchase → active with credentials |
| 4. Verdict path: EVL breach → failed + enforcement command + evidence + NOT/DOC/AUD | BE-1 | 3 d | 3, EVL core | induced breach: account fails once (redelivered event = no-op), positions closed, email sent |
| 5. Phase/funding path: target_hit → phase_complete → funding_pending → funded (KYC gate) | BE-1 | 3 d | 4, KYC-06/07 | full happy path on sandbox: pass phase 1 → funded |
| 6. Pause/resume + clock (trading_time_left) + rollover job + day_rolled | BE-1 | 2.5 d | 5 | pause freezes clock across broker-midnight rollover |
| 7. Commands worker + LCC-27 orphan-position monitor + LCC-41/43 idempotency tests | BE-2 | 2.5 d | 3, 4 | chaos: duplicate commands/verdicts → single effect; orphan scan finds & fixes injected orphan |
| 8. Trader + admin endpoints (incl. credentials reveal with audit) + TD read integration | BE-2 + FE-01 | 3 d | 2–7 | TD shows live account with progress + reveal flow audited |
| 9. MIG import path (states + history seed) for FunderBlu cutover | BE-1 | 3 d | 7, MIG plan | dry-run import of 50 real TTS accounts into staging with correct states |
| 10. V2: optimistic-concurrency formalization, manual overrides, extensions, transfers/merges, archive/retention, instant funding, labels, export | BE-1 + BE-2 | 2 wks | 9 | — |

**Risks:** transition-table drift between code and docs (mitigation: table is
generated into `contracts/events/account-transitions.yaml` by a unit test — the
contract IS the code); command worker backlog during broker outage (mitigation:
backoff + alert + LCC-27 safety net); clock bugs (mitigation: property tests on
pause/rollover combinations).

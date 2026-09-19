# 09 — EVL: Evaluation & Rule Engine

> Covers PRD module **EVL** (54 requirements). The engine that answers, on every
> sync tick, **is this account still within its rules — and if not (or if it just
> hit a target), what exactly happened and why?** It is the module a trader's
> livelihood is decided by, so its outputs must be *deterministic, exact, and
> defensible in a dispute* (EVL-16, EVL-29, EVL-53 are about exactly that).

## 1. Purpose & scope

EVL owns:
1. **Rule packs** — tenant/program rule sets as **versioned data** (not code):
   drawdowns, targets, time, instruments, (V2) conduct rules.
2. **The evaluation function** — a pure function:
   `evaluate(EvalState, RuleSet, Tick) → Verdict` (EVL-04), property-tested.
3. **Evaluation state** — per-account counters (daily start equity, high-water
   marks, trading days, per-day P&L), versioned in PG.
4. **Verdicts & decisions** — `ok | breach | target_hit`, with an explicit
   **decision priority matrix** (EVL-44) when several fire on one tick.

Out of scope: real-time *fraud/anti-gaming* detection (that is RSK, V2), pre-trade
blocking (Alpha One has no order path — enforcement is post-trade via LCC/BRG),
and analytics (ANA).

Requirement coverage: `EVL-01,02,04,05,06,07,08,16,17,19,20,29,34,35,36,44,46,47,48,49,50,51,52,53,54` (V1.0/V1.1: 20,36,51 are V1.1) +
`03,09,10,11,12,13,14,15,18,21,22,23,26,27,28,30,31,32,33,37,38,39,40,41,42,43,45` (V2.0) +
`24,25` (V3.0: custom DSL / multi-asset).

## 2. Architecture

```
 bridge.tick (event, per account)
        │
        ▼
 workers: evaluation-trigger consumer  (per-account serial lane)
        │  1. load EvalState (PG, row lock by account id) + RuleSet (versioned)
        │  2. HTTP → engine (Rust): /evaluate
        │       ┌────────────────────────────────────────────────────┐
        │       │  EVALUATE (pure, deterministic)                    │
        │       │   metrics: recompute from tick (registry §3.3)     │
        │       │   rules:  run rule functions in pack order         │
        │       │   matrix: EVL-44 priority resolves multi-fires     │
        │       │   → Verdict {status, rule_id?, evidence}           │
        │       └────────────────────────────────────────────────────┘
        │  3. if verdict ≠ ok:
        │       PG: update EvalState (new version) + INSERT verdict
        │       outbox: evaluation.verdict → LCC transition (+ NOT/DOC/AUD)
        │  4. else: update EvalState counters (equity high-water, dailies)
```

**Stateless engine (ADR-11):** the Rust service holds no state; everything it
needs arrives in the request (EvalState JSON + RuleSet JSON + Tick JSON). This
makes it trivially testable, horizontally scalable, and re-runnable —
**re-running history is a feature**: any past verdict can be recomputed from
stored (state, rules, tick) — the dispute answer (EVL-16/29/49: "one defensible
answer").

## 3. System design

### 3.1 Rule packs (data, versioned — EVL-02/34)

```yaml
# rule pack: tenant funderblu / program "FB-100K" / version 3
id: rp_01J9...
version: 3
effective_from: 2026-09-01T00:00:00Z        # applies to accounts created after
rules:
  - id: max_daily_loss
    kind: daily_loss
    basis: equity                     # equity | balance
    unit: percent                     # percent | absolute
    value: 5.00                       # % of day-start equity
    day_start: broker_rollover        # ADR-12: broker server midnight
    tolerance_cents: 1                # EVL-53: comparison tolerance
  - id: max_total_loss
    kind: max_loss
    mode: static                      # static | trailing (V2) | balance_trailing (V2)
    unit: percent
    value: 10.00
    reference: initial_balance        # static: vs initial; trailing: vs high-water (EVL-29)
  - id: profit_target
    kind: target
    unit: percent
    value: 8.00
    min_trading_days: 5               # phase pass gate (EVL-19)
  - id: time_limit
    kind: max_calendar_days
    value: 30
  - id: instruments
    kind: restricted_symbols
    symbols: [XAUUSD]                 # V2: allowed-list mode
  # V2 additions: min_trading_days, consistency, weekend_holding, news,
  # lot limits, stop-loss-required, max open positions/lots, trading hours...
meta: { created_by: ..., change_reason: "tighten daily to 5%" }
```

Rules: **account binds the pack version at purchase** (terms snapshot, LCC-20) —
pack edits create a new version; live accounts keep their version (EVL-34
"migration for existing accounts" = optional tenant action to re-bind a new
version with an effective date — audited, never silent). The ADM builder
(EVL-01) is a constrained form (no free text — the form is the DSL surface in
V1/V2; V3 EVL-24 opens a JSON/YAML DSL for advanced tenants).

### 3.2 Evaluation state (per account, PG row)

```
evaluation_state:
  account_id (PK) · rule_pack_id · rule_pack_version
  initial_balance_cents
  day_key (broker date of current period) · day_start_equity_cents
  daily_loss_max_cents            # max intraday drawdown seen today
  high_water_equity_cents         # EVL-29: all-time max (static ref + trailing source)
  max_total_loss_used_cents
  profit_cents                    # vs initial (realized, at tick equity)
  trading_days · calendar_days · started_at
  daily_pnls JSONB                # [{day, pnl_cents, equity_end_cents}]
  target_reached_at · breach_rule_id · breach_at
  version (optimistic)
```

Updates happen **only** in the evaluation consumer (single writer per account;
the per-account lane in 04 §3.5 guarantees serialization).

### 3.3 Metric registry (EVL-46) — the only place metric math lives

| Metric | Formula (all integers, cents) |
|---|---|
| `equity_cents` | broker-reported equity (MetaApi already in account currency) — **never recomputed**; broker is truth |
| `floating_pnl_cents` | Σ over positions: side × (current−open) × lots × contract_size (for display; breach math uses broker equity) |
| `realized_pnl_cents` | Σ closed deals (profit+swap+commission) since initial — from `broker_deals` |
| `daily_pnl_cents` | equity_now − day_start_equity_cents (equity basis) |
| `daily_loss_cents` | max(0, day_start_equity_cents − equity_now) |
| `max_total_loss_used_cents` | max(0, reference_cents − equity_now) (static ref = initial) |
| `profit_cents` | equity_now − initial_balance_cents |

**Precision & rounding (EVL-53, binding):** money = integer cents end-to-end in
EVL (broker values converted once at the BRG normalizer: `Decimal × 100,
ROUND_HALF_UP`); percentages computed as `cents × 10_000 / base_cents` (basis
points, integer) — no floats anywhere in verdict math. Tolerance: a rule fires at
`value_cents ≥ limit_cents + tolerance_cents` (tolerance default 1¢, per-rule
configurable) to absorb broker tick rounding (EVL-30 V2 formalizes buffers).
The **metric registry** is a code table (metric → formula + unit + source),
documented in `contracts/events/metrics.md` — a single source so ANA, TD, EVL
and disputes all use identical definitions.

### 3.4 Verdicts & decision priority matrix (EVL-44/17/19)

When one tick can fire multiple rules, the matrix resolves **deterministically**:

| Priority | Verdict | Action | Notes |
|---|---|---|---|
| 1 | `breach` (any loss or expiry rule) | fail account; `breach_rule_id` = **highest-priority rule fired**: max_total_loss > max_daily_loss > time_limit > (V2 conduct rules) | one breach, ever (LCC-43); evidence = full tick + state snapshot |
| 2 | `target_hit` | phase pass gate: requires `trading_days ≥ min_trading_days` (EVL-19): met → `target_hit`; not met → **`target_hit_pending`** (state flag; pass fires on the first tick after the Nth trading day with profit still ≥ target) | if a loss rule also fires same tick → priority 1 wins (breach beats pass); `target_hit_pending` may be recorded in `evaluations.status` for observability but is never emitted as `evaluation.verdict` — the emitted pass event is `target_hit` on the days-met tick |
| 3 | `ok` | update counters | — |

Edge semantics (pinned by the test-vector suite, EVL-54):
- equity exactly at the limit → fires (with tolerance).
- **Time-limit expiry (D30):** `time_limit` (max_calendar_days) is a breach
  rule — when the rollover tick observes `calendar_days ≥ max_calendar_days`,
  the verdict is `breach` with `rule_id=time_limit` (same evidence, LCC-43
  idempotency and critical audit as any breach; `failed_reason=
  'breach:time_limit'`). `account.expired` stays the NOT/ANA mirror event,
  not a separate enforcement path.
- target reached, then equity falls below target **before** min days → not
  pending (only a tick ≥ target sets the flag; once set it stays set).
- rollover while `target_hit_pending` and days now met → pass on rollover tick.
- **Fast risk guard (EVL-51, V1-Plus):** an independent, cheaper check in the
  same consumer: if `equity < high_water × (1 − max_total_pct) − buffer` OR
  `equity < initial × (1 − max_total_pct) − buffer` with buffer = 0.5% of
  account size → emit `evaluation.risk_guard` (ADM page) **before** the formal
  breach (early warning for ops to intervene; does not change the verdict).
- **Emergency stop (EVL-51b):** CON can raise `evaluation.emergency` per
  account/tenant → consumer skips normal eval and forces `breach(emergency)`
  path (documented disaster tool, critical audit).

### 3.5 Observed vs evaluated (EVL-49/50)

Two records, never conflated:
- **Observed** (`bridge.tick` in `events`): what the broker reported (raw
  normalization). Immutable, append-only.
- **Evaluated** (`evaluation.verdict` rows + `evaluations` table): what the
  engine decided *about* an observed tick, **with the rule pack version and
  input snapshot** (`input_hash = sha256(state||rules||tick)`).

The **rule trigger matrix** (EVL-50) = documented mapping table
(observation → which rules can fire → which verdict): enforced as a lint —
every rule declares its trigger events (`tick`, `day_rolled`, `manual`); the
contract test renders the matrix from code (same pattern as LCC transitions).

### 3.6 Triggers (EVL-05)

| Trigger | Source | What runs |
|---|---|---|
| `tick` | `bridge.tick` (per account, 60 s cadence) | full evaluate (SUSPENDED/terminal accounts are skipped — WARN, no state change; D31) |
| `day_rolled` | LCC `account.day_rolled` (broker midnight per server) | daily reset: push `daily_pnls`, `day_start_equity = equity`, `trading_days++` (if any trade that day), `calendar_days++`; then re-evaluate on the post-rollover tick (SUSPENDED accounts get no rollover event — clocks frozen, docs/07 §3.3; D31) |
| `manual` | ADM "run evaluation now" (EVL-36: 2FA, audited; used after data repairs) | full evaluate on latest tick |
| `backfill` (V2 EVL-33) | CON batch tool | re-evaluate a tick range (uses stored observed ticks; writes corrected verdicts only if the fix changes state — with full before/after audit) |

### 3.7 Overrides (EVL-20, V1-Plus)

Tenant staff (registry roles firm:owner/admin/risk; step-up `mfa_verified_at`
within 5 min; a risk override > $500k requires a firm:owner approval flag — the
`account.manual_override` registry row; reason; critical audit) can **clear a false positive**:
e.g. broker-reported glitch tick caused a breach. Mechanism: NOT deleting the
verdict — writing `evaluation.override {clears: verdict_id, reason, by}` which
transitions LCC back (`failed → active`, V1 supports breach-only reversals;
trading re-enabled via BRG). The original verdict + evidence remain visible
("one defensible answer" = the override is itself on the record). The LCC
machine's two guarded reversal edges — `BREACH_DETECTED → ACTIVE` and
`FAILED → ACTIVE` — exist **only** for this flow (tenth pass D29, docs/50): the
transition validates the override record; closed positions stay closed; BRG
re-enables trading.

## 4. Events (topic `evaluation`)

### 4.1 V1 baseline events — authoritative (tenth pass D28)

From `contracts/events/catalog.md`. Envelope EVT-03 (`id`, `type`, `version`,
`tenant_id`, `occurred_at`, `correlation_id`, `payload`); schemas in
`contracts/events/payloads/`. `bridge.tick` (the observed input, topic
`bridge`) is cataloged from docs/08 §4.1 in the same decision.

| Event | Producer (V1) | V1 consumers |
|---|---|---|
| `evaluation.verdict` | EVL (every non-ok verdict) | LCC (transitions; dedupe on `(account_id, verdict_id)`, LCC-43), NOT-01, DOC-04 (breach report TD-25), AUD (critical on breach), RSK (V2 case open) |
| `evaluation.daily_reset` | EVL (rollover) | ANA (daily P&L points), AUD (standard) |

### 4.2 Extended (post-V1) event model — design-level

| Event | When | Consumers |
|---|---|---|
| `evaluation.risk_guard` (V1-Plus) | buffer breach | ADM (page), AUD |
| `evaluation.override` (V1-Plus) | manual clear | LCC, NOT, AUD (critical) |
| `evaluation.manual_run` (V1-Plus) | ADM trigger | AUD |
| `evaluation.emergency` (V1-Plus) | CON stop | LCC, AUD (critical), NOT |
| `evaluation.recomputed` (V2) | backfill changed history | AUD (critical), CON |

## 5. Lifecycles

- **Rule pack:** `draft (ADM) → active (version N, effective_from) →
  superseded (by N+1; retained forever)`. Re-bind to accounts = explicit tenant
  action (EVL-34) — never automatic.
- **Evaluation state:** created on `account.activated`; frozen (read-only) on
  terminal LCC states; preserved through archive (dispute support).
- **Verdict:** `recorded → (overridden? → superseded_by_override)` — append-only.
- **Trading day:** broker-server-day (per group timezone); the "trading day"
  counter increments when ≥ 1 closed deal that day (registry rule).
- **Phase pass:** `target_hit_pending` (flag) → `target_hit` (event, on
  days-met tick) — a flag lifecycle, fully covered by the priority matrix.

## 6. Error taxonomy
### 6.1 V1 baseline codes — authoritative

From `contracts/errors/taxonomy.md` (the V1 execution sheet; module EVL). These are the exact codes the V1 surfaces return; the envelope is GW-18 (`code`, `message`, `correlation_id`).
| Code | HTTP | Meaning | User-facing message |
|---|---|---|---|
| `challenge.not_found` | 404 | Challenge id unknown | "Challenge not found." |
| `challenge.invalid_config` | 400 | Challenge phases/rules/pricing inconsistent | "Please check the challenge configuration." |
| `ruleset.not_found` | 404 | Rule set unknown | "Rule set not found." |
| `ruleset.invalid_rules` | 400 | Rule payload fails validation | "Please check the rule values." |
| `override.action_unknown` | 400 | Manual override action not in pass/fail/reset | "Unknown override action." |
| `override.reason_required` | 400 | Manual override without recorded reason | "A reason is required." |
| `account.not_found` | 404 | Account unknown or not owned by caller | "Account not found." |
| `account.not_active` | 409 | Action invalid from current state | "This action is not available for this account." |
| `account.terminal_state` | 409 | Operation on FAILED/TERMINATED account | "This account is closed." |
| `account.not_suspended` | 409 | Resume on non-suspended account | "This account is not suspended." |


Namespace `EVL` (internal-facing; client errors surface via LCC/ADM codes):
### 6.2 Extended (post-V1) codes — design-level

> Below the V1 baseline (6.1); names in the GW-18 dotted convention. Rows duplicating a V1 baseline code were folded into the baseline table (the merged registry: docs/30).


| Code | Meaning |
|---|---|
| `evl.state_conflict` | Optimistic-lock conflict after retries (per-account writer bug — alerted) |
| `evl.rulepack_invalid` | Pack failed schema/validation on create (ADM, 422 to user) |
| `evl.rulepack_conflict` | Pack contains conflicting rules (e.g. two `max_daily_loss`) — EVL-28 V2 validator; V1: builder prevents |
| `evl.input_mismatch` | `input_hash` of stored re-run ≠ recomputed (data corruption — CRITICAL) |
| `evl.tick_stale` | Tick older than 10 min (sync lag) — evaluation skipped + WARN (stale equity must not drive verdicts; EVL-52 snapshot ordering: verdicts only from ticks newer than the state's last evaluated tick). No verdict row is written; the `gap_flagged` status is reserved for `bridge.sync_gap` verdicts (§3.5) |
| `evl.unknown_rule_kind` | Engine newer/older than pack (versioning bug — deploy gate) |
| `evl.override_invalid` | Override target not overridable (terminal/already overridden) |
| `evl.metric_unavailable` | Required metric missing from tick (e.g. deal data gap) — verdict = `ok-with-gap-flag` + WARN; **never** assume (00 §8 #5) |

## 7. API endpoints
### 7.1 V1 baseline — `evl` (authoritative: `contracts/api/evl.md`)

| Method + path | Auth | Permission | Idempotency | V1 errors |
|---|---|---|---|---|
| `POST /v1/admin/challenges` | Tenant Admin — EVL-01 | `challenge.write` # AUTH-13, key derived from EVL-01 | required | `challenge.invalid_config` |
| `PATCH /v1/admin/challenges/{challenge_id}` | Tenant Admin — EVL-01 | `challenge.write` # EVL-01 | required | `challenge.not_found` |
| `POST /v1/admin/rule-sets` | Tenant Admin — EVL-02 | `ruleset.write` # derived from EVL-02 versioning | required | `ruleset.invalid_rules` |
| `POST /v1/admin/rule-sets/{rule_set_id}/versions` | Tenant Admin — EVL-02, EVL-34 | `ruleset.write` # EVL-02 | required | `ruleset.not_found` |
| `POST /v1/admin/accounts/{account_id}/evaluate` | tenant staff — firm:owner/admin/risk, step-up (V1.1) — EVL-36 | `account.evaluate` # derived from EVL-36 "force re-evaluation" | required | `account.not_found`, `account.terminal_state` |
| `POST /v1/admin/accounts/{account_id}/override` | tenant staff — firm:owner/admin/risk, step-up; >$500k needs firm:owner approval flag (V1.1) — EVL-20 | `account.manual_override` # EVL-20 | required | `account.not_found`, `override.action_unknown`, `override.reason_required` |

Scope, request/response shapes, and per-endpoint notes: `contracts/api/evl.md` (field values in the research are owner TODOs until contract freeze; canonical JSON is fixed at freeze, per the docs/99 §12 rules).

### 7.2 Extended (post-V1) surface — provisional

> Not in the V1 execution sheet. Design-level; paths beyond the V1 baseline are provisional until the URL-plan decision (`contracts/api/gw.md`, open question). Shown for platform completeness (V2/V3 phases, docs/99).

Engine (internal, Rust service): `POST /internal/v1/evaluate`
`{account_id, state, rule_pack, tick}` → `{verdict, state_after, metrics}`
(stateless request — also used by the re-run tool).

Tenant (ADM): `GET|POST /v1/rule-packs`, `GET /v1/rule-packs/{id}`,
`POST /v1/rule-packs/{id}/activate` (new version), `POST /v1/rule-packs/{id}/rebind`
(EVL-34, reason required), `POST /v1/evaluations/{account_id}/run` (EVL-36, 2FA),
`POST /v1/evaluations/{account_id}/override` (EVL-20, 2FA + reason),
`GET /v1/evaluations/{account_id}/verdicts` (dispute view: verdicts + evidence
+ observed ticks), `GET /v1/evaluations/{account_id}/state`.

Trader (TD): `GET /v1/accounts/{id}/rules` (plain-language rule rendering — TD-27),
`GET /v1/accounts/{id}/breach-report` (TD-25: structured breach explanation from
verdict evidence).
## 8. Schema (key shapes)

```jsonc
// POST /internal/v1/evaluate → 200
{ "data": { "verdict": { "status": "breach", "rule_id": "max_daily_loss",
    "detail": { "limit_cents": 500000, "observed_cents": 512300,
                "tolerance_cents": 1, "day_key": "2026-09-19",
                "equity_cents": 9487700, "day_start_equity_cents": 10000000 } },
  "state_after": { "daily_loss_max_cents": 512300, "breach_rule_id": "max_daily_loss",
                   "breach_at": 1758278400000, "version": 412 },
  "metrics": { "daily_pnl_cents": -512300, "profit_cents": -512300 } } }

// GET /v1/accounts/{id}/breach-report (TD-25)
{ "data": { "account_id": "01J9ACC...", "rule": "Maximum daily loss (5% of day-start equity)",
    "limit": "50,000.00", "observed": "51,230.00", "at_broker_time": "2026-09-19 14:22:31",
    "evidence": { "equity_at": 9487700, "day_start_equity": 10000000,
                  "open_positions": 2, "deals_today": 9 },
    "appeal_hint": "Contact support within 7 days with evidence of a data glitch." } }
```

## 9. Database design

```sql
CREATE TABLE rule_packs (
  id            ULID PRIMARY KEY,
  tenant_id     ULID NOT NULL,
  name          TEXT NOT NULL,
  version       INT NOT NULL,
  status        TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','active','superseded')),
  rules         JSONB NOT NULL,             -- validated vs contracts schema
  effective_from TIMESTAMPTZ,
  change_reason TEXT,
  created_by    ULID,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, name, version)
);

CREATE TABLE evaluations (                     -- "evaluated" record (EVL-49)
  id            ULID PRIMARY KEY,
  account_id    ULID NOT NULL,
  tenant_id     ULID NOT NULL,
  tick_event_id ULID NOT NULL,                -- → events.event_id (observed ref)
  input_hash    TEXT NOT NULL,
  rule_pack_id  ULID NOT NULL, rule_pack_version INT NOT NULL,
  status        TEXT NOT NULL CHECK (status IN ('ok','breach','target_hit','target_hit_pending','gap_flagged')),
  rule_id       TEXT,
  detail        JSONB NOT NULL,               -- evidence: metrics at decision time
  state_version BIGINT NOT NULL,              -- EvalState version used
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_evals_account ON evaluations(account_id, created_at DESC);
CREATE INDEX idx_evals_breach ON evaluations(tenant_id, status, created_at) WHERE status IN ('breach','target_hit');

CREATE TABLE evaluation_state (                -- "evaluated" counters (single writer)
  account_id            ULID PRIMARY KEY,
  tenant_id             ULID NOT NULL,
  rule_pack_id          ULID NOT NULL, rule_pack_version INT NOT NULL,
  initial_balance_cents BIGINT NOT NULL,
  day_key               DATE NOT NULL,
  day_start_equity_cents BIGINT NOT NULL,
  daily_loss_max_cents  BIGINT NOT NULL DEFAULT 0,
  high_water_equity_cents BIGINT NOT NULL,     -- EVL-29
  max_total_loss_used_cents BIGINT NOT NULL DEFAULT 0,
  profit_cents          BIGINT NOT NULL DEFAULT 0,
  trading_days          INT NOT NULL DEFAULT 0,
  calendar_days         INT NOT NULL DEFAULT 0,
  started_at            TIMESTAMPTZ NOT NULL,
  daily_pnls            JSONB NOT NULL DEFAULT '[]',
  target_reached_at     TIMESTAMPTZ,
  target_hit_pending    BOOLEAN NOT NULL DEFAULT false,
  breach_rule_id        TEXT, breach_at TIMESTAMPTZ,
  version               BIGINT NOT NULL DEFAULT 0
);

CREATE TABLE evaluation_overrides (
  id            ULID PRIMARY KEY,
  account_id    ULID NOT NULL,
  tenant_id     ULID NOT NULL,
  verdict_id    ULID NOT NULL REFERENCES evaluations(id),
  kind          TEXT NOT NULL CHECK (kind IN ('clear_breach','manual_run','emergency')),
  reason        TEXT NOT NULL,
  actor_id      ULID NOT NULL,
  correlation_id ULID,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

## 10. Security & compliance

- **Dispute-grade determinism (the compliance core):** (state, rules, tick) →
  verdict is a pure function; every verdict stores its inputs' hash; re-run
  tooling proves historical verdicts reproduce (EVL-16/29/49/54). The breach
  report (TD-25) is generated from stored evidence, never re-interpreted.
- **Override control:** owner role + 2FA + reason + critical audit + CON
  visibility; overrides are themselves versioned records (the audit trail of the
  audit trail).
- **Rule change integrity:** packs are immutable once active; the builder
  validates (no two same-kind rules, sensible ranges: daily ≤ total, tolerance ≥ 0);
  activation is a new version (EVL-02) — a tenant can't silently change live
  accounts (re-bind is explicit + audited).
- **No float, no tolerance abuse:** EVL-53 invariants are property tests in CI
  (rounding table is a test fixture, not a runtime constant).
- **Broker time trust:** verdicts carry `broker_time`; platform-clock skew is
  measured (NTP monitor, OPS) — a > 2 s skew alert exists because day boundaries
  depend on it (EVL-47).

## 11. Scalability considerations

- **Latency budget (per tick):** PG state read ~1 ms + engine HTTP ~2 ms +
  state write ~1 ms → p95 < 10 ms; breach-to-enforcement (engine → LCC → BRG
  confirm) p95 < 100 ms target, SLO 1 s (29 §4). At 10 ticks/s this is
  nothing; at 100 ticks/s (V2) the engine scales horizontally (stateless).
- **Per-account serialization** (04 §3.5 lanes) is the correctness mechanism;
  10k accounts / 8 lanes = fine (each tick is independent work).
- **Rule packs** are tiny (KB) — cached in the worker (in-mem, version-keyed),
  invalidated on `rule_pack.activated`.
- **Re-runs/backfills** are batch (V2 EVL-33): 1k ticks/s single-worker,
  off-peak, with progress in CON — never on the live path.
- **Memory:** engine per-request state ~2 KB; 100 req/s = trivial.

## 12. Open-source solutions

| Option | Verdict |
|---|---|
| **Custom Rust engine** (ADR-11; `pf-platform` scaffold exists, property tests green) | **CHOSEN** — the rule semantics are the product's core IP; a DSL VM (OPA/Rego, Drools) buys nothing at 15 rule kinds and costs debuggability |
| OPA / Rego (research: "use OPA for policy") | Rejected for trading math (Turing-tapable, float semantics, slow introspection); **kept for AuthZ** (AUTH) where it's a good fit |
| Nautilus Trader / backtest frameworks | Research-validated as *inspiration* for the tick→metrics→verdict pipeline; not integrated |
| Flink/stream processing | Rejected (ADR-7 class): our tick rate doesn't need CEP |
| TimescaleDB for ticks | Rejected: PG partitions + R2 archive suffice (ANA owns long-term) |

## 13. Technology stack

Rust (axum service `engine`: reqwest-free pure core + serde; `cargo test` +
proptest property suite + fuzz corpus from real MetaApi fixtures), Go consumer in
`workers` (per-account lanes), Postgres (state/evaluations/packs), Redis (pack
cache invalidation pub/sub), Prometheus (verdict latency, gap-flag rate),
Sentry (engine panics = P1: a panic mid-verdict must surface, not drop).

## 14. Integration — internal modules (glue)

| Module | How |
|---|---|
| **BRG** | consumes `bridge.tick` (observed); EVL never calls MetaApi; gap flags (`bridge.sync_gap`) → `gap_flagged` verdicts |
| **LCC** | `evaluation.verdict` → transitions (breach/target/rollover); LCC owns state *transitions*, EVL owns *decisions* — the cleanest split in the system |
| **TEN** | rule packs are tenant-owned; builder in ADM uses tenant limits (`max_custom_rules`) |
| **ADM** | pack builder (EVL-01), re-bind, manual run, override, verdict viewer |
| **NOT/DOC** | breach email + breach report PDF (TD-25) from verdict evidence |
| **AUD** | every verdict (standard), breach/override/emergency (critical) |
| **ANA** | `evaluation.daily_reset` → daily P&L read model; pass/fail funnel KPIs |
| **RSK** (V2) | verdicts feed risk cases; RSK detections feed back as *new verdicts* (kind `conduct`, same matrix priority below loss rules) |
| **MIG** | cutover: FunderBlu's in-flight TTS accounts get `evaluation_state` seeded from TTS exports (day-start equity, high-water, trading days) + a `migration_backfill` event; one full re-eval tick on first sync verifies coherence |

## 15. Integration — external tools

None directly (the engine is deliberately closed: inputs in, verdict out).
Indirectly: MetaApi data via BRG; Sentry; Prometheus/Grafana; (V2) economic
calendar feed for news rules — the provider is a data import into
`trading_calendar` (EVL-47/14), not a live dependency in the verdict path.

## 16. Implementation blueprint

| Step | Owner | Est | Depends | Exit criteria |
|---|---|---|---|---|
| 1. Metric registry + precision module (cents/bps, rounding table) + property tests | BE-1 | 2 d | OPS | rounding property: 10k random ticks → identical results across runs |
| 2. Engine core: state + rule kinds (daily_loss, max_loss static, target, time, symbols) + priority matrix | BE-1 | 5 d | 1 | unit: matrix cases from §3.4 all pass; fuzz 10M ticks no invariant break |
| 3. Schemas (rule_packs, evaluations, evaluation_state, overrides) + validation | BE-1 | 1.5 d | 1 | pack schema rejects conflicting rules |
| 4. Evaluation consumer (per-account lanes) + tick/rollover triggers + verdict → LCC wiring | BE-1 | 3 d | 2, 3, LCC, BRG-3 | sandbox: live sync → daily counter visible in TD; rollover resets correctly |
| 5. ADM rule-pack builder (EVL-01) + versioning/activation + re-bind (EVL-34) | BE-2 + FE-1 | 4 d | 3 | tenant creates v2 pack; live account keeps v1; re-bind with reason works |
| 6. Dispute tooling: verdict viewer + evidence + re-run proof + override flow (EVL-16/20/36) | BE-2 | 3 d | 4 | re-run of a stored verdict reproduces it (hash match shown in UI) |
| 7. Risk guard + emergency stop + tick-staleness guard (EVL-51/52) | BE-1 | 2 d | 4 | injected 12-min-old tick → evaluation skipped + WARN, no verdict row; injected `bridge.sync_gap` → `gap_flagged` verdict; emergency stop fails account end-to-end |
| 8. **Test-vector suite (EVL-54) + regression suite (EVL-35)** as CI gate (fixture packs × fixture tick histories) | BE-1 | 2 d | 2–4 | CI job `evl-vectors` green; a changed rounding constant fails it |
| 9. MIG state seeding for FunderBlu cutover | BE-1 | 2 d | 4, MIG | 20 real in-flight accounts seeded; first live tick coherent (no false breaches) |
| 10. V2: remaining rule kinds (trailing/EOD-trailing/balance-trailing, min days, consistency, weekend, news, lot/position caps, stop-required, trading hours), simulation tool (EVL-22), backfill (EVL-33), conflict validator (EVL-28) | BE-1 | 3 wks | 8–9 | each new kind = vectors + docs + matrix row updated |

**Risks:** rule-semantics disputes with FunderBlu (mitigation: §3.4 edge
semantics are contractual — get Risk Owner sign-off on the vector suite in
Phase 1, it doubles as the rulebook); engine latency regression (mitigation:
latency property test in CI); state drift from manual DB edits (mitigation:
single-writer + `input_hash` re-run check nightly on a sample).

# 64 — EVL state ownership: the stateless engine, re-confirmed (twenty-third pass)

> The twenty-third pass answers two questions that the twenty-second
> (docs/63) made unavoidable. **First: who owns evaluation account state?**
> The binding architecture says a Go `workers` consumer does (docs/63 §4.1's
> topology, docs/04 §3.5 + line 457, docs/09 §3.2). The Rust engine
> (`propfirm-engine`) has, over several rounds of work, grown its own
> tenant-scoped Postgres account store with optimistic concurrency, its own
> idempotency store, its own rule-pack lifecycle, its own service-bearer
> auth, and business endpoints that read and write account state directly.
> Two components now both believe they own account state. This was never
> decided either way — **it drifted**. **Second: what does the corrected
> multi-tenant capacity target (docs/29 §1.1, docs/63 §4.11 — 100,000
> accounts, not 10,000) require of the event bus, the Postgres write path,
> and the engine's scaling story?** Four decisions came out of the pass
> (**D81–D84**, owner picks, 2026-09-25). This document is the binding
> decision record; docs/00/01/04/08/09/29/63 carry the matching normative
> edits (§9 wiring map).

Status: DECIDED — 4 decisions (D81–D84), 7 findings, **1 open blocker** (the `workers` evaluation consumer does not exist yet, F-B1)
Owner: Tech Lead (decision) · BE-2 (`workers`) · BE-1 (bridge) · EVL owner (`propfirm-engine`)
Version: v1
Last updated: 2026-09-25

---

## 1. Scope & method

- **Read (spec):** docs/63 §4.1/§4.4/§4.5/§4.11/§4.13/§4.14, docs/09
  §1/§2/§3.2/§3.8/§11, docs/04 §3.5/§11/§13, docs/01 ADR-6/7/9/11,
  docs/29 §1.1/§1.3/§3.1/§3.4, docs/00 §1/§5/§8, docs/37 D77–D80,
  `contracts/events/payloads/bridge.tick.v1.json`,
  `contracts/api/09-EVL.openapi.yaml`.
- **Read (code):** `propfirm-engine` at `e7ada88` — `src/api/{handlers,routes,dto,auth,idempotency,server}.rs`,
  `src/pure.rs`, `src/persistence/{traits,postgres,memory,rulepack_store}.rs`,
  `src/engine/{decision,evaluator,pipeline,state}.rs`, `src/rules/**`,
  `src/risk/**`, `src/core/tick.rs`, `migrations/*.sql`, `benches/engine.rs`,
  `docs/architecture.md`, `README.md`; and `pf-platform/go/{gw,bridge}` for
  the existing consumer/gateway patterns.
- **Constraints honoured (not reopened):** ADR-6 (transactional outbox),
  ADR-7 (Redis Streams, at-least-once, `consumer_state` idempotency),
  ADR-9 (single Hetzner box + Compose — **narrowed at V2 by docs/63 F12,
  not overturned**), ADR-11 (stateless Rust EVL — **re-confirmed here**),
  BVR-28 (no vendor is the final authority on a breach), docs/00 §8 #1/#2/#4
  (Postgres is the system of record; tenant isolation is a correctness
  property; idempotency everywhere), docs/09 §3.2 (single writer per
  account), docs/09 §3.3 (the metric registry is the only place metric math
  lives), I-03 (recompute from stored inputs).

## 2. Findings

| # | Sev | Finding | Disposition |
|---|---|---|---|
| G1 | **Critical** | **Two components own `evaluation_state`.** `propfirm-engine` has a Postgres-backed `AccountStore` (`src/persistence/postgres.rs`, 1,838 lines; `get_for_tenant`, `put_with_version`, `put_with_version_and_events`, `ingest_trade_fill`, position and trade tables) behind 9 migrations creating its own `accounts`/`positions`/`trades`/`events`/`rule_packs`/`idempotency_entries` schema. docs/09 §3.2 assigns the same state, and the same single-writer guarantee, to the `workers` evaluation consumer. docs/09 §2 says explicitly "the Rust service holds no state; everything it needs arrives in the request (EvalState JSON + RuleSet JSON + Tick JSON)". **The engine's own `POST /internal/v1/evaluate` violates that: it reads the account from its store** (`handlers.rs:158-164`, `s.store.get_for_tenant(...)`) rather than taking state in the request. | **D81:** the engine is pared back to ADR-11's scope; state, ordering, idempotency, retry and DLQ move to `workers`. |
| G2 | **Critical** | **The engine's own OCC is a second, competing concurrency mechanism.** `put_with_version(expected)` returns `Error::StateConflict` on mismatch (P1-8). Optimistic concurrency is the right tool when *several* writers may race. Under docs/04 §3.5's per-entity serial lanes there is exactly one writer per account, so OCC is not needed — and keeping it means a conflict is a **retry loop** where the spec promises a **serialisation guarantee**. At 100k accounts across 10 tenants, retry loops on the hot path are how a burst becomes a stall. | **D81:** the single-writer guarantee becomes structural (one lane owns one account) instead of transactional (OCC detects the violation after the fact). |
| G3 | **Critical** | **A tenant-authored, activated rule pack does not affect the verdict.** `evaluate_internal_impl` builds the pack as `RulePack::synthetic_from_plan(account_id, tenant_id, &acc.plan)` and the rule set as `RuleRegistry::with_default_rules_for_plan(&acc.plan)` (`handlers.rs:167-176`). `rule_pack_store` is referenced **only** by the `/v1/rule-packs*` CRUD handlers (`handlers.rs:556-727`) — never on the evaluation path. In `pure.rs` the supplied `pack` contributes `pack_id`, `pack_version` and `pack.content_hash()` to the recorded verdict and to `input_hash` (`pure.rs:105,125-126,318`), but the rules that actually execute come from `registry`. **So an activated pack changes what the verdict *claims* it was evaluated against, and changes the reproducibility hash, without changing the decision.** That is worse than the pack being ignored: it makes `input_hash` assert a reproducibility that does not hold. | **D81 + §4.2:** rule-pack *storage and lifecycle* move out of the engine to where ADM's editor persists them; *validation* stays in the engine as a stateless endpoint. The parallel-and-disconnected store is **removed, not connected** — connecting it would require deciding pack-vs-plan precedence, which is EVL/ADM's data-model question (docs/09 §3.1), not the engine's. Recorded as a blocker in its own right (F-B1's sibling): until packs drive evaluation, tenant rule configuration is inert. |
| G4 | High | **Idempotency is implemented twice, with different semantics.** The engine has its own `IdempotencyStore` + `idempotency_entries` table (`src/api/idempotency.rs`, 270 lines; `check_and_remember(tenant, endpoint, key, body, response)` returning `Replay`/`Conflict`/`Fresh`/`Error`, keyed per endpoint, caching the *response body*). The platform's mechanism is `(event_id, consumer)` upserted in `consumer_state` (docs/04 §3.5), which caches the *fact of processing*, not a response. These are not the same guarantee, and only the platform one is exercised by the replay/DLQ-retry tooling (`relay dlq retry`, docs/04 §3.5's D47). | **D81:** the engine's idempotency store is removed. Idempotency is `workers`' job, via `consumer_state`, exactly as NOT/LED/AUD do it. |
| G5 | High | **The `Tick` at the API boundary is not the `bridge.tick` envelope.** `src/core/tick.rs` models a per-symbol quote (`symbol`, `quote{bid,ask,ts}`, `last`, `bid_volume`, `ask_volume`). The real event (docs/63 §4.2/§4.4, `contracts/events/payloads/bridge.tick.v1.json`) is an *account-level* record: `equity_cents`, `balance_cents`, `margin_cents`, `free_margin_cents`, `leverage`, `positions[]`, `deals_count`, `last_deal_ticket`, `broker_time`, plus the D79 additions `trigger`, `source`, `stream_seq`, `equity_low_cents`, `equity_high_cents`. Breach math runs on **broker-reported account equity, never recomputed** (docs/09 §3.3, BVR-28) — a bid/ask quote for one symbol cannot express it. | **D81 §4.4:** the request DTO at the boundary becomes the real envelope. The per-symbol `Quote`/`Tick` type is retained **internally** for marking/display logic that is not breach math. |
| G6 | High | **`/evaluate` returns no floor hints**, so the D79 EVL→BRG return path (docs/09 §3.8, docs/63 §4.4) has no producer. The bridge is specified to cache `floor_daily_cents` / `floor_total_cents` / `target_equity_cents` / `floors_version` and to use them to decide *when* to emit a tick — including the uncapped crossing case (invariant I-21). Without hints, every account degrades to the materiality/heartbeat cadence (≤ 60 s), which is the pre-D78 behaviour D78 exists to replace. | **§4.5:** `hints` is added to the response, computed from the metric registry, property-tested against the rule functions. |
| G7 | Medium | **Doc-comment/code mismatch on `InternalEvaluateRequest.rule_pack`.** The comment says "The field is kept optional for backward compatibility with existing callers; if present it is ignored with a warning" (`handlers.rs:845-852`). The code returns a hard **400**: `"rule_pack is no longer accepted; evaluation uses the account's bound plan"` (`handlers.rs:167-171`). | **§4.6:** the 400 is kept (it is the better behaviour — a silently-ignored pack is how G3 stays invisible) and the comment is corrected to match. |
| F-B1 | **Blocker** | **The `workers` evaluation consumer does not exist.** `pf-platform/go/` contains `gw/` and `bridge/` but no `workers/` package and no `evaluation` consumer. docs/04 §13 lists "`workers` consumers" in the stack and docs/63 §4.1's topology routes `bridge.tick` through it, so the spec assumes a component that is not built. Until it exists, D81's "move it to `workers`" has no destination — which is why stripping the engine and building the consumer are **one change, sequenced consumer-first** (§6), not two. | Open. §6's migration order. |

## 3. Why this had to be decided before the scale-up

The drift is survivable at 431 accounts and awkward at 10,000. At the
corrected target — **100,000 accounts across 10 tenants** — it is a
capacity problem as well as a correctness problem, and the two compound:

- **A stateful engine cannot be scaled by adding replicas.** That is the
  entire content of ADR-11's "trivially horizontally scalable". If the
  engine owns `evaluation_state`, then N replicas are N writers on the same
  rows, and the only ways to keep that safe are OCC retries (G2 — which
  convert a serialisation guarantee into a retry loop, precisely when load
  is highest) or engine-side sharding logic (a second, private
  implementation of the lane hashing docs/04 §3.5 already specifies). A
  stateless engine scales by `--scale engine=N` and nothing else. At
  2,500 verdicts/s sustained and 10k/s burst (docs/29 §1.1) that difference
  is the whole capacity plan.
- **Duplicated ordering/idempotency/retry semantics are a tax paid twice,
  forever.** Every fix to retry backoff, DLQ depth, redelivery handling,
  poison-event quarantine or lane rebalancing has to be made and tested in
  two implementations — the platform's shared `workers` pattern and the
  engine's Postgres-backed store. They will drift, because nothing forces
  them to agree. **This review has already found them drifting**: G3 (a
  rule-pack system that is not consulted), G4 (two idempotency semantics),
  G7 (a comment that contradicts its own function), and docs/63 F11
  (generator drift). The white-label scale-up multiplies the number of
  tenants whose money depends on those semantics being right once.
- **Two writers break the guarantee docs/09 §3.2 actually states.**
  "Updates happen **only** in the evaluation consumer (single writer per
  account; the per-account lane in 04 §3.5 guarantees serialization)." With
  the engine also writing, that sentence is false, and no amount of OCC
  makes it true — OCC detects a violation, it does not prevent one. The
  guarantee only exists if the *architecture* has one writer.

## 4. The decisions

### 4.1 D81 — the Rust engine is a stateless compute service; `workers` owns state

**The call.** `propfirm-engine` is pared back to ADR-11's original scope:

```
evaluate(state, rules, tick) → (verdict, new_state, hints)
```

No database connection of its own. No tenant or account CRUD. No
idempotency store. Everything it needs arrives in the request; everything
it produces leaves in the response. **ADR-11 is re-confirmed, dated
2026-09-25, not superseded** — the engine was always supposed to be this,
and the drift is being reversed rather than ratified.

State ownership, per-account and per-tenant ordering, retries and DLQ
handling move to a `workers` evaluation consumer built on **the platform's
existing Go consumer-supervisor pattern** (docs/04 §3.5): per-entity serial
lanes via consistent hashing on `entity_id`, `(event_id, consumer)`
idempotency upserted in `consumer_state`, `max_attempts: 5` with
backoff `1 s × 2^k`, `timeout: 30 s`, `dlq.{consumer}` plus the
`relay dlq list/retry/purge` recovery path (D47). **This is the same
mechanism NOT, LED and AUD already use — not a new one invented for EVL.**
Inventing an EVL-specific consumer is what produced G1–G4.

**Why, explicitly, so this does not get silently re-litigated.** The
argument is not stylistic preference and it is not "Go is better at I/O".
It is three things, in order of weight:

1. **Correctness at scale.** Duplicating ordering, idempotency and retry
   semantics across two implementations is a maintenance *and correctness*
   liability that gets **materially worse** at white-label multi-tenant
   scale, not better. Every semantic fix is made and tested twice; the two
   drift; and at 10 tenants × 10k accounts the drift is not a bug in one
   firm's configuration, it is a divergence in how two components believe
   money-moving state is serialised. §3 above lists four already-found
   instances.
2. **A stateless compute tier makes horizontal scaling trivial.** "Add
   replicas." No sharding logic of its own to get right, no OCC retry
   budget to tune, no per-replica Postgres connection pool to size against
   PgBouncer (ADR-8), no rebalancing to implement. At 100k+ accounts this
   is the difference between a capacity plan and a research project.
3. **One writer per account becomes structural.** docs/09 §3.2's guarantee
   stops being an aspiration enforced by conflict detection and becomes a
   property of the topology: one lane, one tenant's lane set, one account.

**What moves out of `propfirm-engine` and into `workers`:**

| Moves | Currently | Lands as |
|---|---|---|
| The Postgres-backed `AccountStore` — reads/writes of `evaluation_state` | `src/persistence/postgres.rs` (1,838 lines), `src/persistence/traits.rs`, `migrations/2026010100000{1..4}` | `workers` reads `evaluation_state`, calls `/evaluate`, writes the returned `(new_state, verdict, hints)` back — **in that order, one write path, one writer per account** |
| The idempotency store | `src/api/idempotency.rs`, `migrations/20260923180000_create_idempotency_entries.sql` | `consumer_state` `(event_id, consumer)` upsert, docs/04 §3.5 |
| Per-account / per-tenant ordering | implicit in the engine's OCC | `hash(account_id) → lane` within a **tenant-owned lane set** (D82, docs/63 §4.13) |
| Retry / DLQ | engine-local | `max_attempts: 5`, `1 s × 2^k`, `dlq.evaluation`, `relay dlq retry` (D47) |
| The *writes* behind `override` / `manual-run` / `emergency-stop` | `POST /internal/v1/{override,manual-run,emergency-stop}` | `workers` (and LCC for the lifecycle transition). **The *decision* of whether to allow an override stays engine logic; the *write* belongs in `workers`.** `emergency` stays a first-class input to `/evaluate` so the decision-priority matrix (`Emergency` beats `Liquidate`, docs/09 §3.4) still resolves it deterministically and reproducibly |
| Rule-pack **storage and lifecycle** (draft/active/superseded) | `src/persistence/rulepack_store.rs`, `migrations/…_create_rule_packs.sql`, `…_add_rule_pack_artifact_fields.sql`, the `/v1/rule-packs*` endpoints | wherever **ADM's rule-pack editor actually persists them** (docs/17 §3.1, docs/09 §3.1's versioned-data model). This also closes G3 — by **removing** the parallel-and-disconnected system rather than connecting it |
| The append-only event store, positions/trades tables, broker fill ingestion | `src/events/store.rs`, `src/persistence/postgres.rs`'s `ingest_trade_fill`, `migrations/…_create_{positions,trades,events}.sql` | BRG owns `broker_deals`/`broker_positions` (docs/08 §9, docs/63 §4.5's group commit); LED/AUD own the event log (ADR-6). The engine has no business holding a second copy |

**What stays in `propfirm-engine`:**

- **The pure rule/decision math.** `pure::evaluate` and everything under
  `src/rules/` (the 22 evaluators, `registry.rs`, `context.rs`, `params.rs`,
  `traits.rs`), `src/engine/decision.rs` (the priority matrix), `src/risk/`
  (drawdown, exposure, metrics, VaR), `src/config/` (plans, presets,
  `rule_config`), `src/rulepack.rs` (the schema and its validation),
  `src/equity_input.rs` (the `BrokerReported` vs `Estimated` provenance
  guard), `src/liquidation.rs`, `src/override_engine.rs`'s *decision*
  logic, `src/sha256_helper.rs` (the `input_hash`).
- **Rule-pack schema validation** — as a stateless operation on a supplied
  document (§4.2).
- **A narrow HTTP surface that `workers` calls** (§4.3).
- **The proptest/property suite and the golden-replay corpus**, which are
  the reason ADR-11 chose Rust in the first place (docs/09 §12: "the rule
  semantics are the product's core IP").

**Alternatives rejected.**

- *Keep the self-contained engine and delete the `workers` consumer.*
  Rejected: it contradicts docs/04 §3.5, docs/09 §2/§3.2 and docs/63 §4.1,
  all of which are binding; it forfeits `consumer_state`, the DLQ tooling
  and the replay path that already exist and are already exercised by
  NOT/LED/AUD; and it leaves the engine owning a sharding problem at
  exactly the scale where getting sharding wrong is expensive.
- *Write a bespoke Rust consumer for the `evaluation` lane only.*
  Rejected: a **third** ordering/idempotency implementation. It would be
  better engineered than the engine's current one and still diverge from
  `consumer_state`, and it would put the platform's money-loop lane outside
  the tooling (`relay dlq …`, the CON DLQ screen) that ops actually uses.
- *Keep both and reconcile with OCC.* Rejected: that is today's state, and
  G1–G4 are its output. OCC detects a violated invariant; the spec asks for
  an invariant that cannot be violated.
- *Split the difference — engine keeps a read replica.* Rejected: a read
  path in the engine still means the engine's answer depends on something
  other than its request, which is the property ADR-11 and I-03 exist to
  guarantee, and it re-introduces staleness as a verdict input.

### 4.2 Rule packs: validation stays, storage and lifecycle go

The engine keeps a **stateless** `POST /internal/v1/rule-packs/validate`:
give it a candidate pack document, get back schema validation, semantic
checks (threshold coherence, loss-reference consistency with the plan's
`max_loss_reference`, tolerance sanity), and the `content_hash` it would
carry. It persists nothing and enforces no lifecycle.

Storage and the draft → active → superseded lifecycle move to wherever
ADM's rule-pack editor persists them (docs/17 §3.1), against docs/09 §3.1's
versioned-data model, with `rule_pack.activated` on Redis pub/sub as the
cache-invalidation signal the `workers` consumer already expects (docs/09
§11: "cached in the worker (in-mem, version-keyed), invalidated on
`rule_pack.activated`").

**This resolves G3 by removal.** The engine's `RulePackStore` is not
consulted during evaluation and never was; the evaluation path derives its
rules from `acc.plan`. Connecting the two would require deciding whether an
activated pack overrides a plan preset, and how a pack's rule set maps onto
`RuleRegistry::with_default_rules_for_plan` — that is docs/09 §3.1's
data-model question, owned by EVL/ADM, and answering it inside a storage
layer that is about to be deleted is how parallel systems get built. **The
follow-on work is registered, not hidden:** once ADM owns pack persistence,
`workers` must pass the *bound, activated* pack (id + version + document)
into `/evaluate`, and `/evaluate` must build its registry **from that
document** rather than from the account's plan preset. Until then, tenant
rule configuration is inert — see §7's open item O-1, which is the single
most consequential thing this pass found and did not fix.

### 4.3 The engine's HTTP surface after the split (case-by-case, not blanket)

Step-by-step disposition of every route in `src/api/routes.rs`. The test
applied to each: *does serving this endpoint require the engine to hold or
reach state it was not given in the request?* If yes, it moves.

| Route (today) | Disposition | Reasoning |
|---|---|---|
| `GET /health`, `GET /ready` | **Keep**, unauthenticated | Liveness/readiness probes for Compose healthchecks and the D57 external checker. A stateless service still needs them; `/ready` must now assert *no* DB dependency. |
| `POST /internal/v1/evaluate` | **Keep — and change shape** (§4.4, §4.5) | The whole reason the service exists. It must take state in the request (G1) and return `new_state` + `hints` (G6). Service-token auth stays. |
| `POST /internal/v1/rule-packs/validate` | **Add** (§4.2) | Stateless validation of a supplied document. Replaces the CRUD surface's only legitimately engine-side function. |
| `POST /internal/v1/explain` | **Add** (stateless) | Replaces `GET /internal/v1/breach-report/:account_id`. Takes `(state, pack, verdict, evidence)` and returns the structured "why did I fail" explanation with rule-by-rule reasoning (TD-25, EVL-16/29/53). **The rendering of evidence into an explanation is rule math and belongs here; the account lookup does not.** |
| `GET /internal/v1/breach-report/:account_id` | **Move** to `api`/TD | It is a persisted-state read keyed by account id. The engine has no store to read. TD composes `workers`-persisted verdict + evidence with `/internal/v1/explain`. |
| `POST /internal/v1/override` | **Split** | *Decision* (is this override admissible — does it clear a breach-only verdict, is the actor's step-up MFA within 5 min, does a >$500k risk override need the firm:owner flag; docs/09 §3.7) stays expressible as engine logic invoked by `workers`. *Write* (`evaluation.override`, the LCC `failed → active` / `BREACH_DETECTED → ACTIVE` reversal edge, re-enabling trading via BRG) moves to `workers` + LCC. The original verdict and evidence are never deleted — that invariant is unchanged and is easier to hold when the engine cannot write at all. |
| `POST /internal/v1/manual-run` | **Move** entirely | "Force re-evaluation of an account" = read state + evaluate + write. That is precisely the `workers` lane's job. It becomes "enqueue a `resync`-trigger evaluation for this account" on the account's lane, which preserves per-account ordering instead of racing the lane. No engine endpoint is needed; the math it triggers is `/evaluate`. |
| `POST /internal/v1/emergency-stop` | **Split** | *Decision* stays: `Emergency` must keep beating every other verdict including `Liquidate` (docs/09 §3.4's priority matrix, P1-12). It stays expressible because `emergency` is a first-class input to `/evaluate`, so the outcome remains deterministic and reproducible under I-03. *Write* (the account-state transition, the audit record, the LCC transition, the BRG disable command) moves to `workers` + LCC. |
| `POST /v1/evaluate-order` | **Keep, made stateless** — flagged unused in V1 | Pre-trade order evaluation is a pure function of `(state, rules, order)` and is worth keeping for the V3 pre-trade path. But docs/09 §1 is explicit that "Alpha One has no order path — enforcement is post-trade via LCC/BRG", so **this is dead surface in V1** and is kept behind the internal service token, not the tenant-key `/v1` prefix. The current implementation loads the account from the store; that goes. |
| `GET /v1/accounts/:id` | **Remove** | Pure account CRUD serving a self-contained deployment. ADM/TD read accounts through `api`. |
| `POST /v1/rule-packs`, `GET /v1/rule-packs/:id`, `PATCH /v1/rule-packs/:id`, `POST …/activate`, `POST …/supersede` | **Remove** (§4.2) | Storage and lifecycle, which move to ADM. `validate` replaces the only stateless part. |
| Service-bearer auth (`src/api/auth.rs`), `Idempotency-Key` handling | **Keep auth, remove idempotency** | A narrow internal HTTP surface still needs the service token and the constant-time comparison (`subtle`, §A.1). Per-endpoint response-caching idempotency is G4 and goes; `workers` supplies `(event_id, consumer)`. |

**Net surface: 2 unauthenticated probes + 3 stateless internal endpoints
(`/evaluate`, `/rule-packs/validate`, `/explain`) + 1 kept-but-unused
stateless `/evaluate-order`, all behind the service token.** From 14 routes
to 7, and from "a service with a database" to "a function with an HTTP
shape".

### 4.4 D81's wire contract: `bridge.tick` v1 at the boundary (G5)

`/evaluate`'s request DTO becomes the real `bridge.tick` v1 envelope
(`contracts/events/payloads/bridge.tick.v1.json`, docs/63 §4.2/§4.4), not
the per-symbol quote model:

- **Account-level money, integer cents:** `equity_cents` (broker-reported,
  never recomputed — docs/09 §3.3, BVR-28), `balance_cents`,
  `margin_cents`, `free_margin_cents`, `leverage` (string, D34).
- **`positions[]`** as the envelope defines them (`position_id`, `symbol`,
  `side`, `lots`, `open_price`, `current_price`, `sl`, `tp`, `opened_at`,
  `profit_cents`, `swap_cents`, `commission_cents`).
- **`deals_count`, `last_deal_ticket`** (an incremental fetch cursor, never
  a continuity oracle — D33).
- **`broker_time`** — broker-attested (ADR-12), the trading clock for day
  boundaries, never the platform clock.
- **The D79 additive fields:** `trigger` ∈
  `deal|position|guard|material|heartbeat|resync`, `source` ∈
  `stream|poll|resync`, `stream_seq`, `equity_low_cents`,
  `equity_high_cents`.
- **Provenance stays explicit:** `equity_source` maps to `EquityInput::
  BrokerReported` vs `Estimated`, defaulting to the safe option, and
  breach-capable rules still refuse to terminate on an estimate (P1-5).
  A tick whose `source` is `poll` or `resync` is broker-reported; the
  `estimated` path remains for pre-stream bootstrap only.

**`trigger` is evidence, never a rule input** (the schema says so, and
docs/63 §4.4 depends on it): a rule must not behave differently because a
tick arrived on a heartbeat. `equity_low_cents`/`equity_high_cents` are
carried into verdict evidence for disputes ("what did the account touch
between ticks?") and are **not** used for V1 breach or HWM math — whether a
program may trail on the observed intraday high is docs/63 §8 Q6, still
open, still an EVL rule-semantics question.

**The internal per-symbol `Quote`/`Tick` type is retained** for the
marking/display logic that is not breach math (instrument pricing, exposure
concentration in `src/risk/exposure.rs`, the TD live view's inputs). It
stops being the API boundary.

### 4.5 Floor hints (G6, docs/09 §3.8, docs/63 §4.4)

`/evaluate`'s response gains a `hints` object alongside the verdict,
computed from the **post-evaluation** state and the bound rule set:

| Hint | Definition | `null` when |
|---|---|---|
| `floor_daily_cents` | the equity at which the active **equity-basis** daily-loss rule fires — `day_start_equity − limit` | no equity-basis daily-loss rule is bound |
| `floor_total_cents` | the **stricter** of the static and trailing (EVL-29) max-loss floors | no equity-basis max-loss rule is bound |
| `target_equity_cents` | the profit-target equity | no profit-target rule is bound |
| `floors_version` | the `evaluation_state.version` these came from | never — it is the state version the hints were derived from |

**Balance-basis rules need no hint** (docs/09 §3.8): balance moves only on
deals, and deals always emit ticks, so there is nothing for the bridge to
watch for.

**Implementation constraint: this is read-only reuse, not new math.** The
formulas already exist in the metric registry (docs/09 §3.3 — "the only
place metric math lives") inside the daily-drawdown, max-drawdown,
trailing-drawdown and profit-target evaluators. The hint functions invert
the same expressions. They must live in the registry, next to the rule
functions, so there is one place for the math and the two cannot diverge.

**Property test (the acceptance criterion, not a nice-to-have):** for every
equity-basis rule and every generated `(state, pack)`,
- at `equity == floor` the rule **fires**;
- at `equity == floor + 1 cent` it **does not**;
- under the existing per-rule `tolerance_cents()` handling (§3.4's
  tolerance absorbs broker rounding noise at the boundary — so the property
  is stated at the tolerance-adjusted boundary, and the test must generate
  cases on both sides of it);
- and `floor_total_cents` equals `min(static_floor, trailing_floor)`
  whenever both are bound, so "the stricter of" is asserted rather than
  assumed.

**Advisory by construction, and the test must assert it:** the engine never
reads `floor_*` back as an input, so I-03 recompute is unaffected; a wrong
or stale hint changes only *when* a tick is emitted, never *what* is
decided. `workers` persists the hints into `evaluation_state.floor_*` in
the **same transaction** as the state update and publishes
`evl.floors {account_id, version}` on Redis pub/sub (docs/09 §3.8);
`day_rolled` and rule-pack re-binds recompute them.

### 4.6 G7 — the comment and the code now agree

`InternalEvaluateRequest.rule_pack` keeps the hard **400** and the comment
is corrected to say so. The 400 is the better behaviour: a silently ignored
pack is exactly how G3 stayed invisible for several rounds. A caller that
sends a pack is telling us it believes the pack drives the decision, and
that belief must be corrected loudly. Under D81 the field is **removed**
from the request entirely — the bound pack arrives as `rule_pack_ref`
`(id, version)` resolved by `workers`, or as a full document when ADM has
persisted one (§4.2, O-1) — so the mismatch cannot recur.

### 4.7 D82 — per-tenant fairness on the event bus

**Full text, reasoning and rejected alternatives: docs/63 §4.13.** In one
paragraph: all tenants sharing one `topic.bridge` stream makes one
consumer group chew one FIFO, so a tenant generating 80 % of ticks takes
≈ 80 % of consumer capacity; and `workers`' globally-hashed lanes mean a
tenant's accounts share **serial** lanes with other tenants' accounts,
which is head-of-line blocking and is invisible in aggregate throughput.
The decision is **one stream per tenant (`topic.bridge.{tenant_id}`) plus
tenant-owned lane sets**, with lanes `max(10, ceil(weight × total))` per
tenant and a total of `max(128, 10 × tenants)`. Weighted fair queuing on a
*shared* stream was rejected because it is not implementable on Redis
Streams: `XREADGROUP >` delivers in stream-id order, so the consumer never
chooses which tenant's work to take — per-tenant streams are the
*precondition* for any fairness policy. Tenant-tier grouping was rejected
because it re-creates the unfairness inside a tier. The section also fixes
the `MAXLEN ~100000` trim hazard (detection via `evl.stream_trimmed` +
replay-from-PG, prevention via D84's shedding, and an explicit refusal to
raise `MAXLEN` because Redis is never the source of truth).

### 4.8 D83 — Postgres write scaling for `evaluation_state`

**Full text and arithmetic: docs/29 §3.4.** In one paragraph: at the
corrected target the evaluation path is ≈ 11.8k q/s sustained and ≈ 42.9k
q/s burst (≈ 2.6k / ≈ 10.1k commits/s) against a single primary planned at
≈ 10k q/s. **Sustained fits; burst does not** — but burst need not be
served at line rate, only drained inside the staleness window, and a
5-minute burst at 10k ticks/s against a 5k ticks/s write path drains in
exactly **10 minutes = the `evl.tick_stale` threshold**, i.e. **zero
margin**. Decision: partition `evaluation_state` by `tenant_id` (hash, 64
buckets) and `account_snapshots` / `broker_deals` by `(tenant_id, day)`;
`events` by day with `bridge.tick` on a ≤ 7-day hot window plus R2
columnar archive (docs/63 F13); **nothing outside the write path reads the
primary** — ANA, disputes, ADM, RSK and the TD read a replica on box 2
(docs/29 §3.4.3's per-reader table). **Single-primary-with-partitioning is
the V2 plan; horizontal Postgres (Citus, distribution key `tenant_id`) is
staged on a measured trigger** — sustained commits > 6,000/s for 2 weeks,
or `evl_lag_seconds > 300` more than twice a month with the engine tier
demonstrably unsaturated. Citus is not adopted now because the sustained
load does not require it, because D84's shedding ladder removes ≈ 14 % at level 1, ≈ 30 % at level 2 and ≈ 60 % at level 3
of sustained load (zero correctness cost at levels 1–2), because it conflicts with docs/00
§8 #6 (a 1-person DevOps team), and because ADR-6's outbox is a
single-database transaction that would become a distributed one.
Partitioning first is not a dead end: `tenant_id` hash partitioning and a
Citus `tenant_id` distribution key are the same sharding function.

### 4.9 D84 — autoscaling signal and load-shedding

**Full text: docs/63 §4.14.** The honest constraint is that **the
deployment target has no autoscaler** — ADR-9 is Compose on Hetzner and
docs/00 §8 #6 forbids Kubernetes; Compose has `--scale` but no controller.
So the signal is defined for the platform that exists: `evl_lag_seconds
{tenant} = consumer-group lag ÷ measured drain rate`, scraped by Prometheus,
acted on by an **operator** via `docker compose up -d --scale engine=N
--scale workers=M` in V2, by an optional ~200-line Compose-scale actuator
in V2.5 **only if the load test proves the manual loop too slow**, and by
KEDA/HPA in V3 if the platform ever leaves Compose. **Lag in seconds, not
entries**, because it is the quantity comparable to the correctness
backstop. **Engine CPU is deliberately not the signal**: `benches/engine.rs`
measures ≈ 52,600 pure evals/s single-threaded, so at 10k verdict/s the
engine is never the bottleneck — HTTP fan-in and Postgres are, and scaling
on engine CPU would add replicas to an unsaturated tier. Thresholds are
fractions of the 10-minute `tick_stale` window: scale out at 60 s, WARN at
120 s, **PAGE at 300 s**, INCIDENT at 480 s (or on `evl.stream_trimmed`, or
on any funded-account `tick_stale` suppression). Shedding **widens the
bridge conflation window rather than dropping observations** — so
`equity_low/high_cents` still bound the gap (I-22) and nothing
dispute-relevant is lost — reuses **docs/63 §4.7's existing resync priority
list** (guard-band → funded → open positions → the rest) rather than
inventing an ordering, is delivered by `evl.load_shed` pub/sub (the
`evl.floors` pattern), and **never sheds `deal`, `position`, `guard`,
crossing (I-21) or `resync`**. The ladder removes ≈ 14 % at level 1, ≈ 30 % at level 2 and ≈ 60 % at level 3 of sustained
load (docs/63 §4.14's derivation), zero correctness cost at levels 1–2 — and its
ceiling is ≈ 60 %, not 100 %, because funded accounts are half the fleet and the
priority list protects them. **`evl.tick_stale` is explicitly not a
capacity plan**: it is the correctness backstop, and reaching it on funded
accounts is already a docs/29 §4 SLO failure, which is why that condition
is an incident and not a degradation.

## 5. ADR-11's status

**Re-confirmed, dated 2026-09-25, with a pointer to this document.** ADR-11
was not wrong and is not superseded; it was drifted from, and the drift is
reversed. The ADR text in docs/01 §3 now reads, in addition to its original
sentence: *"Re-confirmed 2026-09-25 by D81 (docs/64) after the engine was
found to have grown its own Postgres account store, idempotency store and
rule-pack lifecycle. The engine holds no state and opens no database
connection; `workers` owns `evaluation_state`, ordering, idempotency, retry
and DLQ."*

The three properties ADR-11 claimed, restated against the corrected target:

| ADR-11's claim | True before D81? | True after |
|---|---|---|
| "trivially testable" | **Yes** — `pure::evaluate` + the proptest suite + golden replay are genuinely good, and are the reason Rust was chosen (docs/09 §12) | Yes, unchanged. G6 adds the hint property tests. |
| "horizontally scalable" | **No** — a Postgres-backed `AccountStore` with OCC makes N replicas N competing writers (G2) | **Yes** — `--scale engine=N`, no sharding logic, no retry budget |
| "re-runnable — any past verdict can be recomputed from stored `(state, rules, tick)`" | **Partly** — `input_hash` is computed over a `pack` that did not drive the decision (G3), so the hash asserts a reproducibility that does not hold | Yes, once O-1 lands (the registry must be built from the recorded pack). **Until then the claim is qualified, and this document says so rather than leaving it in the README** |

## 6. Migration order (consumer-first, because F-B1)

D81's "move it to `workers`" has no destination until `workers` exists
(F-B1). Stripping the engine first would leave the platform with **no
evaluation path at all**. So:

1. **Build the `workers` evaluation consumer** (Go, docs/04 §3.5's pattern
   verbatim): consume `bridge.tick` from the per-tenant stream, lane per
   account within a tenant-owned lane set, `consumer_state` idempotency,
   `max_attempts: 5`, `dlq.evaluation`. Read `evaluation_state`, call
   `/evaluate`, write `(new_state, verdict, hints)` back **in that order,
   one write path**. Persist the floor hints in the **same transaction** as
   the state update and publish `evl.floors`.
2. **Change the wire contract** (§4.4) and **add hints** (§4.5) — these can
   proceed alongside step 1, and the engine can serve both the old and the
   new request shape during the overlap so the two repos need not land in
   one atomic commit.
3. **Only then strip the engine** (§4.1's tables, §4.3's dispositions):
   remove the Postgres `AccountStore`, the idempotency store, the account
   CRUD and rule-pack CRUD routes; keep `validate` and add `explain`.
4. **Update `propfirm-engine`'s `README.md` and `docs/architecture.md`** to
   state plainly that it is a stateless compute service consumed by
   `workers`, not a self-contained deployment — so a future contributor
   does not reintroduce the drift this pass reverses. The README currently
   advertises "Optimistic concurrency control", "Tenant isolation …
   `AccountStore::get_for_tenant`" and the `/v1/accounts` + `/v1/rule-packs`
   surface as *features*; those sections are what makes the drift look
   intentional.
5. **Then D82/D83/D84's implementation** (per-tenant streams, partitioning
   + replica, lag metrics + shed ladder), which depend on `workers` owning
   the lane sets and the write path.

Steps 1 and 3 are **one change in review terms** even though they land as
two commits in two repos: merging 3 without 1 removes the evaluation path.

## 7. Open items (registered, not hidden)

| # | Item | Owner | Why it is not closed here |
|---|---|---|---|
| **O-1** | **Activated rule packs still do not drive evaluation.** D81 removes the engine's disconnected `RulePackStore` (G3) but does **not** by itself make tenant-authored packs effective. `workers` must resolve the account's bound `(rule_pack_id, rule_pack_version)`, fetch the document from ADM's store, and `/evaluate` must build its `RuleRegistry` **from that document** rather than from `acc.plan`'s preset. Until that lands, tenant rule configuration is inert and `input_hash` reproducibility remains qualified (§5). | EVL owner + ADM owner | It needs docs/09 §3.1's pack-vs-plan precedence decided first — a data-model question, not a refactor. **This is the single most consequential thing this pass found and did not fix, and it is stated here so it cannot be lost behind a green build.** |
| O-2 | The `workers` consumer does not exist (F-B1) | BE-2 | §6 step 1 |
| O-3 | docs/04 §3.4's 13-month `events` retention needs the `bridge.tick` tier exception recorded normatively (docs/63 F13, §10.2 there) | BE-1 | docs/29 §3.4.2 states the decision; the docs/04/32 edits are mechanical and belong in a wiring pass |
| O-4 | `contracts/api/09-EVL.openapi.yaml` must be regenerated for the §4.3 surface (14 routes → 7, the new `/evaluate` request/response shape, `/rule-packs/validate`, `/explain`) | EVL owner | Contract changes are versioned explicitly (docs/00 §8 #8); doing it inside this decision doc would bypass that |
| O-5 | MetaApi's per-server credit limit: per (`Client-Id`, server) or global? (docs/63 §8 Q8) | BE-1 + Tech Lead | A vendor question. Planned against the pessimistic reading until answered. |
| O-6 | Measured RSS per `bridge-stream` account (docs/63 §8 Q3/Q7) | BE-1 + DevOps | F12's shard count and the second-box requirement follow from it; the ≈ 50-shard figure is an estimate |

## 8. Test hooks

| # | Invariant / check | Asserts | Owner |
|---|---|---|---|
| I-24 | **single writer per account, structurally** | for any account, over any interleaving of redelivered `bridge.tick` events, DLQ retries and `manual-run` enqueues, exactly one `workers` lane issues `evaluation_state` writes — asserted by a concurrency test that fails if any two lanes hold the same `account_id`, and by the absence of any OCC conflict path in the engine | 64 §4.1 / 09 §3.2 / 04 §3.5 |
| I-25 | **the engine holds no state** | the engine binary starts, passes `/ready` and serves `/evaluate` with **no `DATABASE_URL` configured and no reachable Postgres or Redis**; a CI job asserts the crate has no `sqlx` dependency and no `postgres` feature in the default build | 64 §4.1 / 01 ADR-11 |
| I-26 | **hint/rule agreement** (property test) | for every equity-basis rule and generated `(state, pack)`: at `equity == floor` the rule fires; at `floor + 1 cent` it does not; both under the rule's `tolerance_cents()`; and `floor_total_cents == min(static, trailing)` when both are bound | 64 §4.5 / 09 §3.8 |
| I-27 | **hints are advisory** | mutating any `floor_*` value in a persisted state changes **no** verdict for any tick — the engine never reads them back (I-03 preserved) | 64 §4.5 / 63 §4.4 |
| I-28 | **`trigger` is not a rule input** | the same `(state, pack, equity)` produces the same verdict for every value of `trigger` ∈ {deal, position, guard, material, heartbeat, resync} | 64 §4.4 / 63 §4.4 |
| I-29 | **envelope conformance** | every `/evaluate` request the `workers` consumer sends validates against `contracts/events/payloads/bridge.tick.v1.json`'s payload schema; a contract test fails on any field the engine accepts that the schema does not define | 64 §4.4 |
| I-30 | **no shed trigger is ever dropped** (load test LT-6) | under shed levels 1–3, zero `deal`/`position`/`guard`/crossing/`resync` ticks are withheld, and I-22's evidence bound holds across every widened conflation window | 63 §4.14 / 29 §6 |
| I-31 | **per-tenant fairness** (load test LT-4) | with tenant A driven at 10× weight and B–J at their sustained rate, B–J's quote→verdict p95 is unchanged within measurement noise and no `evl.tick_stale` fires outside A | 63 §4.13 / 29 §6 |
| — | **idempotency is `consumer_state`'s** | redelivering any `bridge.tick` produces exactly one state write and exactly one `evaluation.verdict`; the engine has no idempotency table to test | 64 §4.1 / 04 §3.5 |
| — | **reproducibility (I-03), re-asserted post-split** | replaying a stored `(state, pack, tick, server_time)` through `/evaluate` reproduces the recorded verdict **and** `input_hash` — with O-1 open, this is asserted against the plan-derived pack and **must be re-asserted against the bound pack once O-1 lands** | 09 §2 / 64 §5 |

## 9. Wiring map (files touched by this pass)

| File | Change |
|---|---|
| docs/00 | §1 the white-label scale target (binding note); §5 the corrected V2 table |
| docs/01 | **ADR-11 re-confirmed + dated + pointer to this doc (§5)**; §1.1's `engine` row restated as a stateless compute service; ADR-9's single-box clause narrowed at V2 (docs/63 F12) |
| docs/04 | §11 the relay partition count, per-tenant streams, lane count, DLQ per-tenant depth, the new trim-detection row, the `bridge.tick` retention exception |
| docs/08 | §11 every V2 column recomputed at 100k; new cold-resync and tenant-fairness rows |
| docs/09 | §11 the tick rate, the lane count, the write-path row, the memory row; §2's stateless-engine paragraph re-anchored to D81 |
| docs/29 | §1.1/§1.1.1/§1.1.2 the corrected targets; §1.2 the headroom clause; §1.3 the per-resource model; §2 the GW+EVT/BRG/EVL rows; §3.1 the second box as a V2 prerequisite; **new §3.4 (D83)**; §5 the MetaApi cost; §6 the LT-1..LT-8 load test |
| docs/63 | the v1.1 header; F1/F4/F7 corrected, **new F12/F13**; §4.2 per-tenant shard ownership; §4.4 the envelope at 100k; §4.5 the relay target + lane count; §4.7 the resync and fallback arithmetic; **§4.11/§4.11.1/§4.11.2/§4.11.3**; §4.12 four new failure rows; **new §4.13 (D82), §4.14 (D84)**; §5 D81–D84; §6 the load row; §8 Q7/Q8; §10 follow-up 5 |
| **docs/64** | **this document (new)** |
| `scripts/design-questions.json` → docs/37 | **D81–D84** |
| docs/35 | I-24..I-31 |
| `propfirm-engine` README + docs/architecture.md | **pending §6 step 4** — stateless compute service, not a self-contained deployment |
| `contracts/api/09-EVL.openapi.yaml` | **pending O-4** |

## 10. What did **not** change

- EVL is still the only decision-maker, and the bridge still never decides a
  breach (BVR-28, docs/09 §1).
- `evaluate(state, rules, tick)` is still pure; I-03 recompute still holds.
- ADR-6 (transactional outbox), ADR-7 (Redis Streams, at-least-once),
  ADR-12 (the broker attests time), D33 (ordering cursors are ours) and
  D34 (the canonical tick shape) are untouched. D77–D80 are untouched;
  D79's conflation is *reused* by D84's shedding rather than amended.
- The Rust engine's rule math, its 22 evaluators, the decision priority
  matrix, the metric registry, the `EquityInput` provenance guard, the
  proptest suite and the golden-replay corpus are **all kept**. This pass
  removes a database, not a body of work.
- V1's numbers (431 accounts) are unchanged. This is a V2 planning
  correction.
- docs/00 §8's non-negotiables all still hold; #6 ("one Hetzner box") is
  **narrowed at V2** by docs/63 F12, and that narrowing is recorded in
  docs/29 §3.1 rather than left implicit.

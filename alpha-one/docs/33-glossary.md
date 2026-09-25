# 33 — Glossary (the shared language)

> Every term the docs use with a precise meaning, in one place.
> Each entry names the owning doc — the doc is the definition's
> authority; this glossary is the index. New code MUST use these
> terms for identifiers, table names, and event names (docs/32
> §1); a PR that invents a synonym for a glossary term fails
> review.
>
> Requirement coverage: cross-cutting (terminology; no PRD module).

## 1. The business (prop trading)

| Term | Meaning | Owner |
|---|---|---|
| prop firm / tenant | the customer: a firm running challenges on the platform; the unit of data isolation (`tenant_id` everywhere) | 03 |
| trader | the end user: buys challenges, trades, gets paid; always belongs to exactly one tenant per account | 02 |
| challenge | the product a trader buys: a template (profit target, drawdown rules, phases) + an account to trade it on | 09 |
| phase | one step of a challenge (e.g. phase 1 → phase 2 → funded); passing advances, breaching ends | 07 |
| funded / funding | the state after passing all phases: the account trades firm capital and earns payouts | 07 |
| evaluation | the act of checking an account's metrics against its rulepack on each trigger | 09 |
| rulepack | the versioned set of rules bound to an account (version pinned at account creation) | 09 |
| verdict | the evaluation output: pass / breach / continue (+ rule refs + hash) | 09 |
| recompute | re-running `evaluate()` over stored snapshots to reproduce a verdict hash (the audit proof) | 09 |
| drawdown (daily / max / trailing) | loss limits: since day boundary / since start / from the high-water mark | 09 |
| high-water mark (trailing) | the running equity peak the trailing drawdown is measured from (EVL-29) | 09 |
| profit target | the gain that passes a phase | 09 |
| breach | a hard-rule violation: ends the challenge/funded spell, triggers enforcement | 07 |
| enforcement | the broker-side consequence of a breach (close positions, disable trading), executed idempotently via BRG | 07/08 |
| double-enforcement prevention | LCC-41: the same breach decision can never execute twice (idempotency key LCC-43) | 07 |
| confirmation | BRG-11: broker-side proof an enforcement command actually executed (else: the confirm path) | 08 |
| day boundary | the broker-timezone midnight that resets daily drawdown (ADR-12) | 01/09 |

## 2. The money (payouts, ledger, checkout)

| Term | Meaning | Owner |
|---|---|---|
| payout | money owed to a funded trader: request → eligibility → approval → execution → settled | 11 |
| eligibility | the frozen-rule check (profit available, KYC L2, no hold, schedule, …) before a payout is approved | 11 |
| available profit | the computed payable amount (PAY-02); a payout for already-paid profit 422s | 11 |
| approval queue | the staff worklist of pending payouts (manual approval is the V1 default) | 11/17 |
| two-op | two-operator approval: a second staffer confirms a sensitive action (payouts, overrides, legal blocks) | 02/17/21 |
| hold (risk hold) | RSK-11 + PAY-04: an open risk case blocks payouts (never purchases) | 10/11 |
| rail | a payout execution channel (NOWPayments crypto, manual wire in V1) | 11 |
| obligation / settlement | the ledger pair: `obligation` at approval, `settlement` at execution (LED-07/08) | 05 |
| reconciliation | the scheduled job matching our ledger against the provider's evidence (PAY-34, BRG-15, CHK-31) | 11/08/12 |
| ledger | the double-entry book: every money movement posts balanced, immutable (triggers reject UPDATE/DELETE) | 05 |
| chart of accounts | LED-01: the account taxonomy every posting references | 05 |
| posting / reversal | an entry pair / its reason-required correction (never an edit) | 05 |
| order | a purchase intent that became payable: session → intent → capture → `order.paid` → provisioning | 12 |
| checkout | the login-first purchase flow (catalog → session → provider → order) | 12 |
| intent / capture | the provider pair: authorized amount / actually taken amount (mismatch → manual review) | 12 |
| refund / chargeback | post-purchase money-back (CHK-15/35, V2) / rail-initiated reversal; both post to the ledger (LED-05) | 12/05 |
| provider adapter | the interface implementation per PSP/KYC/broker/email vendor (BVR-16, docs/34 §5) | 04/34 |

## 3. Identity, access, compliance

| Term | Meaning | Owner |
|---|---|---|
| 2FA | TOTP second factor: staff in V1 (AUTH-09), traders in V2 (AUTH-10) | 02 |
| scope | a permission string (`resource.action`) checked by the permission engine (AUTH-13) | 02 |
| role | a named scope bundle (custom roles are AUTH-14, V2) | 02 |
| ABAC / RBAC | attribute-based (tenant, ownership, case state) over role-based access control | 02 |
| 404-not-403 | the posture: unauthorized cross-tenant access returns 404 (no existence oracle), never 403 | 04 |
| realm (CON) | the platform console's separate auth realm: tenant credentials can never enter it | 21 |
| session / deny-set | PG-backed sessions + the Redis revocation set (logout/staff-2FA-reset take effect immediately) | 02 |
| KYC L1 / L2 | identity gates: L1 to purchase, L2 to be paid (KYC-07/08) | 13 |
| verified-identity record | KYC-09 (V1.1): the durable proof of a passed verification, checked at first payout | 13 |
| re-verification | KYC-21 (V2): event/expiry-triggered fresh verification | 13 |
| audit (event / log) | the append-only record of who did what; security-sensitive writes are fail-closed (action rolls back if audit fails) | 05 |
| fail-closed | the posture: a failed control blocks the action (never degrades to allow) | 05/28 |
| replay chain | AUD-05 (V2): the hash-linked per-account audit trail verifiable back to genesis | 05 |
| consent | the per-trader, per-purpose marketing permission (CRM decides, NOT enforces) | 20/14 |

## 4. Platform mechanics (events, data, tenancy)

| Term | Meaning | Owner |
|---|---|---|
| outbox / relay / Stream | the event path: PG outbox table → single relay process → Redis Streams → consumers (EVT-01/02) | 04 |
| envelope | EVT-03: `{id, event, event_version, tenant_id, created_at, data}` on every message | 04 |
| consumer (idempotent) | EVT-05: every consumer dedupes on `(event, id)` — delivery is at-least-once | 04 |
| DLQ | the dead-letter queue: poison messages park with alert, never silently drop | 04 |
| webhook (inbound/outbound) | provider→us (signature-verified, EVT-10) / us→tenant-developer (signed, Hook0-retried, EVT-11/13/14/15) | 04/27 |
| idempotency key | the client-supplied key making mutating calls safe to retry (GW-12) | 04 |
| saga | a multi-step cross-service flow with compensations (tenant creation, provisioning) | 03/07 |
| read model (`*_ro`) | a rebuildable, never-authoritative projection for reads/analytics (ANA-01) | 19 |
| `as_of` | the staleness stamp on every read-model row/number (stale shows stale, never silent) | 19 |
| rebuild | regenerating a read model from its source (the correctness proof) | 19 |
| frozen snapshot | the point-in-time data a document/decision renders from (never a live table) | 15 |
| ULID | the 26-char lexicographically-sortable ID (docs/32); internal ULIDs never leak to public APIs (ref indirection) | 32/27 |
| money (`_cents`) | int64 minor units + ISO-4217 currency — never floats (docs/32) | 32 |
| broker tick (`bridge.tick`) | the observed-record event BRG emits per account (equity, balance, margin, positions, broker time) — EVL's only trading input (EVL-49) | 08 |
| stream / stream state | BRG's per-account MetaApi streaming subscription (D78) and its state `subscribing → syncing → live → stale`; only `live` streams emit heartbeat ticks | 08/63 |
| stream gateway (`bridge-stream`) | the Node/TS sidecar hosting MetaApi's SDK; forwards ordered frames to the Go bridge — no money math, no persistence, no decisions (D77, ADR-15) | 63 |
| conflation | folding many broker equity quotes into few `bridge.tick` events by trigger (deal, position, guard, material, heartbeat, resync), keeping the low/high in between (D79) | 63 |
| floor hint | EVL's advisory per-account equity levels (daily floor, total floor, target) that tell the conflator where quotes matter — decide *when* a tick is sent, never *what* is decided | 09 §3.8 |
| guard band | the equity zone just above a floor hint (default 50 bps of initial balance) where every quote becomes an urgent tick (≤ 4/s); a crossing is never rate-capped (I-21) | 63 |
| heartbeat tick | a tick restating current state after 60 s (open positions) / 300 s (flat) with no other trigger — keeps `evl.tick_stale` meaningful | 63 |
| fallback poll | REST polling of accounts whose stream is `stale`, under a MetaApi CPU-credit budget (D78) | 08 §3.3 |
| doorbell (`outbox_doorbell`) | the payload-free Postgres `NOTIFY` that wakes the relay right after an outbox commit — never the transport (D79) | 04 §3.3 |

## 5. The surfaces (apps)

| Term | Meaning | Owner |
|---|---|---|
| TD (trader portal) | the Next.js app traders use (dashboard, purchase, payout, docs) | 16 |
| ADM (tenant admin) | the Next.js app firm staff use (accounts, queues, KYC, exports, settings) | 17 |
| CON (platform console) | the separate-subdomain app FunderBlu/our ops use (tenants, audit review, incidents) | 21 |
| MOB / JRN / EDU / CHT | V2 trader surfaces: React Native app / private journal / academy / community chat | 26 |
| CMS / CMP | V3 tenant surfaces: constrained site builder / competitions engine | 24 |
| SDK / DVP / TRD | V3 developer+trading surfaces: public API+SDKs / developer portal / copy-backtest-paper | 27 |
| template | a versioned notification/document layout (NOT-05, DOC-01) | 14/15 |
| dedupe | NOT-13: the 24-h SETNX that stops double-sends | 14 |
| block (CMS) | the constrained content unit tenants compose sites from (legal blocks are 2FA + version-cited) | 24 |
| scoring (CMP) | the pure, versioned, re-runnable competition ranking function | 24 |

## 6. Trading ecosystem (V3)

| Term | Meaning | Owner |
|---|---|---|
| copy trading | mirroring a leader's fills to followers (opt-in, 2FA, TRD-08 guardrails) | 27-B |
| backtest | replaying a strategy over historical data (reproducible: same inputs → same Sharpe) | 27-B |
| paper trading | simulated trading that can never touch a live rail (the "PAPER" badge property test) | 27-B |
| sandbox (DVP) | the developer playground: synthetic data, same API shapes, conformance suite | 27-A |
| conformance | the 50-check suite a third-party integration must pass to be certified | 27-A |
| deprecation (12-month) | the public-API breaking-change rule: sunset header + 12 months (27 Part A §3.5) | 27-A |
| attribution | AFF: last-touch-30d credit of a purchase to an affiliate | 23 |
| rate card | AFF: the frozen commission terms a payout computes from | 23 |
| reversal (commission) | AFF-07: a refund reverses commission via a linked entry — never a delete | 23 |
| meter / invoice / dunning | BIL: per-tenant usage metering → monthly invoice → overdue collection | 22 |
| pass-through | BIL: provider costs (MetaApi, Veriff, …) billed to tenants at cost | 22 |

## 7. Operations & delivery

| Term | Meaning | Owner |
|---|---|---|
| TTS | FunderBlu's legacy system (the migration source; read-only after cutover) | 25 |
| dry run | the anonymized end-to-end migration rehearsal (the 100%-or-dispositioned gate) | 25 |
| parallel run | 14 days of TTS-live + Alpha-One-mirroring with per-day delta reports | 25 |
| cutover | the instant TTS goes read-only and Alpha One goes live (+ 30-day rollback watch) | 25 |
| concierge | the SUP-backed white-glove support during parallel run + cutover | 25/18 |
| restore drill | the monthly practiced PG restore proving RPO ≤ 5 min / RTO ≤ 2 h | 06 |
| RPO / RTO | recovery-point / recovery-time objectives (how much data / how much downtime) | 06 |
| break-glass | the emergency elevated-access path (2FA'd, auto-expiring, always reviewed) | 21 |
| 2-box | the V3 production shape: app box + data box (the 29 §3.2) | 29/27-C1 |
| health score / NPS / QBR | CS: per-tenant health (weekly), satisfaction survey (quarterly), business review | 27-C2 |
| capacity review (PLT-02) | the quarterly infra headroom + cost review | 27-C1 |

## 8. Process (how we build)

| Term | Meaning | Owner |
|---|---|---|
| ADR | Architecture Decision Record: the 12 binding stack/shape decisions (docs/01 §3) | 01 |
| non-negotiables | the 8 product invariants (docs/00 §8) re-verified at every gate | 00 |
| train (V1.0/V1.1/V2.0/V3.0) | the PRD release grouping: 154 / 21 / 630 / 214 rows (+1 unassigned) | 00/99 |
| phase (0–5) | the build grouping in docs/99 (phases ≠ trains: MIG ships early, V1.1 splits) | 99 |
| wave | a parallelizable sub-group inside Phase 4/5 (waves overlap by ≤1 week) | 99 |
| milestone (M0–M5) | the phase-end go/no-go gate with a staging demo + checklist | 99 |
| freeze (contracts) | the milestone-tagged API/event snapshot: additive-only until the next freeze | 99/12 |
| P0 / P1 / P2 | PRD priority: launch-blocking / train-committed / nice-to-have-in-train | PRD |
| S / M / L | PRD complexity: days / ~week / multi-week (no XL anywhere) | PRD |
| synthetic data | generated test data (the only data allowed on staging — never prod copies) | 06 |
| prod-like | a dataset shaped like production: a legal event + CON sign-off + anonymization | 06/25 |
| property test | a test asserting an invariant over generated inputs (the 28 §11 suite) | 28 |
| contract check | the CI gate asserting code matches `contracts/` (routes, codes, schemas) | 04 |
| isolation test | the CI property test: querying as another tenant returns 0 rows, every table | 01/28/35 |
| ticket / SLA | SUP: a support case / its response+resolve time contract | 18 |
| segment / campaign | CRM: a computed trader cohort / a consent-checked outreach over it | 20 |

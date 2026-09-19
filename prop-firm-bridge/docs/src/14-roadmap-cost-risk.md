## 14. Build Roadmap, Team, Cost, and Risk Register

### 14.1 Phased roadmap (A→Z)

**Phase 0 — Foundations (weeks 1–6).** Contract repo (protobuf + rule-pack schema + OpenAPI) with codegen in all three languages; monorepo + CI/CD + environments; PG schema (ledger, rule packs, pairings, audit chain) + RLS; Vault; OTel baseline; **sim-harness v0** (deterministic market gen + ground-truth oracle, MT5-REST persona only); MT5 EA v0 (pairing + spool + hello/ack). *Exit criterion: a simulated MT5 persona trades in stage; every event is auditable end-to-end; guard passes the full T1–T3 regression suite.*

**Phase 1 — Supervision MVP (weeks 6–14).** Go bridge nodes (WS+REST), MT5 adapter, normalizer+guard (Rust crate, FFI), Kafka topics, rules engine v1 (daily loss, max overall static/trailing, target, min days, rollover), challenge state machine, trader portal v1 (live view, challenge status), tenant admin v0 (single tenant, rule-pack CRUD), reconciliation v1 (position diff 60 s + hourly full state), hash-chained audit + evidence pack generator. *Exit: one real (or stage) tenant runs challenges; dispute pack settles a synthetic dispute.*

**Phase 2 — Funded loop (weeks 14–22).** Funding saga (funded + hedge accounts via broker API), position/hedge sync with drift alerts + auto-rebalance, funded rule scopes (payout schedules, consistency rules), payout service (provider integration, 4-eyes workflow, FX schedule), billing/metering v1, notifications. *Exit: a simulated trader is funded, trades, hedges 1:1 with drift < tolerance, and receives a correct payout — all asserted by the harness.*

**Phase 3 — Platform breadth (weeks 22–30).** MT4 adapter (REST, `.pfx` onboarding), cTrader adapter (cBot + Open API server-side mode), DXtrade adapter, TradingView webhook adapter, multi-tenant hardening (per-tenant consumer groups, metering-based billing, tenant exports), storefront (tenant-branded checkout), KYC tooling integration, fraud feature pipeline v1 (identity graph, news-proximity, latency arb). *Exit: 3+ tenants, 3+ platforms, 10k simulated traders in stage with SLOs green under news-spike scenario.*

**Phase 4 — Scale & adversarial hardening (weeks 30–40).** WS protobuf v2 + Ed25519 keys, multi-region active-passive (MirrorMaker, RTO < 15 min), shadow-verdict canary system, ML risk scoring (champion/challenger, drift monitoring), advanced consistency rules, dispute-center (tenant-side portal), cost/tenant metering v2, chaos game-day cycle. *Exit: 25k-trader reference fleet sustained at SLOs; RTO proven in game-day; pentest findings closed.*

**Phase 5 — Platform business maturity (ongoing).** Tenant self-serve everything (rule packs, pricing, branding, data exports), partner APIs (tenant ↔ platform webhooks), advanced venues, white-label "as-a-service" marketplace features, DR active-active evaluation, cost optimization program.

### 14.2 Team & effort (reference)

| Role | FTE (phases 0–4) | Notes |
|---|---|---|
| Go engineers (bridge + services) | 3.5 | |
| Rust engineers (engine, guard, harness) | 2.5 | the harness is one of their permanent jobs |
| TypeScript engineers (portal, back-office, storefront) | 3.5 | |
| Platform integrations (MQL/cBot, broker APIs) | 1 | scarce skill; start recruiting in phase 0 |
| SRE / security | 1 | |
| Product / domain (ex-prop-firm ops preferred) | 1 | owns the rule-pack semantics — *this person is why the engine is right* |
| PM | 0.5 | |
| **Total** | **~13 FTE × 40 weeks** | ≈ 52 person-months to phase 4; range ±25 % depending on broker API access and team seniority |

### 14.3 Cost outlook (excl. salaries)

- **Infra** (Section 12.5): ~$10–16k/mo at 25k traders; ~$2–4k/mo during phases 0–2.
- **Third parties**: economic calendar, KYC/AML (per-check), PSP fees (per payout), pentest ($30–80k/yr), broker fees for funded/hedge accounts (the real P&L line — model slippage asymmetry and spread costs per symbol pair before promising a split).
- **Biggest hidden cost**: broker API access negotiation (cTrader/DXtrade server-side) — start vendor conversations in phase 0; if denied, topology B shrinks to "server-side where allowed" and MT stays terminal-side.

### 14.4 Risk register (top 12)

| # | Risk | L×I | Mitigation (owner) |
|---|---|---|---|
| R1 | Wrong verdict (false fail/pass) erodes trust or loses money | M×H | pure engine + property tests + golden files + shadow verdicts + evidence packs (eng lead) |
| R2 | Broker API access denied / changed | H×H | dual-topology design (§3.2); vendor contracts in phase 0; topology A as permanent fallback (PM + integrations) |
| R3 | Terminal-side tampering scales (patched EA fleet) | M×H | broker-side truth via reconciliation + server-side execution migration + fraud scoring + pairing revocation (security) |
| R4 | Regulatory reclassification of challenges in key markets | M×H | jurisdiction feature flags, counsel review per market, entity routing (PM + counsel) — *do not ship into a market before this is answered* |
| R5 | News-spike cascade (orders ×20 + quote ×100) | M×M | allocation-free intent path, 50× load test in CI, pre-reject at L1 (eng) |
| R6 | Rollover bug hits 10k accounts at once | L×H | sharded leases + idempotent unique constraint + harness scenario + canary tenants (eng) |
| R7 | Hedge drift = silent real-money loss | M×H | 10 s drift loop, fill-aware tolerance, auto-flatten + page (eng + ops) |
| R8 | Multi-tenant cross-access (bug or insider) | L×H | RLS + repo enforcement + cross-tenant tests per release + audit chain + 4-eyes (security) |
| R9 | Talent: MQL integrator / Rust financial engineer scarcity | H×M | recruit early, document the thin-client contract so it's swappable (PM) |
| R10 | Kafka/PG ops at scale outpace team | M×M | managed services, GitOps, runbooks from day 1, game-days (SRE) |
| R11 | Cost overruns at scale (ticks, storage, connections) | M×M | opt-in tick feeds, metering from day 1, weekly capacity review (SRE + PM) |
| R12 | Scope creep into "become the broker" | H×M | hard scope line: supervision, never custody-of-funds; brokerage features are tenant contracts, not platform features (product) |

### 14.5 The A–Z in one breath

**A**uthenticity (signing, pairing, fingerprints) → **B**roker topologies (terminal-side vs server-side) → **C**anonical events (protobuf, deal-id idempotency) → **D**rawdown math (decimal, broker_ts, intraday vs EOD, static vs trailing) → **E**vidence (event-sourced, hash-chained, replayable) → **F**raud (graph, calendar, latency, pattern) → **G**uard (HMAC/seq/nonce/skew, < 1 µs) → **H**edging (mirror accounts, drift loops) → **I**solation (RLS, tenant-bound keys, queue isolation) → **J**ustice (dispute packs, retroactive apply) → **K**afka (partition-per-account) → **L**edger (double-entry, immutable) → **M**ulti-tenancy (packs, metering, exports) → **N**ews (calendar-joined rules, pause-vs-fail policy) → **O**perations (SLOs, six runbooks, game-days) → **P**ayouts (saga, 4-eyes, FX schedule) → **Q**uotes (opt-in, spread caps) → **R**esilience (spools, resync, degraded mode) → **S**imulation (the harness as moat) → **T**rust (reconciliation as heartbeat) → **U**pgrades (canary by account hash, shadow verdicts) → **V**erdicts (proof, not assertion) → **W**eekends (cutoffs, swaps, carry) → **X**-tenant leaks (zero-tolerance SLO) → **Y**ield (billing, metering, unit economics) → **Z**ero-downtime rollovers (leases + unique constraints).

---

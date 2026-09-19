## 15. Glossary and References

### 15.1 Glossary

| Term | Meaning in this document |
|---|---|
| **PFaaS** | Prop Firm-as-a-Service: multi-tenant SaaS on which prop firms (tenants) run funded-trader businesses |
| **Bridge** | The edge plane connecting trader-side trading terminals to the platform core (telemetry up, control down) |
| **Adapter** | Per-platform component (MT4/MT5/cTrader/DXtrade/TradingView) mapping wire ↔ canonical schema |
| **Canonical event** | The platform's normalized trade/account event (protobuf-defined); the unit of the event log |
| **Pairing key** | Per-account, one-time-showed long-lived key that bootstraps a terminal session |
| **Session key** | 256-bit per-session key signing every bridge message (24 h TTL) |
| **Guard** | Per-message verification pipeline (HMAC, seq, nonce, binding, cross-checks) |
| **Spool** | Terminal-local ring buffer (≥ 72 h) of unsent telemetry — the evidence-survives-outages guarantee |
| **Resync / snapshot** | Full state collection from the terminal after a gap, checksummed and chunked |
| **Rule pack** | Immutable, versioned, tenant-scoped JSON definition of all rules for an account scope |
| **Verdict** | Structured, input-complete rule outcome (proof, not assertion) |
| **HWM** | High-water mark; the reference for trailing drawdown |
| **Day snapshot** | Per-account, per-day row: start equity/balance, traded flag, counters — the rollover artifact |
| **Reconciliation** | The continuous proof that platform state ≈ broker state (two-truths discipline) |
| **Integrity alert** | Raised when bridge cross-checks (recomputed PnL, broker_ts monotonicity) fail |
| **Deferral** | Pausing an account's rules clock while its input stream is incomplete — never decide on partial evidence |
| **Saga** | Multi-step provisioning/payout with compensations (funded + hedge account) |
| **Topology A/B** | Terminal-side thin-client execution / server-side (platform-executed) trading |
| **Hedge/mirror account** | The firm's offsetting real account neutralizing funded traders' market exposure |
| **Evidence pack** | Generated, signed dispute bundle: events, verdicts with inputs, reconciliation, admin actions |
| **Sim harness** | Deterministic broker + terminal simulator with scenario DSL and ground-truth oracles |
| **Shadow verdicts** | Canary-build verdicts computed alongside live and diffed for auto-rollback |

### 15.2 Protocol & platform references

- MetaTrader 5 MQL5 reference — `WebRequest`, `OnTradeTransaction`, `HistoryDealSelect`, `AccountInfo` (MetaQuotes documentation).
- MetaTrader 4 — `WebRequest` domain-signature model (`.pfx`), terminal constraints (32-bit, one account per terminal/server).
- cTrader — Open API v2 (server-side REST: positions, execution reports, history), cBot developer docs (client-side).
- DXtrade — platform REST + WebSocket API (trade webhooks, position limits, per-account API keys).
- TradingView — strategy webhook documentation (outbound HTTPS, token auth, no execution API).
- RFC 8785 (JSON Canonicalization Scheme) — canonical byte form for HMAC signing of JSON envelopes.
- RFC 8259 / 4180 basics for wire hygiene; NTP/PTP — chrony operational practice for bridge clock discipline.

### 15.3 Architecture pattern references

- **Event sourcing & CQRS** — the trading domain's state is a materialized view over an append-only log (Martin Fowler's pattern literature; Gray & Reuter for transaction foundations).
- **Saga pattern** (H. Garcia-Molina & K. Salem; Microsoft Orleans documentation) — multi-service provisioning with compensation.
- **Transactional outbox** — reliable cross-store publish (Kleppmann, *Designing Data-Intensive Applications* — the single best book for this architecture; especially chapters on consistency, consensus, and replication).
- **Consensus-free partition ordering** — Kafka partition-key ordering as the substitute for distributed consensus (Kleppmann ch. 10 discussion of ordering).
- **Dual-entry ledger design** — the accounting literature (double-entry bookkeeping invariants) applied to `journal/entries` tables.
- **Row-Level Security multi-tenancy** — PostgreSQL RLS documentation; tenant-isolation patterns (SaaS tenancy surveys, e.g., the "Database-per-Tenant vs Schema-per-Tenant vs RLS" decision space).
- **STRIDE threat modeling** (Microsoft SDL) — the structure of Section 8.1.
- **SRE practice** (Google SRE Workbook) — SLOs, error budgets, toil; adapted in Section 12.
- **Property-based testing** — `proptest` (Rust), `fast-check` (TS), `go-spew`-era testing idioms; the literature on algebraic specifications of invariants.
- **Financial data systems** — click-through: ClickHouse documentation (S3-backed cold storage, ReplacingMergeTree for evidence tables); Redpanda documentation (Kafka-API compatibility).

### 15.4 Domain references (the prop-firm business itself)

- Prop-firm public rules pages (FTMO, FundingPips, TopStep-style futures firms, MyFundedFX etc.) — the *ground truth* of what rule packs must express; collect 10–20 competitor rule sets and derive the rule-pack schema from the union of their semantics (this is a week-1 product exercise, not an afterthought).
- Broker API documentation (for the specific brokers the platform onboards): MT5/CTP (MetaQuotes), cTrader Open API (cTrader LLC), DXtrade (DXglobal).
- Payment-rail documentation (Payoneer, Stripe Connect/Transfers, ACH/SEPA schemas) for the payout saga.
- Economic calendar provider documentation (ForexFactory et al.) — tier definitions (high/medium/low impact) are *their* vocabulary; the rules pack must pin a calendar **version** and a mapping to its own tiers.
- Regulatory: FCA/ASIC/CMA statements on prop firms and "gaming" classification where applicable; PRA/Pakistani SECP considerations for the tenant's entity (per-market counsel review — Section 8.7).

### 15.5 Decision log (ADR seeds to write in week 1)

1. ADR-001: Terminal-side execution as default, server-side where broker APIs allow (§3.2).
2. ADR-002: Event-sourced trading domain; PG as materialized view; Kafka partition-per-account (§4.4, §7.2).
3. ADR-003: Rule packs as immutable data, engine as pure evaluator, broker_ts as rule clock (§6).
4. ADR-004: RLS multi-tenancy over schema-per-tenant (revisit at 500+ tenants or on contract demand) (§4.5).
5. ADR-005: JSON wire v1 → protobuf v2; JCS canonicalization for HMAC (§5.1, §5.4).
6. ADR-006: Go bridge nodes + Rust guard/engine (swap path defined by the interface) (§10.1).
7. ADR-007: Redpanda vs Kafka (default: Kafka; switch criteria documented) (§11.1).
8. ADR-008: Degraded-mode policy on platform outage — trading continues at broker, rules clock pauses, spooled evidence decides (§5.7).
9. ADR-009: Evidence retention 7 y cold (jurisdiction-configurable) (§8.6).
10. ADR-010: Sim harness as CI/ canary / DR referee — mandatory investment (§11.11, §13.4).

---

*End of document. Diagrams: 15 (system context, container architecture, lifecycle, event flow, auth handshake, order placement, close + verdict, reconnect/resync, daily rollover, funding saga, payout, deployment, rules engine, tenant onboarding, fraud detection) — Mermaid sources in `diagrams/`, rendered SVGs in `rendered/`.*

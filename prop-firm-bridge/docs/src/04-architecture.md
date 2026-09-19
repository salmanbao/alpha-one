## 4. High-Level Architecture

### 4.1 System context

{{DIAG:01-system-context}}

### 4.2 Container architecture

{{DIAG:02-container-architecture}}

### 4.3 The four planes

**Edge plane (Go).** TLS termination, WAF, WebSocket frontend with per-connection state machine (authed → streaming → degraded → suspended), API gateway for all HTTP surfaces (portal, admin, webhooks, broker callbacks). Stateless; horizontal autoscaling; WebSocket connections placed by consistent hash of `account_id` for *soft* stickiness (Redis session registry makes any node able to take over any session, so stickiness is optimization, not requirement).

**Bridge plane (Go core, Rust hot-path lib).** Adapters → normalizer → guard (sequence, replay, idempotency, clock skew) → publisher. The "hot path" — per-message HMAC verification, canonicalization, sequence accounting — is Rust (shared library or gRPC microservice; the pragmatic choice in v1 is a **Rust core behind a Go shim**: Go owns connections/Kafka, Rust owns the per-message pipeline; measure before splitting further).

**Core plane (Go).** Domain services: identity/tenancy, challenges (state machine), accounts & balances (ledger), orders & positions, position/hedge sync, payouts, billing, notifications, reconciliation. All read/write PostgreSQL with **tenant-scoped queries enforced at the repository layer** (no service sees another tenant's rows), outbox pattern for all cross-service effects.

**Data plane.**
- **PostgreSQL 16** — system of record. Multi-tenant via Row-Level Security (one database, tenant-scoped policies) — simpler ops than per-tenant schemas at ~50–500 tenants; move to schema-per-tenant only if a contractual requirement demands it. Double-entry **ledger tables** for every balance movement; `day_snapshots`, `rule_packs` (immutable, versioned), `verdicts`, `audit_log` (hash-chained), `sessions`, `pairings`.
- **Redis 7** — hot session state (seq counters, rules pack version, halt flags, hot account state for the rules engine), rate limits, distributed leases (cron sharding), pub/sub for control-command fan-out.
- **Kafka / Redpanda** — the event backbone. Topics partitioned by `account_id` so per-account ordering is *structural*, not probabilistic. Exactly-once *delivery* is unnecessary; exactly-once *effect* is achieved by idempotent consumers + idempotency keys.
- **ClickHouse** — ticks (optional, if quotes feed rules or analytics), closed trades, verdicts, message telemetry (per-tenant metering), feature stores for fraud. 90-day hot, object-storage cold.
- **Object storage (S3-compatible)** — immutable audit archive (hash-chained blocks, GPG-signed manifests), tenant exports, ETL landings.

### 4.4 Event backbone design (the spine)

{{DIAG:04-event-data-flow}}

Topics and partitioning:

| Topic | Partition key | Retention | Consumers |
|---|---|---|---|
| `bridge.events` | `account_id` (hash) | 7 d (30 d for audit tenants) | rules engine, order svc, challenge svc, risk, CH sink, reconciliation |
| `bridge.events.control` | `account_id` | 7 d | bridge fleet (control fan-out), audit |
| `ticks` | `symbol` | 24 h | rules engine (spread/news rules), CH sink |
| `rule.verdicts` | `account_id` | 30 d | challenge FSM, notifications, risk, CH sink, push fan-out |
| `audit` | `tenant_id` | 365 d | audit sink (hash-chained → object storage) |
| `metering` | `tenant_id` | 90 d | billing |

Ordering guarantee: **all rule-relevant events for an account are on one partition and consumed by the rules engine single-threaded per account.** Parallelism across accounts is unbounded; parallelism within an account is zero — which is what makes the engine's state machine trivial and replay exact.

### 4.5 Multi-tenancy model

- `tenant_id` is a first-class column on every table, key, topic consumer group, metric label, and log field. No exceptions (this is an SLO: "zero cross-tenant data access" is verified by integration tests on every release).
- **RLS**: `CREATE POLICY tenant_isolation USING (tenant_id = current_setting('app.tenant_id'))`; the app sets the GUC per connection pool. Repository layer refuses to build a query without a tenant scope (compile-time-checked wrapper in Go).
- **Performance isolation**: per-tenant queue *consumer groups* for bursty work (rollover, reconciliation) so one tenant's backlog cannot starve others; per-tenant message rate limits on the bridge (plan-based); noisy-neighbor circuit breakers on PG (pgBouncer pool per tenant class).
- **Key isolation**: every bridge API key is bound to `(tenant_id, purpose, platform)`; a key from tenant A *cannot* even be verified against tenant B's accounts (pairing records are tenant-scoped).

### 4.6 Deployment topology

{{DIAG:12-deployment}}

### 4.7 Tenant onboarding (what "as-a-service" looks like in ops)

{{DIAG:14-tenant-onboarding}}

### 4.8 Where every rule-relevant truth lives

| Truth | Owner | Store |
|---|---|---|
| Position exists at broker | Broker | broker (authoritative) |
| Position in platform model | Order service | PG `positions` (+ ClickHouse history) |
| Balance (platform ledger) | Account service | PG `ledger` (double-entry) |
| Day snapshot & HWM | Rules engine state | PG `day_snapshots` (persisted at each event batch + rollover), Redis hot |
| Rule definition | Rule pack registry | PG `rule_packs` (immutable versions) + Redis cache |
| Verdicts | Rules engine | PG `verdicts` + Kafka + ClickHouse |
| Evidence (raw telemetry) | Bridge | Kafka → ClickHouse → object storage (immutable) |

This separation is deliberate: **the broker is right about markets, you are right about the business.** Reconciliation (Section 7.4) exists only because both are true simultaneously.

---

## 11. Technology Selection (Best Solutions)

Selections below are the **recommended defaults** with the runner-up and the kill-criteria for each. All are boring-on-purpose: in a system where a bug costs real money, the best technology is the one with a decade of production scars.

### 11.1 Event backbone

| Option | Verdict |
|---|---|
| **Kafka (Confluent or MSK)** | ✅ Default. Partition-per-account ordering, exactly-once effect via idempotent consumers, MirrorMaker for DR, 7-year ecosystem, ops tooling. Cost: real (3 brokers minimum) |
| **Redpanda** | ✅ Strong runner-up — same Kafka API, lower ops burden, single-binary; pick it if you don't need Kafka's exotic connectors. *Switch criterion:* none until scale forces |
| NATS JetStream | ❌ Here. Ordering guarantees + retention semantics are weaker for this use case; great for internal control-plane messaging (use it *inside* a service if you like) |
| Pulsar | ❌ Here. Two-tier storage is overkill; smaller ecosystem for financial-grade patterns |

### 11.2 System of record

- **PostgreSQL 16** (Citus only if shard pain arrives; RLS is native — the multi-tenant answer). pgBouncer (transaction mode) + per-tenant-class pools. PITR 35 d, logical replication to DR + analytics read replica.
- ❌ MySQL here (RLS story, JSON, ecosystem), ❌ per-tenant databases at 100+ tenants (ops suicide), ❌ document DB for the ledger (you need transactions and constraints, not flexibility).
- Ledger design: double-entry `journal` + `entries` with decimal(20,8), one transaction per business effect, immutable (no UPDATE — corrections are new entries). This is the difference between "our math is defensible" and "our math is folklore."

### 11.3 Hot state

- **Redis 7 cluster** (3 shards, AOF everysec, no eviction — OOM must page, never silently evict a session key).
- ❌ Memcached (no persistence, no TTLs-without-pain), ❌ building your own (you're not).

### 11.4 Time-series / analytics

- **ClickHouse** (2×2 shards/replicas): ticks, trades, verdicts, raw-event evidence, per-tenant metering. Columnar scans for dispute packs are *fast* here; 7-year cold tier via S3-backed tables.
- Runner-up: **QuestDB** (simpler ops, weaker multi-tenant + DR story), **Timescale** (fine up to ~2× the tick volume here).
- ❌ InfluxDB for the evidence tier (retention/consistency story), ❌ "just use Postgres for ticks" (it will hurt at 1k rows/s × 7 y).

### 11.5 Streaming compute

- Consumers are **services, not a Flink cluster**: the domain is partition-ordered state machines, which a per-account Rust/Go consumer *is*. Add Flink/Polars later only if fraud-feature pipelines outgrow simple consumers (the ML side can batch — it doesn't need the hot path).
- Batch/ETL: **dbt** on PG/CH + object storage; exports to tenant S3 on schedule (contractual right).

### 11.6 API & service layer

- **gRPC** between services (typed, fast, streaming for control fan-out), **REST + WS** at the edges (OpenAPI-published), **tRPC or REST** portal↔BFF.
- **Go gateway** with: OIDC validation, RBAC checks, rate limits (Redis token-bucket, per tenant/IP/account), request tracing propagation, schema-validated webhooks.
- ❌ Service mesh as a *requirement*: optional (use Istio only for mTLS at scale); default-deny NetworkPolicy + mTLS sidecars-free via Vault CNI keeps it simpler.

### 11.7 Secrets & keys

- **HashiCorp Vault** (or AWS KMS + Secrets Manager if single-cloud): dynamic broker credentials where supported, per-tenant encryption keys, pairing-key wrapping, OIDC root for internal mTLS, audit logging of every secret read.
- **KMS envelope encryption** for PG at rest and S3 evidence.
- ❌ Env-var secrets (dead on arrival), ❌ per-tenant KMS keys *as default* (cost/ops; offer as enterprise tier).

### 11.8 Observability

- **OpenTelemetry everywhere** (Go/Rust/TS SDKs → OTLP collector): traces carry `tenant_id`, `account_id`, `deal_id` — a trace from "trader clicked" to "verdict emitted" is one link click in Grafana.
- **Prometheus + Grafana** (metrics, SLO burn alerts), **Loki** (structured JSON logs, tenant-filtered), **Grafana IRM / PagerDuty** (alert routing).
- Business-observability dashboards are *first-class*: connections per node, spool occupancy, seq-gap rate, DLQ age, verdict deferrals, reconciliation drift, rollover progress, per-tenant message metering. If you can't see a resync storm happening, you're too late.
- **SLOs** (error-budget based, per plane): bridge availability 99.95 %, verdict freshness p99 < 150 ms (target, tracked), zero cross-tenant access (hard SLO, 100 %), zero uncorrected reconciliation drift > 24 h.

### 11.9 Infrastructure & delivery

- **Kubernetes** (EKS/GKE — pick the one your team knows; the app is k8s-idiomatic either way), **Helm + ArgoCD** GitOps, **Terraform** for everything else, per-env (dev/stage/prod, + per-tenant canary tenants in prod).
- **Blue-green** for core services, **canary** (5 % of accounts by hash) for bridge releases — a bridge regression touches live supervision; canary + automatic rollback on seq-gap/SLO burn is mandatory.
- **Cha engineering**: quarterly game-days (Kafka down 10 min, PG failover, 30 % of bridge nodes killed, broker fake-outage) with the sim harness as the referee.
- ❌ Raw VMs (you'll outgrow by month 4), ❌ Serverless for the bridge (cold starts + connection model are wrong for 6k–50k WS).

### 11.10 Payments, news, KYC (the "boring" integrations that define the product)

- **Payouts**: Payoneer + bank rails (ACH/SEPA/wire) + Stripe (card payouts for small amounts); idempotency keys on every provider call; webhooks HMAC-verified; *never* block the platform on provider latency (async saga + status webhooks).
- **Economic calendar**: one primary (e.g., ForexFactory API) + one secondary; the rules engine joins on calendar *version*; calendar outages degrade to "news rules paused + audit flag" (config: pause vs fail-closed — tenant choice, documented in terms).
- **KYC/AML**: provider API (e.g., Sumsub/Onfido/Veriff) with document storage in tenant-scoped buckets, sanctions/PEP screening on funded conversion and every payout (re-screen schedule per jurisdiction).

### 11.11 The one place NOT to be boring

The **simulation harness** (Rust) is where you spend "fun" budget: a deterministic, scenario-driven broker simulator with scenario DSL (news spikes, gaps, partial fills, broker outages, malicious-EA personas) that drives the *entire* production pipeline in CI and staging. Every production incident that has ever happened in this industry is a scenario the harness could have generated on Tuesday. If you build one thing extra, build this.

---

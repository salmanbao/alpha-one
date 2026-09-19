# 01 — Platform Architecture

> This document is the contract between all module docs. If a module doc contradicts
> this document, this document wins and the module doc must be corrected.

## 1. Shape of the system

Alpha One is a **monolith-lite** deployment: a small number of tightly-coupled
services that share one Postgres, connected by an event backbone, behind one edge.
We deliberately reject microservice sprawl: with 1 DevOps, every extra service is an
on-call surface.

```
                        ┌────────────────────────────────────────────────────────────┐
                        │                       Cloudflare (edge)                    │
                        │  DNS · CDN · WAF · Bot mgmt · TLS · rate limiting (edge)  │
                        └───────────────┬────────────────────────────┬───────────────┘
                                        │                            │
                          ┌─────────────▼───────────┐    ┌───────────▼──────────────┐
                          │  Next.js web apps (FE)  │    │  Go Core API  ─────────┐ │
                          │  TD · ADM · CON · CMS   │◄──►│  (in-app GW layer)     │ │
                          └─────────────────────────┘    └───────────┬─────────────┘ │
                                                                     │               │
        ┌───────────────────┐   ┌───────────────────┐   ┌───────────▼───────────────▼┐
        │  Bridge (Go)      │   │  Engine (Rust)    │   │  Workers (Go)              │
        │  BRG: MT5/MetaApi │   │  EVL: rules,      │   │  · event consumers         │
        │  sync·enforce     │   │  verdicts, PnL    │   │  · schedulers (day-boundary│
        └─────────┬─────────┘   └─────────┬─────────┘   │  · reconcilers · DLQs)    │
                  │  provider API         │  verdicts   └───────────────┬────────────┘
                  ▼                       ▼                             │
        ┌───────────────────┐   ┌───────────────────┐                   │
        │  MetaApi / MT5    │   │  Ledger & Audit   │◄──────────────────┤ (same PG)
        │  (broker world)   │   │  (Postgres)       │
        └───────────────────┘   └───────────────────┘                   │
                                                                        │
        ┌────────────────────────────────────────────────────────────────┴───────┐
        │                        Postgres 16 (PgBouncer, tx mode)               │
        │  system of record: domain tables · event log · outbox · commands ·    │
        │  ledger · audit · idempotency keys                                    │
        ├────────────────────────────────────────────────────────────────────────┤
        │  Redis 7 (AOF)   sessions · rate-limit counters · streams (event bus) │
        ├────────────────────────────────────────────────────────────────────────┤
        │  Hook0 (self-hosted)  tenant outbound webhooks: retry, sign, replay   │
        ├────────────────────────────────────────────────────────────────────────┤
        │  Cloudflare R2  tenant docs & PDFs (tenant-prefixed keys, zero egress)│
        ├────────────────────────────────────────────────────────────────────────┤
        │  External: MetaApi · Veriff · Match2Pay/Interkasa/NOWPayments ·       │
        │  Postmark · Sentry · Flipt (flags) · Prometheus/Grafana/Loki/OTel     │
        └────────────────────────────────────────────────────────────────────────┘
```

### 1.1 Deployables (Docker Compose services)

| Service | Language | Responsibility | Scaling |
|---|---|---|---|
| `web` | Next.js 15 / TS | TD, ADM, CON, CMS frontends (routed by host/subdomain). SSR/RSC for pages; no business logic | stateless, 1 instance V1 |
| `api` | Go 1.27 | All public + internal REST APIs. Hosts the **in-app gateway layer** (GW). Sync request handling | stateless, 1–2 instances |
| `bridge` | Go 1.27 | BRG: MetaApi connections, account provisioning, polling sync, enforcement actions | stateless over PG, 1 instance (MetaApi rate-limited anyway) |
| `engine` | Rust (axum) | EVL: rule evaluation, verdicts, PnL math, day-boundary processing | stateless, 1–2 instances; invoked by `api`/`bridge`/`workers` |
| `relay` | Go 1.27 | Outbox relay: reads `outbox`, publishes to Redis Streams, manages delivery seq | **exactly one instance** (locked via PG advisory lock) |
| `workers` | Go 1.27 | Event consumers (consumer groups), schedulers, reconcilers, report generation, DLQ handling | stateless, 1–2 instances |
| `docs-worker` | Node 22 | DOC: Puppeteer PDF rendering, uploads to R2 | stateless |
| `db` | Postgres 16 | System of record | single instance + nightly WAL archiving (DR) |
| `db-proxy` | PgBouncer | Tx-pool in front of Postgres | — |
| `redis` | Redis 7 | Sessions, rate limits, Streams, BullMQ jobs (cron) | AOF everysec |
| `hook0` | Hook0 | Outbound webhook delivery to tenants | — |
| `flipt` | Flipt | Feature flags (TEN-10, CON-31) | — |
| `prometheus` / `grafana` / `loki` / `otel-collector` | — | Observability stack (V2 register; V1: structured logs + Prometheus + Grafana) | — |

**Rules:** no service writes to another service's tables directly — cross-domain
writes go through domain APIs or domain events. The `api` service may *read*
other domains' tables (it hosts all REST endpoints) but writes are issued as
commands handled by the owning domain package. In code, domains are Go packages
with enforced boundaries (linter: `goimports` + custom `boundary` check in CI).

## 2. Technology stack (binding)

| Concern | Choice | Rationale / rejected alternatives |
|---|---|---|
| Core language | **Go 1.27** (api, bridge, relay, workers) | One binary per service, easy concurrency for sync polling, excellent Postgres/Redis clients. Rejected: Node (GC latency in hot sync path, weaker type safety for money math), Python (runtime perf for sync). |
| Rule engine language | **Rust** (engine) | Verdict math must be exact, allocation-light, and property-tested (already scaffolded in `pf-platform` with `cargo test` green). Exposed as HTTP service (JSON, no gRPC in V1 — JSON for debuggability; move to gRPC only if p99 proves it). |
| Frontend | **Next.js 15 + TypeScript + Tailwind** | App Router, RSC for data-heavy pages, client islands for live charts (TradingView Lightweight Charts, ~45KB). One pnpm monorepo (`web/`) for TD/ADM/CON/CMS. Rejected: separate frameworks per app. |
| Primary DB | **Postgres 16** | Domain data, event log, outbox, command log, ledger, audit — all here. `pg_cron` NOT used (schedulers live in workers). |
| DB access (Go) | **pgx + sqlc** | Compile-time type-safe SQL; no ORM drift. Migrations: **golang-migrate** (single source `infra/migrations`). |
| DB access (web) | Direct via api service only — **the FE never touches PG** | SSR fetches internal API over HTTP. |
| Cache/queue | **Redis 7** (AOF) | Sessions, rate-limit counters (INCR/EXPIRE), event streams, BullMQ for JS cron jobs. Rejected: Kafka (forbidden — see ADR-7), NATS (consider-later only). |
| Event bus | **Redis Streams + consumer groups**, fed by **Postgres outbox** | At-least-once delivery; consumers must be idempotent. Rejected: direct PG NOTIFY (no replay), Kafka. |
| Outbound webhooks | **Hook0** (self-hosted) | Retry, HMAC signing, replay UI, per-tenant endpoint mgmt. AGPL reviewed (self-hosted, no SaaS — acceptable). Rejected: homegrown delivery (rebuilds Hook0), Zapier (V3 at best). |
| API gateway | **In-app middleware** (Go `api`) behind **Cloudflare** | Tenant resolution → authn → authz → rate limit → quota → idempotency → logging. Rejected: Kong, Traefik (forbidden in V1 — extra service, and Cloudflare already does edge security). |
| AuthN | **Better Auth** (Go-compatible via its API, or the TS `web` BFF path) | Multi-tenant org model, sessions, 2FA (TOTP), DB-backed. Confirm multi-tenant org plugin in Phase 0 (BE-1 owns). Rejected: Auth0, Cognito (tenant-RBAC mismatch; cost; forbidden in PRD). |
| AuthZ | **Cerbos** (PDP) | Policy-as-code RBAC; `api` calls Cerbos per request decision (cached per (role, resource) pair). If integration proves painful in Phase 1, AUTH-13 becomes an in-house policy engine with the same interface. |
| Feature flags | **Flipt** (self-hosted) | TEN-10 (per-tenant entitlement gating), CON-31. |
| Secrets | **SOPS + age** in repo | Repo is the source of truth; Compose loads at deploy. Rejected: HashiCorp Vault (forbidden), Infisical (V2 upgrade path). |
| Hosting | **Hetzner** dedicated server (AX line), **Docker Compose** | Rejected: Kubernetes (forbidden V1), AWS (cost + lock-in), multiple regions (V3 at best). |
| Object storage | **Cloudflare R2** | Tenant docs, PDFs, KYC evidence images. Tenant-prefixed keys (`{tenant_id}/...`), signed URLs, zero egress fees. Rejected: S3 (egress), Hetzner Object Storage (no signed-URL parity). |
| KYC provider | **Veriff** (signed via FunderBlu contract) | Adapter pattern (KYC-04); second provider adapter only when demanded. |
| Payment providers | **NOWPayments** (crypto: TRC20/ERC20/BEP20), **Match2Pay + Interkasa** (PK/IN card & local) | Adapter pattern (CHK-04). Stripe Billing only for BIL (V3). |
| Email | **Postmark** (transactional); Resend allowed for dev | Templates rendered server-side (MJML → HTML), tenant-overridable. |
| PDFs | **Puppeteer** (Node `docs-worker`) | Certificates, statements, invoices. Rejected: html-pdf-lite (capability limits). |
| CI/CD | **GitHub Actions** (signed) | One workflow file family: lint → test → build → migrate → deploy (SSH, Compose pull). |
| Observability | **Prometheus + Grafana** (V1), **+ Loki + OTel** (V2 register) | Structured JSON logs (slog/Zap) with `tenant_id`, `correlation_id`. Sentry for errors (signed). Uptime Kuma for synthetic checks. |
| Charts | **TradingView Lightweight Charts** | TD-06/21 equity curves, P&L charts (~45KB, MIT). |

**Versioning:** URL-based (`/v1/...`) — the only supported scheme. Additive-only
changes within a version; breaking changes get `/v2/` and a `Deprecation`/`Sunset`
header on the old route (GW-28).

## 3. The twelve binding architectural decisions (ADRs)

Recorded from the PRD Open-Questions sheet (all "answered"). Each has a full write-up
where it bites; this is the register.

| # | Decision | Consequence |
|---|---|---|
| **ADR-1** | **Shared-schema multi-tenancy** with mandatory `tenant_id` column on every tenant-owned table. No schema-per-tenant, no DB-per-tenant in V1. | Every repository method takes `tenantID` as first argument; a **shared-schema guard** query hook wraps every query (adds `WHERE tenant_id=$?` if missing — enforced by the DB client wrapper, not developer memory). Proved by the `isolation.test` suite that runs every mutation under two tenants. |
| **ADR-2** | **No multi-brand / sub-tenants in V1.** One brand per tenant. | TEN white-label covers logo/colors/domain/email-sender; sub-tenant model is explicitly deferred (schema must not preclude it: `tenants.parent_id NULL` exists from day one). |
| **ADR-3** | **Secrets = SOPS+age in the repo.** | `.env` files are SOPS-encrypted; age private keys on deploy only; deploy script decrypts to Compose. Rotations are PRs with audit. |
| **ADR-4** | **API gateway = in-app middleware behind Cloudflare.** No standalone gateway process. | GW is a Go package; "deploying the gateway" = deploying `api`. Edge security (WAF, DDoS, TLS, basic rate limit) = Cloudflare. |
| **ADR-5** | **URL-only API versioning.** | No `Accept`-header versioning; no per-tenant version pinning in V1 (V2: tenant-pinned versions via CON). |
| **ADR-6** | **Outbox relay is a separate process.** Relay polls `outbox` (keyset pagination, batch 500) and writes to Redis Streams with a monotonically increasing `seq` per topic. Exactly-once publishing is guaranteed by PG transactional outbox + relay idempotency (event_id dedupe in relay state table). | No business code writes to Streams directly. Events that can't be read from PG can't exist — **events are transactions, not side effects**. |
| **ADR-7** | **Redis Streams = the event bus; at-least-once delivery; consumers are idempotent.** Kafka is forbidden. | Every consumer declares a consumer group; every consumer has a DLQ stream (`dlq.{consumer}`); replay = re-publish from event log or XGROUP CREATECONSUMER from offset. The **event log** in PG (`events` table) is the replay source of truth; Streams are the hot transport. |
| **ADR-8** | **PgBouncer in front of Postgres (transaction mode).** | All services connect via `db-proxy`. Long-lived connections live in the pool, not in services. `prepare` statements: use extended protocol without prepared-statement cache across pool restarts (pgx default handles this). |
| **ADR-9** | **Single Hetzner dedicated server + Docker Compose.** Kubernetes forbidden in V1. | One machine, one Compose project, healthchecks wired, restart policies. Multi-server/HA is a **Phase 4** item (V2) — single-machine is acceptable for V1 scale (§00 §5) with rehearsed DR. |
| **ADR-10** | **Single Postgres instance + rehearsed restore.** No warm standby in V1. | Nightly `pg_basebackup` + WAL archiving to a second Hetzner box (S3-compatible, cheap). **Restore drill is a monthly ops ritual with a documented target: RPO ≤ 5 min (WAL), RTO ≤ 2 h.** The drill report is a CON screen (PLT). |

**ADR-11**: **EVL is a separate Rust service.** The hot evaluation
path (per-tick drawdown/limit checks) runs in Rust with property-tested invariants;
Go calls it over local HTTP. Engine is stateless — all state in PG; Rust owns *math
and verdict logic only*.

**ADR-12**: **The broker attests time.** For all trading data
(positions, trades, equity), the broker-reported timestamp is canonical for day
boundaries and rule evaluation. Platform clock is used only for non-trading
lifecycle. Day boundaries are computed **per broker server timezone** (BRG-12).

## 4. Event backbone

### 4.1 Topology

```
 [PG tx] domain write + INSERT into outbox  ──►  relay (1 instance)
                                                     │ XADD topic.<domain>  (with seq)
                                                     ▼
                                             Redis Streams
        ┌──────────────────┬──────────────────┬──────────────────┬───────────────────┐
        ▼                  ▼                  ▼                  ▼                   ▼
   workers: consumers  web (SSE fan-out)  hook0 (tenant       analytics read-    DLQ per consumer
   (consumer groups):   for live dashboards)  webhooks, signed)  model updaters
   · notification       (TD live equity, ADM live queue) · per-tenant endpoint    (ANA read models)
     dispatcher        · in-app notifier       mgmt, retries, replay
   · ledger applier
   · evaluation trigger
   · audit applier
```

### 4.2 Envelope (binding — see `contracts/shared/event-envelope.json`)

```json
{
  "event_id": "01J9ZK8P3M4N5R6S7T8V9W0X1Y",
  "type": "account.evaluation_failed",
  "version": 1,
  "tenant_id": "01J9ZK8P3M4N5R6S7T8V9W0A",
  "occurred_at": 1758278400000,
  "correlation_id": "01J9ZK8P3M4N5R6S7T8V9W0Z",
  "causation_id": "01J9ZK8P3M4N5R6S7T8V9W0A",
  "actor": {"kind": "system", "id": "bridge:mt5-sync", "tenant_id": "01J9ZK8P3M4N5R6S7T8V9W0A"},
  "data": { "...": "type-specific payload, JSON Schema in contracts/events/" }
}
```

Rules:
- `type` = `{domain}.{past_tense_verb}` (e.g. `payout.requested`, `kyc.document_submitted`).
  The full catalog with consumers per event is in [31-event-catalog](31-event-catalog.md).
- `version` is the **schema version** of `data`; consumers must handle `version < max`
  they know about; unknown higher version → DLQ + alert.
- Events are **immutable facts** (never UPDATE/DELETE). Corrections are new events
  (`*.corrected` / `*.reversed`).
- `occurred_at` is when the fact happened (broker time if broker-attested); relay adds
  `published_at` internally (not in the envelope).
- Streams are trimmed to 7 days (`MAXLEN ~`); PG `events` table keeps full history
  (partitioned monthly; retention per AUD policy).

### 4.3 Delivery semantics

| Path | Semantics | Mechanism |
|---|---|---|
| PG → relay | exactly-once publish of a committed event | outbox + relay dedupe table |
| relay → consumer | **at-least-once** | Streams + consumer groups; ack on success |
| consumer → side effect | **idempotent** | idempotency keys derived from `event_id`; consumers check-then-act under row locks |
| consumer failure | retry w/ exponential backoff (5 attempts) → DLQ | workers supervisor; DLQ alerting to NOT + CON |
| replay | manual, from PG `events` by (topic, seq range) | CON screen + `relayer replay` CLI |

**Ordering:** no global ordering guarantee. Per-entity ordering is preserved by
routing keys = entity id (hash slot); consumers that need ordering process per-entity
serially (single goroutine per account key, or `FOR UPDATE` row lock).

## 5. Request lifecycle (in-app gateway)

```
Cloudflare ──► Next.js (page SSR, /api/* client routes)
                 │  (server-side: cookies → internal api call with service token)
                 ▼
        Go api /v1/...  [in-app GW chain]
         1. tenant resolution: subdomain (acme.alpha1.io) / header (internal) / API-key (external)
         2. authn: session cookie (web) · service token (internal) · API key (tenant machines)
         3. authz: Cerbos decision (role on resource) — console routes use platform realm
         4. rate limit: per-IP (edge) + per-user (Redis INCR) + per-tenant quota
         5. entitlement gate: does the tenant's plan include this route/module? (Flipt + TEN)
         6. idempotency: X-Idempotency-Key → Redis SETNX (TTL 24h, scope = method+path+key)
         7. correlation id: X-Correlation-Id in or generated; propagated to logs, events, engine
         8. handler → domain package → PG (tx) + outbox
         9. response envelope: { "data": ..., "meta": { request_id, version } }
        errors: { "error": { "code", "message", "details", "request_id", "docs_url" } }
```

The **error contract** is global ([30-error-taxonomy](30-error-taxonomy.md)); every
module doc registers its module-specific codes against it. GW-18: one error shape for
every failure, machine-readable `code`, human `message`, never a stack trace.

## 6. Data lifecycles (the four canonical flows)

**Flow A — Purchase → funded (happy path).**
```
Trader: TD "Buy challenge" → CHK session (GW idempotency)
  → order created (CHK) → payment provider (NOWPayments/Match2Pay) → webhook
  → order.paid (event) → LCC account provisioned (state=PAYMENT_PENDING → ACTIVATING)
  → BRG: MetaApi creates MT5 account (+ credentials encrypted, BRG-06)
  → LCC state=ACTIVE_EVAL, EVL: rule pack bound, evaluation.started
  → NOT: "You're live" email; DOC: certificate later on funding
  → TRADER TRADES: BRG sync (positions/equity/deals) every ≤60s + on tick events
  → each sync: EVL verdict (ok / breaching / passed) → LCC state transitions
  → on pass: LCC state=FUNDED_OFFER (V1: auto-fund or manual approval per tenant setting)
```

**Flow B — Sync tick (hot path, ~10/s).**
```
bridge: poll MetaApi (per account, staggered) → normalize (BRG-19)
  → upsert broker_account snapshot (PG) + INSERT sync_batch (PG, same tx)
  → outbox: bridge.tick {account, equity, margin, positions[...], broker_time}
  → workers: evaluation trigger → engine /evaluate (Rust, <5ms)
  → verdict stored + outbox: evaluation.verdict {ok|breach|target_hit}
  → LCC state machine applies (breach → ACCOUNT_FAILED + NOT + AUD)
  → ANA read-model updater (equity curve point) + web SSE fan-out (TD live)
```

**Flow C — Payout.**
```
Trader (funded): TD "Request payout" → PAY request (eligibility check: KYC ok, min trades,
  no open risk case, ledger balance) → payout.requested
  → ADM payout queue (manual approval in V1 default) → approver approves (step-up auth)
  → PAY executes via rail (crypto: NOWPayments withdrawal; card: provider)
  → ledger: two entries (payout liability → provider transfer) + AUD entry
  → provider webhook → payout.settled / payout.failed → NOT + DOC (receipt)
  → nightly reconciliation (workers): provider report vs ledger → mismatch → risk case
```

**Flow D — Tenant onboarding (CON).**
```
CON: create tenant (TEN) → plan + entitlements (Flipt flags) → white-label (domain, logo)
  → DNS CNAME → Cloudflare (ops) → AUTH org provisioned (Better Auth org)
  → invite first admin (email) → tenant "ready" checklist (ADM-39 on the tenant side)
  → CON usage metering starts (BIL foundation)
```

## 7. Tenant isolation (ADR-1 enforcement detail)

1. **Column:** `tenant_id ULID NOT NULL` on every tenant-owned table; FK to `tenants`.
   Platform-owned tables (plans, feature catalog, provider configs) have no tenant.
2. **Guard:** the Go DB wrapper (`pgxpool`-based `db.Tenanted`) exposes only
   `Query(ctx, tenantID, sql, args...)`; sqlc-generated queries carry the tenant param.
   A CI test (`guard_test.go`) scans the generated set for queries missing the tenant
   predicate.
3. **Web:** tenant is bound to the *subdomain*; the session cookie is scoped to
   `{tenant}.alpha1.io`. Cross-tenant cookie use fails tenant resolution (403).
4. **API keys:** keys embed tenant; the GW resolves tenant from the key and **ignores**
   any tenant header on key-authed requests.
5. **Isolation test suite:** every domain API test runs its happy path under tenant A,
   then under tenant B with A's ids → must 404 (not 403 — no existence leakage).
6. **Storage:** R2 keys are `{tenant_id}/{...}`; R2 bucket policy denies cross-prefix
   writes; signed URLs expire ≤ 1 h.
7. **Caching:** every Redis key is namespaced `t:{tenant_id}:...` — enforced by the
   cache client (same pattern as the DB guard).
8. **Second layer (open, D3):** Postgres RLS is the only way to make a *forgotten*
   predicate fail closed instead of leaking — the DB returns zero rows instead of all
   rows. Adopting it costs 2–4 % on indexed queries and demands transaction-scoped
   `set_config('app.tenant_id', …, true)` under PgBouncer transaction mode (ADR-8),
   `FORCE ROW LEVEL SECURITY` (the owner bypasses policies otherwise) and a
   `(tenant_id, …)` index on every policy table. Decision + mechanics:
   `docs/41-auth-ten-open-source-evaluation.md` §5, register row **D3**.

## 8. Module dependency graph

Build must respect this (arrows = "depends on"):

```
        AUTH ──────────────► TEN ──────────────► CON
          │                   │  ▲                  │
          ▼                   │  │                  │
        GW (in-app) ──────────┘  │                  │
          │                      │                  │
          ├──► EVT (outbox/relay/streams) ──────────┤
          │        │                                 │
          ├──► LED ◄── AUD                           │
          │        │                                 │
          ▼        ▼                                 ▼
        LCC ──► BRG ──► EVL          (ops plane: OPS underlies everything)
          │        │        │
          │        └──► RSK │
          ▼                 ▼
        KYC ◄──CHK──► PAY ◄── NOT ◄── DOC
                                │
              ADM ──► SUP ──► ANA ◄── CRM
              (all read the same domain APIs; MIG consumes LCC/BRG/CHK/PAY/KYC)
              (D5: BIL, AFF, SDK, DVP, TRD, PLT, CS attach in V2/V3)
```

Reading the graph:
- **Phase 0 (foundation):** OPS, AUTH, TEN, GW, EVT, LED, AUD, CON — nothing else
  works without them.
- **Phase 1 (core engine):** LCC → BRG → EVL → RSK (detection V2) → PAY, plus CHK +
  KYC + NOT + DOC because *purchasing and paying out* are V1.0 content.
- **Phase 2 (surfaces):** TD, ADM, SUP, ANA, MIG (FunderBlu cutover).
- **Phase 3 (V2 scale):** remaining V2 of each module (full ADM, API/webhooks, mobile,
  CMS, CMP, CRM, JRN, EDU, CHT, DVP keys).
- **Phase 4 (ops hardening):** HA, restore drills, capacity, PLT.
- **Phase 5 (V3 ecosystem):** BIL, AFF, SDK, CS, TRD, PLT full.

The authoritative, task-level version with exit criteria is
[99-development-phases](99-development-phases.md).

## 9. Repository layout (monorepo `alpha-one-platform`)

```
alpha-one-platform/
├── apps/
│   ├── api/            # Go: core API + in-app GW + domain packages (lcc, brg, evl-client, pay, chk, kyc, not, doc, led, aud, ten, authz-client, sup, ana, adm, con, mig, ...)
│   ├── bridge/         # Go: BRG service (MetaApi client, connectors, sync, enforcement)
│   ├── relay/          # Go: outbox relay + replay CLI
│   ├── workers/        # Go: consumers, schedulers, reconcilers
│   ├── engine/         # Rust: EVL (axum service + property tests + fuzz corpus)
│   ├── docs-worker/    # Node: DOC PDF rendering
│   └── web/            # Next.js monorepo: td/, adm/, con/, cms/, shared/
├── packages/
│   ├── go-shared/      # envelope, errors, db guard, events pub/sub, ids, money
│   └── web-shared/     # api client (generated from OpenAPI), design system, i18n
├── contracts/          # MIRROR of /home/user/alpha-one/contracts (single source, synced)
├── infra/
│   ├── compose/        # docker-compose.{dev,staging,prod}.yml, .env.sops
│   ├── migrations/     # golang-migrate (numbered, both up+down)
│   └── ci/             # GitHub Actions workflows
└── ops/
    ├── runbooks/       # per-incident-type runbook (see 06-devops-deployment)
    └── dr/             # DR scripts + drill records
```

## 10. Extension points (how the platform grows without rewrites)

| Extension | Mechanism (designed in V1) |
|---|---|
| New broker platform (MT4/cTrader) | BRG connector interface (BRG-01) + capability declaration (BRG-04); contract test suite (BRG-43) |
| New payment rail | CHK provider adapter (CHK-04) + provider registry table; no checkout code changes |
| New KYC provider | KYC provider adapter (KYC-04); Veriff is one instance |
| New notification channel | NOT channel driver (email/in-app are V1; telegram/whatsapp = driver + template) |
| New rule type | EVL rule pack schema (versioned) — rule packs are data, not code; engine interprets |
| New tenant plan/entitlement | Flipt flag + TEN entitlement row; GW gate reads entitlements — no deploy |
| Sub-tenants (V2+) | `tenants.parent_id` + resolution chain; ADR-2 keeps the door open |
| Multi-region (V3+) | Read replicas + regional edge; event bus remains per-region with cross-region sync (out of V1 scope, schema must not forbid) |
| SaaS self-serve signup | TEN + BIL (V3): checkout-for-tenants reuses CHK provider adapters |

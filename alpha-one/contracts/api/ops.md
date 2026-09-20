# Ops & Deployment Contract (OPS)

Status: DRAFT
Owner: TBD
Version: v1
Last updated: 2026-09-20

Derived from the V1 Execution Sheet (V1.0 only). Nothing here is final until contract freeze.

## No HTTP surface in V1
OPS is platform infrastructure: containerization (OPS-01), Compose orchestration (OPS-02), CI/CD (OPS-03, OPS-04), migrations (OPS-06), backups (OPS-07, OPS-38), secrets (OPS-09), connection pooling (OPS-25), Redis durability (OPS-26), image registry (OPS-36), resource limits (OPS-37). This module has no HTTP contract in V1 — see module spec later.

## What it provides instead (internal contracts)

### Services (OPS-01, OPS-02)
All services run as Docker images built in CI: api, workers, relay, bot, frontends — the service lanes used in `contracts/diagrams/lanes.md`. Production is a Docker Compose stack on Hetzner (BVR-10: no Kubernetes in V1).

Resolved 2026-09-17: **there is no `bot` lane in V1.** OPS-01's `bot` reference is a stale forward reference to the V2 Telegram bot worker (NOT-09, V2.0; NOT-10 linking likewise V2). The V1 service topology is `api`, `workers` (8 logical lanes per `contracts/diagrams/lanes.md`), `docs-worker`, `bridge`, `engine`, `relay`, plus the frontends and data services — container inventory in docs/06 §2.2. The `worker-realtime`/`worker-batch` naming belongs to OPS-16 (V2.0 row) and is not the V1 topology. NOT runs email + in-app channels in V1 (NOT-01); Telegram is deferred to V2.

### CI/CD (OPS-03, OPS-04)
Every push runs lint, typecheck, unit tests, image build (GitHub Actions), plus gitleaks, dependency scan, and the contract gates (docs/99 0.2/0.10: error registry, 31 catalog, 32 schema). Merge to main deploys staging automatically; production requires manual approval. Production deploys roll two api replicas (D58) — no stop-the-world.

### Migrations (OPS-06)
Versioned migrations with expand-contract discipline: **golang-migrate** (both up/down files mandatory, single runner, advisory lock — docs/06 §2.3); data access via **sqlc** codegen (docs/99 0.4). All `contracts/data/schemas/*.sql` are delivered through this process. BVR-08's Drizzle/Prisma preference predates the Go/Rust stack (ADR-9) and has no V1 surface — superseded for backend services (docs/56, docs/34).

### Backups (OPS-07, OPS-38)
pgBackRest (D55): continuous WAL (`archive_timeout` 5 min, failure alerts) + nightly base; 3-2-1 copies (prod + standby host + off-provider delete-protected object store). Warm standby on a second prod-class host — promote ≤ 15 min (D56). Weekly automated restore verification + monthly full drill (D59).

### Secrets (OPS-09, BVR-06/21)
SOPS + age. Secrets out of code, injected at runtime. TEN-12 depends on this for tenant integration secrets.

### Data services (OPS-25, OPS-26, OPS-36, OPS-37)
PgBouncer pooling per service; Redis 7.2 as **three containers per D51** (docs/06 §2.6): `redis-main` sessions/deny-set/rate-counters/idempotency-claims (AOF everysec, noeviction), `redis-streams` (AOF everysec, noeviction, MAXLEN), `redis-cache` (allkeys-lru). Immutable image tags (commit sha) with env moving tags; explicit CPU/memory limits per container.

## Events emitted/consumed
- None. OPS emits no domain events in the V1 sheet.

## Open contract questions
- Resolved 2026-09-17: lane inventory — no `bot` lane in V1; V1 lanes are api, worker-realtime, worker-batch, outbox-relay (+ frontends); OPS-01's `bot` is a V2 forward reference (NOT-09). Remaining parameter: exact container counts/names per lane (deployment config, not contract).
- Resolved 2026-09-20 (D53, docs/56): migration PRs need **two approvals** — DevOps owns the process (CI dry-run, both-files rule, rollback note) and BE-1 owns the schema content (types, indexes, tenant rules).
- Resolved 2026-09-20: RPO ≤ 5 min / RTO ≤ 2 h per docs/06 §2.4 — the monthly drill measures and files both.
- Resolved 2026-09-20: headroom = 16 GB RAM + 1 TB disk reserved (docs/06 §2.2); per-service limits per the §2.2 table.

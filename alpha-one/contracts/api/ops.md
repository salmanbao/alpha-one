# Ops & Deployment Contract (OPS)

Status: DRAFT
Owner: TBD
Version: v1
Last updated: 2026-09-17

Derived from the V1 Execution Sheet (V1.0 only). Nothing here is final until contract freeze.

## No HTTP surface in V1
OPS is platform infrastructure: containerization (OPS-01), Compose orchestration (OPS-02), CI/CD (OPS-03, OPS-04), migrations (OPS-06), backups (OPS-07, OPS-38), secrets (OPS-09), connection pooling (OPS-25), Redis durability (OPS-26), image registry (OPS-36), resource limits (OPS-37). This module has no HTTP contract in V1 — see module spec later.

## What it provides instead (internal contracts)

### Services (OPS-01, OPS-02)
All services run as Docker images built in CI: api, workers, relay, bot, frontends — the service lanes used in `contracts/diagrams/lanes.md`. Production is a Docker Compose stack on Hetzner (BVR-10: no Kubernetes in V1).

Resolved 2026-09-17: **there is no `bot` lane in V1.** OPS-01's `bot` reference is a stale forward reference to the V2 Telegram bot worker (NOT-09, V2.0; NOT-10 linking likewise V2). The V1 worker topology is `api`, `worker-realtime`, `worker-batch`, `outbox-relay` (naming per OPS-16, which is itself a V2.0 row; V1 workers are the worker lanes enumerated in `contracts/diagrams/lanes.md`). NOT runs email + in-app channels in V1 (NOT-01); Telegram is deferred to V2.

### CI/CD (OPS-03, OPS-04)
Every push runs lint, typecheck, unit tests, image build (GitHub Actions). Merge to main deploys staging automatically; production requires manual approval.

### Migrations (OPS-06)
Versioned migrations with expand-contract discipline. Drizzle ORM primary; Prisma fallback only (BVR-08). All `contracts/data/schemas/*.sql` are delivered through this process.

### Backups (OPS-07, OPS-38)
Daily Postgres backups plus WAL archiving; monthly restore rehearsal; scheduled automated restore verification to a scratch environment with alerting on failure.

### Secrets (OPS-09, BVR-06/21)
SOPS + age. Secrets out of code, injected at runtime. TEN-12 depends on this for tenant integration secrets.

### Data services (OPS-25, OPS-26, OPS-36, OPS-37)
PgBouncer pooling per service; Redis 7.2 with AOF for Streams and eviction for cache; immutable image tags (commit sha) with env moving tags; explicit CPU/memory limits per container.

## Events emitted/consumed
- None. OPS emits no domain events in the V1 sheet.

## Open contract questions
- Resolved 2026-09-17: lane inventory — no `bot` lane in V1; V1 lanes are api, worker-realtime, worker-batch, outbox-relay (+ frontends); OPS-01's `bot` is a V2 forward reference (NOT-09). Remaining parameter: exact container counts/names per lane (deployment config, not contract).
- TODO — needs owner decision: migration tooling ownership split between OPS-06 and module schemas (who reviews expand-contract PRs).
- TODO — needs owner decision: backup RTO/RPO numbers for OPS-38 verification.
- TODO — needs owner decision: host capacity headroom numbers for OPS-37.

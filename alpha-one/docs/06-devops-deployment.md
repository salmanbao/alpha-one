# 06 — OPS: DevOps & Deployment

> Covers PRD module **OPS** (40 requirements). The single server, the pipelines,
> the backups, and the rules that keep a 1-person DevOps sane. This document is
> binding infrastructure policy: if it's not here, it's not allowed in prod.

## 1. Purpose & scope

OPS owns: infrastructure (Hetzner + Docker Compose), CI/CD (GitHub Actions),
environments (dev/staging/prod parity), migrations, secrets (SOPS+age), backups &
DR, observability, alerting, and incident process. **Everything else in the
platform runs on what this document defines** — ADR-9/10 are its anchor.

Requirement coverage: `OPS-01,02,03,04,06,07,09,25,26,36,37,38` (V1.0) +
`05,08,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,27,28,29,30,31,32,33,34,35,39,40` (V2.0) — the V2 list is the ops-hardening phase.

## 2. Architecture

```
 GitHub ──push/PR──► GitHub Actions (signed)
                      ├── lint (golangci-lint, eslint, buf) + unit tests
                      ├── build images (GHCR: OPS-36) — go/rust/node per service
                      ├── migrate (dry-run against throwaway PG)
                      └── deploy (SSH → prod/staging host):
                           1. sops -d .env.sops → .env (never logged)
                           2. docker compose pull (tag = git sha, immutable)
                           3. docker compose up -d (rolling: new → health → old down)
                           4. migrate up (golang-migrate, single runner, advisory lock)
                           5. smoke: /readyz + one internal canary request
```

### 2.1 Environments

| Env | Host | Data | Purpose |
|---|---|---|---|
| `dev` | laptops (Compose) | synthetic (make fixture) | daily dev |
| `staging` | Hetzner CX32 (2nd box) | **synthetic-only** (PRD decision: yes to synthetic-only staging) + staging broker sandbox (MetaApi demo server, OPS-19 V2) | pre-prod, cutover dress rehearsal |
| `prod` | Hetzner **AX42** (4×AMD EPYC, 64 GB RAM, 2×1 TB NVMe) | real | FunderBlu live |

**Parity rule (OPS-05):** one Compose file family + env files; staging and prod
differ only in `.env` values and host resources. Any config key not in both
envs' files fails CI.

### 2.2 Service resource limits (OPS-37, compose `deploy.resources`)

| Service | CPU | Mem (limit) | Notes |
|---|---|---|---|
| api | 2 | 4 GB | 2 replicas V2 |
| bridge | 1.5 | 2 GB | MetaApi-bound, not CPU-bound |
| engine | 1 | 1 GB | Rust, tight |
| relay | 0.5 | 512 MB | exactly 1 |
| workers | 2 | 4 GB | consumers + schedulers |
| docs-worker | 1 | 2 GB | Puppeteer is hungry |
| web | 1.5 | 2 GB | Next.js SSR |
| db (PG) | 6 | 24 GB | `shared_buffers` 6 GB, `work_mem` bounded |
| redis | 1 | 8 GB | maxmemory 6 GB, `allkeys-lru` on the `cache:*` DB only (see 2.6) |
| hook0/flipt/observability | 1 | 2 GB | — |

**V1 lane inventory (binding, `contracts/diagrams/lanes.md`, rendered PNG
alongside):** edge (Cloudflare: DNS + WAF + tenant resolution input) → api
(in-app middleware: GW-02/03/04/05/12) → workers (8 lanes: **sync** BRG-07/08,
**evaluation** EVL-05, **enforcement** BRG-10/EVT-20, **notifications** NOT-01,
**documents** DOC-04, **provisioning** LCC-05/06, **ledger postings**
LED-04/07/08, **analytics** ANA-01) → relay (outbox relay, EVT-02) → frontends
(trader portal TD, admin panel ADM, platform console CON).

> Resolved 2026-09-17 (from the research): **no `bot` lane in V1** — OPS-01's
> `bot` reference is a stale forward reference to the V2 Telegram bot worker
> (NOT-09, V2.0; NOT-10 likewise V2). NOT runs email + in-app channels in V1;
> Telegram is deferred.

Host headroom: 16 GB + 1 TB free disk reserved. `nofile` 65536 on db.

### 2.3 Migrations (OPS-06)

- golang-migrate, `infra/migrations/NNNN_name.{up,down}.sql`, **both files
  mandatory** (CI rejects up-only).
- Applied by a one-shot compose service (`migrate`) — never by app containers
  (app sees "migrations current" via `/readyz` checking schema version).
- Rules: expand → migrate → contract (no destructive down in prod; contract is a
  later, separately-reviewed step); long transactions forbidden (single-statement
  DDL where possible; `CONCURRENTLY` indexes with a lock-wait guard).
- Every migration has a companion note in the PR (what it touches, rollback path).
- `migrate version` is reported in `/readyz`; deploy is blocked on drift.

### 2.4 Backups & DR (OPS-07, OPS-38, ADR-10)

| Item | Mechanism | Target |
|---|---|---|
| PG WAL | `archive_command` → rsync to 2nd Hetzner box (S3-compatible object store), continuous | **RPO ≤ 5 min** |
| PG base backup | `pg_basebackup` nightly 03:00 UTC → same remote, encrypted at rest (SSE + age on key) | verified, not assumed |
| **Backup integrity** (OPS-38) | monthly **restore drill**: base + WAL → scratch instance on staging host → run integrity suite (row counts on 12 key tables, ledger balance check, audit chain spot-check) → report filed in CON; drill failure = P1 incident | **RTO ≤ 2 h** (documented runbook + rehearsed) |
| R2 | versioning enabled on the tenant-docs bucket; cross-region replication off in V1 (single region, nightly object manifest backup to the remote box) | docs restorable to last night |
| Redis | AOF `everysec` (OPS-26) + `maxmemory-policy noeviction` on sessions/streams DBs, `allkeys-lru` only on the cache DB | streams rebuildable from `events` table (Redis is transport, not truth) |
| Config/secrets | repo (SOPS) is the source of truth; age keys on 2 offline locations + 1 host | rotation = PR |
| Compose/state | declarative; `docker compose config` reproducible from git sha | redeploy = pull + up |

DR runbook (`ops/dr/runbook.md`, V2 OPS-22): 5 sections — *detect (who notices),
assess (WAL lag check), restore (exact commands), verify (integrity suite),
declare (status update template)*.

### 2.5 Secrets (OPS-09, ADR-3)

SOPS + age: `infra/env/{dev,staging,prod}.env.sops` in repo; age public keys:
staging host, prod host, 2 team members. Deploy decrypts in-memory to
`/run/alpha-one/.env` (0600, tmpfs) — never on disk outside tmpfs, never in logs
(CI redaction + log-scanner test). Provider secrets (MetaApi, Veriff, NOWPayments,
Match2Pay, Interkasa, Postmark, Sentry, R2, Cloudflare) all live here.
Rotation: per-provider calendar in `ops/secrets.md` (MetaApi/CF quarterly,
provider keys on any personnel change). **Infisical is the V2 upgrade path**
(register) — SOPS is sufficient at V1 scale.

### 2.6 Redis durability & eviction (OPS-26)

Three logical DBs (separate key prefixes + `SELECT`): `0` sessions/deny-set
(AOF, noeviction), `1` streams (AOF, noeviction, MAXLEN per stream), `2` cache
(allkeys-lru). Misconfigured eviction of a session key = forced re-login (safe);
eviction of a stream = data loss (therefore noeviction + capacity alert at 80%).

## 3. System design (deploy mechanics)

### 3.1 Zero-downtime deploys (V2 OPS-18; V1 = acceptable 10 s window)

V1 reality: `compose up -d` with healthchecks — Go services drain connections
(SIGTERM handler, 30 s grace). V2 adds: blue-green `api` (two tagged stacks,
`up -d api-green` → canary → `rm api-blue`) + migrate-before-deploy ordering
(backend-compatible-first rule: **additive migrations land in the release before
the code that needs them**).

### 3.2 Rollback (V2 OPS-30)

`deploy rollback --to <sha>`: pull previous image tag, `up -d`, run `migrate
down` **only** if the failed release owned the migration (else manual). Rollback
is a rehearsed part of the monthly drill.

### 3.3 Access control (V2 OPS-20)

Prod host: SSH key per team member (rotated quarterly) + Tailscale-only access
(no public SSH port); UFW default-deny, in: 80/443 (Cloudflare origin rules
restrict to CF ranges — OPS-15), Tailscale subnet. No database port exposed
outside the Docker network. Root SSH disabled; sudoers per task.

### 3.4 Job scheduling & single-execution (OPS-17, OPS-27)

Workers own all cron (no `pg_cron`, no host crontab): each job declares
`{name, cron, lock_key, timeout}`; execution takes `SELECT pg_try_advisory_lock`
→ exactly one instance runs (safe when workers scale to 2). Jobs: day-boundary
rollover (EVL), sync gap scanner (BRG), reconciliation (LED/PAY), read-model
refresh (ANA), outbox pruning (EVT), backup integrity check, retention purges
(AUD/KYC docs), usage metering flush (TEN), relay watchdog.

## 4. Events

OPS does not produce domain events. It produces **operational** signals:
`ops.deploy_started/succeeded/failed`, `ops.backup_completed/failed`,
`ops.restore_drill_completed` → CON (internal dashboard) + NOT (staff channel).
Provider health (MetaApi/Veriff) → `ops.provider_health` (feeds BRG-16 V2).

## 5. Lifecycles

- **Release:** `built (GHCR tag=sha) → promoted (staging) → deployed (prod) →
  rolled-forward | rolled-back (≤ <sha>)` — immutable tags, no `latest` in
  compose files (CI lints for it).
- **Backup:** `taken → verified (weekly checksum) → (monthly) restored-and-tested
  → (90 d) pruned (base) / (7 d) WAL segment rotation`.
- **Secret:** `created (PR) → active → rotated (PR) → retired (90 d)`.
- **Incident:** `detected (alert) → triaged (P1–P3) → mitigated → resolved →
  post-mortem (P1/P2 within 48 h, blameless, in repo `ops/incidents/`)`.

## 6. Error taxonomy

OPS errors surface as infra conditions, not client errors. Client-visible:
`sys.maintenance` (503, GW-32), `sys.degraded` (200 + `X-Service: degraded`
header on affected reads). Internal condition codes (metrics/alerts):
`ops.migration_failed`, `ops.backup_failed`, `ops.backup_unverified`,
`ops.restore_drill_failed`, `ops.relay_down`, `ops.disk_full_80`,
`ops.redis_mem_80`, `ops.cert_expiring_14d` (OPS-35), `ops.provider_degraded`.

## 7. API endpoints
### 7.1 V1 baseline — `ops` (see `contracts/api/ops.md`)

**No HTTP surface in V1** — this is an internal/service contract. The internal contracts (what other modules call, what workers run, what is enforced) are in `contracts/api/ops.md`.

### 7.2 Extended (post-V1) surface — provisional

> Not in the V1 execution sheet. Design-level; paths beyond the V1 baseline are provisional until the URL-plan decision (`contracts/api/gw.md`, open question). Shown for platform completeness (V2/V3 phases, docs/99).

Console-only (no tenant surface):

- `GET /v1/console/ops/health` — per-service health plus PG, Redis, relay, and disk status.
- `GET /v1/console/ops/backups` — backup history plus the last restore-drill report.
- `POST /v1/console/ops/backups/verify` — trigger a manual backup checksum verification.
- `GET /v1/console/ops/costs` — V2 OPS-23: Hetzner spend plus provider usage from the BRG-47 foundation.
- `GET /v1/console/ops/slos` — V2 OPS-40: SLO definitions and current compliance.

Liveness/readiness probes (GW-14) are owned by the gateway — see 04 §3.6; they ship in the 04 spec, not here.
## 8. Schema

No tenant-owned tables. Platform tables: `backups` (id, kind, taken_at,
size_bytes, checksum, verified_at, drill_report JSONB), `incidents` (id,
severity, title, started_at, resolved_at, post_mortem_url), `deploys` (id,
env, sha, started_at, finished_at, status, actor), `slo_defs` (V2). All in the
platform schema (no tenant_id).

## 9. Database design

See §8 — trivial size; the only index that matters:
`backups(kind, taken_at DESC)`.

## 10. Security & compliance

- Origin protection (OPS-15): Cloudflare **orange-cloud only**; direct-origin
  access blocked (CF rule + UFW to CF IP ranges). TLS 1.3, HSTS at edge.
- Image hygiene (OPS-14): distroless/alpine bases, non-root users, Trivy scan in
  CI (block on critical), no `latest`, layer pinning.
- Host hardening (OPS-13, V2): fail2ban, unattended-upgrades (security only),
  auditd, no world-writable paths.
- Production data: **never** in dev/staging (synthetic-only rule); any
  "production-like" dataset request requires legal + CON sign-off (and is
  anonymized before it leaves prod — AUD-12 mechanism).
- Log retention & access (OPS-32, V2): Loki 30 d hot (V2 stack), structured
  JSON, PII redaction same rules as AUD §9; access via Tailscale-only Grafana.

## 11. Scalability considerations

V1 single-box budget (AX42): PG 24 GB + Redis 8 GB leaves ~32 GB for compute —
comfortable at 10× V1 targets. When to scale (written thresholds, not vibes):
- PG `max_connections` pressure sustained > 70% (PgBouncer absorbs; alert)
- disk > 70% (WAL + events partitions)
- bridge poll backlog > 2 min (add bridge replica — stateless)
- single box → 2 boxes: `api+web` box / `db+redis` box is the V2 first split
  (OPS-33 failover strategy doc); K8s remains forbidden (revisit only at > 50
  tenants or multi-region).

## 12. Open-source solutions

| Tool | Role |
|---|---|
| **Docker Compose** | orchestration (ADR-9) |
| **golang-migrate** | migrations |
| **SOPS + age** | secrets (ADR-3) |
| **GHCR + GitHub Actions** | registry + CI/CD (PRD signed) |
| **PgBouncer** | connection pooling (ADR-8) |
| **Prometheus + Grafana** | V1 metrics/dashboards (Loki + OTel V2 register) |
| **Uptime Kuma** | external uptime (OPS-31) |
| **Trivy** | image scanning |
| **Tailscale** | private access (ops plane) |
| **restic** (or bare rsync + age) | backup transport/encryption |

## 13. Technology stack

Shell + Compose + Go (one-shot services), GitHub Actions, GHCR, Hetzner Cloud
API (provisioning, cost queries), SOPS/age, Prometheus/Grafana/Uptime Kuma/
Trivy, Tailscale, restic.

## 14. Integration — internal modules (glue)

- **Every service**: resource limits, healthchecks, SIGTERM drain, structured
  logging format (01 §4 envelope applies to ops logs too: `tenant_id`,
  `correlation_id`).
- **GW**: `/readyz` includes relay lag — the deploy smoke test uses it.
- **CON**: ops health/backup/drill/cost screens (this module's API feeds them).
- **EVT**: relay watchdog job; DLQ depth alerting.
- **BRG**: staging broker sandbox (OPS-19) gives the bridge a MetaApi demo
  account farm for integration tests.
- **MIG**: cutover uses the deploy pipeline's staging↔prod patterns verbatim
  (rehearsed 2× before FunderBlu cutover).

## 15. Integration — external tools

Hetzner (hosts, object storage), GitHub Actions/GHCR (signed), Cloudflare (DNS,
origin rules, cert bot for custom domains — OPS-35 expiry monitor), Sentry,
Uptime Kuma, Postmark (staff alerts via NOT), provider consoles (manual
cost tracking until BRG-47/OPS-23 automate it).

## 16. Implementation blueprint

| Step | Owner | Est | Depends | Exit criteria |
|---|---|---|---|---|
| 1. Prod host provision + hardening baseline + Tailscale + UFW/origin rules | DevOps | 2 d | — | CF-only origin access verified |
| 2. Compose files (dev/staging/prod) + all V1 services + resource limits + healthchecks | DevOps | 3 d | 1 | `make deploy-staging` green from a clean box |
| 3. CI: lint+test+build+GHCR+staging deploy workflow; migration dry-run gate | DevOps + BE-1 | 3 d | 2 | PR → staging deploy fully automatic |
| 4. Migrations framework + first schema set + version gate in /readyz | BE-1 + DevOps | 2 d | 2 | drift blocks deploy |
| 5. Backups: WAL archiving + nightly base + remote box + weekly checksum verify | DevOps | 2 d | 2 | restore from base+WAL into scratch PG succeeds |
| 6. **First restore drill** (full integrity suite) + runbook v1 | DevOps | 2 d | 5 | drill report filed; RTO measured ≤ 2 h |
| 7. SOPS secrets rollout (all providers) + rotation calendar + CI redaction test | DevOps | 1.5 d | 1 | no plaintext secret anywhere in repo/logs (scan clean) |
| 8. Prometheus + Grafana (service/PG/Redis/relay/dashboards) + alert routing v1 | DevOps | 3 d | 2 | alert fires on induced relay stop |
| 9. Prod deploy + smoke + Uptime Kuma + Sentry wired | DevOps | 1 d | 2–8 | platform live on prod host |
| 10. V2 hardening phase (OPS-05,08,10–14,16,18–24,27–35,39,40): zero-downtime, rollback rehearsal, load test (OPS-29: k6 scripts in repo), SLOs, log retention, cost dashboard, incident process | DevOps + all | 3 wks | 9 | load test at 10× targets green; SLO dashboards live |

**Risks:** single-box SPOF (accepted V1, ADR-9/10, with rehearsed DR + RPO 5
min); deploy window (V1 accepts 10 s, documented in status template); backup
"trust but verify" (OPS-38 makes verification a first-class, drilled job).

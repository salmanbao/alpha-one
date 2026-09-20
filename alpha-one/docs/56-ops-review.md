# 56 — OPS: DevOps & Deployment — The Platform Under Everything (fifteenth pass)

> The fifteenth completeness pass reviews **docs/06 (OPS)** — the module every
> other reviewed module stands on: the single server, the pipelines, the
> backups, the secrets, the Redis, the alerts. docs/06 had already absorbed
> fixes from the identity reviews (G39/G43/G45), so this pass found fewer
> loose rows than earlier passes — but it found **one impossible design**
> (the Redis topology), **one code-naming conflict** that would fail the
> error-registry gate, **a self-contradiction inside the binding identity
> doc**, **three stale contract TODOs**, and **a three-way tier conflict**
> over which tools ship in V1. The owner ruled via four decisions
> (**D51–D54**); everything else was mechanical and fixed in place.

Status: REVIEW — decisions D51–D54 recorded, mechanical fixes applied
Owner: TBD (DevOps + Platform)
Version: v1
Last updated: 2026-09-20

---

## 1. Scope & method

- **Module:** docs/06 (OPS, 40 requirements — 12 V1.0: OPS-01/02/03/04/06/07/09/25/26/36/37/38; the V2 list is the ops-hardening phase).
- **Cross-checked against:** docs/02 (token/deny-set numbers), docs/04 (GW-14 probes, `gw.maintenance`, Prometheus mentions), docs/29 (scale posture), docs/31 (event catalog — harvested from module §4s), docs/32 (schema — harvested from module SQL blocks), docs/34 (tooling registry, BVR-08, Hook0), docs/55 (the GW solution spec), docs/99 (Phase 0 build plan), contracts/api/ops.md, contracts/diagrams/lanes.md, `contracts/errors/taxonomy.md`.
- **Method** = every prior pass: read the module end to end; verify every number, code, event, table and tool against its citing/cited doc; classify each finding **mechanical** (enforces already-binding text — fixed silently) or **design** (owner decides via multiple choice).

## 2. What the review validated (no action needed)

- **Backups/DR (OPS-07/38):** RPO ≤ 5 min / RTO ≤ 2 h, nightly base + WAL, monthly restore drill with a real integrity suite (row counts, ledger balance, audit chain spot-check, IdP-link check + login smoke) — internally consistent, and docs/48 makes no competing numbers. The ZITADEL DB rides the same ritual with the master key stored separately.
Session restore (D64, docs/59): browser sessions are PG rows (`auth_sessions`),
so a restored DB repopulates all three realms' cookies (trader, staff, console);
the redis-main session keys are an acceleration layer, not truth.
- **Secrets (OPS-09):** SOPS+age, tmpfs-only decrypt, CI redaction test, rotation calendar; TEN-11/12 dependency intact; Infisical correctly parked as the V2 path.
- **Migrations (OPS-06):** both-files mandatory, expand→migrate→contract, no destructive down, version gate in `/readyz`, ZITADEL's one-way event-sourced migrations correctly excluded from golang-migrate with a deploy order.
- **Auth posture (§3.5):** the login-outage asymmetry is stated as a decision; the numbers match docs/02 §9 and docs/43 (JWKS 24 h + refresh-on-unknown-kid; revocation p95 ≤ 60 s; `IdpSyncStalled` pages at 5 min).
- **Runbooks (§3.6):** staff on/offboarding, quarterly access review (G39), IdP break-glass, deny-set drill (docs/99 gate 10) — all present and rehearsed-shaped.
- **Single-box posture:** resource limits (§2.2), the scale-out thresholds (§11), and the K8s-forbidden rule are consistent with docs/29 and BVR-10/ADR-9.

## 3. Findings

| # | Finding | Class | Resolution |
|---|---|---|---|
| F1 | **Redis topology impossible (§2.6):** one instance, three logical DBs, per-DB eviction policies — Redis policy + `maxmemory` are instance-wide; a full cache could evict sessions or idempotency claims. Also: the GW chain (docs/55) had no named home for rate counters + idempotency claims | **Design** | **D51** — three containers (`redis-main` / `redis-streams` / `redis-cache`); claims + counters on `redis-main`; §2.6 rewritten; §2.2 resource row split |
| F2 | **Unregistered codes (§6):** `sys.maintenance` (registered name is `gw.maintenance`, docs/04 §6.2) and `sys.degraded` (registered nowhere) — both would fail `error_registry_test`; and a degraded 200 has no field a code could occupy under the binding D45 envelope | **Design** | **D52** — `gw.maintenance` adopted; degraded = `X-Service: degraded` header convention, no code; §6 rewritten |
| F3 | **docs/02 self-contradiction:** the deny-set TTL is "24 h" in §3.3 prose but "jti = access-token TTL; session-keyed entries outlive the refresh idle window" in the §9 parameter block (G12/D10) | Mechanical | docs/02 §3.3 harmonized to the §9 split rule (the refined, reviewed formulation); docs/55's deny-set row conformed to it |
| F4 | **docs/55 deviated from binding numbers:** JWKS cache "15 min" (docs/02 §9 binds **24 h** + refresh-on-unknown-kid); deny-set "24 h" flat | Mechanical | docs/55 §3.4 rows corrected to the docs/02 numbers (spec follows binding) |
| F5 | **ops.md ORM line stale:** "Drizzle ORM primary; Prisma fallback (BVR-08)" — a TS ORM on a Go/Rust backend that uses golang-migrate + sqlc (docs/99 0.4); docs/34 still had "Drizzle adopt (Phase 0)" open | Mechanical | ops.md aligned to golang-migrate + sqlc; docs/34 BVR-08 annotated superseded-for-backend; the Phase-0 checklist item closed as N/A |
| F6 | **ops.md worker topology stale:** "api, worker-realtime, worker-batch, outbox-relay" vs lanes.md ("api, workers, relay") and docs/06 §2.2's container inventory | Mechanical | ops.md states the lanes.md topology + points at docs/06 §2.2; `worker-realtime`/`worker-batch` tagged as OPS-16 (V2) naming |
| F7 | **ops.md CI list narrow:** "lint, typecheck, unit tests, image build" vs docs/99 0.2 (gitleaks, dep-scan) and 0.10 (contract gates) | Mechanical | ops.md + docs/06 §2 pipeline diagram now list gitleaks, dep-scan, and the three contract gates |
| F8 | **ops events invisible to the catalog:** docs/06 §4 listed `ops.deploy_*`/`ops.backup_*`/`ops.restore_drill_completed`/`ops.provider_health` in prose — the docs/31 harvester reads §4 tables, so none were registered (`ops.provider_health` got in only via docs/08's table) | Mechanical | §4 reformatted into the 4.1/4.2 table structure; docs/31 now carries the ops signals (ext) |
| F9 | **Three stale ops.md TODOs:** migration-review ownership (real open question); RTO/RPO numbers (already answered by docs/06 §2.4); host headroom (already answered by §2.2) | 1 × Design + 2 × Mechanical | **D53** — dual approval (DevOps process + BE-1 content); the other two resolved citing their answer texts |
| F10 | **Tier conflict on three tools:** Hook0 (docs/99 0.3/0.7 build+test it vs docs/34 "EVT-11/13/14/15 (V2.0)"); Prometheus/Grafana (docs/06 §16 step 8 + docs/04's `relay.lag`/DLQ metrics vs docs/99 0.9 "observability stack V2"); Uptime Kuma (docs/06 §16 step 9 vs OPS-31 V2) | **Design** | **D54** — Hook0 + minimal Prometheus/Grafana (the four binding metrics) in V1; Uptime Kuma + full stack V2; docs/06 §2.2/§12/§15/§16 and docs/34 aligned |
| F11 | **V2 rows quoted as V1 practice:** parity rule (OPS-05), job scheduling (OPS-17/27), DR runbook (OPS-22), load scripts (OPS-29) — the practices are V1-necessary but the rows are V2-tier | Mechanical | docs/06 texts re-tagged: "V1 practice; OPS-NN productizes in V2" — no PRD row touched |
| F12 | **Platform tables had no DDL:** `backups`, `incidents`, `deploys` named in docs/06 §8 but absent from docs/32's count | Mechanical | DDL block added to docs/06 §8 (docs/32: 125 → 128 tables) |
| F13 | **Stale §7.2 note:** "provisional until the URL-plan decision (open question)" — the URL plan was resolved (D46, docs/54) | Mechanical | Note cites D46; paths conform to `/v1/console/*` |
| F14 | **`/readyz` contract gap:** docs/06 §2.3 reports the migration version and blocks deploys on drift; docs/04's GW-14 row didn't list it | Mechanical | docs/04 GW-14 row extended with the citation |

## 4. Decisions (full texts in the register)

- **D51 (Redis):** three containers — `redis-main` (sessions, deny-set, GW rate counters, idempotency claims; AOF `everysec`, `noeviction`), `redis-streams` (AOF `everysec`, `noeviction`, `MAXLEN`), `redis-cache` (`allkeys-lru`, no persistence). Money-adjacent state never shares an eviction domain with the cache.
- **D52 (codes):** `gw.maintenance` (503) is the only maintenance code; degraded reads are the `X-Service: degraded` **header** on an otherwise normal D45 200 — no code exists or will be registered. The taxonomy registers envelope codes only.
- **D53 (migrations):** every migration PR carries the docs/06 §2.3 companion note and needs **two approvals** — DevOps (process: CI dry-run, both-files rule, rollback path) and BE-1 (content: types, indexes, tenant rules).
- **D54 (V1 tool tiers):** Hook0 ships in V1 (docs/99 0.3/0.7 are binding; the EVT-11/13/14/15 V2 rows describe the *productized per-tenant surface*, not the pipeline); minimal Prometheus+Grafana ships in V1 for the four binding metrics (`relay.lag`, DLQ depth, disk, redis-mem — docs/04 assumes them); Uptime Kuma (OPS-31) and the full observability stack (Loki/OTel/dashboards, OPS-10/12) stay V2.

## 5. Wiring map (what changed, where)

| File | Change |
|---|---|
| docs/06 | §2 CI diagram (+gitleaks/dep-scan/contract gates); §2.1 parity note; §2.2 redis + hook0/flipt/prometheus rows; §2.4 runbook note; §2.6 rewritten (D51); §3.4 re-tagged; §4 reformatted (catalog harvest); §6 rewritten (D52); §7.2 D46 note; §8 DDL block; §5 placeholder; §12/§15/§16 D54 tags |
| contracts/api/ops.md | golang-migrate+sqlc; lanes topology; CI list; D51 Redis line; all three TODOs resolved (one via D53); date bump |
| docs/02 | §3.3 deny-set phrasing harmonized to the §9 split rule |
| docs/04 | GW-14 `/readyz` row + schema version (docs/06 §2.3) |
| docs/34 | BVR-08 superseded-for-backend; Drizzle tool row + Phase-0 checklist closed; Hook0 row → ADOPT (V1 pipeline, D54) |
| docs/55 | JWKS 24 h; deny-set split TTL; counters/claims → `redis-main`; durability note cites D51 |
| scripts/design-questions.json | D51–D54 appended (58 entries) |
| docs/30/31/32/37 | regenerated (ops signals in the catalog; 128 tables; D51–D54 rendered) |

## 6. Follow-ups surfaced (not blocking, recorded)

- The cross-cutting freeze audit (docs/28/29/35) remains the last unreviewed cluster; docs/29's §6 prose is dense enough that its load numbers deserve that audit's full attention.
- `ops.provider_health` "feeds BRG-16 (V2)" — confirm BRG-16's text says the same when the surfaces pass runs.
- The monthly drill's integrity suite names "12 key tables" — the list itself should live in the drill runbook (ops/dr/runbook.md) when Phase 0 writes it; docs/06 deliberately keeps only the categories.
- PNG re-renders and the docs/35 §4 strict example-validation gate remain carried follow-ups from earlier passes.

Like docs/42 ff., this pass changes V1 design detail only — **no PRD workbook
row was changed** (the V2-tagged rows that name V1 practices were re-tagged
in the module doc, not in the workbook).

# 57 — OPS vs Industry: The Benchmark Review (sixteenth pass)

> The sixteenth pass takes the fifteenth's finished OPS module
> ([docs/06](06-devops-deployment.md), as corrected by D51–D54) and benchmarks
> it against how professional teams actually run **small money platforms**
> (payments/ledger workloads on 1–3 bare-metal hosts): backup architecture,
> disaster recovery, monitoring blind spots, deploy mechanics, and backup-test
> cadence. Five practices in our spec were **bogus or not implementable as
> written**; the owner chose the industry-standard fix for each — registered
> as **D55–D59**.

Status: REVIEW — benchmark vs industry practice; D55–D59 recorded, wiring applied
Owner: TBD (DevOps + Platform)
Version: v1
Last updated: 2026-09-20

---

## 1. Method

Each claim in docs/06 was tested against the practices a professional
platform team of this scale is expected to run: the **3-2-1 backup rule**
(3 copies, 2 systems, 1 off-provider), purpose-built backup tooling
(pgBackRest/WAL-G vs hand-rolled scripts), **warm standby** replication vs
restore-from-backup recovery, **external** monitoring and dead-man's switches
(the monitor must not die with the monitored), **real** rolling deploys vs
documented fiction, and the **weekly automated restore test** cadence for
money platforms. Where our text promised something the mechanism cannot
deliver, it is listed as bogus — with the industry fix as the MCQ option the
owner picked.

## 2. What already meets the bar (validated, no action)

- Secrets (SOPS+age, tmpfs decrypt, CI redaction test, rotation calendar), migrations discipline (expand→contract, both files, advisory lock, version gate), the auth-outage asymmetry as a stated decision, the incident ladder with blameless post-mortems, host hardening (CF-only origin, Tailscale, no public DB port), resource limits with written scale-out thresholds, and the monthly **human** drill with a real integrity suite — all match or exceed industry practice at this scale.

## 3. The bogus list → the industry fix (owner's choice)

### B1 — The RPO promise was not implementable as written → **D55 (pgBackRest + 3-2-1)**

- **Bogus:** WAL shipped via `archive_command` + rsync with **no
  `archive_timeout`** — Postgres only ships a WAL segment when it fills
  (~16 MB), so a quiet day can go **hours** between ships while the doc
  promises RPO ≤ 5 min. No archive-failure alerting existed, so the promise
  could silently stop being true. And every copy lived at one provider —
  a provider lock-out or a compromised host could touch all of them.
- **Industry fix (chosen):** pgBackRest owns archiving (`archive_timeout`
  5 min, failure alerts), nightly base, retention, encryption, verification.
  Copies follow 3-2-1: prod box + standby host + **off-provider** object
  storage with object lock and separate credentials.

### B2 — Recovery rebuilds from zero while a second host could be a standby → **D56 (warm standby, promote ≤ 15 min)**

- **Bogus (economics):** the DR plan paid full restore cost (RTO ≤ 2 h) for
  every disaster; the industry standard for a money platform is an async
  **streaming replica** on a second host — recovery = promote, minutes.
- **Chosen:** a prod-class standby host runs the warm replica of the whole PG
  cluster (platform + ZITADEL DBs — PG replicates cluster-wide). RTO: promote
  ≤ 15 min primary path; ≤ 2 h full restore remains the documented worst case
  (so docs/99 0.9's bound still holds). **Sizing honesty:** the CX32 staging
  box (4 GB/160 GB) cannot serve as this standby — the option's "no new cost"
  framing is corrected: expect one additional AX42-class host (~€40/mo).

### B3 — The monitor dies with the monitored → **D57 (external checks + dead-man's switches, in V1)**

- **Bogus:** all V1 monitoring ran on the prod box (Prometheus included);
  a dead box reports nothing to anyone. The external uptime checker was
  deferred to V2 by the D54 slice.
- **Chosen:** Uptime Kuma runs on the standby host (outside the prod box) and
  **Healthchecks.io** (off-provider, free tier) provides dead-man's switches:
  backups, cron jobs, and the drill must ping in — silence pages. This
  **supersedes the Uptime-Kuma slice of D54** (the full-stack OPS-10/12 slice
  stands); docs/99 0.9's "not V1" list corrected accordingly.

### B4 — The deploy description was fiction → **D58 (two api replicas, real rolling)**

- **Bogus:** "rolling: new → health → old down" with **one** api container —
  plain `docker compose up -d` recreates a single container in place; the
  real behaviour was the honestly-labelled 10 s stop/start.
- **Chosen:** two api replicas behind the compose-network ingress with a
  deploy cycler (start new → health → drain old with the 30 s SIGTERM grace).
  Same box, real zero-downtime; "2 replicas V2" moves to V1 for api only;
  blue-green two-stack tagging remains V2 (OPS-18).

### B5 — A backup tested once a month → **D59 (weekly automated restore verification)**

- **Bogus (cadence):** between monthly drills a silently broken backup could
  sit undetected up to 30 days — for a ledger, that is a 30-day RPO in the
  worst case.
- **Chosen:** weekly automated restore verification (restore → scratch PG on
  the standby host → `pg_verifybackup` + row-count/ledger-balance subset;
  alert on failure) alongside the monthly full human drill.

## 4. Wiring map

| File | Change |
|---|---|
| docs/06 | §2.1 standby-host row; §2.2 api row (2 replicas V1); §2.4 rewritten (pgBackRest, archive_timeout, 3-2-1, standby, weekly verify, RTO dual number); §2 CI diagram rolling line; §3.1 rewritten (D58); §5 backup lifecycle; §11 second-box note; §12 pgBackRest/Uptime-Kuma/Healthchecks rows; §13/§15 tool lines; §16 steps 5/6/9 |
| contracts/api/ops.md | Backups section (pgBackRest/3-2-1/standby/weekly-verify); deploy line (two-replica rolling); date bump |
| docs/99 | 0.9 "not V1" list corrected (external uptime in V1 — D57); sixteenth-pass sentence |
| scripts/design-questions.json | D55–D59 appended (63 entries) |
| docs/37 | regenerated (D55–D59 rendered) |

## 5. Follow-ups surfaced (recommendations, not decisions)

- **Compose secrets vs env vars:** DB credentials currently ride process env
  (visible via `docker inspect`); moving them to file-based compose secrets is
  a hardening candidate for the Phase-0 compose work.
- **Supply chain:** "GitHub Actions (signed)" should be made concrete — cosign
  image signing + SBOM per service (cheap, industry standard).
- **Sync replication:** consider `synchronous_commit`/sync standby only when
  the second site exists; async is the correct V1 posture (documented RPO
  seconds).

Like every review pass, this changes V1 design detail only — **no PRD workbook
row was changed**.

# 19 — ANA: Analytics & BI

> Covers PRD module **ANA** (36 requirements). The PRD's default "report
> API = NO (CSV export)" and our single-Postgres architecture (ADR) shape
> ANA: it is **event-driven read models in the same Postgres**, not a
> separate warehouse. V1 ships the foundation + the live KPI dashboard;
> the report suite is V2; warehouse/predictive/cross-tenant is V3.

## 1. Purpose & scope

- **Read model foundation (ANA-01, V1):** materialized tables maintained by
  event consumers (the EVT consumer-group pattern, 04 §3.3): fast, denormalized
  queries for TD/ADM without hitting the write-side tables.
- **Real-time KPI dashboard (ANA-32, V1):** the operator's glance screen
  (rendered in ADM): what is live right now, what needs attention.
- **V2 (29):** the report suite (daily ops ANA-02, monthly financial
  ANA-03, challenge performance ANA-04, payout ANA-05, geo ANA-06,
  challenge-vs-payout ANA-07, top earners/loss cohorts ANA-08, funnel
  ANA-09/30, payment analytics ANA-16), delivery (CSV ANA-11, scheduled
  email ANA-12, PDF ANA-27, sharing ANA-35), quality (freshness labels
  ANA-14, **read model reconciliation ANA-21**, **rebuild tool ANA-22**,
  health dashboard ANA-33, KPI definitions registry ANA-23), analysis
  (period comparison ANA-25, drill-down ANA-26, attribution ANA-24/31,
  unit economics ANA-20, LTV/CAC ANA-29, custom KPI alerting ANA-34),
  permissions (ANA-13), operator KPI feed (ANA-10).
- **V3 (5):** retention/cohort (ANA-15), custom report builder (ANA-17),
  **data warehouse integration (ANA-18 — the escape hatch: read-model dump
  to BigQuery when the numbers outgrow PG)**, predictive (ANA-19),
  cross-tenant platform analytics (ANA-28 — platform-ops view only,
  tenant data never mixed).

Requirement coverage: `ANA-01,32` (V1) + `02..14,16,20..31,33..36` (V2) +
`15,17,18,19,28` (V3).

## 2. Architecture

```
 EVT relay (Redis Streams) ──per-entity lanes + standard topics──►
   ANA consumers (in the workers process — the "read-model updater" of 01 §4.3):
     equity_points      ← bridge.tick (per account, 1-min bucket)
     accounts_ro        ← account.state_changed (denormalized account row)
     traders_ro         ← identity + membership events
     payments_daily     ← payments.intent_captured/refund_settled (daily rollup)
     payouts_daily      ← payout.settled/failed (daily rollup)
     funnel_steps       ← kyc.session_started, payments.intent_created,
                           account.funded (per-trader step table)
     risk_summary       ← risk.case_opened/decided (counts + aging)
     kpi_snapshot       ← 30-s materialized view refresh (the dashboard table)
   dashboards (ADM V1; ANA-02/03 V2): read-only SQL against the read models
   exports (V2): async CSV/PDF workers (R2, 24 h URLs) + scheduled email (NOT)
   reconciliation (V2 ANA-21): nightly job compares read models vs source
     (hash of aggregates) → drift = CRITICAL alert + auto-rebuild option
```

**Principles** (committed for V2 quality, honored from V1):
1. **Read models are rebuildable, never authoritative.** Source of truth is
   the write-side tables + the PG `events` log (04 §5.4). Any read model
   row must be recomputable from the log (the ANA-22 rebuild tool is the
   proof — V1 ships the rebuild script for `equity_points` because TD's
   chart depends on it).
2. **Freshness is labeled** (ANA-14 from day 1): every dashboard figure
   carries `as_of`; equity points carry their tick time; a stale read model
   shows "data from {time}", not a wrong-looking current number.
3. **Tenant isolation is structural**: every read model row has `tenant_id`;
   cross-tenant queries are platform-ops role only (V3 ANA-28).

## 3. System design

### 3.1 V1 read models (the foundation)

```
equity_points (account_id PK with as_of index):
  tenant_id · account_id · as_of (1-min bucket) · equity_cents ·
  balance_cents · hwm_cents · tick_at
  -- 1-min buckets; the TD chart reads a day's ~1,440 rows (or the 60 the
  -- SSE appends live); retention 13 months (matches the events log, 04)

accounts_ro:
  tenant_id · account_id PK · identity_id · package · state · phase ·
  opened_at · funded_at · breached_at · broker_account · equity_now ·
  state_changed_at   -- the ADM account list's fast path (17 §2)

traders_ro:
  tenant_id · identity_id PK · name_masked · email_masked · country ·
  kyc_l1_at · kyc_l2_at · created_at · account_count · last_active_at

payments_daily (tenant, date PK-ish):
  intents · captured · gross_cents · fee_cents · refunds · refund_cents
payouts_daily (tenant, date):
  requested · approved · settled · settled_cents · failed · avg_approval_h

funnel_steps (tenant, identity_id, step, at) — append-only:
  step ∈ registered|kyc_started_l1|kyc_verified_l1|intent_created|
         purchased|funded|first_payout
risk_summary (tenant, day):
  open_cases · opened_today · decided_today · hold_cents_active
kpi_snapshot (tenant, as_of 30-s):
  the dashboard's single-row-per-tenant aggregates (see §3.2)
```

All tables: `tenant_id` indexed first, monthly partitions from V2
(only `equity_points` in V1 — it's the volume table: 1,440 rows/account/month
≈ 50M rows/yr at 1k funded accounts → partition by month + 13-mo retention).

### 3.2 V1 KPI dashboard (ANA-32 — in ADM)

One screen, five blocks (all from `kpi_snapshot` + `risk_summary`):
1. **Live**: funded accounts (state=funded), active traders (24 h),
   equity total (Σ equity_now — the "book value"), tick age of the
   feed (the feed's own staleness — if the BRG→ANA lane is down, the
   dashboard says so, not the KPIs).
2. **Today**: purchases (count + gross), payouts settled (count + cents),
   breaches (count — with a link to the accounts).
3. **Queues**: payout pending (age distribution), KYC manual (count),
   risk open (count) — mirrors the ADM queue home but with the 7-day
   trend sparkline.
4. **Providers**: BRG provider health (08: MetaApi up/degraded + last
   sync age per tenant), payment rail circuit states (CHK/PAY),
   relay lag (04: relay's LastSeq vs source).
5. **Alerts**: open CRITICAL/WARN from CON (OPS) — the dashboard is the
   ops room's single wall screen.

Refresh: 30 s (SSE push of the snapshot row; the 30-s refresh job in the
worker computes it).

### 3.3 V2 reports (the suite, all async)

Every report = a **named query over read models** (registry row: name,
params, SQL template, columns, schedule?, permissions) → run → CSV or PDF
(DOC renders) → R2 → email (NOT) or in-ADM link. The report registry is
data (ANA-23's KPI definitions live in it: each column documents its
definition — "settled = payout.state=settled, provider-confirmed; excludes
failed_final").

Key V2 reports (PRD-mapped): daily ops (ANA-02: the dashboard + yesterday
comparison), monthly financial (ANA-03: revenue by package, payout cost,
fee income, net margin — the tenant's P&L, built on LED + payments_daily +
payouts_daily), challenge performance (ANA-04: pass/fail rate, average
time-to-fund, time-to-breach by rule set), payout (ANA-05: volume, avg
approval time, method mix), geo (ANA-06), challenge-vs-payout (ANA-07:
the unit economics of being in business — challenge revenue vs payout
cost per cohort), top earners (ANA-08), funnel (ANA-09/30: the
registered→funded→first-payout conversion with drop-off by step),
payment analytics (ANA-16: rail success rates, fee margins), LTV/CAC
(ANA-29, needs AFF attribution V3 — V2 = internal channels only).

**Unit economics (ANA-20)** is the strategic report: per package:
challenge price × volume − payout cost − provider fees − infra share =
margin; it's the answer to "is FunderBlu making money on Alpha One?" —
scheduled monthly to the COO + owner.

### 3.4 Quality machinery (V2 ANA-21/22/33 — the part that makes reports trustworthy)

- **Reconciliation (ANA-21):** nightly: for each read model, compare
  aggregate hashes vs a direct computation from source tables (e.g.
  Σ equity_points.last per account vs `accounts.equity`); drift →
  CRITICAL alert + the ADM surface shows which model is stale.
- **Rebuild (ANA-22):** `ana-rebuild <model> [--from date]` — re-consume
  the PG `events` log (04 §5.4, 13-month window) into the model;
  window-limited (equity rebuild for a week = seconds of compute);
  behind a 2FA'd ADM trigger (it's a data operation on production).
- **Health dashboard (ANA-33):** per consumer: lag (source Seq − consumed
  Seq), last write time, row counts vs expected (growth rate), rebuild
  history. A read model with 3-day silence is **red on the wall**, not
  silently wrong.

### 3.5 Alerting & permissions (V2 ANA-34/13)

- KPI alerting: registry rows with thresholds (e.g. "payouts_daily.settled
  > 3× 30-day average → WARN to finance", "relay lag > 5 min → CRITICAL")
  → CON/NOT. The V1 dashboard already shows the values; V2 adds the
  thresholds.
- Permissions: `firm:owner/admin` see all reports; `firm:finance`
  financial reports; `firm:risk` risk + funnel; per-report override in the
  registry (ANA-13) — Cerbos policies generated from the registry (the
  report registry is the single source; CI checks policy coverage).

## 4. Events (topic `analytics` — mostly internal)

| Event | When | Consumers |
|---|---|---|
| `analytics.read_model_drift` (V2) | reconciliation mismatch | CON (CRITICAL), ADM, AUD |
| `analytics.read_model_rebuilt` (V2) | rebuild complete | AUD |
| `analytics.report_generated` (V2) | async report done | NOT (email link), AUD |
| `analytics.kpi_alert` (V2) | threshold breach | NOT (per routing), CON, AUD |

Consumes: `bridge.tick` (equity points — the EVL-observed feed, 08/09),
`account.*`, `identity.*`, `kyc.*`, `payments.*`, `payout.*`, `risk.*`,
`system.*` (provider health, relay lag).

## 5. Lifecycles

- **Read model row:** upserted by its consumer; rebuildable (§3.4);
  retention per table (§3.1) with a V2 lifecycle job (delete + audit).
- **Report run (V2):** `requested → running → available (R2, 24 h) |
  failed` (failure → retry once → alert; a failed report is an ops event,
  not a silent gap).
- **Schedule (V2):** `active → paused` (registry); cron via the worker's
  advisory-lock jobs (06 §advisory-lock pattern — one job, N reports).
- **KPI snapshot:** rolling 30-s rows, 7-day retention (the sparklines).

## 6. Error taxonomy

Namespace `ANA`:

| Code | HTTP | Meaning |
|---|---|---|
| `ana.model_stale` | 409 (dashboard context) | Read model lag > threshold (UI: "data from {as_of}" banner — the ANA-14 label, surfaced as a soft error) |
| `ana.report_not_found` | 404 | Unknown report id (V2) |
| `ana.report_params_invalid` | 422 | (V2) Bad report params |
| `ana.report_running` | 409 | Duplicate concurrent run (return the existing run id) |
| `ana.export_limit` | 429 | (V2) Concurrent export cap |
| `ana.threshold_invalid` | 422 | (V2) Alert rule malformed |
| `ana.rebuild_window_exceeded` | 422 | (V2) Rebuild older than the events log window (13 mo) |
| internal: `ana.consumer_lag` | — | Ops metric → CON alert (not an API code) |

## 7. API endpoints
### 7.1 V1 baseline — `ana` (authoritative: `contracts/api/ana.md`)

| Method + path | Auth | Permission | Idempotency | V1 errors |
|---|---|---|---|---|
| `GET /v1/admin/analytics/kpi` | Tenant Admin — ANA-32 (V1.1) | `analytics.read` # ANA-32 | n/a | standard |

Scope, request/response shapes, and per-endpoint notes: `contracts/api/ana.md` (field values in the research are owner TODOs until contract freeze; canonical JSON is fixed at freeze, per the docs/99 §12 rules).

### 7.2 Extended (post-V1) surface — provisional

> Not in the V1 execution sheet. Design-level; paths beyond the V1 baseline are provisional until the URL-plan decision (`contracts/api/gw.md`, open question). Shown for platform completeness (V2/V3 phases, docs/99).

Staff (ADM): `GET /v1/admin/analytics/kpis` (the V1 dashboard data — one
call, the snapshot + feed health),
`GET /v1/admin/analytics/accounts?…` (the ADM account list fast path, 17
§3.1 — reads `accounts_ro`),
V2: `GET /v1/admin/analytics/reports` (registry + definitions),
`POST /v1/admin/analytics/reports/{id}/run` `{params}` → run id,
`GET /v1/admin/analytics/reports/runs/{id}` (status + R2 URL when done),
`POST /v1/admin/analytics/reports/{id}/schedule` (V2 ANA-12/35),
`GET /v1/admin/analytics/health` (ANA-33),
`POST /v1/admin/analytics/rebuild` (ANA-22, 2FA),
`GET /v1/admin/analytics/exports` (history, 24 h links).

No trader-facing endpoints (the TD's equity curve reads the BRG/LCC APIs;
the TD does not query ANA — the read models serve staff surfaces + the SSE
relay).
## 8. Schema (key shapes)

```jsonc
// GET /v1/admin/analytics/kpis
{ "data": { "as_of": 1758282150000, "feed": { "lag_s": 2, "state": "live" },
    "live": { "funded_accounts": 214, "active_traders_24h": 89,
              "book_value_cents": 22140000000 },
    "today": { "purchases": { "count": 6, "gross_cents": 2994000 },
               "payouts_settled": { "count": 3, "cents": 8421000 },
               "breaches": 2 },
    "queues": { "payout_pending": 4, "kyc_manual": 2, "risk_open": 1 },
    "providers": { "metaapi": "up", "nowpayments": "up", "relay_lag_ms": 120 } } }

// V2 report registry row
{ "data": { "id": "rpt-unit-economics", "name": "Per-challenge unit economics",
    "params": { "from": "date", "to": "date", "package": "optional" },
    "columns": [ { "key": "margin_cents",
                   "definition": "challenge_gross − payout_settled − provider_fees − infra_share" } ],
    "permissions": ["firm:owner", "firm:finance"], "schedule": "monthly" } }
```

## 9. Database design

```sql
CREATE TABLE equity_points (
  tenant_id   ULID NOT NULL,
  account_id  ULID NOT NULL,
  as_of       TIMESTAMPTZ NOT NULL,          -- 1-min bucket
  equity_cents BIGINT NOT NULL,
  balance_cents BIGINT, hwm_cents BIGINT,
  tick_at     TIMESTAMPTZ NOT NULL,
  PRIMARY KEY (tenant_id, account_id, as_of)
);
CREATE INDEX idx_eqp_range ON equity_points(tenant_id, as_of DESC);
-- monthly partitions (created by migration; 13-mo retention job V2)

CREATE TABLE accounts_ro (
  tenant_id   ULID PRIMARY KEY (tenant_id, account_id),
  account_id  ULID NOT NULL,
  identity_id ULID, package TEXT, state TEXT, phase TEXT,
  opened_at TIMESTAMPTZ, funded_at TIMESTAMPTZ, breached_at TIMESTAMPTZ,
  broker_account TEXT, equity_cents BIGINT, state_changed_at TIMESTAMPTZ
);
CREATE INDEX idx_accts_ro_state ON accounts_ro(tenant_id, state);

CREATE TABLE traders_ro (
  tenant_id   ULID NOT NULL, identity_id ULID NOT NULL,
  name_masked TEXT, email_masked TEXT, country CHAR(2),
  kyc_l1_at TIMESTAMPTZ, kyc_l2_at TIMESTAMPTZ, created_at TIMESTAMPTZ,
  account_count INT, last_active_at TIMESTAMPTZ,
  PRIMARY KEY (tenant_id, identity_id)
);

CREATE TABLE payments_daily (
  tenant_id ULID NOT NULL, day DATE NOT NULL,
  intents INT, captured INT, gross_cents BIGINT, fee_cents BIGINT,
  refunds INT, refund_cents BIGINT,
  PRIMARY KEY (tenant_id, day)
);
CREATE TABLE payouts_daily (
  tenant_id ULID NOT NULL, day DATE NOT NULL,
  requested INT, approved INT, settled INT, settled_cents BIGINT,
  failed INT, approval_h_avg NUMERIC(6,2),
  PRIMARY KEY (tenant_id, day)
);

CREATE TABLE funnel_steps (
  tenant_id ULID NOT NULL, identity_id ULID NOT NULL,
  step TEXT NOT NULL, at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (tenant_id, identity_id, step, at)
);

CREATE TABLE risk_summary (
  tenant_id ULID NOT NULL, day DATE NOT NULL,
  open_cases INT, opened INT, decided INT, hold_cents_active BIGINT,
  PRIMARY KEY (tenant_id, day)
);

CREATE TABLE kpi_snapshots (
  tenant_id ULID NOT NULL, as_of TIMESTAMPTZ NOT NULL,
  payload JSONB NOT NULL,                     -- the §3.2 blocks
  PRIMARY KEY (tenant_id, as_of)
);
-- V2 adds: report_registry, report_runs, kpi_alerts (per §3.3–3.5)
```

## 10. Security & compliance

- **Tenant isolation on every read model** (§2 principle 3); cross-tenant
  queries need the platform-ops role (V3 ANA-28) and are themselves
  audited (reading another tenant's KPIs = critical tier).
- **PII in read models is masked by construction** (`traders_ro` stores
  masked name/email — the raw identity lives in AUTH; a read-model leak
  exposes aggregates, not people).
- **Exports contain tenant data** (V2): R2 tenant-prefixed, 24 h URLs,
  download audit, role-gated (ANA-13).
- **Rebuild is a data operation** (ANA-22): 2FA + audit + the window is
  bounded by the events log (13 mo) — a rebuild can never fabricate
  history outside the log.
- **Report definitions are versioned** (registry rows) — "the margin
  number changed" has an answer: the definition row (ANA-23) + the run
  snapshot.
- **No external data** in V1/V2 reports (ANA-18 warehouse is V3; no
  third-party analytics APIs anywhere — the first-party-only rule from TD
  §10 extends to staff tools).

## 11. Scalability considerations

- Consumer load: `bridge.tick` is the only high-rate input (~1-10
  ticks/account/min across the fleet → V1: < 100 writes/sec platform-wide
  at 1k accounts) — one consumer instance, batched inserts (100 rows or
  500 ms), zero pressure.
- `equity_points` is the one big table: 1,440 rows/account/month; 1k
  accounts ≈ 50M rows/yr; monthly partitions + 13-mo retention ≈ 5.4M
  rows hot — indexed point reads for the TD chart are sub-millisecond.
- Dashboard: one `kpi_snapshots` row read per 30 s per ADM session —
  trivial; the 30-s compute job is a handful of indexed aggregates
  (< 50 ms).
- V2 reports: async by design (the registry + run queue); the heaviest
  (unit economics over 12 months) ≈ a few seconds of SQL; PDF render via
  DOC; 5 concurrent run cap (ANA_EXPORT_LIMIT).
- **The escape hatch (committed):** if read models ever stop being enough
  (V3: predictive ANA-19, cross-tenant ANA-28), ANA-18 dumps the read
  models (not the source tables) to BigQuery — the dump is append-only
  log + model exports, so the warehouse is also rebuildable.

## 12. Open-source solutions

| Option | Verdict |
|---|---|
| **PG materialized read models** (this design) | **CHOSEN** — single DB (ADR), event-driven upserts, rebuildable from the events log; the research files' "TimescaleDB/Elasticsearch" tier is overkill below ~10× scale |
| TimescaleDB (research list) | Rejected: hypertables ≈ our monthly partitions; the extension adds upgrade risk for no V1 benefit |
| ClickHouse (OLAP sidecar) | V3 candidate (ANA-18 class) if unit-economics queries outgrow PG — the read-model boundary makes it a later decision, not a day-1 one |
| Metabase (self-hosted BI) | Rejected: a second app + its own DB auth to build the same 10 reports the registry does; revisit post-V2 if the V2 report suite feels constrained |
| Grafana (OPS stack, 06) | Stays for *system* metrics (OPS); ANA owns *business* metrics — the wall screen is one ADM page, not two dashboards (the V1 dashboard in §3.2 is ANA's, with the CON alerts block) |
| DOC + R2 + NOT | V2 export/delivery plumbing (already chosen) |

## 13. Technology stack

Go consumer jobs (workers process) + api routes; Postgres (read models,
partitions, the events log as rebuild source); R2 (V2 exports); DOC (V2
PDF); NOT (V2 scheduled email); ADM (dashboard + report UI); Prometheus
(consumer lag, job runtime); Sentry.

## 14. Integration — internal modules (glue)

| Module | How |
|---|---|
| **EVT** | consumers on per-entity lanes + standard topics; `event_ref` on upserts for rebuild traceability |
| **BRG/EVL** | `bridge.tick` → equity_points (the EVL-49 observed feed — ANA is where the TD chart and the ADM dashboard get their numbers) |
| **LCC** | account.* → accounts_ro (ADM list fast path, 17 §3.1) |
| **PAY/CHK** | settlement/capture events → the daily rollups (the unit-economics inputs) |
| **RSK** | case events → risk_summary |
| **KYC/AUTH** | funnel steps + traders_ro |
| **ADM** | the KPI dashboard page, report registry UI, health dashboard, rebuild trigger |
| **CON** | lag/drift alerts (CON owns the alert routing, 06) |
| **LED** | V2 financial reports cross-check rollups vs ledger balances (the monthly report reconciles to the books — ANA-21's money case) |
| **MIG** | cutover: read models are **rebuilt from the migrated history** during the parallel run (ANA-22's first real use — the reconciliation vs TTS reports is the cutover evidence, 25/MIG) |

## 15. Integration — external tools

Prometheus/Grafana (system metrics), R2, Postmark (via NOT, V2), (V3)
BigQuery (ANA-18), Sentry.

## 16. Implementation blueprint

| Step | Owner | Est | Depends | Exit criteria |
|---|---|---|---|---|
| 1. Read model schemas (V1 set, §3.1) + partitions + retention job | BE-2 | 1.5 d | OPS | migrations green; partition maintenance works |
| 2. Consumers (equity_points from bridge.tick; accounts_ro; traders_ro; dailies; funnel) + batched upserts + lag metrics | BE-2 | 4 d | 1, EVT lanes, BRG-07 | seeded ticks → points within 2 s; consumer lag visible in Prometheus |
| 3. Rebuild script (equity_points from events log, windowed) + the first reconciliation check | BE-2 | 1.5 d | 2 | kill a day of points → rebuild → identical (property test) |
| 4. KPI dashboard (ANA-32) in ADM: 5 blocks, 30-s refresh, feed staleness banner, provider block | FE-1 + BE-2 | 3 d | 2, ADM shell | wall screen shows live numbers on staging; BRG outage → banner, not wrong numbers |
| 5. Freshness labeling pass (as_of on every figure) + V2 prep: report registry schema | BE-2 | 1 d | 4 | no dashboard figure without an as_of (code review checklist) |
| 6. V2: report suite (ANA-02..16,20,24..26,29,31), CSV/PDF exports + schedules + email, permissions, KPI alerting, health dashboard, full reconciliation + rebuild tooling | BE-2 + FE-1 | 4 wks | 5 | monthly financial report reconciles to LED within 0 (test: seeded 1¢ drift → CRITICAL) |
| 7. V3: warehouse dump (ANA-18), retention/cohort, builder, predictive, cross-tenant | BE-2 | 4 wks | 6 | dump replay into BigQuery matches PG aggregates |

**Risks:** read model drift going unnoticed (mitigation: reconciliation is
V1-adjacent — the equity rebuild check ships in step 3, the rest in V2;
the ANA-33 health surface makes silence visible); the dashboard becoming
wrong-looking during outages (mitigation: the feed staleness banner is a
hard requirement — a KPI without an as_of is a bug, not a gap); scope
creep into BI-tool territory (the registry + 10 named reports is the
boundary; "custom report builder" waits for V3 per the PRD).

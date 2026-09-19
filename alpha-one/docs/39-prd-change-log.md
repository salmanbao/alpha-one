# 39 — PRD Change Log, Backlog Audit & Vocabularies

> Generated 2026-09-19 by `scripts/build_prd_registers.py` from
> `scripts/prd-workbook.json` (parsed from `uploads/Alpha One PRD.pdf`,
> the *Change Log* sheet). Do not edit by hand: re-run the script after a PRD
> change, exactly like `scripts/prd-backlog.json`.
>
> The workbook's own history: every structural edit the PRD author made, the last automated backlog audit, and the controlled vocabularies the backlog columns draw from. Use §1 to date a requirement change, §2 to see what is still inconsistent, and §3 as the enum source for contracts.


Change-log entries: **67**. Audit findings: **7**. Vocabulary sections: **13**.

## 1. Change log

| Timestamp | Actor | Action | Req | Field | Old | New |
|---|---|---|---|---|---|---|
| 2026-09-14 10:15:43 | salmancodez@gmail.com | `CLEANUP_V2_CORRECTION` | BULK | Master Backlog + Open Questions + Feature Name | CLEANUP_V2 was recorded as full but only partially executed: Master Backlog Notes 2 / Proposed By for V1 rows not rewritten; Open Questions KYC re-verification row not realigned. | Master Backlog Notes 2 rewritten for V1 rows and stray demotion text cleared from Proposed By; KYC re-verification row realigned; BRG-27 and CHK-28 Feature Name cells corrected. |
| 2026-09-14 10:22:30 | salmancodez@gmail.com | `MOVE_FORWARD` | BULK | Derived sheets | — | V1=159, Future=814 |
| 2026-09-14 10:40:32 | salmancodez@gmail.com | `MOVE_FORWARD` | BULK | Derived sheets | — | V1=159, Future=814 |
| 2026-09-14 10:44:47 | salmancodez@gmail.com | `FIX_INTEGRATION_MAP` | BULK | Integration Map | 7 columns (Tool \| Category \| What it does \| V1 rows it serves \| Cost \| Signup status \| Action needed) | 10 columns (Tool \| Category \| What it does \| Serves Req IDs \| Serves Release \| Cost \| Cost model \| Signup status \| Owner \| Action needed). 55 tools. |
| 2026-09-14 10:46:31 | salmancodez@gmail.com | `FIX_INTEGRATION_MAP` | BULK | Integration Map | 7 columns (Tool \| Category \| What it does \| V1 rows it serves \| Cost \| Signup status \| Action needed) | 10 columns (Tool \| Category \| What it does \| Serves Req IDs \| Serves Release \| Cost \| Cost model \| Signup status \| Owner \| Action needed). 55 tools. |
| 2026-09-14 10:51:15 | salmancodez@gmail.com | `FIX_DATA_DICTIONARY` | N/A | Data Dictionary | 5 sections (Priority, Phase, Status, Complexity, Build Strategy) with incomplete Build Strategy values | 68 enum values across 10 sections (Priority, Phase, Release, Status, Complexity, Build Strategy, Comment Status, Release -> Phase, Tool Category, Signup status, Tool Type, Hosting, Domain ID) |
| 2026-09-14 10:59:04 | salmancodez@gmail.com | `FIX_VERSION_ROADMAP` | BULK | Version Roadmap | 6 rows (V1.0, V1.1, V1.2, V2.0, V2.1, V3.0), 11 columns, empty Target Dates, no Gate Status | 4 rows (V1.0, V1.1, V2.0, V3.0), 12 columns with Gate Status, refreshed counts from Master Backlog |
| 2026-09-14 7:03:14 | salmancodez@gmail.com | `CLEANUP_V1` | BULK | Build vs Buy Rules | BVR-08=Prisma, BVR-14=in-house auth, BVR-23=Use Cerbos, BVR-19..21 missing | BVR-08=Drizzle preferred, BVR-14=Better Auth foundation, BVR-23=Evaluate Cerbos, BVR-19..21 added |
| 2026-09-14 7:03:14 | salmancodez@gmail.com | `CLEANUP_V2` | BULK | V1 Execution + Open Questions + Integration Map + Out Of Scope | Inconsistent / stale / misaligned | Reconciled / synced / aligned |
| 2026-09-15 23:15:46 | salmancodez@gmail.com | `PROPOSAL_SUBMITTED` | PROP-0001 | Feature Proposals | — | TD — News feed widget (P2, S, V2.0) |
| 2026-09-15 23:16:17 | salmancodez@gmail.com | `PROPOSAL_SUBMITTED` | PROP-0002 | Feature Proposals | — | TD — Watchlist widget (P2, S, V2.0) |
| 2026-09-15 23:16:37 | salmancodez@gmail.com | `PROPOSAL_SUBMITTED` | PROP-0003 | Feature Proposals | — | TD — Order tracking widget (P2, S, V2.0) |
| 2026-09-15 23:17:13 | salmancodez@gmail.com | `PROPOSAL_SUBMITTED` | PROP-0004 | Feature Proposals | — | EVL — Trading hours restriction rule (P1, S, V2.0) |
| 2026-09-15 23:17:39 | salmancodez@gmail.com | `PROPOSAL_SUBMITTED` | PROP-0005 | Feature Proposals | — | EVL — News event trading lock (P1, M, V2.0) |
| 2026-09-15 23:18:03 | salmancodez@gmail.com | `PROPOSAL_SUBMITTED` | PROP-0006 | Feature Proposals | — | KYC — AML / sanctions / PEP screening (P1, L, V2.0) |
| 2026-09-15 23:18:35 | salmancodez@gmail.com | `PROPOSAL_SUBMITTED` | PROP-0007 | Feature Proposals | — | CMP — Loyalty points and redemption (P2, M, V3.0) |
| 2026-09-15 23:19:01 | salmancodez@gmail.com | `PROPOSAL_SUBMITTED` | PROP-0008 | Feature Proposals | — | MOB — White-label mobile app packaging per tenant (P1, L, V3.0) |
| 2026-09-15 23:19:33 | salmancodez@gmail.com | `PROPOSAL_SUBMITTED` | PROP-0009 | Feature Proposals | — | BRG — Volumetrica adapter (P2, L, V3.0) |
| 2026-09-15 23:20:14 | salmancodez@gmail.com | `PROPOSAL_SUBMITTED` | PROP-0010 | Feature Proposals | — | BRG — Quantower adapter (P2, L, V3.0) |
| 2026-09-15 23:20:30 | salmancodez@gmail.com | `PROPOSAL_SUBMITTED` | PROP-0011 | Feature Proposals | — | BRG — ATAS adapter (P2, L, V3.0) |
| 2026-09-15 23:21:03 | salmancodez@gmail.com | `PROPOSAL_SUBMITTED` | PROP-0012 | Feature Proposals | — | CHK — PSP catalog expansion framework (P1, M, V2.0) |
| 2026-09-15 23:21:27 | salmancodez@gmail.com | `PROPOSAL_SUBMITTED` | PROP-0013 | Feature Proposals | — | TD — Trader portal UI localization (P2, M, V2.0) |
| 2026-09-15 23:21:55 | salmancodez@gmail.com | `PROPOSAL_SUBMITTED` | PROP-0014 | Feature Proposals | — | CMS — Freeform landing page builder (P2, L, V3.0) |
| 2026-09-18 2:15:22 | rule-engine-gap-fill@script | `RULE_ENGINE_GAP_FILL` | EVL-46 | New row | — | Metric registry and calculation service |
| 2026-09-18 2:15:23 | rule-engine-gap-fill@script | `RULE_ENGINE_GAP_FILL` | EVL-47 | New row | — | Trading calendar and time semantics |
| 2026-09-18 2:15:24 | rule-engine-gap-fill@script | `RULE_ENGINE_GAP_FILL` | EVL-48 | New row | — | Rule composition and dependency map |
| 2026-09-18 2:15:24 | rule-engine-gap-fill@script | `RULE_ENGINE_GAP_FILL` | EVL-49 | New row | — | Observed vs evaluated snapshot model |
| 2026-09-18 2:15:25 | rule-engine-gap-fill@script | `RULE_ENGINE_GAP_FILL` | EVL-50 | New row | — | Rule trigger matrix and observation requirements |
| 2026-09-18 2:15:25 | rule-engine-gap-fill@script | `RULE_ENGINE_GAP_FILL` | EVL-51 | New row | — | Fast risk guard and emergency threshold path |
| 2026-09-18 2:15:26 | rule-engine-gap-fill@script | `RULE_ENGINE_GAP_FILL` | EVL-52 | New row | — | Snapshot ordering and staleness policy |
| 2026-09-18 2:15:27 | rule-engine-gap-fill@script | `RULE_ENGINE_GAP_FILL` | EVL-53 | New row | — | Precision, rounding and threshold comparison semantics |
| 2026-09-18 2:15:27 | rule-engine-gap-fill@script | `RULE_ENGINE_GAP_FILL` | EVL-54 | New row | — | Rule test vector suite |
| 2026-09-18 2:15:28 | rule-engine-gap-fill@script | `RULE_ENGINE_GAP_FILL` | LCC-43 | New row | — | Breach decision idempotency key |
| 2026-09-18 2:15:28 | rule-engine-gap-fill@script | `RULE_ENGINE_GAP_FILL` | LCC-44 | New row | — | Partial enforcement state and per-position confirmation |
| 2026-09-18 2:15:29 | rule-engine-gap-fill@script | `RULE_ENGINE_GAP_FILL` | RSK-53 | New row | — | Independent risk guard and emergency kill switch |
| 2026-09-18 2:15:29 | rule-engine-gap-fill@script | `RULE_ENGINE_GAP_FILL` | BVR-28 | New rule | — | BVR-28: Own rule semantics, rule versions, metric definitions, breach decisions, account... |
| 2026-09-18 2:15:32 | rule-engine-gap-fill@script | `REGENERATE` | BULK | V1 Execution Sheet | — | 175 rows from Master Backlog |
| 2026-09-18 2:15:33 | rule-engine-gap-fill@script | `REGENERATE` | BULK | Future Backlog | — | 844 rows from Master Backlog |
| 2026-09-18 2:15:35 | rule-engine-gap-fill@script | `REFRESH_COUNTS` | BULK | Version Roadmap | — | Recalculated from Master Backlog |
| 9/13/2026 16:23:19 | salmancodez@gmail.com | `FIX_COLUMNS` | N/A | Collaboration block | AA–AG | Q–W |
| 9/13/2026 17:31:40 | salmancodez@gmail.com | `DELETE_TAB` | N/A | Raw Data | present | deleted |
| 9/13/2026 18:21:38 | salmancodez@gmail.com | `STEP8_IMPORT` | BULK | New modules + features | — | 5 modules, 61 features |
| 9/13/2026 23:30:30 | salmancodez@gmail.com | `MOVE_FORWARD` | BULK | Derived sheets | — | V1=159, Future=814, Roadmap=6 |
| 9/14/2026 0:25:44 | salmancodez@gmail.com | `MOVE_FORWARD` | BULK | Derived sheets | — | V1=159, Future=814, Roadmap=6 |
| 9/14/2026 13:00:27 | salmancodez@gmail.com | `CLEANUP_V3` | BULK | Master Backlog Notes 2 column | present | removed |
| 9/14/2026 13:00:28 | salmancodez@gmail.com | `FIX_CHK_25_STATUS` | CHK-25 | Status | — | Draft |
| 9/14/2026 13:00:28 | salmancodez@gmail.com | `FIX_OUT_OF_SCOPE_HEADER` | BULK | Out Of Scope 5th block header | Risk Management | Analytics & BI |
| 9/14/2026 13:00:29 | salmancodez@gmail.com | `FIX_FUTURE_BACKLOG_SCHEMA` | BULK | Future Backlog Column 23 | present | removed |
| 9/14/2026 13:00:30 | salmancodez@gmail.com | `CLEANUP_V4` | CHK-28 | User Story | trailing note embedded in cell | moved to Notes |
| 9/14/2026 13:00:30 | salmancodez@gmail.com | `CLEANUP_V4` | CON-04 | User Story | extra sentence embedded in cell | moved to Notes |
| 9/14/2026 13:00:31 | salmancodez@gmail.com | `CLEANUP_V4` | DOC-12 | User Story | DocuSign/HelloSign | Documenso |
| 9/14/2026 13:00:32 | salmancodez@gmail.com | `CLEANUP_V4` | BVR-08 | Tooling Register Prisma Why this one | Prisma migrations are best-fit for our discipline | Prisma acceptable fallback; Drizzle primary per BVR-08 |
| 9/14/2026 13:00:33 | salmancodez@gmail.com | `FIX_CROSS_REFERENCES` | BULK | Tooling Register Serves Req IDs | partial | reconciled |
| 9/14/2026 13:00:33 | salmancodez@gmail.com | `FIX_BULLMQ_DASHBOARD_REQ_IDS` | BVR-25 | Applies to | OPS-21, CON-21 | OPS-17, CON-21 |
| 9/14/2026 13:00:35 | salmancodez@gmail.com | `FIX_BULLMQ_DASHBOARD_REQ_IDS` | Tooling Register BullMQ Dashboard | Serves Req IDs | OPS-21, CON-21 | OPS-17, CON-21 |
| 9/14/2026 13:00:35 | salmancodez@gmail.com | `FIX_OUT_OF_SCOPE_TRADER_DASHBOARD` | BULK | Out Of Scope 4th block header | Trading Dashboard | Trader Dashboard |
| 9/14/2026 13:00:36 | salmancodez@gmail.com | `BACKFILL_PROVENANCE` | BULK | Collaboration columns | blank | backfilled |
| 9/14/2026 13:15:32 | salmancodez@gmail.com | `FIX_BULLMQ_DASHBOARD_INTEGRATION_MAP` | Integration Map BullMQ Dashboard | Serves Req IDs | OPS-21, CON-21 | OPS-17, CON-21 |
| 9/14/2026 13:15:33 | salmancodez@gmail.com | `FIX_BULLMQ_DASHBOARD_TOOLING_REGISTER` | Tooling Register BullMQ Dashboard | Serves releases | V1.0 | V2.0 |
| 9/14/2026 13:15:34 | salmancodez@gmail.com | `FIX_PRISMA_WHY_REJECTED` | BVR-08 | Tooling Register Prisma Why rejected | Prisma migrations are best-fit for our discipline | Drizzle preferred for SQL-fluent control, faster cold starts, smaller bundle. Prisma retained only as declarative-schema fallback per BVR-08. |
| 9/14/2026 13:15:34 | salmancodez@gmail.com | `FIX_DOCUSIGN_REJECTED` | DOC-12 | Tooling Register + Integration Map DocuSign Signup status | EVALUATING | REJECTED |
| 9/14/2026 13:15:35 | salmancodez@gmail.com | `CLOSE_ANSWERED_OPEN_QUESTIONS` | BULK | Open Questions Answer | Open | Answered with decision pointer |
| 9/14/2026 13:15:36 | salmancodez@gmail.com | `FIX_SENTRY_RELEASE` | OPS-11 | Sentry Serves Release | V1.0 | V2.0 |
| 9/14/2026 13:15:37 | salmancodez@gmail.com | `FIX_PLUNK_SERVES_REQ_IDS` | CRM-06 | Plunk Serves Req IDs | NOT-14, CRM-06 | CRM-06 |
| 9/14/2026 13:15:37 | salmancodez@gmail.com | `FIX_DOMAINS_STRAY_HEADER` | BULK | Domains and Modules Column 5 header | Column 5 | (cleared) |
| 9/14/2026 13:15:38 | salmancodez@gmail.com | `FIX_RESIDUAL_CONSISTENCY` | BULK | Workbook | Residual PRD(20) inconsistencies | Reconciled |
| 9/16/2026 14:49:57 | salmancodez@gmail.com | `FIX_ZONELESS_INTEGRATION_MAP` | Zoneless | Integration Map | Missing | Added |

### 1.1 Actions you will meet

- `FIX_COLUMNS` — Sheet-data repair: a column, enum or row was corrected after review.
- `DELETE_TAB` — Sheet-data repair: a column, enum or row was corrected after review.
- `STEP8_IMPORT` — Bulk regeneration / import of the workbook.
- `MOVE_FORWARD` — A requirement was pulled into an earlier release.
- `CLEANUP_V1` — Sheet-data repair: a column, enum or row was corrected after review.
- `CLEANUP_V2` — Sheet-data repair: a column, enum or row was corrected after review.
- `CLEANUP_V2_CORRECTION` — Sheet-data repair: a column, enum or row was corrected after review.
- `FIX_INTEGRATION_MAP` — Sheet-data repair: a column, enum or row was corrected after review.
- `FIX_DATA_DICTIONARY` — Sheet-data repair: a column, enum or row was corrected after review.
- `FIX_VERSION_ROADMAP` — Sheet-data repair: a column, enum or row was corrected after review.
- `CLEANUP_V3` — Sheet-data repair: a column, enum or row was corrected after review.
- `FIX_CHK_25_STATUS` — Sheet-data repair: a column, enum or row was corrected after review.
- `FIX_OUT_OF_SCOPE_HEADER` — Sheet-data repair: a column, enum or row was corrected after review.
- `FIX_FUTURE_BACKLOG_SCHEMA` — Sheet-data repair: a column, enum or row was corrected after review.
- `CLEANUP_V4` — Sheet-data repair: a column, enum or row was corrected after review.
- `FIX_CROSS_REFERENCES` — Sheet-data repair: a column, enum or row was corrected after review.
- `FIX_BULLMQ_DASHBOARD_REQ_IDS` — Sheet-data repair: a column, enum or row was corrected after review.
- `FIX_OUT_OF_SCOPE_TRADER_DASHBOARD` — Sheet-data repair: a column, enum or row was corrected after review.
- `BACKFILL_PROVENANCE` — Bulk regeneration / import of the workbook.
- `FIX_BULLMQ_DASHBOARD_INTEGRATION_MAP` — Sheet-data repair: a column, enum or row was corrected after review.
- `FIX_BULLMQ_DASHBOARD_TOOLING_REGISTER` — Sheet-data repair: a column, enum or row was corrected after review.
- `FIX_PRISMA_WHY_REJECTED` — Sheet-data repair: a column, enum or row was corrected after review.
- `FIX_DOCUSIGN_REJECTED` — Sheet-data repair: a column, enum or row was corrected after review.
- `CLOSE_ANSWERED_OPEN_QUESTIONS` — Answers were copied back into `docs/37-prd-open-questions.md`.
- `FIX_SENTRY_RELEASE` — Sheet-data repair: a column, enum or row was corrected after review.
- `FIX_PLUNK_SERVES_REQ_IDS` — Sheet-data repair: a column, enum or row was corrected after review.
- `FIX_DOMAINS_STRAY_HEADER` — Sheet-data repair: a column, enum or row was corrected after review.
- `FIX_RESIDUAL_CONSISTENCY` — Sheet-data repair: a column, enum or row was corrected after review.
- `PROPOSAL_SUBMITTED` — A feature proposal was filed (see `docs/36-prd-feature-proposals.md`).
- `FIX_ZONELESS_INTEGRATION_MAP` — Sheet-data repair: a column, enum or row was corrected after review.
- `RULE_ENGINE_GAP_FILL` — Requirements added from the rule-engine review (`rule-engine-gap-fill@script`).
- `REGENERATE` — Bulk regeneration / import of the workbook.
- `REFRESH_COUNTS` — Bulk regeneration / import of the workbook.

## 2. Backlog audit

Last run: `2026-09-16T13:13:15.580Z` (1 error, 6 warnings).

| Severity | Sheet | Row | Rule | Detail |
|---|---|---|---|---|
| **ERROR** | Master Backlog | 975 | Placeholder requirement | BRG-28 — define or delete before contract freeze |
| **WARN** | Tooling Register | 13 | Tool not in Integration Map | PostgreSQL (Self-hosted) is not represented in Integration Map |
| **WARN** | Tooling Register | 14 | Tool not in Integration Map | Redis (Self-hosted) is not represented in Integration Map |
| **WARN** | Tooling Register | 47 | Tool not in Integration Map | Prometheus (Self-hosted) is not represented in Integration Map |
| **WARN** | Tooling Register | 48 | Tool not in Integration Map | Grafana (Self-hosted) is not represented in Integration Map |
| **WARN** | Tooling Register | 49 | Tool not in Integration Map | Loki (Self-hosted) is not represented in Integration Map |
| **WARN** | Tooling Register | 50 | Tool not in Integration Map | OpenTelemetry (Self-hosted) is not represented in Integration Map |

### 2.1 What each finding means for us

- **`BRG-28` is still a placeholder** (`broker server time drift detection`). It has no release in the workbook and no contract surface; either define it or delete it before Phase 1 contract freeze (`docs/99 §12`). Tracked in `docs/08-trading-bridge.md` open items.
- **`Tool not in Integration Map` warnings** are documentation drift inside the PRD itself (PostgreSQL, Redis, Prometheus, Grafana, Loki, OpenTelemetry are self-hosted platform pieces rather than signup dependencies). `docs/34-tooling-registry.md` §3.2 lists them as platform infrastructure; no action needed beyond keeping the two sheets in step.

## 3. Workbook vocabularies

These are the PRD's own allowed values; module docs and contracts must use exactly these spellings.

**Priority:** `P0`, `P1`, `P2`, `P3`

**Phase:** `V1-Core`, `V1-Plus`, `V2`, `V3`, `Icebox`

**Release:** `V1.0`, `V1.1`, `V2.0`, `V3.0`

**Status:** `Draft`, `In Review`, `Approved`, `Deferred`, `Rejected`, `Duplicate`, `Needs Rewrite`, `Needs Dependency Fix`

**Complexity:** `S`, `M`, `L`

**Build Strategy:** `Build`, `Buy`, `Integrate`, `Manual for V1`, `Defer`, `Build/config`, `Build flow, Integrate providers`, `Build core, Integrate advanced`, `Integrate provider, Build gates`, `Integrate provider, Build routing`, `Buy/Integrate`

**Release -> Phase:** `V1.0 = V1-Core`, `V1.1 = V1-Plus`, `V2.0 = V2`, `V3.0 = V3`

**Tool Category:** `Must-integrate`, `Self-hosted`, `Consider-later`, `Forbidden`

**Signup status:** `NOT STARTED`, `IN PROGRESS`, `SIGNED`, `SELF-HOSTED`, `EVALUATING`, `DEFERRED`, `REJECTED`

**Tool Type:** `Open-source`, `Commercial`, `Self-hosted`

**Hosting:** `Self-hosted (Hetzner)`, `Self-hosted (bundled)`, `Cloud (vendor)`, `Edge`, `Client-side (bundled)`

**Domain ID:** `D1`, `D2`, `D3`, `D4`, `D5`

**Comment Status:** `New`, `Discussed`, `Accepted`, `Rejected`, `Needs Info`


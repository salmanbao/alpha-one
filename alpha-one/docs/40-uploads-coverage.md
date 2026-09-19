# 40 — Source Material & Coverage (the uploads audit)

> Written 2026-09-19. Every file in `uploads/` was read file-by-file and is
> accounted for below: what it is, where its content landed in this repo, and
> what is still open. This is the traceability record for the doc set — if a
> reader asks "did we actually read the research?", this table is the answer.
>
> Requirement coverage: cross-cutting (provenance; no PRD module).

## 1. How to read this document

Three source families were processed:

| Family | Files | Volume | Where it landed |
|---|---|---|---|
| `uploads/Alpha One PRD.pdf` | 1 (79 printed pages, 13 sheets) | 1.7 MB | `scripts/prd-backlog.json` (the 1020-row scope authority), `scripts/prd-workbook.json` (every sheet, machine-readable), `docs/36`–`docs/39` (the registers), and the module docs' §1/§16 |
| `uploads/Alpha One PRD - Domains and Modules.pdf` | 1 (2 pages) | 8 KB | `docs/00 §3` (5 domains / 36 modules), `docs/36`–`docs/39` headers, `scripts/prd-workbook.json → domains_and_modules` |
| `uploads/contracts/**` | 64 | 0.2 MB | `contracts/**` (a strict superset — see §3) |
| `uploads/module-wise-research/*.md` | 10 | 1.3 MB | The module docs' design sections (see §4) |

**The rule applied:** the uploads are *source material*, not authority. Where a
source file is older than the repo artifact (all of `uploads/contracts` is an
older snapshot), the repo artifact wins and the delta is recorded here.

## 2. The PRD workbook, sheet by sheet

`scripts/parse_prd_workbook.py` extracts all 13 sheets from the 79-page PDF
(Google Sheets export, so each printed page repeats its sheet header). Verified
against the PRD's own summary rows: the parsed per-release counts equal the
workbook's Version Roadmap sheet exactly (`154 / 21 / 630 / 214`).

| Sheet | Pages | Rows parsed | Repo artifact |
|---|---|---|---|
| Domains & Modules | 1–2 | 36 (5 domains, 36 modules) | `docs/00 §3`, `scripts/prd-workbook.json` |
| Master Backlog | 3–28 | **1020** | `scripts/prd-backlog.json`, every module doc §1/§16, `docs/99` App. A |
| V1 Execution | 47–52 | 175 | `docs/99` App. A.1/A.2 (V1.0 = 154 + V1.1 = 21) |
| Future Backlog | 54–63 | 844 | `docs/99` App. A.3/A.4 (V2.0 + V3.0) |
| Backlog Audit | 41 | 7 findings | `docs/39-prd-change-log.md` §2 |
| Feature Proposals | 42 | 14 | `docs/36-prd-feature-proposals.md` §1 |
| Version Roadmap | 43 | 4 releases | `docs/36-prd-feature-proposals.md` §2, `docs/99` §2 |
| Change Log | 44–46 | 67 entries | `docs/39-prd-change-log.md` §1 |
| Integration Map | 53 | 59 tools | `docs/34-tooling-registry.md` §3 |
| Tooling Register | 64–65 | 74 tools | `docs/34-tooling-registry.md` §3/§3.5 |
| Build vs Buy Rules | 66 | 28 (BVR-01..28) | `docs/34-tooling-registry.md` §2 |
| Data Dictionary | 67–69 | 68 enum values / 13 sections | `docs/39-prd-change-log.md` §3, `contracts/data/dictionary.md` |
| Open Questions | 70–77 | 205 | `docs/37-prd-open-questions.md` |
| Out Of Scope | 78–79 | 266 | `docs/38-prd-out-of-scope.md`, `docs/34` §3.5 |

### 2.1 What the re-parse changed

The legacy extraction (`scripts/prd-backlog.json` before 2026-09-19) had four
systematic defects, all fixed and now guarded by `--check`:

1. **8 requirements were missing entirely** — `PLT-01..08` (Platform
   Operations). Every PLT statement in the doc set ("PLT has no PRD rows") was
   wrong and is corrected (`docs/27 Part C.1`, `docs/99 §8`, `contracts/api/plt.md`).
2. **Module names leaked into `Feature Name`** (e.g. `Trading Platform Bridge
   Capability interface`) — cells are centred, so a wide module cell drifts left.
3. **Truncated cells** where a wrapped line started left of its column
   (`server- side`, `IP ,`, lost first words) — 203 rows recovered leading text.
4. **Owner lists were cut to the first name** (`BE-1` instead of `BE-1, FE-1`)
   in 114 rows, and 4 complexity values differed.

### 2.2 Open items the workbook itself reports

- **BRG-28** is a placeholder row with no release (audit ERROR) — see
  `docs/08-trading-bridge.md` §1 and `docs/39` §2.1.
- **Six "tool not in Integration Map" WARNs** for self-hosted platform pieces —
  they are documented as platform infrastructure in `docs/34 §3.2`, so the
  workbook warning is informational.
- **14 unreviewed proposals** (`PROP-0001..0014`, all status `New`) await a
  promote-or-reject decision — `docs/36` §4.

## 3. `uploads/contracts/**` — the older snapshot, file by file

64 files. The repo's `contracts/` is the maintained superset: **36** api specs
(vs 20), **26** SQL schemas (vs 3 drafts), **19 + 141** event schemas +
examples (vs 19 drafts), extended error taxonomy, and a permissions registry
roughly twice the size.

| Group | Files | Status vs repo | Notes |
|---|---|---|---|
| `contracts/README.md` | 1 | older (12.4 KB) | repo README is the pack index; the upload is the pre-split draft |
| `contracts/api/*.md` | 20 | **byte-identical** | the V1 binding specs were lifted unchanged |
| `contracts/data/dictionary.md` | 1 | superseded (30 KB → 5.4 KB + docs/32) | upload = the V1 Execution-sheet draft: 37 tables, 67 `TODO`/open-question markers. The repo split it into `contracts/data/dictionary.md` (canonical vocabulary) + `docs/32` (117 tables). Every upload table has a home in the repo schema family (e.g. `users`+`roles`+`permissions` → `identities` + `tenant_memberships` + policy; `trades`/`positions` → `08-brg.sql`/`09-evl.sql`) |
| `contracts/data/schemas/*.sql` | 3 | **not carried** (`_template`, `accounts`, `orders`) | draft DDL superseded by the 26 per-module schemas; kept in the uploads as history |
| `contracts/diagrams/*` | 17 | md same, **PNG zero-byte in uploads** | the repo carries the rendered PNGs (mermaid sources unchanged) |
| `contracts/errors/taxonomy.md` | 1 | draft → extended | repo: 66 V1 codes + 232 extended; upload has the V1 draft only |
| `contracts/events/catalog.md` | 1 | byte-identical | 141 post-V1 schemas were added on top |
| `contracts/events/payloads/*.json` | 19 | draft (0.3–0.5 KB) → schemas (1.4–2.0 KB) | the uploads are illustrative payload *sketches*; the repo carries full JSON Schemas + examples |
| `contracts/permissions/registry.md` | 1 | draft (5.3 KB) → registry (11.3 KB) | repo adds the post-V1 keys mined from module docs |

**Conclusion:** nothing in `uploads/contracts` is unread or unaccounted for;
where it is not byte-identical, the repo artifact is a superset and the deltas
above are the complete list. The only deliberate *deletions* are the three
draft SQL files, which the 26 per-module schemas replace.

## 4. `uploads/module-wise-research/*.md` — the module research, file by file

Ten files, 1.3 MB, all vendor evaluations and design explorations. Each was read
and its decisions carried into the module docs; the code samples (Python
snippets, docker-compose fragments, Redis layouts) were treated as *evidence*
for decisions, not as deliverables — the repo states the decision and the
interface, and leaves implementation to the module build.

| Research file | KB | Landed in | What was taken |
|---|---|---|---|
| `account-lifecycle.md` | 84 | `docs/07-account-lifecycle.md` | state machine, phase/spawn semantics, disable-then-close ordering, reconciliation job |
| `auth-authz-multi-tenancy.md` | 145 | `docs/02-identity-access.md`, `docs/03-tenant-management.md`, `docs/28-security.md` | Better Auth evaluation (superseded), org/tenant model, RBAC policy decision point, K8s NetworkPolicy isolation notes, auth API shape |
| `checkout-and-billing.md` | 143 | `docs/12-checkout-billing.md`, `docs/22-billing.md` | PSP comparison (Match2Pay/Interkasa/NOWPayments), hosted-flow PCI scope, pricing engine concept |
| `multi-tenant-billing.md` | 98 | `docs/22-billing.md`, `docs/34` §3 | Lago metering model, usage events → billable metrics, revenue-share engine shape (deferred to V3 per BVR rules) |
| `multi-tenant-management.md` | 179 | `docs/03-tenant-management.md`, `docs/25-migration.md` | tenant lifecycle, subdomain/domain mapping, entitlements, migration/cutover mechanics |
| `notification-service.md` | 149 | `docs/14-notifications.md` | Novu evaluation → in-house thin service, event→template mapping, channel matrix |
| `payout-system.md` | 109 | `docs/11-payout-system.md` | profit calculation engine, eligibility/approval flow, rails + reconciliation |
| `risk and rule engine.md` | 164 | `docs/09-evaluation-engine.md`, `docs/10-risk-management.md` | YAML rule DSL, cross-account hedging/consistency rules, real-time metric set, Redis hot-state layout |
| `risk-and-evaluation-engine.md` | 172 | `docs/09-evaluation-engine.md`, `docs/10-risk-management.md` | OPA/Rego policy evaluation, drawdown models, fraud detectors, Python engine skeleton |
| `trading-platform-bridge.md` | 62 | `docs/08-trading-bridge.md`, `docs/34` §3 | broker connector comparison (MetaApi/Darwinex ZeroMQ/cTrader/Nautilus), Kafka-vs-Redis-Streams decision, Prometheus bridge metrics |

**The near-duplicate pair is not duplicate:** `risk and rule engine.md` is the
*rule-authoring* view (YAML DSL, rule catalogue, Redis state) while
`risk-and-evaluation-engine.md` is the *evaluation* view (OPA/Rego, drawdown
models, detector implementation). Both are cited; neither supersedes the other.

## 5. What was deliberately not carried

- **Vendor code samples** (Kubernetes NetworkPolicy YAML, `revenue_share_engine.py`,
  `docker-compose.billing.yml`, Lago API call scripts): implementation detail
  for modules that are V2/V3 and were not chosen (Lago is deferred). The docs
  record the decision and the interface contract instead.
- **Third-party product names that the BVR rules rejected** (Lago, Novu,
  Kafka, Terraform, WooCommerce, Intercom/Zendesk, WordPress, DocuSign):
  retained as *rejected options* with reasons in `docs/34` §3.5 and
  `docs/39` §1, never as dependencies.
- **The uploads' 67 `TODO`/open-question markers** in the draft data dictionary:
  the questions themselves survive in `docs/37` (the workbook's own Open
  Questions register) where they have owners, and the schema decisions they
  gated are now stated in `docs/32` + `contracts/data/dictionary.md`.

## 6. Keeping this honest

```bash
python3 scripts/parse_prd_workbook.py             # re-extract every sheet
python3 scripts/parse_prd_workbook.py --check     # must print: OK: 1020 rows…
python3 scripts/build_prd_registers.py --check    # docs/36–39 match the JSON
python3 scripts/complete_contracts_pack.py --check-only   # coverage claims hold
```

If the PRD is revised: re-run the three commands, then re-check §2.1's defect
list (the `--check` diff lists any changed field), and update §2.1/§2.2 here.

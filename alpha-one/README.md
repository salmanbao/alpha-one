# Alpha One — Prop Firm as a Service (PFaaS)

**Engineering documentation set.** This repository is the single, navigable home for
building the Alpha One platform: a multi-tenant prop-firm-as-a-service system that lets
firms (tenants) sell trading challenges and funded accounts without owning trading
infrastructure.

The platform's first tenant is **FunderBlu**, which is migrating from TTS (their current
stack). Most "expected answer" decisions in the docs reference FunderBlu's current
operations.

---

## How to use this documentation

**If you are a developer joining the project:**

1. Read [docs/00-executive-brief.md](docs/00-executive-brief.md) — what we are building,
   who it is for, and the module catalog (15 min).
2. Read [docs/01-platform-architecture.md](docs/01-platform-architecture.md) — the system
   you will work in: topology, data flow, the twelve architectural decisions that constrain
   everything, and the module dependency graph (30 min).
3. Open your module's document (`docs/0N-<module>.md`). Every module document has the
   same skeleton so you can navigate predictably:
   *Purpose → Architecture → System design → Domain & lifecycle → Events →
   Error taxonomy → Data model → API (endpoints) → Security & compliance →
   Scalability → Build/buy & integrations → Implementation blueprint.*
4. Before writing code, check [contracts/](contracts/README.md) — the API + event
   contracts for your module are frozen there.
5. Find your task in [docs/99-development-phases.md](docs/99-development-phases.md) —
   phases are ordered so that no task has an unmet dependency, and each phase lists its
   exit criteria.

**Numbering convention:** `00–01` = foundation (read in order), `02–27` = modules
(any order, grouped by domain; `27` is the V3 ecosystem bundle), `28–35` =
cross-cutting reference material, `99` = the development plan (read last, then
constantly).

---

## Document map

### 0x — Foundation
| Doc | Contents |
|---|---|
| [00-executive-brief](docs/00-executive-brief.md) | Vision, personas, 5-domain / 36-module catalog, release trains, business context |
| [01-platform-architecture](docs/01-platform-architecture.md) | Topology, deployment, event backbone, twelve binding decisions (ADRs), module dependency graph, request & data lifecycles |

### 1x — Platform infrastructure (domain D4) — build in this order
| Doc | Module |
|---|---|
| [02-identity-access](docs/02-identity-access.md) | AUTH — auth, authorization, multi-tenant identity |
| [03-tenant-management](docs/03-tenant-management.md) | TEN — tenant lifecycle, white-label, entitlements |
| [04-gateway-events](docs/04-gateway-events.md) | GW + EVT — API gateway middleware, event bus, outbox, webhooks |
| [05-ledger-audit](docs/05-ledger-audit.md) | LED + AUD — double-entry ledger, audit & compliance |
| [06-devops-deployment](docs/06-devops-deployment.md) | OPS — infra, CI/CD, environments, observability, DR |
| [21-platform-console](docs/21-console.md) | CON — platform (super-admin) console |

### 1x — Core trading engine (domain D1) — build in this order
| Doc | Module |
|---|---|
| [07-account-lifecycle](docs/07-account-lifecycle.md) | LCC — trader account state machine, phases, activation, cutover |
| [08-trading-bridge](docs/08-trading-bridge.md) | BRG — broker connectors (MT5/MT4/cTrader), sync, enforcement, provisioning |
| [09-evaluation-engine](docs/09-evaluation-engine.md) | EVL — rule packs, verdicts, drawdowns, day boundaries |
| [10-risk-management](docs/10-risk-management.md) | RSK — fraud/anti-gaming detection, cases |
| [11-payout-system](docs/11-payout-system.md) | PAY — payout requests, approvals, rails, reconciliation |

### 1x — Trader experience (domain D2)
| Doc | Module |
|---|---|
| [12-checkout-billing](docs/12-checkout-billing.md) | CHK — checkout, pricing, orders, payment providers |
| [13-kyc-verification](docs/13-kyc.md) | KYC — verification flows, provider adapters, document handling |
| [14-notifications](docs/14-notifications.md) | NOT — channels, templates, in-app, preferences |
| [15-document-generation](docs/15-documents.md) | DOC — certificates, statements, PDFs, storage |
| [16-trader-dashboard](docs/16-trader-dashboard.md) | TD — trader portal (FE) |
| [26-mobile-journal-education-community](docs/26-mobile-apps.md) | MOB, JRN, EDU, CHT — secondary trader-surface modules (V2+) |

### 1x — Tenant operations (domain D3)
| Doc | Module |
|---|---|
| [17-admin-panel](docs/17-admin-panel.md) | ADM — tenant admin panel |
| [18-support-inbox](docs/18-support.md) | SUP — tickets, SLAs, Telegram intake |
| [19-analytics-bi](docs/19-analytics.md) | ANA — read models, reports, KPIs |
| [20-crm-communications](docs/20-crm.md) | CRM — segments, campaigns, sequences |
| [25-migration-tooling](docs/25-migration.md) | MIG — TTS → Alpha One cutover & data migration |

### 1x — Ecosystem & growth (domain D5)
| Doc | Module |
|---|---|
| [22-tenant-billing](docs/22-billing.md) | BIL — we bill the tenants (usage metering, invoicing) |
| [23-affiliate-system](docs/23-affiliates.md) | AFF — referrals, commissions |
| [24-website-cms-competitions](docs/24-cms-competitions.md) | CMS + CMP — tenant site, landing pages, contests |
| [27-ecosystem-advanced](docs/27-ecosystem.md) | SDK, DVP, TRD, PLT, CS — BYO SDK, developer portal, advanced trading, platform ops, customer success (V3) |

### 2x — Cross-cutting reference
| Doc | Contents |
|---|---|
| [28-security-compliance](docs/28-security.md) | Security model, threat model, PCI/KYC/GDPR boundaries, encryption, secrets |
| [29-scalability-operations](docs/29-scalability.md) | Capacity model, hot paths, load targets, failure modes, runbooks |
| [30-error-taxonomy](docs/30-error-taxonomy.md) | Global error contract + per-module error code registries |
| [31-event-catalog](docs/31-event-catalog.md) | Every domain event, its schema, producer, consumers, delivery semantics |
| [32-database-design](docs/32-database-design.md) | Consolidated schema: per-domain tables, indexes, partitioning, retention |
| [33-glossary](docs/33-glossary.md) | The shared language: every precise term, its owner doc, identifier rules |
| [34-tooling-registry](docs/34-tooling-registry.md) | **Binding** build/buy decisions: the 28 BVR rules, the integration map, license policy, adapter registry |
| [35-testing-strategy](docs/35-testing-strategy.md) | Test pyramid, the 16-invariant suite, contract gates, load/security/migration assurance per milestone |

### 3x — PRD registers (generated from the workbook)
| Doc | Contents |
|---|---|
| [36-prd-feature-proposals](docs/36-prd-feature-proposals.md) | The 14 `PROP-*` proposals (all unreviewed) + the release roadmap with its gates and counts |
| [37-prd-open-questions](docs/37-prd-open-questions.md) | All 205 workbook questions by module — 8 answered (binding), 197 open, each with owner + deadline — plus the 16 design-review questions (**D1–D5**, **P1–P4**, **D10–D11** answered; **D6–D9**, **D12** open with recorded defaults) raised by the AUTH/TEN evaluations and the deprovisioning review |
| [38-prd-out-of-scope](docs/38-prd-out-of-scope.md) | The 266 deliberate exclusions by module — the "do not build this" register |
| [39-prd-change-log](docs/39-prd-change-log.md) | The workbook's 67-row change log, the 7 backlog-audit findings, and the 13 controlled vocabularies |
| [40-uploads-coverage](docs/40-uploads-coverage.md) | Source traceability: every `uploads/` file, where it landed, and what stayed open |
| [41-auth-ten-open-source-evaluation](docs/41-auth-ten-open-source-evaluation.md) | AUTH + TEN: every candidate open-source identity/authorization/multi-tenancy solution scored against the PRD rows, the mandated picks re-examined, and the nine decisions they produced (ZITADEL + Casbin + Postgres RLS) |
| [42-auth-ten-gap-analysis](docs/42-auth-ten-gap-analysis.md) | Second-pass AUTH/TEN review: 20 findings (G1–G20) against the ZITADEL/Casbin/RLS decisions, all closed in-pass — the artifact behind the `docs/02` §3.x resolutions and the contract-pack fixes |
| [43-idp-deprovisioning](docs/43-idp-deprovisioning.md) | Third-pass design: near-real-time IdP deprovisioning (`idp-sync` pull consumer + durable inbox over the event log), delivery-failure handling, the 15-min token-lifetime bound, reconciliation as the safety net, the self-service deletion posture, and the industry precedent (decisions D10–D12) |
| [44-auth-multitenancy-review](docs/44-auth-multitenancy-review.md) | Fourth-pass AUTH/AuthZ/multi-tenancy review: 13 findings (G21–G33) across identity↔IdP cardinality (one person = one user *per org*), the ratified role→permission-key binding contract (`roles.yaml`), Casbin storage/reload/fail-closed boot, the RLS exemption model, refresh-token ownership and the request-path status gate — all closed in-pass (decisions D13–D18) |

> Regenerate with `python3 scripts/parse_prd_workbook.py` →
> `python3 scripts/build_prd_registers.py` (both have `--check` modes). The
> machine-readable mirror of every PRD sheet is `scripts/prd-workbook.json`.

### Contracts
| Path | Contents |
|---|---|
| [contracts/README.md](contracts/README.md) | How to read the contract pack, versioning rules |
| [contracts/shared/](contracts/shared/) | Shared OpenAPI components: envelopes, errors, pagination, event envelope |
| [contracts/*.openapi.yaml](contracts/) | One OpenAPI 3.1 spec per module (26 specs, 434 operations) |
| [contracts/api/](contracts/api/) | Human-readable endpoint contracts per module (36: 20 binding V1 + 16 provisional post-V1) |
| [contracts/events/](contracts/events/) | V1 baseline catalog + payloads; post-V1 topic schemas (141 events) + example fixtures |
| [contracts/data/](contracts/data/) | Field dictionary + per-module SQL schemas (26, split from docs/32) |
| [contracts/errors/](contracts/errors/) | Error registry: 66 binding V1 codes + 232 provisional extended |
| [contracts/permissions/](contracts/permissions/) | Permission registry: 100 `resource.action` keys (31 binding V1 + 69 provisional) |
| [contracts/diagrams/](contracts/diagrams/) | Architecture/lifecycle diagrams (source + renders) |

### 99 — The plan
| Doc | Contents |
|---|---|
| [99-development-phases](docs/99-development-phases.md) | **The** build order: Phase 0 → Phase 5, workstreams, per-phase task lists with dependencies, exit criteria, cutover plan, Req-ID-by-phase index (App. A), module build-order checklist (App. B) |

---

## Conventions used throughout

- **Money** is always integer minor units (cents/paisa) in APIs and the ledger;
  `Decimal` in the evaluation engine; never float.
- **Timestamps** are epoch milliseconds (int64) in events and APIs. The *broker
  attested* timestamp is authoritative for trading data; platform time is for
  everything else.
- **Tenant scoping**: every domain row carries `tenant_id`. Isolation is enforced at
  the repository layer and verified by the shared-schema guard (see
  [01-platform-architecture §7](docs/01-platform-architecture.md)).
- **Ids**: ULIDs (26-char Crockford base32) for all entities and events; UUIDv7 only
  where an external system requires it.
- **API versioning**: URL-based (`/v1/`), additive changes only inside a version.
- **Docs cite requirements** as `MODULE-NN` (e.g. `BRG-07`) referring to the PRD master
  backlog; module docs list which requirements they cover.
- **The PRD backlog is the scope authority**: 1020 rows (154 V1.0 + 21 V1.1 + 630 V2.0
  + 214 V3.0 + 1 unassigned — BRG-28, the workbook's open placeholder),
  machine-readable in `scripts/prd-backlog.json`. Every module doc's §1
  coverage claim is cross-checked against it (`complete_contracts_pack.py --check-only`),
  and docs/99 Appendix A maps every row to exactly one phase.

## Source material (superseded by this set)

The individual research reports (`trading-platform-bridge.md`,
`risk-and-evaluation-engine.md`, `risk and rule engine.md`, `account-lifecycle.md`,
`payout-system.md`, `checkout-and-billing.md`, `multi-tenant-billing.md`,
`multi-tenant-management.md`, `notification-service.md`,
`auth-authz-multi-tenancy.md`, and the *Alpha One PRD* spreadsheet) were consolidated
into this documentation set. Where they disagreed with the PRD's Tooling Register or
Open-Questions sheet (e.g. Kafka vs Redis Streams, Kubernetes vs Compose, Auth0 vs
in-house auth), **the PRD decisions win** and are recorded as ADRs in
[01-platform-architecture §3](docs/01-platform-architecture.md).

# 00 — Executive Brief

## 1. What we are building

**Alpha One** is a **Prop Firm as a Service (PFaaS)** platform. A prop firm buys
Alpha One and, without owning trading infrastructure, offers traders:

- **Challenges** (evaluation accounts with rules: drawdown targets, profit targets,
  time limits, trading rules),
- **Funded accounts** (real P&L, profit split, payouts),
- and everything around them: checkout, KYC, payouts, certificates, support,
  branding, billing, analytics.

Traders connect to **real broker accounts** (MetaTrader 5 via MetaApi in V1; MT4 and
cTrader later) that the platform provisions, monitors, and enforces rules on in near
real-time.

Alpha One is **multi-tenant**: many prop firms run on one shared instance, each
isolated, branded, and independently configured (rule packs, challenges, pricing,
payout policy, support).

> **First tenant: FunderBlu.** FunderBlu is migrating from TTS (their current
> provider). Every ambiguous default in this document set — "what does a prop firm
> usually do?" — is answered from FunderBlu's current TTS operations unless a
> decision is marked otherwise.

## 2. The business model

Two-sided revenue:

| Side | Description | Module |
|---|---|---|
| **Traders → tenant** | Traders pay tenants for challenges, add-ons, activation fees, payouts | [12-checkout-billing](12-checkout-billing.md), [11-payout-system](11-payout-system.md) |
| **Tenants → platform** | Tenants pay Alpha One for subscription + usage (accounts, payouts, API calls) | [22-tenant-billing](22-billing.md) |

The platform's unit economics depend on: challenge pass rates, payout volume vs
challenge revenue, broker cost per account (MetaApi ≈ $50–100/mo per funded account
in our current estimate — the single biggest cost driver), and churn. These are why
the PRD tracks them as first-class analytics ([19-analytics-bi](19-analytics.md)).

## 3. Personas

| Persona | Description | Primary surfaces |
|---|---|---|
| **Trader** | Buys a challenge, trades, gets funded, requests payouts | Trader dashboard (TD), mobile, email |
| **Tenant admin / operator** | Runs the firm on the platform: configures challenges, reviews KYC & payouts, manages traders | Admin panel (ADM) |
| **Tenant risk officer** | Reviews rule breaches, fraud cases, loss cohorts | ADM risk queues, ANA reports |
| **Tenant support agent** | Answers tickets, communicates with traders | Support inbox (SUP), ADM |
| **Tenant owner** | Business KPIs, finance, team management | ADM, ANA |
| **Platform operator (Alpha One staff)** | Runs the platform: onboards tenants, health, incidents, tenant billing | Platform console (CON) |
| **Platform tenant-admin (super-admin)** | Provisioning, plan assignment, entitlements, suspension | CON |
| **Developer / integrator** | Builds on the tenant's API or BYO integration | Developer portal (DVP), SDK (SDK) |
| **Affiliate** | Refers traders, earns commissions | AFF portal (V3) |

## 4. Domains and module catalog

36 modules in 5 domains. "Rel" is the release where the module ships its first
meaningful scope (see §6 for release semantics; full requirement-level mapping in
`docs/99-development-phases.md`).

### D1 — Core trading engine (the heart of the platform)
| Module | Name | One line | Rel |
|---|---|---|---|
| **BRG** | Trading Platform Bridge | Provisions and syncs real broker accounts (MT5/MetaApi V1); enforcement hooks; the platform's hands in the trading world | 1.0 |
| **LCC** | Account Lifecycle | The trader-account state machine: purchase → evaluation → funding → funded → payout/breach states; phase transitions | 1.0 |
| **EVL** | Evaluation & Rule Engine | Rule packs (drawdown, daily loss, targets, time, conduct rules), verdicts, day-boundary rollover, evaluation state | 1.0 |
| **RSK** | Risk Management | Post-activity fraud & anti-gaming detection (news trading, hedging, latency, IP/device clusters), risk cases | 1.0 (detection V2) |
| **PAY** | Payout System | Payout requests, eligibility, approval workflow, payment rails, ledger entries, reconciliation | 1.0 |

### D2 — Trader experience
| Module | Name | One line | Rel |
|---|---|---|---|
| **TD** | Trader Dashboard | The trader portal: accounts, P&L, credentials, purchases, payouts, KYC, notifications | 1.0 |
| **CHK** | Checkout & Billing (trader side) | Challenge purchase flow, payment provider adapters, orders, refunds | 1.0 |
| **KYC** | KYC & Verification | Identity verification: document upload, provider (Veriff) workflow, manual review | 1.0 |
| **NOT** | Notification Service | Event-driven notifications: email, in-app, (later Telegram/WhatsApp); templates; preferences | 1.0 |
| **DOC** | Document Generation | Certificates, trade statements, invoices — templated PDFs, storage | 1.0 (certs/statements) |
| **JRN** | Trading Journal | Trader's private journal and performance analysis | 2.0 |
| **EDU** | Education Hub | Lessons, challenges of the week, completion tracking | 2.0 |
| **MOB** | Mobile App | Native mobile companion (React Native) | 2.0 |
| **CHT** | Community & Live Chat | Community space, trader chat, live support handoff | 2.0 |

### D3 — Tenant operations
| Module | Name | One line | Rel |
|---|---|---|---|
| **ADM** | Admin Panel | The tenant's operational cockpit: traders, accounts, KYC/payout/risk queues, settings | 1.0 (account list + core queues) |
| **SUP** | Support Inbox | Ticketing, SLAs, canned responses, Telegram intake, escalation | 1.0 (basic) |
| **ANA** | Analytics & BI | Read models, KPI dashboards, reports, exports | 1.0 (foundation + live KPIs) |
| **CRM** | CRM & Communications | Trader segmentation, campaigns, email sequences, lifecycle automation | 2.0 |
| **MIG** | Migration Tooling | TTS → Alpha One: data migration, account cutover, parallel-run reconciliation | 1.0 (for FunderBlu) |

### D4 — Platform infrastructure
| Module | Name | One line | Rel |
|---|---|---|---|
| **AUTH** | Identity, AuthN/AuthZ | Multi-tenant auth (Better Auth), roles & policies (Cerbos), API keys, 2FA, sessions | 1.0 |
| **TEN** | Tenant Management | Tenant lifecycle, white-label (branding, domain), feature entitlements, settings | 1.0 |
| **EVT** | Event Bus & Webhooks | Redis Streams backbone, outbox relay, consumer contracts, tenant outbound webhooks | 1.0 |
| **GW** | API Gateway | In-app gateway layer behind Cloudflare: tenant resolution, auth, rate limits, quotas, idempotency, error contract | 1.0 |
| **LED** | Ledger & Accounting | Double-entry ledger for all money movement: orders, payouts, provider fees | 1.0 |
| **AUD** | Audit & Compliance | Append-only, hash-chained audit trail; access audit; retention | 1.0 (append-only) |
| **OPS** | DevOps & Deployment | Hetzner infra, Docker Compose, CI/CD (GitHub Actions), environments, observability, DR | 1.0 |
| **CON** | Platform Console | Alpha One's own console: tenant provisioning, plans, health, usage | 1.0 |

### D5 — Ecosystem & growth
| Module | Name | One line | Rel |
|---|---|---|---|
| **BIL** | Tenant Billing (platform side) | We bill tenants: plans, usage metering, invoicing, dunning | 3.0 |
| **AFF** | Affiliate System | Referrals, attribution, commissions, fraud checks, payouts | 3.0 |
| **CMS** | Website & CMS | Tenant's public site: landing pages, pricing pages, blog | 2.0 |
| **CMP** | Competitions & Gamification | Trading contests, leaderboards, loyalty points | 2.0 |
| **SDK** | BYO Integration SDK | Let tenants run their own front-end against our API | 3.0 |
| **DVP** | Developer Portal | Tenant public API, API keys, webhooks, sandbox, docs | 2.0 (keys/webhooks) |
| **PLT** | Platform Operations | Cross-tenant platform analytics, capacity, multi-tenant ops tooling | 2.0 |
| **CS** | Customer Success | Tenant NPS, health scoring, churn prediction, QBRs | 3.0 |
| **TRD** | Advanced Trading | Advanced order types, copy-trade feeds, algo execution for tenants | 3.0 |

> Modules marked **V3** (BIL, AFF, SDK, CS, TRD) still get a full design doc now so
> architecture decisions (schemas, event contracts) are made while the foundations are
> fresh — but their build starts in Phase 5.

## 5. Scale assumptions (design targets)

| Metric | V1 target | V2 target | Notes |
|---|---|---|---|
| Tenants | 1–5 | 25–50 | FunderBlu first |
| Active traders (registered) | ~5k | ~50k | Per tenant aggregate |
| Concurrent broker accounts | ~1k | ~10k | 1 funded/eval account = 1 broker account |
| Sync ticks (positions/equity) | 10/s sustained | 100/s | MT5 polling-driven, bursty |
| Peak event throughput | 200 msg/s | 2k msg/s | Redis Streams |
| Daily orders (challenge purchases) | ~200 | ~5k | PK/IN/US crypto + card |
| Payouts/day | ~50 | ~500 | Manual approval at launch |
| MT5 accounts on MetaApi | ~300 | ~5k | **Cost driver** — see 09 & 29 |

These drive the capacity model in [29-scalability-operations](29-scalability.md).

## 6. Release trains

| Release | Codename | Content (one line) |
|---|---|---|
| **V1.0** | Core | Everything a tenant needs to onboard traders end-to-end: purchase → trade → evaluate → fund → pay out. (137 P0 requirements) |
| **V1.1** | Plus | Polished V1: email verification, staff invites, admin queue polish, real-time KPIs, invoice PDFs. |
| **V2.0** | Scale | Operations at scale: full ADM, analytics suite, tenant API & webhooks, mobile, community, competitions, CMS, migration hardening. |
| **V3.0** | Ecosystem | Platform business: tenant self-serve billing, affiliates, developer SDK/portal, advanced trading, customer success tooling. |

**Every requirement in the PRD carries one of these phase tags.** The development plan
([99-development-phases](99-development-phases.md)) maps requirements → phases →
workstreams with dependencies, so a developer can always answer: *what do I build
next, what blocks me, and what does "done" mean?*

## 7. Team & stakeholders (planning assumptions)

| Role | Count | Scope |
|---|---|---|
| Tech lead (you, the user) | 1 | Architecture, bridge, integrations, cutover |
| Backend engineers | 2 | BE-1: bridge, lifecycle, evaluation. BE-2: checkout, billing, notifications, admin APIs |
| Frontend engineers | 2–3 | FE-01: trader dashboard. FE-1/FE-2: admin, console, marketing site |
| DevOps | 1 | Infra, CI/CD, environments, observability |
| FunderBlu stakeholders | COO, Risk Owner, Ops Owner, Product Owner, Marketing, Legal | Acceptance of V1 scope, cutover sign-off |

With 4–5 engineers, the plan in `docs/99-development-phases.md` targets **V1.0 in
roughly 4 months of parallel work** (Phases 0–2), V1.1 immediately after, V2.0 the
following two quarters.

## 8. Non-negotiables (read before designing anything)

1. **Postgres is the system of record.** Events, commands, ledger, audit — all
   durable state lives in Postgres. Redis is for streams/sessions/caching only and is
   never the source of truth.
2. **Tenant isolation is a correctness property, not a best effort.** Every query is
   tenant-scoped; the integration test suite proves it (shared-schema guard).
3. **Money never floats.** Integers (minor units) in APIs and the ledger; `Decimal`
   in evaluation math; exact reconciliation between broker, ledger, and payouts.
4. **Idempotency everywhere.** Every write endpoint accepts an idempotency key; every
   event consumer tolerates redelivery (at-least-once bus).
5. **The broker is the source of truth for trading state.** We do not trust our own
   copy. Sync gaps are detected, alerted, and never silently filled.
6. **Boring technology.** The platform must be operable by a 1-person DevOps team:
   Docker Compose on Hetzner, no Kubernetes, no Kafka, no microservice sprawl.
   "Monolith-lite": one deployable per concern (bridge, core API, workers), shared
   Postgres.
7. **Everything auditable.** Sensitive reads and all state changes write to the audit
   trail. If it isn't audited, it doesn't ship.
8. **Contracts freeze early.** API + event contracts are in `contracts/` and change
   only by explicit versioning. Bridge ↔ engine ↔ ledger interop is contract-tested.

# 34 — Tooling Registry (binding build/buy decisions)

> Extracted 2026-09-19 from the PRD **Tooling Register** (74 tools,
> machine-readable in `scripts/prd-workbook.json`), the **Integration Map**
> (59 tools), the **28 BVR rules**, and the **Out Of Scope** sheet
> (266 items — the product-scope mirror is `docs/38-prd-out-of-scope.md`).
> This document is binding: §2 rules constrain every module doc and every PR (a violation
> fails review per the rule's enforcement column). §3 is the signup +
> adoption checklist. Tool *usage* details live in the owning module doc;
> this doc owns the *decisions*.
>
> Requirement coverage: cross-cutting (no PRD module owns tooling; rules cite
> the Req IDs they serve).

## 1. How to use this document

- **Before adding any dependency** (npm/go/rust package with a network or
  license footprint, SaaS trial, self-hosted service): read §2. If a rule
  covers it, the rule decides. If no rule covers it, BVR-15 applies: add the
  tool to §3 first, then merge the PR.
- **Before building infrastructure** (queues, flags, webhooks, PDFs, auth,
  search, billing): check §2 — most infrastructure classes have a
  *do-not-build* verdict with the mandated tool.
- **Phase planning**: §7 maps every tool to the phase that adopts it; §9
  lists the signups that must start in Phase 0 (one is the #1 schedule risk).
- **License questions**: §4. Anything not MIT/Apache-2.0/BSD/MPL-2.0/
  PostgreSQL-License needs the review BVR-17/18 demand.

## 2. The 28 build-vs-buy rules (BVR-01..28)

Binding. "Enforced by" = who/what stops a violation.

| Rule | Verdict (do not build → use) | Applies to | Enforced by |
|---|---|---|---|
| BVR-01 | Do not build SMTP/mail delivery → **Postmark** | any email send | code review (iface NOT-03) |
| BVR-02 | Do not build a PSP or touch raw card data → **hosted flows** | checkout, refunds, tenant billing | code review + PCI scope (iface CHK-04) |
| BVR-03 | Do not build identity verification → **Veriff** + manual fallback | KYC | code review (iface KYC-01) |
| BVR-04 | Do not build a broker Manager API client → **MetaApi** (or Brokeree) behind BRG-01 | MT5 provisioning, sync, enforcement | code review (iface BRG-01) |
| BVR-05 | Do not build WAF/DDoS/bot filter → **Cloudflare** at the edge | all HTTP ingress | architecture review (OPS-15, GW-20) |
| BVR-06 | Do not build a secret manager → **SOPS + age** in V1 | all secrets | code review (OPS-09) |
| BVR-07 | Do not build a PDF renderer → **Puppeteer** | certificates, receipts, statements | code review (DOC-01) |
| BVR-08 | Do not build an ORM/migration runner → **Drizzle ORM** (Prisma = acceptable fallback) | all DB migrations | code review (OPS-06) |
| BVR-09 | No message broker other than **Redis Streams** in V1 | events, queue, commands | architecture review (Kafka/Redpanda/NATS out of scope) |
| BVR-10 | No Kubernetes/Nomad/Swarm in V1 → **Docker Compose** | orchestration | architecture review |
| BVR-11 | No commercial APM → **Prometheus + Grafana + Loki + Sentry** | observability | architecture review |
| BVR-12 | No standalone gateway → **in-app middleware** behind Cloudflare | edge/routing | architecture review |
| BVR-13 | No third analytics/BI tool in V1 → **read models + fixed reports** | reporting | architecture review |
| BVR-14 | No managed IdP → **self-hosted Better Auth** + our AUTH-13 permission engine | auth & identity | architecture review |
| BVR-15 | Any new third-party dependency → **register here before merge** | all dependency PRs | code review |
| BVR-16 | Every external integration sits behind a **defined adapter interface** | payments, KYC, broker, email, storage, tax | code review (§5 table) |
| BVR-17 | Before upgrading Redis beyond 7.2 → **licence review** | Redis version | change request (7.4+ = RSALv2/SSPLv1) |
| BVR-18 | No self-hosted fair-code tools without **licence review** | n8n, Sentry self-host, etc. | change request (prefer MIT/Apache/BSD/MPL/PG) |
| BVR-19 | Do not build a job queue/scheduler → **BullMQ** | BRG-07/08, EVL-05, OPS-17/27 | code review |
| BVR-20 | Do not build feature flags → **Flipt** | TEN-10, CON-31 | code review |
| BVR-21 | No secrets-manager-with-UI in V1 (SOPS+age suffices) → **Infisical** is the V2 upgrade path | OPS-09 | change request |
| BVR-22 | Do not build consent banners → **c15t** self-hosted (not in V1) | portals, tenant sites | code review |
| BVR-23 | Do not build an RBAC policy point before **evaluating Cerbos** for AUTH-13 | AUTH-13/14 | architecture review (Cerbos = EVALUATE) |
| BVR-24 | Do not build webhook dispatch/retry/signing/logs → **Hook0** | EVT-11/13/14/15 | code review |
| BVR-25 | **BullMQ Dashboard** for job observability (no custom job UI) | OPS-17, CON-21 | code review |
| BVR-26 | Do not build SOC2/ISO evidence collection → **Comp AI or Openlane** | AUD-17/18 | compliance review |
| BVR-27 | Do not build e-signature → **Documenso** | DOC-12 | code review |
| BVR-28 | **Own the semantics; rent the runtime.** Rule semantics, versions, metric definitions, breach decisions, state transitions, enforcement policy, audit/replay are OURS. Buy/integrate only runtime, broker connectivity, provisioning, streaming, execution infra. Never let a proprietary vendor be the final authority for an account breach — vendors sit underneath BRG-01. | EVL, LCC, BRG, AUD | architecture review |

## 3. Integration map (every third-party dependency)

Status vocabulary: **SIGNED** (contract/keys exist), **SELF-HOSTED**
(runs on our Hetzner box), **EVALUATING** (spike before adoption —
§6), **DEFERRED** (decided, later phase), **NOT STARTED** (signup
needed — §9), **REJECTED** (never adopt).

### 3.1 Must-integrate — commercial SaaS (V1.0 unless noted)

| Tool | What it does | Serves | Cost | Status | Owner | Action needed |
|---|---|---|---|---|---|---|
| MetaApi | MT5 provisioning, balance/equity/position sync, execution, enable/disable | BRG-01/02/05/07/08/10/11/14/43/44 | $50–100/mo per active account | NOT STARTED | Shadab | **Sign day 1.** Sandbox keys. Confirm provisioning coverage before Phase 1. #1 schedule risk (docs/99 §1). |
| Veriff | Identity verification, document checks, liveness | KYC-01/02/06/07/08/24 | per verification | SIGNED (FunderBlu contract) | FunderBlu COO | Confirm keys work. Confirm webhooks included (KYC-05). Build adapter. |
| Match2Pay | Card + local payments (PK/IN) | CHK-04/06/07/08 | per transaction | NOT STARTED | BE-2 | Sign week 1. API keys. Test hosted checkout. Settlement report format. |
| Interkasa | Secondary local rail, same iface | CHK-04/05 | per transaction | NOT STARTED | BE-2 | Sign as secondary behind CHK-04 iface. |
| NOWPayments | Crypto (BTC/ETH/USDT), webhooks, auto-conversion | CHK-04/05 | ~1% | NOT STARTED | BE-2 | Sign week 2. Confirm TRC20/ERC20/BEP20. |
| Postmark | Transactional email (best deliverability) | AUTH-05, NOT-03/04/05 | $15/mo per 10k | NOT STARTED | BE-2 | Sign day 1. Production choice for payout + reset. |
| Cloudflare | DNS, CDN, WAF, DDoS, edge | TEN-02/18, GW-01/20, OPS-15, DOC-06 | free tier | NOT STARTED | DevOps | Edge for every tenant domain. Confirm Cloudflare-for-SaaS for custom domains. |
| Cloudflare R2 | Tenant-scoped object storage, zero egress | TEN-18, DOC-06 | free 10 GB, then per GB | NOT STARTED | DevOps | Set up week 2 (DOC-01). Tenant-prefixed keys. |
| GitHub Actions | CI/CD | OPS-03/04/36 | free/$4 | SIGNED | DevOps | Pipelines week 1. SOPS secrets integration. |
| Better Auth | Auth foundation (registration, login, sessions, MFA, OAuth) | AUTH-01..43 | free | EVALUATING | BE-1 | Phase-0 spike: confirm org plugin fits multi-tenant orgs (docs/02 §2). |
| Cerbos | RBAC policy decision point | AUTH-13/14 | free self-hosted | EVALUATING | BE-2 | Evaluate before writing AUTH-13 logic (BVR-23). |
| Resend | TS email SDK + React Email | NOT-03/04/05 | $20/mo per 50k | EVALUATING | BE-2 | Dev + non-critical. Postmark stays production. Same iface. |
| Sentry | Error tracking + stack traces | OPS-11 (V2.0) | free 5k/mo | NOT STARTED | DevOps | Add to every service day 1. Alert routing per OPS-39. |

### 3.2 Self-hosted platform (Hetzner, Compose — V1.0 unless noted)

| Tool | What it does | Serves | Status | Owner | Notes |
|---|---|---|---|---|---|
| Hetzner (dedicated, AX line) | Compute for the whole Compose stack | OPS-02/07/23/37 | NOT STARTED | DevOps | One box V1. Document sizing + headroom (OPS-37). |
| PostgreSQL 16 | System of record (domain, outbox, log, ledger, audit) | EVT-01/08/20, LED, AUD | SELF-HOSTED | DevOps | WAL archiving + daily backups + restore drill (OPS-38). |
| Redis 7.2 | Sessions, rate limits, Streams, BullMQ store | AUTH-07, GW-05, EVT-02/22, OPS-26 | SELF-HOSTED | DevOps | AOF on. **Never >7.2 without licence review** (BVR-17). |
| Docker + Compose | Containerization + V1 orchestration | OPS-01/02/37 | SELF-HOSTED | DevOps | Compose is the V1 source of truth (BVR-10). CPU/mem limits per service. |
| PgBouncer | PG connection pooling (tx mode) | OPS-25 | SELF-HOSTED | DevOps | Per-service pool sizing. |
| SOPS + age | Secrets at rest, injected at deploy | OPS-09 | SELF-HOSTED | DevOps | No Vault in V1 (BVR-06). Infisical is the V2 path. |
| Drizzle ORM | **Primary** ORM (SQL-fluent, pure-SQL migrations) | OPS-06 | EVALUATING | BE-1, DevOps | Adopt (BVR-08). Tenant-scoped query shape control. |
| Prisma | Typed ORM, declarative schema — **fallback only** | OPS-06 | EVALUATING | BE-1 | Only if team prefers declarative schema. Never primary. |
| BullMQ | Job queue + scheduler (sync, reconcilers, reports) | BRG-07/08, EVL-05, OPS-17/27 | EVALUATING | BE-1 | Adopt (BVR-19). + Dashboard for obs. |
| Puppeteer | HTML→PDF (certificates) | DOC-01 | SELF-HOSTED | BE-2 | No DocRaptor/PDFMonkey (BVR-07). html-pdf-lite is the V2 candidate. |
| BullMQ Dashboard | Queue metrics UI (embeddable React) | OPS-17, CON-21 (V2.0) | EVALUATING | BE-1 | Embed in admin panel (BVR-25). No custom build. |
| Prometheus + Grafana + Loki + OTel | Metrics, dashboards, logs, tracing | OPS-10/12 (V2.0) | SELF-HOSTED | DevOps | No commercial APM (BVR-11). Verify Grafana/Loki AGPL distribution. |
| TradingView Lightweight Charts | Equity/P&L charts (~45 KB) | TD-06/21 (V2.0) | EVALUATING | FE-1 | + Recharts for admin bars/lines. Confirm data contract pre-build. |
| Flipt | Feature flags (Git-native, declarative) | TEN-10, CON-31 (V2.0) | EVALUATING | BE-2 | Adopt (BVR-20). Per-tenant + platform rollouts. |
| Hook0 | Webhook delivery (retry, HMAC, logs, breakers) | EVT-11/13/14/15 (V2.0) | EVALUATING | BE-1 | Adopt with outbound webhooks (BVR-24). AGPL — verify. |
| Uptime Kuma | External uptime probes (independent box) | OPS-31 (V2.0) | EVALUATING | DevOps | Detects total outages (runs off-platform). |

### 3.3 V2.0 consider-later adoptions

| Tool | What it does | Serves | Status | Owner | Notes |
|---|---|---|---|---|---|
| UnKey | API key mgmt (issue/rotate/revoke, per-key limits, analytics) | AUTH-21, GW-16 | EVALUATING | BE-2 | Adopt with tenant API keys. AGPL — verify. |
| Logto | Multi-tenant IdP (alt. to Better Auth) | AUTH-01..43 | EVALUATING | BE-1 | Only if Better Auth hits a wall (orgs/SCIM). |
| c15t | Consent management (self-hosted) | TD-01, ADM-01, NOT-02 | EVALUATING | FE-1 | With CMS (V3) or analytics/chat tools (BVR-22). Not V1. |
| Infisical | Secrets manager + audit trails | OPS-09 | DEFERRED | DevOps | V2 upgrade from SOPS when audit trails required (BVR-21). |
| html-pdf-lite | Faster/smaller HTML→PDF | DOC-01/13/14 | EVALUATING | BE-2 | Drop-in Puppeteer replacement if memory bites. |
| NATS JetStream | Event bus upgrade path | EVT-02/06/20 | DEFERRED | BE-1 | Only when services outgrow Streams (6–7+). Never V1. |
| Traefik | Edge gateway (V2) | GW-01, OPS-02 | DEFERRED | DevOps | Only when gateway needs its own service (BVR-12 holds V1). |
| Documenso | E-signature (self-hosted) | DOC-12 | EVALUATING | BE-2 | Adopt at DOC-12 (BVR-27). Replaces DocuSign. |
| Comp AI | SOC2/ISO evidence automation | AUD-17/18 | EVALUATING | BE-1 | Adopt when SOC2 becomes a sales requirement (BVR-26). |
| Openlane | Compliance automation + Trust Center (Apache-2.0) | AUD-17 | EVALUATING | BE-1 | Permissive-licence alternative to Comp AI. |
| ipinfo | IP enrichment (geo, ASN, proxy/hosting flags) | RSK-02 | EVALUATING | BE-2 | Adopt with risk fingerprinting. Behind Risk adapter. |
| QuickBooks / Xero | Accounting sync (pick one at build) | LED-20 | EVALUATING | FunderBlu COO | CSV export is the fallback. Confirm with accountant. |
| Avalara | VAT/GST engine | CHK-26 | EVALUATING | BE-2 | Vs manual tax fields; depends on jurisdiction list. |
| Twilio | SMS channel | NOT-17 | DEFERRED | BE-2 | V2 by design. Behind NOT-02 channel iface. |
| Discord API | Community role automation | CHT-02 | EVALUATING | BE-2 | Where the community already is. Behind adapter. |

### 3.4 V3.0 consider-later adoptions

| Tool | What it does | Serves | Status | Notes |
|---|---|---|---|---|
| FingerprintJS | Device fingerprinting at scale | RSK-02/04 | DEFERRED | ipinfo first; adopt when volume justifies cost. |
| Stripe Billing | Recurring tenant invoicing | BIL-07 | EVALUATING | Behind Billing adapter. Depends on tenant jurisdictions. |
| n8n | Self-hosted low-code connectors | DVP-09 | EVALUATING | Sustainable-Use licence — review before deploy (BVR-18). |
| Zapier | Commercial low-code connectors | DVP-09 | DEFERRED | Prefer n8n. Webhook-based either way. |
| BigQuery | Warehouse + ETL target | ANA-18 | DEFERRED | Event-driven ETL from read models. |
| Authentik | Enterprise SSO (SAML/OIDC/LDAP) | AUTH-24/25 | DEFERRED | Only when a paying tenant demands SSO. Never V1/V2. |
| Plunk | Marketing email + newsletters | CRM-06 (+NOT-14) | DEFERRED | V3 with CRM. Never transactional (Postmark/Resend). |
| Nango | 500+ prebuilt API connectors | SDK-01/04/08/11/12/13 | DEFERRED | Elastic-2.0 — verify commercial terms. |
| Zoneless | Stripe-compatible stablecoin rail | CHK-04, PAY-43 | DEFERRED | Regulatory review required. |

### 3.5 Rejected / forbidden (never introduce)

| Tool | Rejected by | Why | Use instead |
|---|---|---|---|
| DocuSign | BVR-27 | per-envelope commercial | Documenso (self-hosted) |
| Kafka / Redpanda / NATS (V1) | BVR-09 | ops weight at our scale | Redis Streams |
| Kubernetes / Nomad / Swarm | BVR-10 | on-call surface for 1 DevOps | Docker Compose |
| HashiCorp Vault | BVR-06 | overkill V1 (+BUSL licence) | SOPS + age → Infisical (V2) |
| Auth0 / AWS Cognito | BVR-14 | per-MAU cost + tenant-RBAC mismatch | Better Auth (self-hosted) |
| Datadog / New Relic | BVR-11 | commercial APM cost | Prometheus + Grafana + Loki + Sentry |
| Kong / Traefik (V1) / AWS API GW | BVR-12 | extra service; Cloudflare covers edge | in-app middleware |
| Terraform | register | full IaC is out of scope in V1 — Compose + the runbook is the source of truth | Docker Compose + documented Hetzner provisioning (docs/06) |
| WooCommerce | register | V1 owns the checkout flow; a plugin storefront is out of scope | native checkout (CHK) |
| Intercom / Zendesk | register | a third-party helpdesk is out of scope in V1 | in-house Support Inbox (SUP) |
| WordPress | register | external CMS out of scope; the hosted CMS is a V3 module (CMS) | in-house CMS (V3, docs/24) |
| Metabase / Looker (V1) | BVR-13 | embedded-BI weight | read models + fixed reports + CSV |
| S3 (as primary store) | register | egress cost | Cloudflare R2 |
| DocRaptor / PDFMonkey | BVR-07 | paid PDF SaaS | Puppeteer |
| Stripe/Adyen (checkout) | register | weak PK/IN coverage | Match2Pay + Interkasa + NOWPayments |
| Onfido / Sumsub / in-house OCR | BVR-03 | no contract / out of scope | Veriff (signed) |
| Brokeree (open question) | BVR-04 | coverage-vs-cost TBD | MetaApi (primary); Brokeree stays the named alternative |

## 4. License policy

- **Default-allow:** MIT, Apache-2.0, BSD (2/3-clause), MPL-2.0,
  PostgreSQL License, ISC. No review needed.
- **Review-before-upgrade:** Redis >7.2 (RSALv2/SSPLv1) — BVR-17.
  Pin 7.2 until the review passes.
- **Review-before-deploy (fair-code / source-available):** n8n
  (Sustainable Use), Sentry self-host, Nango (Elastic-2.0) — BVR-18.
- **AGPL in the stack (self-hosted, no SaaS distribution):**
  Hook0, UnKey, Comp AI, Grafana, Loki. Verify the distribution
  model matches our use (self-hosted backend, no AGPL code shipped
  to tenants) before each adoption — recorded as a Phase-checklist
  item in docs/99, not a blocker.
- **Forbidden:** BUSL in V1 (Vault), SSPL/RSALv2 without review.
- Every adoption records: licence, version pin, exit path (the
  interface that lets us swap it — §5), and the decision owner.

## 5. Adapter rule (BVR-16)

Every external integration sits behind a **defined interface** so the
tool swaps without touching domain code. The registry:

| Interface | Owner doc | Implementations (V1 → later) |
|---|---|---|
| `BrokerCapability` (BRG-01) | 08 §3.1 | MetaApi → Brokeree (alt) → cTrader/DXtrade adapters (V3) |
| `PaymentProvider` (CHK-04) | 12 §3.4 | Match2Pay + Interkasa + NOWPayments → Zoneless (V3, deferred) |
| `KYCProvider` (KYC-01) | 13 §3.1 | Veriff → manual fallback (V1); 2nd provider on demand |
| `EmailProvider` (NOT-03) | 14 §3.1 | Postmark (prod) + Resend (dev/non-critical) |
| `ChannelDriver` (NOT-02) | 14 §3.1 | email + in-app (V1) → Telegram/WhatsApp/SMS drivers (V2) |
| `StorageBackend` (TEN-18) | 03 §3.4 | Cloudflare R2 (tenant-prefixed keys) |
| `PdfRenderer` (DOC-01) | 15 §3.1 | Puppeteer → html-pdf-lite (V2 candidate) |
| `RiskEnrichment` | 10 §3.3 | ipinfo → FingerprintJS (V3, deferred) |
| `TaxEngine` (CHK-26) | 12 (V2) | manual fields → Avalara (V2, evaluating) |
| `AccountingSync` (LED-20) | 05 (V2) | CSV export → QuickBooks/Xero (V2, evaluating) |
| `SecretsBackend` (OPS-09) | 06 §2.5 | SOPS + age → Infisical (V2) |
| `EventBus` (EVT-02) | 04 §5 | Redis Streams → NATS JetStream (V2, deferred) |
| `BillingProvider` (BIL-07) | 22 (V3) | Stripe Billing (evaluating at build) |
| `CommunityRelay` (CHT-02) | 26-D | Discord API (V2) |
| `ComplianceEvidence` (AUD-17) | 05 (V2) | Comp AI / Openlane (evaluating) |
| `ESignature` (DOC-12) | 15 (V2) | Documenso |
| `ConnectorPack` (SDK-04) | 27-A (V3) | Nango (deferred) |
| `SSOProvider` (AUTH-24) | 02 (V3) | Authentik (deferred) |

**Adapter contract rules:** timeouts + retries + circuit breaking live
in the adapter (never in domain code); provider timestamps are mapped
to epoch-ms at the boundary; provider webhooks enter via the ingress
path (EVT-10, signature-verified); every adapter has a **sandbox +
contract-test** mode so CI never touches a live vendor.

## 6. Evaluation process (EVALUATING → ADOPTED / REJECTED)

1. **Spike (time-boxed, ≤2 days):** one engineer proves the single
   riskiest fit (e.g. Better Auth org plugin multi-tenancy, Cerbos
   latency at 2k req/s, Hook0 AGPL distribution model).
2. **ADR note:** 1-page record in the owning module doc (§12) + a row
   update here (status + version pin + exit path). No separate ADR
   folder — the module doc is the ADR.
3. **Contract test:** the adapter (§5) gets a sandbox contract test in
   CI before any production key exists.
4. **Keys last:** production credentials are the final step (SOPS,
   §4), never the first.
5. **Rejection is a decision:** record REJECTED + why (like DocuSign)
   so the next engineer doesn't re-litigate.

## 7. Adoption timeline by phase

| Phase (docs/99) | Adoptions (tool → Req IDs) |
|---|---|
| 0 — Foundation (w0–4) | Hetzner, PG16, Redis 7.2, Compose, PgBouncer, SOPS+age, GHA, Cloudflare(+R2), Postmark, Sentry-SDK, Drizzle (adopt), BullMQ (adopt), Better Auth (spike), Cerbos (spike), MetaApi (**sign**), Match2Pay/Interkasa (sign), NOWPayments (sign wk2), Veriff (confirm keys) |
| 1 — Money loop (w5–16) | MetaApi (build), Veriff (build), Match2Pay/Interkasa/NOWPayments (build), Puppeteer (build) |
| 2 — Cutover (w17–24) | Prom/Grafana/Loki/OTel (harden), Uptime Kuma (adopt), BullMQ Dashboard (embed) |
| 3 — V2 breadth (w25–40) | Hook0, Flipt, UnKey, TV Charts, Documenso, ipinfo, QuickBooks/Xero (pick), Avalara (pick), Discord API, Comp AI/Openlane (pick), c15t (if CMS/chat), Logto (only if Better Auth fails), html-pdf-lite (only if PDFs bite), Infisical (only if secret-audit required) |
| 4 — Hardening | Traefik (only if gateway splits), NATS (only if Streams bottlenecks) — both default NO |
| 5 — V3 ecosystem | Stripe Billing, Authentik (only on tenant demand), Plunk, Nango, BigQuery, FingerprintJS (on volume), Zapier/n8n (pick), Zoneless (only after regulatory review) |

## 8. Cost summary (run-rate at V1.0 launch, excl. per-transaction fees)

| Line | Est. |
|---|---|
| Hetzner dedicated (AX) | €40–80/mo |
| MetaApi (per active account — the dominant line) | $50–100/mo × active accounts |
| Postmark (10k tier) | $15/mo |
| Cloudflare + R2 (free tiers) | $0 |
| GitHub Actions (private) | ~$4/mo |
| Sentry (free tier) | $0 |
| Everything self-hosted (PG, Redis, Compose, SOPS, Drizzle, BullMQ, Puppeteer, Prom stack, Flipt, Hook0, Kuma) | $0 (Hetzner sunk) |
| **Fixed floor** | **≈ €60–100/mo + MetaApi usage** |

Per-transaction lines (scale with revenue): Veriff per-verification,
Match2Pay/Interkasa per-transaction, NOWPayments ~1%, ipinfo/FingerprintJS/
Twilio/Stripe/Avalara/QuickBooks per-use in V2+. MetaApi is the only
fixed line that scales with *accounts* rather than revenue — tenant
pricing must cover it (docs/22 §3.4, docs/29 §5).

## 9. Open items (signup + confirmation checklist)

- [ ] **MetaApi signup (day 1)** — owner Shadab. Sandbox keys + provisioning coverage confirm. Blocks BRG (docs/08 §16).
- [ ] **Match2Pay signup (week 1)** — owner BE-2. Keys + hosted checkout test + settlement format.
- [ ] **Interkasa signup (week 1)** — owner BE-2. Secondary rail behind CHK-04.
- [ ] **Postmark signup (day 1)** — owner BE-2. Sending domain + auth.
- [ ] **Cloudflare setup (week 1)** — owner DevOps. DNS/edge + for-SaaS confirm.
- [ ] **R2 setup (week 2)** — owner DevOps. Bucket + tenant prefixes.
- [ ] **NOWPayments signup (week 2)** — owner BE-2. Networks TRC20/ERC20/BEP20.
- [ ] **Veriff keys confirm (week 1)** — owner FunderBlu COO. Webhooks included?
- [ ] **Better Auth spike (Phase 0)** — owner BE-1. Org plugin multi-tenancy fit.
- [ ] **Cerbos spike (Phase 0/1)** — owner BE-2. Latency + policy fit; else in-house AUTH-13.
- [ ] **Drizzle adopt (Phase 0)** — owners BE-1 + DevOps. Else Prisma fallback (BVR-08).
- [ ] **Sentry SDKs day 1** — owner DevOps. Every service from the first deploy.
- [ ] **AGPL distribution checks** (Hook0, UnKey, Comp AI, Grafana, Loki) — at each adoption.
- [ ] **Accountant call (V2)** — owner FunderBlu COO. QuickBooks vs Xero at LED-20.
- [ ] **Jurisdiction list (V2)** — owner BE-2 + legal. Avalara vs manual at CHK-26.

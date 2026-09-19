# 38 — PRD Out-Of-Scope Register

> Generated 2026-09-19 by `scripts/build_prd_registers.py` from
> `scripts/prd-workbook.json` (parsed from `uploads/Alpha One PRD.pdf`,
> the *Out Of Scope* sheet). Do not edit by hand: re-run the script after a PRD
> change, exactly like `scripts/prd-backlog.json`.
>
> What the platform deliberately does **not** do, per module. Anything listed here needs an explicit scope change (a promoted proposal, PRD change-log entry and backlog row) before it can be built — a PR implementing one of these is rejected on sight.


Items: **266** across 28 modules.

| Module | Items |
|---|---|
| KYC / Verification | 18 |
| DevOps & Deployment | 17 |
| Trading Platform Bridge | 16 |
| Support Inbox | 11 |
| Admin Panel | 10 |
| Checkout & Billing | 10 |
| Risk Management | 10 |
| Tenant Management | 10 |
| Trader Dashboard | 10 |
| API Gateway | 9 |
| Affiliate System | 9 |
| Auth & Identity | 9 |
| Evaluation Engine | 9 |
| Event Bus & Webhooks | 9 |
| Tenant Billing | 9 |
| Account Lifecycle | 8 |
| Advanced API / Developer Portal | 8 |
| Analytics & BI | 8 |
| BYO Integration SDK | 8 |
| CRM & Communications | 8 |
| Competition / Gamification | 8 |
| Ledger & Accounting | 8 |
| Payout System | 8 |
| Platform Console | 8 |
| Website / CMS | 8 |
| Audit & Compliance | 7 |
| Notification Service | 7 |
| Document Generation | 6 |

## KYC / Verification

- Dedicated AML, sanctions, and PEP screening beyond Veriff defaults. Deferred to a later compliance phase.
- In-house document OCR and identity matching. The provider does verification science.
- Periodic re-KYC on document expiry in V1. Trigger-based re-verification arrives at P2.
- Corporate and entity account verification. V1 verifies individuals only.
- Selling KYC as a standalone service outside the platform flow.
- Multiple identity documents per trader beyond a primary ID and optional address proof.
- Step-up biometric re-authentication at login or at payout time.
- Continuous watchlist monitoring. V1 screens once at verification.
- Building a proprietary identity verification engine. V1 uses external providers (Veriff) with manual fallback.
- Real-time identity monitoring or continuous authentication beyond document expiry triggers.
- Biometric matching beyond what the provider handles. We do not build facial recognition.
- KYC for platform staff or super admins. KYC applies only to traders.
- Multi-jurisdiction KYC routing (automatically selecting different providers per country). V1 uses one provider per tenant.
- KYC data sharing between tenants. Each tenant's KYC data is isolated.
- Automated document translation or OCR extraction beyond what the provider returns.
- KYC for payment method verification. Payment method validation is handled by the payout module.
- Regulatory filing automation. We export data for compliance but do not file with regulators.
- KYC for affiliates. Affiliate identity verification is not in V1 scope.

## DevOps & Deployment

- Kubernetes, service mesh, and horizontal autoscaling in V1.
- Multi-region active-active deployment and cross-region failover.
- GitOps controllers such as ArgoCD or Flux. GitHub Actions CI/CD is sufficient.
- Full Terraform coverage of all infrastructure in V1. Compose files plus documented Hetzner provisioning are the source of truth. IaC grows later.
- A chaos engineering program.
- Dedicated SRE or DBA hires in V1. DevOps is owned by an assigned developer.
- On-premise or hybrid deployments for tenants.
- Per-tenant isolated environments or dedicated stacks.
- Ephemeral preview environments per pull request. Staging is shared in V1.
- Commercial APM such as Datadog or New Relic in V1.
- Kubernetes and container orchestration beyond Compose.
- Multi-region active-active and automated cross-region failover. PLT-01 covers this later.
- Chaos engineering.
- Commercial APM tooling.
- Fully automated database failover in V1. Manual switchover runbook only.
- Blue-green deployment with parallel full-stack environments. Proxy-level switching is sufficient.
- Full Terraform-managed infrastructure in V1. Compose plus documented provisioning.

## Trading Platform Bridge

- Building raw MT4 or MT5 Manager API clients in-house. V1 uses vendor adapters only.
- cTrader, DXtrade, TradeLocker, Rithmic, NinjaTrader, and Tradovate adapters in V1.
- Order placement or trade execution from our platform. Traders trade in their terminal. We manage accounts and enforce rules.
- A-Book and B-Book routing, liquidity provider integration, and internal trade copiers to live markets. These belong to the advanced risk module later.
- Real-time tick streaming as a V1 requirement. Polling is the baseline. Streaming is an optional capability later.
- Instrument catalog management beyond normalization. Instrument restrictions are enforced through broker groups in V1.
- Automated server and group provisioning at the broker. Broker ops provisions servers and groups in V1.
- Mobile terminal packaging. Traders use the vendor terminals.
- FIX protocol connectivity.
- Building raw MT4 or MT5 Manager API integrations ourselves.
- Order placement or trade execution on behalf of traders.
- Partial closes in enforcement. Enforcement closes all positions only.
- Real-time tick processing. Streaming remains P2 at best, polling is the baseline.
- Broker-side margin and stop enforcement. The broker handles that natively.
- Multi-vendor failover in V1. Single MT5 vendor behind the capability interface.
- Broker-side reporting and exports. We use our own stored data.

## Support Inbox

- Full helpdesk suite replacement for Zendesk, Freshdesk, Intercom, or Crisp.
- Live chat widget in V1.
- AI support bot, AI summarization, and suggested replies.
- Knowledge base and FAQ article management.
- Complex auto-assignment rules and round-robin routing.
- Customer satisfaction surveys.
- Voice, WhatsApp, and SMS support channels.
- Public support portal outside the trader dashboard.
- Multi-brand helpdesk routing beyond tenant scoping.
- SLA contractual reporting for external enterprise tenants.
- Full Telegram two-way support sync in V1 unless explicitly approved after the first cutover.

## Admin Panel

- Drag-and-drop dashboard layout editor and widget marketplace. V1 ships fixed role-based dashboards.
- Custom report builder with arbitrary dimensions. V1 ships the fixed report set plus CSV export.
- In-panel visual certificate designer.
- Full CRM with sales pipeline and lead management. Deferred to M11.
- Live chat with traders inside the admin. The support inbox is ticket and Telegram based in V1.
- Field-level permissions beyond route and action permissions.
- White-labeling the admin panel beyond branding tokens: logo, colors, and terminology.
- A mobile admin app.
- Embedded third-party BI dashboards such as Metabase or Looker in V1.
- Full helpdesk suite features such as macros, knowledge base, and auto-assignment rules. The thin account-tied inbox ships in Phase 4; the suite arrives later.

## Checkout & Billing

- Building a payment service provider or touching raw card data. Hosted flows keep us out of PCI scope.
- Subscription and recurring billing for traders or tenants in V1.
- Tax calculation such as VAT or GST, and tax invoices.
- Multi-currency settlement. V1 settles in USD only.
- Full chargeback dispute workflow. V1 records chargebacks only.
- Multi-item carts and marketplace-style checkout. Checkout is one challenge plus add-ons.
- Checkout plugin SDK and WooCommerce plugin for external platforms. Arrives after V1.
- Affiliate coupon attribution logic. Coupons exist standalone in V1; affiliate attribution arrives with the affiliate module.
- Dynamic pricing, price experiments, and A/B price testing.
- Buy-now-pay-later and financing payment methods.

## Risk Management

- Auto-fail or auto-block driven by detectors. Humans decide in V1.
- A-Book and B-Book routing, liquidity provider integration, and firm-level hedging.
- Internal trade copier from funded accounts to live market accounts.
- Toxicity scoring and machine learning based anomaly detection.
- Real-time tick-level exposure monitoring. V1 works from synced positions in batch.
- Latency arbitrage and high-frequency trading detection, which require tick data.
- Martingale and grid strategy detection.
- Graph network analysis beyond pair-level correlation.
- Chargeback fraud scoring beyond the payment reuse signal.
- Selling risk data or scores to external consumers.

## Tenant Management

- Self-serve tenant signup and onboarding wizard. V1 onboarding is sales-led and performed by a super admin.
- Tenant billing, subscriptions, invoicing, and usage-based charging. Deferred module. V1 only records metering counters.
- Schema-per-tenant or database-per-tenant isolation. V1 uses one shared schema with tenant_id on every row.
- Per-tenant dedicated infrastructure or single-tenant deployments.
- Module marketplace UI and automated module provisioning pipelines. V1 entitlement changes are manual and immediate.
- Per-tenant resource quotas and rate limits beyond global gateway limits.
- Multi-brand or sub-tenant hierarchy under one firm.
- Automated SSL certificate provisioning for arbitrary custom domains. V1 uses manual Cloudflare setup.
- GDPR-grade tenant data export and deletion tooling. Arrives with M23 advanced compliance.
- White-label mobile app packaging per tenant.

## Trader Dashboard

- Native mobile apps and PWA push notifications.
- Live market charts and trade execution inside the portal. Trading happens in the broker terminal.
- Leaderboards, competitions, and badges. Deferred with the competition module.
- Economic calendar and news feed widgets.
- Trade journal and advanced analytics.
- Multi-language UI in V1.
- User-toggleable dark and light mode. V1 ships the tenant theme only.
- Affiliate and referral pages. Deferred with the affiliate module.
- Social features and public trader profiles.
- WebSocket real-time streaming in V1. Polling with visible freshness timestamps is the contract.

## API Gateway

- A standalone gateway product such as Kong, Traefik, or AWS API Gateway in V1.
- GraphQL API surface.
- A public developer portal and self-serve API key marketplace. Keys are issued by tenant admins in V1.
- Per-tenant dedicated API domains or private network endpoints.
- API monetization and per-call billing.
- Per-tenant sandbox environments. Deferred to P2.
- gRPC or other binary protocols.
- Client SDKs in multiple languages. OpenAPI-generated clients arrive later.
- A separate mobile-specific API surface. Mobile reuses the same API.

## Affiliate System

- Multi-tier and MLM style sub-affiliate commissions in V1.
- Tiered volume-based commission auto-progression. V1 supports manual per-affiliate overrides only.
- Lifetime recurring commissions beyond the configured per-order rules.
- Automated affiliate payout execution. V1 records manual execution with full audit.
- A standalone affiliate portal on its own domain. V1 lives as an affiliate section inside the trader portal.
- Click fraud detection beyond self-referral and basic velocity checks.
- Mobile install and deep-link attribution.
- Affiliate tax document generation.
- Real-time click streaming analytics. Daily batch aggregation is the contract.

## Auth & Identity

- SSO, SAML, and OIDC enterprise federation. Deferred to Phase 5.
- Passkeys, WebAuthn, and hardware security keys.
- SMS-based 2FA in V1. TOTP only. SMS channel arrives later with Twilio.
- Social login providers beyond Google.
- Biometric login.
- Buying Auth0 or Cognito. Decision is build in-house. Rationale: per-MAU pricing at trader scale plus custom tenant RBAC make a managed IdP a poor fit.
- Affiliate and partner identity types. The affiliate module is deferred.
- Username-only login. Email is the unique identifier per tenant.
- A staff user belonging to two tenants at once. Not supported in V1.

## Evaluation Engine

- Pre-trade rule enforcement that blocks order placement. Trades execute in the broker terminal. Broker groups enforce hard limits in V1.
- Cross-account pattern detection such as copy trading, inverse trading, and hedging rings. That belongs to the Risk module.
- Scaling plan engine. Deferred to a later phase.
- A custom rule DSL or arbitrary admin-authored expressions in V1. V1 ships a fixed rule catalog with parameters.
- Machine learning based anomaly detection.
- Per-instrument rule sets beyond restricted symbol flags.
- Automatic migration of in-flight accounts between rule set versions beyond the defined propagation policy.
- Competition scoring rules. Deferred with the competition module.
- Martingale and grid strategy detection. Deferred to the Risk module.

## Event Bus & Webhooks

- Kafka, Redpanda, NATS, or any broker other than Redis Streams in V1.
- Exactly-once delivery semantics. We use at-least-once delivery with idempotent consumers.
- Event sourcing as the primary persistence model. Postgres remains the source of truth. The event log exists for replay and audit, not for state.
- Public event stream access for tenants. Tenants receive signed HTTP webhooks, not stream credentials.
- A standalone schema registry service. Versioned JSON contracts in code are sufficient for V1.
- Event transformation and ETL pipelines into a data warehouse. Deferred with advanced analytics.
- WebSocket or GraphQL subscription push of domain events to frontends. Dashboards use read models and polling in V1.
- Cross-region event replication.
- Platform-wide broadcast events to all tenants. Events are tenant-scoped by construction.

## Tenant Billing

- Self-serve tenant signup funnel in the first iteration. Onboarding stays sales-led with billing recorded manually or via manual contract mode.
- Complex revenue recognition schedules. Invoices only; recognition stays with the accountant process.
- Multi-currency billing beyond USD in the first iteration.
- Reseller and partner revenue-share billing.
- Automated tax engines such as Avalara or TaxJar. V1 uses manual tax fields on invoices.
- Tenant credit balances, prepaid credits, and wallet systems.
- Per-feature metered pricing beyond the defined counters, except pass-through costs at P2.
- B2B chargeback dispute workflows beyond recording the event.
- Contract e-signature integrations.

## Account Lifecycle

- Account merging for scaling plans. Scaling is deferred.
- Automated broker server slot management and broker-side archiving.
- Sub-accounts and copy trading relationships between accounts. Deferred to the Risk module.
- Trader-initiated account upgrades or size changes mid-phase.
- Multi-currency account balances. V1 is USD only.
- Automatic re-provisioning on broker server migrations. Manual ops in V1.
- Inbound sync of account metadata edited directly in the broker manager. We detect such drift through reconciliation, not sync.
- Partial or fractional account transfers between traders.

## Advanced API / Developer Portal

- A public marketplace with revenue share on partner integrations.
- Per-call API monetization in the first iteration. Plan-based quotas only.
- Mobile SDKs for external developers.
- Self-serve partner onboarding with automated legal contracts.
- AI-assisted integration builders and codegen copilots.
- Multi-region API endpoints and developer-selectable data residency.
- SLA-backed enterprise API tiers with contractual uptime, until platform maturity justifies them.
- Replacing REST with GraphQL. REST remains the primary public contract.

## Analytics & BI

- Custom drag-and-drop report builder with arbitrary dimensions.
- Data warehouse such as ClickHouse or BigQuery and ETL pipelines in V1.
- Embedded third-party BI tools such as Metabase or Looker in V1.
- Real-time streaming dashboards. Event-driven read models plus nightly batch is the contract.
- Machine learning forecasting and lifetime value prediction.
- Cross-tenant benchmarking reports for the platform console.
- Public or shareable report links outside the admin panel.
- GA4, pixel, and marketing analytics integrations. Attribution capture already exists in checkout; marketing tooling stays external in V1.

## BYO Integration SDK

- Official SDKs beyond two languages at launch. Go, PHP, and Java arrive only on demonstrated demand.
- A GraphQL public API.
- A partner marketplace listing third-party integrations.
- White-glove integration engineering as a standard offering. Professional services only.
- Real-time streaming public feeds such as WebSocket event streams in the first iteration.
- Mobile client SDKs.
- Guaranteed client code generation beyond publishing the OpenAPI specification.
- Multi-region sandbox environments.

## CRM & Communications

- Full B2B sales pipeline and lead scoring. External CRM tooling stays external for platform sales.
- Live chat widgets and third-party chat integrations such as Intercom or Crisp in V1.
- SMS and WhatsApp channels. Deferred with the notification channel expansion.
- AI-generated content and send-time optimization.
- A/B testing of campaigns and subject lines.
- Web push notifications.
- Call center integration and call logging.
- Predictive churn scoring and machine learning based segmentation.

## Competition / Gamification

- Real-time tick-level leaderboard updates in the first iteration. Batch per sync cycle is the contract.
- Social trading, signal marketplaces, and copy-follow features.
- Wagering or real-money entry pools beyond fixed entry fees, which would raise gambling regulation issues.
- Cross-tenant platform-wide competitions in the first iteration. Competitions are tenant-scoped.
- NFT or tokenized badges and tradable achievements.
- Automated prize procurement and physical goods fulfillment.
- Sponsorship and advertising placement management inside competitions.
- Bracket-style tournament formats. The first iteration ships ranked leaderboard competitions only.

## Ledger & Accounting

- Multi-currency ledger and FX revaluation in V1. USD only, with capture-time rate stored as metadata.
- Deferred revenue schedules and a full accrual accounting engine.
- QuickBooks, Xero, or NetSuite integrations. CSV export only in V1.
- Automated tax calculation and filing support.
- Inter-company or inter-tenant accounting.
- Budgeting and forecasting tools.
- Real-time profit and loss dashboards beyond what Analytics reads from ledger balances.
- Editing or deleting posted journal entries. Corrections happen only through reversing adjustments.

## Payout System

- Automated provider execution in V1. Sending stays manual with full recording in the platform.
- Batch execution file uploads and mass payout API runs in V1. Batch approval only.
- Tax document generation such as W-8BEN or 1099 forms.
- Multi-currency payouts. V1 pays in USD only.
- Affiliate and referral commission payouts through this engine. Deferred with the affiliate module.
- Trader-to-trader transfers of balances or profits.
- Automatic payout initiation on cycle without a trader request. V1 is request-driven only.
- Payout method changes without cooldown and re-confirmation. Blocked by PAY-06 by design.

## Platform Console

- Tenant billing, subscriptions, invoicing, and payment collection from tenants. Deferred module.
- Module marketplace and self-serve module installation UI.
- Per-tenant dedicated infrastructure provisioning from the console.
- White-label console for resellers or partners.
- Tenant-to-tenant data migration tooling inside the console.
- Automated tenant onboarding email sequences. V1 onboarding is manual and sales-led.
- Platform-level feature experimentation and A/B testing UI.
- A public status page managed from the console.

## Website / CMS

- A freeform drag-and-drop page builder. The constrained section editor is the deliberate limit.
- E-commerce beyond the challenge checkout deep link.
- Multi-language sites in the first iteration.
- A/B testing and personalization.
- Membership or gated content beyond the existing trader portal.
- Custom code injection by tenants, including arbitrary scripts and iframes, for security reasons.
- Email capture popups and exit-intent tooling. Marketing automation belongs to CRM.
- Hosting tenant-owned external applications or arbitrary backends on tenant subdomains.

## Audit & Compliance

- Automated regulatory reporting packs and regulator filings.
- Streaming audit into an external SIEM in V1. Export only.
- A self-serve data subject request portal for traders. V1 is manual export by the compliance owner.
- Court-ready forensic tooling beyond the replay chain and exports.
- Cross-tenant analytics or anomaly detection on staff behavior.
- Blockchain or third-party notarization of audit records.
- Automatic PII redaction inside audit payloads. V1 minimizes PII in payloads by design; redaction tooling arrives with anonymization.

## Notification Service

- SMS, WhatsApp, and voice notifications. Deferred to Phase 4 with Twilio integration.
- Marketing automation, drip campaigns, and behavioral email sequences. Deferred to M11 CRM.
- Push notifications for mobile apps. V1 has no native mobile app.
- Building or self-hosting an SMTP server. We use a managed provider.
- Complex A/B testing of subject lines or send times.
- Multi-language email templates in V1. English only, with template structure ready for i18n later.
- In-app chat or real-time messaging between traders and support. That is M20 Support Inbox.

## Document Generation

- Visual drag-and-drop certificate designer. V1 uses code-based templates.
- Complex legal contracts with e-signatures (DocuSign, HelloSign integration).
- Tax documents (W-8BEN, 1099, VAT invoices).
- Multi-language certificates in V1. English only.
- Physical printing and mailing of certificates.
- Watermarking or complex DRM on PDFs.

## Related

- Rejected tools and forbidden infrastructure live in `docs/34-tooling-registry.md` §3.5; this register is about *product* scope.
- Deferrals that are scheduled (not forbidden) appear as `V2`/`V3` phases in `scripts/prd-backlog.json`, never here.


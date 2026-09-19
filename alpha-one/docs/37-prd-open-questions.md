# 37 — PRD Open Questions Register

> Generated 2026-09-19 by `scripts/build_prd_registers.py` from
> `scripts/prd-workbook.json` (parsed from `uploads/Alpha One PRD.pdf`,
> the *Open Questions* sheet). Do not edit by hand: re-run the script after a PRD
> change, exactly like `scripts/prd-backlog.json`.
>
> Every question the PRD raised, grouped by the module it blocks. An empty **Answer** cell means the question is still open and must be closed before the owning module's contract freeze (docs/99 §12). Answers captured in the workbook are reproduced verbatim; they outrank prose elsewhere in the doc set.


Questions: **205** in 28 sections — **205 answered**, 0 open.

| Section | Questions | Open |
|---|---|---|
| KYC / Verification | 15 | 0 |
| Trading Platform Bridge | 13 | 0 |
| DevOps & Deployment | 11 | 0 |
| Analytics & BI | 10 | 0 |
| Support Inbox | 8 | 0 |
| Auth & Identity | 7 | 0 |
| Tenant Management | 7 | 0 |
| Evaluation Engine | 7 | 0 |
| Account Lifecycle | 7 | 0 |
| Checkout & Billing | 7 | 0 |
| Payout System | 7 | 0 |
| Risk Management | 7 | 0 |
| Affiliate System | 7 | 0 |
| Ledger & Accounting | 7 | 0 |
| Competition / Gamification | 7 | 0 |
| Tenant Billing | 7 | 0 |
| BYO Integration SDK | 7 | 0 |
| Advanced API / Developer Portal | 7 | 0 |
| Event Bus & Webhooks | 6 | 0 |
| API Gateway | 6 | 0 |
| Notification Service | 6 | 0 |
| Trader Dashboard | 6 | 0 |
| Admin Panel | 6 | 0 |
| Audit & Compliance | 6 | 0 |
| Platform Console | 6 | 0 |
| Website / CMS | 6 | 0 |
| CRM & Communications | 5 | 0 |
| Document Generation | 4 | 0 |

## KYC / Verification

| # | Question | Raised by | Owner | Deadline | Answer |
|---|---|---|---|---|---|
| 1 | Does FunderBlu's Veriff contract include webhook endpoints or only polling? This affects KYC-05 implementation. | Tech Lead | manager | Week 4 | Open |
| 2 | What KYC verification level does each FunderBlu challenge type require at migration? Map each challenge to basic, enhanced, or skipped. | Tech Lead | Funderblu Ops Owner | Kickoff +7 days | Open |
| 3 | Do we require proof of address in V1 or only ID plus liveness as Veriff defaults? | Tech Lead | Funderblu Risk Owner | Kickoff +7 days | Open |
| 4 | What is the restricted country list for V1, and does it apply at registration, at KYC, or both? | Tech Lead | Funderblu Risk Owner, Legal | Kickoff +10 days | Open |
| 5 | Which role can approve KYC manually in the fallback path, and does it require dual control? | Tech Lead | FunderBlu COO | Kickoff +7 days | Open |
| 6 | How many resubmission attempts are allowed before final rejection? | Tech Lead | Funderblu Ops Owner | Kickoff +7 days | Open |
| 7 | Do we store only Veriff media references, or also cache documents in our object storage for manual cases? Recommended: manual cases only. | Tech Lead | Tech Lead | Kickoff +5 days | Open |
| 8 | What is the KYC document retention period required by FunderBlu's jurisdiction? This determines KYC-31 configuration. | Tech Lead | Legal | Week 16 | Open |
| 9 | Does FunderBlu require proof of address for all challenges or only funded accounts? This affects KYC- 28 configuration. | Tech Lead | Legal | Week 14 | Open |
| 10 | What is the acceptable SLA for manual KYC review? Current target is 4 hours but confirm with operations. | Tech Lead | FunderBlu COO | Week 16 | Open |
| 11 | Do we need KYC re-verification on an annual cycle or only on document expiry? | Tech Lead | FunderBlu COO | Week 16 | Open |
| 12 | What happens to KYC data when a trader account is terminated? Immediate deletion, retention period, or anonymization? | Tech Lead | FunderBlu COO | Week 16 | Open |
| 13 | Does FunderBlu require selfie/liveness for all KYC levels or only enhanced? This affects Veriff configuration. | Tech Lead | FunderBlu COO | Week 14 | Open |
| 14 | What is the maximum number of KYC resubmission attempts before the trader must contact support? | Tech Lead | FunderBlu COO | Week 14 | Open |
| 15 | Do we need to support KYC for traders who registered before the KYC module was live (migration backfill)? | Tech Lead | Tech Lead | Week 14 | Open |

## Trading Platform Bridge

| # | Question | Raised by | Owner | Deadline | Answer |
|---|---|---|---|---|---|
| 1 | MetaApi or Brokeree for MT5? Decision criteria: provisioning API coverage, price per account, sandbox quality, support response. | Tech Lead | BE-1, Shadab | Week 2 | Open |
| 2 | Does the broker contract grant API rights for account creation, disable, enable, close all, group assignment, and password reset, or are some manual in broker manager? If manual, enforcement and provisioning designs degrade. | Tech Lead | Shadab | Before Phase 2 starts | Open |
| 3 | What is the default sync interval per tenant and the minimum safe interval given vendor rate limits? | BE-1 | BE-1 | Kickoff +5 days | Open |
| 4 | Daily drawdown reset follows broker server time or a tenant-configured timezone? | Tech Lead | Tech Lead | Kickoff +5 days | Open |
| 5 | Which MT5 groups map to which phases, and who creates those groups at the broker, broker ops or API? | BE-1 | BE-1, Shadab | Before Phase 2 starts | Open |
| 6 | Do we store trader terminal passwords in our database or delegate password generation and delivery to the vendor? Needs a security review. | Tech Lead | BE-1, Tech Lead | Kickoff +7 days | Open |
| 7 | If the broker does not offer MatchTrader, is cTrader the fallback second platform for V1? | Tech Lead | Shadab | Week 4 | Open |
| 8 | Can broker groups be created by API, or does broker ops create them manually per request? | Tech Lead | Shadab, BE-1 | Before Phase 2 starts | Open |
| 9 | Default sync interval per account phase: same interval for evaluation and funded, or faster for funded? | Tech Lead | BE-1, Funderblu Risk Owner | Kickoff +5 days | Open |
| 10 | Investor password: delivered by default in the credential email or only on request? | Tech Lead | DevOps | Kickoff +5 days | Open |
| 11 | Enforcement retry policy: max attempts, backoff ceiling, and escalation SLA for ops response. | BE-1 | BE-1, Tech Lead | Kickoff +5 days | Open |
| 12 | At what active account count does MetaApi per- account pricing become more expensive than Brokeree or self-hosted alternatives? | Tech Lead | FunderBlu COO | Week 4 | Open |
| 13 | Maximum tolerable sync outage before we alert traders or pause provisioning? | Tech Lead Tech Lead, Funderblu Risk Owner | — | Kickoff +7 days | Open |

## DevOps & Deployment

| # | Question | Raised by | Owner | Deadline | Answer |
|---|---|---|---|---|---|
| 1 | Secrets store for V1: SOPS with age in repo, Vault, or encrypted env injection on hosts? | DevOps | DevOps owner | Kickoff +3 days | Answered — SOPS + age per BVR-06 / BVR-21. |
| 2 | What trigger moves us from Compose to Kubernetes: service count, tenant count, or multi-region? Recommended: none of these in year one. | Tech Lead | Tech Lead, DevOps | Kickoff +5 days | Open |
| 3 | Backup retention period and off-host copy destination, for example a Hetzner Storage Box? | DevOps | DevOps owner | Kickoff +3 days | Open |
| 4 | On-call rotation and alert channel for a 4 to 5 person team: which Telegram group or phone tree? | Tech Lead | Tech Lead | Kickoff +5 days | Open |
| 5 | Staging data: synthetic only, or anonymized production copies, and what are the anonymization rules? | Tech Lead | Tech Lead, DevOps | Kickoff +5 days | Open |
| 6 | Do we need a bastion or VPN for production access in V1, or is keyed SSH with fail2ban sufficient? | DevOps | DevOps owner | Kickoff +3 days | Open |
| 7 | What RPO and RTO does the business accept, for example RPO 15 minutes and RTO 4 hours? | Tech Lead | Tech Lead, FunderBlu COO | Before cutover plan | Open |
| 8 | PgBouncer in front of Postgres or application-level pooling only? Recommended: PgBouncer. | DevOps | DevOps owner | Kickoff +5 days | Open |
| 9 | V1 database strategy: single instance with rehearsed restore inside RTO, or warm standby from day one? Recommended: single instance plus drills. | Tech Lead | DevOps owner | Kickoff +5 days | Open |
| 10 | What are the load test target numbers: concurrent trader sessions, sync batch size, payout burst volume? | Tech Lead | Tech Lead, BE-1 | Before Phase 2 | Open |
| 11 | Is synthetic-only staging data approved, meaning no production PII ever lands in staging? Recommended: yes. | Tech Lead | Tech Lead | Kickoff +5 days | Open |

## Analytics & BI

| # | Question | Raised by | Owner | Deadline | Answer |
|---|---|---|---|---|---|
| 1 | Confirm the exact V1 report list against the reports FunderBlu uses today in TTS: which of the eleven risk tabs map into V1? | Tech Lead | FunderBlu COO | Week 4 | Open |
| 2 | What timezone defines the daily and monthly cutoff for aggregates: tenant timezone or UTC? | BE-2 | Tech Lead, FunderBlu COO | Kickoff +7 days | Open |
| 3 | Do we expose a report API to tenants for their own BI tools in V1? Recommended: no, CSV export only. | Tech Lead | Tech Lead | Kickoff +7 days | Open |
| 4 | What is the read model rebuild procedure if a read model corrupts: full replay from the event log, and how long must that take? | BE-2 | BE-2, DevOps | Week 20 | Open |
| 5 | Which roles receive financial reports by default, and does the support role see any analytics at all? | BE-2 | FunderBlu COO | Kickoff +7 days | Open |
| 6 | Which of TTS's report tabs must be reproduced at cutover, and which can wait? This gates cutover. | Tech Lead | FunderBlu COO | Before Phase 3 | Open |
| 7 | What is the business definition of an active account and a pass? These definitions must be pinned before any KPI is trusted. | Tech Lead | FunderBlu COO | Before Phase 3 | Open |
| 8 | Is reporting day boundary in tenant timezone or UTC? | Tech Lead | FunderBlu COO | Before Phase 3 | Open |
| 9 | Is nightly batch freshness acceptable for all reports, or do any reports need near-real-time? | Tech Lead | FunderBlu COO | Before Phase 3 | Open |
| 10 | How far back must trend data be retained for trend views? | Tech Lead | Tech Lead, DevOps | Before Phase 4 | Open |

## Support Inbox

| # | Question | Raised by | Owner | Deadline | Answer |
|---|---|---|---|---|---|
| 1 | Does FunderBlu want the support inbox in the first cutover, or can Telegram/email remain primary until Phase 4? | Tech Lead | FunderBlu COO | Week 12 | Open |
| 2 | What are the V1 support categories: account, payout, KYC, payment, breach, technical, general, or a different list? | Tech Lead | Support Owner | Week 12 | Open |
| 3 | What are the SLA targets per priority, for example urgent first response within 1 hour and normal within 24 hours? | Tech Lead | Owner | Week 12 | Open |
| 4 | Are traders allowed to appeal breaches through support tickets, and who can make final decisions on appeals? | Tech Lead | Owner | Week 12 | Open |
| 5 | What file types and size limits are allowed for attachments? Recommended: images and PDFs only, max 10 MB per file. | BE-2 | Tech Lead, DevOps | Week 12 | Open |
| 6 | Does Telegram intake mean full two-way sync in V1, or only linking Telegram messages manually to a ticket? Recommended: defer full sync. | Tech Lead | Tech Lead, Support Owner | Week 12 | Open |
| 7 | Should support staff be allowed to see payout destination details inside tickets, or should these remain masked unless the staff role has finance permission? | Tech Lead | FunderBlu COO, Tech Lead | Week 12 | Open |
| 8 | Do resolved tickets auto-close after a fixed period, and what is the default duration? | Support owner | Tech Lead | Week 12 | Open |

## Auth & Identity

| # | Question | Raised by | Owner | Deadline | Answer |
|---|---|---|---|---|---|
| 1 | Is 2FA mandatory for all staff roles in V1, or only finance and risk roles? | Tech Lead | Tech Lead, FunderBlu COO | Kickoff +2 days | Open |
| 2 | Do we ship Google OAuth in V1 or defer all social login? | Tech Lead | Tech Lead | Kickoff +2 days | Open |
| 3 | What are the access token and refresh token lifetimes and rotation rules? | BE-1 | BE-1 | Kickoff +3 days | Open |
| 4 | Do migrated TTS traders get a forced password reset at cutover or a reset-email flow? | Tech Lead | Tech Lead | Before migration plan | Open |
| 5 | Do we store API keys and secrets in Postgres or an external secrets manager in V1? | BE-1 | DevOps owner | Kickoff +3 days | Answered — SOPS + age per BVR-06 / BVR-21. External manager (Infisical) deferred to V2. |
| 6 | Does any V1 tenant require SSO or SAML, which would pull it into V1 scope? | Tech Lead | Sales owner (unassigned) | Kickoff +5 days | Open |
| 7 | Do we allow super admin impersonation of tenant admins for support, and under what audit rules? | Tech Lead | Tech Lead | Kickoff +5 days | Open |

## Tenant Management

| # | Question | Raised by | Owner | Deadline | Answer |
|---|---|---|---|---|---|
| 1 | Confirm V1 isolation model: shared schema with tenant_id column, not schema-per-tenant. | Tech Lead | Tech Lead, BE-1 | Kickoff +3 days | Answered — Yes. Shared schema with tenant_id per Out Of Scope → Tenant Management. |
| 2 | Custom domain SSL in V1: manual via Cloudflare for SaaS, or automated certificate provisioning? | DevOps | DevOps owner | Kickoff +3 days | Open |
| 3 | Who may edit the terminology map: tenant admin or super admin only? | Tech Lead | Tech Lead | Kickoff +2 days | Open |
| 4 | Impersonation consent model: in-product consent per session or contract-level permission? | Tech Lead | Tech Lead, Legal | Kickoff +5 days | Open |
| 5 | Which secrets store: external manager or encrypted columns in Postgres for V1? | BE-1 | DevOps owner | Kickoff +3 days | Answered — SOPS + age per BVR-06 / BVR-21. |
| 6 | What happens to existing data when a module entitlement is disabled, for example affiliate commissions after affiliate is turned off? | BE-2 | Tech Lead, BE-2 | Kickoff +5 days | Open |
| 7 | Do we support multiple brands or sub-tenants under one firm in V1? Expected answer is no. | Tech Lead | Tech Lead | Kickoff +2 days | Open |

## Evaluation Engine

| # | Question | Raised by | Owner | Deadline | Answer |
|---|---|---|---|---|---|
| 1 | Daily drawdown reset follows broker server midnight or a tenant-configured reset time? | Tech Lead Funderblu Risk Owner, Tech Lead | — | Kickoff +5 days | Open |
| 2 | What is the default basis, equity or balance, for daily and max drawdown across FunderBlu products? | Tech Lead | Funderblu Risk Owner | Kickoff +5 days | Open |
| 3 | Which rules are hard breach versus soft breach by default in V1 product configs? | Tech Lead | Funderblu Risk Owner | Kickoff +7 days | Open |
| 4 | Does auto-pass apply to the final evaluation phase or does live verification always require manual review, as TTS defaulted? | Tech Lead | Funderblu Ops Owner | Kickoff +7 days | Open |
| 5 | Is the consistency rule evaluated only at payout request or continuously on funded accounts? | BE-1 Tech Lead, Funderblu Risk Owner | — | Kickoff +7 days | Open |
| 6 | News calendar source in V1: manually maintained internal calendar or an external feed provider? | Tech Lead | Tech Lead | Week 6 | Open |
| 7 | Do we support per-instrument rule sets in V1 or only global per-phase rules plus restricted symbol flags? Expected: global only. | BE-1 | Tech Lead | Kickoff +7 days | Open |

## Account Lifecycle

| # | Question | Raised by | Owner | Deadline | Answer |
|---|---|---|---|---|---|
| 1 | Is AWAITING_ACTIVATION a separate state or a flag on PASS_PENDING? Separate state recommended for clarity. | BE-1 | BE-1, Tech Lead | Kickoff +5 days | Open |
| 2 | Which challenges get free retakes, how many, and is that configured per challenge or per tenant? | Tech Lead | Funderblu Product Owner | Kickoff +7 days | Open |
| 3 | On suspension with open positions: disable trading only, or close positions as well? | Tech Lead | Funderblu Risk Owner | Kickoff +7 days | Open |
| 4 | How long do terminal accounts stay hot before archive, for example 12 months? | BE-2 | Tech Lead, DevOps | Kickoff +7 days | Open |
| 5 | Which TTS account states map to which new states, and do imported accounts keep original rule versions or bind to new versions? | Tech Lead | Tech Lead, BE-1 | Before migration plan | Open |
| 6 | Do giveaway and partner accounts skip payout eligibility rules or use custom payout terms? | Tech Lead | Funderblu Ops Owner | Kickoff +7 days | Open |
| 7 | Credential delivery channels: portal only, email only, or both, and do we issue a read-only investor password? | Tech Lead Tech Lead, Funderblu Ops Owner | — | Kickoff +7 days | Open |

## Checkout & Billing

| # | Question | Raised by | Owner | Deadline | Answer |
|---|---|---|---|---|---|
| 1 | Which providers are confirmed for V1 launch: Match2Pay, Interkasa, and which crypto rail exactly? | Tech Lead | FunderBlu COO | Week 2 | Open |
| 2 | During migration parallel run, does FunderBlu keep its current external checkout and cut over per cohort, or switch all at once? | Tech Lead | Tech Lead, FunderBlu COO | Before migration plan | Open |
| 3 | Coupon stacking rules: one coupon per order, and can affiliate coupons combine with promo coupons? | Tech Lead | Funderblu Marketing Owner | Kickoff +7 days | Open |
| 4 | Final V1 add-on list: reset, swap-free, and time extension only, or more? | Tech Lead | Funderblu Product Owner | Kickoff +7 days | Open |
| 5 | Refund policy window and approval role: COO only or a finance role as well? | Tech Lead | FunderBlu COO | Kickoff +7 days | Open |
| 6 | Login-first checkout or guest checkout with quick signup? Recommended: login-first with fast signup. | FE-1 | Tech Lead, FE-01 | Kickoff +5 days | Open |
| 7 | How many network confirmations for crypto payments before provisioning starts? | BE-2 | BE-2, FunderBlu COO | Kickoff +7 days | Open |

## Payout System

| # | Question | Raised by | Owner | Deadline | Answer |
|---|---|---|---|---|---|
| 1 | Which payout rails and networks are confirmed for V1: which crypto networks such as TRC20 or ERC20, and which fiat rail? | Tech Lead | FunderBlu COO | Week 2 | Open |
| 2 | Are partial payouts allowed by default across FunderBlu products, and what are the min and max thresholds per challenge? | Funderblu Product Owner Tech Lead | Risk Owner | Kickoff +7 days | Open |
| 3 | Is auto-approve ever enabled in V1 or is approval manual only at launch? Recommended: manual at launch. | Tech Lead | FunderBlu COO | Kickoff +7 days | Open |
| 4 | What is the second approval threshold amount for V1? | Tech Lead | FunderBlu COO | Kickoff +7 days | Open |
| 5 | Post-payout balance handling: keep the remainder or reset to initial after a full payout? | Tech Lead | Funderblu Risk Owner | Kickoff +7 days | Open |
| 6 | What are the payout frequency defaults per product: bi- weekly, monthly, or on-demand? | Tech Lead | Funderblu Product Owner | Kickoff +7 days | Open |
| 7 | Do affiliate commissions flow through this payout engine in V1? Expected: no, affiliate module is deferred. | Tech Lead | Tech Lead | Kickoff +5 days | Open |

## Risk Management

| # | Question | Raised by | Owner | Deadline | Answer |
|---|---|---|---|---|---|
| 1 | Confirm the V1 detector set: IP overlap, device overlap, copy, inverse, and KYC reuse in V1, with payment reuse at P2. | Tech Lead, Funderblu Risk Owner | — | Kickoff +7 days | Open |
| 2 | What open and close time delta and symbol match window counts as correlated for the copy detector in V1? | BE-2 | BE-2, Funderblu Risk Owner | Week 20 | Open |
| 3 | What score thresholds auto-open a case per signal type, versus info-only signals? | BE-2 | Funderblu Risk Owner | Week 20 | Open |
| 4 | Does an open case block new challenge purchases as well as payouts? Recommended: payouts only in V1. | Tech Lead | Funderblu Risk Owner | Kickoff +7 days | Open |
| 5 | Device fingerprinting in V1: ipinfo flags only, or add FingerprintJS now? Recommended: ipinfo now, FingerprintJS when volume justifies cost. | Tech Lead | Tech Lead | Kickoff +5 days | Open |
| 6 | Who owns the risk staff role definition and the case review SLA, for example review within 24 hours? | Tech Lead | FunderBlu COO | Kickoff +7 days | Open |
| 7 | What is the retention period for signals and device logs? | BE-2 | Tech Lead, DevOps | Kickoff +7 days | Open |

## Affiliate System

| # | Question | Raised by | Owner | Deadline | Answer |
|---|---|---|---|---|---|
| 1 | Does FunderBlu migrate its existing affiliate program at cutover, or keep it running externally until Phase 4 lands? This changes the migration plan. | Tech Lead | FunderBlu COO, Tech Lead | Before migration plan | Open |
| 2 | Commission basis in V1: first order only, or every order from a referred trader? | Tech Lead | FunderBlu COO, FunderBlu | Week 20 | Open |
| 3 | What refund window length gates commission approval, for example 14 days? | Tech Lead | FunderBlu COO | Week 20 | Open |
| 4 | What is the minimum payout threshold and which payout rails do affiliates use, same as traders or separate? | Tech Lead | FunderBlu COO | Week 20 | Open |
| 5 | Does FunderBlu's current program use tiered or multi- tier commissions? If yes, V1 scope must change. | Tech Lead | FunderBlu marketing/design | Week 20 | Open |
| 6 | What cookie duration applies by default, for example 30 days? | Tech Lead | FunderBlu marketing/design | Week 20 | Open |
| 7 | Can a trader also be an affiliate, and is self-purchase through own link blocked outright or flagged for review? | Tech Lead | FunderBlu COO | Week 20 | Open |

## Ledger & Accounting

| # | Question | Raised by | Owner | Deadline | Answer |
|---|---|---|---|---|---|
| 1 | Confirm the V1 chart of accounts with the external accountant: are the seven accounts sufficient? | Tech Lead | FunderBlu COO | Week 12 | Open |
| 2 | Revenue recognition: recognize challenge fees at capture or defer until challenge completion? This needs an accountant ruling, not an engineering guess. | Tech Lead | FunderBlu COO | Week 12 | Open |
| 3 | What settlement report format and availability does each provider offer: Match2Pay, Interkasa, and the crypto rail, CSV, API, or manual statement? | BE-2 | FunderBlu COO | Week 12 | Open |
| 4 | At what rate do we book crypto payments and payouts: capture-time rate recorded as metadata? | Tech Lead | — | Week 14 | Open |
| 5 | Who may post adjustments: COO only, or a finance role with dual control above a threshold? | Tech Lead | FunderBlu COO | Kickoff +7 days | Open |
| 6 | Do ledger entries carry product and challenge tags in V1 for per-product revenue breakdown? Recommended: yes. | BE-2 | BE-2, FunderBlu COO | Week 14 | Open |
| 7 | Confirm reporting currency and fiscal year for exports: USD and calendar year? | Tech Lead | FunderBlu COO | Week 12 | Open |

## Competition / Gamification

| # | Question | Raised by | Owner | Deadline | Answer |
|---|---|---|---|---|---|
| 1 | What is the build trigger: named tenant demand or a marketing-led campaign plan? FunderBlu's previous competition module had zero conversions, so validate demand before spending effort. | Funderblu Product Owner Tech Lead | , FunderBlu | Before Phase 5 planning | Open |
| 2 | Do competition accounts use a separate demo group at the broker or reuse evaluation accounts, and does the broker support the needed group? | BE-2 | FunderBlu COO, BE-2, Broker | Before Phase 5 planning | Open |
| 3 | Which scoring criteria ship in the first iteration: profit percent only, or also ROI and risk-adjusted score? | Tech Lead | Funderblu Product Owner | Before Phase 5 planning | Open |
| 4 | Which prize types launch first: account credit, coupon, or cash payout, and which budget funds the prize pool? | Tech Lead | FunderBlu COO | Before Phase 5 planning | Open |
| 5 | Is the leaderboard alias-only by default with opt-in real names, and what does legal say about public performance data? | Tech Lead | Legal, Funderblu Product Owner | Before Phase 5 planning | Open |
| 6 | What leaderboard update frequency is acceptable at launch: batch per sync cycle or near real-time? Recommended: batch per sync. | BE-2 | BE-2, Funderblu Product Owner | Before Phase 5 planning | Open |
| 7 | Do competition results and badges become part of the trader's permanent record and certificates? | Tech Lead | Funderblu Product Owner | Before Phase 5 planning | Open |

## Tenant Billing

| # | Question | Raised by | Owner | Deadline | Answer |
|---|---|---|---|---|---|
| 1 | Confirm the pricing model: fixed plan plus usage overage, pure module-based pricing, or hybrid? This is a commercial decision, not an engineering one. | Tech Lead | CEO, FunderBlu COO | — | Open |
| 2 | Which metering counters are billable: active traders, trading accounts, orders, API calls, or a subset? | Tech Lead | CEO, FunderBlu COO | — | Open |
| 3 | Billing currency and tax handling per tenant jurisdiction: who validates the rules, and do invoices need reverse- charge wording for EU tenants? | Tech Lead | Legal | — | Open |
| 4 | Dunning policy: grace period length, and does past due mean suspension or read-only mode first? | Tech Lead | FunderBlu COO | — | Open |
| 5 | Is FunderBlu itself a billed subscription or exempt as the owner tenant, and how is that represented? | Tech Lead | Tech Lead, FunderBlu COO | — | Open |
| 6 | Do B2B collections reuse the trader payment adapters or a separate invoicing provider such as Stripe Billing? | BE-2 | FunderBlu COO, BE-2 | — | Open |
| 7 | Contract terms at launch: monthly only, or annual with discount? | Tech Lead | CEO, FunderBlu COO | — | Open |

## BYO Integration SDK

| # | Question | Raised by | Owner | Deadline | Answer |
|---|---|---|---|---|---|
| 1 | Which languages get official SDKs at launch: TypeScript and Python only, or more? | Tech Lead | Tech Lead | Before build trigger | Open |
| 2 | Sandbox data policy: synthetic data only, or masked production-shaped data? Recommended: synthetic only. | Tech Lead | Tech Lead, DevOps | Before build trigger | Open |
| 3 | Is the developer portal a separate documentation site or a section of the platform marketing site? | FE-2 Funderblu Product Owner | , Tech Lead | Before build trigger | Open |
| 4 | Which BYO paths get documented first based on real demand: checkout, affiliate, or KYC? | Sales owner (unassigned) Tech Lead | Product Owner | Before build trigger | Open |
| 5 | Is public API access included in base plans or reserved for enterprise tiers? Ties into tenant billing. | Tech Lead | CEO, FunderBlu COO | Before build trigger | Open |
| 6 | What is the support model for integrators: docs and sandbox only, or paid onboarding as professional services? | Tech Lead | CEO, FunderBlu COO | Before build trigger | Open |
| 7 | How many days of webhook delivery history is replayable in sandbox and in production? | BE-2 | BE-2, DevOps | Before build trigger | Open |

## Advanced API / Developer Portal

| # | Question | Raised by | Owner | Deadline | Answer |
|---|---|---|---|---|---|
| 1 | Is the developer portal public before we have external tenants? Recommended: private beta docs for design partners, public at the second tenant. | Sales owner (unassigned) Tech Lead | Product Owner | Before build trigger | Open |
| 2 | Do we monetize API access separately from plans with per-call pricing, or include quotas in tiers only? Ties into tenant billing. | Tech Lead | CEO, FunderBlu COO | Before build trigger | Open |
| 3 | Which API products ship first: read-only reports, webhooks, or account management? | Tech Lead | Funderblu Product Owner | Before build trigger | Open |
| 4 | Does partner-delegated access ship in the first iteration, or do we start with tenant-owned keys only? | Tech Lead | Tech Lead | Before build trigger | Open |
| 5 | Is GraphQL real demand or speculation? Recommended: defer until two tenants explicitly request it. | Tech Lead | Tech Lead | Before build trigger | Open |
| 6 | Who owns portal content, guides, and tutorials, and what keeps them current across releases? | Tech Lead Funderblu Product Owner | , Tech Lead | Before build trigger | Open |
| 7 | Status page: build a minimal internal one or use an external provider such as Instatus? Recommended: external provider at launch. | DevOps | DevOps owner | Before build trigger | Open |

## Event Bus & Webhooks

| # | Question | Raised by | Owner | Deadline | Answer |
|---|---|---|---|---|---|
| 1 | Do outbound tenant webhooks ship in V1 or immediately after MVP , given FunderBlu does not need them? | Tech Lead | Tech Lead | Kickoff +3 days | Open |
| 2 | Redis Streams retention: what max stream length and retention window do we configure for V1? | DevOps | DevOps owner | Kickoff +3 days | Open |
| 3 | Event log retention period for replay: 90 days, 1 year, or permanent archive to object storage? | BE-2 | DevOps owner | Kickoff +5 days | Open |
| 4 | Who approves event schema changes and version bumps to prevent contract drift between modules? | Tech Lead | Tech Lead | Kickoff +2 days | Open |
| 5 | Is the outbox relay a separate process or a background worker inside the API binary for V1? Recommended: separate process. | BE-1 | BE-1 | Kickoff +3 days | Open |
| 6 | Do any V1 flows require stronger than at-least-once delivery plus idempotent consumers? Expected answer is no. | BE-1 | Tech Lead | Kickoff +5 days | Open |

## API Gateway

| # | Question | Raised by | Owner | Deadline | Answer |
|---|---|---|---|---|---|
| 1 | Confirm V1 gateway is in-app middleware behind Cloudflare, not a standalone Kong or Traefik deployment. | Tech Lead | Tech Lead, DevOps | Kickoff +2 days | Answered — Yes. In-app middleware behind Cloudflare per BVR-12 and Out Of Scope. |
| 2 | What are the default rate limits per route group for trader, admin, and webhook traffic? | BE-1 | BE-1 | Kickoff +3 days | Open |
| 3 | Do per-tenant quotas ship in V1 or only after the second paying tenant? Expected: after. | Tech Lead | Tech Lead | Kickoff +3 days | Open |
| 4 | Versioning strategy: URL versioning only, or also header-based negotiation? Recommended: URL only. | BE-1 | BE-1 | Kickoff +3 days | Open |
| 5 | Do we expose a public tenant API in V1 or only inbound and outbound webhooks? Ties to the EVT-11 question. | Tech Lead | Tech Lead | Kickoff +5 days | Open |
| 6 | Who defines and reviews the PII exclusion list for request logs? | Tech Lead | Tech Lead, DevOps | Kickoff +5 days | Open |

## Notification Service

| # | Question | Raised by | Owner | Deadline | Answer |
|---|---|---|---|---|---|
| 1 | Which email provider for V1: Postmark, SendGrid, or AWS SES? Postmark recommended for deliverability. | Tech Lead | Tech Lead, DevOps | Kickoff +3 days | Answered — Postmark (production) per Tooling Register / Integration Map. Resend is dev/non-critical backup. |
| 2 | Who designs and provides the HTML/CSS for the 10 core email templates? | Tech Lead | FunderBlu marketing/design | Week 4 | Open |
| 3 | Do we need SMS notifications in V1? Recommended: no, email and in-app only. | Tech Lead | Tech Lead | Kickoff +3 days | Open |
| 4 | How do we handle email bounces: suppress immediately, or allow manual override by support? | Tech Lead | Support Owner, Tech Lead | Kickoff +5 days | Open |
| 5 | Telegram bot hosting: run as a separate worker in our Hetzner stack or use a managed bot service? Recommended: separate worker. | DevOps | DevOps owner | Kickoff +3 days | Open |
| 6 | Do broadcasts respect user notification preferences, or do they override them for critical system announcements? | Tech Lead | Tech Lead | Kickoff +5 days | Open |

## Trader Dashboard

| # | Question | Raised by | Owner | Deadline | Answer |
|---|---|---|---|---|---|
| 1 | What is the default polling interval for dashboard data: 30 seconds or 60 seconds? | FE-1 | BE-1, FE-01 | Kickoff +5 days | Open |
| 2 | Does the trader portal include marketing and pricing pages in V1, or does the tenant's external website handle marketing and link into checkout? Recommended: external site links in. | Tech Lead | marketing/design | Kickoff +5 days | Open |
| 3 | Single theme per tenant or a user-toggleable dark and light mode in V1? Recommended: tenant theme only. | FE-1 | FE-01 | Kickoff +3 days | Open |
| 4 | What columns and row limits apply to trade history CSV export? | FE-1 | BE-1, FE-01 | Kickoff +7 days | Open |
| 5 | Which chart library for the equity curve: Recharts or TradingView Lightweight Charts? | FE-1 | FE-01 | Kickoff +5 days | Answered — TradingView Lightweight Charts for equity/P&L; Recharts for admin bar/line charts. See Tooling Register. |
| 6 | Which terminology strings does FunderBlu want customized at launch, for example challenge versus evaluation? | Tech Lead | FunderBlu marketing/design | Week 4 | Open |

## Admin Panel

| # | Question | Raised by | Owner | Deadline | Answer |
|---|---|---|---|---|---|
| 1 | Which default roles ship in V1, for example admin, finance, risk, support, and marketing, and what permission subsets do they carry? | Tech Lead | Tech Lead, FunderBlu COO | Kickoff +7 days | Open |
| 2 | Does the account detail include device activity and IP events in V1, or only after the risk detectors land in Phase 4? | Tech Lead | Tech Lead | Kickoff +7 days | Open |
| 3 | Which reports map to the first read models: daily, monthly financial, challenge versus payout, country payout, top earners? | Tech Lead | FunderBlu COO, Tech Lead | Week 4 | Open |
| 4 | Confirm masking policy: no staff role can view raw trader trading passwords, only trigger a resend. | Tech Lead | Tech Lead | Kickoff +5 days | Open |
| 5 | Email template editor in V1: text and variables only with locked layout, or full HTML? Recommended: text and variables only. | FE-1 | Tech Lead | Kickoff +7 days | Open |
| 6 | Bulk operation guardrails: maximum selection size and mandatory confirmation step? | FE-1 | Tech Lead | Kickoff +7 days | Open |

## Audit & Compliance

| # | Question | Raised by | Owner | Deadline | Answer |
|---|---|---|---|---|---|
| 1 | What retention period applies per audit category, for example seven years for financial actions and two years for security events? | Tech Lead | Tech Lead, Legal | Before cutover | Open |
| 2 | Which actions trigger real-time alerts in V1: payout above threshold, production rule change, bulk suspension, or others? | Tech Lead | FunderBlu COO | Kickoff +7 days | Open |
| 3 | Can traders view audit entries about themselves in V1? Recommended: no, data subject export on request only. | Tech Lead | Legal | Kickoff +7 days | Open |
| 4 | Does hash chaining ship in V1 or later? Recommended: later, since append-only storage plus restricted database access is sufficient for V1. | Tech Lead | Tech Lead | Kickoff +7 days | Open |
| 5 | Which roles may access the audit viewer: admin only, or also risk and finance? | Tech Lead | FunderBlu COO | Kickoff +7 days | Open |
| 6 | What is the policy for KYC documents after account closure: anonymize, delete, or retain for the full financial retention period? | Tech Lead | Legal, DevOps | Before cutover | Open |

## Platform Console

| # | Question | Raised by | Owner | Deadline | Answer |
|---|---|---|---|---|---|
| 1 | Confirm console hosting on a separate subdomain with its own auth realm, isolated from tenant identity tables. | Tech Lead | Tech Lead | Kickoff +3 days | Open |
| 2 | Who holds super admin seats at launch, by name, and what is the break-glass procedure if one is compromised? | Tech Lead | FunderBlu COO, Tech Lead | Kickoff +5 days | Open |
| 3 | Does tenant provisioning seed default challenge templates or start empty? Recommended: empty with an optional template library copy. | Tech Lead, | Funderblu Product Owner | Kickoff +7 days | Open |
| 4 | What impersonation scopes exist: read-only, full admin, or full admin excluding finance actions? | Tech Lead | FunderBlu COO, Tech Lead | Kickoff +7 days | Open |
| 5 | Who is on call for platform-level alerts versus tenant- level alerts, and what thresholds separate them? | DevOps | DevOps owner | Week 6 | Open |
| 6 | Does the console show tenant financial revenue by default, or only usage counts until tenant billing exists? Recommended: usage counts only. | Tech Lead | FunderBlu COO, Tech Lead | Kickoff +7 days | Open |

## Website / CMS

| # | Question | Raised by | Owner | Deadline | Answer |
|---|---|---|---|---|---|
| 1 | What trigger justifies starting this module: a named tenant demand, a revenue threshold, or a sales commitment? | Tech Lead, | Sales owner (unassigned) | Before Phase 5 planning | Open |
| 2 | First iteration scope: templates plus pricing widget only, or include blog from the start? Recommended: templates and widget only. | Tech Lead | Funderblu Product Owner | Before Phase 5 planning | Open |
| 3 | Does a hosted tenant site replace the tenant's existing website or coexist with it, for example platform hosts landing and pricing while the tenant keeps an external blog? | Funderblu Product Owner Tech Lead | marketing/design | Before Phase 5 planning | Open |
| 4 | Hosting model on our stack: Nginx vhosts per tenant on Hetzner, or edge-rendered static pages? | DevOps | DevOps owner | Before Phase 5 planning | Open |
| 5 | Is published content subject to an approval workflow in regulated markets, and who approves? | Tech Lead | Legal, Funderblu Product Owner | Before Phase 5 planning | Open |
| 6 | Do we offer import from WordPress or Webflow for existing tenant content, or start fresh only? | Tech Lead | Funderblu Product Owner | Before Phase 5 planning | Open |

## CRM & Communications

| # | Question | Raised by | Owner | Deadline | Answer |
|---|---|---|---|---|---|
| 1 | Which automated sequences are must-have at launch for FunderBlu: welcome, cart abandonment, retry reminder, or re-engagement? | Tech Lead | Funderblu Marketing Owner | Week 20 | Open |
| 2 | Should segments be able to exclude traders with open risk cases from campaigns? Recommended: yes, by default. | Funderblu Risk Owner, Funderblu | Marketing Owner | Week 20 | Open |
| 3 | Who writes and owns the marketing copy for sequences and campaigns? | Tech Lead | Funderblu Marketing Owner | Week 20 | Open |
| 4 | Do we need explicit marketing consent capture at registration for EU traders in V1, or is consent implied by terms acceptance? | Tech Lead | Tech Lead, Legal | Week 20 | Open |
| 5 | Does FunderBlu run an active Discord community today, and is role automation worth P2 effort? | Tech Lead | Funderblu Marketing Owner | Week 20 | Open |

## Document Generation

| # | Question | Raised by | Owner | Deadline | Answer |
|---|---|---|---|---|---|
| 1 | Which HTML-to-PDF library to use? Puppeteer/Playwright is heavy. Consider `@react- pdf/renderer` or a lightweight Node library. | Tech Lead | BE-2 | Kickoff +3 days | Answered — Puppeteer per BVR-07. html-pdf-lite is a V2 lower-footprint candidate. |
| 2 | Do we need a visual drag-and-drop template designer in V1? Recommended: No, use hardcoded templates with JSON config for variables. | Tech Lead | Tech Lead | Kickoff +3 days | Open |
| 3 | What are the exact V1 certificate types? Recommended: Challenge Passed, Funded Trader, Payout Receipt. | Tech Lead | Funderblu Product Owner | Kickoff +5 days | Open |
| 4 | Do we need a QR code on the certificate for external verification in V1? Recommended: No, unique ID is enough for V1. | Tech Lead | Tech Lead | Kickoff +5 days | Open |

## Using this register

- **An open question is a design risk, not a blocker to writing docs** — the owning doc states the default it assumes and cites the question row; the answer then updates both.
- **Answered rows are decisions.** They are binding for contract freeze; the `docs/99-development-phases.md` gate checklist re-reads this register at each phase exit.
- **New questions** belong in the PRD workbook (so this script picks them up), not in ad-hoc comments.


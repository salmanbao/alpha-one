# 37 — PRD Open Questions Register

> Generated 2026-09-19 by `scripts/build_prd_registers.py` from
> `scripts/prd-workbook.json` (parsed from `uploads/Alpha One PRD.pdf`,
> the *Open Questions* sheet). Do not edit by hand: re-run the script after a PRD
> change, exactly like `scripts/prd-backlog.json`.
>
> Every question the PRD raised, grouped by the module it blocks. An empty **Answer** cell means the question is still open and must be closed before the owning module's contract freeze (docs/99 §12). Answers captured in the workbook are reproduced verbatim; they outrank prose elsewhere in the doc set.


Questions: **205** in 28 sections — **8 answered**, 197 open.

Design-review questions (raised by the team, not the PRD workbook): **54** — **5 open** (§Design-review questions below).

| Section | Questions | Open |
|---|---|---|
| KYC / Verification | 15 | 15 |
| Trading Platform Bridge | 13 | 13 |
| DevOps & Deployment | 11 | 10 |
| Analytics & BI | 10 | 10 |
| Support Inbox | 8 | 8 |
| Auth & Identity | 7 | 6 |
| Tenant Management | 7 | 5 |
| Evaluation Engine | 7 | 7 |
| Account Lifecycle | 7 | 7 |
| Checkout & Billing | 7 | 7 |
| Payout System | 7 | 7 |
| Risk Management | 7 | 7 |
| Affiliate System | 7 | 7 |
| Ledger & Accounting | 7 | 7 |
| Competition / Gamification | 7 | 7 |
| Tenant Billing | 7 | 7 |
| BYO Integration SDK | 7 | 7 |
| Advanced API / Developer Portal | 7 | 7 |
| Event Bus & Webhooks | 6 | 6 |
| API Gateway | 6 | 5 |
| Notification Service | 6 | 5 |
| Trader Dashboard | 6 | 5 |
| Admin Panel | 6 | 6 |
| Audit & Compliance | 6 | 6 |
| Platform Console | 6 | 6 |
| Website / CMS | 6 | 6 |
| CRM & Communications | 5 | 5 |
| Document Generation | 4 | 3 |

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

## Design-review questions

Raised by the team during design review — they are **not** PRD workbook rows, so they are maintained in `scripts/design-questions.json` (the PRD rows above are generated from `scripts/prd-workbook.json`). Evidence for each is in `docs/41-auth-ten-open-source-evaluation.md`; an answer here must be applied to the owning module doc in the same change.

| ID | Question | Raised by | Owner | Deadline | Answer |
|---|---|---|---|---|---|
| D1 | Identity component wiring: Better Auth has no Go SDK, so the V1 plan assumes a Node identity surface. Options — A: keep Better Auth, run it in the Node tier behind a documented JWT/JWKS contract for Go (one more deployable); B: Better Auth for flows, Go owns session/refresh-token tables and revocation; C: replace with a multi-tenant IdP (Zitadel AGPL-3.0, or Keycloak if deep SAML/LDAP is needed), everything OIDC; D: build the identity domain in Go (~3-4 dev-weeks, zero extra runtime, BVR-14 superseded). See docs/41 §7. | Design review (docs/41) | Tech Lead, BE-1 | Before Phase 0 exit | **Answered 2026-09-19 — option C, product P1: ZITADEL** (self-hosted, AGPL-3.0, one instance, Organization per tenant). Better Auth (BVR-14) and Cerbos (BVR-23) are superseded by ADR-13/ADR-14. See docs/41 §10. |
| D2 | Does any tenant need SAML/OIDC SSO or SCIM at V1 cutover? Restates PRD row *Auth & Identity #6* as a build decision. The PRD schedules AUTH-24/25 at V3 and every OSS IdP that ships them at V1 (Zitadel, Keycloak, authentik) costs a second identity store plus, for Zitadel, an AGPL-3.0 review. Answering yes promotes AUTH-24/25 into V1 and changes D1. | Design review (docs/41 §4) | Sales owner, Tech Lead | Before Phase 0 exit | **Answered 2026-09-19 — yes:** one V1 tenant requires SSO at cutover. AUTH-24 (SAML/OIDC federation) is promoted into V1.0/V1.1 scope and AUTH-25 (SCIM) is promoted with it per P3. Recorded as a post-PRD design decision (docs/41 §10), not a PRD workbook row. |
| D3 | Isolation enforcement depth: keep ADR-1 app-level only (Go tenant guard + sqlc + CI guard test), or add Postgres RLS as a fail-closed second layer? RLS costs 2-4% on indexed queries and requires transaction-scoped `set_config('app.tenant_id', …, true)` under PgBouncer, `FORCE ROW LEVEL SECURITY` and a (tenant_id, …) index on every policy table; a missed guard currently leaks all tenants' rows, with RLS it returns zero rows. See docs/41 §5. | Design review (docs/41 §5) | Tech Lead, BE-1, DevOps | Before tenant-scoped tables are frozen | **Answered 2026-09-19 — yes: Postgres RLS is adopted** as the fail-closed second enforcement layer on every tenant-owned table (docs/01 §7.8, docs/03 §10). App-level guard (ADR-1) stays. |
| D4 | Authorization engine and deployment mode: keep Cerbos (BVR-23) as sidecar/central service, embed the Cerbos Go engine in-process (no extra process, fail-closed hazard disappears), switch to Casbin embedded (Apache-2.0, RBAC-with-domains, fastest, weakest decision logs), or fall back to the in-house engine behind `authorizer.Check`. The docs/02 §11 rule 'PDP unreachable → deny' only applies to the sidecar mode. | Design review (docs/41 §3.2) | Tech Lead, BE-2 | Phase 1 start (before AUTH-13) | **Answered 2026-09-19 — Casbin, embedded** in the Go api, RBAC-with-domains model. Cerbos is superseded (ADR-14); the `authorizer.Check` interface is unchanged. See docs/41 §10. |
| D5 | Staff 2FA scope in V1: AUTH-09 as written (mandatory for every staff role) or finance + risk only? This is PRD open question 'Auth & Identity #1' restated as a build decision; it sizes the enrolment UX, recovery flow and support load for launch. | Design review (docs/41 §8) | Tech Lead, FunderBlu COO | Kickoff +2 days | **Answered 2026-09-19 — all staff roles, enforced at first login, with backup codes in V1**: AUTH-11 (backup codes) is promoted with AUTH-09; AUTH-29 (email change) and AUTH-28 (admin-assisted 2FA reset) become explicit V1 dependencies of the forced-enrolment path. |
| P1 | Which identity provider do we adopt (D1 = option C)? | Design review (docs/41 §10) | Tech Lead | Phase 0 exit | **Answered 2026-09-19 — ZITADEL**, self-hosted single instance + Postgres (AGPL-3.0, unmodified). Keycloak rejected on ops weight (1-2 GB, Java) and organisation fit; authentik rejected on hardening track record for fund-holding accounts. Legal review of AGPL obligations is a Phase-0 gate; policy: never patch ZITADEL source, contribute upstream. |
| P2 | Where do the login page and session live (D1 = C)? | Design review (docs/41 §10) | Tech Lead, BE-1 | Phase 0 exit | **Answered 2026-09-19 — IdP-hosted login + IdP tokens at the API.** Users log in on ZITADEL Hosted Login v2 (org-scoped via `urn:zitadel:iam:org:id:{id}`), the api accepts the ZITADEL access token and keeps a Redis deny-set + `auth_sessions` projection for immediate revocation (AUTH-07/20/27/39). Our `/v1/auth/login\|refresh` contract is retired in favour of OIDC endpoints; `contracts/api/auth.md` and `contracts/shared/openapi.yaml` are updated accordingly. |
| P3 | With SSO needed at cutover, how far does SSO/SCIM go in V1 (D2 = yes)? | Design review (docs/41 §10) | Tech Lead, Sales owner | Phase 0 exit | **Answered 2026-09-19 — SSO + SCIM for that tenant.** AUTH-24 and AUTH-25 both promoted into V1. ZITADEL limits SCIM to the User schema (no Groups, verified 2026-09-19), so deprovisioning is user-level; role assignment stays with us (P4) and group-to-role mapping is out of scope for the SCIM path. |
| P4 | Roles and membership: which system owns them (AUTH-12/13/14, TEN-32)? | Design review (docs/41 §10) | Tech Lead, BE-1 | Phase 0 exit | **Answered 2026-09-19 — our Postgres is authoritative** for tenant membership, roles, custom roles and the `resource.action` permission registry. ZITADEL organizations are used for login scoping, per-org policies and SSO routing; ZITADEL user grants mirror our roles only so tokens can carry them (Actions v2 `preAccessToken`), and a reconciliation job reports drift (TEN-32 access review). |
| D6 | Per-identity concurrent session limit (AUTH-07): the contracts/api/auth.md open item. How many active sessions may one identity hold at once, and what happens on overflow? | Design review (docs/42 §8) | BE-1, Tech Lead | Before contract freeze | **Open — default recorded:** 10 concurrent sessions per identity, oldest evicted (the newest login wins and the evicted session gets `auth.session_revoked` plus a `user.session_revoked` event with reason `concurrency_limit`). Raise only if trader feedback demands it; the running count lives in `auth_sessions` and is checked at `/v1/auth/session` time. |
| D7 | TTS cutover password posture (docs/25 §3.5, AUTH-01/05/17): import existing password hashes into ZITADEL (traders keep passwords) or force a reset at first login? | Design review (docs/42 §8) | FunderBlu COO, BE-1 | Cutover gate (M2) | **Open — default recorded:** force reset (`passwordChangeRequired=true`, the docs/25 §3.5 posture B). Import-and-keep is technically available since ZITADEL accepts hashed passwords when the source algorithm is enabled in the password-hasher verifier list (verified 2026-09-19, review G9); the COO can switch to posture A at the gate if TTS supplies verified per-user hashes with a supported KDF. |
| D8 | Tenant login hostname (docs/03 §3.8, TEN-05): does the tenant's own domain ever serve the login page in V1? | Design review (docs/42 §8) | Tech Lead, Sales owner | Before Phase 0 exit | **Open — default recorded:** no. V1 logins happen on `login.alpha1.io` scoped to the tenant organization (per-org branding, policies and MFA settings); tenant domains serve the app and the API only, with a silent OIDC redirect back to the tenant host after login. The vanity login host (`login.firm.com`, edge rewrite preserving the org scope) ships with TEN-05 in V2 if tenants ask. |
| D9 | GDPR erasure across two stores (docs/02 §10.4, AUTH-35): ZITADEL is event-sourced and does not de-identify past events (upstream issue #7811, open). Is the residual PII (email + display name in the IdP event stream) acceptable, or do we need a compensating control? | Design review (docs/42 §8) | FunderBlu COO, Tech Lead | Phase 0 exit (DPO review) | **Open — default recorded:** accept and document. We store no more PII in the IdP than email + display name (KYC profile and documents stay in our stores), the erasure procedure deletes the user and our rows, and the residual event entries are recorded as a known limitation with a DPO review at Phase 0 exit. Compensating control if the DPO refuses: pseudo-anonymous login names (`usr_{ulid}@login.alpha1.io`) with the notification email held only in our database. |
| D10 | Access/refresh token lifetimes and rotation (restates the open PRD workbook question as a build decision): ZITADEL's instance default is 12 h access tokens, so the 15-min figure in docs/02 §3.2 is documented but not enforced — what do we set, and where? | Design review (docs/43 §6) | BE-1, Tech Lead | Phase 0 exit (gate 6) | **Answered 2026-09-19 — access/ID 15 min, refresh idle 30 min, absolute 30 d, rotation on every use with reuse detection.** Written at provisioning through the instance OIDC-settings endpoint (`/admin/v1/settings/oidc`, update = method `PUT`, all four fields required, seconds precision) and read back at Phase 0 (docs/99 gate 6). This is the bound that holds when the deprovisioning pipeline *and* its alerting are both down (docs/43 §6). |
| D11 | How does an IdP-side deprovisioning (tenant SCIM deactivation, ZITADEL-console user removal, or user self-deletion) reach `tenant_memberships` before anyone notices — given that nightly reconciliation does not exist yet and Actions v2 event executions have no retry? | Design review (docs/43) | BE-1 | Phase 0 exit (gate 7) | **Answered 2026-09-19 — a pull consumer (`idp-sync`), not a webhook.** The worker polls ZITADEL's event log (`admin/v1/events/_search`, sequence cursor, 10 s) through a durable inbox and applies the AUTH-20 suspension path; covered event types, retry/DLQ/alerting and the nightly direction-aware reconciliation (safety net, never the mechanism) are specified in docs/43 §3–§7. Actions v2 event executions are rejected as the transport: no retry (upstream #10268) and instance-breaking event conditions (upstream #12225). |
| D12 | Self-service account deletion: ZITADEL lets a user irreversibly delete their own account (`user.self.delete`, reached via `ORG_USER_SELF_MANAGER` / `SELF_MANAGEMENT_GLOBAL`, from the console or the API). Do we grant it in V1 and accept that nothing in our stack can intercept it? | Design review (docs/43 §8) | FunderBlu COO (DPO), Tech Lead | Phase 0 exit (gate 8) | **Open — default recorded:** no self-delete-capable role grants in V1 and no self-service delete surface; closure runs through staff (V1 runbook → V2 `AUTH-35` flow) with business checks, a payout hold and the actor recorded as `system:account-closure`. Enforced by detection: an alert on `user.grant.added` containing `ORG_USER_SELF_MANAGER` and on `instance.member.added` containing `SELF_MANAGEMENT_GLOBAL`. The cost — no self-service erasure until V2 — is the DPO's call at gate 8 (docs/43 §8); the `defaults.yaml` role-permission override is a recorded Phase-0 option, not a default. |
| D13 | One person can hold one ZITADEL user per organization, but `identities` carried a single `idp_user_id` — a trader registering at a second tenant overwrites the first org's pointer, and that org's deprovisioning events (`user.deactivated` / `user.removed`) then resolve to no identity and land in the DLQ. What is the identity↔IdP join model? | Fourth-pass review (docs/44 §3) | BE-1 | Phase 0 exit (gate 10) | **Answered 2026-09-19 — `identity_idp_links` (one row per identity×org).** New table `identity_idp_links(idp_user_id PK, identity_id, idp_org_id, tenant_id NULL = platform, state active\|retired, first/last_seen, retired_at)`, `UNIQUE(identity_id, idp_org_id)`; `identities.idp_user_id`/`idp_org_id` demoted to a "last used" pointer. Login resolves link → `identity_key` fallback; `idp-sync` maps `aggregate_id` through links and holds the cursor plus alerts on an unknown link (never guesses a tenant); a deleted user's link is retired and stays as the audit alias (docs/43 §9). Written into docs/02 §3.1/§3.2/§9 and docs/43 §3/§4. |
| D14 | No role→permission-key binding existed for the 31-key registry and the tenant/platform role sets, so `authorizer.Check` had no policy to evaluate; the registry carried four decision-shaped TODOs (sensitive-data key per AUD-23, `audit.read`/`analytics.read` naming, trader self-actions, `payout.read_queue` masking). Derive and ratify now, or defer? | Fourth-pass review (docs/44 §4) | Tech Lead, BE-1 | Phase 0 exit (gate 9) | **Answered 2026-09-19 — derive and ratify now.** `contracts/permissions/roles.yaml` is the machine-readable source (12 roles in two realms, `scope` all/own/platform, effective holder sets closed under descendants, ABAC constraints recorded per key); it seeds the `casbin_rule` migration and `scripts/verify_roles.py` keeps YAML ⇄ seed ⇄ docs/02 §3.1 identical. TODOs closed: sensitive-data access = `kyc.document.read` + `payout.method.review` (audit-on-access, AUD-23); names ratified (`payout.read_queue` keeps its name); trader self-actions = declared keys with scope `own`; three platform keys promoted to V1 (`platform.identity.admin`, `platform.tenant.provision`, `platform.session.revoke`) and one reserved (`platform.analytics.read`). Platform role catalogs unified (`platform:super_admin` supersedes `platform:owner`/`admin`/`billing`). Registry now 36 V1 keys. |
| D15 | Casbin storage, reload, change-audit and boot behaviour were unspecified (ADR-14 said "rows in Postgres"; no DDL existed anywhere): where do the policies live, how do the api instances learn about a change, and what happens if the policy set cannot be loaded? | Fourth-pass review (docs/44 §4) | BE-1, DevOps | Phase 0 exit (gate 9) | **Answered 2026-09-19 — `casbin_rule` + versioning + Redis reload + fail closed.** The policy table is seeded **by migration** from `roles.yaml` (V1 has no policy-CRUD surface); every change bumps `authz_policy_versions`, writes an `audit_events` row, and publishes `casbin:reload` on Redis, with a ≤ 30 s version re-check so a missed message self-heals; an empty or unloadable policy set at boot denies everything and raises a SEV-1 alert — never allow. DDL and the change lifecycle are in docs/02 §9 (ADR-14 amended). |
| D16 | Fail-closed RLS (D3) has no exemption model: cross-tenant readers (relay, ledger/audit appliers, ANA, CON, `idp-sync`), the pre-tenant-context lookups (session by id, API key by hash) and console sessions (`auth_sessions.tenant_id IS NULL`) cannot work under the tenant policy as written, and migrations run under `FORCE ROW LEVEL SECURITY`. What is the exemption model? | Fourth-pass review (docs/44 §5) | DevOps, BE-1 | Phase 0 exit (gate 11) | **Answered 2026-09-19 — one named platform role, enumerated, with accessors for pre-auth reads.** `app_platform` holds `BYPASSRLS` and is used **only** by the enumerated cross-tenant services, whose queries must still carry explicit `tenant_id` predicates (CI grep-class check + review — RLS is their backstop, not their isolation); `app_rw` stays fail-closed; `migrator` is a discrete DDL job. The four context-free reads go through `SECURITY DEFINER` accessors in the `auth` schema (session by id, API key by hash, link by `idp_user_id`, console-session check); the platform-owned tables are listed explicitly so "every policy table" cannot be read as "all tables". docs/02 §9 + docs/28 §3.3. |
| D17 | P2 chose "IdP-issued tokens, no own rotating-refresh stack", but docs/02 §3.2 implemented rotation/reuse detection ourselves and the schema carried `refresh_hash` / `prev_refresh_hash`. Who owns refresh rotation and reuse detection? | Fourth-pass review (docs/44 §6.2) | BE-1 | Phase 0 exit | **Answered 2026-09-19 — ZITADEL owns rotation and reuse detection; we own the response.** The `refresh_hash` / `prev_refresh_hash` columns and our reuse-detection logic are removed; a reused token revokes its family in the IdP, and our side keeps the Redis deny-set, `auth_sessions` projection, `RevokeAllMyRefreshTokens` + `DeleteSession` kill and the CRITICAL audit. One owner per concern, no second refresh state to reconcile. |
| D18 | V1 API-key surface was contradictory: docs/02 §3.5 and blueprint step 7 build the primitives, while the GW chain, `contracts/api/auth.md` and the endpoint table all say keys are V2 with no endpoint. Which is it? | Fourth-pass review (docs/44 §7) | BE-1 | Phase 0 exit | **Answered 2026-09-19 — primitives only, internal consumers only.** V1 ships create/revoke/hash/scope helpers for service tokens and the future AUTH-21 surface; there is **no tenant-facing key endpoint** in V1, and the GW chain note now names the internal consumer instead of saying "keys are V2". Tenant machine integrations use TEN-11 integration secrets until AUTH-21 ships. |
| D19 | The token did not prove which tenant it was for: `tenants` carried no OIDC client/application binding, docs/02 said "one project + OIDC application" instance-wide while docs/03's saga provisioned a project per org, and a token minted for tenant A was accepted on tenant B's host. Per-tenant audience + session binding, or one shared application with an org claim? | Fifth-pass review (docs/45 G34) | BE-1 | Phase 0 exit (gate 12) | **Answered 2026-09-19 — per-tenant application + binding (option A).** One ZITADEL project + OIDC application **per tenant org**; `tenants.idp_client_id` is stored (client secret in the tenant secret store, referenced by `tenants.idp_client_secret_ref`). Every `/session` requires `aud` == that tenant's client id and checks the org claim when present; the `auth_sessions` row is bound to the tenant resolved from the request domain, so a token presented on another tenant's host is refused with the new `auth.tenant_mismatch` (403). Provisioning step 3 writes the binding. |
| D20 | `identity_key` was the mutable join key: `AUTH-29` rewrote it on email change, which silently creates a second identity for one person, moves the `AUTH-36` merge anchor and stops the old address resolving. Make the join key immutable with an email table, or keep one mutable key? | Fifth-pass review (docs/45 G35) | BE-1 | Phase 0 exit | **Answered 2026-09-19 — immutable key + email table (option A).** `identities.identity_key` = hash of the **first verified email** and never moves. New `identity_emails(identity_id, email_hash UNIQUE, email, is_primary, verified_at, retired_at)` is the match key for `/session`, `idp-sync` and `AUTH-36` merges; an email change adds a row and flips `is_primary`, and the old row is retained so a login on the old address still resolves to the same person (`identities.email` is only a cache). |
| D21 | Cross-org auto-link (an existing identity gaining a link in a new org) trusted an undefined "verified email" and had no abuse control — a matching address at a second org silently attached to the existing identity (identity poisoning). What gate applies? | Fifth-pass review (docs/45 G36) | BE-1 | Phase 0 exit | **Answered 2026-09-19 — verified-email gate + audited link (option A).** Auto-link requires a verified email (token `email_verified` **and** ZITADEL's user email state = verified). An unverified address creates a **separate identity + merge task** for staff. Every cross-org link writes a **CRITICAL** audit event and notifies the identity's existing org admins; the first org's contact details are never revealed to the second. |
| D22 | SSO group→role mapping was contradictory: decision P3 (AUTH-24/25 in V1) implied directory-driven roles, the provisioning saga said "map directory groups → roles", and the registry advertised a viewable map — while the ratified model assigns roles ourselves. And the `invited → active` membership transition was undocumented. Which V1 posture? | Fifth-pass review (docs/45 G37) | BE-1 | Phase 0 exit | **Answered 2026-09-19 — no group→role mapping in V1 (option A).** SSO users are assigned roles by us at onboarding (later via platform/ADM actions); directory groups only drive sign-in/provisioning. docs/03 step 3a and the registry `tenant.sso.read` wording are corrected, and the membership lifecycle is documented: `user.human.added`/invite → `invited`, first successful `/v1/auth/session` → `active`. |
| D23 | No V1 step-up existed although `payout.approve` requires a factor assertion < 5 min, the taxonomy already had `authz.step_up_required`, and the only planned step-up surface (AUTH-30) is V2. Where does V1 step-up live? | Fifth-pass review (docs/45 G38) | BE-1 | Phase 1 (payout approval) | **Answered 2026-09-19 — hosted re-auth, server-enforced (option A).** The web tier re-runs hosted login with `prompt=login&max_age=300`; the fresh token carries a new `auth_time` and the `api` enforces the ≤ 5 min freshness rule on the payout keys, returning `authz.step_up_required` (403, `details.max_age`) when stale. The API-owned step-up surface (challenge initiation, AUTH-30) remains V2; V1 has exactly one policy rule and it is enforced server-side, never in the UI. |
| D24 | ZITADEL's own admin plane was ungoverned: who holds `IAM_OWNER`, whether the Console/Admin API is reachable from the edge, and what the IdP break-glass is were all unstated — while the authz model assumes the IdP is trusted. What governance applies? | Fifth-pass review (docs/45 G39) | DevOps + BE-1 | Phase 0 exit | **Answered 2026-09-19 — private plane, two owners, quarterly review (option A).** The admin plane (Console, `admin/v1`, `management/v1`) is not reachable from the edge: internal network only, operator access via Cloudflare Access. Exactly **two named `IAM_OWNER` holders** (or one owner plus a sealed emergency credential in the ops vault), both with mandatory MFA (the `alpha1-platform` org is `force_mfa=true`). Every IAM role grant is part of the quarterly access review and is mirrored into our audit stream by `idp-sync` (`instance.member.*`). Runbooks: docs/06 §3.6; first execution is a Phase-0 checklist item (docs/34 §9). |
| D25 | Cross-tenant tenant-audit access from the platform realm: docs/05 named a `platform:compliance` role that does not exist in the ratified catalog (G30 closure), while docs/21 CON-01 assigns the console audit view to `platform:super_admin`. Who reads tenant audit cross-tenant (always critical-tier audited)? Options — A: platform:super_admin only (no new role/key); B: new key platform.audit.read bound to super_admin + platform:finance; C: add the platform:compliance role + key. See docs/48 §2. | Eighth-pass review (docs/48 F8) | Tech Lead | Phase 1 (LED/AUD build) | **Answered 2026-09-19 — option A:** `platform:super_admin` only, no new role, no new key. docs/05 §10 corrected to the ratified catalog; a dedicated key can still be proposed at the CON V2 freeze if finance/compliance oversight demands it. |
| D26 | The tenant chart of accounts is 'seeded at provisioning' (docs/05 §3.1) but the provisioning saga has no CoA step — the first order.paid post would fail `led.account_not_found`. Options — A: saga step 6b (idempotent, compensated); B: lazy seed inside ledger.Post; C: seed at the go-live checklist. See docs/48 §2. | Eighth-pass review (docs/48 F9) | BE-2 | Phase 1 (saga + LED build) | **Answered 2026-09-19 — option A:** the saga gains an idempotent, compensated step 6b (CoA template + platform-account links), documented in docs/03 §3.5 and docs/05 §3.1; the docs/47 saga summary counts 9 steps + 3a + 6b. |
| D27 | audit_events.seq was 'app-assigned via Redis INCR' while audit.Write is fail-closed (audit failure = sensitive action denied) and seq has no V1 consumer (the hash chain is V2) — a Redis outage would deny every sensitive action platform-wide. Options — A: drop seq from V1 (V2 chain-init backfills in id order); B: keep seq sourced from Postgres; C: keep Redis INCR and accept the coupling. See docs/48 §2. | Eighth-pass review (docs/48 F10) | BE-1 | Phase 1 (AUD build) | **Answered 2026-09-19 — option A:** V1 carries no seq; the V2 hash chain (AUD-14) introduces it at chain init, backfilled in id order. The fail-closed audit write is one INSERT in the action's transaction with no Redis dependency. |
| D28 | The V1 event catalog has zero EVL/BRG events, yet EVL is Phase-1 V1.0 and the binding machine edge ACTIVE→BREACH_DETECTED (EVL-17) consumes evaluation.verdict — the sheet cannot wire its own core loop. Which events enter the V1 catalog? Options — A: promote the Phase-1 five (evaluation.verdict, bridge.tick, account.day_rolled, account.activated, evaluation.daily_reset); B: promote only the breach-path three; C: keep them out as internal wiring (breaks the EVT-03/AUD-02 mirror + trace for the core loop). See docs/50 §2 F1. | Tenth-pass review (docs/50 F1) | BE-1 | Phase 1 (EVL/BRG build) | **Answered 2026-09-19 — option A:** all five promoted with payload schemas + examples; `bridge.tick` is the observed record (EVL-49) and does not mirror to audit (docs/05 §14 exception). |
| D29 | docs/09 §3.7 says an EVL-20 override (V1.1) transitions LCC back 'failed → active', but the binding state machine has no reverse edge out of FAILED and LCC-12's manual override-transition is V2 — a false-positive breach cannot be undone. Options — A: add guarded reversal edges BREACH_DETECTED→ACTIVE and FAILED→ACTIVE (override record = guard); B: reversal only before FAILED commits, post-FAILED is V2; C: never reopen — spawn a replacement account. See docs/50 §2 F2. | Tenth-pass review (docs/50 F2) | BE-1 | Phase 1 (EVL override build, V1.1) | **Answered 2026-09-19 — option A:** the two edges exist, valid only with a referenced override record (evaluation_overrides.id, kind clear_breach) + step-up; closed positions stay closed; BRG re-enables trading. Machine, diagram source, API contract and docs updated in the same decision. |
| D30 | Rule packs include time_limit (max_calendar_days) but the EVL-44 priority matrix never classifies it and the machine has no expiry edge, while account.expired exists with failed_reason 'expired' — what IS a time-limit expiry? Options — A: expiry is a breach verdict (rule_id=time_limit) through the existing breach path; B: a dedicated 'expired' verdict + machine edge + AccountExpired promoted to V1. See docs/50 §2 F3. | Tenth-pass review (docs/50 F3) | BE-1 | Phase 1 (EVL build) | **Answered 2026-09-19 — option A:** expiry is a breach verdict (matrix priority 1, after max_daily_loss; failed_reason 'breach:time_limit'); account.expired remains the NOT/ANA mirror event. One enforcement path to build and test. |
| D31 | LCC freezes trading_time_left while SUSPENDED, but EVL's day_rolled trigger increments calendar_days unconditionally and nothing gates evaluation on account state — a suspended account burns its calendar limit and racks up verdicts while frozen. Options — A: suspension freezes everything (no rollover event, EVL skips suspended ticks, resume re-evaluates on the next fresh tick); B: only the trading clock freezes, evaluation continues. See docs/50 §2 F4. | Tenth-pass review (docs/50 F4) | BE-1 | Phase 1 (LCC rollover build) | **Answered 2026-09-19 — option A:** the rollover job skips SUSPENDED (and terminal) accounts; EVL skips their ticks with WARN; clocks frozen; V1-Plus pause behaves the same (paused_at). docs/07 §3.3 + docs/09 §3.6/§5 updated. |
| D32 | FUNDED accounts have no breach edge: the V1 machine routes FUNDED only to SUSPENDED/TERMINATED, so a breach verdict on a funded account has no automatic transition (docs/50 F13). Options to consider — A: FUNDED→BREACH_DETECTED reusing the breach path (terminates via CLOSING); B: FUNDED→SUSPENDED automatic + risk review decides; C: funded breach = force-terminate path with extra guard. Not decided in the tenth pass. | Tenth-pass review (docs/50 F13) | BE-1 + PAY owner | Phase 4 wave 3 (trading depth) or first funded-account incident | **Answered 2026-09-19 — option A (twelfth pass, docs/52):** FUNDED→BREACH_DETECTED reuses the breach path (evidence, LCC-43 idempotency, CLOSING cleanup); in-flight approved payouts carry the hold flag (status_reason='on_hold', human queue); the RSK breach case auto-opens with payout_hold. The D29 FAILED reversal restores the pre-breach state (FUNDED for funded accounts). |
| D33 | docs/08 §3.3 bound V1 gap detection as per-login deal-ticket continuity (min(new) > last+1), but MT5 deal tickets are SERVER-GLOBAL counters — any other account on the server consumes tickets, so the check alarms on nearly every poll and EVL drowns in gap_flagged verdicts. Options — A: history-window count (deals in [last_synced_at−overlap, now] via history API vs rows written); B: defer gap detection to V2, V1 uses tick-staleness + nightly reconciliation only; C: keep the heuristic with a tuned threshold. See docs/51 §2 F1. | Eleventh-pass review (docs/51 F1) | BE-1 | Phase 1 (BRG sync build) | **Answered 2026-09-19 — option A:** the V1 check is the history-window deals-count reconciliation; last_deal_ticket is a fetch cursor only, never a continuity oracle. The pf-platform scaffold's bridge-assigned per-account seq is the same lesson (ordering cursors must be ours, not the broker's). |
| D34 | The D28 bridge.tick payload schema (5 fields) under-specified docs/08 §8's canonical shape (positions array, margin/free_margin, leverage, deals_count, last_deal_ticket), and §8 itself carried invalid JSON (leverage: 1:500). Which is canonical? Options — A: full §8 shape as the schema (fixing the JSON); B: minimal schema, consumers read PG. See docs/51 §2 F2. | Eleventh-pass review (docs/51 F2) | BE-1 | Phase 1 (BRG sync build) | **Answered 2026-09-19 — option A:** the full §8 shape is the canonical payload schema (positions array for TD live view + RSK V2; leverage as a string); schema + example regenerated and strictly validated. |
| D35 | docs/08 §3.3 binds 'every tick updates account_snapshots (1 row/account/min, 14-day rolling in PG)' but the table was defined nowhere (not §9, not docs/32, not ANA). Where does it live? Options — A: BRG-owned partitioned table; B: ANA read model only; C: drop the concept, rely on the events log. See docs/51 §2 F3. | Eleventh-pass review (docs/51 F3) | BE-1 | Phase 1 (BRG sync build) | **Answered 2026-09-19 — option A:** account_snapshots is BRG-owned (docs/08 §9): minute buckets, equity/balance/margin/free_margin cents + broker_time, daily partitions, 14-day rolling drop after the ANA daily rollup; PAY eligibility + TD intraday curves read here; BRG-09 refreshes the latest row on demand. |
| D36 | The BRG contract's open question: an admin 'force sync' endpoint would be a scope addition (BRG-09 on-demand sync is worker-internal, called by PAY-02/03 per docs/11). Options — A: keep worker-internal only in V1; B: add a V1-Plus admin endpoint + permission key. See docs/51 §2 F5. | Eleventh-pass review (docs/51 F5) | BE-1 | Phase 1 (BRG build) | **Answered 2026-09-19 — option A:** sheet-faithful — no admin force-sync in V1; ADM observes freshness via the health surface (docs/08 §7.2); revisit with the V2 broker-management surfaces (BRG-26/34). |
| D37 | No payout.requested event and no trader acknowledgment email exist in V1 (the not.md template-7 TODO); the sheet lists only approved/rejected/PayoutPaid. Options — A: no V1 requested event (201 + TD status is the ack; queue reads the table; template 7 reserved); B: promote payout.requested + NOT template (scope addition). See docs/52 §2 F6. | Twelfth-pass review (docs/52 F6) | BE-2 | Phase 1 (PAY build) | **Answered 2026-09-19 — option A:** no V1 request event; template 7 has no V1 trigger (V2 reserve). Sheet-faithful. |
| D38 | docs/11 conflicted on reserves: §3.6/§10 say V2 (PAY-37) while blueprint step 8 built the approval-time hard block early. Options — A: V1 = visibility only (CON dashboard cash-vs-obligations + queue banner; no hard block); B: early hard block at approval. See docs/52 §2 F7. | Twelfth-pass review (docs/52 F7) | BE-2 | Phase 1 (PAY build) | **Answered 2026-09-19 — option A:** V1 reserves = visibility only; the PAY-37 hard block (nightly + at approval) stays V2. Human approvers are the V1 control. |
| D39 | §3.1 binds 'eligibility re-checked at approval' but never says what a failed re-check does during approve. Options — A: approve fails with payout.ineligible, payout stays pending_approval (human decides); B: auto-reject on failed re-check. See docs/52 §2 F8. | Twelfth-pass review (docs/52 F8) | BE-2 | Phase 1 (PAY build) | **Answered 2026-09-19 — option A:** failed re-check = 422 payout.ineligible, payout stays pending_approval, no state change; the approver may reject manually with a reason. Pinned in docs/11 §3.7 guard 2. |
| D40 | docs/12 presented the refund state machine as 'binding V1' citing CHK-09, but CHK-09 is the order.paid→provisioning row — refunds are CHK-15 (V2.0), and the taxonomy's V1 baseline has no refund codes. Options — A: V1-Plus minimal manual refunds (ADM-only object; manual provider op + webhook confirm + LED reversal; no trader window, no auto-breach, no provider API); B: sheet-faithful, refunds fully V2; C: full §3.4 machine as documented. See docs/53 §2 F3. | Thirteenth-pass review (docs/53 F3) | BE-1 | Phase 1 (CHK build) | **Answered 2026-09-19 — option A:** V1-Plus minimal manual refunds; the machine/DDL are shared so V2 lights up the other triggers without re-modeling. |
| D41 | docs/12's V1 rails included bank wire (manual capture, 72 h) citing CHK-20 — a V2.0 row; the sheet's V1 rails are Match2Pay/Interkasa/NOWPayments only. Options — A: keep wire in V1 as a documented scope addition; B: demote wire to V2 (sheet-faithful). See docs/53 §2 F4. | Thirteenth-pass review (docs/53 F4) | BE-1 | Phase 1 (CHK build) | **Answered 2026-09-19 — option B:** wire demoted to V2 (CHK-20); V1 rails = Match2Pay + Interkasa + NOWPayments; the wire capture endpoint/TTL move to the V2 blueprint. |
| D42 | CHK-08 says the order record is created ON capture, CHK-42 says checkout submit never double-creates an order, and docs/12's DDL has orders in 'open' pre-payment — when does the order exist? Options — A: order at checkout submit (CHK-42, idempotent), capture moves open→paid; B: sheet-literal, order born at capture. See docs/53 §2 F5. | Thirteenth-pass review (docs/53 F5) | BE-1 | Phase 1 (CHK build) | **Answered 2026-09-19 — option A:** order at submit (status open), capture = the fulfillment record; also added the checkout_sessions DDL (CHK-02/43/44 — previously dictionary-only). |
| D43 | The KYC machine had three open edges (PENDING→EXPIRED undefined, APPROVED→EXPIRED 'P2', REJECTED→PENDING 'open question') and the DDL invented four non-KYC-06 states; the catalog's kyc.expired TODO blocked since Decision 5. Options — A: EXPIRED = 24 h session TTL only; APPROVED never expires in V1; REJECTED terminal (new session via cooldown); manual review = IN_REVIEW + is_manual_review flag; B: keep the edges with defined triggers. See docs/53 §2 F7. | Thirteenth-pass review (docs/53 F7) | BE-2 | Phase 1 (KYC build) | **Answered 2026-09-19 — option A:** pinned everywhere (module doc, diagram, DDL, catalog, api/kyc.md); DDL now carries KYC-06's exact seven states. |
| D44 | docs/12 §14 said purchase requires KYC (citing KYC-08, the payout gate); docs/13's duplicated gate tables disagreed (extended-only vs CHK-10 = V2); the sheet has no purchase-KYC row at all. Options — A: no V1 purchase gate (login-first checkout is the control; KYC-07 funding is the first gate; TTS L1-to-buy = V2 tenant config); B: V1-Plus purchase gate at session create. See docs/53 §2 F8. | Thirteenth-pass review (docs/53 F8) | BE-1 + BE-2 | Phase 1 (CHK/KYC build) | **Answered 2026-09-19 — option A:** no V1 purchase gate; docs/12 §14 and docs/13 §3.2 de-conflicted to one table. |
| D45 | The API success envelope has been a 'working draft — owner decision' since the research (api/gw.md's oldest TODO). Options — A: adopt the working draft {data, meta{request_id, version, pagination{cursor, has_more}}} as binding (matches every module's §8 examples + the shared OpenAPI envelope + GW-21 cursor pagination); B: flat {data} + pagination headers (churn against 11 modules' illustrated shapes). See docs/54 §2 F9. | Fourteenth-pass review (docs/54 F9) | BE-1 | Phase 1 (GW build) | **Answered 2026-09-19 — option A:** the working draft is binding; api/gw.md updated. |
| D46 | The extended surfaces used un-grouped paths (/v1/accounts, /v1/payouts, /v1/kyc, /v1/payments) while GW-01 binds grouped ones (/v1/trader/*, /v1/admin/*, /v1/console/*, /v1/webhooks/*). Options — A: grouped everywhere (the GW-01 groups are the plan; normalize the §7.2 illustrations); B: resource-style with realm by token (contradicts the binding groups and route-class gates). See docs/54 §2 F10. | Fourteenth-pass review (docs/54 F10) | BE-1 | Phase 1 (GW build) | **Answered 2026-09-19 — option A:** the GW-01 groups are the URL plan; docs/09/11/12/13 §7.2 normalized; internal /internal/* compose-only group documented. |
| D47 | V1 DLQ operations were undefined: a poison event lands in dlq.{consumer} + alert, but the CON list/retry screen is blueprint V2 and replay is V2 — no documented V1 recovery. Options — A: a relay dlq list/retry/purge subcommand in V1 (ops SOPS identity, AUD-logged; CON screen stays V2); B: alert-only with documented manual SQL; C: pull the CON DLQ screen into V1. See docs/54 §2 F11. | Fourteenth-pass review (docs/54 F11) | BE-1 | Phase 1 (relay build) | **Answered 2026-09-19 — option A:** the relay subcommand ships in V1 (blueprint step 2); the rule is no dead event without a retry or a recorded purge decision. |
| D48 | When a backing service dies (Redis / Postgres / the flag store), what should each gateway step do: keep working with defaults, serve slightly-old data, or refuse? The docs/55 §3.6 matrix proposes: fail open where the Cloudflare edge still protects (default + login rate limits, with a CRITICAL alert), fail closed where money is at stake (payout rate limit, idempotency claims), serve status-gate/entitlement caches stale for 30 s / 5 min then refuse — and never map an infrastructure failure to a suspension code. Approve the matrix or amend it? | Gateway solution spec (docs/55 §12 SOL-04) | BE-1 | Phase 1 (GW build) | **Answered 2026-09-20 — approved as proposed:** the docs/55 §3.6 degradation matrix is binding for the GW build (fail-open only where the edge guards, fail-closed on money paths, bounded stale-serving, infra failures never masquerade as suspension codes). |
| D49 | What does a client receive when it retries with the same idempotency key while the first request is still running? docs/55 §4.8 SOL-06 proposes: 409 request.idempotency_conflict (the registered code), with the in-flight claim held on a 15-minute lease; the client backs off and gets a clean replay after the first request finishes. Alternatives rejected: waiting server-side (cross-request pub/sub complexity in V1) and 425 Too Early (unregistered code — the registry gate forbids it). Approve? | Gateway solution spec (docs/55 §12 SOL-06) | BE-1 | Phase 1 (GW build) | **Answered 2026-09-20 — approved as proposed:** an in-flight duplicate gets 409 request.idempotency_conflict; the 15-minute in-flight lease stands; registered codes only. |
| D50 | Which error code does an unexpected platform failure (panic, unregistered failure) return? The taxonomy registers gw.internal but its HTTP cell was — (it was a UX-mapping row), and inventing a new code would fail the error-registry gate. docs/55 §4.12 SOL-07 proposes: pin gw.internal to HTTP 500 as the generic boundary code (message “Something went wrong on our side.”, plus X-Sentry-Event-Id for support). Approve the pin? | Gateway solution spec (docs/55 §12 SOL-07) | BE-1 | Phase 1 (GW build) | **Answered 2026-09-20 — approved:** gw.internal is the generic API boundary code at HTTP 500 (taxonomy UX row updated to match); no new code is invented; the Sentry event id travels in the response header for support. |

## Using this register

- **An open question is a design risk, not a blocker to writing docs** — the owning doc states the default it assumes and cites the question row; the answer then updates both.
- **Answered rows are decisions.** They are binding for contract freeze; the `docs/99-development-phases.md` gate checklist re-reads this register at each phase exit.
- **New questions** belong in `scripts/prd-workbook.json` (PRD rows) or `scripts/design-questions.json` (design-review rows) so this script picks them up, not in ad-hoc comments.

- **Design-review rows carry an ID (`D1`, `D2`, …)** and are cited by that ID from the module docs; PRD rows are cited as `<Section> #<n>`.


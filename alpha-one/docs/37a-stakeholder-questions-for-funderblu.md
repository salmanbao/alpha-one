# 37a — Open Questions, grouped by who can answer (hand-off for FunderBlu)

> Generated 2026-09-20 by `scripts/build_prd_registers.py` from `scripts/prd-question-triage.json` + `scripts/prd-workbook.json` (the docs/37 open rows). Do not edit by hand — answers are captured in the PRD workbook and the design-question register (the D-number convention), then this file is regenerated.
>
> **What this is:** the 197 open PRD questions from `docs/37-prd-open-questions.md`, regrouped by the stakeholder who can actually answer each one. **What it is not:** an answer sheet. Only the "Internal — Tech-Lead can decide now" section at the bottom carries proposed answers, each marked *Proposed — pending sign-off*; every other section needs the named stakeholder's decision. A question becomes *Answered* only when a real owner decision is recorded (workbook answer cell or a D-row in docs/37) — never by default.
>
**How to use it (suggested):** each stakeholder replies per question (copy the numbered list into a reply). When a decision lands: the Tech Lead writes it into `scripts/prd-workbook.json` (PRD rows) or `scripts/design-questions.json` (new D-row), re-runs `scripts/build_prd_registers.py`, and the owning module doc is updated in the same change.

## FunderBlu COO — 28 questions

| # | Section | Question | Note |
|---|---|---|---|
| 1 | Account Lifecycle | Which challenges get free retakes, how many, and is that configured per challenge or per tenant? | Commercial policy — retakes are a give-away with real cost. |
| 2 | Account Lifecycle | Do giveaway and partner accounts skip payout eligibility rules or use custom payout terms? | Commercial policy — non-commercial accounts and the payout gate. |
| 3 | Affiliate System | Does FunderBlu migrate its existing affiliate program at cutover, or keep it running externally until Phase 4 lands? This changes the migration plan. | Migration-scope decision (the module is deferred — docs/23/38 — so 'keep external' is the default until Phase 4). |
| 4 | Affiliate System | Commission basis in V1: first order only, or every order from a referred trader? | Commercial policy (V2 module, but the answer shapes the migration data model). |
| 5 | Affiliate System | What refund window length gates commission approval, for example 14 days? | Commercial policy. |
| 6 | Affiliate System | What is the minimum payout threshold and which payout rails do affiliates use, same as traders or separate? | Commercial policy. |
| 7 | Affiliate System | Does FunderBlu's current program use tiered or multi- tier commissions? If yes, V1 scope must change. | Fact about the current program — a 'yes' is a scope change to the deferred module. |
| 8 | Affiliate System | Can a trader also be an affiliate, and is self-purchase through own link blocked outright or flagged for review? | Program policy (self-referral = the fraud-adjacent edge; the spec's aff.self_referral block exists, the policy is COO's). |
| 9 | Auth & Identity | Does any V1 tenant require SSO or SAML, which would pull it into V1 scope? | Commercial fact — 'does any V1 tenant require X' is a sales/COO fact, not an engineering guess (ZITADEL ships SSO/SAML, ADR-13 — enabling it is a config + SCIM scope question). |
| 10 | Checkout & Billing | During migration parallel run, does FunderBlu keep its current external checkout and cut over per cohort, or switch all at once? | Cutover strategy (docs/25 parallel run) — a business-continuity call. |
| 11 | Checkout & Billing | Coupon stacking rules: one coupon per order, and can affiliate coupons combine with promo coupons? | Commercial policy (affiliates are deferred, so the combining half is a V2 input). |
| 12 | Checkout & Billing | Refund policy window and approval role: COO only or a finance role as well? | Money-control policy (the refund state machine exists, docs/12 §3.4; the window + role are the policy). |
| 13 | Competition / Gamification | Which prize types launch first: account credit, coupon, or cash payout, and which budget funds the prize pool? | Budget + prize policy (cash prizes = payout-engine coupling). |
| 14 | DevOps & Deployment | What RPO and RTO does the business accept, for example RPO 15 minutes and RTO 4 hours? | Business-acceptance question. The spec has already committed to RPO ≤ 5 min (pgBackRest, D55) and RTO ≤ 15 min promoted / ≤ 2 h worst case (D56, docs/06 §2.4) — COO confirms the business accepts those numbers; rejecting them overturns D55/D56, it is not a retune. |
| 15 | Ledger & Accounting | Confirm the V1 chart of accounts with the external accountant: are the seven accounts sufficient? | Accountant confirmation — the COO's office owns the external relationship. |
| 16 | Ledger & Accounting | Revenue recognition: recognize challenge fees at capture or defer until challenge completion? This needs an accountant ruling, not an engineering guess. | The question says it — an accountant ruling, not an engineering guess. |
| 17 | Ledger & Accounting | At what rate do we book crypto payments and payouts: capture-time rate recorded as metadata? | Accounting treatment (capture-time rate as metadata is the proposed treatment — COO/accountant confirm). |
| 18 | Ledger & Accounting | Who may post adjustments: COO only, or a finance role with dual control above a threshold? | Money-control policy (the adjustment mechanism + dual-control template exist, docs/05/21). |
| 19 | Ledger & Accounting | Confirm reporting currency and fiscal year for exports: USD and calendar year? | Accounting convention confirmation. |
| 20 | Payout System | Are partial payouts allowed by default across FunderBlu products, and what are the min and max thresholds per challenge? | Payout policy per product (the mechanics — PAY-02 available-profit formula — are spec'd; the policy values are not). |
| 21 | Payout System | Is auto-approve ever enabled in V1 or is approval manual only at launch? Recommended: manual at launch. | Money-approval policy. Spec posture: manual-only at launch (docs/11 — the API request path is always-manual); COO confirms. |
| 22 | Payout System | What is the second approval threshold amount for V1? | Money-control threshold. |
| 23 | Payout System | What are the payout frequency defaults per product: bi- weekly, monthly, or on-demand? | Payout policy per product (funded terms: `payout_frequency`, docs/11 §3.2 — the values are the policy). |
| 24 | Platform Console | Does the console show tenant financial revenue by default, or only usage counts until tenant billing exists? Recommended: usage counts only. | Sensitive-data visibility. PRD recommends usage-only until tenant billing exists (docs/22 V2). |
| 25 | Support Inbox | Does FunderBlu want the support inbox in the first cutover, or can Telegram/email remain primary until Phase 4? | Cutover-scope decision (the inbox is Phase-4 content in docs/99 — the question is whether FunderBlu waits). |
| 26 | Support Inbox | Should support staff be allowed to see payout destination details inside tickets, or should these remain masked unless the staff role has finance permission? | Sensitive-data visibility policy (payout destinations = financial PII). |
| 27 | Tenant Billing | Dunning policy: grace period length, and does past due mean suspension or read-only mode first? | Collections policy (the suspension machinery is spec'd, TEN-15; the grace/first-step is policy). |
| 28 | Tenant Billing | Do B2B collections reuse the trader payment adapters or a separate invoicing provider such as Stripe Billing? | Vendor choice for B2B invoicing (no Stripe in V1 for trader rails, docs/12 — B2B is a separate question). |

## FunderBlu Risk Owner — 19 questions

| # | Section | Question | Note |
|---|---|---|---|
| 1 | Account Lifecycle | On suspension with open positions: disable trading only, or close positions as well? | Risk posture on suspended accounts (disable = LCC-11 V1.1; close-positions adds the BRG-10 path). |
| 2 | Audit & Compliance | Which actions trigger real-time alerts in V1: payout above threshold, production rule change, bulk suspension, or others? | Alert policy (the AUD CRITICAL set exists, docs/05; the business list + thresholds are risk's). |
| 3 | CRM & Communications | Should segments be able to exclude traders with open risk cases from campaigns? Recommended: yes, by default. | Risk policy (raised with the Risk Owner). PRD recommends yes-by-default — the docs/20 segment model supports the exclusion. |
| 4 | Evaluation Engine | Daily drawdown reset follows broker server midnight or a tenant-configured reset time? | Risk semantics — the reset instant defines 'daily drawdown' (same question as the Bridge row; one answer for both). |
| 5 | Evaluation Engine | What is the default basis, equity or balance, for daily and max drawdown across FunderBlu products? | Risk semantics per product — drives the rule-pack defaults. |
| 6 | Evaluation Engine | Which rules are hard breach versus soft breach by default in V1 product configs? | Risk policy — hard breach = immediate disable+close (EVL-17 path); the default per rule is a risk call. |
| 7 | Evaluation Engine | Does auto-pass apply to the final evaluation phase or does live verification always require manual review, as TTS defaulted? | Risk process — manual review at the funded boundary is the conservative TTS default; Risk Owner decides. |
| 8 | Evaluation Engine | Is the consistency rule evaluated only at payout request or continuously on funded accounts? | Risk-monitoring scope (raised with the Risk Owner). Continuous = more enforcement commands; request-time = cheaper but slower. |
| 9 | Evaluation Engine | News calendar source in V1: manually maintained internal calendar or an external feed provider? | Risk-data input for the news-trading rule — a vendor + cost + reliability call owned by Risk. |
| 10 | Evaluation Engine | Do we support per-instrument rule sets in V1 or only global per-phase rules plus restricted symbol flags? Expected: global only. | Rule-semantics scope. PRD expects global-only — Risk Owner confirms the rule-pack model stays simple for V1. |
| 11 | Risk Management | Confirm the V1 detector set: IP overlap, device overlap, copy, inverse, and KYC reuse in V1, with payment reuse at P2. | Detector scope confirmation (raised with the Risk Owner). |
| 12 | Risk Management | What open and close time delta and symbol match window counts as correlated for the copy detector in V1? | Detector threshold — a risk-tuning number, not an engineering one. |
| 13 | Risk Management | What score thresholds auto-open a case per signal type, versus info-only signals? | Auto-open thresholds (the case model + D71 one-open-case rule are spec'd; the scores are risk's). |
| 14 | Risk Management | Does an open case block new challenge purchases as well as payouts? Recommended: payouts only in V1. | Risk policy. PRD recommends payouts-only — the spec's hold interlock (PAY-04/RSK-11, D68) covers payouts; purchase-blocking would be a new gate. |
| 15 | Risk Management | Who owns the risk staff role definition and the case review SLA, for example review within 24 hours? | Risk-ops ownership (role definition + SLA). |
| 16 | Support Inbox | Are traders allowed to appeal breaches through support tickets, and who can make final decisions on appeals? | Appeal authority is a risk decision (ties to the EVL-20 override record, docs/07 §3.2). |
| 17 | Trading Platform Bridge | Daily drawdown reset follows broker server time or a tenant-configured timezone? | Risk semantics — the reset instant defines 'daily drawdown'. (Same question raised under Evaluation Engine.) |
| 18 | Trading Platform Bridge | Default sync interval per account phase: same interval for evaluation and funded, or faster for funded? | Risk posture for funded accounts (more money at risk → tighter monitoring is the risk question, not an engineering one). |
| 19 | Trading Platform Bridge | Maximum tolerable sync outage before we alert traders or pause provisioning? | Risk tolerance question (raised with the Risk Owner in the PRD). |

## FunderBlu Ops Owner — 19 questions

| # | Section | Question | Note |
|---|---|---|---|
| 1 | Account Lifecycle | Which TTS account states map to which new states, and do imported accounts keep original rule versions or bind to new versions? | Migration plan (docs/25 cutover) — the mapping table is an ops artifact with risk sign-off. |
| 2 | Account Lifecycle | Credential delivery channels: portal only, email only, or both, and do we issue a read-only investor password? | Delivery policy (raised with the Ops Owner); the read-only investor password already exists in the spec (BRG-06/44). |
| 3 | Admin Panel | Which default roles ship in V1, for example admin, finance, risk, support, and marketing, and what permission subsets do they carry? | Role model — the permission *framework* is spec'd (roles.yaml, docs/02/46); which roles + subsets ship is the staffing call. |
| 4 | Admin Panel | Confirm masking policy: no staff role can view raw trader trading passwords, only trigger a resend. | Security-policy confirmation — the spec already implements 'resend-only' (BRG-13/17 V2, no raw reveal in V1); Ops confirms the policy for the role matrix. |
| 5 | Analytics & BI | Which roles receive financial reports by default, and does the support role see any analytics at all? | Role/permission policy — who holds which reports. |
| 6 | Audit & Compliance | Which roles may access the audit viewer: admin only, or also risk and finance? | Access policy (roles.yaml change + the quarterly review G39 covers it). |
| 7 | Auth & Identity | Is 2FA mandatory for all staff roles in V1, or only finance and risk roles? | Staff security policy (the spec already forces MFA on the platform org, docs/02/06 — the per-role breadth is Ops' call). |
| 8 | Auth & Identity | Do migrated TTS traders get a forced password reset at cutover or a reset-email flow? | Cutover procedure decision (migration runbook, docs/25). |
| 9 | Auth & Identity | Do we allow super admin impersonation of tenant admins for support, and under what audit rules? | Access policy (the view-as machinery + deny-list exist, docs/21; the allow + audit rules are Ops'). |
| 10 | DevOps & Deployment | On-call rotation and alert channel for a 4 to 5 person team: which Telegram group or phone tree? | Staffing decision: who is paged. The alert *set* is already defined (docs/06 §2.7/D76: CRITICAL pages), the roster is not. |
| 11 | KYC / Verification | Which role can approve KYC manually in the fallback path, and does it require dual control? | Role + control decision (the KYC-11 manual path is V1.1). |
| 12 | KYC / Verification | What is the acceptable SLA for manual KYC review? Current target is 4 hours but confirm with operations. | Staffing/SLA confirmation — the 4 h target is theirs to confirm. |
| 13 | KYC / Verification | Do we need to support KYC for traders who registered before the KYC module was live (migration backfill)? | Migration-scope decision (who gets re-verified, when). |
| 14 | Notification Service | How do we handle email bounces: suppress immediately, or allow manual override by support? | Support/ops procedure (suppression list ownership). |
| 15 | Platform Console | What impersonation scopes exist: read-only, full admin, or full admin excluding finance actions? | Access policy (the docs/21 view-as machinery supports scopes; which ship is the policy). |
| 16 | Platform Console | Who is on call for platform-level alerts versus tenant- level alerts, and what thresholds separate them? | On-call policy (pairs with the DevOps on-call row). |
| 17 | Support Inbox | What are the V1 support categories: account, payout, KYC, payment, breach, technical, general, or a different list? | Support-ops taxonomy — the team that staffs it defines the buckets. |
| 18 | Support Inbox | What are the SLA targets per priority, for example urgent first response within 1 hour and normal within 24 hours? | SLA targets — an ops-commitment, not an engineering number. |
| 19 | Trading Platform Bridge | Investor password: delivered by default in the credential email or only on request? | Credential-delivery policy (same family as the lifecycle 'delivery channels' row). |

## FunderBlu Product Owner — 34 questions

| # | Section | Question | Note |
|---|---|---|---|
| 1 | Admin Panel | Does the account detail include device activity and IP events in V1, or only after the risk detectors land in Phase 4? | Scope call — V1 risk surface vs Phase-4 detectors. |
| 2 | Admin Panel | Which reports map to the first read models: daily, monthly financial, challenge versus payout, country payout, top earners? | Report scope (pairs with the Analytics report-list rows). |
| 3 | Admin Panel | Email template editor in V1: text and variables only with locked layout, or full HTML? Recommended: text and variables only. | Scope call. PRD recommends text + variables — matches the NOT-01 template model (docs/14). |
| 4 | Advanced API / Developer Portal | Does partner-delegated access ship in the first iteration, or do we start with tenant-owned keys only? | Scope call (tenant-owned keys is the simple start). |
| 5 | Advanced API / Developer Portal | Who owns portal content, guides, and tutorials, and what keeps them current across releases? | Content ownership. |
| 6 | Analytics & BI | Confirm the exact V1 report list against the reports FunderBlu uses today in TTS: which of the eleven risk tabs map into V1? | Product scope — which TTS reports are V1-mandatory. |
| 7 | Analytics & BI | What timezone defines the daily and monthly cutoff for aggregates: tenant timezone or UTC? | Business-reporting semantics (same family as the 'reporting day boundary' row — one answer covers both). |
| 8 | Analytics & BI | Do we expose a report API to tenants for their own BI tools in V1? Recommended: no, CSV export only. | Scope call. PRD recommends CSV-only — matches the V1 surface (ANA-32 exports); the report API is a V2 candidate. |
| 9 | Analytics & BI | Which of TTS's report tabs must be reproduced at cutover, and which can wait? This gates cutover. | Cutover gate — Product owns the must-have list. |
| 10 | Analytics & BI | What is the business definition of an active account and a pass? These definitions must be pinned before any KPI is trusted. | Business definitions — the spec can only compute what the business defines. |
| 11 | Analytics & BI | Is reporting day boundary in tenant timezone or UTC? | Twin of the 'cutoff timezone' row — one answer. |
| 12 | Analytics & BI | Is nightly batch freshness acceptable for all reports, or do any reports need near-real-time? | Freshness expectation per report (V1 default: nightly batch; near-real-time list = scope addition). |
| 13 | Auth & Identity | Do we ship Google OAuth in V1 or defer all social login? | Scope call (ZITADEL supports it, ADR-13 — shipping it is a config + support-surface decision). |
| 14 | BYO Integration SDK | Which languages get official SDKs at launch: TypeScript and Python only, or more? | Scope call (V2 module — docs/01 phase 3; the launch set is product's to size). |
| 15 | BYO Integration SDK | Is the developer portal a separate documentation site or a section of the platform marketing site? | Product decision (docs hosting is the CMS/docs surface). |
| 16 | Checkout & Billing | Final V1 add-on list: reset, swap-free, and time extension only, or more? | Product scope — the add-on set at launch. |
| 17 | Checkout & Billing | Login-first checkout or guest checkout with quick signup? Recommended: login-first with fast signup. | UX scope call. PRD recommends login-first — the spec already builds login-first (docs/12 §1 'Login-first checkout'). |
| 18 | Competition / Gamification | Which scoring criteria ship in the first iteration: profit percent only, or also ROI and risk-adjusted score? | Product scope (the scoring engine is agnostic — docs/24). |
| 19 | Competition / Gamification | Do competition results and badges become part of the trader's permanent record and certificates? | Product/brand decision (touches the D61 closed certificate set). |
| 20 | Document Generation | Do we need a visual drag-and-drop template designer in V1? Recommended: No, use hardcoded templates with JSON config for variables. | Scope call. PRD recommends hardcoded + JSON config — matches docs/15 (DOC-01 templates with vars). |
| 21 | Document Generation | What are the exact V1 certificate types? Recommended: Challenge Passed, Funded Trader, Payout Receipt. | Product scope. PRD's recommendation matches the D61 set (docs/14: phase_passed, funded certificate via DOC-04). |
| 22 | Notification Service | Do we need SMS notifications in V1? Recommended: no, email and in-app only. | Scope call. Spec posture already excludes SMS from V1 (docs/14: email in V1; in-app + Telegram in V2). |
| 23 | Notification Service | Do broadcasts respect user notification preferences, or do they override them for critical system announcements? | Product policy — critical-announcement override vs preference respect. |
| 24 | Payout System | Post-payout balance handling: keep the remainder or reset to initial after a full payout? | Product mechanics — the HWM-based available-profit formula (docs/11 §3.2) works either way; the product decision is what 'full payout' means for the account. |
| 25 | Platform Console | Does tenant provisioning seed default challenge templates or start empty? Recommended: empty with an optional template library copy. | Onboarding UX. PRD recommends empty + optional library — the TEN-01 provisioning saga is agnostic to the seed. |
| 26 | Tenant Management | Who may edit the terminology map: tenant admin or super admin only? | Brand-control decision (the terminology map mechanism is TEN-32 V2 — the answer decides its scope too). |
| 27 | Tenant Management | Impersonation consent model: in-product consent per session or contract-level permission? | Product/UX policy (the docs/21 view-as machinery supports both). |
| 28 | Tenant Management | What happens to existing data when a module entitlement is disabled, for example affiliate commissions after affiliate is turned off? | Product semantics — disable = hide the surface, keep the data (the TEN-09 entitlement lifecycle exists; the data policy is product's). |
| 29 | Trader Dashboard | Does the trader portal include marketing and pricing pages in V1, or does the tenant's external website handle marketing and link into checkout? Recommended: external site links in. | Scope call. PRD recommends external site — consistent with CMS being V2 (docs/01 phase 3). |
| 30 | Trader Dashboard | Single theme per tenant or a user-toggleable dark and light mode in V1? Recommended: tenant theme only. | Scope call. PRD recommends tenant theme only. |
| 31 | Trader Dashboard | Which terminology strings does FunderBlu want customized at launch, for example challenge versus evaluation? | Branding content — the terminology map mechanism exists (TEN); the string list is FunderBlu's. |
| 32 | Website / CMS | First iteration scope: templates plus pricing widget only, or include blog from the start? Recommended: templates and widget only. | Scope call. PRD recommends templates + widget only. |
| 33 | Website / CMS | Does a hosted tenant site replace the tenant's existing website or coexist with it, for example platform hosts landing and pricing while the tenant keeps an external blog? | Product model (coexist is the likely answer — it changes little engineering). |
| 34 | Website / CMS | Do we offer import from WordPress or Webflow for existing tenant content, or start fresh only? | Scope call (import = a V2+ engineering investment). |

## FunderBlu Marketing — 5 questions

| # | Section | Question | Note |
|---|---|---|---|
| 1 | Affiliate System | What cookie duration applies by default, for example 30 days? | Attribution-window policy (marketing owns referral attribution). |
| 2 | CRM & Communications | Which automated sequences are must-have at launch for FunderBlu: welcome, cart abandonment, retry reminder, or re-engagement? | Campaign scope at launch. |
| 3 | CRM & Communications | Who writes and owns the marketing copy for sequences and campaigns? | Content ownership. |
| 4 | CRM & Communications | Does FunderBlu run an active Discord community today, and is role automation worth P2 effort? | Community-ops fact + effort judgment. |
| 5 | Notification Service | Who designs and provides the HTML/CSS for the 10 core email templates? | Design ownership — the platform ships the NOT-01 engine + the D61 closed template set (docs/14), the brand work is Marketing's. |

## FunderBlu Legal — 20 questions

| # | Section | Question | Note |
|---|---|---|---|
| 1 | API Gateway | Who defines and reviews the PII exclusion list for request logs? | PII policy (the redaction machinery exists, docs/04/28; the list is Legal's). |
| 2 | Audit & Compliance | What retention period applies per audit category, for example seven years for financial actions and two years for security events? | Retention schedule — jurisdiction-driven. |
| 3 | Audit & Compliance | Can traders view audit entries about themselves in V1? Recommended: no, data subject export on request only. | GDPR posture. PRD recommends no + DSR export on request — matches the docs/05 access model. |
| 4 | Audit & Compliance | What is the policy for KYC documents after account closure: anonymize, delete, or retain for the full financial retention period? | PII end-of-life policy (twin of the KYC-termination row — one answer for both). |
| 5 | CRM & Communications | Do we need explicit marketing consent capture at registration for EU traders in V1, or is consent implied by terms acceptance? | GDPR consent question — Legal owns it. |
| 6 | Competition / Gamification | Is the leaderboard alias-only by default with opt-in real names, and what does legal say about public performance data? | Public-performance-data question — Legal owns it (alias-only is the safe default). |
| 7 | KYC / Verification | What KYC verification level does each FunderBlu challenge type require at migration? Map each challenge to basic, enhanced, or skipped. | Compliance-level mapping per product — determines KYC-07/08 gates at cutover. |
| 8 | KYC / Verification | Do we require proof of address in V1 or only ID plus liveness as Veriff defaults? | KYC policy (jurisdiction-driven). |
| 9 | KYC / Verification | What is the restricted country list for V1, and does it apply at registration, at KYC, or both? | Jurisdiction policy; the enforcement points (registration gate + KYC-13) exist in the spec, the list does not. |
| 10 | KYC / Verification | How many resubmission attempts are allowed before final rejection? | KYC policy (same family as the 'before contact support' row). |
| 11 | KYC / Verification | Do we store only Veriff media references, or also cache documents in our object storage for manual cases? Recommended: manual cases only. | Data-retention choice. PRD recommends 'manual cases only' — consistent with the docs/13 §5 R2 retention posture; sign-off needed. |
| 12 | KYC / Verification | What is the KYC document retention period required by FunderBlu's jurisdiction? This determines KYC-31 configuration. | Jurisdiction retention law. |
| 13 | KYC / Verification | Does FunderBlu require proof of address for all challenges or only funded accounts? This affects KYC- 28 configuration. | KYC policy (funded = higher level is the usual answer; Legal confirms). |
| 14 | KYC / Verification | Do we need KYC re-verification on an annual cycle or only on document expiry? | Compliance cycle (V2 machinery, KYC-21/25 — the answer sets scope). |
| 15 | KYC / Verification | What happens to KYC data when a trader account is terminated? Immediate deletion, retention period, or anonymization? | PII end-of-life policy. |
| 16 | KYC / Verification | Does FunderBlu require selfie/liveness for all KYC levels or only enhanced? This affects Veriff configuration. | KYC level policy (Veriff configuration follows). |
| 17 | KYC / Verification | What is the maximum number of KYC resubmission attempts before the trader must contact support? | KYC policy (twin of the 'before final rejection' row — both need one number). |
| 18 | Risk Management | What is the retention period for signals and device logs? | Retention policy for surveillance data (sensitive PII-adjacent). |
| 19 | Tenant Billing | Billing currency and tax handling per tenant jurisdiction: who validates the rules, and do invoices need reverse- charge wording for EU tenants? | Tax compliance (reverse-charge wording is a Legal/finance question). |
| 20 | Website / CMS | Is published content subject to an approval workflow in regulated markets, and who approves? | Regulatory content-approval question. |

## FunderBlu CEO — 14 questions

| # | Section | Question | Note |
|---|---|---|---|
| 1 | API Gateway | Do per-tenant quotas ship in V1 or only after the second paying tenant? Expected: after. | Commercial trigger (the quota machinery GW-29 exists; WHEN it ships is a business call). |
| 2 | API Gateway | Do we expose a public tenant API in V1 or only inbound and outbound webhooks? Ties to the EVT-11 question. | Scope call. Spec posture: the public tenant API is V2 (docs/01 phase 3; EVT-11) — V1 = inbound provider webhooks + outbound tenant webhooks only. |
| 3 | Advanced API / Developer Portal | Do we monetize API access separately from plans with per-call pricing, or include quotas in tiers only? Ties into tenant billing. | Commercial decision. |
| 4 | BYO Integration SDK | Is public API access included in base plans or reserved for enterprise tiers? Ties into tenant billing. | Commercial tiering decision. |
| 5 | BYO Integration SDK | What is the support model for integrators: docs and sandbox only, or paid onboarding as professional services? | Professional-services commercial decision. |
| 6 | Competition / Gamification | What is the build trigger: named tenant demand or a marketing-led campaign plan? FunderBlu's previous competition module had zero conversions, so validate demand before spending effort. | Strategic build-trigger — the zero-conversion history is the case for demand validation first. |
| 7 | Event Bus & Webhooks | Do outbound tenant webhooks ship in V1 or immediately after MVP , given FunderBlu does not need them? | Scope call. Note: the platform SHIPS Hook0 in V1 (docs/01 §1.1 deployable; EVT-10/signed delivery) — the question is whether FunderBlu *uses* it at launch; the build-vs-use distinction is CEO's. |
| 8 | Platform Console | Who holds super admin seats at launch, by name, and what is the break-glass procedure if one is compromised? | Named humans — the break-glass *procedure* is already documented (docs/06 §3.6 runbook, G39: two IAM_OWNER holders, sealed credential, rotate on use); the seat-holders' names are the missing fact. |
| 9 | Tenant Billing | Confirm the pricing model: fixed plan plus usage overage, pure module-based pricing, or hybrid? This is a commercial decision, not an engineering one. | Commercial decision — the question says it is not an engineering one. |
| 10 | Tenant Billing | Which metering counters are billable: active traders, trading accounts, orders, API calls, or a subset? | Pricing mechanics — pairs with the pricing-model row. |
| 11 | Tenant Billing | Is FunderBlu itself a billed subscription or exempt as the owner tenant, and how is that represented? | Commercial self-dealing question. |
| 12 | Tenant Billing | Contract terms at launch: monthly only, or annual with discount? | Commercial terms. |
| 13 | Tenant Management | Do we support multiple brands or sub-tenants under one firm in V1? Expected answer is no. | Scope call. Spec posture: one firm = one tenant (docs/47 multi-tenancy model); sub-tenants are a structural V2+ question. |
| 14 | Website / CMS | What trigger justifies starting this module: a named tenant demand, a revenue threshold, or a sales commitment? | Strategic build-trigger (the module is V2 — docs/01 phase 3; the trigger decides WHEN). |

## Broker (Shadab) — 6 questions

| # | Section | Question | Note |
|---|---|---|---|
| 1 | Competition / Gamification | Do competition accounts use a separate demo group at the broker or reuse evaluation accounts, and does the broker support the needed group? | Broker capability question (group support) + the mapping decision. |
| 2 | Trading Platform Bridge | Does the broker contract grant API rights for account creation, disable, enable, close all, group assignment, and password reset, or are some manual in broker manager? If manual, enforcement and provisioning designs degrade. | Only the broker can answer. Every 'manual' item forces a human step into BRG-05/10/11 — get the API-rights list in writing before contract freeze. |
| 3 | Trading Platform Bridge | Which MT5 groups map to which phases, and who creates those groups at the broker, broker ops or API? | Broker-side topology + who operates it. |
| 4 | Trading Platform Bridge | If the broker does not offer MatchTrader, is cTrader the fallback second platform for V1? | Depends on broker platform support; the platform is MetaTrader 5 in V1 (docs/00/01). |
| 5 | Trading Platform Bridge | Can broker groups be created by API, or does broker ops create them manually per request? | Broker capability — same family as the API-rights row; 'manual' means a human step in provisioning. |
| 6 | Trading Platform Bridge | At what active account count does MetaApi per- account pricing become more expensive than Brokeree or self-hosted alternatives? | Vendor pricing data — a commercial input for the year-2 vendor review, not a V1 design input. |

## Sales (unassigned) — 4 questions

| # | Section | Question | Note |
|---|---|---|---|
| 1 | Advanced API / Developer Portal | Is the developer portal public before we have external tenants? Recommended: private beta docs for design partners, public at the second tenant. | Demand/timing call (raised with 'Sales owner (unassigned)'). |
| 2 | Advanced API / Developer Portal | Which API products ship first: read-only reports, webhooks, or account management? | Demand signal — what design partners actually need. |
| 3 | Advanced API / Developer Portal | Is GraphQL real demand or speculation? Recommended: defer until two tenants explicitly request it. | Demand validation. PRD recommends deferral until two tenants request it. |
| 4 | BYO Integration SDK | Which BYO paths get documented first based on real demand: checkout, affiliate, or KYC? | Demand signal — Sales owns it (unassigned role; the question was raised by 'Sales owner (unassigned)'). |

## External vendors (Veriff / payment rails) — 5 questions

| # | Section | Question | Note |
|---|---|---|---|
| 1 | Checkout & Billing | Which providers are confirmed for V1 launch: Match2Pay, Interkasa, and which crypto rail exactly? | Provider confirmations (the spec assumes Match2Pay + Interkasa + NOWPayments — docs/12 §1; the crypto network list is the open part). |
| 2 | Checkout & Billing | How many network confirmations for crypto payments before provisioning starts? | Rail-provider confirmation counts (NOWPayments); sets the fraud window before provisioning starts. |
| 3 | KYC / Verification | Does FunderBlu's Veriff contract include webhook endpoints or only polling? This affects KYC-05 implementation. | Contract fact only Veriff can confirm; the platform handles both (webhook + poll fallback, docs/13). |
| 4 | Ledger & Accounting | What settlement report format and availability does each provider offer: Match2Pay, Interkasa, and the crypto rail, CSV, API, or manual statement? | Provider fact — determines the nightly reconciliation input format (docs/12 §3.5). |
| 5 | Payout System | Which payout rails and networks are confirmed for V1: which crypto networks such as TRC20 or ERC20, and which fiat rail? | NOWPayments network support + the fiat rail choice. |

## Internal — Tech-Lead can decide now — 43 questions

These are the questions the Tech Lead can decide now; each carries a proposal marked *Proposed — pending sign-off*. Proposals adopt the PRD's own 'Recommended:' text where present, or the binding spec where it already decided the point. They are **not** decisions until FunderBlu (the relevant owner) signs off.

| # | Section | Question | Note |
|---|---|---|---|
| 1 | API Gateway | What are the default rate limits per route group for trader, admin, and webhook traffic? | Proposed — pending sign-off: the binding table (docs/55 §4.6) — per-user 100 rpm (tenant-plan adjustable), auth 10 / 5 min, payout 5 / h, Cloudflare per-IP edge limit outside; inbound provider webhooks are handler-deduped by provider event id (no app rate limit). |
| 2 | API Gateway | Versioning strategy: URL versioning only, or also header-based negotiation? Recommended: URL only. | Proposed — pending sign-off: URL only — the spec is built on /v1/... with Deprecation/Sunset headers (docs/55 GW-28; docs/04 §4.2 envelope). |
| 3 | Account Lifecycle | Is AWAITING_ACTIVATION a separate state or a flag on PASS_PENDING? Separate state recommended for clarity. | Proposed — pending sign-off: separate state — it is already a state in the binding LCC-02 machine (docs/07 §3.1 state diagram). |
| 4 | Account Lifecycle | How long do terminal accounts stay hot before archive, for example 12 months? | Proposed — pending sign-off: 12 months hot, then archive — sits inside the 13-month event-log window so replays still resolve them (LCC-27 cleanup, docs/07 §5). |
| 5 | Admin Panel | Bulk operation guardrails: maximum selection size and mandatory confirmation step? | Proposed — pending sign-off: max selection 500 per bulk operation + mandatory confirmation step (proposed default — the bulk endpoints don't exist yet, the guardrail ships with them, ADM-05 surface). |
| 6 | Advanced API / Developer Portal | Status page: build a minimal internal one or use an external provider such as Instatus? Recommended: external provider at launch. | Proposed — pending sign-off: external provider (Instatus) at launch — ops default, fits the docs/06 D57 monitoring stack (Uptime Kuma feeds it). |
| 7 | Analytics & BI | What is the read model rebuild procedure if a read model corrupts: full replay from the event log, and how long must that take? | Proposed — pending sign-off: full replay from the 13-month event log (docs/19 ANA-14 pattern); time budget at V1 scale to be fixed at the freeze — proposed target < 1 h, measured in the exit test. |
| 8 | Analytics & BI | How far back must trend data be retained for trend views? | Proposed — pending sign-off: 13 months — matches the event log retention the read models replay from (docs/19: 'retention 13 months (matches the events log, 04)'. Longer trends need the R2 archive, a V2 item). |
| 9 | Audit & Compliance | Does hash chaining ship in V1 or later? Recommended: later, since append-only storage plus restricted database access is sufficient for V1. | Proposed — pending sign-off: adopt 'later' — V1 = append-only + restricted DB access; the hash-chain columns are already reserved for V2 (docs/05: `prev_entry_hash` — V2 hash chain). |
| 10 | Auth & Identity | What are the access token and refresh token lifetimes and rotation rules? | Proposed — pending sign-off: 15-min access token (binding — docs/02/43: the 15-min access token bounds IdP-sync exposure); session expiry idle > 30 min / absolute 24 h (docs/02 §5); refresh rotation with reuse detection (`auth.session_revoked`, docs/02). |
| 11 | BYO Integration SDK | Sandbox data policy: synthetic data only, or masked production-shaped data? Recommended: synthetic only. | Proposed — pending sign-off: synthetic only — docs/28 PII posture (no production data in sandbox; the SDK-06 sandbox injects synthetic events). |
| 12 | BYO Integration SDK | How many days of webhook delivery history is replayable in sandbox and in production? | Proposed — pending sign-off: production replay from the 13-month event log (docs/04) — practical V1 window 7 days (the outbox trim horizon); sandbox 30 days of synthetic events. Proposed defaults, tunable at the V2 API freeze. |
| 13 | Competition / Gamification | What leaderboard update frequency is acceptable at launch: batch per sync cycle or near real-time? Recommended: batch per sync. | Proposed — pending sign-off: batch per sync cycle — the docs/24 design reads the same ANA read models; near-real-time would be a separate stream consumer. |
| 14 | DevOps & Deployment | What trigger moves us from Compose to Kubernetes: service count, tenant count, or multi-region? Recommended: none of these in year one. | Proposed — pending sign-off: adopt 'none of these in year one'. docs/06 §11 keeps K8s forbidden, revisited only at > 50 tenants or multi-region. |
| 15 | DevOps & Deployment | Backup retention period and off-host copy destination, for example a Hetzner Storage Box? | Proposed — pending sign-off: the 3-2-1 scheme is already binding (D55, docs/06 §2.4) — prod box + standby host + off-provider object store (B2/Wasabi, object lock, separate credentials); retention is tool-managed by pgBackRest, exact day-counts fixed at the freeze session. |
| 16 | DevOps & Deployment | Staging data: synthetic only, or anonymized production copies, and what are the anonymization rules? | Proposed — pending sign-off: synthetic only — no production PII ever lands in staging (docs/28 PII posture; consistent with the companion row 'synthetic-only approved'). |
| 17 | DevOps & Deployment | Do we need a bastion or VPN for production access in V1, or is keyed SSH with fail2ban sufficient? | Proposed — pending sign-off: keyed SSH + UFW + fail2ban + Cloudflare origin-auth in V1 (docs/28 §3.1); bastion is a V2 item. |
| 18 | DevOps & Deployment | PgBouncer in front of Postgres or application-level pooling only? Recommended: PgBouncer. | Proposed — pending sign-off: PgBouncer — already a V1 deployable (`db-proxy`, docs/01 §1.1). |
| 19 | DevOps & Deployment | V1 database strategy: single instance with rehearsed restore inside RTO, or warm standby from day one? Recommended: single instance plus drills. | Proposed — pending sign-off: as documented post-D56 — prod single box (accepted SPOF, ADR-9/10) PLUS the D56 warm standby (disaster replica, promote ≤ 15 min, docs/06 §2.4/§11). The PRD's 'single plus drills' predates D55/D56 and is superseded by them. |
| 20 | DevOps & Deployment | What are the load test target numbers: concurrent trader sessions, sync batch size, payout burst volume? | Proposed — pending sign-off: adopt the docs/29 capacity model — sync throughput per the docs/08 §11 rows (431 accounts ≈ 7.2 req/s; 5k accounts ≈ 83 req/s), load test at 10× V1 targets (docs/06 blueprint step 10, OPS-29 k6 scripts). |
| 21 | DevOps & Deployment | Is synthetic-only staging data approved, meaning no production PII ever lands in staging? Recommended: yes. | Proposed — pending sign-off: yes — docs/28 PII posture (no production PII in non-prod environments). |
| 22 | Document Generation | Do we need a QR code on the certificate for external verification in V1? Recommended: No, unique ID is enough for V1. | Proposed — pending sign-off: no QR — verification is the unique certificate hash via the /v1/documents/verify endpoint (docs/15; the D61 set ships hash-verification, not QR). |
| 23 | Event Bus & Webhooks | Redis Streams retention: what max stream length and retention window do we configure for V1? | Proposed — pending sign-off: per the docs/04 §11 parameters — MAXLEN ~100k per stream (approximate trim, keeps XADD O(1)); streams are transport only, rebuildable from the 13-month `events` log (docs/04 §5.4). |
| 24 | Event Bus & Webhooks | Event log retention period for replay: 90 days, 1 year, or permanent archive to object storage? | Proposed — pending sign-off: 13 months in PG, then archive to R2 — already binding (docs/04: 'retention: V1 keep 13 months, then archive to R2 (EVT-22)'). |
| 25 | Event Bus & Webhooks | Who approves event schema changes and version bumps to prevent contract drift between modules? | Proposed — pending sign-off: module owner proposes, contract gates enforce — ADR-7 additive-only versioning (bump `version` on payload change; unknown-higher → DLQ + alert), enforced by the docs/99 0.10 contract checks (catalog + schema + payload gates). A schema change is a PR against `contracts/` reviewed by the module owner + BE lead. |
| 26 | Event Bus & Webhooks | Is the outbox relay a separate process or a background worker inside the API binary for V1? Recommended: separate process. | Proposed — pending sign-off: separate process — binding (docs/01 §1.1 `relay` deployable; the failover story is docs/06 §3.7 / D76). |
| 27 | Event Bus & Webhooks | Do any V1 flows require stronger than at-least-once delivery plus idempotent consumers? Expected answer is no. | Proposed — pending sign-off: none — at-least-once + idempotent consumers IS the binding semantics (ADR-6/7, docs/04 §4.3); no V1 flow needs exactly-once at the bus level (money paths are guarded by idempotency keys + state machines instead). |
| 28 | Ledger & Accounting | Do ledger entries carry product and challenge tags in V1 for per-product revenue breakdown? Recommended: yes. | Proposed — pending sign-off: yes — via the existing `journal_entry.ref_type`/`ref_id` (docs/32) — the challenge/product resolves through the reference; no new columns needed. |
| 29 | Notification Service | Telegram bot hosting: run as a separate worker in our Hetzner stack or use a managed bot service? Recommended: separate worker. | Proposed — pending sign-off: no V1 decision needed — Telegram is a V2 channel (docs/14). When it lands: separate worker, per the PRD recommendation (it would run inside the `workers` deployable). |
| 30 | Payout System | Do affiliate commissions flow through this payout engine in V1? Expected: no, affiliate module is deferred. | Proposed — pending sign-off: no — the affiliate module is deferred (docs/23; out-of-scope register docs/38), so the V1 payout engine pays trader payouts only. Revisit when AFF lands. |
| 31 | Platform Console | Confirm console hosting on a separate subdomain with its own auth realm, isolated from tenant identity tables. | Proposed — pending sign-off: confirm — already binding (docs/02 §7.1 realm isolation; docs/21 console routes deny non-platform sessions structurally; `con.platform_role_required`). |
| 32 | Risk Management | Device fingerprinting in V1: ipinfo flags only, or add FingerprintJS now? Recommended: ipinfo now, FingerprintJS when volume justifies cost. | Proposed — pending sign-off: adopt 'ipinfo now' — the cost gate is a volume decision; the signal schema already carries device flags (docs/10 RSK signals). |
| 33 | Support Inbox | What file types and size limits are allowed for attachments? Recommended: images and PDFs only, max 10 MB per file. | Proposed — pending sign-off: adopt the PRD recommendation — images + PDFs only, 10 MB per file (docs/40 uploads-coverage limits). |
| 34 | Support Inbox | Does Telegram intake mean full two-way sync in V1, or only linking Telegram messages manually to a ticket? Recommended: defer full sync. | Proposed — pending sign-off: defer full sync — manual linking only in V1 (Telegram is a V2 platform channel anyway, docs/14; the CHT Discord/Telegram relay is Phase 4, docs/99 4.1). |
| 35 | Support Inbox | Do resolved tickets auto-close after a fixed period, and what is the default duration? | Proposed — pending sign-off: auto-close resolved tickets after 7 days (proposed default — ops-visible, trivially tunable per tenant later). |
| 36 | Tenant Management | Custom domain SSL in V1: manual via Cloudflare for SaaS, or automated certificate provisioning? | Proposed — pending sign-off: V1 is subdomain-only ({slug}.alpha1.io, docs/03); custom domain is the V1.1 provisioning step (docs/03 §3 step 5) with manual Cloudflare-for-SaaS at that point; automated certificate provisioning is a V2 item (TEN-05). |
| 37 | Trader Dashboard | What is the default polling interval for dashboard data: 30 seconds or 60 seconds? | Proposed — pending sign-off: SSE islands are the primary path with the TD-11 fallback (1/2/5/15 s backoff, docs/16 §3); default poll 30 s for live trading views, 60 s for static views (proposed default — the spec leaves the interval open). |
| 38 | Trader Dashboard | What columns and row limits apply to trade history CSV export? | Proposed — pending sign-off: columns = the TD trade table (ticket, symbol, side, volume, open/close price & time, profit); row limit 10,000 (proposed default — export is a docs/16 TD surface; the limit is tunable per tenant later). |
| 39 | Trading Platform Bridge | MetaApi or Brokeree for MT5? Decision criteria: provisioning API coverage, price per account, sandbox quality, support response. | Proposed — pending sign-off: MetaApi — it is the binding V1 choice (docs/01 §1.1 `bridge` row; the entire docs/08 design; docs/00 'MT5 via MetaApi in V1'). Brokeree comparison stays a V2 vendor-review input (see the pricing row). |
| 40 | Trading Platform Bridge | What is the default sync interval per tenant and the minimum safe interval given vendor rate limits? | Proposed — pending sign-off: per-account `poll_interval_s` default 60 (docs/32 `broker_accounts.poll_interval_s`); the interval widens ×2 automatically when p95 > 2 s and MetaApi rate limits are the binding constraint (docs/08 §3/§11). |
| 41 | Trading Platform Bridge | Do we store trader terminal passwords in our database or delegate password generation and delivery to the vendor? Needs a security review. | Proposed — pending sign-off: store platform-side, field-encrypted AES-256-GCM with key versioning (BRG-44; docs/32 `broker_accounts.credentials_enc`/`cred_key_version`). The security review at freeze verifies key handling — the storage decision itself is already made in the DDL. |
| 42 | Trading Platform Bridge | Enforcement retry policy: max attempts, backoff ceiling, and escalation SLA for ops response. | Proposed — pending sign-off: as designed in docs/08 — commands run `pending → executing → confirmed \| failed(retry) → dead`; reconnect retries 3 with 30 s halving backoff; a dead enforcement command never auto-retries past dead → CON CRITICAL + human (the escalation SLA is the on-call response time in the docs/06 runbooks). |
| 43 | Website / CMS | Hosting model on our stack: Nginx vhosts per tenant on Hetzner, or edge-rendered static pages? | Proposed — pending sign-off: Nginx vhosts on the same Hetzner stack — boring, in line with docs/06; the CMS module is V2, so the decision can land with that phase. |

---

Counts by stakeholder: FunderBlu COO 28, FunderBlu Risk Owner 19, FunderBlu Ops Owner 19, FunderBlu Product Owner 34, FunderBlu Marketing 5, FunderBlu Legal 20, FunderBlu CEO 14, Broker (Shadab) 6, Sales (unassigned) 4, External vendors (Veriff / payment rails) 5, Internal — Tech-Lead can decide now 43. Total: **197** of 205 PRD questions are open (8 answered — in the docs/37 register; answers captured in the workbook outrank prose elsewhere).


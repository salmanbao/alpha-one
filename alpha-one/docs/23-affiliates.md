# 23 — AFF: Affiliate System

> Covers PRD module **AFF** (29 requirements — all V3). Affiliates are
> prop-firm marketing's core channel: a trader/manager who refers funded
> traders earns commission on the referred revenue. V3 by PRD; the design
> doc exists now (the docs/00 commitment: schema + event contracts frozen
> while the foundations are fresh) so the V3 build is execution, not
> rediscovery.

## 1. Purpose & scope

**V3 (all 29):** registration & approval (AFF-01), attribution tracking
(AFF-03 — the first-party cookie/URL param model), coupon attribution
(AFF-04 — the promo codes that carry the affiliate id), the commission
rules engine (AFF-05 — per-affiliate rate cards: % of challenge revenue,
first-N-payouts bonus, tiered), commission accrual (AFF-06 — accrues on
**captured** purchase, clawback-able), refund & chargeback (AFF-07 — a
refunded purchase reverses the accrual), the approval window (AFF-08 —
accruals settle after the refund window, e.g. 30 d), the affiliate
dashboard (AFF-09 — links, stats, commission balance, history), payout
request & queue (AFF-10 — affiliate payouts are **manual finance ops**
through the console, not auto-rails), payout history & receipts (AFF-11),
**self-referral fraud detection (AFF-12)**, admin management (AFF-13),
reports (AFF-14), the conversion webhook (AFF-15 — the tenant's
integration point), materials library (AFF-16), affiliate events (AFF-17),
multi-tier commissions (AFF-18 — capped depth 2), the affiliate API
(AFF-19 — for the affiliate's own tools), attribution window (AFF-20),
affiliate payout methods (AFF-21/29 — same rails as PAY: crypto via
NOWPayments + local), tax form collection (AFF-22 — 1099/W-8 class
documents before payout), swap/refund discount rules (AFF-07/27:
chargebacks claw back; caps: max commission per referral, monthly cap),
fraud velocity checks (AFF-30 — an affiliate whose referrals all breach
in week 1 is a red flag → RSK signal).

**Out of scope:** auto-payouts to affiliates (manual + finance queue — the
same trust posture as PAY approvals; affiliate money is platform money out,
and it stays human-gated), tier-3+ depth (capped at 2 — the multi-tier
depth cap is a compliance choice: unlimited MLM depth is a regulatory
hazard).

Requirement coverage: `AFF-01..29` (all V3; the 29th/07/29 duplicates in the
PRD extraction are the refund/chargeback and payout-method pairs — one
capability each).

## 2. Architecture

```
 attribution (first-party only — the TD §10 rule):
   /r/{affiliate_code} link or ?ref= on the tenant site (CMS) →
   the signup flow stores the ref code on the identity (AFF-03) +
   sets a first-party cookie (30 d, the AFF-20 window)
   coupon: checkout applies ?code= → CHK order line (CHK §3.1 V2 promo
   layer carries the affiliate id) — the coupon IS the attribution for
   card-less funnels (AFF-04)

 events:
   payments.intent_captured (with order.affiliate_id) ─►
     AFF accrual: commission = f(rate card, order value, tier)
     → accrual row (status: accrued)
   payments.refund_settled / chargeback (CHK) ─► accrual reversed
     (the row is corrected with a reversal entry — the LED-04 pattern;
     no delete: the clawback is itself the audit trail)
   the 30-d approval window (AFF-08): accrual → settled at window close
     (worker, advisory-lock) — settlement = payable
   AFF-12/30 fraud checks (worker, nightly): velocity (referrals/day),
     quality (breach-rate of referred accounts — reads RSK/EVL data),
     device/IP clustering (feeds RSK-03/04's detectors, and reads them
     back for the affiliate's referrals)
   payout (AFF-10): affiliate requests → console queue (finance, 2FA +
     tax-form-present check) → manual execution (crypto via NOWPayments
     or local rail — the PAY-12 execution-record pattern reused) →
     receipt (DOC)
```

## 3. System design

### 3.1 The accrual model (the money-critical part)

```
accruals:
  id · tenant_id · affiliate_id · source_ref (order_id)
  basis (purchase|payout_bonus) · gross_cents
  rate (from the rate card at capture time — frozen, versioned)
  commission_cents · status (accrued|settled|reversed|cancelled)
  settled_at (window close) · reversal_ref (the refund/chargeback)
rate cards:
  id · affiliate_id · effective_from/to (versioned)
  { challenge_pct_bps, first_payouts_bonus: {count, pct_bps},
    tier_multipliers: {tier_2: 0.5} (depth-2 = half the tier-1 rate),
    caps: { per_referral_cents, monthly_cents } }
```

- **Frozen at capture** (the CHK §3.1 / PAY §3.2 discipline): a rate card
  change never touches an existing accrual.
- **Reversal, never deletion:** a refunded purchase reverses the accrual
  (new status + reversal entry referencing the refund) — "why did the
  affiliate's commission drop $400" is one query.
- **The window (AFF-08):** accruals become `settled` 30 days after
  capture **if no refund/chargeback** (the worker checks the order's
  refund state at close) — the affiliate's "available balance" is Σ
  settled, never Σ accrued (the dashboard shows both, labeled).

### 3.2 Attribution integrity (AFF-03/04/20)

- **First-party only** (no third-party tracking — the TD §10 rule):
  ref-code on identity (stored, not inferred) + the first-party cookie
  (30 d). The **last-touch wins** rule is explicit: a trader who clicks
  affiliate A, then B, then converts → B (the cookie/param at signup).
  Stored on the identity at signup time (the identity's `affiliation`
  row: affiliate_id, source, attributed_at, method) — one attribution,
  immutable (a correction = a console audit action + a new row, the
  MIG-grade data honesty).
- **Self-referral (AFF-12):** an affiliate cannot attribute their own
  identity (the signup checks: the ref code ≠ the affiliate's own
  identity/any identity sharing their KYC identity hash (KYC-08's
  detector data) or device/IP cluster (RSK-03/04)). The check runs at
  signup **and** nightly (the retroactive catch: a referral attributed
  pre-verification that fails the KYC-reuse check → attribution voided +
  RSK signal).

### 3.3 Fraud & quality (AFF-30/12 → RSK)

Nightly worker per active affiliate: referrals in 30 d, refund rate,
breach rate of referred accounts (EVL verdicts), device/IP overlap
among referrals (RSK-04 data), chargeback rate. Score ≥ threshold →
**RSK signal** (kind `affiliate_fraud`, the RSK-07 ingestion path) +
commission **hold** (accruals stay `accrued`, don't settle — the
affiliate sees "under review", the dashboard is honest) + console alert.
Release = RSK case decision (the RSK §3.4 action path: AFF hold
release is an RSK action type). The commission hold is the same posture
as the payout hold: the money doesn't move until a human says it can.

### 3.4 Payouts (AFF-10/11/21/22/29 — the finance queue)

- Affiliate requests payout (dashboard) → **pre-conditions**: settled
  balance ≥ minimum, **tax form on file** (AFF-22 — the document in DOC,
  the check in the queue), no active fraud hold.
- Console queue (finance, 2FA): the same record pattern as PAY-12
  (`affiliate_payout_executions`: provider, ref, state) — manual
  execution (crypto/local), the affiliate's method is field-encrypted
  like PAY methods (11 §9).
- Receipts via DOC; the payout history (AFF-11) in the dashboard.
- **Affiliate money is platform revenue-adjacent outflow** — it appears
  in BIL's platform books (22), not in any tenant ledger (the affiliate
  is contracted with the platform or the tenant per the rate card's
  owner — the `rate card.owner` field: `platform` (default) or
  `tenant:{id}` — a tenant-subsidized affiliate program bills the
  tenant through BIL-17 pass-through logic).

## 4. Events (topic `affiliate`)

| Event | When | Consumers |
|---|---|---|
| `affiliate.attributed` | signup attribution (method) | AUD (critical — money's origin) |
| `affiliate.accrual_created` | captured purchase with ref | AUD, ANA |
| `affiliate.accrual_settled` | window close, no refund | AUD |
| `affiliate.accrual_reversed` | refund/chargeback | NOT (affiliate notice), AUD (critical) |
| `affiliate.fraud_hold_set/released` | AFF-30/RSK interplay | NOT, RSK, AUD (critical) |
| `affiliate.payout_settled` | execution complete | NOT (receipt), DOC, AUD (critical) |
| `affiliate.conversion` (outbound, AFF-15) | the tenant's webhook (Hook0) | the tenant's system (V3 DVP surface) |

Consumes: `identity.created` (attribution window), `payments.intent_
captured` (accrual), `payments.refund_settled`/`chargeback` (reversal),
`account.breached`/`kyc.verified` (quality checks), `risk.case_decided`
(hold release).

## 5. Lifecycles

- **Affiliate:** `applied → approved (console, the approval is a human
  onboarding: identity + KYC-L2 + agreement) → active → suspended (fraud
  hold) → terminated`. (AFF-01: approval is **never** self-serve in V3
  launch — the first cohort is curated.)
- **Attribution:** immutable at signup (§3.2); correction = new row +
  audit.
- **Accrual:** §3.1 machine (`accrued → settled | reversed`; `cancelled`
  = the order was abandoned pre-capture — no accrual existed; keep the
  status for the dashboard's "pending" line).
- **Rate card:** versioned (§3.1) — changes are future-dated (effective_
  from), never retroactive.
- **Payout:** `requested → (pre-checks) → queue → approved (2FA) →
  processing → settled | failed (re-execute manually)` — the PAY-13
  machine, simplified (no trader-facing states).
- **Tax form:** `requested → uploaded (DOC) → validated (console) →
  current` (expiring forms re-request at payout time).

## 6. Error taxonomy

Namespace `AFF`:

| Code | HTTP | Meaning |
|---|---|---|
| `aff.not_approved` | 403 | Non-affiliate calling affiliate APIs (the dashboard/API surface) |
| `aff.self_referral` | 422 | Attribution attempt blocked (the signup surfaces "no referral applied") |
| `aff.attribution_expired` | — | Window (30 d) passed at signup (no attribution, not an error to the trader) |
| `aff.coupon_invalid` | 422 | (CHK wraps: the checkout code check) |
| `aff.tax_form_required` | 422 | Payout request without a current tax form |
| `aff.below_minimum` | 422 | Settled balance < payout minimum |
| `aff.fraud_hold` | 423 | Payout blocked by hold (reason class: "under review") |
| `aff.payout_state_conflict` | 409 | Duplicate payout request (one active per affiliate) |
| `aff.rate_card_missing` | 500-internal | Capture with ref but no effective rate card (fail: accrue at 0 + CRITICAL — never guess a rate) |
| `aff.tier_depth_exceeded` | — | Depth-3+ link ignored (structural cap, logged) |

## 7. API endpoints
> **Scope note:** AFF is not in the V1 execution sheet (V2 scope). There is no V1 baseline contract for this module; the surface below is design-level (post-V1, docs/99) and provisional until its phase's contract freeze.


Affiliate (their dashboard, console realm's affiliate org — or a separate
subdomain `aff.alphaone.example` if tenants want white-label affiliate
portals, V3 decision):
`GET /v1/affiliate/dashboard` (balance: accrued/settled/hold, links,
stats),
`GET /v1/affiliate/links` (+ `POST` — link generation with the code),
`GET /v1/affiliate/accruals` (history incl. reversals with reasons),
`POST /v1/affiliate/payouts/requests`, `GET /v1/affiliate/payouts`,
`GET|POST /v1/affiliate/methods` (encrypted, PAY-pattern),
`GET /v1/affiliate/tax-forms` (+ upload).

Console (AFF-13): `GET /v1/console/affiliates` (+ apply/approve — 2FA),
`GET /v1/console/affiliates/{id}` (attribution quality, accruals, holds),
`POST /v1/console/affiliates/{id}/rate-card` (versioned, future-dated,
2FA), `POST /v1/console/affiliate-payouts/{id}/approve` (2FA),
`GET /v1/console/affiliates/reports` (AFF-14).

Outbound (AFF-15/19): the tenant's `affiliate.conversion` webhook
(Hook0, EVT-10 egress pattern); a narrow affiliate API (API key,
scoped `affiliate:read`) for the affiliate's own tooling.

## 8. Schema (key shapes)

```jsonc
// GET /v1/affiliate/dashboard
{ "data": { "affiliate_id": "01J9AFF…",
    "balance": { "accrued_cents": 120000, "settled_cents": 95000,
                 "hold_cents": 25000, "lifetime_cents": 480000 },
    "links": [ { "code": "ali-7f", "url": "https://funderblu.example/r/ali-7f",
                 "clicks_30d": 310, "conversions_30d": 12 } ],
    "stats_30d": { "referrals": 14, "refund_rate": 0.07, "breach_rate": 0.31 } } }

// accrual (the audit-critical row)
{ "id": "01J9ACC…", "affiliate_id": "01J9AFF…", "order_id": "01J9ORD…",
  "basis": "purchase", "rate": { "card_version": 2, "challenge_bps": 1500 },
  "commission_cents": 7485, "status": "settled",
  "captured_at": 1758200000000, "settled_at": 1758459200000 }
```

## 9. Database design

```sql
CREATE TABLE affiliates (
  id          ULID PRIMARY KEY,
  tenant_id   ULID,                          -- NULL = platform program
  identity_id ULID NOT NULL,                 -- the person (KYC L2 required)
  status      TEXT NOT NULL DEFAULT 'applied'
    CHECK (status IN ('applied','approved','active','suspended','terminated')),
  code        TEXT NOT NULL UNIQUE,          -- the ref code
  agreement_ref TEXT,                        -- DOC: signed agreement
  approved_by ULID, approved_at TIMESTAMPTZ,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE affiliate_rate_cards (
  id          ULID PRIMARY KEY,
  affiliate_id ULID NOT NULL,
  owner       TEXT NOT NULL DEFAULT 'platform',   -- platform | tenant:{id}
  challenge_bps INT NOT NULL,
  first_payouts_bonus JSONB,
  tier_multipliers JSONB NOT NULL DEFAULT '{}',
  caps        JSONB NOT NULL,
  effective_from TIMESTAMPTZ NOT NULL, effective_to TIMESTAMPTZ,
  created_by  ULID,
  UNIQUE (affiliate_id, effective_from)
);
CREATE TABLE identity_affiliation (           -- the attribution record
  tenant_id   ULID NOT NULL,
  identity_id ULID NOT NULL,
  affiliate_id ULID NOT NULL,
  method      TEXT NOT NULL,                  -- link|coupon
  attributed_at TIMESTAMPTZ NOT NULL,
  voided      BOOLEAN NOT NULL DEFAULT false, -- self-referral catch
  void_reason TEXT,
  PRIMARY KEY (tenant_id, identity_id)       -- one attribution, immutable
);
CREATE TABLE affiliate_accruals (
  id            ULID PRIMARY KEY,
  tenant_id     ULID NOT NULL,
  affiliate_id  ULID NOT NULL,
  identity_id   ULID NOT NULL,                -- the referred trader
  order_id      ULID,                          -- basis: purchase
  basis         TEXT NOT NULL,                -- purchase|payout_bonus
  card_version  ULID NOT NULL,
  rate_bps      INT NOT NULL,
  gross_cents   BIGINT NOT NULL,
  commission_cents BIGINT NOT NULL,
  status        TEXT NOT NULL DEFAULT 'accrued'
    CHECK (status IN ('accrued','settled','reversed','cancelled')),
  captured_at   TIMESTAMPTZ NOT NULL, settled_at TIMESTAMPTZ,
  reversal_ref  TEXT,                          -- the refund/chargeback id
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_affacc_affiliate ON affiliate_accruals(affiliate_id, status, captured_at DESC);
CREATE INDEX idx_affacc_order ON affiliate_accruals(order_id);
-- payouts: affiliate_payouts + affiliate_payout_executions (the PAY-12
-- pattern, §3.4); affiliate_methods (field-encrypted, PAY-pattern)
```

## 10. Security & compliance

- **Commission is money leaving** — the full PAY-grade discipline: 2FA
  approvals, execution records, no auto-rails, the fraud hold (§3.3),
  critical-tier audit on every accrual/reversal/payout.
- **Attribution is money's origin** (AUD critical on `affiliate.
  attributed` — the "where did this revenue claim come from" chain:
  click → signup → order → accrual → payout is one queryable line).
- **Self-referral is the #1 affiliate fraud** (§3.2): the check uses the
  same detectors as RSK-08 (KYC reuse) — an affiliate is a person with
  skin in the game to game the system, so the detector set is applied
  to them first.
- **MLM depth cap = 2** (§1) — the compliance posture (tier-3+ pyramid
  depth is a regulatory classification risk in several jurisdictions the
  tenant base spans); the cap is structural (the accrual walker stops at
  depth 2).
- **Tax forms before payout** (AFF-22) — the pre-condition is enforced in
  the queue, not the API (both, actually: the API 422s, the queue
  re-checks — the PAY §3.1 double-check pattern).
- **Affiliate PII**: identities are real persons (KYC L2) — their
  payment methods are field-encrypted (PAY-pattern), the dashboard shows
  masked methods, commission data is visible to the affiliate only for
  themselves (the tenant sees the program totals in the console, never
  per-affiliate PII).
- **Webhook (AFF-15)**: outbound via Hook0 (EVT-10 egress), signed,
  replayable — the tenant's integration sees `{order_ref, amount,
  commission, tier}` — no PII in the webhook (the tenant gets numbers,
  not names).

## 11. Scalability considerations

- V3 launch scale: a few hundred affiliates, ~50k referrals/yr
  platform-wide — the accrual table is ~50k rows/yr, the nightly fraud
  worker is O(active affiliates × a few indexed reads) = seconds.
- Attribution is a signup-time check (one indexed read of the rate card
  + the self-referral detector reads) — zero added latency to the
  critical path beyond ~5 ms.
- The conversion webhook fan-out: per-capture, single delivery (Hook0
  retries) — no queue of its own.
- Leaderboards/contests (if CMP-01 competitions use affiliate links —
  they do, §24) share the same attribution path; no extra surface.
- The scaling story is the same as everywhere: PG + the advisory-lock
  workers; the first horizontal scale point is the nightly fraud worker
  at 10k affiliates (shard by affiliate id range — a config change).

## 12. Open-source solutions

| Option | Verdict |
|---|---|
| **In-house Go domain pkg** (this design) | **CHOSEN** — the accrual/reversal/hold model is small; the value is in the detector interplay (RSK/KYC) and the PAY-grade payout discipline, both native here |
| FirstPromoter/ReferralCandy/SaaS referral engines | Rejected: they own attribution + commission in a SaaS box — the self-referral checks would need our KYC/RSK data (PII out of house), and the payout discipline would fork from PAY's |
| Lago (BIL) for affiliate billing | Rejected for V3 launch: affiliate "billing" is a manual finance queue (the AFF-10 commitment); if auto-payouts ever ship, the PAY executor + the accrual model port directly (Lago models tenant subscriptions, not this) |
| NOWPayments (crypto payout rail) | CHOSEN (shared with PAY, §3.4) |

## 13. Technology stack

Go domain pkg (api + workers: window-close settler, fraud worker, payout
executor); Postgres (affiliates, cards, attribution, accruals, payouts);
NOWPayments/local rails (payouts); DOC (agreements, tax forms, receipts);
RSK/KYC (detector data both ways); Hook0 (conversion webhook); NOT
(notices); CON (management + payout queue); R2 (tax forms); Prometheus
(accrual volume, hold rate, window-close lag); Sentry.

## 14. Integration — internal modules (glue)

| Module | How |
|---|---|
| **CHK** | the coupon/promo layer (CHK §3.1 V2) carries `affiliate_id` on the order — capture events are the accrual trigger; refund/chargeback events are the reversal trigger |
| **RSK** | the hold interplay (§3.3): AFF sets the hold via an RSK action; RSK-03/04/08 data feeds the self-referral + fraud checks; `affiliate_fraud` is an RSK signal kind (RSK-07) |
| **KYC** | affiliate approval requires L2 (the KYC gate reads); the KYC-reuse hash is the self-referral detector's input |
| **PAY** | the method encryption, execution-record, and double-check patterns are reused as-is (11 §3.3/9); the rails are shared (NOWPayments + local) |
| **BIL** | tenant-owned rate cards bill the tenant (BIL-17 pass-through logic); affiliate payouts land in the platform's books (22 §14) |
| **CON** | affiliate management + the payout queue (console realm, finance role) |
| **DOC** | agreements, tax forms, payout receipts (new doc types: `affiliate_agreement`, `affiliate_receipt`, `tax_form`) |
| **NOT** | approval, settlement, reversal ("a referral was refunded"), hold, payout notices |
| **EVT/Hook0** | the `affiliate.conversion` tenant webhook (AFF-15) — the V3 DVP surface's first external event |
| **ANA** | program KPIs (referred revenue, refund rate, commission as % of referred revenue) |
| **AUD** | the full money chain (§10) mirrored critical-tier |

## 15. Integration — external tools

NOWPayments (crypto payouts), local rails (PAY-shared), R2, Postmark
(via NOT), Hook0, Prometheus/Grafana, Sentry.

## 16. Implementation blueprint (V3)

| Step | Owner | Est | Depends | Exit criteria |
|---|---|---|---|---|
| 1. Schemas (affiliates, cards, attribution, accruals) + attribution at signup (link/coupon, first-party, last-touch, window) | BE-2 | 3 d | AUTH, KYC, EVT | seeded signups: correct attribution; window expiry; last-touch; the row is immutable (edit attempt = audit-only correction) |
| 2. Self-referral detector (KYC-reuse hash + device/IP cluster) at signup + nightly retroactive void + RSK signal wiring | BE-2 | 3 d | 1, RSK-08/04, KYC | a seeded self-referral (same KYC hash) is voided + the RSK case opens with the evidence |
| 3. Accrual engine (capture → accrual, frozen rate, reversal on refund/chargeback, 30-d window settler) + property tests (recompute from order + card) | BE-2 | 3 d | 1, CHK events, LED pattern | seeded 30-day window: accrue → refund → reversal → settle-nothing; no-refund path settles exactly at day 30 |
| 4. Fraud worker (velocity/quality/cluster) + commission hold (RSK action) + console hold surface | BE-2 | 3 d | 3, RSK-13/14 | seeded bad affiliate (10 referrals, all breached week 1): hold set, dashboard honest, release via RSK decision |
| 5. Affiliate dashboard (links, balance, accruals, payout request, methods, tax forms) | FE-2 | 4 d | 3–4, DOC | end-to-end: approved affiliate earns on a sandbox purchase, requests payout, gets the receipt |
| 6. Console (approval, rate cards, reports, payout queue with 2FA + tax-form pre-check) + conversion webhook (Hook0) + tax form flow | BE-2 + FE-2 | 4 d | 5, BIL-17 logic, EVT-10 egress | a full payout in staging (manual rail): pre-checks enforced, execution recorded, tenant webhook delivered + replayable |
| 7. Multi-tier (depth-2) walker + caps + tenant-owned cards + reports + the affiliate read API (key-scoped) | BE-2 | 3 d | 3–6 | depth-3 link ignored (structural test); a tenant card's accruals bill the tenant in BIL |

**Risks:** affiliate fraud becoming the platform's #1 support cost
(mitigation: approval curation at launch (§5 — no self-serve), the
detector-first self-referral check, the hold before settlement, and the
fraud worker reading the *same* detectors as RSK — the fraud signal is
already built, AFF consumes it); commission disputes (mitigation: frozen
rate cards + reversal-never-delete + the audit chain query in §10 —
"show me why" is one screen in the console); tax/compliance drift across
jurisdictions (mitigation: tax forms gate payouts per the rate card's
`owner` jurisdiction — the form set is data, reviewed by FunderBlu's
advisor at V3 scope); attribution-privacy tension (the first-party cookie
is the boundary — no cross-site tracking, ever, the TD §10 rule extends
to marketing).

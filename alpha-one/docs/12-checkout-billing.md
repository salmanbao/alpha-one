# 12 — CHK: Checkout & Billing

> Covers PRD module **CHK** (46 requirements). CHK is the money-**in** side
> (PAY is money-out): the trader buys a challenge, we must prove we got the
> money, book it, and provision the account — or refund cleanly. The
> purchase→payment→provisioning chain is the platform's critical path: a
> stuck checkout = revenue leak and an angry trader who paid but has no account.

## 1. Purpose & scope

CHK owns: **payment intents** (orders + money capture via rails), **capture
confirmation** (the webhook truth), **invoice/receipt issuance**, **refunds**
(the state machine + provider ops), **reconciliation** (provider reports vs our
bookings), **payment methods** (for purchases — V2 saved cards/local details),
and **multi-currency** handling.

Rails (V1): **Match2Pay** (card + PK local), **Interkasa** (IN + PK local),
**NOWPayments** (crypto, same provider as payouts — deposit side),
**bank wire** (manual capture, 72 h confirmation — CHK-20). No Stripe in V1
(§4 decision). **Login-first checkout** (PRD default: you must be a signed-in
trader to buy — no guest carts).

Requirement coverage: `CHK-01,02,04,06,07,08,09,42,43,44` (V1.0) + `16,17,40` (V1.1) +
`03,05,10,11,12,13,14,15,18,19,20,21,22,23,24,26,28,29,30,31,32,33,34,35,36,38,39,41,45,46` (V2.0) +
`25,27,37` (V3.0).

## 2. Architecture

```
 trader (TD checkout) ──select package/rule set──►
   POST /v1/payments/intents ──► Order (line items, pricing snapshot)
        │ (login-first: session required; tenant from session)
        ▼
   PaymentIntent {provider, method} ──► provider redirect / deposit URL / wire instructions
        ▼
   provider processes (outside us) ──► WEBHOOK /v1/webhooks/{provider}
        │ (EVT-10: verify, ingest, idempotency, outbox)
        ▼
   capture: intent captured (amount, provider_ref, fee)
        ├──► LED: cash debit / challenge-revenue credit (LED-01/05)
        ├──► Invoice PDF (DOC) + receipt email (NOT)
        └──► account_purchased → LCC provisioning saga (07)
   failures: provider failed/expired → intent failed → order closed (no account)
   refunds (ADM or auto-breach): Refund state machine → provider → WEBHOOK →
        LED reversal entry + invoice voided
   nightly: provider report import → reconcile vs captured intents → exceptions
```

Components (research §3, adapted):
- **Catalog/pricing**: the tenant's **packages + rule sets** (TEN-23, docs/03)
  are the catalog — CHK prices them (base price, tenant override V2, currency
  conversion, V2 promos/affiliates/Aff-01 commission snapshot).
- **Order + Intent**: Order = "what was bought" (frozen line items + price);
  Intent = "how it's paid" (provider, attempt state). One order, N intents
  (retries on new rails).
- **Orchestrator**: webhook-driven (no polling for cards/local; wire = manual
  capture by finance).
- **Refunds**: first-class objects (CHK-09 state machine below), never implicit.
- **Reconciliation**: nightly job per provider (V2 formal jobs; V1: manual
  import + diff report to ADM).

## 3. System design

### 3.1 Pricing snapshot (CHK-05)

At intent creation, the price is **frozen** into the order:
`{package_id, rule_set_id, base_cents, currency, fx_rate (if converted),
fee_model, total_cents}` — from the **current** TEN pricing at that moment.
The PRD's multi-layer pricing engine (tenant overrides, promos, affiliate
discounts, tax) is **V2+** (CHK-03/04/38/46 + AFF-01); V1 = base price +
currency conversion only. The frozen snapshot means: a price change in TEN
mid-purchase never affects an in-flight order; invoices and LCC terms cite the
same numbers.

### 3.2 Intent state machine (CHK-15/16)

```
 created ──(trader goes to provider)──► pending
   pending ──webhook captured──► captured (terminal: success)
   pending ──webhook failed──► failed (trader may retry → new intent, same order)
   pending ──TTL (card 15 min / crypto 24 h / wire 72 h)──► expired
   captured ──(trader/ADM within window)──► refund_requested (see §3.4)
   captured ──webhook refunded──► refunded (terminal)
```

- **Idempotency:** provider webhooks carry a provider event id → `provider_events`
  (EVT-10) dedupes replays; a second `captured` for the same intent = logged
  anomaly, never double-booked (LED capture entry keyed on intent id).
- **Crypto specifics (NOWPayments):** min payment 100%, max 110% tolerance;
  underpaid → auto-fail at TTL (no partial captures); the 24 h window covers
  slow-chain confirmations.
- **Wire (CHK-20):** finance enters `POST /v1/admin/payments/wire/{intent}/capture`
  (manual, 2FA, bank ref) → captured. 72 h with no finance capture → expired.
- **Order state:** `open → (any intent captured) paid → (LCC saga started)
  provisioning → (LCC funded) fulfilled | (saga failed) failed_provisioning`
  (→ auto-refund, §3.4) `| (all intents expired/failed) abandoned`.

### 3.3 Invoices & receipts (CHK-10/11/12)

On `captured`: DOC renders the tenant-branded invoice (R2 object,
`invoices/{tenant}/{id}.pdf`), NOT emails the receipt link. V2: downloadable
from TD, invoice history, re-issuance on currency/fix (void + re-issue, the
original retained — no mutation).

### 3.4 Refunds (CHK-09 — binding state machine)

```
 refund_requested ──(provider op)──► provider_pending ──webhook──► refunded
 refund_requested ──ADM cancel (pre-provider)──► cancelled
 provider_pending ──webhook failed──► failed ──(retry)──► provider_pending
```

Triggers: (a) **auto-breach refund** — `account.breached` (LCC) with tenant
policy `auto_refund: true` (FunderBlu default **false** — breaches don't auto-
refund; the trader can request via support (CON) which creates the refund
object) — the PRD's "challenge failed auto-refund" default is tenant-configurable
and the config lives in TEN (`refunds.auto_refund`); (b) trader request
(pre-funding, within window — the terms' refund policy, e.g. "challenge not
started"); (c) finance/ADM manual (fraud, chargeback, support decision —
reason + 2FA).

Every refund: provider op with ref, LED **reversal entry** (LED-04 pattern —
never delete the capture entry), invoice marked `refunded`, trader notified
(estimated settlement time per rail). **Chargebacks** (V2 CHK-24): provider
webhook → the same object family (`chargeback_opened/won/lost`) — a lost
chargeback = reversal + RSK signal.

### 3.5 Payment methods (CHK-06/07/33, V2)

Saved card tokens live **provider-side** (Match2Pay vault — SAQ-A posture);
we store `provider_method_ref` + masked display. Local-method details
(wallet/bank ref for disbursement) encrypted like PAY methods. One-click
repurchase (CHK-07) = intent with saved method, no redirect.

### 3.6 Reconciliation (CHK-30/43/46 — V1 basic, V2 jobs)

Nightly per provider: import settlement/report file (R2 upload or API) →
match every `captured` intent's provider_ref & amount & fee → exceptions
(unmatched provider rows, mismatched amounts, missing fee data) → ADM finance
queue + audit. V2: automated ledger adjustments for fee drift (LED-13).

### 3.7 Multi-currency (CHK-17/18/34)

Base = USD (terms, ledger). Display/charge currencies: PKR, INR (V1, per
provider), USD (cards/crypto). FX rate: provider-provided at payment time
(local rails), frozen on the intent (no re-pricing). V2: our own rate source +
margin; FX gain/loss ledger accounts (LED CoA).

## 4. Events (topic `payments`)

### 4.1 V1 baseline events — authoritative

From `contracts/events/catalog.md` (the V1 execution sheet). Envelope EVT-03 (`id`, `type`, `version`, `tenant_id`, `occurred_at`, `payload`); schemas in `contracts/events/payloads/`. Producers write the outbox (EVT-01); consumers are idempotent by event id (EVT-05).

| Event | Producer (V1) | V1 consumers |
|---|---|---|
| `order.paid` | CHK-09 (payment captured, via CHK-07 webhook + CHK-08 order) | LCC-05 (provisioning), LED-04 (payment capture posting), ANA-01 |
| `checkout.session.expired` | CHK-43 (scheduled expiry worker, via outbox) | ANA-01 (funnel/abandonment read model) |

**Mapping to the extended model below:** `order.paid` = the extended `payment.intent_captured`; `checkout.session.expired` = the extended `payment.intent_expired` (added to V1 scope by Decision 7, 2026-09-16). The `checkout started / abandoned / completed` events of earlier drafts are NOT in the V1 sheet — abandoned-cart analytics is a scope change (catalog.md).

### 4.2 Extended (post-V1) event model — design-level

> The extended event set for V2/V3 (and internal V1 detail where marked); see the mapping above for how it relates to the V1 baseline. Topic, dedupe, and transport rules unchanged (docs/04 §5).

| Event | When | Consumers |
|---|---|---|
| `payment.intent_created` | intent issued | AUD |
| `payment.intent_captured` | webhook captured | LED (cash/revenue), LCC (saga start), DOC, NOT, ANA, AUD |
| `payment.intent_failed` / `payment.intent_expired` | webhook/TTL | NOT (trader: "complete your payment"), ANA |
| `payment.wire_captured` | manual finance capture | same as captured |
| `payment.refund_requested` / `payment.refund_settled` / `payment.refund_failed` | refund flow | LED (reversal on settled), DOC, NOT, RSK (V2 chargeback signals), AUD |
| `payment.chargeback_opened/won/lost` (V2) | provider | ADM, RSK, LED, NOT, AUD |
| `payment.reconciliation_exception` (V2) | nightly | ADM, CON, AUD |
## 5. Lifecycles

- **Order:** `open → paid → provisioning → fulfilled | failed_provisioning →
  (refund) | abandoned` (abandon = all intents dead, TTL 30 d then archive).
- **Intent:** §3.2.
- **Refund:** §3.4.
- **Invoice:** `issued → (refunded →) voided_by_refund | reissued (V2)` —
  the PDF object is immutable; void = new object + link.
- **Provider circuit breaker:** per provider, same pattern as PAY (5 fails →
  30 min; checkout offers alternative rails when a circuit opens).

## 6. Error taxonomy
### 6.1 V1 baseline codes — authoritative

From `contracts/errors/taxonomy.md` (the V1 execution sheet; module CHK). These are the exact codes the V1 surfaces return; the envelope is GW-18 (`code`, `message`, `correlation_id`).
| Code | HTTP | Meaning | User-facing message |
|---|---|---|---|
| `catalog.challenge_not_found` | 404 | Challenge not in tenant catalog | "This challenge is no longer available." |
| `checkout.coupon_invalid` | 400 | Coupon rejected at session reservation | "This coupon code is not valid." |
| `checkout.session_expired` | 410 | Price/coupon reservation window elapsed | "Your checkout session expired. Please start again." |
| `checkout.session_not_found` | 404 | Checkout session unknown or not owned by caller | "Checkout session not found." |
| `checkout.session_not_cancellable` | 409 | Session already completed or expired — nothing to cancel | "This checkout session can no longer be cancelled." |
| `order.not_found` | 404 | Order unknown or not owned by caller | "Order not found." |
| `order.not_retryable` | 409 | Payment not in a recoverable state | "This payment cannot be retried." |
| `receipt.not_ready` | 409 | PDF generation pending | "Your receipt is being prepared." |
| `webhook.signature_invalid` | 401 | Provider webhook signature failed | none (provider-facing) |


Namespace `CHK`:
### 6.2 Extended (post-V1) codes — design-level

> Below the V1 baseline (6.1); names in the GW-18 dotted convention. Rows duplicating a V1 baseline code were folded into the baseline table (the merged registry: docs/30).


| Code | HTTP | Meaning |
|---|---|---|
| `chk.order_invalid` | 422 | Package/rule-set combo not purchasable (TEN validation) |
| `chk.package_unavailable` | 422 | Package deactivated mid-checkout (price snapshot protects existing intents) |
| `chk.method_not_allowed` | 422 | Rail not enabled for tenant/currency (provider matrix) |
| `chk.login_required` | 401 | Guest checkout (login-first policy) |
| `chk.intent_expired` | 409 | Tries to pay a dead intent (new intent offered) |
| `chk.intent_conflict` | 409 | Concurrent webhook state race (last-write validated by state machine) |
| `chk.capture_mismatch` | 500-internal | Webhook amount ≠ intent (anomaly → anomaly ticket, not auto-accept) |
| `chk.refund_window_closed` | 422 | Trader request outside policy window |
| `chk.refund_conflict` | 409 | Refund on already-refunded/chargeback'd intent |
| `chk.provider_unavailable` | 503 | Circuit open (alternate rails suggested in response) |
| `chk.wire_awaiting_confirmation` | 200 + status | Wire not yet confirmed (72 h policy info) |
| `chk.fx_unavailable` | 422 | Currency unsupported for rail (V2) |
| `chk.chargeback_active` | 409 | New refund while chargeback open |

## 7. API endpoints
### 7.1 V1 baseline — `chk` (authoritative: `contracts/api/chk.md`)

| Method + path | Auth | Permission | Idempotency | V1 errors |
|---|---|---|---|---|
| `GET /v1/trader/catalog` | none required (public browsing) — TODO — needs owner decision; story TD-09 implies pre-login browsing | none | n/a | `catalog.challenge_not_found` |
| `POST /v1/trader/checkout/sessions` | Trader — TODO — needs owner decision (login timing) | trader self-action | required | `catalog.challenge_not_found`, `checkout.coupon_invalid`, `checkout.session_expired` |
| `DELETE /v1/checkout/sessions/{id}` | Trader (session owner) — CHK-44 (V1.0) | none — identity-scoped per Decision 2 (trader self-action; the row explicitly states "no permission key") | required | `checkout.session_not_found`, `checkout.session_not_cancellable` |
| `POST /v1/webhooks/payments/{provider}` | provider signature (EVT-10 shared verification utilities) | none (signature-authenticated) | required — dedupe by provider event id | `webhook.signature_invalid` |
| `POST /v1/trader/orders/{order_id}/retry-payment` | Trader — CHK-16 (V1.1) | trader self-action | required | `order.not_found`, `order.not_retryable` |
| `GET /v1/trader/orders/{order_id}/receipt` | Trader (owner) — CHK-17 (V1.1) | trader self-action | n/a | `order.not_found`, `receipt.not_ready` |
| `GET /v1/trader/orders/{order_id}/invoice` | Trader (owner) — CHK-40 (V1.1) | trader self-action | n/a | `order.not_found` |

Scope, request/response shapes, and per-endpoint notes: `contracts/api/chk.md` (field values in the research are owner TODOs until contract freeze; canonical JSON is fixed at freeze, per the docs/99 §12 rules).

### 7.2 Extended (post-V1) surface — provisional

> Not in the V1 execution sheet. Design-level; paths beyond the V1 baseline are provisional until the URL-plan decision (`contracts/api/gw.md`, open question). Shown for platform completeness (V2/V3 phases, docs/99).

Trader (TD): `GET /v1/payments/catalog` (purchasable packages × rules ×
pricing — from TEN, filtered by tenant policy),
`POST /v1/payments/intents` `{order:{package_id, rule_set_id, currency},
method}` → `{intent_id, redirect_url|deposit_instructions|wire_details, ttl}`,
`GET /v1/payments/intents/{id}` (status poll for the redirect-back UX),
`GET /v1/payments/orders` (own history: orders + invoices + refund status),
`POST /v1/payments/orders/{id}/refund-request` (policy-window check),
`GET /v1/payments/methods` + `POST|DELETE` (V2 saved methods).

Staff (ADM): `GET /v1/admin/payments?status=`, `GET /v1/admin/payments/intents/{id}`
(full detail incl. provider refs, redacted),
`POST /v1/admin/payments/wire/{intent_id}/capture` (2FA, bank ref),
`POST /v1/admin/refunds` (manual, reason, 2FA), `GET /v1/admin/refunds`,
`POST /v1/admin/reconcile/{provider}/import` (V2 job trigger).

Internal: `/v1/webhooks/match2pay`, `/v1/webhooks/interkasa`,
`/v1/webhooks/nowpayments` (EVT-10 ingress; the same NOWPayments path serves
PAY deposit rails — disambiguated by payload type).
## 8. Schema (key shapes)

```jsonc
// POST /v1/payments/intents → 201
{ "data": { "intent_id": "01J9INT...", "order_id": "01J9ORD...",
    "provider": "match2pay", "method": "card",
    "amount_cents": 49900, "currency": "USD",
    "redirect_url": "https://pay.match2pay.com/…",
    "expires_at": 1758285600000, "ttl_s": 900 } }

// GET /v1/payments/intents/{id} (redirect-back)
{ "data": { "status": "pending", "note": "Payment in progress — this page
    updates automatically. Do not submit twice." } }

// captured (event-derived order state, TD history)
{ "data": { "id": "01J9ORD...", "status": "provisioning",
    "invoice_url": "/r2/invoices/{tenant}/01J9ORD….pdf",
    "account_status": "account_opening", "paid_at": 1758282000000 } }
```

## 9. Database design

```sql
CREATE TABLE orders (
  id              ULID PRIMARY KEY,
  tenant_id       ULID NOT NULL,
  identity_id     ULID NOT NULL,
  status          TEXT NOT NULL DEFAULT 'open'
    CHECK (status IN ('open','paid','provisioning','fulfilled',
                      'failed_provisioning','abandoned')),
  line_items      JSONB NOT NULL,            -- frozen: package_id, rule_set_id,
                                             -- base_cents, currency, fx_rate, total
  amount_cents    BIGINT NOT NULL,
  currency        CHAR(3) NOT NULL,
  intent_ids      ULID[],
  invoice_id      TEXT,                      -- DOC object key
  saga_id         TEXT,                      -- LCC provisioning saga (EVT-17)
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  paid_at         TIMESTAMPTZ, fulfilled_at TIMESTAMPTZ,
  closed_at       TIMESTAMPTZ
);
CREATE INDEX idx_ord_tenant ON orders(tenant_id, created_at DESC);
CREATE INDEX idx_ord_identity ON orders(tenant_id, identity_id, status);

CREATE TABLE payment_intents (
  id              ULID PRIMARY KEY,
  tenant_id       ULID NOT NULL,
  order_id        ULID NOT NULL REFERENCES orders(id),
  provider        TEXT NOT NULL,             -- match2pay|interkasa|nowpayments|wire
  method          TEXT NOT NULL,             -- card|local:{kind}|crypto:{chain}|wire
  amount_cents    BIGINT NOT NULL,
  currency        CHAR(3) NOT NULL,
  status          TEXT NOT NULL DEFAULT 'created'
    CHECK (status IN ('created','pending','captured','failed','expired')),
  provider_ref    TEXT,                      -- provider's transaction id
  fee_cents       BIGINT, fee_currency CHAR(3),   -- from webhook (recon-verified)
  capture_at      TIMESTAMPTZ, expires_at TIMESTAMPTZ NOT NULL,
  idempotency_key TEXT UNIQUE,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_pint_tenant_status ON payment_intents(tenant_id, status, created_at DESC);
CREATE INDEX idx_pint_provider_ref ON payment_intents(provider, provider_ref);

CREATE TABLE refunds (
  id              ULID PRIMARY KEY,
  tenant_id       ULID NOT NULL,
  intent_id       ULID NOT NULL REFERENCES payment_intents(id),
  order_id        ULID NOT NULL,
  kind            TEXT NOT NULL,             -- trader|manual|auto_breach|chargeback
  status          TEXT NOT NULL DEFAULT 'refund_requested'
    CHECK (status IN ('refund_requested','provider_pending','refunded',
                      'failed','cancelled')),
  amount_cents    BIGINT NOT NULL,
  currency        CHAR(3) NOT NULL,
  reason          TEXT,
  provider_ref    TEXT,
  requested_by    ULID,                      -- identity (trader) or staff or 'system'
  provider_at     TIMESTAMPTZ, settled_at TIMESTAMPTZ,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_rfd_tenant ON refunds(tenant_id, status, created_at DESC);
CREATE INDEX idx_rfd_intent ON refunds(intent_id);

-- provider report files: R2 (reports/{provider}/{date}.csv) + a small
-- recon_runs table (provider, date, file_key, matched, exceptions[]) on V2
```

## 10. Security & compliance

- **Webhook trust:** signature verification per provider (EVT-10); amounts and
  statuses from webhooks are **verified against the intent** — mismatch =
  anomaly ticket, never silent capture (CHK_CAPTURE_MISMATCH).
- **PCI/SAQ-A:** card data never touches our servers (provider-hosted fields /
  redirect); we store tokens refs + masked PAN only; audit evidence kept for
  FunderBlu's acquirer reviews.
- **Manual wire capture** = 2FA + bank-ref + amount match or explicit mismatch
  note (fraud pattern: fake "wire sent" screenshots → the bank ref + finance
  verification is the control).
- **Refunds are critical-tier audit** (2FA, reason, approver ≠ requester for
  manual).
- **Chargeback loss** triggers RSK signal (V2) + LED reversal + trader notice
  (per terms).
- **Money math:** integer cents end-to-end (README convention); provider fees
  in the provider's currency, converted at the frozen rate for the ledger line.
- **Data:** provider refs in logs masked to last-4; intent detail API
  (ADM) includes full refs behind `firm:finance`/`firm:owner` + audit.

## 11. Scalability considerations

- Volume: ~50 checkouts/day V1; provider latency dominates (redirect +
  webhook 5 s–5 min); no queue depth concerns in V1.
- Webhook concurrency is the only "hot" path: EVT-10's single-process relay +
  per-provider consumer lanes keep it ordered and idempotent; p95 ingest →
  state change < 5 s target.
- Reconciliation: O(settled that day) — seconds.
- Invoice PDF: DOC worker async (never blocks capture); capture → event < 2 s,
  invoice in ≤ 30 s.
- At 10× (V2): provider lane workers scale horizontally (consumer group);
  `payment_intents` partitions by month at > 10M.

## 12. Open-source solutions

| Option | Verdict |
|---|---|
| **Match2Pay + Interkasa** (register) | **CHOSEN V1** — PK/IN cards + local (JazzCash/EasyPaisa/UPI/Paytm), webhook-capable |
| **NOWPayments** (register, shared with PAY) | Crypto deposits (dedicated address per intent or fixed address + amount match; V1: dedicated deposit URL from the provider) |
| Stripe (research default) | **Rejected** — not available on the FunderBlu rail mix (PK/IN local + crypto); Match2Pay/Interkasa cover the anchor tenant; Stripe added later only if a US tenant lands (adapter interface) |
| Hyperswitch | Rejected V1 (see PAY §12): 3–4 providers, thin needs |
| Wire = manual | No OSS for manual bank ops — ADM capture screen + 2FA is the whole design (CHK-20/21) |
| QuickBooks/Xero sync (research) | Consider-later (register) — V2 ANA/finance export first |
| Sift / Riskified / Signifyd (fraud scoring) | Rejected V1: manual review + (V2) RSK chargeback signals suffice at our volume; evaluate behind a `FraudScore` adapter if chargeback rate justifies it |

## 13. Technology stack

Go domain package (api) + webhook consumers (EVT-10 relay) + recon worker;
Match2Pay/Interkasa/NOWPayments REST; Postgres; LED (cash + challenge revenue
accounts); R2 (invoices, provider reports); DOC (PDF); NOT (receipt, refund
status); Postmark (via NOT); Prometheus (capture rate, webhook lag, refund
rate, circuit state); Sentry.

## 14. Integration — internal modules (glue)

| Module | How |
|---|---|
| **TEN** | packages + rule sets = the catalog (TEN-23); tenant pricing + provider matrix (which rails, which currencies); refund policy config (`refunds.auto_refund`) |
| **LCC** | `payment.intent_captured` → LCC provisioning saga start (07 §3.3, step 2: broker account open); saga failure → `failed_provisioning` → refund flow; `account.breached` + policy → auto-refund trigger |
| **LED** | capture: `cash` debit (tenant's money in) / `challenge_revenue` credit (LED-01); fee line; refund: reversal entries (LED-04); provider report recon feeds LED-13 adjustments (V2) |
| **KYC** | purchase requires trader verified for *purchases* (KYC-08 gate) — the catalog endpoint is visible; intent creation checks the gate (FunderBlu: L1 to buy, L2 for payout — TTS parity) |
| **RSK** | (V2) chargeback loss → signal; capture anomalies → signal (manual V1) |
| **AFF** (V2) | intent carries `affiliate_code` → commission snapshot (AFF-01) at capture |
| **DOC** | invoice/receipt PDFs; refund confirmation PDF |
| **NOT** | receipt, "complete payment", refund status, chargeback notice |
| **ANA** | conversion funnel (catalog view → intent → captured), rail success rates, refund rate by reason |
| **MIG** | FunderBlu: no in-flight purchases to import (new platform), but the
  first-week recon compares our captured set vs the tenant's bank statement |
| **TD** | checkout flow (select package/rule/rail → redirect → status → account
  opening live status via LCC events) |

## 15. Integration — external tools

Match2Pay (card + PK local), Interkasa (IN + PK local), NOWPayments (crypto),
manual wire (bank, human), R2, Postmark (via NOT), Sentry, Prometheus/Grafana.

## 16. Implementation blueprint

| Step | Owner | Est | Depends | Exit criteria |
|---|---|---|---|---|
| 1. Schemas (orders, intents, refunds) + pricing snapshot from TEN | BE-1 | 2 d | OPS, TEN, EVT | snapshot property test: TEN price change doesn't alter an existing order |
| 2. Intent creation + provider matrix (tenant rails × currencies) + TTLs | BE-1 | 2 d | 1 | each rail returns correct redirect/deposit/wire payload |
| 3. Webhook ingress (3 providers, EVT-10) + capture + idempotency + mismatch anomaly | BE-1 | 4 d | 2, EVT-10 | replayed webhook → exactly one capture; 1¢ mismatch → anomaly ticket |
| 4. LCC saga wiring (captured → provisioning → fulfilled/failed→refund) | BE-1 | 3 d | 3, LCC | sandbox: pay → account opening visible → funded (or failed → refund offered) |
| 5. Invoice (DOC) + receipt email + TD checkout UI (login-first) | FE-01 + BE-1 | 4 d | 3, DOC, NOT | end-to-end purchase in staging with real sandbox provider keys |
| 6. Refund state machine + provider ops + trader request + ADM manual (2FA) | BE-1 | 3 d | 3 | full refund cycle in staging (provider sandbox); reversal entry posts |
| 7. Wire manual capture (2FA + bank ref) + 72 h expiry | BE-1 | 1 d | 3 | finance captures a wire; mismatch note path works |
| 8. V1 recon: manual report import + diff report to ADM | BE-1 | 1.5 d | 3 | seeded 5-row report → 3 matched, 2 exceptions flagged |
| 9. Crypto rail specifics (deposit URL, 110% tolerance, chain confirmations) | BE-1 | 2 d | 3 | testnet underpayment auto-fails at TTL |
| 10. V2: saved methods, one-click, promos/affiliates wiring, tax (V2 flag), multi-currency margin, chargebacks, recon jobs, currency FX source | BE-1 + FE-01 | 3 wks | 8–9 | each behind Flipt flag per tenant |

**Risks:** provider webhook flakiness (mitigation: TTL + status poll fallback
in TD UI + recon catches the truth); PK/IN rail success rates below card
markets (mitigation: rail matrix + circuit breakers + the redirect UX says
"don't double-submit"); wire fraud (mitigation: 2FA + bank ref + finance
verification); double-purchase on double-redirect (mitigation: intent TTL +
one-active-intent-per-order + idempotency keys).

# Checkout API Contract (CHK)

Status: DRAFT
Owner: TBD
Version: v1
Last updated: 2026-09-17

Derived from the V1 Execution Sheet (V1.0 / V1.1). Nothing here is final until contract freeze.

## Scope
Catalog consumption, checkout session with price/coupon reservation, session lifecycle (expiry worker CHK-43 + trader cancel CHK-44 — Decision 7, 2026-09-16), payment provider adapters (Match2Pay, Interkasa, crypto rails — CHK-04), hosted payment flow, payment webhook handling, order creation, provisioning trigger, failed payment handling (V1.1), receipts (V1.1), invoice download (V1.1), client retry idempotency. (CHK-01, CHK-02, CHK-04, CHK-06, CHK-07, CHK-08, CHK-09, CHK-16, CHK-17, CHK-40, CHK-42, CHK-43, CHK-44)

Note: coupons are reserved in sessions (CHK-02) but coupon CRUD is not a V1 row — TODO — needs owner decision (management surface unspecified).

## Auth
Trader routes are public-or-trader per endpoint (browsing before login is implied by TD-09 purchase flow; login-required at checkout — TODO — needs owner decision). Webhook routes are provider-authenticated (signature per EVT-10).

## Tenant resolution
From domain (GW-02). Catalog is per-tenant (CHK-01: "my tenant's catalog").

## Permissions
- Purchase/checkout: trader self-action; no staff permission implied. TODO — needs owner decision whether a `checkout.create` key is required or checkout is anonymous-allowed.

## Idempotency
Required on checkout submit and order creation: client retries never double-create an order (CHK-42, GW-12). Webhooks deduplicate by provider event id (CHK-07, EVT-10).

## Endpoints

### GET /v1/trader/catalog
Auth: none required (public browsing) — TODO — needs owner decision; story TD-09 implies pre-login browsing
Tenant: from domain (GW-02)
Permission: none
Idempotency: n/a

Response 200:
```json
{ "challenges": [ { "challenge_id": "TODO", "type": "TODO", "sizes": "TODO", "prices": "TODO" } ] }
```

Errors:
- `catalog.challenge_not_found` 404 — requested challenge does not exist in tenant catalog # implied by CHK-01

### POST /v1/trader/checkout/sessions
Auth: Trader — TODO — needs owner decision (login timing)
Tenant: from domain (GW-02)
Permission: trader self-action
Idempotency: required # GW-12, CHK-42

Request:
```json
{ "challenge_id": "TODO", "size": "TODO", "add_ons": ["TODO"], "coupon_code": "TODO" }
```

Response 201:
```json
{ "session_id": "TODO", "reserved_price": "TODO", "reservation_expires_at": "TODO", "payment_url": "TODO" }
```

Errors:
- `catalog.challenge_not_found` 404 # implied by CHK-01
- `checkout.coupon_invalid` 400 — coupon rejected at reservation # implied by CHK-02 coupon reservation; exact code naming TODO — needs owner decision
- `checkout.session_expired` 410 — reservation window elapsed # implied by CHK-02 "limited window"

### DELETE /v1/checkout/sessions/{id}
Auth: Trader (session owner) — CHK-44 (V1.0)
Tenant: from domain (GW-02)
Permission: none — identity-scoped per Decision 2 (trader self-action; the row explicitly states "no permission key")
Idempotency: required # GW-12 (repeat cancels must not double-release coupon/price holds)

Request:
```json
{}
```

Response 200:
```json
{ "session_id": "TODO", "state": "cancelled" }
```

Errors:
- `checkout.session_not_found` 404 — unknown or not owned by caller # implied by CHK-44 identity scoping
- `checkout.session_not_cancellable` 409 — session already completed or expired # implied by CHK-44 "pending checkout session"; exact state guard — TODO — needs owner decision

Effects: releases the reserved price and coupon holds (CHK-44); marks the session cancelled (CHK-44); parent reservation model per CHK-02. Trader-initiated; the scheduled path is CHK-43 below.

### Checkout session expiry worker (CHK-43 — scheduled, not request-driven)
No HTTP surface. A scheduled worker (P0, V1.0) expires abandoned checkout sessions after the reservation window, marks them expired, releases the reserved coupon and price holds, and emits `checkout.session.expired` through the outbox (EVT-01) so that stale reservations never corrupt a later order. Parent model: CHK-02. Depends on CHK-02 + EVT-01. Scheduling mechanics (poll interval, clock) — TODO — needs owner decision; the `reservation_expires_at` column already exists in `data/dictionary.md` → `checkout_sessions`.

### POST /v1/webhooks/payments/{provider}
Auth: provider signature (EVT-10 shared verification utilities)
Tenant: from request subdomain (GW-02, TEN-02). Provider webhook URLs are provisioned per tenant: `https://{tenant-subdomain}.platform.com/v1/webhooks/payments/{provider}`
Permission: none (signature-authenticated)
Idempotency: required — dedupe by provider event id # CHK-07, EVT-10

Request: provider-specific payload — TODO — needs owner decision per adapter (Match2Pay, Interkasa, crypto rails)

Response 200:
```json
{ "received": true }
```

Errors:
- `webhook.signature_invalid` 401 — signature verification failed # implied by EVT-10

Effects: on payment captured — transition payment state (CHK-07), create order (CHK-08), emit order.paid (CHK-09) triggering provisioning (LCC-05), post ledger entries (LED-04).

### POST /v1/trader/orders/{order_id}/retry-payment
Auth: Trader — CHK-16 (V1.1)
Tenant: from domain (GW-02)
Permission: trader self-action
Idempotency: required # GW-12

Request:
```json
{}
```

Response 200:
```json
{ "payment_url": "TODO" }
```

Errors:
- `order.not_found` 404 # implied by CHK-16
- `order.not_retryable` 409 — payment not in a failed/recoverable state # implied by CHK-16; state set — TODO — needs owner decision

### GET /v1/trader/orders/{order_id}/receipt
Auth: Trader (owner) — CHK-17 (V1.1)
Tenant: from domain (GW-02)
Permission: trader self-action
Idempotency: n/a

Response 200: PDF receipt (generated via DOC-01 Puppeteer) # CHK-17

Errors:
- `order.not_found` 404 # implied
- `receipt.not_ready` 409 — generation pending # implied by async DOC-01 pipeline; sync vs async — TODO — needs owner decision

### GET /v1/trader/orders/{order_id}/invoice
Auth: Trader (owner) — CHK-40 (V1.1)
Tenant: from domain (GW-02)
Permission: trader self-action
Idempotency: n/a

Response 200: invoice PDF # CHK-40

Errors:
- `order.not_found` 404 # implied
- Invoice numbering/tax fields — TODO — needs owner decision (Out Of Scope: no automatic tax calculation; manual tax fields only)

## Events emitted
- `order.paid` — payment captured — CHK-09 (producer), consumed by LCC-05, LED-04, ANA-01.
- `checkout.session.expired` — reservation window elapsed — CHK-43 (producer, via outbox; added by Decision 7, 2026-09-16), consumed by ANA-01. See `contracts/events/catalog.md`.
- Failed-payment events: implied by CHK-16 (notify trader via NOT-05) — TODO — needs owner decision on event name and producer Req ID.

## Open contract questions
- TODO — needs owner decision: checkout session TTL duration (CHK-02 "limited window"; CHK-43's "reservation window" — the lifecycle mechanism is now decided, the duration is not).
- TODO — needs owner decision: coupon model — CHK-02 reserves a coupon but no V1 row defines coupon creation, validation rules, or usage limits.
- TODO — needs owner decision: add-on catalog representation (TD-09 mentions add-ons; CHK rows do not define them).
- TODO — needs owner decision: provider webhook payload schemas for each of the three rails (Match2Pay, Interkasa, NOWPayments crypto).
- Resolved 2026-09-17: webhook tenant routing — per-tenant subdomain (GW-02, TEN-02); provider webhook URLs are provisioned per tenant. No second tenant-resolution mechanism.
- TODO — needs owner decision: order numbering / invoice numbering scheme (CHK-08, CHK-40).
- TODO — needs owner decision: refunds — Out Of Scope says V1 records chargebacks only; confirm refund endpoint absence is intentional.

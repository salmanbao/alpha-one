# Gateway API Contract

Status: DRAFT
Owner: TBD
Version: v1
Last updated: TODO

Derived from the V1 Execution Sheet (V1.0 only). Nothing here is final until contract freeze.

## Scope
Single entry point with route-group separation, tenant resolution middleware, authentication middleware, authorization middleware, rate limiting, idempotency keys, and the platform-wide error contract. (GW-01, GW-02, GW-03, GW-04, GW-05, GW-12, GW-18)

## Nature of this contract
The gateway is in-app middleware behind Cloudflare (BVR-12: no standalone gateway product). This file defines the cross-cutting request/response contract that every module contract inherits.

## Route groups (GW-01)
One API exposing four route groups, separation enforced at the routing layer:
- `/v1/auth/*`, `/v1/trader/*` — trader portal surface
- `/v1/admin/*` — tenant admin surface
- `/v1/console/*` — platform console (separate auth realm, CON-01)
- `/v1/webhooks/*` — provider webhooks (payments CHK-07, KYC KYC-05)

Exact prefixes per module — TODO — needs owner decision (the sheet fixes the groups, not the URL plan).

## Tenant resolution (GW-02)
Tenant is resolved from request domain/subdomain before any handler runs. Unknown host => `404 tenant.unknown_host` (see errors taxonomy, TEN-02). No request executes without tenant context.

## Authentication (GW-03)
JWT (trader/staff) or console realm session verified on every protected route. Invalid credentials => `401 auth.invalid_credentials`. API keys are V2 (AUTH-21) — not in V1.

## Authorization (GW-04)
Module-declared `resource.action` permission keys enforced per route (AUTH-13). Denied => `403 permission.denied`. Key-to-route mapping lives in `contracts/permissions/registry.md`.

## Rate limiting (GW-05)
Per-IP and per-user limits with `429 rate.limited` responses. Redis-backed (self-hosted). Numeric limits and headers — TODO — needs owner decision.

## Idempotency (GW-12)
Clients MAY send an idempotency key on mutating requests. Retries never double-create orders, payouts, or accounts. Behavior on conflicting key reuse: `409 request.idempotency_conflict`. Key scope/TTL — TODO — needs owner decision.

## Error envelope (GW-18)
Every error response uses exactly this envelope (GW-18):

```json
{ "code": "TODO", "message": "TODO", "correlation_id": "TODO" }
```

- `code`: stable machine code (see `contracts/errors/taxonomy.md`)
- `message`: user-facing message pattern per taxonomy
- `correlation_id`: request correlation id, also recorded in audit entries (AUD-01)

Success envelopes and pagination conventions — TODO — needs owner decision.

## Standard errors (cited per GW rows)
- `tenant.unknown_host` 404 — domain does not resolve to a tenant # implied by GW-02, TEN-02
- `auth.invalid_credentials` 401 — missing/invalid token # implied by GW-03
- `permission.denied` 403 — role lacks the route's permission key # implied by GW-04, AUTH-13
- `rate.limited` 429 — per-IP/per-user limit exceeded # implied by GW-05
- `request.idempotency_conflict` 409 — idempotency key reused with a different request # implied by GW-12
- `tenant.suspended` 403 — tenant suspended (logins/orders/payouts stop) # implied by TEN-15 cascade
- `tenant.not_entitled` 403 — module disabled for tenant # implied by TEN-08; the sheet names no error row for this: TODO — needs owner decision on code naming and status

## Open contract questions
- TODO — needs owner decision: full URL plan per route group and module prefixes.
- TODO — needs owner decision: success envelope shape and pagination convention (cursor vs offset) for list endpoints.
- TODO — needs owner decision: rate-limit numbers, bucketing, and response headers.
- TODO — needs owner decision: idempotency key scope (per route? per tenant?) and retention window.
- TODO — needs owner decision: correlation id source (inbound header vs generated) and propagation into event payloads and audit entries.
- TODO — needs owner decision: error code for disabled-module access and where entitlements are checked (gateway middleware vs module).

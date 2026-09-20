# Gateway API Contract

Status: DRAFT
Owner: TBD
Version: v1
Last updated: 2026-09-20

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

Exact prefixes per module — resolved 2026-09-19 (D46, docs/54): the GW-01 groups ARE the plan; module paths normalize under them (docs/04 §7.2; reviewed modules' §7.2 already normalized).

## Tenant resolution (GW-02)
Tenant is resolved from request domain/subdomain before any handler runs. Unknown host => `404 tenant.unknown_host` (see errors taxonomy, TEN-02). No request executes without tenant context.

## Authentication (GW-03)
JWT (trader/staff) or console realm session verified on every protected route. Invalid credentials => `401 auth.invalid_credentials`. API keys are V2 (AUTH-21) — not in V1.

## Authorization (GW-04)
Module-declared `resource.action` permission keys enforced per route (AUTH-13). Denied => `403 permission.denied`. Key-to-route mapping lives in `contracts/permissions/registry.md`.

## Rate limiting (GW-05)
Per-IP and per-user limits with `429 rate.limited` + `Retry-After` (GW-29) responses. Redis-backed (self-hosted). Numbers (docs/04 §3.1 step 5): per-user 100 rpm default (tenant-plan adjustable), auth routes 10/5 min, payout routes 5/h; edge per-IP at Cloudflare.

## Idempotency (GW-12)
Clients MAY send an idempotency key on mutating requests. Retries never double-create orders, payouts, or accounts. Behavior on conflicting key reuse: `409 request.idempotency_conflict`. Scope/TTL (docs/04 §3.1 step 7): per (tenant, method, path, key), 24 h; body stored as hash only.

## Error envelope (GW-18)
Every error response uses exactly this envelope (GW-18):

```json
{ "code": "TODO", "message": "TODO", "correlation_id": "TODO" }
```

- `code`: stable machine code (see `contracts/errors/taxonomy.md`)
- `message`: user-facing message pattern per taxonomy
- `correlation_id`: request correlation id, also recorded in audit entries (AUD-01)

Success envelope — BINDING (D45, docs/54): `{data, meta{request_id, version, pagination{cursor, has_more}}}`; pagination is cursor-based (GW-21), `?limit≤100&cursor=`.

## Standard errors (cited per GW rows)
- `tenant.unknown_host` 404 — domain does not resolve to a tenant # implied by GW-02, TEN-02
- `auth.invalid_credentials` 401 — missing/invalid token # implied by GW-03
- `permission.denied` 403 — role lacks the route's permission key # implied by GW-04, AUTH-13
- `rate.limited` 429 — per-IP/per-user limit exceeded # implied by GW-05
- `request.idempotency_conflict` 409 — idempotency key reused with a different request # implied by GW-12
- `tenant.suspended` 403 — tenant suspended (logins/orders/payouts stop) # implied by TEN-15 cascade
- `tenant.not_entitled` 403 — module disabled for tenant # the V1 baseline code (taxonomy; checked at the GW-06 entitlement middleware)

## Open contract questions
- Resolved 2026-09-19 (D46, docs/54): the GW-01 groups are the URL plan; module paths normalize under them (docs/04 §3.1/§7.2).
- Resolved 2026-09-19 (D45, docs/54): `{data, meta{...}}` with cursor pagination.
- Resolved 2026-09-19 (docs/54): numbers per docs/04 §3.1 step 5 (100 rpm default user, auth 10/5 min, payout 5/h); headers: `Retry-After` (GW-29).
- Resolved 2026-09-19 (docs/54): scope = (tenant, method, path, key); TTL 24 h; body hash only.
- Resolved 2026-09-19 (docs/54): `X-Correlation-Id` inbound or a minted ULID (GW-09); propagated to the event envelope's required `correlation_id` (docs/49 C1) and `audit_events.correlation_id`; workers mint one per job.
- Resolved 2026-09-19 (docs/54): `tenant.not_entitled` 403, checked at the GW-06 entitlement middleware (step 6 of the chain), not per-module.

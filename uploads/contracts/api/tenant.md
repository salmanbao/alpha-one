# Tenant API Contract

Status: DRAFT
Owner: TBD
Version: v1
Last updated: TODO

Derived from the V1 Execution Sheet (V1.0 / V1.1). Nothing here is final until contract freeze.

## Scope
Tenant record CRUD with suspend/terminate, tenant resolution at the edge, tenant-scoped data access, per-tenant module entitlements, integration config with secret handling, storage scoping, subdomain availability/reservation. (TEN-01, TEN-02, TEN-03, TEN-08, TEN-11, TEN-12, TEN-15, TEN-18, TEN-42)

## Auth
Tenant admin operations run under the admin route group (GW-01) with Tenant Admin or Super Admin roles (AUTH-12). Subdomain availability is a super-admin console operation (TEN-42 story).

## Tenant resolution
The edge resolves tenant from domain/subdomain (TEN-02); gateway middleware rejects unknown hosts (GW-02, error `tenant.unknown_host`). This is the resolution contract every other module depends on.

## Permissions
`resource.action` keys per AUTH-13, cited per endpoint.

## Idempotency
Mutating requests accept an idempotency key per GW-12. Tenant create retries must not double-create.

## Endpoints

### POST /v1/tenants
Auth: Super Admin (console realm) — TEN-01
Tenant: platform scope (creates tenants; no tenant context yet)
Permission: `tenant.create` # AUTH-13, key derived from TEN-01
Idempotency: required # GW-12

Request:
```json
{ "name": "TODO", "subdomain": "TODO" }
```

Response 201:
```json
{ "tenant_id": "TODO", "subdomain": "TODO" }
```

Errors:
- `tenant.subdomain_taken` 409 — subdomain collision # implied by TEN-42
- `tenant.subdomain_reserved` 409 — reserved list: www, admin, api, console, app # implied by TEN-42

### GET /v1/tenants/{tenant_id}
Auth: Super Admin — TEN-01
Tenant: platform scope
Permission: `tenant.read` # derived from TEN-01 "view"
Idempotency: n/a

Response 200:
```json
{ "tenant_id": "TODO", "name": "TODO", "subdomain": "TODO", "status": "TODO", "entitlements": ["TODO"] }
```

Errors:
- `tenant.not_found` 404 # implied by TEN-01

### PATCH /v1/tenants/{tenant_id}
Auth: Super Admin — TEN-01
Tenant: platform scope
Permission: `tenant.update` # derived from TEN-01 "edit"
Idempotency: required # GW-12

Request:
```json
{ "name": "TODO" }
```

Response 200:
```json
{ "tenant_id": "TODO", "name": "TODO" }
```

Errors:
- `tenant.not_found` 404 # implied by TEN-01

### POST /v1/tenants/{tenant_id}/suspend
Auth: Super Admin — TEN-15
Tenant: platform scope
Permission: `tenant.suspend` # AUTH-13, key derived from TEN-15
Idempotency: required # GW-12

Request:
```json
{ "reason": "TODO" }
```

Response 200:
```json
{ "tenant_id": "TODO", "status": "suspended" }
```

Errors:
- `tenant.not_found` 404 # implied by TEN-15

Effects (per TEN-15): logins stop, new orders stop, payouts stop immediately; data preserved. Cascade mechanism (events vs synchronous calls) — TODO — needs owner decision.

### POST /v1/tenants/{tenant_id}/terminate
Auth: Super Admin — TEN-01
Tenant: platform scope
Permission: `tenant.terminate` # derived from TEN-01
Idempotency: required # GW-12

Request:
```json
{ "reason": "TODO" }
```

Response 200:
```json
{ "tenant_id": "TODO", "status": "terminated" }
```

Errors:
- `tenant.not_found` 404 # implied by TEN-01
- Downstream effects of terminate on live accounts/payments: TODO — needs owner decision

### GET /v1/tenants/subdomain-check
Auth: Super Admin — TEN-42
Tenant: platform scope
Permission: `tenant.create` (used during creation flow) # TEN-42
Idempotency: n/a

Query: `?subdomain=TODO`

Response 200:
```json
{ "available": true, "reserved": false }
```

Errors: none (availability is a boolean) # TEN-42

### PUT /v1/tenants/{tenant_id}/entitlements
Auth: Super Admin — TEN-08
Tenant: platform scope
Permission: `tenant.entitlement.change` # AUTH-13, key derived from TEN-08
Idempotency: required # GW-12

Request:
```json
{ "modules": { "CHK": true, "PAY": true, "RSK": false } }
```

Response 200:
```json
{ "tenant_id": "TODO", "modules": { "CHK": true, "PAY": true, "RSK": false } }
```

Errors:
- `tenant.not_found` 404 # implied by TEN-08
- `module.unknown` 400 — module key not a V1 module # implied by TEN-08; exact behavior TODO — needs owner decision

Effects: changes are manual and immediate (Out Of Scope sheet: no marketplace UI, no provisioning pipeline). Gateway enforcement point — TODO — needs owner decision (the sheet does not say where entitlements are checked per request; compare `module.not_entitled` naming).

### PUT /v1/tenants/{tenant_id}/integrations
Auth: Tenant Admin — TEN-11
Tenant: from domain (GW-02)
Permission: `tenant.integration.write` # AUTH-13, key derived from TEN-11
Idempotency: required # GW-12

Request:
```json
{ "broker": { "credentials": "TODO" }, "payments": { "keys": "TODO" }, "kyc": { "settings": "TODO" }, "email": { "sender_config": "TODO" } }
```

Response 200:
```json
{ "updated": true }
```

Errors:
- `tenant.not_found` 404 # implied by TEN-11

Secrecy: values are encrypted at rest (TEN-12); never returned in logs or API responses (TEN-12). GET returning masked values — TODO — needs owner decision (the sheet forbids returning secrets; the read-back UX is unspecified).

### GET /v1/tenants/{tenant_id}/integrations
Auth: Tenant Admin — TEN-11
Tenant: from domain (GW-02)
Permission: `tenant.integration.read` # derived from TEN-11 management need; read-back masking rules — TODO — needs owner decision
Idempotency: n/a

Response 200:
```json
{ "broker": { "configured": true }, "payments": { "configured": true }, "kyc": { "configured": true }, "email": { "configured": true } }
```

Errors:
- `tenant.not_found` 404 # implied by TEN-11

## Internal contracts (no HTTP)
- TEN-03 tenant-scoped repository access: every repository query is injected with the caller's tenant id. No HTTP surface.
- TEN-18 storage scoping: object storage keys are prefixed by tenant id (Cloudflare R2). Key format — TODO — needs owner decision (prefix pattern not specified beyond "tenant id prefix").

## Open contract questions
- TODO — needs owner decision: tenant list endpoint for console (TEN-01 says "create, view, edit, suspend, terminate" — pagination/filter contract unspecified).
- TODO — needs owner decision: what terminate does to running accounts, open payouts, stored data (TEN-01 does not define cascade).
- TODO — needs owner decision: entitlement change propagation latency and enforcement point (TEN-08 says immediate; mechanism unspecified).
- TODO — needs owner decision: whether tenant suspension also blocks the trader portal read-only or fully blocks all routes (TEN-15 names logins, orders, payouts).
- TODO — needs owner decision: integration config GET masking format (TEN-12 forbids returning secrets but the admin UI needs some read model).
- TODO — needs owner decision: custom domain support beyond subdomains (Out Of Scope says manual Cloudflare setup; API surface TBD).

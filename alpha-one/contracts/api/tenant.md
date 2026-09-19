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

Effects (per TEN-15): logins stop, new orders stop, payouts stop immediately; data preserved. Cascade mechanism (resolved by the docs/03 §5.1/§5.2 design): the state flip is transactional, the `tenant.suspended` event drives GW deny-set + session termination + notification fan-out, and the per-state capability matrix in §5.1 is the binding definition of what each surface does.

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
- Downstream effects of terminate: resolved 2026-09-19 — docs/03 §5.2 saga (settlement-only path for in-flight money, identities deactivated, financial/audit rows retained anonymised).

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

Secrecy: values are encrypted at rest (TEN-12); never returned in logs or API responses (TEN-12). Read-back: masked per docs/03 §3.7 (`••••1234` fingerprint + `configured: true`), decryption only inside the integration worker behind an audited accessor.

### GET /v1/tenants/{tenant_id}/integrations
Auth: Tenant Admin — TEN-11
Tenant: from domain (GW-02)
Permission: `tenant.integration.read` # derived from TEN-11 management need; masking rules in docs/03 §3.7
Idempotency: n/a

Response 200:
```json
{ "broker": { "configured": true }, "payments": { "configured": true }, "kyc": { "configured": true }, "email": { "configured": true } }
```

Errors:
- `tenant.not_found` 404 # implied by TEN-11

## Internal contracts (no HTTP)
- TEN-03 tenant-scoped repository access: every repository query is injected with the caller's tenant id. No HTTP surface.
- TEN-18 storage scoping: object storage keys are prefixed by tenant id (Cloudflare R2). Key format: `tenants/{tenant_id}/{kind}/{ulid}.{ext}` (matches the branding example in docs/03 §8); the prefix is asserted by a storage-layer guard on every write and by the RLS-equivalent test (docs/35 I-17 class).

## Identity side of a tenant (ADR-13, docs/03 §3.5/§3.8)
- The provisioning saga creates the ZITADEL organization and stores `tenants.idp_org_id`
  (+ `idp_org_domain = {slug}.alpha1.io`); the org carries the tenant's login policy,
  password policy, lockout policy, branding and (when contracted) its external IdP.
- Tenant users log in on `login.alpha1.io` scoped to their org in V1; the tenant's own
  domains serve the app/API only (docs/03 §3.8, decision D8).
- Suspension/deactivation cascade to the IdP: `tenant.suspended` kills the org's sessions
  (deny-set + ZITADEL session termination) and blocks new logins; termination deactivates
  every identity in the org (docs/03 §5.2).
- New permission keys for this surface: `platform.tenant.provision`, `tenant.sso.read`,
  `tenant.sso.configure`, `tenant.scim.manage`, `tenant.identity.read` (registry
  §Identity-management keys).

## Open contract questions
- Tenant list endpoint: the console surface `GET /v1/console/tenants` (docs/03 §7.2, extended) owns pagination/filtering; the V1 baseline exposes get-by-id only. Pagination follows the shared convention (`contracts/shared/openapi.yaml`).
- **Resolved 2026-09-19 (review G7):** termination is the saga in docs/03 §5.2 — traffic stops, export, identities deactivated in the IdP, R2 archived, PII anonymised, financial/audit rows retained, `deleted` tombstone at the end. Open payouts must settle first (settlement-only state in the §5.1 matrix).
- Entitlement propagation (resolved 2026-09-19): entitlements are cached per tenant (`t:{tenant}:entitlements`, TTL 5 min) and invalidated by `tenant.entitlement_changed`; enforcement is GW middleware step 6 (docs/04 §3, `tenant.not_entitled`). V1 is immediate because the write path invalidates the cache synchronously.
- **Resolved 2026-09-19 (review G7):** the state → capability matrix in docs/03 §5.1 is binding: `suspended` blocks login, traffic, API keys, webhooks and payouts; only the platform staff surface may act (reasons/audit), and settlement-only paths continue for in-flight money.
- **Resolved 2026-09-19 (review G13):** integration config GET returns per-field masks (`••••1234` of a fingerprint, plus `configured: true`) and never decrypts; decryption happens only in the integration worker behind an audited accessor (`tenant.integration.revealed`). Field-by-field inventory: docs/03 §3.7.
- **Resolved 2026-09-19 (review G8/G19):** subdomains are immutable in V1 (`{slug}.alpha1.io`, reserved list + normalisation rules in docs/03 §3.2); custom domains (TEN-05, V2) are added through CON with a Cloudflare DNS record and the same edge rewrite pattern — no vanity login host in V1 (decision D8).

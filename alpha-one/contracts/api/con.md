# Platform Console API Contract (CON)

Status: DRAFT
Owner: TBD
Version: v1
Last updated: 2026-09-20

Derived from the V1 Execution Sheet (V1.0 only). Nothing here is final until contract freeze.

## Scope
Console auth realm with mandatory 2FA (CON-01), console shell and navigation (CON-29 — frontend), console session management and security (CON-30). (CON-01, CON-29, CON-30)

## Auth
Separate console realm isolated from tenant identities (CON-01, AUTH-16). Super Admin role only (AUTH-12). Mandatory 2FA — TOTP per AUTH-09 pattern (SMS 2FA out of scope). Console routes are the `/v1/console/*` group (GW-01).

## Tenant resolution
Console is platform-scope: no tenant context by default. AUTH-16 is a separation contract only in V1: because no impersonation path exists in V1, the console cannot act inside a tenant at all (impersonation enablement — TEN-16, CON-07, AUD-08 — is V2.0; see `contracts/api/auth.md` "Impersonation (AUTH-16)").

## Permissions
- Console session actions: self-action
- Session revocation of another super admin: `console.session.revoke` # derived from CON-30 "can be revoked by another super admin"
- Impersonation: none in V1 — no impersonation API exists (AUTH-16 separation-only; enablement is V2). No key declared.

## Idempotency
Mutating requests accept an idempotency key per GW-12.

## Endpoints

### POST /v1/console/auth/login
Auth: none (public console login) — CON-01
Tenant: platform scope
Permission: none
Idempotency: optional

Request:
```json
{ "email": "TODO", "password": "TODO", "totp_code": "TODO" }
```

Response 200 (D45):
```json
{ "data": { "session_token": "<opaque>", "expires_at": 1758283020000 },
  "meta": { "request_id": "01J9ULID...", "version": "v1" } }
```

Errors:
- `auth.invalid_credentials` 401 (enumeration-resistant) # implied by AUTH-04 pattern
- `auth.totp_required` 401 — mandatory 2FA # implied by CON-01

### POST /v1/console/auth/logout
Auth: Super Admin console session — CON-01
Tenant: platform scope
Permission: self-action
Idempotency: optional

Response 200 (D45):
```json
{ "data": {}, "meta": { "request_id": "01J9ULID...", "version": "v1" } }
```

Errors: none

### POST /v1/console/sessions/{session_id}/revoke
Auth: Super Admin (a different one) — CON-30
Tenant: platform scope
Permission: `console.session.revoke` # CON-30
Idempotency: required # GW-12

Request:
```json
{ "reason": "TODO" }
```

Response 200 (D45):
```json
{ "data": { "session_id": "01J9SES...", "revoked": true },
  "meta": { "request_id": "01J9ULID...", "version": "v1" } }
```

Errors:
- `console.session_not_found` 404 # implied by CON-30
- `console.cannot_revoke_self` 400 — the V1 baseline rule (docs/21 §6.1: revoking your own session goes through the self-service session list, not the admin revoke endpoint).

### Session semantics (CON-30, no dedicated endpoints implied)
- Expires after inactivity — timeout value TODO — needs owner decision
- Requires re-authentication for sensitive actions — which actions count as sensitive — TODO — needs owner decision

## Frontend note
CON-29 (shell, navigation, layout, routing) is a frontend requirement with no API surface; it consumes the endpoints above plus tenant management (TEN-01 via `contracts/api/tenant.md`), entitlements (TEN-08), and console-visible features. No HTTP contract beyond session/auth in V1.

## Open contract questions
- RESOLVED 2026-09-17: impersonation API surface and audit format — none in V1 (AUTH-16 separation-only; enablement TEN-16/CON-07/AUD-08 is V2.0). See `contracts/api/auth.md`.
- TODO — needs owner decision: console inactivity timeout and step-up re-auth action list (CON-30).
- TODO — needs owner decision: what the console can see in V1 (the sheet ships shell + tenant management + entitlements; the full console feature list is not in V1 rows).

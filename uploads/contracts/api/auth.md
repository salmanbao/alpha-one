# Auth API Contract

Status: DRAFT
Owner: TBD
Version: v1
Last updated: 2026-09-17

Derived from the V1 Execution Sheet (V1.0 / V1.1). Nothing here is final until contract freeze.
Permission keys follow AUTH-13 (`resource.action`). Idempotency semantics cite GW-12.
Auth foundation: Better Auth (BVR-14); argon2id password hashing (AUTH-17).

## Scope
Trader registration, login, password reset and self-service change, token sessions with rotation and revocation, staff 2FA enrollment, role model, permission engine enforcement, tenant scoping, super admin separation, account suspension/unsuspension, logout. (AUTH-01, AUTH-04, AUTH-05, AUTH-07, AUTH-09, AUTH-12, AUTH-13, AUTH-15, AUTH-16, AUTH-17, AUTH-20, AUTH-39, AUTH-40, AUTH-43)

## Auth
Per-route groups (GW-01): trader routes use email+password login issuing short-lived JWT access tokens with rotating refresh tokens and server-side revocation (AUTH-07). Staff routes additionally require TOTP 2FA enrolled at first login (AUTH-09). API keys are V2 (AUTH-21) — not in this contract.

## Tenant resolution
Tenant comes from the request domain/subdomain resolved at the edge (TEN-02) and is enforced by gateway middleware (GW-02). Every query and action is restricted to the caller's tenant in the data layer (AUTH-15, TEN-03). Requests on unknown hosts are rejected before auth runs.

## Permissions
Enforced at the API layer by the AUTH-13 permission engine using module-declared `resource.action` keys (GW-04). Keys used by this module are listed in `contracts/permissions/registry.md`.

## Idempotency
Mutating requests accept an idempotency key per GW-12. Client retries on register/login MUST NOT create duplicate users or sessions.

## Endpoints

### POST /v1/auth/register
Auth: none (public; Trader role afterwards) — AUTH-01
Tenant: from domain (GW-02)
Permission: none — public registration on a tenant domain
Idempotency: required # GW-12 — retries never double-create a user

Request:
```json
{ "email": "TODO", "password": "TODO" }
```

Response 201:
```json
{ "user_id": "TODO", "tenant_id": "TODO" }
```

Errors:
- `auth.invalid_registration` 400 — payload fails validation # implied by AUTH-01 + AUTH-17
- `auth.email_taken` 409 — email already registered on this tenant # implied by AUTH-01; enumeration-safety treatment TODO — needs owner decision
- `tenant.suspended` 403 — registration on a suspended tenant # implied by TEN-15

### POST /v1/auth/login
Auth: none (public) — AUTH-04
Tenant: from domain (GW-02)
Permission: none — public login
Idempotency: optional # GW-12; login is not a create

Request:
```json
{ "email": "TODO", "password": "TODO", "totp_code": "TODO" }
```

Response 200:
```json
{ "access_token": "TODO", "refresh_token": "TODO", "expires_in": "TODO", "requires_2fa_enrollment": "TODO" }
```

Errors:
- `auth.invalid_credentials` 401 — identical message for unknown email and wrong password (enumeration-resistant) # implied by AUTH-04
- `auth.account_suspended` 403 — user suspended; all sessions/tokens already invalidated # implied by AUTH-20
- `auth.totp_required` 401 — staff login missing 2FA code # implied by AUTH-09
- `auth.totp_invalid` 401 — bad TOTP code # implied by AUTH-09
- `tenant.suspended` 403 — tenant suspended: logins stop # implied by TEN-15

### POST /v1/auth/password-reset
Auth: none (public) — AUTH-05
Tenant: from domain (GW-02)
Permission: none
Idempotency: optional

Request:
```json
{ "email": "TODO" }
```

Response 200: always success (no account enumeration).
```json
{}
```

Errors: none distinguishable (enumeration-resistant); delivery via NOT-03 Postmark. # AUTH-05

### POST /v1/auth/password-reset/confirm
Auth: none (single-use email link token) — AUTH-05
Tenant: from domain (GW-02)
Permission: none
Idempotency: required # GW-12 — single-use link token

Request:
```json
{ "token": "TODO", "new_password": "TODO" }
```

Response 200:
```json
{}
```

Errors:
- `auth.reset_token_invalid` 400 — unknown/expired/already-used single-use token # implied by AUTH-05

### POST /v1/auth/password
Auth: any logged-in user — AUTH-40
Tenant: from domain (GW-02)
Permission: self-action (no resource key; identity = caller) # AUTH-13 model
Idempotency: optional

Request:
```json
{ "current_password": "TODO", "new_password": "TODO" }
```

Response 200:
```json
{}
```

Errors:
- `auth.invalid_credentials` 401 — current password wrong # implied by AUTH-40
- `auth.weak_password` 400 — fails strength policy / argon2id hashing # implied by AUTH-17

### POST /v1/auth/2fa/enroll
Auth: Tenant Admin / Staff at first login — AUTH-09
Tenant: from domain (GW-02)
Permission: self-action
Idempotency: optional

Request:
```json
{}
```

Response 200:
```json
{ "totp_secret_uri": "TODO" }
```

Errors: TODO — needs owner decision (enrollment edge cases)

### POST /v1/auth/2fa/verify
Auth: Tenant Admin / Staff — AUTH-09
Tenant: from domain (GW-02)
Permission: self-action
Idempotency: optional

Request:
```json
{ "code": "TODO" }
```

Response 200:
```json
{ "enrolled": true }
```

Errors:
- `auth.totp_invalid` 400 — code mismatch # implied by AUTH-09

### POST /v1/auth/refresh
Auth: refresh token (rotating) — AUTH-07
Tenant: from domain (GW-02)
Permission: none
Idempotency: optional

Request:
```json
{ "refresh_token": "TODO" }
```

Response 200:
```json
{ "access_token": "TODO", "refresh_token": "TODO", "expires_in": "TODO" }
```

Errors:
- `auth.session_revoked` 401 — token revoked server-side or reused rotation token # implied by AUTH-07

### POST /v1/auth/logout
Auth: any user — AUTH-39
Tenant: from domain (GW-02)
Permission: self-action
Idempotency: optional

Request:
```json
{}
```

Response 200:
```json
{}
```

Errors: none # AUTH-39

### POST /v1/auth/users/{user_id}/suspend
Auth: Tenant Admin — AUTH-20
Tenant: from domain (GW-02)
Permission: `user.suspend` # AUTH-13, key from AUTH-20 story
Idempotency: required # GW-12

Request:
```json
{}
```

Response 200:
```json
{ "user_id": "TODO", "status": "suspended" }
```

Errors:
- `auth.user_not_found` 404 # implied by AUTH-20
- `auth.cannot_suspend_self` 400 — TODO — needs owner decision (self-suspension rule not in sheet)

### POST /v1/auth/users/{user_id}/unsuspend
Auth: Tenant Admin — AUTH-43
Tenant: from domain (GW-02)
Permission: `user.unsuspend` # AUTH-13, key from AUTH-43 story
Idempotency: required # GW-12

Request:
```json
{}
```

Response 200:
```json
{ "user_id": "TODO", "status": "active" }
```

Errors:
- `auth.user_not_found` 404 # implied by AUTH-43
- `auth.user_not_suspended` 409 # implied by AUTH-43 ("previously suspended")

### Role / permission management
AUTH-12 defines the role model (Super Admin, Tenant Admin, custom staff roles, Trader, API Consumer) and AUTH-13 the permission engine. CRUD endpoints for roles and role-permission bindings are implied but not specified: TODO — needs owner decision.

### Impersonation (AUTH-16)
**No impersonation API exists in V1.** AUTH-16 is a separation contract, not an enablement one: the console identity *cannot act inside a tenant except through* audited impersonation — and because no impersonation path exists in V1, the console simply cannot act inside a tenant at all. This contract documents that restriction; it defines no endpoint for it.

The enablement surface — impersonation consent + control UI (TEN-16, CON-07) and the impersonation audit record (AUD-08) — is V2.0 in the Master Backlog and out of V1 scope. The restriction holds vacuously in V1 and requires no audit format, consent model, or control UI. When V2 enablement lands, AUTH-16's contract will be amended; until then the console realm stays platform-scope (see `contracts/api/con.md`).

## Events emitted
- None directly in the sheet. Suspension cascades via TEN-15 are outbox events? TODO — needs owner decision (user suspension events not named in the sheet).

## Open contract questions
- TODO — needs owner decision: exact registration response shape and email-verification behavior (no verification row in V1 sheet).
- TODO — needs owner decision: enumeration-safe response for duplicate registration emails.
- TODO — needs owner decision: refresh-token rotation window and reuse-detection semantics (AUTH-07 says rotating + revocable but no parameters).
- TODO — needs owner decision: session concurrency limits per user.
- TODO — needs owner decision: CRUD surface for roles and role-permission bindings (AUTH-12/AUTH-13 imply management UI/APIs but no rows specify them).
- TODO — needs owner decision: JWT claims structure (tenant_id, role, permission set) — needed by every other module.
- TODO — needs owner decision: 2FA enrollment enforcement timing details ( grace period? forced at first login — what exactly?).
- TODO — needs owner decision: rate limits on auth endpoints (GW-05 is global; auth-specific limits unspecified).

# Auth API Contract

Status: DRAFT
Owner: TBD
Version: v1
Last updated: 2026-09-19

Derived from the V1 Execution Sheet (V1.0 / V1.1). Nothing here is final until contract freeze.
Permission keys follow AUTH-13 (`resource.action`). Idempotency semantics cite GW-12.
Auth foundation: **ZITADEL, self-hosted** (ADR-13, decision P1) — credentials, MFA factors, SSO/SAML and SCIM live there; this API verifies ZITADEL tokens (JWKS, audience per realm) and owns authorization. Authorization engine: **Casbin, embedded** (ADR-14, decision D4). Password hashing (AUTH-17) is ZITADEL's Argon2id.

## Scope
Trader registration, login, password reset and self-service change, token sessions with rotation and revocation, staff 2FA enrollment, role model, permission engine enforcement, tenant scoping, super admin separation, account suspension/unsuspension, logout. (AUTH-01, AUTH-04, AUTH-05, AUTH-07, AUTH-09, AUTH-12, AUTH-13, AUTH-15, AUTH-16, AUTH-17, AUTH-20, AUTH-39, AUTH-40, AUTH-43)

## Delegated to the identity provider (ZITADEL, ADR-13 / decision P2)
Registration, login, MFA challenge, password reset and token issuance/refresh are
**not** part of this API any more. The web tier redirects to ZITADEL Hosted Login v2
(tenant-scoped via `urn:zitadel:iam:org:id:{id}`), and token refresh/revocation use
ZITADEL's OIDC endpoints (`/oauth/v2/token`, `/oauth/v2/revoke`, `/oidc/v1/userinfo`,
`/oauth/v2/keys` for JWKS). Session listing/termination projects ZITADEL's session
service v2; SSO/SAML configuration projects the org IdP APIs; SCIM is served by
ZITADEL's `/scim/v2/Users` (user schema only). Consequences for this file: the
`POST /v1/auth/register`, `/login`, `/password-reset`, `/password-reset/confirm`,
`/2fa/enroll`, `/2fa/verify` and `/refresh` operations are **retired**; the V1
baseline below is what remains ours, plus `POST /v1/auth/session` and the backup-code
pair introduced by decisions D5/P2.

## Auth
Per-route groups (GW-01): every authenticated request carries a **ZITADEL access
token** (short-lived JWT) that the API verifies over JWKS with the audience of the
realm it belongs to (tenant application vs console application, AUTH-16). Immediate
revocation is ours: Redis deny-set + the `auth_sessions` projection, with reuse of a
rotated refresh token revoking all sessions of the identity (AUTH-07). Staff routes
additionally require an MFA assertion (`amr`) or a redeemed backup code (AUTH-09/11).
API keys are V2 (AUTH-21) — not in this contract.

## Tenant resolution
Tenant comes from the request domain/subdomain resolved at the edge (TEN-02) and is enforced by gateway middleware (GW-02). Every query and action is restricted to the caller's tenant in the data layer (AUTH-15, TEN-03). Requests on unknown hosts are rejected before auth runs.

## Permissions
Enforced at the API layer by the AUTH-13 permission engine using module-declared `resource.action` keys (GW-04). Keys used by this module are listed in `contracts/permissions/registry.md`.

## Idempotency
Mutating requests accept an idempotency key per GW-12. Client retries on register/login MUST NOT create duplicate users or sessions.

## Endpoints

### POST /v1/auth/session
Auth: ZITADEL access token (bearer, tenant audience) — AUTH-04/07
Tenant: from domain (GW-02)
Permission: none — materialises the identity + memberships on first login
Idempotency: required # GW-12 — repeated calls for the same token return the same session row

Request:
```json
{ "idp_session_id": "TODO" }
```

Response 200:
```json
{ "session_id": "TODO", "user_id": "TODO", "tenant_id": "TODO",
  "roles": ["user:trader"], "mfa_satisfied": false, "expires_at": "TODO" }
```

Errors:
- `auth.token_invalid` 401 — signature/issuer/audience/JWKS verification failed # AUTH-07
- `auth.account_suspended` 403 — user suspended in ZITADEL (deactivated) or locally # implied by AUTH-20
- `auth.tenant_suspended` 403 — tenant suspended: logins stop # implied by TEN-15
- `auth.mfa_required` 401 — staff role without an MFA assertion and no redeemed backup code # implied by AUTH-09/11

### POST /v1/auth/2fa/backup-codes
Auth: staff at first-login enrolment — AUTH-09/11 (V1 per decision D5)
Tenant: from domain (GW-02)
Permission: self-action
Idempotency: required

Request:
```json
{}
```

Response 201: plaintext codes shown once (10, single-use, Argon2id-hashed at rest).
```json
{ "codes": ["TODO"] }
```

Errors: `auth.mfa_not_enrolled` 409 — no verified factor to attach the codes to # AUTH-11

### POST /v1/auth/2fa/backup-code
Auth: staff without a working factor — AUTH-11
Tenant: from domain (GW-02)
Permission: self-action (sets `mfa_satisfied` on the caller's session)
Idempotency: required

Request:
```json
{ "code": "TODO" }
```

Response 200:
```json
{ "mfa_satisfied": true }
```

Errors: `auth.backup_code_invalid` 401 — unknown/used code # implied by AUTH-11

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

Revokes the caller's session in the projection + deny-set and calls ZITADEL's
session termination + OIDC end-session so the IdP-side session dies too.

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
- `user.login_success` / `user.login_failure` (emitted by `/v1/auth/session` and fed by ZITADEL Actions v2 event webhooks), `user.session_revoked` (logout/forced logout), `user.2fa_enrolled` / `user.2fa_disarmed`, `user.suspended` / `user.activated`, `api_key.created` / `api_key.revoked` — shapes in docs/31 (EVT catalog). ZITADEL's own events remain the IdP-side source of record and are mirrored into `audit_events` (AUD-01).

## Open contract questions
- Resolved by ADR-13 / decision P2: registration shape and email verification are ZITADEL's org-scoped registration flow; our `/session` response shape is the canonical identity payload (see above).
- Resolved by ADR-13: duplicate-registration / enumeration handling is ZITADEL's public error surface plus our generic `auth.token_invalid` on `/session`.
- Resolved by P2: refresh rotation + reuse detection are ZITADEL's token semantics plus our deny-set; parameters come from the ZITADEL application/session settings (tenant-configurable V2, AUTH-34).
- Still open (owner: BE-1): session concurrency limits per user.
- Still open (owner: BE-1): CRUD surface for roles and role-permission bindings — the Casbin policy table is the mechanism; the ADM screen is V2 (AUTH-14).
- Resolved by P4/ADR-14: token claims carry `sub`, audience/realm and MFA/`auth_time` facts; role/permission data is resolved by our API from `tenant_memberships` + Casbin, not from the token.
- Resolved by D5: staff 2FA is enforced at first login with backup codes issued in the same flow; no grace period for staff roles.
- Still open (owner: BE-1): auth-specific rate limits beyond ZITADEL's per-org login policy + GW-05.

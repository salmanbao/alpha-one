# 02 — AUTH: Identity, Authentication & Authorization

> Covers PRD module **AUTH** (43 requirements). Every section from the standard
> template is present. Requirements are cited as `AUTH-NN`.
>
> **Decided 2026-09-19 (ADR-13): ZITADEL is the identity provider.** Authentication,
> credential storage, MFA, SSO/SAML and SCIM are ZITADEL's; roles, membership,
> permissions and every AUTH lifecycle event stay ours. **ADR-14: Casbin (embedded)
> is the authorization engine.** Evidence and the decision trail:
> [41 — AUTH + TEN open-source evaluation](41-auth-ten-open-source-evaluation.md) §8/§10;
> open rows: none (D1–D5 and P1–P4 all answered in docs/37).

## 1. Purpose & scope

AUTH is the **identity layer of the entire platform**: who can log in, which tenant
they belong to, what role they hold in that tenant, and what they are allowed to do.
It serves four kinds of clients:

| Client | Method | Notes |
|---|---|---|
| Traders / tenant staff (web) | OIDC **login at ZITADEL Hosted Login v2**; the web tier keeps the tokens server-side (BFF) and calls the `api` with a bearer token | Tenant-scoped subdomain; login is org-scoped (`urn:zitadel:iam:org:id:{id}`) so branding/policies are the tenant's |
| Machine-to-machine (internal) | Service token (HMAC) | bridge → api, api → engine |
| Tenant integrators (external) | API key (V2: `DVP-11`/`AUTH-21`) | Tenant-scoped, hashed at rest — ours, not ZITADEL's |
| Platform staff (console) | OIDC login against the **console application** (distinct audience) | Structurally rejected by tenant routes: no tenant scopes, no membership, no impersonation in V1 (`AUTH-16`) |

**In scope (V1):** registration, login, sessions, 2FA (TOTP) for staff **with backup
codes**, password management, role/permission model, tenant membership, suspension,
API-key primitives, **SSO (SAML/OIDC) and SCIM for the tenant that needs it at cutover**
(`AUTH-24/25` promoted by design decisions D2/P3 — post-PRD scope, recorded in docs/37).
**Out of scope (V2+):** social login, email verification UX, staff invitations, step-up
authentication surface, IP allowlists, login history UX, passkeys (V3), trader-optional
2FA (`AUTH-10`, V2).

Requirement coverage: `AUTH-01,04,05,07,09,12,13,15,16,17,20,39,40,43` (V1.0) +
`AUTH-02,03,06,08,10,11,14,18,19,21,22,23,27,28,29,30,31,32,33,34,35,36,37,38,41,42` (V2.0) +
`AUTH-24,25,26` (V3.0).

## 2. Architecture

```
 browser ──(subdomain)──► Next.js (TD/ADM/CON)  ── OIDC redirect ──► ZITADEL
                             │  web-tier session (HttpOnly cookie, {tenant} scope)   Hosted Login v2
                             │  server-side tokens (BFF)                              (per-org branding,
                             ▼                                                        MFA, SSO, SAML, SCIM)
                    Go api — AUTH domain package                                     │
                       ├── authn: verify ZITADEL access token (JWKS, audience per     │
                       │          realm) → identity_id, tenant, role, amr, auth_time │
                       ├── authz: Casbin enforcer, embedded (RBAC with domains;       │
                       │          policies in DB, model file in repo)   [ADR-14]      │
                       ├── rate limit / lockout (Redis sliding window)                │
                       └── field encryption (broker passwords, backup codes,          │
                                  API-key material)                                   │
                             │                                                        │
                ┌────────────┼──────────────┬─────────────────────────────────────────┘
                ▼            ▼              ▼
             Postgres      Redis      ZITADEL Postgres (identities, credentials,
        identities,   deny-set,      MFA factors, sessions, orgs, SSO links)
        memberships,  lockouts,
        roles,        rate-limit
        auth_sessions
        (projection),
        api_keys, backup_codes
```

**ZITADEL mapping (ADR-13).** One self-hosted instance on the same box (ADR-9, Compose),
one **Organization per tenant** (`tenants.idp_org_id`), one **project + OIDC application**
for the tenant realm and a second application pair for the console realm. ZITADEL owns:
credentials (Argon2id), password policy per org, MFA factors (TOTP, WebAuthn), login
policy (lockout, session lifetimes), SSO/SAML connections per org, SCIM users, and the
event stream. We own: `identities` (our id ↔ `idp_user_id`), memberships, roles,
custom roles, the permission registry, API keys, backup codes, deny-set/revocation
projection, and every domain event.

- **Login is hosted, tokens are ZITADEL's (decision P2).** The web tier starts an
  Authorization Code + PKCE flow with `urn:zitadel:iam:org:id:{tenant_org}` so the
  tenant's branding, password policy and MFA settings apply, and keeps the resulting
  tokens server-side (HttpOnly, `{tenant}.alpha1.io`), handing the `api` a bearer
  access token. The `api` verifies signature/issuer/**audience** via JWKS and never
  stores a password. Token lifetimes are ZITADEL's; our contract is the
  rotation/revocation *semantics* (AUTH-07, §3.2).
- **Two realms = two audiences (AUTH-16).** Tenant traffic only accepts the tenant
  application's audience; console traffic only the console application's. A platform
  operator has no membership row and no tenant-audience token, so "console acts inside
  a tenant" is structurally impossible; V1 adds no impersonation.
- **Casbin is embedded (ADR-14).** `authorizer.Check(ctx, subject, action, resource)`
  is the only policy entry point; the model (`g(r.sub, p.sub, r.dom)`, domain =
  `tenant_id`) and the policy rows live with our code and schema, so an authz decision
  never leaves the process. Cerbos' policy tests are replaced by Go tests over the model
  + fixtures (§16 step 4).

- **ZITADEL, self-hosted (ADR-13)** replaces Better Auth (BVR-14) and the whole
  Node-identity-surface question: a single Go binary + Postgres in the Compose stack,
  one Organization per tenant, per-org login policy/branding/IdP, OIDC + SAML +
  SCIM. Authentication facts live there; authorization facts stay here (§2). The
  evaluation that produced this decision, including why Better Auth was retired
  (TypeScript-only, no Go SDK) and why Keycloak/authentik/Ory/Logto were rejected,
  is [docs/41](41-auth-ten-open-source-evaluation.md) §3–§4 and §10.
- **Casbin, embedded (ADR-14)** replaces Cerbos (BVR-23) as the policy decision
  point: `authorizer.Check(ctx, subject, action, resource)` is unchanged, but the
  enforcer runs in-process with the RBAC-with-domains model (`dom` = `tenant_id`),
  policies stored in Postgres and loaded at boot with a watch channel. An authz
  decision is a function call (sub-millisecond), there is no PDP to be unreachable,
  and policy review happens through Go tests + fixtures. Trade-off accepted: no
  Cerbos-style decision log/explainability, so the `api` logs every denial itself
  (AUD-23) with the matched policy row.

## 3. System design

### 3.1 Identity model

- **Identity** is platform-wide and tenant-independent (one person = one identity,
  possibly member of several tenants).
- **Tenant membership** binds identity ↔ tenant with a **role** (per tenant).
- Roles are hierarchical; permissions derive from roles + ABAC policy.

```
roles (hierarchy — child inherits parent):
  platform:super_admin ⊃ platform:admin ⊃ {platform:ops, platform:billing, platform:readonly}
  firm:owner ⊃ firm:admin ⊃ {firm:risk, firm:compliance, firm:support, firm:finance}
  user:trader            (funDED traders carry an attribute, not a new role, V1)
```

**V1 baseline permission model (AUTH-13, binding)** — `resource.action` keys:
keys are **module-declared** and **enforced at the API layer** (GW-04). The
V1 registry (30 keys, each with module owner + the Req ID that justifies it)
is `contracts/permissions/registry.md`. Rules from the research:

- **Trader self-actions** (registration, login, own account reads, checkout,
  own payout requests, own documents) are **identity-scoped**: the caller is
  the resource. Whether they additionally require declared keys is an open
  question (AUTH-13 requires declared keys; the sheet's stories are
  self-referential).
- **`tenant.impersonate`: no such key in V1.** AUTH-16 is a *separation*
  contract — the console identity cannot act inside a tenant at all because
  no impersonation path exists in V1. Enablement (TEN-16, CON-07, AUD-08) is
  V2.0 and would introduce the key with its audit format.
- **Role bindings** (which role gets which key) are not defined by any V1 row
  — open owner decision (AUTH-12 defines the roles: Super Admin, Tenant
  Admin, custom staff, Trader, API Consumer).
- Field-level permissions beyond route/action permissions are out of scope.

**Roles (AUTH-12)** and the extended (post-V1) permission catalog (design
level; the V1 key registry above is the binding subset):

| Role | Key permissions (extended catalog) |
|---|---|
| `firm:owner` | everything in-tenant incl. settings, team, billing view, audit |
| `firm:admin` | traders, challenges, payouts (approve), KYC, comms, reports |
| `firm:risk` | read all trades/accounts, risk queue, override (bounded by ABAC) |
| `firm:compliance` | KYC review/approve, audit export, data-subject requests |
| `firm:support` | tickets, read trader context (no payout/KYC decision) |
| `firm:finance` | orders, payouts process, refunds, reports |
| `user:trader` | own: accounts, trades, purchases, payouts request, KYC submit, profile |

ABAC policies (extended, beyond the V1 key model; evaluated in the embedded Casbin
model — role bindings are rows, attribute rules are the model's matchers plus a small
Go policy layer):
- **own-data only**: `trader.read` allowed iff `resource.user_id == subject.id`
  (and `resource.tenant_id == subject.tenant_id` — always checked first).
- **payout step-up**: `payout.approve` denied unless
  `subject.mfa_verified_at` within 5 min (V1: TOTP re-entry).
- **risk override bound**: `risk.override` for accounts > $500k requires
  `firm:owner` approval flag in context.
- **geo restriction**: funded-account actions denied when
  `context.geo.country ∈ tenant.config.restricted_countries`.
- **platform separation** (`AUTH-16`, V1 — binding): console routes are a
  separate realm; tenant roles never satisfy console policies and vice versa.
  **V1 has no impersonation path at all** (separation-only — see the V1
  baseline rules above); V2 enablement would add the impersonation policy +
  audit format (AUD-08). The realm is carried by the token **audience**
  (console app vs tenant app) and by `identities.realm`; Casbin policies are
  keyed per realm domain (`platform` vs the tenant id).

### 3.2 Authentication flows

**Registration / login (V1):** no password endpoint of ours exists any more — the web
tier redirects to ZITADEL Hosted Login v2 (register or sign in), org-scoped for tenant
traffic. ZITADEL returns the code; the web tier exchanges it (PKCE) and issues the `api`
a bearer access token. Our `POST /v1/auth/session` (new) *materialises* the session:
upsert `identities` by `idp_user_id`, resolve the tenant from the request domain and the
user's membership, write the `auth_sessions` projection row, emit `user.login_success`
(AUD/NOT/RSK). ZITADEL is the source of truth for *authentication* facts; our row is the
source of truth for *authorization* facts. **Enumeration resistance** (`AUTH-33`, V2) is
now ZITADEL's generic error surface plus ours on `/session`; throttling and lockout come
from ZITADEL's per-org lockout policy with our per-IP counters as the second layer.

**Sessions** (`AUTH-07`, `TD-20`): ZITADEL access tokens (short-lived, JWT) + rotating
refresh tokens; `api` keeps a **Redis deny-set** (jti/session-id, 24 h TTL) and the
`auth_sessions` projection so revocation is immediate. **V1 baseline survives
intact (binding):** rotating refresh, server-side revocation, and *reuse of a rotated
refresh token → revoke all sessions of the identity + CRITICAL audit* — reuse detection
is implemented by us (ZITADEL's `RevokeAllMyRefreshTokens` + session v2 `DeleteSession`
do the killing). Sliding idle 30 min / absolute 24 h are per-org ZITADEL session
lifetimes (tenant-configurable V2, `AUTH-34`). Trader lists/revokes sessions in TD via
`GET /v1/auth/sessions` and `DELETE /v1/auth/sessions/{id}` (both project ZITADEL's
session APIs).

**2FA** (`AUTH-09` staff-mandatory — V1 scope widened by decision D5: *all* staff roles,
enforced at first login, **backup codes included in V1**): TOTP (RFC 6238) enrolment and
verification happen in ZITADEL; the `api` **enforces** staff 2FA by requiring an MFA
assertion in the token (`amr` contains `otp`/`webauthn`, `auth_time` fresh for step-up)
for every staff-role action. Backup codes (`AUTH-11`) are ours: 10 single-use codes,
Argon2id-hashed, issued at first-login enrolment, redeemed at `/v1/auth/2fa/backup-code`;
exhaustion or reset routes through `AUTH-28` (admin-assisted reset, V1 dependency).
Trader-optional 2FA (`AUTH-10`) stays V2. Step-up (`AUTH-30`, V2) is a re-authentication
prompt (`prompt=login`/`max_age`) whose freshness we check from `auth_time`.

**Password policy** (per-org in ZITADEL, within platform bounds we set at provisioning):
min 10 / max 128, complexity, no reuse of last 5 (ZITADEL history), self-service change
(`AUTH-40`) requires the current password + (staff) 2FA. **HIBP breached-password check
stays ours** (ZITADEL does not call HIBP): registration and change flows pass the
candidate password through our range-API check before ZITADEL accepts it (Actions v2
`preuserinfo`/`preaccesstoken` hook or a pre-flight call from the web tier).

### 3.3 Tenant resolution (binding order)

1. **Custom domain** (`firm.com` → tenant) — V1 via CON-maintained mapping table +
   Cloudflare DNS; 2. **Subdomain** (`firm.alpha1.io`) → `tenants.slug`;
   3. **Internal** `X-Tenant-Id` header (service tokens only); 4. **API key** embeds
   tenant (key wins over any header). Unresolved → `404 tenant.not_found`
   (never 400 — avoids leaking which subdomains exist).

### 3.4 API keys (primitives V1, full UX V2 `AUTH-21`)

`sk_live_t_{tenant}_{random}` — only SHA-256 hash + 8-char prefix stored; scopes
(`trades:read`, `accounts:read`, `payouts:read`, ...); rate limit 600 req/min default;
optional expiry; last-used tracking; revocation immediate (hash delete + Redis
blocklist TTL 24 h).

## 4. Events

| Event | Producer | Consumers | Notes |
|---|---|---|---|
| `user.registered` | AUTH | NOT (welcome), AUD, ANA | identity + tenant + source |
| `user.login_success` / `user.login_failure` | AUTH | AUD, RSK (anomaly), NOT | failure carries attempt count, ip, ua |
| `user.suspended` / `user.activated` | AUTH (on `AUTH-20/43`) | NOT, GW (immediate session kill), AUD | suspension reason code |
| `user.role_changed` | AUTH | cache-invalidator (authz), AUD | old+new role |
| `user.session_revoked` | AUTH | (terminal) AUD | which session, by whom |
| `user.password_changed` | AUTH | session invalidator (all other sessions), AUD | — |
| `user.2fa_enrolled` / `user.2fa_disarmed` | AUTH | AUD (compliance), NOT | — |
| `api_key.created` / `api_key.revoked` | AUTH | AUD | never includes the key |
| `tenant.member_invited` / `tenant.member_joined` | AUTH (V2) | NOT, CON | — |

Event rules: all audit-relevant (every row in `audit_events` mirrors these with
before/after); `actor` = the human or `system:auth`.

## 5. Lifecycles

**Identity:** `pending_verification → active → suspended → banned | deactivated`.
Our `identities.status` is the authorization-side state; each transition is mirrored
to ZITADEL (`DeactivateUser` / `ReactivateUser` / session termination) so login is
blocked at the IdP as well as the API. Reasons: `risk`, `kyc_failed`,
`payment_dispute`, `platform_policy`, `manual`. Suspension kills all sessions
(Redis pub/sub → api instances evict) **and** calls ZITADEL session termination.
Deactivation (GDPR) is in [13-kyc-verification §7](13-kyc.md) (KYC-08/09) + this
doc's §10.4; **financial obligations block deletion** (open payout, unsettled
refund → hold in `deletion_pending` 30-day grace).

**Session:** `active → (idle>30m|abs>24h) expired | revoked`. Our `auth_sessions`
row is a projection of the ZITADEL session (id, jti, device, ip, amr, auth_time,
expiries) used for listing, revocation fan-out and audit. Reuse-detection: our
refresh exchange is single-use; a replay of a rotated token revokes **all** sessions
of that identity (`RevokeAllMyRefreshTokens` + mirror rows) + CRITICAL security alert.

**API key:** `active → expired | revoked`.

## 6. Error taxonomy
### 6.1 V1 baseline codes — authoritative

From `contracts/errors/taxonomy.md` (the V1 execution sheet; module AUTH). These are the exact codes the V1 surfaces return; the envelope is GW-18 (`code`, `message`, `correlation_id`).

> **Post-decision note (ADR-13 / P2):** the codes that belonged to the *login form*
> (`auth.totp_required`, `auth.totp_invalid`, `auth.invalid_credentials`,
> `auth.reset_token_invalid`, `auth.email_taken`, `auth.invalid_registration`) are now
> returned by ZITADEL's hosted-login surface, not by our API. They stay in the registry
> because tenant-facing copy and support runbooks reference them; our API's equivalents
> for the same situations are `auth.token_invalid`, `auth.mfa_required`,
> `auth.backup_code_invalid` and `auth.account_suspended` (§7.0).
| Code | HTTP | Meaning | User-facing message |
|---|---|---|---|
| `auth.invalid_registration` | 400 | Registration payload fails validation (incl. password policy) | "Please check your details and try again." |
| `auth.email_taken` | 409 | Email already registered on this tenant | "An account with this email already exists." |
| `auth.account_suspended` | 403 | User suspended; sessions and tokens already invalidated | "Your account has been suspended." |
| `auth.totp_required` | 401 | Staff login missing 2FA code | "Enter your two-factor code." |
| `auth.totp_invalid` | 401 | Wrong TOTP code | "That two-factor code is not valid." |
| `auth.reset_token_invalid` | 400 | Unknown/expired/used single-use reset link | "This reset link is no longer valid." |
| `auth.weak_password` | 400 | Password fails strength policy (argon2id hashing) | "Please choose a stronger password." |
| `auth.session_revoked` | 401 | Refresh token revoked or rotation reuse detected | "Your session has ended. Please log in again." |
| `auth.user_not_found` | 404 | Suspend/unsuspend target missing | "User not found." |
| `auth.user_not_suspended` | 409 | Unsuspend on a non-suspended user | "This user is not suspended." |
| `auth.cannot_suspend_self` | 400 | Admin suspending own account | "You cannot suspend your own account." |


Global contract: [30-error-taxonomy](30-error-taxonomy.md). Module codes (namespace `AUTH`):
### 6.2 Extended (post-V1) codes — design-level

> Below the V1 baseline (6.1); names in the GW-18 dotted convention. Rows duplicating a V1 baseline code were folded into the baseline table (the merged registry: docs/30).


| Code | HTTP | Meaning |
|---|---|---|
| `auth.invalid_credentials` | 401 | Wrong email/password (identical for unknown email, V2+) |
| `auth.mfa_required` | 401 | MFA challenge required (`mfa_token` returned) |
| `auth.mfa_invalid` | 401 | Bad/expired TOTP code |
| `auth.session_expired` | 401 | Session gone; client re-authenticates |
| `auth.account_locked` | 429 | Throttled; `Retry-After` set |
| `auth.password_policy_violation` | 422 | Which rule (enum list in `details`) |
| `auth.tenant_not_found` | 404 | Unresolvable subdomain/domain |
| `auth.tenant_suspended` | 403 | Tenant suspended — all its traffic |
| `authz.denied` | 403 | Policy denial; `details.policy` names the policy |
| `authz.step_up_required` | 403 | Sensitive action needs fresh 2FA |
| `auth.api_key_invalid` | 401 | Unknown/revoked/expired key |
| `auth.api_key_scope_missing` | 403 | Key lacks scope for route |
| `auth.email_already_exists` | 409 | Registration conflict |
| `auth.invitation_invalid` | 422 | Expired/used/revoked invite (V2) |

Logging rule: never log passwords, tokens, TOTP secrets, full API keys (prefix ok).

## 7. API endpoints
### 7.0 Delegated to ZITADEL (ADR-13 / decision P2)

These surfaces are **no longer ours**: credentials, MFA factors, SSO, sessions and
SCIM are served by ZITADEL. The paths below are ZITADEL's (written without the
HTTP-method prefix so the contract generator does not mistake them for our API):

| ZITADEL surface | Endpoint(s) | Replaces |
|---|---|---|
| Hosted Login v2 | `/ui/login` (+ org scope `urn:zitadel:iam:org:id:{id}` / `…:domain:primary:{domain}`) | `AUTH-01` registration, `AUTH-04` login, `AUTH-05` reset UX |
| OIDC endpoints | `/oauth/v2/authorize`, `/oauth/v2/token`, `/oauth/v2/revoke`, `/oauth/v2/introspect`, `/oidc/v1/userinfo`, `/oauth/v2/keys` (JWKS) | `AUTH-07` token issuance/rotation |
| Session service v2 | `/v2/sessions/{id}` (get/delete), `/v2/sessions` (list) | `AUTH-07/08/27` session list + termination |
| User service v2 | `/v2/users/{id}/password`, `/password_reset`, `/deactivate`, `/reactivate`, `/lock`, `/unlock`, `/v2/users/me/tokens/refresh/_revoke_all` | `AUTH-17/20/40/43`, forced logout |
| MFA / passkeys | `/v2/users/{id}/totp`, `/v2/users/me/auth_factors`, WebAuthn registration APIs | `AUTH-09/10/26` factors |
| SSO / SAML | `/v2/orgs/me/idps`, SAML metadata + ACS endpoints, `/v2/settings/login/idps` | `AUTH-24` federation (per-org IdP) |
| SCIM 2.0 | `/scim/v2/Users` (user schema only — no Groups) | `AUTH-25` provisioning |
| Actions v2 | targets + executions (`/v2/actions/…`), signed webhooks on `user.*`, `session.*` | `AUTH-19/22` login history + audit feed |

### 7.1 V1 baseline — `auth` (authoritative: `contracts/api/auth.md`)

| Method + path | Auth | Permission | Idempotency | V1 errors |
|---|---|---|---|---|
| `POST /v1/auth/session` | ZITADEL access token (bearer, tenant audience) — AUTH-04/07 | none — materialises the identity + memberships on first login | required | `auth.token_invalid`, `auth.account_suspended`, `auth.tenant_suspended`, `auth.mfa_required` |
| `POST /v1/auth/password` | any logged-in user — AUTH-40 | self-action (no resource key; identity = caller) # AUTH-13 model | optional | `auth.invalid_credentials`, `auth.weak_password` |
| `POST /v1/auth/2fa/backup-codes` | Staff at first-login enrolment — AUTH-09/11 (V1 per D5) | self-action | required | `auth.mfa_not_enrolled` |
| `POST /v1/auth/2fa/backup-code` | Staff without a working factor — AUTH-11 | self-action (sets the session's `mfa_satisfied`) | required | `auth.backup_code_invalid` |
| `POST /v1/auth/logout` | any user — AUTH-39 | self-action | optional | standard |
| `POST /v1/auth/users/{user_id}/suspend` | Tenant Admin — AUTH-20 | `user.suspend` # AUTH-13, key from AUTH-20 story | required | `auth.user_not_found`, `auth.cannot_suspend_self` |
| `POST /v1/auth/users/{user_id}/unsuspend` | Tenant Admin — AUTH-43 | `user.unsuspend` # AUTH-13, key from AUTH-43 story | required | `auth.user_not_found`, `auth.user_not_suspended` |

Scope, request/response shapes, and per-endpoint notes: `contracts/api/auth.md` (field values in the research are owner TODOs until contract freeze; canonical JSON is fixed at freeze, per the docs/99 §12 rules).

### 7.2 Extended (post-V1) surface — provisional

> Not in the V1 execution sheet. Design-level; paths beyond the V1 baseline are provisional until the URL-plan decision (`contracts/api/gw.md`, open question). Shown for platform completeness (V2/V3 phases, docs/99).

Public (pre-auth): *moved to ZITADEL* — registration, login, MFA challenge, password
forgot/reset and `/.well-known/openid-configuration` are the IdP's surfaces (§7.0);
our API exposes no pre-auth password endpoint any more. `GET /.well-known/openid-configuration`
is published by ZITADEL, and our `/.well-known/alpha1-config` (tenant resolution hints
for the web tier) is the only public config endpoint we host.

Authenticated (self): `POST /v1/auth/logout`, `POST /v1/auth/logout-all`,
`GET /v1/auth/sessions` (V2, `AUTH-08`; projects ZITADEL session v2 list),
`DELETE /v1/auth/sessions/{id}` (V2, `AUTH-08/27`; projects `DeleteSession`),
`PATCH /v1/auth/profile`, `POST /v1/auth/password` (change, V1 — above).
Factor management (TOTP/passkey enrolment, removal, MFA reset) is ZITADEL's
surface (§7.0); our V1 extra is the backup-code pair above, and listing codes is
deliberately impossible (they are shown once at issue).

Authenticated (staff, in-tenant): `GET|POST /v1/auth/members`,
`POST /v1/auth/members/invite` (V2), `PATCH /v1/auth/members/{id}/role`,
`POST /v1/auth/members/{id}/suspend` (`reason`, `note`),
`POST /v1/auth/members/{id}/activate` (`AUTH-43`),
`GET|POST /v1/auth/api-keys`, `DELETE /v1/auth/api-keys/{id}`.

Console (platform realm): `GET /v1/console/tenants/{id}/members`,
`POST /v1/console/impersonation` (`AUTH-16` separation + audit) — full listing in
`contracts/auth.openapi.yaml`.
## 8. Schema (key API shapes)

```jsonc
// POST /v1/auth/session → 200 (token verified; identity + membership materialised)
{ "data": { "session_id": "01J9...", "user": { "id": "01J9...", "idp_user_id": "28910...",
    "email": "trader@x.com", "display_name": "T. Rader", "roles": ["user:trader"],
    "mfa_satisfied": false, "tenant": { "id": "01J9...", "name": "FunderBlu",
    "slug": "funderblu" } }, "expires_at": 1758282000000 },
  "meta": { "request_id": "..." } }

// GET /v1/auth/sessions
{ "data": { "sessions": [ { "id": "01J9...", "device": "Chrome · macOS",
    "ip": "1.2.3.4", "country": "PK", "created_at": 1758278400000,
    "last_active_at": 1758279000000, "current": true } ] } }

// POST /v1/auth/members/invite (V2) → 202
{ "data": { "invitation_id": "01J9...", "email": "ops@firm.com",
    "role": "firm:support", "expires_at": 1758883200000 } }

// API key creation → 201 (plaintext shown ONCE)
{ "data": { "id": "01J9...", "name": "backfill-bot", "key": "sk_live_t_01J9..._AbC123...",
    "prefix": "sk_live_t", "scopes": ["trades:read","accounts:read"],
    "rate_limit_per_min": 600, "expires_at": null } }
```

## 9. Database design

```sql
-- platform-wide identity (no tenant_id by design)
CREATE TABLE identities (
  id            ULID PRIMARY KEY,
  idp_user_id   TEXT UNIQUE,                -- ZITADEL user id (sub); NULL until first login
  realm         TEXT NOT NULL DEFAULT 'tenant'
                CHECK (realm IN ('tenant','platform')),   -- AUTH-16 audience realm
  email         CITEXT UNIQUE NOT NULL,
  email_verified BOOLEAN NOT NULL DEFAULT false,
  phone         TEXT, phone_verified BOOLEAN NOT NULL DEFAULT false,
  password_hash TEXT,                       -- argon2id; NULL for social-only (V3)
  password_changed_at TIMESTAMPTZ,
  password_history JSONB NOT NULL DEFAULT '[]',   -- last 5 argon2id hashes
  first_name TEXT, last_name TEXT, display_name TEXT,
  date_of_birth DATE, nationality CHAR(3),
  status        TEXT NOT NULL DEFAULT 'pending_verification'
                CHECK (status IN ('pending_verification','active','suspended','banned','deactivated')),
  suspension_reason TEXT,
  mfa_enabled   BOOLEAN NOT NULL DEFAULT false,   -- mirror of ZITADEL factor state
  mfa_enrolled_at TIMESTAMPTZ,                    -- D5: staff 2FA enforced from first login
  -- TOTP secrets live in ZITADEL and are never stored here (§10.2)
  failed_logins INT NOT NULL DEFAULT 0,
  locked_until  TIMESTAMPTZ,
  last_login_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  deleted_at TIMESTAMPTZ                    -- GDPR soft-delete marker
);
CREATE INDEX idx_identities_status ON identities(status) WHERE status = 'suspended';

CREATE TABLE tenant_memberships (
  id          ULID PRIMARY KEY,
  identity_id ULID NOT NULL REFERENCES identities(id),
  tenant_id   ULID NOT NULL REFERENCES tenants(id),
  role        TEXT NOT NULL DEFAULT 'user:trader',
  status      TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','suspended','invited')),
  display_name_override TEXT,
  joined_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_active_at TIMESTAMPTZ,
  UNIQUE (identity_id, tenant_id)
);
CREATE INDEX idx_membership_tenant ON tenant_memberships(tenant_id, status);
CREATE INDEX idx_membership_identity ON tenant_memberships(identity_id);

-- projection of the ZITADEL session + our revocation state (P2)
CREATE TABLE auth_sessions (
  id            ULID PRIMARY KEY,
  identity_id   ULID NOT NULL REFERENCES identities(id),
  tenant_id     ULID REFERENCES tenants(id),        -- NULL for console sessions
  is_console    BOOLEAN NOT NULL DEFAULT false,     -- platform realm (AUTH-16)
  idp_session_id TEXT NOT NULL,                     -- ZITADEL session id
  idp_token_jti  TEXT,                              -- current access-token jti
  refresh_hash  TEXT UNIQUE,                        -- single-use, rotated (ours)
  prev_refresh_hash TEXT,                           -- for reuse detection
  amr           TEXT[] NOT NULL DEFAULT '{}',       -- otp/webauthn/pwd (AUTH-09)
  user_agent TEXT, ip INET, geo JSONB,
  mfa_verified_at TIMESTAMPTZ,                      -- step-up freshness (auth_time)
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  idle_expires_at TIMESTAMPTZ NOT NULL,
  abs_expires_at  TIMESTAMPTZ NOT NULL,
  revoked_at TIMESTAMPTZ, revocation_reason TEXT
);
CREATE INDEX idx_sessions_identity ON auth_sessions(identity_id, revoked_at);
CREATE INDEX idx_sessions_idp ON auth_sessions(idp_session_id);

-- backup codes are ours (AUTH-11, V1 per D5): 10 single-use, Argon2id-hashed
CREATE TABLE auth_backup_codes (
  id ULID PRIMARY KEY,
  identity_id ULID NOT NULL REFERENCES identities(id),
  code_hash TEXT NOT NULL,
  used_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_backup_codes_identity ON auth_backup_codes(identity_id) WHERE used_at IS NULL;

CREATE TABLE api_keys (
  id         ULID PRIMARY KEY,
  identity_id ULID NOT NULL REFERENCES identities(id),
  tenant_id  ULID NOT NULL REFERENCES tenants(id),
  name       TEXT NOT NULL,
  key_prefix TEXT NOT NULL,          -- 11 chars, display
  key_hash   TEXT NOT NULL UNIQUE,   -- sha256 of full key
  scopes     TEXT[] NOT NULL,
  rate_limit_per_min INT NOT NULL DEFAULT 600,
  expires_at TIMESTAMPTZ,
  last_used_at TIMESTAMPTZ, last_used_ip INET,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  revoked_at TIMESTAMPTZ
);
CREATE INDEX idx_apikeys_tenant ON api_keys(tenant_id) WHERE revoked_at IS NULL;
-- audit_events: see 05-ledger-audit (AUD-01 schema) — AUTH emits into it.
```

**Why PG sessions instead of Redis:** revocation is a correctness feature
(payout-adjacent accounts must be killable instantly across all instances); PG
survives a Redis flush. Redis holds only the hot deny-set (evicted session ids,
24 h TTL) for O(1) fast-path rejects.

## 10. Security & compliance

10.1 **Password hashing**: Argon2id (m=64 MB, t=3, p=4); per-user salt; rehash-on-login
when parameters change.
10.2 **Field encryption (envelope)**: TOTP secrets, (later) wallet/bank strings live
as AES-256-GCM with a **per-tenant DEK**; the DEK is wrapped by a **master key kept
outside the repo** (age key on the deploy host, written to a memory-only process
secret at boot; SOPS wraps only deployment-time values). Rotation: re-encrypt batch
job (V2). This is our SOPS/Vault replacement (ADR-3) applied to data fields.
10.3 **Cookies**: session cookie — HttpOnly, Secure, SameSite=Lax,
`Domain={tenant}.alpha1.io`, path `/`; refresh on `/v1/auth/*` only, SameSite=Strict.
10.4 **GDPR**: export (identity + per-tenant data bundle, 7-day signed link, audited),
erasure (30-day grace, obligations check, anonymize identity → retain financial
rows with `deleted_at`, R2 docs deleted). Owners: compliance role in tenant;
platform executes on request.
10.5 **Login anomaly scoring** (V2 `AUTH-18/19` feed): new device +30, >500 km
impossible travel +50, Tor/VPN IP +35, credential-stuffing pattern (≥5 emails/10 min
from one IP) +60, unusual hour +15; ≥70 → block + alert, ≥50 → force MFA.
10.6 **Headers** (all web apps): HSTS preload, CSP nonce-based, `frame-ancestors
'none'`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`.
10.7 **Audit**: every row in §4 is mirrored to `audit_events` with actor, IP, UA,
before/after JSON. Console impersonation = `security.impersonation` (CRITICAL tier).
10.8 **Compliance posture**: SOC 2 Type II target (Comp AI/Openlane, consider-later
register); PCI: AUTH stores **no** card data (SAQ-A support); KYC documents are
KYC module's storage, AUTH stores only status pointers.

## 11. Scalability considerations

| Surface | V1 design | Failure mode & fix |
|---|---|---|
| Login p99 | < 300 ms end-to-end (ZITADEL's Argon2id verify dominates; now in its process, not ours) | ZITADEL scales vertically on the same box; login bursts are capped at the Cloudflare edge |
| Session check (per request) | JWKS-verified JWT (cached keys) + Redis deny-set O(1) | JWKS fetch failure → cached keys (24 h) then fail closed; Redis down → fail-open to the `auth_sessions` row (degraded, alerted) |
| Authz | Casbin enforcer in-process, decisions < 1 ms, no network hop | none — the only failure mode is a bad policy, caught by the model tests in CI |
| Tenant resolution | 2-level cache (in-mem 30 s + Redis 5 min), 99%+ hit | cache flush storm → PG can absorb (keyed lookup, indexed) |
| Lockouts | Redis INCR/EXPIRE | Redis down → per-instance in-mem counters (weaker, alerted) |
| Scale headroom | 10k traders × 5 req/min = 830 req/min ≈ 14 req/s — 1 instance does 2k+ req/s | scale-out = add api replicas (stateless); session table needs only read replica (V2) |

## 12. Open-source solutions

> Decided 2026-09-19. Full scoring (every candidate, every constraint, sources):
> [41 — AUTH + TEN open-source evaluation](41-auth-ten-open-source-evaluation.md) §3–§4.

| Option | Verdict |
|---|---|
| **ZITADEL** (Go, AGPL-3.0, self-hosted, Postgres) | **CHOSEN — the identity provider (ADR-13, decision P1).** Organizations = tenants, per-org policies/branding/IdP, OIDC + SAML + SCIM (users) + passkeys, event-sourced audit stream, Actions v2 for token claims and audit webhooks, ~100–600 MB idle, no MAU limits self-hosted. Conditions: unmodified source (AGPL discipline), single instance, `tenants.idp_org_id` link, Oct-2026 legal review at Phase-0 exit |
| **Better Auth** (MIT, TS library) | **Superseded (BVR-14)** by ADR-13. Retired because it is TypeScript-only (no Go SDK → a second runtime for auth) and because V1 now needs SSO + SCIM, which its SSO plugin documents as not production-ready. Kept in docs as the fallback if the ZITADEL integration fails in Phase 0 |
| Keycloak (Apache-2.0, Java) | Rejected: 1–2 GB idle JVM, Organizations only since 26.0, SCIM still preview and not covering Organizations. **Kept as the documented escape hatch** if a tenant demands deep SAML/LDAP federation (ADR-13 fallback) |
| authentik (MIT core, Python) | Rejected: weaker hardening record than ZITADEL for fund-holding accounts; enterprise carve-out. No longer the V3 SSO plan — ZITADEL covers SSO from V1 |
| Ory Kratos/Hydra/Keto | Rejected: no OSS multi-tenancy (one instance per tenant), B2B orgs/SSO/SCIM are commercial, 3–4 components to run |
| Logto / Casdoor / Authelia / SuperTokens / FusionAuth | Rejected: Logto OSS has no multi-tenant console (Cloud-only), Casdoor has no advantage over ZITADEL, Authelia has no SAML/tenancy, SuperTokens' SAML needs a bridge and its enterprise bits are `ee/`-gated, FusionAuth is commercial |
| **Casbin** (Apache-2.0, embedded Go) | **CHOSEN — the authorization engine (ADR-14, decision D4).** RBAC with domains maps `role × tenant` directly, sub-millisecond in-process decisions, policies in Postgres, Go tests as the policy suite. Trade-off: no decision log — we log denials ourselves |
| Cerbos (Apache-2.0 PDP) | **Superseded (BVR-23)** by ADR-14. Rejected as *runtime* only: an extra process on a one-box deployment for gain we do not need at 50 tenants; its decision logs/query plans remain the reason it would be revisited if policy complexity grows (documented trigger: > 200 tenants or > 500 policy rows) |
| OPA / SpiceDB / OpenFGA | Rejected: OPA = steeper ops + no authz domain model; SpiceDB/OpenFGA = ReBAC overkill that adds a tuple store to keep in sync |
| Auth0 / Cognito | **Forbidden** (PRD/BVR-14): cost, tenant-RBAC mismatch |
| HIBP range API (breached passwords) | Standard, no key needed — **ours**, ZITADEL does not call it |
| Backup codes / API keys / trusted devices | Ours (ZITADEL has no recovery-code primitive; API keys are tenant-facing product surface) |
| SAML-only bridge (fallback) | Ory Polis (Apache-2.0, ex-BoxyHQ SAML Jackson) if ZITADEL's SAML ever proves insufficient — not needed for the V1 tenant |

## 13. Technology stack

Go (AUTH domain package in `api`), **ZITADEL** (Compose service, own Postgres
database, Hosted Login v2 + OIDC/SAML/SCIM), **Casbin** (Go library, embedded — no
service), Postgres, Redis (deny-set, rate limits, caches), Postmark (transactional
email: verify, reset, invite, security notice — ZITADEL notifications disabled for
these), Sentry, Flipt (rollout of 2FA mandate per tenant), Cloudflare (edge rate
limits + WAF for login routes).

**Service-count change (ADR-9):** one new Compose unit (`zitadel`) and one new
database in the same Postgres instance — no new box, no Kubernetes. Cerbos never
existed as a deployed unit (the fallback was in-process too), so ADR-14 removes a
service rather than adding one. Deployables are listed in docs/01 §5.

## 14. Integration — internal modules (glue)

| Module | How |
|---|---|
| **GW** (in-app) | AUTH is middleware steps 2–3: every request gets `(identity, tenant, role, permissions)` in context; `user.suspended` event → GW deny-set |
| **TEN** | membership reads `tenants` status; tenant suspension (`tenant.suspended`) kills sessions of all its members via event |
| **EVT** | producer of §4 events via outbox; consumer of `tenant.suspended`, `tenant.member_*` (mirror events) |
| **AUD** | every §4 event + all sensitive reads (e.g. staff viewing trader KYC) → `audit_events` |
| **NOT** | consumes `user.registered` (welcome), `user.login_failure` (security notice), `tenant.member_invited` |
| **RSK** | consumes `user.login_failure` streams for anomaly clustering (V2) |
| **LCC/PAY/KYC** | step-up policy gates their sensitive endpoints (payout approve, KYC approve) |
| **CON** | console realm auth (separate); tenant provisioning creates the org + owner membership (Flow D) |
| **web** | cookie scoping per subdomain; TD session page (`TD-20`) calls §7 endpoints |

## 15. Integration — external tools

**ZITADEL** (identity provider: hosted login, credentials, MFA factors, SSO/SAML,
SCIM, sessions, org policies; SMTP/notifications from ZITADEL disabled in favour of
ours unless a tenant's SSO requires IdP-sent mail), **Casbin** (embedded PDP),
Postmark (transactional email: verify, reset, invite, security notice), HIBP
(breached passwords — called by us), ipinfo (geo for sessions + anomaly; register
"NOW"), Sentry (CRITICAL security alerts), Flipt (rollout flags), Cloudflare (edge,
login routes, DNS for the IdP hostname). Device fingerprinting: ipinfo now,
FingerprintJS deferred (PRD default).

## 16. Implementation blueprint

> Re-planned 2026-09-19 for ADR-13/ADR-14 and decisions D1–D5/P1–P4. Estimates are
> person-days excluding OPS setup time.

| Step | Owner | Est | Depends | Exit criteria |
|---|---|---|---|---|
| 1. Deploy ZITADEL (Compose + own DB) and harden it: TLS host, SMTP off, backups in the ADR-10 ritual, AGPL legal review closed | BE-1 | 3 d | OPS env | `/debug/healthz` green; console reachable; login works for a scratch org |
| 2. Tenant provisioning hooks: create org + project/application, per-org password/lockout/session policies + branding defaults, write `tenants.idp_org_id` (idempotent, compensatable) | BE-1 | 3 d | 1, TEN step | re-running the saga step is a no-op; a second saga run never duplicates an org |
| 3. Token path: hosted-login hand-off from the web tier (PKCE, org scope), JWKS verification middleware (issuer + audience per realm), `POST /v1/auth/session`, `auth_sessions` projection + Redis deny-set, logout with `DeleteSession` + end-session | BE-1 | 5 d | 2 | TD + ADM login on a staging subdomain; a revoked session is refused < 1 s; console-audience token refused by tenant routes (AUTH-16) |
| 4. Authorization: Casbin model (`g(r.sub, p.sub, r.dom)`), policy table + loader/reload, role catalog, the `authorizer.Check` interface, denial logging | BE-1 | 4 d | 2 | fixture tests: trader can't read another's trades; ≥ 30 permission keys resolved by role; a policy change reloads without redeploy |
| 5. 2FA enforcement + backup codes: staff first-login enrolment flow (hosted), `amr`/`auth_time` rule in the API, `/v1/auth/2fa/backup-codes` + `/backup-code`, admin reset path (AUTH-28) | BE-2 | 4 d | 3 | staff login without a factor is refused by the API; backup code redeems once; reset flow audited |
| 6. Suspension/activation: status mirror to ZITADEL (deactivate/reactivate, session termination) + event fan-out + platform-realm separation test | BE-1 | 2 d | 3, 4 | suspended user's live session dies < 1 s; unsuspend restores with audit |
| 7. API-key primitives (create/revoke/hash/scopes) | BE-2 | 2 d | 3 | key works end-to-end against one read route |
| 8. RLS layer: policies + `FORCE ROW LEVEL SECURITY` + transaction-scoped `set_config` in the DB wrapper + negative tests (D3) | BE-1 | 3 d | 2 | isolation suite green under both layers; no-context query returns zero rows |
| 9. Audit + login history feed: Actions v2 event webhooks → `audit_events`, anomaly counters, security headers | BE-2 | 3 d | 5 | AUD-23 sensitive-access audit visible; login history rows appear |
| 10. SSO + SCIM for the cutover tenant (AUTH-24/25): org IdP config, metadata exchange, attribute→role mapping on our side, SCIM user provisioning token + deactivation path | BE-1 + BE-2 | 5 d | 3, 4 | the tenant's staff sign in through their IdP; SCIM create/deactivate lands as our membership rows |
| 11. V2: social login, step-up API surface, IP allowlists, session policy config, email-change + closure flows | BE-2 | 8 d | 10 | — |
| 12. V3: passkeys, duplicate-identity merge, trusted devices, advanced federation | BE-1 | 10 d | V2 base | — |

**Risks:** ZITADEL upgrade/migration ops (mitigation: pin the version, rehearse the
upgrade on staging, it shares the ADR-10 backup ritual); hosted-login UX divergence
from our design system (mitigation: per-org branding + the planned custom
`.well-known/alpha1-config` entry point, custom UI only if a tenant pays for it);
`amr`/`auth_time` claim shape (mitigation: spike in step 5 before enforcing);
AGPL interpretation (mitigation: unmodified upstream, Actions-only customisation,
legal review closed at step 1); identity-store drift (mitigation: nightly
reconciliation job + TEN-32 access review); SCIM user-only limitation (mitigation:
role assignment stays in ADM, documented in docs/41 §8.1).

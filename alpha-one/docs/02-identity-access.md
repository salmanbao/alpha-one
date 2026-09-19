# 02 — AUTH: Identity, Authentication & Authorization

> Covers PRD module **AUTH** (43 requirements). Every section from the standard
> template is present. Requirements are cited as `AUTH-NN`.

## 1. Purpose & scope

AUTH is the **identity layer of the entire platform**: who can log in, which tenant
they belong to, what role they hold in that tenant, and what they are allowed to do.
It serves four kinds of clients:

| Client | Method | Notes |
|---|---|---|
| Traders / tenant staff (web) | Session cookie (Better Auth) | Tenant-scoped subdomain |
| Machine-to-machine (internal) | Service token (HMAC) | bridge → api, api → engine |
| Tenant integrators (external) | API key (V2: `DVP-11`/`AUTH-21`) | Tenant-scoped, hashed at rest |
| Platform staff (console) | Session, separate **platform auth realm** | Never shares tenant sessions |

**In scope (V1):** registration, login, sessions, 2FA (TOTP) for staff, password
management, role/permission model, tenant membership, suspension, API-key primitives.
**Out of scope (V2+):** social login, email verification UX, staff invitations, step-up
authentication, IP allowlists, login history, SSO/SAML (V3), passkeys (V3).

Requirement coverage: `AUTH-01,04,05,07,09,12,13,15,16,17,20,39,40,43` (V1.0) +
`AUTH-02,03,06,08,10,11,14,18,19,21,22,23,27,28,29,30,31,32,33,34,35,36,37,38,41,42` (V2.0) +
`AUTH-24,25,26` (V3.0).

## 2. Architecture

```
 browser ──(subdomain)──► Next.js (TD/ADM/CON)
                             │  cookies: {tenant}.alpha1.io scope
                             ▼
                    Go api — AUTH domain package
                       ├── authn: Better Auth (Go client, session store in PG)
                       ├── authz: Cerbos PDP (policy files in repo, versioned)
                       ├── rate limit / lockout (Redis sliding window)
                       └── field encryption (broker passwords, TOTP secrets)
                             │
                ┌────────────┼─────────────┐
                ▼            ▼             ▼
             Postgres      Redis       Postmark (verification,
        identities,     sessions,   reset, invite emails)
        memberships,  lockouts,
        mfa, sessions, rate-limit
        api_keys
```

- **Better Auth** (PRD-mandated foundation, `AUTH-01..43`): we use its Go API
  surface — sessions, users, organizations (tenant = org), 2FA TOTP, password
  hashing (Argon2id). **Phase 0 spike (BE-1, 2 days):** confirm the org plugin
  supports per-org member roles; if it doesn't, we own the membership table and use
  Better Auth only for credential/session primitives. The rest of this doc is
  agnostic to that outcome — the domain package is the boundary.
- **Cerbos** (PRD-mandated PDP for `AUTH-13/14`): policies live in-repo
  (`infra/policies/`), versioned with the code; the `api` asks Cerbos per request
  and caches decisions per `(role, resource, action)` 60 s. If Phase 1 proves
  integration cost > 3 person-days, AUTH-13 becomes an in-house policy engine behind
  the same Go interface (`authorizer.Check(ctx, subject, action, resource)`).

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

ABAC policies (extended, beyond the V1 key model; Cerbos as candidate engine):
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
  audit format (AUD-08).

### 3.2 Authentication flows

**Login (V1):** `POST /v1/auth/login {email, password}` → Argon2id verify →
session created (PG) + cookie set (subdomain-scoped, HttpOnly, Secure, SameSite=Lax)
→ `user.login_success` audit + event. Failures: per-IP + per-identity counters
(Redis, 5-min window); 10 fails/5 min per identity → soft lock 15 min +
`user.login_throttled` event (unlock after wait, `AUTH-42` V2). **Enumeration
resistance** (`AUTH-33`, V2): identical error + constant-time path for unknown email.

**Sessions** (`AUTH-07`, `TD-20`): **V1 baseline (binding, `contracts/api/auth.md`):**
login issues a short-lived access token with a **rotating refresh token** and
**server-side revocation** (reuse of a rotated refresh token = revoke-all,
critical audit). Implementation: Better Auth (BVR-14) sessions in PG + Redis
deny-set — the contract is the rotation/revocation semantics; token format is
an implementation choice. Extended: device list, step-up state, sliding idle
30 min / absolute 24 h V1 default; tenant-configurable V2 `AUTH-34`. Trader can
list/revoke sessions from TD.

**2FA** (`AUTH-09` staff-mandatory, `AUTH-10` trader-optional V2): TOTP (RFC 6238),
secret field-encrypted; backup codes (10, hashed, single-use, `AUTH-11` V2).
Mandatory for: payout approval, tenant setting changes, API-key management,
suspension actions — enforced by the step-up policy (§3.1), not by client.

**Password policy** (tenant-overridable within platform bounds): min 10 / max 128,
breached-password check (Kibana/HaveIBeenPwned range API), no reuse of last 5,
self-service change (`AUTH-40`) requires current password + (staff) 2FA.

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
- Suspension reasons: `risk`, `kyc_failed`, `payment_dispute`, `platform_policy`,
  `manual`. Suspension kills all sessions (Redis pub/sub → api instances evict).
- Deactivation (GDPR) is in [13-kyc-verification §7](13-kyc.md)
  (KYC-08/09) + this doc's §10.4; **financial obligations block deletion**
  (open payout, unsettled refund → hold in `deletion_pending` 30-day grace).

**Session:** `active → (idle>30m|abs>24h) expired | revoked`. Reuse-detection:
refresh token is single-use; a replay of a rotated token revokes **all** sessions
of that identity + CRITICAL security alert (token-theft pattern).

**API key:** `active → expired | revoked`.

## 6. Error taxonomy
### 6.1 V1 baseline codes — authoritative

From `contracts/errors/taxonomy.md` (the V1 execution sheet; module AUTH). These are the exact codes the V1 surfaces return; the envelope is GW-18 (`code`, `message`, `correlation_id`).
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
### 7.1 V1 baseline — `auth` (authoritative: `contracts/api/auth.md`)

| Method + path | Auth | Permission | Idempotency | V1 errors |
|---|---|---|---|---|
| `POST /v1/auth/register` | none (public; Trader role afterwards) — AUTH-01 | none — public registration on a tenant domain | required | `auth.invalid_registration`, `auth.email_taken`, `tenant.suspended` |
| `POST /v1/auth/login` | none (public) — AUTH-04 | none — public login | optional | `auth.invalid_credentials`, `auth.account_suspended`, `auth.totp_required`, `auth.totp_invalid`, `tenant.suspended` |
| `POST /v1/auth/password-reset` | none (public) — AUTH-05 | none | optional | standard |
| `POST /v1/auth/password-reset/confirm` | none (single-use email link token) — AUTH-05 | none | required | `auth.reset_token_invalid` |
| `POST /v1/auth/password` | any logged-in user — AUTH-40 | self-action (no resource key; identity = caller) # AUTH-13 model | optional | `auth.invalid_credentials`, `auth.weak_password` |
| `POST /v1/auth/2fa/enroll` | Tenant Admin / Staff at first login — AUTH-09 | self-action | optional | standard |
| `POST /v1/auth/2fa/verify` | Tenant Admin / Staff — AUTH-09 | self-action | optional | `auth.totp_invalid` |
| `POST /v1/auth/refresh` | refresh token (rotating) — AUTH-07 | none | optional | `auth.session_revoked` |
| `POST /v1/auth/logout` | any user — AUTH-39 | self-action | optional | standard |
| `POST /v1/auth/users/{user_id}/suspend` | Tenant Admin — AUTH-20 | `user.suspend` # AUTH-13, key from AUTH-20 story | required | `auth.user_not_found`, `auth.cannot_suspend_self` |
| `POST /v1/auth/users/{user_id}/unsuspend` | Tenant Admin — AUTH-43 | `user.unsuspend` # AUTH-13, key from AUTH-43 story | required | `auth.user_not_found`, `auth.user_not_suspended` |

Scope, request/response shapes, and per-endpoint notes: `contracts/api/auth.md` (field values in the research are owner TODOs until contract freeze; canonical JSON is fixed at freeze, per the docs/99 §12 rules).

### 7.2 Extended (post-V1) surface — provisional

> Not in the V1 execution sheet. Design-level; paths beyond the V1 baseline are provisional until the URL-plan decision (`contracts/api/gw.md`, open question). Shown for platform completeness (V2/V3 phases, docs/99).

Public (pre-auth): `POST /v1/auth/register`, `POST /v1/auth/login`,
`POST /v1/auth/mfa/verify`, `POST /v1/auth/password/forgot`,
`POST /v1/auth/password/reset`, `GET /.well-known/openid-configuration` (V3 prep).

Authenticated (self): `POST /v1/auth/logout`, `POST /v1/auth/logout-all`,
`GET /v1/auth/sessions`, `DELETE /v1/auth/sessions/{id}`,
`PATCH /v1/auth/profile`, `POST /v1/auth/password/change`,
`POST /v1/auth/2fa/enroll`, `POST /v1/auth/2fa/confirm`, `DELETE /v1/auth/2fa`,
`GET /v1/auth/2fa/backup-codes` (V2).

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
// POST /v1/auth/login → 200
{ "data": { "session_id": "01J9...", "user": { "id": "01J9...", "email": "trader@x.com",
    "display_name": "T. Rader", "roles": ["user:trader"], "tenant": { "id": "01J9...",
    "name": "FunderBlu", "slug": "funderblu" } } } , "meta": { "request_id": "..." } }

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
  mfa_enabled   BOOLEAN NOT NULL DEFAULT false,
  mfa_totp_secret TEXT,                     -- AES-256-GCM field-encrypted (envelope, §10)
  mfa_backup_codes_hash JSONB,              -- V2
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

CREATE TABLE auth_sessions (
  id            ULID PRIMARY KEY,
  identity_id   ULID NOT NULL REFERENCES identities(id),
  tenant_id     ULID REFERENCES tenants(id),        -- NULL for console sessions
  is_console    BOOLEAN NOT NULL DEFAULT false,     -- platform realm (AUTH-16)
  refresh_hash  TEXT NOT NULL UNIQUE,               -- single-use, rotated
  prev_refresh_hash TEXT,                           -- for reuse detection
  user_agent TEXT, ip INET, geo JSONB,
  mfa_verified_at TIMESTAMPTZ,                      -- step-up freshness
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  idle_expires_at TIMESTAMPTZ NOT NULL,
  abs_expires_at  TIMESTAMPTZ NOT NULL,
  revoked_at TIMESTAMPTZ, revocation_reason TEXT,
  CHECK (NOT (revoked_at IS NOT NULL)) OR TRUE      -- keep history
);
CREATE INDEX idx_sessions_identity ON auth_sessions(identity_id, revoked_at);

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
| Login p99 | < 300 ms (Argon2id ~150 ms dominates) | CPU-bound: cap logins/IP at edge (Cloudflare); if needed, move Argon2 to a worker pool (V2) |
| Session check (per request) | Redis deny-set O(1); PG only on miss/refresh | Redis down → fail-open to PG check (degraded, alerted) |
| Authz | Cerbos in-proc decision cache 60 s per (role,action,resource); PDP local process | PDP down → deny (authz failures fail **closed**) |
| Tenant resolution | 2-level cache (in-mem 30 s + Redis 5 min), 99%+ hit | cache flush storm → PG can absorb (keyed lookup, indexed) |
| Lockouts | Redis INCR/EXPIRE | Redis down → per-instance in-mem counters (weaker, alerted) |
| Scale headroom | 10k traders × 5 req/min = 830 req/min ≈ 14 req/s — 1 instance does 2k+ req/s | scale-out = add api replicas (stateless); session table needs only read replica (V2) |

## 12. Open-source solutions

| Option | Verdict |
|---|---|
| **Better Auth** (TS library, orgs, sessions, 2FA, DB-agnostic) | **CHOSEN** (PRD). Used via its Go-compatible HTTP API or thin Node BFF path; confirm org plugin in Phase 0 spike |
| Keycloak / Authentik (IdP servers) | Rejected V1: Java ops weight, tenant-RBAC fit requires custom SPI; Authentik kept as **V3 SSO** option (register) |
| Logto / UnKey (register) | Rejected: same class as Keycloak, less tenant fit |
| **Cerbos** | **CHOSEN** PDP (PRD). Fallback: in-house policy engine, same interface |
| OPA / SpiceDB | OPA = more flexible, steeper ops; SpiceDB = ReBAC overkill for our role+ABAC needs |
| Auth0 / Cognito | **Forbidden** (PRD): cost, tenant-RBAC mismatch |
| Argon2 (password) | Standard library, all runtimes |
| TOTP: `pquerna/otp` (Go) | Standard |
| Breached passwords: HIBP range API | Standard, no key needed for range API |

## 13. Technology stack

Go (domain package in `api`), Better Auth (Go client or Node BFF path), Cerbos
(self-hosted Compose service, policies in `infra/policies/`), Postgres, Redis,
Postmark (emails), Sentry (auth-failure alerts), Flipt (feature-flag-gated rollout of
2FA mandate per tenant), Cloudflare (edge rate limits + WAF for login routes).

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

Better Auth (foundation), Cerbos (PDP), Postmark (transactional email: verify,
reset, invite, security notice), HIBP (breached passwords), ipinfo (geo for
sessions + anomaly; register "NOW"), Sentry (CRITICAL security alerts),
Flipt (rollout flags), Cloudflare (edge). Device fingerprinting: ipinfo now,
FingerprintJS deferred (PRD default).

## 16. Implementation blueprint

| Step | Owner | Est | Depends | Exit criteria |
|---|---|---|---|---|
| 1. Phase-0 spike: Better Auth org plugin fit; Cerbos hello-policy | BE-1 | 2 d | OPS env | Written ADR: org plugin or own membership |
| 2. Schemas + guard: identities, memberships, sessions, api_keys; isolation test passes | BE-1 | 2 d | 1 | `isolation.test` green for AUTH |
| 3. Authn: register/login/logout, sessions, cookies, lockout, password policy | BE-1 | 5 d | 2 | TD login works on staging subdomain |
| 4. Authz: Cerbos service + role catalog + own-data/step-up policies; `authorizer` interface | BE-1 | 4 d | 2 | policy tests: trader can't read other's trades; payout w/o MFA denied |
| 5. 2FA TOTP enroll/confirm + step-up enforcement | BE-2 | 3 d | 3,4 | staff login requires TOTP on staging |
| 6. Suspension/activation + session kill pub/sub; platform-realm separation | BE-1 | 2 d | 4 | suspended user's live session dies < 1 s |
| 7. API-key primitives (create/revoke/hash/scopes) | BE-2 | 2 d | 3 | key works end-to-end against one read route |
| 8. Audit wiring + security headers + anomaly counters (V2 hooks) | BE-2 | 2 d | 5 | AUD-23 sensitive-access audit visible |
| 9. V1.1: email verification UX, staff invites, login history, 2FA backup codes | FE-1 + BE-2 | 5 d | 8 | AUTH V1.1 req list green |
| 10. V2: social login, step-up API surface, IP allowlists, session policy config | BE-2 | 8 d | 9 | — |
| 11. V3: SAML SSO (Authentik or direct), SCIM, passkeys | BE-1 | 10 d | V2 base | — |

**Risks:** Better Auth org plugin mismatch (mitigation: spike first, fallback
designed in step 1); Cerbos latency (mitigation: decision cache + local PDP);
cookie subdomain complexity in testing (mitigation: staging uses `*.staging.alpha1.io`).

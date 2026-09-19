# 42 — AUTH + TEN Deep Review: Gap Analysis

> Second-pass review of the identity (`AUTH`) and tenant (`TEN`) modules, 2026-09-19,
> after the ADR-13/ADR-14 decisions. Method: every one of the **88 PRD rows**
> (43 AUTH + 45 TEN) checked against `docs/02`, `docs/03`, the contracts pack
> (`api/*.md`, `*.openapi.yaml`, `permissions/`, `events/`, `data/`), and the
> cross-cutting docs (01, 06, 25, 28, 29, 31, 32, 34, 35, 99) — plus a
> fresh-source check of the chosen stack (ZITADEL) against the design we wrote.
>
> Status legend: **FIXED** (closed in this pass) · **OPEN** (needs a decision or a
> later phase) · **ACCEPTED** (deliberate, documented risk).
>
> Requirement coverage: cross-cutting (review artifact for `AUTH-*` + `TEN-*`).

## 1. Summary

| # | Finding | Severity | Status |
|---|---|---|---|
| G1 | Multi-tenant identity model conflicts with ZITADEL's user→organization ownership; the `urn:zitadel:iam:org:id:` scope rejects users whose home org differs (upstream regression, issue #11869) | **High** | FIXED (documented model + spike gate) — see §3.1 |
| G2 | Staff-only MFA enforcement cannot be configured in ZITADEL (org-level `force_mfa` only, user-level is an open upstream issue #6316) — the enrolment path was unspecified | **High** | FIXED — §3.2, mechanism + API path documented |
| G3 | HIBP breached-password check is **not enforceable** on flows that ZITADEL owns (hosted login / password reset) | **Medium** | FIXED (documented deviation + options) — §3.3 |
| G4 | ZITADEL's event store retains PII indefinitely; retention/de-identification is an unimplemented upstream request (#7811) → our GDPR erasure claim was too strong | **High** | FIXED (two-store deletion model + accepted risk) — §3.4 |
| G5 | V1 AUTH/TEN **events** were absent from the V1 event catalog and had no payload schemas (consumers GW/NOT/AUD/ANA depend on them) | **High** | FIXED — §4.1 (catalog + 12 payloads) |
| G6 | `docs/32` + `contracts/data/schemas/02-auth.sql` / `03-ten.sql` were **stale** (no `idp_user_id`, `realm`, `idp_org_id`, backup codes; RLS absent) | **High** | FIXED — §4.2 |
| G7 | Tenant lifecycle had no **state→capability enforcement matrix** (what exactly stops at `onboarding`, `suspended`, `deactivated`, `pending_deletion`) and no complete **termination/deletion** semantics | **High** | FIXED — §5.1/§5.2 |
| G8 | Tenant **subdomain rules, reserved list, normalisation and immutability** were referenced but never specified (TEN-42 is a V1 row) | **Medium** | FIXED — §5.3 |
| G9 | Migration: password hashes **can** be imported into ZITADEL (verifier config) — the doc asserted "reset-required" by default without the option | **Medium** | FIXED — §6.1 |
| G10 | No operational doc for the new identity service: secrets/keys inventory, backup+restore of the second database, upgrade/pin policy, outage behaviour, IdP metrics/SLOs | **High** | FIXED (02 §3.7 + 06/28/29/34) — §3.5–§3.7 |
| G11 | Platform-staff identity provisioning (console realm) — creation, offboarding, break-glass, MFA mandate — was undefined | **Medium** | FIXED — §3.8 |
| G12 | Token/session parameters (access TTL, refresh rotation window, JWKS cache/rotation, clock skew, concurrency limits) were still "TODO — owner decision" | **Medium** | FIXED (defaults documented, one row still open) — §3.9 |
| G13 | Tenant integration secrets: no inventory of *which* fields are secret, masking rules, rotation or read-audit | **Medium** | FIXED — §5.4 |
| G14 | No per-module test plan for the new stack (token verification matrix, realm separation, RLS negatives, IdP outage drill, upgrade rehearsal) | **Medium** | FIXED — §6.3 |
| G15 | Several AUTH rows (V2/V3) are named in the coverage line but have **no design text** anywhere (AUTH-31/32/35/36/37/38 …) | **Medium** | PARTIAL — §7 lists them; V1 unaffected, V2 design deferred by design |
| G16 | Permission registry lacks the identity-management keys the new model needs (`tenant.identity.*`, `tenant.sso.*`, `tenant.scim.*`, `platform.identity.*`) | **Medium** | FIXED — §4.3 (provisional keys added) |
| G17 | `docs/02 §7` V1 surface has no endpoint for **staff MFA status** / enrolment start, which the enforcement flow needs | **Low** | FIXED — §3.2 |
| G18 | No runbook for IdP incidents (compromise, key rotation, mass session revocation, IdP down at login) | **Medium** | FIXED — §3.6 |
| G19 | Tenant `custom domain` (TEN-05) and **login hostname** design (tenant login on the tenant's own domain vs IdP host) was unresolved | **Medium** | FIXED (v1 posture + V2 plan) — §5.5 |
| G20 | `docs/13` (KYC) and AUTH share identity data (name, DOB, nationality); the split of which store holds what after ADR-13 was unwritten | **Low** | FIXED — §3.4 |

## 2. What was already complete (no action)

- All 23 V1.0/V1.1 rows had a design, an endpoint or an explicit delegation note.
- Endpoint tables, error registries, schema sketches, security and scalability
  sections exist for both modules; nothing in the V1 set was missing at the
  *section* level (the standard 16-section template is complete in both).
- The permissions registry (30 V1 keys) covers the V1 module surface; the gap was
  identity-management keys (G16), not the business keys.

## 3. Identity provider model and operations (docs/02)

### 3.1 Multi-tenant identity ↔ ZITADEL organizations (G1)

ZITADEL owns users per **organization**; a person is a member of exactly one org
(the resource owner). Cross-tenant membership is expressed as **user grants** — a
role on another org's project. Verified 2026-09-19: the `urn:zitadel:iam:org:id:{id}`
scope currently accepts only users whose resource owner matches the requested org
(upstream issue **#11869**, regression since v4.12.3, breaks the documented B2B
pattern), and username uniqueness is per instance unless the org-domain suffix is
enabled.

Documented model (docs/02 §3.1):

| Case | How it works |
|---|---|
| Trader registers on a tenant's subdomain (the 99% case) | Registered **in that tenant's org** — resource owner = tenant org, so org-scoped hosted login works and the tenant's branding/policies apply |
| Same email at a second tenant (multi-firm trader, agency staff) | Second **ZITADEL user in the second org**; our `identities` row is keyed by a platform-level `identity_key` (normalised email hash) so the two IdP users map to **one** logical identity with two memberships. Login is per-org; the org-scoped scope always resolves because the user exists in the requested org |
| Staff of tenant A also granted access in tenant B | Home org = A. The token may carry the grant claim; **login stays in the home org** (org scoping is used for branding only when the user's home org matches), and our API resolves the *active tenant* from the request domain + membership, not from the token's org claim |
| Platform staff | Their own org (`alpha1-platform`), console application, no tenant memberships |

The Phase-0 spike must verify the org-scope behaviour on the pinned version and
record the outcome; the design above does not depend on the upstream fix.

### 3.2 Staff-only MFA (G2, G17)

ZITADEL enforces MFA only at **org or instance level** (`force_mfa`,
`force_mfa_local_only`, `mfa_init_skip_lifetime`); per-user/per-role enforcement is
an open upstream request (#6316). Trade-off: forcing MFA on the tenant org would
force it on traders too, which the PRD schedules for V2 (`AUTH-10`) — so:

1. **Enrolment (V1):** the tenant-app front-end calls the ZITADEL User v2 API
   (`POST /v2/users/{id}/totp` etc.) **with the user's own access token** (an admin
   token does not attach the factor to the user's session), then re-authenticates
   so hosted login shows the pending factor. Our `GET /v1/auth/mfa/status` and
   `POST /v1/auth/mfa/enrollment` (new, V1) wrap that with the staff-role check and
   the audit event.
2. **Enforcement (V1):** the API refuses any staff-role action whose token has no
   MFA assertion (`amr`) — the token is the gatekeeper, not the IdP.
3. **Backup codes (V1, decision D5):** ours, issued at enrolment, redeemable at
   `/v1/auth/2fa/backup-code`.
4. **Trader-optional MFA (V2):** same enrolment API, gated by a tenant setting.

### 3.3 Breached-password check (G3)

ZITADEL owns password set/reset and has no HIBP hook and no pre-password-change
action trigger, so the PRD's breached-password rule (`AUTH-17`) **cannot be
enforced on hosted-login flows**. Options are recorded in docs/02 §10.1, with the
V1 posture: (a) keep ZITADEL's complexity/history policy as the enforced bar, (b)
add a *detection* job — on password change we cannot read the plaintext, so
instead we call HIBP from our own "change password" UI path (which we keep for
authenticated users) and from registration when it happens through our form, and
(c) document the residual deviation from the PRD row with the owner (Tech Lead,
Phase 0). A full fix would require a custom login UI (rejected for V1).

### 3.4 Erasure across two stores (G4, G20)

`DELETE /v2/users/{id}` removes the IdP-side user and revokes sessions, but
ZITADEL is event-sourced and **does not de-identify events** (upstream #7811).
Documented model (docs/02 §10.4): erasure = (1) our Postgres hard-deletes PII and
keeps the anonymised financial/audit rows, (2) ZITADEL deletes the user, (3) the
residual event entries are **accepted as a documented limitation** — mitigated by
(a) not storing more PII in the IdP than email + display name, (b) keeping the
KYC/identity profile in our store, (c) a legal-review item for the DPO at Phase 0,
(d) tracking #7811 for a future retention setting. Same rule for the tenant's own
termination (docs/03 §5.2).

### 3.5 Secrets and keys inventory (G10)

Every ZITADEL-related secret now has an owner, a SOPS entry and a rotation
interval in docs/02 §3.7 + docs/28 §5: postgres DSN, master key
(`ZITADEL_MASTERKEY`), console/tenant OIDC client secrets, the provisioning
machine-user key (JWT/PAT), SCIM bearer tokens per tenant, Actions v2 signing
keys, and SMTP credentials (disabled unless a tenant needs IdP-sent mail).

### 3.6 Operational posture (G10, G18)

- **Backup:** the ZITADEL database rides the ADR-10 ritual (nightly base backup +
  WAL, monthly restore drill covering *both* databases, integrity checks include
  `auth.users`-equivalent counts and `identities` join integrity).
- **Upgrade policy:** pin the ZITADEL version; upgrades are rehearsed on staging
  against a restored prod dump; event-sourced migrations are one-way, so the
  rollback plan is "restore the pre-upgrade dump", never "downgrade the binary".
- **Outage behaviour:** existing access tokens keep validating (JWKS cached, 24 h);
  **logins are unavailable** — the runbook says: post a status notice, keep the
  API serving, do not restart the box blindly (the IdP shares Postgres with the
  platform), and if the outage is a ZITADEL upgrade failure, restore the dump.
- **Incident runbooks added:** IdP compromise (rotate master key + client secrets,
  revoke all sessions, invalidate JWKS cache, force re-auth), mass revocation,
  SCIM token leak, and Actions v2 target signing-key compromise.
- **Observability:** metrics and SLOs in docs/02 §11 (login success rate, token
  verification failures, JWKS fetch failures, provisioning-saga failures, login
  p95), each with an alert threshold; the CON health screen gets the IdP rows.

### 3.7 Platform-staff realm operations (G11)

Documented in docs/02 §3.1 + docs/21: staff identities are created by an existing
platform admin (no self-registration), the org is `alpha1-platform`, MFA is
mandatory for every member of the console application, offboarding deactivates the
IdP user **and** revokes sessions, and break-glass is a sealed credential pair held
by the CTO/COO with a documented activation + post-incident rotation.

### 3.8 Token and session parameters (G12)

Documented defaults (docs/02 §3.2): access token 15 min, refresh rotation on every
use with a 30-day absolute lifetime, idle 30 min, JWT clock skew ±60 s, JWKS cached
24 h with a 5-min refresh on `kid` miss, deny-set TTL = token TTL. Still open:
**per-identity concurrent session limit** (owner BE-1) — one row in
docs/37 §Design-review (D6).

## 4. Contracts pack

### 4.1 Events (G5) — FIXED

`contracts/events/catalog.md` gained the V1 identity/tenant section and
`contracts/events/payloads/` gained the schemas: `user.registered`,
`user.login_success`, `user.login_failure`, `user.suspended`, `user.activated`,
`user.role_changed`, `user.session_revoked`, `user.password_changed`,
`tenant.created`, `tenant.suspended`, `tenant.reactivated`,
`tenant.member_invited`. docs/31 marks them V1 tier.

### 4.2 Schemas (G6) — FIXED

`docs/32` §02/§03 and the generated `contracts/data/schemas/02-auth.sql` /
`03-ten.sql` were regenerated from the updated `docs/02 §9` and `docs/03 §9`:
`identities.idp_user_id/realm/identity_key`, `auth_sessions.idp_*` + `amr`,
`auth_backup_codes`, `tenants.idp_org_id/idp_org_domain`, RLS policy snippets and
the `(tenant_id, …)` index requirement.

### 4.3 Permissions (G16) — FIXED

Provisional keys added so the identity-management surface is not key-less:
`tenant.identity.read`, `tenant.identity.suspend`, `tenant.sso.configure`,
`tenant.scim.manage`, `platform.identity.admin`, `platform.tenant.provision`.

### 4.4 API surfaces (G17) — FIXED

`contracts/api/auth.md` gains `GET /v1/auth/mfa/status` and
`POST /v1/auth/mfa/enrollment`; `contracts/api/tenant.md` documents the IdP
provisioning steps (org + project + app + policies) and the SSO/SCIM management
surface as V1/MVP sections, with regenerated OpenAPI.

## 5. Tenant module (docs/03)

### 5.1 Lifecycle enforcement matrix (G7) — FIXED

A per-state table now states, for every lifecycle state, what is allowed for
traders, staff, API keys, webhooks, bridge sync, payouts and payments — the
`onboarding` and `deactivated` states previously only appeared in prose.

### 5.2 Termination and deletion (G7) — FIXED

Termination is documented as a saga mirroring provisioning (stop traffic → export
→ revoke identities in ZITADEL → archive R2 → anonymise → schedule deletion), with
the retention windows, the recovery window (`deactivated → active` inside N days),
and the rule that financial rows survive anonymised.

### 5.3 Subdomain rules (G8) — FIXED

Format (3–30 chars, `[a-z0-9-]`, no leading/trailing hyphen, no punycode
look-alikes), the reserved list (www, admin, api, app, console, login, id, auth,
status, docs, support, mail, cdn, static, staging, test, demo, billing, …), the
normalisation (lowercase, unicode → error not transliteration), the uniqueness
check (DB + DNS negative cache), and the V1 rule: **subdomains are immutable**
(changing one is TEN-43, V2, and would require a redirect window).

### 5.4 Integration secret inventory (G13) — FIXED

A table lists every tenant-integration field, whether it is a secret, its storage
(envelope-encrypted with the per-tenant DEK), masking on read, rotation path and
audit: broker credentials, payment provider keys/webhook secrets, KYC provider
keys, email sender credentials, and (V2) payout rails.

### 5.5 Tenant login hostname (G19) — FIXED

V1 posture: tenant users log in on the IdP host scoped to their org
(`login.alpha1.io` + org scope, per-org branding = tenant logo/colours/texts);
tenant custom domains serve the *app*, and a vanity login host
(`login.firm.com`) is V2 (TEN-05), implemented at the edge as a rewrite that
preserves the org scope — the same pattern as the app-side custom domain.

## 6. Operations, migration, testing

### 6.1 Migration (G9) — FIXED

`docs/25` now states the option ZITADEL actually supports: bulk import via
`/admin/v1/import` with `hashedPassword` when the source algorithm is enabled in
`ZITADEL_SYSTEMDEFAULTS_PASSWORDHASHER_VERIFIERS` (bcrypt default; argon2, scrypt,
pbkdf2, md5-family, phpass, drupal7 available) — hashes are re-hashed transparently
on the next successful login. So the cutover can choose **import-and-keep** (no
forced reset) or **reset-required** (`passwordChangeRequired`); the recommendation
stays reset-required for TTS unless TTS's KDF is on the list and the COO accepts
the verification risk. Either way the OTP seeds (2FA) and passkey keys can be
imported too.

### 6.2 New service in the ops docs (G10) — FIXED

docs/06 gains the service row, health endpoints, deploy ordering (migrate →
zitadel → api), the second-database backup entry and the upgrade rehearsal step;
docs/29 gains the auth capacity/failure rows (login burst, JWKS, deny-set memory,
IdP restart); docs/34 gains the version pin, licence note and exit path.

### 6.3 Test plan (G14) — FIXED

docs/35 gains, for AUTH/TEN: the token-verification matrix (valid/expired/wrong
audience/wrong issuer/rotated JWKS), realm separation both ways, RLS negative
tests (no context → zero rows, cross-tenant write rejected), staff-MFA gate,
tenant-state enforcement matrix, IdP-outage drill, and the upgrade rehearsal.

## 7. Requirement rows still without design text (G15)

These rows are named in the coverage lines but have no design section yet. They are
all V2/V3 except where noted, and they are **not** blockers for the V1 contract
freeze — but each needs a stub before its phase starts (owner listed in the PRD):

`AUTH-31` terms acceptance log · `AUTH-32` registration abuse protection ·
`AUTH-35` self-serve closure · `AUTH-36` duplicate identity merge ·
`AUTH-37` trusted devices · `AUTH-38` staff credential hygiene ·
`TEN-20` usage metering · `TEN-21` tenant health view · `TEN-27` config
inheritance/effective view · `TEN-28` config versioning · `TEN-33` offboarding
export · `TEN-38` archival vs hard deletion.

Two of them gain a V1 hook in this pass: `AUTH-31` (the terms-acceptance record is
written by our `/v1/auth/session` on first login — the table and event are defined
now, the UX is V2) and `AUTH-36` (the `identity_key` introduced for G1 is exactly
the merge anchor; the merge procedure itself is V2).

## 8. Decisions this review opens

| # | Question | Default if unanswered |
|---|---|---|
| D6 | Per-identity concurrent session limit (the last `contracts/api/auth.md` TODO) | 10 active sessions, oldest evicted |
| D7 | Migration posture for TTS traders: import password hashes (keep passwords) or force reset | Force reset (`passwordChangeRequired`) |
| D8 | Does the tenant's own domain ever serve the **login** page in V1 (vanity `login.firm.com`), or is IdP-hosted login on `login.alpha1.io` with per-org branding enough? | IdP-hosted + per-org branding; vanity host deferred to V2 with TEN-05 |
| D9 | Is the residual PII in ZITADEL's event stream acceptable (documented, upstream #7811), or do we need a compensating control (e.g. pseudonymous login names with notification-only email) for the DPO? | Accept + document; re-review when #7811 ships |

These are recorded in `docs/37` §Design-review questions (D6–D9) so they carry an
owner and a deadline like every other open row.

The **deprovisioning follow-up** raised by the third pass lives in
`docs/43-idp-deprovisioning.md` with decisions **D10–D12**: token-lifetime enforcement
(15 min, written to the instance OIDC settings), the `idp-sync` propagation mechanism
(pull consumer over the event log, reconciliation as the safety net), and the
self-service deletion posture (withhold; closure through us).

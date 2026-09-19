# 41 — AUTH + TEN: Open-Source Solution Evaluation

> Research date **2026-09-19**. Scope: the identity layer (`AUTH`, 43 reqs) and the
> tenant layer (`TEN`, 45 reqs) — what we could adopt instead of building, what we
> must still build ourselves, and where the current spec's assumptions are wrong.
>
> This document is the *evidence* for §12 of [02-identity-access](02-identity-access.md)
> and [03-tenant-management](03-tenant-management.md). It changes no binding decision
> on its own: the decisions it recommends are listed in §8 and are recorded in
> [37-prd-open-questions](37-prd-open-questions.md) once approved.
>
> Requirement coverage: cross-cutting (vendor evaluation for `AUTH-*` + `TEN-*`).

## 1. What the solution must satisfy

The constraints are unusually narrow, because they come from the PRD, the ADRs, and
the team shape — not from a wish list.

| # | Constraint | Source |
|---|---|---|
| C1 | **Self-hosted, open source, no per-MAU cost.** Auth0/Cognito are forbidden. | `docs/34` §2 BVR-14, §3.5; PRD Out Of Scope |
| C2 | **One person = one identity, member of several tenants**; roles are *per tenant*, not global. | AUTH-12/15, TEN-01; `docs/02` §3.1 |
| C3 | **Two realms:** tenant users (traders/staff) and platform staff must never share a session. No impersonation in V1. | AUTH-16, `docs/02` §3.1 |
| C4 | **Go runtime for the API**; Node only for the Next.js web tier; one Hetzner box + Docker Compose; Kubernetes forbidden. Every extra service is an on-call surface for one DevOps. | `docs/01` ADR-4, ADR-9; BVR-10 |
| C5 | **Shared-schema multi-tenancy** with a mandatory `tenant_id` on every tenant-owned table; no schema-per-tenant, no DB-per-tenant. | `docs/01` ADR-1; PRD Out Of Scope (confirmed answered) |
| C6 | **Tenant resolution from the request** (custom domain → subdomain → internal header → API key, that order). | TEN-02, `docs/02` §3.3 |
| C7 | **Short-lived access token + rotating refresh token + server-side revocation**; replay of a rotated token revokes all sessions. | AUTH-07 (V1, binding) |
| C8 | **Declared `resource.action` permission keys enforced per route**, with module ownership and per-tenant custom roles later. | AUTH-13 (V1), AUTH-14 (V2) |
| C9 | **Staff TOTP 2FA mandatory**, trader TOTP optional (V2), backup codes (V2), step-up for payout/settings (V2). | AUTH-09/10/11/30 |
| C10 | **Tenant lifecycle**: create → provision (org, branding, broker group, rule packs, flags) → suspend → terminate, with a suspension cascade that kills sessions and blocks writes. | TEN-01, TEN-08, TEN-15, TEN-42 |
| C11 | **Tenant config is data**: branding, terminology, legal pages, email sender, limits, entitlements, integration secrets (encrypted, SOPS+age). | TEN-04/06/11/12/13/14 |
| C12 | **V3 path**: SSO federation (SAML/OIDC), SCIM provisioning, passwordless/passkeys. | AUTH-24/25/26 |

Everything else in AUTH/TEN (rate limiting, lockout, audit, login history, quotas,
impersonation) is either already ours to build or sits on top of whatever identity
component is chosen.

## 2. The landscape, in three classes

The market splits cleanly, and the split is what matters — not the vendor list.

| Class | Examples | Shape | Fit for Alpha One |
|---|---|---|---|
| **A. Embedded auth library** | **Better Auth** (MIT, TS), SuperTokens (Apache-2.0 core, Java core + SDKs), Casbin (authz only) | Runs *inside* our app; we own the tables, the UI, the flows | Best for C2/C3/C8 (we need tenant-specific semantics the PRD already defines), worst for C4 if we don't have a Node surface |
| **B. Headless IdP / API-first** | **Ory Kratos** + Hydra + Keto (Apache-2.0, Go), Zitadel (AGPL-3.0, Go), Logto (MPL-2.0) | A service we call; we build the UI | Good ops profile for Go shops; multi-tenancy is the weak spot (Kratos explicitly does not do B2B tenancy in OSS) |
| **C. Full IdP server** | **Keycloak** (Apache-2.0, Java), **authentik** (MIT core, Python), Zitadel, Casdoor (Apache-2.0, Go) | Login happens at the IdP; we consume OIDC tokens | Solves C12 today, but adds a heavyweight stateful service (C4) and an identity store outside our Postgres (C5/C11 friction) |

Two more axes cut across the classes and matter more than the vendor choice:

- **Where sessions live.** A library/headless approach keeps sessions in our Postgres
  and Redis (AUTH-07 revocation is then trivial). A full IdP moves the session to the
  IdP; our API only sees tokens, and "revoke all sessions of a suspended user"
  becomes an IdP admin call (possible, but a second source of truth).
- **Who owns the tenant entity.** With class A/B the tenant row lives in our schema
  and the identity layer references it (TEN owns the lifecycle, AUTH owns membership).
  With class C the IdP usually owns an "organization" object, and we get a
  synchronization problem between `tenants` and the IdP's orgs (TEN-27 config
  inheritance, TEN-28 versioning, TEN-34 clone, TEN-44 branding limits all assume
  *we* own the data).

## 3. The two PRD-mandated choices, re-examined

The PRD named Better Auth (BVR-14) and Cerbos (BVR-23). Both were named before the
Go-stack decision was tested against reality. This is what the research says.

### 3.1 Better Auth — the premise needs correcting

| Fact | Consequence |
|---|---|
| Better Auth is **TypeScript-only**; there is no official Go SDK. Community ports exist (e.g. `jasoncolburne/better-auth-go`) but it is a protocol re-implementation, not the library. | The spec's phrase *"we use its Go API surface"* (`docs/02` §2) is **not implementable as written**. |
| The workable Go integration is documented and used in production: run Better Auth in the Node tier, enable its **JWT plugin**, expose **JWKS**, and have Go verify tokens with `jwk.Fetch` (`github.com/lestrrat-go/jwx`) — the "proxy pattern". | Requires a **new deployable**: an identity endpoint in the `web` tier (or a small `auth` Node service). That is a service-count increase under ADR-9 and must be explicit in the docs. |
| The **organization plugin** does deliver what AUTH-12/15 need: `organization` / `member` (per-org role) / `invitation` / optional `team`, `session.activeOrganizationId`, custom roles passed to `ac`/`roles`, **dynamic access control** (roles created at runtime — the AUTH-14 shape), organization hooks, invitations and multi-role members. | The Phase-0 spike in `docs/02` §2 is answerable **now**: the org plugin supports per-org member roles. The remaining question is not "does it" but "do we want a Node identity hop". |
| **SSO plugin** (`@better-auth/sso`) supports SAML 2.0 + OIDC with per-organization providers, organization provisioning and claim mapping — but its own docs say it is *"in active development and may not be suitable for production use"*. | V3 SSO (`AUTH-24`) could be Better Auth — but it is not a dependency we should bet V1 on. |
| 2FA (TOTP), backup codes, passkeys, admin plugin (ban/unban, impersonation), API keys are first-party plugins. | AUTH-09/10/11/26/30 are all covered without writing crypto. |
| MIT license, ~30k stars, active. | C1 satisfied. |

**Net:** Better Auth is a strong *feature* fit and a **runtime-fit problem**. The
choice is not "Better Auth yes/no" — it is *"is a 2-service identity path acceptable,
or do we want Go-native sessions?"* (§7 Options A/B/D).

### 3.2 Cerbos — still the right call, with a cheaper alternative

| Fact | Consequence |
|---|---|
| Apache-2.0 PDP, stateless (loads policy files, no DB), YAML + CEL policies, decision logs, policy tests, `PlanResources` query-plan API with ORM adapters (Drizzle, Prisma, SQLAlchemy, …). | Directly serves AUTH-13/14 and list-filtering (the "which rows may I see" problem). |
| Deployment: central service, **sidecar**, serverless, or **embedded as a Go library** (core engine is Go; WASM embedding is the commercial path for other runtimes). | ADR-4 (no standalone gateway process) does not forbid a PDP, but an **in-process Go embed** keeps the service count at zero — worth verifying in the spike. |
| Sub-millisecond decisions for typical authz; the vendor reports up to ~17× faster than their earlier OPA-based engine; stateless instances scale horizontally. | Meets the `docs/02` §11 authz budget (60 s per-`(role,action,resource)` cache is then optional). |
| If PDP is unreachable → we **deny** (fail closed), per `docs/02` §11. | Unchanged; with in-process embedding the failure mode disappears entirely. |
| OPA (Apache-2.0, CNCF) is the generalist alternative: Rego, bundle distribution, more ecosystem, but steeper language and no first-class role/tenant model. | Still the documented fallback; not better for our shape. |
| **Casbin** (Apache-2.0) is the embedded-library alternative: PERM model, **RBAC with domains/tenants** is a first-class model, Postgres policy adapters, hot reload, benchmarks ≈0.03 ms/op for domain RBAC at small scale and ≈2.3 ms at 11k rules. | The "no extra process, no extra language" option. Weaker on decision logs/explainability than Cerbos; policy lives in DB rows or CSV, which we'd have to review like code. |
| OpenFGA / SpiceDB (Zanzibar ReBAC) | Rejected in `docs/02` §12 as overkill; research agrees — we have role + attribute decisions, not a sharing graph. Their value is `ListObjects`; Cerbos' query plan covers our version of it. |

**Net:** keep Cerbos as the decision point, but **make the deployment mode explicit**
(sidecar vs embedded Go library) — the current doc implies a service and never says
what happens when the process is the API.

## 4. Class B/C candidates, scored

Legend: ✅ meets · ◐ partial / needs work · ❌ fails the constraint · — n/a.
"Ops" = marginal cost on the single Hetzner box (ADR-9). "C5" = does it respect *our*
tenant entity, or introduce a second one.

| Candidate | License | Runtime | V1 authn fit | Multi-tenant fit (C2) | Two realms (C3) | Ops (C4) | Owns our tenant data (C5/C11) | V3 SSO path (C12) | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| **Better Auth** (library, Node) | MIT | TS | ✅ registration, login, sessions, TOTP, API keys | ✅ org plugin: per-org roles, invitations, dynamic roles | ✅ two separate instances/configs | ◐ **+1 deployable** (Node identity endpoint) | ✅ tables are ours | ◐ SSO plugin (not production-ready per its docs) | **Keep — see §7 Options A/B** |
| **Ory Kratos** (+Hydra/Keto/Polis) | Apache-2.0 | Go | ✅ flows, TOTP, passkeys, magic links | ❌ **no OSS multi-tenancy** — the official position is one instance/project per tenant; B2B org login is enterprise | ✅ separate projects | ❌ per-tenant instances; 3–4 components in the Ory stack | ❌ identities leave our schema | ✅ (enterprise / Polis for SAML) | Reject for V1; note as the "all-Go" path only if we accept per-tenant instances |
| **Zitadel** | **AGPL-3.0** (SDKs Apache-2.0) | Go | ✅ | ✅✅ organizations/projects are first-class, per-org IdP + branding | ✅ | ◐ single binary + Postgres, but a second identity store | ❌ its own org/user model; we'd reconcile `tenants` ↔ orgs (TEN-27/28/34 pain) | ✅ SAML/OIDC/SCIM 2.0 built in | **Strongest feature fit; license + second source of truth are the blockers. Ask (Q2)** |
| **Keycloak** | Apache-2.0 | Java/Quarkus | ✅ | ◐ Organizations (supported since 26.0, one realm); realm-per-tenant scales to 2000+ realms but whole-cluster ops grow linearly | ✅ | ❌ 1–2 GB RAM idle, Java + Infinispan cache; heaviest option | ❌ | ✅ SAML/LDAP mature; SCIM only preview (26.7) and per-realm, reusing admin roles | Reject for V1; keep as the "enterprise SSO checklist" answer if a tenant demands deep SAML/LDAP |
| **authentik** | MIT core (+ enterprise carve-out) | Python/Django + Go outposts | ✅ | ◐ brands/tenants, SCIM, LDAP outpost | ✅ | ◐ ~0.8 GB RAM, Django + workers | ❌ | ✅ SAML/OIDC/SCIM | Not for V1 (`docs/02` already registers it as the **V3 SSO** option — that call stands) |
| **SuperTokens** | Apache-2.0 core (`ee/` carve-out) | Java core + Node/Go SDKs | ✅ sessions, rotation, theft detection, TOTP | ✅ multi-tenancy in core | ✅ | ◐ core service + Postgres | ✅ (SDK model, but core tables are its own) | ◐ SAML only via SAML Jackson / Ory Polis | Plausible if we want SDK-embedded auth in Go; smaller feature set than Better Auth, enterprise bits are `ee` |
| **Logto** | MPL-2.0 | Node | ✅ | ❌ OSS has no multi-tenant console; multi-tenancy is a Cloud feature; ≤3 SAML apps | ◐ | ◐ | ❌ | ◐ | Reject (OSS/Cloud split cuts exactly where we need it) |
| **Casdoor** | Apache-2.0 | Go single binary | ✅ | ◐ organizations exist, but the product is a UI-first IdP with a large surface | ◐ | ◐ | ❌ | ✅ OIDC/SAML/CAS/SCIM | Reject — no advantage over Zitadel, less governance |
| **Authelia** | Apache-2.0 | Go | ◐ forward-auth / OIDC provider | ❌ no multi-tenancy | — | ✅ tiny | ❌ | ❌ no SAML | Reject |
| **FusionAuth** | **Commercial** (free community edition) | Java | ✅ | ✅ tenants are first-class | ✅ | ❌ | ❌ | ✅ | Reject — C1 (not open source) |
| **Ory Polis** (ex-BoxyHQ SAML Jackson) | Apache-2.0 | Node | — (SAML bridge only) | ✅ per-tenant connections | — | ◐ +1 service | — | ✅ fills the SAML gap for any OIDC-only choice | **Keep as the SAML bridge option** if we ever need SAML without a full IdP |

### 4.1 What no candidate gives us (we build it either way)

- **Tenant resolution order** (TEN-02) with the 404-not-403 no-oracle rule — ours.
- **Suspension cascade** (TEN-15) across sessions, orders, payouts, webhooks — ours
  (an IdP can revoke its own sessions, but not our domain state).
- **Config inheritance, versioning, clone, branding limits** (TEN-27/28/34/44) — ours.
- **Integration secrets** (TEN-11/12, SOPS+age) — ours.
- **Step-up for payout approval / settings** (AUTH-30) — policy we own; the IdP only
  supplies the 2FA primitive.
- **Custom role → permission-key mapping** (AUTH-14 + `contracts/permissions/registry.md`)
  — ours (Better Auth's dynamic roles and Cerbos' derived roles both need our key
  catalog as the source of truth).
- **Enumeration-resistant flows, lockout, login history, IP allowlists** (AUTH-18/19/23/33)
  — ours in either model; only the class-C IdPs ship some of it.

## 5. Multi-tenant data isolation — the third decision

ADR-1 fixes *shared schema*; it does not fix *who enforces the predicate*. Three
levels exist, and the research on Postgres RLS is specific enough to decide:

| Level | Enforced by | Failure mode when the caller forgets | Cost |
|---|---|---|---|
| **App-level guard** (today's plan: `db.Tenanted`, sqlc queries carry `tenant_id`, CI `guard_test.go`) | Go wrapper + code review + CI | The forgotten query returns **every tenant's rows** — silent, catastrophic | 0 |
| **Postgres RLS** (add as defense-in-depth) | The database, on every plan | **Zero rows** — fail-closed | 2–4 % on indexed queries; full scans if `tenant_id` is not indexed |

Research findings that decide the mechanics, if we adopt it:

- **Transaction-scoped context is mandatory.** With PgBouncer in transaction mode
  (ADR-8), a session-level `SET app.tenant_id` **leaks to the next tenant** on the
  recycled backend. The only correct pattern is `set_config('app.tenant_id', $1, true)`
  (or `SET LOCAL`) inside the transaction, read back by the policy via
  `current_setting('app.tenant_id', true)`.
- **`FORCE ROW LEVEL SECURITY`** is required, otherwise the table owner (our
  migration/user role) silently bypasses every policy.
- **Index discipline:** every policy column needs a `(tenant_id, …)` index, and the
  planner must fold the predicate into the index scan; without it the policy turns
  index scans into sequential scans (the reported production failure mode).
- **GUC unset ⇒ zero rows** — the correct failure mode for a security control, which
  is exactly why it is worth having under a shared schema.
- Testing is provable in CI (pgTAP or our own negative tests): tenant A reads only A;
  no tenant set reads nothing; a write tagged with another tenant fails the
  `WITH CHECK`.

This does **not** replace ADR-1: it *is* ADR-1's shared schema, with the predicate
enforced twice.

## 6. What this changes in the current spec

| Current statement | Reality | Action |
|---|---|---|
| `docs/02` §2: "Better Auth … we use its Go API surface" | No Go SDK exists | Rewrite after Q1 — either the Node identity endpoint (+JWT/JWKS for Go) or the chosen alternative |
| `docs/02` §2: "Phase 0 spike: confirm the org plugin supports per-org member roles" | Answered: it does (per-org `member.role`, custom/dynamic roles, invitations, hooks) | Replace the spike with *integration* criteria (token issuance, tenant claim, revocation propagation) |
| `docs/02` §12: "Cerbos … fallback in-house policy engine" | Cerbos can also be embedded in-process (Go) | Record the chosen deployment mode; keep the interface `authorizer.Check(…)` |
| `docs/02` §11: "PDP down → deny (fail closed)" | True for a sidecar/central PDP; moot if embedded | Keep as the sidecar rule |
| `docs/03` §12: "Nile/Citus rejected; revisit at >200 tenants" | Consistent with the RLS research; the shared-schema + RLS path is the scale answer | Keep; add the RLS decision from Q3 |
| Tech stack lines in both docs | List Better Auth/Cerbos without the Node hop or the deployment mode | Update with Q1/Q4 outcomes |

## 7. Options

**Option A — Keep Better Auth, add an explicit identity endpoint (recommended).**
Better Auth runs in the Node tier (`web`, or a small dedicated `auth` service) with its
JWT plugin; Go verifies via JWKS and keeps `identities`-grade data in Postgres. Cost:
one more deployment unit + Node↔Go token contract. Benefit: every AUTH-01…43 flow
(register, login, reset, TOTP, backup codes, sessions/rotation, org membership,
invitations, API keys, dynamic roles) exists today; MIT; no new identity store.

**Option B — Better Auth for flows, Go-owned sessions.** Same Node identity endpoint,
but we disable Better Auth sessions for the API path and issue our own rotating
refresh tokens (AUTH-07's semantics are ours anyway). Benefit: revocation and
tenant-scoped session tables stay in our DB; risk: we re-implement what Better Auth
already tests.

**Option C — Replace with a multi-tenant IdP (Zitadel first, Keycloak if a tenant
demands deep SAML/LDAP).** Everything is OIDC; SSO/SCIM are day-one. Cost: a Go
single binary + Postgres schema we don't own, AGPL-3.0 review (Zitadel) or a 1–2 GB
JVM/Infinispan footprint (Keycloak), and a reconciliation layer between `tenants`
and the IdP's organizations. Best if Q2 answers "SSO is needed in V1".

**Option D — Build the identity domain ourselves in Go.** Sessions (opaque +
rotating refresh), Argon2id, TOTP (`pquerna/otp`), HIBP range check, invitations —
all in `api`, reusing Better Auth only as a reference. Cost: ~3–4 dev-weeks for
AUTH-01…43 without SSO; benefit: zero extra runtime, sessions and revocation are
first-class in our schema, and the Phase-0 spike disappears. Best if C4 (one
runtime, one service fewer) outranks feature reuse.

## 8. Decisions — answered 2026-09-19

These five decisions (and the four follow-ups they produced) are recorded as rows in
[37-prd-open-questions](37-prd-open-questions.md) §*Design-review questions*, and are
applied to `docs/01`, `docs/02`, `docs/03`, `docs/28`, `docs/34` and the contracts pack.

| # | Decision | Answer |
|---|---|---|
| **D1** | Identity component wiring | **Option C — adopt a multi-tenant IdP** (product: **P1 = ZITADEL**, self-hosted). Better Auth (BVR-14) and its Node-identity-surface question are retired; the `AUTH-*` domain package stays the boundary. |
| **D2** | Is SAML/OIDC SSO required by a V1 tenant? | **Yes, one tenant at cutover.** `AUTH-24` is promoted into V1 scope; `AUTH-25` (SCIM) follows per P3. |
| **D3** | Tenant isolation enforcement depth | **Postgres RLS adopted** as a fail-closed second layer on every tenant-owned table, on top of the ADR-1 application guard. |
| **D4** | Authorization engine + deployment mode | **Casbin, embedded in the Go `api`** (RBAC with domains). Cerbos is superseded; the `authorizer.Check(ctx, subject, action, resource)` interface is unchanged. |
| **D5** | V1 staff 2FA scope | **All staff roles, enforced at first login, with backup codes in V1** — `AUTH-11`, `AUTH-28` and `AUTH-29` become V1 dependencies of the enrolment path. |

Follow-up decisions created by the answers:

| # | Decision | Answer |
|---|---|---|
| **P1** | Which IdP? | **ZITADEL** — single self-hosted instance, Postgres-backed, one Organization per tenant, unmodified AGPL-3.0 (legal review is a Phase-0 gate). |
| **P2** | Where do login and session live? | **IdP-hosted login + IdP tokens at the API.** Hosted Login v2 (org-scoped), ZITADEL access tokens accepted by the Go `api`, plus our own `auth_sessions` projection and Redis deny-set for immediate revocation. |
| **P3** | SSO/SCIM depth in V1? | **SSO + SCIM for that tenant.** Role assignment stays with us; SCIM covers users only (ZITADEL limitation, verified). |
| **P4** | Who owns roles/membership? | **Our Postgres.** ZITADEL holds credentials, MFA, SSO links and login policy; membership, roles, custom roles and the permission registry stay ours, mirrored into tokens via Actions v2. |

## 8.1 Requirement mapping for the chosen stack (ZITADEL + Casbin + RLS)

`✓` = satisfied by the tool · `B` = we build it (ours either way) · `⚠` = satisfied with a
caveat that has an owner.

| Requirement | How the chosen stack satisfies it |
|---|---|
| AUTH-01 registration | ✓ ZITADEL Hosted Login registration, org-scoped (`urn:zitadel:iam:org:id:{id}`) so the trader lands in the right tenant org; org domain + login-name format set per tenant. |
| AUTH-04 login | ✓ Hosted Login v2; per-org login policy (MFA, passwordless, session lifetimes, password complexity, lockout). |
| AUTH-05 password reset | ✓ ZITADEL self-service reset (`/ui/login/…`, `POST /v2/users/{id}/password_reset` flows). |
| AUTH-07 sessions, rotation, revocation | ✓ ZITADEL refresh tokens with rotation + `/oauth/v2/revoke`, `RevokeAllMyRefreshTokens`, session-service `DeleteSession`; **B** our `auth_sessions` projection + Redis deny-set make revocation immediate at the API even before token expiry, and reuse-detection alerting is ours. |
| AUTH-08 session control (V2) | ✓ `ListMyUserSessions` / session v2 `ListSessions`, `DeleteSession`; **B** TD/ADM screens. |
| AUTH-09 staff TOTP mandatory | ✓ TOTP factor + per-org login policy; **B** enforcement keyed to *our* roles (staff vs trader in the same org) — api denies staff actions without an MFA assertion (`amr`) and the console shows enrolment. ⚠ owner BE-1, verify `amr`/`auth_time` claims in the Phase-0 spike. |
| AUTH-10 trader 2FA, AUTH-11 backup codes (V1 per D5) | ✓ factor management (`AddMyAuthFactorOTP`, self-service) — **B** backup codes are ours (schema + redemption endpoint), because ZITADEL has no recovery-code primitive; AUTH-28 (admin reset) uses ZITADEL's MFA reset APIs. |
| AUTH-12 role model, AUTH-13 permission engine, AUTH-14 custom roles | **B** with **Casbin** as the engine: model `g(r.sub, p.sub, r.dom)`, `dom` = tenant id; role hierarchy and the `resource.action` registry (`contracts/permissions/registry.md`) are ours. ZITADEL roles are used only as a login-time mirror so tokens can carry them. |
| AUTH-15 tenant scoping | **B** ADR-1 guard + **RLS** (D3). |
| AUTH-16 super-admin separation | ✓⚠ two OIDC applications (or two projects) with distinct audiences — console tokens cannot be accepted by tenant routes and vice versa; **B** the realm column on `identities` and the audience check in the GW. No impersonation in V1. |
| AUTH-17 password policy | ✓ per-org password complexity + ZITADEL's Argon2id hashing; **B** HIBP breached-password check (ZITADEL does not call HIBP) at registration/change. |
| AUTH-18 throttling, AUTH-42 unlock (V2) | ✓ per-org lockout policy (max attempts) + ZITADEL's own rate limits; **B** our per-IP counters, `Retry-After` semantics and the unlock endpoint (`UnlockUser`). |
| AUTH-19 login history (V2), AUTH-22 auth audit | ✓ ZITADEL's event-sourced stream is the authentication record; **B** Actions v2 `Event` webhooks → our `audit_events` (AUD-01) so login history and audit live with the rest of the platform. |
| AUTH-20 suspend, AUTH-43 unsuspend | ✓ `DeactivateUser` / `ReactivateUser` (+ session termination) driven by our admin API; **B** the reason codes, events and audit. |
| AUTH-21 API keys (V2) | **B** ours (SHA-256 hash + prefix + scopes) — ZITADEL machine users cover service accounts, not tenant-facing `sk_live_t_*` keys. |
| AUTH-23 IP allowlist (V2) | **B** GW/Cloudflare middleware keyed to our role model. |
| AUTH-24 SSO (V1 per D2), AUTH-26 passwordless (V3) | ✓ OIDC + SAML 2.0 per organization; ✓ passkeys/WebAuthn; **B** the tenant-admin SSO configuration screen and metadata exchange (ADM), plus the org-scoped login hand-off. |
| AUTH-25 SCIM (V1 per P3) | ✓⚠ ZITADEL SCIM 2.0 server (**User schema only** — no Groups); **B** the provisioning token per tenant, the user→membership mapping, and role assignment (which stays in our ADM). |
| AUTH-27 forced logout (V2) | ✓ session v2 `DeleteSession` / `RevokeAllMyRefreshTokens` per user; **B** the admin action, reason and audit. |
| AUTH-29 email change, AUTH-31 terms, AUTH-32 abuse protection, AUTH-33 enumeration resistance, AUTH-34 session policy, AUTH-35 closure, AUTH-36 merge, AUTH-37 trusted devices, AUTH-38 credential hygiene, AUTH-40/41 | Mixed: ZITADEL covers email-change verification, password change and policy; **B** for trusted devices, duplicate-identity merge, terms-acceptance ledger, closure orchestration and the full audit trail. |
| TEN-01/02/08/15/18/42 | **B** ours: `tenants` row, resolution order (custom domain → subdomain → internal → API key), entitlements, suspension cascade, storage prefixes, subdomain reservation. ZITADEL org is created by the provisioning saga (step 3) and referenced by `tenants.idp_org_id`. |
| TEN-04 branding, TEN-05 custom domain | ✓⚠ per-org branding (label policy, message texts, login texts) via ZITADEL; per-tenant *login* domains need either the instance custom-domain feature or a Cloudflare edge that maps `firm.com/login → login.alpha1.io?org=<id>` — **B** that mapping (TEN-05/26) and the branding asset validation (TEN-44). |
| TEN-11/12 integration secrets | **B** SOPS+age / field encryption, unchanged. |
| TEN-36 cross-tenant isolation testing | **B** the isolation suite, now asserting **both** layers: app guard and RLS (no-context → zero rows). |

## 8.2 New risks accepted with these decisions

| Risk | Mitigation |
|---|---|
| **AGPL-3.0** on ZITADEL's main repo | Run unmodified; never patch source (contribute upstream); all customisation via Actions v2 (configuration, not derivative work); legal review at Phase 0 exit; keep the Keycloak escape hatch documented (ADR-13). |
| A second identity store (credentials in ZITADEL, roles in our DB) | P4 makes the split explicit: ZITADEL = authentication + login policy; our DB = authorization. Drift is detected by a nightly reconciliation job and surfaced in TEN-32 access review. |
| Login availability is now ZITADEL's availability | Single instance on the same box (ADR-9), Postgres backup/restore ritual covers both databases (docs/01 ADR-10); ZITADEL's own `/debug/healthz` joins the uptime checks (docs/29). |
| Per-org MFA policy cannot distinguish staff from traders in one org | Enforce staff MFA in the api on the `amr` claim (AUTH-09) and force MFA in the org policy only if a tenant asks for all-user MFA; spike item for BE-1 (see AUTH-09 row above). |
| Promotions change the release plan (AUTH-24/25 and AUTH-11/28/29 move earlier) | Recorded as post-PRD design decisions in docs/37 (D2/P3/D5) and reflected in docs/99 Phase 0/1 task lists; the PRD workbook itself is untouched — these are design-level scope changes with an explicit, citable origin. |

## 9. Sources

### 9.1 Chosen stack (verified 2026-09-19)

- ZITADEL organizations, per-org settings (MFA, passwordless, session lifetimes,
  IdPs, password complexity, lockout, branding, message texts), org scopes
  (`urn:zitadel:iam:org:id:{id}`, `…:domain:primary:{domain}`) and domain discovery —
  [Organizations](https://zitadel.com/docs/guides/manage/console/organizations),
  [Hosted Login UI](https://zitadel.com/docs/guides/integrate/login/hosted-login),
  [B2B multi-tenant scenario](https://zitadel.com/docs/guides/solution-scenarios/b2b).
- Sessions and revocation — [session service v2 (GetSession/DeleteSession/List)](https://zitadel.com/docs/apis/resources/session_service_v2/session-service-get-session),
  [RevokeAllMyRefreshTokens](https://zitadel.com/docs/apis/resources/auth/auth-service-revoke-all-my-refresh-tokens),
  [RevokeMyRefreshToken](https://zitadel.com/docs/apis/resources/auth/auth-service-revoke-my-refresh-token),
  [revocation endpoint](https://help.zitadel.com/how-to-revoke-an-access-token/refresh-token).
- User lifecycle parity for AUTH-20/43 (deactivate/reactivate, lock/unlock) —
  [User service v2 ReactivateUser](https://zitadel.com/docs/reference/api/user/zitadel.user.v2.UserService.ReactivateUser);
  v1 management equivalents are deprecated, so we pin the v2 API.
- Token claims and enrichment (the P4 wiring — roles/permissions mirrored into tokens) —
  [Claims](https://zitadel.com/docs/apis/openidoauth/claims),
  [Actions v2 code examples](https://zitadel.com/docs/apis/actions/code-examples),
  [role→permissions via org metadata + preAccessToken](https://help.zitadel.com/extend-authorization-in-zitadel-with-organization-metadata-preaccesstoken-action-),
  [custom roles example](https://github.com/zitadel/actions/blob/main/examples/custom_roles.js),
  [Actions v1→v2 trigger map](https://zitadel.com/docs/guides/integrate/actions/migrate-from-v1).
- SCIM limit that shapes P3 — [SCIM v2.0 guide ("only the SCIM User schema … Group provisioning … not supported")](https://zitadel.com/docs/guides/manage/user/scim2),
  [inbound SCIM issue #8140](https://github.com/zitadel/zitadel/issues/8140).
- Licence and self-host scope — [AGPL-3.0 main repo, no MAU limits self-hosted, cloud tiers](https://doolpa.com/article/zitadel),
  [AGPL risk framing and self-hosted feature parity](https://www.opentechhub.io/zitadel/).
- Casbin — RBAC with domains (the model ADR-14 uses): policy matchers keyed on a
  domain field, Postgres adapters and in-process enforcement, per the survey and
  benchmarks already cited above.

## 9.2 General landscape

Vendor and comparison sources consulted 2026-09-19 (all links verified in-session):

- Better Auth organization plugin, dynamic access control, teams, hooks —
  [plugin docs](https://github.com/better-auth/better-auth/blob/main/docs/content/docs/plugins/organization.mdx);
  organization limits/roles/invitations and multi-tenant patterns
  [Neon guide](https://neon.com/docs/auth/guides/plugins/organization),
  [Crea guide](https://crea.mba/en/blog/multi-tenancy-better-auth-guide).
- Better Auth SSO plugin (SAML 2.0 + OIDC, per-organization providers, provisioning)
  and its "may not be suitable for production use" notice —
  [SSO docs](https://www.better-auth.com/docs/plugins/sso.mdx),
  [package](https://www.npmjs.com/package/@better-auth/sso).
- Better Auth + Go via JWT/JWKS ("proxy pattern"), and the absence of a Go SDK —
  [Go Fiber integration](https://rogasper.com/blog/better-auth-with-non-node-backends-1766666588906),
  [Go + Better Auth write-up](https://blog.dreamsofcode.io/better-auth-is-so-good-that-i-almost-switched-programming-languages),
  community port [better-auth-go](https://github.com/jasoncolburne/better-auth-go).
- Better Auth license/scale profile — [MIT, ~30k stars, v1.7.x](https://www.opensourcealternatives.to/item/better-auth).
- Cerbos deployment modes (central, sidecar, embedded library, WASM),
  [vs OPA](https://www.cerbos.dev/cerbos-vs-opa),
  [vs OpenFGA](https://www.cerbos.dev/cerbos-vs-openfga),
  [WASM embedded PDP](https://www.cerbos.dev/features-benefits-and-use-cases/wasm-embedded-pdp),
  [license/PDP scope](https://appsecsanta.com/cerbos).
- Casbin domain/tenant RBAC, benchmarks, adapters —
  [pkg.go.dev](https://pkg.go.dev/github.com/muratsplat/casbin),
  [authorization tool survey](https://startwithidentity.com/articles/top-7-open-source-authorization-tools/),
  [Go backend patterns](https://zylos.ai/research/2026-05-20-rbac-ai-agent-systems-authorization-patterns/).
- Ory Kratos multi-tenancy position (not in OSS; enterprise/Network for scale) —
  [maintainer thread](https://github.com/ory/kratos/discussions/2403),
  [multi-tenancy discussion](https://github.com/ory/kratos/discussions/3056),
  [product comparison](https://skycloak.io/blog/open-source-authentication-comparison-2026/).
- Zitadel multi-tenant organizations, SAML/SCIM, AGPL-3.0 —
  [2026 review](https://doolpa.com/article/zitadel),
  [open-source alternative profile](https://www.opentechhub.io/zitadel/),
  [comparison table](https://skycloak.io/blog/open-source-authentication-comparison-2026/).
- Keycloak Organizations + realm scaling + SCIM preview limits —
  [Organizations announcement](https://www.keycloak.org/2024/06/announcement-keycloak-organizations),
  [multitenancy guide (realm measurements)](https://skycloak.io/blog/multitenancy-in-keycloak-using-the-organizations-feature/),
  [SCIM preview analysis](https://skycloak.io/blog/keycloak-native-scim-api-preview-26-7-2/).
- authentik / SuperTokens / Logto / Authelia / Casdoor / FusionAuth positioning and
  licensing — [comparison](https://skycloak.io/blog/open-source-authentication-comparison-2026/),
  [self-host alternatives](https://use-apify.com/blog/auth0-alternatives-2026),
  [SuperTokens + SAML Jackson](https://supertokens.com/blog/saml-vs-sso),
  [Logto OSS vs Cloud](https://blog.logto.io/logto-oss-vs-logto-cloud).
- Postgres RLS with PgBouncer (transaction-scoped `set_config`, `FORCE`, index
  discipline, fail-closed) — [production pattern](https://theroadtoenterprise.com/blog/postgres-rls-multi-tenant-saas),
  [pooling failure modes](https://multi-tenant-saas.com/tenant-aware-data-routing-query-scoping/connection-pooling-in-multi-tenant-systems/pgbouncer-transaction-pooling-for-multi-tenant-saas/),
  [benchmarks and pitfalls](https://dev.to/software_mvp-factory/row-level-security-in-postgresql-multi-tenant-data-isolation-for-your-saas-without-a-query-change-57bb).

## 10. Decision trail (2026-09-19) — where every answer landed

The nine decisions are canonical in `scripts/design-questions.json` (rendered into
`docs/37` §Design-review questions). This section records the *consequences*: which
doc, contract or register was changed because of each answer, so a reviewer can audit
the chain without re-reading the whole set.

| Decision | Answer | Landed in |
|---|---|---|
| D1 / P1 | Replace Better Auth with **self-hosted ZITADEL** (Organization per tenant) | `docs/01` ADR-13 (+ `zitadel` deployable row), `docs/02` §1–§3 + §7.0/§7.1, `docs/03` §3.2/§3.5, `docs/34` BVR-14 + integration row, `contracts/api/auth.md` (rewritten), `contracts/errors/taxonomy.md`, generator `scripts/build_contracts.py` (security scheme), docs/41 §3.1/§6 |
| D2 / P3 | SSO **and** SCIM in V1 for the cutover tenant (AUTH-24/25 promoted) | `docs/02` §1 (scope), §3.2 (IdP registration), §7.2; `docs/03` §3.5 step 3a; `contracts/api/tenant.md`; `docs/34` §3 rows + §9 checklist; docs/37 P3 answer |
| D3 | **Postgres RLS** as the fail-closed second isolation layer | `docs/01` §7.8, `docs/02` §9, `docs/03` §9, `docs/35` invariant I-17, `docs/28` §3.3, docs/41 §5 |
| D4 | **Casbin embedded** replaces Cerbos (BVR-23, ADR-14) | `docs/01` ADR-14 + GW step-3, `docs/02` §3.1, `docs/04` §2/§3, `docs/19`, `docs/34` BVR-23 + tool rows, `contracts/permissions/registry.md` |
| D5 | Staff 2FA mandatory at first login, **backup codes in V1** (AUTH-11 promoted) | `docs/02` §3.2 (enrolment + `amr` gate), §7.1/§7.2, §8 (`auth_backup_codes`), `contracts/api/auth.md`, `docs/35` invariant I-19 |
| P2 | IdP-hosted login + IdP-issued tokens at our API (no own refresh stack) | `docs/02` §3.2/§3.3, `docs/28` §6, `contracts/api/auth.md` (register/login/reset retired), `contracts/shared/openapi.yaml`, `contracts/README.md` |
| P4 | Our Postgres is authoritative for membership/roles/permission keys | `docs/02` §3.1 (membership model), §9 (`identity_key`, `idp_org_id`), `docs/03` §3.5 step 3, `docs/21`, `contracts/permissions/registry.md` |

### 10.1 Follow-up review (docs/42, 2026-09-19)

The second-pass review (`docs/42-auth-ten-gap-analysis.md`) re-checked all 88 AUTH+TEN
workbook rows against this stack and fixed the gaps that the decisions exposed. The
findings that change behaviour here:

1. **Org-scope regression (upstream #11869)** — the platform's identity model no longer
   assumes a person belonging to one ZITADEL organization; users are created in the org
   they register on and `identities.identity_key` joins them (docs/02 §3.1).
2. **Staff-only MFA is not an IdP policy** (upstream #6316) — enforcement moved into the
   API's `amr` check with new enrolment endpoints (docs/02 §3.2, §7.1).
3. **HIBP cannot be enforced on hosted-login password flows** — documented deviation with
   the residual gap owned by the Tech Lead (docs/02 §3.2).
4. **No IdP-side event retention** (upstream #7811) — two-store erasure procedure and a
   DPO review at Phase 0 exit (docs/02 §10.4, decision D9).
5. **Password hashes are importable** (verifier configuration) — the migration posture is
   now a cutover choice, not a forced reset (docs/25 §3.5, decision D7).
6. **V1 identity/tenant events were uncatalogued** — 13 payload schemas added
   (`contracts/events/payloads/`, `contracts/events/catalog.md`, docs/31).

### 10.2 Deprovisioning follow-up (docs/43, 2026-09-19)

The third pass asked a build question the first two did not: *how does an IdP-side
deprovisioning reach `tenant_memberships` before someone notices?* Findings that change
the design here:

1. **Actions v2 event executions cannot carry it** — a failed call loses the event with
   no retry (upstream #10268, open, v3-era, *To-be-closed*) and event-condition
   executions can break the instance's APIs and login (upstream #12225, open). The
   mechanism is therefore a **pull consumer over the event store**
   (`admin/v1/events/_search` + sequence cursor + durable inbox), with a webhook
   admissible only as a later fast path (docs/43 §2–§3).
2. **Token lifetimes were documented, not enforced** — ZITADEL ships 12 h access tokens;
   the 15-min figure in docs/02 §3.2 requires the instance OIDC settings to be written at
   provisioning (docs/43 §6, decision D10). This is the bound that survives a total
   pipeline + alerting failure.
3. **Reconciliation was mislabelled as the mitigation** — it is the safety net behind a
   real-time mechanism, and it is not built yet (docs/43 §1/§7).
4. **Self-service deletion is a live capability** (ZITADEL's `user.self.delete` via
   `ORG_USER_SELF_MANAGER` / `SELF_MANAGEMENT_GLOBAL`, both console and API paths) —
   V1 posture is to withhold it and route closure through us, with a role-grant alert as
   the enforcement (docs/43 §8, decision D12).

Precedent check (docs/43 §10): Stripe, Okta, Google Workspace, Entra Connect, Entra
provisioning quarantine and the IGA vendors all pair push with a pull/reconcile path —
we are following the norm; our vendor's zero-retry push is the reason the puller is the
transport rather than a nicety.

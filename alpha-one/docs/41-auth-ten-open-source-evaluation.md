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

## 8. Decisions needed

Each of these is recorded as a row in [37-prd-open-questions](37-prd-open-questions.md)
and then applied to §2/§12/§13 of `docs/02` and `docs/03`.

| # | Decision | Options | Default if unanswered |
|---|---|---|---|
| **D1** | Identity component wiring | A / B / C / D above | A (keep BVR-14, make the Node hop explicit, spike 2 days) |
| **D2** | Is SAML/OIDC SSO required by a V1 tenant? | no (PRD AUTH-24 stands at V3) / yes for one tenant at cutover / protect for it now | no — the PRD already schedules it V3 |
| **D3** | Tenant isolation enforcement depth | app-level only (ADR-1 as written) / **+ Postgres RLS** as defense-in-depth | app-level only; RLS deferred to V2 unless approved |
| **D4** | Authorization engine + deployment mode | Cerbos sidecar / Cerbos embedded (Go) / Casbin embedded / OPA / in-house behind `authorizer.Check` | Cerbos embedded if the spike passes, else Cerbos sidecar |
| **D5** | V1 staff 2FA scope | all staff roles / finance + risk only | all staff (AUTH-09 as written) |

## 9. Sources

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

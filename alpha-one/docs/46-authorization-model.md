# 46 — The Authorization Model (consolidated specification)

> Sixth pass on the identity stack, 2026-09-19, after `docs/45`. The fifth pass closed the
> last *authentication* gaps; this pass closes the **authorization-read** gap: everything a
> developer needs to answer *"who can do what, and where exactly is that enforced?"* in one
> navigable place. It changes **no decision** — it consolidates ADR-13/ADR-14 and decisions
> D14–D24 into one specification, adds two generated views, and fixes the stale wording this
> audit surfaced (findings A1–A4, §12).
>
> **Binding sources (this doc never overrides them):** AUTH-12/13 —
> `contracts/permissions/registry.md` (the keys),
> `contracts/permissions/roles.yaml` (the bindings —
> the machine-readable source, seeded into Casbin), [02 — AUTH](02-identity-access.md) §3.1
> (identity model + rendered role catalog), [04 — GW](04-gateway-events.md) §3.1 (the
> middleware-chain order). **Generated views (CI-gated, do not edit by hand):**
> `contracts/permissions/matrix.md` — the role × key
> matrix, the key → holders detail, and the V1 route → permission → authorized-roles map.

## 1. How to answer "can X do Y?" — the five questions, in order

Every authorization answer on this platform is the AND of five checks. When any one
fails, the request stops with the code listed in §6 — never a generic 403.

1. **Which realm is the request in?** The token's **audience** decides, not the caller's
   intent: a tenant-application token only ever reaches tenant routes, a console-application
   token only console routes (AUTH-16). Internal service tokens and API keys are separate
   classes again (§2). Cross-realm is structurally impossible, not policy-denied.
2. **Who is the subject, and what is their one role here?** A human is an `identities` row
   resolved through `identity_idp_links`; the `tenant_memberships` row for
   `(identity, resolved tenant)` carries **exactly one role** — there are no composite or
   multi-role grants in V1. Platform staff have `identities.realm='platform'` and no
   membership at all.
3. **What does the route demand?** Every V1 operation declares `x-permission`: a registry
   key (`resource.action`), `self` (caller on own data), or `none` (public / provider
   signature). A V1 operation without a declaration fails the build (gate 13, review G41).
4. **Does the role hold that key, at that scope?** `roles.yaml` is the single binding
   source: every key has a `scope` (`all` / `own` / `platform`) and an effective holder set
   (closed under inheritance). The rows are seeded into `casbin_rule` by migration and
   evaluated in-process by the embedded Casbin enforcer (ADR-14). **A key with no binding
   is denied for every role; a role with no keys can do nothing; an empty or unloadable
   policy set fails the boot closed** (D15).
5. **Do the attribute rules pass?** Scope matchers and ABAC (§7): tenant match first, then
   own-data, step-up freshness, owner-flag bounds — plus the status gates (§8) and the
   tenant's module entitlements.

To **change** an answer you change `roles.yaml` (a reviewed migration — §11), never code.
The full per-cell answer is `matrix.md` §1; the
per-route answer is its §3.

## 2. Subjects — who can be authorized at all

| Subject class | Credential | Realm | Authorized surface | V1 status |
|---|---|---|---|---|
| **Human — tenant member** (trader or firm staff) | ZITADEL access token (bearer), audience = **that tenant's** OIDC application (`tenants.idp_client_id`) | tenant | tenant routes, via the membership role | V1 |
| **Human — platform staff** | ZITADEL access token, audience = the **console** application; `identities.realm='platform'`; mandatory MFA (org `force_mfa`, G33) | platform | `/v1/console/*` only | V1 |
| **Internal service** (bridge → api, api → engine, relay, workers, `idp-sync`) | static per-service bearer token from SOPS (90 d rotation) | none (internal route group) | pre-allowed internal routes only — never user routes | V1 (docs/44 §7) |
| **Tenant integrator API key** | `sk_live_t_{tenant}_{random}`, SHA-256 hash + 8-char prefix at rest | tenant (embedded in the key) | key scopes only — **no tenant-facing surface in V1** (internal consumers only, D18) | primitives V1, UX V2 (AUTH-21) |
| **Provider webhook** | HMAC signature per provider (EVT-10) | none | the two `none` webhook routes (payments CHK-07, KYC KYC-05) | V1 |
| **ZITADEL machine users** (provisioning saga, `idp-sync` PAT) | JWT key / PAT | IdP plane | IdP administration only — governed by the D24 runbook, mirrored into our audit (`instance.member.*`) | V1 |

Not subjects: refresh tokens (never presented to the `api` — ZITADEL owns rotation, D17),
browser cookies (web-tier only; the `api` sees bearer tokens), ZITADEL's Console/Admin API
principals (IdP plane, not ours). System actors (`system:auth`, `system:<worker>`) appear
as event/audit actors but never as HTTP callers.

## 3. Realms and the role catalog — the 12 roles

Realms (AUTH-16, binding): **tenant** — `user:trader`, `firm:support`, `firm:finance`,
`firm:compliance`, `firm:risk`, `firm:admin` (inherits the four staff roles),
`firm:owner` (inherits admin); **platform** — `platform:readonly`,
`platform:finance`/`platform:support`/`platform:ops` (each inherits readonly),
`platform:super_admin` (inherits ops + support + finance). Superseded earlier names
(`platform:owner`, `platform:admin`, `platform:billing`) are recorded in `roles.yaml`
(`superseded_role_names`). A tenant role can never satisfy a platform policy and vice
versa — the realm rides the token audience, the role prefix, and the Casbin domain.

Below, "keys" are counted from the V1 registry (36 = 22 `all` + 4 `own` + 10 `platform`);
the authoritative per-cell view is `matrix.md`.

### 3.1 Tenant realm

| Role | Can (semantic) | Deliberately cannot |
|---|---|---|
| `user:trader` | Request a payout on an own funded account; manage **own** payout methods; read **own** documents/certificates; all keyless self-actions (login, logout, password, MFA enrolment, backup codes) | Anything `all`-scoped: read another trader's anything, see firm analytics/audit, any admin action. All 4 of its keys are `own` — the own-data matcher (A1) is what makes "own" true. Funded status is an **attribute**, not a role. Trader-optional 2FA is AUTH-10 (V2) |
| `firm:support` | List/filter **all** accounts (`account.read`) — the read-assist role | Read KYC documents or payout methods (no `kyc.document.read`/`payout.method.review`); see the payout queue; **any** write (no suspend/override/evaluate, no user suspend); audit or analytics. Support tooling (tickets) is V2 with proposed keys |
| `firm:finance` | Read accounts; view the payout queue; **approve/reject payouts** (step-up A3); record executions + export; write payout policy; view a trader's payout methods for approval (audited, A5) | KYC decisions or document reads; audit read/export; analytics; account suspend/override/evaluate; user suspend/unsuspend; challenge/ruleset/integration writes |
| `firm:compliance` | KYC review + decisions; maintain the restricted-country list; read a trader's KYC documents (audited, A5); view payout methods (audited, A5); read + export audit | Any payout decision/approval/execution/policy; account risk actions; analytics; user suspend/unsuspend; integration config. Data-subject request tooling is V2 |
| `firm:risk` | Read accounts; suspend/resume accounts; manual pass/fail/reset override (**bounded**, A4); force re-evaluation; view the payout queue (read-only); open risk cases; firm analytics | **Approve or execute payouts** (the queue is read-only for risk) — risk can *stop* money (account suspension, the RSK-11 payout hold) but can never *move* it; anything KYC; audit; user suspend; config writes |
| `firm:admin` | The union of the four staff roles — **all 22 `all`-scope keys**: traders (suspend/unsuspend), accounts, challenges, rule sets, payouts (full), KYC (full), risk cases, audit, analytics, integration config | Platform keys (structural — realm separation); the four trader `own` keys (they are per-person, not delegation); the V1.1/V2 team/SSO/SCIM governance keys (§13 — mostly owner-only once they land) |
| `firm:owner` | Identical effective key set to `firm:admin` in V1 — the difference is **governance**, not V1 keys: owner-only provisional keys (`tenant.identity.role_change`, `tenant.sso.configure`, `tenant.scim.manage`), the $500k override-approval duty (A4), the quarterly access review, billing view | Same as admin, plus: nothing is added in V1 — any doc claiming an owner-only *V1* key is stale (G30 closure) |

### 3.2 Platform realm

| Role | Can (semantic) | Deliberately cannot |
|---|---|---|
| `platform:readonly` | View tenant records (`tenant.read`) — health/tenant/analytics *read* visibility | Any write; any console control surface; any tenant-realm action, ever |
| `platform:finance` | = `platform:readonly` in V1 (`tenant.read`; CON-19 financial screens are read views) | Any tenant financial write — invoicing/dunning keys are V2/V3 proposals (§13) |
| `platform:support` | = `platform:readonly` in V1: tenant contact registry + console read visibility (G42 wording) | Cross-tenant read-assist is V2 (CON-27); **no tenant-realm action in V1** — AUTH-16 forbids it structurally |
| `platform:ops` | `platform:readonly` **+ revoke sessions**: another console operator's session (CON-30, V1 route) and — when the AUTH-27 surface ships — any identity's sessions (`platform.session.revoke`; exercised via runbook until then) | Create/update/suspend/terminate a tenant; change entitlements; administer console identities. Ops keeps the platform *running*, super_admin decides *who exists* |
| `platform:super_admin` | **All 10 platform keys**: tenant lifecycle (create/update/**suspend/terminate**), entitlement changes, the provisioning saga, console identity administration (`platform.identity.admin`), session revocation | Tenant-realm keys (structural); nothing else — it is the only role that may suspend or terminate a tenant or change a tenant's entitlements. The ZITADEL IAM plane is *not* part of this catalog: it is runbook-governed (exactly two named `IAM_OWNER` holders, D24) |

### 3.3 Structural rules that bound every role

- **Realm separation (AUTH-16)** — enforced at the routing layer, before any policy runs:
  a console-audience token is refused by tenant routes and vice versa; V1 has **no
  impersonation path at all** (no `tenant.impersonate` key exists — §4.5).
- **Per-tenant audience (D19)** — a token minted for tenant A's application is refused on
  tenant B's host even inside the tenant realm (`auth.tenant_mismatch`).
- **One role per membership** — role changes are audited (`user.role_changed`); the V1
  change path is the staff runbook (docs/06 §3.6), the V2 surface is
  `tenant.identity.role_change` (§13).
- **No field-level permissions** — the permission unit is the route/action key (PRD
  Out-Of-Scope; masking like `tenant.integration.read` "never decrypts" is module
  behaviour, not a permission).
- **Fail-closed everywhere** — unbound key → denied; unknown role → denied; empty policy
  at boot → deny all + SEV-1 (D15); RLS with no tenant context → zero rows (D16).

## 4. Permission keys

### 4.1 Format and the three scopes

`resource.action` (AUTH-13), module-declared, enforced at the API layer (GW-04). Each
binding carries one scope:

| Scope | Meaning | Casbin shape |
|---|---|---|
| `all` | Tenant-wide: any resource inside the caller's tenant | `p, role, key, all` + `g(identity, role, tenant_id)` — the domain **is** the tenant |
| `own` | Self-scoped: ABAC additionally requires `resource.user_id == subject.id` (after `resource.tenant_id == subject.tenant_id`, always checked first) | same rows + the own-data matcher (A1) |
| `platform` | Cross-tenant: console realm only; domain = `platform` | tenant roles can never hold these and vice versa |

The full V1 registry (36 keys, each with module owner + justifying Req ID) is
`registry.md`; the holder sets are `roles.yaml`; the
rendered matrix is `matrix.md`.

### 4.2 Keyless actions (`self`) and unauthenticated routes (`none`)

Actions with no resource beyond the caller's own session need no key — they are declared
`self` and still pass the own-data matcher: `/v1/auth/session`, `/password`,
`/2fa/backup-codes`, `/2fa/backup-code`, `/mfa/status`, `/mfa/enrollment`, `/logout`,
every trader-owned read (`/v1/trader/accounts*`, payouts list, checkout/KYC self
surfaces), console logout. `none` marks the surfaces with **no user authorization at
all**: the public catalog read, the two provider webhooks (signature-authenticated, EVT-10),
and console login (the login itself). 19 `self` + 4 `none` over the 61 V1 operations;
the full map is `matrix.md` §3.

### 4.3 The V1 registry in one line each

See `registry.md` for the authoritative table (key → module → description → Req ID) and
`matrix.md` §2 for key → scope → holders → constraint. Distribution: 22 `all`, 4 `own`
(all trader), 10 `platform` (9 super_admin-only or ops-shared, `tenant.read` held by all
five platform roles).

### 4.4 Bound V1 keys with no V1 route — the six, and their first surfaces

The verifier reports these as info, not error: the binding is ratified now, enforced from
the moment the route ships, and until then the key is exercised only by runbooks/internal
surfaces. Naming the first surface here so "bound but unrouted" is never mysterious:

| Key | First HTTP surface | What happens until then |
|---|---|---|
| `kyc.document.read` | The KYC manual-review document view (the KYC-11/36 review-detail + uploads surface, V1.1) | Compliance reaches documents through the KYC provider flow; any staff view is runbook + audit |
| `payout.method.read` | `GET /v1/trader/payout-methods` (the read side of PAY-05; the write side is already a V1 route) | Methods are created at payout-request time; reads ride the trader's own request context |
| `payout.method.review` | The payout approval **detail** view (PAY-08/09 queue detail — the reviewer must see the destination method) | Approval decisions use the queue list; method inspection is runbook + audit |
| `platform.identity.admin` | The console identity-admin UI — create/deactivate console users (AUTH-03 staff management, V1.1) and the forced MFA reset (AUTH-28, V2) | The V1 staff onboarding/offboarding **runbook** (docs/06 §3.6): ZITADEL user → MFA → `identities` row → Casbin grant → audit |
| `platform.session.revoke` | AUTH-27 admin forced logout (V2 surface, docs/02 §4.1) | V1 revocation happens through `user.suspend` (kills sessions) and CON-30 for console sessions |
| `platform.tenant.provision` | The saga run/resume/destroy surface (docs/03 §3.5; the V2 wizard per the CON contract) | V1 saga trigger = the TEN API's `tenant.create` route + the resume runbook (saga compensation) |

### 4.5 Keys that deliberately do not exist

- **`tenant.impersonate`** — AUTH-16 is a separation contract in V1: the console identity
  cannot act inside a tenant because **no impersonation path exists**. If V2 enablement
  (TEN-16, CON-07) is approved, the key is introduced *with* its audit format (AUD-08,
  CRITICAL) — never before.
- **`trader.read`** and similar staff-reads of trader profiles — staff see trader context
  through the module read models (`account.read`, queue views); no standalone key was
  ratified. The extended catalog in docs/02 §3.1 is design-level, not binding.
- **API-key scopes are not this registry** — `trades:read`, `accounts:read`,
  `payouts:read`, `payout:write`, … are the *key-scope catalog*, a separate namespace
  (§9). A permission key never appears in an API key and a scope never appears in
  `roles.yaml`.

## 5. Who holds what — the views

1. **Role → keys** — docs/02 §3.1 (generated render block) and `matrix.md` §1 (the full
   role × key grid with scope letters).
2. **Key → roles** — `matrix.md` §2 (with module owner and the ABAC constraint text).
3. **Route → key → roles** — `matrix.md` §3 (all 61 V1 operations).
4. **Machine source** — `roles.yaml` (what Casbin is seeded from; `--seed` prints the
   INSERTs). All four are kept identical by `scripts/verify_roles.py` (gates 9/13/15).

## 6. The authorization decision pipeline (per request, in order)

The chain order is **binding** (docs/04 §3.1); this section spells out the authorization-
relevant steps and the exact failure code of each. "V1" codes are the frozen registry
(`contracts/errors/taxonomy.md`); "(ext)" codes are registered in the extended block but
already enforced where noted.

| # | Check | On failure |
|---|---|---|
| 1 | Edge handoff — Cloudflare trust chain, WAF (GW-20/33) | edge-level |
| 2 | **Tenant resolution** — custom domain → subdomain → `X-Tenant-Id` (internal group only) → API key (key wins over headers) (docs/02 §3.4) | `404 tenant.unknown_host` (V1; never 400 — no subdomain enumeration) |
| 3 | **Authenticate** by credential class (GW-03): bearer → JWKS sig + issuer + **audience == the resolved tenant's `idp_client_id`** (D19; console routes demand the console audience) + org claim when present; Redis deny-set fast-path (session/jti, 24 h TTL). Internal group: per-service bearer. API key: hash lookup + expiry/revocation (internal consumers only, D18) | `401 auth.token_invalid` (the API's bearer-surface code — ext block per docs/02 §6.1's post-decision note; GW's V1 name for an authn failure is `auth.invalid_credentials`), `403 auth.tenant_mismatch` (D19), `401 auth.session_revoked` (deny-set), `401 auth.api_key_invalid` (ext) |
| 3.5 | **Status gate** (docs/44 §7) — resolved in this order so the error reveals no more than the host already did: (a) tenant state → (b) identity state → (c) membership state for `(identity, tenant)` — console realm skips (c). Cached ≤ 5 s per `(identity, tenant)`, invalidated by `user.suspended` / `user.activated` / membership events | `403 tenant.suspended` (V1), `403 tenant.not_live` (ext — onboarding tenant on a trader route), `403 auth.account_suspended` (V1 — suspended/banned/deactivated), `403 auth.membership_suspended` (V1) |
| 4a | **Staff-MFA gate (A2)** — every staff-role action requires an MFA assertion in the token (`amr` ⊇ `otp`/`webauthn`); platform-org `force_mfa` (G33) is the IdP-side second layer | `401 auth.mfa_required` (ext code, **V1-enforced**, D5) → route to enrolment |
| 4b | **Route declaration** — the operation's `x-permission` is a bound key, `self`, or `none` | build-time: gate 13 fails the CI run, not the request |
| 4c | **Policy check** — the embedded Casbin enforcer evaluates `Check(subject, domain, action, resource)` with subject = identity + role and domain = the tenant id (or the platform domain); rows seeded from `roles.yaml` (D14/D15) | `403 permission.denied` (V1; the ext successor `authz.denied` adds `details.policy`) — **every denial is logged** with the matched policy row (AUD-23) || 4d | **Scope matchers** — `all`: domain match only; `own`: A1; `platform`: platform domain + platform role | `403 permission.denied` |
| 4e | **Step-up (A3)** — `payout.approve` requires `auth_time` ≤ 5 min | `403 authz.step_up_required` with `details.max_age` (ext code, **V1-enforced**, D23) → client re-runs hosted login with `prompt=login&max_age=300` and retries |
| 4f | **Audit-on-access (A5)** — `kyc.document.read`, `payout.method.review` write an AUD-23 sensitive-access row (actor, target, correlation) | not a gate — a mandatory side effect |
| 5 | Rate limits — edge per-IP → per-user → per-route (GW-05) | `429 rate.limited` (V1) + `Retry-After` |
| 6 | **Quota + entitlement** — plan limits; **module entitlement gate** (TEN-08; changes are platform-side, `tenant.entitlement.change`) | `403 tenant.not_entitled` (V1), `429 gw.quota_exceeded` (ext) |
| 7 | Idempotency (GW-12/31) | `409 request.idempotency_conflict` (V1) |
| 8–10 | Correlation, hygiene (body caps, timeouts, header redaction), handler | — |
| 11 | Response — success envelope / GW-18 error contract | — |
| DB | **RLS backstop (D3/D16)** — tenant tables `FORCE ROW LEVEL SECURITY` on `app.tenant_id` (unset → 0 rows, fail-closed); context-free reads only via four named `SECURITY DEFINER` accessors; only enumerated `app_platform` services bypass, still with explicit tenant predicates | even a buggy *allow* cannot leak cross-tenant rows on tenant tables |

Self-guards ride in the handlers (400-class, not authz denials): `auth.cannot_suspend_self`
(suspending yourself), `console.cannot_revoke_self` (revoking your own console session).

## 7. ABAC — the attribute rules that ride on the keys

Role × key is necessary but not sufficient; these rules are part of the enforced model.
V1 rules (binding):

| # | Rule | Applies to | Predicate | On failure |
|---|---|---|---|---|
| A1 | **Own-data matcher** | every `own`-scope key + every `self` route | `resource.tenant_id == subject.tenant_id` (always first) **and** `resource.user_id == subject.id` | `403 permission.denied` |
| A2 | **Staff-MFA gate** | every staff-role action (`firm:*` keys, all console routes) | token `amr` contains `otp`/`webauthn`; enrolment via our endpoints (docs/02 §3.2); platform org additionally `force_mfa` (G33) | `401 auth.mfa_required` → enrolment |
| A3 | **Payout step-up** | `payout.approve` (V1's only freshness rule — D23) | session `mfa_verified_at` (= token `auth_time`) ≤ 5 min | `403 authz.step_up_required` + `details.max_age` |
| A4 | **Bounded risk override** | `account.manual_override` on accounts > $500k | requires a `firm:owner` approval flag in the request context | `403 permission.denied` |
| A5 | **Audit-on-access** | `kyc.document.read`, `payout.method.review` | every exercise writes an AUD-23 sensitive-access audit row | — (logging rule) |
| A6 | **Self-guards** | `user.suspend`/`unsuspend`, console-session revoke | actor ≠ target | `400 auth.cannot_suspend_self` / `console.cannot_revoke_self` |
| A7 | **Realm separation** | every key | tenant roles never satisfy platform policies and vice versa (audience + role prefix + Casbin domain) | structural refusal (AUTH-16) |
| A8 | **Per-tenant audience** | every tenant-realm request | token `aud` == the domain-resolved tenant's `idp_client_id`; org claim checked when present (D19) | `403 auth.tenant_mismatch` |

Named post-V1 rules (design-level, enforced when their surface ships):

| # | Rule | Source |
|---|---|---|
| A9 | **Geo restriction** — funded-account actions denied when `context.geo.country ∈ tenant.config.restricted_countries` (the list `firm:compliance` maintains via `kyc.restrictions.write`) | docs/02 §3.1 extended catalog |
| A10 | **API-channel payout manual approval** — the auto-approve policy never applies to API-key requests; a machine's payout request always gets a human | docs/27 §3.1, docs/11 §3.5 |
| A11 | **Impersonation** — read-only, CRITICAL-audited, time-boxed; introduces `tenant.impersonate` + the AUD-08 audit format | V2 (TEN-16/CON-07) |

## 8. Status gates — how lifecycle state changes authorization

Authorization never consults a single flag; it consults three state machines (§6 step 3.5)
plus module state:

| State | Effect | Code |
|---|---|---|
| Tenant `onboarding` | trader-facing routes refused; staff activation blocked until KYB | `tenant.not_live` (ext) / `tenant.kyb_required` (ext code, the V1 activation gate) |
| Tenant `suspended` | **all** tenant traffic refused at GW 3.5a; live sessions killed by event fan-out (`tenant.suspended` → GW deny-set) | `403 tenant.suspended` (V1) |
| Tenant deactivated / pending deletion | export-only surfaces inside the recovery window | `tenant.deactivated` / `tenant.pending_deletion` (ext) |
| Identity `pending_verification` | the hosted-login flow completes verification before the first materialised session; no tenant action before `active` | login-path refusals surface at ZITADEL |
| Identity `suspended` / `banned` / `deactivated` | status gate refuses; all sessions killed (deny-set + ZITADEL termination — a suspended user cannot log in even if our API is bypassed); mirror written to the IdP. `banned` is permanent; deactivation is the GDPR path (docs/02 §10.4) | `403 auth.account_suspended` (V1) |
| Membership `invited` | no session exists yet, so nothing is reachable; the **first `/v1/auth/session`** flips `invited → active` (G37/D22) | — (authn fails first) |
| Membership `suspended` | this tenant refuses the identity (the identity itself is fine — it may still belong to other tenants) | `403 auth.membership_suspended` (V1) |
| Trading account `suspended` (LCC-11) | **not an authz state** — routes still authorize; the engine/BRG refuse trading. Authz and trading-enforcement are deliberately separate layers | module codes (docs/07) |

Gate staleness is bounded: the 3.5 cache lives ≤ 5 s and is invalidated by the suspension
events, so a suspension propagates in well under the 15-minute worst case that the token
lifetime already guarantees (docs/43 §6).

## 9. Machine principals — service tokens, API keys, webhooks

**Internal service tokens (V1).** One static bearer per service from SOPS, 90-day
rotation, valid **only** on the internal route group (compose network, never edge-routed);
the tenant comes from `X-Tenant-Id`; every call is logged with the service identity +
`correlation_id` (docs/44 §7). Service tokens are **not Casbin subjects** — they carry no
role and can never exercise a registry key. Their authority is the explicit per-route
internal allowlist plus network placement; HMAC/mTLS is the V2 upgrade. A service token
presented on a public route is refused like any invalid credential.

**API keys (primitives V1 — D18: internal consumers only).** `sk_live_t_{tenant}_{random}`;
only the SHA-256 hash + 8-char prefix are stored; default 600 req/min; optional expiry;
revocation is immediate (hash delete + Redis blocklist 24 h). Scopes (`trades:read`,
`accounts:read`, `payouts:read`, …) form the **key-scope catalog**, frozen with AUTH-21
(V2 tenant UX) and the V3 public API (docs/27 Part A §3.1 — including the money-adjacent
`payout:write` tier at 60 req/min). Errors: `auth.api_key_invalid` (401) /
`auth.api_key_scope_missing` (403). No tenant route accepts a key in V1; tenant machine
integrations use TEN-11 integration secrets until AUTH-21 ships.

**Provider webhooks.** The only `none` routes: payments (CHK-07) and KYC (KYC-05),
signature-authenticated (EVT-10), schema-checked (`evt.webhook_schema_invalid`), deduped
(`evt.webhook_duplicate` → 200). A webhook can never carry user authority — it triggers
module-internal state machines.

**The IdP plane.** ZITADEL's Console/Admin API is private (internal network + Cloudflare
Access), with exactly two named `IAM_OWNER` holders (or one + a sealed break-glass
credential), mandatory MFA, a quarterly access review, and every IAM grant mirrored into
our audit by `idp-sync` (D24). It is governance, not part of the Casbin model — but it is
part of "who is authorized for what", which is why it is named here.

## 10. The data plane — RLS as the final backstop

The request-path DB role `app_rw` runs every tenant table under `FORCE ROW LEVEL
SECURITY` keyed on `app.tenant_id` (unset context → zero rows, fail-closed; `WITH CHECK`
on writes). Context-free identity lookups (session by id, key by hash, link by
`idp_user_id`, console sessions) go through four named `SECURITY DEFINER` accessors —
the only path that can read console sessions. Cross-tenant services (`relay`, ledger/audit
appliers, ANA updaters, `idp-sync`, CON read models) run as the enumerated `app_platform`
role (`BYPASSRLS`) and still carry explicit tenant predicates (CI-checked). Negative
matrix: docs/35 §5.1. Authorization bugs above this layer therefore cannot leak tenant
rows; the authz layer is about *intent*, RLS is about *blast radius* (D3/D16, docs/02 §9).

## 11. Governance — how authorization changes, and how it is verified

**Change control (V1).** There is no policy-CRUD surface (AUTH-14/AUTH-03 are V2), so
every authorization change is a reviewed deploy:

1. A module proposes a key in `registry.md` (with its Req ID) — the V1 table is frozen;
   post-V1 keys join at their module's freeze (docs/99 §12).
2. The key is bound in `roles.yaml`: one `scope`, an **effective** holder set (closed
   under inheritance), any ABAC constraint text. Proposed holders for future keys go to
   `provisional_bindings` so the later freeze is mechanical.
3. `scripts/verify_roles.py` must be green: registry ⇄ bindings ⇄ rendered docs/02 §3.1
   ⇄ matrix.md ⇄ every V1 route's declared key (gates 9/13/15).
4. The migration seeds `casbin_rule`, bumps `authz_policy_versions`, writes the audit row,
   and publishes `casbin:reload`; instances reload and re-check the version per request
   (cached ≤ 30 s). Boot with an empty/unloadable set = deny everything + SEV-1 (D15).

**People grants (V1).** Staff onboarding/offboarding is the docs/06 §3.6 runbook
(ZITADEL user → MFA → `identities` row → Casbin grant straight from `roles.yaml` →
audit), reviewed quarterly together with the ZITADEL IAM plane (D24) and the sealed
break-glass credential.

**Denial visibility.** Every denial is logged with the matched policy row (AUD-23 — the
accepted trade-off of an embedded engine with no decision log, ADR-14); the V1 client
sees the generic `permission.denied`, the ext `authz.denied` adds `details.policy` for
staff surfaces. Sensitive reads (A5) are audited even when *allowed*.

**Verification map.**

| Gate (docs/99) | What proves |
|---|---|
| 9 | `roles.yaml` seeded, verifier green, fail-closed boot |
| 12 | per-tenant audience binding (`auth.tenant_mismatch`) |
| 13 | 61/61 V1 operations declare a bound key or `self`/`none` |
| 14 | step-up freshness on `payout.approve` (D23) |
| 15 | **`matrix.md` regenerates byte-identical** from `roles.yaml` + registry + contracts (this pass) |

Plus the model tests over the Casbin fixtures (ADR-14 — e.g. trader cannot read another
trader's trades; support cannot read a KYC document), the token/status matrices and RLS
negatives (docs/35 §5.1), and the table-driven state × surface matrix (docs/35 I-20).

## 12. This pass — findings and changes (2026-09-19)

| # | Finding | Severity | Resolution |
|---|---|---|---|
| A1 | **The authorization model had no consolidated specification** — the roles, scopes, ABAC rules, decision order, status gates and machine principals were scattered across docs/02, 04, 21, 27, 44, 45, `registry.md` and `roles.yaml`; no role × key matrix and no route → authorized-roles view existed, so "who is authorized for what" required mentally intersecting five artifacts | High | **FIXED** — this document + the generated `contracts/permissions/matrix.md` (`verify_roles.py --write-matrix`), with the freshness gate (15) wired into the verifier |
| A2 | **`registry.md` still said `Status: DRAFT / Owner: TBD / 2026-09-17`** although D14 ratified the bindings on 2026-09-19, and its `console.session.revoke` row claimed "surface is V2" while the CON-30 route carrying it is `x-phase: V1` in `contracts/21-CON.openapi.yaml` | Medium | **FIXED** — header ratified (owner AUTH/Tech Lead, dated); the note now names the V1 CON-30 route and its `console.cannot_revoke_self` self-guard; `roles.yaml` `note` aligned |
| A3 | **`contracts/api/adm.md` still listed "staff role definitions for admin panel access" as an open owner decision**, although D14/`roles.yaml` answered it — a developer reading the contracts would believe the role model undecided | Low | **FIXED** — the open questions now point at the ratified catalog and this doc |
| A4 | **The six bound-but-unrouted V1 keys were reported by the verifier but never explained** — nothing said where `platform.identity.admin` or `payout.method.review` first bind to a route | Low | **FIXED** — §4.4 names each key's first surface and the runbook that exercises it until then; `matrix.md` §4 lists the set |

No PRD workbook row changed; no decision was re-opened; `roles.yaml` bindings are
untouched except the corrected `console.session.revoke` note.

## 13. Post-V1 reservations (bindings proposed, not seeded)

From `roles.yaml` `provisional_bindings` — holders recorded now so each freeze
(docs/99 §12) is mechanical; nothing here is enforced until its phase ships:

| Key | Phase | Proposed holders |
|---|---|---|
| `tenant.identity.read` | V1.1 | `firm:owner`, `firm:admin`, `firm:support` |
| `tenant.sso.read` | V1.1 | `firm:owner`, `firm:admin` |
| `tenant.sso.configure` | V1.1 | `firm:owner` |
| `tenant.scim.manage` | V1.1 | `firm:owner` |
| `tenant.identity.invite` | V2 | `firm:owner`, `firm:admin` |
| `tenant.identity.role_change` | V2 | `firm:owner` (only) |
| `tenant.identity.remove` | V2 | `firm:owner`, `firm:admin` |
| `platform.analytics.read` | V2 (ANA-28 pattern) | all five platform roles |

Also reserved: **custom roles** (AUTH-14, V2 — tenant-scoped role definitions as Casbin
rows versioned with the tenant config, TEN-28), **impersonation** (`tenant.impersonate` +
AUD-08, V2), **staff invitations** (AUTH-03, V1.1 — `tenant.identity.invite` +
`tenant.member_invited`), and the ~70 proposed post-V1 keys in `registry.md`'s
design-level sections (SUP/CRM/BIL/AFF/CMS/CMP/MIG/JRN/EDU/CHT/DVP/TRD/PLT/CS), each
freezing with its module.

---

*Navigation: [02 — AUTH](02-identity-access.md) (binding design) ·
[04 — GW](04-gateway-events.md) §3.1 (chain order) ·
`contracts/permissions/registry.md` (keys) ·
`contracts/permissions/roles.yaml` (bindings) ·
`contracts/permissions/matrix.md` (generated views) ·
[44 — fourth pass](44-auth-multitenancy-review.md) (D14–D18) ·
[45 — fifth pass](45-auth-contract-hardening.md) (G34–G45, D19–D24) ·
[47 — The Multi-Tenancy Model](47-multi-tenancy-model.md) (the isolation/lifecycle companion).*

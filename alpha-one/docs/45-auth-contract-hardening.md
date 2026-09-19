# 45 — Auth contract hardening: Fifth-Pass Review

> Fifth pass on the identity stack, 2026-09-19, after `docs/44`. Scope: the
> authn + authz + multi-tenancy surface re-checked this time **against the contracts and
> the provisioning path** — the questions were: *does the token prove which tenant it is
> for? does the login path survive an email change? is every route's authorization
> declared and enforced? and is the IdP's own admin plane governed?*
>
> Method: `docs/02` read end to end (§3.1–3.5, §6.1, §7.1, §9, §10), then `docs/03`
> (tenant entity, provisioning saga), `docs/21` §14, `docs/28` (§3.1–3.4, §4), `docs/06`,
> `docs/43`, `contracts/permissions/registry.md` + `roles.yaml`,
> `contracts/02-AUTH.openapi.yaml`, `contracts/errors/taxonomy.md`, and a scripted audit of
> **every V1 operation's `x-permission`** across `contracts/*.openapi.yaml`. Findings
> `G34`–`G45`.
>
> Status legend: **FIXED** (closed in this pass) · **DECIDED** (owner answered, applied)
> · **OPEN** (carries a decision row).
>
> Requirement coverage: a cross-cutting **review artifact**, not a module doc — it claims
> no PRD rows of its own; the doc/contract changes it drives are listed in §5.

## 1. Summary

| # | Finding | Severity | Resolution |
|---|---|---|---|
| G34 | **The token did not prove which tenant it was for.** `tenants` had no OIDC client/application binding, so `aud` could not be checked per tenant; docs/02 said "one project + OIDC application" instance-wide while docs/03's saga created a project *per org*; a tenant-A token was accepted on tenant-B's host (both are "tenant realm") | **High** | **FIXED / DECIDED (D19)** — one project + application **per tenant org**; `tenants.idp_client_id` (+ secret ref); `/session` requires `aud` == that tenant's client id and the org claim when present; `auth_sessions` is bound to the resolved tenant; new `auth.tenant_mismatch` (§2, §3.1) |
| G35 | **`identity_key` was the mutable join key** — `AUTH-29` rewrote it on email change, which silently creates a second identity for one person and moves the `AUTH-36` merge anchor; the old address stops resolving | **High** | **FIXED / DECIDED (D20)** — `identity_key` = hash of the **first verified email**, immutable; new `identity_emails` table (`email_hash UNIQUE`) is the match key for `/session`, `idp-sync` and merges; retired rows kept so an old address still resolves (§3.1, §9) |
| G36 | **Cross-org auto-link trusted an undefined "verified email"** and had no abuse control: anyone able to create a matching email at a second org could attach to an existing identity (identity poisoning), silently | **Medium** | **FIXED / DECIDED (D21)** — auto-link requires `email_verified` in the token **and** ZITADEL's user email state = verified; unverified → separate identity + merge task; every cross-org link writes a **CRITICAL** audit event and notifies the existing org's admins (§3.1) |
| G37 | **SSO group→role mapping was contradictory:** decision P3 (AUTH-24/25 in V1) implied directory-driven roles, the saga's step 3a said "map directory groups → roles", and the registry advertised a viewable map — while the ratified model assigns roles ourselves; the `invited → active` membership transition was undocumented | **Medium** | **FIXED / DECIDED (D22)** — group→role mapping is **out of V1** (SSO users are assigned roles by us at onboarding); docs/03 step 3a + registry wording corrected; lifecycle documented (`user.human.added`/invite → `invited`; first `/session` → `active`) |
| G38 | **No V1 step-up existed** although `payout.approve` requires a factor assertion < 5 min (ABAC), `authz.step_up_required` was already in the taxonomy, and the only planned step-up surface (AUTH-30) is V2 | **Medium** | **FIXED / DECIDED (D23)** — V1 uses hosted re-auth (`prompt=login&max_age=300`); the API enforces `auth_time` ≤ 5 min on the payout keys and returns `authz.step_up_required`; the API-owned surface stays V2 (§3.2) |
| G39 | **ZITADEL's own admin plane was ungoverned** — who holds `IAM_OWNER`, whether the Console/Admin API is reachable, and what the IdP break-glass is were all unstated while our whole authz model assumes the IdP is trusted | **Medium** | **FIXED / DECIDED (D24)** — admin plane internal-only (Cloudflare Access); exactly two named `IAM_OWNER` holders (or one + sealed emergency credential); quarterly access review; IdP role grants mirrored into our audit stream (§3.1, docs/06 §3.6) |
| G40 | **A password change did not kill other sessions.** The hosted-login flow never touches our projection, and the `idp-sync` action map had no credential-change row — so a stolen session survived exactly the action a user takes to defend themselves | **Medium** | **FIXED (default)** — `idp-sync` maps `user.human.password.changed` + MFA-factor events to *revoke every other session of the identity* (CRITICAL audit); also covers the staff forced reset (docs/43 §4) |
| G41 | **Route → permission was not enforced as a contract:** 24 of 61 V1 operations carried no `x-permission`, and nothing checked that a declared key existed in the policy set | **Medium** | **FIXED (default)** — every V1 op now declares a registry key **or** an explicit keyless marker (`self` = own-data, `none` = public/signature-authenticated); `scripts/verify_roles.py` fails the build otherwise (gate 13) |
| G42 | `platform:support` was advertised as "read-assist" in V1 while cross-tenant assist (CON-27) is V2 and AUTH-16 forbids tenant-realm action for platform roles | Low | **FIXED (default)** — wording corrected in docs/21 §2, `roles.yaml` and the registry; the V2 capability is named as V2 |
| G43 | **The V1 staff onboarding/role-management path was unstated** (AUTH-03 is V1.1, `tenant.identity.*` is V2): how does a new staff member get an identity and a role? | Low | **FIXED (default)** — a written V1 runbook (docs/06 §3.6): ZITADEL user → MFA → `identities` row → Casbin grant from `roles.yaml` (`verify_roles.py --seed`) → audit; offboarding in reverse |
| G44 | **No retention policy for auth artifacts** — `auth_sessions` rows carry IP/UA/geo, revoked rows accumulate, and the deny-set/backup-code lifetimes were never stated as a retention class | Low | **FIXED (default)** — new S2b class in docs/28 §4: IP/UA/geo scrubbed at 90 days (row kept for the audit trail), deny-set 24 h TTL, backup codes purged on use/offboarding |
| G45 | **The IdP's availability posture was implicit** — what happens to authenticated traffic when ZITADEL is down, and what login/revocation numbers we actually promise, were never stated | Low | **FIXED (default)** — explicit posture table in docs/06 §3.5 (login ≥ 99.5 %/mo; `/session` p95 < 300 ms; existing tokens keep validating for the JWKS cache lifetime; revocation p95 ≤ 60 s / worst case ≤ 15 min) |

**Severity mix:** 2 High, 6 Medium, 4 Low — all closed in-pass (6 by decision, 6 by default).

## 2. Decisions D19–D24 (owner answers, 2026-09-19)

| ID | Gap | Decision (option A in every case) |
|---|---|---|
| **D19** | G34 | One ZITADEL project + OIDC application **per tenant org**; `tenants.idp_client_id` stored (client secret in the tenant secret store, referenced by `tenants.idp_client_secret_ref`); every `/session` requires `aud` == that tenant's client id and checks the org claim when present; sessions are bound to the resolved tenant, so a token presented on another tenant's host is refused. |
| **D20** | G35 | `identity_key` = hash of the **first verified email** and never moves; new `identity_emails(identity_id, email_hash UNIQUE, email, is_primary, verified_at, retired_at)` is the match key for `/session`, `idp-sync` and `AUTH-36` merges; an email change adds a row and flips `is_primary`, the old row is retained. |
| **D21** | G36 | Cross-org auto-link requires a verified email (token `email_verified` **and** ZITADEL user state = verified); unverified → separate identity + merge task; every cross-org link writes a CRITICAL audit event and notifies the identity's existing org admins. |
| **D22** | G37 | SSO directory group→role mapping is **out of V1**; roles are assigned by us at SSO onboarding (later via platform/ADM actions); docs/03 step 3a and the registry wording corrected; the membership lifecycle (`invited` → `active`) documented. |
| **D23** | G38 | V1 step-up = hosted re-auth from the web tier (`prompt=login&max_age=300`); the API enforces `auth_time` freshness ≤ 5 min and returns `authz.step_up_required` when stale; AUTH-30's API-owned surface stays V2. |
| **D24** | G39 | ZITADEL admin plane private (internal network / Cloudflare Access only); exactly two named `IAM_OWNER` holders with mandatory MFA — or one owner plus a sealed emergency credential in the ops vault — plus a quarterly access review and IAM role-grant audit (the CON break-glass pattern). |

## 3. What changed, by finding

### 3.1 Tenant binding, identity join, SSO roles, admin plane (docs/02, docs/03)

- **docs/02 §2** — the ZITADEL mapping now reads *one Organization per tenant, one
  project + OIDC application per tenant org* (`tenants.idp_client_id`), and the
  two-realms bullet gains the per-tenant audience rule: the tenant is resolved from the
  request domain first, and the token must name that tenant's application (`aud`) and org.
- **docs/02 §3.1** — `identity_key` is documented as immutable, with `identity_emails` as
  the match key and the 3-path resolution table (`/session`, `idp-sync`, re-link) updated;
  the cross-org verified-email gate (G36) is stated with its audit/notification rule.
- **docs/02 §3.2** — the `/session` materialisation steps now include the audience check,
  the tenant-bound session row, and the `invited → active` transition; the credential-change
  session kill (G40) and the V1 step-up flow (D23) are written next to the session rules.
- **docs/02 §3.1 (platform realm)** — platform-realm governance (D24) and the V1 staff
  onboarding runbook (G43) are stated where the role catalog lives.
- **docs/02 §6.1** — new `auth.tenant_mismatch` (403); `/session`'s V1 error cell updated.
- **docs/02 §9** — `identities.identity_key` comment (immutable), `identity_emails` DDL,
  `tenants` binding columns, membership lifecycle comment.
- **docs/03 §3.5** — saga steps 3/3a: write `idp_client_id` (secret → secret store); SSO
  registration **without** group→role mapping; the tenants DDL gains `idp_client_id` +
  `idp_client_secret_ref`; the secret inventory gains the per-tenant OIDC client secret
  (180 d rotation); the AUTH integration row reflects all of it.

### 3.2 Contract coverage (G41)

`contracts/*.openapi.yaml` — 24 V1 operations gained an explicit permission value:
self-actions (`POST /v1/auth/session`, `/password`, `/2fa/backup-codes`, `/mfa/enrollment`,
`GET /mfa/status`, `POST /logout`), trader own-scope routes (accounts, payouts, catalog,
checkout session create/cancel, retry-payment, receipt), the two provider webhooks
(`none` — signature-authenticated), and the console login/logout pair. The convention is
documented in `contracts/permissions/registry.md`, and `scripts/verify_roles.py` now
enforces: **no V1 operation without a declared permission; no declared key that is not
bound in `roles.yaml`**. Gate 13.

### 3.3 Defaults adopted without a decision (G40, G42–G45)

| Finding | Where it landed |
|---|---|
| G40 credential-change session kill | docs/43 §4 action map + docs/02 §3.2 |
| G42 `platform:support` wording | docs/21 §2, `roles.yaml`, registry |
| G43 staff onboarding runbook | docs/06 §3.6 + docs/02 §3.1 |
| G44 auth-artifact retention (S2b) | docs/28 §4 |
| G45 availability posture | docs/06 §3.5 |
| G41 contract gate (mechanism) | `scripts/verify_roles.py`, registry notes, docs/99 gate 13 |

## 4. Verification

| Check | Result |
|---|---|
| V1 operations with a declared permission | **61/61** (30 distinct keys over 38 ops, 19 `self`, 4 `none`) |
| Declared keys bound in `roles.yaml` | 30/30 used keys (6 bound keys have no V1 route yet — 2 sensitive-data review keys and 4 platform/console keys that attach to post-V1 surfaces; reported by the verifier as a note, not an error) |
| `verify_roles.py` (YAML ⇄ registry ⇄ inheritance closure ⇄ docs/02 §3.1 render) | green |
| Phase-0/1 gates added | docs/99 gates 12 (per-tenant audience), 13 (route→permission), 14 (step-up freshness) |
| Workbook / registers / pack | unchanged by this pass (no PRD row added or changed) |

## 5. Change map

| Artifact | Change |
|---|---|
| `docs/02-identity-access.md` | per-tenant audience + session binding (G34); immutable `identity_key` + `identity_emails` (G35); verified-email link gate (G36); step-up + credential-change kill (G38/G40); platform-realm governance + staff runbook (G39/G43); `auth.tenant_mismatch`; §9 DDL |
| `docs/03-tenant-management.md` | saga steps 3/3a; `tenants.idp_client_id` / `idp_client_secret_ref`; SSO roles manual (G37); secret inventory row |
| `docs/06-devops-deployment.md` | §3.5 availability posture (G45); §3.6 V1 runbooks (G43/G39) |
| `docs/11-payout-system.md` | step-up mechanism named on the approve flow (G38) |
| `docs/21-console.md` | `platform:support` wording (G42) |
| `docs/28-security.md` | S2b auth-artifact retention (G44) |
| `docs/43-idp-deprovisioning.md` | credential-change kill row; `identity_emails` in the re-link path (G40/G35) |
| `docs/99-development-phases.md` | gates 12–14; fifth-pass artifact reference |
| `contracts/*.openapi.yaml` (7 files) | V1 `x-permission` completed (G41) |
| `contracts/errors/taxonomy.md` | `auth.tenant_mismatch` |
| `contracts/permissions/registry.md` | marker convention + support/SSO wording |
| `contracts/permissions/roles.yaml` | `platform:support` description |
| `scripts/design-questions.json` | D19–D24 |
| `scripts/verify_roles.py` | V1 route→permission check |

## 6. Residual risk & open items

1. **Step-up depth.** V1 enforces exactly one freshness rule (payout approval). Anything
   more granular waits for AUTH-30 (V2) — the *semantics* (`auth_time` ≤ 5 min,
   `authz.step_up_required`) are fixed now so V2 does not re-litigate them.
2. **Extended surface is not contract-annotated.** Post-V1 operations carry no
   `x-permission` yet, so the verifier can only report bound keys with no V1 route; each
   extended route gets its annotation at its own contract freeze.
3. **ZITADEL's Actions v2 remains vetoed** as an execution path (docs/43 §2, §7); the
   `idp-sync` pull consumer is the only mechanism, which is why G40 rides on it rather
   than on a hosted-login hook.
4. **Zero-downtime SSO.** Step 3a still assumes a metadata exchange with the tenant's IdP;
   `IdP metadata errors` retry path is manual (documented in the saga), unchanged by this
   pass.
5. **Admin-plane controls are operational, not code** (G39): the two-owner rule and the
   quarterly review are runbooks (docs/06 §3.6) with audit evidence, and their first
   execution is a Phase-0 checklist item in docs/34 §9.

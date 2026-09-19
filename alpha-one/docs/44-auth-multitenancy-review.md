# 44 — AUTH / AuthZ / Multi-Tenancy: Fourth-Pass Review

> Fourth pass on the identity stack, 2026-09-19, after `docs/42` (gap analysis) and
> `docs/43` (deprovisioning). Scope this time: **the whole authn + authz + multi-tenancy
> surface checked against itself** — module docs, contracts, generated artifacts and the
> decisions — asking one question: *could a team build this as written without hitting a
> contradiction or an authorization hole?*
>
> Method: `docs/02` read end to end, then every cross-reference checked — `docs/01`
> §4/§7.8, `docs/03` §5, `docs/04` §3.1 (GW chain), `docs/21`, `docs/28` §3.3,
> `docs/35` §5.1, `contracts/permissions/registry.md`, `contracts/api/auth.md`,
> `contracts/errors/taxonomy.md`, docs/43. Findings `G21`–`G33`.
>
> Status legend: **FIXED** (closed in this pass) · **DECIDED** (owner answered, applied)
> · **OPEN** (carries a decision row).
>
> Requirement coverage: a cross-cutting **review artifact**, not a module doc — it claims
> no PRD rows of its own; the doc/contract changes it drives are listed in §9.

## 1. Summary

| # | Finding | Severity | Status |
|---|---|---|---|
| G21 | `identities.idp_user_id` is a single column while the agreed model needs one identity ↔ **many** ZITADEL users (one per org). Deprovisioning (`idp-sync`) would fail silently for exactly the multi-tenant users it must protect | **High** | **FIXED / DECIDED (D13)** — §3 |
| G22 | **Role → permission bindings** were undefined (31 registry keys, 6 tenant + 5 platform roles): `authorizer.Check` had no policy to evaluate. Registry carried 4 decision-shaped TODOs | **High** | **FIXED / DECIDED (D14)** — §4 |
| G23 | **Casbin policy storage, reload and audit unspecified** — no table DDL, no reload path, no policy-change audit, and no fail-closed boot rule | **High** | **FIXED / DECIDED (D15)** — §4 |
| G24 | **RLS exemption model missing.** Fail-closed RLS breaks every path that reads across tenants (relay, audit/ledger appliers, ANA, CON, `idp-sync`) and the pre-tenant-context lookups; **console sessions** (`auth_sessions.tenant_id IS NULL`) would be invisible | **High** | **FIXED / DECIDED (D16)** — §5 |
| G25 | `identities.realm` is a single column — a platform staffer who also trades cannot exist; the second login would overwrite the realm | **Medium** | **FIXED** — §6.1 |
| G26 | **Refresh-token ownership contradiction:** P2 says "no own rotating-refresh stack", docs/02 §3.2 implemented reuse detection ourselves and the schema carried `refresh_hash` / `prev_refresh_hash` | **Medium** | **FIXED / DECIDED (D17)** — §6.2 |
| G27 | **API keys:** §3.5 and blueprint step 7 build V1 primitives, while the GW chain, contract and endpoint table all say keys are V2 with no surface | **Medium** | **FIXED / DECIDED (D18)** — §7 |
| G28 | **Service-to-service authentication absent in V1** while an `internal` route group exists; nothing stated that internal routes bypass the edge or how a service authenticates | **Medium** | **FIXED** — §7 |
| G29 | **No identity/membership status check in the GW chain** — steps 2–4 cover tenant → JWT → keys, yet the error codes and tests assume a suspension check | **Medium** | **FIXED** — §7 |
| G30 | **Two platform role catalogs** (docs/02 `platform:super_admin/admin/ops/billing/readonly` vs docs/21 `platform:owner/ops/support/finance`) | **Low** | **FIXED** — §4.3 |
| G31 | The impersonation token's `readonly` claim (docs/21) contradicted P4's "no authorization facts in the token" | **Low** | **FIXED** — §7 |
| G32 | `idp-sync` had no routing rule for platform-org events or an unknown `resource_owner` | **Low** | **FIXED** — §8 |
| G33 | ZITADEL's `force_mfa` was described as unusable for staff; on the **platform org** (all members are staff) it is exactly right and was unmentioned | **Low** | **FIXED** — §8 |

Plus two bookkeeping corrections: the registry counts **31** V1 keys while docs/02 said
30 (now 36 with the three platform keys promoted and two AUD-23 keys added), and
`docs/37`'s design-question header was under-reporting open rows (fixed in `7151f95`).

## 2. Decisions this pass produced

| # | Question | Answer |
|---|---|---|
| **D13** | Identity ↔ IdP user cardinality | **`identity_idp_links`** (1 identity ↔ N ZITADEL users); `idp_user_id` demoted to a pointer — §3 |
| **D14** | Role × permission key bindings | **Ratify now**: `contracts/permissions/roles.yaml` is the machine-readable source; Casbin seeded from it; registry TODOs closed — §4 |
| **D15** | Casbin policy storage / reload / audit | **Postgres `casbin_rule` + Redis pub/sub watcher + fail-closed boot + policy-version audit** — §4 |
| **D16** | RLS exemption for cross-tenant paths | **Named `app_platform` role (BYPASSRLS)** for enumerated services + explicit tenant filters + CI guard; pre-auth lookups through `SECURITY DEFINER` accessors — §5 |
| **D17** | Refresh-token rotation ownership | **ZITADEL owns** rotation + reuse detection; our rotation columns and logic are removed; deny-set stays ours — §6.2 |
| **D18** | V1 API-key scope | **Internal primitives only** — no tenant-facing surface until AUTH-21 — §7 |

They are recorded in `docs/37` §Design-review questions (D13–D18) with owners.

## 3. Identity ↔ IdP user cardinality (G21) — FIXED (D13)

**The defect.** `docs/02` §3.1 says the platform model is "one person = one identity"
even though ZITADEL stores **one user per organization** — so a trader who registers at a
second tenant holds **two** ZITADEL users against **one** `identities` row, "matched by
`identity_key`". But:

- `identities.idp_user_id TEXT UNIQUE` can hold only one of them;
- `docs/02` §3.2 materialises the session by *"upsert `identities` by `idp_user_id`"*;
- `docs/43` §3 resolves IdP events by *"aggregate_id → `identities.idp_user_id`"*.

So the second login overwrites the first user id, and from then on the **first org's**
events — including `user.deactivated` and `user.removed` — resolve to no identity and land
in the DLQ. Deprovisioning would work for single-tenant users and silently fail for
multi-tenant ones, which is the opposite of the intended risk profile. The design docs/43
introduced inherited the flaw; this pass is what caught it.

**Model (binding).** One identity, many IdP links, one link per (identity, org):

```sql
CREATE TABLE identity_idp_links (
  idp_user_id   TEXT PRIMARY KEY,              -- ZITADEL user id (sub); never reused by ZITADEL
  identity_id   ULID NOT NULL REFERENCES identities(id),
  idp_org_id    TEXT NOT NULL,                 -- ZITADEL org (resource owner) of this user object
  tenant_id     ULID REFERENCES tenants(id),   -- NULL for the platform org (`alpha1-platform`)
  state         TEXT NOT NULL DEFAULT 'active'
                CHECK (state IN ('active','retired')),
  first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_seen_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  retired_at    TIMESTAMPTZ,
  UNIQUE (identity_id, idp_org_id)             -- one live user object per org per identity
);
CREATE INDEX idx_idp_links_identity ON identity_idp_links(identity_id) WHERE state = 'active';
```

`identities.idp_user_id` becomes a **denormalised pointer to the most recently used link**
(read convenience for joins, refreshed on login) — it is no longer the join key. The
column list keeps `idp_org_id` as the *current* org for the same reason.

**Resolution rules (binding, all three paths).**

| Path | Rule |
|---|---|
| Session materialisation (`POST /v1/auth/session`) | link lookup by `sub` → identity; miss → `identity_key` match on the verified email → attach link; miss → create identity + link. A link is written for **every** `(identity, org)` pair the person logs in from |
| `idp-sync` event mapping (docs/43 §3 step 2) | `aggregate_id` → `identity_idp_links` → identity. Unknown link → resolve by `identity_key` if the payload carries the email, else hold the cursor + alert (never guess) |
| Re-link after deletion (docs/43 §9) | the deleted user's link is set `retired` (its `idp_user_id` is the audit alias); a returning user gets a **new** link and never silently re-links to a closed identity — staff approval, re-KYC |

Platform staff: one link per staff user, `tenant_id NULL`, in the `alpha1-platform` org.

## 4. Authorization: bindings, storage, reload (G22, G23) — FIXED (D14, D15)

### 4.1 The binding table (D14)

`authorizer.Check(ctx, subject, action, resource)` had nothing to evaluate: 31 V1 keys,
a role catalog, and every mapping between them marked "TODO — needs owner decision".
There is now one machine-readable source, **`contracts/permissions/roles.yaml`**:

- **realms** — tenant (`firm:*`, `user:trader`) and platform (`platform:*`); a role holds
  keys of one realm only, and the realm is also carried by the token audience (AUTH-16);
- **role catalog** — 7 tenant + 5 platform roles with `inherits` (the Casbin `g` edges);
- **bindings** — every key with `scope` (`all` / `own` / `platform`), its effective role
  set, and any ABAC constraint that rides on it (step-up for `payout.approve`, the $500k
  owner flag for `account.manual_override`, audit-on-access for the two AUD-23 keys);
- **trader self-actions** — resolved as *declared keys with scope `own`* (AUTH-13 is
  satisfied, and the own-data ABAC matcher does the resource check);
- **provisional bindings** — the identity/SSO/SCIM keys get proposed holders now so the
  later freeze (docs/99 §12) is mechanical rather than a fresh decision.

Registry TODOs closed by this: role bindings; trader self-actions; **which key gates
sensitive-data access** → two new V1 keys, `kyc.document.read` and `payout.method.review`,
both audit-on-access per AUD-23; key naming → ratified as-is (`payout.read_queue` keeps
its name: the queue is a distinct resource, and renaming it would churn four artifacts for
no gain). The registry now counts **36 V1 keys** (31 + 3 platform promoted from the
provisional block + 2 new), and docs/02's stale "30 keys" is corrected.

### 4.2 Storage, reload and audit (D15)

```
boot   ──► load model.conf (from the binary, versioned in the repo)
       ──► load rules from Postgres `casbin_rule` at policy_version P
       ──► rules empty OR load error ──► FAIL CLOSED (deny all) + SEV-1 alert, no traffic
change ──► INSERT/UPDATE rows + bump policy_version + audit row
       ──► PUBLISH casbin:reload{version}
       ──► every api instance reloads; mismatch → deny + alert
```

```sql
-- standard Casbin table; `v0..v5` per the model, plus an audit-side version pointer
CREATE TABLE casbin_rule (
  id    BIGSERIAL PRIMARY KEY,
  ptype TEXT NOT NULL,          -- p (policy) | g (role inheritance)
  v0 TEXT, v1 TEXT, v2 TEXT, v3 TEXT, v4 TEXT, v5 TEXT
);
CREATE UNIQUE INDEX idx_casbin_rule ON casbin_rule (ptype, v0, v1, v2, v3, v4, v5);
CREATE TABLE authz_policy_versions (
  version    BIGINT PRIMARY KEY,
  applied_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  actor      TEXT NOT NULL,        -- who/what changed it (V1: migration or staff runbook, never an API)
  summary    TEXT NOT NULL         -- human-readable diff summary; the full delta is in audit_events
);
```

Rules: policies are **seeded by migration** from `roles.yaml` (V1 has no policy-CRUD
surface — AUTH-14/AUTH-03 are V2 — so every change is a reviewed deploy), every change
writes an `audit_events` row (AUD-01) with the diff, and **an empty or unloadable policy
set denies everything** and alerts — never allows. Reload is a Redis pub/sub message on
`casbin:reload`; a subscriber that misses the message re-syncs on the next request's
version check (version read is cached ≤ 30 s). `scripts/verify_roles.py` asserts the
YAML ⇄ seeded-rows equivalence and that the effective sets match `inherits`, so the file
cannot drift from the policy table.

### 4.3 One platform role catalog (G30)

`platform:owner` (docs/21/25/27) and `platform:super_admin` (docs/02) were the same role
under two names; `platform:admin` and `platform:billing` were names with no surface. The
catalog is now the five roles in `roles.yaml`: `platform:super_admin` ⊃ {`platform:ops`,
`platform:support`, `platform:finance`, `platform:readonly`}. The superseded names are
recorded in `roles.yaml` (`superseded_role_names`) and docs/21 CON-01 points at the
catalog rather than restating it.

## 5. Multi-tenancy and RLS (G24) — FIXED (D16)

**The defect.** `docs/02` §9 makes `tenant_memberships`, `auth_sessions` and `api_keys`
fail-closed on `current_setting('app.tenant_id')`. Three classes of query cannot work
under that policy as written:

1. **Cross-tenant consumers** — relay, ledger/audit appliers, ANA read models, CON
   aggregates and the new `idp-sync` all read or write rows belonging to many tenants;
2. **Pre-tenant-context lookups** — the session-by-id and API-key-by-hash lookups happen
   *before* a tenant is known (that is how the tenant gets known);
3. **Console sessions** — `auth_sessions.tenant_id IS NULL` for `is_console` rows, so a
   tenant policy hides them and console login/logout breaks.

**Model (binding).**

| Principal | DB role | Policy |
|---|---|---|
| Request paths (tenant-scoped) | `app_rw` | **RLS enforced, fail-closed**: every tenant-owned table has `ENABLE`+`FORCE ROW LEVEL SECURITY`, `USING`/`WITH CHECK` on `current_setting('app.tenant_id', true)`, set with `SET LOCAL` inside the transaction (PgBouncer txn mode safe) |
| Auth resolution (session by id, API key by hash, link by `idp_user_id`, console-session check) | `app_rw` via **`SECURITY DEFINER` accessors** | four named functions in the `auth` schema; they take the lookup key, return the minimal row, and are the only way to read those tables without a tenant context. `EXECUTE` granted to `app_rw`, not to application code paths that could widen it |
| Enumerated cross-tenant services (relay, ledger applier, audit applier, ANA updaters, `idp-sync`, CON read models) | `app_platform` | **`BYPASSRLS`**, used only by those services; their queries must still carry explicit `tenant_id` predicates — enforced by the CI grep-class check on new sqlc queries (docs/06) and review, because RLS is the backstop, not their isolation |
| Migrations / DDL | `migrator` | `BYPASSRLS`; never in application config; run as a discrete job |
| Analytics read models | `app_platform` (writes) / `app_rw` (reads) | `*_ro` tables carry `tenant_id` and are RLS-enforced for readers; the updater writes per tenant with context set, so no exemption is needed there |

`auth_sessions` policy is now explicit: tenant rows via `app.tenant_id`; console rows
(`is_console`) reachable only through the identity-scoped accessor. That is what "(tenant
rows)" in §9 always meant — it is now written as SQL intent rather than a parenthetical.

**Also corrected:** the RLS statement "every policy table" now enumerates its scope —
memberships, sessions, API keys, KYC documents/decisions, accounts/trades/payouts/audit
(the per-module tenant-owned tables), *not* `identities`, `identity_idp_links`,
`auth_backup_codes`, `tenants`, `casbin_rule` and the platform-scoped audit rows, which
are platform-owned and guard-only (identity-scoped accessors). Naming the exemption list
is the difference between a second layer and a false sense of one.

Negative tests extend `docs/35` §5.1: `app_rw` with no context → zero rows on every
tenant table; `app_rw` cross-tenant write → rejected by `WITH CHECK`; **`app_rw` reading
`auth_sessions` without context → zero rows** (console rows included) while the accessor
succeeds; `app_platform` works and is the only role that does; a migration on a
tenant-owned table succeeds under `FORCE RLS`.

## 6. Realm and token ownership (G25, G26)

### 6.1 Realm is per context, not per person (G25) — FIXED

`identities.realm` as a single value means a person cannot be platform staff **and** a
tenant member: the second login overwrites the column, and AUTH-16's separation assumes
staff hold no tenant membership. V1 posture (binding): **one realm per identity**, chosen
at first login, and a person who needs both uses **two identities with distinct emails**
— the platform realm is a working context, not a personal trait. The DB keeps
`identities.realm` with a `CHECK`, and a login from the other realm with a matching
`identity_key` is **refused** (`auth.realm_mismatch`, new code) instead of silently
flipping the column — an operator can then decide. When impersonation lands (V2, CON-07)
the cross-realm read path is explicit, audited and read-only, so it does not need a
dual-realm identity.

### 6.2 Refresh rotation is ZITADEL's (G26, D17) — FIXED

P2 chose "IdP-issued tokens accepted by our API … no own rotating-refresh stack", but
§3.2 kept our rotation logic and the schema carried `refresh_hash`/`prev_refresh_hash`.
The stack has one owner per concern:

| Concern | Owner | Our artefact |
|---|---|---|
| Access/refresh token issuance, rotation, reuse detection | **ZITADEL** (OIDC refresh with rotation; reuse revokes the token family) | none — `auth_sessions.refresh_hash` / `prev_refresh_hash` are **removed** from the schema |
| Immediate revocation | ours | Redis deny-set + `DeleteSession` / `RevokeAllMyRefreshTokens` |
| Session inventory + polling/step-up facts | ours | `auth_sessions` (`idp_session_id`, `idp_token_jti`, `amr`, `auth_time`, idle/absolute expiry) |
| Lifetime ceilings | ours, enforced in the IdP | instance OIDC settings, 900 s access/ID (docs/43 §6) |

`docs/02` §3.2's "reuse detection is implemented by us" sentence is corrected to point at
ZITADEL, keeping our reuse *response* (kill the family, CRITICAL audit) because the
`RevokeAllMyRefreshTokens` call and the session kill are ours.

## 7. Request path and scope fixes (G27, G28, G29, G31)

**Status check (G29).** The GW chain gains step 3.5, between authn and authz:

| Order | Check | Failure |
|---|---|---|
| 3.5a | tenant state (from the resolution in step 2) | `tenant.suspended` / `tenant.not_live` (code name corrected 2026-09-19, docs/47 M2 — `tenant.not_ready` was never registered) |
| 3.5b | identity state (`identities.status`) | `auth.account_suspended` (403) |
| 3.5c | membership state for `(identity, tenant)` — console realm skips this | `auth.membership_suspended` (403, new code) |

The resolution is cached in Redis for ≤ 5 s keyed by `(identity, tenant)`, and invalidated
by `user.suspended` / `user.activated` / membership events, so the suspension path stays
"≤ 1 s" (docs/03 §5.1). Order matters: tenant before identity before membership, so the
403 never leaks which layer failed for an unauthenticated probing caller (the tenant is
already public via the host).

**Service-to-service (G28).** Inbound `internal` routes: never routed through Cloudflare
(no edge route, no DNS), reachable only on the compose network; V1 authentication is a
**static per-service bearer token** (SOPS, 90 d rotation, one per service: web, workers,
relay) plus the tenant via `X-Tenant-Id` (the documented internal path, already in
`docs/02` §3.4); every internal call is logged with `correlation_id` and the service
identity. HMAC-signed requests and mTLS are V2 — documented as the upgrade path, not
required for V1. Worker→DB access uses the roles in §5, not this token.

**API keys (G27, D18).** V1 ships the primitives only (`api_keys` table + hash/scope/
revoke helpers) for service tokens and the future AUTH-21 surface; **no tenant-facing
endpoint exists in V1**, and the GW chain's note ("API keys are V2") is corrected to say
so. Any machine integration for the cutover tenant uses tenant integration secrets
(TEN-11) until AUTH-21 ships.

**Tokens carry context, never authority (G31).** Rule now stated once: a token may carry
*context* facts — `sub`, audience/realm, `amr`, `auth_time`, session id, and (V2) an
impersonation reference — and must never carry roles, permission keys or an authorization
verdict. The impersonation `readonly` behaviour is therefore validated server-side against
the impersonation session record, not trusted from a claim; docs/21's wording is corrected
to that rule and the impersonation row is re-tagged V2.

## 8. Operational and consistency fixes (G32, G33)

**`idp-sync` routing (G32).** Routing is now explicit (docs/43 §4): events whose
`resource_owner` is the platform org → the platform-staff path (link `tenant_id NULL`,
`platform.identity.admin`-owners notified); a `resource_owner` that matches no
`tenants.idp_org_id` and is not the platform org → **hold the cursor + alert** (never
guess a tenant, never drop); a tenant in `deleted`/`archived` → apply to the membership
row and audit, since the tenant-termination saga already suspended its identities.

**Staff MFA at the IdP (G33).** ZITADEL's `force_mfa` cannot express "staff only" *inside*
a tenant org — but the platform org contains nothing but staff, so it now carries
`force_mfa = true` as the IdP-side layer behind our `amr` gate (defence in depth: a token
that reaches our API without a factor is refused either way). Tenant orgs keep
`force_mfa` off in V1 (traders are AUTH-10/V2).

## 9. Where this lands in the build

| Artifact | Change |
|---|---|
| `contracts/permissions/roles.yaml` | **New** — the ratified binding source (D14) |
| `contracts/permissions/registry.md` | TODOs closed; 3 platform keys promoted to V1; 2 AUD-23 keys added; 36-key count; pointer to `roles.yaml` |
| `docs/02` §3.1/§3.2/§3.3/§9/§16 | Identity links + resolution rules; realm rule; refresh ownership; Casbin tables + fail-closed boot; RLS principal table; `force_mfa` on the platform org; blueprint steps (seeding, accessors, keys) |
| `docs/04` §3.1 | GW steps 3.5a–c; internal-route exposure + service token; API-key note corrected |
| `docs/01` ADR-14 / §7.8 | Policy storage + reload + fail-closed boot; `app_platform` role |
| `docs/21` | CON-01 role names unified; impersonation row re-tagged V2 with the context-claim rule |
| `docs/28` §3.3 | RLS scope + exemption list + the three DB roles |
| `docs/35` §5.1 | Link resolution, realm mismatch, status-matrix, RLS platform/accessor negatives, Casbin fail-closed boot, role-seeding equivalence |
| `docs/34` §9, `docs/99` | Phase-0/1 gates: role seeding + fail-closed drill, accessor tests, platform-role migration |
| `docs/43` | §3/§4/§9 use `identity_idp_links`; routing rows (§8 above) |
| `docs/37` + `scripts/design-questions.json` | D13–D18 recorded with owners |
| `scripts/verify_roles.py` | **New** — asserts `roles.yaml` ⇄ seeded Casbin rows ⇄ rendered tables |

## 10. Carried forward (unchanged, for completeness)

The residual items already recorded elsewhere still stand and are **not** re-litigated
here: the ZITADEL org-scope regression (#11869) and the two Phase-0 spikes it forces
(docs/02 §3.1, docs/99 gate 1); the `amr` shape spike (gate 2); the residual IdP event-store
PII and its DPO review (AUTH-35, D9); the self-service deletion posture awaiting the same
DPO review (D12, docs/43 §8); password-import posture (D7); and `AUTH-10/18/19/21/30/34`
staying V2 by scope. Every one of those carries an owner and a gate already; this pass
added no new deferred work — it removed the three things that could not be built as
written.

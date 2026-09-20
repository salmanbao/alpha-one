# 03 — TEN: Tenant Management

> Covers PRD module **TEN** (45 requirements). Tenant lifecycle, white-label,
> entitlements, limits, and the configuration inheritance chain. The consolidated
> developer-facing multi-tenancy specification (isolation layers, per-tenant identity,
> lifecycle semantics) is [47 — The Multi-Tenancy Model](47-multi-tenancy-model.md).

## 1. Purpose & scope

TEN owns **the tenant as an entity**: its lifecycle, its brand, its configuration,
its limits, and its entitlements (which modules/features it has enabled). It is the
"central nervous system" that every other module reads. In V1 there are 1–5 tenants
and tenants are created **by Alpha One staff in the Platform Console** — there is no
self-serve signup until V3 (`BIL-18`), but the provisioning pipeline is built as if
signup existed (same steps, different trigger).

Requirement coverage: `TEN-01,02,03,08,11,12,15,18,42` (V1.0: registry, resolution, lifecycle, entitlements, suspension, storage prefix, subdomain validation) +
`TEN-04,05,06,07,09,10,13,14,16,17,19,20,21,22,23,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,41,43,44,45` (V2.0: white-label, custom domains, flags, settings, onboarding, quotas) +
`TEN-24` (V3.0: data residency).

## 2. Architecture

```
CON (staff) ──create/suspend/upgrade──► TEN domain (api package)
                                              │  provisioning orchestrator (saga in workers)
                                              ▼
        steps: validate → create record → provision identity (AUTH org)
               → branding defaults → domain (subdomain now / custom V1.1)
               → broker group defaults (BRG-12) → default rule packs (EVL)
               → feature flags (Flipt) → welcome invite (NOT) → activate
                                              │
        consumers of tenant.config/limits/branding:
        GW (resolution, quotas, entitlement gate) · web (theme) · NOT (sender,
        templates) · DOC (branding on PDFs) · BRG (server groups) · EVT (webhooks)
```

- **Config inheritance** (platform default → plan/tier → tenant override): stored as
  a **single resolved row per tenant** (denormalized on write), never computed on
  read. Changing a platform default does NOT rewrite tenants; the tenant's row wins.
- **Entitlements** = `tenant_entitlements` rows (module, enabled, limit overrides) +
  Flipt flags for code-level kill switches (`TEN-10`, `CON-31`). GW reads
  entitlements per route group; Flipt decides per feature. `tenants.features`
  is a **denormalised snapshot, not a second source of truth**: it is written
  only inside the same transaction as `tenant_entitlements` by the
  entitlement-change path, and no authorization decision ever reads it (GW
  step 6 reads the rows; the snapshot exists for cheap renders/exports).
- **White-label** is data, not code: `tenants.branding` JSONB → compiled to CSS
  variables + email template brand at render time (§3.4).

## 3. System design

### 3.1 Tenant entity (core fields)

```
tenants
  id (ULID) · slug (unique, = subdomain) · parent_id (NULL, ADR-2 door)
  firm_name · legal_entity_name · registration_number · tax_id
  jurisdiction (ISO 3166-1 alpha-2) · kyb_status (pending|verified|failed) · kyb_verified_at
  primary_contact {name, email, phone} · support_email
  status (state machine §5) · plan (manual contract ref in V1; BIL subscription V3)
  limits JSONB · settings JSONB · branding JSONB · features JSONB (denormalized)
  data_region (metadata only in V1 — everything is EU-Hetzner)
  created_by (platform staff id) · timestamps · suspended_at · suspension_reason
```

**Limits model** (enforced at write-time, not after): `max_traders`,
`max_active_accounts` (broker accounts), `max_challenges_per_month`,
`max_funded_capital`, `api_rate_limit_rpm`, `storage_quota_gb`,
`data_retention_days`, `max_admin_users`, `max_custom_rules`. Enforcer: a small
`limits.Assert(tenant, metric)` call in the owning domain's create-path (e.g. LCC
checks `max_active_accounts` before provisioning a broker account); over-limit →
`tenant.limit_exceeded` with the metric named (code name corrected 2026-09-19,
docs/47 M3 — the row formerly read `ten.limit_exceeded`).

### 3.2 Tenant resolution (order binding — see 01 §5)

custom domain → subdomain (`{slug}.alpha1.io`) → internal `X-Tenant-Id` (service
tokens only) → API-key-embedded (wins over headers). Negative lookups are cached
(60 s) so unknown-subdomain probing doesn't hammer PG. Status check in the same
call: `suspended` tenant → 403 for all its traffic (`GW-23`); the per-state
behaviour is the matrix in §5.1.

**Subdomain rules (TEN-42, review G8).** Format: 3–30 chars, `[a-z0-9-]`, no leading
or trailing hyphen, no double hyphen, must not be all-digits; the input is
lower-cased and trimmed, and a non-ASCII/punycode attempt is an error (no
transliteration — homograph protection). Reserved list (never creatable, checked in
addition to `tenant.subdomain_taken`): `www, admin, api, app, console, login, id,
auth, sso, status, docs, help, support, mail, email, cdn, static, assets, billing,
pay, payments, bridge, engine, relay, test, staging, demo, beta, internal, alpha1,
alphaone`. Availability is checked against `tenants.slug` **and** the reserved list
in one call (`GET /v1/tenants/subdomain-check`), with DNS only consulted at
provisioning. **V1: subdomains are immutable** — a change would break cookies, email
links and webhooks, so `TEN-43` (V2) ships it as an explicit migration with a
redirect window rather than an edit field. **`tenants.slug` is the subdomain's single
source of truth** (decision D, docs/47 §15): resolution reads the slug for
`{slug}.alpha1.io` and never `domain_mappings`; that table is for **custom domains
only** (its `subdomain` type value is dropped at the V1.1 custom-domain freeze).

### 3.3 Configuration surface (settings JSONB, curated keys)

```
trading:   { default_leverage, supported_symbols (override of broker group),
             broker_group (→ BRG-12) }
challenge: { default_phases, auto_fund_on_pass (bool — V1 default per tenant) }
risk:      { restricted_countries[], require_kyc_before_funding }
payout:    { min_amount_cents, currency, approval_mode: manual|auto,
             min_trades, first_payout_delay_days, methods[] }
kyc:       { required: true, provider: "veriff", reverify_days: 365 }
comms:     { email_from, email_reply_to, language: "en", telegram_channel (V2) }
legal:     { terms_url, privacy_url, risk_disclosure_url, refund_policy_url }
geo:       { allowed_countries[] (or null = all), restricted_countries[] }
```

Every key has a **schema (JSON Schema in `contracts/tenants/tenant-settings.schema.json`)**
validated on write; unknown keys rejected. The full key reference lives in that file.

### 3.4 White-label engine

`branding` JSONB: `logo {primary, dark, favicon, app_icon, email_header}` (R2
object keys, tenant-prefixed), `colors {primary, primary_dark, accent, background,
surface, text, text_secondary, error, warning, success, info, profit, loss}`,
`typography {primary_font, mono_font}`, `layout {sidebar, radius, density}`,
`social {website, telegram, discord, instagram, ...}`, `legal {company_name,
terms_url, privacy_url, risk_disclosure_url, refund_policy_url, cookie_policy_url}`,
`custom_css` (≤ 20 KB, sanitized — styles only: no @import, no url() to foreign
origins, no JS-bearing `srcdoc`).

Resolution: `base theme → plan overrides → tenant branding` deep-merged; compiled to
`:root` CSS custom properties (web) and injected into email/PDF templates (NOT,
DOC). Admin preview in ADM (`ADM-19` settings pages). No JS theme injection.

### 3.5 Provisioning pipeline (saga, `provisioning_jobs` table)

| # | Step | Compensate | Fails → |
|---|---|---|---|
| 1 | validate application (KYB basics, sanctions list check, jurisdiction) | — | `tenant.provisioning_failed` |
| 2 | create `tenants` row (`status=provisioning`), slug unique | delete row | idempotent retry |
| 3 | provision ZITADEL organization + **project/OIDC application for the tenant** + owner membership (Admin API), store `idp_org_id` **and `idp_client_id`** (that application's audience — review G34 / decision D19; its secret goes to the tenant secret store, never to `tenants`); per-org login policy, password policy, lockout and branding defaults, org domain = `{slug}.alpha1.io`, `mfa_init_skip_lifetime` set (staff-MFA nudge, docs/02 §3.2) | destroy org | retry ×2 |
| 3a | (only when the tenant contracted SSO — AUTH-24/25) register the org's external IdP (SAML/OIDC metadata), attach it to the org, **assign the SSO users' roles ourselves** (ADM action at onboarding), issue the SCIM bearer token into the IdP. **No group→role mapping in V1 (review G37 / decision D22):** directory groups drive sign-in and provisioning only; the membership lifecycle is `user.human.added` → `invited`, first `/v1/auth/session` → `active` (docs/02 §3.2), and group→role mapping is a V2 capability (AUTH-24 extension) | revoke token, remove IdP | retry; manual on metadata errors |
| 4 | branding defaults + legal defaults | delete rows | retry |
| 5 | subdomain DNS (Cloudflare API: `CNAME {slug}.alpha1.io`) | delete record | retry; custom domain = V1.1 step |
| 6 | default broker group ref (BRG-12) + default rule packs (EVL seed) | delete refs | retry |
| 6b | seed the tenant chart of accounts (LED CoA template, docs/05 §3.1 — accounts + platform-account links; idempotent) | delete seeded rows | retry |
| 7 | Flipt flags for plan | reset flags | retry |
| 8 | welcome invite email to owner (NOT) | — (safe to resend) | retry ×3 |
| 9 | `status=onboarding` → checklist starts (ADM-39 side) | — | — |

Orchestrator runs in `workers` (single worker, PG `FOR UPDATE SKIP LOCKED` job
queue). Each step: idempotent (safe to re-run), timeout, ≤ 3 retries, on terminal
failure → `status=provisioning_failed` + CON alert + job context saved for manual
resume. **`provisioning_jobs`** is the resume/replay mechanism for tenant onboarding.

### 3.6 Onboarding checklist (tenant side, ADM-39)

Steps: company profile → branding → domain (optional) → first challenge template
(LCC) → risk config (EVL) → payment/payout config (CHK/PAY) → KYC config (KYC) →
team invites (AUTH V2) → **run one full test challenge with a test trader** (gate
for `go_live`) → go-live review (CON staff sign-off) → `status=active`.
Checklist state in `tenants.onboarding_state JSONB`; rendered in ADM.

### 3.7 Integration secret inventory (TEN-11/TEN-12, review G13)

Every tenant-supplied credential, whether it is a secret, and how it is handled.
Storage = envelope encryption with a per-tenant DEK (docs/28 §5); `masked` fields
return `••••1234` (last 4 of a fingerprint, never the value) on read; every read of a
revealed value is audited (`tenant.integration.revealed`).

| Field | Secret? | Storage | Read-back | Rotation | Audit |
|---|---|---|---|---|---|
| Broker API token / investor password (incl. MetaApi token) | yes | encrypted (`integration_config`) | masked | tenant-initiated; connection test on save (TEN-25, V2) | write + reveal |
| Broker account login / server | no (sensitive) | plain, tenant-scoped | full to tenant admin | — | write |
| Payment provider key + secret (Match2Pay/Interkasa/NOWPayments) | yes | encrypted | masked | tenant-initiated + 90 d reminder | write + reveal |
| Payment webhook signing secret (per provider) | yes | encrypted | masked, never logged | rotate on leak runbook | write |
| KYC provider key (Veriff) | yes | encrypted | masked | 180 d | write |
| KYC provider webhook secret | yes | encrypted | masked | 180 d | write |
| Email sender credentials (SMTP/API key) | yes | encrypted | masked | 180 d | write |
| Payout rail credentials (V2, PAY-05) | yes | encrypted + separate field key | masked | tenant-initiated | write + reveal |
| SSO signing certificate / IdP metadata (V1 for the cutover tenant) | public cert + private only at the IdP | metadata stored as text; no private key on our side | full (public) | tenant-side | write |
| SCIM bearer token we issue | yes (hash only, like API keys) | SHA-256 hash | shown once at issue | 90 d | write + issue |
| ZITADEL OIDC client secret (per tenant application, G34/D19) | yes | in the tenant secret store (`integration_config`), referenced by `tenants.idp_client_secret_ref` | never shown after provisioning | 180 d, dual-secret overlap | rotate (saga action + CON resume) |

Rules: secrets never appear in logs, error payloads, analytics or event payloads;
`GET /v1/tenants/{tenant_id}/integrations` never decrypts (masking only) — decryption happens
only in the integration worker through a scoped accessor that writes the audit row;
a failed connection test is not a reason to log the credential; the tenant-settings
JSONB never contains secrets (they live in `integration_config`, TEN-12).

### 3.8 Tenant login hostname (review G19)

V1: tenants log in at **`login.alpha1.io`** scoped to their org
(`urn:zitadel:iam:org:id:{id}`), which yields per-org branding, password policy and MFA
settings — the hosted-login page is themed with the tenant's logo/colours/product name.
The tenant's own domains (`firm.com`, `firm.alpha1.io`) serve the **app** and the API;
they never serve a login form in V1. Post-login the app performs a silent OIDC
redirect back to the tenant host, so the browser's address bar is on the tenant domain
for the session.

V2 (with TEN-05 custom domains, and only if tenants ask): a **vanity login host**
(`login.firm.com`) implemented at the edge as a rewrite to `login.alpha1.io` with the
org scope preserved and the TLS cert issued for the tenant domain — the same
edge-rewrite pattern as the app-side custom domain, no second login implementation.

## 4. Events

### 4.1 V1 baseline events — authoritative

From `contracts/events/catalog.md`. Envelope EVT-03; payloads in
`contracts/events/payloads/`. TEN is the producer for the tenant lifecycle; AUTH
produces the member events.

| Event | Producer (V1) | V1 consumers |
|---|---|---|
| `tenant.created` | TEN-01 | AUD, CON, NOT (owner) |
| `tenant.provisioning_step_completed` / `_failed` | TEN (orchestrator, docs/03 §3.5) | CON (live view), NOT (staff) |
| `tenant.activated` | TEN (checklist complete) | GW (allow traffic), NOT (owner), AUD, ANA |
| `tenant.suspended` | TEN-15 | AUTH (kill sessions), GW (deny), NOT (owner), AUD — **all stop within 1 s** |
| `tenant.reactivated` | TEN-15 | GW, NOT, AUD, AUTH (identities stay active; sessions require a new login) |
| `tenant.member_invited` | AUTH-03 (V2 row, V1 SSO-tenant exception) | NOT, CON |

### 4.2 Extended (post-V1) event model — design-level

| Event | When | Consumers |
|---|---|---|
| `tenant.plan_changed` | plan/entitlement edit | Flipt sync, limits revalidate, AUD |
| `tenant.settings_changed` | settings JSONB edited | cache invalidator (`t:{id}:*`), AUD (before/after diff) |
| `tenant.branding_changed` | logo/colours/texts edited | web (cache bust), DOC/NOT (next render), AUD |
| `tenant.deletion_scheduled` / `tenant.data_cleaned` | termination saga (§5.2) | CON, AUD, MIG (blocks cutover) |
| `tenant.deactivated` / `tenant.reactivated_post_grace` | recovery window (TEN-45, V2) | GW, AUTH, NOT, AUD |
| `tenant.limit_exceeded` | enforcer warning at 80%, hard stop at 100% | NOT (owner), ANA |
| `tenant.entitlement_changed` | module on/off | GW (route gating), Flipt, AUD (TEN-08) |

## 5. Lifecycles

```
pending_approval ──approve──► provisioning ──steps ok──► onboarding ──checklist──► ACTIVE
        │                         │                                        │  ▲
        └──reject──► (terminal)   └──fail──► provisioning_failed ──resume──┘  │
                                                                        SUSPENDED ◄─┐ (manual, reason)
                                                                          │reactivate│
                                                                        (grace) │
ACTIVE/ONBOARDING ──deactivate──► deactivated ──30d──► pending_deletion ──► data_cleanup ──► archived ──retention──► deleted
```

- **Suspension** is reversible and immediate (traffic + sessions killed). Reasons:
  `billing` (V3), `abuse`, `risk`, `manual`, `provider` (e.g. MetaApi suspension).
- **Deletion** never touches financial rows before retention: ledger/audit rows are
  anonymized (`identity_id` → NULL, kept for legal retention per AUD policy), KYC
  documents deleted from R2, trader PII purged. `tenants` row kept as `deleted`
  tombstone (ids stay unique forever).
- **Plan change**: entitlements/limits updated atomically; quota check re-run for
  the most constrained metric; event emitted. V1 = manual CON action; V3 = BIL-driven.

### 5.1 State → capability matrix (review G7)

What each state means for the surfaces that matter. The machine-readable source is
`contracts/tenants/state-capabilities.yaml` (docs/47, finding M1) — the table below is
**generated** from it (`scripts/verify_tenant_states.py`, gate 16), and the same file is
what the docs/35 I-20 table-driven test consumes.

<!-- tenant-states:begin (generated from contracts/tenants/state-capabilities.yaml — do not edit by hand) -->

| State | Trader login/traffic | Staff (ADM) | API keys | Webhooks out | Bridge sync | Payments | Payouts |
|---|---|---|---|---|---|---|---|
| `pending_approval` | — (`tenant.unknown_host`; DNS exists only from provisioning step 5 — host resolution fails first) | — (`tenant.unknown_host`) | — (`tenant.unknown_host`) | — (`tenant.unknown_host`) | — (`tenant.unknown_host`) | — (`tenant.unknown_host`) | — (`tenant.unknown_host`) |
| `provisioning` | — (`tenant.unknown_host`; before saga step 5; after it, tenant.not_live (details.state=provisioning) — a resolved host on a pre-active tenant) | — (`tenant.unknown_host`; same DNS caveat; tenant.not_live once the host resolves) | — (`tenant.unknown_host`) | — (`tenant.unknown_host`) | — (`tenant.unknown_host`) | — (`tenant.unknown_host`) | — (`tenant.unknown_host`) |
| `provisioning_failed` | — (`tenant.not_live`; details.state=provisioning_failed; unresolved-host case yields tenant.unknown_host at GW step 2) | — (`tenant.not_live`) | — (`tenant.not_live`) | — (`tenant.not_live`) | — (`tenant.not_live`) | — (`tenant.not_live`) | — (`tenant.not_live`) |
| `onboarding` | — (`tenant.not_live`) | ✓ | — (`tenant.not_live`) | — (`tenant.not_live`) | — (`tenant.not_live`; dry-run mode only — BRG sandbox routing, never a live broker connection) | — (`tenant.not_live`) | — (`tenant.not_live`) |
| `active` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `suspended` | — (`tenant.suspended`) | — (`tenant.suspended`) | — (`tenant.suspended`) | — (`tenant.suspended`; in-flight queue drains <= 24 h, then DLQ) | — (`tenant.suspended`; paused, resumable) | — (`tenant.suspended`) | — (`tenant.suspended`; held per PAY policy — approved-but-unexecuted payouts wait) |
| `deactivated` | — (`tenant.deactivated`) | ~ (export-only surface (TEN-33 bundle)) | — (`tenant.deactivated`) | — (`tenant.deactivated`) | — (`tenant.deactivated`) | — (`tenant.deactivated`) | — (`tenant.deactivated`) |
| `pending_deletion` | — (`tenant.pending_deletion`) | ~ (export-only surface) | — (`tenant.pending_deletion`) | — (`tenant.pending_deletion`) | — (`tenant.pending_deletion`) | ~ (settlement only — capture of existing obligations, no new checkout) | ~ (settlement only — owed payouts execute; new requests refused) |
| `archived` | — (`tenant.unknown_host`; DNS removed at data_cleanup) | — (`tenant.unknown_host`) | — (`tenant.unknown_host`) | — (`tenant.unknown_host`) | — (`tenant.unknown_host`) | — (`tenant.unknown_host`) | — (`tenant.unknown_host`) |
| `deleted` | — (`tenant.unknown_host`; by id: tenant.not_found) | — (`tenant.unknown_host`) | — (`tenant.unknown_host`) | — (`tenant.unknown_host`) | — (`tenant.unknown_host`) | — (`tenant.unknown_host`) | — (`tenant.unknown_host`) |

`✓` allowed · `—` blocked (the GW-18 code returned; `details.state` carries the tenant state where the code is generic) · `~` allowed but degraded (note). Generated from `contracts/tenants/state-capabilities.yaml` — the same file the docs/35 I-20 table-driven test consumes; enforcement point is GW step 3.5a (docs/04 §3.1), with module-level holds (payout hold, bridge pause, webhook queue → DLQ) applied by the owning modules from the same `tenant.*` events. Console (platform realm) is not governed by tenant state.

<!-- tenant-states:end -->

Every transition emits `tenant.*` (docs/31) and invalidates `t:{tenant}:*` caches;
`suspended` must reflect in ≤ 1 s (GW deny-set + session kill, TEN-15). The consolidated
multi-tenancy specification — lifecycle, isolation layers, per-tenant identity,
provisioning, configuration — is [47 — The Multi-Tenancy Model](47-multi-tenancy-model.md).

### 5.2 Termination and deletion (review G7)

`POST /v1/tenants/{tenant_id}/terminate` (CON, `tenant.terminate`) is a **saga**, not a flag:
stop traffic (state `suspended`) → export bundle for the tenant (TEN-33 shape, V2
surface; V1 = manual archive of `tenants` + settings + document manifest) → suspend
every identity in the ZITADEL org (`DeactivateUser`) → archive the R2 prefix to cold
storage → anonymise PII in our tables (financial/audit rows retained per AUD policy)
→ `pending_deletion` for the retention window → at **data_cleanup**: delete the KYC
documents + R2 prefix, remove the subdomain DNS record, run the IdP-side erasure
(docs/02 §10.4 — ZITADEL user deletion revokes sessions and blocks login) → `deleted`
tombstone (id and slug never reused; the subdomain therefore never returns to the
available pool).

**The IdP org's fate (stated 2026-09-19, docs/47 M4).** The ZITADEL organization itself
is **never destroyed by the termination saga** — it is retained as the IdP-side
tombstone: after the erasure step it holds no active users, no sessions and no SSO
config, so login is impossible even though the org object (and `tenants.idp_org_id`)
survives for audit, matching our `deleted` tombstone. Org **destruction** exists in
exactly two audited places: the provisioning saga's step-3 *compensation* (a failed
create is torn down so a retry starts clean) and a manual break-glass runbook for
completed-erasure requests executed by a `platform.tenant.provision` holder with a
CRITICAL audit row. `idp-sync` keeps applying late IdP events for `deleted`/`archived`
tenants to the membership rows (docs/43 §4) — never guessing a tenant. The **IdP side**
mirrors the identity deletion rules (docs/02 §10.4), including the accepted limitation
on ZITADEL's event stream.

`deactivated` is recoverable for **30 days** (TEN-45, V2): reactivation restores the
state, DNS and branding from the archive; after that the tenant is only reachable via
an ops restore of the pre-deletion dump.

## 6. Error taxonomy
### 6.1 V1 baseline codes — authoritative

From `contracts/errors/taxonomy.md` (the V1 execution sheet; module TEN). These are the exact codes the V1 surfaces return; the envelope is GW-18 (`code`, `message`, `correlation_id`).
| Code | HTTP | Meaning | User-facing message |
|---|---|---|---|
| `tenant.not_found` | 404 | Tenant id unknown | "Firm not found." |
| `tenant.subdomain_taken` | 409 | Subdomain already in use | "That subdomain is already taken." |
| `tenant.subdomain_reserved` | 409 | Subdomain on reserved list (www, admin, api, console, app) | "That subdomain is reserved." |


Namespace `TEN` (global contract: [30-error-taxonomy](30-error-taxonomy.md)):
### 6.2 Extended (post-V1) codes — design-level

> Below the V1 baseline (6.1); names in the GW-18 dotted convention. Rows duplicating a V1 baseline code were folded into the baseline table (the merged registry: docs/30).


| Code | HTTP | Meaning |
|---|---|---|
| `tenant.suspended` | 403 | Tenant traffic denied (reason in details) |
| `tenant.not_live` | 403 | Pre-`active` tenant on a tenant-realm route (`details.state`: `provisioning`, `provisioning_failed`, `onboarding`; corrected 2026-09-19, docs/47 M2 — the matrix formerly cited an unregistered `tenant.not_ready`) |
| `tenant.provisioning_failed` | 500 | Pipeline terminal failure (CON only, with step) |
| `tenant.slug_taken` | 409 | Slug/subdomain conflict |
| `tenant.domain_invalid` | 422 | DNS/verification failure (custom domain V1.1) |
| `tenant.limit_exceeded` | 422 | `details.metric` + current/limit |
| `tenant.settings_invalid` | 422 | JSON Schema violation, `details.violations[]` |
| `tenant.branding_invalid` | 422 | Asset/size/CSS-safety check failed |
| `tenant.kyb_required` | 403 | Staff can't activate without KYB (V1 gate) |
| `tenant.plan_insufficient` | 403 | Route/module not in tenant's entitlements |
| `tenant.deactivated` | 403 | Tenant deactivated; export-only surface (recoverable inside the 30-day window, TEN-45) |
| `tenant.pending_deletion` | 403 | Tenant scheduled for deletion; settlement-only surface (§5.1) |

## 7. API endpoints
### 7.1 V1 baseline — `tenant` (authoritative: `contracts/api/tenant.md`)

| Method + path | Auth | Permission | Idempotency | V1 errors |
|---|---|---|---|---|
| `POST /v1/tenants` | Super Admin (console realm) — TEN-01 | `tenant.create` # AUTH-13, key derived from TEN-01 | required | `tenant.subdomain_taken`, `tenant.subdomain_reserved` |
| `GET /v1/tenants/{tenant_id}` | Super Admin — TEN-01 | `tenant.read` # derived from TEN-01 "view" | n/a | `tenant.not_found` |
| `PATCH /v1/tenants/{tenant_id}` | Super Admin — TEN-01 | `tenant.update` # derived from TEN-01 "edit" | required | `tenant.not_found` |
| `POST /v1/tenants/{tenant_id}/suspend` | Super Admin — TEN-15 | `tenant.suspend` # AUTH-13, key derived from TEN-15 | required | `tenant.not_found` |
| `POST /v1/tenants/{tenant_id}/terminate` | Super Admin — TEN-01 | `tenant.terminate` # derived from TEN-01 | required | `tenant.not_found` |
| `GET /v1/tenants/subdomain-check` | Super Admin — TEN-42 | `tenant.create` (used during creation flow) # TEN-42 | n/a | standard |
| `PUT /v1/tenants/{tenant_id}/entitlements` | Super Admin — TEN-08 | `tenant.entitlement.change` # AUTH-13, key derived from TEN-08 | required | `tenant.not_found`, `module.unknown` |
| `PUT /v1/tenants/{tenant_id}/integrations` | Tenant Admin — TEN-11 | `tenant.integration.write` # AUTH-13, key derived from TEN-11 | required | `tenant.not_found` |
| `GET /v1/tenants/{tenant_id}/integrations` | Tenant Admin — TEN-11 | `tenant.integration.read` # masked read-back, docs/03 §3.7 (review G13) | n/a | `tenant.not_found` |

Scope, request/response shapes, and per-endpoint notes: `contracts/api/tenant.md` (field values in the research are owner TODOs until contract freeze; canonical JSON is fixed at freeze, per the docs/99 §12 rules).


#### V2 row stubs — design intent per requirement (review G15)

| Req | Feature | Design intent (V2 unless marked) |
|---|---|---|
| TEN-04 | Branding | V1 field set already exists (§3.4/§8 `branding` JSONB); V2 adds the editor UI, asset validation (TEN-44) and per-surface overrides. |
| TEN-05 | Custom domain | `domain_mappings` row + CON verification wizard; edge rewrite (app + optional vanity login host, §3.8); TLS via Cloudflare for SaaS. |
| TEN-06 / TEN-07 | Terminology + locale | Curated keys in `settings` (`terminology.*`, `locale: {currency, timezone, language}`) resolved once and served by `/v1/settings` + the tenant-context endpoint. |
| TEN-09 | Module lifecycle | Entitlement rows gain a state (`installed|enabled|suspended|disabled`) with `tenant.entitlement_changed`; UI/API gate on `enabled`. |
| TEN-10 | Feature flags | Flipt, per-tenant; flag changes audited as `tenant.settings_changed` (V1 already ships the flags, V2 adds the tenant-facing toggle). |
| TEN-13 / TEN-29 | Legal pages + versioning/re-consent | Document versions stored with content hash; publishing a version writes `legal_versions` and sets the re-consent gate checked by `/v1/auth/session` (AUTH-31 log). |
| TEN-14 | Email sender config | `settings.comms` + DNS records (SPF/DKIM) per tenant; sending domain verification status surfaced with TEN-26. |
| TEN-16 | Impersonation | Consent + control UI (CON-07) + `tenant.impersonate` key + AUD-08 audit format; **not in V1** (AUTH-16 is separation-only, docs/02 §3.1). |
| TEN-17 | Tenant context endpoint | `GET /v1/tenants/context` — single bootstrap payload (branding, entitlements, flags, terminology, locale) served from the `t:{tenant}:*` cache. |
| TEN-19 | Tenant audit | Read surface over `audit_events` filtered to the tenant, plus the config-diff timeline (§3.3 `tenant.settings_changed` before/after). |
| TEN-20 / TEN-22 / TEN-23 | Metering, quotas, alerts | `usage_events` (V1 table, §9) + enforcer counters; quotas in `limits`; 80 %/100 % thresholds emit `tenant.limit_exceeded` → NOT + CON. |
| TEN-21 | Tenant health | Per-tenant rollups of error rate, broker-sync lag (BRG), queue lag and provisioning state; CON dashboard row per tenant. |
| TEN-24 (V3) | Data residency | Out of scope until a second region exists (ADR-9 single box / ADR-10 single PG); row stays parked with the decision recorded in docs/41 §5. |
| TEN-25 | Integration connection test | Per-integration probe from the worker (broker ping, payment provider auth check, KYC key check, SMTP handshake) with the result audited and stored per config version. |
| TEN-26 | Domain verification + SSL | DNS record instructions + periodic verification job; certificate state from Cloudflare for SaaS; failures alert the tenant admin. |
| TEN-27 / TEN-28 / TEN-39 | Effective-value view, config versioning/rollback, dry-run | `tenant_settings_versions` (append-only, diffs), resolver that walks platform → tenant → module defaults, and a dry-run endpoint that returns the resolved diff without writing. |
| TEN-30 | Setup checklist | The §3.6 checklist with per-step completion stored in `tenants.onboarding_state` (already in V1) and V2 exposing progress + gating. |
| TEN-31 | Notification channel policy | `settings.comms.channels` + a mandatory-channel list consumed by NOT (breach/payout always on). |
| TEN-32 | Staff access review | Join of `tenant_memberships` + last-active + IdP MFA state; bulk-disable action; nightly drift report from the ZITADEL mirror (P4). |
| TEN-33 / TEN-37 / TEN-38 | Offboarding export, portability, archival vs hard deletion | Export package spec (JSONL + CSV + media manifest) built by the MIG/ANA exporters; retention windows per data class; `archived` vs `deleted` distinction in the lifecycle (§5.2). |
| TEN-34 | Config clone | Copy of the curated `settings`/`branding`/`terminology` between tenants with an explicit include list; never copies secrets or entitlements. |
| TEN-35 | Entitlement impact preview | Pre-flight query counting active entities that depend on a module (commission accruals, competitions, scheduled content) before disabling. |
| TEN-36 | Cross-tenant isolation testing | V1 deliverable in CI: docs/35 I-01/I-14 + I-17 (RLS) — the V2 row is the per-module expansion of the same suite. |
| TEN-40 | Tenant-targeted incidents | Incident records with a tenant scope + status page segment; NOT delivers to the affected tenants only. |
| TEN-41 | Tenant admin invite email | The provisioning saga's step 8 invite (§3.5) re-issued from CON with a fresh one-time link. |
| TEN-43 | Subdomain change | Explicit migration job: new slug provisioned → redirect window from the old subdomain → cookies/session invalidated → audit (V1 keeps subdomains immutable, §3.2). |
| TEN-44 | Branding asset validation | Type/size/dimension limits + SVG sanitisation on upload (§3.4); the V1 upload path already enforces type/size in docs/03 §7.2. |
| TEN-45 | Deactivation recovery window | 30-day `deactivated` window with restore (or `pending_deletion` continuation) — mechanics in §5.2; the row adds the configurable window + CON surface. |

### 7.2 Extended (post-V1) surface — provisional

> Not in the V1 execution sheet. Design-level; paths beyond the V1 baseline are provisional until the URL-plan decision (`contracts/api/gw.md`, open question). Shown for platform completeness (V2/V3 phases, docs/99).

Tenant-side (staff role in-tenant):
`GET /v1/settings`, `PATCH /v1/settings` (curated keys), `GET|PUT /v1/branding`,
`POST /v1/branding/assets` (upload → R2, validated: type png/svg/jpg, ≤ 2 MB),
`GET /v1/onboarding` (checklist state + progress), `POST /v1/onboarding/complete-step`,
`GET /v1/limits` (current usage vs limits).

Console (platform realm, CON):
`POST /v1/console/tenants`, `GET /v1/console/tenants`, `GET /v1/console/tenants/{id}`,
`PATCH /v1/console/tenants/{id}` (plan, limits, tags),
`POST /v1/console/tenants/{id}/suspend | /activate | /deactivate`,
`POST /v1/console/tenants/{id}/provisioning/resume` (failed step),
`GET /v1/console/tenants/{id}/provisioning` (job state),
`GET /v1/console/tenants/{id}/usage`, `GET /v1/console/tenants/{id}/health`.
Full listing in `contracts/tenants.openapi.yaml`.
## 8. Schema (key shapes)

```jsonc
// GET /v1/console/tenants/{id}
{ "data": { "id": "01J9...", "slug": "funderblu", "firm_name": "FunderBlu",
    "status": "active", "plan": "funderblu-launch-2026", "jurisdiction": "PK",
    "kyb_status": "verified",
    "limits": { "max_traders": 5000, "max_active_accounts": 2000,
                "api_rate_limit_rpm": 600, "storage_quota_gb": 50 },
    "usage":  { "traders": 1204, "active_accounts": 431,
                "storage_gb": 6.2, "api_rpm_avg": 95 },
    "domains": [ { "domain": "funderblu.alpha1.io", "type": "subdomain", "verified": true } ],
    "branding": { "logo": { "primary": "tenants/01J9.../logo.png" }, "colors": { "primary": "#0B2545" } },
    "created_at": 1757673600000 } }

// PATCH /v1/settings (tenant-side; only provided keys changed)
{ "data": { "payout": { "approval_mode": "manual", "min_amount_cents": 5000 },
    "comms": { "email_from": "no-reply@funderblu.com" } },
  "meta": { "request_id": "...", "version": "v1" } }
```

## 9. Database design

```sql
CREATE TABLE tenants (
  id            ULID PRIMARY KEY,
  slug          VARCHAR(63) UNIQUE NOT NULL,
  idp_org_id    TEXT UNIQUE,                      -- ZITADEL org (review G1); NULL until provisioned
  idp_org_domain TEXT,                            -- {slug}.alpha1.io, set as the org domain
  idp_client_id TEXT UNIQUE,                      -- that org's OIDC application audience — token `aud` check (G34/D19)
  idp_client_secret_ref TEXT,                     -- SOPS/KMS reference; the secret itself never lives in this row
  parent_id     ULID REFERENCES tenants(id),      -- ADR-2 door, NULL in V1
  firm_name     VARCHAR(255) NOT NULL,
  legal_entity_name VARCHAR(255), registration_number VARCHAR(100), tax_id VARCHAR(100),
  jurisdiction  CHAR(2) NOT NULL DEFAULT 'PK',
  kyb_status    TEXT NOT NULL DEFAULT 'pending' CHECK (kyb_status IN ('pending','verified','failed')),
  kyb_verified_at TIMESTAMPTZ,
  primary_contact JSONB NOT NULL DEFAULT '{}',     -- {name,email,phone}
  support_email TEXT,
  status        TEXT NOT NULL DEFAULT 'pending_approval'
    CHECK (status IN ('pending_approval','provisioning','provisioning_failed','onboarding',
                      'active','suspended','deactivated','pending_deletion','archived','deleted')),
  plan          TEXT NOT NULL DEFAULT 'manual',     -- contract ref V1; BIL plan id V3
  limits        JSONB NOT NULL DEFAULT '{}',
  settings      JSONB NOT NULL DEFAULT '{}',        -- validated vs contracts schema
  branding      JSONB NOT NULL DEFAULT '{}',
  features      JSONB NOT NULL DEFAULT '{}',        -- denormalized entitlements snapshot; written only in the entitlement-change transaction (never a second write path, never read for authz)
  onboarding_state JSONB NOT NULL DEFAULT '{"completedSteps":[]}',
  data_region   VARCHAR(20) NOT NULL DEFAULT 'eu-hetzner',
  suspended_at  TIMESTAMPTZ, suspension_reason TEXT,
  created_by    ULID,                                -- platform staff identity
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  activated_at  TIMESTAMPTZ                         -- set on the onboarding->active transition
  deletion_scheduled_at TIMESTAMPTZ
);
CREATE INDEX idx_tenants_status ON tenants(status);
CREATE INDEX idx_tenants_parent ON tenants(parent_id) WHERE parent_id IS NOT NULL;

CREATE TABLE domain_mappings (
  id            ULID PRIMARY KEY,
  tenant_id     ULID NOT NULL REFERENCES tenants(id),
  domain        VARCHAR(255) UNIQUE NOT NULL,
  -- custom domains ONLY (decision D, docs/47 §15): the subdomain lives solely in
  -- tenants.slug — resolution never reads this table for {slug}.alpha1.io, and the
  -- 'subdomain' enum value is dropped at the V1.1 custom-domain freeze
  type          TEXT NOT NULL CHECK (type IN ('subdomain','custom')),
  verified      BOOLEAN NOT NULL DEFAULT false,
  verification_token TEXT,            -- TXT record token (custom domain)
  ssl_status    TEXT NOT NULL DEFAULT 'pending',
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE tenant_entitlements (
  id           ULID PRIMARY KEY,
  tenant_id    ULID NOT NULL REFERENCES tenants(id),
  module       TEXT NOT NULL,          -- 'td','adm','not','cmp','sdk',...
  enabled      BOOLEAN NOT NULL DEFAULT true,
  limit_override JSONB,                -- e.g. {"max_rules": 50}
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, module)
);

CREATE TABLE provisioning_jobs (
  id              ULID PRIMARY KEY,
  tenant_id       ULID REFERENCES tenants(id),
  type            TEXT NOT NULL DEFAULT 'provision',
  status          TEXT NOT NULL DEFAULT 'pending'
                  CHECK (status IN ('pending','running','succeeded','failed','needs_resume')),
  current_step    TEXT,
  completed_steps JSONB NOT NULL DEFAULT '[]',
  failed_step     TEXT, error_message  TEXT,
  context         JSONB NOT NULL DEFAULT '{}',
  started_at      TIMESTAMPTZ, completed_at TIMESTAMPTZ,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_provjobs_active ON provisioning_jobs(status) WHERE status IN ('pending','running','needs_resume');

CREATE TABLE usage_events (               -- BIL foundation (V3 billing reads these)
  id               ULID,
  tenant_id        ULID NOT NULL,
  metric_name      TEXT NOT NULL,         -- active_traders, funded_accounts, api_calls,
                                          -- storage_gb, payouts_processed, kyc_verifications...
  value            NUMERIC(18,4) NOT NULL,
  unit             TEXT NOT NULL,
  period_started_at TIMESTAMPTZ NOT NULL,
  recorded_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  idempotency_key  TEXT,
  PRIMARY KEY (id, period_started_at)   -- partitioned table: PK must include the partition key
) PARTITION BY RANGE (period_started_at);  -- monthly partitions (decision U, docs/47 §15)
CREATE INDEX idx_usage_tenant_metric ON usage_events(tenant_id, metric_name, period_started_at);

-- Retention (decision U, 2026-09-19): raw rows are kept 25 months (monthly partitions
-- dropped past the window by the scheduled-jobs worker); from month 13 onward the
-- flusher also writes monthly rollups below, and BIL (V3) reads rollups for anything
-- older. Tenant deletion purges both per §5.2 (rollups keep the anonymised totals).
CREATE TABLE usage_rollups_monthly (
  tenant_id        ULID NOT NULL,
  metric_name      TEXT NOT NULL,
  month            DATE NOT NULL,          -- first day of the month, UTC
  value_total      NUMERIC(18,4) NOT NULL,
  sample_count     BIGINT NOT NULL,
  rolled_up_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (tenant_id, metric_name, month)
);
```

**RLS (D3).** Every tenant-owned table in this module (`domain_mappings`,
`tenant_entitlements`, `provisioning_jobs`, `usage_events`, and `integration_config`
where it exists in the module that owns the field)
carries `ENABLE`/`FORCE ROW LEVEL SECURITY` with the `current_setting('app.tenant_id', true)`
policy, a `(tenant_id, …)` index, and `WITH CHECK` so a cross-tenant insert fails;
`tenants` itself is guard-only (platform-owned) and excluded from the policy set.

Cache: `t:{tenant}:config|branding|entitlements` in Redis (TTL 5 min / 1 h for
branding) + in-mem LRU 60 s; invalidation via `tenant.*_changed` events + pub/sub
`cache:invalidate` channel (all api instances clear L1).

## 10. Security & compliance

- **Isolation**: every table here is tenant-owned except `tenants` itself (platform
  realm). `tenant_id` immutability enforced at write (reject updates to the column).
  **Enforcement depth (decided D3, 2026-09-19): two layers.** ADR-1's app-level
  guard (Go tenant guard + sqlc + CI guard test) stays, and every tenant-owned table
  additionally gets **Postgres RLS**: `FORCE ROW LEVEL SECURITY`, a policy reading
  `current_setting('app.tenant_id', true)` set per transaction via
  `set_config(…, true)` (mandatory under PgBouncer transaction mode, ADR-8), and a
  `(tenant_id, …)` index on every policy table. A forgotten predicate then returns
  *zero* rows instead of all of them, at 2–4 % query cost. Mechanics and failure
  modes: docs/41 §5; negative tests are part of TEN-36.
- **KYB gate** (V1): a tenant cannot reach `active` with `kyb_status != verified` —
  verification = CON staff review of legal entity docs (manual in V1; Veriff business
  flows V3). Sanctions screening of the legal entity + primary contact before
  provisioning (staff checklist; automated screen V2).
- **Tenant compromise blast radius**: API keys are tenant-scoped (AUTH), quotas are
  hard (GW), R2 prefixes are tenant-bound, audit shows per-tenant access; a
  compromised tenant admin cannot cross tenants (proven by isolation suite).
- **Deletion integrity**: financial/audit rows survive deletion anonymized (GDPR
  storage limitation vs. financial retention — legal review item, FunderBlu counsel).
- **Settings abuse**: `custom_css` sandboxed; legal URLs must be https and
  tenant-owned (or platform default) — no arbitrary redirect hosting.

## 11. Scalability considerations

- Resolution is the hot path: 99%+ cache hit; negative-cache 60 s.
- Config reads: denormalized rows → single indexed fetch per request max, cached.
- Usage metering: buffered writes (flush every 60 s or 1 k events) to
  `usage_events` — never on the request path.
- Tenant count headroom: at 50 tenants the `tenants` table is 50 rows; no
  per-tenant infrastructure in V1 means scaling = more rows, not more resources.
- Noisy neighbor: API rate limits (per-tenant RPM) + broker account caps (MetaApi
  cost guard) + storage quotas. Bulkheads: bridge sync scheduler assigns each tenant
  a share of the poll budget (e.g. max 50% of poll slots to any one tenant).

## 12. Open-source solutions

> Re-evaluated 2026-09-19 together with AUTH: the candidate-by-candidate scoring is
> [41 — AUTH + TEN open-source evaluation](41-auth-ten-open-source-evaluation.md).
> The class that matters here is *multi-tenant databases* — shared schema + RLS vs
> schema-per-tenant vs DB-per-tenant — and the conclusion is unchanged: ADR-1
> (shared schema, `tenant_id`) is the only model that fits one Postgres on one box,
> with **Postgres RLS as an optional fail-closed second layer (D3)**.

| Option | Verdict |
|---|---|
| Flipt (self-hosted) | **CHOSEN** — code-level feature flags & per-tenant gating (PRD register) |
| Postgres RLS (same database, second enforcement layer) | **CHOSEN (D3, 2026-09-19):** fail-closed, 2–4 % overhead, needs `FORCE RLS` + transaction-scoped `set_config(…, true)` under PgBouncer and a `(tenant_id, …)` index per policy table (docs/41 §5). Adopted on every tenant-owned table; the app guard stays as the first layer |
| Schema-per-tenant / DB-per-tenant | Rejected (ADR-1): N× migrations, catalog bloat, PgBouncer friction, connection-limit pressure; the isolation gain is not worth it at ≤ 200 tenants |
| Spiffy/Temporal (provisioning) | Rejected V1: saga is 9 steps, one orchestrator loop in `workers` with PG job rows is simpler and observable; revisit if steps > 20 |
| Nile/Citus (tenant sharding) | Rejected V1 (ADR-1); revisit at > 200 tenants |
| Casbin (tenant-level policies) | Same engine as AUTH (ADR-14, embedded): tenant config policies are Casbin rows in the same policy table, keyed by `dom = tenant_id` |
| Documenso | Only for DOC-12 e-sign (V2) — not a TEN component |
| Kong-style tenant gateways | Rejected (ADR-4) |

## 13. Technology stack

Go domain package in `api`; provisioning orchestrator in `workers` (PG job queue);
**ZITADEL Admin API** (organization, project/application, org policies, branding —
step 3 of the saga); Flipt (Compose service); Cloudflare API (DNS records); R2
(branding assets); Postmark via NOT (invite emails); Sentry (provisioning failure
alerts).

## 14. Integration — internal modules (glue)

| Module | How |
|---|---|
| **AUTH** | provisioning step 3 creates the ZITADEL organization + project/application + owner membership and writes `idp_org_id` + `idp_client_id` (step 3a adds the external IdP + SCIM token when contracted — no group→role mapping in V1, G37/D22); `tenant.suspended` kills its sessions (our deny-set + ZITADEL session termination); console realm separates platform staff |
| **GW** | tenant resolution source; quota & entitlement gate reads TEN rows; `suspended` → immediate 403 |
| **BRG** | `settings.trading.broker_group` selects the MetaApi server group (BRG-12); account caps enforced here |
| **EVL** | provisioning seeds default rule packs; tenant custom rules live in EVL but capped by `max_custom_rules` |
| **NOT** | owner emails (invite, suspension, limit warnings) use `settings.comms` + branding |
| **DOC** | certificates/statements/invoices render with `branding` |
| **CON** | all tenant CRUD for staff; live provisioning view; usage & health screens |
| **ANA** | per-tenant KPIs join `tenants` for plan/jurisdiction cuts |
| **MIG** | cutover creates tenant `funderblu` via the same pipeline with extra steps (data import, account mapping) |
| **BIL (V3)** | reads `usage_events`; plan changes call TEN's `plan_changed` path |

## 15. Integration — external tools

Cloudflare (DNS + TLS for subdomains/custom domains), Flipt, R2, Postmark (via NOT),
Sentry, ipinfo (jurisdiction checks for KYB evidence), Comp AI/Openlane (SOC 2
evidence for tenant onboarding records — consider-later register).

## 16. Implementation blueprint

| Step | Owner | Est | Depends | Exit criteria |
|---|---|---|---|---|
| 1. Schemas (tenants, domain_mappings, entitlements, provisioning_jobs, usage_events) + guard | BE-2 | 1.5 d | OPS, AUTH | isolation suite green |
| 2. Tenant CRUD + settings/branding validation (JSON Schemas in contracts) | BE-2 | 3 d | 1 | CON creates tenant `staging-fb` end-to-end |
| 3. Resolution middleware (custom domain/subdomain/header/key) + negative cache | BE-1 | 2 d | 1 | unknown subdomain → 404, < 5 ms cached |
| 4. Provisioning saga (steps 1–9, incl. 6b CoA seed — D26) + resume CLI | BE-2 | 4 d | 2, AUTH org, Cloudflare creds | kill step 6 mid-run → resume completes; tenant live on staging subdomain |
| 5. Suspension/activation + session/traffic kill (event wiring to AUTH/GW) | BE-1 | 1.5 d | 4 | suspended tenant's live trader gets 403 in < 1 s |
| 6. Limits enforcer (`limits.Assert`) + usage metering buffer | BE-2 | 2 d | 4 | over-limit account provisioning rejected with `tenant.limit_exceeded` (docs/47 M3) |
| 7. White-label render path (CSS vars + email brand) + asset upload/validation | FE-01 + BE-2 | 3 d | 5 | TD login page shows tenant brand on staging |
| 8. Onboarding checklist API + ADM screen (ADM-39) | FE-1 | 3 d | 6 | FunderBlu checklist completable in staging |
| 9. V1.1: custom domains (TXT verify, Cloudflare cert), quota alert emails | BE-2 + FE-1 | 4 d | 7 | `trade.funderblu.com` live on staging |
| 10. V2: onboarding polish, report branding, per-tenant API version pin (doors only) | BE-2 | 4 d | 9 | — |
| 11. V3: self-serve signup wiring (BIL-18), sub-tenant door review | BE-2 | 5 d | BIL | — |

**Risks:** Cloudflare DNS ops without a staffed API account (mitigation: service
token scoped to the zone, Phase 0); slug collision at cutover (FunderBlu slug
reserved in Phase 0); settings JSONB drift (mitigation: schema test that renders
every key into the tenant docs page).

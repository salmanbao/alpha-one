# 03 — TEN: Tenant Management

> Covers PRD module **TEN** (45 requirements). Tenant lifecycle, white-label,
> entitlements, limits, and the configuration inheritance chain.

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
  entitlements per route group; Flipt decides per feature.
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
`ten.limit_exceeded` with the metric named.

### 3.2 Tenant resolution (order binding — see 01 §5)

custom domain → subdomain (`{slug}.alpha1.io`) → internal `X-Tenant-Id` (service
tokens only) → API-key-embedded (wins over headers). Negative lookups are cached
(60 s) so unknown-subdomain probing doesn't hammer PG. Status check in the same
call: `suspended` tenant → 403 for all its traffic (`GW-23`); `onboarding` tenant →
trader-facing routes 403, staff routes OK.

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
| 3 | provision AUTH org + owner membership | destroy org | retry ×2 |
| 4 | branding defaults + legal defaults | delete rows | retry |
| 5 | subdomain DNS (Cloudflare API: `CNAME {slug}.alpha1.io`) | delete record | retry; custom domain = V1.1 step |
| 6 | default broker group ref (BRG-12) + default rule packs (EVL seed) | delete refs | retry |
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

## 4. Events

| Event | Producer | Consumers |
|---|---|---|
| `tenant.created` | TEN | AUD, CON |
| `tenant.provisioning_step_completed/failed` | TEN (orchestrator) | CON (live view), NOT (staff) |
| `tenant.activated` | TEN | GW (allow traffic), NOT (owner), AUD, ANA |
| `tenant.suspended` | TEN | AUTH (kill sessions), GW (deny), NOT (owner), AUD — **all stop within 1 s** |
| `tenant.reactivated` | TEN | GW, NOT, AUD |
| `tenant.plan_changed` | TEN | Flipt sync, limits revalidate, AUD |
| `tenant.settings_changed` | TEN | cache invalidator (`t:{id}:*`), AUD (before/after diff) |
| `tenant.branding_changed` | TEN | web (cache bust), DOC/NOT (next render), AUD |
| `tenant.deletion_scheduled` / `tenant.data_cleaned` | TEN | CON, AUD, MIG (blocks cutover) |
| `tenant.limit_exceeded` (warning, non-blocking at 80%) | enforcers | NOT (owner), ANA |

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
| `tenant.not_live` | 403 | `onboarding` tenant, trader-facing route |
| `tenant.provisioning_failed` | 500 | Pipeline terminal failure (CON only, with step) |
| `tenant.slug_taken` | 409 | Slug/subdomain conflict |
| `tenant.domain_invalid` | 422 | DNS/verification failure (custom domain V1.1) |
| `tenant.limit_exceeded` | 422 | `details.metric` + current/limit |
| `tenant.settings_invalid` | 422 | JSON Schema violation, `details.violations[]` |
| `tenant.branding_invalid` | 422 | Asset/size/CSS-safety check failed |
| `tenant.kyb_required` | 403 | Staff can't activate without KYB (V1 gate) |
| `tenant.plan_insufficient` | 403 | Route/module not in tenant's entitlements |

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
| `GET /v1/tenants/{tenant_id}/integrations` | Tenant Admin — TEN-11 | `tenant.integration.read` # derived from TEN-11 management need; read-back masking rules — TODO — needs owner decision | n/a | `tenant.not_found` |

Scope, request/response shapes, and per-endpoint notes: `contracts/api/tenant.md` (field values in the research are owner TODOs until contract freeze; canonical JSON is fixed at freeze, per the docs/99 §12 rules).

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
  features      JSONB NOT NULL DEFAULT '{}',        -- denormalized entitlements snapshot
  onboarding_state JSONB NOT NULL DEFAULT '{"completedSteps":[]}',
  data_region   VARCHAR(20) NOT NULL DEFAULT 'eu-hetzner',
  suspended_at  TIMESTAMPTZ, suspension_reason TEXT,
  created_by    ULID,                                -- platform staff identity
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  activated_at  TIMESTAMPTZ, suspended_reason TEXT,
  deletion_scheduled_at TIMESTAMPTZ
);
CREATE INDEX idx_tenants_status ON tenants(status);
CREATE INDEX idx_tenants_parent ON tenants(parent_id) WHERE parent_id IS NOT NULL;

CREATE TABLE domain_mappings (
  id            ULID PRIMARY KEY,
  tenant_id     ULID NOT NULL REFERENCES tenants(id),
  domain        VARCHAR(255) UNIQUE NOT NULL,
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
  PRIMARY KEY (id)
);
CREATE INDEX idx_usage_tenant_metric ON usage_events(tenant_id, metric_name, period_started_at);
```

Cache: `t:{tenant}:config|branding|entitlements` in Redis (TTL 5 min / 1 h for
branding) + in-mem LRU 60 s; invalidation via `tenant.*_changed` events + pub/sub
`cache:invalidate` channel (all api instances clear L1).

## 10. Security & compliance

- **Isolation**: every table here is tenant-owned except `tenants` itself (platform
  realm). `tenant_id` immutability enforced at write (reject updates to the column).
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

| Option | Verdict |
|---|---|
| Flipt (self-hosted) | **CHOSEN** — code-level feature flags & per-tenant gating (PRD register) |
| Spiffy/Temporal (provisioning) | Rejected V1: saga is 9 steps, one orchestrator loop in `workers` with PG job rows is simpler and observable; revisit if steps > 20 |
| Nile/Citus (tenant sharding) | Rejected V1 (ADR-1); revisit at > 200 tenants |
| Cerbos (tenant-level policies) | Same PDP as AUTH; tenant config policies live in the same policy repo |
| Documenso | Only for DOC-12 e-sign (V2) — not a TEN component |
| Kong-style tenant gateways | Rejected (ADR-4) |

## 13. Technology stack

Go domain package in `api`; provisioning orchestrator in `workers` (PG job queue);
Flipt (Compose service); Cloudflare API (DNS records); R2 (branding assets);
Postmark via NOT (invite emails); Sentry (provisioning failure alerts).

## 14. Integration — internal modules (glue)

| Module | How |
|---|---|
| **AUTH** | provisioning step 3 creates the org + owner membership; `tenant.suspended` kills its sessions; console realm separates platform staff |
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
| 4. Provisioning saga (steps 1–9) + resume CLI | BE-2 | 4 d | 2, AUTH org, Cloudflare creds | kill step 6 mid-run → resume completes; tenant live on staging subdomain |
| 5. Suspension/activation + session/traffic kill (event wiring to AUTH/GW) | BE-1 | 1.5 d | 4 | suspended tenant's live trader gets 403 in < 1 s |
| 6. Limits enforcer (`limits.Assert`) + usage metering buffer | BE-2 | 2 d | 4 | over-limit account provisioning rejected with `TENANT_LIMIT_EXCEEDED` |
| 7. White-label render path (CSS vars + email brand) + asset upload/validation | FE-01 + BE-2 | 3 d | 5 | TD login page shows tenant brand on staging |
| 8. Onboarding checklist API + ADM screen (ADM-39) | FE-1 | 3 d | 6 | FunderBlu checklist completable in staging |
| 9. V1.1: custom domains (TXT verify, Cloudflare cert), quota alert emails | BE-2 + FE-1 | 4 d | 7 | `trade.funderblu.com` live on staging |
| 10. V2: onboarding polish, report branding, per-tenant API version pin (doors only) | BE-2 | 4 d | 9 | — |
| 11. V3: self-serve signup wiring (BIL-18), sub-tenant door review | BE-2 | 5 d | BIL | — |

**Risks:** Cloudflare DNS ops without a staffed API account (mitigation: service
token scoped to the zone, Phase 0); slug collision at cutover (FunderBlu slug
reserved in Phase 0); settings JSONB drift (mitigation: schema test that renders
every key into the tenant docs page).

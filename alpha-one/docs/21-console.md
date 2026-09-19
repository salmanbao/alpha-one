# 21 — CON: Platform Console

> Covers PRD module **CON** (33 requirements). The **platform operator's**
> cockpit — the surface *we* (and FunderBlu's stakeholders with platform
> roles) use to run every tenant: provisioning, entitlements, platform
> health, cross-tenant observability, security posture, and incident
> controls. It is a different realm from both TD (traders) and ADM
> (tenant staff) — the PRD non-negotiable: **separate subdomain + own auth
> realm** (02 §3.4).

## 1. Purpose & scope

**V1 (3 — binding):**
- **Console auth realm (CON-01):** the `platform:*` role family in a
  separate ZITADEL application/audience (AUTH-12/16): `platform:owner`
  (everything, incl. tenant suspension), `platform:ops` (health, jobs,
  incidents), `platform:support` (read-assist, tenant contact registry),
  `platform:finance` (platform financials, CON-19 V2 early-read).
- **Console shell (CON-29):** the app shell on `console.alphaone.example`
  (Next.js `web/con`), module navigation, global tenant search (V1: id/name
  only), session management (CON-30).
- **Console session management (CON-30):** sessions in the console realm —
  15 min idle, concurrent sessions allowed, login anomaly scoring applies
  (02 §3.7 — platform operators are the highest-value accounts on the
  system; the same controls, stricter defaults), session listing +
  revocation for the signed-in operator.

**V2 (28):** tenant list/search (CON-02), **provisioning wizard (CON-03 —
the 9-step saga from 03 §3.1 driven from the console, with a live step
view)**, tenant detail (CON-04), entitlement management (CON-05),
suspension & termination (CON-06 — the nuclear buttons, 2FA + second
operator), impersonation control (CON-07 — the only cross-realm entry:
view-as, fully audited), platform health dashboard (CON-08 — the CON/OPS
wall screen for platform ops), platform audit view (CON-09), usage metering
(CON-10), global defaults (CON-11), deploy & version visibility (CON-12),
cross-tenant abuse signals (CON-13 — RSK's cross-tenant inputs),
announcements (CON-14), **incident controls (CON-15 — the emergency stop
surface: platform halt, tenant halt, relay pause, flag overrides — every
control 2FA + critical audit + runbook link)**, maintenance mode (CON-16),
global entity search (CON-17), role management (CON-18), platform financial
overview (CON-19), broker/provider registry (CON-20 — the tooling register
as live state), job & scheduler observability (CON-21 — the advisory-lock
job dashboard, 06), security overview (CON-22), master reference data
(CON-23), subscription & contract (CON-24 → BIL), cross-tenant support
assist (CON-27), retention & residency (CON-26 V3), cross-tenant queue
overview (CON-25), feature flags (CON-31 — Flipt admin surface), action
approval (CON-32 — two-operator approval for the nuclear set), notification
centre (CON-33).

Requirement coverage: `CON-01,29,30` (V1.0) + `02..23,25,27,28,31..33` (V2.0) + `24,26` (V3.0: data residency, billing overlap).

## 2. Architecture

```
 web/con (Next.js 15, the monorepo's third app)
   │  · realm: platform:* only — the GW rejects non-platform sessions on
   │    /v1/console/* routes (structural, 02 §3.4); a tenant staff cookie
   │    on the console subdomain is useless
   │  · RSC pages; the incident-controls and tenant-suspension surfaces are
   │    the most-protected pages on the platform (2FA + V2 two-operator)
   ▼
 GW /v1/console/* → Go console APIs:
   · TEN (03): provisioning saga trigger, entitlements, suspension
   · OPS state (06): health, jobs, deploys, relay lag, backup status
   · CON (05): platform audit view (cross-tenant, owner-role)
   · ANA (19): platform KPIs (cross-tenant = the ANA-28 V3 pattern,
     available to platform:owner from V2 — the platform's own analytics)
   · RSK: cross-tenant abuse signals (V2 CON-13)
   · BIL (V3): subscriptions
   · Flipt (flags), UptimeKuma (external checks) — read surfaces
```

**Principle (same as ADM, stronger):** the console **triggers** domain
actions (saga start, suspension, halt) — it never writes tenant data
directly. Every cross-tenant read is role-gated **and** audit-critical
(a platform operator reading tenant X's payout data is a critical event —
the platform's own compliance posture models the tenants').

## 3. System design

### 3.1 V1 screens

| Screen | Content |
|---|---|
| **Login + session** | ZITADEL console application (separate audience); 2FA mandatory for all platform roles (no exceptions — these accounts can suspend tenants); session list + revoke (CON-30) |
| **Home** | platform health glance: relay lag, **IdP event sync (last event, lag, DLQ depth — docs/43 §5)**, provider health (MetaApi/Veriff/NOWPayments/Postmark up/degraded — from 08/04 health endpoints), open CRITICALs (CON), last deploy + version (OPS-24), backup last-success + RPO (06) |
| **Tenants (V1 minimum)** | list (id, name, status, created, funded-account count) + detail (the TEN record: config, entitlements display, provisioning saga state if in-flight) — read-only in V1; the wizard lands with V2 CON-03 (V1 provisioning is the TEN API + the saga visible here, FunderBlu's onboarding happens during Phase 1 anyway) |
| **Search (V1)** | tenant id/name (CON-02 early); global entity search (accounts/traders across tenants) = V2 CON-17 |

### 3.2 Incident controls (CON-15 — designed V1, full V2)

The emergency-stop ladder (each rung a 2FA'd action, critical audit,
runbook link in the dialog — the dialog shows the runbook, not just the
button):

1. **Tenant halt** (LCC-33 class, 07): pause all accounts of one tenant —
   trading halts, no new purchases, payouts freeze (in-flight settle).
   Use: tenant-side incident, provider abuse by a tenant.
2. **Platform maintenance mode** (CON-16, V2): banner + purchase/payout
   intake off (trading continues — it's broker-side, we can't stop it; the
   banner tells traders "platform maintenance, trading unaffected").
3. **Relay pause** (04): the outbox relay stops draining (events queue in
   the outbox — **trading and enforcement are unaffected**; 04 §3.2: the
   relay never gates the hot path). Use: consumer incident.
4. **Flag override** (CON-31, V2): Flipt kill-switches — EVL evaluation
   pause (emergency stop EVL-51's admin face), a rail circuit force-open,
   auto-approve force-off.
5. **Platform halt** (last): API intake off (Cloudflare + GW flag),
   trading continues (broker-side), staff surfaces stay up. Use: active
   breach response.

Every control's dialog states: what keeps working (trading, broker sync,
payouts-settled) and what stops — **the "what keeps working" text is
mandatory in the UI** (an operator under stress must never guess the
blast radius).

### 3.3 Impersonation (CON-07, V2)

The only cross-realm entry: `view-as {tenant, identity}` from a tenant
detail → opens the TD/ADM **in a clearly-badged read-only session**
(banner: "You are viewing as X — platform:owner {name}"). Rules: ≤ 15 min
per session, renewable (each renewal re-2FA'd), **read-only** (the
impersonation session's GW token carries a `readonly` claim — any
state-changing route 403s, structurally), every request audited with the
real operator id, and a hard deny-list: **payout approve, credential
reveal, and settings write are never available in any impersonation
session, any role** (the platform can see; the platform does not act as a
trader or tenant staff).

### 3.4 Cross-tenant observability (V2)

- **Platform audit view (CON-09):** the AUD mirror (05) cross-tenant —
  the security/compliance search (by actor, entity, event, tenant, time);
  every search itself audited.
- **Usage metering (CON-10):** per-tenant consumption (accounts, API
  calls, storage, events/day) — the inputs to BIL (V3) and to "is this
  tenant within its plan?" (the CON-05 entitlements enforcement reads it).
- **Queue overview (CON-25):** every tenant's queue depths (payout/KYC/
  risk/support) on one screen — a tenant whose payout queue sits at 40
  for a week is a churn (and reputational) risk the platform sees first.
- **Abuse signals (CON-13):** RSK's cross-tenant inputs (IP/device clusters
  spanning tenants — the tenant that onboards the worst 1% of traders) —
  read-only in the console; action = CON-06/RSK territory.
- **Jobs dashboard (CON-21):** every advisory-lock job (06): last run,
  duration, next due, lock holder, failure count — the "why is nothing
  reconciling" answer in one screen.

### 3.5 Two-operator approval (CON-32, V2)

The nuclear set (tenant suspend/terminate, platform halt, relay pause,
flag kill-switches) requires: operator A initiates (2FA) → operator B
approves (2FA, within 10 min, sees the exact action + blast-radius text) →
executes. B must not be A (structural: the approval token names A; a
self-approval is a 403, not a warning). The pattern is **pre-built in
V1** for tenant halt (the one V1 nuclear action) so V2 doesn't retrofit
safety.

## 4. Events (topic `console`)

| Event | When | Consumers |
|---|---|---|
| `console.operator_action` | any 2FA'd action (control, suspension, impersonation) | AUD (critical), NOT (ops channel) |
| `console.escalation_approved` (V2) | second operator approves | AUD (critical) |
| `console.impersonation_started/ended` (V2) | view-as lifecycle | AUD (critical) |
| `tenant.*` (TEN) | provisioning/saga/suspension — produced by TEN, surfaced in console | CON (ops alerts), AUD |

Consumes: `system.*` (OPS), `tenant.*`, relay/provider health polls,
`audit.*` (for the platform audit view's live tail).

## 5. Lifecycles

- **Console session:** §1/§3.1 (15 min idle, concurrent, revocable,
  anomaly-scored).
- **Provisioning saga (via CON-03 wizard):** the 03 §3.1 machine —
  the wizard is a live view of the saga (step state, blockers, retry
  button per failed step — the saga's compensation steps are operator-
  driven from here).
- **Tenant status (CON-06):** `active → suspended (2FA + V2 two-op) →
  terminated (two-op, runbook, data-retention handoff to AUD/DOC
  retention jobs)`.
- **Incident control:** `armed (2FA) → [V2: pending_approval → ]
  active → (restored) → post-incident note required within 24 h
  (the CON-28 V2 incident process ties the note to the action's audit
  chain)`.
- **Impersonation session:** §3.3 (15 min, renewable, read-only).
- **Announcement (CON-14, V2):** `draft → scheduled → visible (banner in
  TD/ADM, per-tenant or platform) → expired`.

## 6. Error taxonomy
### 6.1 V1 baseline codes — authoritative

From `contracts/errors/taxonomy.md` (the V1 execution sheet; module CON). These are the exact codes the V1 surfaces return; the envelope is GW-18 (`code`, `message`, `correlation_id`).
| Code | HTTP | Meaning | User-facing message |
|---|---|---|---|
| `console.session_not_found` | 404 | Session id unknown | "Session not found." |
| `console.cannot_revoke_self` | 400 | Revoking own session via admin endpoint | "You cannot revoke your own session here." |


Namespace `CON`:
### 6.2 Extended (post-V1) codes — design-level

> Below the V1 baseline (6.1); names in the GW-18 dotted convention. Rows duplicating a V1 baseline code were folded into the baseline table (the merged registry: docs/30).


| Code | HTTP | Meaning |
|---|---|---|
| `con.platform_role_required` | 403 | Non-platform session on a console route (structural deny — also logged as a security event) |
| `con.tenant_not_found` | 404 | — |
| `con.saga_blocked` | 409 | Provisioning step can't retry (blocker named) |
| `con.approval_required` | 403 | Nuclear action without the V2 second operator |
| `con.approval_expired` | 409 | Approval window (10 min) passed |
| `con.self_approval` | 403 | B == A (structural deny, security event) |
| `con.impersonation_read_only` | 403 | State-changing call under a view-as token |
| `con.impersonation_denied` | 403 | Deny-listed action (payout approve etc. — security event + CRITICAL) |
| `con.control_active` | 409 | Can't arm a control that's already active |
| `con.suspension_terminal` | 409 | Act on a terminated tenant (retention reads only) |

## 7. API endpoints
### 7.1 V1 baseline — `con` (authoritative: `contracts/api/con.md`)

| Method + path | Auth | Permission | Idempotency | V1 errors |
|---|---|---|---|---|
| `POST /v1/console/auth/login` | none (public console login) — CON-01 | none | optional | `auth.invalid_credentials`, `auth.totp_required` |
| `POST /v1/console/auth/logout` | Super Admin console session — CON-01 | self-action | optional | standard |
| `POST /v1/console/sessions/{session_id}/revoke` | Super Admin (a different one) — CON-30 | `console.session.revoke` # CON-30 | required | `console.session_not_found`, `console.cannot_revoke_self` |

Scope, request/response shapes, and per-endpoint notes: `contracts/api/con.md` (field values in the research are owner TODOs until contract freeze; canonical JSON is fixed at freeze, per the docs/99 §12 rules).

### 7.2 Extended (post-V1) surface — provisional

> Not in the V1 execution sheet. Design-level; paths beyond the V1 baseline are provisional until the URL-plan decision (`contracts/api/gw.md`, open question). Shown for platform completeness (V2/V3 phases, docs/99).

All under `/v1/console/*` (platform realm):
`GET /v1/console/health` (home screen),
`GET /v1/console/tenants` (+ search), `GET /v1/console/tenants/{id}`
(detail: TEN record, saga state, entitlements, usage, queue depths),
`POST /v1/console/tenants` (provision — V2 wizard; V1 = the TEN API
directly), `POST /v1/console/tenants/{id}/saga/{step}/retry` (V2),
`POST /v1/console/tenants/{id}/suspend` / `/terminate` (2FA + two-op V2),
`POST /v1/console/controls/{tenant_halt|maintenance|relay_pause|platform_halt}`
(+ `/release`), `GET /v1/console/controls` (state of all rungs),
`POST /v1/console/flags/{key}` (V2, Flipt override, 2FA),
`GET /v1/console/jobs` (CON-21), `GET /v1/console/deploy` (CON-12: last
deploy, version, image digest, rollback link),
`GET /v1/console/audit?…` (CON-09 cross-tenant search, owner role),
`GET /v1/console/metering?tenant=` (CON-10),
`POST /v1/console/impersonation` (V2, 2FA → view-as token),
`GET /v1/console/security` (CON-22: failed logins 24 h, anomaly blocks,
open security events, cert expiries — OPS-35),
`GET|POST /v1/console/reference` (CON-23: the master data — provider
registry, error code registry (30), event catalog (31) — read + V2
admin), `GET /v1/console/sessions` (+ `DELETE` revoke) (CON-30).
## 8. Schema (key shapes)

```jsonc
// GET /v1/console/health
{ "data": { "as_of": 1758282150000,
    "relay": { "state": "ok", "lag_ms": 120 },
    "providers": { "metaapi": "up", "veriff": "up", "nowpayments": "up",
                   "postmark": "up", "match2pay": "up" },
    "tenants": 1, "funded_accounts": 214,
    "criticals_open": 0,
    "deploy": { "version": "1.0.3", "at": 1758270000000, "digest": "sha256:…" },
    "backup": { "last_wal": "4m ago", "last_full_ok": true } } }

// control arming response
{ "data": { "control": "tenant_halt", "tenant_id": "01J9TEN…",
    "state": "active", "arming": { "by": "01J9…", "at": 1758282200000,
    "keeps_working": ["broker_sync", "trading", "payout_settlement"],
    "stops": ["new_purchases", "payout_requests", "account_transitions"] } } }
```

## 9. Database design

The console owns almost no tables (it triggers domains):

```sql
CREATE TABLE console_controls (                  -- control state (source of
  control     TEXT PRIMARY KEY,                  -- truth for what's armed)
  tenant_id   ULID,                              -- NULL = platform-wide
  state       TEXT NOT NULL DEFAULT 'disarmed'
    CHECK (state IN ('disarmed','pending_approval','active')),
  armed_by    ULID, approved_by ULID,
  armed_at    TIMESTAMPTZ, approved_at TIMESTAMPTZ,
  runbook     TEXT NOT NULL,                     -- the link shown in dialogs
  note        TEXT                               -- required on release
);
CREATE TABLE console_impersonations (            -- V2 audit table (AUD mirrors
  id          ULID PRIMARY KEY,                  -- it too)
  tenant_id   ULID NOT NULL, identity_id ULID NOT NULL,
  operator_id ULID NOT NULL,
  started_at  TIMESTAMPTZ NOT NULL, ends_at TIMESTAMPTZ NOT NULL,
  renewed     INT NOT NULL DEFAULT 0
);
CREATE TABLE console_announcements (             -- V2 CON-14
  id          ULID PRIMARY KEY,
  scope       TEXT NOT NULL,                     -- 'platform' | tenant_id
  title       TEXT NOT NULL, body TEXT NOT NULL,
  visible_from TIMESTAMPTZ, visible_to TIMESTAMPTZ,
  created_by  ULID, created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- everything else (tenants, sagas, entitlements, audit, jobs) is read from
-- TEN/OPS/AUD/ANA — the console renders, it doesn't store.
```

## 10. Security & compliance

- **Realm separation is structural** (§2): the GW rejects non-platform
  sessions on console routes; the console realm's sessions live in the
  same PG sessions table but a different org — a stolen trader cookie
  cannot reach the console, and a console cookie cannot reach TD/ADM
  (except the audited, read-only impersonation, V2).
- **2FA mandatory, all platform roles, no exemptions** (§3.1) — the
  platform operator account is the crown jewel; login anomaly scoring
  (02 §3.7) applies with the strictest thresholds (a new-country login
  for a platform operator = block + CON-22 alert, not just MFA).
- **Two-operator on the nuclear set** (§3.5) — pre-built in V1 for tenant
  halt; the `console_controls` table makes the state auditable (who armed,
  who approved, when, with which runbook).
- **Cross-tenant reads are critical-tier audit** (§2) — the platform's
  own compliance posture: if we audit tenants' access, we audit ours
  harder. The CON-09 search is itself logged (who searched for what).
- **Impersonation deny-list** (§3.3): payout approve, credential reveal,
  settings write — never, any role, in a view-as session; an attempt is a
  CRITICAL security event (it means someone probed the boundary).
- **Tenant termination** (CON-06): two-op + the data-handoff runbook
  (what's retained: AUD 7-10 yr, ledger 7 yr, documents 7 yr; what's
  deleted: the rest, with the deletion audit — the retention clocks from
  each module doc, coordinated here).
- **Secrets hygiene:** the console never displays secrets (provider keys
  = "set/reset" flows, never "view" — 06 SOPS posture; the CON-20
  registry shows key *state* (fingerprint, last rotation), not values).

## 11. Scalability considerations

- Users: 5-15 platform operators; concurrency irrelevant — the design
  costs are the safety features, not the throughput.
- Cross-tenant queries (audit search, metering, queue overview): the ANA
  read models + indexed AUD mirror handle it at V1/V2 scale (the audit
  mirror at 10M rows: the (tenant, entity, time) index + partition by
  month — the 05 design already partitions it).
- Job dashboard: reads the job state rows (06) — one indexed read.
- The health screen polls (5 s) five health endpoints — each sub-10 ms;
  SSE for the criticals feed (V2 CON-33).
- At 10× tenants: every cross-tenant surface is a read-model query —
  the scaling story is ANA's, not the console's.

## 12. Open-source solutions

| Option | Verdict |
|---|---|
| **Next.js 15 (web/con, binding stack)** | **CHOSEN** — fourth app in the monorepo; the shared design system (web/shared) makes it the cheapest surface on the platform |
| **Flipt** (flags, register) | CHOSEN — the CON-31 override surface is Flipt's admin API behind our 2FA/two-op wrapper |
| **Uptime Kuma** (register) | CHOSEN — external checks feed the health screen (its API); internal health = the providers' own endpoints |
| Portainer/Grafana as the console | Rejected: system-ops tools for the DevOps role; the console is the **business-ops** surface (tenants, sagas, controls) — Grafana stays in Grafana, linked from CON-08 |
| ZITADEL SSO (register) | Platform operators can federate to FunderBlu's own IdP through the same ZITADEL instance (`AUTH-24` is V1 by decision D2); no second IdP product |

## 13. Technology stack

Next.js 15 (web/con), TypeScript, Tailwind, shadcn/ui, SSE, ZITADEL (console
application/audience), Casbin (platform:* policies), Flipt, Postgres (the small
console tables + read access), Uptime Kuma API, Prometheus/Grafana
(linked), Sentry.

## 14. Integration — internal modules (glue)

| Module | How |
|---|---|
| **TEN** | the provisioning saga (03 §3.1) is driven + watched here; entitlements (CON-05); suspension/termination (CON-06) |
| **AUTH** | the platform realm (02 §3.4); 2FA/step-up; anomaly scoring (the strictest tier); platform identity administration (`platform.identity.admin` — staff onboarding/offboarding, forced MFA reset AUTH-28, break-glass) and the tenant-provisioning saga actions (`platform.tenant.provision`, docs/03 §3.5) |
| **OPS** | health (relay, backup, deploy), jobs (CON-21), security overview inputs (certs, hardening state — OPS-13/35) |
| **AUD** | the platform audit view (CON-09); every console action mirrored; the termination data-handoff |
| **ANA** | platform KPIs + metering (CON-10) + cross-tenant queue overview (CON-25) |
| **RSK** | cross-tenant abuse signals (CON-13) |
| **EVL** | the emergency-stop flag (EVL-51) is rung 4 of the control ladder |
| **BIL** (V3) | subscriptions & contracts (CON-24) render the BIL records |
| **NOT** | ops-channel alerts (control armed, criticals, approval pending) |
| **SUP/ADM** | cross-tenant support assist (CON-27 V2): the console opens a
  read-only view of a tenant's tickets (the impersonation pattern,
  tenant-staff-targeted) |

## 15. Integration — external tools

ZITADEL, Casbin, Flipt, Uptime Kuma, Prometheus/Grafana (linked
dashboards), Sentry, (V3) Keycloak/SSO.

## 16. Implementation blueprint

| Step | Owner | Est | Depends | Exit criteria |
|---|---|---|---|---|
| 1. Platform realm (ZITADEL console application/audience, platform:* roles, Casbin policies, 2FA-mandatory) + session management (list/revoke) | BE-1 | 2 d | AUTH | a platform operator logs in on the console subdomain; a trader/tenant-staff token is structurally rejected (tested both ways) |
| 2. Shell + home screen (health, providers, criticals, deploy, backup) + tenant list/detail (read) | FE-2 + BE-1 | 4 d | 1, OPS health endpoints, TEN read APIs | the wall screen renders live on staging; every number has an as_of |
| 3. Tenant halt control (rung 1): arming (2FA), state table, "keeps working/stops" dialog, release with note, audit | BE-1 + FE-2 | 2.5 d | 2, LCC-33, TEN | halt on staging tenant: purchases/payouts/requests stop, broker sync + trading continue (the test matrix), release + audit chain complete |
| 4. Two-operator approval wiring (A arms → B approves, self-approval 403) — built for tenant halt now, the template for V2 | BE-1 | 1.5 d | 3 | self-approval rejected; approval expiry works; the CON-32 flow is reusable (code review) |
| 5. V2: provisioning wizard (CON-03, live saga view + step retry), impersonation (view-as read-only + deny-list + 15 min), platform audit view, metering, jobs dashboard, security overview, queue overview, abuse signals, announcements, flag overrides (Flipt), maintenance mode, incident notes, notification centre, action-approval rollout to all rungs | FE-2 + BE-1 | 4 wks | 3–4 + V2 backend surfaces | full V2 exit: a new tenant provisioned end-to-end from the wizard; a drill (quarterly, 06-adjacent) walks the whole control ladder on staging |

**Risks:** the console becoming a bypass surface (mitigation: it triggers
domains, never writes their data — the same LCC-41 rule generalized, and
the impersonation deny-list makes the read boundary structural);
operator-account compromise (mitigation: 2FA-mandatory, strictest anomaly
scoring, two-op on the nuclear set, every action critical-audited — the
console is designed as if a breach of it is a given); scope drift toward
"admin-of-admins" gold-plating (mitigation: every V2 screen maps to a
named CON requirement; the 28 V2 items are the ceiling).

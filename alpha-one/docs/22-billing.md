# 22 — BIL: Tenant Billing (Platform Revenue)

> Covers PRD module **BIL** (21 requirements — 20 of them V3). This is the
> platform's own billing of **tenants** (FunderBlu and future firms):
> subscription plans + usage charges for running on Alpha One. It is
> distinct from CHK (trader→tenant money) and PAY (tenant→trader money):
> BIL is **tenant→platform** money, and it starts as the manual-contract
> era (V1/V2: FunderBlu pays by contract/invoice, no self-serve) and
> becomes productized in V3.

## 1. Purpose & scope

**V1/V2 (0 PRD reqs, but binding behavior):** **manual contract mode
(BIL-16, pulled forward as V1 reality)** — FunderBlu's commercial terms
live in the contract; the console records them (`tenants.commercial`
config: plan name, usage limits, payment schedule); metering (CON-10)
tracks usage against the contract for the quarterly review; there is
**no billing engine in V1/V2** — invoicing is off-platform (the contract
process), and the platform's revenue reports (ANA-14 V3 / CON-19 V2) read
the recorded invoices, not a billing system.

**V3 (20):** the productized engine: plan catalog (BIL-01), add-ons
(BIL-02), subscription records (BIL-03), entitlement sync (BIL-04 —
the CON-05 entitlements become billing-driven), recurring invoicing
(BIL-05), **usage charge computation (BIL-06 — from CON-10 metering:
funded accounts, payout volume, API calls, storage)**, B2B collection
(BIL-07 — wire/ACH primary; card via provider), dunning & grace (BIL-08),
proration (BIL-09), swap discounts (BIL-10), trials (BIL-11), invoice
documents & delivery (BIL-12 → DOC), billing portal (BIL-13), platform
revenue reports (BIL-14), billing events & audit (BIL-15), manual
contract mode stays (BIL-16 — the FunderBlu path never goes away),
pass-through cost billing (BIL-17 — provider costs passed through:
MetaApi per-account fees, provider fees above a margin), billing approval
workflow (BIL-21), invoice templates (BIL-19), self-serve signup
(BIL-18 — the multi-tenant-farming endgame).

Requirement coverage: V1/V2 = `BIL-16`-class manual mode + CON-10
metering (the engine's input, built early by design) + `BIL-21` approval
workflow early (invoice approval in the console, V2) + the 18 remaining
(V3).

## 2. Architecture

```
 V1/V2:  contract terms (tenants.commercial config, CON-05 entitlements)
          + metering (CON-10 ← ANA rollups: accounts, payout volume, API
          calls, storage, events) → quarterly review in the console →
          off-platform invoice (recorded in console: amount, period, status)

 V3:     metering events (EVT: api.call rollups, account.created,
          payout.settled volume, storage deltas) ──► BIL (Lago, self-hosted):
            plan catalog + subscription state (the engine of record)
          Lago webhooks ──► platform:
            invoice.created ─► DOC (invoice PDF, tenant-branded-billing)
                            ─► NOT (email) ─► CON (billing queue)
            payment.succeeded/failed ─► dunning (BIL-08) ─► entitlement
                            sync (BIL-04: CON-05 reads subscription state —
                            grace period = degraded service banner, not
                            outage; the ladder: 7 d past due = dunning
                            emails, 30 d = tenant pause (CON-06 class,
                            two-op), 60 d = termination flow)
            entitlements ─► TEN config write (the same 9-step saga's
                            entitlement step, driven by billing state)
          BIL portal (BIL-13): invoices, usage, payment methods (tenant
          staff, console realm)
```

**Chosen engine: Lago (self-hosted, AGPL-3.0)** — the research file's
recommended hybrid, and the register-consistent license posture (AGPL
self-hosted was already accepted for Hook0). Lago gives: usage-based
billing natively (metering API), multi-tenancy, invoicing, dunning,
multi-gateway, webhooks — the 70% we don't want to build. Kill Bill was
the alternative (Apache-2.0, battle-tested, Java) — rejected on the
integration surface: Lago's modern REST + the Rust-backed core fits a
Go/Node shop better than a Java plugin stack, and its AGPL is the same
class we already accept. **Custom (prop-firm-specific) parts stay ours:**
the metering event definitions (from ANA rollups), the entitlement-sync
contract with TEN, the pass-through cost model (BIL-17 — Lago doesn't
model "we pass MetaApi's per-account fee through at cost + 5%"), and the
console billing queue.

## 3. System design

### 3.1 Metering (the part built in V1/V2, deliberately)

The metering facts come from **ANA rollups**, not raw events (ANA §2
principle: read models, not the hot path):

| Meter | Source | Billed as |
|---|---|---|
| `funded_accounts` (peak concurrent) | `accounts_ro` | plan tier / unit charge |
| `payout_volume` (settled, monthly) | `payouts_daily` | % charge (the platform's take on money moved) |
| `api_calls` (external SDK, monthly) | GW rollup (external-key calls only — internal calls free) | unit charge |
| `storage_mb` (R2, monthly) | R2 usage report | unit charge |
| `kyc_verifications` (monthly) | KYC session rollup | unit charge (provider cost pass-through, BIL-17) |
| `events_outbound` (Hook0 deliveries) | EVT delivery rollup | unit charge |

The metering rollup job (workers, nightly) writes `metering_daily`
(tenant, meter, day, value) — **the CON-10 screen reads it; the V3 Lago
feed reads it; the quarterly review reads it.** One metering table, three
eras. The nightly job is advisory-locked (06) and its output is
reconcilable against the ANA models it reads (the ANA-21 pattern).

### 3.2 Plans (V3 BIL-01/02 — the shape, for the contract to reference)

```
plan: { name, base_monthly_cents, currency,
  limits: { funded_accounts, api_calls_mo, storage_gb, kyc_mo, events_mo },
  overage: { per_funded_account_cents, per_1k_api_calls_cents,
             per_gb_cents, per_kyc_cents, per_1k_events_cents,
             payout_volume_bps } }
addons: { extra_seats, priority_support, extra_white_label_domain,
          custom_rules_consulting, dedicated_backup_retention }
```

The V1 contract with FunderBlu maps onto this shape (its "plan" is
recorded in `tenants.commercial` in exactly these fields) — so V3
productization is a **migration of recorded contracts into the catalog**,
not a renegotiation. That's the whole reason the metering shape is
frozen in V1.

### 3.3 Lifecycle & dunning (V3 BIL-03/08/09)

```
trial (BIL-11, 14 d, sandbox-only — staging is synthetic-only, 06 §2;
  a trial tenant = a staging-tenant, never a prod tenant with fake data)
→ active (invoice cycle: monthly) → past_due (grace: service continues,
  dunning ladder, entitlements "degraded" flag = console banner for the
  tenant staff, NOT emails) → paused (30 d: CON-06-class pause, two-op —
  their tenants' trading CONTINUES, onboarding/purchases freeze) →
  terminated (60 d: the CON-06 termination flow, retention handoff)
proration (BIL-09): plan change mid-cycle = Lago's standard proration,
  shown on the next invoice line (the "why did the invoice change" answer)
```

### 3.4 Pass-through costs (BIL-17 — the prop-firm-specific model)

Provider costs the platform pays on a tenant's behalf (MetaApi
per-account fees — 08's cost-control note, Veriff verification fees,
payment provider fees above margin) are billed back **at cost + a
disclosed margin %** (per provider, in the plan config). Lago models this
as a pass-through charge item; the cost facts come from the same metering
rollups (the provider fee fields on `payments_daily`/`payouts_daily` —
CHK §3.6 and PAY §3.6 already capture actual provider fees for
reconciliation, BIL reads those). The tenant's invoice shows the pass-
through lines **separately from platform fees** (transparency = the
contract trust).

### 3.5 Invoice & payment (V3 BIL-05/07/12/14/21)

- Invoice: Lago generates → webhook → **DOC renders the PDF** (tenant-
  billing-branded, §15 DOC contract) → NOT emails → CON billing queue.
- Payment: B2B = **wire/ACH primary** (the BIL-07 reality for PK/IN +
  global B2B), card via provider for smaller tenants; manual contract
  mode (BIL-16) tenants are invoiced + marked paid by a finance operator
  (2FA) — the FunderBlu path.
- Approval workflow (BIL-21, early in V2): any **manual** invoice (credit
  notes, adjustments, contract-mode invoices) requires two-op approval
  in the console before issue (the CON-32 pattern reused — platform
  money-out-adjacent actions get the same treatment as tenant-halt).
- Revenue reports (BIL-14): MRR/ARR, churn, usage-vs-plan by tenant,
  pass-through margins — in CON-19 (the platform financial overview)
  from V2 (contract-mode data) and V3 (Lago data).

## 4. Events (topic `billing`)

| Event | When | Consumers |
|---|---|---|
| `billing.metering_recorded` | nightly rollup (V1+) | CON (metering view), AUD (low) |
| `billing.invoice_created` (V3) | Lago webhook | DOC, NOT, CON (billing queue), AUD |
| `billing.payment_succeeded/failed` (V3) | Lago webhook | AUD |
| `billing.subscription_state_changed` (V3) | active/past_due/paused/terminated | TEN (entitlement sync BIL-04), CON, NOT, AUD (critical on pause/terminate) |
| `billing.entitlement_degraded` (V3) | grace flag set | TEN (banner), NOT |
| `billing.credit_note_issued` (V3) | adjustment | CON, AUD (critical) |

Consumes: ANA metering rollups (V3 feed → Lago metering API), CON-06
suspension events (a tenant paused for cause ≠ past_due — the state
machines must not collide: cause-pause wins, billing state preserved).

## 5. Lifecycles

- **Contract/subscription:** §3.3 machine (contract mode: `active →
  renewed | amended (versioned terms) | terminated`).
- **Invoice:** `draft → (approval, BIL-21) → issued → paid | past_due →
  (dunning) → written_off (two-op) | credit_noted`.
- **Metering record:** append-only daily rows; corrections = new rows +
  the correction note (never an edit — the ANA-21 reconciliation reads
  them).
- **Dunning ladder:** `1 (7 d: email) → 2 (14 d: email + console alert) →
  3 (21 d: final notice + owner escalation) → pause (30 d) → terminate
  (60 d)` — the ladder is config (plan-level), the timers run in the
  workers process (advisory-lock).
- **Trial (V3):** staging-tenant lifecycle (06 synthetic-only rule — a
  trial is a sandbox experience; the conversion = the 9-step provisioning
  saga, 03).

## 6. Error taxonomy

Namespace `BIL`:

| Code | HTTP | Meaning |
|---|---|---|
| `bil.tenant_not_billable` | 422 | Metering/invoice op on a contract-mode tenant in V1/V2 (the era guard — the API says "manual mode; record in console") |
| `bil.plan_invalid` | 422 | (V3) Plan/limit mismatch |
| `bil.approval_required` | 403 | Manual invoice issue without two-op (V2+) |
| `bil.state_conflict` | 409 | Subscription transition conflict (e.g. pause on an already-terminated tenant) |
| `bil.metering_stale` | 409 | Invoice computed before the metering rollup completed (retry — the rollup is nightly; same-day invoices use yesterday's + a flag) |
| `bil.gateway_unavailable` | 503 | (V3) Payment provider down (invoice stays issued; dunning clock is provider-tolerant) |
| `bil.pass_through_unconfigured` | 422 | (V3) Provider cost line with no margin config (fail closed: the invoice can't be issued with an unknown pass-through) |

## 7. API endpoints
> **Scope note:** BIL (platform revenue) is not in the V1 execution sheet (V3 scope — V1 tenants are invoiced manually per 00 §4). There is no V1 baseline contract for this module; the surface below is design-level (post-V1, docs/99) and provisional until its phase's contract freeze.


Staff (CON — billing surfaces live in the console):
`GET /v1/console/metering?tenant=&meter=&range=` (V1+),
`GET|POST /v1/console/billing/contracts` (contract-mode terms, versioned;
V1+ — the FunderBlu contract record),
`POST /v1/console/billing/invoices` (manual/contract-mode invoice, 2FA;
V2+ approval),
`POST /v1/console/billing/invoices/{id}/mark-paid` (2FA + proof ref),
`GET /v1/console/billing/invoices` (all modes),
`GET /v1/console/billing/revenue` (BIL-14/CON-19: MRR/ARR/churn/pass-
through margins),
V3: `GET /v1/console/billing/plans` (+ catalog admin),
`POST /v1/console/billing/subscriptions` (create/change → Lago),
`POST /v1/console/billing/credits` (credit notes, two-op),
`GET /v1/billing/portal/*` (BIL-13: tenant-staff portal: invoices, usage
vs plan, payment methods — console realm, tenant-scoped).

## 8. Schema (key shapes)

```jsonc
// GET /v1/console/metering (the V1 shape — frozen for the V3 migration)
{ "data": { "tenant_id": "01J9TEN…", "range": "2026-09",
    "funded_accounts_peak": 214, "payout_volume_cents": 482000000,
    "api_calls": 1842000, "storage_mb": 9200, "kyc_verifications": 131,
    "events_outbound": 960000,
    "vs_plan": { "funded_accounts": "98%", "api_calls": "61%",
                 "payout_volume": "within", "overage_projected_cents": 0 } } }

// V3 invoice line (Lago-rendered, DOC PDF)
{ "lines": [ { "kind": "platform_base", "label": "Scale plan (monthly)",
                "amount_cents": 250000 },
              { "kind": "usage", "label": "API calls overage (842k)",
                "amount_cents": 126300 },
              { "kind": "pass_through", "label": "MetaApi account fees (214 × $75, +5% margin)",
                "amount_cents": 1690000, "note": "at cost + 5%" } ] }
```

## 9. Database design

```sql
-- V1+ (platform-owned):
CREATE TABLE metering_daily (
  tenant_id ULID NOT NULL, meter TEXT NOT NULL,
  day DATE NOT NULL, value BIGINT NOT NULL,
  source TEXT NOT NULL,                    -- 'ana_rollup'|'r2_report'|'gw_rollup'
  PRIMARY KEY (tenant_id, meter, day)
);
CREATE TABLE tenant_contracts (             -- BIL-16 contract-mode record
  id          ULID PRIMARY KEY,
  tenant_id   ULID NOT NULL,
  version     INT NOT NULL DEFAULT 1,       -- amended terms = new version
  plan_name   TEXT NOT NULL,
  base_monthly_cents BIGINT NOT NULL,
  currency    CHAR(3) NOT NULL,
  limits      JSONB NOT NULL,               -- the §3.2 shape
  pass_through_margin_bps JSONB NOT NULL,   -- per provider
  payment_terms TEXT NOT NULL,              -- 'net_30_wire' | …
  active_from DATE NOT NULL, active_to DATE,
  created_by  ULID, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, version)
);
CREATE TABLE platform_invoices (            -- all modes (V3: Lago refs)
  id          ULID PRIMARY KEY,
  tenant_id   ULID NOT NULL,
  mode        TEXT NOT NULL,                -- 'contract'|'lago'
  period_from DATE NOT NULL, period_to DATE NOT NULL,
  lines       JSONB NOT NULL,               -- §8 shape
  total_cents BIGINT NOT NULL, currency CHAR(3) NOT NULL,
  status      TEXT NOT NULL DEFAULT 'draft'
    CHECK (status IN ('draft','approved','issued','paid','past_due',
                      'written_off','credit_noted')),
  approved_by ULID, approved_at TIMESTAMPTZ,   -- BIL-21 (two-op in V3;
  paid_at     TIMESTAMPTZ, payment_ref TEXT,  -- 2FA in V2)
  lago_ref    TEXT,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_plinv_tenant ON platform_invoices(tenant_id, period_from DESC);
-- V3 adds: plans, plan_addons, subscriptions (Lago is the engine of
-- record; these rows cache the tenant-facing state for CON/portal reads)
```

## 10. Security & compliance

- **Money discipline (platform-side):** manual invoices are
  approval-gated (BIL-21: 2FA in V2, two-op in V3 — the CON-32 pattern);
  credit notes are two-op always (money back is the direction that needs
  the most control); `mark-paid` requires a payment proof ref (bank ref /
  provider ref) — the same discipline as CHK's wire capture (12 §3.2).
- **Tenant data in billing:** metering is aggregate (counts/cents/MB — no
  PII, no trader names); the portal (BIL-13) is tenant-scoped console
  realm; cross-tenant revenue reads = platform:finance/owner, critical
  audit (the CON-09 posture).
- **Pass-through transparency** (§3.4): the margin is disclosed per line —
  a tenant can reconcile the pass-through to the provider's own statement
  (the trust property; it's also the anti-"hidden margin" contract clause).
- **Trial = sandbox** (§5): no prod tenant ever exists in trial state —
  the staging synthetic-only rule (06) makes this structural.
- **Lago as processor:** self-hosted (AGPL), same trust boundary as our
  other self-hosted components; tenant payment data (card tokens) is
  Lago/provider-side (SAQ-A posture, the CHK §10 pattern); Lago webhooks
  verified (EVT-10 ingress pattern) — a forged `payment_succeeded` is an
  anomaly, not a state change.
- **Retention:** invoices + contracts 7 yr (the AUD/LED class); metering
  3 yr (the reporting class); dunning emails retained with the invoice.

## 11. Scalability considerations

- Metering: one nightly rollup job reading ANA models — seconds at any
  tenant count (the rollups are already aggregated by design, ANA §3.1).
- V3 Lago: sized for 10-100 tenants × monthly cycles — a single Lago
  instance is overkill-provisioned at that scale; its own workers handle
  the invoice/dunning timers (we don't add timers of our own — single
  source of the clock).
- The portal: read cache of subscription state (CON reads) — trivial.
- Revenue reports: monthly aggregates — trivial.
- **The scaling risk is commercial, not technical:** pass-through cost
  models that don't survive a 10× MetaApi price change are a plan-config
  problem (BIL-17 margins are data, not code) — the design keeps every
  commercial number in a config a finance operator can change without a
  deploy.

## 12. Open-source solutions

| Option | Verdict |
|---|---|
| **Lago (self-hosted, AGPL-3.0, research-recommended)** | **CHOSEN (V3)** — native usage billing, multi-tenant, invoicing, dunning, webhooks; AGPL accepted on the Hook0 precedent |
| Kill Bill (Apache-2.0, research alternative) | Rejected: Java plugin stack, heavier ops, older API; same capability surface for our needs |
| Stripe Billing (SaaS) | Rejected: data residency + the PK/IN B2B reality (wire-primary) + a second processor dependency; the adapter pattern keeps it a V3+ option for card-heavy tenant bases |
| **In-house metering + contract mode** (V1/V2, this design) | **CHOSEN** — the metering table + contract records + console approval; the engine (Lago) joins in V3 without a re-architecture (the metering shape is frozen for it, §3.1) |
| DOC + NOT + CON | V3 delivery/approval plumbing (already chosen) |

## 13. Technology stack

Go (metering rollup job, console APIs), Postgres (metering/contracts/
invoices), ANA (the rollup substrate), Lago (V3: Rust/Ruby self-hosted,
its own PG schema — the one second Postgres on the box, budgeted in 06
host specs as a V3 line), DOC (invoice PDFs), NOT (billing emails),
Flipt (no — billing state is not a flag; it's ledger-adjacent data),
Prometheus (rollup runtime, dunning timer health), Sentry.

## 14. Integration — internal modules (glue)

| Module | How |
|---|---|
| **ANA** | the metering rollups read ANA models (accounts_ro, payouts_daily, payments_daily, storage/API rollups) — BIL never re-derives from raw events |
| **CON** | the billing queue (contracts, invoices, approval, revenue view CON-19), the pause/terminate flows (CON-06) are billing-triggered in V3, the manual-triggered same flows in V1/V2 |
| **TEN** | entitlement sync (V3 BIL-04): subscription state → TEN config (the saga's entitlement step); contract terms (V1) → TEN limits (the funding caps from 03/08 read the same `limits` shape — cost control = billing control, one config) |
| **DOC** | invoice PDFs (BIL-12): the DOC contract gains a `billing_invoice` type (V3) |
| **NOT** | invoice + dunning emails (V3); the dunning ladder's messages are templates (NOT §3.4 extension) |
| **CHK** | the provider-fee facts (actual fees on payments_daily) feed the pass-through lines (BIL-17) — CHK reconciles provider fees; BIL bills them back |
| **PAY** | payout_volume meter (payouts_daily) — the platform's % charge on money moved |
| **EVT** | metering feed (V3 → Lago metering API via the workers process), billing events on the bus |
| **AUD** | every invoice action (critical), metering corrections, subscription state changes |
| **LED** | **platform** revenue recognition stays in the platform's own books (off-platform accounting — the platform's revenue is not in the tenants' LEDgers; the ANA-03 monthly financial report is per-tenant; BIL-14 is the platform's) |

## 15. Integration — external tools

Lago (V3), the payment provider for B2B collection (V3: wire/ACH via
the tenant's bank + card via a B2B-capable provider — the decision at
V3 scope, informed by the tenant base), R2 (invoice objects via DOC),
Postmark (via NOT), Prometheus/Grafana, Sentry.

## 16. Implementation blueprint

| Step | Owner | Est | Depends | Exit criteria |
|---|---|---|---|---|
| 1. (V1, Week 2 of build) `metering_daily` + nightly rollup job (6 meters) + CON-10 metering screen | BE-2 | 2 d | ANA-01, CON-10 | staging: rollup matches hand-computed values from ANA models (property test) |
| 2. (V1) `tenant_contracts` + console contract screen (record FunderBlu's terms in the §3.2 shape) + vs-plan display | BE-1 | 1.5 d | 1, CON | FunderBlu's actual contract recorded; vs-plan percentages render |
| 3. (V2) `platform_invoices` + manual invoice flow (draft → 2FA approve → issue → mark-paid with proof ref) + revenue view (MRR/ARR from contracts) | BE-1 | 3 d | 2, CON-32 | a full contract-mode invoice cycle in staging with the proof-ref requirement enforced |
| 4. (V2) dunning-timer skeleton (the ladder as config, running on contract-mode past-due) + pass-through margin config + revenue pass-through reporting | BE-2 | 2 d | 3 | a seeded past-due tenant walks the ladder (emails + console alerts); pass-through lines render with margin |
| 5. (V3) Lago deployment (self-hosted, own PG schema, SOPS secrets, its webhooks through EVT-10) + plan catalog + subscription lifecycle + entitlement sync with TEN | BE-2 | 3 wks | 4, CON-06 flows | a seeded subscription: invoice → pay → entitlements active; payment fail → dunning → pause (trading continues, purchases freeze — the test matrix) |
| 6. (V3) metering feed (metering_daily → Lago metering API), proration, pass-through charge items, portal (BIL-13), credit notes (two-op), revenue reports (Lago data), trial-as-sandbox | BE-2 + FE-2 | 3 wks | 5 | end-to-end: a tenant's month closes — usage metered, invoice correct to the cent vs metering_daily (the reconciliation test), portal shows it |

**Risks:** the V1/V2 "no billing engine" era creating an unmetered gap
(mitigation: the metering table ships in V1 week 2 — the FunderBlu
quarterly review in month 3 runs on real numbers, and the V3 migration is
a data load, not a re-implementation); Lago lock-in (mitigation: Lago is
the engine of *invoice + dunning* only — metering, contracts, approval,
and revenue truth live in our tables; swapping Lago = re-pointing the
webhooks + re-issuing invoices); pass-through disputes (mitigation: the
transparency rule — every pass-through line names the provider, the unit
count, the unit cost, and the margin %; the tenant can reconcile against
the provider's statement); dunning-vs-cause-pause collisions (mitigation:
the state precedence in §4 — cause wins, billing state preserved, no
double-suspension).

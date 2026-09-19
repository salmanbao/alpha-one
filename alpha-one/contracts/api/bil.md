# Tenant Billing API Contract (BIL)

Status: PROVISIONAL (post-V1, design-level)
Owner: TBD
Version: v1
Last updated: 2026-09-19

Derived from `docs/22-billing.md` §7 + PRD BIL-NN (V3.0). Nothing here is final until that phase's contract freeze (docs/99 §12).

## Scope

PRD module **BIL** (21 requirements). Abridged backlog:

| Req | Feature | Release | Pri | Owner | User story (abridged) |
|---|---|---|---|---|---|
| `BIL-01` | Plan catalog | V3.0 | P0 | BE-2 | As a super admin, I define plans such as Starter, Professional, and Enterprise with included modules, limits, and prices so that t… |
| `BIL-02` | Add-on catalog | V3.0 | P0 | BE-2 | As a super admin, I define à la carte module add-ons and usage rates with prices so that modular pricing works per tenant. |
| `BIL-03` | Subscription record | V3.0 | P0 | BE-2 | As the platform, I maintain a per-tenant subscription with plan, add-ons, billing period, and status including trial, active, past… |
| `BIL-04` | Entitlement sync | V3.0 | P0 | BE-2 | As the platform, on any subscription change I update tenant entitlements automatically so that access always matches what is paid … |
| `BIL-05` | Recurring invoicing | V3.0 | P0 | BE-2 | As the platform, I generate an invoice each billing cycle from plan, add-ons, and usage so that billing runs without manual work. |
| `BIL-06` | Usage charge computation | V3.0 | P1 | BE-2 | As the platform, I compute usage charges from metering counters such as traders, accounts, orders, and API calls against included … |
| `BIL-07` | B2B payment collection | V3.0 | P1 | BE-2 | As the platform, I collect tenant payments by card, crypto, or bank transfer through existing payment adapters so that we do not b… |
| `BIL-08` | Dunning and grace period | V3.0 | P1 | BE-2 | As the platform, on payment failure I enter a grace period, notify tenant admins, then suspend per policy so that non-payment is h… |
| `BIL-09` | Proration on plan change | V3.0 | P1 | BE-2 | As a super admin or tenant admin, I upgrade or downgrade a plan with mid-cycle proration so that changes are fair and predictable. |
| `BIL-10` | Swap discount rule | V3.0 | P2 | BE-2 | As a super admin, I configure discounts for tenants that bypass built-in modules in favor of their own tooling so that the modular… |
| `BIL-11` | Trial periods | V3.0 | P1 | BE-2 | As a super admin, I create time-boxed trials with full or partial entitlements so that sales can prove value before a contract is … |
| `BIL-12` | Invoice document and delivery | V3.0 | P1 | BE-2 | As a tenant admin, I receive branded invoices with line items and tax fields so that my finance team can book the cost properly. |
| `BIL-13` | portal view | V3.0 | P1 | FE-2 | As a tenant admin, I see my current plan, add-ons, next invoice, payment history, and usage so that billing is transparent and sup… |
| `BIL-14` | Platform revenue reports | V3.0 | P1 | BE-2 | As a platform owner, I see MRR, ARR, churn, revenue per tenant, and add-on attach rates so that the business itself is measurable. |
| `BIL-15` | events and audit | V3.0 | P0 | BE-2 | As the platform, I emit subscription and payment events and audit every billing change so that commercial history is fully traceab… |
| `BIL-16` | Manual contract mode | V3.0 | P1 | BE-2 | As a super admin, I mark a tenant as a manual offline contract with custom pricing and offline invoicing so that enterprise deals … |
| `BIL-17` | Pass-through cost billing | V3.0 | P2 | BE-2 | As a super admin, I bill pass-through costs such as KYC checks per verification so that variable provider costs do not erode margi… |
| `BIL-18` | Self-serve signup with billing | V3.0 | P2 | BE-2 | As a new prop firm, I can sign up, choose a plan, pay, and get a provisioned tenant without talking to sales so that acquisition s… |
| `BIL-19` | Invoice template management | V3.0 | P1 | BE-2 | As a platform owner, I manage invoice templates and variables, so that tenant invoices are branded and consistent. |
| `BIL-20` | tax profile and tax ID capture | V3.0 | P1 | BE-2 | As a tenant admin, I capture my tax ID and billing jurisdiction, so that invoices are tax- compliant. |
| `BIL-21` | approval workflow for plan changes | V3.0 | P1 | BE-2 | As a platform owner, I require approval for enterprise plan changes, so that commercial changes are controlled. |

## Auth

Platform staff via CON (invoicing, dunning) + tenant read-only (own invoices, usage). All routes sit in the GW chain (docs/04 §3.1): tenant resolution →
authn → authz (`resource.action` key per route) → rate limit → entitlement gate →
idempotency → audit. Error envelope per GW-18 (`code`, `message`, `correlation_id`).

## Tenant resolution

From domain (GW-02) for web routes; from the API key for machine routes (key wins
over any header); `X-Tenant-Id` header for internal service tokens only. Unknown
host/key → `404 tenant.not_found` (no-oracle rule, docs/04 §6).

## Permissions

No dedicated permission keys beyond the V1 registry are fixed yet — keys are proposed in the module doc's §7 and freeze with the module.

## Idempotency

Mutating requests accept an `Idempotency-Key` header per GW-12 (24 h TTL, scope =
method+path+key). Retries MUST NOT create duplicate resources.

## Endpoints (provisional)

> Copied verbatim from `docs/22-billing.md` §7 on 2026-09-19 — the module doc is authoritative if they drift; regenerate with `python3 scripts/complete_contracts_pack.py`.

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

## Open contract questions

- Paths, methods, and field names below are PROVISIONAL until this module's phase
  freeze (docs/99 §12) — additive changes only after freeze; breaking changes get
  `/v2/` + the 12-month deprecation rule for public surfaces.
- Permission keys: the V1 registry (`permissions/registry.md`) is binding; keys used
  below beyond it are provisional and join the registry at freeze.
- Error codes: V1 baseline codes are binding (`errors/taxonomy.md`); extended codes
  follow the GW-18 dotted convention and freeze with the module (docs/30).

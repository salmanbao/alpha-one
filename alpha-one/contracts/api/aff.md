# Affiliate System API Contract (AFF)

Status: PROVISIONAL (post-V1, design-level)
Owner: TBD
Version: v1
Last updated: 2026-09-19

Derived from `docs/23-affiliates.md` §7 + PRD AFF-NN (V3.0). Nothing here is final until that phase's contract freeze (docs/99 §12).

## Scope

PRD module **AFF** (30 requirements). Abridged backlog:

| Req | Feature | Release | Pri | Owner | User story (abridged) |
|---|---|---|---|---|---|
| `AFF-01` | Registration and approval | V3.0 | P1 | BE-2 | As a trader or external partner, I can apply to become an affiliate, and as admin I approve or reject applications so that the pro… |
| `AFF-02` | Referral link and code generation | V3.0 | P1 | BE-2 | As an affiliate, I get unique referral links and coupon codes so that my traffic is attributable to me. |
| `AFF-03` | Attribution tracking | V3.0 | P1 | BE-2 | As the platform, I capture referral clicks with cookie, UTM, and sub-ID and attribute the signup and purchase to the affiliate so … |
| `AFF-04` | Coupon attribution | V3.0 | P1 | BE-2 | As the platform, I attribute purchases made with an affiliate coupon even without a cookie so that code-driven sales are counted. |
| `AFF-05` | Commission rules engine | V3.0 | P1 | BE-2 | As a tenant admin, I define CPA flat fee, revenue share percentage, or hybrid per program with per-affiliate overrides so that dea… |
| `AFF-06` | Commission accrual | V3.0 | P1 | BE-2 | As the platform, I create pending commission entries on attributed paid orders so that earnings accumulate automatically without m… |
| `AFF-07` | Refund and chargeback reversal | V3.0 | P1 | BE-2 | As the platform, I reverse pending or approved commissions when the attributed order is refunded or charged back so that affiliate… |
| `AFF-08` | Commission approval window | V3.0 | P1 | BE-2 | As the platform, I move commissions from pending to approved only after a configurable refund window so that payouts are safe. |
| `AFF-09` | Affiliate dashboard | V3.0 | P1 | FE-1 | As an affiliate, I see clicks, signups, conversions, earnings, and payout history so that I can track my own business. |
| `AFF-10` | Payout request and queue | V3.0 | P1 | BE-2 | As an affiliate, I request payout above a minimum threshold, and as finance I approve and record manual execution so that affiliat… |
| `AFF-11` | Payout history and receipts | V3.0 | P2 | FE-1 | As an affiliate, I see my payout history and download receipts so that my records are complete. |
| `AFF-12` | Self-referral fraud detection | V3.0 | P1 | BE-2 | As the platform, I detect and flag self-referrals where the affiliate and the referred trader share user, IP , or device so that p… |
| `AFF-13` | Affiliate management admin | V3.0 | P1 | FE-1 | As a tenant admin, I list affiliates, approve or reject, set custom rates, and blacklist so that program operations are manageable… |
| `AFF-14` | Affiliate reports | V3.0 | P2 | BE-2 | As a tenant admin, I view conversions, earnings, and top affiliates so that program return on investment is visible. |
| `AFF-15` | Conversion webhook for BYO affiliate | V3.0 | P2 | BE-2 | As a tenant using an external affiliate tool, I receive signed conversion webhooks so that my external tool can attribute and pay … |
| `AFF-16` | Marketing materials library | V3.0 | P2 | FE-1 | As an affiliate, I access banners and copy provided by the tenant so that promotion is easy and on brand. |
| `AFF-17` | Affiliate events | V3.0 | P1 | BE-2 | As the platform, I emit referred, commission earned, commission approved, and commission paid events so that notifications and rep… |
| `AFF-18` | Multi-tier commissions | V3.0 | P2 | BE-2 | As a tenant admin, I configure multi-tier (MLM-style) commissions so that affiliates earn from sub-affiliates. |
| `AFF-19` | Affiliate API | V3.0 | P2 | BE-2 | As an affiliate, I access my data via API so that I can build custom dashboards and tools. |
| `AFF-20` | Attribution window and model configuration | V3.0 | P1 | BE-2 | As a tenant admin, I configure the cookie window duration and the attribution model (first-click vs last-click) so that attributio… |
| `AFF-21` | Affiliate payout method management | V3.0 | P0 | BE-2 | As an affiliate, I can save and confirm my payout method (crypto wallet, bank, or other) so that approved payouts go to the right … |
| `AFF-22` | Affiliate tax form collection | V3.0 | P1 | BE-2 | As a tenant admin, I can require affiliates to submit W-9 or W-8BEN forms before payout approval so that affiliate payouts are tax… |
| `AFF-23` | Affiliate notification templates | V3.0 | P1 | BE-2 | As the platform, I send affiliates notifications when commissions are accrued, approved, and paid, using tenant-branded templates,… |
| `AFF-24` | Conversion tracking postback | V3.0 | P1 | BE-2 | As an affiliate running paid ads, I can configure a postback URL that fires on conversion so that I can track which ads drive conv… |
| `AFF-25` | Affiliate deep links | V3.0 | P1 | BE-2 | As an affiliate, I can generate tracked links to specific challenges or landing pages with sub-ID tracking so that I can promote s… |
| `AFF-26` | Affiliate tier system | V3.0 | P2 | BE-2 | As a tenant admin, I can define affiliate tiers (e.g., Standard, Gold, VIP) with escalating commission rates so that top affiliate… |
| `AFF-27` | Commission cap | V3.0 | P2 | BE-2 | As a tenant admin, I can set a maximum total commission per affiliate or per period so that commission exposure is bounded. |
| `AFF-28` | Affiliate coupon management | V3.0 | P2 | BE-2 | As a tenant admin, I create affiliate-specific coupons with limits, expiry, and stacking rules, so that affiliate promotions are c… |
| `AFF-29` | Affiliate payout method verification | V3.0 | P2 | BE-2 | As the platform, I verify affiliate payout destination ownership before paying, so that affiliate payouts are not sent to unverifi… |
| `AFF-30` | Affiliate fraud velocity checks | V3.0 | P1 | BE-2 | As the platform, I detect abnormal click, signup, and payment velocity across affiliate links, so that affiliate fraud is caught b… |

## Auth

Affiliates (trader-realm section) + staff (program config, approvals). All routes sit in the GW chain (docs/04 §3.1): tenant resolution →
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

> Copied verbatim from `docs/23-affiliates.md` §7 on 2026-09-19 — the module doc is authoritative if they drift; regenerate with `python3 scripts/complete_contracts_pack.py`.

> **Scope note:** AFF is not in the V1 execution sheet (V2 scope). There is no V1 baseline contract for this module; the surface below is design-level (post-V1, docs/99) and provisional until its phase's contract freeze.


Affiliate (their dashboard, console realm's affiliate org — or a separate
subdomain `aff.alphaone.example` if tenants want white-label affiliate
portals, V3 decision):
`GET /v1/affiliate/dashboard` (balance: accrued/settled/hold, links,
stats),
`GET /v1/affiliate/links` (+ `POST` — link generation with the code),
`GET /v1/affiliate/accruals` (history incl. reversals with reasons),
`POST /v1/affiliate/payouts/requests`, `GET /v1/affiliate/payouts`,
`GET|POST /v1/affiliate/methods` (encrypted, PAY-pattern),
`GET /v1/affiliate/tax-forms` (+ upload).

Console (AFF-13): `GET /v1/console/affiliates` (+ apply/approve — 2FA),
`GET /v1/console/affiliates/{id}` (attribution quality, accruals, holds),
`POST /v1/console/affiliates/{id}/rate-card` (versioned, future-dated,
2FA), `POST /v1/console/affiliate-payouts/{id}/approve` (2FA),
`GET /v1/console/affiliates/reports` (AFF-14).

Outbound (AFF-15/19): the tenant's `affiliate.conversion` webhook
(Hook0, EVT-10 egress pattern); a narrow affiliate API (API key,
scoped `affiliate:read`) for the affiliate's own tooling.

## Open contract questions

- Paths, methods, and field names below are PROVISIONAL until this module's phase
  freeze (docs/99 §12) — additive changes only after freeze; breaking changes get
  `/v2/` + the 12-month deprecation rule for public surfaces.
- Permission keys: the V1 registry (`permissions/registry.md`) is binding; keys used
  below beyond it are provisional and join the registry at freeze.
- Error codes: V1 baseline codes are binding (`errors/taxonomy.md`); extended codes
  follow the GW-18 dotted convention and freeze with the module (docs/30).

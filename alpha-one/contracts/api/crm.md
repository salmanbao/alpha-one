# CRM & Communications API Contract (CRM)

Status: PROVISIONAL (post-V1, design-level)
Owner: TBD
Version: v1
Last updated: 2026-09-19

Derived from `docs/20-crm.md` §7 + PRD CRM-NN (V2.0, V3.0). Nothing here is final until that phase's contract freeze (docs/99 §12).

## Scope

PRD module **CRM** (16 requirements). Abridged backlog:

| Req | Feature | Release | Pri | Owner | User story (abridged) |
|---|---|---|---|---|---|
| `CRM-01` | Tags and internal notes | V2.0 | P1 | BE-2 | As staff, I can add tags and internal notes to trader profiles so that context accumulates across teams and shifts. |
| `CRM-02` | Communication history timeline | V2.0 | P1 | BE-2 | As staff, I see every email sent, ticket, note, and payout interaction on one trader timeline so that any agent gets full context … |
| `CRM-03` | Saved segments | V2.0 | P1 | BE-2 | As marketing staff, I define and save segments with rules on status, challenge, size, country, payout history, and tags so that ca… |
| `CRM-04` | Segment consumption | V2.0 | P1 | BE-2 | As marketing staff, I apply saved segments to broadcasts and offers so that targeting is reusable instead of re-filtered by hand e… |
| `CRM-05` | stage tracking | V2.0 | P1 | BE-2 | As the platform, I track lifecycle stages from lead to registered to purchased to evaluating to funded to paid to dormant to churn… |
| `CRM-06` | Automated sequences | V3.0 | P2 | BE-2 | As marketing staff, I configure simple drip sequences such as welcome series, cart abandonment, retry reminder, and re-engagement,… |
| `CRM-07` | Suppression and preferences | V2.0 | P1 | BE-2 | As the platform, I honor unsubscribe links and notification preferences and suppress sequences for blocked or suspended traders so… |
| `CRM-08` | Campaign performance metrics | V3.0 | P2 | BE-2 | As marketing staff, I see sends, opens, clicks, and conversions per campaign so that campaign value is measurable. |
| `CRM-09` | Discord community integration | V3.0 | P2 | BE-2 | As the platform, I assign and remove Discord roles on funded and payout events so that community status matches account status aut… |
| `CRM-10` | Unsubscribe and compliance management | V2.0 | P1 | BE-2 | As the platform, I process unsubscribe links and maintain suppression lists per tenant so that email compliance holds across campa… |
| `CRM-11` | Marketing consent capture | V3.0 | P2 | BE-2 | As the platform, I capture marketing consent at registration where required so that consented-only sends are enforceable per juris… |
| `CRM-12` | Lead scoring | V3.0 | P2 | BE-2 | As marketing staff, I score leads based on behavior so that sales focuses on high-value prospects. |
| `CRM-13` | Multi-channel campaigns | V3.0 | P2 | BE-2 | As marketing staff, I orchestrate email, SMS, and push in coordinated campaigns so that messaging is consistent. |
| `CRM-14` | Contact scoring and engagement history | V3.0 | P2 | BE-2 | As marketing staff, I see an engagement history and score for each contact, so that outreach is prioritised. |
| `CRM-15` | Campaign email template management | V3.0 | P2 | BE-2 | As marketing staff, I manage templates for campaign emails, so that consistent copy is reusable. |
| `CRM-16` | data export | V2.0 | P2 | BE-2 | As a tenant admin, I export CRM data, so that my records are portable. |

## Auth

Staff (Tenant Admin / marketing role). No trader-facing surface except consent + unsubscribe. All routes sit in the GW chain (docs/04 §3.1): tenant resolution →
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

> Copied verbatim from `docs/20-crm.md` §7 on 2026-09-19 — the module doc is authoritative if they drift; regenerate with `python3 scripts/complete_contracts_pack.py`.

> **Scope note:** CRM is not in the V1 execution sheet (V2 scope). There is no V1 baseline contract for this module; the surface below is design-level (post-V1, docs/99) and provisional until its phase's contract freeze.


Staff (CON/ADM — CRM surfaces live in the console for platform staff and in
ADM for tenant marketing, V2):
`GET /v1/crm/segments` (+ `POST`, `POST /{id}/recompute`),
`GET /v1/crm/segments/{id}/preview` (size + masked top 50),
`GET|POST /v1/crm/campaigns`, `POST /{id}/send` (2FA),
`GET /{id}/performance` (V3),
`GET /v1/crm/traders/{id}` (stage, tags, notes, communication history,
consent),
`POST /v1/crm/traders/{id}/tags`, `POST /{id}/notes` (CRM-01),
`GET /v1/crm/history?identity=` (CRM-02: the unified log — NOT delivery
events + SUP tickets + CRM campaigns, one timeline),
unsubscribe: `POST /v1/public/crm/unsubscribe` (token, no auth) +
`GET /v1/public/crm/preferences` (token — the V2 prefs page: toggle
purposes, the consent record edited).

## Open contract questions

- Paths, methods, and field names below are PROVISIONAL until this module's phase
  freeze (docs/99 §12) — additive changes only after freeze; breaking changes get
  `/v2/` + the 12-month deprecation rule for public surfaces.
- Permission keys: the V1 registry (`permissions/registry.md`) is binding; keys used
  below beyond it are provisional and join the registry at freeze.
- Error codes: V1 baseline codes are binding (`errors/taxonomy.md`); extended codes
  follow the GW-18 dotted convention and freeze with the module (docs/30).

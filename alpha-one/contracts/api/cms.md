# Website / CMS (Part A) API Contract (CMS)

Status: PROVISIONAL (post-V1, design-level)
Owner: TBD
Version: v1
Last updated: 2026-09-19

Derived from `docs/24-cms-competitions.md` §7 + PRD CMS-NN (V3.0). Nothing here is final until that phase's contract freeze (docs/99 §12).

## Scope

PRD module **CMS** (15 requirements). Abridged backlog:

| Req | Feature | Release | Pri | Owner | User story (abridged) |
|---|---|---|---|---|---|
| `CMS-01` | Tenant site provisioning | V3.0 | P0 | BE-2 | As a super admin or tenant admin, I can provision a tenant marketing site on a platform subdomain or custom domain with SSL so tha… |
| `CMS-02` | Template library | V3.0 | P0 | FE-1 | As a tenant admin, I choose from prebuilt landing templates with hero, pricing, features, FAQ, testimonials, and footer sections s… |
| `CMS-03` | Constrained section editor | V3.0 | P0 | FE-1 | As a tenant admin, I edit section content including text, images, links, and brand-token colors through a constrained editor so th… |
| `CMS-04` | Pricing and challenge widget | V3.0 | P0 | BE-2 | As a tenant admin, I embed a live pricing block that pulls the catalog and links into checkout so that public prices never go stal… |
| `CMS-05` | Blog and content management | V3.0 | P1 | BE-2 | As marketing staff, I create and edit blog posts and pages with drafts and publishing so that content marketing lives on-platform. |
| `CMS-06` | controls | V3.0 | P1 | BE-2 | As marketing staff, I set per-page title, meta description, open graph tags, and canonical URLs, and the platform emits sitemap an… |
| `CMS-07` | Form builder | V3.0 | P1 | BE-2 | As marketing staff, I build contact and lead forms that feed CRM contacts and segments so that leads are captured in-platform inst… |
| `CMS-08` | Legal page rendering | V3.0 | P0 | FE-1 | As the platform, I render terms, privacy, and risk disclaimer from tenant settings on both the tenant site and the portal so that … |
| `CMS-09` | Navigation builder | V3.0 | P1 | FE-1 | As a tenant admin, I configure site navigation menus and footer links so that site structure is manageable without code. |
| `CMS-10` | Social proof blocks | V3.0 | P2 | FE-1 | As a tenant admin, I add curated testimonials and statistics blocks so that social proof is present on landing pages. |
| `CMS-11` | and help pages | V3.0 | P2 | FE-1 | As a tenant admin, I publish FAQ and help articles so that support deflection happens on the public site. |
| `CMS-12` | Analytics hooks | V3.0 | P1 | FE-1 | As marketing staff, I add pixel and analytics identifiers per tenant site so that marketing measurement works without code changes… |
| `CMS-13` | Media library and asset management | V3.0 | P1 | FE-1 | As marketing staff, I upload and reuse tenant- scoped images and assets, so that page editing is efficient and consistent. |
| `CMS-14` | Page versioning and rollback | V3.0 | P1 | FE-1 | As a tenant admin, I see page change history and can roll back to a prior version, so that bad publishes are recoverable. |
| `CMS-15` | Scheduled publishing | V3.0 | P1 | FE-1 | As marketing staff, I schedule pages and posts for future publication, so that launches are timed without manual work. |

## Auth

Public (published site) + staff (editor, Tenant Admin). All routes sit in the GW chain (docs/04 §3.1): tenant resolution →
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

> Copied verbatim from `docs/24-cms-competitions.md` §7 on 2026-09-19 — the module doc is authoritative if they drift; regenerate with `python3 scripts/complete_contracts_pack.py`.

> **Scope note:** CMS/CMP is not in the V1 execution sheet (V2/V3 scope). There is no V1 baseline contract for this module; the surface below is design-level (post-V1, docs/99) and provisional until its phase's contract freeze.


Public (tenant domain, no auth): the rendered pages (RSC/SSR),
`GET /v1/public/{tenant}/catalog` (the widget data, 5-min edge cache),
`POST /v1/public/{tenant}/forms/{form_id}` (lead submit, rate-limited),
`GET /sitemap.xml`, `GET /robots.txt` (per-tenant generated).

Staff (ADM marketing, V3): `GET|POST /v1/admin/site/pages` (+
`POST /{id}/publish` (2FA on legal), `POST /{id}/rollback`,
`POST /{id}/schedule`), `GET|POST /v1/admin/site/blocks`,
`POST /v1/admin/site/media` (upload), `GET /v1/admin/site/preview/{page}`
(the live-data preview), `GET|POST /v1/admin/site/seo`,
`GET /v1/admin/site/leads`, `GET /v1/admin/site/published-stats` (+
`POST` — publish the numbers).

## Open contract questions

- Paths, methods, and field names below are PROVISIONAL until this module's phase
  freeze (docs/99 §12) — additive changes only after freeze; breaking changes get
  `/v2/` + the 12-month deprecation rule for public surfaces.
- Permission keys: the V1 registry (`permissions/registry.md`) is binding; keys used
  below beyond it are provisional and join the registry at freeze.
- Error codes: V1 baseline codes are binding (`errors/taxonomy.md`); extended codes
  follow the GW-18 dotted convention and freeze with the module (docs/30).

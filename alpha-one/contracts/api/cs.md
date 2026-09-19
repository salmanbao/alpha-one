# Customer Success (Part C.2) API Contract (CS)

Status: PROVISIONAL (post-V1, design-level)
Owner: TBD
Version: v1
Last updated: 2026-09-19

No §7 in the module doc (console-only module); scope from PRD CS-NN (V3.0). Nothing here is final until that phase's contract freeze (docs/99 §12).

## Scope

PRD module **CS** (7 requirements). Abridged backlog:

| Req | Feature | Release | Pri | Owner | User story (abridged) |
|---|---|---|---|---|---|
| `CS-01` | surveys | V3.0 | P2 | BE-2 | As a tenant admin, I send NPS surveys to traders so that satisfaction is measured. |
| `CS-02` | Customer health scoring | V3.0 | P2 | BE-2 | As the platform, I score tenant health based on usage, support tickets, and churn signals so that at-risk tenants are flagged. |
| `CS-03` | Churn prediction | V3.0 | P2 | BE-2 | As the platform, I predict trader churn using ML so that retention campaigns are targeted. |
| `CS-04` | Onboarding workflows | V3.0 | P2 | BE-2 | As the platform, I guide new tenants through setup with checklists and tutorials so that time-to-value is reduced. |
| `CS-05` | Customer success playbooks and tasks | V3.0 | P1 | BE-2 | As customer success staff, I use playbooks and tasks for onboarding and retention, so that success work is repeatable. |
| `CS-06` | Renewal and expansion tracking | V3.0 | P1 | BE-2 | As customer success staff, I track renewal and expansion opportunities per tenant, so that revenue retention is managed. |
| `CS-07` | Quarterly business review reporting | V3.0 | P2 | BE-2 | As customer success staff, I generate QBR reports from tenant health and usage data, so that reviews are data-driven. |

## Auth

Platform staff via CON. No dedicated HTTP surface — console screens over module APIs + jobs. All routes sit in the GW chain (docs/04 §3.1): tenant resolution →
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

No dedicated HTTP surface: this module is console screens (CON) over other modules' APIs plus background jobs. See the module doc Part C.

## Open contract questions

- Paths, methods, and field names below are PROVISIONAL until this module's phase
  freeze (docs/99 §12) — additive changes only after freeze; breaking changes get
  `/v2/` + the 12-month deprecation rule for public surfaces.
- Permission keys: the V1 registry (`permissions/registry.md`) is binding; keys used
  below beyond it are provisional and join the registry at freeze.
- Error codes: V1 baseline codes are binding (`errors/taxonomy.md`); extended codes
  follow the GW-18 dotted convention and freeze with the module (docs/30).

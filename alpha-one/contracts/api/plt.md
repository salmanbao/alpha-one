# Platform Operations (Part C.1) API Contract (PLT)

Status: PROVISIONAL (post-V1, design-level)
Owner: TBD
Version: v1
Last updated: 2026-09-19

No §7 in the module doc (console-only module); scope from PRD PLT-NN (V3.0). Nothing here is final until that phase's contract freeze (docs/99 §12).

## Scope

PRD module **PLT** (8 requirements). Abridged backlog:

| Req | Feature | Release | Pri | Owner | User story (abridged) |
|---|---|---|---|---|---|
| `PLT-01` | Multi-region deployment | V3.0 | P2 | DevOps | As ops, I deploy to multiple regions for disaster recovery so that regional outages don't stop the platform. |
| `PLT-02` | Capacity planning | V3.0 | P2 | DevOps | As ops, I forecast resource needs based on growth so that infrastructure scales ahead of demand. |
| `PLT-03` | Cost allocation | V3.0 | P2 | BE-2 | As the business, I see infrastructure cost per tenant so that profitability is measurable. |
| `PLT-04` | Performance benchmarking | V3.0 | P1 | DevOps | As ops, I track p50/p95/p99 latencies per endpoint so that performance regressions are caught. |
| `PLT-05` | Incident management and on-call runbooks | V3.0 | P1 | DevOps | As platform ops, I follow documented incident runbooks and on-call escalation, so that incidents are handled consistently. |
| `PLT-06` | Capacity and cost governance dashboard | V3.0 | P2 | DevOps | As platform ops, I see capacity and cost trends per tenant and service, so that scaling and spend are governed. |
| `PLT-07` | Multi-region failover runbook and drills | V3.0 | P1 | DevOps | As platform ops, I rehearse multi-region failover, so that regional outages are recoverable. |
| `PLT-08` | Security operations and vulnerability management | V3.0 | P1 | DevOps | As platform ops, I run ongoing vulnerability management and security operations, so that platform security is proactive. |

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

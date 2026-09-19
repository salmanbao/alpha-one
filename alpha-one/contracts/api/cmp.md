# Competitions & Gamification (Part B) API Contract (CMP)

Status: PROVISIONAL (post-V1, design-level)
Owner: TBD
Version: v1
Last updated: 2026-09-19

Derived from `docs/24-cms-competitions.md` §7 + PRD CMP-NN (V3.0). Nothing here is final until that phase's contract freeze (docs/99 §12).

## Scope

PRD module **CMP** (17 requirements). Abridged backlog:

| Req | Feature | Release | Pri | Owner | User story (abridged) |
|---|---|---|---|---|---|
| `CMP-01` | Competition creation | V3.0 | P0 | BE-2 | As a tenant admin, I create a competition with period, entry type, eligibility, scoring criteria, and prize structure so that even… |
| `CMP-02` | Competition account provisioning | V3.0 | P0 | BE-2 | As the platform, I provision dedicated competition accounts through the broker bridge with a competition group and rules so that c… |
| `CMP-03` | Entry and registration | V3.0 | P0 | BE-2 | As a trader, I register for a competition with free or paid entry through checkout so that participation is tracked and paid entri… |
| `CMP-04` | Scoring engine | V3.0 | P0 | BE-2 | As the platform, I compute scores from synced equity using the configured criterion such as profit percent, ROI, or absolute profi… |
| `CMP-05` | Leaderboard | V3.0 | P0 | BE-2 | As a trader or public visitor, I view a ranked leaderboard with alias option and a visible update timestamp so that the competitio… |
| `CMP-06` | Leaderboard integrity | V3.0 | P1 | BE-2 | As the platform, I exclude breached, suspended, and risk-flagged accounts from rankings and freeze scores at competition end so th… |
| `CMP-07` | Prize distribution | V3.0 | P1 | BE-2 | As the platform, I award prizes as account credit, payout-engine payout, or coupon, with audit entries and winner notification, so… |
| `CMP-08` | Competition end and results | V3.0 | P1 | BE-2 | As the platform, I finalize results at end time, publish final standings, and archive the competition so that history is preserved… |
| `CMP-09` | Badges and achievements | V3.0 | P1 | BE-2 | As the platform, I grant badges on milestone events such as funded, first payout, payout streak, and competition win, and display … |
| `CMP-10` | Trader levels and XP | V3.0 | P2 | BE-2 | As the platform, I maintain simple activity tiers so that long-term engagement has visible progression. |
| `CMP-11` | Public trader profiles | V3.0 | P2 | BE-2 | As a trader, I can opt in to a public profile with stats and badges so that community recognition exists while privacy defaults to… |
| `CMP-12` | Competition notifications | V3.0 | P1 | BE-2 | As the platform, I notify participants on start, end, prize award, and optional rank milestones so that engagement is event-driven… |
| `CMP-13` | Competition admin UI | V3.0 | P0 | FE-1 | As a tenant admin, I manage competitions, view live standings, moderate entries, and approve prize distribution so that operations… |
| `CMP-14` | Multi-entry limits | V3.0 | P1 | BE-2 | As the platform, I enforce per-trader entry limits and detect multi-account entries so that competitions cannot be farmed by one p… |
| `CMP-15` | Competition templates | V3.0 | P1 | FE-1 | As a tenant admin, I create competitions from reusable templates, so that events are launched quickly and consistently. |
| `CMP-16` | Team/group competitions | V3.0 | P2 | BE-2 | As a tenant admin, I run team-based competitions with aggregate scoring, so that community engagement is broader. |
| `CMP-17` | Competition audit and dispute resolution | V3.0 | P1 | BE-2 | As a tenant admin, I review competition decisions and resolve disputes with audit, so that outcomes are defensible. |

## Auth

Trader (enter, leaderboard) + staff (create, score, prize). All routes sit in the GW chain (docs/04 §3.1): tenant resolution →
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

Trader (TD): `GET /v1/competitions` (open/active/archived for the
tenant), `GET /v1/competitions/{id}` (rules, prizes, board, their
entry), `POST /v1/competitions/{id}/entries` (the fee purchase flow —
CHK intent, the same as a package purchase), `GET /v1/competitions/{id}/
board` (the public board, as_of-labeled), `POST /v1/competitions/{id}/
disputes` (the window + the reason), `GET /v1/profiles/{handle}`
(public, the masked-by-default surface).

Staff (ADM, CMP-13): `GET|POST /v1/admin/competitions` (+ the full
lifecycle actions, 2FA on create (the liability booking) and on
results publish), `GET /v1/admin/competitions/{id}/dq-queue` (the
confirmation queue), `POST /{entry}/dq-confirm`,
`GET /v1/admin/competitions/{id}/scoring` (the per-tick scores +
recompute button — the recompute is a read-only proof, 2FA'd),
`POST /v1/admin/competitions/templates` (CMP-15).

Public: `GET /v1/public/{tenant}/competitions/{id}/board` (the
unauthenticated board — a competition page is a marketing page; CMS-04
widget's sibling).

## Open contract questions

- Paths, methods, and field names below are PROVISIONAL until this module's phase
  freeze (docs/99 §12) — additive changes only after freeze; breaking changes get
  `/v2/` + the 12-month deprecation rule for public surfaces.
- Permission keys: the V1 registry (`permissions/registry.md`) is binding; keys used
  below beyond it are provisional and join the registry at freeze.
- Error codes: V1 baseline codes are binding (`errors/taxonomy.md`); extended codes
  follow the GW-18 dotted convention and freeze with the module (docs/30).

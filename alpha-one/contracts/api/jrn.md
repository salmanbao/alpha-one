# Trading Journal (Part B) API Contract (JRN)

Status: PROVISIONAL (post-V1, design-level)
Owner: TBD
Version: v1
Last updated: 2026-09-19

Derived from `docs/26-mobile-apps.md` §7 + PRD JRN-NN (V2.0, V3.0). Nothing here is final until that phase's contract freeze (docs/99 §12).

## Scope

PRD module **JRN** (8 requirements). Abridged backlog:

| Req | Feature | Release | Pri | Owner | User story (abridged) |
|---|---|---|---|---|---|
| `JRN-01` | Trade logging | V2.0 | P1 | FE-1 | As a trader, I can log trades with entry, exit, size, and rationale so that I build a personal record. |
| `JRN-02` | Screenshot attachments | V2.0 | P1 | FE-1 | As a trader, I can attach chart screenshots to a trade entry so that I record my setup visually. |
| `JRN-03` | Tags and strategies | V2.0 | P1 | FE-1 | As a trader, I can tag trades with strategies and setups so that I can analyze performance by approach. |
| `JRN-04` | Journal analytics | V2.0 | P1 | FE-1 | As a trader, I see win rate, average R multiple, and performance by strategy from my journal entries so that I improve. |
| `JRN-05` | Daily review | V2.0 | P2 | FE-1 | As a trader, I can write a daily reflection with mood and key lessons so that I build discipline. |
| `JRN-06` | Trade replay | V3.0 | P2 | FE-1 | As a trader, I can replay a logged trade on a chart so that I review execution. |
| `JRN-07` | Journal export | V2.0 | P1 | FE-1 | As a trader, I can export my entire journal, so that my notes are portable. |
| `JRN-08` | Trade replay sharing | V3.0 | P2 | FE-1 | As a trader, I can share a trade replay with a mentor or support so that feedback is possible. |

## Auth

Trader (own journal) + optional staff aggregate reads (never entry content without consent). All routes sit in the GW chain (docs/04 §3.1): tenant resolution →
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

> Copied verbatim from `docs/26-mobile-apps.md` §7 on 2026-09-19 — the module doc is authoritative if they drift; regenerate with `python3 scripts/complete_contracts_pack.py`.

Trader (TD — the journal is a TD section):
`GET /v1/journal/entries?account=&from=&to=&tag=`,
`POST /v1/journal/entries` `{account_id, deal_id?, day_key?, body,
tags[], screenshot_id?}`,
`GET /v1/journal/entries/{id}` (+ `PATCH` (edit, the version
bump), `DELETE`),
`POST /v1/journal/screenshots` (upload → the R2 + the scan queue),
`GET /v1/journal/stats?account=&range=` (the JRN-04 aggregates),
`GET /v1/journal/replay?account=&day=` (V3 — the render data),
`POST /v1/journal/entries/{id}/share` (V3 → `{url, expires_at}`),
`DELETE /v1/journal/entries/{id}/share` (V3 — revoke),
`GET /v1/journal/export` (the JRN-07 self-serve),
public: `GET /v/journal/{share_token}` (V3 — the shared page,
rate-limited, the allowlisted content).

## Open contract questions

- Paths, methods, and field names below are PROVISIONAL until this module's phase
  freeze (docs/99 §12) — additive changes only after freeze; breaking changes get
  `/v2/` + the 12-month deprecation rule for public surfaces.
- Permission keys: the V1 registry (`permissions/registry.md`) is binding; keys used
  below beyond it are provisional and join the registry at freeze.
- Error codes: V1 baseline codes are binding (`errors/taxonomy.md`); extended codes
  follow the GW-18 dotted convention and freeze with the module (docs/30).

# Advanced Trading (Part B) API Contract (TRD)

Status: PROVISIONAL (post-V1, design-level)
Owner: TBD
Version: v1
Last updated: 2026-09-19

Derived from `docs/27-ecosystem.md` §7 + PRD TRD-NN (V3.0). Nothing here is final until that phase's contract freeze (docs/99 §12).

## Scope

PRD module **TRD** (8 requirements). Abridged backlog:

| Req | Feature | Release | Pri | Owner | User story (abridged) |
|---|---|---|---|---|---|
| `TRD-01` | Copy trading marketplace | V3.0 | P2 | BE-2 | As a trader, I follow successful traders automatically so that I learn from proven strategies. |
| `TRD-02` | Social trading feed | V3.0 | P2 | BE-2 | As a trader, I see a social feed of trades and insights so that I learn from the community. |
| `TRD-03` | Strategy marketplace | V3.0 | P2 | BE-2 | As a trader, I buy and sell trading strategies so that I can monetize my edge. |
| `TRD-04` | Backtesting tools | V3.0 | P2 | BE-2 | As a trader, I backtest strategies on historical data so that I validate before risking capital. |
| `TRD-05` | Paper trading at scale | V3.0 | P1 | BE-2 | As the platform, I offer unlimited demo accounts so that traders practice without risk. |
| `TRD-06` | Advanced order types | V3.0 | P2 | BE-2 | As an advanced trader, I use OCO, trailing stops, and bracket orders, so that my strategies are executable. |
| `TRD-07` | for algorithmic traders | V3.0 | P2 | BE-1 | As an algorithmic trader, I access trading endpoints via API, so that I can automate strategies. |
| `TRD-08` | Advanced trading risk controls and kill switch | V3.0 | P1 | BE-2 | As a tenant admin, I configure risk controls and a kill switch for advanced trading, so that runaway strategies are contained. |

## Auth

Trader (copy, backtest, paper, algos) + staff (venue config). All routes sit in the GW chain (docs/04 §3.1): tenant resolution →
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

> Copied verbatim from `docs/27-ecosystem.md` §7 on 2026-09-19 — the module doc is authoritative if they drift; regenerate with `python3 scripts/complete_contracts_pack.py`.

> **Scope note:** SDK/DVP/TRD/PLT/CS is not in the V1 execution sheet (V2/V3 scope; API keys themselves are V2 per AUTH-21). There is no V1 baseline contract for this module; the surface below is design-level (post-V1, docs/99) and provisional until its phase's contract freeze.


Trader (the TD's V3 extension):
`GET /v1/trading/leaders` (the social feed, the TRD-02: the public performance, the as_of-labeled),
`GET /v1/trading/leaders/{id}` (the performance, the subscription CTA),
`POST /v1/trading/copy/subscriptions` (the TRD-01: the config, the consent, the 2FA-class),
`GET /v1/trading/copy/subscriptions` (the own, the PnL, the latency stats),
`DELETE /v1/trading/copy/subscriptions/{id}` (the cancel, the open positions (the keep/close, the 2FA on the close)),
`POST /v1/trading/orders` (the TRD-06: the advanced order (the OCO, the trailing), the 2FA, the sensitive action),
`GET /v1/trading/paper/accounts` (the TRD-05, the "PAPER" badged),
`POST /v1/trading/paper/accounts` (the create, the virtual funding, the no-real-money),
`GET /v1/trading/backtests` (the TRD-04, the runs, the results).

Staff (the ADM's V3 extension, the tenant's curation):
`GET /v1/admin/trading/leaders` (the curation queue, the 24 Part A pattern),
`POST /v1/admin/trading/leaders/{id}/delist` (the 2FA, the followers' notice),
`GET /v1/admin/trading/strategies` (the marketplace curation),
`POST /v1/admin/trading/strategies/{id}/approve` (the 2FA, the backtest-verified gate),
`GET /v1/admin/trading/copy/stats` (the tenant's copy health: the latency, the slippage, the skip rate, the PnL),
`GET /v1/admin/trading/algo/keys` (the TRD-07/08: the keys, the guardrails, the halt state),
`POST /v1/admin/trading/algo/keys/{id}/guardrails` (the 2FA, the versioned config),
`POST /v1/admin/trading/algo/keys/{id}/re-enable` (the 2FA, the review).

Public (the SDK, the Part A's public API extended):
`GET /v1/public/trading/leaders` (the social feed, the masked PII, the ref indirection, the Part A §8),
`POST /v1/public/trading/orders` (the TRD-07: the algo's order, the `trading:write` scope, the TRD-08 pre-check, the critical audit),
`GET /v1/public/trading/backtests/{id}` (the TRD-04's result, the tenant-scoped).

## Open contract questions

- Paths, methods, and field names below are PROVISIONAL until this module's phase
  freeze (docs/99 §12) — additive changes only after freeze; breaking changes get
  `/v2/` + the 12-month deprecation rule for public surfaces.
- Permission keys: the V1 registry (`permissions/registry.md`) is binding; keys used
  below beyond it are provisional and join the registry at freeze.
- Error codes: V1 baseline codes are binding (`errors/taxonomy.md`); extended codes
  follow the GW-18 dotted convention and freeze with the module (docs/30).

# Analytics API Contract (ANA)

Status: DRAFT
Owner: TBD
Version: v1
Last updated: 2026-09-20

Derived from the V1 Execution Sheet (V1.0 / V1.1). Nothing here is final until contract freeze.

## Scope
Read model foundation maintained from domain events plus nightly aggregation (ANA-01), and the real-time KPI dashboard (ANA-32, V1.1: today's revenue, active accounts, pending queues, breach count, refreshed within a minute). (ANA-01, ANA-32)

BVR-13: no third analytics/BI tool in V1 — read models + fixed reports are the contract. Out Of Scope: no streaming dashboards — event-driven read models plus nightly batch is the contract; no embedded BI tools; no custom report builder.

## Auth
Dashboard endpoint in admin group (GW-01), Tenant Admin role. Note: a `analytics.financial.read`-style financial reporting permission was referenced in earlier drafts (ANA-13) but that Req ID is not in the V1 sheet — financial reports beyond the KPI dashboard are not in V1 scope.

## Tenant resolution
From domain (GW-02). Read models are tenant-scoped; no cross-tenant analytics in V1 (Out Of Scope).

## Permissions
- `analytics.read` — view KPI dashboard — registered and ratified 2026-09-19 (D14; `contracts/permissions/registry.md`: view the real-time KPI dashboard of the caller's own firm, ANA-32).

## Idempotency
n/a (read-only surface).

## Endpoints

### GET /v1/admin/analytics/kpi
Auth: Tenant Admin — ANA-32 (V1.1)
Tenant: from domain (GW-02)
Permission: `analytics.read` # ANA-32
Idempotency: n/a

Response 200 (D45):
```json
{ "data": { "revenue_today_cents": 0, "active_accounts": 0,
    "pending_queues": { "payout": 0, "kyc_manual": 0, "risk": 0 },
    "breach_count": 0, "as_of": 1758282000000 },
  "meta": { "request_id": "01J9ULID...", "version": "v1" } }
```

Definitions per docs/19 §3.2 (active = 24 h; revenue = order.paid gross today;
queues = payout pending / KYC manual / risk open).

Errors: none beyond standard gateway errors # ANA-32
Freshness contract: values no older than one minute # ANA-32 ("update within a minute")

## Internal contracts (no HTTP)
- ANA-01 read models: tables updated from domain events (all catalog events) plus nightly aggregation jobs; reports never query operational tables.

## Events consumed
- V1 domain events feed the read models (ANA-01: "read model tables updated from domain events plus nightly aggregation"). The per-table event mapping — resolved 2026-09-20 (docs/62): docs/19 §3.1's feed map (equity_points ← bridge.tick; accounts_ro/traders_ro ← the LCC events; payments_daily ← order.paid; payouts_daily ← payout.*; funnel_steps ← the registered funnel events; risk_summary ← risk.case_*; kpi_snapshot ← the 30-s job).

## Open contract questions
- Resolved 2026-09-20 (docs/59): KPI definitions = docs/19 §3.2 (active traders = 24 h; revenue = order.paid gross today; queues = payout pending / KYC manual / risk open; breach count; tick-age honesty block).
- Resolved 2026-09-20 (docs/59): the read-model table list = docs/19 §3.1 (equity_points, accounts_ro, traders_ro, payments_daily, payouts_daily, funnel_steps, risk_summary, kpi_snapshot); refresh: 30-s snapshot job, 1-min equity buckets, the KPI route answers values ≤ 1 min old (ANA-32).
- Resolved 2026-09-20 (docs/59): the dashboard beyond KPI = the fixed V2 report suite (ANA-02..09/16, docs/19 §3.3) — V1 ships the KPI screen only.
- Resolved 2026-09-20 (docs/59): CSV export = ANA-11 (V2): async CSV/PDF workers → R2 → 24-h URLs (docs/19 §2).

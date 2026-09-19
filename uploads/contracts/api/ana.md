# Analytics API Contract (ANA)

Status: DRAFT
Owner: TBD
Version: v1
Last updated: TODO

Derived from the V1 Execution Sheet (V1.0 / V1.1). Nothing here is final until contract freeze.

## Scope
Read model foundation maintained from domain events plus nightly aggregation (ANA-01), and the real-time KPI dashboard (ANA-32, V1.1: today's revenue, active accounts, pending queues, breach count, refreshed within a minute). (ANA-01, ANA-32)

BVR-13: no third analytics/BI tool in V1 — read models + fixed reports are the contract. Out Of Scope: no streaming dashboards — event-driven read models plus nightly batch is the contract; no embedded BI tools; no custom report builder.

## Auth
Dashboard endpoint in admin group (GW-01), Tenant Admin role. Note: a `analytics.financial.read`-style financial reporting permission was referenced in earlier drafts (ANA-13) but that Req ID is not in the V1 sheet — financial reports beyond the KPI dashboard are not in V1 scope.

## Tenant resolution
From domain (GW-02). Read models are tenant-scoped; no cross-tenant analytics in V1 (Out Of Scope).

## Permissions
- `analytics.read` — view KPI dashboard # derived from ANA-32 admin story — TODO — needs owner decision on key naming

## Idempotency
n/a (read-only surface).

## Endpoints

### GET /v1/admin/analytics/kpi
Auth: Tenant Admin — ANA-32 (V1.1)
Tenant: from domain (GW-02)
Permission: `analytics.read` # ANA-32
Idempotency: n/a

Response 200:
```json
{ "revenue_today": "TODO", "active_accounts": "TODO", "pending_queues": "TODO", "breach_count": "TODO", "as_of": "TODO" }
```

Errors: none beyond standard gateway errors # ANA-32
Freshness contract: values no older than one minute # ANA-32 ("update within a minute")

## Internal contracts (no HTTP)
- ANA-01 read models: tables updated from domain events (all catalog events) plus nightly aggregation jobs; reports never query operational tables.

## Events consumed
- V1 domain events feed the read models (ANA-01: "read model tables updated from domain events plus nightly aggregation"). The per-table event mapping — TODO — needs owner decision (ANA-01 names the mechanism, not the event list).

## Open contract questions
- TODO — needs owner decision: exact KPI definitions (what counts as "active accounts", "pending queues" — which queues?, "revenue" — captured vs settled?).
- TODO — needs owner decision: read model table list and refresh SLAs beyond the one-minute KPI rule.
- TODO — needs owner decision: tenant dashboards beyond KPI (fixed report set from Out Of Scope — "fixed report set plus CSV export" — the report list itself is not in the V1 sheet).
- TODO — needs owner decision: CSV export surface for reports (referenced by Out Of Scope; no V1 row defines it).

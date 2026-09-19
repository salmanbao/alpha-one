# Admin Panel Contract (ADM)

Status: DRAFT
Owner: TBD
Version: v1
Last updated: TODO

Derived from the V1 Execution Sheet (V1.0 only). Nothing here is final until contract freeze.

## No HTTP contract in V1 — see module spec later
ADM is a frontend module with a single V1 row:
- ADM-05 account list — staff list and filter all trading accounts by status, phase, challenge, and broker. The data contract is `GET /v1/admin/accounts` owned by LCC (`contracts/api/lcc.md`, derived from ADM-05).

All other admin-panel data flows consume module contracts: payouts queue (`contracts/api/pay.md`), KYC review (`contracts/api/kyc.md`), challenges/rule sets (`contracts/api/evl.md`), audit (`contracts/api/aud.md`), tenant config (`contracts/api/tenant.md`), analytics (`contracts/api/ana.md`).

Out Of Scope constraints: fixed role-based dashboards (no widget editor), fixed report set plus CSV export, no live chat, no field-level permissions beyond route/action permissions, white-label limited to branding tokens.

## Open contract questions
- TODO — needs owner decision: whether ADM needs any endpoints of its own in V1 (the sheet implies none — every screen is a consumer).
- TODO — needs owner decision: staff role definitions for admin panel access (AUTH-12 custom staff roles exist as a model, but no V1 row binds roles to admin screens).

# Payout API Contract (PAY)

Status: DRAFT
Owner: TBD
Version: v1
Last updated: 2026-09-17

Derived from the V1 Execution Sheet (V1.0 / V1.1). Nothing here is final until contract freeze.

## Scope
Payout request, available profit calculation, eligibility engine, risk hold (V1.1), payout method management (V1.1), approval queue, approve/reject with reason, manual execution recording, payout state machine, ledger integration, scheduling enforcement, payout policy configuration, batch export (V1.1), crypto address validation (V1.1). (PAY-01, PAY-02, PAY-03, PAY-04, PAY-05, PAY-08, PAY-09, PAY-12, PAY-13, PAY-14, PAY-21, PAY-38, PAY-44, PAY-45)

## Payout state machine (PAY-13)
States: requested, eligibility checked, pending approval, approved, rejected, processing, paid, failed, cancelled. See `contracts/diagrams/payout-state.md`.

### V1 edges (resolved 2026-09-17)

```text
requested            → eligibility checked   PAY-03 runs checks synchronously
eligibility checked  → pending approval      enters approver queue (PAY-08)
pending approval     → approved              approver approves with reason (PAY-09)
pending approval     → rejected              approver rejects with reason (PAY-09)
approved             → paid                  COO records execution (PAY-12)
```

Failed eligibility never creates a payout: PAY-03 is a gate ("so that only eligible requests proceed"), so an ineligible request returns `payout.ineligible` and no payout row is created. Rejected is reached only from pending approval (PAY-09) — never directly from requested.

### Reserved states — defined, no V1 entry path
- `processing` — reserved for V2 automated provider execution (PAY-24). In V1 execution is manual (PAY-12, Build Strategy "Manual for V1"), so there is no automated window between approved and paid; the manual-send window is elapsed time between two transitions, not a state.
- `failed` — reserved for V2 failure/retry (PAY-18). No V1 row defines entry conditions.
- `cancelled` — reserved for V2 trader cancellation (PAY-17). No V1 row defines entry conditions.

The state list is fixed by PAY-13 (V1) — the states are not removed; V1 code simply never transitions into these three.

## Auth
Trader routes in trader group; finance approver and COO actions in admin group (GW-01). Roles: Trader (requests), Finance Approver (queue, approve/reject), COO (execution recording) — role names per AUTH-12 model. Binding (roles.yaml): `payout.request` user:trader (own); `payout.approve` firm:owner/admin/finance + step-up; `payout.read_queue` firm:owner/admin/finance/risk; `payout.record_execution` firm:owner/admin/finance; `payout.policy.write` firm:owner/admin/finance; `payout.method.write/read` user:trader (own).

## Tenant resolution
From domain (GW-02). Payouts, methods, and policy are tenant-scoped (TEN-03).

## Permissions
- `payout.request` — trader self-action # PAY-01
- `payout.approve` — approve/reject with reason # PAY-09
- `payout.record_execution` — record executed payout # PAY-12
- `payout.read_queue` — view approval queue # PAY-08 (key bound in roles.yaml/registry)
- `payout.policy.write` — configure payout policy # PAY-38
- `payout.method.write` / `payout.method.read` — trader method management # PAY-05 (self)

## Idempotency
Mutating requests accept an idempotency key per GW-12. Duplicate payout requests while one is open fail with `payout.active_exists` 409 (docs/11 §3.1: one active request per account, enforced day 1).

## Endpoints

### POST /v1/trader/payouts
Auth: Trader (funded account owner) — PAY-01
Tenant: from domain (GW-02)
Permission: `payout.request` (self) # PAY-01
Idempotency: required # GW-12

Request:
```json
{ "account_id": "TODO", "amount": "TODO", "payout_method_id": "TODO" }
```

Response 201:
```json
{ "payout_id": "TODO", "state": "requested" }
```

Errors:
- `payout.ineligible` 422 — failed an eligibility check with sub-reasons: KYC not approved (KYC-08), minimum trading days, consistency, trading day threshold, first withdrawal delay, next withdrawal date, min/max payout limits, account status (PAY-03) # implied by PAY-03 + KYC-08
- `payout.risk_hold` 423 — open risk case (RSK-11); 403 variant when the hold is an active suspension (PAY-04 / LCC-11) # docs/11 §6.1
- `payout.not_funded` 409 — account not in FUNDED state # implied by PAY-01 "funded trader" + LCC-02
- `payout.amount_exceeds_available` 422 — beyond available profit (PAY-02: balance+equity − initial balance − prior payouts, partial payout rules) # implied by PAY-02
- `payout.method_not_confirmed` 400 — method not confirmed per PAY-05 # implied by PAY-05
- `payout.invalid_address` 400 — chain-specific crypto address validation failed # implied by PAY-45
- `payout.schedule_not_due` 422 — frequency/next-withdrawal-date enforcement # implied by PAY-21

### GET /v1/trader/payouts
Auth: Trader (self) — TD-10 (track payout status)
Tenant: from domain (GW-02)
Permission: self-read
Idempotency: n/a

Response 200:
```json
{ "payouts": [ { "payout_id": "TODO", "state": "TODO", "amount": "TODO" } ] }
```

Errors: none beyond standard gateway errors # TD-10

### POST /v1/trader/payout-methods
Auth: Trader — PAY-05 (V1.1)
Tenant: from domain (GW-02)
Permission: `payout.method.write` (self) # PAY-05
Idempotency: required # GW-12

Request:
```json
{ "type": "TODO", "details": "TODO" }
```

Response 201:
```json
{ "payout_method_id": "TODO", "confirmation_state": "TODO" }
```

Errors:
- `payout.method_invalid` 400 — invalid details / failed chain-specific validation # implied by PAY-05 + PAY-45
- Confirmation flow (cooldown and re-confirmation rules referenced in Out Of Scope as "PAY-06 by design") — TODO — needs owner decision (PAY-06 is not a V1 row; confirm what V1.1 requires)

### GET /v1/admin/payouts/queue
Auth: Finance Approver — PAY-08
Tenant: from domain (GW-02)
Permission: `payout.read_queue` # PAY-08
Idempotency: n/a

Response 200:
```json
{ "payouts": [ { "payout_id": "TODO", "account": "TODO", "profit": "TODO", "rules": "TODO", "kyc": "TODO", "risk": "TODO" } ] }
```

Errors: none beyond standard gateway errors # PAY-08 (queue shows "full context including account, profit, rules, KYC, and risk")

### POST /v1/admin/payouts/{payout_id}/approve
Auth: Finance Approver — PAY-09
Tenant: from domain (GW-02)
Permission: `payout.approve` # PAY-09
Idempotency: required # GW-12

Request:
```json
{ "reason": "TODO" }
```

Response 200:
```json
{ "payout_id": "TODO", "state": "approved" }
```

Errors:
- `payout.not_pending_approval` 409 # implied by PAY-13 states
- `payout.ineligible` 422 — re-check at approval runs inside the approval lock (docs/11 §3.7); failure returns the sub-reason and the payout stays `pending_approval` (D39, docs/52) — no state change

Effects: emits payout.approved (PAY-09); posts payout obligation (LED-07, PAY-14); audit recorded (AUD-01).

### POST /v1/admin/payouts/{payout_id}/reject
Auth: Finance Approver — PAY-09
Tenant: from domain (GW-02)
Permission: `payout.approve` # PAY-09
Idempotency: required # GW-12

Request:
```json
{ "reason": "TODO" }
```

Response 200:
```json
{ "payout_id": "TODO", "state": "rejected" }
```

Errors:
- `payout.not_pending_approval` 409 # implied by PAY-13
- `payout.reason_required` 400 — recorded reason is the point of PAY-09 # implied by PAY-09

Effects: emits payout.rejected (PAY-09); trader notified (NOT-05 payout rejected template).

### POST /v1/admin/payouts/{payout_id}/execution
Auth: COO — PAY-12 (Build Strategy: "Manual for V1" — sending money is manual; this endpoint records reality)
Tenant: from domain (GW-02)
Permission: `payout.record_execution` # PAY-12
Idempotency: required # GW-12 — recording twice must not double-settle

Request:
```json
{ "provider": "TODO", "reference": "TODO", "amount": "TODO", "executed_at": "TODO" }
```

Response 200:
```json
{ "payout_id": "TODO", "state": "paid" }
```

Errors:
- `payout.not_approved` 409 # implied by PAY-13
- `payout.execution_mismatch` 400 — recorded amount ≠ approved amount (docs/11 §6.1); the recording is refused, payout state unchanged

Effects: settles obligation in ledger (LED-08 — Decision 6 consumer); emits PayoutPaid through the outbox (PAY-12 — resolved 2026-09-16 (Decision 6); consumed by LED-08, DOC-04, ANA-01).

### POST /v1/admin/payouts/export
Auth: Finance user — PAY-44 (V1.1)
Tenant: from domain (GW-02)
Permission: `payout.record_execution` (batch file feeds manual execution) # PAY-44 (key reuses PAY-12's — registry row cites both)
Idempotency: optional

Request:
```json
{ "payout_ids": ["TODO"], "format": "TODO" }
```

Response 200: provider-formatted batch file # PAY-44

Errors:
- `payout.no_approved_payouts` 422 # implied by PAY-44 (approved payouts only)

### PUT /v1/admin/payout-policy
Auth: Tenant Admin — PAY-38
Tenant: from domain (GW-02)
Permission: `payout.policy.write` # PAY-38
Idempotency: required # GW-12

Request:
```json
{ "challenge_id": "TODO", "min_payout": "TODO", "max_payout": "TODO", "first_payout_delay": "TODO", "payout_frequency": "TODO", "profit_split": "TODO", "partial_payout_rules": "TODO", "post_payout_balance_behavior": "TODO" }
```

Response 200:
```json
{ "updated": true }
```

Errors:
- `payout.policy_invalid` 400 # implied by PAY-38
- Policy versioning: policy edits never touch live funded accounts — terms are frozen at funding (LCC-20); new terms apply to fundings after the change (docs/07 §3.2)

## Internal contracts (no HTTP)
- PAY-02 available profit: from balance and equity (fresh via BRG-09 on-demand sync), minus initial balance and prior payouts, respecting partial payout rules.
- PAY-03 eligibility engine: KYC status (KYC-08), minimum trading days, consistency, trading day threshold, first withdrawal delay, next withdrawal date, min/max limits, account status. Thresholds are per-tenant policy values configured via `PUT /v1/admin/payout-policy` (PAY-38; defaults = the challenge/funded terms).
- PAY-04 risk hold: block on open risk cases (RSK-11) or active suspension (LCC-11).
- PAY-14 ledger: approval => obligation entry, execution => settled entry (LED-07, LED-08).

## Open contract questions
- Resolved 2026-09-17: payout state machine V1 edges and reserved states — see "Payout state machine (PAY-13)" above.
- TODO — needs owner decision: exact sub-reason codes list for `payout.ineligible` (PAY-03 names eight checks; code naming scheme open).
- TODO — needs owner decision: payout method confirmation flow in V1.1 (PAY-05 says "save and confirm"; steps and cooldown unspecified — Out Of Scope references a PAY-06 cooldown that is not a V1 row).
- Resolved 2026-09-19 (docs/52): the catalog consumer binding IS the tie — `payout.approved`/`payout.rejected` list NOT-01 (NOT-05 templates) as V1 consumers (contracts/events/catalog.md); NOT-01 consumes the events.
- Resolved 2026-09-17: `failed` has no V1 entry path — reserved for V2 failure/retry (PAY-18). See "Payout state machine (PAY-13)" above.
- Resolved 2026-09-19 (docs/52): V1 is USD-only (docs/38 Out of Scope); all amount fields are single-currency integer cents (`currency CHAR(3) DEFAULT 'USD'` stays for V2 multi-currency).

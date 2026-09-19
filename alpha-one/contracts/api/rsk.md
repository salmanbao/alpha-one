# Risk API Contract (RSK)

Status: DRAFT
Owner: TBD
Version: v1
Last updated: TODO

Derived from the V1 Execution Sheet (V1.0 / V1.1). Nothing here is final until contract freeze.

## Scope
Signal and case model (RSK-01: signals with type, score, source, evidence, status; cases with linked accounts, traders, review actions, final decision), case opening automatic on threshold or manual by staff (RSK-10), payout hold while a case is open (RSK-11, consumed by PAY-04/PAY-03).

## Auth
Manual case opening in admin group (GW-01). Review surface — TODO — needs owner decision (RSK-01 models review actions and final decision, but no V1 row defines a case-management UI or its endpoints; Out Of Scope: humans decide — no auto-fail/auto-block).

## Tenant resolution
From domain (GW-02). Signals and cases are tenant-scoped (TEN-03).

## Permissions
- `risk.case.create` — manual case opening # derived from RSK-10 "or manually by staff"
- Case review/decision permissions — TODO — needs owner decision

## Idempotency
Mutating requests accept an idempotency key per GW-12. Automatic case opening is idempotent per signal — TODO — needs owner decision (dedupe rule unspecified).

## Endpoints

### POST /v1/admin/risk/cases
Auth: staff — RSK-10 (manual opening)
Tenant: from domain (GW-02)
Permission: `risk.case.create` # RSK-10
Idempotency: required # GW-12

Request:
```json
{ "account_id": "TODO", "trader_id": "TODO", "reason": "TODO", "linked_signals": ["TODO"] }
```

Response 201:
```json
{ "risk_case_id": "TODO", "state": "open" }
```

Errors:
- `risk.account_not_found` 404 # implied by RSK-01 linked accounts
- `risk.case_already_open` 409 — one open case per account rule — TODO — needs owner decision (rule not in sheet)

## Internal contracts (no HTTP)
- RSK-01 model: signals (type, score, source, evidence, status) grouped into cases (linked accounts, traders, review actions, final decision).
- RSK-10 automatic opening: signal score crosses a configured threshold — threshold config surface — TODO — needs owner decision.
- RSK-11 payout hold: open case on the account blocks payout eligibility (consumed by PAY-04 in PAY-03 checks).

## Events emitted
- None named in the sheet. Case-opened notifications to staff — TODO — needs owner decision (no V1 row requires it; NOT-05 has no such template).

## Open contract questions
- TODO — needs owner decision: case review/decision endpoints and states (RSK-01 models them; V1 rows do not define the workflow UI/API).
- TODO — needs owner decision: signal producers in V1 — which modules emit risk signals and on what triggers (no V1 row names a producer; detectors like copy-trading are Out Of Scope).
- TODO — needs owner decision: threshold configuration surface (per tenant? per signal type?).
- TODO — needs owner decision: case closure effects (does closing a case release the PAY-04 hold immediately?).

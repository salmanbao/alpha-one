# Risk API Contract (RSK)

Status: DRAFT
Owner: TBD
Version: v1
Last updated: 2026-09-20

Derived from the V1 Execution Sheet (V1.0 / V1.1). Nothing here is final until contract freeze.

## Scope

Signal and case model (RSK-01: signals with type, score, source, evidence, status; cases with linked accounts, traders, review actions, final decision), case opening automatic on threshold or manual by staff (RSK-10), payout hold while a case is open (RSK-11, consumed by PAY-04/PAY-03 — the interlock wires in V1.1, task 2.1; in V1.0 the case carries the dormant `payout_hold` flag — D68, docs/60).

## Auth

The tenant-admin group (GW-01; D46): staff realm on `/v1/admin/risk/*`. The review surface is the ADM **Risk cases** screen (docs/17 §3.1, V1-era thin view; task 1.4's exit walk — resolved 2026-09-20, docs/60). Humans decide — no auto-fail/auto-block (Out Of Scope).

## Tenant resolution

From domain (GW-02). Signals and cases are tenant-scoped (TEN-03).

## Permissions

- `risk.case.create` — manual case opening (RSK-10); bound `firm:owner`, `firm:admin`, `firm:risk`
- `risk.case.read` — the risk queue: cases, signal summaries, hold state (docs/17 §3.1 — resolved 2026-09-20, docs/60)
- `risk.case.decide` — decide a case (outcome + note); **2FA step-up always** (D70 — resolved 2026-09-20, docs/60; the D38 `authz.step_up_required` chain)

## Idempotency

Mutating requests accept an idempotency key per GW-12. Automatic (breach) case opening is idempotent per breach verdict id — the `dedup_key` (kind + normalized scope, §3.1; the Redis SETNX is best-effort, the PG unique constraint is the backstop — resolved 2026-09-20, docs/60).

## Endpoints

### POST /v1/admin/risk/cases
Auth: staff — RSK-10 (manual opening)
Tenant: from domain (GW-02)
Permission: `risk.case.create`
Idempotency: required (GW-12)

Request:
```json
{ "trader_id": "01J9...", "accounts": ["01J9ACC..."],
  "signals": [ { "kind": "manual", "note": "two accounts same IP per trader claim" } ],
  "payout_hold": true }
```

Response 201 (D45):
```json
{ "data": { "id": "01J9CASE...", "kind": "manual", "severity": "high",
    "trader_id": "01J9...", "accounts": ["01J9ACC..."], "payout_hold": true,
    "signals": [ { "kind": "manual", "note": "two accounts same IP per trader claim" } ],
    "status": "open" },
  "meta": { "request_id": "01J9ULID...", "version": "v1" } }
```

Errors:
- `risk.account_not_found` 404 — case target account unknown
- `risk.case_already_open` 409 — **one open case per account** (the D71 rule, docs/60): enforced as a transactional check under a per-trader advisory lock (accounts is an array; no plain unique index)

### GET /v1/admin/risk/cases
Auth: staff — the ADM risk queue (docs/17 §3.1)
Permission: `risk.case.read`

Response 200 (D45): `{ "data": [ …case rows (id, kind, severity, trader, accounts, hold state, age)… ], "meta": { … } }`

### GET /v1/admin/risk/cases/{id}
Auth: staff — case detail (signals summary, hold state)
Permission: `risk.case.read`

Response 200 (D45): the case row with `signals[]` and `actions[]`. Errors: `risk.case_not_found` 404.

### POST /v1/admin/risk/cases/{id}/decide
Auth: staff — the case machine (docs/10 §5; task 1.4's exit walk)
Permission: `risk.case.decide` + **2FA step-up** (D70)
Idempotency: required (GW-12)

Request:
```json
{ "outcome": "confirmed", "note": "IP evidence checks out" }
```

Response 200 (D45):
```json
{ "data": { "status": "decided", "outcome": "confirmed",
    "actions": [ { "type": "payout_hold", "state": "kept" } ],
    "decided_by": "01J9...", "decided_at": 1758278400000 },
  "meta": { "request_id": "01J9ULID...", "version": "v1" } }
```

Errors:
- `risk.case_not_found` 404
- `risk.case_closed` 409 — action on a decided case (appeal is V2)
- `risk.decision_conflict` 409 — concurrent decision (optimistic lock)

## Internal contracts (no HTTP)
- RSK-01 model: signals (type, score, source, evidence, status) grouped into cases (linked accounts, traders, review actions, final decision). V1 signal kinds: `breach`, `manual` (the `risk_signal_kinds` data registry — D69-era unification, docs/60).
- RSK-10 automatic opening: in V1.0 the only automatic opener is the breach case on `AccountBreached` (D68); score-threshold opening arrives with the V2 detectors (RSK-28; the threshold configuration surface is the V2 detector manifest, RSK-20 — no V1 config surface).
- RSK-11 payout hold: open case on the account blocks payout eligibility (consumed by PAY-04 in PAY-03 checks) — **V1.1**, task 2.1 (D68); the check fails with `payout.risk_hold` 423. Case closure effects (resolved, docs/60): `dismissed` releases the hold immediately; `confirmed` keeps it; the RSK-31 expiry (V2) auto-closes the case and releases.

## Events emitted
- `risk.case_opened`, `risk.case_decided` — V1 catalog events (D65, docs/59). Case-opened staff notifications: none in V1 (the ADM queue is the surface; the risk-case email templates stay V2 reserves — D61, docs/58).

## Open contract questions
- Resolved 2026-09-20 (docs/60): case review/decision endpoints = `POST /v1/admin/risk/cases/{id}/decide` (V1.0 — the case machine's `decided` edge; docs/17 §3.1's queue) + `risk.case.decide` with always-step-up (D70).
- Resolved 2026-09-20 (docs/60): V1 signal producers = the breach case opener (kind=breach, on `AccountBreached` — D68) and staff (kind=manual). No detector fires in V1.0 (empty manifest by design).
- Resolved 2026-09-20 (docs/60): threshold configuration = none in V1 (V2 detector manifest, RSK-20/28).
- Resolved 2026-09-20 (docs/60): case closure effects — dismissed releases the hold, confirmed keeps it, RSK-31 expiry (V2) releases + auto-closes.

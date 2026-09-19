# Evaluation Engine API Contract (EVL)

Status: DRAFT
Owner: TBD
Version: v1
Last updated: TODO

Derived from the V1 Execution Sheet (V1.0 / V1.1). Nothing here is final until contract freeze.

## Scope
Challenge template builder, rule set versioning and migration, pure evaluation function, evaluation triggers, profit target / daily drawdown / max drawdown rules, trailing HWM mechanics, evaluation audit, hard breach action, pass detection/auto-pass, manual override (V1.1), manual re-evaluation trigger (V1.1), regression suite. (EVL-01, EVL-02, EVL-04, EVL-05, EVL-06, EVL-07, EVL-08, EVL-16, EVL-17, EVL-19, EVL-20, EVL-29, EVL-34, EVL-35, EVL-36)

## Auth
Challenge/rule-set admin endpoints sit in the admin route group (GW-01), Tenant Admin role (AUTH-12). Manual override requires a dedicated permission (EVL-20: "with permission").

## Tenant resolution
From domain (GW-02). Rule sets and accounts are tenant-scoped (TEN-03).

## Permissions
- Challenge and rule set management: `challenge.write`, `ruleset.write` # keys derived from EVL-01/EVL-34 stories — TODO — needs owner decision on exact key names
- Manual pass/fail/reset: `account.manual_override` # EVL-20 (compare working-session draft `account.force_pass` — that Req ID LCC-12 is not in the sheet)

## Idempotency
Mutating requests accept an idempotency key per GW-12. Evaluation triggers are idempotent by (account, snapshot) inputs — TODO — needs owner decision on the exact dedupe key.

## Endpoints

### POST /v1/admin/challenges
Auth: Tenant Admin — EVL-01
Tenant: from domain (GW-02)
Permission: `challenge.write` # AUTH-13, key derived from EVL-01
Idempotency: required # GW-12

Request:
```json
{ "type": "TODO", "account_sizes": ["TODO"], "pricing": "TODO", "phases": "TODO", "per_phase_rules": "TODO" }
```

Response 201:
```json
{ "challenge_id": "TODO" }
```

Errors:
- `challenge.invalid_config` 400 — phases/rules/pricing inconsistent # implied by EVL-01; exact validation set TODO — needs owner decision

### PATCH /v1/admin/challenges/{challenge_id}
Auth: Tenant Admin — EVL-01
Tenant: from domain (GW-02)
Permission: `challenge.write` # EVL-01
Idempotency: required # GW-12

Request:
```json
{ "pricing": "TODO" }
```

Response 200:
```json
{ "challenge_id": "TODO" }
```

Errors:
- `challenge.not_found` 404 # implied by EVL-01
- Pricing edit interaction with in-flight checkout sessions (CHK-02 price reservation) — TODO — needs owner decision

### POST /v1/admin/rule-sets
Auth: Tenant Admin — EVL-02
Tenant: from domain (GW-02)
Permission: `ruleset.write` # derived from EVL-02 versioning
Idempotency: required # GW-12

Request:
```json
{ "challenge_id": "TODO", "rules": "TODO" }
```

Response 201:
```json
{ "rule_set_id": "TODO", "version": "TODO" }
```

Errors:
- `ruleset.invalid_rules` 400 # implied by EVL-02

### POST /v1/admin/rule-sets/{rule_set_id}/versions
Auth: Tenant Admin — EVL-02, EVL-34
Tenant: from domain (GW-02)
Permission: `ruleset.write` # EVL-02
Idempotency: required # GW-12

Request:
```json
{ "rules": "TODO", "migration_policy": "TODO" }
```

Response 201:
```json
{ "rule_set_id": "TODO", "version": "TODO", "affected_accounts": "TODO" }
```

Errors:
- `ruleset.not_found` 404 # implied by EVL-02
- Migration policy options and preview payload — TODO — needs owner decision (EVL-34 promises an impact view and a chosen policy; shapes unspecified)

### POST /v1/admin/accounts/{account_id}/evaluate
Auth: support staff (V1.1) — EVL-36
Tenant: from domain (GW-02)
Permission: `account.evaluate` # derived from EVL-36 "force re-evaluation"
Idempotency: required # GW-12 — repeated triggers on the same corrected snapshot must not double-fire breach actions

Request:
```json
{ "reason": "TODO" }
```

Response 202:
```json
{ "evaluation_id": "TODO" }
```

Errors:
- `account.not_found` 404 # implied by LCC-01 aggregate
- `account.terminal_state` 409 — evaluating a FAILED/TERMINATED account — TODO — needs owner decision (rule not in sheet)

### POST /v1/admin/accounts/{account_id}/override
Auth: Tenant Admin (V1.1) — EVL-20
Tenant: from domain (GW-02)
Permission: `account.manual_override` # EVL-20
Idempotency: required # GW-12

Request:
```json
{ "action": "TODO", "reason": "TODO" }
```

Response 200:
```json
{ "account_id": "TODO", "status": "TODO" }
```

Errors:
- `account.not_found` 404 # implied
- `override.action_unknown` 400 — action not in pass/fail/reset # implied by EVL-20
- `override.reason_required` 400 — reason recorded per EVL-20 # implied by EVL-20

## Internal contracts (no HTTP)
- Pure evaluation function (EVL-04): inputs = snapshot + rule set version; outputs = per-rule results with observed values and reasons. Deterministic; golden-case regression suite proves no drift (EVL-35).
- Triggers (EVL-05): on sync snapshot (BRG-07), on trade close (BRG-08), daily schedule, admin demand. Schedule time — TODO — needs owner decision.
- Trailing HWM (EVL-29): persisted per account; ratchets only upward; balance-vs-equity basis locked per account at creation (EVL-08). Basis flag storage — see `data/schemas/accounts.sql`.
- Hard breach (EVL-17): transition to BREACH_DETECTED + enqueue disable-then-close commands (BRG-10 via EVT-20).
- Pass detection (EVL-19): all objectives + day requirements met => PASS_PENDING; auto-advance or queue for verification per config.
- Evaluation audit (EVL-16): every evaluation stores inputs hash, rule version, observed values, thresholds, result (AUD-01 storage).

## Events emitted/consumed
- Trigger inputs: sync snapshots (BRG-07), trade closes (BRG-08), daily schedule, and admin demand (EVL-05 names all four triggers).
- Emits: pass/breach outcomes surface as AccountPassed, AccountBreached, AccountFailed — lifecycle events are LCC-emitted (LCC-23).

## Open contract questions
- TODO — needs owner decision: exact rule parameters set (EVL-06/07/08 name rule families; full parameter list per rule needs the rule-set schema).
- TODO — needs owner decision: daily reset time and timezone handling for EVL-07 daily starting balance.
- TODO — needs owner decision: trailing HWM ratchet basis enum values and where the basis is configured (EVL-29 says explicit, sheet does not enumerate).
- TODO — needs owner decision: auto-advance vs verification-queue config location (EVL-19 per config — challenge-level or tenant-level?).
- TODO — needs owner decision: minimum trading days and consistency checks (referenced by PAY-03 eligibility; not defined as EVL rules in V1 sheet).
- TODO — needs owner decision: evaluation audit storage table ownership (EVL-16 writes; AUD module owns schema?).

# Account Lifecycle API Contract (LCC)

Status: DRAFT
Owner: TBD
Version: v1
Last updated: 2026-09-17

Derived from the V1 Execution Sheet (V1.0 / V1.1). Nothing here is final until contract freeze.

## Scope
Authoritative TradingAccount aggregate, guarded state machine, state history/audit, provisioning on purchase, provisioning on phase pass, KYC-gated funding, suspension and resume (V1.1), payout terms at funding, lifecycle events, terminal state cleanup. (LCC-01, LCC-02, LCC-03, LCC-05, LCC-06, LCC-07, LCC-11, LCC-20, LCC-23, LCC-27)

## State machine (LCC-02)
States: CREATED, ACTIVE, BREACH_DETECTED, CLOSING, FAILED, PASS_PENDING, VERIFICATION, AWAITING_ACTIVATION, FUNDED, SUSPENDED, TERMINATED. Transitions are guarded; invalid states impossible. See `contracts/diagrams/account-state.md`.

### Same-account edges (resolved 2026-09-17)

```text
CREATED             → ACTIVE                    broker account provisioned, credentials delivered (BRG-05, BRG-06)
ACTIVE              → BREACH_DETECTED           hard breach (EVL-17)
ACTIVE              → PASS_PENDING              objectives met (EVL-19)
ACTIVE              → SUSPENDED                 admin suspend (LCC-11, V1.1)
BREACH_DETECTED     → CLOSING                   disable-then-close enqueued (BRG-10, EVL-17)
CLOSING             → FAILED                    broker confirms closure (BRG-11)
PASS_PENDING        → VERIFICATION              manual verification required per config (EVL-19)
PASS_PENDING        → AWAITING_ACTIVATION       activation fee configured (LCC-08)
VERIFICATION        → AWAITING_ACTIVATION       approved, fee due (LCC-06 + LCC-08)
VERIFICATION        → TERMINATED                verification rejected
AWAITING_ACTIVATION → TERMINATED                payment window elapsed, no fee
FUNDED              → SUSPENDED                 admin suspend (LCC-11, V1.1)
SUSPENDED           → ACTIVE                    resume from evaluation-phase suspend (LCC-11)
SUSPENDED           → FUNDED                    resume from funded-phase suspend (LCC-11)
FUNDED              → TERMINATED                end of engagement (LCC-27)
FAILED              → TERMINATED                archival (LCC-27)
<any>               → TERMINATED                admin force-terminate (LCC-27)
```

`TERMINATED` is terminal-only: no outgoing edges. LCC-27 guarantees no orphaned positions or broker state, and a dead account cannot transition.

Citation note: the ACTIVE → PASS_PENDING branches and the AWAITING_ACTIVATION flow are supported by EVL-19 ("either auto-advance or queue it for verification per config") plus LCC-05/LCC-06/LCC-20/LCC-27 (all V1). The AWAITING_ACTIVATION hold-and-pay flow itself traces to LCC-08, which is **V2.0** in the Master Backlog — it is named here only because LCC-02 (V1) fixes the state; a V1 activation-fee product would require a PRD amendment. Flagged in the README open-questions list.

### Spawn edges (new account created; current account terminal at PASS_PENDING, VERIFICATION, or AWAITING_ACTIVATION)
- Next-phase creation (mid-challenge pass): new `CREATED` with `parent_account_id` set (LCC-06).
- Funded creation (final-phase pass, no activation fee): new `FUNDED`.
- Funded creation (activation fee paid): new `FUNDED`.

### KYC timing enum (per challenge config, LCC-07/KYC-07 gating)
`{at_creation, after_evaluation, at_first_payout, skipped}` — value set per KYC-03's timing description ("at account creation, after evaluation, at first payout, or skipped"); KYC-03 itself is **V2.0**, so V1 challenges may only use the subset their V1 gates (KYC-07/KYC-08) can enforce. Storage: `challenges.kyc_timing` in `data/dictionary.md`.

## Auth
Trader-facing reads sit in the trader route group; admin actions in the admin route group (GW-01). Suspension/resume requires Tenant Admin (LCC-11).

## Tenant resolution
From domain (GW-02). Accounts are tenant-scoped (TEN-03, AUTH-15).

## Permissions
- Suspend/resume account: `account.suspend` # LCC-11
- Read account detail: `account.read` # derived from ADM-05/TD-03 consumption — TODO — needs owner decision on trader self-read vs staff read keys

## Idempotency
Mutating requests accept an idempotency key per GW-12. Provisioning itself is idempotent end to end: order.paid (CHK-09) is deduplicated by provider event id (CHK-07) and broker account creation carries its own idempotency key (BRG-05).

## Endpoints

### GET /v1/trader/accounts
Auth: Trader — TD-03
Tenant: from domain (GW-02)
Permission: self-read (accounts of caller) # AUTH-13; key — TODO — needs owner decision
Idempotency: n/a

Response 200:
```json
{ "accounts": [ { "account_id": "TODO", "status": "TODO", "phase": "TODO", "balance": "TODO", "equity": "TODO", "open_pnl": "TODO" } ] }
```

Errors: none beyond standard gateway errors # TD-03

### GET /v1/trader/accounts/{account_id}
Auth: Trader (owner) — TD-03
Tenant: from domain (GW-02)
Permission: self-read
Idempotency: n/a

Response 200:
```json
{ "account_id": "TODO", "status": "TODO", "phase": "TODO", "rule_set_version": "TODO", "payout_terms": "TODO" }
```

Errors:
- `account.not_found` 404 # implied by LCC-01

### GET /v1/admin/accounts
Auth: Staff — ADM-05
Tenant: from domain (GW-02)
Permission: `account.read` # AUTH-13, key derived from ADM-05
Idempotency: n/a

Query filters: `status`, `phase`, `challenge`, `broker` # ADM-05

Response 200:
```json
{ "accounts": [ { "account_id": "TODO", "status": "TODO", "phase": "TODO" } ], "pagination": "TODO" }
```

Errors: none beyond standard gateway errors # ADM-05

### POST /v1/admin/accounts/{account_id}/suspend
Auth: Tenant Admin (V1.1) — LCC-11
Tenant: from domain (GW-02)
Permission: `account.suspend` # LCC-11
Idempotency: required # GW-12

Request:
```json
{ "reason": "TODO" }
```

Response 200:
```json
{ "account_id": "TODO", "status": "SUSPENDED" }
```

Errors:
- `account.not_found` 404 # implied
- `account.not_active` 409 — cannot suspend from current state — TODO — needs owner decision (guard set unspecified in LCC-02)

Effects: disables trading at the broker (BRG-14); emits Suspended (LCC-23); blocks payouts (PAY-04).

### POST /v1/admin/accounts/{account_id}/resume
Auth: Tenant Admin (V1.1) — LCC-11
Tenant: from domain (GW-02)
Permission: `account.suspend` (resume is the paired action) # LCC-11
Idempotency: required # GW-12

Request:
```json
{ "reason": "TODO" }
```

Response 200:
```json
{ "account_id": "TODO", "status": "ACTIVE" }
```

Errors:
- `account.not_suspended` 409 # implied by LCC-11

Effects: re-enables trading at the broker (BRG-14); emits Resumed (LCC-23).

## Internal contracts (no HTTP)
- Provisioning on purchase (LCC-05): consumes order.paid (CHK-09); creates phase 1 account via bridge (BRG-05) with group, leverage, balance; delivers credentials (BRG-06).
- Provisioning on phase pass (LCC-06): consumes verification approval (EVL-19 PASS_PENDING => VERIFICATION flow); creates next phase account and links phase lineage.
- KYC-gated funding (LCC-07): funded account creation gated on KYC status per challenge KYC timing config (KYC-07).
- Payout terms at funding (LCC-20): profit split, payout frequency, first withdrawal delay, next withdrawal date set at funded creation per challenge config (PAY-38 source).
- State history (LCC-03): every transition records prior state, new state, trigger, actor, inputs (AUD-01 storage).
- Terminal cleanup (LCC-27): on FAILED/TERMINATED, close open positions and disable at broker with audit. Mechanism per the sheet: enqueue disable-then-close commands in the command_queue (EVT-20), executed by the enforcement worker (BRG-10), with broker confirmations written back to the command and the account state (BRG-11) — so no orphaned open position is left live after the account is dead.

## Events emitted (LCC-23, via outbox EVT-01)
AccountCreated, PhaseAdvanced, AccountPassed, AccountBreached, AccountFailed, FundedCreated, Suspended, Resumed — see `contracts/events/catalog.md`.

## Open contract questions
- TODO — needs owner decision: phase lineage representation (LCC-06 links accounts via `parent_account_id`; whether a separate lineage table is needed).
- TODO — needs owner decision: whether suspend/resume is also exposed for staff (LCC-11 says tenant admin only).
- Resolved 2026-09-17: LCC-02 edge list, TERMINATED entry, KYC timing enum — see "State machine (LCC-02)" above. Note: the AWAITING_ACTIVATION hold-and-pay flow cites LCC-08 (V2.0); confirm with PRD owners whether a V1 activation-fee product is intended.

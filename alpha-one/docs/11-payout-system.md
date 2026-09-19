# 11 — PAY: Payout System

> Covers PRD module **PAY** (49 requirements). Payouts are where the platform's
> trust lives: a trader's real money, calculated from trading we enforce, moved
> through providers we don't control. Every number here must be recomputable,
> every state auditable, every rail reconcilable.

## 1. Purpose & scope

PAY owns: payout **methods** (trader's wallets/accounts), **eligibility**, the
**profit calculation**, the **approval workflow** (manual in V1 — PRD default),
**execution** through rails, **status tracking** to settlement, and
**reconciliation** against provider reports.

Rails (V1): **crypto via NOWPayments** (TRC20/ERC20/BEP20 — ~1% fee) and
**local methods via Match2Pay/Interkasa** where the provider supports disbursement.
Wires (V2 CHK-38 family), multi-network crypto (PAY-43 V2), instant payout
option (PAY-41 V2). **Manual approval at launch** for all tenants (auto-approve
toggle PAY-11 is V2; FunderBlu default = manual, reviewed in ADM).

Requirement coverage: `PAY-01,02,03,08,09,12,13,14,21,38` (V1.0) + `04,05,44,45` (V1.1) +
`06,07,10,11,15..20,22..37,39..43,46..49` (V2.0).

## 2. Architecture

```
 trader (TD) ──request──► BRG-09 on-demand sync (fresh snapshot)
                          PAY: eligibility gate (KYC-08, RSK-11/PAY-04 hold,
                               funded status, min/max, delays, frequency,
                               account status — PAY-03, synchronous)
                               → available profit (PAY-02: balance+equity −
                                 initial − prior payouts)
                               → pending_approval (queue with full context:
                                 account, profit, rules, KYC, risk — PAY-08)
 finance (ADM) ──approve/reject (reason)──► approved (emits payout.approved)
                                            └► LED-07 obligation posted (PAY-14)
 COO ──record execution (provider, reference, amount, timestamp — PAY-12)
        (Build Strategy: "Manual for V1" — sending money is manual)
        ──► paid (emits PayoutPaid via outbox — Decision 6)
             └► LED-08 obligation settled · DOC-04 certificate · NOT-01
 reject path: reason recorded, payout.rejected, trader notified (NOT-05)
 nightly: reconciliation (V2 PAY-34) + reserves check (V2 PAY-37)
```

The V1 sequence in full: `contracts/diagrams/payout-flow.md` (rendered PNG
alongside).

Components (from the research, adapted):
- **Orchestrator** = the state machine below (no Temporal in V1 — command/worker
  pattern, same as LCC; Temporal is the V2 upgrade path if approval flows grow).
- **Profit calculator** = pure function (inputs frozen at request time —
  PAY-27 V2 names it; we do it in V1 because it's non-negotiable for disputes).
- **Rail adapters** = strategy interface (same pattern as BRG/CHK/KYC).
- **Ledger** = LED (05) — PAY calls `ledger.Post`, never keeps its own books.
- **Approval workflow** = V1: single human decision (manual default); V2:
  threshold second-approval (PAY-10), batch (PAY-19/42), delegation (PAY-46),
  auto-approve rules (PAY-11).

## 3. System design

### 3.1 Eligibility (PAY-03) — checked at request time AND re-checked at approval

| Check | Source | Fail code |
|---|---|---|
| Account is `funded` and `active` (not paused/suspended/failed) | LCC | `payout.not_funded` / `payout.account_state` |
| KYC payout-level verified (KYC-08 gate; L2 + wallet name match V2) | KYC | `payout.kyc_required` |
| No open risk case with payout hold (RSK-10) | RSK | `payout.risk_hold` |
| Frequency window elapsed since last settled payout (funded terms: `payout_frequency_days`, `first_payout_delay_days`) — PAY-21 | funded_terms + payout history | `pay.frequency` |
| Amount ≥ `min_amount_cents` (terms) | terms | `payout.below_min` |
| One active request per account (enforced day 1; PAY-28 V2 formalizes UX) | PAY | `payout.active_exists` |
| Balance: payoutable = HWM − initial − paid_out, floor 0 (see §3.2) | calc | `payout.nothing_due` |

### 3.2 Profit calculation (PAY-02) — the frozen-snapshot function

```
inputs (frozen into payout_requests.calc_snapshot at request time):
  initial_balance_cents          (from account terms)
  hwm_cents                      (EVL high_water_equity_cents — EVL-29)
  equity_cents_now               (latest verified snapshot; staleness guard:
                                  tick age < 10 min else reject with `pay.stale_data` (409))
  settled_paid_cents             (Σ final_payout_amount of settled payouts, this account)
  split_ratio_bps                (funded terms: e.g. 8000 = 80%)
  min_amount_cents, currency     (funded terms)
  rail_fee                       (provider: NOWPayments ~1% — computed per rail)
  tenant_fee_cents               (tenant payout fee if configured, V2)

steps (integer cents, ROUND_HALF_UP only at the final display conversion):
  1. gross        = max(0, hwm − initial)                 # HWM-based: payouts never
                                                          # exceed high-water profit
  2. available    = max(0, gross − settled_paid)          # no double-paying
  3. trader_share = available × split_ratio_bps / 10_000  # (trader's cut of profit)
  4. cap          = min(requested_cents, trader_share)
  5. fee          = cap × rail_fee_bps / 10_000           # rail bears fee unless
                                                          # tenant says otherwise
  6. final        = cap − fee
output: every step stored in calc_snapshot (disputes recompute from this)
```

Notes: (a) **HWM-based, not equity-based** — the trader can't lose payout rights
by trading after requesting; (b) equity staleness guard makes the input honest
(PAY-29 V2 forces a fresh broker read pre-execution); (c) adjustments (V2
PAY-30: finance can correct with reason + 2FA → new calc_snapshot version,
original retained).

### 3.3 State machine (PAY-13, V1 — binding)

States are exactly those named by PAY-13 (`contracts/diagrams/payout-state.md`,
rendered PNG alongside):

```
requested ──checks pass (PAY-03)──► eligibility_checked
                                       │ queued (PAY-08)
                                       ▼
                                  pending_approval ──approve with reason (PAY-09)──► approved
                                       │                                              │
                                       └──reject with reason (PAY-09)──► rejected    │ COO records
                                                                                     │ execution
                                                                                     │ (PAY-12)
                                                                                     ▼
                                                                                   paid ──► (terminal;
                                                                                             obligation settled,
                                                                                             LED-08)
rejected ──► (terminal; trader notified, NOT-05 payout-rejected template)
```

**Failed eligibility never creates a payout** — PAY-03 is a synchronous gate,
so an ineligible request returns `payout.ineligible` (with sub-reasons) and no
payout row is created; there is no `requested → rejected` edge in V1.
`rejected` is reached only from `pending_approval` (PAY-09).

**Reserved states — defined by PAY-13, no V1 entry path:**

- `processing` — V2 automated provider execution (PAY-24). V1 execution is
  manual (PAY-12, Build Strategy "Manual for V1"); the manual-send window is
  elapsed time between `approved` and `paid`, not a state.
- `failed` — V2 failure/retry (PAY-18). No V1 row defines entry conditions.
- `cancelled` — V2 trader cancellation (PAY-17). No V1 row defines entry
  conditions.

The state list is fixed by PAY-13 (V1) — the states are not removed; V1 code
simply never transitions into these three.

**The hold flag (D32, docs/52):** an approved-but-unexecuted payout whose
account breaches keeps `status='approved'` with `status_reason='on_hold'`
(the RSK breach case also opens with `payout_hold`, docs/10 §3) and lands in
the human queue — hold is a **flag, not a machine state** (PAY-13's list is
fixed); the approver executes or rejects each held payout by hand.

**Ledger coupling:** approval posts the payout obligation (LED-07, PAY-14);
recorded execution settles it (LED-08). Both are event-driven:
`payout.approved` → LED-07; `PayoutPaid` (emitted by PAY-12 through the
outbox — Decision 6, 2026-09-16) → LED-08 + DOC-04 + ANA-01.

**Execution recording (PAY-12):** every recorded execution is appended to
`payout_executions` (provider, reference, amount, timestamp, actor) — the COO's
"proof it actually left" record. Recording twice must not double-settle
(idempotency, GW-12).

> Extended (post-V1) execution model: the rail-adapter worker, retry policy
> (15 m / 1 h / 6 h), `failed_final` → human queue, provider webhooks
> (EVT-10), and reconsider — all V2 (PAY-18/24), when `processing`/`failed`
> get entry paths.

### 3.4 Payout methods (PAY-05) + crypto validation (PAY-45)

Methods: `{crypto_trc20, crypto_erc20, crypto_bep20, local:{provider method}}`,
each with field-encrypted details (wallet address / account ref). Rules:
- **Address validation (V1):** per-chain format check (length/charset/base58/bech32
  as applicable) + checksum where the chain has one (EIP-55 for ERC20 addresses);
  V2: test-transfer verification (PAY-35) + name match (PAY-07).
- **Method change cooldown (PAY-06, V2):** a method edited < 72 h before payout
  request triggers a warning flag on the request (fraud pattern: compromised
  trader account).
- **Default method (PAY-49, V2)** + per-tenant method catalog (PAY-26).

### 3.5 Approval UX & controls

ADM payout queue (PAY-08): columns — trader, account, amount, rail, age,
eligibility re-check (live badge), **risk context** (open cases — RSK-35 V2;
V1: case flag), action buttons. Approve = hosted re-auth step-up
(`prompt=login&max_age=300`; the API enforces `auth_time` ≤ 5 min and returns
`authz.step_up_required` when stale — docs/02 §3.2, decision D23) + optional
note; reject = **reason required** (taxonomy: `insufficient_kyc`, `risk_review`,
`balance_mismatch`, `suspicious_method`, `other:{note}`). Batch export
(PAY-44, V1-Plus: CSV of the queue for the COO's spreadsheet world). V2:
threshold second approval (PAY-10), delegation (PAY-46), batch approve (PAY-19),
SLA tracking (PAY-40).

### 3.6 Reconciliation & reserves (V2 PAY-34/37/48; V1 manual)

Nightly (V2): import provider settlement report → match `payout_executions`
external refs → exceptions to ADM finance (LED-13 pattern); fee reconciliation
(PAY-48: actual provider fee vs `fee` in calc → ledger adjustment entry).
Reserves (PAY-37, V2): tenant's collected-challenge-funds balance (LED `cash`
account) ≥ pending obligations (Σ approved+processing) → breach = CON CRITICAL
(the platform never promises a payout the tenant's collected funds can't cover —
FunderBlu's TTS-parity rule). **V1 (D38, docs/52): visibility only** — the CON
dashboard plots `cash` vs open obligations nightly and the ADM queue shows a
reserve banner; there is **no hard block in V1** (human approvers in the loop
at ~50 payouts/day).

### 3.7 Execution safety (exactly-once per payout)

V1 execution is **manual** (PAY-12, Build Strategy "Manual for V1"): the COO
sends via the provider's dashboard and records the result. The three guards
below bind the **approval and recording paths in V1** and are the same guards
the V2 rail executor (PAY-24) carries forward — the `approved → processing →
settled` rail-worker narrative (sweeper, retries, provider idempotency keys)
is the V2 design, not a V1 state path (V1 terminal is `paid`; `processing` has
no V1 entry — §3.3):

1. **Per-payout mutex (PG advisory lock):**
   `SELECT pg_advisory_xact_lock(hashtext('payout:' || payout_id))` — held
   for the whole approve→execute transaction. Two workers can never execute
   the same payout concurrently, and the lock dies with the transaction
   (no orphan-lock sweeper needed).
2. **Status CAS:** V1 approve path: `UPDATE payout_requests SET
   status='approved' WHERE id=? AND status='pending_approval'` — 0 rows
   affected means a concurrent approver won; the loser exits quietly. The
   **eligibility re-check (PAY-03) runs inside the lock**, so two concurrent
   approvals of the same profit can't both pass (the second sees the first's
   obligation row). A failed re-check returns `payout.ineligible` and the
   payout **stays `pending_approval`** — no state change; the approver may
   reject manually with a reason (D39, docs/52). V2 executor: the same CAS
   moves `approved → processing` (PAY-24).
3. **Recording CAS (V1) / rail idempotency (V2):** V1 recording is
   `UPDATE payout_requests SET status='paid' WHERE id=? AND
   status='approved'` under the GW-12 idempotency key — recording twice can
   never double-settle (LED-08 posts once; the duplicate returns the first
   result). V2: the provider idempotency key is the payout ULID; a retried
   rail call returns the original transfer.

**Redlock (research §10) explicitly rejected:** at one PG box, advisory
locks are transactional *with the state change they guard* — a Redis fence
adds a failure mode (fencing-token plumbing, clock-drift reasoning) for zero
benefit. Revisit only if executors ever span PGs. **Crash recovery:** a
`processing` row older than 15 min is reaped by the sweeper → transient rail
errors retry with backoff (≤ 5 attempts), deterministic failures go straight
to the manual ticket (no unbounded auto-retry, §3.5).

## 4. Events (topic `payout`)

### 4.1 V1 baseline events — authoritative

From `contracts/events/catalog.md` (the V1 execution sheet). Envelope EVT-03 (`id`, `type`, `version`, `tenant_id`, `occurred_at`, `correlation_id`, `payload` — correlation_id required since docs/49 C1); schemas in `contracts/events/payloads/`. Producers write the outbox (EVT-01); consumers are idempotent by event id (EVT-05).

| Event | Producer (V1) | V1 consumers |
|---|---|---|
| `payout.approved` | PAY-09 | LED-07 (payout obligation posting), NOT-01 (template: payout approved), ANA-01 |
| `payout.rejected` | PAY-09 | NOT-01 (template: payout rejected), ANA-01 |
| `PayoutPaid` | PAY-12 (execution recording, via outbox — Decision 6) | LED-08 (settlement posting), DOC-04 (certificate), ANA-01 |

**Mapping to the extended model below:** `payout.approved` / `payout.rejected` are the same events (their extended-table rows are folded into the baseline table above); `PayoutPaid` = the extended `payout.settled` (Decision 6, 2026-09-16: emitted by PAY-12 through the outbox). The extended `payout.requested` has no V1 counterpart — resolved D37 (docs/52): no V1 request event (the 201 + TD status is the ack; the finance queue reads the table, PAY-08); template 7 is a V2 reserve.

### 4.2 Extended (post-V1) event model — design-level

> The extended event set for V2/V3 (and internal V1 detail where marked); see the mapping above for how it relates to the V1 baseline. Topic, dedupe, and transport rules unchanged (docs/04 §5).

| Event | When | Consumers |
|---|---|---|
| `payout.requested` | request created (eligible) | NOT (trader + finance), ANA |
| `payout.eligibility_failed` | request rejected at validation | NOT (trader, reason template) |
| `payout.execution_attempted` | each send/retry | AUD |
| `payout.failed` / `payout.failed_final` | rail failure | NOT (on final), ADM, AUD |
| `payout.cancelled` | trader cancel (pre-approval) | NOT, ANA |
| `payout.hold_set` / `payout.hold_released` | RSK interplay (V2) | AUD |
| `payout.reconciled` / `payout.reconciliation_exception` (V2) | nightly | ADM, CON, AUD |
## 5. Lifecycles

- **Payout request:** the PAY-13 state machine above (§3.3). V1 terminal
  states: `paid` (obligation settled, LED-08) and `rejected` (trader notified,
  NOT-05). `processing`/`failed`/`cancelled` are reserved (no V1 entry path —
  §3.3). Failed eligibility creates no payout row.
- **Payment method:** `active → (edited: versioned, cooldown flag) →
  deactivated (trader)`. Edits are versioned rows (`payout_methods` is
  append-mostly: new version, old rows retained — the "which address did the
  $2k go to" question is always answerable: the method **version** used is on
  the request).
- **Calculation snapshot:** immutable per request (adjustments = new version,
  V2).
- **Rail circuit breaker:** per provider: 5 consecutive failures → open 30 min
  (new requests queue with ETA, executions pause).

## 6. Error taxonomy
### 6.1 V1 baseline codes — authoritative

From `contracts/errors/taxonomy.md` (the V1 execution sheet; module PAY). These are the exact codes the V1 surfaces return; the envelope is GW-18 (`code`, `message`, `correlation_id`).
| Code | HTTP | Meaning | User-facing message |
|---|---|---|---|
| `payout.ineligible` | 422 | Failed an eligibility check; sub-reasons from PAY-03: KYC not approved (KYC-08), minimum trading days, consistency, trading day threshold, first withdrawal delay, next withdrawal date, min/max limits, account status | "You are not eligible for a payout yet: {reason}." |
| `payout.kyc_required` | 422 | Payout gate blocked pending KYC approval | "Verify your identity before requesting a payout." |
| `payout.risk_hold` | 423/403 | Open risk case (RSK-11) or active suspension (PAY-04) | "Payouts are temporarily held for review." |
| `payout.not_funded` | 409 | Account not in FUNDED state | "Payouts are only available on funded accounts." |
| `payout.amount_exceeds_available` | 422 | Beyond available profit (HWM − initial − prior payouts, pre-split — §3.2) | "Amount exceeds your available profit." |
| `payout.schedule_not_due` | 422 | Frequency or next-withdrawal-date not reached | "Your next payout is available on {date}." |
| `payout.method_not_confirmed` | 400 | Payout method not confirmed | "Confirm your payout method first." |
| `payout.invalid_address` | 400 | Chain-specific crypto address validation failed | "That wallet address is not valid for {chain}." |
| `payout.method_invalid` | 400 | Payout method details invalid | "Please check your payout details." |
| `payout.not_pending_approval` | 409 | Approve/reject on a payout not pending approval | "This payout has already been decided." |
| `payout.not_approved` | 409 | Execution recording on a non-approved payout | "This payout is not approved for execution." |
| `payout.reason_required` | 400 | Reject without recorded reason | "A reason is required." |
| `payout.no_approved_payouts` | 422 | Batch export contains no approved payouts | "Nothing to export." |
| `payout.execution_mismatch` | 400 | Recorded execution amount ≠ approved amount | "Recorded amount does not match the approved payout." |
| `payout.policy_invalid` | 400 | Payout policy configuration invalid | "Please check the payout policy values." |


Namespace `PAY` (user-safe messages — the trader-facing strings are in the
template registry, NOT):
### 6.2 Extended (post-V1) codes — design-level

> Below the V1 baseline (6.1); names in the GW-18 dotted convention. Rows duplicating a V1 baseline code were folded into the baseline table (the merged registry: docs/30).


| Code | HTTP | Meaning |
|---|---|---|
| `pay.not_eligible` (with `details.checks[]`) | 422 | Eligibility failed (each failed check named) |
| `payout.not_funded` / `payout.account_state` | 422 | — |
| `payout.kyc_required` | 422 | KYC payout gate |
| `payout.risk_hold` | 423 | Open risk case (reason class only) |
| `pay.frequency` | 422 | Window not elapsed (`details.next_eligible_at`) |
| `payout.below_min` | 422 | `details.min_cents` |
| `payout.active_exists` | 409 | Existing active request (id in details) |
| `payout.nothing_due` | 422 | Available = 0 |
| `pay.stale_data` | 409 | Snapshot older than 10 min — retry (transient) |
| `pay.method_invalid` | 422 | Address/format failed (chain named) |
| `pay.method_changed_recently` | 200 + flag | Warning flag, not a block (V2) |
| `pay.approval_required` | 403 | Self-serve approve attempt (no such route; defense-in-depth) |
| `pay.state_conflict` | 409 | Illegal transition attempt |
| `pay.rail_unavailable` | 503 | Circuit open (`details.retry_after`) |
| `pay.rail_rejected` | internal | Provider rejected (reason stored, retried per policy) |
| `pay.amount_adjusted` (V2) | — | Finance adjustment applied (audit) |

## 7. API endpoints
### 7.1 V1 baseline — `pay` (authoritative: `contracts/api/pay.md`)

| Method + path | Auth | Permission | Idempotency | V1 errors |
|---|---|---|---|---|
| `POST /v1/trader/payouts` | Trader (funded account owner) — PAY-01 | `payout.request` (self) # PAY-01 | required | `payout.ineligible`, `payout.risk_hold`, `payout.not_funded`, `payout.amount_exceeds_available`, `payout.method_not_confirmed`, `payout.invalid_address`, `payout.schedule_not_due` |
| `GET /v1/trader/payouts` | Trader (self) — TD-10 (track payout status) | `self` — own payouts | n/a | standard |
| `POST /v1/trader/payout-methods` | Trader — PAY-05 (V1.1) | `payout.method.write` (self) # PAY-05 | required | `payout.method_invalid` |
| `GET /v1/admin/payouts/queue` | Finance Approver — PAY-08 | `payout.read_queue` # PAY-08 | n/a | standard |
| `POST /v1/admin/payouts/{payout_id}/approve` | Finance Approver — PAY-09 | `payout.approve` # PAY-09 | required | `payout.not_pending_approval`, `payout.ineligible`, `authz.step_up_required` |
| `POST /v1/admin/payouts/{payout_id}/reject` | Finance Approver — PAY-09 | `payout.approve` # PAY-09 | required | `payout.not_pending_approval`, `payout.reason_required` |
| `POST /v1/admin/payouts/{payout_id}/execution` | COO — PAY-12 (Build Strategy: "Manual for V1" — sending money is manual; this endpoint records reality) | `payout.record_execution` # PAY-12 | required | `payout.not_approved`, `payout.execution_mismatch` |
| `POST /v1/admin/payouts/export` | Finance user — PAY-44 (V1.1) | `payout.record_execution` (batch file feeds manual execution) # PAY-44; key — TODO — needs owner decision | optional | `payout.no_approved_payouts` |
| `PUT /v1/admin/payout-policy` | Tenant Admin — PAY-38 | `payout.policy.write` # PAY-38 | required | `payout.policy_invalid` |

Scope, request/response shapes, and per-endpoint notes: `contracts/api/pay.md` (field values in the research are owner TODOs until contract freeze; canonical JSON is fixed at freeze, per the docs/99 §12 rules).

### 7.2 Extended (post-V1) surface — provisional

> Not in the V1 execution sheet. Design-level; paths beyond the V1 baseline are provisional until the URL-plan decision (`contracts/api/gw.md`, open question). Shown for platform completeness (V2/V3 phases, docs/99).

Trader (TD): `GET /v1/trader/payouts/eligibility?account_id=` (the TD-26 preview:
payoutable amount, next eligible time, method list),
`POST /v1/trader/payouts/requests` `{account_id, method_id, amount_cents?}` (amount
optional = "everything available"; idempotency key mandatory),
`GET /v1/trader/payouts` (own, history + status), `GET /v1/trader/payouts/{id}`
(status + calc summary + receipt link when settled),
`DELETE /v1/trader/payouts/requests/{id}` (cancel pre-approval),
`GET|POST /v1/trader/payouts/methods`, `DELETE /v1/trader/payouts/methods/{id}` (PAY-05),
`POST /v1/trader/payouts/methods/{id}/default` (V2). (Paths normalized to the
GW-01 groups — D46, docs/54.)

Staff (ADM): `GET /v1/admin/payouts/queue?status=`,
`POST /v1/admin/payouts/{id}/approve` (2FA, note),
`POST /v1/admin/payouts/{id}/reject` (reason required),
`GET /v1/admin/payouts/{id}` (full detail: calc snapshot, executions, method
version, risk context), `POST /v1/admin/payouts/export` (PAY-44),
V2: batch approve, adjust amount, re-execute, SLA config.

Internal: provider webhook paths `/v1/webhooks/nowpayments` (shared with CHK via
EVT-10 adapter), `POST /internal/v1/payouts/{id}/execute` (worker trigger).
## 8. Schema (key shapes)

```jsonc
// GET /v1/payouts/eligibility?account_id=… (TD-26)
{ "data": { "eligible": true, "available_cents": 412000,
    "suggested_cents": 412000, "min_cents": 50000,
    "next_eligible_at": null, "method_count": 2,
    "checks": { "account": "pass", "kyc": "pass", "risk": "pass",
                "frequency": "pass" } } }

// POST /v1/payouts/requests → 201
{ "data": { "id": "01J9PAY...", "status": "pending_approval",
    "amount_cents": 412000, "fee_cents": 4120, "final_cents": 407880,
    "method": { "type": "crypto_trc20", "address_preview": "TQrY...9fXz" },
    "calc": { "hwm_cents": 10412000, "initial_cents": 10000000,
              "paid_cents": 0, "split_bps": 8000 } } }

// ADM detail (GET /v1/admin/payouts/{id})
{ "data": { ..., "calc_snapshot": { "steps": [
      { "step": "gross", "value_cents": 412000 },
      { "step": "trader_share", "value_cents": 329600, "note": "80% of 412000" },
      { "step": "cap", "value_cents": 329600 },
      { "step": "fee", "value_cents": 3296, "note": "NOWPayments 1%" },
      { "step": "final", "value_cents": 326304 } ] },
  "executions": [ { "attempt": 1, "state": "settled", "external_ref": "np_8842",
                     "at": 1758282000000 } ],
  "method_version": 2, "risk": { "open_cases": 0 } } }
```

## 9. Database design

```sql
CREATE TABLE payout_methods (                 -- versioned (edit = new row)
  id            ULID PRIMARY KEY,
  tenant_id     ULID NOT NULL,
  identity_id   ULID NOT NULL,                -- trader
  kind          TEXT NOT NULL,                -- crypto_trc20|crypto_erc20|crypto_bep20|local:{p}
  details_enc   JSONB NOT NULL,               -- AES-256-GCM (wallet/account ref)
  key_version   INT NOT NULL DEFAULT 1,
  label         TEXT,                         -- "Main TRON wallet"
  is_default    BOOLEAN NOT NULL DEFAULT false,
  active        BOOLEAN NOT NULL DEFAULT true,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  deactivated_at TIMESTAMPTZ
);
CREATE INDEX idx_pmeth_trader ON payout_methods(tenant_id, identity_id, active);

CREATE TABLE payout_requests (
  id                ULID PRIMARY KEY,
  tenant_id         ULID NOT NULL,
  identity_id       ULID NOT NULL,
  account_id        ULID NOT NULL REFERENCES accounts(id),
  method_id         ULID NOT NULL REFERENCES payout_methods(id),
  method_version_at INT NOT NULL,             -- which method row version (disputes)
  requested_cents   BIGINT,                   -- NULL = everything available
  status            TEXT NOT NULL DEFAULT 'requested'
    CHECK (status IN ('requested','eligibility_checked','pending_approval','approved',
                      'processing','paid','failed','cancelled','rejected')),
    -- PAY-13's exact list (docs/52: 'settled'→'paid'; 'failed_final' is a V2
    -- terminal reason within 'failed'; holds are status_reason='on_hold' flags on
    -- 'approved' — never states, D32)
  status_reason     TEXT,
  -- frozen calc (PAY-02, §3.2)
  calc_snapshot     JSONB NOT NULL,           -- steps + inputs + snapshot versions
  gross_cents       BIGINT NOT NULL,
  trader_share_cents BIGINT NOT NULL,
  fee_cents         BIGINT NOT NULL,
  final_cents       BIGINT NOT NULL,
  currency          CHAR(3) NOT NULL DEFAULT 'USD',
  rail              TEXT NOT NULL,            -- nowpayments|match2pay|interkasa|manual
  -- approval
  approval_required BOOLEAN NOT NULL DEFAULT true,   -- V1: always; V2 toggle
  approved_by       ULID, approved_at TIMESTAMPTZ, approval_note TEXT,
  rejected_by       ULID, rejected_at TIMESTAMPTZ, reject_reason_code TEXT,
  -- execution
  external_ref      TEXT,                     -- provider ref
  executed_at       TIMESTAMPTZ, settled_at TIMESTAMPTZ, failed_at TIMESTAMPTZ,
  attempts          INT NOT NULL DEFAULT 0,
  -- ledger
  obligation_entry_id ULID, settlement_entry_id ULID,
  idempotency_key   TEXT NOT NULL UNIQUE,
  cancelled_by      ULID, cancelled_at TIMESTAMPTZ,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_pay_tenant_status ON payout_requests(tenant_id, status, created_at DESC);
CREATE INDEX idx_pay_account ON payout_requests(tenant_id, account_id, status);
CREATE INDEX idx_pay_identity ON payout_requests(tenant_id, identity_id, created_at DESC);

CREATE TABLE payout_executions (               -- PAY-12 append-only record
  id            ULID PRIMARY KEY,
  payout_id     ULID NOT NULL REFERENCES payout_requests(id),
  tenant_id     ULID NOT NULL,
  attempt       INT NOT NULL,
  action        TEXT NOT NULL,                -- send|webhook|retry|reconcile
  provider      TEXT NOT NULL,
  external_ref  TEXT,
  state         TEXT NOT NULL,                -- sent|confirmed|failed
  provider_resp JSONB,                        -- redacted
  at            TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_pexec_payout ON payout_executions(payout_id, attempt);
-- status history: reuse the AUD pattern (payout.status_changed events mirror to
-- audit_events; a lightweight payout_status_history table is added only if the
-- AUD mirror proves insufficient for queue UX — V1: events + audit suffice)
```

## 10. Security & compliance

- **2FA on every approve/reject** (step-up, AUTH §3.1) + critical-tier audit;
  segregation of duties (PAY-31 V2: the person who created the trader's method
  can't approve their payout — V1: at least, approver ≠ requester, which is
  structural: traders can't approve).
- **Wallet strings are PII-adjacent:** field-encrypted, masked in all APIs
  (`TQrY…9fXz`), full value only in the execution worker (never logged);
  method changes versioned + cooldown-flagged (PAY-06) — the classic
  account-takeover payout fraud pattern is specifically guarded.
- **Ledger coupling:** approved payouts create the obligation (LED-07) *before*
  execution — the books show the liability even if the rail is down; settlement
  posts LED-08; a payout that settled without a ledger entry = integrity alert
  (nightly check).
- **Provider trust boundary:** NOWPayments webhooks verified (EVT-10), amounts
  from webhooks **never trusted over our own** (mismatch → exception, not
  auto-accept).
- **Reserves:** V1 = visibility only (CON dashboard + queue banner — D38);
  V2 PAY-37 enforces nightly + at approval (fast path: read LED balance) —
  the "we don't pay what the tenant hasn't collected" rule (FunderBlu parity
  with TTS).
- **PCI:** card-rail payouts (V2) keep card data provider-side (SAQ-A posture,
  AUD-26); V1 crypto/local rails store no card data at all.
- **Compliance evidence:** `calc_snapshot` + `payout_executions` + audit mirror
  = the full chain "profit X → split Y → fee Z → sent to address A at time T →
  provider ref R" (MIG cutover uses this for the first reconciliation week).

## 11. Scalability considerations

- Volume: ~50 payouts/day V1 → approvals are the bottleneck (human), not
  compute; queue UX (filtering, export) matters more than throughput.
- Eligibility check is a fan-out read (LCC state, KYC status, RSK hold,
  history SUM) — all indexed; < 20 ms p95; cached briefly in Redis
  (30 s, invalidated by the four domains' events).
- Execution: provider-bound (NOWPayments latency); worker concurrency 5 per
  rail; queue with age alerting (> 1 h unexecuted approved = WARN).
- `payout_requests` growth: ~20k rows/tenant/year — trivial; partitions only
  if > 10M platform-wide.
- Reconciliation (V2): provider CSV import O(settled that day) — seconds.
- **Money safety over speed:** the staleness guard (`pay.stale_data`) and the
  pre-execution fresh read (PAY-29 V2) intentionally make payouts *slower*;
  that is the correct trade.

## 12. Open-source solutions

| Option | Verdict |
|---|---|
| **NOWPayments** (crypto rail, register) | **CHOSEN V1** — TRC20/ERC20/BEP20, withdrawal API, webhooks, ~1% |
| **Match2Pay / Interkasa** (local rails, register) | V1 local disbursement where supported |
| Hyperswitch (open-source payments router) | Rejected V1: it solves *inbound* orchestration breadth; our rails are 3 providers with thin needs — adapter interface (strategy pattern) covers it; revisit at > 8 rails |
| Fireblocks/Circle (crypto custody, research list) | Not in V1 scope: we pay out from the tenant's provider balance, we are not a custodian |
| Temporal (approval workflows, research) | V2 upgrade path (PAY-10/19/46 complexity); V1 = state machine + worker |
| Redlock / Redis fencing (research §10) | **Rejected** — PG advisory lock + status CAS are transactional with the guarded state (§3.7); revisit if executors span PGs |
| TigerBeetle (research ledger option) | Not PAY's call — verdict lives in 05 §12 (PG journal V1, TigerBeetle V2+ path) |
| Wise/Rise/Airwallex (research list) | V2 candidates for local rails (register: consider) |

## 13. Technology stack

Go domain package (api) + payout-executor worker; NOWPayments/Match2Pay/
Interkasa REST (EVT-10 webhook adapters); Postgres (requests/methods/
executions); LED (obligation/settlement); PG advisory locks (execution mutex, §3.7);
Redis (eligibility cache, circuit state); R2 (receipt PDFs via DOC); Postmark (via NOT); Prometheus (queue age,
rail circuit, settlement rate); Sentry.

## 14. Integration — internal modules (glue)

| Module | How |
|---|---|
| **LCC** | `funded` state + funded terms (split, frequency, min, first delay) = the eligibility input; `account.breached` freezes in-flight processing (approved-but-unexecuted → on-hold queue, human decision) |
| **KYC** | payout-level gate (KYC-08); name-match (V2 PAY-07) reads KYC verified name |
| **RSK** | open case → `payout.risk_hold`; hold release re-triggers eligibility |
| **LED** | `ledger.Post` obligation on approve (LED-07), settlement on settled (LED-08), fee lines (LED-06 V2); reserves check reads `cash` balance |
| **CHK** | shares the provider-webhook ingress (EVT-10) and the method-encryption pattern; refunds are CHK's (not PAY's) |
| **NOT** | templates: requested, rejected (reason class), approved, settled (+ receipt link), failed_final |
| **DOC** | receipt PDF on settled (branded, tenant white-label) |
| **ANA** | payout volume/SLA/pass-rate KPIs; payout-vs-revenue unit economics |
| **MIG** | cutover: FunderBlu's in-flight TTS payouts are **imported as settled
  history** (method versions seeded) so "paid_out" math is correct from day 1 |
| **TD** | eligibility preview (TD-26), request UI, payout section (TD-10) |

## 15. Integration — external tools

NOWPayments (V1 crypto: withdrawals + webhooks), Match2Pay/Interkasa (local
disbursement where supported), (V2) Wise/Airwallex/Rise, R2 (receipts),
Postmark (via NOT), Sentry, Prometheus/Grafana.

## 16. Implementation blueprint

| Step | Owner | Est | Depends | Exit criteria |
|---|---|---|---|---|
| 1. Schemas (methods versioned, requests, executions) + encryption + address validators | BE-2 | 2 d | OPS, AUTH, LCC | property: 5k random addresses → correct accept/reject per chain |
| 2. Profit calculator (pure) + calc_snapshot + property tests (HWM, split, fee, floor) | BE-2 | 2 d | 1, EVL-29 | recompute-from-snapshot test: stored steps == recomputed |
| 3. Eligibility service (5 checks) + preview endpoint | BE-2 | 2 d | 2, KYC, RSK-10, LED | each fail code triggerable in staging |
| 4. Request lifecycle: create → pending_approval → ADM queue → approve/reject (2FA) | BE-2 + FE-1 | 4 d | 3, AUTH step-up | end-to-end in staging: request appears in queue, approve posts LED obligation |
| 5. Manual execution path: provider dashboard procedure (COO) + ADM record + `PayoutPaid` (outbox) + LED-08 settlement + receipt | BE-2 | 4 d | 4, LED-08 | settled payout posts LED-08 exactly once; duplicate record = idempotent no-op (the V2 rail adapter + executor + webhooks are PAY-24, step 10) |
| 6. Method management (TD UI) + versioning + cooldown flag + default | FE-01 + BE-2 | 3 d | 1 | edit wallet → new version visible in next request's snapshot |
| 7. Receipt (DOC) + notifications + batch export (PAY-44) + staleness guard | BE-2 | 2 d | 5 | settled payout → branded PDF + email; stale tick → `pay.stale_data` |
| 8. Reserves visibility: CON dashboard (`cash` vs open obligations) + ADM queue banner (V1 — D38; the PAY-37 hard block stays V2) | BE-2 | 1 d | 4, LED | dashboard shows a shortfall injected on a synthetic tenant |
| 9. MIG import: FunderBlu settled-history seeding + first-week reconciliation plan | BE-2 | 2 d | 4, MIG | dry run: "paid_out" per account matches TTS export |
| 10. V2: second approval, batch, auto-approve rules, instant option, multi-network, test transfers, name match, SLA, adjustment workflow, reconciliation jobs, fee recon | BE-2 + FE-1 | 3 wks | 8–9 | each behind Flipt flag per tenant |

**Risks:** NOWPayments as single crypto rail (mitigation: adapter interface,
Match2Pay backup path, manual-execution escape hatch in ADM); calc disputes
(mitigation: frozen snapshots + recompute proof in the detail view — get
FunderBlu Risk Owner to sign the §3.2 formula in Phase 1); address typos
(mitigation: format+checksum validation V1, test transfer V2); stolen-account
payout fraud (mitigation: method versioning + cooldown flag + 2FA approvals +
risk-hold block).

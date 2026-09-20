# Ledger & Accounting Contract (LED)

Status: DRAFT
Owner: TBD
Version: v1
Last updated: 2026-09-17

Derived from the V1 Execution Sheet (V1.0 only). Nothing here is final until contract freeze.

## No HTTP surface in V1
LED is a domain service with no trader/admin endpoints in the V1 sheet: fixed chart of accounts (LED-01), double-entry journal model (LED-02), idempotent posting (LED-03), payment capture posting (LED-04), payout obligation posting (LED-07), payout settlement posting (LED-08), immutability enforcement (LED-18). This module has no HTTP contract in V1 — see module spec later.

## What it provides instead (internal contracts)

### Chart of accounts (LED-01)
Fixed V1 chart per tenant covering: customer payments, provider settlement, refunds, fees, payout obligations, payouts paid, adjustments. USD only (Out Of Scope: no multi-currency; capture-time rate stored as metadata when relevant).

### Journal model (LED-02, LED-18)
Every money event is a balanced set of immutable journal entries carrying a source event id. No update or delete path in the application; corrections only through reversing adjustments (Out Of Scope).

### Idempotent posting (LED-03)
Postings deduplicate by source event id so event replay never double-posts money (per EVT-05 at-least-once semantics).

### Postings (LED-04, LED-07, LED-08)
- On payment captured (order.paid from CHK-09): customer payment credit + settlement receivable (LED-04).
- On payout approval (payout.approved from PAY-09): payout obligation (LED-07).
- On recorded payout execution (PAY-12): settle the obligation (LED-08).

## Delivery mechanism (resolved 2026-09-17)
Event consumption. No synchronous calls. **LED-04 consumes `order.paid`. LED-07 consumes `payout.approved`. LED-08 consumes `PayoutPaid`.** All postings are event-driven per LED-02/LED-03: journal entries carry a `source_event_id` and deduplicate by it, so event replay never double-posts money (EVT-05 at-least-once semantics). A ledger posting is a reaction to a fact, not a request — a synchronous CHK/PAY → LED call path would violate EVT-20's separation of commands (requests) from events (facts).

## Events consumed
- order.paid (CHK-09) — LED-04 posts customer payment credit + settlement receivable on payment captured. Posting is event-driven per LED-02/LED-03 (entries carry a source event id and dedupe by it "so that event replay never double-posts money").
- payout.approved — LED-07 posts the payout obligation on payout approval (LED-07: "on payout approval I post a payout obligation").
- PayoutPaid (producer PAY-12, resolved 2026-09-16 (Decision 6)) — LED-08 settles the obligation on recorded payout execution (LED-08; Depends On: PAY-12).

## Events emitted
- None named in the sheet.

## Open contract questions
- Resolved 2026-09-17: ledger delivery mechanism — event consumption (LED-04 ← order.paid, LED-07 ← payout.approved, LED-08 ← PayoutPaid); no synchronous calls. Remaining sub-items: account codes, refund/fee/adjustment posting triggers, balance read path for analytics.
- Resolved 2026-09-20 (docs/62): the account codes are the docs/05 §5 chart slugs (`tenant:payout_liability`, `tenant:payout_paid`, `platform:revenue`, …) — the slug IS the code; the chart is seeded by the provisioning saga step 6b (D26, docs/48).
- Resolved 2026-09-20 (docs/62): the refund account is used by **D40's minimal manual refund** (V1-Plus form, docs/53): a staff-approved refund posts the reversal pair against the original order lines; chargebacks stay record-only (Out Of Scope).
- Resolved 2026-09-20 (docs/62): provider fees post with the settlement line — the LED-08 payout settlement carries the `fee_charged` line when the provider reports a fee (docs/05 §3.3); no standalone fee-capture trigger in V1.
- Resolved 2026-09-20 (docs/62): **no manual adjustment surface in V1** — reversals post only through the owning flows (D40 refunds, the payout-failed path); the `adjustment` kind exists for worker-level corrections (provider settlement fixes); staff-facing adjustment tooling is V2 (LED-10/23 class, docs/05 §3.4).
- Resolved 2026-09-20 (docs/62): balances read from the LED `balances` projection (docs/05 §3.4 — the 5-min refresh + on-demand), tenant-scoped and read-only for ANA/ADM reads; ANA-01 dashboards render from it plus the event-fed read models (docs/19 §3.1).
- Resolved 2026-09-20 (docs/62): the V1 ledger export rides the **audit-export path** (`audit.export`, CON-13 — critical-audited CSV, docs/21 §3.3); the self-serve ANA CSV suite is V2 (ANA-11, docs/19 §2).

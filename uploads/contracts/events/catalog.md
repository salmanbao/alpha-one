# Event Catalog

Status: DRAFT
Owner: TBD
Version: v1
Last updated: 2026-09-17

Derived from the `V1 Execution Sheet` (releases V1.0 and V1.1 only) of `Alpha One PRD.xlsx`.
Every event uses the EVT-03 envelope: `id`, `type`, `version`, `tenant_id`, `occurred_at`, `payload`.
Delivery is at-least-once with idempotent consumers (EVT-05). Payload field values are TODO until owners fill them in.

## Lifecycle events — producer: LCC (LCC-23, emitted through the outbox per EVT-01)

| Event | Version | Producer | Consumers | Payload |
|---|---|---|---|---|
| AccountCreated | v1 | LCC-23 | NOT-01 (NOT-05 template: account created), ANA-01 | `payloads/AccountCreated.v1.json` |
| PhaseAdvanced | v1 | LCC-23 | ANA-01 | `payloads/PhaseAdvanced.v1.json` |
| AccountPassed | v1 | LCC-23 | NOT-01 (NOT-05 template: phase passed), DOC-04 (certificate), ANA-01 | `payloads/AccountPassed.v1.json` |
| AccountBreached | v1 | LCC-23 | NOT-01 (NOT-05 template: breach), ANA-01 | `payloads/AccountBreached.v1.json` |
| AccountFailed | v1 | LCC-23 | NOT-01 (NOT-05 template: phase failed), ANA-01 | `payloads/AccountFailed.v1.json` |
| FundedCreated | v1 | LCC-23 | DOC-04 (certificate), ANA-01; NOT-01 — TODO — needs owner decision (citation not directly supported by sheet: no funded-account template in NOT-05) | `payloads/FundedCreated.v1.json` |
| Suspended | v1 | LCC-23 | PAY-04 (holds payouts on active suspension — mechanism, event vs status check, TODO — needs owner decision), ANA-01 | `payloads/Suspended.v1.json` |
| Resumed | v1 | LCC-23 | ANA-01 | `payloads/Resumed.v1.json` |

## Checkout events

| Event | Version | Producer | Consumers | Payload |
|---|---|---|---|---|
| order.paid | v1 | CHK-09 (payment captured, via CHK-07 webhook + CHK-08 order creation) | LCC-05 (provisioning on purchase), LED-04 (payment capture posting), ANA-01 | `payloads/order.paid.v1.json` |
| checkout.session.expired | v1 | CHK-43 (scheduled expiry worker, via outbox per EVT-01) — resolved 2026-09-16 (Decision 7) | ANA-01 (funnel/abandonment read model) | `payloads/checkout.session.expired.v1.json` |

## KYC events — producer: KYC (KYC-05 amended by Decision 5; KYC-16 in V1.0 / V1-Core)

Resolved 2026-09-16 (Decision 5): KYC-05 emits these five events through the outbox; KYC-16 moved from V2.0 to V1.0 / V1-Core. These are V1 scope.

| Event | Version | Producer | Consumers | Payload |
|---|---|---|---|---|
| kyc.submitted | v1 | KYC-05 (webhook status handling, via outbox per EVT-01), KYC-16 | NOT-01 (NOT-05 template: KYC result), ANA-01 — consumer link per KYC-16's story ("so that lifecycle auto-upgrade and payout eligibility react without coupling"; LCC-07 / KYC-07 / KYC-08 gates remain synchronous status checks, not event consumption) | `payloads/kyc.submitted.v1.json` |
| kyc.approved | v1 | KYC-05 (webhook status handling, via outbox per EVT-01), KYC-16 | NOT-01 (NOT-05 template: KYC result), LCC-06 (auto-upgrade on approval), PAY-03 (payout eligibility reacts without coupling), ANA-01 | `payloads/kyc.approved.v1.json` |
| kyc.rejected | v1 | KYC-05 (webhook status handling, via outbox per EVT-01), KYC-16 | NOT-01 (NOT-05 template: KYC result), ANA-01 | `payloads/kyc.rejected.v1.json` |
| kyc.expired | v1 | KYC-05 (webhook status handling, via outbox per EVT-01), KYC-16 | NOT-01 (NOT-05 template: KYC result), ANA-01 — EXPIRED trigger itself is still TODO — needs owner decision | `payloads/kyc.expired.v1.json` |
| kyc.resubmission_requested | v1 | KYC-05 (webhook status handling, via outbox per EVT-01), KYC-16 | NOT-01 (NOT-05 template: KYC result), ANA-01 | `payloads/kyc.resubmission_requested.v1.json` |

Note: the "KYC result" NOT-05 template's per-event mapping (which of the five events fires it) is TODO — needs owner decision.

## Payout events

| Event | Version | Producer | Consumers | Payload |
|---|---|---|---|---|
| payout.approved | v1 | PAY-09 | LED-07 (payout obligation posting), NOT-01 (NOT-05 template: payout approved), ANA-01 | `payloads/payout.approved.v1.json` |
| payout.rejected | v1 | PAY-09 | NOT-01 (NOT-05 template: payout rejected), ANA-01 | `payloads/payout.rejected.v1.json` |
| PayoutPaid | v1 | PAY-12 (execution recording, via outbox per EVT-01) — resolved 2026-09-16 (Decision 6) | LED-08 (settlement posting), DOC-04 (certificate), ANA-01 | `payloads/PayoutPaid.v1.json` |

## Notes

- `checkout started / abandoned / completed` events (CHK-24 in earlier drafts) are NOT in the V1 Execution Sheet and are excluded from V1 scope. If the working session wants abandoned-cart analytics, that is a scope change.
- EVT-20: broker commands are NOT events. They live in the `command_queue` and must never appear in this catalog.
- Producers write to the outbox (EVT-01); the relay (EVT-02) publishes to Redis Streams; consumers deduplicate by event id (EVT-05); every published event is appended to the event log (EVT-08).
- Decisions 5, 6, and 7 were applied to the PRD on 2026-09-16 19:06:13 UTC (PRD Change Log `APPLY_DECISION_*` entries); this catalog was aligned in the same change.

## Open contract questions

- TODO — needs owner decision: payload schemas (field names/types) for every event above; the sheet defines only the envelope (EVT-03).
- TODO — needs owner decision: NOT-01's delivery mechanism for the "payout approved" / "payout rejected" templates — NOT-01 requires event consumption, but no V1 row ties the templates to payout.approved / payout.rejected; alternative is direct template triggering from PAY-09.
- TODO — needs owner decision: is `PhaseAdvanced` consumed by NOT-01 (a "phase advanced" email is not in the NOT-05 template list)?
- TODO — needs owner decision: event versioning policy — the catalog pins v1; confirm bump rules after contract freeze.

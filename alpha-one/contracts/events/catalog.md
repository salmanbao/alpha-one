# Event Catalog

Status: DRAFT
Owner: TBD
Version: v1
Last updated: 2026-09-17

Derived from the `V1 Execution Sheet` (releases V1.0 and V1.1 only) of `Alpha One PRD.xlsx`.
Every event uses the EVT-03 envelope: `id`, `type`, `version`, `tenant_id`, `occurred_at`, `correlation_id`, `payload` (correlation_id required since the ninth pass — docs/49 C1; it is GW step 8's propagation promise made contractual).
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

## Identity events — producer: AUTH (ADR-13 model; V1 baseline)

V1 identity events, payloads in `payloads/`. Login/session rows originate in ZITADEL and
are ingested through the Actions v2 event trigger (docs/02 §3.1); if a trigger is not
available in the pinned version, the row is derived locally at session materialisation
with the same field set. `email_hash` carries `sha256(normalised email)` — event
payloads never carry the address itself.

| Event | Version | Producer | Consumers | Payload |
|---|---|---|---|---|
| user.registered | v1 | AUTH (AUTH-01) | NOT-01 (welcome), AUD, ANA-01 | `payloads/user.registered.v1.json` |
| user.login_success | v1 | AUTH / ZITADEL | AUD, ANA-01, RSK (anomaly baseline) | `payloads/user.login_success.v1.json` |
| user.login_failure | v1 | ZITADEL (Actions v2) | AUD, RSK (anomaly scoring), NOT (security notice on threshold) | `payloads/user.login_failure.v1.json` |
| user.suspended | v1 | AUTH (AUTH-20) / idp-sync (IdP-driven, docs/43) | NOT-01, GW (session kill), AUD | `payloads/user.suspended.v1.json` |
| user.activated | v1 | AUTH (AUTH-43) / idp-sync | NOT-01, AUD | `payloads/user.activated.v1.json` |
| user.session_revoked | v1 | AUTH (AUTH-39 logout, AUTH-20 suspension; AUTH-27 admin in V2) | AUD | `payloads/user.session_revoked.v1.json` |
| user.password_changed | v1 | AUTH (AUTH-05, AUTH-40) | session invalidator, AUD | `payloads/user.password_changed.v1.json` |

## Tenant events — producer: TEN (V1 baseline)

| Event | Version | Producer | Consumers | Payload |
|---|---|---|---|---|
| tenant.created | v1 | TEN-01 | AUD, CON-01, NOT-01 (owner) | `payloads/tenant.created.v1.json` |
| tenant.provisioning_step_completed | v1 | TEN (saga step; `status=failed` on the failure branch) | CON-01 (live view), NOT (staff) | `payloads/tenant.provisioning_step_completed.v1.json` |
| tenant.activated | v1 | TEN (checklist complete) | GW (allow traffic), NOT-01, AUD, ANA-01 | `payloads/tenant.activated.v1.json` |
| tenant.suspended | v1 | TEN-15 | AUTH (kill sessions), GW (deny), NOT-01, AUD — all within 1 s | `payloads/tenant.suspended.v1.json` |
| tenant.reactivated | v1 | TEN-15 | GW, NOT-01, AUD, AUTH | `payloads/tenant.reactivated.v1.json` |
| tenant.member_invited | v1 | AUTH-03 (V1 for the SSO cutover tenant, decision P3) | NOT-01 (invite email), CON-01 | `payloads/tenant.member_invited.v1.json` |

Note: the extended (post-V1) identity/tenant topics (`user.role_changed`, `user.2fa_enrolled`,
`api_key.*`, `identity.*`, `tenant.settings_changed`, `tenant.limit_exceeded`, …) stay in
docs/31 §2 with the rest of the extended catalog.

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

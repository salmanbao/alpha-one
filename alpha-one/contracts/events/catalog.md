# Event Catalog

Status: DRAFT
Owner: TBD
Version: v1
Last updated: 2026-09-20

Derived from the `V1 Execution Sheet` (releases V1.0 and V1.1 only) of `Alpha One PRD.xlsx`.
Every event uses the EVT-03 envelope: `id`, `type`, `version`, `tenant_id`, `occurred_at`, `correlation_id`, `payload` (correlation_id required since the ninth pass — docs/49 C1; it is GW step 8's propagation promise made contractual).
Delivery is at-least-once with idempotent consumers (EVT-05). Every event's payload schema (field names/types) is a JSON Schema in `payloads/` — the sheet defines only the envelope (EVT-03), and the per-event payloads were pinned in the gap-closure pass of 2026-09-20, each derived from the owning module doc and the docs/32 DDL (source section cited in each schema's `description`); `scripts/check_event_payloads.py` fails the build if any catalog event lacks its schema.

## Lifecycle events — producer: LCC (LCC-23, emitted through the outbox per EVT-01)

| Event | Version | Producer | Consumers | Payload |
|---|---|---|---|---|
| AccountCreated | v1 | LCC-23 | NOT-01 (NOT-05 template: account created), ANA-01 | `payloads/AccountCreated.v1.json` |
| PhaseAdvanced | v1 | LCC-23 | ANA-01 only — NOT-01 does NOT consume it (resolved 2026-09-20: the V1 template set (D61, docs/14 §3.4) has no "phase advanced" template; the trader-facing phase-completion email is `phase_passed` ← `AccountPassed`. `PhaseAdvanced` is the internal progression signal for the read models) | `payloads/PhaseAdvanced.v1.json` |
| AccountPassed | v1 | LCC-23 | NOT-01 (NOT-05 template: phase passed), DOC-04 (certificate), ANA-01 | `payloads/AccountPassed.v1.json` |
| AccountBreached | v1 | LCC-23 | NOT-01 (NOT-05 template: breach), ANA-01 | `payloads/AccountBreached.v1.json` |
| AccountFailed | v1 | LCC-23 | NOT-01 (NOT-05 template: phase failed), ANA-01 | `payloads/AccountFailed.v1.json` |
| FundedCreated | v1 | LCC-23 | DOC-04 (certificate), ANA-01 — NOT-01 does NOT consume it (resolved 2026-09-20: the closed V1 template set (D61, docs/14 §3.4) deliberately carries no funded-account template — funding is confirmed by the DOC-04 certificate + the TD funded view; adding a funded email is a scope change to the closed D61 set, docs/14 §3.4) | `payloads/FundedCreated.v1.json` |
| Suspended | v1 | LCC-23 | PAY-04 (payout hold while suspension is active — resolved 2026-09-20: **status check, not event consumption**: PAY-03/PAY-04 read `accounts.state == SUSPENDED` synchronously at request and approval time (docs/11 §3.1/§3.7, D39); the event informs ANA only — a suspended account whose event is delayed must still be blocked the moment the state is read), ANA-01 — NOT-01 does NOT consume it (resolved 2026-09-20: no suspension template in the closed D61 set; the trader sees the state in TD and at the payout gate, the D63 "silent" pattern, docs/14 §3.4) | `payloads/Suspended.v1.json` |
| Resumed | v1 | LCC-23 | ANA-01 | `payloads/Resumed.v1.json` |
| account.activated | v1 | LCC (CREATED → ACTIVE on broker.created) — tenth pass D28 (docs/50) | BRG (start sync), EVL (start evaluation + create evaluation_state), NOT-01, AUD | `payloads/account.activated.v1.json` |
| account.day_rolled | v1 | LCC (rollover job at broker-server midnight, ADR-12; skips SUSPENDED — D31) | EVL (daily reset), ANA | `payloads/account.day_rolled.v1.json` |

## Evaluation & bridge events — producers: EVL / BRG (V1 — tenth pass, docs/50 D28)

The V1.0 core loop (docs/99 Phase 1: LCC → BRG → EVL) could not be wired from
the sheet without these: EVL-17's breach path consumes `evaluation.verdict`,
EVL-05's trigger is `bridge.tick`, and the daily reset rides `account.day_rolled`.
`bridge.tick` is the **observed** record (EVL-49) and does NOT mirror to
`audit_events` (docs/05 §14); the evaluated/decision events do.

| Event | Version | Producer | Consumers | Payload |
|---|---|---|---|---|
| evaluation.verdict | v1 | EVL (every non-ok verdict; EVL-17) | LCC (transitions; dedupe on (account_id, verdict_id) per LCC-43), NOT-01, DOC-04 (TD-25 breach report), AUD (critical on breach), RSK (V2 case open) | `payloads/evaluation.verdict.v1.json` |
| evaluation.daily_reset | v1 | EVL (rollover) | ANA (daily P&L points), AUD (standard) | `payloads/evaluation.daily_reset.v1.json` |
| bridge.tick | v1 | BRG (streaming conflator, per account, event-driven: deal/position/guard/material/resync + heartbeat ≤ 60 s open / ≤ 300 s flat; fallback poll 60 s — D78/D79, docs/63 §4.4) | EVL (evaluate), ANA (equity points); observed record per EVL-49 — no audit mirror (docs/05 §14) | `payloads/bridge.tick.v1.json` |
| bridge.sync_gap | v1 | BRG (history-window count mismatch — D33, docs/51) | ADM (manual review), AUD, EVL (gap_flagged verdict) | `payloads/bridge.sync_gap.v1.json` |

## Checkout events

| Event | Version | Producer | Consumers | Payload |
|---|---|---|---|---|
| order.paid | v1 | CHK-09 (payment captured, via CHK-07 webhook + CHK-08 order creation) | LCC-05 (provisioning on purchase), LED-04 (payment capture posting), ANA-01 | `payloads/order.paid.v1.json` |
| checkout.session.expired | v1 | CHK-43 (scheduled expiry worker, via outbox per EVT-01) — resolved 2026-09-16 (Decision 7) | ANA-01 (funnel/abandonment read model) | `payloads/checkout.session.expired.v1.json` |

## KYC events — producer: KYC (KYC-05 amended by Decision 5; KYC-16 in V1.0 / V1-Core)

Resolved 2026-09-16 (Decision 5): KYC-05 emits these five events through the outbox; KYC-16 moved from V2.0 to V1.0 / V1-Core. These are V1 scope.

| Event | Version | Producer | Consumers | Payload |
|---|---|---|---|---|
| kyc.submitted | v1 | KYC-05 (webhook status handling, via outbox per EVT-01), KYC-16 | ANA-01 (no V1 email — D61: `kyc.submitted` is the pre-decision record; the trader just submitted, there is nothing to tell them) — consumer link per KYC-16's story ("so that lifecycle auto-upgrade and payout eligibility react without coupling"; LCC-07 / KYC-07 / KYC-08 gates remain synchronous status checks, not event consumption) | `payloads/kyc.submitted.v1.json` |
| kyc.approved | v1 | KYC-05 (webhook status handling, via outbox per EVT-01), KYC-16 | NOT-01 (NOT-05 template: `kyc_approved` — D61 split), LCC-06 (auto-upgrade on approval), PAY-03 (payout eligibility reacts without coupling), ANA-01 | `payloads/kyc.approved.v1.json` |
| kyc.rejected | v1 | KYC-05 (webhook status handling, via outbox per EVT-01), KYC-16 | NOT-01 (NOT-05 template: `kyc_rejected` — D61 split), ANA-01 | `payloads/kyc.rejected.v1.json` |
| kyc.expired | v1 | KYC-05 (webhook status handling, via outbox per EVT-01), KYC-16 + the session-TTL worker (D43, docs/53: 24 h session expiry) | ANA-01 (no V1 email — D63: expiry is silent in V1; the portal shows the status and the payout gate's `kyc.required` redirect is the signal) — trigger resolved 2026-09-19 (D43: session TTL only; APPROVED never expires in V1) | `payloads/kyc.expired.v1.json` |
| kyc.resubmission_requested | v1 | KYC-05 (webhook status handling, via outbox per EVT-01), KYC-16 | NOT-01 (NOT-05 template: `kyc_needs_docs` — D61 split), ANA-01 | `payloads/kyc.resubmission_requested.v1.json` |

Note: the "KYC result" NOT-05 template's per-event mapping is **resolved (D61, docs/58)** — the single "KYC result" template was split per event: `kyc_approved` ← `kyc.approved`, `kyc_rejected` ← `kyc.rejected`, `kyc_needs_docs` ← `kyc.resubmission_requested`; `kyc.submitted` fires no V1 email (pre-decision) and `kyc.expired` is silent in V1 (D63). docs/14 §3.4 is the binding list.

## Payout events

| Event | Version | Producer | Consumers | Payload |
|---|---|---|---|---|
| payout.approved | v1 | PAY-09 | LED-07 (payout obligation posting), NOT-01 (NOT-05 template: `payout_approved` — D61: fired by event consumption through the docs/14 §3.3 mapping table, not by a direct call from PAY-09), ANA-01 | `payloads/payout.approved.v1.json` |
| payout.rejected | v1 | PAY-09 | NOT-01 (NOT-05 template: `payout_rejected` — D61, same mechanism), ANA-01 | `payloads/payout.rejected.v1.json` |
| payout.settled | v1 | PAY-12 (execution recording, via outbox per EVT-01) — resolved 2026-09-16 (Decision 6; renamed from the sheet's `PayoutPaid` by D60, docs/58) | LED-08 (settlement posting), DOC-04 (receipt), ANA-01 | `payloads/payout.settled.v1.json` |

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

**All resolved (gap-closure pass, 2026-09-20):**

- ~~Payload schemas (field names/types) for every event~~ — **Done:** all 37 V1 events have a JSON Schema in `payloads/` (one file per event, plus `envelope.schema.json`), each derived from the owning module doc + the docs/32 DDL (source cited in the schema's `description`; money = integer minor units per docs/00 #3). Enforced by `scripts/check_event_payloads.py` (fails if a catalog event has no schema file or its `type` const mismatches).
- ~~NOT-01's delivery mechanism for the "payout approved" / "payout rejected" templates~~ — **Resolved by citation (D61, docs/58; docs/14 §3.3/§3.4):** NOT-01 fires templates by **event consumption** through the event→template mapping table (docs/14 §3.3, data not code); the binding rows `payout_approved` ← `payout.approved` and `payout_rejected` ← `payout.rejected` exist in the closed V1 set (docs/14 §3.4). No direct triggering from PAY-09 — the producer emits the event, NOT maps it.
- ~~Is `PhaseAdvanced` consumed by NOT-01?~~ — **No, deliberately:** the closed V1 template set (D61) contains no "phase advanced" template; the trader-facing phase-completion email is `phase_passed` ← `AccountPassed` (docs/14 §3.4). `PhaseAdvanced` stays ANA-only.
- ~~Event versioning policy~~ — **Resolved by citation (docs/01 §4.2, ADR-7):** `version` is the schema version of `payload`; bump on any payload change, additive-only between freezes; consumers must handle `version < max` they know about; an unknown higher version → DLQ + alert. The catalog pins v1 for every V1 event; the first payload change to any event becomes v2 under those rules at the contract-freeze session (docs/99 §12).

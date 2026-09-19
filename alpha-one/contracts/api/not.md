# Notification API Contract (NOT)

Status: DRAFT
Owner: TBD
Version: v1
Last updated: TODO

Derived from the V1 Execution Sheet (V1.0 only). Nothing here is final until contract freeze.

## No HTTP surface in V1
NOT is an event-driven worker: it consumes domain events from the outbox relay (NOT-01), sends email through a swappable provider adapter (NOT-03 — Postmark production; BVR-01: no SMTP server built), renders 10 core transactional templates (NOT-05), and deduplicates by event id and channel (NOT-13, per EVT-05). The V1 sheet defines no notification management or preference endpoints. This module has no HTTP contract in V1 — see module spec later.

## The 10 core templates (NOT-05)
1. account created (consumes AccountCreated)
2. phase passed (consumes AccountPassed)
3. phase failed (consumes AccountFailed)
4. breach (consumes AccountBreached)
5. KYC invite — triggering req — TODO — needs owner decision (no V1 row names what emits a KYC invite)
6. KYC result — consumes the kyc.* events (KYC-05 emits; Decision 5 moved KYC-16 into V1.0 / V1-Core) — per-event mapping for this template — TODO — needs owner decision (which of the five events fires it)
7. payout requested (consumes payout request; producer req — TODO — needs owner decision: is a payout.requested event emitted? Not named in the sheet)
8. payout approved (consumes payout.approved)
9. payout rejected (consumes payout.rejected)
10. certificate issued (consumes certificate issuance — DOC flow; producer req — TODO — needs owner decision)

Template content and branding — TODO — needs owner decision (English only in V1 per Out Of Scope).

## Events consumed
AccountCreated, AccountPassed, AccountFailed, AccountBreached, payout.approved, payout.rejected, kyc.submitted, kyc.approved, kyc.rejected, kyc.expired, kyc.resubmission_requested — see `contracts/events/catalog.md`. The kyc.* events are V1 scope as of Decision 5 (2026-09-16): KYC-05 emits them via the outbox; the per-event mapping to the "KYC result" template is still a working-session item. Plus template-specific triggers listed above with TODOs.

## Events emitted
- None.

## Open contract questions
- TODO — needs owner decision: what emits the KYC invite (template 5) in V1.
- TODO — needs owner decision: which of the five kyc.* events fires the "KYC result" template (NOT-05 names one template; the sheet does not map events to it).
- TODO — needs owner decision: whether a payout.requested event exists (template 7 needs a trigger; no event row in the sheet).
- TODO — needs owner decision: notification suppression/unsubscribe rules for transactional email (no V1 row; compliance expectation open).
- TODO — needs owner decision: failed-send retry policy and channel dedupe window (NOT-13 says dedupe by event id and channel; window unspecified).

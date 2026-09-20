# Notification API Contract (NOT)

Status: DRAFT
Owner: TBD
Version: v1
Last updated: 2026-09-20

Derived from the V1 Execution Sheet (V1.0 only). Nothing here is final until contract freeze.

## No HTTP surface in V1
NOT is an event-driven worker: it consumes domain events from the outbox relay (NOT-01), sends email through a swappable provider adapter (NOT-03 — Postmark production; BVR-01: no SMTP server built), renders the 14 V1 templates (NOT-05 — D61, docs/58), and deduplicates by the docs/14 §3.5 key (24 h window, NOT-13). The V1 sheet defines no notification management or preference endpoints. This module has no HTTP contract in V1 — see module spec later.

## The V1 template set (NOT-05 — D61, docs/58)

Fourteen templates, every one mapped to a registered V1 event (docs/31).
The authoritative table with contents: docs/14 §3.4.

Trader (11): `account_created` ← AccountCreated · `phase_passed` ←
AccountPassed · `phase_failed` ← AccountFailed · `breach` ← AccountBreached ·
`kyc_approved` ← kyc.approved · `kyc_rejected` ← kyc.rejected ·
`kyc_needs_docs` ← kyc.resubmission_requested · `payout_approved` ←
payout.approved · `payout_rejected` ← payout.rejected · `payout_settled` ←
payout.settled (D60) · `payment_captured` ← order.paid.

Staff (3): `payout_approved_by_other` ← payout.approved (recipient = the
requesting staff member) · `payout_settled_staff` ← payout.settled (finance
copy) · `worker_dlq` ← the DLQ-depth ops alert path (not a domain event).

Owner rulings: **no KYC invite email in V1** (D62, docs/58 — the session
opens inside the purchase flow; `kyc.session_started` stays an internal ext
event) and **expiry is silent in V1** (D63 — the portal status and the
payout gate's `kyc.required` error are the signals). V2 reserves (trigger
named, not shipped dead): docs/14 §3.4.

Template content and branding — resolved 2026-09-20: English only in V1 per
Out Of Scope; the renderer is i18n-ready so V2 ur/hi are content-only
(docs/14 §3.4).

## Events consumed
AccountCreated, AccountPassed, AccountFailed, AccountBreached (LCC-23) ·
payout.approved, payout.rejected, payout.settled (PAY — D60) · kyc.approved,
kyc.rejected, kyc.resubmission_requested (KYC-05/16 — the KYC-result split
per docs/14 §3.4; kyc.submitted and kyc.expired fire no email in V1, D63) ·
order.paid (CHK-09). Ops alerts (DLQ depth, restore drills, backup failures)
arrive via the ops.* signal path (docs/56 §4), not the domain bus.

## Events emitted
notification.sent, notification.failed_final, notification.suppressed (V1
worker emissions — docs/14 §4.1). V2: notification.bounce,
notification.complaint, notification.broadcast_sent.

## Open contract questions
- Resolved 2026-09-20 (D61, docs/58): the V1 template set is the 14-template merged list (docs/14 §3.4); the former 10-template list and its per-event TODOs are superseded.
- Resolved 2026-09-20 (D62, docs/58): no V1 KYC invite email; the invite template is a V2 reserve (`kyc.session_started` stays ext).
- Resolved 2026-09-20 (D63, docs/58): kyc.expired triggers no email in V1 (portal + the payout gate's kyc.required error are the signals).
- Resolved 2026-09-20 (D37, docs/52): no payout.requested event in V1; the template is a V2 reserve.
- Resolved 2026-09-20 (docs/14 §10): transactional email is non-toggleable in V1 (no prefs surface — NOT-11/29 are V2); every email carries the preferences link pointing at the future prefs page (CASL-style honest labeling).
- Resolved 2026-09-20 (docs/14 §2/§3.5): failed sends retry ×3 (backoff) → DLQ + ops alert; dedupe window 24 h, key = sha256(event_type + entity_id + recipient + template_key + template_version).

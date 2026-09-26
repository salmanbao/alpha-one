# Screen 21 — KYC status & start · `/kyc` · F6 · V1.0

> Copy-able UI prompt for the Alpha One trader portal.
> Extracted from `trader-flows-and-screen-prompts.md` (Part 3).
> Source spec: `alpha-one/docs/16-trader-dashboard.md` and the owning module docs.

```prompt
Build the KYC status screen for the Alpha One trader portal (Next.js 15,
TypeScript, Tailwind, shadcn/ui). KYC is a gate system, not a feature: this screen
exists to tell the trader, in one glance, what is verified, what is blocking them,
and the single next action that unblocks it.

LAYOUT — a status hero, a gates panel, a next-action panel, and a history list.
Max-w-3xl.

STATUS HERO — a large state card driven by the verification state machine
(`not_started`, `pending`, `in_review`, `approved`, `rejected`,
`needs_resubmission`, `expired`). Each state has its own icon, colour, headline
and one-sentence explanation written for a trader, never for a compliance officer:
- `not_started`: "Verify your identity to unlock funding and payouts."
- `pending`: "Verification in progress — we'll email you the moment it's decided."
- `in_review`: "Our team is reviewing your documents. Most reviews finish within
  24 hours."
- `approved`: green "You're verified" with the verification date.
- `rejected`: "We couldn't verify your identity" with the **reason class only**
  (e.g. "document unreadable") and a clear path to try again.
- `needs_resubmission`: "We need a clearer photo of your document" with a
  "Resubmit" button.
- `expired`: "Your verification session expired" with "Start again".

GATES PANEL — three rows showing which gates this verification controls, each
with a pass/pending/blocked badge: **Funding** (activating a challenge account),
**Payouts** (receiving money), and — where configured — **Purchases**. A blocked
gate links directly to the action that clears it.

NEXT-ACTION PANEL — a single, unambiguous primary button whose label changes with
the state: "Verify now" / "Continue verification" / "Resubmit documents" /
"Upload documents manually" / nothing when approved. Below it, a short plain
description of what will happen: "You'll take a photo of your ID and a selfie. It
takes about two minutes and happens right here in your browser."

CONSENT & COUNTRY — before starting, a country self-declare select and a consent
line naming the verification provider and linking to the privacy policy. Consent
is captured at session start (the provider requires it) and the record is stored.

HISTORY — a list of past verification attempts with date, outcome and reason
class. Attempts are visible so the trader can see what already failed.

ERROR & EDGE STATES —
- `kyc.country_restricted` (403): "Verification isn't available in your country."
  with a support link — no further action offered.
- `kyc.already_in_progress` (409): "You already have a verification in progress"
  with a "Continue" button instead of a new session.
- After a rejection, a 24-hour cooldown applies: show "You can try again in
  {n} hours" with a countdown and the button disabled.
- Provider unavailable: an amber panel "Our verification provider is temporarily
  unavailable — you can upload documents for manual review instead" with the
  manual path as the primary action. This is the designed degradation, not an
  error.
- Verified identity is shown masked only (e.g. "Ali K."), never in full.

ACCESSIBILITY & MOBILE — the state hero is an aria-live region, gates are a
definition list with text badges, the primary action is always the largest
target, and the layout is single column from 320 px. No dark/light toggle in V1.
```

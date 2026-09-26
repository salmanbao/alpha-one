# Screen 36 — Mobile: KYC capture · app screen · F10 · V2.0

> Copy-able UI prompt for the Alpha One trader portal.
> Extracted from `trader-flows-and-screen-prompts.md` (Part 3).
> Source spec: `alpha-one/docs/16-trader-dashboard.md` and the owning module docs.

```prompt
Build the mobile app's KYC capture screen (React Native, iOS + Android) for the
Alpha One trader companion. The capture happens inside the verification provider's
mobile SDK; our side is the same session API, the same state machine and the same
honest shell as the web flow.

LAYOUT — a status header, the provider's capture surface, and a progress footer.

STATUS HEADER — the same state hero semantics as the web KYC screen
(not started / pending / in review / approved / rejected / needs resubmission /
expired), each with a plain-language headline, plus the gates the verification
controls (funding, payouts) with pass/pending/blocked badges. The verified name is
always masked.

CAPTURE — embed the provider's mobile SDK (the same provider adapter the web flow
uses — a second client, not a second integration). Before launching, request
camera permission with a native rationale ("We need your camera to photograph your
ID") and handle a denial with a settings deep-link and the manual-upload fallback.
A session started on the phone completes on the phone; a session started on the web
shows "Continue on your other device" rather than restarting.

PROGRESS — states only, never a fake percentage: a stepper with "Documents →
Selfie → Done", advancing on real provider callbacks. If the provider returns
undecided, show "Our team will review this manually — we'll email you" and link
back to the status view.

FALLBACK — if the provider is unavailable, the screen offers the manual upload path
natively: camera or photo-library capture per document slot, with the same
client-side pre-checks (type, 10 MB maximum, minimum resolution) and per-file
progress with retry. This is the designed degradation, not an error.

COMPLETION — a native success panel ("You're verified" or "Submitted for review")
with the next step in one sentence, then auto-return to the status view after a
short, visible countdown.

ERROR & EDGE STATES — a restricted country shows "Verification isn't available in
your country" with a support link; an in-progress session shows "Continue
verification" rather than starting a second one; a 24-hour cooldown after a
rejection shows a countdown; an expired session offers "Start a new one". Documents
upload from the device are encrypted in transit and stored tenant-prefixed.

ACCESSIBILITY — the status header is announced on change, the stepper uses text
labels, all capture affordances are at least 44×44 pt, Dynamic Type is respected,
and the camera permission rationale is readable by VoiceOver/TalkBack.
```

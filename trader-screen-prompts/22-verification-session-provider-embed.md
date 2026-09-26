# Screen 22 — Verification session (provider embed) · `/kyc/session/{id}` · F6 · V1.0

> Copy-able UI prompt for the Alpha One trader portal.
> Extracted from `trader-flows-and-screen-prompts.md` (Part 3).
> Source spec: `alpha-one/docs/16-trader-dashboard.md` and the owning module docs.

```prompt
Build the hosted verification session screen for the Alpha One trader portal
(Next.js 15, TypeScript, Tailwind, shadcn/ui). The provider's flow (Veriff) runs
inside a same-origin iframe wrapper; our job is a calm, honest shell around it.

LAYOUT — a header with the account/firm name and a "Cancel" text button, the
iframe area, and a status footer. Max-w-3xl.

IFRAME AREA — the provider checkout embedded in a same-origin wrapper iframe with
a fixed aspect ratio that grows to fill available height on mobile. Above it a
one-line "You're verifying with { provider } — your documents go straight to them,
we only see the result."

LOADING STATE — a skeleton panel with a spinner and the line "Opening secure
verification…". If the provider takes more than 10 seconds, add "Taking longer
than usual? You can cancel and try again." — never a blank rectangle.

PROGRESS — show **states only, never a fake percentage**: a small stepper with
"Documents → Selfie → Done", advancing only on real provider callbacks. If the
provider reports an undecided result, the shell shows "Our team will review this
manually — we'll email you" and links back to the KYC status screen.

COMPLETION — on the provider's success callback, show a green confirmation panel
"You're verified" (or "Submitted for review" where manual review is required), the
next step in one sentence, and primary buttons "Back to verification status" and
"Go to my accounts". Auto-return to the KYC status screen after ~3 seconds with a
visible countdown so it never feels stuck.

CANCELLATION — "Cancel" opens a confirm dialog: "Leave verification? Your progress
won't be saved and you can start again later." On confirm, abandon the session
server-side and return to the status screen. Never leave an orphaned provider
session.

ERROR & EDGE STATES — provider unavailable (503): the shell swaps to the manual
upload path with an explanation. Session expired (24 h TTL): "This verification
link expired" with "Start a new one". Webhook mismatch (a provider callback for an
unknown session): never change state; show a neutral "Something went wrong —
please start again" and log the correlation id for support. Browser blocked
third-party iframes: a fallback panel with an "Open verification in a new tab"
button.

ACCESSIBILITY & MOBILE — the iframe has a descriptive title, focus is moved to the
shell heading on load, the cancel dialog traps focus and closes on Escape, and
the layout works from 320 px with the iframe filling the viewport height on
phones. No dark/light toggle in V1.
```

# Screen 02 — 2FA enrolment & backup codes · `/login/2fa` · F1 · V1.0

> Copy-able UI prompt for the Alpha One trader portal.
> Extracted from `trader-flows-and-screen-prompts.md` (Part 3).
> Source spec: `alpha-one/docs/16-trader-dashboard.md` and the owning module docs.

```prompt
Build the two-factor authentication enrolment screen for the Alpha One trader
portal (Next.js 15, TypeScript, Tailwind, shadcn/ui). It is shown the first time a
trader enables 2FA from their profile, and re-shown whenever they add or reset a
factor. The whole flow runs inside one shared `SensitiveDialog` shell: a title, a
one-line reason ("Confirm it's you to change your security settings"), the 2FA
step, and a typed confirmation.

LAYOUT — three sequential steps in a single card with a step indicator (1 Set up ·
2 Verify ·3 Save backup codes), max-w-lg.

STEP 1 — "Set up your authenticator": a QR code (rendered as an SVG, ~200 px) for
the TOTP secret, the secret shown as monospace text with a copy button and a
"Can't scan? Enter this key manually" disclosure, and a plain-language line:
"Open Google Authenticator, Authy or 1Password and scan this code."

STEP 2 — "Verify": a 6-digit code input (six single-character boxes, auto-advance,
paste support) and a "Verify and enable" button. While pending show a spinner on
the button; on a wrong code show an inline "That code isn't right. Codes change
every 30 seconds — try the current one." with a live countdown to the next code
window. On success show a green success state with a check icon and auto-advance.

STEP 3 — "Save your backup codes": a 2×5 grid of 10 monospace codes, buttons for
"Copy all" and "Download as .txt", a required checkbox "I have saved these codes
somewhere safe", and an "Finish" button that is disabled until the box is ticked.
Warn clearly: "Each code works once. If you lose your authenticator these are the
only way back in."

EXTRA STATES — a "Regenerate backup codes" action (also step-up protected) that
invalidates the old codes after confirmation; a status line "Backup codes
remaining: {n}"; and a read-only summary card for users already enrolled showing
enrolment date, method (TOTP), and codes remaining, with "Remove 2FA" as a
destructive, step-up-protected action that warns it will sign out other devices.

ACCESSIBILITY & MOBILE — each step is a labelled region, focus moves to the new
step's heading on advance, the QR has a text alternative (the manual key), all
buttons have accessible names, and the code inputs use inputmode="numeric" with
autocomplete="one-time-code" so mobile keyboards and SMS autofill work. Responsive
single column from 320 px. No dark/light toggle in V1.
```

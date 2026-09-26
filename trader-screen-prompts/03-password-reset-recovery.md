# Screen 03 — Password reset / recovery · `/reset-password` · F1 · V1.0

> Copy-able UI prompt for the Alpha One trader portal.
> Extracted from `trader-flows-and-screen-prompts.md` (Part 3).
> Source spec: `alpha-one/docs/16-trader-dashboard.md` and the owning module docs.

```prompt
Build the self-serve password reset flow for the Alpha One trader portal
(Next.js 15, TypeScript, Tailwind, shadcn/ui). Three states on one route,
tenant-branded, no support ticket required at any point.

STATE A — "Reset your password" (default): an email field, a "Send reset link"
button, and a line "We'll email you a link to choose a new password. The link
works once and expires in 60 minutes." Below the form: "Remembered it? Back to
sign in."

STATE B — "Check your email": shown immediately after submit, always identical
whether or not the address exists (enumeration resistance) — a mail icon, the
masked address the link was sent to, a "Resend email" button with a 60-second
cooldown, a "Change email address" link back to State A, and a hint "Nothing
after a few minutes? Check spam, then contact support."

STATE C — "Choose a new password": reached from the emailed link (validates the
token server-side). Fields: new password with show/hide, confirm new password,
and a live checklist that ticks off as the trader types: at least 10 characters,
upper and lower case, a number, not one of your last 5 passwords, and not found
in a known breached-password list. A "Save and sign in" button.

BEHAVIOUR — the reset itself is handled by the hosted identity provider; the
portal only initiates and consumes it. On success, sign the trader in and land on
the account home with a success toast "Password updated. Other devices have been
signed out." — because a credential change revokes every other session, and the
trader must be told that happened.

ERROR & EDGE STATES — expired or already-used link: a full-card state "This reset
link has expired." with a "Send a new link" button. Rate limited: inline amber
"Too many requests — try again in {n} seconds." Password rejected by policy:
inline field error quoting the specific failing rule. Network/server failure:
inline error with a retry button and a "Contact support" link carrying the
correlation id.

ACCESSIBILITY & MOBILE — single column, max-w-md, large tap targets, the
checklist is an aria-live region so screen-reader users hear each rule pass, and
the whole flow works from 320 px. Do not add a dark/light toggle.
```

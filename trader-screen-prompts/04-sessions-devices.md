# Screen 04 — Sessions & devices · `/profile/security` · F1 · V2.0

> Copy-able UI prompt for the Alpha One trader portal.
> Extracted from `trader-flows-and-screen-prompts.md` (Part 3).
> Source spec: `alpha-one/docs/16-trader-dashboard.md` and the owning module docs.

```prompt
Build the "Sessions & devices" security screen for the Alpha One trader portal
(Next.js 15, TypeScript, Tailwind, shadcn/ui). It answers one question: who else
is in my account, and how do I get them out.

LAYOUT — a page inside the profile section: breadcrumb "Profile / Security", a
heading "Where you're signed in", and a table (cards on mobile) of active
sessions.

SESSION ROW — device label (e.g. "Ali's iPhone", "Chrome on Windows"), a
"Current session" badge on this one, approximate location (city, country — or
"Unknown"), "Last active {relative time}", "Signed in {date}", and a "Sign out"
button. Above the table: a count "3 active sessions" and a destructive
"Sign out of all other devices" button that opens the shared `SensitiveDialog`
(reason + 2FA step-up + typed confirmation) before executing.

BELOW THE TABLE — two short explainer cards:
- "Changing your password signs out every other device automatically."
- "Lost your phone? Sign out of all devices, then change your password."
Each with a link to the relevant action.

EMPTY STATE — only the current session: "You're signed in on this device only."

STATES — loading skeletons for the table; a per-row spinner while revoking; a
success toast "Signed out of {device}"; an optimistic row removal that reverts
with an inline error and a retry button if the call fails; a 429 state showing
"Too many attempts — try again in {n} seconds."

DATA — `GET /v1/auth/sessions` and `DELETE /v1/auth/sessions/{id}` via the GW with
the session cookie; never expose raw token identifiers in the DOM.

ACCESSIBILITY & MOBILE — the table becomes stacked cards under 640 px, the
destructive action has a confirmation dialog and is never the default focus, and
every row action is reachable by keyboard. No dark/light toggle in V1.
```

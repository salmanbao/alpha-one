# Screen 29 — Notification centre · `/notifications` · F9 · V2.0

> Copy-able UI prompt for the Alpha One trader portal.
> Extracted from `trader-flows-and-screen-prompts.md` (Part 3).
> Source spec: `alpha-one/docs/16-trader-dashboard.md` and the owning module docs.

```prompt
Build the in-app notification centre for the Alpha One trader portal (Next.js 15,
TypeScript, Tailwind, shadcn/ui). In V1 the centre is a stub — email is the only
channel — so the V1 screen must be honest about that while reserving the exact
shape V2 fills in.

LAYOUT — a header with an unread count and a "Mark all read" action, a filter row,
and a grouped list. Max-w-3xl. On mobile it is a full-screen route; on desktop a
popover anchored to the bell in the top bar.

V1 STUB STATE — a single, plainly-worded panel: "Notifications are delivered by
email. In-app notifications are coming soon." Beneath it, a read-only list of the
lifecycle events that have been emailed to the trader (account created, phase
passed, phase failed, breach, KYC result, payment captured, payout approved,
payout rejected, payout settled) with their dates and a link to the relevant
object where one exists. This is a history view, not a lie about live in-app
delivery.

V2 LIST — notification rows with an unread dot, a type icon, a title, a one-line
body, a relative timestamp, and a deep link to the object. Grouped under date
headers (Today / Yesterday / Earlier). Unread rows have a subtle background;
read rows are plain. Clicking a row marks it read and navigates.

FILTERS — All / Unread, and type chips (Accounts, Payouts, KYC, Documents,
Security). Filters write to the URL.

PREFERENCES (V2) — a linked settings panel: a matrix of channels (Email, In-app,
Push, Telegram) × categories (Transactional — always on, Account updates,
Payouts, Marketing), quiet hours with a timezone, and a digest option. Transactional
rows are non-toggleable and rendered as such with an explanation, rather than as
disabled switches.

BEHAVIOUR — live updates arrive over the same SSE stream as the rest of the portal;
new notifications prepend with an aria-live announcement and the bell badge
increments. Optimistic "mark read" reverts with an inline retry on failure.

EMPTY STATE — "Nothing new. We'll tell you here when something happens to your
accounts."

ERROR & EDGE STATES — a failed list fetch shows an inline retry; the bell badge
falls back to the last known count rather than disappearing.

ACCESSIBILITY & MOBILE — the list is an aria-live region for new items, unread
state is conveyed by text as well as a dot, the popover traps focus and closes on
Escape and outside-click, and the full-screen mobile route has a back button. No
dark/light toggle in V1.
```

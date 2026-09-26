# Screen 31 — Support & ticket history · `/support` · F9 · V2.0

> Copy-able UI prompt for the Alpha One trader portal.
> Extracted from `trader-flows-and-screen-prompts.md` (Part 3).
> Source spec: `alpha-one/docs/16-trader-dashboard.md` and the owning module docs.

```prompt
Build the support screen for the Alpha One trader portal (Next.js 15, TypeScript,
Tailwind, shadcn/ui). Support lives inside the product: the trader raises a ticket
from here or from any dead end elsewhere, and never has to find an email address.

LAYOUT — two panes on desktop (ticket list left, thread right) and a
list→detail navigation on mobile. Max-w-6xl.

NEW TICKET FORM — a category select with the fixed V1 set (Account, Payment,
Payout, KYC, Technical, Other), a subject line, a message body, an optional
attachment (type and size validated; unscanned files carry a visible
"unscanned" flag for staff), and a "Submit" button. When the trader arrived from a
dead end elsewhere in the portal, the form opens **pre-filled** with the context:
the account id, the saga id where one exists, the error code, and the page they
were on — shown as read-only "context chips" above the form so the trader can see
exactly what support will receive. A line explains: "Including this context helps
us answer faster."

TICKET LIST — the trader's own tickets only: subject, category badge, status
badge, last-activity relative time, and an unread indicator when staff has
replied. Filter chips by status (Open / In progress / Resolved / Closed /
Cancelled) and a search box. Sorted by last activity, newest first.

THREAD VIEW — the ticket header (subject, category, status, created date, the
context chips), then a chronological message thread. Three message types are
visually distinct: trader messages, staff replies, and internal notes (internal
notes are **never** shown to the trader — they exist only in the staff view; do
not render a placeholder for them). Each staff reply shows the agent's display
name and role. A reply box at the bottom with a "Send" button; sending is
optimistic with a retry on failure. The trader can cancel their own open ticket
via a "Cancel ticket" action with a confirm dialog.

STATUS MACHINE (trader-visible) — `open` → `in_progress` → `resolved` → `closed`,
plus `cancelled` by the trader. Each transition is shown in the thread as a
system line ("Your ticket was marked as resolved — reply to reopen it"). Replying
to a resolved ticket reopens it, and the UI says so.

NOTIFICATIONS — a note that every status change and reply is emailed (in-app
arrives in V2), with a link to the notification preferences.

EMPTY STATE — "No tickets yet. If something's wrong with your account, the fastest
way to reach us is here." with the form focused.
ERROR — inline retry on both panes; a failed send keeps the draft text.

ACCESSIBILITY & MOBILE — the list is a proper listbox/tablist pair with
aria-selected, the thread is an ordered list of articles, the reply box is
labelled and announces "Sent" via aria-live, and the mobile flow is list →
detail with a back button. No dark/light toggle in V1.
```

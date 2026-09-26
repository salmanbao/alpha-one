# Screen 38 — Trading journal · `/journal` · F10 · V2.0/V3.0

> Copy-able UI prompt for the Alpha One trader portal.
> Extracted from `trader-flows-and-screen-prompts.md` (Part 3).
> Source spec: `alpha-one/docs/16-trader-dashboard.md` and the owning module docs.

```prompt
Build the trading journal screen for the Alpha One trader portal (Next.js 15,
TypeScript, Tailwind, shadcn/ui). It is the trader's private workspace: a place to
attach notes, tags and emotions to their own deals. Privacy is the headline
requirement — there is no staff read path, ever, and the UI must make that
unmistakable.

LAYOUT — a header with a "New entry" primary button, a filter/search row, and a
two-pane layout on desktop (entry list left, editor right) that becomes a
list→detail flow on mobile. Max-w-6xl.

ENTRY LIST — each entry shows the linked trade (symbol, side, lots, close time,
net P&L), the entry's title, its tags as chips, a mood/confidence indicator if the
trader set one, and the last-edited relative time. Search across title, body, tags
and symbol; filter by tag, by date range, and by outcome (winners / losers).

EDITOR — a title field, a rich-text body (bold, italic, lists, links — no image
paste from arbitrary URLs), a tag input with suggestions from the trader's existing
tags, an emotion/confidence picker, and a "linked deal" reference. The linked deal
is a **frozen snapshot** of the trade at the time of linking: symbol, side, lots,
open and close prices, P&L, swap, commission, timestamps and the broker ticket.
Show the snapshot as a read-only card above the editor so the trader can see
exactly which trade the entry belongs to, even if the trade list paginates away.

LINKING — a "Link a trade" action opens a searchable picker of the trader's closed
deals; selecting one attaches the frozen snapshot and shows the card. An entry can
link to one deal (V2) or several (V3).

ANALYTICS (V2) — a stats strip computed from the journal itself: entries per week,
the trader's win rate on entries tagged with a given emotion, average P&L by tag,
and a calendar heat-map of P&L by day. Clearly labelled as derived from the
trader's own notes and closed deals.

REPLAY & SHARING (V3) — a "Replay" action that re-renders the linked trade's price
action around its open and close with the entry's notes as annotations, and an
opt-in "Share" that produces a public, read-only, anonymised link (no account
numbers, no identity) — off by default, and the share dialog says plainly what will
be visible.

PRIVACY BANNER — a persistent, dismissible-per-session banner: "Your journal is
private. No one at your firm or at Alpha One can read it." It reappears on the
first entry of each session.

EMPTY STATE — "No entries yet. Write your first note on a closed trade to start
building your edge." with the button focused.
ERROR — per-pane retry; a failed save keeps the draft in local state and offers
"Retry" and "Copy to clipboard" so work is never lost.

ACCESSIBILITY & MOBILE — the editor is keyboard-navigable with a visible focus
ring, the list is a semantic list with aria-selected, the two-pane layout collapses
to a stack under 1024 px, and the body field supports undo/redo natively. No
dark/light toggle in V1.
```

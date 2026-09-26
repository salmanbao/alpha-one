# Screen 27 — Payout history & receipts · `/payouts/history` · F7 · V1.0

> Copy-able UI prompt for the Alpha One trader portal.
> Extracted from `trader-flows-and-screen-prompts.md` (Part 3).
> Source spec: `alpha-one/docs/16-trader-dashboard.md` and the owning module docs.

```prompt
Build the payout history and receipts screen for the Alpha One trader portal
(Next.js 15, TypeScript, Tailwind, shadcn/ui). Every payout the trader has ever
requested, with the receipt as a first-class citizen — the receipt is the dispute
defence, so it must always be one click away.

LAYOUT — a filter row, a table of requests, and an expandable detail panel per
row. Max-w-5xl.

FILTERS — status chips (All / Pending / Approved / On hold / Paid / Rejected), a
date range, and an account selector when there are several. Filters write to the
URL query.

TABLE COLUMNS — Requested (date), Account, Amount (final, in the account
currency), Method (rail + masked destination), Status badge, and actions
(Receipt, Details, Support).

STATUS BADGES — always word + colour: `pending_approval` amber "Awaiting
approval", `approved` blue "Approved", `on hold` amber "On hold for review",
`paid` green "Paid", `rejected` red "Not approved". A rejected row shows the
reason class in the table itself, not hidden in a tooltip.

EXPANDED DETAIL PANEL — the full, recomputable record:
- The frozen calculation: gross (high-water − initial), less already paid, trader
  share at the split ratio, cap at the requested amount, rail fee, final amount —
  each step on its own row with the arithmetic.
- The method **version** used and its masked destination, so the address a payout
  went to is always answerable.
- The execution record: provider, external reference (last four characters),
  amount, and timestamp.
- The approval trail: who approved it and when, in the firm's terms ("Approved by
  your firm's finance team on { date }").
- The rejection reason where applicable, plus a "Ask about this decision" button
  that opens support with the payout id pre-filled (the dispute channel lives in
  the product).

RECEIPT — a "Download receipt (PDF)" button on every `paid` row, rendered from
the frozen calculation. Signed URLs are 15 minutes and fetched on click, never
embedded. A receipt still generating shows "Preparing…" with a spinner and
auto-enables when ready; a failure shows an inline retry.

EMPTY STATE — "No payout requests yet" with a "Request a payout" button.
LOADING — skeleton rows. ERROR — inline retry with a support link.

ACCESSIBILITY & MOBILE — the table becomes stacked cards under 768 px with the
status badge first, the detail panel is a proper disclosure with aria-expanded,
amounts use tabular numerals and a consistent currency format, and every action is
keyboard reachable. No dark/light toggle in V1.
```

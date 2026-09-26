# Screen 09 — Orders & invoices · `/orders` · F2 · V1.1

> Copy-able UI prompt for the Alpha One trader portal.
> Extracted from `trader-flows-and-screen-prompts.md` (Part 3).
> Source spec: `alpha-one/docs/16-trader-dashboard.md` and the owning module docs.

```prompt
Build the order and invoice history screen for the Alpha One trader portal
(Next.js 15, TypeScript, Tailwind, shadcn/ui). Every purchase the trader has ever
made, in one place, with the paperwork attached.

LAYOUT — a page header "Orders & invoices" with a count, a filter row, and a
table (cards on mobile). Server-rendered; no live stream needed.

FILTERS — status chips (All / Paid / Provisioning / Fulfilled / Failed /
Abandoned), a date-range picker (last 30 / 90 days / all time), and a text search
on order number or challenge name. Filters write to the URL query.

TABLE COLUMNS — Date, Order no. (monospace), Challenge (name + size), Amount
(with currency), Method (masked), Status badge, and an actions cell.

STATUS BADGES — colour-coded and labelled in words, never colour alone:
`open` grey "Awaiting payment", `paid` blue "Paid", `provisioning` amber
"Setting up", `fulfilled` green "Complete", `failed_provisioning` red "Setup
failed", `abandoned` grey "Abandoned".

ROW ACTIONS — "Download invoice" (V1.1), "Download receipt", "Retry payment"
(only when the order is `open` with a dead intent), "View account" (when
fulfilled and an account exists), and "Contact support" (always, as the last
item in an overflow menu).

ROW EXPANSION — clicking a row expands a detail panel: the full line items, the
frozen price snapshot (base, FX rate if converted, fee model, total), the payment
attempts (each with provider, masked reference, amount and outcome), the coupon
used if any, the linked account id, and the invoice/receipt download links.

DOCUMENT STATES — "Preparing…" with a spinner while the PDF worker is still
rendering (409 `receipt.not_ready`); "Download" once generated; an inline retry
if a signed URL fails to resolve. Signed URLs are 15-minute and fetched on click,
never embedded in the page.

EMPTY STATE — "No orders yet" with a "Browse challenges" primary button.
LOADING — skeleton table rows. ERROR — inline banner with retry and support link.

ACCESSIBILITY & MOBILE — the table becomes stacked cards under 768 px with the
status badge first, all badge colours meet AA contrast and are accompanied by
text, and the expansion is a proper disclosure widget with aria-expanded.
```

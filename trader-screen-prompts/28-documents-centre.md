# Screen 28 — Documents centre · `/documents` · F8 · V1.0

> Copy-able UI prompt for the Alpha One trader portal.
> Extracted from `trader-flows-and-screen-prompts.md` (Part 3).
> Source spec: `alpha-one/docs/16-trader-dashboard.md` and the owning module docs.

```prompt
Build the documents centre for the Alpha One trader portal (Next.js 15,
TypeScript, Tailwind, shadcn/ui). Agreements, certificates, invoices and receipts
in one place — the paper a prop-firm trader screenshots and shares.

LAYOUT — a page header "Documents", a type filter, and a grouped list. Max-w-4xl.

TYPE FILTER — chips: All / Agreements / Certificates / Invoices / Receipts, with
counts. Filters write to the URL.

DOCUMENT ROW — an icon per type, the document title in plain words ("Funded
account certificate — $100,000"), the related account or order, the issue date,
and a primary "Download" button. A "New" badge appears on documents generated in
the last 7 days (V2 in-app notification complement). Rows are grouped under
sticky type headers with a count.

DOCUMENT TYPES (V1) — challenge agreement (issued at purchase), funded account
certificate, invoice, payout receipt. Each has its own icon and colour.

STATES PER ROW —
- Generated: an enabled "Download" button.
- Pending: a disabled-looking "Preparing…" with a small spinner; the button
  auto-enables when the document arrives (poll or SSE), never requiring a reload.
- Failed: "Couldn't generate this document" with a "Try again" button and a
  support link carrying the document id.

BEHAVIOUR — clicking Download calls the signed-URL route (15-minute TTL, audited)
and opens the PDF in a new tab; the URL is never embedded in the page or logged.
Show a brief "Preparing your download…" state while the URL resolves. On mobile,
the PDF opens in the system viewer.

EMPTY STATE — "No documents yet. Your agreement and invoice appear here right
after your first purchase, and your certificate the moment you're funded." with a
"Browse challenges" button.

ERROR & EDGE STATES — a document the trader doesn't own or that doesn't exist
returns the not-found page (404, never 403). A bulk list failure shows an inline
retry. Never render a broken link or an empty href.

ACCESSIBILITY & MOBILE — rows are list items with descriptive accessible names
including the type and date, the "New" badge is text as well as colour, group
headers are real headings, and the layout is a single column from 320 px. No
dark/light toggle in V1.
```

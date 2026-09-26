# Screen 10 — Account home (overview dashboard) · `/` · F3/F4 · V1.0

> Copy-able UI prompt for the Alpha One trader portal.
> Extracted from `trader-flows-and-screen-prompts.md` (Part 3).
> Source spec: `alpha-one/docs/16-trader-dashboard.md` and the owning module docs.

```prompt
Build the account home / overview dashboard — the landing page after sign-in —
for the Alpha One trader portal (Next.js 15, TypeScript, Tailwind, shadcn/ui).
This is the screen a funded trader opens every day. It must answer "where do I
stand?" in under five seconds.

LAYOUT — a top bar with the tenant logo, an account switcher (when the trader has
more than one account), the trader's avatar menu, and a global freshness chip.
Below: a responsive grid of account cards (1 column mobile, 2 desktop), then a
secondary row of widgets.

ACCOUNT CARD — the core component of the whole portal:
- Header: program name, account size, and the **state badge** (one component,
  reused everywhere): `opening` (spinner + a mini steps strip), `evaluating`
  (phase + "Phase 1 of 2"), `funded` (green "Funded"), `paused`/`suspended`
  (amber with a reason class and a support link), `failed`/`breached` (red, with
  the rule name and a "View report" link), `closed` (grey, documents only).
- Metric row: Equity (large), Balance, Open P&L (green/red), Drawdown used
  (e.g. "2.10% of 6.00%"), Daily loss used, Target progress (e.g. "68% of
  $8,000"), Time left ("27 days").
- A **tick-age chip** on the card footer: green dot + "Live" under 2 minutes;
  amber dot + "stale — 6 min ago" when older; a card-level banner "Data from
  14:02" past 10 minutes. Never render a number without its age.
- Footer actions: "Open" (account detail), "Live view", "Payout", "Credentials".

SECONDARY WIDGETS (V1 minimal, V2 configurable) — a compact equity sparkline for
the selected account (last 24 h, appended live over SSE), a "Next payout"
eligibility teaser with the available amount and next eligible date, a documents
"new" badge count, and a support shortcut. Widgets are individually hideable and
rearrangeable in V2 — build the grid so that is a data change, not a rewrite.

LIVE BEHAVIOUR — subscribe to SSE for the selected account; update the metrics
and sparkline in place without a reload; on stream loss fall back to 5-second
polling and show the amber "reconnect" chip. Server-side revalidation is 30
seconds, and authenticated pages are never CDN-cached.

EMPTY STATE — no accounts: a friendly panel "You don't have any accounts yet"
with a "Browse challenges" primary button and a "How it works" link.
PARTIAL FAILURE — if one card's fetch fails while the page renders, show that
card as a skeleton with its own retry button; never break the whole page.
ERROR — full-page error boundary with retry, a pre-filled support ticket and the
Sentry id shown.

ANNOUNCEMENTS (V2) — a dismissible tenant announcement banner slot at the top,
driven by tenant config, never blocking the metrics.

ACCESSIBILITY & MOBILE — cards are semantic articles with headings, the state
badge always includes a text label, the metric grid reflows to two columns on
phones, all interactive elements are keyboard reachable, and first contentful
paint stays under 2.5 s on a 4G connection (server-render the metrics, hydrate
only the sparkline and switcher). No dark/light toggle in V1.
```

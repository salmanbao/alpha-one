# Screen 13 — Live trading view · `/accounts/{id}/trade` · F4 · V1.0

> Copy-able UI prompt for the Alpha One trader portal.
> Extracted from `trader-flows-and-screen-prompts.md` (Part 3).
> Source spec: `alpha-one/docs/16-trader-dashboard.md` and the owning module docs.

```prompt
Build the live trading view for the Alpha One trader portal (Next.js 15,
TypeScript, Tailwind, shadcn/ui). It is the trader's window onto their broker
account: an equity curve that moves, the positions they hold, and the deals they
have closed.

LAYOUT — a header with the account name, the state badge and the freshness chip;
then the equity chart panel; then a tab bar (Positions / History / Orders) with
its table. Max-w-6xl.

EQUITY CHART PANEL — a line/area chart of equity over the selected range (1H /
1D / 1W / 1M / All). In V1.0 render with plain SVG or canvas (no chart library
dependency); the component boundary must allow swapping in TradingView
Lightweight Charts in V2 without touching the data layer. The chart hydrates with
the last 60 points and appends live points from SSE. Draw the high-water mark as
a dashed reference line and the drawdown floor as a red dashed line when the rule
pack has one. Full history is a server-fetched range request with 30-second
revalidation — never block first paint on it. Show the y-axis in the account
currency and the x-axis in the trader's local time.

FRESHNESS — the panel header carries the tick-age chip: green "Live" under 2
minutes, amber "stale — n min ago" when older, and an amber banner "Data from
{time}" past 10 minutes. If the SSE stream drops three times, switch to 5-second
polling and show an amber "Reconnecting…" chip — this is a degraded mode, not an
error screen.

POSITIONS TAB — a table of open positions: Symbol, Side (buy/sell badge), Lots,
Open price, Current price, S/L, T/P, P&L (coloured and signed), Swap, Commission,
Opened (broker time). Totals row for floating P&L. Pagination at 100 rows per
page. Live P&L updates in place; a row flashes subtly on change rather than
re-mounting.

HISTORY TAB — closed deals: Close time, Symbol, Side, Lots, Open, Close, P&L,
Swap, Commission, and a ticket number. Date-range filter and a "Export CSV"
button (V2) that generates the file client-side from the fetched page.

ORDERS TAB — pending orders (V2). In V1 render the tab with an honest "Working
orders aren't tracked yet" empty state rather than hiding the tab.

EMPTY & ERROR STATES — no open positions: "No open positions" with a line "Your
closed trades appear under History." Chart with a single point or none: a flat
line with "Not enough data yet". Fetch failure inside the panel: a per-panel
skeleton with its own retry, never a broken page. Never show a number without its
timestamp.

ACCESSIBILITY & MOBILE — tables become card lists under 768 px, the chart has a
text summary ("Equity up 2.4% today, high $104,155, low $103,980") for screen
readers, live updates are polite aria-live regions and never steal focus, and the
tabs are a proper ARIA tablist. No dark/light toggle in V1.
```

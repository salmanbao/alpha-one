# Screen 18 — Performance stats · `/accounts/{id}/performance` · F4 · V2.0

> Copy-able UI prompt for the Alpha One trader portal.
> Extracted from `trader-flows-and-screen-prompts.md` (Part 3).
> Source spec: `alpha-one/docs/16-trader-dashboard.md` and the owning module docs.

```prompt
Build the performance statistics screen for the Alpha One trader portal
(Next.js 15, TypeScript, Tailwind, shadcn/ui). Basic analytics computed from the
trader's own closed deals — enough to be useful, clearly labelled as indicative.

LAYOUT — a date-range selector (7 / 30 / 90 days / all), a summary strip of four
headline numbers, a breakdown table, and an equity/drawdown chart. Max-w-6xl.

HEADLINE NUMBERS — Win rate (%), Average win, Average loss, Profit factor. Each
tile shows the value, the label, and a one-line plain explanation on hover/focus
("Profit factor = gross profit ÷ gross loss. Above 1.0 is profitable.").

SECONDARY METRICS (V2 advanced) — Sharpe ratio, Sortino ratio, Calmar ratio and
maximum drawdown duration, each with the same explanatory tooltip and a
computation note ("computed from daily closes, 365-day basis").

BREAKDOWN TABLE — per symbol: trades, win rate, net P&L, average win, average
loss, largest win, largest loss, total commission + swap. Sortable columns, with
the sort state in the URL. A totals row at the bottom.

CHART — a combined equity curve with a drawdown sub-chart underneath, sharing the
x-axis, rendered with the same chart component boundary as the live view so the
V1 SVG/canvas implementation and the V2 chart-library swap stay in one place.

HONESTY RULES — every metric is computed from closed deals only; open positions
are excluded and the screen says so. Where there are too few trades for a metric
to be meaningful (e.g. fewer than 30 closed trades for a Sharpe ratio), show the
metric as "—" with a tooltip "Needs at least 30 closed trades", never a fabricated
number. A footer note: "Statistics are indicative and computed from broker data
synced to the platform. They are not a statement of account."

EMPTY STATE — no closed trades: an illustration-free, plain panel "No closed
trades in this period" with the range selector highlighted.
ERROR — per-panel retry; never a blank page.

ACCESSIBILITY & MOBILE — headline tiles are semantic with text values (never
colour-only), the table becomes cards under 768 px, sortable headers are real
buttons with aria-sort, and the chart has a text summary for screen readers.
```

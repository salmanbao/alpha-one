# Screen 11 — Account detail · `/accounts/{id}` · F4 · V1.0

> Copy-able UI prompt for the Alpha One trader portal.
> Extracted from `trader-flows-and-screen-prompts.md` (Part 3).
> Source spec: `alpha-one/docs/16-trader-dashboard.md` and the owning module docs.

```prompt
Build the account detail screen for the Alpha One trader portal (Next.js 15,
TypeScript, Tailwind, shadcn/ui). One account, everything about it, with a clear
route into every sub-surface.

LAYOUT — a header block, a metrics grid, a tab bar, and a state-history timeline.
Max-w-6xl.

HEADER — program name and account size, the state badge (the same component used
on the home cards, with the same semantics), the phase ("Phase 1 of 2"), the
broker and a masked broker account number, and a freshness chip. A primary
action cluster on the right: "Live view", "Request payout" (only when funded and
eligible), "Credentials", and an overflow menu with "Documents", "Rules",
"Contact support".

METRICS GRID — Equity, Balance, Open P&L, High-water mark, Trailing drawdown
(bps and %), Daily loss used / limit, Profit target progress, Trading days
completed / minimum, and Time left. Each tile shows the value, a label, and where
relevant a thin progress bar with the limit marked. All values carry the tick-age
chip treatment.

TAB BAR — "Overview" (metrics + history), "Live view" (positions, deals, equity
chart), "Objectives" (the meters), "Rules" (plain language), "History" (state
transitions). Tabs are proper ARIA tabs with arrow-key navigation and the active
tab is reflected in the URL so the view is shareable and reload-safe.

STATE HISTORY TIMESTAMPED LIST — every transition with from-state, to-state,
trigger, actor (system / firm / trader) and timestamp in the trader's local time
( broker time on hover where they differ ). The most recent first, "Load more"
pagination. This is the trader-visible half of the append-only state history.

STATE-DRIVEN CONTENT — the screen adapts to the account state:
- `opening`: a prominent steps strip (payment → KYC → broker account → active)
  with the "taking longer than usual?" support escape hatch.
- `evaluating`: objectives front and centre.
- `funded`: payout call-to-action with the available amount.
- `paused`/`suspended`: an explanation panel with the reason class and a support
  link; payout actions hidden.
- `failed`/`breached`: a red panel naming the rule, the observed value versus the
  threshold, and a "View breach report" link.
- `closed`: documents only, all actions disabled with a plain explanation.

DATA — `GET /v1/trader/accounts/{id}` (server component) plus the SSE stream for
live updates. A cross-tenant or unknown id returns the "not found" page — never a
403.

ACCESSIBILITY & MOBILE — one heading per section, the metric grid collapses to two
columns on phones, tabs become a scrollable tablist, and the timeline is a
semantic ordered list. No dark/light toggle in V1.
```

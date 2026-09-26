# Screen 33 — Mobile: live trade viewer · app tab · F10 · V2.0

> Copy-able UI prompt for the Alpha One trader portal.
> Extracted from `trader-flows-and-screen-prompts.md` (Part 3).
> Source spec: `alpha-one/docs/16-trader-dashboard.md` and the owning module docs.

```prompt
Build the mobile app's live trade viewer screen (React Native, iOS + Android) for
the Alpha One trader companion app. It is the web live trading view in a native
window, consuming the same read APIs and the same SSE stream.

LAYOUT — a screen with a segmented control (Chart / Positions / History), a
freshness header, and a scrollable body. Pull-to-refresh.

CHART SEGMENT — an equity curve for the selected range (1H / 1D / 1W / 1M), with
the high-water mark as a dashed reference line and the drawdown floor as a red
dashed line where the rule pack defines one. Prefer a native chart library that
accepts the same data shape; if none renders correctly, embed the web chart route
in a webview — the data contract is identical either way. The chart hydrates with
the last 60 points and appends live points from SSE; full history is a
range request with 30-second revalidation. If the chart fails to render, degrade to
a numbers table (time, equity, change) — the chart is an enhancement, the numbers
are the product.

POSITIONS SEGMENT — native cards, one per open position: symbol and side badge,
lots, open price, current price, and the P&L large and signed, with swap and
commission beneath and the open time. Live P&L updates in place with a subtle
flash on change. A totals header shows the floating P&L. Pagination at 100 rows.

HISTORY SEGMENT — closed deals as compact cards with close time, symbol, side,
lots, open/close prices and net P&L including swap and commission. A date filter
and a "Share / export" action (V2) that produces a CSV from the fetched page.

FRESHNESS HEADER — always visible: green "Live" under 2 minutes, amber
"stale — n min ago" when older, and an amber banner past 10 minutes. The SSE
lifecycle follows the web pattern exactly: reconnect with 1/2/5/15 s backoff,
three failures → 5-second polling + a "Reconnecting…" banner. This is a degraded
mode, never an error screen.

EMPTY & ERROR STATES — no open positions: "No open positions — your closed trades
are under History." A single data point: a flat line with "Not enough data yet."
A fetch failure inside a segment: a per-segment retry, never a blank screen. Never
show a number without its timestamp.

ACCESSIBILITY — every value has a native accessibility label including units, the
chart exposes a text summary for VoiceOver/TalkBack, live updates use polite
announcements and never move focus, and all touch targets are at least 44×44 pt.
```

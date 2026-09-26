# Screen 12 — Objectives & progress meters · `/accounts/{id}/objectives` · F4 · V1.1

> Copy-able UI prompt for the Alpha One trader portal.
> Extracted from `trader-flows-and-screen-prompts.md` (Part 3).
> Source spec: `alpha-one/docs/16-trader-dashboard.md` and the owning module docs.

```prompt
Build the "Objectives & progress" screen for the Alpha One trader portal
(Next.js 15, TypeScript, Tailwind, shadcn/ui). Its job is to make it impossible
for a trader to be surprised by a rule: every objective is a visual meter showing
exactly what is measured, the current value and the limit.

LAYOUT — a page header "What you're evaluated on" with the phase name, then a
2-column grid of meter cards (1 column mobile).

METER CARD — for each objective: a label, a plain-language one-liner explaining
the rule, the current value and the limit, and a horizontal progress meter.
Objectives to render (all values come from the trader account read; there is no
separate endpoint):
- **Profit target** — progress toward the target, percentage and remaining
  amount. On `target_reached`, the card switches to a green "Target reached"
  celebration state with the date it was hit.
- **Maximum (trailing) drawdown** — the floor value, the current high-water mark,
  and how much room is left, expressed both in currency and as a percentage of
  the initial balance. When the remaining room drops below 20% the card turns
  amber; below 10% red — with the wording "You are close to your drawdown
  limit", never an alarmist red flash.
- **Daily loss limit** — used today versus the limit, plus a countdown to the
  next reset at broker-server midnight, labelled "Resets at 00:00 broker time
  (in 4h 12m)".
- **Minimum trading days** — days traded versus the minimum, with a calendar-ish
  dot row for the last 14 days (a filled dot = a day with at least one trade).
- **Time remaining** — days/hours left in the evaluation window, or "No time
  limit" when the rule pack has none.
- **Consistency rule** (when configured) — the largest single-day profit as a
  share of total profit, against the configured cap.

METAPHYSICS OF THE METER — every meter shows three things at once: current value,
limit, and percentage. The fill colour is derived from the percentage but the
numeric label is always present, so the state is never colour-only. Meters animate
their fill on load and on live update, but the number never animates — it snaps.

LIVE BEHAVIOUR — metrics update over SSE; the daily-loss meter re-renders on the
`account.day_rolled` event and resets to zero with a brief "Daily limit reset"
toast. The tick-age chip applies to every number.

EMPTY & EDGE STATES — an account with no trades yet shows all meters at zero with
a "Start trading to see progress" note rather than empty bars; a
`paused`/`suspended` account shows a banner explaining that the clock is frozen
and no objectives are being evaluated; a failed account shows the final values
frozen with a "View breach report" link.

ACCESSIBILITY & MOBILE — each meter is a labelled group with the values in text,
progress uses role="progressbar" with aria-valuenow/min/max and an accessible
name, the grid is single column from 320 px, and nothing relies on hover. No
dark/light toggle in V1.
```

# Screen 19 — Position-size & drawdown calculator · `/tools/position-size` · F4 · V2.0

> Copy-able UI prompt for the Alpha One trader portal.
> Extracted from `trader-flows-and-screen-prompts.md` (Part 3).
> Source spec: `alpha-one/docs/16-trader-dashboard.md` and the owning module docs.

```prompt
Build the position-size and drawdown calculator for the Alpha One trader portal
(Next.js 15, TypeScript, Tailwind, shadcn/ui). A tool the trader uses *before*
placing a trade, to stay inside their own rules. It must be fast, keyboard-driven
and honest about being an estimate.

LAYOUT — two columns on desktop (inputs left, results right), stacked on mobile.
Max-w-4xl. The account selector at the top pre-fills equity and limits from the
selected account.

INPUTS — account equity (pre-filled, editable), instrument (a searchable select
with the tenant's allowlist; unknown symbols show "Not available on your
account"), risk per trade as a percentage of equity (a slider plus a numeric
field, default 1%), stop-loss distance in pips (numeric), and the account's daily
loss limit and maximum drawdown (pre-filled and read-only, with a "from your
rules" note).

RESULTS — a prominent primary output: **recommended lot size**, rounded down to
the broker's lot step, with the exact unrounded value in smaller text beneath.
Secondary outputs: risk amount in currency, the equity move that would trigger
the daily loss limit, the number of consecutive losing trades at this size that
would breach the daily limit, and the distance in price terms to the maximum
drawdown floor.

SAFETY WARNINGS — when the requested risk would breach a limit, the result panel
switches from neutral to amber with a specific message: "At 2.00 lots this trade
risks $2,000 — that's 40% of your daily loss limit. One loss today would leave
$3,000." and the recommended lot size is clamped to the largest safe value with
the clamp explained. When the symbol isn't in the tenant's allowlist, show
"Trading this instrument isn't permitted on your account" and refuse to compute.

BEHAVIOUR — every input recomputes on change (debounced 150 ms), the whole thing
runs client-side with no API call, and the state is reflected in the URL so a
calculation can be shared or reloaded. A "Reset" link returns to the account's
pre-filled values.

DISCLAIMER — a persistent footer: "Estimates only. Uses your equity, limits and
stop distance; does not account for spread, swap, commissions or slippage."

ACCESSIBILITY & MOBILE — all inputs are labelled with units, the slider is
keyboard-operable with arrow keys and shows its value, results are announced via
aria-live on change, and the layout is single column from 320 px. No dark/light
toggle in V1.
```

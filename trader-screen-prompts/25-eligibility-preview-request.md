# Screen 25 — Eligibility preview & request · `/payouts/request` · F7 · V1.0

> Copy-able UI prompt for the Alpha One trader portal.
> Extracted from `trader-flows-and-screen-prompts.md` (Part 3).
> Source spec: `alpha-one/docs/16-trader-dashboard.md` and the owning module docs.

```prompt
Build the payout eligibility preview and request screen for the Alpha One trader
portal (Next.js 15, TypeScript, Tailwind, shadcn/ui, react-hook-form + zod). Before
a trader requests anything they must see every check with a pass or a block reason,
and exactly what they will receive. This screen is the trust surface of the whole
platform.

LAYOUT — three stacked panels: the eligibility checklist, the amount form, and the
calculation breakdown. Max-w-3xl.

ELIGIBILITY CHECKLIST — a list where each row has an icon, a plain-language rule
name, and a pass or block state with the reason:
- Account is funded and active
- KYC verified for payouts
- No open review on your account
- Minimum trading days met ( "7 of 10" )
- Consistency rule met
- First-payout delay passed
- Next withdrawal date reached
- Amount within the minimum and maximum
- A payout method is confirmed
Each blocking row shows what to do about it and links to that action. The panel
header summarises: "9 of 9 checks passed" or "3 checks need attention". The
checklist is re-fetched from the server every time the screen opens — never trust
a cached preview, and label the fetch time.

AMOUNT FORM — a currency-formatted input, a "Max" button that fills the available
amount, and a range slider beneath it. Show the available maximum, the minimum, and
the rail fee as the amount changes. Below, the method selector (radio cards with
masked destinations and the fee per rail). A note: "Your payout is based on your
high-water mark, so trading after you request can't reduce it."

CALCULATION BREAKDOWN — an always-visible, expandable panel showing every step of
the frozen calculation, because a payout must be recomputable in a dispute:
gross profit (high-water − initial) → less already paid → trader share at the split
ratio → capped at the requested amount → less rail fee → **final amount**. Each
step on its own row with the arithmetic shown, and a line "These figures are frozen
when you submit."

SUBMIT — the "Request { amount }" button opens the shared `SensitiveDialog` with
the 2FA step-up and a typed confirmation ("Type REQUEST to confirm"). Submission is
idempotent (an idempotency key is sent; a double-submit or network retry can never
create two requests). While submitting, disable the button and show a spinner; on
success navigate to the payouts overview with a success state.

ERROR & EDGE STATES — every failure names the check and the next step, using the
server's user-safe message and never the error code:
- `payout.ineligible` (422): the checklist highlights the failing rows with the
  sub-reason ("minimum trading days", "next payout date", "KYC").
- `payout.amount_exceeds_available` (422): inline on the amount field with the
  maximum restated.
- `payout.schedule_not_due` (422): "Your next payout is available on { date }"
  with a countdown.
- `payout.method_not_confirmed` (400): "Confirm your payout method first" linking
  to the methods screen.
- `payout.invalid_address` (400): "That wallet address isn't valid for { chain }"
  inline on the method.
- `payout.risk_hold` (423/403): "Payouts are temporarily held for review" with a
  support link.
- `pay.stale_data` (409): "We couldn't get a fresh balance from the broker — try
  again in a moment" with retry.
- One active request already exists: replace the form with a link to the existing
  request instead of showing a dead button.

ACCESSIBILITY & MOBILE — the checklist is a definition list with text badges (never
colour-only), the amount input is currency-formatted with inputmode="decimal", the
dialog traps focus, and the layout is a single column from 320 px. No dark/light
toggle in V1.
```

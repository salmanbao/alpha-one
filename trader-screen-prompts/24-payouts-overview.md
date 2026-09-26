# Screen 24 — Payouts overview · `/payouts` · F7 · V1.0

> Copy-able UI prompt for the Alpha One trader portal.
> Extracted from `trader-flows-and-screen-prompts.md` (Part 3).
> Source spec: `alpha-one/docs/16-trader-dashboard.md` and the owning module docs.

```prompt
Build the payouts overview screen for the Alpha One trader portal (Next.js 15,
TypeScript, Tailwind, shadcn/ui). For a funded trader this is the most
emotionally loaded screen in the product: it must be calm, precise and never
vague about why something is or isn't available.

LAYOUT — an account selector (when there is more than one funded account), an
availability card, an active-request tracker (only when one exists), a history
table, and a methods shortcut. Max-w-5xl.

AVAILABILITY CARD — the hero. It shows:
- "Available to withdraw" with the amount in large type, computed from the
  high-water mark minus the initial balance minus prior settled payouts, times
  the profit split, minus the rail fee. Show the fee line separately so the
  number is never a surprise.
- A one-line derivation in small text: "High-water profit $4,120 − already paid
  $0 = $4,120 × 80% split − 1% fee = $3,263.04".
- "Next payout available on { date }" when a frequency window applies, or
  "Available now" when it doesn't.
- A primary "Request payout" button, and a secondary "How payouts work" link.
- The tick-age chip on the equity figure the calculation is based on, and a
  "Refresh" action that triggers a fresh broker read before re-fetching.

BLOCKED STATE — when the trader is not eligible, the card turns neutral (not red)
and lists each failing check with its plain-language reason and, where one exists,
the date it clears: "KYC not yet verified — verify now", "Minimum 10 trading days
— you have 7", "Next withdrawal available on 12 Oct", "Payouts are held for
review". Each reason links to the action that resolves it. Never show a bare
"ineligible".

ACTIVE REQUEST TRACKER — when a request exists, a horizontal status tracker:
`pending approval` → `approved` → `paid`, with the current step highlighted, the
requested amount, the method (masked), the submission date, and — for `approved` —
"Expected within { n } business days". An `on hold` request shows an amber flag
"On hold for review" with a support link. A rejected request shows the reason
class and a "Ask about this" link that opens support.

HISTORY TABLE — Date, Amount, Method (masked), Status badge, and actions
(Receipt, Details). Statuses in words as well as colour: `pending_approval`,
`approved`, `on hold`, `paid`, `rejected`. Expanding a row reveals the frozen
calculation breakdown — gross, trader share, fee, final — which is the dispute
defense and must be shown in full.

METHODS SHORTCUT — a compact list of the trader's payout methods with the default
marked and an "Add or edit methods" link. An unconfirmed method shows a
"Confirm" badge linking to the methods screen.

EMPTY STATE — a funded account with no payout history: "No payouts yet — your
first one starts here."
ERROR — inline retry with a support link; a stale-data rejection
(`pay.stale_data`, 409) shows "We couldn't get a fresh balance from the broker —
try again in a moment" with a retry button, because the correct behaviour is to be
slower, not to guess.

ACCESSIBILITY & MOBILE — the tracker is an ordered list with aria-current, the
derivation is a real definition list, the table becomes cards under 768 px, and
all amounts use tabular numerals. No dark/light toggle in V1.
```

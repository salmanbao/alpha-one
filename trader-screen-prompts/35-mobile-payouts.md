# Screen 35 — Mobile: payouts · app tab · F10 · V2.0

> Copy-able UI prompt for the Alpha One trader portal.
> Extracted from `trader-flows-and-screen-prompts.md` (Part 3).
> Source spec: `alpha-one/docs/16-trader-dashboard.md` and the owning module docs.

```prompt
Build the mobile app's payouts tab (React Native, iOS + Android) for the Alpha One
trader companion. The full payout surface — eligibility, request, methods, history
and receipts — consuming exactly the same PAY endpoints as the web portal.

LAYOUT — a tab screen with an availability card at the top, a status tracker when a
request is active, and a history list beneath. Pull-to-refresh triggers a fresh
broker read before re-fetching.

AVAILABILITY CARD — "Available to withdraw" in large type, with the fee line
separate and a one-line derivation ("High-water profit $4,120 − paid $0 = $4,120 ×
80% − 1% fee = $3,263.04"), the next-eligible date or "Available now", the
tick-age chip on the equity figure, and a primary "Request payout" button.

BLOCKED STATE — when ineligible, a neutral card listing each failing check with its
plain-language reason and the date it clears, each linking to the action that
resolves it (verify KYC, wait for trading days, confirm a method). Never a bare
"ineligible".

REQUEST FLOW — a modal screen with the eligibility checklist (each rule with pass
or block and reason), an amount field with a "Max" button and a slider, a method
selector with masked destinations and per-rail fees, and an always-visible
calculation breakdown (gross → less paid → trader share → cap → fee → final).
Submitting runs the server-side step-up (biometric unlock of the device token, then
the fresh-assertion check) and is idempotent — a double-tap or a network retry can
never create two requests. Every failure names the check and the next step using
the server's user-safe message; a stale-data rejection shows "We couldn't get a
fresh balance from the broker — try again in a moment" with a retry.

STATUS TRACKER — a native stepper (pending approval → approved → paid) with the
current step highlighted, the amount, the masked method, and the submission date.
An on-hold request shows an amber flag with a support link; a rejected request
shows the reason class and an "Ask about this" action.

METHODS — a screen listing the trader's methods with masked destinations, a
"Needs confirmation" badge where confirm-once applies, an add/edit form with
chain-specific address validation (format plus EIP-55 checksum for ERC20), version
history so the address used for any past payout stays answerable, and a security
explainer with a support shortcut.

HISTORY & RECEIPTS — a list of past requests with status badges in words as well as
colour; expanding a row shows the frozen calculation, the method version used, the
execution record and the approval trail. A "Download receipt" action on paid rows
resolves a 15-minute signed URL on tap and opens the PDF in the system viewer.

ACCESSIBILITY — the checklist uses text badges as well as colour, amounts use
tabular figures, the stepper exposes aria-current equivalents, live updates are
polite announcements, and all touch targets are at least 44×44 pt.
```

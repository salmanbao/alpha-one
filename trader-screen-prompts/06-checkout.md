# Screen 06 — Checkout · `/buy/checkout` · F2 · V1.0

> Copy-able UI prompt for the Alpha One trader portal.
> Extracted from `trader-flows-and-screen-prompts.md` (Part 3).
> Source spec: `alpha-one/docs/16-trader-dashboard.md` and the owning module docs.

```prompt
Build the checkout screen for the Alpha One trader portal (Next.js 15, TypeScript,
Tailwind, shadcn/ui, react-hook-form + zod). Money-in is the platform's critical
path: a stuck checkout is a revenue leak, so every state on this screen must be
explicit and recoverable.

LAYOUT — two columns on desktop (order summary left, payment right), single
column stacked on mobile. A thin sticky bar at the top shows the reservation
countdown.

ORDER SUMMARY (left, or top on mobile) — challenge name, account size, phase
count, a line-item list, the subtotal, any discount, and the total in large type.
Below it an expandable "What's included" with the rule summary and a link to the
full terms. A small lock icon line: "Price and coupon are held for this session."

COUPON — a text input with an "Apply" button. Valid: a green chip with the code
and the discount amount, plus a "Remove" button. Invalid: inline red "This coupon
code isn't valid." Applying is optimistic with a spinner; the code is only
reserved, never committed, until the order is created.

PAYMENT METHOD (right) — radio cards for each rail the tenant has enabled for the
selected currency: Card (Match2Pay), local methods for Pakistan/India (JazzCash,
EasyPaisa, UPI, Paytm via Interkasa), and Crypto (NOWPayments). Each card shows
the provider name, an icon, an indicative fee, and an estimated settlement time.
If a provider's circuit breaker is open, that rail renders disabled with
"Temporarily unavailable — try another method" and the alternatives stay
selectable.

TERMS — a required checkbox: "I accept the challenge agreement and the firm's
terms" with links opening in a new tab. The submit button stays disabled until
it is ticked.

RESERVATION TIMER — a countdown "Price held for 14:32" that turns amber under two
minutes. At zero the screen swaps to the expired state (below). The timer is
server-truth-driven: on focus/visibility change the client re-validates the
session rather than trusting a local clock.

PRIMARY ACTION — "Pay {total}" full width, with a spinner and a disabled state
while submitting. Submitting is idempotent: double-clicks, double-taps and network
retries must never create a second order. Show a one-time "Creating your order…"
then hand off to the provider.

ERROR & EDGE STATES —
- `checkout.session_expired` (410): full-card "Your checkout session expired.
  Please start again." with a "Back to challenges" button.
- `checkout.coupon_invalid` (400): inline on the coupon field.
- `catalog.challenge_not_found` (404): "This challenge is no longer available."
  with a link back to the catalog.
- Provider unavailable (503): inline on the rail card with the alternatives
  highlighted.
- Logged-out visit: redirect to login with `next` preserved (login-first
  checkout — no guest carts).
- Generic failure: inline error with retry and a "Contact support" button that
  pre-fills the correlation id.

ACCESSIBILITY & MOBILE — the rail picker is a radiogroup, the coupon field is
labelled and announces its result via aria-live, the countdown is announced
politely at the two-minute mark, the layout is single column from 320 px, and the
primary button is reachable without scrolling on a phone. Card data is entered on
the provider's hosted page — never render card fields on this screen.
```

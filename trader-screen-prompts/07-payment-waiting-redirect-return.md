# Screen 07 — Payment waiting / redirect return · `/buy/status` · F2 · V1.0

> Copy-able UI prompt for the Alpha One trader portal.
> Extracted from `trader-flows-and-screen-prompts.md` (Part 3).
> Source spec: `alpha-one/docs/16-trader-dashboard.md` and the owning module docs.

```prompt
Build the payment-status screen for the Alpha One trader portal (Next.js 15,
TypeScript, Tailwind, shadcn/ui). The trader has been handed to a payment
provider and has come back (or is waiting on a crypto confirmation). The single
most important job of this screen is to stop a double charge.

LAYOUT — a centred card, max-w-md, with a large status icon, a headline, one
sentence of explanation, and a single secondary action. Nothing else competes for
attention.

PRIMARY STATE — "Waiting for your payment" — an animated indeterminate spinner,
the order number, the amount, the method, and this exact prominent line: "This
page updates automatically. Do not submit twice." Under it, small: "Usually takes
a few seconds. Crypto can take up to 24 hours."

CRYPTO VARIANT — when the rail is crypto, show the deposit address (monospace,
copy button), the exact amount to send, a QR code encoding the payment URI, a
note "Send between 100% and 110% of the amount — underpayments are refunded
automatically", and a countdown to the 24-hour window expiry.

BEHAVIOUR — poll `GET /v1/trader/orders/{order_id}` (or the intent status) every
3 seconds with exponential backoff to 10 seconds, and stop the moment a terminal
state arrives. Never re-submit the payment from this screen. Use
`visibilitychange` to pause polling in a background tab. A "Refresh" text button
is available but de-emphasised.

TERMINAL STATES —
- Success: green check, "Payment received", "We're setting up your account now",
  and a "Continue" button to the order/confirmation screen. Auto-advance after
  ~2 seconds with a visible progress hint so it never feels stuck.
- Failed: amber, "That payment didn't go through", the provider's reason in plain
  language, a "Try again" button that creates a **new payment intent on the same
  order** (never a new order), and a "Choose another method" link.
- Expired: "This payment link expired", a "Start a new payment" button.
- Not retryable (409 `order.not_retryable`): "This payment can't be retried" with
  a "Contact support" button carrying the correlation id.

LOADING & ERROR — a skeleton card on first paint; a network-failure banner
"We're still checking — you can safely leave this page, we'll email you" so the
trader is never trapped; and a server-error state with retry plus a support link.

ACCESSIBILITY & MOBILE — the status region is aria-live polite, the spinner has
an accessible label, the copy buttons announce "Copied", and the layout is a
single thumb-friendly column. Never auto-redirect without a visible success state
first.
```

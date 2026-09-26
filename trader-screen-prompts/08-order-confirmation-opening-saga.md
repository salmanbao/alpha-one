# Screen 08 — Order confirmation + opening saga · `/orders/{id}` · F2/F3 · V1.0

> Copy-able UI prompt for the Alpha One trader portal.
> Extracted from `trader-flows-and-screen-prompts.md` (Part 3).
> Source spec: `alpha-one/docs/16-trader-dashboard.md` and the owning module docs.

```prompt
Build the order-confirmation and account-provisioning screen for the Alpha One
trader portal (Next.js 15, TypeScript, Tailwind, shadcn/ui). This screen is the
visible form of the purchase→provisioning saga and is the designed answer to the
firm's number-one support question: "why is my account still opening?"

LAYOUT — a success header, then a vertical steps strip, then an order summary
panel. Max-w-2xl, centred.

HEADER — green check icon, "You're in", the challenge name and account size, and
the order number in monospace with a copy button. A secondary row of buttons:
"Download invoice" (or "Invoice preparing…"), "View my accounts", "Browse more
challenges".

STEPS STRIP — the saga made visible, in order, each with its own state:
1. Payment confirmed — timestamp
2. Identity check (KYC) — only shown when the challenge requires it before
   activation; otherwise rendered as "Not required" and skipped visually
3. Broker account created (MT5) — with the account number once known
4. Credentials delivered
5. Account active
Each step shows a spinner while in progress, a green check when done, and an
amber warning when stuck. A step stuck for more than 15 minutes shows
"Taking longer than usual" plus a "Contact support" button with the saga id
already filled in.

LIVE BEHAVIOUR — subscribe to the account SSE stream (`/v1/trader/streams/{id}`)
and advance steps on `account.state_changed` without a page reload; on stream
drop, fall back to 5-second polling and show the amber "reconnect" chip. The
current step is announced via aria-live.

CREDENTIALS HANDOFF — when step 4 completes, show an inline callout: "Your MT5
login details are ready" with a "View credentials" link (the reveal itself is a
separate, 2FA-protected screen).

ORDER SUMMARY PANEL — line items, subtotal, discount, total, currency, payment
method (masked), paid-at timestamp, and a link to the challenge agreement PDF
once generated.

ERROR & EDGE STATES —
- `failed_provisioning`: red step, "We couldn't set up your account", the plain
  reason, and "Contact support" with the order and saga ids pre-filled (a refund,
  if applicable, is handled by the firm — never promise one in the UI).
- Document still generating: "Preparing…" with a spinner, never a broken link.
- Order not found / not owned (404): the "not found" page (never a 403).
- Stream lost: amber chip plus continued polling; the page still works.

ACCESSIBILITY & MOBILE — the steps strip is an ordered list with clear labels,
the current step is announced, timestamps are shown in the trader's local time
with the broker time on hover where they differ, and the layout is a single
column from 320 px. No dark/light toggle.
```

# Screen 43 — Affiliate / referral dashboard · `/referrals` · F10 · V3.0

> Copy-able UI prompt for the Alpha One trader portal.
> Extracted from `trader-flows-and-screen-prompts.md` (Part 3).
> Source spec: `alpha-one/docs/16-trader-dashboard.md` and the owning module docs.

```prompt
Build the affiliate and referral dashboard for the Alpha One trader portal
(Next.js 15, TypeScript, Tailwind, shadcn/ui). In V3 traders get a referral entry
point inside their own dashboard rather than a separate portal. This surface is
explicitly out of scope for V1 — build it only in the V3 phase.

LAYOUT — an earnings summary strip, a referral-links panel, a performance table,
and a payouts panel. Max-w-5xl. A short status banner shows the affiliate's
approval state (Pending / Approved / Suspended) where relevant.

EARNINGS SUMMARY — four headline tiles: Clicks, Signups, Conversions, and Earnings
(pending + approved + paid, each broken out). Each tile has a plain explanation on
hover/focus ("Conversions = referred traders who completed a paid order").

REFERRAL LINKS — the trader's unique referral link with a copy button, and any
coupon codes issued to them, each with its own copy button and a usage counter
("used 34 of 100"). A deep-link generator: pick a target (a specific challenge or
landing page) and an optional sub-ID, and get a tracked URL — the sub-ID is
included so the trader can tell which ad or post drove a conversion. A note
explains the attribution window and model in plain words ("we credit the last
click within 30 days").

PERFORMANCE TABLE — per link or per period: clicks, signups, conversions, earnings,
and the conversion rate. Date-range filter, sortable columns, and a CSV export.
Commission lines show their state (pending / approved / paid / reversed) with the
reversal reason where one applies, because an affiliate must be able to see why an
earning disappeared.

PAYOUTS PANEL — the affiliate's payout methods (masked, confirm-once semantics
identical to trader payout methods), a payout request above the configured minimum
threshold, and the payout history with receipts. A note that payouts are approved
and executed by the firm's finance team, with the same audit trail as trader
payouts.

MARKETING MATERIALS (V3) — a library of tenant-provided banners and copy, each with
a download button and the affiliate's tracked link pre-applied, so promotion stays
on brand.

ENTRY POINT FROM THE TRADER DASHBOARD — a small card on the trader's account home
(V3, TD-24) showing the referral link and an earnings summary, linking here. The
card is dismissible and never blocks the account metrics.

STATES — not yet an affiliate: an application panel ("Apply to refer traders")
explaining the program, the commission structure and the approval step. Pending
approval: "Your application is being reviewed." Rejected: the reason in plain
language with a support link. Empty performance data: "No clicks yet — share your
link to get started."

ERROR & EDGE STATES — a failed copy falls back to selecting the text; a failed
payout request names the blocking reason (below minimum threshold, unconfirmed
method); a 429 shows "Too many attempts — try again in { n }s".

ACCESSIBILITY & MOBILE — the links panel uses labelled read-only inputs with copy
buttons, the table becomes cards under 768 px, status badges are word + colour, and
all targets are keyboard reachable. No dark/light toggle.
```

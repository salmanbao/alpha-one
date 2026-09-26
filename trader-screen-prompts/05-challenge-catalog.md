# Screen 05 — Challenge catalog · `/buy` · F2 · V1.0

> Copy-able UI prompt for the Alpha One trader portal.
> Extracted from `trader-flows-and-screen-prompts.md` (Part 3).
> Source spec: `alpha-one/docs/16-trader-dashboard.md` and the owning module docs.

```prompt
Build the challenge catalog (storefront) screen for the Alpha One trader portal
(Next.js 15, TypeScript, Tailwind, shadcn/ui). This is the page a prospective
trader lands on from the firm's marketing site. It is the only page in the portal
that works before login — public browsing is deliberate (login is required only
at checkout).

LAYOUT — a hero strip with the tenant's headline and a single "How it works"
three-step explainer (Buy → Trade → Get funded), then a filter bar, then a
responsive grid of challenge cards (1 column mobile, 2 tablet, 3 desktop).

FILTER BAR — account-size chips (e.g. $25K / $50K / $100K / $200K), a phase-count
select (1-phase / 2-phase / instant), a sort select (Most popular / Price low→high
/ Price high→low / Newest), and a result count. Filters update the URL query so
the view is shareable and survives a refresh.

CHALLENGE CARD — account size as the headline, phase count and type, the price
(large, with the currency), a small "per month / one-off" note where relevant, a
three-line rule summary (profit target, max drawdown, daily loss), the payout
split, a "Most popular" or "New" badge where the tenant configured one, and a
primary "Choose" button. Hovering/focusing a card raises it subtly and shows a
"View rules" secondary link that opens a rules modal.

RULES MODAL — the full plain-language rule set for that challenge, grouped
(drawdown, daily loss, profit target, time limit, trading rules), with a close
button, focus trap and Escape-to-close.

PRICING & CURRENCY — display the tenant's configured currency; where a local
currency is available, show a secondary line "≈ PKR 45,000 (indicative)". The
price shown is always the tenant's current catalog price.

STATES — loading skeleton grid (8 cards); empty "No challenges match those
filters" with a "Clear filters" button; a card for a challenge that is sold out
or deactivated renders greyed with a "Currently unavailable" label and a disabled
button (never a 404 for a deactivated product the trader already has a link to);
server error shows an inline retry panel with a support link.

BEHAVIOUR — clicking "Choose" on a public (logged-out) visit redirects to
`/login?next=/buy/checkout?...`; for a signed-in trader it creates a checkout
session and navigates to checkout. Catalog data comes from `GET /v1/trader/catalog`
(public, tenant pricing and entitlements applied after login).

ACCESSIBILITY & MOBILE — the filter chips are a proper radio group, cards are
links/buttons with descriptive accessible names including size and price, the
grid reflows to one column on mobile, and the whole page is server-rendered for
fast first paint. No leaderboards, no competitions, no dark/light toggle in V1.
```

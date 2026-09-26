# Alpha One — Trader Flows & Screen Prompts

> **What this document is.** A filtered extract of the Alpha One specification
> (`alpha-one/docs/00`–`99`, `alpha-one/contracts/`) covering **only the trader
> side** — the journeys a trader takes through the product and every screen those
> journeys need. Part 1 lists the trader flows in plain language. Part 2 indexes
> every screen. Part 3 gives a **copy-able prompt per screen** — paste any one of
> them into a UI generator (v0 / Lovable / Cursor / Claude / Figma-Make) and it
> describes the screen completely enough to build against the real contracts.
>
> **Source of truth.** `docs/16-trader-dashboard.md` (TD), `docs/12-checkout-billing.md`
> (CHK), `docs/11-payout-system.md` (PAY), `docs/13-kyc.md` (KYC), `docs/07-account-lifecycle.md`
> (LCC), `docs/08-trading-bridge.md` (BRG), `docs/15-documents.md` (DOC),
> `docs/14-notifications.md` (NOT), `docs/02-identity-access.md` (AUTH),
> `docs/18-support.md` (SUP), `docs/26-mobile-apps.md` (MOB/JRN/EDU/CHT),
> `docs/24-cms-competitions.md` (CMP), `docs/23-affiliates.md` (AFF), plus
> `scripts/prd-backlog.json` for requirement IDs and `contracts/diagrams/*` for flows.
>
> **Release tags.** V1.0 / V1.1 = build now. V2 / V3 = designed but post-launch.
> The tags are taken verbatim from the backlog — do not build a V2 screen in the
> V1 sprint.

---

## Part 0 — The global design brief (apply to every screen)

Every prompt in Part 3 assumes these constraints. They are the non-negotiables
from `docs/16` §2/§3/§10 and `docs/59`:

| # | Rule | Why |
|---|---|---|
| G1 | **Next.js 15 App Router, TypeScript, Tailwind, shadcn/ui**, pnpm monorepo `web/td` + `web/shared`. Server Components (RSC) for data-heavy pages; client islands only for the live chart, payout form, checkout widget and notification center. | binding stack (`docs/01` §2) |
| G2 | **The front end never touches Postgres.** Every value comes from a GW route under `/v1/trader/*` using the HttpOnly session cookie (D64). No API keys in the browser. | FE-never-touches-PG |
| G3 | **Live data = one-way SSE** at `/v1/trader/streams/{account_id}`. Reconnect backoff 1/2/5/15 s; after 3 failures fall back to 5 s polling and show an amber "reconnect" chip. Never WebSockets. | `docs/16` §3.2 / TD-11 |
| G4 | **Freshness is always visible.** Every live number carries its timestamp: green "Live" under 2 min, amber "stale — n min ago" when older, and a "Data from {time}" banner past 10 min. Never show a number without its age. | tick honesty, EVL-52 parity |
| G5 | **Error envelope is `{code, message, correlation_id}`.** Render `message` only — **never show the `code` to the trader**. Use `code` for behaviour (retry vs. redirect vs. inline). 429 → "slow down, try in {n}s". 500 → error boundary with retry + pre-filled support ticket + Sentry id. | GW-18 |
| G6 | **One `SensitiveDialog`** for every step-up action: reason + 2FA re-auth + typed confirmation. Used by credential reveal, payout request, email change, password change, 2FA setup. Each writes a critical-tier audit row. | `docs/16` §3.5 |
| G7 | **Every dead end has a "Contact support" button** with the context pre-filled (account id, saga id, error code). | SUP-01 |
| G8 | **Money is integer minor units** end-to-end; format only at display. Never float money in state. | non-negotiable #3 |
| G9 | **PII masked by default** (email, wallet, KYC names, broker numbers). Unmask = explicit click. Credentials are shown **once**, then masked forever. | `docs/16` §10 |
| G10 | **Tenant branding everywhere** — logo, colours, product terminology and enabled features come from the tenant context, so the portal feels like the firm's own product (TD-01). | white-label |
| G11 | **Mobile-responsive from day one**; keyboard navigable; WCAG AA contrast; Lighthouse < 2.5 s on 4G. | TD-17 |
| G12 | **Out of scope in V1:** dark/light toggle, multi-language UI, leaderboards/competitions, native apps, journal, education, community, service workers. | `contracts/api/td.md` |

---

## Part 1 — The trader flows (plain language)

Nine journeys. Each one is a sequence a real trader walks through, with the
screens it touches and the one thing that journey exists to prove.

### F1 · Get in — Access & identity
The trader lands on the firm's own domain, registers or signs in through the
hosted identity provider (org-scoped per firm), proves a second factor if
enrolled, and gets a session. If they forget the password they self-serve a
reset. If they suspect someone else is in their account they can see every
active session and kill it. **This flow exists to prove access is fully
self-serve with no support ticket.**
Screens: 01 Sign-in · 02 2FA enrolment · 03 Password reset · 04 Sessions & devices.

### F2 · Choose and buy — Catalog → checkout → payment
The trader browses the firm's challenges (sizes, phases, prices, headline
rules), picks one, and opens a checkout session that **freezes the price and any
coupon** for a limited window so a mid-flow price change can never corrupt the
order. They pick a rail (card, PK/IN local method, or crypto), accept the terms,
and are handed to the provider's hosted payment page — card data never touches
our servers. A waiting screen polls the intent and tells them, loudly, not to
submit twice. **This flow exists to prove money-in is captured exactly once and
provisions an account without a human.**
Screens: 05 Catalog · 06 Checkout · 07 Payment waiting · 08 Confirmation + opening saga · 09 Orders & invoices.

### F3 · Account comes alive — The opening saga
The moment payment is captured, the account begins a visible provisioning saga:
KYC gate → broker account created at MT5 → credentials delivered → active. The
trader watches a steps strip advance in real time. This is deliberately the
answer to the firm's #1 support question — *"why is my account still opening?"* —
so it is answered by the UI rather than a ticket. If a step sticks for more than
15 minutes the strip offers support with the saga id already filled in.
Screens: 08 Confirmation + opening saga · 10 Account home · 21 KYC.

### F4 · Trade and watch — Live account, rules and progress
This is where the trader lives every day. They see each account's state badge
and headline numbers (equity, balance, open P&L, drawdown used, target progress,
time left) with an honest freshness chip, then drill into the live view: an
equity curve that appends over SSE, open positions and closed deals. Separate
screens answer "what exactly am I judged on" (objective meters, plain-language
rules) and "why did I fail" (the breach report). **This flow exists to remove
the gap between what the dashboard shows and what the rule engine sees.**
Screens: 10 Account home · 11 Account detail · 12 Objectives & progress · 13 Live trading view · 15 Rules · 16 Breach report · 17 Phase journey · 18 Performance stats · 19 Position-size calculator · 20 Economic calendar.

### F5 · Connect the terminal — Credentials
The trader reveals their MT5 login, server and password **once**, behind a 2FA
step-up, and copies them into their own terminal. After the reveal the password
is masked forever; re-issue is a support action, not a self-serve button. An
opaque link to the firm's MetaApi portal is offered for read-only access.
Screens: 14 Credentials reveal · 34 Mobile credentials.

### F6 · Prove who you are — KYC
KYC is a **gate system, not a feature**. The trader sees one status card telling
them exactly which gate is open or blocked (funding, payout), starts a hosted
verification session in an iframe, and watches state-only progress — no fake
percentages. If the provider is down or flags the case, the same flow degrades
to a manual document upload that a human at the firm reviews. **This flow exists
to prove compliance never hard-blocks a trader and never needs emailing
documents to support.**
Screens: 21 KYC status · 22 Verification session · 23 Manual upload · 36 Mobile KYC capture.

### F7 · Get paid — Payouts
Before requesting anything the funded trader sees a **checklist of every
eligibility rule** with a pass or a plain-language block reason, the available
profit computed from the high-water mark, and the exact fee and final amount.
They request behind a 2FA step-up; the request enters a human approval queue at
the firm; and they can then track it to settlement and download the receipt.
**This flow exists to prove every cent is recomputable and every failure is
explained before money moves.**
Screens: 24 Payouts overview · 25 Eligibility & request · 26 Payout methods · 27 History & receipts · 35 Mobile payouts.

### F8 · Keep the paperwork — Documents
Agreements at purchase, the funded certificate, payout receipts and invoices are
generated asynchronously as branded PDFs and listed in one centre with download
buttons and an honest "preparing…" state while the worker renders. **This flow
exists to prove the trader always has the paper, and the paper always matches
what was true at the moment it was issued.**
Screens: 28 Documents centre.

### F9 · Stay in control — Notifications, profile, support
The trader reads what happened to their accounts (email in V1, an in-app centre
in V2), manages their own profile and security, and raises a support ticket from
any dead end with context already attached. **This flow exists to prove the
trader is never stranded inside the product.**
Screens: 29 Notification centre · 30 Profile & settings · 31 Support · 37 Mobile notifications & devices.

### F10 · Beyond V1 — the satellites (V2/V3, designed, not built)
Five thinner surfaces reuse the exact same GW APIs: a native mobile companion
that mirrors the portal, a private trading journal, an education hub, a community
and support chat, and — in V3 — competitions with leaderboards and badges plus an
affiliate dashboard. None of them owns a money path. **They exist to prove the
portal's backend is the platform's only trader API.**
Screens: 32–37 Mobile · 38 Journal · 39 Education · 40 Community · 41 Competitions · 42 Badges & public profile · 43 Affiliate dashboard.

---

## Part 2 — Screen index

| # | Screen | Route | Flow | Release |
|---|---|---|---|---|
| 01 | Sign-in / register | `/login` | F1 | V1.0 |
| 02 | 2FA enrolment & backup codes | `/login/2fa` | F1 | V1.0 |
| 03 | Password reset / recovery | `/reset-password` | F1 | V1.0 |
| 04 | Sessions & devices | `/profile/security` | F1 | V2.0 |
| 05 | Challenge catalog | `/buy` | F2 | V1.0 |
| 06 | Checkout | `/buy/checkout` | F2 | V1.0 |
| 07 | Payment waiting / redirect return | `/buy/status` | F2 | V1.0 |
| 08 | Order confirmation + opening saga | `/orders/{id}` | F2, F3 | V1.0 |
| 09 | Orders & invoices | `/orders` | F2 | V1.1 |
| 10 | Account home (overview dashboard) | `/` | F3, F4 | V1.0 |
| 11 | Account detail | `/accounts/{id}` | F4 | V1.0 |
| 12 | Objectives & progress meters | `/accounts/{id}/objectives` | F4 | V1.1 |
| 13 | Live trading view | `/accounts/{id}/trade` | F4 | V1.0 |
| 14 | Credentials reveal | `/accounts/{id}/credentials` | F5 | V1.0 |
| 15 | Full rules view | `/accounts/{id}/rules` | F4 | V2.0 |
| 16 | Breach report | `/accounts/{id}/breach` | F4 | V2.0 |
| 17 | Phase journey | `/accounts/{id}/phases` | F4 | V2.0 |
| 18 | Performance stats | `/accounts/{id}/performance` | F4 | V2.0 |
| 19 | Position-size & drawdown calculator | `/tools/position-size` | F4 | V2.0 |
| 20 | Economic calendar widget | `/calendar` | F4 | V2.0 |
| 21 | KYC status & start | `/kyc` | F6 | V1.0 |
| 22 | Verification session (provider embed) | `/kyc/session/{id}` | F6 | V1.0 |
| 23 | Manual document upload | `/kyc/upload` | F6 | V1.1 |
| 24 | Payouts overview | `/payouts` | F7 | V1.0 |
| 25 | Eligibility preview & request | `/payouts/request` | F7 | V1.0 |
| 26 | Payout methods | `/payouts/methods` | F7 | V1.1 |
| 27 | Payout history & receipts | `/payouts/history` | F7 | V1.0 |
| 28 | Documents centre | `/documents` | F8 | V1.0 |
| 29 | Notification centre | `/notifications` | F9 | V2.0 |
| 30 | Profile & settings | `/profile` | F9 | V2.0 |
| 31 | Support & ticket history | `/support` | F9 | V2.0 |
| 32 | Mobile — account home | app tab | F10 | V2.0 |
| 33 | Mobile — live trade viewer | app tab | F10 | V2.0 |
| 34 | Mobile — credentials | app screen | F10 | V2.0 |
| 35 | Mobile — payouts | app tab | F10 | V2.0 |
| 36 | Mobile — KYC capture | app screen | F10 | V2.0 |
| 37 | Mobile — notifications, devices & push prefs | app screen | F10 | V2.0 |
| 38 | Trading journal | `/journal` | F10 | V2.0 |
| 39 | Education hub | `/academy` | F10 | V2.0 |
| 40 | Community & live chat | `/community` | F10 | V2.0 |
| 41 | Competitions & leaderboard | `/competitions` | F10 | V3.0 |
| 42 | Badges & public profile | `/profile/public` | F10 | V3.0 |
| 43 | Affiliate / referral dashboard | `/referrals` | F10 | V3.0 |

Each screen also has a standalone copy-able file in `trader-screen-prompts/`.

---

## Part 3 — Copy-able prompts, one per screen

Each block below is self-contained: copy it, paste it into your UI tool, and it
describes the screen, its data, its states and its rules. Mock data shapes match
the real contracts so the generated UI drops onto the GW routes without rework.

---

### SCREEN 01 — Sign-in / register · `/login` · F1 · V1.0

```prompt
Build the trader sign-in / register screen for "Alpha One", a white-label prop-firm
platform (Next.js 15 App Router, TypeScript, Tailwind, shadcn/ui). This screen is
tenant-branded: logo, colours and product wording come from the tenant context so it
feels like the firm's own product, not a generic SaaS.

LAYOUT — centred auth card, max-w-md, on a neutral background with a subtle brand
gradient. Two tabs at the top: "Sign in" (default) and "Create account". Below the
card: a footer line with links to Terms, Privacy and "Contact support".

SIGN-IN TAB — email field (type=email, autocomplete=username, required), password
field with show/hide toggle, "Forgot password?" link to /reset-password, a
"Sign in" primary button (full width, loading state on submit), and an optional
row of SSO buttons if the tenant has them configured.

CREATE-ACCOUNT TAB — email, password, confirm password, a required checkbox
accepting the firm's Terms and Privacy Policy (links open in a new tab), and a
"Create account" button. Show an inline password-policy hint under the password
field: minimum 10 characters, mixed case, a number, and not one of the last 5 used.

BEHAVIOUR — authentication is delegated to the hosted identity provider (ZITADEL
Hosted Login, org-scoped for this firm's domain); render the provider hand-off as
a full-card "Taking you to secure sign-in…" state with a spinner and a "Cancel"
link that returns to the form. On return, exchange the code server-side and
materialise the session. After a successful sign-in, redirect to the `next` query
parameter if present, otherwise to the account home `/`.

ERROR & EDGE STATES (all inline, never a raw dialog):
- Invalid credentials: inline red text under the form, "Those details don't match an account. Try again." — never reveal whether the email exists.
- Rate limited (429): amber inline banner "Too many attempts. Try again in {n} seconds." with a countdown.
- Account locked: "This account is temporarily locked after too many attempts. Reset your password or contact support."
- Tenant not found (404 on the host): a full-page "Site not found" state — 404, not 403 — with a support link.
- Session expired (401 on any call while on another page): a full-screen re-login card that preserves the page the trader was on and restores their form input afterwards.
- Idle timeout (30 minutes for traders): a modal "You've been signed out for security. Sign in to continue." with a single "Sign in" button.

2FA — if the identity has a second factor, after the password step show a 6-digit
code screen: six separate single-character inputs with auto-advance and
paste-support, a "Use a backup code instead" link, a "Verify" button, and a
"Resend / having trouble?" link to support. Show a 30-second cooldown on resend.

ACCESSIBILITY & MOBILE — fully keyboard navigable with a visible focus ring, all
inputs labelled, error text tied to inputs with aria-describedby, the tabs are a
proper tablist with arrow-key support, and the layout is single-column and
thumb-friendly from 320 px up. Do not add a dark/light toggle (out of scope for V1).
```

---

### SCREEN 02 — 2FA enrolment & backup codes · `/login/2fa` · F1 · V1.0

```prompt
Build the two-factor authentication enrolment screen for the Alpha One trader
portal (Next.js 15, TypeScript, Tailwind, shadcn/ui). It is shown the first time a
trader enables 2FA from their profile, and re-shown whenever they add or reset a
factor. The whole flow runs inside one shared `SensitiveDialog` shell: a title, a
one-line reason ("Confirm it's you to change your security settings"), the 2FA
step, and a typed confirmation.

LAYOUT — three sequential steps in a single card with a step indicator (1 Set up ·
2 Verify ·3 Save backup codes), max-w-lg.

STEP 1 — "Set up your authenticator": a QR code (rendered as an SVG, ~200 px) for
the TOTP secret, the secret shown as monospace text with a copy button and a
"Can't scan? Enter this key manually" disclosure, and a plain-language line:
"Open Google Authenticator, Authy or 1Password and scan this code."

STEP 2 — "Verify": a 6-digit code input (six single-character boxes, auto-advance,
paste support) and a "Verify and enable" button. While pending show a spinner on
the button; on a wrong code show an inline "That code isn't right. Codes change
every 30 seconds — try the current one." with a live countdown to the next code
window. On success show a green success state with a check icon and auto-advance.

STEP 3 — "Save your backup codes": a 2×5 grid of 10 monospace codes, buttons for
"Copy all" and "Download as .txt", a required checkbox "I have saved these codes
somewhere safe", and an "Finish" button that is disabled until the box is ticked.
Warn clearly: "Each code works once. If you lose your authenticator these are the
only way back in."

EXTRA STATES — a "Regenerate backup codes" action (also step-up protected) that
invalidates the old codes after confirmation; a status line "Backup codes
remaining: {n}"; and a read-only summary card for users already enrolled showing
enrolment date, method (TOTP), and codes remaining, with "Remove 2FA" as a
destructive, step-up-protected action that warns it will sign out other devices.

ACCESSIBILITY & MOBILE — each step is a labelled region, focus moves to the new
step's heading on advance, the QR has a text alternative (the manual key), all
buttons have accessible names, and the code inputs use inputmode="numeric" with
autocomplete="one-time-code" so mobile keyboards and SMS autofill work. Responsive
single column from 320 px. No dark/light toggle in V1.
```

---

### SCREEN 03 — Password reset / recovery · `/reset-password` · F1 · V1.0

```prompt
Build the self-serve password reset flow for the Alpha One trader portal
(Next.js 15, TypeScript, Tailwind, shadcn/ui). Three states on one route,
tenant-branded, no support ticket required at any point.

STATE A — "Reset your password" (default): an email field, a "Send reset link"
button, and a line "We'll email you a link to choose a new password. The link
works once and expires in 60 minutes." Below the form: "Remembered it? Back to
sign in."

STATE B — "Check your email": shown immediately after submit, always identical
whether or not the address exists (enumeration resistance) — a mail icon, the
masked address the link was sent to, a "Resend email" button with a 60-second
cooldown, a "Change email address" link back to State A, and a hint "Nothing
after a few minutes? Check spam, then contact support."

STATE C — "Choose a new password": reached from the emailed link (validates the
token server-side). Fields: new password with show/hide, confirm new password,
and a live checklist that ticks off as the trader types: at least 10 characters,
upper and lower case, a number, not one of your last 5 passwords, and not found
in a known breached-password list. A "Save and sign in" button.

BEHAVIOUR — the reset itself is handled by the hosted identity provider; the
portal only initiates and consumes it. On success, sign the trader in and land on
the account home with a success toast "Password updated. Other devices have been
signed out." — because a credential change revokes every other session, and the
trader must be told that happened.

ERROR & EDGE STATES — expired or already-used link: a full-card state "This reset
link has expired." with a "Send a new link" button. Rate limited: inline amber
"Too many requests — try again in {n} seconds." Password rejected by policy:
inline field error quoting the specific failing rule. Network/server failure:
inline error with a retry button and a "Contact support" link carrying the
correlation id.

ACCESSIBILITY & MOBILE — single column, max-w-md, large tap targets, the
checklist is an aria-live region so screen-reader users hear each rule pass, and
the whole flow works from 320 px. Do not add a dark/light toggle.
```

---

### SCREEN 04 — Sessions & devices · `/profile/security` · F1 · V2.0

```prompt
Build the "Sessions & devices" security screen for the Alpha One trader portal
(Next.js 15, TypeScript, Tailwind, shadcn/ui). It answers one question: who else
is in my account, and how do I get them out.

LAYOUT — a page inside the profile section: breadcrumb "Profile / Security", a
heading "Where you're signed in", and a table (cards on mobile) of active
sessions.

SESSION ROW — device label (e.g. "Ali's iPhone", "Chrome on Windows"), a
"Current session" badge on this one, approximate location (city, country — or
"Unknown"), "Last active {relative time}", "Signed in {date}", and a "Sign out"
button. Above the table: a count "3 active sessions" and a destructive
"Sign out of all other devices" button that opens the shared `SensitiveDialog`
(reason + 2FA step-up + typed confirmation) before executing.

BELOW THE TABLE — two short explainer cards:
- "Changing your password signs out every other device automatically."
- "Lost your phone? Sign out of all devices, then change your password."
Each with a link to the relevant action.

EMPTY STATE — only the current session: "You're signed in on this device only."

STATES — loading skeletons for the table; a per-row spinner while revoking; a
success toast "Signed out of {device}"; an optimistic row removal that reverts
with an inline error and a retry button if the call fails; a 429 state showing
"Too many attempts — try again in {n} seconds."

DATA — `GET /v1/auth/sessions` and `DELETE /v1/auth/sessions/{id}` via the GW with
the session cookie; never expose raw token identifiers in the DOM.

ACCESSIBILITY & MOBILE — the table becomes stacked cards under 640 px, the
destructive action has a confirmation dialog and is never the default focus, and
every row action is reachable by keyboard. No dark/light toggle in V1.
```

---

### SCREEN 05 — Challenge catalog · `/buy` · F2 · V1.0

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

---

### SCREEN 06 — Checkout · `/buy/checkout` · F2 · V1.0

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

---

### SCREEN 07 — Payment waiting / redirect return · `/buy/status` · F2 · V1.0

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

---

### SCREEN 08 — Order confirmation + opening saga · `/orders/{id}` · F2/F3 · V1.0

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

---

### SCREEN 09 — Orders & invoices · `/orders` · F2 · V1.1

```prompt
Build the order and invoice history screen for the Alpha One trader portal
(Next.js 15, TypeScript, Tailwind, shadcn/ui). Every purchase the trader has ever
made, in one place, with the paperwork attached.

LAYOUT — a page header "Orders & invoices" with a count, a filter row, and a
table (cards on mobile). Server-rendered; no live stream needed.

FILTERS — status chips (All / Paid / Provisioning / Fulfilled / Failed /
Abandoned), a date-range picker (last 30 / 90 days / all time), and a text search
on order number or challenge name. Filters write to the URL query.

TABLE COLUMNS — Date, Order no. (monospace), Challenge (name + size), Amount
(with currency), Method (masked), Status badge, and an actions cell.

STATUS BADGES — colour-coded and labelled in words, never colour alone:
`open` grey "Awaiting payment", `paid` blue "Paid", `provisioning` amber
"Setting up", `fulfilled` green "Complete", `failed_provisioning` red "Setup
failed", `abandoned` grey "Abandoned".

ROW ACTIONS — "Download invoice" (V1.1), "Download receipt", "Retry payment"
(only when the order is `open` with a dead intent), "View account" (when
fulfilled and an account exists), and "Contact support" (always, as the last
item in an overflow menu).

ROW EXPANSION — clicking a row expands a detail panel: the full line items, the
frozen price snapshot (base, FX rate if converted, fee model, total), the payment
attempts (each with provider, masked reference, amount and outcome), the coupon
used if any, the linked account id, and the invoice/receipt download links.

DOCUMENT STATES — "Preparing…" with a spinner while the PDF worker is still
rendering (409 `receipt.not_ready`); "Download" once generated; an inline retry
if a signed URL fails to resolve. Signed URLs are 15-minute and fetched on click,
never embedded in the page.

EMPTY STATE — "No orders yet" with a "Browse challenges" primary button.
LOADING — skeleton table rows. ERROR — inline banner with retry and support link.

ACCESSIBILITY & MOBILE — the table becomes stacked cards under 768 px with the
status badge first, all badge colours meet AA contrast and are accompanied by
text, and the expansion is a proper disclosure widget with aria-expanded.
```

---

### SCREEN 10 — Account home (overview dashboard) · `/` · F3/F4 · V1.0

```prompt
Build the account home / overview dashboard — the landing page after sign-in —
for the Alpha One trader portal (Next.js 15, TypeScript, Tailwind, shadcn/ui).
This is the screen a funded trader opens every day. It must answer "where do I
stand?" in under five seconds.

LAYOUT — a top bar with the tenant logo, an account switcher (when the trader has
more than one account), the trader's avatar menu, and a global freshness chip.
Below: a responsive grid of account cards (1 column mobile, 2 desktop), then a
secondary row of widgets.

ACCOUNT CARD — the core component of the whole portal:
- Header: program name, account size, and the **state badge** (one component,
  reused everywhere): `opening` (spinner + a mini steps strip), `evaluating`
  (phase + "Phase 1 of 2"), `funded` (green "Funded"), `paused`/`suspended`
  (amber with a reason class and a support link), `failed`/`breached` (red, with
  the rule name and a "View report" link), `closed` (grey, documents only).
- Metric row: Equity (large), Balance, Open P&L (green/red), Drawdown used
  (e.g. "2.10% of 6.00%"), Daily loss used, Target progress (e.g. "68% of
  $8,000"), Time left ("27 days").
- A **tick-age chip** on the card footer: green dot + "Live" under 2 minutes;
  amber dot + "stale — 6 min ago" when older; a card-level banner "Data from
  14:02" past 10 minutes. Never render a number without its age.
- Footer actions: "Open" (account detail), "Live view", "Payout", "Credentials".

SECONDARY WIDGETS (V1 minimal, V2 configurable) — a compact equity sparkline for
the selected account (last 24 h, appended live over SSE), a "Next payout"
eligibility teaser with the available amount and next eligible date, a documents
"new" badge count, and a support shortcut. Widgets are individually hideable and
rearrangeable in V2 — build the grid so that is a data change, not a rewrite.

LIVE BEHAVIOUR — subscribe to SSE for the selected account; update the metrics
and sparkline in place without a reload; on stream loss fall back to 5-second
polling and show the amber "reconnect" chip. Server-side revalidation is 30
seconds, and authenticated pages are never CDN-cached.

EMPTY STATE — no accounts: a friendly panel "You don't have any accounts yet"
with a "Browse challenges" primary button and a "How it works" link.
PARTIAL FAILURE — if one card's fetch fails while the page renders, show that
card as a skeleton with its own retry button; never break the whole page.
ERROR — full-page error boundary with retry, a pre-filled support ticket and the
Sentry id shown.

ANNOUNCEMENTS (V2) — a dismissible tenant announcement banner slot at the top,
driven by tenant config, never blocking the metrics.

ACCESSIBILITY & MOBILE — cards are semantic articles with headings, the state
badge always includes a text label, the metric grid reflows to two columns on
phones, all interactive elements are keyboard reachable, and first contentful
paint stays under 2.5 s on a 4G connection (server-render the metrics, hydrate
only the sparkline and switcher). No dark/light toggle in V1.
```

---

### SCREEN 11 — Account detail · `/accounts/{id}` · F4 · V1.0

```prompt
Build the account detail screen for the Alpha One trader portal (Next.js 15,
TypeScript, Tailwind, shadcn/ui). One account, everything about it, with a clear
route into every sub-surface.

LAYOUT — a header block, a metrics grid, a tab bar, and a state-history timeline.
Max-w-6xl.

HEADER — program name and account size, the state badge (the same component used
on the home cards, with the same semantics), the phase ("Phase 1 of 2"), the
broker and a masked broker account number, and a freshness chip. A primary
action cluster on the right: "Live view", "Request payout" (only when funded and
eligible), "Credentials", and an overflow menu with "Documents", "Rules",
"Contact support".

METRICS GRID — Equity, Balance, Open P&L, High-water mark, Trailing drawdown
(bps and %), Daily loss used / limit, Profit target progress, Trading days
completed / minimum, and Time left. Each tile shows the value, a label, and where
relevant a thin progress bar with the limit marked. All values carry the tick-age
chip treatment.

TAB BAR — "Overview" (metrics + history), "Live view" (positions, deals, equity
chart), "Objectives" (the meters), "Rules" (plain language), "History" (state
transitions). Tabs are proper ARIA tabs with arrow-key navigation and the active
tab is reflected in the URL so the view is shareable and reload-safe.

STATE HISTORY TIMESTAMPED LIST — every transition with from-state, to-state,
trigger, actor (system / firm / trader) and timestamp in the trader's local time
( broker time on hover where they differ ). The most recent first, "Load more"
pagination. This is the trader-visible half of the append-only state history.

STATE-DRIVEN CONTENT — the screen adapts to the account state:
- `opening`: a prominent steps strip (payment → KYC → broker account → active)
  with the "taking longer than usual?" support escape hatch.
- `evaluating`: objectives front and centre.
- `funded`: payout call-to-action with the available amount.
- `paused`/`suspended`: an explanation panel with the reason class and a support
  link; payout actions hidden.
- `failed`/`breached`: a red panel naming the rule, the observed value versus the
  threshold, and a "View breach report" link.
- `closed`: documents only, all actions disabled with a plain explanation.

DATA — `GET /v1/trader/accounts/{id}` (server component) plus the SSE stream for
live updates. A cross-tenant or unknown id returns the "not found" page — never a
403.

ACCESSIBILITY & MOBILE — one heading per section, the metric grid collapses to two
columns on phones, tabs become a scrollable tablist, and the timeline is a
semantic ordered list. No dark/light toggle in V1.
```

---

### SCREEN 12 — Objectives & progress meters · `/accounts/{id}/objectives` · F4 · V1.1

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

---

### SCREEN 13 — Live trading view · `/accounts/{id}/trade` · F4 · V1.0

```prompt
Build the live trading view for the Alpha One trader portal (Next.js 15,
TypeScript, Tailwind, shadcn/ui). It is the trader's window onto their broker
account: an equity curve that moves, the positions they hold, and the deals they
have closed.

LAYOUT — a header with the account name, the state badge and the freshness chip;
then the equity chart panel; then a tab bar (Positions / History / Orders) with
its table. Max-w-6xl.

EQUITY CHART PANEL — a line/area chart of equity over the selected range (1H /
1D / 1W / 1M / All). In V1.0 render with plain SVG or canvas (no chart library
dependency); the component boundary must allow swapping in TradingView
Lightweight Charts in V2 without touching the data layer. The chart hydrates with
the last 60 points and appends live points from SSE. Draw the high-water mark as
a dashed reference line and the drawdown floor as a red dashed line when the rule
pack has one. Full history is a server-fetched range request with 30-second
revalidation — never block first paint on it. Show the y-axis in the account
currency and the x-axis in the trader's local time.

FRESHNESS — the panel header carries the tick-age chip: green "Live" under 2
minutes, amber "stale — n min ago" when older, and an amber banner "Data from
{time}" past 10 minutes. If the SSE stream drops three times, switch to 5-second
polling and show an amber "Reconnecting…" chip — this is a degraded mode, not an
error screen.

POSITIONS TAB — a table of open positions: Symbol, Side (buy/sell badge), Lots,
Open price, Current price, S/L, T/P, P&L (coloured and signed), Swap, Commission,
Opened (broker time). Totals row for floating P&L. Pagination at 100 rows per
page. Live P&L updates in place; a row flashes subtly on change rather than
re-mounting.

HISTORY TAB — closed deals: Close time, Symbol, Side, Lots, Open, Close, P&L,
Swap, Commission, and a ticket number. Date-range filter and a "Export CSV"
button (V2) that generates the file client-side from the fetched page.

ORDERS TAB — pending orders (V2). In V1 render the tab with an honest "Working
orders aren't tracked yet" empty state rather than hiding the tab.

EMPTY & ERROR STATES — no open positions: "No open positions" with a line "Your
closed trades appear under History." Chart with a single point or none: a flat
line with "Not enough data yet". Fetch failure inside the panel: a per-panel
skeleton with its own retry, never a broken page. Never show a number without its
timestamp.

ACCESSIBILITY & MOBILE — tables become card lists under 768 px, the chart has a
text summary ("Equity up 2.4% today, high $104,155, low $103,980") for screen
readers, live updates are polite aria-live regions and never steal focus, and the
tabs are a proper ARIA tablist. No dark/light toggle in V1.
```

---

### SCREEN 14 — Credentials reveal · `/accounts/{id}/credentials` · F5 · V1.0

```prompt
Build the broker credentials screen for the Alpha One trader portal (Next.js 15,
TypeScript, Tailwind, shadcn/ui). It is the most protected screen in the portal:
it hands the trader the keys to a real MT5 account, exactly once.

LAYOUT — a warning-toned header, three credential rows, an actions cluster, and
a help panel. Max-w-2xl.

HEADER — a lock/shield icon, "Your MetaTrader 5 credentials", and one sentence:
"These log in to your trading account at the broker. Keep them private — our
team will never ask you for them."

CREDENTIAL ROWS — three rows, each with a label, a monospace value, and an
action:
1. **Account number** (login) — visible by default, with a copy button.
2. **Server** — visible by default, with a copy button.
3. **Password** — masked as `••••••••••` by default with a "Reveal" button. The
   trading password and the investor password are two separate rows; the investor
   (read-only) password can be revealed independently.

REVEAL FLOW — clicking "Reveal" opens the shared `SensitiveDialog`: a one-line
reason ("Confirm it's you to reveal your trading password"), the 2FA step-up
(re-authentication, `prompt=login&max_age=300`), and a typed confirmation
("Type REVEAL to continue"). On success the password renders once in monospace
with a copy button and a countdown ("This disappears in 60s" — auto-mask on
timer, on blur, and on navigation). The response is never cached (no-store) and
is never written to localStorage or IndexedDB. After the first reveal the row
returns to masked permanently: re-issuing a password is a support action, not a
button, so show "Need a new password? Contact support" with the account id
pre-filled.

METAAPI PORTAL LINK — a secondary action "Open read-only portal" that opens the
firm's opaque hosted MetaApi URL in a new tab. Never construct a broker URL from
raw credentials, and never expose anything beyond this opaque link.

HELP PANEL — three short steps: "1. Open MetaTrader 5. 2. File → Login to Trade
Account. 3. Enter the server, login and password." Plus a link to the firm's
setup guide and a "Contact support" button.

ERROR & EDGE STATES — step-up expired (`authz.step_up_required`, 403): the dialog
shows "That took too long — confirm again to continue" and re-prompts, without
losing the dialog context. Account not active: the screen explains credentials
appear once the account is active and links to the opening saga. Account not
found or not owned: the "not found" page. Rate limited: inline "Too many
attempts — try again in {n}s".

ACCESSIBILITY & MOBILE — the reveal button is never auto-focused, the dialog
traps focus and closes on Escape, the copy buttons announce "Copied", values use
`aria-label` including which credential they are, and the layout is a single
column from 320 px. No dark/light toggle in V1.
```

---

### SCREEN 15 — Full rules view · `/accounts/{id}/rules` · F4 · V2.0

```prompt
Build the "Your rules" screen for the Alpha One trader portal (Next.js 15,
TypeScript, Tailwind, shadcn/ui). Beyond the objective meters, this is the
complete, plain-language rule set for this specific account — the expectations
made explicit so nothing is a surprise.

LAYOUT — a page header "Your rules" with the account name and a note "These are
the rules frozen on your account at purchase. They don't change mid-account.",
then grouped rule sections, then a footer with the agreement PDF.

RULE GROUPS — render as an accordion or card list, each group with an icon and a
one-line summary, expanding to individual rules:
- **Drawdown** — maximum/trailing drawdown type, the floor value, how it is
  calculated, whether it trails the high-water mark.
- **Daily loss** — the daily limit, how a "day" is defined (broker-server
  midnight, named timezone), and when it resets.
- **Profit target** — the target and whether it is per phase.
- **Time limits** — minimum trading days, maximum calendar duration, what happens
  at expiry.
- **Consistency** (when configured) — the rule in plain words, e.g. "no single
  trading day may contribute more than 40% of total profit".
- **Trading restrictions** — weekend/holding-overnight rules, news-event
  restrictions, prohibited instruments, expert-advisor/copy-trading rules,
  minimum trade duration, maximum lot size, hedging rules.
Each rule row shows the threshold value and, where the platform already tracks
it, the trader's current value next to it ("Used today: 34% of 5%").

LANGUAGE RULES — every rule is written in plain language with no jargon; where a
term is unavoidable ("high-water mark", "trailing drawdown") it gets a small
info tooltip with a one-sentence definition. Tone is explanatory, never legalistic.

FOOTER — "Download the full challenge agreement (PDF)" linking to the document
signed-URL route, plus "Questions about a rule? Contact support" with the account
id pre-filled.

STATES — loading skeletons per group; a rule group that does not apply to this
account is omitted entirely rather than shown as "N/A"; a server error shows an
inline retry. If the terms snapshot is missing (a data bug), show an honest
"We couldn't load your frozen terms — contact support" panel rather than
rendering the current template, because the template may have changed since
purchase.

ACCESSIBILITY & MOBILE — the accordion is a proper disclosure pattern with
aria-expanded, tooltips are keyboard-accessible, groups are semantic sections
with headings, and everything reflows to one column on phones. No dark/light
toggle in V1.
```

---

### SCREEN 16 — Breach report · `/accounts/{id}/breach` · F4 · V2.0

```prompt
Build the breach report screen for the Alpha One trader portal (Next.js 15,
TypeScript, Tailwind, shadcn/ui). It is shown when an account fails. The tone
requirement is explicit and non-negotiable: **factual and non-accusatory** — this
is a document a trader screenshots and disputes, so it must be evidence, not a
scolding.

LAYOUT — a status header, an evidence panel, a "what happened next" panel, and an
actions footer. Max-w-3xl.

STATUS HEADER — a neutral (not celebratory, not alarming) icon, "Account breached",
the program name, the breach timestamp in the trader's local time **and** broker
time side by side (they differ, and the difference matters in a dispute), and the
verdict/reference id in monospace.

EVIDENCE PANEL — the heart of the screen: a small table with exactly three
columns — **Rule**, **Threshold**, **Observed** — plus a "When" column.
Example rows: "Maximum drawdown | 6.00% of initial balance | 6.34% | 14:02 broker
time"; "Daily loss limit | 5.00% | 5.21% | 09:47 broker time". Below the table a
one-sentence plain-language explanation of the rule that was broken and how the
observed value was derived (e.g. "Your trailing drawdown is measured from your
high-water mark of $104,155, reached at 13:58."). Where the platform holds an
equity snapshot series, render a small chart of the minutes around the breach
with the threshold line drawn in — the visual is the evidence.

WHAT HAPPENED NEXT — a short ordered list of what the platform did, in plain
words: open positions were closed at market, trading was disabled at the broker,
the account moved to `failed`, a certificate/notice document is available, and
whether any in-flight payout was placed on hold.

ACTIONS — "Download breach notice (PDF)", "View my other accounts", and a
prominent "Appeal or ask a question" button that opens support as a ticket with
the account id, the verdict id and the rule id pre-filled (the dispute channel is
the product, not an email address).

STATES — an account that failed by **time-limit expiry** rather than a breach
renders the same shell with a different headline ("Evaluation period ended") and
an evidence panel showing the time rule, the start date and the expiry date. A
breach that was overridden by the firm shows a green "This breach was reversed by
{ firm } on { date }" banner with the reason. Loading, not-found (404, never 403)
and error states as elsewhere in the portal.

ACCESSIBILITY & MOBILE — the evidence table is a real table with header scope,
numbers are right-aligned and tabular, the timestamps are machine-readable with
human labels, and the layout is a single column from 320 px. No dark/light toggle.
```

---

### SCREEN 17 — Phase journey · `/accounts/{id}/phases` · F4 · V2.0

```prompt
Build the phase journey screen for the Alpha One trader portal (Next.js 15,
TypeScript, Tailwind, shadcn/ui). For multi-phase challenges it shows the whole
arc — passed phases, the current one, and what's next — so product-level progress
is obvious.

LAYOUT — a page header "Your journey" with the program name, then a horizontal
stepper (vertical on mobile), then a detail panel for the selected phase.

STEPPER — one node per phase in ordinal order. Each node shows the phase name,
its state, and a one-line result:
- **Passed** (green check): phase name, the profit achieved versus the target,
  and the date it completed.
- **Current** (highlighted ring): phase name, the live progress toward the
  target, and days remaining.
- **Next** (outlined, muted): phase name and a one-line description of what
  changes (e.g. "tighter drawdown, higher profit split").
- **Failed** (red): the phase and the reason, with a link to the breach report.
Connectors between nodes are coloured by progress. The current node is
announced via aria-live when it changes.

DETAIL PANEL — selecting a node opens a panel for that phase: its rule summary
(target, drawdown, daily loss, minimum days), its start and end dates, the
metrics at the moment it ended (final equity, high-water mark, profit, trading
days), and — for the current phase — the live meters linked to the objectives
screen.

LINEAGE NOTE — where a phase was completed by spawning a new account, show a
small "continued in a new account" note with a link to that account, so the
trader understands why the account id changed. This is the visible form of
`parent_account_id`.

EMPTY & EDGE STATES — a single-phase challenge renders the stepper with one node
and a line "This is a one-phase challenge."; loading skeletons; a not-found or
cross-tenant id returns the not-found page.

ACCESSIBILITY & MOBILE — the stepper is an ordered list with `aria-current="step"`
on the active node, nodes are buttons that move focus to the detail panel, and
the layout stacks vertically from 320 px. No dark/light toggle in V1.
```

---

### SCREEN 18 — Performance stats · `/accounts/{id}/performance` · F4 · V2.0

```prompt
Build the performance statistics screen for the Alpha One trader portal
(Next.js 15, TypeScript, Tailwind, shadcn/ui). Basic analytics computed from the
trader's own closed deals — enough to be useful, clearly labelled as indicative.

LAYOUT — a date-range selector (7 / 30 / 90 days / all), a summary strip of four
headline numbers, a breakdown table, and an equity/drawdown chart. Max-w-6xl.

HEADLINE NUMBERS — Win rate (%), Average win, Average loss, Profit factor. Each
tile shows the value, the label, and a one-line plain explanation on hover/focus
("Profit factor = gross profit ÷ gross loss. Above 1.0 is profitable.").

SECONDARY METRICS (V2 advanced) — Sharpe ratio, Sortino ratio, Calmar ratio and
maximum drawdown duration, each with the same explanatory tooltip and a
computation note ("computed from daily closes, 365-day basis").

BREAKDOWN TABLE — per symbol: trades, win rate, net P&L, average win, average
loss, largest win, largest loss, total commission + swap. Sortable columns, with
the sort state in the URL. A totals row at the bottom.

CHART — a combined equity curve with a drawdown sub-chart underneath, sharing the
x-axis, rendered with the same chart component boundary as the live view so the
V1 SVG/canvas implementation and the V2 chart-library swap stay in one place.

HONESTY RULES — every metric is computed from closed deals only; open positions
are excluded and the screen says so. Where there are too few trades for a metric
to be meaningful (e.g. fewer than 30 closed trades for a Sharpe ratio), show the
metric as "—" with a tooltip "Needs at least 30 closed trades", never a fabricated
number. A footer note: "Statistics are indicative and computed from broker data
synced to the platform. They are not a statement of account."

EMPTY STATE — no closed trades: an illustration-free, plain panel "No closed
trades in this period" with the range selector highlighted.
ERROR — per-panel retry; never a blank page.

ACCESSIBILITY & MOBILE — headline tiles are semantic with text values (never
colour-only), the table becomes cards under 768 px, sortable headers are real
buttons with aria-sort, and the chart has a text summary for screen readers.
```

---

### SCREEN 19 — Position-size & drawdown calculator · `/tools/position-size` · F4 · V2.0

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

---

### SCREEN 20 — Economic calendar widget · `/calendar` · F4 · V2.0

```prompt
Build the economic calendar screen for the Alpha One trader portal (Next.js 15,
TypeScript, Tailwind, shadcn/ui). It helps the trader plan around high-impact news
events without leaving the platform, and tells them plainly when trading is
restricted around an event.

LAYOUT — a page header "Economic calendar", a filter row, and a day-grouped list
of events. Max-w-4xl.

FILTER ROW — impact chips (All / High / Medium / Low), a currency multi-select
(USD, EUR, GBP, JPY, PKR, INR…), and a "Today / This week" toggle. Filters write
to the URL.

EVENT ROW — time (in the trader's local timezone, with the source timezone on
hover), an impact badge (High = filled red, Medium = amber, Low = grey — always
accompanied by the word, never colour alone), the country flag, the event name,
and the previous / forecast / actual values where published. Past events dim and
show the actual.

NEWS-RULE INTEGRATION — when the trader's rule pack restricts trading around news
events, affected events get a distinct marker and an explanatory line: "Trading is
restricted from 14:30 to 15:30 broker time around this release." The marker must
be understandable at a glance and also available as text.

DAY GROUPING — events grouped under sticky date headers with the day name and
date, "no events" days collapsed to a single muted line rather than an empty gap.

STATES — loading skeletons; a provider-outage state "The calendar is temporarily
unavailable" with a retry (never a silent empty list); an empty filter result with
a "Clear filters" button.

ACCESSIBILITY & MOBILE — rows are list items, impact badges include text, the
filter chips are a real group, timezone handling is explicit and labelled, and
the layout is a single column on phones. No dark/light toggle in V1.
```

---

### SCREEN 21 — KYC status & start · `/kyc` · F6 · V1.0

```prompt
Build the KYC status screen for the Alpha One trader portal (Next.js 15,
TypeScript, Tailwind, shadcn/ui). KYC is a gate system, not a feature: this screen
exists to tell the trader, in one glance, what is verified, what is blocking them,
and the single next action that unblocks it.

LAYOUT — a status hero, a gates panel, a next-action panel, and a history list.
Max-w-3xl.

STATUS HERO — a large state card driven by the verification state machine
(`not_started`, `pending`, `in_review`, `approved`, `rejected`,
`needs_resubmission`, `expired`). Each state has its own icon, colour, headline
and one-sentence explanation written for a trader, never for a compliance officer:
- `not_started`: "Verify your identity to unlock funding and payouts."
- `pending`: "Verification in progress — we'll email you the moment it's decided."
- `in_review`: "Our team is reviewing your documents. Most reviews finish within
  24 hours."
- `approved`: green "You're verified" with the verification date.
- `rejected`: "We couldn't verify your identity" with the **reason class only**
  (e.g. "document unreadable") and a clear path to try again.
- `needs_resubmission`: "We need a clearer photo of your document" with a
  "Resubmit" button.
- `expired`: "Your verification session expired" with "Start again".

GATES PANEL — three rows showing which gates this verification controls, each
with a pass/pending/blocked badge: **Funding** (activating a challenge account),
**Payouts** (receiving money), and — where configured — **Purchases**. A blocked
gate links directly to the action that clears it.

NEXT-ACTION PANEL — a single, unambiguous primary button whose label changes with
the state: "Verify now" / "Continue verification" / "Resubmit documents" /
"Upload documents manually" / nothing when approved. Below it, a short plain
description of what will happen: "You'll take a photo of your ID and a selfie. It
takes about two minutes and happens right here in your browser."

CONSENT & COUNTRY — before starting, a country self-declare select and a consent
line naming the verification provider and linking to the privacy policy. Consent
is captured at session start (the provider requires it) and the record is stored.

HISTORY — a list of past verification attempts with date, outcome and reason
class. Attempts are visible so the trader can see what already failed.

ERROR & EDGE STATES —
- `kyc.country_restricted` (403): "Verification isn't available in your country."
  with a support link — no further action offered.
- `kyc.already_in_progress` (409): "You already have a verification in progress"
  with a "Continue" button instead of a new session.
- After a rejection, a 24-hour cooldown applies: show "You can try again in
  {n} hours" with a countdown and the button disabled.
- Provider unavailable: an amber panel "Our verification provider is temporarily
  unavailable — you can upload documents for manual review instead" with the
  manual path as the primary action. This is the designed degradation, not an
  error.
- Verified identity is shown masked only (e.g. "Ali K."), never in full.

ACCESSIBILITY & MOBILE — the state hero is an aria-live region, gates are a
definition list with text badges, the primary action is always the largest
target, and the layout is single column from 320 px. No dark/light toggle in V1.
```

---

### SCREEN 22 — Verification session (provider embed) · `/kyc/session/{id}` · F6 · V1.0

```prompt
Build the hosted verification session screen for the Alpha One trader portal
(Next.js 15, TypeScript, Tailwind, shadcn/ui). The provider's flow (Veriff) runs
inside a same-origin iframe wrapper; our job is a calm, honest shell around it.

LAYOUT — a header with the account/firm name and a "Cancel" text button, the
iframe area, and a status footer. Max-w-3xl.

IFRAME AREA — the provider checkout embedded in a same-origin wrapper iframe with
a fixed aspect ratio that grows to fill available height on mobile. Above it a
one-line "You're verifying with { provider } — your documents go straight to them,
we only see the result."

LOADING STATE — a skeleton panel with a spinner and the line "Opening secure
verification…". If the provider takes more than 10 seconds, add "Taking longer
than usual? You can cancel and try again." — never a blank rectangle.

PROGRESS — show **states only, never a fake percentage**: a small stepper with
"Documents → Selfie → Done", advancing only on real provider callbacks. If the
provider reports an undecided result, the shell shows "Our team will review this
manually — we'll email you" and links back to the KYC status screen.

COMPLETION — on the provider's success callback, show a green confirmation panel
"You're verified" (or "Submitted for review" where manual review is required), the
next step in one sentence, and primary buttons "Back to verification status" and
"Go to my accounts". Auto-return to the KYC status screen after ~3 seconds with a
visible countdown so it never feels stuck.

CANCELLATION — "Cancel" opens a confirm dialog: "Leave verification? Your progress
won't be saved and you can start again later." On confirm, abandon the session
server-side and return to the status screen. Never leave an orphaned provider
session.

ERROR & EDGE STATES — provider unavailable (503): the shell swaps to the manual
upload path with an explanation. Session expired (24 h TTL): "This verification
link expired" with "Start a new one". Webhook mismatch (a provider callback for an
unknown session): never change state; show a neutral "Something went wrong —
please start again" and log the correlation id for support. Browser blocked
third-party iframes: a fallback panel with an "Open verification in a new tab"
button.

ACCESSIBILITY & MOBILE — the iframe has a descriptive title, focus is moved to the
shell heading on load, the cancel dialog traps focus and closes on Escape, and
the layout works from 320 px with the iframe filling the viewport height on
phones. No dark/light toggle in V1.
```

---

### SCREEN 23 — Manual document upload · `/kyc/upload` · F6 · V1.1

```prompt
Build the manual document upload screen for the Alpha One trader portal
(Next.js 15, TypeScript, Tailwind, shadcn/ui). It is the fallback path used when
the verification provider is unavailable or has flagged a case — the guarantee
that compliance never hard-blocks a trader.

LAYOUT — an explanation panel, upload slots, a submit button, and a status panel.
Max-w-2xl.

EXPLANATION PANEL — why the trader is here, in one sentence ("Our verification
provider is unavailable, so we'll review your documents manually"), what is needed,
and the expected turnaround ("usually within 24 hours"). Tone: reassuring, never
implying the trader did something wrong.

UPLOAD SLOTS — one card per required document type, driven by the tenant's
configuration: ID front, ID back, selfie, proof of address. Each slot is a
dropzone plus a "Choose file" button, shows the accepted formats (JPG, PNG, PDF),
the 10 MB maximum, and once a file is chosen shows a thumbnail (for images), the
filename, the size, a remove button, and an "Uploading… 64%" progress bar with a
retry button on failure.

VALIDATION — client-side pre-checks before upload: file type, size under 10 MB,
and a minimum resolution for image documents, each with a specific inline message
("That file is 14 MB — the maximum is 10 MB", "That image is too small — use at
least 1000 px wide"). These exist to catch obvious failures before paying a
provider or a reviewer's time.

SUBMIT — a "Submit for review" button, disabled until all required slots have a
successfully uploaded file. On submit, show a confirmation state: "Documents
submitted — our team will review them and email you the result." with a link back
to the KYC status screen.

STATUS PANEL — after submission, a persistent card on the KYC status screen
showing each uploaded document with its upload date and a "Under review" badge,
plus a "Replace document" action that creates a new version rather than mutating
the old one (the review history must stay answerable).

ERROR & EDGE STATES — upload failure: a retry button on that slot with the error
inline, and the rest of the form preserved. `kyc.upload_failed` (400): "Upload
failed — please try again." Session already in review: "Your documents are
already with our team" with the status panel instead of the form. Provider
recovers mid-flow: a note "You can also finish instantly with { provider }" with a
button that starts a hosted session.

ACCESSIBILITY & MOBILE — dropzones are keyboard-operable (Enter/Space opens the
file picker) with clear focus rings, progress bars use role="progressbar" with
aria-valuenow, errors are announced via aria-live, and the layout is single column
from 320 px with large tap targets. No dark/light toggle in V1.
```

---

### SCREEN 24 — Payouts overview · `/payouts` · F7 · V1.0

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

---

### SCREEN 25 — Eligibility preview & request · `/payouts/request` · F7 · V1.0

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

---

### SCREEN 26 — Payout methods · `/payouts/methods` · F7 · V1.1

```prompt
Build the payout methods screen for the Alpha One trader portal (Next.js 15,
TypeScript, Tailwind, shadcn/ui). It is where a trader tells the platform where
their money goes — the single highest-value fraud target in the product, so every
edit is versioned, confirmed and cooldown-flagged.

LAYOUT — a list of existing methods, an "Add method" form (inline panel or dialog),
and a security explainer. Max-w-3xl.

METHOD CARD — for each method: the rail type with its icon (TRC20 / ERC20 / BEP20 /
local provider), a masked destination ("TQrY…9fXz" — never the full string), an
optional label ("Main TRON wallet"), a "Default" badge where applicable, a
confirmation badge ("Confirmed" / "Needs confirmation"), the date added, and
actions: "Confirm", "Set as default" (V2), "Edit", "Remove".

CONFIRM-ONCE RULE (V1.1) — a newly added or edited method must be explicitly
confirmed by the trader before its first payout. Show a prominent amber banner on
unconfirmed methods: "Confirm this method before your next payout" with a
"Confirm method" button. After confirmation the badge turns green and the action
disappears. There is no per-payout re-confirmation.

ADD / EDIT FORM — a chain/rail selector, a destination field with chain-specific
validation (length, charset, base58/bech32 as applicable, and EIP-55 checksum for
ERC20), an optional label field, and a "Save" button. Validation runs on blur and
on submit with specific inline messages ("That doesn't look like a TRON address —
they start with T and are 34 characters"). Never accept an address that fails
checksum validation, and say why in plain words.

VERSIONING & COOLDOWN — editing a method creates a new version; the card shows
"Edited { date } — v2" and the previous version stays in an expandable history
("v1 · TQrY…9fXz · used on payout 01J9PAY…") so "which address did the $2,000 go
to" is always answerable. When a method is edited shortly before a payout request,
show a warning flag on the request (V2): "You changed this method recently — we've
flagged the request for review." Never silently swap a destination.

REMOVE — a confirm dialog: "Remove this payout method? Payouts already requested
will still be sent to the address on the request." Removal deactivates rather than
deletes, and the row is retained in history.

SECURITY EXPLAINER — a short panel: "We never show your full wallet address, we
verify the format before every payout, and changes are versioned so you can always
see where money was sent. If you didn't make a change, contact support
immediately." With a support button pre-filled with the account id.

ERROR & EDGE STATES — `payout.method_invalid` (400): "Please check your payout
details." inline on the field. `payout.invalid_address` (400): chain-specific
message. Saving while the dialog is open on another device: a conflict state with a
refresh prompt. Empty: "No payout methods yet — add one to receive payouts."

ACCESSIBILITY & MOBILE — the form fields are labelled with the chain named, the
confirmation banner is aria-live, the masked value has a "reveal" affordance only
for the trader's own data (an explicit click, never hover), and the layout is a
single column from 320 px. No dark/light toggle in V1.
```

---

### SCREEN 27 — Payout history & receipts · `/payouts/history` · F7 · V1.0

```prompt
Build the payout history and receipts screen for the Alpha One trader portal
(Next.js 15, TypeScript, Tailwind, shadcn/ui). Every payout the trader has ever
requested, with the receipt as a first-class citizen — the receipt is the dispute
defence, so it must always be one click away.

LAYOUT — a filter row, a table of requests, and an expandable detail panel per
row. Max-w-5xl.

FILTERS — status chips (All / Pending / Approved / On hold / Paid / Rejected), a
date range, and an account selector when there are several. Filters write to the
URL query.

TABLE COLUMNS — Requested (date), Account, Amount (final, in the account
currency), Method (rail + masked destination), Status badge, and actions
(Receipt, Details, Support).

STATUS BADGES — always word + colour: `pending_approval` amber "Awaiting
approval", `approved` blue "Approved", `on hold` amber "On hold for review",
`paid` green "Paid", `rejected` red "Not approved". A rejected row shows the
reason class in the table itself, not hidden in a tooltip.

EXPANDED DETAIL PANEL — the full, recomputable record:
- The frozen calculation: gross (high-water − initial), less already paid, trader
  share at the split ratio, cap at the requested amount, rail fee, final amount —
  each step on its own row with the arithmetic.
- The method **version** used and its masked destination, so the address a payout
  went to is always answerable.
- The execution record: provider, external reference (last four characters),
  amount, and timestamp.
- The approval trail: who approved it and when, in the firm's terms ("Approved by
  your firm's finance team on { date }").
- The rejection reason where applicable, plus a "Ask about this decision" button
  that opens support with the payout id pre-filled (the dispute channel lives in
  the product).

RECEIPT — a "Download receipt (PDF)" button on every `paid` row, rendered from
the frozen calculation. Signed URLs are 15 minutes and fetched on click, never
embedded. A receipt still generating shows "Preparing…" with a spinner and
auto-enables when ready; a failure shows an inline retry.

EMPTY STATE — "No payout requests yet" with a "Request a payout" button.
LOADING — skeleton rows. ERROR — inline retry with a support link.

ACCESSIBILITY & MOBILE — the table becomes stacked cards under 768 px with the
status badge first, the detail panel is a proper disclosure with aria-expanded,
amounts use tabular numerals and a consistent currency format, and every action is
keyboard reachable. No dark/light toggle in V1.
```

---

### SCREEN 28 — Documents centre · `/documents` · F8 · V1.0

```prompt
Build the documents centre for the Alpha One trader portal (Next.js 15,
TypeScript, Tailwind, shadcn/ui). Agreements, certificates, invoices and receipts
in one place — the paper a prop-firm trader screenshots and shares.

LAYOUT — a page header "Documents", a type filter, and a grouped list. Max-w-4xl.

TYPE FILTER — chips: All / Agreements / Certificates / Invoices / Receipts, with
counts. Filters write to the URL.

DOCUMENT ROW — an icon per type, the document title in plain words ("Funded
account certificate — $100,000"), the related account or order, the issue date,
and a primary "Download" button. A "New" badge appears on documents generated in
the last 7 days (V2 in-app notification complement). Rows are grouped under
sticky type headers with a count.

DOCUMENT TYPES (V1) — challenge agreement (issued at purchase), funded account
certificate, invoice, payout receipt. Each has its own icon and colour.

STATES PER ROW —
- Generated: an enabled "Download" button.
- Pending: a disabled-looking "Preparing…" with a small spinner; the button
  auto-enables when the document arrives (poll or SSE), never requiring a reload.
- Failed: "Couldn't generate this document" with a "Try again" button and a
  support link carrying the document id.

BEHAVIOUR — clicking Download calls the signed-URL route (15-minute TTL, audited)
and opens the PDF in a new tab; the URL is never embedded in the page or logged.
Show a brief "Preparing your download…" state while the URL resolves. On mobile,
the PDF opens in the system viewer.

EMPTY STATE — "No documents yet. Your agreement and invoice appear here right
after your first purchase, and your certificate the moment you're funded." with a
"Browse challenges" button.

ERROR & EDGE STATES — a document the trader doesn't own or that doesn't exist
returns the not-found page (404, never 403). A bulk list failure shows an inline
retry. Never render a broken link or an empty href.

ACCESSIBILITY & MOBILE — rows are list items with descriptive accessible names
including the type and date, the "New" badge is text as well as colour, group
headers are real headings, and the layout is a single column from 320 px. No
dark/light toggle in V1.
```

---

### SCREEN 29 — Notification centre · `/notifications` · F9 · V2.0

```prompt
Build the in-app notification centre for the Alpha One trader portal (Next.js 15,
TypeScript, Tailwind, shadcn/ui). In V1 the centre is a stub — email is the only
channel — so the V1 screen must be honest about that while reserving the exact
shape V2 fills in.

LAYOUT — a header with an unread count and a "Mark all read" action, a filter row,
and a grouped list. Max-w-3xl. On mobile it is a full-screen route; on desktop a
popover anchored to the bell in the top bar.

V1 STUB STATE — a single, plainly-worded panel: "Notifications are delivered by
email. In-app notifications are coming soon." Beneath it, a read-only list of the
lifecycle events that have been emailed to the trader (account created, phase
passed, phase failed, breach, KYC result, payment captured, payout approved,
payout rejected, payout settled) with their dates and a link to the relevant
object where one exists. This is a history view, not a lie about live in-app
delivery.

V2 LIST — notification rows with an unread dot, a type icon, a title, a one-line
body, a relative timestamp, and a deep link to the object. Grouped under date
headers (Today / Yesterday / Earlier). Unread rows have a subtle background;
read rows are plain. Clicking a row marks it read and navigates.

FILTERS — All / Unread, and type chips (Accounts, Payouts, KYC, Documents,
Security). Filters write to the URL.

PREFERENCES (V2) — a linked settings panel: a matrix of channels (Email, In-app,
Push, Telegram) × categories (Transactional — always on, Account updates,
Payouts, Marketing), quiet hours with a timezone, and a digest option. Transactional
rows are non-toggleable and rendered as such with an explanation, rather than as
disabled switches.

BEHAVIOUR — live updates arrive over the same SSE stream as the rest of the portal;
new notifications prepend with an aria-live announcement and the bell badge
increments. Optimistic "mark read" reverts with an inline retry on failure.

EMPTY STATE — "Nothing new. We'll tell you here when something happens to your
accounts."

ERROR & EDGE STATES — a failed list fetch shows an inline retry; the bell badge
falls back to the last known count rather than disappearing.

ACCESSIBILITY & MOBILE — the list is an aria-live region for new items, unread
state is conveyed by text as well as a dot, the popover traps focus and closes on
Escape and outside-click, and the full-screen mobile route has a back button. No
dark/light toggle in V1.
```

---

### SCREEN 30 — Profile & settings · `/profile` · F9 · V2.0

```prompt
Build the profile and settings screen for the Alpha One trader portal (Next.js 15,
TypeScript, Tailwind, shadcn/ui). Everything the trader controls about their own
account, with the sensitive actions clearly separated and protected.

LAYOUT — a left nav (Profile, Security, Notifications, Verification, Data) that
becomes a top tab bar on mobile, and the selected panel on the right. Max-w-5xl.

PROFILE PANEL — display name, email (read-only with a "Change" button), and a
summary card: member since, tenant/firm name, verification status with a link to
the KYC screen. A "Change email" flow is a sensitive action: it runs through the
shared `SensitiveDialog` and requires verifying **both** the old and the new
address before it takes effect, with a clear "We've sent a link to { new } —
click it to finish the change" state in between.

SECURITY PANEL — links into: password change (current password + new password with
the policy checklist), 2FA management (enrolment, backup codes, removal), and
"Where you're signed in" (the sessions screen). Each row shows its current state
("2FA: on — TOTP", "Password: changed 3 months ago") and an action button. A note
explains that changing the password signs out every other device.

NOTIFICATIONS PANEL — the preferences matrix from the notification centre
(channels × categories, quiet hours, digest), with transactional rows locked on
and explained.

VERIFICATION PANEL — the KYC status summary with a link to the full KYC screen;
the verified name is shown masked ("Ali K.").

DATA PANEL (V2, GDPR) — a "Export my data" button that requests a full export of
the personal data the platform holds, with an explanation of what is included, an
email delivery promise ("we'll email you a link within 24 hours"), and a list of
previous exports with their status and download links. Plus an "Activity log" link
showing the trader's own recent account activity (logins, changes, actions) so
they can spot anything suspicious.

BEHAVIOUR — every mutation is optimistic with a revert-and-retry on failure;
successes show a toast; sensitive mutations additionally emit a critical audit row
(the trader is told: "For your security we've emailed you about this change").

ERROR & EDGE STATES — a stale step-up (`authz.step_up_required`, 403) re-prompts
inside the dialog without losing context; a conflict on a concurrent edit shows
"Your profile was changed elsewhere — here's the latest" with a reload action; a
429 shows "Too many attempts — try again in { n }s".

ACCESSIBILITY & MOBILE — the nav is a real tablist with arrow keys, form fields
are labelled with inline validation, the panels are semantic sections with
headings, and everything works from 320 px. No dark/light toggle in V1.
```

---

### SCREEN 31 — Support & ticket history · `/support` · F9 · V2.0

```prompt
Build the support screen for the Alpha One trader portal (Next.js 15, TypeScript,
Tailwind, shadcn/ui). Support lives inside the product: the trader raises a ticket
from here or from any dead end elsewhere, and never has to find an email address.

LAYOUT — two panes on desktop (ticket list left, thread right) and a
list→detail navigation on mobile. Max-w-6xl.

NEW TICKET FORM — a category select with the fixed V1 set (Account, Payment,
Payout, KYC, Technical, Other), a subject line, a message body, an optional
attachment (type and size validated; unscanned files carry a visible
"unscanned" flag for staff), and a "Submit" button. When the trader arrived from a
dead end elsewhere in the portal, the form opens **pre-filled** with the context:
the account id, the saga id where one exists, the error code, and the page they
were on — shown as read-only "context chips" above the form so the trader can see
exactly what support will receive. A line explains: "Including this context helps
us answer faster."

TICKET LIST — the trader's own tickets only: subject, category badge, status
badge, last-activity relative time, and an unread indicator when staff has
replied. Filter chips by status (Open / In progress / Resolved / Closed /
Cancelled) and a search box. Sorted by last activity, newest first.

THREAD VIEW — the ticket header (subject, category, status, created date, the
context chips), then a chronological message thread. Three message types are
visually distinct: trader messages, staff replies, and internal notes (internal
notes are **never** shown to the trader — they exist only in the staff view; do
not render a placeholder for them). Each staff reply shows the agent's display
name and role. A reply box at the bottom with a "Send" button; sending is
optimistic with a retry on failure. The trader can cancel their own open ticket
via a "Cancel ticket" action with a confirm dialog.

STATUS MACHINE (trader-visible) — `open` → `in_progress` → `resolved` → `closed`,
plus `cancelled` by the trader. Each transition is shown in the thread as a
system line ("Your ticket was marked as resolved — reply to reopen it"). Replying
to a resolved ticket reopens it, and the UI says so.

NOTIFICATIONS — a note that every status change and reply is emailed (in-app
arrives in V2), with a link to the notification preferences.

EMPTY STATE — "No tickets yet. If something's wrong with your account, the fastest
way to reach us is here." with the form focused.
ERROR — inline retry on both panes; a failed send keeps the draft text.

ACCESSIBILITY & MOBILE — the list is a proper listbox/tablist pair with
aria-selected, the thread is an ordered list of articles, the reply box is
labelled and announces "Sent" via aria-live, and the mobile flow is list →
detail with a back button. No dark/light toggle in V1.
```

---

### SCREEN 32 — Mobile: account home · app tab · F10 · V2.0

```prompt
Build the mobile app's account home screen (React Native, iOS + Android) for the
Alpha One trader portal's native companion. It is a native layout, not a web port:
it uses the shared design tokens but not the DOM, and it consumes exactly the same
GW APIs and SSE endpoint as the web portal — there is no new backend.

LAYOUT — a native stack navigator screen with a large-title header showing the
tenant logo, an account switcher chip, and a bell icon with an unread badge.
Content scrolls with pull-to-refresh.

ACCOUNT CARD — the same information architecture as the web home card, natively
laid out: program name and account size, the state badge (opening / evaluating /
funded / paused / suspended / failed / closed) with the same semantics and
support links, and a 2×3 metric grid of Equity, Balance, Open P&L, Drawdown used,
Daily loss used, Target progress — each with a tick-age chip treatment (green
"Live" under 2 minutes, amber "stale — n min ago" older, banner past 10 minutes).
Tapping a card pushes the account detail screen.

QUICK ACTIONS ROW — horizontally scrollable native buttons: Live view, Request
payout, Credentials, Documents, Support — each disabled with an explanation when
the account state doesn't allow it (e.g. no payout button on an evaluation
account).

LIVE BEHAVIOUR — one SSE subscription for the selected account with the same
reconnect backoff (1/2/5/15 s) and 5-second polling fallback after three failures,
surfaced as a native banner "Reconnecting…" rather than a web chip. Pull-to-refresh
forces a server revalidation and updates the freshness label.

SESSION & SECURITY — on cold start, the app unlocks with the device biometric
(Face ID / fingerprint) over a short-lived device token; if the token has expired
or the biometric is unavailable, it falls back to the full password + 2FA login.
Show the locked state as a native biometric prompt, not a web form.

PUSH — on first launch, request notification permission with a plain explanation
of what will be pushed (payout settled, breach, funding, KYC decisions, security
events) and link to the preferences screen. Push deep-links open the matching
screen.

OFFLINE (V3) — cached read views only with a persistent native banner "Offline —
data from { time }"; no offline writes ever, and any write attempt shows
"You need a connection for this" rather than queueing.

ERROR & EDGE STATES — a 401 on the device token shows the full login; a 426
(minimum client version) shows a native update nudge with a store deep link and
degrades to read-only; a network failure shows a native retry panel, never a blank
screen. Authenticated screens are never cached to disk beyond the offline cache,
and the cache is encrypted with the keychain/keystore-wrapped key.

ACCESSIBILITY — native accessibility labels on every metric (including units), the
state badge is announced as text, Dynamic Type / font scaling is respected, and
all touch targets are at least 44×44 pt.
```

---

### SCREEN 33 — Mobile: live trade viewer · app tab · F10 · V2.0

```prompt
Build the mobile app's live trade viewer screen (React Native, iOS + Android) for
the Alpha One trader companion app. It is the web live trading view in a native
window, consuming the same read APIs and the same SSE stream.

LAYOUT — a screen with a segmented control (Chart / Positions / History), a
freshness header, and a scrollable body. Pull-to-refresh.

CHART SEGMENT — an equity curve for the selected range (1H / 1D / 1W / 1M), with
the high-water mark as a dashed reference line and the drawdown floor as a red
dashed line where the rule pack defines one. Prefer a native chart library that
accepts the same data shape; if none renders correctly, embed the web chart route
in a webview — the data contract is identical either way. The chart hydrates with
the last 60 points and appends live points from SSE; full history is a
range request with 30-second revalidation. If the chart fails to render, degrade to
a numbers table (time, equity, change) — the chart is an enhancement, the numbers
are the product.

POSITIONS SEGMENT — native cards, one per open position: symbol and side badge,
lots, open price, current price, and the P&L large and signed, with swap and
commission beneath and the open time. Live P&L updates in place with a subtle
flash on change. A totals header shows the floating P&L. Pagination at 100 rows.

HISTORY SEGMENT — closed deals as compact cards with close time, symbol, side,
lots, open/close prices and net P&L including swap and commission. A date filter
and a "Share / export" action (V2) that produces a CSV from the fetched page.

FRESHNESS HEADER — always visible: green "Live" under 2 minutes, amber
"stale — n min ago" when older, and an amber banner past 10 minutes. The SSE
lifecycle follows the web pattern exactly: reconnect with 1/2/5/15 s backoff,
three failures → 5-second polling + a "Reconnecting…" banner. This is a degraded
mode, never an error screen.

EMPTY & ERROR STATES — no open positions: "No open positions — your closed trades
are under History." A single data point: a flat line with "Not enough data yet."
A fetch failure inside a segment: a per-segment retry, never a blank screen. Never
show a number without its timestamp.

ACCESSIBILITY — every value has a native accessibility label including units, the
chart exposes a text summary for VoiceOver/TalkBack, live updates use polite
announcements and never move focus, and all touch targets are at least 44×44 pt.
```

---

### SCREEN 34 — Mobile: credentials · app screen · F10 · V2.0

```prompt
Build the mobile app's credentials screen (React Native, iOS + Android) for the
Alpha One trader companion. It is the most protected action in the app and must
feel like it: the biometric is a local convenience layered on top of a server-side
step-up, never a substitute for it.

LAYOUT — a screen with a warning-toned header ("Your MetaTrader 5 credentials",
plus "Keep these private — our team will never ask for them"), three credential
rows, an actions cluster, and a short setup-help panel.

CREDENTIAL ROWS — Account number (login) and Server visible by default with native
copy buttons; the trading password and the investor password masked by default
with a "Reveal" button each.

REVEAL FLOW — "Reveal" first performs the **device biometric** (Face ID /
fingerprint) to unlock the locally stored device token, then performs the
**server-side step-up** (a fresh authentication assertion no older than 5 minutes;
a stale one returns 403 `authz.step_up_required` and the app re-prompts). On
success the password renders once in monospace with a copy button and an
auto-mask countdown ("This disappears in 60s") that also masks on backgrounding the
app and on navigation. The value is never written to disk, never logged, and the
response is marked no-store.

SETUP HELP — three numbered steps (open MetaTrader 5 → File → Login to Trade
Account → enter server, login, password), a link to the firm's guide, and a
"Contact support" button with the account id pre-filled.

ERROR & EDGE STATES — biometric unavailable or removed on the device: fall back to
the full password + 2FA login, with a line "Biometric unlock isn't available on
this device." Account not yet active: an explanation that credentials appear once
the account is active, with a link to the opening saga. Account not found or not
owned: a native not-found state (never a 403). Rate limited: "Too many attempts —
try again in { n }s".

ACCESSIBILITY — the reveal button is never auto-focused, the biometric prompt uses
the platform's native system UI, copy actions announce "Copied", and all touch
targets are at least 44×44 pt with Dynamic Type respected.
```

---

### SCREEN 35 — Mobile: payouts · app tab · F10 · V2.0

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

---

### SCREEN 36 — Mobile: KYC capture · app screen · F10 · V2.0

```prompt
Build the mobile app's KYC capture screen (React Native, iOS + Android) for the
Alpha One trader companion. The capture happens inside the verification provider's
mobile SDK; our side is the same session API, the same state machine and the same
honest shell as the web flow.

LAYOUT — a status header, the provider's capture surface, and a progress footer.

STATUS HEADER — the same state hero semantics as the web KYC screen
(not started / pending / in review / approved / rejected / needs resubmission /
expired), each with a plain-language headline, plus the gates the verification
controls (funding, payouts) with pass/pending/blocked badges. The verified name is
always masked.

CAPTURE — embed the provider's mobile SDK (the same provider adapter the web flow
uses — a second client, not a second integration). Before launching, request
camera permission with a native rationale ("We need your camera to photograph your
ID") and handle a denial with a settings deep-link and the manual-upload fallback.
A session started on the phone completes on the phone; a session started on the web
shows "Continue on your other device" rather than restarting.

PROGRESS — states only, never a fake percentage: a stepper with "Documents →
Selfie → Done", advancing on real provider callbacks. If the provider returns
undecided, show "Our team will review this manually — we'll email you" and link
back to the status view.

FALLBACK — if the provider is unavailable, the screen offers the manual upload path
natively: camera or photo-library capture per document slot, with the same
client-side pre-checks (type, 10 MB maximum, minimum resolution) and per-file
progress with retry. This is the designed degradation, not an error.

COMPLETION — a native success panel ("You're verified" or "Submitted for review")
with the next step in one sentence, then auto-return to the status view after a
short, visible countdown.

ERROR & EDGE STATES — a restricted country shows "Verification isn't available in
your country" with a support link; an in-progress session shows "Continue
verification" rather than starting a second one; a 24-hour cooldown after a
rejection shows a countdown; an expired session offers "Start a new one". Documents
upload from the device are encrypted in transit and stored tenant-prefixed.

ACCESSIBILITY — the status header is announced on change, the stepper uses text
labels, all capture affordances are at least 44×44 pt, Dynamic Type is respected,
and the camera permission rationale is readable by VoiceOver/TalkBack.
```

---

### SCREEN 37 — Mobile: notifications, devices & push prefs · app screen · F10 · V2.0

```prompt
Build the mobile app's notifications and device-management screen (React Native,
iOS + Android) for the Alpha One trader companion. Push is the scarcest channel in
the product, so the defaults are conservative and the trader opts in to more rather
than being opted in by default.

LAYOUT — three sections in a scrollable settings screen: Notifications, Devices,
Security.

NOTIFICATIONS — the in-app centre (unread rows, date grouping, deep links to the
related object, mark-read) plus the push preferences: a matrix of channels
(In-app, Push, Email) × categories (Transactional — locked on and explained,
Account updates, Payouts, KYC, Marketing), a quiet-hours picker with a timezone,
and a digest option. A short explainer at the top: "We only push what matters —
payouts, breaches, funding and security. Add more if you want them." Push deep-links
open the matching screen.

DEVICES — a list of the trader's logged-in devices with a label, platform, last
active time and a "Current device" badge, each with a "Sign out" action, plus a
prominent destructive "Sign out of all devices" at the bottom with a confirmation.
This is the phone-loss control and is surfaced prominently rather than buried. Each
row also shows the device's push registration state ("Receiving push" /
"Not receiving push") with a "Re-enable" action, because a dead push token is
silently healed on the next registration.

SECURITY — links into password change, 2FA management, and the activity log (the
trader's own recent logins, changes and actions so they can spot anything
suspicious), plus a "For your security we email you about sensitive changes" note.

BEHAVIOUR — on app reinstall or token refresh, re-register the push token and
dead-letter the old one; on a 401 for the device token, drop to the full login and
re-enrol the biometric afterwards; on a 426 (minimum client version), show the
store update nudge and degrade to read-only.

ERROR & EDGE STATES — push permission denied: an inline card "Push is off — turn it
on in Settings" with a deep link, never a silent failure. A failed preference save
reverts with an inline retry. An empty device list shows only the current device.

ACCESSIBILITY — toggles are real switches with labels, the destructive action has a
confirmation dialog and is never the default focus, the device list is a semantic
list, and all targets are at least 44×44 pt with Dynamic Type respected.
```

---

### SCREEN 38 — Trading journal · `/journal` · F10 · V2.0/V3.0

```prompt
Build the trading journal screen for the Alpha One trader portal (Next.js 15,
TypeScript, Tailwind, shadcn/ui). It is the trader's private workspace: a place to
attach notes, tags and emotions to their own deals. Privacy is the headline
requirement — there is no staff read path, ever, and the UI must make that
unmistakable.

LAYOUT — a header with a "New entry" primary button, a filter/search row, and a
two-pane layout on desktop (entry list left, editor right) that becomes a
list→detail flow on mobile. Max-w-6xl.

ENTRY LIST — each entry shows the linked trade (symbol, side, lots, close time,
net P&L), the entry's title, its tags as chips, a mood/confidence indicator if the
trader set one, and the last-edited relative time. Search across title, body, tags
and symbol; filter by tag, by date range, and by outcome (winners / losers).

EDITOR — a title field, a rich-text body (bold, italic, lists, links — no image
paste from arbitrary URLs), a tag input with suggestions from the trader's existing
tags, an emotion/confidence picker, and a "linked deal" reference. The linked deal
is a **frozen snapshot** of the trade at the time of linking: symbol, side, lots,
open and close prices, P&L, swap, commission, timestamps and the broker ticket.
Show the snapshot as a read-only card above the editor so the trader can see
exactly which trade the entry belongs to, even if the trade list paginates away.

LINKING — a "Link a trade" action opens a searchable picker of the trader's closed
deals; selecting one attaches the frozen snapshot and shows the card. An entry can
link to one deal (V2) or several (V3).

ANALYTICS (V2) — a stats strip computed from the journal itself: entries per week,
the trader's win rate on entries tagged with a given emotion, average P&L by tag,
and a calendar heat-map of P&L by day. Clearly labelled as derived from the
trader's own notes and closed deals.

REPLAY & SHARING (V3) — a "Replay" action that re-renders the linked trade's price
action around its open and close with the entry's notes as annotations, and an
opt-in "Share" that produces a public, read-only, anonymised link (no account
numbers, no identity) — off by default, and the share dialog says plainly what will
be visible.

PRIVACY BANNER — a persistent, dismissible-per-session banner: "Your journal is
private. No one at your firm or at Alpha One can read it." It reappears on the
first entry of each session.

EMPTY STATE — "No entries yet. Write your first note on a closed trade to start
building your edge." with the button focused.
ERROR — per-pane retry; a failed save keeps the draft in local state and offers
"Retry" and "Copy to clipboard" so work is never lost.

ACCESSIBILITY & MOBILE — the editor is keyboard-navigable with a visible focus
ring, the list is a semantic list with aria-selected, the two-pane layout collapses
to a stack under 1024 px, and the body field supports undo/redo natively. No
dark/light toggle in V1.
```

---

### SCREEN 39 — Education hub · `/academy` · F10 · V2.0/V3.0

```prompt
Build the education hub screen for the Alpha One trader portal (Next.js 15,
TypeScript, Tailwind, shadcn/ui). Lessons and courses that help traders understand
the rules they are judged on — with completion tracking that is honest rather than
gamified into meaninglessness.

LAYOUT — a header "Academy", a "Continue where you left off" strip, a course grid,
and (V2) a recommended-lessons widget on the dashboard that links here.

COURSE CARD — title, a one-line description, the lesson count, the estimated
duration, a difficulty badge, the completion state (Not started / In progress 3 of
8 / Completed with the date), and a primary "Start" / "Continue" / "Review" button.
Cards are grouped by track (Getting started, Risk management, Trading psychology,
Platform guides).

LESSON VIEWER — a two-pane layout: the lesson content on the left and a lesson
sidebar on the right showing the course outline with completion ticks. Content
supports text, images, and video delivered through short-lived signed URLs (video
is streamed from object storage, never embedded from a third party). A "Mark as
complete" button advances the outline and updates the course progress bar.

COMPLETION HONESTY — a lesson is complete only when its stated criteria are met:
for a video lesson, watched to at least 90%; for a quiz lesson, passed at the
configured threshold; for a reading lesson, explicitly marked. Show the criterion
on the lesson ("Watch 90% to complete") and, where it is not yet met, show the
progress toward it ("78% watched"). Never auto-complete on page view, and never
show a completion tick that the criteria don't support.

QUIZZES — multiple-choice with immediate per-question feedback, a pass threshold
shown up front, unlimited retakes, and a results panel listing which questions were
missed with a link back to the relevant lesson section.

PROGRESS — a per-track progress bar and a "certificates of completion" list (V3)
where the tenant awards them. Progress is visible on the dashboard widget
(recommended lessons and course progress) and in the profile.

EMPTY STATE — "No courses published yet by your firm." (the hub is
tenant-populated), rather than a generic empty state.
ERROR — per-pane retry; a video that fails to load shows "This video couldn't
load — try again" with a retry, never a black rectangle.

ACCESSIBILITY & MOBILE — the outline is a proper navigation list with
aria-current, the video player has captions support and keyboard controls, quiz
options are real radio groups with feedback announced via aria-live, and the
two-pane layout stacks under 1024 px. No dark/light toggle in V1.
```

---

### SCREEN 40 — Community & live chat · `/community` · F10 · V2.0/V3.0

```prompt
Build the community and live-chat screen for the Alpha One trader portal
(Next.js 15, TypeScript, Tailwind, shadcn/ui). Two distinct things share this
surface and must not be confused: a persistent support conversation with the firm,
and (V3) a peer forum. They have different moderation rules and different privacy
expectations.

LAYOUT — a left rail with two sections: "Support" (direct messages with firm staff)
and "Community" (V3: channels and the forum). The main pane shows the selected
conversation. Max-w-6xl. On mobile it is a list → conversation flow.

SUPPORT DIRECT MESSAGES (V2) — a persistent thread between the trader and firm
staff. Messages are bubbles with the author's display name and role, timestamps,
and read state. A composer at the bottom with a send button and an attachment
action. Conversation history persists across sessions so context is never lost. A
clear header states who the trader is talking to ("Chatting with FunderBlu
support") and the expected response window. An escalation line: "Need a formal
ticket? Open a support ticket" linking to the support screen, because the chat is
not a substitute for the audited ticket.

ANNOUNCEMENT CHANNEL — a read-only channel where the firm publishes updates.
Messages are full-width cards with a date, and the channel shows an unread divider.
The trader cannot post here, and the UI says so.

COMMUNITY FORUM (V3) — a channel list and a thread view: threads with a title,
author (with an alias option), tags, reply count and last-activity time; a thread
view with nested replies, a composer, and a "report" action on every post. Aliases
are opt-in per post, and the default display name is the trader's chosen alias
rather than their real name.

MODERATION (V3, staff-side but visible here) — a removed post renders as
"This message was removed by a moderator" with no content, and a banned user sees
a plain notice rather than an error loop. Report actions confirm and thank the
trader.

LIVE CHAT HANDOFF (V3) — from a support conversation, a "Start live chat" action
that shows the queue position and the wait estimate, and hands off to an agent with
the conversation history attached.

PRIVACY & SAFETY — a persistent note in the support section: "Firm staff can read
these messages. Never share your password or 2FA codes." In the community section:
"Aliases are optional. Posts are public to other traders at your firm."

EMPTY STATES — no conversations: "Message us any time — we usually reply within a
few hours." No community yet: "Your firm hasn't opened the community yet."
ERROR — per-pane retry; a failed send keeps the draft text and offers retry.

ACCESSIBILITY & MOBILE — the conversation is an ordered list of articles, new
messages are announced politely via aria-live without stealing focus, the composer
is labelled, and the mobile flow is list → conversation with a back button. No
dark/light toggle in V1.
```

---

### SCREEN 41 — Competitions & leaderboard · `/competitions` · F10 · V3.0

```prompt
Build the competitions and leaderboard screen for the Alpha One trader portal
(Next.js 15, TypeScript, Tailwind, shadcn/ui). Trading contests run by the firm,
with a leaderboard that is transparent about its freshness and its integrity rules.
This surface is explicitly out of scope for V1 — build it only in the V3 phase.

LAYOUT — a competition list, a competition detail view with a live leaderboard, and
a results/archive view. Max-w-6xl.

COMPETITION CARD — name, the period (start and end dates), the entry type (Free /
Paid with the price), the scoring criterion in plain words ("highest profit
percentage"), the prize structure summary, the eligibility summary, and a status
badge (Upcoming / Live / Ended). A primary "Register" button, or "Join — $X" for
paid entries which routes through the same checkout flow as a challenge.

COMPETITION DETAIL — a header with the name, period, a live countdown to the end,
and the trader's own rank highlighted in the leaderboard. Tabs: Leaderboard /
Rules / Prizes / My entry.

LEADERBOARD — a ranked table: rank, trader (alias by default, with the real name
only where the trader opted into a public profile), the score, and the change since
the last refresh. A visible **"Updated { relative time }"** timestamp is mandatory —
the leaderboard is only trustworthy if its freshness is stated. Rows for breached,
suspended or risk-flagged accounts are excluded from rankings, and a note says so.
Scores freeze at the competition end, and the frozen table is what remains
published. An alias toggle lets the trader control how they appear.

RULES TAB — eligibility (which accounts qualify), the scoring formula, the
tie-breakers, the entry limits per trader, and the multi-account policy stated in
plain words.

PRIZES TAB — the prize table (1st/2nd/3rd and any milestone prizes), the delivery
mechanism for each (account credit, payout, or coupon), and the notification
promise ("winners are notified by email and in-app").

MY ENTRY — the trader's competition account (provisioned separately from their
evaluation accounts, in a dedicated competition group), their current score, their
rank, and a link to the live view for that account.

END & RESULTS — when a competition ends, the view switches to final standings with
the prizes awarded, a "Results are final" note, and the archive of past
competitions browsable underneath.

STATES — a registered trader sees "You're in" with a "View my entry" button; an
ineligible trader sees the specific reason ("requires a funded account"); a full
competition shows "Registration closed". Loading skeletons; a not-found or
cross-tenant id returns the not-found page.

ACCESSIBILITY & MOBILE — the leaderboard is a real table with header scope and
right-aligned numbers, the freshness timestamp is a semantic time element, rank
changes are announced politely, and the table becomes cards under 768 px. No
dark/light toggle in V1.
```

---

### SCREEN 42 — Badges & public profile · `/profile/public` · F10 · V3.0

```prompt
Build the badges and public-profile screen for the Alpha One trader portal
(Next.js 15, TypeScript, Tailwind, shadcn/ui). Achievement is visible and
shareable, but privacy defaults to off and every disclosure is an explicit,
reversible choice by the trader. This surface is explicitly out of scope for V1.

LAYOUT — two sections: "Your badges" and "Public profile" (with an opt-in switch).
Max-w-3xl.

BADGES — a grid of badge tiles, each with an icon, a name, a one-line description
of how it was earned, and the date earned. Earned badges are full colour; unearned
ones are muted with the criterion shown ("First payout — request and receive your
first payout"). Badge categories: milestones (funded, first payout, payout streak),
competition results, and activity tiers. A count header "12 of 40 earned".

LEVELS & XP (V3) — a progress bar showing the trader's current tier, the XP in the
current tier, and what the next tier unlocks, with a tooltip explaining how XP is
earned (activity, not spend).

PUBLIC PROFILE OPT-IN — a switch, off by default, with a plain explanation of
exactly what becomes visible: the trader's chosen alias, their badge collection,
their aggregate statistics (win rate, profit factor, total funded time), and their
competition placements. The explanation lists what is **never** shown: real name,
email, account numbers, wallet addresses, live equity, or per-trade history. Turning
it on requires an explicit confirmation; turning it off takes effect immediately
and the public URL stops resolving.

PROFILE PREVIEW — a read-only preview card of how the public profile appears to
others, with the public URL displayed and a copy button, plus a "View public page"
link that opens it in a new tab. The public page itself shows no PII, is
rate-limited, and renders a plain not-found for an unknown or opted-out profile.

STATS SELECTION — checkboxes letting the trader choose which aggregate statistics
appear (win rate, profit factor, total trades, funded days, badges). Live equity,
balance and per-trade data are never selectable.

ERROR & EDGE STATES — a failed opt-in reverts the switch with an inline retry; a
public URL for an opted-out trader returns a not-found page rather than a
permission error; badge data that fails to load shows a per-section retry.

ACCESSIBILITY & MOBILE — the opt-in switch is a real switch with a label, the
preview is a semantic article, badges have text names and descriptions (never
icon-only), and the layout is a single column from 320 px. No dark/light toggle.
```

---

### SCREEN 43 — Affiliate / referral dashboard · `/referrals` · F10 · V3.0

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

---

## Part 4 — How to use these prompts

1. **Pick the release.** Only screens tagged V1.0 / V1.1 belong in the V1 build.
   The V2/V3 screens are designed but deliberately deferred — building them early
   is scope creep against the V1.0 money-path gate.
2. **Copy one block at a time.** Each `prompt` block in Part 3 is self-contained
   and also exists as its own file in `trader-screen-prompts/`, so you can paste a
   single screen into v0, Lovable, Cursor or Figma-Make without dragging the rest
   of the document along.
3. **Swap the mock data for the real routes.** Every prompt names the data it
   renders; the actual contracts live in `alpha-one/contracts/api/` (`td.md`,
   `chk.md`, `pay.md`, `kyc.md`, `doc.md`, `lcc.md`). Generate against the
   documented shapes and the screens drop onto the GW without rework.
4. **Keep the four honesty rules.** Whatever tool you use, do not let it drop
   these, because they are the product's trust surface: (a) every live number
   shows its age, (b) errors show the user-safe message and never the code,
   (c) sensitive actions always go through the step-up dialog, (d) every dead end
   has a support button with context pre-filled.
5. **One component library, not forty.** The state badge, the tick-age chip, the
   meter, the `SensitiveDialog`, the status tracker and the empty/error panels are
   the same components on every screen. Build them once in `web/shared` and let
   the prompts reference them.

# 16 — TD: Trader Dashboard

> Covers PRD module **TD** (Trader Dashboard, Rel 1.0). The trader portal:
> accounts, live P&L, broker credentials, purchases, payouts, KYC, documents,
> notifications.
>
> **Note on requirements:** TD's requirement rows sat in a PRD page band the
> extraction tool could not parse (0 recovered ids — see `99-development-
> phases.md` §risk register). This document is scoped from the module catalog
> (docs/00 §4) plus the TD-xx references other module docs committed to
> (TD-06/21 equity curves, TD-10 payout section, TD-11 status polling,
> TD-26 payout preview). **FunderBlu's product owner should confirm the TD
> screen list in Phase 1** — that confirmation is a Phase-1 checklist item,
> not a blocker: the screen list below is what the backend already promises.

## 1. Purpose & scope

TD is where a funded trader lives every day. V1 screens (the committed set):

| Area | Screen(s) | Key data source (via GW) |
|---|---|---|
| **Onboarding** | Login/2FA/recovery (AUTH UI), KYC flow (13), first-purchase path | AUTH, KYC, CHK |
| **Account home** | My accounts: state badge, phase, key numbers (equity, balance, drawdown, daily loss, target progress, time left), state history | LCC |
| **Live trading view** | Live equity curve, open positions, recent deals, tick-age indicator | BRG (read API) + SSE live feed (01 §4.3) |
| **Credentials** | MT5 account # + password (one-time reveal flow), MetaApi portal link, reset request | LCC/BRG |
| **Purchase** | Catalog (packages × rule sets), checkout (CHK), order history | CHK, TEN |
| **Payouts** | Eligibility preview (TD-26), request form, payout history + status + receipts, payment methods | PAY |
| **Documents** | Certificates, agreements, invoices, receipts, download | DOC |
| **Notifications** | In-app center (V2), history, preferences | NOT |
| **Profile** | Email change (sensitive flow), password/2FA, KYC status, payout method defaults | AUTH, KYC, PAY |

**Explicitly not in V1:** journal (JRN V2), education (EDU V2), community
(CHT V2), mobile (MOB V2 — TD must be mobile-*responsive* from day 1),
settings-adjacent admin surfaces (those are ADM's).

## 2. Architecture

```
 browser ──► Next.js 15 (web/td) — RSC pages + client islands
   │   · RSC (server components) for data-heavy pages: accounts, history,
   │     documents (server-side GW fetch with the session cookie; FE never
   │     sees PG or long-lived secrets)
   │   · client islands: live chart (TradingView Lightweight Charts ~45KB),
   │     payout form, checkout widget, notification center
   │   · live updates: SSE endpoint /v1/td/streams/{account} (01 §4.3):
   │     GW-authenticated SSE, server-side relay of EVT `account.state_changed`,
   │     equity points (ANA read model), `notification.*` (V2 in-app)
   │   · fallback: the TD-11 pattern — if the stream drops, the island polls
   │     the status endpoint (5 s) and the UI shows a "live" vs "5s ago" chip
   ▼
 GW (docs/04): tenant resolution (subdomain/custom domain), session auth,
   rate limits, the single error contract
   ▼
 Go domain APIs (LCC/BRG/PAY/KYC/CHK/DOC/NOT)
```

**FE-never-touches-PG** (binding stack): every data point is a GW API; RSC
does server-side fetch with the authenticated session (same-origin cookie).
No API keys in the browser except the trader's session; the MetaApi portal
link is an opaque hosted URL (08), never a raw broker credential beyond the
one-time reveal.

## 3. System design

### 3.1 Page → API contract (V1)

| Route | Data (GET via RSC or island) | Notes |
|---|---|---|
| `/` (account home) | `GET /v1/accounts` (state, phase, metrics snapshot, time left) | metrics = the EVL-49 *observed* numbers; staleness chip if tick age > 10 min |
| `/accounts/{id}` | `GET /v1/accounts/{id}` + `GET /v1/accounts/{id}/positions|deals` (BRG read) + SSE | positions/deals paginated, 100 max page |
| `/accounts/{id}/credentials` | `GET /v1/accounts/{id}/credentials` (masked; reveal = 2FA + audit) | one-time reveal: password shown once, then masked forever (re-issue = support reset, BRG) |
| `/buy` | `GET /v1/payments/catalog` → checkout (CHK) → redirect → `/orders` | checkout is the only page with a redirect out |
| `/orders` | `GET /v1/payments/orders` (own) + invoice links | |
| `/payouts` | `GET /v1/payouts/eligibility` (TD-26) + request form + `GET /v1/payouts` | eligibility re-fetched on open (server-side) — never trust the cached preview |
| `/payouts/methods` | PAY methods CRUD (11 §7) | |
| `/kyc` | KYC status + session embed + uploads (13 §7) | Veriff iframe embed (same-origin wrapper) |
| `/documents` | `GET /v1/documents` + signed URLs (15 §7) | |
| `/notifications` | in-app center (V2; V1: "email only" stub + history stub) | |
| `/profile` | AUTH profile/2FA endpoints + email change (sensitive) | |

### 3.2 Live data design (the equity view)

- **Equity curve:** ANA read model (01: `equity_points`-class table, 1 min
  granularity) → RSC loads the day's points; the island appends live points
  via SSE; TradingView Lightweight Charts renders (no custom canvas code).
- **Tick honesty:** every live number carries its `tick_at`; the UI renders
  "live" (green dot) when < 2 min, "stale — {n} min ago" (amber) when older,
  matching the EVL-52 guard semantics so the trader sees the same staleness
  the engine sees (no "my dashboard shows equity, my account failed" gap).
- **No chart SSR jank:** the island hydrates with the last 60 points; full
  history is a server-fetched range request (RSC revalidation 30 s).

### 3.3 State-driven UI (the LCC badge)

The account state machine (07 §5) drives a single badge component used on
every account surface: `opening` (spinner + steps: KYC → broker account →
funding → active), `evaluating` (phase + metrics), `funded` (live),
`paused`/`suspended` (reason class + support link), `failed/breached`
(what rule, evidence numbers, next steps — from the breach verdict),
`closed` (documents only). The **steps strip** during `opening` is the
purchase→funding saga made visible (EVT-17 saga events) — the #1 support
question ("why is my account still opening?") answered by the UI, not a ticket.

### 3.4 Error & empty states

The GW error contract (04 §3.4: `{error:{code,message,details}}`) maps 1:1 to
UI treatments: `*_REQUIRED`/`*_WINDOW`/`*_BELOW_MIN` → inline forms with the
`details` (next eligible time, missing docs); `*_CONFLICT`/`*_EXISTS` →
toast + link to the existing object; `503`-class (rail unavailable) → "try
another method" with the alternatives from the response. **No code in the
error text:** the UI shows the `message` (already user-safe) and uses `code`
for behavior only.

### 3.5 Sensitive actions in TD

Email change (re-verification of both addresses), password reset, 2FA setup,
credential reveal, payout request (2FA step-up per AUTH), refund request —
all step-up (MFA) flows share one `SensitiveDialog` component (reason + 2FA +
confirmation text). Every one of these emits audit (critical tier, AUD).

## 4. Events (consumed by TD)

| Event | How TD uses it |
|---|---|
| `account.state_changed` | SSE → badge + steps strip update (no full reload) |
| `equity.point` (ANA read model, SSE relayed) | chart append |
| `payout.status_changed` | payout section live update (island refetch on SSE) |
| `kyc.status_changed` | KYC screen update (post-Veriff-callback) |
| `document.generated` | documents badge "new" (V2 in-app notification) |
| `notification.*` (V2) | in-app center push |
| `checkout.order_state` | `/buy` completion screen (polling fallback) |

TD **produces no domain events** — every trader action is an API call; the
domain emits. (A `trader.ui_action` event for ANA is V2, not V1.)

## 5. Lifecycles

TD has no domain state machine; its lifecycles are **UI/session**:

- **Session:** AUTH session (PG + Redis deny-set, 02); step-up expiry 5 min;
  idle timeout 30 min (auth config) → re-login (credentials screen preserved
  via `next` param).
- **SSE stream:** connect → (heartbeat 25 s) → drop → reconnect with backoff
  (1/2/5/15 s) → 3 failures → polling fallback (TD-11) + "reconnect" chip.
- **Saga strip:** `opening` steps advance on EVT-17 saga events; a step stuck
  > 15 min shows "contact support" with the saga id pre-filled (SUP).

## 6. Error taxonomy

TD introduces **no new server codes**; it *presents* the module codes.
Client-side taxonomy (for FE error-boundary + Sentry grouping):

| Class | Trigger | UI |
|---|---|---|
| `auth.expired` | 401 on any call | full-screen re-login (state preserved via query) |
| `tenant.not_found` | 404 tenant | "site not found" (04: 404-not-403 posture) |
| `rate.limited` | 429 + Retry-After | inline "slow down, try in {n}s" |
| `gw.internal` | 5xx | error boundary: retry button + ticket pre-fill + Sentry id shown |
| `stream.lost` | SSE 3 reconnect fails | polling fallback + amber chip (not an error screen) |
| `render.stale` | data age > 10 min on live views | amber "data from {time}" banner (honesty over polish) |
| `PARTIAL` | island fetch failed but page rendered | per-card skeleton + retry, never a broken page |

## 7. API endpoints
### 7.1 V1 baseline — `td` (see `contracts/api/td.md`)

**No HTTP surface in V1** — this is an internal/service contract. The internal contracts (what other modules call, what workers run, what is enforced) are in `contracts/api/td.md`.

### 7.2 Extended (post-V1) surface — provisional

> Not in the V1 execution sheet. Design-level; paths beyond the V1 baseline are provisional until the URL-plan decision (`contracts/api/gw.md`, open question). Shown for platform completeness (V2/V3 phases, docs/99).

TD consumes (all via GW, session-authed): AUTH (02), LCC `GET /v1/accounts…`,
BRG read `GET /v1/accounts/{id}/positions|deals|history` (08 §7), PAY (11 §7
trader surface), CHK (12 §7 trader surface), KYC (13 §7 trader surface),
DOC (15 §7 trader surface), NOT (14 §7), `GET /v1/td/streams/{account_id}`
(SSE — GW route, server-side relay), `GET /v1/td/health` (for the UI's
"platform status" chip, reads the ops status object, OPS).

TD exposes **no endpoints** (it's a client).
## 8. Schema (key shapes — what TD renders)

```jsonc
// GET /v1/accounts/{id} (the home card)
{ "data": { "id": "01J9ACC...", "state": "funded", "phase": "funded",
    "package": "Funded $100K", "broker": "MT5", "broker_account": "51002345",
    "metrics": { "equity_cents": 10412000, "balance_cents": 10398000,
        "hwm_cents": 10412000, "trailing_dd_bps": 210, "daily_loss_bps": 340,
        "target_bps": 8000, "target_reached": true,
        "trading_time_left_s": 4102000, "tick_at": 1758282001000 },
    "state_history": [ { "state": "funded", "at": 1758278400000 } ] } }

// SSE frame (account stream)
event: equity
data: { "at": 1758282001000, "equity_cents": 10412000 }
event: state
data: { "state": "paused", "reason_class": "trader_requested", "at": 1758282002000 }
```

## 9. Database design

**None** — TD is stateless (binding: FE never touches PG). Its only
"database" is the browser: session cookie (AUTH-owned), localStorage for UI
preferences (chart theme, last-selected account), IndexedDB **not** used
(no client-side data persistence of financial data — a leaked profile must
not leak equity history).

## 10. Security & compliance

- **XSS surface:** the only untrusted content is tenant branding (CMS) and
  support canned text — sanitized at render (React escaping default; no
  `dangerouslySetInnerHTML` without an explicit sanitize pass — lint rule
  enforced in CI).
- **CSRF:** same-origin cookie auth + `SameSite=Lax` + the GW's CSRF
  posture for state-changing routes (04); the checkout redirect is the one
  exception and is GET-idempotent by design.
- **Credentials reveal:** 2FA + critical audit + one-time semantics (07/08
  own the reset); the reveal response is never cached (no-store headers on
  that route) and the island never writes it to storage.
- **PII in the UI:** masked by default (email, method strings, KYC names);
  unmask = explicit click (no extra auth for own data — it's the trader's
  own profile; the AUD line is still written for credential reveal only).
- **No service workers in V1** (stale-data risk on financial pages); V2 with
  a strict no-cache policy for data routes.
- **Console hardening:** the admin console is a **separate subdomain + auth
  realm** (PRD non-negotiable) — TD and CON never share session storage.
- **Analytics:** first-party only (ANA events via the GW, no third-party
  trackers in V1 — a tracker exfiltrating equity data would be a breach).

## 11. Scalability considerations

- V1: ~1-2k concurrent traders peak (FunderBlu migrating base ~ a few hundred
  daily actives); Next.js on 1 container + RSC caching handles 10× that.
- **SSE is the scaling-sensitive part:** 2k concurrent streams × 1 msg/25 s
  heartbeat = trivial load; the server-side relay fans out from the EVT
  consumer (one reader, many SSE writers) — at 10×, put the SSE endpoints
  behind their own container replicas (stateless; the relay reads Redis
  Streams directly).
- RSC revalidation: 30 s for account pages (the SSE keeps it feeling live);
  full-page CDN cache: **none** for authenticated pages (Cloudflare:
  per-user no-cache, `cdn-cache-control: private`).
- Assets: images via Cloudflare (R2 bucket), charts client-only (~45KB),
  no SSR for the chart (island).
- Mobile-responsive from day 1 = the MOB (V2) app reuses the same GW APIs
  (01: MOB consumes TD's backend, not a new one).

## 12. Open-source solutions

| Option | Verdict |
|---|---|
| **Next.js 15 + TS + Tailwind** (binding stack, 01 §2) | **CHOSEN** — App Router, RSC, one monorepo with ADM/CON/CMS (`web/`) |
| TradingView Lightweight Charts (register) | **CHOSEN** — equity curves/positions, ~45KB, MIT |
| shadcn/ui + Tailwind | CHOSEN (component library, copy-in — no runtime dep) |
| Zustand (client state in islands) | CHOSEN (minimal; server state = RSC) |
| Apollo/React Query (full client data layer) | Rejected: RSC already owns the fetch layer; islands need little client state |
| Storybook | CHOSEN (design-system QA for the badge/status components — the LCC-driven UI) |
| react-hook-form + zod | CHOSEN (forms: payout, checkout, KYC uploads; zod schemas mirror the GW error contract) |

## 13. Technology stack

Next.js 15 (App Router, RSC, SSE), TypeScript, Tailwind, shadcn/ui,
TradingView Lightweight Charts, react-hook-form/zod, Storybook, Sentry
(browser SDK), pnpm monorepo (`web/td/` + `web/shared/`).

## 14. Integration — internal modules (glue)

| Module | How |
|---|---|
| **GW** | every call; tenant by subdomain; session cookie; SSE route; the error contract is the UI's contract |
| **AUTH** | login/2FA/recovery UI (Better Auth frontend), step-up dialog, profile |
| **LCC** | account home, state badge, steps strip (EVT-17 saga), credentials |
| **BRG** | positions/deals/equity read APIs; tick-age chip (08) |
| **EVL/ANA** | metrics (observed numbers) + equity curve read model |
| **CHK** | catalog → checkout → order completion |
| **PAY** | eligibility preview (TD-26), request, methods, receipts |
| **KYC** | status, Veriff embed wrapper, uploads |
| **DOC** | documents list + download |
| **NOT** | in-app center (V2), email-only stub (V1) |
| **SUP** | "contact support" with pre-filled context (saga id, account id, error code) — every dead-end in TD has a ticket button (SUP-01 intake) |

## 15. Integration — external tools

Better Auth (frontend), Veriff (checkout embed iframe), Cloudflare (assets +
edge), Sentry (browser), TradingView (charts, no data leaves the browser —
public CDN script, allowed exception to the no-third-party rule for a
rendering library with zero payload).

## 16. Implementation blueprint

| Step | Owner | Est | Depends | Exit criteria |
|---|---|---|---|---|
| 1. Monorepo scaffold (`web/td` + `web/shared`), design system (badge, card, dialog, error states), routing shell | FE-01 | 3 d | OPS (web deploy), GW auth flows working | Storybook green; routes render against a stub GW |
| 2. Auth screens (login/2FA/recovery) + session/step-up wiring + AUTH_EXPIRED flow | FE-01 | 3 d | 1, AUTH | full login lifecycle in staging incl. 2FA + lockout messages |
| 3. Account home + badge + steps strip + LCC/B RG read wiring + SSE island (chart, staleness chip, polling fallback) | FE-01 | 5 d | 2, LCC, BRG, ANA read model | live equity updates in browser on a sandbox account; stream kill → polling fallback visible |
| 4. Purchase flow (catalog → checkout → completion) + orders | FE-01 | 4 d | 3, CHK | end-to-end purchase in staging (sandbox provider); double-redirect = no double order |
| 5. Payouts (eligibility preview, request + 2FA, methods, history, receipts) | FE-01 | 4 d | 4, PAY | full payout journey in staging; every fail code has a tested UI state |
| 6. KYC screens (status, Veriff embed, uploads, progress) | FE-01 | 3 d | 2, KYC | L1 verification completed in-browser in staging |
| 7. Documents + profile + notifications stub + credentials reveal (2FA) | FE-01 | 3 d | 3, DOC, AUTH | each screen has happy + error + empty states (checklist-reviewed) |
| 8. Mobile responsive pass + a11y (keyboard, contrast) + Lighthouse < 2.5 s on 4G | FE-01 + FE-02 | 3 d | 7 | Lighthouse report in PR; FunderBlu UAT on real devices |
| 9. V2: in-app notification center, preferences, journal shell prep (APIs land with JRN) | FE-01 | 2 wks | NOT V2, JRN | — |

**Risks:** screen-list drift (the TD reqs were never machine-extracted —
mitigation: Phase-1 screen-list sign-off with FunderBlu PO before step 4
freezes; backend API surfaces are already committed, so drift is UI-scope,
not data-scope); SSE reliability on flaky mobile networks (mitigation:
polling fallback is first-class, not a patch — the staleness chip makes the
degrade visible); chart vendor lock (Lightweight Charts is a render-only
lib — the data layer is ours; swap cost is days, not weeks); design velocity
(one FE on the critical path V1 — FE-02 covers ADM and picks up TD step 8+).

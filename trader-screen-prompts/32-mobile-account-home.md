# Screen 32 — Mobile: account home · app tab · F10 · V2.0

> Copy-able UI prompt for the Alpha One trader portal.
> Extracted from `trader-flows-and-screen-prompts.md` (Part 3).
> Source spec: `alpha-one/docs/16-trader-dashboard.md` and the owning module docs.

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

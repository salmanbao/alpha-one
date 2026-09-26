# Screen 34 — Mobile: credentials · app screen · F10 · V2.0

> Copy-able UI prompt for the Alpha One trader portal.
> Extracted from `trader-flows-and-screen-prompts.md` (Part 3).
> Source spec: `alpha-one/docs/16-trader-dashboard.md` and the owning module docs.

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

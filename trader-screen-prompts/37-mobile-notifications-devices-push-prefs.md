# Screen 37 — Mobile: notifications, devices & push prefs · app screen · F10 · V2.0

> Copy-able UI prompt for the Alpha One trader portal.
> Extracted from `trader-flows-and-screen-prompts.md` (Part 3).
> Source spec: `alpha-one/docs/16-trader-dashboard.md` and the owning module docs.

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

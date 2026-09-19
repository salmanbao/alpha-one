# 26 — MOB: Mobile App · JRN: Trading Journal · EDU: Education Hub · CHT: Community & Live Chat

> Covers PRD modules **MOB** (8 reqs, V2), **JRN** (8 reqs, V2/V3),
> **EDU** (9 reqs, V2/V3), and **CHT** (7 reqs, V2/V3). Four
> trader-experience satellites, all post-launch: they consume the same
> GW APIs TD uses (the 01 commitment: MOB consumes TD's backend, not a
> new one) and each is deliberately a **thin client over existing
> domains** — none of them owns a money path.

---

# Part A — MOB: Mobile App (8 reqs, V2)

## 1. Purpose & scope

Native iOS + Android companion (MOB-01/02): the trader's pocket
surface — portfolio at a glance, live account states, credentials,
payout status, KYC capture, push notifications. The PRD's V2 set:
native apps, **biometric login (MOB-04)**, **mobile KYC capture
(MOB-05)**, **mobile trade viewer (MOB-06)**, **push notifications
(MOB-03)**, mobile onboarding (MOB-07); V3: offline mode (MOB-08).

**Binding decisions:**
- **React Native** (the docs/00 catalog: "Native mobile companion
  (React Native)") — one codebase, the same TypeScript discipline, the
  same design tokens as TD (the `web/shared` design system ports to RN
  components; the FE-01/FE-2 split: the mobile surface is FE-01's V2
  work after the TD V1 hardening).
- **No new backend.** Every MOB screen is a GW API (the TD §3.1
  contract) + the SSE stream (the TD §3.2 live data, over the same
  endpoint; RN handles the WebSocket/SSE lifecycle with the same
  reconnect + polling-fallback pattern — MOBI-06's trade viewer is the
  TD chart island in a native window, TradingView's RN chart or the
  lightweight-charts webview — decision at build: prefer the native
  chart lib if it renders the same data shape, else a 1-line webview
  embedding the TD chart route — the data contract is identical either
  way).
- **Biometric login (MOB-04)** = the standard pattern: device
  Keychain/Keystore holds a local key that decrypts a **short-lived
  device token** (the Better Auth device-credential flow, V2) — the
  biometric unlocks the token, the token authenticates to the GW like
  any session; **re-login on token expiry** (7 d) with the full
  password + 2FA; a device loss = the session revoke (the AUTH §3.3
  deny-set — the trader's "log out all devices" covers it). The
  biometric never substitutes for the server-side session; it's a
  local-unlock convenience over a server-issued token.
- **Push notifications (MOB-03)** = the NOT delivery channel gains a
  `push` adapter (FCM/APNs — the NOT §2 channel abstraction, exactly
  what it was designed for): the same event → template mapping, the
  same dedupe (a push + an email for the same event is **one**
  notification unit with two channels — the trader's prefs (NOT-11)
  choose the mix), the same quiet hours. No new notification system.
- **Mobile KYC capture (MOB-05)** = the KYC-12 upload path with camera
  capture (the Veriff mobile SDK embed, the KYC-01 adapter's second
  client — Veriff supports mobile capture natively; our side is the
  same session API, the capture happens in Veriff's SDK, the documents
  land in the same R2 path). The KYC screen in MOB reuses the TD
  session lifecycle — a session started on the phone completes on the
  phone.
- **Offline mode (V3, MOB-08)** = cached read views only (the last
  known account state with a hard "offline — data from {time}" banner,
  the ANA-14 freshness rule applied to a phone pocket); **no offline
  writes, ever** (a payout request queued offline is a support-ticket
  factory; the rule: offline = read-only, clearly labeled).

Requirement coverage: `MOB-01,02,03,04,05,06,07` (V2) + `MOB-08` (V3).

## 2. Architecture

```
 React Native app (one codebase, iOS+Android)
   · auth: Better Auth device-credential flow (the biometric-unlocked
     token, §1) · the same GW, the same tenant subdomain (the app
     resolves the tenant from the login — a trader's session is
     tenant-bound like the web)
   · live data: the TD SSE endpoint (reconnect + polling fallback, the
     16 §3.2 pattern) · the same error contract (16 §6 client classes,
     ported)
   · push: FCM/APNs tokens registered with NOT (the `push` channel,
     token per device, the NOT-16 complaint rules apply to push too)
   · KYC: the Veriff mobile SDK (the KYC-01 adapter, second client)
   · store: MMKV/SQLite for UI prefs + the V3 offline cache (encrypted
     at rest — the keychain/keystore-wrapped key; no financial data in
     plain-text storage, the TD §10 "leaked profile must not leak
     equity" rule extends to a lost phone)
 push path: EVT → NOT (the mapping, the dedupe, the prefs, the quiet
   hours) → push channel adapter → FCM/APNs (deep links → the app
   screen, the same deep-link scheme as the TD routes)
```

## 3. System design (the screen set — mirrors TD, mobile-first)

| Screen | Source | Notes |
|---|---|---|
| Account home | LCC (the TD home card) | state badge + the key metrics + tick-age chip (the staleness honesty, 16 §3.2) |
| Live view | BRG read + SSE | the trade viewer (MOB-06): equity curve + positions; the chart decision per §1 |
| Credentials | LCC/BRG | the one-time reveal (2FA via the biometric-locked token + the server step-up — the reveal is the most-protected action in the app, the TD §3.5 SensitiveDialog pattern) |
| Payouts | PAY (11 §7) | the eligibility preview (TD-26), request (2FA), methods, receipts — the full TD payout surface |
| KYC | KYC (13 §7) | status + the Veriff mobile capture (MOB-05) |
| Documents | DOC (15 §7) | the same signed-URL download (the PDF opens in the system viewer) |
| Notifications | NOT (14 §7) | the in-app center (the NOT-07 store, V2) + the push preference (NOT-11) |
| Profile | AUTH | the device management (the logged-in devices list — the "log out all" is the phone-loss control, surfaced prominently), the prefs |

**Mobile-specific rules:** the app is **responsive-off** (it's a native
layout, not a web port — the design system's tokens, not its DOM);
the app is **update-gated** (a minimum API version check at launch —
the GW's error contract carries `min_client_version` on 426-class
responses, the app-store update nudge; a stale client can read but the
sensitive actions 426 with the update prompt — the version skew rule
from 04 §3.2 applied to clients); **no in-app browser for
money actions** (the Veriff embed is the exception — it's the provider's
audited surface; the rest is native or a deep link to the web).

## 4. Events (consumed — the same topics as TD)

`account.*`, `payout.*`, `kyc.*`, `document.*`, `notification.*` —
via the SSE (live) + the push channel (the NOT mapping decides which
events push: V2 default push set = the `critical`/`high` priorities
only (payout settled, breach, funding, KYC decision, security events)
— the prefs (NOT-11) extend it; the anti-spam rule: push is the
scarcest channel, the defaults are conservative, the trader adds
channels, not the other way around).

## 5. Lifecycles

- **Device token:** `registered (FCM/APNs token → NOT) → (app
  reinstall: re-registered, the old token dead-lettered by the
  provider) → revoked (the device management / the session revoke)`.
- **Biometric binding:** `enrolled (the device credential, 7-d token
  life) → re-auth (token expiry: full login) → unenrolled (biometric
  removed on device → falls back to the full login, the app detects
  the Keychain/Keystore change)`.
- **Offline cache (V3):** `populated (every successful read, TTL 24 h)
  → expired (the banner + the "refresh" is the only write) → purged
  (app uninstall / the "clear data")`.
- **KYC session (mobile):** the 13 §3.1 machine, the capture step is
  the Veriff SDK (the session state advances identically).
- **App version:** the `min_client_version` gate (§3) — the lifecycle
  is `current → outdated (read-only degraded) → blocked (update
  required for sensitive actions)`.

## 6. Error taxonomy

MOB presents the domain codes (no new server namespace). Client
classes (port of 16 §6 + the mobile specifics):

| Class | Trigger | UI |
|---|---|---|
| `device.token_expired` | 401 on the device-token flow | full login (the biometric path is re-enrolled after) |
| `min.client_version` | 426 | the update nudge (the store deep link) + the read-only banner |
| `push.token_invalid` | NOT-side dead letter | silent (the next push registration heals it) |
| `OFFLINE` | no network | the cache banner (V3) — never a blank screen, never a stale-without-label number |
| `chart.degraded` | the webview chart failed (if the webview path is chosen) | the native fallback: the numbers table (the chart is an enhancement, the numbers are the product) |
| `biometric.unavailable` | device without biometrics | the full login (the feature degrades, the app doesn't) |

## 7. API endpoints
> **Scope note:** MOB/JRN/EDU/CHT is not in the V1 execution sheet (V3 scope). There is no V1 baseline contract for this module; the surface below is design-level (post-V1, docs/99) and provisional until its phase's contract freeze.


**None new** — MOB consumes: the TD contract (16 §7), the AUTH
device-credential endpoints (V2: `POST /v1/auth/devices` (register,
returns the device token), `DELETE /v1/auth/devices/{id}` (the
device management), the token refresh), the NOT push-token endpoints
(`POST /v1/notifications/push-tokens`, the prefs API). The GW gains
one route class: `/v1/mobile/*` is **not** a new API — it's the same
routes with the mobile client's Accept/version headers (the
`min_client_version` check is a GW middleware, 04's chain, a new step
after the auth).

## 8. Schema (key shapes)

```jsonc
// POST /v1/auth/devices → 201 (the biometric binding, V2)
{ "data": { "device_id": "01J9DEV…", "label": "Ali's iPhone",
    "token": "dt_live_…", "token_expires_at": 1758886800000,
    "biometric": "face_id" } }

// push registration (NOT)
{ "data": { "registered": true, "device_id": "01J9DEV…",
    "platform": "fcm", "delivery": "critical_high" } }

// the offline-cache envelope (V3 — every read response gains this)
{ "data": { … }, "cache": { "stale_after": 86400000,
   "as_of": 1758282000000 } }
```

## 9. Database design

No new domain tables. The additions:

```sql
CREATE TABLE auth_devices (                        -- the V2 device
  id          ULID PRIMARY KEY,                    -- credential store
  identity_id ULID NOT NULL,
  tenant_id   ULID NOT NULL,
  label       TEXT, platform TEXT,                 -- (AUTH-owned — shown
  token_hash  TEXT NOT NULL,                       --   here for the
  biometric   TEXT,                                 --   contract; the
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),  --   table lives in
  last_seen_at TIMESTAMPTZ, revoked_at TIMESTAMPTZ,--   AUTH's schema,
  UNIQUE (identity_id, id)                         --   02 owns it)
);
CREATE TABLE push_tokens (                         -- NOT-owned
  id          ULID PRIMARY KEY,
  tenant_id   ULID NOT NULL,
  identity_id ULID NOT NULL,
  device_id   ULID NOT NULL,
  platform    TEXT NOT NULL,                        -- fcm|apns
  token       TEXT NOT NULL,                        -- (the token is
  active      BOOLEAN NOT NULL DEFAULT true,        --   provider-
  dead_at     TIMESTAMPTZ,                          --   opaque to us;
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()    --   field-encrypted
);                                                  --   like the PAY
                                                  --   method strings)
```

## 10. Security & compliance

- **The phone is a lost-device scenario** (the web is not): encrypted
  local store (the keychain/keystore-wrapped key — no financial data
  in plain storage, §1), the device management surface (the trader
  sees + revokes devices, the "log out all" is one tap), the session
  deny-set (AUTH §3.3) is the server-side backstop (a revoked token
  dies everywhere within one GW call, not on a sync), and the
  biometric token's 7-d life bounds the stale-credential window.
- **Push tokens are PII-adjacent** (they identify a device to a
  person): field-encrypted, the NOT-16 complaint path applies (a push
  complaint = the token dead-lettered + the suppression entry, the
  NOT §3.5 pattern), and push content obeys the NOT PII-var guard
  (the §14 NOT rule: no wallet strings in a notification banner —
  the banner shows "Payout settled — $2,633.04 — tap for receipt",
  never the address).
- **The KYC capture (MOB-05)** stays inside the Veriff SDK's
  audited surface (the images go Veriff → our R2 via the existing
  KYC-12 path — the app never holds a KYC document locally beyond
  the SDK's own secure storage during capture).
- **App-store compliance:** the ToS/privacy in-app (the CMS-08 legal
  pages render in-app — the version citation, the 24 Part A §3.4
  rule), the "not a broker" disclosure on the account screens (the
  prop-firm app-store posture — the app sells a challenge, it does
  not execute trades; the MT5 login is the trader's own broker
  relationship), data-deletion on account close (the 13 §10
  retention + the device store purge on logout-all).
- **No offline writes** (the §1 rule) — an offline "request" is a
  local draft (explicitly labeled, never sent silently later — the
  auto-send-later pattern is banned: a payout request that fires
  while offline-then-online is a surprise; the draft requires a
  deliberate send).

## 11. Scalability considerations

- The app multiplies the read clients (a trader with phone + web =
  2× the SSE sessions + 2× the API reads) — the GW + the read models
  absorb it (16 §11's SSE scaling story applies: the relay reads
  Redis Streams, the SSE writers scale); the V2 target (50k
  registered traders, ~10% DAU on mobile ≈ 5k concurrent sessions
  peak) is 5× V1 web — the same design, more instances.
- Push volume: the conservative default set (§4 — critical/high
  only) keeps FCM/APNs volume at ~2× the email volume; the NOT
  rate limits (14 §3.6) apply per channel.
- The Veriff mobile SDK: provider-hosted (their infra), our side is
  the session API (no added load).
- Chart: the data shape is the TD's (1-min points + SSE appends) —
  the rendering cost is on-device; the download is the same ~60
  initial points + the live frames.
- **The app is the V2 retention surface** (the push notification is
  the "you're funded — start trading" moment that email can't
  deliver) — the investment is the trader's habit, the engineering
  is the thin client over existing contracts.

## 12. Open-source solutions

| Option | Verdict |
|---|---|
| **React Native (docs/00 catalog)** | **CHOSEN** — one TS codebase with the web team, the design-system tokens port, the FE-01 continuity |
| Flutter (the alternative) | Rejected: a second language (Dart) for a team that's TS across web + a small RN surface; the team-velocity argument wins |
| TradingView chart (RN) or the TD webview | Decision at build (§1): the data contract is identical; the webview is the 1-line fallback |
| FCM / APNs (push) | CHOSEN (the platform defaults; the NOT push adapter is the seam) |
| Veriff mobile SDK (MOB-05) | CHOSEN (the KYC-01 adapter's second client — the provider's audited capture surface) |
| MMKV/SQLite (local store) | CHOSEN (encrypted-at-rest with the keystore key) |

## 13. Technology stack

React Native + TypeScript, the `web/shared` design tokens (ported
components), TradingView (chart, per §12), FCM/APNs, the Veriff
mobile SDK, Better Auth (device credentials), the GW (no new API —
the version middleware is the only server change), Sentry (the RN
SDK — crash reporting with the tenant + device context, the PII
rules of 16 §10 apply to crash breadcrumbs: no financial values in
exception payloads), the CI: the app builds in the GitHub Actions
pipeline (the 06 CI gains the mobile jobs — the EAS/CI build +
store uploads are the DevOps workstream).

## 14. Integration — internal modules (glue)

| Module | How |
|---|---|
| **GW** | the same routes; the `min_client_version` middleware step (04's chain); the device-token auth is a session class (the GW doesn't distinguish it — the token authenticates like a cookie) |
| **AUTH** | the device-credential flow (V2: the 02 schema gains `auth_devices`), the session revoke covers devices, the anomaly scoring sees device logins (a new device = the +score input, the 02 §3.7 rule) |
| **TD (API)** | the entire data contract (16 §3.1) — MOB is a second client, the TD doc is its API spec |
| **NOT** | the `push` channel adapter (the §2 path), the push-token store, the prefs (NOT-11's channel list gains `push`), the dedupe (one unit, N channels) |
| **KYC** | the Veriff mobile SDK client (the KYC-01 adapter), the session lifecycle shared with the web (start on phone, the docs land in the same R2 path) |
| **LCC/BRG/PAY/DOC** | via the TD contract — no direct coupling (the app calls the same endpoints a web client calls; a bug that affects MOB affects TD identically — the shared contract is the safety property) |
| **EVT** | the SSE relay (the same endpoint; the app's reconnect pattern is the TD-11 fallback) |
| **ANA** | the app-version adoption stats (the min_client_version gate's analytics — how many traders are on the outdated client), the push-delivery KPIs (the NOT-22 dashboard gains the push channel) |
| **CMS** | the in-app legal pages (the 24 Part A renderer's content, the same API) |
| **SUP** | the app's "contact support" carries the device + version context (the SUP pre-fill, 16 §3.3 pattern — a mobile bug report names the app version, not a guess) |

## 15. Integration — external tools

FCM + APNs (push), the Veriff mobile SDK, Apple/Google app stores
(the distribution — the store-review posture: the "not a broker"
language, the in-app ToS, the data-deletion proof), Sentry, the
GitHub Actions mobile jobs (the 06 CI), the keychain/Keystore
(platform-native).

## 16. Implementation blueprint (V2)

| Step | Owner | Est | Depends | Exit criteria |
|---|---|---|---|---|
| 1. RN scaffold + the design-system port (tokens, the badge/card/dialog components) + auth (login, 2FA, the device-credential flow with biometric) + the version-gate middleware (GW) | FE-01 + BE-1 | 4 wks | AUTH V2 (device credentials), the TD contract stable | a trader logs in with the biometric on a real device; the token expiry forces a full re-login (the 7-d boundary tested); an outdated client is read-only-degraded (the 426 path) |
| 2. The core screens (home, live view + chart decision, credentials reveal, documents, profile + device management) over the TD contract + the SSE + the polling fallback | FE-01 | 4 wks | 1, the TD SSE live | the app shows a live funded account (the chart appends, the staleness chip works, the kill-stream test → polling fallback, same as TD) |
| 3. Payouts (the full TD surface) + KYC (status + the Veriff mobile capture) + the SensitiveDialog port (the step-up on the device) | FE-01 | 3 wks | 2, PAY/KYC V2 stable | a payout request + a KYC L2 verification completed end-to-end on a phone in staging |
| 4. Push (the NOT `push` adapter, FCM/APNs, the deep links, the conservative default set, the prefs) + the in-app notification center (the NOT-07 store) | BE-1 + FE-01 | 3 wks | 2–3, NOT V2 (the channel abstraction) | a payout-settled event → one push (the dedupe: no email+push double for the same unit on a push-only pref) + the deep link lands on the receipt; quiet hours respected |
| 5. Onboarding (MOB-07: the app-store → login → the first-account tour) + the store assets + the review posture (the ToS in-app, the disclosures) + crash reporting (Sentry, the PII breadcrumb rules) | FE-01 + DevOps | 2 wks | 2–4 | the app passes a store-review pre-check (the compliance checklist: disclosures, data deletion, the "not a broker" lines) — a testflight build to the FunderBlu team |
| 6. Store submission (TestFlight/Play internal → the V2 launch cohort) + the version-adoption dashboard (ANA) + the offline read-only cache (V3 MOB-08, if the V2 scope allows early) | FE-01 + DevOps | 2 wks | 5 | the FunderBlu team runs on the app; the adoption dashboard shows version distribution; (if early) the offline cache shows the TTL-labeled banner |

**Risks:** the app becoming a second product surface with divergent
behavior (mitigation: the shared contract rule — no new endpoints, the
TD doc is the spec, a MOB-only API is a code-review red flag);
store-review friction (the prop-firm category + the "not a broker"
posture — the §10 checklist is prepared in step 5, not at submission);
push fatigue (the conservative defaults + the prefs + the NOT-16
complaint path — the §4 rule: the trader adds channels, not the
platform); device-security incidents (a lost phone — the §10 stack:
encryption, the device management, the deny-set, the 7-d token
bound; the incident runbook entry in 06: "trader reports lost device"
= the deny-set flush + the forced reset, a 5-minute ops action);
team split (FE-01 on mobile while ADM V2 lands on FE-1/FE-2 — the
design-system port is what makes the split safe, the same `web/
shared` source of truth).

---

# Part B — JRN: Trading Journal (8 reqs, V2/V3)

## 1. Purpose & scope

The trader's **private** journal: trade logging (JRN-01), screenshot
attachments (JRN-02), tags & strategies (JRN-03), journal analytics
(JRN-04), the daily review (JRN-05), trade replay (JRN-06, V3),
export (JRN-07), replay sharing (JRN-08, V3).

**The one-sentence design:** the journal is a **trader-owned
annotation layer over their own trading history** — it stores the
trader's notes/tags/screenshots keyed to deals/positions that
**already exist in BRG** (the journal never re-stores trade data; it
references it). The journal is **private by default** (JRN-08 sharing
is an explicit, per-entry, revocable action — the default is no
sharing, and shared entries expose the deal facts + the trader's
note, never the broker credentials or the account's other data).

Requirement coverage: `JRN-01,02,03,04,05,07` (V2) + `JRN-06,08` (V3).

## 2. Architecture

```
 trader (TD "Journal" section — the JRN surface lives in TD, not a
 separate app: it's a trader-content section like Documents):
   · entries: a note (markdown) + tags + a screenshot (R2, tenant-
     prefixed, the 10 MB limit) keyed to {account_id, deal_id? /
     position_id? / "account-day" (the daily review is
     account+day-keyed, no deal)}
   · the deal facts render from BRG's read API at view time (the
     journal entry stores the deal_id + a snapshot of the key fields
     at write time (price, PnL — the EVL-49 observed values — so a
     journal entry still makes sense if the BRG data ages out; the
     snapshot is labeled "as recorded")
 analytics (JRN-04): the journal's own aggregate (PnL by tag/strategy,
   win rate by day-of-week/hour — computed from the BRG deals + the
   entry tags; the read-model pattern: a `journal_stats` table
   rebuilt on entry change + nightly over the deals — the ANA-01
   substrate, trader-scoped)
 daily review (JRN-05): a per-account-day checklist surface (what
   went right/wrong, the screenshot, the plan-for-tomorrow) — the
   streak metric (the gamification-adjacent number that stays in
   the journal, not the CMP level system — §24 Part B's
   no-money-gating rule: the streak is a journal stat, nothing
   else reads it)
 replay (V3 JRN-06): a read-only reconstruction of the day's deals
   (the BRG deals + the equity_points curve, 19 §3.1 — the replay is
   a rendering of existing data: the deals timeline + the equity
   path + the journal entries overlaid; no new data is created)
 sharing (V3 JRN-08): a per-entry share link (R2-class: a short
  signed URL, 30-day TTL, revocable — the shared page shows the
  entry + the deal snapshot, the trader's chosen display name
  (the CMP-11 handle), and nothing else; the share is audited
  (AUD low tier — it's the trader's own content, the audit is for
  the platform's integrity: "this shared link existed"))
 export (JRN-07): CSV/JSON of entries + the stats (the ANA-11
   export pattern, trader-scoped, self-serve in TD)
```

## 3. System design

### 3.1 The entry model

```
journal_entries:
  id · tenant_id · identity_id · account_id
  deal_id? (BRG ref) · position_id? · day_key? (the daily-review
    entries: date-only, account-scoped)
  kind (trade_note|daily_review)
  body (markdown, sanitized like the CMS-03 rule — the renderer is
    the trust boundary, no raw HTML)
  tags [] (the trader's own taxonomy — free tags, the JRN-03
    strategy labels; the tag list is per-trader, the analytics
    group by it)
  screenshot_ref? (R2 key)
  deal_snapshot (the as-recorded fields: symbol, side, volume,
    entry/exit price, PnL cents, at — the EVL-49 observed values;
    NULL for daily reviews)
  created_at · updated_at (the entry is the trader's content —
    editable, unlike the audit trail; the edit history is a
    lightweight versions array (last 5) — the journal is a diary,
    not an evidence record; the evidence record is BRG/EVL)
```

**The privacy rules:** entries are visible to the trader only
(structurally: the TD journal API is identity-scoped, no ADM/CON
read path exists in V2 — staff support (SUP) sees a journal entry
only if the trader attaches the link in a ticket, the trader's
choice); the screenshot is a PII-adjacent upload (the trader might
screenshot their own MT5 terminal — the file is stored, never
processed for content, the V2 ClamAV scan (18 §3.5) applies, and
the 10 MB limit); the journal data retention = the trader's account
lifetime + 90 d (the trader's content, not the platform's financial
record — a shorter class than the 7-yr financial docs; the deletion
runs on account close + 90 d, audited).

### 3.2 The analytics (JRN-04)

`journal_stats` (trader-scoped read model, the ANA-01 pattern):
rebuilt on entry change (incremental) + nightly (the deals join):
PnL by tag, by day-of-week, by hour-of-day (the broker-TZ hours —
the ADR-12 clock rule), the streak (the daily-review consecutive
days), the screenshot rate (a fun metric the trader themselves will
find useful: "I journal more after wins"). The queries are
trader-scoped (never cross-trader — the journal analytics are
personal; the platform never aggregates journal content, the
privacy line: **no cross-trader journal analytics, ever** — the
data is personal notes, the platform's job is to return it to its
owner, not to study it).

### 3.3 Replay & sharing (V3)

- **Replay (JRN-06):** the read-only reconstruction (§2) — the
  rendering is the equity_points curve + the deals markers + the
  entry overlays; the data is all existing (BRG + ANA + the
  journal); the replay is a TD route (the trading-view's sibling,
  the 16 §3.2 chart island, a time-range parameter).
- **Sharing (JRN-08):** the per-entry share link (§2) — the
  revocation is a JWT-style token check (the token row:
  `journal_shares {id, entry_id, token_hash, expires_at, revoked_at}`
  — a revoked token 404s immediately (the next request, the
  server-side check, no client-side trust)); the shared page is
  public-but-token-gated (the link is the permission), the content
  is the entry + the snapshot + the display name (the CMP-11
  handle, the masked default rule extends: the share never
  includes the real name, the account number, or the broker
  credentials — the field list is allowlisted in the renderer).

## 4. Events (topic `journal`)

| Event | When | Consumers |
|---|---|---|
| `journal.entry_created/updated` | the trader writes | AUD (low tier — the trader's content event; the sensitive-read audit applies if staff ever see it via a ticket), ANA (the stats rebuild trigger) |
| `journal.entry_deleted` | the trader deletes | AUD (low), ANA |
| `journal.share_created/revoked` (V3) | the sharing actions | AUD (low) |

Consumes: nothing new (the nightly stats job reads BRG deals + ANA
equity_points directly — the journal is a reader of the trading
data, the trading data doesn't know the journal exists — the
loose-coupling rule: the journal is optional, a journal bug never
touches the trading path).

## 5. Lifecycles

- **Entry:** `created → (edited ×, the 5-version history) → deleted
  (the trader's right, immediate) → (account close + 90 d) archived/
  deleted (the retention job, audited)`.
- **Screenshot:** `uploaded (ClamAV scanned, the 18 §3.5 pattern) →
  (referenced) → orphaned (with its entry) → deleted (the retention
  job)`.
- **Stats:** `incremental + nightly rebuild` (the ANA-21
  reconciliation applies: the stats are re-derivable from the
  entries + the deals — a stats row that can't be recomputed is a
  bug, the same rebuildable-read-model rule, 19 §2).
- **Share (V3):** `created (30-d TTL) → (revoked: immediate 404) →
  expired`.
- **Replay (V3):** stateless (a render of existing data — no
  lifecycle).
- **Tag:** the trader's free taxonomy (no lifecycle; the stats
  group by the current tag set — a re-tag re-keys the stats on the
  next rebuild, the "as recorded" label on the entry's snapshot
  keeps the history honest).

## 6. Error taxonomy

Namespace `JRN`:

| Code | HTTP | Meaning |
|---|---|---|
| `jrn.entry_not_found` | 404 | (ownership: 404, the 04 posture) |
| `jrn.deal_not_found` | 422 | An entry keyed to a deal that doesn't exist (the BRG read returned nothing — the entry still saves with `deal_snapshot: null` + the flag; a journal entry pointing at nothing is allowed, labeled — the trader's note survives the data gap, the honesty rule) |
| `jrn.screenshot_invalid` | 422 | Type/size (the 10 MB, the image types) |
| `jrn.screenshot_unscanned` | 200 + flag | The V2 scan pending (the view shows "scanning" — the 18 §3.5 pattern) |
| `jrn.share_revoked` | 404 | The shared link is dead (the page: "this share is no longer available" — no leak of why) |
| `jrn.export_limit` | 429 | The self-serve export cap (1/day — the ANA-11 pattern) |
| `jrn.stats_stale` | 200 + label | The stats `as_of` is old (the nightly hasn't run — the ANA-14 freshness label, the 19 §2 rule) |

## 7. API endpoints

Trader (TD — the journal is a TD section):
`GET /v1/journal/entries?account=&from=&to=&tag=`,
`POST /v1/journal/entries` `{account_id, deal_id?, day_key?, body,
tags[], screenshot_id?}`,
`GET /v1/journal/entries/{id}` (+ `PATCH` (edit, the version
bump), `DELETE`),
`POST /v1/journal/screenshots` (upload → the R2 + the scan queue),
`GET /v1/journal/stats?account=&range=` (the JRN-04 aggregates),
`GET /v1/journal/replay?account=&day=` (V3 — the render data),
`POST /v1/journal/entries/{id}/share` (V3 → `{url, expires_at}`),
`DELETE /v1/journal/entries/{id}/share` (V3 — revoke),
`GET /v1/journal/export` (the JRN-07 self-serve),
public: `GET /v/journal/{share_token}` (V3 — the shared page,
rate-limited, the allowlisted content).

## 8. Schema (key shapes)

```jsonc
// POST /v1/journal/entries → 201
{ "data": { "id": "01J9JRN…", "account_id": "01J9ACC…",
    "kind": "trade_note", "body": "Held the long through the spread
    blowout — the rule said stop, I didn't. Not doing that again.",
    "tags": ["news", "discipline"],
    "deal_snapshot": { "symbol": "EURUSD", "side": "buy", "volume": 0.5,
      "entry": "1.16420", "exit": "1.16580", "pnl_cents": 8000,
      "at": 1758282000000 },
    "screenshot_ref": "journal/{tenant}/01J9JRN…/1.jpg" } }

// GET /v1/journal/stats
{ "data": { "as_of": 1758282150000,
    "by_tag": [ { "tag": "news", "pnl_cents": -42000, "trades": 18 },
                { "tag": "trend", "pnl_cents": 128000, "trades": 41 } ],
    "by_hour": [ … ], "daily_review_streak": 6,
    "screenshot_rate": 0.34 } }
```

## 9. Database design

```sql
CREATE TABLE journal_entries (
  id            ULID PRIMARY KEY,
  tenant_id     ULID NOT NULL,
  identity_id   ULID NOT NULL,
  account_id    ULID NOT NULL,
  deal_id       TEXT,                          -- the BRG ref (the snapshot
  day_key       DATE,                          --   is the as-recorded truth)
  kind          TEXT NOT NULL
    CHECK (kind IN ('trade_note','daily_review')),
  body          TEXT NOT NULL,
  tags          TEXT[] NOT NULL DEFAULT '{}',
  screenshot_ref TEXT,
  deal_snapshot JSONB,                         -- the §3.1 fields
  versions      JSONB NOT NULL DEFAULT '[]',   -- the last-5 edit history
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_jrn_trader ON journal_entries(tenant_id, identity_id, created_at DESC);
CREATE INDEX idx_jrn_account ON journal_entries(tenant_id, account_id, created_at DESC);
CREATE INDEX idx_jrn_tag ON journal_entries USING gin (tags);

CREATE TABLE journal_stats (                    -- the rebuildable read model
  id            ULID PRIMARY KEY,
  tenant_id     ULID NOT NULL,
  identity_id   ULID NOT NULL,
  account_id    ULID,
  bucket        TEXT NOT NULL,                  -- 'tag'|'hour'|'dow'|'streak'
  key           TEXT NOT NULL,
  value         JSONB NOT NULL,
  as_of         TIMESTAMPTZ NOT NULL,
  UNIQUE (tenant_id, identity_id, account_id, bucket, key, as_of)
);
CREATE TABLE journal_shares (                   -- V3
  id            ULID PRIMARY KEY,
  entry_id      ULID NOT NULL REFERENCES journal_entries(id),
  token_hash    TEXT NOT NULL UNIQUE,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  expires_at    TIMESTAMPTZ NOT NULL,
  revoked_at    TIMESTAMPTZ
);
```

## 10. Security & compliance

- **Private by default, structurally** (§3.1): the TD API is
  identity-scoped, no staff read path in V2 (the SUP-adjacent
  access is the trader's own link-sharing, §3.3), and the
  **no-cross-trader-analytics rule** (§3.2 — the platform never
  aggregates journal content; the ANA read models exclude the
  journal tables by design — a CI property test asserts the ANA
  queries never reference `journal_*` tables, the 24 Part B
  no-money-gating test's sibling).
- **Screenshots are unprocessed uploads** (the §3.1 rule: stored +
  scanned, never content-parsed — the platform doesn't read the
  trader's screenshots; the ClamAV scan is a security control, not
  a content feature; the OCR idea is explicitly rejected — it
  would make the journal a PII surface the platform reads).
- **The sharing allowlist** (§3.3): the shared page's field list is
  code-reviewed + a property test (seed an entry with max-PII
  context → the shared page renders only the allowlist — the NOT
  PII-guard pattern, 14 §3.3, applied to sharing).
- **The edit-vs-evidence line** (§3.1): the journal is editable
  (it's a diary) but the `deal_snapshot` is labeled "as recorded"
  (the BRG/EVL data is the evidence — a journal entry is a
  trader's claim + their context, the disputes (RSK-41, 09 §10)
  run on the engine's records, never on the journal — the
  journal has zero weight in any enforcement, the design rule
  stated in the UI: "your journal is for you; enforcement uses
  the trading records").
- **Retention** (§3.1): account lifetime + 90 d (the personal-content
  class), the deletion audited, the screenshot lifecycle with the
  entry.
- **The streak metric** (§3.1): a journal stat only (nothing else
  reads it — the gamification separation, 24 Part B's rule).

## 11. Scalability considerations

- Journal volume: ~5-20 entries/trader/week at engagement (the
  journal's growth is a product metric, not an infra one) —
  50k traders × 10/week ≈ 26M entries/yr worst case, realistically
  < 5% engagement = < 1.3M/yr — PG is fine (the (tenant,
  identity) index is the hot path; the tag GIN index for the
  analytics).
- The stats rebuild: incremental (on entry change: a few tag-bucket
  updates) + nightly (the deals join over the day's deals) —
  seconds per trader, the nightly batch is the ANA-worker pattern
  (advisory-lock, the 06 jobs) at ~5k engaged traders ≈ minutes.
- Screenshots: 10 MB × ~1/entry × 1.3M/yr ≈ 13 TB/yr worst case —
  the R2 lifecycle (with the entry retention) + the 10 MB limit +
  the image-type restriction keep it bounded; the realistic
  (30% screenshot rate) ≈ 4 TB/yr — the R2 cost line in the BIL
  pass-through (the storage meter, 22 §3.1) shows the tenant the
  number.
- Replay (V3): a read of equity_points + the deals (the existing
  data, the existing indexes) — the render cost is on the client;
  no new storage.
- The sharing page (V3): one indexed token lookup + the cached
  entry — trivial (rate-limited, the public-surface pattern from
  24 Part A).

## 12. Open-source solutions

| Option | Verdict |
|---|---|
| **In-house (the TD section + the rebuildable stats)** (this design) | **CHOSEN** — the journal is annotations + one read model over existing data; there's no OSS journal to integrate (every trading-journal SaaS is its own account world — the "keyed to our deals" property is the product, and it's ours) |
| TradingView's journal (their product) | Rejected: it lives on their platform, keyed to their data; our journal is keyed to our BRG deals + tenant-scoped + private-by-default |
| ClamAV (screenshots, the 18 pattern) | CHOSEN |
| (Replay) the existing equity_points + deals | CHOSEN — the replay is a render, §3.3 |

## 13. Technology stack

The TD section (Next.js 15, the 16 stack), Postgres (entries/stats/
shares), R2 (screenshots, tenant-prefixed), BRG (the deal reads +
the snapshot source), ANA (the equity_points for the replay, the
rebuild job pattern), ClamAV (V2, the 18 worker), NOT (no
notifications — the journal is silent by design; a "your streak hit
30" nudge is a V2-late product decision, default off), Prometheus
(entry volume, the stats rebuild runtime, the share hit rate),
Sentry.

## 14. Integration — internal modules (glue)

| Module | How |
|---|---|
| **BRG** | the deal reads (the entry keying + the snapshot fields) — the journal is BRG's read client (the same read API the TD positions tab uses, 08 §7) |
| **ANA** | the equity_points (the V3 replay's curve) + the rebuildable-read-model pattern for `journal_stats` (the 19 §2 discipline: re-derivable, labeled `as_of`) |
| **TD** | the host surface (the §1 rule: a section, not an app) |
| **R2** | the screenshot store (the tenant-prefix isolation, the 10 MB, the lifecycle with the entries) |
| **AUD** | the low-tier entry events (the trader's content lifecycle, the audit exists for the platform's integrity — the "this entry existed/was shared" record) |
| **SUP** | the trader's choice: a journal link in a ticket (the trader shares, the platform doesn't read — §10) |
| **EVL/RSK** | **none** — the journal has zero weight in evaluation or enforcement (§10, the stated design rule) — the absence is the property (the CI test that no EVL/RSK code path reads `journal_*`) |
| **CMP** | the display name (the JRN-08 shared page shows the CMP-11 handle — the public identity, the masked default) |
| **BIL** | the storage meter (the screenshot volume in the tenant's storage line, 22 §3.1) |

## 15. Integration — external tools

R2, ClamAV (V2), Prometheus/Grafana, Sentry.

## 16. Implementation blueprint (V2)

| Step | Owner | Est | Depends | Exit criteria |
|---|---|---|---|---|
| 1. Schemas (entries/stats/shares-later) + the entry CRUD (the deal snapshot at write, the edit versions) + the TD section shell | FE-01 + BE-2 | 2 wks | the TD stable, BRG read API | a trader keys a note to a deal; the snapshot survives (delete the BRG row in a test DB → the entry still renders the "as recorded" snapshot) |
| 2. Screenshots (upload, the ClamAV queue, the unscreened flag, the R2 lifecycle) + tags + the markdown render (the sanitize pass) | FE-01 + BE-2 | 2 wks | 1, the 18 ClamAV worker | a screenshot uploads → scans → renders; a seeded infected file is quarantined (the 18 §3.5 test reused); the property test: no raw HTML in the render |
| 3. The stats (the rebuildable `journal_stats`, the incremental + nightly jobs, the `as_of` labeling) + the JRN-04 screen (by-tag/hour/dow + the streak + the screenshot rate) | BE-2 + FE-01 | 2 wks | 1–2, the ANA worker pattern | the stats match a hand-computed fixture (the recompute property, the 19 §3.4 test); a stale stats render shows the label, not a wrong number |
| 4. The daily review (the day-keyed entries + the streak) + the export (JRN-07, the ANA-11 self-serve pattern) + the retention job (account close + 90 d, audited) | FE-01 + BE-2 | 2 wks | 3 | a 30-day review history renders; the export CSV round-trips (import the fixture, export, diff = 0); a closed account's journal deletes on schedule (the deletion audit row exists) |
| 5. V3: the replay (the equity_points + deals render, the entry overlays) + the sharing (the token links, the revocation, the allowlist property test, the public page) | BE-2 + FE-01 | 3 wks | 3–4, the ANA feed | a replay renders a seeded day (the curve + the markers + the notes); a share link works, revokes to a 404 on the next request, and the property test proves the allowlist (max-PII seed → allowlist-only render) |

**Risks:** zero engagement (the journal is a retention feature that
only works if traders use it — the product bet: the daily review +
the streak + the "what I learned" loop; the mitigation is scope
discipline (no features beyond the PRD's 8), not feature bloat);
privacy incidents (a screenshot leak — the §10 stack: R2 tenant-
prefix isolation, no content parsing, the sharing allowlist, the
retention job; the incident runbook entry: "journal screenshot
exposed" = the R2 prefix audit + the affected-trader notice, the
KYC-doc-class response, 13 §10); the journal-vs-evidence
confusion (a trader arguing from their journal in a dispute — the
§10 design rule stated in the UI + the support canned response
(SUP-20) + the SUP-33 flow that routes the dispute to the engine's
records; the journal is a diary, the engine is the court); the stats
drift (the rebuildable pattern + the `as_of` label — the 19 §3.4
machinery reused, not reinvented).

---

# Part C — EDU: Education Hub (9 reqs, V2/V3)

## 1. Purpose & scope

The tenant's education surface: the course library (EDU-01), video
lessons (EDU-02), quizzes (EDU-03), progress tracking (EDU-04),
completion certificates (EDU-05), the lesson-completion events
(EDU-07), learning paths (EDU-08), enrollment (EDU-09); V3: admin
course authoring (EDU-06).

**The one-sentence design:** EDU is **content + progress**, hosted on
the platform for the tenant's brand — the content is tenant-owned
(R2 media + PG content), the progress is per-trader (the read-model
pattern), and the certificate is the DOC pipeline (the completion
certificate is a DOC-15-class object with the QR verify — the
"verified: completed FunderBlu's Risk Management course" credential
that the trader's public profile (the CMP-11 handle) can display).
EDU is **not** a trading-advice surface: the content is the tenant's
educational material (the "how prop-firm rules work" class), the
platform provides no financial advice (the ToS line, the CMS-08
template extends to the EDU disclaimer block).

Requirement coverage: `EDU-01,02,03,04,05,07,08,09` (V2) + `EDU-06`
(V3).

## 2. Architecture

```
 content (tenant-owned, the tenant staff manages in ADM V2; the
   V3 EDU-06 authoring is the full editor — V2 is the import/seed
   flow: the tenant provides their existing course material (the
   FunderBlu onboarding content), the platform structures it):
   · courses: {tenant, title, description, blocks[]} where a block
     = {video (R2, the streaming — R2 + Cloudflare's streaming
     delivery, the 24 Part A media pattern), text (markdown, the
     CMS-03 sanitize rule), quiz (the EDU-03 object), duration}
   · paths (EDU-08): an ordered set of courses (the "funded-trader
     onboarding path" — the tenant's recommended sequence)
   · the video is R2-streamed (the signed-URL pattern, the 15-min
     TTL, the tenant-prefix isolation; the playback is a standard
     <video> with the MP4/HLS the tenant provides — no transcoding
     in V2 (the tenant provides web-ready files; the HLS option is
     the V3 authoring's upload pipeline, the ffmpeg job in the
     workers process))
 learner (trader, the TD "Learn" section — the JRN-adjacent trader
   section, the same pattern: a section in TD, not a new app):
   · enrollment (EDU-09): a path or a course (the enrollment is
     explicit — the progress tracking is honest: enrolled →
     in-progress → completed; the auto-enrollment option is
     tenant-config (the "new funded traders auto-enroll in the
     onboarding path" is the FunderBlu default — the enrollment
     event is the NOT-adjacent nudge, the trader's choice to
     proceed)
   · progress (EDU-04/07): per-lesson completion (the video:
     90% watched + the quiz: passed — the completion criteria are
     per-block type, the tenant's config; the `lesson_completed`
     event (EDU-07) fires on the criteria met — the event is the
     glue: the CMP gamification (a badge for "completed the
     onboarding path", the 24 Part B badge pattern) and the ANA
     funnel (the "educated" stage — the correlation: do educated
     traders breach less? the ANA-15 cohort question, V3) read the
     event, EDU emits it
   · the quiz (EDU-03): the MCQ/TF object (the questions are
     tenant content; the answers are server-checked (the quiz
     submit is an API call — the client never sees the answer key
     before submission, the standard pattern); the retake policy
     (the tenant config: unlimited / 3 attempts)
   · the certificate (EDU-05): on path completion → the DOC
     pipeline (the `course_certificate` type, the DOC-15 QR
     verify extends — the public verify page: "verified: {name-
     masked} completed {course}, {tenant}, {date}"; the badge on
     the public profile (the CMP-11) shows the verified mark)
```

## 3. System design

### 3.1 The content model

```
edu_courses: id · tenant_id · title · slug · description ·
  status (draft|published|archived) · order (the library order) ·
  est_minutes · created/published (the CMS-14 versioning pattern
  applies: published = the live pointer, the drafts are edit-safe —
  the CMS §3.2 discipline reused, the content rows are
  `edu_course_blocks {course_id, version, block_type
  (video|text|quiz), data}`)
edu_quiz: id · block_ref · questions [{q, options[], answer_idx,
  explanation}] · pass_pct · max_attempts
edu_paths: id · tenant_id · name · course_ids[] (ordered) ·
  auto_enroll (the tenant config flag)
edu_enrollments: id · tenant_id · identity_id · course_id? ·
  path_id? · state (enrolled|in_progress|completed|dropped) ·
  started_at · completed_at
edu_progress: id · enrollment_id · block_id · state
  (not_started|in_progress|completed) · video_pct · quiz_attempts ·
  quiz_best_pct · completed_at
  (the EDU-07 event fires on block state → completed)
```

**The media rules:** the video files are the tenant's (they provide
the MP4/HLS; the platform stores + streams — the R2 streaming with
the signed URLs, the 24 Part A pattern; the playback never buffers
the whole file client-side — the standard streaming, the 10 MB
upload limit doesn't apply to video (the video is the R2 large-
upload, the multipart, the tenant-staff upload surface in ADM —
the 5 GB/file cap, the content-type restriction `video/*` only));
the video is **never** transcoded in V2 (the tenant provides
web-ready files — the authoring V3 adds the ffmpeg pipeline); the
playback URL is signed + 15-min + the tenant-prefix isolated (the
13/15 R2 rules); a course video is **not** hotlinkable (the signed
URL + the tenant prefix + the rate limit on the media route — the
content is the tenant's IP, the platform's job is to protect it as
much as the R2 isolation allows).

### 3.2 The completion criteria (the honesty part)

Per block type (the tenant config per course):
- **video:** 90% watched (the client reports the playback position
  to the progress API — the server accepts the max position, the
  anti-skip: a position that jumps backwards or the video ends
  before 90% → the block is `in_progress` not `completed`; the
  client-side % is a claim, the server stores the max claimed % and
  marks completion at ≥ 90% + the `ended` event — the pragmatic
  middle: the platform can't verify video watch-time beyond the
  client's claims (no DRM in V2), so the criterion is "the client
  claims 90%+ and the video ended" — the labeled posture: EDU
  completion is **self-attested playback**, the certificate says
  "completed" not "verified watching" — the honesty over the
  illusion; the V3 option: the periodic-checkpoint quizzes
  (a quiz block mid-video — the tenant can require it, the
  server-checked, the real gate) — the FunderBlu onboarding path
  uses the checkpoint-quiz version, the honest gate where it
  matters)
- **text:** the "mark as read" (the explicit action — the text
  block completes on the trader's click, the labeled
  self-attestation)
- **quiz:** the pass_pct (the server-checked — the real gate) +
  the retake policy
- **path:** all blocks completed (the path completion = the
  certificate trigger)

**The certificate's claim is bounded by the gates it passed** (the
UI: the certificate shows the course name + the completion date +
the verify link — it never claims "assessed competence" unless the
course was quiz-gated (the tenant's course config decides the
claim level: `self_attested` vs `quiz_gated` — the certificate
text reflects it: "completed" vs "completed (assessed)"). The
anti-design: a certificate that implies a qualification it didn't
test (the compliance line: EDU certificates are **completion
records**, not credentials — the ToS + the certificate footer say
so).

### 3.3 The events & the glue

`edu.lesson_completed` (EDU-07) — the block completion (the badge
glue, the ANA funnel stage); `edu.course_completed` /
`edu.path_completed` (the certificate trigger + the profile
badge); `edu.enrolled` (the auto-enroll audit + the NOT nudge).
Consumes: `account.funded` (the auto-enroll trigger, the tenant
config), the CMP badge events (the reverse: the EDU completion is
a badge input, the 24 Part B pattern).

## 4. Events (topic `edu`)

| Event | When | Consumers |
|---|---|---|
| `edu.enrolled` | enrollment (explicit or auto) | NOT (the nudge, the tenant config), AUD (low) |
| `edu.lesson_completed` (EDU-07) | a block completes | CMP (the badge inputs), ANA (the "educated" funnel stage), AUD (low) |
| `edu.course_completed` / `edu.path_completed` | the course/path done | DOC (the certificate trigger), CMP, NOT, AUD |
| `edu.certificate_issued` | the DOC pipeline finished | NOT (the link), TD (the badge), AUD |
| `edu.quiz_submitted` | a quiz attempt (the server check) | AUD (low — the attempt count, the anti-cheat metric: a 50-attempt quiz is a signal the content is wrong or the trader is gaming the completion — the ANA-34 alert class, V2-late) |

## 5. Lifecycles

- **Course:** the CMS-14 pointer model (draft/published/archived,
  the versioned blocks, the rollback) — the EDU content is the
  CMS content pattern's second user (the block-registry discipline
  reused: the block types are code-reviewed, no free HTML, the
  sanitize pass — the 24 Part A §10 rule applies to EDU content
  verbatim).
- **Enrollment:** `enrolled → in_progress → completed | dropped
  (the trader's right to drop, the progress retained 90 d then
  cleaned — the re-enrollment is a fresh progress)`.
- **Progress (per block):** `not_started → in_progress →
  completed` (the state machine is per-block; the video's
  `in_progress` carries the `video_pct` claim, the §3.2 honesty
  labels).
- **Certificate:** the DOC lifecycle (the 15 §5: generated,
  versioned, the QR verify, the 7-yr retention — the certificate
  is a financial-adjacent document (it's a credential claim), the
  DOC retention class applies).
- **Quiz attempt:** append-only (the attempts are the audit trail —
  a deleted attempt is a deleted record; the `max_attempts`
  enforcement is the count of the attempts).
- **Path:** `active → archived` (the course_ids immutable once
  published? no — the path is the CMS pointer model too: an edited
  path creates a new version; an in-progress enrollment pins the
  path version at enrollment (the "what did they complete" is
  answerable, the LCC-20 frozen-snapshot discipline applied to
  content: the enrollment carries the `path_version`, the
  certificate cites it)).

## 6. Error taxonomy

Namespace `EDU`:

| Code | HTTP | Meaning |
|---|---|---|
| `edu.course_not_found` | 404 | (the public library route: 404, the 04 posture) |
| `edu.not_enrolled` | 403 | Progress read/write without an enrollment (the enrollment-first rule — no ghost progress) |
| `edu.block_not_ready` | 409 | A lesson access before the prior block (the path order is enforced when the tenant config `sequential: true` — the onboarding paths are sequential, the library courses aren't) |
| `edu.quiz_attempts_exhausted` | 429 | The retake policy (the `details.next_attempt_at` if the tenant config has a cooldown) |
| `edu.progress_stale` | 409 | A video position claim older than the last accepted (the anti-rewind: positions only move forward — the §3.2 rule) |
| `edu.media_unavailable` | 410 | The video object is gone (the tenant deleted it mid-course — the block shows "content unavailable", the progress is preserved, the course completion is blocked until the tenant restores it — the honest state, not a silent skip) |
| `edu.certificate_pending` | 409 | The certificate before the DOC pipeline finishes (the "preparing" state, the DOC §6 pattern) |
| `edu.upload_invalid` | 422 | (V3 authoring) A non-`video/*` or over-cap file |

## 7. API endpoints

Trader (TD "Learn" section):
`GET /v1/edu/library` (the tenant's published courses + paths),
`GET /v1/edu/courses/{id}` (the blocks, the progress state),
`POST /v1/edu/enrollments` `{course_id? | path_id?}`,
`GET /v1/edu/enrollments` (the progress overview — the §3.2 states),
`POST /v1/edu/blocks/{id}/progress` (the video position claim / the
text mark-read — the server-side max-claim logic),
`POST /v1/edu/quizzes/{id}/attempts` (the answers → the
server-check → the result),
`GET /v1/edu/certificates` (the earned, the DOC links),
`GET /v/edu/certificates/{cert_hash}` (V2: the public verify —
the DOC-16 pattern, the allowlisted content).

Staff (ADM, V2 the import/seed surface; V3 the EDU-06 authoring):
`GET|POST /v1/admin/edu/courses` (+ the block editor V3, the
versioning, the publish — the CMS-03 pattern reused),
`POST /v1/admin/edu/courses/{id}/media` (the large-upload, the
tenant-staff only),
`GET|POST /v1/admin/edu/paths` (the path builder),
`GET /v1/admin/edu/analytics` (the completion rates, the quiz
pass rates, the drop-off by block — the ANA-adjacent report, the
"which lesson do traders quit" metric — the tenant's content
improvement loop).

## 8. Schema (key shapes)

```jsonc
// GET /v1/edu/enrollments (the progress overview)
{ "data": [ { "path_id": "01J9EDU…", "path_version": 2,
    "name": "Funded Trader Onboarding", "state": "in_progress",
    "blocks": [ { "title": "How Drawdown Works", "state": "completed",
                  "gated": "quiz", "quiz_best_pct": 100 },
                { "title": "Risk Management Basics", "state": "in_progress",
                  "video_pct": 42, "gated": "checkpoint_quiz" },
                { "title": "Payout Windows", "state": "not_started" } ],
    "certificate": null } ] }

// the public verify (the EDU-05 credential)
{ "data": { "valid": true, "holder": "ali_k", "course": "Funded
    Trader Onboarding", "tenant": "FunderBlu", "gating": "quiz",
    "completed_at": "2026-10-05", "claim": "completed (assessed)" } }
```

## 9. Database design

```sql
CREATE TABLE edu_courses (
  id          ULID PRIMARY KEY,
  tenant_id   ULID NOT NULL,
  slug        TEXT NOT NULL, title TEXT NOT NULL,
  description TEXT, est_minutes INT,
  status      TEXT NOT NULL DEFAULT 'draft'
    CHECK (status IN ('draft','published','archived')),
  live_version INT NOT NULL DEFAULT 1,
  sequential  BOOLEAN NOT NULL DEFAULT false,  -- the path-order gate
  gating      TEXT NOT NULL DEFAULT 'self_attested'
    CHECK (gating IN ('self_attested','quiz')),
  published_at TIMESTAMPTZ, published_by ULID,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, slug)
);
CREATE TABLE edu_course_blocks (
  id          ULID PRIMARY KEY,
  course_id   ULID NOT NULL REFERENCES edu_courses(id),
  version     INT NOT NULL,
  sort        INT NOT NULL,
  block_type  TEXT NOT NULL CHECK (block_type IN ('video','text','quiz')),
  data        JSONB NOT NULL,                  -- video: {r2_key, duration,
                                               --   title}; text: {markdown,
                                               --   title}; quiz: {quiz_id,
                                               --   checkpoint: bool}
  UNIQUE (course_id, version, sort)
);
CREATE TABLE edu_quiz (
  id          ULID PRIMARY KEY,
  tenant_id   ULID NOT NULL,
  questions   JSONB NOT NULL,                  -- the §3.1 shape (the answer
                                               --   key is server-side only
                                               --   — the trader API never
                                               --   returns it pre-submit)
  pass_pct    INT NOT NULL DEFAULT 80,
  max_attempts INT NOT NULL DEFAULT 3,
  attempt_cooldown_h INT
);
CREATE TABLE edu_paths (
  id          ULID PRIMARY KEY,
  tenant_id   ULID NOT NULL,
  name        TEXT NOT NULL,
  course_ids  ULID[] NOT NULL,
  auto_enroll BOOLEAN NOT NULL DEFAULT false,  -- on account.funded
  live_version INT NOT NULL DEFAULT 1,
  status      TEXT NOT NULL DEFAULT 'published'
    CHECK (status IN ('draft','published','archived')),
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE edu_enrollments (
  id            ULID PRIMARY KEY,
  tenant_id     ULID NOT NULL,
  identity_id   ULID NOT NULL,
  course_id     ULID, path_id ULID,
  path_version  INT,                           -- the frozen version (§5)
  state         TEXT NOT NULL DEFAULT 'enrolled'
    CHECK (state IN ('enrolled','in_progress','completed','dropped')),
  started_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  completed_at  TIMESTAMPTZ,
  UNIQUE (identity_id, course_id), UNIQUE (identity_id, path_id)
);
CREATE INDEX idx_eduenr_trader ON edu_enrollments(tenant_id, identity_id);
CREATE TABLE edu_progress (
  id            ULID PRIMARY KEY,
  enrollment_id ULID NOT NULL REFERENCES edu_enrollments(id),
  block_id      ULID NOT NULL,
  state         TEXT NOT NULL DEFAULT 'not_started'
    CHECK (state IN ('not_started','in_progress','completed')),
  video_pct     SMALLINT NOT NULL DEFAULT 0,   -- the max claim (§3.2)
  quiz_attempts INT NOT NULL DEFAULT 0,
  quiz_best_pct SMALLINT NOT NULL DEFAULT 0,
  completed_at  TIMESTAMPTZ,
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (enrollment_id, block_id)
);
CREATE TABLE edu_quiz_attempts (               -- the append-only audit
  id            ULID PRIMARY KEY,
  quiz_id       ULID NOT NULL,
  enrollment_id ULID NOT NULL,
  block_id      ULID,
  pct           INT NOT NULL,
  answers       JSONB NOT NULL,                -- (the given answers — the
  passed        BOOLEAN NOT NULL,              --   content team's wrong-
  at            TIMESTAMPTZ NOT NULL DEFAULT now()  -- question analysis)
);
CREATE INDEX idx_eduatt_quiz ON edu_quiz_attempts(quiz_id, at DESC);
-- the certificate: the DOC pipeline (the `course_certificate` type,
-- the 15 §3.1 set) — EDU emits the event, DOC owns the object
```

## 10. Security & compliance

- **The content is the tenant's IP** (§2 media rules): the R2
  tenant-prefix isolation + the signed 15-min URLs + the `video/*`
  content-type restriction + the media route rate limit — the
  platform's protection is storage-isolation + short-lived access,
  the anti-hotlinking posture (the DRM is explicitly out of V2 —
  the labeled gap: the content is protected at the storage level,
  a determined downloader defeats a signed URL; the tenant's
  decision to publish is their IP decision, the platform's job is
  no accidental public bucket + no open CDN path — the R2 bucket
  is private, the signed URLs are the only path, the CI check:
  the bucket policy rejects unsigned reads).
- **The answer key is server-side** (§3.1): the quiz API returns
  the questions without the answers pre-submit (the property test:
  a max-privilege trader API call on an unsubmitted quiz contains
  no answer field — the quiz-gating is only as strong as this);
  the attempts are append-only (the retake policy is the attempt
  count, not a client-side flag).
- **The completion claims are bounded** (§3.2): the certificate
  text reflects the gating level (`completed` vs `completed
  (assessed)`); the footer: "completion record, not a
  qualification credential" (the compliance line — the EDU
  certificate is never a license/credential claim, the ToS + the
  certificate say so, the FunderBlu legal sign-off on the
  template is a V2 checklist item); the video completion is the
  labeled self-attestation (the §3.2 posture — the platform
  doesn't claim watch-time verification it doesn't have).
- **The no-advice line** (§1): the content is the tenant's
  educational material; the platform's UI carries the disclaimer
  block (the CMS-08 template's EDU variant: "educational content,
  not financial advice"); the tenant is the content owner + the
  advice-liability owner (the ToS clause, the Phase-1 legal
  checklist item for the V2 launch).
- **Progress PII:** the progress is behavioral (which blocks,
  when) — it's the trader's own learning record, the retention
  with the enrollment (the dropped enrollments' progress cleans
  in 90 d, §5); the quiz attempts (the given answers) are the
  content team's metric + the trader's record — the staff read is
  the ADM analytics (aggregate) + the per-trader attempt is
  trader-visible only (the "why did I fail" detail is the trader's,
  the staff see the pass-rate aggregates — the privacy-minimal
  surface).
- **The auto-enroll** (the tenant config): the enrollment event is
  audited (the auto-action is the most visible one — the trader
  should see "you were enrolled in X because you were funded" —
  the NOT nudge explains it, the enrollment row carries
  `enrolled_by: auto|trader`, the honesty rule for system
  actions, the 24 Part B posture).

## 11. Scalability considerations

- Video streaming is the only heavy path: R2 → Cloudflare
  streaming (the edge does the delivery — the PG/API never touch
  the bytes; the signed URL is the handoff); a 500-concurrent
  viewer spike (a tenant pushes the new course) = 500 ×
  ~5 Mbps ≈ 2.5 Gbps peak — the Cloudflare bandwidth line (the
  BIL pass-through's storage/bandwidth meter, 22 §3.1 — the
  tenant sees the number, the platform's edge budget is the
  V2 capacity item, the 29 doc's bandwidth section); the V2
  target (50k traders, ~5% concurrent video ≈ 2.5k viewers ≈
  12 Gbps) is the V2 capacity review's line item.
- The progress API: small writes (the position claim is a
  throttled endpoint — 1 claim/10 s per block, the
  anti-spam + the bandwidth-saver: the client reports every 10 s
  of playback, not every frame) — trivial load.
- The quiz: the submit is a small POST + a JSON compare —
  trivial; the attempts table grows at ~10 rows/trader/course —
  trivial.
- The content: the PG rows are tiny (the media is R2); the
  library queries are tenant-scoped + cached (the CMS-14
  pointer read, the 5-min edge cache for the library page —
  the 24 Part A pattern).
- The certificate: the DOC pipeline (the 15 §11 numbers — a
  completion is a PDF render, the ~500 docs/day V1 number
  scales with the engagement, the worker concurrency is the
  same).
- **The cost that matters is the content, not the compute**
  (the tenant's course creation is the effort; the platform's
  job is to make the V2 import/seed flow (the tenant's existing
  material → the structured blocks) a day of work, not a
  migration project — the §16 step 1 is that flow).

## 12. Open-source solutions

| Option | Verdict |
|---|---|
| **In-house (the CMS-pattern content + the DOC certificate + R2 streaming)** (this design) | **CHOSEN** — EDU reuses three existing disciplines (the CMS-03 block content, the DOC-15 certificate, the R2 signed-URL media) + one read model (the progress); a course platform (Moodle, etc.) is an app within the app with its own auth/content model — the integration surface exceeds the build |
| Moodle/Canvas/OSS LMS | Rejected: the LMS features (SCORM, the complex assessment engine) are 90% unused for "video + quiz + certificate"; the 10% used (the progress tracking) is a read model here |
| Mux/Cloudflare Stream (video hosting) | V2: R2 + Cloudflare streaming (the bytes never touch our servers — the Mux transcoding/API is a V3 authoring option (the EDU-06 upload pipeline's decision, the register: consider-later)); the V2 rule: the tenant provides web-ready files |
| ffmpeg (V3 authoring) | The worker job (the 06 worker topology) — the V3 decision at the upload-pipeline scope |
| DOC (the certificate) | CHOSEN (the 15 pipeline + the DOC-15 QR verify) |

## 13. Technology stack

The TD section (the 16 stack), Postgres (the content/progress/
attempts), R2 (the video, the tenant-prefix, the private bucket
+ signed URLs), Cloudflare (the streaming delivery, the edge
cache), the CMS-03 block pattern (the content model), the DOC
pipeline (the certificate), the NOT (the nudges), the CMP (the
badge input), the ANA (the funnel stage + the completion KPIs),
the ClamAV (the V3 upload scan), Prometheus (the streaming
bandwidth, the claim rate, the quiz runtime), Sentry.

## 14. Integration — internal modules (glue)

| Module | How |
|---|---|
| **CMS (24 Part A)** | the block-content pattern (the EDU content is the CMS-03 discipline's second user — the sanitize pass, the versioning, the pointer model; the EDU block types extend the registry (the code-reviewed addition, the CMS §10 supply-chain rule)) |
| **DOC** | the `course_certificate` type (the 15 §3.1 set extended) + the DOC-15/16 QR verify (the public page) |
| **CMP** | the badge input (the `edu.path_completed` → the badge, the 24 Part B pattern) + the public profile's verified mark (the EDU-05 credential on the CMP-11 handle) |
| **ANA** | the "educated" funnel stage (the `edu.*` events) + the completion analytics (the tenant's content loop, §7) |
| **NOT** | the enrollment nudges (the auto-enroll explanation, the path-completion congratulations) |
| **LCC** | the `account.funded` trigger (the auto-enroll, the tenant config) — the EDU reads the event, the LCC knows nothing about EDU (the loose coupling, the JRN §4 pattern) |
| **TD** | the host section (the "Learn" section, the JRN-adjacent pattern) |
| **R2** | the media store (the private bucket, the signed URLs, the tenant prefix, the lifecycle) |
| **BIL** | the storage/bandwidth meter (the tenant's media cost visibility, 22 §3.1) |
| **AUD** | the enrollment events (the auto-enroll audit), the certificate issuance (the DOC tier) |
| **SUP** | the "I can't play the video" ticket category (the media-unavailable state, the §6 code) — the tenant's content issue, the platform's delivery, the split is clear in the canned response |

## 15. Integration — external tools

Cloudflare (the streaming + the edge), R2, (V3) ffmpeg (the worker
job), Postmark (via NOT), Prometheus/Grafana (the bandwidth
monitoring — the V2 capacity line), Sentry.

## 16. Implementation blueprint (V2)

| Step | Owner | Est | Depends | Exit criteria |
|---|---|---|---|---|
| 1. The content model (courses/blocks/quizzes/paths — the CMS-03 pattern + the block registry extension) + the V2 import/seed flow (the tenant's existing material → the structured blocks, the FunderBlu onboarding content as the seed) | BE-2 + FE-2 | 3 wks | the CMS-03 pattern proven (the 24 Part A build), the R2 media setup | the FunderBlu onboarding content is live in the seed flow; the block schemas validate; the answer-key property test green (no answers pre-submit) |
| 2. The learner surface (the TD "Learn" section: the library, the enrollment, the player (the signed-URL video), the text blocks, the quiz (the server-check), the progress states) | FE-01 | 4 wks | 1, the TD stable | a trader enrolls, watches (the position claims, the 90%+ended completion), passes a quiz, sees the progress — end-to-end in staging |
| 3. The paths (the sequential gate, the auto-enroll on `account.funded`, the path-version freeze at enrollment, the NOT nudge) + the completion events (the EDU-07/08/09 event set) | BE-2 | 2 wks | 2, the LCC events | a funded trader auto-enrolls (the audit row + the nudge); the sequential gate blocks skip-ahead (tested); the events fire on the criteria (the property: the events match the progress states exactly) |
| 4. The certificate (the DOC `course_certificate` type, the gating-level text, the QR verify, the public page) + the profile badge (the CMP-11 verified mark) | BE-2 + FE-02 | 2 wks | 3, the DOC pipeline, the CMP profile | a path completion → the certificate (the "completed (assessed)" text on the quiz-gated seed path) → the verify page → the badge on the profile |
| 5. The staff analytics (the completion rates, the quiz pass rates, the drop-off by block, the attempt metrics) + the media upload (the large-upload, the content-type + cap, the V2 no-transcode rule) + the retention (the dropped-enrollment cleanup) | FE-2 + BE-2 | 2 wks | 2–4 | the tenant's content loop works (the "which lesson do traders quit" report renders); a 2 GB video uploads (the multipart, the cap enforced); the cleanup job deletes on schedule (the audit row) |
| 6. V3: the EDU-06 authoring (the full block editor in ADM, the ffmpeg upload pipeline (the decision: the ffmpeg worker vs the Mux-class service, the register), the HLS output, the checkpoint-quiz authoring) | FE-2 + BE-2 | 4 wks | 5, the 06 worker topology | a tenant staff member authors a new course with an uploaded MP4 → the HLS pipeline → the live course (the full loop, no platform dev involved) |

**Risks:** the video bandwidth surprise (the §11 line item — the
Cloudflare cost at the V2 target; mitigation: the BIL meter shows
the tenant the number from day 1, the V2 capacity review
(29) budgets it, the V3 Mux-class option is the escape hatch);
the content-liability line (a lesson that sounds like financial
advice — the §10 disclaimer + the tenant-content-owner ToS + the
FunderBlu legal sign-off on the seed content in step 1 — the
platform's posture: we host educational content, the tenant owns
the advice); the completion-gaming (a trader speed-watching for
the badge — the §3.2 posture: the self-attested blocks are
labeled, the quiz-gated blocks are the real gates, the tenant
chooses the gating per course; the anti-design of "verified
watching" is explicitly not claimed); the engagement
(education is a retention feature, not a revenue one — the
measure is the breach-rate correlation (the ANA-15 cohort, V3:
"do educated traders breach less?"), not the certificate count;
the metric honesty: the platform reports the correlation, the
tenant decides what it means).

---

# Part D — CHT: Community & Live Chat (7 reqs, V2/V3)

## 1. Purpose & scope

The tenant's community + live support surface: the live chat
widget (CHT-01), the Discord integration (CHT-02), direct messaging
with support (CHT-04), the announcement channel (CHT-05), the chat
history persistence (CHT-07); V3: the community forum (CHT-03),
chat moderation (CHT-08).

**The one-sentence design:** CHT is the **support conversation's
third surface** (after the SUP ticket and the email) + the
**tenant's community bridge** — and the bridge is deliberately
**thin**: the platform owns the support DM (the CHT-04: the trader
↔ support conversation, the SUP ticket's real-time front door) and
the announcement channel (the CHT-05: the tenant's broadcast to the
trader base — the NOT-14 broadcast pattern, the real-time
delivery), while the **community itself lives where the traders
already are** (the Discord integration, the CHT-02: the tenant's
Discord server is the community; the platform provides the identity
bridge (the CMP-11 handle ↔ the Discord account, the verified mark)
+ the announcement posting (the CHT-05 → the Discord channel) +
the support handoff (the CHT-04 from Discord: a trader DMs the
tenant's support bot → the SUP ticket). The in-platform forum
(CHT-03, V3) is the fallback for tenants without a Discord —
built last, because the Discord bridge covers the anchor tenant
and the forum is the long tail.

Requirement coverage: `CHT-01,02,04,05,07` (V2) + `CHT-03,08`
(V3).

## 2. Architecture

```
 the support DM (CHT-04 — the platform-owned surface):
   trader (the TD "Support" section — the SUP-adjacent surface,
     the 16 §14 pre-fill pattern: the conversation opens with the
     context) ◄──real-time──► support staff (the ADM inbox — the
     SUP-06 queue's chat variant: the live conversation sits next
     to the tickets, the same queue, the same SLA)
   · transport: the SSE (the 01 §4.3 pattern — the support
     conversation is an SSE stream per participant, the relay
     reads the `chat.*` events from the outbox; the reconnect +
     the polling fallback is the TD-11 pattern, the 16 §3.2
     discipline)
   · the conversation IS a SUP ticket (the CHT-04 = the SUP ticket
     with `channel: chat` — the §18 ticket model's `messages`
     table is the conversation store (the kind: trader|staff, the
     same thread rules: the internal notes are invisible, the
     messages are immutable, the SLA clock is the SUP's, the
     canned responses (SUP-20) work in the chat (the one-click
     insert), the escalation (the SUP-33 class) works — the chat
     is not a new conversation system, it's the SUP's real-time
     front door; the history (CHT-07) is the thread's history —
     the persistence is free (the PG thread, the 18 §9 design))
   · the handoff from Discord (the CHT-02): the tenant's support
     bot (the Discord bot account, the 20 §10 CRM-09 pattern —
     the bot's DMs route to SUP) → a `channel: discord` ticket →
     the same ADM inbox (the support staff answers in the ADM;
     the answer posts back to the Discord DM via the bot — the
     round-trip is the bot's job, the platform's job is the
     ticket + the queue)
 the announcement channel (CHT-05 — the real-time broadcast):
   tenant staff (the ADM broadcast, the NOT-14 pattern: the 2FA +
     the preview + the tenant scope) ──► the announcement object
     {tenant, title, body, severity (info|warning|critical),
     visible_until}
   delivery: the SSE (the live banner in the TD — the trader
     sees the banner in ≤ 5 s, the §3.2 SSE latency) + the NOT
     email (the critical severity: the email too, the NOT-25
     priority mapping) + the Discord (the CHT-02: the bot posts
     to the tenant's #announcements channel, the option per
     tenant config)
   · the announcement is the CON-14 pattern's tenant-level sibling
     (the CON-14 is platform→all-tenants; the CHT-05 is
     tenant→its-traders — the same object model, the scope is
     the difference)
 the live chat widget (CHT-01 — the public surface):
   the tenant site (the 24 Part A CMS) + the TD: the widget = the
     support DM's entry point (the "chat with support" button →
     the CHT-04 conversation, the logged-in traders; the
     public (not-logged-in) visitors: the lead form (the
     CMS-07 form, the 24 Part A §3.3 — the public widget is the
     lead capture, the logged-in widget is the support DM —
     the two are distinct, the widget routes on auth state))
 the Discord bridge (CHT-02 — the identity + the channels):
   · the identity: the trader links their Discord account (the
     TD "Integrations" section: the OAuth-ish link — the Discord
     user id ↔ the platform identity, the `discord_links` table,
     the CMP-11 handle shown as the Discord display name option
     (the tenant config: the verified mark in Discord = the bot
     grants a "Verified Trader" role to linked accounts (the
     bot's role management, the tenant's server, the tenant's
     rules — the platform provides the link + the verified
     signal, the tenant's Discord admin owns the server))
   · the announcements: the CHT-05 → the bot post (§2)
   · the support: the bot DM → the SUP ticket (§2)
   · the community (the V3 CHT-03 fallback): the in-platform
     forum (the board/thread/post model, the moderation the
     CHT-08 — see §3.3)
```

## 3. System design

### 3.1 The conversation state (the CHT-04, the SUP-adjacent)

```
conversations (the SUP ticket with channel: chat — the 18 §9
  `tickets` + `ticket_messages` tables, the `kind` enum gains
  'chat' — no new tables):
  · the real-time: the `chat.message` event (the EVT topic —
    the outbox event on every message; the SSE relay fans it to
    the participants (the trader's TD session + the staff's ADM
    session — the per-participant SSE, the 01 §4.3 pattern))
  · the SLA: the SUP's (the 18 §3.3 — the first-response clock
    runs on the chat (the real-time expectation is higher: the
    tenant config's chat SLA is tighter than the ticket SLA
    (the FunderBlu default: 15-min first response, business
    hours — the config, the ADM-33 V2 pattern))
  · the presence: the "support is online" indicator (the staff
    online state — the console's session presence, the simple
    model: a staff is "online" while their ADM session is active
    + they haven't marked away (the away flag, the manual
    toggle) — the presence is the SSE event `chat.presence`,
    the honest version: "a support agent is available" not
    "someone is reading your message")
  · the mobile: the CHT-04 in the MOB app (the 26 Part A: the
    push notification on a support reply — the NOT-03 pattern,
    the deep link to the conversation; the real-time in the app
    = the SSE (the 26 Part A §1) or the push (the reply
    arrives as a push, the open is the sync) — the pragmatic
    mobile: the push is the notification, the open is the
    refresh, the SSE in-app is the enhancement)
```

### 3.2 The announcement (the CHT-05)

```
announcements: id · tenant_id · title · body (the CMS-03
  sanitize pass — the announcement is rendered content, the
  same trust boundary) · severity (info|warning|critical) ·
  visible_from · visible_until · created_by (2FA) ·
  channel_flags {td_banner: bool, email: bool (the NOT
  template, the critical → the email default), discord: bool
  (the tenant config + the flag)}
  · the TD banner: the SSE `chat.announcement` → the banner
    (the dismissible, the severity-colored, the `visible_until`
    expiry — the banner queue: max 3 visible, the critical
    displaces the info (the severity order, the NOT-25 pattern))
  · the retention: the announcements are the 2-yr marketing-
    class (the 18's retention posture) — the trader's history
    (the TD "Announcements" list, the CHT-07-adjacent history)
    is the thread of what the tenant told them (the
    "when did they tell me about the holiday schedule" answer
    — the history is the trust artifact)
```

### 3.3 The forum (V3 CHT-03) + the moderation (V3 CHT-08)

The in-platform forum (the Discord-less tenants' community):
```
boards: {tenant, key, name, order} (the tenant-configured: the
  "General", "Funded", "Payouts" boards — the tenant owns the
  taxonomy)
threads: {board, title, author (the identity), state
  (open|closed|pinned|removed), created/pinned_by}
posts: {thread, author, body (the markdown, the sanitize pass),
  state (visible|removed), created}
  · the identity: the CMP-11 handle (the public identity, the
    masked default extends: the forum posts show the handle,
    the real name never)
  · the moderation (CHT-08): the tenant staff (the `firm:
    support` role) can pin/close/remove (the 2FA on remove —
    the content removal is the critical-tier action, the AUD
    line with the pre-removal content snapshot — the removed
    post's body is retained in the audit (the evidence, the
    18 §5 message immutability pattern: the removal is a state
    change, not a delete)); the report flow (the trader reports
    a post → the staff queue (the ADM's CHT section) → the
    staff decision (the remove/restore/ignore, the 2FA on
    remove)); the auto-moderation (the V3-late: the banned-word
    list (the tenant config) + the rate limit (the anti-spam,
    the CMS-07 pattern) — the auto-moderation is the
    flag-not-remove: a flagged post is visible to moderators
    only pending review (the labeled state, the "under review"
    the CMP-06 pattern) — the auto-removal is banned (the
    false-positive on a trader's post is a trust event; the
    human reviews, the machine flags))
  · the retention: the forum content is the 2-yr marketing-
    class (the community content, not the financial record —
    the same class as the announcements; the tenant config
    can set a shorter board-level retention (the "General"
    board at 90 d) — the config, the retention job, the audit)
```

## 4. Events (topic `chat`)

| Event | When | Consumers |
|---|---|---|
| `chat.message` | a conversation message (the trader/staff) | the SSE relay (the participants), the SUP SLA clock (the first-response), AUD (low) |
| `chat.presence` | a staff online/away | the SSE relay (the indicator), — |
| `chat.announcement` | the CHT-05 publish (the channel_flags) | the SSE relay (the TD banner), the NOT (the email), the Discord bot (the post), AUD (critical on the critical severity — the broadcast is the tenant's public statement, the CON-14 tier) |
| `chat.discord_linked` | the identity link (the CHT-02) | AUD (low — the link is the trader's action) |
| `chat.forum_post_reported` (V3) | the report flow | the ADM queue (the NOT to the staff), AUD (low) |
| `chat.forum_post_removed` (V3) | the moderation (the 2FA) | AUD (critical — the content removal) |

Consumes: the `notification.*` (the push for the support reply,
the 26 Part A pattern), the SUP events (the conversation IS the
ticket — the `ticket.replied` is the `chat.message`'s sibling,
the same outbox event, the two topics mirror for the ANA
consumption).

## 5. Lifecycles

- **Conversation:** the SUP ticket machine (the 18 §3.1: open →
  in_progress → resolved → closed) with the `channel: chat` +
  the tighter SLA (§3.1) — the real-time adds the presence
  (the online/away, the manual toggle) + the "typing" indicator
  (the ephemeral SSE event — the typing indicator is never
  persisted (the ephemeral event, the `chat.typing` with a
  5-s TTL in the SSE, no outbox, no PG — the honest
  real-time: the presence + the typing are live signals, the
  message is the record)).
- **Announcement:** `draft → published (the 2FA) → visible
  (the window) → expired (the `visible_until` — the banner
  drops, the history retains) | withdrawn (the staff action,
  the 2FA, the "this announcement was withdrawn" notice in the
  history — the withdrawal is not a deletion: the history shows
  the withdrawn marker, the integrity rule, the CMP-17 posture
  applied to announcements)`.
- **Discord link:** `linked → (the bot's role sync) → unlinked
  (the trader's right, the TD section; the unlinked = the bot
  removes the verified role (the next bot sync) + the platform
  retains the link history (the audit: "this Discord account
  was linked to this trader on X" — the fraud-adjacent record,
  the RSK-04-adjacent data: a Discord account linked to two
  platform identities is a signal (the detector input, the
  23 §3.2 pattern))`.
- **Forum thread/post (V3):** the §3.3 states (the thread:
  open/closed/pinned/removed; the post: visible/removed with
  the audit snapshot) — the removal is the state change (the
  immutability rule, the 18 §5 pattern).
- **The report (V3):** `filed → (the staff queue) →
  actioned (remove/restore/ignore) — the report is the audit
  trail of the moderation (the "who reported what, what
  happened" record, the 2-yr retention)`.

## 6. Error taxonomy

Namespace `CHT`:

| Code | HTTP | Meaning |
|---|---|---|
| `cht.conversation_not_found` | 404 | (the ownership: 404, the 04 posture) |
| `cht.closed` | 409 | A message on a resolved/closed conversation (the reopen = the staff action, the SUP rule) |
| `cht.rate_limited` | 429 | The message rate (the 10/min per conversation — the anti-spam, the auto-moderation's sibling) |
| `cht.presence_unknown` | — | (internal) the presence state is stale (the indicator shows "availability unknown" — the honest fallback, the ANA-14 label pattern) |
| `cht.announcement_validation` | 422 | (V2) The broadcast preview failed (the NOT-14 pattern: the preview is required) |
| `cht.discord_unlinked` | 409 | A Discord-directed action without the link (the "link your Discord" prompt, the TD section) |
| `cht.forum_removed` | 410 | (V3) A removed post/thread (the page: "this content is no longer available" — no leak of the reason, the 24 Part A §6 posture) |
| `cht.report_duplicate` | 409 | (V3) The same report twice (the dedupe on (post, reporter)) |
| `cht.moderation_requires_2fa` | 403 | (V3) The removal without the step-up (the §3.3 rule) |

## 7. API endpoints

Trader (TD):
`GET /v1/chat/conversations` (the own, the SUP-adjacent),
`POST /v1/chat/conversations` (the new — the pre-fill context,
the 16 §14 pattern), `GET /v1/chat/conversations/{id}` (the
thread), `POST /v1/chat/conversations/{id}/messages` (the
real-time — the SSE delivers, the API is the write + the
reconnect-sync (the last-message-id cursor, the 04 §5.7
replay-pattern: the reconnect fetches the missed messages by
cursor — the real-time honesty: the SSE is the fast path, the
cursor is the truth)),
`GET /v1/chat/announcements?active=` (the banner + the
history), `GET /v1/chat/presence` (the support availability),
`POST /v1/chat/discord/link` (the CHT-02 — the Discord auth
code exchange, the staff-approved link (the tenant config:
auto-approve vs staff-approve — the FunderBlu default: staff-
approve (the verified role is the tenant's badge, the tenant
approves its placement))),
`DELETE /v1/chat/discord/unlink`,
V3 (the forum): `GET /v1/chat/boards`, `GET /v1/chat/threads?
board=`, `POST /v1/chat/threads`, `POST /v1/chat/threads/{id}/
posts`, `POST /v1/chat/posts/{id}/report`,
`GET /v1/chat/profiles/{handle}` (the forum identity — the
CMP-11 surface).

Staff (ADM — the CHT section, the SUP-adjacent queue):
`GET /v1/admin/chat/queue` (the live conversations + the
reported posts (V3)), `GET /v1/admin/chat/conversations/{id}`
(the full thread + the internal notes — the SUP-09 pattern),
`POST /v1/admin/chat/conversations/{id}/messages` (the staff
reply + the internal note, the kind), `POST /v1/admin/chat/
announcements` (the CHT-05 — the 2FA + the preview, the NOT-14
pattern), `POST /v1/admin/chat/announcements/{id}/withdraw`
(the 2FA),
`GET /v1/admin/chat/discord/links` (the pending links — the
staff-approve flow), `POST /v1/admin/chat/discord/links/{id}/
approve|reject`,
V3 (the moderation): `POST /v1/admin/chat/posts/{id}/remove`
(the 2FA + the snapshot), `POST /v1/admin/chat/posts/{id}/
restore`, `GET /v1/admin/chat/reports` (the report queue).

The Discord bot (the CHT-02 — the bot's endpoints, the
Discord-webhook-in): the bot receives the DMs (the Discord
gateway) → the `channel: discord` tickets (the §2 path); the
bot posts the announcements (the CHT-05 → the #announcements
channel); the bot syncs the verified roles (the link state →
the role grant/revoke, the nightly + the event-driven); the
bot is the tenant's (the bot account is added to the tenant's
server by the tenant's admin — the platform provides the bot
program, the tenant owns the server + the bot's placement).

## 8. Schema (key shapes)

```jsonc
// the conversation message (the SSE frame)
event: message
data: { "conversation_id": "01J9TCK…", "kind": "staff",
  "body": "Your payout is in the queue — I can see it, it's
  next in line for the finance review.", "at": 1758282000000,
  "seq": 42 }

// the announcement (the banner)
event: announcement
data: { "id": "01J9ANN…", "title": "Holiday schedule",
  "body": "Support hours over the holiday: …", "severity": "info",
  "visible_until": 1758886800000 }

// the Discord link state
{ "data": { "linked": true, "discord_user": "fblu_trader_01",
  "role": "verified", "linked_at": 1758282000000,
  "approval": "staff" } }
```

## 9. Database design

```sql
-- the conversation = the SUP ticket (the 18 §9 tables, the
-- `tickets.channel` column: 'ticket'|'chat'|'discord' — the
-- CHT-04/02 channels) + the `ticket_messages` (the thread).
-- The new CHT tables:
CREATE TABLE chat_announcements (
  id            ULID PRIMARY KEY,
  tenant_id     ULID NOT NULL,
  title         TEXT NOT NULL,
  body          TEXT NOT NULL,                  -- the CMS-03 sanitize
  severity      TEXT NOT NULL DEFAULT 'info'
    CHECK (severity IN ('info','warning','critical')),
  channel_flags JSONB NOT NULL,                 -- {td_banner, email,
                                                --   discord}
  visible_from  TIMESTAMPTZ NOT NULL DEFAULT now(),
  visible_until TIMESTAMPTZ NOT NULL,
  withdrawn_at  TIMESTAMPTZ,                    -- the §5 withdrawal
  withdrawn_by  ULID,
  created_by    ULID, created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_chatann_active ON chat_announcements(tenant_id, visible_until)
  WHERE withdrawn_at IS NULL;
CREATE TABLE discord_links (
  id            ULID PRIMARY KEY,
  tenant_id     ULID NOT NULL,
  identity_id   ULID NOT NULL,
  discord_user_id TEXT NOT NULL,
  discord_username TEXT,
  state         TEXT NOT NULL DEFAULT 'pending'
    CHECK (state IN ('pending','approved','rejected','unlinked')),
  approved_by   ULID, approved_at TIMESTAMPTZ,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, identity_id)               -- one active link
);
CREATE INDEX idx_disc_user ON discord_links(tenant_id, discord_user_id);
-- V3 (the forum):
CREATE TABLE forum_boards (
  id          ULID PRIMARY KEY,
  tenant_id   ULID NOT NULL, name TEXT NOT NULL, key TEXT NOT NULL,
  order       INT, retention_days INT NOT NULL DEFAULT 730,
  UNIQUE (tenant_id, key)
);
CREATE TABLE forum_threads (
  id          ULID PRIMARY KEY,
  tenant_id   ULID NOT NULL, board_id ULID NOT NULL,
  title       TEXT NOT NULL, author_id ULID NOT NULL,
  state       TEXT NOT NULL DEFAULT 'open'
    CHECK (state IN ('open','closed','pinned','removed')),
  removed_at  TIMESTAMPTZ, removed_by ULID,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_forum_threads ON forum_threads(tenant_id, board_id, created_at DESC);
CREATE TABLE forum_posts (
  id          ULID PRIMARY KEY,
  tenant_id   ULID NOT NULL, thread_id ULID NOT NULL,
  author_id   ULID NOT NULL, body TEXT NOT NULL,
  state       TEXT NOT NULL DEFAULT 'visible'
    CHECK (state IN ('visible','removed','flagged')),
  removed_at  TIMESTAMPTZ, removed_by ULID,
  removed_body_snapshot TEXT,                   -- the audit snapshot
                                                --   (the §3.3 rule —
                                                --   the removed content
                                                --   is retained in the
                                                --   audit, the AUD mirror
                                                --   carries it)
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_forum_posts ON forum_posts(tenant_id, thread_id, created_at);
CREATE TABLE forum_reports (
  id          ULID PRIMARY KEY,
  tenant_id   ULID NOT NULL, post_id ULID NOT NULL,
  reporter_id ULID NOT NULL, reason TEXT NOT NULL,
  state       TEXT NOT NULL DEFAULT 'filed'
    CHECK (state IN ('filed','actioned','dismissed')),
  action      TEXT, actioned_by ULID, actioned_at TIMESTAMPTZ,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (post_id, reporter_id)
);
-- the presence: the Redis (the ephemeral state — the staff
-- online/away is the Redis key (the 15-min TTL, the heartbeat
-- from the ADM session), never the PG (the presence is the
-- live signal, the §3.1 posture); the typing: the SSE-ephemeral
-- (no store, the §5 rule)
```

## 10. Security & compliance

- **The conversation is a support record** (the CHT-04 = the SUP
  ticket, the 18 §10 rules apply verbatim: the internal notes
  invisible to the trader (the structural filter, the 18 §3.1
  property test), the ownership (404 not 403), the message
  immutability (the corrections are new messages — the real-time
  doesn't add an edit: a sent chat message is a sent message,
  the "typo" is a new message — the evidence integrity over the
  chat comfort, the 18 §5 rule), the retention (the 7-yr for
  the money-linked conversations (the payout chat is the money-
  linked class, the SUP-13 pattern), the 2-yr for the general
  — the tenant config per category, the 18 §3.3 SLA/retention
  posture)).
- **The real-time is the SSE (no WebSocket upgrade in V2)**
  (§2): the SSE is the 01 §4.3 pattern (the GW-authenticated,
  the relay-backed) — the WebSocket is the V3 option if the
  bidirectional latency demands it (the typing indicator is the
  only truly bidirectional signal, and it's ephemeral — the SSE
  + the cursor-sync covers the V2 requirements; the honest
  engineering: the SSE is simpler, the GW's existing surface,
  the reconnect is the TD-11 pattern — the WebSocket is a
  later optimization, not a day-1 choice).
- **The announcement is the tenant's public statement**
  (§3.2): the 2FA + the preview (the NOT-14 pattern) + the
  critical-tier audit (the CON-14 tier — the broadcast is the
  tenant talking to all its traders at once, the platform's own
  CON-14 discipline modeled for the tenant) + the withdrawal
  is a labeled state (the §5 rule — the integrity over the
  convenience: a withdrawn announcement shows as withdrawn,
  never vanishes).
- **The Discord bridge** (§2/§7): the link is the trader's
  action + the tenant's approval (the staff-approve default,
  the §7 note — the verified role is the tenant's badge, the
  tenant decides its placement); the bot is the tenant's (the
  server is theirs, the bot's permissions are the tenant's
  config — the platform's bot program requests the minimal
  permissions (the DM read/write for the support, the channel
  post for the announcements, the role management for the
  verified mark — the no-admin-permission rule: the bot never
  has the server admin, the supply-chain hygiene, the 24 Part
  A §10 posture applied to the Discord)); the link history is
  the fraud record (the §5 rule — a Discord account linked to
  two identities is the RSK input, the 23 §3.2 pattern); the
  Discord PII (the username, the user id) is the link record
  (the retention with the link, the 2-yr class, the staff-
  visible in the ADM's Discord section, the critical-audited
  read — the CON-09 posture).
- **The forum** (V3, the §3.3 rules): the handle-only identity
  (the CMP-11 masked default — the real name never in the
  forum), the removal is the state change + the audit snapshot
  (the §9 `removed_body_snapshot` — the content is retained in
  the evidence, the 18 §5 immutability pattern), the
  auto-moderation is the flag-not-remove (the §3.3 rule — the
  false-positive ban: the machine flags, the human removes,
  the 2FA on the removal, the report flow is the trader's
  recourse (the "I reported it, what happened" answer = the
  report state, the trader-visible in their report history)),
  the rate limit + the banned-word list are the anti-spam (the
  CMS-07 pattern), the board-level retention is the tenant
  config (the §3.3).
- **The presence honesty** (§3.1): the indicator says
  "available" (a staff session is active + not away) — it
  never claims "reading your message" (the presence is the
  availability, the typing is the ephemeral signal, the SLA
  is the promise — the three are distinct, the UI labels them
  distinct: "Support is available" / "Agent is typing…" /
  "First response within 15 min (business hours)" — the
  anti-pattern: a green dot that means "we'll get to you
  eventually" (the trust killer, the labeled-honesty rule
  across the platform, the ANA-14 posture applied to the
  support UI)).
- **The no-community-advice line** (the §1 posture extends to
  the forum): the forum is the tenant's community (the tenant
  owns the moderation, the content, the advice-liability — the
  ToS clause, the EDU §10 pattern); the platform's role is the
  surface + the moderation tools + the identity bridge — the
  trader-to-trader advice in the forum is the tenant's
  community, not the platform's (the ToS line: "community
  content is user-generated; the platform is not a broker and
  community members are not platform staff" — the FunderBlu
  legal sign-off, the V2 checklist item).

## 11. Scalability considerations

- The real-time: the SSE per participant (the trader + the
  staff) — the 01 §4.3 fan-out (the relay reads the `chat.*`
  events, the SSE writers scale); the V2 target (50k traders,
  ~1% in an active conversation ≈ 500 concurrent
  conversations × 2 participants ≈ 1k SSE sessions) is within
  the TD SSE budget (the 16 §11 numbers — the chat adds ~10%
  to the SSE load, the same design).
- The cursor-sync (the reconnect truth, §7): the last-message-
  id fetch is a PG range read (the (conversation, seq) index
  — the `ticket_messages` gains the `seq` column (the
  per-conversation monotonic, the outbox-seq pattern, the 04
  §5.7 replay posture)) — sub-millisecond.
- The announcements: the SSE fan-out on publish (a single event
  → the tenant's active sessions — the burst is bounded by the
  tenant's concurrent traders, the 16 §11 SSE story) + the
  email (the NOT batch, the 14 §3.6 rate limits) + the Discord
  (the bot's single post, the Discord rate limit — the bot
  respects the Discord API's per-channel rate, the 5-sec
  spacing on a multi-channel announcement, the trivial).
- The Discord bot: the gateway connection (the Discord
  websocket, the bot's own connection — the platform runs one
  bot process per tenant server (the bot accounts are per-
  tenant, the tenant's server) — the process count = the
  tenant count with a Discord (the V2: 1-5, the V3: 25-50 —
  the bot process is lightweight (the event handler + the API
  calls), the workers-process adjacency, the 06 worker
  topology line item).
- The forum (V3): the board/thread/post reads are the standard
  indexed PG (the (tenant, board, created_at) index, the
  keyset pagination, the 17 §11 pattern); the moderation queue
  is the ADM surface (the report volume: the ~10 reports/week
  at the V2 tenant scale — the queue is a list, not a system).
- **The cost that matters is the support staffing** (the real-
  time raises the response expectation — the 15-min SLA is the
  tenant's staffing decision, the platform's job is to make
  each conversation answerable from one screen (the 17 §3.4
  surface, the 18 §14 integration) — the chat is the
  support-velocity tool, the SLA is the tenant's ops).

## 12. Open-source solutions

| Option | Verdict |
|---|---|
| **In-house (the SUP conversation + the SSE real-time + the Discord bot)** (this design) | **CHOSEN** — the conversation is the SUP ticket (the 18 design, the thread store, the SLA, the canned responses, the escalation — all exist); the real-time is the SSE pattern (the 01/16 design); the Discord bot is a thin program over the Discord API (the 20 §10 CRM-09 precedent) — a third-party live-chat SaaS (Intercom, Crisp, Zendesk Chat) would own the conversation data + the support queue — exactly the duplication the SUP-adjacent design forbids (the 18 §12 posture) |
| Intercom/Crisp/Zendesk Chat (the SaaS live chat) | Rejected: the conversation data leaves the house (the support record is the 7-yr evidence class, the 18 §10), the queue forks from the SUP, the pricing at the V2 scale (the per-seat) — the in-house build is the SUP surface + the SSE, both exist |
| **Discord API (the CHT-02 bridge)** | CHOSEN (the bot program, the gateway, the role sync — the tenant's server, the tenant's community, the platform's bridge — the §10 permission-minimal bot) |
| (V3 forum) the in-house board/thread/post (this design) | CHOSEN (the forum is the PG rows + the moderation tools; the Discourse-class self-host is a stack-within-a-stack (the PHP/its-DB/its-auth) — the 24 Part A §12 posture: the content we need is 10% of what Discourse manages, the 90% is the overhead) |
| Discourse (the self-hosted forum alternative) | Rejected (the V3 decision, the rationale above; the register: the V3 re-review if the forum scope exceeds the §3.3 model) |
| The SSE (the 01 §4.3) | CHOSEN (the real-time transport — the WebSocket is the V3 optimization option, the §10 posture) |

## 13. Technology stack

The SSE (the 01 relay pattern), Postgres (the SUP tables + the
CHT tables), Redis (the presence, the ephemeral state), the
Discord API (the bot: the gateway + the REST, the bot process
per tenant server), the TD/ADM surfaces (the 16/17 stacks),
the NOT (the announcement email, the push for the replies,
the 14 channel pattern), the CMS-03 sanitize pass (the
announcement/forum content), the R2 (none — the CHT has no
media of its own; the file attachments in the conversation
are the SUP-21 pattern (the 18 §3.5: the 10 MB, the type
validation, the ClamAV V2)), Prometheus (the conversation
volume, the SLA first-response, the SSE load, the bot
health), Sentry.

## 14. Integration — internal modules (glue)

| Module | How |
|---|---|
| **SUP** | the conversation IS the ticket (the 18 §9 tables, the `channel` column, the SLA, the canned responses, the escalation, the internal notes — the CHT-04 is the SUP's real-time front door, not a parallel system; the SUP-24 (the Telegram intake, V3) joins the same `channel` enum (the Telegram bot = the Discord bot's sibling, the register: the V3 decision)) |
| **NOT** | the announcement email (the CHT-05 → the NOT template, the critical severity's email), the push for the support replies (the 26 Part A pattern, the MOB-03 channel), the broadcast (the NOT-14 pattern's delivery) |
| **EVT** | the `chat.*` topic (the outbox events, the SSE relay's source, the 04 §3.3 lanes) |
| **GW** | the SSE routes (the 01 §4.3 pattern, the GW-authenticated), the cursor-sync API (the §7 reconnect), the rate limits (the CHT-06 class — the per-conversation message rate, the 04's rate-limit config) |
| **CMP** | the handle (the forum identity, the §3.3), the verified mark (the Discord role's platform-side signal, the §2), the public profile's "community" section (the V3: the forum reputation, the badge-adjacent, the no-money-gating rule, the 24 Part B §3.5 posture) |
| **TD** | the "Support" section (the CHT-04 surface, the 16 §14 pre-fill), the banner (the CHT-05, the §3.2), the "Integrations" section (the Discord link, the §7), the forum (the V3 "Community" section) |
| **ADM** | the CHT section (the live conversation queue next to the tickets, the announcement manager, the Discord link approvals, the V3 moderation queue) — the 17 §3.1 ADM-adjacent surface (the queue pattern, the 2FA on the sensitive actions (the announcement publish, the post removal)) |
| **CON** | the platform-level announcement (the CON-14, the tenant-level CHT-05's sibling — the two are distinct: the CON-14 is the platform → the tenants' staff (the console realm), the CHT-05 is the tenant → its traders (the TD) — the object model is shared, the scope is the difference, the 21 §3.4 posture) |
| **RSK** | the Discord link history (the §5 fraud input — the multi-identity link signal, the 23 §3.2 pattern), the forum reports (the V3: a pattern of reports on one trader's posts → the RSK-07 signal input, the tenant's community enforcement's platform-side echo) |
| **ANA** | the support KPIs (the first-response time, the conversation volume, the channel mix — the SUP-25 reporting, the 18 §14), the announcement reach (the banner impressions, the email opens — the NOT-22 delivery data), the forum engagement (the V3: the post volume, the report rate, the moderation turnaround) |
| **AUD** | the conversation events (the SUP tier — the money-linked 7-yr, the general 2-yr, the 18 §3.3), the announcement (the critical tier, the CON-14 posture), the Discord link (the low tier + the staff-approve's critical), the forum moderation (the critical on the removal, the §3.3) |
| **MOB** | the push for the support replies (the 26 Part A, the deep link to the conversation), the banner (the MOB's home screen, the CHT-05) |
| **BIL** | (the V3: the Discord bot's infra is the tenant's platform cost — the meter-adjacent, the 22 §3.1 line) |

## 15. Integration — external tools

Discord API (the bot: the gateway, the REST, the role management —
the tenant's server), the SSE (the 01 infra), Postmark (via NOT —
the announcement email, the reply push's email fallback),
ClamAV (the V2 attachment scan, the 18 worker), Prometheus/
Grafana (the bot health, the SSE load, the SLA dashboard),
Sentry (the bot + the surfaces).

## 16. Implementation blueprint (V2)

| Step | Owner | Est | Depends | Exit criteria |
|---|---|---|---|---|
| 1. The conversation foundation (the SUP `channel` column, the `seq` on the messages, the cursor-sync API, the `chat.message` events, the SSE delivery to the participants) | BE-2 | 2 wks | the SUP (the 18 V1), the EVT, the SSE (the 16 §3.2 proven) | a message in staging: the trader's TD + the staff's ADM see it in ≤ 2 s (the SSE), the reconnect (the kill-stream test) syncs via the cursor (no message lost, no duplicate — the property test) |
| 2. The TD "Support" section (the conversation UI: the thread, the composer, the presence indicator (the honest labels, the §10), the typing indicator (the ephemeral), the pre-fill context) + the ADM CHT queue (the live conversations next to the tickets, the internal notes, the canned responses) | FE-01 + FE-1 | 3 wks | 1, the 16/17 surfaces | the FunderBlu support dry-run: a real conversation end-to-end (the trader in the TD, the staff in the ADM, the internal note invisible to the trader (the test), the SLA clock runs, the canned response inserts) |
| 3. The presence (the Redis, the heartbeat, the away toggle, the `chat.presence` SSE) + the rate limit (the 10/min) + the mobile push (the NOT push channel, the deep link) | BE-2 + FE-01 | 2 wks | 1–2, the NOT V2 (the push), the MOB (the 26 Part A step 4) | the presence shows the honest states (the staff away → the indicator updates ≤ 5 s, the session end → the "unavailable"); a support reply pushes to a phone (the deep link opens the conversation); the rate limit 429s the 11th message (the test) |
| 4. The announcement channel (the CHT-05: the object, the ADM manager (the 2FA + the preview), the TD banner (the SSE, the severity queue, the `visible_until`), the email (the NOT), the history (the TD list, the withdrawal marker)) | BE-2 + FE-1 | 2 wks | 1, the NOT, the CMS-03 sanitize | a critical announcement: the banner in ≤ 5 s (the SSE test), the email (the NOT delivery), the history retains (the withdrawal shows as withdrawn (the test), the 2FA + the preview enforced (the test)) |
| 5. The Discord bridge (the CHT-02: the bot program (the DM → the `channel: discord` ticket, the announcement post, the role sync), the TD "Integrations" link flow (the staff-approve), the ADM's link approvals, the link history (the audit, the RSK input wiring)) | BE-2 + FE-01 | 3 wks | 1–4, the Discord bot account (the FunderBlu server, the tenant's admin) | a FunderBlu trader links Discord (the staff approves, the verified role lands in the server (the bot's role sync), a DM to the bot opens a ticket in the ADM (the round-trip: the staff answer posts back to the DM), the announcement posts to #announcements; the multi-identity link test: a Discord account linked to two identities → the RSK signal (the 23 §3.2 pattern) |
| 6. The CHT-01 widget (the CMS site + the TD: the logged-in → the CHT-04, the public → the CMS-07 lead form, the routing on auth) + the support staffing config (the chat SLA, the business-hours, the ADM-33-adjacent config) | FE-01 + FE-2 | 2 wks | 2–5, the CMS (the 24 Part A) | the FunderBlu site's widget: a logged-in trader starts a conversation (the pre-fill), a visitor submits the lead (the CRM + the SUP lead, the 24 Part A §3.3); the chat SLA shows in the UI (the "15 min, business hours" label, the §10 honesty) |
| 7. V3: the forum (the CHT-03: the boards/threads/posts, the handle identity, the sequential-free posting, the report flow) + the moderation (the CHT-08: the staff tools (the pin/close/remove + the 2FA + the snapshot), the report queue, the auto-moderation (the flag-not-remove, the banned-word list, the rate limit)) + the Telegram intake (the SUP-24, the channel's third value, the bot sibling) | BE-2 + FE-2 | 4 wks | 5–6, the CMP handle (the 24 Part B) | a seeded forum: a thread + the posts render (the handle-only identity, the property test: no real name in the public surface); a reported post → the staff queue → the removal (the 2FA, the snapshot in the audit, the 410 on the public URL, the trader's report history shows the action); the auto-flag (a banned word → the post is `flagged` (moderator-only visible, the test), never auto-removed); the Telegram DM → the `channel: telegram` ticket (the round-trip) |

**Risks:** the real-time expectation vs the support staffing
(the 15-min SLA is the tenant's staffing decision — the
platform's job is the velocity (the one-screen answerability,
the canned responses, the pre-fill), the SLA config is the
tenant's (the §11 posture — the anti-pattern: the platform
promising a real-time SLA the tenant can't staff (the trust
breaker); the mitigation: the presence honesty (the §10) +
the SLA label (the "business hours" qualifier) + the staffing
checklist in the V2 launch (the FunderBlu COO's ops review —
the "how many support staff for the chat SLA" is a Phase-2
ops item, not a platform guess)); the Discord bot compromise
(the bot's token is the server's keys — the §10 permission-
minimal bot + the SOPS storage (the 06 posture) + the no-admin
rule + the incident runbook entry ("bot token leaked" = the
token rotation + the server re-link, the 30-min ops action,
the CON-15 control-ladder-adjacent)); the conversation-data
leak (a staff seeing another tenant's conversations — the
tenant scope is structural (the 04 posture), the property test
(cross-tenant conversation read = 404, the test), the AUD on
every read (the CON-09 posture)); the forum moderation
backlog (the V3: the report queue's SLA (the tenant config,
the ADM-33 pattern) + the flag-not-remove (the §3.3 rule —
the false-positive ban is the trust rule: a wrongly removed
trader post is a community event, the human review is the
control, the auto-moderation is the triage, never the
execution)); the real-time protocol scope creep (the
WebSocket-itis — the §10 posture: the SSE + the cursor is the
V2 truth, the WebSocket is the V3 optimization only if the
metrics demand it (the SSE p95 > 5 s on the reconnect-sync is
the trigger, the labeled decision, the 29 doc's protocol
section)).

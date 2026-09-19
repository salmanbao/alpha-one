# 17 — ADM: Admin Panel

> Covers PRD module **ADM** (41 requirements). The tenant's operational
> cockpit. The PRD marks only **ADM-05 (account list)** as V1 — but V1
> *operation* is impossible without the queues the V1 backend requires
> humans in the loop on (payout approval, KYC manual review, risk cases,
> support triage). docs/00 therefore commits ADM 1.0 = **shell + account
> list + core queues**; the remaining 38 requirements ship in V2.

## 1. Purpose & scope

**V1 (binding):**
- **Shell** — app shell, module navigation, queue badges (unprocessed
  counts), global search (account/trader id), responsive (ADM-01/38 early).
- **Account list (ADM-05)** — filterable (state, package, trader, date),
  the ops starting point; row → detail.
- **Core queues (V1-justified, V2-completed):**
  - **Payout queue** (PAY-08/09: approve/reject with reason, 2FA, export
    PAY-44) — V1 payouts are manual, so this screen is critical path.
  - **KYC manual review** (KYC-11/12) — the undecided/needs-docs queue.
  - **Risk cases** (RSK-10/12 V1 flow: open, decide, hold release).
  - **Trader management (ADM-03/04 minimum):** find trader → detail →
    actions (suspend/resume → AUTH, pause account → LCC, note).
  - **Account detail (ADM-06 minimum):** the account, its events, its
    positions (read), its documents, its payouts — one page, read-heavy.

**V2 (the 38):** operator dashboard, challenge manager, verification queue,
pending tasks, communication composer, live ops feed, reports UI, coupon
manager, broadcast/banner, email template editor, team & roles, audit log
viewer, settings pages, webhook manager, positions browser, news calendar,
bulk ops, list exports, broker management, payout forecast, SLA config,
offer manager, global search 2.0, queue assignment, alert routing,
onboarding checklist, admin notification centre, keyboard shortcuts.

Requirement coverage: `ADM-05` (V1.0) + `01,02,03,04,06..41` (V2.0; the payout/KYC/risk/account queue screens — ADM-03,04,06,09,10,11 — are built in the V1.0 era as thin queue views per docs/00 §6 and hardened in V2).

## 2. Architecture

```
 Next.js 15 (web/adm) — same monorepo, different app + different realm
   │  · subdomain console.alphaone.example (SEPARATE from TD — PRD
   │    non-negotiable: own auth realm, separate session storage)
   │  · staff roles only (firm:*) — a trader identity cannot render ADM
   │    (AUTH realm split + Cerbos: no policy grants firm:* to user:*)
   │  · RSC data pages + client islands (queue tables, composer, detail
   │    panes); live queue updates via SSE (the same relay pattern as TD,
   │    scoped to staff topics)
   ▼
 GW (staff routes /v1/admin/* — 04) → Go domain APIs
   (PAY, LCC, KYC, RSK, CHK, BRG read, NOT, ANA, TEN settings)
```

**Principle:** ADM is a **workqueue client over the same APIs the backend
owns**. Every action button calls the domain endpoint that owns the
transition (ADM never calls "force state" endpoints that bypass LCC/PAY
state machines — the LCC-41 rule generalized: ADM triggers, domains
enforce). V1 queue badges = server-side counts on shell load + SSE
updates (no polling storms).

## 3. System design

### 3.1 V1 screens

| Screen | Content | Backend surface |
|---|---|---|
| **Queue home** | unprocessed counts (payout, KYC, risk, support-triage), SLA aging columns (V2 config; V1 fixed: > 24 h amber, > 72 h red) | per-queue count endpoints |
| **Accounts (ADM-05)** | list: id, trader, package, state, phase, opened date, equity (observed), breach flag; filters: state, package, trader name/id, date range; export CSV (V2 ADM-25; V1: the list only) | LCC admin account-list reads (07 §7) |
| **Account detail (ADM-06)** | tabs: Overview (state machine timeline — `account_state_history`), Metrics (observed vs evaluated — the EVL-49 pair, side by side, for dispute triage), Positions/Deals (BRG read), Payouts, Documents (signed URL fetch), Events (the audit mirror for this entity), Actions (pause/resume, request halt, open risk case, note) | LCC/BRG/PAY/DOC/AUD reads + LCC command endpoints |
| **Payout queue** | table: trader, account, amount, rail, age, eligibility re-check badge (live), risk flag; approve (2FA dialog) / reject (reason taxonomy) / detail (calc snapshot, executions, method version) / export (PAY-44) | PAY admin API (11 §7) |
| **KYC queue** | manual_review sessions: trader, level, provider verdict, reason class, doc viewer (sensitive-read audited), decide (2FA + reason) | KYC admin API (13 §7) |
| **Risk cases** | open/reopened cases: severity, signals summary, trader, accounts, payout hold state; decide (outcome + note; actions execute per RSK §3.4); V1 auto-opened breach cases appear here | RSK API (10 §7) |
| **Traders (ADM-03/04)** | list + detail (identities, accounts, KYC status, payout history, notes); actions: suspend/resume identity (2FA), note | AUTH identity admin + read joins |
| **Settings (V1 minimum)** | tenant profile basics, brand assets (TEN-05/06), payout policy display (read-only V1; edit = TEN API, 2FA), provider rail matrix display | TEN APIs (03) |

### 3.2 Queue mechanics (the V1 core)

- **Claim pattern (V1 simple, V2 ADM-36 assignment):** V1 = no assignment
  (any staff in role can act; the actor is recorded); V2 = claim/assign with
  SLA clocks. The API supports both from day 1 (`assigned_to` nullable) —
  V1 just doesn't fill it.
- **Aging:** computed server-side (`created_at` → now); the SLA thresholds
  are V2 config (ADM-33), V1 hard-coded 24/72 h (FunderBlu default).
- **Concurrency:** two staff clicking approve on the same payout → the
  domain state machine resolves (second gets `pay.state_conflict` 409 →
  toast + row refresh). No optimistic UI on state-changing buttons.
- **Live feed (V2 ADM-30; V1 minimum):** queue rows update on SSE events
  (a payout approved elsewhere removes it from my view within 2 s).

### 3.3 Action safety model

Every state-changing action in ADM follows the same contract:
1. **2FA step-up** (AUTH) — always, no exceptions in V1 (even "low-risk"
   actions; the cost is one TOTP entry, the value is uniform audit).
2. **Reason capture** where the domain requires it (reject: reason code;
   override: mandatory text).
3. **Confirmation dialog** naming the object + the effect in plain language
   ("Suspend trader Ali K. — they will lose access to all 2 accounts.
   Payouts are blocked.")
4. **Critical-tier audit** (AUD) with the full before/after.
5. **Reversibility shown:** the dialog names how to undo ("resume from
   Traders detail") — irreversibles (refund settle, document regenerate
   money doc) say so.

### 3.4 Dispute triage surface (the hidden V1 feature)

FunderBlu's support team will open "why did my account fail?" tickets. The
account detail's **Metrics tab** (observed vs evaluated side-by-side, 09 §3.4)
+ **Events tab** (audit mirror) + **Documents** (breach notice) is the
complete evidence pack — the target: a support agent answers a breach
dispute without escalating to the dev team, from one screen.

## 4. Events (consumed by ADM)

| Event | Use |
|---|---|
| `payout.status_changed` | queue live update + badge |
| `kyc.status_changed` (manual_review) | KYC queue |
| `risk.case_opened/decided` | risk queue |
| `account.state_changed` | account list badges + SSE |
| `notification.failed_final` / `system.*` ops events | ops alert surface (V1: a simple "ops alerts" list on the home; V2: routing ADM-37) |
| `audit.access_denied` (V2) | security tab (V2) |

## 5. Lifecycles

- **Queue item:** `unprocessed → (acted) → resolved` (V1); V2 adds
  `assigned → claimed → (sla_breached flag) → resolved`.
- **Action session:** step-up MFA < 5 min (AUTH) — the 2FA window for the
  whole action batch.
- **Export (V2 ADM-25/31):** `requested → running → available (R2 URL, 24 h)
  → expired`.
- **Broadcast (V2 ADM-15):** `draft → preview → sent` (NOT-14 contract).
- **Session:** staff sessions (AUTH realm split); idle 15 min (stricter than
  TD's 30 — money actions); concurrent admin sessions allowed (audit
  distinguishes actors).

## 6. Error taxonomy

ADM presents domain codes (no new namespace). UI-level classes mirror TD §6
plus:

| Class | Trigger | UI |
|---|---|---|
| `CONFLICT` | 409 on any action button | toast + auto row-refresh (someone else acted) |
| `stepup.expired` | 403 `auth.mfa_required` after 5 min | 2FA dialog reopens (object preserved) |
| `forbidden.role` | 403 Cerbos denial | "you need {role}" + link to settings (ADM-17 V2) |
| `export.busy` | 429 concurrent export cap | queue position shown (V2) |

## 7. API endpoints
### 7.1 V1 baseline — `adm` (see `contracts/api/adm.md`)

**No HTTP surface in V1** — this is an internal/service contract. The internal contracts (what other modules call, what workers run, what is enforced) are in `contracts/api/adm.md`.

### 7.2 Extended (post-V1) surface — provisional

> Not in the V1 execution sheet. Design-level; paths beyond the V1 baseline are provisional until the URL-plan decision (`contracts/api/gw.md`, open question). Shown for platform completeness (V2/V3 phases, docs/99).

ADM consumes: LCC admin (account-list reads, detail reads, command triggers —
07 §7), PAY admin (11 §7), KYC admin (13 §7), RSK admin (10 §7), CHK
admin (12 §7: wire capture, refunds, recon import), AUTH identity admin
(02 §7: suspend/resume, role grant), ANA reads (19 §7: KPI cards), TEN
settings (03 §7), AUD viewer (V2 ADM-18; V1: the per-entity events tab reads
the audit mirror), NOT admin (14 §7: templates/test send), BRG read
(08 §7: positions browser minimum = account detail tab).

ADM exposes **no endpoints** (it's a client).
## 8. Schema (key shapes — what ADM renders)

```jsonc
// queue home (shell load)
{ "data": { "payout_pending": 4, "kyc_manual": 2, "risk_open": 1,
    "ops_alerts": 0, "aging": { "payout_24h": 1, "payout_72h": 0 } } }

// account detail (overview tab)
{ "data": { "id": "01J9ACC...", "trader": { "id": "01J9...", "name": "Ali K.",
    "identity_state": "active" },
  "package": "Funded $100K", "state": "breached",
  "state_timeline": [ { "state": "funded", "at": 1758100000000 },
                       { "state": "breached", "at": 1758278400000,
                         "verdict_ref": "01J9EVL…" } ],
  "actions_available": [ "request_halt", "open_risk_case", "note",
                         "view_evidence" ] } }
```

## 9. Database design

**None** (FE never touches PG). ADM's state: session cookie (staff realm),
URL state for filters (shareable queue links — the `?status=pending_approval`
URL is the workflow handoff tool), localStorage for layout prefs only.

## 10. Security & compliance

- **Realm separation (PRD non-negotiable):** console subdomain, separate
  Better Auth org + Cerbos realm — a trader's session cookie is useless
  against `/v1/admin/*` (the GW rejects cross-realm tokens structurally, 02
  §3.4).
- **2FA on all state-changing actions** (§3.3) — including role grants
  (ADM-17 V2) and settings writes (TEN config changes are 2FA + critical
  audit).
- **Sensitive reads audited:** KYC docs, credential data (ADM sees masked
  broker credentials + a "reveal via support" path, not a direct reveal —
  broker passwords are trader-owned; ADM requests a BRG reset instead),
  payout method strings.
- **No bulk destructive actions in V1** (ADM-24 V2 with explicit caps +
  2FA + dry-run preview).
- **Session hygiene:** 15 min idle, concurrent sessions allowed, login
  anomaly scoring applies to staff too (02 §3.7) — a staff account is a
  higher-value target, and the same controls apply.
- **Export data governance (V2):** exports contain PII → R2 24 h TTL +
  download audit + role cap (`firm:owner`/`firm:compliance`).
- **Audit viewer (V2 ADM-18):** reads the AUD mirror (05) — the viewer is
  itself audited (who looked at the audit log).

## 11. Scalability considerations

- Volume: 5-20 staff per tenant; queues < 500 items (V1 FunderBlu scale).
  No pagination pressure; server-side filtering keeps list endpoints < 100 ms.
- SSE per staff session (not per trader) — trivial.
- Account list at 10k accounts: indexed filters (state, package, date) +
  LIMIT/OFFSET pagination (keyset for V2); export offloads heavy reads
  (R2 + async, V2).
- Detail tabs are independent fetches (a slow BRG read never blocks the
  timeline tab) — per-tab error boundaries.
- The shell is the only page with N queue counts: one batched count endpoint
  (1 query per queue, UNION view V2 if slow) — never 6 sequential fetches.

## 12. Open-source solutions

| Option | Verdict |
|---|---|
| **Next.js 15 (web/adm, binding stack)** | **CHOSEN** — same monorepo/toolchain as TD; FE-1/FE-2 velocity |
| shadcn/ui (data-table components) | **CHOSEN** — the queue tables are shadcn Table + TanStack Table |
| TanStack Table (sorting/filtering) | CHOSEN (V2 global search builds on it) |
| react-hook-form + zod (action dialogs) | CHOSEN |
| storybook | CHOSEN (shared with TD — the design system lives in `web/shared`) |
| Full low-code admin generators (refine, react-admin) | Rejected: queue-specific UX (2FA dialogs, live badges, evidence tabs) beats generic CRUD; a generator would fight the safety model |
| FullCalendar (news calendar ADM-23, V2) | V2 candidate |

## 13. Technology stack

Next.js 15 (web/adm), TypeScript, Tailwind, shadcn/ui + TanStack Table,
react-hook-form/zod, SSE, Sentry, pnpm monorepo.

## 14. Integration — internal modules (glue)

| Module | How |
|---|---|
| **GW** | all calls under `/v1/admin/*`; realm-scoped auth; rate limits (staff tier higher than trader tier) |
| **AUTH** | staff login (Better Auth console realm), roles (Cerbos firm:*), step-up 2FA, identity admin |
| **LCC** | account list/detail, state timeline, action triggers (pause/halt commands — LCC enforces) |
| **PAY** | the payout queue is ADM's highest-stakes screen (11 §7 admin API) |
| **KYC/RSK** | manual review + risk case queues (13/10 §7) |
| **CHK** | wire capture (2FA), refund management, recon import (12 §7) |
| **BRG** | positions/deals read (08), provider health display (V2 ADM-26 broker mgmt) |
| **ANA** | KPI cards on the queue home (V2 ADM-02 dashboard) |
| **NOT** | template editor + test send + broadcasts (14 §7 admin) |
| **TEN** | settings pages → TEN config APIs (03); brand assets |
| **AUD** | per-entity event tabs (V1); full viewer (V2 ADM-18) |
| **SUP** | shared trader/account context: ADM can open a support ticket with the current object pre-filled (and vice versa — SUP escalations appear in the relevant queue) |

## 15. Integration — external tools

Better Auth (console realm), Sentry, Cloudflare, (V2) FullCalendar, R2
(exports).

## 16. Implementation blueprint

| Step | Owner | Est | Depends | Exit criteria |
|---|---|---|---|---|
| 1. Shell (web/adm): realm login, nav, queue home with live badges (SSE), global id search | FE-1 | 3 d | AUTH console realm, GW admin routes | staff login on console subdomain; trader session rejected (tested) |
| 2. Account list (ADM-05) + account detail (overview/timeline tabs + actions) | FE-1 | 4 d | 1, LCC admin APIs | filters work; state timeline renders; pause action with 2FA + audit |
| 3. Payout queue (live re-check badge, approve/reject 2FA dialogs, detail with calc snapshot, export) | FE-1 | 4 d | 2, PAY admin APIs | FunderBlu finance dry-run: approve 5 + reject 2 sandbox payouts, every step 2FA'd |
| 4. KYC manual review queue (doc viewer with sensitive-read audit, decide) | FE-1 | 2.5 d | 2, KYC admin APIs | undecided session → decided, all reads audited |
| 5. Risk cases queue (V1 flow) + trader list/detail + actions | FE-1 | 3 d | 2, RSK/AUTH admin | breach case → decide → payout hold release visible in PAY queue |
| 6. Settings minimum (brand, payout policy display, rail matrix) + ops alerts list | FE-1 | 2 d | 2, TEN APIs | tenant rebrand reflected in TD email within one template render |
| 7. Queue concurrency hardening (409 handling, no optimistic UI) + a11y + responsive | FE-1 + FE-2 | 2 d | 3–6 | two-browser conflict test passes; keyboard-only navigation of all queues |
| 8. V2: dashboard (ADM-02), challenge manager, verification queue, composer, live feed, reports, coupons, broadcast, template editor, team/roles, audit viewer, webhook manager, positions browser, news calendar, bulk ops, exports, broker mgmt, forecast, SLA config, offers, search 2.0, assignment, alert routing, checklist, notif centre, shortcuts | FE-1 + FE-2 | 4 wks | 7 + the V2 backend surfaces | each V2 ADM screen lands with its backend module in the same phase (99 maps this) |

**Risks:** ADM underbuild in V1 (the PRD's 1-req V1 scope tempts scope
creep *down* — but manual payouts without the queue are impossible; the
queue-justification in §1 is the commitment); queue UX complexity (2FA
dialogs + live updates + conflict toasts = interaction testing is the exit
criteria, not a checklist); two FE split (FE-1 on ADM V1, FE-2 on
marketing/CON — the shared design system in `web/shared` is what makes the
split safe; step 8's V2 burst is the reskilling point).

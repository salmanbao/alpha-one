# 20 — CRM: CRM & Communications

> Covers PRD module **CRM** (15 requirements). All V2/V3. CRM is the
> **marketing-communications** layer: who a trader is in their lifecycle,
> what we may say to them, and the campaigns we say it with. It deliberately
> does **not** replace NOT (delivery) or SUP (support) — CRM decides
> *audience + message + timing*; NOT executes delivery; SUP owns inbound.

## 1. Purpose & scope

**V2 (7):** tags & internal notes (CRM-01), communication history (CRM-02 —
the unified log of everything sent to a trader across all channels), saved
segments (CRM-03), segment consumption (CRM-04 — NOT/ADM consume segments),
lifecycle stage tracking (CRM-05 — the funnel the reports in ANA-09 make
actionable), suppression & preferences (CRM-07), unsubscribe & compliance
(CRM-10).

**V3 (7):** automated sequences (CRM-06 — event-triggered drip: "purchased
but KYC incomplete after 24 h" → sequence), campaign performance (CRM-08),
Discord community integration (CRM-09), marketing consent capture (CRM-11 —
the consent record behind every marketing email), contact scoring
(CRM-14), campaign email templates (CRM-15), multi-channel campaigns
(CRM-13 — email + Telegram + in-app in one campaign).

**Out of scope (by design):** support conversations (SUP), transactional
email (NOT — CRM never sends the "your payout settled" class), and the
trader-facing surfaces (TD).

Requirement coverage: `CRM-01,02,03,04,05,07,10` (V2) + `06,08,09,11,13,14,15`
(V3).

## 2. Architecture

```
 CRM (Go domain pkg — part of the workers process for sequences, api for
     CRM-admin surfaces in CON/ADM):
   segments   ← event consumers (funnel steps, engagement events, KYC state,
                payout history) → segment membership is COMPUTED, not stored
                as a fixed list (a segment is a query: "funded, no payout
                request in 14 d, tenant X") — recomputed on schedule (15 min)
                into a membership snapshot table for fast NOT consumption
   sequences  ← event triggers (V3 CRM-06): step engine (PG state per
                (trader, sequence, step)) — the LCC pattern applied to
                marketing (deterministic, auditable, replayable)
   campaigns  ← staff-created (V2 manual sends: segment × template × channel
                → handed to NOT as a batch with CRM correlation ids)
   consent    ← capture points (TD signup checkbox, V3 CRM-11; NOT
                unsubscribe links, 14 §3.4) → the single consent record
   suppression ← NOT bounce/complaint (14 §3.5) + CRM-10 unsubscribes →
                the NOT suppression list is the enforcement point (CRM
                writes it; NOT enforces it — same separation as RSK→PAY)
```

**The one rule that keeps CRM honest:** CRM output is always
`{segment, template, vars, channel, consent_check_result}` handed to NOT —
CRM has no direct mail provider access. Consent + suppression are checked
at dispatch (NOT), so even a misconfigured campaign can't email someone
who unsubscribed.

## 3. System design

### 3.1 Lifecycle stages (CRM-05)

```
prospect → registered → kyc_in_progress → purchased → evaluating →
funded → paid_out → dormant (30 d no activity) → churned (account closed,
60 d) / breached
```

Stages derive from the same funnel facts as ANA-09 (`funnel_steps` +
account state + payout history) — **one computation, two consumers** (ANA
reports, CRM segments). A trader's stage is a read-model attribute
(`traders_ro.lifecycle_stage`, ANA-01) — CRM doesn't own a copy.

### 3.2 Segments (CRM-03/04)

- Definition: a named query (registry row: name, tenant, SQL template over
  read models, cadence, enabled). V2 starter set: "new funded (7 d)",
  "funded no payout (14 d)", "KYC stalled (48 h)", "near first payout
  window", "dormant", "at-risk (breached, repurchase candidate — with the
  tone guard: re-engagement after breach is COO-approved copy only)".
- Consumption: NOT batch dispatch reads the membership snapshot (the 15-min
  recompute table); ADM shows segment sizes + composition preview (top 50,
  masked); a campaign stores the **snapshot version** it used (audit: "who
  was emailed on that campaign" is answerable exactly).

### 3.3 Consent & unsubscribe (CRM-10/11 — the compliance core)

- **Consent record** per (identity, tenant, purpose): purposes =
  `transactional` (implied by purchase — not toggleable, honestly labeled),
  `marketing_email`, `marketing_telegram` (V3), `updates` (product news).
  Captured at signup (TD checkbox, V2) — pre-ticked boxes are banned
  (the design rule: the checkbox renders unchecked).
- **Unsubscribe** = a one-click link in every marketing email → immediate
  suppression (NOT list) + consent update + confirmation email (no further
  interaction — the GDPR/CASL pattern).
- **Suppression precedence:** complaint > unsubscribe > consent-withdrawn >
  segment rules. The NOT suppression table (14 §9) is the single
  enforcement store; CRM and NOT both write it with distinct reasons.
- **Records retention:** consent + unsubscribe history 7 yr (compliance
  evidence that we stopped emailing someone is itself regulated data).

### 3.4 Sequences (V3 CRM-06)

Event-triggered drip with the LCC discipline: `sequence_steps` state
machine per (trader, sequence) — `active → step_n → (event) → step_n+1 →
completed | exited (stage changed | unsubscribed | sequence version
replaced)`. Exit conditions are evaluated on every step dispatch (a
trader who completed KYC exits the "KYC stalled" sequence before its next
step). Sequence runs are **audited** (what was sent, when, under which
consent version) and **idempotent** (event replay can't double-send — the
dedupe pattern from NOT §3.5).

### 3.5 Campaigns (V2 manual; V3 multi-channel)

A campaign = `{tenant, name, segment (snapshot version), template (CRM-15
V3 / NOT template V2), channel(s), send window (quiet-hours aware via
NOT), status}`. V2: manual "send now" or scheduled (worker cron, advisory
lock). V3: multi-channel fan-out with per-channel consent checks and a
single performance rollup (CRM-08: opens/clicks via Postmark stats +
Telegram read receipts + in-app open events — the click URL carries the
campaign+trader ref, first-party only).

## 4. Events (topic `crm`)

| Event | When | Consumers |
|---|---|---|
| `crm.segment_recomputed` | 15-min cadence / manual | AUD (low) |
| `crm.campaign_sent` | batch dispatched to NOT | NOT (the actual sends), ANA (CRM-08 inputs), AUD (critical: marketing sends are tenant-visible) |
| `crm.sequence_advanced` / `crm.sequence_exited` (V3) | step engine | AUD (low) |
| `crm.consent_changed` | capture/unsubscribe/withdrawal | NOT (suppression list), AUD (critical) |
| `crm.unsubscribe` | link clicked | NOT, AUD |

Consumes: funnel steps, `account.state_changed`, `payout.*`, `kyc.*`,
`notification.bounce/complaint` (suppression sync).

## 5. Lifecycles

- **Segment:** `active → paused → archived` (versioned definitions).
- **Membership snapshot:** rolling 15-min versions, 7-day retention (the
  audit trail of "who was in the segment when").
- **Campaign:** `draft → scheduled → sending → sent → (report)`; cancel
  allowed pre-send (mid-send: the batch stops at the batch boundary — NOT
  batches ≤ 500, so worst-case overage is one batch, logged).
- **Sequence run:** §3.4 machine.
- **Consent record:** `granted → withdrawn` (append-only history rows).
- **Suppression entry:** NOT's list (§3.3 precedence), 12-mo sunset for
  bounces (re-tryable), **no sunset for unsubscribes** (a human re-subscribe
  is the only path back).

## 6. Error taxonomy

Namespace `CRM`:

| Code | HTTP | Meaning |
|---|---|---|
| `crm.segment_not_found` | 404 | — |
| `crm.segment_empty` | 200 + warning | Campaign on an empty segment (allowed; the confirmation shows "0 recipients") |
| `crm.campaign_sending` | 409 | Duplicate send trigger |
| `crm.template_invalid` | 422 | (V3) Template render failure in preview |
| `crm.consent_missing` | 422 | Marketing send attempted without consent capture point configured (V3) |
| `crm.sequence_version_replaced` | — | Info: active runs exit at next step |
| `crm.unsubscribe_unknown` | 404 | Bad token (page: "nothing to do here", no leak of validity) |

## 7. API endpoints
> **Scope note:** CRM is not in the V1 execution sheet (V2 scope). There is no V1 baseline contract for this module; the surface below is design-level (post-V1, docs/99) and provisional until its phase's contract freeze.


Staff (CON/ADM — CRM surfaces live in the console for platform staff and in
ADM for tenant marketing, V2):
`GET /v1/crm/segments` (+ `POST`, `POST /{id}/recompute`),
`GET /v1/crm/segments/{id}/preview` (size + masked top 50),
`GET|POST /v1/crm/campaigns`, `POST /{id}/send` (2FA),
`GET /{id}/performance` (V3),
`GET /v1/crm/traders/{id}` (stage, tags, notes, communication history,
consent),
`POST /v1/crm/traders/{id}/tags`, `POST /{id}/notes` (CRM-01),
`GET /v1/crm/history?identity=` (CRM-02: the unified log — NOT delivery
events + SUP tickets + CRM campaigns, one timeline),
unsubscribe: `POST /v1/public/crm/unsubscribe` (token, no auth) +
`GET /v1/public/crm/preferences` (token — the V2 prefs page: toggle
purposes, the consent record edited).

## 8. Schema (key shapes)

```jsonc
// GET /v1/crm/traders/{id}
{ "data": { "identity_id": "01J9...", "name_masked": "Ali K.",
    "lifecycle_stage": "funded", "tags": ["vip", "kolkata-office"],
    "consent": { "marketing_email": "granted@2026-07-01", "updates": "granted@2026-07-01" },
    "notes": [ { "body": "Asked about scaling plan — sent doc", "by": "01J9…", "at": 1758200000000 } ],
    "history": [ { "channel": "email", "kind": "campaign", "subject": "Your payout window is open",
                    "at": 1758282000000 },
                  { "channel": "support", "kind": "ticket", "subject": "Payout question", "at": 1758100000000 } ] } }

// segment definition
{ "data": { "id": "01J9SEG...", "name": "funded_no_payout_14d",
    "sql_template": "… over accounts_ro/payouts_daily …",
    "size": 42, "last_recomputed": 1758282150000 } }
```

## 9. Database design

```sql
CREATE TABLE crm_segments (
  id          ULID PRIMARY KEY,
  tenant_id   ULID NOT NULL,
  name        TEXT NOT NULL,
  sql_template TEXT NOT NULL,               -- allowlisted tables only (review gate)
  cadence_min INT NOT NULL DEFAULT 15,
  enabled     BOOLEAN NOT NULL DEFAULT true,
  created_by  ULID, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, name)
);
CREATE TABLE crm_segment_members (           -- the snapshot (recomputed)
  tenant_id ULID NOT NULL, segment_id ULID NOT NULL,
  identity_id ULID NOT NULL,
  computed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (tenant_id, segment_id, identity_id)
);
CREATE INDEX idx_segmem_computed ON crm_segment_members(computed_at);

CREATE TABLE crm_campaigns (
  id          ULID PRIMARY KEY,
  tenant_id   ULID NOT NULL,
  name        TEXT NOT NULL,
  segment_id  ULID NOT NULL,
  snapshot_at TIMESTAMPTZ NOT NULL,          -- which membership version
  template    TEXT NOT NULL,                 -- NOT template key@version
  channels    TEXT[] NOT NULL DEFAULT '{email}',
  status      TEXT NOT NULL DEFAULT 'draft'
    CHECK (status IN ('draft','scheduled','sending','sent','cancelled')),
  sent_count  INT, created_by ULID,
  sent_at     TIMESTAMPTZ, created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE crm_consent (                   -- append-only history
  id          ULID PRIMARY KEY,
  tenant_id   ULID NOT NULL, identity_id ULID NOT NULL,
  purpose     TEXT NOT NULL,                 -- marketing_email|marketing_telegram|updates
  state       TEXT NOT NULL,                 -- granted|withdrawn
  source      TEXT NOT NULL,                 -- signup|prefs_page|unsubscribe|manual
  at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_crmconsent_current ON crm_consent(tenant_id, identity_id, purpose, at DESC);
-- tags/notes: identity_tags (identity_id, tag, created_by) + identity_notes
-- (identity_id, body, author) — both audit-mirrored; sequence state (V3):
-- sequence_runs (identity, sequence, step, state, updated_at)
```

## 10. Security & compliance

- **Marketing data separation:** CRM reads **masked** read models only
  (traders_ro) — it never touches raw emails (NOT resolves recipient at
  dispatch); the campaign object doesn't contain addresses.
- **Consent is the compliance record** (§3.3): 7-yr retention, the
  unsubscribe flow is first-class (one click, no login, no "are you
  sure" — the legal pattern), suppression precedence is enforced in NOT
  (the enforcement point can't be bypassed by CRM bugs).
- **Segment SQL allowlist:** templates may reference only the
  `*_ro`/`*_daily` read models (a lint + CI check — a segment query that
  references a PII table fails review; the recompute job runs as a
  read-only role that cannot see non-ro tables).
- **Marketing vs transactional labeling:** honest in every email footer
  (TD §10 rule) — "transactional" sends carry no unsubscribe (they're
  contractual), "marketing" always do.
- **Multi-tenant marketing:** a tenant can only segment/send to its own
  traders (structural: the tenant_id on every row); the platform's own
  marketing (cross-tenant) is V3 ANA-28-class work with its own legal
  review — **not** in V2.
- **Discord integration (V3 CRM-09):** role-based, read-write via the
  Discord API with a dedicated bot account; the bot's DMs route into
  SUP (support) — marketing-in-DMs is banned (spam surface + trust).

## 11. Scalability considerations

- Segment recompute: 15-min cadence × ~20 segments × a few indexed queries
  each = seconds of CPU; the membership table is ≤ identity-count ×
  active segments (10k traders × 20 = 200k rows) — trivial.
- Campaign sends: batches of 500 through NOT (its rate limits, 14 §3.6) —
  a 10k-trader campaign ≈ 30 min (the quiet-hours window is a feature:
  nobody is surprised by a 3 a.m. marketing email).
- History timeline (CRM-02): a UNION of three indexed tables (NOT
  notifications, SUP tickets, CRM campaigns) — per-trader queries,
  < 50 ms.
- The sequence engine (V3): ≤ 1k active runs × 1 step/hour = nothing;
  the PG advisory-lock worker pattern (06) scales it.
- Postmark stats (opens/clicks) polled hourly into ANA (V3 CRM-08) —
  no webhook needed at this volume.

## 12. Open-source solutions

| Option | Verdict |
|---|---|
| **In-house Go domain pkg + NOT** (this design) | **CHOSEN** — CRM's value is the consent/suppression/segment discipline on top of NOT; a full CRM (Mautic, Listmonk, etc.) would be a second mail sender — exactly the duplication §2 forbids |
| Listmonk (self-hosted newsletter) | Rejected: it owns its own lists + sending — the consent enforcement point would split across two systems |
| Mautic (full CRM/MA) | Rejected: PHP stack + its own DB + a 3-week integration to do what the domain pkg + NOT already do |
| Postmark stats API | CHOSEN (deliverability data, V3 CRM-08) |
| Discord API (V3) | Direct (bot account) |

## 13. Technology stack

Go domain pkg (api + workers: recompute, sequences V3, campaign batches);
Postgres (segments/campaigns/consent/history); NOT (all delivery); ANA
(read models = the segment substrate); R2 (V3 campaign assets); Postmark
(via NOT); Prometheus (recompute lag, campaign throughput, consent change
rate); Sentry.

## 14. Integration — internal modules (glue)

| Module | How |
|---|---|
| **NOT** | the delivery contract: campaigns/sequences dispatch as NOT batches; NOT enforces consent + suppression (the split in §2); bounce/complaint feeds CRM's suppression writes |
| **ANA** | `traders_ro` + `funnel_steps` + dailies = segment substrate + lifecycle stage (one computation, two consumers — §3.1) |
| **SUP** | communication history (CRM-02) includes tickets; Discord DMs (V3) route to SUP |
| **TD** | consent capture at signup (V2 CRM-11 early), the prefs page (V2), unsubscribe target |
| **CON/ADM** | CRM surfaces (console for platform, ADM for tenant marketing — both read the same APIs) |
| **TEN** | tenant marketing config (default consent copy, quiet hours, send windows) |
| **RSK** | (V2+) re-engagement segments for breached traders are COO-gated; RSK watchlist traders are **excluded** from all marketing segments (a hard filter in the recompute — the rule: no marketing to someone under risk review) |
| **AUD** | campaign sends (critical), consent changes (critical), segment recompute (low) |

## 15. Integration — external tools

Postmark (via NOT — stats API), Discord API (V3), R2, Prometheus/Grafana,
Sentry.

## 16. Implementation blueprint

| Step | Owner | Est | Depends | Exit criteria |
|---|---|---|---|---|
| 1. Consent record + capture points (signup checkbox, prefs page, one-click unsubscribe) + suppression sync with NOT | BE-2 | 3 d | NOT, TD | unsubscribe click → suppressed within 1 s; transactional still delivers (the legal-critical test) |
| 2. Segment registry + recompute worker (15 min) + membership snapshots + preview API + SQL allowlist lint | BE-2 | 3 d | ANA read models | 5 starter segments recompute correctly; allowlist lint rejects a PII-table query |
| 3. Campaigns (manual + scheduled) → NOT batches + snapshot versioning + cancel-at-batch-boundary | BE-2 | 2.5 d | 1–2, NOT batches | 1k-trader staging campaign: exact recipient set = snapshot version (re-queried and matched) |
| 4. Tags/notes + unified history timeline + lifecycle stage surfacing in ADM/CON trader views | FE-1 + BE-2 | 3 d | 2–3, SUP | one screen shows a trader's full comms history (3 sources, merged, ordered) |
| 5. Compliance pass: retention jobs, consent audit export, footer labeling audit, RSK-exclusion filter | BE-2 | 1.5 d | 1–4 | property: a watchlisted trader appears in zero campaign batches (tested) |
| 6. V3: sequences (LCC-pattern step engine), multi-channel campaigns, performance rollups (Postmark stats + Telegram + in-app), scoring, Discord integration | BE-2 | 3 wks | 5 | a KYC-stalled sequence advances on the KYC event and exits on verification — audited |

**Risks:** consent-state divergence (CRM vs NOT beliefs) (mitigation: the
single suppression store in NOT + the consent record as the only source of
marketing permission — one writer per fact); segment SQL becoming a PII
channel (mitigation: allowlist lint in CI + read-only role + review gate —
the recompute job literally cannot SELECT from identity tables);
marketing fatigue/deliverability damage (mitigation: quiet hours, caps,
unsubscribe friction = zero, the bounce monitor from NOT §14); the RSK
exclusion rule being forgotten by a future feature (mitigation: it's in the
recompute itself, not in each campaign — a segment can't include
watchlisted traders at any layer).

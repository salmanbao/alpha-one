# 14 — NOT: Notifications

> Covers PRD module **NOT** (41 requirements). Every other module emits
> events; NOT is where those events become **messages a human receives** —
> email in V1, in-app + Telegram in V2. NOT is deliberately a **dumb pipe
> with good hygiene**: it never decides *what* happened (the producer's
> event says that), it decides *who gets what message, when, in which
> channel, and exactly once*.

## 1. Purpose & scope

- **Event consumer (NOT-01):** subscribes to the event bus; maps events →
  notification templates (the mapping table is data, §3.3).
- **Email provider adapter (NOT-03):** **Postmark** (register, SIGNED-capable)
  behind the `mail.Send` interface.
- **Core transactional templates (NOT-05):** the V1 set (§3.4).
- **Idempotency & deduplication (NOT-13):** the same logical notification is
  never sent twice (event replay, redelivery, producer retry all absorbed).
- **V2:** channel abstraction (NOT-02), full template engine with branding
  (NOT-04/06), in-app store + widget (NOT-07/08), Telegram (NOT-09/10),
  preferences (NOT-11), delivery logs (NOT-12), broadcasts (NOT-14), retry +
  DLQ (NOT-15), bounce/complaint (NOT-16), SMS/WhatsApp (NOT-17/18), test
  send (NOT-20), mapping admin (NOT-21), dashboard (NOT-22), escalation
  (NOT-23), quiet hours (NOT-24/36), priority (NOT-25), trader history
  (NOT-28), consent (NOT-29), rate limits (NOT-30), failure semantics
  (NOT-32), versioning (NOT-33), SLA (NOT-37), digest (NOT-39), throttling
  (NOT-41), suppression (NOT-26).

Requirement coverage: `NOT-01,03,05,13` (V1) + `02,04,06..22,23,24,25,26,28,
29,30,32,33,35,36,37,39,41` (V2) + `38,40` (V3).

## 2. Architecture

```
 EVT relay (Redis Streams) ──topics: account.*, payout.*, kyc.*, payments.*,
                                 risk.*, order/checkout events, system.*
      │  (NOT consumer group — its own lane, at-least-once)
      ▼
 NOT worker (Go, part of the workers process):
   1. map(event) → [ (recipient, template, vars, priority, channel) ]
        (mapping table in PG — admin-editable V2 NOT-21)
   2. dedupe: key = hash(event_type, entity_id, recipient, template_version)
        (Redis SETNX, TTL 24 h — same key as the GW idempotency pattern)
   3. prefs/suppression (V2: quiet hours, unsubscribes, digests)
   4. render template (PG-stored, tenant-branded V2) with vars from event
   5. dispatch via channel adapter:
        V1: Postmark (email)                    V2: + in-app (PG row + WS push)
           V2: Telegram Bot API, (SMS/WhatsApp providers)
   6. log delivery (NOT-12 V2; V1: table + Postmark stats API poll)
   7. failures: retry ×3 (backoff) → DLQ lane → ADM alert (NOT-15)
```

**Why in-house, not Novu** (research §5.1 top pick): Novu is excellent but
ships its own stack — **MongoDB + NestJS + extra infra** — which breaks the
binding stack (Postgres 16 + Redis 7 only, Go-first, one Compose, ADR-7).
What Novu gives (dashboard, prefs UI, in-app widget) we already build inside
TD/ADM with the same events. The engine we need is: map → dedupe → render →
send → log. That is ~2k lines of Go, not a platform. (If V2 channel sprawl
proves otherwise, the `channel` interface is the migration seam.)

## 3. System design

### 3.1 The notification unit

```
notification (PG):
  id · tenant_id · event_ref (stream entry id) · kind (mapping key)
  recipient {identity_id | staff_role | 'owner_broadcast'}
  channel (email|inapp|telegram|sms) · template_id · template_version
  vars JSONB (rendered-from, PII-safe: names, amounts, links, dates)
  state (pending|sent|delivered|failed|dlq|suppressed)
  provider_ref (Postmark Message-Id) · sent_at · delivered_at
  dedup_key (unique per TTL window)
```

The unit is **append-only**; a "fix" = a new notification (or a bounce-handled
suppression), never a mutation of a sent row.

### 3.2 Recipient resolution (the multi-tenancy crux)

- **Trader-facing:** recipient = the trader's identity (email from profile;
  V2: linked Telegram, in-app). Tenancy is structural: events carry
  `tenant_id`, templates are tenant-scoped.
- **Staff-facing:** recipient = **role within a tenant** (`firm:risk`,
  `firm:finance`) + the platform's own ops channel (system events: DLQ,
  circuit breakers, restore drills). Role → members resolution at send time
  (AUTH membership read) — a departing staff member stops getting email
  automatically (the membership row is gone).
- **Escalation (NOT-23 V2):** role chains (risk → risk → owner) with timers —
  the case-SLA and payout-SLA escalations from RSK/PAY reuse this.

### 3.3 Event → template mapping (data, not code)

`notification_mappings` (PG): `{event_type (e.g. 'payout.settled'),
channels[] (['email']), template_key (e.g. 'payout_settled'), priority
(critical|high|normal|low), vars_selector (JSONPath picks from event payload),
enabled, tenant_override?}`.

- V1 ships ~20 rows (the core set, §3.4); V2 makes it admin-editable
  (NOT-21) with a "test send" (NOT-20) preview.
- **vars_selector enforces PII hygiene:** only whitelisted event fields may
  flow into vars; the renderer rejects vars containing full PAN/wallet/KYC
  values (regex guard — the same masking rules as PAY/KYC).

### 3.4 V1 core templates (NOT-05)

Trader: `kyc_session_started`, `kyc_needs_docs`, `kyc_approved`,
`kyc_rejected` (reason class), `account_opening_started`,
`account_funded` (live-trading welcome + terms summary link),
`account_breached` (what happened + next steps, no jargon),
`account_halt_requested` (suspension), `payout_requested`,
`payout_rejected` (reason class), `payout_approved`, `payout_settled`
(+ receipt link), `payout_failed_final`, `payment_captured` (purchase
confirmed + invoice link), `payment_pending` (complete your payment, TTL),
`payment_refund_settled`.

Staff (per tenant): `payout_pending_approval`, `payout_approved_by_other`,
`payout_settled`, `risk_case_opened`, `risk_case_decided`,
`kyc_manual_review_needed`, `payment_reconciliation_exception` (V2),
`worker_dlq` (ops), `slo_breach` (ops, V2).

Each template: subject + body (HTML + text fallback), tenant branding
(V2 NOT-06: logo, colors from TEN-05/06; V1: platform-branded with tenant
name variable), unsubscribe footer (preferences link, V2 NOT-11), locale
(en V1 — the renderer supports i18n from day 1 so V2 ur/hi are content-only).

### 3.5 Idempotency (NOT-13 — the part that makes the rest safe)

`dedup_key = sha256(event_type + entity_id + recipient + template_key +
template_version)`; Redis `SETNX key 1 EX 86400` **before** render; on
collision → log `suppressed {reason: dedupe}` and ack. This means: relay
redelivery, relay restart from LastSeq, producer double-emit, and the
nightly event-log replay (04 §5.7) can all hit NOT safely. The 24 h window
matches the GW idempotency TTL (04) — same reasoning.

### 3.6 Delivery semantics

- **Postmark:** transactional server; `Message-Id` stored; bounce/complaint
  webhooks (V2 NOT-16: bounce → mark + suppress after 3, complaint →
  suppress + flag identity).
- **V2 channels:** in-app = PG row + WebSocket push (TD connects via the GW
  session — 01 topology) + polling fallback (TD-11 pattern); Telegram =
  Bot API send + `update_id` stored; SMS/WhatsApp via provider (V2).
- **Priority (V2 NOT-25):** `critical` (payout settled, breach, security)
  bypasses digest/quiet-hours; `normal`/`low` respect quiet hours (NOT-24)
  and digest batching (NOT-39: daily "your account summary" for low-priority).
- **Rate limits (V2 NOT-30/41):** per recipient (10/h normal, 50/h critical
  burst) and per template (200/h platform-wide) — the anti-herd-breach
  measure: 200 accounts breaching at the broker rollover must not melt
  Postmark limits or the trader's inbox.

## 4. Events (topic `notification`)

| Event | When | Consumers |
|---|---|---|
| `notification.sent` | channel accept (provider ref) | AUD (low tier), ANA (V2) |
| `notification.failed_final` | retries exhausted → DLQ | ADM (ops alert), CON, AUD |
| `notification.suppressed` | dedupe/prefs/quiet-hours/bounce | AUD (low), ANA |
| `notification.bounce` / `notification.complaint` (V2) | provider webhook | AUD |
| `notification.broadcast_sent` (V2) | staff broadcast | AUD (critical) |

NOT **consumes** (V1): `kyc.*`, `account.*` (LCC states incl. funded/breached/
halted), `payout.*`, `payments.*` (CHK), `risk.*` (cases), `ledger.*`
(anomalies → ops), `system.*` (ops: restore drill, backup failures).

## 5. Lifecycles

- **Notification:** `pending → sent → delivered | failed(→retry→)→ dlq |
  suppressed` (terminal).
- **Mapping row:** `active → disabled → (versioned archive, V2 NOT-33)`.
- **Template:** versioned rows; a mapping points at a version; publish =
  new version + mapping bump (V2 NOT-33; V1: single version, admin-edit
  with audit).
- **Suppression list (V2):** `active → (sunset 12 mo) → archived`; per
  (identity, channel, reason: bounce|complaint|unsub|manual).
- **Digest (V2):** `collecting → sent (daily 09:00 tenant TZ)`.

## 6. Error taxonomy

Namespace `NOT`:

| Code | HTTP | Meaning |
|---|---|---|
| `not.template_not_found` | 500-internal | Mapping references missing template (deploy error — CRITICAL alert) |
| `not.vars_invalid` | 500-internal | vars_selector produced empty/PII-guarded vars (alert + skip, never send half-rendered) |
| `not.recipoent_unknown` | 500-internal | No email/identity (alert — usually a data bug) |
| `not.provider_unavailable` | 503 | Postmark down (retry queue drains on recovery; critical templates page ops) |
| `not.rate_limited` | 429 | (V2) Per-recipient/template cap hit (batched into digest) |
| `not.suppressed` | — | Info state (not an error) |
| `not.broadcast_validation` | 422 | (V2) Broadcast preview failed |
| `not.tg_not_linked` | — | (V2) Telegram channel skipped (in-app fallback) |

## 7. API endpoints
### 7.1 V1 baseline — `not` (see `contracts/api/not.md`)

**No HTTP surface in V1** — this is an internal/service contract. The internal contracts (what other modules call, what workers run, what is enforced) are in `contracts/api/not.md`.

### 7.2 Extended (post-V1) surface — provisional

> Not in the V1 execution sheet. Design-level; paths beyond the V1 baseline are provisional until the URL-plan decision (`contracts/api/gw.md`, open question). Shown for platform completeness (V2/V3 phases, docs/99).

Trader (TD): `GET /v1/notifications` (in-app list, V2 NOT-07/08),
`POST /v1/notifications/read-all` (V2), `GET /v1/notifications/history`
(email history, V2 NOT-28), `GET|PUT /v1/notifications/preferences`
(V2 NOT-11: channels × categories, quiet hours NOT-24).

Staff (ADM): `GET /v1/admin/notifications/templates`,
`POST /v1/admin/notifications/templates` (V2 versioning),
`POST /v1/admin/notifications/templates/{id}/test` (NOT-20: render preview
to a specified address),
`GET /v1/admin/notifications/mappings` + `POST` (NOT-21),
`POST /v1/admin/notifications/broadcast` (NOT-14, 2FA, preview required,
tenant-scoped, never cross-tenant),
`GET /v1/admin/notifications/dashboard` (NOT-22: volumes, failure rate,
DLQ depth, template render errors).

Internal: Postmark webhooks `/v1/webhooks/postmark` (bounce/complaint,
EVT-10); (V2) Telegram webhook.
## 8. Schema (key shapes)

```jsonc
// notification row (internal; not exposed raw)
{ "id": "01J9NTF...", "tenant_id": "01J9TEN...", "event_ref": "3-1042",
  "kind": "payout_settled", "recipient": { "identity_id": "01J9ID..." },
  "channel": "email", "template": "payout_settled@2",
  "vars": { "trader_first_name": "Ali", "amount": "2,633.04",
            "currency": "USD", "receipt_url": "https://app.alphaone.example/payouts/01J9PAY…/receipt" },
  "state": "sent", "provider_ref": "abc123…@postmark", "sent_at": 1758282120000 }

// V2 preferences
{ "data": { "email": { "transactional": true, "updates": true, "digest": "daily" },
    "telegram": { "linked": true, "channels": ["critical", "high"] },
    "quiet_hours": { "enabled": true, "from": "22:00", "to": "07:00", "tz": "Asia/Karachi" } } }
```

## 9. Database design

```sql
CREATE TABLE notification_templates (
  id            ULID PRIMARY KEY,
  tenant_id     ULID,                          -- NULL = platform default
  key           TEXT NOT NULL,                 -- 'payout_settled'
  version       INT NOT NULL DEFAULT 1,
  subject       TEXT NOT NULL,
  body_html     TEXT NOT NULL,
  body_text     TEXT NOT NULL,
  branding      JSONB,                         -- V2: logo/color overrides (TEN-05/06)
  active        BOOLEAN NOT NULL DEFAULT true,
  created_by    ULID, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, key, version)
);

CREATE TABLE notification_mappings (
  id            ULID PRIMARY KEY,
  tenant_id     ULID,                          -- NULL = platform mapping
  event_type    TEXT NOT NULL,                 -- 'payout.settled'
  channels      TEXT[] NOT NULL DEFAULT '{email}',
  template_key  TEXT NOT NULL,
  priority      TEXT NOT NULL DEFAULT 'normal'
    CHECK (priority IN ('critical','high','normal','low')),
  vars_selector JSONB NOT NULL,                -- whitelisted event fields → vars
  enabled       BOOLEAN NOT NULL DEFAULT true,
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, event_type, channels)
);

CREATE TABLE notifications (
  id            ULID PRIMARY KEY,
  tenant_id     ULID NOT NULL,
  event_ref     TEXT,                          -- stream entry id (trace)
  kind          TEXT NOT NULL,
  recipient_identity ULID,
  recipient_role  TEXT,                        -- staff role target
  channel       TEXT NOT NULL,
  template      TEXT NOT NULL,                 -- 'key@version'
  vars          JSONB NOT NULL,
  state         TEXT NOT NULL DEFAULT 'pending'
    CHECK (state IN ('pending','sent','delivered','failed','dlq','suppressed')),
  suppress_reason TEXT,                        -- dedupe|bounce|complaint|prefs|quiet
  provider_ref  TEXT,
  attempts      INT NOT NULL DEFAULT 0,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  sent_at       TIMESTAMPTZ, delivered_at TIMESTAMPTZ
);
CREATE INDEX idx_not_tenant_state ON notifications(tenant_id, state, created_at DESC);
CREATE INDEX idx_not_identity ON notifications(recipient_identity, created_at DESC);
-- partitions by month from V2 if > 10M rows (delivery logs NOT-12 = same table)

CREATE TABLE notification_suppressions (        -- V2 NOT-26/16
  id            ULID PRIMARY KEY,
  tenant_id     ULID NOT NULL,
  identity_id   ULID NOT NULL,
  channel       TEXT NOT NULL,
  reason        TEXT NOT NULL,                 -- bounce|complaint|unsub|manual
  until         TIMESTAMPTZ,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, identity_id, channel, reason)
);
```

## 10. Security & compliance

- **PII guard on vars:** the renderer rejects vars matching PAN/wallet/KYC
  patterns (see §3.3) — a template author can't accidentally leak a full
  wallet address into an email; tests prove it (property: seed every event
  type with max-PII payloads → no leak in rendered output).
- **No cross-tenant mail:** tenant resolution is from the event's `tenant_id`
  (producer-stamped, relay-verified 04 §3.2) — NOT never re-resolves tenancy
  from recipient attributes (the classic multi-tenant leak).
- **Broadcasts (V2):** 2FA + required preview to a test address + tenant
  scope + critical-tier audit; the platform's own ops broadcasts are
  staff-role-scoped, never trader-facing without a tenant scope.
- **Unsubscribe compliance:** every email has the prefs link (V2); a
  transactional-only send still carries it (pointing at prefs where
  transactional = non-toggleable, per CASL-style honest labeling).
- **Retention:** notifications 12 months hot (delivery logs V2 NOT-12),
  then archive; bounces/complaints retained with the suppression row.
- **Postmark keys** per environment (SOPS), sender domain = platform domain
  + tenant custom-domain sending V2 (SPF/DKIM/DMARC documented — the Phase-1
  email-infrastructure checklist: DKIM failure = undeliverable money emails).

## 11. Scalability considerations

- V1 volume: ~200 notifications/day — Postmark limits are a non-issue.
- The real scaling story is the **herd event**: broker rollover with 200
  accounts breaching → 200 × (breach email + risk case + owner alert) in
  minutes. Design: the NOT consumer processes at 10 msg/s (deliberate),
  critical-only bypass, Postmark burst allowance, rate limits per §3.6,
  and the **digest** (V2) for anything non-critical. Load test target
  (V2 OPS-29): 500 events/min sustained → zero loss (DLQ = 0), p95 send
  latency < 60 s for critical.
- Worker: single instance (the workers process); consumer-group semantics
  mean V2 horizontal scale is a config change.
- In-app (V2): read = PG query (indexed), push = the TD WebSocket (01 §4.3
  pattern); no new store.
- Template render: text templating (no engine — Go `text/template` +
  a small filter set); render p95 < 1 ms; the cost is I/O, never CPU.

## 12. Open-source solutions

| Option | Verdict |
|---|---|
| **In-house Go consumer** (this design) | **CHOSEN** — 4 V1 requirements; ~2k LOC; full control of dedupe/PII mapping |
| **Novu** (research top pick) | **Rejected** — MongoDB + NestJS + extra infra violates the binding Postgres+Redis/Go stack (ADR-7 class); dashboard/prefs value is rebuilt in TD/ADM anyway |
| Postmark (register, SIGNED) | **CHOSEN** — transactional email, webhooks, ~99.9% deliverability, flat pricing fits V1 volume |
| Resend/Brevo/SES (alternatives) | Rejected: Postmark already chosen for FunderBlu; `mail.Send` interface keeps it swappable |
| Telegram Bot API (V2) | Direct (no middleware) — it's a webhook + HTTP API |
| Twilio/WhatsApp BSP (V2) | V2 decision at volume; `channel` interface is the seam |

## 13. Technology stack

Go worker (in the workers process) + GW routes (TD/ADM surfaces); Postmark
REST + webhooks (EVT-10); Postgres (templates/mappings/notifications/
suppressions); Redis (dedupe SETNX, retry queue state); TD WebSocket for
in-app push (V2); Telegram Bot API (V2); Prometheus (send rate, DLQ depth,
render errors, provider latency); Sentry.

## 14. Integration — internal modules (glue)

| Module | How |
|---|---|
| **EVT** | consumes via the relay's consumer groups (its own lane); `event_ref` on every notification = traceability to the raw event in the PG log |
| **AUTH** | recipient email (profile), role→members resolution for staff targets, step-up for broadcasts |
| **TEN** | tenant branding (V2 NOT-06) from TEN-05/06; per-tenant mapping overrides |
| **LCC/PAY/KYC/CHK/RSK** | producers — they emit domain events; the mapping table decides mail (producers never call NOT directly — event-only, keeps them decoupled) |
| **TD** | in-app center (V2), prefs UI, notification history |
| **ADM** | template/mapping admin, test send, broadcasts, dashboard |
| **ANA** | (V2) delivery KPIs: bounce rate, critical latency, template error rate |
| **CON/OPS** | DLQ depth + provider outage → ops alerting (UptimeKuma-independent, in-band) |

## 15. Integration — external tools

Postmark (email, webhooks, stats API), (V2) Telegram, (V2) SMS/WhatsApp
provider, Prometheus/Grafana, Sentry.

## 16. Implementation blueprint

| Step | Owner | Est | Depends | Exit criteria |
|---|---|---|---|---|
| 1. Schemas (templates, mappings, notifications) + core template set (§3.4, ~25 templates) | BE-2 | 2 d | OPS, EVT | templates render from PG with vars; PII-guard property test green |
| 2. Consumer (mapping → dedupe → render → Postmark) + retry + DLQ lane + ops alert | BE-2 | 3 d | 1, EVT (relay) | seeded events → correct email, exactly once under replay; DLQ row on injected provider failure |
| 3. Staff-role targets + V1 staff templates (payout queue, risk case, KYC manual) | BE-2 | 1.5 d | 2, AUTH | role change (remove member) → no further mail (tested) |
| 4. Postmark webhooks (bounce/complaint) + suppression skeleton + DKIM/SPF checklist | BE-2 | 1 d | 2 | bounced address suppressed after 3; checklist signed off by FunderBlu ops |
| 5. TD/ADM minimum surfaces: trader prefs stub + test send (staff) | FE-01 | 1.5 d | 2 | staff can preview any template before publish |
| 6. V2: channel abstraction, in-app store + WS push, Telegram, prefs, quiet hours, digest, priority, rate limits, delivery logs, dashboard, versioning, consent, SMS/WhatsApp | BE-2 + FE-01/FE-02 | 3 wks | 5 | load test: 500 ev/min → 0 DLQ; quiet hours respected; Telegram delivers |
| 7. V3: outbound webhooks (NOT-38), analytics (NOT-40) | BE-2 | 1 wk | 6 | — |

**Risks:** single email provider (mitigation: `mail.Send` interface + the
in-app channel (V2) is the fallback surface; Postmark's reliability record);
template rot (stale copy after a legal change — mitigation: templates are
versioned + audited + the MIG cutover includes a template review with
FunderBlu's COO); email deliverability (mitigation: DKIM/SPF/DMARC checklist
in Phase 1, bounce monitoring from day 1); herd-breach melt (mitigation:
deliberate consumer rate + digest + load test as an exit criterion, not an
afterthought).

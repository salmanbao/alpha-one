# 18 — SUP: Support Inbox

> Covers PRD module **SUP** (33 requirements). Support is where "the
> platform is a product" becomes true or false: a funded trader whose
> account halted at a broker rollover needs an answer in minutes, not
> ticket-days. V1 ships the **basic loop** (docs/00: SUP 1.0 = basic);
> the full queue feature set is V2 (27 reqs), Telegram/KB/live-chat/AI are
> V3.

## 1. Purpose & scope

**V1 basic (binding minimum):**
- **Ticket creation** from two surfaces: TD ("contact support" with
  pre-filled context — account id, saga id, error code, 16 §3.3) and ADM
  (staff-opened, any object pre-filled).
- **Categories** (fixed V1 set: `account`, `payment`, `payout`, `kyc`,
  `technical`, `other` — the V2 SUP-02 manager makes this tenant-editable).
- **Status machine** (SUP-03, simplified V1): `open → in_progress →
  resolved → closed` (+ `cancelled` by trader).
- **Reply flows**: trader replies (SUP-05), staff replies (SUP-08), internal
  notes (SUP-09) — three message types, one thread.
- **List/detail**: trader sees their tickets (SUP-04); staff inbox (SUP-06
  basic: filter by status/category, no assignment).
- **Notifications** (SUP-16/17 minimum): email on every status change +
  reply (via NOT); in-app = V2.
- **Account-linked tickets** (SUP-12): every ticket carries
  `account_id?`/`identity_id` — the evidence bridge to ADM's dispute
  triage surface (17 §3.4).

**V2 (27):** full SLA engine + breach alerts (SUP-19), priority (SUP-11),
domain-specific ticket types with structured fields (SUP-13/14/15: payout
dispute, **breach appeal**, KYC issue), canned responses (SUP-20),
attachment scanning (SUP-21), search (SUP-22), audit (SUP-23), reporting
(SUP-25), auto-close (SUP-26), templates (SUP-30), agent performance
(SUP-31), satisfaction surveys (SUP-32), in-app notifications (SUP-17 full),
enforcement-dispute workflow (SUP-33).

**V3 (4):** Telegram intake (SUP-24), knowledge base (SUP-27), live chat
widget (SUP-28), AI support bot (SUP-29 — answers only from the KB,
escalates to human; the "AI gives trading advice" pattern is banned by
the compliance posture).

Requirement coverage: V1-basic (unnumbered — the TD/ADM pre-fill contract is what the other docs committed) + `SUP-01..23,25,26,30,31,32,33` (V2.0) + `SUP-24,27,28,29` (V3.0).

## 2. Architecture

```
 TD "contact support" / ADM "open ticket" ──► SUP API (Go domain pkg)
     ──► ticket + first message (context JSONB: object refs, error code,
          saga id, screenshot attachment ref)
     ──► event ticket.created
 staff inbox (ADM — the SUP queue renders inside ADM, not a separate app)
     ──► reply / status change / internal note
 NOT: email on created/replied/status_changed (V1) · in-app (V2)
 attachments: R2 (support/{tenant}/{ticket}/), virus-scan job (V2 SUP-21;
 V1: type/size validation only + a staff-visible "unscanned" flag)
 escalations: V2 — ticket → RSK case (breach appeal) / PAY dispute note
 (the link is the object ref; the domain owns the decision, SUP owns the
 conversation — same separation as RSK §1)
```

SUP is a **Go domain package** (api + a light worker for SLA clocks V2 and
attachment scanning V2), not a separate service — ticket volume is low and
every screen it needs already exists (TD, ADM, NOT).

## 3. System design

### 3.1 Ticket model

```
tickets:
  id · tenant_id · category (registry rows — data, not enum-in-code)
  status (open|in_progress|resolved|closed|cancelled)
  priority (V2: low|normal|high|critical; V1: normal fixed, auto-critical
            if linked object is a payout or breach — the one V1 heuristic)
  trader_identity_id · account_id? · object_refs JSONB
            (e.g. {"saga_id":"…","error_code":"LCC_ACCOUNT_OPENING_STUCK"})
  created_by ('trader' | identity_id | 'staff' | identity_id)
  assignee_id? (V2) · sla_due_at (V2; V1: derived 24 h, shown in ADM)
  first_response_at · resolved_at · closed_at
  satisfaction (V2: 1-5 + comment, post-resolution)
messages:
  id · ticket_id · kind (trader|staff|internal|system) · body ·
  attachment_refs[] · author · created_at
  (system messages = status changes, auto-generated, not editable)
```

**Thread rules:** a trader sees trader+staff messages only (internal notes
are structurally invisible to the TD API — a filter on `kind`, not a
permission check, so there is no role that can accidentally see them);
attachments get a 15-min signed URL on fetch (same pattern as DOC).

### 3.2 Domain-specific ticket types (V2 SUP-13/14/15/33)

Structured fields per category (not free text only):
- **payout dispute:** payout_id required → the ticket embeds the calc
  snapshot read; staff can attach the rejection-reason context; resolution
  writes a **note on the payout** (PAY-22 V2) — SUP never changes payout
  state.
- **breach appeal:** account_id + the breach verdict ref required; routing =
  opens/links a **RSK appeal case** (RSK-41 V2) — the appeal *decision* is
  RSK's; the ticket is the conversation. This is the fairness mechanism for
  EVL verdicts (09 §10) made concrete.
- **KYC issue:** session ref + what's stuck; routes to the KYC manual queue.
- **enforcement dispute (SUP-33):** a trader disputes a specific enforcement
  (halt, block) — links the `account_commands` row (07 LCC-41); response
  SLA 48 h (V2 config).

### 3.3 SLA (V2 SUP-19; V1 minimum)

V1: every ticket gets `sla_due_at = created + 24 h` (first-response target);
ADM shows aging (the same 24/72 h amber/red convention as ADM queues).
V2: per-tenant SLA policy (ADM-33): first-response by category/priority,
resolution target, breach alert to owner + escalation chain (NOT-23).
Satisfaction (SUP-32) fires on `resolved` (email, 1 link, 7-day window).

### 3.4 Canned responses (V2 SUP-20)

Per-tenant, per-category, versioned snippets (the "your account is
evaluating — here's what the status means" family); staff insert with one
click; usage counted (ANA: which canneds resolve without follow-up).
**V1: the 5 top questions are static strings in the TD contact form**
("why is my account still opening?", "how do I reset my MT5 password?",
"when is my payout due?") — the V1 answer to the volume problem.

### 3.5 Attachments (V1 minimum → V2 SUP-21)

V1: ≤ 10 MB (PRD attachment default), types: png/jpg/webp/pdf; R2
tenant-prefixed; staff-visible "unscanned" badge (honest about the V1 gap).
V2: ClamAV scan job in the workers process (scan → `scanned`/`infected`;
infected = quarantined + removed from the thread + alert); scanner runs
out-of-band — the upload is never blocked on it.

### 3.6 Escalation & cross-module contract

- **To RSK:** breach appeal ticket → `risk.case_appealed` (V2) — RSK owns
  the verdict, SUP owns the conversation, NOT owns the notification.
- **To PAY:** payout dispute → PAY note (V2) + the payout queue shows the
  open ticket (the 17 §3.4 evidence pack reads it).
- **To ADM:** any ticket linked to an object appears in that object's
  "Events" tab (the audit mirror includes `ticket.*` events) — the
  support/dev boundary: devs see the conversation, never replace it.

## 4. Events (topic `ticket`)

| Event | When | Consumers |
|---|---|---|
| `ticket.created` | created (surface: trader/staff) | NOT (email ack to trader; staff notify), AUD |
| `ticket.replied` | any message (kind) | NOT (the other side, per kind), ANA |
| `ticket.status_changed` | status transition | NOT, ANA, AUD |
| `ticket.escalated` (V2) | SLA breach / manual | NOT (owner chain), AUD (critical if money-linked) |
| `ticket.satisfaction_submitted` (V2) | survey response | ANA |

Consumes: `account.state_changed` (auto-note on linked tickets: "account
moved to X" — the ticket updates itself when the backend resolves the
underlying issue; a huge V1-quality lever), `payout.status_changed`
(same pattern for payout-linked tickets).

## 5. Lifecycles

- **Ticket:** §3.1 machine; `closed` = 7 days after `resolved` with no
  trader reply (auto-close policy V2 SUP-26; V1: staff closes manually —
  less magic, more honest in week 1).
- **Message:** immutable (no edits — support quality: corrections are new
  messages; "edit" would destroy the evidence record).
- **Canned response (V2):** `active → disabled` (versioned).
- **SLA clock (V2):** `running → (responded) first_response_met → (resolved)
  met|breached`.
- **Attachment:** `uploaded → scanned (V2) → (infected: quarantined)`.

## 6. Error taxonomy

Namespace `SUP`:

| Code | HTTP | Meaning |
|---|---|---|
| `sup.ticket_not_found` | 404 | — (ownership check returns 404, never 403 — 04 posture) |
| `sup.closed` | 409 | Reply on a closed ticket (reopen = staff action) |
| `sup.category_unknown` | 422 | Category not in the registry (V2) |
| `sup.attachment_invalid` | 422 | Type/size violation |
| `sup.duplicate_open` | 200 + hint | (V2) Similar open ticket exists (same trader+category+account, < 7 days) — the create response includes it; trader chooses |
| `sup.rate_limited` | 429 | Trader ticket-create cap (5/day — abuse control, V2 SUP-30 family) |
| `sup.field_required` | 422 | Domain-specific type missing its required object ref (V2) |
| `sup.satisfaction_expired` | 409 | Survey window passed (V2) |

## 7. API endpoints
> **Scope note:** SUP is not in the V1 execution sheet (V2 scope). There is no V1 baseline contract for this module; the surface below is design-level (post-V1, docs/99) and provisional until its phase's contract freeze.


Trader (TD): `GET /v1/support/tickets` (own), `POST /v1/support/tickets`
`{category, subject, body, account_id?, attachment_ids?}`,
`GET /v1/support/tickets/{id}` (thread, own only),
`POST /v1/support/tickets/{id}/messages` (reply),
`DELETE /v1/support/tickets/{id}` (cancel — V1: only while `open`),
`GET /v1/support/attachments/{id}/url` (own, signed),
`POST /v1/support/tickets/{id}/satisfaction` (V2).

Staff (ADM): `GET /v1/admin/support/queue?status=&category=`,
`GET /v1/admin/support/tickets/{id}` (full: internal notes, object context,
linked-object evidence reads),
`POST /v1/admin/support/tickets` (staff-opened),
`POST /v1/admin/support/tickets/{id}/messages` (staff reply / internal note
via `kind`),
`POST /v1/admin/support/tickets/{id}/status` (transition, 2FA for
`resolved` on money-linked tickets — the "we fixed your payout" claim must
be deliberate),
V2: assignment, canneds CRUD, templates, reports, search.

## 8. Schema (key shapes)

```jsonc
// POST /v1/support/tickets (from TD — the pre-filled case)
{ "data": { "id": "01J9TCK...", "status": "open", "category": "account",
    "context": { "account_id": "01J9ACC...", "saga_id": "01J9SAGA...",
                 "error_code": "LCC_ACCOUNT_OPENING_STUCK",
                 "note": "Still 'opening' after 3 hours" } } }

// staff detail (ADM)
{ "data": { ..., "thread": [
    { "kind": "trader", "body": "Still 'opening' after 3 hours", "at": 1758282000000 },
    { "kind": "system", "body": "Account state: opening → evaluating (auto-note)", "at": 1758290000000 },
    { "kind": "internal", "body": "Broker open delayed — BRG shows no account yet; escalating", "at": 1758290100000 } ],
  "linked": { "account_state": "evaluating", "payouts": 0, "kyc": "verified" } } }
```

## 9. Database design

```sql
CREATE TABLE ticket_categories (          -- registry (data; V2 tenant-editable)
  id          ULID PRIMARY KEY,
  tenant_id   ULID,                        -- NULL = platform default
  key         TEXT NOT NULL,               -- 'account'|'payment'|…
  label       TEXT NOT NULL,
  sla_hours   INT NOT NULL DEFAULT 24,     -- V2: per priority
  enabled     BOOLEAN NOT NULL DEFAULT true,
  UNIQUE (tenant_id, key)
);

CREATE TABLE tickets (
  id                ULID PRIMARY KEY,
  tenant_id         ULID NOT NULL,
  category          TEXT NOT NULL,
  status            TEXT NOT NULL DEFAULT 'open'
    CHECK (status IN ('open','in_progress','resolved','closed','cancelled')),
  priority          TEXT NOT NULL DEFAULT 'normal'
    CHECK (priority IN ('low','normal','high','critical')),
  subject           TEXT NOT NULL,
  identity_id       ULID NOT NULL,         -- the trader
  account_id        ULID,
  object_refs       JSONB NOT NULL DEFAULT '{}',
  created_by        TEXT NOT NULL,         -- 'trader' | 'staff'
  assignee_id       ULID,                  -- V2
  first_response_at TIMESTAMPTZ,
  sla_due_at        TIMESTAMPTZ NOT NULL,
  resolved_at       TIMESTAMPTZ, closed_at TIMESTAMPTZ,
  satisfaction      SMALLINT, satisfaction_comment TEXT,   -- V2
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_tick_tenant_status ON tickets(tenant_id, status, created_at DESC);
CREATE INDEX idx_tick_identity ON tickets(tenant_id, identity_id, created_at DESC);
CREATE INDEX idx_tick_account ON tickets(account_id) WHERE account_id IS NOT NULL;

CREATE TABLE ticket_messages (
  id            ULID PRIMARY KEY,
  tenant_id     ULID NOT NULL,
  ticket_id     ULID NOT NULL REFERENCES tickets(id),
  kind          TEXT NOT NULL CHECK (kind IN ('trader','staff','internal','system')),
  body          TEXT NOT NULL,
  attachment_refs JSONB NOT NULL DEFAULT '[]',
  author_id     ULID,                      -- NULL for system
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_tmsg_ticket ON ticket_messages(ticket_id, created_at);

CREATE TABLE ticket_attachments (
  id          ULID PRIMARY KEY,
  tenant_id   ULID NOT NULL,
  r2_key      TEXT NOT NULL,               -- support/{tenant}/{ticket}/{n}
  bytes       BIGINT NOT NULL,
  content_type TEXT NOT NULL,
  scan_state  TEXT NOT NULL DEFAULT 'unscanned'   -- V2: scanned|infected
    CHECK (scan_state IN ('unscanned','scanned','infected')),
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

## 10. Security & compliance

- **Internal notes are structurally invisible to trader APIs** (kind
  filter on the query — a trader endpoint has no code path to `kind=
  internal` rows; a test asserts it).
- **Ownership:** traders see only their own tickets (404 on others', the
  04 posture); staff are tenant-scoped (no cross-tenant ticket reads).
- **Attachments:** type/size validation at upload (V1), ClamAV (V2);
  signed URLs 15 min; R2 tenant-prefixed (same isolation as KYC/DOC).
- **Evidence integrity:** messages immutable (§5); the ticket thread +
  object refs + the auto-notes is the dispute record for breach appeals
  (RSK-41 reads it); retention 7 yr for money-linked tickets, 2 yr others
  (V2 SUP-26 policy config; V1: 7 yr flat — simpler and safer).
- **Resolved-on-money 2FA** (§7): "your payout is resolved" is a claim a
  trader screenshots; making it a deliberate 2FA'd action + critical audit
  is the trust control.
- **V3 AI bot boundary:** answers only from the KB (RAG over approved
  articles), never from the DB, never about specific account outcomes,
  always with a human-escalate path — and it is disclosed as a bot.

## 11. Scalability considerations

- Volume: ~50 tickets/day V1 (FunderBlu base; ~20% of funded traders/month
  opening at least one) — a PG table, not a problem.
- The throughput risk is **response time, not message volume** — the SLA
  design (§3.3) and the auto-note feature (the ticket answers itself when
  the backend resolves the issue) are the load tools; V2 assignment +
  canneds are the rest.
- Attachment storage: 10 MB × ~3/ticket × 50/day ≈ 4.5 GB/month — R2
  trivial; lifecycle with retention.
- Search (V2 SUP-22): PG `tsvector` on subject+body (trigram for fuzzy ids)
  — no Elasticsearch at this scale (the research files' ES recommendation
  is for the analytics stack, not 5k tickets/quarter).
- Auto-notes consume domain events on the SUP lane (EVT consumer group) —
  at-least-once, deduped on (ticket, event_ref).

## 12. Open-source solutions

| Option | Verdict |
|---|---|
| **In-house Go domain pkg** (this design) | **CHOSEN** — 33 reqs, most V2; the integration surface (ADM/TD/NOT/RSK/PAY) is the product; a third-party desk would own the data we need adjacent to money state |
| FreeScout / osTicket / Zammad (self-hosted desks) | Rejected: they add their own DBs + auth + UIs to integrate with — three integrations to replace one domain package; and the breach-appeal→RSK link is custom either way |
| Crisp/Freshdesk (SaaS desks) | Rejected: data residency + the evidence-integrity requirements (immutable threads adjacent to payout disputes) don't fit a SaaS desk |
| ClamAV (V2 SUP-21) | CHOSEN (the standard; runs in the workers process, out-of-band) |
| PG full-text (V2 SUP-22) | CHOSEN (tsvector + pg_trgm) |
| (V3) AI bot: any hosted LLM API over KB only | V3 decision; the boundary rules in §10 are non-negotiable |

## 13. Technology stack

Go domain package (api) + workers (SLA clocks V2, ClamAV V2); Postgres
(tickets/messages/attachments); R2 (attachments); NOT (emails); ADM (queue
UI — no separate app); TD (contact form + ticket list); Prometheus (SLA
aging, volume by category, auto-note resolution rate); Sentry.

## 14. Integration — internal modules (glue)

| Module | How |
|---|---|
| **TD** | contact form with pre-filled context (16 §3.3: every dead-end has the button); ticket list + thread + cancel |
| **ADM** | the inbox renders inside ADM (17 §3.1 — a queue, not an app); object-linked views (ticket on the account detail's Events tab) |
| **NOT** | created/replied/status emails (V1); in-app + survey (V2); escalation chains (NOT-23) |
| **RSK** | breach appeal ↔ risk case (V2 RSK-41): ticket opens/links the appeal; RSK decides; the ticket carries the conversation |
| **PAY** | payout dispute → PAY note (V2 PAY-22); payout queue shows open tickets; `payout.status_changed` auto-notes |
| **LCC/BRG** | `account.state_changed` auto-notes; enforcement-dispute tickets link `account_commands` (07 LCC-41) |
| **KYC** | KYC-issue tickets route to the manual queue (13) |
| **CHK** | payment-issue tickets link the intent/order (12) |
| **ANA** | volume by category, first-response time, resolution rate, satisfaction, auto-note efficacy |
| **AUD** | `ticket.*` events mirrored (critical tier: resolved on money-linked) |

## 15. Integration — external tools

R2 (attachments), ClamAV (V2), Postmark (via NOT), (V3) LLM API for the KB
bot, Prometheus/Grafana, Sentry.

## 16. Implementation blueprint

| Step | Owner | Est | Depends | Exit criteria |
|---|---|---|---|---|
| 1. Schemas (categories, tickets, messages, attachments) + create/reply/status APIs + ownership rules | BE-2 | 2.5 d | OPS, AUTH, EVT | property: trader A cannot read trader B's ticket (404); internal notes invisible to TD API |
| 2. NOT wiring (created/replied/status emails) + TD contact form (pre-filled context) + trader ticket list | BE-2 + FE-01 | 3 d | 1, NOT, TD | create from TD → trader + staff get emails; thread renders |
| 3. ADM inbox (queue, detail, staff reply, internal notes, status with 2FA on money-linked resolve) | FE-1 | 3 d | 2, ADM shell | full loop in staging: open → staff note → reply → resolve → closed |
| 4. Auto-notes (account/payout state events → system messages) + attachment upload (V1 validation) | BE-2 | 2 d | 2, LCC/PAY events | linked ticket gets an auto-note within 2 s of the state change |
| 5. V2: SLA engine + alerts, priority, assignment, domain ticket types (payout/breach-appeal/KYC/enforcement), canneds, attachment scanning, search, auto-close, templates, reports, satisfaction | BE-2 + FE-1 | 3 wks | 4, RSK-41, PAY-22 | breach appeal opens a RSK appeal case; SLA breach alerts owner; ClamAV flags a seeded infected file |
| 6. V3: Telegram intake, KB, live chat, AI bot (KB-only, disclosed) | BE-2 + FE-01 | 4 wks | 5 | bot answers a seeded question from the KB and escalates an account-specific one |

**Risks:** support becoming the de-facto dispute engine without the domain
links (mitigation: the object_refs + auto-notes + the breach-appeal→RSK
contract make SUP a *conversation about* domain state, never a *replacement
for* it); V1 scope whiplash (PRD says 0 V1 reqs, docs/00 commits basic —
mitigation: §1 is the reconciled scope, signed in the Phase-1 review);
response time (mitigation: auto-notes + canneds + FunderBlu's own support
staff own the SLA — the platform's job is to make each ticket answerable
from one screen, 17 §3.4).

# 05 — LED + AUD: Ledger & Accounting, Audit & Compliance

> Covers PRD modules **LED** (26 requirements) and **AUD** (26 requirements). The deep
> review of this module — findings F1–F10 and decisions D25–D27 — is
> [48 — Ledger & Audit: Deep Review](48-ledger-audit-review.md); the chain review and the
> open-source/library evaluation are [49 — chain review + OSS](49-chain-review-ledger-audit-oss.md).
> LED is the **only** place money math happens twice: every payment, fee, payout,
> and refund posts as a balanced double-entry journal. AUD is the tamper-evident
> record of **who did what, when, from where** — for every sensitive action.

## 1. Purpose & scope

**LED** answers: "where is the money, and is every entry provably balanced?"
Design stance (from the payout research, adapted to the PRD stack): **Postgres
double-entry journal** — no TigerBeetle in V1 (separate Rust DB = ops weight;
our volume is ~500 journal entries/day in V1, Postgres does this trivially).
TigerBeetle stays on the register as the V2+ upgrade path if payout volume grows
10×.

**AUD** answers: "prove what happened, to whom, without trusting anyone including
us." Append-only, access-audited, exportable, (V2) hash-chained.

Requirement coverage: LED `01,02,03,04,07,08,18` (V1.0) + `05,06,09,10,11,12,13,14,15,17,20,21,22,23,24,25,26` (V2.0) + `16,19` (V3.0);
AUD `01,03,04,21` (V1.0) + `23` (V1.1) + `02,05..17,20,22,24,25,26` (V2.0) + `18,19` (V3.0).

## 2. Architecture

```
 CHK (order paid)──┐                        ┌──► ADM (financial views)
 PAY (obligation)──┼─► ledger.Post()  ──tx─►│──► ANA (financial read models)
 PAY (settlement)──┤    (balanced,         │──► CON (platform finance)
 LED (adjust,     │     immutable)         │──► BIL (V3: usage + revenue)
      reversal)───┘                        └──► external: QuickBooks/Xero (V2)

 every module ──audit.Write(action, resource, before/after, actor)──► audit_events (append-only)
```

Both domains live in `api` (domain packages) but are **write-only facades**: other
modules call `ledger.Post(ctx, TenantID, entry)` / `audit.Write(...)`; they never
touch the tables. Reads: financial read endpoints are owned by LED (trial balance,
balances) and AUD (query/export).

## 3. System design

### 3.1 Chart of accounts (LED-01)

Two layers: **platform accounts** (Alpha One's own P&L — revenue, broker cost,
payout pass-through) and **tenant accounts** (the firm's books). Tenant accounts
are seeded at provisioning (COA template, overridable per tenant in V2):

| Account | Type | Meaning |
|---|---|---|
| `tenant:challenge_receivable` | A | trader owes challenge fee (created at order, cleared at payment) |
| `tenant:challenge_revenue` | R | recognized when order paid (V2 defers: `tenant:deferred_revenue` — LED-21) |
| `tenant:addon_revenue` | R | add-on sales |
| `tenant:payout_liability` | L | firm owes trader (created at funded profit accrual / payout request) |
| `tenant:payout_paid` | R (contra) | cleared when payout settles |
| `tenant:refund_payable` | L | refunds in flight |
| `tenant:provider_fee_expense` | E | payment-provider fees |
| `tenant:broker_cost_expense` | E | MetaApi per-account cost (imported, V2) |
| `tenant:cash` | A | tenant's money on the platform (their collected fees, pre-payout) |

Seeded by the provisioning saga's **step 6b** (decision D26, docs/48 — added
2026-09-19: the saga previously omitted it, so the first `order.paid` post would
have failed `led.account_not_found`); idempotent, compensated like every step.

Account: `id (ULID) · tenant_id (NULL = platform) · code (unique per tenant) ·
name · type {asset,liability,equity,revenue,expense} · currency · is_system`.

### 3.2 Journal model (LED-02)

```
journal_entry:  id · tenant_id · idempotency_key (unique) · reason_code
                (enum: order_paid, order_refunded, payout_requested, payout_settled,
                       payout_failed, fee_charged, adjustment, reversal, opening_balance,
                       provider_settlement) · ref_type · ref_id (order_id/payout_id/...)
                · description · posted_at · posted_by (identity or system:svc)
                · prev_entry_hash (V2 chain) · batch_id (reconciliation runs)
journal_line:   entry_id · account_id · debit_cents · credit_cents · currency
                · memo — invariant: exactly one of debit/credit > 0;
                SUM(debit) = SUM(credit) per entry (DB constraint, below)
```

**Zero-sum invariant (LED-11) is a database constraint, not a convention.**
The check must run **after the lines exist** — an `AFTER INSERT` trigger on
`journal_entry` fires before any line is written and would pass every entry
(finding F1, docs/48). The enforced form is a **deferred constraint trigger on
`journal_line`**, checked at commit:

```sql
CREATE FUNCTION trg_entry_balance() RETURNS trigger AS $$
DECLARE
  eid ULID := COALESCE(NEW.entry_id, OLD.entry_id);
  unbalanced int; mixed int;
BEGIN
  SELECT COALESCE(SUM(debit_cents),0) - COALESCE(SUM(credit_cents),0),
         COUNT(DISTINCT currency)
    INTO unbalanced, mixed
    FROM journal_line WHERE entry_id = eid;
  IF unbalanced <> 0 OR mixed > 1 THEN
    RAISE EXCEPTION 'journal entry % is unbalanced or mixed-currency', eid;
  END IF;
  RETURN NULL;  -- AFTER trigger
END $$ LANGUAGE plpgsql;
CREATE CONSTRAINT TRIGGER trg_lines_balance AFTER INSERT OR UPDATE OR DELETE ON journal_line
  DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION trg_entry_balance();
-- Row-level + deferred = evaluated per touched entry at COMMIT: lines inserted after
-- the entry row are all present when the check runs; statement-level shortcuts are
-- what broke the earlier sketch (an AFTER INSERT trigger on journal_entry fires
-- before any line exists — finding F1, docs/48).
-- One currency per entry (§3.2 rule 4) rides the same check (F6).
-- The app role also gets INSERT-only (§9): corrections are reversal entries, never edits.
```

**Posting rules:**
1. `Post` is idempotent on `idempotency_key` (same key → same entry, no error).
2. **Postings never fail silently** (LED-25): a failed post raises; the caller's
   business tx rolls back. For the event-driven appliers (V1's CHK/PAY paths) a
   failed post is an ordinary EVT-05 retry → DLQ with alert: "payment captured
   but not posted" lives in the **applier's retry/DLQ semantics and the CON DLQ
   screen (docs/04 §5.6)** — there is deliberately **no extra order state**
   (docs/12's binding order machine is untouched; the `payment_captured_ledger_pending`
   state named here before docs/48 never existed in docs/12).
3. Entries are **immutable** (LED-18): app DB role has `INSERT` only on
   `journal_entry`/`journal_line`; corrections are **reversal entries**
   (LED-24: `POST /v1/ledger/entries/{id}/reverse` with reason + 2FA, V2) that
   reference `reverses_entry_id`.
4. Amounts: integer cents, one currency per entry (multi-currency = V3 LED-19;
   FX at settlement recorded as an explicit `fee_charged` line, never hidden).

### 3.3 Posting flows (V1 set)

| Trigger | Entry (debit → credit) | Req |
|---|---|---|
| Order paid (`order.paid`) | `tenant:challenge_receivable` → `tenant:challenge_revenue` (gross) + provider fee: `tenant:challenge_revenue` → `tenant:provider_fee_expense` (fee) + `tenant:cash` stays (net effect: cash up by net) | LED-04 |
| Payout requested & approved (`payout.approved`) | `tenant:cash` → `tenant:payout_liability` | LED-07 |
| Payout settled (`payout.settled` — the V1 catalog name; renamed from `PayoutPaid` by D60, docs/58) | `tenant:payout_liability` → `tenant:payout_paid` + fee line | LED-08 |
| Payout failed (`payout.failed`, V2 rail failure — the V1 failed-return is posted by the applier from the payout row) | `tenant:payout_liability` → `tenant:cash` (return) | LED-07 (V2 formal) |
| Refund (`payment.refund_requested` → settled reversal, V2) | `tenant:challenge_revenue` → `tenant:refund_payable` → `tenant:cash` | LED-05 |

### 3.4 Derived balances & reports (V2: LED-10/23)

`balances` materialized table refreshed by worker (5 min cadence + on-demand
rebuild): per (tenant, account, currency): `balance_cents, updated_at`. Trial
balance endpoint cross-checks SUM(balance) vs SUM(journal) — mismatch = CRITICAL
alert (integrity monitor, also runs nightly). Reconciliation (LED-13/14): nightly
job imports provider settlement reports (LED-12: CSV import per provider),
matches ledger entries, exceptions → `ledger.reconciliation_exception` event →
ADM finance queue.

## 4. Events

### 4.1 V1 baseline — LED/AUD produce **no domain events**

The V1 appliers are **consumers**: the `ledger-applier` worker consumes
`order.paid`, `payout.approved` and `payout.settled` (the V1 catalog names — D60) and
posts the §3.3 entries inside its own transaction; the `audit-applier` mirrors
catalog events into `audit_events` (tier per the catalog). Emitting no events in
V1 is deliberate — the journal itself is the record, and the audit mirror is
written directly (finding F3, docs/48; the former single table here mixed tiers
and named three events that do not exist in the catalog).

### 4.2 Extended (post-V1) event model — design-level

| Event | Producer | Consumers | Tier |
|---|---|---|---|
| `ledger.entry_posted` | LED | AUD (mirror), ANA, CON (platform finance) | ext |
| `ledger.entry_reversed` | LED | AUD, ANA, NOT (tenant finance) | ext |
| `ledger.reconciliation_exception` | worker | NOT (tenant owner + CON), ADM queue | ext |
| `audit.critical_action` | AUD (tiered) | NOT (owner/CON), RSK (V2 correlation) | ext |
| `audit.export_completed` | AUD | AUD self (meta), CON | ext |

## 5. Lifecycles

- **Journal entry:** `posted (terminal)` or `reversed` (referenced by a new
  entry — original never mutated). No `draft` state in V1.
- **Account:** `active → closed (retained, historical)` — never deleted.
- **Audit event:** `appended → (retention: tenant 7 yr / platform 10 yr per legal
  template, configurable per tenant — V2 AUD-10) → archived (R2, index kept)`.
  V2: `legal_hold` flag pins rows (AUD-22).
- **Export job:** `requested → running → completed (7-day signed link) | failed`.

## 6. Error taxonomy

| Code | HTTP | Meaning |
|---|---|---|
| `led.entry_unbalanced` | 500 (internal) | Constraint should catch this; surfaced as bug alert |
| `led.account_not_found` | 404 | Unknown account code |
| `led.account_closed` | 422 | Posting to closed account |
| `led.idempotency_conflict` | 422 | Same key, different entry payload |
| `led.entry_already_reversed` | 409 | Double reversal |
| `led.reversal_requires_reason` | 422 | — |
| `led.reconciliation_mismatch` | — | Internal (exception event, never a client error) |
| `aud.export_limited` | 429 | Export quota (scope too broad / too frequent) |
| `aud.scope_denied` | 403 | Export/audit query exceeds role scope |
| `aud.write_failed` | — | Internal CRITICAL: audit write failed (fail-closed: the business action is rolled back and alerted) |

**Fail-closed audit (V1 rule):** if `audit.Write` fails on a *sensitive* action,
the action is denied and the user is told "service temporarily unavailable" —
sensitive actions without an audit record are not allowed (PRD: "everything
auditable"). Non-sensitive actions degrade to metric + log.

## 7. API endpoints
### 7.1 V1 baseline — `led` (see `contracts/api/led.md`)

**No HTTP surface in V1** — this is an internal/service contract. The internal contracts (what other modules call, what workers run, what is enforced) are in `contracts/api/led.md`.
### 7.2 V1 baseline — `aud` (authoritative: `contracts/api/aud.md`)

| Method + path | Auth | Permission | Idempotency | V1 errors |
|---|---|---|---|---|
| `GET /v1/admin/audit` | staff with audit read permission — AUD-21 | `audit.read` # AUD-21 | n/a | standard |
| `POST /v1/admin/audit/export` | staff with export permission — AUD-21 | `audit.export` # AUD-21 | required | standard |

Scope, request/response shapes, and per-endpoint notes: `contracts/api/aud.md` (field values in the research are owner TODOs until contract freeze; canonical JSON is fixed at freeze, per the docs/99 §12 rules).

### 7.3 Extended (post-V1) surface — provisional

> Not in the V1 execution sheet. Design-level; paths beyond the V1 baseline are provisional until the URL-plan decision (`contracts/api/gw.md`, open question). Shown for platform completeness (V2/V3 phases, docs/99).

Tenant-side (finance/compliance roles):
`GET /v1/ledger/accounts`, `GET /v1/ledger/balances` (V2),
`GET /v1/ledger/entries?account=&from=&to=` (V2), `POST /v1/ledger/entries/{id}/reverse` (V2),
`GET /v1/ledger/trial-balance?as_of=` (V2), `POST /v1/ledger/reconciliation/run` (V2).

Tenant-side audit: `GET /v1/audit/events?actor=&resource=&from=&to=` (AUD-21;
compliance role), `POST /v1/audit/exports` (scope: tenant, time-range, filters →
job), `GET /v1/audit/exports/{id}` (status + signed download link).

Console (platform realm): `GET /v1/console/ledger/platform` (platform CoA +
cross-tenant aggregates — anonymized per ANA rules),
`GET /v1/console/audit?tenant=`, `POST /v1/console/audit/legal-hold` (V2).

Internal (service-to-service, not public): `POST /internal/v1/ledger/post`,
`POST /internal/v1/audit/write` — these are what the Go domain packages call;
they also exist as HTTP for the workers service.
## 8. Schema (key shapes)

```jsonc
// POST /internal/v1/ledger/post
{ "data": { "idempotency_key": "pay:01J9PAID...", "reason_code": "order_paid",
    "ref_type": "order", "ref_id": "01J9ORD...", "description": "Order #FB-1042 paid",
    "lines": [
      { "account_code": "challenge_receivable", "debit_cents": 50000, "credit_cents": 0 },
      { "account_code": "challenge_revenue",    "debit_cents": 0,   "credit_cents": 50000 }
    ] } }
// → 201 { "data": { "entry_id": "01J9JE...", "posted_at": 1758278400123 } }

// POST /v1/audit/exports → 202
{ "data": { "export_id": "01J9EXP...", "status": "running",
    "scope": { "tenant_id": "01J9...", "from": 1755686400000, "to": 1758278400000,
               "actions": ["payout.*","kyc.*"] },
    "eta_seconds": 45 } }
// GET /v1/audit/exports/{id} → 200 { "data": { "status": "completed",
//   "download_url": "https://r2.../signed", "expires_at": 1758364800000, "rows": 18220 } }
```

## 9. Database design

```sql
CREATE TABLE accounts (
  id         ULID PRIMARY KEY,
  tenant_id  ULID REFERENCES tenants(id),      -- NULL = platform-level
  code       TEXT NOT NULL,
  name       TEXT NOT NULL,
  type       TEXT NOT NULL CHECK (type IN ('asset','liability','equity','revenue','expense')),
  currency   CHAR(3) NOT NULL DEFAULT 'USD',
  is_system  BOOLEAN NOT NULL DEFAULT true,
  closed_at  TIMESTAMPTZ,
  UNIQUE (COALESCE(tenant_id,'00000000-0000-0000-0000-000000000000'::ulid_placeholder), code)
);  -- in practice: UNIQUE (tenant_id, code) with a platform sentinel row

CREATE TABLE journal_entry (
  id               ULID PRIMARY KEY,
  tenant_id        ULID NOT NULL,
  idempotency_key  TEXT NOT NULL UNIQUE,
  reason_code      TEXT NOT NULL,
  ref_type         TEXT, ref_id TEXT,
  description      TEXT,
  reverses_entry_id ULID REFERENCES journal_entry(id),
  prev_entry_hash  TEXT,                        -- V2 hash chain
  posted_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  posted_by        ULID                         -- identity or system sentinel
);
CREATE INDEX idx_jentry_tenant_time ON journal_entry(tenant_id, posted_at DESC);
CREATE INDEX idx_jentry_ref ON journal_entry(ref_type, ref_id);

CREATE TABLE journal_line (
  id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  entry_id     ULID NOT NULL REFERENCES journal_entry(id) ON DELETE RESTRICT,
  account_id   ULID NOT NULL REFERENCES accounts(id),
  debit_cents  BIGINT NOT NULL DEFAULT 0 CHECK (debit_cents >= 0),
  credit_cents BIGINT NOT NULL DEFAULT 0 CHECK (credit_cents >= 0),
  currency     CHAR(3) NOT NULL DEFAULT 'USD',
  memo         TEXT,
  CHECK (debit_cents = 0 OR credit_cents = 0)   -- one side only
);
CREATE INDEX idx_jline_account_time ON journal_line(account_id, entry_id);
-- + balance-check trigger (§3.2). App role: INSERT only on both tables.

CREATE TABLE audit_events (
  id            BIGINT GENERATED ALWAYS AS IDENTITY,
  tenant_id     ULID,                             -- NULL = platform-level
  actor_id      ULID,
  actor_kind    TEXT NOT NULL CHECK (actor_kind IN ('user','service','api_key','system')),
  actor_role    TEXT,
  action        TEXT NOT NULL,                    -- 'payout.approved' style
  resource_type TEXT, resource_id TEXT,
  status        TEXT NOT NULL CHECK (status IN ('success','failure','denied')),
  before        JSONB, after JSONB,               -- redacted at write (AUD-23 rules)
  ip            INET, user_agent TEXT,
  correlation_id ULID,
  request_id    TEXT,
  geo           JSONB,
  tier          TEXT NOT NULL DEFAULT 'standard' CHECK (tier IN ('standard','sensitive','critical')),
  prev_hash     TEXT, entry_hash TEXT,            -- V2 hash chain; `seq BIGINT`
                                                  -- (per-tenant monotonic) joins at chain
                                                  -- init (AUD-14), backfilled in id order —
                                                  -- decision D27, docs/48: V1 carries no seq,
                                                  -- so the fail-closed audit write is one
                                                  -- INSERT with no Redis dependency
  legal_hold    BOOLEAN NOT NULL DEFAULT false,   -- V2
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (id, created_at)                    -- partitioned tables must carry the
                                                  -- partition key in every unique/PK
                                                  -- constraint (finding F2, docs/48)
) PARTITION BY RANGE (created_at);
CREATE INDEX idx_audit_tenant_time ON audit_events(tenant_id, created_at DESC);
CREATE INDEX idx_audit_actor ON audit_events(tenant_id, actor_id, created_at DESC);
CREATE INDEX idx_audit_action ON audit_events(tenant_id, action, created_at DESC);
CREATE INDEX idx_audit_resource ON audit_events(resource_type, resource_id, created_at DESC);
-- Immutability (docs/32 convention, 28 §3.3): BEFORE DELETE/UPDATE triggers raise,
-- and the app role holds INSERT + SELECT only — the DDL the convention cites:
CREATE FUNCTION trg_ledger_no_mutation() RETURNS trigger AS $$
BEGIN RAISE EXCEPTION '% on % is not permitted', TG_OP, TG_TABLE_NAME; END
$$ LANGUAGE plpgsql;
CREATE TRIGGER no_mutate_journal  BEFORE UPDATE OR DELETE ON journal_entry  FOR EACH STATEMENT EXECUTE FUNCTION trg_ledger_no_mutation();
CREATE TRIGGER no_mutate_jline    BEFORE UPDATE OR DELETE ON journal_line    FOR EACH STATEMENT EXECUTE FUNCTION trg_ledger_no_mutation();
CREATE TRIGGER no_mutate_audit    BEFORE UPDATE OR DELETE ON audit_events    FOR EACH STATEMENT EXECUTE FUNCTION trg_ledger_no_mutation();

-- RLS (D16 model): journal_entry, journal_line and the tenant rows of audit_events
-- are tenant-owned — ENABLE/FORCE ROW LEVEL SECURITY on app.tenant_id (fail-closed),
-- written by the appliers with per-message context (decision W). Rows with
-- tenant_id IS NULL (platform CoA accounts, platform audit rows) are guard-only and
-- reachable through the app_platform services (audit-applier, CON read models) —
-- the same named-exemption model as every other module (docs/44 §5, docs/47 §7).
```

**Redaction at write (AUD-23):** `before`/`after` pass through a field filter:
passwords, tokens, TOTP, full card data, KYC document content never stored —
pointers/hashes only. This is the "sensitive data access audit" surface: any
endpoint that *displays* a redacted field also writes an `audit.sensitive_read`
event (AUD-23: staff viewing a trader's KYC documents or payout wallet).

## 10. Security & compliance

- **Integrity:** V1 = append-only (DB privileges) + nightly hash snapshot (all
  rows → R2, checksummed). V2 = true hash chain (`entry_hash =
  sha256(prev_entry_hash || canonical(row))`, per-tenant chain, AUD-14) +
  verification job (AUD-24) + breach-evidence export (AUD-25). The chain design
  follows the distilled rules in [49 — LED/AUD open-source evaluation](49-chain-review-ledger-audit-oss.md)
  §6: **per-tenant stream** (not one global chain), a transaction-scoped
  **advisory lock per stream** so concurrent appends cannot fork the chain, a
  **versioned canonical string** covering every immutable field (content itself
  enters only as a `content_hash`, so PII redaction/erasure nulls fields without
  breaking verification — erasure by redact-in-place, never rewrite), and an
  external anchor (RFC 3161 timestamp or a transparency log) for the
  nightly chain head.
- **Access:** tenant audit readable by the `audit.read` holders per
  `roles.yaml` — `firm:owner`, `firm:admin`, `firm:compliance` (D14; the
  "compliance/owner only" wording here predates the ratified bindings)
  (V1: AUD-21 export is the primary surface; ADM viewer is V2 AUD-06). Platform
  staff access to tenant audit = the **console realm's `platform:super_admin`**
  (decision D25, docs/48 — the `platform:compliance` role named here before the
  eighth pass does not exist in the ratified catalog; docs/21 CON-01 is
  authoritative) + **always** audited as `security.platform_access` (critical
  tier). Traders **never** see
  the audit trail (PRD default: "traders don't view own audit").
- **PCI SAQ-A support (AUD-26):** the audit trail records which endpoints
  touched payment data (they never store it) — evidence export per tenant per
  period.
- **SOC 2 evidence (AUD-17, V2):** Comp AI/Openlane collection: audit export
  endpoints are the evidence source; critical-action alerts feed the
  "response to incidents" control.
- **GDPR interplay:** data-subject export (AUD-12) = identity-scoped audit
  bundle + domain data (orchestrated with AUTH §10.4); erasure anonymizes
  `actor_id` in *tenant* audit rows only where retention allows, never platform
  rows.
- **SIEM (AUD-15, V2):** nightly bulk export to tenant's SIEM endpoint
  (signed) or CSV via export jobs.

## 11. Scalability considerations

- Volume: ~500 journal entries/day, ~20k audit rows/day (V1) → partitioning is
  belt-and-braces, not necessity. V2 targets: 5k entries/day, 200k audit/day —
  still trivial for partitioned PG; balances table keeps ADM reads O(1).
- Audit writes are on the hot path of sensitive actions: single INSERT, indexed,
  same tx as the action → < 2 ms p99.
- Export jobs are the heavy path: cursor scan + stream to R2 (never buffer in
  RAM); concurrency cap 2 exports/platform; 7-day link expiry.
- Balance rebuild: O(entries) per account; run off-peak + on demand; drift
  monitor (trial balance check) nightly + after every rebuild.

## 12. Open-source solutions

| Option | Verdict |
|---|---|
| **Postgres journal** (our design) | **CHOSEN V1** — PRD: Postgres is system of record; at ~500 entries/day every purpose-built alternative is ops weight (full scoring: [49](49-chain-review-ledger-audit-oss.md) §4) |
| TigerBeetle | V2+ upgrade path if payout throughput 10× (register: consideration); open-source engine, engine-level double-entry, self-hosted — the same posture we already run |
| **Formance Ledger** (MIT core + Numscript) | **Consider-later (the same 10× review point as TigerBeetle)** — self-hostable programmable ledger, one instance hosts many isolated ledgers; rejected for V1 as a second storage+API stack for trivial volume; its posting-template (Numscript) model is the reference for our `reason_code` posting flows |
| Midaz (Lerian) | Watch — Go, multi-asset double-entry, but **source-available (not OSI)**; fails the docs/34 license posture today |
| Fragment / Modern Treasury / Moov | Rejected — managed-cloud only (self-host posture, ADR-9); QLDB-class managed ledgers are the cautionary precedent (vendor-controlled roadmap) |
| Apache Iceberg / DWH for financials | Not needed; PG partitions + R2 archive suffice to V3 |
| **go-money / shopspring/decimal** (Go libs) | **ADOPTED (V1, edges only)** — `go-money` for cent arithmetic + currency formatting in reports/exports, `shopspring/decimal` where provider payloads/CSVs arrive as decimals; the DB rule is unchanged (integer `_cents`, docs/32) — libraries never store floats |
| QuickBooks/Xero connector (register "consider-later") | V2 LED-20 — REST connector, one-way export of journal summaries |
| Documenso | Not LED-related (DOC-12) |

## 13. Technology stack

Go domain packages (`ledger`, `audit`) in `api`; money math at the edges: `go-money` (cent arithmetic, currency formatting) + `shopspring/decimal` (provider payload parsing) — never floats (docs/32); workers: reconciliation,
balance refresh, hash-snapshot, export runner; Postgres (partitions, triggers,
privileges); R2 (exports, archives, hash snapshots); Postmark (export-ready
emails via NOT); Sentry (integrity alerts); Comp AI/Openlane (V2 evidence).

## 14. Integration — internal modules (glue)

| Module | How |
|---|---|
| **CHK** | consumes `checkout.order_paid/refunded` → posts LED-04/LED-05 entries (worker `ledger-applier`) |
| **PAY** | `payout.approved` → LED-07 and `payout.settled` → LED-08 (the V1 applier consumes the catalog names — D60); **V1 eligibility does not read the ledger** — it computes `available = gross − settled_paid` from payout history (docs/11 §3); the V2 `balances` table (LED-10) becomes the fast path then |
| **AUD consumers** | every domain event in the catalog mirrors to `audit_events` (the **audit-applier**): **actor** from the payload's `*_by` field (`approved_by`/`executed_by`), else the producing service as `actor_kind='system'`, `actor=<producer>` (ninth pass, docs/49 C1 — the envelope's `correlation_id` fills `audit_events.correlation_id`); **tier by rule** (ninth pass, docs/49 C2 — "decided by the catalog" was never a mapping): `critical` = suspensions/terminations/reversals/audit-tamper classes, `sensitive` = every money-adjacent event (`payout.*`, `order.*`, `payment.*`) and KYC events, `standard` = the rest — this is the AUD-02 "mandatory coverage" mechanism (V2 formalizes the lint). **Exception (tenth pass, docs/50 D28):** observed high-frequency events — `bridge.tick` — do NOT mirror (their append-only `events` row *is* the record, EVL-49); evaluated/decision events mirror as usual (`evaluation.verdict` breach rows are critical — termination-class; `evaluation.daily_reset`, `account.day_rolled`, `account.activated` are standard) |
| **GW** | sensitive-route audit flag triggers direct `audit.Write` (sensitive reads that aren't events) |
| **CON** | platform finance views, legal holds (V2), integrity dashboards |
| **ANA** | financial read models join `journal_entry` (never mutate) |
| **BIL (V3)** | platform revenue = platform-level CoA; tenant billing uses `usage_events` + journal |
| **MIG** | cutover imports FunderBlu opening balances as `opening_balance` entries (LED-26) — the single source for "we started with X" |

## 15. Integration — external tools

QuickBooks/Xero (V2 export), R2, Postmark (via NOT), Comp AI/Openlane (SOC 2
evidence, consider-later), tenant SIEM endpoints (V2, AUD-15).

## 16. Implementation blueprint

| Step | Owner | Est | Depends | Exit criteria |
|---|---|---|---|---|
| 1. CoA + journal tables + balance trigger + privilege setup (INSERT-only app role) | BE-2 | 2 d | OPS, TEN (seed) | unbalanced insert fails at DB; UPDATE denied to app role |
| 2. `ledger.Post` + idempotency + internal HTTP endpoint + entry_posted event | BE-2 | 2 d | 1, EVT | contract test: same key → one entry |
| 3. CHK applier (order paid → entries incl. fee split) | BE-2 | 2 d | 2, CHK-08 | staging purchase → balanced entries visible |
| 4. PAY applier (obligation/settlement/failed-return) | BE-2 | 2 d | 2, PAY flow | payout lifecycle posts all three entry types |
| 5. Audit schema + partitioning + `audit.Write` + redaction filter + fail-closed wiring | BE-1 | 3 d | EVT, AUTH (actor) | sensitive action with audit outage is denied + alerted |
| 6. AUD-21 query + AUD-23 sensitive-read audit on KYC/payout viewers | BE-1 | 2 d | 5 | viewer shows rows; each sensitive read appears in audit |
| 7. Export jobs (tenant + console), R2 signed links, quotas, meta-audit | BE-2 | 3 d | 5, R2 | 100k-row export < 2 min, link 7-day, export itself audited |
| 8. Integrity: nightly hash snapshot + drift monitor + CON dashboard | BE-1 | 2 d | 1, 5 | injected row change (test) detected next night |
| 9. V2: balances materialization + trial balance + reversal workflow + reconciliation (provider imports) | BE-2 | 8 d | 3, 4 | nightly recon on staging with fake provider CSVs; exceptions land in ADM |
| 10. V2: hash chain + verification + legal hold + SIEM export + SOC 2 evidence pack | BE-1 | 8 d | 5, 8 | chain verify passes; hold pins rows through retention job |
| 11. V3: multi-currency + affiliate postings | BE-2 | 5 d | 9 | — |

**Risks:** ledger bugs are financial bugs (mitigation: property test on
balance-invariant + nightly drift monitor + cutover dry-run on FunderBlu's real
history via MIG); audit bloat (mitigation: partitioning + tier-based retention);
reversal misuse (mitigation: 2FA + reason + audit critical tier + CON visibility).

# 25 — MIG: Migration Tooling

> Covers PRD module **MIG** (8 requirements). The anchor-tenant reality
> that makes or breaks the launch: **FunderBlu migrates off TradeTech
> Solutions (TTS) onto Alpha One** — existing traders, existing funded
> accounts on TTS's MT5 broker, existing payout history, existing
> relationships. The PRD phases the generic importers at V2 (MIG-01/02
> TTS + YourPropFirm, MIG-04 verification, MIG-06 concierge, MIG-07
> dry-run) and PropAccount at V3 — but docs/00/01 commit the **FunderBlu
> cutover to Phase 2 (V1.0 era)**: the MIG-01 TTS importer exists and
> works for one tenant before the others get the product. This doc is
> that plan.

## 1. Purpose & scope

**What moves (the FunderBlu scope):**

| Data class | From (TTS export) | To (Alpha One) | Risk |
|---|---|---|---|
| **Traders** | identities, emails, KYC status, country | `identities` + `tenant_memberships` + KYC records (re-verified — §3.3) | PII handling, legal |
| **Accounts** | challenge/funded accounts, terms, states, progress (drawdown, target, time left) | `accounts` + `funded_terms` (the LCC-20 snapshot) + the **live MT5 accounts** (08: MetaApi **adopts** the existing TTS MT5 accounts — no new broker accounts for funded traders) | **The money-adjacent data — the highest-risk class** |
| **Trading history** | deals/positions for active accounts | BRG sync baseline (08 §3.2: the bridge.sync history backfill, the deal-ticket gap detection applies — evidence-unavailable, never assumed) | broker API limits, backfill window |
| **Payout history** | settled payouts (amounts, dates, methods) | `payout_requests` (imported as `settled`, the PAY-12 records marked `imported`) — so PAY §3.2's `paid_out` math is correct from day 1 | the "how much have we already paid" number must reconcile to TTS's books |
| **Challenge purchase history** | orders (what they paid for) | `orders` (imported, state `fulfilled`/`failed` per TTS) + the LED challenge-revenue entries (the tenant's books start true) | the revenue baseline for ANA/BIL |
| **Documents** | certificates/agreements (if exported) | R2 (DOC objects, marked `imported`) | format variance |
| **KYC documents** | **not migrated** (§3.3) | re-collected or accepted per FunderBlu legal | the one intentional gap |

**Not migrated (explicit):** TTS's internal tickets/notes (SUM: FunderBlu
re-triages open issues manually — the concierge, MIG-06, owns that
process), TTS's marketing data (CRM starts fresh), TTS's affiliate data
(V3 module, doesn't exist yet), anything PII beyond the §1 table without
FunderBlu legal's sign-off.

**Requirement coverage: `MIG-01,02,04,05,06,07,08` (V2.0; MIG-01/04/07 are the FunderBlu cutover scope, built first per docs/99) + `MIG-03` (V3.0: PropAccount).

## 2. Architecture

```
 FunderBlu provides (the export package — TTS's data export, coordinated
   by the concierge (MIG-06) with TTS's team):
   · CSV/JSON exports (traders, accounts, terms, history, payouts,
     orders) + the MT5 broker account list (account # + the MetaApi
     credential handoff)
   · the cut date (T_date) + the freeze window (the last TTS purchases
     close N days before; TTS challenges in-flight at T_date are
     finished on TTS or converted per the policy in §3.2)

 MIG pipeline (workers, per tenant — a migration is a bounded job):
   0. DRY RUN (MIG-07): the full import against a **staging tenant**
      (the synthetic-data rule is satisfied: staging gets the *real
      FunderBlu data only with the legal + CON sign-off* — 06 §2's
      "any prod-like dataset in staging = legal + CON sign-off +
      anonymization option"; the FunderBlu dry run runs on **anonymized
      data** (emails/identities hashed, names dummy-mapped, amounts
      preserved — the reconciliation math needs real amounts, not real
      people) — the dry run proves the pipeline, the real run proves
      the data)
   1. VALIDATE: schema checks, row counts vs the TTS manifest (the
      manifest: TTS's own counts per table — "TTS says 1,204 traders;
      we got 1,204" per class), the FK graph (every account's trader
      exists; every payout's account exists), amount integrity (integer
      cents, no negatives in the wrong fields), the KYC status mapping
      (TTS states → our states, the mapping table is reviewed)
   2. IMPORT (one transaction per data class, ordered by dependency:
      identities → traders → KYC status → accounts + terms → history
      baseline → orders → payouts → documents): each class lands as
      `state: imported` with the source row hash (the per-row sha256 —
      the reconciliation key, §3.4)
   3. RECONCILE (MIG-04): the reconciliation report — per class:
      counts, sum(amount) vs TTS manifest, per-row hash match rate,
      the exceptions list (the rows that didn't match — each with a
      reason code). **The cutover gate: the report must be 100%
      matched or every exception individually dispositioned by
      FunderBlu's COO + our ops (2FA'd, the CON-32 pattern) — no
      "close enough" cutover on money data**
   4. CUTOVER (the T_date window, the 10-second deploy class from 06 §3):
      · DNS/branding flip (the tenant domain → Alpha One, the TEN
        custom-domain config, 03)
      · traders log in to Alpha One (ZITADEL user import — **corrected
        2026-09-19, review G9**: ZITADEL *can* import existing password
        hashes through the admin `ImportHumanUser`/bulk-import endpoints
        (`hashedPassword`), provided the source algorithm is enabled in
        `ZITADEL_SYSTEMDEFAULTS_PASSWORDHASHER_VERIFIERS` (bcrypt on by
        default; argon2, scrypt, pbkdf2, md5-family, phpass, drupal7
        available) — the hash is transparently re-hashed to bcrypt on the
        next successful login. So the cutover has two postures and the
        COO picks one at the cutover gate:
        **A. import-and-keep** — traders keep their passwords (allowed
        only if TTS's KDF is on that list and TTS supplies per-user
        hashes in a verified export); **B. reset-required** (the
        recommendation, and the default) — import identity attributes
        only and set `passwordChangeRequired`, so every trader sets a
        fresh password through ZITADEL's reset flow at first login.
        TOTP seeds and passkey keys can be imported with the same
        endpoint where TTS exposes them; anything not importable
        becomes an enrolment prompt at first login (the SSO of
        convenience)
      · MT5: the MetaApi credential handoff completes (the trader's
        broker session now flows through our bridge — the account
        keeps trading; **no broker-side downtime** — the MT5 account
        was never ours to move, the *integration* moves)
      · TTS read-only for the tenant (their side) — the cutover is
        "stop using TTS", not "TTS stops"
   5. PARALLEL-RUN (the first 2 weeks post-cutover — the docs/01
      commitment): every Alpha One metric is compared against TTS's
      live numbers (equity, PnL, payout totals): the daily
      reconciliation (the PAY/CHK recon pattern, §3.4 extended) runs
      on both sides; any drift > 1¢ = a P1 incident (the 06 incident
      posture) with the reconciliation report as the evidence
   6. CLOSE: the parallel-run report signed (COO + ops), the migration
      records archived (the source exports + reports, R2, 7-yr
      retention — the audit chain for "we moved correctly")
```

## 3. System design

### 3.1 The importer contracts (one per data class)

Each importer = `{source schema (the TTS CSV/JSON shape), target
mapping (the column → column + transformation table), validation rules,
idempotency key (source row hash), state}`. The transformation table is
**data, reviewed, versioned** (like the KYC state mapping) — a
transformation is never code-logic-in-a-loop; the review surface is a
spreadsheet-shaped table the FunderBlu COO can read ("TTS 'Challenge 1
Active' → our 'evaluating' phase 1 — is that right?").

**The per-row source hash** (sha256 of the normalized source row) is
stored on every imported row (`import_meta: {source_hash, source_row,
imported_at, migration_id}`) — it's the key that makes §3.4's
reconciliation row-level, not just aggregate.

### 3.2 The in-flight-challenge policy (the FunderBlu decision)

Challenges (evaluating accounts) active at T_date, policy per FunderBlu
COO sign-off (the Phase-1 checklist item — this is *their* business
decision, the platform provides the machinery):

- **Default (recommended):** in-flight challenges **finish on TTS**
  (TTS keeps running them to completion; passers get funded on TTS or
  their funding is re-created on Alpha One at the funding step — the
  account class carries a `migrated_from: tts` marker + the TTS ref).
  Rationale: mid-challenge state (day counters, HWM, time-left) is the
  hardest data to move correctly, and the trader is mid-psychological-
  arc — a cutover mid-challenge is the highest-complaint scenario.
- **Alternative (if TTS winds down):** full conversion — the state
  mapping carries the counters (the LCC-20 snapshot + the EVL
  evaluation_state import, 09 §9: HWM, daily reset points, days
  elapsed) — supported by the importer (the `evaluation_state` class
  exists in the MIG-01 schema) but it's the riskier path; the dry run
  must exercise it end-to-end if chosen.

**Funded accounts: always converted** (they're the revenue; their MT5
accounts are adopted by MetaApi per 08 — the bridge backfills the
history; the terms snapshot is imported verbatim (the LCC-20 rule:
what they agreed stays what they agreed, including TTS-era terms —
the terms migration is **verbatim + reviewed**, not re-mapped to new
FunderBlu packages — a trader who bought TTS's "$100k 80/20" keeps
exactly that on Alpha One; FunderBlu's *new* packages apply to new
purchases only).

### 3.3 KYC (the one intentional gap)

TTS's KYC documents are **not migrated** (the document images + the
provider verdicts don't transfer between verification providers —
Veriff's verdicts are Veriff's). Policy (FunderBlu legal + our
compliance, Phase-1 item):

- **Traders with TTS-verified KYC who request a payout on Alpha One:**
  re-verification (the L2 flow, 13) — the payout gate holds until
  verified (the KYC-08 gate does this automatically: imported traders
  start at `kyc.l1 = pending_reverify`, not `verified`).
- **The name/DOB data** (not the documents) migrates (the KYC-09
  record, marked `source: tts_import, reverify_required: true`) — the
  trader re-confirms identity against the record at re-verification
  (friction: one re-verification; honesty: we don't claim Veriff
  verified someone TTS verified).
- **Funded traders with no payout request** are not blocked from
  trading (the L1 gate for activation is satisfied by the import —
  the activation is a *migration* action, not a new purchase — the
  KYC gate config for migrated traders: `l1: satisfied_by_import`).

### 3.4 Reconciliation (MIG-04 — the cutover gate, then the 2-week
parallel run)

**Per-class reconciliation (at import):** counts, Σ amounts, per-row
hash match, exceptions list (row-level, each with reason: `mapping_
missing`, `amount_mismatch`, `fk_orphan`, `duplicate`, `state_
unmapped`). The report is a DOC PDF (the FunderBlu COO signs it — the
signature is the cutover gate's legal artifact).

**Parallel run (post-cutover, daily × 14):** for each funded account:
Alpha One equity (EVL observed) vs TTS-reported equity (FunderBlu
pulls TTS's daily statement during the overlap); payout totals (both
sides' books); purchase totals (TTS's last-week orders vs our imported
baseline). Drift > 1¢ per account-day = P1 (the 06 incident class) —
the evidence is the reconciliation row; the fix path is the MIG
correction flow (§3.5).

### 3.5 Corrections (the post-import fix flow)

A post-cutover data error (a term imported wrong, a payout amount off)
is never a silent edit: **the correction flow** = a MIG correction
object `{migration_id, class, row_ref (source_hash), old, new, reason,
approved_by (2FA, COO+ops), linked: {LCC/PAY/LED ref}}` → applies the
domain's own correction pattern (the LED-04 reversal, the LCC state
re-assertion, the PAY adjustment with the calc-snapshot version) → the
correction is on the audit trail with the original import row (the
`import_meta` never changes — the correction references it).

### 3.6 The concierge (MIG-06 — the process, productized in V2)

The migration is 50% data and 50% **people**: TTS's team (the export
coordination, the MT5 credential handoff schedule), FunderBlu's COO
(the policies: §3.2 in-flight, §3.3 KYC, the cutover date, the comms
plan), FunderBlu's traders (the "what changes for you" notice — the
emails they get: the timeline, the login change, the forced password
reset, "your MT5 account is the same number, your broker is the same,
your terms are unchanged" — the truth, in plain words, sent by
FunderBlu's own domain). The concierge = the project plan + the
checklist + the comms templates + the go/no-go call at T_date-7,
T_date-1, and T_date. For FunderBlu it's a **service** (we do it with
them, Phase 2); for future tenants it's a product (V2 MIG-06: the
guided flow with the checklist in the console).

### 3.7 Dry-run mode (MIG-07)

The full pipeline (validate → import → reconcile) against a **staging
tenant with anonymized data** (§2 step 0): the anonymization is a
pipeline stage (the PII stage: identities → synthetic ids with a
mapping table kept **out of staging** (the mapping lives with the
production cutover, encrypted, access-restricted — staging proves the
math, production carries the identities)); amounts/dates/states are
real (the reconciliation must test real magnitudes); the dry run's
exit = the reconciliation report at 100% or dispositioned exceptions +
the parallel-run comparator running against a **simulated TTS feed**
(the TTS export replayed as the "other side" — the comparator's logic
is tested even though the data is synthetic).

## 4. Events (topic `migration`)

| Event | When | Consumers |
|---|---|---|
| `migration.started` | import begins (class) | CON (ops), AUD (critical) |
| `migration.class_completed` | a data class lands (counts, exceptions) | CON, AUD |
| `migration.reconciled` | the report (match rate, exceptions) | CON (the cutover gate reads it), AUD (critical) |
| `migration.exception_dispositioned` | an exception is dispositioned (2FA'd) | AUD (critical) |
| `migration.cutover_complete` | T_date flip done | CON, AUD (critical — the platform's biggest audit event of the year) |
| `migration.parallel_drift` | the daily comparator exceeds 1¢ | CON (P1), NOT (ops), AUD (critical) |
| `migration.closed` | parallel run signed | CON, AUD |

Consumes: nothing (MIG is a producer; the domains it writes to emit
their own events as normal — the imported rows trigger `account.*`
events at cutover, which is the ANA read models' first real data).

## 5. Lifecycles

- **Migration (per tenant):** `planned → exports_received → validated →
  dry_run_passed → import_ready → importing → reconciled →
  (exceptions dispositioned) → cutover_pending → cut_over →
  parallel_running → closed | aborted (pre-cutover: everything rolled
  back — the import is transactional per class, the abort = the
  classes' transactions roll back + the staging tenant is deleted)`.
- **Data class:** `pending → validating → imported (state: imported) |
  failed (the whole class rolls back — no partial classes)`.
- **Exception:** `open → dispositioned {reason, by, action} |
  (feeds the import retry)`.
- **Parallel-run day:** `computed → matched | drift (P1 until resolved)`.
- **Correction:** `requested → approved (2FA) → applied → verified
  (the domain's own check) → closed`.
- **Retention:** the export package + all reports + dispositions: R2,
  7 yr (the financial-adjacent class — "we migrated correctly" is a
  7-year claim).

## 6. Error taxonomy

Namespace `MIG`:

| Code | HTTP | Meaning |
|---|---|---|
| `mig.export_schema_invalid` | 422 | The TTS export doesn't match the expected schema (the class is rejected before any row lands — fail at the door, not mid-import) |
| `mig.manifest_mismatch` | 409 | Row counts vs the TTS manifest differ (the import halts; the diff is the first artifact) |
| `mig.mapping_missing` | 409 | A source value has no mapping (state/term) — the row is an exception, the import continues, the halt-at-gate is on the report |
| `mig.dry_run_failed` | 409 | The dry-run reconciliation gate failed (the real run is structurally blocked — the state machine enforces `dry_run_passed` before `importing`) |
| `mig.cutover_gate_closed` | 409 | Cutover attempted with undispositioned exceptions |
| `mig.parallel_drift` | — | (internal) the daily comparator exceeded tolerance (a P1 event, not an API error) |
| `mig.correction_rejected` | 409 | A correction on an already-corrected row (the chain: corrections are sequential, one per row per cycle) |
| `mig.tenant_not_ready` | 409 | Import attempted before the saga/tenant state allows (the tenant must be `active` with the MIG entitlement) |
| `mig.kyc_reverify_outstanding` | — | (informational) traders blocked at payout by the §3.3 gate — surfaced in the concierge dashboard, not an error |

## 7. API endpoints
> **Scope note:** MIG is not in the V1 execution sheet (V2 scope — the FunderBlu onboarding program). There is no V1 baseline contract for this module; the surface below is design-level (post-V1, docs/99) and provisional until its phase's contract freeze.


Console (MIG is a platform-ops surface — the console realm, the
migration runbook UI):
`POST /v1/console/migrations` (create: tenant, export refs, the policy
set — §3.2/§3.3 decisions recorded as data, 2FA),
`GET /v1/console/migrations/{id}` (the runbook view: class states,
reconciliation report, exceptions queue, the gate state),
`POST /v1/console/migrations/{id}/dry-run` (2FA — starts the §2 step 0
pipeline on the staging tenant),
`POST /v1/console/migrations/{id}/classes/{class}/retry` (after a fix),
`POST /v1/console/migrations/{id}/exceptions/{id}/dispose` (2FA, reason,
action — the COO+ops pattern),
`POST /v1/console/migrations/{id}/cutover` (the gate-checked trigger,
2FA + the V2 two-op — for FunderBlu, two-op from day 1: the §21 CON-32
pattern),
`GET /v1/console/migrations/{id}/parallel-run` (the daily comparator
state), `POST /{id}/parallel-run/close` (the sign-off, 2FA + note),
`POST /v1/console/migrations/{id}/corrections` (the §3.5 flow).

Trader-facing: none (the cutover is invisible-by-design: the trader
logs in, trades, requests payouts — the only trader-visible MIG artifact
is the forced password reset at first login + the FunderBlu comms).

## 8. Schema (key shapes)

```jsonc
// migration record
{ "data": { "id": "01J9MIG…", "tenant_id": "01J9TEN…",
    "status": "reconciled",
    "policies": { "in_flight_challenges": "finish_on_tts",
                  "kyc": "reverify_at_payout", "passwords": "reset_required" },
    "classes": [ { "class": "traders", "state": "imported",
                   "source_rows": 1204, "imported_rows": 1204,
                   "exceptions": 0, "sum_check": "n/a" },
                 { "class": "payouts", "state": "imported",
                   "source_rows": 892, "imported_rows": 892,
                   "exceptions": 3, "sum_source_cents": 4820000000,
                   "sum_imported_cents": 4820000000 } ],
    "gate": { "reconciliation": "99.94% matched",
              "exceptions_dispositioned": 3, "cutover": "pending" } } }

// parallel-run day
{ "data": { "date": "2026-10-02", "accounts_compared": 214,
    "drift": [ { "account_id": "01J9ACC…", "ae_cents": 10412000,
                 "tts_cents": 10411998, "delta_cents": 2 } ],
    "payouts_match": true, "state": "drift" } }
```

## 9. Database design

```sql
CREATE TABLE migrations (
  id          ULID PRIMARY KEY,
  tenant_id   ULID NOT NULL,
  source      TEXT NOT NULL,                  -- 'tts'|'yourpropfirm'|'propaccount'
  status      TEXT NOT NULL DEFAULT 'planned'
    CHECK (status IN ('planned','exports_received','validated',
                      'dry_run_passed','import_ready','importing',
                      'reconciled','cutover_pending','cut_over',
                      'parallel_running','closed','aborted')),
  policies    JSONB NOT NULL,                 -- §3.2/3.3 decisions (data)
  t_date      TIMESTAMPTZ NOT NULL,
  exports_ref JSONB NOT NULL,                 -- R2 keys of the export package
  manifest    JSONB NOT NULL,                 -- TTS's per-class counts/sums
  created_by  ULID, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  closed_at   TIMESTAMPTZ
);
CREATE TABLE migration_classes (
  id            ULID PRIMARY KEY,
  migration_id  ULID NOT NULL REFERENCES migrations(id),
  class         TEXT NOT NULL,                -- traders|accounts|terms|history|orders|payouts|docs|kyc_records
  state         TEXT NOT NULL DEFAULT 'pending'
    CHECK (state IN ('pending','validating','imported','failed')),
  source_rows   INT, imported_rows INT, exceptions_open INT,
  sum_source    BIGINT, sum_imported BIGINT,
  import_meta   JSONB,                        -- importer version, mapping
  started_at    TIMESTAMPTZ, completed_at TIMESTAMPTZ,
  UNIQUE (migration_id, class)
);
CREATE TABLE migration_exceptions (
  id            ULID PRIMARY KEY,
  migration_id  ULID NOT NULL,
  class         TEXT NOT NULL,
  source_hash   TEXT NOT NULL,                -- the row's hash
  reason        TEXT NOT NULL,                -- the MIG_* reason codes
  detail        JSONB NOT NULL,
  disposition   TEXT,                          -- NULL = open
  disposition_action JSONB,                    -- {action, refs}
  disposed_by   ULID, disposed_at TIMESTAMPTZ
);
CREATE INDEX idx_migexc_open ON migration_exceptions(migration_id, disposition);
CREATE TABLE migration_parallel_days (
  id            ULID PRIMARY KEY,
  migration_id  ULID NOT NULL,
  day           DATE NOT NULL,
  accounts_compared INT NOT NULL,
  drift         JSONB NOT NULL,               -- the per-account deltas
  payouts_match BOOLEAN, purchases_match BOOLEAN,
  state         TEXT NOT NULL,                -- matched|drift|resolved
  UNIQUE (migration_id, day)
);
CREATE TABLE migration_corrections (          -- §3.5
  id            ULID PRIMARY KEY,
  migration_id  ULID NOT NULL,
  class         TEXT NOT NULL, source_hash TEXT NOT NULL,
  old           JSONB NOT NULL, new JSONB NOT NULL,
  reason        TEXT NOT NULL,
  approved_by   ULID, approved_at TIMESTAMPTZ,
  domain_refs   JSONB NOT NULL,               -- the LCC/PAY/LED objects touched
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  applied_at    TIMESTAMPTZ
);
-- the imported rows themselves: no new table — every domain table gains
-- the import_meta column (JSONB, NULL for non-imported rows):
--   import_meta = { migration_id, source_hash, source_row, imported_at }
-- the per-row hash is the reconciliation key everywhere (the §3.1 rule)
```

## 10. Security & compliance

- **The export package is a PII gold mine** (traders' KYC data, payout
  methods, history): it lands in R2 (a dedicated `migrations/{tenant}/`
  prefix, the bucket IAM scoped, access = the migration operators'
  console role only, every read audited critical-tier); the package is
  encrypted at rest (R2) + the cutover deletes it on a 30-day
  post-close schedule (the retention job, the deletion audited — the
  data stays 7 yr **as reports**, not as the raw export: the reports +
  import_meta hashes are the 7-yr record, the raw PII export is 30-day
  post-close — the shortest-safe retention, per FunderBlu legal's
  sign-off in Phase 1).
- **Anonymization is structural** (the dry run, §2/§3.7): the PII
  mapping table never touches staging (it's in the production cutover
  bundle, SOPS-encrypted, two-op access) — a staging breach leaks
  synthetic ids, not people.
- **Forced password reset** (§2 step 4): TTS password hashes are not
  imported (the KDF may differ; the reset is the honest posture — and
  it doubles as the "we are a new system, same you" moment that the
  comms plan leans on).
- **KYC honesty** (§3.3): the reverify posture is the compliance
  position (we don't inherit another provider's verdict); FunderBlu
  legal signs the trader notice language (the "your verification will
  be re-checked before your first payout" line — clear, not alarming).
- **The cutover gate is the money control** (§3.4): 100% or
  dispositioned, 2FA'd, two-op, the signed report in R2 — the
  "migrated correctly" claim is a 7-year-defensible artifact.
- **Corrections are the audit story** (§3.5): the `import_meta` never
  mutates; corrections chain; the COO+ops pattern; the domain's own
  correction semantics (reversals, not edits) — the LED-04 discipline
  extends to migration.
- **Access:** the migration console surface is platform:owner + a
  named ops role (CON-18); the disposition/cutover/correction actions
  are the critical-tier set (the CON-09 audit view's most-watched
  events during Phase 2).

## 11. Scalability considerations

- One tenant at a time (FunderBlu is the only V1-era migration) —
  the pipeline is a bounded batch job, not a streaming system:
  ~50k rows total (traders ~5k, accounts ~3-5k, payout history
  ~50k, deals history for active accounts ~200k) — PG transaction
  batches of 1k rows, the whole import ≈ minutes of compute.
- **The MT5 history backfill is the long pole** (08: the MetaApi
  deals history per account, paged API calls — 500 funded accounts ×
  ~200 calls/account at rate limits ≈ hours): it runs **asynchronously
  post-cutover** (the cutover doesn't wait for history: the live sync
  starts at T_date, the backfill fills the gap overnight, the
  gap-detection flag (08's `bridge.sync_gap`) marks the unfilled
  window honestly — "history loading" on the account, not silence).
- The parallel-run comparator: O(funded accounts) daily reads × 14
  days — trivial.
- Productization (V2 MIG-06, 10 concurrent tenants): the pipeline is
  per-tenant isolated (the `migrations` row scopes everything); the
  only shared resource is the MetaApi rate budget (the backfill is
  scheduled off-peak per tenant, the 06 advisory-lock pattern).
- No read-model pressure: the ANA models rebuild from the imported
  rows' events at cutover (the §2 event note — the imported rows emit
  their `account.*` events once, the read models build themselves).

## 12. Open-source solutions

| Option | Verdict |
|---|---|
| **In-house pipeline (this design)** | **CHOSEN** — the importer is a per-source transformation table + validation + reconciliation; no OSS "migration engine" handles "adopt live MT5 accounts into MetaApi mid-flight" (there is nothing to reuse — the 08 bridge is the novel part, and it's ours) |
| pgloader / ETL tools (Airbyte, etc.) | Rejected: they move data between databases; this moves data between **business domains** (TTS states → LCC states + terms + bridge baseline) — the transformation is the product, and the reconciliation gate is custom anyway |
| (For the backfill) MetaApi REST (the 08 rail) | CHOSEN — the deals history endpoint paged; the gap-detection is the 08 pattern |
| DOC (the signed reconciliation report) | CHOSEN — the report is a PDF artifact the COO signs |

## 13. Technology stack

Go (the pipeline workers — the import/reconcile/comparator/correction
jobs, advisory-locked), Postgres (the migration tables + the
`import_meta` column on every domain table), R2 (the export package,
reports, the cutover bundle), CON (the runbook UI — the console's
Phase-2 surface), LED/LCC/PAY/CHK/BRG (the target domains — the
correction flow uses their own semantics), DOC (reports), NOT (the
FunderBlu comms — the trader emails, the ops alerts), Prometheus
(import row rate, exception count, backfill progress, comparator
runtime), Sentry.

## 14. Integration — internal modules (glue)

| Module | How |
|---|---|
| **LCC** | the target of accounts/terms import (the `funded_terms` verbatim rule, §3.2); the `migrated_from` marker; the in-flight-challenge policy machinery; the post-import `account.*` events (the read models' first data) |
| **BRG** | the MetaApi credential handoff (the MT5 adoption, 08 §1); the deals history backfill (the long pole, §11); the gap-detection honesty (`bridge.sync_gap` on the unfilled window) |
| **EVL** | the `evaluation_state` import (the alternative policy path, §3.2: HWM, day counters, the EVL-29 state — the evaluator resumes from the imported state; the `input_hash` chain starts fresh post-cutover (the verdict history is TTS's, our chain starts at T_date — the 09 §10 dispute story: "pre-cutover verdicts: TTS's records; post-cutover: ours, re-runnable") |
| **PAY** | the payout history import (the `settled` + `imported` marks — the §3.2 `paid_out` math from day 1, 11 §14); the parallel-run payout comparator |
| **CHK** | the order import (the revenue baseline); the LED challenge-revenue entries (the tenant's books start true) |
| **KYC** | the §3.3 posture (the records with `reverify_required`; the gate config for migrated traders) |
| **LED** | the baseline entries (revenue, the payout liabilities as historical facts — the import creates the opening-balance entries, the 05 §3 pattern: the books open true, and the nightly trial-balance check (05) starts passing on day 1 of the parallel run) |
| **CON** | the runbook UI (§7), the cutover control (the §21 control ladder + the two-op), the parallel-drift P1 surface |
| **DOC** | the reconciliation report (the signed artifact), the imported documents, the cutover bundle |
| **NOT** | the trader comms (the FunderBlu-branded timeline/reset/
  "same account number" emails — the templates are the Phase-1
  checklist item, FunderBlu COO-approved), the ops alerts |
| **AUD** | the full migration audit chain (the §5 lifecycle events +
  every disposition/correction — the 7-yr "we migrated correctly"
  record) |
| **ANA** | the read models rebuild from the cutover events; the
  parallel-run comparator reads the ANA models (the equity facts) |
| **TEN** | the tenant must be `active` (the saga complete) before import; the custom-domain flip at cutover (the 03 config) |

## 15. Integration — external tools

MetaApi (the MT5 handoff + backfill), R2 (exports/reports/bundle),
Postmark (via NOT — the trader comms), Prometheus/Grafana, Sentry,
TTS's export tooling (theirs — the concierge coordinates the format).

## 16. Implementation blueprint

| Step | Owner | Est | Depends | Exit criteria |
|---|---|---|---|---|
| 1. Export format agreement + manifest spec + the transformation tables (all 8 classes, the state/term mappings) — reviewed with FunderBlu COO (the spreadsheet sign-off) | BE-2 + DevOps | 1 wk (the project work, the MIG-06 concierge) | TEN (FunderBlu active), TTS team | a real TTS export validates against the spec; every mapping row is initialed (the review artifact) |
| 2. Importer engine (per-class, transactional, idempotent, the `import_meta` column migrations on all domain tables) + validation + the exceptions queue | BE-2 | 2 wks | 1, LCC/PAY/CHK/LED schemas | a seeded export (100 synthetic rows/class) imports clean; a re-run is a no-op (idempotency); a bad class rolls back whole |
| 3. Dry-run mode (the anonymization stage + the staging tenant + the simulated-TTS parallel comparator) | BE-2 | 2 wks | 2, 06 (staging) | the FunderBlu anonymized export runs end-to-end: dry-run reconciliation report generated; the mapping table proves correct on real magnitudes |
| 4. Reconciliation report (DOC PDF, the 100%-or-dispositioned gate) + exception dispositions (2FA, two-op) + the cutover gate state machine | BE-2 | 1 wk | 3 | the gate blocks cutover with one open exception (tested); a signed report renders |
| 5. Cutover runbook (the T_date sequence: domain flip, auth import + forced reset, MetaApi handoff per account, the event emission, the read-model rebuild) + the trader comms templates (FunderBlu-approved) | BE-2 + DevOps | 1 wk | 4, 03 (domain), AUTH, 08 | a full cutover drill on staging (synthetic tenant): flip → traders log in → accounts live → ANA shows the data — the drill is recorded (the runbook is proven, not written) |
| 6. Parallel-run comparator (the daily 14-day jobs, the drift P1 wiring, the close sign-off) + corrections flow | BE-2 | 1 wk | 5, ANA models | the comparator flags a seeded 2¢ drift as P1; a correction applies through the domain's own semantics with the full audit chain |
| 7. **FunderBlu cutover (T_date) + the 2-week parallel run + close** | BE-2 + DevOps + FunderBlu COO | the event + 2 wks | 1–6 (the go/no-go at T-7) | the parallel-run report at 14 days: zero unresolved drift; the COO + ops sign; the MIG-04 exit = "cutover closed" in the console with the signed artifacts in R2 |
| 8. (V2) Productization: YourPropFirm + PropAccount importers (the same engine, new transformation tables), the guided concierge flow in the console, the multi-tenant backfill scheduler | BE-2 + FE-2 | 3 wks | 7 | a second synthetic tenant migrates unassisted through the console flow (the "product" proof) |

**Risks:** TTS export quality (the #1 practical risk — a "real" export
with 400 undocumented quirks; mitigation: step 1 is a week of *their*
data in our hands before any code finalizes, the manifest catches the
loud failures, the exceptions queue is the design for the quiet
ones, and the concierge owns the relationship that gets TTS's team to
answer format questions); mid-challenge state loss (mitigation: the
default policy is finish-on-TTS — §3.2 — the risky path is opt-in and
dry-run-exercised); trader trust at cutover (the "did they keep my
terms?" fear — mitigation: the verbatim-terms rule + the comms that
say exactly what is and isn't changing + the parallel run proving the
numbers); the backfill gap (mitigation: it's honest — the
`sync_gap` flag + the "history loading" UX, and the 08 gap-detection
means an incomplete backfill is visible, never silent); cutover-day
incident (mitigation: the 10-second deploy window discipline (06), the
runbook drilled in step 5, the T_date-1 go/no-go with the CON control
ladder staged (the tenant-halt rung is the abort lever), and the
rollback = "keep using TTS" (the cutover is reversible pre-parallel-
run by design — nothing is destroyed on TTS; that's a requirement, not
an accident: **TTS stays read-only, not off, for 30 days post-cutover**
(the rollback window, then the wind-down per FunderBlu/TTS contract)).

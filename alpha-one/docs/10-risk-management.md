# 10 — RSK: Risk Management (Fraud & Anti-Gaming)

> Covers PRD module **RSK** (50 requirements). EVL enforces the rules a trader
> *agreed to*; RSK catches the behavior no rule covers: syndicates, copy
> trading, IP/device reuse, KYC identity reuse, rule gaming. **V1 ships the
> model and case flow only** (RSK-01/10) — detectors land in V2 as a data
> problem, once enough history exists.

## 1. Purpose & scope

- **Signals**: raw detector outputs (V2+), stored, scored, deduped.
- **Risk cases**: a human-reviewable object bundling signals + evidence + a
  trader/account scope; the unit of the risk queue (ADM).
- **Decisions & actions**: approve/reject/escalate → actions execute through the
  normal command paths (LCC suspend, PAY hold, NOT template) — RSK never mutates
  state directly (same rule as EVL: RSK *decides*, LCC/PAY *act*).
- **PRD default (binding):** an open risk case **blocks payouts only** — it does
  not suspend trading, does not auto-fail accounts. (FunderBlu default; per-tenant
  setting V2 `PAY-37` reserve/hold extends this.)
- **Explicitly out of scope (research "integrity rules" list):** A-Book/B-Book
  routing, LP integration, exposure dashboards, trade copying (RSK-23..27, 37..39)
  — Alpha One is not a market maker; those are V3 items for a future execution
  offering.

Requirement coverage: `RSK-01,10` (V1) + `02..08,12..20,28..36,41,43,45..51` (V2) +
`09,21..27,37..39,48..49` (V3).

## 2. Architecture

```
 V1:  LCC breach (EVL) ──────────────► risk case auto-open (kind=breach)
      ADM manual "flag trader" ──────► risk case (kind=manual)
 V2:  detectors (workers, scheduled) ─► signals ──scoring/dedup──► risk case auto-open
      EVL conduct verdicts (V2 rule kinds) ─► signals
 V3:  ML models, cross-account graphs (offline, batch) ─► signals

 case (ADM risk queue) ──decision──► actions:
      · payout hold/release (PAY)      · account suspend (LCC, if tenant policy)
      · trader suspend (AUTH, if tenant policy) · watchlist · allowlist · NOT
```

Detectors run as **batch workers** (nightly + hourly for high-signal ones),
reading PG only — they never touch the hot path. Each detector is a pure job:
`detect(window) → signals[]`, registered in a manifest (name, cadence, inputs,
output schema) — the V2 "detector scheduling & monitoring" (RSK-20) reads that
manifest for dashboards.

## 3. System design

### 3.1 Signal model (RSK-01 — V1, future-proof)

```
signals:
  id · tenant_id · kind (enum registry — V1: breach_ref, manual)
  scope { trader_id, account_id? }
  detector_id (V2: which detector; V1: 'manual'|'breach')
  severity (info|low|medium|high|critical)
  score (0..100, V2 scoring model RSK-28; V1: fixed by kind)
  evidence JSONB (detector output: e.g. {ip, device_hash, accounts:[...]})
  dedup_key (kind + normalized scope — dedupe window 7 d, RSK-28)
  case_id NULL (until attached) · created_at
```

The registry of kinds is data (`risk_signal_kinds` rows) so V2 detectors add
kinds without schema changes. Evidence is **redacted at write** (no KYC document
content, no wallet strings — hashes/pointers only; AUD-23 rules).

### 3.2 Case model & flow (RSK-10 — V1)

```
open ──(review)──► decided {outcome: confirmed|dismissed|escalated_platform}
  │                   │
  └──(auto: 72 h SLA, V2 RSK-29)──► escalated (alert to owner + CON)
decided ──(appeal, V2 RSK-41)──► reopened (audit)
```

Case fields: `id · tenant_id · kind (breach|manual|detector:{kind}|appeal) ·
status · severity (max of signals) · signals[] (ids) · trader_id · accounts[] ·
payout_hold (bool — the V1 action) · decided_by · decided_at · decision_note ·
actions JSONB (what was executed: hold_id, suspend refs) · SLA fields (V2)`.

**Opening a case (V1)** is exactly: `POST /v1/risk/cases` (ADM, risk role) with
signals (≥ 1) or a direct reason; the only V1 side effect:
`payout_hold` set → PAY eligibility check fails until released. Breach cases are
opened **automatically** on `account.breached` (V1: kind=breach, payout_hold per
tenant policy default true) — the "open risk case blocks payouts" default
becomes concrete here.

### 3.3 V2 detectors (design now, build in Phase 3)

| Detector (reqs) | Input | Window | Signal |
|---|---|---|---|
| IP overlap (RSK-03) | login IPs (AUTH), deal times (deals) | 30 d | same IP, ≥ 2 traders, correlated trading hours |
| Device overlap (RSK-04/02) | device hashes (ipinfo + UAs; fingerprint V2) | 30 d | same device hash, ≥ 2 traders |
| Copy trading (RSK-05) | deal streams of account pairs (same tenant) | 7 d | ≥ 90% trade overlap (symbol, side, volume, time ±60 s) |
| Inverse trading (RSK-06) | same | 7 d | mirror positions (hedging a funded acct with a challenge) |
| KYC reuse (RSK-08) | KYC name/DOB hashes + provider ids | all-time | same identity across ≥ 2 traders |
| EVL conduct flags (RSK-07) | `evaluation.verdict` kind=conduct (V2 rules) | live | rule-gaming patterns (grid/martingale RSK-43, sudden strategy RSK-51, hours anomaly RSK-50, perfect consistency RSK-45, drawdown manipulation RSK-46, cycling RSK-47, HFT RSK-36, profit spike RSK-34) |
| Account cycling (RSK-47) | account history per trader | 90 d | repeated fail→repurchase→fail with pattern |
| Latency arb (V3 RSK-38) | deal timing vs news calendar | 1 d | clustered pre-news entries |
| Payment reuse (V3 RSK-09) | payout method hashes | all-time | shared wallet/bank across traders |

Scoring (RSK-28): per-kind base score × recency decay × overlap strength;
dedupe on `dedup_key`; ≥ 70 → auto-open case, 40–69 → signal-only (queue
"watchlist" RSK-43), < 40 → stored only. Allowlists (RSK-30: e.g. known shared
office IPs for a tenant's office traders) suppress signals — managed in ADM,
audited.

### 3.4 Actions (RSK-13/14 — V2 formal workflow; V1 = hold only)

Decision → actions are **executed through owning modules** with the case id as
correlation: PAY `hold/release` (RSK-31: hold expiry = case auto-close + release),
LCC `suspend/reinstate`, AUTH `suspend`, NOT templates. Action execution is
recorded in `case.actions` with refs — the payout queue shows risk context
(RSK-35: a payout with an open case is visibly held and why).

## 4. Events (topic `risk`)

| Event | When | Consumers |
|---|---|---|
| `risk.signal_created` | any signal | ANA (V2), AUD (standard) |
| `risk.case_opened` | manual/auto/after breach | NOT (owner/risk), ADM (queue), AUD |
| `risk.case_decided` | decision | PAY (hold release/keep), LCC (if action), NOT, AUD |
| `risk.case_escalated` (V2) | SLA breach | NOT (owner + CON), AUD |
| `risk.case_appealed` (V2) | trader appeal | ADM, AUD |
| `risk.payout_hold_set` / `risk.payout_hold_released` | hold lifecycle | PAY, NOT, AUD |

## 5. Lifecycles

- **Signal:** `created → deduped (merged) | attached (case) | aged (90 d, then
  archive; RSK-19 retention + audit of deletions)`.
- **Case:** `open → decided → (appeal → reopened) → closed (30 d after decision,
  V2 SLA fields)`. V1: `open → decided` (+auto-close at case decision).
- **Payout hold:** `set (by case) → released (by decision | expiry | manual)`.
- **Watchlist (V2):** `added → active → removed` (trader-level, ADM-managed).
- **Detector (V2):** `enabled → scheduled → (disabled)`, with manifest row.

## 6. Error taxonomy
### 6.1 V1 baseline codes — authoritative

From `contracts/errors/taxonomy.md` (the V1 execution sheet; module RSK). These are the exact codes the V1 surfaces return; the envelope is GW-18 (`code`, `message`, `correlation_id`).
| Code | HTTP | Meaning | User-facing message |
|---|---|---|---|
| `risk.account_not_found` | 404 | Case target account unknown | "Account not found." |
| `risk.case_already_open` | 409 | Second open case on same account | "A review case is already open." |


Namespace `RSK`:
### 6.2 Extended (post-V1) codes — design-level

> Below the V1 baseline (6.1); names in the GW-18 dotted convention. Rows duplicating a V1 baseline code were folded into the baseline table (the merged registry: docs/30).


| Code | HTTP | Meaning |
|---|---|---|
| `rsk.case_not_found` | 404 | — |
| `rsk.case_closed` | 409 | Action on decided case (use appeal, V2) |
| `rsk.signal_required` | 422 | Open case without signal/reason |
| `rsk.decision_conflict` | 409 | Concurrent decision (optimistic lock) |
| `rsk.hold_not_active` | 409 | Release without hold |
| `rsk.allowlist_invalid` | 422 | (V2) Allowlist entry malformed |
| `rsk.detector_disabled` | 422 | (V2) Trigger detector that's disabled |

## 7. API endpoints
### 7.1 V1 baseline — `rsk` (authoritative: `contracts/api/rsk.md`)

| Method + path | Auth | Permission | Idempotency | V1 errors |
|---|---|---|---|---|
| `POST /v1/admin/risk/cases` | staff — RSK-10 (manual opening) | `risk.case.create` # RSK-10 | required | `risk.account_not_found`, `risk.case_already_open` |

Scope, request/response shapes, and per-endpoint notes: `contracts/api/rsk.md` (field values in the research are owner TODOs until contract freeze; canonical JSON is fixed at freeze, per the docs/99 §12 rules).

### 7.2 Extended (post-V1) surface — provisional

> Not in the V1 execution sheet. Design-level; paths beyond the V1 baseline are provisional until the URL-plan decision (`contracts/api/gw.md`, open question). Shown for platform completeness (V2/V3 phases, docs/99).

V1: `GET|POST /v1/risk/cases` (ADM), `GET /v1/risk/cases/{id}`,
`POST /v1/risk/cases/{id}/decide` `{outcome, note}`,
`POST /v1/risk/cases/{id}/hold-release` (manual release, reason),
`GET /v1/risk/cases/{id}/signals`.

V2: signals endpoints, detector manifest/controls, watchlist, allowlist,
appeals, five-account compare (RSK-15), IP/device views (RSK-16/17), SLA
config. Trader (TD): none — traders see **outcomes** (payout hold notice via
NOT), never the case internals (PRD: traders don't see risk internals; appeal
surface V2 RSK-41).
## 8. Schema (key shapes)

```jsonc
// POST /v1/risk/cases → 201
{ "data": { "id": "01J9CASE...", "kind": "manual", "severity": "high",
    "trader_id": "01J9...", "accounts": ["01J9ACC..."], "payout_hold": true,
    "signals": [ { "kind": "manual", "note": "two accounts same IP per trader claim" } ],
    "status": "open" } }

// POST /v1/risk/cases/{id}/decide
{ "data": { "status": "decided", "outcome": "confirmed",
    "actions": [ { "type": "payout_hold", "state": "kept" } ],
    "decided_by": "01J9...", "decided_at": 1758278400000 } }
```

## 9. Database design

```sql
CREATE TABLE risk_signal_kinds (             -- kind registry (data, not code)
  kind        TEXT PRIMARY KEY,
  label       TEXT NOT NULL,
  base_score  INT NOT NULL,
  severity_default TEXT NOT NULL,
  enabled     BOOLEAN NOT NULL DEFAULT false  -- V1: only 'breach','manual'
);

CREATE TABLE risk_signals (
  id          ULID PRIMARY KEY,
  tenant_id   ULID NOT NULL,
  kind        TEXT NOT NULL REFERENCES risk_signal_kinds(kind),
  detector_id TEXT,
  trader_id   ULID NOT NULL,
  account_id  ULID,
  severity    TEXT NOT NULL,
  score       INT NOT NULL,
  evidence    JSONB NOT NULL,               -- redacted at write
  dedup_key   TEXT NOT NULL,
  case_id     ULID,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  archived_at TIMESTAMPTZ
);
CREATE INDEX idx_rsig_tenant ON risk_signals(tenant_id, created_at DESC);
CREATE INDEX idx_rsig_dedup ON risk_signals(tenant_id, dedup_key, created_at DESC);

CREATE TABLE risk_cases (
  id            ULID PRIMARY KEY,
  tenant_id     ULID NOT NULL,
  kind          TEXT NOT NULL,              -- breach|manual|detector:{kind}|appeal
  status        TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','decided','reopened','closed')),
  severity      TEXT NOT NULL,
  trader_id     ULID NOT NULL,
  account_ids   ULID[],
  payout_hold   BOOLEAN NOT NULL DEFAULT false,
  hold_until    TIMESTAMPTZ,                -- RSK-31 (V2 expiry)
  decision_note TEXT,
  actions       JSONB NOT NULL DEFAULT '[]',
  decided_by    ULID, decided_at TIMESTAMPTZ,
  opened_by     ULID,                       -- identity or 'system:evl'
  sla_due_at    TIMESTAMPTZ,                -- V2
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  closed_at     TIMESTAMPTZ
);
CREATE INDEX idx_rcase_tenant_status ON risk_cases(tenant_id, status, created_at DESC);
CREATE INDEX idx_rcase_trader ON risk_cases(tenant_id, trader_id, status);
```

## 10. Security & compliance

- **Evidence hygiene:** no KYC content, no wallet strings, no full documents in
  `evidence` — hashes and pointers; the case detail view fetches originals
  behind sensitive-read audit (AUD-23).
- **Access:** `firm:risk` + `firm:owner` only; decisions require 2FA when they
  release a hold or keep it past 72 h (V2 SLA); all case ops audited
  (critical tier for suspend actions).
- **Trader fairness:** the payout-hold notice names the *class* of issue
  ("under review"), never detector internals; appeal (V2) is the fairness
  mechanism; FunderBlu legal reviewed the hold-notice template (Phase 1 item).
- **Data retention:** signals 90 d hot, cases 7 yr (financial-adjacent),
  detector model artifacts versioned in repo (V2).
- **No auto-punishment in V1** (by design): the only automated V1 action is the
  payout hold on a breach case — every trader-affecting action is human in V1.

## 11. Scalability considerations

- V1 volume: ~10 cases/week/tenant — trivial.
- V2 detector load: copy/inverse detection = pairwise deal correlation;
  bounded by tenant (accounts per tenant ≤ few thousand): O(n²) pair screening
  with prefilter (active same-week accounts, symbol overlap) → < 5 min nightly
  at 2k accounts; the prefilter is the scaling story, not parallelism.
- Graph-like detectors (V3: syndicates) move to a nightly **batch with sampling**
  (top 10% by volume) — full-graph ML is explicitly V3 (RSK-25) with its own
  compute budget (worker slot, off-peak).
- Signals table grows ~1k/day/tenant at V2 scale — partition by year if > 10M.

## 12. Open-source solutions

| Option | Verdict |
|---|---|
| **Custom detectors** (Go workers) | **CHOSEN** — detectors are tenant-specific heuristics; no OSS package does prop-firm anti-gaming |
| Apache Flink (streaming CEP) | Rejected — batch windows suffice (ADR-7 class) |
| scikit-learn/River (research §fraud) | V3 only (RSK-25), Python sidecar for models; V2 is pure Go heuristics |
| Neo4j/graph DB (syndicate graphs) | Rejected V1/V2; V3 batch uses PG recursive CTEs on sampled data first |
| ipinfo (register: NOW) | IP enrichment for detectors (datacenter/residential/TOR flags) |
| FingerprintJS | Deferred per PRD (device overlap V2 uses UA+ipinfo hash first) |

## 13. Technology stack

Go workers (detector jobs, manifest registry), Postgres (signals/cases/kinds),
ADM (queue UI, FE-1), NOT (notifications), AUD (mirror), Prometheus (detector
runtime, case aging), Sentry.

## 14. Integration — internal modules (glue)

| Module | How |
|---|---|
| **EVL** | `account.breached` → auto case (V1); V2 conduct verdicts → signals |
| **PAY** | eligibility: open case → `payout.eligibility_failed {reason: risk_case}`; hold release re-checks eligibility |
| **LCC** | (V2 action path) suspend/reinstate via `account_commands` |
| **AUTH** | (V2) trader suspension on confirmed cases |
| **ADM** | risk queue (ADM-11 V2), decisions, context on payout queue (RSK-35) |
| **NOT** | hold notices, decision notices, owner escalations |
| **ANA** | (V2) risk KPIs: cases/week, confirmed rate, blocked payout $ |
| **AUD** | full case lifecycle mirror |
| **TD** | trader sees payout status reason (TD-10) — never case internals |

## 15. Integration — external tools

ipinfo (IP enrichment), (V2) FingerprintJS if adopted, (V3) Python/ML sidecar,
Prometheus/Grafana, Sentry.

## 16. Implementation blueprint

| Step | Owner | Est | Depends | Exit criteria |
|---|---|---|---|---|
| 1. Schemas (kinds, signals, cases) + case open/decide flow + audit | BE-2 | 2 d | EVT, AUTH | manual case lifecycle works end-to-end in ADM |
| 2. Breach auto-open + payout-hold wiring to PAY eligibility | BE-2 | 1.5 d | 1, LCC, PAY | breach on sandbox → case open → payout request blocked with reason |
| 3. Hold release (decision/manual) + NOT templates | BE-2 | 1 d | 2 | release → eligibility restored within one tick of the event |
| 4. V2: detector framework (manifest, scheduling, scoring, dedupe, allowlist) | BE-2 | 4 d | 1, ANA read models | two dummy detectors registered & scheduled, signals visible |
| 5. V2: detector set 1 (IP, device, KYC reuse, account cycling) + case auto-open ≥ 70 | BE-2 | 5 d | 4 | seeded synthetic syndicate in staging → case auto-opens with evidence |
| 6. V2: detector set 2 (copy/inverse/EVL-conduct ingest) + five-account compare + IP/device views | BE-2 + FE-1 | 6 d | 5 | copy-traded pair detected in staging |
| 7. V2: SLA/escalation, appeals, watchlist, hold expiry | BE-2 | 4 d | 5 | aged case escalates; appeal reopens with audit |
| 8. V3: ML sidecar + graph sampling + latency arb + payment reuse | BE-2 | 4 wks | 5–7 | — |

**Risks:** false-positive reputation damage (mitigation: V1 human-only, V2
auto-open only at ≥ 70 with full evidence + 72 h human SLA before any trader-
facing consequence beyond the payout hold); detector drift on tenant rule
differences (mitigation: detectors are tenant-scoped configs, not global);
evidence privacy (mitigation: redaction at write + sensitive-read audit).

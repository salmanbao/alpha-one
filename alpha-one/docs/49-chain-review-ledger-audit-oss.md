# 49 — The Four-Domain Chain Review + LED/AUD Open-Source Evaluation (ninth pass)

> Two jobs in one pass, 2026-09-19. **Part A** walks the platform **sequentially** —
> authentication → authorization → multi-tenancy → ledger & audit — and verifies every
> *handoff* between the domains, not just each domain in isolation: the eight review
> passes (docs/41–48) each proved one domain; nothing had proved the **chain**. **Part B**
> is the open-source research the owner asked for: existing libraries and tools that let
> LED and AUD be built fast — scored against the repo's binding posture (one box, one
> Postgres, OSI licenses, docs/34) with adopt/watch/reject verdicts.
>
> Requirement coverage: a cross-cutting **review + research artifact** — no PRD rows of
> its own. Findings **C1–C2** (chain) closed by default; the research produces **adopted
> libraries and V2 design rules**, no new decisions. No PRD workbook row changed.

---

## Part A — The sequential chain: every handoff, verified

The platform's request path crosses all four domains before money moves:

```
authn (who) → authz (may) → multi-tenancy (where/whose) → GW pipeline → module action
                                                                    ↘ LED (post) · AUD (record)
```

| # | Handoff | Contract | Verified by | Status |
|---|---|---|---|---|
| 1 | **authn → authz** | the verified token yields `(identity, realm, amr, auth_time)`; the membership yields the **one role**; Casbin evaluates `subject × domain × action` | docs/46 §1 (the five questions); gate 9 seeding | ✓ |
| 2 | **authz → multi-tenancy** | the domain **is** the tenant (`g(identity, role, tenant_id)`); per-tenant audience (D19) refuses a tenant-A token on tenant B's host before any policy runs | docs/46 §3.3/§6; gate 12 | ✓ |
| 3 | **multi-tenancy → authz** | tenant state gates at GW 3.5a are **route-class aware** (onboarding staff surfaces pass); the state × capability matrix is machine-read (`state-capabilities.yaml`, gate 16) | docs/47 §5; docs/04 3.5a note | ✓ |
| 4 | **authz → AUD (synchronous)** | every denial is logged with the matched policy row; sensitive reads are audit-on-access (A5); the fail-closed rule denies the action when the audit write fails | docs/46 §6/§11; docs/05 §6 | ✓ |
| 5 | **authn → AUD** | `audit_events` carries `actor_id/actor_kind/actor_role` — for *route* actions the GW context fills them | docs/05 §9 | ✓ |
| 6 | **events → AUD (asynchronous mirror)** | the audit-applier mirrors catalog events (AUD-02 coverage) — needs actor + correlation **in the event** | docs/05 §14 | **C1 — FIXED** |
| 7 | **multi-tenancy → LED/AUD** | `journal_entry.tenant_id NOT NULL`; appliers are workers → per-message `app.tenant_id` under RLS (decision W); the audit mirror rows are tenant-scoped the same way | docs/47 §15; docs/48 §3 | ✓ |
| 8 | **events → LED** | the ledger-applier consumes `order.paid`, `payout.approved`, `PayoutPaid` (catalog names, F3-closed), idempotent on `idempotency_key`; CoA exists because the saga seeds it (D26, step 6b) | docs/48; docs/03 §3.5 | ✓ |
| 9 | **AUD ↔ authorization keys** | `audit.read`/`audit.export` holders per `roles.yaml` (owner/admin/compliance); cross-tenant tenant-audit = `platform:super_admin` only (D25) | docs/46 matrix; docs/48 | ✓ |
| 10 | **AUD ↔ GDPR/retention** | erasure anonymises tenant audit rows where retention allows — must not break the V2 hash chain | docs/05 §10 | ✓ — chain rule added (§6 below) |
| 11 | **tenancy ↔ LED lifecycle** | termination's settlement-only surfaces still post owed payouts; the tombstone keeps journal/audit history per AUD retention | docs/47 §5; docs/05 §5 | ✓ |
| 12 | **authn → LED (step-up reuse)** | V2 reversal (LED-24) reuses the step-up machinery (`auth_time` freshness) — one mechanism, two consumers | docs/46 §7 A3; docs/05 §3.2 | ✓ (noted) |

**Chain findings (both closed by default — they enforce existing binding text):**

### C1 — The audit mirror had nothing to mirror from (Medium) — FIXED

`audit_events` requires `actor_id`, `actor_role`, `correlation_id`; docs/04's GW step 8
has always promised "correlation propagated: logs, **events**"; and the eighth pass made
the audit-applier a V1 component. But the **EVT-03 envelope carried no `correlation_id`**
(and no actor context), and `order.paid`'s payload carries none either — so every
event-originated audit row would have been written with NULL actor/correlation, and the
trace join (`correlation_id` → request → journal entry) would have been impossible. The
design's own comment ("enrichment goes inside payload") was extended-only, leaving V1
with nothing.

**Fix:** `correlation_id` is now a **required** envelope field (`envelope.schema.json` +
all 31 payload schemas + 149 example files patched; docs/04's envelope comment and the
catalog header updated; docs/31 regenerated). Actor rule stated in docs/05 §14: payload
`*_by` fields (`approved_by`, `executed_by`) when a human acted, else the producing
service (`actor_kind='system'`). The event-catalog CI gate (docs/35 §4) now enforces the
envelope automatically.

### C2 — "Tier decided by the catalog" was never a mapping (Medium) — FIXED

docs/05 promised audit tiers per event ("the tier decided by the catalog") but the
catalog has **no tier column** and no rule existed — the audit-applier had no defined
input. **Fix** (docs/05 §14): a deterministic rule — `critical` = suspensions,
terminations, reversals, audit-tamper classes; `sensitive` = every money-adjacent event
(`payout.*`, `order.*`, `payment.*`) and KYC events; `standard` = the rest. V2 may
promote it to a catalog column (AUD-02 lint).

**Chain verdict:** with C1/C2 closed, all twelve handoffs are specified, enforced, and
(gate-covered) verified. No further gaps found walking authn → authz → multi-tenancy →
LED/AUD end-to-end; the domains now reference each other consistently (docs/46 ↔ 47 ↔ 48
↔ the module docs), and every seam has a CI gate or a named test.

---

## Part B — LED/AUD open-source research: build fast without losing the ledger

> The owner's brief: use what exists so LED and AUD are **rapidly developed**. Method:
> score every credible candidate against the repo's binding posture — one box (ADR-9),
> one Postgres, ~500 journal entries/day, Go stack, OSI-license preference (docs/34),
> self-host everything (ADR-13 precedent). "Adopt" ≠ "replace our design": the fastest
> safe path is **keep the thin Postgres core, adopt libraries for the edges, and steal
> the proven patterns** for the V2 hardening.

### 4. LED candidates (ledger engines)

| Candidate | What it is | License / posture | Verdict |
|---|---|---|---|
| **Postgres journal (our design)** | double-entry tables + deferred-constraint balance trigger + INSERT-only role + reversal-only corrections (docs/48 gate 17) | ours | **ADOPT (V1)** — at ~500 entries/day, anything else is ops weight; the invariant machinery is already commit-enforced |
| **TigerBeetle** | purpose-built OLTP accounting engine; double-entry enforced at engine level; self-hosted; Jepsen-tested | open-source engine, self-host | **V2+ upgrade path (existing register)** — revisit at the recorded 10× volume trigger; same self-hosted posture we already run |
| **Formance Ledger** | self-hostable programmable core ledger (MIT core + Numscript posting DSL); one instance hosts many isolated ledgers | MIT (core) | **Consider-later** at the same review point as TigerBeetle — rejected for V1 (a second storage + API stack for trivial volume); Numscript's posting-template model is the **reference** for our `reason_code` posting flows |
| **Midaz (Lerian Studio)** | Go, cloud-native multi-asset double-entry ledger + Go SDK | **source-available (not OSI)** | **Watch** — fails the docs/34 license posture today; recheck if it relicenses |
| **Fragment / Modern Treasury / Moov** | managed-cloud ledger APIs | proprietary SaaS | **Rejected** — self-host posture; managed-ledger lock-in is the cautionary tale (the QLDB class: vendor-controlled roadmaps) |
| **go-money / shopspring/decimal** | Go money-arithmetic + arbitrary-decimal libraries | MIT / BSD-style | **ADOPTED (V1, edges only)** — `go-money` for cent arithmetic + currency formatting in reports/exports; `shopspring/decimal` where provider payloads/CSVs arrive as decimals. The DB rule is untouched (integer `_cents`, docs/32); libraries never introduce floats |

### 5. AUD candidates (audit trails, tamper-evidence)

| Candidate | What it is | Verdict |
|---|---|---|
| **Postgres append-only + nightly hash snapshots (our design)** | privileges + immutability triggers + R2 checksum snapshots (docs/48) | **ADOPT (V1)** — the compliance surface (query/export/sensitive-read audit) is ours regardless of storage |
| **Hash-chain patterns (per-stream chains, canonical strings, advisory locks)** | the distilled design of several 2026 implementations: chain **per stream** (per tenant) not globally; stamp `prev_hash/entry_hash` under a **transaction-scoped advisory lock** so concurrent appends never fork; hash a **versioned canonical string** of immutable fields with row content entering only as a `content_hash`; verify-from-head jobs | **ADOPTED as the V2 design rules (AUD-14)** — §6 below; documented into docs/05 §10 |
| **Erasure-aware hashing (redact-in-place)** | GDPR right-to-erasure vs immutability: null/redact the PII fields, **keep the hashes**, verification skips erased records — the chain stays verifiable for everyone else | **ADOPTED as a V2 design rule** — resolves the docs/05 §10 "erasure anonymizes audit rows" vs AUD-14 conflict *before* it is built |
| **External anchoring (RFC 3161 timestamping, transparency logs)** | periodically anchor the chain head externally so even a full DB compromise cannot rewrite history unnoticed | **ADOPTED as a V2 option** — nightly anchor of the per-tenant chain head (cheap, no new service for RFC 3161) |
| **immudb (Codenotary)** | immutable, cryptographically verifiable DB; v1.11 (2026) adds built-in immutable audit logging and PostgreSQL compatibility; Merkle-tree verification | **Watch (V2/V3 alternative)** — the right tool if a regulator demands an externally-verifiable store; not V1: a second database for the audit trail's first five years of volume is ops weight |
| **pgaudit (+ immudb-log-audit class shippers)** | Postgres's session/statement audit extension; shippers can land pgaudit JSON into immutable stores | **Pattern reference (ops plane)** — worth a docs/06 hardening note for the *DBA-plane* audit trail; our AUD is the application action plane and stays ours |
| **pgmemento** | trigger-based row-version audit extension for Postgres | Pattern reference only — our audit is app-level action audit with actor/tier/correlation, not row-diff auditing |
| **Trillian / Rekor (Merkle transparency infrastructure)** | Google's append-only Merkle trees / transparency log | Overkill for V1/V2 volumes; the RFC 3161 anchor covers the same guarantee cheaply — revisit only if external verifiers must audit the log directly |
| **OpenTelemetry** | observability traces/metrics | Rejected for AUD — observability is not compliance evidence; different retention, different audience (the docs/05 fail-closed and tier rules have no OTel equivalent) |
| **audit4j and similar JVM audit frameworks** | Java audit libraries | Rejected — wrong runtime (Go stack, ADR/01) |

### 6. The V2 chain design rules (distilled, recorded into docs/05 §10)

1. **One chain per tenant** (a stream), not one global chain — contention drops, and a
   tenant's evidence export *is* its chain segment.
2. **Stamp under a transaction-scoped advisory lock per stream** (`pg_advisory_xact_lock`
   on the tenant key) — concurrent appends can never fork the chain; at our volume the
   serialization cost is nil.
3. **Versioned canonical string**: hash `seq ‖ tenant_id ‖ action ‖ resource ‖ tier ‖
   created_at ‖ correlation_id ‖ content_hash ‖ prev_hash` — the row *content* enters
   only as `content_hash`, so fields can be redacted later without breaking verification
   (rule 4). Changing the canonical format bumps `canonical_version` on the row.
4. **Erasure = redact-in-place**: null `before/after`/IP/geo on erasure, keep every hash,
   verification skips erased rows — GDPR and tamper-evidence stop being enemies.
5. **Anchor the head nightly** (RFC 3161 timestamp or equivalent) so even a full database
   compromise cannot rewrite the past unnoticed; store the anchor in R2 next to the
   existing hash snapshot.
6. **Verify from head** on a nightly job (AUD-24) and expose the verification result on
   the CON integrity dashboard.

### 7. What this pass changed

| Artifact | Change |
|---|---|
| `contracts/events/payloads/envelope.schema.json` + 31 payload schemas + 149 examples | `correlation_id` required (C1) |
| `docs/04-gateway-events.md`, `contracts/events/catalog.md`, `docs/31` (regenerated), `scripts/aggregate_docs.py` | envelope field list + generator |
| `docs/05-ledger-audit.md` | §14 audit-applier actor + tier rules (C1/C2); §10 V2 chain design rules (§6 above); §12 research table; §13 money libraries |
| `docs/49` (this doc) | the chain verification + the research record |
| `README.md`, `scripts/build_docs_site.py`, `docs/99` | docs/49 row; "Design decisions (41–49)" group; ninth-pass artifact line |

No new decisions were required: C1/C2 enforce existing binding text (GW step 8's
propagation promise; the tier model docs/05 already declared), and the research outcome
is library adoptions + V2 design rules, consistent with the docs/34 register.

---

*Navigation: [46 — Authorization](46-authorization-model.md) ·
[47 — Multi-Tenancy](47-multi-tenancy-model.md) ·
[48 — LED/AUD deep review](48-ledger-audit-review.md) (the F-findings and D25–D27) ·
[05 — LED + AUD](05-ledger-audit.md) (the reviewed module) ·
[04 — GW + EVT](04-gateway-events.md) (the envelope and the GW chain) ·
[34 — Tooling Registry](34-tooling-registry.md) (the license posture).*

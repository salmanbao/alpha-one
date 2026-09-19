# 48 — Ledger & Audit: Deep Review (eighth pass)

> Selected after the identity/tenancy passes (docs/41–47): **LED + AUD
> (docs/05)** is the platform's financial system of record and its compliance
> evidence backbone — every money module (CHK, PAY, BIL) posts through it, every
> sensitive action is fail-closed on it, and the SOC 2 story sits on its export
> surface. It had received **no** dedicated review in any pass; this pass reads
> docs/05 end-to-end against the binding sources (the event catalog, the error
> taxonomy, `roles.yaml`, the docs/03 provisioning saga, the D16 RLS model,
> docs/11/12 money modules) and closes ten findings — seven mechanically (the
> binding sources already answered them) and three by owner decision
> (**D25–D27**, recorded in docs/37 and `scripts/design-questions.json`).
>
> Requirement coverage: a cross-cutting **review artifact** — it claims no PRD
> rows of its own; the changes it drives are in §4. No PRD workbook row changed;
> no event or error code was added or removed.

## 1. Summary

| # | Finding | Severity | Resolution |
|---|---|---|---|
| F1 | **The balance invariant could never fire.** The zero-sum check was an `AFTER INSERT` trigger on `journal_entry` — which runs *before any journal line exists* (lines are inserted after the entry row), so every unbalanced entry would have passed. The `CHECK (true)` placeholder constrained nothing | **High** | **FIXED** — a `DEFERRABLE INITIALLY DEFERRED` **constraint trigger on `journal_line`** evaluates each touched entry **at COMMIT**, when all lines are present; the sketch in docs/05 §3.2 is replaced with the working DDL (docs/05 §3.2) |
| F2 | **Illegal partitioned-table DDL, twice.** `audit_events` declared `PRIMARY KEY (id)` with `PARTITION BY RANGE (created_at)` — Postgres requires the partition key in every PK/unique constraint, so the migration would fail outright. The same bug was introduced by docs/47's `usage_events` partitioning (`PRIMARY KEY (id)`) | **High** | **FIXED** — `audit_events` → `PRIMARY KEY (id, created_at)`; `usage_events` → `PRIMARY KEY (id, period_started_at)` (docs/05 §9, docs/03 §9) |
| F3 | **Event names drifted from the catalog and tiers were unlabeled**: docs/05 §3.3/§4 used `checkout.order_paid` (catalog: **`order.paid`**), `payout.settled` (**does not exist** — the V1 settlement event is **`PayoutPaid`**, Decision 6/LCC-23), `checkout.refund_issued` (catalog: `payment.refund_requested`, ext); and §4's single table mixed V1 consumers with extended events and presented three `ext` events as current | **Medium** | **FIXED** — §3.3 uses the catalog names; §4 is split into **4.1 (V1: LED/AUD produce no domain events — the appliers are consumers)** and **4.2 (extended, true `ext` tiers)** |
| F4 | **A phantom order state**: posting rule 2 invented `payment_captured_ledger_pending` as an order state, but docs/12's binding order machine (`open → paid → …`) has no such state — a developer wiring CHK to LED would look for a state that isn't in the owning module | **Medium** | **FIXED** — reframed: "captured but unposted" is the **applier's EVT-05 retry → DLQ semantics + the CON DLQ screen** (docs/04 §5.6); docs/12's machine is untouched (docs/05 §3.2 rule 2) |
| F5 | **`audit.read` holders understated**: docs/05 §10 said "readable only by `firm:compliance`/`firm:owner`", omitting `firm:admin` — contradicting the ratified bindings (D14: owner, admin, compliance) | **Low** | **FIXED** — §10 now cites `roles.yaml` as the source (docs/05 §10) |
| F6 | **"One currency per entry" was a convention, not a constraint** — nothing stopped lines of an entry disagreeing on currency (or an account's currency) | **Low** | **FIXED** — the F1 deferred trigger also rejects `COUNT(DISTINCT currency) > 1` per entry (docs/05 §3.2) |
| F7 | **The immutability DDL the conventions cite didn't exist**: docs/32's convention list says "`BEFORE DELETE` triggers reject (05 §9, 28 §3.3)" but docs/05 §9 carried no such triggers — immutability rested on privileges alone | **Low** | **FIXED** — `no_mutate_journal` / `no_mutate_jline` / `no_mutate_audit` `BEFORE UPDATE OR DELETE` triggers added next to the INSERT-only privilege note (docs/05 §9) |
| F8 | **Phantom role**: cross-tenant tenant-audit access was granted to a `platform:compliance` role that does not exist in the ratified catalog (the G30 one-catalog rule), while docs/21 CON-01 assigns the console audit view to `platform:super_admin` | **Medium** | **FIXED / DECIDED (D25)** — §2 |
| F9 | **The ledger CoA was never seeded**: docs/05 §3.1 says tenant accounts are "seeded at provisioning", but the docs/03 saga (steps 1–9, 3a) has no CoA step — the first `order.paid` post would have failed `led.account_not_found` on every new tenant | **High** | **FIXED / DECIDED (D26)** — §2 |
| F10 | **A Redis dependency on the fail-closed audit path**: `audit_events.seq` was "app-assigned via Redis INCR" while `audit.Write` is fail-closed (audit failure ⇒ sensitive action denied) — a Redis outage would deny every sensitive action platform-wide; and `seq` has **no V1 consumer** (the hash chain that needs it is V2) | **Medium** | **FIXED / DECIDED (D27)** — §2 |

**Severity mix:** 3 High, 4 Medium, 3 Low — 7 closed by default (binding sources
already decided them), 3 by owner decision.

## 2. Decisions D25–D27 (owner answers, 2026-09-19)

| ID | Gap | Decision |
|---|---|---|
| **D25** | F8 | **`platform:super_admin` only.** No new role, no new key: the console audit view (`GET /v1/console/audit`, V2 surface) is a super_admin screen, always critical-tier audited (`security.platform_access`), consistent with docs/21 CON-01 and the one-catalog rule. A dedicated `platform.audit.read` key can still be proposed at the CON V2 freeze if finance/compliance oversight demands it — the freeze is the decision point, not now. docs/05 §10 corrected. |
| **D26** | F9 | **Saga step 6b seeds the CoA.** An idempotent, compensated step right after the EVL rule-pack seed: creates the tenant's chart-of-accounts template (docs/05 §3.1 accounts + platform-account links). Explicit, visible in the CON live saga view, consistent with how rule packs and flags are seeded. docs/03 §3.5 gains the row; the blueprint step counts it; docs/47 §6's summary reads "9 steps + 3a + 6b". |
| **D27** | F10 | **No `seq` in V1.** The column is removed from the V1 DDL; the V2 hash chain (AUD-14) introduces per-tenant monotonic `seq` at chain-init time, backfilled in `id` order. The fail-closed audit write becomes exactly one INSERT inside the action's transaction with **no Redis dependency**. docs/05 §9 carries the note. |

## 3. What the review confirmed as sound (not re-litigated)

- **Postgres double-entry over TigerBeetle at V1 volume** (~500 entries/day) with
  the 10× revisit trigger — the register entry stands (docs/05 §12).
- **Fail-closed audit** on sensitive actions (AUD-01/23): audit write in the
  action's transaction, denial + alert on failure, degradation only for
  non-sensitive actions. The D27 decision removes the one hidden dependency that
  could have turned this posture into an outage amplifier.
- **Reversal-only corrections** (LED-18/24) with the INSERT-only app role —
  now backed by the F7 triggers as defence in depth.
- **The applier architecture**: `ledger-applier` consuming `order.paid` /
  `payout.approved` / `PayoutPaid` (catalog names) with idempotent posting on
  `idempotency_key`, and PAY V1 eligibility computing from payout history
  (docs/11 §3) rather than the V2 `balances` table (docs/05 §14 corrected).
- **AUD's tier model** (standard/sensitive/critical) and the redaction-at-write
  filter (AUD-23) as the mechanism behind the authz passes' "audit-on-access"
  rules (docs/46 A5).

## 4. What changed, by artifact

| Artifact | Change |
|---|---|
| `docs/05-ledger-audit.md` | §3.2 working deferred-trigger DDL + currency rule (F1/F6); §3.3 catalog event names (F3); §3.2 rule 2 applier-retry framing (F4); §4 split V1/extended with true tiers (F3); §9 partitioned PK, immutability triggers, RLS statement, `seq` removed (F2/F7/D27); §10 `audit.read` holders (F5) + `platform:super_admin` (D25); §3.1 CoA seeding note (D26); §14 PAY eligibility source |
| `docs/03-tenant-management.md` | saga step **6b** (CoA seed, D26); blueprint step 4 counts it; `usage_events` partitioned PK fix (F2) |
| `docs/47-multi-tenancy-model.md` | §6 saga summary: "9 steps + 3a + 6b" |
| `docs/32` + `contracts/data/schemas/05-led-aud.sql`, `03-ten.sql` | regenerated from the amended §9s |
| `docs/37` + `scripts/design-questions.json` | D25–D27 recorded with owners |
| `docs/99-development-phases.md` | gate 17; eighth-pass artifact line |
| `docs/34-tooling-registry.md` | §9 checklist item for gate 17 |
| `README.md`, `scripts/build_docs_site.py` | docs/48 row; "Design decisions (41–48)" group |

## 5. Verification

Gate **17** (docs/99, recorded in docs/34 §9): the journal invariant is
commit-enforced — the deferred constraint trigger rejects unbalanced or
mixed-currency entries at COMMIT (a property test over randomized line sets must
pass), the immutability triggers + INSERT-only privileges hold for the app role,
the applier replays the same event idempotently (same `idempotency_key` → one
entry), and a deliberately unbalanced post rolls the business transaction back
with `led.entry_unbalanced`. Plus the existing suite: applier contract tests
(docs/99 tasks 3/4), nightly trial-balance drift monitor, injected-mutation
detection (docs/05 §16 step 8).

## 6. Residual notes (owned, not silent)

1. **Hash chain and legal hold remain V2** (AUD-14/22/24/25) — the V1 posture is
   append-only + nightly R2 hash snapshots; the chain design will reintroduce
   `seq` per D27 and must be verified against partition boundaries.
2. **Multi-currency is V3** (LED-19); until then the single-currency-per-entry
   trigger is what makes the ledger's arithmetic honest.
3. **Provider reconciliation is V2** (LED-12/13/14); V1 money-in correctness
   rides the CHK intent/order machines and the applier's DLQ visibility.
4. The **platform CoA** (Alpha One's own P&L) is referenced by §3.1 but its
   account list lands with the CON platform-finance surface (V2) — the tenant
   template is the V1 deliverable.

---

*Navigation: [05 — LED + AUD](05-ledger-audit.md) (the reviewed module) ·
[11 — PAY](11-payout-system.md) · [12 — CHK](12-checkout-billing.md) ·
[04 — GW + EVT](04-gateway-events.md) §5 (outbox/applier semantics) ·
[47 — Multi-Tenancy Model](47-multi-tenancy-model.md) §6 (the sagas) ·
[46 — Authorization Model](46-authorization-model.md) (A5 audit-on-access) ·
[37 — open questions](37-prd-open-questions.md) (D25–D27).*

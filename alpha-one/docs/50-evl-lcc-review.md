# 50 — EVL + LCC: Deep Review (tenth pass)

> The tenth completeness pass, and the first into the **trading core**: the
> Evaluation & Rule Engine (docs/09 — "the module a trader's livelihood is
> decided by") and the seams it drives into the Account Lifecycle (docs/07 —
> "if LCC's state machine is wrong, everything downstream is wrong"). Passes
> 1–7 covered AUTH/TEN (docs/41–47), pass 8 LED/AUD (docs/48), pass 9 the
> four-domain chain (docs/49). This pass asks the question the chain review
> pointed at: **who feeds the ledger, and can their decisions be trusted
> end-to-end?** Module selection and every design gap below were decided by
> the owner interactively (multiple choice); mechanical inconsistencies were
> fixed in place as enforcements of already-binding text.

## 1. Scope & method

- **Target:** docs/09 (EVL) + docs/07 (LCC) in full; seams to docs/08 (BRG
  triggers), docs/10 (RSK consumers), docs/11 (PAY eligibility), docs/05
  (audit tiers/mirror), docs/04 (envelope/correlation).
- **Cross-checked against every binding registry:** `contracts/events/catalog.md`
  + `payloads/` + `examples/`, `contracts/diagrams/account-state.md` (the
  machine source), `contracts/api/lcc.md` + `evl.md`, `contracts/errors/taxonomy.md`,
  `contracts/permissions/roles.yaml` + `registry.md` + `matrix.md`, docs/32
  (DDL source of truth → `contracts/data/schemas/07-lcc.sql`, `09-evl.sql`),
  docs/35 §4 (contract gates), docs/99 (phases: EVL/LCC are Phase-1 V1.0).
- **Verdict:** the two modules' internals are unusually tight (pure-function
  verdict math, single transition function, idempotency keys, evidence
  hashing). Every finding is a **seam** finding — the places where EVL, LCC
  and the registries meet. Four were design gaps (owner decisions
  **D28–D31**); the rest were mechanical drift, fixed in place.

## 2. Findings

| # | Sev | Finding | Disposition |
|---|---|---|---|
| F1 | **High** | **The V1 catalog cannot wire its own core loop.** Zero EVL/BRG events existed, yet EVL is Phase-1 V1.0 and the binding machine edge `ACTIVE → BREACH_DETECTED` (EVL-17) consumes `evaluation.verdict` — a V1 breach path with no V1 event, schema, or envelope enforcement (the C1 class again, one layer deeper). | **D28 (owner: option A):** promoted the Phase-1 five — `evaluation.verdict`, `bridge.tick`, `account.day_rolled`, `account.activated`, `evaluation.daily_reset` — with payload schemas, examples, catalog rows (docs/31 regenerates: **36 V1 baseline events**). `bridge.tick` is the *observed* record (EVL-49) and does **not** mirror to `audit_events` (docs/05 §14 exception). |
| F2 | **High** | **A false-positive breach could never be undone.** docs/09 §3.7 says the EVL-20 override (V1.1) transitions LCC back `failed → active`; the binding machine has no reverse edge out of FAILED, and LCC-12's manual override-transition is V2 — V1.1 shipped a dead letter. | **D29 (owner: option A):** two guarded reversal edges added — `BREACH_DETECTED → ACTIVE`, `FAILED → ACTIVE` — valid only with a referenced override record (`evaluation_overrides.id`, kind `clear_breach`) + step-up; closed positions stay closed; BRG re-enables trading. Machine (docs/07 §3.1/§3.2), diagram source, `contracts/api/lcc.md` edge list, and docs/09 §3.7 updated together. |
| F3 | **Medium** | **Time-limit expiry was unclassifiable.** Rule packs carry `time_limit` (max_calendar_days) but the EVL-44 matrix classifies only loss rules, the machine has no expiry edge, yet `account.expired` + `failed_reason 'expired'` existed — a second, unspecified enforcement path. | **D30 (owner: option A):** expiry **is a breach verdict** (`rule_id=time_limit`, matrix priority 1 after max_daily_loss) through the existing evidence/idempotency/critical-audit path; `failed_reason='breach:time_limit'`; `account.expired` stays the NOT/ANA mirror event. One enforcement path. |
| F4 | **Medium** | **Suspension didn't freeze evaluation.** LCC freezes `trading_time_left` while SUSPENDED (§3.3), but EVL's `day_rolled` trigger incremented `calendar_days` unconditionally and nothing gated evaluation on account state — a suspended account burned its calendar limit and racked up verdicts while frozen. | **D31 (owner: option A):** suspension freezes everything — the rollover job skips SUSPENDED (and terminal) accounts (no `account.day_rolled`), EVL skips their ticks (WARN, no state change); resume re-evaluates on the next fresh tick; V1-Plus pause behaves the same (`paused_at`). docs/07 §3.3 + docs/09 §3.6/§5. |
| F5 | Medium | **Step-up missing on two registry keys.** EVL-36 (manual re-evaluation) and EVL-20 (override) both say "2FA" in the module docs, but `account.evaluate` / `account.manual_override` had no step-up ABAC in `roles.yaml` — unlike the `payout.approve` precedent. | Fixed mechanically: step-up ABAC added (`mfa_verified_at` within 5 min; the >$500k owner-approval flag kept on override); `matrix.md` regenerated (gate 15 green — 36 keys / 12 roles / 113 registry keys unchanged). |
| F6 | Low | **`AccountBreached` couldn't satisfy LCC-43's chain.** The payload schema had no `verdict_id`/`evidence_ref`, so the breach event couldn't trace its verdict (docs/07 §4.2 and §10 both name them). | Fixed mechanically: `verdict_id` now required, `evidence_ref` optional (generator + schema + example; envelope untouched). |
| F7 | Low | **Auth wording drift.** docs/09 said override = "firm:owner", evaluate = "support staff"; the binding registry grants owner/admin/risk (override with the >$500k owner-approval flag). | Fixed mechanically: docs/09 §3.7/§7.1 aligned to the registry wording. |
| F8 | Low | **State-count fiction.** docs/07 §12 claimed "14 states"; the binding machine has 11. The extra names (`pending_payment`, `provisioning`, `funding_pending`) are row-level statuses, not machine states. | Fixed mechanically: §12 corrected; the spawn section now states the KYC-wait explicitly (the funded row is created on `kyc.approved`; `funding_pending` is a row status). |
| F9 | Low | **Stale-tick contradiction.** §6.2 said stale tick → "evaluation skipped + WARN"; the blueprint's step-7 exit said "→ `gap_flagged`, no verdict" (which is itself an oxymoron — `gap_flagged` is a verdict status). | Fixed mechanically, both texts preserved: stale tick → **no verdict row** + WARN; `bridge.sync_gap` → `gap_flagged` verdict row (the status's only producer). §6.2 + §16 updated. |
| F10 | Low | **Producer contradiction on the suspend event.** §4.2 listed `account.suspended` as produced by "risk (V2)" while the binding machine's admin suspend (LCC-11, V1.1) exists now. | Fixed mechanically: producer = "admin suspend (LCC-11, V1.1); risk (V2 reinstate)"; tier note made explicit (critical). |
| F11 | Low (latent) | **The C1 envelope fix had a regression surface.** `scripts/build_contracts.py`'s `EventEnvelope` template — and the generated `contracts/shared/openapi.yaml` — still lacked `correlation_id`; any regeneration would have silently reverted pass 9. | Fixed mechanically: template + generated artifact both carry `correlation_id` (required) with the docs/49 C1 citation. |
| F12 | Info | **Pass-9's example placeholder violated the envelope's own ULID pattern.** `01JCORRELATION0000000000` is 24 chars and contains O/L/I — excluded by the Crockford pattern; the defect was in all 149 examples (jsonschema wasn't installed in pass 9, so nothing caught it). | Fixed mechanically: all 149 examples now carry the pattern-valid `01J9ZACC0RRT…` placeholder; the six touched examples validate **strictly** (envelope + payload schema). Follow-up recorded: the other 22 V1 + 121 extended examples remain intentionally illustrative (empty/summary payloads, per `examples/README.md`) — a strict example-validation CI gate is a candidate for docs/35 §4. |
| F13 | Info (open) | **FUNDED accounts have no breach edge.** The V1 machine routes FUNDED only to SUSPENDED/TERMINATED; a breach verdict on a funded account has no automatic transition. Deliberately **not decided** in this pass. | Surfaced for the next pass (an owner decision touching LCC × PAY × BRG). Recorded here and in docs/37 via the design-questions register as an open row. |

## 3. Decisions (owner, 2026-09-19)

All four were presented and chosen interactively (multiple choice, this
session); registered in `scripts/design-questions.json` (D28–D31, rendered
into docs/37):

- **D28 — promote the Phase-1 five** to the V1 catalog (option A; alternatives:
  breach-path three only; keep out of catalog).
- **D29 — guarded reversal edges** for the breach override (option A;
  alternatives: pre-FAILED-only reversal; spawn-a-replacement).
- **D30 — expiry = breach verdict** with `rule_id=time_limit` (option A;
  alternative: dedicated `expired` verdict + machine edge + promoted event).
- **D31 — suspension freezes everything** (option A; alternative: calendar
  clock keeps running during suspension).

## 4. Verified clean (no action)

- The machine in docs/07 §3.1 == `contracts/diagrams/account-state.md` ==
  `contracts/api/lcc.md` (edge-for-edge, before the D29 additions).
- EVL/LCC DDL: docs/09 §9 == docs/32 == `contracts/data/schemas/09-evl.sql`;
  docs/07 §9 == docs/32 == `07-lcc.sql` (no drift).
- Error taxonomy: every EVL V1 code (`challenge.*`, `ruleset.*`, `override.*`,
  `account.*`) and every `lcc.*` extended code is registered in
  `contracts/errors/taxonomy.md` with matching HTTP codes.
- Audit tiers: the docs/49 C2 rule covers the new events without extension —
  breach/override/emergency are critical (termination/reversal classes),
  verdict/daily_reset/rollover/activation are standard; the one needed
  addition was the **bridge.tick no-mirror exception** (docs/05 §14).
- LCC-41/43 idempotency design (command keys, `(account_id, verdict_id)`
  dedupe) is intact and now has the payload field (F6) and the catalog event
  (F1) it needs.
- The correlation chain survives end-to-end: GW `X-Correlation-Id` → envelope
  `correlation_id` (C1) → `evaluation.verdict` → LCC transition history →
  `audit_events.correlation_id` → journal `ref_id` — the pass-9 trace join is
  now real for the trading core.

## 5. Wiring (files touched by this pass)

Binding: docs/07 (machine + tables + §3.3 + §4 + §5 + §12), docs/09 (§3.4/§3.6/
§3.7/§4/§6.2/§7.1/§16), docs/08 §4.1 (bridge.tick V1 row), docs/05 §14 (mirror
exception), contracts: `events/catalog.md` (+5 rows, +1 section),
`events/payloads/` (5 new schemas; `AccountBreached` +`verdict_id`),
`events/examples/` (5 promoted + filled; `AccountBreached` example; the ULID-
placeholder repair across all 149), `diagrams/account-state.md` (+2 edges,
render note — PNG re-render pending, no mmdc in CI),
`api/lcc.md` (+2 edges), `permissions/roles.yaml` (+2 step-up ABAC) and
`matrix.md` (regenerated), `shared/openapi.yaml` (envelope correlation_id — F11).
Generators: `build_v1_payloads.py`, `build_contracts.py` (F11 template),
`complete_contracts_pack.py` (promoted-event guard), `aggregate_docs.py`
(regenerated docs/31: 36 V1 baseline), `build_prd_registers.py` (docs/37:
D28–D31 rows). Register: `design-questions.json` (35 questions).

## 6. Follow-ups (explicitly not done here)

1. **F13** — the FUNDED-breach machine edge: owner decision next pass.
2. **Example-validation gate** — strict JSON-Schema validation of V1 examples
   in CI (docs/35 §4 candidate row) after the remaining 22 V1 examples get
   real payloads from their owners.
3. **`account-state.png` re-render** — the diagram source is authoritative;
   the PNG needs a mermaid toolchain pass.

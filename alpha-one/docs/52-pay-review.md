# 52 — PAY: Payout System Deep Review (twelfth pass)

> The twelfth completeness pass: the **Payout System** (docs/11) — "where the
> platform's trust lives: a trader's real money, calculated from trading we
> enforce, moved through providers we don't control." Selection and gap policy
> were the owner's (multiple choice); the open **D32** row from pass 10 was
> folded in by owner decision (PAY + LCC are one seam here). Mechanical
> inconsistencies were fixed in place; design gaps became decisions
> **D32 (answered), D37–D39**. The core loop LCC → BRG → EVL is now fully
> reviewed (passes 10–11); this pass closes the money-out leg of Phase 1.

## 1. Scope & method

- **Target:** docs/11 in full; seams to docs/07 (breach blocks, funded terms),
  docs/10 (RSK hold), docs/13 (KYC-08), docs/05 (LED-07/08 postings, audit
  tiers), docs/02 (step-up), `contracts/api/pay.md` (28 TODOs), `api/not.md`,
  `contracts/diagrams/payout-state.md`, docs/31/32/37.
- **Verdict:** the money math is the tightest in the repo (frozen
  `calc_snapshot`, HWM-based payoutable, integer cents, property-tested
  calculator, PG-native exactly-once guards). The findings are almost all
  **model conflicts** — V2 research text that never got reconciled with the
  binding V1 sheet after the design-report merge.

## 2. Findings

| # | Sev | Finding | Disposition |
|---|---|---|---|
| F1 | **High** | **§3.7 described a V1 that doesn't exist.** "The executor (one worker, V1) processes `approved → processing → settled`" — but V1 execution is **manual** (Build Strategy "Manual for V1"), `processing` has no V1 entry path (§3.3 reserved), and the terminal is `paid`, not `settled`. Blueprint step 5 built the rail adapter + executor + webhooks in V1 on the same wrong premise. | Fixed mechanically (enforces PAY-13 + the Build Strategy): §3.7 now pins the V1 guards on the **approval and recording paths** (advisory-lock + status CAS + re-check-in-lock; recording CAS `approved → paid` under the GW-12 key = double-record impossible); the rail-worker narrative (sweeper, retries, provider idempotency) is explicitly the **V2 PAY-24** design. Blueprint step 5 re-scoped to the manual path; step 10 keeps the V2 executor. |
| F2 | **High** | **The DDL status enum contradicted PAY-13 three ways**: `settled` (machine says `paid`), no `eligibility_checked` (a PAY-13 state), and two invented states — `failed_final`, `on_hold` — that PAY-13 never named (its list is fixed). Same drift in docs/32 + `11-pay.sql`. | Fixed mechanically: CHECK now carries PAY-13's exact nine states; `failed_final` = a V2 terminal *reason* within `failed`; holds are `status_reason='on_hold'` **flags** on `approved` — never states (D32). docs/32 + `11-pay.sql` regenerated. |
| F3 | Medium | **The old balance-based profit formula survived in two registries.** §6.1 and `taxonomy.md` defined `payout.amount_exceeds_available` as "balance+equity − initial − prior payouts" — the exact formula §3.2 Note (a) supersedes ("HWM-based, not equity-based"). A dispute answered from the registry would compute a different number than the calculator. | Fixed mechanically at the source (`taxonomy.md`) + docs/11 §6.1: "HWM − initial − prior payouts, pre-split — §3.2"; docs/30 regenerated. |
| F4 | Medium | **D32 (folded from pass 10): FUNDED accounts had no breach edge**, and docs/11 §14's "approved-but-unexecuted → on-hold queue" had no machine or schema basis (the DDL had invented an `on_hold` state for it). | **D32 (owner: option A):** `FUNDED → BREACH_DETECTED` reuses the breach path (evidence, LCC-43 idempotency, CLOSING cleanup); in-flight approved payouts carry the **hold flag** (`status_reason='on_hold'`, human queue); the RSK breach case auto-opens with `payout_hold` (docs/10 §3). Machine, diagram source, API edge list, docs/07 §3.2/§4.2/§14 updated together — plus the D29 reversal now specifies **restore-to = the pre-breach state** (FUNDED for funded accounts). |
| F5 | Medium | **Reserves enforcement contradicted itself**: §3.6/§10 said V2 (PAY-37), blueprint step 8 built the approval-time hard block early. | **D38 (owner: option A):** V1 = **visibility only** (CON dashboard `cash` vs open obligations + ADM queue banner); the PAY-37 hard block stays V2. §3.6/§10/blueprint aligned. |
| F6 | Medium | **The trader-ack question**: no `payout.requested` event and no confirmation email in V1 (`api/not.md` template 7 TODO); the sheet lists only approved/rejected/PayoutPaid. | **D37 (owner: option A):** no V1 request event — the 201 + TD status is the ack; the finance queue reads the table (PAY-08); template 7 reserved for V2. `api/not.md` + docs/11 §4.1 resolved. |
| F7 | Low | **Failed re-check at approval was unspecified** ("re-checked at approval" bound, failure behavior undefined). | **D39 (owner: option A):** failed re-check returns `payout.ineligible`; the payout **stays `pending_approval`** (no state change; human may reject with a reason). Pinned in §3.7 guard 2. |
| F8 | Low | **§4.1's envelope list predated C1** — no `correlation_id` (docs/07/09 got the fix in passes 9–10; docs/11 was missed). | Fixed mechanically. |
| F9 | Low | **`PAY_STALE_DATA` naming** (§3.2, §11, blueprint step 7) vs the registered dotted code `pay.stale_data` (§6.2/taxonomy). | Fixed mechanically (all three spots). |
| F10 | Info | **`api/pay.md` refresh — 10 of 28 TODOs were already answered by binding text** (the pass-11 F5 pattern): role bindings (roles.yaml), duplicate-request rule (`payout.active_exists` + GW-12), risk-hold HTTP (423 case / 403 suspension), re-check semantics (D39), execution-mismatch rule (§6.1), export key (`payout.record_execution` per the registry row), policy versioning (LCC-20 freeze), threshold source (PAY-38), NOT delivery (the catalog consumer binding), USD-only (docs/38). | Contract refreshed with citations. **Three genuinely-open TODOs remain** (owner PAY/NOT): the `payout.ineligible` sub-reason code scheme, the V1.1 method-confirmation flow (PAY-05/06), and `payout.kyc_required` dedicated-vs-sub-reason (taxonomy TODO). |
| F11 | Info | **Verified clean:** payload schemas carry the actor fields the AUD mirror rule needs (`approved_by`/`rejected_by`/`executed_by`); all six `payout.*` permission keys bound in roles.yaml/registry (the settlement event `PayoutPaid` was renamed to `payout.settled` by D60, docs/58); ledger postings (LED-07 at approve, LED-08 at `PayoutPaid`) match docs/05 §3 and the `reason_code` enum; the `payout-state.md` diagram == §3.3; audit tiers coexist coherently — the **event mirror** rows are sensitive per the docs/49 C2 rule (money-adjacent) while the direct approve/reject **action write** is critical per this module's spec (different records, no conflict). | No action. |

## 3. Decisions (owner, 2026-09-19)

All presented and chosen interactively; registered in
`scripts/design-questions.json` (rendered into docs/37):

- **D32 — answered (option A):** FUNDED breach edge + hold-flag queue; D29
  reversal restores the pre-breach state.
- **D37 — no V1 request event** (option A; alternative: promote
  `payout.requested` + template).
- **D38 — reserves V1 = visibility only** (option A; alternative: early hard
  block at approval).
- **D39 — failed re-check leaves the payout pending** (option A; alternative:
  auto-reject).

## 4. Wiring (files touched by this pass)

Binding: docs/11 (§3.2/§3.3/§3.6/§3.7/§4.1/§6.1/§9/§10/§16), docs/07 (§3.1
machine + §3.2 row + §4.2 + §14), docs/32 (regenerated),
`contracts/diagrams/account-state.md` + `contracts/api/lcc.md` (+FUNDED
breach edge), `contracts/errors/taxonomy.md` (formula), `contracts/api/pay.md`
(10 TODOs resolved with citations), `contracts/api/not.md` (template 7),
docs/30/37 (regenerated). Register: `design-questions.json` (43 questions;
D32 answered). Generators: `aggregate_docs.py`, `build_data_schemas.py`,
`build_prd_registers.py`.

## 5. Follow-ups (explicitly not done here)

1. The three remaining `api/pay.md` owner TODOs: ineligible sub-reason code
   scheme; V1.1 method-confirmation flow (PAY-05/06); `payout.kyc_required`
   dedicated code vs sub-reason.
2. `account-state.png` re-render (now carries **three** unrendered edges:
   the two D29 reversals + the D32 FUNDED breach edge).
3. Carried: strict example-validation gate (docs/35 §4 candidate); BRG-28
   workbook row; credentials-email template (NOT-05).

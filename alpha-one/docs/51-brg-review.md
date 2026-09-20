# 51 — BRG: Trading Bridge Deep Review (eleventh pass)

> The eleventh completeness pass: the **Trading Platform Bridge** (docs/08) —
> the platform's only door into the broker world and its highest-risk external
> dependency (MetaApi), the last unreviewed leg of the Phase-1 core loop
> (LCC → BRG → EVL). Selection and gap policy were the owner's (multiple
> choice); the pass was explicitly allowed to cite the **pf-platform** scaffold
> and **prop-firm-bridge** research report as research input — the owner's
> call, after the eleventh-pass read of both (chat analysis, summary-only).
> Mechanical inconsistencies were fixed in place; design gaps became decisions
> **D33–D36**.

## 1. Scope & method

- **Target:** docs/08 in full; seams to docs/07 (commands, machine edges),
  docs/09 (bridge.tick/gap semantics), docs/11 (BRG-09 on-demand sync for
  payout eligibility), docs/05 (audit), docs/04 (lanes), docs/32 (DDL),
  `contracts/api/brg.md`, `contracts/errors/taxonomy.md`, docs/31/99.
- **Research input (owner-approved):** `pf-platform/` (working scaffold: Rust
  rules-engine, Go EA-push bridge, proto + rule-pack contracts, golden +
  property tests) and `prop-firm-bridge/` (the A–Z report it accompanies —
  the report docs/01 ADR-11 cites). Used as *evidence*, never as normative
  text: where the scaffold's semantics differ from the binding docs, the
  binding docs win (see F9).
- **Verdict:** docs/08's architecture (poll-only V1, adapter interface,
  command/confirm execution, nightly reconciliation) is sound and honestly
  scoped. The serious findings are in the **sync-path mechanics** — one of
  them (F1) would have mis-fired in production on day one.

## 2. Findings

| # | Sev | Finding | Disposition |
|---|---|---|---|
| F1 | **High** | **The bound gap-detection check is wrong for MT5.** §3.3 defined V1 gap detection as per-login ticket continuity (`min(new_tickets) > last_ticket + 1`), but MT5 deal tickets are **server-global** counters — any other account on the same server consumes tickets, so the check alarms on nearly every poll. EVL would have drowned in `gap_flagged` verdicts (every one an ADM page), training ops to ignore the alert. | **D33 (owner: option A):** the V1 check is the **history-window deals-count reconciliation** (history API count vs rows written per window); `last_deal_ticket` demoted to a fetch cursor — *never a continuity oracle*. §3.3/§5/§6 rewritten. The pf-platform scaffold corroborates: its per-account `seq` is bridge-assigned precisely because broker-side counters can't serve as ordering/continuity oracles. |
| F2 | Medium | **`bridge.tick` was under-specified — twice.** The D28 payload schema (pass 10) carried 5 fields against docs/08 §8's canonical shape (positions array, margin/free_margin, leverage, deals_count, last_deal_ticket); and §8 itself contained invalid JSON (`"leverage": 1:500`). | **D34 (owner: option A):** the full §8 shape is canonical — schema + example regenerated (positions array for TD live view/RSK V2; leverage as a string) and strictly validated against the envelope. |
| F3 | Medium | **`account_snapshots` was bound but defined nowhere.** §3.3 requires "every tick updates `account_snapshots` (1 row/account/min, 14-day rolling in PG)"; the table appeared in no DDL (not §9, not docs/32, not ANA). PAY eligibility and TD equity curves read... nothing defined. | **D35 (owner: option A):** BRG-owned partitioned table added to §9 (`account_snapshots`: minute buckets, cents columns, `broker_time`; 14-day rolling drop after the ANA daily rollup); docs/32 + `08-brg.sql` regenerated (docs/32: 124 tables). |
| F4 | Medium | **`bridge.sync_gap` — a V1-emitted event — was not in the V1 catalog.** Gap detection is "V1 basic" (§3.3), EVL's `gap_flagged` status consumes the event, yet only `bridge.tick` had been promoted (D28). Same class as pass-10 F1: V1 behavior with no enveloped event. | Fixed mechanically under the D28 principle ("Phase-1 V1 behavior gets catalog events"): catalog row + payload schema (`window_start`, `expected_count`, `got_count`) + example, all strict-validated. docs/31: **37 V1 baseline events**. |
| F5 | Medium | **`contracts/api/brg.md` was stale on four of five open questions.** It still said "Events emitted: none named in the sheet" (D28 resolved that), and its TODOs for sync interval, retry limits, confirm mechanics, and snapshot schema were all already answered normatively by docs/08 §3 — the contract predated the module doc. Its one true scope question (admin force-sync) was undecided. | Contract refreshed mechanically (answers cited to docs/08 §3.3/§3.4/§9); the force-sync question became **D36 (owner: option A)** — stays worker-internal in V1, sheet-faithful; ADM watches freshness via the health surface. Remaining open TODO: the credentials-email template (NOT-05) — genuinely open, owner NOT. |
| F6 | Low | **`broker.created`/`broker.failed` naming drift.** docs/07 referenced these names in six places (§4.1 row, §4.2 rows, §7.2, §14 ×2, blueprint step 3); the event forms in docs/08 §4.2 are `bridge.account_created`/`bridge.account_create_failed`; and per EVT-20 the V1 mechanism is actually **command completion** (the `account_commands` result row), not an event. | Fixed mechanically: docs/07 now says "BRG reports back by completing the provisioning command; the V2 event forms are `bridge.account_created`/`bridge.account_create_failed`." |
| F7 | Low | **docs/07 §14 said EVL consumes "`account.activated/day_rolled/sync`"** — no `sync` event exists; the trigger is `bridge.tick` (docs/09 §3.6). | Fixed mechanically. |
| F8 | Low | **`free_margin` was polled (§3.3), tick-carried (§8), and snapshot-bound — but had no column.** `broker_accounts` stored equity/balance/margin only. | Fixed mechanically: `last_free_margin_cents BIGINT` added; docs/32 + `08-brg.sql` regenerated. |
| F9 | Info | **Research cross-walk (pf-platform / prop-firm-bridge), for the record:** (1) V1 **poll-only** is the deliberate L2-only layering — the report's L0 (EA) / L1 (bridge pre-trade) enforcement layers exist in the scaffold but were consciously excluded from Alpha One V1 (docs/01/08: no order path; post-trade enforcement only). (2) The scaffold's **integrity-alert taxonomy** (`PNL_MISMATCH`, `BALANCE_DRIFT`, `SEQ_REGRESSION`, `MALFORMED`) is the pattern for BRG-33 V2's per-deal hash reconciliation and the nightly reconciler's exception kinds. (3) Its **checksummed snapshot + control-replay resync protocol** is the reference if V2 streaming (BRG-21) ever replaces polling. (4) Its trust model (platform ledger recomputes PnL) **differs from the binding docs** (broker is truth, EVL never recomputes — docs/09 §3.3); binding docs win. | Recorded; no repo changes to pf-platform (owner: summary-only). |
| F10 | Info (carried) | **BRG-28** (broker server time-drift detection) remains the workbook's one ERROR row — unassigned release, must be defined-or-deleted before the Phase-1 contract freeze (docs/39 §2). Not ours to fix (no workbook changes). | Carried; surfaced again at freeze time. |

## 3. Decisions (owner, 2026-09-19)

All four presented and chosen interactively; registered in
`scripts/design-questions.json` (rendered into docs/37):

- **D33 — history-window gap detection** (option A; alternatives: defer to V2;
  tuned-threshold heuristic).
- **D34 — full §8 shape is the `bridge.tick` canonical payload** (option A;
  alternative: minimal schema + PG reads).
- **D35 — `account_snapshots` is BRG-owned** (option A; alternatives: ANA-only;
  drop the concept).
- **D36 — no admin force-sync in V1** (option A; alternative: V1-Plus endpoint +
  permission key).

## 4. Verified clean (no action)

- All ten `brg.*` error codes registered in `contracts/errors/taxonomy.md`
  with matching severities; provider-safe message discipline holds.
- BRG DDL == docs/32 == `contracts/data/schemas/08-brg.sql` (before this
  pass's additions, which were made at the doc source and regenerated).
- docs/11's payout path: BRG-09 on-demand sync → fresh snapshot → eligibility
  (PAY-02/03) is consistent on both sides.
- docs/04's per-entity lanes cover the per-account ordering EVL needs; the
  command queue (EVT-20) correctly stays out of the event catalog.
- The audit path is coherent: enforcement executions write `broker_executions`
  + direct critical-tier `audit.Write` rows; state consequences mirror via
  LCC events; observed ticks deliberately don't mirror (docs/05 §14).
- Credential custody (BRG-44 envelope, reveal-audited, log-scanner test) is
  consistent with docs/02 §10.2 and docs/28.

## 5. Wiring (files touched by this pass)

Binding: docs/08 (§3.3 D33, §4.1/§4.2, §5, §6, §8 D34, §9 D35+M8), docs/07
(naming, six spots), docs/32 (regenerated: 124 tables),
`contracts/api/brg.md` (refresh + D36), `contracts/events/catalog.md`
(+`bridge.sync_gap`), `contracts/events/payloads/` (bridge.tick full shape;
bridge.sync_gap new; 37 total), `contracts/events/examples/bridge.schema/`
(tick filled; sync_gap filled — both strict-validated),
`contracts/data/schemas/08-brg.sql` (regenerated), docs/31 (37 V1 baseline),
docs/37 (D33–D36). Generators: `build_v1_payloads.py`,
`aggregate_docs.py`, `build_data_schemas.py`, `build_prd_registers.py`.
Register: `design-questions.json` (40 questions).

## 6. Follow-ups (explicitly not done here)

1. **BRG-28** — workbook ERROR row; owner must define or delete before the
   Phase-1 contract freeze (docs/39 §2).
2. **Credentials-email template** — the contract's one remaining open TODO
   (NOT-05 ownership; security vs BRG-06 email delivery).
3. Carried from pass 10: `account-state.png` re-render (no mmdc in CI); the
   strict example-validation gate for docs/35 §4.

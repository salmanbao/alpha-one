# 60 — RSK: Risk Management (nineteenth pass)

> The nineteenth completeness pass reviews **docs/10 (RSK — fraud &
> anti-gaming)** — the last Phase-1 core module without a review pass —
> against its contract (`api/rsk.md`), the permission registry, the event
> catalog, docs/07 (the breach edge it hangs off), docs/11 (the payout
> interlock), docs/17 (the queue screen), docs/19 (the read model), docs/28
> (the threat model) and docs/99 (the build order). The V1 scope is
> deliberately tiny (RSK-01 signal record + RSK-10 case spine; detectors are
> V2 by design), and the doc's architecture held up well — but it carried
> **four genuine design gaps**: an unresolved V1.0 boundary (when does the
> breach auto-open fire?), a two-spelling error namespace (`risk.*` vs
> `rsk.*`), an unsettled 2FA rule for case decisions, and a registered 409
> rule nobody had defined or enforced. The owner ruled all four
> (**D68–D71**); the mechanical drifts (tier labels, event names, consumer
> wiring, payload parity) were fixed in place.

Status: REVIEW — decisions D68–D71 recorded, mechanical fixes applied
Owner: TBD (BE-2)
Version: v1
Last updated: 2026-09-20

---

## 1. Scope & method

- **Module:** docs/10 (RSK-01/10 V1.0; RSK-11 V1.1; detectors V2; ML/graphs V3 — 53 requirements).
- **Cross-checked against:** `api/rsk.md` (10 open TODOs — the most of any unreviewed contract), the registry + roles.yaml, docs/30/31 (taxonomy + catalog), docs/07 §4/§5 (the `AccountBreached` edge, D32's FUNDED row), docs/11 (PAY-04/`payout.risk_hold`), docs/17 §3.1/§3.2 (the Risk-cases screen, the claim pattern), docs/19 §3.1 (`risk_summary`), docs/28 (T3's payout-fraud defense), docs/32/`10-rsk.sql` (the DDL), docs/99 (tasks 1.4 and 2.1).
- **Method** = every pass: read end to end; verify every path, code, event, key and tier against its source; mechanical vs design; design to the owner as MCQs.

## 2. What the review validated (no action needed)

- **The V1 restraint is right and consistent:** signals/cases/kinds in PG, detectors as pure batch jobs behind a manifest, Redis for ephemerals only (§3.5's narrow-by-design table), and the explicit rejection of the research's real-time Redis layout. "RSK decides, LCC/PAY act" mirrors the EVL rule.
- **The fairness posture is coherent:** the PRD default (an open case blocks payouts only), no auto-punishment in V1, evidence redacted at write (AUD-23), the trader never sees case internals, appeal is V2.
- The 53-requirement tier map, the detector table's V2/V3 splits, and the scalability story (prefilter-first O(n²)) matched their sources everywhere we checked.

## 3. Findings

| # | Finding | Class | Resolution |
|---|---|---|---|
| F1 | **The V1.0 boundary was self-contradictory:** §2's diagram and §3.2 put the breach auto-open in V1 (and docs/07's FUNDED breach row + docs/17's queue row agree), but §3.2 also claimed the payout hold as "the only V1 side effect" while the coverage line, docs/99 task 1.4 and task 2.1 put the interlock (RSK-11 + PAY-04) in V1.1 | **Design** | **D68** — the breach auto-open is V1.0 (case + **dormant** `payout_hold` flag, idempotent per breach verdict id); the PAY-04 interlock wires in V1.1 (task 2.1). §3.2 rewritten; docs/07's V1 `AccountBreached` consumer row + docs/99 task 1.4 aligned |
| F2 | **Two spellings, one module:** the V1 codes say `risk.*`, all seven extended codes said `rsk.*` — while the event topic and the permission keys say `risk` | **Design** | **D69** — unified on `risk.*` (the registered baseline + topic + keys win); 7 ext rows renamed, `risk.case_claimed` added from §3.5; docs/30 regenerated |
| F3 | **Case-decision 2FA was unsettled:** §10's garbled sentence ("2FA when they release a hold or keep it past 72 h (V2 SLA)") never states the V1 rule, while the same family elsewhere is strict (payout approve/reject always-2FA; KYC decide 2FA) | **Design** | **D70** — case decisions require the 2FA step-up, always, from V1.0 (the D38 `authz.step_up_required` chain); `risk.case.decide` registered with the abac step-up clause; §10 rewritten |
| F4 | **The registered 409 had no rule behind it:** `risk.case_already_open` ("second open case on same account") is V1-baseline, but the contract flagged "rule not in sheet" and nothing enforced it (cases key on trader with an `account_ids` array — no unique index possible) | **Design** | **D71** — one open case per account, enforced as a transactional check under a per-trader advisory lock; documented in §3.2/§9/DDL and the contract |
| F5 | **The V1 surface was incomplete against its own commitments:** §7.1 had only the create endpoint, decide/list/detail sat in the "provisional" §7.2 block with un-prefixed paths — yet task 1.4's exit test walks the case machine in ADM and docs/17's queue screen is V1-era | Mechanical | Baseline gains `GET /v1/admin/risk/cases`, `GET .../{id}` (reads for the committed queue) and `POST .../decide` (the machine's decided edge); `hold-release` re-tiered V1.1; the stale URL-plan note now cites D46; §7.2 re-tiered |
| F6 | **Event wiring gaps:** `AccountBreached`'s V1 consumer row lacked RSK (the extended row had it); the case events' consumers lacked ANA although docs/19's `risk_summary` already declares the feed; §14 cited `account.breached` (the extended name) without the V1 mapping | Mechanical | docs/07 V1 row + §4.1 consumers + §14 rows fixed (`risk_summary` counts = V1; the KPI analytics stay V2) |
| F7 | **Kind-name drift:** §3.1 said the V1 kinds are `breach_ref, manual`; §2/§9 and the D49 payloads say `breach` | Mechanical | Unified on `breach` |
| F8 | **Payload drift (self-inflicted, pass 18):** the D65 schemas had `account_id` (singular), no `info` severity, no `payout_hold`, an open `outcome`, and a `summary` field the case model doesn't have | Mechanical | Schemas rebuilt to the docs/10 model (trader + `account_ids[]`, severity incl. `info`, `payout_hold`, `outcome` enum `confirmed|dismissed|escalated_platform`, `decision_note`) |
| F9 | **The claim race was presented as available machinery** (`rsk:claim` → `rsk.case_claimed`) while docs/17 §3.2 says V1 has no assignment (V2, ADM-36), and the code was unregistered | Mechanical | §3.5 row marked V2; `risk.case_claimed` 409 registered in §6.2 (D69 namespace) |
| F10 | **Tier/audit ambiguities:** §10's "critical tier for suspend actions" mixed the V2 action path with V1 ops; the audit-tier family list had no home for case decisions | Mechanical | §10 states the mapping (decided = sensitive — money-adjacent; opened = standard; the V2 suspend path = critical); docs/05 §14's sensitive family gains `risk.case_decided` |
| F11 | api/rsk.md: all **10 owner-TODOs** answered from binding text or the D68–D71 rulings; the flat 201/200 bodies conformed to D45; the request/response shapes aligned to §8 | Mechanical | Contract refreshed with citations; zero open questions remain |
| F12 | §5's "V1: open → decided (+auto-close at case decision)" contradicted the 30-d V2 close; the PAY interlock row cited no code | Mechanical | §5: decided is terminal in V1.0; §14's PAY row cites `payout.risk_hold` 423 (V1.1) |

## 4. Decisions (full texts in the register)

- **D68 (auto-open boundary):** the breach auto-open is V1.0 — case + dormant hold flag; the PAY-04 interlock bites from V1.1 (task 2.1). The queue is warm on day one; the sheet's RSK-11 = V1.1 line stands.
- **D69 (namespace):** `risk.*` everywhere — the V1 codes, the topic and the keys already said `risk`; the seven extended rows follow.
- **D70 (step-up):** case decisions carry the 2FA step-up always, from V1.0 — same family treatment as the payout approval and the KYC decide.
- **D71 (uniqueness):** one open case per account (the registered 409's meaning), enforced app-side: transactional check under a per-trader advisory lock.

## 5. Wiring map

| File | Change |
|---|---|
| docs/10 | §3.1 kind name; §3.2 opening paragraph (D68/D71); §3.5 claim row; §4.1 consumers; §5 lifecycle note; §6.2 namespace + `risk.case_claimed`; §7.1 baseline (+reads, +decide); §7.2 re-tier; §9 DDL comments; §10 access/tiers; §14 EVL/PAY/ANA rows |
| docs/07 | V1 `AccountBreached` consumer row gains RSK (D68) |
| docs/05 | §14 sensitive family gains `risk.case_decided` |
| docs/17 | Risk-cases row: the D70 step-up + the queue keys + the D68 note |
| docs/28 | T3's RSK-hold clause annotated (flag V1.0, interlock V1.1) |
| docs/32 + `10-rsk.sql` | DDL comments (D71 rule, dormant flag) |
| docs/99 | Task 1.4: D68 scope + the breach-open exit assertion |
| api/rsk.md | Full refresh: 4 endpoints, D45 shapes, 10 TODOs resolved, permissions/idempotency written |
| registry + roles.yaml | `risk.case.read`, `risk.case.decide` (+ abac step-up) |
| contracts/events/payloads | risk.case_opened/decided rebuilt to the docs/10 model (26 schemas) |
| scripts/design-questions.json | D68–D71 (75 entries) |

## 6. Follow-ups surfaced (not blocking)

- **The cross-cutting freeze audit (docs/28/29/35)** is now the only unreviewed cluster — with RSK closed, every Phase-1 module has a pass. Its sweep families grow by one: `risk.*` vs `rsk.*` spellings (the taxonomy is clean now, but prose may still say `rsk.`).
- The V2 detector pass (Phase 4 wave 3) should re-read §3.3/§3.5 together — the manifest, scoring thresholds and claim/assignment land as one unit.
- The docs/99 task 2.1 exit text still quotes the legacy `PAY_RISK_HOLD` token; the registered name is `payout.risk_hold` — a one-word alignment for the next docs/99 touch.

Like every review pass, this changes V1 design detail only — **no PRD workbook
row was changed**.

# 61 — The Cross-Cutting Freeze Audit (twentieth pass)

> The twentieth completeness pass reviews the three cross-cutting docs —
> **docs/28 (Security)**, **docs/29 (Scalability)**, **docs/35 (Testing
> Strategy)** — the aggregation layer every module review has been editing
> around for nineteen passes. This is the audit the program promised as its
> closing move: verify that the cross-cutting story still matches the
> binding text underneath it, and sweep the drift families the recent
> passes created. **The headline: zero new decisions were needed** — the
> first review pass with none. Every inconsistency found was
> already-decided binding text that hadn't been propagated yet. The book
> freezes consistent.

Status: REVIEW — all findings mechanical (already-decided text, propagated)
Owner: TBD (BE-1, DevOps)
Version: v1
Last updated: 2026-09-20

---

## 1. Scope & method

- **Docs:** docs/28 (1,076 lines — threat model, control stack, PII classes, secrets, compliance, assurance), docs/29 (the capacity model + scaling seams + the failure map), docs/35 (the pyramid, the I-01…I-20 invariant suite, the contract gates, the assurance map).
- **Cross-checked against:** docs/06 (the current OPS posture — D51/D55/D56/D57/D59), docs/55 (the 11-step chain), docs/02 (the restructured AUTH layout), docs/30/31 (the registries), docs/01/03/04/07/23/24/27/32/33/99 (the sweep families), and the decision register (D1–D71).
- **Method** = every pass: read end to end; verify every code, table name, event name, section reference and posture claim against its source; mechanical vs design. This pass produced **no design MCQs** — nothing new required an owner ruling.

## 2. What the review validated (no action needed)

- **The security architecture survived 19 passes of edits:** the top-10 red-team scenarios' defenses all still resolve (scenario 5's forged event is `payout.settled` — post-D60; scenario 8's "origin check" became real with D64; the money-boundary posture, the RLS principal model, the PII class table incl. S2b, and the secrets/age-key ceremony all match their owners).
- **docs/35's invariant suite is the strongest asset in the repo:** I-01…I-20 name their owners, the §5.1 identity/tenancy test plan matches docs/42/43/44's reviewed behaviors, and the assurance map's gates align with docs/99's milestones.
- **docs/29's capacity model is internally sound:** the 2× headroom rule, the per-resource V2-peak table, and the "scale-out is for RTO/residency, not load" posture all cohere; the numbers traced to docs/00 §5 cleanly.
- `sys.internal` (the 500 class), `aud.export_limited`, `chk.capture_mismatch`, `evt.webhook_schema_invalid` — all registered; `payout.risk_hold`, `risk.case_already_open` — correctly cited.

## 3. Findings (all mechanical)

| # | Finding | Fix |
|---|---|---|
| F1 | **docs/29 still described the pre-D51/D55/D56/D57 OPS world:** one Redis ("~4 GB, session/deny-set/SSE/rate-limit"), "the WAL-rsync", "Uptime Kuma" as the monitor, RTO ≤ 2 h as the only story, the drill monthly-only | docs/29 ×7: the three containers (2/2/4 split), pgBackRest, the warm standby (promote ≤ 15 min / ≤ 2 h worst case), the external monitors + dead-man switches, the weekly automated verify (D59) |
| F2 | **docs/28's drill/secrets posture predated the OPS passes:** "the WAL", the monthly drill only, Uptime Kuma ×2, the backup cell in §12 P0 | The restore ritual rewritten (pgBackRest, weekly verify + monthly drill, D56's promoted RTO); §9/§12 re-pointed to D57 |
| F3 | **30+ `02 §x.y` citations pointed at the pre-restructure AUTH layout:** §3.4 (was ABAC/step-up — actually Tenant resolution), §3.6 (was anomaly — doesn't exist; it's §10.5), §3.7 (was envelope — it's §10.2), §3.8 (was SSO — it's §3.3), plus role/session refs split between §3.1/§3.2, Argon2id → §10.1, the API-key → §3.5, the deactivation state → §5 | docs/28: 30 re-points, each verified against the live docs/02 headings; the already-correct refs (§9 DDL, §3.5 API keys, §3.3 IdP ops, §10.2/§10.5 in §12) untouched |
| F4 | **`audit_log` — the table name docs/48 retired:** 3 spots in docs/28 + 2 in docs/32's own conventions header (the DDL says `audit_events`) | All 5 → `audit_events` |
| F5 | **Three legacy uppercase codes** in docs/28/35/99: `AUD_EXPORT_LIMITED`, `CHK_CAPTURE_MISMATCH`, `EVT_WEBHOOK_SCHEMA_INVALID` | Lowercased to the registered forms (`aud.export_limited`, `chk.capture_mismatch`, `evt.webhook_schema_invalid`) |
| F6 | **The `payments.*` alias family still lived in 5 docs:** docs/23 (affiliate accrual feeds ×2 blocks), docs/24 (competition entry fees), docs/27 (the public egress subsets ×2), docs/99 task 1.6 — the registered V1 event is `order.paid`; the ext alias is singular `payment.intent_captured` (docs/12) | All re-pointed with the alias note; docs/07's §14 DOC row gained the V1 names (`FundedCreated`, `AccountBreached`) |
| F7 | **`isolation.test` had no home:** cited as "the 04 §11's event" by docs/28 ×3, docs/35 I-01, docs/99 R4, and the glossary — but docs/04 §11 is Scalability and contains no such event (it's a CI suite, defined by docs/01 ADR-1, described in docs/28 §3.3) | Attribution fixed to "the 01 ADR-1 / the 28 §3.3 / the 35 I-01"; the glossary row follows; the phantom "event" wording dropped (it is not a catalog event and must never appear in docs/31's namespace) |
| F8 | **docs/35 predated the last five decisions** (it was written before D64/D66/D68/D70/D71 existed) | New §3.1: the decision-coverage hooks (the origin-check negatives, the idle carve-outs, the auto-open idempotence, the decide step-up, the one-case rule); I-01's owner fixed; the ABAC fixture list gained the fifth constraint; the drill cadence updated |
| F9 | **docs/28 §3.2's GW-chain recap predated docs/55** and said nothing about the D64 origin check | The recap now names docs/55 §3 as the binding order + the origin check; §6 gained the D64 transport paragraph (cookie realms vs bearer machines) |
| F10 | **docs/28 §7's RSK-hold line** still said "the sole V1 action" without the D68 boundary | Annotated: the flag set in V1.0, the PAY-04 interlock biting from V1.1 |
| F11 | **docs/01/04 still implied Uptime Kuma ran on the prod box** (docs/06 moved it to the standby — D57) | Annotated: standby-hosted + the external checker |

## 4. Decisions

**None.** Every finding resolved against already-ratified text (D51, D55, D56, D57, D59, D60, D64, D65, D68). The register stays at 71 entries — D1–D71 with no gaps.

## 5. Wiring map

| File | Change |
|---|---|
| docs/28 | 45+ mechanical fixes: F2–F6, F9, F10 + the 30 citation re-points (§3 finding table above) |
| docs/29 | F1 (7 fixes across §1.3, §2, §4, §6) |
| docs/35 | F5, F7, F8 (+ the new §3.1 hooks table) |
| docs/32 | F4 (the conventions header ×2) |
| docs/33 | F7 (the glossary owner row) |
| docs/01, docs/04 | F11 (the D57 monitor placement) |
| docs/07, docs/23, docs/24, docs/27, docs/99 | F6 (the `payments.*` family retired; the task 1.6 code lowercased; the R4 attribution) |

## 6. What "freeze" means here (and what stays open)

- **Frozen:** the cross-cutting layer now agrees with every module doc and
  the register; the drift families the reviews were tracking (renamed
  events, URL prefixes, template keys, error spellings, tier labels) all
  sweep clean — `grep`-verified at commit time.
- **Deliberately still open (tracked, not drift):** the ~52 contract
  owner-TODOs in the reviewed modules' contracts (EVL 13, AUD 9, CHK 7,
  LED 6, LCC 5, CON 4, PAY 3, tenant 2, brg 2, kyc 1) — these are frozen
  at contract-freeze per docs/99 §12, not now; the V2/V3 design-level
  blocks; the PK data-residency and hash-chain timing items (docs/28 §13).
- The **PNG re-renders** of the architecture diagrams remain pending
  (carried from earlier passes).

Like every review pass, this changes V1 design detail only — **no PRD workbook
row was changed**.

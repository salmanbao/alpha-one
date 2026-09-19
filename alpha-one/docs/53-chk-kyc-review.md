# 53 — CHK + KYC: Money-In & Gates Deep Review (thirteenth pass)

> The thirteenth completeness pass: **CHK Checkout & Billing** (docs/12) and
> **KYC Identity Verification** (docs/13) — the money-in path and the
> regulatory gates, reviewed together because they are one seam (purchase ↔
> verification levels). This closes the money triangle (CHK in — pass 13,
> LED books — pass 8, PAY out — pass 12) and every Phase-1 core-loop module
> has now had a deep review. Selection and gap policy were the owner's;
> mechanical inconsistencies were fixed in place; design gaps became decisions
> **D40–D44**. The deciding evidence this pass was the **workbook itself**
> (`scripts/prd-backlog.json`): docs/12/13's requirement citations were
> checked row-by-row against the sheet for the first time.

## 1. Scope & method

- **Targets:** docs/12 + docs/13 in full; seams to docs/07 (provisioning saga,
  funding gate), docs/11 (payout gate), docs/05 (LED capture/reversal
  postings), docs/04 (EVT-10 webhook ingress), `contracts/api/chk.md` (19
  TODOs) + `api/kyc.md` (10 TODOs), `contracts/diagrams/kyc-state.md`,
  docs/31/32/37, and the sheet rows CHK-01…44 / KYC-01…16.
- **Verdict:** the webhook-truth architecture (EVT-10 verify → idempotent
  ingest → state machine → outbox → LED) is sound and consistent across both
  modules. The failures were **citations and release tiers**: docs/12 had
  systematically mis-cited sheet rows in a way that upgraded V2 features into
  "binding V1" — caught only by reading the workbook.

## 2. Findings

| # | Sev | Finding | Disposition |
|---|---|---|---|
| F1 | **High** | **Systematic requirement mis-citations in docs/12.** §3.1 cited CHK-05 (a V2 local-methods row) for the pricing snapshot (that is CHK-02); §3.2 cited CHK-15/16 (V2 refunds + V1.1 retry) for the intent state machine (that is CHK-07); §3.4 cited CHK-09 for the refund machine (CHK-09 is *order.paid → provisioning*). An implementer following the citations would have built the wrong release tiers. | Citation fixes mechanical (CHK-02 / CHK-07+16 / CHK-15); the three release-tier questions they hid became **D40–D42**. |
| F2 | Medium | **docs/13 §3.2 existed twice** — two different "Gate semantics" tables with conflicting purchase-gate rows (one "extended — not a V1 KYC row", one citing CHK-10 = V2), a review-merge editing accident. | Merged into one table mechanically; the purchase-gate question became **D44**. |
| F3 | Medium | **Refund release tier** (sheet: CHK-15 = V2; docs/12: full V1 machine + DDL + blueprint step). | **D40 (owner: option A):** V1-Plus **minimal manual refunds** — ADM-only object (reason + 2FA, critical audit, approver ≠ requester), finance executes in the provider dashboard, webhook confirms → `refunded` + LED reversal; no trader self-serve window, no auto-breach trigger, no provider-API automation. Machine/DDL shared so V2 lights up the rest. §3.4 + blueprint step 6 re-scoped. |
| F4 | Medium | **Wire rail tier** (docs/12 V1 rails included bank wire citing CHK-20 = V2; no V1 row covers wire). | **D41 (owner: option B):** wire **demoted to V2** — V1 rails = Match2Pay + Interkasa + NOWPayments; wire capture endpoint + 72 h TTL moved to the V2 blueprint step. |
| F5 | Medium | **Order-creation timing contradiction** (CHK-08: order created on capture; CHK-42: submit never double-creates an order; DDL: `open` pre-payment) — and the **`checkout_sessions` table was dictionary-only**, despite CHK-02/43/44 all operating on it. | **D42 (owner: option A):** order created at checkout submit (idempotent per CHK-42), `open → paid` at capture (CHK-08 read as the capture/fulfillment record); `checkout_sessions` DDL added to §9 (`reserved → completed/expired/cancelled`, price+coupon snapshot, `reservation_expires_at`) — docs/32: 125 tables. |
| F6 | Medium | **KYC DDL contradicted the binding KYC-06 machine** (invented `in_session`/`manual_review`/`verified`/`re_verification_required`; missing `not_started`/`pending`/`approved`/`needs_resubmission`) — the pass-12 F2 class again. | Fixed mechanically under **D43**: CHECK now carries KYC-06's exact seven states; manual review is `in_review` + an `is_manual_review` flag (a queue view, not a state). |
| F7 | Medium | **The KYC machine's three open edges** (`PENDING→EXPIRED` "undefined", `APPROVED→EXPIRED` "P2", `REJECTED→PENDING` "open question") had blocked the catalog's `kyc.expired` row since Decision 5. | **D43 (owner: option A):** `EXPIRED` = the 24 h session TTL only (worker); `APPROVED` never expires in V1 (re-verification = KYC-21/25 V2 — edge removed); `REJECTED` terminal in-session (retry = new session via the 24 h cooldown). Pinned in docs/13 §3.1/§5, the diagram source, the DDL, the catalog row, and `api/kyc.md`. |
| F8 | Medium | **The purchase-gate question**: docs/12 §14 claimed purchases require KYC (citing KYC-08 — the *payout* gate); docs/13's duplicate tables disagreed; the sheet has no purchase-KYC row at all. | **D44 (owner: option A):** **no V1 purchase gate** — login-first checkout is the control; KYC-07 funding is the first KYC touchpoint; the TTS-parity "L1 to buy" is V2 tenant config. docs/12 §14 + docs/13 §3.2 de-conflicted. |
| F9 | Low | **Stale §4.1 envelope lists** in both docs (no `correlation_id`) — the C1 pattern, last modules to carry it. | Fixed mechanically. |
| F10 | Low | **docs/13 §1** said manual fallback is "KYC-11/12, **V1**" while its own coverage list (and §3.1) say **V1.1**. | Fixed mechanically. |
| F11 | Info | **`api/chk.md` + `api/kyc.md` refresh — 15 more owner-TODOs resolved from binding text** (login-first timing, checkout key policy, coupon code naming, session-cancellable guard, CHK-43 sweep + TTL durations, retry-state set, receipt async, failed-payment event tier, the KYC edge set, `kyc.review` key naming, decision enum, already-in-progress rule, manual-doc retention/access, upload size cap, refunds-absence intentionality). **Remaining genuinely-open (owners):** coupon CRUD model, add-on catalog representation, provider webhook payload schemas, order/invoice numbering, invoice tax fields, upload format list, resumable-upload protocol, identity name-match rules. | Contracts refreshed with citations. |
| F12 | Info | **Verified clean:** `provider_events` (EVT-10 ingress idempotency) is defined in docs/04 §9; all `checkout.*`/`kyc.*`/`catalog.*`/`order.*` codes registered in the taxonomy with matching HTTP statuses; `kyc.review`/`kyc.restrictions.write`/`kyc.document.read` bound in roles.yaml (D14 lineage); the five V1 KYC events + `order.paid`/`checkout.session.expired` payloads validate; the audit-tier rule covers refund/capture/decision classes (critical) and KYC notices (sensitive) without extension; the gateway/catalog public-read posture matches TD-09. | No action. |

## 3. Decisions (owner, 2026-09-19)

All presented and chosen interactively; registered in
`scripts/design-questions.json` (rendered into docs/37):

- **D40 — V1-Plus minimal manual refunds** (option A; alternatives:
  sheet-faithful none; full machine).
- **D41 — wire demoted to V2** (option B; alternative: keep as V1-Plus).
- **D42 — order at checkout submit + `checkout_sessions` DDL** (option A;
  alternative: order born at capture).
- **D43 — KYC edges pinned** (option A; alternative: defined triggers on the
  kept edges).
- **D44 — no V1 purchase gate** (option A; alternative: V1-Plus gate at
  session create).

## 4. Wiring (files touched by this pass)

Binding: docs/12 (§1/§2/§3.1–§3.4/§5/§9/§15/§16), docs/13 (§1/§3.1/§3.2/§5/
§9/§14/§16), docs/32 (regenerated: 125 tables), `contracts/api/chk.md` +
`api/kyc.md` (TODO resolutions), `contracts/diagrams/kyc-state.md` (D43),
`contracts/events/catalog.md` (kyc.expired trigger resolved),
`contracts/data/schemas/12-chk.sql` + `13-kyc.sql` (regenerated), docs/37
(D40–D44). Generators: `aggregate_docs.py`, `build_data_schemas.py`,
`build_prd_registers.py`. Register: `design-questions.json` (48 questions).

## 5. Follow-ups (explicitly not done here)

1. The eight genuinely-open contract TODOs (coupon model, add-ons, webhook
   payload schemas, numbering schemes, tax fields, upload formats, resumable
   protocol, name-match rules) — owner items before the contract freeze.
2. `kyc-state.png` + `account-state.png` re-renders (now four unrendered
   edges across the two diagrams).
3. Carried: strict example-validation gate (docs/35 §4); BRG-28 workbook row;
   credentials-email template (NOT-05); the three `api/pay.md` owner TODOs.

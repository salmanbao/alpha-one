# 58 — NOT + DOC: Messages and Paper (seventeenth pass)

> The seventeenth completeness pass reviews the last unreviewed backend pair
> of the Phase-1 money loop: **docs/14 (NOT — notifications)** and
> **docs/15 (DOC — documents & certificates)**. These modules turn the
> reviewed event spine into emails and branded PDFs — payout receipts,
> challenge certificates, breach notices — the artifacts traders screenshot
> and disputes are settled with. The review found the **messiest
> cross-document state of any pass so far**: two irreconcilable template
> lists, a settlement event with two names split across ten-plus docs, a
> typo'd registered error code, and five contract questions the module docs
> had already answered. The owner ruled on four decisions
> (**D60–D63**); everything else was mechanical and fixed in place.

Status: REVIEW — decisions D60–D63 recorded, mechanical fixes applied
Owner: TBD (BE-2)
Version: v1
Last updated: 2026-09-20

---

## 1. Scope & method

- **Modules:** docs/14 (NOT — 4 V1 rows: NOT-01/03/05/13), docs/15 (DOC — 5 V1 rows: DOC-01/03/04/05/06).
- **Cross-checked against:** docs/31 (the event catalog — the name oracle), docs/11 §4 + docs/05 (the PayoutPaid citations), docs/48 F3 + docs/52 (the prior rulings), docs/52 D37 (the payout-requested ruling), docs/12 (the order.paid = payment.intent_captured mapping), docs/13 (KYC events), docs/56 §4 (the ops.* signals), docs/04 (D45/D46/GW-31), docs/32 (schema harvest), docs/99 (tasks 0.7/1.8/1.9), `contracts/api/not.md` + `contracts/api/doc.md`, `contracts/permissions/registry.md`, `contracts/events/payloads/`.
- **Method** = every pass: read end to end; verify every template, trigger, event name, code and endpoint against its citing/cited source; mechanical vs design classification; design gaps to the owner as MCQs.

## 2. What the review validated (no action needed)

- The **dumb-pipe architecture** (map → dedupe → render → send → log; producers never call NOT directly) and the in-house-vs-Novu rejection rationale.
- The **PII guard** on template vars (whitelisted selectors + renderer regex; property-tested) and the **no-cross-tenant-mail** rule (tenancy from the producer-stamped `tenant_id`, never from recipient attributes).
- **NOT-13 dedupe** (SETNX 24 h before render — replay/redelivery/replay-of-the-log all absorbed) and the append-only notification unit.
- **DOC's frozen-snapshot rule** (mappers read only LCC-20/PAY-02 snapshots — a PDF can never show a number that changed later), masking by design, the no-network render sandbox, R2 tenant-prefix isolation with audited signed URLs, and money-doc immutability under regeneration.

## 3. Findings

| # | Finding | Class | Resolution |
|---|---|---|---|
| F1 | **The settlement event has two names.** Registered: `PayoutPaid` (Decision 6; docs/48 F3 *fixed docs/05 to it* and called `payout.settled` nonexistent). Drift: **ten-plus docs** (docs/11 diagram text, docs/14, docs/15, docs/19–24, docs/99 1.7) say `payout.settled` — a name in no catalog | **Design** | **D60** — `payout.settled` is the V1 name; docs/11 §4.1 + docs/05 + the payload schema (`payout.settled.v1.json`) + the generator + review citations renamed; the ten-plus drift docs became correct with zero edits. (The `prd-backlog.json` sheet text is untouched — workbook rows are frozen.) |
| F2 | **Two irreconcilable template lists.** `api/not.md`: 10 templates (account created, phase passed/failed, breach, KYC invite/result, payout requested/approved/rejected, certificate). docs/14 §3.4: ~23 (kyc set, payout set, payment set, staff ops set). They barely overlap — and templates in **both** lists lack V1 triggers (payout requested → D37; refund → V2 CHK-15/35; risk cases → no V1 risk events; certificate email → DOC-07 is V2; payment_pending → no V1 event) | **Design** | **D61** — one merged, catalog-anchored set: **14 V1 templates** (11 trader + 3 staff), every one mapped to a registered V1 event; everything else a V2 reserve with its future trigger **named** ("never ship a dead template"). docs/14 §3.4 + api/not.md rewritten to the one set |
| F3 | The contract's oldest TODO: what fires the "KYC invite" email? (`kyc.session_started` is ext, no email consumer; the session opens mid-checkout) | **Design** | **D62** — no V1 invite email; the template is a V2 reserve |
| F4 | The catalog's own open question: does `kyc.expired` email anyone? | **Design** | **D63** — silent in V1 (portal status + the payout gate's `kyc.required` error are the signals) |
| F5 | `not.recipoent_unknown` — a **typo inside a registered error code** (taxonomy + docs/14 §6) | Mechanical | Renamed `not.recipient_unknown` in both; docs/30 regenerated |
| F6 | docs/14 dedupe formula stated two ways (§2 omits `template_key`; §3.5 includes it); consumes a **`system.*` topic that was never registered** (the ops signals are `ops.*`, docs/56) | Mechanical | §2 aligned to §3.5; topics/consumes lines now name the registered V1 event set + `ops.*` |
| F7 | docs/14 §4 and docs/15 §4 had no 4.1/4.2 split — the catalog harvester marked **all** their events ext, including the V1 worker emissions | Mechanical | Both split: V1 baselines (`notification.sent/failed_final/suppressed`; `document.generated/failed`) now harvest as V1 |
| F8 | docs/15 triggers used `payments.intent_captured` (a **misspelled alias** — docs/12: `order.paid` = the extended `payment.intent_captured`) and `account.funded` (the ext event) where the V1 catalog events are `order.paid` and `FundedCreated`; api/doc.md consumed `AccountPassed` for certificates (a **V2 document type**) | Mechanical | All V1 trigger references renamed to the catalog names; the phase certificate marked V2 in docs/15 §3.1 + api/doc.md |
| F9 | docs/15 §6.2 `doc.not_found` **duplicated the V1 baseline** `document.not_found` (the same fold pattern as pass 14's idempotency pair) | Mechanical | Extended row folded with the standard annotation |
| F10 | The **signed-URL download endpoint was missing from the V1 baseline** (api/doc.md answered PDF binary through the api) while every other text (§2/§5/§10, blueprint step 4) depends on the worker→R2→signed-read flow | Mechanical | `GET /v1/trader/documents/{document_id}/url` added to docs/15 §7.1 + api/doc.md (15-min TTL, audited, `doc.pending` 409); the binary response retired |
| F11 | api/doc.md responses violated the **D45 envelope** (`{documents: [...]}` with TODO fields); 4 open questions + the permission-naming TODO were answerable from existing binding text | Mechanical | D45 shapes written; `document.read` cited from the registry; the four questions resolved (cert ID = the `documents.id` ULID, cert_hash being the separate V2 mechanism; CHK owns the order/lines/invoice number, DOC renders; async with `doc.pending` 409; storage keys `documents/{tenant}/{type}/{id}.pdf`) |
| F12 | docs/99 task 1.8 claimed preferences + the in-app channel for V1 (NOT-11/07/08 are **V2 rows**; docs/14 §3.2 is recipient resolution, not preferences) | Mechanical | Task text corrected; template-set pointer to D61 added |
| F13 | Stale §7.2 URL-plan notes in both docs (D46 resolved the plan); docs/15 §7.2 trader paths missed the `/v1/trader/` prefix | Mechanical | Notes cite D46; prefixes fixed |
| F14 | docs/15's catalog cell for the settlement event said DOC consumes it for a "certificate" — it is the **receipt** trigger | Mechanical | Fixed in docs/11 §4.1 + the payload schema consumers |

## 4. Decisions (full texts in the register)

- **D60 (event name):** the V1 settlement event is **`payout.settled`** — the catalog row, payload schema, docs/05/11 and the review citations renamed; the PascalCase `PayoutPaid` is retired (the LCC-23 PascalCase set is untouched).
- **D61 (template set):** **14 V1 templates** — trader: account_created, phase_passed, phase_failed, breach, kyc_approved, kyc_rejected, kyc_needs_docs, payout_approved, payout_rejected, payout_settled, payment_captured; staff: payout_approved_by_other, payout_settled_staff, worker_dlq. V2 reserves name their triggers (payout.requested, payout.failed, refund events, checkout-session lifecycle, risk.*, kyc.session_started promotion, manual-review event, ledger.reconciliation_exception, document.generated+DOC-07, OPS-40).
- **D62:** no V1 KYC invite email (the session opens mid-checkout; `kyc.session_started` stays ext).
- **D63:** kyc.expired is silent in V1 (portal + the `kyc.required` payout-gate error are the signals).

## 5. Wiring map

| File | Change |
|---|---|
| docs/14 | §2 topics/dedupe; §3.3 count; §3.4 rewritten (the D61 set); §4 split 4.1/4.2 + registered consume list; §6 typo; §7.2 D46 note |
| docs/15 | §1/§3.1/§14 trigger renames + phase-cert V2 note; §4 split + consumes; §6.2 fold; §7.1 +/url row; §7.2 D46 + prefixes; §2 diagram prefix |
| contracts/api/not.md | rewritten: the 14-template set, registered consume/emit lists, all six questions resolved |
| contracts/api/doc.md | D45 responses; +/url endpoint; permission cited; triggers corrected; all four questions resolved |
| docs/11, docs/05 | `PayoutPaid` → `payout.settled` (D60) with annotations; docs/48 F3 superseded-note; docs/52 rename note |
| contracts/events/payloads/ | `PayoutPaid.v1.json` → `payout.settled.v1.json` (generator key renamed; regen) |
| scripts/ | build_v1_payloads.py key; aggregate_docs.py PascalCase label |
| taxonomy | recipient typo |
| docs/99 | task 1.8 tier fix; seventeenth-pass sentence |
| scripts/design-questions.json | D60–D63 (67 entries) |

## 6. Follow-ups surfaced (not blocking)

- The **payload-generator drift** carried from earlier passes now includes the renamed schema — a one-time `build_v1_payloads.py` regen lands with this pass; the remaining 13-schema field drift stays on the carried list.
- The **credentials-email template** (staff onboarding invite) remains a NOT-05 gap to settle with the AUTH/CON surfaces pass — docs/06 §3.6's onboarding runbook creates the user in ZITADEL (whose own invite mail may cover it); decide at the surfaces pass.
- Cross-cutting freeze audit (docs/28/29/35) remains the closing pass — this pass found two name-drift families it should sweep for (`payout.settled`-class event renames and template-key style).

Like every review pass, this changes V1 design detail only — **no PRD workbook
row was changed** (the sheet's `PayoutPaid` story text stays as written; the
catalog + payloads carry the D60 name).

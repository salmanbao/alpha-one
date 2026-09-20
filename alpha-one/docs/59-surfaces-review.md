# 59 — Surfaces: TD + ADM + CON + ANA (eighteenth pass)

> The eighteenth completeness pass reviews the four surface modules of
> Phase 1: **docs/16 (TD — trader portal)**, **docs/17 (ADM — tenant admin)**,
> **docs/21 (CON — platform console)**, and **docs/19 (ANA — analytics &
> read models)** — including the payout-approval money gate (2FA + the
> two-person rule) that these surfaces put on the binding PAY backend
> reviewed in docs/52. The surfaces are the least cross-checked texts in the
> repo: the pass found **the biggest architectural contradiction since the
> Redis bug** (browser transport: bearer vs cookie, with a CSRF defense
> cited to middleware that was never written), a V1 screen riding events
> that officially don't exist in V1, a session-timeout split with no
> policy behind it, and an admin panel placed on the wrong product's
> subdomain. The owner ruled four decisions (**D64–D67**); twelve-plus
> mechanical drifts were fixed in place.

Status: REVIEW — decisions D64–D67 recorded, mechanical fixes applied
Owner: TBD (FE-1, FE-2, BE-1, BE-2)
Version: v1
Last updated: 2026-09-20

---

## 1. Scope & method

- **Modules:** docs/16 (TD-02/03/09/10 V1.0 + TD-05 V1.1), docs/17 (ADM-05 V1.0 + the doc-committed core queues), docs/21 (CON-01/29/30), docs/19 (ANA-01 V1.0 + ANA-32 V1.1).
- **Cross-checked against:** docs/04 (the chain, D45/D46, the realm table), docs/02 (sessions, realms, the §9 parameter block), docs/28 (the T8 threat model's CSRF defense), docs/47 (the host model), docs/55 (the GW spec), docs/56 (`ops.*`), docs/58 (the D61 reserves), docs/11/12 §7 (the normalized trader paths), docs/31 (the catalog), the registry (D14-ratified keys), docs/99 (tasks 1.10–1.13 + 3.2), and the four contracts (`api/td|adm|con|ana.md`).
- **Method** = every pass: read end to end; verify every path, code, event, key and parameter against its source; mechanical vs design; design to the owner as MCQs.

## 2. What the review validated (no action needed)

- **The money gate is coherent end to end:** payout approve/reject in ADM → 2FA step-up on every action (§3.3: "always, no exceptions in V1") → `authz.step_up_required` per D38 → the two-person trail via `payout_approved_by_other` (docs/58) → critical audit → `pay.state_conflict` 409 on concurrent approves (registered) with no optimistic UI. The blueprint's exit test (finance dry-run, every step 2FA'd) matches docs/52's rules.
- **The 404-not-403 posture, the realm separation (TD/ADM/CON never share session storage), the G31 tokens-carry-context rule in impersonation (docs/21 §3.3 server-side readonly), and the ANA principles** (rebuildable-never-authoritative, `as_of` everywhere, tenant-isolated rows) are all correctly stated and consistent with their sources.
- docs/21's incident ladder ("what keeps working" mandatory text), the deny-listed impersonation actions, and the CON V1 baseline codes were already clean (earlier passes touched them).

## 3. Findings

| # | Finding | Class | Resolution |
|---|---|---|---|
| F1 | **The transport contradiction:** docs/04 §3.1 realm table says trader/staff = JWT bearer; docs/16 §2/§10 (and 17/21 implicitly) say the browser uses a same-origin session cookie; docs/28 T8 then cites "the CSRF origin check — the 04's middleware" which **no gateway text defines**. The SSE design, CSRF posture, and MOB reuse all hinge on it | **Design** | **D64** — dual transport: browser = HttpOnly session cookie (`auth_sessions` projection; ZITADEL refresh behind it), machines = bearer; the GW chain gains the **origin check** on cookie-authenticated mutations. Written into docs/02 §3.3, docs/04 §3.1, docs/55 §4.3; docs/16 §10 citation fixed |
| F2 | **V1 screen on ext events:** the ADM risk queue (V1-committed) lives on `risk.case_opened/decided` — catalogued ext; RSK-01/10 are V1 rows | **Design** | **D65** — the two lifecycle events promoted to V1 (docs/10 §4 split 4.1/4.2; payload schemas added; catalog regenerated). The risk-case *email templates* stay V2 reserves (docs/58 D61 — no contradiction) |
| F3 | **Session idle split with no policy:** docs/02 §9 says 30 min globally; docs/17 ("idle 15 — money actions") and docs/21 CON-30 enforce 15 for staff/console | **Design** | **D66** — realm carve-out in docs/02 §9: traders 30, staff + console 15 (both mentions + the session machine) |
| F4 | **ADM on the wrong host:** docs/17 §2 placed the admin panel on `console.alphaone.example` — docs/21's console host; no text names the admin host | **Design** | **D67** — the admin renders on the tenant's own host under `/admin` (one host per firm; session realm decides the portal; realm-name-separated cookies; tenant resolution unchanged; console keeps its own subdomain) |
| F5 | docs/16 §3.4 rendered the **pre-D45 error envelope** (`{error:{code,message,details}}`) | Mechanical | GW-18 shape written; `details` marked as the V2 extension |
| F6 | docs/16 §3.1/§7.2 paths un-prefixed (`/v1/accounts`, `/v1/payouts`, `/v1/documents`, `/v1/payments/catalog`) and the SSE route `/v1/td/streams/*` outside the D46 plan | Mechanical | All normalized to `/v1/trader/*` per docs/11/12/15 §7 (verified against the owning contracts); `/v1/td/health` → `/v1/trader/status` |
| F7 | api/td.md's Out-Of-Scope line ("polling…") contradicted the docs/01 §4.3 SSE design | Mechanical | Reworded: one-way SSE + the TD-11 polling fallback; no WebSockets (the actual constraint) |
| F8 | docs/17 §6 cited `auth.mfa_required` (401, the missing-`amr` case) for the 5-min step-up expiry | Mechanical | `authz.step_up_required` 403 (the registered D38 code), with the distinction stated |
| F9 | docs/17 contradicted itself on PAY-44 export (V1 in §1, "not in V1" in §3.1; PAY-44 is V1.1 per docs/99) | Mechanical | Aligned to V1.1 in both |
| F10 | `system.*` ops events consumed in docs/17 §4 and docs/21 §4 (the topic was never registered — docs/56 fixed OPS to `ops.*`) | Mechanical | Both now consume `ops.*` |
| F11 | docs/19's ANA-32 header said V1 while its own coverage line, the contract, and docs/99 say **V1.1**; the feed lines used unregistered names (`payments.intent_captured/refund_settled`, `payments.intent_created`) | Mechanical | Header/§3.2 re-tiered (the `kpi_snapshot` read model ships with ANA-01, the screen in V1.1); feeds renamed to the registered events (`order.paid`; funnel steps from registered V1 events) |
| F12 | api/con.md responses violated D45 (raw `{session_token…}`); `console.cannot_revoke_self` carried a TODO that docs/21 §6.1 already answers; api/ana.md had a flat non-envelope KPI response, a stale key-naming TODO (D14 ratified `analytics.read`), and four TODOs answerable from docs/19 §3.1/§3.2 | Mechanical | All rewritten/resolved by citation |
| F13 | api/td.md TODOs (TD-05 progress endpoint; polling cadence) answerable from docs/16 §8/§3.2/§5; api/adm.md's "does ADM need endpoints" answered by docs/17 §7.1 | Mechanical | Resolved by citation |
| F14 | Stale D46 URL-plan notes in docs/16/17/21 §7.2; docs/21 §3.2's maintenance rung read as V2-only while the GW-32 flag is live in V1 (D54's minimal Flipt) | Mechanical | Notes cite D46; the maintenance rung annotated (V1 = flip Flipt directly; CON-16 screen V2) |

## 4. Decisions (full texts in the register)

- **D64 (transport):** browser surfaces authenticate with the HttpOnly session cookie (the `auth_sessions` projection; ZITADEL refresh behind it); machine clients keep the bearer JWT; the GW chain performs the **origin check** on cookie-authenticated state changes (docs/28 T8's defense, now implemented). SSE works unchanged.
- **D65 (risk events):** `risk.case_opened` + `risk.case_decided` are V1 catalog events (consumers: ADM queue, AUD; PAY/LCC on decide); the risk-case email templates remain V2 reserves.
- **D66 (idle):** traders 30 min; staff + console 15 min (docs/02 §9 carries the carve-out; the surface docs' stricter numbers are now policy).
- **D67 (admin host):** the staff admin lives on the tenant's own host under `/admin`; the platform console keeps its dedicated subdomain.

## 5. Wiring map

| File | Change |
|---|---|
| docs/16 | §2 SSE path; §3.1 paths + methods-tier note; §3.4 GW-18 envelope; §4 stream-frame note; §7.2 D46 + paths; §10 CSRF citation |
| docs/17 | §2 host (D67); §1/§3.1 PAY-44 tier; §4 `ops.*`; §6 step-up code; §7.2 D46 |
| docs/21 | §3.2 maintenance-rung V1 annotation; §4 `ops.*`; §7.2 D46 |
| docs/19 | §1/§3.2 ANA-32 re-tiered; §2 feeds to registered events |
| docs/02 | §3.3 transport (D64); §9 idle carve-out (D66, both mentions) |
| docs/04 | §3.1: D46 note replaced the stale open-question text; the D64 transport + origin-check paragraph |
| docs/55 | §4.3 the D64 transport + origin-check paragraph |
| docs/10 | §4 split 4.1/4.2 (D65) |
| api/td.md | OOS/SSE rewording; TD-05 + polling TODOs resolved |
| api/adm.md | endpoints TODO resolved |
| api/con.md | D45 responses; cannot_revoke_self resolved |
| api/ana.md | key cited (D14); D45 KPI response; four TODOs resolved |
| contracts/events/payloads/ | +risk.case_opened.v1.json, +risk.case_decided.v1.json (26 schemas) |
| scripts/design-questions.json | D64–D67 (71 entries) |

## 6. Follow-ups surfaced (not blocking)

- **The closing cross-cutting freeze audit (docs/28/29/35)** is now the only unreviewed cluster — this pass added two more sweep families for it (URL-plan prefixes; event-name drift), on top of the two from docs/58.
- The MOB (V2) reuse promise ("MOB consumes TD's backend") should cite D64's dual transport when the mobile pass runs — native apps = bearer clients.
- The credentials-email question (staff onboarding invite) stays carried: docs/06 §3.6's runbook creates the user in ZITADEL, whose own invite mail likely covers it — settle at contract freeze with FunderBlu ops.
- `console.operator_action` (docs/21 §4) is catalogued ext while its V1 controls are 2FA'd actions — a candidate V1 promotion at the freeze audit, same shape as D65 (left alone here: no V1 *screen* depends on consuming it).

Like every review pass, this changes V1 design detail only — **no PRD workbook
row was changed**.

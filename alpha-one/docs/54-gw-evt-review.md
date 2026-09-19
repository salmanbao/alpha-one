# 54 — GW + EVT: The Spine Deep Review (fourteenth pass)

> The fourteenth completeness pass: the **API Gateway + Event Backbone**
> (docs/04) — the "nervous system" every previously reviewed guarantee is
> *delivered* by: the middleware chain (tenant resolution → status gates →
> authn → authz → rate → quota → idempotency → correlation → hygiene), the
> transactional outbox → relay → Streams → consumers pipeline with its
> per-entity lanes, the durable event log, and the EVT-10 webhook ingress
> that is the truth path for CHK/KYC. Selection and gap policy were the
> owner's; mechanical inconsistencies were fixed in place; design gaps became
> decisions **D45–D47** — including the two oldest open contract TODOs in the
> repo (the success envelope and the URL plan). With this pass, every
> load-bearing Phase-1 module has been deep-reviewed.

## 1. Scope & method

- **Target:** docs/04 in full; seams to docs/02/44 (middleware steps 3–3.5),
  docs/47 (route-class gates), docs/05 (audit tiers + the D27 lesson),
  docs/08/12/13 (EVT-10 consumers), docs/28/29 (security + load numbers),
  `contracts/api/gw.md` (11 TODOs) + `api/evt.md` (5 TODOs),
  `contracts/errors/taxonomy.md` (gw/evt/request/webhook codes), docs/31.
- **Verdict:** the spine's architecture is the repo's strongest — the outbox
  invariant ("a domain event exists iff the tx committed"), single-writer
  relay with SKIP LOCKED, dedupe-by-`event_id` everywhere, and the C1
  envelope already carried `correlation_id` correctly. The findings were
  code-comment lies, one self-contradicting error-code pair, stale §4
  structure — and three long-standing owner decisions that had accumulated
  in the contract as TODOs.

## 2. Findings

| # | Sev | Finding | Disposition |
|---|---|---|---|
| F1 | **High** | **`events.seq`'s own comment contradicted its DDL — and repeated the exact mistake D27 removed.** The column is `GENERATED ALWAYS AS IDENTITY` (global append order, assigned by the INSERT from the single-writer relay), but the comment said "per-topic seq in app (**Redis INCR** on publish)": wrong mechanism (no Redis counter belongs in the durable path — the D27 lesson, docs/48), wrong scope (global, not per-topic). | Fixed mechanically (enforces D27 + the DDL): comment rewritten — global append order via IDENTITY, no Redis dependency; V2 CON replay addresses seq ranges. |
| F2 | Medium | **The same failure had two registered answers with different statuses**: §6.2 extended `gw.idempotency_conflict` **422** vs the V1 baseline `request.idempotency_conflict` **409** (GW-12) — identical condition, conflicting code AND HTTP. Same pattern for `evt.webhook_signature_invalid` duplicating baseline `webhook.signature_invalid`. | Fixed mechanically: extended rows marked **folded** with pointers to the V1 baseline codes (the docs/30 merged-registry rule). |
| F3 | Medium | **§3.6 invented an event name**: "Veriff decision → `kyc.provider_decision`" — a name that exists nowhere (docs/13's V1 events are `kyc.approved/rejected/…`). Same class as pass-11's `broker.created` drift: ingress-side naming that would leak into code. | Fixed mechanically: the ingress emits *the producer module's* V1 events; never an event name invented at the ingress. |
| F4 | Medium | **§3.2's outbox example used a non-catalog topic** (`"checkout.order_paid"` vs the catalog's `order.paid`) — a copy-paste trap in the most-copied code snippet in the repo. | Fixed mechanically. |
| F5 | Low | **§4 lacked the 4.1/4.2 structure every other module has** — the docs/31 generator's V1-baseline scan depends on it (the spine's telemetry events were classified extended *by luck*). | Fixed mechanically: §4.1 states **none** (the spine emits no V1 catalog events — provider truth is the producer modules' events; commands are EVT-20 table traffic); §4.2 carries the extended telemetry; `relay.lag` explicitly a metric, not an event. |
| F6 | Low | **§3.3 cited EVT-33 (a V2.0 row) for V1 pruning** — the pass-13 mis-tier class; pruning is a V1 *necessity* (the outbox must not grow unbounded). | Fixed mechanically: labeled a V1 necessity; EVT-33 formalizes the V2 retention ops. |
| F7 | Low | **`§02 §3.3` typo** (step 2) and the route-group table omitted the compose-only `internal` group that steps 2–3 rely on. | Fixed mechanically (docs/02 §3.3; `internal` row added). |
| F8 | Info | **The §11 degradation claims are self-contained**: "documented degradation matrix in 29" pointed at a matrix that lives here (29 carries the load numbers) — reworded. Verified consistent: rate-limit fail-open + authn-falls-to-PG + relay-pause are the documented failure posture; "trading continues when the relay is down" is real (bridge enforcement rides `account_commands` PG rows, not events — docs/08 §3.4). | Reworded + verified. |
| F9 | **Owner decision** | **The success envelope** — "working draft — owner decision" since the research; the oldest open contract TODO (api/gw.md), illustrated consistently by 11 modules' §8 examples and the shared OpenAPI envelope. | **D45 (owner: option A):** the working draft **`{data, meta{request_id, version, pagination{cursor, has_more}}}`** is **binding**; cursor pagination per GW-21. api/gw.md updated. |
| F10 | **Owner decision** | **The URL plan**: extended surfaces used un-grouped paths (`/v1/accounts`, `/v1/payouts`, `/v1/kyc`, `/v1/payments`) while GW-01 binds the groups (`/v1/trader/*`, `/v1/admin/*`, `/v1/console/*`, `/v1/webhooks/*`) — the "provisional until the URL-plan decision" note had propagated into four reviewed docs' §7.2s. | **D46 (owner: option A):** the GW-01 groups **are** the plan; docs/09/11/12/13 §7.2 normalized to `/v1/trader/*` and `/v1/admin/*`; the compose-only `/internal/*` group documented in the route table. |
| F11 | **Owner decision** | **V1 DLQ operations were undefined**: poison event → `dlq.{consumer}` + alert, but the CON list/retry screen is blueprint V2 and replay is V2 — a runbook hole on the async path. | **D47 (owner: option A):** the relay gains a **`dlq list/retry/purge` subcommand in V1** (ops SOPS identity; every action AUD-logged — the `security.replay` class); the rule: *no dead event without a retry or a recorded purge decision*. Blueprint step 2 exit criteria updated; CON screen stays V2. |
| F12 | Info | **All 16 contract TODOs resolved from binding text** (api/gw.md 11 + api/evt.md 5 — the largest single-pass TODO closure): rate-limit numbers, idempotency scope/TTL, correlation source/propagation, entitlement code+middleware, stream naming, relay batch/lag, retention windows, command retry numbers (docs/08 §3.4), envelope version policy. Zero genuinely-open TODOs remain in either contract. | Contracts refreshed with citations. |
| F13 | Info | **Verified clean:** the C1 envelope text in §8 was already correct (pass 9); the outbox/relay/consumer invariants match every consumer's assumptions (EVL's per-account lanes, the audit-applier's fail-closed semantics, EVT-05 idempotency); `provider_events` matches CHK/KYC's dedupe contract; the four route groups + status gates match docs/44/47; all `gw.*`/`evt.*`/`request.*`/`rate.*`/`tenant.*`/`auth.*`/`permission.*`/`module.*` codes registered; webhook security posture (signature-before-parse, 256 KB caps, SSRF guards) consistent with docs/28. | No action. |

## 3. Decisions (owner, 2026-09-19)

All presented and chosen interactively; registered in
`scripts/design-questions.json` (rendered into docs/37):

- **D45 — the working-draft success envelope is binding** (option A;
  alternative: flat `{data}` + pagination headers).
- **D46 — the GW-01 groups are the URL plan** (option A; alternative:
  resource-style paths with realm-by-token).
- **D47 — the relay `dlq` subcommand ships in V1** (option A; alternatives:
  alert-only with manual SQL; early CON screen).

## 4. Wiring (files touched by this pass)

Binding: docs/04 (§3.1/§3.2/§3.3/§3.5/§3.6/§4/§6.2/§7.2/§8/§9/§11/§16),
docs/09/11/12/13 (§7.2 URL normalization — D46), `contracts/api/gw.md` +
`api/evt.md` (all TODOs resolved), docs/31 (regenerated — §4 structure),
docs/37 (D45–D47). Register: `design-questions.json` (51 questions).
Generators: `aggregate_docs.py`, `build_prd_registers.py`.

## 5. Follow-ups (explicitly not done here)

1. `account-state.png`, `payout-state.png`, `kyc-state.png` re-renders
   (carried; the spine has no diagram PNG of its own — `event-bus.png` is
   unchanged by this pass).
2. Carried: strict example-validation gate (docs/35 §4); BRG-28 workbook row;
   credentials-email template (NOT-05); the three `api/pay.md` owner TODOs;
   the eight CHK/KYC owner TODOs.
3. The remaining unreviewed modules are thin-surface or trader-plane (RSK,
   NOT/DOC, TD/ADM/CON/ANA, OPS/DEVOPS, MIG) — the next pass should pick from
   these or begin cross-cutting freeze audits.

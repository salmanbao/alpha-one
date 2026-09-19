# Contract Pack

Status: DRAFT
Owner: TBD (per-module owners table below)
Freeze date: TBD

## Purpose

This repo contains the frozen interfaces every V1 module must conform to.

Derived from the `V1 Execution Sheet` of `Alpha One PRD.xlsx` (V1.0 and V1.1 releases only). Cross-referenced with `Integration Map`, `Build vs Buy Rules` (BVR-*), and `Out Of Scope`. Nothing here is final until contract freeze.

## Contents

- `api/` — API contracts per module (module-ID filenames: `auth.md`, `tenant.md`, …). Modules with no HTTP surface carry an explicit no-HTTP note with their events/internal contracts instead.
- `events/` — Event catalog and payload schemas in the EVT-03 envelope.
- `data/` — Data dictionary and SQL schemas with per-column Req ID citations.
- `errors/` — Error taxonomy (GW-18 envelope: code, message, correlation_id).
- `permissions/` — Permission registry in `resource.action` format (AUTH-13).
- `diagrams/` — Mermaid sources (`.md`) for each flow/state diagram; `.png` files are placeholders to render.

## Module owners

| Module | Contract file | Owner |
|---|---|---|
| AUTH | `api/auth.md` | TBD |
| TEN | `api/tenant.md` | TBD |
| GW | `api/gw.md` | TBD |
| EVT | `api/evt.md` | TBD |
| OPS | `api/ops.md` | TBD |
| BRG | `api/brg.md` | TBD |
| EVL | `api/evl.md` | TBD |
| LCC | `api/lcc.md` | TBD |
| CHK | `api/chk.md` | TBD |
| PAY | `api/pay.md` | TBD |
| KYC | `api/kyc.md` | TBD |
| NOT | `api/not.md` | TBD |
| DOC | `api/doc.md` | TBD |
| TD | `api/td.md` | TBD |
| ADM | `api/adm.md` | TBD |
| RSK | `api/rsk.md` | TBD |
| ANA | `api/ana.md` | TBD |
| AUD | `api/aud.md` | TBD |
| CON | `api/con.md` | TBD |
| LED | `api/led.md` | TBD |
| Events | `events/catalog.md` | TBD |
| Data | `data/dictionary.md` | TBD |
| Errors | `errors/taxonomy.md` | TBD |
| Permissions | `permissions/registry.md` | TBD |
| Diagrams | `diagrams/` | TBD |

## V1 scope

Modules in the V1 Execution Sheet (V1.0 + V1.1), with requirement counts:

| Module | Name | V1.0 | V1.1 | Total |
|---|---|---|---|---|
| AUTH | Auth & Identity | 14 | 0 | 14 |
| TEN | Tenant Management | 9 | 0 | 9 |
| GW | API Gateway | 7 | 0 | 7 |
| EVT | Event Bus & Webhooks | 7 | 0 | 7 |
| OPS | DevOps & Deployment | 12 | 0 | 12 |
| BRG | Trading Platform Bridge | 13 | 0 | 13 |
| EVL | Evaluation Engine | 13 | 2 | 15 |
| LCC | Account Lifecycle | 9 | 1 | 10 |
| CHK | Checkout & Billing | 10 | 3 | 13 |
| PAY | Payout System | 10 | 4 | 14 |
| KYC | KYC / Verification | 7 | 6 | 13 |
| NOT | Notification Service | 4 | 0 | 4 |
| DOC | Document Generation | 5 | 0 | 5 |
| TD | Trader Dashboard | 4 | 1 | 5 |
| ADM | Admin Panel | 1 | 0 | 1 |
| RSK | Risk Management | 2 | 1 | 3 |
| ANA | Analytics & BI | 1 | 1 | 2 |
| AUD | Audit & Compliance | 4 | 1 | 5 |
| CON | Platform Console | 3 | 0 | 3 |
| LED | Ledger & Accounting | 7 | 0 | 7 |
| **Total** | | **142** | **20** | **162** |

## Derived from

- Workbook: `Alpha One PRD.xlsx`
- Sheets used:
  - `V1 Execution Sheet` — sole source of requirements (162 rows: 142 V1.0, 20 V1.1; includes KYC-16 moved to V1.0 by Decision 5 and CHK-43/CHK-44 added by Decision 7, applied 2026-09-16). V2.0 and V3.0 rows ignored.
  - `Integration Map` — which tools serve which Req IDs (MetaApi, Veriff, Match2Pay, Interkasa, NOWPayments, Postmark, Cloudflare/R2, Better Auth, BullMQ, Puppeteer, self-hosted Postgres/Redis/Docker/PgBouncer/SOPS).
  - `Build vs Buy Rules` — build constraints per module (BVR-01..BVR-27).
  - `Out Of Scope` — exclusions honored throughout (no exactly-once delivery, no GraphQL, no multi-currency, manual payout execution in V1, polling not streaming, shared schema with tenant_id, etc.).
- Earlier drafts' Req IDs not present in the V1 Execution Sheet were NOT used; where a referenced row was missing, the artifact says so and marks the decision `TODO — needs owner decision`.

## Change process

All changes go through a PR. Contracts freeze at v1. After freeze, changes require review.

## Open contract questions

Aggregated from every artifact (each file also carries its own section — these become the working session agenda). Seven blocking questions were resolved 2026-09-17 — see **Resolved blocking questions** below:

1. Gateway URL plan per route group; success envelope and pagination convention (GW).
2. JWT claims structure and session/refresh rotation parameters (AUTH-07) — every module depends on this.
3. Role-to-permission binding table (AUTH-12 × AUTH-13) and whether trader self-actions need declared keys.
5. Entitlement enforcement point and error naming (`tenant.not_entitled` vs `module.not_entitled`) (TEN-08).
6. KYC expiry trigger — what moves a verification to EXPIRED in V1 (Out Of Scope mentions trigger-based re-verification at P2; no V1 row defines the trigger). (LCC-02 edge list, TERMINATED entry, and KYC timing enum resolved 2026-09-17 — see Resolved blocking questions.)
8. Whether `accounts` denormalizes `current_balance`/`current_equity` from the latest `equity_snapshots` row or all reads join to snapshots. Affects TD-03 (dashboard at-a-glance read), PAY-02 (available-profit calculation), and snapshot staleness checks (cites LCC-28 from the handoff doc — not a V1 row; confirm owner or drop). If denormalized, define the update trigger (sync worker write path).
9. EVL rule parameter schema, daily reset time/timezone, trailing-HWM basis enum values (EVL-04/07/08/29).
10. NOT-01's delivery mechanism for payout notification templates (event consumption vs direct call). (Payout state machine edges, `processing` owner, `failed`/`cancelled` entry resolved 2026-09-17 — see Resolved blocking questions.)
11. Payout method confirmation flow and cooldown (PAY-05; PAY-06 referenced by Out Of Scope is not a V1 row).
12. Coupon model and storage (CHK-02 reserves coupons; no CRUD/storage row exists).
13. Checkout session TTL duration (CHK-02/CHK-43 — lifecycle mechanism resolved by Decision 7; the window length is not).
15. Read model table list and KPI definitions (ANA-01, ANA-32).
16. Audit retention, PII minimization rule, and who may read/export audit logs (AUD-01/03/21; earlier-draft AUD-06 not in sheet).
17. Ledger account codes, refund/fee/adjustment posting triggers, and balance read path for analytics (LED-01..LED-08). (Delivery mechanism resolved 2026-09-17: event consumption — see Resolved blocking questions.)
18. Redis Streams naming/partitioning, relay parameters, outbox/event-log retention, command retry limits (EVT-01/02/08/20, BRG-10).
19. Sync interval and MetaApi cost budget; snapshot schema details (BRG-07/08; Integration Map pricing).
21. TD-05 objectives/progress endpoint — no V1 API row exposes evaluation progress to traders.
22. Diagram rendering tool; PNG generated in CI or committed.
23. Per-event mapping of the five kyc.* events to NOT-05's single "KYC result" template (which events fire it); what emits the "KYC invite" template.
24. Sub-state naming for cancelled/expired checkout sessions (CHK-43/CHK-44 mark sessions; no state enum is named in the sheet).

## Resolved blocking questions

Resolved 2026-09-17 from the working session's seven blocking answers. Every resolution traces to V1 Execution Sheet rows (V1.0/V1.1 only); V2.0 citations are explicitly deferred mechanisms:

- **Q4 — Impersonation (AUTH-16)**: no impersonation API exists in V1. AUTH-16 is a separation contract — the console cannot act inside a tenant at all. Enablement (TEN-16, CON-07, AUD-08) is V2.0. Files: `api/auth.md`, `api/con.md`, `permissions/registry.md`, `api/aud.md`.
- **Q6 — LCC-02 edges / TERMINATED / KYC timing**: full same-account edge list applied; TERMINATED is terminal-only; spawn edges via `parent_account_id`; KYC timing enum `{at_creation, after_evaluation, at_first_payout, skipped}`. Files: `api/lcc.md`, `diagrams/account-state.md`, `data/dictionary.md`, `data/schemas/accounts.sql`. Note: the AWAITING_ACTIVATION hold-and-pay flow cites LCC-08 (V2.0) — PRD confirmation flagged in the open list and `api/lcc.md`.
- **Q7 — Phase semantics**: per-challenge ordinal, `CHECK (phase >= 1)`; funded stage is `status = FUNDED` and the funded account continues the ordinal. Files: `data/dictionary.md`, `data/schemas/accounts.sql`, `diagrams/account-state.md`.
- **Q10 — Payout state machine**: V1 edges `requested → eligibility checked → pending approval → approved|rejected → paid`; `processing`/`failed`/`cancelled` reserved for V2 (PAY-24/PAY-18/PAY-17) with no V1 entry path. Files: `api/pay.md`, `diagrams/payout-state.md`.
- **Q14 — Webhook tenant routing**: per-tenant subdomain (GW-02, TEN-02); provider webhook URLs provisioned per tenant. Files: `api/chk.md`, `api/kyc.md`.
- **Q17 — Ledger delivery**: event consumption, no synchronous calls — LED-04 ← `order.paid`, LED-07 ← `payout.approved`, LED-08 ← `PayoutPaid`; dedupe by source event id. Files: `api/led.md`.
- **Q20 — `bot` lane**: no `bot` lane in V1; OPS-01's reference is a V2 forward reference (Telegram bot, NOT-09). V1 worker topology: api, worker-realtime, worker-batch, outbox-relay. Files: `api/ops.md`, `diagrams/lanes.md`.

## Cross-file drift

Working-session items found by re-audit. Listed deliberately — NOT auto-fixed:

### Real gaps requiring contract changes

1. `payout.method.read` is declared in `permissions/registry.md` but no endpoint in `api/pay.md` references it (no read-methods endpoint exists — PAY-05 defines save/confirm only).
2. `roles`, `permissions`, `role_permissions`, `user_roles` tables have no writing endpoint in any `api/*.md` (role/permission CRUD flagged as an open question in `api/auth.md`).
3. `risk_signals` table (RSK-01) has no V1 producer row and no endpoint that creates a signal.

### Informational (design, not drift)

4. `PhaseAdvanced`, `Resumed`, and `Suspended` events are referenced by no endpoint; their only solid consumer is ANA-01 read models (`Suspended`'s PAY-04 consumption mechanism is itself unresolved).
5. `notifications`, `notification_templates`, `documents`, `ledger_accounts`, `journal_entries`, `journal_lines`, `ledger_balances`, `equity_snapshots`, `trades`, `positions`, `account_state_history`, `outbox`, `event_log`, `command_queue`, `audit_entries` are written only by workers/internal services, not by any endpoint — expected for worker modules, listed for completeness.
6. RESOLVED 2026-09-16 (Decision 7): `checkout_sessions` lifecycle — CHK-43 (scheduled expiry worker + `checkout.session.expired`) and CHK-44 (`DELETE /v1/checkout/sessions/{id}`) close this gap; `api/chk.md` and `events/catalog.md` now carry both. Remaining sub-item: session state naming (open question 24).
7. NOT-01's delivery mechanism for payout notification templates is unspecified (NOT-01 says event consumption; no V1 row ties payout.approved / payout.rejected to the "payout approved" / "payout rejected" templates) — see `events/catalog.md` open questions.

## Resolved decisions

Applied 2026-09-16 19:06:13.720000 UTC — PRD Change Log entries `APPLY_DECISION_5` / `APPLY_DECISION_6` / `APPLY_DECISION_7` (script `applyDecisions567`). The resolutions are final; the contract pack was aligned to them on 2026-09-16.

- **Decision 5 — KYC events (option a)** → KYC-05 (amended: emits `kyc.submitted`, `kyc.approved`, `kyc.rejected`, `kyc.expired`, `kyc.resubmission_requested` through the outbox), KYC-16 (moved V2.0 → V1.0 / V1-Core). The five `kyc.*` events are V1 scope; the catalog's former "Deferred to V2" section is removed. Files: `events/catalog.md`, `events/payloads/kyc.*.v1.json`, `api/kyc.md`, `api/not.md`, `diagrams/event-bus.md`.
- **Decision 6 — PayoutPaid producer** → PAY-12 (producer, emits `PayoutPaid` through the outbox), LED-08 (consumer, settles the obligation). Files: `events/catalog.md`, `events/payloads/PayoutPaid.v1.json`, `api/pay.md`, `api/led.md`, `api/doc.md`, `diagrams/payout-flow.md`.
- **Decision 7 — Checkout session lifecycle (option c: both)** → CHK-43 (new, P0, V1.0: scheduled expiry worker, releases coupon/price holds, emits `checkout.session.expired` via outbox), CHK-44 (new, P1, V1.0: `DELETE /v1/checkout/sessions/{id}`, identity-scoped per Decision 2 — no permission key). Files: `api/chk.md`, `events/catalog.md`, `events/payloads/checkout.session.expired.v1.json`, `data/dictionary.md`, `data/schemas/orders.sql`, `errors/taxonomy.md`, `diagrams/purchase-flow.md`.

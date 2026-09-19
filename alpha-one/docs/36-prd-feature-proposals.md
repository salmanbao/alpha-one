# 36 — PRD Feature Proposals & Release Roadmap

> Generated 2026-09-19 by `scripts/build_prd_registers.py` from
> `scripts/prd-workbook.json` (parsed from `uploads/Alpha One PRD.pdf`,
> the *Feature Proposals* sheet). Do not edit by hand: re-run the script after a PRD
> change, exactly like `scripts/prd-backlog.json`.
>
> This document is the funnel between *ideas* and *the backlog*: §1 lists every proposal as submitted, §2 is the release roadmap with its gates. A proposal becomes buildable only when it is promoted into the backlog — the promoted Req ID is recorded in the PRD's `Promoted Req ID` column.


Proposals: **14** (New 14). None are promoted into the backlog as of the workbook snapshot.

## 1. Proposals

| ID | Submitted | Domain | Module | Feature | Cx | Pri | Release | Status | Promoted Req |
|---|---|---|---|---|---|---|---|---|---|
| `PROP-0001` | 2026-09-15 23:15:44 | D2 — Trader Experience | TD — Trader Dashboard | News feed widget | S | P2 | V2.0 | New | — |
| `PROP-0002` | 2026-09-15 23:16:16 | D2 — Trader Experience | TD — Trader Dashboard | Watchlist widget | S | P2 | V2.0 | New | — |
| `PROP-0003` | 2026-09-15 23:16:36 | D2 — Trader Experience | TD — Trader Dashboard | Order tracking widget | S | P2 | V2.0 | New | — |
| `PROP-0004` | 2026-09-15 23:17:12 | D1 — Core Trading Engine | EVL — Evaluation Engine | Trading hours restriction rule | S | P1 | V2.0 | New | — |
| `PROP-0005` | 2026-09-15 23:17:37 | D1 — Core Trading Engine | EVL — Evaluation Engine | News event trading lock | M | P1 | V2.0 | New | — |
| `PROP-0006` | 2026-09-15 23:18:01 | D2 — Trader Experience | KYC — KYC / Verification | AML / sanctions / PEP screening | L | P1 | V2.0 | New | — |
| `PROP-0007` | 2026-09-15 23:18:34 | D5 — Ecosystem & Growth | CMP — Competition / Gamification | Loyalty points and redemption | M | P2 | V3.0 | New | — |
| `PROP-0008` | 2026-09-15 23:19:00 | D2 — Trader Experience | MOB — Mobile App | White-label mobile app packaging per tenant | L | P1 | V3.0 | New | — |
| `PROP-0009` | 2026-09-15 23:19:31 | D1 — Core Trading Engine | BRG — Trading Platform Bridge | Volumetrica adapter | L | P2 | V3.0 | New | — |
| `PROP-0010` | 2026-09-15 23:20:12 | D1 — Core Trading Engine | BRG — Trading Platform Bridge | Quantower adapter | L | P2 | V3.0 | New | — |
| `PROP-0011` | 2026-09-15 23:20:29 | D1 — Core Trading Engine | BRG — Trading Platform Bridge | ATAS adapter | L | P2 | V3.0 | New | — |
| `PROP-0012` | 2026-09-15 23:21:02 | D2 — Trader Experience | CHK — Checkout & Billing | PSP catalog expansion framework | M | P1 | V2.0 | New | — |
| `PROP-0013` | 2026-09-15 23:21:26 | D2 — Trader Experience | TD — Trader Dashboard | Trader portal UI localization | M | P2 | V2.0 | New | — |
| `PROP-0014` | 2026-09-15 23:21:54 | D5 — Ecosystem & Growth | CMS — Website / CMS | Freeform landing page builder | L | P2 | V3.0 | New | — |

### 1.1 Why each was raised

- **`PROP-0001` News feed widget** — Teammate identified news feed; current backlog only has economic calendar TD-30.
- **`PROP-0002` Watchlist widget** — Missing; complements economic calendar and charts.
- **`PROP-0003` Order tracking widget** — TD-08 covers positions and closed trades, not working orders.
- **`PROP-0004` Trading hours restriction rule** — Missing; competitor feature map includes trading hours restrictions.
- **`PROP-0005` News event trading lock** — EVL-14 detects/flags; no auto-lock.
- **`PROP-0006` AML / sanctions / PEP screening** — Currently out of scope; teammate includes AML checks.
- **`PROP-0007` Loyalty points and redemption** — CMP-09/10 cover badges/XP, not points/redemption.
- **`PROP-0008` White-label mobile app packaging per tenant** — Current MOB has native apps but not per-tenant packaging; out of scope currently.
- **`PROP-0009` Volumetrica adapter** — Competitor feature map lists Volumetrica; backlog lacks it.
- **`PROP-0010` Quantower adapter** — Missing; competitor feature map lists Quantower.
- **`PROP-0011` ATAS adapter** — Missing; competitor feature map lists ATAS.
- **`PROP-0012` PSP catalog expansion framework** — Teammate mentions 80+ PSP integrations; current backlog has few adapters.
- **`PROP-0013` Trader portal UI localization** — TEN-07/NOT-31 cover locale and notifications, not full UI i18n.
- **`PROP-0014` Freeform landing page builder** — Current CMS has constrained editor; out of scope freeform.

## 2. Release roadmap and gates

| Release | Theme | Cashflow-critical gate | Gate status | P0 | P1 | P2 | Total | Status | Notes |
|---|---|---|---|---|---|---|---|---|---|
| **V1.0** | TBD | YES | Not Met | 146 | 8 | 0 | 154 | Planned | Auth, Tenant, Bridge, Eval, Lifecycle, Checkout, KYC, Payout, Ledger, Audit |
| **V1.1** | TBD | NO | Not Met | 11 | 10 | 0 | 21 | Planned | — |
| **V2.0** | TBD | NO | Not Met | 175 | 348 | 107 | 630 | Planned | Completes the module set: auth hardening, tenant config depth, bridge expansion, checkout depth, payout hardening, risk detectors, notifications, documents, dashboards, admin operations, support, analytics, audit, ledger, console, migration tooling |
| **V3.0** | TBD | NO | Not Met | 26 | 76 | 112 | 214 | Planned | AFF, CMS, CMP, BIL, SDK, DVP, PLT, CS, TRD modules land here |

## 3. Reading the roadmap

- **A gate status of `Not Met` is the default until the release ships** — the PRD records the gate, not progress against it. The delivery order that satisfies the V1.0 gate is `docs/99-development-phases.md`.
- **V1.0 must ship every P0 money-path item** (take money → provision account → evaluate → pay out). P1 items inside a release are pulled in only when the P0 set is green; P2 items are opportunistic.
- Proposals (§1) do **not** count toward a release total until the `Promoted Req ID` column is filled and the row appears in the master backlog (`scripts/prd-backlog.json`).

## 4. Open items

- 14 proposals are un-reviewed for promotion (status `New`); the promotion board should either promote each into a release or reject it with a note.
- V1.0/V1.1 gates are `Not Met` and are re-evaluated at each release review (`docs/99-development-phases.md` §Gates).

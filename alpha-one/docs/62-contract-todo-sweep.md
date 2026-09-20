# 62 — The Contract-TODO Backlog Sweep (twenty-first pass)

> The twenty-first completeness pass sweeps the **open contract
> questions** — the owner-TODOs scattered across the `contracts/api/`
> pack that every prior review left deliberately open. With the module
> reviews done and the freeze audit passed, these 53 questions were the
> last holes in the contract pack the code implements. The method: for
> each TODO, either **resolve by citation** (the binding text already
> answers it — the registry, the taxonomy, a module doc's section, a
> ratified decision) or **put it to the owner**. The result: **49
> resolved by citation, 4 decided (D72–D75), zero TODOs remaining**.

Status: REVIEW — 53 questions closed (49 cited, 4 decided D72–D75)
Owner: TBD (BE-1, BE-2)
Version: v1
Last updated: 2026-09-20

---

## 1. Scope & method

- **Corpus:** all 12 contract files carrying `TODO — needs owner decision` (evl 13, aud 9, chk 7, led 6, lcc 5, con 4, pay 3, tenant 2, brg 2, kyc 1, ana 1; the adm hit was an already-resolved strikethrough).
- **Citation sources used:** the permission registry + roles.yaml (keys that were already registered and bound), docs/30 (codes already registered), docs/09 §3.1 (the rulepack block: HWM basis `equity|balance`, broker-midnight `day_start`, phase-level `min_trading_days`), docs/05 (the §5 chart slugs, the §3.4 balances projection, the §14 audit tiers), docs/07 (the §5.1 matrix, the V1/V2 lineage split), docs/12 §3.1/§3.2 (the frozen price, the adapter normalization), docs/13 §3.3 (the verified-identity record), docs/19 §3.1 (the feed map), docs/21 §3.1/§3.3–§3.5 (the V1 console scope, the gated actions), docs/55 §4.7 (the entitlement gate), and the ratified decisions D14, D25, D36, D40, D61, D66.

## 2. What the sweep showed (no action needed)

- **The registry work paid off:** a large share of the "TODOs" were contract lines written *before* the D14 key-ratification and the role bindings landed — the answer already existed in `registry.md`/`roles.yaml` (EVL's `challenge.write`/`ruleset.write`, AUD's `audit.read`/`audit.export`, LCC's `account.read`/`account.suspend`).
- **The module reviews had done their job:** every code the contracts flagged as "rule not in sheet" turned out to be registered with its rule documented (`account.terminal_state`, `account.not_active`, `module.unknown` — all V1 rows in docs/30 with their owning docs' matrices).
- docs/09's §3.1 rulepack block silently answered six EVL questions (parameters, reset time, HWM basis, auto-advance level) — written in the tenth pass, never back-propagated to the contract.

## 3. The four owner decisions

- **D72 (payout sub-reasons):** `payout.ineligible` carries a **closed named enum** — `kyc_not_approved`, `min_trading_days`, `consistency`, `trading_day_threshold`, `first_payout_delay`, `next_payout_date`, `min_amount`, `max_amount`, `account_status`, `risk_hold`; extended only at freeze. `payout.kyc_required` stays a sub-reason (one shape for all failures — no dedicated top-level code).
- **D73 (method confirmation, PAY-05/06 V1.1):** **confirm-once** — a new method version must be confirmed by the trader in TD before its first payout; the registered 72-h cooldown guards changes afterwards; no per-payout re-confirmation.
- **D74 (credential delivery, BRG-06):** **no automated credential email in V1** — staff copy credentials from the ADM detail view (sensitive-read audited, the KYC-doc pattern) and deliver through the firm's own channel; NOT-05 gains no template (the D61 set stands); automated delivery is a V2 template with its own security design. (Carried twice — the bridge pass and the NOT pass — now settled.)
- **D75 (checkout catalog):** coupons = tenant-managed catalog rows (code, %/flat off, usage limit, expiry) under the `challenge.write` family, validated + usage-decremented at session reservation; **add-ons defer to V2** (TD-09's mention is the V2 catalog); numbering `ORD-{TENANT}-{YY}-{seq6}` / `INV-{TENANT}-{YY}-{seq6}`.

## 4. The cited resolutions (49 — highlights)

| Contract | Resolved by |
|---|---|
| evl ×13 | registry keys; the `evaluations` dedupe (account_id, tick_event_id); the §3.1 rulepack = the validation set + params + HWM basis + broker-midnight reset; docs/12 §3.1's frozen price for the pricing-edit interaction; the keep-version/re-bind-with-reason policy (EVL-34, never automatic); the §5.1 matrix for `account.terminal_state`; PAY-03 owns min-days/consistency; the EVL-owned audit tables |
| aud ×9 | the D14-era keys + role bindings; the docs/05 §9 filter columns; the 7-yr retention; the docs/28 §4 PII rule; CON-13's CSV export; V1 console audit visibility = none (D25; the V2 task-5 surface) |
| chk ×7 | D75 (coupons, add-ons, numbering); the adapter normalization (docs/12 §3.2) for the provider webhook shapes |
| led ×6 | the §5 chart slugs; D40's refund posting; the LED-08 fee line; no manual adjustment surface in V1; the §3.4 balances projection; the audit-export path for V1 CSV |
| lcc ×5 | `account.read` (staff) vs the `self` route (trader); the §5.1 suspend guards; `parent_account_id` only in V1 (phase_history = V2); staff suspend via `account.suspend` |
| con ×4 | the 15-min idle (D66); the step-up list = the actions docs/21 §3.3–§3.5 gate; the §3.1 V1 scope |
| tenant ×2 | the registered `module.unknown`; the GW step-6 entitlement gate (docs/55 §4.7) |
| brg ×2 | D36 (force-sync stays worker-internal); D74 |
| kyc ×1 | the docs/13 §3.3 record + the name-match rule |
| ana ×1 | the docs/19 §3.1 feed map |

## 5. Wiring map

| File | Change |
|---|---|
| contracts/api/ evl, aud, chk, led, lcc, con, pay, tenant, brg, kyc, ana | All 53 TODO lines resolved with citations or the D72–D75 rulings — **zero open questions remain in the pack** |
| docs/11 | The D72 sub-reason enum (§6 row); the D73 confirm-once rule (§3) |
| docs/08 | The D74 delivery path (§2 step 4 + the §16 blueprint row) |
| docs/12 | The D75 coupon model + numbering scheme (§9 DDL block) |
| scripts/design-questions.json | D72–D75 (79 entries) |

## 6. What this closes (and what genuinely remains)

- **The contract pack is now TODO-free:** every question is either answered
  by binding text or decided. The docs/99 §12 rule stands — canonical JSON
  values are fixed at the contract-freeze session, but no *open decision*
  blocks it.
- **Still open by design (tracked, not contract TODOs):** the V2/V3
  design-level blocks in the module docs; the PK data-residency and
  audit-hash-chain timing items (docs/28 §13); the PNG re-renders.
- **Frozen book status after 21 passes:** 61 docs, 79 recorded decisions,
  a TODO-free contract pack, and a green freeze audit.

Like every review pass, this changes V1 design detail only — **no PRD workbook
row was changed**.

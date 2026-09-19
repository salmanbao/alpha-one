## 2. Domain: How a Prop Firm-as-a-Service Actually Works

### 2.1 Business model

A prop firm sells **performance-based access to firm capital**:

1. A trader **pays a fee** to enter an evaluation (challenge) — typically $100–$1,500.
2. The trader gets a **simulated (demo) or firm-controlled account** at a broker, with a fixed starting balance (e.g., $100k virtual).
3. The trader must hit a **profit target** (e.g., +8–10%) within a window (often unlimited days), while respecting **risk rules** (max daily loss 4–5%, max overall loss 8–10%, minimum trading days 3–5, sometimes news/weekend/overnight restrictions).
4. Pass → **verification** (second, easier phase) → **funded account**: the trader trades a real firm capital account, the firm keeps a mirror/hedge account to neutralize market risk, and the trader receives a **profit split** (commonly 70–90%) via periodic payouts.

Revenue for the firm = fees (the majority of revenue for most prop firms; pass rates are typically 1–5% at the funded stage) plus carry on funded accounts. The platform's job is to make this *verifiable, auditable, and operable at scale* for many firms simultaneously.

### 2.2 The prop firm lifecycle (state machine)

{{DIAG:03-trader-lifecycle}}

The state machine above is **the** core domain model. Rules engine verdicts are the *only* inputs that may transition it (plus expiry timers and manual risk actions). This is enforced technically: no service other than the challenge state machine writes these states, and every transition is an event with an idempotency key.

### 2.3 Account topology

| Phase | Trader account | Hedge/mirror | Nature |
|---|---|---|---|
| Challenge / Verification | Demo or firm-managed account at broker | Optional (some firms hedge evals) | Virtual capital; broker never sees real money for the trader |
| Funded | Real account with firm capital (deposit = account size) | Real mirror account, 1:1 (or ratio), same broker | Trader's PnL = firm's PnL on funded account − hedge account; firm risk ≈ 0 after split cost |

Key consequences for the bridge:

- **Same broker cluster** for funded + hedge (co-location, shared symbol tables, identical fills where possible).
- The **position/hedge sync service** must mirror every trade with fill-aware tolerance and drift alerts (this is where firms silently lose money if done poorly: slippage asymmetry, partial fills, spreads differing by seconds).
- **Evaluation accounts may be "virtualized"**: balance lives in *your* database, the broker account may just be a $0 demo used for execution and marks. The bridge therefore must support **platform-authoritative balances** (your ledger) alongside **broker-attested execution**. This is the single biggest reason to keep an event-sourced ledger rather than trusting `AccountInfo()` alone.

### 2.4 Money flows (who pays whom)

```
Trader ──fee──▶ Tenant (prop firm) ──(via you, the PFaaS)──▶ platform revenue share
Trader ◀──payout (profit split)── Tenant ◀──firm capital PnL── broker (funded+ hedge accounts)
Tenant ──broker margin/fees──▶ broker
```

The PFaaS platform is a **b2b billing layer**: tenants pay you (revenue share / per-active-trader / infra fee), and you give them tenant-scoped services. The payout service (Section 6.9) computes *trader* payouts on behalf of the tenant; the billing service computes *tenant* invoices from platform usage (active traders, messages processed, storage).

### 2.5 Rule taxonomy (what the engine must evaluate)

| Rule | Typical expression | Evaluation basis | Edge cases |
|---|---|---|---|
| Max daily loss | 4–5% | **Equity** at any moment (intraday) or at EOD | Timezone of "day"; open-position marks; does equity recovery before EOD count? (config: intraday-breach vs EOD) |
| Max overall loss | 8–10% | Equity vs starting balance (**static**) or vs high-water mark (**trailing**) | HWM update frequency; equity-based HWM can be hit intraday by marks |
| Profit target | +8–10% | Equity or balance; realized-only options | Target met while equity is below after a partial close; multiple targets for scaling |
| Min trading days | 3–5 days | Days with ≥ 1 closed trade | One trade at 23:59; timezone; does a rolled day with only swaps count? (config) |
| Time limit | 30/60/∞ days | Calendar | Paused days during outages (policy decision, must be explicit) |
| News trading | Block N min before/after red events (per instrument class) | Order placement time vs economic calendar | Calendar source reliability; instrument impact mapping; pre-positioned orders (position opened *before* window must be flagged, not just new orders) |
| Weekend hold | No positions held into Friday close / no Friday opens | Position state at weekly cutoff | Swap charges over weekend; "close all" automation at cutoff |
| Overnight rule (funded) | No holding overnight / no holding past X hours | Position age vs day boundary | Split-day policies per tenant |
| Spread cap | Reject order if spread > X pips | Live quote at order_intent | Quote staleness; per-symbol table |
| Volume caps | Max volume, max open positions, max per-symbol exposure | Account aggregate | Hedged pairs counted net or gross (config) |
| Consistency / strategy | No martingale, no grid, no stop-hunting (advanced) | Pattern detection over history | ML-based, scored not hard-failed; evidence packs |

Every rule is **data, not code**: a versioned, tenant-scoped JSON rule pack (Section 6.2) evaluated by one engine. This is what makes tenants self-service and makes disputes replayable.

### 2.6 What "as-a-service" adds: the tenant dimension

- **Tenancy**: every row, key, queue partition consumer group, metric, and audit record carries a `tenant_id`.
- **Self-service**: rule packs, pricing, branding, payout schedules are tenant-editable within plan limits (admin UI in TypeScript, validated against the schema).
- **Metering**: the platform bills tenants on usage; the bridge's message counters are the metering source.
- **Independence**: a tenant can leave with its data (export pipeline to object storage) — retention and export are contractual, so design them in from day one.

---

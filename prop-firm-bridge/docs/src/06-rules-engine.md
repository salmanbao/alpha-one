## 6. The Rules Engine

### 6.1 Position in the system

{{DIAG:13-rules-engine}}

The rules engine is a **stateless, partition-ordered consumer** of `bridge.events` that maintains, per account, a small value-semantic state and a versioned rule pack, and emits `(new_state, verdicts)` for each event. "Stateless" means: no local persistence — state lives in Redis (hot) / PG (durable), and **any event stream prefix can be re-applied from scratch to reconstruct the exact state**. That property — *replayability* — is the foundation of disputes resolution, rule-pack migrations, backfills, and audits.

### 6.2 Rule packs: data, versioned, immutable

```jsonc
// rule_packs v12 — tenant "acme-firm", scope "challenge_100k"
{
  "pack_id": "acme:challenge:100k:v12",
  "currency": "USD",
  "start_balance": 100000,
  "day": { "timezone": "Europe/London", "basis": "equity", "breach": "intraday" },
  "rules": {
    "max_daily_loss_pct": 4.0,
    "max_overall_loss_pct": { "mode": "static", "value": 8.0,
                              "mode_alt": "trailing", "note": "trailing = HWM-based" },
    "profit_target_pct": 10.0,
    "min_trading_days": 4,
    "time_limit_days": null,
    "news": { "enabled": true, "block_minutes_before": 5, "block_minutes_after": 5,
              "tiers": ["high"], "instruments": "FX_majors,indices",
              "source": "economic-calendar:v3", "pre_positioned": "flag" },
    "weekend": { "mode": "no_hold", "cutoff": "Fri 21:00 Europe/London", "action": "close_all" },
    "overnight": { "enabled": false },
    "spread_max_pips": { "EURUSD": 2.5, "default": 6.0 },
    "volume_max": 10.0, "open_positions_max": 20,
    "allowed_symbols": ["*"], "denied_symbols": ["XAUUSD_limit_1.0"]
  }
}
```

Rules are **compiled once per pack version** into a typed plan (Rust); the hot path executes the plan, not JSON. Pack changes create a new version; accounts pin their pack until the next rollover boundary (mid-day swaps are a classic source of "but it was different when I signed up" disputes — avoid them by policy, not by cleverness).

### 6.3 State model (per account)

```rust
struct AccountState {
    account: AccountId,
    pack: PackVersion,
    balance: Decimal,            // platform ledger (authoritative for business math)
    equity: Decimal,             // broker-attested marks (authoritative for market value)
    high_water_mark: Decimal,    // trailing-DD mode
    day: DaySnapshot,            // {date, start_equity, start_balance, traded: bool, verdicts: bool}
    open_positions: Vec<Position>,
    day_counter: u32,            // trading days counted
    flags: FlagSet,              // halted, outage_window, integrity_alerted, …
    seq_applied: u64,            // last applied event seq (crash/replay pointer)
}
```

Arithmetic uses **decimal with fixed 8-dp** (never f64 for money); marks come from broker-attested prices; a one-cent drift between platform ledger and broker balance is an *alert*, a one-dollar drift is a *page*.

### 6.4 Evaluation semantics (the exact math, because it will be litigated)

For event `e` at broker-time `t` with resulting marks:

1. **Intraday equity breach (config `breach: intraday`)**: `equity(t) < day.start_equity * (1 − max_daily_loss_pct/100)` → `BREACH(daily_max_loss)` **immediately**, even if equity recovers later that day. (Some tenants run `eod`: evaluate only at rollover with the day's worst equity — support both, default intraday.)
2. **Max overall, static**: `equity(t) < start_balance * (1 − max_overall_loss_pct/100)` → `BREACH(max_overall_loss)`.
3. **Max overall, trailing**: HWM updated on every *realized* close (and at rollover) using `balance + closed_pnl_to_date` (config: equity-based HWM is aggressive and mark-sensitive — tenant choice); breach when `equity(t) < HWM * (1 − pct/100)`.
4. **Profit target**: `equity(t) ≥ start_balance * (1 + target/100)` **and** `day_counter ≥ min_trading_days` → `TARGET_REACHED` (evaluation) / `PAYOUT_ELIGIBLE` (funded, per tenant schedule).
5. **Min days**: incremented at rollover when `day.traded == true` (a day with at least one *closed* deal at broker_ts inside the day boundary).
6. **News block**: an `order_intent` (or opened position) with `t` inside `[event.start − before, event.end + after]` for an in-scope tier/instrument → `BREACH(news_rule)` (evaluation) or `order rejected + evidence` (funded, config). `pre_positioned: flag` records positions opened *before* the window with an audit marker rather than failing (tenant choice between `flag`, `fail`, `close`).
7. **Weekend hold**: at cutoff, any open position → controlled `close_all` + `BREACH(weekend)` if close generates a loss beyond the allowed swap buffer (config; default: breach only on new violations, existing-positions-closed-by-firm is penalized per tenant policy).

**Every rule result is a structured record** — rule id, input values (exact decimals, pack version, event id, broker_ts) — so a verdict is a *proof*, not an assertion. Dispute resolution = replay the stream to the disputed event, diff against the trader's terminal, done.

### 6.5 Where enforcement happens (three layers, three speeds)

| Layer | Latency budget | Enforces | Why |
|---|---|---|---|
| **L0 client (EA)** | 0 ms (cached pack) | Hard halts, weekend cutoff, spread cap, volume caps | Trader UX: a halted account should be *immediately* blocked in the terminal without a round trip; the cached pack is pushed via `set_param` |
| **L1 bridge edge** | < 8 ms p99 | `order_intent` pre-check against live pack version + halt flags + quote state | Authoritative *at order time*; reject before execution to avoid broker-side fills that must be unwound |
| **L2 rules engine** | < 150 ms p99 | Everything (post-fill marks, drawdowns, targets, rollover) | The financial truth; L0/L1 are optimizations and *never* substitutes |

Design invariant: **L0 and L1 may be slow/stale; L2 is always right.** L0/L1 only *tighten* (they can refuse early), L2 *decides*. An L1 miss that L2 later breaches is still a valid breach; an L1 false-allow is never a problem because L2 catches the mark.

The full close → verdict → control round trip, including the breach path that halts the trader's terminal:

{{DIAG:07-close-and-verdict}}

### 6.6 Rollover (daily close of books)

{{DIAG:09-daily-rollover}}

- Trigger: cron at tenant timezone midnight, sharded by `(tenant, account)` with a **distributed lease** (Redis `SET NX PX`) — exactly one worker per account per day, unique constraint `(account, date)` on `day_snapshots` makes double-runs impossible.
- Per account: finalize `day.traded`, compute day PnL, trail HWM (if trailing pack), increment `day_counter`, check EOD-basis rules, write new `day_snapshots` row, emit `RolloverCompleted` + verdicts, hash-chain the audit row.
- Late-arriving events (fill recorded with `broker_ts` in the *previous* day, delivered after rollover): applied to the previous day via a **retroactive apply** path that re-derives both days' snapshots and, if a breach changed, emits a correction verdict. The engine must treat "time" as `broker_ts`, and "processing order" as arrival order — the two are different, and conflating them is the #1 rules-engine bug in this industry.

### 6.7 Rule-pack migration & replay

When a tenant changes rules (or you fix a bug): (1) publish new pack version; (2) engine pins per-account switchover at the next rollover (or immediate, per tenant config); (3) **migration verification job** re-evaluates a sample of accounts under old and new packs over the trailing 30 days and reports the diff before activation. Because evaluation is pure, this is a batch job, not a migration script.

### 6.8 Funded accounts: the engine's second mode

Same engine, different pack scope: `funded` packs add **payout-schedule rules** (e.g., "first payout day 14, then every 14 days with ≥ $200 withdrawable"), **consistency rules** (tenant-optional: max consecutive losing days, max daily volume, consistency score), and **hedge-drift rules** (mirrored-position divergence beyond tolerance → alert/suspend). Breaches on funded accounts do not "fail" — they produce `SUSPEND`/`TERMINATE` verdicts with a manual-review gate (Section 7.6) because the stakes are real money.

### 6.9 Payout computation (the numbers the engine feeds)

```
tradeable_pnl        = funded_equity_now − deposit − locked_margin
trader_share         = tradeable_pnl * split_pct          (e.g. 80%)
fee_deductions       = Σ broker commissions/swaps on funded account (tenant policy: pass-through or absorb)
fx_adjustment        = if payout_ccy ≠ account_ccy: mid-rate at T-1 (published schedule)
available            = max(0, trader_share − fee_deductions − fx_adjustment)
```

Computed by the payout service **from engine-persisted marks + the ledger** (never from a live broker poll at click time — snapshot at request, re-verify at settlement). Approval workflow (auto below threshold, two-officer above) and the hash-chained audit trail are in Section 8.6. End-to-end:

{{DIAG:11-payout}}

---

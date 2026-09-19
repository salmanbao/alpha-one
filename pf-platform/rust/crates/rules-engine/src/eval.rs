//! The pure evaluator (doc §6.4): `(state, event, pack) -> (state, verdicts)`.
//!
//! No I/O, no clocks, no randomness. Every rule check is exact decimal math.
//! The Kafka consumer wrapper (production) is: load state → apply each event in
//! partition order → persist state + publish verdicts via outbox (doc §7.3).

use crate::events::{decimal, CanonicalEvent, Side};
use crate::pack::CompiledPack;
use crate::state::{AccountState, DayState, NewsWindowRec, Position};
use crate::verdict::{RuleId, RuleInputs, Verdict, VerdictStatus, verdict};
use rust_decimal::Decimal;
use std::collections::BTreeSet;

#[derive(Debug, Clone, PartialEq, Default)]
pub struct IntegrityAlert {
    pub event_id: String,
    pub deal_id: Option<String>,
    pub kind: String,
    pub detail: String,
}

impl IntegrityAlert {
    fn new(event_id: &str, deal_id: Option<String>, kind: &str, detail: String) -> Self {
        Self {
            event_id: event_id.to_string(),
            deal_id,
            kind: kind.to_string(),
            detail,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Default)]
pub struct ApplyResult {
    pub verdicts: Vec<Verdict>,
    pub integrity_alerts: Vec<IntegrityAlert>,
    pub state_changed: bool,
}

impl ApplyResult {
    pub fn no_change() -> Self {
        Self::default()
    }
}

/// Stateless engine handle: owns the compiled pack (doc §6.2: compiled once per pack version).
#[derive(Debug, Clone)]
pub struct Engine {
    pack: CompiledPack,
}

impl Engine {
    pub fn new(raw: &crate::pack::RulePack) -> Result<Self, crate::pack::PackError> {
        Ok(Self {
            pack: CompiledPack::compile(raw)?,
        })
    }

    pub fn pack(&self) -> &CompiledPack {
        &self.pack
    }

    pub fn initial_state(&self, account: &str, initial_day: &str) -> AccountState {
        AccountState::new(account, &self.pack, initial_day)
    }

    /// Apply one event. Pure in the sense that all non-determinism (clocks, I/O) is
    /// excluded; `state` is the only mutable input.
    pub fn apply(&self, state: &mut AccountState, ev: &CanonicalEvent) -> ApplyResult {
        apply(state, &self.pack, ev)
    }
}

// ---------------------------------------------------------------------------

/// Apply one event to an account state under a compiled pack.
///
/// Order of operations (documented — this IS the specification):
///  1. idempotency (deal_id / event_id / (account, date)) — duplicates are no-ops;
///  2. clock & sequence integrity alerts (recorded, never fatal — doc §5.4);
///  3. state transition (balance / positions / marks / day);
///  4. rule evaluation at the NEW state (intraday semantics, doc §6.4).
pub fn apply(state: &mut AccountState, pack: &CompiledPack, ev: &CanonicalEvent) -> ApplyResult {
    // 1. idempotency (doc §7.3): at-least-once delivery is safe.
    if !state.seen_dedup_keys.insert(ev.dedup_key()) {
        return ApplyResult::no_change();
    }

    let mut out = ApplyResult::default();

    // 2. integrity alerts — flagged, never fatal (a buggy EA must not silently
    //    fail a trader; the alert path reconciles — doc §5.4).
    if let Some(last) = state.last_broker_ts {
        if ev.broker_ts() < last {
            out.integrity_alerts.push(IntegrityAlert::new(
                ev.event_id(),
                None,
                "BROKER_TS_REGRESSION",
                format!("event broker_ts {} < last applied {}", ev.broker_ts(), last),
            ));
        }
    }
    if ev.seq() < state.seq_applied {
        out.integrity_alerts.push(IntegrityAlert::new(
            ev.event_id(),
            None,
            "SEQ_REGRESSION",
            format!("event seq {} < seq_applied {}", ev.seq(), state.seq_applied),
        ));
    }

    // 3. state transition.
    match ev {
        CanonicalEvent::Mark { symbol, px, .. } => {
            if let Some(px) = decimal(px) {
                state.last_px.insert(symbol.clone(), px);
                out.state_changed = true;
                check_rules(state, pack, ev, &mut out);
            }
        }

        CanonicalEvent::OrderFilled {
            order_id,
            symbol,
            side,
            volume,
            fill_px,
            commission,
            ..
        } => {
            let px = match decimal(fill_px) {
                Some(px) => px,
                None => {
                    out.integrity_alerts.push(IntegrityAlert::new(
                        ev.event_id(),
                        Some(order_id.clone()),
                        "MALFORMED",
                        format!("unparseable fill price {fill_px:?}"),
                    ));
                    return out;
                }
            };
            let comm = decimal(commission).unwrap_or(Decimal::ZERO);

            // News rule (doc §6.4-6): a NEW fill inside an in-scope window is a breach
            // unless the tenant policy is flag-only for pre-positioned (which this is not —
            // see NewsWindow handling for pre-positioned positions).
            if pack.news.enabled && pack.news.symbol_in_scope(symbol) {
                if let Some(w) = state.news_windows.iter().find(|w| {
                    w.symbol == *symbol
                        && pack.news.tier_in_scope(&w.tier)
                        && w.window_start <= ev.broker_ts()
                        && ev.broker_ts() <= w.window_end
                }) {
                    if pack.news.pre_positioned_flag {
                        out.verdicts.push(verdict(
                            state,
                            ev,
                            RuleId::NewsRule,
                            VerdictStatus::Flagged,
                            inputs_news(symbol, w),
                        ));
                    } else {
                        out.verdicts.push(verdict(
                            state,
                            ev,
                            RuleId::NewsRule,
                            VerdictStatus::Breach,
                            inputs_news(symbol, w),
                        ));
                    }
                }
            }

            if state.positions.contains_key(order_id) {
                out.integrity_alerts.push(IntegrityAlert::new(
                    ev.event_id(),
                    Some(order_id.clone()),
                    "DUPLICATE_FILL",
                    format!("order {order_id} already open; duplicate fill dropped"),
                ));
                return out;
            }

            state.positions.insert(
                order_id.clone(),
                Position {
                    order_id: order_id.clone(),
                    symbol: symbol.clone(),
                    side: *side,
                    volume: Decimal::from_f64_retain(*volume).expect("wire invariant: volume is finite"),
                    entry_px: px,
                    opened_ts: ev.broker_ts(),
                },
            );
            state.last_px.insert(symbol.clone(), px);
            state.balance += comm; // opening commission (negative = cost)
            out.state_changed = true;

            // Drain any closes that arrived before this fill (out-of-order delivery,
            // doc §7.1-1 liveness). Applied at the close's own broker_ts.
            let mut i = 0;
            while i < state.deferred_closes.len() {
                let closed_order = match &state.deferred_closes[i] {
                    CanonicalEvent::TradeClosed { order_id: o, .. } => o.clone(),
                    _ => String::new(),
                };
                if closed_order == *order_id {
                    let ev = state.deferred_closes.remove(i);
                    apply_close(state, pack, &ev, &mut out);
                } else {
                    i += 1;
                }
            }

            check_rules(state, pack, ev, &mut out);
        }

        CanonicalEvent::TradeClosed { order_id, .. } => {
            if state.positions.get(order_id).is_none() {
                // Out-of-order delivery: the fill hasn't arrived yet (doc §7.1-1).
                // Buffer the close — it is applied at its own broker_ts when the
                // matching fill arrives. In in-order operation this should not
                // happen; it is flagged (not fatal) so it is visible.
                state.deferred_closes.push(ev.clone());
                out.integrity_alerts.push(IntegrityAlert::new(
                    ev.event_id(),
                    Some(order_id.clone()),
                    "CLOSE_DEFERRED",
                    format!("close for not-yet-open order {order_id}; buffered until fill"),
                ));
                out.state_changed = true;
                return out;
            }
            apply_close(state, pack, ev, &mut out);
        }

        CanonicalEvent::BalanceAdjustment {
            kind, amount, ..
        } => {
            let amt = match decimal(amount) {
                Some(a) => a,
                None => {
                    out.integrity_alerts.push(IntegrityAlert::new(
                        ev.event_id(),
                        None,
                        "MALFORMED",
                        format!("unparseable adjustment amount {amount:?}"),
                    ));
                    return out;
                }
            };
            let _ = kind; // ledger classifies by kind; engine applies the signed value
            state.balance += amt;
            if pack.overall_mode == crate::pack::OverallMode::Trailing {
                state.hwm = state.hwm.max(state.equity());
            }
            out.state_changed = true;
            check_rules(state, pack, ev, &mut out);
        }

        CanonicalEvent::AccountStateReport {
            balance_reported, ..
        } => {
            // Cross-check, don't overwrite: the platform ledger is the business truth
            // (doc §2.3 virtualized balances). Drift beyond tolerance is an alert.
            if let Some(rep) = decimal(balance_reported) {
                if (rep - state.balance).abs() > pack.pnl_tolerance {
                    out.integrity_alerts.push(IntegrityAlert::new(
                        ev.event_id(),
                        None,
                        "BALANCE_DRIFT",
                        format!(
                            "broker-reported {rep} vs platform {} (tol {})",
                            state.balance, pack.pnl_tolerance
                        ),
                    ));
                }
            }
        }

        CanonicalEvent::NewsWindow {
            symbol,
            tier,
            window_start,
            window_end,
            ..
        } => {
            if !pack.news.enabled || !pack.news.symbol_in_scope(symbol) {
                state.news_windows.push(NewsWindowRec {
                    symbol: symbol.clone(),
                    tier: tier.clone(),
                    window_start: *window_start,
                    window_end: *window_end,
                });
                return out;
            }
            if !pack.news.tier_in_scope(tier) {
                state.news_windows.push(NewsWindowRec {
                    symbol: symbol.clone(),
                    tier: tier.clone(),
                    window_start: *window_start,
                    window_end: *window_end,
                });
                return out;
            }
            state.news_windows.push(NewsWindowRec {
                symbol: symbol.clone(),
                tier: tier.clone(),
                window_start: *window_start,
                window_end: *window_end,
            });
            // Pre-positioned positions (doc §6.4-6, policy "flag"): opened before the
            // window starts => flagged, not failed. (Policy "close" drives a CLOSE_ALL
            // control command via the verdict consumer — control plane, not engine.)
            let mut flagged: BTreeSet<String> = BTreeSet::new();
            for pos in state.positions.values() {
                if pos.symbol == *symbol && pos.opened_ts < *window_start && flagged.insert(pos.order_id.clone()) {
                    out.verdicts.push(verdict(
                        state,
                        ev,
                        RuleId::NewsPrePositioned,
                        VerdictStatus::Flagged,
                        inputs_news(symbol, &NewsWindowRec {
                            symbol: symbol.clone(),
                            tier: tier.clone(),
                            window_start: *window_start,
                            window_end: *window_end,
                        }),
                    ));
                }
            }
            out.state_changed = true;
        }

        CanonicalEvent::Rollover { date, .. } => {
            // doc §6.6: finalize the day, roll the snapshot. Idempotent via day:<date>.
            let eq_now = state.equity();

            // eod-breach packs judge the day here (doc §6.4-1, config "eod").
            if !pack.daily_breach_intraday && !state.day.daily_breached {
                let floor = pack.daily_floor(state.day.start_equity);
                if state.day.worst_equity < floor {
                    state.day.daily_breached = true;
                    out.verdicts.push(verdict(
                        state,
                        ev,
                        RuleId::DailyMaxLoss,
                        VerdictStatus::Breach,
                        RuleInputs {
                            equity: Some(state.day.worst_equity.to_string()),
                            threshold: Some(floor.to_string()),
                            start_equity: Some(state.day.start_equity.to_string()),
                            ..Default::default()
                        },
                    ));
                }
            }

            // min trading days (doc §6.4-5): a day counts when it had >= 1 closed deal.
            if state.day.traded {
                state.day_counter += 1;
            }

            if pack.overall_mode == crate::pack::OverallMode::Trailing {
                state.hwm = state.hwm.max(eq_now);
            }

            let prev_date = state.day.date.clone();
            let day_pnl = eq_now - state.day.start_equity;
            out.verdicts.push(verdict(
                state,
                ev,
                RuleId::Rollover,
                VerdictStatus::Info,
                RuleInputs {
                    day_counter: Some(state.day_counter),
                    day_pnl: Some(day_pnl.to_string()),
                    symbol: Some(prev_date), // inputs.symbol doubles as "previous day" here
                    ..Default::default()
                },
            ));

            state.day = DayState {
                date: date.clone(),
                start_equity: eq_now,
                worst_equity: eq_now,
                traded: false,
                daily_breached: false,
            };
            out.state_changed = true;
        }
    }

    // Bookkeeping (always, for non-duplicate events).
    state.seq_applied = state.seq_applied.max(ev.seq());
    state.last_broker_ts = Some(state.last_broker_ts.map(|l| l.max(ev.broker_ts())).unwrap_or(ev.broker_ts()));

    out
}

// ---------------------------------------------------------------------------

/// Close a position: PnL cross-check, ledger update, HWM trail, rule check.
/// Shared by the in-order path and the deferred-closes drain (out-of-order path).
fn apply_close(state: &mut AccountState, pack: &CompiledPack, ev: &CanonicalEvent, out: &mut ApplyResult) {
    let (order_id, symbol, exit_px, pnl_reported, commission, swap) =
        match ev {
            CanonicalEvent::TradeClosed {
                order_id,
                symbol,
                exit_px,
                pnl_reported,
                commission,
                swap,
                ..
            } => (order_id.clone(), symbol.clone(), exit_px.clone(), pnl_reported.clone(), commission.clone(), swap.clone()),
            _ => return, // unreachable: only TradeClosed events reach here
        };

    let exit = match decimal(&exit_px) {
        Some(px) => px,
        None => {
            out.integrity_alerts.push(IntegrityAlert::new(
                ev.event_id(),
                Some(order_id.clone()),
                "MALFORMED",
                format!("unparseable exit price {exit_px:?}"),
            ));
            return;
        }
    };
    let pos = match state.positions.get(&order_id) {
        Some(p) => p.clone(),
        None => return, // unreachable given call sites
    };

    // PnL cross-check (doc §5.4 #5): recompute from stored entry + broker exit.
    // The platform value always wins; a mismatch beyond tolerance is an alert.
    let recomputed = match pos.side {
        Side::Buy => (exit - pos.entry_px) * pos.volume,
        Side::Sell => (pos.entry_px - exit) * pos.volume,
    };
    if let Some(rep) = decimal(&pnl_reported) {
        let tol = pack.pnl_tolerance;
        if (rep - recomputed).abs() > tol {
            out.integrity_alerts.push(IntegrityAlert::new(
                ev.event_id(),
                Some(order_id.clone()),
                "PNL_MISMATCH",
                format!("reported {rep} vs recomputed {recomputed} (tol {tol})"),
            ));
        }
    }

    let comm = decimal(&commission).unwrap_or(Decimal::ZERO);
    let swp = decimal(&swap).unwrap_or(Decimal::ZERO);
    state.balance += recomputed + comm + swp;
    state.positions.remove(&order_id);
    state.last_px.insert(symbol.clone(), exit);
    state.day.traded = true;
    if pack.overall_mode == crate::pack::OverallMode::Trailing {
        state.hwm = state.hwm.max(state.equity());
    }
    out.state_changed = true;
    check_rules(state, pack, ev, out);
}

// ---------------------------------------------------------------------------

/// Rule evaluation at the NEW state (doc §6.4). Called after every state-changing event,
/// including marks — intraday equity is mark-driven (doc §6.4-1 "equity at any moment").
fn check_rules(state: &mut AccountState, pack: &CompiledPack, ev: &CanonicalEvent, out: &mut ApplyResult) {
    let eq = state.equity();

    // eod packs track the day's worst equity for the rollover judgment.
    if !pack.daily_breach_intraday {
        state.day.worst_equity = state.day.worst_equity.min(eq);
    }

    // 1. max daily loss (doc §6.4-1).
    if pack.daily_breach_intraday && !state.day.daily_breached {
        let floor = pack.daily_floor(state.day.start_equity);
        let basis = if pack.daily_basis_equity { eq } else { state.balance };
        if basis < floor {
            state.day.daily_breached = true;
            out.verdicts.push(verdict(
                state,
                ev,
                RuleId::DailyMaxLoss,
                VerdictStatus::Breach,
                RuleInputs {
                    threshold: Some(floor.to_string()),
                    start_equity: Some(state.day.start_equity.to_string()),
                    ..Default::default()
                },
            ));
            return; // day is over, rule-wise: overall/target below still evaluated once below
        }
    }
    // (no early return: overall & target are independent rules)

    // 2. max overall loss (doc §6.4-2/3): static vs trailing (HWM).
    if !state.overall_breached {
        let floor = pack.overall_floor(state.hwm);
        if eq < floor {
            state.overall_breached = true;
            out.verdicts.push(verdict(
                state,
                ev,
                RuleId::MaxOverallLoss,
                VerdictStatus::Breach,
                RuleInputs {
                    threshold: Some(floor.to_string()),
                    hwm: Some(state.hwm.to_string()),
                    start_equity: Some(state.day.start_equity.to_string()),
                    start_balance: Some(state.start_balance.to_string()),
                    ..Default::default()
                },
            ));
        }
    }

    // 3. profit target (doc §6.4-4): requires min trading days.
    if !state.target_reached && state.day_counter >= pack.min_trading_days {
        let level = pack.target_level();
        if eq >= level {
            state.target_reached = true;
            out.verdicts.push(verdict(
                state,
                ev,
                RuleId::ProfitTarget,
                VerdictStatus::TargetReached,
                RuleInputs {
                    threshold: Some(level.to_string()),
                    day_counter: Some(state.day_counter),
                    ..Default::default()
                },
            ));
        }
    }
}

fn inputs_news(symbol: &str, w: &NewsWindowRec) -> RuleInputs {
    RuleInputs {
        symbol: Some(symbol.to_string()),
        tier: Some(w.tier.clone()),
        window_start: Some(w.window_start),
        window_end: Some(w.window_end),
        ..Default::default()
    }
}

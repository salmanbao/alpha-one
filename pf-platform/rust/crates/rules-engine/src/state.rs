//! Per-account state (doc §6.3).
//!
//! Value-semantic, fully serializable, `PartialEq` so tests can assert exact
//! reconstruction (replay equivalence). Hot copy lives in Redis; durable copy in
//! PostgreSQL `day_snapshots` + `verdicts` (doc §4.6).

use crate::events::CanonicalEvent;
use rust_decimal::Decimal;
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, HashMap, HashSet};

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Position {
    pub order_id: String,
    pub symbol: String,
    pub side: Side,
    /// Exact decimal of the wire f64 (documented rounding, doc §13.2-7).
    pub volume: Decimal,
    pub entry_px: Decimal,
    pub opened_ts: i64,
}

/// Side is defined once, in the wire layer (events.rs).
pub use crate::events::Side;

/// The day ledger (doc §6.6). Written once per day at rollover; unique (account, date).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct DayState {
    pub date: String,
    pub start_equity: Decimal,
    /// Worst equity seen this day (used by eod-breach packs).
    pub worst_equity: Decimal,
    pub traded: bool,
    pub daily_breached: bool,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct NewsWindowRec {
    pub symbol: String,
    pub tier: String,
    pub window_start: i64,
    pub window_end: i64,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct AccountState {
    pub account: String,
    pub pack_version: String,

    /// Platform ledger balance — the business truth (double-entry in PG; here its value).
    pub balance: Decimal,
    pub start_balance: Decimal,

    /// High-water mark for trailing overall-loss packs (doc §6.4 rule 3).
    pub hwm: Decimal,

    pub day: DayState,
    /// Trading days with >= 1 closed deal (doc §6.4 rule 5).
    pub day_counter: u32,

    /// Open positions, keyed by order_id.
    pub positions: HashMap<String, Position>,
    /// Last known mark per symbol (platform marks; production uses broker marks at broker_ts).
    pub last_px: BTreeMap<String, Decimal>,

    pub overall_breached: bool,
    pub target_reached: bool,

    pub news_windows: Vec<NewsWindowRec>,

    /// Closes whose fill hasn't arrived yet (out-of-order delivery, doc §7.1).
    /// Drained when the matching fill applies; applied at their own broker_ts.
    pub deferred_closes: Vec<CanonicalEvent>,

    /// Idempotency (doc §7.3).
    pub seen_dedup_keys: HashSet<String>,

    /// Highest applied bridge sequence (crash/replay pointer, doc §7.2).
    pub seq_applied: u64,
    /// Monotonicity watchdog for broker-attested time (integrity alert on regression).
    pub last_broker_ts: Option<i64>,
}

impl AccountState {
    pub fn new(account: &str, pack: &CompiledPack, initial_day: &str) -> Self {
        Self {
            account: account.to_string(),
            pack_version: pack.pack_id.clone(),
            balance: pack.start_balance,
            start_balance: pack.start_balance,
            hwm: pack.start_balance,
            day: DayState {
                date: initial_day.to_string(),
                start_equity: pack.start_balance,
                worst_equity: pack.start_balance,
                traded: false,
                daily_breached: false,
            },
            day_counter: 0,
            positions: HashMap::new(),
            last_px: BTreeMap::new(),
            overall_breached: false,
            target_reached: false,
            news_windows: Vec::new(),
            deferred_closes: Vec::new(),
            seen_dedup_keys: HashSet::new(),
            seq_applied: 0,
            last_broker_ts: None,
        }
    }

    /// Platform equity: ledger balance + unrealized PnL at last known marks.
    /// (Doc §6.3: marks are broker-attested in production; here they are the last
    /// Mark/fill/exit price — the conservation and determinism properties hold either way.)
    pub fn equity(&self) -> Decimal {
        let mut eq = self.balance;
        for pos in self.positions.values() {
            let mark = self
                .last_px
                .get(&pos.symbol)
                .copied()
                .unwrap_or(pos.entry_px);
            let upnl = match pos.side {
                Side::Buy => (mark - pos.entry_px) * pos.volume,
                Side::Sell => (pos.entry_px - mark) * pos.volume,
            };
            eq += upnl;
        }
        eq
    }

    /// PnL of a position at a mark (exact decimals).
    pub fn unrealized(pos: &Position, mark: Decimal) -> Decimal {
        match pos.side {
            Side::Buy => (mark - pos.entry_px) * pos.volume,
            Side::Sell => (pos.entry_px - mark) * pos.volume,
        }
    }
}

use crate::pack::CompiledPack;

//! Canonical events (doc §5.3) — the unit of the event log.
//!
//! Wire form mirrors `contracts/proto/bridge/v1/bridge.proto`. In production these
//! are prost-generated messages consumed from Kafka (partition-ordered per account);
//! for the scaffold they are serde types with the same field layout, money/price
//! values carried as **decimal strings** so no float ever touches the engine.

use rust_decimal::Decimal;
use serde::{Deserialize, Serialize};
use std::str::FromStr;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Side {
    Buy,
    Sell,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum AdjKind {
    Commission,
    Swap,
    Bonus,
    Refund,
    Correction,
}

/// One canonical event on the per-account, partition-ordered stream.
///
/// `broker_ts` (epoch ms) is the rule clock. `seq` is the per-account bridge sequence.
/// `event_id` is the ULID of the event (dedup for non-deal events).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum CanonicalEvent {
    /// A fill opened (or would-open) a position. `fill_px` is broker-attested.
    OrderFilled {
        event_id: String,
        seq: u64,
        broker_ts: i64,
        order_id: String,
        /// Global idempotency key.
        deal_id: String,
        symbol: String,
        side: Side,
        /// Contracts. f64 on the wire (a quantity, not money); converted via
        /// `Decimal::from_f64_retain` — deterministic, documented rounding.
        volume: f64,
        fill_px: String,
        /// Cost of opening, minor units, negative = cost.
        commission: String,
    },
    /// A price mark for a symbol (from the quote feed or a position update).
    Mark {
        event_id: String,
        seq: u64,
        broker_ts: i64,
        symbol: String,
        px: String,
    },
    /// A position was closed. `pnl_reported` comes from the terminal and is
    /// **recomputed** by the engine (doc §5.4 cross-check).
    TradeClosed {
        event_id: String,
        seq: u64,
        broker_ts: i64,
        order_id: String,
        deal_id: String,
        symbol: String,
        volume: f64,
        entry_px: String,
        exit_px: String,
        pnl_reported: String,
        commission: String,
        swap: String,
    },
    /// External balance movement (bonus, refund, correction, pass-through fee).
    BalanceAdjustment {
        event_id: String,
        seq: u64,
        broker_ts: i64,
        kind: AdjKind,
        amount: String,
        ref_: Option<String>,
    },
    /// Broker-attested account snapshot. The engine cross-checks the reported
    /// balance against the platform ledger (drift => integrity alert).
    AccountStateReport {
        event_id: String,
        seq: u64,
        broker_ts: i64,
        balance_reported: String,
        equity_reported: Option<String>,
    },
    /// A news window (economic-calendar join, doc §6.4 rule 6). Emitted by the
    /// rules-orchestrator from the calendar feed, not by the terminal.
    NewsWindow {
        event_id: String,
        seq: u64,
        broker_ts: i64,
        symbol: String,
        tier: String,
        window_start: i64,
        window_end: i64,
    },
    /// Day boundary (doc §6.6). `date` (YYYY-MM-DD) is the NEW day, computed by
    /// the tenant-timezone cron. Carries the engine's day counter forward.
    Rollover {
        event_id: String,
        seq: u64,
        broker_ts: i64,
        date: String,
    },
}

impl CanonicalEvent {
    pub fn event_id(&self) -> &str {
        match self {
            CanonicalEvent::OrderFilled { event_id, .. }
            | CanonicalEvent::Mark { event_id, .. }
            | CanonicalEvent::TradeClosed { event_id, .. }
            | CanonicalEvent::BalanceAdjustment { event_id, .. }
            | CanonicalEvent::AccountStateReport { event_id, .. }
            | CanonicalEvent::NewsWindow { event_id, .. }
            | CanonicalEvent::Rollover { event_id, .. } => event_id,
        }
    }

    pub fn seq(&self) -> u64 {
        match self {
            CanonicalEvent::OrderFilled { seq, .. }
            | CanonicalEvent::Mark { seq, .. }
            | CanonicalEvent::TradeClosed { seq, .. }
            | CanonicalEvent::BalanceAdjustment { seq, .. }
            | CanonicalEvent::AccountStateReport { seq, .. }
            | CanonicalEvent::NewsWindow { seq, .. }
            | CanonicalEvent::Rollover { seq, .. } => *seq,
        }
    }

    pub fn broker_ts(&self) -> i64 {
        match self {
            CanonicalEvent::OrderFilled { broker_ts, .. }
            | CanonicalEvent::Mark { broker_ts, .. }
            | CanonicalEvent::TradeClosed { broker_ts, .. }
            | CanonicalEvent::BalanceAdjustment { broker_ts, .. }
            | CanonicalEvent::AccountStateReport { broker_ts, .. }
            | CanonicalEvent::NewsWindow { broker_ts, .. }
            | CanonicalEvent::Rollover { broker_ts, .. } => *broker_ts,
        }
    }

    /// Natural idempotency key: deal-based events dedupe on `deal_id`,
    /// everything else on `event_id` (doc §5.4, §7.3).
    pub fn dedup_key(&self) -> String {
        match self {
            CanonicalEvent::OrderFilled { deal_id, .. }
            | CanonicalEvent::TradeClosed { deal_id, .. } => format!("deal:{deal_id}"),
            CanonicalEvent::Rollover { date, .. } => format!("day:{date}"),
            other => format!("ev:{}", other.event_id()),
        }
    }
}

pub fn decimal(s: &str) -> Option<Decimal> {
    Decimal::from_str(s).ok()
}


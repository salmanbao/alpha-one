//! Verdicts (doc §6.4): a verdict is a *proof*, not an assertion.
//!
//! Every verdict carries the exact decimal inputs, the pack version, the event id
//! and the broker timestamp. Dispute resolution = replay the stream to the event,
//! diff against the trader's terminal, done (doc §6.4).

use rust_decimal::Decimal;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum RuleId {
    DailyMaxLoss,
    MaxOverallLoss,
    ProfitTarget,
    NewsRule,
    NewsPrePositioned,
    WeekendNoHold, // reserved: enforced at cutoff by the control plane
    OvernightRule, // reserved: funded packs
    Rollover,      // info: day finalized
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum VerdictStatus {
    Breach,
    TargetReached,
    Flagged,
    Info,
}

/// Exact inputs that produced the verdict (all money as decimal strings).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, Default)]
pub struct RuleInputs {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub equity: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub threshold: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub start_equity: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub start_balance: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub hwm: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub day_pnl: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub reported_pnl: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub recomputed_pnl: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub day_counter: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub window_start: Option<i64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub window_end: Option<i64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub tier: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub symbol: Option<String>,
}

impl RuleInputs {
    fn d(v: Decimal) -> String {
        v.to_string()
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Verdict {
    pub event_id: String,
    pub account: String,
    pub rule: RuleId,
    pub status: VerdictStatus,
    /// Trading day the verdict belongs to (for (rule, day) identity).
    pub day: String,
    pub broker_ts: i64,
    pub pack_version: String,
    pub inputs: RuleInputs,
}

impl Verdict {
    /// Deterministic fingerprint of the verdict *identity* (rule, status, day) —
    /// used by properties that assert order-independence of verdict sets.
    pub fn identity(&self) -> String {
        format!("{:?}|{:?}|{}", self.rule, self.status, self.day)
    }

    /// Full deterministic fingerprint including exact inputs (doc §13.2-1).
    pub fn fingerprint(&self) -> String {
        let mut s = String::new();
        s.push_str(&self.identity());
        s.push('|');
        s.push_str(&format!(
            "ts={};pack={};eq={};thr={};start={};hwm={};dpnl={};rpnl={};cpnl={};dc={}",
            self.broker_ts,
            self.pack_version,
            self.inputs.equity.as_deref().unwrap_or("-"),
            self.inputs.threshold.as_deref().unwrap_or("-"),
            self.inputs.start_equity.as_deref().unwrap_or("-"),
            self.inputs.hwm.as_deref().unwrap_or("-"),
            self.inputs.day_pnl.as_deref().unwrap_or("-"),
            self.inputs.reported_pnl.as_deref().unwrap_or("-"),
            self.inputs.recomputed_pnl.as_deref().unwrap_or("-"),
            self.inputs.day_counter.map(|v| v.to_string()).unwrap_or_default(),
        ));
        s
    }
}

pub(crate) fn verdict<'a>(
    state: &'a crate::state::AccountState,
    ev: &'a crate::events::CanonicalEvent,
    rule: RuleId,
    status: VerdictStatus,
    mut inputs: RuleInputs,
) -> Verdict {
    let eq = state.equity();
    if inputs.equity.is_none() {
        inputs.equity = Some(RuleInputs::d(eq));
    }
    if inputs.start_balance.is_none() {
        inputs.start_balance = Some(RuleInputs::d(state.start_balance));
    }
    if inputs.day_pnl.is_none() {
        inputs.day_pnl = Some(RuleInputs::d(eq - state.day.start_equity));
    }
    Verdict {
        event_id: ev.event_id().to_string(),
        account: state.account.clone(),
        rule,
        status,
        day: state.day.date.clone(),
        broker_ts: ev.broker_ts(),
        pack_version: state.pack_version.clone(),
        inputs,
    }
}

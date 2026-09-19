//! Rule packs (doc §6.2): data, versioned, immutable.
//!
//! JSON shape is defined by `contracts/rulepack/v1/rulepack.schema.json`
//! (validated in CI by `scripts/check-contracts.js`). This module compiles the
//! JSON into a typed plan so the hot path never touches JSON or floats.

use rust_decimal::Decimal;
use serde::Deserialize;
use std::collections::BTreeSet;

/// Raw JSON rule pack (wire form). Money/percent fields are parsed to Decimal at compile time.
#[derive(Debug, Clone, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RulePack {
    pub pack_id: String,
    #[serde(rename = "start_balance")]
    pub start_balance: Decimal,
    pub day: DayCfg,
    pub rules: RulesCfg,
    #[serde(default)]
    pub funded: Option<FundedCfg>,
    #[serde(default)]
    pub currency: Option<String>,
}

#[derive(Debug, Clone, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct DayCfg {
    pub timezone: String,
    /// "equity" | "balance"
    pub basis: String,
    /// "intraday" | "eod"
    pub breach: String,
}

#[derive(Debug, Clone, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RulesCfg {
    pub max_daily_loss_pct: Decimal,
    /// Contract field name (rulepack.schema.json): "max_overall_loss_pct".
    #[serde(
        rename = "max_overall_loss_pct",
        deserialize_with = "de_overall_loss"
    )]
    pub max_overall_loss: OverallLossCfg,
    pub profit_target_pct: Decimal,
    pub min_trading_days: u32,
    #[serde(default)]
    pub time_limit_days: Option<u32>,
    #[serde(default)]
    pub news: Option<NewsCfg>,
    #[serde(default)]
    pub pnl_tolerance: Option<Decimal>,

    // L0/L1 fields: part of the pack, consumed by the bridge/EA (doc §6.5),
    // declared here so the pack parses as one whole document.
    #[serde(default)]
    pub weekend: Option<WeekendCfg>,
    #[serde(default)]
    pub overnight: Option<OvernightCfg>,
    #[serde(default)]
    pub spread_max_pips: Option<std::collections::BTreeMap<String, Decimal>>,
    #[serde(default)]
    pub volume_max: Option<Decimal>,
    #[serde(default)]
    pub open_positions_max: Option<u32>,
    #[serde(default)]
    pub allowed_symbols: Option<Vec<String>>,
    #[serde(default)]
    pub denied_symbols: Option<Vec<String>>,
}

#[derive(Debug, Clone, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct WeekendCfg {
    #[serde(default)]
    pub mode: Option<String>,
    #[serde(default)]
    pub cutoff: Option<String>,
    #[serde(default)]
    pub action: Option<String>,
}

#[derive(Debug, Clone, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct OvernightCfg {
    #[serde(default)]
    pub enabled: Option<bool>,
    #[serde(default)]
    pub max_hold_hours: Option<f64>,
}

/// `"max_overall_loss_pct": 8.0` (shorthand = static) or
/// `"max_overall_loss_pct": {"mode": "trailing", "value": 10.0}` (doc §6.4).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum OverallLossCfg {
    Static(Decimal),
    Trailing(Decimal),
}

#[derive(Debug, Clone, Deserialize, Default)]
#[serde(deny_unknown_fields)]
pub struct NewsCfg {
    #[serde(default)]
    pub enabled: bool,
    #[serde(default)]
    pub tiers: Option<Vec<String>>,
    #[serde(default)]
    pub instruments: Option<String>, // comma list or "*"
    #[serde(default)]
    pub source: Option<String>, // e.g. "economic-calendar:v3"
    #[serde(default)]
    pub pre_positioned: Option<String>, // "flag" | "fail" | "close" (default "flag")
}

#[derive(Debug, Clone, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct FundedCfg {
    #[serde(default)]
    pub split_pct: Option<Decimal>,
    #[serde(default)]
    pub payout: Option<PayoutCfg>,
    #[serde(default)]
    pub hedge_drift: Option<HedgeDriftCfg>,
}

#[derive(Debug, Clone, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct PayoutCfg {
    #[serde(default)]
    pub first_payout_day: Option<u32>,
    #[serde(default)]
    pub every_days: Option<u32>,
    #[serde(default)]
    pub min_withdrawal: Option<Decimal>,
}

#[derive(Debug, Clone, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct HedgeDriftCfg {
    #[serde(default)]
    pub max_ticks: Option<u32>,
    #[serde(default)]
    pub max_latency_ms: Option<u64>,
    #[serde(default)]
    pub on_breach: Option<String>,
}

// ---------------------------------------------------------------------------

fn de_overall_loss<'de, D>(d: D) -> Result<OverallLossCfg, D::Error>
where
    D: serde::Deserializer<'de>,
{
    #[derive(Deserialize)]
    #[serde(untagged)]
    enum Raw {
        Num(Decimal),
        Obj { mode: String, value: Decimal },
    }
    match Raw::deserialize(d)? {
        Raw::Num(v) => Ok(OverallLossCfg::Static(v)),
        Raw::Obj { mode, value } => match mode.as_str() {
            "static" => Ok(OverallLossCfg::Static(value)),
            "trailing" => Ok(OverallLossCfg::Trailing(value)),
            other => Err(serde::de::Error::custom(format!(
                "unknown max_overall_loss_pct mode: {other}"
            ))),
        },
    }
}

// ---------------------------------------------------------------------------

/// Compile-time errors. A pack that fails to compile can never reach the hot path.
#[derive(Debug, PartialEq, Eq)]
pub enum PackError {
    InvalidBasis(String),
    InvalidBreachMode(String),
    InvalidPrePositioned(String),
    NonPositiveDailyLoss,
    NonPositiveTarget,
    PackIdMissing,
}

impl std::fmt::Display for PackError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(
            f,
            "pack error: {self:?}"
        )
    }
}

/// Compiled, typed rule plan. The hot path (eval.rs) executes this, not JSON.
#[derive(Debug, Clone, PartialEq)]
pub struct CompiledPack {
    pub pack_id: String,
    pub start_balance: Decimal,
    pub daily_loss_pct: Decimal,
    pub overall_mode: OverallMode,
    pub overall_loss_pct: Decimal,
    pub target_pct: Decimal,
    pub min_trading_days: u32,
    pub time_limit_days: Option<u32>,
    pub daily_basis_equity: bool,
    pub daily_breach_intraday: bool,
    pub news: CompiledNews,
    pub pnl_tolerance: Decimal,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum OverallMode {
    Static,
    Trailing,
}

/// Compiled news rule: scope (tiers + symbols) and pre-positioned policy.
#[derive(Debug, Clone, PartialEq)]
pub struct CompiledNews {
    pub enabled: bool,
    pub pre_positioned_flag: bool,
    /// Economic-impact tiers in scope; empty = all.
    pub tiers: BTreeSet<String>,
    /// Symbols in scope; contains "*" for all.
    pub symbols: BTreeSet<String>,
}

impl CompiledNews {
    pub fn symbol_in_scope(&self, symbol: &str) -> bool {
        self.symbols.iter().any(|s| s == "*" || s == symbol)
    }

    pub fn tier_in_scope(&self, tier: &str) -> bool {
        self.tiers.is_empty() || self.tiers.iter().any(|t| t == tier)
    }
}

impl CompiledPack {
    pub fn compile(p: &RulePack) -> Result<Self, PackError> {
        if p.pack_id.is_empty() {
            return Err(PackError::PackIdMissing);
        }
        let daily_basis_equity = match p.day.basis.as_str() {
            "equity" => true,
            "balance" => false,
            other => return Err(PackError::InvalidBasis(other.to_string())),
        };
        let daily_breach_intraday = match p.day.breach.as_str() {
            "intraday" => true,
            "eod" => false,
            other => return Err(PackError::InvalidBreachMode(other.to_string())),
        };
        if p.rules.max_daily_loss_pct <= Decimal::ZERO {
            return Err(PackError::NonPositiveDailyLoss);
        }
        if p.rules.profit_target_pct <= Decimal::ZERO {
            return Err(PackError::NonPositiveTarget);
        }
        let (overall_mode, overall_loss_pct) = match &p.rules.max_overall_loss {
            OverallLossCfg::Static(v) => (OverallMode::Static, *v),
            OverallLossCfg::Trailing(v) => (OverallMode::Trailing, *v),
        };
        let news = p
            .rules
            .news
            .as_ref()
            .map(|n| CompiledNews {
                enabled: n.enabled,
                pre_positioned_flag: match n.pre_positioned.as_deref().unwrap_or("flag") {
                    "flag" => true,
                    "fail" => false,
                    _ => true, // "close" is enforced by the control plane; engine flags
                },
                tiers: n
                    .tiers
                    .clone()
                    .unwrap_or_default()
                    .into_iter()
                    .map(|t| t.to_ascii_lowercase())
                    .collect(),
                symbols: n
                    .instruments
                    .as_deref()
                    .unwrap_or("*")
                    .split(',')
                    .map(|s| s.trim().to_string())
                    .filter(|s| !s.is_empty())
                    .collect(),
            })
            .unwrap_or(CompiledNews {
                enabled: false,
                pre_positioned_flag: true,
                tiers: BTreeSet::new(),
                symbols: BTreeSet::new(),
            });
        Ok(CompiledPack {
            pack_id: p.pack_id.clone(),
            start_balance: p.start_balance,
            daily_loss_pct: p.rules.max_daily_loss_pct,
            overall_mode,
            overall_loss_pct,
            target_pct: p.rules.profit_target_pct,
            min_trading_days: p.rules.min_trading_days,
            time_limit_days: p.rules.time_limit_days,
            daily_basis_equity,
            daily_breach_intraday,
            news,
            pnl_tolerance: p
                .rules
                .pnl_tolerance
                .unwrap_or_else(|| Decimal::new(1, 2)), // 0.01 minor units (doc §5.4: 1 pip class)
        })
    }

    // -- precomputed threshold helpers (exact decimal math) -----------------

    pub fn daily_floor(&self, day_start: Decimal) -> Decimal {
        day_start * (Decimal::ONE - self.daily_loss_pct / Decimal::new(100, 0))
    }

    /// Overall-loss threshold: static is against start_balance; trailing against HWM.
    pub fn overall_floor(&self, hwm: Decimal) -> Decimal {
        let base = match self.overall_mode {
            OverallMode::Static => self.start_balance,
            OverallMode::Trailing => hwm,
        };
        base * (Decimal::ONE - self.overall_loss_pct / Decimal::new(100, 0))
    }

    pub fn target_level(&self) -> Decimal {
        self.start_balance * (Decimal::ONE + self.target_pct / Decimal::new(100, 0))
    }
}

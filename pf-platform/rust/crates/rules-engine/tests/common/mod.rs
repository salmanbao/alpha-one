//! Test infrastructure: deterministic event-stream builder + pack helpers.
//!
//! The builder is the "sim harness in miniature" (doc §13.4): it generates
//! well-formed, seeded streams and — crucially — tracks the *expected* running
//! ledger balance in exact decimals, which lets property tests assert the money
//! conservation invariant at every prefix (doc §13.2-4).

use rules_engine::events::{AdjKind, CanonicalEvent, Side};
use rules_engine::pack::RulePack;
use rust_decimal::Decimal;
use serde_json::from_str;
use std::collections::BTreeMap;

pub const DAY0: &str = "2026-01-05";
pub const ACCOUNT: &str = "acct-0001";

// ---------------------------------------------------------------------------
// Packs (JSON = the contract shape, validated in CI against the JSON Schema)

pub fn pack_json(daily_pct: &str, overall: &str, target: &str, min_days: u32) -> String {
    format!(
        r#"{{
  "pack_id": "test:challenge:100k:v1",
  "currency": "USD",
  "start_balance": 100000,
  "day": {{"timezone": "Europe/London", "basis": "equity", "breach": "intraday"}},
  "rules": {{
    "max_daily_loss_pct": {daily_pct},
    "max_overall_loss_pct": {overall},
    "profit_target_pct": {target},
    "min_trading_days": {min_days},
    "pnl_tolerance": 0.01
  }}
}}"#
    )
}

pub fn pack_daily4() -> RulePack {
    let j = pack_json("4.0", "8.0", "10.0", 4);
    from_str(&j).expect("pack parses")
}

pub fn pack_daily8() -> RulePack {
    let j = pack_json("8.0", "16.0", "10.0", 4);
    from_str(&j).expect("pack parses")
}

/// Trailing-10% overall pack for HWM tests.
pub fn pack_trailing10() -> RulePack {
    let j = pack_json(
        "4.0",
        r#"{"mode": "trailing", "value": 10.0}"#,
        "10.0",
        0,
    );
    from_str(&j).expect("pack parses")
}

/// eod-breach daily pack.
pub fn pack_eod_daily4() -> RulePack {
    let j = r#"{
  "pack_id": "test:challenge:100k:v2",
  "currency": "USD",
  "start_balance": 100000,
  "day": {"timezone": "Europe/London", "basis": "equity", "breach": "eod"},
  "rules": {
    "max_daily_loss_pct": 4.0,
    "max_overall_loss_pct": 8.0,
    "profit_target_pct": 10.0,
    "min_trading_days": 1,
    "pnl_tolerance": 0.01
  }
}"#;
    from_str(j).expect("pack parses")
}

/// Contract conformance: the shipped sample packs must compile.
#[test]
fn sample_packs_compile() {
    for f in ["challenge_100k.json", "funded_100k.json"] {
        let p = format!("{}/../../../contracts/samples/{f}", env!("CARGO_MANIFEST_DIR"));
        let json = std::fs::read_to_string(p).expect("sample pack exists");
        let raw: RulePack = from_str(&json).unwrap_or_else(|e| panic!("{f}: {e}"));
        rules_engine::pack::CompiledPack::compile(&raw)
            .unwrap_or_else(|e| panic!("{f}: {e}"));
    }
}

// ---------------------------------------------------------------------------
// Deterministic LCG (seeded; no external RNG dep)

pub struct Rng(u64);
impl Rng {
    pub fn new(seed: u64) -> Self {
        Self(if seed == 0 { 0x9E3779B97F4A7C15 } else { seed })
    }
    pub fn u64(&mut self) -> u64 {
        self.0 = self
            .0
            .wrapping_mul(6364136223846793005)
            .wrapping_add(1442695040888963407);
        self.0 >> 1
    }
    pub fn range(&mut self, lo: u64, hi: u64) -> u64 {
        lo + self.u64() % (hi - lo + 1)
    }
    pub fn chance(&mut self, pct: u64) -> bool {
        self.range(0, 99) < pct
    }
}

// ---------------------------------------------------------------------------
// Stream builder

pub struct GenOpts {
    pub max_events: usize,
    pub allow_rollover: bool,
    pub allow_news: bool,
    pub allow_reports: bool,
}

pub struct GenResult {
    pub events: Vec<CanonicalEvent>,
    /// Expected running platform balance after each event (in-order only).
    pub expected_balance_after: Vec<Decimal>,
    pub final_price: Decimal,
}

#[derive(Debug, Clone)]
struct OpenRec {
    order_id: String,
    side: Side,
    entry: Decimal,
    vol: Decimal,
}

const VOLUMES: &[f64] = &[0.1, 0.5, 1.0, 2.5, 5.0];
const MONTHS: &[u32] = &[31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];

struct World {
    rng: Rng,
    price: Decimal,
    balance: Decimal,
    opens: Vec<OpenRec>,
    seq: u64,
    ts: i64,
    n: u64,
    day: (u32, u32, u32),
}

impl World {
    fn new(seed: u64) -> Self {
        Self {
            rng: Rng::new(seed),
            price: Decimal::from(10000u64),
            balance: Decimal::from(100000u64),
            opens: Vec::new(),
            seq: 0,
            ts: 1_750_000_000_000,
            n: 0,
            day: (2026, 1, 5),
        }
    }

    fn tick(&mut self) -> i64 {
        self.ts += 1000 + (self.rng.range(0, 9) as i64) * 1000;
        self.ts
    }

    fn eid(&mut self, kind: &str) -> String {
        self.n += 1;
        format!("{kind}-{}", self.n)
    }

    fn day_str(&self) -> String {
        format!(
            "{:04}-{:02}-{:02}",
            self.day.0, self.day.1, self.day.2
        )
    }

    fn bump_day(&mut self) {
        let (y, m, d) = self.day;
        let dim = MONTHS[(m - 1) as usize];
        if d < dim {
            self.day.2 = d + 1;
        } else if m < 12 {
            self.day = (y, m + 1, 1);
        } else {
            self.day = (y + 1, 1, 1);
        }
    }

    fn vol_dec(&mut self) -> (f64, Decimal) {
        let v = VOLUMES[self.rng.range(0, VOLUMES.len() as u64 - 1) as usize];
        (v, Decimal::from_f64_retain(v).expect("finite test volume"))
    }

    /// Generate one action. Returns (events, balance_after).
    fn act(&mut self, opts: &GenOpts) -> Vec<(CanonicalEvent, Decimal)> {
        let r = self.rng.range(0, 99);

        // keep the book bounded; bias toward closing when we have room to draw a close
        if self.opens.len() >= 10 {
            return self.close(opts);
        }
        if r >= 35 && r < 85 && !self.opens.is_empty() {
            return self.close(opts);
        }
        match r {
            0..=34 => self.open(false),
            35..=84 => self.mark(),
            85..=91 => self.adjust(),
            _ => {
                if opts.allow_reports && self.rng.chance(50) {
                    self.report()
                } else if opts.allow_news && self.rng.chance(40) {
                    self.news_then_open()
                } else if opts.allow_rollover && self.rng.chance(25) {
                    self.rollover()
                } else {
                    self.mark()
                }
            }
        }
    }

    fn open(&mut self, after_news: bool) -> Vec<(CanonicalEvent, Decimal)> {
        let ts = self.tick();
        let (side, volume, entry) = {
            let side = if self.rng.chance(50) { Side::Buy } else { Side::Sell };
            let (v, _) = self.vol_dec();
            let entry = self.price;
            (side, v, entry)
        };
        let commission = if self.rng.chance(10) { Decimal::from(-5i64) } else { Decimal::ZERO };
        let order_id = format!("ord-{}", self.n + 1);
        let deal_id = format!("deal-{order_id}");
        self.opens.push(OpenRec {
            order_id: order_id.clone(),
            side,
            entry,
            vol: Decimal::from_f64_retain(volume).expect("finite test volume"),
        });
        self.balance += commission;
        let _ = after_news;
        vec![(
            CanonicalEvent::OrderFilled {
                event_id: self.eid("fill"),
                seq: self.next_seq(),
                broker_ts: ts,
                order_id,
                deal_id,
                symbol: "EURUSD".into(),
                side,
                volume,
                fill_px: entry.to_string(),
                commission: commission.to_string(),
            },
            self.balance,
        )]
    }

    fn news_then_open(&mut self) -> Vec<(CanonicalEvent, Decimal)> {
        let wstart = self.tick() + 1000;
        let wend = wstart + 30_000;
        let w = CanonicalEvent::NewsWindow {
            event_id: self.eid("news"),
            seq: self.next_seq(),
            broker_ts: self.tick(),
            symbol: "EURUSD".into(),
            tier: "high".into(),
            window_start: wstart,
            window_end: wend,
        };
        // open during the window (guaranteed: the open's ts > wstart)
        self.tick();
        let bal_before = self.balance;
        let mut evs = self.open(true);
        evs.insert(0, (w, bal_before));
        evs
    }

    fn close(&mut self, _opts: &GenOpts) -> Vec<(CanonicalEvent, Decimal)> {
        let idx = self.rng.range(0, self.opens.len() as u64 - 1) as usize;
        let open = self.opens.remove(idx);
        let exit = self.price;
        let ts = self.tick();
        let recomputed = match open.side {
            Side::Buy => (exit - open.entry) * open.vol,
            Side::Sell => (open.entry - exit) * open.vol,
        };
        // 5% of terminals report a wrong PnL (malicious/buggy persona, doc §13.4)
        let reported = if self.rng.chance(5) {
            recomputed * Decimal::from(3)
        } else {
            recomputed
        };
        let commission = if self.rng.chance(10) { Decimal::from(-5i64) } else { Decimal::ZERO };
        let swap = if self.rng.chance(10) { Decimal::from(-3i64) } else { Decimal::ZERO };
        self.balance += recomputed + commission + swap;
        vec![(
            CanonicalEvent::TradeClosed {
                event_id: self.eid("close"),
                seq: self.next_seq(),
                broker_ts: ts,
                order_id: open.order_id.clone(),
                deal_id: format!("deal-close-{}", open.order_id),
                symbol: "EURUSD".into(),
                volume: f64::try_from(open.vol).expect("finite"),
                entry_px: open.entry.to_string(),
                exit_px: exit.to_string(),
                pnl_reported: reported.to_string(),
                commission: commission.to_string(),
                swap: swap.to_string(),
            },
            self.balance,
        )]
    }

    fn mark(&mut self) -> Vec<(CanonicalEvent, Decimal)> {
        let ts = self.tick();
        let step = self.rng.range(1, 300) as i64;
        if self.rng.chance(50) {
            self.price -= Decimal::from(step);
        } else {
            self.price += Decimal::from(step);
        }
        vec![(
            CanonicalEvent::Mark {
                event_id: self.eid("mark"),
                seq: self.next_seq(),
                broker_ts: ts,
                symbol: "EURUSD".into(),
                px: self.price.to_string(),
            },
            self.balance,
        )]
    }

    fn adjust(&mut self) -> Vec<(CanonicalEvent, Decimal)> {
        let ts = self.tick();
        let amt = if self.rng.chance(50) {
            Decimal::from(50i64)
        } else {
            Decimal::from(-50i64)
        };
        self.balance += amt;
        vec![(
            CanonicalEvent::BalanceAdjustment {
                event_id: self.eid("adj"),
                seq: self.next_seq(),
                broker_ts: ts,
                kind: AdjKind::Correction,
                amount: amt.to_string(),
                ref_: Some(format!("corr-{}", self.n)),
            },
            self.balance,
        )]
    }

    fn report(&mut self) -> Vec<(CanonicalEvent, Decimal)> {
        let ts = self.tick();
        // 10% of reports drift by 1000 (simulates terminal/broker desync)
        let reported = if self.rng.chance(10) {
            self.balance + Decimal::from(1000i64)
        } else {
            self.balance
        };
        vec![(
            CanonicalEvent::AccountStateReport {
                event_id: self.eid("rep"),
                seq: self.next_seq(),
                broker_ts: ts,
                balance_reported: reported.to_string(),
                equity_reported: None,
            },
            self.balance,
        )]
    }

    fn rollover(&mut self) -> Vec<(CanonicalEvent, Decimal)> {
        let ts = self.tick();
        let _prev = self.day_str();
        self.bump_day();
        vec![(
            CanonicalEvent::Rollover {
                event_id: self.eid("roll"),
                seq: self.next_seq(),
                broker_ts: ts,
                date: self.day_str(),
            },
            self.balance,
        )]
    }

    fn next_seq(&mut self) -> u64 {
        self.seq += 1;
        self.seq
    }
}

pub fn build_stream(seed: u64, opts: &GenOpts) -> GenResult {
    let mut w = World::new(seed);
    let mut events = Vec::new();
    let mut expected = Vec::new();
    for _ in 0..opts.max_events {
        let out = w.act(opts);
        for (ev, bal) in out {
            events.push(ev);
            expected.push(bal);
        }
    }
    // ensure the stream ends with all positions closed (clean final state)
    while let Some(open) = w.opens.last().cloned() {
        let opts2 = GenOpts { max_events: 0, ..*opts };
        let out = w.close(&opts2);
        for (ev, bal) in out {
            events.push(ev);
            expected.push(bal);
        }
        let _ = open;
    }
    GenResult {
        events,
        expected_balance_after: expected,
        final_price: w.price,
    }
}

/// Canonical comparison of the open-position book (order-insensitive).
pub fn position_book(s: &rules_engine::state::AccountState) -> BTreeMap<String, (Side, String, String)> {
    s.positions
        .iter()
        .map(|(k, p)| {
            (
                k.clone(),
                (p.side, p.volume.to_string(), p.entry_px.to_string()),
            )
        })
        .collect()
}

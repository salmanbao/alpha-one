//! Golden-file tests (doc §13.2): hand-verified scenarios with EXACT expected
//! values. These encode the business semantics that properties cannot express.
//!
//! Money units: start balance 100,000.00000000 minor units; prices in minor units.

mod common;

use common::*;
use rules_engine::events::{CanonicalEvent, Side};
use rules_engine::pack::RulePack;
use rules_engine::verdict::{RuleId, VerdictStatus};
use rules_engine::{Engine, RuleId as R};
use rust_decimal::Decimal;
use std::str::FromStr;

fn ev_id(n: u64, kind: &str) -> String {
    format!("{kind}-{n}")
}

fn d(s: &str) -> Decimal {
    Decimal::from_str(s).unwrap()
}

// ---------------------------------------------------------------------------
// g1: basic open → mark → close. No breaches. Ledger moves by exactly the PnL.
#[test]
fn g1_basic_roundtrip() {
    let e = Engine::new(&pack_daily4()).unwrap();
    let mut s = e.initial_state(ACCOUNT, DAY0);

    let r1 = e.apply(&mut s, &CanonicalEvent::OrderFilled {
        event_id: ev_id(1, "fill"), seq: 1, broker_ts: 1_750_000_000_000,
        order_id: "o1".into(), deal_id: "d1".into(),
        symbol: "EURUSD".into(), side: Side::Buy, volume: 1.0,
        fill_px: "10000".into(), commission: "0".into(),
    });
    let r2 = e.apply(&mut s, &CanonicalEvent::Mark {
        event_id: ev_id(2, "mark"), seq: 2, broker_ts: 1_750_000_001_000,
        symbol: "EURUSD".into(), px: "9900".into(),
    });
    let r3 = e.apply(&mut s, &CanonicalEvent::TradeClosed {
        event_id: ev_id(3, "close"), seq: 3, broker_ts: 1_750_000_002_000,
        order_id: "o1".into(), deal_id: "d2".into(),
        symbol: "EURUSD".into(), volume: 1.0,
        entry_px: "10000".into(), exit_px: "9900".into(),
        pnl_reported: "-100".into(), commission: "0".into(), swap: "0".into(),
    });

    assert!(r1.verdicts.is_empty() && r2.verdicts.is_empty());
    assert!(r3.verdicts.is_empty(), "no rules may fire: {:?}", r3.verdicts);
    assert_eq!(s.balance, d("99900"));
    assert!(s.positions.is_empty());
    assert!(s.day.traded);
    assert!(!s.day.daily_breached && !s.overall_breached && !s.target_reached);
}

// ---------------------------------------------------------------------------
// g2: intraday daily-loss breach on a MARK (not a close), and no un-breach
//     when equity recovers. Exact threshold math: floor = 100000 * 0.96 = 96000.
#[test]
fn g2_intraday_breach_on_mark_no_unbreach() {
    let e = Engine::new(&pack_daily4()).unwrap();
    let mut s = e.initial_state(ACCOUNT, DAY0);

    e.apply(&mut s, &CanonicalEvent::OrderFilled {
        event_id: ev_id(1, "fill"), seq: 1, broker_ts: 1_750_000_000_000,
        order_id: "o1".into(), deal_id: "d1".into(),
        symbol: "EURUSD".into(), side: Side::Buy, volume: 5.0,
        fill_px: "10000".into(), commission: "0".into(),
    });
    // mark 9199 → upnl = (9199-10000)*5 = -4005 → equity 95995 < 96000 → BREACH
    let r = e.apply(&mut s, &CanonicalEvent::Mark {
        event_id: ev_id(2, "mark"), seq: 2, broker_ts: 1_750_000_001_000,
        symbol: "EURUSD".into(), px: "9199".into(),
    });
    assert_eq!(r.verdicts.len(), 1);
    let v = &r.verdicts[0];
    assert_eq!(v.rule, RuleId::DailyMaxLoss);
    assert_eq!(v.status, VerdictStatus::Breach);
    assert_eq!(v.inputs.threshold.as_deref(), Some("96000.00"));
    assert_eq!(v.inputs.equity.as_deref(), Some("95995"));
    assert!(s.day.daily_breached);

    // recovery: equity 99950 — still breached, NO new verdict, flag stays set
    let r2 = e.apply(&mut s, &CanonicalEvent::Mark {
        event_id: ev_id(3, "mark"), seq: 3, broker_ts: 1_750_000_002_000,
        symbol: "EURUSD".into(), px: "9999".into(),
    });
    assert!(r2.verdicts.is_empty(), "no un-breach, no duplicate: {:?}", r2.verdicts);
    assert!(s.day.daily_breached);
}

// ---------------------------------------------------------------------------
// g3: trailing HWM. +1200 close raises HWM to 101200; trailing floor = 91080.
//     Equity EXACTLY at the floor does not breach; 0.01 below does.
#[test]
fn g3_trailing_hwm_exact_threshold() {
    // daily 4%, trailing 10% off HWM, target 100% (never fires), no min days.
    let pack = serde_json::from_str::<RulePack>(
        r#"{
      "pack_id": "test:challenge:100k:trailing",
      "currency": "USD",
      "start_balance": 100000,
      "day": { "timezone": "Etc/UTC", "basis": "equity", "breach": "intraday" },
      "rules": {
        "max_daily_loss_pct": 4.0,
        "max_overall_loss_pct": { "mode": "trailing", "value": 10.0 },
        "profit_target_pct": 100.0,
        "min_trading_days": 0
      }
    }"#,
    )
    .expect("pack parses");
    let e = Engine::new(&pack).unwrap();
    let mut s = e.initial_state(ACCOUNT, DAY0);

    // +20000 realized: balance 120000, HWM 120000
    e.apply(&mut s, &CanonicalEvent::OrderFilled {
        event_id: ev_id(1, "fill"), seq: 1, broker_ts: 1_750_000_000_000,
        order_id: "o1".into(), deal_id: "d1".into(),
        symbol: "EURUSD".into(), side: Side::Buy, volume: 1.0,
        fill_px: "10000".into(), commission: "0".into(),
    });
    e.apply(&mut s, &CanonicalEvent::Mark {
        event_id: ev_id(2, "mark"), seq: 2, broker_ts: 1_750_000_001_000,
        symbol: "EURUSD".into(), px: "30000".into(),
    });
    let r = e.apply(&mut s, &CanonicalEvent::TradeClosed {
        event_id: ev_id(3, "close"), seq: 3, broker_ts: 1_750_000_002_000,
        order_id: "o1".into(), deal_id: "d2".into(),
        symbol: "EURUSD".into(), volume: 1.0,
        entry_px: "10000".into(), exit_px: "30000".into(),
        pnl_reported: "20000".into(), commission: "0".into(), swap: "0".into(),
    });
    assert!(r.verdicts.is_empty(), "{:?}", r.verdicts);
    assert_eq!(s.balance, d("120000"));
    assert_eq!(s.hwm, d("120000"), "HWM must trail to 120000");

    // open 12 @ 10000; mark 9000 -> upnl = (9000-10000)*12 = -12000
    // -> equity 108000 == trailing floor (120000 * 0.90) -> strict < : NO breach
    e.apply(&mut s, &CanonicalEvent::OrderFilled {
        event_id: ev_id(4, "fill"), seq: 4, broker_ts: 1_750_000_003_000,
        order_id: "o2".into(), deal_id: "d3".into(),
        symbol: "EURUSD".into(), side: Side::Buy, volume: 12.0,
        fill_px: "10000".into(), commission: "0".into(),
    });
    let r = e.apply(&mut s, &CanonicalEvent::Mark {
        event_id: ev_id(5, "mark"), seq: 5, broker_ts: 1_750_000_004_000,
        symbol: "EURUSD".into(), px: "9000".into(),
    });
    assert!(r.verdicts.is_empty(), "at-the-floor is not a breach: {:?}", r.verdicts);

    // mark 8999.99 -> upnl -12000.12 -> equity 107999.88 < 108000 -> BREACH
    let r = e.apply(&mut s, &CanonicalEvent::Mark {
        event_id: ev_id(6, "mark"), seq: 6, broker_ts: 1_750_000_005_000,
        symbol: "EURUSD".into(), px: "8999.99".into(),
    });
    assert_eq!(r.verdicts.len(), 1, "{:?}", r.verdicts);
    assert_eq!(r.verdicts[0].rule, RuleId::MaxOverallLoss);
    assert_eq!(r.verdicts[0].status, VerdictStatus::Breach);
    assert_eq!(r.verdicts[0].inputs.hwm.as_deref(), Some("120000"));
    assert_eq!(r.verdicts[0].inputs.threshold.as_deref(), Some("108000.00"));
    assert_eq!(r.verdicts[0].inputs.equity.as_deref(), Some("107999.88"));
    assert_eq!(r.verdicts[0].inputs.start_equity.as_deref(), Some("100000"));
}

// ---------------------------------------------------------------------------
// g4: min trading days gate the target. +2500/day for 4 days:
//     target (110000) is first *checkable* once day_counter reaches 4, which
//     happens at the 4th rollover — so it fires on the next event of day 5,
//     with day_counter input == 4.
#[test]
fn g4_min_days_gates_target() {
    let e = Engine::new(&pack_daily4()).unwrap(); // min_trading_days = 4
    let mut s = e.initial_state(ACCOUNT, DAY0);

    let mut ts = 1_750_000_000_000i64;
    let mut seq = 0u64;
    let mut n = 0u64;
    let mut next_ts = || { ts += 1000; ts };
    let mut next_seq = || { seq += 1; seq };
    let mut next_n = || { n += 1; n };

    let mut all_verdicts = Vec::new();
    let mut day_no = 0u32;
    for day in 1..=4u32 {
        day_no = day;
        let o = format!("o{day}");
        all_verdicts.extend(e.apply(&mut s, &CanonicalEvent::OrderFilled {
            event_id: ev_id(next_n(), "fill"), seq: next_seq(), broker_ts: next_ts(),
            order_id: o.clone(), deal_id: format!("d{day}"),
            symbol: "EURUSD".into(), side: Side::Buy, volume: 2.0,
            fill_px: "10000".into(), commission: "0".into(),
        }).verdicts);
        all_verdicts.extend(e.apply(&mut s, &CanonicalEvent::TradeClosed {
            event_id: ev_id(next_n(), "close"), seq: next_seq(), broker_ts: next_ts(),
            order_id: o, deal_id: format!("dc{day}"),
            symbol: "EURUSD".into(), volume: 2.0,
            entry_px: "10000".into(), exit_px: "11250".into(),
            pnl_reported: "2500".into(), commission: "0".into(), swap: "0".into(),
        }).verdicts);
        if day < 4 {
            let new_date = match day {
                1 => "2026-01-06".to_string(),
                _ => format!("2026-01-0{}", 5 + day),
            };
            all_verdicts.extend(e.apply(&mut s, &CanonicalEvent::Rollover {
                event_id: ev_id(next_n(), "roll"), seq: next_seq(), broker_ts: next_ts(),
                date: new_date,
            }).verdicts);
        }
    }
    // after day-4 close: balance 110000, counter still 3 (day 4 not rolled)
    assert_eq!(s.balance, d("110000"));
    assert_eq!(s.day_counter, 3);
    assert!(!s.target_reached, "target must not fire before min days are counted");

    // roll day 4 → counter 4, start_equity 110000 (day 5)
    all_verdicts.extend(e.apply(&mut s, &CanonicalEvent::Rollover {
        event_id: ev_id(next_n(), "roll"), seq: next_seq(), broker_ts: next_ts(),
        date: "2026-01-09".to_string(),
    }).verdicts);
    assert_eq!(s.day_counter, 4);
    assert!(!s.target_reached, "rollover itself does not run rule checks");

    // first event of day 5: a mark at current price → target fires
    let r = e.apply(&mut s, &CanonicalEvent::Mark {
        event_id: ev_id(next_n(), "mark"), seq: next_seq(), broker_ts: next_ts(),
        symbol: "EURUSD".into(), px: "11250".into(),
    });
    let targets: Vec<_> = r.verdicts.iter().filter(|v| v.rule == R::ProfitTarget).collect();
    assert_eq!(targets.len(), 1, "target must fire on first day-5 event: {:?}", r.verdicts);
    assert_eq!(targets[0].status, VerdictStatus::TargetReached);
    assert_eq!(targets[0].inputs.day_counter, Some(4));
    assert_eq!(targets[0].inputs.threshold.as_deref(), Some("110000.00"));
    let _ = day_no;
}

// ---------------------------------------------------------------------------
// g5: PnL cross-check. Reported 500 vs recomputed 200 → alert, ledger uses 200.
#[test]
fn g5_pnl_mismatch_alert_and_platform_truth() {
    let e = Engine::new(&pack_daily4()).unwrap();
    let mut s = e.initial_state(ACCOUNT, DAY0);

    e.apply(&mut s, &CanonicalEvent::OrderFilled {
        event_id: ev_id(1, "fill"), seq: 1, broker_ts: 1_750_000_000_000,
        order_id: "o1".into(), deal_id: "d1".into(),
        symbol: "EURUSD".into(), side: Side::Buy, volume: 1.0,
        fill_px: "10000".into(), commission: "0".into(),
    });
    let r = e.apply(&mut s, &CanonicalEvent::TradeClosed {
        event_id: ev_id(2, "close"), seq: 2, broker_ts: 1_750_000_001_000,
        order_id: "o1".into(), deal_id: "d2".into(),
        symbol: "EURUSD".into(), volume: 1.0,
        entry_px: "10000".into(), exit_px: "10200".into(),
        pnl_reported: "500".into(), commission: "0".into(), swap: "0".into(),
    });
    assert_eq!(r.integrity_alerts.len(), 1);
    assert_eq!(r.integrity_alerts[0].kind, "PNL_MISMATCH");
    assert!(r.integrity_alerts[0].detail.contains("500"));
    assert!(r.integrity_alerts[0].detail.contains("200"));
    assert_eq!(s.balance, d("100200"), "platform truth (recomputed) wins");
    assert!(r.verdicts.is_empty());
}

// ---------------------------------------------------------------------------
// g6: eod-breach pack. Intraday dip below the floor does NOT breach; the
//     rollover verdicts it from the day's worst equity. Rollover is idempotent.
#[test]
fn g6_eod_breach_judged_at_rollover_and_idempotent() {
    let e = Engine::new(&pack_eod_daily4()).unwrap();
    let mut s = e.initial_state(ACCOUNT, DAY0);

    // a traded day: +500 locked in
    e.apply(&mut s, &CanonicalEvent::OrderFilled {
        event_id: ev_id(1, "fill"), seq: 1, broker_ts: 1_750_000_000_000,
        order_id: "o1".into(), deal_id: "d1".into(),
        symbol: "EURUSD".into(), side: Side::Buy, volume: 2.0,
        fill_px: "10000".into(), commission: "0".into(),
    });
    e.apply(&mut s, &CanonicalEvent::TradeClosed {
        event_id: ev_id(2, "close"), seq: 2, broker_ts: 1_750_000_001_000,
        order_id: "o1".into(), deal_id: "d2".into(),
        symbol: "EURUSD".into(), volume: 2.0,
        entry_px: "10000".into(), exit_px: "10250".into(),
        pnl_reported: "500".into(), commission: "0".into(), swap: "0".into(),
    });
    // dip: open 5 @ 10250, mark 9250 → upnl -5000, equity 95500 < 96000 floor
    e.apply(&mut s, &CanonicalEvent::OrderFilled {
        event_id: ev_id(3, "fill"), seq: 3, broker_ts: 1_750_000_002_000,
        order_id: "o2".into(), deal_id: "d3".into(),
        symbol: "EURUSD".into(), side: Side::Buy, volume: 5.0,
        fill_px: "10250".into(), commission: "0".into(),
    });
    let r = e.apply(&mut s, &CanonicalEvent::Mark {
        event_id: ev_id(4, "mark"), seq: 4, broker_ts: 1_750_000_003_000,
        symbol: "EURUSD".into(), px: "9250".into(),
    });
    assert!(r.verdicts.is_empty(), "eod pack: no intraday verdict: {:?}", r.verdicts);
    assert!(!s.day.daily_breached);
    assert_eq!(s.day.worst_equity, d("95500"));
    // recover
    e.apply(&mut s, &CanonicalEvent::Mark {
        event_id: ev_id(5, "mark"), seq: 5, broker_ts: 1_750_000_004_000,
        symbol: "EURUSD".into(), px: "10200".into(),
    });

    // rollover: worst 95500 < 96000 → breach; day traded → counter 1
    let r = e.apply(&mut s, &CanonicalEvent::Rollover {
        event_id: ev_id(6, "roll"), seq: 6, broker_ts: 1_750_000_005_000,
        date: "2026-01-06".into(),
    });
    let breach = r.verdicts.iter().find(|v| v.rule == R::DailyMaxLoss);
    assert!(breach.is_some(), "rollover must judge the eod breach: {:?}", r.verdicts);
    assert_eq!(breach.unwrap().inputs.equity.as_deref(), Some("95500"));
    assert_eq!(breach.unwrap().inputs.threshold.as_deref(), Some("96000.00"));
    assert_eq!(s.day_counter, 1);
    assert_eq!(s.day.date, "2026-01-06");
    // new day starts from the equity at rollover: balance 100500 + upnl (10200-10250)*5 = -250
    assert_eq!(s.day.start_equity, d("100250"));

    // same rollover again → no-op
    let r2 = e.apply(&mut s, &CanonicalEvent::Rollover {
        event_id: ev_id(7, "roll"), seq: 7, broker_ts: 1_750_000_006_000,
        date: "2026-01-06".into(),
    });
    assert!(r2.verdicts.is_empty(), "rollover must be idempotent: {:?}", r2.verdicts);
    assert!(!r2.state_changed);
}

// ---------------------------------------------------------------------------
// g7: out-of-order close. Close delivered before its fill is buffered and
//     applied (at its own broker_ts) when the fill arrives.
#[test]
fn g7_close_before_fill_is_buffered_and_applied() {
    let e = Engine::new(&pack_daily4()).unwrap();
    let mut s = e.initial_state(ACCOUNT, DAY0);

    let close = CanonicalEvent::TradeClosed {
        event_id: ev_id(1, "close"), seq: 1, broker_ts: 1_750_000_001_000,
        order_id: "o1".into(), deal_id: "d2".into(),
        symbol: "EURUSD".into(), volume: 1.0,
        entry_px: "10000".into(), exit_px: "10100".into(),
        pnl_reported: "100".into(), commission: "0".into(), swap: "0".into(),
    };
    let r1 = e.apply(&mut s, &close);
    assert_eq!(r1.integrity_alerts.iter().map(|a| a.kind.as_str()).collect::<Vec<_>>(),
        vec!["CLOSE_DEFERRED"]);
    assert!(s.deferred_closes.len() == 1);
    assert_eq!(s.balance, d("100000"), "nothing applied yet");

    let open = CanonicalEvent::OrderFilled {
        event_id: ev_id(2, "fill"), seq: 2, broker_ts: 1_750_000_000_500,
        order_id: "o1".into(), deal_id: "d1".into(),
        symbol: "EURUSD".into(), side: Side::Buy, volume: 1.0,
        fill_px: "10000".into(), commission: "0".into(),
    };
    let r2 = e.apply(&mut s, &open);
    assert!(s.deferred_closes.is_empty(), "buffer must drain on matching fill");
    assert_eq!(s.balance, d("100100"), "deferred close must be applied (recomputed pnl)");
    assert!(s.positions.is_empty());
    assert_eq!(r2.verdicts.len(), 0);
}

//! Property tests for the rules engine (doc §13.2 — "the crown jewels").
//!
//! Every property is a *financial invariant*: a violation would mean the engine
//! can produce a wrong verdict or lose money. All streams are seeded/deterministic
//! (LCG in common/mod.rs), so failures reproduce with the printed seed.

mod common;
use std::str::FromStr;

use common::*;
use proptest::prelude::*;
use rules_engine::{Engine, Side};
use rust_decimal::Decimal;
use std::collections::BTreeMap;

fn opts_all(max: usize) -> GenOpts {
    GenOpts {
        max_events: max,
        allow_rollover: true,
        allow_news: true,
        allow_reports: true,
    }
}

/// Run a stream incrementally; returns (final state, verdicts, alert kinds).
fn run(stream: &[rules_engine::CanonicalEvent], pack: &rules_engine::pack::RulePack) -> (
    rules_engine::state::AccountState,
    Vec<rules_engine::verdict::Verdict>,
    Vec<String>,
) {
    let e = Engine::new(pack).unwrap();
    let mut state = e.initial_state(ACCOUNT, DAY0);
    let mut verdicts = Vec::new();
    let mut alert_kinds = Vec::new();
    for ev in stream {
        let res = e.apply(&mut state, ev);
        verdicts.extend(res.verdicts);
        for a in res.integrity_alerts {
            alert_kinds.push(a.kind);
        }
    }
    (state, verdicts, alert_kinds)
}

fn identity_set(verdicts: &[rules_engine::verdict::Verdict]) -> Vec<String> {
    let mut v: Vec<String> = verdicts.iter().map(|x| x.identity()).collect();
    v.sort();
    v
}

proptest! {
    // ------------------------------------------------------------------
    // 1. DETERMINISM (doc §13.2-1): same stream + same pack ⇒ bit-identical
    //    state and verdict fingerprints. Run twice on fresh states.
    #[test]
    fn determinism(seed in 1u64..u64::MAX, len in 1usize..=200) {
        let g = build_stream(seed, &opts_all(len));
        let pack = pack_daily4();
        let (s1, v1, a1) = run(&g.events, &pack);
        let (s2, v2, a2) = run(&g.events, &pack);
        prop_assert_eq!(s1, s2, "state must be bit-identical (seed {}, len {})", seed, len);
        prop_assert_eq!(
            v1.iter().map(|v| v.fingerprint()).collect::<Vec<_>>(),
            v2.iter().map(|v| v.fingerprint()).collect::<Vec<_>>(),
            "verdict fingerprints must be identical (seed {})", seed
        );
        prop_assert_eq!(a1, a2);
    }

    // ------------------------------------------------------------------
    // 2. REPLAY EQUIVALENCE (doc §13.2-2): incremental apply at every prefix ==
    //    replay-from-zero to that prefix. Same code path, same result.
    #[test]
    fn replay_equivalence(seed in 1u64..u64::MAX, len in 1usize..=120) {
        let g = build_stream(seed, &opts_all(len));
        let pack = pack_daily4();
        let compiled = rules_engine::pack::CompiledPack::compile(&pack).unwrap();
        // incremental states at every prefix (prefixes[0] = initial state,
        // prefixes[n] = state after the first n events)
        let e = Engine::new(&pack).unwrap();
        let mut state = e.initial_state(ACCOUNT, DAY0);
        let mut prefixes = vec![state.clone()];
        for ev in &g.events {
            e.apply(&mut state, ev);
            prefixes.push(state.clone());
        }
        // replay-from-zero at a few prefixes (0, n/2, n) — full prefix sweep is O(n^2)
        for n in [0usize, g.events.len() / 2, g.events.len()] {
            let replayed = rules_engine::replay::replay_prefix(ACCOUNT, &compiled, DAY0, &g.events, n);
            prop_assert_eq!(replayed, prefixes[n].clone(),
                "replay-to-{} must equal incremental state (seed {})", n, seed);
        }
    }

    // ------------------------------------------------------------------
    // 3. MONOTONE BREACH + IDEMPOTENCY (doc §13.2-3, §7.3):
    //    a daily breach never "un-breaches" within its day; no duplicate
    //    verdict identities; re-applying the whole stream changes nothing.
    #[test]
    fn monotone_breach_and_idempotency(seed in 1u64..u64::MAX, len in 1usize..=200) {
        let g = build_stream(seed, &opts_all(len));
        let pack = pack_daily4();

        // (a) monotonicity: a daily breach, once set, holds until the day rolls
        let e = Engine::new(&pack).unwrap();
        let mut state = e.initial_state(ACCOUNT, DAY0);
        for ev in &g.events {
            let day_before = state.day.date.clone();
            let breached_before = state.day.daily_breached;
            e.apply(&mut state, ev);
            if breached_before && state.day.date == day_before {
                prop_assert!(state.day.daily_breached,
                    "daily breach must be monotone within its day (seed {})", seed);
            }
        }

        // (b) verdict multiplicity: overall loss & target once per account;
        //     daily loss at most once per day
        let (s, v, _) = run(&g.events, &pack);
        let _ = s;
        let overall = v.iter().filter(|x| format!("{:?}", x.rule) == "MaxOverallLoss").count();
        let target = v.iter().filter(|x| format!("{:?}", x.rule) == "ProfitTarget").count();
        prop_assert!(overall <= 1, "overall loss verdicts must be once per account ({} , seed {})", overall, seed);
        prop_assert!(target <= 1, "target verdicts must be once per account ({} , seed {})", target, seed);
        let mut per_day: BTreeMap<String, u32> = BTreeMap::new();
        for x in v.iter().filter(|x| format!("{:?}", x.rule) == "DailyMaxLoss") {
            *per_day.entry(x.day.clone()).or_insert(0) += 1;
        }
        for (d, c) in &per_day {
            prop_assert!(*c <= 1, "daily breach twice on {} (seed {})", d, seed);
        }

        // (c) idempotency: duplicate the whole stream — state, verdicts, alerts unchanged
        let mut dup = g.events.clone();
        dup.extend_from_slice(&g.events);
        let (s_dup, v_dup, a_dup) = run(&dup, &pack);
        let (s1, v1, a1) = run(&g.events, &pack);
        prop_assert_eq!(s_dup, s1, "duplicated stream must leave state unchanged (seed {})", seed);
        prop_assert_eq!(v_dup.len(), v1.len(), "duplicated stream must not add verdicts");
        prop_assert_eq!(a_dup.len(), a1.len(), "duplicated stream must not add alerts");
    }

    // ------------------------------------------------------------------
    // 4. MONEY CONSERVATION (doc §13.2-4): at EVERY prefix,
    //    balance == start + Σ(open commissions) + Σ(closed recomputed pnl
    //    + commissions + swap) + Σ(adjustments). Exact decimals.
    #[test]
    fn money_conservation(seed in 1u64..u64::MAX, len in 1usize..=200) {
        let g = build_stream(seed, &opts_all(len));
        let pack = pack_daily4();
        let e = Engine::new(&pack).unwrap();
        let mut state = e.initial_state(ACCOUNT, DAY0);
        for (ev, expected) in g.events.iter().zip(g.expected_balance_after.iter()) {
            e.apply(&mut state, ev);
            prop_assert_eq!(state.balance, *expected,
                "money conservation broken at event {} (seed {})", ev.event_id(), seed);
        }
        // and at the end the builder's and the engine's final price agree with the book
        prop_assert_eq!(state.positions.len(), 0);
    }

    // ------------------------------------------------------------------
    // 5. PACK MONOTONICITY (doc §13.2-5): widening loss limits never produces
    //    MORE loss breaches. (State evolution is identical; thresholds nest.)
    #[test]
    fn pack_monotonicity(seed in 1u64..u64::MAX, len in 1usize..=200) {
        let g = build_stream(seed, &opts_all(len));
        let tight = pack_daily4();  // daily 4% / overall 8%
        let loose = pack_daily8();  // daily 8% / overall 16%
        let (_, v_tight, _) = run(&g.events, &tight);
        let (_, v_loose, _) = run(&g.events, &loose);
        let count = |v: &[rules_engine::verdict::Verdict], r: &str, s: &str| {
            v.iter().filter(|v|
                format!("{:?}", v.rule) == r && format!("{:?}", v.status) == s
            ).count()
        };
        let d_t = count(&v_tight, "DailyMaxLoss", "Breach");
        let d_l = count(&v_loose, "DailyMaxLoss", "Breach");
        let o_t = count(&v_tight, "MaxOverallLoss", "Breach");
        let o_l = count(&v_loose, "MaxOverallLoss", "Breach");
        prop_assert!(d_t >= d_l, "tight pack must breach daily >= loose ({d_t} vs {d_l}, seed {seed})");
        prop_assert!(o_t >= o_l, "tight pack must breach overall >= loose ({o_t} vs {o_l}, seed {seed})");
    }

    // ------------------------------------------------------------------
    // 6. DELIVERY-ORDER ROBUSTNESS (doc §13.2-6, §7.1): shuffling the delivery
    //    order of a single-day, well-formed stream must NOT change
    //      - final ledger balance,
    //      - final position book,
    //      - per-deal integrity findings (PNL_MISMATCH).
    //    NOTE: breach/target *verdicts* are deliberately NOT asserted invariant:
    //    whether intraday equity ever crosses a floor depends on which marks
    //    coincide with which position books — a delivery-order property, by
    //    design (doc §6.6). Only the terminal state and per-deal findings are
    //    delivery-invariant.
    #[test]
    fn reorder_robustness_single_day(seed in 1u64..u64::MAX, len in 1usize..=120) {
        let opts = GenOpts {
            max_events: len,
            allow_rollover: false,
            allow_news: false,      // windows are order-sensitive by nature
            allow_reports: false,   // drift vs moving balance is order-sensitive
        };
        let g = build_stream(seed, &opts);
        let pack = pack_daily4();
        let (base, v_base, a_base) = run(&g.events, &pack);

        let mismatches_base = a_base.iter().filter(|k| k.as_str() == "PNL_MISMATCH").count();

        let mut rng = common::Rng::new(seed ^ 0xA5A5);
        for _trial in 0..4 {
            let mut shuffled = g.events.clone();
            for i in (1..shuffled.len()).rev() {
                let j = rng.range(0, i as u64) as usize;
                shuffled.swap(i, j);
            }
            let (s, v, a) = run(&shuffled, &pack);
            prop_assert_eq!(s.balance, base.balance,
                "final balance must be delivery-order independent (seed {})", seed);
            prop_assert_eq!(position_book(&s), position_book(&base),
                "final position book must be delivery-order independent (seed {})", seed);
            // (verdict identity set is path-dependent by design — not asserted here)
            let m = a.iter().filter(|k| k.as_str() == "PNL_MISMATCH").count();
            prop_assert_eq!(m, mismatches_base,
                "per-deal PnL mismatch findings must be order independent (seed {})", seed);
        }
    }

    // ------------------------------------------------------------------
    // 7. DECIMAL EXACTNESS (doc §13.2-7): the recomputed PnL must equal
    //    hand-computed (exit - entry) * volume in exact decimals — for fuzzed
    //    price/volume inputs, with the mismatch surfaced as an alert whose
    //    "recomputed" field carries the exact value.
    #[test]
    fn decimal_exactness(entry in 9000u64..12000, exit in 8000u64..13000, vol_i in 1u64..=50) {
        let entry = Decimal::from(entry) / Decimal::from(100u64); // e.g. 100.12
        let exit = Decimal::from(exit) / Decimal::from(100u64);
        let vol = Decimal::from(vol_i) / Decimal::from(10u64);   // e.g. 3.7

        let pack = pack_daily4();
        let e = Engine::new(&pack).unwrap();
        let mut state = e.initial_state(ACCOUNT, DAY0);

        let ev_open = rules_engine::CanonicalEvent::OrderFilled {
            event_id: "e-open".into(), seq: 1, broker_ts: 1_750_000_000_000,
            order_id: "o1".into(), deal_id: "d1".into(),
            symbol: "EURUSD".into(), side: Side::Buy,
            volume: f64::try_from(vol).unwrap(), fill_px: entry.to_string(), commission: "0".into(),
        };
        let ev_close = rules_engine::CanonicalEvent::TradeClosed {
            event_id: "e-close".into(), seq: 2, broker_ts: 1_750_000_001_000,
            order_id: "o1".into(), deal_id: "d2".into(),
            symbol: "EURUSD".into(), volume: f64::try_from(vol).unwrap(),
            entry_px: entry.to_string(), exit_px: exit.to_string(),
            pnl_reported: "0".into(), commission: "0".into(), swap: "0".into(),
        };
        let r1 = e.apply(&mut state, &ev_open);
        prop_assert!(r1.integrity_alerts.is_empty());
        let r2 = e.apply(&mut state, &ev_close);

        // Mirror the engine exactly: prices parsed from the wire strings,
        // volume through the f64 wire round-trip (from_f64_retain).
        let vol_wire = f64::try_from(vol).unwrap();
        let vol_engine = Decimal::from_f64_retain(vol_wire).unwrap();
        let entry_engine = Decimal::from_str(&entry.to_string()).unwrap();
        let exit_engine = Decimal::from_str(&exit.to_string()).unwrap();
        let expected_pnl = (exit_engine - entry_engine) * vol_engine;
        // reported 0 => alert expected exactly when |pnl| > tolerance
        if expected_pnl.abs() > Decimal::new(1, 2) {
            let alert = r2.integrity_alerts.iter()
                .find(|a| a.kind == "PNL_MISMATCH")
                .expect("mismatch alert must fire");
            prop_assert!(
                alert.detail.contains(&expected_pnl.to_string()),
                "alert must carry the exact recomputed value: {}", alert.detail
            );
        }
        // ledger reflects the EXACT recomputed value, never the reported one
        prop_assert_eq!(state.balance, Decimal::from(100_000u64) + expected_pnl);
    }
}

// ---------------------------------------------------------------------------
// Determinism of the stream builder itself (guard against "flaky" properties):
// same seed ⇒ byte-identical event stream.
#[test]
fn builder_is_deterministic() {
    let a = build_stream(42, &opts_all(100));
    let b = build_stream(42, &opts_all(100));
    assert_eq!(a.events, b.events);
    assert_eq!(a.expected_balance_after, b.expected_balance_after);
}

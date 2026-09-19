//! replay-tool — dispute/backfill/migration workhorse (doc §6.7, §7.2).
//!
//! ```text
//! replay-tool --pack contracts/samples/challenge_100k.json \
//!             --events examples/sample-events.jsonl \
//!             [--account acct-0001] [--day 2026-01-05] [--json]
//! ```
//!
//! Same `apply` as the live consumer — this is the "replay is the same code
//! path" guarantee made usable from a shell. Exit code 0 always (it is a
//! reporting tool); CI gates compare its output.

use rules_engine::events::CanonicalEvent;
use rules_engine::pack::RulePack;
use rules_engine::Engine;
use std::collections::BTreeMap;
use std::process::ExitCode;

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let mut pack_path = None;
    let mut events_path = None;
    let mut account = "acct-0001".to_string();
    let mut day = "2026-01-05".to_string();
    let mut json_out = false;

    let mut i = 0;
    while i < args.len() {
        match args[i].as_str() {
            "--pack" => { i += 1; pack_path = args.get(i).cloned(); }
            "--events" => { i += 1; events_path = args.get(i).cloned(); }
            "--account" => { i += 1; account = args.get(i).cloned().unwrap_or_default(); }
            "--day" => { i += 1; day = args.get(i).cloned().unwrap_or_default(); }
            "--json" => json_out = true,
            other => { eprintln!("unknown arg {other}"); return ExitCode::from(2); }
        }
        i += 1;
    }
    let (pack_path, events_path) = match (pack_path, events_path) {
        (Some(p), Some(e)) => (p, e),
        _ => {
            eprintln!("usage: replay-tool --pack <json> --events <jsonl> [--account a] [--day d] [--json]");
            return ExitCode::from(2);
        }
    };

    let pack_json = match std::fs::read_to_string(&pack_path) {
        Ok(s) => s,
        Err(e) => { eprintln!("cannot read pack: {e}"); return ExitCode::from(1); }
    };
    let pack: RulePack = match serde_json::from_str(&pack_json) {
        Ok(p) => p,
        Err(e) => { eprintln!("invalid pack: {e}"); return ExitCode::from(1); }
    };
    let engine = match Engine::new(&pack) {
        Ok(e) => e,
        Err(e) => { eprintln!("pack failed to compile: {e}"); return ExitCode::from(1); }
    };

    let events_text = match std::fs::read_to_string(&events_path) {
        Ok(s) => s,
        Err(e) => { eprintln!("cannot read events: {e}"); return ExitCode::from(1); }
    };
    let mut events = Vec::new();
    for (n, line) in events_text.lines().enumerate() {
        let line = line.trim();
        if line.is_empty() { continue; }
        match serde_json::from_str::<CanonicalEvent>(line) {
            Ok(ev) => events.push(ev),
            Err(e) => { eprintln!("line {}: invalid event: {e}", n + 1); return ExitCode::from(1); }
        }
    }

    let mut state = engine.initial_state(&account, &day);
    let mut verdicts = Vec::new();
    let mut alerts: BTreeMap<String, u32> = BTreeMap::new();

    for ev in &events {
        let res = engine.apply(&mut state, ev);
        for a in res.integrity_alerts {
            *alerts.entry(a.kind).or_insert(0) += 1;
        }
        verdicts.extend(res.verdicts);
    }

    if json_out {
        #[derive(serde::Serialize)]
        struct Report<'a> {
            account: &'a str,
            pack: &'a str,
            events: usize,
            final_state: &'a rules_engine::state::AccountState,
            verdicts: &'a Vec<rules_engine::verdict::Verdict>,
            integrity_alerts: &'a BTreeMap<String, u32>,
        }
        let rep = Report {
            account: &account,
            pack: &engine.pack().pack_id,
            events: events.len(),
            final_state: &state,
            verdicts: &verdicts,
            integrity_alerts: &alerts,
        };
        println!("{}", serde_json::to_string_pretty(&rep).unwrap());
    } else {
        println!("== replay: {account} under {} ==", engine.pack().pack_id);
        println!("events: {}", events.len());
        println!();
        println!("verdicts:");
        if verdicts.is_empty() {
            println!("  (none)");
        }
        for v in &verdicts {
            println!(
                "  [ts={}] {:?} day={} status={:?}  eq={} thr={} start={} hwm={} dc={}",
                v.broker_ts,
                v.rule,
                v.day,
                v.status,
                v.inputs.equity.as_deref().unwrap_or("-"),
                v.inputs.threshold.as_deref().unwrap_or("-"),
                v.inputs.start_equity.as_deref().unwrap_or("-"),
                v.inputs.hwm.as_deref().unwrap_or("-"),
                v.inputs.day_counter.map(|v| v.to_string()).unwrap_or_default(),
            );
        }
        if !alerts.is_empty() {
            println!();
            println!("integrity alerts:");
            for (k, c) in &alerts {
                println!("  {k}: {c}");
            }
        }
        println!();
        println!(
            "final: balance={} equity={} hwm={} day_counter={} day={} positions={}",
            state.balance,
            state.equity(),
            state.hwm,
            state.day_counter,
            state.day.date,
            state.positions.len(),
        );
    }
    ExitCode::SUCCESS
}

## 13. Testing Strategy and the Simulation Harness

### 13.1 Testing pyramid for a rules-critical system

```
        ╱‾‾‾‾E2E: full pipeline vs sim broker, scenario DSL, nightly + canary gate╲
      ╱‾‾‾contract tests: every adapter ↔ canonical schema (pact-style), per build╲
    ╱‾‾‾‾property + golden-file tests: rules engine (the crown jewels), per commit╲
  ╱‾‾‾‾‾‾‾‾‾‾unit: guard, adapters, services, packs compiler, per commit (fast)╲
```

### 13.2 The crown jewel: rules-engine property tests (Rust, `proptest`)

Properties that must hold for *all* generated event streams (thousands per run, seeded and reproducible):

1. **Determinism**: same stream + same pack ⇒ bit-identical verdicts and state (run twice, compare).
2. **Replay equivalence**: state after replay-from-zero == state after incremental apply, for any prefix.
3. **Monotone breach**: once `DailyMaxLoss` is breached (intraday mode), no later event can un-breach that day.
4. **Money conservation**: for any stream, `ledger.balance == start + Σ(closed_pnl + commission + swap + adjustments)` — the double-entry invariant, checked at every step.
5. **Pack sanity**: compiling a pack is total (no panics); pack A tightened (larger loss limit) never produces *more* breaches than pack B (directional monotonicity where defined).
6. **Clock robustness**: reordering *delivery* of events (keeping `broker_ts`) must not change verdicts, except via the documented retroactive-apply rules (which are themselves tested as explicit cases).
7. **Decimal exactness**: all assertions on `Decimal`, never float; a fuzz input that makes `f64` disagree with `Decimal` fails the build.

Plus **golden files**: recorded production-like streams (anonymized) with hand-verified expected verdicts, checked every commit — these encode the *business* semantics the properties can't express ("trader who closes at 23:59:58 with broker_ts counts for that day — yes").

### 13.3 Adapter contract tests

For each platform adapter: a corpus of captured wire messages (real, anonymized) in `testcorpora/{mt4,mt5,ctrader,dxtrade}/` → decode → assert canonical equality; and the inverse: canonical event → encode → golden wire bytes. New EA/cBot releases run the corpus before publication. Fuzz the decoders (malformed, truncated, huge, unicode-hostile inputs) — a crashing bridge node on one weird message is a fleet incident.

### 13.4 The simulation harness (Rust) — the moat

**What it is**: a deterministic broker simulator + terminal emulator fleet that drives the *real* production pipeline (bridge → Kafka → engine → services → PG/CH) in CI/stage, with a scenario DSL:

```rust
// scenarios/nfp_spike.msl  (pseudo-DSL, compiled to a scenario binary)
market EURUSD base 1.0850 vol(0.2 pips/s)
event news(NFP, at t=10m, impact: [EURUSD, DXY, indices])
  spread_before 1.2 pips, spread_at_event 18 pips, gap ±8 pips, vol ×6 for 90s
accounts 500 {
  450 profile(retail_active)          // 2–10 orders/h, TP/SL, weekday rhythm
  40  profile(high_frequency)         // news snipers: fire within 200 ms of print
  10  profile(martingale)             // doubling grid — must trip consistency rules
}
terminal_profiles {
  60% stable_link, 25% flaky (drop 5% of windows 2–20 s), 10% malicious
}
malicious {
  "pnl_spoof": reports pnl = real_pnl × 0.5 on 30% of closes (must trigger integrity alerts, zero wrong verdicts)
  "clock_rewind": broker_ts − 120 s on 5% of events (must be flagged, not trusted)
  "replay": re-sends yesterday's deal ids (must be idempotent no-ops)
}
assert {
  zero_lost_events,
  verdicts_match_oracle,        // independent slow oracle (Rust reference, different impl)
  halt_delivery_p99 < 200ms,
  reconciliation_drift == 0 at t+5m,
  no_cross_tenant_access        // two tenants in one scenario
}
```

**Why it wins**: (1) it's *deterministic* (seeded RNG, virtual clocks) — every incident is reproducible; (2) it generates **ground truth** (the sim knows what "happened") so the pipeline's output is *asserted*, not eyeballed; (3) it includes adversarial personas, which no manual test will ever sustain; (4) it's the load generator (9.5), the canary gate, and the DR drill — one tool, four jobs. Build it in week 1 as a stub, grow it every sprint; it is the highest-leverage engineering artifact in this project.

### 13.5 E2E & chaos

- Nightly E2E in stage: scenario DSL → full pipeline → assertions; canary releases in prod run a reduced corpus against 5 % of accounts with shadow assertions (compare shadow vs live verdicts; divergence = auto-rollback).
- Chaos: quarterly game-days per runbook (Section 12.4) — the harness *is* the referee: after "Kafka down 10 min", it asserts zero lost events and correct retroactive verdicts.
- **Dispute drills**: quarterly, pick a real (anonymized) dispute, run the evidence-pack generator, have the risk team settle it using *only* the generated pack. If a pack can't settle its own dispute, the audit pipeline is broken.

### 13.6 Security testing

- AuthN/Z and replay tests in CI (the guard's test suite *is* the T1–T3 regression net);
- OWASP ASVS L2 target for all web surfaces, annual third-party pentest (bridge protocol gets custom test cases: the default pentest kit doesn't know what an MQL5 EA is);
- Dependency: `cargo audit` / `npm audit` / Go vuln, SBOM per artifact, image signing + admission policy;
- Threat-model reviews at each major feature (the STRIDE table from Section 8.1 is a living document, not a one-time artifact).

### 13.7 Data quality & golden paths

- Synthetic tenant in dev/stage: 1,000 simulated traders with known "true" outcomes (the harness computes them independently) — the platform's *reporting* (pass rates, PnL, payouts) is diffed against truth every run. This catches the entire class of "the dashboard says the firm made money it didn't" bugs, which in production are *financial restatements*.

---

## 12. Operations, Observability, and Runbooks

### 12.1 Operating model

- **You operate three products**: the platform (SaaS for tenants), the bridge fleet (the supervision plane), and the evidence pipeline (the trust plane). The last one has its own on-call rotation — *audit pipeline down* is P1 even if traders see nothing, because disputes cannot be settled without it.
- **Environments**: `dev` (sim-harness-driven, ephemeral), `stage` (full topology, synthetic tenants, chaos-safe), `prod` (multi-tenant), plus **canary tenants** (real small tenants on pre-prod bridge builds — the only honest way to test bridge releases against real terminals).
- **Change discipline**: all changes via GitOps; bridge releases canary (5 % accounts) → 25 % → 100 % with SLO burn + seq-gap rate as auto-rollback gates; rule-pack changes require tenant approval + (for funded scope) risk-officer sign-off; schema migrations are expand/contract (dual-write window, no big-bang).

### 12.2 SLOs and the metrics that mean something

| SLO | Target | Measurement |
|---|---|---|
| Bridge plane availability | 99.95 %/mo | LB success rate on hello/auth + WS message flow |
| Verdict freshness (fill → verdict) | p99 < 150 ms, p99.9 < 500 ms | Kafka→engine latency histogram per account |
| Zero cross-tenant data access | 100 % | integration test suite + query audit log (RLS denials) |
| Zero lost evidence | 0 | spool accounting + reconciliation drift = 0 beyond tolerance |
| Rollover completeness | 100 % within 5 min of rollover | `RolloverCompleted` count vs active accounts |
| Reconciliation clean | 100 % within 24 h | drift ledger age |
| Control delivery (halt) | p99 < 200 ms (connected) | control-topic → terminal ack |
| Resync p95 | < 3 s (≤ 200 positions) | resync duration histogram |

**Error budgets**: bridge canary rolls pause automatically at 50 % budget burn in the window; verdict-freshness burn pages the Rust team; cross-tenant *denial spikes* (not successes) page security — a sudden wave of RLS denials is a bug or an attack.

### 12.3 Alerting philosophy

Page on **user-money-relevant uncertainty**, not on load. Load is dashboards; uncertainty is pages. Concretely: DLQ age > 5 min (missing evidence), reconciliation drift beyond tolerance (P ≠ B), Kafka consumer lag on `bridge.events` > 30 s (verdicts deferring), spool-occupancy p95 > 25 % of capacity (fleet about to lose data), NTP offset > 50 ms (clock discipline = replay defense), halt commands unacked > 60 s across > 1 % of halted accounts.

### 12.4 Runbooks (the six that matter)

1. **Resync storm** (post-incident mass reconnect): throttle snapshot chunks per account; prioritize funded accounts; watch PG apply rate; declare "evidence integrity window" in audit for the period.
2. **Kafka partition backlog / broker death**: consumer groups fail over (managed); verify `seq_applied` watermarks; on catch-up, the rules engine re-applies from watermark (pure apply — safe); confirm zero `integrity_alert` spikes; publish incident note to affected tenants if any verdicts were deferred (transparency is a contractual and trust asset).
3. **Broker outage**: flag accounts `broker_down`; pause rules clock (no verdicts — no wrong verdicts); on recovery: force full rescan + diff for all accounts; tight reconciliation for 2 h; auto-generated outage-window audit record.
4. **Suspected malicious EA** (impossible PnL / tamper signatures): auto-halt (config), preserve evidence (snapshot of raw events + pairing record + fingerprint), risk-desk case with evidence pack, pairing revocation, tenant notification (they own the trader relationship), post-mortem of the detector (tune thresholds on the sim harness before re-tightening).
5. **Payout provider incident**: idempotency keys prevent double-send; reconcile provider statement vs ledger same-day; manual-queue workflow with 4-eyes for any manual correction; never "fix" a ledger row — corrections are entries.
6. **Cross-tenant exposure (suspected)**: freeze (read-only mode) for involved tenants, RLS audit trace, contract-law + security triage in parallel, evidence preservation to object storage *before* any fix.

### 12.5 Capacity & cost operations

- Weekly capacity review from ClickHouse metering: connections, msg/s, storage growth per tenant → plan node counts 2 quarters ahead; tenant metering is *also* the billing input (bill on active traders + message volume above plan).
- Cost model (reference fleet, AWS us-east): bridge 8 nodes × 4vCPU ≈ $4–6k/mo; Kafka (3× managed) ≈ $1.5–2.5k; PG + Redis + CH ≈ $2–4k; object storage (7 y evidence) ≈ $0.5–1.5k; observability + misc ≈ $1–2k → **≈ $10–16k/mo infrastructure at 25k traders**, scaling ~linearly per 25k traders. (Recalculate with your cloud; the shape — bridge nodes + Kafka + PG/CH dominate — is stable.)

### 12.6 Incident management & post-mortems

- SEV ladder: SEV1 (money at risk: hedge drift uncontrolled, cross-tenant exposure, evidence loss), SEV2 (supervision degraded: verdict deferrals > 10 min, resync storms), SEV3 (degraded, contained).
- Every SEV1/2 → written post-mortem within 5 days, **and the incident becomes a sim-harness scenario** (regression-tested forever). This loop — incident → scenario → CI — is what makes a platform in this domain mature; it's the direct analog of how payment processors operate.

---

## 9. Scalability, Performance, and Latency Budgets

### 9.1 Load model (sizing assumptions — recalculate per tenant mix)

**Reference fleet**: 10 tenants, 25,000 registered traders, 6,000 concurrently active accounts during peak (FX NY/London overlap), 40% on MT5-EA/REST, 35% MT5/WS-proxy or cBot-WS, 25% server-side (cTrader/DXtrade).

| Signal | Rate (peak) | Notes |
|---|---|---|
| `order_intent` + `order_filled` | ~40 msg/s fleet (10/s burst) | spikes around news: 10× for seconds |
| `position_closed` / `order_modified` | ~15 msg/s | |
| `account_state` pushes | 1/s per connected account ≈ 6k msg/s steady | the *volume* driver; make it adaptive: push on change > 10 bps or 5 s max interval |
| heartbeats | 2 × 6k / 10 s = 1.2k msg/s | tiny; batchable |
| Control commands | < 1/s average, bursty on halts (1k accounts at once = fan-out event) | |
| Quote feeds (if enabled) | 50 instruments × 20/s = 1k/s | opt-in per tenant |
| **Total ingest** | **~8–10k msg/s steady, 30k/s burst** | one bridge node: ≥ 5k msg/s (Go+Rust, measured in the sim harness) → 4–6 nodes at peak, 3× headroom |
| Kafka | 1.5 MB/s compressed steady | 3 brokers, trivial |
| ClickHouse ingest | ticks (opt-in) 1k rows/s; trades+verdicts 100 rows/s | trivial; the storage that grows is *evidence* (raw events, ~5 GB/day at reference scale, LZ4) |

**The bridge is sized by connections and message rate, not by CPU.** 6k–50k concurrent WS connections: one node per ~8k idle connections (tokio/go runtime, 2 vCPU); plan 6–10 nodes at 50k. Memory ≈ 2 MB/connection worst case (buffers + session) → 100 GB at 50k — shard, don't oversize.

### 9.2 Latency budget (critical path: order)

```
Trader click ──[0-20ms]──▶ EA local fast-fail (L0)
  ──[20-60ms, network]──▶ Bridge edge checks (L1): HMAC verify ~1µs, seq, halt-flag (Redis local cache, 50ms staleness)
  ──[20-60ms, network]──▶ EA OrderSend
  ──[10-100ms]──▶ Broker execution + fill
  ──[20-60ms]──▶ Bridge ingests order_filled, guard
  ──[10-50ms]──▶ Kafka partition (account)
  ──[5-30ms]──▶ Rules engine applies, verdict emitted
Total: intent→allow ~40–120 ms (network-dominated); fill→verdict p99 < 150 ms
```

Budget rules: (1) nothing in L1 may touch PG — halt flags, pack version, and quote caps live in node-local cache refreshed from Redis (≤ 50 ms stale, acceptable: L2 is truth); (2) HMAC verify and canonicalization are the only per-message allocations in the hot path (Rust, pool-allocated); (3) Kafka produce with `acks=all, linger.ms=5, batch=32KB` on `bridge.events` — ordering within account is preserved by single-partition-per-account + single producer thread per account shard.

### 9.3 Data growth & retention

| Dataset | Growth (reference) | Hot | Cold |
|---|---|---|---|
| Raw events (evidence) | ~5 GB/d | 90 d (CH) | 7 y (S3, immutable, zstd) |
| Ticks (opt-in) | ~10 GB/d | 14 d | 1 y (S3) |
| Closed trades | ~200 MB/d | 2 y | 7 y |
| Audit chain | ~500 MB/d | 1 y | 7–10 y (jurisdiction-dependent) |
| Ledger / snapshots | ~50 MB/d | forever | PITR backups 35 d |

### 9.4 Capacity patterns that break prop-firm platforms (learned from the industry)

1. **News spikes**: NFP/CPI → order rates 10–20× for 30–60 s *and* quote rates 100×. The bridge must absorb without queueing into the broker (it doesn't route execution — good), but L1 must pre-reject at full rate: keep the intent path allocation-free and test at 50× sustained.
2. **Rollover thundering herd**: 10k accounts roll over in the same minute. Sharded leases + per-tenant offsets (spread rollover checks across 10 min by hash(account)) → constant CPU instead of a spike.
3. **Halt fan-out**: one tenant halts 5k accounts → 5k control pushes in seconds. Fan-out goes through Kafka control topic (partitioned by account), bridge pushes are async, no synchronous waits — a halt *command* is durable (PG) even if 100% of pushes are delayed.
4. **Snapshot storms after an incident**: 10k reconnects in 5 min → 10k snapshots. Chunks are rate-limited per account (2/s), snapshots are *the* backpressure valve: shed heartbeat bandwidth first, never trade telemetry.
5. **Weekend effect**: Friday 21:00 cutoff → `close_all` on 5k positions → 5k fills in minutes → 5k `position_closed` events + reconciliation load. The cutoff itself is batched (hash-sharded across 10 min) and reconciliation cadence auto-tightens for 1 h after.

### 9.5 Load & performance testing targets

- Bridge node: 5k msg/s × 30 min @ < 1% error, p99 intent→allow < 25 ms (sim-harness generator, Section 13.4).
- Fleet chaos: kill bridge node with 8k connections → 100% resync in < 60 s p95, zero lost events (asserted against harness ground truth).
- Kafka lag injection: +5 min partition lag → rules verdicts defer (clock pause verified), no incorrect verdicts, catch-up re-applies cleanly (property test).
- Rollover: 50k accounts simulated → 100% within 5 min, PG p99 query time flat (no row-lock storms).
- Soak: 14 d continuous at 80% peak → memory flat (leak radar), Redis memory bounded (TTL discipline), CH compression ratio stable.

---

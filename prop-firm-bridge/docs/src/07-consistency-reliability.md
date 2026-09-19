## 7. Consistency, Correctness, and Reliability

### 7.1 The two-truths problem, formally

Let **B** = broker state (positions, deals, balances as the broker server sees them) and **P** = platform state (ledger, positions model, day snapshots, verdicts). The bridge continuously maps B → P (telemetry), reconciliation periodically verifies P ≈ B, and control commands push P → B-adjacent effects (halts, close-all at the terminal). Correctness requirements:

1. **Liveness**: every broker-side event for a supervised account eventually reaches P (spool + reconnect + `events_since` + periodic full rescan).
2. **Soundness**: P never contains a position/deal that B doesn't (no phantom PnL) — enforced by deal-id ingestion only (P is built *from* B-attested deals) and by reconciliation deleting orphans (with audit).
3. **Completeness at decision time**: a verdict is only rendered when P's input for the decision horizon is complete; if the input is uncertain (e.g., 40 s gap), the verdict is *deferred* (rules clock pauses for that account) — a deferred breach is better than a wrong one, and the deferral is recorded.

### 7.2 Event sourcing for the trading domain

- `bridge.events` (canonical, Kafka → ClickHouse → immutable object storage) **is** the event log. PostgreSQL is a *materialized view* of it (consumers with outbox + idempotent apply).
- Any PG row can be regenerated: `replay(account, from_ts, to_ts)` — a first-class ops command, used for incident repair, tenant audits, and dispute packs.
- **Offset discipline**: each consumer group tracks per-partition offsets; the rules engine additionally stores `seq_applied` per account in Redis/PG so it can self-heal after lag (re-read from `seq_applied` if a watermark mismatch is detected).
- **Dead-letter queues** per consumer: any event that fails apply 5× goes to DLQ with the full error + envelope; DLQ age > 5 min pages. A DLQ'd trade event is a P0 by definition (missing evidence).

### 7.3 Idempotency & exactly-once *effect*

Delivery is at-least-once everywhere (Kafka, WS pushes, retries). Exactly-once *effect* is achieved by:

- **Natural keys**: `(account, deal_id)` for trade events; `(account, date)` for rollovers; `(application_id)` for payouts/funding; all with **unique constraints** — duplicates collapse into no-ops that return the original result.
- **Idempotency keys on mutations** (HTTP and control): client sends `Idempotency-Key` header/field; server stores result for 24 h.
- **No side effects on read paths**: verdict emission happens only inside the apply transaction (PG write + Kafka publish via **transactional outbox** polled by a relay — at-least-once publish, exactly-once effect downstream via idempotency).

### 7.4 Reconciliation (the heartbeat of trust)

{{DIAG:08-reconnect-resync}} *(the reactive, per-connection half)*

The proactive half, run by the **Reconciliation Service (Go)**:

| Loop | Cadence | Method | Action on mismatch |
|---|---|---|---|
| Event-level | continuous | each ingested deal cross-checked against stored entry/exit | alert (integrity) → auto-correct PnL from B |
| Position diff | 60 s (connected), 5 min (disconnected) | B positions (EA collect or server API) vs P positions | phantom in P → delete + audit; missing in P → ingest + audit + page if > 2 min |
| Full account state | hourly (rolling shard) | balances, margin, full closed-deal scan since last full sync | ledger drift: ≤ 0.01% → auto-correct with reason; more → page |
| Broker history audit | daily per account (off-peak) | full `HistorySelect` since account creation vs ClickHouse evidence | the canonical audit record per account per day |
| Funded hedge drift | 10 s | funded position vs hedge position (fill-aware tolerance: 1 tick + 100 ms) | auto-rebalance order; drift > threshold → suspend trader account + risk page |

Reconciliation output is itself an event (`reconciliation_result`), so the *auditors of the auditors* can be audited. Every correction carries `(cause, before, after, evidence_ids)` in the hash-chained audit log.

### 7.5 Failure-mode matrix

| Failure | Detection | Behavior | Trader sees |
|---|---|---|---|
| WS drop (trader) | heartbeat 3×10 s | client spools; backoff 1 s→30 s jittered; resync on return | nothing, if < few seconds |
| Bridge node crash | LB health, Kafka consumer lag | other nodes serve; sessions in Redis | sub-second |
| Kafka partition lag | consumer-lag SLO alert | rules verdicts **defer** (per-account clock pause), no wrong verdicts; replay on catch-up | nothing (trading continues at broker) |
| PG primary failover | HA manager | read-replica promotion; outbox relay pauses; at-least-once consumers re-apply | sub-minute |
| Broker server outage | terminal reports, API 5xx | all accounts `broker_down` flag; rules clock paused; no verdicts; on recovery → full rescan + diff | "platform unavailable" notice |
| Stale/buggy EA version | `client_diagnostics`, schema mismatch | pin: force `set_param` refetch; if still bad → degrade to REST polling with tighter heartbeat; if tamper-suspected → pairing revocation + fraud review | update prompt |
| Clock skew (bridge node) | NTP offset > 50 ms | node ejected from LB; its in-flight sessions resume elsewhere (Redis registry) | nothing |
| Tenant billing overdue | billing svc | plan: grace → read-only → suspend new challenges (funded accounts always keep full service — contractual) | notice |
| Malicious client (patched EA) | signature valid but *content* anomalies: impossible PnL, broker_ts regressions, EA hash mismatch, device fingerprint change | integrity alerts → auto-halt (config) → risk review with evidence pack | halt notice |

### 7.6 Sagas for multi-step provisioning

Funding (Section 2.3) and payouts are **sagas** — sequences of local transactions with compensations:

{{DIAG:10-funding-provisioning}}

- Every saga step is a row in `saga_steps` `(saga_id, step, status, payload, compensation)`; a worker advances steps, and on failure runs compensations in reverse order with retry/backoff, then a manual-queue item.
- **No saga is allowed to leave a funded account open without a hedge** (invariant checked by an independent auditor job, not by the saga itself).
- Payouts: request → freeze (ledger hold) → provider call → webhook confirm → settle; provider timeout → retry with same idempotency key; provider "lost" state → manual reconciliation queue with provider statement download.

### 7.7 Availability design

- **Stateless everything** at the bridge/edge; state in Redis/PG/Kafka — any pod is disposable.
- **Multi-region**: active-passive with DNS failover (RTO target < 15 min); Kafka MirrorMaker for event replay across regions; RPO < 60 s. (Active-active is a phase-5 optimization; the domain tolerates passive failover because broker execution is unaffected.)
- **Degraded mode is a feature**: with the platform down, the broker keeps executing; on recovery, spooled evidence + full rescan rebuild P. The platform's failure never strands a position (the hedge service has its own local fail-safe: on loss of trader-account visibility > threshold, it flattens the hedge *and* pages — tenant-configurable between flatten-hedge and hold-hedge, a real money decision that must be an explicit tenant setting, never an implicit default).

---

## 1. Executive Summary

### 1.1 What is being built

A **prop firm-as-a-service (PFaaS) platform** is a multi-tenant SaaS that lets prop firms — and white-label brands — run the entire funded-trader business: challenge storefronts, evaluation accounts, rule enforcement (drawdowns, profit targets, trading restrictions), live account supervision, hedging, and payouts. The platform itself never touches trader funds directly; money moves between traders, tenants (the prop firms), and brokers.

The **trading platform bridge** is the most operationally critical component of such a platform. It is the edge layer that connects thousands of trader-side trading terminals — MetaTrader 4/5 Expert Advisors, cTrader cBots, DXtrade clients, TradingView strategies — to the platform core, over unreliable internet connections, in real time. Everything that makes a prop firm *trustworthy* flows through the bridge:

- **Order telemetry**: every open, modify, and close of a position, with broker-attested prices, timestamps, and tickets.
- **Account state**: balance, equity, margin, free margin — continuously.
- **Control plane**: trading halts, close-all, account suspension, parameter updates pushed *down* to the terminal.
- **Rule enforcement input**: the raw evidence stream that the deterministic rules engine evaluates to decide pass/fail/fraud.

### 1.2 The five hard problems

1. **Execution reality**: on MT4/MT5/cTrader, orders are executed by the trader's *client terminal* against the broker server. The bridge cannot execute orders; it can only *observe, pre-authorize, and react*. The design consequence: execution path and telemetry path must be cleanly separated, and the bridge must tolerate arbitrary disconnects without corrupting rule state.
2. **Trust under adversarial conditions**: the terminal runs on the trader's machine. It is an untrusted device reporting to you over the public internet, and its data determines whether the firm loses money. The bridge must assume malicious or buggy clients: unsigned messages, replayed messages, spoofed PnL, manipulated clocks, patched EAs. Every message is signed, sequenced, deduplicated, cross-checked against broker-attested fields, and cross-validated by independent reconciliation.
3. **Deterministic correctness of rules**: drawdown calculations are *financial*. A daily-loss limit breached by one tick must be enforced; a false positive that fails a trader costs the firm trust and potentially regulatory exposure. Rule evaluation must be a pure, versioned, replayable function over an append-only event log — never ad-hoc code against a mutable DB row.
4. **Multi-tenant isolation at scale**: every tenant (prop firm) has different rule packs, pricing, payout splits, brands, and risk appetites, running on shared bridge infrastructure. Isolation must hold for data (RLS + tenant scoping everywhere), keys (tenant-bound credentials), performance (noisy-neighbor guards), and operations (per-tenant queues and dashboards).
5. **The broker is the source of truth for positions, you are the source of truth for the relationship**: the broker knows what positions exist; you know what the trader is *allowed* to do and what they have *done*. Keeping these two truths consistent — across disconnects, broker outages, and account changes — is the reconciliation discipline this document centers on.

### 1.3 Recommended stack in one paragraph

A stateless **Go** bridge fleet behind a WebSocket-capable load balancer normalizes platform-specific telemetry into a canonical event schema (defined in Protobuf), guards it with sequence numbers, HMAC signatures, and deal-level idempotency, and publishes to **Kafka/Redpanda** partitioned by account. A **Rust** rules engine consumes those ordered streams as a pure evaluator over versioned rule packs, emitting verdicts and state deltas. **Go** domain services (challenges, accounts, orders, payouts, reconciliation) persist to **PostgreSQL** (system of record, row-level security per tenant) with **Redis** for hot session/state and **ClickHouse** for ticks, trades, and analytics. The trader storefront, tenant admin, and back-office are **TypeScript/React**; a small set of browser-side JavaScript bridges (portal widgets, webhook relays) round out the surface. Secrets live in **Vault/KMS**; everything is traced with **OpenTelemetry**; and a Rust **simulation broker harness** lets you replay deterministic market scenarios end-to-end in CI.

### 1.4 Critical-path guarantees (design targets)

| Guarantee | Target |
|---|---|
| Bridge pre-authorization (order_intent → order_allow) | p99 < 8 ms (same region), p999 < 25 ms |
| Telemetry event → rules verdict (end-to-end) | p99 < 150 ms, p99.9 < 500 ms |
| Control command (halt) → delivered to terminal (connected) | p99 < 200 ms |
| Snapshot resync after reconnect | p95 < 3 s for ≤ 200 open positions |
| Daily rollover batch | 100% of accounts within 5 min of rollover |
| Reconciliation drift detection | full daily diff + 60 s event-level checks |
| Message delivery to rule engine | at-least-once with exactly-once *effect* (idempotent apply) |
| Availability of bridge fleet | 99.95 % monthly; degraded mode (trading continues at broker, platform pauses rule clock) on outage |

### 1.5 The single most important design decision

**Never route execution through the bridge.** The terminal executes at the broker; the bridge authorizes, observes, and controls. This keeps trader latency identical to a normal brokerage connection, removes the bridge from the broker's execution critical path (you are not a point of failure for *their* fills), and confines your failure domain to *supervision* — which, by policy and by the reconciliation design, can degrade gracefully and be repaired retrospectively from the event log.

---

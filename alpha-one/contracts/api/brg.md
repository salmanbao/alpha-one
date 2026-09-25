# Bridge (Broker) API Contract (BRG)

Status: DRAFT
Owner: TBD
Version: v1
Last updated: 2026-09-25 (twenty-second pass, docs/63 — streaming ingestion, D77–D80)

Derived from the V1 Execution Sheet (V1.0 only). Nothing here is final until contract freeze.

## Scope
One broker capability interface with an MT5 adapter via MetaApi/Brokeree (BVR-04: no raw Manager API clients), account creation, credential storage/delivery, balance/equity sync, position/trade sync, on-demand sync, enforcement execution with confirmations, leverage/group config, enable/disable trading, adapter contract tests, credential rotation. (BRG-01, BRG-02, BRG-05, BRG-06, BRG-07, BRG-08, BRG-09, BRG-10, BRG-11, BRG-12, BRG-14, BRG-43, BRG-44)

## No direct HTTP surface in V1
The bridge is invoked by other modules (LCC provisioning, EVL evaluation inputs, enforcement worker) and by workers, not by frontends. The sheet defines no trader/admin endpoints for BRG. This module has no HTTP contract in V1 — see module spec later. If the working session wants an admin "force sync" endpoint it is a scope addition — resolved 2026-09-20 (docs/62, citing D36, docs/51): force-sync stays **worker-internal**; no admin endpoint in V1 (the on-demand sync is a worker trigger, not HTTP).

## Capability interface (BRG-01)
One interface covering: create, state, positions, close, disable, enable, leverage, password. Domain code never branches per platform. Every adapter must pass the shared contract test suite (BRG-43).

## Internal operations (cited)
- Create account: group, leverage, initial balance, with idempotency key so retries never duplicate accounts (BRG-05). Called by LCC-05/LCC-06.
- Credentials: stored encrypted (TEN-12, BRG-44 rotation), delivered to trader via portal and email (BRG-06, NOT-03).
- Sync (D78, docs/63): balances/equity (BRG-07) and open positions/closed trades (BRG-08) are ingested by **streaming** — the MetaApi streaming API via the `bridge-stream` Node sidecar (D77, official SDK) → the Go bridge's per-account hot state → conflated `bridge.tick` events (D79, docs/08 §3.3), written by a group-commit transaction (outbox + `pg_notify('outbox_doorbell')`). BRG-21 (streaming) is therefore delivered in V1. **Fallback:** accounts whose stream is `stale` > 30 s are REST-polled every 60 s (tenant-configurable 30–300 s), staggered, within a per-`client-id` CPU-credit budget. Snapshots land in `account_snapshots` (1 row/account/min with `equity_low/high_cents`, 14-day rolling — docs/08 §9, D35).
- Stream gateway (internal, D77): `bridge-stream` → bridge over gRPC on a Unix domain socket, protobuf `bridge.ingest.v1`. Frames: `Equity`, `AccountInfo`, `Positions`/`PositionsReplaced`, `Deal`, `SyncState`, `Health`, `Downgrade`; control: `Subscribe`, `Unsubscribe`, `Cursor` (PG-backed SDK `HistoryStorage`), `Priority`. Numbers cross as decimal strings; equity only from raw packet values (never the SDK's local recompute); critical frames never dropped — overflow forces a resync (docs/63 §4.2). Not a public or cross-module contract; versioned with the bridge.
- Floor hints (D79): the conflator reads EVL's advisory `evaluation_state.floor_daily_cents` / `floor_total_cents` / `target_equity_cents` (docs/09 §3.8) — cached, invalidated by Redis pub/sub `evl.floors`, re-read from PG every 30 s. Hints change only *when* a tick is emitted; BRG never decides a breach (BVR-28).
- On-demand sync for a single account before eligibility checks (BRG-09). Called by PAY-02/PAY-03. With a `live` stream the answer is the hot state (flushed as a tick); otherwise a REST refresh.
- Enforcement: disable-then-close commands executed from the command queue (EVT-20) with retries (3, exponential backoff; circuit-breaker per account) and confirmations via broker re-read, written back to command and account state so FAILED is recorded only after real closure (BRG-11; docs/08 §3.4). `credit` never auto-retries. Triggered by EVL-17 and LCC-27.
- Leverage/group set at creation and phase change per rule set config (BRG-12).
- Enable/disable trading for suspensions and appeals (BRG-14). Called by LCC-11.

## Events consumed
- Consumes commands from `command_queue` (EVT-20) — commands, not events.
- Sync writes feed EVL-05 evaluation triggers (snapshots, trade close).

## Events emitted
- **`bridge.tick`** (v1) — per account, emitted by the streaming conflator on `deal` / `position` / `guard` / `material` / `heartbeat` / `resync` triggers (fallback-poll ticks carry `source = poll`) (tenth pass D28, docs/50; D79, docs/63 §4.4); the observed record (EVL-49); no audit mirror (docs/05 §14). Additive optional fields: `trigger`, `source`, `stream_seq`, `equity_low_cents`, `equity_high_cents`.
- **`bridge.sync_gap`** (v1) — history-window deals-count mismatch (eleventh pass D33, docs/51); EVL verdicts on it carry `gap_flagged`.
- Extended (post-V1) forms — `bridge.account_created/failed`, `bridge.trading_disabled/enabled`, `bridge.positions_closed`, `bridge.reconciliation_exception`, `bridge.command_dead`, `ops.provider_health`, `bridge.watchdog_divergence` (V2, D80 — MetaApi risk-management tracker alarm, never a verdict) — per docs/08 §4.2.

## Open contract questions
- Resolved 2026-09-19 (D36, docs/51): no admin "force sync" endpoint in V1 — BRG-09 on-demand sync stays worker-internal (PAY-02/03 call it before eligibility, docs/11 §3); ADM observes freshness via the health surface (docs/08 §7.2).
- Resolved 2026-09-19 (D35, docs/51): snapshot schema = `account_snapshots` (docs/08 §9): minute buckets, equity/balance/margin/free_margin cents, broker_time; 14-day rolling partitions; daily rollup to ANA.
- Resolved 2026-09-19 (D33, docs/51): gap detection = history-window deals-count reconciliation; `last_deal_ticket` is a fetch cursor, never a continuity oracle (MT5 tickets are server-global).
- Resolved 2026-09-20 (D74, docs/62): **no automated credential email in V1** — BRG stores credentials encrypted; staff copy them from the ADM detail view (sensitive-read audited, the KYC-doc pattern) and deliver them through the firm's own channel; NOT-05 gains no template (the D61 set stands). Automated delivery is a V2 template with its own security design (one-time link, no credentials-in-email).
- Resolved 2026-09-25 (D77, docs/63): the streaming runtime is a thin **Node/TS sidecar (`bridge-stream`) on the official `metaapi.cloud-sdk`** (pinned; source-available licence — docs/34 review-before-deploy); no money math, persistence or decisions in the sidecar.
- Resolved 2026-09-25 (D78, docs/63): **V1 ingest = streaming**; REST polling is the credit-budgeted fallback + reconciliation path (the 60-s poll plan exceeds MetaApi's per-server CPU-credit limit at V1 scale — docs/63 F1).
- Resolved 2026-09-25 (D79, docs/63): the hot path stays on the **transactional outbox** (ADR-6) with bridge-side conflation, group commit and a relay `NOTIFY` doorbell; `bridge.tick` stays v1 with additive fields.
- Resolved 2026-09-25 (D80, docs/63): MetaApi **risk-management trackers = optional V2 watchdog, off by default** — never a verdict source (BVR-28).

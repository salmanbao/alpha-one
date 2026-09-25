# 63 — BRG → EVL/RSK: Real-Time Trading-Data Ingestion via MetaApi Streaming (twenty-second pass)

> The twenty-second pass answers one question end to end: **how does the
> evaluation engine (EVL) — and, behind it, risk (RSK) — ingest each
> account's trading data (equity, balance, margin, positions, deals) from
> MetaApi with minimum latency and high throughput?** The pass read the
> five MetaApi API families (client/streaming, provisioning, risk
> management, MetaStats, CopyFactory) and the official SDK's source, then
> re-checked docs/08's poll-only V1 against MetaApi's documented quotas. The
> poll plan fails those quotas (F1), so the owner moved V1 to **streaming
> ingestion**. Four decisions came out of the pass (**D77–D80**, all owner
> picks, 2026-09-25). This document is the binding design; docs/08/09/01/04
> carry the matching normative edits (§9 wiring map).

Status: REVIEW — 4 decisions (D77–D80), 11 findings, 0 open blockers (6 spike questions, §8)
Owner: TBD (BE-1 bridge, BE-2 EVL consumer, DevOps)
Version: v1
Last updated: 2026-09-25

---

## 1. Scope & method

- **Target:** the observed-data path `MetaApi → BRG → bridge.tick → EVL`
  (docs/08 §3.3, docs/09 §2/§3.6), its side-feeds (`broker_deals` → RSK
  batch detectors, docs/10 §3; `account_snapshots` → PAY/TD/ANA), and
  the provisioning settings that affect them (docs/08 §3.2).
- **Sources read (primary):**
  - MetaApi client API: [overview](https://metaapi.cloud/docs/client/), [WebSocket/streaming](https://metaapi.cloud/docs/client/websocket/overview/), [using the streaming API](https://metaapi.cloud/docs/client/websocket/usingStreamingApi/), [synchronize request](https://metaapi.cloud/docs/client/websocket/synchronizing/synchronize/), [`prices` packet](https://metaapi.cloud/docs/client/websocket/marketDataStreaming/prices/), [subscribe to market data](https://metaapi.cloud/docs/client/websocket/marketDataStreaming/subscribeToMarketData/), [rate limiting](https://metaapi.cloud/docs/client/rateLimiting/).
  - [Provisioning API](https://metaapi.cloud/docs/provisioning/), [risk management API](https://metaapi.cloud/docs/risk-management/) (+ [tracking periods](https://metaapi.cloud/docs/risk-management/trackingPeriods/), [tracker event](https://metaapi.cloud/docs/risk-management/models/trackerEvent/), [period statistics](https://metaapi.cloud/docs/risk-management/models/periodStatistics/), [FAQ](https://metaapi.cloud/docs/risk-management/faq/)), [MetaStats](https://metaapi.cloud/docs/metastats/), [CopyFactory](https://metaapi.cloud/docs/copyfactory/), [official SDK list](https://metaapi.cloud/sdks).
  - **SDK source**, `metaapi.cloud-sdk` **29.3.3** (npm, current at the
    pass date): `SynchronizationListener` (the callback surface),
    `PacketOrderer` (sequence restoration), `SynchronizationThrottler`
    (concurrent-sync caps), `MetaApiWebsocketClient` (socket sharding,
    `status` heartbeat timeout, packet dispatch), `TerminalState` (the
    local equity fallback), `HistoryStorage` (the resume cursor), and the
    risk-management stream managers (`equityBalanceStreamManager`,
    `trackerEventListenerManager`).
- **Constraints honoured (not reopened):** ADR-6 (transactional outbox),
  ADR-7 (Redis Streams, at-least-once), ADR-9 (single Hetzner box +
  Compose), ADR-11 (stateless Rust EVL), ADR-12 (the broker attests
  time), BVR-04 (MetaApi behind BRG-01), BVR-28 (**no vendor is ever the
  final authority on a breach**), docs/09 §3.3 (broker equity is truth,
  never recomputed), D33 (ordering cursors are ours, not the broker's),
  D34 (the `bridge.tick` canonical shape — extended here only
  additively).

## 2. The MetaApi surface — what each API offers the ingest path

| API | Real-time mechanism | What it carries | Cost model | Verdict for EVL/RSK ingestion |
|---|---|---|---|---|
| **Client API — streaming** (socket.io; SDK `getStreamingConnection()`) | Server-push terminal-state sync, per account. Packet types (SDK dispatch): `synchronizationStarted`, `accountInformation`, `positions`, `orders`, `specifications`, **`update`** (`accountInformation`, `updatedPositions`, `removedPositionIds`, `updatedOrders`, `completedOrderIds`, `historyOrders`, **`deals`**), **`prices`** (quotes **plus** `equity`, `margin`, `freeMargin`, `marginLevel`), `deals`, `historyOrders`, `dealSynchronizationFinished`, `orderSynchronizationFinished`, **`status`** (heartbeat + health), `downgradeSubscription`. Every packet has `sequenceNumber` (+1 per packet, restarts per session) and `sequenceTimestamp` (monotonic across sessions). | Everything EVL needs: broker equity recomputed server-side on each price move, balance on each deal, the open-position set, and new deals as they happen. | **Zero CPU credits** ("real-time streaming API does not consume any credits"). Quotas are subscription quotas instead: ≤ 300 accounts per user per MetaApi server, total subscriptions ≤ 10 × deployed accounts, concurrent synchronizations ≤ 10 % of subscribed accounts per server, subscribe requests 10/min × deployed accounts. | **Primary ingest (D78).** The only channel that is both real-time and quota-free. SDK-only in practice: MetaApi states the protocol "is complex" and insists on an SDK (D77). |
| **Client API — REST / RPC** | Request/response. | Account info, positions, orders, deals/history by ticket/position/time range, symbols, server time. | **CPU credits:** 50 per state read; `history-deals/time` = 75 + 0.65 × deals found. Limits: per app 6,000/min × deployed accounts; **per front-end server 18,000/min (2,000/s)** — rotate `client-id` to reach another server (12 servers at doc time); per account 5,000/10 s. MetaApi's own note: apps with > 120 accounts hit the per-server limit first. | **Fallback + reconciliation + on-demand only** (stale-stream accounts, D33 checks at resync, BRG-09 payout refresh, the nightly reconciler). Never the steady-state feed (F1). |
| **Provisioning API** | none (control plane) | Account create/deploy/undeploy/redeploy; `reliability` (`high` = redundant infra: two server-side instances per account, resource slot billed ×2), `region`, `resourceSlots`, `riskManagementApiEnabled`, `metastatsApiEnabled`, `accountReplicas` (cross-region), `state` (`DEPLOYING` → `DEPLOYED` / `DEPLOY_FAILED` …), `connectionStatus`. | per account-hour (MetaApi pricing) | **Set at provisioning** (§4.9). Not an ingest channel. |
| **Risk management API** ("prop trading API") | Tracker events via long-poll `GET /users/current/tracker-events/stream?previousSequenceNumber=…` (durable, resumable cursor); period-statistics and equity-chart "streams" are SDK-side REST pollers; **`EquityBalanceListener` is only a wrapper that opens an ordinary streaming connection** (SDK source). | Server-side drawdown/profit **trackers**: `period` ∈ `day, date, week, week-to-date, month, month-to-date, quarter, quarter-to-date, year, year-to-date, lifetime`, absolute/relative drawdown and profit thresholds, broker-timezone periods; events carry `absoluteDrawdown`, `relativeDrawdown`, `exceededThresholdType`, `brokerTime`, `sequenceNumber`. Period statistics carry `initialBalance`, `maxAbsoluteDrawdown`, `tradeDayCount`. | Billed **per account-hour on top of** MetaApi; MT5 **netting accounts unsupported**. | **Optional V2 watchdog, off by default (D80).** Never a verdict source: drawdown is measured against the period's `initialBalance` (not our day-start equity), there is no trailing high-water mark, and BVR-28 forbids vendor-final breaches. |
| **MetaStats** | none (REST) | Computed metrics: trades with gain/duration/pips, open trades, account statistics. | currently no extra charge | **Not on the ingest path.** Candidate V2 enrichment for TD/ANA trade statistics; `metastatsApiEnabled = false` by default. RSK computes its own features from `broker_deals`. |
| **CopyFactory** | transaction/stop-out feeds scoped to copy relationships | copy-trading execution + risk filters | extra CopyFactory resource slots | **Not an ingest channel.** Relevant only to TRD's V3 copy feature (docs/27 Part B). |

## 3. Findings

| # | Sev | Finding | Disposition |
|---|---|---|---|
| F1 | **Critical** | **The 60-s poll plan breaks MetaApi's per-server CPU-credit limit at V1 scale, and cannot reach the V2 target at all.** One poll cycle = account info (50) + positions (50) + deals-by-time-range (75 + 0.65n) ≈ **176 credits**. The per-server limit (18,000/min) therefore holds **≈ 100 accounts** at a 60-s cadence. V1 (431 accounts, docs/08 §11) ≈ 76k credits/min, which already needs `client-id` rotation across ≥ 5 front-end servers (unspecified in docs/08). V2 (10k accounts, docs/29 §1) ≈ **1.76M credits/min against ≈ 216k/min for all 12 servers combined — about 8× over.** docs/29's "~167 req/s to MetaApi" also counts one call per account, not three. | **D78:** streaming is the V1 primary ingest; REST becomes a credit-budgeted fallback (§4.7). |
| F2 | High | **Poll latency is enforcement latency.** Poll-only detection lag is up to the interval (60 s, widening ×2 under degradation, docs/08 §3.6) plus backlog. On a 5 % daily-loss rule, a fast market overshoots the floor well inside 60 s. On funded accounts the overshoot is the firm's money, and on challenges it is a dispute ("I was only at −5.2 % when you closed me"). Streaming delivers broker equity with every price packet. | D78 + D79 (latency budget §4.6). |
| F3 | High | **Streaming is SDK-only in practice, and there is no Go SDK.** Official SDKs: JS (node/browser), Python, Java (+ risk-management JS/Python). The SDK hides sequence restoration (100-packet wait list, out-of-order → resubscribe), two-instance redundancy merging (`instanceIndex`), sticky `Client-Id` socket sharding (≤ 100 accounts/socket), region/replica routing, sync throttling, and 429 back-off. | **D77:** a thin Node/TS stream-gateway sidecar using the official SDK. |
| F4 | High | **Per-quote ticks cannot ride the outbox.** The relay's documented capacity is 10k events/min (docs/04 §11), and every `bridge.tick` also lands in the 13-month `events` log (docs/04 §3.4). 10k accounts × 1 quote/s = 600k events/min. | **D79:** in-memory **conflation** at the bridge; only material, near-floor, deal, position, resync, and heartbeat ticks become events (§4.4). The tick volume stays on the order of the old poll plan's. |
| F5 | Medium | **The SDK recomputes equity locally when a `prices` packet lacks `equity`** (`TerminalState`: balance + Σ unrealizedProfit + swap [+ commission on MT4]). Reading `terminalState.accountInformation.equity` would silently break docs/09 §3.3 ("broker equity — never recomputed"). | Normative (§4.2): the gateway reads the **raw `equity` argument** of `onSymbolPricesUpdated` / `onAccountInformationUpdated` only. A missing value is treated as *absent*, never derived. Test hook §6. |
| F6 | Medium | **D76's "trading path unaffected by a relay stall" is not true for evaluation.** Enforcement commands bypass events, but EVL's only input rides outbox → relay → Streams. A 60–90 s relay stall means 60–90 s of evaluation blindness. | Correction recorded (docs/04 §3.3 note). D79 adds the relay doorbell plus a `bridge`-topic relay-lag alert (WARN > 5 s, CRITICAL > 30 s). The accepted-risk wording in D76 still holds for the other topics. |
| F7 | Medium | **Resync storms.** A gateway restart resyncs every account. MetaApi caps concurrent syncs at 10 % of subscribed accounts per server. The SDK throttler runs per socket: `min(ceil(accounts/10), 15)`, i.e. ≤ 10 per 100-account socket. Without a history cursor, each resync would also download the full deal history. | §4.7: a PG-backed `HistoryStorage` cursor (resume from `max(deal_time) − 5 min`), prioritised resubscribe (guard-band → funded → open positions → rest). Budget: cold resync ≈ 1–2 min at 10k accounts. |
| F8 | Low | docs/08 §2 said "Webhooks exist". The MetaApi client API has no account-state webhooks; the real-time channel is the socket.io streaming API. | Fixed mechanically in docs/08 §2. |
| F9 | Low | D33's history-window check was defined "per poll". Under streaming there is no poll. | Re-anchored: the check runs at **every (re)synchronization** (after `dealsSynchronized`), plus an hourly sweep, plus the nightly reconciler (§4.7). |
| F10 | Info | **SDK licence:** "(c) MetaApi DMCC … free of charge provided you use it to implement applications which use metaapi.cloud". Source-available, not OSI. The transitive `socket.io-client ~2.4`. | Registered in docs/34 as **review-before-deploy**, pinned `29.3.3`; exit path = BRG-01 (the gateway is replaceable by another provider's adapter). |
| F11 | Info | **Pre-existing generator drift (not caused by this pass):** running `aggregate_docs.py` / `build_data_schemas.py` on the untouched tree already rewrites unrelated rows in docs/30 (D72 payout rows), docs/32 (`audit_events` → `audit_log`, the D75 coupon comment), `10-rsk.sql`, and `12-chk.sql`. | Not regenerated here (it would mix unrelated changes into this pass). This pass hand-mirrored its own DDL/error rows into docs/30/32 and the SQL split. Follow-up §10.1. |

## 4. The design (binding — D77–D80)

### 4.1 Topology

```
 MetaApi cloud — region per broker group; reliability=high ⇒ 2 server instances/account
   │  socket.io streaming (0 CPU credits) · ≤100 accounts/socket · sticky Client-Id
   ▼
┌─ bridge-stream  (Node 22 LTS · TypeScript · metaapi.cloud-sdk 29.3.3 pinned) × S shards ─┐
│  one SynchronizationListener per account → frame encoder (NO arithmetic, NO decisions)    │
│  PgHistoryStorage: lastDealTime()/lastHistoryOrderTime() ← bridge Cursor RPC               │
│  health: onHealthStatus · onBrokerConnectionStatusChanged · onDisconnected · onStreamClosed│
│  latencyMonitor on (priceLatencies/updateLatencies → Prometheus)                           │
└───────────────┬───────────────────────────────────────────────────────────────────────────┘
                │ gRPC bidi stream over a Unix domain socket (same Compose host)
                │ bounded queues · backpressure · never drops Deal/Position/Account frames
                ▼
┌─ bridge (Go) — ingest core ───────────────────────────────────────────────────────────────┐
│  decode → normalize (decimal string → cents, docs/09 rounding table)                      │
│  per-account hot state (memory): equity/balance/margin, positions hash, stream_seq,       │
│     low/high since last tick, stream state, EVL floor hints                               │
│  conflator (§4.4) → tick candidates (trigger = deal|position|guard|material|heartbeat|    │
│     resync)                                                                               │
│  group-commit writer (≤25 ms or ≤500 rows; urgent ⇒ flush now), ONE PG tx:                │
│     broker_accounts · broker_positions · broker_deals (ON CONFLICT DO NOTHING) ·          │
│     account_snapshots (minute bucket + low/high) · outbox bridge.tick ·                   │
│     pg_notify('outbox_doorbell')                                                          │
│  fallback poller (REST; credit-budgeted; only accounts in stream state `stale`)           │
│  executor · reconciler · provider health (docs/08 §3.4–§3.6, unchanged)                   │
└───────────────┬───────────────────────────────────────────────────────────────────────────┘
                ▼  relay: LISTEN outbox_doorbell (+1 s safety poll) → XADD topic.bridge
                ▼  workers: evaluation consumer — per-account serial lanes (docs/04 §3.5)
                ▼  Rust engine /evaluate (ADR-11) → evaluation_state (+ floor hints)
                ▼  outbox evaluation.verdict → LCC transition → account_commands → BRG executor
                ▲  floor hints → bridge: PG columns + Redis pub/sub `evl.floors` (advisory)
```

### 4.2 The stream gateway `bridge-stream` (D77)

**Why a sidecar, and why Node.** The SDK *is* the protocol implementation
(F3). Porting it to Go means owning MetaApi's evolving, partially
documented sync protocol: v1/v2 sync with position/order/specification
hashes, ordering timeouts, replica routing, and throttler semantics. The
JS SDK is MetaApi's reference implementation, and the risk-management
SDK is JS/Python-only too.

**The exception is narrow.** docs/01 §2 rejected Node for the "hot sync
path" because of GC latency and money-math safety. The gateway therefore
does **no money arithmetic, no persistence, and no decisions**:
- **Numbers cross the boundary as strings.** Each numeric field is sent
  as `String(n)`, the shortest decimal that round-trips the IEEE-754
  double MetaApi already put on the wire (e.g. `7306.649913200001`).
  The Go bridge parses it as a decimal and applies the docs/09 rounding
  table → cents. The float is MetaApi's; the rounding is ours and
  deterministic.
- **Equity comes from raw callback arguments only (F5).**
  `onSymbolPricesUpdated(instanceIndex, prices, equity, margin, freeMargin, marginLevel)`
  and `onAccountInformationUpdated(instanceIndex, accountInformation)`
  supply it. `terminalState.*.equity` is never read. `equity === undefined`
  → the frame carries no equity.
- **`broker_time` is broker-attested (ADR-12).** It is the newest price
  `time` in the packet, a deal `time`, or a position `updateTime`. Never
  the gateway clock. The gateway stamps `recv_ns` separately.

**Frames** (`bridge.ingest.v1` protobuf; gateway → bridge):

| Frame | Source callback(s) | Payload |
|---|---|---|
| `Equity` | `onSymbolPricesUpdated` (and candles/ticks/books variants) | account, session, seq, instance, equity, margin, free_margin, margin_level, broker_time, recv_ns |
| `AccountInfo` | `onAccountInformationUpdated` | balance, equity, margin, free_margin, credit, leverage, trade_allowed, currency, broker_time, recv_ns |
| `Positions` / `PositionsReplaced` | `onPositionsUpdated` / `onPositionsReplaced` | updated[], removed_ids[] / full set |
| `Deal` | `onDealAdded` | the MT deal (id, type, entry, symbol, volume, price, profit, swap, commission, time, positionId) |
| `SyncState` | `onSynchronizationStarted`, `onPositionsSynchronized`, `onDealsSynchronized`, `onPendingOrdersSynchronized` | phase, synchronization_id |
| `Health` | `onConnected`, `onDisconnected`, `onBrokerConnectionStatusChanged`, `onHealthStatus` (coalesced ≤ 1 per 10 s per account), `onStreamClosed` | connected, connected_to_broker, instance, health status |
| `Downgrade` | `onSubscriptionDowngraded` | symbol, updates |

**Control** (bridge → gateway): `Subscribe(account, priority)`,
`Unsubscribe(account)`, `Cursor(account) → last_deal_time` (serves
`PgHistoryStorage`), `Priority(account, level)`.

**Redundancy handling (reliability `high`).** Both server instances
stream the same account. The gateway pins a **primary instance** per
account (the first to finish synchronizing; fail over on its
`onDisconnected`) and forwards data frames from the primary only.
`Deal` frames are forwarded from both instances, because the
`(login, deal_id)` primary key makes duplicates harmless and a deal
seen by either instance is never lost.

**Backpressure.** Queues are bounded per shard. When the bridge is
slow, `Equity` frames coalesce per account (latest-wins, with running
low/high carried in the frame). `Deal`, `Positions`, `AccountInfo`,
`SyncState`, and `Health` frames are **never dropped**. If their queue
overflows, the gateway marks the account `desync` and forces an SDK
resync, which re-derives the full state from MetaApi (invariant I-23).

**Durability.** The gateway holds none, by design. A gateway crash
turns its accounts `stale` (fallback poll covers them, §4.7). Restart
resubscribes from the PG cursor; MetaApi replays terminal state plus
deals since the cursor.

**Sharding.** S shards by consistent hash of the MetaApi account id,
≤ 2,000 accounts per shard (≈ 20 sockets per instance). V1 runs 1 shard;
V2 runs 5–6. Per-account memory is a Phase-0 spike measurement (§8 Q3);
alarm at 1.5 GB RSS per shard. `PgHistoryStorage` keeps cursors only,
not deal arrays, so SDK history memory stays flat.

**SDK options.** `packetOrderingTimeout` 60 s (the default).
`enableLatencyMonitor: true`. `synchronizationThrottler` left at the
defaults (they already track MetaApi's 10 % rule). `retryOpts` default.
The `packetLogger` is **on in staging** to record raw packets into the
BRG-43 fixture corpus (§6).

### 4.3 Subscriptions and market data

- The terminal-state sync supplies account info, positions, and deals.
  **Equity arrives on `prices` packets for subscribed symbols.** The
  gateway subscribes `quotes` for each symbol with an open position
  (subscribe on first open, unsubscribe when the last position on that
  symbol closes), with `intervalInMilliseconds` = the broker-group
  setting (default **1000 ms**, floor 250 ms). If MetaApi already pushes
  position-symbol prices unsubscribed, this is a harmless no-op safety
  net (§8 Q1). MetaTrader auto-subscribes conversion symbols (e.g.
  EURUSD for an EUR account trading GBPUSD) — that is expected.
- Market-data cost is market-data credits, not CPU credits: 2 per quote,
  31,500/10 s per account. One quote per second per symbol is two
  orders of magnitude below the limit.
- MetaApi **G2 infrastructure** is required. G1 caps quote streaming at
  one tick per 2.5 s, and MetaApi's own risk-management FAQ recommends
  G2 high reliability for prop workloads.

### 4.4 Conflation — the tick trigger rules (D79)

The bridge keeps, per account, the last emitted tick **E** and the live
hot state **S**. Every frame updates S and the running `low`/`high`
equity since E. It then checks the triggers in order; the first match
emits a `bridge.tick` carrying that `trigger`:

| # | Trigger | Fires when | Flush | Rate cap |
|---|---|---|---|---|
| 1 | `deal` | any new deal (open/close/partial, balance or credit op) | **urgent** (no group-commit wait) | none |
| 2 | `position` | the open-position set changed (open/close/partial; SL/TP-only edits do not fire — they ride the next tick) | urgent | none |
| 3 | `guard` | equity ≤ any **floor hint** + guard band, or equity ≥ target hint − guard band (guard band default **50 bps of initial balance**, per program) | urgent | ≤ 4/s per account (latest-wins in between) — **except crossings** |
| 3a | `guard` (crossing) | equity ≤ a floor hint (the band's inner edge) | urgent | **uncapped — a crossing quote is never conflated away** (invariant I-21) |
| 4 | `material` | \|equity − E.equity\| ≥ materiality (default **10 bps of initial balance**) | normal | ≤ 1 per 10 s per account |
| 5 | `heartbeat` | now − E.t ≥ **60 s** with open positions, or ≥ **300 s** when flat — **only while the stream is `live`** | normal | — |
| 6 | `resync` | synchronization completed / broker reconnected (fresh full state) | urgent | — |

**Floor hints (EVL → bridge).** After every evaluation, and on
`day_rolled` and rule-pack rebind, EVL persists per account:
- `floor_daily_cents` = day_start_equity − daily limit;
- `floor_total_cents` = the stricter of the static and trailing floors
  (EVL-29);
- `target_equity_cents`;
- `floors_version` = the `evaluation_state.version` they came from.

It publishes `evl.floors` on Redis pub/sub, the same cache-invalidation
pattern as `rule_pack.activated`. The bridge caches the hints, reloads
from PG on miss/start, and re-reads all hints every 30 s as a Redis-down
fallback.

**The hints are advisory by construction.** A wrong or stale hint
changes only *when* a tick is emitted, never *what* EVL decides: EVL
recomputes everything from the tick, so I-03 is untouched. Heartbeat and
material ticks bound the worst case of a stale hint to ≤ 60 s — today's
poll cadence. **The bridge never decides a breach** (BVR-28, docs/09 §1).

**Evidence fields.** Every tick carries `equity_low_cents` /
`equity_high_cents`, the observed extremes of broker equity since the
previous tick. They exist so a dispute can show what happened *between*
evaluated ticks. EVL V1 semantics are unchanged: breach and HWM run at
tick equity. The HWM sampling error is bounded by the materiality
threshold (≤ 10 bps) instead of being unbounded under 60-s polling.
Whether a program may trail on the observed intraday high is an EVL rule
question (§8 Q6), not an ingest one.

**Tick-volume envelope** (assumes 30 % of accounts hold open positions,
~50 deals/account/day per docs/08 §11):

| Term | V1 (431) | V2 (10k) |
|---|---|---|
| heartbeat (60 s open / 300 s flat) | ≈ 3/s | ≈ 73/s |
| material (≤ 1/10 s per active account; typical ≪ cap) | ≈ 5/s | ≈ 100/s |
| deal + position (avg; news bursts ×20) | < 1/s | ≈ 6/s (≈ 120/s burst) |
| guard (accounts near a floor; ≤ 4/s each) | rare | ≤ 400/s worst burst |
| **Sustained / burst design point** | **≈ 10/s / ≈ 100/s** | **≤ 250/s / ≤ 1,000/s** |

The sustained volume is **the same order as the old 60-s poll plan**
(10k × 1/min = 167/s), so docs/04's `events` retention and docs/29's
storage line stay valid. The latency on anything that can change a
verdict drops from ≤ 60 s to sub-second. The burst point sits inside
EVL's 1k verdict/s (docs/29 §1) and the raised relay target (§4.5).

### 4.5 The commit path — group commit, outbox, doorbell (D79)

- **Group commit.** One writer goroutine per bridge instance flushes on
  the **first** of: 25 ms since the first queued item, 500 rows, or an
  urgent tick arriving. The flush is one PG transaction:
  - batched `INSERT … ON CONFLICT` via `unnest` arrays for
    `broker_accounts` / `broker_positions` / `broker_deals`;
  - the `account_snapshots` minute-bucket upsert, whose low/high widen
    with `LEAST`/`GREATEST`;
  - the `outbox` rows;
  - `SELECT pg_notify('outbox_doorbell', '')`.
- **ADR-6 intact.** The tick is a transaction, not a side effect: if the
  PG write fails, no event exists.
- **Relay doorbell.** The relay `LISTEN`s on `outbox_doorbell` and drains
  immediately on wake (doorbells coalesce), keeping its 1-s safety poll.
  NOTIFY is only a *doorbell*: the outbox stays the transport and the
  `events` log stays the replay source. docs/04 §12's rejection of NOTIFY
  *as transport* stands.
- **Relay throughput target:** raised from 10k to **60k events/min
  sustained** (500-row pipelined `XADD`), measured in the docs/29 §6 load
  test.
- **Consumer:** the existing per-account serial lanes (docs/04 §3.5), ≥ 16
  lanes. Every tick is evaluated in order; there is no consumer-side
  skipping. Conflation happens once, at the bridge, where low/high are
  tracked continuously.

### 4.6 Latency budget — quote at MetaApi → disable command sent

| Hop | Budget (p95) | Measured by |
|---|---|---|
| MetaApi terminal → gateway (provider + WAN; region-dependent) | provider-owned; target **< 250 ms** EU↔EU (§8 Q2) | SDK `latencyMonitor.priceLatencies` / `updateLatencies` |
| gateway decode → UDS frame | < 1 ms | gateway histogram |
| bridge normalize + trigger | < 0.1 ms | bridge histogram |
| urgent group commit (PG tx + NOTIFY) | 2–5 ms | bridge histogram |
| relay wake → `XADD` | 2–5 ms | `relay.lag{topic=bridge}` |
| Streams → lane → EVL (state read + engine + write) | < 10 ms | docs/09 §11 |
| verdict → outbox → relay → LCC → `account_commands` → executor → MetaApi call | 20–50 ms internal + MetaApi RPC | docs/08 §3.4 |
| **Platform-internal quote → verdict** | **p95 < 50 ms** (SLO 250 ms) | end-to-end trace |
| **Quote → disable command sent** | **p95 < 150 ms internal** (SLO 1 s, docs/29 §4's breach-to-enforcement SLO kept) | end-to-end trace |

Old poll-only equivalent: up to 60 s + backlog before EVL even sees the
equity.

### 4.7 Ordering, gaps, liveness, resync, fallback

**Ordering.** MetaApi numbers packets per session. The SDK's
`PacketOrderer` restores order (a 100-packet wait list) and resubscribes
on an ordering timeout. The bridge then assigns **its own** per-account
monotonic `stream_seq` (D33: ordering cursors are ours). A frame whose
`(session, seq)` regresses is dropped with metric `seq_regression` (the
scaffold's `SEQ_REGRESSION` class, docs/51 F9).

**Stream state per account:**
`subscribing → syncing → live → stale → (fallback polling) → syncing → live`.
- **`stale` on:** `onDisconnected`, `onStreamClosed`,
  `connectedToBroker = false`, or no data/`Health` frame for **90 s**.
  The SDK itself declares a disconnect after 60 s without a `status`
  packet.
- **While `stale`:** no heartbeat ticks are emitted, so EVL's
  `evl.tick_stale` guard engages exactly as it does today — no verdict
  on stale equity.
- **Tick age.** The envelope `occurred_at` of every tick is the receive
  time of the newest frame folded into it (data or `Health`), never the
  emit time of a heartbeat restating old data.

**Resync.** The steps are:
1. On `synchronizationStarted` the account enters `syncing`.
2. `PgHistoryStorage.lastDealTime()` returns `max(broker_deals.deal_time) − 5 min`.
3. MetaApi replays deals since then; the rows land `ON CONFLICT DO NOTHING`.
4. After `dealsSynchronized` + `positionsSynchronized`, the bridge runs
   the **D33 history-window check** over `[last_live_at − overlap, now]`.
   This is one REST `history-deals/time` call (75 + 0.65n credits). A
   count mismatch emits `bridge.sync_gap`.
5. The bridge emits a `resync` tick, and the account goes `live`.
6. The D33 check also runs as an hourly sweep, alongside the nightly
   reconciler (docs/08 §3.5).

**Resync priority (F7).** Guard-band accounts first, then funded, then
accounts with open positions, then the rest. **Cold resync budget:**
< 30 s at V1, ≈ 1–2 min at 10k (≈ 1,000 concurrent syncs across ~100
sockets).

**Fallback poller** (the old poll code, demoted — not deleted):
- Scope: accounts `stale` for > 30 s get REST-polled every 60 s,
  `source = poll`.
- Budget: a hard CPU-credit budget per `client-id`, ≤ 80 % of the
  18k/min per-server limit (≈ 80 accounts/min per server slot), rotating
  client-ids.
- Overflow: in a MetaApi-wide outage the stale set outruns the budget.
  Funded and open-position accounts are then polled first; the rest ride
  `evl.tick_stale` until the stream returns. Commands keep queueing
  (docs/08 §3.6).

**MetaApi 429s** (`TooManyRequestsError`) honour
`metadata.recommendedRetryTime`. `LIMIT_ACCOUNT_SUBSCRIPTIONS_PER_SERVER`
(server full) switches `Client-Id`; the SDK does this automatically for
subscriptions, and the fallback poller does it for REST.

### 4.8 What RSK and the other readers get

- **RSK** stays batch and **never subscribes to ticks** (docs/10 §3's
  non-goal holds). It gains freshness for free: deals land in
  `broker_deals` within one group commit (≤ 25 ms) of arrival instead of
  ≤ 60 s. `deal_time` (broker) vs `received_at` (platform) becomes an
  honest latency feature for the V2/V3 news and latency-arb detectors
  (RSK-38).
- **PAY** eligibility still calls BRG-09 on-demand sync. With a `live`
  stream the answer is the hot state (no REST call); the REST refresh
  runs only if the stream is not `live`.
- **TD/ANA** read `account_snapshots`, now with `equity_low_cents` /
  `equity_high_cents` per minute bucket: honest candles instead of a
  once-a-minute sample.

### 4.9 Provisioning settings (docs/08 §3.2 addendum)

| Field | Setting | Why |
|---|---|---|
| `reliability` | `high` for **funded** accounts; challenge accounts per program (default `regular`) | redundant server instances ⇒ no single-instance stream loss where money is at stake; each resource slot bills ×2 → tenant pass-through (docs/22 §3.4). §8 Q5 |
| `region` | one MetaApi region per broker group (`broker_groups.metaapi_region`), nearest the broker server and the Hetzner DC | latency (§4.6) |
| `resourceSlots` | 1 | extra slots are a copy-trading latency lever, not ours |
| `riskManagementApiEnabled` | `false` (V1); `true` only where the D80 watchdog is enabled | per-account-hour cost |
| `metastatsApiEnabled` | `false` | not on the ingest path (§2) |
| Deploy gating | subscribe the stream only at `state = DEPLOYED` and `connectionStatus = CONNECTED`; `DEPLOY_FAILED` → docs/08 §3.2 step 5 failure path | no zombie subscriptions |

### 4.10 The V2 watchdog — MetaApi risk-management trackers (D80)

**Opt-in per tenant/program**, off by default (extra per-account-hour
cost, passed through).

**Tracker mirroring.** When enabled, BRG creates trackers that mirror
the rule pack:
- **Daily loss:** `period: 'date'` (the broker-timezone calendar day,
  aligned with ADR-12's broker midnight),
  `absoluteDrawdownThreshold` = the daily-limit amount.
- **Total loss:** `period: 'lifetime'`, `absoluteDrawdownThreshold` =
  the static max-loss amount. **Trailing-HWM programs get no total-loss
  tracker**, because trailing floors aren't representable.
- **MT5 netting accounts** get no trackers (unsupported by MetaApi).

**Consumption.** One long-poll loop on
`/users/current/tracker-events/stream`, with `previousSequenceNumber`
persisted in PG (`metaapi_watchdog_cursors`). The loop is durable and
resumable.

**Semantics — an alarm, never a judge (BVR-28):**
- If the account's stream is `live` and no EVL breach follows within
  30 s: emit `bridge.watchdog_divergence` (ext) → ADM review.
  Divergence is *expected* when positions carry over midnight, because
  trackers measure from the period's `initialBalance` while EVL measures
  from day-start equity.
- If the stream is `stale`: an immediate BRG-09 REST refresh → urgent
  tick → **EVL decides**.
- The watchdog never touches LCC.

**Not used:**
- `EquityBalanceListener` — a second streaming connection to the same
  account;
- the equity chart — ANA owns charts;
- period statistics — `tradeDayCount` is a possible V2 cross-check for
  EVL `trading_days`.

### 4.11 Capacity summary

| Metric | V1 (431 accounts) | V2 (10k accounts) |
|---|---|---|
| MetaApi subscriptions (high reliability ⇒ 2 instances) | ≤ 862 | ≤ 20k (quota: 10 × deployed) |
| Sockets (≤ 100 accounts per socket per instance) | ≈ 10 | ≈ 200 |
| Gateway shards | 1 | 5–6 |
| Inbound `Equity` frames (≤ 1/s per open-position account) | ≈ 130/s | ≈ 3k/s (burst 10k/s) |
| Emitted `bridge.tick` sustained / burst | ≈ 10/s / ≈ 100/s | ≤ 250/s / ≤ 1k/s |
| PG transactions from group commit | ≤ 40/s per bridge instance | ≤ 40/s per bridge instance |
| Steady-state CPU credits | ≈ 0 (resync D33 checks + fallback + reconciler only) | same |
| Cold resync (all accounts) | < 30 s | ≈ 1–2 min |

### 4.12 Failure modes

| Failure | Effect | Designed response |
|---|---|---|
| MetaApi region/stream outage | accounts `stale` | fallback poll within the credit budget (funded/open-position first); others → `evl.tick_stale` (no verdicts); enforcement commands queue (docs/08 §3.6); CON banner |
| One account's broker disconnect | that account `stale` | no verdicts on stale data; resync on reconnect → D33 check → `resync` tick |
| Gateway crash | its shard `stale` | Compose restart; fallback poll covers the gap; prioritised resubscribe from the PG cursor |
| Bridge crash | gateway queues fill | `Equity` coalesces; critical-frame overflow → `desync` → resync after the bridge returns |
| Relay stall | evaluation pause (F6) | doorbell + `bridge`-topic relay-lag WARN 5 s / CRITICAL 30 s; D76 lock-steal ≤ 30 s |
| Redis down | floor pub/sub lost; Streams down (docs/29 §4) | bridge reloads floors from PG every 30 s (hints are advisory); outbox holds ticks until the relay can publish |
| EVL down | ticks accumulate in Streams | lanes drain in order on recovery; `evl.tick_stale` stops verdicts on ticks older than 10 min |
| SDK upgrade changes behaviour | silent semantic drift | version pinned; recorded-packet fixture replay (BRG-43) gates every upgrade |
| Clock | — | trading clock = broker times from packets (ADR-12); platform `recv_ns` for liveness (NTP monitor, docs/09 §10) |

## 5. Decisions (owner, 2026-09-25)

All four were presented and chosen interactively; they are registered
in `scripts/design-questions.json` (rendered into docs/37):

- **D77 — the stream runtime: a Node/TS `bridge-stream` sidecar on the
  official `metaapi.cloud-sdk`** (§4.2). It carries no money math,
  persistence, or decisions, and talks to the Go bridge over local gRPC.
  *Alternatives rejected:* port the socket.io protocol to Go (we'd own an
  evolving protocol MetaApi says not to re-implement); a Java SDK
  sidecar (a JVM on the single box, and a third language).
- **D78 — V1 ingest is streaming; polling is demoted to fallback +
  reconciliation** (§4.7). This pulls BRG-21 ("optional broker
  streaming", workbook V3.0) into V1 as the primary path, forced by F1.
  The workbook itself is unchanged (no workbook edits); the pull-forward
  is recorded in docs/08 §1 and docs/99. *Alternatives rejected:* V1
  poll-only with streaming in V2 (V1 would still need client-id sharding
  and would carry F2's latency); keep V3.
- **D79 — the hot path stays on the transactional outbox (ADR-6),
  with bridge-side conflation, group commit, and a NOTIFY doorbell for
  the relay** (§4.4–§4.5). EVL floor hints are advisory. `bridge.tick`
  gains additive fields (`trigger`, `source`, `stream_seq`,
  `equity_low_cents`, `equity_high_cents`), still v1.
  *Alternatives rejected:* an ADR-6 exception (a tick stream bypassing
  the outbox — observed ticks would stop being transactions); direct
  bridge→EVL gRPC with async persistence (the weakest dispute and replay
  story).
- **D80 — MetaApi risk-management trackers are an optional V2
  watchdog, off by default** (§4.10): an alarm and a stale-stream
  refresh trigger, never a verdict source (BVR-28). *Alternatives
  rejected:* enable it from V1 on funded accounts (cost plus a second
  vendor dependency in the V1 money loop); never use it.

## 6. Test hooks

| # | Invariant / check | Asserts | Owner |
|---|---|---|---|
| I-21 | no crossing conflated away | for any generated quote sequence and floor set, **every** quote with equity ≤ a floor hint yields an emitted tick (property test on the conflator) | 63 §4.4 / 08 §3.3 |
| I-22 | conflation evidence | each tick's `equity_low/high_cents` bound every quote folded since the previous tick; `equity_low_cents` ≥ every floor hint unless the tick is itself a crossing tick | 63 §4.4 |
| I-23 | no silent frame loss | under injected backpressure, `Deal`/`Positions`/`AccountInfo` frames are never dropped — they queue, or the account is resynced (chaos test on the gateway↔bridge link) | 63 §4.2 |
| — | broker-truth equity | a `prices` fixture without `equity` produces **no** equity update (the SDK's local recompute is never forwarded — F5) | 63 §4.2 |
| — | resync idempotency | replaying the same recorded session twice leaves `broker_deals`/`broker_positions` byte-identical (extends I-15) | 63 §4.7 |
| — | fixture corpus | SDK `packetLogger` recordings from staging (≥ 24 h, 3 demo accounts, incl. a forced disconnect) replay through gateway + bridge deterministically; BRG-43 runs them per adapter | 08 §16 |
| — | load | 10k simulated accounts (recorded-packet replay, ×N fan-out) → ≤ 250 ticks/s sustained at the default thresholds; quote→verdict p95 < 50 ms internal; relay ≥ 60k events/min | 29 §6 |

## 7. What did **not** change

- EVL is still the only decision-maker; `evaluate(state, rules, tick)`
  is still pure; I-03 recompute still holds (floor hints and conflation
  live outside the function).
- `bridge.tick` is still the observed record (EVL-49), still v1 (the
  new fields are optional and additive), still not mirrored to audit
  (docs/05 §14).
- Enforcement execution, confirm re-reads, circuit breakers, and the
  nightly reconciler (docs/08 §3.4–§3.5) are unchanged.
- No account/position hot state goes to Redis (docs/10 §3's non-goal).
  The hot state lives in the bridge process and is rebuilt from MetaApi
  plus PG on restart.

## 8. Phase-0 spike questions (measure, don't decide)

1. **Q1** — does MetaApi push `prices` (with `equity`) for open-position
   symbols without an explicit `subscribeToMarketData`? (§4.3 is safe
   either way.)
2. **Q2** — which MetaApi region gives the lowest p95 from the Hetzner
   DC to FunderBlu's broker server? What is the account-level default
   streaming interval on G2?
3. **Q3** — gateway RSS per account with `PgHistoryStorage` (sizes the
   shards).
4. **Q4** — does `/users/current/tracker-events/stream` accept a
   filter-less global cursor (one loop), or must it run per account?
   (D80, V2.)
5. **Q5** — `reliability: high` for challenge accounts: the cost delta
   vs. the observed single-instance stream-loss rate (keep the default
   `regular` unless the loss rate argues otherwise).
6. **Q6** (EVL owner, rule semantics) — should any program trail its HWM
   on the observed intraday high (`equity_high_cents`) rather than tick
   equity? V1 answer: no — semantics unchanged.

## 9. Wiring map (files touched by this pass)

| File | Change |
|---|---|
| docs/08 | §1 release note (D78); §2 architecture + MetaApi model (streaming, F8); §3.1 `Connector` gains `Stream`; §3.2 provisioning settings; §3.3 rewritten as streaming ingest + conflation + fallback; §3.6 stream health; §4.1/§4.2 tick cadence + `bridge.watchdog_divergence`; §5 stream lifecycle; §6 new codes; §8 tick shape; §9 DDL; §11 scalability; §12 MetaApi API rows; §13 stack; §14 EVL/RSK; §16 blueprint |
| docs/09 | §2 floors return path; §3.6 trigger row; new §3.8 floor hints; §6 `evl.tick_stale` tick-age definition; §9 `evaluation_state` floor columns; §11 latency budget; §14 BRG line |
| docs/10 | §3 non-goal note: deal freshness, no tick subscription, watchdog is not RSK |
| docs/01 | §1.1 `bridge-stream` component; §2 language note (the D77 exception); §4 data-flow line; **ADR-15** |
| docs/04 | §3.3 relay doorbell + the F6 correction; §11 relay target |
| docs/00 | §5 sync-tick load row |
| docs/29 | §1 tick-rate + MetaApi rows |
| docs/30, `contracts/errors/taxonomy.md` | `brg.stream_stale`, `brg.stream_desync`, `brg.rate_limited` |
| docs/31, `contracts/events/catalog.md` | `bridge.tick` producer text; `bridge.watchdog_divergence` (ext) |
| `scripts/build_v1_payloads.py` → `contracts/events/payloads/bridge.tick.v1.json`; example JSON | additive optional fields |
| docs/32, `contracts/data/schemas/08-brg.sql`, `09-evl.sql` | hand-mirrored DDL (F11) |
| `contracts/api/brg.md` | sync-worker line → streaming; the gateway contract; events |
| docs/33 | glossary: conflation, floor hint, guard band, stream gateway, stream state |
| docs/34 | MetaApi row; `metaapi.cloud-sdk` (review-before-deploy licence) |
| docs/35 | I-21..I-23 + D77–D80 hooks |
| docs/99 | 0.1 / 1.2 / 5.14 / R1 / B-09 |
| `scripts/design-questions.json` → docs/37 | D77–D80 |
| README, `site/` | doc map row; site rebuilt |

## 10. Follow-ups (explicitly not done here)

1. **Generator drift (F11).** Reconcile docs/30/32 and
   `10-rsk.sql`/`12-chk.sql` with their generators in a dedicated
   mechanical pass (it touches D72/D75 rows and the `audit_log` rename —
   not this pass's scope).
2. **docs/27 Part B (TRD, V3)** still labels copy latency "poll-bound
   (≤ 60 s)". Under D78 the leader-deal signal is stream-fed (seconds).
   TRD's owner should refresh the label and the latency-arb posture when
   V3 planning starts.
3. **Load-test targets** (docs/29 §6) gain the §6 load row; the storage
   line gets re-measured once the Phase-0 spike records real
   frame/tick ratios.
4. **BRG-28** (broker time-drift detection, the workbook ERROR row)
   gains a natural implementation under streaming: price `time` vs.
   `recv_ns` drift per server. It is still for the owner to define into
   a train or delete (docs/39 §2).

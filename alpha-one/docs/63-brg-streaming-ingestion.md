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

Status: REVIEW — 5 decisions (D77–D81), 13 findings, 0 open blockers (7 spike questions, §8)
Owner: TBD (BE-1 bridge, BE-2 EVL consumer, DevOps)
Version: v1.1
Last updated: 2026-09-25

> **v1.1 — the capacity target was corrected (D81-adjacent, §4.11).**
> Every number in v1 of this document was sized against a
> **single-tenant** ceiling of 10,000 accounts total. The platform is a
> white-label multi-tenant system: many independent prop firms run on
> shared infrastructure and each can hold 5,000–10,000 active accounts.
> The V2 planning target is therefore **10 tenants × 10,000 accounts =
> 100,000 concurrent broker accounts** — 10× the v1 figure. §4.11 carries
> the recomputed table and the arithmetic behind every row; §4.4, §4.5,
> §4.7, F1/F4/F7 and the §6 load row were re-derived at the same target.
> **This is a planning estimate, not a hard ceiling** (§4.11.1 names the
> revisit triggers). V1's 431 accounts are unchanged — this is a V2
> planning correction only.

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
| F1 | **Critical** | **The 60-s poll plan breaks MetaApi's per-server CPU-credit limit at V1 scale, and cannot reach the V2 target at all.** One poll cycle = account info (50) + positions (50) + deals-by-time-range (75 + 0.65n) ≈ **176 credits**. The per-server limit (18,000/min) therefore holds **≈ 100 accounts** at a 60-s cadence. V1 (431 accounts, docs/08 §11) ≈ 76k credits/min, which already needs `client-id` rotation across ≥ 5 front-end servers (unspecified in docs/08). V2 (10k accounts, docs/29 §1) ≈ **1.76M credits/min against ≈ 216k/min for all 12 servers combined — about 8× over.** docs/29's "~167 req/s to MetaApi" also counts one call per account, not three. **v1.1 correction:** at the multi-tenant target (100k accounts, §4.11) poll-everything would need ≈ **17.6M credits/min — ≈ 81× over** all 12 servers combined. F1's conclusion strengthens rather than changes: polling is not a steady-state feed at any plausible white-label scale. | **D78:** streaming is the V1 primary ingest; REST becomes a credit-budgeted fallback (§4.7). |
| F2 | High | **Poll latency is enforcement latency.** Poll-only detection lag is up to the interval (60 s, widening ×2 under degradation, docs/08 §3.6) plus backlog. On a 5 % daily-loss rule, a fast market overshoots the floor well inside 60 s. On funded accounts the overshoot is the firm's money, and on challenges it is a dispute ("I was only at −5.2 % when you closed me"). Streaming delivers broker equity with every price packet. | D78 + D79 (latency budget §4.6). |
| F3 | High | **Streaming is SDK-only in practice, and there is no Go SDK.** Official SDKs: JS (node/browser), Python, Java (+ risk-management JS/Python). The SDK hides sequence restoration (100-packet wait list, out-of-order → resubscribe), two-instance redundancy merging (`instanceIndex`), sticky `Client-Id` socket sharding (≤ 100 accounts/socket), region/replica routing, sync throttling, and 429 back-off. | **D77:** a thin Node/TS stream-gateway sidecar using the official SDK. |
| F4 | High | **Per-quote ticks cannot ride the outbox.** The relay's documented capacity is 10k events/min (docs/04 §11), and every `bridge.tick` also lands in the 13-month `events` log (docs/04 §3.4). 10k accounts × 1 quote/s = 600k events/min; **100k accounts × 1 quote/s = 6M events/min** at the corrected multi-tenant target (§4.11) — 100× the relay's documented 10k events/min, and 10× the 600k/min target D79 raises it to for *conflated* ticks. | **D79:** in-memory **conflation** at the bridge; only material, near-floor, deal, position, resync, and heartbeat ticks become events (§4.4). The tick volume stays on the order of the old poll plan's. |
| F5 | Medium | **The SDK recomputes equity locally when a `prices` packet lacks `equity`** (`TerminalState`: balance + Σ unrealizedProfit + swap [+ commission on MT4]). Reading `terminalState.accountInformation.equity` would silently break docs/09 §3.3 ("broker equity — never recomputed"). | Normative (§4.2): the gateway reads the **raw `equity` argument** of `onSymbolPricesUpdated` / `onAccountInformationUpdated` only. A missing value is treated as *absent*, never derived. Test hook §6. |
| F6 | Medium | **D76's "trading path unaffected by a relay stall" is not true for evaluation.** Enforcement commands bypass events, but EVL's only input rides outbox → relay → Streams. A 60–90 s relay stall means 60–90 s of evaluation blindness. | Correction recorded (docs/04 §3.3 note). D79 adds the relay doorbell plus a `bridge`-topic relay-lag alert (WARN > 5 s, CRITICAL > 30 s). The accepted-risk wording in D76 still holds for the other topics. |
| F7 | Medium | **Resync storms.** A gateway restart resyncs every account. MetaApi caps concurrent syncs at 10 % of subscribed accounts per server. The SDK throttler runs per socket: `min(ceil(accounts/10), 15)`, i.e. ≤ 10 per 100-account socket. Without a history cursor, each resync would also download the full deal history. | §4.7: a PG-backed `HistoryStorage` cursor (resume from `max(deal_time) − 5 min`), prioritised resubscribe (guard-band → funded → open positions → rest). Budget: cold resync ≈ 1–2 min at 10k accounts; **≈ 10–20 min at the corrected 100k target** (§4.7) — long enough that a full-fleet resync is an incident-shaped event rather than a routine restart. |
| F8 | Low | docs/08 §2 said "Webhooks exist". The MetaApi client API has no account-state webhooks; the real-time channel is the socket.io streaming API. | Fixed mechanically in docs/08 §2. |
| F9 | Low | D33's history-window check was defined "per poll". Under streaming there is no poll. | Re-anchored: the check runs at **every (re)synchronization** (after `dealsSynchronized`), plus an hourly sweep, plus the nightly reconciler (§4.7). |
| F10 | Info | **SDK licence:** "(c) MetaApi DMCC … free of charge provided you use it to implement applications which use metaapi.cloud". Source-available, not OSI. The transitive `socket.io-client ~2.4`. | Registered in docs/34 as **review-before-deploy**, pinned `29.3.3`; exit path = BRG-01 (the gateway is replaceable by another provider's adapter). |
| F11 | Info | **Pre-existing generator drift (not caused by this pass):** running `aggregate_docs.py` / `build_data_schemas.py` on the untouched tree already rewrites unrelated rows in docs/30 (D72 payout rows), docs/32 (`audit_events` → `audit_log`, the D75 coupon comment), `10-rsk.sql`, and `12-chk.sql`. | Not regenerated here (it would mix unrelated changes into this pass). This pass hand-mirrored its own DDL/error rows into docs/30/32 and the SQL split. Follow-up §10.1. |
| F12 | **Critical** | **The corrected multi-tenant target does not fit the ADR-9 single-box posture.** At 100k accounts the stream gateway needs ≈ 50 shards (§4.11) at the §4.2 alarm threshold of 1.5 GB RSS each — ≈ 75 GB of sidecar RSS before Postgres, Redis, the Go bridge, `api`, `relay`, `workers`, ZITADEL, Hook0 and the two Next.js surfaces are counted. The AX42-class V1/V2 box is 32–64 GB (docs/06 §1, docs/29 §1.3). This is not a tuning problem: the bridge-stream tier alone exceeds the box. | **New:** the V2 second box (docs/29 §3.2) is pulled **forward into V2 as a prerequisite, not a V3 seam**, and it hosts the `bridge-stream` shards first (they are stateless, restart-resync, and the easiest tier to move). Recorded in docs/29 §1.3/§3.1 and docs/06 §1. Spike §8 Q7 measures real RSS/account before the shard count is frozen. |
| F13 | **Critical** | **13-month in-Postgres retention of `bridge.tick` (docs/04 §3.4, EVT-22) is not viable at the corrected target.** Sustained ≤ 2,500 ticks/s = 216M rows/day = **≈ 85 B rows over the 13-month (≈ 395-day) window**; at ≈ 400 B/row that is ≈ **34 TB** in the `events` log, against docs/29 §1.3's "≈ 200 GB/yr … 1 TB disk". (The row was already ≈ 17× over at the old 10k target — 8.5 B rows, ≈ 3.4 TB — so this is pre-existing drift the ×10 correction makes binding, in F11's sense.) | **New:** `bridge.tick` gets an explicit retention tier instead of the default 13-month log: **≤ 7 days hot in PG** (≈ 1.5 B rows, ≈ 600 GB, partitioned per day per §4.11.2) then **columnar archive to R2** (≈ 10:1 compressed ≈ 3 TB/yr ≈ $45/mo at docs/22 §3.1's R2 class). Replay for disputes older than the hot window reads the archive, not PG. Every other topic keeps the 13-month PG window — they are 3–4 orders of magnitude smaller. Needs docs/04 §3.4 + docs/32 edits (follow-up §10.2). |

## 4. The design (binding — D77–D81, D82/D84 for the multi-tenant scale requirements)

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
**V2 runs ≈ 50 at the corrected 100k target** (100,000 ÷ 2,000) — the v1
figure of 5–6 was for 10k accounts. Per-account memory is a Phase-0
spike measurement (§8 Q3, Q7); alarm at 1.5 GB RSS per shard, which at
50 shards is **≈ 75 GB of sidecar RSS and does not fit the ADR-9 single
box (F12)**. `PgHistoryStorage` keeps cursors only, not deal arrays, so
SDK history memory stays flat.

**Shard ownership is per tenant, not global (v1.1).** The consistent
hash is over `(tenant_id, account_id)` and a shard never spans two
tenants. At 10 tenants × 10k that is 5 shards per tenant — 50 in total.
This costs nothing at V1 (one tenant, one shard) and buys three things
at V2: a tenant's resync storm, MetaApi credential set, credit budget,
and blast radius are all confined to its own shards; a shard can be
moved to the second box without re-hashing other tenants' accounts; and
§4.13's per-tenant fairness has a physical unit to be enforced on.

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
~50 deals/account/day per docs/08 §11). **v1.1: the V2 column is
recomputed at the corrected multi-tenant target — 100,000 concurrent
broker accounts (10 tenants × 10k), §4.11. The per-account assumptions
are unchanged; only the account count moved, so every row is the v1
figure × 10.** The arithmetic is shown per row so the derivation is
auditable rather than asserted:

| Term | V1 (431) | V2 (100k) — derivation at 100k accounts |
|---|---|---|
| heartbeat (60 s open / 300 s flat) | ≈ 3/s | **≈ 733/s** — open: 30,000 ÷ 60 s = 500/s; flat: 70,000 ÷ 300 s = 233/s |
| material (≤ 1/10 s per active account; typical ≪ cap) | ≈ 5/s | **≈ 1,000/s** — cap = 30,000 active ÷ 10 s = 3,000/s; typical ≈ ⅓ of cap (the v1 ratio) |
| deal + position (avg; news bursts ×20) | < 1/s | **≈ 58/s** (≈ **1.2k/s** burst) — 50 deals × 100k = 5M/day ÷ 86,400 s = 57.9/s; ×20 news burst |
| guard (accounts near a floor; ≤ 4/s each) | rare | **≤ 4,000/s** worst burst — 1 % of accounts near a floor (1,000) × 4/s |
| **Sustained / burst design point** | **≈ 10/s / ≈ 100/s** | **≤ 2,500/s / ≤ 10,000/s** |

Sustained sum = 733 + 1,000 + 58 ≈ **1,791/s**, rounded up to the
**≤ 2,500/s** design point (≈ 40 % headroom for the guard-band trickle
outside a burst). Burst sum = 4,000 (guard) + 1,200 (deal/position news)
+ 3,000 (material at cap) + 733 (heartbeat) ≈ **8,933/s**, rounded up to
the **≤ 10,000/s** design point. Both are the v1-at-10k figures × 10,
which is the check: nothing here is superlinear in account count,
because conflation is per account and the caps are per account.

The sustained volume is **the same order as the old 60-s poll plan**
(100k × 1/min = 1,667/s), so the *shape* of docs/04's `events` retention
argument survives. Its *magnitude* does not: 2,500 rows/s into a
13-month log is ≈ 34 TB (F13), so docs/04 §3.4's retention and docs/29's
storage line are **not** valid at this target and are corrected there.
The latency on anything that can change a verdict drops from ≤ 60 s to
sub-second. The burst point no longer sits inside EVL's old 1k verdict/s
(docs/29 §1) — it needs 10k verdict/s and the lane count that implies
(§4.5, docs/09 §11) — and it sets the raised relay target (§4.5).

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
- **Relay throughput target:** raised from 10k to **600k events/min
  sustained (10k/s)** at the corrected multi-tenant target — the v1
  figure was 60k events/min (1k/s) for 10k accounts; the burst point is
  10× (§4.4). Mechanism unchanged: 500-row pipelined `XADD`, measured in
  the docs/29 §6 load test. **This is 5× the relay's documented
  single-process capacity** (docs/04 §11: "2k msg/s fine on Redis"), so
  the relay is no longer one process at V2: it partitions by
  `(topic, tenant-shard)` with a per-partition advisory lock — the
  horizontal seam docs/04 §11/§3.2 already names, pulled forward. At the
  §1.2 2× headroom rule the design point is **≥ 10 relay partitions**
  (20k/s ÷ 2k/s per partition); Redis Streams itself is not the limit
  (≈ 10 MB/s of pipelined `XADD` at 10k/s × ~1 KB payloads).
- **Consumer:** the existing per-account serial lanes (docs/04 §3.5).
  **v1.1: "≥ 16 lanes" is not enough at 100k accounts and is corrected
  to ≥ 128.** The arithmetic: docs/09 §11's per-tick budget is p95 < 10 ms
  (PG state read ~1 ms + engine HTTP ~2 ms + state write ~1 ms), so one
  serial lane sustains ≈ **100 ticks/s**. Sustained 2,500/s ⇒ 25 lanes;
  burst 10,000/s ⇒ 100 lanes; ×2 headroom (§1.2) ⇒ 200 lanes. The design
  point is **≥ 128 lanes, configurable to 256**, and lane count must be
  ≥ (tenant shards × per-shard lanes) so that §4.13's per-tenant
  fairness has something to be fair *across*. At 100k accounts, 16 lanes
  would put 6,250 accounts per lane — and since 100k accounts emit
  1,600 ticks/s of capacity against ≈ 1,791/s of *sustained* demand (§4.4) —
  the fleet saturates on ordinary traffic, before any burst and before the
  ≈ 4,000/s guard term is considered. Every tick is still evaluated in order; there is
  no consumer-side skipping. Conflation happens once, at the bridge,
  where low/high are tracked continuously.

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
sockets), **≈ 10–20 min at the corrected 100k target**.

The 100k figure needs its reasoning shown, because it is *not* what
MetaApi's caps imply on their own. Concurrency scales with sockets
(the per-socket throttler is `min(ceil(accounts/10), 15)` = 10 per
100-account socket), so 2,000 sockets ⇒ ≈ 20,000 concurrent syncs ⇒
5 waves at 100k, exactly as at 10k — the provider-side wave count is
scale-invariant. What is *not* invariant is our side: 50 shards
resyncing at once through one or two boxes' NIC and CPU, ≈ 100k PG
cursor reads, and terminal-state replay (account info + positions +
specifications) for every account. The estimate is therefore linear-in-
accounts **once our own box is the binding constraint rather than
MetaApi's 10 % cap**, and it is a planning estimate to be measured in
spike §8 Q7 — not a measurement.

**The operational consequence is the real deliverable: a fleet-wide cold
resync is never performed.** Resync is a **rolling per-shard** operation
— 1 shard (2,000 accounts, 1 tenant's 1/5) at a time, ≈ 12–24 s of
`evl.tick_stale` blindness per shard, no verdicts on stale equity during
it (docs/09 §6), 50 shards ⇒ ≈ 10–20 min wall-clock for a full gateway
upgrade with the blast radius held at 2 % of the fleet. A simultaneous
50-shard restart (host reboot, Compose recreate) is a **declared
maintenance window**, announced per tenant via CON-15, not a restart.
Fleet-wide resync is only unavoidable on a MetaApi-side event, and then
the priority list above is what decides who recovers first.

**Fallback poller** (the old poll code, demoted — not deleted):
- Scope: accounts `stale` for > 30 s get REST-polled every 60 s,
  `source = poll`.
- Budget: a hard CPU-credit budget per `client-id`, ≤ 80 % of the
  18k/min per-server limit (≈ 80 accounts/min per server slot), rotating
  client-ids.
- **v1.1 — the budget does not survive the corrected target without
  per-tenant credentials.** At 100k accounts the arithmetic depends on a
  MetaApi ambiguity that must be resolved (§8 Q8):
  - *Reading A — the 18k/min limit is per (`Client-Id`, server) pair.*
    White-label means each tenant has its own MetaApi account, so the
    budget multiplies by tenant: 10 tenants × 12 servers × 80 =
    **9,600 accounts/min**. Full stale pass ≈ 10.4 min; the priority
    subset (30k accounts with open positions) ≈ **3.1 min** — inside the
    10-minute `evl.tick_stale` window. Workable.
  - *Reading B — the limit is global per front-end server* (MetaApi's own
    note that "apps with > 120 accounts hit the per-server limit first"
    is consistent with this). Then it is 12 × 80 = **960 accounts/min
    platform-wide regardless of tenant count**: full pass ≈ 104 min,
    priority subset ≈ 31 min. **Not workable** — a MetaApi-wide outage at
    100k accounts means most of the fleet rides `evl.tick_stale` for the
    duration.
  - **Plan against Reading B until Q8 answers.** Under B, a MetaApi-wide
    outage at the corrected target is a *declared degradation*, not a
    recoverable incident: `evl.tick_stale` is the correct fail-safe (no
    verdicts on stale equity, docs/09 §6), enforcement commands keep
    queueing (docs/08 §3.6), and the tenant-visible commitment is the
    CON-15 banner plus the docs/29 §4 breach-to-enforcement SLO being
    formally suspended for the outage's duration — not a promise of
    continued evaluation. This is also the strongest argument for
    §4.13's per-tenant stream sharding: under Reading B a shared credit
    pool lets one tenant's stale storm consume another tenant's fallback
    budget, and per-tenant budgets are the only fair allocation.
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

**v1.1 — recomputed at the corrected multi-tenant target.** v1 of this
table was sized against a *single-tenant* ceiling of 10,000 accounts
total. The platform is white-label: independent prop firms share the
infrastructure and each can hold 5,000–10,000 active accounts. The
corrected V2 planning target is **10 tenants × 10,000 accounts = 100,000
concurrent broker accounts**. V1 (431 accounts) is unchanged — this is a
V2 planning correction only.

| Metric | V1 (431 accounts) | V2 (100,000 accounts = 10 tenants × 10k) |
|---|---|---|
| MetaApi subscriptions (high reliability ⇒ 2 instances) | ≤ 862 | **≤ 200k** (quota: 10 × deployed = 1M — 5× headroom) |
| Sockets (≤ 100 accounts per socket per instance) | ≈ 10 | **≈ 2,000** (100k × 2 instances ÷ 100) |
| Gateway shards (≤ 2,000 accounts/shard) | 1 | **≈ 50** (5 per tenant) — **≈ 75 GB RSS at the §4.2 alarm threshold ⇒ F12, does not fit one box** |
| MetaApi `client-id` slots (≤ 300 accounts per user per server) | ≈ 2 | **≥ 334** (100k ÷ 300); with 12 front-end servers ⇒ **≥ 28 MetaApi user accounts**, or ≥ 3 per tenant under per-tenant credentials (§4.7 Q8) |
| Inbound `Equity` frames (≤ 1/s per open-position account; 30 % hold positions) | ≈ 130/s | **≈ 30k/s** (burst **100k/s** at 1 quote/s fleet-wide) |
| Emitted `bridge.tick` sustained / burst | ≈ 10/s / ≈ 100/s | **≤ 2,500/s / ≤ 10,000/s** (§4.4 derivation) |
| Relay `XADD` throughput | 10k events/min | **600k events/min (10k/s)** — ⇒ **≥ 10 relay partitions** at the §1.2 2× rule (docs/04 §11's single process is 2k/s) |
| `workers` evaluation lanes (≈ 100 ticks/s per lane at docs/09 §11's p95 < 10 ms) | ≥ 16 | **≥ 128** (25 sustained / 100 burst / 200 at 2× headroom) — v1's "≥ 16" is corrected in §4.5 |
| PG group-commit rows (snapshots + deals + positions + outbox) | ≈ 750/s | **≈ 4,300/s sustained, ≈ 11,800/s burst** (snapshots 100k/min = 1,667/s; deals 58/s; outbox = the tick rate) |
| PG transactions from group commit | ≤ 40/s per bridge instance | **≤ 40/s per bridge instance** (cap unchanged; ≈ 9 tx/s sustained, ≈ 24 tx/s burst at 500 rows/tx) — **≥ 2 bridge instances** at 100k for frame ingest, partitioned per tenant |
| PG queries from the evaluation path (`evaluation_state` read + write, one per tick) | ≈ 20/s | **≈ 5,000 q/s sustained, ≈ 20,000 q/s burst** for the read+write pair alone; **≈ 11,800 q/s sustained, ≈ 42,900 q/s burst once the `outbox` and `events` rows the same tick generates are counted — the itemised derivation is docs/29 §3.4.1 and that is the figure the primary must absorb** ⇒ §4.11.2 |
| `broker_deals` volume (50/account/day) | ≈ 21.5k/day | **≈ 5M/day**; 90-day hot window ≈ **450M rows** (≈ 150 GB at ≈ 330 B/row) |
| `account_snapshots` volume (1/min/account) | ≈ 620k/day | **≈ 144M/day**; 14-day rolling ≈ **2.0 B rows** (≈ 400 GB at ≈ 180 B/row heap + PK index) ⇒ §4.11.2 |
| `bridge.tick` rows in the `events` log | ≈ 8.6M/13 mo | **≈ 85 B/13 mo (≈ 395 d) ≈ 34 TB** ⇒ **F13, the 13-month PG retention is not viable; ≤ 7 days hot + R2 columnar archive** |
| EVL verdict rate | ≈ 10/s | **2,500/s sustained, 10k/s burst** (docs/29 §1.3's EVL row corrected from "~1k verdict/s") |
| MetaApi cost (docs/08 §1, ≈ $75/mo per deployed account, tenant pass-through docs/22 §3.4) | ≈ $32k/mo | **≈ $7.5M/mo platform-wide; ≈ $750k/mo per tenant at 10k accounts** |
| Steady-state CPU credits | ≈ 0 (resync D33 checks + fallback + reconciler only) | same (streaming consumes no credits — the reason D78 holds at 10× the scale) |
| Cold resync (all accounts) | < 30 s | **≈ 10–20 min fleet-wide ⇒ never performed fleet-wide; rolling per shard, ≈ 12–24 s of blindness per 2,000 accounts (§4.7)** |

Every row above is the v1-at-10k figure **× 10**, because conflation,
subscription, socket, shard and credit limits are all *per account* or
*per shard* — nothing on this path is superlinear in account count. The
rows that are **not** simple ×10 are the ones where a documented ceiling
is crossed rather than a volume scaled: relay partitions (a 2k/s process
limit), `workers` lanes (a 10 ms serial-lane limit), gateway RSS (F12),
and event retention (F13). Those four are the actual work the corrected
number creates.

#### 4.11.1 This is a planning estimate, not a hard ceiling

100,000 accounts is **the number the platform is sized to plan against**,
derived as 10 tenants × 10,000 accounts because that is the shape of the
white-label roster (each firm 5,000–10,000 active accounts), not because
any signed contract says so. docs/00 §5's V2 tenant range is 25–50, which
at the same per-tenant account count implies 250k–500k accounts — i.e.
**this target is deliberately conservative relative to the stated tenant
ambition**, and the arithmetic above is linear, so re-deriving it at a
different roster is a multiplication, not a redesign. What is *not*
linear is the four ceiling crossings named above; those are what a
re-derivation has to re-examine.

**Re-derive these numbers before any of:**

1. **Onboarding tenant #15** (the roster milestone; 15 × 10k = 150k is
   1.5× this target and pushes the relay partition count, the lane count
   and the F12 box arithmetic past their stated headroom).
2. **Any single tenant exceeding 10,000 concurrently deployed accounts**
   (per-tenant shards are sized at 5 per tenant; a 25k-account tenant
   needs 13 shards and its own blast-radius review).
3. **The signed roster exceeding 10 tenants**, or a commercial commitment
   that names a specific account count — at which point that number
   replaces the estimate here and in docs/29 §1.1, and this subsection
   records the replacement.
4. **MetaApi changing the 300-accounts-per-user-per-server cap, the
   10 × deployed subscription quota, or the 18k credits/min per-server
   limit** — all three are provider policy, not ours, and all three are
   load-bearing above.
5. **Spike §8 Q3/Q7 returning a real RSS-per-account figure** that differs
   materially from the 1.5 GB/shard alarm threshold (F12's shard count
   and second-box requirement follow from it).

Until one of those fires, **100k is the number every downstream sizing
decision is derived from** — Redis Streams throughput, the relay target,
Postgres write volume, and the `workers` lane count all quote this table.

#### 4.11.2 What the corrected number breaks (and the honest answer)

Correcting the target is not a find-and-replace. Four things stop
working, and two of them were already wrong at 10k:

| # | What breaks | The arithmetic | The answer |
|---|---|---|---|
| 1 | **The ADR-9 single box (F12)** | 50 shards × 1.5 GB ≈ 75 GB of sidecar RSS vs a 32–64 GB box, before PG/Redis/api/relay/workers/ZITADEL/Hook0/Next are counted | The docs/29 §3.2 second box moves **forward from a V3 seam to a V2 prerequisite**, hosting `bridge-stream` first (stateless, restart-resync, the cheapest tier to move). Measure real RSS/account first (§8 Q7) — the shard count may be lower. |
| 2 | **13-month PG retention of `bridge.tick` (F13)** | 2,500/s ⇒ 216M rows/day ⇒ ≈ 85 B rows over 13 mo (≈ 395 d) ≈ 34 TB vs docs/29 §1.3's "≈ 200 GB/yr, 1 TB disk". Already ≈ 17× over at the old 10k target | ≤ 7 days hot in PG (≈ 1.5 B rows, ≈ 600 GB, day-partitioned), then columnar archive to R2 (≈ 3 TB/yr, ≈ $45/mo). Dispute replay older than the hot window reads the archive. All other topics keep 13 months — they are 3–4 orders of magnitude smaller. |
| 3 | **The single relay process** | 10k `XADD`/s burst vs docs/04 §11's documented 2k msg/s single process | ≥ 10 relay partitions by `(topic, tenant-shard)`, each with its own advisory lock — the seam docs/04 §11/§3.2 already names, pulled into V2. Redis itself is not the limit (≈ 10 MB/s pipelined). |
| 4 | **Single-primary Postgres at burst** | Evaluation path **≈ 11,800 q/s sustained, ≈ 42,900 q/s burst** (≈ 2,600 / ≈ 10,100 commits/s) once the `evaluation_state` read+write pair, the `outbox` row and the `events` row the same tick generates are all counted — itemised in docs/29 §3.4.1 — plus 1,667 snapshot rows/s and 58 deal rows/s. An AX42-class 8–16 vCPU NVMe primary is planned at ≈ 10k q/s | **Sustained fits; burst does not.** But burst does not need line-rate service — see the drain arithmetic below. Partition by `tenant_id` (§4.11.3), and stage the horizontal option on a *measured* trigger. Full sizing in docs/29 §3.4. |

**The burst-drain arithmetic (why #4 is survivable, and just).** A burst
does not have to be served at 10,000 ticks/s; it has to be *drained*
inside the window where staleness is still correct. Take a 5-minute news
burst at 10k/s against a write path that sustains 5,000 ticks/s: backlog
accrued = (10,000 − 5,000) × 300 s = **1.5M events**; drain time after
the burst = 1.5M ÷ 5,000 = **300 s**; worst-case evaluation lag ≈
**10 minutes** — exactly docs/09 §6's `evl.tick_stale` threshold. So a
single primary survives the corrected target's burst **with zero margin
against the correctness backstop**. That is not a comfortable place to
be, and it is the quantitative reason §4.14 (autoscaling + load-shedding)
exists: under sustained overload the platform must *deliberately* defer
low-priority ticks (heartbeats, non-funded challenge accounts) rather
than discover the `tick_stale` cliff empirically. It is also the reason
the docs/29 §3.4 horizontal-Postgres option is staged rather than
dismissed.

**All PG/Redis throughput figures in this subsection are planning
estimates, not measurements.** There is no load-test data at 100k
accounts. They are derived from documented per-unit limits (MetaApi's
published quotas, docs/09 §11's per-tick latency budget, docs/04 §11's
relay figure) and must be replaced by measured numbers from the docs/29
§6 load test before the second box is bought. The doc's own posture
applies: *measure, don't decide* (§8).

#### 4.11.3 Partitioning and the read path (summary — full sizing in docs/29 §3.4)

- `evaluation_state`, `broker_deals` and `account_snapshots` are
  **partitioned by `tenant_id`** at minimum, with `account_snapshots` and
  `broker_deals` sub-partitioned by day (they are the 100M+ rows/day
  tables). `evaluation_state` is 100k rows and does not need a time
  dimension — it needs tenant locality, because every evaluation query is
  tenant-scoped by the docs/00 §8 non-negotiable.
- Everything outside the hot write path — ANA read models, dispute
  replay, ADM screens — reads a **replica**, never the primary. The
  evaluation write path and the read path do not contend.
- Single-primary-with-partitioning is the V2 plan; the horizontal option
  (Citus, distribution key `tenant_id`) is **staged on a measured
  trigger**, with the arithmetic and the trigger in docs/29 §3.4. It is
  not adopted now: it conflicts with docs/00 §8's non-negotiable #6
  (operable by a 1-person DevOps team) and the corrected sustained load
  does not require it.

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
| **One tenant's spike (v1.1)** | that tenant's lane set saturates; without §4.13 the shared stream and globally-hashed lanes would degrade *every* tenant | per-tenant stream + tenant-owned lane set (D82) contains it; the shared resources (PG, engine) are protected by per-tenant shed levels (D84); the spiking tenant's own `evl_lag_seconds` warns at 120 s, pages at 300 s |
| **Consumer lag outruns scaling (v1.1)** | evaluation falls behind; at 10 min equity is stale and `evl.tick_stale` suppresses verdicts | §4.14: scale out at 60 s of lag, shed levels 1→3 (widen conflation, never drop `deal`/`position`/`guard`/crossing/`resync`), page at 300 s, declare an incident + suspend the docs/29 §4 SLO at 480 s or on any funded-account suppression |
| **Redis Streams trims a lagging group (v1.1)** | entries past `MAXLEN ~100000` are trimmed; evaluation gap for that tenant | not data loss — the outbox/`events` log is the replay source (ADR-6/7). `evl.stream_trimmed` is emitted by comparing `last-delivered-id` against the stream's `first-entry`, then that tenant's range is replayed from PG. Shedding (§4.14) is the prevention |
| **Full-fleet gateway resync (v1.1)** | ≈ 10–20 min at 100k accounts, every account on `evl.tick_stale` | never performed fleet-wide: rolling per shard (2,000 accounts, ≈ 12–24 s of blindness per shard, 2 % blast radius). A simultaneous 50-shard restart is a declared maintenance window announced per tenant via CON-15 (§4.7) |

### 4.13 Per-tenant fairness on the event bus (D82)

**The problem this solves.** Nothing in the v1 design stops one tenant's
traffic spike from degrading another tenant's evaluation latency. Two
distinct mechanisms cause it, and they need separate fixes:

1. **Stream-level proportionality.** All tenants sharing one
   `topic.bridge` stream means one consumer group chewing one FIFO: a
   tenant generating 80 % of the ticks gets ≈ 80 % of the consumer
   capacity. That is proportional, not starved — but proportional means a
   10× spike by tenant A cuts tenant B's evaluation throughput by up to
   10×, and B drifts toward `evl.tick_stale` without having done anything.
2. **Lane-level head-of-line blocking.** `workers` assigns lanes by
   `hash(entity_id) → N lanes` (docs/04 §3.5) with a *global* hash, so
   tenant A's accounts share lanes with tenant B's. A lane is **serial**,
   so every A account hashed to lane 7 delays every B account hashed to
   lane 7. This is the real starvation, and it is invisible in aggregate
   throughput metrics.

**The decision: shard the stream per tenant, and give each tenant shard
its own lane set.** One stream key per tenant — `topic.bridge.{tenant_id}`
— each with its own consumer group, and `workers` lane sets owned by
exactly one tenant shard.

**Why sharding and not weighted fair queuing.** WFQ across lanes was the
alternative, and it is not implementable on Redis Streams *without*
sharding: `XREADGROUP >` delivers undelivered entries **in stream-id
order** to whichever consumer asks. The consumer never gets to choose
which tenant's work to take next — the stream decides. To exercise a
choice you must either read from per-tenant streams, or read into a local
buffer and reorder there, which abandons the at-least-once-plus-
idempotent simplicity of ADR-7 and adds unbounded in-process buffering to
a component whose whole job is to be restartable. **Per-tenant streams
are the precondition for any fairness policy; WFQ is then trivially
expressible on top of them** (and is what the lane-set weights below
implement). Choosing "WFQ instead of sharding" would have meant
re-implementing a queue inside the consumer.

**Why one stream per tenant, and not per tenant-tier.** Tenant count is
small (10 at the corrected target, 25–50 in docs/00 §5's V2 range); Redis
handles thousands of streams and 50 streams at `MAXLEN ~100000` is
≈ 5 GB worst case across the fleet, ≈ 1 GB at 10 tenants — inside the
`redis-streams` container's 2 GB (D51, docs/29 §1.3). One stream per
tenant buys exact per-tenant isolation of **backlog, lag metric, DLQ
depth, replay range and trim detection**, and it aligns the isolation
unit with everything else that is already per tenant: the §4.2 shard
ownership (`(tenant_id, account_id)` hash, 5 shards per tenant), the
§4.7 MetaApi credential set and credit budget, and the docs/00 §8
non-negotiable that every query is tenant-scoped. **One tenant = one
shard set = one stream = one lane set = one credit budget** is a single
isolation unit that an operator can reason about. Tier-grouping was
rejected because it re-creates mechanism 1 inside a tier.

**Lane allocation (weighted, with a floor).** Total lanes
`max(128, 10 × tenants)` (§4.5's arithmetic). Per tenant:
`max(10, ceil(weight_t × total))` lanes, where `weight_t` defaults to the
tenant's share of deployed accounts and is a CON-editable config. **The
floor of 10 lanes per tenant is that tenant's own burst design point**
(10 × 100 ticks/s = 1,000 ticks/s = §4.4's per-tenant burst at 100k ÷ 10
tenants), so a tenant can absorb its own news burst without borrowing
capacity it may not get back. Surplus lanes beyond the sum of floors are
allocated by weight. The supervisor round-robins over tenant lane sets
that have work; within a set, lanes are serial per account
(`hash(account_id) → lane`, docs/04 §3.5 unchanged).

**Guarantee this buys.** A tenant's backlog can consume **only its own
lane set**, so tenant A's spike cannot delay tenant B's evaluation by
more than B's own share of the *shared* resource — Postgres and the
engine (§4.11.2, §4.14) — and both of those are handled explicitly rather
than left implicit: PG by `tenant_id` partitioning (§4.11.3), the engine
by shed levels that are per tenant (§4.14).

**Streams `MAXLEN` and the trim hazard.** `MAXLEN ~100000` per tenant
stream is ≈ 400 s of that tenant's sustained ticks but only ≈ 100 s of
its burst. §4.11.2's drain arithmetic shows a 5-minute platform-wide
burst can put ≈ 150k entries behind a single tenant's group — **past the
trim point**. Trimmed entries are not *lost* (the outbox and the `events`
log are the replay source, ADR-6/ADR-7), but silent trimming would be a
silent evaluation gap. So:
- the consumer tracks `last-delivered-id` against `XINFO STREAM`'s
  `first-entry` / `max-deleted-entry-id` and emits **`evl.stream_trimmed`**
  on any group that has fallen behind the stream's first entry, then
  triggers a replay-from-PG for that tenant's range;
- §4.14's shedding keeps the backlog below the trim point *before* Redis
  enforces it — shedding is the prevention, trim detection is the
  backstop;
- `MAXLEN` stays at ~100000 rather than being raised to ~1M, because
  1M × 1 KB × 10 tenants ≈ 10 GB does not fit the `redis-streams`
  budget and Redis is explicitly never the source of truth (docs/00 §8 #1).

**DLQ stays single, per consumer** (`dlq.evaluation`, docs/04 §3.5) with
`tenant_id` in the envelope and a **per-tenant depth metric + alert**.
DLQ traffic is post-`max_attempts` and low-volume; 50 DLQ streams would
multiply CON screens for no isolation benefit.

### 4.14 Autoscaling signal and load-shedding for the stateless engine tier (D84)

This section assumes **D81** (§5): the engine is a stateless compute
service and `workers` owns state, ordering and idempotency. Under the v1
drifted architecture none of this was possible — an engine that owns a
Postgres account store cannot be scaled by adding replicas, because the
replicas then contend on the same rows it is supposed to own.

**The honest constraint: the deployment target has no autoscaler.**
ADR-9 is one Hetzner box + Docker Compose, and docs/00 §8 non-negotiable
#6 forbids Kubernetes. Compose has `--scale` but no controller that
decides when to use it. So the autoscaling story is stated for the
platform that exists, not the one that would be convenient:

| Tier | Signal | Actuator |
|---|---|---|
| **V2 (Compose, 1–2 boxes)** | `evl_lag_seconds` per tenant (below), scraped by Prometheus | **Operator action**, surfaced in CON: `docker compose up -d --scale engine=N --scale workers=M`. A runbook line, not a controller. |
| **V2.5 (only if the load test proves the manual loop too slow)** | same | A **lag controller**: a ~200-line Compose-scale actuator that reads the same metric and calls the Compose API within its min/max bounds. Explicitly optional, explicitly a new deployable, and it must be justified by measured operator response time before it is built. |
| **V3 (if the platform ever leaves Compose)** | same metric | KEDA/HPA on `redis_streams_consumer_group_lag` — the standard pattern, and the reason the metric is defined in lag terms rather than CPU. |

**The signal.** Redis Streams consumer-group lag is the right signal
(the Kafka-consumer-lag analogue), but **lag in entries is not
actionable — lag in seconds is**. The quantity that matters is
time-to-drain, because it compares directly against the correctness
backstop:

```
evl_lag_seconds{tenant, group} = lag_entries ÷ measured_drain_rate
lag_entries                    = XINFO GROUPS → lag  (Redis ≥ 7.0)
measured_drain_rate            = EWMA of entries/s actually acknowledged
                                 over the last 60 s, per group
```

Supporting metrics: `evl_stream_lag_entries{tenant}`,
`evl_lane_queue_depth{tenant,lane}`, `evl_evaluate_seconds` (the engine
HTTP call, the stateless tier's own saturation), `evl_pg_state_seconds`
(the read + write, the shared resource), `evl_shed_level{tenant}`,
`evl_stream_trimmed_total{tenant}`. **Engine CPU is deliberately not the
scaling signal**: `benches/engine.rs` puts pure evaluation at ≈ 52,600
evals/s single-threaded, so at 10,000 verdict/s the engine is never the
bottleneck — HTTP fan-in and Postgres are. Scaling on engine CPU would
add replicas to a tier that is not saturated while the real constraint
goes unaddressed.

**Thresholds — derived from the `tick_stale` window, not chosen.**
`evl.tick_stale` suppresses verdicts on equity older than **10 minutes**
(docs/09 §6, already implemented). That is the correctness cliff, so the
thresholds are fractions of it:

| `evl_lag_seconds` (any tenant) | Response |
|---|---|
| > 60 s for 60 s | **Scale out**: engine +1 replica, `workers` +1 instance, up to the configured max. Automatic in V2.5/V3, a CON prompt in V2. |
| > 120 s for 5 min | **WARN** — shed level 1 for that tenant (§ below). No page. |
| **> 300 s for 60 s** | **PAGE (P1).** Half the `tick_stale` window: at this lag, verdicts begin being suppressed in ≈ 5 minutes if nothing changes. |
| > 480 s, or any `evl.stream_trimmed`, or any `evl.tick_stale` suppression on a **funded** account | **INCIDENT** — declared, tenant-visible via CON-15, and the docs/29 §4 breach-to-enforcement SLO is *formally suspended* for the duration, with the suspension recorded. |
| < 30 s for 10 min | Scale in, one replica at a time. |

**Load-shedding — widen the conflation window, never drop evidence.**
Under sustained overload the platform sheds by **raising the bridge
conflator's thresholds**, which is the same mechanism D79 already uses,
not a new one. That matters for defensibility: a shed tick is not a lost
observation, because `equity_low_cents` / `equity_high_cents` keep
bounding what happened between emitted ticks (invariant I-22), exactly as
they already do for conflated quotes. **What is never shed:** `deal`,
`position`, `guard`, `guard`-crossing (I-21 — a crossing quote is never
conflated away), and `resync`. Those are the triggers that can change a
verdict.

The shed level reuses **§4.7's existing resync priority list**
(guard-band → funded → open positions → the rest) rather than inventing a
new ordering:

The baseline it works against is §4.4's sustained ≈ **1,791/s** = heartbeat
733/s + material 1,000/s + deal/position 58/s. **Funded accounts are 50 %
of the fleet (docs/29 §1.1), so the heartbeat term splits ≈ 367/s funded /
≈ 367/s non-funded, and the material term ≈ 500/s each** — which is why the
ladder's ceiling is ≈ 60 % and not 100 %: the priority list protects funded
and guard-band accounts, so roughly half the load is never sheddable.

| Level | Trigger | Action | Cumulative sustained load removed |
|---|---|---|---|
| **0** | normal | nothing | — |
| **1** | `evl_lag_seconds > 120` for one tenant | `heartbeat` interval 60 s → 180 s (open) and 300 s → 900 s (flat), for **non-funded** accounts only | non-funded heartbeat 367/s → 122/s (15,000 open ÷ 180 + 35,000 flat ÷ 900). **Removes ≈ 245/s = ≈ 14 %** of sustained. Zero correctness cost — see the two notes below |
| **2** | `> 300`, or level 1 held 15 min | + `material` threshold 10 bps → 25 bps for non-funded accounts | non-funded material 500/s → 200/s. **Cumulative ≈ 545/s = ≈ 30 %** |
| **3** | `> 480`, or any funded-account `tick_stale` | + funded heartbeats widen too **except guard-band accounts** (the 1 % nearest a floor keep 60 s / 300 s absolutely); + `material` 10 bps → 25 bps fleet-wide; + non-funded challenge accounts' lane weight drops to the floor while funded and guard-band accounts keep full rate. **This is the incident level** | heartbeat 733/s → ≈ 253/s, material 1,000/s → ≈ 400/s. **Cumulative ≈ 1,080/s = ≈ 60 %**, and the remaining capacity is reallocated to funded + guard-band by the lane weights |

**Two notes that make level 1 safe, because both were easy to get wrong:**

1. **Widening the heartbeat interval cannot trip `evl.tick_stale`.** The
   staleness guard measures *tick age* — `now − envelope occurred_at` — and
   `occurred_at` is the receive time of the newest **frame** folded into the
   tick, data *or* `Health` (docs/09 §6, §4.6 above). `Health` frames arrive
   at ≤ 1 per 10 s per account while the stream is `live` (§4.2), so a
   heartbeat emitted every 900 s still carries an `occurred_at` no older
   than ≈ 10 s. **A heartbeat never refreshes stale data** — it restates
   the newest frame's time, and a `stale` stream emits no heartbeats at all
   (§4.7), which is the case the guard exists for. The emission *cadence*
   and the tick *age* are different quantities, and only the second one is
   guarded. (The naive reading — "900 s > the 600 s window, so level 1
   breaks the guard" — is wrong, and is exactly the kind of error this note
   is here to prevent.)
2. **Widening the heartbeat does not widen the crossing-detection gap by
   900 s.** The heartbeat's stated job (§4.4) is to bound the worst case of
   a *stale floor hint* to ≤ 60 s. Under level 1 that bound becomes ≤ 180 s
   for non-funded accounts — but it was never the only bound: the `material`
   trigger (10 bps, unchanged at level 1) still fires at ≤ 1/10 s per active
   account, and the `guard` and `guard`-crossing triggers (I-21, uncapped)
   still fire whenever a hint *is* present and correct. A hint goes stale
   only if evaluation itself has stopped, which is the condition shedding is
   responding to. So level 1 trades a ≤ 60 s stale-hint bound for a ≤ 180 s
   one on accounts that are not the firm's money — which is the priority
   list's own ordering.

**The level-2/3 material figures are a lower bound.** Rate ∝ 1/threshold
assumes equity movement is roughly uniform in log-space; under a diffusive
model the time to move *X* bps scales as *X²*, which would make 10 → 25 bps
remove ≈ 84 % of the material term rather than 60 %. The linear figure is
quoted because it is the conservative one, and load test **LT-6** replaces
it with a measurement.

**Delivery mechanism (reuse, not invention).** `workers` publishes
`evl.load_shed {tenant_id, level, reason, at}` on Redis pub/sub and the
bridge applies it — the *same* advisory cache-invalidation pattern as
`evl.floors` (§4.4) and `rule_pack.activated`. Redis-down degrades to
level 0 at the bridge (the safe direction: shed nothing, keep emitting)
with a 30 s PG reload fallback, exactly as floor hints already do (the level is persisted in `evl_load_shed`, docs/64 §4.9 "as implemented"). The
decision to shed is made where the lag is observable (`workers`); the
act of shedding happens where the tick is born (the bridge conflator), so
no outbox row, relay `XADD` or PG write is spent on a tick that is about
to be deferred.

**What is explicitly *not* a capacity plan.** `evl.tick_stale` is the
correctness backstop — it stops verdicts on stale equity — and it is
already implemented. It is not, and must not be treated as, a substitute
for the above: a system that reaches `tick_stale` on funded accounts has
already failed its docs/29 §4 SLO, which is why that condition is an
incident and not a degradation.

## 5. Decisions (owner, 2026-09-25)

D77–D80 were presented and chosen interactively; D81–D84 came out of the
multi-tenant capacity correction (v1.1) and are written up in full in
**docs/64**. All are registered in `scripts/design-questions.json`
(rendered into docs/37):

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

The v1.1 decisions (full text in **docs/64**, registered in docs/37):

- **D81 — the Rust engine is a stateless compute service; `workers` owns
  state.** `propfirm-engine` is pared back to ADR-11's original scope —
  `evaluate(state, rules, tick) → (verdict, new_state, hints)`, no
  database of its own, no tenant/account CRUD, no idempotency store. The
  Postgres-backed `AccountStore`, the idempotency store, per-account/
  per-tenant ordering, retry/DLQ and the *writes* behind
  override/manual-run/emergency-stop move to a `workers` evaluation
  consumer built on the platform's existing consumer-supervisor pattern
  (docs/04 §3.5) — the same mechanism NOT/LED/AUD already use. ADR-11 is
  re-confirmed, not superseded. *Alternatives rejected:* keep the
  self-contained engine (two components both owning account state, and
  every retry/ordering fix made and tested twice); write a bespoke Rust
  consumer for EVL only (a third ordering implementation).
- **D82 — per-tenant stream sharding for event-bus fairness** (§4.13):
  one `topic.bridge.{tenant_id}` stream + one tenant-owned lane set per
  tenant, lanes `max(10, ceil(weight × total))`. *Alternatives rejected:*
  weighted fair queuing on a shared stream (not implementable — `XREADGROUP`
  delivers in stream order, so the consumer never chooses); tenant-tier
  grouping (re-creates the unfairness inside a tier).
- **D83 — Postgres write scaling for the evaluation path** (§4.11.2,
  §4.11.3, sized in docs/29 §3.4): partition `evaluation_state`,
  `broker_deals` and `account_snapshots` by `tenant_id` (+ day for the two
  high-volume tables); all non-hot-path reads go to a replica;
  single-primary-with-partitioning is the V2 plan and **horizontal
  Postgres (Citus, distribution key `tenant_id`) is staged on a measured
  trigger, not adopted now**. *Alternatives rejected:* adopt Citus now
  (breaks docs/00 §8 #6's 1-person-DevOps non-negotiable for load that
  does not require it); do nothing (burst has zero margin against the
  `tick_stale` cliff — §4.11.2's drain arithmetic).
- **D84 — lag-in-seconds as the autoscaling signal, conflation-widening
  as load-shedding** (§4.14): `evl_lag_seconds` = consumer-group lag ÷
  measured drain rate; page at 300 s (half the `tick_stale` window);
  incident at 480 s, on `evl.stream_trimmed`, or on any funded-account
  `tick_stale` suppression. Shedding widens the bridge conflator's
  thresholds per tenant via `evl.load_shed` pub/sub (the `evl.floors`
  pattern) and reuses §4.7's resync priority list; `deal`/`position`/
  `guard`/crossing/`resync` are never shed. *Alternatives rejected:*
  scale on engine CPU (the engine is never the bottleneck — ≈ 52,600
  evals/s single-threaded vs a 10k verdict/s target); treat
  `evl.tick_stale` as the capacity plan (it is a correctness backstop;
  reaching it on funded accounts is already an SLO failure).

## 6. Test hooks

| # | Invariant / check | Asserts | Owner |
|---|---|---|---|
| I-21 | no crossing conflated away | for any generated quote sequence and floor set, **every** quote with equity ≤ a floor hint yields an emitted tick (property test on the conflator) | 63 §4.4 / 08 §3.3 |
| I-22 | conflation evidence | each tick's `equity_low/high_cents` bound every quote folded since the previous tick; `equity_low_cents` ≥ every floor hint unless the tick is itself a crossing tick | 63 §4.4 |
| I-23 | no silent frame loss | under injected backpressure, `Deal`/`Positions`/`AccountInfo` frames are never dropped — they queue, or the account is resynced (chaos test on the gateway↔bridge link) | 63 §4.2 |
| — | broker-truth equity | a `prices` fixture without `equity` produces **no** equity update (the SDK's local recompute is never forwarded — F5) | 63 §4.2 |
| — | resync idempotency | replaying the same recorded session twice leaves `broker_deals`/`broker_positions` byte-identical (extends I-15) | 63 §4.7 |
| — | fixture corpus | SDK `packetLogger` recordings from staging (≥ 24 h, 3 demo accounts, incl. a forced disconnect) replay through gateway + bridge deterministically; BRG-43 runs them per adapter | 08 §16 |
| — | load | **100k simulated accounts** (10 tenant partitions × 10k, recorded-packet replay, ×N fan-out) → ≤ 2,500 ticks/s sustained and a 10k/s burst drained inside the 10-min `evl.tick_stale` window at the default thresholds; quote→verdict p95 < 50 ms internal; relay ≥ 600k events/min across ≥ 10 partitions; `workers` ≥ 128 lanes with no lane starved (§4.13's fairness assertion); PG evaluation path ≤ 10 ms p95 at 5,000 q/s. **v1.1: the 10k/250-ticks-per-second version of this row is retired — a load test that validates 10k accounts says nothing about whether the system survives 100k.** | 29 §6 |

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
7. **Q7** (v1.1, sizes F12) — real `bridge-stream` RSS **per account**
   with `PgHistoryStorage`, measured at 2,000 accounts/shard, and the
   wall-clock + PG write volume of a single-shard cold resync. Q3 measures
   the same thing at V1 scale; Q7 measures it at the corrected target,
   because F12's second-box requirement and §4.11's ≈ 50-shard count both
   follow from it. Exit: a shard count and a box count, not an estimate.
8. **Q8** (v1.1, sizes §4.7's fallback budget) — ask MetaApi directly
   whether the 18k credits/min front-end-server limit is **per
   (`Client-Id`, server) pair** or **global per front-end server**.
   Reading A makes per-tenant credentials multiply the fallback budget
   (9,600 accounts/min platform-wide); Reading B caps it at 960
   accounts/min regardless of tenant count, which turns a MetaApi-wide
   outage at 100k accounts into a declared degradation rather than a
   recoverable incident. Plan against B until answered. Also confirm the
   ≤ 300 accounts/user/server cap under `reliability: high` (does a
   redundant instance count as a second account?).

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
5. **v1.1 — the capacity correction's downstream doc edits (F12, F13).**
   docs/04 §3.4 (the 13-month `events` retention needs the `bridge.tick`
   tier exception), docs/04 §11 (the relay's "2k msg/s" single-process
   row and the 60k events/min target), docs/06 §1 (the second box moves
   from V3 to a V2 prerequisite), docs/08 §11 and docs/09 §11 (their V2
   headroom columns quote the 10k figures), and docs/32
   (`account_snapshots`/`broker_deals`/`bridge.tick` partitioning +
   retention DDL). docs/29 §1.1/§1.3/§3.4/§6 are corrected in this pass;
   the rest are listed here so the drift is registered rather than
   silent — the same discipline F11 applies to generator drift.

# Bridge (Broker) API Contract (BRG)

Status: DRAFT
Owner: TBD
Version: v1
Last updated: 2026-09-19 (eleventh pass, docs/51)

Derived from the V1 Execution Sheet (V1.0 only). Nothing here is final until contract freeze.

## Scope
One broker capability interface with an MT5 adapter via MetaApi/Brokeree (BVR-04: no raw Manager API clients), account creation, credential storage/delivery, balance/equity sync, position/trade sync, on-demand sync, enforcement execution with confirmations, leverage/group config, enable/disable trading, adapter contract tests, credential rotation. (BRG-01, BRG-02, BRG-05, BRG-06, BRG-07, BRG-08, BRG-09, BRG-10, BRG-11, BRG-12, BRG-14, BRG-43, BRG-44)

## No direct HTTP surface in V1
The bridge is invoked by other modules (LCC provisioning, EVL evaluation inputs, enforcement worker) and by workers, not by frontends. The sheet defines no trader/admin endpoints for BRG. This module has no HTTP contract in V1 — see module spec later. If the working session wants an admin "force sync" endpoint it is a scope addition: TODO — needs owner decision (compare BRG-09 on-demand sync, which is worker-internal).

## Capability interface (BRG-01)
One interface covering: create, state, positions, close, disable, enable, leverage, password. Domain code never branches per platform. Every adapter must pass the shared contract test suite (BRG-43).

## Internal operations (cited)
- Create account: group, leverage, initial balance, with idempotency key so retries never duplicate accounts (BRG-05). Called by LCC-05/LCC-06.
- Credentials: stored encrypted (TEN-12, BRG-44 rotation), delivered to trader via portal and email (BRG-06, NOT-03).
- Sync worker: polls balances and equity at a configurable interval writing timestamped snapshots (BRG-07); polls open positions and closed trades into a unified schema (BRG-08). Interval: 60 s default, tenant-configurable 30–300 s, staggered, with a per-tenant poll budget (docs/08 §3.3). Snapshots land in `account_snapshots` (1 row/account/min, 14-day rolling — docs/08 §9, D35).
- On-demand sync for a single account before eligibility checks (BRG-09). Called by PAY-02/PAY-03.
- Enforcement: disable-then-close commands executed from the command queue (EVT-20) with retries (3, exponential backoff; circuit-breaker per account) and confirmations via broker re-read, written back to command and account state so FAILED is recorded only after real closure (BRG-11; docs/08 §3.4). `credit` never auto-retries. Triggered by EVL-17 and LCC-27.
- Leverage/group set at creation and phase change per rule set config (BRG-12).
- Enable/disable trading for suspensions and appeals (BRG-14). Called by LCC-11.

## Events consumed
- Consumes commands from `command_queue` (EVT-20) — commands, not events.
- Sync writes feed EVL-05 evaluation triggers (snapshots, trade close).

## Events emitted
- **`bridge.tick`** (v1) — every sync tx, per account (tenth pass D28, docs/50); the observed record (EVL-49); no audit mirror (docs/05 §14).
- **`bridge.sync_gap`** (v1) — history-window deals-count mismatch (eleventh pass D33, docs/51); EVL verdicts on it carry `gap_flagged`.
- Extended (post-V1) forms — `bridge.account_created/failed`, `bridge.trading_disabled/enabled`, `bridge.positions_closed`, `bridge.reconciliation_exception`, `bridge.command_dead`, `ops.provider_health` — per docs/08 §4.2.

## Open contract questions
- Resolved 2026-09-19 (D36, docs/51): no admin "force sync" endpoint in V1 — BRG-09 on-demand sync stays worker-internal (PAY-02/03 call it before eligibility, docs/11 §3); ADM observes freshness via the health surface (docs/08 §7.2).
- Resolved 2026-09-19 (D35, docs/51): snapshot schema = `account_snapshots` (docs/08 §9): minute buckets, equity/balance/margin/free_margin cents, broker_time; 14-day rolling partitions; daily rollup to ANA.
- Resolved 2026-09-19 (D33, docs/51): gap detection = history-window deals-count reconciliation; `last_deal_ticket` is a fetch cursor, never a continuity oracle (MT5 tickets are server-global).
- TODO — needs owner decision: credential delivery email content vs security (BRG-06 sends credentials by email; template ownership NOT-05 has no such template).

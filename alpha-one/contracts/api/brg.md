# Bridge (Broker) API Contract (BRG)

Status: DRAFT
Owner: TBD
Version: v1
Last updated: TODO

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
- Sync worker: polls balances and equity at a configurable interval writing timestamped snapshots (BRG-07); polls open positions and closed trades into a unified schema (BRG-08). Interval value — TODO — needs owner decision.
- On-demand sync for a single account before eligibility checks (BRG-09). Called by PAY-02/PAY-03.
- Enforcement: disable-then-close commands executed from the command queue (EVT-20) with retries and backoff (BRG-10); confirmations written back to command and account state so FAILED is recorded only after real closure (BRG-11). Triggered by EVL-17 and LCC-27.
- Leverage/group set at creation and phase change per rule set config (BRG-12).
- Enable/disable trading for suspensions and appeals (BRG-14). Called by LCC-11.

## Events consumed
- Consumes commands from `command_queue` (EVT-20) — commands, not events.
- Sync writes feed EVL-05 evaluation triggers (snapshots, trade close).

## Events emitted
- None named in the sheet. Snapshot persistence and confirmation writes are internal state changes. TODO — needs owner decision (whether sync/enforcement outcomes should emit events for ANA-01; the sheet does not say).

## Open contract questions
- TODO — needs owner decision: sync interval and per-account polling cost budget (MetaApi is per-active-account priced; Integration Map).
- TODO — needs owner decision: snapshot table schema details (BRG-07 says timestamped snapshots; fields unspecified beyond balance/equity).
- TODO — needs owner decision: command retry limits and what marks a command permanently failed (BRG-10/EVT-20).
- TODO — needs owner decision: whether enforcement confirms close via position poll or broker callback (BRG-11 mechanics).
- TODO — needs owner decision: credential delivery email content vs security (BRG-06 sends credentials by email; template ownership NOT-05 has no such template).

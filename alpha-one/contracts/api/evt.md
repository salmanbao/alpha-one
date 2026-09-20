# Event Bus API Contract (EVT)

Status: DRAFT
Owner: TBD
Version: v1
Last updated: 2026-09-20

Derived from the V1 Execution Sheet (V1.0 only). Nothing here is final until contract freeze.

## No HTTP surface in V1
EVT is infrastructure: the outbox pattern (EVT-01), the relay process (EVT-02), the envelope (EVT-03), idempotent consumption (EVT-05), the append-only event log (EVT-08), inbound webhook verification utilities (EVT-10), and the command queue (EVT-20). None of these are trader- or admin-facing HTTP endpoints. This module has no HTTP contract in V1 — see module spec later.

## What it provides instead (internal contracts)

### Event envelope (EVT-03)
Every event carries exactly: `id`, `type`, `version`, `tenant_id`, `occurred_at`, `payload`. See `contracts/events/catalog.md` and `contracts/events/payloads/*.json`.

### Outbox (EVT-01)
Domain state and the outbox row are written in one Postgres transaction (OPS-06 database). No event is lost; no event is emitted for a rolled-back transaction.

### Relay (EVT-02)
A dedicated relay process polls the outbox and publishes to Redis Streams (BVR-09: no other broker in V1). Delivery survives application restarts. Redis AOF durability per OPS-26.

### Idempotent consumers (EVT-05)
Consumers deduplicate by event `id`. At-least-once delivery is the contract; exactly-once is out of scope (Out Of Scope sheet).

### Event log (EVT-08)
Every published event is appended to an append-only log table for replay and audit (Postgres, OPS-06).

### Inbound webhook verification (EVT-10)
Shared utilities verify provider signatures and deduplicate by provider event id, used by payment webhooks (CHK-07) and KYC webhooks (KYC-05).

### Command queue (EVT-20)
Broker commands are requests, not facts. They live in a separate Postgres command table with retry and backoff (used by BRG-10 enforcement execution). Commands never appear in the event catalog.

## Events emitted/consumed
- Emits: none of its own (transport only).
- Consumes (carries): every event in `contracts/events/catalog.md`.

## Open contract questions
- Resolved 2026-09-19 (docs/54): shared per-topic streams `topic.<domain>` (docs/04 §3.3; tenant_id is in the envelope, lanes order by entity_id); consumer group = the consumer's declared name (§3.5).
- Resolved 2026-09-19 (docs/54): keyset poll, 500/batch (docs/04 §3.3); lag alerting: `/readyz` fails past 60 s relay lag (GW-14) and `evt.relay_stopped` CRITICAL at 60 s (docs/04 §6.2).
- Resolved 2026-09-19 (docs/54): outbox rows pruned 7 d after publish; `events` retained 13 months in PG, then R2 archive (EVT-22) — the replay window.
- Resolved 2026-09-19 (docs/54): the numbers live with the executor — docs/08 §3.4: 3 retries with backoff, circuit-breaker per account, terminal = `dead` + CRITICAL + LCC-27 monitor backup; `credit` never auto-retries.
- Resolved 2026-09-19 (docs/54): `version` bumps on any payload change, additive-only between freezes (the envelope schema's own rule, contracts/events/payloads/envelope.schema.json).

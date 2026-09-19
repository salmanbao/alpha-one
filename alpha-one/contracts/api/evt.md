# Event Bus API Contract (EVT)

Status: DRAFT
Owner: TBD
Version: v1
Last updated: TODO

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
- TODO — needs owner decision: Redis Stream key naming per tenant vs shared stream, and consumer group naming.
- TODO — needs owner decision: relay batch size / poll interval and lag alerting threshold.
- TODO — needs owner decision: outbox retention policy and event log retention policy (replay window).
- TODO — needs owner decision: command table retry/backoff parameters and dead-letter handling (EVT-20 says retry and backoff, no numbers).
- TODO — needs owner decision: envelope `version` bump policy per event type.

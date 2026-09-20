# event-bus — render to PNG

Outbox → relay → Redis Streams → consumers. Derives from EVT-01, EVT-02, EVT-03, EVT-05, EVT-08, EVT-20. Redis Streams only in V1 (ADR-6, docs/04 §4; BVR-09).

```mermaid
flowchart LR
    subgraph producers[Module services]
        LCC[LCC-23 lifecycle events]
        CHK[CHK-09 order.paid + CHK-43 checkout.session.expired]
        PAY[PAY-09 payout.approved/rejected + PAY-12 payout.settled]
        KYC[KYC-05 kyc.* events — V1 per Decision 5]
    end
    OB[(Postgres outbox — EVT-01, same transaction as domain state)]
    RL[Relay process — EVT-02, polls outbox]
    RS[(Redis Streams — AOF per OPS-26)]
    LG[(Postgres event_log — EVT-08, append-only)]
    subgraph consumers[Consumers — idempotent by event id, EVT-05]
        NOT[NOT-01 notifications]
        LED[LED postings LED-04, LED-07, LED-08]
        DOC[DOC-04 certificates]
        ANA[ANA-01 read models]
        LCCP[LCC-05/LCC-06 provisioning]
    end
    CQ[(Postgres command_queue — EVT-20, separate table)]
    ENF[Enforcement worker BRG-10]

    LCC --> OB
    CHK --> OB
    PAY --> OB
    KYC --> OB
    OB --> RL
    RL --> RS
    RL --> LG
    RS --> NOT
    RS --> LED
    RS --> DOC
    RS --> ANA
    RS --> LCCP
    EVL17[EVL-17 hard breach] --> CQ
    LCC27[LCC-27 terminal cleanup] --> CQ
    CQ --> ENF
    ENF --> BRG[Broker BRG-10/BRG-11]
    CQ -.->|commands are requests, not facts| RS
```

Key contract points: domain state and outbox row written in one transaction (EVT-01); relay survives restarts (EVT-02); envelope id/type/version/tenant_id/occurred_at/payload (EVT-03); at-least-once delivery with idempotent consumers (EVT-05); every published event logged append-only (EVT-08); broker commands never in the event stream (EVT-20).

## Confirmed parameters (resolved 2026-09-20, gap-closure pass — all by citation, docs/04)
- **Stream naming**: one stream per event family, `topic.<domain>` (e.g. `topic.account`, `topic.payout`) — the V1 topic set is closed by the catalog; each stream is trimmed with `MAXLEN ~ 100k` (approximate trim keeps XADD O(1)).
- **Consumer groups**: group name = the consumer's name (NOT-01, LED, DOC, ANA, LCC…); every consumer joins its own group so streams fan out per consumer with independent offsets (ADR-7).
- **Partitioning**: no per-tenant partitioning in V1 — streams are partitioned by *entity lane* (the event's primary entity), not tenant; tenant scale in V1 is one firm (docs/01 §4.3, docs/04 §11).
- **DLQ**: dead-letter stream `dlq.{consumer}` + CRITICAL alert on unknown-higher-version or schema-reject (ADR-7; the envelope's `version` is the compatibility knob).
- **Lag alerting**: `relay.lag` metric per stream/group + `evt.relay_stopped` CRITICAL after 60 s without a publish (docs/04 §11; docs/06 relay monitoring).
- **Relay batch/poll**: keyset pagination, batch size 500, `SELECT … FOR UPDATE SKIP LOCKED`; one Redis `XADD` batch per poll (pipeline); relay liveness via the `relay:lock` key with a 30 s heartbeat steal (docs/04 §3.3/§11). Exact poll cadence is a tuning detail fixed at ops time, not a contract.
- **Outbox retention**: prune published rows after 7 days (the event_log is the durable record, EVT-08) — docs/04 §11.

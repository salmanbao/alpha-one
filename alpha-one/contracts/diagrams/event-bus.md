# event-bus — render to PNG

Outbox → relay → Redis Streams → consumers. Derives from EVT-01, EVT-02, EVT-03, EVT-05, EVT-08, EVT-20. Redis Streams only in V1 (BVR-09).

```mermaid
flowchart LR
    subgraph producers[Module services]
        LCC[LCC-23 lifecycle events]
        CHK[CHK-09 order.paid + CHK-43 checkout.session.expired]
        PAY[PAY-09 payout.approved/rejected + PAY-12 PayoutPaid]
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

## Open contract questions
- TODO — needs owner decision: stream/consumer-group naming, partitioning per tenant, and lag alerting.
- TODO — needs owner decision: relay batch/poll parameters and outbox retention.

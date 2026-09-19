# lanes — render to PNG

High-level service lanes. Derives from OPS-01: "every service including api, workers, relay, bot, and frontends runs as a Docker image built in CI". Compose stack on Hetzner (OPS-02). Edge is Cloudflare (TEN-02, BVR-05/BVR-12: no standalone gateway).

Resolved 2026-09-17: **no `bot` lane in V1** — OPS-01's `bot` reference is a stale forward reference to the V2 Telegram bot worker (NOT-09, V2.0). V1 lanes: edge, api, workers, relay, frontends.

```mermaid
flowchart LR
    subgraph edge[Cloudflare edge]
        CF[DNS + WAF + tenant resolution input]
    end
    subgraph api[API service]
        GW[In-app middleware: GW-02 tenant, GW-03 auth, GW-04 permissions, GW-05 rate limit, GW-12 idempotency]
    end
    subgraph workers[Workers]
        W1[Sync worker: BRG-07, BRG-08]
        W2[Evaluation: EVL-05]
        W3[Enforcement: BRG-10, EVT-20]
        W4[Notifications: NOT-01]
        W5[Documents: DOC-04]
        W6[Provisioning: LCC-05, LCC-06]
        W7[Ledger postings: LED-04, LED-07, LED-08]
        W8[Analytics read models + nightly: ANA-01]
    end
    subgraph relay[Relay process]
        R[Outbox relay: EVT-02]
    end
    subgraph frontends[Frontends]
        TD[Trader portal: TD-02, TD-03, TD-05, TD-09, TD-10]
        ADM[Admin panel: ADM-05 + module screens]
        CON[Platform console: CON-29]
    end
    PG[(Postgres: OPS-06, OPS-07)]
    RD[(Redis: EVT-02 Streams, GW-05, AUTH-07, BullMQ BVR-19)]
    R2[(R2 object storage: TEN-18, DOC-05)]
    BRG[MetaApi broker adapter: BRG-01, BRG-02]
    PVP[Payment providers: CHK-04]
    KYCP[KYC provider: KYC-01 Veriff]
    EM[Email provider: NOT-03 Postmark]

    CF --> GW
    TD --> CF
    ADM --> CF
    CON --> CF
    GW --> PG
    GW --> RD
    workers --> PG
    relay --> RD
    R --> RD
    workers --> R2
    W1 --> BRG
    W3 --> BRG
    GW --> PVP
    workers --> KYCP
    workers --> EM
```

## Open contract questions
- Resolved 2026-09-17: no `bot` lane in V1 (OPS-01's reference is a V2 forward reference to NOT-09). V1 lanes shown above.

# account-state — render to PNG

The LCC-02 state machine with the resolved edge list (2026-09-17). States are exactly those named by LCC-02. TERMINATED is terminal-only — no outgoing edges (LCC-27 cleanup guarantees no orphaned broker state; a dead account cannot transition). Phase is a per-challenge ordinal (see `data/dictionary.md` `accounts.phase`); the funded stage is `status = FUNDED`, not a phase.

```mermaid
stateDiagram-v2
    [*] --> CREATED: purchase paid (LCC-05, CHK-09)
    CREATED --> ACTIVE: broker account provisioned + credentials delivered (BRG-05, BRG-06)
    ACTIVE --> PASS_PENDING: objectives met (EVL-19)
    ACTIVE --> BREACH_DETECTED: hard breach (EVL-17)
    ACTIVE --> SUSPENDED: admin suspend (LCC-11, V1.1)
    PASS_PENDING --> VERIFICATION: queued for verification per config (EVL-19)
    PASS_PENDING --> AWAITING_ACTIVATION: activation fee configured (LCC-08)
    VERIFICATION --> AWAITING_ACTIVATION: approved, fee due (LCC-06 + LCC-08)
    VERIFICATION --> TERMINATED: verification rejected
    AWAITING_ACTIVATION --> TERMINATED: payment window elapsed, no fee
    BREACH_DETECTED --> CLOSING: disable-then-close commands enqueued (EVL-17, BRG-10)
    CLOSING --> FAILED: broker confirms closure (BRG-11)
    FUNDED --> SUSPENDED: admin suspend (LCC-11, V1.1)
    SUSPENDED --> ACTIVE: resume from evaluation-phase suspend (LCC-11)
    SUSPENDED --> FUNDED: resume from funded-phase suspend (LCC-11)
    FUNDED --> TERMINATED: end of engagement (LCC-27)
    FAILED --> TERMINATED: archival (LCC-27)
    FAILED --> [*]: terminal; cleanup done (LCC-27)
    TERMINATED --> [*]: terminal-only; no outgoing edges (LCC-27)
```

Admin force-terminate (LCC-27): `<any> → TERMINATED`.

Spawn edges — the passing account terminates at PASS_PENDING, VERIFICATION, or AWAITING_ACTIVATION and a **new account** is created (not a transition of the same row):
- Next-phase creation (mid-challenge pass): new `CREATED` with `parent_account_id` set (LCC-06).
- Funded creation (final-phase pass, no activation fee): new `FUNDED`.
- Funded creation (activation fee paid): new `FUNDED`.

Every transition is recorded with prior state, new state, trigger, actor, inputs (LCC-03). Hard breach enqueues commands (EVL-17, EVT-20). Terminal states close positions and disable at broker (LCC-27, BRG-10).

Citation note: the AWAITING_ACTIVATION hold-and-pay flow traces to LCC-08, which is **V2.0** in the Master Backlog — the state itself is fixed by LCC-02 (V1). Flagged in `contracts/README.md` open questions as a source-PRD confirmation, not a contract decision.

## Open contract questions
- LCC-08 (V2.0) is cited for the AWAITING_ACTIVATION hold-and-pay flow — confirm with PRD owners whether a V1 activation-fee product is intended (see `api/lcc.md`).

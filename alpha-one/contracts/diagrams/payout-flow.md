# payout-flow — render to PNG

Payout flow: request → eligibility → approval → execution → ledger. Derives from PAY-01, PAY-02, PAY-03, PAY-04, PAY-08, PAY-09, PAY-12, PAY-14, KYC-08, RSK-11, LED-07, LED-08, BRG-09.

```mermaid
sequenceDiagram
    participant T as Trader (PAY-01)
    participant PAY as Payout (PAY)
    participant BRG as Bridge (BRG-09 on-demand sync)
    participant KYC as KYC gate (KYC-08)
    participant RSK as Risk hold (RSK-11)
    participant FIN as Finance approver (PAY-08)
    participant COO as COO (PAY-12 manual)
    participant LED as Ledger (LED-07, LED-08)
    participant EVT as Outbox/Relay (EVT-01)

    T->>BRG: triggers fresh snapshot (on-demand sync)
    T->>PAY: request payout (PAY-01, idempotent GW-12)
    PAY->>PAY: compute available profit (PAY-02: balance+equity − initial − prior payouts)
    PAY->>KYC: KYC approved? (PAY-03 via KYC-08)
    PAY->>RSK: open risk case or suspension? (PAY-04)
    PAY->>PAY: min/max, delays, frequency, status checks (PAY-03, PAY-21)
    alt ineligible
        PAY-->>T: payout.ineligible with sub-reason
    else eligible
        PAY->>FIN: enter approval queue (PAY-08 full context)
        FIN->>PAY: approve (PAY-09) — emits payout.approved (outbox EVT-01)
        PAY->>LED: obligation posted (LED-07, PAY-14)
        FIN->>COO: approved batch, optional export (PAY-44)
        COO->>PAY: record execution: provider, reference, amount, timestamp (PAY-12)
        PAY->>LED: settle obligation (LED-08)
        PAY->>EVT: PayoutPaid (PAY-12, via outbox — Decision 6, consumed by LED-08, DOC-04, ANA-01)
    end
    Note over FIN,COO: reject path: reason recorded (PAY-09), payout.rejected emitted, trader notified (NOT-05)
```

## Open contract questions
- TODO — needs owner decision: who moves approved → processing → paid given manual execution (PAY-13 states vs PAY-12 direct recording).
- TODO — needs owner decision: whether on-demand sync (BRG-09) is automatic in the request flow or operator-triggered.

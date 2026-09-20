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
        PAY->>EVT: payout.settled (PAY-12, via outbox — catalog name; consumed by LED-08, DOC-04, ANA-01)
    end
    Note over FIN,COO: reject path: reason recorded (PAY-09), payout.rejected emitted, trader notified (NOT-05)
```

## Confirmed by citation (resolved 2026-09-20, gap-closure pass — docs/11, docs/07)
- **Who moves `approved → processing → paid`** — nobody, in V1: `processing` is a **reserved state with no V1 entry path** (docs/11 §3.3). V1 terminal states are `paid` and `rejected`; the manual execution recording (PAY-12 — provider, reference, amount, timestamp, amount must equal the approved amount to the cent or `payout.execution_mismatch` 400) moves `approved → paid` **directly**, with the LED-08 settlement posting and the `payout.settled` event in the same step. The `approved → processing → paid` chain is the **V2** design (automated rail executor PAY-24, docs/11 §3.3 note).
- **On-demand sync (BRG-09)** — it is **automatic in the request flow, not operator-triggered**: the trader's payout request triggers the fresh snapshot, and the PAY-03 eligibility gate runs synchronously against it (docs/11 §2 flow: "trader (TD) ──request──► BRG-09 on-demand sync (fresh snapshot)"). This is also why the payout's risk/suspension check (PAY-04) is a synchronous status check on `accounts.state`, not an event consumer (docs/11 §3.1/§3.7, D39).
- **Event name**: the catalog name is `payout.settled` (the "PayoutPaid" label in the earlier diagram draft was a legacy name — see contracts/events/catalog.md, D60).

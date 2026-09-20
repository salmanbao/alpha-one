# build-order — render to PNG

Module dependency order from the `Depends On` column of the V1 Execution Sheet (V1.0 + V1.1 rows; inter-module edges only). This mirrors the sheet's dependency data — it is a transcription, not an invention.

```mermaid
flowchart TD
    OPS[OPS infra: OPS-01..OPS-38]
    TEN[TEN: TEN-01, TEN-02, TEN-03, TEN-42]
    AUTH[AUTH: AUTH-01..AUTH-43]
    GW[GW: GW-01..GW-18]
    EVT[EVT: EVT-01..EVT-20]
    AUD[AUD: AUD-01, AUD-03, AUD-04, AUD-21, AUD-23]
    EVL[EVL: EVL-01..EVL-36]
    BRG[BRG: BRG-01..BRG-44]
    LCC[LCC: LCC-01..LCC-27]
    CHK[CHK: CHK-01..CHK-42]
    KYC[KYC: KYC-01..KYC-36]
    PAY[PAY: PAY-01..PAY-45]
    NOT[NOT: NOT-01..NOT-13]
    DOC[DOC: DOC-01..DOC-06]
    LED[LED: LED-01..LED-18]
    RSK[RSK: RSK-01, RSK-10, RSK-11]
    ANA[ANA: ANA-01, ANA-32]
    CON[CON: CON-01, CON-29, CON-30]
    TD[TD frontend: TD-02..TD-10]
    ADM[ADM frontend: ADM-05]

    OPS --> TEN
    OPS --> GW
    OPS --> EVT
    OPS --> LED
    OPS --> AUD
    TEN --> AUTH
    TEN --> GW
    TEN --> EVL
    TEN --> CHK
    TEN --> KYC
    AUTH --> GW
    AUTH --> CON
    AUTH --> EVL
    AUTH --> ADM
    AUTH --> PAY
    AUTH --> TD
    AUTH --> AUD
    AUTH --> LCC
    AUTH --> RSK
    GW --> CHK
    GW --> TD
    GW --> EVL
    GW --> PAY
    GW --> KYC
    GW --> ANA
    EVT --> LCC
    EVT --> CHK
    EVT --> NOT
    EVT --> DOC
    EVT --> LED
    EVT --> ANA
    EVL --> BRG
    EVL --> LCC
    EVL --> CHK
    EVL --> PAY
    EVL --> TD
    EVL --> ADM
    EVL --> KYC
    EVL --> RSK
    EVL --> ANA
    BRG --> LCC
    BRG --> PAY
    BRG --> TD
    BRG --> RSK
    AUD --> EVL
    AUD --> LCC
    AUD --> PAY
    AUD --> KYC
    AUD --> RSK
    AUD --> ANA
    LCC --> CHK
    LCC --> PAY
    LCC --> TD
    LCC --> KYC
    LCC --> NOT
    LCC --> DOC
    LCC --> BRG2[BRG enforcement]
    LCC --> ADM
    CHK --> NOT
    CHK --> DOC
    CHK --> LED
    CHK --> BRG2
    CHK --> LCC
    KYC --> PAY
    KYC --> LCC
    KYC --> NOT
    PAY --> NOT
    PAY --> DOC
    PAY --> LED
    PAY --> BRG2
    PAY --> RSK
    RSK --> PAY
    NOT --> TD
    NOT --> DOC
    DOC --> TD
    DOC --> CHK
    LED --> PAY
    ANA --> TD
    ANA --> ADM
    CON --> ADM
    CON --> TEN
    CON --> AUTH
```

Note: edges are the union of `Depends On` references between modules in the sheet. Intra-module dependencies (e.g. AUTH-07 depending on nothing) are omitted. Arrow = "depends on".

**The sheet's graph is cyclic** (LCC ⇄ BRG, EVL ⇄ LCC via CHK, PAY → LCC, LED ⇄ CHK/PAY, …) — a dependency graph with cycles has no linear topological order, so this picture must not be read as a strict total order. The **binding build order is the phase plan**, not the raw edge list: Phase-0 prefix `OPS → TEN → AUTH → GW → EVT` (LED/AUD/CON fold into 0.8; frozen V0 contracts land at 0.10) and Phase-1 `LCC → BRG → EVL → RSK → KYC → CHK → PAY` (docs/01 §8, docs/99). Within Phase 1, `LCC → BRG → EVL` is the **deliberate cycle-break**: the V0 contracts frozen at 0.10 (envelope, payload schemas, error taxonomy — `contracts/`) let both sides of every cross pair build and integrate in parallel without waiting on the other.

## Confirmed sequencing (resolved 2026-09-20, gap-closure pass)
The earlier candidate path "OPS → TEN → AUTH → GW → EVT → **EVL/BRG → LCC** → CHK → PAY → LED" was a misreading of the edge direction (the sheet's edges say LCC depends on BRG/EVL, not the reverse). Confirmed against docs/01 §8 and docs/99: **OPS → TEN → AUTH → GW → EVT, then LCC → BRG → EVL → RSK → KYC → CHK → PAY** — the order above, not one that puts EVL/BRG before LCC.

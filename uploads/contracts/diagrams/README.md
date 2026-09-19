# Diagrams

Status: DRAFT
Owner: TBD
Last updated: TODO

Derived from the V1 Execution Sheet of `Alpha One PRD.xlsx`.

Each diagram has a Mermaid source in a sibling `.md` file. The zero-byte `.png` files are placeholders: **render the Mermaid to PNG** (and replace the placeholder) before contract freeze. Rendering tool: TODO — needs owner decision (mermaid-cli suggested).

| Diagram | Mermaid source | PNG placeholder | Cites |
|---|---|---|---|
| Service lanes | `lanes.md` | `lanes.png` | OPS-01 (api, workers, relay, bot, frontends) |
| Purchase flow | `purchase-flow.md` | `purchase-flow.png` | CHK-06, CHK-07, CHK-08, CHK-09, LCC-05 |
| Payout flow | `payout-flow.md` | `payout-flow.png` | PAY-01, PAY-03, PAY-08, PAY-09, PAY-12, LED-07, LED-08 |
| Account state machine | `account-state.md` | `account-state.png` | LCC-02 |
| KYC state machine | `kyc-state.md` | `kyc-state.png` | KYC-06 |
| Payout state machine | `payout-state.md` | `payout-state.png` | PAY-13 |
| Event bus | `event-bus.md` | `event-bus.png` | EVT-01, EVT-02, EVT-05, EVT-08 |
| Build order | `build-order.md` | `build-order.png` | Depends On column, V1 Execution Sheet |

## Open contract questions
- TODO — needs owner decision: PNG rendering tool and whether PNGs stay in-repo or are generated in CI.

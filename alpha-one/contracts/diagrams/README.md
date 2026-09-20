# Diagrams

Status: DRAFT
Owner: TBD
Last updated: 2026-09-20 (rendering tool pinned, PNG-vs-CI decided, all "needs owner decision" markers resolved — see the note below each diagram source)

Derived from the V1 Execution Sheet of `Alpha One PRD.xlsx`.

Each diagram has a Mermaid source in a sibling `.md` file. **Rendering tool
(pinned 2026-09-20):** `@mermaid-js/mermaid-cli` (mermaid-cli v11, already a
declared dependency of `prop-firm-bridge/` — `npm i && npx mmdc -i <file>.md
-o <file>.png` from that directory; its `puppeteer.json` supplies the
`--no-sandbox` flags this environment needs). **PNG strategy (pinned
2026-09-20): the rendered PNGs are committed in-repo** — the contract-freeze
review happens in the docs, not in CI, and mermaid-cli needs a Chromium
download that not every build environment can guarantee. When a Mermaid
source changes, re-render its PNG in the same change (a reviewer noticing a
stale PNG is a merge blocker, not a CI failure). CI wiring is a V2
candidate, not a V1 requirement.

| Diagram | Mermaid source | PNG (rendered, committed) | Cites |
|---|---|---|---|
| Service lanes | `lanes.md` | `lanes.png` | OPS-01 (api, workers, relay, bot, frontends) |
| Purchase flow | `purchase-flow.md` | `purchase-flow.png` | CHK-06, CHK-07, CHK-08, CHK-09, LCC-05 |
| Payout flow | `payout-flow.md` | `payout-flow.png` | PAY-01, PAY-03, PAY-08, PAY-09, PAY-12, LED-07, LED-08 |
| Account state machine | `account-state.md` | `account-state.png` | LCC-02 |
| KYC state machine | `kyc-state.md` | `kyc-state.png` | KYC-06 |
| Payout state machine | `payout-state.md` | `payout-state.png` | PAY-13 |
| Event bus | `event-bus.md` | `event-bus.png` | EVT-01, EVT-02, EVT-05, EVT-08 |
| Build order | `build-order.md` | `build-order.png` | Depends On column, V1 Execution Sheet |

## Rendering & staleness (resolved 2026-09-20, gap-closure pass)
- Tool: mermaid-cli v11 via `prop-firm-bridge/node_modules/.bin/mmdc` (Chromium via puppeteer; `puppeteer.json` args `--no-sandbox --disable-setuid-sandbox --disable-dev-shm-usage`).
- All 8 PNGs above are currently rendered from the committed sources (last render 2026-09-20). Diagrams whose sources changed in the 2026-09-20 gap-closure pass: `build-order.md`, `event-bus.md`, `purchase-flow.md`, `payout-flow.md` (plus the `PayoutPaid` → `payout.settled` rename touching `event-bus.md`/`payout-flow.md`) — re-render these four before contract freeze.
- The Mermaid sources are the source of truth; a PNG that contradicts its source is treated as a contract defect.

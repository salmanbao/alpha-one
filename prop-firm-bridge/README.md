# Prop Firm Bridge — A–Z Architecture & Implementation Research

Enterprise-grade research document + architecture for building a **Rules & Trading Platform Bridge** for a prop firm-as-a-service platform (target languages: TypeScript, JavaScript, Go, Rust).

## Deliverables

| Path | What it is |
|---|---|
| `site/report.html` | **Main deliverable** — self-contained interactive report (dark theme, all 15 diagrams inline as SVG, syntax-highlighted code). Open in any browser; no network needed. |
| `docs/prop-firm-trading-bridge.md` | The full document as Markdown with inline Mermaid diagram sources — drop it into GitHub/GitLab/VS Code/Obsidian/mermaid.live and the diagrams render there too. |
| `diagrams/*.mmd` | 15 Mermaid diagram sources (edit + re-render any of them). |
| `rendered/*.svg` | Rendered SVGs of all 15 diagrams (standalone use in slides/decks). |
| `docs/src/*.md` | Section sources the document is assembled from. |
| `scripts/build.js` | Rebuild script: `node scripts/build.js` → regenerates both the MD and the HTML. |

## The 15 diagrams

1. System context (C4-level) · 2. Container architecture · 3. Trader lifecycle state machine
4. Event/data flow backbone · 5. Auth & WS handshake (sequence) · 6. Order placement critical path (sequence)
7. Position close → verdict → halt (sequence) · 8. Reconnect & snapshot resync (sequence)
9. Daily rollover pipeline · 10. Funding provisioning saga (sequence) · 11. Payout flow (sequence)
12. Deployment topology (k8s) · 13. Rules engine internals · 14. Tenant onboarding flow
15. Fraud detection pipeline

## Re-rendering a diagram

```bash
npx mmdc -i diagrams/06-order-placement.mmd -o rendered/06-order-placement.svg -b white -p puppeteer.json
node scripts/build.js   # reassemble MD + HTML
```

## Document map

- §1 Executive summary & critical-path SLOs · §2 Domain (prop-firm lifecycle, account topology, rule taxonomy)
- §3 Platform integration targets (MT4/5, cTrader, DXtrade, TradingView; terminal-side vs server-side execution)
- §4 Architecture (four planes, event backbone, multi-tenancy, deployment, onboarding)
- §5 Bridge protocol (transports, session machine, canonical schema, the Guard, pairing, clocks, outage policy)
- §6 Rules engine (rule packs, exact drawdown semantics, three enforcement layers, rollover, funded mode, payout math)
- §7 Consistency (two-truths, event sourcing, idempotency, reconciliation loops, failure matrix, sagas, availability)
- §8 Security (STRIDE table, crypto design, authN/Z, network, fraud graph, hash-chained audit, compliance)
- §9 Scalability (load model, latency budget, data growth, spike patterns, load-test targets)
- §10 Language assignment (Rust/Go/TS/JS matrix, monorepo layout, code sketches in all four languages)
- §11 Technology selection (event backbone, SoR, hot state, TSDB, secrets, observability, infra)
- §12 Operations (SLOs, alerting philosophy, six runbooks, cost ops)
- §13 Testing (property tests, adapter contracts, the sim harness as moat, chaos, dispute drills)
- §14 Roadmap (5 phases, ~40 weeks), team, cost, 12-risk register, A–Z one-breath summary
- §15 Glossary, protocol/architecture/domain references, ADR seeds

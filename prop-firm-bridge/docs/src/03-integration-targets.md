## 3. Trading Platform Integration Targets

The bridge is a **fleet of protocol adapters** behind one canonical event schema. Each adapter owns: wire format, auth model, session semantics, state collection (for snapshots), and known broker-side quirks. New platforms are added by writing a new adapter against the same internal contract — this is the entire extensibility strategy.

### 3.1 Platform capability matrix

| Platform | Order execution location | Bridge channel | Auth model | Snapshot/state collection | Key constraints |
|---|---|---|---|---|---|
| **MetaTrader 4** | Client terminal → broker | EA (MQL4) over HTTPS (WebRequest) or WebSocket-capable proxy | Domain whitelist `.pfx` signature; account-bound pairing key | `PositionsTotal()`, `HistorySelect()`, `AccountInfoDouble` | 32-bit terminal; WebRequest needs per-domain signing (friction for updates); no native custom TLS headers; effectively legacy — support for existing tenants, no new design investment |
| **MetaTrader 5** | Client terminal → broker | EA (MQL5) over **HTTPS REST + optional WebSocket via third-party libs**; most shops use REST polling with short-interval push | WebRequest to any allowed domain (terminal setting "Allow WebRequest"); account-bound pairing key, HMAC per message | `PositionsGet`, `HistoryDealGetTicket`, `AccountInfo` | Terminal is the only path to the broker; **one MT5 account per terminal per broker server** (affects multi-account traders); terminal must stay running (VPS recommended); `OnTradeTransaction`/`OnTester` give event hooks |
| **cTrader** | Client terminal → broker (cBot), **or** broker Open API v2 server-side | cBot (C#) over HTTPS/WS *or* server-side Open API if broker grants | cTrader account tokens; pairing key for bridge | Open API v2 `GetPositionsAsync`, `GetExecutionReportAsync`, `GetHistoryAsync` | cTrader's Open API is the cleanest of the four: full server-side access where broker allows → enables **server-side execution for evaluations** (no trader terminal needed) — a strong differentiator; otherwise cBot pattern mirrors MT |
| **DXtrade** | Client or via broker API | REST + WebSocket API (first-class, broker-supported) | API keys (OAuth-style) per account | REST `/positions`, `/trades`, `/account` | API is designed for firms: webhooks for trade events, position limits, per-account permissions → best fit for **server-side evaluation accounts** |
| **TradingView** | Nowhere (no execution API for retail strategies) | Strategy **webhooks** (outbound HTTPS) | Webhook token (static + HMAC) | None — signals only | One-way, ~0.5–2 s webhook latency; must define: TV is a *signal source*, bridge relays the order to the *primary execution platform* (MT/cTrader) or broker API; rate-limit and origin-validate aggressively |
| **Tradovate / others** | Varies | ODBC/WebSocket | Per broker | Per broker | Treat as adapter projects; same canonical contract |

### 3.2 The two deployment topologies (and why you build both)

**Topology A — Terminal-side thin client (MT4/MT5, cTrader cBot).**
The EA/cBot is the bridge's *agent* on the trader's machine. It:
- subscribes to the bridge's control channel (poll or WS),
- fast-fails locally against a **cached rule pack** (halt flag, weekend rule, spread cap) *before* asking the bridge,
- sends `order_intent` for authorization, executes at the broker, reports the fill with broker-attested fields,
- spools all telemetry in a local ring buffer (≥ 72 h) so a network outage never loses evidence,
- heartbeats and re-authenticates.

This topology is the default for evaluation trading because traders keep their normal workflow and the broker relationship stays purely between trader-terminal and broker.

**Topology B — Server-side execution (cTrader Open API, DXtrade API, MT5 via broker-authorized paths).**
The *platform* holds the credentials (in Vault) and executes directly. The bridge then has **both** the execution path and the telemetry path, which enables:
- **instant halts** (you stop orders at your edge, not the trader's machine),
- **no-PA trading** (evaluations without trader-installed software — reduces tampering surface to near zero),
- **faster rule feedback** (fill → verdict in the same control loop).
This is the strategic direction: new platforms default to B; MT remains A (MT has no open broker API for this purpose).

The adapter contract is identical for both: *intake of canonical events, emission of control commands*. Topology B simply adds an `Executor` port the adapter implements.

### 3.3 MT4/MT5 reality check (read before designing the EA)

- **The terminal must be running and logged in.** The bridge must model "trader offline" as a first-class, long-lived state (weekends, vacations, VPS failure) with explicit policy: grace windows, retroactive rule application from spooled data, and invalidation after tenant-configurable maximum silence.
- **MT4 WebRequest** requires the trader to install a per-domain signature file and allow WebRequest in terminal options; MT5 requires only the allow-list. Both make onboarding friction a *conversion* problem: pairing flow must be 3 clicks and support QR.
- **Terminal restarts lose in-memory state but not spooled evidence** — the EA's on-disk ring buffer is non-negotiable, and the snapshot flow (diagram 08) rebuilds session state from it.
- **Multiple evaluation attempts** = multiple accounts = multiple terminals/VPS instances. Capacity and fraud models must assume N accounts per human (device/IP fingerprinting, Section 8.5).
- **Time**: use **broker timestamps** (`time` of deals, `OrderSelectTime`) as the rule-authoritative clock; the trader's machine clock is untrusted. Bridge NTP (chrony) is authoritative for *bridge-side* ordering; deal times are authoritative for *rule* evaluation.

### 3.4 Adapter internal contract (code level)

```
interface PlatformAdapter {
  // intake: raw platform message -> canonical event (+ diagnostics)
  decode(raw: WireMessage): Result<CanonicalEvent | ControlEvent, DecodeError>
  // control: canonical command -> platform wire message
  encode(cmd: ControlCommand): WireMessage
  // snapshot: instruct client to collect full state
  collectSnapshot(session: Session): AsyncIterable<SnapshotChunk>
  // capabilities
  caps: { serverSideExec: bool, webhooks: bool, maxMsgSize: int, … }
}
```

The normalizer maps wire events to the **canonical schema** (Section 5.3). Diagnostics (decode failures, schema version mismatches) are emitted as their own event class so fleet-wide client regressions are visible in minutes, not weeks.

---

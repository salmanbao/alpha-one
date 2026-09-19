## 10. Language Assignment: Rust, Go, TypeScript, JavaScript

### 10.1 The assignment matrix

| Component | Language | Why (and when NOT to) |
|---|---|---|
| **Rules engine** (evaluator, state, replay) | **Rust** | The financial-correctness core: deterministic, zero-alloc hot path, decimal math, no GC pauses, single-thread-per-account model maps to ownership. You *can* do this in Go — acceptable at ≤ ~2k accounts/region — but Rust's invariants (no data races by construction, no panic paths in `no_std`-style core) and speed headroom make it the right tool where a verdict = money |
| **Bridge hot path** (guard: HMAC, canonicalize, seq, idempotency) | **Rust** (crate, linked into Go nodes via FFI or gRPC sidecar) | < 1 µs per message, 10k+ msg/s per node; GC-free. Go alone is fine at v1 scale; extract to Rust when profiling says so — but the *interface* (canonical bytes in → guard verdict out) is designed from day 1 so the swap is mechanical |
| **Bridge nodes** (WS/REST connections, sessions, adapters, Kafka I/O) | **Go** | Mature WS/HTTP stack, trivially huge connection counts, fast to hire, great k8s/otel ecosystem, protobuf/grpc first-class. Rust's tokio is equally good — pick Rust here too if the team is Rust-heavy; the protocol design is language-agnostic, the matrix is a *default*, not a law |
| **Core domain services** (challenges, accounts, orders, payouts, billing, reconciliation, notifications) | **Go** | CRUD-plus-orchestration work; speed of development + operational maturity beats micro-optimization; gRPC + PG + Kafka idioms are boring in the best way |
| **Simulation broker harness** | **Rust** | Deterministic market generator + mock MT/cTrader server; property-test oracle for the whole pipeline; no allocations on the tick path |
| **Trader storefront & portal** | **TypeScript** (Next.js + React, tRPC/REST, WS for live views) | Rich client, type-safe end-to-end (shared types generated from the same `.proto`/OpenAPI), live challenge dashboards (equity curve, drawdown meters, verdicts) |
| **Tenant admin & back-office (risk desk console)** | **TypeScript** (React) | Rule-pack editor (schema-driven forms + JSON escape hatch), approval workflows, evidence-pack viewer, payout approvals, tenant config |
| **BFF / webhooks / edge jobs** | **TypeScript** (Node 20+) | Thin adapters: payment webhooks, email, tenant portal session refresh; Vercel/edge-friendly |
| **Browser-side bridges** | **JavaScript** (ES2022, no build step where possible) | Portal widgets embedded on tenant sites, TradingView webhook debug console, EA-pairing QR flow, legacy tenant scripts; plain JS keeps third-party embed surface auditable |
| **MQL4/MQL5 EAs** (unavoidable extra) | **MQL** (not in your 4 — reality of MT) | Thin client only (~500 LOC): pairing, spool, intent/fill reporting, control handling, snapshot collection. All logic stays server-side; the EA is a *transport + local cache*. MQL4 variant is REST-only. The EA is the one piece of code running on untrusted hardware — keep it small, signed, hash-pinned |
| **cBot (if not server-side)** | **C#** (cTrader platform) | Same thin-client philosophy; superseded by Open API server-side where broker permits |

**Shared contract**: one `contracts/` directory of **Protobuf + JSON Schema (rule packs) + OpenAPI**, with generated clients in Go (`protoc-gen-go`), Rust (`prost`/`tonic`), and TypeScript (`ts-proto`). The contract repo is the source of truth; CI fails on breaking changes without a version bump (buf breaking). This is how four languages stay one system.

### 10.2 Monorepo layout

```
pf-platform/
├── contracts/                 # protobuf, rule-pack JSON schema, OpenAPI, buf config
├── rust/
│   ├── rules-engine/          # evaluator, state, pack compiler, replay tool
│   ├── bridge-guard/          # per-message pipeline (HMAC/seq/dedup) + cdylib + gRPC
│   ├── sim-harness/           # deterministic broker simulator + scenario DSL
│   └── crates/{decimal-math, canonicalize, eventlog}/
├── go/
│   ├── bridge/                # nodes: WS/REST, adapters (mt4, mt5, ctrader, dxtrade, tv)
│   ├── services/{identity,challenge,account,order,payout,billing,notification,recon}/
│   ├── gateway/               # API gateway, webhook receivers
│   └── ops/{replay-tool, audit-gen, capacity}/
├── web/
│   ├── storefront/            # Next.js (tenant-branded)
│   ├── portal/                # trader portal (TS)
│   ├── backoffice/            # tenant admin + risk console (TS)
│   └── widgets/               # plain-JS embeddables
├── ea/
│   ├── mt5-bridge/            # MQL5 thin client (signed builds)
│   ├── mt4-bridge/            # MQL4 (REST)
│   └── cbot-bridge/           # C# thin client
├── infra/                     # Terraform, k8s manifests, ArgoCD, helm
├── pipelines/                 # CI/CD, contract tests, load profiles
└── docs/                      # this document, runbooks, ADRs
```

### 10.3 Code sketches (the load-bearing parts)

**Rust — rules engine core (pure, replayable, no I/O in `apply`):**

```rust
// rust/rules-engine/src/eval.rs
pub struct Evaluator { pack: CompiledPack, metrics: Metrics }

/// Pure: (state, event) -> (state, verdicts). No I/O, no clocks, no randomness.
pub fn apply(state: &mut AccountState, ev: &CanonicalEvent, pack: &CompiledPack)
            -> ApplyResult {
    match ev {
        CanonicalEvent::OrderFilled(f) => {
            state.upsert_position(f);
            let equity = state.broker_equity_at(f.broker_ts);
            let day_pct = pack.daily_loss_pct; // Decimal, from pack
            let floor = state.day.start_equity * (DECIMAL_1 - day_pct / DECIMAL_100);
            let mut verdicts = vec![];
            if pack.daily_breach_mode == BreachMode::Intraday && equity < floor {
                verdicts.push(verdict(state, ev, RuleId::DailyMaxLoss,
                    RuleInput { equity, floor, start: state.day.start_equity }));
            }
            if equity < pack.overall_floor(state) {   // static or trailing (HWM)
                verdicts.push(verdict(state, ev, RuleId::MaxOverallLoss,
                    RuleInput { equity, hwm: state.high_water_mark, start: state.start_balance }));
            }
            if pack.target_met(state) && state.day_counter >= pack.min_trading_days {
                verdicts.push(verdict(state, ev, RuleId::ProfitTarget, RuleInput::target(state)));
            }
            ApplyResult { verdicts, state_changed: true }
        }
        CanonicalEvent::TradeClosed(c) => {
            let recomputed = pnl_from_entry(state.position_for(c.deal_id)?, c);
            if recomputed != c.pnl && (recomputed - c.pnl).abs() > pack.pnl_tolerance {
                return ApplyResult { verdicts: vec![], integrity_alert: Some(c.deal_id) };
            }
            state.apply_close(c); state.maybe_trail_hwm(c); // per pack config
            ApplyResult { verdicts: check_post_close(state, ev, pack), state_changed: true }
        }
        CanonicalEvent::Rollover(r) => state.finalize_day(r.date, pack),
        _ => ApplyResult::unchanged(),
    }
}
// Consumer wrapper (async, per account partition): load state (Redis/PG) ->
// for ev in batch { apply -> persist state (seq_applied) -> outbox publish verdicts }
// Replay tool re-runs the SAME apply over the event log to any point in time.
```

**Go — bridge node: WS session with guard, spool-tolerant resync:**

```go
// go/bridge/session.go
type Session struct {
    Acct    AccountID
    Key     []byte          // session key (256-bit), from keystore, TTL 24h
    LastSeq uint64          // last ACKed client seq (Redis-backed)
    PackVer string
    node    *Node
}

func (s *Session) handleEnvelope(raw []byte, send func(Wire)) {
    env, err := guard.Verify(raw, s.Key, s.LastSeq, s.nonceCache, s.clock) // Rust FFI: <1µs
    if err != nil {
        switch err {
        case guard.ErrReplay, guard.ErrSig:  s.reject(env403, err); s.escalateTrust()
        case guard.ErrGap:                   s.beginResync(send)    // snapshot flow, §5.2
        default:                             s.reject(env400, err)
        }
        return
    }
    s.LastSeq = env.Seq
    canon, diag := s.adapter.Decode(env)                    // per-platform adapter
    s.metrics.Inc(env.Type)
    if ack := s.acks.maybe(env.Seq, 250*time.Millisecond); ack {
        send(Wire{Kind: "ack", Seq: ack})
    }
    s.pub.PublishAsync(canon, s.Acct)                       // Kafka, partition=account
    if env.Kind == KindCtlAck { s.node.deliverControl(s.Acct, env) }
    s.audit.Append(env)                                     // hash-chained, async
}

func (n *Node) beginResync(s *Session, send func(Wire)) {
    send(ctlSnapshotRequest)                                // §08 diagram
    // terminal sends snapshot chunks (positions, deals since last ack);
    // checksum-verified, merged, then unacked control commands replayed.
}
```

**TypeScript — trader portal live view (WS fan-in from core, not from bridge):**

```ts
// web/portal/live.ts — the portal NEVER connects to the bridge; it consumes
// rule.verdicts + account_state from the core push service (account-scoped WS)
export function useAccountLive(account: AccountId) {
  const [state, setState] = useState<AccountView | null>(null)
  useEffect(() => {
    const ws = connect(`${import.meta.env.VITE_PUSH}/v1/live/${account}`,
      { withCredentials: true, onReconnect: backoff(1, 30) })
    ws.on('account_state', s => setState(prev => mergeView(prev, s)))   // idempotent merge
    ws.on('verdict', v => { if (v.status === 'BREACH') toast.violation(v) })
    return () => ws.close()
  }, [account])
  return state
}
```

**JavaScript (plain, no build) — tenant-embeddable status widget:**

```js
// web/widgets/status.js — <script src> embed on tenant sites; signed, versioned, pinned
(function () {
  const root = document.currentScript.dataset.pfWidget            // "acme:widget:3"
  fetch('/v1/public/widgets/' + root + '/state', { credentials: 'omit' })
    .then(r => r.json())
    .then(s => {
      const el = document.getElementById(root); if (!el) return
      el.textContent = s.platform_status === 'operational' ? '● Markets feed OK'
                                                           : '○ Reconnecting…';
      el.title = 'Updated ' + new Date(s.ts).toLocaleTimeString()
    })
  setInterval(tick, 30000)   // poll fallback; WS where the host page allows
})();
```

**MQL5 — thin EA (the untrusted-device contract, kept ~500 LOC on purpose):**

```mql5
//+------------------------------------------------------------------+
//| mt5-bridge: pairing, spool, intent/fill, control, snapshot       |
//+------------------------------------------------------------------+
void OnTradeTransaction(const MqlTradeTransaction& t, const MqlTradeRequest& rq,
                        const MqlTradeResult& rs)
{
   if(t.type == TRADE_TRANSACTION_DEAL_ADD)
   {
      MqlDeal d; HistoryDealSelect(t.deal);
      SpoolEvent(SpooledEvent{ .kind="order_filled",
         .deal_id=(string)t.deal, .order_id=(string)d.order(), .symbol=d.symbol(),
         .side=d.entry()==DEAL_ENTRY_IN? "buy":"sell", .volume=d.volume(),
         .fill_px=d.price(), .commission=-d.commission(), .swap=d.swap(),
         .broker_ts=(long)d.time() });               // broker time, never TimeCurrent()
   }
}

bool PreFlight(const string& symbol, const double& vol)
{
   if(CachedPack.halted || WeekendRule.closed()) return false;          // L0
   if(BidAskSpread(symbol) > CachedPack.spread_max(symbol)) return false;
   if(!Bridge.OrderIntent(symbol, vol, &allow_tok, &ttl_ms)) return false; // L1
   return (GetTickCount() - sent_tick) * 1000 < ttl_ms;                 // token fresh
}

void OnTimer()   // 1 s: heartbeat, spool drain (batch<=50), control poll fallback
```

### 10.4 Team-shape implication

A 10–14 person build team: 3–4 Go (bridge + services), 2–3 Rust (engine + guard + sim harness), 3–4 TypeScript (portal, back-office, storefront), 1 MQL/cBot (platform integrations — hire from the FX dev community; this skill is rare and critical), 1 SRE/security, 1 PM/domain. The contract repo and sim harness are what let these streams move independently — invest in them in week 1, not week 12.

---

# pf-platform — working scaffold

Executable companion to the design report in [`../prop-firm-bridge/`](../prop-firm-bridge)
(prop-firm challenge rules engine + Trading Platform Bridge). This scaffold
implements the contract surface and both runtime planes, and — unlike the
report — is **verified**: every check below runs and is green.

```
pf-platform/
├── contracts/                  # the single source of truth for the wire
│   ├── proto/bridge/v1/        #   bridge envelope / events / control (protobuf)
│   ├── rulepack/v1/            #   rule-pack JSON Schema (draft 2020-12)
│   └── samples/                #   two validated rule packs (100k challenge & funded)
├── rust/
│   ├── crates/rules-engine/    # deterministic rules engine (pure, tz-free)
│   │   └── tests/              #   7 golden scenarios + 7 proptest properties
│   └── crates/replay-tool/     # CLI: replay a JSONL event stream through the engine
├── go/bridge/                  # Trading Platform Bridge (WS + REST, in-process guard)
├── examples/sample-events.jsonl
├── scripts/check-contracts.js  # buf lint + schema validation
└── Makefile                    # make check = the whole verification bar
```

## Verification bar

```
make check
```

runs, in order:

| step       | what it proves                                                                 |
|------------|--------------------------------------------------------------------------------|
| `contracts`| proto passes `buf lint`; both sample packs validate against the rule-pack schema |
| `rust`     | 8 golden tests (hand-computed ledger/verdict outcomes) + 9 property tests (determinism, replay-prefix, monotonic breach, once-per-account verdicts, tight-vs-loose, delivery-order robustness, decimal exactness, builder determinism, money conservation) |
| `go`       | bridge builds, vets, and passes the e2e protocol test: pair → WS hello → `auth_ok` → signed `ev` → `ack` → replay reject → bad-sig reject → seq-gap → `ctl(snapshot_request)` → checksummed snapshot → `resync_complete` → REST event path, plus cross-tenant binding rejection |
| `replay`   | the bundled 12-event stream reproduces the worked example: 1 `DailyMaxLoss` breach on 2026-01-06 (equity 94250 < floor 95520.00), 1 `Rollover` info, 1 `PNL_MISMATCH` (reported 5000 vs recomputed −5250), 1 `BALANCE_DRIFT` (94960 vs 94245), final balance **94245** |

## What is real, what is deliberately stubbed

**Real (logic-bearing):**

- Rust engine: canonical-event state machine — fills/closes (deal-scoped,
  idempotent by `deal_id`), out-of-order close buffering (`CLOSE_DEFERRED`,
  drained at the matching fill at the close's own broker_ts), platform PnL
  always recomputed in exact `Decimal` with `PNL_MISMATCH` alerts, balance
  law, trailing-HWM overall loss, intraday vs eod daily breach, min-trading-day
  gated target, news windows, rollover day-boundary handling, malformed
  px/amount → `MALFORMED` alert with no state change.
- Go bridge: tenant pairing (one-time 32-byte hex key), WS hello signed with
  the pairing key → fresh session key, per-event HMAC-SHA256 over a fixed
  canonical array form, verify order (binding → sig → 90 s skew → nonce TTL →
  strict seq), nonce/TTL replay protection, seq-gap → snapshot resync protocol
  with SHA-256 checksum over canonical sorted-key JSON, control-plane commands
  (halt/restore/…) pushed over the same channel and replayed after resync,
  outbox publisher (JSONL file + in-memory ring) and a kafka-go publisher
  with partition key = account.
- Contracts: the proto envelope/event/control surface and the rule-pack schema
  that both languages' hand-written types mirror.

**Deliberately scaffold-level (documented in-code):**

- No protobuf *code generation* wired in — both languages use hand-written
  mirror types; `buf.gen.yaml`/`buf.gen.rust.yaml` are ready for the v2 step.
- No live broker/Kafka dependency in tests: the bridge test runs in-process
  over `httptest` + WebSocket; Kafka is behind the `Publisher` interface.
- MQL/MT5 EA side is out of scope here (see the report, §8).

## Running the pieces

```sh
# Rust engine tests
cd rust && cargo test --workspace

# Replay any JSONL stream
cd rust && cargo run -p replay-tool -- \
  --pack ../contracts/samples/challenge_100k.json \
  --events ../examples/sample-events.jsonl

# Go bridge — config via environment (see go/bridge/main.go header)
cd go
# JSONL outbox mode (default):
PF_LISTEN=127.0.0.1:8443 PF_OUTBOX=/tmp/outbox.jsonl go run ./bridge
# ... with the Kafka backbone instead (outbox still stages durably):
PF_LISTEN=127.0.0.1:8443 PF_KAFKA_BROKERS=127.0.0.1:9092 PF_KAFKA_TOPIC=pf.canonical.v1 go run ./bridge

# Contract checks
node scripts/check-contracts.js
```

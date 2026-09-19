## 5. The Bridge: Protocol, Transport, and State Machine

### 5.1 Transport choices

| Concern | Decision | Rationale |
|---|---|---|
| Primary transport | **WebSocket over TLS 1.3** | Bidirectional (telemetry up, control down) on one long-lived connection; MT5 EAs lack native WS, so MT clients use **HTTPS JSON POST** with the same envelope and short-interval push (500 ms–2 s adaptive) — the protocol is *transport-agnostic* by design |
| Fallback / bulk | HTTPS REST (`POST /bridge/v1/events`, batched up to 50 events) | Terminal spool delivery after long outages; snapshot chunks |
| Message encoding | **JSON (v1) → protobuf over WS (v2)** | JSON for trivially debuggable v1 and MT's native `WebRequest` string world; protobuf later for bandwidth at scale — schema in `.proto` from day 1, JSON is just a codec |
| Message size | ≤ 64 KB per message; snapshots chunked at 128 positions or 32 KB | Terminal memory + gateway limits |
| Compression | `permessage-deflate` (WS) / gzip (REST) | Telemetry is highly compressible |
| MT4 quirk | REST-only (WebRequest), domain `.pfx` onboarding | MT4 constraint (Section 3.3) |

The **connection is a convenience; the protocol is a sequence-ordered, idempotent log.** Any transport — WS, REST polling, or a future MQTT bridge — is acceptable as long as the guard (5.4) verifies the same invariants. This is what makes "trader's laptop over hotel wifi" a supported deployment.

### 5.2 Session lifecycle

```
IDLE ──hello──▶ AUTHENTICATING ──auth_ok──▶ ACTIVE ──gap/timeout──▶ RESYNC ──snapshot ok──▶ ACTIVE
                    │ (bad key / replay / tenant mismatch)               │ (checksum fail, N times)
                    ▼                                                    ▼
                 REJECTED (403 + reason code, pair rotation suggested)  SUSPENDED (alert + reconciliation + manual)
ACTIVE ──24h key expiry──▶ REAUTH (inline, connection preserved)
ACTIVE ──heartbeat miss x3 (30s)──▶ DEGRADED (trading allowed, flagged; control via next connect)
```

Sessions are **stored in Redis**, not on the node: `{account_id → {node_id, seq, sess_key_ref, rules_pack_ver, state, since}}`. This gives: (a) node failure → any node resumes; (b) LB hash changes are harmless; (c) the session registry *is* the "who is connected" map for ops dashboards and for the `events_since` API used during resync.

### 5.3 Canonical event schema (v1 core)

Defined in Protobuf; JSON rendering for wire v1. Every message is wrapped in an **envelope**:

```json
{
  "v": 1,
  "id": "0193f7a2-…",            // ULID, server or client origin
  "kind": "ev",                   // ev | ctl | ack | snap | hb
  "type": "order_filled",
  "tenant": "acme-firm",
  "account": "778123",
  "seq": 482,                     // client-origin: monotonic per account-session
  "ts_client": 1758259200123,     // client clock (untrusted, recorded for skew analysis)
  "ts_server": 1758259200091,     // bridge clock (NTP, authoritative for ordering)
  "nonce": "d41c…",               // replay guard (per session, 60 s window)
  "sig": "base64(hmac-sha256(canonical_bytes, sess_key))",
  "payload": { }
}
```

Canonical event types (bridge → core):

| Type | Key payload fields | Source of truth notes |
|---|---|---|
| `account_state` | balance, equity, margin, free_margin, leverage, currency | broker-reported; platform ledger cross-check |
| `order_filled` | order_id, deal_id, symbol, side, type, volume, fill_px, stop/limit, commission, swap, **broker_ts**, slippage | `deal_id` is the **global idempotency key** |
| `order_modified` | order_id, new_sl, new_tp, deal_id | same idempotency discipline |
| `position_closed` | deal_id, entry_px, exit_px, volume, pnl, commission, swap, **broker_ts** | PnL **recomputed** by bridge from stored entry — discrepancy > tolerance → `data_integrity_alert` |
| `quote` (optional) | symbol, bid, ask, ts | only if tenant enables quote-based rules (spread caps, mark frequency) |
| `balance_adjustment` | type (commission, swap, bonus, refund, correction), amount, ref, **broker_ts** | ledger entries must reconcile 1:1 |
| `data_integrity_alert` | kind, details | emitted by bridge when its cross-checks fail |
| `snapshot_applied` | seq_range, checksum, collected_at | resync completion marker |
| `client_diagnostics` | app_ver, ea_build, decode errors, buffer occupancy | fleet health |

Control commands (core → bridge → terminal), all with `ttl`, `seq`, and `reason`:

`trading_halt`, `resume_trading`, `close_all`, `close_symbol`, `set_param` (rules pack version bump → client refetches pack), `snapshot_request`, `force_rescan_history`, `pair_rotate` (new signing key), `account_notice` (display to trader).

Every control command is also written to `bridge.events.control` and to PG — **a halt must survive terminal disconnects**: on reconnect, the bridge replays all unacknowledged control commands for the account.

### 5.4 The Guard: security invariants on every message

Executed in Rust, < 1 µs budget per check (amortized):

1. **Signature**: HMAC-SHA256 over canonical bytes (sorted keys, no whitespace, UTF-8) with `sess_key` (fresh per session) → protects against tampering and spoofed accounts. Pairing key (long-lived, per account) signs only `hello`/`auth`.
2. **Sequence continuity**: `seq` must equal `last_seq + 1`. Gap → buffer up to 2 s for out-of-order delivery; then `RESYNC`. (WS is ordered per connection, so gaps mean *lost batches* on the client side → spool replay.)
3. **Replay**: `nonce` must be unseen in the last 60 s (Redis Bloom+exact, per session) and `ts_client` within 90 s of bridge NTP. Catches recorded traffic replay.
4. **Binding**: `tenant`/`account` must match the session's pairing record (a tenant-A key cannot speak for tenant-B accounts, ever).
5. **Broker-attestation cross-check** (on `order_filled`/`position_closed`): recompute PnL fields from the stored entry event; verify `broker_ts` plausibility (monotone per symbol within jitter tolerance); flag — never hard-fail — anomalies (a buggy EA should not silently fail a trader; the alert path reconciles).
6. **Idempotency**: `(account, deal_id)` insert-once into PG with a unique constraint; duplicates are acked, not processed.

### 5.5 The two most important exchanges (sequences)

**Authentication & session establishment** (every connection, including reconnects):

{{DIAG:05-auth-handshake}}

**The critical order path** — note that execution happens at the broker, and the bridge only authorizes and observes:

{{DIAG:06-order-placement}}

### 5.6 Pairing: getting a new terminal connected

1. Trader portal: "Connect MT5 account" → platform provisions the broker demo/real account → creates a **pairing record** `{account, tenant, pairing_key (256-bit, shown once), platforms, limits}`.
2. Trader enters pairing code into the EA (or scans QR in the portal — EA displays QR on a second tab). EA signs a `hello` probe with the pairing key.
3. Bridge verifies, returns `pairing_ack {ok, session bootstrap}`. Pairing key is **single-use for session bootstrap**; thereafter the session key signs everything. Pairing records are revocable per terminal (device fingerprint recorded: MT account number, terminal build, IP ASN, hash of EA identifier).
4. Rotation: 24 h session key rotation is inline (no disconnect); pairing keys rotate on revocation or on "device trust downgrade" (new IP-ASN pattern → require re-pair; configurable per tenant risk appetite).

### 5.6 Clock discipline

- All bridge nodes run **chrony** against at least 3 NTP sources; bridge exposes its own offset/precision via health endpoint; nodes with |offset| > 50 ms are auto-removed from load (configurable).
- **Rule evaluation uses `broker_ts`** (attested by broker, per deal) — the trader's machine clock is recorded and *analyzed* (skew histograms feed fraud features) but never trusted for decisions.
- **Rollover and expiry use server NTP** in the tenant's configured timezone — documented in tenant-facing terms so "what is a trading day" is unambiguous.

### 5.7 Outage policy (bridge down, broker fine)

The bridge is **not** on the execution path, so during a platform outage traders can keep trading at the broker — the policy question is what happens to the *rules clock*:

1. **Grace window** (tenant-config, default 15 min): trading continues; on recovery, spooled telemetry is replayed and rules are evaluated retrospectively. No trader-visible penalty.
2. **Extended outage** (> grace): tenants choose per account class: (a) pause evaluation timers and apply rules from spool once data arrives, or (b) mark accounts `outage_window` and invalidate challenges breached during the window (rare; usually (a) + audit).
3. **Terminal silent** (no connection for N hours): config-driven — challenge pauses or fails after `max_silence` (default 7 days for evaluations, 1 day for funded), with notice sent at each milestone.
4. Every outage window is stamped into the audit log (start, end, affected accounts, retroactive verdicts) — this is the document that settles disputes.

### 5.8 Control-channel fan-out

Halt/resume/close-all are **account-scoped pub/sub**: the challenge service writes the command to `bridge.events.control` (partition = account) and to Redis; the bridge node(s) serving that account (any node, via the session registry) push it to the terminal with ack; unacked commands are re-pushed on every reconnect and are visible in the ops console. A halt is *also* a PG state (`trading_halted = true` + reason), so even a fully offline terminal is treated as halted by the rules engine on the next data point — the control push is latency optimization, the DB state is truth.

---

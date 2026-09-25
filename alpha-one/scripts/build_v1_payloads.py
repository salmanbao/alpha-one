#!/usr/bin/env python3
"""Generate contracts/events/payloads/<event>.v1.json for the V1 catalog
events (contracts/events/catalog.md, 37 events) plus the two risk.* schemas
used by the extended catalog rows (docs/31).

Envelope per EVT-03 (envelope.schema.json). Every payload is DERIVED — not
invented: each spec carries `source` = the owning module doc section (and the
docs/32 DDL table) that fixes the field set, and `source` is rendered into the
schema's `description`. Money is integer minor units (docs/00 non-negotiable
#3); instrument prices and lot sizes are the only non-integer numerics (they
are ratios, not money). Field confirmation was pinned in the gap-closure pass
of 2026-09-20; the gap-closure pass also removed the earlier "INFERRED"
provenance (that wording described the open state the catalog tracked).

Usage: python3 scripts/build_v1_payloads.py
"""
import json, os

OUT = os.path.join(os.path.dirname(__file__), "..", "contracts", "events", "payloads")

ULID = {"$ref": "envelope.schema.json#/$defs/ULID"}
TS = {"$ref": "envelope.schema.json#/$defs/TimestampMs"}
MONEY = {"$ref": "envelope.schema.json#/$defs/Money"}

def obj(fields, required=None, extra=None):
    props = dict(fields)
    o = {"type": "object", "properties": props, "additionalProperties": False}
    if required:
        o["required"] = required
    if extra:
        o.update(extra)
    return o

EVENTS = {
  # --- LCC lifecycle (producer LCC-23) ---
  "AccountCreated": {
    "consumers": ["NOT-01 (template: account created)", "ANA-01"],
    "source": "docs/07 §3.2 (CREATED→ACTIVE side effect 'state + AccountCreated (LCC-23, outbox)'); field names per docs/32 `accounts` (id, program_id, phase) and `broker_accounts` (server)",
    "payload": obj({
      "account_id": ULID,
      "challenge_id": {"$ref": "envelope.schema.json#/$defs/ULID",
                       "description": "accounts.program_id (the challenge template ref; docs/12 catalog name 'challenge')"},
      "phase": {"type": "integer", "minimum": 1},
      "broker": {"type": "string", "description": "broker server name (accounts.broker_account_id → broker_accounts.server)"},
      "initial_balance": MONEY,
    }, ["account_id", "challenge_id", "phase", "broker"]),
  },
  "PhaseAdvanced": {
    "consumers": ["ANA-01"],
    "source": "docs/07 §3.2 (ACTIVE→PASS_PENDING side effect 'PhaseAdvanced / AccountPassed (LCC-23) per phase'); docs/14 §3.4: no V1 email fires from this event (phase_passed ← AccountPassed instead)",
    "payload": obj({
      "account_id": ULID, "from_phase": {"type": "integer", "minimum": 1},
      "to_phase": {"type": "integer", "minimum": 2},
    }, ["account_id", "from_phase", "to_phase"]),
  },
  "AccountPassed": {
    "consumers": ["NOT-01 (template: phase passed)", "DOC-04 (certificate)", "ANA-01"],
    "source": "docs/07 §3.2 (PASS/VERIFICATION rows emit 'AccountPassed (LCC-23)'); docs/32 `accounts` (id, identity_id→trader_id, program_id); docs/14 §3.4 (phase_passed template)",
    "payload": obj({
      "account_id": ULID,
      "trader_id": {"$ref": "envelope.schema.json#/$defs/ULID", "description": "accounts.identity_id"},
      "challenge_id": {"$ref": "envelope.schema.json#/$defs/ULID", "description": "accounts.program_id"},
      "phase": {"type": "integer", "minimum": 1}, "passed_at": TS,
    }, ["account_id", "trader_id", "challenge_id", "phase", "passed_at"]),
  },
  "AccountBreached": {
    "consumers": ["NOT-01 (template: breach)", "ANA-01"],
    "source": "docs/07 §3.2 (ACTIVE→BREACH_DETECTED side effect 'AccountBreached (LCC-23)'); verdict fields per docs/09 §3.3/§3.4 (rule, limit_cents, tolerance_cents, input_hash) and docs/32 `evaluations`",
    "payload": obj({
      "account_id": ULID, "phase": {"type": "integer", "minimum": 1},
      "rule": {"type": "string", "description": "the breached rule id (e.g. max_daily_loss, max_total_loss, time_limit — D30)"},
      "verdict_id": ULID,
      "evidence_ref": {"type": "string", "description": "pointer to the EVL evidence snapshot (evaluations.detail: metrics at decision time)"},
      "observed_cents": {"type": "integer"}, "limit_cents": {"type": "integer"},
      "tolerance_cents": {"type": "integer", "description": "EVL-53 comparison tolerance (default 1¢, docs/09 §3.3)"},
      "breached_at": TS,
    }, ["account_id", "phase", "rule", "verdict_id", "breached_at"]),
  },
  "AccountFailed": {
    "consumers": ["NOT-01 (template: phase failed)", "ANA-01"],
    "source": "docs/07 §3.2 (CLOSING→FAILED: 'FAILED recorded only after real closure (BRG-11); AccountFailed (LCC-23)'); docs/32 `accounts.failed_reason`",
    "payload": obj({
      "account_id": ULID, "phase": {"type": "integer", "minimum": 1},
      "reason": {"type": "string", "description": "accounts.failed_reason: 'breach:{rule}' | 'expired' (D30)"},
      "failed_at": TS,
    }, ["account_id", "phase", "reason", "failed_at"]),
  },
  "FundedCreated": {
    "consumers": ["DOC-04 (certificate)", "ANA-01"],
    "source": "docs/07 §3.1 (spawn edge: 'Funded creation … new FUNDED' with parent_account_id); funded terms per docs/11 §3.2 (split_ratio_bps, frequency, first payout delay); docs/14 §3.4: no V1 email (deliberate, D61 closed set)",
    "payload": obj({
      "account_id": ULID,
      "trader_id": {"$ref": "envelope.schema.json#/$defs/ULID", "description": "accounts.identity_id"},
      "parent_account_id": {"$ref": "envelope.schema.json#/$defs/ULID", "description": "the passed evaluation account (spawn edge, docs/07 §3.1)"},
      "split_ratio_bps": {"type": "integer", "minimum": 0, "maximum": 10000,
                          "description": "funded terms (docs/11 §3.2): basis points, e.g. 8000 = 80% — integer, never a float ratio"},
      "payout_frequency": {"type": "string", "description": "funded terms (docs/11 §3.1): biweekly|monthly|on_demand per tenant config"},
      "first_payout_delay_days": {"type": "integer", "minimum": 0, "description": "funded terms (docs/11 §3.1 first-withdrawal delay; the D72 sub-reason name is first_payout_delay)"},
    }, ["account_id", "trader_id", "parent_account_id"]),
  },
  "Suspended": {
    "consumers": ["PAY-04 (payout hold — status check at request/approval time, not event consumption; docs/11 §3.1/§3.7, D39)", "ANA-01"],
    "source": "docs/07 §3.2 (ACTIVE/FUNDED→SUSPENDED rows: 'BRG-14 disable trading; Suspended (LCC-23); payouts blocked (PAY-04)'); actor per docs/32 `account_state_history` (actor_kind/actor_id); docs/14 §3.4: no V1 email (deliberate, D61 closed set)",
    "payload": obj({
      "account_id": ULID, "actor_id": ULID,
      "reason": {"type": "string", "description": "staff note (account_state_history.detail)"},
      "suspended_at": TS,
    }, ["account_id", "actor_id", "reason", "suspended_at"]),
  },
  "Resumed": {
    "consumers": ["ANA-01"],
    "source": "docs/07 §3.2 (SUSPENDED→ACTIVE/FUNDED rows: 'BRG-14 enable; Resumed (LCC-23)')",
    "payload": obj({
      "account_id": ULID, "actor_id": ULID, "resumed_at": TS,
    }, ["account_id", "actor_id", "resumed_at"]),
  },
  # --- tenth pass (docs/50 D28): the Phase-1 core-loop wiring events ---
  "account.activated": {
    "consumers": ["BRG (start sync)", "EVL (start evaluation + create evaluation_state)", "NOT-01", "AUD"],
    "source": "docs/07 §3.1/§5 (CREATED→ACTIVE = the activated state; 'Credentials: issued at account.activated'); docs/32 `accounts.broker_account_id` + `broker_accounts.server`",
    "payload": obj({
      "account_id": ULID, "broker_account_id": ULID,
      "server": {"type": "string", "description": "broker server id (ADR-12 day-boundary authority)"},
      "phase": {"type": "integer", "minimum": 1},
    }, ["account_id", "broker_account_id", "server", "phase"]),
  },
  "account.day_rolled": {
    "consumers": ["EVL (daily reset)", "ANA"],
    "source": "docs/09 §3.6 (day_rolled trigger: 'trading_days++ (if any trade that day), calendar_days++; push daily_pnls'; broker-server midnight per ADR-12); skips SUSPENDED (D31)",
    "payload": obj({
      "account_id": ULID,
      "broker_date": {"type": "string", "description": "the new broker-server date (YYYY-MM-DD, per server group timezone — ADR-12)"},
      "server": {"type": "string"},
      "trading_days": {"type": "integer", "minimum": 0},
      "calendar_days": {"type": "integer", "minimum": 0},
    }, ["account_id", "broker_date", "server", "trading_days", "calendar_days"]),
  },
  "evaluation.verdict": {
    "consumers": ["LCC (transitions; dedupe on (account_id, verdict_id) per LCC-43)", "NOT-01", "DOC-04 (TD-25 breach report)", "AUD (critical on breach)", "RSK (V2 case open)"],
    "source": "docs/09 §3.4 (verdict priority + emission) + docs/32 `evaluations` (status enum, rule_id, input_hash); comparison fields per docs/09 §3.3 (limit_cents, tolerance_cents)",
    "payload": obj({
      "account_id": ULID, "verdict_id": ULID,
      "status": {"type": "string", "enum": ["breach", "target_hit", "gap_flagged"],
                 "description": "evaluations.status minus the non-emitted states (ok is not an event; target_hit_pending is recorded only — docs/09 §3.4)"},
      "rule_id": {"type": "string", "description": "required when status=breach (e.g. max_daily_loss, max_total_loss, time_limit — D30)"},
      "input_hash": {"type": "string", "description": "sha256(state||rules||tick) — the EVL-49 re-run proof"},
      "broker_time": TS,
      "limit_cents": {"type": "integer"}, "observed_cents": {"type": "integer"},
      "tolerance_cents": {"type": "integer"},
    }, ["account_id", "verdict_id", "status", "input_hash", "broker_time"]),
  },
  "evaluation.daily_reset": {
    "consumers": ["ANA (daily P&L points)", "AUD (standard)"],
    "source": "docs/09 §3.6 (daily reset) + docs/32 `evaluation_state.daily_pnls` shape {day, pnl_cents, equity_end_cents}",
    "payload": obj({
      "account_id": ULID,
      "broker_date": {"type": "string", "description": "the closed broker-server date (YYYY-MM-DD)"},
      "day_pnl_cents": {"type": "integer"},
      "equity_end_cents": {"type": "integer"},
      "trading_days": {"type": "integer", "minimum": 0},
    }, ["account_id", "broker_date", "day_pnl_cents", "equity_end_cents", "trading_days"]),
  },
  "bridge.tick": {
    "consumers": ["EVL (evaluate)", "ANA (equity points)", "web SSE fan-out (TD live) — observed record per EVL-49; no audit mirror (docs/05 §14)"],
    "source": "docs/08 §8 (canonical tick shape — D34, docs/51: positions array, margin/free_margin, leverage-as-string, deals_count, last_deal_ticket; D79, docs/63: optional trigger/source/stream_seq/equity_low_cents/equity_high_cents); money cents per docs/32 `account_snapshots`/`broker_accounts`",
    "payload": obj({
      "account_id": ULID,
      "broker_login": {"type": "string"},
      "equity_cents": {"type": "integer", "description": "broker-reported equity in cents — never recomputed, broker is truth (docs/09 §3.3)"},
      "balance_cents": {"type": "integer"},
      "margin_cents": {"type": "integer"},
      "free_margin_cents": {"type": "integer"},
      "leverage": {"type": "string", "description": "e.g. 1:500 (string — D34 fixed the invalid-number form)"},
      "positions": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                    "required": ["position_id", "symbol", "side", "lots", "open_price", "opened_at"],
                    "properties": {
                      "position_id": {"type": "string"},
                      "symbol": {"type": "string"},
                      "side": {"type": "string", "enum": ["buy", "sell"]},
                      "lots": {"type": "number", "description": "lot size (a quantity, not money)"},
                      "open_price": {"type": "number", "description": "instrument price (an asset/asset ratio, not money — the integer-minor-units rule applies to amounts, docs/00 #3)"},
                      "current_price": {"type": ["number", "null"]},
                      "sl": {"type": ["number", "null"]}, "tp": {"type": ["number", "null"]},
                      "opened_at": TS,
                      "profit_cents": {"type": "integer"}, "swap_cents": {"type": "integer"},
                      "commission_cents": {"type": "integer"}}},
                 "description": "open positions at tick time (TD live view, RSK V2)"},
      "deals_count": {"type": "integer", "minimum": 0},
      "last_deal_ticket": {"type": "integer", "description": "incremental fetch cursor (D33: never a continuity oracle)"},
      "broker_time": TS,
      "trigger": {"type": "string", "enum": ["deal", "position", "guard", "material", "heartbeat", "resync"],
                  "description": "why the streaming conflator emitted this tick (D79, docs/63 §4.4); evidence only — never a rule input. Absent on fallback-poll ticks"},
      "source": {"type": "string", "enum": ["stream", "poll", "resync"],
                 "description": "ingest path (D78): stream = MetaApi streaming, poll = credit-budgeted REST fallback, resync = post-(re)synchronization full state"},
      "stream_seq": {"type": "integer", "minimum": 0,
                     "description": "bridge-assigned per-account monotonic sequence (D33: ordering cursors are ours, not the broker's)"},
      "equity_low_cents": {"type": "integer",
                           "description": "lowest broker equity observed since the previous tick (conflation evidence, D79; invariant I-22)"},
      "equity_high_cents": {"type": "integer",
                            "description": "highest broker equity observed since the previous tick (conflation evidence, D79; invariant I-22)"},
    }, ["account_id", "broker_login", "equity_cents", "balance_cents", "margin_cents",
        "free_margin_cents", "leverage", "positions", "deals_count", "last_deal_ticket", "broker_time"]),
  },
  "bridge.sync_gap": {
    "consumers": ["ADM (manual review)", "AUD", "EVL (gap_flagged verdict)"],
    "source": "docs/08 §3.3 (D33 history-window deals-count reconciliation: history API count vs rows written)",
    "payload": obj({
      "account_id": ULID,
      "window_start": TS,
      "expected_count": {"type": "integer", "minimum": 0, "description": "deals the history API reports in the window"},
      "got_count": {"type": "integer", "minimum": 0, "description": "rows written this window"},
    }, ["account_id", "window_start", "expected_count", "got_count"]),
  },
  # --- Checkout ---
  "order.paid": {
    "consumers": ["LCC-05 (provisioning)", "LED-04 (payment capture posting)", "ANA-01"],
    "source": "docs/12 §3.2 (capture: intent captured → order paid) + docs/32 `orders` (id, amount_cents, currency, line_items{package_id}), `payment_intents` (provider, method), `provider_events` (provider_event_id); coupon per D75 (docs/62)",
    "payload": obj({
      "order_id": ULID,
      "challenge_id": {"$ref": "envelope.schema.json#/$defs/ULID",
                       "description": "orders.line_items.package_id (frozen at submit — D42); the accounts.program_id / catalog 'challenge' ref LCC-05 provisions from"},
      "amount": MONEY,
      "payment_method": {"type": "string", "description": "payment_intents.method: card|local:{kind}|crypto:{chain}|wire"},
      "provider": {"type": "string", "enum": ["match2pay", "interkasa", "nowpayments"]},
      "provider_event_id": {"type": "string", "description": "provider_events(provider, provider_event_id) — the ingress idempotency key (EVT-10)"},
      "coupon_code": {"type": ["string", "null"], "description": "reserved at session (D75); null when no coupon"},
    }, ["order_id", "challenge_id", "amount", "payment_method", "provider", "provider_event_id"]),
  },
  "checkout.session.expired": {
    "consumers": ["ANA-01 (funnel/abandonment read model)"],
    "source": "docs/12 §3.2 (TTL expiry: card 15 min / crypto 24 h; CHK-43 scheduled worker) + docs/32 `checkout_sessions` (id, price_snapshot{package_id}, reservation_expires_at); Decision 7 (2026-09-16)",
    "payload": obj({
      "session_id": ULID,
      "challenge_id": {"$ref": "envelope.schema.json#/$defs/ULID", "description": "checkout_sessions.price_snapshot.package_id"},
      "expired_at": TS,
    }, ["session_id", "challenge_id", "expired_at"]),
  },
  # --- KYC (KYC-05, V1 per Decision 5) ---
  "kyc.submitted": {
    "consumers": ["ANA-01 (no V1 email — D61: pre-decision record)"],
    "source": "docs/13 §4.1 (V1 kyc.* events) + docs/32 `kyc_sessions` (id, provider, provider_case_id, identity_id)",
    "payload": obj({
      "kyc_session_id": {"$ref": "envelope.schema.json#/$defs/ULID",
                         "description": "kyc_sessions.id (the API path parameter is still named kyc_verification_id — docs/13 §7.1; same id)"},
      "trader_id": {"$ref": "envelope.schema.json#/$defs/ULID", "description": "kyc_sessions.identity_id"},
      "provider": {"type": "string", "enum": ["veriff"]},
      "provider_reference": {"type": "string", "description": "kyc_sessions.provider_case_id"},
      "submitted_at": TS,
    }, ["kyc_session_id", "trader_id", "provider"]),
  },
  "kyc.approved": {
    "consumers": ["NOT-01 (template: kyc_approved — D61 split)", "LCC-06 (auto-upgrade on approval)", "PAY-03 (payout eligibility)", "ANA-01"],
    "source": "docs/13 §4.1 (V1 kyc.* events) + docs/32 `kyc_sessions` (id, state=approved, identity_id)",
    "payload": obj({
      "kyc_session_id": {"$ref": "envelope.schema.json#/$defs/ULID", "description": "kyc_sessions.id (API alias kyc_verification_id)"},
      "trader_id": {"$ref": "envelope.schema.json#/$defs/ULID", "description": "kyc_sessions.identity_id"},
      "provider": {"type": "string", "enum": ["veriff"]},
      "provider_reference": {"type": "string", "description": "kyc_sessions.provider_case_id"},
      "approved_at": TS,
    }, ["kyc_session_id", "trader_id", "provider", "approved_at"]),
  },
  "kyc.rejected": {
    "consumers": ["NOT-01 (template: kyc_rejected — D61 split)", "ANA-01"],
    "source": "docs/13 §4.1 (V1 kyc.* events) + docs/32 `kyc_sessions` (reject_reason_class — what the trader sees)",
    "payload": obj({
      "kyc_session_id": {"$ref": "envelope.schema.json#/$defs/ULID", "description": "kyc_sessions.id (API alias kyc_verification_id)"},
      "trader_id": {"$ref": "envelope.schema.json#/$defs/ULID", "description": "kyc_sessions.identity_id"},
      "reason": {"type": "string", "description": "kyc_sessions.reject_reason_class (detail is staff-only, never in the payload)"},
      "rejected_at": TS,
    }, ["kyc_session_id", "trader_id", "reason", "rejected_at"]),
  },
  "kyc.expired": {
    "consumers": ["ANA-01 (no V1 email — D63: expiry is silent)"],
    "source": "docs/13 §4.1 + D43 (docs/53): EXPIRED = 24 h session TTL only, fired by the session-TTL worker; APPROVED never expires in V1",
    "payload": obj({
      "kyc_session_id": {"$ref": "envelope.schema.json#/$defs/ULID", "description": "kyc_sessions.id (API alias kyc_verification_id)"},
      "trader_id": {"$ref": "envelope.schema.json#/$defs/ULID", "description": "kyc_sessions.identity_id"},
      "expired_at": TS,
    }, ["kyc_session_id", "trader_id", "expired_at"]),
  },
  "kyc.resubmission_requested": {
    "consumers": ["NOT-01 (template: kyc_needs_docs — D61 split)", "ANA-01"],
    "source": "docs/13 §4.1 (V1 kyc.* events) + docs/32 `kyc_sessions` (state=needs_resubmission, reject_reason_class)",
    "payload": obj({
      "kyc_session_id": {"$ref": "envelope.schema.json#/$defs/ULID", "description": "kyc_sessions.id (API alias kyc_verification_id)"},
      "trader_id": {"$ref": "envelope.schema.json#/$defs/ULID", "description": "kyc_sessions.identity_id"},
      "reason": {"type": "string", "description": "which documents need resubmitting (kyc_sessions.reject_reason_class)"},
      "requested_at": TS,
    }, ["kyc_session_id", "trader_id", "reason"]),
  },
  # --- Payout ---
  "payout.approved": {
    "consumers": ["LED-07 (payout obligation posting)", "NOT-01 (template: payout_approved — D61, event-consumed via the docs/14 §3.3 mapping)", "ANA-01"],
    "source": "docs/11 §4.1 (payout.approved) + docs/32 `payout_requests` (id, account_id, approved amount, approved_by/at per the approval path §3.5)",
    "payload": obj({
      "payout_id": ULID, "account_id": ULID,
      "amount": MONEY,
      "approved_by": ULID, "approved_at": TS,
    }, ["payout_id", "account_id", "amount", "approved_by", "approved_at"]),
  },
  "payout.rejected": {
    "consumers": ["NOT-01 (template: payout_rejected — D61, event-consumed)", "ANA-01"],
    "source": "docs/11 §4.1 (payout.rejected) + §3.5 (reject reason required — taxonomy: insufficient_kyc|risk_review|balance_mismatch|suspicious_method|other:{note})",
    "payload": obj({
      "payout_id": ULID, "account_id": ULID,
      "amount": MONEY,
      "rejected_by": ULID,
      "reason": {"type": "string", "description": "required (payout.reason_required): reason class + note (docs/11 §3.5)"},
      "rejected_at": TS,
    }, ["payout_id", "account_id", "amount", "rejected_by", "reason", "rejected_at"]),
  },
  "payout.settled": {
    "consumers": ["LED-08 (settlement posting)", "DOC-04 (receipt)", "ANA-01"],
    "source": "docs/11 §4.1 (payout.settled — Decision 6, renamed from the sheet's PayoutPaid by D60, docs/58) + docs/32 `payout_executions` (provider, reference, amount, timestamp, actor)",
    "payload": obj({
      "payout_id": ULID, "account_id": ULID, "amount": MONEY,
      "provider": {"type": "string", "description": "payout_executions.provider"},
      "reference": {"type": "string", "description": "payout_executions.reference (the provider's transfer ref — 'proof it actually left', docs/11 §3.3)"},
      "executed_by": ULID,
      "executed_at": TS,
    }, ["payout_id", "account_id", "amount", "provider", "reference", "executed_at"]),
  },
  # --- Risk (extended-catalog rows, docs/31; V1.0 breach auto-open per D68) ---
  "risk.case_opened": {
    "consumers": ["ADM (queue)", "AUD", "ANA (risk_summary daily counts)"],
    "source": "docs/10 §3.2/§4.1 + docs/32 `risk_cases` (case_id, account_ids, kind, severity, payout_hold flag — D68/D71)",
    "payload": obj({
      "case_id": ULID,
      "trader_id": {"$ref": "envelope.schema.json#/$defs/ULID", "description": "risk_cases.identity_id (the envelope carries tenant_id)"},
      "account_ids": {"type": "array", "items": ULID},
      "kind": {"type": "string", "enum": ["manual", "breach"]},
      "severity": {"type": "string", "enum": ["info", "low", "medium", "high", "critical"]},
      "payout_hold": {"type": "boolean", "description": "the dormant hold flag set at V1.0, interlock bites V1.1 (D68)"},
      "opened_by": ULID, "opened_at": TS,
    }, ["case_id", "trader_id", "account_ids", "kind", "severity", "payout_hold", "opened_at"]),
  },
  "risk.case_decided": {
    "consumers": ["PAY (hold release/keep — the interlock from V1.1)", "LCC (if action)", "AUD (sensitive)", "ANA (risk_summary daily counts)"],
    "source": "docs/10 §5 (case machine decision) + docs/32 `risk_cases` (outcome, decided_by/at)",
    "payload": obj({
      "case_id": ULID,
      "trader_id": {"$ref": "envelope.schema.json#/$defs/ULID", "description": "risk_cases.identity_id (the envelope carries tenant_id)"},
      "outcome": {"type": "string", "enum": ["confirmed", "dismissed", "escalated_platform"]},
      "actions": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
      "decided_by": ULID, "decision_note": {"type": "string"}, "decided_at": TS,
    }, ["case_id", "trader_id", "outcome", "decided_by", "decided_at"]),
  },
  # --- Identity (AUTH, ADR-13) ---
  "user.registered": {
    "consumers": ["NOT-01 (welcome)", "AUD", "ANA-01"],
    "source": "docs/02 §4.1 (user.registered, AUTH-01) + docs/32 `identities` (id) / `identity_emails` (email_hash)",
    "payload": obj({
      "identity_id": ULID,
      "email_hash": {"type": "string", "description": "sha256(normalised email) — the address itself never appears in an event payload (catalog note)"},
      "source": {"type": "string", "description": "registration channel (e.g. hosted login, sso)"},
      "registered_at": TS,
    }, ["identity_id", "source", "registered_at"]),
  },
  "user.login_success": {
    "consumers": ["AUD", "ANA-01", "RSK (anomaly baseline)"],
    "source": "docs/02 §4.1 (user.login_success, session materialisation) + docs/32 `auth_sessions` (id, amr, ip/ua per the §4.1 note)",
    "payload": obj({
      "identity_id": ULID, "session_id": ULID,
      "amr": {"type": "array", "items": {"type": "string"}, "description": "auth_sessions.amr (authentication methods)"},
      "mfa": {"type": "boolean"},
      "ip": {"type": "string"}, "user_agent": {"type": "string"},
      "logged_in_at": TS,
    }, ["identity_id", "session_id", "amr", "logged_in_at"]),
  },
  "user.login_failure": {
    "consumers": ["AUD", "RSK (anomaly scoring)", "NOT (security notice on threshold)"],
    "source": "docs/02 §4.1 (user.login_failure via ZITADEL Actions v2; payloads carry ip/ua per the §4.1 note; timing is the envelope's occurred_at)",
    "payload": obj({
      "identity_id": ULID,
      "reason": {"type": "string", "description": "provider-safe class (bad_credentials, totp_invalid, locked …) — never account-specific detail (enumeration posture, docs/02 §3.2)"},
      "attempt_count": {"type": "integer", "minimum": 1},
      "ip": {"type": "string"}, "user_agent": {"type": "string"},
    }, ["identity_id", "reason", "attempt_count"]),
  },
  "user.suspended": {
    "consumers": ["NOT-01", "GW (session kill)", "AUD"],
    "source": "docs/02 §4.1 (user.suspended, AUTH-20 / idp-sync per docs/43) + docs/32 `tenant_memberships` (id, status=suspended)",
    "payload": obj({
      "identity_id": ULID, "membership_id": ULID,
      "reason_code": {"type": "string"}, "reason_text": {"type": "string"},
      "actor": {"type": "string", "description": "actor identity (staff ULID or 'system:idp-sync')"},
      "suspended_at": TS,
    }, ["identity_id", "reason_code", "suspended_at"]),
  },
  "user.activated": {
    "consumers": ["NOT-01", "AUD"],
    "source": "docs/02 §4.1 (user.activated, AUTH-43 / idp-sync) + docs/32 `tenant_memberships` (status active)",
    "payload": obj({
      "identity_id": ULID, "membership_id": ULID,
      "actor": {"type": "string"}, "activated_at": TS,
    }, ["identity_id", "activated_at"]),
  },
  "user.session_revoked": {
    "consumers": ["AUD"],
    "source": "docs/02 §4.1 (user.session_revoked: AUTH-39 logout, AUTH-20 suspension; D6 concurrency-limit eviction) + docs/32 `auth_sessions` (id)",
    "payload": obj({
      "identity_id": ULID, "session_id": ULID,
      "reason": {"type": "string", "description": "logout|suspended|concurrency_limit|admin_revoked (AUTH-27, V2)"},
      "revoked_by": {"type": "string", "description": "actor identity or 'system'"},
      "revoked_at": TS,
    }, ["identity_id", "session_id", "reason", "revoked_at"]),
  },
  "user.password_changed": {
    "consumers": ["session invalidator", "AUD"],
    "source": "docs/02 §4.1 (user.password_changed, AUTH-05/AUTH-40; credential change kills other sessions — review G40)",
    "payload": obj({
      "identity_id": ULID,
      "method": {"type": "string", "description": "self|admin_reset|migration_reset"},
      "other_sessions_revoked": {"type": "integer", "minimum": 0},
      "changed_at": TS,
    }, ["identity_id", "method", "changed_at"]),
  },
  # --- Tenant (TEN) ---
  "tenant.created": {
    "consumers": ["AUD", "CON-01", "NOT-01 (owner)"],
    "source": "docs/03 §4.1 (tenant.created, TEN-01) + docs/32 `tenants` (slug, firm_name, idp_org_id, jurisdiction, plan, created_by)",
    "payload": obj({
      "slug": {"type": "string", "description": "tenants.slug (the {slug}.alpha1.io domain root)"},
      "firm_name": {"type": "string"},
      "idp_org_id": {"type": ["string", "null"], "description": "tenants.idp_org_id — NULL until provisioning"},
      "jurisdiction": {"type": "string", "description": "tenants.jurisdiction (ISO-3166-1 alpha-2)"},
      "plan": {"type": "string", "description": "tenants.plan (contract ref in V1)"},
      "created_by": ULID,
      "created_at": TS,
    }, ["slug", "firm_name", "created_at"]),
  },
  "tenant.provisioning_step_completed": {
    "consumers": ["CON-01 (live view)", "NOT (staff)"],
    "source": "docs/03 §3.5 (9-step saga) + docs/32 `provisioning_jobs` (current_step, status, error_message, completed_at)",
    "payload": obj({
      "step": {"type": "string", "description": "provisioning_jobs.current_step (e.g. step_1_zitadel_org)"},
      "status": {"type": "string", "enum": ["succeeded", "failed"], "description": "provisioning_jobs status on this step"},
      "error_message": {"type": ["string", "null"], "description": "provisioning_jobs.error_message — provider-safe, never a secret"},
      "completed_at": TS,
    }, ["step", "status", "completed_at"]),
  },
  "tenant.activated": {
    "consumers": ["GW (allow traffic)", "NOT-01", "AUD", "ANA-01"],
    "source": "docs/03 §4.1 (tenant.activated, onboarding checklist complete) + docs/32 `tenants.activated_at`",
    "payload": obj({
      "activated_at": TS,
      "activated_by": ULID,
    }, ["activated_at"]),
  },
  "tenant.suspended": {
    "consumers": ["AUTH (kill sessions)", "GW (deny)", "NOT-01", "AUD — all within 1 s"],
    "source": "docs/03 §4.1 (tenant.suspended, TEN-15 cascade) + docs/32 `tenants` (suspended_at, suspension_reason)",
    "payload": obj({
      "reason_code": {"type": "string"},
      "reason_text": {"type": "string", "description": "tenants.suspension_reason"},
      "actor": {"type": "string", "description": "platform staff identity or 'system'"},
      "suspended_at": TS,
    }, ["reason_code", "suspended_at"]),
  },
  "tenant.reactivated": {
    "consumers": ["GW", "NOT-01", "AUD", "AUTH"],
    "source": "docs/03 §4.1 (tenant.reactivated, TEN-15)",
    "payload": obj({
      "actor": {"type": "string"},
      "reactivated_at": TS,
    }, ["reactivated_at"]),
  },
  "tenant.member_invited": {
    "consumers": ["NOT-01 (invite email)", "CON-01"],
    "source": "docs/03 §4.1 (tenant.member_invited, AUTH-03 — V1 for the SSO cutover tenant, decision P3) + docs/32 `tenant_memberships` (id, role, status=invited)",
    "payload": obj({
      "invitation_id": {"$ref": "envelope.schema.json#/$defs/ULID", "description": "tenant_memberships.id with status='invited' (G37/D22 lifecycle)"},
      "email_hash": {"type": "string", "description": "sha256(normalised email) — never the address"},
      "role": {"type": "string", "description": "tenant_memberships.role (roles.yaml tenant realm)"},
      "invited_by": ULID,
    }, ["invitation_id", "role"]),
  },
}

def main():
    os.makedirs(OUT, exist_ok=True)
    for name, spec in EVENTS.items():
        doc = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": f"{name}.v1.json",
            "title": f"Alpha One — event {name} v1",
            "description": (
                f"V1 catalog event `{name}` (v1). Envelope per EVT-03 (see envelope.schema.json). "
                f"Producer/consumers per contracts/events/catalog.md: consumers = {', '.join(spec['consumers'])}. "
                f"Derived from: {spec['source']}. Money is integer minor units (docs/00 #3); "
                f"the envelope carries tenant_id — no redundant tenant field in the payload."
            ),
            "allOf": [
                {"$ref": "envelope.schema.json#/$defs/envelope"},
                {
                    "properties": {
                        "type": {"const": name},
                        "version": {"const": 1},
                        "payload": spec["payload"],
                    },
                    "required": ["type", "version", "payload"],
                },
            ],
        }
        with open(os.path.join(OUT, f"{name}.v1.json"), "w") as f:
            json.dump(doc, f, indent=2)
            f.write("\n")
    print(f"wrote {len(EVENTS)} payload schemas to {os.path.normpath(OUT)}")

if __name__ == "__main__":
    main()

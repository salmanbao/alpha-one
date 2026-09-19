#!/usr/bin/env python3
"""Generate contracts/events/payloads/<event>.v1.json for the 18 V1 catalog
events (contracts/events/catalog.md). Envelope per EVT-03; payload fields are
INFERRED from consumer requirements in the research (catalog.md, api/*.md,
flows) and marked as such — the sheet defines only the envelope (EVT-03), so
payload field values are owner decisions (open question in catalog.md)."""
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
    "payload": obj({
      "account_id": ULID, "challenge_id": ULID, "phase": {"type": "integer", "minimum": 1},
      "broker": {"type": "string"}, "initial_balance": MONEY,
    }, ["account_id", "challenge_id", "phase", "broker"]),
  },
  "PhaseAdvanced": {
    "consumers": ["ANA-01"],
    "payload": obj({
      "account_id": ULID, "from_phase": {"type": "integer", "minimum": 1},
      "to_phase": {"type": "integer", "minimum": 2},
    }, ["account_id", "from_phase", "to_phase"]),
  },
  "AccountPassed": {
    "consumers": ["NOT-01 (template: phase passed)", "DOC-04 (certificate)", "ANA-01"],
    "payload": obj({
      "account_id": ULID, "trader_id": ULID, "challenge_id": ULID,
      "phase": {"type": "integer", "minimum": 1}, "passed_at": TS,
    }, ["account_id", "trader_id", "challenge_id", "phase", "passed_at"]),
  },
  "AccountBreached": {
    "consumers": ["NOT-01 (template: breach)", "ANA-01"],
    "payload": obj({
      "account_id": ULID, "phase": {"type": "integer", "minimum": 1},
      "rule": {"type": "string", "description": "the breached rule (e.g. daily drawdown, max drawdown, profit target breach path)"},
      "verdict_id": ULID,
      "evidence_ref": {"type": "string", "description": "pointer to the EVL evidence snapshot (verdict input: tick data, rule state)"},
      "observed": {"type": "number"}, "limit": {"type": "number"}, "breached_at": TS,
    }, ["account_id", "phase", "rule", "verdict_id", "breached_at"]),
  },
  "AccountFailed": {
    "consumers": ["NOT-01 (template: phase failed)", "ANA-01"],
    "payload": obj({
      "account_id": ULID, "phase": {"type": "integer", "minimum": 1},
      "reason": {"type": "string"}, "failed_at": TS,
    }, ["account_id", "phase", "reason", "failed_at"]),
  },
  "FundedCreated": {
    "consumers": ["DOC-04 (certificate)", "ANA-01"],
    "payload": obj({
      "account_id": ULID, "trader_id": ULID, "parent_account_id": ULID,
      "profit_split": {"type": "number"}, "payout_frequency": {"type": "string"},
      "first_withdrawal_delay_days": {"type": "integer"},
    }, ["account_id", "trader_id", "parent_account_id"]),
  },
  "Suspended": {
    "consumers": ["PAY-04 (payout hold while open)", "ANA-01"],
    "payload": obj({
      "account_id": ULID, "actor_id": ULID, "reason": {"type": "string"}, "suspended_at": TS,
    }, ["account_id", "actor_id", "reason", "suspended_at"]),
  },
  # --- tenth pass (docs/50 D28): the Phase-1 core-loop wiring events ---
  "account.activated": {
    "consumers": ["BRG (start sync)", "EVL (start evaluation + create evaluation_state)", "NOT-01", "AUD"],
    "payload": obj({
      "account_id": ULID, "broker_account_id": ULID,
      "server": {"type": "string", "description": "broker server id (ADR-12 day-boundary authority)"},
      "phase": {"type": "integer", "minimum": 1},
    }, ["account_id", "broker_account_id", "server", "phase"]),
  },
  "account.day_rolled": {
    "consumers": ["EVL (daily reset)", "ANA"],
    "payload": obj({
      "account_id": ULID,
      "broker_date": {"type": "string", "description": "the new broker-server date (YYYY-MM-DD, per server group timezone)"},
      "server": {"type": "string"},
      "trading_days": {"type": "integer", "minimum": 0},
      "calendar_days": {"type": "integer", "minimum": 0},
    }, ["account_id", "broker_date", "server", "trading_days", "calendar_days"]),
  },
  "evaluation.verdict": {
    "consumers": ["LCC (transitions; dedupe on (account_id, verdict_id) per LCC-43)", "NOT-01", "DOC-04 (TD-25 breach report)", "AUD (critical on breach)", "RSK (V2 case open)"],
    "payload": obj({
      "account_id": ULID, "verdict_id": ULID,
      "status": {"type": "string", "enum": ["breach", "target_hit", "gap_flagged"],
                 "description": "target_hit_pending is recorded in evaluations.status only — it is never emitted (docs/09 §3.4)"},
      "rule_id": {"type": "string", "description": "required when status=breach (e.g. max_daily_loss, max_total_loss, time_limit — D30)"},
      "input_hash": {"type": "string", "description": "sha256(state||rules||tick) — the EVL-49 re-run proof"},
      "broker_time": TS,
      "limit_cents": {"type": "integer"}, "observed_cents": {"type": "integer"},
      "tolerance_cents": {"type": "integer"},
    }, ["account_id", "verdict_id", "status", "input_hash", "broker_time"]),
  },
  "evaluation.daily_reset": {
    "consumers": ["ANA (daily P&L points)", "AUD (standard)"],
    "payload": obj({
      "account_id": ULID,
      "broker_date": {"type": "string", "description": "the closed broker-server date (YYYY-MM-DD)"},
      "day_pnl_cents": {"type": "integer"},
      "equity_end_cents": {"type": "integer"},
      "trading_days": {"type": "integer", "minimum": 0},
    }, ["account_id", "broker_date", "day_pnl_cents", "equity_end_cents", "trading_days"]),
  },
  "bridge.tick": {
    "consumers": ["EVL (evaluate)", "ANA (equity points) — observed record per EVL-49; no audit mirror (docs/05 §14)"],
    "payload": obj({
      "account_id": ULID,
      "equity_cents": {"type": "integer", "description": "broker-reported equity in cents — never recomputed, broker is truth (docs/09 §3.3)"},
      "balance_cents": {"type": "integer"},
      "open_positions": {"type": "integer", "minimum": 0},
      "broker_time": TS,
    }, ["account_id", "equity_cents", "balance_cents", "open_positions", "broker_time"]),
  },
  "Resumed": {
    "consumers": ["ANA-01"],
    "payload": obj({
      "account_id": ULID, "actor_id": ULID, "resumed_at": TS,
    }, ["account_id", "actor_id", "resumed_at"]),
  },
  # --- Checkout ---
  "order.paid": {
    "consumers": ["LCC-05 (provisioning)", "LED-04 (payment capture posting)", "ANA-01"],
    "payload": obj({
      "order_id": ULID, "challenge_id": ULID, "size": {"type": "string"},
      "amount": MONEY, "payment_method": {"type": "string"},
      "provider": {"type": "string"}, "provider_event_id": {"type": "string"},
      "coupon_code": {"type": ["string", "null"]},
    }, ["order_id", "challenge_id", "size", "amount", "payment_method", "provider", "provider_event_id"]),
  },
  "checkout.session.expired": {
    "consumers": ["ANA-01 (funnel/abandonment read model)"],
    "payload": obj({
      "session_id": ULID, "challenge_id": ULID, "expired_at": TS,
    }, ["session_id", "challenge_id", "expired_at"]),
  },
  # --- KYC (KYC-05, V1 per Decision 5) ---
  "kyc.submitted": {
    "consumers": ["NOT-01 (template: KYC result)", "ANA-01"],
    "payload": obj({
      "kyc_verification_id": ULID, "trader_id": ULID, "provider": {"type": "string"},
      "provider_reference": {"type": "string"}, "submitted_at": TS,
    }, ["kyc_verification_id", "trader_id", "provider"]),
  },
  "kyc.approved": {
    "consumers": ["NOT-01 (template: KYC result)", "LCC-06 (auto-upgrade on approval)", "PAY-03 (payout eligibility)", "ANA-01"],
    "payload": obj({
      "kyc_verification_id": ULID, "trader_id": ULID, "provider": {"type": "string"},
      "provider_reference": {"type": "string"}, "approved_at": TS,
    }, ["kyc_verification_id", "trader_id", "provider", "approved_at"]),
  },
  "kyc.rejected": {
    "consumers": ["NOT-01 (template: KYC result)", "ANA-01"],
    "payload": obj({
      "kyc_verification_id": ULID, "trader_id": ULID, "reason": {"type": "string"}, "rejected_at": TS,
    }, ["kyc_verification_id", "trader_id", "reason", "rejected_at"]),
  },
  "kyc.expired": {
    "consumers": ["NOT-01 (template: KYC result)", "ANA-01"],
    "payload": obj({
      "kyc_verification_id": ULID, "trader_id": ULID, "expired_at": TS,
    }, ["kyc_verification_id", "trader_id", "expired_at"]),
  },
  "kyc.resubmission_requested": {
    "consumers": ["NOT-01 (template: KYC result)", "ANA-01"],
    "payload": obj({
      "kyc_verification_id": ULID, "trader_id": ULID, "reason": {"type": "string"}, "requested_at": TS,
    }, ["kyc_verification_id", "trader_id", "reason"]),
  },
  # --- Payout ---
  "payout.approved": {
    "consumers": ["LED-07 (payout obligation posting)", "NOT-01 (template: payout approved)", "ANA-01"],
    "payload": obj({
      "payout_id": ULID, "account_id": ULID, "amount": MONEY,
      "approved_by": ULID, "approved_at": TS,
    }, ["payout_id", "account_id", "amount", "approved_by", "approved_at"]),
  },
  "payout.rejected": {
    "consumers": ["NOT-01 (template: payout rejected)", "ANA-01"],
    "payload": obj({
      "payout_id": ULID, "account_id": ULID, "amount": MONEY,
      "rejected_by": ULID, "reason": {"type": "string"}, "rejected_at": TS,
    }, ["payout_id", "account_id", "amount", "rejected_by", "reason", "rejected_at"]),
  },
  "PayoutPaid": {
    "consumers": ["LED-08 (settlement posting)", "DOC-04 (certificate)", "ANA-01"],
    "payload": obj({
      "payout_id": ULID, "account_id": ULID, "amount": MONEY,
      "provider": {"type": "string"}, "reference": {"type": "string"},
      "executed_by": ULID, "executed_at": TS,
    }, ["payout_id", "account_id", "amount", "provider", "reference", "executed_at"]),
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
                f"Payload field values are INFERRED from consumer requirements; the sheet fixes only the "
                f"envelope (EVT-03) — field confirmation is an open owner decision (catalog.md)."
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

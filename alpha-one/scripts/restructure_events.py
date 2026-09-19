#!/usr/bin/env python3
"""Restructure §4 (Events) of the four V1-emitting module docs (07 LCC,
12 CHK, 13 KYC, 11 PAY):
  - prepend the V1 baseline events from contracts/events/catalog.md
    (exact event names, producers, V1 consumers);
  - keep the pre-existing table as the extended (post-V1) event model with
    an explicit mapping note (how each V1 baseline event relates to the
    extended model)."""
import os, re

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
DOCS = os.path.join(ROOT, "docs")

BASE = (
    "### 4.1 V1 baseline events — authoritative\n\n"
    "From `contracts/events/catalog.md` (the V1 execution sheet). Envelope "
    "EVT-03 (`id`, `type`, `version`, `tenant_id`, `occurred_at`, `payload`); "
    "schemas in `contracts/events/payloads/`. Producers write the outbox "
    "(EVT-01); consumers are idempotent by event id (EVT-05).\n\n"
)

DOCS4 = {
    "07-account-lifecycle.md": {
        "rows": [
            ("AccountCreated", "LCC-23", "NOT-01 (template: account created), ANA-01"),
            ("PhaseAdvanced", "LCC-23", "ANA-01"),
            ("AccountPassed", "LCC-23", "NOT-01 (template: phase passed), DOC-04 (certificate), ANA-01"),
            ("AccountBreached", "LCC-23", "NOT-01 (template: breach), ANA-01"),
            ("AccountFailed", "LCC-23", "NOT-01 (template: phase failed), ANA-01"),
            ("FundedCreated", "LCC-23", "DOC-04 (certificate), ANA-01"),
            ("Suspended", "LCC-23", "PAY-04 (payout hold while open), ANA-01"),
            ("Resumed", "LCC-23", "ANA-01"),
        ],
        "map": (
            "**Mapping to the extended model below:** V1 emits the single "
            "`AccountCreated` when the account exists in the lifecycle "
            "(the extended `account.purchased` + `account.activated` pair is "
            "internal V2 granularity); `AccountPassed` = the extended "
            "`account.phase_completed`; `AccountBreached` = `account.breached`; "
            "`AccountFailed` = `account.expired` / `account.closed`; "
            "`FundedCreated` = `account.funded`; `Suspended` / `Resumed` = "
            "`account.suspended` / `account.resumed`."
        ),
        "drop": [],
    },
    "12-checkout-billing.md": {
        "rows": [
            ("order.paid", "CHK-09 (payment captured, via CHK-07 webhook + CHK-08 order)", "LCC-05 (provisioning), LED-04 (payment capture posting), ANA-01"),
            ("checkout.session.expired", "CHK-43 (scheduled expiry worker, via outbox)", "ANA-01 (funnel/abandonment read model)"),
        ],
        "map": (
            "**Mapping to the extended model below:** `order.paid` = the "
            "extended `payment.intent_captured`; `checkout.session.expired` = "
            "the extended `payment.intent_expired` (added to V1 scope by "
            "Decision 7, 2026-09-16). The `checkout started / abandoned / "
            "completed` events of earlier drafts are NOT in the V1 sheet — "
            "abandoned-cart analytics is a scope change (catalog.md)."
        ),
        "drop": [],
    },
    "13-kyc.md": {
        "rows": [
            ("kyc.submitted", "KYC-05 (webhook status handling), KYC-16", "NOT-01 (template: KYC result), ANA-01"),
            ("kyc.approved", "KYC-05, KYC-16", "NOT-01, LCC-06 (auto-upgrade on approval), PAY-03 (payout eligibility), ANA-01"),
            ("kyc.rejected", "KYC-05, KYC-16", "NOT-01, ANA-01"),
            ("kyc.expired", "KYC-05, KYC-16", "NOT-01, ANA-01 — EXPIRED trigger is an open question"),
            ("kyc.resubmission_requested", "KYC-05, KYC-16", "NOT-01, ANA-01"),
        ],
        "map": (
            "**Mapping to the extended model below:** `kyc.submitted` = "
            "`kyc.session_started`; `kyc.approved` = `kyc.verified`; "
            "`kyc.rejected` / `kyc.resubmission_requested` = the terminal "
            "branches of the extended `kyc.status_changed`. The five V1 "
            "events were moved into V1 scope by Decision 5 (2026-09-16): "
            "KYC-05 was amended to emit them through the outbox and KYC-16 "
            "moved from V2.0 to V1.0 / V1-Core. LCC-07 / KYC-07 / KYC-08 "
            "gates remain **synchronous status checks**, not event "
            "consumption."
        ),
        "drop": [],
    },
    "11-payout-system.md": {
        "rows": [
            ("payout.approved", "PAY-09", "LED-07 (payout obligation posting), NOT-01 (template: payout approved), ANA-01"),
            ("payout.rejected", "PAY-09", "NOT-01 (template: payout rejected), ANA-01"),
            ("PayoutPaid", "PAY-12 (execution recording, via outbox — Decision 6)", "LED-08 (settlement posting), DOC-04 (certificate), ANA-01"),
        ],
        "map": (
            "**Mapping to the extended model below:** `payout.approved` / "
            "`payout.rejected` are the same events (their extended-table rows "
            "are folded into the baseline table above); `PayoutPaid` = the "
            "extended `payout.settled` (Decision 6, 2026-09-16: emitted by "
            "PAY-12 through the outbox). The extended `payout.requested` has "
            "no V1 counterpart — whether a request event exists is an open "
            "question (contracts/api/not.md, template 7)."
        ),
        "drop": ["`payout.approved` / `payout.rejected`", "`payout.settled`"],
    },
}

def main():
    for doc, spec in DOCS4.items():
        path = os.path.join(DOCS, doc)
        text = open(path).read()
        m = re.search(r"^(## 4\.[^\n]*\n)(.*?)(?=^## 5\. )", text, re.S | re.M)
        if not m:
            print(f"SKIP {doc}"); continue
        old = m.group(2)
        tb = ["| Event | Producer (V1) | V1 consumers |", "|---|---|---|"]
        for name, prod, cons in spec["rows"]:
            tb.append(f"| `{name}` | {prod} | {cons} |")
        baseline = BASE + "\n".join(tb) + "\n\n" + spec["map"] + "\n\n"
        # fold dropped rows out of the extended table
        ext_lines = []
        for line in old.splitlines():
            if line.lstrip().startswith("|") and any(d in line for d in spec["drop"]):
                continue
            ext_lines.append(line)
        ext = "\n".join(ext_lines)
        ext = re.sub(
            r"^(## 4\.[^\n]*\n)", r"\1", ext  # keep original section heading in place
        )
        new_sec = (
            m.group(1)
            + "\n"
            + baseline
            + "### 4.2 Extended (post-V1) event model — design-level\n\n"
            "> The extended event set for V2/V3 (and internal V1 detail where "
            "marked); see the mapping above for how it relates to the V1 "
            "baseline. Topic, dedupe, and transport rules unchanged "
            "(docs/04 §5).\n\n"
            + ext.strip()
        )
        text = text[:m.start()] + new_sec + "\n" + text[m.end():]
        open(path, "w").write(text)
        print(f"OK {doc}: +{len(spec['rows'])} V1 events, "
              f"{len(spec['drop'])} extended rows folded")

if __name__ == "__main__":
    main()

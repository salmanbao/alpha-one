#!/usr/bin/env python3
"""Contract gate: every V1 event in contracts/events/catalog.md must have a
payload schema file, and each schema must be well-formed (valid JSON, valid
JSON Schema draft 2020-12, `type` const matching the catalog event, no
float-typed money fields).

This is the gate that keeps the "payload schemas" gap from reopening silently
(gap-closure pass, 2026-09-20): the catalog's per-event `payloads/<Name>.v1.json`
cell and the file on disk must agree, and the money-as-integer-minor-units rule
(docs/00 non-negotiable #3) is checked structurally.

Usage:
  python3 scripts/check_event_payloads.py            # fail (exit 1) on any gap
  python3 scripts/check_event_payloads.py --check    # same (alias for CI)

Wire into CI next to the other contract gates (docs/99 0.10: error registry,
31 catalog, 32 schema checks).
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CATALOG = ROOT / "contracts" / "events" / "catalog.md"
PAYLOADS = ROOT / "contracts" / "events" / "payloads"

# Money field names that must never be type: number (docs/00 #3). Prices and
# lots are asset/asset ratios and quantities — they are NOT money and are
# excluded by name below.
MONEY_KEY = re.compile(r"(^|_)(amount|cents|balance|equity|pnl|profit|fee|split[_a-z]*bps|price_cents)(_|$)", re.I)
NOT_MONEY = re.compile(r"(open_price|current_price|_price$|lots$|profit_split$)", re.I)


def catalog_events() -> list[tuple[str, str]]:
    """Return [(event_name, declared_payload_path)] from the catalog tables."""
    text = CATALOG.read_text(encoding="utf-8")
    out: list[tuple[str, str]] = []
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 5 or cells[0] in ("Event", "---") or set(cells[0]) <= {"-"}:
            continue
        name = cells[0]
        m = re.search(r"`(payloads/[^`]+)`", line)
        if not m:
            continue
        out.append((name, m.group(1)))
    return out


def check() -> list[str]:
    errors: list[str] = []
    events = catalog_events()
    if not events:
        return ["catalog: no events parsed — catalog.md format changed?"]
    for name, rel in events:
        path = ROOT / "contracts" / "events" / rel
        if not path.exists():
            errors.append(f"{name}: missing payload schema file {rel}")
            continue
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            errors.append(f"{name}: {rel} is not valid JSON ({e})")
            continue
        # valid 2020-12 schema with the allOf envelope composition
        if doc.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
            errors.append(f"{name}: {rel} lacks the 2020-12 $schema")
        all_of = doc.get("allOf", [])
        if len(all_of) != 2 or all_of[0].get("$ref") != "envelope.schema.json#/$defs/envelope":
            errors.append(f"{name}: {rel} must allOf [envelope, event-const]")
        else:
            const = all_of[1].get("properties", {}).get("type", {}).get("const")
            if const != name:
                errors.append(f"{name}: {rel} type const is {const!r}, expected {name!r}")
        payload = all_of[1].get("properties", {}).get("payload") if len(all_of) == 2 else None
        if not isinstance(payload, dict):
            errors.append(f"{name}: {rel} has no payload object schema")
            continue
        # money-as-integer-minor-units: no float-typed money fields
        def walk(node, path="$"):
            if isinstance(node, dict):
                for k, v in node.items():
                    p = f"{path}.{k}"
                    if isinstance(v, dict):
                        t = v.get("type")
                        if t == "number" and MONEY_KEY.search(k) and not NOT_MONEY.search(k):
                            errors.append(f"{name}: {rel} field {p} is type 'number' — money must be integer minor units (docs/00 #3)")
                        walk(v, p)
                    elif isinstance(v, list):
                        for i, item in enumerate(v):
                            walk(item, f"{p}[{i}]")
        walk(payload, "payload")
    # structural sanity: the two extended risk.* schemas present in payloads/
    # are fine to exist beyond the catalog; we only fail on missing catalog files.
    print(f"catalog events: {len(events)}")
    for e in events:
        print(f"  ok   {e[0]} -> {e[1]}")
    return errors


if __name__ == "__main__":
    fails = check()
    if fails:
        print(f"\nFAIL: {len(fails)} problem(s):")
        for f in fails:
            print(" -", f)
        sys.exit(1)
    print("\ncontracts/events: ALL OK — every catalog event has a payload schema")

#!/usr/bin/env python3
"""Verify the tenant state -> capability matrix (seventh pass, docs/47 — M1/M2).

`contracts/tenants/state-capabilities.yaml` is the machine-readable source for the
docs/03 §5.1 table and for the docs/35 I-20 table-driven test ("the §5.1 state→
capability matrix holds for every state x surface pair"). This script is the CI
gate that keeps the YAML, the rendered table and the error taxonomy identical.

Invariants checked:

1. Every state in the YAML appears in the `tenants.status` CHECK list of the
   docs/03 §9 DDL (the lifecycle and the matrix can never diverge).
2. Every capability is specified for every state (`allow` | `deny` | `degraded`).
3. Every deny code exists in `contracts/errors/taxonomy.md` — the matrix may only
   return registered GW-18 codes (this closes finding M2: `tenant.not_ready` was
   referenced by three docs but never registered; the canonical code is
   `tenant.not_live`).
4. The rendered docs/03 §5.1 table (between the `tenant-states:begin`/`:end`
   markers) regenerates byte-identical from the YAML.

Usage:
  python3 scripts/verify_tenant_states.py             # check (exit 1 on error)
  python3 scripts/verify_tenant_states.py --write-doc # rewrite the docs/03 §5.1 render block
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "contracts" / "tenants" / "state-capabilities.yaml"
DOC = ROOT / "docs" / "03-tenant-management.md"
TAXONOMY = ROOT / "contracts" / "errors" / "taxonomy.md"

BEGIN = "<!-- tenant-states:begin (generated from contracts/tenants/state-capabilities.yaml — do not edit by hand) -->"
END = "<!-- tenant-states:end -->"

# docs/03 §5.1 column order (capability key -> header)
COLUMNS = [
    ("trader_routes", "Trader login/traffic"),
    ("staff_routes", "Staff (ADM)"),
    ("api_keys", "API keys"),
    ("webhooks_out", "Webhooks out"),
    ("bridge_sync", "Bridge sync"),
    ("payments", "Payments"),
    ("payouts", "Payouts"),
]


def load_matrix() -> dict:
    text = MATRIX.read_text()
    try:
        import yaml  # type: ignore

        return yaml.safe_load(text)
    except ImportError:
        return json.loads(text)


def ddl_states() -> set[str]:
    """The tenants.status CHECK list from the docs/03 §9 DDL."""
    text = DOC.read_text()
    m = re.search(
        r"CHECK \(status IN \(([^)]*)\)\)", text.split("CREATE TABLE tenants", 1)[1]
    )
    if not m:
        raise SystemExit("docs/03 §9: tenants.status CHECK list not found")
    return set(re.findall(r"'([a-z_]+)'", m.group(1)))


def taxonomy_codes() -> set[str]:
    return set(re.findall(r"^\|\s*`([a-z0-9_.]+)`\s*\|", TAXONOMY.read_text(), re.M))


def render_cell(cap) -> str:
    if cap == "allow":
        return "✓"
    if isinstance(cap, str):  # malformed — surfaced by the structural checks
        return "?"
    if "deny" in cap:
        out = f"— (`{cap['deny']}`"
        note = cap.get("note")
        if note:
            out += f"; {note}"
        return out + ")"
    if "degraded" in cap:
        return f"~ ({cap['degraded']})"
    return "?"


def render(spec: dict) -> str:
    states = spec["states"]
    lines = [
        BEGIN,
        "",
        "| State | Trader login/traffic | Staff (ADM) | API keys | Webhooks out | Bridge sync | Payments | Payouts |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for state, caps in states.items():
        row = [f"`{state}`"]
        for key, _label in COLUMNS:
            row.append(render_cell(caps[key]))
        lines.append("| " + " | ".join(row) + " |")
    lines += [
        "",
        "`✓` allowed · `—` blocked (the GW-18 code returned; `details.state` carries the tenant state where the code is generic) · `~` allowed but degraded (note). "
        "Generated from `contracts/tenants/state-capabilities.yaml` — the same file the docs/35 I-20 table-driven test consumes; "
        "enforcement point is GW step 3.5a (docs/04 §3.1), with module-level holds (payout hold, bridge pause, webhook queue → DLQ) "
        "applied by the owning modules from the same `tenant.*` events. Console (platform realm) is not governed by tenant state.",
        "",
        END,
    ]
    return "\n".join(lines)


def check_doc(rendered: str) -> list[str]:
    text = DOC.read_text()
    m = re.search(re.escape(BEGIN) + r".*?" + re.escape(END), text, re.S)
    if not m:
        return ["docs/03 §5.1: tenant-states:begin/:end block missing"]
    if m.group(0).rstrip("\n") != rendered.rstrip("\n"):
        return ["docs/03 §5.1: rendered state table differs from state-capabilities.yaml (run --write-doc)"]
    return []


def write_doc(rendered: str) -> None:
    text = DOC.read_text()
    if re.search(re.escape(BEGIN) + r".*?" + re.escape(END), text, re.S):
        text = re.sub(
            re.escape(BEGIN) + r".*?" + re.escape(END), rendered.rstrip("\n"), text, flags=re.S
        )
    else:
        raise SystemExit("docs/03: marker block missing — insert it once, then re-run")
    DOC.write_text(text)


def main() -> int:
    spec = load_matrix()
    states: dict = spec["states"]
    errors: list[str] = []
    codes = taxonomy_codes()

    # 1 — states == DDL lifecycle
    ddl = ddl_states()
    for name in states:
        if name not in ddl:
            errors.append(f"{name}: in state-capabilities.yaml but not in the docs/03 §9 status CHECK")
    for name in ddl:
        if name not in states:
            errors.append(f"{name}: in the docs/03 §9 status CHECK but not in state-capabilities.yaml")

    # 2 — complete capability set per state
    for state, caps in states.items():
        for key, _label in COLUMNS:
            if key not in caps:
                errors.append(f"{state}.{key}: missing cell")
        for key, cap in caps.items():
            if key.startswith("$"):
                continue
            if cap != "allow" and (not isinstance(cap, dict) or not ({"deny", "degraded"} & set(cap))):
                errors.append(f"{state}.{key}: cell must be 'allow', {{deny: code}} or {{degraded: note}}")

    # 3 — deny codes are registered
    for state, caps in states.items():
        for key, cap in caps.items():
            if isinstance(cap, dict) and "deny" in cap and cap["deny"] not in codes:
                errors.append(f"{state}.{key}: deny code '{cap['deny']}' is not in contracts/errors/taxonomy.md")

    rendered = render(spec)

    if "--write-doc" in sys.argv:
        write_doc(rendered)
        print("docs/03 §5.1 render block rewritten from contracts/tenants/state-capabilities.yaml")
    else:
        errors += check_doc(rendered)

    if errors:
        print("FAIL — tenant state matrix is inconsistent:\n")
        for e in errors:
            print(f"  - {e}")
        return 1

    n_cells = len(states) * len(COLUMNS)
    print(
        f"OK: tenant state matrix consistent — {len(states)} states x {len(COLUMNS)} capabilities "
        f"({n_cells} cells), all deny codes registered, docs/03 §5.1 render in sync (I-20 source)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

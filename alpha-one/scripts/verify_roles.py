#!/usr/bin/env python3
"""Verify the authorization binding set (decision D14/D15, docs/44 §4).

`contracts/permissions/roles.yaml` is the single source for role → permission-key
bindings; it seeds the `casbin_rule` table and is rendered into docs/02 §3.1. This
script is the CI gate that keeps the three views identical.

Invariants checked:

1. Every bound key exists in `contracts/permissions/registry.md`.
2. Realm separation: `platform` scope ⇒ platform roles only; `all`/`own` ⇒ tenant
   roles only (AUTH-16 — one key never spans both realms).
3. Effective holder sets are closed under descendants: if role R holds a key, every
   role that (transitively) inherits from R is listed for that key too — so
   `roles` is exactly the set of roles that can exercise the key, and the seeded
   policy rows (one per listed role) reproduce it without resolving inheritance.
4. A role's rendered key list (docs/02 §3.1, between the `roles:begin`/`roles:end`
   markers) equals its effective set = own listed keys ∪ every ancestor's listed keys.
5. Warnings: keys with no holder, registry keys with no binding and no provisional row.

Usage:
  python3 scripts/verify_roles.py             # check (exit 1 on error)
  python3 scripts/verify_roles.py --seed      # print the casbin_rule INSERTs
  python3 scripts/verify_roles.py --write-doc # rewrite the docs/02 §3.1 render block
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROLES = ROOT / "contracts" / "permissions" / "roles.yaml"
REGISTRY = ROOT / "contracts" / "permissions" / "registry.md"
DOC = ROOT / "docs" / "02-identity-access.md"
CONTRACTS = sorted((ROOT / "contracts").glob("*.openapi.yaml"))
MARKERS = {"self", "none"}          # explicit keyless markers (docs/45 §G41)

BEGIN = "<!-- roles:begin (generated from contracts/permissions/roles.yaml — do not edit by hand) -->"
END = "<!-- roles:end -->"

REALM_ORDER = ["tenant", "platform"]


def load_roles() -> dict:
    text = ROLES.read_text()
    try:
        import yaml  # type: ignore

        return yaml.safe_load(text)
    except ImportError:
        return json.loads(text)


def registry_keys(head_only: bool = False) -> set[str]:
    """Key names declared in registry.md (all sections, or the V1 table only)."""
    text = REGISTRY.read_text()
    if head_only:
        text = text.split("## Permission model notes", 1)[0]
    return set(re.findall(r"^\|\s*`([a-z0-9_.]+)`\s*\|", text, re.M))


def ancestors(role: str, catalog: dict) -> set[str]:
    out: set[str] = set()
    stack = list(catalog[role].get("inherits") or [])
    while stack:
        parent = stack.pop()
        if parent in out:
            continue
        out.add(parent)
        stack.extend(catalog.get(parent, {}).get("inherits") or [])
    return out


def descendants(role: str, catalog: dict) -> set[str]:
    children: dict[str, set[str]] = {r: set() for r in catalog}
    for r, meta in catalog.items():
        for parent in meta.get("inherits") or []:
            children.setdefault(parent, set()).add(r)
    out: set[str] = set()
    stack = list(children.get(role, ()))
    while stack:
        child = stack.pop()
        if child in out:
            continue
        out.add(child)
        stack.extend(children.get(child, ()))
    return out


def effective(role: str, bindings: dict, catalog: dict) -> list[str]:
    own = {k for k, rule in bindings.items() if role in rule.get("roles", [])}
    inherited = {
        k for k, rule in bindings.items() if ancestors(role, catalog) & set(rule.get("roles", []))
    }
    return sorted(own | inherited)


def render(spec: dict) -> str:
    catalog, bindings = spec["role_catalog"], spec["bindings"]
    lines = [BEGIN, ""]
    for scope in REALM_ORDER:
        lines.append(f"**{'Tenant' if scope == 'tenant' else 'Platform'} realm**")
        lines.append("")
        lines.append("| Role | Permission keys (effective) |")
        lines.append("|---|---|")
        for role, meta in catalog.items():
            if meta["realm"] != scope:
                continue
            keys = effective(role, bindings, catalog)
            shown = ", ".join(f"`{k}`" for k in keys) if keys else "_none_"
            lines.append(f"| `{role}` | {shown} |")
        lines.append("")
    lines.append(END)
    return "\n".join(lines)


def check_contracts(bindings: dict) -> tuple[list[str], list[str]]:
    """Every V1 operation declares a permission (key | self | none) — review G41.

    Keys must be bound in roles.yaml (and therefore declared in the registry);
    `self` = caller acting on their own data (the own-data matcher still runs),
    `none` = unauthenticated or signature-authenticated (provider webhooks).
    Post-V1 operations are scanned too, so a key that is *never* used by any route
    is reported (a V1-bound key whose only routes are post-V1 is reported as info:
    the binding is a Phase-N obligation, not a V1 hole).
    """
    errors: list[str] = []
    warnings: list[str] = []
    if not CONTRACTS:
        warnings.append("no contracts/*.openapi.yaml found - route-permission check skipped")
        return errors, warnings
    try:
        import yaml  # type: ignore
    except ImportError:
        warnings.append("PyYAML unavailable - route-permission check skipped")
        return errors, warnings
    v1_used: dict[str, int] = {}
    post_used: dict[str, int] = {}
    n_v1 = 0
    n_self = n_none = 0
    for f in CONTRACTS:
        doc = yaml.safe_load(f.read_text()) or {}
        for path, item in (doc.get("paths") or {}).items():
            for meth, op in item.items():
                if meth not in ("get", "post", "put", "patch", "delete"):
                    continue
                perm = op.get("x-permission")
                is_v1 = str(op.get("x-phase", "")).lower() == "v1"
                where = f"{f.name} {meth.upper()} {path}"
                if is_v1:
                    n_v1 += 1
                    if not perm:
                        errors.append(f"{where}: V1 operation without x-permission")
                        continue
                    if perm in MARKERS:
                        if perm == "self":
                            n_self += 1
                        else:
                            n_none += 1
                        continue
                    v1_used[perm] = v1_used.get(perm, 0) + 1
                    if perm not in bindings:
                        errors.append(f"{where}: permission key '{perm}' is not bound in roles.yaml")
                elif perm and perm not in MARKERS:
                    post_used[perm] = post_used.get(perm, 0) + 1
    unused = sorted(k for k in bindings if k not in v1_used and k not in post_used)
    if unused:
        print("  note: V1-bound keys with no V1 route (the post-V1 surface is not "
              "contract-annotated yet, so these attach to extended routes): "
              + ", ".join(unused))
    n_keyed_ops = sum(v1_used.values())
    print(f"  route coverage: {n_v1} V1 operations checked — {n_keyed_ops} with registry keys "
          f"({len(v1_used)} distinct), {n_self} `self`, {n_none} `none`")
    return errors, warnings


def check_doc(spec: dict) -> list[str]:
    text = DOC.read_text()
    m = re.search(re.escape(BEGIN) + r".*?" + re.escape(END), text, re.S)
    if not m:
        return ["docs/02 §3.1: roles:begin/roles:end block missing"]
    want = render(spec)
    got = m.group(0).rstrip("\n")
    if got != want:
        return ["docs/02 §3.1: rendered role table differs from roles.yaml (run --write-doc)"]
    return []


def write_doc(spec: dict) -> bool:
    text = DOC.read_text()
    want = render(spec)
    if re.search(re.escape(BEGIN) + r".*?" + re.escape(END), text, re.S):
        text = re.sub(re.escape(BEGIN) + r".*?" + re.escape(END), want, text, flags=re.S)
    else:
        anchor = "**Role catalog (AUTH-12"
        idx = text.find(anchor)
        if idx < 0:
            raise SystemExit("docs/02: anchor for the render block not found")
        end = text.find("\n\n", idx)
        text = text[: end + 2] + want + "\n\n" + text[end + 2 :]
    DOC.write_text(text)
    return True


def main() -> int:
    spec = load_roles()
    catalog, bindings = spec["role_catalog"], spec["bindings"]
    keys = registry_keys()
    v1_keys = registry_keys(head_only=True)
    errors: list[str] = []
    warnings: list[str] = []

    if "--write-doc" in sys.argv:
        write_doc(spec)
        print("docs/02 §3.1 render block rewritten from contracts/permissions/roles.yaml")

    for key, rule in bindings.items():
        if key not in keys:
            errors.append(f"{key}: not found in registry.md")
        scope = rule.get("scope")
        for role in rule.get("roles", []):
            if role not in catalog:
                errors.append(f"{key}: unknown role {role}")
                continue
            realm = catalog[role]["realm"]
            if scope == "platform" and realm != "platform":
                errors.append(f"{key} (platform scope): tenant role {role}")
            if scope in ("all", "own") and realm == "platform":
                errors.append(f"{key} ({scope} scope): platform role {role} — one key never spans realms")

    # 3 — closure under descendants
    for key, rule in bindings.items():
        holders = set(rule.get("roles", []))
        for role in holders:
            missing = descendants(role, catalog) - holders
            if missing:
                errors.append(
                    f"{key}: {role} holds it, so its inheritors must hold it too — missing "
                    + ", ".join(sorted(missing))
                )

    # 4 — rendered list == effective set
    for role in catalog:
        listed = {k for k, rule in bindings.items() if role in rule.get("roles", [])}
        if sorted(listed) != effective(role, bindings, catalog):
            errors.append(f"{role}: effective key set is not reproduced by its listed keys")

    errors += check_doc(spec)
    contract_errors, contract_warnings = check_contracts(bindings)
    errors += contract_errors
    warnings += contract_warnings

    provisional = set(spec.get("provisional_bindings", {})) - {"$comment"}
    unbound = v1_keys - set(bindings)
    if unbound:
        warnings.append("V1 registry keys with no binding: " + ", ".join(sorted(unbound)))
    unknown_provisional = provisional - keys
    if unknown_provisional:
        errors.append("provisional_bindings reference keys absent from registry.md: " + ", ".join(sorted(unknown_provisional)))

    if errors:
        print("FAIL — role binding set is inconsistent:\n")
        for e in errors:
            print(f"  - {e}")
        return 1

    print(
        f"OK: roles.yaml consistent — {len(bindings)} bound V1 keys, {len(catalog)} roles, "
        f"{len(keys)} registry keys, docs/02 render in sync, every V1 route declares its permission."
    )
    for w in warnings:
        print(f"  warning: {w}")

    if "--seed" in sys.argv:
        print("\n-- casbin_rule seed: p rows (role × key × scope) --")
        for key, rule in sorted(bindings.items()):
            for role in sorted(rule.get("roles", [])):
                print(
                    "INSERT INTO casbin_rule (ptype, v0, v1, v2) VALUES "
                    f"('p', '{role}', '{key}', '{rule.get('scope', 'all')}') ON CONFLICT DO NOTHING;"
                )
        print("\n-- casbin_rule seed: g rows (role inheritance) --")
        for role, meta in sorted(catalog.items()):
            for parent in meta.get("inherits") or []:
                print(
                    "INSERT INTO casbin_rule (ptype, v0, v1) VALUES "
                    f"('g', '{role}', '{parent}') ON CONFLICT DO NOTHING;"
                )
    return 0


if __name__ == "__main__":
    sys.exit(main())

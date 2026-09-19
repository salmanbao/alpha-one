#!/usr/bin/env python3
"""Restructure each module doc's §7 (API endpoints):
  7.1  V1 baseline — extracted from contracts/api/<mod>.md (authoritative,
       V1 execution-sheet research 2026-09-16/17).
  7.2  Extended (post-V1) surface — the doc's pre-existing endpoint content,
       explicitly provisional (the URL plan beyond the V1 baseline is an
       open owner decision — contracts/api/gw.md).
Modules without a V1 contract file get a scope note instead of a baseline."""
import os, re

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
DOCS = os.path.join(ROOT, "docs")
API = os.path.join(ROOT, "contracts", "api")

# doc file -> api file(s)
MAP = {
    "02-identity-access.md": ["auth"],
    "03-tenant-management.md": ["tenant"],
    "04-gateway-events.md": ["gw"],
    "05-ledger-audit.md": ["led", "aud"],
    "06-devops-deployment.md": ["ops"],
    "07-account-lifecycle.md": ["lcc"],
    "08-trading-bridge.md": ["brg"],
    "09-evaluation-engine.md": ["evl"],
    "10-risk-management.md": ["rsk"],
    "11-payout-system.md": ["pay"],
    "12-checkout-billing.md": ["chk"],
    "13-kyc.md": ["kyc"],
    "14-notifications.md": ["not"],
    "15-documents.md": ["doc"],
    "16-trader-dashboard.md": ["td"],
    "17-admin-panel.md": ["adm"],
    "19-analytics.md": ["ana"],
    "21-console.md": ["con"],
}

NO_V1_NOTE = {
    "18-support.md": "SUP is not in the V1 execution sheet (V2 scope).",
    "20-crm.md": "CRM is not in the V1 execution sheet (V2 scope).",
    "22-billing.md": "BIL (platform revenue) is not in the V1 execution sheet (V3 scope — V1 tenants are invoiced manually per 00 §4).",
    "23-affiliates.md": "AFF is not in the V1 execution sheet (V2 scope).",
    "24-cms-competitions.md": "CMS/CMP is not in the V1 execution sheet (V2/V3 scope).",
    "25-migration.md": "MIG is not in the V1 execution sheet (V2 scope — the FunderBlu onboarding program).",
    "26-mobile-apps.md": "MOB/JRN/EDU/CHT is not in the V1 execution sheet (V3 scope).",
    "27-ecosystem.md": "SDK/DVP/TRD/PLT/CS is not in the V1 execution sheet (V2/V3 scope; API keys themselves are V2 per AUTH-21).",
}

def parse_api(path):
    """Return (endpoints, has_http, internal_notes) from an api contract file."""
    text = open(path).read()
    # split into endpoint blocks: '### METHOD /path' up to next '###' or '## '
    blocks = re.split(r"\n### ", text)
    eps, has_http = [], False
    for b in blocks[1:]:
        lines = b.splitlines()
        head = lines[0].strip()
        m = re.match(r"^([A-Z]+) (\S+)$", head)
        if not m:
            continue
        has_http = True
        meth, p = m.group(1), m.group(2)
        body = "\n".join(lines[1:])
        def field(name):
            fm = re.search(rf"^{name}: (.+)$", body, re.M)
            return fm.group(1).strip() if fm else ""
        auth = field("Auth")
        perm = field("Permission")
        idem = field("Idempotency")
        errs = re.findall(r"^- `([a-z0-9_.]+)` \d{3}", body, re.M)
        # non-endpoint '###' sections (workers, session semantics...)
        eps.append((meth, p, auth, perm, idem, errs))
    return eps, has_http

def v1_table(name, eps):
    rows = ["| Method + path | Auth | Permission | Idempotency | V1 errors |",
            "|---|---|---|---|---|"]
    for meth, p, auth, perm, idem, errs in eps:
        perm = perm or "—"
        idem = idem.split(" #")[0].strip()
        errs = ", ".join(f"`{e}`" for e in errs) or "standard"
        rows.append(f"| `{meth} {p}` | {auth} | {perm} | {idem} | {errs} |")
    return "\n".join(rows)

def main():
    for doc, names in MAP.items():
        path = os.path.join(DOCS, doc)
        text = open(path).read()
        m = re.search(r"^## 7\. API endpoints\n(.*?)(?=^## 8\. )", text, re.S | re.M)
        if not m:
            print(f"SKIP {doc} (no §7)"); continue
        old = m.group(1).strip()
        parts = []
        for name in names:
            apif = os.path.join(API, f"{name}.md")
            eps, has_http = parse_api(apif)
            if has_http:
                parts.append(
                    f"### 7.{len(parts)+1} V1 baseline — `{name}` "
                    f"(authoritative: `contracts/api/{name}.md`)\n\n"
                    + v1_table(name, eps)
                    + "\n\nScope, request/response shapes, and per-endpoint notes: "
                    + f"`contracts/api/{name}.md` (field values in the research are "
                    "owner TODOs until contract freeze; canonical JSON is fixed at "
                    "freeze, per the docs/99 §12 rules)."
                )
            else:
                if name == "gw":
                    body = (
                        "**In-app middleware contract, not endpoints** — the "
                        "gateway is in-app middleware behind Cloudflare (no "
                        "standalone gateway product). `contracts/api/gw.md` "
                        "defines the cross-cutting request/response contract "
                        "every module inherits: route groups (GW-01), tenant "
                        "resolution (GW-02), authentication (GW-03), "
                        "authorization via `resource.action` keys (GW-04), "
                        "rate limiting (GW-05), idempotency (GW-12), and the "
                        "error envelope (GW-18 — `code`, `message`, "
                        "`correlation_id`)."
                    )
                else:
                    body = (
                        "**No HTTP surface in V1** — this is an internal/"
                        "service contract. The internal contracts (what other "
                        "modules call, what workers run, what is enforced) are "
                        "in `contracts/api/" + name + ".md`."
                    )
                parts.append(
                    f"### 7.{len(parts)+1} V1 baseline — `{name}` "
                    f"(see `contracts/api/{name}.md`)\n\n" + body
                )
        new_sec = (
            "\n".join(parts)
            + f"\n\n### 7.{len(parts)+1} Extended (post-V1) surface — provisional\n\n"
            "> Not in the V1 execution sheet. Design-level; paths beyond the V1 "
            "baseline are provisional until the URL-plan decision "
            "(`contracts/api/gw.md`, open question). Shown for platform "
            "completeness (V2/V3 phases, docs/99).\n\n" + old
        )
        text = text[:m.start(1)] + new_sec + "\n" + text[m.end(1):]
        open(path, "w").write(text)
        print(f"OK {doc}: {len(eps)} V1 endpoints")
    # modules without a V1 file: add a scope note at the top of §7
    for doc, note in NO_V1_NOTE.items():
        path = os.path.join(DOCS, doc)
        text = open(path).read()
        m = re.search(r"^## 7\. API endpoints\n", text, re.M)
        if not m:
            print(f"SKIP {doc} (no §7)"); continue
        if "no V1 baseline" in text[:text.find("## 8")]:
            continue
        insert = (
            f"> **Scope note:** {note} There is no V1 baseline contract for this "
            "module; the surface below is design-level (post-V1, docs/99) and "
            "provisional until its phase's contract freeze.\n\n"
        )
        text = text[:m.end()] + insert + text[m.end():]
        open(path, "w").write(text)
        print(f"NOTE {doc}")

if __name__ == "__main__":
    main()

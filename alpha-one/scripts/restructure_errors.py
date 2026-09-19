#!/usr/bin/env python3
"""Restructure each module doc's §6 (Error taxonomy):
  - prepend the V1 baseline codes from contracts/errors/taxonomy.md (the
    PRD-derived dotted `domain.action` codes, authoritative);
  - convert the doc's pre-existing (extended) codes from legacy
    MODULE_TOKEN to the same dotted convention (mechanical, bijective);
  - drop extended rows that duplicate a V1 baseline code (baseline wins)."""
import os, re

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
DOCS = os.path.join(ROOT, "docs")
TAX = os.path.join(ROOT, "contracts", "errors", "taxonomy.md")

# taxonomy section heading -> (doc file, title used in the doc)
SEC_MAP = {
    "Gateway / platform (GW)": ("04-gateway-events.md", "GW"),
    "Auth (AUTH)": ("02-identity-access.md", "AUTH"),
    "Tenant (TEN)": ("03-tenant-management.md", "TEN"),
    "Checkout (CHK)": ("12-checkout-billing.md", "CHK"),
    "Payout (PAY)": ("11-payout-system.md", "PAY"),
    "KYC (KYC)": ("13-kyc.md", "KYC"),
    "Evaluation (EVL)": ("09-evaluation-engine.md", "EVL"),
    "Console (CON)": ("21-console.md", "CON"),
    "Risk (RSK)": ("10-risk-management.md", "RSK"),
    "Documents (DOC)": ("15-documents.md", "DOC"),
}

def parse_taxonomy():
    text = open(TAX).read()
    secs = {}
    heads = list(re.finditer(r"^## (.+?)\n", text, re.M))
    for i, h in enumerate(heads):
        title = h.group(1)
        if title not in SEC_MAP:
            continue
        body = text[h.end(): heads[i + 1].start() if i + 1 < len(heads) else len(text)]
        rows = re.findall(
            r"^\| `([a-z0-9_.]+)` \| (\d{3}(?:/\d{3})?) \| (.+?) \| (.+?) \| (.+?) \|$",
            body, re.M)
        secs[title] = rows
    return secs

def dotted(tok):
    return tok.replace("_", ".", 1).lower()

def main():
    secs = parse_taxonomy()
    all_v1 = set()
    for rows in secs.values():
        for r in rows:
            all_v1.add(r[0])

    per_doc = {}
    for title, (doc, mod) in SEC_MAP.items():
        rows = secs.get(title, [])
        per_doc.setdefault(doc, []).append((mod, rows))
    # the account.* rows live in the EVL section but are LCC-owned (Module column)
    acct = [(r[0], r[1], r[2], r[3], r[4]) for r in secs.get("Evaluation (EVL)", [])
            if r[0].startswith("account.")]
    if acct:
        per_doc.setdefault("07-account-lifecycle.md", []).append(
            ("LCC", acct))

    all_docs = sorted(os.path.join(DOCS, f) for f in os.listdir(DOCS)
                      if f.endswith(".md") and f[:2].isdigit())
    for path in all_docs:
        doc = os.path.basename(path)
        if doc in ("30-error-taxonomy.md", "31-event-catalog.md",
                   "32-database-design.md", "99-development-phases.md"):
            continue
        text = open(path).read()
        m = re.search(r"^## 6\. Error taxonomy\n(.*?)(?=^## 7\. )", text, re.S | re.M)
        if not m:
            print(f"SKIP {doc}"); continue
        old = m.group(1)
        entries = per_doc.get(doc, [])
        v1_blocks = []
        if entries:
            for mod, rows in entries:
                tb = ["| Code | HTTP | Meaning | User-facing message |",
                      "|---|---|---|---|"]
                for code, http, meaning, msg, module in rows:
                    meaning = meaning.replace("|", "\\|")
                    msg = msg.replace("|", "\\|")
                    tb.append(f"| `{code}` | {http} | {meaning} | {msg} |")
                v1_blocks.append(
                    "### 6.1 V1 baseline codes — authoritative\n\n"
                    "From `contracts/errors/taxonomy.md` (the V1 execution "
                    f"sheet; module {mod}). These are the exact codes the V1 "
                    "surfaces return; the envelope is GW-18 (`code`, "
                    "`message`, `correlation_id`).\n\n" + "\n".join(tb))
        # convert legacy extended codes to dotted + fold baseline duplicates
        v1_here = {r[0] for _, rows in entries for r in rows}
        out_lines, dropped, converted = [], 0, 0
        for line in old.splitlines():
            lm = re.match(r"^(\| `)([A-Z][A-Z0-9]*_[A-Z0-9_]+)(` \| )", line)
            if lm:
                newcode = dotted(lm.group(2))
                if newcode in v1_here:
                    dropped += 1
                    continue
                line = lm.group(1) + newcode + lm.group(3) + line[lm.end():]
                converted += 1
            out_lines.append(line)
        ext = "\n".join(out_lines)
        ext = re.sub(
            r"^Module codes.*$",
            "### 6.2 Extended (post-V1) codes — design-level\n\n"
            "Below the V1 baseline; names converted to the GW-18 dotted "
            "convention. Rows duplicating a V1 baseline code were folded "
            "into the baseline table.",
            ext, count=1, flags=re.M)
        new_sec = (v1_blocks[0] + "\n\n" + ext) if v1_blocks else ext
        text = text[:m.start(1)] + new_sec + "\n" + text[m.end(1):]
        open(path, "w").write(text)
        n_v1 = sum(len(r) for _, r in entries)
        print(f"OK {doc}: +{n_v1} V1 codes, {converted} converted, "
              f"{dropped} duplicates folded")

if __name__ == "__main__":
    main()

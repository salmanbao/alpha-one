#!/usr/bin/env python3
"""Split docs/32-database-design.md's DDL into per-module SQL files under
contracts/data/schemas/ (referenced by the V1 contract research, e.g.
api/evl.md's `data/schemas/accounts.sql`). docs/32 stays the source of truth;
this is a mechanical split of its sql fences, grouped by module section."""
import os, re

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "docs", "32-database-design.md")
OUT = os.path.join(ROOT, "contracts", "data", "schemas")

MOD_RE = re.compile(r"^### (\d{2}) — (\S+) \(from (.+?) §9\)", re.M)

def main():
    text = open(SRC).read()
    matches = list(MOD_RE.finditer(text))
    os.makedirs(OUT, exist_ok=True)
    written = 0
    for i, m in enumerate(matches):
        num, mod, srcdoc = m.group(1), m.group(2), m.group(3)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        section = text[start:end]
        blocks = re.findall(r"```sql\n(.*?)```", section, re.S)
        sql = "\n\n".join(b.strip() for b in blocks)
        if not sql.strip():
            continue
        header = (
            f"-- {num} — {mod}: DDL split from docs/32-database-design.md "
            f"(source: {srcdoc} §9). docs/32 is the source of truth; delivered "
            f"through versioned migrations (OPS-06, expand-contract discipline).\n"
        )
        path = os.path.join(OUT, f"{num}-{re.sub(r'[^a-z0-9]+', '-', mod.lower()).strip('-')}.sql")
        with open(path, "w") as f:
            f.write(header + sql + "\n")
        written += 1
        print(f"  {os.path.basename(path)}: {sql.count('CREATE TABLE')} tables")
    print(f"wrote {written} schema files to {OUT}")

if __name__ == "__main__":
    main()

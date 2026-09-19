#!/usr/bin/env python3
"""Complete the contracts/ pack for post-V1 modules + extended registries.

What this script does (all output is marked PROVISIONAL / design-level; the V1
baseline files are never rewritten, only appended to in clearly-marked sections):
  1. contracts/api/<mod>.md for the 16 modules with no V1 HTTP contract
     (SUP, CRM, BIL, AFF, CMS, CMP, MIG, MOB, JRN, EDU, CHT, SDK, DVP, TRD, PLT, CS)
     from each module doc's §7 + the PRD backlog (scripts/prd-backlog.json).
  2. contracts/events/examples/<topic>/<event>.v1.example.json — one illustrative
     example instance per extended event schema (test-fixture scaffolding).
  3. Appends the extended (post-V1) error registry from docs/30 to
     contracts/errors/taxonomy.md (V1 baseline section untouched).
  4. Appends provisional permission keys mined from module docs §7 + api specs to
     contracts/permissions/registry.md (V1 registry untouched).
  5. Prints a requirement-coverage cross-check: every module doc's
     "Requirement coverage" claim vs the parsed PRD backlog.

Provenance:
  - scripts/prd-backlog.json: parsed from uploads/Alpha One PRD.pdf
    (master backlog row-starts `MOD-NN D[1-5]` + the workbook registers; 1020 rows).
    Re-parse if the PRD changes (scripts/parse_prd_workbook.py, which also emits
    scripts/prd-workbook.json — the full sheet mirror).
  - Module docs: alpha-one/docs/*.md (authoritative prose; this script copies §7 verbatim).

Usage:  python3 scripts/complete_contracts_pack.py [--check-only]
"""
import json, re, sys, pathlib, hashlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
CON = ROOT / "contracts"
PRD = json.load(open(ROOT / "scripts" / "prd-backlog.json"))
CHECK_ONLY = "--check-only" in sys.argv
TODAY = "2026-09-19"

ULID_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"

def fake_ulid(seed: str) -> str:
    h = hashlib.sha256(seed.encode()).digest()
    n = int.from_bytes(h, "big")
    out = ""
    for _ in range(26):
        out = ULID_ALPHABET[n % 32] + out
        n //= 32
    return out

# ---------------------------------------------------------------- module table
# mod -> (doc file, section7 index within doc, title, audience/auth note)
MODULES = {
    "sup": ("18-support.md", 0, "Support Inbox", "Trader (own tickets) + staff (queue). Trader routes identity-scoped; staff routes require support role."),
    "crm": ("20-crm.md", 0, "CRM & Communications", "Staff (Tenant Admin / marketing role). No trader-facing surface except consent + unsubscribe."),
    "bil": ("22-billing.md", 0, "Tenant Billing", "Platform staff via CON (invoicing, dunning) + tenant read-only (own invoices, usage)."),
    "aff": ("23-affiliates.md", 0, "Affiliate System", "Affiliates (trader-realm section) + staff (program config, approvals)."),
    "cms": ("24-cms-competitions.md", 0, "Website / CMS (Part A)", "Public (published site) + staff (editor, Tenant Admin)."),
    "cmp": ("24-cms-competitions.md", 1, "Competitions & Gamification (Part B)", "Trader (enter, leaderboard) + staff (create, score, prize)."),
    "mig": ("25-migration.md", 0, "Migration Tooling", "Super Admin only (CON). Tenant staff get read-only cutover status."),
    "mob": ("26-mobile-apps.md", 0, "Mobile App (Part A)", "Trader (mobile session; same API as TD, no mobile-specific surface per Out Of Scope)."),
    "jrn": ("26-mobile-apps.md", 1, "Trading Journal (Part B)", "Trader (own journal) + optional staff aggregate reads (never entry content without consent)."),
    "edu": ("26-mobile-apps.md", 2, "Education Hub (Part C)", "Trader (learn) + staff (publish, Tenant Admin)."),
    "cht": ("26-mobile-apps.md", 3, "Community & Live Chat (Part D)", "Trader (community) + staff (moderation)."),
    "sdk": ("27-ecosystem.md", 0, "BYO Integration SDK (Part A, public API)", "External integrators (public API keys, UnKey-backed in V2+; ref-indirected ids)."),
    "dvp": ("27-ecosystem.md", 0, "Developer Portal (Part A, portal API)", "Developers (firm:developer session on dev portal; 2FA on key create/revoke)."),
    "trd": ("27-ecosystem.md", 1, "Advanced Trading (Part B)", "Trader (copy, backtest, paper, algos) + staff (venue config)."),
    "plt": (None, -1, "Platform Operations (Part C.1)", "Platform staff via CON. No dedicated HTTP surface — console screens over module APIs + jobs."),
    "cs": (None, -1, "Customer Success (Part C.2)", "Platform staff via CON. No dedicated HTTP surface — console screens over module APIs + jobs."),
}

def section7(doc: str, index: int) -> str:
    text = open(DOCS / doc).read()
    starts = [m.start() for m in re.finditer(r"^## 7\.", text, re.M)]
    if index >= len(starts):
        return ""
    s = text.index("\n", starts[index]) + 1
    m = re.search(r"^## 8\.", text[s:], re.M)
    body = text[s:s + m.start()] if m else text[s:s + 6000]
    return body.strip() + "\n"

def prd_rows(mod: str):
    mod = mod.upper()
    out = []
    for k, v in PRD.items():
        if k.split("-")[0] == mod:
            try: n = int(k.split("-")[1])
            except ValueError: continue
            out.append((n, k, v))
    return sorted(out)

def scope_table(mod: str) -> str:
    rows = prd_rows(mod)
    lines = ["| Req | Feature | Release | Pri | Owner | User story (abridged) |",
             "|---|---|---|---|---|---|"]
    for n, k, v in rows:
        story = re.sub(r"\s+", " ", v.get("story", "")).strip()
        story = (story[:130] + "…") if len(story) > 130 else story
        story = story.replace("|", "/")
        feat = re.sub(r"\s+", " ", v.get("feat", "")).strip().replace("|", "/")[:60]
        lines.append(f"| `{k}` | {feat} | {v['rel']} | {v['pri']} | {v['own']} | {story} |")
    return "\n".join(lines)

AUTH_BOILER = """## Auth

{auth_note} All routes sit in the GW chain (docs/04 §3.1): tenant resolution →
authn → authz (`resource.action` key per route) → rate limit → entitlement gate →
idempotency → audit. Error envelope per GW-18 (`code`, `message`, `correlation_id`).

## Tenant resolution

From domain (GW-02) for web routes; from the API key for machine routes (key wins
over any header); `X-Tenant-Id` header for internal service tokens only. Unknown
host/key → `404 tenant.not_found` (no-oracle rule, docs/04 §6).

## Permissions

{perm_note}

## Idempotency

Mutating requests accept an `Idempotency-Key` header per GW-12 (24 h TTL, scope =
method+path+key). Retries MUST NOT create duplicate resources.
"""

OPEN_QUESTIONS = """## Open contract questions

- Paths, methods, and field names below are PROVISIONAL until this module's phase
  freeze (docs/99 §12) — additive changes only after freeze; breaking changes get
  `/v2/` + the 12-month deprecation rule for public surfaces.
- Permission keys: the V1 registry (`permissions/registry.md`) is binding; keys used
  below beyond it are provisional and join the registry at freeze.
- Error codes: V1 baseline codes are binding (`errors/taxonomy.md`); extended codes
  follow the GW-18 dotted convention and freeze with the module (docs/30).
"""

def build_api(mod: str, doc: str, idx: int, title: str, auth_note: str) -> str:
    mod_up = mod.upper()
    body7 = section7(doc, idx) if doc else ""
    releases = sorted({v["rel"] for _, _, v in prd_rows(mod)})
    rel_str = ", ".join(releases) if releases else "TBD"
    perm_note = ("No dedicated permission keys beyond the V1 registry are fixed yet — "
                 "keys are proposed in the module doc's §7 and freeze with the module.")
    if mod in ("sdk", "dvp"):
        perm_note = ("Public scopes (e.g. `trades:read`) + portal keys; full scope catalog "
                     "freezes with the V3 public API (docs/27 Part A §3.1).")
    deriv = f"Derived from `docs/{doc}` §7 + PRD {mod_up}-NN ({rel_str})." if doc else \
        f"No §7 in the module doc (console-only module); scope from PRD {mod_up}-NN ({rel_str})."
    out = [f"# {title} API Contract ({mod_up})",
           "",
           "Status: PROVISIONAL (post-V1, design-level)",
           "Owner: TBD",
           "Version: v1",
           f"Last updated: {TODAY}",
           "",
           deriv + " Nothing here is final until that phase's contract freeze (docs/99 §12).",
           "",
           "## Scope",
           "",
           f"PRD module **{mod_up}** ({len(prd_rows(mod))} requirements). Abridged backlog:",
           "",
           scope_table(mod),
           "",
           AUTH_BOILER.format(auth_note=auth_note, perm_note=perm_note),
           "## Endpoints (provisional)",
           ""]
    if body7:
        out.append(f"> Copied verbatim from `docs/{doc}` §7 on {TODAY} — the module doc "
                   "is authoritative if they drift; regenerate with "
                   "`python3 scripts/complete_contracts_pack.py`.")
        out.append("")
        out.append(body7)
    else:
        out.append("No dedicated HTTP surface: this module is console screens (CON) over "
                   "other modules' APIs plus background jobs. See the module doc Part C.")
        out.append("")
    out.append(OPEN_QUESTIONS)
    return "\n".join(out)

# ------------------------------------------------------- 2. event examples
def gen_examples():
    ext = CON / "events" / "extended"
    out_root = CON / "events" / "examples"
    count = 0
    for schema_file in sorted(ext.glob("*.schema.json")):
        schema = json.load(open(schema_file))
        defs = schema.get("$defs", {})
        topic = schema_file.stem
        for def_name, d in defs.items():
            if def_name == "EventEnvelope":
                continue
            # event name from allOf const
            ev_name = None
            desc = ""
            for part in d.get("allOf", []):
                props = part.get("properties", {})
                if "type" in props and "const" in props["type"]:
                    ev_name = props["type"]["const"]
                if "payload" in props:
                    desc = props["payload"].get("description", "")
            if not ev_name:
                ev_name = f"{topic}.{def_name}"
            ex = {
                "_note": ("ILLUSTRATIVE example for the extended (post-V1) event "
                          f"`{ev_name}` — envelope per EVT-03; payload fields are "
                          "provisional until that phase's freeze. Canonical schema: "
                          f"contracts/events/extended/{schema_file.name} ($defs/{def_name}). "
                          + re.sub(r"\s+", " ", desc)[:300]),
                "id": fake_ulid(ev_name + ":id"),
                "type": ev_name,
                "version": 1,
                "tenant_id": fake_ulid(ev_name + ":tenant"),
                "occurred_at": 1758278400000,
                "payload": {},
            }
            dest = out_root / topic / f"{ev_name}.v1.example.json"
            if (CON / "events" / "payloads" / f"{ev_name}.v1.json").exists():
                continue  # promoted to the V1 catalog (docs/50 D28) — example is maintained with the payload schema
            if not CHECK_ONLY:
                dest.parent.mkdir(parents=True, exist_ok=True)
                json.dump(ex, open(dest, "w"), indent=2)
                open(dest, "a").write("\n")
            count += 1
    readme = out_root / "README.md"
    if not CHECK_ONLY:
        readme.write_text(
            "# Extended event examples (illustrative fixtures)\n\n"
            f"One example instance per extended (post-V1) event schema in `../extended/` "
            f"({count} files, generated {TODAY} by `scripts/complete_contracts_pack.py`).\n\n"
            "- **Envelope** fields (`id`, `type`, `version`, `tenant_id`, `occurred_at`) "
            "follow EVT-03 and are stable.\n"
            "- **`payload` is intentionally `{}`**: per-event payload fields are provisional "
            "until that phase's contract freeze (docs/99 §12). Use these files as consumer-test "
            "scaffolding: copy, fill the payload from the module doc's §4/§8, and assert envelope "
            "handling + idempotency-by-`id`.\n"
            "- V1 baseline payloads (with fixed fields) live in `../payloads/`.\n"
        )
    return count

# ------------------------------------------------------- 3. errors extension
def extend_errors():
    doc30 = open(DOCS / "30-error-taxonomy.md").read()
    # sections: ### NN — MOD... ; rows: | `code` | HTTP | Meaning | Tier |
    sections = re.split(r"^### (\d+) — (.+)$", doc30, flags=re.M)
    # sections[0] preamble, then triples (nn, mods, body)
    ext_by_mod = {}
    for i in range(1, len(sections), 3):
        mods = sections[i + 1].strip()
        body = sections[i + 2]
        rows = []
        for m in re.finditer(r"^\| `([^`]+)` \| (\d{3}|—) \| (.*?) \| (V1|ext) \|$", body, re.M):
            code, http, meaning, tier = m.groups()
            if tier == "ext":
                rows.append((code, http, meaning.strip()))
        if rows:
            ext_by_mod[mods] = rows
    tax_path = CON / "errors" / "taxonomy.md"
    tax = open(tax_path).read()
    if "## Extended (post-V1) registry" in tax:
        return 0  # already extended
    lines = ["", "", "---", "",
             "## Extended (post-V1) registry (design-level, provisional)",
             "",
             f"> Appended {TODAY} by `scripts/complete_contracts_pack.py` from the master "
             "registry (docs/30-error-taxonomy.md §2, Tier=ext). The V1 baseline above is "
             "untouched and remains the binding contract. Extended codes follow the GW-18 "
             "dotted convention; each freezes with its module's phase (docs/99 §12). "
             "docs/30 is the master — regenerate on drift.",
             ""]
    total = 0
    for mods, rows in ext_by_mod.items():
        lines.append(f"### {mods} (extended)")
        lines.append("")
        lines.append("| Code | HTTP | Meaning |")
        lines.append("|---|---|---|")
        for code, http, meaning in rows:
            lines.append(f"| `{code}` | {http} | {meaning} |")
            total += 1
        lines.append("")
    if not CHECK_ONLY:
        open(tax_path, "w").write(tax.rstrip() + "\n" + "\n".join(lines))
    return total

# ------------------------------------------------------- 4. permissions extension
DOTTED = re.compile(r"`([a-z][a-z0-9_]*\.[a-z][a-z0-9_]+(?:\.[a-z][a-z0-9_]+)?)`")

def mine_permissions():
    """Mine permission keys from docs §7 tables' Permission columns + api specs."""
    found = {}  # key -> (module, source)
    # (a) docs §7 permission columns
    for doc_file in sorted(DOCS.glob("*.md")):
        text = open(doc_file).read()
        for m in re.finditer(r"^## 7\..*?(?=^## 8\.|\Z)", text, re.M | re.S):
            sec = m.group(0)
            cur_header = None
            for line in sec.splitlines():
                if line.startswith("|") and "Permission" in line and "---" not in line:
                    cur_header = [h.strip().lower() for h in line.strip().strip("|").split("|")]
                    continue
                if cur_header and line.startswith("|") and "---" not in line:
                    cells = [c.strip() for c in line.strip().strip("|").split("|")]
                    for idx, h in enumerate(cur_header):
                        if "permission" in h and idx < len(cells):
                            for k in DOTTED.findall(cells[idx]):
                                if k not in ("resource.action",):
                                    found.setdefault(k, (doc_file.stem, f"docs/{doc_file.name} §7"))
                if line.startswith("## "):
                    cur_header = None
    # (b) api specs' Permissions sections
    for api_file in sorted((CON / "api").glob("*.md")):
        text = open(api_file).read()
        m = re.search(r"^## Permissions$(.*?)(?=^## |\Z)", text, re.M | re.S)
        if m:
            for k in DOTTED.findall(m.group(1)):
                if k not in ("resource.action",):
                    found.setdefault(k, (api_file.stem, f"contracts/api/{api_file.name}"))
    # subtract error codes (docs/30 code set)
    doc30 = open(DOCS / "30-error-taxonomy.md").read()
    err_codes = set(re.findall(r"^\| `([^`]+)` \| \d{3} \|", doc30, re.M))
    found = {k: v for k, v in found.items() if k not in err_codes}
    return found

def extend_permissions(mined):
    reg_path = CON / "permissions" / "registry.md"
    reg = open(reg_path).read()
    if "## Extended (provisional)" in reg:
        return 0
    existing = set(re.findall(r"^\| `([^`]+)` \|", reg, re.M))
    new = {k: v for k, v in mined.items() if k not in existing}
    lines = ["", "", "---", "",
             "## Extended (provisional) keys (design-level)",
             "",
             f"> Appended {TODAY} by `scripts/complete_contracts_pack.py`, mined from module "
             "docs §7 endpoint tables + api specs. The V1 registry above is untouched and "
             "remains binding. Each key freezes with its module's phase (docs/99 §12); "
             "role bindings are fixed at freeze (AUTH-12 × AUTH-13 open question).",
             "",
             "| Permission key | Module (source) | Source |",
             "|---|---|---|"]
    for k in sorted(new):
        mod, src = new[k]
        lines.append(f"| `{k}` | {mod} | {src} |")
    lines.append("")
    if not CHECK_ONLY:
        open(reg_path, "w").write(reg.rstrip() + "\n" + "\n".join(lines))
    return len(new)

# ------------------------------------------------------- 5. coverage check
def expand_req_list(mod_hint, text):
    """Expand shorthand like `MOD-01,04,07`, `01..12`, `02..08,12..20` into MOD-NN set.
    Bare numbers expand ONLY inside backticked spans (prose numbers like "V1.0" or
    "remaining 33" must not become phantom reqs); explicit MOD-NN match anywhere."""
    ids = set()
    for m in re.finditer(r"\b([A-Z]{2,4})-(\d{1,3})\b", text):
        ids.add("%s-%02d" % (m.group(1), int(m.group(2))))
    for m in re.finditer(r"\b([A-Z]{2,4})-(\d{1,3})\.\.(\d{1,3})\b", text):
        for n in range(int(m.group(2)), int(m.group(3)) + 1):
            ids.add("%s-%02d" % (m.group(1), n))
    cur = mod_hint
    for span in re.finditer(r"`([^`]*)`", text):
        body = span.group(1)
        before = text[:span.start()]
        m_space = re.search(r"\b([A-Z]{2,4})\s+$", before)
        if m_space:
            cur = m_space.group(1)
        else:
            cands = list(re.finditer(r"\b([A-Z]{2,4})-\d", before))
            if cands:
                cur = cands[-1].group(1)
        for m in re.finditer(r"(?:^|[,\s\n])([A-Z]{2,4}-)?(\d{1,3})(\.\.(\d{1,3}))?", body):
            pr, a, _, b = m.group(1), m.group(2), m.group(3), m.group(4)
            if pr:
                cur = pr[:-1]
            if cur in ("V1", "V2", "V3", "??"):
                continue
            if b:
                for n in range(int(a), int(b) + 1):
                    ids.add("%s-%02d" % (cur, n))
            else:
                ids.add("%s-%02d" % (cur, int(a)))
    return ids

def coverage_check():
    print("\n=== 5. Requirement-coverage cross-check (docs vs PRD) ===")
    issues = 0
    for doc_file in sorted(DOCS.glob("*.md")):
        text = open(doc_file).read()
        ms = list(re.finditer(r"Requirement coverage:(.*?)(?:\n\n|\Z)", text, re.S))
        if not ms:
            continue
        claim = "\n".join(m.group(0) for m in ms)
        # module hint from filename/doc title
        hint_m = re.search(r"^# \d+ — ([A-Z/· ]+)", text, re.M)
        # per-module: expand and compare release attribution is complex; do set-level check
        claimed = expand_req_list("??", claim)
        # filter to real PRD ids for modules mentioned in claim
        mods_in_claim = set(re.findall(r"\b([A-Z]{2,4})-\d", claim)) | set(
            re.findall(r"\b([A-Z]{2,4})\s+`", claim))
        if not mods_in_claim:
            continue
        prd_ids = {k for k in PRD if k.split("-")[0] in mods_in_claim}
        missing = sorted(prd_ids - claimed, key=lambda x: (x.split("-")[0], int(x.split("-")[1])))
        phantom = sorted(claimed - set(PRD), key=lambda x: (x.split("-")[0], int(x.split("-")[1]) if x.split("-")[1].isdigit() else 0))
        # release attribution: text between markers belongs to the FOLLOWING marker
        # (claims read "`A,B` (V1), `C,D` (V2)"): segment = text since previous ")" .
        markers = list(re.finditer(r"\((V1\.1/V2|V1-Core/Plus|V1-Core|V1\.0|V1\.1|V1|V2\.0|V2|V3\.0|V3)[^)]*\)", claim))
        seg_issues = []
        prev_end = 0
        for seg_m in markers:
            tag = seg_m.group(1)
            if tag in ("V1.1/V2", "V2.0", "V2"):
                want = "V2"
            elif tag in ("V3.0", "V3"):
                want = "V3"
            else:
                want = "V1"
            seg = claim[prev_end:seg_m.start()]
            prev_end = seg_m.end()
            # inherit module prefix: seed from nearest MOD- in preceding text
            seed = re.findall(r"\b([A-Z]{2,4})(?:-\d|\s+`)", claim[:seg_m.start()])
            seg_ids = expand_req_list(seed[-1] if seed else "??", seg)
            if tag == "V1.1/V2":
                pass  # mixed marker: accept V1.1 or V2.0 below via want=V2 + V1.1 allowance
            for rid in seg_ids:
                if rid in PRD:
                    actual = PRD[rid]["rel"]
                    ok = (want == "V1" and actual in ("V1.0", "V1.1")) or (want == "V2" and actual in ("V2.0", "V1.1")) or (want == "V3" and actual == "V3.0")
                    if not ok:
                        seg_issues.append(f"{rid} claimed {want} but PRD={actual}")
        if missing or phantom or seg_issues:
            issues += 1
            print(f"\n-- docs/{doc_file.name} --")
            if missing: print(f"  PRD reqs NOT claimed ({len(missing)}): {', '.join(missing[:25])}" + ("…" if len(missing) > 25 else ""))
            if phantom: print(f"  Claimed but NOT in PRD ({len(phantom)}): {', '.join(phantom[:25])}" + ("…" if len(phantom) > 25 else ""))
            for s in seg_issues[:12]: print(f"  ATTRIBUTION: {s}")
            if len(seg_issues) > 12: print(f"  … +{len(seg_issues)-12} more attribution notes")
    # 5b. every PRD module must be claimed somewhere: the legacy extractor once
    # lost PLT-01..08 and nothing noticed, because an unclaimed module simply
    # had no coverage line to compare.
    all_claims = "\n".join(open(f).read() for f in sorted(DOCS.glob("*.md")))
    prd_modules = sorted({k.split("-")[0] for k in PRD})
    unclaimed = [m for m in prd_modules
                 if not re.search(r"\b" + re.escape(m) + r"-\d|\b" + re.escape(m) + r"\b[^\n]{0,3}module", all_claims, re.I)]
    if unclaimed:
        issues += 1
        print(f"\n-- module coverage --\n  PRD modules never claimed by a doc: {', '.join(unclaimed)}")
    if issues == 0:
        print("All module docs' coverage claims match the PRD backlog; "
              f"all {len(prd_modules)} PRD modules are covered.")
    return issues

def main():
    print("=== 1. Generating contracts/api/*.md (16 post-V1 modules) ===")
    for mod, (doc, idx, title, auth_note) in MODULES.items():
        dest = CON / "api" / f"{mod}.md"
        if dest.exists() and not CHECK_ONLY:
            print(f"  SKIP {dest.name} (exists)")
            continue
        content = build_api(mod, doc, idx, title, auth_note)
        if not CHECK_ONLY:
            dest.write_text(content)
        print(f"  {'[check] ' if CHECK_ONLY else ''}WROTE {dest.name} ({len(content.splitlines())} lines)")
    print("\n=== 2. Generating extended event examples ===")
    n = gen_examples()
    print(f"  {'[check] ' if CHECK_ONLY else ''}{n} example files under contracts/events/examples/")
    print("\n=== 3. Extending contracts/errors/taxonomy.md ===")
    n = extend_errors()
    print(f"  {'[check] ' if CHECK_ONLY else ''}{n} extended codes appended (0 = already present)")
    print("\n=== 4. Extending contracts/permissions/registry.md ===")
    mined = mine_permissions()
    print(f"  mined {len(mined)} candidate keys")
    for k in sorted(mined):
        print(f"    {k}  ({mined[k][0]}, {mined[k][1]})")
    n = extend_permissions(mined)
    print(f"  {'[check] ' if CHECK_ONLY else ''}{n} new keys appended (0 = already present)")
    coverage_check()

if __name__ == "__main__":
    main()

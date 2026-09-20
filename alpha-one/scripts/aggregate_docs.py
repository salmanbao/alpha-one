#!/usr/bin/env python3
"""Aggregate module docs (02-27) into cross-cutting docs 30/31/32.
30: error-code registry (mechanical, faithful to each doc's rows)
31: event catalog (by topic, producer=owning module)
32: master database schema (all SQL blocks, module-ordered)
"""
import re, pathlib, collections

ROOT = pathlib.Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"

MODULES = [
    ("02-identity-access.md",   "AUTH", "02"),
    ("03-tenant-management.md", "TEN",  "03"),
    ("04-gateway-events.md",    "GW+EVT","04"),
    ("05-ledger-audit.md",      "LED/AUD","05"),
    ("06-devops-deployment.md", "OPS",  "06"),
    ("07-account-lifecycle.md", "LCC",  "07"),
    ("08-trading-bridge.md",    "BRG",  "08"),
    ("09-evaluation-engine.md", "EVL",  "09"),
    ("10-risk-management.md",   "RSK",  "10"),
    ("11-payout-system.md",     "PAY",  "11"),
    ("12-checkout-billing.md", "CHK",  "12"),
    ("13-kyc.md",               "KYC",  "13"),
    ("14-notifications.md",     "NOT",  "14"),
    ("15-documents.md",         "DOC",  "15"),
    ("16-trader-dashboard.md",  "TD",   "16"),
    ("17-admin-panel.md",       "ADM",  "17"),
    ("18-support.md",           "SUP",  "18"),
    ("19-analytics.md",         "ANA",  "19"),
    ("20-crm.md",               "CRM",  "20"),
    ("21-console.md",           "CON",  "21"),
    ("22-billing.md",           "BIL",  "22"),
    ("23-affiliates.md",        "AFF",  "23"),
    ("24-cms-competitions.md",  "CMS/CMP","24"),
    ("25-migration.md",         "MIG",  "25"),
    ("26-mobile-apps.md",       "MOB/JRN/EDU/CHT","26"),
    ("27-ecosystem.md",         "SDK/DVP/TRD/PLT/CS","27"),
]

def cells(line):
    line = line.strip()
    if not (line.startswith("|") and line.endswith("|")):
        return None
    parts = [c.strip() for c in line[1:-1].split("|")]
    return parts

CODE_RE = re.compile(r"`([a-z][a-z0-9]*(?:\.[a-z][a-z0-9_]*)+)`")          # dotted codes
LEGACY_CODE_RE = re.compile(r"`([A-Z]{2,4}_[A-Z0-9_]+)`")                  # legacy tokens
EVENT_RE = re.compile(r"`([a-z][a-z0-9_]*\.[a-z][a-z0-9_.]*)`")            # dotted events
PASCAL_EVENT_RE = re.compile(r"`([A-Z][a-z]+(?:[A-Z][a-z0-9]*)*)`")        # AccountCreated, PayoutPaid, Suspended
HTTP_RE = re.compile(r"^\d{3}(?:/\d{3})?$")

def section(text, num):
    """Body of `## <num>. <anything>` up to the next `## ` heading."""
    m = re.search(rf"^## {num}\.[^\n]*\n(.*?)(?=^## )", text, re.S | re.M)
    return m.group(1) if m else ""

# ---------- doc 30: error registry ----------
def build_errors():
    """Scan only each doc's §6. 6.1 = V1 baseline rows (marked), the rest =
    extended. Returns (num, mod) -> [(code, http, meaning, v1)]."""
    out = collections.OrderedDict()
    for fname, mod, num in MODULES:
        text = (DOCS / fname).read_text()
        sec6 = section(text, "6")
        if not sec6:
            continue
        m61 = re.search(r"### 6\.1[^\n]*\n(.*?)(?=^### 6\.2|\Z)", sec6, re.S | re.M)
        v1_zone = m61.group(1) if m61 else ""
        seen = set()
        for line in sec6.splitlines():
            if not line.strip().startswith("|"):
                continue
            parts = cells(line)
            if parts is None or len(parts) < 2:
                continue
            if all(re.fullmatch(r":?-{2,}:?", c) for c in parts if c):
                continue
            cm = CODE_RE.search(parts[0]) or LEGACY_CODE_RE.search(parts[0])
            if not cm:
                continue
            code = cm.group(1)
            http = ""
            hm = re.match(r"(\d{3})", parts[1])
            if hm:
                http = hm.group(1)
            meaning_parts = parts[2:]
            meaning = " — ".join(p.strip().replace("\\|", "|") for p in meaning_parts
                                 if p.strip() not in ("/", "—", "-"))
            meaning = re.sub(r"\s+", " ", meaning).strip()
            if len(meaning) > 160:
                meaning = meaning[:157].rsplit(" ", 1)[0] + "..."
            v1 = line in v1_zone
            if code in seen:
                continue
            seen.add(code)
            out.setdefault((num, mod), []).append([code, http, meaning, v1])
    return out

# ---------- doc 31: event catalog ----------
def build_events():
    """Scan only each doc's §4. 4.1 = V1 baseline (Event | Producer | Consumers),
    4.2 = extended (Event | When | … | Consumers). PascalCase (AccountCreated)
    and dotted (order.paid) event names."""
    out = collections.OrderedDict()  # event -> [num, mod, when, consumers, v1]
    for fname, mod, num in MODULES:
        text = (DOCS / fname).read_text()
        sec4 = section(text, "4")
        if not sec4:
            continue
        m41 = re.search(r"### 4\.1[^\n]*\n(.*?)(?=^### 4\.2|\Z)", sec4, re.S | re.M)
        v1_zone = m41.group(1) if m41 else ""
        seen = set()
        for line in sec4.splitlines():
            if not line.strip().startswith("|"):
                continue
            parts = cells(line)
            if parts is None or len(parts) < 2:
                continue
            if all(re.fullmatch(r":?-{2,}:?", c) for c in parts if c):
                continue
            if parts[0].strip("` ") == "Event":
                continue
            cm = EVENT_RE.search(parts[0]) or PASCAL_EVENT_RE.search(parts[0])
            if not cm:
                continue
            ev = cm.group(1)
            if ev in ("dev.alphaone.example","trade.funderblu.com","details.metric",
                      "tickets.channel","traders_ro.lifecycle_stage","trader.ui_action",
                      "trader.read"):
                continue
            when = re.sub(r"\s+", " ", parts[1]).replace("`", "").strip()
            consumers = re.sub(r"\s+", " ", parts[-1]).replace("`", "").strip()
            if len(when) > 110:
                when = when[:107].rsplit(" ", 1)[0] + "..."
            if len(consumers) > 150:
                consumers = consumers[:147].rsplit(" ", 1)[0] + "..."
            v1 = line in v1_zone
            if ev in seen:
                continue
            seen.add(ev)
            out[ev] = [num, mod, when, consumers, v1]
    return out

# ---------- doc 32: schema ----------
def build_schema():
    out = []
    for fname, mod, num in MODULES:
        text = (DOCS / fname).read_text()
        blocks = re.findall(r"```sql\n(.*?)```", text, re.S)
        out.append((num, mod, fname, blocks))
    return out

# ============ render ============
e = build_errors()
total_codes = sum(len(v) for v in e.values())
v1_count = sum(1 for rows in e.values() for r in rows if r[3])
lines = []
A = lines.append
A("> **Generated aggregation** of the error taxonomies in the 26 module docs")
A("> (each doc's §6). This is the single registry the CI gate (docs/04 §6,")
A("> docs/28 §11) checks against: a code used in code but absent here, or an")
A("> HTTP/status that disagrees with the module doc, fails the build. Meaning")
A("> text is condensed from the owning doc's row; the owning doc is the")
A("> authority. Tier: **V1** = the V1 execution-sheet baseline (exact codes,")
A("> `contracts/errors/taxonomy.md`); **ext** = the extended (post-V1) design")
A("> set (the same dotted convention; names provisional until that phase's")
A("> freeze).")
A("")
A("## 1. Global conventions (docs/04 §3.1 + the V1 baseline, binding)")
A("")
A("- **The shape** (GW-18, every error, every surface): exactly")
A("  `{ \"code\": ..., \"message\": ..., \"correlation_id\": ... }`.")
A("  Extended (post-V1): a `details` object and `docs_url` are the V2")
A("  addition (docs/04 §3.1).")
A("- **Codes** are dotted `domain.action` (lowercase) — the domain is the")
A("  module namespace (auth, ten/tenant, gw, evt, led, aud, sys, lcc/account,")
A("  brg, evl, rsk/risk, pay/payout, chk/checkout/catalog/order, kyc, not,")
A("  doc/document, td, adm, sup, ana/analytics, crm, con/console, bil, aff,")
A("  cms, cmp, mig, mob, jrn, edu, cht, sdk, dvp, trd, plt, cs, public). A")
A("  code appears in exactly one namespace; reuse across modules is a review")
A("  failure. (Pre-baseline legacy `MODULE_TOKEN` names were mapped to this")
A("  convention mechanically; see each doc's §6.2.)")
A("- **HTTP semantics** (the 04 §6 mapping): 400 input, 401 auth, 403 scope/ABAC/")
A("  state-forbidden, 404 not-found-or-not-yours (the no-oracle, 04 §6), 409 state")
A("  machine conflict, 410 gone (reservation expired), 422 domain validation,")
A("  423 locked (risk hold — status is an open question, taxonomy.md), 429")
A("  rate/quota, 503 dependency down (+`Retry-After`), 500 `sys.internal` (never")
A("  a module code at 500).")
A("- **The 404-not-403 rule** (04 §6, 28 §3.3): a resource in another tenant (or")
A("  another identity's) is 404, never 403 — existence is not leaked.")
A("- **The public-safe subset** (27 Part A): public routes return only the public")
A("  codes (the `public.*` namespace + the module codes marked public in that doc's")
A("  §6); an internal code at the public perimeter is a CI failure.")
A("- **Never leak**: stack traces, SQL, internal ids (ULIDs) at the public perimeter")
A("  (the ref indirection, 27 Part A §8), PII (28 §4), the reason a key is invalid")
A("  vs revoked (02 §3.5, same 401).")
A("- **Deprecation**: `Deprecation` header + `public.deprecated` (200) → `410")
A("  public.removed` after the 12-month window (27 Part A §3.5).")
A("")
A(f"## 2. The registry ({total_codes} codes — {v1_count} V1 baseline, "
  f"{total_codes - v1_count} extended — across {len(e)} modules)")
A("")
for (num, mod), rows in e.items():
    A(f"### {num} — {mod}")
    A("")
    A("| Code | HTTP | Meaning (from doc " + num + " §6) | Tier |")
    A("|---|---|---|---|")
    for code, http, meaning, v1 in rows:
        A(f"| `{code}` | {http or '—'} | {meaning or '—'} | {'V1' if v1 else 'ext'} |")
    A("")

(DOCS / "30-error-taxonomy.md").write_text(
    "# 30 — Error Taxonomy (Master Registry)\n\n" + "\n".join(lines) + "\n")

ev = build_events()
topics = collections.OrderedDict()
for ev_name, (num, mod, when, cons, v1) in ev.items():
    t = ev_name.split(".")[0] if "." in ev_name else "(v1-pascal)"
    topics.setdefault(t, []).append((ev_name, num, mod, when, cons, v1))

lines = []
A = lines.append
A("> **Generated aggregation** of the event tables in the 26 module docs (each")
A("> doc's §4). This is the catalog the CI gate checks against (docs/04 §5.7,")
A("> docs/28 §11): an event emitted but not cataloged, or a consumer that never")
A("> handled it, fails the build. The V1 event schemas live in")
A(f"> `contracts/events/payloads/` (envelope + {len(list((ROOT / 'contracts' / 'events' / 'payloads').glob('*.v1.json'))) } V1 event schemas) and the extended")
A("> set in `contracts/events/extended/`; this table is the")
A("> producer/consumer map. `when`/`consumers` are condensed from the owning")
A("> doc's row; the owning doc is the authority. Tier: **V1** = the V1")
A("> execution-sheet baseline (exact names, `contracts/events/catalog.md`);")
A("> **ext** = the extended (post-V1) design set.")
A("")
A("## 1. Transport (docs/04 §5, binding)")
A("")
A("- Redis Streams, at-least-once, idempotent consumers (04 §5.7); the outbox in")
A("  PG (04 §5.4); the relay = one process (advisory lock) → the V3 two-relay")
A("  partition (29 §3.2). Webhook egress = Hook0 (04 §5.6). SSE = the relay's")
A("  fan-out (01 §4.3). Broker **commands are not events** (EVT-20) — they")
A("  live in `command_queue` and never appear in this catalog.")
A("- **Every event carries** (EVT-03, exactly): `id` (ULID), `type` (event")
A("  name), `version` (integer, starts 1), `tenant_id` (ULID), `occurred_at`")
A("  (int64 epoch ms, UTC), `correlation_id` (ULID — the originating request's")
A("  correlation, required since the ninth pass: docs/49 C1), `payload`")
A("  (event-specific, per-event schema in `contracts/events/payloads/`).")
A("- **The DLQ** (04 §5.6): 5 retries → `evt.consumer_dlq` (04 §6) → the CON-15")
A("  alert (21 §3.2).")
A("")
n_ev = len(ev)
n_v1ev = sum(1 for v in ev.values() if v[4])
A(f"## 2. The catalog ({n_ev} events — {n_v1ev} V1 baseline, "
  f"{n_ev - n_v1ev} extended — across {len(topics)} topics)")
A("")
for t, rows in topics.items():
    A(f"### `{t}.*`" if t != "(v1-pascal)" else "### V1 PascalCase events (LCC-23)")
    A("")
    A("| Event | Producer | When / V1 producer | Consumers | Tier |")
    A("|---|---|---|---|---|")
    for ev_name, num, mod, when, cons, v1 in rows:
        A(f"| `{ev_name}` | {num} ({mod}) | {when} | {cons} | {'V1' if v1 else 'ext'} |")
    A("")

(DOCS / "31-event-catalog.md").write_text(
    "# 31 — Event Catalog (Master)\n\n" + "\n".join(lines) + "\n")

# doc 32
sch = build_schema()
total_tables = sum(len(b) for _,_,_,b in sch)
total_ct = sum(len(re.findall(r"CREATE TABLE", block)) for _,_,_,blocks in sch for block in blocks)
lines = []
A = lines.append
A("> **Generated aggregation** of the database designs in the 26 module docs")
A("> (each doc's §9). This is the master schema the migrations (golang-migrate,")
A("> 01 §2) are generated from; the owning doc is the authority for each block,")
A("> this file is the review surface (one place to see the whole schema). The")
A("> full DDL of the 27 ecosystem module's tables is in doc 27 §9 verbatim.")
A("")
A("## 1. Conventions (binding, 01 ADR-1, 05 §9, 32 = this doc)")
A("")
A("- **`tenant_id ULID NOT NULL`** on every tenant-scoped table (the structural")
A("  isolation, 28 §3.3); exceptions (the platform-level): `tenants`,")
A("  `identities`, `audit_log` (tenant + platform scope, 05 §9).")
A("- **ULIDs** everywhere (01 §2); the char-25 top-3-bits guard (02 §3.5);")
A("  public surface uses `public_id_refs` (27 Part A §8), never raw ULIDs.")
A("- **Money**: `_cents BIGINT` + `currency` (no floats, 05 §9).")
A("- **Time**: `TIMESTAMPTZ` (the broker-attested for trading, ADR-12, 01 §3).")
A("- **Partitioning**: monthly partitions for the high-volume tables (the 08")
A("  deals/ticks, the 05 entries/audit, the 04 outbox); the 13-mo tick retention")
A("  (04 §5.4) → R2 archive (06 §3.2, 29 §3.2).")
A("- **Retention**: 7-yr financial/audit (00 §6, 05 §3.5), 2-yr tickets (18 §3.5),")
A("  12-mo competition (24 Part B), 30-day sandbox (27 Part A §5).")
A("- **Append-only**: `ledger_entries`, `audit_log` — the `BEFORE UPDATE`/")
A("  `BEFORE DELETE` triggers reject (05 §9, 28 §3.3).")
A("- **PII**: envelope-encrypted `pii_*` / `*_encrypted` columns (02 §3.7, 28 §3.3);")
A("  documents in R2 (per-tenant prefix), the PG holds the ref only (13 §3.4).")
A("- **Indexes**: every `(tenant_id, …)` leading; the read-model tables (`*_ro`)")
A("  are the query surface for reads (19 §3.1).")
A("")
A(f"## 2. The schema ({total_ct} tables in {total_tables} DDL blocks, module-ordered)")
A("")
for num, mod, fname, blocks in sch:
    A(f"### {num} — {mod} (from docs/{fname} §9)")
    A("")
    if not blocks:
        A("_(no DDL in the module doc — the module is stateless or reuses another)_")
        A("")
        continue
    for b in blocks:
        A("```sql")
        A(b.rstrip())
        A("```")
        A("")

(DOCS / "32-database-design.md").write_text(
    "# 32 — Database Design (Master Schema)\n\n" + "\n".join(lines) + "\n")

print(f"errors: {total_codes} codes / {len(e)} namespaces")
print(f"events: {n_ev} / {len(topics)} topics")
print(f"schema: {total_ct} tables / {total_tables} DDL blocks")

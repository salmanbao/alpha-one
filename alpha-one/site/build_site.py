#!/usr/bin/env python3
"""Build the Alpha One specification website (alpha-one/site/).

Generates a self-contained, offline-capable documentation site for the whole
spec: all 66 docs in alpha-one/docs/, the contracts pack (event catalog,
payload schemas, error taxonomy, 33 API contracts, diagrams) and the PRD /
design-question registers. No network needed at runtime — the only external
dependency (marked.min.js, markdown renderer) is vendored into site/vendor/.

Usage:  python3 site/build_site.py     (regenerates everything)

Outputs (all in alpha-one/site/):
  index.html             SPA shell
  styles.css             design system (light + dark themes)
  app.js                 router, search, renderers
  vendor/marked.min.js   markdown renderer (vendored)
  data/site-data.json    all docs + contracts + registers

Content notes:
  * docs/07 and docs/13 contain one ```mermaid block each — the same machines
    are committed as rendered PNGs in contracts/diagrams/ (account-state,
    kyc-state); the build swaps the fence for an <img> of the committed PNG
    with a link to the Mermaid source. docs/99's flowchart has no committed
    PNG and stays a labeled source block.
  * nothing in docs/ is modified — the site only reads.
"""
from __future__ import annotations

import json
import pathlib
import re
import shutil

ROOT = pathlib.Path(__file__).resolve().parent.parent   # alpha-one/
SITE = ROOT / "site"
DOCS = ROOT / "docs"
CONTRACTS = ROOT / "contracts"
SCRIPTS = ROOT / "scripts"
GENERATED = "2026-09-20"

V1_API_MODULES = {
    "auth": "AUTH — Identity & Access",
    "tenant": "TEN — Tenant Management",
    "gw": "GW — API Gateway",
    "evt": "EVT — Event Backbone",
    "led": "LED — Ledger",
    "aud": "AUD — Audit",
    "lcc": "LCC — Account Lifecycle",
    "brg": "BRG — Trading Bridge",
    "evl": "EVL — Evaluation Engine",
    "rsk": "RSK — Risk Management",
    "kyc": "KYC — Verification",
    "chk": "CHK — Checkout & Billing",
    "pay": "PAY — Payout System",
    "not": "NOT — Notifications",
    "doc": "DOC — Document Generation",
    "td": "TD — Trader Dashboard",
    "adm": "ADM — Admin Panel",
    "con": "CON — Platform Console",
    "ops": "OPS — DevOps",
}

DIAGRAMS = [
    ("lanes.png", "Service lanes", "lanes.md", "OPS-01 (api, workers, relay, bot, frontends)"),
    ("purchase-flow.png", "Purchase flow", "purchase-flow.md", "CHK-06/07/08/09, LCC-05 — webhook tenant routing resolved by citation (docs/12, docs/32)"),
    ("payout-flow.png", "Payout flow", "payout-flow.md", "PAY-01/03/08/09/12, LED-07/08 — `payout.settled` is the catalog name (D60)"),
    ("account-state.png", "Account state machine", "account-state.md", "LCC-02 (binding)"),
    ("kyc-state.png", "KYC state machine", "kyc-state.md", "KYC-06 (binding, D43 edges resolved)"),
    ("payout-state.png", "Payout state machine", "payout-state.md", "PAY-13 (processing/failed/cancelled reserved in V1)"),
    ("event-bus.png", "Event bus", "event-bus.md", "EVT-01/02/05/08 — parameters per docs/04"),
    ("build-order.png", "Build order", "build-order.md", "V1 Execution Sheet `Depends On` — binding order OPS→TEN→AUTH→GW→EVT→LCC→BRG→EVL (docs/01 §8)"),
]

MERMAID_PNG = {
    "07": ("account-state.png", "account-state.md", "The LCC-02 account state machine (same source as contracts/diagrams/account-state.md)"),
    "13": ("kyc-state.png", "kyc-state.md", "The KYC-06 session state machine (same source as contracts/diagrams/kyc-state.md)"),
}

# --------------------------------------------------------------------------- #
# collection
# --------------------------------------------------------------------------- #
def h1_title(text: str, fallback: str) -> str:
    m = re.search(r"^#\s+(.+)$", text, re.M)
    t = (m.group(1) if m else fallback).strip()
    t = re.sub(r"^\d{1,3}[a-z]?\s*[—-]\s*", "", t)
    return t


def doc_groups(num: str) -> str:
    n = int(re.match(r"\d+", num).group())
    if num.startswith("37a"):
        return "prd"
    if n in (0, 1, 99):
        return "start"
    if 2 <= n <= 15:
        return "modules"
    if 16 <= n <= 27:
        return "surfaces"
    if 28 <= n <= 35:
        return "crosscutting"
    if 36 <= n <= 40:
        return "prd"
    return "reviews"


def collect_docs() -> list[dict]:
    out = []
    for p in sorted(DOCS.glob("*.md")):
        text = p.read_text(encoding="utf-8")
        num = re.match(r"(\d+[a-z]?)", p.stem).group(1)
        if num in MERMAID_PNG:
            png, src, cap = MERMAID_PNG[num]
            def swap(m, png=png, src=src, cap=cap):
                return (f'<figure class="diagram"><img src="../contracts/diagrams/{png}" '
                        f'alt="{cap}" loading="lazy" decoding="async" width="860" height="480">'
                        f'<figcaption>{cap} — Mermaid source: '
                        f'<a href="../contracts/diagrams/{src}" target="_blank">{src}</a></figcaption></figure>')
            text = re.sub(r"```mermaid\n.*?```", swap, text, flags=re.S, count=1)
        out.append({
            "id": p.stem,
            "num": num,
            "file": f"../docs/{p.name}",
            "title": h1_title(text, p.stem),
            "group": doc_groups(num),
            "content": text,
        })
    return out


def is_open_answer(ans) -> bool:
    a = (ans or "").strip().lstrip("*_ ").strip()
    return not a or a.lower().startswith("open")


def collect_payloads() -> list[dict]:
    out = []
    for p in sorted((CONTRACTS / "events" / "payloads").glob("*.json")):
        if p.name == "envelope.schema.json":
            continue
        doc = json.loads(p.read_text(encoding="utf-8"))
        desc = doc.get("description", "")
        src = ""
        m = re.search(r"Derived from:\s*(.+?)(?:\. Envelope|\.\s*$)", desc)
        if m:
            src = m.group(1).strip()
        all_of = doc.get("allOf", [])
        payload = all_of[1].get("properties", {}).get("payload", {}) if len(all_of) == 2 else {}
        required = set(payload.get("required", []))
        fields = []
        for name, f in (payload.get("properties") or {}).items():
            if "$ref" in f:
                t = f["$ref"].split("/")[-1]
            else:
                t = f.get("type") or "object"
                if isinstance(t, list):
                    t = "|".join(t)
            fields.append({
                "name": name,
                "type": t.replace("envelope.schema.json#/$defs/", ""),
                "required": name in required,
                "desc": (f.get("description") or "").strip(),
            })
        cons = re.search(r"consumers\s*=\s*([^.]+)", desc)
        out.append({
            "event": p.stem.replace(".v1", ""),
            "file": p.name,
            "v1": not p.stem.startswith("risk."),
            "source": src,
            "consumers": cons.group(1).strip() if cons else "",
            "fields": fields,
            "json": json.dumps(doc, indent=1, ensure_ascii=False),
        })
    return out


def collect() -> dict:
    docs = collect_docs()
    payloads = collect_payloads()
    api = []
    for p in sorted((CONTRACTS / "api").glob("*.md")):
        name = p.stem
        api.append({
            "name": name,
            "label": V1_API_MODULES.get(name, name.upper()),
            "v1": name in V1_API_MODULES,
            "content": p.read_text(encoding="utf-8"),
        })
    dq = json.loads((SCRIPTS / "design-questions.json").read_text(encoding="utf-8"))["questions"]
    wb = json.loads((SCRIPTS / "prd-workbook.json").read_text(encoding="utf-8"))["open_questions"]
    tri = json.loads((SCRIPTS / "prd-question-triage.json").read_text(encoding="utf-8"))
    return {
        "generated": GENERATED,
        "project": {
            "name": "Alpha One",
            "tagline": "Prop Firm as a Service (PFaaS) — platform specification",
            "status": {
                "frozen": "Frozen — self-consistent (2026-09-20 gap-closure pass): all docs, contracts and registers agree with each other.",
                "open": "Not business-complete: 197 of 205 PRD questions still await FunderBlu's owners (triaged in docs/37 + docs/37a); 5 of 80 design-review questions open.",
            },
            "stats": {
                "docs": len(docs),
                "v1_events": sum(1 for p in payloads if p["v1"]),
                "payloads": len(payloads),
                "api_specs": len(api),
                "diagrams": len(DIAGRAMS),
                "d_rows": len(dq),
                "d_open": sum(1 for q in dq if is_open_answer(q.get("answer"))),
                "prd_total": len(wb),
                "prd_open": sum(1 for q in wb if is_open_answer(q.get("answer"))),
            },
        },
        "docs": docs,
        "contracts": {
            "readme": (CONTRACTS / "README.md").read_text(encoding="utf-8"),
            "catalog": (CONTRACTS / "events" / "catalog.md").read_text(encoding="utf-8"),
            "taxonomy": (CONTRACTS / "errors" / "taxonomy.md").read_text(encoding="utf-8"),
            "payloads": payloads,
            "api": api,
            "diagrams": [
                {"png": d[0], "name": d[1], "source": d[2], "cites": d[3]} for d in DIAGRAMS
            ],
        },
        "registers": {
            "design_questions": dq,
            "prd_questions": wb,
            "triage": tri,
        },
    }

# --------------------------------------------------------------------------- #
# index.html shell
# --------------------------------------------------------------------------- #
INDEX = """<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Alpha One — Platform Specification</title>
<meta name="description" content="Complete specification & contract pack for Alpha One, a Prop Firm-as-a-Service platform: 65 spec docs, 37 V1 events, 33 API contracts, decision registers.">
<link rel="stylesheet" href="styles.css">
<script>/* set theme before first paint */
try{var t=localStorage.getItem('a1-theme');if(!t)t=matchMedia('(prefers-color-scheme: light)').matches?'light':'dark';document.documentElement.dataset.theme=t;}catch(e){}
</script>
</head>
<body>
<div class="progress" id="progress" aria-hidden="true"></div>
<button class="hamburger" id="hamburger" type="button" aria-label="Toggle navigation" aria-expanded="false">☰</button>
<div class="overlay" id="overlay"></div>

<div class="layout">
<aside class="sidebar" id="sidebar">
  <div class="sb-head">
    <a class="sb-brand" href="#/"><span class="sb-logo">◈</span> Alpha One <span class="sb-tag">spec</span></a>
    <div class="sb-search">
      <input id="nav-search" type="search" placeholder="Search the spec…  ( / )" autocomplete="off" aria-label="Search the specification">
    </div>
  </div>
  <nav class="sb-nav" id="sb-nav" aria-label="Specification"></nav>
  <div class="sb-foot">
    <a class="sb-chip frozen" href="#/doc/00-executive-brief">frozen · self-consistent</a>
    <a class="sb-chip open" href="#/registers">197 PRD questions open →</a>
  </div>
</aside>

<div class="content-col">
<header class="topbar">
  <div class="topbar-crumb" id="crumb">Alpha One — Platform Specification</div>
  <div class="topbar-actions">
    <a class="tbtn" href="../docs/" target="_blank" title="Browse the raw markdown">Markdown</a>
    <button class="tbtn" id="theme-toggle" type="button" aria-label="Toggle color theme" title="Theme (t)">◐</button>
  </div>
</header>

<main class="content" id="view" tabindex="-1"></main>

<aside class="rail" id="rail" aria-label="On this page">
  <div class="rail-box">
    <h4>On this page</h4>
    <ol class="rail-list" id="rail-list"></ol>
  </div>
</aside>
</div>
</div>

<button class="totop" id="totop" type="button" aria-label="Back to top">↑</button>
<script src="vendor/marked.min.js"></script>
<script src="app.js"></script>
</body>
</html>
"""

# --------------------------------------------------------------------------- #
# styles.css
# --------------------------------------------------------------------------- #
CSS = r"""/* Alpha One spec site — design system (2026-09-20) */
:root{
  --sidebar-w:302px; --rail-w:224px; --topbar-h:52px;
  --font:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  --mono:ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,monospace;
}
html[data-theme="dark"]{
  --bg:#0d1117; --bg-soft:#161b22; --bg-code:#0a0e14;
  --border:#30363d; --border-soft:#21262d;
  --text:#e6edf3; --muted:#8b949e; --faint:#6e7681;
  --accent:#58a6ff; --accent-soft:rgba(88,166,255,.12);
  --ok:#3fb950; --ok-soft:rgba(63,185,80,.12);
  --warn-bg:rgba(187,128,9,.12); --warn-border:#9e6a03; --warn-text:#e3b341;
  --info-soft:rgba(88,166,255,.08);
  --shadow:0 8px 30px rgba(0,0,0,.45);
  color-scheme:dark;
}
html[data-theme="light"]{
  --bg:#ffffff; --bg-soft:#f6f8fa; --bg-code:#f6f8fa;
  --border:#d0d7de; --border-soft:#eaeef2;
  --text:#1f2328; --muted:#57606a; --faint:#8c959f;
  --accent:#0969da; --accent-soft:rgba(9,105,218,.08);
  --ok:#1a7f37; --ok-soft:rgba(26,127,55,.1);
  --warn-bg:rgba(212,167,44,.12); --warn-border:#bf8700; --warn-text:#9a6700;
  --info-soft:rgba(9,105,218,.05);
  --shadow:0 8px 30px rgba(31,35,40,.12);
  color-scheme:light;
}
*{box-sizing:border-box}
html{scroll-behavior:smooth;scroll-padding-top:calc(var(--topbar-h) + 16px)}
body{margin:0;background:var(--bg);color:var(--text);font:16px/1.65 var(--font)}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}
button{font-family:inherit}

.progress{position:fixed;top:0;left:0;height:3px;width:0;background:var(--accent);z-index:60;transition:width .1s linear}
.topbar{position:sticky;top:0;height:var(--topbar-h);display:flex;align-items:center;justify-content:space-between;gap:12px;
  padding:0 20px;background:color-mix(in srgb, var(--bg) 88%, transparent);backdrop-filter:blur(8px);
  border-bottom:1px solid var(--border-soft);z-index:40}
.topbar-crumb{font-size:14px;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.topbar-actions{display:flex;gap:8px;flex:none}
.tbtn{background:var(--bg-soft);border:1px solid var(--border);border-radius:8px;color:var(--text);
  padding:5px 10px;font-size:13px;cursor:pointer;text-decoration:none!important}
.tbtn:hover{border-color:var(--accent);color:var(--accent)}

.layout{display:grid;grid-template-columns:var(--sidebar-w) minmax(0,1fr);max-width:1560px;margin:0 auto}
.content-col{min-width:0;display:grid;grid-template-columns:minmax(0,1fr) var(--rail-w);grid-template-rows:auto 1fr;column-gap:32px}
.topbar{grid-column:1 / -1}
.content{grid-column:1;grid-row:2;max-width:880px;padding:8px 40px 80px;width:100%;outline:none}

/* ---------- sidebar ---------- */
.sidebar{position:sticky;top:0;height:100vh;overflow-y:auto;border-right:1px solid var(--border-soft);
  padding:16px 14px 20px;background:var(--bg);display:flex;flex-direction:column;gap:10px;scrollbar-width:thin}
.sb-head{display:flex;flex-direction:column;gap:10px}
.sb-brand{display:flex;align-items:center;gap:8px;font-weight:650;font-size:15.5px;color:var(--text);text-decoration:none!important}
.sb-logo{color:var(--accent);font-size:18px}
.sb-tag{font-size:11px;font-weight:500;color:var(--muted);border:1px solid var(--border);border-radius:20px;padding:1px 8px}
.sb-search input{width:100%;background:var(--bg-soft);border:1px solid var(--border);border-radius:8px;
  color:var(--text);padding:7px 10px;font-size:13.5px;outline:none}
.sb-search input:focus{border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-soft)}
.sb-nav{flex:1;display:flex;flex-direction:column;gap:14px;font-size:14px;padding-bottom:8px}
.sb-group h4{margin:0 0 4px;font-size:11px;text-transform:uppercase;letter-spacing:.09em;color:var(--faint);padding:0 8px}
.sb-group ol{list-style:none;margin:0;padding:0}
.sb-group a{display:flex;gap:8px;align-items:baseline;padding:4.5px 8px;border-radius:7px;color:var(--muted);
  text-decoration:none!important;white-space:nowrap;overflow:hidden}
.sb-group a span.t{overflow:hidden;text-overflow:ellipsis}
.sb-group a:hover{color:var(--text);background:var(--bg-soft);text-decoration:none}
.sb-group a.active{color:var(--accent);background:var(--accent-soft);font-weight:600}
.sb-num{color:var(--faint);font:600 11px var(--mono);min-width:22px;flex:none}
.sb-group a.active .sb-num{color:var(--accent)}
.sb-foot{display:flex;flex-direction:column;gap:6px;border-top:1px solid var(--border-soft);padding-top:12px}
.sb-chip{font-size:12.5px;border-radius:8px;padding:6px 10px;text-decoration:none!important;border:1px solid}
.sb-chip.frozen{color:var(--ok);background:var(--ok-soft);border-color:color-mix(in srgb, var(--ok) 35%, transparent)}
.sb-chip.open{color:var(--warn-text);background:var(--warn-bg);border-color:var(--warn-border)}

/* ---------- rail ---------- */
.rail{position:sticky;top:var(--topbar-h);align-self:start;grid-column:2;grid-row:2;max-height:calc(100vh - var(--topbar-h));padding:20px 12px;overflow-y:auto;scrollbar-width:thin}
.rail-box{font-size:13px}
.rail-box h4{margin:0 0 10px;font-size:11.5px;text-transform:uppercase;letter-spacing:.08em;color:var(--faint)}
.rail-list{list-style:none;margin:0;padding:0;border-left:1px solid var(--border-soft)}
.rail-list a{display:block;padding:4px 12px;color:var(--muted);text-decoration:none!important;border-left:2px solid transparent;margin-left:-1px}
.rail-list a:hover{color:var(--text);text-decoration:none}
.rail-list a.active{color:var(--accent);border-left-color:var(--accent);font-weight:600}
.rail-list .l3{padding-left:24px;font-size:12.5px}

/* ---------- typography ---------- */
h1{font-size:29px;line-height:1.25;margin:8px 0 14px}
h2{font-size:24px;line-height:1.25;margin:52px 0 14px;padding-top:18px;border-top:1px solid var(--border-soft);scroll-margin-top:calc(var(--topbar-h) + 12px)}
h3{font-size:19px;margin:32px 0 10px;scroll-margin-top:calc(var(--topbar-h) + 12px)}
h4{font-size:16.5px;margin:24px 0 8px;scroll-margin-top:calc(var(--topbar-h) + 12px)}
p{margin:12px 0}
ul,ol{padding-left:26px}
li{margin:5px 0}
hr{border:none;border-top:1px solid var(--border-soft);margin:40px 0}
blockquote{border-left:3px solid var(--accent);margin:16px 0;padding:6px 16px;color:var(--muted);background:var(--bg-soft);border-radius:0 8px 8px 0}
strong{font-weight:650}
del{color:var(--faint)}
code{background:var(--bg-code);border:1px solid var(--border-soft);border-radius:5px;padding:1.5px 5px;font:13px/1.5 var(--mono)}

/* ---------- tables ---------- */
.tablewrap{overflow-x:auto;border:1px solid var(--border-soft);border-radius:10px;margin:16px 0}
table{border-collapse:collapse;width:100%;font-size:13.5px;min-width:560px}
th,td{border-bottom:1px solid var(--border-soft);padding:8px 12px;text-align:left;vertical-align:top}
thead th{position:sticky;top:var(--topbar-h);background:var(--bg-soft);font-weight:650;z-index:2}
tbody tr:last-child td{border-bottom:none}
tbody tr:hover td{background:var(--info-soft)}

/* ---------- code ---------- */
.codeblock{margin:18px 0;border:1px solid var(--border-soft);border-radius:10px;overflow:hidden;background:var(--bg-code)}
.codehead{display:flex;align-items:center;gap:10px;padding:6px 12px;background:var(--bg-soft);border-bottom:1px solid var(--border-soft)}
.codehead .lang{font:600 11px var(--mono);text-transform:uppercase;letter-spacing:.06em;color:var(--muted);
  background:var(--accent-soft);border-radius:4px;padding:2px 7px}
.codehead .fname{font:12.5px var(--mono);color:var(--faint);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.copybtn{margin-left:auto;background:transparent;border:1px solid var(--border);border-radius:6px;color:var(--muted);
  font:12px var(--mono);padding:2px 9px;cursor:pointer}
.copybtn:hover{color:var(--accent);border-color:var(--accent)}
.copybtn.done{color:var(--ok);border-color:var(--ok)}
.codeblock pre{margin:0;padding:16px;overflow-x:auto;line-height:1.55}
.codeblock pre code{background:none;border:none;padding:0;font-size:13px}

/* ---------- figures ---------- */
figure.diagram{margin:26px 0;background:#fff;border:1px solid var(--border-soft);border-radius:12px;padding:18px;overflow-x:auto}
figure.diagram img{max-width:100%;height:auto;display:block;margin:0 auto}
figure.diagram figcaption{color:#57606a;font-size:13px;text-align:center;margin-top:10px;font-style:italic}
figure.diagram figcaption a{color:#0969da;font-style:normal}

/* ---------- headings: anchor links ---------- */
.hlink{opacity:0;margin-left:8px;font-size:.75em;color:var(--faint);text-decoration:none!important;transition:opacity .12s}
h2:hover .hlink,h3:hover .hlink,h4:hover .hlink,.hlink:focus{opacity:1}
.hlink.copied{color:var(--ok);opacity:1}

/* ---------- home ---------- */
.hero{padding:26px 0 6px}
.hero-kicker{font-size:12.5px;text-transform:uppercase;letter-spacing:.1em;color:var(--accent);margin:0 0 10px;font-weight:650}
.hero h1{margin:0 0 12px}
.hero-sub{color:var(--muted);font-size:15.5px;margin:0 0 16px}
.hero-meta{display:flex;flex-wrap:wrap;gap:8px}
.chip{font-size:12.5px;color:var(--muted);background:var(--bg-soft);border:1px solid var(--border);border-radius:20px;padding:3px 11px}
.chip b{color:var(--text);font-weight:650}
.callout{border-radius:10px;padding:14px 16px;font-size:14.5px;margin:20px 0}
.callout.warn{background:var(--warn-bg);border:1px solid var(--warn-border)}
.callout.warn strong:first-child{color:var(--warn-text)}
.callout.info{background:var(--info-soft);border:1px solid color-mix(in srgb, var(--accent) 30%, transparent)}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:12px;margin:22px 0}
.card{border:1px solid var(--border-soft);border-radius:12px;padding:14px 16px;background:var(--bg-soft);text-decoration:none!important;display:block}
.card:hover{border-color:var(--accent);text-decoration:none}
.card h3{margin:0 0 6px;font-size:15.5px}
.card p{margin:0;font-size:13px;color:var(--muted);line-height:1.5}
.card .card-tag{font:600 10.5px var(--mono);text-transform:uppercase;letter-spacing:.07em;color:var(--accent)}
.doclist{border:1px solid var(--border-soft);border-radius:12px;overflow:hidden}
.doclist h4{margin:0;padding:10px 14px;background:var(--bg-soft);font-size:12px;text-transform:uppercase;letter-spacing:.07em;color:var(--faint)}
.doclist ol{list-style:none;margin:0;padding:4px 0}
.doclist a{display:flex;gap:10px;padding:7px 14px;color:var(--text);text-decoration:none!important;font-size:14px}
.doclist a:hover{background:var(--bg-soft)}
.doclist a .n{font:600 12px var(--mono);color:var(--faint);min-width:30px}

/* ---------- registers ---------- */
.filterbar{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin:18px 0}
.filterbar input,.filterbar select{background:var(--bg-soft);border:1px solid var(--border);border-radius:8px;
  color:var(--text);padding:7px 10px;font-size:13.5px;outline:none}
.filterbar input{flex:1;min-width:180px}
.countline{font-size:13.5px;color:var(--muted);margin:8px 0 16px}
.badge{display:inline-block;font:600 11px var(--mono);border-radius:20px;padding:1.5px 9px;border:1px solid}
.badge.ok{color:var(--ok);background:var(--ok-soft);border-color:color-mix(in srgb, var(--ok) 35%, transparent)}
.badge.open{color:var(--warn-text);background:var(--warn-bg);border-color:var(--warn-border)}
.badge.v1{color:var(--accent);background:var(--accent-soft);border-color:color-mix(in srgb, var(--accent) 40%, transparent)}
.badge.ext{color:var(--muted);background:var(--bg-soft);border-color:var(--border)}
.drow{border:1px solid var(--border-soft);border-radius:10px;margin:10px 0;background:var(--bg-soft);overflow:hidden}
.drow summary{cursor:pointer;padding:10px 14px;font-size:14px;list-style:none;display:flex;gap:10px;align-items:baseline}
.drow summary::-webkit-details-marker{display:none}
.drow summary .did{font:700 12.5px var(--mono);color:var(--accent);min-width:44px}
.drow summary .dsum{flex:1;color:var(--text)}
.drow .dbody{padding:0 14px 14px 68px;font-size:14px}
.drow .dbody p{margin:8px 0}
.drow .meta{font-size:12.5px;color:var(--faint)}
.eventrow{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:9px 14px;border-bottom:1px solid var(--border-soft);text-decoration:none!important;color:var(--text)}
.eventrow:hover{background:var(--bg-soft);text-decoration:none}
.eventrow .ename{font:600 13.5px var(--mono)}
.eventrow .emeta{font-size:12px;color:var(--faint);flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.schematbl td.req::after{content:" *";color:var(--warn-text)}
.schema-note{font-size:12.5px;color:var(--faint);margin:4px 0 14px}
.diagrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px;margin:20px 0}
.dia{border:1px solid var(--border-soft);border-radius:12px;overflow:hidden;background:#fff;text-decoration:none!important;display:block}
.dia:hover{border-color:var(--accent);text-decoration:none}
.dia img{width:100%;height:190px;object-fit:cover;object-position:top;display:block}
.dia .dia-cap{padding:10px 14px;background:var(--bg-soft);color:var(--text);font-size:13.5px;font-weight:600}
.dia .dia-cites{padding:0 14px 12px;background:var(--bg-soft);color:var(--faint);font-size:12px}

/* ---------- search results ---------- */
.sr{border:1px solid var(--border-soft);border-radius:10px;padding:12px 16px;margin:10px 0;background:var(--bg-soft);text-decoration:none!important;display:block}
.sr:hover{border-color:var(--accent);text-decoration:none}
.sr .sr-title{font-weight:650;color:var(--accent);font-size:14.5px}
.sr .sr-snip{font-size:13.5px;color:var(--muted);margin-top:5px;line-height:1.55}
.sr .sr-snip mark{background:var(--warn-bg);color:var(--warn-text);border-radius:3px;padding:0 2px}

/* ---------- prev/next + foot ---------- */
.pn{display:flex;gap:12px;margin:28px 0 8px}
.pn a{flex:1;border:1px solid var(--border-soft);border-radius:10px;padding:10px 14px;font-size:14px;text-decoration:none!important}
.pn a:hover{border-color:var(--accent)}
.pn .pn-label{display:block;font-size:11.5px;color:var(--faint);text-transform:uppercase;letter-spacing:.07em}
.pn .pn-title{color:var(--accent);font-weight:600}
.page-foot{margin-top:48px;border-top:1px solid var(--border-soft);padding-top:20px;font-size:14px;color:var(--muted)}
.foot-links a{color:var(--muted)}

/* ---------- misc controls ---------- */
.hamburger{display:none;position:fixed;top:10px;left:12px;z-index:70;width:40px;height:40px;border-radius:9px;
  background:var(--bg-soft);border:1px solid var(--border);color:var(--text);font-size:17px;cursor:pointer}
.overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:50}
.totop{position:fixed;right:22px;bottom:22px;z-index:45;width:42px;height:42px;border-radius:50%;
  background:var(--bg-soft);border:1px solid var(--border);color:var(--text);font-size:17px;cursor:pointer;
  opacity:0;pointer-events:none;transition:opacity .15s;box-shadow:var(--shadow)}
.totop.show{opacity:1;pointer-events:auto}
.totop:hover{color:var(--accent);border-color:var(--accent)}

@media (max-width:1240px){
  .content-col{grid-template-columns:minmax(0,1fr);grid-template-rows:auto 1fr}
  .rail{display:none}
}
@media (max-width:900px){
  .layout{grid-template-columns:1fr}
  .sidebar{position:fixed;left:0;top:0;bottom:0;width:min(86vw,320px);z-index:65;transform:translateX(-102%);
    transition:transform .18s ease;box-shadow:var(--shadow)}
  body.nav-open .sidebar{transform:none}
  body.nav-open .overlay{display:block}
  .hamburger{display:block}
  .topbar{padding-left:60px}
  .content{padding:8px 20px 70px}
  .hero h1{font-size:24px}
  thead th{top:0}
}
@media print{
  .sidebar,.topbar,.rail,.hamburger,.totop,.progress,.copybtn,.hlink,.pn{display:none!important}
  .layout{display:block}
  .content{max-width:none;padding:0}
  html{scroll-behavior:auto}
}
"""

# --------------------------------------------------------------------------- #
# app.js
# --------------------------------------------------------------------------- #
JS = r"""/* Alpha One spec site — app.js (2026-09-20) */
(function () {
  "use strict";
  var DATA = null, DATA_READY = null;

  function $(s, r) { return (r || document).querySelector(s); }
  function $$(s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); }
  function esc(s) { return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;"); }

  DATA_READY = fetch("data/site-data.json").then(function (r) { return r.json(); }).then(function (d) { DATA = d; });

  marked.use({ gfm: true, breaks: false });

  /* ---------- markdown rendering ---------- */
  function slugify(t) {
    return t.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
  }
  function renderMd(md) {
    var html = marked.parse(md);
    return html;
  }
  function postProcess(scope) {
    /* heading ids + anchor links */
    var used = {};
    $$("h1,h2,h3,h4", scope).forEach(function (h) {
      var base = slugify(h.textContent.replace(/\s*¶\s*$/, "")) || "section";
      var id = base, i = 2;
      while (used[id]) id = base + "-" + i++;
      used[id] = 1;
      h.id = id;
      var a = document.createElement("a");
      a.className = "hlink";
      a.href = currentRoute().replace(/\/+$/, "") + "/h=" + id;
      a.textContent = "¶";
      a.setAttribute("aria-label", "Link to this section");
      h.appendChild(a);
    });
    /* code blocks: tablewrap + copy */
    $$("pre", scope).forEach(function (pre) {
      if (pre.parentElement.classList.contains("codeblock")) return;
      var wrap = document.createElement("div"); wrap.className = "codeblock";
      var head = document.createElement("div"); head.className = "codehead";
      var code = pre.querySelector("code");
      var lang = "text";
      if (code) {
        var cm = code.className.match(/language-([\w+-]+)/);
        if (cm) lang = cm[1];
      }
      var fname = "";
      if (code) {
        var fm = (code.textContent || "").match(/^\s*\/\/\s*([\w./-]+\.\w{1,4})\b/);
        if (fm) fname = fm[1];
      }
      head.innerHTML = '<span class="lang"></span><span class="fname"></span><button class="copybtn" type="button">copy</button>';
      head.querySelector(".lang").textContent = lang;
      head.querySelector(".fname").textContent = fname;
      pre.parentNode.insertBefore(wrap, pre);
      wrap.appendChild(head); wrap.appendChild(pre);
      wrap.querySelector(".copybtn").addEventListener("click", function () { copyText(pre.innerText, this); });
    });
    /* tables: wrap */
    $$("table", scope).forEach(function (t) {
      if (t.parentElement.classList.contains("tablewrap")) return;
      var w = document.createElement("div"); w.className = "tablewrap";
      t.parentNode.insertBefore(w, t); w.appendChild(t);
    });
    /* links: intra-doc NN-name.md cross-refs become SPA routes; relative file refs open in a new tab */
    $$("a", scope).forEach(function (a) {
      var href = a.getAttribute("href");
      if (!href || /^https?:/.test(href) || href.charAt(0) === "#") return;
      var bare = href.replace(/^docs\//, "");
      if (/^\d{1,3}[a-z]?-[\w-]+\.md$/.test(bare)) {
        var doc = DATA.docs.filter(function (d) { return d.id === bare.replace(/\.md$/, ""); })[0];
        if (doc) { a.setAttribute("href", "#/doc/" + doc.id); return; }
      }
      if (/^\.\.\//.test(href) || /^contracts\//.test(href)) a.setAttribute("target", "_blank");
    });
    /* anchor links: copy url */
    $$(".hlink", scope).forEach(function (a) {
      a.addEventListener("click", function (e) {
        e.preventDefault();
        var url = location.href.split("#")[0] + a.getAttribute("href");
        copyText(url, a, "✓");
      });
    });
  }
  function copyText(text, btn, doneMark) {
    var done = function () {
      if (btn.classList) { btn.textContent = doneMark || "copied ✓"; btn.classList.add("done"); }
      setTimeout(function () { btn.textContent = btn.getAttribute("data-orig") || "copy"; btn.classList.remove("done"); }, 1400);
    };
    if (!btn.getAttribute("data-orig")) btn.setAttribute("data-orig", btn.textContent);
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(text).then(done, function () {});
  }

  /* ---------- route helpers ---------- */
  function parseHash() {
    var h = location.hash.replace(/^#\/?/, "");
    var parts = h.split("/").filter(Boolean);
    return { route: parts[0] || "home", arg: parts[1] || "", sub: parts[2] || "" };
  }
  function currentRoute() {
    return location.hash ? location.hash : "#/";
  }
  function setCrumb(t) { var c = $("#crumb"); if (c) c.textContent = t; }

  /* ---------- sidebar ---------- */
  var GROUPS = [
    ["start", "Start here"],
    ["modules", "Module specs (V1 core)"],
    ["surfaces", "Surfaces & integrations"],
    ["crosscutting", "Cross-cutting"],
    ["prd", "PRD & registers"],
    ["reviews", "Reviews & audits"],
    ["contracts", "Contract pack"],
    ["registers", "Decision registers"],
  ];
  function buildSidebar() {
    var nav = $("#sb-nav");
    nav.innerHTML = "";
    GROUPS.forEach(function (g) {
      var div = document.createElement("div"); div.className = "sb-group";
      div.innerHTML = "<h4>" + g[1] + "</h4><ol></ol>";
      var ol = div.querySelector("ol");
      if (g[0] === "contracts" || g[0] === "registers") {
        var links = g[0] === "contracts" ? [
          ["contracts", "", "Contracts — overview"],
          ["contracts", "events", "Event catalog & payloads"],
          ["contracts", "errors", "Error taxonomy"],
          ["contracts", "api", "API contracts"],
          ["contracts", "diagrams", "Diagrams"],
        ] : [
          ["registers", "", "Decisions & open questions"],
          ["registers", "d", "Design decisions D1–D" + DATA.project.stats.d_rows],
          ["registers", "prd", "PRD open questions (205)"],
          ["registers", "triage", "Triage — who answers what"],
        ];
        links.forEach(function (l) {
          var a = document.createElement("a");
          a.href = "#/" + l[0] + (l[1] ? "/" + l[1] : "");
          a.innerHTML = '<span class="t"></span>';
          a.querySelector(".t").textContent = l[2];
          ol.appendChild(a);
        });
      } else {
        DATA.docs.filter(function (d) { return d.group === g[0]; }).forEach(function (d) {
          var a = document.createElement("a");
          a.href = "#/doc/" + d.id;
          a.dataset.doc = d.id;
          a.innerHTML = '<span class="sb-num"></span><span class="t"></span>';
          a.querySelector(".sb-num").textContent = d.num;
          a.querySelector(".t").textContent = d.title;
          ol.appendChild(a);
        });
      }
      nav.appendChild(div);
    });
    /* search filter */
    var search = $("#nav-search");
    search.addEventListener("input", function () {
      var q = search.value.trim().toLowerCase();
      $$("#sb-nav .sb-group a").forEach(function (a) {
        var txt = (a.textContent || "").toLowerCase();
        a.style.display = !q || txt.indexOf(q) !== -1 ? "" : "none";
      });
      $$("#sb-nav .sb-group").forEach(function (g) {
        var any = $$("a", g).some(function (a) { return a.style.display !== "none"; });
        g.style.display = any ? "" : "none";
      });
    });
  }

  /* ---------- rail (on this page) ---------- */
  function buildRail(scope) {
    var list = $("#rail-list");
    list.innerHTML = "";
    $$("h2,h3", scope).forEach(function (h) {
      var li = document.createElement("li");
      var a = document.createElement("a");
      a.href = currentRoute().replace(/\/+$/, "") + "/h=" + h.id;
      a.textContent = h.textContent.replace(/\s*¶\s*$/, "").trim();
      if (h.tagName === "H3") li.className = "l3";
      li.appendChild(a); list.appendChild(li);
    });
  }

  /* ---------- scroll-spy + progress ---------- */
  function initScroll(scope) {
    var heads = $$("h2[id],h3[id]", scope);
    var railLinks = $$("#rail-list a");
    var sbLinks = $$("#sb-nav a[data-doc]");
    var cur = parseHash();
    var docLink = sbLinks.filter(function (a) { return a.dataset.doc === cur.arg; })[0];
    if (docLink && cur.route === "doc") docLink.classList.add("active");
    if (window._a1scroll) window.removeEventListener("scroll", window._a1scroll);
    var ticking = false;
    var onScroll = function () {
      if (ticking) return; ticking = true;
      requestAnimationFrame(function () {
        ticking = false;
        var line = 90, act = null;
        for (var i = heads.length - 1; i >= 0; i--) {
          if (heads[i].getBoundingClientRect().top - line <= 1) { act = heads[i]; break; }
        }
        railLinks.forEach(function (a) { a.classList.toggle("active", act && a.textContent === act.textContent.replace(/\s*¶\s*$/, "").trim()); });
        var doc = document.documentElement;
        var max = doc.scrollHeight - window.innerHeight;
        $("#progress").style.width = (max > 0 ? Math.min(100, window.scrollY / max * 100) : 0) + "%";
        $("#totop").classList.toggle("show", window.scrollY > 700);
      });
    };
    window._a1scroll = onScroll;
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
  }

  /* ---------- page builders ---------- */
  function pageDoc(id) {
    var d = DATA.docs.filter(function (x) { return x.id === id; })[0];
    if (!d) return pageNotFound();
    var v = $("#view");
    var idx = DATA.docs.indexOf(d);
    v.innerHTML = '<article class="doc"><div id="doc-body"></div>' +
      '<nav class="pn" id="prevnext"></nav>' +
      '<footer class="page-foot"><p>Source: <a href="' + d.file + '" target="_blank">' + esc(d.file.replace("../", "")) + "</a> · generated " + esc(DATA.generated) +
      ' · re-render after doc changes with <code>python3 site/build_site.py</code></p></footer></article>';
    var body = $("#doc-body");
    body.innerHTML = renderMd(d.content);
    postProcess(body);
    buildRail(body);
    /* prev/next */
    var pn = $("#prevnext");
    if (idx > 0) {
      var p = DATA.docs[idx - 1];
      var ap = document.createElement("a"); ap.href = "#/doc/" + p.id;
      ap.innerHTML = '<span class="pn-label">← Previous</span><span class="pn-title"></span>';
      ap.querySelector(".pn-title").textContent = p.num + " — " + p.title;
      pn.appendChild(ap);
    }
    if (idx < DATA.docs.length - 1) {
      var nx = DATA.docs[idx + 1];
      var an = document.createElement("a"); an.href = "#/doc/" + nx.id; an.style.textAlign = "right";
      an.innerHTML = '<span class="pn-label">Next →</span><span class="pn-title"></span>';
      an.querySelector(".pn-title").textContent = nx.num + " — " + nx.title;
      pn.appendChild(an);
    }
    setCrumb("Doc " + d.num + " — " + d.title);
    /* deep link to heading */
    var h = parseHash().sub;
    if (h && h.indexOf("h=") === 0) {
      var hid = h.slice(2), el = document.getElementById(hid);
      if (el) setTimeout(function () { el.scrollIntoView(); }, 30);
    }
    initScroll(v);
  }

  function pageHome() {
    var v = $("#view");
    var s = DATA.project.stats;
    v.innerHTML =
      '<header class="hero">' +
      '<p class="hero-kicker">Alpha One · platform specification</p>' +
      '<h1>Prop Firm as a Service — the complete specification</h1>' +
      '<p class="hero-sub">' + esc(DATA.project.tagline) + " — 65 spec docs, the frozen contract pack, and the decision registers. Everything a developer needs to build V1, in one place.</p>" +
      '<div class="hero-meta">' +
      '<span class="chip"><b>' + s.docs + '</b> spec docs</span>' +
      '<span class="chip"><b>' + s.v1_events + '</b> V1 events · ' + s.payloads + ' payload schemas</span>' +
      '<span class="chip"><b>' + s.api_specs + '</b> API contracts</span>' +
      '<span class="chip"><b>' + s.d_rows + '</b> design decisions (D1–D' + s.d_rows + ")</span>" +
      '<span class="chip"><b>' + s.prd_total + '</b> PRD questions</span>' +
      "</div></header>" +
      '<div class="callout info"><strong>What "frozen" means here:</strong> ' + esc(DATA.project.status.frozen) +
      " " + esc(DATA.project.status.open) + "</div>" +
      '<h2>Start here</h2><div class="cards">' +
      card("#/doc/00-executive-brief", "Executive Brief", "What we are building, the non-negotiables, the 12 ADRs in one read.") +
      card("#/doc/01-platform-architecture", "Platform Architecture", "Deployables, tech stack, ADRs, event backbone, request lifecycle.") +
      card("#/doc/99-development-phases", "Development Phases", "The task-level build plan with exit criteria — the program's operating document.") +
      card("#/contracts", "Contract Pack", "Frozen V0 contracts: events, payload schemas, error taxonomy, API specs.") +
      card("#/registers", "Decisions & Questions", "D1–D" + s.d_rows + " design decisions, the 205 PRD questions, triage by owner.") +
      card("#/contracts/diagrams", "Diagrams", "8 committed architecture diagrams (state machines, flows, build order).") +
      "</div>" +
      "<h2>Browse the specification</h2>" +
      "<div id='browse'></div>";
    var browse = $("#browse");
    GROUPS.filter(function (g) { return g[0] !== "contracts" && g[0] !== "registers"; }).forEach(function (g) {
      var docs = DATA.docs.filter(function (d) { return d.group === g[0]; });
      if (!docs.length) return;
      browse.innerHTML += "<div class='doclist' style='margin-top:14px'><h4></h4><ol></ol></div>";
      var dl = browse.lastElementChild;
      dl.querySelector("h4").textContent = g[1] + " (" + docs.length + ")";
      docs.forEach(function (d) {
        var li = document.createElement("li");
        li.innerHTML = "<a href='#/doc/" + d.id + "'><span class='n'></span><span class='t'></span></a>";
        li.querySelector(".n").textContent = d.num;
        li.querySelector(".t").textContent = d.title;
        dl.querySelector("ol").appendChild(li);
      });
    });
    setCrumb("Alpha One — Platform Specification");
    initScroll(v);
  }
  function card(href, title, sub, tag) {
    return "<a class='card' href='" + href + "'><div class='card-tag'>" + esc(tag || title.split(" ")[0]) + "</div><h3>" + esc(title) + "</h3><p>" + esc(sub) + "</p></a>";
  }

  function pageContractsHub() {
    var v = $("#view");
    v.innerHTML =
      "<h1>Contract Pack</h1>" +
      "<p>The frozen V0 contracts (<a href='#/doc/99-development-phases'>docs/99 task 0.10</a>): the machine-readable source of truth for every module. " +
      "CI gates fail the build on drift (error registry, catalog, schema, and payload gates). Generated from <code>contracts/</code> — <a href='../contracts/README.md' target='_blank'>pack README</a>.</p>" +
      "<div class='cards'>" +
      card("#/contracts/events", "Event catalog & payloads", DATA.project.stats.v1_events + " V1 catalog events (39 schemas incl. 2 risk.*) — every payload derived from its owning module doc, with the source cited.") +
      card("#/contracts/errors", "Error taxonomy", "The V1 baseline error codes (dotted domain.action) with owner-rationale resolutions + the extended post-V1 registry.") +
      card("#/contracts/api", "API contracts", DATA.project.stats.api_specs + " module API specs (endpoints, permissions, error codes). 19 are V1-surface; the rest are extended/provisional.") +
      card("#/contracts/diagrams", "Diagrams", "8 committed PNGs: state machines, purchase/payout flows, event bus, build order.") +
      "</div>" +
      "<h2>Event catalog (quick reference)</h2>" +
      "<p>Jump straight to a payload schema — each page shows the derived-from citation, consumers, and the full field table.</p>" +
      "<div id='event-quick'></div>";
    var q = $("#event-quick");
    q.innerHTML = "<div class='doclist'><ol></ol></div>";
    var ol = q.querySelector("ol");
    DATA.contracts.payloads.forEach(function (p) {
      var a = document.createElement("a");
      a.href = "#/contracts/payloads/" + encodeURIComponent(p.event);
      a.innerHTML = "<span class='n'></span><span class='t'></span>";
      a.querySelector(".n").textContent = p.v1 ? "V1" : "ext";
      a.querySelector(".t").textContent = p.event;
      ol.appendChild(a);
    });
    setCrumb("Contract pack");
    initScroll(v);
  }

  function pageCatalog() {
    var v = $("#view");
    v.innerHTML = "<article id='cat-body'></article>";
    var body = $("#cat-body");
    body.innerHTML = renderMd(DATA.contracts.catalog);
    postProcess(body);
    buildRail(body);
    setCrumb("Contracts — event catalog");
    initScroll(v);
  }

  function pagePayload(event) {
    var v = $("#view");
    var p = DATA.contracts.payloads.filter(function (x) { return x.event === decodeURIComponent(event); })[0];
    if (!p) return pageNotFound();
    var rows = p.fields.map(function (f) {
      return "<tr class='" + (f.required ? "req" : "") + "'><td><code>" + esc(f.name) + "</code></td><td>" + esc(f.type) +
        "</td><td>" + (f.required ? "required" : "optional") + "</td><td>" + esc(f.desc || "—") + "</td></tr>";
    }).join("");
    v.innerHTML =
      "<p class='schema-note'>Contract pack → <a href='#/contracts/events'>event catalog</a> → " + esc(p.event) + "</p>" +
      "<h1>" + esc(p.event) + "</h1>" +
      "<div class='hero-meta'><span class='chip'>" + (p.v1 ? "<b>V1 catalog</b>" : "extended") + " · " + esc(p.file) + "</span>" +
      (p.consumers ? "<span class='chip'>consumers: " + esc(p.consumers) + "</span>" : "") + "</div>" +
      (p.source ? "<div class='callout info'><strong>Derived from:</strong> " + esc(p.source) +
        " — field names per docs/32 DDL; money is integer minor units (docs/00 non-negotiable #3).</div>" : "") +
      "<h2>Envelope</h2><p>Every event carries the <code>EVT-03</code> envelope: <code>id</code> (ULID), <code>type</code> (const = event name), <code>version</code> (1), <code>tenant_id</code>, <code>occurred_at</code>, <code>payload</code> (below). See <a href='../contracts/events/payloads/envelope.schema.json' target='_blank'>envelope.schema.json</a>.</p>" +
      "<h2>payload fields</h2>" +
      "<table><thead><tr><th>Field</th><th>Type</th><th>Cardinality</th><th>Description</th></tr></thead><tbody>" + rows + "</tbody></table>" +
      "<h2>Raw schema (JSON Schema 2020-12)</h2><div id='rawjson'></div>" +
      "<footer class='page-foot'><p>Source: <a href='../contracts/events/" + esc(p.file) + "' target='_blank'>contracts/events/" + esc(p.file) + "</a> · enforced by <code>scripts/check_event_payloads.py</code></p></footer>";
    var raw = $("#rawjson");
    raw.innerHTML = "<div class='codeblock'><div class='codehead'><span class='lang'>json</span><span class='fname'></span><button class='copybtn' type='button'>copy</button></div><pre><code></code></pre></div>";
    raw.querySelector(".fname").textContent = p.file;
    raw.querySelector("code").textContent = p.json;
    raw.querySelector(".copybtn").addEventListener("click", function () { copyText(p.json, this); });
    setCrumb("Payload — " + p.event);
    initScroll(v);
  }

  function pageTaxonomy() {
    var v = $("#view");
    v.innerHTML = "<article id='tax-body'></article>";
    var body = $("#tax-body");
    body.innerHTML = renderMd(DATA.contracts.taxonomy);
    postProcess(body);
    buildRail(body);
    setCrumb("Contracts — error taxonomy");
    initScroll(v);
  }

  function pageApiIndex() {
    var v = $("#view");
    v.innerHTML = "<h1>API contracts</h1>" +
      "<p>" + DATA.contracts.api.length + " module API specs. <span class='badge v1'>V1</span> = V1-surface contracts (frozen at 0.10); " +
      "<span class='badge ext'>ext</span> = extended (post-V1) design-level, provisional until that phase's freeze (docs/99 §12).</p>" +
      "<div class='doclist' style='max-height:640px;overflow-y:auto'><ol></ol></div>";
    var ol = v.querySelector("ol");
    DATA.contracts.api.forEach(function (a) {
      var row = document.createElement("a");
      row.className = "eventrow";
      row.href = "#/contracts/api/" + a.name;
      row.innerHTML = "<span class='ename'></span><span class='emeta'></span><span>" +
        (a.v1 ? "<span class='badge v1'>V1</span>" : "<span class='badge ext'>ext</span>") + "</span>";
      row.querySelector(".ename").textContent = a.name;
      row.querySelector(".emeta").textContent = a.label;
      ol.appendChild(row);
    });
    setCrumb("Contracts — API contracts");
    initScroll(v);
  }

  function pageApi(name) {
    var v = $("#view");
    var a = DATA.contracts.api.filter(function (x) { return x.name === name; })[0];
    if (!a) return pageNotFound();
    v.innerHTML = "<article id='api-body'></article>";
    var body = $("#api-body");
    body.innerHTML = renderMd(a.content);
    postProcess(body);
    buildRail(body);
    setCrumb("API contract — " + a.label);
    initScroll(v);
  }

  function pageDiagrams() {
    var v = $("#view");
    var cards = DATA.contracts.diagrams.map(function (d) {
      return "<a class='dia' href='../contracts/diagrams/" + d.png + "' target='_blank'><img src='../contracts/diagrams/" + d.png +
        "' alt='" + esc(d.name) + "' loading='lazy'><div class='dia-cap'></div><div class='dia-cites'></div></a>";
    }).join("");
    v.innerHTML = "<h1>Diagrams</h1>" +
      "<p>8 committed architecture diagrams (Mermaid sources in <code>contracts/diagrams/*.md</code>, rendered PNGs committed in-repo — " +
      "re-render with mermaid-cli when a source changes; a PNG that contradicts its source is a contract defect). Click to open full-size.</p>" +
      "<div class='diagrid'>" + cards + "</div>" +
      "<footer class='page-foot'><p><a href='../contracts/diagrams/README.md' target='_blank'>contracts/diagrams/README.md</a> — rendering tool, PNG strategy, staleness rules.</p></footer>";
    $$(".dia", v).forEach(function (d) {
      var data = DATA.contracts.diagrams.filter(function (x) {
        return d.querySelector("img").getAttribute("src").indexOf(x.png) !== -1;
      })[0];
      d.querySelector(".dia-cap").textContent = data.name;
      d.querySelector(".dia-cites").textContent = data.cites;
    });
    setCrumb("Contracts — diagrams");
    initScroll(v);
  }

  function pageRegisters(tab) {
    var v = $("#view");
    var r = DATA.registers;
    var dqOpen = r.design_questions.filter(function (q) { return openAns(q.answer); }).length;
    var prdOpen = r.prd_questions.filter(function (q) { return openAns(q.answer); }).length;
    var tabs = ["", "d", "prd", "triage"];
    var tabLabel = ["Overview", "Design decisions", "PRD questions", "Triage"];
    var i = Math.max(0, tabs.indexOf(tab || ""));
    v.innerHTML = "<h1>Decisions & open questions</h1>" +
      "<div class='filterbar' style='border:none'>" +
      tabs.map(function (t, j) {
        return "<a class='tbtn" + (j === i ? "' style='border-color:var(--accent);color:var(--accent)'" : "") + "' href='#/registers" + (t ? "/" + t : "") + "'>" + tabLabel[j] + "</a>";
      }).join("") + "</div><div id='reg-body'></div>";
    var body = $("#reg-body");
    if (i === 0) pageRegOverview(body, r, dqOpen, prdOpen);
    else if (i === 1) pageRegDecisions(body, r);
    else if (i === 2) pageRegPrd(body, r);
    else pageRegTriage(body, r);
    postProcess(body);
    setCrumb("Registers — " + tabLabel[i]);
    initScroll(v);
  }
  function openAns(a) { var t = (a || "").trim().replace(/^[\*_\s]+/, ""); return !t || t.toLowerCase().indexOf("open") === 0; }

  function pageRegOverview(body, r, dqOpen, prdOpen) {
    var s = DATA.project.stats;
    body.innerHTML =
      "<div class='callout info'><strong>Register state (" + esc(DATA.generated) + "):</strong> " +
      "<b>" + s.d_rows + "</b> design-review questions (D1–D" + s.d_rows + ") — <span class='badge ok'>" + (s.d_rows - dqOpen) + " answered</span> <span class='badge open'>" + dqOpen + " open</span>; " +
      "<b>" + s.prd_total + "</b> PRD questions — <span class='badge ok'>" + (s.prd_total - prdOpen) + " answered</span> <span class='badge open'>" + prdOpen + " open</span>.</div>" +
      "<div class='cards'>" +
      card("#/registers/d", "Design decisions (D1–D" + s.d_rows + ")", "Team decisions from design review — answered rows are binding for contract freeze (the D-number convention).") +
      card("#/registers/prd", "PRD open questions (205)", "Every question the PRD raised, grouped by module. Open rows must close before the owning module's freeze (docs/99 §12).") +
      card("#/registers/triage", "Triage — who can answer", "All " + prdOpen + " open PRD questions assigned to the stakeholder who can answer them; 43 carry 'Proposed — pending sign-off'.") +
      card("#/doc/37a-stakeholder-questions-for-funderblu", "Stakeholder hand-off (docs/37a)", "The flat hand-off document for FunderBlu's owners — reply per question; decisions land as workbook answers or D-rows.") +
      "</div>" +
      "<p>Rule of the register (docs/62): <em>an answer is a decision</em> — it lands only with a real owner decision, then the owning module doc is updated in the same change. Nothing is marked answered by default.</p>";
  }

  function pageRegDecisions(body, r) {
    var openN = r.design_questions.filter(function (q) { return openAns(q.answer); }).length;
    var html = "<div class='filterbar'><input type='search' id='dq-q' placeholder='Filter decisions…'> " +
      "<select id='dq-f'><option value='all'>All (" + r.design_questions.length + ")</option><option value='open'>Open (" + openN + ")</option><option value='answered'>Answered</option></select></div>" +
      "<div class='countline' id='dq-count'></div><div id='dq-list'></div>";
    body.innerHTML = html;
    function draw() {
      var q = $("#dq-q").value.trim().toLowerCase();
      var f = $("#dq-f").value;
      var list = $("#dq-list");
      var n = 0;
      list.innerHTML = "";
      r.design_questions.forEach(function (d) {
        var isOpen = openAns(d.answer);
        if (f === "open" && !isOpen) return;
        if (f === "answered" && isOpen) return;
        var hay = (d.id + " " + d.section + " " + d.question + " " + (d.answer || "")).toLowerCase();
        if (q && hay.indexOf(q) === -1) return;
        n++;
        var el = document.createElement("details");
        el.className = "drow";
        var summary = (d.question || "").length > 150 ? d.question.slice(0, 147) + "…" : (d.question || "");
        el.innerHTML = "<summary><span class='did'></span><span class='dsum'></span><span>" +
          (isOpen ? "<span class='badge open'>open</span>" : "<span class='badge ok'>answered</span>") + "</span></summary>" +
          "<div class='dbody'><p class='meta'></p><p class='dquest'></p>" +
          (d.answer ? "<p class='danswer'></p>" : "") + "</div>";
        el.querySelector(".did").textContent = d.id;
        el.querySelector(".dsum").textContent = summary;
        el.querySelector(".meta").textContent = "source doc " + d.source_doc + " · " + (d.section || "") + " · owner: " + (d.owner || "—") + " · deadline: " + (d.deadline || "—");
        el.querySelector(".dquest").textContent = d.question;
        if (d.answer) el.querySelector(".danswer").textContent = d.answer;
        list.appendChild(el);
      });
      $("#dq-count").textContent = n + " of " + r.design_questions.length + " decisions";
    }
    $("#dq-q").addEventListener("input", draw);
    $("#dq-f").addEventListener("change", draw);
    draw();
  }

  function pageRegPrd(body, r) {
    var openN = r.prd_questions.filter(function (q) { return openAns(q.answer); }).length;
    var sections = {};
    r.prd_questions.forEach(function (q) {
      (sections[q.section || "Unfiled"] = sections[q.section || "Unfiled"] || []).push(q);
    });
    body.innerHTML = "<div class='filterbar'><input type='search' id='pq-q' placeholder='Filter questions…'> " +
      "<select id='pq-f'><option value='all'>All (" + r.prd_questions.length + ")</option><option value='open'>Open (" + openN + ")</option><option value='answered'>Answered</option></select>" +
      "<select id='pq-s'><option value=''>All sections</option>" +
      Object.keys(sections).sort().map(function (s) { return "<option>" + esc(s) + "</option>"; }).join("") +
      "</select></div><div class='countline' id='pq-count'></div><div id='pq-list'></div>";
    function draw() {
      var q = $("#pq-q").value.trim().toLowerCase();
      var f = $("#pq-f").value;
      var sec = $("#pq-s").value;
      var list = $("#pq-list");
      var n = 0;
      list.innerHTML = "";
      Object.keys(sections).sort().forEach(function (s) {
        if (sec && s !== sec) return;
        var rows = sections[s].filter(function (row) {
          var isOpen = openAns(row.answer);
          if (f === "open" && !isOpen) return false;
          if (f === "answered" && isOpen) return false;
          if (q && (row.question + " " + (row.answer || "")).toLowerCase().indexOf(q) === -1) return false;
          return true;
        });
        if (!rows.length) return;
        n += rows.length;
        var div = document.createElement("div");
        div.innerHTML = "<h3 style='margin-top:26px'></h3><table><thead><tr><th style='width:36px'>#</th><th>Question</th><th style='width:110px'>Owner</th><th style='width:110px'>Deadline</th><th>Answer</th></tr></thead><tbody></tbody></table>";
        div.querySelector("h3").textContent = s + " (" + rows.length + ")";
        var tb = div.querySelector("tbody");
        rows.forEach(function (row, i) {
          var tr = document.createElement("tr");
          tr.innerHTML = "<td>" + (i + 1) + "</td><td></td><td></td><td></td><td></td>";
          tr.children[1].textContent = row.question;
          tr.children[2].textContent = row.owner || "—";
          tr.children[3].textContent = row.deadline || "—";
          var ans = (row.answer || "").trim();
          tr.children[4].innerHTML = openAns(ans) ? "<span class='badge open'>open</span>" : "<span class='badge ok'>answered</span><br><span style='font-size:12.5px'>" + esc(ans) + "</span>";
          tb.appendChild(tr);
        });
        list.appendChild(div);
      });
      $("#pq-count").textContent = n + " of " + r.prd_questions.length + " questions";
    }
    $("#pq-q").addEventListener("input", draw);
    $("#pq-f").addEventListener("change", draw);
    $("#pq-s").addEventListener("change", draw);
    draw();
  }

  function pageRegTriage(body, r) {
    var t = r.triage;
    var rows = t.rows || [];
    var counts = {};
    rows.forEach(function (x) { counts[x.bucket] = (counts[x.bucket] || 0) + 1; });
    var internal = t.internal_bucket;
    body.innerHTML = "<p>" + esc(t.note || "") + "</p><div class='countline'></div><div class='cards' id='tri-cards'></div>" +
      "<h2>Internal — Tech-Lead can decide now (" + (counts[internal] || 0) + ")</h2><div class='countline'>Each carries a proposed answer marked <em>Proposed — pending sign-off</em> — it becomes a decision only when the owner signs off (D-number convention).</div>" +
      "<div id='tri-list'></div>";
    body.querySelector(".countline").textContent = rows.length + " open PRD questions → " + Object.keys(counts).length + " stakeholder buckets. Full hand-off: ";
    var al = document.createElement("a");
    al.href = "#/doc/37a-stakeholder-questions-for-funderblu";
    al.textContent = "docs/37a (flat, grouped by stakeholder)";
    body.querySelector(".countline").appendChild(al);
    var cards = $("#tri-cards");
    (t.buckets || []).forEach(function (b) {
      var c = document.createElement("a");
      c.className = "card"; c.href = "#/registers/prd";
      c.innerHTML = "<div class='card-tag'></div><h3></h3><p></p>";
      c.querySelector(".card-tag").textContent = b === internal ? "internal" : "stakeholder";
      c.querySelector("h3").textContent = (counts[b] || 0) + " questions";
      c.querySelector("p").textContent = b;
      cards.appendChild(c);
    });
    var list = $("#tri-list");
    rows.filter(function (x) { return x.bucket === internal; }).forEach(function (x) {
      var el = document.createElement("details");
      el.className = "drow";
      el.innerHTML = "<summary><span class='did'></span><span class='dsum'></span></summary><div class='dbody'><p class='meta'></p><p class='dquest'></p><p class='danswer'></p></div>";
      el.querySelector(".did").textContent = x.section.replace(/ .*/, "").slice(0, 12);
      el.querySelector(".dsum").textContent = x.q.length > 150 ? x.q.slice(0, 147) + "…" : x.q;
      el.querySelector(".meta").textContent = x.section;
      el.querySelector(".dquest").textContent = x.q;
      el.querySelector(".danswer").textContent = x.note;
      list.appendChild(el);
    });
  }

  function pageNotFound() {
    $("#view").innerHTML = "<h1>Not found</h1><p>That page does not exist. <a href='#/'>Back to the overview</a>.</p>";
  }

  /* ---------- router ---------- */
  function route() {
    var h = parseHash();
    if (!DATA) return;
    window.scrollTo(0, 0);
    /* reset doc highlight */
    $$("#sb-nav a[data-doc]").forEach(function (a) { a.classList.remove("active"); });
    if (h.route === "doc" && h.arg) pageDoc(h.arg);
    else if (h.route === "contracts" && h.arg === "events") pageCatalog();
    else if (h.route === "contracts" && h.arg === "payloads" && h.sub) pagePayload(h.sub);
    else if (h.route === "contracts" && h.arg === "errors") pageTaxonomy();
    else if (h.route === "contracts" && h.arg === "api" && h.sub) pageApi(h.sub);
    else if (h.route === "contracts" && h.arg === "api") pageApiIndex();
    else if (h.route === "contracts" && h.arg === "diagrams") pageDiagrams();
    else if (h.route === "contracts") pageContractsHub();
    else if (h.route === "registers") pageRegisters(h.arg);
    else pageHome();
  }

  /* ---------- boot ---------- */
  function boot() {
    buildSidebar();
    /* theme */
    $("#theme-toggle").addEventListener("click", function () {
      var cur = document.documentElement.dataset.theme === "light" ? "dark" : "light";
      document.documentElement.dataset.theme = cur;
      try { localStorage.setItem("a1-theme", cur); } catch (e) {}
    });
    /* drawer */
    var ham = $("#hamburger");
    ham.addEventListener("click", function () {
      var open = !document.body.classList.contains("nav-open");
      document.body.classList.toggle("nav-open", open);
      ham.setAttribute("aria-expanded", open ? "true" : "false");
    });
    $("#overlay").addEventListener("click", function () { document.body.classList.remove("nav-open"); });
    $$("#sb-nav a").forEach(function (a) {
      a.addEventListener("click", function () { if (window.innerWidth <= 900) document.body.classList.remove("nav-open"); });
    });
    /* totop */
    $("#totop").addEventListener("click", function () { window.scrollTo({ top: 0, behavior: "smooth" }); });
    /* keyboard */
    window.addEventListener("keydown", function (e) {
      var typing = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement && document.activeElement.tagName);
      if (typing) return;
      if (e.key === "/") { e.preventDefault(); $("#nav-search").focus(); }
      else if (e.key === "t") { $("#theme-toggle").click(); }
    });
    window.addEventListener("hashchange", route);
    route();
  }
  DATA_READY.then(boot);
})();
"""

# --------------------------------------------------------------------------- #
def main() -> None:
    data = collect()
    SITE.mkdir(exist_ok=True)
    (SITE / "data").mkdir(exist_ok=True)
    (SITE / "vendor").mkdir(exist_ok=True)
    (SITE / "data" / "site-data.json").write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    # vendor marked (from the npm pack if present, else keep existing)
    src = None
    for cand in [
        pathlib.Path("/tmp/vendor/package/marked.min.js"),
        ROOT.parent / "node_modules" / "marked" / "lib" / "marked.min.js",
    ]:
        if cand.is_file():
            src = cand
            break
    if src is not None:
        shutil.copyfile(src, SITE / "vendor" / "marked.min.js")
    else:
        assert (SITE / "vendor" / "marked.min.js").is_file(), "marked.min.js not found"
    (SITE / "index.html").write_text(INDEX, encoding="utf-8")
    (SITE / "styles.css").write_text(CSS, encoding="utf-8")
    (SITE / "app.js").write_text(JS, encoding="utf-8")
    s = data["project"]["stats"]
    print("wrote alpha-one/site/:")
    for f in ["index.html", "styles.css", "app.js", "vendor/marked.min.js", "data/site-data.json"]:
        p = SITE / f
        print(f"  {f:26s} {p.stat().st_size/1024:8.1f} KB")
    print(f"  docs={s['docs']} payloads={s['payloads']} api={s['api_specs']} "
          f"d_rows={s['d_rows']} prd={s['prd_total']}")


if __name__ == "__main__":
    main()

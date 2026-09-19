#!/usr/bin/env python3
"""Build the contracts/ pack from the module docs.
- shared/openapi.yaml : shared OpenAPI components (envelope, errors, pagination,
                        event envelope, common types, security schemes, responses)
- <nn>-<slug>.openapi.yaml : one OpenAPI 3.1 spec per module (endpoints extracted
                        from each module doc, $ref-ing shared components)
- events/<topic>.schema.json : canonical JSON Schema (2020-12) per event topic,
                        one $def per event, from doc 31
- README.md : how to read the pack + versioning rules
"""
import re, json, pathlib, yaml, collections

ROOT = pathlib.Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
CON = ROOT / "contracts"
CON.mkdir(exist_ok=True)
(CON / "shared").mkdir(exist_ok=True)
(CON / "events").mkdir(exist_ok=True)

MODULES = [
    ("02","02-identity-access","AUTH","Identity & Access", "Authentication, authorization, multi-tenant identity, sessions, MFA, API keys."),
    ("03","03-tenant-management","TEN","Tenant Management","Tenant lifecycle, white-label, entitlements, creation saga."),
    ("04","04-gateway-events","GW+EVT","Gateway & Events","API gateway middleware chain, outbox, relay, event bus, webhooks, SSE."),
    ("05","05-ledger-audit","LED+AUD","Ledger & Audit","Double-entry ledger, append-only audit, reconciliation, snapshots."),
    ("06","06-devops-deployment","OPS","DevOps & Deployment","Infra, CI/CD, environments, observability, DR, health endpoints."),
    ("07","07-account-lifecycle","LCC","Account Lifecycle","Trader account state machine, phases, activation, enforcement."),
    ("08","08-trading-bridge","BRG","Trading Bridge","Broker connectors (MT5 via MetaApi), sync, provisioning, enforcement commands."),
    ("09","09-evaluation-engine","EVL","Evaluation Engine","Rule packs, verdicts, drawdowns, day boundaries (Rust service)."),
    ("10","10-risk-management","RSK","Risk Management","Fraud/anti-gaming detectors, signals, cases, holds."),
    ("11","11-payout-system","PAY","Payout System","Payout requests, eligibility, approvals, rails, reconciliation, HWM."),
    ("12","12-checkout-billing","CHK","Checkout & Billing","Checkout, pricing, orders, payment providers, refunds, capture-matching."),
    ("13","13-kyc","KYC","KYC Verification","L1/L2 verification, provider adapters, document handling, reverify."),
    ("14","14-notifications","NOT","Notifications","Channels, templates, in-app, push, preferences, dedupe."),
    ("15","15-documents","DOC","Document Generation","Certificates, statements, PDFs (Puppeteer), storage, mappers."),
    ("16","16-trader-dashboard","TD","Trader Dashboard","Trader portal (FE) API surface: equity, rules, payout, documents."),
    ("17","17-admin-panel","ADM","Admin Panel","Tenant admin panel: traders, accounts, payouts, KYC, exports."),
    ("18","18-support","SUP","Support","Tickets, SLAs, categories, money-linked resolve, chat intake."),
    ("19","19-analytics","ANA","Analytics & BI","Read models, reports, KPIs, as_of, exports."),
    ("20","20-crm","CRM","CRM & Communications","Segments, campaigns, sequences, consent, RSK-exclusion."),
    ("21","21-console","CON","Platform Console","Platform (super-admin) console: tenants, audit review, incidents."),
    ("22","22-billing","BIL","Tenant Billing","Usage metering, invoicing, pass-through, dunning."),
    ("23","23-affiliates","AFF","Affiliates","Referrals, commissions, rate cards, reversals, self-referral."),
    ("24","24-cms-competitions","CMS+CMP","CMS & Competitions","Tenant site blocks, landing pages, contests, scoring, prizes."),
    ("25","25-migration","MIG","Migration","TTS to Alpha One cutover and data migration pipeline."),
    ("26","26-mobile-apps","MOB/JRN/EDU/CHT","Mobile, Journal, Education, Community","RN app, journal, education, community chat (V2+)."),
    ("27","27-ecosystem","SDK/DVP/TRD/PLT/CS","Ecosystem","Public SDK, developer portal, advanced trading, platform ops, customer success (V3)."),
]

# ---------------------------------------------------------------- endpoints
EP_RE = re.compile(r"`?([A-Z][A-Z|]*) (/(?:(?:v[0-9]+|internal|dvp|webhooks|sandbox)(?:\{[^{}]*\}|[^\s`|)\]{}])*|healthz|readyz))`?")
ENUM_PLACEHOLDER_RE = re.compile(r"\{[a-z0-9_]+(?:\|[a-z0-9_]+)+\}")

def _v1_zone(text):
    """Return (start, end) char offsets of the V1 baseline zone: from the first
    '### 7.1' heading to the '### 7.N Extended' heading (or '## 8.' if absent).
    A module may have several 7.x V1 subsections (e.g. LED+AUD)."""
    m1 = re.search(r"^### 7\.1[^\n]*\n", text, re.M)
    if not m1:
        return -1, -1
    start = m1.end()
    rest = text[start:]
    m2 = re.search(r"^### 7\.\d+[^\n]*Extended[^\n]*$", rest, re.M)
    m8 = re.search(r"^## 8\.", rest, re.M)
    ends = [x.start() for x in (m2, m8) if x]
    end = min(ends) if ends else len(text)
    return start, start + end

def extract_endpoints(fname):
    """Return [ {meth, path, summary, phase, v1_errors, permission, idempotency, auth} ].
    V1 operations come from the doc's §7.1 zone (authoritative:
    contracts/api/<mod>.md); everything else is the extended (post-V1)
    surface (phase='extended')."""
    text = (DOCS / (fname + ".md")).read_text()
    zs, ze = _v1_zone(text)
    v1z = text[zs:ze] if zs != -1 else ""
    out, seen = [], set()
    # pass 1: the V1 baseline table rows
    for line in v1z.splitlines():
        if not line.strip().startswith("|"):
            continue
        parts = [p.strip() for p in line.strip().strip("|").split("|")]
        if len(parts) < 2 or set(parts[0]) <= set("-: ") or parts[0].startswith("Method"):
            continue
        m = re.match(r"^`?([A-Z]+) (\S+?)`?$", parts[0].strip())
        if not m:
            continue
        meth, path = m.group(1), m.group(2).split("?")[0]
        if meth not in ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"):
            continue
        if (meth, path) in seen:
            continue
        seen.add((meth, path))
        auth = parts[1] if len(parts) > 1 else ""
        perm_cell = parts[2] if len(parts) > 2 else ""
        idem_cell = parts[3] if len(parts) > 3 else ""
        errs_cell = parts[4] if len(parts) > 4 else ""
        perm = re.search(r"`([a-z0-9_.]+)`", perm_cell)
        errs = re.findall(r"`([a-z0-9_.]+)`", errs_cell)
        out.append({"meth": meth, "path": path, "summary": "", "phase": "V1",
                    "auth": auth, "permission": perm.group(1) if perm else None,
                    "idempotency": idem_cell.replace("`", "").strip() or "n/a",
                    "v1_errors": errs})
    # pass 2: the rest of the doc (extended surface, old shorthand style),
    # with the V1 zone blanked out so its tokens are not re-picked
    if zs != -1:
        text = text[:zs] + " " * (ze - zs) + text[ze:]
    real_matches = list(EP_RE.finditer(text))
    for i, m in enumerate(real_matches):
        methods, path = m.group(1), m.group(2)
        end = m.end()
        nxt = real_matches[i + 1].start(2) if i + 1 < len(real_matches) else len(text)
        if nxt - end > 220:
            line_end = text.find("\n", end)
            nxt = end if line_end == -1 else min(nxt, line_end)
        desc = text[end:nxt].split("\n")[0]
        desc = desc.strip()
        mpar = re.match(r"^\(([^()]*)\)\s*,?\s*(.*)$", desc)
        if mpar:  # unwrap a leading parenthetical: "(V2), POST" -> "V2 \u2014 POST"
            head, tail = mpar.group(1).strip(), mpar.group(2).strip()
            desc = (head + (" \u2014 " + tail if tail else "")).strip()
        desc = desc.lstrip("(),;:\u2014\u2013- ").strip()
        desc = re.sub(r"`", "", desc)
        desc = re.sub(r"\s+", " ", desc).strip().rstrip(".,;").strip().rstrip("\u2014\u2013-").strip()
        if len(desc) < 6 or re.fullmatch(r"[A-Z][A-Z|+\s]*", desc):
            desc = ""  # bare method/version fragments -> "Title METHOD path" fallback
        path = path.rstrip("`").split("?")[0]
        for meth in methods.split("|"):
            if meth not in ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"):
                continue
            key = (meth, path)
            if key in seen:
                continue
            seen.add(key)
            out.append({"meth": meth, "path": path, "summary": desc, "phase": "extended",
                        "auth": "", "permission": None, "idempotency": "", "v1_errors": []})
    return out

def infer_tag(path):
    p = path.lower()
    if p.startswith("/v1/internal") or "/internal/" in p:
        return "internal"
    if "/webhooks/" in p:
        return "webhook"
    if p.startswith("/v1/public") or "/public/" in p or p.startswith("/v1/sandbox"):
        return "public"
    if "/dvp" in p or "/v1/dvp" in p:
        return "dvp"
    if p.startswith("/v1/admin") or "/admin/" in p:
        return "admin"
    if p.startswith("/v1/con") or "/console/" in p:
        return "console"
    return "core"

NO_AUTH_PATHS = {"/healthz", "/readyz", "/v1/openapi.json"}

def infer_security(tag, path=""):
    if path in NO_AUTH_PATHS:
        return []  # unauthenticated (probes/docs)
    if tag == "internal":
        return [{"internalService": []}]
    if tag in ("public", "dvp"):
        return [{"apiKeyAuth": []}]
    if tag == "webhook":
        return []  # verified by signature header, not token
    return [{"sessionAuth": []}]

def slugify(method, path):
    return re.sub(r"[^a-z0-9]+", "_", (method + path).lower()).strip("_")

def normalize_path(path):
    """Return (normalized_path, [{name, enum}]).
    - an enum placeholder {a|b|c} -> a single {a} param recording the enum
    - repeated param names -> {id}, {id_2}, ...
    """
    out = []
    last = 0
    params = []
    used = set()
    for m in re.finditer(r"\{([^{}]+)\}", path):
        out.append(path[last:m.start()])
        raw = m.group(1)
        if "|" in raw:  # enum placeholder
            name = raw.split("|")[0].strip()
            enum = [v.strip() for v in raw.split("|")]
        else:
            name = raw.strip()
            enum = None
        if name in used:
            k = 2
            while f"{name}_{k}" in used:
                k += 1
            name = f"{name}_{k}"
        used.add(name)
        params.append({"name": name, "enum": enum})
        out.append("{%s}" % name)
        last = m.end()
    out.append(path[last:])
    return "".join(out), params

def build_module_spec(num, fname, mod, title, blurb):
    eps = extract_endpoints(fname)
    paths = dict()
    tags_used = set()
    counter = collections.defaultdict(int)
    used_opids = set()
    n_v1 = sum(1 for e in eps if e["phase"] == "V1")
    for ep in eps:
        meth, path, summary = ep["meth"], ep["path"], ep["summary"]
        tag = infer_tag(path)
        tags_used.add(tag)
        npath, pparams = normalize_path(path)
        ops = paths.setdefault(npath, {})
        counter[tag] += 1
        base = slugify(meth, npath)
        pid, k = base, 2
        while pid in used_opids:
            pid = f"{base}_{k}"
            k += 1
        used_opids.add(pid)
        params = []
        for pp in pparams:
            schema = {"type": "string"}
            if pp.get("enum"):
                schema["enum"] = pp["enum"]
                schema["description"] = "enum: " + " | ".join(pp["enum"])
            params.append({"name": pp["name"], "in": "path", "required": True,
                           "schema": schema})
        op = {
            "tags": [tag],
            "summary": summary or (title + " " + meth + " " + npath),
            "operationId": pid,
            "x-phase": ep["phase"],
        }
        if ep["phase"] == "V1":
            op["x-v1-baseline"] = "contracts/api/" + API_NAME.get(num, num + ".md")
        if ep.get("permission"):
            op["x-permission"] = ep["permission"]
        if ep.get("idempotency"):
            op["x-idempotency"] = ep["idempotency"]
        if ep.get("auth"):
            op["x-auth"] = ep["auth"]
        if ep.get("v1_errors"):
            op["x-v1-errors"] = ep["v1_errors"]
        if params:
            op["parameters"] = params
        sec = infer_security(tag, npath)
        if sec:
            op["security"] = sec
        if meth in ("POST", "PUT", "PATCH"):
            op["requestBody"] = {
                "required": True,
                "content": {"application/json": {"schema": {"$ref": "shared/openapi.yaml#/components/schemas/JsonObject"}}},
            }
        op["responses"] = {
            "200": {"description": "Success (see module doc for the canonical shape)",
                    "content": {"application/json": {"schema": {"$ref": "shared/openapi.yaml#/components/schemas/JsonObject"}}}},
            "default": {"$ref": "shared/openapi.yaml#/components/responses/Error"},
        }
        if tag in ("public", "dvp"):
            op["responses"]["401"] = {"$ref": "shared/openapi.yaml#/components/responses/Unauthorized"}
            op["responses"]["403"] = {"$ref": "shared/openapi.yaml#/components/responses/Forbidden"}
            op["responses"]["429"] = {"$ref": "shared/openapi.yaml#/components/responses/RateLimited"}
        elif tag == "internal":
            op["responses"]["503"] = {"$ref": "shared/openapi.yaml#/components/responses/ServiceUnavailable"}
        else:
            op["responses"]["401"] = {"$ref": "shared/openapi.yaml#/components/responses/Unauthorized"}
            op["responses"]["403"] = {"$ref": "shared/openapi.yaml#/components/responses/Forbidden"}
            op["responses"]["404"] = {"$ref": "shared/openapi.yaml#/components/responses/NotFound"}
        ops[meth.lower()] = op
    tag_list = [{"name": t, "description": TAGDESC.get(t, t)} for t in
                sorted(tags_used, key=lambda x: -counter[x])]
    spec = {
        "openapi": "3.1.0",
        "info": {
            "title": f"Alpha One — {mod} ({title})",
            "version": "1.0.0",
            "description": (f"{blurb}\n\n"
                            f"Module doc: [docs/{fname}.md](../docs/{fname}.md). "
                            f"V1 baseline: operations with `x-phase: V1` are the V1 "
                            f"execution-sheet contract (see the doc's §7.1 and "
                            f"contracts/api/{API_NAME.get(num, 'n/a')}); `x-phase: extended` "
                            f"operations are the post-V1 design surface (provisional URL plan). "
                            f"Error codes: [docs/30-error-taxonomy.md](../docs/30-error-taxonomy.md) "
                            f"({mod} namespace; the V1 set in contracts/errors/taxonomy.md). "
                            f"Events: [docs/31-event-catalog.md](../docs/31-event-catalog.md). "
                            f"Schema: [docs/32-database-design.md](../docs/32-database-design.md)."),
        },
        "servers": [{"url": "https://api.staging.alphaone.example", "description": "Staging (synthetic data only)"}],
        "tags": tag_list,
        "paths": paths,
        "components": {
            "schemas": {
                "JsonObject": {
                    "description": "Module-specific object. The canonical shape is defined in the module doc's §8 (Schema); this generic reference is a contract-pack placeholder until the module's schema is inlined.",
                    "type": "object",
                    "additionalProperties": True,
                },
            },
            "securitySchemes": {
                name: {"$ref": f"shared/openapi.yaml#/components/securitySchemes/{name}"}
                for name in ("sessionAuth", "apiKeyAuth", "internalService", "webhookSignature")
            },
        },
    }
    return spec

# module -> contracts/api/<name>.md (the V1 baseline contract file)
API_NAME = {
    "02": "auth.md", "03": "tenant.md", "04": "gw.md", "05": "led.md + contracts/api/aud.md",
    "06": "ops.md", "07": "lcc.md", "08": "brg.md", "09": "evl.md", "10": "rsk.md",
    "11": "pay.md", "12": "chk.md", "13": "kyc.md", "14": "not.md", "15": "doc.md",
    "16": "td.md", "17": "adm.md", "19": "ana.md", "21": "con.md",
}

TAGDESC = {
    "core": "Core domain endpoints (trader + shared)",
    "admin": "Tenant admin (ADM) surface",
    "console": "Platform console (CON) surface",
    "public": "Public API (key-authed, the SDK/DVP surface)",
    "dvp": "Developer portal surface",
    "internal": "Service-to-service / worker / provider-webhook",
    "webhook": "Inbound provider webhook (signature-verified)",
}

# ---------------------------------------------------------------- shared
SHARED = {
    "openapi": "3.1.0",
    "info": {
        "title": "Alpha One — Shared Contract Components",
        "version": "1.0.0",
        "description": ("Shared OpenAPI components referenced by every module spec "
                        "via `shared/openapi.yaml#/components/...`. "
                        "Global conventions: docs/30 (error taxonomy), docs/31 (events), "
                        "docs/04 §6 (the error contract)."),
    },
    "paths": {},
    "components": {
        "securitySchemes": {
            "sessionAuth": {
                "type": "http", "scheme": "bearer",
                "description": "ZITADEL access token (short-lived JWT issued by the identity provider, ADR-13; verified over JWKS with the audience of the caller's realm, rotating refresh, server-side revocation via our deny-set + auth_sessions projection, AUTH-07). V1: the tenant is resolved from the request domain/subdomain only (GW-02, TEN-02); extended (V2+): header for internal calls, API-key binding.",
            },
            "apiKeyAuth": {
                "type": "apiKey", "in": "header", "name": "Authorization",
                "description": "Public API key (sk_live_t_… / sk_test_…). Scopes + rate tiers per key. Two secrets: the API key auths calls, the webhook secret signs deliveries.",
            },
            "internalService": {
                "type": "apiKey", "in": "header", "name": "X-Internal-Token",
                "description": "Service-to-service token (internal Compose network only). Never exposed past the perimeter.",
            },
            "webhookSignature": {
                "type": "apiKey", "in": "header", "name": "X-AlphaOne-Signature",
                "description": "Outbound webhook HMAC-SHA256 over ts + '.' + raw body (the 04 §5.6 / 27 §3.2 contract). Timestamp tolerance ±5 min.",
            },
        },
        "parameters": {
            "XIdempotencyKey": {"name": "Idempotency-Key", "in": "header", "required": False,
                                "description": "Client idempotency key (04 §3.3). Duplicate key returns the original result.",
                                "schema": {"type": "string"}},
            "XRequestId": {"name": "X-Request-Id", "in": "header", "required": False,
                           "description": "Correlation id, echoed in the response + audit.", "schema": {"type": "string"}},
            "Cursor": {"name": "cursor", "in": "query", "required": False,
                       "description": "Opaque pagination cursor.", "schema": {"type": "string"}},
            "Limit": {"name": "limit", "in": "query", "required": False,
                      "description": "Page size.", "schema": {"type": "integer", "minimum": 1, "maximum": 200, "default": 50}},
            "AsOf": {"name": "as_of", "in": "query", "required": False,
                     "description": "Point-in-time read (epoch ms). Read models are as_of-labeled (ANA-14).",
                     "schema": {"type": "integer", "format": "int64"}},
        },
        "schemas": {
            "ULID": {"type": "string", "description": "26-char Crockford base32 ULID.",
                     "pattern": "^[0-9A-HJKMNP-TV-Z]{26}$"},
            "Money": {"type": "object", "description": "Money in integer minor units (cents); never float. V1 is USD-only (Out Of Scope: no multi-currency).",
                      "required": ["amount", "currency"],
                      "properties": {"amount": {"type": "integer", "format": "int64"},
                                     "currency": {"type": "string", "minLength": 3, "maxLength": 3, "example": "USD"}}},
            "TimestampMs": {"type": "integer", "format": "int64",
                            "description": "Epoch milliseconds. Broker-attested time is authoritative for trading data."},
            "JsonObject": {"type": "object", "additionalProperties": True},
            "ErrorDetail": {"type": "object", "additionalProperties": True,
                            "description": "Extended (post-V1): module-specific, safe-to-expose details (V2 addition to the GW-18 envelope)."},
            "Error": {
                "type": "object",
                "description": ("The single error contract — GW-18 (docs/04 §3.1, docs/30). "
                                "V1: every error response carries EXACTLY code, message, "
                                "correlation_id. Extended (post-V1): a details object and "
                                "docs_url are the V2 addition."),
                "required": ["code", "message", "correlation_id"],
                "properties": {
                    "code": {"type": "string", "description": "Stable machine code, dotted domain.action convention (e.g. payout.ineligible). V1 baseline: contracts/errors/taxonomy.md; full registry: docs/30."},
                    "message": {"type": "string", "description": "The user-facing message pattern per the taxonomy (user-safe; no internals)."},
                    "correlation_id": {"type": "string", "description": "Request correlation id; also recorded in audit entries (AUD-01)."},
                    "details": {"$ref": "#/components/schemas/ErrorDetail"},
                },
            },
            "PageMeta": {
                "type": "object",
                "properties": {"next_cursor": {"type": ["string", "null"]},
                               "has_more": {"type": "boolean"}},
            },
            "Paged": {
                "type": "object",
                "description": "Cursor-paginated list envelope.",
                "required": ["data", "meta"],
                "properties": {"data": {"type": "array", "items": {"$ref": "#/components/schemas/JsonObject"}},
                               "meta": {"$ref": "#/components/schemas/PageMeta"}},
            },
            "EventEnvelope": {
                "type": "object",
                "description": ("The canonical domain-event envelope — EVT-03 (docs/04 §5, "
                                "docs/31, contracts/events/payloads/envelope.schema.json). "
                                "Every event carries EXACTLY these fields; `payload` is "
                                "per-event. Broker commands are NOT events (EVT-20)."),
                "required": ["id", "type", "version", "tenant_id", "occurred_at", "payload"],
                "properties": {
                    "id": {"$ref": "#/components/schemas/ULID"},
                    "type": {"type": "string", "description": "The event name (e.g. order.paid, AccountCreated)."},
                    "version": {"type": "integer", "minimum": 1, "description": "Bumped on any payload change (additive-only between freezes)."},
                    "tenant_id": {"$ref": "#/components/schemas/ULID"},
                    "occurred_at": {"$ref": "#/components/schemas/TimestampMs"},
                    "payload": {"type": "object", "additionalProperties": True,
                                "description": "Per-event payload (contracts/events/payloads/ for V1; contracts/events/extended/ for the post-V1 set)."},
                },
            },
        },
        "responses": {
            "Error": {"description": "Domain error (see docs/30 for the code + status)",
                      "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}}},
            "Unauthorized": {"description": "401 — missing/invalid auth (no detail leak)",
                             "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}}},
            "Forbidden": {"description": "403 — scope/ABAC/state-forbidden",
                          "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}}},
            "NotFound": {"description": "404 — not found OR not yours (the no-oracle rule, 04 §6)",
                         "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}}},
            "Conflict": {"description": "409 — state-machine conflict",
                         "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}}},
            "Unprocessable": {"description": "422 — domain validation",
                              "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}}},
            "RateLimited": {"description": "429 — rate/quota (carries Retry-After + X-RateLimit-*)",
                            "headers": {"Retry-After": {"schema": {"type": "integer"}}},
                            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}}},
            "ServiceUnavailable": {"description": "503 — dependency down (carries Retry-After)",
                                   "headers": {"Retry-After": {"schema": {"type": "integer"}}},
                                   "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}}},
        },
    },
}

def dump_yaml(obj, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(obj, sort_keys=False, allow_unicode=True, width=100))

# ---------------------------------------------------------------- events
def parse_events():
    """Extended (post-V1, dotted-name) events from docs/31. The V1 PascalCase
    section is skipped (those events live in contracts/events/payloads/)."""
    text = (DOCS / "31-event-catalog.md").read_text()
    topics = dict()
    cur = None
    for line in text.splitlines():
        m = re.match(r"^### `([a-z][a-z0-9_]*)\.\*`", line)
        if line.startswith("### "):
            cur = m.group(1) if m else None   # reset on any other heading
            if cur:
                topics[cur] = []
            continue
        if cur and line.strip().startswith("|"):
            parts = [p.strip() for p in line.strip().strip("|").split("|")]
            if len(parts) < 2 or parts[0].startswith("Event") or set(parts[0]) <= set("-: "):
                continue
            ev = parts[0].strip("`")
            prod = parts[1] if len(parts) > 1 else ""
            when = parts[2] if len(parts) > 2 else ""
            cons = parts[3] if len(parts) > 3 else ""
            topics[cur].append({"event": ev, "producer": prod, "when": when, "consumers": cons})
    return topics

def build_event_file(topic, events):
    defs = {}
    for e in events:
        name = e["event"].replace(".", "_")
        defs[name] = {
            "allOf": [
                {"$ref": "#/$defs/EventEnvelope"},
                {
                    "type": "object",
                    "properties": {
                        "type": {"const": e["event"]},
                        "payload": {"type": "object", "additionalProperties": True,
                                 "description": (f"Per-event payload. Producer: {e['producer']}. "
                                                 f"When: {e['when']}. Consumers: {e['consumers']}. "
                                                 f"Canonical fields: the producer module doc's §4/§8 (docs/31).")},
                    },
                },
            ],
        }
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": f"alphaone://events/{topic}",
        "title": f"Alpha One events (extended) — topic `{topic}.*`",
        "description": (f"Extended (post-V1) schemas for the `{topic}.*` event topic — "
                        f"the design-level set beyond the V1 execution-sheet baseline "
                        f"(contracts/events/catalog.md + payloads/). Envelope per EVT-03. "
                        f"Catalog + producer/consumer map: docs/31-event-catalog.md. "
                        f"Transport: Redis Streams at-least-once + idempotent consumers (docs/04 §5); "
                        f"webhook egress via Hook0 (docs/04 §5.6)."),
        "$defs": {
            "EventEnvelope": {
                "type": "object",
                "required": ["id", "type", "version", "tenant_id", "occurred_at", "payload"],
                "properties": {
                    "id": {"type": "string", "pattern": "^[0-9A-HJKMNP-TV-Z]{26}$"},
                    "type": {"type": "string"},
                    "version": {"type": "integer", "minimum": 1},
                    "tenant_id": {"type": "string", "pattern": "^[0-9A-HJKMNP-TV-Z]{26}$"},
                    "occurred_at": {"type": "integer", "format": "int64"},
                    "payload": {"type": "object"},
                },
            },
            **defs,
        },
        "anyOf": [{"$ref": f"#/$defs/{e['event'].replace('.', '_')}"} for e in events],
    }
    return schema

# ---------------------------------------------------------------- run
yaml.safe_dump(SHARED, open(CON / "shared" / "openapi.yaml", "w"), sort_keys=False, allow_unicode=True, width=100)
print("shared/openapi.yaml written")

total_eps = 0
for num, fname, mod, title, blurb in MODULES:
    spec = build_module_spec(num, fname, mod, title, blurb)
    n = sum(len(v) for v in spec["paths"].values())
    total_eps += n
    out = CON / f"{num}-{mod.replace('+', '-').replace('/', '-')}.openapi.yaml"
    dump_yaml(spec, out)
    print(f"{out.name}: {len(spec['paths'])} paths / {n} ops")

topics = parse_events()
nte = 0
ext_dir = CON / "events" / "extended"
ext_dir.mkdir(parents=True, exist_ok=True)
# remove stale extended files for topics no longer in the catalog
for stale in ext_dir.glob("*.schema.json"):
    stale.unlink()
for topic, events in topics.items():
    if not events:
        continue
    sch = build_event_file(topic, events)
    (ext_dir / f"{topic}.schema.json").write_text(json.dumps(sch, indent=2) + "\n")
    nte += len(events)
print(f"extended events: {nte} across {len(topics)} topics (events/extended/)")
print(f"total endpoint ops: {total_eps}")

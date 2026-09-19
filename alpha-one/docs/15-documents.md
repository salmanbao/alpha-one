# 15 — DOC: Documents & Certificates

> Covers PRD module **DOC** (14 requirements). DOC turns state changes into
> **branded, verifiable PDFs**: the challenge agreement at purchase, the
> funded-account certificate, the payout receipt, the invoice. A prop firm
> lives on paper its traders screenshot — a beautiful, unimpeachable PDF is
> a marketing asset and a dispute defense at once.

## 1. Purpose & scope

- **PDF generation engine (DOC-01):** HTML template → PDF via the Node 22
  docs-worker (Puppeteer — binding stack, docs/01 §2). Templates are versioned
  artifacts (repo + DB-managed in V2).
- **Data mapping (DOC-03):** each document type has a mapper: domain state →
  template vars (LCC-01 account, funded terms, identity, amounts, dates).
- **Event triggers (DOC-04):** documents are generated **asynchronously from
  events** (never inline in the money path): `account.funded` → certificate,
  `payments.intent_captured` → agreement + invoice, `payout.settled` →
  receipt, `account.breached` → breach notice (V2).
- **Secure storage (DOC-05):** R2, tenant-prefixed keys
  (`documents/{tenant}/{type}/{id}.pdf`), short-lived signed URLs (15 min),
  bucket IAM scoped per tenant prefix, all reads audited.
- **V2:** tenant branding injection (DOC-02), certificate QR + **public
  verification page** (DOC-15/16), admin regeneration (DOC-09), audit log
  (DOC-10), tax documents (DOC-11), template management UI (DOC-13), bulk
  generation (DOC-14), unique certificate IDs (DOC-08), email delivery
  (DOC-07 — via NOT).

Requirement coverage: `DOC-01,03,04,05` (V1) + `02,07,08,09,10,11,13,14,15,16`
(V2).

## 2. Architecture

```
 domain events (EVT) ──► docs-worker (Node 22, Puppeteer):
   1. trigger table (event → doc type, like NOT mappings — PG data)
   2. mapper: read domain state (SQL read-only) → vars
   3. render: HTML template (tenant branding V2) + vars → HTML
   4. Puppeteer: HTML → PDF (A4, print CSS, header/footer with cert id)
   5. upload R2 (tenant-prefixed) + insert documents row + emit
      document.generated (NOT email link V2 DOC-07; V1: link surfaced in TD)
 read paths:
   TD/ADM: GET /v1/documents/{id}/url → signed URL (15 min, audited)
   V2 public: GET /v/verify/{cert_hash} → verification page (no login,
              no PII: name masked, amounts, validity, issuer)
```

The docs-worker is a **separate process** (Node 22 — Puppeteer needs a JS
runtime; everything else is Go). It reads PG (read-only role) and talks to
R2 directly. Failure = retry ×3 → DLQ lane + ops alert (a stuck certificate
on a funded account is a support ticket; a stuck invoice is a revenue
documentation gap).

## 3. System design

### 3.1 Document types (V1 set)

| Type | Trigger | Contents | Audience |
|---|---|---|---|
| `challenge_agreement` | `payments.intent_captured` | package, rules (from the frozen rule set version), terms snapshot (LCC-20), price, tenant ToS link, acceptance timestamp | trader (kept forever by them) |
| `funded_certificate` | `account.funded` | account id, size, split, target, drawdown rules, funding date, trader name (masked surname), tenant logo | trader (screenshot magnet) |
| `payout_receipt` | `payout.settled` | amount, split math (from the frozen calc snapshot — every step), fee, method (masked), settlement date, provider ref (last 4) | trader + tenant finance |
| `invoice` | `payments.intent_captured` | order line items, amount, currency, tax (V2), tenant billing details | trader |
| `breach_notice` (V2) | `account.breached` | what rule, when, the evidence numbers (drawdown %), next steps | trader (tone: factual, non-accusatory — FunderBlu COO review) |

### 3.2 The mapper (DOC-03)

Each type = one Go-mapped… no — one **mapper function in the docs-worker**
(plain TS, ~100 lines each): `map(context) → vars`, where context =
`{tenant, account/order/payout id}` and the mapper issues **read-only SQL**
(account, terms snapshot, calc snapshot, identity). Rules:
- **Only frozen snapshots** (terms snapshot LCC-20, calc snapshot PAY-02) —
  the PDF can never show a number that changed later; it shows what was true
  at the moment the event fired.
- **Masking by design:** wallet strings last-4, document numbers never,
  identity = first name + initial.
- Mappers are unit-tested with golden fixtures (var → expected string).

### 3.3 Templates & branding

V1: platform-branded templates (HTML in the repo, versioned in git, deployed
with the worker) with tenant name + logo variables (from TEN-05/06 when set).
V2 (DOC-02/13): tenant uploads logo/colors → stored (R2 + TEN config),
template registry in PG with versions, admin preview + "generate test" before
publish. The template format is plain HTML + a small mustache-ish var engine
— **no** heavyweight engine (docs are 5 types, not 500).

### 3.4 Verification (V2 DOC-08/15/16)

Each certificate gets `cert_hash = sha256(tenant || account_id ||
funded_at || secret)` — the public page `/v/verify/{cert_hash}` resolves it
to a live lookup: **valid** (account funded, state matches) / **invalid** /
**revoked** (account closed/breached — the certificate honestly shows its
current status). QR code on the PDF encodes the URL. This is both a
marketing surface (traders share verified certs) and an impersonation
defense (fake "funded certificate" scams get checked and fail).

### 3.5 Bulk & regeneration (V2 DOC-09/14)

Regeneration = new version of the same document (old object retained; the
documents row tracks versions; "why regenerated" reason + staff id + audit).
Bulk = queue (per-tenant batch, 500/min cap, R2 + queue state in PG) — e.g.
re-issue all certificates after a branding change.

## 4. Events (topic `document`)

| Event | When | Consumers |
|---|---|---|
| `document.generated` | PDF stored (type, id, url-key) | NOT (V2 email link DOC-07), TD (badge: "your certificate is ready"), AUD |
| `document.failed` | retries exhausted (DLQ) | ADM (ops alert), CON, AUD |
| `document.regenerated` (V2) | admin action | AUD (critical-tier if it changes a money doc) |
| `document.verified_lookup` (V2) | public verify page hit | ANA (marketing metric) |

Consumes: `account.funded`, `payments.intent_captured`, `payout.settled`,
`account.breached` (V2).

## 5. Lifecycles

- **Document:** `pending → generated (v1) → (regenerated: v2, v3…)`; each
  version is an immutable R2 object; the documents row = current version +
  version history (JSONB or child rows — child rows, simpler queries).
- **Signed URL:** 15 min TTL, single-use not enforced V1 (enforced V2 for
  PII-bearing docs), every issuance audited.
- **Trigger mapping row:** `active → disabled`.
- **Retention:** documents 7 years (financial-adjacent; agreements +
  receipts), invoice objects 7 yr, breach notices 7 yr; R2 lifecycle +
  deletion audit.

## 6. Error taxonomy
### 6.1 V1 baseline codes — authoritative

From `contracts/errors/taxonomy.md` (the V1 execution sheet; module DOC). These are the exact codes the V1 surfaces return; the envelope is GW-18 (`code`, `message`, `correlation_id`).
| Code | HTTP | Meaning | User-facing message |
|---|---|---|---|
| `document.not_found` | 404 | Document unknown or not owned | "Document not found." |


Namespace `DOC`:
### 6.2 Extended (post-V1) codes — design-level

> Below the V1 baseline (6.1); names in the GW-18 dotted convention. Rows duplicating a V1 baseline code were folded into the baseline table (the merged registry: docs/30).


| Code | HTTP | Meaning |
|---|---|---|
| `doc.not_found` | 404 | Document id unknown |
| `doc.pending` | 409 | URL requested before generation finished (TD shows "preparing…") |
| `doc.state_missing` | 500-internal | Mapper found no source state (data bug — CRITICAL alert) |
| `doc.render_failed` | 500-internal | Template/Puppeteer failure (retry; 3× → DLQ) |
| `doc.upload_failed` | 500-internal | R2 write failed (retry) |
| `doc.template_version_missing` | 500-internal | Deploy mismatch (template not in worker) — CI check prevents |
| `doc.verify_not_found` (V2) | 404 | Unknown cert hash (page says "not found", no detail) |
| `doc.bulk_limit` | 422 | (V2) Bulk size over cap |

## 7. API endpoints
### 7.1 V1 baseline — `doc` (authoritative: `contracts/api/doc.md`)

| Method + path | Auth | Permission | Idempotency | V1 errors |
|---|---|---|---|---|
| `GET /v1/trader/documents` | Trader (self) — DOC-06 | self-read | n/a | standard |
| `GET /v1/trader/documents/{document_id}` | Trader (owner) — DOC-06 | self-read | n/a | `document.not_found` |

Scope, request/response shapes, and per-endpoint notes: `contracts/api/doc.md` (field values in the research are owner TODOs until contract freeze; canonical JSON is fixed at freeze, per the docs/99 §12 rules).

### 7.2 Extended (post-V1) surface — provisional

> Not in the V1 execution sheet. Design-level; paths beyond the V1 baseline are provisional until the URL-plan decision (`contracts/api/gw.md`, open question). Shown for platform completeness (V2/V3 phases, docs/99).

Trader (TD): `GET /v1/documents` (own: certificates, receipts, agreements,
invoices — with state + download),
`GET /v1/documents/{id}/url` (signed URL, audited).

Staff (ADM): `GET /v1/admin/documents?tenant=&type=&identity=`,
`POST /v1/admin/documents/regenerate` (V2, reason, 2FA),
`POST /v1/admin/documents/bulk` (V2),
`GET|POST /v1/admin/documents/templates` (V2 management + preview),
`POST /v1/admin/documents/templates/{id}/test` (generate to staff address).

Public (no auth, rate-limited, V2): `GET /v/verify/{cert_hash}` (HTML
verification page), `GET /api/v1/verify/{cert_hash}` (JSON for the page).

Internal: none (worker-triggered only; the worker is event-driven, not
HTTP-poked — an admin "generate now" is a PG queue row the worker polls).
## 8. Schema (key shapes)

```jsonc
// GET /v1/documents
{ "data": [ { "id": "01J9DOC...", "type": "funded_certificate",
              "account_id": "01J9ACC...", "version": 1,
              "state": "generated", "available_at": 1758282000000,
              "url": "/v1/documents/01J9DOC…/url" } ] }

// V2 verification page payload
{ "data": { "valid": true, "status": "active", "issuer": "FunderBlu",
    "holder": "Ali K.", "account_size": "100,000 USD",
    "funded_at": "2026-09-21", "verified_at": "2026-09-21T04:00Z" } }
```

## 9. Database design

```sql
CREATE TABLE documents (
  id            ULID PRIMARY KEY,
  tenant_id     ULID NOT NULL,
  type          TEXT NOT NULL,               -- challenge_agreement|funded_certificate|…
  ref_kind      TEXT NOT NULL,               -- account|order|payout
  ref_id        ULID NOT NULL,
  identity_id   ULID,                        -- owner (trader docs)
  version       INT NOT NULL DEFAULT 1,
  state         TEXT NOT NULL DEFAULT 'pending'
    CHECK (state IN ('pending','generated','failed')),
  r2_key        TEXT,                        -- documents/{tenant}/{type}/{id}-v{n}.pdf
  vars          JSONB,                       -- rendered vars (PII-safe, for audit/redraw)
  cert_hash     TEXT,                        -- V2: verification hash (certs only)
  fail_reason   TEXT,
  attempts      INT NOT NULL DEFAULT 0,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  generated_at  TIMESTAMPTZ,
  UNIQUE (ref_kind, ref_id, type, version)
);
CREATE INDEX idx_doc_tenant_identity ON documents(tenant_id, identity_id, created_at DESC);
CREATE INDEX idx_doc_ref ON documents(ref_kind, ref_id, type);
CREATE INDEX idx_doc_cert ON documents(cert_hash) WHERE cert_hash IS NOT NULL;

CREATE TABLE document_versions (               -- regeneration history (V2)
  id            ULID PRIMARY KEY,
  document_id   ULID NOT NULL REFERENCES documents(id),
  version       INT NOT NULL,
  r2_key        TEXT NOT NULL,
  reason        TEXT,
  created_by    ULID,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (document_id, version)
);

CREATE TABLE document_triggers (               -- event → doc type mapping (data)
  id            ULID PRIMARY KEY,
  event_type    TEXT NOT NULL,
  doc_type      TEXT NOT NULL,
  enabled       BOOLEAN NOT NULL DEFAULT true,
  UNIQUE (event_type, doc_type)
);
```

## 10. Security & compliance

- **R2 isolation:** tenant-prefixed keys + IAM prefix scoping (same pattern
  as KYC docs, 13 §10); signed URLs 15 min; read issuance = audit row
  (who, which doc, when) — a trader can only ever resolve their own docs
  (the TD route checks ownership; the ADM route is role-gated + audited).
- **No PII beyond mask rules:** the mapper's masking (§3.2) is property-
  tested (golden fixtures contain max-PII inputs; assert last-4 only).
- **Public verification page (V2):** no login, no PII (masked holder name,
  no email, no wallet, no document numbers), rate-limited (10/min/IP),
  revocation visible (a breached account's cert shows `status: revoked` —
  integrity over marketing).
- **Money docs are immutable:** payout receipts reference the frozen calc
  snapshot; regeneration of a money doc = new version + critical audit +
  the old version remains downloadable (never overwritten — the R2 key is
  versioned, §9).
- **Template supply chain:** templates ship in the repo (V1) / PG registry
  with publish-audit (V2) — no runtime-fetched HTML (XSS in a PDF = brand
  + legal risk).
- **Retention:** 7 yr for financial docs (same class as LED/AUD), R2
  lifecycle + deletion audit; breach notices reviewed by FunderBlu COO
  before first production send (Phase-1 checklist item).

## 11. Scalability considerations

- Volume: ~5 docs/purchase + 1 certificate + 1-2 receipts/month/trader →
  ~500 PDFs/day V1. Puppeteer render ≈ 300-800 ms each (headless, no
  external fonts — fonts bundled locally; **no network in the sandboxed
  render** by design).
- Worker: single Node process, queue concurrency 3 (PG `SKIP LOCKED`
  pattern, 06 §advisory-lock jobs) → ~2k PDFs/hour capacity = 4× V1 peak;
  scale = add worker replicas (the queue is PG — stateless workers).
- R2 is the durable store; worker crash mid-render = row stays `pending`,
  redelivered (the trigger is event-driven with dedupe on
  (ref_kind, ref_id, type, version)).
- Bulk (V2): 500/min cap keeps a 10k-doc rebrand at ~20 min — fine.
- Public verify page (V2): one indexed lookup + cache (Redis 5 min) —
  even a viral cert URL is a PG point read.

## 12. Open-source solutions

| Option | Verdict |
|---|---|
| **Puppeteer (Node 22 docs-worker, register)** | **CHOSEN** — HTML→PDF fidelity with real CSS (flexbox, print headers) beats every Go PDF lib for branded layouts |
| Go: gofpdf/wkhtmltopdf/weasyprint | Rejected: wkhtmltopdf is deprecated upstream; Go PDF libs choke on modern CSS; we'd re-implement the browser engine |
| Gotenberg (Dockerized Chromium API) | Rejected: extra service + container orchestration we don't have; the worker is the container boundary already |
| Documenso (e-sign, register consider-later) | V2+ if FunderBlu wants e-signed agreements (DOC-12 class); V1 agreements are click-accepted (ToS acceptance logged at purchase) |
| R2 (register) | CHOSEN storage |
| qrcode (V2) | any stdlib-grade QR lib in TS — trivial |

## 13. Technology stack

Node 22 docs-worker (Puppeteer, headless Chromium, bundled fonts), Postgres
(read-only mapper queries + queue + documents tables), R2 (objects), EVT
(trigger consumer), NOT (V2 delivery), Postmark (via NOT), Prometheus
(render latency, queue depth, DLQ), Sentry.

## 14. Integration — internal modules (glue)

| Module | How |
|---|---|
| **LCC** | `account.funded` → certificate (vars: terms snapshot LCC-20, account state); `account.breached` → breach notice (V2); data mapping reads `accounts` + `funded_terms` |
| **CHK** | `payments.intent_captured` → agreement + invoice (vars: frozen order lines, invoice number) |
| **PAY** | `payout.settled` → receipt (vars: the frozen calc snapshot steps — the receipt *is* the dispute defense) |
| **TEN** | branding (logo, colors, billing details) for V2 injection; tenant doc retention override (V2) |
| **NOT** | V2: `document.generated` → email with signed link (DOC-07) |
| **TD** | documents section (TD-10 family): list + download + "ready" badge events |
| **ADM** | admin documents view, regeneration, bulk, template management |
| **AUD** | every read issuance + generation + regeneration (regeneration of money docs = critical tier) |
| **ANA** | (V2) verify-page hits (marketing funnel), doc generation latency |

## 15. Integration — external tools

R2 (storage), Puppeteer/Chromium (render, local fonts), Postmark (via NOT,
V2 delivery), Prometheus/Grafana, Sentry.

## 16. Implementation blueprint

| Step | Owner | Est | Depends | Exit criteria |
|---|---|---|---|---|
| 1. docs-worker scaffold (Node 22, Puppeteer, queue via PG SKIP LOCKED, R2 upload) + documents schema | BE-1 | 2 d | OPS, R2, EVT | seeded queue row → PDF in R2 → `generated` |
| 2. Mappers (agreement, certificate, receipt, invoice) + golden-fixture tests + masking property test | BE-1 | 3 d | 1, LCC, PAY, CHK state | each doc renders from fixture state; no PII leak in output |
| 3. Templates V1 (4 types, platform branding + tenant vars) + print CSS + bundled fonts | FE-02 | 3 d | 2 | FunderBlu design review passes on the certificate (it's the marketing asset) |
| 4. Triggers (event consumer) + TD documents section + signed-URL routes (15 min, audited) | BE-1 + FE-01 | 3 d | 2–3 | funded account in staging → cert appears in TD within 1 min; read is audited |
| 5. Failure path (retry, DLQ, ops alert) + load check (2k PDFs/hour) | BE-1 | 1 d | 4 | kill worker mid-render → redelivery, no duplicate objects |
| 6. V2: branding injection, template registry + admin preview, regeneration + bulk, cert hash + QR + public verify page, email delivery, tax docs, audit log surface | BE-1 + FE-02 | 3 wks | 5 | verify page live (staging URL shared with FunderBlu for marketing review) |

**Risks:** Puppeteer memory in a shared container (mitigation: worker has its
own memory cap — OPS-37; queue concurrency 3; render timeouts 15 s); template
branding debt across tenants (V2 registry mitigates; V1 is single-tenant-
friendly by design); agreement legal review (Phase-1: FunderBlu legal signs
the V1 template before go-live — it's a contract artifact); verify-page
abuse (rate limit + no PII + the hash is unguessable).

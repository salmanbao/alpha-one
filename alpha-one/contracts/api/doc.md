# Document Generation API Contract (DOC)

Status: DRAFT
Owner: TBD
Version: v1
Last updated: 2026-09-20

Derived from the V1 Execution Sheet (V1.0 only). Nothing here is final until contract freeze.

## Scope
PDF generation engine (Puppeteer, BVR-07: no renderer bought), data mapping from account data, event-triggered certificates, secure tenant-prefixed storage, trader portal download. (DOC-01, DOC-03, DOC-04, DOC-05, DOC-06)

## Auth
Trader download endpoint in trader group (GW-01), owner-only. Generation is internal and event-driven.

## Tenant resolution
From domain (GW-02). Storage keys tenant-prefixed (TEN-18, Cloudflare R2 per DOC-06).

## Permissions
- `document.read` (self certificates) — registered (`contracts/permissions/registry.md`: view and download own certificates, DOC-06); own-scope enforced at the GW (docs/04 §3.1 step 4).

## Idempotency
Generation is idempotent by triggering event id (EVT-05: consumers deduplicate by event id; DOC-04 consumes via the outbox, EVT-01).

## Endpoints

### GET /v1/trader/documents
Auth: Trader (self) — DOC-06
Tenant: from domain (GW-02)
Permission: `document.read` (own scope)
Idempotency: n/a

Response 200 (D45 — list, so pagination is present):
```json
{ "data": [ { "document_id": "01J9DOC...", "type": "funded_certificate",
      "account_id": "01J9ACC...", "version": 1, "state": "generated",
      "created_at": 1758282120000 } ],
  "meta": { "request_id": "01J9ULID...", "version": "v1",
            "pagination": { "cursor": "", "has_more": false } } }
```

Errors: none beyond standard gateway errors # DOC-06

### GET /v1/trader/documents/{document_id}
Auth: Trader (owner) — DOC-06
Tenant: from domain (GW-02)
Permission: `document.read` (own scope)
Idempotency: n/a

Response 200 (document metadata — the bytes flow via the signed URL):
```json
{ "data": { "document_id": "01J9DOC...", "type": "funded_certificate",
    "account_id": "01J9ACC...", "version": 1, "state": "generated",
    "created_at": 1758282120000 },
  "meta": { "request_id": "01J9ULID...", "version": "v1" } }
```

Errors:
- `document.not_found` 404 # implied by DOC-06
- `doc.pending` 409 — generation still in flight (the portal shows "preparing…")

### GET /v1/trader/documents/{document_id}/url
Auth: Trader (owner) — DOC-06
Tenant: from domain (GW-02)
Permission: `document.read` (own scope)
Idempotency: n/a

Response 200:
```json
{ "data": { "url": "https://<r2-signed>/...", "expires_at": 1758283020000 },
  "meta": { "request_id": "01J9ULID...", "version": "v1" } }
```

A short-lived signed R2 URL — 15-min TTL, every issuance audited
(docs/15 §2/§5/§10). Added to the V1 baseline 2026-09-20 (docs/58): the
whole module design (worker → R2 → signed read) depends on it; the former
binary-through-api response is retired.

Errors:
- `document.not_found` 404
- `doc.pending` 409

## Internal contracts (no HTTP)
- DOC-01 engine: HTML templates rendered to PDF via Puppeteer.
- DOC-03 data mapping: trader name, account size, date, certificate ID into template variables.
- DOC-04 triggers (corrected 2026-09-20, docs/58): `FundedCreated` → funded_certificate · `order.paid` → challenge_agreement + invoice · `payout.settled` → payout_receipt (D60). `AccountPassed` → phase certificate is a **V2 document type** (the catalog consumer note anticipates it), not in the V1 set (docs/15 §3.1).
- DOC-05 storage: object storage with tenant-prefixed keys, durable and isolated.

## Events consumed
FundedCreated, order.paid, payout.settled (D60) — see `contracts/events/catalog.md`. V2: account.breached (breach notice).

## Open contract questions
- Resolved 2026-09-20 (docs/58): certificate ID = the `documents.id` ULID (rendered in the PDF header/footer); the V2 `cert_hash` + QR + public verify page is a separate mechanism (docs/15 §3.4/§9).
- Resolved 2026-09-20 (docs/58): CHK owns the order, its frozen line items, and allocates the invoice number at capture (order-at-submit, docs/53); DOC renders the agreement + invoice from `order.paid` (docs/15 §3.1/§14).
- Resolved 2026-09-20 (docs/58): generation is asynchronous (event-triggered); a download request before completion answers `doc.pending` 409 and the portal shows "preparing…" (docs/15 §5/§6.2).
- Resolved 2026-09-20 (docs/58): storage keys `documents/{tenant}/{type}/{id}.pdf` with per-version objects (docs/15 §1/§5/§9).

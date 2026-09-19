# Document Generation API Contract (DOC)

Status: DRAFT
Owner: TBD
Version: v1
Last updated: TODO

Derived from the V1 Execution Sheet (V1.0 only). Nothing here is final until contract freeze.

## Scope
PDF generation engine (Puppeteer, BVR-07: no renderer bought), data mapping from account data, event-triggered certificates, secure tenant-prefixed storage, trader portal download. (DOC-01, DOC-03, DOC-04, DOC-05, DOC-06)

## Auth
Trader download endpoint in trader group (GW-01), owner-only. Generation is internal and event-driven.

## Tenant resolution
From domain (GW-02). Storage keys tenant-prefixed (TEN-18, Cloudflare R2 per DOC-06).

## Permissions
- `document.read` (self certificates) # derived from DOC-06 — TODO — needs owner decision on key naming

## Idempotency
Generation is idempotent by triggering event id (EVT-05: consumers deduplicate by event id; DOC-04 consumes via the outbox, EVT-01).

## Endpoints

### GET /v1/trader/documents
Auth: Trader (self) — DOC-06
Tenant: from domain (GW-02)
Permission: self-read
Idempotency: n/a

Response 200:
```json
{ "documents": [ { "document_id": "TODO", "type": "TODO", "issued_at": "TODO" } ] }
```

Errors: none beyond standard gateway errors # DOC-06

### GET /v1/trader/documents/{document_id}
Auth: Trader (owner) — DOC-06
Tenant: from domain (GW-02)
Permission: self-read
Idempotency: n/a

Response 200: PDF binary (certificate) # DOC-01, DOC-06

Errors:
- `document.not_found` 404 # implied by DOC-06

## Internal contracts (no HTTP)
- DOC-01 engine: HTML templates rendered to PDF via Puppeteer.
- DOC-03 data mapping: trader name, account size, date, certificate ID into template variables.
- DOC-04 triggers: generate certificates on AccountPassed, FundedCreated, and PayoutPaid events (consumes LCC-23 events and PayoutPaid — produced by PAY-12, resolved 2026-09-16 (Decision 6), see catalog).
- DOC-05 storage: object storage with tenant-prefixed keys, durable and isolated.

## Events consumed
AccountPassed, FundedCreated, PayoutPaid — see `contracts/events/catalog.md`.

## Open contract questions
- TODO — needs owner decision: certificate ID scheme (DOC-03 names a certificate ID; format/sequence unspecified).
- TODO — needs owner decision: receipt/invoice rendering ownership split between CHK (CHK-17, CHK-40) and DOC — the sheet implies CHK requests and DOC renders; interface shape open.
- TODO — needs owner decision: PDF generation sync vs async UX for downloads (generation latency unspecified).
- TODO — needs owner decision: storage key format beyond tenant prefix (TEN-18).

# KYC API Contract (KYC)

Status: DRAFT
Owner: TBD
Version: v1
Last updated: 2026-09-17

Derived from the V1 Execution Sheet (V1.0 / V1.1). Nothing here is final until contract freeze.

## Scope
Provider adapter interface (Veriff per tenant keys), webhook status handling, KYC state machine, funding gate, payout gate, verified identity record (V1.1), manual review fallback (V1.1), manual document upload (V1.1), country restrictions (V1.1), age verification (V1.1), upload progress/retry (V1.1), kyc.* event emission through the outbox (KYC-05 amended by Decision 5; KYC-16 in V1.0 / V1-Core). (KYC-01, KYC-02, KYC-05, KYC-06, KYC-07, KYC-08, KYC-09, KYC-11, KYC-12, KYC-13, KYC-14, KYC-16, KYC-36)

## KYC state machine (KYC-06)
States: NOT_STARTED, PENDING, IN_REVIEW, APPROVED, REJECTED, NEEDS_RESUBMISSION, EXPIRED. See `contracts/diagrams/kyc-state.md`. Transition triggers — TODO — needs owner decision (states fixed; edges not enumerated).

## Auth
Trader routes in trader group; manual review in admin group (GW-01). KYC applies to traders only (Out Of Scope: no KYC for staff/super admins).

## Tenant resolution
From domain (GW-02). One provider per tenant in V1 (Out Of Scope: no multi-jurisdiction routing). Provider runs on the tenant's own Veriff keys (KYC-02, TEN-11 config).

## Permissions
- `kyc.review` — manual review decisions # KYC-11 — TODO — needs owner decision on key naming
- `kyc.restrictions.write` — maintain restricted country list # KYC-13
- Trader session creation/status/upload: self-action

## Idempotency
Webhooks deduplicate by provider event id (KYC-05, EVT-10). Mutating requests accept an idempotency key per GW-12.

## Endpoints

### POST /v1/trader/kyc/sessions
Auth: Trader — implied by KYC-01 session creation + TD-02 self-serve flow
Tenant: from domain (GW-02)
Permission: self-action
Idempotency: required # GW-12

Request:
```json
{}
```

Response 201:
```json
{ "kyc_verification_id": "TODO", "provider_session_url": "TODO" }
```

Errors:
- `kyc.country_restricted` 403 — trader jurisdiction on tenant restricted list # implied by KYC-13 (V1.1)
- `kyc.already_in_progress` 409 # implied by KYC-06 states; rule TODO — needs owner decision

### POST /v1/webhooks/kyc/{provider}
Auth: provider signature (EVT-10 shared verification utilities) — KYC-05
Tenant: from request subdomain (GW-02, TEN-02). Provider webhook URLs are provisioned per tenant: `https://{tenant-subdomain}.platform.com/v1/webhooks/kyc/{provider}`
Permission: none (signature-authenticated)
Idempotency: required — dedupe by provider event id # KYC-05, EVT-10

Request: provider-specific payload (Veriff) — TODO — needs owner decision

Response 200:
```json
{ "received": true }
```

Errors:
- `webhook.signature_invalid` 401 # implied by EVT-10

Effects: updates KYC state machine (KYC-06); stores verified identity data on approval (KYC-09: full name, DOB, country, provider reference); age check rejects under-18 (KYC-14); emits kyc.submitted, kyc.approved, kyc.rejected, kyc.expired, and kyc.resubmission_requested through the outbox (EVT-01) — resolved 2026-09-16 (Decision 5: KYC-05 amended; KYC-16 in V1.0 / V1-Core). See `contracts/events/catalog.md`.

### GET /v1/trader/kyc/status
Auth: Trader (self) — implied by KYC-06 "status is explicit and queryable"
Tenant: from domain (GW-02)
Permission: self-action
Idempotency: n/a

Response 200:
```json
{ "state": "TODO", "provider": "TODO" }
```

Errors: none beyond standard gateway errors

### POST /v1/trader/kyc/documents
Auth: Trader — KYC-12 (V1.1 manual fallback upload: ID + proof of address)
Tenant: from domain (GW-02)
Permission: self-action
Idempotency: required # GW-12; upload progress and retry per KYC-36 (mechanics — TODO — needs owner decision: resumable upload protocol unspecified)

Request: multipart upload — TODO — needs owner decision (size limits, formats unspecified)

Response 201:
```json
{ "document_id": "TODO", "upload_state": "TODO" }
```

Errors:
- `kyc.upload_failed` 400 — retriable per KYC-36 # implied by KYC-36
- Storage is tenant-prefixed (TEN-18, R2)

### GET /v1/admin/kyc/manual-queue
Auth: Tenant Admin — KYC-11 (V1.1 fallback when provider unavailable or flags a case)
Tenant: from domain (GW-02)
Permission: `kyc.review` # KYC-11
Idempotency: n/a

Response 200:
```json
{ "cases": [ { "kyc_verification_id": "TODO", "trader_id": "TODO", "documents": ["TODO"] } ] }
```

Errors: none beyond standard gateway errors # KYC-11

### POST /v1/admin/kyc/{kyc_verification_id}/decision
Auth: Tenant Admin — KYC-11 (V1.1)
Tenant: from domain (GW-02)
Permission: `kyc.review` # KYC-11
Idempotency: required # GW-12

Request:
```json
{ "decision": "TODO", "reason": "TODO" }
```

Response 200:
```json
{ "kyc_verification_id": "TODO", "state": "TODO" }
```

Errors:
- `kyc.case_not_reviewable` 409 # implied by KYC-06 states
- Decision enum (approve/reject/request-resubmission) — TODO — needs owner decision
- Sensitive data access is audited with actor, reason, permission, entity (AUD-23 records the audit; the gating permission is a working-session item) # implied by AUD-23

### PUT /v1/admin/kyc/restricted-countries
Auth: Tenant Admin — KYC-13 (V1.1)
Tenant: from domain (GW-02)
Permission: `kyc.restrictions.write` # KYC-13
Idempotency: required # GW-12

Request:
```json
{ "countries": ["TODO"] }
```

Response 200:
```json
{ "countries": ["TODO"] }
```

Errors: none beyond standard gateway errors # KYC-13

## Internal contracts (no HTTP)
- KYC-01 provider interface: session creation, status retrieval, webhook parsing, document retrieval. Swappable per tenant (BVR-03: no in-house verification engine).
- KYC-07 funding gate: block funded account creation until APPROVED when challenge timing requires it (consumed by LCC-07).
- KYC-08 payout gate: block payout eligibility until APPROVED when timing requires it (consumed by PAY-03).

## Open contract questions
- Resolved 2026-09-17: KYC timing enum = `{at_creation, after_evaluation, at_first_payout, skipped}` — per KYC-03's timing description; stored as `challenges.kyc_timing` (see `data/dictionary.md`, `api/lcc.md`). Note: KYC-03 (the config UI row) is V2.0 in the Master Backlog — V1 timing is per-challenge config data enforced by the V1 gates KYC-07/KYC-08.
- TODO — needs owner decision: EXPIRED state trigger (document expiry triggers mentioned in Out Of Scope as "trigger-based re-verification arrives at P2" — what makes V1 expire?).
- TODO — needs owner decision: manual document review retention and access rules (AUD-23 audit exists; access permission granularity open).
- TODO — needs owner decision: identity record fields exactness (KYC-09: full name, DOB, country, provider reference — types and name-match rules for payout methods open).

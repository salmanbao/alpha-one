# Audit API Contract (AUD)

Status: DRAFT
Owner: TBD
Version: v1
Last updated: 2026-09-17

Derived from the V1 Execution Sheet (V1.0 / V1.1). Nothing here is final until contract freeze.

## Scope
Audit event schema (AUD-01), single audit service API (AUD-03), append-only storage (AUD-04), audit log access/export itself audited (AUD-21), sensitive data access audit (AUD-23, V1.1). (AUD-01, AUD-03, AUD-04, AUD-21, AUD-23)

## Auth
Read/search/export endpoints in admin group (GW-01). Who may read audit logs — TODO — needs owner decision (an `audit.read`-style permission was referenced in earlier drafts (AUD-06) but that Req ID is not in the V1 sheet; AUD-21 implies viewing/searching/exporting happens but grants no role).

## Tenant resolution
From domain (GW-02). Audit entries are tenant-scoped (AUD-01 records tenant).

## Permissions
- `audit.read` — view/search audit log # derived from AUD-21 — TODO — needs owner decision on key name and role
- `audit.export` — export audit log # derived from AUD-21 — TODO — needs owner decision

## Idempotency
n/a for reads; exports accept an idempotency key per GW-12.

## Endpoints

### GET /v1/admin/audit
Auth: staff with audit read permission — AUD-21
Tenant: from domain (GW-02)
Permission: `audit.read` # AUD-21
Idempotency: n/a

Query filters — TODO — needs owner decision (AUD-01 schema suggests actor, action, entity type/id, time range, correlation id)

Response 200:
```json
{ "entries": [ { "id": "TODO", "actor": "TODO", "action": "TODO", "entity_type": "TODO", "entity_id": "TODO", "occurred_at": "TODO" } ], "pagination": "TODO" }
```

Errors: none beyond standard gateway errors

Side effect: this read is itself recorded (actor, filters, result count) # AUD-21

### POST /v1/admin/audit/export
Auth: staff with export permission — AUD-21
Tenant: from domain (GW-02)
Permission: `audit.export` # AUD-21
Idempotency: required # GW-12

Request:
```json
{ "filters": "TODO", "format": "TODO" }
```

Response 200:
```json
{ "export_id": "TODO" }
```

Errors: none beyond standard gateway errors

Side effect: the export is itself recorded # AUD-21

## Internal contracts (no HTTP)
- AUD-01 entry schema: actor, role, tenant, action, entity type and id, before/after payload, IP, user agent, correlation id, timestamp.
- AUD-03 single audit service: all modules emit through one shared service (format, storage, retention consistent).
- AUD-04 append-only: immutable, no update or delete path in the application (LED-18 depends on the same principle).
- AUD-23 sensitive access (V1.1): staff access to KYC documents, payout methods, and personal data audited with actor, reason, permission, entity (consumers: KYC-11 manual review, PAY-05 methods).

## Open contract questions
- TODO — needs owner decision: who can read audit logs (role/permission not granted to any V1 row).
- TODO — needs owner decision: retention period and archival (AUD-03 mentions retention; no value in the sheet).
- TODO — needs owner decision: before/after payload size limits and PII minimization rules (Out Of Scope: automatic PII redaction is out; "V1 minimizes PII in payloads by design" — the minimization rule needs definition).
- TODO — needs owner decision: export format and delivery (download vs email link).
- TODO — needs owner decision: console-side audit visibility in V1 (what the super admin console can see and with which permission; no impersonation exists in V1 per `api/auth.md`, so there is no impersonation-audit integration point).

# Audit API Contract (AUD)

Status: DRAFT
Owner: TBD
Version: v1
Last updated: 2026-09-17

Derived from the V1 Execution Sheet (V1.0 / V1.1). Nothing here is final until contract freeze.

## Scope
Audit event schema (AUD-01), single audit service API (AUD-03), append-only storage (AUD-04), audit log access/export itself audited (AUD-21), sensitive data access audit (AUD-23, V1.1). (AUD-01, AUD-03, AUD-04, AUD-21, AUD-23)

## Auth
Read/search/export endpoints in admin group (GW-01). Who may read audit logs — resolved 2026-09-20 (docs/62): `audit.read` / `audit.export` (registry, D14-era) bound to `firm:owner`, `firm:admin`, `firm:compliance` (roles.yaml); every view/search/export is itself recorded.

## Tenant resolution
From domain (GW-02). Audit entries are tenant-scoped (AUD-01 records tenant).

## Permissions
- `audit.read` — view/search audit log # registered (D14-era registry, AUD-21); owner/admin/compliance — resolved 2026-09-20 (docs/62)
- `audit.export` — export audit log # registered; owner/admin/compliance — resolved 2026-09-20 (docs/62)

## Idempotency
n/a for reads; exports accept an idempotency key per GW-12.

## Endpoints

### GET /v1/admin/audit
Auth: staff with audit read permission — AUD-21
Tenant: from domain (GW-02)
Permission: `audit.read` # AUD-21
Idempotency: n/a

Query filters — resolved 2026-09-20 (docs/62): actor, action, resource type/id, time range, correlation_id — exactly the `audit_events` columns and indexes (docs/05 §9).

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
- Resolved 2026-09-20 (docs/62): who reads — `audit.read` (owner/admin/compliance, roles.yaml).
- Resolved 2026-09-20 (docs/62): retention = **7 years** (the binding 00 §6 duty; docs/05 §3.5), partitioned by month; archival = the nightly R2 snapshot (docs/05 §3.5).
- Resolved 2026-09-20 (docs/62): before/after = JSONB, capped by the GW 10 MB payload limit; PII minimization = the docs/28 §4 rule — S1/S2 data never enters payloads (refs/masks only, AUD-23); no automatic redaction in V1 (Out Of Scope stands).
- Resolved 2026-09-20 (docs/62): export = CSV download from CON (CON-13, docs/21 §3.3), critical-audited, 7-yr retained — no email links.
- Resolved 2026-09-20 (docs/62): console-side audit visibility in V1 = **none** — the platform audit view is a V2 CON row (docs/99 task 5 batch); cross-tenant audit reads are `platform:super_admin`-only by D25 (docs/48), with no V1 UI.

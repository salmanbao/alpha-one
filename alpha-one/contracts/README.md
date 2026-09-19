# Alpha One — API & Event Contracts Pack

The contract source of truth for every Alpha One surface. The
module specs here are what the implementation **builds against**
and what CI **checks against** (docs/99 §12: the pack is the
source of truth; the code is generated/checked against it).

This pack is **generated**, not hand-edited. It is produced by
`scripts/build_contracts.py` from the canonical module docs
(`docs/02`–`docs/27`, section 7 "API endpoints" and section 4
"Events"). If a doc changes, re-run the generator — never edit
a generated file in place.

```bash
python3 scripts/build_contracts.py     # regenerate everything
```

## Layout

```
contracts/
├── shared/openapi.yaml        # shared components (all modules $ref into this)
├── 02-AUTH.openapi.yaml       # one spec per module doc (26 specs, 02…27)
├── …
├── 27-SDK-DVP-TRD-PLT-CS.openapi.yaml
└── events/                    # JSON Schema 2020-12, one file per event domain
    ├── account.schema.json    #   (40 files; every event on that topic)
    ├── console.schema.json
    └── …
```

**Scope numbers, last generation:** 26 module specs, **388
operation entries**, 40 event files, **163 events**.

## Reading a module spec

1. `info.description` — the module doc reference, the PRD
   requirement ids covered, and links to the three reference
   catalogs (30 error taxonomy, 31 event catalog, 32 database
   design). Read the doc first; the spec is its machine-readable
   shadow.
2. `tags` — the surface the path lives on: `public` (customer
   API), `dvp` (developer portal), `internal` (service-to-service
   via the internal network), `console` / `admin` (FunderBlu
   console), `core`, `webhook`. The tag drives the security
   requirement.
3. `paths` — the endpoints from the doc's section 7. Parameter
   names follow the doc verbatim; where a doc uses an enum
   placeholder in a path (e.g. CON's
   `/v1/console/controls/{tenant_halt|maintenance|…}`) the
   generator emits one path parameter with an `enum` schema.
4. Responses — every operation returns `200` (application
   `application/json`; the **canonical request/response JSON is
   in the module doc's section 8**, the spec keeps the pack
   stable while the docs evolve) plus the error surface for its
   tag:
   - `public` / `dvp`: `401`, `403`, `429` + `default`
   - `internal`: `503` + `default`
   - console/admin/core: `401`, `403`, `404` + `default`

   `default` always resolves to the shared `Error` envelope
   (docs/30). Error **codes** are the 253-entry taxonomy in
   docs/30 — the code lives in the error body, not in the HTTP
   status table.
5. `components.securitySchemes` — `$ref`s into the shared file
   (one `$ref` per scheme).

## Shared components (`shared/openapi.yaml`)

| Component | Purpose |
|---|---|
| `securitySchemes.sessionAuth` | Bearer session token (Better Auth) — public/console/dvp |
| `securitySchemes.apiKeyAuth` | `Authorization: Bearer sk_live_t_…` — customer API (docs/02 key model) |
| `securitySchemes.internalService` | `X-Internal-Token` — internal paths only |
| `securitySchemes.webhookSignature` | `X-AlphaOne-Signature`: `HMAC-SHA256(timestamp + "." + body)`, `ts` header, ±5 min replay window (docs/04) |
| `parameters.XIdempotencyKey` | `Idempotency-Key` — all mutating public ops (docs/04 §4) |
| `parameters.XRequestId` | `X-Request-Id` — correlation, echoed in responses |
| `parameters.Cursor` / `Limit` / `AsOf` | pagination & as-of reads (docs/04 §4.3) |
| `schemas.ULID` | crockford base32, 26 chars (docs/32) |
| `schemas.Money` | `{amount: int64 cents, currency: ISO-4217}` — never floats (docs/32) |
| `schemas.TimestampMs` | int64 epoch ms, UTC (docs/32) |
| `schemas.JsonObject` | placeholder for doc-defined bodies |
| `schemas.Error` / `ErrorEnvelope` | `{error: {code, message, request_id, details?}}` (docs/30) |
| `schemas.PageMeta` / `Paged` | cursor pagination envelope |
| `schemas.EventEnvelope` | `{id, event, event_version, tenant_id, created_at, data}` — the broker's wire envelope (docs/04 §5.1) |
| `responses.*` | shared error responses |

## Event schemas (`events/`)

One file per **topic domain** (40). Schema dialect:
`https://json-schema.org/draft/2020-12/schema`. Each file is a
`$defs` of the individual events (each `allOf`-composing the
shared `EventEnvelope`) plus a top-level `anyOf` over the domain's
events — validate a message against the file, and the `event`
name tells you which event it is.

Rules (docs/31, docs/04 §5.6, docs/99 §12):

- **Additive only** between freezes; a changed/removed field = a
  new `event_version` (never an in-place change).
- `tenant_id` is mandatory on every event (shared-schema
  multi-tenancy, ADR-1).
- Delivery is at-least-once via Redis Streams (ADR-7); consumers
  must be idempotent on `(event, id)`.
- The 163-event catalog with producer/consumer/SLA is
  docs/31 — this folder is its machine-checkable form.

## Versioning & URL conventions (ADR-2, docs/04 §3)

- URL-only versioning: `/v1/…` today. A breaking public change
  waits for the next major (`/v2/`) with the 12-month
  deprecation (docs/27 Part A §3.5); internal surfaces bump
  freely.
- Webhook payloads are versioned by `event_version`, never by
  URL.

## Validation

The pack is validated with `openapi-spec-validator` (each file
resolved against its directory, so the cross-file `$ref`s into
`shared/` resolve). Run it exactly like CI does:

```bash
cd contracts
for f in shared/openapi.yaml *.openapi.yaml; do
  openapi-spec-validator "$f" || exit 1
done
for f in events/*.schema.json; do
  python3 -c "import json,sys; json.load(open('$f'))" || exit 1
done
```

**Status (last run): 27/27 specs green, 40/40 event files
green.** CI (docs/06, Phase 0) runs this on every PR that touches
`contracts/` or `docs/` and blocks the merge on any failure —
that gate is what keeps code, docs, and contracts from drifting
(docs/99 §12, DoD point 2).

## Freeze rules (docs/99 §12)

| Milestone | Freeze | Surface |
|---|---|---|
| M0 | v0 | the Phase 0–1 public + internal core (AUTH, GW/EVT, LED/AUD, TEN, BRG, EVL) |
| M1 | v1 | the full V1-Core set (docs/99 §4) |
| M3 | v1.1 | V2 additions |
| M4 | v2 | the V2 completion |
| M5 | v3 | the V3 set (docs/99 §7–8) |

- Between freezes: **additive only**.
- After a freeze, a breaking public change = 12-month
  deprecation; a breaking internal change = a `/v2/` bump.
- Event schemas follow the additive-only rule with the
  `event_version` bump.

## Where this pack sits in the delivery

- **Codegen** (Phase 0, docs/06 §7): the Go client for the
  internal services, the TS client for the console, and the
  webhook verifier are generated from these specs.
- **Contract check** (CI gate, DoD point 2): handlers' routes,
  status codes, and parameter names are asserted against the
  spec on every build.
- **Review artifact**: during milestone reviews the diff of
  `contracts/` between freezes is the review of the API's
  evolution (docs/99 §10).

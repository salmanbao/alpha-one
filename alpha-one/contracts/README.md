# Alpha One — API & Event Contracts Pack

The contract source of truth for every Alpha One surface. The
module specs here are what the implementation **builds against**
and what CI **checks against** (docs/99 §12: the pack is the
source of truth; the code is generated/checked against it).

This pack is **generated**, not hand-edited. It is produced by
two generators from the canonical module docs (`docs/02`–`docs/27`)
plus the parsed PRD backlog (`scripts/prd-backlog.json`, 1012 rows).
If a doc changes, re-run the generators — never edit a generated
file in place.

```bash
python3 scripts/build_contracts.py           # OpenAPI specs + extended event schemas
python3 scripts/complete_contracts_pack.py   # post-V1 api specs, examples, extended registries
```

## Layout

```
contracts/
├── shared/openapi.yaml        # shared components (all specs $ref into this)
├── 02-AUTH.openapi.yaml       # one OpenAPI 3.1 spec per module doc (26 specs, 02…27)
├── …                          #   445 operations total
├── 27-SDK-DVP-TRD-PLT-CS.openapi.yaml
├── api/                       # human-readable endpoint contracts, one file per module (36)
│   ├── auth.md … tenant.md    #   V1 baseline: 20 files, Req-ID-cited, binding at freeze
│   └── sup.md … cs.md         #   post-V1: 16 files, PROVISIONAL (PRD scope + doc §7)
├── data/
│   ├── dictionary.md          #   canonical field dictionary
│   └── schemas/*.sql          #   per-module DDL, split from docs/32 (26 files, 06/16/17 incl.)
├── events/
│   ├── catalog.md             #   V1 baseline event catalog (18 events, Req-ID-cited)
│   ├── payloads/              #   V1 baseline payload schemas (19 files incl. envelope)
│   ├── extended/              #   post-V1 topic schemas, JSON Schema 2020-12 (32 files, 141 events)
│   └── examples/              #   illustrative example per extended event (141 fixtures + README)
├── errors/taxonomy.md         #   error registry: 66 V1 codes (binding) + 232 extended (provisional)
├── permissions/registry.md    #   permission registry: 31 V1 keys (binding) + 69 provisional
└── diagrams/                  #   8 architecture/lifecycle diagrams (md source + png)
```

**Scope numbers (2026-09-19):** 26 OpenAPI specs (**445**
operations), 36 api specs, 26 SQL schemas, 32 extended event
schemas (**141 events**) + 141 examples, 19 V1 payloads,
298 error codes, 100 permission keys, 8 diagrams.

## Pack index (per module)

| Doc | Module | OpenAPI | api/*.md | SQL schema | Events | Errors | Permissions |
|---|---|---|---|---|---|---|---|
| 02 | AUTH | 02-AUTH | auth.md (V1) | 02-auth.sql | user.*, api_key.* | §AUTH (11 V1 + ext) | user.*, tenant.member.* |
| 03 | TEN | 03-TEN | tenant.md (V1) | 03-ten.sql | tenant.* | §TEN | tenant.* |
| 04 | GW+EVT | 04-GW-EVT | gw.md, evt.md (V1) | 04-gw-evt.sql | gateway.*, relay.*, outbox.* | §GW+EVT | — (chain, not keys) |
| 05 | LED+AUD | 05-LED-AUD | led.md, aud.md (V1) | 05-led-aud.sql | ledger.*, audit.* | §LED/AUD | audit.* |
| 06 | OPS | 06-OPS | ops.md (V1) | 06-ops.sql | ops.* | §OPS | — (platform role) |
| 07 | LCC | 07-LCC | lcc.md (V1) | 07-lcc.sql | account.* (+9 V1 PascalCase) | §LCC | account.read/suspend |
| 08 | BRG | 08-BRG | brg.md (V1, no HTTP) | 08-brg.sql | bridge.*, equity.* | §BRG | — (worker-internal) |
| 09 | EVL | 09-EVL | evl.md (V1) | 09-evl.sql | evaluation.* | §EVL | challenge/ruleset/account.* |
| 10 | RSK | 10-RSK | rsk.md (V1) | 10-rsk.sql | risk.* | §RSK | risk.case.create |
| 11 | PAY | 11-PAY | pay.md (V1) | 11-pay.sql | payout.*, payment.* | §PAY | payout.* |
| 12 | CHK | 12-CHK | chk.md (V1) | 12-chk.sql | order.*, checkout.* | §CHK | checkout.create |
| 13 | KYC | 13-KYC | kyc.md (V1) | 13-kyc.sql | kyc.* | §KYC | kyc.review/restrictions |
| 14 | NOT | 14-NOT | not.md (V1) | 14-not.sql | notification.* | §NOT | — (V1: system) |
| 15 | DOC | 15-DOC | doc.md (V1) | 15-doc.sql | document.* | §DOC | document.read |
| 16 | TD | 16-TD | td.md (V1) | 16-td.sql (stateless) | — (consumes) | §TD | — (identity-scoped) |
| 17 | ADM | 17-ADM | adm.md (consumer) | 17-adm.sql (stateless) | — (consumes) | §ADM | via owning modules |
| 18 | SUP | 18-SUP | sup.md (prov.) | 18-sup.sql | ticket.* | §SUP | ticket.*, canned.*, support.* |
| 19 | ANA | 19-ANA | ana.md (V1) | 19-ana.sql | analytics.* | §ANA | analytics.read |
| 20 | CRM | 20-CRM | crm.md (prov.) | 20-crm.sql | crm.* | §CRM | segment.*, campaign.*, consent.* |
| 21 | CON | 21-CON | con.md (V1) | 21-con.sql | console.* | §CON | console.session.revoke |
| 22 | BIL | 22-BIL | bil.md (prov.) | 22-bil.sql | billing.* | §BIL | invoice.*, usage.*, dunning.* |
| 23 | AFF | 23-AFF | aff.md (prov.) | 23-aff.sql | affiliate.* | §AFF | affiliate.*, commission.* |
| 24 | CMS+CMP | 24-CMS-CMP | cms.md, cmp.md (prov.) | 24-cms-cmp.sql | site.* | §CMS/CMP | site.*, competition.*, prize.* |
| 25 | MIG | 25-MIG | mig.md (prov.) | 25-mig.sql | migration.* | §MIG | migration.* |
| 26 | MOB/JRN/EDU/CHT | 26-* | mob/jrn/edu/cht.md (prov.) | 26-*.sql | — (consume TD APIs) | §26 | journal.*, course.*, channel.*, message.* |
| 27 | SDK/DVP/TRD/PLT/CS | 27-* | sdk/dvp/trd/plt/cs.md (prov.) | 27-*.sql | developer.*, sandbox.*, webhook.* | §27 | devkey.*, webhook.*, copy.*, backtest.*, platform.*, tenant.health.*, nps.*, qbr.* |

Legend: **V1** = binding at the M1 freeze (docs/99 §12); **prov.** =
PROVISIONAL design-level, freezes with its phase. PLT/CS have no
dedicated HTTP surface (console screens + jobs — see their api specs).

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
   (docs/30). Error **codes** are the 298-entry taxonomy in
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

## Human-readable endpoint contracts (`api/`)

One file per module (36). The 20 V1 files are Req-ID-cited
against the V1 execution sheet and bind at the M1 freeze; the 16
post-V1 files carry the PRD scope table (feature + story + owner)
plus the module doc's §7 surface, marked PROVISIONAL. ADM/BRG/PLT/CS
document their *absence* of HTTP surface (consumers / worker-internal /
console-only) so the "no endpoint" decision is explicit, not a gap.

## Data contracts (`data/`)

`dictionary.md` is the canonical field dictionary; `schemas/*.sql`
is the per-module DDL split from docs/32 (docs/32 stays the source
of truth; the split exists so each module's tables are reviewable
and diffable in isolation). 06/16/17 are included: OPS holds the
platform tables (deploys, backups, incidents, SLO defs); TD/ADM
attest their statelessness (FE never touches PG) plus the
browser-state contract.

## Event schemas (`events/`)

- `catalog.md` — the V1 baseline catalog (18 events, Req-ID-cited).
- `payloads/` — V1 baseline payload schemas (18 + envelope).
- `extended/` — post-V1 topic schemas, JSON Schema 2020-12 (32
  files, 141 events). Each file is a `$defs` of the individual
  events (each `allOf`-composing the shared `EventEnvelope`) plus
  a top-level `anyOf` over the domain's events — validate a
  message against the file, and the `event` name tells you which
  event it is.
- `examples/` — one illustrative example instance per extended
  event (141 fixtures): envelope fields are stable (EVT-03),
  `payload` is `{}` until that phase's freeze. Consumer-test
  scaffolding: copy, fill the payload from the module doc's
  §4/§8, assert envelope handling + idempotency-by-`id`.

Rules (docs/31, docs/04 §5.6, docs/99 §12):

- **Additive only** between freezes; a changed/removed field = a
  new `event_version` (never an in-place change).
- `tenant_id` is mandatory on every event (shared-schema
  multi-tenancy, ADR-1).
- Delivery is at-least-once via Redis Streams (ADR-7); consumers
  must be idempotent on `(event, id)`.
- The 150-row catalog with producer/consumer/SLA is
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
`shared/` resolve) plus JSON parsing of every event file. Run it
exactly like CI does:

```bash
cd contracts
for f in shared/openapi.yaml *.openapi.yaml; do
  openapi-spec-validator "$f" || exit 1
done
for f in events/extended/*.schema.json events/payloads/*.json events/examples/*/*.json; do
  python3 -c "import json; json.load(open('$f'))" || exit 1
done
python3 ../scripts/complete_contracts_pack.py --check-only  # coverage cross-check
```

CI (docs/06, Phase 0) runs this on every PR that touches
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

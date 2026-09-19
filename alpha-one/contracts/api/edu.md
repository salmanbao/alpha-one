# Education Hub (Part C) API Contract (EDU)

Status: PROVISIONAL (post-V1, design-level)
Owner: TBD
Version: v1
Last updated: 2026-09-19

Derived from `docs/26-mobile-apps.md` §7 + PRD EDU-NN (V2.0, V3.0). Nothing here is final until that phase's contract freeze (docs/99 §12).

## Scope

PRD module **EDU** (9 requirements). Abridged backlog:

| Req | Feature | Release | Pri | Owner | User story (abridged) |
|---|---|---|---|---|---|
| `EDU-01` | Course library | V2.0 | P1 | FE-1 | As a trader, I can browse a library of courses and lessons so that I learn trading fundamentals inside the portal. |
| `EDU-02` | Video lessons | V2.0 | P1 | FE-1 | As a trader, I can watch video lessons with progress tracking so that I learn at my own pace. |
| `EDU-03` | Lesson quizzes | V2.0 | P2 | FE-1 | As a trader, I can take quizzes at the end of lessons so that I check my understanding. |
| `EDU-04` | Progress tracking | V2.0 | P2 | FE-1 | As a trader, I see my overall course progress so that I stay motivated. |
| `EDU-05` | Completion certificates | V2.0 | P2 | FE-1 | As a trader, I receive a certificate when I complete a course so that my learning is recognized. |
| `EDU-06` | Admin course authoring | V3.0 | P2 | BE-2 | As a tenant admin, I can author and publish lessons and courses so that education matches my firm. |
| `EDU-07` | Lesson completion tracking | V2.0 | P1 | FE-1 | As a trader, I see per-lesson completion state so that I can resume learning precisely where I stopped. |
| `EDU-08` | Learning paths | V2.0 | P2 | FE-1 | As a trader, I follow sequenced learning paths (beginner → advanced), so that learning is structured. |
| `EDU-09` | Course enrollment | V2.0 | P2 | FE-1 | As a trader, I explicitly enroll in a course so that my progress and completion are tracked per path. |

## Auth

Trader (learn) + staff (publish, Tenant Admin). All routes sit in the GW chain (docs/04 §3.1): tenant resolution →
authn → authz (`resource.action` key per route) → rate limit → entitlement gate →
idempotency → audit. Error envelope per GW-18 (`code`, `message`, `correlation_id`).

## Tenant resolution

From domain (GW-02) for web routes; from the API key for machine routes (key wins
over any header); `X-Tenant-Id` header for internal service tokens only. Unknown
host/key → `404 tenant.not_found` (no-oracle rule, docs/04 §6).

## Permissions

No dedicated permission keys beyond the V1 registry are fixed yet — keys are proposed in the module doc's §7 and freeze with the module.

## Idempotency

Mutating requests accept an `Idempotency-Key` header per GW-12 (24 h TTL, scope =
method+path+key). Retries MUST NOT create duplicate resources.

## Endpoints (provisional)

> Copied verbatim from `docs/26-mobile-apps.md` §7 on 2026-09-19 — the module doc is authoritative if they drift; regenerate with `python3 scripts/complete_contracts_pack.py`.

Trader (TD "Learn" section):
`GET /v1/edu/library` (the tenant's published courses + paths),
`GET /v1/edu/courses/{id}` (the blocks, the progress state),
`POST /v1/edu/enrollments` `{course_id? | path_id?}`,
`GET /v1/edu/enrollments` (the progress overview — the §3.2 states),
`POST /v1/edu/blocks/{id}/progress` (the video position claim / the
text mark-read — the server-side max-claim logic),
`POST /v1/edu/quizzes/{id}/attempts` (the answers → the
server-check → the result),
`GET /v1/edu/certificates` (the earned, the DOC links),
`GET /v/edu/certificates/{cert_hash}` (V2: the public verify —
the DOC-16 pattern, the allowlisted content).

Staff (ADM, V2 the import/seed surface; V3 the EDU-06 authoring):
`GET|POST /v1/admin/edu/courses` (+ the block editor V3, the
versioning, the publish — the CMS-03 pattern reused),
`POST /v1/admin/edu/courses/{id}/media` (the large-upload, the
tenant-staff only),
`GET|POST /v1/admin/edu/paths` (the path builder),
`GET /v1/admin/edu/analytics` (the completion rates, the quiz
pass rates, the drop-off by block — the ANA-adjacent report, the
"which lesson do traders quit" metric — the tenant's content
improvement loop).

## Open contract questions

- Paths, methods, and field names below are PROVISIONAL until this module's phase
  freeze (docs/99 §12) — additive changes only after freeze; breaking changes get
  `/v2/` + the 12-month deprecation rule for public surfaces.
- Permission keys: the V1 registry (`permissions/registry.md`) is binding; keys used
  below beyond it are provisional and join the registry at freeze.
- Error codes: V1 baseline codes are binding (`errors/taxonomy.md`); extended codes
  follow the GW-18 dotted convention and freeze with the module (docs/30).

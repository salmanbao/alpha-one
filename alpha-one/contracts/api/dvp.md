# Developer Portal (Part A, portal API) API Contract (DVP)

Status: PROVISIONAL (post-V1, design-level)
Owner: TBD
Version: v1
Last updated: 2026-09-19

Derived from `docs/27-ecosystem.md` §7 + PRD DVP-NN (V3.0). Nothing here is final until that phase's contract freeze (docs/99 §12).

## Scope

PRD module **DVP** (18 requirements). Abridged backlog:

| Req | Feature | Release | Pri | Owner | User story (abridged) |
|---|---|---|---|---|---|
| `DVP-01` | Public developer portal site | V3.0 | P0 | BE-1 | As an external developer, I land on a public portal with documentation, guides, API reference, and changelog so that I can evaluat… |
| `DVP-02` | Developer accounts | V3.0 | P0 | BE-1 | As an external developer, I create a developer account tied to a tenant or partner organization, separate from tenant user identit… |
| `DVP-03` | product subscription | V3.0 | P1 | BE-2 | As a developer, I subscribe to API products such as read-only reports, webhooks, and account management with plan-based quotas so … |
| `DVP-04` | Interactive API explorer | V3.0 | P1 | BE-1 | As a developer, I call endpoints from the portal against the sandbox using my own keys so that I can learn the API without writing… |
| `DVP-05` | Webhook simulator in portal | V3.0 | P1 | BE-2 | As a developer, I register a test endpoint from the portal UI and receive simulated events so that event onboarding is instant. |
| `DVP-06` | Developer usage analytics | V3.0 | P1 | BE-1 | As a developer or tenant admin, I see call volumes, error rates, and quota consumption per key so that I can debug and capacity-pl… |
| `DVP-07` | Public status page | V3.0 | P1 | DevOps | As a developer, I check a status page with component health and incident history so that I can trust operations and plan around in… |
| `DVP-08` | Changelog subscription | V3.0 | P1 | BE-1 | As a developer, I subscribe to changelog notifications by email or RSS so that I hear about changes before they affect me. |
| `DVP-09` | Low-code connectors | V3.0 | P2 | BE-2 | As an operations user, I use official Zapier and n8n connectors for common events such as payment captured and payout approved so … |
| `DVP-10` | Partner key delegation | V3.0 | P1 | BE-1 | As a tenant, I grant a partner organization scoped and time-boxed API access to my tenant so that agencies can build for me withou… |
| `DVP-11` | GraphQL query API | V3.0 | P2 | BE-1 | As a developer, I query nested tenant data through GraphQL so that complex reads take one call instead of many. |
| `DVP-12` | Streaming API | V3.0 | P2 | BE-1 | As a developer, I subscribe to near real-time account and event streams over WebSocket so that latency-sensitive integrations are … |
| `DVP-13` | Partner directory | V3.0 | P2 | BE-2 | As a tenant, I browse certified integration partners for KYC, payments, and CRM so that I can choose vetted vendors quickly. |
| `DVP-14` | Certification badge program | V3.0 | P2 | BE-2 | As a partner, I pass the certification checklist and receive a public badge and directory listing so that the ecosystem has qualit… |
| `DVP-15` | Developer community space | V3.0 | P2 | DevOps | As ops, I deploy to multiple regions for disaster recovery so that regional outages don't stop the platform. |
| `DVP-16` | detection | V3.0 | P1 | BE-1 | As a developer or tenant admin, I receive alerts on quota breaches and abnormal API key usage, so that integration issues surface … |
| `DVP-17` |  | V3.0 | P2 | BE-2 | As a developer, I open and track support tickets from the portal, so that integration help is centralized. |
| `DVP-18` | API mock server | V3.0 | P2 | BE-1 | As a developer, I test against a mock API without consuming sandbox quotas, so that iteration is fast. |

## Auth

Developers (firm:developer session on dev portal; 2FA on key create/revoke). All routes sit in the GW chain (docs/04 §3.1): tenant resolution →
authn → authz (`resource.action` key per route) → rate limit → entitlement gate →
idempotency → audit. Error envelope per GW-18 (`code`, `message`, `correlation_id`).

## Tenant resolution

From domain (GW-02) for web routes; from the API key for machine routes (key wins
over any header); `X-Tenant-Id` header for internal service tokens only. Unknown
host/key → `404 tenant.not_found` (no-oracle rule, docs/04 §6).

## Permissions

Public scopes (e.g. `trades:read`) + portal keys; full scope catalog freezes with the V3 public API (docs/27 Part A §3.1).

## Idempotency

Mutating requests accept an `Idempotency-Key` header per GW-12 (24 h TTL, scope =
method+path+key). Retries MUST NOT create duplicate resources.

## Endpoints (provisional)

> Copied verbatim from `docs/27-ecosystem.md` §7 on 2026-09-19 — the module doc is authoritative if they drift; regenerate with `python3 scripts/complete_contracts_pack.py`.

the contracts pack; the developer-facing portal API)

Portal (`dev.alphaone.example`, the developer-authed — the
`firm:developer` session):
`GET /dvp/docs/*` (the generated docs, the static + the
dynamic (the changelog, the status)),
`GET|POST /dvp/keys` (the management, the scopes, the
rotation, the revocation — the 2FA on the create/revoke),
`POST /dvp/keys/{id}/delegate` (the DVP-10),
`GET /dvp/usage` (the DVP-06: the calls, the webhooks, the
limits),
`GET /dvp/webhooks/deliveries` (the log, the DVP-05/07),
`POST /dvp/webhooks/{delivery}/replay` (the sandbox),
`GET /dvp/status` (the DVP-07 data),
`GET /dvp/changelog` (the DVP-08, the subscription),
`POST /dvp/support/tickets` (the DVP-17, the SUP category),
`POST /dvp/sandbox/reset` (the §5 reset),
`GET /dvp/directory` (the DVP-13, the public),
`GET /dvp/certification` (the SDK-10 status).

The public API (the §3.1 table, the `/v1/public/*` +
`/v1/sandbox/*` + the GraphQL + the SSE) — the routes are
the GW's (the 04 chain), the spec is the contracts pack
(the OpenAPI 3.1, the `contracts/` deliverable).

## Open contract questions

- Paths, methods, and field names below are PROVISIONAL until this module's phase
  freeze (docs/99 §12) — additive changes only after freeze; breaking changes get
  `/v2/` + the 12-month deprecation rule for public surfaces.
- Permission keys: the V1 registry (`permissions/registry.md`) is binding; keys used
  below beyond it are provisional and join the registry at freeze.
- Error codes: V1 baseline codes are binding (`errors/taxonomy.md`); extended codes
  follow the GW-18 dotted convention and freeze with the module (docs/30).

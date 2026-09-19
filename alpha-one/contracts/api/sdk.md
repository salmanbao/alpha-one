# BYO Integration SDK (Part A, public API) API Contract (SDK)

Status: PROVISIONAL (post-V1, design-level)
Owner: TBD
Version: v1
Last updated: 2026-09-19

Derived from `docs/27-ecosystem.md` §7 + PRD SDK-NN (V3.0). Nothing here is final until that phase's contract freeze (docs/99 §12).

## Scope

PRD module **SDK** (18 requirements). Abridged backlog:

| Req | Feature | Release | Pri | Owner | User story (abridged) |
|---|---|---|---|---|---|
| `SDK-01` | Public API contract and versioning policy | V3.0 | P0 | BE-1 | As the platform, I publish a versioned public API contract with a written deprecation policy so that integrators can build with co… |
| `SDK-02` | Webhook event catalog | V3.0 | P0 | BE-2 | As an integrator, I get a documented catalog of all outbound events with schemas, versions, and example payloads so that I can con… |
| `SDK-03` | Signature verification helpers | V3.0 | P0 | BE-2 | As an integrator, I use official helper libraries for TypeScript and Python to verify webhook signatures so that my security imple… |
| `SDK-04` | core | V3.0 | P1 | BE-1 | As an integrator, I use an official client SDK with authentication, pagination, idempotency keys, and error handling so that my in… |
| `SDK-05` | Sandbox tenant environment | V3.0 | P0 | BE-2 | As an integrator, I get a sandbox tenant with synthetic test data and simulated events so that I can build without touching produc… |
| `SDK-06` | Sandbox event injection | V3.0 | P1 | BE-2 | As an integrator, I can trigger simulated lifecycle events such as payment captured, account passed, and payout approved in the sa… |
| `SDK-07` | Webhook replay and testing tools | V3.0 | P1 | BE-2 | As an integrator, I can replay past webhook deliveries to my endpoint from the delivery log so that debugging is self-serve. |
| `SDK-08` | Developer portal docs | V3.0 | P0 | BE-1 | As an integrator, I read generated API reference plus integration guides for each swappable path including checkout, affiliate, KY… |
| `SDK-09` | key self-management | V3.0 | P0 | FE-2 | As a tenant admin or integrator, I create, scope, rotate, and revoke API keys from the admin panel with audit so that machine acce… |
| `SDK-10` | Integration certification checklist | V3.0 | P2 | BE-2 | As the platform, I run an automated checklist against the sandbox verifying signature checks, idempotency handling, and retry beha… |
| `SDK-11` | status API | V3.0 | P1 | BE-2 | As a tenant running external KYC, I push verification decisions through the API so that my external flow still gates funding and p… |
| `SDK-12` | accounting export | V3.0 | P2 | BE-2 | As a tenant running external accounting, I pull journal and settlement data through the API or scheduled exports so that their boo… |
| `SDK-13` | sync | V3.0 | P2 | BE-2 | As a tenant running an external CRM, I subscribe to trader and lifecycle events and pull trader profiles so that their CRM stays c… |
| `SDK-14` | Public API rate limits and quotas | V3.0 | P1 | BE-1 | As the platform, I enforce documented per- tenant quotas on public endpoints so that one integrator cannot degrade the platform fo… |
| `SDK-15` | Changelog and deprecation channel | V3.0 | P1 | BE-1 | As an integrator, I get a changelog and advance notice of breaking changes so that my integration never breaks silently. |
| `SDK-16` | quickstart and code samples | V3.0 | P1 | BE-1 | As an integrator, I use runnable quickstarts and code samples, so that I can make my first API call quickly. |
| `SDK-17` | compatibility matrix | V3.0 | P1 | BE-1 | As an integrator, I see which SDK version supports which API version, so that upgrades are predictable. |
| `SDK-18` | package publishing pipeline | V3.0 | P1 | DevOps | As the platform, I publish SDK packages to npm and PyPI automatically from CI, so that releases are reliable. |

## Auth

External integrators (public API keys, UnKey-backed in V2+; ref-indirected ids). All routes sit in the GW chain (docs/04 §3.1): tenant resolution →
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

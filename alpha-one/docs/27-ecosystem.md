# 27 — Ecosystem: SDK · DVP · TRD · PLT · CS

> Covers PRD modules **SDK** (17 reqs, V3), **DVP** (18 reqs,
> V3), **TRD** (8 reqs, V3), **PLT** (6 reqs, V3 — 5 recovered),
> and **CS** (7 reqs, V3 — the requirement rows were in the
> unrecovered PRD band; scoped from the docs/00 catalog: "Tenant
> NPS, health scoring, churn prediction, QBRs" — the same
> Phase-1 confirmation item as TD, doc 16 §1). All five are V3
> by the PRD's phases; this doc is the V3 design made now, per
> the docs/00 commitment ("Modules marked V3 still get a full
> design doc now so architecture decisions — schemas, event
> contracts — are made while the foundations are fresh").
>
> **The shared spine:** all five are the platform's *external
> interfaces* — DVP/SDK are for the tenants' developers, TRD is
> the trading-advanced layer for the tenants' traders, PLT is
> the platform's own scale governance, CS is the platform's
> tenant relationship. They consume the same GW, the same EVT,
> the same AUD, and they inherit the same rules: tenant isolation
> is structural, PII never leaves the house without a named
> contract, and the public API is the platform's most durable
> commitment (the deprecation discipline, Part A §3.5).

---

# Part A — DVP: Developer Portal + SDK: BYO Integration (18 + 17 reqs)

## 1. Purpose & scope

**DVP (18, V3):** the public developer portal (DVP-01), developer
accounts (DVP-02), API product subscription (DVP-03), interactive
API explorer (DVP-04), webhook simulator (DVP-05), usage analytics
(DVP-06), public status page (DVP-07), changelog subscription
(DVP-08), low-code connectors (DVP-09 — the n8n-class integration
surface, the register's "consider-later" becomes this), partner key
delegation (DVP-10), GraphQL query API (DVP-11), streaming API
(DVP-12), partner directory (DVP-13), certification badge (DVP-14),
usage alerts (DVP-16), developer support tickets (DVP-17), mock
server (DVP-18).

**SDK (17, V3):** the public API contract (SDK-01), the webhook
event catalog (SDK-02), signature verification helpers (SDK-03),
the client SDK core (SDK-04), the sandbox tenant environment
(SDK-05), sandbox event injection (SDK-06), webhook replay &
testing (SDK-07), integration certification (SDK-10), changelog &
deprecation (SDK-15), public API rate limits (SDK-14), quickstart
& code samples (SDK-16), compatibility matrix (SDK-17), SDK
package publishing (SDK-18), the BYO-KYC status API (SDK-11), the
BYO-accounting export (SDK-12), the BYO-CRM sync (SDK-13).

**The product in one line:** a tenant (or its agency, or its
software vendor) can build *their own* front-end, CRM, accounting,
or trading tool against Alpha One's public API + webhooks +
sandbox — "BYO" (bring your own) is the D5 domain's promise: the
platform is the system of record, the tenant's ecosystem is
unlimited. The anchor tenant (FunderBlu) is the first customer of
its own platform API (their agency builds the marketing site's
live data, their accounting pulls the LED export, their CRM syncs
the trader states).

**Binding decisions:**
- **The public API is a versioned surface of the same GW**
  (SDK-01): the `/v1/` routes gain the external-key auth (the
  AUTH-25 API keys, the 02 §3.5 design: `sk_live_t_…` /
  `sk_test_t_…`, the scopes, the 600 req/min base) — there is no
  separate "public API server"; the GW's tenant resolution (the
  key → the tenant, the 04 §3.4 chain) + the rate limits (the
  04's per-key tier, the SDK-14 config) + the idempotency (the
  04 §3.3) are the public API. The **public subset** is declared
  per route (a route is either `internal` (session-authed, the
  TD/ADM/CON surfaces) or `public` (key-authed, the documented
  contract) — the declaration is in the route registry, the CI
  check: a public route without a docs entry fails the build,
  the SDK-01 contract test).
- **The contract is the OpenAPI pack** (the `contracts/` deliverable,
  the README convention): the public API = the OpenAPI 3.1 spec +
  the webhook event JSON schemas (SDK-02) + the error contract
  (the 04 single error shape, the 30-error-taxonomy's public
  codes) — the spec is the source of truth for the SDK, the
  explorer (DVP-04), and the mock server (DVP-18) (all three are
  generated from the same spec — the one-contract rule: a
  divergence between the spec and the code is a CI failure, the
  contract tests, the 04 §6 error-code registry's CI gate
  extended to the public routes).
- **The sandbox (SDK-05/06, DVP-18):** a sandbox = a **staging
  tenant with synthetic data + a synthetic broker** (the 06 §2
  rule — staging is synthetic-only, the MetaApi demo accounts,
  the 01 ADR posture): the sandbox tenant gets a full platform
  (the packages, the flow, the webhooks) against the demo broker;
  the event injection (SDK-06) = the test-harness endpoint
  (`POST /v1/sandbox/inject` — a sandbox-only route: fire
  `account.funded`, `payout.settled`, a synthetic tick, a breach —
  the developer tests their webhook handlers against real event
  shapes without waiting for a real trade; the injection is
  sandbox-tenant-scoped, audited, and **structurally impossible
  in production** (the route 404s on a live tenant — the
  environment claim on the key (`sk_test_` vs `sk_live_`) is
  what the route checks, the 02 §3.5 key class)).
- **GraphQL (DVP-11) & streaming (DVP-12):** GraphQL is a
  **query projection over the public REST data** (the
  read-only, the key-authed, the same rate limits — the
  graphql-go resolver over the public routes' data; it's a
  convenience for the tenant's front-end, not a new data path —
  the resolvers call the same domain reads, the tenant
  isolation is inherited); streaming = the SSE public endpoint
  (the `account.*`/`payout.*` events for a key's tenant, the
  01 §4.3 relay, the key-authed — the DVP-12 "streaming API"
  is the public version of the TD SSE, the same relay).
- **The BYO surface (SDK-11/12/13):** these are the
  high-value read APIs the "BYO" promise names explicitly:
  - **BYO-KYC status (SDK-11):** the tenant's external KYC
    provider's status sync *into* us (the tenant runs its own
    Veriff/Sumsub for some flow and pushes the status — the
    `POST /v1/public/kyc/status-sync` with the provider case ref;
    the KYC-01 adapter pattern's external input, the 13 §1
    adapter interface; the audit: the external KYC claim is
    recorded with the provider + the case ref, the reverify
    posture (the 25 §3.3 pattern) applies: an external claim
    marks `source: external:{provider}`, the payout gate reads
    it with the same weight as the platform flow only if the
    tenant's config `kyc.external_accepted: true` (the FunderBlu
    default: false — the platform verification is the gate, the
    BYO-KYC is a convenience sync, the labeled posture))
  - **BYO-accounting (SDK-12):** the tenant pulls the ledger
    data for their own books — the **accounting export API**
    (`GET /v1/public/accounting/ledger?from=&to=` — the LED's
    entries + the CoA + the balances, the 05 §9 schema, the
    CSV/JSON, the key-scoped to the tenant, the 7-yr
    availability (the LED retention), the **read-only, the
    hash-verifiable** (the export carries the R2 hash snapshot
    refs, the 05 §3.5 nightly snapshot — the tenant's
    accountant can verify the export against the platform's
    published hash, the trust artifact); this is the
    QuickBooks/Xero bridge's data source (the register's
    consider-later: the connector (DVP-09) maps the export to
    the accounting system, the data path is the export API))
  - **BYO-CRM sync (SDK-13):** the tenant's CRM pulls the
    trader lifecycle states (the `traders_ro`-class data, the
    19 §3.1 read model — the public subset: the identity id,
    the stage, the account states, the payout states, the
    KYC gate states — **no PII beyond the masked name/email
    (the 19 §10 rule extends to the public API: the BYO-CRM
    sync carries the CRM-usable fields, the contact data is
    the tenant's own (they have it), we carry the states))
- **The portal (DVP-01..08, 13..18):** the developer portal is
  a **public web app** (the `web/dvp`, the monorepo's fifth
  app, the 01 §2 web stack) on `dev.alphaone.example` (+ the
  tenant's white-label subdomain option, the TEN-14 domain
  config extends to the portal): the docs (generated from the
  OpenAPI + the markdown guides), the API explorer (the
  Scalar/Stoplight-class embed, generated from the spec — the
  DVP-04), the keys management (the developer's keys, the
  scopes, the rotation — the AUTH-25 surface, the developer
  account = a `platform:developer`-class identity in the
  tenant's org (the DVP-02: the developer is the tenant's
  person/agency, their account is a tenant membership with the
  `developer` role (the 02 §3.2 role set extended:
  `firm:developer` — the key management scope, the docs read
  scope; the developer role has **no trader data access**
  (the structural rule: a developer key's scopes are
  API-level, the developer *person* sees their keys + usage +
  the docs, never the traders' data — the two are distinct:
  the key's scopes define what the API returns, the developer
  account's role defines what the portal shows))), the webhook
  simulator (the DVP-05: the developer points their endpoint at
  the sandbox, fires the injection (SDK-06), sees the delivery
  log (the Hook0 delivery, the 04 §5.6 egress log, the
  developer-visible subset: the event, the status, the
  signature headers, the replay (SDK-07))), the usage
  analytics (the DVP-06: the key's calls by route/status/day,
  the webhook delivery rate, the rate-limit hits — the ANA-
  adjacent read model, the developer-scoped), the status page
  (the DVP-07: the public health (the 06's health endpoints +
  the incident feed (the CON-15 class, the public subset —
  the Uptime Kuma public page + the incident notes, the
  21 §3.2 posture: the status page is the honest feed, the
  "degraded" state is public)), the changelog (the DVP-08/
  SDK-15: the API changelog — the versioned, the
  deprecation-notice-carrying, the subscription (the email
  feed, the NOT template)), the partner directory (the DVP-13:
  the certified integrations list — the "builds on Alpha One"
  registry, the certification badge (DVP-14) is the mark),
  the usage alerts (the DVP-16: the key's usage thresholds
  (80%/100% of the quota) → the email, the NOT pattern),
  the developer support (the DVP-17: the SUP ticket's
  `developer` category, the 18 §3.1 pattern — the developer's
  ticket carries the key id (never the key), the sandbox
  context, the error codes), the mock server (the DVP-18:
  the spec-generated mock (the Prism-class, the
  register-consistent OSS) — the developer's local dev
  environment: `npm i @alphaone/mock` runs the mock from the
  spec, the CI-friendly, the no-network-needed).

Requirement coverage: `DVP-01..18` (all V3) + `SDK-01..18`
(all V3).

## 2. Architecture

```
 the external developer (the tenant's dev / agency / vendor):
   · the portal (web/dvp, the public app, the tenant-scoped):
     docs (generated) · explorer (generated, the spec) · keys
     (the AUTH-25 management, the scopes) · the webhook
     simulator (the sandbox) · usage · the status · the
     changelog · the support (the SUP category)
   · the SDK (the published packages, the SDK-18):
     the client SDK core (SDK-04) — Go + TypeScript (the two
     languages the tenant base writes in; the community
     Python/PHP is the V3-late, the SDK-17 matrix lists the
     supported set) — the SDK is thin: the HTTP client + the
     auth (the key + the signature) + the webhook verifier
     (SDK-03) + the typed models (generated from the OpenAPI)
     + the retry (the idempotency-key-aware, the 04 §3.3
     pattern) — the SDK-16 quickstart: the 5-minute path
     (install → key → first call → first webhook verified)
   · the API (the public subset of the GW, the §1 binding):
     REST (/v1/public/*, the key-authed, the scoped, the
     rate-limited, the idempotent, the versioned) + GraphQL
     (the read projection) + SSE (the stream) + the webhooks
     (the egress, the Hook0, the signed)
   · the sandbox (the staging tenant, the synthetic broker,
     the injection endpoint, the mock server)
 the webhook egress (the SDK-02/03/07 contract):
   · the event catalog: the public event set (the `account.*`,
     the `payout.*`, the `payments.*`, the `kyc.*`, the
     `order.*` subsets the developer subscribes to — the
     subscription is the key's config (the scopes include
     `webhook:{topic}`), the Hook0 delivery (the 04 §5.6:
     the retry, the signature (the HMAC-SHA256 of the body +
     the timestamp + the key secret — the SDK-03 verifier is
     the reference implementation, the timestamp tolerance
     ±5 min, the replay protection), the delivery log)
   · the replay (SDK-07): the developer re-delivers a past
     event (the sandbox: the full history; the production:
     the replay is the tenant-admin action (the ADM's
     webhook manager, the 04 §5.7 replay policy — the
     developer sees the replay in the simulator, the
     production replay is the tenant's ops action, the
     AUD-critical, the "why did my CRM miss that event"
     answer)
   · the BYO surface (the SDK-11/12/13, the §1 decisions)
 the certification (the SDK-10, the DVP-14): the integration
   certification = the conformance suite (the public test
   suite: the developer's integration runs against the
   sandbox's conformance harness (the 50-check suite: the
   auth, the error handling, the idempotency, the webhook
   signature verification, the pagination, the rate-limit
   backoff, the BYO-export parse) — pass = the certified
   badge (the DVP-14) + the partner directory listing (the
   DVP-13) — the certification is the platform's quality
   gate on the ecosystem (the "works with Alpha One" mark,
   the FunderBlu's agency gets it first (the anchor
   tenant's integration is the reference certification))
```

## 3. System design

### 3.1 The public API surface (the SDK-01 contract, V3 set)

| Area | Endpoints (the public subset) | Notes |
|---|---|---|
| **Accounts** | `GET /v1/public/accounts` (+detail, the states, the metrics (the observed, the 09 §3.4 class — the public metrics are the observed numbers, the tenant's traders' data, the key's tenant-scoped), the positions/deals read (the BRG read API, the 08 §7 public subset)) | the tenant's system of record read — the "BYO front-end" data source |
| **Payouts** | `GET /v1/public/payouts` (the states, the amounts, the method **masked** (the 11 §10 masking extends: the public API never returns the full wallet string — the tenant's CRM doesn't need it, the payout execution is the platform's)), `POST /v1/public/payouts/requests` (the **tenant-initiated** payout request — the tenant's own system requests the payout on the trader's behalf (the idempotency key, the eligibility check, the 11 §3.1 — the request is the same object, the channel is the API (the audit: the request source is `api:{key_id}` — the "who requested" is answerable)) | the money-adjacent public surface — the strictest scope (`payout:write`), the 2FA-equivalent: the API request is **always manual-approval** (the auto-approve never applies to the API channel — the 11 §3.5 posture: the API is a machine, the machine's request always gets the human; the labeled rule) |
| **Payments** | `GET /v1/public/payments` (the orders, the intents' states, the invoices (the DOC links, the 15 §7 public subset)), `POST /v1/public/payments/checkout-sessions` (the **checkout link** — the tenant's system creates a checkout session (the pre-filled package), returns the URL, the trader completes it in the platform (the login-first rule holds: the URL carries the session, the trader logs in, the checkout is the platform's — the BYO checkout is the *link*, not the *flow* (the 12 §1 posture: the payment flow is the platform's, the tenant's UI is around it)) | the conversion surface for the BYO front-end |
| **KYC** | `GET /v1/public/kyc/status` (the states per identity (the masked, the 13 §7 public subset)), `POST /v1/public/kyc/status-sync` (the SDK-11, the §1 rule) | the gate states, not the documents (the documents never leave — the 13 §10 rule extends to the public API: the KYC data is the most PII-dense class, the public surface is the *states*, the `reverify` posture) |
| **Trading** | `GET /v1/public/accounts/{id}/positions|deals|equity` (the read, the BRG public subset), `GET /v1/public/streams/{account_id}` (the SSE, the DVP-12) | the read-only (the trading itself is the trader's MT5 — the platform's public API never executes trades in V3 (the TRD Part C is the advanced layer, the separate design)) |
| **Accounting** | `GET /v1/public/accounting/ledger` (the SDK-12 export, the hash-verifiable), `GET /v1/public/accounting/balances` (the 05 §3.4 balances) | the BYO-accounting data path |
| **CRM** | `GET /v1/public/crm/traders` (the SDK-13 states sync, the masked PII rule) | the BYO-CRM data path |
| **Webhooks** | the subscription config (the key's topics), the delivery log (the developer-visible), the replay (the sandbox full / the production tenant-admin) | the SDK-02/03/07 |
| **Sandbox** | `POST /v1/sandbox/inject` (the SDK-06, the sandbox-only), the mock server (the DVP-18, the spec-generated) | the test environment |
| **Meta** | `GET /v1/public/meta/health` (the status page data), `GET /v1/public/meta/changelog` (the DVP-08) | the platform transparency |

**The rate limits (SDK-14):** the per-key tier (the 04 §3.4
config): the base 600 req/min (the AUTH-25 default), the
read-heavy burst (the 10× for the GET-only, the 6000 burst),
the write tier (the `payout:write`-class: the 60/min — the
money-adjacent writes are deliberately slow, the 11 §11
posture), the SSE connections (the 10/key), the webhook
delivery (the Hook0's per-endpoint limits, the 04 §5.6). The
429 carries the `Retry-After` + the `X-RateLimit-Remaining`
headers (the SDK-16 quickstart teaches the backoff — the SDK
core does it by default, the labeled behavior).

### 3.2 The webhook contract (the SDK-02/03 — the durable part)

```
the delivery (the Hook0 egress, the 04 §5.6):
  POST {the developer's endpoint}
  Headers:
    X-AlphaOne-Signature: t={unix_ts},v1={hmac_sha256(
        ts + "." + body, the key's webhook_secret)}
    X-AlphaOne-Event: {event_type}
    X-AlphaOne-Delivery-Id: {the delivery id (the replay ref)}
    X-AlphaOne-Retry: {n}
  Body: the event JSON (the 31-event-catalog's public subset —
    the schema per event type, the JSON-Schema files in
    contracts/events/ (the README's contracts pack), the
    versioned (the `event_version` field, the additive-only
    evolution rule — a new field is OK, a changed/removed
    field is a new event version, the SDK-15 deprecation
    policy))
  Verification (the SDK-03, the reference implementation):
    1. the timestamp within ±5 min (the replay window)
    2. the HMAC over ts + "." + raw body (the raw-body rule —
       the SDK warns against body-re-serialization, the
       04 §5.6 posture)
    3. the secret = the key's webhook_secret (the separate
       from the API key (the two secrets, the 02 §3.5 key
       class: the API key auths the calls, the webhook secret
       signs the deliveries — the key rotation doesn't break
       the webhooks and vice versa, the two-rotation
       surface))
  The retry (the 04 §5.6): the 5 attempts (the 1m/5m/30m/2h/
    6h backoff), the 2xx/3xx = delivered, the DLQ → the
    delivery log (the developer sees the failure + the
    one-click replay (the sandbox) / the tenant-admin replay
    (the production))
  The idempotency (the consumer rule, the 04 §5.7): the
    developer dedupes on the Delivery-Id (the SDK-16
    quickstart shows the dedupe table — the at-least-once
    delivery is the contract, the idempotent consumer is the
    developer's job, the documented posture)
```

### 3.3 The developer account & the keys (the DVP-02, the AUTH-25
extension)

```
the developer: the tenant org's member (the 02 §3.2
  membership) with the `firm:developer` role (the key
  management + the docs + the usage + the support — the
  **no trader data** rule: the developer role's portal
  views are the keys/usage/docs/status/changelog/support —
  the traders' data is reachable only via the API with the
  key's scopes (the separation: the person sees the
  instrumentation, the key sees the data, the two are
  distinct surfaces — the 02 §3.4 realm posture applied
  within the tenant realm))
the key (the AUTH-25, the 02 §3.5 design, the public
  extension): sk_live_t_… / sk_test_t_… (the environment
  class), the scopes (the per-area: the `accounts:read`,
  the `payouts:read`, the `payouts:write` (the strictest,
  the manual-approval rule, the §3.1), the `payments:read`,
  the `payments:checkout` (the checkout-session create),
  the `kyc:read`, the `kyc:sync` (the SDK-11), the
  `accounting:read`, the `crm:read`, the `trading:read`,
  the `webhook:{topic}`, the `sandbox:inject` (the
  sandbox-only)), the rate tier, the IP allowlist (the
  optional — the developer's office IP, the 02 §3.5
  posture), the rotation (the 24-h dual-live window, the
  02 §3.5), the revocation (the immediate, the deny-set)
the delegation (DVP-10): the partner key delegation — the
  tenant delegates a **scoped sub-key** to their partner
  (the agency): the sub-key's scopes ⊆ the parent's, the
  sub-key is labeled (the `delegated_from` ref, the audit:
  the partner's calls carry both keys in the audit trail,
  the "what did the agency do" answer), the revocation of
  the parent revokes the sub-keys (the delegation
  hierarchy is one level — the sub-sub-key is banned, the
  the depth cap, the 23 §1 MLM-cap posture applied to keys)
```

### 3.4 The sandbox (the SDK-05/06, the DVP-18)

```
the sandbox tenant: the staging tenant (the 06 §2
  synthetic-only, the MetaApi demo broker, the synthetic
  traders) + the developer's test keys (the sk_test_ class,
  the same GW, the staging environment) — the sandbox is
  the product (the DVP-05/18): the developer signs up on
  the portal (the DVP-02) → gets the sandbox tenant (the
  auto-provisioned, the 03 §3.1 saga, the synthetic-data
  class — the "trial-as-sandbox" rule, the 22 §3.5
  posture, the BIL-11 pattern) → the keys + the webhook
  endpoint + the injection
the injection (SDK-06): POST /v1/sandbox/inject {event,
  payload-override?} — the sandbox route (the 404 on live,
  the environment check), the audited (the sandbox audit,
  the low tier), the full event catalog injectable (the
  developer tests every handler) + the synthetic tick
  (the bridge.tick class, the 08 §3.2 feed) + the synthetic
  breach (the EVL verdict, the 09 class)
the mock server (DVP-18): the spec-generated (the Prism-
  class, the register-consistent) — `npx @alphaone/mock`
  (the SDK-18 package), the local, the no-network, the CI-
  friendly (the developer's unit tests run against the
  mock, the integration tests against the sandbox, the
  e2e against the staging tenant — the three-test
  pyramid, the SDK-16 quickstart's dev workflow)
```

### 3.5 The changelog & deprecation (the SDK-15, the DVP-08 —
the durable-commitment discipline)

```
the API versioning: the /v1/ (the 01 §2 URL-versioning
  rule) + the additive evolution (the OpenAPI's additive-
  only rule on the public routes — the CI check: a
  breaking change on a public route fails the build unless
  it's a /v2/ (the version-bump gate, the 04 §6 registry's
  CI extended))
the deprecation: the `Deprecation` header (the 30-error-
  taxonomy's deprecation code, the 04 error contract) +
  the changelog entry (the version, the date, the
  migration guide, the removal date — the **12-month
  minimum deprecation window** on the public API (the
  durability rule: the tenant's integration is their
  business infrastructure, the platform's commitment is
  the 12-month notice — the shorter window is a board-
  level exception, the CON-32-class approval, the labeled
  exception))
the changelog: the public feed (the DVP-08, the
  subscription, the NOT template, the RSS), the per-
  version (the additive changes, the deprecations, the
  breaking (the /v2/-class, the migration guide), the
  security (the CVE-class, the responsible-disclosure
  posture — the security changelog is the private-first,
  the public-after-the-fix, the 28 doc's disclosure
  policy))
the compatibility matrix (SDK-17): the SDK version × the
  API version × the Go/TS version (the published table,
  the SDK-16 quickstart's "which version for me" answer)
the certification (SDK-10, the DVP-14): the conformance
  suite (§2) + the badge + the directory (the DVP-13) —
  the certification is re-run on each SDK release (the
  certified integration stays certified or it lapses —
  the badge shows the last-certified date, the honest
  mark, the no-quiet-lapse rule: the lapse is a 30-day
  notice to the partner, the CHT-05-class notification)
```

## 4. Events (topic `developer` + the public egress)

| Event | When | Consumers |
|---|---|---|
| **Public egress (the webhooks):** the `account.*`, `payout.*`, `payments.*`, `kyc.*`, `order.*` public subsets (the 31-event-catalog's public class) | the domain events (the relay's egress, the Hook0) | the developer's endpoint (the tenant's system) |
| `developer.key_created/rotated/revoked` | the key lifecycle (the AUTH-25) | AUD (the critical on the revoke — the access change), the NOT (the tenant admin's notice) |
| `developer.delegation_created/revoked` (DVP-10) | the sub-key lifecycle | AUD (the critical — the partner's access), the NOT |
| `developer.usage_alert` (DVP-16) | the 80%/100% quota | the NOT (the developer's email), the AUD (the low) |
| `developer.certification_passed/lapsed` (SDK-10/DVP-14) | the conformance result | the portal (the badge), the directory, the AUD (the low) |
| `developer.support_ticket` (DVP-17) | the SUP category | the SUP queue (the 18 pattern), the AUD (the low) |
| `sandbox.inject` (SDK-06) | the injection | the AUD (the sandbox low), the ANA (the sandbox usage) |
| `webhook.delivery_failed_final` (the SDK-07) | the DLQ | the developer's log (the portal), the AUD (the low), the NOT (the tenant admin, the "your webhook is down" — the 04 §5.6 posture) |

## 5. Lifecycles

- **Key:** `created → active → (rotation: the 24-h dual-live) →
  revoked` (the 02 §3.5 machine, the public extension: the
  environment class (test/live) is immutable on the key, the
  scopes are editable (the scope widen = the 2FA (the key
  management's sensitive action, the ADM-adjacent 2FA rule,
  the 17 §3.3 pattern), the scope narrow is instant).
- **Delegation (DVP-10):** `created (the sub-key) → active →
  revoked` (the parent-revoke cascade, the §3.3 rule).
- **Sandbox tenant:** the 03 tenant machine (the `active`
  class, the synthetic-data flag) + the **sandbox-specific:
  the reset** (the developer's "reset my sandbox" — the
  wipe + the re-seed, the 2FA-light (the sandbox is
  synthetic, the reset is the convenience, the audited low
  tier) + the **sandbox expiry** (the 30-day inactivity →
  the archival (the data deleted, the keys dead, the
  re-provision is the new sandbox — the staging hygiene,
  the 06 §2 posture: the synthetic data doesn't accumulate
  forever)).
- **Webhook subscription:** `active → (the endpoint dead:
  the DLQ state, the delivery-log red) → (the endpoint
  recovered: the next delivery green) | unsubscribed` (the
  subscription state is the delivery health, the developer-
  visible, the DVP-05 simulator's dashboard).
- **Certification (SDK-10):** `applied → (the conformance
  run) → certified (the badge, the directory) → (the SDK
  release re-run) → certified (the new date) | lapsed (the
  30-day notice, the re-certify window) → unlisted` (the
  directory's honest state, the §3.5 rule).
- **Changelog entry:** `draft (the platform's) → published
  (the version cut) → (the deprecation: the 12-month clock
  starts) → (the removal: the /v2/ or the 410 (the
  deprecated route returns 410 + the migration header, the
  the 04 error contract's 410 class, the labeled
  end-of-life))`.
- **Developer account:** the 02 membership machine (the
  `firm:developer` role, the tenant-managed, the ADM-17-
  class role UI (the V2 ADM-17 extends to the developer
  role, the console's CON-18 for the platform developers)).

## 6. Error taxonomy (the public codes — the 30-error-taxonomy's
public namespace)

The public API uses the 04 single error contract + the
module codes' **public-safe subset** (the 30 doc aggregates;
the public-specific):

| Code | HTTP | Meaning (the public contract) |
|---|---|---|
| `public.auth_invalid` | 401 | The key is invalid/revoked (the no-detail leak — the 04 posture: the invalid key and the revoked key are the same 401, the oracle ban, the 02 §3.4 posture) |
| `public.scope_missing` | 403 | The key lacks the scope (the scope name in the `details` — the developer's fix is the scope request, the actionable error) |
| `public.rate_limited` | 429 | The tier limit (the `Retry-After`, the `X-RateLimit-*`, the tier name) |
| `public.env_mismatch` | 403 | A test key on a live route / a live key on a sandbox route (the environment claim check, the §1 binding) |
| `public.id_not_found` | 404 | The object (the tenant scope: another tenant's object = the 404, the 04 posture, the cross-tenant oracle ban) |
| `public.webhook_signature_invalid` | — | (the developer's side, the SDK-03 error class, the docs' troubleshooting) |
| `public.checkout_session_expired` | 409 | The checkout link dead (the TTL, the 12 §3.2 class) |
| `public.payout_manual_approval` | 202 | The API payout request accepted (the **always-manual rule, the §3.1** — the 202 + the `status: pending_approval`, the "the machine's request waits for the human" contract, the documented behavior) |
| `public.deprecated` | 200 + the `Deprecation` header | The 12-month window (the header: the sunset date, the migration URL, the SDK-15 contract) |
| `public.removed` | 410 | The end-of-life (the migration header, the labeled removal) |
| `public.kyc_sync_rejected` | 422 | The SDK-11 sync (the provider unrecognized, the tenant config `external_accepted: false`, the state conflict) |
| `sandbox.inject_invalid` | 422 | The SDK-06 (the event unknown, the payload schema fail) |
| `sandbox.live_only` | 404 | The sandbox route on a live tenant (the structural ban, the §1 rule — the 404, not the 403, the route-existence oracle ban) |

## 7. API endpoints (the public surface — the full registry in
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

## 8. Schema (key shapes — the public contract)

```jsonc
// the public event (the webhook body, the SDK-02)
{ "id": "evt_01J9…", "event": "payout.settled",
  "event_version": 1, "tenant_id": "01J9TEN…",
  "created_at": 1758282000000,
  "data": { "payout_id": "01J9PAY…", "identity_ref": "id_01J9…",
    "account_ref": "acc_01J9ACC…", "final_cents": 326304,
    "currency": "USD", "rail": "crypto_trc20",
    "method_preview": "TQrY…9fXz", "settled_at": 1758282000000 } }
// note: the public data uses the *ref* ids (the opaque
//  `id_…`/`acc_…` refs, the tenant-internal ULIDs are
//  never in the public API — the ref indirection: the
//  public id is a stable alias (the 19 §10 masked-PII
//  posture extended: the public surface carries the refs,
//  the mapping is the tenant's (they know their own
//  ids), the platform's internal ids are an
//  implementation detail — the durable-contract rule:
//  an internal ULID leak in the public API is a
//  contract break)

// the accounting export (the SDK-12)
{ "data": { "from": "2026-09-01", "to": "2026-09-30",
    "entries": [ { "entry_id": "le_01J9…", "at": 1758282000000,
        "account": "1000 (cash)", "debit_cents": 0,
        "credit_cents": 49900, "memo": "challenge purchase",
        "ref": "ord_01J9…" } ],
    "balances": [ { "account": "1000", "balance_cents": 12400000 } ],
    "hash_ref": "r2:led-hashes/{tenant}/2026-09.sha256" } }

// the CRM sync (the SDK-13)
{ "data": [ { "trader_ref": "id_01J9…", "stage": "funded",
    "name_masked": "Ali K.", "email_masked": "a***@example.com",
    "accounts": [ { "ref": "acc_01J9ACC…", "state": "funded" } ],
    "kyc": { "l1": "verified", "l2": "verified" },
    "last_payout_at": 1758200000000, "updated_at": 1758282000000 } ] }
```

## 9. Database design

```sql
-- the keys: the AUTH-25 (the 02 schema) — the public
-- extension columns:
--   api_keys.scope JSONB (the §3.3 scope set),
--   api_keys.environment TEXT ('test'|'live', the immutable),
--   api_keys.rate_tier TEXT (the SDK-14 config ref),
--   api_keys.ip_allowlist CIDR[],
--   api_keys.webhook_secret_hash TEXT (the separate secret,
--     the §3.2 two-secrets rule),
--   api_keys.delegated_from ULID (the DVP-10, the NULL for
--     the parent, the one-level cap, the §3.3)
-- the developer role: the tenant_memberships.role =
--   'firm:developer' (the 02 §3.2 role set)
CREATE TABLE public_id_refs (                    -- the §8 ref
  id            ULID PRIMARY KEY,                -- indirection (the
  tenant_id     ULID NOT NULL,                   --  durable-contract
  kind          TEXT NOT NULL,                   --  rule): the
  internal_id   ULID NOT NULL,                   --  public API's
  public_ref    TEXT NOT NULL,                   --  stable aliases
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, kind, internal_id),
  UNIQUE (tenant_id, public_ref)
);
-- the public_ref is the `id_…`/`acc_…`/`ord_…`/`pay_…`
-- string (the ULID-based, the tenant-scoped) — every public
-- API read/write translates: the public_ref in → the
-- internal id (the GW middleware, the 04 chain step), the
-- internal id out → the public_ref (the serializer, the
-- contract test: a public response containing a raw ULID
-- fails the CI (the property test, the §8 rule))
CREATE TABLE webhook_subscriptions (             -- the key's
  id            ULID PRIMARY KEY,                --  topics (the
  key_id        ULID NOT NULL,                   --  SDK-02
  topics        TEXT[] NOT NULL,                 --  subscription)
  endpoint      TEXT NOT NULL,
  active        BOOLEAN NOT NULL DEFAULT true,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE webhook_deliveries_public (         -- the developer-
  id            ULID PRIMARY KEY,                --  visible log
  key_id        ULID NOT NULL,                   --  (the DVP-05/07,
  event_id      TEXT NOT NULL,                   --  the SDK-07
  endpoint      TEXT NOT NULL,                   --  replay)
  state         TEXT NOT NULL,                   --  the delivery
  attempts      INT NOT NULL DEFAULT 0,          --  health
  last_status   INT, last_error TEXT,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_whd_key ON webhook_deliveries_public(key_id, created_at DESC);
CREATE TABLE developer_usage_daily (             -- the DVP-06
  key_id        ULID NOT NULL,
  day           DATE NOT NULL,
  calls         BIGINT NOT NULL,
  by_status     JSONB NOT NULL,                  --  read model
  webhook_deliveries BIGINT, webhook_failures BIGINT,
  rate_limited  BIGINT NOT NULL DEFAULT 0,
  PRIMARY KEY (key_id, day)
);
CREATE TABLE integrations_certified (            -- the SDK-10,
  id            ULID PRIMARY KEY,                --  the DVP-13/14
  tenant_id     ULID,                            --  the directory
  partner_name  TEXT NOT NULL,                   --  + the badge
  partner_url   TEXT, description TEXT,
  integration_type TEXT NOT NULL,                --  the "builds on
  sdk_version   TEXT,                            --  Alpha One"
  certified_at  TIMESTAMPTZ NOT NULL,
  last_run_at   TIMESTAMPTZ,
  state         TEXT NOT NULL DEFAULT 'certified'
    CHECK (state IN ('applied','certified','lapsed','unlisted')),
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- the changelog: the platform's (the docs/ changelog rows —
--   the version, the date, the changes JSONB, the
--   deprecations (the sunset dates), the security (the
--   private-first flag) — the PG table + the generated
--   feed (the DVP-08), the static site's data source
```

## 10. Security & compliance

- **The public API is the trust boundary with the outside
  world** (the 28 doc's perimeter): the key auth (the
  02 §3.5: the sha256 storage, the no-plaintext, the
  rotation, the revocation, the deny-set), the scope
  discipline (the per-area scopes, the widen-2FA, the
  §3.3), the rate limits (the SDK-14, the per-key tier,
  the write-slow rule), the tenant isolation (the
  structural, the 04 posture — the public API's cross-
  tenant read is the 404 + the security event (the
  CON-22-class alert: a key probing foreign tenant ids is
  the recon pattern, the RSK-adjacent signal, the 10 §3.3
  detector input)), the PII rules (the §8 masked-PII
  posture: the public data carries the refs + the masked
  fields, the wallet strings never (the 11 §10 rule),
  the KYC documents never (the 13 §10 rule), the
  accounting export is the tenant's own data (the
  hash-verifiable, the SDK-12 trust artifact)).
- **The two-secrets rule** (the §3.2): the API key auths
  the calls, the webhook secret signs the deliveries —
  the separate rotation (a leaked webhook secret doesn't
  expose the API, a leaked API key doesn't forge the
  webhooks), the reference verifier (the SDK-03, the
  timestamp tolerance, the raw-body HMAC, the replay
  window) is the security contract (the developer who
  implements verification wrong is the ecosystem's
  weakest link — the SDK-16 quickstart + the
  conformance suite (the §2 certification) test the
  verification (the check: the developer's endpoint
  rejects a forged signature (the harness sends the
  forged one, the certified integration must 401 it) —
  the certification is the security gate, not just the
  quality gate).
- **The always-manual payout rule** (the §3.1): the API
  channel never auto-approves (the 11 §3.5 posture
  extended: the machine's request is the human's
  decision — the labeled contract, the 202 response,
  the `pending_approval` status — the tenant's system
  integrates the queue, not the bypass).
- **The sandbox is the staging posture** (the 06 §2):
  the synthetic-only, the MetaApi demo, the injection
  sandbox-only (the 404 on live, the structural ban),
  the 30-day inactivity expiry (the staging hygiene),
  the reset (the synthetic wipe, the audited low tier) —
  the sandbox leak is a synthetic-data event (the 06
  incident posture: the "staging data exposed" class,
  not the "prod PII" class — the synthetic-only rule is
  what makes that true, the 25 §3.7 anonymization
  posture).
- **The deprecation is the durability contract** (the
  §3.5): the 12-month minimum, the `Deprecation` header,
  the 410 end-of-life, the changelog's public feed, the
  board-level exception for the shorter (the CON-32-
  class, the labeled exception) — the public API is the
  platform's most durable commitment (the tenant's
  business is built on it, the SDK-15 discipline is the
  platform's credibility).
- **The developer account** (the §3.3): the `firm:
  developer` role (the no-trader-data rule, the
  structural — the developer's portal views are the
  keys/usage/docs, the traders' data is via the API
  with the key's scopes), the delegation (the DVP-10,
  the one-level cap, the parent-revoke cascade, the
  audit's two-key trail), the support (the DVP-17, the
  SUP category, the key id in the ticket, never the key
  value — the support ticket with a full API key is
  the incident (the SUP-21-class content check, the
  18 §3.5 pattern: the ticket body scanned for the
  `sk_live_` pattern → the auto-flag + the key rotation
  prompt, the developer's key in their own ticket is
  the developer's error, the platform's response is
  the rotation, the audit, the no-silence)).
- **The partner directory & badge** (the DVP-13/14):
  the certification is the platform's endorsement
  (the conformance suite, the §2) — the badge is
  earned, re-earned (the SDK-release re-run, the
  §3.5 lapse rule), and revocable (a certified
  integration that's compromised (the partner's breach
  affecting the platform's data via their key) is
  unlisted + the key revoked (the CON-15-class
  incident, the 21 §3.2 control, the "partner key
  compromised" runbook entry: the delegation revoke
  (the parent cascade) + the partner notice + the
  directory update — the 30-min ops action)).
- **The accounting export & the books** (the SDK-12):
  the export is the read (the 05 §10 posture: the
  ledger is the system of record, the export is the
  copy, the hash-verifiable (the 05 §3.5 snapshot),
  the tenant's accountant verifies (the trust
  artifact) — the export never carries the other
  tenants' data (the tenant scope, the structural),
  the 7-yr availability (the LED retention, the
  05 §3.5).

## 11. Scalability considerations

- **The public API's load is the tenant's
  integration's load** (the V3 scale: the 25-50
  tenants, each with 1-10 integrations, each doing
  the read-heavy sync (the CRM's hourly pull, the
  accounting's daily export, the front-end's live
  reads)): the read path is the GW + the read models
  (the 19 §3.1 — the public reads hit the `*_ro`
  tables, the 19 §2 pattern, the source tables are
  never the public API's hot path), the rate limits
  (the SDK-14 per-key tier bounds the worst case:
  the 600/min × the 500 keys ≈ 5k req/s platform-
  wide ≈ the 00 §5 V2 peak (2k msg/s events + the
  reads) — the GW's V2 capacity (the 29 doc) covers
  it with headroom).
- **The webhook egress is the Hook0's
  problem** (the 04 §5.6: the per-endpoint limits,
  the retry, the DLQ, the single-relay → the
  egress-fan-out; the V3 scale (the 500 endpoints ×
  the 2k msg/s) = the Hook0's sized-for class, the
  04 §11 relay's egress section).
- **The GraphQL projection** (the DVP-11): the
  resolvers over the public reads (the read-model
  hits, the N+1 guard: the resolver's batch loading,
  the graphql-go's DataLoader pattern, the §1
  "no new data path" rule) — the GraphQL load is
  the REST load (same reads, same limits).
- **The SSE public** (the DVP-12): the 01 §4.3
  relay (the key-authed, the 10/key cap) — the V3
  concurrent streams ≈ the 5k (the 00 §5 class),
  the relay's horizontal scale (the 16 §11
  pattern).
- **The sandbox** (the staging tenant, the synthetic
  broker): the staging box's capacity (the 06 §1
  CX32, the synthetic-only load ≈ the 10% of prod) —
  the sandboxes are few (the V3: the 10-20 active
  sandboxes, the 30-day expiry bounds them, the
  06 staging sizing covers it).
- **The accounting export** (the SDK-12): the
  daily/monthly pull (the LED's range read, the
  05 §9 partitioned entries, the CSV stream — the
  10M-entry monthly export ≈ the minutes of SQL,
  the async (the export job, the ANA-11 pattern,
  the 19 §3.3: the report run → the R2 → the
  download URL, the 24-h TTL, the audited) — the
  export is never a synchronous big read (the
  API's 10-s cap, the 06 deploy-window class:
  a 5-minute export blocks nothing, the async is
  the design).
- **The cost that matters is the partner
  support** (the DVP-17, the SUP category) — the
  developer questions are the V3 support volume
  (the ~20/week at the 50-tenant scale) — the
  SUP-20 canned responses (the API troubleshooting
  set: the 401/403/429/webhook-signature/
  idempotency) + the status page (the DVP-07, the
  "is it down" deflection) + the changelog (the
  "did it change" deflection) — the three
  self-serve surfaces are the support-load
  controls (the 18 §3.4 posture).

## 12. Open-source solutions

| Option | Verdict |
|---|---|
| **The GW public subset + the OpenAPI contracts pack** (this design) | **CHOSEN** — the public API is the 04 gateway's declared subset (the one-contract rule, the §1 binding), the contracts pack (the README deliverable) is the spec source, the SDK/explorer/mock all generate from it — no separate API platform (the Kong-class, the forbidden list, the 01 ADR posture) |
| **Hook0** (the webhook egress, the register) | CHOSEN (the 04 §5.6, the signed delivery, the retry, the DLQ, the replay — the SDK-02/03/07 contract is the Hook0's delivery + the platform's spec) |
| **OpenAPI 3.1 + the buf/Ajv-class validation** (the contract tooling, the 04 §6 CI) | CHOSEN (the spec is the source, the CI gates: the public route without docs fails, the breaking change fails, the ULID-leak property test fails, the 04 §6 registry's CI extended) |
| **Scalar/Stoplight** (the API explorer embed, the DVP-04) | CHOSEN (the spec-generated explorer, the register-consistent OSS, the portal's embed) |
| **Prism** (the mock server, the DVP-18) | CHOSEN (the spec-generated mock, the `npx` local, the CI-friendly — the SDK-18 package wraps it) |
| **graphql-go** (the DVP-11) | CHOSEN (the read projection, the DataLoader batching, the §11 N+1 guard) |
| **Strapi/API-platform SaaS** (the managed-API alternatives) | Rejected (the data out of house, the 01 ADR posture, the 24 Part A §12 class — the public API is the platform's core surface, not an add-on) |
| **The SDK languages** (Go + TS first, the SDK-17) | CHOSEN (the tenant base's languages; the thin client, the generated models, the reference verifier, the idempotent retry — the 500-LOC-class per language, the SDK-16 quickstart) |
| **Uptime Kuma** (the DVP-07 status page, the register) | CHOSED (the public health + the incident feed, the 21 §3.2 posture, the CON-adjacent) |

## 13. Technology stack

The GW (the public subset, the 04 chain + the public
routes), the OpenAPI 3.1 (the contracts pack, the
source of truth), Hook0 (the egress), the AUTH-25
(the keys, the scopes, the two secrets), the read
models (the 19 substrate, the public reads), the
LED (the SDK-12 export, the 05 §3.5 hash), the
`web/dvp` (the portal, the 01 §2 web stack, the
monorepo's fifth app), Scalar (the explorer), Prism
(the mock), graphql-go (the DVP-11), the SSE relay
(the DVP-12, the 01 §4.3), the SUP (the DVP-17
category, the 18 pattern), the NOT (the DVP-16
alerts, the DVP-08 changelog feed, the delivery-
failed notices), the CON (the platform's
deprecation governance, the 21 §3.2), the ANA (the
developer usage read model, the 19 pattern), R2
(the exports, the 24-h TTL), Prometheus (the public
API's per-key metrics, the egress health, the
sandbox usage), Sentry (the portal + the SDK error
reporting, the developer opt-in, the PII rules,
the 16 §10 posture).

## 14. Integration — internal modules (glue)

| Module | How |
|---|---|
| **GW** | the public routes are the GW's declared subset (the 04 chain: the tenant resolution (the key → the tenant), the auth (the key), the scopes, the rate limits, the idempotency, the error contract, the ref indirection (the §8 middleware)) |
| **AUTH** | the keys (the 02 §3.5, the public extension: the environment, the scopes, the two secrets, the delegation), the `firm:developer` role (the §3.3), the developer account (the 02 membership) |
| **EVT/Hook0** | the webhook egress (the 04 §5.6, the SDK-02/03/07 contract), the public events (the 31-event-catalog's public subset), the delivery log (the DVP-05/07), the replay (the SDK-07) |
| **LED** | the SDK-12 accounting export (the 05 §9 entries, the §3.4 balances, the 05 §3.5 hash snapshot, the 7-yr) |
| **LCC/BRG/EVL** | the public account/trading reads (the 07/08/09 public subsets, the observed metrics, the positions/deals) |
| **PAY** | the public payout reads (the masked, the 11 §10) + the API payout request (the always-manual rule, the §3.1, the 11 §3.1 eligibility, the `api:{key_id}` source) |
| **CHK** | the checkout-session (the 12 §3.2, the login-first, the BYO-link-not-flow rule) |
| **KYC** | the public status (the 13 §7, the masked states) + the SDK-11 sync (the 13 §1 adapter's external input, the `external_accepted` config) |
| **TEN** | the tenant's public-API config (the `kyc.external_accepted`, the rate tier, the webhook topics allowed), the white-label portal (the TEN-14 domain, the §2) |
| **ANA** | the developer usage read model (the DVP-06, the 19 pattern), the public API's KPIs (the per-tenant integration health) |
| **SUP** | the DVP-17 (the `developer` category, the 18 §3.1, the key-in-ticket check, the §10) |
| **NOT** | the DVP-16 (the usage alerts), the DVP-08 (the changelog feed), the delivery-failed (the 04 §5.6), the delegation notices |
| **CON** | the deprecation governance (the §3.5, the 12-month rule, the board-level exception, the CON-32-class), the partner-incident control (the §10, the CON-15-class) |
| **AUD** | the key lifecycle (the critical on the revoke/delegate), the public API's sensitive calls (the `payouts:write` = the critical tier, the 05 §3.3 posture), the certification, the sandbox injection (the low) |
| **28 (security)** | the public perimeter (the 28 doc's threat model: the key compromise, the webhook forgery, the cross-tenant probe, the partner breach — the §10 stack is the 28 doc's D5 section) |

## 15. Integration — external tools

Hook0 (the egress), Scalar (the explorer), Prism (the
mock), graphql-go (the DVP-11), Uptime Kuma (the
DVP-07), the SDK publishing (the npm/Go module
registry, the SDK-18), the Postmark (via NOT, the
developer emails), the R2 (the exports), Prometheus/
Grafana (the public API metrics), Sentry (the
portal + the SDK).

## 16. Implementation blueprint (V3)

| Step | Owner | Est | Depends | Exit criteria |
|---|---|---|---|---|
| 1. The public-subset declaration + the ref indirection (the `public_id_refs`, the middleware, the serializer, the ULID-leak property test) + the public error codes (the 30 doc's public namespace) + the CI gates (the public route without docs fails, the breaking change fails) | BE-1 | 3 wks | the GW (the 04), the contracts pack (the README deliverable) | a public route returns only the refs (the property test green); a breaking OpenAPI change fails the CI (the test); the error contract is the 04 shape (the contract test) |
| 2. The keys' public extension (the environment, the scopes, the two secrets, the delegation, the IP allowlist) + the `firm:developer` role + the rate tiers (the SDK-14) + the key management (the portal's keys surface, the 2FA on the create/revoke) | BE-1 + FE-2 | 3 wks | 1, the AUTH-25 | a test key + a live key (the environment check, the 403 on the mismatch); a delegation (the sub-key's scopes ⊆, the parent-revoke cascade, the audit's two-key trail); the rate limit 429s with the headers (the test) |
| 3. The public read APIs (the accounts/payouts/payments/kyc/trading/accounting/crm, the §3.1 table) + the always-manual payout rule (the 202) + the SDK-12 export (the async, the hash-verifiable) + the SDK-13 sync | BE-1 | 4 wks | 1–2, the read models (the 19), the LED (the 05) | the FunderBlu agency's integration (the anchor): their CRM pulls the trader states (the SDK-13, the masked PII), their accounting pulls the monthly export (the SDK-12, the hash verified against the 05 snapshot), a payout request via the API lands in the manual queue (the 202, the `api:{key_id}` source in the audit) |
| 4. The webhook egress public (the Hook0's signed delivery, the SDK-02/03 contract, the reference verifier, the delivery log, the replay, the subscription config) + the DVP-05 simulator (the sandbox endpoint, the log, the one-click replay) | BE-1 | 3 wks | 2–3, the Hook0 (the 04 §5.6) | a developer's endpoint receives a signed event (the verifier passes, the forged signature 401s (the test)), the DLQ → the log (the red state), the replay re-delivers (the idempotency: the developer's dedupe on the Delivery-Id, the SDK-16 pattern) |
| 5. The sandbox (the staging tenant, the synthetic broker, the SDK-06 injection, the 30-day expiry, the reset) + the mock server (the Prism wrap, the SDK-18 package) + the conformance suite (the 50-check, the SDK-10) + the certification (the badge, the directory, the DVP-13/14) | BE-1 + FE-2 | 4 wks | 3–4, the 06 staging, the MetaApi demo | a developer's full loop: sign up (the portal) → the sandbox tenant (the auto-provisioned) → the keys + the webhook endpoint → the injection fires (the handler tested) → the conformance run (the 50 checks, the pass) → the badge (the directory, the DVP-13) — the FunderBlu agency certified (the reference) |
| 6. The portal (the `web/dvp`: the docs (generated), the explorer (the Scalar), the usage (the DVP-06), the status (the DVP-07, the Uptime Kuma feed), the changelog (the DVP-08, the subscription), the support (the DVP-17), the directory (the public)) + the GraphQL (the DVP-11, the read projection) + the SSE public (the DVP-12) | FE-2 + BE-1 | 4 wks | 3–5, the Uptime Kuma, the NOT | the portal's dry run: the FunderBlu agency manages their keys/webhooks/usage on the portal; the GraphQL projection returns the same data as the REST (the contract test); the SSE stream delivers the public events (the key-authed, the 10/key cap) |
| 7. The SDK core (the Go + TS, the generated models, the reference verifier, the idempotent retry, the SDK-16 quickstart, the SDK-17 matrix, the SDK-18 publishing) + the deprecation machinery (the `Deprecation` header, the 410, the 12-month clock, the changelog's deprecation section) + the BYO-KYC sync (the SDK-11, the `external_accepted` config) | BE-1 | 3 wks | 3–6, the contracts pack | the SDK's quickstart: the 5-minute path works (the install → the key → the first call → the webhook verified, the README's code); the deprecation: a test route deprecated (the header, the changelog, the 410 after the window (the time-travel test)); the SDK-11: an external KYC status sync (the `source: external`, the config gate) |
| 8. The V3-late: the low-code connectors (the DVP-09, the n8n-class, the register's consider-later — the n8n self-hosted or the partner-built, the decision at the V3 scope), the partner key delegation's multi-tenant (the DVP-10's cross-tenant partner, the CON-adjacent approval), the streaming's advanced (the DVP-12's backpressure, the 29 doc), the Python/PHP SDK (the SDK-17's community set) | BE-1 + FE-2 | 4 wks | 6–7 | the n8n connector (the decision: the self-hosted n8n on the platform box (the 01 ADR posture — the n8n is a workflow tool, the register-consistent) or the partner-built (the ecosystem choice) — the data path is the public API, the connector is the mapping) |

**Risks:** the contract rot (the public API drifting from
the spec — the one-contract rule, the CI gates, the
§16 step 1's property tests: the spec is the source,
the code is the test, the drift is a build failure,
the SDK-01 discipline); the key compromise (the
§10 stack: the two secrets, the rotation, the
delegation cascade, the IP allowlist, the rate
limits, the cross-tenant probe alert — the incident
runbook entry: "key compromised" = the revoke +
the delegation cascade + the partner notice + the
audit review, the 15-min ops action, the CON-15-
class); the webhook forgery (the developer's
mis-implementation — the §10's reference verifier
+ the conformance suite's forged-signature check
(the certification is the gate) + the docs'
troubleshooting (the DVP-17's canned response));
the partner breach (a certified integration's
compromise — the §10's partner-incident control,
the delegation revoke, the unlist, the directory
update, the 30-min action); the deprecation
pressure (a tenant demanding the breaking change
sooner — the 12-month rule, the board-level
exception, the labeled posture, the CON-32-class
approval — the platform's credibility is the 12-
month commitment, the SDK-15 discipline); the
sandbox abuse (a developer using the sandbox for
production-ish load — the 30-day expiry + the
staging capacity (the 06) + the synthetic-only
rule (the 06 §2) + the rate tier (the sandbox
keys are the test tier, the §3.1) — the sandbox is
the test environment, the capacity is sized for
it, the 06 staging box's budget line).

---

# Part B — TRD: Advanced Trading (8 reqs, V3)

## 1. Purpose & scope

The advanced-trading layer for the tenants' traders: the
copy-trading marketplace (TRD-01), the social trading feed
(TRD-02), the strategy marketplace (TRD-03), the backtesting
tools (TRD-04), the paper trading at scale (TRD-05), the
advanced order types (TRD-06), the trading API for
algorithmic (TRD-07), the advanced trading risk controls
(TRD-08).

**The boundary that keeps TRD honest:** the V1-V2 platform
is a **rule-enforcement + accounting platform over the
trader's own MT5 account** (the 08 §1 posture: the
platform is not an execution venue — the trading is the
broker's, the platform's hands are the enforcement
commands + the accounting). TRD is the V3 extension of
that posture, and every TRD feature must pass the
**execution-boundary test**: does this feature require
the platform to *place* trades, or only to *see,
score, connect, and account* them?

- **Pass (the TRD V3 set):** the copy-trading
  **feed** (the signal: a leader's trades are *observed*
  by the platform (the BRG read, the 08 §3.2 sync) and
  *mirrored by the follower's own execution* (the
  follower's MT5, via the follower's own terminal or
  the MetaApi's order API **on the follower's own
  account** (the execution is the follower's action,
  the platform's role is the signal + the mirror logic
  + the accounting — the follower can also use their
  own EA, the platform is the feed, the execution is
  the follower's choice, the labeled posture)), the
  social feed (the TRD-02: the public performance
  stats, the 24 Part B's public-profile pattern
  extended to the trading stats), the strategy
  marketplace (the TRD-03: the strategy = the signal
  definition (the MQL5 EA code or the platform's
  strategy spec), the tenant's curated marketplace,
  the platform hosts the listing + the subscription
  (the BIL-adjacent, the 22 class), the execution is
  the trader's), the backtesting (the TRD-04: the
  platform's historical data (the BRG's tick/deal
  history, the 08 §3.2) + the backtest engine (the
  research-grade, the V3 compute, the 29 doc's
  budget) — the backtest is the analysis, not the
  execution), the paper trading at scale (the TRD-05:
  the simulated accounts (the no-broker, the
  platform's own simulation (the synthetic fills,
  the research's paper-trading class) — the TRD-05
  is the only TRD feature with **no MT5 at all**
  (the simulation is the platform's, the labeled
  "paper" — the anti-design: a paper account that
  looks like a funded account (the trust breaker) —
  the TRD-05 accounts are visually distinct (the
  "PAPER" badge, the UI rule, the 16 §3.3 badge
  pattern extended), the terms say "simulation, no
  real money")), the advanced order types (the
  TRD-06: the **MetaApi's** advanced orders (the
  OCO, the trailing stop — the MT5-native via the
  MetaApi API, the execution is the broker's, the
  platform's role is the order placement *on the
  trader's behalf with the trader's explicit
  action* (the TD/SDK's order UI, the 2FA-class
  sensitive action, the audit) — the TRD-06 is the
  order *interface*, the execution is the
  broker's, the boundary holds)), the algo trading
  API (the TRD-07: the **public API's trading
  write** (the Part A's public API is read-only in
  V3-late — the TRD-07 is the exception surface:
  the `trading:write` scope (the strictest, the
  2FA-equivalent: the algo key's order placement is
  rate-limited + the risk-checked (the TRD-08) +
  the audited (the critical tier) — the TRD-07 is
  the "BYO algo" surface, the tenant's/developer's
  algo places orders on the trader's account via
  the key (the delegation pattern, the Part A §3.3,
  the one-level cap), the execution is the MetaApi's
  (the broker's), the platform's role is the gate +
  the audit + the accounting), the advanced risk
  controls (the TRD-08: the algo's guardrails (the
  per-key limits: the max position, the max daily
  loss, the order rate, the symbol allowlist — the
  config, the enforcement is the pre-order check
  (the reject before the MetaApi call), the
  breach = the key halt (the circuit breaker, the
  08 §3.3 pattern) + the trader notice + the RSK
  signal (the 10 §3.2 class)).

- **Fail (the banned set, the V3 boundary):** the
  platform as a **broker** (the platform holding the
  trader's money + executing against the LP — the
  A-book/b-b-b, the RSK-23/24, the 10 §1 "not a
  market maker" rule, the 28 doc's regulatory
  posture: the platform is the technology provider
  + the accounting system, the broker is the MT5
  firm (the tenant's broker relationship, the
  08 §1), the TRD never crosses into the
  execution-venue license territory), the
  **guaranteed-return** strategy (the marketplace
  strategy that promises the return — the banned
  listing, the TRD-03's curation rule: the strategy
  listing carries the performance history (the
  honest, the 24 Part B's integrity posture),
  never the guarantee, the ToS line, the FunderBlu
  legal's V3 sign-off), the **dark-pool** matching
  (the platform matching the traders against each
  other — the banned, the execution-venue
  territory, the 28 posture).

Requirement coverage: `TRD-01..08` (all V3; the
execution-boundary test is the design rule, the
§1).

## 2. Architecture

```
 the signal layer (the TRD-01/02/03 — the observe +
   connect, the no-platform-execution):
   · the leader (the trader with the "leader" opt-in
     (the TD's opt-in, the 2FA-class, the public
     performance (the 24 Part B's public profile +
     the verified mark, the masked PII rule, the
     19 §10 posture)): the platform *observes* the
     leader's trades (the BRG read, the 08 §3.2 —
     the leader's MT5 account is the platform's
     synced account, the signal is the observation)
   · the copy engine (the TRD-01): the follower
     subscribes (the allocation: the follower's
     capital % per leader trade, the risk config
     (the max position, the stop behavior — the
     follower's config, the 24 Part B's no-money-
     gating rule inverted: the follower *chooses*
     the risk, the platform enforces the follower's
     config + the TRD-08 guardrails), the mirror:
     the leader's fill (the BRG deal event) → the
     copy engine → the follower's order (the
     MetaApi order API, **on the follower's own
     MT5 account** (the execution is the follower's
     account, the broker's execution, the
     platform's role is the signal → the order
     (the follower's explicit consent at
     subscription, the ongoing, the cancel is the
     follower's right (the unsubscribe, the open
     positions: the follower's choice (the keep/
     close, the labeled decision, the UI rule)))
   · the copy accounting (the LED-adjacent): the
     copy trade is the follower's trade (the BRG
     deal, the 08 §3.2 sync, the EVL's observed,
     the 09 class — the copy is invisible to the
     EVL (it's the follower's trading, the rules
     apply as normal — the anti-design: a copy
     trade that bypasses the EVL (the trust
     breaker) — the copy is the follower's trading,
     the enforcement is normal, the RSK's conduct
     detectors (the 10 §3.3, the RSK-05/06) run on
     the copy trades (the copy-trading *is* the
     RSK-05 detector's input — the circularity:
     the copy engine creates the RSK-05 signal,
     the resolution: the copy is the *legitimate*
     RSK-05 (the labeled: the platform's own copy
     engine is allowlisted from the RSK-05 DQ
     (the config: the `copy_engine: platform`
     flag on the deal (the BRG's deal metadata,
     the 08 §3.2) — the RSK-05 fires on the
     *trader-initiated* copy (the EA-based, the
     leader's own mirror), not the platform's
     copy engine (the labeled distinction, the
     24 Part B's conduct-rule posture))
   · the social feed (the TRD-02): the public
     performance (the stats, the 24 Part B's
     pattern, the 19 read model), the feed (the
     "top leaders" board (the 24 Part B's
     leaderboard pattern, the computed + the
     as_of-labeled, the integrity rule)), the
     subscription (the copy, the TRD-01)
   · the strategy marketplace (the TRD-03): the
     listing (the strategy = the MQL5 EA (the
     code, the R2, the tenant-curated (the
     tenant's curation, the 24 Part A's content
     posture) or the platform's spec (the
     declarative, the signal definition)), the
     subscription (the BIL-adjacent, the 22
     class, the tenant's revenue share), the
     execution (the trader's own (the EA on their
     MT5, the platform's role is the hosting +
     the curation + the accounting, the no-
     guarantee rule, the §1))
 the analysis layer (the TRD-04/05 — the no-live-
   execution):
   · the backtesting (the TRD-04): the historical
     data (the BRG's tick/deal history, the 08
     §3.2, the 13-mo retention (the 04 §5.4) —
     the backtest's data window is the retention,
     the labeled), the engine (the V3 compute,
     the 29 doc's budget: the backtest worker
     (the Go/Rust, the research-grade, the
     event-driven (the tick replay, the 09
     engine's pure-function posture — the
     backtest is the EVL-class engine over the
     historical ticks, the re-runnable, the
     09 §3.4 discipline)), the results (the
     stats, the equity curve, the drawdown —
     the ANA-class read, the tenant/trader-
     scoped), the strategy (the TRD-03's spec,
     the backtest-verified listing (the
     marketplace's "backtested" mark (the
     honest: the backtest result, the period,
     the data source — the 24 Part B's
     integrity posture, the no-survivorship-
     bias disclaimer (the UI rule: the
     backtest's limitations stated, the research
     honesty)))
   · the paper trading at scale (the TRD-05): the
     simulation (the no-broker, the platform's
     own (the synthetic fills (the tick-driven,
     the slippage model (the config, the
     research's paper-trading class), the
     funding (the virtual, the 0 LED (the paper
     account has no real money, the accounting
     is the simulation's (the separate
     `paper_*` tables, the 05 §1 posture: the
     paper is not the ledger (the labeled
     distinction, the "PAPER" badge, the
     visually-distinct rule, the §1))), the
     scale (the "at scale": the tenant runs a
     100-trader paper contest (the 24 Part B's
     competition pattern on the paper accounts —
     the CMP-01's paper variant, the no-broker-
     cost (the MetaApi cost is the 08 §1 cost
     driver, the paper is the zero-cost
     contest, the BIL-adjacent)), the V3-late
     (the TRD-05 is the V3-late within the V3,
     the after the copy engine (the dependency:
     the paper uses the same signal/mirror
     machinery, the simulation is the broker's
     stand-in)))
 the execution layer (the TRD-06/07/08 — the
   gated, the audited, the broker-executed):
   · the advanced order types (the TRD-06): the
     MetaApi's advanced orders (the OCO, the
     trailing, the 08 §1's MetaApi capability —
     the Capabilities() (the 08 §1 binding: the
     connector's capability set, the advanced
     orders are the MetaApi's (the MT5-native),
     the platform's role is the order UI (the
     TD's order panel (the V3 TD extension) +
     the SDK's order API (the Part A's public
     API's `trading:write`)), the placement is
     the trader's explicit action (the 2FA-
     class, the sensitive action, the 16 §3.5
     pattern, the audit), the execution is the
     MetaApi's (the broker's), the fill is the
     BRG's deal (the 08 §3.2), the EVL's
     observed (the 09) — the boundary holds:
     the platform *interfaces* the order, the
     broker *executes* it
   · the algo trading API (the TRD-07): the
     public API's trading write (the Part A's
     read-only extended, the `trading:write`
     scope (the strictest), the key (the
     delegation pattern, the Part A §3.3, the
     one-level cap, the tenant's/developer's
     algo), the order placement (the MetaApi's,
     the broker's execution), the pre-order gate
     (the TRD-08's check, the §2), the audit
     (the critical tier, the 05 §3.3 posture),
     the rate limit (the order rate, the
     TRD-08 config), the halt (the circuit
     breaker, the 08 §3.3 pattern, the key
     halt on the breach)
   · the advanced risk controls (the TRD-08):
     the guardrails (the per-key/per-follower
     config: the max position, the max daily
     loss, the order rate, the symbol
     allowlist, the max leverage (the MT5's,
     the broker's limit, the platform's check
     is the pre-order, the reject before the
     MetaApi call), the enforcement (the
     pre-order check (the synchronous, the
     07 §3.2's single-path posture — the
     TRD-08 check is the order path's gate,
     the 08 §3.3's executor's pre-check
     extended), the breach (the key/follower
     halt (the circuit), the open positions
     (the follower's choice (the keep/close,
     the labeled, the UI)), the trader notice
     (the NOT template), the RSK signal (the
     10 §3.2, the `algo_breach` kind (the RSK-
     07 ingestion)), the audit (the critical
     tier))
```

## 3. System design

### 3.1 The copy engine (the TRD-01 — the signal → the mirror)

```
the leader: the opt-in (the TD, the 2FA-class,
  the public performance (the 24 Part B's
  pattern), the terms (the "leader" agreement
  (the disclosure: the leader's trades are
  visible to the followers, the performance is
  public, the no-guarantee, the tenant's
  curation (the leader listing is the tenant-
  approved (the 24 Part A's content posture,
  the curation queue, the ADM-adjacent))),
  the signal (the BRG deal event, the 08 §3.2,
  the platform-observed (the leader's account
  is the platform's synced account, the
  observation is normal, the 08 posture))
the follower: the subscription (the config:
  the allocation (the % or the fixed, the
  follower's capital, the risk config (the max
  position, the stop (the mirror the leader's
  stop? the follower's choice (the config:
  `mirror_stop: true|false` — the labeled
  choice, the default: the mirror (the
  research's copy-trading default, the
  honesty: the follower who doesn't mirror
  the stop is the follower's risk, the UI
  says so))), the consent (the ongoing, the
  cancel (the unsubscribe, the open positions
  (the keep/close, the labeled decision, the
  UI rule, the 2FA-class on the close (the
  money action, the 16 §3.5 pattern))),
  the mirror (the copy engine's worker (the
  advisory-lock, the 06 pattern), the
  signal → the order (the MetaApi order, the
  follower's account, the slippage tolerance
  (the config: the max slippage (the bps, the
  the order is the limit at the leader's
  price ± the slippage (the no-market-order
  default (the slippage control, the research
  posture) — the unfilled (the slippage
  exceeded) = the skipped (the follower
  notice, the audit, the no-partial (the
  labeled: the all-or-nothing per trade, the
  research's copy-trading integrity rule —
  a partial copy is the position mismatch,
  the trust breaker, the all-or-nothing is
  the design)), the latency (the signal →
  the order's latency (the measured, the
  ANA-class metric, the "copy latency p95"
  (the public stat (the honest: the followers
  see the latency (the 24 Part B's as_of
  posture, the ANA-14 rule))), the failure
  (the MetaApi down (the 08 §3.3's provider
  health) = the copy paused (the follower
  notice, the signal queued (the bounded
  queue (the 60-s window (the stale signal
  (the > 60 s = the skipped (the labeled,
  the no-late-copy (the research posture:
  a 5-minute-late copy is a different
  trade, the integrity rule), the audit))
the copy accounting: the copy deal is the
  follower's deal (the BRG sync, the 08
  §3.2, the `copy_engine: platform` flag
  (the deal metadata, the §1's RSK-05
  allowlist), the EVL's observed (the 09,
  the normal enforcement), the LED (the
  follower's trading, the normal (the copy
  has no special ledger entry (the it's the
  follower's trade, the 05 §1 posture)),
  the RSK (the RSK-05/06 (the copy is the
  allowlisted, the §1's labeled
  distinction), the RSK-08 (the leader-
  follower cluster (the device/IP (the
  follower who copies 5 leaders on the same
  device (the RSK-04 input, the 10 §3.3))
the copy economics (the tenant's revenue):
  the subscription (the BIL-adjacent, the 22
  class: the tenant's copy fee (the
  % of the copied PnL or the flat, the
  tenant config, the BIL-17 pass-through
  class (the MetaApi cost of the follower's
  account, the 08 §1), the 22 §3.2 plan
  shape), the ledger (the tenant's revenue,
  the 05 class, the normal), the disclosure
  (the follower's terms (the fee, the
  labeled, the 24 Part A's legal-block
  pattern))
```

### 3.2 The backtesting (the TRD-04)

```
the data: the BRG's historical (the tick
  (the 08 §3.2's `bridge.tick` (the 13-mo
  retention, the 04 §5.4) + the deal history
  (the 08's monthly partitions, the 09 §9
  class)), the labeled window (the backtest's
  data range (the UI: "data: 2026-01 to
  2026-09 (13-mo platform retention)" (the
  honest, the ANA-14 posture), the
  survivorship (the accounts that breached
  are in the data (the no-survivorship-
  bias (the 24 Part B's integrity posture,
  the research honesty: the backtest's
  limitation stated in the results (the UI
  rule))))
the engine: the tick replay (the event-
  driven, the 09 engine's pure function
  (the `evaluate(state, rules, tick)`
  (the 09 §1's ADR-11, the Rust service,
  the backtest is the engine over the
  historical ticks (the re-runnable, the
  09 §3.4's recompute property, the input_
  hash (the 09 §3.2) — the backtest is the
  09 engine's second user (the EVL is the
  live evaluator, the backtest is the
  historical, the same function, the
  29 doc's compute budget: the backtest
  worker (the separate slot, the off-peak
  (the 06 §3.3's advisory-lock class),
  the V3 scale (the 100-trader paper
  contest's backtest (the batch, the
  research's compute class))))
the strategy: the TRD-03's spec (the
  declarative (the signal definition (the
  entry/exit rules, the risk params) or
  the MQL5 EA (the code, the R2, the
  tenant-curated) — the backtest runs the
  spec (the platform's spec: the engine
  native, the MQL5 EA: the backtest is the
  MT5's (the MetaApi's backtest API (the
  broker's backtest (the 08's capability
  (the Capabilities() (the 08 §1) — the
  MQL5 backtest is the broker's engine,
  the platform's role is the orchestration
  + the results, the labeled: the
  "backtested on MT5" vs "backtested on
  platform engine" (the two engines, the
  honest label, the 24 Part B's
  integrity posture))), the results (the
  stats (the net PnL, the max DD, the
  win rate, the profit factor, the
  Sharpe (the research's standard set),
  the equity curve (the ANA-class read,
  the 19 pattern), the per-trade (the
  deal list, the audit-able), the
  comparison (the strategy A vs B, the
  tenant's curation tool (the ADM-
  adjacent, the V3-late)))
the marketplace integration (the TRD-03):
  the "backtested" mark (the result, the
  period, the data source, the engine (the
  §3.2's label), the no-guarantee
  (the §1's banned set, the ToS line),
  the curation (the tenant's queue (the
  ADM, the 17 §3.1 pattern), the
  approval (the 2FA-class, the content
  posture, the 24 Part A §3.4's legal-
  review pattern))
```

### 3.3 The paper trading (the TRD-05)

```
the simulation: the no-broker (the
  platform's own (the synthetic fills (the
  tick-driven (the 08's `bridge.tick`
  (the live ticks, the 13-mo history)),
  the slippage model (the config (the bps,
  the research's paper-trading class),
  the funding (the virtual (the 0 real
  money (the `paper_accounts` (the
  separate tables (the 05 §1 posture:
  the paper is not the ledger (the
  labeled, the "PAPER" badge (the 16
  §3.3's badge pattern, the visually-
  distinct (the UI rule, the §1's
  anti-design), the terms (the
  "simulation, no real money" (the
  CMS-08's legal block, the ToS line)),
  the scale (the tenant's 100-trader
  paper contest (the 24 Part B's
  competition pattern (the CMP-01's
  paper variant (the no-broker-cost (the
  08 §1's MetaApi cost is the driver,
  the paper is the zero-cost contest,
  the BIL-adjacent (the 22 class, the
  tenant's contest revenue (the entry
  fee (the real money (the CHK's normal
  flow (the 12 §3.2), the prize (the
  24 Part B's prize pattern (the PAY-
  class, the 22 §3.4))))
  the contest's scoring (the 24 Part B's
  scoring engine (the pure, the versioned,
  the re-runnable, the 09 §3.4
  discipline), the paper equity (the
  simulation's, the observed-class (the
  09 §3.4's observed-vs-evaluated, the
  paper is the observed-only (the no-
  enforcement (the paper account has no
  EVL (the rules are the contest's
  scoring, the 24 Part B's class))))
the V3-late: the TRD-05 is the after the
  copy engine (the §16's step order, the
  dependency: the paper uses the signal/
  mirror machinery (the 08's sync, the
  09's engine), the simulation is the
  broker's stand-in (the 29 doc's V3
  compute line)
```

### 3.4 The advanced orders + the algo API + the risk
controls (the TRD-06/07/08)

```
the order path (the single, the 07 §3.2's
  posture extended):
  the trader's UI (the TD's order panel (the
    V3 TD extension, the 16 §3.1's screen
    set extended) / the SDK's order API (the
    Part A's public API's `trading:write`
    (the TRD-07))
    → the TRD-08 pre-check (the synchronous,
      the guardrails (the §2's config),
      the reject before the MetaApi (the
      08 §3.3's executor's pre-check
      extended, the 07 §3.2's single
      path: the order path is the one
      path, the TRD-08 is its gate))
    → the MetaApi order (the 08's
      connector, the Capabilities() (the
      advanced orders (the OCO, the
      trailing (the 08 §1's MT5-native)),
      the broker's execution, the fill =
      the BRG's deal (the 08 §3.2), the
      EVL's observed (the 09), the LED's
      normal (the 05))
  the audit (the critical tier (the order
    placement (the 05 §3.3's sensitive-
    action class, the 16 §3.5's Sensitive-
    Dialog pattern (the 2FA on the
    trader's UI (the money action), the
    algo's key (the key's scope is the
    2FA-equivalent (the delegation + the
    guardrails + the halt (the §2))
  the halt (the circuit (the 08 §3.3's
    pattern, the per-key/per-follower),
    the breach → the halt (the open
    positions (the follower's/trader's
    choice (the keep/close, the labeled,
    the UI)), the notice (the NOT), the
    RSK signal (the 10 §3.2, the
    `algo_breach`), the audit (the
    critical))
```

## 4. Events (topic `trading` + the copy/backtest/paper)

| Event | When | Consumers |
|---|---|---|
| `trading.order_placed` (the TRD-06/07) | the order (the MetaApi call) | the BRG (the 08's sync), the AUD (the critical), the ANA (the order latency) |
| `trading.order_filled` | the fill (the BRG's deal) | the EVL (the 09's observed), the LED (the 05's normal), the copy engine (the TRD-01's signal), the AUD (the low) |
| `trading.order_rejected_trd08` (the TRD-08) | the guardrail reject | the AUD (the low), the ANA (the reject rate), the NOT (the trader notice (the reason, the 04 error contract's public-safe class)) |
| `copy.subscription_created/cancelled` (the TRD-01) | the follower's consent | the AUD (the critical (the money-adjacent consent), the NOT (the confirmation), the ANA (the copy stats) |
| `copy.trade_mirrored` (the TRD-01) | the mirror (the follower's order) | the BRG, the AUD (the low), the ANA (the copy latency, the slippage) |
| `copy.skipped` (the TRD-01) | the slippage/latency skip | the NOT (the follower notice), the AUD (the low), the ANA (the skip rate (the health metric)) |
| `backtest.completed` (the TRD-04) | the result | the tenant's curation (the ADM), the AUD (the low), the ANA (the backtest stats) |
| `paper.account_created/traded` (the TRD-05) | the simulation | the ANA (the paper stats), the AUD (the low (the no-real-money (the tier is the low, the labeled))) |
| `trading.key_halted` (the TRD-08) | the circuit | the NOT (the trader/developer notice), the RSK (the signal), the AUD (the critical), the CON (the ops alert (the key-halt rate (the health))) |

## 5. Lifecycles

- **Leader:** `opted_in (the 2FA, the terms) → listed (the tenant-curation, the 24 Part A pattern) → active (the signal flowing) → (the tenant's delist (the curation, the 2FA) / the leader's opt-out (the followers' open positions (the keep/close, the labeled))) → delisted` (the public performance history retained (the 24 Part B's integrity, the as_of-labeled, the no-quiet-removal (the delisted leader's history shows "delisted", the 24 Part B's DQ-public posture))).
- **Copy subscription:** `created (the consent, the config) → active (the mirror running) → (the leader delisted / the follower cancel / the TRD-08 halt) → closed (the open positions (the keep/close, the labeled decision, the 2FA on the close, the UI rule))` (the subscription's PnL (the tenant's fee basis, the 05 class, the labeled)).
- **Backtest run:** `queued (the 29 doc's compute slot) → running (the tick replay, the off-peak) → completed (the result, the re-runnable (the 09 §3.4, the input hash)) | failed (the compute error, the retry, the ANA-class metric)` (the run is the audit-able (the strategy version, the data window, the engine (the §3.2's label), the result hash (the recompute property, the 09 §3.4))).
- **Paper account:** `created (the virtual funding, the no-real-money) → active (the simulation's trading, the tick-driven) → (the contest end / the 30-day inactivity) → archived (the results retained (the 24 Part B's class), the virtual balance deleted (the no-real-money (the labeled, the audit))` (the paper account is visually distinct (the "PAPER" badge, the §1's anti-design, the UI rule, the property test: a paper account's UI never renders the funded-badge, the 16 §3.3's badge pattern's negative test)).
- **Advanced order (the TRD-06):** the MT5's order lifecycle (the broker's, the 08 §3.2's sync: the `order_placed → order_filled|order_canceled|order_expired` (the BRG's state, the EVL's observed, the normal)).
- **Algo key (the TRD-07):** the Part A's key lifecycle (the `trading:write` scope, the delegation, the rotation, the revoke) + the halt state (the TRD-08's circuit: the `active → halted (the breach) → (the tenant's/developer's re-enable (the 2FA-class, the review (the ADM-adjacent, the CON-adjacent for the platform keys)) → active` (the halt is the audit-critical, the 05 §3.3)).
- **The TRD-08 guardrail config:** the versioned (the per-key/per-follower, the 03 §3.1's config pattern, the change = the 2FA-class (the risk config, the sensitive), the audit, the "what was the guardrail when the halt fired" answerable (the config version on the halt event, the 24 Part B's evidence posture)).

## 6. Error taxonomy (the public-safe + the internal)

| Code | HTTP | Meaning |
|---|---|---|
| `trd.leader_not_listed` | 404 | The copy subscription on a delisted/unlisted leader (the 04 posture) |
| `trd.copy_inactive` | 409 | The mirror attempt on a closed subscription (the state machine) |
| `trd.slippage_exceeded` | 422 (the internal → the `copy.skipped`) | The skip (the labeled, the §3.1's all-or-nothing) |
| `trd.signal_stale` | 422 (the internal → the skip) | The > 60 s (the §3.1's no-late-copy, the integrity rule) |
| `trd.order_capability_missing` | 422 | The advanced order the MetaApi doesn't support (the Capabilities() (the 08 §1, the honest: the order type is the broker's capability, the platform's error is the capability gap, the labeled)) |
| `trd.trd08_limit` | 422 (the public-safe: the reason class, the 04 contract) | The guardrail reject (the max position, the daily loss, the rate, the symbol — the `details.checks[]` (the PAY-03 pattern, the 11 §3.1), the actionable) |
| `trd.key_halted` | 403 | The order on a halted key (the re-enable path, the §5) |
| `trd.backtest_data_gap` | 422 | The window exceeds the retention (the 13-mo, the labeled, the ANA-14 posture) |
| `trd.backtest_running` | 409 | The duplicate (the run id returned, the 19 §6 pattern) |
| `trd.paper_funded_attempt` | 403 | The real-money action on a paper account (the structural ban, the 04 posture — the paper account's id space is separate (the `paper_` prefix (the internal, the §3.3), the real-money route 403s on the paper id, the anti-design's code-level enforcement) |
| `trd.strategy_not_certified` | 422 (the marketplace) | The listing without the backtest (the §3.2's mark, the curation gate) |
| `trd.copy_circuit_open` | 503 | The copy engine's pause (the MetaApi down (the 08 §3.3), the `retry_after`, the 04 §6 pattern) |

## 7. API endpoints
> **Scope note:** SDK/DVP/TRD/PLT/CS is not in the V1 execution sheet (V2/V3 scope; API keys themselves are V2 per AUTH-21). There is no V1 baseline contract for this module; the surface below is design-level (post-V1, docs/99) and provisional until its phase's contract freeze.


Trader (the TD's V3 extension):
`GET /v1/trading/leaders` (the social feed, the TRD-02: the public performance, the as_of-labeled),
`GET /v1/trading/leaders/{id}` (the performance, the subscription CTA),
`POST /v1/trading/copy/subscriptions` (the TRD-01: the config, the consent, the 2FA-class),
`GET /v1/trading/copy/subscriptions` (the own, the PnL, the latency stats),
`DELETE /v1/trading/copy/subscriptions/{id}` (the cancel, the open positions (the keep/close, the 2FA on the close)),
`POST /v1/trading/orders` (the TRD-06: the advanced order (the OCO, the trailing), the 2FA, the sensitive action),
`GET /v1/trading/paper/accounts` (the TRD-05, the "PAPER" badged),
`POST /v1/trading/paper/accounts` (the create, the virtual funding, the no-real-money),
`GET /v1/trading/backtests` (the TRD-04, the runs, the results).

Staff (the ADM's V3 extension, the tenant's curation):
`GET /v1/admin/trading/leaders` (the curation queue, the 24 Part A pattern),
`POST /v1/admin/trading/leaders/{id}/delist` (the 2FA, the followers' notice),
`GET /v1/admin/trading/strategies` (the marketplace curation),
`POST /v1/admin/trading/strategies/{id}/approve` (the 2FA, the backtest-verified gate),
`GET /v1/admin/trading/copy/stats` (the tenant's copy health: the latency, the slippage, the skip rate, the PnL),
`GET /v1/admin/trading/algo/keys` (the TRD-07/08: the keys, the guardrails, the halt state),
`POST /v1/admin/trading/algo/keys/{id}/guardrails` (the 2FA, the versioned config),
`POST /v1/admin/trading/algo/keys/{id}/re-enable` (the 2FA, the review).

Public (the SDK, the Part A's public API extended):
`GET /v1/public/trading/leaders` (the social feed, the masked PII, the ref indirection, the Part A §8),
`POST /v1/public/trading/orders` (the TRD-07: the algo's order, the `trading:write` scope, the TRD-08 pre-check, the critical audit),
`GET /v1/public/trading/backtests/{id}` (the TRD-04's result, the tenant-scoped).

## 8. Schema (key shapes)

```jsonc
// the social feed (the TRD-02, the public)
{ "data": { "as_of": 1758282000000, "leaders": [
    { "ref": "id_01J9…", "display_name": "ali_k",
      "win_rate_90d": 0.62, "pnl_90d_cents": 4820000,
      "max_dd_90d_bps": 840, "followers": 42,
      "copy_latency_p95_ms": 320, "status": "active" } ] } }

// the copy subscription (the TRD-01)
{ "data": { "id": "01J9CPY…", "leader_ref": "id_01J9…",
    "allocation": { "mode": "pct", "pct_bps": 1000 },
    "risk": { "max_position_cents": 500000, "mirror_stop": true },
    "state": "active", "pnl_cents": 124000,
    "copy_latency_p95_ms": 310, "trades_mirrored": 84,
    "trades_skipped": 3 } }

// the TRD-08 guardrail reject (the public-safe, the 04 contract)
{ "error": { "code": "TRD_TRD08_LIMIT",
    "message": "Order rejected: position limit reached.",
    "details": { "checks": [
      { "check": "max_position", "state": "fail",
        "limit_cents": 500000, "would_be_cents": 520000 } ] } } }

// the backtest result (the TRD-04)
{ "data": { "id": "01J9BKT…", "strategy_ref": "str_01J9…",
    "engine": "platform", "window": { "from": "2026-01", "to": "2026-09" },
    "data_source": "platform_ticks (13-mo retention)",
    "result": { "net_pnl_cents": 2840000, "max_dd_bps": 620,
                "win_rate": 0.58, "profit_factor": 1.9,
                "sharpe": 2.1 }, "result_hash": "sha256:…",
    "recompute": "match", "disclaimer": "Backtest on historical platform data; not a guarantee of future performance." } }
```

## 9. Database design

```sql
CREATE TABLE trading_leaders (                -- the TRD-01/02
  id          ULID PRIMARY KEY,
  tenant_id   ULID NOT NULL,
  identity_id ULID NOT NULL,                  -- the leader (the opt-in,
  account_id  ULID NOT NULL,                  --   the 2FA, the terms)
  display_name TEXT,                          -- the 24 Part B's handle
  status      TEXT NOT NULL DEFAULT 'opted_in'
    CHECK (status IN ('opted_in','listed','delisted')),
  delisted_at TIMESTAMPTZ, delisted_reason TEXT,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, identity_id)
);
CREATE TABLE copy_subscriptions (             -- the TRD-01
  id          ULID PRIMARY KEY,
  tenant_id   ULID NOT NULL,
  leader_id   ULID NOT NULL REFERENCES trading_leaders(id),
  identity_id ULID NOT NULL,                  -- the follower
  account_id  ULID NOT NULL,                  -- the follower's MT5
  allocation  JSONB NOT NULL,                 -- the §3.1 config
  risk_config JSONB NOT NULL,                 -- the guardrails (the
  config_version INT NOT NULL DEFAULT 1,      --   TRD-08's versioned)
  state       TEXT NOT NULL DEFAULT 'active'
    CHECK (state IN ('active','closed','halted')),
  closed_at   TIMESTAMPTZ, close_reason TEXT,
  pnl_cents   BIGINT NOT NULL DEFAULT 0,
  trades_mirrored INT NOT NULL DEFAULT 0,
  trades_skipped INT NOT NULL DEFAULT 0,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_copsub_follower ON copy_subscriptions(tenant_id, identity_id, state);
CREATE TABLE copy_trades (                    -- the mirror log (the
  id          ULID PRIMARY KEY,               --   audit, the ANA)
  tenant_id   ULID NOT NULL,
  subscription_id ULID NOT NULL,
  leader_deal_id TEXT NOT NULL,               -- the signal (the BRG ref)
  follower_deal_id TEXT,                      -- the mirror (the NULL on
  state       TEXT NOT NULL,                  --   the skip)
  CHECK (state IN ('mirrored','skipped')),
  skip_reason TEXT,                           -- slippage|stale|circuit
  signal_at   TIMESTAMPTZ NOT NULL,
  mirror_at   TIMESTAMPTZ,
  latency_ms  INT,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_copytrades_sub ON copy_trades(subscription_id, created_at DESC);
CREATE TABLE backtest_runs (                  -- the TRD-04
  id          ULID PRIMARY KEY,
  tenant_id   ULID NOT NULL,
  identity_id ULID,                           -- the trader's (the NULL
  strategy_ref TEXT NOT NULL,                 --   for the tenant's)
  engine      TEXT NOT NULL,                  -- 'platform'|'mt5' (the
  window_from DATE NOT NULL, window_to DATE NOT NULL,
  state       TEXT NOT NULL DEFAULT 'queued'
    CHECK (state IN ('queued','running','completed','failed')),
  result      JSONB,                          -- the §8 shape
  result_hash TEXT,                           -- the recompute (the 09
  error       TEXT,                           --   §3.4)
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  completed_at TIMESTAMPTZ
);
CREATE INDEX idx_bktrun_tenant ON backtest_runs(tenant_id, created_at DESC);
CREATE TABLE paper_accounts (                 -- the TRD-05 (the
  id          ULID PRIMARY KEY,               --   no-real-money, the
  tenant_id   ULID NOT NULL,                  --   separate tables, the
  identity_id ULID NOT NULL,                  --   05 §1 posture)
  contest_id  ULID,                           -- the 24 Part B's comp
  virtual_balance_cents BIGINT NOT NULL,      -- the 0 LED (the labeled)
  state       TEXT NOT NULL DEFAULT 'active'
    CHECK (state IN ('active','archived')),
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  archived_at TIMESTAMPTZ
);
CREATE INDEX idx_paper_trader ON paper_accounts(tenant_id, identity_id, state);
-- the paper deals: the `paper_deals` (the simulation's, the tick-
--   driven, the no-BRG (the no-broker, the §3.3) — the separate
--   table, the 13-mo retention (the 04 §5.4 class), the "PAPER"
--   badge's data source (the UI's negative test, the §5)
-- the advanced orders: the BRG's `orders` table (the 08 §9, the
--   MetaApi's order state, the Capabilities() (the 08 §1) — the
--   TRD-06 adds no table (the order is the BRG's, the 08's
--   sync, the EVL's observed, the normal)
-- the algo keys: the Part A's `api_keys` (the `trading:write`
--   scope, the delegation) + the TRD-08's guardrail config (the
--   `algo_guardrails` (the per-key, the versioned, the §5)):
CREATE TABLE algo_guardrails (
  id          ULID PRIMARY KEY,
  tenant_id   ULID NOT NULL,
  key_id      ULID,                           -- the algo key (the NULL
  follower_id ULID,                           --   for the copy's
  max_position_cents BIGINT,                  --   subscription (the
  max_daily_loss_cents BIGINT,                --   risk_config, the
  order_rate_per_min INT,                     --   §3.1)
  symbol_allowlist TEXT[],
  version     INT NOT NULL DEFAULT 1,
  active      BOOLEAN NOT NULL DEFAULT true,
  created_by  ULID, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, key_id, version)
);
-- the halt state: the `algo_halts` (the key/follower, the breach
--   ref, the config version, the re-enable (the 2FA, the review) —
--   the 08 §3.3's circuit pattern, the 24 Part B's evidence
--   posture)
```

## 10. Security & compliance

- **The execution boundary is the compliance line**
  (the §1's test): the platform *observes,
  scores, connects, accounts, and interfaces* —
  the *execution is the broker's* (the MT5
  firm, the tenant's relationship, the 08 §1)
  and the *trader's* (the follower's account,
  the follower's consent, the trader's explicit
  order). The platform never holds the trader's
  money (the 05 §1: the ledger is the
  accounting, the cash is the tenant's broker
  balance, the platform's books are the
  obligation), never matches the traders
  against each other (the banned, the
  28 doc's regulatory posture), never
  guarantees the return (the banned, the
  §1, the ToS line, the FunderBlu legal's
  V3 sign-off). The TRD-08's pre-order gate
  is the *trader's protection* (the
  guardrails are the trader's/tenant's
  config, the platform enforces the
  trader's own limits — the posture: the
  platform is the safety device, not the
  gatekeeper of the broker's discretion).
- **The copy is the follower's trading**
  (the §3.1): the copy deal is the
  follower's deal (the BRG's sync, the
  08 §3.2, the `copy_engine: platform`
  flag, the EVL's normal enforcement,
  the 09), the RSK-05 allowlist (the
  §1's labeled distinction: the platform's
  copy engine is the legitimate copy,
  the trader-initiated EA-copy is the
  RSK-05 input — the config is the
  detector's input, the 10 §3.3's
  detector manifest), the follower's
  consent (the ongoing, the 2FA-class on
  the subscribe + the close, the
  labeled decision on the open
  positions (the keep/close, the UI
  rule, the anti-design: a silent
  auto-close of the follower's
  positions (the trust breaker) — the
  close is the follower's action,
  always).
- **The paper is the no-real-money**
  (the §3.3): the separate tables (the
  05 §1 posture: the paper is not the
  ledger, the labeled), the "PAPER"
  badge (the 16 §3.3's pattern, the
  visually-distinct, the property
  test: the paper UI never renders
  the funded-badge, the §5's negative
  test), the no-real-money route (the
  `trd.paper_funded_attempt` 403, the
  code-level enforcement, the §6),
  the virtual balance deleted on
  archive (the audit, the labeled),
  the terms (the "simulation, no real
  money", the CMS-08's legal block,
  the ToS line) — the anti-design:
  the paper account that looks like
  the funded (the regulatory + the
  trust, the 28 posture).
- **The algo API is the strictest
  surface** (the TRD-07): the
  `trading:write` scope (the Part A's
  strictest, the §3.1's always-manual
  posture adapted: the algo's order is
  the machine's action, the human's
  equivalent is the guardrails + the
  halt (the TRD-08, the §3.4) + the
  delegation (the Part A §3.3, the
  one-level cap, the parent-revoke
  cascade) + the audit (the critical
  tier, the 05 §3.3) + the rate limit
  (the order rate, the TRD-08 config)
  — the "the machine's trading waits
  for the human's limits" (the
  §3.1's always-manual rule, the
  TRD-08's form), the key compromise
  (the Part A §10's stack: the two
  secrets, the rotation, the IP
  allowlist, the cross-tenant probe
  alert, the CON-15-class incident,
  the 30-min runbook).
- **The backtest is the research
  honesty** (the §3.2): the labeled
  window (the retention, the ANA-14
  posture), the survivorship (the
  breached accounts in the data, the
  24 Part B's integrity), the engine
  label (the "platform" vs "MT5",
  the §3.2's two engines, the honest
  label), the recompute (the 09 §3.4,
  the input hash, the result hash,
  the property test), the disclaimer
  (the "not a guarantee", the §8,
  the ToS line, the FunderBlu legal's
  sign-off) — the anti-design: the
  backtest that implies the live
  performance (the research integrity,
  the 24 Part B's posture).
- **The leader's public performance**
  (the TRD-02): the masked PII (the
  19 §10, the Part A §8's ref
  indirection), the as_of-labeled (the
  24 Part B's freshness, the ANA-14),
  the delisted-history (the 24 Part
  B's DQ-public posture, the no-
  quiet-removal), the no-guarantee
  (the §1's banned set), the tenant's
  curation (the 24 Part A's content
  posture, the 2FA on the delist,
  the followers' notice) — the
  leader's data is their consent
  (the opt-in, the terms, the 2FA,
  the labeled disclosure).
- **The tenant's copy revenue** (the
  §3.1's economics): the BIL-adjacent
  (the 22 class, the pass-through,
  the MetaApi cost, the 08 §1), the
  ledger (the 05, the normal tenant
  revenue), the disclosure (the
  follower's terms, the fee, the
  labeled, the 24 Part A's legal
  block) — the copy fee is the
  tenant's product, the platform's
  role is the engine + the
  accounting, the 22 §3.4's
  pass-through transparency.

## 11. Scalability considerations

- **The copy engine is the latency-
  sensitive path** (the §3.1's
  signal → the order): the p95 target
  (the 300-500 ms, the measured, the
  ANA-class metric, the public stat
  (the honest, the 24 Part B's
  posture)) — the worker's path:
  the BRG deal event (the 08 §3.2's
  sync, the ≤ 60 s poll (the 08 §1's
  poll-only, the signal's freshness
  is the poll's freshness (the
  labeled: the copy latency includes
  the poll's latency (the 08's
  60-s stagger (the 08 §3.2) — the
  copy's "real-time" is the
  poll-bound (the honest, the
  research posture: the copy is the
  near-real-time, the no-latency-
  arbitrage claim (the RSK-38's V3
  detector's input (the 10 §3.3) —
  the copy engine's latency is the
  RSK-38's data, the circularity
  resolved: the copy is the
  legitimate, the RSK-38 fires on
  the *news-clustered* entries (the
  10 §3.3's detector, the copy's
  normal latency is not the
  arb-pattern (the labeled
  distinction, the 24 Part B's
  conduct posture))))
- **The scale** (the V3: the 25-50
  tenants, the 10k concurrent broker
  accounts (the 00 §5), the copy
  subscriptions ≈ the 1-2k active (
  the 10% of the funded (the
  research's adoption class)): the
  mirror's order rate ≈ the leaders'
  trade rate × the followers per
  leader (the 10 leaders × the 100
  followers × the 10 trades/day ≈
  the 10k orders/day ≈ the 0.12/s
  average, the burst (the leader's
  scalping (the 100 orders in the
  minute) × the 100 followers = the
  10k in the minute ≈ the 167/s
  burst — the MetaApi's rate limit
  (the 08 §1's provider, the
  research's ~100 orders/s per
  account (the MT5's limit) — the
  copy engine's order rate is
  bounded by the follower's account
  limit (the per-account, the
  MetaApi's), the platform's
  aggregate is the fan-out (the
  10k accounts × the per-account
  limit (the 08 §3.2's stagger, the
  poll budget (the 08 §3.2) — the
  copy orders are the poll-budget-
  adjacent (the 08's per-tenant poll
  budget extended to the copy's
  order budget, the 29 doc's V3
  line item).
- **The backtest is the compute
  batch** (the §3.2): the off-peak
  (the 06 §3.3's advisory-lock), the
  V3 compute slot (the 29 doc's
  budget: the backtest worker (the
  separate, the Rust (the 09 engine
  (the ADR-11, the 01 §2) — the
  backtest is the 09 service's
  historical mode (the same binary,
  the `--historical` flag, the
  29 doc's V3 compute line), the
  100-trader paper contest's
  backtest (the batch, the minutes-
  to-hours, the off-peak, the 29
  doc's capacity).
- **The paper is the no-broker-cost**
  (the §3.3): the simulation's
  compute (the tick-driven, the 08's
  `bridge.tick` (the 10/s sustained (
  the 00 §5, the V1) → the 100/s (
  the V2) — the paper's 100 accounts
  × the 100/s ticks = the 10k/s
  simulation ticks (the V3: the
  29 doc's compute line, the
  simulation's batch (the 100-ms
  window, the 1k ticks/batch, the
  PG's write (the `paper_deals` (the
  monthly partitions (the 08 §9's
  pattern), the 13-mo retention)),
  the no-MetaApi-cost (the 08 §1's
  cost driver avoided (the paper's
  selling point, the 24 Part B's
  zero-cost contest, the BIL-
  adjacent).
- **The algo API is the rate-limited**
  (the TRD-07/08): the per-key order
  rate (the TRD-08 config, the 60/min
  default (the write-tier, the Part
  A §3.1's slow-write rule), the
  burst (the 10×, the 600), the halt
  (the circuit, the 08 §3.3's
  pattern) — the algo's load is the
  tenant's/developer's, the platform's
  role is the gate + the audit +
  the accounting, the 29 doc's V3
  line item.
- **The cost that matters is the
  MetaApi's** (the 08 §1's cost
  driver): the copy's follower
  accounts (the real MT5, the $75/mo
  each (the 08 §1) — the copy
  adoption is the cost (the tenant's
  decision (the BIL-17 pass-through,
  the 22 §3.4), the paper is the
  zero-cost alternative (the §3.3,
  the TRD-05's value prop), the
  backtest is the no-account
  (the historical, the 08's sync'd
  data, the no-new-account) — the
  TRD's cost story: the copy is
  expensive (the real accounts),
  the paper is free (the simulation),
  the backtest is cheap (the
  historical), the advanced orders
  are the existing (the MetaApi's
  capability, the no-new-cost).

## 12. Open-source solutions

| Option | Verdict |
|---|---|
| **In-house copy engine + the 09 engine's historical mode + the simulation** (this design) | **CHOSEN** — the copy is the signal → the mirror (the 08's sync + the MetaApi's order + the 09's observed, the existing machinery), the backtest is the 09 engine's second user (the ADR-11, the 01 §2, the Rust service), the paper is the simulation (the no-broker, the 08's stand-in) — a copy-trading SaaS (the ZuluTrade-class, the FXCopy-class) is the execution-venue territory (the §1's banned set, the 28 posture) + the data out of house |
| ZuluTrade/FXCopy/OSS copy engines | Rejected (the execution venue, the §1's boundary, the 28 doc's regulatory posture, the 01 ADR class) |
| **MetaApi's advanced orders** (the TRD-06, the 08 §1) | CHOSEN (the MT5-native, the Capabilities() (the 08 §1), the broker's execution, the boundary holds) |
| **The 09 engine (Rust, the ADR-11)** (the backtest's engine, the 01 §2) | CHOSEN (the `evaluate(state, rules, tick)` (the 09 §1) over the historical ticks (the re-runnable, the 09 §3.4, the input hash) — the backtest is the engine's historical mode, the no-new-engine) |
| Backtesting OSS (Backtrader, Zipline, the research's class) | Rejected (the Python stack, the 01 §2's Go/Rust binding, the 09 engine's Rust is the backtest's engine, the ADR-11's posture — the research-grade backtest is the 09 engine's historical mode + the 29 doc's compute, not a new OSS) |
| (The paper's simulation) the in-house tick simulation (this design) | CHOSEN (the no-broker, the 08's stand-in, the `paper_deals` (the separate, the 05 §1 posture) — the simulation is the platform's (the research's paper-trading class, the no-OSS (the simulation is the 200-LOC-class over the ticks, the 08's sync's stand-in)) |
| TradingView (the social feed's chart, the 16 §12) | CHOSEN (the leader's equity curve, the 24 Part B's public profile, the existing) |

## 13. Technology stack

The 09 engine (Rust, the ADR-11, the 01 §2 — the backtest's historical mode, the `--historical` flag), the 08 bridge (the MetaApi, the sync, the Capabilities() (the 08 §1), the order path (the TRD-06/07)), the Go workers (the copy engine, the advisory-lock (the 06 pattern), the simulation's batch), the Postgres (the TRD tables, the §9, the `paper_deals` (the partitions), the BRG's `orders` (the 08 §9)), the 24 Part B's leaderboard pattern (the social feed, the computed + the as_of), the 19 read model (the leader's performance, the ANA-class), the NOT (the notices: the copy skip, the halt, the contest), the RSK (the signals: the `algo_breach`, the RSK-05/06/38's input, the 10 §3.3), the 22 BIL (the tenant's copy revenue, the pass-through, the MetaApi cost, the 08 §1), the ANA (the metrics: the copy latency, the slippage, the skip rate, the backtest stats, the paper stats), the AUD (the critical: the order, the subscribe, the halt; the low: the mirror, the skip), the 28 (the execution boundary, the regulatory posture, the threat model: the key compromise, the copy manipulation, the paper-looks-funded), Prometheus (the copy latency p95 (the public stat), the order rate, the halt rate, the backtest runtime, the simulation tick rate), Sentry.

## 14. Integration — internal modules (glue)

| Module | How |
|---|---|
| **BRG (08)** | the signal (the leader's deal, the 08 §3.2's sync), the mirror's execution (the MetaApi's order, the follower's account, the 08 §3.3's executor), the Capabilities() (the advanced orders, the 08 §1), the `copy_engine: platform` flag (the deal metadata, the §1's RSK-05 allowlist), the poll budget (the copy's order budget, the 08 §3.2's stagger) |
| **EVL (09)** | the observed (the copy deal is the follower's observed, the 09 §3.4, the normal enforcement), the engine (the backtest's historical mode, the ADR-11, the 01 §2, the re-runnable, the 09 §3.4), the conduct (the RSK-05/06's input, the 10 §3.3, the labeled distinction) |
| **LCC (07)** | the account state (the follower's account is the funded/evaluating, the copy is the trading, the state machine's normal), the enforcement (the TRD-08's halt is the LCC-41-class command (the 07 §3.2's single path, the `account_commands` (the 07 §9), the idempotency (the 07's pattern))) |
| **PAY (11)** | the copy's PnL is the follower's trading (the payout's normal, the 11 §3.2's calc, the HWM, the split — the copy has no special payout (the it's the follower's profit, the 05 §1 posture)), the contest's prize (the 24 Part B's prize, the PAY-class, the 22 §3.4) |
| **RSK (10)** | the signals (the `algo_breach` (the TRD-08's halt, the 10 §3.2's kind), the RSK-05/06 (the copy's input, the §1's allowlist), the RSK-38 (the latency arb, the copy's latency data, the 10 §3.3)), the case (the copy manipulation (the follower's device/IP cluster, the RSK-04, the 10 §3.3)) |
| **CHK (12)** | the contest's entry fee (the TRD-05's paper contest, the real money, the CHK's normal flow, the 12 §3.2), the strategy subscription (the TRD-03, the BIL-adjacent, the 22 class) |
| **LED (05)** | the copy's accounting (the follower's trading, the normal, the 05 §1), the paper is the no-LED (the separate tables, the labeled, the 05 §1 posture), the tenant's copy revenue (the BIL-adjacent, the 22, the pass-through) |
| **BIL (22)** | the tenant's copy fee (the plan shape, the 22 §3.2, the pass-through, the MetaApi cost, the 08 §1), the strategy subscription (the 22 class), the paper contest's zero-cost (the BIL-adjacent, the 24 Part B's contest) |
| **ANA (19)** | the read model (the leader's performance, the social feed, the 19 §3.1), the metrics (the copy latency p95 (the public stat), the slippage, the skip rate, the backtest stats, the paper stats, the 19 §3.2's KPI), the backtest's result (the ANA-class read, the 19 pattern) |
| **NOT (14)** | the notices (the copy skip (the follower), the halt (the trader/developer), the leader delist (the followers), the contest (the 24 Part B's pattern), the backtest completed (the tenant)) |
| **TD (16)** | the V3 extension (the social feed screen, the copy subscription UI, the order panel (the TRD-06), the paper account (the "PAPER" badge, the §1's anti-design), the backtest results, the 16 §3.1's screen set extended) |
| **ADM (17)** | the curation (the leader queue, the strategy queue, the 24 Part A's content posture, the 2FA), the copy stats (the tenant's health, the 17 §3.1's pattern), the algo keys (the TRD-07/08, the guardrails, the halt, the re-enable, the 2FA) |
| **24 Part B (CMP)** | the paper contest (the competition pattern, the CMP-01's paper variant, the 24 Part B's scoring (the pure, the versioned, the re-runnable), the prize, the leaderboard, the integrity) |
| **28 (security)** | the execution boundary (the regulatory posture, the §1's test), the threat model (the key compromise, the copy manipulation, the paper-looks-funded, the backtest integrity), the 28 doc's D5 section |
| **AUD (05)** | the critical (the order, the subscribe, the halt, the delist), the low (the mirror, the skip, the backtest, the paper), the recompute (the backtest's result hash, the 09 §3.4, the evidence) |
| **29 (scalability)** | the V3 compute (the backtest's slot, the simulation's batch, the copy's order budget), the MetaApi cost (the 08 §1's cost driver, the BIL-17's pass-through, the 22 §3.4) |

## 15. Integration — external tools

MetaApi (the 08 §1: the sync, the order (the TRD-06/07), the Capabilities() (the advanced orders), the backtest API (the MQL5's backtest, the §3.2's "MT5" engine), the rate limit (the copy's order budget), the cost (the $75/mo/account, the 08 §1, the BIL-17's pass-through)), the 09 engine (Rust, the ADR-11, the 01 §2 — the backtest's historical mode, the compute (the 29 doc's V3 line)), Prometheus/Grafana (the copy latency p95 (the public stat), the order rate, the halt rate, the backtest runtime, the simulation tick rate), Sentry, the R2 (the strategy's MQL5 EA (the TRD-03, the tenant-curated, the 24 Part A's media pattern), the backtest's result (the ANA-class, the 19 pattern)).

## 16. Implementation blueprint (V3)

| Step | Owner | Est | Depends | Exit criteria |
|---|---|---|---|---|
| 1. The leader/copy foundation (the `trading_leaders`, the `copy_subscriptions`, the signal (the BRG deal event, the 08 §3.2), the mirror (the MetaApi's order, the follower's account), the all-or-nothing (the slippage, the 60-s stale, the skip), the `copy_engine: platform` flag (the deal metadata), the copy accounting (the BRG's sync, the EVL's observed, the normal)) | BE-2 | 4 wks | the 08 stable, the MetaApi's order API, the 09's observed | a sandbox leader's fill → the follower's mirror (the ≤ 500 ms p95 (the measured, the ANA metric)), the slippage-exceeded skip (the labeled, the audit), the stale-signal skip (the 60-s, the integrity rule), the RSK-05 allowlist (the property test: the platform copy doesn't fire the RSK-05, the trader-initiated copy does) |
| 2. The social feed (the TRD-02: the leader's public performance (the 19 read model, the as_of-labeled, the masked PII, the Part A §8's ref indirection), the feed (the "top leaders" board (the 24 Part B's leaderboard pattern, the computed + the as_of)), the TD's V3 screens (the leader list, the detail, the subscribe CTA), the tenant's curation (the ADM queue, the 2FA, the delist + the followers' notice)) | FE-01 + BE-2 | 3 wks | 1, the 19 read model, the 24 Part B's pattern | the feed renders (the as_of present, the property test: no PII in the public surface), the curation works (the delist (the 2FA, the notice, the history retained (the "delisted" marker, the 24 Part B's posture))), the subscribe (the 2FA, the consent, the config) |
| 3. The TRD-08 guardrails + the order path (the single, the 07 §3.2's posture: the TRD-08 pre-check (the synchronous, the reject before the MetaApi), the `algo_guardrails` (the versioned, the 2FA on the change), the halt (the circuit, the 08 §3.3's pattern, the `algo_halts`, the re-enable (the 2FA, the review)), the order path (the TD's order panel (the 2FA, the sensitive), the SDK's `trading:write` (the Part A's strictest scope), the critical audit)) | BE-2 + FE-01 | 3 wks | 1, the 07's command pattern, the Part A's keys | the guardrail reject (the `trd.trd08_limit` (the `details.checks[]`, the actionable)), the halt (the breach → the circuit, the open positions (the keep/close, the labeled, the 2FA on the close), the notice, the RSK signal, the audit), the re-enable (the 2FA, the review, the audit), the order path (the single (the property test: no order bypasses the TRD-08 (the CI check, the 07 §3.2's posture))) |
| 4. The advanced orders (the TRD-06: the MetaApi's Capabilities() (the OCO, the trailing, the 08 §1), the TD's order panel (the V3 extension, the 2FA), the BRG's `orders` sync (the 08 §9, the fill = the deal, the EVL's observed, the normal), the `trd.order_capability_missing` (the honest capability gap)) | BE-2 + FE-01 | 2 wks | 3, the MetaApi's capabilities | the OCO order (the TD, the 2FA, the MetaApi's execution, the BRG's sync, the EVL's observed), the capability gap (the honest error (the test: the order type the MetaApi doesn't support → the `trd.order_capability_missing` (the labeled))) |
| 5. The algo API (the TRD-07: the public API's `trading:write` (the Part A's extension, the strictest scope), the delegation (the Part A §3.3, the one-level cap), the order (the MetaApi's, the broker's execution), the rate limit (the TRD-08's order rate, the 60/min), the halt (the §3's circuit), the key compromise runbook (the Part A §10, the CON-15-class, the 30-min)) | BE-1 | 3 wks | 3–4, the Part A's public API | the algo's order (the SDK, the key, the TRD-08 pre-check, the MetaApi's execution, the critical audit, the `api:{key_id}` source), the halt (the breach → the circuit, the re-enable (the 2FA)), the key compromise drill (the revoke + the cascade + the notice, the 30-min, the runbook proven) |
| 6. The backtesting (the TRD-04: the 09 engine's historical mode (the `--historical` flag, the Rust, the ADR-11, the 01 §2), the data (the BRG's tick/deal history, the 13-mo, the 04 §5.4, the labeled window), the engine (the platform's (the 09's) + the MT5's (the MetaApi's backtest API, the §3.2's two engines, the honest label)), the strategy (the TRD-03's spec, the declarative + the MQL5 EA (the R2, the tenant-curated)), the results (the stats, the equity curve, the per-trade, the recompute (the 09 §3.4, the input hash, the result hash), the disclaimer), the compute (the 29 doc's V3 slot, the off-peak, the advisory-lock)) | BE-2 | 4 wks | the 09 engine, the 08's history, the 29 doc's compute | a strategy's backtest (the platform engine, the 13-mo window, the recompute (the property test: the re-run = the same result hash)), the MT5 backtest (the MetaApi's API, the label "backtested on MT5"), the marketplace integration (the "backtested" mark (the result, the period, the engine, the disclaimer)), the compute (the off-peak, the 29 doc's budget (the measured, the capacity line)) |
| 7. The strategy marketplace (the TRD-03: the listing (the strategy (the spec/MQL5), the backtest-verified gate (the §6's `trd.strategy_not_certified`), the tenant's curation (the ADM, the 2FA, the 24 Part A's content posture), the subscription (the BIL-adjacent, the 22 class, the tenant's revenue, the pass-through), the no-guarantee (the §1's banned set, the ToS line, the FunderBlu legal's sign-off), the execution (the trader's own (the EA on their MT5, the platform's hosting + curation + accounting, the boundary holds))) | BE-2 + FE-1 | 3 wks | 6, the 22 BIL, the 24 Part A's curation | a strategy listed (the backtest-verified (the mark, the disclaimer), the curation (the 2FA, the queue), the subscription (the tenant's revenue, the BIL-adjacent, the ledger), the execution (the trader's EA, the no-platform-execution (the boundary test, the §1)), the no-guarantee (the ToS, the legal sign-off (the Phase-1 class, the V3 checklist)) |
| 8. The paper trading at scale (the TRD-05: the simulation (the no-broker, the synthetic fills (the tick-driven, the slippage model (the config)), the virtual balance (the 0 LED, the separate tables, the labeled), the "PAPER" badge (the 16 §3.3's pattern, the property test: the paper UI never renders the funded-badge), the no-real-money route (the `trd.paper_funded_attempt` 403, the code-level), the terms (the "simulation, no real money", the CMS-08, the ToS), the contest (the 24 Part B's pattern, the zero-cost, the BIL-adjacent), the V3-late (the after the copy engine, the §16's step order)) | BE-2 + FE-01 | 4 wks | 1–6, the 24 Part B's competition, the 29 doc's compute | a 100-trader paper contest (the 24 Part B's pattern, the zero-cost (the no-MetaApi, the BIL-adjacent), the simulation (the tick-driven, the slippage, the virtual balance), the "PAPER" badge (the property test green), the no-real-money (the route 403 (the test), the terms (the legal sign-off)), the contest's scoring (the 24 Part B's pure/versioned/re-runnable, the paper equity (the observed-only)), the prize (the 24 Part B's pattern, the PAY-class, the real money (the entry fee's revenue, the CHK's normal))) |

**Risks:** the execution-boundary drift (a feature that
creeps into the platform-executing — the §1's test is
the code-review gate (the "does this place the
trade?" question, the 28 doc's regulatory
posture, the FunderBlu legal's V3 review (the
Phase-1 class)), the copy latency (the poll-
bound (the 08 §1's poll-only, the honest
label, the no-latency-arb claim (the
RSK-38's data, the 10 §3.3), the
slippage (the all-or-nothing (the §3.1's
integrity rule, the no-partial, the
research posture), the MetaApi's rate
limit (the copy's order budget (the
08 §3.2's stagger, the 29 doc's V3
line), the burst (the leader's
scalping × the followers (the 167/s
burst, the §11, the per-account
limit (the MT5's, the 08 §1))), the
paper-looks-funded (the trust + the
regulatory, the §10's property test
(the negative test, the CI gate),
the "PAPER" badge (the 16 §3.3's
pattern), the terms (the legal
sign-off)), the backtest integrity
(the survivorship (the §3.2's
honesty, the 24 Part B's posture),
the recompute (the 09 §3.4, the
property test), the disclaimer (the
ToS, the legal), the engine label
(the two engines, the §3.2's
honest label)), the copy manipulation
(a follower who manipulates the
leader (the device/IP cluster, the
RSK-04, the 10 §3.3), the leader who
front-runs the followers (the
latency, the RSK-38, the 10 §3.3,
the §11's honest latency (the
public stat, the 24 Part B's
posture))), the algo key compromise
(the Part A §10's stack, the TRD-08's
guardrails + the halt (the machine's
trading waits for the human's
limits, the §3.1's always-manual
rule, the TRD-08's form), the 30-min
runbook, the CON-15-class), the
tenant's copy-revenue dispute (the
fee (the BIL-adjacent, the 22 §3.4's
pass-through transparency, the
labeled, the 24 Part A's legal
block), the PnL attribution (the
copy trade is the follower's (the
BRG's sync, the 08 §3.2, the
`copy_engine` flag, the audit-
able, the "whose PnL is it" answer
(the follower's (the execution is
the follower's account, the
broker's, the 08 §1's posture),
the fee is the tenant's product
(the §3.1's economics, the 22
class))).

---

# Part C — PLT: Platform Operations (6 reqs) + CS:
Customer Success (7 reqs)

## Part C.1 — PLT (6 reqs, V3 — 5 recovered)

### 1. Purpose & scope

The cross-tenant platform governance: multi-region
deployment (PLT-01), capacity planning (PLT-02), cost
allocation (PLT-03), incident management (PLT-05),
capacity & cost governance (PLT-06). (PLT-04 is in the
unrecovered band — the pattern: the "platform SLO
ownership" class, the 06 §3.4's SLO's platform-level
owner; scoped from the 06/29 docs' posture.)

**The boundary:** PLT is the *governance layer* over the
06 (DevOps) + the 29 (Scalability) — the 06 is the
*how* (the Hetzner, the Compose, the CI/CD, the
observability, the DR), the 29 is the *numbers* (the
capacity model, the scaling paths, the cost), PLT is
the *decisions* (the multi-region go/no-go, the
capacity investment, the cost allocation to the
tenants, the incident's post-mortem ownership, the
governance cadence). PLT adds no new infra in V3 —
it's the governance over the existing 06/29
machinery.

### 2. The five capabilities

- **PLT-01 (multi-region):** the V3 go/no-go
  framework (the 06 §1's single-Hetzner-AX42 is
  the V1/V2 binding, the ADR-1's posture — the
  multi-region is the V3 *option*, the
  decision framework: the trigger (the RTO/RPO
  breach (the 06 §3.2's RTO ≤ 2 h, the RPO ≤ 5
  min (the WAL rsync (the 06 §3.2) — the
  multi-region is the RTO improvement (the
  cross-region failover, the RTO → the
  minutes-class), the cost (the 29 doc's
  capacity model: the second region = the
  2× infra + the replication (the PG's logical
  replication (the V3's option, the 06 §3.3's
  failover strategy extended), the Redis's
  replication (the 06 §3.2's AOF, the
  cross-region), the MetaApi's geo (the 08
  §1's broker (the MT5 server's geo (the
  ADR-12's broker-TZ, the 09 §3.2's trading
  calendar — the multi-region's
  complication: the trading clock is the
  broker's (the ADR-12, the 01 §3), the
  region doesn't change the broker's geo
  (the trading stays the broker's, the
  platform's region is the API's)), the
  decision: the V3 trigger = the RTO
  breach (the 06 §3.2's monthly drill (the
  binding ops duty, the 06 §3.2) — a
  drill that misses the RTO twice → the
  multi-region review (the CON-adjacent,
  the 21 §3.4's governance), the FunderBlu
  + the platform ops's decision (the 29
  doc's capacity line, the 06 §3.2's DR
  runbook extended).
- **PLT-02 (capacity planning):** the 29
  doc's model + the V3 cadence (the
  quarterly review (the CON-adjacent, the
  21 §3.4): the 00 §5's scale targets (the
  V2: the 25-50 tenants, the 50k traders,
  the 10k accounts, the 100/s ticks, the
  2k msg/s, the 5k orders/day, the 500
  payouts/day, the 5k MetaApi accounts) →
  the headroom (the 2× rule (the 29
  doc's posture: the capacity is the
  2× the target (the measured, the
  Prometheus (the 06 §3.4), the ANA's
  KPIs (the 19 §3.2))), the investment
  decision (the V3: the 2nd AX42 (the
  06 §1's class) / the VPS scale (the
  29 doc's path) / the multi-region
  (the PLT-01), the cost (the 29 doc's
  cost model, the 22 §3.1's meter, the
  BIL's pass-through (the 22 §3.4) —
  the capacity cost is the tenant's
  (the BIL-17, the 22 §3.4) + the
  platform's (the PLT-03's allocation,
  the §2 below).
- **PLT-03 (cost allocation):** the
  per-tenant cost (the 22 §3.1's meter
  (the funded accounts, the payout
  volume, the API calls, the storage,
  the KYC, the events) → the cost model
  (the 29 doc's cost: the MetaApi
  ($75/mo/account, the 08 §1) + the infra
  (the AX42's share (the CPU/RAM/
  storage's allocation (the measured,
  the Prometheus (the 06 §3.4), the
  cgroup's accounting (the 06 §3.1's
  container limits (the OPS-37 (the 06
  §1)), the R2 (the storage, the 22 §3.1's
  meter), the Cloudflare (the bandwidth,
  the 24 Part A §11's line), the MetaApi
  (the 08 §1's cost driver), the
  providers (the Veriff (the 13 §12), the
  NOWPayments (the 11 §12), the
  Match2Pay/Interkasa (the 12 §12), the
  Postmark (the 14 §12))), the allocation
  (the 22 §3.4's pass-through (the
  tenant sees their cost (the BIL's
  invoice, the 22 §3.4's transparency
  (the "at cost + 5%" (the 22 §3.2))),
  the platform's margin (the 22 §3.4's
  disclosed, the BIL-17's pattern)),
  the V3 cadence (the monthly (the BIL's
  invoice (the 22 §3.5), the quarterly
  (the PLT-02's review, the CON-
  adjacent), the audit (the cost's
  ledger (the 22's platform books (the
  22 §14's LED posture (the platform's
  revenue is the platform's books (the
  off-platform, the 22 §14), the
  allocation is the BIL's data (the 22
  §3.1's meter, the 22 §3.4's pass-
  through)).
- **PLT-05 (incident management):** the
  06 §3.3's incident process + the V3
  governance (the severity (the 06
  §3.3's P0-P3), the response (the 06
  §3.3's runbook, the CON-15's control
  ladder (the 21 §3.2), the comms (the
  06 §3.3's status (the Uptime Kuma (the
  21 §12), the DVP-07's status page (the
  Part A §1), the tenant's notice (the
  NOT, the 14 §3.4), the trader's notice
  (the NOT, the 14)), the post-mortem
  (the 06 §3.3's blameless, the V3:
  the cross-tenant (the incident's
  tenant impact (the ANA's per-tenant
  KPI (the 19 §3.2), the CON-09's audit
  (the 21 §3.4), the remediation's
  ownership (the PLT-06's governance
  (the §2 below)), the V3 cadence (the
  monthly (the incident review (the
  CON-adjacent), the quarterly (the
  PLT-02's capacity review's input (the
  incident's capacity signal (the 29
  doc's posture))), the drill (the 06
  §3.2's monthly restore (the binding),
  the V3: the game day (the quarterly
  (the CON-15's control ladder's full
  walk (the 21 §16's step 4's V2 drill
  extended, the cross-team (the
  platform ops + the FunderBlu's ops
  (the MIG-06's concierge pattern (the
  25 §3.6), the labeled)).
- **PLT-06 (capacity & cost
  governance):** the V3 cadence (the
  quarterly (the CON-adjacent, the 21
  §3.4): the capacity (the PLT-02's
  headroom (the 2× rule, the 29 doc),
  the cost (the PLT-03's allocation
  (the 22 §3.4), the margin (the 22
  §3.4's disclosed), the incident (the
  PLT-05's post-mortem's remediation
  (the ownership, the 06 §3.3), the
  decision (the investment (the 2nd
  AX42 / the VPS / the multi-region (
  the PLT-01), the 2FA-class (the
  CON-32's two-op (the 21 §3.5, the
  governance decision, the board-
  adjacent (the 21 §3.2's posture)),
  the audit (the decision's record (
  the CON-09 (the 21 §3.4), the 7-yr
  (the financial-adjacent (the 05's
  class, the 22's platform books))),
  the V3's first governance (the
  FunderBlu's QBR's input (the CS's
  §C.2 below) — the capacity/cost is
  the QBR's data (the tenant sees their
  cost (the BIL's invoice (the 22 §3.5),
  the platform's health (the 21 §3.1's
  home screen, the DVP-07's status
  page (the Part A §1)).

### 3. Events / lifecycles / errors

PLT is the governance (the no new events
(the 06/29/21/22's events are the
data), the cadence (the quarterly
review (the CON-adjacent, the 21 §3.4),
the monthly incident review (the 06
§3.3), the monthly cost (the BIL's
invoice (the 22 §3.5)), the decision
(the CON-32's two-op (the 21 §3.5),
the audit (the CON-09 (the 21 §3.4))),
the errors (the governance's error is
the 21's CON codes (the 21 §6), the
06's SYS codes (the 06 §6) — the PLT
adds no namespace (the governance is
the decisions, the errors are the
06/21's).

### 4. Blueprint (V3)

| Step | Owner | Est | Depends | Exit |
|---|---|---|---|---|
| 1. The cost model (the PLT-03: the per-tenant cost (the 22 §3.1's meter → the 29 doc's cost → the BIL-17's pass-through (the 22 §3.4), the monthly (the BIL's invoice, the 22 §3.5)) | DevOps + BE-2 | 2 wks | the 22's meter, the 29 doc, the 06's observability | the FunderBlu's monthly invoice shows their cost (the MetaApi, the infra share, the R2, the Cloudflare, the providers (the 22 §3.4's transparency, the "at cost + 5%" (the 22 §3.2))) |
| 2. The capacity review (the PLT-02: the quarterly (the 00 §5's targets → the 29 doc's headroom (the 2×), the investment decision (the 2nd AX42 / the VPS / the multi-region (the PLT-01), the CON-32's two-op, the CON-09's audit) | DevOps | 2 wks | 1, the 29 doc, the 06's capacity | the first quarterly review (the FunderBlu + the platform ops, the decision (the labeled, the audit, the 7-yr)), the capacity line in the 29 doc updated (the V3's numbers, the measured) |
| 3. The incident governance (the PLT-05: the monthly review (the 06 §3.3's post-mortem's cross-tenant (the ANA's per-tenant impact (the 19 §3.2), the CON-09's audit), the game day (the quarterly (the CON-15's full walk (the 21 §16's step 4 extended), the cross-team (the FunderBlu's ops, the MIG-06's pattern (the 25 §3.6))), the 06 §3.3's runbook's V3 update (the multi-region's option (the PLT-01's trigger, the RTO breach (the 06 §3.2's drill, the 2× miss → the review)) | DevOps + BE-2 | 2 wks | the 06's incident process, the 21's control ladder, the CON's audit | the game day (the full walk, the cross-team, the post-mortem (the blameless, the 06 §3.3), the remediation's ownership (the PLT-06's governance), the runbook updated (the multi-region's trigger (the labeled)) |
| 4. The multi-region framework (the PLT-01: the go/no-go (the trigger (the RTO breach, the 06 §3.2's drill 2× miss), the cost (the 29 doc's 2× infra + the replication (the PG's logical (the 06 §3.3's failover extended), the Redis's (the 06 §3.2), the MetaApi's geo (the 08 §1, the ADR-12's broker-TZ (the 01 §3)), the decision (the CON-32's two-op, the board-adjacent (the 21 §3.2), the 7-yr audit), the V3-late (the after the 2nd-AX42 (the PLT-02's investment, the cheaper option first (the 29 doc's posture)) | DevOps | 4 wks | 2–3, the 29 doc, the 06's DR | the framework (the trigger, the cost, the decision, the audit), the 2nd-AX42's decision (the PLT-02's review, the CON-32's two-op), the multi-region's go/no-go (the V3-late, the trigger's posture (the no-premature-region (the 29 doc's cost, the 06 §1's single-Hetzner binding (the ADR-1 (the 01 §3))))) |

---

## Part C.2 — CS: Customer Success (7 reqs, V3 — the
unrecovered band, scoped from the docs/00 catalog: "Tenant
NPS, health scoring, churn prediction, QBRs")

### 1. Purpose & scope

The platform's tenant relationship: the tenant NPS
(the survey, the cadence), the health scoring
(the tenant's usage/support/incident → the
score), the churn prediction (the V3-late,
the ML-class, the 29 doc's compute),
the QBR (the quarterly business review,
the FunderBlu's + the future tenants').
The 7 reqs are in the unrecovered band (the
TD/GW/CS pattern, the 16 §1's note) — the
Phase-1 confirmation item (the FunderBlu's
CS owner, the 00 §4's D3 class).

**The boundary:** CS is the *relationship
layer* over the existing data (the ANA's
KPIs (the 19 §3.2), the BIL's usage (the
22 §3.1's meter), the SUP's tickets (the
18 §3.1), the CON's health (the 21 §3.1),
the MIG's cutover (the 25 §3.6) — CS
adds no new data, it's the *interpretation
+ the cadence* (the score, the survey,
the QBR's deck, the churn's signal).

### 2. The capabilities

- **The health score** (the per-tenant,
  the weekly (the ANA's read model (the
  19 §3.1), the CON-adjacent (the 21
  §3.1's home screen's tenant detail
  (the CON-04 (the 21 §3.1))): the
  inputs (the adoption (the tenant's
  traders' active rate (the 19 §3.1's
  `traders_ro` (the 19 §3.1), the
  purchase rate (the 19 §3.1's
  `payments_daily` (the 19 §3.1), the
  payout rate (the 19 §3.1's
  `payouts_daily` (the 19 §3.1), the
  support (the SUP's ticket volume +
  the SLA (the 18 §3.3), the incident
  (the PLT-05's tenant impact (the
  §C.1), the usage vs plan (the BIL's
  meter (the 22 §3.1), the 22 §3.2's
  limits), the score (the weighted (
  the config (the tenant's weights (
  the CS's config, the CON-adjacent),
  the 0-100, the weekly (the ANA's
  rebuild (the 19 §3.4's pattern, the
  rebuildable (the 19 §2's principle))),
  the use (the QBR's input (the §2
  below), the CON-25's queue overview
  (the 21 §3.4's cross-tenant queue (
  the tenant's queue depth (the 17
  §3.1's ADM queues, the CON-25 (the
  21 §3.4))), the churn's signal (the
  §2 below).
- **The NPS** (the survey, the cadence
  (the quarterly (the QBR's cycle (the
  §2), the annual (the contract's cycle
  (the BIL's contract (the 22 §3.1))):
  the survey (the 0-10, the "how likely
  to recommend", the single-question
  (the NPS's standard), the channel (
  the email (the NOT, the 14 §3.4), the
  tenant's CS owner + the platform's
  CS (the 2-person survey, the
  FunderBlu's COO + the platform's
  ops (the §C.2's QBR's attendees)),
  the result (the promoter/passive/
  detractor (the NPS's standard), the
  trend (the quarterly, the ANA-class
  read (the 19 pattern), the CON-
  adjacent (the 21 §3.1's home screen
  (the platform's NPS (the all-tenants,
  the platform:owner (the 21 §1's
  role)))), the follow-up (the
  detractor (the 0-6) → the CS's
  outreach (the human, the QBR's
  agenda (the §2), the SUP-adjacent (
  the ticket (the 18 §3.1, the CS's
  category (the `cs` (the 18 §3.1's
  category registry (the data, the 18
  §3.1)))).
- **The churn prediction** (the V3-
  late, the ML-class (the 25 §12's
  RSK-25 pattern (the 10 §12), the
  29 doc's compute (the Python sidecar
  (the 10 §12's V3 class), the no-
  new-infra (the 29 doc's budget, the
  off-peak (the 06 §3.3's advisory-
  lock))): the inputs (the health
  score's trend (the §2), the usage
  drop (the BIL's meter (the 22 §3.1),
  the support escalation (the SUP's
  SLA breach (the 18 §3.3), the
  incident impact (the PLT-05 (the
  §C.1), the contract's renewal (the
  BIL's contract (the 22 §3.1, the
  `active_to` (the 22 §9)), the
  payout-volume trend (the 19 §3.1's
  `payouts_daily` (the 19 §3.1)),
  the model (the V3-late: the
  logistic (the research's class (the
  10 §12's scikit-learn (the V3
  sidecar)), the no-ML-in-V3-early
  (the health score's trend is the
  V3-early's churn signal (the
  labeled: the "prediction" is the
  trend, the ML is the V3-late (the
  29 doc's compute, the Python
  sidecar (the 10 §12's pattern))),
  the output (the churn-risk (the
  0-100, the weekly (the ANA's
  rebuild (the 19 §3.4), the CON-
  adjacent (the 21 §3.1), the CS's
  outreach (the high-risk (the > 70) →
  the QBR's agenda (the §2), the
  human (the CS's decision (the no-
  auto-action (the 10 §10's V1 human-
  posture extended: the churn-risk is
  the signal, the human decides (the
  outreach, the concession (the BIL's
  contract (the 22 §3.1, the
  `tenant_contracts` (the 22 §9, the
  versioned (the 22 §9)))), the audit
  (the CON-09 (the 21 §3.4), the
  critical (the money-adjacent (the
  concession, the BIL's class (the 22
  §10))).
- **The QBR** (the quarterly business
  review, the FunderBlu's + the future
  tenants'): the cadence (the
  quarterly (the BIL's cycle (the 22
  §3.5), the contract's cycle (the 22
  §3.1)), the deck (the auto-generated
  (the ANA's reports (the 19 §3.3),
  the DOC's PDF (the 15 §3.1), the
  tenant-branded (the 24 Part A's
  branding (the 24 Part A §3.3)),
  the content (the adoption (the 19
  §3.2's KPIs), the revenue (the BIL's
  (the 22 §3.5's invoice, the 22
  §3.4's pass-through), the cost (the
  PLT-03's allocation (the §C.1),
  the support (the SUP's SLA (the 18
  §3.3), the incident (the PLT-05 (
  the §C.1), the health (the §2),
  the NPS (the §2), the roadmap (
  the platform's (the DVP-08's
  changelog (the Part A §1), the
  tenant's (the TEN's feature flags (
  the 03 §3.1, the Flipt (the 01
  §2))), the attendees (the FunderBlu's
  COO + the risk owner + the CS owner
  (the 00 §3's team, the FunderBlu's
  stakeholders (the session memory's
  anchor)), the platform's ops + the
  CS + the tech lead (the 00 §3's
  team)), the outcome (the decisions (
  the roadmap's priorities, the
  contract's renewal (the BIL's (the
  22 §3.1), the concession (the BIL's
  contract (the 22 §9, the versioned),
  the 2FA-class (the CON-32 (the 21
  §3.5) for the concession (the money,
  the BIL's class (the 22 §10)), the
  the action items (the CON-adjacent
  (the 21 §3.1's home screen's tenant
  detail (the CON-04 (the 21 §3.1)),
  the SUP-adjacent (the ticket (the
  18 §3.1, the CS's category)), the
  audit (the CON-09 (the 21 §3.4), the
  7-yr (the financial-adjacent (the
  22's platform books (the 22 §14))
  ).

### 3. Events / lifecycles / errors

The CS's events (the `cs.*` (the topic,
the EVT's class (the 04 §3.1)):
`cs.health_scored` (the weekly (the
ANA's rebuild (the 19 §3.4)), the
consumers (the CON (the 21 §3.1), the
AUD (the low))), `cs.nps_submitted`
(the survey, the NOT's delivery (the
14), the AUD (the low)),
`cs.churn_risk_flagged` (the > 70,
the CON (the 21 §3.1), the NOT (the
platform's CS (the 14 §3.2's staff
role), the AUD (the critical (the
churn-adjacent (the money (the BIL's
class (the 22 §10)))))),
`cs.qbr_generated` (the deck, the DOC
(the 15), the NOT (the invite (the 14
§3.4), the AUD (the low)),
`cs.concession_granted` (the BIL's
contract (the 22 §9), the 2FA (the
CON-32 (the 21 §3.5)), the AUD (the
critical (the money, the BIL's class
(the 22 §10)))). The lifecycles:
the health score (the weekly rebuild
(the 19 §3.4's pattern, the 7-day
retention (the 19 §5's class), the
trend (the 12-mo (the ANA's retention
(the 19 §3.1)))), the NPS (the
quarterly (the survey (the NOT's
delivery (the 14 §3.4), the response
(the 14 §3.5's dedupe (the no-double-
survey), the result (the ANA's read
(the 19 pattern), the 7-yr (the
relationship-class (the 18's 2-yr
extended (the NPS is the relationship
record (the 7-yr (the 05's class (the
financial-adjacent (the contract (the
22 §3.1)))))), the churn-risk (the
weekly (the health score's trend (the
§2), the 7-day retention (the 19 §5),
the ML's V3-late (the 29 doc's
compute, the Python sidecar (the 10
§12's pattern))), the QBR (the
quarterly (the deck (the DOC's PDF (
the 15 §3.1), the 7-yr (the 05's
class), the action items (the CON-
adjacent (the 21 §3.1), the SUP-
adjacent (the 18 §3.1))), the errors:
the CS's codes (the `CS_*` (the
namespace, the 30 doc's class (the
04 §6)): `cs.health_stale` (the 409
(the 19 §6's `ana.model_stale`
pattern (the 19 §6)), the QBR's deck
missing (the 409 (the 19 §6's
`ana.report_running` pattern (the 19
§6))), `cs.nps_duplicate` (the 409 (
the 14 §3.5's dedupe (the no-double-
survey)), the `CS_CONCESSION_
REQUIRED_2FA` (the 403 (the CON-32 (
the 21 §3.5), the BIL's class (the
22 §10))), `cs.churn_model_unavailable`
(the V3-late's ML down (the 503 (the
04 §6's `*_PROVIDER_UNAVAILABLE`
pattern (the 04 §6)), the fallback (
the trend (the §2's labeled: the
"prediction unavailable, the trend
shown" (the ANA-14 (the 19 §2), the
honest)).

### 4. Blueprint (V3)

| Step | Owner | Est | Depends | Exit |
|---|---|---|---|---|
| 1. The health score (the §2: the inputs (the 19 §3.1's read models, the 18 §3.3's SLA, the 22 §3.1's meter, the §C.1's incident), the weighted (the config, the CON-adjacent), the weekly (the ANA's rebuild (the 19 §3.4)), the CON's surface (the 21 §3.1's tenant detail (the CON-04 (the 21 §3.1))) | BE-2 | 2 wks | the 19's read models, the 18's SLA, the 22's meter, the CON's tenant detail | the FunderBlu's health score (the weekly, the CON's surface, the audit (the `cs.health_scored` (the low)), the rebuildable (the 19 §2's principle, the recompute (the property test (the 19 §3.4's pattern)))) |
| 2. The NPS (the survey (the NOT's delivery (the 14 §3.4), the 0-10, the single-question, the quarterly (the QBR's cycle), the result (the ANA's read (the 19 pattern), the CON's home (the 21 §3.1, the platform:owner), the detractor's follow-up (the CS's outreach, the SUP's category (the 18 §3.1)) | BE-2 + FE-2 | 2 wks | 1, the NOT, the ANA, the SUP | the FunderBlu's first NPS (the quarterly, the COO + the platform's ops (the 2-person), the result (the CON's home, the trend (the 12-mo (the 19 §5))), the detractor's follow-up (the outreach (the logged, the SUP's ticket (the `cs` category (the 18 §3.1)))) |
| 3. The QBR (the deck (the ANA's reports (the 19 §3.3), the DOC's PDF (the 15 §3.1), the tenant-branded (the 24 Part A §3.3), the content (the §2's set), the auto-generated (the quarterly (the BIL's cycle (the 22 §3.5))), the invite (the NOT (the 14 §3.4)), the action items (the CON-adjacent (the 21 §3.1), the SUP-adjacent (the 18 §3.1)), the audit (the CON-09 (the 21 §3.4), the 7-yr) | BE-2 + FE-2 | 3 wks | 1–2, the 19's reports, the DOC, the BIL's cycle | the FunderBlu's first QBR (the deck (the auto-generated, the tenant-branded, the content complete (the adoption, the revenue, the cost (the §C.1), the support, the incident, the health, the NPS, the roadmap)), the meeting (the COO + the risk owner + the CS (the FunderBlu), the ops + the CS + the tech lead (the platform)), the decisions (the roadmap's priorities, the renewal (the BIL's (the 22 §3.1)), the action items (the CON's surface, the SUP's tickets), the audit (the 7-yr)) |
| 4. The churn prediction (the V3-late: the trend (the §2's V3-early (the health score's trend, the labeled)), the ML (the V3-late (the Python sidecar (the 10 §12's pattern), the 29 doc's compute, the off-peak (the 06 §3.3)), the output (the 0-100, the weekly (the ANA's rebuild (the 19 §3.4)), the CON's surface (the 21 §3.1), the outreach (the > 70, the QBR's agenda (the §3), the human (the no-auto-action (the 10 §10's posture)), the concession (the BIL's contract (the 22 §9), the 2FA (the CON-32 (the 21 §3.5)), the audit (the critical (the BIL's class (the 22 §10)))) | BE-2 | 3 wks | 1–3, the 29 doc's compute, the 10 §12's sidecar pattern, the BIL's contract | the churn-risk (the weekly, the CON's surface, the audit), the ML (the V3-late (the sidecar, the off-peak, the 29 doc's budget), the trend fallback (the `cs.churn_model_unavailable` (the 503, the labeled (the ANA-14 (the 19 §2)))), the outreach (the > 70 (the QBR's agenda, the human), the concession (the BIL's contract (the versioned (the 22 §9)), the 2FA, the critical audit) |

**Risks (CS):** the score's gaming (a
tenant optimizing the score, not the
business — the §2's inputs are the
*business* metrics (the adoption, the
revenue, the support (the 18 §3.3's
SLA, the 19 §3.2's KPIs)), the no-
single-metric (the weighted (the
config, the CON-adjacent (the 21
§3.4)), the audit (the score's
computation (the 19 §3.4's rebuildable
(the 19 §2)), the "what's the score"
answerable (the 24 Part B's evidence
posture (the 24 Part B §3.3))),
the NPS's low response (the 2-person
survey (the §2, the FunderBlu's COO +
the platform's ops (the 00 §3's
team, the stakeholders (the session
memory's anchor)), the QBR's
integration (the NPS is the QBR's
input (the §3), the no-standalone-
survey (the relationship context
(the QBR (the §3)), the churn's false
positive (a high-risk that's not
churning — the §2's human (the no-
auto-action (the 10 §10's posture),
the QBR's agenda (the §3), the
outreach (the human's judgment (the
CS's role (the 00 §4's D3, the
relationship))), the concession's
slip (a QBR concession that erodes
the margin — the BIL's contract (the
22 §9, the versioned, the 2FA (the
CON-32 (the 21 §3.5)), the audit (
the critical (the BIL's class (the
22 §10)), the margin check (the PLT-
03's allocation (the §C.1), the 22
§3.4's pass-through (the "at cost +
5%" (the 22 §3.2)) — the concession
is the margin's decision (the
platform's finance (the 22 §14's
platform books (the 22 §14)), the
QBR's data (the PLT-03 (the §C.1),
the 22 §3.4).

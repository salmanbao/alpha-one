# 04 — GW + EVT: API Gateway & Event Backbone

> Covers PRD modules **GW** (37 requirements, in-app gateway layer) and **EVT**
> (34 requirements: outbox, relay, streams, event log, webhooks in/out).
> Together they are the "nervous system": everything that crosses a boundary goes
> through one of these two paths.

## 1. Purpose & scope

**GW** is the in-app request pipeline (ADR-4): tenant resolution, authn, authz,
rate limits, quotas, entitlements, idempotency, correlation, the global error
contract, request logging, and request hygiene (size/timeouts, header redaction).
It is a **Go middleware package inside `api`**, not a separate service — but it has
its own contracts, tests, and error codes because every module depends on it.

**EVT** is the async backbone (ADR-6/7): transactional outbox → relay → Redis
Streams → consumer groups, the durable **event log**, replay, DLQs, **ingress
webhooks** (provider → us, V1), and **outbound tenant webhooks** (us → tenant
integrators, V2 via Hook0).

Requirement coverage: GW `01,02,03,04,05,12,18` (V1.0: route groups, tenant resolution, authn, authz, rate limit, idempotency, error envelope) +
`06,07,08,09,10,11,13,14,15,16,17,20,21,22,23,24,25,26,27,29,30,31,32,33,34,35,36,37` (V2.0) + `19,28` (V3.0: tenant sandbox, deprecation headers);
EVT `01,02,03,05,08,10,20` (V1.0: outbox, relay, envelope, consumers, event log, ingress webhooks, command queue) +
`04,06,07,09,11,12,13,14,15,16,17,18,19,21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,36` (V2.0) + `37` (V3.0).

## 2. Architecture

```
                 REQUEST PATH (GW)                                   EVENT PATH (EVT)
┌──────────┐  ┌───────────────────────────────────────────┐   ┌─────────────────────────────┐
│ client   │──► 1 security headers & hardening            │   │ domain tx:  write + outbox  │
└──────────┘  │ 2 tenant resolution (GW-02)               │   └──────────────┬──────────────┘
              │ 3 authn (session|service|api-key)         │                  ▼
              │ 4 authz (Casbin; AUTH-13)                 │   ┌─────────────────────────────┐
              │ 5 rate limit: IP (edge) + user + tenant   │   │ relay (1 instance, PG lock) │
              │ 6 quota + entitlement gate (TEN)          │   │  poll outbox (keyset, 500)  │
              │ 7 idempotency (Redis, 24h, scoped)        │   │  XADD topic.<domain>        │
              │ 8 correlation id in/propagate             │   └──────────────┬──────────────┘
              │ 9 body limits / timeouts / redaction      │                  ▼
              │ 10 handler                                │   ┌─────────────────────────────┐
              │ 11 success/error envelope + audit flag    │   │ Redis Streams (consumer grp)│
              └───────────────────────────────────────────┘   └──┬──────────────────────┬───┘
                                                                 ▼                      ▼
                                                        workers consumers          DLQ.{consumer}
```

## 3. System design

### 3.1 GW middleware chain (order binding)

**Route groups (GW-01, V1 — binding):** one API exposing four route groups,
separation enforced at the routing layer:

| Group | Surface | Auth realm |
|---|---|---|
| `/v1/auth/*`, `/v1/trader/*` | trader portal | trader (email+password → JWT access + rotating refresh, AUTH-07) |
| `/v1/admin/*` | tenant admin | staff (JWT + TOTP 2FA, AUTH-09) |
| `/v1/console/*` | platform console | separate console realm, Super Admin only, mandatory 2FA (CON-01, AUTH-16) |
| `/v1/webhooks/*` | provider webhooks (payments CHK-07, KYC KYC-05) | provider signature (EVT-10) |
| `/internal/*` (compose network only) | service-to-service (BRG/EVL command + engine paths) | static per-service bearer (step 3); never edge-routed |

The URL plan beyond the V1 baseline groups is resolved (D46, docs/54): module
paths normalize under the four groups (each doc's §7.1/§7.2).

**Transport (D64, docs/59):** the browser surfaces (TD/ADM/CON) authenticate
with the **HttpOnly session cookie** (the `auth_sessions` projection is the
session of record — docs/02 §3.3; the ZITADEL refresh flow sits behind it);
non-browser clients present the bearer JWT. Cookie-authenticated state
changes pass the **origin check** in this chain — the docs/28 T8 CSRF
defense, now written into the chain rather than cited.

| # | Step | Behavior | Req |
|---|---|---|---|
| 1 | Edge handoff | Trust Cloudflare: `CF-Connecting-IP` (only if CF proxy chain verified, GW-33), WAF/DDoS done at edge | GW-20, GW-33 |
| 2 | Tenant resolution | **V1: domain/subdomain only** on the public edge (TEN-02; rejected before auth runs; unknown → `404 tenant.unknown_host`). **Internal routes** (`internal` group) are never edge-routed: they are reachable only on the compose network and resolve the tenant from `X-Tenant-Id` (docs/02 §3.3 order) | GW-02, TEN-02 |
| 3 | Authn | **V1:** JWT (trader/staff) or console realm session verified on every protected route; invalid → `401 auth.invalid_credentials`. **Internal routes:** static per-service bearer token from SOPS (one per service, 90 d rotation) — never user tokens; every call logged with the service identity + `correlation_id` (docs/44 §7; HMAC/mTLS is the V2 upgrade). **API keys:** primitives exist in V1 but have **no tenant-facing surface** until AUTH-21 (decision D18) | GW-03, GW-16 |
| 3.5 | **Status gate** (docs/44 §7) | a) tenant state → `tenant.suspended`, or `tenant.not_live` for a pre-`active` tenant on a trader-facing route (`details.state` names it — corrected from the unregistered `tenant.not_ready`, docs/47 M2); b) identity state → `auth.account_suspended`; c) membership state for `(identity, tenant)` → `auth.membership_suspended` (console realm skips c). Resolved in this order so the error never reveals which layer failed beyond what the host already discloses; cached in Redis ≤ 5 s keyed by `(identity, tenant)`, invalidated by `user.suspended` / `user.activated` / membership events. **Route-class aware** (docs/47 §5): the pre-`active` deny (`tenant.not_live`) applies to trader-facing routes only — an `onboarding` tenant's staff surfaces pass the gate by design (the checklist state); `tenant.suspended` denies every surface. The state × surface × code cell set is `contracts/tenants/state-capabilities.yaml` (I-20 test source, gate 16) | GW-04, AUTH-20/43, TEN-15 |
| 4 | Authz | **V1:** module-declared `resource.action` permission keys (AUTH-13) enforced per route; registry `contracts/permissions/registry.md` + bindings `contracts/permissions/roles.yaml` (role → key, seeded into Casbin — D14/D15); denied → `403 permission.denied`. Engine: policy evaluation behind `authorizer.Check` (Casbin embedded — ADR-14; an implementation detail, the contract is the key model). Console realm separate (CON-01) | GW-04, AUTH-13 |
| 5 | Rate limit | edge (per-IP) → per-user (Redis 100 rpm default) → per-route (auth 10/5 min, payout 5/h) | GW-05 |
| 6 | Tenant quota + entitlement | plan limits (RPM, concurrency) + module entitlement gate; suspended tenant → 403 | GW-06, GW-22, GW-23 |
| 7 | Idempotency | `X-Idempotency-Key` (UUIDv4) → `SETNX t:{ten}:idem:{method}:{path}:{key}` TTL 24 h (GW-31); stored result replayed verbatim (same status); **conflict** (same key, different body hash) → `409 request.idempotency_conflict` (GW-12 V1 code) | GW-12, GW-31, GW-37 |
| 8 | Correlation | `X-Correlation-Id` in or new ULID; propagated: logs, events (`correlation_id`), engine calls, webhooks | GW-09, GW-36 |
| 9 | Hygiene | body ≤ 1 MB (uploads 10 MB via presigned R2 — GW-26); handler timeout 10 s; sensitive header redaction in logs (Authorization, tokens — GW-35) | GW-13, GW-35 |
| 10 | Handler | domain package | — |
| 11 | Response | success envelope (**binding — D45, docs/54**): `{data, meta{request_id, version, pagination{cursor, has_more}}}`; error contract (GW-18 — `code`, `message`, `correlation_id`); pagination standard (GW-21, cursor); `Retry-After` on 429 (GW-29); `Deprecation`/`Sunset` headers (GW-28, V3) | GW-18..21,28,29,30 |
| — | Audit flag | sensitive routes registered in a route table → mandatory audit write on success + failure (GW-17) | GW-17 |
| — | Probes | `/healthz` (liveness: process up), `/readyz` (readiness: PG ping + Redis ping + relay lag < 60 s; schema version reported, deploy blocks on drift — docs/06 §2.3) | GW-14 |
| — | OpenAPI | `/v1/openapi.json` per route group, served by api (GW-15); docs at `docs.alpha1.io` (CMS) | GW-15 |
| — | Maintenance | `maintenance_mode` flag (Flipt) → 503 + `Retry-After` for all non-probe routes (GW-32) | GW-32 |
| — | Caching | GET-only, cacheable routes declared per route (`Cache-Control: private, max-age=N` + tenant-tagged keys; invalidation by domain events) (GW-24, V2) | GW-24 |
| — | Batch | `/v1/batch` (POST, ≤ 50 sub-requests, all GET, same tenant) → sequential results (GW-25, V2) | GW-25 |
| — | Sandbox | `X-Sandbox: true` with tenant's sandbox flag (test tenants) → writes to shadow namespace, never broker (GW-19, V2) | GW-19 |

**Error contract (GW-18) — the single shape for every failure** (exact
envelope per the V1 execution sheet, `contracts/api/gw.md`):

```json
{ "code": "payout.ineligible",
  "message": "You are not eligible for a payout yet: minimum trading days not met.",
  "correlation_id": "01J9..." }
```

- `code` — stable machine code, dotted `domain.action` convention
  (registry: [30-error-taxonomy](30-error-taxonomy.md); the V1 baseline set:
  `contracts/errors/taxonomy.md`).
- `message` — the user-facing message pattern per the taxonomy (user-safe).
- `correlation_id` — request correlation id; also recorded in audit entries
  (AUD-01).
- Internal details never leak (stack traces, SQL, provider keys, PII).
  Extended (post-V1, design-level): module-specific `details` objects and
  auto-generated `docs_url` pages per code are the V2 addition.

### 3.2 EVT: outbox write pattern (EVT-01)

Rule: **a domain event exists iff the DB transaction that caused it committed.**

```go
// inside any domain write transaction
tx.Events().Append(ctx, "order.paid", map[string]any{
  "order_id": o.ID, "amount_cents": o.AmountCents, ...
})
tx.Commit()   // INSERT row + INSERT outbox row — atomic
```

`outbox` row: `event_id (ULID, unique) · topic · payload (envelope JSON) ·
tenant_id · entity_id (routing key) · correlation_id · created_at ·
published_at NULL · publish_attempt`. No business code touches Streams directly.

### 3.3 Relay (EVT-02)

Single instance (PG advisory lock `relay:lock`, steal after 30 s heartbeat):
1. `SELECT ... FROM outbox WHERE published_at IS NULL ORDER BY id LIMIT 500 FOR UPDATE SKIP LOCKED`.
2. Per event: `XADD topic.<domain> MAXLEN ~ 100000 * {payload}` with stream
   field `event_id` for dedupe; set `published_at = now()`.
3. On XADD failure: leave `published_at NULL`, `publish_attempt++`; 5 failures →
   CRITICAL alert (relay is the only bridge — its failure = platform-wide event halt).
4. **Pruning** (a V1 necessity — the outbox must not grow unbounded; EVT-33's
   V2 retention ops formalize the policy): published events older than 7 d
   deleted nightly (they live in the `events` table forever).
5. **Wake-up = doorbell + safety poll (D79, docs/63 §4.5).** The relay
   `LISTEN`s on the `outbox_doorbell` channel and runs step 1 immediately
   on each notification; notifications arriving mid-drain coalesce into
   one more pass. Producers on the latency-critical path (the BRG
   group-commit writer) issue `pg_notify('outbox_doorbell','')` inside
   their outbox transaction, so the doorbell rings on commit and never
   for a rolled-back row. The 1-s safety poll stays, so a lost
   notification (e.g. a relay reconnect) costs ≤ 1 s. NOTIFY carries **no
   payload and no delivery guarantee**. It is not the transport (§12's
   rejection stands); the outbox row is.

   **Correction to D76's accepted-risk wording (docs/63 F6):** enforcement
   commands do not ride the relay, but **evaluation does**. EVL's only
   input, `bridge.tick`, is outbox → relay → Streams, so a relay stall is
   an evaluation pause. The `bridge` topic therefore gets its own lag
   alert: `relay.lag{topic=bridge}` > 5 s → WARN, > 30 s → CRITICAL.

### 3.4 Event log (EVT-08)

`events` = durable replay source (outbox rows are pruned): written by the relay
(same XADD batch → PG INSERT, best-effort same tx via a second connection with
retry; if PG insert fails after XADD, the relay **fails the batch** and re-publishes —
consumers dedupe by `event_id`, so duplicate XADD is safe). Partitioned monthly;
retention: V1 keep 13 months, then archive to R2 (EVT-22).

### 3.5 Consumers (EVT-05)

Every consumer declares: `name`, `topic` pattern (`*` allowed), `group` (= name),
`acks: manual`, `dlq: dlq.{name}`, `idempotency: (event_id, consumer) upsert in
consumer_state`, `max_attempts: 5` with backoff 1 s ×2^k, `timeout: 30 s`.
Worker supervisor: per-consumer goroutine pool (per-entity serial lanes via
`entity_id` hash → N lanes, ordering preserved per entity, EVT-25 V2 formalizes).
**At-least-once + idempotent = effectively-once for side effects.**
**DLQ operations (V1 — D47, docs/54):** after `max_attempts` the event lands in
`dlq.{consumer}` + alert; recovery is the relay's `dlq` subcommand —
`relay dlq list --consumer=X`, `relay dlq retry --consumer=X --id=...`
(re-publishes the original envelope; consumers dedupe), `relay dlq purge`
— run by ops with the SOPS service identity; every action is logged to AUD
(`security.replay` class). The CON DLQ screen (list/filter/bulk-retry) is the
V2 UX (blueprint step 10); the V1 rule is: no dead event without either a
retry or a recorded purge decision.

### 3.6 Ingress webhooks (EVT-10, V1)

Provider → us (MetaApi, Veriff, NOWPayments/Match2Pay/Interkasa):
- dedicated paths `/v1/webhooks/{provider}` (GW-11 routing), **unauthenticated by
  design** but each adapter: (a) verifies signature/HMAC or provider token,
  (b) validates schema, (c) **idempotent on provider event id** (`provider_events`
  table: provider, provider_event_id, payload_hash, status → unique key),
  (d) processes inline if < 200 ms else `202` + async handler.
- Provider event processing emits **our** domain events (e.g. a Veriff decision
  → the producer module's V1 events `kyc.approved`/`kyc.rejected`, docs/13
  §4.1 — never an event name invented at the ingress) → our outbox → consumers. Never call providers from
  consumer paths without a circuit breaker.

### 3.7 Outbound tenant webhooks (EVT-11..16, 26, 31, 34 — V2)

Per tenant: endpoints (`tenant_webhooks`: url, event filters, `secret` field-
encrypted, active, retry policy). Delivery = **Hook0** (self-hosted): our relay-side
dispatcher forwards tenant-filtered events to Hook0 (which does retry/backoff,
HMAC-SHA256 signing `X-AlphaOne-Signature`, delivery logs, replay UI in ADM-20).
Rules: per-endpoint throttle 100/min (EVT-16); tenant suspension pauses delivery;
5xx/timeout → Hook0 retry (max 8, 1 h); then endpoint auto-disabled + alert
(tenant + CON). Test: ADM "send test event" (EVT-15). Replay window 72 h (EVT-26).
Signing secret rotation: two secrets, 24 h overlap (EVT-34).

### 3.8 Replay & backfill (EVT-09, V2 formal ops)

`relay replay --topic=account --from=seq --to=seq` re-publishes from `events` with
original envelope (consumers dedupe). Used after: consumer bug fixes, DLQ purges,
read-model rebuilds (ANA-22), cutover verification (MIG).

## 4. Events (produced by this module)

### 4.1 V1 baseline events — authoritative

**None.** The spine emits no V1 catalog events: provider truth surfaces as the
*producer modules'* V1 events (`order.paid`, `kyc.*` — docs/12/13 §4.1), and
command traffic is the `account_commands` table (EVT-20), never events. (The
docs/31 generator's 4.1/4.2 scan requires this section to exist — docs/54 M5.)

### 4.2 Extended (post-V1) event model — design-level

| Event | Producer | Consumers |
|---|---|---|
| `gateway.maintenance_entered/exited` | GW | CON, NOT (tenant owners) |
| `gateway.rate_limit_breached` (sampled 1%) | GW | ANA, CON |
| `webhook.delivered / webhook.failed / webhook.endpoint_disabled` | EVT (V2) | ADM (tenant), AUD, CON |
| `outbox.pruned` (daily summary) | relay | AUD |

(`relay.lag` is a Prometheus metric + CON gauge, not an event — it never
enters the outbox.)

## 5. Lifecycles

- **Idempotency key:** `new → (24 h TTL) → expired`. Replayed within TTL; after
  TTL the request is treated as new (documented to integrators).
- **Outbox row:** `unpublished → published → pruned (7 d)`.
- **Event (log row):** `appended → (retention 13 mo) → archived (R2)`.
- **Consumer state:** per (consumer, event_id): `processing → acked | dlq` (V2
  inspectable — EVT-27).
- **Webhook endpoint:** `active → (8 consecutive failures) disabled → re-enabled
  (admin)`.
- **Maintenance mode:** `off → on (Flipt) → off`; on = 503 + `Retry-After: 60`.

## 6. Error taxonomy
### 6.1 V1 baseline codes — authoritative

From `contracts/errors/taxonomy.md` (the V1 execution sheet; module GW). These are the exact codes the V1 surfaces return; the envelope is GW-18 (`code`, `message`, `correlation_id`).
| Code | HTTP | Meaning | User-facing message |
|---|---|---|---|
| `tenant.unknown_host` | 404 | Domain/subdomain does not resolve to a tenant | "This address does not belong to a registered firm." |
| `auth.invalid_credentials` | 401 | Missing/invalid token or login failed — identical for unknown email and wrong password (enumeration-resistant) | "Email or password is incorrect." |
| `permission.denied` | 403 | Role lacks the route's `resource.action` key | "You do not have access to this action." |
| `rate.limited` | 429 | Per-IP/per-user rate limit exceeded | "Too many requests. Try again shortly." |
| `request.idempotency_conflict` | 409 | Idempotency key reused with different request body | "Request already processed with different data." |
| `tenant.suspended` | 403 | Tenant suspended: logins, new orders, payouts stop | "This firm is currently suspended." |
| `tenant.not_entitled` | 403 | Module disabled for tenant | "This feature is not part of your plan." |
| `module.unknown` | 400 | Entitlement change references a non-V1 module | "Unknown module." |


Namespace `GW` (+ `EVT` for webhook/ingress):
### 6.2 Extended (post-V1) codes — design-level

> Below the V1 baseline (6.1); names in the GW-18 dotted convention. Rows duplicating a V1 baseline code were folded into the baseline table (the merged registry: docs/30).


| Code | HTTP | Meaning |
|---|---|---|
| `gw.unresolved_tenant` | 404 | (public shape = `TENANT_NOT_FOUND`) |
| `gw.unauthorized` | 401 | Missing/invalid credentials |
| `gw.forbidden` | 403 | Authz denial (policy id in details) |
| `gw.rate_limited` | 429 | `Retry-After` set; scope in details (ip/user/tenant) |
| `gw.quota_exceeded` | 429 | Plan quota; `details.metric` |
| `gw.module_disabled` | 403 | Entitlement gate (module not enabled for tenant) |
| `gw.idempotency_conflict` | — | (folded — the V1 baseline code is `request.idempotency_conflict` **409**, GW-12; this extended variant predates the fold) |
| `gw.payload_too_large` | 413 | Body over limit |
| `gw.timeout` | 504 | Handler exceeded budget |
| `gw.maintenance` | 503 | Maintenance mode |
| `gw.method_not_allowed` | 405 | — |
| `evt.webhook_signature_invalid` | — | (folded — the V1 baseline code is `webhook.signature_invalid` **401**, EVT-10) |
| `evt.webhook_schema_invalid` | 422 | Ingress: payload failed schema |
| `evt.webhook_duplicate` | 200 | Ingress: already processed (idempotent 200) |
| `evt.consumer_dlq` | — | Internal: consumer gave up (alert + DLQ row) |
| `evt.relay_stopped` | — | Internal CRITICAL: relay not publishing 60 s |

HTTP mapping table (code → status) is part of the contract tests; a leaked 500 with
a non-registered code fails CI (`error_registry_test`).

## 7. API endpoints
### 7.1 V1 baseline — `gw` (see `contracts/api/gw.md`)

**In-app middleware contract, not endpoints** — the gateway is in-app middleware behind Cloudflare (no standalone gateway product). `contracts/api/gw.md` defines the cross-cutting request/response contract every module inherits: route groups (GW-01), tenant resolution (GW-02), authentication (GW-03), authorization via `resource.action` keys (GW-04), rate limiting (GW-05), idempotency (GW-12), and the error envelope (GW-18 — `code`, `message`, `correlation_id`).

### 7.2 Extended (post-V1) surface — provisional

> Not in the V1 execution sheet. Design-level. **URL plan resolved (D46, docs/54): the GW-01 groups are the plan** — every module's extended surface normalizes into `/v1/trader/*`, `/v1/admin/*`, `/v1/console/*`, `/v1/webhooks/*` (or the compose-only `/internal/*`); the un-grouped paths in other modules' §7.2 lists are pre-normalization illustrations. Shown for platform completeness (V2/V3 phases, docs/99).

Public/system:

- `GET /healthz` — liveness: the process is up (GW-14, unauthenticated).
- `GET /readyz` — readiness: PG ping + Redis ping + relay lag under 60 s (GW-14, unauthenticated).
- `GET /v1/openapi.json` — the served OpenAPI document for this deployment.
- `POST /v1/webhooks/metaapi`, `POST /v1/webhooks/veriff`, `POST /v1/webhooks/nowpayments`, `POST /v1/webhooks/match2pay`, `POST /v1/webhooks/interkasa` — provider webhook ingress (EVT-10, signature-verified).

Tenant-side (V2 webhook management): `GET|POST /v1/webhooks`,
`GET|PATCH|DELETE /v1/webhooks/{id}`, `POST /v1/webhooks/{id}/test`,
`GET /v1/webhooks/{id}/deliveries`, `POST /v1/webhooks/{id}/replay`.

Console: `GET /v1/console/events?topic=&tenant=&since=`,
`POST /v1/console/events/replay` (seq range, requires 2FA),
`GET /v1/console/dlq?consumer=`, `POST /v1/console/dlq/{id}/retry`,
`GET /v1/console/relay` (lag, queue depth, publish rate).

Every domain module's endpoints inherit the GW envelope, pagination
(`?limit≤100&cursor=`, response `meta.pagination{cursor, has_more}`), and
`X-Idempotency-Key` support on all `POST`/`PATCH` writes.
## 8. Schema (key shapes)

```jsonc
// success envelope — BINDING (D45, docs/54): every 2xx response
{ "data": { ... }, "meta": { "request_id": "01J9...", "version": "v1",
    "pagination": { "cursor": "eyJpZCI6...", "has_more": true } } }  // pagination on lists only

// error envelope (GW-18) — exact V1 shape, see §3.1
{ "code": "...", "message": "...", "correlation_id": "01J9..." }

// event envelope (EVT-03) — canonical: contracts/events/payloads/envelope.schema.json
// exactly: id, type, version, tenant_id, occurred_at, correlation_id, payload
// correlation_id is REQUIRED from the ninth pass (docs/49 C1): GW step 8's
// propagation promise ("events (correlation_id)") is now part of the envelope
// contract; workers mint one at job start. Actor context stays payload-level
// (`*_by` fields) extended by causation_id/actor{kind,id,tenant_id} post-V1.

// GET /v1/console/relay
{ "data": { "lag_seconds": 1.2, "queue_depth": 42, "publish_rate_per_min": 3200,
    "last_published_at": 1758278400123, "instances": 1, "lock_holder": "relay-abc" } }
```

## 9. Database design

```sql
CREATE TABLE outbox (
  event_id      ULID PRIMARY KEY,
  topic         TEXT NOT NULL,              -- 'account','bridge','payout',...
  payload       JSONB NOT NULL,             -- full envelope
  tenant_id     ULID NOT NULL,
  entity_id     TEXT NOT NULL,              -- routing key (ordering lane)
  correlation_id ULID,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  published_at  TIMESTAMPTZ,
  publish_attempt INT NOT NULL DEFAULT 0
);
CREATE INDEX idx_outbox_unpublished ON outbox(id) WHERE published_at IS NULL;

CREATE TABLE events (
  event_id      ULID,
  seq           BIGINT GENERATED ALWAYS AS IDENTITY,   -- global append order, assigned by the
                                                       -- INSERT (the relay is the single writer;
                                                       -- NO Redis counter in the durable path —
                                                       -- the D27 lesson, docs/48); V2 CON replay
                                                       -- addresses seq ranges
  topic         TEXT NOT NULL,
  tenant_id     ULID NOT NULL,
  entity_id     TEXT NOT NULL,
  type          TEXT NOT NULL,
  version       INT NOT NULL,
  occurred_at   TIMESTAMPTZ NOT NULL,
  correlation_id ULID,
  payload       JSONB NOT NULL,
  appended_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (topic, event_id)
) PARTITION BY RANGE (appended_at);
CREATE INDEX idx_events_tenant_type ON events(tenant_id, type, occurred_at);
CREATE INDEX idx_events_entity ON events(entity_id, occurred_at);

CREATE TABLE consumer_state (
  consumer      TEXT NOT NULL,
  event_id      ULID NOT NULL,
  status        TEXT NOT NULL DEFAULT 'processing',
  attempts      INT NOT NULL DEFAULT 1,
  last_error    TEXT,
  processed_at  TIMESTAMPTZ,
  PRIMARY KEY (consumer, event_id)
);

CREATE TABLE provider_events (           -- ingress idempotency (EVT-10)
  provider      TEXT NOT NULL,
  provider_event_id TEXT NOT NULL,
  tenant_id     ULID,
  payload_hash  TEXT NOT NULL,
  status        TEXT NOT NULL DEFAULT 'processed',
  received_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (provider, provider_event_id)
);

CREATE TABLE tenant_webhooks (           -- V2
  id            ULID PRIMARY KEY,
  tenant_id     ULID NOT NULL REFERENCES tenants(id),
  url           TEXT NOT NULL,
  events        TEXT[] NOT NULL,         -- filters, e.g. {'payout.*','account.*'}
  secret_enc    TEXT NOT NULL,           -- field-encrypted
  secret_ver    INT NOT NULL DEFAULT 1,
  active        BOOLEAN NOT NULL DEFAULT true,
  retry_policy  JSONB NOT NULL DEFAULT '{"max_retries":8,"max_backoff_s":3600}',
  disabled_reason TEXT,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

Redis keys: `t:{ten}:idem:{m}:{p}:{k}` (24 h), `t:{ten}:rl:{scope}` (sliding
window ZSET), `t:{ten}:cfg:*` (tenant config), session deny-set (AUTH),
relay lock is PG-side.

## 10. Security & compliance

- Ingress webhooks are the platform's most-attacked surface: allow-listed paths
  only, per-provider signature verification before any parsing, size caps 256 KB,
  no introspection of unknown providers (404), all verified + failed attempts
  logged (AUD: `security.webhook_ingress`).
- Outbound: secrets encrypted; URLs validated (https, no IP literals, no internal
  ranges — SSRF guard on Hook0 side + our pre-check); per-tenant throttle;
  signing mandatory (no unsigned deliveries).
- Replay is a **sensitive console action**: 2FA + audit (`security.replay`) +
  seq-range validation (no full-tenant replay without CON super-admin).
- Idempotency bodies: store body **hash** only (not the body) — no PII parked in
  Redis.
- Correlation ids make every request/event chain traceable in a breach (EVT-28).

## 11. Scalability considerations

| Surface | Design | Headroom |
|---|---|---|
| Middleware chain | < 2 ms overhead (cached tenant config, JWKS/session deny-set in Redis) | 2k req/s per instance; add instances (stateless) |
| Idempotency | Redis SETNX + 24 h TTL; ~2 MB RAM per 10k keys — trivial | — |
| Outbox poll | keyset + SKIP LOCKED; 500/batch; publish in one XADD batch (pipeline); `NOTIFY` doorbell wake-up (§3.3 step 5) → publish latency p95 < 10 ms after commit | target **60k events/min sustained** (1k/s — the D79 V2 `bridge.tick` burst point ≤ 1k/s + other topics; sustained ticks ≤ 250/s, docs/63 §4.4); measured in the 29 §6 load test |
| Streams | per-topic streams; MAXLEN ~100k; consumer groups | 2k msg/s fine on Redis with AOF everysec |
| Ordering | per-entity lanes (hash) | no global ordering — documented |
| DLQ | per-consumer stream + CON screen | DLQ depth alert > 100 |
| Replay | from PG `events` — O(range), no stream scan | 13-month window |
| Failure: relay down | outbox accumulates (bounded by tx rate); **trading continues** (bridge→PG direct for enforcement-critical paths — sync ticks are PG writes, events are derived) — but **evaluation pauses** (EVL consumes `bridge.tick` via the relay; docs/63 F6) | RTO for relay = restart (< 1 min); `bridge`-topic lag CRITICAL at 30 s |
| Failure: Redis down | GW: authn falls to PG (degraded); rate limits fail-open with alert; EVT: relay pauses (outbox accumulates) | the failure rows above + 29 §6 load numbers |

## 12. Open-source solutions

| Option | Verdict |
|---|---|
| **Hook0** (self-hosted webhook delivery) | **CHOSEN** for outbound (EVT-11/13/14/15; AGPL review done — self-hosted OK) |
| Kafka / NATS JetStream | **Forbidden/consider-later** (ADR-7); Redis Streams for V1–V2 |
| Outbox alternatives (PG NOTIFY, CDC/Debezium) | Rejected as transport: NOTIFY no replay; Debezium = extra infra, more moving parts. NOTIFY **is** used as the relay's payload-free wake-up doorbell (§3.3 step 5, D79) |
| Kong/Traefik | Forbidden (ADR-4) |
| Apifox/Scalar (OpenAPI hosting) | Scalar for the docs site rendering (CMS), contract served by api |
| BullMQ | Used only for JS-side cron (docs-worker jobs); not the event bus |

## 13. Technology stack

Go (`api` middleware package, `relay` service, `workers` consumers), Redis 7
(streams + idempotency + rate limits), Postgres (outbox/events), Hook0,
Flipt (maintenance flag), Cloudflare (edge), Prometheus (relay lag, DLQ depth,
IdP-sync lag/stall, rate-limit hits), Sentry (consumer crashes), Uptime Kuma from the standby host + the external checker (D57, docs/57) (probe `/readyz`).

## 14. Integration — internal modules (glue)

| Module | How |
|---|---|
| Every domain | writes via `tx.Events()` (outbox); consumes via declared consumer; registers error codes + sensitive routes at build time |
| AUTH | supplies authn (step 3) + authz (step 4); `user.suspended` → GW deny-set |
| TEN | resolution source, quotas, entitlements, `suspended` |
| AUD | audit write on sensitive routes (step 11) + gateway security events |
| ANA | read-model consumers for `account.*`, `payout.*`, `checkout.*` |
| NOT | notification dispatcher consumes domain events → channels |
| BRG | ingress webhooks (MetaApi) + `bridge.*` events source |
| KYC/CHK/PAY | ingress webhook adapters; provider events → domain events |
| CON | relay/DLQ/replay screens; maintenance toggle |
| MIG | replay used for cutover verification (MIG parallel-run) |

## 15. Integration — external tools

MetaApi, Veriff, NOWPayments, Match2Pay, Interkasa (ingress), Hook0 (outbound),
Cloudflare (edge), Prometheus/Grafana, Sentry, Uptime Kuma (standby-hosted — D57, docs/57), Flipt.

## 16. Implementation blueprint

| Step | Owner | Est | Depends | Exit criteria |
|---|---|---|---|---|
| 1. Outbox + envelope + `tx.Events()` helper in go-shared | BE-1 | 2 d | OPS, DB | unit: event exists iff tx commits |
| 2. Relay service + lock + pruning + metrics + `dlq list/retry/purge` subcommand (D47) | BE-1 | 3 d | 1 | kill relay 5 min → restart → zero events lost, zero dupes; a poisoned event is retried/purged via the CLI with an AUD row |
| 3. Event log table + partitioning + retention job | BE-1 | 1 d | 2 | 13-month retention verified by test clock |
| 4. Consumer framework (groups, DLQ, backoff, idempotency, lanes) + supervisor | BE-2 | 4 d | 2 | chaos test: consumer crash mid-batch → no loss, no dup side effects |
| 5. GW chain steps 1–9 + error contract + envelope + pagination | BE-1 | 5 d | AUTH, TEN | contract tests: every registered route returns registered codes only |
| 6. Idempotency + rate limits + quotas + entitlement gate + maintenance | BE-1 | 3 d | 5, TEN | idempotency replay returns identical body; suspended tenant 403 in < 1 s |
| 7. Ingress webhook framework + MetaApi + Veriff adapters (V1 set) | BE-1 | 4 d | 5, BRG/KYC/CHK adapters exist | replayed provider payload → exactly-once domain effect |
| 8. Correlation propagation + structured logging + redaction | BE-2 | 1.5 d | 5 | a login → purchase → sync chain shares one correlation id across logs+events |
| 9. V2: outbound webhooks (Hook0, ADM manager UI, test/replay, rotation) | BE-2 + FE-1 | 6 d | 7 | tenant receives signed payout events in staging; rotation works |
| 10. V2: DLQ console, replay CLI/UI, observability dashboards (EVT-21/27/35) | BE-2 | 3 d | 4, 9 | operator can replay a seq range from CON with 2FA |
| 11. V2: sandbox mode, batch endpoint, response caching, deprecation headers | BE-1 | 4 d | 5 | — |

**Risks:** relay as single point (mitigation: outbox is durable + restart is the
fix + bridge enforcement doesn't depend on events); Redis flush losing
idempotency (mitigation: keys are cheap to re-derive; consumers are idempotent on
`event_id` anyway); webhook SSRF (mitigation: Hook0 allow/deny + our pre-check +
no internal ranges).

# 55 — Gateway (GW): The 11-Step Chain — Solution Specification

> The developer-facing **how-to-build** for the binding middleware chain in
> [04-gateway-events](04-gateway-events.md) §3.1 and
> [contracts/api/gw.md](../contracts/api/gw.md). Where those texts say
> *what* must happen (codes, numbers, order), this spec says *how* to build
> it: algorithms, data structures, key layouts, failure behavior, latency
> budgets, tests, and build order. Binding text is quoted, never changed.
> Implementation-level choices made below the contract line are tagged
> **SOL-nn** and registered in §12 — anything there that needs owner
> ratification is flagged in place. (None outstanding: SOL-04/06/07 were
> approved by the owner on 2026-09-20 and are now **D48–D50** in the
> decision register.)

Status: SOLUTION SPEC — normative for implementation of the GW chain
Owner: TBD (Platform)
Version: v1
Last updated: 2026-09-20

---

## 0. The short version in plain words

Every request to the platform passes through one checkpoint before it
reaches the real work code — like airport security with eleven desks in a
fixed order. Nobody skips a desk and the order never changes. This file
tells a developer how to build each desk.

| Desk | Plain name | The question it answers |
|---|---|---|
| 1 | Front-door check | "Did this really come through our front door (Cloudflare)? What is your true internet address?" |
| 2 | Which firm | "Which firm's address did you type? We only serve firms we know." |
| 3 | Who are you | "Prove it — a login token, a session cookie, or a secret we gave to another machine." |
| 3.5 | May you act right now | "Is your account blocked? Is the firm suspended or not open for business yet?" |
| 4 | Are you allowed | "Does your role include this action? For dangerous actions, did you confirm your identity in the last 5 minutes?" |
| 5 | Slow down | "Are you asking too much, too fast? This stops spam and password guessing." |
| 6 | Is it in your plan | "Does this firm pay for this feature? Is it within its fair-use limits?" |
| 7 | No double work | "If you press submit twice by accident, the work happens once and you get the same answer twice." |
| 8 | Tracking number | "Every request gets an ID that shows up in every log, event and reply, so we can follow it end to end." |
| 9 | Safety checks | "Is the request too big? Is it stuck? Are secrets kept out of the logs?" |
| 10–11 | Do the work, answer the same way | "The business code runs; every success and every error uses the same fixed shapes." |

Three things underneath can break: the fast cache store (Redis), the main
database (Postgres), and the login service. The rule the owner approved on
2026-09-20 (**D48**): normal pages keep working with slightly old data, and
anything touching money stops safely — pausing a payout for a minute beats
paying twice. A broken cache must never look like "this firm is suspended";
a wrong reason gets the wrong fix.

Two smaller rulings approved the same day: **D49** — if a client retries
while its first copy is still running, it gets the standard "already being
handled" error (409) instead of the server waiting for it; **D50** — any
unexpected crash answers 500 with the code `gw.internal`, the only
"something broke on our side" code the platform will ever show.

The rest of this file is the precise version, for the engineers building it.

---

## 1. How to read this spec

- **Binding sources** (win over this spec wherever they differ):
  [docs/04 §3.1](04-gateway-events.md) (chain order + step behavior),
  [contracts/api/gw.md](../contracts/api/gw.md) (request/response contract),
  [docs/47 §5](47-multi-tenancy-model.md) (route classes, state × surface ×
  code), [docs/44 §7](44-auth-multitenancy-review.md) (status gate, internal
  plane, token rule G31), `contracts/errors/taxonomy.md`
  (the only allowed error codes), [docs/33 §entitlements](33-glossary.md) +
  [docs/32](32-database-design.md) (entitlements, api_keys, audit_events).
- **MUST / SHOULD / MAY** per RFC 2119. "Binding" = already decided in the
  docs above; "SOL-nn" = decided *here*, at the implementation layer.
- A working, dependency-free reference implementation of everything in this
  spec lives at `pf-platform/go/gw/`
  (module `pfgw`, 18 tests, `verify.sh`); §11 maps each spec section to its
  file and tests. The reference is a *scaffold for learning the semantics* —
  production swaps the backed-by-Redis/PG implementations listed per step.
- This spec deliberately does **not** re-litigate architecture: the gateway
  is **in-app middleware behind Cloudflare** (BVR-12, ADR-4; standalone
  gateway products were evaluated and excluded — docs/04 §12).

## 2. The problem, precisely

One multi-tenant API serves five surfaces with **different trust levels,
different failure semantics, and shared money**:

| Surface | Prefix | Realm (authn) | Typical caller | Money at stake |
|---|---|---|---|---|
| Trader portal | `/v1/auth/*`, `/v1/trader/*` | email+password → JWT (AUTH-07) | retail trader on a hosted firm domain | order placement, payout requests |
| Tenant admin | `/v1/admin/*` | staff JWT + TOTP 2FA (AUTH-09) | firm operators | payouts approve, KYC/CHK queues |
| Platform console | `/v1/console/*` | separate session realm, Super Admin + mandatory 2FA (CON-01, AUTH-16) | platform staff | tenant suspension, refunds |
| Provider webhooks | `/v1/webhooks/*` | provider signature (EVT-10) | PSP / KYC vendor machines | payment truth path (CHK-07, KYC-05) |
| Service-to-service | `/internal/*` | static per-service bearer (SOPS) | web, workers, relay on the compose network | commands, engine sync |

Every request must get **eleven decisions** applied in one fixed order —
edge trust, tenant, authn, status, authz, rate, quota, idempotency,
correlation, hygiene, response shape — while satisfying four hard
constraints:

1. **Contract rigidity.** Every error is exactly `{code, message,
   correlation_id}` (GW-18) with a code from the taxonomy; every success is
   `{data, meta{request_id, version[, pagination]}}` (D45). A leaked
   non-registered code fails CI (`error_registry_test`, docs/04 §6.2).
2. **Tenant isolation.** No request executes without tenant context
   (GW-02); a valid token for firm A must be worthless on firm B's host.
3. **Abuse resistance.** Login brute force, payout spam, key-reuse replay
   and body bombs all fail cheap, at the right layer, with the right code.
4. **Latency.** The chain is on every hot path; the app-side overhead budget
   is **≤ 5 ms p99** excluding the handler (SOL-15 budget table).

The engineering difficulty is not any single step — it is that the steps
interact (idempotency needs correlation needs tenant; rate keys need authn
output; the error envelope needs correlation before tenant exists), and that
each dependency (Redis, PG, ZITADEL, Flipt) can be down independently.
§3.6 gives the per-dependency degradation contract; each step section gives
its own failure modes.

## 3. Solution architecture

### 3.1 Topology

```
                    Internet
                       │
              ┌────────▼─────────┐
              │   Cloudflare     │  TLS, WAF/DDoS, per-IP edge rate limit,
              │   (GW-20/33)     │  bot rules. Origin = api only.
              └────────┬─────────┘
                       │ HTTPS (CF published CIDRs only)
              ┌────────▼──────────────────────────────────────────┐
              │  api service (compose network)                    │
              │  ┌─────────────────────────────────────────────┐  │
              │  │ PUBLIC LISTENER :8080                       │  │
              │  │  GW chain steps 1..11 (this spec)           │  │
              │  │  route table → domain handlers              │  │
              │  └─────────────────────────────────────────────┘  │
              │  ┌─────────────────────────────────────────────┐  │
              │  │ INTERNAL LISTENER :8081 (compose net only)  │  │
              │  │  /internal/* : step 3 (service bearer)      │  │
              │  │  + X-Tenant-Id, steps 3.5..11 identical     │  │
              │  └─────────────────────────────────────────────┘  │
              └───┬───────────┬───────────┬───────────┬───────────┘
                  │           │           │           │
             ┌────▼───┐  ┌────▼───┐  ┌────▼───┐  ┌────▼────┐
             │  PG    │  │ Redis  │  │ZITADEL │  │  Flipt  │
             │system  │  │rate/   │  │JWKS/   │  │maint.   │
             │of      │  │idem/   │  │OIDC    │  │flag     │
             │record  │  │gates/  │  │        │  │         │
             │        │  │sessions│  │        │  │         │
             └────────┘  └────────┘  └────────┘  └─────────┘
```

**SOL-02 (two listeners).** `/internal/*` is *never edge-routed* (binding).
Enforce it with network position, not a path check: the api process binds a
**second listener on :8081 attached only to the compose network** (no
Cloudflare route, no DNS, no published port). The public listener returns
`404 tenant.unknown_host` for any `/internal/*` path without executing the
chain (the path itself is unauthenticated knowledge — OpenAPI is public,
GW-15, but internal routes are not in OpenAPI and must not even 401 from the
public side). The internal listener runs steps 3.5..11 identically, resolves
the tenant from `X-Tenant-Id` (docs/44 §7 G28), and skips steps 1–2.

### 3.2 The middleware model (SOL-03)

The chain is N pure middlewares of signature
`func(http.Handler) http.Handler` around one domain handler, built **from a
single declarative route table** (SOL-20):

```
Route := { pattern, method, class,          // docs/47 route class
           key,        scope,               // GW-04 permission key, "all"|"own"
           stepUp,     idem,                // D38 step-up, GW-12 idempotency
           audit,      module }             // GW-17 audit flag, docs/33 module
```

The route table is the single source of truth: the chain builder, the
served OpenAPI (GW-15), the permission-registry cross-check (a route key
missing from `contracts/permissions/registry.md` fails CI), and the audit
flag registration all derive from it. No route exists that is not a table
row.

**Context contract.** Steps communicate only through typed request-context
values — `correlation_id`, `client_ip`, `tenant_id`, `principal`, `route` —
and never by reading a later step's output or mutating shared state. Every
step either (a) enriches the context and calls `next`, or (b) terminates
with the GW-18 envelope through the **single error funnel** (§4.12). No
step writes a response directly.

### 3.3 Why the chain is in-process (one paragraph, settled)

The binding decision is docs/04 §3.1 + contracts/api/gw.md ("in-app
middleware behind Cloudflare — BVR-12: no standalone gateway product";
ADR-4). The eleven steps split into two families: **edge-family** (TLS, WAF,
per-IP rate) belong to Cloudflare and are configured, not coded; **business
family** (tenant, status, permission keys, entitlements, idempotency,
envelope) have no off-the-shelf equivalent because they read platform state
(tenants, memberships, plans, idempotency claims) with sub-millisecond
budgets. docs/04 §12 records the excluded alternatives. This spec implements
the binding shape.

### 3.4 Latency budget (SOL-15)

App-side overhead per request (p50 / p99), excluding the domain handler —
total budget **≤ 5 ms p99**:

| Step | Mechanism | p50 | p99 | Notes |
|---|---|---|---|---|
| 1 edge handoff | CIDR set membership (in-proc bitmap) | <0.01 | 0.01 | CF ranges refreshed 24 h |
| — maintenance flag | in-proc cached 5 s | <0.01 | 0.01 | Flipt behind cache |
| 2 tenant resolve | in-proc LRU hit (≈100%) | 0.005 | 0.05 | miss → Redis → PG |
| 3 authn JWT | EdDSA/RS256 verify + deny-set Redis MGET | 0.6 | 1.5 | JWKS cached 15 min |
| 3 authn session | Redis GET | 0.3 | 1.0 | console realm |
| 3.5 status gate | in-proc hit (5 s cache) | 0.01 | 0.4 | miss → Redis → PG |
| 4 authz | in-proc Casbin enforce | 0.02 | 0.1 | model in memory |
| 5 rate | Redis EVAL (1 round trip) | 0.3 | 1.2 | GCRA / fixed window |
| 6 quota/entitlement | in-proc cache hit | 0.01 | 0.3 | miss → Redis → PG |
| 7 idempotency (writes w/ key) | Redis SET NX + SET | 0.6 | 2.0 | 2 round trips |
| 9 hygiene | length check + wrapper | <0.05 | 0.1 | — |
| **Total (read path)** | | **≈1.0** | **≈3.7** | |
| **Total (idem write path)** | | **≈1.6** | **≈5.7** | idem routes only |

### 3.5 Cache and invalidation summary (SOL-10)

| What | Where | TTL | Invalidated by |
|---|---|---|---|
| Tenant host → id | in-proc LRU (1k hosts) + Redis | 60 s pos / 10 s neg | `tenant.activated`, `tenant.host_changed` (pub/sub) |
| Status gate (tenant / identity / membership) | in-proc + Redis | **≤ 5 s** (binding, docs/44 §7) | `user.suspended`, `user.activated`, membership events |
| Entitlements per tenant | in-proc + Redis | 60 s | `entitlement.changed` |
| JWKS (ZITADEL signing keys) | in-proc | 24 h + refresh-on-unknown-kid (docs/02 §9 — binding; docs/56) | — |
| Rate/step counters | `redis-main` (D51, docs/06 §2.6) | window length | TTL |
| Idempotency claims/results | `redis-main` (D51, docs/06 §2.6) | 24 h (binding GW-31) | TTL |
| Maintenance flag | in-proc | 5 s | TTL (fast enough for a human-scale switch) |
| Revocation deny-set | Redis only | jti = access-token TTL (15 min); session-keyed entries outlive the refresh idle window (docs/02 §9 — docs/56) | write-through on revoke |

Pattern: **Redis pub/sub fan-out → each api instance drops its in-proc
entry**; every cache entry also carries its TTL as the upper bound, so a
lost pub/sub message is bounded by the TTL. No cache is authoritative.

### 3.6 Dependency degradation contract (SOL-04)

Each dependency fails independently; behavior is fixed **per step, per
class** and is part of the tests (§9):

| Dependency down | Step 2 resolve | Step 3 authn | Step 3.5 gate | Step 5 rate | Step 6 quota | Step 7 idempotency |
|---|---|---|---|---|---|---|
| **Redis down** | fall through to PG (cache only) | deny-set unverifiable → accept JWT (15-min tokens bound the exposure); sessions (console) fail-closed `401` | **serve stale ≤ 30 s** (5 s TTL + stale window), then `500 gw.internal` + page | default+auth classes **fail-open** + CRITICAL alert (edge per-IP still guards); payout class **fail-closed** (`429 rate.limited`, Retry-After 60) | serve stale ≤ 5 min, then fail-closed `403 tenant.not_entitled` | **fail-closed** `500 gw.internal` on money routes — never execute an untracked money write + CRITICAL |
| **PG down** | fail-closed `500 gw.internal` (cannot know the tenant) | JWKS is in-proc → authn still works | fail-closed `500 gw.internal` | unaffected | fail-closed `500 gw.internal` | unaffected (Redis is the store) |
| **ZITADEL down** | — | verification works (cached JWKS, 15-min tokens); login/refresh degrade (out of GW scope, docs/02 §9) | — | — | — | — |
| **Flipt down** | — | — | — | — | — | — | maintenance flag serves **last known value** (off) |

Rationale: availability where the edge already protects (default rate),
safety where money or abuse resistance is at stake (payout rate,
idempotency). The matrix is exercised by the chaos tests in §9. When this
spec says "`500 gw.internal`", see SOL-07: the boundary code is the
registered `gw.internal` row pinned to HTTP 500 (ratified
2026-09-20 — D50).

## 4. The eleven steps — solutions

> Each section: **Binding** (what the docs fix), **Solution** (how),
> **Failure & security**, **Tests**, **Alternatives rejected**. Pseudo-code
> is Go-flavored; the reference implementation is cited by file.

### 4.1 Step 1 — Edge handoff (GW-20, GW-33, GW-32)

**Binding.** Trust Cloudflare; `CF-Connecting-IP` only if the CF proxy chain
is verified (GW-33); WAF/DDoS/per-IP live at the edge; maintenance flag
returns `503` + `Retry-After` for all non-probe routes (GW-32).

**Solution.**

1. **Client-IP recovery.** At boot, fetch Cloudflare's published IPv4/IPv6
   ranges; refresh every 24 h; compile into an in-proc CIDR set. Per
   request: take the TCP peer address; if it is inside the CF set, accept
   `CF-Connecting-IP` (parse; reject the request `400`-free by falling back
   to the peer if malformed — log + count). Otherwise the peer *is* the
   client. The result enters the context as `client_ip` and is the only IP
   any later step sees. Direct-to-origin scans (bypassing CF) therefore get
   their real socket IP, never a spoofed header.
2. **Security headers** (defense in depth; CF sets some too):
   `Strict-Transport-Security: max-age=31536000; includeSubDomains`,
   `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
   `Referrer-Policy: strict-origin-when-cross-origin`.
3. **Maintenance gate (GW-32).** Read the Flipt `maintenance_mode` flag
   through the 5 s cache. On: every route except `/healthz`, `/readyz`,
   `/internal/*` returns `503 gw.maintenance` + `Retry-After: 60`.
   Flipping the flag is the *only* supported "stop the world" control; it
   must not require a deploy.

**Failure & security.** CF range fetch failure at boot → start with an empty
set **and fail startup if `CF_TRUST_DISABLED` is unset** (better: refuse to
serve than trust spoofed headers). Malformed `CF-Connecting-IP` from a CF
peer → fall back to peer, increment `gw_cfip_malformed` counter.

**Tests.** Spoofed header from non-CF peer ignored; honored from CF peer;
malformed handled; maintenance on → 503 envelope on trader route while
`/readyz` stays 200.

**Alternatives rejected.** Trusting `X-Forwarded-For` chains (spoofable,
CF already normalizes to `CF-Connecting-IP`); path-based internal-route
protection alone (see SOL-02).

### 4.2 Step 2 — Host → tenant resolution (GW-02, TEN-02)

**Binding.** Resolve from domain/subdomain **before auth runs**; unknown →
`404 tenant.unknown_host`; no request executes without tenant context;
internal routes resolve from `X-Tenant-Id` instead.

**Solution.**

1. Normalize the `Host`: lowercase, strip port, reject empty; IDNA-decode
   punycode so `xn--` hosts compare equal to their UTF-8 form (a classic
   duplicate-host bypass).
2. Look up `tenants` by the **unique host column** through the two-level
   cache (§3.5): in-proc LRU → Redis `tenant:{host}` → PG. A hit puts
   `tenant_id` in the context. A miss (negative cached 10 s) →
   `404 tenant.unknown_host`, message exactly the taxonomy pattern.
3. The lookup selects **live tenants only for public resolution** — a
   `pending_approval` firm with a reserved-but-not-DNS host is unreachable
   by construction (docs/47: DNS is created by saga step 5). Hosts of
   pre-`active` tenants that somehow resolve fall through to step 3.5,
   which enforces `tenant.not_live` on trader surfaces.
4. Resolver interface (swappable): `ByHost(ctx, host) (tenantID, known, err)`;
   production = cached decorator over the PG query; reference =
   `MapResolver` + `CachedResolver`.

**Failure & security.** PG down → `500 gw.internal` (fail-closed: never
guess a tenant). Host header confusion (e.g. `firmA.example:8080`,
`FIRMA.example.`, Unicode forms) collapses to one key by normalization.
Enumeration of firm hosts is *possible by design* (DNS is public); the 404
reveals nothing beyond existence.

**Tests.** Unknown host 404 envelope; port/case/punycode normalization;
internal listener path skips this step; cache negative-TTL expiry lets a
newly-attached host appear within 10 s.

**Alternatives rejected.** Path-prefix tenancy (`/t/{slug}/...`) — breaks
the binding URL plan (D46); JWT-carried tenant only — fails "resolve before
auth" and makes tenant spoofable pre-auth; resolving per request from PG
with no cache — needless hot-path cost.

### 4.3 Step 3 — Authentication (GW-03, GW-16; docs/02; G31)

**Binding.** JWT (trader/staff) or console session verified on every
protected route; invalid → `401 auth.invalid_credentials`; internal routes
use static per-service bearers (SOPS, 90 d rotation, one per service);
API keys have primitives only in V1, no surface (D18). Tokens carry
**context, never authority** (G31): `sub`, audience/realm, `amr`,
`auth_time`, session id — never roles or verdicts.

**Solution.** The realm is derived from the URL plan (D46), never from
configuration:

| Prefix | Credential | Verification |
|---|---|---|
| `/v1/auth/*`, `/v1/trader/*` | `Authorization: Bearer` JWT, aud `trader` | ZITADEL RS256/EdDSA via cached JWKS; `exp/iat/nbf`; `sub` present; **deny-set check** (Redis `GET deny:jti` / `deny:sess:{sid}`, docs/02); `tenant_id` claim must equal the step-2 tenant (SOL-09) — mismatch = cross-tenant token = `401`, logged as a security event |
| `/v1/admin/*` | Bearer JWT, aud `staff` | same checks + `amr` contains mfa for step-up-flagged routes (D38, §4.5) |
| `/v1/console/*` | cookie `pf_console_session` (HttpOnly, Secure, SameSite=Lax) | opaque 128-bit id → server-side session in Redis (15-min sliding idle — the console realm's D66 carve-out, docs/02 §9); session holds the principal; no JWT on this realm |
| `/v1/webhooks/*` | provider signature | per-provider verifier registry (CHK-07, KYC-05, EVT-10): raw body read **before any parse**, HMAC (or provider scheme) verify, timestamp tolerance ±5 min, provider event id extracted for the dedupe the handler owns (`evt.webhook_duplicate` semantics). Failure → `401 webhook.signature_invalid` |
| `/internal/*` | static bearer (SOPS) | SHA-256 of presented token compared constant-time against boot-loaded hashes; service label becomes the principal (`kind=service`); every call logged with service identity + `correlation_id` (docs/44 §7). Rotation: dual-token overlap 24 h (SOL-19) |

`auth_time` (or ZITADEL's `amr` mfa evidence) is carried into the principal
as `MFAAt` — step 4's step-up consumes it; the gateway never *prompts*, it
only refuses with `403 authz.step_up_required`.

**Transport (D64, docs/59):** the browser realms present the HttpOnly session
cookie (the `auth_sessions` projection — docs/02 §3.3); machine clients
present the bearer JWT. Cookie-authenticated state-changing requests pass an
**origin check** (validate `Origin`/`Referer` against the request host)
before the realm logic — the docs/28 T8 CSRF defense; the reference scaffold
notes it as a production swap-in at the front of `Auth.Middleware`.

**Failure & security.** All realm failures return the **identical generic**
`401 auth.invalid_credentials` — no realm disclosure, no user enumeration
(login endpoint's identical-shape failure is the taxonomy's
enumeration-resistance rule). Missing auth on a route whose key requires an
identity → `401` from step 4 (the anonymous principal never passes authz).
The deny-set Redis failure path is fail-open **by design** (§3.6): access
tokens live 15 minutes, so worst-case exposure is bounded by the token
lifetime; console sessions are fail-closed (opaque 128-bit ids cannot be
verified locally).

**Tests.** Expired / wrong-aud / wrong-tenant / revoked-jti tokens → 401
envelope; console cookie absent/expired → 401; webhook signature bad /
stale timestamp / good → 401 / 401 / pass; service token on public listener
→ 404 (route hidden); constant-time compare verified by test vector.

**Alternatives rejected.** Putting roles into JWT claims (violates G31 —
stale on role change, bloated tokens); verifying webhooks after JSON
parse (signature must see raw bytes); accepting the tenant from the token
without comparing to the host-resolved tenant (cross-tenant hole).

### 4.4 Step 3.5 — Status gates (docs/44 §7 G29; docs/47 §5)

**Binding.** Check order **tenant → identity → membership** (console realm
skips membership); codes `tenant.suspended` / `tenant.not_live`
(`details.state` names the pre-active state) / `auth.account_suspended` /
`auth.membership_suspended`; cached in Redis ≤ 5 s keyed `(identity,
tenant)`, invalidated by `user.suspended` / `user.activated` / membership
events; **route-class aware**: `tenant.not_live` applies to trader-facing
routes only — an `onboarding` tenant's staff surfaces pass by design;
`tenant.suspended` denies every surface. The state × surface × code cell
set is `contracts/tenants/state-capabilities.yaml` (the I-20 test source,
gate 16).

**Solution.** One gate function, three ordered lookups, zero per-request PG
on the hot path:

```
gate(ctx, route):
  st_t = cache("t|"+tenant, 5s)            # tenant state
  if st_t == "suspended": 403 tenant.suspended          # every surface
  if route.class in TRADER_FACING and st_t not in {"active"}:
       403 tenant.not_live, details.state = st_t         # pre-active dark
  if principal.kind in {"user","staff"}:
    st_i = cache("i|"+principal.id, 5s)
    if st_i == "suspended": 403 auth.account_suspended
    if principal.kind == "user":
      st_m = cache("m|"+principal.id+"|"+tenant, 5s)
      if st_m == "suspended": 403 auth.membership_suspended
```

- **TRADER_FACING** = `{trader}` (+ `auth` for post-login surfaces per
  `state-capabilities.yaml` — the YAML is the oracle, the code is generated
  from it; gate 16 fails the build if they drift).
- Cache entries are three Redis keys per principal pair with 5 s TTL,
  plus an in-proc mirror; pub/sub events from the identity/tenant services
  drop both mirrors immediately (§3.5). Worst-case suspension propagation =
  one Redis round trip on the transition event (immediate) or 5 s (TTL
  bound) — meets the "≤ 1 s suspension" guarantee of docs/03 §5.1 via the
  event path, with the TTL as the safety net.
- Read path: warm cache = 0 round trips; cold = one Redis MGET.

**Failure & security.** Unknown/empty state values are treated as the
*most restrictive* for trader surfaces (`not_live`) and as pass-through for
staff surfaces only if the tenant is `active` — never invent states; the
DDL status list, the YAML, and this function are lockstepped by gate 16.
Redis down → stale ≤ 30 s, then `500 gw.internal` (§3.6) — **never** map an
infrastructure failure to a suspension code (that would lock a paying firm
out on a cache blip, and the wrong-code CI gate would catch it anyway).

**Tests.** The I-20 table-driven test is *generated* from
`state-capabilities.yaml`: every (state × surface) cell asserts the exact
code or pass; suspension invalidation event drops the cache; ordering
tenant-before-identity asserted by a fixture where both are suspended.

**Alternatives rejected.** One combined cache entry per `(identity, tenant)`
— hides which layer failed and complicates per-layer invalidation; checking
status inside authz — spreads the gate across handlers; no cache — 1–2 PG
queries on every request.

### 4.5 Step 4 — Permission-key authorization (GW-04, AUTH-13; ADR-14; D38)

**Binding.** Module-declared `resource.action` keys enforced per route;
denied → `403 permission.denied`; key registry
`contracts/permissions/registry.md`, role bindings `roles.yaml` seeded into
Casbin (D14/D15); engine behind `authorizer.Check`; console realm separate.

**Solution.**

1. **The check is one call:** `authorizer.Check(ctx, subject, route.key,
   scopeCtx)` → allow/deny. The embedded Casbin enforcer holds the compiled
   model in memory; `roles.yaml` version bumps are pushed by the build and
   hot-reloaded on publish event. The gateway never talks to Casbin's
   storage mid-request.
2. **Decision procedure** (in order, each denial = `403 permission.denied`
   unless stated):
   - route key empty → public route, pass (nothing to check);
   - key not in registry → **wiring bug**: deny closed + `gw_route_key_unknown`
     alert (this also fails CI at build time via SOL-20 — the runtime branch
     is a belt-and-braces);
   - principal is anonymous → `401 auth.invalid_credentials` (authn passed
     it through only because the route class allows anonymous *reach*; a
     keyed route is not one of them);
   - subject roles (from the DB-backed identity, loaded with the principal,
     **not** from the token — G31) intersect the key's role set? no → 403;
   - `scope=own` → route's `Own(req)` extractor returns the owner id; owner
     ≠ principal → 403 (cross-tenant *and* cross-user are the same refusal,
     same code, no detail);
   - `stepUp` (D38) → `MFAAt` within the last **5 min**? no → `403
     authz.step_up_required` (registered extended code); the client re-runs
     the OIDC mfa prompt and retries with a fresh `auth_time`.
3. Console realm has its own key namespace and never shares a key with
   tenant surfaces (CON-01).

**Failure & security.** Enforcer load failure at boot = fail startup (a
gateway without its policy table must not serve). Casbin panics are caught
by the boundary → `500 gw.internal`. Denials of **audited** routes are
audited (GW-17, §5.1) — the brute-force signal lives there.

**Tests.** Role matrix per registry (table-driven from `roles.yaml`);
own-scope pass/deny; step-up fresh vs stale boundary (exactly 5:00);
unknown-key deny + CI check; anonymous-on-keyed → 401.

**Alternatives rejected.** JWT-embedded roles (G31 violation); per-handler
`if role == ...` checks (unauditable, drifts from registry); OPA sidecar —
network hop on hot path for what is an in-memory table check (ADR-14 chose
embedded).

### 4.6 Step 5 — Rate limiting (GW-05, GW-29)

**Binding.** Edge per-IP at Cloudflare → per-user Redis **100 rpm default**
(tenant-plan adjustable) → per-route (auth **10 / 5 min**, payout **5 / h**);
denial → `429 rate.limited` + `Retry-After`.

**Solution.** Two algorithms, one Redis Lua script each, chosen per class:

| Class | Algorithm | Why |
|---|---|---|
| default (per-user, plan-adjustable) | **fixed window** `INCR rl:{tenant}:u:{user}:{epoch_min}` + `EXPIRE 120s` | cheapest; boundary burst ≤ 2× is acceptable where the cap is generous (100/min) and the edge smooths per-IP |
| auth (10 / 5 min) | **GCRA** (leaky bucket, O(1) state) | no boundary burst on a security-sensitive cap; exact `Retry-After` from the theoretical-arrival-time |
| payout (5 / h) | **GCRA** | money path: smooth 5/h, no 2× burst, precise retry hints |

- **Key selection:** authenticated → `u:{identity_id}` (per-user, binding);
  anonymous (login itself) → `ip:{client_ip}` from step 1. Keys are
  tenant-scoped for user keys (`rl:{tenant}:...`) since identity ids are
  tenant-local, and global for ip keys (an attacker's IP is global).
- **Limit resolution:** class caps are code constants (the binding table);
  the per-user default reads the tenant's plan limit from the entitlements
  cache (step 6 shares it), falling back to 100 rpm.
- **Denial:** `429 rate.limited`, `Retry-After` = ceil(seconds to next
  token / window reset), message per taxonomy. A `rate.scope` detail
  (`ip|user|route`) may be logged, not exposed.
- **Redis scripts** (one EVAL per request): fixed window =
  `INCR`+`EXPIRE NX`; GCRA = read TAT / compute / write TAT in one script —
  atomic without transactions.

**Failure & security.** Per §3.6: Redis down → default+auth fail-open with
CRITICAL `gw_ratelimit_open` (the CF per-IP edge limit remains the outer
guard — this is why the edge layer exists); payout fail-closed (a paused
payout for a minute beats an uncapped money spam). Distributed warmup: GCRA
state initializes on first hit (no cold-start penalty). Do NOT rate-limit
`/healthz`, `/readyz` (orchestrators poll), or webhooks (provider IPs are
shared; webhook protection is the signature + provider-side dedupe).

**Tests.** Boundary counts (n, n+1) per class; Retry-After arithmetic; GCRA
smoothness (no 2× burst); fail-open/fail-closed per class with Redis
refused; per-user isolation (two users, one capped, other unaffected).

**Alternatives rejected.** Sliding-window log (exact but O(n) memory per
key); token bucket in app memory (split-brain across replicas); per-IP
limits in-app (that is the edge's job — doing it here again would penalize
NATted offices and mobile CGNAT).

### 4.7 Step 6 — Tenant quota + entitlement (GW-06, GW-22, GW-23; docs/33)

**Binding.** Plan limits (RPM, concurrency) + module entitlement gate;
suspended tenant → 403 (already handled at 3.5 — this step is *not* the
suspension gate).

**Solution.** Two distinct checks, two distinct codes:

1. **Module entitlement** — `route.module` (docs/33 MOD codes) against
   `tenant_entitlements` (docs/32) via the 60 s cache. Not entitled →
   `403 tenant.not_entitled` (the V1 baseline code — contract-resolved
   2026-09-19: checked **here**, once, not per module). Absent row =
   not entitled (fail closed, add-on semantics).
2. **Plan quota (GW-22/23)** — per-tenant RPM and concurrent-request
   counters in Redis (same Lua family as step 5, keyed
   `q:{tenant}:rpm:{epoch_min}` and an `INCR/DECR` + TTL leaseset for
   concurrency). Exceeded → `429 gw.quota_exceeded` (registered extended
   code) + `Retry-After`, `details.metric` logged. This is the *firm-level*
   ceiling that no per-user limit can express.

Order inside the step: entitlement first (a feature the firm doesn't pay
for shouldn't consume quota counters), quota second.

**Failure & security.** Entitlement cache stale ≤ 60 s + event
invalidation (`entitlement.changed` from the billing consumer) — a plan
upgrade lands ≤ 60 s; a downgrade likewise (grace window, documented).
Redis down → serve entitlement stale ≤ 5 min then fail-closed; quota
counters fail-open with alert (per-user limits still active). A tenant at
quota gets `429` — never a silent queue (backpressure must be visible to
the firm's integrators).

**Tests.** Entitled / not-entitled / absent-row; quota boundary; upgrade
invalidation latency < 60 s; concurrency lease decremented on
early-response paths (timeouts too — the lease is `context`-scoped).

**Alternatives rejected.** Per-module entitlement middleware scattered in
handlers (the contract explicitly centralizes it here — 2026-09-19
resolution); hard-failing on stale entitlement cache (needless outage
coupling to Redis).

### 4.8 Step 7 — Idempotency (GW-12, GW-31, GW-37)

**Binding.** `X-Idempotency-Key` (UUIDv4) on mutating requests; scope
`(tenant, method, path, key)`; Redis `SETNX t:{ten}:idem:{method}:{path}:{key}`
TTL 24 h; stored result replayed **verbatim** (same status); same key with
different body hash → `409 request.idempotency_conflict`; **body stored as
hash only**.

**Solution.** A two-phase lifecycle on one Redis key (value = small JSON,
TTL 24 h):

```
Phase 1 — claim (SET NX):
  rec = {st:"inflight", hash: sha256(body), exp: now+15m}
  SET t:{ten}:idem:{method}:{path}:{key} rec NX EX 86400
  ├─ NX lost, stored.hash != hash ............ 409 request.idempotency_conflict
  ├─ NX lost, stored.st == "inflight" ....... 409 (concurrent duplicate; SOL-06)
  ├─ NX lost, stored.st == "done" ........... REPLAY: stored status + body
  │                                           verbatim + X-Idempotent-Replay: true
  └─ claimed → execute handler

Phase 2 — commit (after response, status < 500):
  SET same key {st:"done", hash, status, body≤1MB, ct} EX 86400-elapsed
  (5xx and crashed requests are NOT committed → the key stays "inflight"
   until its 15-min lease dies, then a retry re-executes cleanly)
```

- **Scope discipline:** `path` is the *route pattern*, not the raw URL with
  ids — `/v1/trader/payouts/{id}` retries against the same id. Method and
  tenant are part of the key (binding scope) so a key collision across
  firms or verbs is structurally impossible.
- **Privacy:** the request body never persists — only its SHA-256 (the
  binding "hash only" rule, privacy-reviewed). Response bodies are stored
  to make replays verbatim; they are the client's own data, tenant-scoped,
  24 h TTL.
- **In-flight duplicate = 409** (SOL-06): a client retrying without waiting
  gets a definitive "same key is being processed" and backs off; after the
  first completes it gets a clean replay. This keeps V1 free of
  cross-request waiting (pub/sub notify) which Stripe-style race recovery
  would need.
- **Where it applies:** routes flagged `idem` in the route table (money
  writes: payout create, order create, challenge actions). The header is
  optional by wire format; client contracts *require* it on those routes
  (docs per module). The gateway does not invent a 4xx for a missing key —
  the route's contract does that in docs.
- **Durability honesty:** Redis `redis-main` (the durable container — D51, docs/06 §2.6) with AOF `everysec` + replica. Worst case
  (lose the key between claim and commit) a client retry re-executes — the
  exact scenario idempotency exists to prevent — but bounded: AOF loses ≤ 1
  s of writes, and commit happens within one handler run. A PG-backed store
  (same interface) is the V2 upgrade if audit requires stronger guarantees;
  the binding store for V1 is Redis (docs/04 §3.1 step 7).

**Failure & security.** Redis down on an `idem` route → fail-closed
`500 gw.internal` + CRITICAL (never execute an untracked money write);
non-idem routes unaffected. Key validation: must parse as UUIDv4 (binding
format); malformed → treated as absent (route contract governs), never a
500. **Never** store raw bodies; log the key's hash prefix only (a key is
also a semi-secret — knowing one lets you force a 409).

**Tests.** First/replay/conflict triple; concurrent duplicate → 409;
5xx not remembered (retry re-executes); crash between phases (kill the
store between SETs — lease expiry recovers); hash-only assertion (store
introspection: no raw body bytes present); verbatim replay byte-equality.

**Alternatives rejected.** PG unique-constraint claim (more durable but
binding says Redis; V2 option behind the same interface); returning
`425 Too Early` for in-flight (unregistered code — CI gate); client-supplied
scope (breaks the binding scope tuple).

### 4.9 Step 8 — Correlation (GW-09, GW-36; docs/49 C1; AUD-01)

**Binding.** Inbound `X-Correlation-Id` or a new ULID; propagated to logs,
events (`correlation_id`), engine calls, webhooks; error envelope and
`audit_events.correlation_id` carry it; workers mint one per job.

**Solution.**

- **Adopt-or-mint:** inbound header accepted iff it matches
  `^[0-9A-Za-z-]{8,64}$` and has no whitespace/control chars (Crockford
  ULIDs pass; arbitrary edge-generated opaques pass; junk is replaced).
  Otherwise mint a **ULID**: 48-bit ms timestamp + 80 bits `crypto/rand`,
  Crockford base32 — lexicographically sortable, log-friendly,
  collision-free at platform scale.
- **Chain position (SOL-01 — position clarification):** the binding table
  lists correlation at slot 8, but *every* early error (step 2's 404, step
  3's 401) must already carry `correlation_id` (GW-18 says the envelope
  always has it). Therefore **adopt-or-mint is the first code that runs
  (position 0, before step 1)**, while the *slot-8 duties* — verifying
  propagation to events/audit/engine — are the step-8 checkpoint. No
  security decision moves; correlation is stateless and makes no decisions.
  The binding table's decision order (2…9) is untouched.
- **Propagation contract** (each row is a MUST for the named emitter):

| Emitter | Carried as |
|---|---|
| every response (success + error) | `X-Correlation-Id` header; `meta.request_id` (D45); `correlation_id` (GW-18) |
| access log | `correlation_id` field (JSON line, §5.2) |
| `audit_events` | `correlation_id` column (AUD-01) |
| event envelope (outbox → Kafka) | required `correlation_id` field (docs/49 C1 — schema-enforced) |
| engine/bridge calls | metadata header on the internal call + log line |
| workers | per-job mint when the job originates a unit of work (docs/54 resolution) |

**Failure & security.** None — stateless. Do not accept > 64-char junk
(log-spam via header bloat is capped by the header size limits at the
edge); do not log the correlation id *as* the Sentry event id (they
correlate, they are not equal — SOL-07).

**Tests.** Adopt/mint/replace triple; envelope + header + log field
equality on error *and* success; ULID format + monotonic-ms sanity.

**Alternatives rejected.** UUIDv4 (unsortable, log-hostile); accepting the
inbound value unvalidated (header injection into logs).

### 4.10 Step 9 — Hygiene (GW-13, GW-35, GW-26)

**Binding.** Body ≤ 1 MB (uploads 10 MB via presigned R2 — GW-26); handler
timeout 10 s; sensitive header redaction in logs (GW-35).

**Solution.**

1. **Body limit, two moves:** if `Content-Length > 1 MiB` → `413
   gw.payload_too_large` before reading a byte; else wrap the body in a
   streaming 1 MiB reader so chunked bodies are cut off mid-read (the
   reader's error maps to the same 413). File uploads never traverse the
   chain — clients get presigned R2 URLs (GW-26); the GW never proxies 10 MB.
2. **Handler timeout (10 s):** race the handler against a timer; on timeout
   emit `504 gw.timeout` (a *shaped* envelope, never the edge's default
   502 page). The handler goroutine is abandoned, not killed; upstream
   calls made with the request context terminate themselves. A response
   already started suppresses the 504 (you cannot unwrite bytes; the log
   records `timeout_after_headers`).
3. **Redaction (GW-35):** the access log never carries `Authorization`,
   `Cookie`, `Set-Cookie`, or any `X-Api-*` header value; the logger's
   header serializer replaces them with `[REDACTED]`. Idempotency keys log
   as first 8 chars + length (§4.8).
4. **Method guard:** a route registered for one method answers `405
   gw.method_not_allowed` for any other, placed **before authn and rate**
   (SOL-12) so wrong-method probes cost nothing — route existence is public
   via OpenAPI, so this hides nothing and saves budget.

**Failure & security.** Body-limit double-check protects the parser layer
even when a handler forgets to bound reads. The timeout budget belongs to
the whole chain-after-step-9; steps 1–8 costs are not charged to the
handler (they are the platform's own latency). Slowloris-style body drips
are bounded by the edge's connection limits + this reader (a stalled body
hits the same 10 s race).

**Tests.** Oversized Content-Length 413; chunked oversize 413; timeout →
504 envelope with correlation; redaction unit test over a hostile header
set; 405 before rate (11 wrong-method calls → no 429).

**Alternatives rejected.** `http.TimeoutHandler` (its 503 body is not
GW-18-shaped); killing handler goroutines (unsafe in Go; ctx cancellation
is the coordinated exit).

### 4.11 Step 10 — Handler contract (domain packages)

**Binding.** "domain package" — the chain's job ends; business logic begins.

**Solution (the contract every handler MUST satisfy):**

1. Receive everything from the context: `correlation_id`, `tenant_id`,
   `principal`, `route` — never re-parse headers (single source, testable).
2. Write **only** through the envelope helpers (`WriteSuccess`,
   `WriteCreated`, `WritePage`, `WriteError`) — a lint rule + contract test
   fail on raw `w.Write`/`w.WriteHeader` in handler packages.
3. Return domain errors as typed values that map to **registered codes**;
   the funnel (§4.12) renders them. A handler that invents a code string
   fails CI (registry test scans handler packages for code literals not in
   the taxonomy).
4. Emit state changes transactionally: business row + outbox row in **one
   PG transaction** (docs/04 §3.2) with `correlation_id` in the event
   envelope — the GW's correlation propagation ends here, the event's
   begins.
5. Webhook handlers re-verify nothing (step 3 did), dedupe on provider
   event id (`evt.webhook_duplicate` → idempotent 200), and must be fast —
   persist-and-ack, process async.

### 4.12 Step 11 — Response envelope & the error funnel (D45, GW-18, GW-21, GW-29)

**Binding.** Success `{data, meta{request_id, version[, pagination{cursor,
has_more}]}}`; errors exactly `{code, message, correlation_id}`; cursor
pagination `?limit≤100&cursor=`; `Retry-After` on 429; `Deprecation`/
`Sunset` headers are V3.

**Solution.**

- **Three sanctioned writers** (`WriteSuccess`, `WriteCreated`, `WritePage`)
  plus the **single error funnel** `WriteError(code)`:
  - funnel looks up `(status, message-pattern)` from a table **generated
    from the taxonomy** at build time — a code missing there is a compile/CI
    error, and an unknown code at runtime collapses to the boundary
    (SOL-07), never echoed;
  - `meta.request_id` = correlation id, `meta.version` = `"v1"`;
    `pagination` present **only on list responses** (docs/54 D45: it is
    omitted, not null, elsewhere);
  - 429s carry `Retry-After` (set by step 5 / quota before the funnel runs).
- **SOL-07 (the boundary):** for panics and any unregistered failure, the
  last-resort response is `500` + code `gw.internal` + message
  "Something went wrong on our side." + `X-Sentry-Event-Id: {event id}`.
  The taxonomy registers `gw.internal` as the generic failure row but its
  HTTP cell was "—" (a UX mapping); **this spec pins it to 500 —
  ratified 2026-09-20 as D50, and the taxonomy UX row now carries 500**
  (the alternative — inventing a
  new `gw.internal_error` code — would fail the registry gate the docs
  define). Panics are recovered per request, Sentry-captured with the
  correlation id attached, and counted.
- **Envelope shapes are contract tests**, not conventions: a fixture
  decodes every route's success/error fixture and asserts key sets exactly
  (`{data, meta}`; `{code, message, correlation_id}` — no `details` in V1).

**Tests.** Envelope key-set equality per route class; generated code→status
table compiles; unknown-code collapse; Retry-After present on all 429
paths (rate, quota); pagination block absent on non-lists.

## 5. Chain-external rows (binding table, unnumbered)

### 5.1 Audit flag (GW-17; docs/50)

Routes flagged `audit` write `audit_events` on **success and failure**.
Success-path audits are written **in the same PG transaction** as the
business change (AUD-01 pattern, docs/05) — a business change without its
audit row is impossible by construction, and an audit failure aborts the
business write. Failure-path audits (denied sensitive actions) are written
asynchronously via the outbox with a P1 alert on write failure (docs/50:
silent audit loss is a P1) — never "best-effort silent". Each record carries
actor, tenant, route key, outcome, and `correlation_id`; per-route `AUD-##`
action codes attach when those routes are wired (docs/50).

### 5.2 Probes (GW-14), OpenAPI (GW-15), access logs

- `/healthz` — liveness, always 200 if the process serves.
- `/readyz` — PG ping + Redis ping + **relay lag < 60 s**; any failure →
  503 JSON `{status:"fail", failed:[...]}`; excluded from maintenance,
  rate limits, and authn. Orchestrators pull the instance on fail.
- `/v1/openapi.json` per route group — generated from the route table
  (SOL-20), unauthenticated, cached at the edge.
- Access log: one JSON line per request `{ts, method, path, status,
  duration_ms, correlation_id, client_ip, tenant, principal, route,
  rate_scope, error_code}`; headers only via the redacting serializer
  (GW-35). This line is the HTTP plane's half of correlation; the event
  plane's half is the envelope field (docs/49 C1).

## 6. End-to-end walkthroughs

**Trace A — happy path, money write.** `POST /v1/trader/payouts/` with
Bearer + `X-Idempotency-Key` on `trader1.firmX.example`:
CF verify (1) → host→`tenant X` cached (2) → JWT verifies, deny-set clear,
`tenant_id` claim matches host tenant (3) → gate: tenant `active`, identity
`active`, membership `active` — three cache hits (3.5) → key
`payout.request` + `scope=own`: owner = subject (4) → GCRA 5/h: token ok
(5) → entitlement `mod.payouts` cached yes; quota ok (6) → idem claim SETNX
won (7) → correlation adopted (0/8) → body 1.2 KB passes hygiene (9) →
handler: payout row + outbox row + audit row, **one transaction** (10) →
`201 {data:{id…}, meta{request_id: corr, version:"v1"}}` (11). Redis ops:
deny-set 1 + GCRA 1 + idem 2 = 4; PG round trips: 1 (the transaction).
App overhead ≈ 1.6 ms p50.

**Trace B — idempotent retry after timeout.** Same client, same key,
network dropped the first response: claim SETNX loses → `st=done`, hash
equal → stored 201 replayed byte-for-byte + `X-Idempotent-Replay: true` —
**no second payout row exists**; PG saw one transaction.

**Trace C — suspended firm.** Admin of `firmY` (suspended at 14:00:00)
calls `/v1/admin/kyc/` at 14:00:02: steps 1–3 pass (token valid) → 3.5:
pub/sub `tenant.suspended` already dropped the cache at 14:00:00.4 → PG
fresh read says `suspended` → `403 tenant.suspended` "This firm is
currently suspended." + correlation. Nothing after 3.5 executed — no quota
spent, no log line beyond the access + (route not audited) no audit.

**Trace D — pre-live firm.** `onboarding` firm's staff open the admin
checklist: 3.5 tenant state `onboarding` + admin surface → pass by design
(docs/47). The same firm's trader app hits `/v1/trader/challenges/` →
`403 tenant.not_live`, `details.state: "onboarding"`.

**Trace E — webhook.** PSP posts CHK-07 to `/v1/webhooks/payments/`:
signature verified over raw bytes (3) → gates skipped (class webhook) →
no rate limit → handler dedupes provider event id → `200` (or idempotent
`200` for a duplicate). Bad signature → `401 webhook.signature_invalid`,
body never parsed.

## 7. Security mini-model — attack → control

| Attack | Control | Where |
|---|---|---|
| IP spoof via forged `CF-Connecting-IP` | header trusted only from CF published CIDRs | 4.1 |
| Origin scan bypassing CF | no CF peer ⇒ socket IP used; CF-only origin ACL at ingress | 4.1 |
| Host-header confusion / punycode dupes | normalization + unique-host column | 4.2 |
| Cross-tenant token replay (firm A token on firm B) | `tenant_id` claim ≠ host tenant → 401 + security event | 4.3 (SOL-09) |
| Stolen token after revocation | Redis deny-set (jti/session), 24 h | 4.3 |
| Token theft blast radius | 15-min access tokens; no authority in tokens (G31) | 4.3 |
| Login brute force / enumeration | auth class 10/5min + identical failure shape + edge rules | 4.6, 4.3 |
| Privilege escalation | permission keys from registry, roles from DB, fail-closed unknown keys | 4.5 |
| Sensitive-action session hijack | step-up 5-min window (D38) | 4.5 |
| Payout spam | payout GCRA 5/h fail-closed on Redis loss | 4.6 |
| Double-submit / replay of money writes | idempotency claim + verbatim replay + 409 | 4.8 |
| Key-reuse with different payload | body hash compare → 409 | 4.8 |
| Body bombs / slowloris | 1 MiB two-move limit + 10 s race | 4.10 |
| Suspended firm keeps trading | ≤5 s gate cache + event invalidation + suspension-first check order | 4.4 |
| Log injection / secret leakage | correlation validation + header redaction | 4.9, 4.10 |
| Silent audit loss | same-tx success audits; outbox + P1 alert for failure audits | 5.1 |
| Error-message oracle (which layer failed) | fixed check order, generic messages, single 401 shape | 4.3–4.5 |

## 8. Performance & capacity (V1 numbers)

Assumptions (docs/29 scale): 500 rps peak public read, 50 rps writes, 5 rps
money writes fleet-wide.

- **Redis ops/request:** reads ≈ 1 (deny-set) [+1 gate miss]; writes +2
  (GCRA) +2 (idem) ≈ 5 worst case → ≈ 350 ops/s peak — trivial for one
  Redis (50k+ ops/s); still provision `maxmemory 2gb`, `noeviction`, alert
  at 70%.
- **Idempotency memory:** 50 wps × 86 400 s ≈ 4.3 M keys/day upper bound;
  at ≤ 1 MiB stored bodies the worst case is bounded by cap + TTL: typical
  JSON responses ≈ 1.5 KB → ≈ 6.5 GB/day *if every write carried a key* —
  actual idem-flagged routes are ≈ 5 rps → ≈ 650 MB steady state. TTL 24 h
  bounds growth; the 1 MiB per-record cap bounds blast radius.
- **PG:** the chain adds **zero** PG round trips on warm cache; the only
  structural cost is the +1 audit/outbox row inside the handler's own
  transaction.
- **Horizontal scale:** the chain is stateless per instance (all shared
  state in Redis/PG); scale-out is N replicas behind the ingress with no
  session affinity (console sessions live in Redis, not cookies-with-state).

## 9. Test strategy (maps to docs/35)

| Layer | What | Source of truth |
|---|---|---|
| Unit (table-driven) | each middleware in isolation: given ctx/req → expected ctx/envelope | this spec §4 |
| Contract | envelope key sets, code→status table, Retry-After, pagination presence, `X-Idempotent-Replay` | contracts/api/gw.md + taxonomy (generated fixtures) |
| Registry gate (`error_registry_test`) | every emitted code ∈ taxonomy; every 500 carries a registered code; handler packages contain no unregistered code literals | docs/04 §6.2 |
| State matrix (I-20, gate 16) | state × surface × code table generated from `contracts/tenants/state-capabilities.yaml`; code, YAML, DDL lockstep | docs/47 §5 |
| Property/fuzz | correlation validation, body-limit streaming, GCRA arithmetic | §4.6, §4.9, §4.10 |
| Integration (docker) | full chain against real Redis + PG: traces A–E of §6 | §6 |
| Chaos | Redis down per class (§3.6 matrix), PG down, Flipt down, cache-stale serving | §3.6 |
| Load (k6) | 100 rpm/user boundary, 10/5min auth burst, payout smoothness, p99 budget ≤ 5 ms app overhead | §3.4 |

The reference implementation's 18 tests are the seed of the unit +
contract layers; the CI-gated generators (taxonomy table, route table,
state matrix) make drift a build failure rather than a review finding.

## 10. Build plan (developer milestones)

| M | Deliverable | Done when |
|---|---|---|
| M1 | Route table + chain skeleton + envelope writers + funnel + registry gate | envelope contract tests green; a fake unknown code fails CI |
| M2 | Steps 1–2: CF trust, maintenance flag, tenant resolver + caches + tests | unknown-host 404 envelope; normalization tests green |
| M3 | Step 3 + 3.5: three realms + deny-set + gates + state-matrix test generation | I-20 matrix generated from YAML passes; traces C/D green |
| M4 | Steps 4–6: Casbin embed + key registry cross-check; GCRA/fixed-window scripts; entitlements + quota | role matrix tests; rate boundary tests; §3.6 Redis-down matrix chaos tests |
| M5 | Steps 7–9: idempotency lifecycle; correlation position 0; hygiene + timeout + redaction | triple test (first/replay/409); hash-only assertion; trace B green |
| M6 | §5 rows: audit wiring (same-tx + outbox), probes, OpenAPI generation, access log + Sentry boundary | audit same-tx property test; /readyz reflects relay lag; OpenAPI diff vs route table is empty |

M1–M3 unblock module teams against a stubbed chain; M4–M5 are the
abuse/money hardening; M6 closes the operational contract. The reference
implementation (`pf-platform/go/gw/`) is a walk-through of M1–M5 semantics
with in-memory stores.

## 11. Traceability

| Step | Binding reqs | Spec | Reference impl (`pf-platform/go/gw/`) |
|---|---|---|---|
| 1 edge handoff + maintenance | GW-20/33/32 | §4.1 | `security.go`, (flag: TODO M2) |
| 2 tenant resolution | GW-02, TEN-02 | §4.2 | `tenant.go` |
| 3 authn | GW-03, GW-16, G31, D18 | §4.3 | `authn.go` |
| 3.5 status gates | GW-04, AUTH-20/43, TEN-15 | §4.4 | `statusgate.go` |
| 4 authz | GW-04, AUTH-13, ADR-14, D38 | §4.5 | `authz.go` |
| 5 rate | GW-05, GW-29 | §4.6 | `ratelimit.go` |
| 6 quota + entitlement | GW-06, GW-22/23 | §4.7 | `quota.go` |
| 7 idempotency | GW-12, GW-31, GW-37 | §4.8 | `idempotency.go` |
| 8 correlation | GW-09, GW-36 | §4.9 | `correlation.go`, `ulid.go` |
| 9 hygiene | GW-13, GW-35, GW-26 | §4.10 | `hygiene.go` |
| 10 handler | — | §4.11 | (domain packages) |
| 11 response | GW-18..21,28,29,30, D45 | §4.12 | `envelope.go` |
| audit flag | GW-17 | §5.1 | `gw.go` (auditWrap) |
| probes | GW-14 | §5.2 | `gw.go` (Healthz/Readyz) |
| reference scaffold | — | §1, §10 | `pf-platform/go/gw/README.md` |

Known scaffold gaps vs this spec (intentional, listed for honesty): webhook
signature realm (§4.3) and the maintenance-flag gate are not in the
scaffold; the scaffold's rate limiter is an exact in-memory sliding log, not
the Redis GCRA/fixed-window split; stores are in-memory by design.

## 12. SOL decision register (this spec's implementation-level decisions)

| # | Decision | Rationale / status |
|---|---|---|
| SOL-01 | Correlation adopt-or-mint runs at chain position 0; slot 8 remains the propagation checkpoint | GW-18 requires `correlation_id` on step-2/3 failures; no security decision moves |
| SOL-02 | Two listeners: public :8080, internal :8081 compose-only; `/internal/*` on the public listener → 404 | network-position enforcement of "never edge-routed" beats a path check |
| SOL-03 | Typed context contract; steps never read later steps' outputs; one error funnel | testability + order stability |
| SOL-04 | Degradation matrix (§3.6): fail-open default/auth rate, fail-closed payout rate + idempotency, stale-serve gates ≤ 30 s | availability where the edge guards; safety where money is at stake — **approved 2026-09-20 (D48)** |
| SOL-05 | GCRA for auth/payout classes, fixed window for the per-user default; one Lua script each | smooth money/login caps with exact Retry-After; cheap default |
| SOL-06 | In-flight duplicate idempotency → `409 request.idempotency_conflict`; in-flight lease 15 min | registered codes only; simple client contract — **approved 2026-09-20 (D49)** |
| SOL-07 | Boundary: 500 + `gw.internal` + `X-Sentry-Event-Id`; taxonomy's `gw.internal` HTTP cell pinned to 500 | registry gate forbids unregistered 500 codes; **approved 2026-09-20 (D50)** — the taxonomy UX row now carries 500 |
| SOL-08 | Message strings instantiate the taxonomy patterns per surface (login vs bearer 401 wording) | taxonomy gives patterns; exact strings ratified at contract freeze |
| SOL-09 | `tenant_id` token claim must equal host-resolved tenant, else 401 + security event | closes cross-tenant token replay; 401 keeps "invalid here" semantics |
| SOL-10 | Cache/invalidation table (§3.5): pub/sub drop + TTL upper bound | bounded staleness everywhere; no authoritative cache |
| SOL-11 | Step-up reads ZITADEL `auth_time`/`amr`; 5-min window (D38); refusal code `authz.step_up_required` | registered code; no gateway-initiated prompts |
| SOL-12 | 405 method guard before authn/rate | probes cost nothing; routes are public via OpenAPI |
| SOL-13 | Access-log JSON schema + redaction list (§5.2) | GW-35 enforcement point |
| SOL-14 | Success audits same-transaction; failure audits via outbox with P1 alert | docs/50 "never silent"; audit-abort-business for success path |
| SOL-15 | Latency budget ≤ 5 ms p99 app overhead (§3.4) | the number later perf tests enforce |
| SOL-16 | Webhook realm: raw-body signature verify, ±5 min timestamp, provider dedupe in handler | CHK-07/KY-05/EVT-10 semantics |
| SOL-17 | Probes + OpenAPI bypass authn/rate/maintenance | GW-14/15 semantics; orchestrator correctness |
| SOL-18 | Envelope writers are the only sanctioned writers (lint + contract tests) | D45/GW-18 shape drift becomes a build failure |
| SOL-19 | Internal bearers: SOPS → SHA-256 at boot, constant-time compare, 24 h dual-token rotation | docs/44 §7 90-day rotation with zero-downtime overlap |
| SOL-20 | Declarative route table generates chain + OpenAPI + registry cross-check | one source of truth; drift = CI failure |

**Ratified:** SOL-04 → **D48**, SOL-06 → **D49**, SOL-07 → **D50**
(owner, 2026-09-20; recorded in `scripts/design-questions.json` and applied
to the taxonomy UX row). No flags outstanding. No binding text was changed
by this spec; no PRD workbook row was changed.

# pf-platform/go/gw — reference implementation of the 11-step gateway chain

A working, dependency-free Go implementation of the binding middleware chain
from `docs/04 §3.1` (Alpha-One platform docs, pass 14 state of
`contracts/api/gw.md`). It is the **in-app gateway** per ADR-4: not an edge
proxy — TLS/WAF/edge rate limiting stay at Cloudflare (GW-20/33).

- Go >= 1.19, **zero external modules** (stdlib only).
- Every Redis/PG-backed step sits behind a small interface with a correct
  in-memory implementation; production swaps the interface, not the chain.
- Responses honor the **D45 success envelope** and the **GW-18 error
  contract**; every error code emitted is in the registered baseline set
  (unknown codes collapse to `500 gw.internal`, mirroring the docs/04
  §6.2 registry gate).

## Verify

```sh
bash verify.sh   # go vet + go test -race; needs any Go >= 1.19 toolchain
```

## The chain (request order == binding order)

| # | Step (docs/04 §3.1) | Code | Contract |
|---|---------------------|------|----------|
| — | access log | `hygiene.go AccessLog` | GW-09 propagation |
| 8*| correlation adopt-or-mint | `correlation.go Correlation` | GW-09/36, docs/49 C1 |
| 1 | edge handoff + security headers + CF-IP trust | `security.go SecurityHeaders` | GW-20/33 |
| 2 | host → tenant resolution | `tenant.go TenantResolve` | GW-01, `tenant.unknown_host` 404 |
| — | 405 method guard (before authn/rate: probes burn nothing) | `gw.go methodGuard` | — |
| 3 | authentication (3 realms) | `authn.go Authenticator` | GW-03, D46 URL plan |
| 3.5| status gates (route-class aware, cached) | `statusgate.go StatusGateMW` | docs/47, docs/12 |
| — | sensitive-action audit wrapper | `gw.go auditWrap` | GW-17, docs/50 |
| 4 | permission-key authorization (+own-scope, +step-up) | `authz.go Authorize` | GW-04, ADR-14, D38 |
| 5 | rate limiting (class policies + Retry-After) | `ratelimit.go RateLimitMW` | GW-05/29 |
| 6 | quota + entitlements | `quota.go QuotaMW` | GW-06, docs/33, `tenant.not_entitled` |
| 7 | idempotency (scope, 24h TTL, hash-only, replay, 409) | `idempotency.go IdempotencyMW` | GW-12 |
| 9 | payload limit + handler timeout | `hygiene.go BodyLimit, WithHandlerTimeout` | GW-13 |

\* correlation runs outermost so **pre-step-8 failures still carry
`correlation_id`** in the GW-18 envelope; the security-critical order
(2 → 3 → 3.5 → 4 → 5 → 6 → 7 → 9) is untouched. This is documented in
`correlation.go`.

## Files

| File | Contents |
|------|----------|
| `gw.go` | `Route`, `Config`, `Deps`, `Builder.Build` (the chain), audit wrapper, `Healthz`/`Readyz` |
| `context.go` | typed context accessors: correlation, client IP, tenant, principal, route |
| `ulid.go` | Crockford ULID minting (48-bit ms timestamp + crypto/rand) + correlation validation |
| `envelope.go` | D45 success envelope (`WriteSuccess/WriteCreated/WritePage`), GW-18 errors, code→status table |
| `correlation.go` | step 8 middleware |
| `security.go` | step 1: headers + `CF-Connecting-IP` trusted-CIDR rule |
| `tenant.go` | step 2: resolver interface, `MapResolver`, `CachedResolver` (pos+neg TTL) |
| `authn.go` | step 3: trader/staff JWT realm, console cookie realm, `/internal/*` static bearer realm |
| `statusgate.go` | step 3.5: gate interface, `MapStatusGate`, `CachedGate` with invalidation hooks |
| `authz.go` | step 4: permission table, own-scope, 5-min step-up window (D38) |
| `ratelimit.go` | step 5: sliding-log limiter + binding class policies (auth 10/5min, payout 5/h, else 100/min) |
| `quota.go` | step 6: module entitlements (fail-closed) |
| `idempotency.go` | step 7: store interface, `MemIdemStore`, replay/conflict semantics, SHA-256-only storage |
| `hygiene.go` | step 9: body limit, handler timeout, access log, header redaction |
| `gw_test.go` | 18 tests covering every step, the envelope shapes, ordering, and audit |

## Production swap-in points (no chain changes)

| Interface | Production backend |
|-----------|--------------------|
| `TenantResolver` | SQL `tenants` lookup on unique host (or the cached decorator over it) |
| `TokenVerifier` | platform JWT verifier (RS256 + audience) |
| `SessionStore` | server-side console sessions (Redis) |
| `StatusGate` | one indexed SQL query over `tenants`/`identities`/`tenant_members`; use `CachedGate` + invalidation on state transitions |
| `Limiter` | Redis fixed-window counters (same `Allow` semantics) |
| `Entitlements` | `tenant_entitlements` cache reader |
| `IdempotencyStore` | Redis `SETNX t:{ten}:idem:{method}:{path}:{key}` per GW-31 (24h TTL, AOF everysec; PG-backed store is the V2 upgrade behind the same interface — docs/55 §4.8) |
| `AuditSink` | append-only `audit_events` writer (must alert on failure — docs/50 P1) |
| `Logger` | `*slog.Logger` via a 3-line adapter (`Printf` shim) |

## Deliberate simplifications (reference scope)

- Route matching uses `http.ServeMux` + explicit `Mount(method, …)`; a real
  router can sit underneath without touching the chain.
- The scaffold binds `/internal/*` on the same listener as a path prefix;
  production enforces docs/55 SOL-02: a second listener on the compose
  network only (the public listener 404s internal paths).
- The webhook signature realm (CHK-07/KY-05/EVT-10) and the GW-32
  maintenance flag are specified in docs/55 §4.1/§4.3 but not scaffolded.
- Timeout does not cancel the handler goroutine (request-context-aware
  upstreams cancel themselves; the client is released at the deadline).
- `MemLimiter`/`MemIdemStore` are per-process and exact, not distributed —
  they demonstrate the **semantics** the Redis/PG versions must reproduce
  (tests assert those semantics, including hash-only persistence).
- Audit records are the `AuditEvent` struct; per-route `AUD-##` action codes
  attach when the concrete routes are wired (docs/50).
- Console realm requires a real `SessionStore`; no demo session issuer is
  included (out of gateway scope).

## Binding numbers encoded here

- Rate: auth `10 / 5 min`, payout `5 / h`, default `100 / min` per user
  (edge per-IP stays at Cloudflare) — `429 rate.limited` + `Retry-After`.
- Idempotency: scope `(tenant, method, path, key)`, TTL 24 h, body stored as
  SHA-256 only, replay returns the stored response, key reuse with a
  different body → `409 request.idempotency_conflict`; 5xx never remembered.
- Correlation: inbound `X-Correlation-Id` adopted when valid, else a minted
  26-char Crockford ULID; echoed in `X-Correlation-Id`, the envelope
  `meta.request_id` / `correlation_id`, logs, and audit events.
- Status gates: `tenant.suspended`/`tenant.not_live` for trader surfaces
  pre-live; admin/console/payout staff surfaces operate during onboarding;
  suspended identity/membership → 403 with the registered codes.
- Entitlements: un-entitled module route → `403 tenant.not_entitled`.
- Payload limit default 1 MiB (declared max, GW-13); unknown error codes →
  `500 `gw.internal` (SOL-07, docs/55 §4.12 — registry gate parity with docs/04 §6.2).

# Mobile App (Part A) API Contract (MOB)

Status: PROVISIONAL (post-V1, design-level)
Owner: TBD
Version: v1
Last updated: 2026-09-19

Derived from `docs/26-mobile-apps.md` §7 + PRD MOB-NN (V2.0, V3.0). Nothing here is final until that phase's contract freeze (docs/99 §12).

## Scope

PRD module **MOB** (8 requirements). Abridged backlog:

| Req | Feature | Release | Pri | Owner | User story (abridged) |
|---|---|---|---|---|---|
| `MOB-01` | Native iOS app | V2.0 | P1 | FE-1 | As a trader, I can install a native iOS app so that I access my accounts on my phone. |
| `MOB-02` | Native Android app | V2.0 | P1 | FE-1 | As a trader, I can install a native Android app so that I access my accounts on my phone. |
| `MOB-03` | Mobile push notifications | V2.0 | P1 | BE-2 | As a trader, I receive push notifications on my phone when important lifecycle events occur so that I never miss a breach, pass, o… |
| `MOB-04` | Biometric login | V2.0 | P1 | BE-2 | As a trader, I log in with Face ID or fingerprint so that mobile access is fast and secure. |
| `MOB-05` | Mobile KYC capture | V2.0 | P1 | BE-2 | As a trader, I complete KYC directly from my phone using the camera so that verification is fast. |
| `MOB-06` | Mobile trade viewer | V2.0 | P1 | FE-1 | As a trader, I see my open positions, equity curve, and rule progress on mobile so that I can monitor anywhere. |
| `MOB-07` | Mobile onboarding | V2.0 | P1 | FE-1 | As a trader on mobile, I see a first-run onboarding flow (login, permissions, tutorial) so that mobile use is clear. |
| `MOB-08` | Offline mode | V3.0 | P2 | FE-1 | As a trader, I can view cached account and rule data when offline, so that the app is useful without connectivity. |

## Auth

Trader (mobile session; same API as TD, no mobile-specific surface per Out Of Scope). All routes sit in the GW chain (docs/04 §3.1): tenant resolution →
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

> **Scope note:** MOB/JRN/EDU/CHT is not in the V1 execution sheet (V3 scope). There is no V1 baseline contract for this module; the surface below is design-level (post-V1, docs/99) and provisional until its phase's contract freeze.


**None new** — MOB consumes: the TD contract (16 §7), the AUTH
device-credential endpoints (V2: `POST /v1/auth/devices` (register,
returns the device token), `DELETE /v1/auth/devices/{id}` (the
device management), the token refresh), the NOT push-token endpoints
(`POST /v1/notifications/push-tokens`, the prefs API). The GW gains
one route class: `/v1/mobile/*` is **not** a new API — it's the same
routes with the mobile client's Accept/version headers (the
`min_client_version` check is a GW middleware, 04's chain, a new step
after the auth).

## Open contract questions

- Paths, methods, and field names below are PROVISIONAL until this module's phase
  freeze (docs/99 §12) — additive changes only after freeze; breaking changes get
  `/v2/` + the 12-month deprecation rule for public surfaces.
- Permission keys: the V1 registry (`permissions/registry.md`) is binding; keys used
  below beyond it are provisional and join the registry at freeze.
- Error codes: V1 baseline codes are binding (`errors/taxonomy.md`); extended codes
  follow the GW-18 dotted convention and freeze with the module (docs/30).

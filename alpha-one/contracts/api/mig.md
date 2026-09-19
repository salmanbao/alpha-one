# Migration Tooling API Contract (MIG)

Status: PROVISIONAL (post-V1, design-level)
Owner: TBD
Version: v1
Last updated: 2026-09-19

Derived from `docs/25-migration.md` §7 + PRD MIG-NN (V2.0, V3.0). Nothing here is final until that phase's contract freeze (docs/99 §12).

## Scope

PRD module **MIG** (8 requirements). Abridged backlog:

| Req | Feature | Release | Pri | Owner | User story (abridged) |
|---|---|---|---|---|---|
| `MIG-01` | Import from TradeTechSolutions | V2.0 | P1 | BE-1 | As a super admin, I can import a firm from TTS including traders, accounts, orders, KYC references, balances, and history so that … |
| `MIG-02` | Import from YourPropFirm | V2.0 | P1 | BE-1 | As a super admin, I can import a firm from YourPropFirm with the same fidelity as TTS so that any firm can switch. |
| `MIG-03` | Import from PropAccount and other brokers | V3.0 | P2 | BE-1 | As a super admin, I can import a firm from PropAccount and other white-label platforms so that migration is universal. |
| `MIG-04` | Import verification and reconciliation | V2.0 | P1 | BE-1 | As a super admin, I see checksums and reconciliation reports for every migration so that data integrity is provable before cutover… |
| `MIG-05` | Dual-run mode | V2.0 | P1 | BE-1 | As a super admin, I can run the old and new platform in parallel for a period with unified reporting so that cutover is low-risk. |
| `MIG-06` | Migration concierge service | V2.0 | P1 | BE-1 | As a super admin, I have a runbook and tooling to white-glove the first 10 tenants through migration so that early wins are guaran… |
| `MIG-07` | Migration dry-run mode | V2.0 | P1 | BE-1 | As a super admin, I run a full migration rehearsal that validates data without committing to the target, so that cutover is low-ri… |
| `MIG-08` | Post-migration validation report | V2.0 | P1 | BE-1 | As a super admin, I receive a formal validation report after migration, so that sign-off is provable. |

## Auth

Super Admin only (CON). Tenant staff get read-only cutover status. All routes sit in the GW chain (docs/04 §3.1): tenant resolution →
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

> Copied verbatim from `docs/25-migration.md` §7 on 2026-09-19 — the module doc is authoritative if they drift; regenerate with `python3 scripts/complete_contracts_pack.py`.

> **Scope note:** MIG is not in the V1 execution sheet (V2 scope — the FunderBlu onboarding program). There is no V1 baseline contract for this module; the surface below is design-level (post-V1, docs/99) and provisional until its phase's contract freeze.


Console (MIG is a platform-ops surface — the console realm, the
migration runbook UI):
`POST /v1/console/migrations` (create: tenant, export refs, the policy
set — §3.2/§3.3 decisions recorded as data, 2FA),
`GET /v1/console/migrations/{id}` (the runbook view: class states,
reconciliation report, exceptions queue, the gate state),
`POST /v1/console/migrations/{id}/dry-run` (2FA — starts the §2 step 0
pipeline on the staging tenant),
`POST /v1/console/migrations/{id}/classes/{class}/retry` (after a fix),
`POST /v1/console/migrations/{id}/exceptions/{id}/dispose` (2FA, reason,
action — the COO+ops pattern),
`POST /v1/console/migrations/{id}/cutover` (the gate-checked trigger,
2FA + the V2 two-op — for FunderBlu, two-op from day 1: the §21 CON-32
pattern),
`GET /v1/console/migrations/{id}/parallel-run` (the daily comparator
state), `POST /{id}/parallel-run/close` (the sign-off, 2FA + note),
`POST /v1/console/migrations/{id}/corrections` (the §3.5 flow).

Trader-facing: none (the cutover is invisible-by-design: the trader
logs in, trades, requests payouts — the only trader-visible MIG artifact
is the forced password reset at first login + the FunderBlu comms).

## Open contract questions

- Paths, methods, and field names below are PROVISIONAL until this module's phase
  freeze (docs/99 §12) — additive changes only after freeze; breaking changes get
  `/v2/` + the 12-month deprecation rule for public surfaces.
- Permission keys: the V1 registry (`permissions/registry.md`) is binding; keys used
  below beyond it are provisional and join the registry at freeze.
- Error codes: V1 baseline codes are binding (`errors/taxonomy.md`); extended codes
  follow the GW-18 dotted convention and freeze with the module (docs/30).

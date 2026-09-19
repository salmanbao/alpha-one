# Data Dictionary — V1 Canonical Vocabulary

Status: DRAFT (adopted as the V1 baseline from the V1 execution-sheet
research, 2026-09-16/17). This file is the single reference for the
enumerated values, state names, and field conventions the V1 contract
research cites (e.g. `api/lcc.md` → `data/dictionary.md` →
`accounts.phase`). The full DDL lives in `data/schemas/` (split from
docs/32); the binding conventions live in docs/32 §1 and docs/04.

## 1. Account state machine (LCC-02)

`accounts.status` — the states are exactly those named by LCC-02
(`contracts/diagrams/account-state.md`):

| State | Meaning |
|---|---|
| `CREATED` | purchased, awaiting broker provisioning |
| `ACTIVE` | live, in evaluation (trading enabled) |
| `PASS_PENDING` | objectives met (EVL-19); awaiting auto-advance or verification |
| `VERIFICATION` | queued for manual verification per config |
| `AWAITING_ACTIVATION` | activation fee configured, awaiting payment (state fixed by LCC-02 V1; the hold-and-pay flow cites LCC-08, V2.0 — flagged open question) |
| `BREACH_DETECTED` | hard breach (EVL-17); disable-then-close enqueued |
| `CLOSING` | broker closure in progress (BRG-10/11) |
| `FAILED` | broker confirmed closure |
| `FUNDED` | funded stage — a **status**, not a phase |
| `SUSPENDED` | admin suspend (LCC-11); resumes to `ACTIVE` or `FUNDED` by phase |
| `TERMINATED` | terminal-only, no outgoing edges (LCC-27 cleanup guarantees no orphaned broker state) |

Spawn semantics: a passing account terminates at `PASS_PENDING`,
`VERIFICATION`, or `AWAITING_ACTIVATION` and a **new account row** is
created (not a transition of the same row) — next phase
(`parent_account_id` set, LCC-06) or funded (LCC-07/20).

## 2. `accounts.phase`

Per-challenge ordinal (integer ≥ 1). The funded stage is
`status = FUNDED`, not a phase (LCC-02, `api/lcc.md`). Phase lineage
is `parent_account_id` (LCC-06); a separate lineage table is an open
question.

## 3. `challenges.kyc_timing`

Per-challenge config (LCC-07 / KYC-07 / KYC-08 gating):
`{at_creation, after_evaluation, at_first_payout, skipped}` — the value
set per KYC-03's timing description. KYC-03 (config UI) is V2.0; V1
challenges may only use the subset their V1 gates (KYC-07 funding,
KYC-08 payout) can enforce.

## 4. KYC state machine (KYC-06)

`kyc_verifications.state`: `NOT_STARTED`, `PENDING`, `IN_REVIEW`,
`APPROVED`, `REJECTED`, `NEEDS_RESUBMISSION`, `EXPIRED`
(`contracts/diagrams/kyc-state.md`). EXPIRED trigger and
REJECTED → retry path are open questions.

## 5. Payout state machine (PAY-13)

`payouts.state`: `requested`, `eligibility_checked`, `pending_approval`,
`approved`, `rejected`, `processing`, `paid`, `failed`, `cancelled`
(`contracts/diagrams/payout-state.md`). V1 enters only
`requested → eligibility_checked → pending_approval → approved|rejected
→ paid`. `processing` (PAY-24, V2), `failed` (PAY-18, V2),
`cancelled` (PAY-17, V2) are **reserved states with no V1 entry path**.
Failed eligibility never creates a payout row (PAY-03 is a synchronous
gate → `payout.ineligible`).

## 6. Checkout session lifecycle (CHK-02/43/44)

`checkout_sessions.state`: `reserved` (price + coupon held) →
`completed` (payment captured, order created) | `cancelled`
(trader cancel, CHK-44) | `expired` (scheduled expiry worker, CHK-43,
emits `checkout.session.expired`). `reservation_expires_at` (timestamptz)
holds the reservation window; the duration is an open question.

## 7. Event envelope (EVT-03)

Every event carries exactly: `id` (ULID), `type` (event name),
`version` (integer, starts 1), `tenant_id` (ULID), `occurred_at`
(int64 epoch ms, UTC), `payload` (event-specific object). Schemas:
`events/payloads/envelope.schema.json` + one file per V1 event.
Broker commands are **not** events (EVT-20) — they live in
`command_queue` and must never appear in the event stream.

## 8. Error envelope (GW-18)

Every error response carries exactly: `code` (stable machine code,
`errors/taxonomy.md`), `message` (user-facing pattern),
`correlation_id` (request correlation; also recorded in audit entries,
AUD-01).

## 9. Permission keys (AUTH-13)

Format `resource.action` (e.g. `payout.approve`). Module-declared,
enforced at the API layer (GW-04). The V1 registry:
`permissions/registry.md`. Trader self-actions are identity-scoped
(caller = resource); whether they additionally require keys is an open
question.

## 10. Route groups (GW-01)

One API, four route groups (separation enforced at the routing layer):
`/v1/auth/*` + `/v1/trader/*` (trader portal), `/v1/admin/*`
(tenant admin), `/v1/console/*` (platform console, separate auth realm
CON-01), `/v1/webhooks/*` (provider webhooks, signature-authenticated
EVT-10).

## 11. Reserved subdomains (TEN-42)

`www`, `admin`, `api`, `console`, `app` — the reserved list;
`tenant.subdomain_reserved` 409 on collision.

## 12. Money

USD only in V1 (Out Of Scope: no multi-currency). Minor units (int64
cents) + ISO-4217 code; capture-time rate stored as metadata when
relevant (LED-01). Never floats.

## 13. Tenant resolution (TEN-02 / GW-02)

Edge (Cloudflare) resolves tenant from domain/subdomain; gateway
middleware rejects unknown hosts (`404 tenant.unknown_host`) before auth
runs. No request executes without tenant context. Provider webhook URLs
are provisioned per tenant:
`https://{tenant-subdomain}.platform.com/v1/webhooks/{payments|kyc}/{provider}`.

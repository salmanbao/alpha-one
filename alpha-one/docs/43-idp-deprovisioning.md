# 43 — IAM Deprovisioning: Propagation, Failure Handling & Closure

> Third-pass follow-up to the AUTH/TEN review (`docs/42`), 2026-09-19. Scope: how a
> deprovisioning action in the identity provider reaches `tenant_memberships` in
> seconds rather than a day, what bounds the exposure when it does not, and what
> happens when a user deletes their own account.
>
> Requirement coverage: a cross-cutting **design artifact**, not a module doc — it
> claims no PRD rows of its own. It makes the suspension/unsuspension rows' propagation
> real, turns the session-lifetime row from documentation into configuration, and gives
> the SSO/SCIM rows their deprovisioning half; the touched artifacts are listed in §11.
>
> Evidence: verified against ZITADEL documentation and source
> (`internal/repository/**`, v4.17.x line, checked 2026-09-19) plus the upstream
> issues cited inline. Precedent for the chosen pattern is in §10.
>
> Decisions recorded here: **D10** (token lifetimes — answered), **D11** (propagation
> mechanism — answered), **D12** (self-service deletion posture — open, DPO).

## 1. The gap, stated plainly

**Nothing of this exists today.** There is no webhook, no consumer and no
reconciliation job: deprovisioning is a single sentence in the `docs/02` §16 risk
register ("identity-store drift — mitigation: nightly reconciliation job + TEN-32
access review") and TEN-32 itself is a **V2** staff access-review report. If a tenant
deactivates a user in its directory, or an admin deletes one in the ZITADEL console,
the `tenant_memberships` row stays `active` until a human notices. Worst case is
unbounded in practice; "≤ 24 h" is the optimistic framing, not a guarantee.

Two further facts make the status quo worse than it reads:

| Fact | Consequence |
|---|---|
| ZITADEL's **instance default access-token lifetime is 12 h** (not the 15 min `docs/02` §3.2 records) and nothing in the blueprint sets it | revocation-by-expiry is not a backstop at all — an orphaned token survives the whole working day |
| ZITADEL is the SCIM **server** for the SSO tenant (`AUTH-25`): the tenant's IdP calls ZITADEL, not us | we cannot subscribe to the tenant's SCIM `PATCH active:false`; whatever we build must observe what ZITADEL *recorded* |

Four deprovisioning origins must all be covered, and they converge in exactly one
place — the IdP's event store:

| Origin | Arrives as | Why the event log is required |
|---|---|---|
| Tenant IdP disables/removes a user (SCIM, `AUTH-25`) | ZITADEL applies the SCIM call, then records `user.deactivated` / `user.removed` | ZITADEL terminates the SCIM conversation; our only view is its event log |
| Tenant or platform admin removes access in the ZITADEL console | same events | no API call of ours is involved at all |
| Our own flows (`AUTH-20` suspend, `AUTH-43` unsuspend, tenant teardown) | our outbox → we already write `tenant_memberships` first | unchanged; the consumer must not fight it |
| **User deletes their own account** (`/v2/users/{id}` delete-user endpoint, or ZITADEL's console profile page at `/ui/console/users/me`) | `user.removed` | a hard delete leaves **nothing** in the projection APIs — the log is the only surviving record. Gated by the `user.self.delete` permission, granted via the roles `ORG_USER_SELF_MANAGER` (org) or `SELF_MANAGEMENT_GLOBAL` (instance); §8 sets the V1 posture |

## 2. Why ZITADEL Actions v2 event executions are not the mechanism

Event executions are the obvious first idea, and they are rejected — not as risky,
but as structurally wrong for a security control:

1. **No retry.** A failed call loses the event permanently, confirmed upstream
   ([#10268](https://github.com/zitadel/zitadel/issues/10268), filed Jul-2025 against
   v3.3.0; now labelled *To-be-closed* as a v3-era request, with v3 deprecated
   31 Aug 2026). Epic #7235's promised "failure handling, retries" never shipped. The
   webhook target uses the HTTP response status only.
2. **Event-condition executions are currently unsafe at instance level**
   ([#12225](https://github.com/zitadel/zitadel/issues/12225), open, reproduced
   v4.11.0–v4.15.0): an execution bound to an *Event* condition causes widespread API
   failures and breaks hosted login **regardless of what the target returns** — and
   with `interruptOnError` enabled the instance is unusable. Our deprovisioning
   targets would be exactly that shape.

A push path may be added later as a latency fast path **only** after both upstream
issues are fixed; it can never be the transport. §10 shows we would also be skipping
the retry tier that comparable vendors ship.

## 3. Mechanism — the `idp-sync` consumer (pull from the event log)  [BINDING]

```
ZITADEL event store (instance sequence; retained by default)
   │   POST /admin/v1/events/_search   {asc, sequence: cursor, limit: 500,
   │       aggregateTypes: ["user","user_grant"]}          ← machine user, IAM_OWNER_VIEWER
   ▼                                                          poll every 10 s
idp-sync worker (Go; one instance, joins the existing worker set — docs/01 §4.1)
   │   1. INSERT idp_inbox(event_id PK) ON CONFLICT DO NOTHING      ← idempotent ingest
   │   2. map:  resource_owner → identity_idp_links.idp_org_id → tenant
   │            aggregate_id   → identity_idp_links.idp_user_id → identity
   │   3. apply in one PG tx: tenant_memberships.status, session kill, outbox row
   │   4. advance idp_sync_cursors.last_sequence    ← only after the page is applied
   ▼
PG outbox → relay → Redis Streams `user.suspended` → GW deny-set, NOT, AUD
```

| Element | Definition |
|---|---|
| `idp_sync_cursors(instance_id PK, last_sequence, updated_at)` | one instance-wide cursor; the ZITADEL sequence is instance-global, so a single cursor covers every tenant and the platform staff org |
| `idp_inbox(event_id PK, sequence UNIQUE, type, aggregate_id, resource_owner, payload JSONB, attempts, last_error, applied_at)` | durable landing zone; dedupe key = ZITADEL `event_id` |
| Poll interval | 10 s (config); p50 propagation = one tick, p99 = tick + apply |
| Auth | machine user with `IAM_OWNER_VIEWER` (PAT, 90 d rotation — it joins the `docs/02` §3.3 secret table) |
| Checkpoint-then-act | the cursor advances only after the page's effects commit; a crash re-reads the page and the inbox dedupe makes it a no-op |
| Ordering | sequence-ordered within the instance; effects are idempotent and order-tolerant (a `user.removed` without a prior `user.deactivated` applies the stronger transition) |
| Scope filter | `aggregateTypes: ["user","user_grant"]` plus the instance-member aggregate (§4) |

**Invariant (binding): IdP-derived events may only *reduce* access.** No event from
ZITADEL ever creates a membership, grants a role or adds a permission key. Provisioning
stays in our stores through the tenant saga and ADM (`P4`). This closes the escalation
path where a tenant's own IdP admin adds a user to a mapped group and expects Alpha One
access: they get a review item, never a role.

Latency budget:

| State | Worst-case exposure |
|---|---|
| Normal (sync running, 10 s poll) | ~10 s + ≤ 1 s deny-set rejection |
| Worker down, alert fired | bounded by page + runbook (target ≤ 15 min to acknowledge) |
| Worker down **and** alerting down | **one access-token lifetime** — 15 min once §6 is applied |

## 4. Event mapping (exact event types)

Strings verified in ZITADEL source (`internal/repository/user/{user.go,human.go,human_email.go}`,
`internal/repository/usergrant/user_grant.go`, `internal/repository/{org,instance}/member.go`).
Phase-0 gate: enumerate the live list from the pinned version's
`/admin/v1/events/types/_search` and diff it against this table (docs/99 gate 6).

| ZITADEL event | Effect in our stores |
|---|---|
| `user.deactivated` | `tenant_memberships.status = 'suspended'`; kill sessions (`DeleteSession` + `RevokeAllMyRefreshTokens`) + deny-set; emit `user.suspended` with `reason_code: policy`, `reason_text: idp_deactivated`, actor `system:idp-sync` |
| `user.removed` | as above **plus** membership → terminated (soft), `identities.deleted_at` only when no other active membership remains |
| `user.reactivated` | unsuspend **only** when the recorded suspension reason was IdP-driven; never auto-restore a staff or fraud suspension (`AUTH-20`) |
| `user.locked` / `user.unlocked` | auth-level only → mirror `identities.locked_until`; membership untouched |
| `user.grant.added` / `.changed` / `.cascade.changed` | role mirror: a grant change may **revoke** our role; it never grants one (§3 invariant) |
| `user.grant.removed` / `.cascade.removed` / `.deactivated` | role removed → if **zero** roles remain, suspend the membership (fail-closed) + staff review item |
| `user.grant.reactivated` | restart the review; no automatic role restore |
| `user.human.added` / `user.human.selfregistered` | resolve/create the `identities` stub + membership in state `invited` — never `active` |
| `user.human.email.changed` / `.verified`, `user.username.changed` | maintain `identity_emails` + the `identities.email` cache; **`identity_key` never moves** (review G35 / decision D20); the email-change payout hold stays an app rule (`AUTH-29`) |
| `user.human.password.changed` + the MFA-factor events (`user.human.mfa.*` — exact strings confirmed by the Phase-0 enumeration, gate 6) | **credential-change session kill (review G40, default fix):** revoke every `auth_sessions` row of the identity except the one that performed the change (`DeleteSession` + deny-set + `user.session_revoked` reason `credential_change`), CRITICAL audit — also covers the staff forced-reset path (`AUTH-28`). Without it, a stolen session survives the exact action a user takes to defend themselves |
| `org.member.added` / `.changed` / `.removed` / `.cascade.removed`, `instance.member.*` | audit-only: they record who may change our mirror. `instance.member.added` with `SELF_MANAGEMENT_GLOBAL` also feeds the §8 detection rule |

**Routing rules (review G32, docs/44 §8).** `resource_owner` = the platform org → the
platform-staff path (link `tenant_id NULL`, notify `platform.identity.admin` holders);
`resource_owner` matching no `tenants.idp_org_id` and not the platform org → **hold the
cursor + alert** (never guess a tenant, never drop); a tenant in `deleted`/`archived` →
apply to the membership row and audit (the termination saga already suspended its
identities).

**No new V1 event contract is needed:** the pipeline emits the existing
`user.suspended` / `user.activated` (`contracts/events/payloads/`, `contracts/events/catalog.md`),
with `reason_text` carrying the IdP provenance. Adding `idp_deprovisioned` to the
`reason_code` enum is optional and not a prerequisite.

## 5. Delivery-failure handling  [BINDING]

The point of polling is that **there is no such thing as a missed event** — the only
failure state is a stalled cursor, and that is exactly what the alerts watch. This
inverts the webhook's silent-failure property.

| Failure | Handling |
|---|---|
| ZITADEL API error / timeout / expired PAT | exponential backoff 1/2/4/8/16 s, 5 attempts, then hold the cursor and page |
| Event fails to apply (unknown aggregate, malformed payload, mapping miss) | inbox row keeps `last_error`; 5 attempts; then **hold the cursor** and write `idp_dlq` — never advance past an unapplied deactivation |
| Worker crash / restart | cursor stalls → lag and `absent()` rules fire (no metrics is *not* silence) |
| Duplicate delivery / replay | `idp_inbox.event_id` PK; checkpoint-then-act; applies are idempotent |
| Catch-up after an outage | automatic from the cursor; re-apply is a no-op, so no manual replay tooling is required (`catchup --since <ts>` resets the cursor for disaster cases) |
| Retention shorter than the outage | the one real loss mode. `AuditLogRetention` default is **all events**; verify it at provisioning and include it in the drift check |

Metrics → the existing stack (Prometheus/Grafana, Sentry, Uptime Kuma;
`docs/01` §2, `docs/04` §13): `idp_sync_lag_seconds`, `idp_sync_last_success_timestamp`,
`idp_sync_stalled_seconds`, `idp_sync_dlq_depth`, `idp_sync_apply_failures_total`.

```
- alert: IdpSyncStalled   expr: time() - idp_sync_last_success_timestamp > 300   # SEV-1, page
- alert: IdpSyncLag       expr: idp_sync_lag_seconds > 60                        # SEV-2, page
- alert: IdpSyncDown      expr: absent(idp_sync_last_success_timestamp)          # worker not running
- alert: IdpSyncDlqDepth  expr: idp_sync_dlq_depth > 0                           # ticket
```

Operational surface: a **CON health row** ("IdP event sync: last event, lag, DLQ")
next to the existing PG/Redis/relay rows (`docs/21` §3.2), a runbook entry
(restart worker, cursor reset, DLQ triage), and a **staging drill** in the test plan
(`docs/35` §5.1): kill the worker → confirm the page inside 5 min → restart → confirm
the catch-up applies the missed deactivations with no duplicates.

## 6. Exposure bound — access-token lifetime  [BINDING]

`docs/02` §3.2 records 15 min; nothing sets it, and ZITADEL's instance default is
**12 h** (`DefaultOidcSettings`: access 12 h / id 12 h; refresh idle 720 h, absolute
2160 h). 5–15 min is achievable and is the load-bearing control: it is the only bound
left when the sync *and* its alerting are both dead.

Provisioning step (instance-wide; per-org OIDC settings remain an open upstream
request #5219), using the instance OIDC-settings endpoint
(`/admin/v1/settings/oidc` — update = method `PUT`, all four fields required,
seconds precision; read back with the get method to verify):

```json
{
  "accessTokenLifetime": "900s",
  "idTokenLifetime": "900s",
  "refreshTokenIdleExpiration": "1800s",
  "refreshTokenExpiration": "2592000s"
}
```

900 s access/id, 30 min refresh idle (matching our documented idle timeout), 30 d
absolute — the deployed values are asserted at Phase 0 (docs/99 gate 6) and
re-checked by the drift job (§7).

Two spike items that decide whether an orphaned token can survive (docs/99 gate 6):

1. **Deny-set key shape.** `/sessions/{id}` termination plus a deny-set keyed on
   `jti` works only for the token ids we snapshotted in
   `auth_sessions.idp_token_jti`; a refresh token racing the kill can mint one token
   that survives to natural expiry. If the access token carries a session claim
   equivalent to the id-token `sid`, keying the deny-set on it closes that window —
   verify which claim is present and record it.
2. **Deny-set TTL.** `TTL = access-token TTL` is correct only if the ZITADEL session
   and its refresh tokens are deleted in the same operation; session-keyed entries
   should outlive the refresh idle window.

## 7. Reconciliation as the safety net  [BINDING]

Restated as the user direction requires — and it is **not** how the system is
currently built (see §1):

| Job | Cadence | Direction rule |
|---|---|---|
| Sync lag/health check | 1 min | alerting only (§5) |
| Drift diff: ZITADEL org users + grants vs `tenant_memberships` + `identities` | nightly per tenant | mismatch in the **removal** direction (IdP says gone/inactive, we say active) → suspend + audit automatically; mismatch in the **addition** direction → report only, never auto-grant (`P4`) |
| Boot check | at worker start | run the diff before reporting healthy, so a restart after a gap does not hide one |
| Drill / proof | weekly (staging), monthly (prod, sampled) | re-run the kill-the-worker drill; a safety net that has never fired is an assumption, not a control |
| Staff access review | quarterly (V2, `TEN-32`) | human review of the same join + last-active + IdP MFA state |

Implementation: reuse the existing outbox/job convention, no new infrastructure; the
report lands in the CON health screen and the nightly run emits a metric
(`idp_reconcile_drift_found_total`).

## 8. Self-service deletion posture

ZITADEL lets a user delete their own account, and the operation is irreversible: state
→ `deleted`, all sessions and tokens revoked, the user disappears from the projection
APIs. It requires the `user.self.delete` permission, reachable only through
`ORG_USER_SELF_MANAGER` or `SELF_MANAGEMENT_GLOBAL`. Those roles do exactly one useful
thing — "read policies and delete their own account" — so withholding them costs no
other capability.

**V1 posture (recommended, D12):** **do not grant a self-delete-capable role**, and do
not ship a self-service delete button. Closure runs through us:

1. **V1 — staff runbook.** A closure request is handled by platform staff: business
   checks (open positions, non-zero balance, pending payouts, KYC retention), payout
   hold, then deactivate + revoke, then the `DELETE`/delete-user call with a scoped
   service token, with the actor recorded as `system:account-closure`.
2. **V2 — the `AUTH-35` closure flow** (already scheduled in the `docs/02` §16
   blueprint): the same steps behind a confirmed API/UI with a cool-off window, so the
   user story exists without giving away the raw IdP capability.

**Why not enable it:** ZITADEL's own guidance ("log the request in your own application
before calling the API") is an honour system — once the permission is held, the user
calls ZITADEL directly with their own token and nothing in our stack can intercept or
veto it. A trader with open positions and a balance could irreversibly remove their
login at any hour. That is a business-continuity and dispute risk, not a UX nicety.

**Enforce by detection.** The pipeline already sees role grants, so the "we did not
grant it" decision becomes a monitored invariant:

- alert on `user.grant.added` whose `roleKeys` contain `ORG_USER_SELF_MANAGER`;
- alert on `instance.member.added` whose roles contain `SELF_MANAGEMENT_GLOBAL`;
- record both in the nightly drift report and the `TEN-32` review.

**Belt-and-braces option** (self-hosted): `defaults.yaml → InternalAuthZ.RolePermissionMappings`
can strip `user.self.delete` from those roles. It is configuration, not a source patch,
so it stays within the AGPL discipline — but it must be re-verified on every upgrade,
so it is recorded as a Phase-0 option, not a default.

**Cost of the posture (honest):** users cannot self-serve erasure; requests are handled
by runbook until V2. That interacts with the DPO review (D9) and is the reason D12
carries the DPO as co-owner rather than being closed by engineering.

## 9. Re-link after deletion

A deleted user who returns gets a **new** ZITADEL user id, and our login path upserts
`identity_idp_links` (`docs/02` §3.1, review G21 / decision D13) — so the returning user
would otherwise resolve to a new identity and a duplicate membership, the failure
`G1`/`AUTH-36` exists for, now with a guaranteed trigger. Rule:

1. no **active link** match → fall back to `identity_emails.email_hash` (the immutable match key, review G35 / decision D20; `identity_key` remains as the legacy key and is never rewritten);
2. if that identity carries a self-deletion/closure marker → **never silently re-link**:
   staff approval, re-KYC where applicable — the closed link stays `state='retired'` as
   the audit alias (the link table is what makes "old `idp_user_id` retained" real);
3. `deleted_at` is set only after business closure and the retention decision — access
   revocation is immediate, erasure is a separate policy step (`AUTH-35`, D9).

## 10. Cross-check against the industry norm

The pattern chosen here is the mainstream one; the only unusual thing about our
situation is the vendor.

| Precedent | What they do | What we take |
|---|---|---|
| **Stripe** — "Process undelivered webhook events" | webhooks retried ~3 days, events retained 30 days, and a documented Events-API reconciliation for anything that failed (`delivery_success: false`) | push for latency, **poll for correctness**; same shape as §3 + §7 |
| **Okta** | log streams get two delivery attempts then Okta **deactivates the stream**; no replay; latency not guaranteed; official advice is to reconcile against the System Log API | the pull path is mandatory, not optional |
| **Google Workspace** | Directory/Drive notification channels expire (1 h default, 1 day max) and must be renewed | a TTL'd push channel can never be the only path |
| **Microsoft Entra Connect** | delta sync every 30 min (floor), full sync on demand, a documented ≤ 7-day gap rule, and health alerts on sync gaps | two-speed loop: fast delta + slower full compare (§7) |
| **Microsoft Entra provisioning** | on failure the job enters **quarantine**: retries at 6 h → 12 h → then 24 h for up to 28 days, then disables; thresholds (e.g. > 40 % or > 5,000 failures) trigger it; visible in logs + admin mail | retry → park → alert → escalate ladder (§5), with visibility in CON |
| **SailPoint / Saviynt / Entra ID Governance (IGA)** | *reconciliation* is a first-class product concept: periodically compare the IdM system against managed resources, highlight differences, optionally remediate — plus periodic certification campaigns | our §7, including the human review tier (`TEN-32`) |
| **SCIM deprovisioning practice** | soft delete is the norm: Okta never sends `DELETE` for users (`active=false`); Entra disables then deletes **30 days** later; 30–90 day retention recommended | `user.deactivated` → suspend + revoke; `user.removed` → soft terminate (§4) |
| **Consumer/product closure** | AWS keeps a closed account 90 days before content deletion; Apple gives 30 days' notice | closure is a process with a window, not an instant (§8) |

The contrast that matters: every vendor above retries at least once. ZITADEL retries
zero times ([#10268](https://github.com/zitadel/zitadel/issues/10268)) and its event
executions can break the instance ([#12225](https://github.com/zitadel/zitadel/issues/12225)) —
which is why the poller is the transport here rather than a belt-and-braces extra.

## 11. Where this lands in the build

| Artifact | Change |
|---|---|
| `docs/01` §4.1/§4.3 | `idp-sync` joins the worker topology; a delivery row for the pull path |
| `docs/02` §3.2/§3.3/§4.1/§16 | token parameters enforced; deprovisioning block + failure-mode row + secret row + observability; `user.suspended` producer; blueprint step + risks |
| `docs/04` §13 | IdP-sync lag/stall metrics in the observability stack line |
| `contracts/events/catalog.md` | `user.suspended` / `user.activated` producers gain `idp-sync` |
| `contracts/api/auth.md` | pointer: IdP-driven revocation reuses the deny-set + session-kill path |
| `docs/21` §3.2 | CON health row (IdP event sync) |
| `docs/34` §9, `docs/35` §5.1, `docs/99` Phase-0 gates | checklist items, tests, gates 6–8 |
| `docs/37` | D10, D11 (answered), D12 (open, DPO) |

Gates added (docs/99): **(6)** OIDC token lifetimes set and read back at 900 s + the
deny-set claim spike; **(7)** `idp-sync` end-to-end on the pinned version — live event
types diffed against §4, catch-up and duplicate-suppression proven, kill-the-worker
drill green; **(8)** no self-delete-capable role grants present (or a written DPO
acceptance), recorded in docs/34.

## 12. Open items

| # | Question | Default | Owner |
|---|---|---|---|
| D10 | Access/refresh token lifetimes and rotation (restates the open workbook question) | 15 min access/id, 30 min refresh idle, 30 d absolute, rotation on use + reuse detection — set at provisioning, verified by gate 6 | BE-1, Tech Lead |
| D11 | Deprovisioning propagation mechanism | `idp-sync` pull consumer over the event log (§3–§5) + nightly direction-aware reconciliation (§7); Actions v2 never the transport (§2) | BE-1 |
| D12 | Self-service account deletion | **No** self-delete-capable role grants in V1; closure via staff runbook → V2 `AUTH-35` flow; DPO sign-off on the no-self-service-erasure cost | FunderBlu COO (DPO), Tech Lead |

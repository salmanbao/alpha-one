# 30 — Error Taxonomy (Master Registry)

> **Generated aggregation** of the error taxonomies in the 26 module docs
> (each doc's §6). This is the single registry the CI gate (docs/04 §6,
> docs/28 §11) checks against: a code used in code but absent here, or an
> HTTP/status that disagrees with the module doc, fails the build. Meaning
> text is condensed from the owning doc's row; the owning doc is the
> authority. Tier: **V1** = the V1 execution-sheet baseline (exact codes,
> `contracts/errors/taxonomy.md`); **ext** = the extended (post-V1) design
> set (the same dotted convention; names provisional until that phase's
> freeze).

## 1. Global conventions (docs/04 §3.1 + the V1 baseline, binding)

- **The shape** (GW-18, every error, every surface): exactly
  `{ "code": ..., "message": ..., "correlation_id": ... }`.
  Extended (post-V1): a `details` object and `docs_url` are the V2
  addition (docs/04 §3.1).
- **Codes** are dotted `domain.action` (lowercase) — the domain is the
  module namespace (auth, ten/tenant, gw, evt, led, aud, sys, lcc/account,
  brg, evl, rsk/risk, pay/payout, chk/checkout/catalog/order, kyc, not,
  doc/document, td, adm, sup, ana/analytics, crm, con/console, bil, aff,
  cms, cmp, mig, mob, jrn, edu, cht, sdk, dvp, trd, plt, cs, public). A
  code appears in exactly one namespace; reuse across modules is a review
  failure. (Pre-baseline legacy `MODULE_TOKEN` names were mapped to this
  convention mechanically; see each doc's §6.2.)
- **HTTP semantics** (the 04 §6 mapping): 400 input, 401 auth, 403 scope/ABAC/
  state-forbidden, 404 not-found-or-not-yours (the no-oracle, 04 §6), 409 state
  machine conflict, 410 gone (reservation expired), 422 domain validation,
  423 locked (risk hold — status is an open question, taxonomy.md), 429
  rate/quota, 503 dependency down (+`Retry-After`), 500 `sys.internal` (never
  a module code at 500).
- **The 404-not-403 rule** (04 §6, 28 §3.3): a resource in another tenant (or
  another identity's) is 404, never 403 — existence is not leaked.
- **The public-safe subset** (27 Part A): public routes return only the public
  codes (the `public.*` namespace + the module codes marked public in that doc's
  §6); an internal code at the public perimeter is a CI failure.
- **Never leak**: stack traces, SQL, internal ids (ULIDs) at the public perimeter
  (the ref indirection, 27 Part A §8), PII (28 §4), the reason a key is invalid
  vs revoked (02 §3.5, same 401).
- **Deprecation**: `Deprecation` header + `public.deprecated` (200) → `410
  public.removed` after the 12-month window (27 Part A §3.5).

## 2. The registry (298 codes — 66 V1 baseline, 232 extended — across 25 modules)

### 02 — AUTH

| Code | HTTP | Meaning (from doc 02 §6) | Tier |
|---|---|---|---|
| `auth.invalid_registration` | 400 | Registration payload fails validation (incl. password policy) — "Please check your details and try again." | V1 |
| `auth.email_taken` | 409 | Email already registered on this tenant — "An account with this email already exists." | V1 |
| `auth.account_suspended` | 403 | User suspended; sessions and tokens already invalidated — "Your account has been suspended." | V1 |
| `auth.totp_required` | 401 | Staff login missing 2FA code — "Enter your two-factor code." | V1 |
| `auth.totp_invalid` | 401 | Wrong TOTP code — "That two-factor code is not valid." | V1 |
| `auth.reset_token_invalid` | 400 | Unknown/expired/used single-use reset link — "This reset link is no longer valid." | V1 |
| `auth.weak_password` | 400 | Password fails strength policy (argon2id hashing) — "Please choose a stronger password." | V1 |
| `auth.session_revoked` | 401 | Refresh token revoked or rotation reuse detected — "Your session has ended. Please log in again." | V1 |
| `auth.user_not_found` | 404 | Suspend/unsuspend target missing — "User not found." | V1 |
| `auth.user_not_suspended` | 409 | Unsuspend on a non-suspended user — "This user is not suspended." | V1 |
| `auth.cannot_suspend_self` | 400 | Admin suspending own account — "You cannot suspend your own account." | V1 |
| `auth.invalid_credentials` | 401 | Wrong email/password (identical for unknown email, V2+) | ext |
| `auth.mfa_required` | 401 | MFA challenge required (`mfa_token` returned) | ext |
| `auth.mfa_invalid` | 401 | Bad/expired TOTP code | ext |
| `auth.session_expired` | 401 | Session gone; client re-authenticates | ext |
| `auth.account_locked` | 429 | Throttled; `Retry-After` set | ext |
| `auth.password_policy_violation` | 422 | Which rule (enum list in `details`) | ext |
| `auth.tenant_not_found` | 404 | Unresolvable subdomain/domain | ext |
| `auth.tenant_suspended` | 403 | Tenant suspended — all its traffic | ext |
| `authz.denied` | 403 | Policy denial; `details.policy` names the policy | ext |
| `authz.step_up_required` | 403 | Sensitive action needs fresh 2FA | ext |
| `auth.api_key_invalid` | 401 | Unknown/revoked/expired key | ext |
| `auth.api_key_scope_missing` | 403 | Key lacks scope for route | ext |
| `auth.email_already_exists` | 409 | Registration conflict | ext |
| `auth.invitation_invalid` | 422 | Expired/used/revoked invite (V2) | ext |

### 03 — TEN

| Code | HTTP | Meaning (from doc 03 §6) | Tier |
|---|---|---|---|
| `tenant.not_found` | 404 | Tenant id unknown — "Firm not found." | V1 |
| `tenant.subdomain_taken` | 409 | Subdomain already in use — "That subdomain is already taken." | V1 |
| `tenant.subdomain_reserved` | 409 | Subdomain on reserved list (www, admin, api, console, app) — "That subdomain is reserved." | V1 |
| `tenant.suspended` | 403 | Tenant traffic denied (reason in details) | ext |
| `tenant.not_live` | 403 | `onboarding` tenant, trader-facing route | ext |
| `tenant.provisioning_failed` | 500 | Pipeline terminal failure (CON only, with step) | ext |
| `tenant.slug_taken` | 409 | Slug/subdomain conflict | ext |
| `tenant.domain_invalid` | 422 | DNS/verification failure (custom domain V1.1) | ext |
| `tenant.limit_exceeded` | 422 | `details.metric` + current/limit | ext |
| `tenant.settings_invalid` | 422 | JSON Schema violation, `details.violations[]` | ext |
| `tenant.branding_invalid` | 422 | Asset/size/CSS-safety check failed | ext |
| `tenant.kyb_required` | 403 | Staff can't activate without KYB (V1 gate) | ext |
| `tenant.plan_insufficient` | 403 | Route/module not in tenant's entitlements | ext |

### 04 — GW+EVT

| Code | HTTP | Meaning (from doc 04 §6) | Tier |
|---|---|---|---|
| `tenant.unknown_host` | 404 | Domain/subdomain does not resolve to a tenant — "This address does not belong to a registered firm." | V1 |
| `auth.invalid_credentials` | 401 | Missing/invalid token or login failed — identical for unknown email and wrong password (enumeration-resistant) — "Email or password is incorrect." | V1 |
| `permission.denied` | 403 | Role lacks the route's `resource.action` key — "You do not have access to this action." | V1 |
| `rate.limited` | 429 | Per-IP/per-user rate limit exceeded — "Too many requests. Try again shortly." | V1 |
| `request.idempotency_conflict` | 409 | Idempotency key reused with different request body — "Request already processed with different data." | V1 |
| `tenant.suspended` | 403 | Tenant suspended: logins, new orders, payouts stop — "This firm is currently suspended." | V1 |
| `tenant.not_entitled` | 403 | Module disabled for tenant — "This feature is not part of your plan." | V1 |
| `module.unknown` | 400 | Entitlement change references a non-V1 module — "Unknown module." | V1 |
| `gw.unresolved_tenant` | 404 | (public shape = `TENANT_NOT_FOUND`) | ext |
| `gw.unauthorized` | 401 | Missing/invalid credentials | ext |
| `gw.forbidden` | 403 | Authz denial (policy id in details) | ext |
| `gw.rate_limited` | 429 | `Retry-After` set; scope in details (ip/user/tenant) | ext |
| `gw.quota_exceeded` | 429 | Plan quota; `details.metric` | ext |
| `gw.module_disabled` | 403 | Entitlement gate (module not enabled for tenant) | ext |
| `gw.idempotency_conflict` | 422 | Key reused with different body | ext |
| `gw.payload_too_large` | 413 | Body over limit | ext |
| `gw.timeout` | 504 | Handler exceeded budget | ext |
| `gw.maintenance` | 503 | Maintenance mode | ext |
| `gw.method_not_allowed` | 405 | — | ext |
| `evt.webhook_signature_invalid` | 401 | Ingress: bad provider signature | ext |
| `evt.webhook_schema_invalid` | 422 | Ingress: payload failed schema | ext |
| `evt.webhook_duplicate` | 200 | Ingress: already processed (idempotent 200) | ext |
| `evt.consumer_dlq` | — | Internal: consumer gave up (alert + DLQ row) | ext |
| `evt.relay_stopped` | — | Internal CRITICAL: relay not publishing 60 s | ext |

### 05 — LED/AUD

| Code | HTTP | Meaning (from doc 05 §6) | Tier |
|---|---|---|---|
| `led.entry_unbalanced` | 500 | Constraint should catch this; surfaced as bug alert | ext |
| `led.account_not_found` | 404 | Unknown account code | ext |
| `led.account_closed` | 422 | Posting to closed account | ext |
| `led.idempotency_conflict` | 422 | Same key, different entry payload | ext |
| `led.entry_already_reversed` | 409 | Double reversal | ext |
| `led.reversal_requires_reason` | 422 | — | ext |
| `led.reconciliation_mismatch` | — | Internal (exception event, never a client error) | ext |
| `aud.export_limited` | 429 | Export quota (scope too broad / too frequent) | ext |
| `aud.scope_denied` | 403 | Export/audit query exceeds role scope | ext |
| `aud.write_failed` | — | Internal CRITICAL: audit write failed (fail-closed: the business action is rolled back and alerted) | ext |

### 07 — LCC

| Code | HTTP | Meaning (from doc 07 §6) | Tier |
|---|---|---|---|
| `account.not_found` | 404 | Account unknown or not owned by caller — "Account not found." | V1 |
| `account.not_active` | 409 | Action invalid from current state — "This action is not available for this account." | V1 |
| `account.terminal_state` | 409 | Operation on FAILED/TERMINATED account — "This account is closed." | V1 |
| `account.not_suspended` | 409 | Resume on non-suspended account — "This account is not suspended." | V1 |
| `lcc.account_not_found` | 404 | (cross-tenant probe → same 404) | ext |
| `lcc.state_conflict` | 409 | Transition not allowed from current state (`details.from`, `details.event`) | ext |
| `lcc.transition_conflict` | 409 | Optimistic-lock conflict after retries (alerted internally) | ext |
| `lcc.broker_provisioning_failed` | 502 | Broker-side create failed (`details.reason` provider-safe) | ext |
| `lcc.kyc_gate` | 422 | Funding/payout blocked by KYC level (`details.required`) | ext |
| `lcc.paused` | 422 | Action not allowed while paused | ext |
| `lcc.suspended` | 403 | Account suspended (risk) | ext |
| `lcc.terms_frozen` | 409 | Attempt to modify live-account terms | ext |
| `lcc.time_limit` | 422 | (V2) Time extension unavailable (already used) | ext |
| `lcc.enforcement_duplicate` | — | Internal: duplicate enforcement command (idempotent no-op, logged) | ext |

### 08 — BRG

| Code | HTTP | Meaning (from doc 08 §6) | Tier |
|---|---|---|---|
| `brg.provider_auth` | — | Our MetaApi key rejected (rotated? revoked?) | ext |
| `brg.provider_unavailable` | — | MetaApi 5xx/timeout; circuit handles | ext |
| `brg.account_not_found` | — | Login gone broker-side (closed manually? → page ops) | ext |
| `brg.account_exists` | — | Provisioning got "already exists" (idempotent path: adopt or fail) | ext |
| `brg.capacity` | 503 | Server group full / MetaApi quota — account cap guard | ext |
| `brg.command_failed` | — | Execution failed after retries (reason in command result) | ext |
| `brg.command_conflict` | — | Broker state contradicted preconditions (e.g. position already closed) → confirm path | ext |
| `brg.sync_gap` | — | Deal discontinuity (event + ADM review) | ext |
| `brg.credentials_missing` | — | Provisioned account missing creds (should never happen) | ext |
| `brg.symbol_unknown` | — | Normalization hit unmapped symbol (BRG-32 V2 mapping mgmt; V1: alert + skip with log) | ext |

### 09 — EVL

| Code | HTTP | Meaning (from doc 09 §6) | Tier |
|---|---|---|---|
| `challenge.not_found` | 404 | Challenge id unknown — "Challenge not found." | V1 |
| `challenge.invalid_config` | 400 | Challenge phases/rules/pricing inconsistent — "Please check the challenge configuration." | V1 |
| `ruleset.not_found` | 404 | Rule set unknown — "Rule set not found." | V1 |
| `ruleset.invalid_rules` | 400 | Rule payload fails validation — "Please check the rule values." | V1 |
| `override.action_unknown` | 400 | Manual override action not in pass/fail/reset — "Unknown override action." | V1 |
| `override.reason_required` | 400 | Manual override without recorded reason — "A reason is required." | V1 |
| `account.not_found` | 404 | Account unknown or not owned by caller — "Account not found." | V1 |
| `account.not_active` | 409 | Action invalid from current state — "This action is not available for this account." | V1 |
| `account.terminal_state` | 409 | Operation on FAILED/TERMINATED account — "This account is closed." | V1 |
| `account.not_suspended` | 409 | Resume on non-suspended account — "This account is not suspended." | V1 |
| `evl.state_conflict` | — | — | ext |
| `evl.rulepack_invalid` | — | — | ext |
| `evl.rulepack_conflict` | — | — | ext |
| `evl.input_mismatch` | — | — | ext |
| `evl.tick_stale` | — | — | ext |
| `evl.unknown_rule_kind` | — | — | ext |
| `evl.override_invalid` | — | — | ext |
| `evl.metric_unavailable` | — | — | ext |

### 10 — RSK

| Code | HTTP | Meaning (from doc 10 §6) | Tier |
|---|---|---|---|
| `risk.account_not_found` | 404 | Case target account unknown — "Account not found." | V1 |
| `risk.case_already_open` | 409 | Second open case on same account — "A review case is already open." | V1 |
| `rsk.case_not_found` | 404 | — | ext |
| `rsk.case_closed` | 409 | Action on decided case (use appeal, V2) | ext |
| `rsk.signal_required` | 422 | Open case without signal/reason | ext |
| `rsk.decision_conflict` | 409 | Concurrent decision (optimistic lock) | ext |
| `rsk.hold_not_active` | 409 | Release without hold | ext |
| `rsk.allowlist_invalid` | 422 | (V2) Allowlist entry malformed | ext |
| `rsk.detector_disabled` | 422 | (V2) Trigger detector that's disabled | ext |

### 11 — PAY

| Code | HTTP | Meaning (from doc 11 §6) | Tier |
|---|---|---|---|
| `payout.ineligible` | 422 | Failed an eligibility check; sub-reasons from PAY-03: KYC not approved (KYC-08), minimum trading days, consistency, trading day threshold, first withdrawal... | V1 |
| `payout.kyc_required` | 422 | Payout gate blocked pending KYC approval — "Verify your identity before requesting a payout." | V1 |
| `payout.risk_hold` | 423 | Open risk case (RSK-11) or active suspension (PAY-04) — "Payouts are temporarily held for review." | V1 |
| `payout.not_funded` | 409 | Account not in FUNDED state — "Payouts are only available on funded accounts." | V1 |
| `payout.amount_exceeds_available` | 422 | Beyond available profit (balance+equity − initial − prior payouts) — "Amount exceeds your available profit." | V1 |
| `payout.schedule_not_due` | 422 | Frequency or next-withdrawal-date not reached — "Your next payout is available on {date}." | V1 |
| `payout.method_not_confirmed` | 400 | Payout method not confirmed — "Confirm your payout method first." | V1 |
| `payout.invalid_address` | 400 | Chain-specific crypto address validation failed — "That wallet address is not valid for {chain}." | V1 |
| `payout.method_invalid` | 400 | Payout method details invalid — "Please check your payout details." | V1 |
| `payout.not_pending_approval` | 409 | Approve/reject on a payout not pending approval — "This payout has already been decided." | V1 |
| `payout.not_approved` | 409 | Execution recording on a non-approved payout — "This payout is not approved for execution." | V1 |
| `payout.reason_required` | 400 | Reject without recorded reason — "A reason is required." | V1 |
| `payout.no_approved_payouts` | 422 | Batch export contains no approved payouts — "Nothing to export." | V1 |
| `payout.execution_mismatch` | 400 | Recorded execution amount ≠ approved amount — "Recorded amount does not match the approved payout." | V1 |
| `payout.policy_invalid` | 400 | Payout policy configuration invalid — "Please check the payout policy values." | V1 |
| `pay.not_eligible` | 422 | Eligibility failed (each failed check named) | ext |
| `pay.frequency` | 422 | Window not elapsed (`details.next_eligible_at`) | ext |
| `payout.below_min` | 422 | `details.min_cents` | ext |
| `payout.active_exists` | 409 | Existing active request (id in details) | ext |
| `payout.nothing_due` | 422 | Available = 0 | ext |
| `pay.stale_data` | 409 | Snapshot older than 10 min — retry (transient) | ext |
| `pay.method_invalid` | 422 | Address/format failed (chain named) | ext |
| `pay.method_changed_recently` | 200 | Warning flag, not a block (V2) | ext |
| `pay.approval_required` | 403 | Self-serve approve attempt (no such route; defense-in-depth) | ext |
| `pay.state_conflict` | 409 | Illegal transition attempt | ext |
| `pay.rail_unavailable` | 503 | Circuit open (`details.retry_after`) | ext |
| `pay.rail_rejected` | — | Provider rejected (reason stored, retried per policy) | ext |
| `pay.amount_adjusted` | — | Finance adjustment applied (audit) | ext |

### 12 — CHK

| Code | HTTP | Meaning (from doc 12 §6) | Tier |
|---|---|---|---|
| `catalog.challenge_not_found` | 404 | Challenge not in tenant catalog — "This challenge is no longer available." | V1 |
| `checkout.coupon_invalid` | 400 | Coupon rejected at session reservation — "This coupon code is not valid." | V1 |
| `checkout.session_expired` | 410 | Price/coupon reservation window elapsed — "Your checkout session expired. Please start again." | V1 |
| `checkout.session_not_found` | 404 | Checkout session unknown or not owned by caller — "Checkout session not found." | V1 |
| `checkout.session_not_cancellable` | 409 | Session already completed or expired — nothing to cancel — "This checkout session can no longer be cancelled." | V1 |
| `order.not_found` | 404 | Order unknown or not owned by caller — "Order not found." | V1 |
| `order.not_retryable` | 409 | Payment not in a recoverable state — "This payment cannot be retried." | V1 |
| `receipt.not_ready` | 409 | PDF generation pending — "Your receipt is being prepared." | V1 |
| `webhook.signature_invalid` | 401 | Provider webhook signature failed — none (provider-facing) | V1 |
| `chk.order_invalid` | 422 | Package/rule-set combo not purchasable (TEN validation) | ext |
| `chk.package_unavailable` | 422 | Package deactivated mid-checkout (price snapshot protects existing intents) | ext |
| `chk.method_not_allowed` | 422 | Rail not enabled for tenant/currency (provider matrix) | ext |
| `chk.login_required` | 401 | Guest checkout (login-first policy) | ext |
| `chk.intent_expired` | 409 | Tries to pay a dead intent (new intent offered) | ext |
| `chk.intent_conflict` | 409 | Concurrent webhook state race (last-write validated by state machine) | ext |
| `chk.capture_mismatch` | 500 | Webhook amount ≠ intent (anomaly → anomaly ticket, not auto-accept) | ext |
| `chk.refund_window_closed` | 422 | Trader request outside policy window | ext |
| `chk.refund_conflict` | 409 | Refund on already-refunded/chargeback'd intent | ext |
| `chk.provider_unavailable` | 503 | Circuit open (alternate rails suggested in response) | ext |
| `chk.wire_awaiting_confirmation` | 200 | Wire not yet confirmed (72 h policy info) | ext |
| `chk.fx_unavailable` | 422 | Currency unsupported for rail (V2) | ext |
| `chk.chargeback_active` | 409 | New refund while chargeback open | ext |

### 13 — KYC

| Code | HTTP | Meaning (from doc 13 §6) | Tier |
|---|---|---|---|
| `kyc.country_restricted` | 403 | Registration/verification from restricted jurisdiction — "Verification is not available in your country." | V1 |
| `kyc.already_in_progress` | 409 | Session creation while one is active — "You already have a verification in progress." | V1 |
| `kyc.upload_failed` | 400 | Manual upload failed (retriable) — "Upload failed. Please try again." | V1 |
| `kyc.case_not_reviewable` | 409 | Manual decision on a case not in review — "This case is no longer reviewable." | V1 |
| `account.underage` | 403 | Verified age under 18 — "You must be 18 or older." | V1 |
| `kyc.required` | 422 | Gate fail (consumers wrap: CHK `chk.login_required`? no — each consumer uses its own code; this is the KYC-internal result) | ext |
| `kyc.country_blocked` | 422 | Self-declared country in blocklist | ext |
| `kyc.age` | 422 | Under minimum (at decision time) | ext |
| `kyc.session_expired` | 409 | Provider session dead (new session offered) | ext |
| `kyc.session_limit` | 429 | Rate limit (V2 KYC-29; V1: 3 sessions/level/day) | ext |
| `kyc.docs_invalid` | 422 | Upload failed (size/type/corrupt) | ext |
| `kyc.state_conflict` | 409 | Illegal transition (e.g. decide a verified session) | ext |
| `kyc.provider_unavailable` | 503 | Veriff circuit open (manual-upload path still works) | ext |
| `kyc.provider_mismatch` | 500 | Webhook state inconsistent with session (anomaly ticket) | ext |
| `kyc.reinitial_cooldown` | 429 | V1 24 h cooldown after rejection | ext |
| `kyc.level_mismatch` | 422 | L2 session attempted before L1 verified | ext |

### 14 — NOT

| Code | HTTP | Meaning (from doc 14 §6) | Tier |
|---|---|---|---|
| `not.template_not_found` | 500 | Mapping references missing template (deploy error — CRITICAL alert) | ext |
| `not.vars_invalid` | 500 | vars_selector produced empty/PII-guarded vars (alert + skip, never send half-rendered) | ext |
| `not.recipoent_unknown` | 500 | No email/identity (alert — usually a data bug) | ext |
| `not.provider_unavailable` | 503 | Postmark down (retry queue drains on recovery; critical templates page ops) | ext |
| `not.rate_limited` | 429 | (V2) Per-recipient/template cap hit (batched into digest) | ext |
| `not.suppressed` | — | Info state (not an error) | ext |
| `not.broadcast_validation` | 422 | (V2) Broadcast preview failed | ext |
| `not.tg_not_linked` | — | (V2) Telegram channel skipped (in-app fallback) | ext |

### 15 — DOC

| Code | HTTP | Meaning (from doc 15 §6) | Tier |
|---|---|---|---|
| `document.not_found` | 404 | Document unknown or not owned — "Document not found." | V1 |
| `doc.not_found` | 404 | Document id unknown | ext |
| `doc.pending` | 409 | URL requested before generation finished (TD shows "preparing…") | ext |
| `doc.state_missing` | 500 | Mapper found no source state (data bug — CRITICAL alert) | ext |
| `doc.render_failed` | 500 | Template/Puppeteer failure (retry; 3× → DLQ) | ext |
| `doc.upload_failed` | 500 | R2 write failed (retry) | ext |
| `doc.template_version_missing` | 500 | Deploy mismatch (template not in worker) — CI check prevents | ext |
| `doc.verify_not_found` | 404 | Unknown cert hash (page says "not found", no detail) | ext |
| `doc.bulk_limit` | 422 | (V2) Bulk size over cap | ext |

### 16 — TD

| Code | HTTP | Meaning (from doc 16 §6) | Tier |
|---|---|---|---|
| `auth.expired` | 401 | full-screen re-login (state preserved via query) | ext |
| `tenant.not_found` | 404 | "site not found" (04: 404-not-403 posture) | ext |
| `rate.limited` | 429 | inline "slow down, try in {n}s" | ext |
| `gw.internal` | — | error boundary: retry button + ticket pre-fill + Sentry id shown | ext |
| `stream.lost` | — | polling fallback + amber chip (not an error screen) | ext |
| `render.stale` | — | amber "data from {time}" banner (honesty over polish) | ext |

### 17 — ADM

| Code | HTTP | Meaning (from doc 17 §6) | Tier |
|---|---|---|---|
| `stepup.expired` | 403 | 2FA dialog reopens (object preserved) | ext |
| `forbidden.role` | 403 | "you need {role}" + link to settings (ADM-17 V2) | ext |
| `export.busy` | 429 | queue position shown (V2) | ext |

### 18 — SUP

| Code | HTTP | Meaning (from doc 18 §6) | Tier |
|---|---|---|---|
| `sup.ticket_not_found` | 404 | — (ownership check returns 404, never 403 — 04 posture) | ext |
| `sup.closed` | 409 | Reply on a closed ticket (reopen = staff action) | ext |
| `sup.category_unknown` | 422 | Category not in the registry (V2) | ext |
| `sup.attachment_invalid` | 422 | Type/size violation | ext |
| `sup.duplicate_open` | 200 | (V2) Similar open ticket exists (same trader+category+account, < 7 days) — the create response includes it; trader chooses | ext |
| `sup.rate_limited` | 429 | Trader ticket-create cap (5/day — abuse control, V2 SUP-30 family) | ext |
| `sup.field_required` | 422 | Domain-specific type missing its required object ref (V2) | ext |
| `sup.satisfaction_expired` | 409 | Survey window passed (V2) | ext |

### 19 — ANA

| Code | HTTP | Meaning (from doc 19 §6) | Tier |
|---|---|---|---|
| `ana.model_stale` | 409 | Read model lag > threshold (UI: "data from {as_of}" banner — the ANA-14 label, surfaced as a soft error) | ext |
| `ana.report_not_found` | 404 | Unknown report id (V2) | ext |
| `ana.report_params_invalid` | 422 | (V2) Bad report params | ext |
| `ana.report_running` | 409 | Duplicate concurrent run (return the existing run id) | ext |
| `ana.export_limit` | 429 | (V2) Concurrent export cap | ext |
| `ana.threshold_invalid` | 422 | (V2) Alert rule malformed | ext |
| `ana.rebuild_window_exceeded` | 422 | (V2) Rebuild older than the events log window (13 mo) | ext |
| `ana.consumer_lag` | — | Ops metric → CON alert (not an API code) | ext |

### 20 — CRM

| Code | HTTP | Meaning (from doc 20 §6) | Tier |
|---|---|---|---|
| `crm.segment_not_found` | 404 | — | ext |
| `crm.segment_empty` | 200 | Campaign on an empty segment (allowed; the confirmation shows "0 recipients") | ext |
| `crm.campaign_sending` | 409 | Duplicate send trigger | ext |
| `crm.template_invalid` | 422 | (V3) Template render failure in preview | ext |
| `crm.consent_missing` | 422 | Marketing send attempted without consent capture point configured (V3) | ext |
| `crm.sequence_version_replaced` | — | Info: active runs exit at next step | ext |
| `crm.unsubscribe_unknown` | 404 | Bad token (page: "nothing to do here", no leak of validity) | ext |

### 21 — CON

| Code | HTTP | Meaning (from doc 21 §6) | Tier |
|---|---|---|---|
| `console.session_not_found` | 404 | Session id unknown — "Session not found." | V1 |
| `console.cannot_revoke_self` | 400 | Revoking own session via admin endpoint — "You cannot revoke your own session here." | V1 |
| `con.platform_role_required` | 403 | Non-platform session on a console route (structural deny — also logged as a security event) | ext |
| `con.tenant_not_found` | 404 | — | ext |
| `con.saga_blocked` | 409 | Provisioning step can't retry (blocker named) | ext |
| `con.approval_required` | 403 | Nuclear action without the V2 second operator | ext |
| `con.approval_expired` | 409 | Approval window (10 min) passed | ext |
| `con.self_approval` | 403 | B == A (structural deny, security event) | ext |
| `con.impersonation_read_only` | 403 | State-changing call under a view-as token | ext |
| `con.impersonation_denied` | 403 | Deny-listed action (payout approve etc. — security event + CRITICAL) | ext |
| `con.control_active` | 409 | Can't arm a control that's already active | ext |
| `con.suspension_terminal` | 409 | Act on a terminated tenant (retention reads only) | ext |

### 22 — BIL

| Code | HTTP | Meaning (from doc 22 §6) | Tier |
|---|---|---|---|
| `bil.tenant_not_billable` | 422 | Metering/invoice op on a contract-mode tenant in V1/V2 (the era guard — the API says "manual mode; record in console") | ext |
| `bil.plan_invalid` | 422 | (V3) Plan/limit mismatch | ext |
| `bil.approval_required` | 403 | Manual invoice issue without two-op (V2+) | ext |
| `bil.state_conflict` | 409 | Subscription transition conflict (e.g. pause on an already-terminated tenant) | ext |
| `bil.metering_stale` | 409 | Invoice computed before the metering rollup completed (retry — the rollup is nightly; same-day invoices use yesterday's + a flag) | ext |
| `bil.gateway_unavailable` | 503 | (V3) Payment provider down (invoice stays issued; dunning clock is provider-tolerant) | ext |
| `bil.pass_through_unconfigured` | 422 | (V3) Provider cost line with no margin config (fail closed: the invoice can't be issued with an unknown pass-through) | ext |

### 23 — AFF

| Code | HTTP | Meaning (from doc 23 §6) | Tier |
|---|---|---|---|
| `aff.not_approved` | 403 | Non-affiliate calling affiliate APIs (the dashboard/API surface) | ext |
| `aff.self_referral` | 422 | Attribution attempt blocked (the signup surfaces "no referral applied") | ext |
| `aff.attribution_expired` | — | Window (30 d) passed at signup (no attribution, not an error to the trader) | ext |
| `aff.coupon_invalid` | 422 | (CHK wraps: the checkout code check) | ext |
| `aff.tax_form_required` | 422 | Payout request without a current tax form | ext |
| `aff.below_minimum` | 422 | Settled balance < payout minimum | ext |
| `aff.fraud_hold` | 423 | Payout blocked by hold (reason class: "under review") | ext |
| `aff.payout_state_conflict` | 409 | Duplicate payout request (one active per affiliate) | ext |
| `aff.rate_card_missing` | 500 | Capture with ref but no effective rate card (fail: accrue at 0 + CRITICAL — never guess a rate) | ext |
| `aff.tier_depth_exceeded` | — | Depth-3+ link ignored (structural cap, logged) | ext |

### 24 — CMS/CMP

| Code | HTTP | Meaning (from doc 24 §6) | Tier |
|---|---|---|---|
| `cms.page_not_found` | 404 | Public 404 (the tenant's branded 404 page) | ext |
| `cms.block_schema_invalid` | 500 | Data failed its block schema (editor bug or a corrupt publish — the page renders without the bad block + CRITICAL alert; never a blank page) | ext |
| `cms.publish_conflict` | 409 | Concurrent publish (last-write wins on the pointer, the losing editor is told with a diff) | ext |
| `cms.scheduled_conflict` | 409 | Schedule on an already-live time (the worker skips + alerts) | ext |
| `cms.media_too_large` | 422 | Upload over the block-type limit (images 5 MB) | ext |
| `cms.form_rate_limited` | 429 | Lead form abuse (the honeypot + limit pair) | ext |
| `cms.legal_review_required` | 403 | Legal page publish without the review note (2FA'd override by owner role) | ext |
| `cms.tenant_not_provisioned` | 404 | No site for this tenant (the static fallback renders) | ext |

### 25 — MIG

| Code | HTTP | Meaning (from doc 25 §6) | Tier |
|---|---|---|---|
| `mig.export_schema_invalid` | 422 | The TTS export doesn't match the expected schema (the class is rejected before any row lands — fail at the door, not mid-import) | ext |
| `mig.manifest_mismatch` | 409 | Row counts vs the TTS manifest differ (the import halts; the diff is the first artifact) | ext |
| `mig.mapping_missing` | 409 | A source value has no mapping (state/term) — the row is an exception, the import continues, the halt-at-gate is on the report | ext |
| `mig.dry_run_failed` | 409 | The dry-run reconciliation gate failed (the real run is structurally blocked — the state machine enforces `dry_run_passed` before `importing`) | ext |
| `mig.cutover_gate_closed` | 409 | Cutover attempted with undispositioned exceptions | ext |
| `mig.parallel_drift` | — | (internal) the daily comparator exceeded tolerance (a P1 event, not an API error) | ext |
| `mig.correction_rejected` | 409 | A correction on an already-corrected row (the chain: corrections are sequential, one per row per cycle) | ext |
| `mig.tenant_not_ready` | 409 | Import attempted before the saga/tenant state allows (the tenant must be `active` with the MIG entitlement) | ext |
| `mig.kyc_reverify_outstanding` | — | (informational) traders blocked at payout by the §3.3 gate — surfaced in the concierge dashboard, not an error | ext |

### 26 — MOB/JRN/EDU/CHT

| Code | HTTP | Meaning (from doc 26 §6) | Tier |
|---|---|---|---|
| `device.token_expired` | 401 | full login (the biometric path is re-enrolled after) | ext |
| `min.client_version` | 426 | the update nudge (the store deep link) + the read-only banner | ext |
| `push.token_invalid` | — | silent (the next push registration heals it) | ext |
| `chart.degraded` | — | the native fallback: the numbers table (the chart is an enhancement, the numbers are the product) | ext |
| `biometric.unavailable` | — | the full login (the feature degrades, the app doesn't) | ext |

### 27 — SDK/DVP/TRD/PLT/CS

| Code | HTTP | Meaning (from doc 27 §6) | Tier |
|---|---|---|---|
| `public.auth_invalid` | 401 | The key is invalid/revoked (the no-detail leak — the 04 posture: the invalid key and the revoked key are the same 401, the oracle ban, the 02 §3.4 posture) | ext |
| `public.scope_missing` | 403 | The key lacks the scope (the scope name in the `details` — the developer's fix is the scope request, the actionable error) | ext |
| `public.rate_limited` | 429 | The tier limit (the `Retry-After`, the `X-RateLimit-*`, the tier name) | ext |
| `public.env_mismatch` | 403 | A test key on a live route / a live key on a sandbox route (the environment claim check, the §1 binding) | ext |
| `public.id_not_found` | 404 | The object (the tenant scope: another tenant's object = the 404, the 04 posture, the cross-tenant oracle ban) | ext |
| `public.webhook_signature_invalid` | — | (the developer's side, the SDK-03 error class, the docs' troubleshooting) | ext |
| `public.checkout_session_expired` | 409 | The checkout link dead (the TTL, the 12 §3.2 class) | ext |
| `public.payout_manual_approval` | 202 | The API payout request accepted (the **always-manual rule, the §3.1** — the 202 + the `status: pending_approval`, the "the machine's request waits for the... | ext |
| `public.deprecated` | 200 | The 12-month window (the header: the sunset date, the migration URL, the SDK-15 contract) | ext |
| `public.removed` | 410 | The end-of-life (the migration header, the labeled removal) | ext |
| `public.kyc_sync_rejected` | 422 | The SDK-11 sync (the provider unrecognized, the tenant config `external_accepted: false`, the state conflict) | ext |
| `sandbox.inject_invalid` | 422 | The SDK-06 (the event unknown, the payload schema fail) | ext |
| `sandbox.live_only` | 404 | The sandbox route on a live tenant (the structural ban, the §1 rule — the 404, not the 403, the route-existence oracle ban) | ext |


# Error Taxonomy

Status: DRAFT
Owner: TBD
Version: v1
Last updated: TODO

Derived from the V1 Execution Sheet (V1.0 / V1.1) of `Alpha One PRD.xlsx`.
Envelope per GW-18: every error response carries exactly `code`, `message`, `correlation_id`.

## Gateway / platform (GW)

| Code | HTTP | Meaning | User-facing message pattern | Module |
|---|---|---|---|---|
| `tenant.unknown_host` | 404 | Domain/subdomain does not resolve to a tenant | "This address does not belong to a registered firm." | GW (impl: TEN-02, GW-02) |
| `auth.invalid_credentials` | 401 | Missing/invalid token or login failed — identical for unknown email and wrong password (enumeration-resistant) | "Email or password is incorrect." | GW (impl: GW-03, AUTH-04) |
| `permission.denied` | 403 | Role lacks the route's `resource.action` key | "You do not have access to this action." | GW (impl: GW-04, AUTH-13) |
| `rate.limited` | 429 | Per-IP/per-user rate limit exceeded | "Too many requests. Try again shortly." | GW (impl: GW-05) |
| `request.idempotency_conflict` | 409 | Idempotency key reused with different request body | "Request already processed with different data." | GW (impl: GW-12) |
| `tenant.suspended` | 403 | Tenant suspended: logins, new orders, payouts stop | "This firm is currently suspended." | GW/TEN (impl: TEN-15) |
| `tenant.not_entitled` | 403 | Module disabled for tenant | "This feature is not part of your plan." | GW/TEN (impl: TEN-08; code naming — TODO — needs owner decision) |
| `module.unknown` | 400 | Entitlement change references a non-V1 module | "Unknown module." | TEN (impl: TEN-08) |

## Auth (AUTH)

| Code | HTTP | Meaning | User-facing message pattern | Module |
|---|---|---|---|---|
| `auth.invalid_registration` | 400 | Registration payload fails validation (incl. password policy) | "Please check your details and try again." | AUTH (impl: AUTH-01, AUTH-17) |
| `auth.email_taken` | 409 | Email already registered on this tenant | "An account with this email already exists." | AUTH (impl: AUTH-01) — enumeration-safety treatment — TODO — needs owner decision |
| `auth.account_suspended` | 403 | User suspended; sessions and tokens already invalidated | "Your account has been suspended." | AUTH (impl: AUTH-20) |
| `auth.totp_required` | 401 | Staff login missing 2FA code | "Enter your two-factor code." | AUTH (impl: AUTH-09) |
| `auth.totp_invalid` | 401 | Wrong TOTP code | "That two-factor code is not valid." | AUTH (impl: AUTH-09) |
| `auth.reset_token_invalid` | 400 | Unknown/expired/used single-use reset link | "This reset link is no longer valid." | AUTH (impl: AUTH-05) |
| `auth.weak_password` | 400 | Password fails strength policy (argon2id hashing) | "Please choose a stronger password." | AUTH (impl: AUTH-17) |
| `auth.session_revoked` | 401 | Refresh token revoked or rotation reuse detected | "Your session has ended. Please log in again." | AUTH (impl: AUTH-07) |
| `auth.user_not_found` | 404 | Suspend/unsuspend target missing | "User not found." | AUTH (impl: AUTH-20, AUTH-43) |
| `auth.user_not_suspended` | 409 | Unsuspend on a non-suspended user | "This user is not suspended." | AUTH (impl: AUTH-43) |
| `auth.cannot_suspend_self` | 400 | Admin suspending own account | "You cannot suspend your own account." | AUTH (impl: AUTH-20) — rule — TODO — needs owner decision |

## Tenant (TEN)

| Code | HTTP | Meaning | User-facing message pattern | Module |
|---|---|---|---|---|
| `tenant.not_found` | 404 | Tenant id unknown | "Firm not found." | TEN (impl: TEN-01) |
| `tenant.subdomain_taken` | 409 | Subdomain already in use | "That subdomain is already taken." | TEN (impl: TEN-42) |
| `tenant.subdomain_reserved` | 409 | Subdomain on reserved list (www, admin, api, console, app) | "That subdomain is reserved." | TEN (impl: TEN-42) |

## Checkout (CHK)

| Code | HTTP | Meaning | User-facing message pattern | Module |
|---|---|---|---|---|
| `catalog.challenge_not_found` | 404 | Challenge not in tenant catalog | "This challenge is no longer available." | CHK (impl: CHK-01) |
| `checkout.coupon_invalid` | 400 | Coupon rejected at session reservation | "This coupon code is not valid." | CHK (impl: CHK-02 coupon reservation; earlier draft `checkout.invalid_coupon`/CHK-11 is NOT a V1 row — code naming — TODO — needs owner decision) |
| `checkout.session_expired` | 410 | Price/coupon reservation window elapsed | "Your checkout session expired. Please start again." | CHK (impl: CHK-02) |
| `checkout.session_not_found` | 404 | Checkout session unknown or not owned by caller | "Checkout session not found." | CHK (impl: CHK-44 identity scoping) |
| `checkout.session_not_cancellable` | 409 | Session already completed or expired — nothing to cancel | "This checkout session can no longer be cancelled." | CHK (impl: CHK-44 "pending checkout session"; state guard — TODO — needs owner decision) |
| `order.not_found` | 404 | Order unknown or not owned by caller | "Order not found." | CHK (impl: CHK-16, CHK-40) |
| `order.not_retryable` | 409 | Payment not in a recoverable state | "This payment cannot be retried." | CHK (impl: CHK-16) |
| `receipt.not_ready` | 409 | PDF generation pending | "Your receipt is being prepared." | CHK/DOC (impl: CHK-17, DOC-01) |
| `webhook.signature_invalid` | 401 | Provider webhook signature failed | none (provider-facing) | CHK/KYC (impl: EVT-10) |

## Payout (PAY)

| Code | HTTP | Meaning | User-facing message pattern | Module |
|---|---|---|---|---|
| `payout.ineligible` | 422 | Failed an eligibility check; sub-reasons from PAY-03: KYC not approved (KYC-08), minimum trading days, consistency, trading day threshold, first withdrawal delay, next withdrawal date, min/max limits, account status | "You are not eligible for a payout yet: {reason}." | PAY (impl: PAY-03, KYC-08) |
| `payout.kyc_required` | 422 | Payout gate blocked pending KYC approval | "Verify your identity before requesting a payout." | KYC/PAY (impl: KYC-08; code naming — TODO — needs owner decision: dedicated code vs `payout.ineligible` sub-reason) |
| `payout.risk_hold` | 423/403 | Open risk case (RSK-11) or active suspension (PAY-04) | "Payouts are temporarily held for review." | PAY (impl: PAY-04, RSK-11) — HTTP status — TODO — needs owner decision |
| `payout.not_funded` | 409 | Account not in FUNDED state | "Payouts are only available on funded accounts." | PAY (impl: PAY-01, LCC-02) |
| `payout.amount_exceeds_available` | 422 | Beyond available profit (balance+equity − initial − prior payouts) | "Amount exceeds your available profit." | PAY (impl: PAY-02) |
| `payout.schedule_not_due` | 422 | Frequency or next-withdrawal-date not reached | "Your next payout is available on {date}." | PAY (impl: PAY-21, LCC-20) |
| `payout.method_not_confirmed` | 400 | Payout method not confirmed | "Confirm your payout method first." | PAY (impl: PAY-05) |
| `payout.invalid_address` | 400 | Chain-specific crypto address validation failed | "That wallet address is not valid for {chain}." | PAY (impl: PAY-45) |
| `payout.method_invalid` | 400 | Payout method details invalid | "Please check your payout details." | PAY (impl: PAY-05) |
| `payout.not_pending_approval` | 409 | Approve/reject on a payout not pending approval | "This payout has already been decided." | PAY (impl: PAY-13) |
| `payout.not_approved` | 409 | Execution recording on a non-approved payout | "This payout is not approved for execution." | PAY (impl: PAY-12, PAY-13) |
| `payout.reason_required` | 400 | Reject without recorded reason | "A reason is required." | PAY (impl: PAY-09) |
| `payout.no_approved_payouts` | 422 | Batch export contains no approved payouts | "Nothing to export." | PAY (impl: PAY-44) |
| `payout.execution_mismatch` | 400 | Recorded execution amount ≠ approved amount | "Recorded amount does not match the approved payout." | PAY (impl: PAY-12) — rule — TODO — needs owner decision |
| `payout.policy_invalid` | 400 | Payout policy configuration invalid | "Please check the payout policy values." | PAY (impl: PAY-38) |

## KYC (KYC)

| Code | HTTP | Meaning | User-facing message pattern | Module |
|---|---|---|---|---|
| `kyc.country_restricted` | 403 | Registration/verification from restricted jurisdiction | "Verification is not available in your country." | KYC (impl: KYC-13) |
| `kyc.already_in_progress` | 409 | Session creation while one is active | "You already have a verification in progress." | KYC (impl: KYC-06) — rule — TODO — needs owner decision |
| `kyc.upload_failed` | 400 | Manual upload failed (retriable) | "Upload failed. Please try again." | KYC (impl: KYC-36) |
| `kyc.case_not_reviewable` | 409 | Manual decision on a case not in review | "This case is no longer reviewable." | KYC (impl: KYC-11, KYC-06) |
| `account.underage` | 403 | Verified age under 18 | "You must be 18 or older." | KYC (impl: KYC-14) |

## Evaluation (EVL)

| Code | HTTP | Meaning | User-facing message pattern | Module |
|---|---|---|---|---|
| `challenge.not_found` | 404 | Challenge id unknown | "Challenge not found." | EVL (impl: EVL-01) |
| `challenge.invalid_config` | 400 | Challenge phases/rules/pricing inconsistent | "Please check the challenge configuration." | EVL (impl: EVL-01) |
| `ruleset.not_found` | 404 | Rule set unknown | "Rule set not found." | EVL (impl: EVL-02) |
| `ruleset.invalid_rules` | 400 | Rule payload fails validation | "Please check the rule values." | EVL (impl: EVL-02) |
| `override.action_unknown` | 400 | Manual override action not in pass/fail/reset | "Unknown override action." | EVL (impl: EVL-20) |
| `override.reason_required` | 400 | Manual override without recorded reason | "A reason is required." | EVL (impl: EVL-20) |
| `account.not_found` | 404 | Account unknown or not owned by caller | "Account not found." | LCC (impl: LCC-01; used across EVL/LCC/PAY) |
| `account.not_active` | 409 | Action invalid from current state | "This action is not available for this account." | LCC (impl: LCC-02) — guard set — TODO — needs owner decision |
| `account.terminal_state` | 409 | Operation on FAILED/TERMINATED account | "This account is closed." | LCC (impl: LCC-02) — TODO — needs owner decision |
| `account.not_suspended` | 409 | Resume on non-suspended account | "This account is not suspended." | LCC (impl: LCC-11) |

## Console (CON)

| Code | HTTP | Meaning | User-facing message pattern | Module |
|---|---|---|---|---|
| `console.session_not_found` | 404 | Session id unknown | "Session not found." | CON (impl: CON-30) |
| `console.cannot_revoke_self` | 400 | Revoking own session via admin endpoint | "You cannot revoke your own session here." | CON (impl: CON-30) — rule — TODO — needs owner decision |

## Risk (RSK)

| Code | HTTP | Meaning | User-facing message pattern | Module |
|---|---|---|---|---|
| `risk.account_not_found` | 404 | Case target account unknown | "Account not found." | RSK (impl: RSK-01) |
| `risk.case_already_open` | 409 | Second open case on same account | "A review case is already open." | RSK (impl: RSK-10) — rule — TODO — needs owner decision |

## Documents (DOC)

| Code | HTTP | Meaning | User-facing message pattern | Module |
|---|---|---|---|---|
| `document.not_found` | 404 | Document unknown or not owned | "Document not found." | DOC (impl: DOC-06) |

## Notes
- Earlier-draft codes with no V1 row: `checkout.duplicate_payment` (CHK-30), `checkout.invalid_coupon` (CHK-11), `module.not_entitled` (GW-22) — the closest V1 rows are CHK-07 idempotency (prevents duplicates at the state level), CHK-02 coupon reservation, and TEN-08 entitlements. Naming decisions — TODO — needs owner decision.
- Error codes for worker-internal failures (relay, command queue, sync) are not in the V1 sheet — no client-facing surface exists for them.

## Open contract questions
- TODO — needs owner decision: `payout.kyc_required` as a dedicated code vs a `payout.ineligible` sub-reason (PAY-03 models KYC as one check among many).
- TODO — needs owner decision: HTTP status for `payout.risk_hold` (423 Locked vs 403).
- TODO — needs owner decision: `tenant.not_entitled` vs `module.not_entitled` naming and the enforcement point (gateway middleware vs module).
- TODO — needs owner decision: enumeration-safety for registration duplicate-email responses (mirror AUTH-04 login treatment or not).
- TODO — needs owner decision: full sub-reason code list for `payout.ineligible` (eight checks named in PAY-03; code scheme open).
- TODO — needs owner decision: whether worker/command failures surface any error codes to admins (BRG-10/BRG-11 FAILED semantics are internal).


---

## Extended (post-V1) registry (design-level, provisional)

> Appended 2026-09-19 by `scripts/complete_contracts_pack.py` from the master registry (docs/30-error-taxonomy.md §2, Tier=ext). The V1 baseline above is untouched and remains the binding contract. Extended codes follow the GW-18 dotted convention; each freezes with its module's phase (docs/99 §12). docs/30 is the master — regenerate on drift.

### AUTH (extended)

| Code | HTTP | Meaning |
|---|---|---|
| `auth.invalid_credentials` | 401 | Wrong email/password (identical for unknown email, V2+) |
| `auth.mfa_required` | 401 | MFA challenge required (`mfa_token` returned) |
| `auth.mfa_invalid` | 401 | Bad/expired TOTP code |
| `auth.session_expired` | 401 | Session gone; client re-authenticates |
| `auth.account_locked` | 429 | Throttled; `Retry-After` set |
| `auth.password_policy_violation` | 422 | Which rule (enum list in `details`) |
| `auth.tenant_not_found` | 404 | Unresolvable subdomain/domain |
| `auth.tenant_suspended` | 403 | Tenant suspended — all its traffic |
| `authz.denied` | 403 | Policy denial; `details.policy` names the policy |
| `authz.step_up_required` | 403 | Sensitive action needs fresh 2FA |
| `auth.api_key_invalid` | 401 | Unknown/revoked/expired key |
| `auth.api_key_scope_missing` | 403 | Key lacks scope for route |
| `auth.email_already_exists` | 409 | Registration conflict |
| `auth.invitation_invalid` | 422 | Expired/used/revoked invite (V2) |
| `auth.token_invalid` | 401 | Bearer token missing/malformed/expired/unverifiable (unknown kid, issuer or audience) |
| `auth.mfa_required` | 401 | Staff action without an MFA assertion in the token (`amr`) |
| `auth.mfa_not_enrolled` | 403 | Staff identity has no verified factor yet |
| `auth.mfa_not_required` | 403 | MFA enrolment attempted by a non-staff role |
| `auth.mfa_already_enrolled` | 409 | MFA enrolment attempted when a verified factor exists |
| `auth.backup_code_invalid` | 401 | Backup code wrong, already used or unknown |
| `auth.email_change_requires_verification` | 409 | Email change pending verification (V2) |

### TEN (extended)

| Code | HTTP | Meaning |
|---|---|---|
| `tenant.suspended` | 403 | Tenant traffic denied (reason in details) |
| `tenant.not_live` | 403 | `onboarding` tenant, trader-facing route |
| `tenant.provisioning_failed` | 500 | Pipeline terminal failure (CON only, with step) |
| `tenant.slug_taken` | 409 | Slug/subdomain conflict |
| `tenant.domain_invalid` | 422 | DNS/verification failure (custom domain V1.1) |
| `tenant.limit_exceeded` | 422 | `details.metric` + current/limit |
| `tenant.settings_invalid` | 422 | JSON Schema violation, `details.violations[]` |
| `tenant.branding_invalid` | 422 | Asset/size/CSS-safety check failed |
| `tenant.kyb_required` | 403 | Staff can't activate without KYB (V1 gate) |
| `tenant.plan_insufficient` | 403 | Route/module not in tenant's entitlements |
| `tenant.deactivated` | 403 | Tenant deactivated; export-only surface inside the recovery window |
| `tenant.pending_deletion` | 403 | Tenant scheduled for deletion; settlement-only surface |

### GW+EVT (extended)

| Code | HTTP | Meaning |
|---|---|---|
| `gw.unresolved_tenant` | 404 | (public shape = `TENANT_NOT_FOUND`) |
| `gw.unauthorized` | 401 | Missing/invalid credentials |
| `gw.forbidden` | 403 | Authz denial (policy id in details) |
| `gw.rate_limited` | 429 | `Retry-After` set; scope in details (ip/user/tenant) |
| `gw.quota_exceeded` | 429 | Plan quota; `details.metric` |
| `gw.module_disabled` | 403 | Entitlement gate (module not enabled for tenant) |
| `gw.idempotency_conflict` | 422 | Key reused with different body |
| `gw.payload_too_large` | 413 | Body over limit |
| `gw.timeout` | 504 | Handler exceeded budget |
| `gw.maintenance` | 503 | Maintenance mode |
| `gw.method_not_allowed` | 405 | — |
| `evt.webhook_signature_invalid` | 401 | Ingress: bad provider signature |
| `evt.webhook_schema_invalid` | 422 | Ingress: payload failed schema |
| `evt.webhook_duplicate` | 200 | Ingress: already processed (idempotent 200) |
| `evt.consumer_dlq` | — | Internal: consumer gave up (alert + DLQ row) |
| `evt.relay_stopped` | — | Internal CRITICAL: relay not publishing 60 s |

### LED/AUD (extended)

| Code | HTTP | Meaning |
|---|---|---|
| `led.entry_unbalanced` | 500 | Constraint should catch this; surfaced as bug alert |
| `led.account_not_found` | 404 | Unknown account code |
| `led.account_closed` | 422 | Posting to closed account |
| `led.idempotency_conflict` | 422 | Same key, different entry payload |
| `led.entry_already_reversed` | 409 | Double reversal |
| `led.reversal_requires_reason` | 422 | — |
| `led.reconciliation_mismatch` | — | Internal (exception event, never a client error) |
| `aud.export_limited` | 429 | Export quota (scope too broad / too frequent) |
| `aud.scope_denied` | 403 | Export/audit query exceeds role scope |
| `aud.write_failed` | — | Internal CRITICAL: audit write failed (fail-closed: the business action is rolled back and alerted) |

### LCC (extended)

| Code | HTTP | Meaning |
|---|---|---|
| `lcc.account_not_found` | 404 | (cross-tenant probe → same 404) |
| `lcc.state_conflict` | 409 | Transition not allowed from current state (`details.from`, `details.event`) |
| `lcc.transition_conflict` | 409 | Optimistic-lock conflict after retries (alerted internally) |
| `lcc.broker_provisioning_failed` | 502 | Broker-side create failed (`details.reason` provider-safe) |
| `lcc.kyc_gate` | 422 | Funding/payout blocked by KYC level (`details.required`) |
| `lcc.paused` | 422 | Action not allowed while paused |
| `lcc.suspended` | 403 | Account suspended (risk) |
| `lcc.terms_frozen` | 409 | Attempt to modify live-account terms |
| `lcc.time_limit` | 422 | (V2) Time extension unavailable (already used) |
| `lcc.enforcement_duplicate` | — | Internal: duplicate enforcement command (idempotent no-op, logged) |

### BRG (extended)

| Code | HTTP | Meaning |
|---|---|---|
| `brg.provider_auth` | — | Our MetaApi key rejected (rotated? revoked?) |
| `brg.provider_unavailable` | — | MetaApi 5xx/timeout; circuit handles |
| `brg.account_not_found` | — | Login gone broker-side (closed manually? → page ops) |
| `brg.account_exists` | — | Provisioning got "already exists" (idempotent path: adopt or fail) |
| `brg.capacity` | 503 | Server group full / MetaApi quota — account cap guard |
| `brg.command_failed` | — | Execution failed after retries (reason in command result) |
| `brg.command_conflict` | — | Broker state contradicted preconditions (e.g. position already closed) → confirm path |
| `brg.sync_gap` | — | Deal discontinuity (event + ADM review) |
| `brg.credentials_missing` | — | Provisioned account missing creds (should never happen) |
| `brg.symbol_unknown` | — | Normalization hit unmapped symbol (BRG-32 V2 mapping mgmt; V1: alert + skip with log) |

### EVL (extended)

| Code | HTTP | Meaning |
|---|---|---|
| `evl.state_conflict` | — | — |
| `evl.rulepack_invalid` | — | — |
| `evl.rulepack_conflict` | — | — |
| `evl.input_mismatch` | — | — |
| `evl.tick_stale` | — | — |
| `evl.unknown_rule_kind` | — | — |
| `evl.override_invalid` | — | — |
| `evl.metric_unavailable` | — | — |

### RSK (extended)

| Code | HTTP | Meaning |
|---|---|---|
| `rsk.case_not_found` | 404 | — |
| `rsk.case_closed` | 409 | Action on decided case (use appeal, V2) |
| `rsk.signal_required` | 422 | Open case without signal/reason |
| `rsk.decision_conflict` | 409 | Concurrent decision (optimistic lock) |
| `rsk.hold_not_active` | 409 | Release without hold |
| `rsk.allowlist_invalid` | 422 | (V2) Allowlist entry malformed |
| `rsk.detector_disabled` | 422 | (V2) Trigger detector that's disabled |

### PAY (extended)

| Code | HTTP | Meaning |
|---|---|---|
| `pay.not_eligible` | 422 | Eligibility failed (each failed check named) |
| `pay.frequency` | 422 | Window not elapsed (`details.next_eligible_at`) |
| `payout.below_min` | 422 | `details.min_cents` |
| `payout.active_exists` | 409 | Existing active request (id in details) |
| `payout.nothing_due` | 422 | Available = 0 |
| `pay.stale_data` | 409 | Snapshot older than 10 min — retry (transient) |
| `pay.method_invalid` | 422 | Address/format failed (chain named) |
| `pay.method_changed_recently` | 200 | Warning flag, not a block (V2) |
| `pay.approval_required` | 403 | Self-serve approve attempt (no such route; defense-in-depth) |
| `pay.state_conflict` | 409 | Illegal transition attempt |
| `pay.rail_unavailable` | 503 | Circuit open (`details.retry_after`) |
| `pay.rail_rejected` | — | Provider rejected (reason stored, retried per policy) |
| `pay.amount_adjusted` | — | Finance adjustment applied (audit) |

### CHK (extended)

| Code | HTTP | Meaning |
|---|---|---|
| `chk.order_invalid` | 422 | Package/rule-set combo not purchasable (TEN validation) |
| `chk.package_unavailable` | 422 | Package deactivated mid-checkout (price snapshot protects existing intents) |
| `chk.method_not_allowed` | 422 | Rail not enabled for tenant/currency (provider matrix) |
| `chk.login_required` | 401 | Guest checkout (login-first policy) |
| `chk.intent_expired` | 409 | Tries to pay a dead intent (new intent offered) |
| `chk.intent_conflict` | 409 | Concurrent webhook state race (last-write validated by state machine) |
| `chk.capture_mismatch` | 500 | Webhook amount ≠ intent (anomaly → anomaly ticket, not auto-accept) |
| `chk.refund_window_closed` | 422 | Trader request outside policy window |
| `chk.refund_conflict` | 409 | Refund on already-refunded/chargeback'd intent |
| `chk.provider_unavailable` | 503 | Circuit open (alternate rails suggested in response) |
| `chk.wire_awaiting_confirmation` | 200 | Wire not yet confirmed (72 h policy info) |
| `chk.fx_unavailable` | 422 | Currency unsupported for rail (V2) |
| `chk.chargeback_active` | 409 | New refund while chargeback open |

### KYC (extended)

| Code | HTTP | Meaning |
|---|---|---|
| `kyc.required` | 422 | Gate fail (consumers wrap: CHK `chk.login_required`? no — each consumer uses its own code; this is the KYC-internal result) |
| `kyc.country_blocked` | 422 | Self-declared country in blocklist |
| `kyc.age` | 422 | Under minimum (at decision time) |
| `kyc.session_expired` | 409 | Provider session dead (new session offered) |
| `kyc.session_limit` | 429 | Rate limit (V2 KYC-29; V1: 3 sessions/level/day) |
| `kyc.docs_invalid` | 422 | Upload failed (size/type/corrupt) |
| `kyc.state_conflict` | 409 | Illegal transition (e.g. decide a verified session) |
| `kyc.provider_unavailable` | 503 | Veriff circuit open (manual-upload path still works) |
| `kyc.provider_mismatch` | 500 | Webhook state inconsistent with session (anomaly ticket) |
| `kyc.reinitial_cooldown` | 429 | V1 24 h cooldown after rejection |
| `kyc.level_mismatch` | 422 | L2 session attempted before L1 verified |

### NOT (extended)

| Code | HTTP | Meaning |
|---|---|---|
| `not.template_not_found` | 500 | Mapping references missing template (deploy error — CRITICAL alert) |
| `not.vars_invalid` | 500 | vars_selector produced empty/PII-guarded vars (alert + skip, never send half-rendered) |
| `not.recipoent_unknown` | 500 | No email/identity (alert — usually a data bug) |
| `not.provider_unavailable` | 503 | Postmark down (retry queue drains on recovery; critical templates page ops) |
| `not.rate_limited` | 429 | (V2) Per-recipient/template cap hit (batched into digest) |
| `not.suppressed` | — | Info state (not an error) |
| `not.broadcast_validation` | 422 | (V2) Broadcast preview failed |
| `not.tg_not_linked` | — | (V2) Telegram channel skipped (in-app fallback) |

### DOC (extended)

| Code | HTTP | Meaning |
|---|---|---|
| `doc.not_found` | 404 | Document id unknown |
| `doc.pending` | 409 | URL requested before generation finished (TD shows "preparing…") |
| `doc.state_missing` | 500 | Mapper found no source state (data bug — CRITICAL alert) |
| `doc.render_failed` | 500 | Template/Puppeteer failure (retry; 3× → DLQ) |
| `doc.upload_failed` | 500 | R2 write failed (retry) |
| `doc.template_version_missing` | 500 | Deploy mismatch (template not in worker) — CI check prevents |
| `doc.verify_not_found` | 404 | Unknown cert hash (page says "not found", no detail) |
| `doc.bulk_limit` | 422 | (V2) Bulk size over cap |

### TD (extended)

| Code | HTTP | Meaning |
|---|---|---|
| `auth.expired` | 401 | full-screen re-login (state preserved via query) |
| `tenant.not_found` | 404 | "site not found" (04: 404-not-403 posture) |
| `rate.limited` | 429 | inline "slow down, try in {n}s" |
| `gw.internal` | — | error boundary: retry button + ticket pre-fill + Sentry id shown |
| `stream.lost` | — | polling fallback + amber chip (not an error screen) |
| `render.stale` | — | amber "data from {time}" banner (honesty over polish) |

### ADM (extended)

| Code | HTTP | Meaning |
|---|---|---|
| `stepup.expired` | 403 | 2FA dialog reopens (object preserved) |
| `forbidden.role` | 403 | "you need {role}" + link to settings (ADM-17 V2) |
| `export.busy` | 429 | queue position shown (V2) |

### SUP (extended)

| Code | HTTP | Meaning |
|---|---|---|
| `sup.ticket_not_found` | 404 | — (ownership check returns 404, never 403 — 04 posture) |
| `sup.closed` | 409 | Reply on a closed ticket (reopen = staff action) |
| `sup.category_unknown` | 422 | Category not in the registry (V2) |
| `sup.attachment_invalid` | 422 | Type/size violation |
| `sup.duplicate_open` | 200 | (V2) Similar open ticket exists (same trader+category+account, < 7 days) — the create response includes it; trader chooses |
| `sup.rate_limited` | 429 | Trader ticket-create cap (5/day — abuse control, V2 SUP-30 family) |
| `sup.field_required` | 422 | Domain-specific type missing its required object ref (V2) |
| `sup.satisfaction_expired` | 409 | Survey window passed (V2) |

### ANA (extended)

| Code | HTTP | Meaning |
|---|---|---|
| `ana.model_stale` | 409 | Read model lag > threshold (UI: "data from {as_of}" banner — the ANA-14 label, surfaced as a soft error) |
| `ana.report_not_found` | 404 | Unknown report id (V2) |
| `ana.report_params_invalid` | 422 | (V2) Bad report params |
| `ana.report_running` | 409 | Duplicate concurrent run (return the existing run id) |
| `ana.export_limit` | 429 | (V2) Concurrent export cap |
| `ana.threshold_invalid` | 422 | (V2) Alert rule malformed |
| `ana.rebuild_window_exceeded` | 422 | (V2) Rebuild older than the events log window (13 mo) |
| `ana.consumer_lag` | — | Ops metric → CON alert (not an API code) |

### CRM (extended)

| Code | HTTP | Meaning |
|---|---|---|
| `crm.segment_not_found` | 404 | — |
| `crm.segment_empty` | 200 | Campaign on an empty segment (allowed; the confirmation shows "0 recipients") |
| `crm.campaign_sending` | 409 | Duplicate send trigger |
| `crm.template_invalid` | 422 | (V3) Template render failure in preview |
| `crm.consent_missing` | 422 | Marketing send attempted without consent capture point configured (V3) |
| `crm.sequence_version_replaced` | — | Info: active runs exit at next step |
| `crm.unsubscribe_unknown` | 404 | Bad token (page: "nothing to do here", no leak of validity) |

### CON (extended)

| Code | HTTP | Meaning |
|---|---|---|
| `con.platform_role_required` | 403 | Non-platform session on a console route (structural deny — also logged as a security event) |
| `con.tenant_not_found` | 404 | — |
| `con.saga_blocked` | 409 | Provisioning step can't retry (blocker named) |
| `con.approval_required` | 403 | Nuclear action without the V2 second operator |
| `con.approval_expired` | 409 | Approval window (10 min) passed |
| `con.self_approval` | 403 | B == A (structural deny, security event) |
| `con.impersonation_read_only` | 403 | State-changing call under a view-as token |
| `con.impersonation_denied` | 403 | Deny-listed action (payout approve etc. — security event + CRITICAL) |
| `con.control_active` | 409 | Can't arm a control that's already active |
| `con.suspension_terminal` | 409 | Act on a terminated tenant (retention reads only) |

### BIL (extended)

| Code | HTTP | Meaning |
|---|---|---|
| `bil.tenant_not_billable` | 422 | Metering/invoice op on a contract-mode tenant in V1/V2 (the era guard — the API says "manual mode; record in console") |
| `bil.plan_invalid` | 422 | (V3) Plan/limit mismatch |
| `bil.approval_required` | 403 | Manual invoice issue without two-op (V2+) |
| `bil.state_conflict` | 409 | Subscription transition conflict (e.g. pause on an already-terminated tenant) |
| `bil.metering_stale` | 409 | Invoice computed before the metering rollup completed (retry — the rollup is nightly; same-day invoices use yesterday's + a flag) |
| `bil.gateway_unavailable` | 503 | (V3) Payment provider down (invoice stays issued; dunning clock is provider-tolerant) |
| `bil.pass_through_unconfigured` | 422 | (V3) Provider cost line with no margin config (fail closed: the invoice can't be issued with an unknown pass-through) |

### AFF (extended)

| Code | HTTP | Meaning |
|---|---|---|
| `aff.not_approved` | 403 | Non-affiliate calling affiliate APIs (the dashboard/API surface) |
| `aff.self_referral` | 422 | Attribution attempt blocked (the signup surfaces "no referral applied") |
| `aff.attribution_expired` | — | Window (30 d) passed at signup (no attribution, not an error to the trader) |
| `aff.coupon_invalid` | 422 | (CHK wraps: the checkout code check) |
| `aff.tax_form_required` | 422 | Payout request without a current tax form |
| `aff.below_minimum` | 422 | Settled balance < payout minimum |
| `aff.fraud_hold` | 423 | Payout blocked by hold (reason class: "under review") |
| `aff.payout_state_conflict` | 409 | Duplicate payout request (one active per affiliate) |
| `aff.rate_card_missing` | 500 | Capture with ref but no effective rate card (fail: accrue at 0 + CRITICAL — never guess a rate) |
| `aff.tier_depth_exceeded` | — | Depth-3+ link ignored (structural cap, logged) |

### CMS/CMP (extended)

| Code | HTTP | Meaning |
|---|---|---|
| `cms.page_not_found` | 404 | Public 404 (the tenant's branded 404 page) |
| `cms.block_schema_invalid` | 500 | Data failed its block schema (editor bug or a corrupt publish — the page renders without the bad block + CRITICAL alert; never a blank page) |
| `cms.publish_conflict` | 409 | Concurrent publish (last-write wins on the pointer, the losing editor is told with a diff) |
| `cms.scheduled_conflict` | 409 | Schedule on an already-live time (the worker skips + alerts) |
| `cms.media_too_large` | 422 | Upload over the block-type limit (images 5 MB) |
| `cms.form_rate_limited` | 429 | Lead form abuse (the honeypot + limit pair) |
| `cms.legal_review_required` | 403 | Legal page publish without the review note (2FA'd override by owner role) |
| `cms.tenant_not_provisioned` | 404 | No site for this tenant (the static fallback renders) |

### MIG (extended)

| Code | HTTP | Meaning |
|---|---|---|
| `mig.export_schema_invalid` | 422 | The TTS export doesn't match the expected schema (the class is rejected before any row lands — fail at the door, not mid-import) |
| `mig.manifest_mismatch` | 409 | Row counts vs the TTS manifest differ (the import halts; the diff is the first artifact) |
| `mig.mapping_missing` | 409 | A source value has no mapping (state/term) — the row is an exception, the import continues, the halt-at-gate is on the report |
| `mig.dry_run_failed` | 409 | The dry-run reconciliation gate failed (the real run is structurally blocked — the state machine enforces `dry_run_passed` before `importing`) |
| `mig.cutover_gate_closed` | 409 | Cutover attempted with undispositioned exceptions |
| `mig.parallel_drift` | — | (internal) the daily comparator exceeded tolerance (a P1 event, not an API error) |
| `mig.correction_rejected` | 409 | A correction on an already-corrected row (the chain: corrections are sequential, one per row per cycle) |
| `mig.tenant_not_ready` | 409 | Import attempted before the saga/tenant state allows (the tenant must be `active` with the MIG entitlement) |
| `mig.kyc_reverify_outstanding` | — | (informational) traders blocked at payout by the §3.3 gate — surfaced in the concierge dashboard, not an error |

### MOB/JRN/EDU/CHT (extended)

| Code | HTTP | Meaning |
|---|---|---|
| `device.token_expired` | 401 | full login (the biometric path is re-enrolled after) |
| `min.client_version` | 426 | the update nudge (the store deep link) + the read-only banner |
| `push.token_invalid` | — | silent (the next push registration heals it) |
| `chart.degraded` | — | the native fallback: the numbers table (the chart is an enhancement, the numbers are the product) |
| `biometric.unavailable` | — | the full login (the feature degrades, the app doesn't) |

### SDK/DVP/TRD/PLT/CS (extended)

| Code | HTTP | Meaning |
|---|---|---|
| `public.auth_invalid` | 401 | The key is invalid/revoked (the no-detail leak — the 04 posture: the invalid key and the revoked key are the same 401, the oracle ban, the 02 §3.4 posture) |
| `public.scope_missing` | 403 | The key lacks the scope (the scope name in the `details` — the developer's fix is the scope request, the actionable error) |
| `public.rate_limited` | 429 | The tier limit (the `Retry-After`, the `X-RateLimit-*`, the tier name) |
| `public.env_mismatch` | 403 | A test key on a live route / a live key on a sandbox route (the environment claim check, the §1 binding) |
| `public.id_not_found` | 404 | The object (the tenant scope: another tenant's object = the 404, the 04 posture, the cross-tenant oracle ban) |
| `public.webhook_signature_invalid` | — | (the developer's side, the SDK-03 error class, the docs' troubleshooting) |
| `public.checkout_session_expired` | 409 | The checkout link dead (the TTL, the 12 §3.2 class) |
| `public.payout_manual_approval` | 202 | The API payout request accepted (the **always-manual rule, the §3.1** — the 202 + the `status: pending_approval`, the "the machine's request waits for the... |
| `public.deprecated` | 200 | The 12-month window (the header: the sunset date, the migration URL, the SDK-15 contract) |
| `public.removed` | 410 | The end-of-life (the migration header, the labeled removal) |
| `public.kyc_sync_rejected` | 422 | The SDK-11 sync (the provider unrecognized, the tenant config `external_accepted: false`, the state conflict) |
| `sandbox.inject_invalid` | 422 | The SDK-06 (the event unknown, the payload schema fail) |
| `sandbox.live_only` | 404 | The sandbox route on a live tenant (the structural ban, the §1 rule — the 404, not the 403, the route-existence oracle ban) |

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

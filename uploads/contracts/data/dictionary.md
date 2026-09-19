# Data Dictionary v1

Status: DRAFT
Owner: TBD
Version: v1
Last updated: 2026-09-17

Derived from the V1 Execution Sheet (V1.0 / V1.1) of `Alpha One PRD.xlsx`.
Every table lists owner module, tenant-scoping, columns with the Req IDs that justify them, and indexes.
Tenant isolation is a single shared schema with `tenant_id` on every tenant-scoped row (Out Of Scope sheet: no schema-per-tenant or database-per-tenant).

## tenants
Owner: TEN. Tenant-scoped: no (root table). Req IDs: TEN-01.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | uuid | PK | TEN-01 |
| name | text | NOT NULL | TEN-01 |
| subdomain | text | UNIQUE NOT NULL | TEN-02, TEN-42 (availability + reserved list www/admin/api/console/app) |
| status | text | NOT NULL — TODO enum | TEN-01, TEN-15 (suspend), terminate |
| created_at | timestamptz | NOT NULL DEFAULT now() | standard |
| updated_at | timestamptz | NOT NULL DEFAULT now() | standard |

Indexes: UNIQUE(tenant_id, subdomain) partial WHERE subdomain IS NOT NULL — allows platform rows with NULL subdomain. Partial-index necessity — TODO — needs owner decision.

Open questions: status enum values; terminate semantics — TODO — needs owner decision.

## users
Owner: AUTH. Tenant-scoped: yes. Req IDs: AUTH-01, AUTH-12.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | uuid | PK | standard |
| tenant_id | uuid | NOT NULL, FK tenants | AUTH-01 (tenant belonging) |
| email | text | NOT NULL | AUTH-01, AUTH-04 (email unique per tenant — Out Of Scope: username-only login excluded) |
| password_hash | text | NOT NULL | AUTH-17 (argon2id) |
| user_type | text | NOT NULL — TODO enum | AUTH-12 (Trader, Staff; API Consumer is V2 per AUTH-21 skip) |
| status | text | NOT NULL — TODO enum | AUTH-20 (suspend), AUTH-43 (unsuspend) |
| totp_secret_encrypted | text | NULL | AUTH-09 (staff 2FA enrollment; trader optional?) — TODO — needs owner decision |
| created_at / updated_at | timestamptz | NOT NULL DEFAULT now() | standard |

Indexes: UNIQUE(tenant_id, email), partial-index treatment for NULL tenant_id — TODO — needs owner decision.

Open questions: totp enforcement scope (staff only per AUTH-09?); email verification column — TODO — needs owner decision.

## roles
Owner: AUTH. Tenant-scoped: yes (platform roles flagged). Req IDs: AUTH-12.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | uuid | PK | standard |
| tenant_id | uuid | NULL (platform roles) | AUTH-12 (Super Admin is platform; Tenant Admin/staff custom roles per tenant) |
| name | text | NOT NULL | AUTH-12 (Super Admin, Tenant Admin, custom staff roles, Trader, API Consumer) |
| is_system | boolean | NOT NULL DEFAULT false | AUTH-12 (built-in vs custom) |
| created_at / updated_at | timestamptz | NOT NULL DEFAULT now() | standard |

Indexes: UNIQUE(tenant_id, name) — uniqueness treatment for platform roles with NULL tenant_id — TODO — needs owner decision.

## permissions
Owner: AUTH. Tenant-scoped: no (global catalog). Req IDs: AUTH-13.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | uuid | PK | standard |
| key | text | UNIQUE NOT NULL | AUTH-13 (`resource.action` format) |
| module | text | NOT NULL | AUTH-13 (module-declared keys) |
| description | text | NULL | registry documentation |

Indexes: UNIQUE(key)

## role_permissions
Owner: AUTH. Tenant-scoped: via role. Req IDs: AUTH-12, AUTH-13.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| role_id | uuid | NOT NULL, FK roles | AUTH-12 |
| permission_id | uuid | NOT NULL, FK permissions | AUTH-13 |
| TODO | — | — | any extra attributes (grant/deny, scope) — TODO — needs owner decision |

Indexes: UNIQUE(role_id, permission_id)

## user_roles
Owner: AUTH. Tenant-scoped: via users. Req IDs: AUTH-12. (Implied join table; not listed in the brief's minimum list but required by AUTH-12 assignments.)

| Column | Type | Constraints | Notes |
|---|---|---|---|
| user_id | uuid | NOT NULL, FK users | AUTH-12 |
| role_id | uuid | NOT NULL, FK roles | AUTH-12 |

Indexes: UNIQUE(user_id, role_id)

## sessions
Owner: AUTH. Tenant-scoped: yes. Req IDs: AUTH-07.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | uuid | PK | standard |
| tenant_id | uuid | NOT NULL | AUTH-04 tenant context |
| user_id | uuid | NOT NULL, FK users | AUTH-07 |
| TODO | — | — | device/ip/user-agent fields — TODO — needs owner decision (AUD-01 records them per request; session capture unspecified) |
| revoked_at | timestamptz | NULL | AUTH-07 server-side revocation; AUTH-20 suspension invalidates immediately |
| expires_at | timestamptz | NOT NULL | AUTH-07 |
| created_at | timestamptz | NOT NULL DEFAULT now() | standard |

Indexes: (user_id), (revoked_at)

## refresh_tokens
Owner: AUTH. Tenant-scoped: yes. Req IDs: AUTH-07.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | uuid | PK | standard |
| tenant_id | uuid | NOT NULL | standard |
| session_id | uuid | NOT NULL, FK sessions | AUTH-07 |
| token_hash | text | NOT NULL | AUTH-07 (rotating; never store raw) |
| rotated_from | uuid | NULL | AUTH-07 rotation chain (reuse detection) |
| used_at | timestamptz | NULL | AUTH-07 rotation |
| revoked_at | timestamptz | NULL | AUTH-07 revocation |
| expires_at | timestamptz | NOT NULL | AUTH-07 |
| created_at | timestamptz | NOT NULL DEFAULT now() | standard |

Indexes: UNIQUE(token_hash), (session_id)

Open questions: rotation window; reuse-detection policy — TODO — needs owner decision.

## outbox
Owner: EVT. Tenant-scoped: yes (via payload). Req IDs: EVT-01.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | uuid | PK | EVT-03 envelope id |
| tenant_id | uuid | NOT NULL | EVT-03 |
| type | text | NOT NULL | EVT-03 event type |
| version | text | NOT NULL | EVT-03 |
| payload | jsonb | NOT NULL | EVT-03 |
| occurred_at | timestamptz | NOT NULL | EVT-03 |
| TODO | — | — | relay bookkeeping (published_at, attempts) — TODO — needs owner decision |
| created_at | timestamptz | NOT NULL DEFAULT now() | standard |

Indexes: (created_at) — relay poll cursor — TODO — needs owner decision on shape.

## event_log
Owner: EVT. Tenant-scoped: yes. Req IDs: EVT-08.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | uuid | PK | EVT-03 id (dedupe key for consumers, EVT-05) |
| tenant_id | uuid | NOT NULL | EVT-03 |
| type | text | NOT NULL | EVT-03 |
| version | text | NOT NULL | EVT-03 |
| payload | jsonb | NOT NULL | EVT-03 |
| occurred_at | timestamptz | NOT NULL | EVT-03 |
| published_at | timestamptz | NOT NULL | EVT-08 (append on publish) |

Indexes: (tenant_id, occurred_at), (type)

## command_queue
Owner: EVT (EVT-20); produced by EVL-17/LCC-27; consumed by BRG-10. Tenant-scoped: yes.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | uuid | PK | standard |
| tenant_id | uuid | NOT NULL | standard |
| command_type | text | NOT NULL | EVT-20 (disable-then-close etc.) |
| account_id | uuid | NOT NULL | BRG-10 target |
| payload | jsonb | NOT NULL | BRG-10 |
| status | text | NOT NULL — TODO enum | BRG-11 (pending, executed, FAILED after real closure check) |
| retry_count | int | NOT NULL DEFAULT 0 | EVT-20 retry with backoff |
| next_attempt_at | timestamptz | NULL | EVT-20 backoff |
| TODO | — | — | broker confirmation fields — TODO — needs owner decision (BRG-11) |
| created_at / updated_at | timestamptz | NOT NULL DEFAULT now() | standard |

Indexes: (status, next_attempt_at)

## audit_entries
Owner: AUD. Tenant-scoped: yes. Req IDs: AUD-01, AUD-04.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | uuid | PK | standard |
| tenant_id | uuid | NOT NULL | AUD-01 |
| actor_id | uuid | NULL | AUD-01 (system actions?) |
| actor_role | text | NULL | AUD-01 |
| action | text | NOT NULL | AUD-01 |
| entity_type | text | NOT NULL | AUD-01 |
| entity_id | uuid | NOT NULL | AUD-01 |
| before_payload | jsonb | NULL | AUD-01 |
| after_payload | jsonb | NULL | AUD-01 |
| ip | inet | NULL | AUD-01 |
| user_agent | text | NULL | AUD-01 |
| correlation_id | uuid | NOT NULL | AUD-01 (GW-18 envelope correlation) |
| occurred_at | timestamptz | NOT NULL | AUD-01 |
| sensitive_access | boolean | NOT NULL DEFAULT false | AUD-23 (V1.1 flag or separate table — TODO — needs owner decision) |
| reason | text | NULL | AUD-23 (reason recorded for sensitive access) |

Indexes: (tenant_id, occurred_at), (entity_type, entity_id), (actor_id)
Immutability: append-only; no UPDATE/DELETE path (AUD-04). TODO — needs owner decision on DB-level enforcement (trigger vs grants).

## challenges
Owner: EVL. Tenant-scoped: yes. Req IDs: EVL-01.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | uuid | PK | standard |
| tenant_id | uuid | NOT NULL | EVL-01 |
| type | text | NOT NULL — TODO enum | EVL-01 |
| TODO | — | — | account sizes, pricing, phase structure — TODO — needs owner decision (EVL-01 names them; shape open) |
| kyc_timing | text | NULL — CHECK (at_creation, after_evaluation, at_first_payout, skipped) | LCC-07 per-challenge KYC timing; enum resolved 2026-09-17 per KYC-03's timing description (KYC-03 itself is V2.0 — see `api/lcc.md`) |
| created_at / updated_at | timestamptz | NOT NULL DEFAULT now() | standard |

Indexes: (tenant_id)

## rule_sets
Owner: EVL. Tenant-scoped: yes. Req IDs: EVL-02.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | uuid | PK | standard |
| tenant_id | uuid | NOT NULL | EVL-02 |
| challenge_id | uuid | NOT NULL, FK challenges | EVL-01/EVL-02 |
| current_version | int | NOT NULL | EVL-02 |
| created_at / updated_at | timestamptz | NOT NULL DEFAULT now() | standard |

Indexes: (challenge_id)

## rule_set_versions
Owner: EVL. Tenant-scoped: yes. Req IDs: EVL-02, EVL-34.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | uuid | PK | standard |
| rule_set_id | uuid | NOT NULL, FK rule_sets | EVL-02 |
| version | int | NOT NULL | EVL-02 |
| rules | jsonb | NOT NULL — TODO structure | EVL-04 rule inputs (profit target EVL-06, daily drawdown EVL-07, max drawdown EVL-08 incl. static/trailing + basis) |
| migration_policy | text | NULL — TODO enum | EVL-34 (policy for in-flight accounts; options undefined) |
| created_at | timestamptz | NOT NULL DEFAULT now() | standard |

Indexes: UNIQUE(rule_set_id, version)

## accounts
Owner: LCC. Tenant-scoped: yes. Req IDs: LCC-01, LCC-02, EVL-29. This is the key table — modeled against the LCC-02 state machine and EVL-29 trailing HWM.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | uuid | PK | standard |
| tenant_id | uuid | NOT NULL | TEN-03 |
| trader_id | uuid | NOT NULL, FK users | LCC-01 |
| status | text | NOT NULL — CHECK per LCC-02 | LCC-02: CREATED, ACTIVE, BREACH_DETECTED, CLOSING, FAILED, PASS_PENDING, VERIFICATION, AWAITING_ACTIVATION, FUNDED, SUSPENDED, TERMINATED. Legal transitions: `api/lcc.md` edge list (resolved 2026-09-17) |
| phase | int | NOT NULL, CHECK (phase >= 1) | LCC-01 phase — per-challenge ordinal (resolved 2026-09-17). Funded stage is `status = FUNDED`; the funded account continues the ordinal past the last evaluation phase (e.g. 3 in a 2-evaluation-phase challenge) |
| rule_set_version_id | uuid | NOT NULL, FK rule_set_versions | EVL-02 binding at creation — "the version active at creation" |
| trailing_hwm | numeric | NULL | EVL-29 persisted high-water mark |
| trailing_hwm_basis | text | NOT NULL — TODO enum | EVL-29 "explicitly whether it ratchets on balance or equity" — locked at creation; enum values — TODO — needs owner decision |
| daily_start_balance | numeric | NULL | EVL-07 daily starting balance, resets at configured time |
| daily_reset_at | timestamptz | NULL | EVL-07 |
| challenge_id | uuid | NOT NULL, FK challenges | LCC-01 |
| broker_account_ref | text | NULL | BRG-05 created broker account; see partial-unique index note below |
| broker_group | text | NULL | BRG-12 |
| leverage | int | NULL | BRG-12 |
| profit_split_pct | numeric | NULL | LCC-20 (set at funding) |
| payout_frequency | text | NULL — TODO enum | LCC-20 |
| first_withdrawal_delay_days | int | NULL | LCC-20 |
| next_withdrawal_date | date | NULL | LCC-20, PAY-21 |
| initial_balance | numeric | NOT NULL | LCC-20/PAY-02 (available profit = balance+equity − initial − prior payouts) |
| parent_account_id | uuid | NULL, FK accounts | LCC-06 phase lineage |
| TODO | — | — | payout terms locking at funding vs per-challenge config precedence — TODO — needs owner decision |
| created_at / updated_at | timestamptz | NOT NULL DEFAULT now() | standard |

Indexes: UNIQUE(broker_account_ref) partial index WHERE broker_account_ref IS NOT NULL. Allows multiple NULLs before broker provisioning completes (LCC-05).

## account_state_history
Owner: LCC. Tenant-scoped: yes. Req IDs: LCC-03.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | uuid | PK | standard |
| tenant_id | uuid | NOT NULL | standard |
| account_id | uuid | NOT NULL, FK accounts | LCC-03 |
| prior_state | text | NULL | LCC-03 (NULL for creation) |
| new_state | text | NOT NULL | LCC-03 |
| trigger | text | NOT NULL | LCC-03 |
| actor_id | uuid | NULL | LCC-03 |
| inputs | jsonb | NULL | LCC-03 |
| occurred_at | timestamptz | NOT NULL | LCC-03 |

Indexes: (account_id, occurred_at)
Append-only per LCC-03 "reconstructed at any point in time".

## orders
Owner: CHK. Tenant-scoped: yes. Req IDs: CHK-08.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | uuid | PK | standard |
| tenant_id | uuid | NOT NULL | standard |
| trader_id | uuid | NOT NULL, FK users | CHK-08 customer |
| type | text | NOT NULL — TODO enum | CHK-08 ("type") |
| amount | numeric | NOT NULL | CHK-08 |
| method | text | NOT NULL | CHK-08 (provider used) |
| coupon | text | NULL | CHK-08 |
| customer_ip | inet | NULL | CHK-08 |
| utm | jsonb | NULL | CHK-08 (UTM capture; structure — TODO — needs owner decision) |
| TODO | — | — | challenge/size/add-ons purchased — TODO — needs owner decision (implied by CHK-01/TD-09 but not in CHK-08 field list) |
| created_at / updated_at | timestamptz | NOT NULL DEFAULT now() | standard |

Indexes: (tenant_id, created_at), (trader_id)

## payments
Owner: CHK. Tenant-scoped: yes. Req IDs: CHK-07, CHK-08.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | uuid | PK | standard |
| tenant_id | uuid | NOT NULL | standard |
| order_id | uuid | NOT NULL, FK orders | CHK-07/CHK-08 linkage |
| provider | text | NOT NULL | CHK-04 (Match2Pay, Interkasa, crypto rails) |
| provider_event_id | text | NOT NULL | CHK-07 idempotency — dedupe by provider event id |
| status | text | NOT NULL — TODO enum | CHK-07 "transition payment state" — states undefined |
| amount | numeric | NOT NULL | CHK-08 |
| TODO | — | — | failed payment record fields (CHK-16) — TODO — needs owner decision |
| created_at / updated_at | timestamptz | NOT NULL DEFAULT now() | standard |

Indexes: UNIQUE(provider, provider_event_id), (order_id)

## checkout_sessions
Owner: CHK. Tenant-scoped: yes. Req IDs: CHK-02, CHK-43, CHK-44 (lifecycle added by Decision 7, 2026-09-16).

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | uuid | PK | standard |
| tenant_id | uuid | NOT NULL | standard |
| trader_id | uuid | NULL | CHK-02 — TODO — needs owner decision (guest checkout allowed?) |
| challenge_id | uuid | NOT NULL, FK challenges | CHK-01/CHK-02 |
| reserved_price | numeric | NOT NULL | CHK-02 "reserves price" |
| coupon_code | text | NULL | CHK-02 "reserves ... coupon" |
| reservation_expires_at | timestamptz | NOT NULL | CHK-02 "limited window" — duration TODO — needs owner decision |
| state | text | NOT NULL | CHK-43 marks sessions expired, CHK-44 marks them cancelled; enum values — TODO — needs owner decision (no state list named in the sheet; see open question 24) |
| TODO | — | — | add-ons representation — TODO — needs owner decision (TD-09 mentions add-ons) |
| created_at / updated_at | timestamptz | NOT NULL DEFAULT now() | standard |

Indexes: (reservation_expires_at), (trader_id)

## payouts
Owner: PAY. Tenant-scoped: yes. Req IDs: PAY-01, PAY-13.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | uuid | PK | standard |
| tenant_id | uuid | NOT NULL | standard |
| account_id | uuid | NOT NULL, FK accounts | PAY-01 |
| trader_id | uuid | NOT NULL, FK users | PAY-01 |
| amount | numeric | NOT NULL | PAY-01 |
| state | text | NOT NULL — enum per PAY-13 (values named verbatim in the sheet) | PAY-13: requested, eligibility checked, pending approval, approved, rejected, processing, paid, failed, cancelled |
| payout_method_id | uuid | NULL, FK payout_methods | PAY-05 — TODO — needs owner decision (V1.0 requests without saved methods?) |
| TODO | — | — | approval reason, execution fields (provider, reference, executed_at per PAY-12) — TODO — needs owner decision (on payouts table vs execution sub-table) |
| TODO | — | — | eligibility snapshot (checks passed at approval, PAY-03) — TODO — needs owner decision |
| created_at / updated_at | timestamptz | NOT NULL DEFAULT now() | standard |

Indexes: (tenant_id, state), (account_id), (trader_id)

## payout_methods
Owner: PAY. Tenant-scoped: yes. Req IDs: PAY-05, PAY-45.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | uuid | PK | standard |
| tenant_id | uuid | NOT NULL | standard |
| trader_id | uuid | NOT NULL, FK users | PAY-05 |
| type | text | NOT NULL — TODO enum | PAY-05 (crypto wallet, bank details) |
| details_encrypted | text | NOT NULL | TEN-12 encryption for sensitive config; AUD-23 lists payout methods as sensitive data |
| chain | text | NULL | PAY-45 chain-specific validation |
| address | text | NULL | PAY-45 |
| confirmed_at | timestamptz | NULL | PAY-05 "save and confirm" |
| created_at / updated_at | timestamptz | NOT NULL DEFAULT now() | standard |

Indexes: (trader_id)

## kyc_verifications
Owner: KYC. Tenant-scoped: yes. Req IDs: KYC-06, KYC-09.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | uuid | PK | standard |
| tenant_id | uuid | NOT NULL | standard |
| trader_id | uuid | NOT NULL, FK users | KYC-06 |
| state | text | NOT NULL — enum per KYC-06 (values named verbatim in the sheet) | KYC-06: NOT_STARTED, PENDING, IN_REVIEW, APPROVED, REJECTED, NEEDS_RESUBMISSION, EXPIRED |
| provider | text | NOT NULL | KYC-01 (one provider per tenant in V1) |
| provider_reference | text | NULL | KYC-09 |
| verified_full_name | text | NULL | KYC-09 |
| verified_dob | date | NULL | KYC-09 |
| verified_country | text | NULL | KYC-09, KYC-13 |
| TODO | — | — | manual-review linkage (KYC-11/KYC-12) and upload metadata (KYC-36) — TODO — needs owner decision |
| created_at / updated_at | timestamptz | NOT NULL DEFAULT now() | standard |

Indexes: (trader_id), (tenant_id, state)

## notifications
Owner: NOT. Tenant-scoped: yes. Req IDs: NOT-01, NOT-13.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | uuid | PK | standard |
| tenant_id | uuid | NOT NULL | standard |
| event_id | uuid | NOT NULL | NOT-13 dedupe by event id |
| channel | text | NOT NULL | NOT-13 dedupe by event id and channel |
| template | text | NOT NULL | NOT-05 (one of 10 core templates) |
| recipient_id | uuid | NULL | — TODO — needs owner decision (recipient model) |
| status | text | NOT NULL | — TODO — needs owner decision (status enum not in sheet; column nullable or enum defined at working session) |
| sent_at | timestamptz | NULL | — TODO — needs owner decision |
| created_at | timestamptz | NOT NULL DEFAULT now() | standard |

Indexes: UNIQUE(event_id, channel, recipient_id) — dedupe per NOT-13; (recipient_id)

## notification_templates
Owner: NOT. Tenant-scoped: yes (per-tenant branding). Req IDs: NOT-05.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | uuid | PK | standard |
| key | text | NOT NULL | NOT-05 (one of 10 core template keys) |
| tenant_id | uuid | NULL | per-tenant overrides suggested by NOT-03 sender config; platform defaults implied — TODO — needs owner decision (a nullable FK to tenants should also carry an explicit tenant-override vs platform-default flag) |
| TODO | — | — | subject/body/branding fields — TODO — needs owner decision |
| created_at / updated_at | timestamptz | NOT NULL DEFAULT now() | standard |

Indexes: UNIQUE(tenant_id, key)

## documents
Owner: DOC. Tenant-scoped: yes. Req IDs: DOC-01, DOC-05.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | uuid | PK | DOC-03 certificate ID |
| tenant_id | uuid | NOT NULL | TEN-18 |
| trader_id | uuid | NOT NULL, FK users | DOC-06 |
| type | text | NOT NULL — TODO enum | DOC-04 (certificate trigger types; receipt/invoice from CHK-17/CHK-40 — TODO — needs owner decision whether they live here) |
| storage_key | text | NOT NULL | DOC-05 tenant-prefixed R2 key |
| issued_at | timestamptz | NOT NULL | DOC-04 |
| created_at | timestamptz | NOT NULL DEFAULT now() | standard |

Indexes: (trader_id), (type)

## ledger_accounts
Owner: LED. Tenant-scoped: yes. Req IDs: LED-01.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | uuid | PK | standard |
| tenant_id | uuid | NOT NULL | LED-01 "per tenant" |
| code | text | NOT NULL | LED-01 fixed chart — codes TODO — needs owner decision |
| name | text | NOT NULL | LED-01 (customer payments, provider settlement, refunds, fees, payout obligations, payouts paid, adjustments) |
| TODO | — | — | account type (asset/liability/revenue) — TODO — needs owner decision |

Indexes: UNIQUE(tenant_id, code)

## journal_entries
Owner: LED. Tenant-scoped: yes. Req IDs: LED-02, LED-18.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | uuid | PK | standard |
| tenant_id | uuid | NOT NULL | standard |
| source_event_id | uuid | NOT NULL | LED-02 "carrying a source event id"; LED-03 dedupe |
| TODO | — | — | entry metadata (memo, reversal linkage) — TODO — needs owner decision |
| created_at | timestamptz | NOT NULL DEFAULT now() | standard |

Indexes: UNIQUE(source_event_id) — LED-03 idempotent posting; append-only per LED-18.

## journal_lines
Owner: LED. Tenant-scoped: yes. Req IDs: LED-02.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | uuid | PK | standard |
| journal_entry_id | uuid | NOT NULL, FK journal_entries | LED-02 |
| ledger_account_id | uuid | NOT NULL, FK ledger_accounts | LED-01 |
| direction | text | NOT NULL | LED-02 balanced sets (debit/credit — enum values — TODO — needs owner decision) |
| amount | numeric | NOT NULL CHECK (amount > 0) | LED-02 balanced sets |
| created_at | timestamptz | NOT NULL DEFAULT now() | standard |

Indexes: (journal_entry_id), (ledger_account_id)

## ledger_balances
Owner: LED. Tenant-scoped: yes. Req IDs: LED-02 (derived), Out Of Scope (dashboards read ledger balances).

| Column | Type | Constraints | Notes |
|---|---|---|---|
| ledger_account_id | uuid | PK, FK ledger_accounts | per-account balance |
| balance | numeric | NOT NULL | maintained from journal lines — TODO — needs owner decision (maintained table vs computed view) |
| updated_at | timestamptz | NOT NULL DEFAULT now() | standard |

Indexes: PK as listed.

## equity_snapshots
Owner: BRG. Tenant-scoped: yes. Req IDs: BRG-07.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | uuid | PK | standard |
| tenant_id | uuid | NOT NULL | standard |
| account_id | uuid | NOT NULL, FK accounts | BRG-07 |
| balance | numeric | NOT NULL | BRG-07 |
| equity | numeric | NOT NULL | BRG-07 |
| TODO | — | — | snapshot timestamp vs created_at semantics; sync-run linkage — TODO — needs owner decision |
| created_at | timestamptz | NOT NULL | BRG-07 timestamped snapshots |

Indexes: (account_id, created_at). NOTE (Fix 4 class): the `UNIQUE` constraint discussion applies to any unique index over nullable columns — see `broker_account_ref` below.

## trades
Owner: BRG. Tenant-scoped: yes. Req IDs: BRG-08.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | uuid | PK | standard |
| tenant_id | uuid | NOT NULL | standard |
| account_id | uuid | NOT NULL, FK accounts | BRG-08 |
| broker_trade_id | text | NOT NULL | BRG-08 normalization |
| TODO | — | — | normalized trade fields (symbol, direction, lots, open/close price, open/close time, pnl) — TODO — needs owner decision (BRG-08 says "unified schema" without defining it) |
| created_at / updated_at | timestamptz | NOT NULL DEFAULT now() | standard |

Indexes: UNIQUE(account_id, broker_trade_id), (account_id, closed_at) — closed_at TODO — needs owner decision

## positions
Owner: BRG. Tenant-scoped: yes. Req IDs: BRG-08.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | uuid | PK | standard |
| tenant_id | uuid | NOT NULL | standard |
| account_id | uuid | NOT NULL, FK accounts | BRG-08 |
| broker_position_id | text | NOT NULL | BRG-08 |
| TODO | — | — | open position fields (symbol, direction, lots, open price, current pnl) — TODO — needs owner decision |
| synced_at | timestamptz | NOT NULL | BRG-07/BRG-08 freshness |
| created_at / updated_at | timestamptz | NOT NULL DEFAULT now() | standard |

Indexes: UNIQUE(account_id, broker_position_id)

## risk_signals
Owner: RSK. Tenant-scoped: yes. Req IDs: RSK-01.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | uuid | PK | standard |
| tenant_id | uuid | NOT NULL | standard |
| type | text | NOT NULL | RSK-01 |
| score | numeric | NOT NULL | RSK-01 |
| source | text | NOT NULL | RSK-01 |
| evidence | jsonb | NULL | RSK-01 |
| status | text | NOT NULL — TODO enum | RSK-01 |
| TODO | — | — | linked trader/account — TODO — needs owner decision (FK columns or case linkage only) |
| created_at / updated_at | timestamptz | NOT NULL DEFAULT now() | standard |

Indexes: (tenant_id, type), (status)

## risk_cases
Owner: RSK. Tenant-scoped: yes. Req IDs: RSK-01, RSK-10.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | uuid | PK | standard |
| tenant_id | uuid | NOT NULL | standard |
| account_id | uuid | NULL, FK accounts | RSK-01 linked accounts |
| trader_id | uuid | NULL, FK users | RSK-01 linked traders |
| opened_by | uuid | NULL, FK users | RSK-10 (manual) or system for threshold |
| opened_reason | text | NULL | RSK-10 |
| review_actions | jsonb | NULL | RSK-01 — structure TODO — needs owner decision |
| final_decision | text | NULL — TODO enum | RSK-01 — values TODO — needs owner decision |
| state | text | NOT NULL | open => decided implied by RSK-10/RSK-01 — enum values — TODO — needs owner decision (column nullable or enum defined at working session) |
| created_at / updated_at | timestamptz | NOT NULL DEFAULT now() | standard |

Indexes: (account_id), (state) — "open case" lookup per RSK-11

## tenant_config
Owner: TEN. Tenant-scoped: yes (1:1). Req IDs: TEN-08, TEN-11.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| tenant_id | uuid | PK, FK tenants | 1:1 with tenant |
| integration_config_encrypted | jsonb | NULL | TEN-11 (broker credentials, payment keys, KYC settings, email sender config), encrypted per TEN-12 |
| TODO | — | — | KYC timing defaults, restricted countries (KYC-13) storage location — TODO — needs owner decision (tenant-level vs challenge-level vs separate table) |
| updated_at | timestamptz | NOT NULL DEFAULT now() | standard |

Indexes: PK as listed.

## tenant_entitlements
Owner: TEN. Tenant-scoped: yes. Req IDs: TEN-08.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | uuid | PK | standard |
| tenant_id | uuid | NOT NULL, FK tenants | TEN-08 |
| module | text | NOT NULL | TEN-08 (V1 module IDs) |
| enabled | boolean | NOT NULL | TEN-08 enable/disable |
| updated_at | timestamptz | NOT NULL DEFAULT now() | standard |

Indexes: UNIQUE(tenant_id, module)

## Read models (ANA-01)
ANA-01 maintains read model tables updated from domain events plus nightly aggregation. Table list and shapes — TODO — needs owner decision (excluded from the SQL schemas until defined).

## Open contract questions

- Resolved 2026-09-17: Phase semantics on `accounts` — per-challenge ordinal, `CHECK (phase >= 1)`; funded stage is `status = FUNDED` and the funded account continues the ordinal past the last evaluation phase. See `accounts.phase` above and `api/lcc.md` state machine.
- LCC-08 (AWAITING_ACTIVATION hold-and-pay flow) and LCC-10 (admin-maintained account chain) are V2.0 in the Master Backlog but the V1 LCC-02 state machine names AWAITING_ACTIVATION — confirm with PRD owners whether a V1 activation-fee product is intended (source-PRD fix, not a contract decision).
- Decide whether `accounts` denormalizes `current_balance` and `current_equity` from the latest `equity_snapshots` row, or whether all reads join to snapshots. Affects TD-03 (dashboard at-a-glance read), PAY-02 (available-profit calculation), and snapshot staleness checks (cites LCC-28 from the handoff doc — not a V1 row; confirm owner or drop). If denormalized, define the update trigger (sync worker write path).
- TODO — needs owner decision: status/state enum CHECK values for every table above (LCC-02, KYC-06, PAY-13 name the values; other enums are open).
- TODO — needs owner decision: NULL-handling for partial unique indexes beyond `accounts.broker_account_ref` and `tenants.subdomain` (Postgres UNIQUE allows multiple NULLs — audit any unique index over a nullable column).
- TODO — needs owner decision: evaluation-audit table (EVL-16: inputs hash, rule version, observed values, thresholds, result) — not in the brief's minimum list; EVL-owned new table needed.
- TODO — needs owner decision: coupon table (CHK-02 reserves coupons; no storage defined anywhere in the sheet).
- TODO — needs owner decision: restricted-countries storage (KYC-13) — tenant_config JSON vs dedicated table.
- TODO — needs owner decision: `api_keys` skipped — AUTH-21 is V2 (per instructions). API Consumer role (AUTH-12) has no V1 surface.

# 31 — Event Catalog (Master)

> **Generated aggregation** of the event tables in the 26 module docs (each
> doc's §4). This is the catalog the CI gate checks against (docs/04 §5.7,
> docs/28 §11): an event emitted but not cataloged, or a consumer that never
> handled it, fails the build. The V1 event schemas live in
> `contracts/events/payloads/` (envelope + 39 V1 event schemas) and the extended
> set in `contracts/events/extended/`; this table is the
> producer/consumer map. `when`/`consumers` are condensed from the owning
> doc's row; the owning doc is the authority. Tier: **V1** = the V1
> execution-sheet baseline (exact names, `contracts/events/catalog.md`);
> **ext** = the extended (post-V1) design set.

## 1. Transport (docs/04 §5, binding)

- Redis Streams, at-least-once, idempotent consumers (04 §5.7); the outbox in
  PG (04 §5.4); the relay = one process (advisory lock) → the V3 two-relay
  partition (29 §3.2). Webhook egress = Hook0 (04 §5.6). SSE = the relay's
  fan-out (01 §4.3). Broker **commands are not events** (EVT-20) — they
  live in `command_queue` and never appear in this catalog.
- **Every event carries** (EVT-03, exactly): `id` (ULID), `type` (event
  name), `version` (integer, starts 1), `tenant_id` (ULID), `occurred_at`
  (int64 epoch ms, UTC), `correlation_id` (ULID — the originating request's
  correlation, required since the ninth pass: docs/49 C1), `payload`
  (event-specific, per-event schema in `contracts/events/payloads/`).
- **The DLQ** (04 §5.6): 5 retries → `evt.consumer_dlq` (04 §6) → the CON-15
  alert (21 §3.2).

## 2. The catalog (160 events — 42 V1 baseline, 118 extended — across 33 topics)

### `user.*`

| Event | Producer | When / V1 producer | Consumers | Tier |
|---|---|---|---|---|
| `user.registered` | 02 (AUTH) | AUTH-01 | NOT-01 (welcome), AUD, ANA | V1 |
| `user.login_success` | 02 (AUTH) | AUTH-04 (session materialisation) | AUD, ANA, RSK (anomaly baseline) | V1 |
| `user.login_failure` | 02 (AUTH) | ZITADEL via Actions v2 | AUD, RSK (anomaly), NOT (security notice) | V1 |
| `user.suspended` | 02 (AUTH) | AUTH-20 / AUTH-43 / idp-sync (IdP-driven, docs/43) | NOT, GW (immediate session kill), AUD | V1 |
| `user.activated` | 02 (AUTH) | AUTH-43 (unsuspend) / idp-sync | NOT, AUD | V1 |
| `user.session_revoked` | 02 (AUTH) | AUTH (logout AUTH-39, suspension AUTH-20) | AUD — admin-initiated revocation is AUTH-27 (V2) | V1 |
| `user.password_changed` | 02 (AUTH) | AUTH-05 / AUTH-40 | session invalidator (all other sessions), AUD | V1 |
| `user.role_changed` | 02 (AUTH) | membership role edited | cache-invalidator (authz), AUD | ext |
| `user.status_changed` | 02 (AUTH) | any identity status transition (from, to, reason) | GW, AUD, ANA | ext |
| `user.email_changed` | 02 (AUTH) | email change verified (AUTH-29, V2) | AUD, NOT (both addresses) | ext |

### `tenant.*`

| Event | Producer | When / V1 producer | Consumers | Tier |
|---|---|---|---|---|
| `tenant.created` | 03 (TEN) | TEN-01 | AUD, CON, NOT (owner) | V1 |
| `tenant.member_invited` | 03 (TEN) | AUTH-03 (V2 row, V1 SSO-tenant exception) | NOT, CON | V1 |
| `tenant.provisioning_step_completed` | 03 (TEN) | TEN (orchestrator, docs/03 §3.5) | CON (live view), NOT (staff) | V1 |
| `tenant.activated` | 03 (TEN) | TEN (checklist complete) | GW (allow traffic), NOT (owner), AUD, ANA | V1 |
| `tenant.suspended` | 03 (TEN) | TEN-15 | AUTH (kill sessions), GW (deny), NOT (owner), AUD — **all stop within 1 s** | V1 |
| `tenant.reactivated` | 03 (TEN) | TEN-15 | GW, NOT, AUD, AUTH (identities stay active; sessions require a new login) | V1 |
| `tenant.plan_changed` | 03 (TEN) | plan/entitlement edit | Flipt sync, limits revalidate, AUD | ext |
| `tenant.settings_changed` | 03 (TEN) | settings JSONB edited | cache invalidator (t:{id}:*), AUD (before/after diff) | ext |
| `tenant.branding_changed` | 03 (TEN) | logo/colours/texts edited | web (cache bust), DOC/NOT (next render), AUD | ext |
| `tenant.deletion_scheduled` | 03 (TEN) | termination saga (§5.2) | CON, AUD, MIG (blocks cutover) | ext |
| `tenant.deactivated` | 03 (TEN) | recovery window (TEN-45, V2) | GW, AUTH, NOT, AUD | ext |
| `tenant.limit_exceeded` | 03 (TEN) | enforcer warning at 80%, hard stop at 100% | NOT (owner), ANA | ext |
| `tenant.entitlement_changed` | 03 (TEN) | module on/off | GW (route gating), Flipt, AUD (TEN-08) | ext |

### `api_key.*`

| Event | Producer | When / V1 producer | Consumers | Tier |
|---|---|---|---|---|
| `api_key.created` | 02 (AUTH) | key lifecycle | AUD — never includes the key | ext |

### `identity.*`

| Event | Producer | When / V1 producer | Consumers | Tier |
|---|---|---|---|---|
| `identity.provisioned` | 02 (AUTH) | IdP-side user created by the tenant saga or SCIM | TEN (access review), AUD | ext |

### `gateway.*`

| Event | Producer | When / V1 producer | Consumers | Tier |
|---|---|---|---|---|
| `gateway.rate_limit_breached` | 04 (GW+EVT) | GW | ANA, CON | ext |

### `outbox.*`

| Event | Producer | When / V1 producer | Consumers | Tier |
|---|---|---|---|---|
| `outbox.pruned` | 04 (GW+EVT) | relay | AUD | ext |

### `ledger.*`

| Event | Producer | When / V1 producer | Consumers | Tier |
|---|---|---|---|---|
| `ledger.entry_posted` | 05 (LED/AUD) | LED | ext | ext |
| `ledger.entry_reversed` | 05 (LED/AUD) | LED | ext | ext |
| `ledger.reconciliation_exception` | 05 (LED/AUD) | worker | ext | ext |

### `audit.*`

| Event | Producer | When / V1 producer | Consumers | Tier |
|---|---|---|---|---|
| `audit.critical_action` | 05 (LED/AUD) | AUD (tiered) | ext | ext |
| `audit.export_completed` | 05 (LED/AUD) | AUD | ext | ext |
| `audit.access_denied` | 17 (ADM) | security tab (V2) | security tab (V2) | ext |

### `ops.*`

| Event | Producer | When / V1 producer | Consumers | Tier |
|---|---|---|---|---|
| `ops.deploy_started` | 06 (OPS) | every deploy step | CON (internal dashboard), NOT (staff channel on failure) | ext |
| `ops.backup_completed` | 06 (OPS) | nightly base backup (03:00 UTC) | CON, NOT (staff channel on failure) | ext |
| `ops.restore_drill_completed` | 06 (OPS) | monthly restore drill (OPS-38) | CON (drill report filed) | ext |
| `ops.provider_health` | 08 (BRG) | 5 min | CON, dashboards | ext |

### V1 PascalCase events (LCC-23)

| Event | Producer | When / V1 producer | Consumers | Tier |
|---|---|---|---|---|
| `AccountCreated` | 07 (LCC) | LCC-23 | NOT-01 (template: account created), ANA-01 | V1 |
| `PhaseAdvanced` | 07 (LCC) | LCC-23 | ANA-01 | V1 |
| `AccountPassed` | 07 (LCC) | LCC-23 | NOT-01 (template: phase passed), DOC-04 (certificate), ANA-01 | V1 |
| `AccountBreached` | 07 (LCC) | LCC-23 | NOT-01 (template: breach), ANA-01, RSK (breach case auto-open — D68: V1.0, hold flag dormant until V1.1, docs/60) | V1 |
| `AccountFailed` | 07 (LCC) | LCC-23 | NOT-01 (template: phase failed), ANA-01 | V1 |
| `FundedCreated` | 07 (LCC) | LCC-23 | DOC-04 (certificate), ANA-01 | V1 |
| `Suspended` | 07 (LCC) | LCC-23 | PAY-04 (payout hold while open), ANA-01 | V1 |
| `Resumed` | 07 (LCC) | LCC-23 | ANA-01 | V1 |

### `account.*`

| Event | Producer | When / V1 producer | Consumers | Tier |
|---|---|---|---|---|
| `account.activated` | 07 (LCC) | LCC (CREATED → ACTIVE on the completed provisioning command; the V2 event form is bridge.account_created) | BRG (start sync), EVL (start evaluation + create evaluation_state), NOT-01, AUD | V1 |
| `account.day_rolled` | 07 (LCC) | LCC (rollover job at broker-server midnight, ADR-12; skips SUSPENDED — D31) | EVL (daily reset), ANA | V1 |
| `account.purchased` | 07 (LCC) | order.paid | NOT, ANA, CON | ext |
| `account.provisioning_failed` | 07 (LCC) | provisioning-command failure (the V2 event form is bridge.account_create_failed) | NOT, CON (manual retry), AUD | ext |
| `account.breached` | 07 (LCC) | verdict.breach | NOT, AUD (critical), RSK (case open — V1 for kind=breach, docs/10 §3), BRG (enforce cmd), TD (breach report), PAY (hold in-flight approved payouts... | ext |
| `account.phase_completed` | 07 (LCC) | target_hit | NOT, DOC (cert), ANA | ext |
| `account.funded` | 07 (LCC) | funded.activated | NOT, DOC, ANA, PAY (eligibility on) | ext |
| `account.paused` | 07 (LCC) | tenant | NOT, BRG, AUD | ext |
| `account.suspended` | 07 (LCC) | admin suspend (LCC-11, V1.1); risk (V2 reinstate) | NOT, BRG, PAY (block), AUD (critical) | ext |
| `account.expired` | 07 (LCC) | time-limit expiry (mirror of the breach(time_limit) verdict — D30) | NOT, ANA | ext |
| `account.closed` | 07 (LCC) | close | BRG (archive), NOT, AUD | ext |
| `account.state_changed` | 17 (ADM) | account list badges + SSE | account list badges + SSE | ext |

### `bridge.*`

| Event | Producer | When / V1 producer | Consumers | Tier |
|---|---|---|---|---|
| `bridge.tick` | 08 (BRG) | BRG (sync loop, per account, 60 s cadence) | EVL (evaluate), ANA (equity points) — the observed record per EVL-49; no audit mirror (docs/05 §14) | V1 |
| `bridge.sync_gap` | 08 (BRG) | BRG (history-window count mismatch — D33) | ADM (manual review), AUD, EVL (gap_flagged verdict) | V1 |
| `bridge.account_created` | 08 (BRG) | provisioning | LCC, NOT, CON | ext |
| `bridge.trading_disabled` | 08 (BRG) | after confirmed command | LCC (confirm transition), AUD | ext |
| `bridge.positions_closed` | 08 (BRG) | after confirmed close-all | LCC, AUD, NOT (breach evidence) | ext |
| `bridge.reconciliation_exception` | 08 (BRG) | nightly mismatch | ADM, AUD, CON | ext |
| `bridge.command_dead` | 08 (BRG) | terminal command failure | CON (CRITICAL), AUD | ext |

### `evaluation.*`

| Event | Producer | When / V1 producer | Consumers | Tier |
|---|---|---|---|---|
| `evaluation.verdict` | 09 (EVL) | EVL (every non-ok verdict) | LCC (transitions; dedupe on (account_id, verdict_id), LCC-43), NOT-01, DOC-04 (breach report TD-25), AUD (critical on breach), RSK (V2 case open) | V1 |
| `evaluation.daily_reset` | 09 (EVL) | EVL (rollover) | ANA (daily P&L points), AUD (standard) | V1 |
| `evaluation.risk_guard` | 09 (EVL) | buffer breach | ADM (page), AUD | ext |
| `evaluation.override` | 09 (EVL) | manual clear | LCC, NOT, AUD (critical) | ext |
| `evaluation.manual_run` | 09 (EVL) | ADM trigger | AUD | ext |
| `evaluation.emergency` | 09 (EVL) | CON stop | LCC, AUD (critical), NOT | ext |
| `evaluation.recomputed` | 09 (EVL) | backfill changed history | AUD (critical), CON | ext |

### `risk.*`

| Event | Producer | When / V1 producer | Consumers | Tier |
|---|---|---|---|---|
| `risk.case_opened` | 10 (RSK) | manual open (RSK-10) / breach auto-open on AccountBreached (D68) | ADM (queue), AUD, ANA (risk_summary daily counts) | V1 |
| `risk.case_decided` | 10 (RSK) | decision | PAY (hold release/keep — the interlock from V1.1), LCC (if action), AUD (sensitive — docs/05 §14), ANA (risk_summary daily counts) | V1 |
| `risk.signal_created` | 10 (RSK) | any signal | ANA (V2), AUD (standard) | ext |
| `risk.case_escalated` | 10 (RSK) | SLA breach | NOT (owner + CON), AUD | ext |
| `risk.case_appealed` | 10 (RSK) | trader appeal | ADM, AUD | ext |
| `risk.payout_hold_set` | 10 (RSK) | hold lifecycle (RSK-11/PAY-04, V1.1+) | PAY, NOT, AUD | ext |

### `payout.*`

| Event | Producer | When / V1 producer | Consumers | Tier |
|---|---|---|---|---|
| `payout.approved` | 11 (PAY) | PAY-09 | LED-07 (payout obligation posting), NOT-01 (template: payout approved), ANA-01 | V1 |
| `payout.rejected` | 11 (PAY) | PAY-09 | NOT-01 (template: payout rejected), ANA-01 | V1 |
| `payout.settled` | 11 (PAY) | PAY-12 (execution recording, via outbox — Decision 6) | LED-08 (settlement posting), DOC-04 (receipt), ANA-01 | V1 |
| `payout.requested` | 11 (PAY) | request created (eligible) | NOT (trader + finance), ANA | ext |
| `payout.eligibility_failed` | 11 (PAY) | request rejected at validation | NOT (trader, reason template) | ext |
| `payout.execution_attempted` | 11 (PAY) | each send/retry | AUD | ext |
| `payout.failed` | 11 (PAY) | rail failure | NOT (on final), ADM, AUD | ext |
| `payout.cancelled` | 11 (PAY) | trader cancel (pre-approval) | NOT, ANA | ext |
| `payout.hold_set` | 11 (PAY) | RSK interplay (V2) | AUD | ext |
| `payout.reconciled` | 11 (PAY) | nightly | ADM, CON, AUD | ext |
| `payout.status_changed` | 17 (ADM) | queue live update + badge | queue live update + badge | ext |

### `order.*`

| Event | Producer | When / V1 producer | Consumers | Tier |
|---|---|---|---|---|
| `order.paid` | 12 (CHK) | CHK-09 (payment captured, via CHK-07 webhook + CHK-08 order) | LCC-05 (provisioning), LED-04 (payment capture posting), ANA-01 | V1 |

### `checkout.*`

| Event | Producer | When / V1 producer | Consumers | Tier |
|---|---|---|---|---|
| `checkout.session.expired` | 12 (CHK) | CHK-43 (scheduled expiry worker, via outbox) | ANA-01 (funnel/abandonment read model) | V1 |
| `checkout.order_state` | 16 (TD) | /buy completion screen (polling fallback) | /buy completion screen (polling fallback) | ext |

### `payment.*`

| Event | Producer | When / V1 producer | Consumers | Tier |
|---|---|---|---|---|
| `payment.intent_created` | 12 (CHK) | intent issued | AUD | ext |
| `payment.intent_captured` | 12 (CHK) | webhook captured | LED (cash/revenue), LCC (saga start), DOC, NOT, ANA, AUD | ext |
| `payment.intent_failed` | 12 (CHK) | webhook/TTL | NOT (trader: "complete your payment"), ANA | ext |
| `payment.wire_captured` | 12 (CHK) | manual finance capture | same as captured | ext |
| `payment.refund_requested` | 12 (CHK) | refund flow | LED (reversal on settled), DOC, NOT, RSK (V2 chargeback signals), AUD | ext |
| `payment.reconciliation_exception` | 12 (CHK) | nightly | ADM, CON, AUD | ext |

### `kyc.*`

| Event | Producer | When / V1 producer | Consumers | Tier |
|---|---|---|---|---|
| `kyc.submitted` | 13 (KYC) | KYC-05 (webhook status handling), KYC-16 | NOT-01 (template: KYC result), ANA-01 | V1 |
| `kyc.approved` | 13 (KYC) | KYC-05, KYC-16 | NOT-01, LCC-06 (auto-upgrade on approval), PAY-03 (payout eligibility), ANA-01 | V1 |
| `kyc.rejected` | 13 (KYC) | KYC-05, KYC-16 | NOT-01, ANA-01 | V1 |
| `kyc.expired` | 13 (KYC) | KYC-05, KYC-16 | NOT-01, ANA-01 — EXPIRED trigger is an open question | V1 |
| `kyc.resubmission_requested` | 13 (KYC) | KYC-05, KYC-16 | NOT-01, ANA-01 | V1 |
| `kyc.session_started` | 13 (KYC) | session created (level) | AUD, ANA (funnel) | ext |
| `kyc.status_changed` | 17 (ADM) | KYC queue | KYC queue | ext |
| `kyc.verified` | 13 (KYC) | level verified (record ref) | CHK (gate unblock notification), PAY (gate), ANA, AUD | ext |
| `kyc.manual_review_requested` | 13 (KYC) | provider undecided → queue | NOT (staff), AUD | ext |
| `kyc.gate_blocked` | 13 (KYC) | a gated action failed on KYC | ANA (drop-off funnel), NOT (trader "complete your verification") | ext |
| `kyc.consent_recorded` | 13 (KYC) | consent captured | AUD (compliance) | ext |

### `notification.*`

| Event | Producer | When / V1 producer | Consumers | Tier |
|---|---|---|---|---|
| `notification.sent` | 14 (NOT) | channel accept (provider ref) | AUD (low tier), ANA (V2) | V1 |
| `notification.failed_final` | 17 (ADM) | ops alert surface (V1: a simple "ops alerts" list on the home; V2: routing ADM-37) | ops alert surface (V1: a simple "ops alerts" list on the home; V2: routing ADM-37) | ext |
| `notification.suppressed` | 14 (NOT) | dedupe (V1); prefs/quiet-hours/bounce (V2) | AUD (low), ANA | V1 |
| `notification.bounce` | 14 (NOT) | provider webhook | AUD | ext |
| `notification.broadcast_sent` | 14 (NOT) | staff broadcast | AUD (critical) | ext |

### `document.*`

| Event | Producer | When / V1 producer | Consumers | Tier |
|---|---|---|---|---|
| `document.generated` | 16 (TD) | documents badge "new" (V2 in-app notification) | documents badge "new" (V2 in-app notification) | ext |
| `document.failed` | 15 (DOC) | retries exhausted (DLQ) | ADM (ops alert), CON, AUD | V1 |
| `document.regenerated` | 15 (DOC) | admin action | AUD (critical-tier if it changes a money doc) | ext |
| `document.verified_lookup` | 15 (DOC) | public verify page hit | ANA (marketing metric) | ext |

### `equity.*`

| Event | Producer | When / V1 producer | Consumers | Tier |
|---|---|---|---|---|
| `equity.point` | 16 (TD) | chart append | chart append | ext |

### `ticket.*`

| Event | Producer | When / V1 producer | Consumers | Tier |
|---|---|---|---|---|
| `ticket.created` | 18 (SUP) | created (surface: trader/staff) | NOT (email ack to trader; staff notify), AUD | ext |
| `ticket.replied` | 18 (SUP) | any message (kind) | NOT (the other side, per kind), ANA | ext |
| `ticket.status_changed` | 18 (SUP) | status transition | NOT, ANA, AUD | ext |
| `ticket.escalated` | 18 (SUP) | SLA breach / manual | NOT (owner chain), AUD (critical if money-linked) | ext |
| `ticket.satisfaction_submitted` | 18 (SUP) | survey response | ANA | ext |

### `analytics.*`

| Event | Producer | When / V1 producer | Consumers | Tier |
|---|---|---|---|---|
| `analytics.read_model_drift` | 19 (ANA) | reconciliation mismatch | CON (CRITICAL), ADM, AUD | ext |
| `analytics.read_model_rebuilt` | 19 (ANA) | rebuild complete | AUD | ext |
| `analytics.report_generated` | 19 (ANA) | async report done | NOT (email link), AUD | ext |
| `analytics.kpi_alert` | 19 (ANA) | threshold breach | NOT (per routing), CON, AUD | ext |

### `crm.*`

| Event | Producer | When / V1 producer | Consumers | Tier |
|---|---|---|---|---|
| `crm.segment_recomputed` | 20 (CRM) | 15-min cadence / manual | AUD (low) | ext |
| `crm.campaign_sent` | 20 (CRM) | batch dispatched to NOT | NOT (the actual sends), ANA (CRM-08 inputs), AUD (critical: marketing sends are tenant-visible) | ext |
| `crm.sequence_advanced` | 20 (CRM) | step engine | AUD (low) | ext |
| `crm.consent_changed` | 20 (CRM) | capture/unsubscribe/withdrawal | NOT (suppression list), AUD (critical) | ext |
| `crm.unsubscribe` | 20 (CRM) | link clicked | NOT, AUD | ext |

### `console.*`

| Event | Producer | When / V1 producer | Consumers | Tier |
|---|---|---|---|---|
| `console.operator_action` | 21 (CON) | any 2FA'd action (control, suspension, impersonation) | AUD (critical), NOT (ops channel) | ext |
| `console.escalation_approved` | 21 (CON) | second operator approves | AUD (critical) | ext |

### `billing.*`

| Event | Producer | When / V1 producer | Consumers | Tier |
|---|---|---|---|---|
| `billing.metering_recorded` | 22 (BIL) | nightly rollup (V1+) | CON (metering view), AUD (low) | ext |
| `billing.invoice_created` | 22 (BIL) | Lago webhook | DOC, NOT, CON (billing queue), AUD | ext |
| `billing.subscription_state_changed` | 22 (BIL) | active/past_due/paused/terminated | TEN (entitlement sync BIL-04), CON, NOT, AUD (critical on pause/terminate) | ext |
| `billing.entitlement_degraded` | 22 (BIL) | grace flag set | TEN (banner), NOT | ext |
| `billing.credit_note_issued` | 22 (BIL) | adjustment | CON, AUD (critical) | ext |

### `affiliate.*`

| Event | Producer | When / V1 producer | Consumers | Tier |
|---|---|---|---|---|
| `affiliate.attributed` | 23 (AFF) | signup attribution (method) | AUD (critical — money's origin) | ext |
| `affiliate.accrual_created` | 23 (AFF) | captured purchase with ref | AUD, ANA | ext |
| `affiliate.accrual_settled` | 23 (AFF) | window close, no refund | AUD | ext |
| `affiliate.accrual_reversed` | 23 (AFF) | refund/chargeback | NOT (affiliate notice), AUD (critical) | ext |
| `affiliate.payout_settled` | 23 (AFF) | execution complete | NOT (receipt), DOC, AUD (critical) | ext |
| `affiliate.conversion` | 23 (AFF) | the tenant's webhook (Hook0) | the tenant's system (V3 DVP surface) | ext |

### `site.*`

| Event | Producer | When / V1 producer | Consumers | Tier |
|---|---|---|---|---|
| `site.page_published` | 24 (CMS/CMP) | pointer flip | AUD (critical on legal pages), ANA (cache purge hint) | ext |
| `site.lead_captured` | 24 (CMS/CMP) | form submission | CRM (contact), SUP (ticket), NOT, AUD | ext |
| `site.pricing_changed` | 24 (CMS/CMP) | TEN catalog change | ANA (widget cache invalidation), AUD (low) | ext |
| `site.visit` | 24 (CMS/CMP) | page view (anonymous, first-party) | ANA (funnel: visit → signup, the CRM-08/ANA-09 top of funnel) | ext |

### `migration.*`

| Event | Producer | When / V1 producer | Consumers | Tier |
|---|---|---|---|---|
| `migration.started` | 25 (MIG) | import begins (class) | CON (ops), AUD (critical) | ext |
| `migration.class_completed` | 25 (MIG) | a data class lands (counts, exceptions) | CON, AUD | ext |
| `migration.reconciled` | 25 (MIG) | the report (match rate, exceptions) | CON (the cutover gate reads it), AUD (critical) | ext |
| `migration.exception_dispositioned` | 25 (MIG) | an exception is dispositioned (2FA'd) | AUD (critical) | ext |
| `migration.cutover_complete` | 25 (MIG) | T_date flip done | CON, AUD (critical — the platform's biggest audit event of the year) | ext |
| `migration.parallel_drift` | 25 (MIG) | the daily comparator exceeds 1¢ | CON (P1), NOT (ops), AUD (critical) | ext |
| `migration.closed` | 25 (MIG) | parallel run signed | CON, AUD | ext |

### `developer.*`

| Event | Producer | When / V1 producer | Consumers | Tier |
|---|---|---|---|---|
| `developer.usage_alert` | 27 (SDK/DVP/TRD/PLT/CS) | the 80%/100% quota | the NOT (the developer's email), the AUD (the low) | ext |
| `developer.support_ticket` | 27 (SDK/DVP/TRD/PLT/CS) | the SUP category | the SUP queue (the 18 pattern), the AUD (the low) | ext |

### `sandbox.*`

| Event | Producer | When / V1 producer | Consumers | Tier |
|---|---|---|---|---|
| `sandbox.inject` | 27 (SDK/DVP/TRD/PLT/CS) | the injection | the AUD (the sandbox low), the ANA (the sandbox usage) | ext |

### `webhook.*`

| Event | Producer | When / V1 producer | Consumers | Tier |
|---|---|---|---|---|
| `webhook.delivery_failed_final` | 27 (SDK/DVP/TRD/PLT/CS) | the DLQ | the developer's log (the portal), the AUD (the low), the NOT (the tenant admin, the "your webhook is down" — the 04 §5.6 posture) | ext |


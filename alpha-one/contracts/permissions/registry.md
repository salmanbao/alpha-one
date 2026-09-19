# Permission Registry

Status: DRAFT
Owner: TBD
Version: v1
Last updated: 2026-09-17

Derived from the V1 Execution Sheet (V1.0 / V1.1) of `Alpha One PRD.xlsx`.
Key format: `resource.action` (AUTH-13). Keys are module-declared and enforced at the API layer (GW-04).
Every key names its owning module and description with the Req ID that justifies it.

| Permission key | Module owner | Description |
|---|---|---|
| `user.suspend` | AUTH | Suspend a user, immediately invalidating sessions and tokens. (AUTH-20) |
| `user.unsuspend` | AUTH | Restore access for a previously suspended user, with audit. (AUTH-43) |
| `tenant.create` | TEN | Create a tenant and check subdomain availability/reservation. (TEN-01, TEN-42) |
| `tenant.read` | TEN | View tenant records. (TEN-01) |
| `tenant.update` | TEN | Edit tenant records. (TEN-01) |
| `tenant.suspend` | TEN | Suspend a tenant, stopping logins, orders, and payouts. (TEN-15) |
| `tenant.terminate` | TEN | Terminate a tenant. (TEN-01) |
| `tenant.entitlement.change` | TEN | Enable or disable modules per tenant; manual and immediate in V1. (TEN-08) |
| `tenant.integration.write` | TEN | Store tenant integration config (broker credentials, payment keys, KYC settings, email sender). (TEN-11) |
| `tenant.integration.read` | TEN | View masked integration config. (TEN-11; masking rules — TODO — needs owner decision, TEN-12) |
| `challenge.write` | EVL | Define challenges: type, sizes, pricing, phases, per-phase rules. (EVL-01) |
| `ruleset.write` | EVL | Create and version rule sets; choose migration policy for in-flight accounts. (EVL-02, EVL-34) |
| `account.read` | LCC | List and filter all trading accounts by status, phase, challenge, broker. (ADM-05) |
| `account.suspend` | LCC | Suspend and resume an account with a recorded reason; pauses trading safely. (LCC-11) |
| `account.manual_override` | EVL | Manually pass, fail, or reset an account with a recorded reason. (EVL-20) |
| `account.evaluate` | EVL | Force re-evaluation of a single account after a corrected snapshot. (EVL-36) |
| `payout.request` | PAY | Request a payout of available profit on a funded account. (PAY-01) |
| `payout.approve` | PAY | Approve or reject payout requests with a recorded reason. (PAY-09) |
| `payout.read_queue` | PAY | View the approval queue with full context: account, profit, rules, KYC, risk. (PAY-08) |
| `payout.record_execution` | PAY | Record executed payouts with provider, reference, amount, timestamp; batch export. (PAY-12, PAY-44) |
| `payout.policy.write` | PAY | Configure payout policy per challenge or funded type. (PAY-38) |
| `payout.method.write` | PAY | Save and confirm payout methods (crypto wallet, bank details). (PAY-05) — trader self-action |
| `payout.method.read` | PAY | View own payout methods. (PAY-05) — trader self-action |
| `kyc.review` | KYC | Review uploaded documents manually when provider unavailable or flags a case. (KYC-11) |
| `kyc.restrictions.write` | KYC | Maintain the restricted country list. (KYC-13) |
| `document.read` | DOC | View and download own certificates. (DOC-06) — trader self-action |
| `risk.case.create` | RSK | Open a risk case manually. (RSK-10) |
| `audit.read` | AUD | View and search audit logs; every view/search itself recorded. (AUD-21) — key naming — TODO — needs owner decision (AUD-06 not a V1 row) |
| `audit.export` | AUD | Export audit logs; export itself recorded. (AUD-21) |
| `analytics.read` | ANA | View the real-time KPI dashboard. (ANA-32) — key naming — TODO — needs owner decision (ANA-13 not a V1 row) |
| `console.session.revoke` | CON | Revoke another super admin's console session. (CON-30) |

## Permission model notes
- Trader self-actions (registration, login, own account reads, checkout, own payout requests, own documents) are identity-scoped: the caller is the resource. Whether they additionally require permission keys — TODO — needs owner decision (AUTH-13 requires declared keys; the sheet's stories are self-referential).
- `tenant.impersonate`: **no such key in V1.** AUTH-16 is a separation contract — the console identity cannot act inside a tenant at all because no impersonation path exists. Enablement (TEN-16, CON-07, AUD-08) is V2.0 and would introduce the key with its audit format. See `api/auth.md` ("Impersonation (AUTH-16)").
- Role bindings (which role gets which key) are not defined by any V1 row — TODO — needs owner decision (AUTH-12 defines roles: Super Admin, Tenant Admin, custom staff, Trader, API Consumer).
- Field-level permissions beyond route/action permissions are out of scope (Out Of Scope sheet).

## Open contract questions
- TODO — needs owner decision: role-to-permission binding table per role (AUTH-12 × AUTH-13).
- TODO — needs owner decision: permission keys for trader self-actions — required or identity-scoped only?
- Resolved 2026-09-17: no `tenant.impersonate` key in V1 (AUTH-16 separation-only; no impersonation endpoint exists). Enablement is V2.
- TODO — needs owner decision: keys for staff access to sensitive data (AUD-23 audits access to KYC documents and payout methods; which permission gates that access?).
- TODO — needs owner decision: key naming conventions above marked TODO (`audit.read`, `analytics.read`, `payout.read_queue`, masking reads).


---

## Extended (provisional) keys (design-level)

> Appended 2026-09-19 by `scripts/complete_contracts_pack.py`, mined from module docs §7 endpoint tables + api specs. The V1 registry above is untouched and remains binding. Each key freezes with its module's phase (docs/99 §12); role bindings are fixed at freeze (AUTH-12 × AUTH-13 open question).

| Permission key | Module (source) | Source |
|---|---|---|
| `account.force_pass` | evl | contracts/api/evl.md |
| `checkout.create` | chk | contracts/api/chk.md |

## Proposed post-V1 keys (design-level, 2026-09-19)

> Hand-proposed from each module doc's §7 endpoint surface + PRD scope. NOT yet
> mined from frozen contracts (unlike the section above). Each key freezes with its
> module's phase (docs/99 §12); names may change at freeze. Role bindings
> (AUTH-12 × AUTH-13) are fixed at freeze. MOB proposes no keys (mobile reuses
> the TD API surface — Out Of Scope: no mobile-specific API). SDK proposes no
> `resource.action` keys (public scopes like `trades:read` are a separate catalog,
> docs/27 Part A §3.1).

| Permission key | Module owner | Description |
|---|---|---|
| `ticket.create` | SUP | Open a ticket (trader: own; staff: on behalf). (SUP-01) |
| `ticket.read` | SUP | Read own tickets (trader) / queue + detail (staff). (SUP-04, SUP-06) |
| `ticket.reply` | SUP | Reply + attach evidence. (SUP-05) |
| `ticket.assign` | SUP | Assign to staff, set priority. (SUP-10, SUP-11) |
| `ticket.status.write` | SUP | Transition status; 2FA for `resolved` on money-linked tickets. (SUP-03) |
| `ticket.note` | SUP | Internal staff notes (never trader-visible). (SUP-07) |
| `canned.write` | SUP | Manage canned replies + templates. (V2) |
| `support.report.read` | SUP | SLA + agent performance reports. (SUP-25, SUP-31) |
| `segment.read` | CRM | View segments + counts. (CRM-01) |
| `segment.write` | CRM | Create/edit segments (RSK-exclusion enforced). (CRM-02) |
| `campaign.read` | CRM | View campaigns + delivery stats. (CRM-06) |
| `campaign.write` | CRM | Create/edit campaigns, sequences. (CRM-06) |
| `campaign.send` | CRM | Approve + launch a send (2FA, volume guard). (CRM-06) |
| `consent.read` | CRM | View consent records. (CRM-07) |
| `crm.export` | CRM | Export CRM data (portability). (CRM-16) |
| `invoice.read` | BIL | View tenant invoices (platform: all; tenant: own). (BIL-07) |
| `invoice.write` | BIL | Draft/adjust invoices. (BIL-16) |
| `invoice.approve` | BIL | Approve + issue (two-op in V3). (BIL-21) |
| `usage.read` | BIL | View metering counters. (CON-10 input) |
| `dunning.manage` | BIL | Retry schedules, grace, suspension on non-pay. (BIL-12) |
| `affiliate.read` | AFF | View program + own referrals/earnings. (AFF-01) |
| `affiliate.write` | AFF | Configure program, rate cards. (AFF-05) |
| `affiliate.approve` | AFF | Approve affiliates + manual overrides. (AFF-03) |
| `commission.read` | AFF | View commission ledger. (AFF-10) |
| `commission.adjust` | AFF | Manual adjustments + reversals (audited). (AFF-14) |
| `affiliate.payout.execute` | AFF | Record affiliate payout execution. (AFF-20) |
| `site.read` | CMS | View published site + drafts. (CMS-01) |
| `site.publish` | CMS | Publish/unpublish (tenant admin). (CMS-08) |
| `page.write` | CMS | Create/edit pages + sections. (CMS-03) |
| `media.write` | CMS | Upload/manage media (tenant prefix). (CMS-06) |
| `competition.read` | CMP | View competitions + leaderboards. (CMP-01) |
| `competition.write` | CMP | Create/edit competitions + scoring rules. (CMP-04) |
| `competition.score` | CMP | Run scoring + publish results. (CMP-09) |
| `prize.award` | CMP | Award prizes (two-op, audited). (CMP-12) |
| `entry.create` | CMP | Enter a competition (trader self-action). (CMP-02) |
| `migration.import` | MIG | Run + dry-run importers. (MIG-01, MIG-07) |
| `migration.reconcile` | MIG | Run reconciliation + corrections. (MIG-04) |
| `migration.cutover` | MIG | Execute cutover (super admin, two-op). (MIG-06) |
| `migration.report.read` | MIG | Validation reports + sign-off pack. (MIG-08) |
| `journal.read` | JRN | Read own journal + analytics. (JRN-01) |
| `journal.write` | JRN | Create/edit entries, tags. (JRN-02) |
| `journal.share` | JRN | Share read-only entry links. (JRN-08, V3) |
| `course.read` | EDU | Browse + consume courses. (EDU-01) |
| `course.write` | EDU | Publish/edit courses + lessons. (EDU-04) |
| `lesson.complete` | EDU | Record progress (trader self-action). (EDU-03) |
| `channel.read` | CHT | Join/read community channels. (CHT-01) |
| `channel.write` | CHT | Create/manage channels (staff). (CHT-04) |
| `message.create` | CHT | Post messages (trader). (CHT-01) |
| `message.moderate` | CHT | Delete/ban/timeout (staff, audited). (CHT-05) |
| `role.sync` | CHT | Run Discord/Telegram role automation. (CHT-02) |
| `devkey.create` | DVP | Create portal API keys (2FA). (DVP-06) |
| `devkey.read` | DVP | List keys + usage. (DVP-06) |
| `devkey.revoke` | DVP | Revoke keys (2FA). (DVP-06) |
| `webhook.delivery.read` | DVP | View delivery logs. (DVP-05) |
| `webhook.delivery.replay` | DVP | Replay sandbox deliveries. (DVP-05) |
| `sandbox.reset` | DVP | Reset sandbox tenant data. (SDK-06) |
| `copy.follow` | TRD | Follow/unfollow a strategy (trader). (TRD-01) |
| `backtest.run` | TRD | Run backtests (quota-guarded). (TRD-04) |
| `paper.reset` | TRD | Reset paper account. (TRD-05) |
| `algo.deploy` | TRD | Deploy/pause personal algos. (TRD-06) |
| `platform.health.read` | PLT | Cross-tenant SLO + incident posture. (PLT-04) |
| `platform.cost.read` | PLT | Cost allocation + budgets. (PLT-03) |
| `platform.capacity.read` | PLT | Capacity plans + region posture. (PLT-01, PLT-02) |
| `tenant.health.read` | CS | Health scores + churn signals. (CS-02, CS-03) |
| `nps.manage` | CS | Send + analyze NPS surveys. (CS-01) |
| `qbr.read` | CS | Generate + view QBR reports. (CS-07) |
| `playbook.execute` | CS | Run onboarding/retention playbooks. (CS-04, CS-05) |

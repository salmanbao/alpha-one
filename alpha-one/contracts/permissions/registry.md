# Permission Registry

Status: RATIFIED (V1 bindings ratified 2026-09-19 — decision D14, docs/44 §4)
Owner: AUTH (Tech Lead)
Version: v1
Last updated: 2026-09-19

Derived from the V1 Execution Sheet (V1.0 / V1.1) of `Alpha One PRD.xlsx`.
Key format: `resource.action` (AUTH-13). Keys are module-declared and enforced at the API layer (GW-04).
Every key names its owning module and description with the Req ID that justifies it.
**Role bindings: `contracts/permissions/roles.yaml`** (decision D14, docs/44 §4): the single
source for who holds what, seeded into Casbin. Generated views (do not edit by hand):
`contracts/permissions/matrix.md` (role × key matrix, key detail, V1 route map — regenerated
by `scripts/verify_roles.py --write-matrix`, freshness is gate 15). The consolidated
developer-facing specification is [docs/46-authorization-model.md](../docs/46-authorization-model.md).

**V1 key count: 36** (31 original + 3 platform keys promoted 2026-09-19 + `payout.method.review`
and `kyc.document.read`) — plus 10 provisional keys and the reserved post-V1 keys.

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
| `tenant.integration.read` | TEN | View masked integration config — never decrypts (docs/03 §3.7, TEN-12). (TEN-11) |
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
| `risk.case.read` | RSK | View the risk queue: cases, signal summaries, hold state. (docs/17 §3.1, the V1-era thin view — nineteenth pass, docs/60) |
| `risk.case.decide` | RSK | Decide a risk case (outcome + note); **2FA step-up always** (D70). (RSK-01 case machine) |
| `payout.method.review` | PAY | View **another trader's** payout methods for approval; access is audited (AUD-23). (PAY-08/PAY-09) — added 2026-09-19 (D14) |
| `kyc.document.read` | KYC | View/download a trader's KYC documents; access is audited (AUD-23). (KYC-11) — added 2026-09-19 (D14) |
| `audit.read` | AUD | View and search audit logs; every view/search itself recorded. (AUD-21) — key name ratified 2026-09-19 (D14) |
| `audit.export` | AUD | Export audit logs; export itself recorded. (AUD-21) |
| `analytics.read` | ANA | View the real-time KPI dashboard **of the caller's own firm**. (ANA-32) — key name ratified 2026-09-19 (D14) |
| `console.session.revoke` | CON | Revoke another super admin's console session (CON-30 — V1 route `POST /v1/console/sessions/{id}/revoke`; AUTH-27 cross-identity forced logout is the V2 extension). |
| `platform.identity.admin` | AUTH | Platform-staff identity administration: create/deactivate console users, force MFA reset (AUTH-28), break-glass. (AUTH-16, AUTH-28) — promoted to V1 2026-09-19 (D14) |
| `platform.tenant.provision` | TEN | Run/resume the tenant provisioning saga and destroy a tenant org in the IdP. (docs/03 §3.5) — promoted to V1 2026-09-19 (D14) |
| `platform.session.revoke` | AUTH | Revoke another identity's sessions (admin forced logout, AUTH-27). — promoted to V1 2026-09-19 (D14) |

## Permission model notes
- **Role bindings are ratified (2026-09-19, decision D14, docs/44 §4).** The mapping
  (role → key, with scope and ABAC constraints) is `contracts/permissions/roles.yaml`:
  it seeds the Casbin `casbin_rule` table by migration, and docs/02 §3.1 renders it.
  A key with no binding is denied for every role; `scripts/verify_roles.py` keeps the YAML,
  the seed and the rendered tables in agreement.
- Trader self-actions (own payout requests and methods, own documents) are **declared keys
  with scope `own`**: AUTH-13's "declared keys" is satisfied and the own-data ABAC matcher
  does the resource check. Actions with no resource beyond the session (login, logout,
  password change, MFA enrolment) require no key. (Closed 2026-09-19, D14.)
- `tenant.impersonate`: **no such key in V1.** AUTH-16 is a separation contract — the console identity cannot act inside a tenant at all because no impersonation path exists. Enablement (TEN-16, CON-07, AUD-08) is V2.0 and would introduce the key with its audit format. See `api/auth.md` ("Impersonation (AUTH-16)").
- Field-level permissions beyond route/action permissions are out of scope (Out Of Scope sheet).
- **Every V1 endpoint declares its authorization in the contract** (`x-permission`): a registry
  key, or an explicit keyless marker — `self` (the caller acting on their own data; the own-data
  matcher still runs) or `none` (unauthenticated / signature-authenticated, e.g. provider
  webhooks). `scripts/verify_roles.py` fails the build when a V1 operation declares nothing or
  declares an unbound key, and lists bound keys no route uses (review G41).

## Open contract questions
- Resolved 2026-09-19 (D14): role-to-permission binding table → `contracts/permissions/roles.yaml`.
- Resolved 2026-09-19 (D14): trader self-actions → declared keys with scope `own`.
- Resolved 2026-09-17: no `tenant.impersonate` key in V1 (AUTH-16 separation-only; no impersonation endpoint exists). Enablement is V2.
- Resolved 2026-09-19 (D14): keys for staff access to sensitive data (AUD-23) → `kyc.document.read`
  and `payout.method.review`, both audit-on-access; holders restricted to
  `firm:owner` / `firm:compliance` / `firm:finance` per `roles.yaml`.
- Resolved 2026-09-19 (D14): key naming ratified — `audit.read` / `analytics.read` stay as-is;
  `payout.read_queue` keeps its name (the queue is a distinct resource; renaming would churn
  `docs/11`, `contracts/api/pay.md` and the generated OpenAPI for no semantic gain).


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
| `platform.analytics.read` | CON | Platform-wide analytics in the console: tenant roll-ups, no per-trader PII. (CON-11; the ANA-28 cross-tenant pattern — V2/V3). Kept separate from `analytics.read` so no key spans both realms (AUTH-16) — 2026-09-19 (D14) |

---

## Identity-management keys (review G16, 2026-09-19 — provisional)

The ADR-13 identity model gives the tenant a surface that the V1 registry did not
name: member administration, SSO registration and SCIM tokens. These keys are
**provisional** (V1.1/V2 surfaces per docs/02 §7), each frozen with its phase
(docs/99 §12); their proposed role bindings are recorded in
`contracts/permissions/roles.yaml` (`provisional_bindings`) so the freeze is mechanical.
`platform.identity.admin`, `platform.tenant.provision` and `platform.session.revoke`
were **promoted to the V1 table above (2026-09-19, D14)** — V1 console surfaces already
use them.

| Permission key | Module owner | Description |
|---|---|---|
| `tenant.identity.read` | AUTH | List tenant members and their roles/status (ADM team screen). |
| `tenant.identity.invite` | AUTH | Invite a staff member into the tenant (AUTH-03, V2). |
| `tenant.identity.role_change` | AUTH | Change a member's role; audited (`user.role_changed`). (AUTH-12/14) |
| `tenant.identity.remove` | AUTH | Remove a member from the tenant; deactivates the IdP user when no memberships remain. |
| `tenant.sso.read` | AUTH | View the org's SSO/IdP configuration. (AUTH-24) — group→role mapping is **out of V1** (decision D22): the surface shows the SSO config only |
| `tenant.sso.configure` | AUTH | Register/update/remove the tenant's SAML/OIDC IdP (metadata, certificates, mapping). (AUTH-24, P3) |
| `tenant.scim.manage` | AUTH | Issue/rotate the SCIM bearer token and inspect SCIM-provisioned users. (AUTH-25, P3) |
| `platform.identity.admin` | AUTH | Platform-staff identity administration: create/deactivate console users, force MFA reset (AUTH-28), break-glass. (AUTH-16, AUTH-28) |
| `platform.tenant.provision` | TEN | Run/resume the tenant provisioning saga and destroy a tenant org in the IdP. (docs/03 §3.5) |
| `platform.session.revoke` | AUTH | Revoke another identity's sessions (admin forced logout, AUTH-27). |

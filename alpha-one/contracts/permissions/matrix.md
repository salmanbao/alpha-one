# Permission Matrix (generated — do not edit by hand)

> Rendered by `scripts/verify_roles.py --write-matrix` from `contracts/permissions/roles.yaml`
> (decision D14, docs/44 §4) + the V1 table of `registry.md` + the `x-phase: V1` operations in
> `contracts/*.openapi.yaml`. The machine sources are binding; this file is a view — CI fails on
> drift (gate 15, docs/99). The consolidated specification is
> [docs/46-authorization-model.md](../../docs/46-authorization-model.md).

Version: 1 · decision: D14 · decided: 2026-09-19

## 1. Role × key matrix (V1)

Cell = the scope under which the role holds the key: **A** `all` (tenant-wide),
**O** `own` (self-scoped, ABAC own-data matcher), **P** `platform` (cross-tenant, console
realm only); `·` = denied. A digit cites the constraint in §2. Tenant roles can never hold
`P` keys and platform roles can never hold `A`/`O` keys (AUTH-16 realm separation).

| Key | Scope | trader | sup | fin | comp | risk | admin | owner | ro | p:fin | p:sup | ops | sadmin |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `account.evaluate` | all | · | · | · | · | A1 | A1 | A1 | · | · | · | · | · |
| `account.manual_override` | all | · | · | · | · | A2 | A2 | A2 | · | · | · | · | · |
| `account.read` | all | · | A | A | · | A | A | A | · | · | · | · | · |
| `account.suspend` | all | · | · | · | · | A | A | A | · | · | · | · | · |
| `analytics.read` | all | · | · | · | · | A | A | A | · | · | · | · | · |
| `audit.export` | all | · | · | · | A | · | A | A | · | · | · | · | · |
| `audit.read` | all | · | · | · | A | · | A | A | · | · | · | · | · |
| `challenge.write` | all | · | · | · | · | · | A | A | · | · | · | · | · |
| `console.session.revoke` | platform | · | · | · | · | · | · | · | · | · | · | P | P |
| `document.read` | own | O | · | · | · | · | · | · | · | · | · | · | · |
| `kyc.document.read` | all | · | · | · | A3 | · | A3 | A3 | · | · | · | · | · |
| `kyc.restrictions.write` | all | · | · | · | A | · | A | A | · | · | · | · | · |
| `kyc.review` | all | · | · | · | A | · | A | A | · | · | · | · | · |
| `payout.approve` | all | · | · | A4 | · | · | A4 | A4 | · | · | · | · | · |
| `payout.method.read` | own | O | · | · | · | · | · | · | · | · | · | · | · |
| `payout.method.review` | all | · | · | A5 | A5 | · | A5 | A5 | · | · | · | · | · |
| `payout.method.write` | own | O | · | · | · | · | · | · | · | · | · | · | · |
| `payout.policy.write` | all | · | · | A | · | · | A | A | · | · | · | · | · |
| `payout.read_queue` | all | · | · | A | · | A | A | A | · | · | · | · | · |
| `payout.record_execution` | all | · | · | A | · | · | A | A | · | · | · | · | · |
| `payout.request` | own | O | · | · | · | · | · | · | · | · | · | · | · |
| `platform.identity.admin` | platform | · | · | · | · | · | · | · | · | · | · | · | P |
| `platform.session.revoke` | platform | · | · | · | · | · | · | · | · | · | · | P | P |
| `platform.tenant.provision` | platform | · | · | · | · | · | · | · | · | · | · | · | P |
| `risk.case.create` | all | · | · | · | · | A | A | A | · | · | · | · | · |
| `risk.case.decide` | all | · | · | · | · | A6 | A6 | A6 | · | · | · | · | · |
| `risk.case.read` | all | · | · | · | · | A | A | A | · | · | · | · | · |
| `ruleset.write` | all | · | · | · | · | · | A | A | · | · | · | · | · |
| `tenant.create` | platform | · | · | · | · | · | · | · | · | · | · | · | P |
| `tenant.entitlement.change` | platform | · | · | · | · | · | · | · | · | · | · | · | P |
| `tenant.integration.read` | all | · | · | · | · | · | A | A | · | · | · | · | · |
| `tenant.integration.write` | all | · | · | · | · | · | A | A | · | · | · | · | · |
| `tenant.read` | platform | · | · | · | · | · | · | · | P | P | P | P | P |
| `tenant.suspend` | platform | · | · | · | · | · | · | · | · | · | · | · | P |
| `tenant.terminate` | platform | · | · | · | · | · | · | · | · | · | · | · | P |
| `tenant.update` | platform | · | · | · | · | · | · | · | · | · | · | · | P |
| `user.suspend` | all | · | · | · | · | · | A | A | · | · | · | · | · |
| `user.unsuspend` | all | · | · | · | · | · | A | A | · | · | · | · | · |

Role columns: `user:trader` = `trader`; `firm:support` = `sup`; `firm:finance` = `fin`; `firm:compliance` = `comp`; `firm:risk` = `risk`; `firm:admin` = `admin`; `firm:owner` = `owner`; `platform:readonly` = `ro`; `platform:finance` = `p:fin`; `platform:support` = `p:sup`; `platform:ops` = `ops`; `platform:super_admin` = `sadmin`. Inheritance is pre-expanded (every listed holder can exercise the key — closure is checked).

## 2. Key detail — what each key allows, who holds it, under which constraint

| Key | Module | Scope | Holders (effective) | Constraint |
|---|---|---|---|---|
| `account.evaluate` | EVL | all | `risk`, `admin`, `owner` | (1) step-up: mfa_verified_at within 5 min (docs/02 §3.1; EVL-36 — tenth pass, docs/50) |
| `account.manual_override` | EVL | all | `risk`, `admin`, `owner` | (2) step-up: mfa_verified_at within 5 min; risk override > $500k requires a firm:owner approval flag in context (docs/02 §3.1; EVL-20 — tenth pass, docs/50) |
| `account.read` | LCC | all | `sup`, `fin`, `risk`, `admin`, `owner` | — |
| `account.suspend` | LCC | all | `risk`, `admin`, `owner` | — |
| `analytics.read` | ANA | all | `risk`, `admin`, `owner` | — |
| `audit.export` | AUD | all | `comp`, `admin`, `owner` | — |
| `audit.read` | AUD | all | `comp`, `admin`, `owner` | — |
| `challenge.write` | EVL | all | `admin`, `owner` | — |
| `console.session.revoke` | CON | platform | `ops`, `sadmin` | V1 surface exists: CON-30 console-session revocation (POST /v1/console/sessions/{id}/revoke, self-guard console.cannot_revoke_self); AUTH-27 cross-identity forced logout is the V2 extension (docs/02 §4.1) |
| `document.read` | DOC | own | `trader` | — |
| `kyc.document.read` | KYC | all | `comp`, `admin`, `owner` | (3) access is audited (AUD-23) |
| `kyc.restrictions.write` | KYC | all | `comp`, `admin`, `owner` | — |
| `kyc.review` | KYC | all | `comp`, `admin`, `owner` | — |
| `payout.approve` | PAY | all | `fin`, `admin`, `owner` | (4) step-up: mfa_verified_at within 5 min (docs/02 §3.1) |
| `payout.method.read` | PAY | own | `trader` | — |
| `payout.method.review` | PAY | all | `fin`, `comp`, `admin`, `owner` | (5) access is audited (AUD-23) |
| `payout.method.write` | PAY | own | `trader` | — |
| `payout.policy.write` | PAY | all | `fin`, `admin`, `owner` | — |
| `payout.read_queue` | PAY | all | `fin`, `risk`, `admin`, `owner` | — |
| `payout.record_execution` | PAY | all | `fin`, `admin`, `owner` | — |
| `payout.request` | PAY | own | `trader` | — |
| `platform.identity.admin` | AUTH | platform | `sadmin` | — |
| `platform.session.revoke` | AUTH | platform | `ops`, `sadmin` | — |
| `platform.tenant.provision` | TEN | platform | `sadmin` | — |
| `risk.case.create` | RSK | all | `risk`, `admin`, `owner` | — |
| `risk.case.decide` | RSK | all | `risk`, `admin`, `owner` | (6) step-up: mfa_verified_at within 5 min (docs/02 §3.1; D70 — nineteenth pass, docs/60) |
| `risk.case.read` | RSK | all | `risk`, `admin`, `owner` | — |
| `ruleset.write` | EVL | all | `admin`, `owner` | — |
| `tenant.create` | TEN | platform | `sadmin` | — |
| `tenant.entitlement.change` | TEN | platform | `sadmin` | — |
| `tenant.integration.read` | TEN | all | `admin`, `owner` | — |
| `tenant.integration.write` | TEN | all | `admin`, `owner` | — |
| `tenant.read` | TEN | platform | `ro`, `p:fin`, `p:sup`, `ops`, `sadmin` | — |
| `tenant.suspend` | TEN | platform | `sadmin` | — |
| `tenant.terminate` | TEN | platform | `sadmin` | — |
| `tenant.update` | TEN | platform | `sadmin` | — |
| `user.suspend` | AUTH | all | `admin`, `owner` | — |
| `user.unsuspend` | AUTH | all | `admin`, `owner` | — |

Module + description are the registry's; a key with no binding is denied for every role
(fail-closed rule, roles.yaml `model.fail_closed`).

## 3. V1 route map — every V1 operation, its declared permission, and who can call it

> Review G41 / gate 13: every `x-phase: V1` operation declares a registry key or an explicit
> `self` / `none` marker. `self` = the caller acting on their own data (the own-data matcher,
> docs/46 §7 A1, still runs); `none` = unauthenticated or provider-signature-authenticated.
> Post-V1 operations annotate at their own contract freeze (docs/45 §6.2).

| Contract | Operation | Permission | Authorized roles |
|---|---|---|---|
| `02-AUTH.openapi.yaml` | `POST /v1/auth/session` | `self` | caller only (own data) |
| `02-AUTH.openapi.yaml` | `POST /v1/auth/password` | `self` | caller only (own data) |
| `02-AUTH.openapi.yaml` | `POST /v1/auth/2fa/backup-codes` | `self` | caller only (own data) |
| `02-AUTH.openapi.yaml` | `POST /v1/auth/2fa/backup-code` | `self` | caller only (own data) |
| `02-AUTH.openapi.yaml` | `GET /v1/auth/mfa/status` | `self` | caller only (own data) |
| `02-AUTH.openapi.yaml` | `POST /v1/auth/mfa/enrollment` | `self` | caller only (own data) |
| `02-AUTH.openapi.yaml` | `POST /v1/auth/logout` | `self` | caller only (own data) |
| `02-AUTH.openapi.yaml` | `POST /v1/auth/users/{user_id}/suspend` | `user.suspend` | `admin`, `owner` |
| `02-AUTH.openapi.yaml` | `POST /v1/auth/users/{user_id}/unsuspend` | `user.unsuspend` | `admin`, `owner` |
| `03-TEN.openapi.yaml` | `POST /v1/tenants` | `tenant.create` | `sadmin` |
| `03-TEN.openapi.yaml` | `GET /v1/tenants/{tenant_id}` | `tenant.read` | `ro`, `p:fin`, `p:sup`, `ops`, `sadmin` |
| `03-TEN.openapi.yaml` | `PATCH /v1/tenants/{tenant_id}` | `tenant.update` | `sadmin` |
| `03-TEN.openapi.yaml` | `POST /v1/tenants/{tenant_id}/suspend` | `tenant.suspend` | `sadmin` |
| `03-TEN.openapi.yaml` | `POST /v1/tenants/{tenant_id}/terminate` | `tenant.terminate` | `sadmin` |
| `03-TEN.openapi.yaml` | `GET /v1/tenants/subdomain-check` | `tenant.create` | `sadmin` |
| `03-TEN.openapi.yaml` | `PUT /v1/tenants/{tenant_id}/entitlements` | `tenant.entitlement.change` | `sadmin` |
| `03-TEN.openapi.yaml` | `PUT /v1/tenants/{tenant_id}/integrations` | `tenant.integration.write` | `admin`, `owner` |
| `03-TEN.openapi.yaml` | `GET /v1/tenants/{tenant_id}/integrations` | `tenant.integration.read` | `admin`, `owner` |
| `05-LED-AUD.openapi.yaml` | `GET /v1/admin/audit` | `audit.read` | `comp`, `admin`, `owner` |
| `05-LED-AUD.openapi.yaml` | `POST /v1/admin/audit/export` | `audit.export` | `comp`, `admin`, `owner` |
| `07-LCC.openapi.yaml` | `GET /v1/trader/accounts` | `self` | caller only (own data) |
| `07-LCC.openapi.yaml` | `GET /v1/trader/accounts/{account_id}` | `self` | caller only (own data) |
| `07-LCC.openapi.yaml` | `GET /v1/admin/accounts` | `account.read` | `sup`, `fin`, `risk`, `admin`, `owner` |
| `07-LCC.openapi.yaml` | `POST /v1/admin/accounts/{account_id}/suspend` | `account.suspend` | `risk`, `admin`, `owner` |
| `07-LCC.openapi.yaml` | `POST /v1/admin/accounts/{account_id}/resume` | `account.suspend` | `risk`, `admin`, `owner` |
| `09-EVL.openapi.yaml` | `POST /v1/admin/challenges` | `challenge.write` | `admin`, `owner` |
| `09-EVL.openapi.yaml` | `PATCH /v1/admin/challenges/{challenge_id}` | `challenge.write` | `admin`, `owner` |
| `09-EVL.openapi.yaml` | `POST /v1/admin/rule-sets` | `ruleset.write` | `admin`, `owner` |
| `09-EVL.openapi.yaml` | `POST /v1/admin/rule-sets/{rule_set_id}/versions` | `ruleset.write` | `admin`, `owner` |
| `09-EVL.openapi.yaml` | `POST /v1/admin/accounts/{account_id}/evaluate` | `account.evaluate` | `risk`, `admin`, `owner` |
| `09-EVL.openapi.yaml` | `POST /v1/admin/accounts/{account_id}/override` | `account.manual_override` | `risk`, `admin`, `owner` |
| `10-RSK.openapi.yaml` | `POST /v1/admin/risk/cases` | `risk.case.create` | `risk`, `admin`, `owner` |
| `11-PAY.openapi.yaml` | `POST /v1/trader/payouts` | `payout.request` | `trader` |
| `11-PAY.openapi.yaml` | `GET /v1/trader/payouts` | `self` | caller only (own data) |
| `11-PAY.openapi.yaml` | `POST /v1/trader/payout-methods` | `payout.method.write` | `trader` |
| `11-PAY.openapi.yaml` | `GET /v1/admin/payouts/queue` | `payout.read_queue` | `fin`, `risk`, `admin`, `owner` |
| `11-PAY.openapi.yaml` | `POST /v1/admin/payouts/{payout_id}/approve` | `payout.approve` | `fin`, `admin`, `owner` |
| `11-PAY.openapi.yaml` | `POST /v1/admin/payouts/{payout_id}/reject` | `payout.approve` | `fin`, `admin`, `owner` |
| `11-PAY.openapi.yaml` | `POST /v1/admin/payouts/{payout_id}/execution` | `payout.record_execution` | `fin`, `admin`, `owner` |
| `11-PAY.openapi.yaml` | `POST /v1/admin/payouts/export` | `payout.record_execution` | `fin`, `admin`, `owner` |
| `11-PAY.openapi.yaml` | `PUT /v1/admin/payout-policy` | `payout.policy.write` | `fin`, `admin`, `owner` |
| `12-CHK.openapi.yaml` | `GET /v1/trader/catalog` | `none` | public / provider signature (no user authz) |
| `12-CHK.openapi.yaml` | `POST /v1/trader/checkout/sessions` | `self` | caller only (own data) |
| `12-CHK.openapi.yaml` | `DELETE /v1/checkout/sessions/{id}` | `self` | caller only (own data) |
| `12-CHK.openapi.yaml` | `POST /v1/webhooks/payments/{provider}` | `none` | public / provider signature (no user authz) |
| `12-CHK.openapi.yaml` | `POST /v1/trader/orders/{order_id}/retry-payment` | `self` | caller only (own data) |
| `12-CHK.openapi.yaml` | `GET /v1/trader/orders/{order_id}/receipt` | `self` | caller only (own data) |
| `12-CHK.openapi.yaml` | `GET /v1/trader/orders/{order_id}/invoice` | `self` | caller only (own data) |
| `13-KYC.openapi.yaml` | `POST /v1/trader/kyc/sessions` | `self` | caller only (own data) |
| `13-KYC.openapi.yaml` | `POST /v1/webhooks/kyc/{provider}` | `none` | public / provider signature (no user authz) |
| `13-KYC.openapi.yaml` | `GET /v1/trader/kyc/status` | `self` | caller only (own data) |
| `13-KYC.openapi.yaml` | `POST /v1/trader/kyc/documents` | `self` | caller only (own data) |
| `13-KYC.openapi.yaml` | `GET /v1/admin/kyc/manual-queue` | `kyc.review` | `comp`, `admin`, `owner` |
| `13-KYC.openapi.yaml` | `POST /v1/admin/kyc/{kyc_verification_id}/decision` | `kyc.review` | `comp`, `admin`, `owner` |
| `13-KYC.openapi.yaml` | `PUT /v1/admin/kyc/restricted-countries` | `kyc.restrictions.write` | `comp`, `admin`, `owner` |
| `15-DOC.openapi.yaml` | `GET /v1/trader/documents` | `document.read` | `trader` |
| `15-DOC.openapi.yaml` | `GET /v1/trader/documents/{document_id}` | `document.read` | `trader` |
| `19-ANA.openapi.yaml` | `GET /v1/admin/analytics/kpi` | `analytics.read` | `risk`, `admin`, `owner` |
| `21-CON.openapi.yaml` | `POST /v1/console/auth/login` | `none` | public / provider signature (no user authz) |
| `21-CON.openapi.yaml` | `POST /v1/console/auth/logout` | `self` | caller only (own data) |
| `21-CON.openapi.yaml` | `POST /v1/console/sessions/{session_id}/revoke` | `console.session.revoke` | `ops`, `sadmin` |

## 4. Bound V1 keys with no V1 route (reserved — first surface named in docs/46 §4.4)

`kyc.document.read`, `payout.method.read`, `payout.method.review`, `platform.identity.admin`, `platform.session.revoke`, `platform.tenant.provision`, `risk.case.decide`, `risk.case.read`

These bindings are ratified now and enforced from the moment their route ships; until then
they are exercised by runbooks and internal surfaces only. docs/46 §4.4 names each key's
first surface. _End of generated file._

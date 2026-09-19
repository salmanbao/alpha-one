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

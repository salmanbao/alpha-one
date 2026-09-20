# 28 — Security

> Cross-cutting document. Every module doc has a §10 (Security &
> compliance); this doc is the **threat model + the platform-wide
> control stack** those sections implement. Binding sources:
> ADR-1..12 (docs/01 §3), the stack (docs/01 §2), the Tooling
> Register (docs/00 §7 — SOPS+age, ZITADEL, Casbin, Hook0,
> Cloudflare+R2, Postmark…), the 8 non-negotiables (docs/00 §8),
> and the V1 defaults (docs/00 §6 — audit append-only, manual
> payout approval, login-first checkout, MT5 broker).
>
> **Regulatory posture (binding):** Alpha One is a **fintech
> software platform**, not a bank, not an exchange, not a market
> maker, not a broker. The money is the tenant's: the trader's
> funds sit at the **MT5 broker** (the tenant's broker
> relationship, the 08 §1), the payment money moves via
> **licensed rails** (NOWPayments, Match2Pay/Interkasa, manual
> wire — the 11/12 §1), and the platform's ledger (the 05) is
> an **obligation-ledger** (the accounting of what the
> platform owes to whom), not a deposit account. The 28 doc's
> job: make that posture *true in code*, not just in ToS —
> every feature must pass the money-boundary test (who holds
> the money, who moves it, who can prove it).

## 1. Purpose & scope

Covers: the threat model (§2), the control stack by layer
(§3), data protection & PII (§4), secrets & keys (§5),
authentication & authorization (recap of 02, §6), payment &
funds security (§7), the public-API perimeter (§8, the 27
Part A), incident response & disclosure (§9), compliance
obligations by jurisdiction (§10), assurance (audit,
testing, §11), and the implementation order (§12).

**Not covered (module-owned, cited):** the per-module
control details live in each module's §10 (02 AUTH, 05
AUD, 07 LCC, 08 BRG, 09 EVL, 10 RSK, 11 PAY, 12 CHK, 13 KYC,
14 NOT, 15 DOC, 16 TD, 17 ADM, 18 SUP, 19 ANA, 20 CRM, 21
CON, 22 BIL, 23 AFF, 24 CMS/CMP, 25 MIG, 26 MOB/JRN/EDU/CHT,
27 ecosystem). This doc is the *cross-cutting* layer: what
holds **across** all of them.

## 2. Threat model

### 2.1 The assets (ranked by blast radius)

| # | Asset | Why it matters | Primary owners |
|---|---|---|---|
| A1 | **The ledger + the audit log** (05) | The system of record for every obligation; tampering = the platform's books are a lie; the 7-yr retention is the legal duty | 05, 21 (CON-13/CON-15), 06 (the restore drill) |
| A2 | **Trader PII** (identity, KYC documents, payout methods) | The most sensitive class; the KYC documents (13) are the crown jewels — a KYC leak is a regulatory + criminal event | 02 (envelope encryption), 13, 11 (method masking) |
| A3 | **The tenant's money flows** (payouts, payments, refunds) | Fraud = direct financial loss to traders/tenants; the manual-approval default (00 §6) is the control | 11, 12, 17, 18, 10 (RSK) |
| A4 | **Broker credentials** (MT5 API tokens, login/inv# — the 08 §1) | A leaked broker credential = direct account access at the broker (the platform's *own* trading-bridge accounts, the tenant's broker relationship) | 08, 02 (envelope), 06 (secrets) |
| A5 | **Tenant isolation** (the structural guarantee, 01 ADR-1) | Cross-tenant read = the platform's existential breach (two MT4/5 firms sharing the platform: a leak between them is over) | 04 (the middleware), 03 (the tenant config), 19 (read models), every module |
| A6 | **The trading state** (positions, deals, equity — 08/09) | Manipulation (spoofing the feed, injecting ticks) = wrong verdicts = wrong money decisions | 08 (ingress integrity), 09 (the verdict hash, 09 §3.4) |
| A7 | **The platform's infra** (the Hetzner box, the secrets store) | Full compromise = A1-A6 | 06, 27 Part C.1 (PLT-05) |
| A8 | **The public API / webhooks** (27 Part A) | The external perimeter; a forged webhook = a tenant's CRM acts on fake data; a leaked key = the tenant's data | 27, 04, 02 |

### 2.2 The adversary classes

- **T1 — the external attacker** (the classic): the brute
  forcer, the credential stuffer, the web-scanner, the
  DDoSer, the SQLi/SSRF/XSS probe on the public surface
  (GW, the portal, the DVP). Controls: the 02 §3.6 anomaly
  scoring, the 04 rate limits, the Cloudflare WAF (the 01
  §2, the ADR-4's posture — the GW behind Cloudflare),
  the input validation (the sqlc/typed-params discipline,
  the 01 §2 stack), the output encoding (the Next.js
  escaping, the 01 §2).
- **T2 — the insider** (the staff): the tenant staff
  (the ADM/CON users) over-reaching (reading a trader they
  shouldn't, approving a payout they shouldn't, exporting
  data they shouldn't). Controls: the 02 §3.4 (the ABAC,
  the own-data rule, the MFA on money actions, the 404-not-
  403), the 05 AUD (the critical tier on the sensitive
  actions, the 21 §3.3's CON-13/15 review), the 21 §3.2's
  two-op (the V1, the CON-15), the export logging (the 17
  §3.4's CSV export = the critical audit, the 05 §3.3),
  the break-glass (the 21 §3.5, the 2FA, the CON-15).
- **T3 — the malicious tenant/staff** (the tenant-level
  insider): a tenant operator running fraud *with* the
  platform (the fake traders, the self-funded challenges,
  the payout wash). Controls: the 10 RSK (the conduct
  detectors, the RSK-04/05/06/38, the 10 §3.3), the 12
  CHK (the capture-intent match, the 12 §3.2), the 23 AFF
  (the self-referral, the 23 §3.2), the 13 KYC (the
  reverify-at-payout, the 13 §3.3), the 11 PAY (the method-
  change cooldown, the 11 §3.3).
- **T4 — the compromised integration** (the V3, the 27):
  the tenant's developer key stolen, the partner's webhook
  endpoint forged, the sandbox abused. Controls: the 27
  §10 (the two-secrets rule, the delegation cascade, the
  IP allowlist, the conformance suite's forged-signature
  check), the 04 §5.6 (the signature, the timestamp
  tolerance).
- **T5 — the supply chain** (the deps, the images, the
  model): the compromised npm/Go crate, the tainted image,
  the malicious dep. Controls: the 06 §3.1 (the
  pinned-version discipline, the `package-lock.json` /
  `go.sum` as the manifest, the CI's integrity check (the
  hash verify, the 06's CI), the Dependabot/Renovate (the
  01 §2 GitHub Actions), the **no-`*` versions** (the CI
  check), the image scanning (the trivy-class, the 06's
  CI, the register-consistent OSS), the model's trust
  (the V3 ML, the 10 §12 / the 27 Part C.2: the sidecar,
  the no-network, the research-grade, the labeled).
- **T6 — the social engineer** (the human): the phished
  staff, the fake support call, the spoofed email.
  Controls: the 18 §3.5 (the ticket content check — the
  key-in-ticket, the phone-number-change rule (the 18's
  verification, the no-phone-change-via-chat), the
  2FA-on-money (the 02 §3.4 — the phished click is
  blocked by the MFA), the training (the 06 §3.3's
  runbook includes the social-engineering response,
  the "verify by callback" rule (the 18 §3.5), the
  no-password-over-phone (the 02's posture)).

### 2.3 The top-10 scenarios (the red-team menu, the
annual pentest scope, §11)

1. **The cross-tenant read** (T1/T2): a crafted request
   that reads tenant B's data as tenant A — the defense
   is the structural (the 04 middleware, the
   `tenant_id`-scoped queries via sqlc (the typed, the
   01 §2), the 404-not-403, the property tests (the 06's
   CI, the tenant-isolation test suite (the 04 §11's
   `isolation.test` event, the grep: the `isolation.test`
   in the docs — the CI's isolation test run), the
   CON-22's recon alert (the 21 §3.4).
2. **The payout fraud** (T3): the tenant staff self-
   approves a payout — the defense: the manual approval
   + the 2FA-on-approve (the 11 §3.5, the 02 §3.4's MFA <
   5 min) + the two-op (the 17 §3.3's V1) + the AUD
   critical (the 05 §3.3) + the RSK hold (the 10 §3.2's
   sole V1-era action, the payout hold — the flag set in V1.0, the PAY-04
   interlock biting from V1.1 — D68, docs/60) + the method-change
   cooldown (the 11 §3.3).
3. **The KYC document exfil** (T2): the staff bulk-
   exports the KYC documents — the defense: the export
   limit (the 17 §3.4's export, the 05's `AUD_
   EXPORT_LIMITED`), the document access = the critical
   audit + the MFA (the 13 §10), the R2's bucket policy
   (the per-tenant prefix, the signed URL only, the 24
   Part A §3.5 / the 13 §3.4), the no-direct-R2 (the
   app-only access, the 06's network policy).
4. **The broker credential leak** (T1): the secrets
   store compromised → the MT5 tokens → the tenant's
   broker accounts — the defense: the envelope
   encryption (the 02 §3.7, the per-tenant DEK, the age
   master key on the deploy host, the 06 §3.1's SOPS),
   the SOPS+age (the 01 §2, the register), the no-
   broker-credential-in-logs (the 08 §10, the redaction
   filter, the 06 §3.4's Loki redaction), the rotation
   (the 08's re-auth flow, the 06 §3.1's runbook).
5. **The webhook forgery** (T4): the attacker forges a
   `payout.settled` to the tenant's CRM → the CRM pays
   out — the defense: the HMAC signature (the 04 §5.6,
   the 27 §3.2), the timestamp tolerance (the ±5 min),
   the reference verifier (the 27 §3.2's SDK-03), the
   conformance suite (the 27 §2, the forged-signature
   check), the raw-body rule (the 04 §5.6).
6. **The tick injection** (T1): the attacker injects
   fake ticks → the wrong verdict → the wrong
   enforcement — the defense: the tick source is the
   MetaApi (the 08 §1, the broker-attested time, the
   ADR-12, the 01 §3), the no-external-tick-ingress (
   the structural: ticks come from the bridge's sync,
   never from an API (the 08 §3.2, the ingress
   integrity), the verdict hash (the 09 §3.4, the
   recompute — a forged tick produces a verdict that
   doesn't recompute (the property test)), the
   `evl.tick_stale` (the 09 §6).
7. **The ledger tamper** (T2/T5): the direct DB write
   → the books changed — the defense: the DB
   credentials = the app's (the 06's network: no DB
   port exposed, the PgBouncer-only, the 01 §2), the
   audit hash chain (the 05 §3.5, the LATER per 00 §6 —
   the V1: the append-only via the trigger (the 05's
   `BEFORE UPDATE` trigger = the reject, the no-update
   on the `ledger_entries` (the 05 §9), the nightly
   snapshot + the hash (the 05 §3.5, the R2, the 27
   Part A's SDK-12 export verification)), the monthly
   restore drill (the 06 §3.2, the binding duty),
   the CON-13's audit review (the 21 §3.3).
8. **The session hijack** (T1): the CSRF / the stolen
   refresh token — the defense: the PG-stored sessions +
   the Redis deny-set (the 02 §3.5), the refresh single-
   use + the reuse-detection (the 02 §3.5, the revoke-
   all + the CRITICAL), the SameSite=Lax (the 02's
   posture, the Next.js's cookie), the CSRF on the
   state-changing (the 04's middleware, the
   origin check), the MFA on the money (the 02 §3.4 —
   the hijacked session can't approve the payout
   without the MFA).
9. **The SQLi/SSRF** (T1): the classic web vuln — the
   defense: the sqlc + the typed params (the 01 §2, the
   no-string-SQL, the CI check: the raw `fmt.Sprintf`
   SQL = the build fail, the 06's lint), the output
   encoding (the Next.js), the SSRF: the no-
   user-controlled-URL-fetch (the 13's Veriff callback
   is the allowlisted host, the 04 §5.5's ingress
   allowlist, the 27's DVP-09's connector: the
   egress allowlist, the 06's network policy), the
   dependency scan (the §2.2 T5).
10. **The DDoS / the exhaustion** (T1): the volume
    attack → the platform down → the traders can't
    trade/payout — the defense: the Cloudflare (the 01
    §2, the ADR-4, the DDoS protection, the WAF),
    the 04's rate limits (the per-tenant/per-key, the
    27's SDK-14), the Redis (the non-trading path —
    the trading path is the PG's sync write (the 08
    §3.2, the no-Redis-dependency on the trading
    critical path, the ADR posture), the 06's
    capacity (the 29 doc, the 2× headroom), the 06's
    incident runbook (the 06 §3.3, the CON-15's
    ladder, the 21 §3.2).

## 3. The control stack (by layer)

### 3.1 Network (the 06 §1, the 01 §2, the ADR-4)

- **The perimeter:** Cloudflare → the Hetzner box (the
  single, the 06 §1's AX42-class) → the Docker
  Compose network (the 01 §1's 13 services). The
  exposed ports: the 443 (the Cloudflare's origin
  pull, the origin-auth (the Cloudflare's auth
  header / the IP allowlist to the Cloudflare's ranges
  (the 06's config), the no-direct-to-box (the box's
  firewall: the 22/SSH + the 443-to-Cloudflare only,
  the UFW, the 06 §1)).
- **The internal:** the Compose network (the
  service-to-service, the no-published-ports for the
  DB/Redis/outbox (the 06 §1's compose file: the
  `pg:5432`/`redis:6379` are the internal-only,
  the no-`ports:` for the data stores), the PgBouncer
  (the 01 §2, the tx mode, the 6432 internal),
  the Redis (the 6379 internal, the AOF, the 01
  §2), the Hook0 (the egress-only, the no-
  inbound-except-relay (the 04 §5.6's delivery
  is the outbound, the webhook's target is the
  tenant's endpoint (the platform's egress, the
  06's egress allowlist: the Hook0's outbound is
  the any-HTTPS (the developer's endpoint), the
  rest of the egress is the provider-allowlist
  (the MetaApi, the Veriff, the NOWPayments,
  the Match2Pay, the Interkasa, the Postmark,
  the Cloudflare/R2, the GitHub, the Sentry,
  the ipinfo — the 06's egress policy, the
  fail-closed on the unknown (the T5 defense:
  a compromised container can't phone home
  to an unknown host, the labeled posture)),
  the SSH (the 22, the key-only, the no-
  password, the MFA via the fail2ban-class (the
  06 §1), the 2-factor (the deploy host's
  MFA, the 06's ops posture)).
- **The tenant isolation is the network's
  structural part:** the single-PG + the
  `tenant_id` (the ADR-1, the 01 §3) — the
  isolation is the query layer (the §3.3),
  not the network (the no-per-tenant-
  network, the 01 ADR posture).

### 3.2 Application (the 04 chain, the 01 §2)

- **The GW chain (the 04 §3):** the tenant
  resolution (the 04 §3.4, the custom
  domain > the subdomain > the X-Tenant-Id
  (the internal) > the API key), the auth
  (the ZITADEL token / the key, the 02), the ABAC
  (the Casbin, the 02 §3.1), the rate limit
  (the 04 §3.4), the idempotency (the 04
  §3.3), the payload cap (the 10MB, the 00
  §6, the `gw.payload_too_large`), the error
  contract (the 04 §6, the 30 doc).
- **The service discipline (the 01 §2's
  Go stack):** the typed params (the sqlc,
  the no-string-SQL, the CI check), the
  no-goroutine-leak (the 06's lint, the
  golangci-lint (the 01 §2)), the context-
  everywhere (the timeout, the no-infinite-
  wait), the no-panic-recover-at-the-
  handler (the 04's error contract, the 500
  is the `sys.internal` (the 06 §6) + the
  Sentry (the 01 §2)), the idempotent
  consumer (the 04 §5.7, the at-least-once
  + the dedupe, the 01 ADR posture).
- **The FE discipline (the 01 §2's Next.js):**
  the no-PG-access (the 01 §2's binding:
  the FE never touches the PG, the API-only),
  the output encoding (the React's escaping),
  the no-PII-in-URL (the 19 §10's masked-PII
  posture, the URL is the logged surface
  (the Cloudflare's logs, the 06 §3.4) —
  the PII in the URL = the PII in the log,
  the 04's rule: the PII in the body, not
  the query string), the CSP (the Next.js's
  default, the no-inline (the 01 §2's
  build, the labeled), the no-3rd-party-
  script (the register's discipline:
  the TradingView Lightweight Charts is
  the npm bundle, not the CDN script,
  the 16 §12).

### 3.3 Data (the 05, the 01 §3, the ADR-1)

**RLS principals (review G24, docs/44 §5 — decision D16, binding).** The tenant-owned
tables (`tenant_memberships`, `auth_sessions`, `api_keys`, and every per-module tenant
table: accounts, trades, payouts, KYC documents/decisions, tenant audit rows) carry
`ENABLE`/`FORCE ROW LEVEL SECURITY` fail-closed on `current_setting('app.tenant_id', true)`.
Four DB roles are the whole exemption model: `app_rw` (request paths, RLS enforced,
context set with `SET LOCAL`), `app_rw` + four `SECURITY DEFINER` accessors in the `auth`
schema (the only way to resolve a session by id, a key by hash, a link by `idp_user_id`,
or a console session without a tenant context), `app_platform` (`BYPASSRLS`, enumerated
cross-tenant services only: relay, ledger/audit appliers, ANA updaters, `idp-sync`, CON
read models — their queries still carry explicit `tenant_id` predicates), **workers**
(decision W, docs/47 §15: per-message `app.tenant_id` from the event/job, under RLS by
default; only the manifest-named platform-wide jobs get `app_platform`), and `migrator`
(`BYPASSRLS`, discrete DDL job, never in app config). `identities`, `identity_idp_links`,
`auth_backup_codes`, `tenants`, `casbin_rule` and platform-scoped audit rows are
platform-owned and guard-only. A worker that reads cross-tenant without `app_platform`
sees zero rows — that is the point.

- **The tenant isolation (the structural):**
  every table carries the `tenant_id` (the
  32 doc's convention, the no-exception
  except the platform-level (the `tenants`,
  the `identities` (the platform-wide, the
  02 §3.1), the `audit_log` (the
  tenant-scoped + the platform-scoped,
  the 05 §9)), the sqlc's queries are
  the `tenant_id`-bound (the typed, the
  01 §2), the query without the
  `tenant_id` = the review red flag (the
  06's code review, the CI's grep-class
  check on the new sqlc queries (the
  labeled heuristic, the review + the CI),
  the 404-not-403 (the 04 §6, the no-
  oracle, the 02 §3.4), the cross-
  tenant access = the security event (
  the CON-22 (the 21 §3.4), the alert,
  the 10's RSK input (the 10 §3.3)),
  the read models (the 19 §3.1) are the
  tenant-scoped (the `*_ro` tables, the
  19 §9), the property test (the 06's CI:
  the `isolation.test` — the per-tenant
  data query as another tenant = the 0
  rows (the test suite, the 04 §11),
  the monthly drill (the 06 §3.2's
  restore includes the isolation
  verify (the post-restore query:
  tenant A sees only A, the 06 §3.2's
  runbook)).
- **The PII protection (the 02 §3.7, the
  13, the 11):** the envelope encryption
  (the per-tenant DEK, the master = the
  age key on the deploy host, the 01 §2's
  SOPS+age), the fields encrypted (the
  payout method's detail (the 11 §9's
  `method_encrypted`, the KYC's document
  (the 13's R2 + the encrypted ref (the
  13 §3.4), the personal info (the
  phone, the DOB — the `pii_*` columns,
  the 02's envelope), the no-PII-in-
  logs (the 06 §3.4's redaction filter
  (the Loki's pipeline, the pattern:
  the email/phone/wallet/card, the
  06's config), the no-PII-in-URL (the
  §3.2), the masked display (the 19 §10,
  the 11 §10, the 13 §7 — the `***`
  mask, the 4-char tail), the retention
  (the 05 §3.5's 7-yr for the financial,
  the 13's KYC retention (the legal,
  the 13 §3.5), the 25 §3.7's
  anonymization (the migration's
  synthetic, the 06 §2's staging),
  the deletion (the 25's GDPR-class:
  the trader's data-delete request (
  the 18 §3.1's ticket, the 02's
  identity deactivation (the 02 §3.2's
  state), the KYC document delete (the
  13's R2 delete + the ref tombstone,
  the 13 §3.5), the 30-day completion
  (the 18's SLA, the 18 §3.3), the
  audit retained (the 05's 7-yr, the
  no-delete (the 05 §1: the audit is
  the append-only, the deletion leaves
  the audit trail, the labeled
  posture: the data is gone, the
  "was deleted" is the record)).

### 3.4 The audit (the 05, the 21 §3.3)

The audit is the *last line* (the 05 §1's
posture: detection, not prevention):
the critical tier (the 05 §3.3: the
money, the access, the config, the
enforcement), the fail-closed (the 05
§3.3: the audit-write-fail = the action-
fail, the no-silent-skip), the 7-yr (the
05 §3.5, the financial-adjacent),
the append-only (the 05 §9's trigger,
the no-update/delete on the
`audit_log`), the hash chain (the LATER
per 00 §6 — the V1: the append-only +
the nightly snapshot (the 05 §3.5),
the V2+: the hash chain (the 05's
roadmap), the review (the 21 §3.3's
CON-13/15, the weekly, the 2-op (the
21 §3.5), the export (the 21 §3.4's
CON-13, the critical, the 7-yr),
the CON-22's recon (the 21 §3.4, the
cross-tenant probe, the alert),
the 32 doc's `audit_log` DDL (the
05 §9).

### 3.5 The crypto (the 02 §3.7, the 01 §2)

- **The passwords:** Argon2id (ZITADEL's
  default parameters, consistent with the
  64MB/3/4 target, the 02 §3.2, ADR-13);
  the breach check (HIBP) is ours.
- **The envelope:** the AES-256-GCM (the
  per-tenant DEK, the 02 §3.7), the
  master = the age (the 06 §3.1's SOPS,
  the deploy host, the no-cloud-KMS
  (the 01 ADR posture, the register's
  "consider-later: Infisical (the V2)" —
  the V1 is the age on the host, the
  labeled)).
- **The HMAC:** the SHA-256 (the webhook
  signature, the 04 §5.6, the 27 §3.2;
  the audit hash chain (the LATER, the
  05), the idempotency key (the 04
  §3.3, the no-HMAC (the key is the
  client's, the server stores the
  sha256 (the 02 §3.5's API key
  storage)).
- **The TLS:** the 1.2+ (the Cloudflare's
  origin, the 06's config), the no-
  plaintext-internal (the Compose's
  network is the trusted, the
  labeled: the internal HTTP is the
  design (the 01 §1's single-box, the
  ADR posture), the box's network is
  the trust boundary (the §3.1),
  the no-self-signed-certs-in-
  prod (the 06's config, the
  Cloudflare's origin cert (the
  06 §1)).

## 4. PII & data classification

| Class | Examples | Storage | Access | Retention |
|---|---|---|---|---|
| **S1 — the crown** (the KYC, the payout method) | The KYC documents (the 13), the wallet string / the IBAN (the 11) | The R2 (the per-tenant prefix, the 13 §3.4) + the encrypted ref (the envelope, the 02 §3.7); the `method_encrypted` (the 11 §9) | The critical audit + the MFA (the 13 §10, the 11 §10), the staff with the `firm:compliance` / the `firm:finance` (the 02 §3.2's role), the no-export-bulk (the 17 §3.4's export limit, the 05's `aud.export_limited`) | The KYC: the legal (the 13 §3.5, the 7-yr class); the method: the account-life + the 7-yr (the 11 §3.5) |
| **S2 — the personal** (the identity, the contact) | The email, the phone, the DOB, the name | The PG (the envelope-encrypted `pii_*`, the 02 §3.7) | The own-data (the 02 §3.4's ABAC), the staff with the role (the 02 §3.2), the masked display (the 19 §10) | The identity-life + the 7-yr (the financial-adjacent, the 05's class); the deletion (the §3.3's GDPR-class, the 30-day, the 18's SLA) |
| **S3 — the financial** (the ledger, the audit, the contracts) | The `ledger_entries` (the 05), the `audit_log` (the 05), the `tenant_contracts` (the 22 §9), the payouts (the 11) | The PG (the 05 §9, the 11 §9, the 22 §9) | The `firm:finance` (the 02 §3.2), the critical audit, the 7-yr (the 05 §3.5) | **The 7-yr (the binding, the 00 §6, the 05 §3.5)** |
| **S4 — the operational** (the tickets, the CRM, the CMS) | The `tickets` (the 18), the `crm_records` (the 20), the CMS content (the 24 Part A) | The PG (the 18 §9, the 20 §9, the 24 §9) | The tenant-scoped, the role-scoped (the 02 §3.2), the 2-yr (the 18 §3.5's ticket retention) | The 2-yr (the 18), the CMS: the content-life (the 24 Part A's version, the no-auto-delete) |
| **S5 — the public** (the competition, the public profile, the changelog) | The leaderboard (the 24 Part B), the public performance (the 27 Part B's TRD-02), the changelog (the 27 Part A) | The PG (the 24 §9, the 19 §3.1) | The public (the no-auth, the 19 §10's masked-PII: the handle, the masked name, the no-S2/S1 (the structural)), the as_of-labeled (the 24 Part B, the ANA-14) | The competition-life + the 12-mo (the 24 Part B's retention, the leaderboard's honesty) |
| **S6 — the synthetic** (the staging, the sandbox, the migration dry-run) | The staging data (the 06 §2), the sandbox tenant (the 27 Part A), the migration's anonymized copy (the 25 §3.7) | The staging PG / the R2 (the staging prefix) | The staff (the 06 §2's staging access), the no-prod-PII (the 06 §2's binding: the synthetic-only, the 25 §3.7's anonymization) | The 30-day (the sandbox's expiry, the 27 §5), the staging: the 90-day (the 06 §2's hygiene) |

| **S2b — the auth artifacts** (the sessions, the IPs, the denies) | The `auth_sessions` (the 02 §9: the IP, the user agent, the geo, the `mfa_verified_at`), the Redis deny-set (the 02 §3.2), the revoked/expired rows | The Postgres (the 02 §9) + the Redis (the TTL) | The own-data (the 02 §3.4's ABAC), the `platform:ops` (the revoke), the never-exported in bulk (the 17 §3.4) | The active: the session-life; the IP/UA/geo columns: **scrubbed at 90 days** (the row keeps the identity/tenant/reason as the audit-adjacent record); the deny-set: the 24-h TTL (the 02 §3.2); the backup codes: purged on use + on offboarding; the `identity_emails` retired rows: the identity-life (needed for the re-link, the 02 §3.1) |

## 5. Secrets & keys (the 06 §3.1, the 01 §2, the ADR posture)

- **The store:** the SOPS+age (the 01 §2,
  the register; the no-Vault (the 00
  §7's forbidden), the no-cloud-KMS
  (the ADR posture, the 28 §3.5's
  labeled)). The secrets file (the
  `secrets.enc`, the 06 §3.1, the
  age-encrypted, the SOPS-managed,
  the git-committed-encrypted (the
  06's CI: the decrypt-at-deploy,
  the no-plaintext-in-git (the CI
  check: the `gitleaks`-class (the
  01 §2's GitHub Actions, the register-
  consistent OSS), the secret-in-
  commit = the build fail + the incident
  (the 06 §3.3's runbook, the secret-
  rotation (the §5 below))).
- **The classes:** the DB/Redis's
  credentials (the 06 §1's compose,
  the per-service, the no-shared),
  the broker credentials (the 08 §1,
  the envelope (the §3.3), the
  per-tenant), the provider API keys
  (the Veriff, the NOWPayments,
  the Match2Pay, the Interkasa,
  the Postmark, the MetaApi,
  the ipinfo — the 00 §7's register,
  the SOPS-managed, the per-provider),
  the R2's key (the 24 Part A §3.5,
  the per-tenant prefix, the no-
  long-lived (the signed URL, the
  TTL (the 24 Part A's 15-min, the
  13's 5-min)), the session's secret
  (the 02 §3.2, the ZITADEL application
  and client secrets, the SOPS),
  **the IdP class** (the 02 §3.3's
  register: the `ZITADEL_MASTERKEY`
  (the key-ceremony, the never-rotated),
  the provisioning machine-user key
  (the 90-d), the per-tenant SCIM
  bearer tokens (the 90-d, the stored
  hashed), the Actions-v2 target
  signing key (the 180-d), the
  IdP's own PG DSN (the separate
  database, the §3.3's store —
  dump and master key stored
  **separately** so a stolen dump
  alone decrypts nothing)), the webhook's
  secret (the 27 §3.2's two-secrets,
  the per-key), the Casbin policy
  (the 02 §3.1, the no-secret (the
  policy is the config, the
  version-controlled, the 06's
  config-repo), the Flipt's (the 01
  §2, the no-secret), the Sentry's
  DSN (the 01 §2, the SOPS), the
  age's master key (the deploy host,
  the no-cloud (the §3.5), the
  offline-backup (the 06 §3.2's DR:
  the age key's backup = the offline,
  the 2-person (the 21 §3.5's two-op
  class, the 06's ops posture —
  the age key loss = the full
  lockout (the envelope (the §3.3) +
  the SOPS (the §5) — the 06 §3.2's
  DR includes the age key's restore
  (the offline backup, the tested,
  the 06 §3.2's monthly drill's
  scope (the 06 §3.2: the restore
  = the DB + the secrets + the
  config, the triple-restore,
  the labeled duty))).
- **The rotation:** the DB/Redis (the
  90-day (the 06's ops calendar,
  the 21's CON-adjacent (the 21
  §3.4)), the broker (the on-leak +
  the 180-day (the 08's runbook,
  the 06's calendar), the provider
  (the on-leak + the 180-day (the
  06's calendar, the per-provider
  rotation note (the 00 §7's
  register: the Veriff's / the
  NOWPayments's rotation
  procedure (the provider's doc,
  the 08/11/12/13 §15's
  integration note))), the session
  secret (the on-leak (the immediate,
  the 06 §3.3's incident), the R2
  (the on-leak + the 180-day),
  the webhook secret (the per-key,
  the 27 §3.2, the 24-h dual-live (
  the 02 §3.5's rotation pattern),
  the API key (the 27 §3.3, the 24-h
  dual-live).
- **The leak response (the 06 §3.3's
  runbook, the 15-min):** the revoke
  (the immediate, the deny-set (the
  02 §3.5) / the rotation (the §5),
  the scope (the which-secret, the
  the blast radius (the §2.1's
  asset mapping), the notify (the
  the tenant (the 14's NOT, the 06's
  comms), the CON-15 (the 21 §3.2's
  ladder), the post-mortem (the 06
  §3.3, the blameless), the audit
  (the 05's critical, the 7-yr).

## 6. AuthN & AuthZ (recap — full design: 02)

- **The foundation:** ZITADEL self-hosted
  (ADR-13, the 01 §2, the register): hosted
  login per tenant organization, OIDC tokens
  verified by the api over JWKS (audience per
  realm), sessions terminated through ZITADEL
  APIs, MFA (TOTP) with our backup codes and
  the staff `amr` rule (the 02 §3.2),
  the 2FA-on-money (the 02 §3.1, the
  the < 5-min TTL (the 02 §3.1))),
  the password policy per org (Argon2id),
  the refresh (the single-use, the
  reuse-detection, the 02 §3.2),
  the anomaly (the 02 §10.5, the score,
  the block/MFA), the API key (the
  02 §3.4, the sha256, the scope,
  the 600/min), the HIBP check (ours
  — **with the V1 deviation**:
  enforced on our own change/registration
  paths only, because ZITADEL owns
  hosted-login password set/reset and
  exposes no pre-change hook, the
  02 §3.2, the docs/42 §3.3's
  accepted gap with the owner).
- **The authorization:** Casbin
  embedded (ADR-14, the 01 §2, the register;
  RBAC with domains, `dom` = tenant id)
  behind the `authorizer.Check` (the 02
  §3.1's spike outcome)), the ABAC
  (the 02 §3.4: the own-data,
  the money-MFA, the risk.override's
  owner-flag, the geo-restriction),
  the role (the 02 §3.2:
  the `platform:*`, the
  `firm:owner⊃admin⊃{risk,compliance,
  support,finance}`, the
  `user:trader`, the `firm:developer`
  (the 27 §3.3)), the 404-not-403
  (the 04 §6, the §3.3), the
  impersonation (the 21 §3.4's CON-18,
  the deny-list, the 2FA, the audit).
- **The V3 SSO:** the Authentik (the
  00 §7's consider-later, the V3,
  the SAML/OIDC, the 02 §3.8's
  roadmap, the tenant's SSO (the
  TEN-adjacent, the 03's config),
  the no-V1 (the 00 §6's V1 default:
  the email+password+MFA, the
  labeled).

## 7. Payment & funds security (the 11, the 12, the 00 §6)

- **The money-boundary test (the §1's
  posture):** the trader's money =
  the broker's (the 08 §1, the MT5,
  the tenant's relationship),
  the payment money = the rail's (the
  NOWPayments / the Match2Pay /
  the Interkasa / the wire, the 11/
  12 §1), the platform's books =
  the obligation (the 05 §1, the
  "we owe the trader X" — the
  accounting, not the custody).
  **The platform never holds the
  trader's cash** (the structural:
  the no-wallet (the 05 §1's
  posture, the no-balance-holding),
  the no-escrow (the 12 §1's
  posture, the capture = the
  rail's, the 12 §3.2), the no-
  lending (the no-interest (the
  22 §1's posture, the BIL is
  the subscription, not the
  credit)).
- **The payout path (the 11 §3):** the
  eligibility (the 11 §3.1, the
  16-check, the frozen snapshot (
  the 11 §3.2, the no-live-recompute),
  the HWM (the 11 §3.2, the no-
  double-payout (the property test,
  the 11 §11)), the approval (the
  manual (the 00 §6), the 2FA (the
  02 §3.4), the two-op (the 17 §3.3's
  V1)), the method-change cooldown
  (the 11 §3.3, the 72-h, the
  `pay.method_changed_recently`),
  the RSK hold (the 10 §3.2, the
  sole V1 action), the execution (
  the NOWPayments's / the manual-
  wire, the 11 §3.4, the reconciliation
  (the 11 §3.5, the provider-events,
  the 04 §5.5's pattern), the
  failed → the manual (the 11 §3.5,
  the 18's ticket, the no-auto-
  retry-on-fund (the 11 §3.5's
  posture: the retry = the re-
  approval, the 2FA, the no-
  silent-retry)).
- **The purchase path (the 12 §3):**
  the checkout (the 12 §3.2, the
  login-first (the 00 §6), the frozen
  price (the 12 §3.2, the no-price-
  change-mid-checkout (the 12's
  integrity)), the intent → the
  capture (the 12 §3.2, the
  Match2Pay/Interkasa/NOWPayments/
  the wire, the 12 §1), the capture-
  match (the 12 §3.2, the `CHK_
  CAPTURE_MISMATCH`, the 24-h,
  the manual-review (the 17's queue)),
  the refund (the 12 §3.3, the
  binding machine (the 12 §5),
  the auto-refund (the 12 §3.3,
  the no-funds-without-approval
  (the 12's posture: the auto-
  refund is the config (the tenant's
  choice, the 12 §3.3), the 2FA
  (the 02 §3.4), the audit (the 05's
  critical)), the STRIPE rejected
  (the 00 §6, the 12 §1, the PK/IN
  rails, the register).
- **The reserve (the 11 §3.4, the
  22 §3.4):** the reserve ≥
  the obligation (the nightly
  recon, the 11 §3.5, the 05's
  `ledger.reconciliation_exception`
  (the 05's event, the CON-13 (the
  21 §3.3)), the BIL's pass-through
  (the 22 §3.4, the tenant's cost
  transparency, the 27 Part C.1's
  PLT-03).

## 8. The public-API perimeter (the 27 Part A, the 04, the 02)

- **The key (the 02 §3.5, the 27
  §3.3):** the `sk_live_t_…` /
  the `sk_test_…` (the environment),
  the sha256 (the storage, the no-
  plaintext), the scope (the per-
  area, the widen-2FA (the 27 §5),
  the narrow-instant), the rotation
  (the 24-h dual-live), the revoke
  (the immediate, the deny-set),
  the IP allowlist (the optional,
  the 27 §3.3), the delegation (
  the 27 §3.3, the one-level,
  the parent-revoke-cascade).
- **The webhook (the 04 §5.6, the
  27 §3.2):** the HMAC-SHA256 (the
  ts + the raw-body), the ±5-min
  (the replay window), the two-
  secrets (the API key ≠ the
  webhook secret, the 27 §3.2),
  the conformance (the 27 §2,
  the forged-signature check (
  the §2.3 #5), the DLQ (the 04
  §5.6, the 27 §5's state), the
  replay (the 27 §3.2, the
  sandbox-full / the production-
  tenant-admin).
- **The rate limit (the 04 §3.4,
  the 27's SDK-14):** the per-key
  tier, the 600/min base, the
  write-slow (the 60/min, the 27
  §3.1), the 429 + the `Retry-
  After` (the 27 §6), the burst
  (the 10× read, the 27 §3.1).
- **The tenant scope (the 04 §3.4,
  the 27 §8):** the key → the
  tenant (the 04 §3.4's chain),
  the other-tenant = the 404 (the
  §3.3, the no-oracle), the recon-
  alert (the 21's CON-22, the 27
  §10, the 10's RSK input),
  the PII rule (the 27 §8: the
  ref, the masked, the no-wallet-
  string (the 11 §10), the no-KYC-
  doc (the 13 §10)).
- **The sandbox (the 27 §3.4):**
  the staging (the 06 §2, the
  synthetic-only), the injection (
  the sandbox-only, the 404-on-
  live, the 27 §1), the 30-day (
  the expiry, the 27 §5), the
  mock (the 27 §3.4, the Prism,
  the no-network).

## 9. Incident response & disclosure (the 06 §3.3, the 21 §3.2)

- **The ladder (the 21 §3.2, the
  06 §3.3):** the P0 (the money /
  the PII / the platform-down) →
  the immediate (the CON-15 (the 21
  §3.2), the owner-on-call (the
  06's rota, the 06 §3.3), the
  status (the Uptime Kuma (the 06
  §12, the 21 §12), the DVP-07 (
  the 27 Part A), the tenant-notice
  (the 14's NOT, the 14 §3.4),
  the trader-notice (the 14),
  the 15-min ack (the 06 §3.3's
  SLA), the 1-h status (the 06
  §3.3), the resolve, the post-
  mortem (the 06 §3.3, the
  blameless, the 48-h, the CON-
  15's review (the 21 §3.2)),
  the P1 (the degraded, the
  30-min ack), the P2 (the minor,
  the 4-h ack), the P3 (the log,
  the 24-h).
- **The specific (the §2.3's top-
  10, the runbook per scenario):**
  the key-compromise (the 27 §10,
  the 15-min), the webhook-forgery
  (the 27 §10, the 30-min), the
  broker-credential (the §5,
  the 15-min), the ledger-tamper
  (the §3.4, the immediate +
  the forensics (the 05's
  snapshot (the 05 §3.5),
  the no-destructive-
  response (the forensics-
  first, the 06 §3.3's posture)),
  the DDoS (the Cloudflare (the
  01 §2), the 06 §3.3's runbook),
  the social-engineering (the
  §2.2 T6, the 18 §3.5's
  callback-verify).
- **The disclosure (the 27 §3.5,
  the 14's NOT, the 21's CON):**
  the security-advisory (the
  private-first (the tenant,
  the 48-h), the public-after-
  the-fix (the changelog (the 27
  §3.5), the 14's NOT (the
  tenant-admin), the regulatory
  (the §10, the jurisdiction-
  specific), the no-silence (the
  00 §8's non-negotiable class,
  the "the incident was handled"
  is the comms, the 21 §3.2's
  posture).

## 10. Compliance by jurisdiction

The anchor: **PK** (the FunderBlu,
the 00 §3) + **IN** (the Match2Pay/
Interkasa's rail, the 12 §1) + the
tenant's jurisdiction (the TEN's
config, the 03 §3.1's `geo_
restriction` (the 02 §3.4)):

- **PK (the SECP / the State Bank's
  posture):** the platform is the
  software (the no-bank-license
  (the §1's posture), the no-
  exchange (the 27 Part B's
  execution-boundary, the 10 §1's
  no-market-maker), the crypto-
  payout (the NOWPayments, the 11
  §1, the SBF's crypto-posture
  (the tenant's legal's
  responsibility (the 00 §3's
  FunderBlu-stakeholder, the 28
  doc's labeled: the platform
  provides the rail, the tenant
  bears the regulatory
  judgment, the ToS line (the
  24 Part A's legal block, the
  CMS-08), the AML (the KYC (the
  13, the Veriff (the 00 §7's
  SIGNED), the CFT's screening
  (the 13 §3.3, the tenant's
  config), the records (the 05's
  7-yr (the 00 §6), the data-
  localization (the PK's data-
  posture (the 01 §1's single-
  Hetzner (the 06 §1) — the
  PK-data-residency question =
  the FunderBlu's legal's
  decision (the 00 §3, the 27
  Part C.1's PLT-01's multi-
  region (the V3's option,
  the jurisdiction's data-
  center, the 29 doc's path),
  the V1: the Hetzner's geo (
  the 06 §1) + the ToS (the 24
  Part A), the labeled: the
  platform's V1 is the single-
  region, the tenant's
  jurisdiction's requirement
  is the V3's PLT-01 trigger
  (the §2.3's #10 / the 27
  Part C.1's PLT-01)).
- **IN (the rail's jurisdiction):**
  the Match2Pay / the Interkasa (
  the 12 §1, the register),
  the UDIAC / the RBI's posture
  (the tenant's legal, the
  12 §15's integration note,
  the no-platform-judgment (
  the §1's posture, the rail is
  the licensed (the 12 §1),
  the platform is the
  interface (the 12 §1)).
- **The EU (the GDPR-class, the
  future-tenant's posture):**
  the DPA (the 24 Part A's
  legal block, the CMS-08,
  the tenant-legal (the 00
  §3)), the deletion (the §3.3's
  GDPR-class, the 30-day,
  the 18's SLA), the data-
  subject-right (the 18 §3.1's
  ticket, the 02's
  deactivation, the 13's
  R2-delete), the breach-
  notification (the 72-h (the
  GDPR's, the §9's comms,
  the 14's NOT, the CON-15 (
  the 21 §3.2)), the transfer
  (the §10's PK-posture,
  the SCC-class (the tenant-
  legal, the 24 Part A's
  legal block)).
- **The general (the tenant's
  jurisdiction, the TEN's config):**
  the geo-restriction (the 02
  §3.4, the 03 §3.1), the terms
  (the 24 Part A's legal,
  the version-cited (the 24
  Part A §3.4), the 2FA (the
  legal-change (the 17 §3.3's
  class, the 21's CON-32 (
  the 21 §3.5))), the audit
  (the 05's 7-yr, the 00 §6),
  the records (the 05, the 22's
  7-yr (the 22 §14)).

## 11. Assurance (the testing, the audit, the drill)

- **The property tests (the 06's CI,
  the 01 §2):** the tenant-isolation
  (the §3.3, the 04 §11's
  `isolation.test`, the per-
  tenant-query-as-another-tenant
  = the 0-rows), the HWM (the
  11 §11, the no-double-
  payout), the verdict-recompute
  (the 09 §3.4, the hash,
  the re-run = the same),
  the ref-indirection (the 27
  §8, the no-raw-ULID-in-
  public-API), the paper-
  badge (the 27 Part B §5,
  the no-funded-badge-on-
  paper), the answer-key (
  the 26 Part D §3, the EDU's
  server-side), the JRN-privacy
  (the 26 Part C, the no-cross-
  trader), the ULID (the 01 §2's
  char-25 guard, the 02 §3.5's
  id).
- **The contract tests (the 06's
  CI, the 04 §6):** the error-code
  registry (the 30 doc, the
  04 §6's CI gate), the OpenAPI
  (the 27 Part A, the one-
  contract, the public-route-
  without-docs = the fail,
  the breaking-change = the
  fail), the webhook-schema
  (the 04 §5.6, the 27's SDK-02,
  the JSON-Schema (the
  contracts/events/, the
  README's pack), the event-
  catalog (the 31 doc, the
  producer/consumer,
  the no-unknown-event (the
  04 §5.7's consumer's
  schema-check, the `EVT_
  WEBHOOK_SCHEMA_INVALID` (
  the 04 §6))).
- **The security tests (the
  annual, the 06's calendar,
  the 21's CON-adjacent (
  the 21 §3.4)):** the pentest
  (the §2.3's top-10, the
  external, the annual (the
  06's ops calendar), the
  scope: the GW + the portal
  + the DVP + the public-API
  + the bridge (the 08) +
  the R2 (the signed URL)
  + the webhook (the
  signature), the SAST
  (the golangci-lint (the 01
  §2) + the ESLint (the 01
  §2) + the `gitleaks` (the
  §5) + the dep-scan
  (the GitHub's Dependabot
  (the 01 §2), the weekly (
  the 06's CI), the DAST (
  the OWASP ZAP-class (the
  01 §2's GitHub Actions,
  the register-consistent),
  the monthly (the 06's
  calendar), the red-team
  (the V2+ (the 06's
  roadmap, the §2.2's
  adversary-class, the
  annual (the 06's
  calendar), the CON-15's
  review (the 21 §3.2)).
- **The drill (the 06 §3.2, the
  binding duty):** the monthly
  restore (the RPO ≤ 5-min
  (the WAL), the RTO ≤ 2-h
  (the 00 §6's class, the 06
  §3.2), the scope: the DB +
  the secrets + the config
  (the §5's triple-restore),
  the isolation-verify (the
  §3.3, the post-restore
  query), the age-key
  (the §5, the offline
  backup), the quarterly
  game-day (the 27 Part C.1's
  PLT-05, the CON-15's full
  walk (the 21 §3.2), the
  cross-team (the FunderBlu's
  ops (the 25 §3.6's
  concierge), the incident-
  table-top (the 06 §3.3,
  the §2.3's scenario,
  the 48-h (the 06's
  calendar)).
- **The audit-review (the 21
  §3.3, the CON-13/15):**
  the weekly (the 21 §3.3,
  the critical-tier (the 05
  §3.3), the 2-op (the 21
  §3.5), the export (the
  21 §3.4, the 7-yr,
  the critical (the 05
  §3.3)), the quarterly (
  the 21 §3.4, the full
  (the all-tier, the 21's
  CON-13), the annual
  (the 21 §3.4, the
  compliance (the §10),
  the external (the
  pentest's finding,
  the 06's calendar)).

## 12. Implementation (the security is built
with the modules — the order, the 99 doc's
dependency)

| Phase | The security work | Owner | Depends |
|---|---|---|---|
| **P0 (the infra, the 06):** the SOPS+age (the secrets, the §5), the Cloudflare (the origin-auth, the §3.1), the UFW (the §3.1), the compose (the no-published-data-port, the §3.1), the egress-allowlist (the §3.1, the T5), the CI (the `gitleaks`, the dep-scan, the SAST, the §11), the backup (the WAL + the daily, the 06 §3.2), the restore-drill (the monthly, the 06 §3.2, the §5's triple) | DevOps | the 01 §1's compose, the 01 §2's stack |
| **P1 (the AUTH, the 02):** ZITADEL deploy + org-per-tenant provisioning (ADR-13), the hosted-login hand-off + JWKS verification (the §6), the MFA (the TOTP + our backup codes, the §6), the refresh-reuse (the §6), the anomaly (the §6, the 02 §10.5), the envelope (the per-tenant DEK, the §3.3, the 02 §10.2), the API-key (the sha256, the §6, the 02 §3.4), Casbin embedded (the ABAC, the §6, the 02 §3.1) | BE-1 | P0 |
| **P2 (the GW + the EVT, the 04):** the chain (the tenant-resolution, the §3.2, the 04 §3), the rate-limit (the §3.2, the 04 §3.4), the idempotency (the §3.2, the 04 §3.3), the error-contract (the §3.2, the 04 §6, the 30 doc), the webhook (the HMAC, the §8, the 04 §5.6), the DLQ (the §8, the 04 §5.6), the isolation-test (the §3.3, the 04 §11) | BE-1 | P1 |
| **P3 (the AUD + the LED, the 05):** the audit (the fail-closed, the §3.4, the 05 §3.3), the append-only (the trigger, the 05 §9), the critical-tier (the §3.4, the 05 §3.3), the 7-yr (the §3.4, the 05 §3.5), the snapshot + the hash (the §3.4, the 05 §3.5), the reconciliation (the §7, the 11 §3.5) | BE-1 | P2 |
| **P4 (the money, the 11/12/13/17):** the payout (the 16-check, the §7, the 11 §3.1), the HWM (the §7, the 11 §3.2), the 2FA-on-approve (the §7, the 02 §3.4), the method-cooldown (the §7, the 11 §3.3), the checkout (the frozen-price, the §7, the 12 §3.2), the capture-match (the §7, the 12 §3.2), the refund-machine (the §7, the 12 §3.3), the KYC (the envelope, the §3.3, the 13), the reverify (the §3.3, the 13 §3.3), the ADM (the two-op, the §3.4, the 17 §3.3), the export-limit (the §3.4, the 17 §3.4) | BE-1 + BE-2 | P3 |
| **P5 (the ops, the 21/06):** the CON (the control-ladder, the §9, the 21 §3.2), the audit-review (the §11, the 21 §3.3), the break-glass (the §3.4, the 21 §3.5), the incident-runbook (the §9, the 06 §3.3, the §2.3's top-10), the Uptime Kuma (the §9, the 06 §12), the status-page (the §9, the 27 Part A's DVP-07, the V3) | DevOps + BE-2 | P4 |
| **P6 (the V2/V3 perimeter, the 27):** the public-API (the key-extension, the §8, the 27 §3.3), the webhook-conformance (the §8, the 27 §2), the sandbox (the §8, the 27 §3.4), the delegation (the §8, the 27 §3.3), the DVP (the §8, the 27 Part A), the TRD (the execution-boundary, the 27 Part B §1, the §2.3's #6), the PLT (the multi-region's framework, the 27 Part C.1's PLT-01, the §10's PK-posture) | BE-1 + DevOps | P5, the V2 stable |
| **The continuous:** the monthly restore (the 06 §3.2, the binding, the §11), the weekly audit-review (the 21 §3.3, the §11), the annual pentest (the §11, the 06's calendar), the quarterly game-day (the 27 Part C.1's PLT-05, the §11), the dep-scan (the weekly, the 06's CI), the secret-rotation (the 90/180-day, the §5, the 06's calendar) | DevOps + the team | P5 |

## 13. The open items (the Phase-1 confirmations,
the 00 §4's D-class)

- **The PK data-residency** (the §10,
  the 27 Part C.1's PLT-01): the
  FunderBlu's legal's call (the
  00 §3, the V3's trigger,
  the §10's labeled posture).
- **The audit hash-chain timing**
  (the 00 §6's "LATER"): the V1 =
  the append-only + the snapshot
  (the 05 §3.5), the V2+ = the
  hash-chain (the 05's roadmap,
  the 21's CON-13's input,
  the 99 doc's V2 item).
- **The SSO (the V3, the 02 §3.8,
  the Authentik (the 00 §7's
  consider-later)):** the
  FunderBlu's SSO need (the
  00 §4, the V3's scope,
  the 27 Part C's V3-late).
- **The e-sign (the DOC-12, the
  Documenso (the 00 §7's consider-
  later, the DocuSign rejected)):**
  the contract-signing need (
  the 15 §1, the V3's scope,
  the 24 Part A's legal-block
  (the CMS-08), the 22's
  contract (the 22 §9)).
- **The compliance's scope-
  expansion** (the 14 proposals
  pending (the 00 §6, the V2/V3),
  the 10 §1, the 28 §10's
  jurisdiction's posture,
  the 99 doc's V2/V3 item).

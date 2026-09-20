# 47 — The Multi-Tenancy Model (consolidated specification)

> Seventh pass on the identity/tenancy stack, 2026-09-19, after `docs/46`. The fifth pass
> closed the authentication gaps and the sixth consolidated authorization; this pass does
> the same for **multi-tenancy**: what a tenant *is* on this platform, how it is isolated,
> how it is born, gated, paused and buried — in one navigable place. It changes **no
> decision**: ADR-1/ADR-2, D3/D16, D19, G7/G8/G19 and the docs/42/44 findings stand. What
> it adds is the machine-readable state matrix and six fixes the audit surfaced
> (findings M1–M6, §14).
>
> **Binding sources (this doc never overrides them):** [03 — TEN](03-tenant-management.md)
> (the module: entity, saga, settings, secrets), [02 — AUTH](02-identity-access.md) §3.1/§3.4
> (identity plane + resolution order), [04 — GW](04-gateway-events.md) §3.1 (chain order),
> [44 — fourth pass](44-auth-multitenancy-review.md) §5 (RLS exemption model, D16),
> [28 — Security](28-security.md) §3.3 (isolation + PII). **Machine sources
> (CI-gated):** `contracts/tenants/state-capabilities.yaml` — the state × capability
> matrix (rendered into docs/03 §5.1 by `scripts/verify_tenant_states.py`, gate 16, and
> consumed by the docs/35 I-20 table-driven test); `contracts/tenants/tenant-settings.schema.json`
> — the settings validation contract.

## 1. What a tenant is — five facts that must never drift apart

A tenant on Alpha One is **one coherent thing expressed in five places**. Every
multi-tenancy bug class is one of these drifting from the others, so the platform keeps
them bound by construction (the provisioning saga writes them in one transactional
sequence) and by reconciliation (nightly job, docs/43 §7):

| # | Fact | Where it lives | Bound by |
|---|---|---|---|
| 1 | **The business entity** — firm, jurisdiction, KYB, plan, status | `tenants` row (guard-only, platform realm) | the saga's step 2; the state machine (§5) |
| 2 | **The identity partition** — one ZITADEL Organization + one OIDC application | `tenants.idp_org_id` + `tenants.idp_client_id` (secret in the tenant secret store, referenced) | saga step 3 (G34/D19); compensation destroys on failure |
| 3 | **The host** — `{slug}.alpha1.io` (+ custom domain, V1.1) | `tenants.slug` — the **only** subdomain source of truth (decision D); `domain_mappings` holds custom domains only | saga step 5; G8 rules (§4) |
| 4 | **The data partition** — `tenant_id` on every tenant-owned row | every per-module table (shared schema, ADR-1) | app guard + RLS (§7); isolation suite |
| 5 | **The configuration set** — settings, branding, entitlements, limits, flags | `tenants.settings/branding/features/limits` + `tenant_entitlements` + Flipt | JSON Schema validation (M6, now `contracts/tenants/tenant-settings.schema.json`); denormalised resolved rows |

One database, one schema, one box (ADR-9/ADR-10): **scaling = more rows, not more
infrastructure** — no per-tenant schema, database, or service exists anywhere in the
stack, and none may be introduced without revisiting ADR-1 (> 200 tenants is the
recorded trigger, docs/03 §12).

## 2. Who holds tenants

- **Creation is platform-side in V1** (1–5 tenants): a `platform:super_admin` creates the
  tenant in CON (`tenant.create`), which starts the saga. No self-serve signup until V3
  (`BIL-18`) — but the pipeline is built as if signup existed (same steps, different trigger).
- **Administration is split by realm**: the tenant's own staff (`firm:admin`/`firm:owner`)
  run the inside surfaces (ADM: settings, branding, checklist, integrations); platform
  staff run the outside surfaces (CON: create, suspend, entitlements, provisioning resume,
  termination). AUTH-16 keeps the realms structurally separate; the authorization answer
  for every route is `matrix.md` §3 (docs/46).
- **Nobody else exists**: there is no broker-side, provider-side, or parent-tenant
  principal in V1 (`tenants.parent_id` is the ADR-2 door, `NULL` in V1; sub-tenants are a
  recorded future review, not a feature).

## 3. The identity plane — one org per tenant

The tenant's identity partition is a **ZITADEL Organization** (ADR-13): one org per
tenant (`idp_org_id`), one OIDC application per org whose client id is the tenant's token
audience (`idp_client_id` — the D19 binding that makes a tenant-A token worthless on
tenant B's host), per-org login/password/lockout policy and branding, org domain
`{slug}.alpha1.io`. The **platform org** (`alpha1-platform`) is staff-only: its members
hold console roles, no tenant memberships, and its org policy is `force_mfa = true` (G33).

Practical consequences a developer must know:

- **Login is org-scoped** at `login.alpha1.io` (`urn:zitadel:iam:org:id:{id}`, G19): the
  tenant's branding/policies apply; the tenant's own domains serve the app, never a login
  form in V1 (vanity login host is the V2 edge-rewrite, docs/03 §3.8).
- **The same person at two tenants** is one `identities` row with two memberships and two
  ZITADEL users (one per org, joined by `identity_idp_links`; cross-org auto-link needs a
  verified email — G36/D21). The **active tenant comes from the request host**, never
  from a token claim (G1 model, docs/42 §3.1).
- **Deprovisioning propagates IdP → us** via the `idp-sync` pull consumer; routing is
  explicit (G32): platform-org events → staff path; unknown org → **hold cursor + alert**
  (never guess); `deleted`/`archived` tenant events → apply to the membership row + audit.
- **Suspension is two-sided**: `tenant.suspended` kills sessions in our deny-set **and**
  terminates ZITADEL sessions, so a suspended tenant's users cannot log in even if our
  API is bypassed (≤ 1 s, TEN-15).

## 4. Tenant resolution — the edge's first decision

Binding order (docs/02 §3.4, GW step 2): **custom domain → subdomain → internal
`X-Tenant-Id` (internal route group only) → API-key-embedded (key wins over headers)**.
Rules that trip implementers:

- An **unresolved host** returns `404 tenant.unknown_host` — never 400, never 403 (a
  host is public knowledge via DNS; the 404 avoids subdomain enumeration, I-14). An
  **unknown tenant id** on a platform surface returns `404 tenant.not_found`. The two
  codes are distinct and were conflated in docs/02 §3.4 until this pass (M2).
- Resolution is cached (in-mem 30 s + Redis 5 min; negative lookups 60 s) — a tenant
  state change invalidates via `tenant.*` events; the 3.5 status gate re-checks state on
  its own ≤ 5 s cache so a suspension never waits for the resolution TTL.
- Subdomain rules (G8, V1 binding): 3–30 chars, `[a-z0-9-]`, no leading/trailing hyphen,
  no double hyphen, not all-digits, no punycode (homograph protection), the 31-name
  reserved list (docs/03 §3.2), availability = slug ∧ reserved list in one call.
  **Subdomains are immutable in V1** — `TEN-43` (V2) is an explicit migration with a
  redirect window, never an edit field.
- **Custom domains are V1.1** (`domain_mappings` + TXT verification + Cloudflare for
  SaaS TLS); the resolution order already carries them.

## 5. Lifecycle — states, capabilities, transitions

Ten states (`tenants.status`, docs/03 §9): `pending_approval → provisioning →
(provisioning_failed ⟲ resume) → onboarding → active → suspended ⟷ active`,
plus the termination line `active/onboarding → deactivated → (30 d) → pending_deletion →
archived → deleted`. The **state × capability matrix** — what each state does to trader
routes, staff routes, API keys, webhooks, bridge sync, payments and payouts, with the
exact GW-18 code per blocked cell — is machine-readable
(`contracts/tenants/state-capabilities.yaml`) and rendered in docs/03 §5.1. It is the
source for the docs/35 I-20 table-driven test; the check fails the build when the
rendered table, the YAML, the DDL status list, or the error taxonomy drift apart
(gate 16). Highlights a developer must internalise:

- **Pre-`active` tenants are dark** — most have no DNS yet (it is created by saga step 5),
  so the host fails resolution (`tenant.unknown_host`); once it resolves, the 3.5 gate
  refuses with `tenant.not_live` (details.state). `onboarding` is the one state where
  staff work while traders are blocked — that is the checklist state by design.
- **Suspension is immediate and reversible** (≤ 1 s, two-sided session kill); webhooks
  in flight drain ≤ 24 h then DLQ; payouts hold per PAY policy; bridge pauses resumably.
- **Nothing is ever hard-deleted in place**: termination is a saga (§6), PII is
  anonymised, financial/audit rows survive with `identity_id` → NULL per AUD retention,
  and `deleted` keeps the tombstone — **ids and slugs are never reused**.

## 6. Birth and death — the two sagas

**Provisioning** (docs/03 §3.5, 9 steps + 3a + 6b): validate/KYB/sanctions → create row →
provision the ZITADEL org + application + owner membership (+ 3a: external IdP + SCIM
token when contracted; **no group→role mapping in V1**, D22 — roles are assigned by us) →
branding/legal defaults → DNS → broker group + rule packs **+ the LED chart-of-accounts
seed (6b, decision D26 — docs/48)** → Flipt flags → welcome invite → `onboarding`. Orchestrated in `workers` on a PG `FOR UPDATE SKIP LOCKED` queue; every
step idempotent with a named compensation; terminal failure → `provisioning_failed` +
CON resume. MIG (TTS cutover) reuses this pipeline with extra import steps.

**Termination** (docs/03 §5.2): `tenant.terminate` runs the deletion saga — suspend →
export → suspend all IdP users → archive R2 → anonymise PII → retention window →
data_cleanup (documents, DNS removal, IdP erasure per docs/02 §10.4) → `deleted`
tombstone. **The ZITADEL org is retained as the IdP-side tombstone, never destroyed by
the saga** (M4, now stated in docs/03 §5.2): after erasure it has no users, sessions or
SSO config, so login is impossible; org destruction exists only as the step-3
compensation and an audited break-glass runbook.

## 7. The isolation model — seven layers, and what each one catches

Isolation is **layered, fail-closed, and proven by tests**, not trusted to any single
mechanism. A bug in one layer is caught by the next; the suite (§13) proves the
composition.

| # | Layer | Mechanism | Catches |
|---|---|---|---|
| 1 | **Routing / realm** | four route groups (GW-01); token audience == resolved tenant's app (D19); console routes refuse tenant tokens and vice versa (AUTH-16) | cross-realm access; a token from tenant A used on tenant B's host (`auth.tenant_mismatch`) |
| 2 | **Status gate** | GW 3.5a/b/c — tenant → identity → membership state, ≤ 5 s cache, event-invalidated | serving data for a suspended/pre-active tenant or a suspended user/membership |
| 3 | **Authorization** | one role per membership; registry keys enforced per route (docs/46) | a role acting outside its key set inside the tenant |
| 4 | **Application guard** | every sqlc query tenant-bound; `tenant_id` immutable at write; CI grep-class check on new queries; query without `tenant_id` = review red flag | a forgotten predicate in code |
| 5 | **Postgres RLS** (D3/D16) | `FORCE ROW LEVEL SECURITY` on every tenant-owned table, policy on `current_setting('app.tenant_id', true)` (unset → 0 rows), `SET LOCAL` in-transaction (PgBouncer-safe), `WITH CHECK` on writes; exemptions are **named**: 4 `SECURITY DEFINER` accessors (context-free auth lookups incl. console sessions), enumerated `app_platform` services (relay, ledger/audit appliers, ANA updaters, `idp-sync`, CON read models — still with explicit predicates, CI-checked), `migrator` | a forgotten predicate *and* a compromised guard — a wrong query returns zero rows instead of another tenant's data |
| 6 | **Storage scoping** | R2 per-tenant prefixes (documents, branding); per-tenant DEK envelope encryption for secrets/PII fields (master key off-repo); signed URLs, short TTL | cross-tenant object access; at-rest exposure of one tenant's secrets |
| 7 | **Operational caps** | Redis `t:{tenant}:*` namespacing; per-tenant rate limits + quotas (GW 5/6); `limits.Assert` write-time caps; broker poll budget share (noisy-neighbour bulkheads, docs/03 §11) | one tenant exhausting a shared resource or hammering a provider |

Platform-owned tables (`tenants`, `identities`, `identity_idp_links`, `auth_backup_codes`,
`casbin_rule`, platform audit rows) are **guard-only, not RLS-scoped** — reached through
identity-scoped accessors; naming the exemption list is what makes layer 5 real rather
than decorative (docs/44 §5). Data residency (TEN-24) is parked for V3 — one region
exists (ADR-9), and the decision is recorded, not forgotten (docs/41 §5).

## 8. Configuration — one resolved row, validated on write

The config inheritance chain is **platform default → plan/tier → tenant override**,
resolved **on write** into the tenant's denormalised rows (never computed on read).
Curated `settings` keys (trading, challenge, risk, payout, kyc, comms, legal, geo) are
validated against `contracts/tenants/tenant-settings.schema.json` — added this pass (M6;
docs/03 §3.3 referenced it and the file did not exist). Rules: unknown keys rejected;
**no secret ever enters `settings`** (tenant credentials live in `integration_config`
behind the §3.7 inventory: encrypted, masked reads, reveal-audited); `custom_css` is
sanctioned (≤ 20 KB, styles only); legal URLs must be https and tenant-owned. Branding
is data → compiled to CSS variables + email/PDF brand at render time. Entitlements
(`tenant_entitlements` + Flipt kill switches) gate **modules** at GW step 6
(`tenant.not_entitled`); changes are platform-side (`tenant.entitlement.change`) and
emit `tenant.entitlement_changed` for cache/GW/Flipt sync. Versioning/rollback
(`tenant_settings_versions`) and the effective-value view are V2 (TEN-27/28/39).

## 9. Limits, quotas, metering — the noisy-neighbour contract

`limits` (docs/03 §3.1) are **enforced at write time** by `limits.Assert` in the owning
domain (over-limit → 422 `tenant.limit_exceeded` with `details.metric` — the code name
was corrected this pass, M3); `usage_events` metering is buffered off the request path
(flush 60 s / 1 k events) and is the V3 BIL foundation; 80 %/100 % thresholds emit
`tenant.limit_exceeded` events (V2 alerting, TEN-20/22/23). Edge→per-user→per-route rate
limits plus per-tenant RPM plans and broker-poll budget shares bound any single tenant's
blast radius on shared infrastructure.

## 10. Cross-tenant surfaces — who may see across the wall

The wall is the product; these are its doors, each named and controlled:

| Door | Who | Control |
|---|---|---|
| CON platform console | `platform:*` roles | console realm; every cross-tenant read is role-gated **and** audit-critical; no tenant-realm action exists in V1 (no impersonation) |
| Platform analytics roll-ups | reserved `platform.analytics.read` (V2, ANA-28 pattern) | aggregates only, no per-trader PII; never held by tenant roles |
| Cross-tenant services | relay, ledger/audit appliers, ANA updaters, `idp-sync`, CON read models | `app_platform` (`BYPASSRLS`), enumerated, explicit predicates, CI-checked |
| MIG migration tooling | platform staff, cutover window | runs the tenant pipeline with import steps; `migration.*` keys, two-op cutover |
| Audit export | `firm:compliance`/`firm:admin` (own tenant), CON platform view | `audit.export` audited; the export itself is recorded |
| Support/context reads | `firm:support` (own tenant) | `account.read` only — no KYC documents, no payout methods, no writes |

Anything not on this list is **not a door**. A feature that needs cross-tenant reads
must add its key to the registry with a `platform` scope and its own audit story — never
reuse a tenant-scope key (docs/46 §4.5).

## 11. Verification map

| Check | Where | What proves |
|---|---|---|
| I-01 / I-14 | docs/35 §3 | querying as another tenant → 0 rows; unauthorized reads → 404, never data |
| I-17 | docs/35 §3 | RLS fail-closed: no context → 0 rows everywhere; cross-tenant INSERT → `WITH CHECK` reject |
| I-20 | docs/35 §3 | the state × capability matrix holds for every pair — table-driven over `state-capabilities.yaml` |
| RLS negative suite | docs/35 §5.1, docs/44 §5 | accessors vs `app_rw` vs `app_platform`, console-session invisibility, migration under `FORCE RLS` |
| Gate 9–15 | docs/99 | the auth/authz set (roles seeded, audience binding, route coverage, step-up, matrix freshness) |
| **Gate 16 (this pass)** | docs/99 | `state-capabilities.yaml` ⇄ docs/03 §5.1 render ⇄ DDL status list ⇄ error taxonomy |
| Restore drill | docs/06 §3.2 (monthly) | post-restore isolation verify: tenant A sees only A |
| Resolution order test | docs/35 §5.1 | custom domain → subdomain → header → key; unknown host → 404 |

## 12. Residual gaps — recorded, owned, not silent

- **KYB is manual in V1** (CON staff review of legal documents); automated sanctions
  screening is V2 — the gate itself (`tenant.kyb_required`) is V1 and enforced on
  activation.
- **Custom domains and the sending-domain DNS (SPF/DKIM) are V1.1/V2**; until then every
  tenant mails from the platform domain and serves only the `alpha1.io` subdomain.
- **The provisioning orchestrator is a single worker** — deliberately (9 steps, one box);
  the recorded revisit trigger is steps > 20 or a second region (docs/03 §12).
- **Data residency (TEN-24)** is V3-parked pending a second region; `data_region` is
  metadata only today.

## 13. Post-V1 reservations

`parent_id` sub-tenants (ADR-2 review at V3), impersonation-with-consent (TEN-16 + CON-07
+ AUD-08, V2), self-serve signup (BIL-18, V3), the full white-label editor + terminology/
locale keys (TEN-04/06/07, V2), per-tenant API version pinning (V2 door), residency
(TEN-24, V3). Each joins the registry/settings schema at its module's freeze
(docs/99 §12).

## 14. This pass — findings and changes (2026-09-19)

| # | Finding | Severity | Resolution |
|---|---|---|---|
| M1 | **Multi-tenancy had no consolidated specification and no machine-readable behaviour**: the lifecycle, isolation layers, per-tenant identity, provisioning and cross-tenant rules were spread across docs/02/03/04/28/41/44, and the state × capability matrix existed only as hand-maintained prose — despite docs/35 I-20 demanding a table-driven test over exactly that matrix | High | **FIXED** — this document + `contracts/tenants/state-capabilities.yaml` (machine source) + `scripts/verify_tenant_states.py` (render + cross-checks, gate 16) |
| M2 | **Unregistered and conflated error codes**: `tenant.not_ready` was cited by docs/03 §5.1, docs/04 GW 3.5a and docs/44 §7 but never existed in the taxonomy (canonical: `tenant.not_live` — whose meaning now covers every pre-`active` state with `details.state`); docs/02 §3.4 returned `tenant.not_found` for an unresolved *host* (canonical: `tenant.unknown_host`; `not_found` is the unknown-*id* code) | Medium | **FIXED** — all references corrected in docs/03/04/44/02, `tenant.not_live` meaning widened in docs/03 §6.2 + both taxonomy files; the verifier now fails if a matrix cell cites an unregistered code |
| M3 | **Stale code names** in docs/03: `ten.limit_exceeded` (§3.1, pre-convention) and `TENANT_LIMIT_EXCEEDED` (blueprint step 6) vs the registered `tenant.limit_exceeded` | Low | **FIXED** — both corrected |
| M4 | **The IdP org's fate at termination was unstated** — the deletion saga suspended/deleted users but never said what happens to the ZITADEL org or the subdomain DNS; `platform.tenant.provision` mentions "destroy a tenant org" only as saga compensation | Medium | **FIXED** — docs/03 §5.2 now states: org retained as the IdP-side tombstone (empty ⇒ login impossible), DNS removed at data_cleanup, destruction only via step-3 compensation or audited break-glass; slugs/ids never reused |
| M5 | **`contracts/api/tenant.md` still said `DRAFT / Owner: TBD / Last updated: TODO`** and its error note carried a 5-name shorthand of the 31-name reserved list | Low | **FIXED** — header ratified (owner TEN/BE-2, dated, frozen-v0 basis); the full G8 reserved list referenced |
| M6 | **The settings JSON Schema was dangling**: docs/03 §3.3 named `contracts/tenants/tenant-settings.schema.json` as the validation source but the file did not exist in the pack — a developer implementing settings writes had no contract | Medium | **FIXED** — the schema is authored (curated keys, `additionalProperties: false`, secrets explicitly out of scope, V2 keys intentionally absent until their freeze) |
| M7 | **`workers` was missing from the RLS model**: event consumers, schedulers, reconcilers, the provisioning orchestrator and the metering flusher all do cross-tenant DB work, yet the `app_platform` exemption enumerated only relay / ledger-audit appliers / ANA updaters / `idp-sync` / CON read models — a developer wiring a worker had no defined DB role | High | **FIXED / DECIDED (W, owner answer 2026-09-19)** — hybrid: worker jobs run **tenant-scoped by default** (`app_rw` + per-message `app.tenant_id` from the event/job, under RLS); only manifest-named platform-wide jobs (DLQ sweep, cross-tenant session cleanup, report generation) get `app_platform`, CI-asserted. docs/02 §9 row, docs/28 §3.3, docs/44 §5 amendment note |
| M8 | **`usage_events` had no retention/partitioning rule** — an unbounded table shipping in V1 (the docs/28 retention classes S1–S5/S2b do not cover metering) | Medium | **FIXED / DECIDED (U, owner answer 2026-09-19)** — monthly `PARTITION BY RANGE`; raw rows kept **25 months** then partitions dropped; monthly rollups (`usage_rollups_monthly`) from month 13 for BIL (V3); purge at tenant deletion per docs/03 §5.2. docs/03 §9 DDL + rules |
| M9 | **A subdomain was represented twice** (`tenants.slug` and `domain_mappings(type='subdomain')`) with no precedence rule and no instruction whether the saga writes the mappings row | Low | **FIXED / DECIDED (D, owner answer 2026-09-19)** — `tenants.slug` is the single subdomain source of truth; `domain_mappings` is custom-domains-only and its `subdomain` enum value drops at the V1.1 freeze. docs/03 §3.2 + §9 DDL comment |
| M10 | **Mechanical drift**: the `tenants` DDL carried a duplicate suspension column (`suspension_reason` *and* `suspended_reason`), docs/04's GW 3.5a did not state it is route-class-aware (onboarding staff surfaces pass), `tenants.features` had no sync rule, and gates 15/16 were not recorded in the docs/34 §9 checklist | Low | **FIXED** — duplicate column removed (propagated to docs/32 + `contracts/data/schemas/03-ten.sql` via the generators); 3.5a route-class note; features snapshot = same-transaction write, never read for authz; both gate checklist items added to docs/34 §9 |

No PRD workbook row changed; no decision was re-opened. `docs/30`/`contracts/errors/taxonomy.md`
rows changed meaning-text only (no code added or removed — the registry still has exactly
the V1 set plus the same extended names).

## 15. Owner decisions W / U / D (asked and answered, 2026-09-19)

Raised as interactive findings M7–M9; the owner picked one option each. Binding from now on:

| ID | Question | Decision |
|---|---|---|
| **W** | How do `workers` get DB access under RLS? | **Hybrid (per-message tenant context).** Worker jobs run as `app_rw` with `SET LOCAL app.tenant_id` taken from the event's/job's `tenant_id` and stay under RLS by default. The workers manifest names the platform-wide jobs that may use the `app_platform` DSN (initially: DLQ sweep, cross-tenant session cleanup, report generation); CI asserts only manifest jobs reference that DSN, and the list grows by *job name*, not by service. Every event and saga job already carries `tenant_id` (EVT-03), so the context is always available; a job without one is platform-wide by definition and must be in the manifest. |
| **U** | Retention/partitioning for `usage_events`? | **Declared now.** Monthly `PARTITION BY RANGE(period_started_at)`; raw rows kept **25 months**, partitions dropped by the scheduled-jobs worker past the window; the flusher writes `usage_rollups_monthly` `(tenant_id, metric_name, month, value_total, sample_count)` from month 13 onward, and BIL (V3) reads rollups for anything older. Tenant deletion purges raw + rollups per docs/03 §5.2 (rollups keep anonymised totals where the §5.2 retention rule requires). |
| **D** | Source of truth for a subdomain? | **`tenants.slug` only.** Resolution reads the slug for `{slug}.alpha1.io` and never `domain_mappings`; that table is custom-domains-only, and its `type='subdomain'` value is dropped at the V1.1 custom-domain freeze (TEN-05/26). The saga's DNS step creates no mappings row for the subdomain. |

---

*Navigation: [03 — TEN](03-tenant-management.md) (binding module design) ·
[02 — AUTH](02-identity-access.md) §3.1/§3.4 · [04 — GW](04-gateway-events.md) §3.1 ·
[46 — Authorization Model](46-authorization-model.md) (the who-can-do-what companion) ·
[44 — fourth pass](44-auth-multitenancy-review.md) (D13–D18, RLS exemption model) ·
`contracts/tenants/state-capabilities.yaml` + `contracts/tenants/tenant-settings.schema.json`
(machine sources).*

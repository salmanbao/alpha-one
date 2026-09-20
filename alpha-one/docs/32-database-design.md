# 32 — Database Design (Master Schema)

> **Generated aggregation** of the database designs in the 26 module docs
> (each doc's §9). This is the master schema the migrations (golang-migrate,
> 01 §2) are generated from; the owning doc is the authority for each block,
> this file is the review surface (one place to see the whole schema). The
> full DDL of the 27 ecosystem module's tables is in doc 27 §9 verbatim.

## 1. Conventions (binding, 01 ADR-1, 05 §9, 32 = this doc)

- **`tenant_id ULID NOT NULL`** on every tenant-scoped table (the structural
  isolation, 28 §3.3); exceptions (the platform-level): `tenants`,
  `identities`, `audit_events` (tenant + platform scope, 05 §9).
- **ULIDs** everywhere (01 §2); the char-25 top-3-bits guard (02 §3.5);
  public surface uses `public_id_refs` (27 Part A §8), never raw ULIDs.
- **Money**: `_cents BIGINT` + `currency` (no floats, 05 §9).
- **Time**: `TIMESTAMPTZ` (the broker-attested for trading, ADR-12, 01 §3).
- **Partitioning**: monthly partitions for the high-volume tables (the 08
  deals/ticks, the 05 entries/audit, the 04 outbox); the 13-mo tick retention
  (04 §5.4) → R2 archive (06 §3.2, 29 §3.2).
- **Retention**: 7-yr financial/audit (00 §6, 05 §3.5), 2-yr tickets (18 §3.5),
  12-mo competition (24 Part B), 30-day sandbox (27 Part A §5).
- **Append-only**: `ledger_entries`, `audit_events` — the `BEFORE UPDATE`/
  `BEFORE DELETE` triggers reject (05 §9, 28 §3.3).
- **PII**: envelope-encrypted `pii_*` / `*_encrypted` columns (02 §3.7, 28 §3.3);
  documents in R2 (per-tenant prefix), the PG holds the ref only (13 §3.4).
- **Indexes**: every `(tenant_id, …)` leading; the read-model tables (`*_ro`)
  are the query surface for reads (19 §3.1).

## 2. The schema (128 tables in 30 DDL blocks, module-ordered)

### 02 — AUTH (from docs/02-identity-access.md §9)

```sql
-- platform-wide identity (no tenant_id by design)
CREATE TABLE identities (
  id            ULID PRIMARY KEY,
  idp_user_id   TEXT UNIQUE,                -- ZITADEL user id (sub); NULL until first login
  identity_key  TEXT UNIQUE NOT NULL,       -- sha256 of the FIRST verified email — immutable join key (G35/D20)
  idp_org_id    TEXT,                       -- the ZITADEL org that owns this user object
  realm         TEXT NOT NULL DEFAULT 'tenant'
                CHECK (realm IN ('tenant','platform')),   -- AUTH-16 audience realm
  email         CITEXT UNIQUE NOT NULL,     -- cache of the current primary address; matching uses identity_emails
  email_verified BOOLEAN NOT NULL DEFAULT false,
  phone         TEXT, phone_verified BOOLEAN NOT NULL DEFAULT false,
  password_hash TEXT,                       -- argon2id; NULL for social-only (V3)
  password_changed_at TIMESTAMPTZ,
  password_history JSONB NOT NULL DEFAULT '[]',   -- last 5 argon2id hashes
  first_name TEXT, last_name TEXT, display_name TEXT,
  date_of_birth DATE, nationality CHAR(3),
  status        TEXT NOT NULL DEFAULT 'pending_verification'
                CHECK (status IN ('pending_verification','active','suspended','banned','deactivated')),
  suspension_reason TEXT,
  mfa_enabled   BOOLEAN NOT NULL DEFAULT false,   -- mirror of ZITADEL factor state
  mfa_enrolled_at TIMESTAMPTZ,                    -- D5: staff 2FA enforced from first login
  -- TOTP secrets live in ZITADEL and are never stored here (§10.2)
  failed_logins INT NOT NULL DEFAULT 0,
  locked_until  TIMESTAMPTZ,
  last_login_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  deleted_at TIMESTAMPTZ                    -- GDPR soft-delete marker
);
CREATE INDEX idx_identities_status ON identities(status) WHERE status = 'suspended';

-- one identity ↔ N ZITADEL users (one per org) — review G21 / decision D13, docs/44 §3
CREATE TABLE identity_idp_links (
  idp_user_id   TEXT PRIMARY KEY,              -- ZITADEL user id (sub)
  identity_id   ULID NOT NULL REFERENCES identities(id),
  idp_org_id    TEXT NOT NULL,                 -- ZITADEL org (resource owner) of this user object
  tenant_id     ULID REFERENCES tenants(id),   -- NULL for the platform org
  state         TEXT NOT NULL DEFAULT 'active' CHECK (state IN ('active','retired')),
  first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_seen_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  retired_at    TIMESTAMPTZ,
  UNIQUE (identity_id, idp_org_id)             -- one live user object per org per identity
);
CREATE INDEX idx_idp_links_identity ON identity_idp_links(identity_id) WHERE state = 'active';
-- `identities.idp_user_id` / `idp_org_id` above are a denormalised pointer to the most
-- recently used link (join convenience), never the lookup key.

-- every address an identity has ever verified (review G35 / D20). Matching for
-- /session, idp-sync and the AUTH-36 merge reads email_hash; identity_key never moves.
CREATE TABLE identity_emails (
  id          ULID PRIMARY KEY,
  identity_id ULID NOT NULL REFERENCES identities(id),
  email_hash  TEXT UNIQUE NOT NULL,        -- sha256(lower(trim(email))) — the match key
  email       CITEXT NOT NULL,
  is_primary  BOOLEAN NOT NULL DEFAULT true,
  verified_at TIMESTAMPTZ,                 -- set only on a verified address (G36/D21)
  retired_at  TIMESTAMPTZ,                 -- row kept: a later login on the old address resolves here
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_identity_emails_identity ON identity_emails(identity_id);
-- exactly one live primary per identity (partial unique index in the migration)

CREATE TABLE tenant_memberships (
  id          ULID PRIMARY KEY,
  identity_id ULID NOT NULL REFERENCES identities(id),
  tenant_id   ULID NOT NULL REFERENCES tenants(id),
  role        TEXT NOT NULL DEFAULT 'user:trader',   -- single role per membership; the role's
                                                     -- effective key set (roles.yaml) is the grant
  -- lifecycle (G37/D22): `user.human.added`/invite → invited; first successful /v1/auth/session → active
  status      TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','suspended','invited')),
  display_name_override TEXT,
  joined_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_active_at TIMESTAMPTZ,
  UNIQUE (identity_id, tenant_id)
);
CREATE INDEX idx_membership_tenant ON tenant_memberships(tenant_id, status);
CREATE INDEX idx_membership_identity ON tenant_memberships(identity_id);

-- projection of the ZITADEL session + our revocation state (P2)
CREATE TABLE auth_sessions (
  id            ULID PRIMARY KEY,
  identity_id   ULID NOT NULL REFERENCES identities(id),
  tenant_id     ULID REFERENCES tenants(id),        -- NULL for console sessions
  is_console    BOOLEAN NOT NULL DEFAULT false,     -- platform realm (AUTH-16)
  idp_session_id TEXT NOT NULL,                     -- ZITADEL session id
  idp_token_jti  TEXT,                              -- current access-token jti
  -- refresh tokens are ZITADEL's (rotation + reuse detection, D17): we store no
  -- refresh secret, only the session facts needed for revocation and step-up
  amr           TEXT[] NOT NULL DEFAULT '{}',       -- otp/webauthn/pwd (AUTH-09)
  user_agent TEXT, ip INET, geo JSONB,
  mfa_verified_at TIMESTAMPTZ,                      -- step-up freshness (auth_time)
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  idle_expires_at TIMESTAMPTZ NOT NULL,
  abs_expires_at  TIMESTAMPTZ NOT NULL,
  revoked_at TIMESTAMPTZ, revocation_reason TEXT
);
CREATE INDEX idx_sessions_identity ON auth_sessions(identity_id, revoked_at);
CREATE INDEX idx_sessions_idp ON auth_sessions(idp_session_id);

-- backup codes are ours (AUTH-11, V1 per D5): 10 single-use, Argon2id-hashed
CREATE TABLE auth_backup_codes (
  id ULID PRIMARY KEY,
  identity_id ULID NOT NULL REFERENCES identities(id),
  code_hash TEXT NOT NULL,
  used_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_backup_codes_identity ON auth_backup_codes(identity_id) WHERE used_at IS NULL;

CREATE TABLE api_keys (
  id         ULID PRIMARY KEY,
  identity_id ULID NOT NULL REFERENCES identities(id),
  tenant_id  ULID NOT NULL REFERENCES tenants(id),
  name       TEXT NOT NULL,
  key_prefix TEXT NOT NULL,          -- 11 chars, display
  key_hash   TEXT NOT NULL UNIQUE,   -- sha256 of full key
  scopes     TEXT[] NOT NULL,
  rate_limit_per_min INT NOT NULL DEFAULT 600,
  expires_at TIMESTAMPTZ,
  last_used_at TIMESTAMPTZ, last_used_ip INET,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  revoked_at TIMESTAMPTZ
);
CREATE INDEX idx_apikeys_tenant ON api_keys(tenant_id) WHERE revoked_at IS NULL;
-- audit_events: see 05-ledger-audit (AUD-01 schema) — AUTH emits into it.

-- authorization policy (ADR-14): standard Casbin tables + the change ledger
CREATE TABLE casbin_rule (
  id    BIGSERIAL PRIMARY KEY,
  ptype TEXT NOT NULL,          -- p (policy) | g (role inheritance)
  v0 TEXT, v1 TEXT, v2 TEXT, v3 TEXT, v4 TEXT, v5 TEXT
);
CREATE UNIQUE INDEX idx_casbin_rule ON casbin_rule (ptype, v0, v1, v2, v3, v4, v5);
CREATE TABLE authz_policy_versions (
  version    BIGINT PRIMARY KEY,
  applied_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  actor      TEXT NOT NULL,     -- migration or staff runbook (V1 has no policy-CRUD surface)
  summary    TEXT NOT NULL      -- the full delta is an audit_events row
);
```

### 03 — TEN (from docs/03-tenant-management.md §9)

```sql
CREATE TABLE tenants (
  id            ULID PRIMARY KEY,
  slug          VARCHAR(63) UNIQUE NOT NULL,
  idp_org_id    TEXT UNIQUE,                      -- ZITADEL org (review G1); NULL until provisioned
  idp_org_domain TEXT,                            -- {slug}.alpha1.io, set as the org domain
  idp_client_id TEXT UNIQUE,                      -- that org's OIDC application audience — token `aud` check (G34/D19)
  idp_client_secret_ref TEXT,                     -- SOPS/KMS reference; the secret itself never lives in this row
  parent_id     ULID REFERENCES tenants(id),      -- ADR-2 door, NULL in V1
  firm_name     VARCHAR(255) NOT NULL,
  legal_entity_name VARCHAR(255), registration_number VARCHAR(100), tax_id VARCHAR(100),
  jurisdiction  CHAR(2) NOT NULL DEFAULT 'PK',
  kyb_status    TEXT NOT NULL DEFAULT 'pending' CHECK (kyb_status IN ('pending','verified','failed')),
  kyb_verified_at TIMESTAMPTZ,
  primary_contact JSONB NOT NULL DEFAULT '{}',     -- {name,email,phone}
  support_email TEXT,
  status        TEXT NOT NULL DEFAULT 'pending_approval'
    CHECK (status IN ('pending_approval','provisioning','provisioning_failed','onboarding',
                      'active','suspended','deactivated','pending_deletion','archived','deleted')),
  plan          TEXT NOT NULL DEFAULT 'manual',     -- contract ref V1; BIL plan id V3
  limits        JSONB NOT NULL DEFAULT '{}',
  settings      JSONB NOT NULL DEFAULT '{}',        -- validated vs contracts schema
  branding      JSONB NOT NULL DEFAULT '{}',
  features      JSONB NOT NULL DEFAULT '{}',        -- denormalized entitlements snapshot; written only in the entitlement-change transaction (never a second write path, never read for authz)
  onboarding_state JSONB NOT NULL DEFAULT '{"completedSteps":[]}',
  data_region   VARCHAR(20) NOT NULL DEFAULT 'eu-hetzner',
  suspended_at  TIMESTAMPTZ, suspension_reason TEXT,
  created_by    ULID,                                -- platform staff identity
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  activated_at  TIMESTAMPTZ                         -- set on the onboarding->active transition
  deletion_scheduled_at TIMESTAMPTZ
);
CREATE INDEX idx_tenants_status ON tenants(status);
CREATE INDEX idx_tenants_parent ON tenants(parent_id) WHERE parent_id IS NOT NULL;

CREATE TABLE domain_mappings (
  id            ULID PRIMARY KEY,
  tenant_id     ULID NOT NULL REFERENCES tenants(id),
  domain        VARCHAR(255) UNIQUE NOT NULL,
  -- custom domains ONLY (decision D, docs/47 §15): the subdomain lives solely in
  -- tenants.slug — resolution never reads this table for {slug}.alpha1.io, and the
  -- 'subdomain' enum value is dropped at the V1.1 custom-domain freeze
  type          TEXT NOT NULL CHECK (type IN ('subdomain','custom')),
  verified      BOOLEAN NOT NULL DEFAULT false,
  verification_token TEXT,            -- TXT record token (custom domain)
  ssl_status    TEXT NOT NULL DEFAULT 'pending',
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE tenant_entitlements (
  id           ULID PRIMARY KEY,
  tenant_id    ULID NOT NULL REFERENCES tenants(id),
  module       TEXT NOT NULL,          -- 'td','adm','not','cmp','sdk',...
  enabled      BOOLEAN NOT NULL DEFAULT true,
  limit_override JSONB,                -- e.g. {"max_rules": 50}
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, module)
);

CREATE TABLE provisioning_jobs (
  id              ULID PRIMARY KEY,
  tenant_id       ULID REFERENCES tenants(id),
  type            TEXT NOT NULL DEFAULT 'provision',
  status          TEXT NOT NULL DEFAULT 'pending'
                  CHECK (status IN ('pending','running','succeeded','failed','needs_resume')),
  current_step    TEXT,
  completed_steps JSONB NOT NULL DEFAULT '[]',
  failed_step     TEXT, error_message  TEXT,
  context         JSONB NOT NULL DEFAULT '{}',
  started_at      TIMESTAMPTZ, completed_at TIMESTAMPTZ,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_provjobs_active ON provisioning_jobs(status) WHERE status IN ('pending','running','needs_resume');

CREATE TABLE usage_events (               -- BIL foundation (V3 billing reads these)
  id               ULID,
  tenant_id        ULID NOT NULL,
  metric_name      TEXT NOT NULL,         -- active_traders, funded_accounts, api_calls,
                                          -- storage_gb, payouts_processed, kyc_verifications...
  value            NUMERIC(18,4) NOT NULL,
  unit             TEXT NOT NULL,
  period_started_at TIMESTAMPTZ NOT NULL,
  recorded_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  idempotency_key  TEXT,
  PRIMARY KEY (id, period_started_at)   -- partitioned table: PK must include the partition key
) PARTITION BY RANGE (period_started_at);  -- monthly partitions (decision U, docs/47 §15)
CREATE INDEX idx_usage_tenant_metric ON usage_events(tenant_id, metric_name, period_started_at);

-- Retention (decision U, 2026-09-19): raw rows are kept 25 months (monthly partitions
-- dropped past the window by the scheduled-jobs worker); from month 13 onward the
-- flusher also writes monthly rollups below, and BIL (V3) reads rollups for anything
-- older. Tenant deletion purges both per §5.2 (rollups keep the anonymised totals).
CREATE TABLE usage_rollups_monthly (
  tenant_id        ULID NOT NULL,
  metric_name      TEXT NOT NULL,
  month            DATE NOT NULL,          -- first day of the month, UTC
  value_total      NUMERIC(18,4) NOT NULL,
  sample_count     BIGINT NOT NULL,
  rolled_up_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (tenant_id, metric_name, month)
);
```

### 04 — GW+EVT (from docs/04-gateway-events.md §9)

```sql
CREATE TABLE outbox (
  event_id      ULID PRIMARY KEY,
  topic         TEXT NOT NULL,              -- 'account','bridge','payout',...
  payload       JSONB NOT NULL,             -- full envelope
  tenant_id     ULID NOT NULL,
  entity_id     TEXT NOT NULL,              -- routing key (ordering lane)
  correlation_id ULID,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  published_at  TIMESTAMPTZ,
  publish_attempt INT NOT NULL DEFAULT 0
);
CREATE INDEX idx_outbox_unpublished ON outbox(id) WHERE published_at IS NULL;

CREATE TABLE events (
  event_id      ULID,
  seq           BIGINT GENERATED ALWAYS AS IDENTITY,   -- global append order, assigned by the
                                                       -- INSERT (the relay is the single writer;
                                                       -- NO Redis counter in the durable path —
                                                       -- the D27 lesson, docs/48); V2 CON replay
                                                       -- addresses seq ranges
  topic         TEXT NOT NULL,
  tenant_id     ULID NOT NULL,
  entity_id     TEXT NOT NULL,
  type          TEXT NOT NULL,
  version       INT NOT NULL,
  occurred_at   TIMESTAMPTZ NOT NULL,
  correlation_id ULID,
  payload       JSONB NOT NULL,
  appended_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (topic, event_id)
) PARTITION BY RANGE (appended_at);
CREATE INDEX idx_events_tenant_type ON events(tenant_id, type, occurred_at);
CREATE INDEX idx_events_entity ON events(entity_id, occurred_at);

CREATE TABLE consumer_state (
  consumer      TEXT NOT NULL,
  event_id      ULID NOT NULL,
  status        TEXT NOT NULL DEFAULT 'processing',
  attempts      INT NOT NULL DEFAULT 1,
  last_error    TEXT,
  processed_at  TIMESTAMPTZ,
  PRIMARY KEY (consumer, event_id)
);

CREATE TABLE provider_events (           -- ingress idempotency (EVT-10)
  provider      TEXT NOT NULL,
  provider_event_id TEXT NOT NULL,
  tenant_id     ULID,
  payload_hash  TEXT NOT NULL,
  status        TEXT NOT NULL DEFAULT 'processed',
  received_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (provider, provider_event_id)
);

CREATE TABLE tenant_webhooks (           -- V2
  id            ULID PRIMARY KEY,
  tenant_id     ULID NOT NULL REFERENCES tenants(id),
  url           TEXT NOT NULL,
  events        TEXT[] NOT NULL,         -- filters, e.g. {'payout.*','account.*'}
  secret_enc    TEXT NOT NULL,           -- field-encrypted
  secret_ver    INT NOT NULL DEFAULT 1,
  active        BOOLEAN NOT NULL DEFAULT true,
  retry_policy  JSONB NOT NULL DEFAULT '{"max_retries":8,"max_backoff_s":3600}',
  disabled_reason TEXT,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 05 — LED/AUD (from docs/05-ledger-audit.md §9)

```sql
CREATE FUNCTION trg_entry_balance() RETURNS trigger AS $$
DECLARE
  eid ULID := COALESCE(NEW.entry_id, OLD.entry_id);
  unbalanced int; mixed int;
BEGIN
  SELECT COALESCE(SUM(debit_cents),0) - COALESCE(SUM(credit_cents),0),
         COUNT(DISTINCT currency)
    INTO unbalanced, mixed
    FROM journal_line WHERE entry_id = eid;
  IF unbalanced <> 0 OR mixed > 1 THEN
    RAISE EXCEPTION 'journal entry % is unbalanced or mixed-currency', eid;
  END IF;
  RETURN NULL;  -- AFTER trigger
END $$ LANGUAGE plpgsql;
CREATE CONSTRAINT TRIGGER trg_lines_balance AFTER INSERT OR UPDATE OR DELETE ON journal_line
  DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION trg_entry_balance();
-- Row-level + deferred = evaluated per touched entry at COMMIT: lines inserted after
-- the entry row are all present when the check runs; statement-level shortcuts are
-- what broke the earlier sketch (an AFTER INSERT trigger on journal_entry fires
-- before any line exists — finding F1, docs/48).
-- One currency per entry (§3.2 rule 4) rides the same check (F6).
-- The app role also gets INSERT-only (§9): corrections are reversal entries, never edits.
```

```sql
CREATE TABLE accounts (
  id         ULID PRIMARY KEY,
  tenant_id  ULID REFERENCES tenants(id),      -- NULL = platform-level
  code       TEXT NOT NULL,
  name       TEXT NOT NULL,
  type       TEXT NOT NULL CHECK (type IN ('asset','liability','equity','revenue','expense')),
  currency   CHAR(3) NOT NULL DEFAULT 'USD',
  is_system  BOOLEAN NOT NULL DEFAULT true,
  closed_at  TIMESTAMPTZ,
  UNIQUE (COALESCE(tenant_id,'00000000-0000-0000-0000-000000000000'::ulid_placeholder), code)
);  -- in practice: UNIQUE (tenant_id, code) with a platform sentinel row

CREATE TABLE journal_entry (
  id               ULID PRIMARY KEY,
  tenant_id        ULID NOT NULL,
  idempotency_key  TEXT NOT NULL UNIQUE,
  reason_code      TEXT NOT NULL,
  ref_type         TEXT, ref_id TEXT,
  description      TEXT,
  reverses_entry_id ULID REFERENCES journal_entry(id),
  prev_entry_hash  TEXT,                        -- V2 hash chain
  posted_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  posted_by        ULID                         -- identity or system sentinel
);
CREATE INDEX idx_jentry_tenant_time ON journal_entry(tenant_id, posted_at DESC);
CREATE INDEX idx_jentry_ref ON journal_entry(ref_type, ref_id);

CREATE TABLE journal_line (
  id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  entry_id     ULID NOT NULL REFERENCES journal_entry(id) ON DELETE RESTRICT,
  account_id   ULID NOT NULL REFERENCES accounts(id),
  debit_cents  BIGINT NOT NULL DEFAULT 0 CHECK (debit_cents >= 0),
  credit_cents BIGINT NOT NULL DEFAULT 0 CHECK (credit_cents >= 0),
  currency     CHAR(3) NOT NULL DEFAULT 'USD',
  memo         TEXT,
  CHECK (debit_cents = 0 OR credit_cents = 0)   -- one side only
);
CREATE INDEX idx_jline_account_time ON journal_line(account_id, entry_id);
-- + balance-check trigger (§3.2). App role: INSERT only on both tables.

CREATE TABLE audit_events (
  id            BIGINT GENERATED ALWAYS AS IDENTITY,
  tenant_id     ULID,                             -- NULL = platform-level
  actor_id      ULID,
  actor_kind    TEXT NOT NULL CHECK (actor_kind IN ('user','service','api_key','system')),
  actor_role    TEXT,
  action        TEXT NOT NULL,                    -- 'payout.approved' style
  resource_type TEXT, resource_id TEXT,
  status        TEXT NOT NULL CHECK (status IN ('success','failure','denied')),
  before        JSONB, after JSONB,               -- redacted at write (AUD-23 rules)
  ip            INET, user_agent TEXT,
  correlation_id ULID,
  request_id    TEXT,
  geo           JSONB,
  tier          TEXT NOT NULL DEFAULT 'standard' CHECK (tier IN ('standard','sensitive','critical')),
  prev_hash     TEXT, entry_hash TEXT,            -- V2 hash chain; `seq BIGINT`
                                                  -- (per-tenant monotonic) joins at chain
                                                  -- init (AUD-14), backfilled in id order —
                                                  -- decision D27, docs/48: V1 carries no seq,
                                                  -- so the fail-closed audit write is one
                                                  -- INSERT with no Redis dependency
  legal_hold    BOOLEAN NOT NULL DEFAULT false,   -- V2
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (id, created_at)                    -- partitioned tables must carry the
                                                  -- partition key in every unique/PK
                                                  -- constraint (finding F2, docs/48)
) PARTITION BY RANGE (created_at);
CREATE INDEX idx_audit_tenant_time ON audit_events(tenant_id, created_at DESC);
CREATE INDEX idx_audit_actor ON audit_events(tenant_id, actor_id, created_at DESC);
CREATE INDEX idx_audit_action ON audit_events(tenant_id, action, created_at DESC);
CREATE INDEX idx_audit_resource ON audit_events(resource_type, resource_id, created_at DESC);
-- Immutability (docs/32 convention, 28 §3.3): BEFORE DELETE/UPDATE triggers raise,
-- and the app role holds INSERT + SELECT only — the DDL the convention cites:
CREATE FUNCTION trg_ledger_no_mutation() RETURNS trigger AS $$
BEGIN RAISE EXCEPTION '% on % is not permitted', TG_OP, TG_TABLE_NAME; END
$$ LANGUAGE plpgsql;
CREATE TRIGGER no_mutate_journal  BEFORE UPDATE OR DELETE ON journal_entry  FOR EACH STATEMENT EXECUTE FUNCTION trg_ledger_no_mutation();
CREATE TRIGGER no_mutate_jline    BEFORE UPDATE OR DELETE ON journal_line    FOR EACH STATEMENT EXECUTE FUNCTION trg_ledger_no_mutation();
CREATE TRIGGER no_mutate_audit    BEFORE UPDATE OR DELETE ON audit_events    FOR EACH STATEMENT EXECUTE FUNCTION trg_ledger_no_mutation();

-- RLS (D16 model): journal_entry, journal_line and the tenant rows of audit_events
-- are tenant-owned — ENABLE/FORCE ROW LEVEL SECURITY on app.tenant_id (fail-closed),
-- written by the appliers with per-message context (decision W). Rows with
-- tenant_id IS NULL (platform CoA accounts, platform audit rows) are guard-only and
-- reachable through the app_platform services (audit-applier, CON read models) —
-- the same named-exemption model as every other module (docs/44 §5, docs/47 §7).
```

### 06 — OPS (from docs/06-devops-deployment.md §9)

```sql
CREATE TABLE backups (
  id           ULID PRIMARY KEY,
  kind         TEXT NOT NULL,          -- wal | base | r2_manifest
  taken_at     TIMESTAMPTZ NOT NULL,
  size_bytes   BIGINT NOT NULL,
  checksum     TEXT NOT NULL,
  verified_at  TIMESTAMPTZ,            -- weekly checksum verify (§5)
  drill_report JSONB                   -- monthly restore drill (OPS-38)
);
CREATE INDEX idx_backups_kind_taken ON backups(kind, taken_at DESC);

CREATE TABLE incidents (
  id              ULID PRIMARY KEY,
  severity        TEXT NOT NULL,       -- P1 | P2 | P3 (§5 ladder)
  title           TEXT NOT NULL,
  started_at      TIMESTAMPTZ NOT NULL,
  resolved_at     TIMESTAMPTZ,
  post_mortem_url TEXT                 -- ops/incidents/ (P1/P2 ≤ 48 h)
);

CREATE TABLE deploys (
  id          ULID PRIMARY KEY,
  env         TEXT NOT NULL,           -- staging | prod
  sha         TEXT NOT NULL,           -- immutable GHCR tag
  started_at  TIMESTAMPTZ NOT NULL,
  finished_at TIMESTAMPTZ,
  status      TEXT NOT NULL,           -- promoted | deployed | rolled_back | failed
  actor       TEXT NOT NULL
);
```

### 07 — LCC (from docs/07-account-lifecycle.md §9)

```sql
CREATE TABLE accounts (
  id                  ULID PRIMARY KEY,
  tenant_id           ULID NOT NULL REFERENCES tenants(id),
  identity_id         ULID NOT NULL REFERENCES identities(id),   -- the trader
  kind                TEXT NOT NULL CHECK (kind IN ('challenge','funded')),
  state               TEXT NOT NULL DEFAULT 'pending_payment',
  state_version       BIGINT NOT NULL DEFAULT 0,      -- optimistic lock
  phase               SMALLINT NOT NULL DEFAULT 1,
  phase_history       JSONB NOT NULL DEFAULT '[]',    -- V2 lineage
  program_id          ULID NOT NULL,                  -- challenge template (CHK/LCC catalog)
  program_name        TEXT NOT NULL,
  size_cents          BIGINT NOT NULL,
  currency            CHAR(3) NOT NULL DEFAULT 'USD',
  order_id            ULID UNIQUE,                    -- CHK order
  terms_snapshot      JSONB NOT NULL,                 -- frozen at purchase
  funded_terms_snapshot JSONB,                        -- frozen at funding
  broker_account_id   ULID,                           -- BRG.broker_accounts id (1:1)
  broker_status       TEXT,                           -- last broker-side state (sync)
  paused_at           TIMESTAMPTZ, resumed_at TIMESTAMPTZ,
  trading_time_left_s BIGINT,                         -- clock (§3.3)
  started_at          TIMESTAMPTZ,
  expires_at          TIMESTAMPTZ,
  failed_reason       TEXT,                           -- 'breach:{rule}' | 'expired'
  failed_at           TIMESTAMPTZ,
  closed_at           TIMESTAMPTZ, archived_at TIMESTAMPTZ,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_accounts_tenant_state ON accounts(tenant_id, state);
CREATE INDEX idx_accounts_identity ON accounts(tenant_id, identity_id, state);
CREATE INDEX idx_accounts_expires ON accounts(expires_at) WHERE state IN ('active','funded');

CREATE TABLE account_state_history (
  id            ULID PRIMARY KEY,
  account_id    ULID NOT NULL REFERENCES accounts(id),
  tenant_id     ULID NOT NULL,
  from_state    TEXT, to_state TEXT NOT NULL,
  event         TEXT NOT NULL,
  actor_kind    TEXT NOT NULL, actor_id ULID,
  detail        JSONB,                               -- e.g. breach rule, reason
  correlation_id ULID,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_acchist_account ON account_state_history(account_id, created_at);
-- (append-only; app role INSERT-only like audit)

CREATE TABLE account_commands (              -- LCC → BRG enforcement/provision commands
  id            ULID PRIMARY KEY,
  account_id    ULID NOT NULL,
  tenant_id     ULID NOT NULL,
  type          TEXT NOT NULL,   -- provision_account | disable_trading | close_positions
                                     -- | enable_trading | archive_broker_account
  idempotency_key TEXT NOT NULL UNIQUE,
  payload       JSONB NOT NULL,
  status        TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','executed','failed','dead')),
  attempts      INT NOT NULL DEFAULT 0,
  result        JSONB,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(), executed_at TIMESTAMPTZ
);
CREATE INDEX idx_acmcmd_pending ON account_commands(status, created_at) WHERE status IN ('pending','failed');
```

### 08 — BRG (from docs/08-trading-bridge.md §9)

```sql
CREATE TABLE broker_groups (
  id            ULID PRIMARY KEY,
  tenant_id     ULID NOT NULL REFERENCES tenants(id),
  name          TEXT NOT NULL,
  platform      TEXT NOT NULL DEFAULT 'mt5',
  server_id     TEXT NOT NULL,              -- MetaApi server identifier
  timezone      TEXT NOT NULL,              -- day-boundary authority (ADR-12)
  poll_interval_s INT NOT NULL DEFAULT 60,
  state         TEXT NOT NULL DEFAULT 'active' CHECK (state IN ('active','degraded','disabled')),
  UNIQUE (tenant_id, name)
);

CREATE TABLE broker_accounts (
  id                 ULID PRIMARY KEY,
  tenant_id          ULID NOT NULL,
  account_id         ULID NOT NULL REFERENCES accounts(id),   -- LCC 1:1
  login              TEXT NOT NULL,                           -- MT5 login
  server_id          TEXT NOT NULL,
  group_id           ULID REFERENCES broker_groups(id),
  state              TEXT NOT NULL DEFAULT 'creating',
                     CHECK (state IN ('creating','active','disabled','archived')),
  credentials_enc    JSONB,                -- {trading, investor} AES-256-GCM (BRG-44)
  cred_key_version   INT NOT NULL DEFAULT 1,
  leverage           TEXT,
  last_equity_cents  BIGINT, last_balance_cents BIGINT,
  last_margin_cents  BIGINT, last_free_margin_cents BIGINT,
  last_deal_ticket   BIGINT NOT NULL DEFAULT 0,
  last_synced_at     TIMESTAMPTZ,
  server_time        TIMESTAMPTZ,          -- last broker-attested time
  fail_streak        INT NOT NULL DEFAULT 0,
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  archived_at        TIMESTAMPTZ,
  UNIQUE (login)
);
CREATE INDEX idx_bacc_tenant_state ON broker_accounts(tenant_id, state);
CREATE INDEX idx_bacc_sync ON broker_accounts(state, last_synced_at) WHERE state = 'active';

CREATE TABLE broker_positions (
  position_id   TEXT NOT NULL,             -- login-positionId canonical
  login         TEXT NOT NULL,
  tenant_id     ULID NOT NULL,
  symbol        TEXT NOT NULL,
  side          TEXT NOT NULL CHECK (side IN ('buy','sell')),
  lots          NUMERIC(10,2) NOT NULL,
  open_price    NUMERIC(18,8) NOT NULL,
  sl            NUMERIC(18,8), tp NUMERIC(18,8),
  opened_at     TIMESTAMPTZ NOT NULL,      -- broker time
  closed_at     TIMESTAMPTZ,
  profit_cents  BIGINT, swap_cents BIGINT, commission_cents BIGINT,
  PRIMARY KEY (position_id)
);
CREATE INDEX idx_bpos_open ON broker_positions(login) WHERE closed_at IS NULL;

CREATE TABLE broker_deals (
  deal_id       BIGINT NOT NULL,           -- MT5 deal ticket (per login)
  login         TEXT NOT NULL,
  tenant_id     ULID NOT NULL,
  position_id   TEXT,
  entry         TEXT NOT NULL,             -- in/out
  symbol        TEXT NOT NULL, side TEXT NOT NULL,
  lots          NUMERIC(10,2) NOT NULL,
  price         NUMERIC(18,8) NOT NULL,
  profit_cents  BIGINT, swap_cents BIGINT, commission_cents BIGINT,
  deal_time     TIMESTAMPTZ NOT NULL,      -- broker time
  received_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (login, deal_id)
) PARTITION BY RANGE (received_at);
-- monthly partitions (high-volume table; same pattern as events)

CREATE TABLE account_snapshots (              -- §3.3: 1 row/account/min, 14-day rolling (D35)
  account_id      ULID NOT NULL,
  bucket_ts       TIMESTAMPTZ NOT NULL,       -- minute bucket (UTC)
  tenant_id       ULID NOT NULL,
  login           TEXT NOT NULL,
  equity_cents    BIGINT NOT NULL,
  balance_cents   BIGINT NOT NULL,
  margin_cents    BIGINT,
  free_margin_cents BIGINT,
  broker_time     TIMESTAMPTZ,                -- broker-attested time of the tick
  received_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (account_id, bucket_ts)
) PARTITION BY RANGE (bucket_ts);
-- daily partitions; retention = 14-day rolling (partition DROP; BRG job) with the
-- daily rollup exported to the ANA read model first (docs/19). PAY eligibility and
-- TD intraday equity curves read here (BRG-09 refreshes the latest row on demand).

CREATE TABLE broker_executions (
  id            ULID PRIMARY KEY,
  command_id    ULID NOT NULL,             -- LCC account_commands id
  login         TEXT NOT NULL,
  action        TEXT NOT NULL,
  attempt       INT NOT NULL,
  request_hash  TEXT,                      -- idempotency evidence
  status        TEXT NOT NULL,             -- sent|confirmed|failed|dead
  provider_resp JSONB,                     -- redacted
  broker_time   TIMESTAMPTZ,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_bexec_cmd ON broker_executions(command_id, attempt);
```

### 09 — EVL (from docs/09-evaluation-engine.md §9)

```sql
CREATE TABLE rule_packs (
  id            ULID PRIMARY KEY,
  tenant_id     ULID NOT NULL,
  name          TEXT NOT NULL,
  version       INT NOT NULL,
  status        TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','active','superseded')),
  rules         JSONB NOT NULL,             -- validated vs contracts schema
  effective_from TIMESTAMPTZ,
  change_reason TEXT,
  created_by    ULID,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, name, version)
);

CREATE TABLE evaluations (                     -- "evaluated" record (EVL-49)
  id            ULID PRIMARY KEY,
  account_id    ULID NOT NULL,
  tenant_id     ULID NOT NULL,
  tick_event_id ULID NOT NULL,                -- → events.event_id (observed ref)
  input_hash    TEXT NOT NULL,
  rule_pack_id  ULID NOT NULL, rule_pack_version INT NOT NULL,
  status        TEXT NOT NULL CHECK (status IN ('ok','breach','target_hit','target_hit_pending','gap_flagged')),
  rule_id       TEXT,
  detail        JSONB NOT NULL,               -- evidence: metrics at decision time
  state_version BIGINT NOT NULL,              -- EvalState version used
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_evals_account ON evaluations(account_id, created_at DESC);
CREATE INDEX idx_evals_breach ON evaluations(tenant_id, status, created_at) WHERE status IN ('breach','target_hit');

CREATE TABLE evaluation_state (                -- "evaluated" counters (single writer)
  account_id            ULID PRIMARY KEY,
  tenant_id             ULID NOT NULL,
  rule_pack_id          ULID NOT NULL, rule_pack_version INT NOT NULL,
  initial_balance_cents BIGINT NOT NULL,
  day_key               DATE NOT NULL,
  day_start_equity_cents BIGINT NOT NULL,
  daily_loss_max_cents  BIGINT NOT NULL DEFAULT 0,
  high_water_equity_cents BIGINT NOT NULL,     -- EVL-29
  max_total_loss_used_cents BIGINT NOT NULL DEFAULT 0,
  profit_cents          BIGINT NOT NULL DEFAULT 0,
  trading_days          INT NOT NULL DEFAULT 0,
  calendar_days         INT NOT NULL DEFAULT 0,
  started_at            TIMESTAMPTZ NOT NULL,
  daily_pnls            JSONB NOT NULL DEFAULT '[]',
  target_reached_at     TIMESTAMPTZ,
  target_hit_pending    BOOLEAN NOT NULL DEFAULT false,
  breach_rule_id        TEXT, breach_at TIMESTAMPTZ,
  version               BIGINT NOT NULL DEFAULT 0
);

CREATE TABLE evaluation_overrides (
  id            ULID PRIMARY KEY,
  account_id    ULID NOT NULL,
  tenant_id     ULID NOT NULL,
  verdict_id    ULID NOT NULL REFERENCES evaluations(id),
  kind          TEXT NOT NULL CHECK (kind IN ('clear_breach','manual_run','emergency')),
  reason        TEXT NOT NULL,
  actor_id      ULID NOT NULL,
  correlation_id ULID,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 10 — RSK (from docs/10-risk-management.md §9)

```sql
CREATE TABLE risk_signal_kinds (             -- kind registry (data, not code)
  kind        TEXT PRIMARY KEY,
  label       TEXT NOT NULL,
  base_score  INT NOT NULL,
  severity_default TEXT NOT NULL,
  enabled     BOOLEAN NOT NULL DEFAULT false  -- V1: only 'breach','manual'
);

CREATE TABLE risk_signals (
  id          ULID PRIMARY KEY,
  tenant_id   ULID NOT NULL,
  kind        TEXT NOT NULL REFERENCES risk_signal_kinds(kind),
  detector_id TEXT,
  trader_id   ULID NOT NULL,
  account_id  ULID,
  severity    TEXT NOT NULL,
  score       INT NOT NULL,
  evidence    JSONB NOT NULL,               -- redacted at write
  dedup_key   TEXT NOT NULL,
  case_id     ULID,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  archived_at TIMESTAMPTZ
);
CREATE INDEX idx_rsig_tenant ON risk_signals(tenant_id, created_at DESC);
CREATE INDEX idx_rsig_dedup ON risk_signals(tenant_id, dedup_key, created_at DESC);

CREATE TABLE risk_cases (
  id            ULID PRIMARY KEY,
  tenant_id     ULID NOT NULL,
  kind          TEXT NOT NULL,              -- breach|manual|detector:{kind}|appeal
  status        TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','decided','reopened','closed')),
  severity      TEXT NOT NULL,
  trader_id     ULID NOT NULL,
  account_ids   ULID[],                     -- one open case per account (D71): transactional check under a per-trader advisory lock (§3.2)
  payout_hold   BOOLEAN NOT NULL DEFAULT false,  -- dormant in V1.0; the PAY-04 interlock reads it from V1.1 (D68)
  hold_until    TIMESTAMPTZ,                -- RSK-31 (V2 expiry)
  decision_note TEXT,
  actions       JSONB NOT NULL DEFAULT '[]',
  decided_by    ULID, decided_at TIMESTAMPTZ,
  opened_by     ULID,                       -- identity or 'system:evl'
  sla_due_at    TIMESTAMPTZ,                -- V2
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  closed_at     TIMESTAMPTZ
);
CREATE INDEX idx_rcase_tenant_status ON risk_cases(tenant_id, status, created_at DESC);
CREATE INDEX idx_rcase_trader ON risk_cases(tenant_id, trader_id, status);
```

### 11 — PAY (from docs/11-payout-system.md §9)

```sql
CREATE TABLE payout_methods (                 -- versioned (edit = new row)
  id            ULID PRIMARY KEY,
  tenant_id     ULID NOT NULL,
  identity_id   ULID NOT NULL,                -- trader
  kind          TEXT NOT NULL,                -- crypto_trc20|crypto_erc20|crypto_bep20|local:{p}
  details_enc   JSONB NOT NULL,               -- AES-256-GCM (wallet/account ref)
  key_version   INT NOT NULL DEFAULT 1,
  label         TEXT,                         -- "Main TRON wallet"
  is_default    BOOLEAN NOT NULL DEFAULT false,
  active        BOOLEAN NOT NULL DEFAULT true,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  deactivated_at TIMESTAMPTZ
);
CREATE INDEX idx_pmeth_trader ON payout_methods(tenant_id, identity_id, active);

CREATE TABLE payout_requests (
  id                ULID PRIMARY KEY,
  tenant_id         ULID NOT NULL,
  identity_id       ULID NOT NULL,
  account_id        ULID NOT NULL REFERENCES accounts(id),
  method_id         ULID NOT NULL REFERENCES payout_methods(id),
  method_version_at INT NOT NULL,             -- which method row version (disputes)
  requested_cents   BIGINT,                   -- NULL = everything available
  status            TEXT NOT NULL DEFAULT 'requested'
    CHECK (status IN ('requested','eligibility_checked','pending_approval','approved',
                      'processing','paid','failed','cancelled','rejected')),
    -- PAY-13's exact list (docs/52: 'settled'→'paid'; 'failed_final' is a V2
    -- terminal reason within 'failed'; holds are status_reason='on_hold' flags on
    -- 'approved' — never states, D32)
  status_reason     TEXT,
  -- frozen calc (PAY-02, §3.2)
  calc_snapshot     JSONB NOT NULL,           -- steps + inputs + snapshot versions
  gross_cents       BIGINT NOT NULL,
  trader_share_cents BIGINT NOT NULL,
  fee_cents         BIGINT NOT NULL,
  final_cents       BIGINT NOT NULL,
  currency          CHAR(3) NOT NULL DEFAULT 'USD',
  rail              TEXT NOT NULL,            -- nowpayments|match2pay|interkasa|manual
  -- approval
  approval_required BOOLEAN NOT NULL DEFAULT true,   -- V1: always; V2 toggle
  approved_by       ULID, approved_at TIMESTAMPTZ, approval_note TEXT,
  rejected_by       ULID, rejected_at TIMESTAMPTZ, reject_reason_code TEXT,
  -- execution
  external_ref      TEXT,                     -- provider ref
  executed_at       TIMESTAMPTZ, settled_at TIMESTAMPTZ, failed_at TIMESTAMPTZ,
  attempts          INT NOT NULL DEFAULT 0,
  -- ledger
  obligation_entry_id ULID, settlement_entry_id ULID,
  idempotency_key   TEXT NOT NULL UNIQUE,
  cancelled_by      ULID, cancelled_at TIMESTAMPTZ,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_pay_tenant_status ON payout_requests(tenant_id, status, created_at DESC);
CREATE INDEX idx_pay_account ON payout_requests(tenant_id, account_id, status);
CREATE INDEX idx_pay_identity ON payout_requests(tenant_id, identity_id, created_at DESC);

CREATE TABLE payout_executions (               -- PAY-12 append-only record
  id            ULID PRIMARY KEY,
  payout_id     ULID NOT NULL REFERENCES payout_requests(id),
  tenant_id     ULID NOT NULL,
  attempt       INT NOT NULL,
  action        TEXT NOT NULL,                -- send|webhook|retry|reconcile
  provider      TEXT NOT NULL,
  external_ref  TEXT,
  state         TEXT NOT NULL,                -- sent|confirmed|failed
  provider_resp JSONB,                        -- redacted
  at            TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_pexec_payout ON payout_executions(payout_id, attempt);
-- status history: reuse the AUD pattern (payout.status_changed events mirror to
-- audit_events; a lightweight payout_status_history table is added only if the
-- AUD mirror proves insufficient for queue UX — V1: events + audit suffice)
```

### 12 — CHK (from docs/12-checkout-billing.md §9)

```sql
CREATE TABLE checkout_sessions (              -- CHK-02/43/44 (D42: added — was dictionary-only)
  id              ULID PRIMARY KEY,
  tenant_id       ULID NOT NULL,
  identity_id     ULID NOT NULL,
  state           TEXT NOT NULL DEFAULT 'reserved'
    CHECK (state IN ('reserved','completed','expired','cancelled')),
  price_snapshot  JSONB NOT NULL,           -- package_id, rule_set_id, base_cents, currency
  coupon_code     TEXT,                     -- reserved (CHK-02); released on expire/cancel
  reservation_expires_at TIMESTAMPTZ NOT NULL,
  order_id        ULID,                     -- set on submit (the idempotent CHK-42 create)
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  completed_at    TIMESTAMPTZ, cancelled_at TIMESTAMPTZ
);
CREATE INDEX idx_csess_tenant ON checkout_sessions(tenant_id, identity_id, state);

CREATE TABLE orders (
  id              ULID PRIMARY KEY,
  tenant_id       ULID NOT NULL,
  identity_id     ULID NOT NULL,
  status          TEXT NOT NULL DEFAULT 'open'
    CHECK (status IN ('open','paid','provisioning','fulfilled',
                      'failed_provisioning','abandoned')),
  line_items      JSONB NOT NULL,            -- frozen: package_id, rule_set_id,
                                             -- base_cents, currency, fx_rate, total
  amount_cents    BIGINT NOT NULL,
  currency        CHAR(3) NOT NULL,
  intent_ids      ULID[],
  invoice_id      TEXT,                      -- DOC object key
  saga_id         TEXT,                      -- LCC provisioning saga (EVT-17)
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  paid_at         TIMESTAMPTZ, fulfilled_at TIMESTAMPTZ,
  closed_at       TIMESTAMPTZ
);
CREATE INDEX idx_ord_tenant ON orders(tenant_id, created_at DESC);
CREATE INDEX idx_ord_identity ON orders(tenant_id, identity_id, status);

CREATE TABLE payment_intents (
  id              ULID PRIMARY KEY,
  tenant_id       ULID NOT NULL,
  order_id        ULID NOT NULL REFERENCES orders(id),
  provider        TEXT NOT NULL,             -- match2pay|interkasa|nowpayments|wire
  method          TEXT NOT NULL,             -- card|local:{kind}|crypto:{chain}|wire
  amount_cents    BIGINT NOT NULL,
  currency        CHAR(3) NOT NULL,
  status          TEXT NOT NULL DEFAULT 'created'
    CHECK (status IN ('created','pending','captured','failed','expired')),
  provider_ref    TEXT,                      -- provider's transaction id
  fee_cents       BIGINT, fee_currency CHAR(3),   -- from webhook (recon-verified)
  capture_at      TIMESTAMPTZ, expires_at TIMESTAMPTZ NOT NULL,
  idempotency_key TEXT UNIQUE,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_pint_tenant_status ON payment_intents(tenant_id, status, created_at DESC);
CREATE INDEX idx_pint_provider_ref ON payment_intents(provider, provider_ref);

CREATE TABLE refunds (
  id              ULID PRIMARY KEY,
  tenant_id       ULID NOT NULL,
  intent_id       ULID NOT NULL REFERENCES payment_intents(id),
  order_id        ULID NOT NULL,
  kind            TEXT NOT NULL,             -- trader|manual|auto_breach|chargeback
  status          TEXT NOT NULL DEFAULT 'refund_requested'
    CHECK (status IN ('refund_requested','provider_pending','refunded',
                      'failed','cancelled')),
  amount_cents    BIGINT NOT NULL,
  currency        CHAR(3) NOT NULL,
  reason          TEXT,
  provider_ref    TEXT,
  requested_by    ULID,                      -- identity (trader) or staff or 'system'
  provider_at     TIMESTAMPTZ, settled_at TIMESTAMPTZ,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_rfd_tenant ON refunds(tenant_id, status, created_at DESC);
CREATE INDEX idx_rfd_intent ON refunds(intent_id);

-- provider report files: R2 (reports/{provider}/{date}.csv) + a small
-- recon_runs table (provider, date, file_key, matched, exceptions[]) on V2
```

### 13 — KYC (from docs/13-kyc.md §9)

```sql
CREATE TABLE kyc_sessions (
  id             ULID PRIMARY KEY,
  tenant_id      ULID NOT NULL,
  identity_id    ULID NOT NULL,
  level          TEXT NOT NULL CHECK (level IN ('l1','l2')),   -- level machinery is V2; V1 uses one flow (docs/53)
  is_manual_review BOOLEAN NOT NULL DEFAULT false,  -- queue flag, NOT a state (D43, KYC-11/12)
  state          TEXT NOT NULL DEFAULT 'not_started'
    CHECK (state IN ('not_started','pending','in_review','approved',
                     'rejected','needs_resubmission','expired')),
    -- KYC-06's exact seven states (docs/53: the DDL's invented in_session/
    -- manual_review/verified/re_verification_required removed; manual review
    -- = in_review + is_manual_review)
  provider       TEXT NOT NULL DEFAULT 'veriff',
  provider_case_id TEXT,                     -- Veriff object id
  country_declared CHAR(2), country_ip CHAR(2),
  dob           DATE,                        -- field-encrypted at column level
  identity_data JSONB,                       -- field-encrypted (name, doc, score)
  key_version   INT NOT NULL DEFAULT 1,
  reject_reason_class TEXT,                  -- what the trader sees
  reject_reason_detail TEXT,                 -- staff-only
  decided_by    ULID, decided_at TIMESTAMPTZ,
  override      BOOLEAN NOT NULL DEFAULT false,   -- V2 KYC-18
  session_url_expires_at TIMESTAMPTZ,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_kyc_tenant_identity ON kyc_sessions(tenant_id, identity_id, level, created_at DESC);
CREATE INDEX idx_kyc_queue ON kyc_sessions(tenant_id, state) WHERE state = 'in_review' AND is_manual_review;

CREATE TABLE kyc_documents (
  id         ULID PRIMARY KEY,
  tenant_id  ULID NOT NULL,
  session_id ULID NOT NULL REFERENCES kyc_sessions(id),
  kind       TEXT NOT NULL,                  -- id_front|id_back|selfie|proof_of_address|manual:{n}
  r2_key     TEXT NOT NULL,                  -- kyc/{tenant}/{session}/{n}
  bytes      BIGINT NOT NULL,
  uploaded_by TEXT NOT NULL,                 -- 'trader' | 'staff'
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_kycdocs_session ON kyc_documents(session_id);

-- no separate verified-record table V1: the latest verified kyc_sessions row
-- per (identity, level) IS the record; history = the other rows (KYC-09).
-- V2 adds kyc_consent (KYC-27) + kyc_reverification triggers (KYC-21).
```

### 14 — NOT (from docs/14-notifications.md §9)

```sql
CREATE TABLE notification_templates (
  id            ULID PRIMARY KEY,
  tenant_id     ULID,                          -- NULL = platform default
  key           TEXT NOT NULL,                 -- 'payout_settled'
  version       INT NOT NULL DEFAULT 1,
  subject       TEXT NOT NULL,
  body_html     TEXT NOT NULL,
  body_text     TEXT NOT NULL,
  branding      JSONB,                         -- V2: logo/color overrides (TEN-05/06)
  active        BOOLEAN NOT NULL DEFAULT true,
  created_by    ULID, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, key, version)
);

CREATE TABLE notification_mappings (
  id            ULID PRIMARY KEY,
  tenant_id     ULID,                          -- NULL = platform mapping
  event_type    TEXT NOT NULL,                 -- 'payout.settled'
  channels      TEXT[] NOT NULL DEFAULT '{email}',
  template_key  TEXT NOT NULL,
  priority      TEXT NOT NULL DEFAULT 'normal'
    CHECK (priority IN ('critical','high','normal','low')),
  vars_selector JSONB NOT NULL,                -- whitelisted event fields → vars
  enabled       BOOLEAN NOT NULL DEFAULT true,
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, event_type, channels)
);

CREATE TABLE notifications (
  id            ULID PRIMARY KEY,
  tenant_id     ULID NOT NULL,
  event_ref     TEXT,                          -- stream entry id (trace)
  kind          TEXT NOT NULL,
  recipient_identity ULID,
  recipient_role  TEXT,                        -- staff role target
  channel       TEXT NOT NULL,
  template      TEXT NOT NULL,                 -- 'key@version'
  vars          JSONB NOT NULL,
  state         TEXT NOT NULL DEFAULT 'pending'
    CHECK (state IN ('pending','sent','delivered','failed','dlq','suppressed')),
  suppress_reason TEXT,                        -- dedupe|bounce|complaint|prefs|quiet
  provider_ref  TEXT,
  attempts      INT NOT NULL DEFAULT 0,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  sent_at       TIMESTAMPTZ, delivered_at TIMESTAMPTZ
);
CREATE INDEX idx_not_tenant_state ON notifications(tenant_id, state, created_at DESC);
CREATE INDEX idx_not_identity ON notifications(recipient_identity, created_at DESC);
-- partitions by month from V2 if > 10M rows (delivery logs NOT-12 = same table)

CREATE TABLE notification_suppressions (        -- V2 NOT-26/16
  id            ULID PRIMARY KEY,
  tenant_id     ULID NOT NULL,
  identity_id   ULID NOT NULL,
  channel       TEXT NOT NULL,
  reason        TEXT NOT NULL,                 -- bounce|complaint|unsub|manual
  until         TIMESTAMPTZ,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, identity_id, channel, reason)
);
```

### 15 — DOC (from docs/15-documents.md §9)

```sql
CREATE TABLE documents (
  id            ULID PRIMARY KEY,
  tenant_id     ULID NOT NULL,
  type          TEXT NOT NULL,               -- challenge_agreement|funded_certificate|…
  ref_kind      TEXT NOT NULL,               -- account|order|payout
  ref_id        ULID NOT NULL,
  identity_id   ULID,                        -- owner (trader docs)
  version       INT NOT NULL DEFAULT 1,
  state         TEXT NOT NULL DEFAULT 'pending'
    CHECK (state IN ('pending','generated','failed')),
  r2_key        TEXT,                        -- documents/{tenant}/{type}/{id}-v{n}.pdf
  vars          JSONB,                       -- rendered vars (PII-safe, for audit/redraw)
  cert_hash     TEXT,                        -- V2: verification hash (certs only)
  fail_reason   TEXT,
  attempts      INT NOT NULL DEFAULT 0,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  generated_at  TIMESTAMPTZ,
  UNIQUE (ref_kind, ref_id, type, version)
);
CREATE INDEX idx_doc_tenant_identity ON documents(tenant_id, identity_id, created_at DESC);
CREATE INDEX idx_doc_ref ON documents(ref_kind, ref_id, type);
CREATE INDEX idx_doc_cert ON documents(cert_hash) WHERE cert_hash IS NOT NULL;

CREATE TABLE document_versions (               -- regeneration history (V2)
  id            ULID PRIMARY KEY,
  document_id   ULID NOT NULL REFERENCES documents(id),
  version       INT NOT NULL,
  r2_key        TEXT NOT NULL,
  reason        TEXT,
  created_by    ULID,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (document_id, version)
);

CREATE TABLE document_triggers (               -- event → doc type mapping (data)
  id            ULID PRIMARY KEY,
  event_type    TEXT NOT NULL,
  doc_type      TEXT NOT NULL,
  enabled       BOOLEAN NOT NULL DEFAULT true,
  UNIQUE (event_type, doc_type)
);
```

### 16 — TD (from docs/16-trader-dashboard.md §9)

_(no DDL in the module doc — the module is stateless or reuses another)_

### 17 — ADM (from docs/17-admin-panel.md §9)

_(no DDL in the module doc — the module is stateless or reuses another)_

### 18 — SUP (from docs/18-support.md §9)

```sql
CREATE TABLE ticket_categories (          -- registry (data; V2 tenant-editable)
  id          ULID PRIMARY KEY,
  tenant_id   ULID,                        -- NULL = platform default
  key         TEXT NOT NULL,               -- 'account'|'payment'|…
  label       TEXT NOT NULL,
  sla_hours   INT NOT NULL DEFAULT 24,     -- V2: per priority
  enabled     BOOLEAN NOT NULL DEFAULT true,
  UNIQUE (tenant_id, key)
);

CREATE TABLE tickets (
  id                ULID PRIMARY KEY,
  tenant_id         ULID NOT NULL,
  category          TEXT NOT NULL,
  status            TEXT NOT NULL DEFAULT 'open'
    CHECK (status IN ('open','in_progress','resolved','closed','cancelled')),
  priority          TEXT NOT NULL DEFAULT 'normal'
    CHECK (priority IN ('low','normal','high','critical')),
  subject           TEXT NOT NULL,
  identity_id       ULID NOT NULL,         -- the trader
  account_id        ULID,
  object_refs       JSONB NOT NULL DEFAULT '{}',
  created_by        TEXT NOT NULL,         -- 'trader' | 'staff'
  assignee_id       ULID,                  -- V2
  first_response_at TIMESTAMPTZ,
  sla_due_at        TIMESTAMPTZ NOT NULL,
  resolved_at       TIMESTAMPTZ, closed_at TIMESTAMPTZ,
  satisfaction      SMALLINT, satisfaction_comment TEXT,   -- V2
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_tick_tenant_status ON tickets(tenant_id, status, created_at DESC);
CREATE INDEX idx_tick_identity ON tickets(tenant_id, identity_id, created_at DESC);
CREATE INDEX idx_tick_account ON tickets(account_id) WHERE account_id IS NOT NULL;

CREATE TABLE ticket_messages (
  id            ULID PRIMARY KEY,
  tenant_id     ULID NOT NULL,
  ticket_id     ULID NOT NULL REFERENCES tickets(id),
  kind          TEXT NOT NULL CHECK (kind IN ('trader','staff','internal','system')),
  body          TEXT NOT NULL,
  attachment_refs JSONB NOT NULL DEFAULT '[]',
  author_id     ULID,                      -- NULL for system
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_tmsg_ticket ON ticket_messages(ticket_id, created_at);

CREATE TABLE ticket_attachments (
  id          ULID PRIMARY KEY,
  tenant_id   ULID NOT NULL,
  r2_key      TEXT NOT NULL,               -- support/{tenant}/{ticket}/{n}
  bytes       BIGINT NOT NULL,
  content_type TEXT NOT NULL,
  scan_state  TEXT NOT NULL DEFAULT 'unscanned'   -- V2: scanned|infected
    CHECK (scan_state IN ('unscanned','scanned','infected')),
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 19 — ANA (from docs/19-analytics.md §9)

```sql
CREATE TABLE equity_points (
  tenant_id   ULID NOT NULL,
  account_id  ULID NOT NULL,
  as_of       TIMESTAMPTZ NOT NULL,          -- 1-min bucket
  equity_cents BIGINT NOT NULL,
  balance_cents BIGINT, hwm_cents BIGINT,
  tick_at     TIMESTAMPTZ NOT NULL,
  PRIMARY KEY (tenant_id, account_id, as_of)
);
CREATE INDEX idx_eqp_range ON equity_points(tenant_id, as_of DESC);
-- monthly partitions (created by migration; 13-mo retention job V2)

CREATE TABLE accounts_ro (
  tenant_id   ULID PRIMARY KEY (tenant_id, account_id),
  account_id  ULID NOT NULL,
  identity_id ULID, package TEXT, state TEXT, phase TEXT,
  opened_at TIMESTAMPTZ, funded_at TIMESTAMPTZ, breached_at TIMESTAMPTZ,
  broker_account TEXT, equity_cents BIGINT, state_changed_at TIMESTAMPTZ
);
CREATE INDEX idx_accts_ro_state ON accounts_ro(tenant_id, state);

CREATE TABLE traders_ro (
  tenant_id   ULID NOT NULL, identity_id ULID NOT NULL,
  name_masked TEXT, email_masked TEXT, country CHAR(2),
  kyc_l1_at TIMESTAMPTZ, kyc_l2_at TIMESTAMPTZ, created_at TIMESTAMPTZ,
  account_count INT, last_active_at TIMESTAMPTZ,
  PRIMARY KEY (tenant_id, identity_id)
);

CREATE TABLE payments_daily (
  tenant_id ULID NOT NULL, day DATE NOT NULL,
  intents INT, captured INT, gross_cents BIGINT, fee_cents BIGINT,
  refunds INT, refund_cents BIGINT,
  PRIMARY KEY (tenant_id, day)
);
CREATE TABLE payouts_daily (
  tenant_id ULID NOT NULL, day DATE NOT NULL,
  requested INT, approved INT, settled INT, settled_cents BIGINT,
  failed INT, approval_h_avg NUMERIC(6,2),
  PRIMARY KEY (tenant_id, day)
);

CREATE TABLE funnel_steps (
  tenant_id ULID NOT NULL, identity_id ULID NOT NULL,
  step TEXT NOT NULL, at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (tenant_id, identity_id, step, at)
);

CREATE TABLE risk_summary (
  tenant_id ULID NOT NULL, day DATE NOT NULL,
  open_cases INT, opened INT, decided INT, hold_cents_active BIGINT,
  PRIMARY KEY (tenant_id, day)
);

CREATE TABLE kpi_snapshots (
  tenant_id ULID NOT NULL, as_of TIMESTAMPTZ NOT NULL,
  payload JSONB NOT NULL,                     -- the §3.2 blocks
  PRIMARY KEY (tenant_id, as_of)
);
-- V2 adds: report_registry, report_runs, kpi_alerts (per §3.3–3.5)
```

### 20 — CRM (from docs/20-crm.md §9)

```sql
CREATE TABLE crm_segments (
  id          ULID PRIMARY KEY,
  tenant_id   ULID NOT NULL,
  name        TEXT NOT NULL,
  sql_template TEXT NOT NULL,               -- allowlisted tables only (review gate)
  cadence_min INT NOT NULL DEFAULT 15,
  enabled     BOOLEAN NOT NULL DEFAULT true,
  created_by  ULID, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, name)
);
CREATE TABLE crm_segment_members (           -- the snapshot (recomputed)
  tenant_id ULID NOT NULL, segment_id ULID NOT NULL,
  identity_id ULID NOT NULL,
  computed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (tenant_id, segment_id, identity_id)
);
CREATE INDEX idx_segmem_computed ON crm_segment_members(computed_at);

CREATE TABLE crm_campaigns (
  id          ULID PRIMARY KEY,
  tenant_id   ULID NOT NULL,
  name        TEXT NOT NULL,
  segment_id  ULID NOT NULL,
  snapshot_at TIMESTAMPTZ NOT NULL,          -- which membership version
  template    TEXT NOT NULL,                 -- NOT template key@version
  channels    TEXT[] NOT NULL DEFAULT '{email}',
  status      TEXT NOT NULL DEFAULT 'draft'
    CHECK (status IN ('draft','scheduled','sending','sent','cancelled')),
  sent_count  INT, created_by ULID,
  sent_at     TIMESTAMPTZ, created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE crm_consent (                   -- append-only history
  id          ULID PRIMARY KEY,
  tenant_id   ULID NOT NULL, identity_id ULID NOT NULL,
  purpose     TEXT NOT NULL,                 -- marketing_email|marketing_telegram|updates
  state       TEXT NOT NULL,                 -- granted|withdrawn
  source      TEXT NOT NULL,                 -- signup|prefs_page|unsubscribe|manual
  at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_crmconsent_current ON crm_consent(tenant_id, identity_id, purpose, at DESC);
-- tags/notes: identity_tags (identity_id, tag, created_by) + identity_notes
-- (identity_id, body, author) — both audit-mirrored; sequence state (V3):
-- sequence_runs (identity, sequence, step, state, updated_at)
```

### 21 — CON (from docs/21-console.md §9)

```sql
CREATE TABLE console_controls (                  -- control state (source of
  control     TEXT PRIMARY KEY,                  -- truth for what's armed)
  tenant_id   ULID,                              -- NULL = platform-wide
  state       TEXT NOT NULL DEFAULT 'disarmed'
    CHECK (state IN ('disarmed','pending_approval','active')),
  armed_by    ULID, approved_by ULID,
  armed_at    TIMESTAMPTZ, approved_at TIMESTAMPTZ,
  runbook     TEXT NOT NULL,                     -- the link shown in dialogs
  note        TEXT                               -- required on release
);
CREATE TABLE console_impersonations (            -- V2 audit table (AUD mirrors
  id          ULID PRIMARY KEY,                  -- it too)
  tenant_id   ULID NOT NULL, identity_id ULID NOT NULL,
  operator_id ULID NOT NULL,
  started_at  TIMESTAMPTZ NOT NULL, ends_at TIMESTAMPTZ NOT NULL,
  renewed     INT NOT NULL DEFAULT 0
);
CREATE TABLE console_announcements (             -- V2 CON-14
  id          ULID PRIMARY KEY,
  scope       TEXT NOT NULL,                     -- 'platform' | tenant_id
  title       TEXT NOT NULL, body TEXT NOT NULL,
  visible_from TIMESTAMPTZ, visible_to TIMESTAMPTZ,
  created_by  ULID, created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- everything else (tenants, sagas, entitlements, audit, jobs) is read from
-- TEN/OPS/AUD/ANA — the console renders, it doesn't store.
```

### 22 — BIL (from docs/22-billing.md §9)

```sql
-- V1+ (platform-owned):
CREATE TABLE metering_daily (
  tenant_id ULID NOT NULL, meter TEXT NOT NULL,
  day DATE NOT NULL, value BIGINT NOT NULL,
  source TEXT NOT NULL,                    -- 'ana_rollup'|'r2_report'|'gw_rollup'
  PRIMARY KEY (tenant_id, meter, day)
);
CREATE TABLE tenant_contracts (             -- BIL-16 contract-mode record
  id          ULID PRIMARY KEY,
  tenant_id   ULID NOT NULL,
  version     INT NOT NULL DEFAULT 1,       -- amended terms = new version
  plan_name   TEXT NOT NULL,
  base_monthly_cents BIGINT NOT NULL,
  currency    CHAR(3) NOT NULL,
  limits      JSONB NOT NULL,               -- the §3.2 shape
  pass_through_margin_bps JSONB NOT NULL,   -- per provider
  payment_terms TEXT NOT NULL,              -- 'net_30_wire' | …
  active_from DATE NOT NULL, active_to DATE,
  created_by  ULID, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, version)
);
CREATE TABLE platform_invoices (            -- all modes (V3: Lago refs)
  id          ULID PRIMARY KEY,
  tenant_id   ULID NOT NULL,
  mode        TEXT NOT NULL,                -- 'contract'|'lago'
  period_from DATE NOT NULL, period_to DATE NOT NULL,
  lines       JSONB NOT NULL,               -- §8 shape
  total_cents BIGINT NOT NULL, currency CHAR(3) NOT NULL,
  status      TEXT NOT NULL DEFAULT 'draft'
    CHECK (status IN ('draft','approved','issued','paid','past_due',
                      'written_off','credit_noted')),
  approved_by ULID, approved_at TIMESTAMPTZ,   -- BIL-21 (two-op in V3;
  paid_at     TIMESTAMPTZ, payment_ref TEXT,  -- 2FA in V2)
  lago_ref    TEXT,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_plinv_tenant ON platform_invoices(tenant_id, period_from DESC);
-- V3 adds: plans, plan_addons, subscriptions (Lago is the engine of
-- record; these rows cache the tenant-facing state for CON/portal reads)
```

### 23 — AFF (from docs/23-affiliates.md §9)

```sql
CREATE TABLE affiliates (
  id          ULID PRIMARY KEY,
  tenant_id   ULID,                          -- NULL = platform program
  identity_id ULID NOT NULL,                 -- the person (KYC L2 required)
  status      TEXT NOT NULL DEFAULT 'applied'
    CHECK (status IN ('applied','approved','active','suspended','terminated')),
  code        TEXT NOT NULL UNIQUE,          -- the ref code
  agreement_ref TEXT,                        -- DOC: signed agreement
  approved_by ULID, approved_at TIMESTAMPTZ,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE affiliate_rate_cards (
  id          ULID PRIMARY KEY,
  affiliate_id ULID NOT NULL,
  owner       TEXT NOT NULL DEFAULT 'platform',   -- platform | tenant:{id}
  challenge_bps INT NOT NULL,
  first_payouts_bonus JSONB,
  tier_multipliers JSONB NOT NULL DEFAULT '{}',
  caps        JSONB NOT NULL,
  effective_from TIMESTAMPTZ NOT NULL, effective_to TIMESTAMPTZ,
  created_by  ULID,
  UNIQUE (affiliate_id, effective_from)
);
CREATE TABLE identity_affiliation (           -- the attribution record
  tenant_id   ULID NOT NULL,
  identity_id ULID NOT NULL,
  affiliate_id ULID NOT NULL,
  method      TEXT NOT NULL,                  -- link|coupon
  attributed_at TIMESTAMPTZ NOT NULL,
  voided      BOOLEAN NOT NULL DEFAULT false, -- self-referral catch
  void_reason TEXT,
  PRIMARY KEY (tenant_id, identity_id)       -- one attribution, immutable
);
CREATE TABLE affiliate_accruals (
  id            ULID PRIMARY KEY,
  tenant_id     ULID NOT NULL,
  affiliate_id  ULID NOT NULL,
  identity_id   ULID NOT NULL,                -- the referred trader
  order_id      ULID,                          -- basis: purchase
  basis         TEXT NOT NULL,                -- purchase|payout_bonus
  card_version  ULID NOT NULL,
  rate_bps      INT NOT NULL,
  gross_cents   BIGINT NOT NULL,
  commission_cents BIGINT NOT NULL,
  status        TEXT NOT NULL DEFAULT 'accrued'
    CHECK (status IN ('accrued','settled','reversed','cancelled')),
  captured_at   TIMESTAMPTZ NOT NULL, settled_at TIMESTAMPTZ,
  reversal_ref  TEXT,                          -- the refund/chargeback id
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_affacc_affiliate ON affiliate_accruals(affiliate_id, status, captured_at DESC);
CREATE INDEX idx_affacc_order ON affiliate_accruals(order_id);
-- payouts: affiliate_payouts + affiliate_payout_executions (the PAY-12
-- pattern, §3.4); affiliate_methods (field-encrypted, PAY-pattern)
```

### 24 — CMS/CMP (from docs/24-cms-competitions.md §9)

```sql
CREATE TABLE site_pages (
  id            ULID PRIMARY KEY,
  tenant_id     ULID NOT NULL,
  slug          TEXT NOT NULL,
  title         TEXT NOT NULL,
  status        TEXT NOT NULL DEFAULT 'draft'
    CHECK (status IN ('draft','published','archived')),
  live_version  INT NOT NULL DEFAULT 1,
  nav_order     INT, is_legal BOOLEAN NOT NULL DEFAULT false,
  seo           JSONB NOT NULL DEFAULT '{}',
  publish_at    TIMESTAMPTZ,                  -- CMS-15
  published_at  TIMESTAMPTZ, published_by ULID,
  legal_review_note TEXT,                     -- required on is_legal publish
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, slug)
);
CREATE TABLE site_page_blocks (
  id          ULID PRIMARY KEY,
  page_id     ULID NOT NULL REFERENCES site_pages(id),
  version     INT NOT NULL,
  parent_id   ULID,
  block_type  TEXT NOT NULL,
  data        JSONB NOT NULL,                 -- schema-validated per type
  sort        INT NOT NULL DEFAULT 0,
  UNIQUE (page_id, version, id)
);
CREATE INDEX idx_siteblocks_live ON site_page_blocks(page_id, version);
CREATE TABLE site_media (
  id          ULID PRIMARY KEY,
  tenant_id   ULID NOT NULL,
  r2_key      TEXT NOT NULL,
  bytes       BIGINT NOT NULL, content_type TEXT NOT NULL,
  uploaded_by ULID, created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE site_leads (                      -- PII: field-encrypted name/email
  id          ULID PRIMARY KEY,
  tenant_id   ULID NOT NULL,
  form_id     ULID NOT NULL,
  data_enc    JSONB NOT NULL,
  ip_hash     TEXT,                           -- analytics-grade, not raw IP
  state       TEXT NOT NULL DEFAULT 'captured'
    CHECK (state IN ('captured','contacted','converted','stale')),
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_siteld_tenant ON site_leads(tenant_id, state, created_at DESC);
-- published_stats (tenant, key, value, source, updated_at, auto_refresh)
```

```sql
CREATE TABLE competitions (
  id          ULID PRIMARY KEY,
  tenant_id   ULID NOT NULL,
  name        TEXT NOT NULL,
  status      TEXT NOT NULL DEFAULT 'draft'
    CHECK (status IN ('draft','announced','live','scoring','results',
                      'settled','archived','cancelled','aborted')),
  window_from TIMESTAMPTZ NOT NULL, window_to TIMESTAMPTZ NOT NULL,
  entry_close TIMESTAMPTZ NOT NULL,
  ruleset     JSONB NOT NULL,                -- versioned: metric, period,
  ruleset_version INT NOT NULL,              --   tie-breaks (incl. seed),
                                             --   DQ conditions, team?
  prize_pool  JSONB NOT NULL,                -- ordered prizes: kind, value,
                                             --   ledger_source
  liability_entry_id ULID,                   -- LED: booked at creation
  entry_fee_cents BIGINT NOT NULL DEFAULT 0, -- CHK purchase amount
  limits      JSONB NOT NULL,                -- {per_trader, per_competition}
  template_id ULID,                          -- CMP-15
  created_by  ULID, created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_cmp_tenant ON competitions(tenant_id, status, window_to);

CREATE TABLE competition_entries (
  id            ULID PRIMARY KEY,
  competition_id ULID NOT NULL REFERENCES competitions(id),
  tenant_id     ULID NOT NULL,
  identity_id   ULID NOT NULL,
  account_id    ULID,                        -- the LCC competition account
  entry_fee_ref ULID,                        -- the CHK order (fee > 0)
  status        TEXT NOT NULL DEFAULT 'registered'
    CHECK (status IN ('registered','active','finished','dq_flagged',
                      'dq_confirmed','forfeited')),
  display_name  TEXT, handle TEXT,           -- the public identity (CMP-11)
  registered_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (competition_id, identity_id)
);
CREATE INDEX idx_cment_comp ON competition_entries(competition_id, status);

CREATE TABLE competition_scores (             -- per-tick (re-runnable)
  id            ULID PRIMARY KEY,
  entry_id      ULID NOT NULL REFERENCES competition_entries(id),
  as_of         TIMESTAMPTZ NOT NULL,
  metric_refs   JSONB NOT NULL,              -- equity_points row ids (the
                                             --   input snapshot — CMP-17)
  score         BIGINT NOT NULL,
  dq_flags      JSONB NOT NULL DEFAULT '[]', -- rule + snapshot per flag
  UNIQUE (entry_id, as_of)
);
CREATE INDEX idx_cscore_entry ON competition_scores(entry_id, as_of DESC);
CREATE TABLE competition_board_snapshots (    -- hourly (dispute history)
  id          ULID PRIMARY KEY,
  competition_id ULID NOT NULL, as_of TIMESTAMPTZ NOT NULL,
  rows        JSONB NOT NULL,                -- ranked (rank, entry, score,
                                             --   dq, under_review)
  UNIQUE (competition_id, as_of)
);
CREATE TABLE competition_results (            -- the frozen set
  id            ULID PRIMARY KEY,
  competition_id ULID NOT NULL,
  entry_id      ULID NOT NULL,
  final_rank    INT NOT NULL, final_score BIGINT NOT NULL,
  prize_ref     ULID,                        -- the PAY object (kind: prize)
  evidence      JSONB NOT NULL,              -- rule set version + tick refs
  published_at  TIMESTAMPTZ NOT NULL,
  UNIQUE (competition_id, entry_id)
);
-- gamification: badges (tenant, key, icon, criteria, visibility),
-- user_badges (identity, badge, at), user_xp (identity, xp, level) —
-- event-consumer-populated (the ANA funnel pattern)
```

### 25 — MIG (from docs/25-migration.md §9)

```sql
CREATE TABLE migrations (
  id          ULID PRIMARY KEY,
  tenant_id   ULID NOT NULL,
  source      TEXT NOT NULL,                  -- 'tts'|'yourpropfirm'|'propaccount'
  status      TEXT NOT NULL DEFAULT 'planned'
    CHECK (status IN ('planned','exports_received','validated',
                      'dry_run_passed','import_ready','importing',
                      'reconciled','cutover_pending','cut_over',
                      'parallel_running','closed','aborted')),
  policies    JSONB NOT NULL,                 -- §3.2/3.3 decisions (data)
  t_date      TIMESTAMPTZ NOT NULL,
  exports_ref JSONB NOT NULL,                 -- R2 keys of the export package
  manifest    JSONB NOT NULL,                 -- TTS's per-class counts/sums
  created_by  ULID, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  closed_at   TIMESTAMPTZ
);
CREATE TABLE migration_classes (
  id            ULID PRIMARY KEY,
  migration_id  ULID NOT NULL REFERENCES migrations(id),
  class         TEXT NOT NULL,                -- traders|accounts|terms|history|orders|payouts|docs|kyc_records
  state         TEXT NOT NULL DEFAULT 'pending'
    CHECK (state IN ('pending','validating','imported','failed')),
  source_rows   INT, imported_rows INT, exceptions_open INT,
  sum_source    BIGINT, sum_imported BIGINT,
  import_meta   JSONB,                        -- importer version, mapping
  started_at    TIMESTAMPTZ, completed_at TIMESTAMPTZ,
  UNIQUE (migration_id, class)
);
CREATE TABLE migration_exceptions (
  id            ULID PRIMARY KEY,
  migration_id  ULID NOT NULL,
  class         TEXT NOT NULL,
  source_hash   TEXT NOT NULL,                -- the row's hash
  reason        TEXT NOT NULL,                -- the MIG_* reason codes
  detail        JSONB NOT NULL,
  disposition   TEXT,                          -- NULL = open
  disposition_action JSONB,                    -- {action, refs}
  disposed_by   ULID, disposed_at TIMESTAMPTZ
);
CREATE INDEX idx_migexc_open ON migration_exceptions(migration_id, disposition);
CREATE TABLE migration_parallel_days (
  id            ULID PRIMARY KEY,
  migration_id  ULID NOT NULL,
  day           DATE NOT NULL,
  accounts_compared INT NOT NULL,
  drift         JSONB NOT NULL,               -- the per-account deltas
  payouts_match BOOLEAN, purchases_match BOOLEAN,
  state         TEXT NOT NULL,                -- matched|drift|resolved
  UNIQUE (migration_id, day)
);
CREATE TABLE migration_corrections (          -- §3.5
  id            ULID PRIMARY KEY,
  migration_id  ULID NOT NULL,
  class         TEXT NOT NULL, source_hash TEXT NOT NULL,
  old           JSONB NOT NULL, new JSONB NOT NULL,
  reason        TEXT NOT NULL,
  approved_by   ULID, approved_at TIMESTAMPTZ,
  domain_refs   JSONB NOT NULL,               -- the LCC/PAY/LED objects touched
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  applied_at    TIMESTAMPTZ
);
-- the imported rows themselves: no new table — every domain table gains
-- the import_meta column (JSONB, NULL for non-imported rows):
--   import_meta = { migration_id, source_hash, source_row, imported_at }
-- the per-row hash is the reconciliation key everywhere (the §3.1 rule)
```

### 26 — MOB/JRN/EDU/CHT (from docs/26-mobile-apps.md §9)

```sql
CREATE TABLE auth_devices (                        -- the V2 device
  id          ULID PRIMARY KEY,                    -- credential store
  identity_id ULID NOT NULL,
  tenant_id   ULID NOT NULL,
  label       TEXT, platform TEXT,                 -- (AUTH-owned — shown
  token_hash  TEXT NOT NULL,                       --   here for the
  biometric   TEXT,                                 --   contract; the
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),  --   table lives in
  last_seen_at TIMESTAMPTZ, revoked_at TIMESTAMPTZ,--   AUTH's schema,
  UNIQUE (identity_id, id)                         --   02 owns it)
);
CREATE TABLE push_tokens (                         -- NOT-owned
  id          ULID PRIMARY KEY,
  tenant_id   ULID NOT NULL,
  identity_id ULID NOT NULL,
  device_id   ULID NOT NULL,
  platform    TEXT NOT NULL,                        -- fcm|apns
  token       TEXT NOT NULL,                        -- (the token is
  active      BOOLEAN NOT NULL DEFAULT true,        --   provider-
  dead_at     TIMESTAMPTZ,                          --   opaque to us;
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()    --   field-encrypted
);                                                  --   like the PAY
                                                  --   method strings)
```

```sql
CREATE TABLE journal_entries (
  id            ULID PRIMARY KEY,
  tenant_id     ULID NOT NULL,
  identity_id   ULID NOT NULL,
  account_id    ULID NOT NULL,
  deal_id       TEXT,                          -- the BRG ref (the snapshot
  day_key       DATE,                          --   is the as-recorded truth)
  kind          TEXT NOT NULL
    CHECK (kind IN ('trade_note','daily_review')),
  body          TEXT NOT NULL,
  tags          TEXT[] NOT NULL DEFAULT '{}',
  screenshot_ref TEXT,
  deal_snapshot JSONB,                         -- the §3.1 fields
  versions      JSONB NOT NULL DEFAULT '[]',   -- the last-5 edit history
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_jrn_trader ON journal_entries(tenant_id, identity_id, created_at DESC);
CREATE INDEX idx_jrn_account ON journal_entries(tenant_id, account_id, created_at DESC);
CREATE INDEX idx_jrn_tag ON journal_entries USING gin (tags);

CREATE TABLE journal_stats (                    -- the rebuildable read model
  id            ULID PRIMARY KEY,
  tenant_id     ULID NOT NULL,
  identity_id   ULID NOT NULL,
  account_id    ULID,
  bucket        TEXT NOT NULL,                  -- 'tag'|'hour'|'dow'|'streak'
  key           TEXT NOT NULL,
  value         JSONB NOT NULL,
  as_of         TIMESTAMPTZ NOT NULL,
  UNIQUE (tenant_id, identity_id, account_id, bucket, key, as_of)
);
CREATE TABLE journal_shares (                   -- V3
  id            ULID PRIMARY KEY,
  entry_id      ULID NOT NULL REFERENCES journal_entries(id),
  token_hash    TEXT NOT NULL UNIQUE,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  expires_at    TIMESTAMPTZ NOT NULL,
  revoked_at    TIMESTAMPTZ
);
```

```sql
CREATE TABLE edu_courses (
  id          ULID PRIMARY KEY,
  tenant_id   ULID NOT NULL,
  slug        TEXT NOT NULL, title TEXT NOT NULL,
  description TEXT, est_minutes INT,
  status      TEXT NOT NULL DEFAULT 'draft'
    CHECK (status IN ('draft','published','archived')),
  live_version INT NOT NULL DEFAULT 1,
  sequential  BOOLEAN NOT NULL DEFAULT false,  -- the path-order gate
  gating      TEXT NOT NULL DEFAULT 'self_attested'
    CHECK (gating IN ('self_attested','quiz')),
  published_at TIMESTAMPTZ, published_by ULID,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, slug)
);
CREATE TABLE edu_course_blocks (
  id          ULID PRIMARY KEY,
  course_id   ULID NOT NULL REFERENCES edu_courses(id),
  version     INT NOT NULL,
  sort        INT NOT NULL,
  block_type  TEXT NOT NULL CHECK (block_type IN ('video','text','quiz')),
  data        JSONB NOT NULL,                  -- video: {r2_key, duration,
                                               --   title}; text: {markdown,
                                               --   title}; quiz: {quiz_id,
                                               --   checkpoint: bool}
  UNIQUE (course_id, version, sort)
);
CREATE TABLE edu_quiz (
  id          ULID PRIMARY KEY,
  tenant_id   ULID NOT NULL,
  questions   JSONB NOT NULL,                  -- the §3.1 shape (the answer
                                               --   key is server-side only
                                               --   — the trader API never
                                               --   returns it pre-submit)
  pass_pct    INT NOT NULL DEFAULT 80,
  max_attempts INT NOT NULL DEFAULT 3,
  attempt_cooldown_h INT
);
CREATE TABLE edu_paths (
  id          ULID PRIMARY KEY,
  tenant_id   ULID NOT NULL,
  name        TEXT NOT NULL,
  course_ids  ULID[] NOT NULL,
  auto_enroll BOOLEAN NOT NULL DEFAULT false,  -- on account.funded
  live_version INT NOT NULL DEFAULT 1,
  status      TEXT NOT NULL DEFAULT 'published'
    CHECK (status IN ('draft','published','archived')),
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE edu_enrollments (
  id            ULID PRIMARY KEY,
  tenant_id     ULID NOT NULL,
  identity_id   ULID NOT NULL,
  course_id     ULID, path_id ULID,
  path_version  INT,                           -- the frozen version (§5)
  state         TEXT NOT NULL DEFAULT 'enrolled'
    CHECK (state IN ('enrolled','in_progress','completed','dropped')),
  started_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  completed_at  TIMESTAMPTZ,
  UNIQUE (identity_id, course_id), UNIQUE (identity_id, path_id)
);
CREATE INDEX idx_eduenr_trader ON edu_enrollments(tenant_id, identity_id);
CREATE TABLE edu_progress (
  id            ULID PRIMARY KEY,
  enrollment_id ULID NOT NULL REFERENCES edu_enrollments(id),
  block_id      ULID NOT NULL,
  state         TEXT NOT NULL DEFAULT 'not_started'
    CHECK (state IN ('not_started','in_progress','completed')),
  video_pct     SMALLINT NOT NULL DEFAULT 0,   -- the max claim (§3.2)
  quiz_attempts INT NOT NULL DEFAULT 0,
  quiz_best_pct SMALLINT NOT NULL DEFAULT 0,
  completed_at  TIMESTAMPTZ,
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (enrollment_id, block_id)
);
CREATE TABLE edu_quiz_attempts (               -- the append-only audit
  id            ULID PRIMARY KEY,
  quiz_id       ULID NOT NULL,
  enrollment_id ULID NOT NULL,
  block_id      ULID,
  pct           INT NOT NULL,
  answers       JSONB NOT NULL,                -- (the given answers — the
  passed        BOOLEAN NOT NULL,              --   content team's wrong-
  at            TIMESTAMPTZ NOT NULL DEFAULT now()  -- question analysis)
);
CREATE INDEX idx_eduatt_quiz ON edu_quiz_attempts(quiz_id, at DESC);
-- the certificate: the DOC pipeline (the `course_certificate` type,
-- the 15 §3.1 set) — EDU emits the event, DOC owns the object
```

```sql
-- the conversation = the SUP ticket (the 18 §9 tables, the
-- `tickets.channel` column: 'ticket'|'chat'|'discord' — the
-- CHT-04/02 channels) + the `ticket_messages` (the thread).
-- The new CHT tables:
CREATE TABLE chat_announcements (
  id            ULID PRIMARY KEY,
  tenant_id     ULID NOT NULL,
  title         TEXT NOT NULL,
  body          TEXT NOT NULL,                  -- the CMS-03 sanitize
  severity      TEXT NOT NULL DEFAULT 'info'
    CHECK (severity IN ('info','warning','critical')),
  channel_flags JSONB NOT NULL,                 -- {td_banner, email,
                                                --   discord}
  visible_from  TIMESTAMPTZ NOT NULL DEFAULT now(),
  visible_until TIMESTAMPTZ NOT NULL,
  withdrawn_at  TIMESTAMPTZ,                    -- the §5 withdrawal
  withdrawn_by  ULID,
  created_by    ULID, created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_chatann_active ON chat_announcements(tenant_id, visible_until)
  WHERE withdrawn_at IS NULL;
CREATE TABLE discord_links (
  id            ULID PRIMARY KEY,
  tenant_id     ULID NOT NULL,
  identity_id   ULID NOT NULL,
  discord_user_id TEXT NOT NULL,
  discord_username TEXT,
  state         TEXT NOT NULL DEFAULT 'pending'
    CHECK (state IN ('pending','approved','rejected','unlinked')),
  approved_by   ULID, approved_at TIMESTAMPTZ,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, identity_id)               -- one active link
);
CREATE INDEX idx_disc_user ON discord_links(tenant_id, discord_user_id);
-- V3 (the forum):
CREATE TABLE forum_boards (
  id          ULID PRIMARY KEY,
  tenant_id   ULID NOT NULL, name TEXT NOT NULL, key TEXT NOT NULL,
  order       INT, retention_days INT NOT NULL DEFAULT 730,
  UNIQUE (tenant_id, key)
);
CREATE TABLE forum_threads (
  id          ULID PRIMARY KEY,
  tenant_id   ULID NOT NULL, board_id ULID NOT NULL,
  title       TEXT NOT NULL, author_id ULID NOT NULL,
  state       TEXT NOT NULL DEFAULT 'open'
    CHECK (state IN ('open','closed','pinned','removed')),
  removed_at  TIMESTAMPTZ, removed_by ULID,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_forum_threads ON forum_threads(tenant_id, board_id, created_at DESC);
CREATE TABLE forum_posts (
  id          ULID PRIMARY KEY,
  tenant_id   ULID NOT NULL, thread_id ULID NOT NULL,
  author_id   ULID NOT NULL, body TEXT NOT NULL,
  state       TEXT NOT NULL DEFAULT 'visible'
    CHECK (state IN ('visible','removed','flagged')),
  removed_at  TIMESTAMPTZ, removed_by ULID,
  removed_body_snapshot TEXT,                   -- the audit snapshot
                                                --   (the §3.3 rule —
                                                --   the removed content
                                                --   is retained in the
                                                --   audit, the AUD mirror
                                                --   carries it)
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_forum_posts ON forum_posts(tenant_id, thread_id, created_at);
CREATE TABLE forum_reports (
  id          ULID PRIMARY KEY,
  tenant_id   ULID NOT NULL, post_id ULID NOT NULL,
  reporter_id ULID NOT NULL, reason TEXT NOT NULL,
  state       TEXT NOT NULL DEFAULT 'filed'
    CHECK (state IN ('filed','actioned','dismissed')),
  action      TEXT, actioned_by ULID, actioned_at TIMESTAMPTZ,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (post_id, reporter_id)
);
-- the presence: the Redis (the ephemeral state — the staff
-- online/away is the Redis key (the 15-min TTL, the heartbeat
-- from the ADM session), never the PG (the presence is the
-- live signal, the §3.1 posture); the typing: the SSE-ephemeral
-- (no store, the §5 rule)
```

### 27 — SDK/DVP/TRD/PLT/CS (from docs/27-ecosystem.md §9)

```sql
-- the keys: the AUTH-25 (the 02 schema) — the public
-- extension columns:
--   api_keys.scope JSONB (the §3.3 scope set),
--   api_keys.environment TEXT ('test'|'live', the immutable),
--   api_keys.rate_tier TEXT (the SDK-14 config ref),
--   api_keys.ip_allowlist CIDR[],
--   api_keys.webhook_secret_hash TEXT (the separate secret,
--     the §3.2 two-secrets rule),
--   api_keys.delegated_from ULID (the DVP-10, the NULL for
--     the parent, the one-level cap, the §3.3)
-- the developer role: the tenant_memberships.role =
--   'firm:developer' (the 02 §3.2 role set)
CREATE TABLE public_id_refs (                    -- the §8 ref
  id            ULID PRIMARY KEY,                -- indirection (the
  tenant_id     ULID NOT NULL,                   --  durable-contract
  kind          TEXT NOT NULL,                   --  rule): the
  internal_id   ULID NOT NULL,                   --  public API's
  public_ref    TEXT NOT NULL,                   --  stable aliases
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, kind, internal_id),
  UNIQUE (tenant_id, public_ref)
);
-- the public_ref is the `id_…`/`acc_…`/`ord_…`/`pay_…`
-- string (the ULID-based, the tenant-scoped) — every public
-- API read/write translates: the public_ref in → the
-- internal id (the GW middleware, the 04 chain step), the
-- internal id out → the public_ref (the serializer, the
-- contract test: a public response containing a raw ULID
-- fails the CI (the property test, the §8 rule))
CREATE TABLE webhook_subscriptions (             -- the key's
  id            ULID PRIMARY KEY,                --  topics (the
  key_id        ULID NOT NULL,                   --  SDK-02
  topics        TEXT[] NOT NULL,                 --  subscription)
  endpoint      TEXT NOT NULL,
  active        BOOLEAN NOT NULL DEFAULT true,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE webhook_deliveries_public (         -- the developer-
  id            ULID PRIMARY KEY,                --  visible log
  key_id        ULID NOT NULL,                   --  (the DVP-05/07,
  event_id      TEXT NOT NULL,                   --  the SDK-07
  endpoint      TEXT NOT NULL,                   --  replay)
  state         TEXT NOT NULL,                   --  the delivery
  attempts      INT NOT NULL DEFAULT 0,          --  health
  last_status   INT, last_error TEXT,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_whd_key ON webhook_deliveries_public(key_id, created_at DESC);
CREATE TABLE developer_usage_daily (             -- the DVP-06
  key_id        ULID NOT NULL,
  day           DATE NOT NULL,
  calls         BIGINT NOT NULL,
  by_status     JSONB NOT NULL,                  --  read model
  webhook_deliveries BIGINT, webhook_failures BIGINT,
  rate_limited  BIGINT NOT NULL DEFAULT 0,
  PRIMARY KEY (key_id, day)
);
CREATE TABLE integrations_certified (            -- the SDK-10,
  id            ULID PRIMARY KEY,                --  the DVP-13/14
  tenant_id     ULID,                            --  the directory
  partner_name  TEXT NOT NULL,                   --  + the badge
  partner_url   TEXT, description TEXT,
  integration_type TEXT NOT NULL,                --  the "builds on
  sdk_version   TEXT,                            --  Alpha One"
  certified_at  TIMESTAMPTZ NOT NULL,
  last_run_at   TIMESTAMPTZ,
  state         TEXT NOT NULL DEFAULT 'certified'
    CHECK (state IN ('applied','certified','lapsed','unlisted')),
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- the changelog: the platform's (the docs/ changelog rows —
--   the version, the date, the changes JSONB, the
--   deprecations (the sunset dates), the security (the
--   private-first flag) — the PG table + the generated
--   feed (the DVP-08), the static site's data source
```

```sql
CREATE TABLE trading_leaders (                -- the TRD-01/02
  id          ULID PRIMARY KEY,
  tenant_id   ULID NOT NULL,
  identity_id ULID NOT NULL,                  -- the leader (the opt-in,
  account_id  ULID NOT NULL,                  --   the 2FA, the terms)
  display_name TEXT,                          -- the 24 Part B's handle
  status      TEXT NOT NULL DEFAULT 'opted_in'
    CHECK (status IN ('opted_in','listed','delisted')),
  delisted_at TIMESTAMPTZ, delisted_reason TEXT,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, identity_id)
);
CREATE TABLE copy_subscriptions (             -- the TRD-01
  id          ULID PRIMARY KEY,
  tenant_id   ULID NOT NULL,
  leader_id   ULID NOT NULL REFERENCES trading_leaders(id),
  identity_id ULID NOT NULL,                  -- the follower
  account_id  ULID NOT NULL,                  -- the follower's MT5
  allocation  JSONB NOT NULL,                 -- the §3.1 config
  risk_config JSONB NOT NULL,                 -- the guardrails (the
  config_version INT NOT NULL DEFAULT 1,      --   TRD-08's versioned)
  state       TEXT NOT NULL DEFAULT 'active'
    CHECK (state IN ('active','closed','halted')),
  closed_at   TIMESTAMPTZ, close_reason TEXT,
  pnl_cents   BIGINT NOT NULL DEFAULT 0,
  trades_mirrored INT NOT NULL DEFAULT 0,
  trades_skipped INT NOT NULL DEFAULT 0,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_copsub_follower ON copy_subscriptions(tenant_id, identity_id, state);
CREATE TABLE copy_trades (                    -- the mirror log (the
  id          ULID PRIMARY KEY,               --   audit, the ANA)
  tenant_id   ULID NOT NULL,
  subscription_id ULID NOT NULL,
  leader_deal_id TEXT NOT NULL,               -- the signal (the BRG ref)
  follower_deal_id TEXT,                      -- the mirror (the NULL on
  state       TEXT NOT NULL,                  --   the skip)
  CHECK (state IN ('mirrored','skipped')),
  skip_reason TEXT,                           -- slippage|stale|circuit
  signal_at   TIMESTAMPTZ NOT NULL,
  mirror_at   TIMESTAMPTZ,
  latency_ms  INT,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_copytrades_sub ON copy_trades(subscription_id, created_at DESC);
CREATE TABLE backtest_runs (                  -- the TRD-04
  id          ULID PRIMARY KEY,
  tenant_id   ULID NOT NULL,
  identity_id ULID,                           -- the trader's (the NULL
  strategy_ref TEXT NOT NULL,                 --   for the tenant's)
  engine      TEXT NOT NULL,                  -- 'platform'|'mt5' (the
  window_from DATE NOT NULL, window_to DATE NOT NULL,
  state       TEXT NOT NULL DEFAULT 'queued'
    CHECK (state IN ('queued','running','completed','failed')),
  result      JSONB,                          -- the §8 shape
  result_hash TEXT,                           -- the recompute (the 09
  error       TEXT,                           --   §3.4)
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  completed_at TIMESTAMPTZ
);
CREATE INDEX idx_bktrun_tenant ON backtest_runs(tenant_id, created_at DESC);
CREATE TABLE paper_accounts (                 -- the TRD-05 (the
  id          ULID PRIMARY KEY,               --   no-real-money, the
  tenant_id   ULID NOT NULL,                  --   separate tables, the
  identity_id ULID NOT NULL,                  --   05 §1 posture)
  contest_id  ULID,                           -- the 24 Part B's comp
  virtual_balance_cents BIGINT NOT NULL,      -- the 0 LED (the labeled)
  state       TEXT NOT NULL DEFAULT 'active'
    CHECK (state IN ('active','archived')),
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  archived_at TIMESTAMPTZ
);
CREATE INDEX idx_paper_trader ON paper_accounts(tenant_id, identity_id, state);
-- the paper deals: the `paper_deals` (the simulation's, the tick-
--   driven, the no-BRG (the no-broker, the §3.3) — the separate
--   table, the 13-mo retention (the 04 §5.4 class), the "PAPER"
--   badge's data source (the UI's negative test, the §5)
-- the advanced orders: the BRG's `orders` table (the 08 §9, the
--   MetaApi's order state, the Capabilities() (the 08 §1) — the
--   TRD-06 adds no table (the order is the BRG's, the 08's
--   sync, the EVL's observed, the normal)
-- the algo keys: the Part A's `api_keys` (the `trading:write`
--   scope, the delegation) + the TRD-08's guardrail config (the
--   `algo_guardrails` (the per-key, the versioned, the §5)):
CREATE TABLE algo_guardrails (
  id          ULID PRIMARY KEY,
  tenant_id   ULID NOT NULL,
  key_id      ULID,                           -- the algo key (the NULL
  follower_id ULID,                           --   for the copy's
  max_position_cents BIGINT,                  --   subscription (the
  max_daily_loss_cents BIGINT,                --   risk_config, the
  order_rate_per_min INT,                     --   §3.1)
  symbol_allowlist TEXT[],
  version     INT NOT NULL DEFAULT 1,
  active      BOOLEAN NOT NULL DEFAULT true,
  created_by  ULID, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, key_id, version)
);
-- the halt state: the `algo_halts` (the key/follower, the breach
--   ref, the config version, the re-enable (the 2FA, the review) —
--   the 08 §3.3's circuit pattern, the 24 Part B's evidence
--   posture)
```


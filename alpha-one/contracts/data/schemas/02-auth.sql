-- 02 — AUTH: DDL split from docs/32-database-design.md (source: docs/02-identity-access.md §9). docs/32 is the source of truth; delivered through versioned migrations (OPS-06, expand-contract discipline).
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

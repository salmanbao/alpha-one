-- 02 — AUTH: DDL split from docs/32-database-design.md (source: docs/02-identity-access.md §9). docs/32 is the source of truth; delivered through versioned migrations (OPS-06, expand-contract discipline).
-- platform-wide identity (no tenant_id by design)
CREATE TABLE identities (
  id            ULID PRIMARY KEY,
  idp_user_id   TEXT UNIQUE,                -- ZITADEL user id (sub); NULL until first login
  identity_key  TEXT UNIQUE NOT NULL,       -- sha256(lower(trim(email))) — platform join key (G1/AUTH-36)
  idp_org_id    TEXT,                       -- the ZITADEL org that owns this user object
  realm         TEXT NOT NULL DEFAULT 'tenant'
                CHECK (realm IN ('tenant','platform')),   -- AUTH-16 audience realm
  email         CITEXT UNIQUE NOT NULL,
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

CREATE TABLE tenant_memberships (
  id          ULID PRIMARY KEY,
  identity_id ULID NOT NULL REFERENCES identities(id),
  tenant_id   ULID NOT NULL REFERENCES tenants(id),
  role        TEXT NOT NULL DEFAULT 'user:trader',
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
  refresh_hash  TEXT UNIQUE,                        -- single-use, rotated (ours)
  prev_refresh_hash TEXT,                           -- for reuse detection
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

-- 07 — LCC: DDL split from docs/32-database-design.md (source: docs/07-account-lifecycle.md §9). docs/32 is the source of truth; delivered through versioned migrations (OPS-06, expand-contract discipline).
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

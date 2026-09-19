-- 08 — BRG: DDL split from docs/32-database-design.md (source: docs/08-trading-bridge.md §9). docs/32 is the source of truth; delivered through versioned migrations (OPS-06, expand-contract discipline).
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
  last_margin_cents  BIGINT,
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

-- 08 — BRG: DDL split from docs/32-database-design.md (source: docs/08-trading-bridge.md §9). docs/32 is the source of truth; delivered through versioned migrations (OPS-06, expand-contract discipline).
CREATE TABLE broker_groups (
  id            ULID PRIMARY KEY,
  tenant_id     ULID NOT NULL REFERENCES tenants(id),
  name          TEXT NOT NULL,
  platform      TEXT NOT NULL DEFAULT 'mt5',
  server_id     TEXT NOT NULL,              -- MetaApi server identifier
  timezone      TEXT NOT NULL,              -- day-boundary authority (ADR-12)
  poll_interval_s INT NOT NULL DEFAULT 60,     -- fallback poll cadence (D78: stream is primary)
  metaapi_region  TEXT,                        -- MetaApi region for this group (docs/63 §4.9)
  quote_interval_ms INT NOT NULL DEFAULT 1000 CHECK (quote_interval_ms >= 250), -- stream quotes
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
  stream_state       TEXT NOT NULL DEFAULT 'subscribing'      -- D78, docs/63 §4.7
                     CHECK (stream_state IN ('subscribing','syncing','live','stale','unsubscribed')),
  stream_state_at    TIMESTAMPTZ,
  last_stream_seq    BIGINT NOT NULL DEFAULT 0,               -- bridge-assigned (D33)
  metaapi_reliability TEXT NOT NULL DEFAULT 'regular' CHECK (metaapi_reliability IN ('regular','high')),
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  archived_at        TIMESTAMPTZ,
  UNIQUE (login)
);
CREATE INDEX idx_bacc_tenant_state ON broker_accounts(tenant_id, state);
CREATE INDEX idx_bacc_sync ON broker_accounts(state, last_synced_at) WHERE state = 'active';
CREATE INDEX idx_bacc_stale ON broker_accounts(stream_state_at) WHERE stream_state = 'stale'; -- fallback poller

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

-- D83 (docs/64 §4.8, docs/29 §3.4): the two high-volume BRG tables are
-- partitioned by (tenant_id, day) — HASH(tenant_id) into 16 buckets, each
-- RANGE-partitioned by day. tenant_id first because it is the D83 sharding
-- function (the same key a Citus distribution would use) and every
-- hot-path query carries it; day second for retention (DROP, not DELETE).
-- Postgres requires every partition key in the PRIMARY KEY, so the keys
-- below carry tenant_id and the day column; neither weakens uniqueness,
-- because both are functions of the natural key:
--   * a deal's tenant is its login's tenant, and deal_day is derived from
--     deal_time (broker time, immutable per deal ticket), so a redelivered
--     deal lands on the same PK and the dedupe (ON CONFLICT DO NOTHING)
--     still fires. The previous `PARTITION BY RANGE (received_at)` with
--     `PRIMARY KEY (login, deal_id)` was rejected by Postgres outright, and
--     partitioning on received_at would have broken dedupe (a redelivery has
--     a new received_at);
--   * a snapshot's tenant is its account's tenant; bucket_ts is already
--     the PK.
-- Child partitions: the 16 hash buckets are created here; the per-day
-- children are created ahead of time by the BRG partition job (7 days
-- ahead) and dropped by retention (account_snapshots 14 d rolling, D35;
-- broker_deals monthly children, kept — money evidence).
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
  deal_day      DATE NOT NULL,             -- (deal_time AT TIME ZONE 'UTC')::date, set by the writer
  received_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (tenant_id, login, deal_id, deal_day),
  CHECK (deal_day = (deal_time AT TIME ZONE 'UTC')::date)
) PARTITION BY HASH (tenant_id);

CREATE TABLE account_snapshots (              -- §3.3: 1 row/account/min, 14-day rolling (D35)
  account_id      ULID NOT NULL,
  bucket_ts       TIMESTAMPTZ NOT NULL,       -- minute bucket (UTC)
  tenant_id       ULID NOT NULL,
  login           TEXT NOT NULL,
  equity_cents    BIGINT NOT NULL,
  balance_cents   BIGINT NOT NULL,
  margin_cents    BIGINT,
  free_margin_cents BIGINT,
  equity_low_cents  BIGINT,                   -- D79: observed min/max broker equity in the
  equity_high_cents BIGINT,                   -- minute (streaming; NULL on fallback-poll rows)
  broker_time     TIMESTAMPTZ,                -- broker-attested time of the tick
  received_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (tenant_id, account_id, bucket_ts)
) PARTITION BY HASH (tenant_id);
-- retention = 14-day rolling (per-day child DROP; BRG job) with the daily
-- rollup exported to the ANA read model first (docs/19). PAY eligibility and
-- TD intraday equity curves read here — from the replica (D83), except
-- BRG-09's on-demand refresh of the latest row.

DO $$
BEGIN
  FOR b IN 0..15 LOOP
    EXECUTE format(
      'CREATE TABLE broker_deals_h%s PARTITION OF broker_deals
         FOR VALUES WITH (MODULUS 16, REMAINDER %s) PARTITION BY RANGE (deal_day)', b, b);
    EXECUTE format(
      'CREATE TABLE account_snapshots_h%s PARTITION OF account_snapshots
         FOR VALUES WITH (MODULUS 16, REMAINDER %s) PARTITION BY RANGE (bucket_ts)', b, b);
  END LOOP;
END $$;
-- Day children, e.g. (the BRG partition job's template):
--   CREATE TABLE account_snapshots_h3_20260925 PARTITION OF account_snapshots_h3
--     FOR VALUES FROM ('2026-09-25 00:00+00') TO ('2026-09-26 00:00+00');
--   CREATE TABLE broker_deals_h3_202609 PARTITION OF broker_deals_h3
--     FOR VALUES FROM ('2026-09-01') TO ('2026-10-01');

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

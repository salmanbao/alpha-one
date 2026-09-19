-- 27 — SDK/DVP/TRD/PLT/CS: DDL split from docs/32-database-design.md (source: docs/27-ecosystem.md §9). docs/32 is the source of truth; delivered through versioned migrations (OPS-06, expand-contract discipline).
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

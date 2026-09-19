-- 19 — ANA: DDL split from docs/32-database-design.md (source: docs/19-analytics.md §9). docs/32 is the source of truth; delivered through versioned migrations (OPS-06, expand-contract discipline).
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

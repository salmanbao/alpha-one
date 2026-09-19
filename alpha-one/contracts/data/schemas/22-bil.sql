-- 22 — BIL: DDL split from docs/32-database-design.md (source: docs/22-billing.md §9). docs/32 is the source of truth; delivered through versioned migrations (OPS-06, expand-contract discipline).
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

-- 10 — RSK: DDL split from docs/32-database-design.md (source: docs/10-risk-management.md §9). docs/32 is the source of truth; delivered through versioned migrations (OPS-06, expand-contract discipline).
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
  account_ids   ULID[],
  payout_hold   BOOLEAN NOT NULL DEFAULT false,
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

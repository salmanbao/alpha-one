-- 06 — OPS: DDL from docs/06-devops-deployment.md §8 (docs/32 §06: no DDL in module doc — specified here).
-- Platform schema: NO tenant_id on any table (ops data is platform-owned; tenant drill reports reference tenants by id only).
-- Delivered through versioned migrations (OPS-06, expand-contract discipline).

CREATE TABLE ops_deploys (
  id            ULID PRIMARY KEY,
  env           TEXT NOT NULL CHECK (env IN ('staging','prod')),
  sha           TEXT NOT NULL,                      -- commit sha deployed
  actor         TEXT NOT NULL,                      -- who/what triggered (user id or 'ci')
  status        TEXT NOT NULL DEFAULT 'running'
                CHECK (status IN ('running','succeeded','failed','rolled_back')),
  started_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  finished_at   TIMESTAMPTZ,
  notes         TEXT
);
CREATE INDEX idx_ops_deploys_env ON ops_deploys(env, started_at DESC);

CREATE TABLE ops_backups (
  id            ULID PRIMARY KEY,
  kind          TEXT NOT NULL CHECK (kind IN ('pg_basebackup','wal_archive','r2_snapshot','config_snapshot')),
  taken_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  size_bytes    BIGINT,
  checksum      TEXT,                               -- sha256 of the artifact
  location      TEXT NOT NULL,                      -- R2 key / host path
  verified_at   TIMESTAMPTZ,                        -- last successful restore drill using this artifact
  drill_report  JSONB                               -- RPO/RTO measured, isolation re-verified (OPS-38)
);
CREATE INDEX idx_ops_backups_kind ON ops_backups(kind, taken_at DESC);

CREATE TABLE ops_incidents (
  id            ULID PRIMARY KEY,
  severity      TEXT NOT NULL CHECK (severity IN ('P0','P1','P2','P3')),
  title         TEXT NOT NULL,
  started_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  acked_at      TIMESTAMPTZ,
  resolved_at   TIMESTAMPTZ,
  commander     TEXT,                               -- identity id of the incident commander
  tenant_ids    ULID[] NOT NULL DEFAULT '{}',       -- affected tenants (empty = platform-wide)
  timeline      JSONB NOT NULL DEFAULT '[]',        -- status updates (time, author, text)
  post_mortem_url TEXT
);
CREATE INDEX idx_ops_incidents_open ON ops_incidents(started_at DESC) WHERE resolved_at IS NULL;

CREATE TABLE ops_slo_defs (                          -- V2 (OPS-12); seed rows in Phase 4
  id            ULID PRIMARY KEY,
  service       TEXT NOT NULL,                      -- api|bridge|engine|relay|workers|web
  metric        TEXT NOT NULL,                      -- e.g. 'sync_lag_s_p99', 'http_5xx_rate'
  target        TEXT NOT NULL,                      -- e.g. 'p99 < 60s'
  window_s      INT NOT NULL DEFAULT 3600,
  alert_severity TEXT NOT NULL DEFAULT 'P2' CHECK (alert_severity IN ('P0','P1','P2','P3')),
  enabled       BOOLEAN NOT NULL DEFAULT true,
  UNIQUE (service, metric)
);

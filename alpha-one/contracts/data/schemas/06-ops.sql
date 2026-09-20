-- 06 — OPS: DDL split from docs/32-database-design.md (source: docs/06-devops-deployment.md §9). docs/32 is the source of truth; delivered through versioned migrations (OPS-06, expand-contract discipline).
CREATE TABLE backups (
  id           ULID PRIMARY KEY,
  kind         TEXT NOT NULL,          -- wal | base | r2_manifest
  taken_at     TIMESTAMPTZ NOT NULL,
  size_bytes   BIGINT NOT NULL,
  checksum     TEXT NOT NULL,
  verified_at  TIMESTAMPTZ,            -- weekly checksum verify (§5)
  drill_report JSONB                   -- monthly restore drill (OPS-38)
);
CREATE INDEX idx_backups_kind_taken ON backups(kind, taken_at DESC);

CREATE TABLE incidents (
  id              ULID PRIMARY KEY,
  severity        TEXT NOT NULL,       -- P1 | P2 | P3 (§5 ladder)
  title           TEXT NOT NULL,
  started_at      TIMESTAMPTZ NOT NULL,
  resolved_at     TIMESTAMPTZ,
  post_mortem_url TEXT                 -- ops/incidents/ (P1/P2 ≤ 48 h)
);

CREATE TABLE deploys (
  id          ULID PRIMARY KEY,
  env         TEXT NOT NULL,           -- staging | prod
  sha         TEXT NOT NULL,           -- immutable GHCR tag
  started_at  TIMESTAMPTZ NOT NULL,
  finished_at TIMESTAMPTZ,
  status      TEXT NOT NULL,           -- promoted | deployed | rolled_back | failed
  actor       TEXT NOT NULL
);

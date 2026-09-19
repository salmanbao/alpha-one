-- 25 — MIG: DDL split from docs/32-database-design.md (source: docs/25-migration.md §9). docs/32 is the source of truth; delivered through versioned migrations (OPS-06, expand-contract discipline).
CREATE TABLE migrations (
  id          ULID PRIMARY KEY,
  tenant_id   ULID NOT NULL,
  source      TEXT NOT NULL,                  -- 'tts'|'yourpropfirm'|'propaccount'
  status      TEXT NOT NULL DEFAULT 'planned'
    CHECK (status IN ('planned','exports_received','validated',
                      'dry_run_passed','import_ready','importing',
                      'reconciled','cutover_pending','cut_over',
                      'parallel_running','closed','aborted')),
  policies    JSONB NOT NULL,                 -- §3.2/3.3 decisions (data)
  t_date      TIMESTAMPTZ NOT NULL,
  exports_ref JSONB NOT NULL,                 -- R2 keys of the export package
  manifest    JSONB NOT NULL,                 -- TTS's per-class counts/sums
  created_by  ULID, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  closed_at   TIMESTAMPTZ
);
CREATE TABLE migration_classes (
  id            ULID PRIMARY KEY,
  migration_id  ULID NOT NULL REFERENCES migrations(id),
  class         TEXT NOT NULL,                -- traders|accounts|terms|history|orders|payouts|docs|kyc_records
  state         TEXT NOT NULL DEFAULT 'pending'
    CHECK (state IN ('pending','validating','imported','failed')),
  source_rows   INT, imported_rows INT, exceptions_open INT,
  sum_source    BIGINT, sum_imported BIGINT,
  import_meta   JSONB,                        -- importer version, mapping
  started_at    TIMESTAMPTZ, completed_at TIMESTAMPTZ,
  UNIQUE (migration_id, class)
);
CREATE TABLE migration_exceptions (
  id            ULID PRIMARY KEY,
  migration_id  ULID NOT NULL,
  class         TEXT NOT NULL,
  source_hash   TEXT NOT NULL,                -- the row's hash
  reason        TEXT NOT NULL,                -- the MIG_* reason codes
  detail        JSONB NOT NULL,
  disposition   TEXT,                          -- NULL = open
  disposition_action JSONB,                    -- {action, refs}
  disposed_by   ULID, disposed_at TIMESTAMPTZ
);
CREATE INDEX idx_migexc_open ON migration_exceptions(migration_id, disposition);
CREATE TABLE migration_parallel_days (
  id            ULID PRIMARY KEY,
  migration_id  ULID NOT NULL,
  day           DATE NOT NULL,
  accounts_compared INT NOT NULL,
  drift         JSONB NOT NULL,               -- the per-account deltas
  payouts_match BOOLEAN, purchases_match BOOLEAN,
  state         TEXT NOT NULL,                -- matched|drift|resolved
  UNIQUE (migration_id, day)
);
CREATE TABLE migration_corrections (          -- §3.5
  id            ULID PRIMARY KEY,
  migration_id  ULID NOT NULL,
  class         TEXT NOT NULL, source_hash TEXT NOT NULL,
  old           JSONB NOT NULL, new JSONB NOT NULL,
  reason        TEXT NOT NULL,
  approved_by   ULID, approved_at TIMESTAMPTZ,
  domain_refs   JSONB NOT NULL,               -- the LCC/PAY/LED objects touched
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  applied_at    TIMESTAMPTZ
);
-- the imported rows themselves: no new table — every domain table gains
-- the import_meta column (JSONB, NULL for non-imported rows):
--   import_meta = { migration_id, source_hash, source_row, imported_at }
-- the per-row hash is the reconciliation key everywhere (the §3.1 rule)

-- 20 — CRM: DDL split from docs/32-database-design.md (source: docs/20-crm.md §9). docs/32 is the source of truth; delivered through versioned migrations (OPS-06, expand-contract discipline).
CREATE TABLE crm_segments (
  id          ULID PRIMARY KEY,
  tenant_id   ULID NOT NULL,
  name        TEXT NOT NULL,
  sql_template TEXT NOT NULL,               -- allowlisted tables only (review gate)
  cadence_min INT NOT NULL DEFAULT 15,
  enabled     BOOLEAN NOT NULL DEFAULT true,
  created_by  ULID, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, name)
);
CREATE TABLE crm_segment_members (           -- the snapshot (recomputed)
  tenant_id ULID NOT NULL, segment_id ULID NOT NULL,
  identity_id ULID NOT NULL,
  computed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (tenant_id, segment_id, identity_id)
);
CREATE INDEX idx_segmem_computed ON crm_segment_members(computed_at);

CREATE TABLE crm_campaigns (
  id          ULID PRIMARY KEY,
  tenant_id   ULID NOT NULL,
  name        TEXT NOT NULL,
  segment_id  ULID NOT NULL,
  snapshot_at TIMESTAMPTZ NOT NULL,          -- which membership version
  template    TEXT NOT NULL,                 -- NOT template key@version
  channels    TEXT[] NOT NULL DEFAULT '{email}',
  status      TEXT NOT NULL DEFAULT 'draft'
    CHECK (status IN ('draft','scheduled','sending','sent','cancelled')),
  sent_count  INT, created_by ULID,
  sent_at     TIMESTAMPTZ, created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE crm_consent (                   -- append-only history
  id          ULID PRIMARY KEY,
  tenant_id   ULID NOT NULL, identity_id ULID NOT NULL,
  purpose     TEXT NOT NULL,                 -- marketing_email|marketing_telegram|updates
  state       TEXT NOT NULL,                 -- granted|withdrawn
  source      TEXT NOT NULL,                 -- signup|prefs_page|unsubscribe|manual
  at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_crmconsent_current ON crm_consent(tenant_id, identity_id, purpose, at DESC);
-- tags/notes: identity_tags (identity_id, tag, created_by) + identity_notes
-- (identity_id, body, author) — both audit-mirrored; sequence state (V3):
-- sequence_runs (identity, sequence, step, state, updated_at)

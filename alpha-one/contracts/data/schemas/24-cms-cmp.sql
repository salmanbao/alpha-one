-- 24 — CMS/CMP: DDL split from docs/32-database-design.md (source: docs/24-cms-competitions.md §9). docs/32 is the source of truth; delivered through versioned migrations (OPS-06, expand-contract discipline).
CREATE TABLE site_pages (
  id            ULID PRIMARY KEY,
  tenant_id     ULID NOT NULL,
  slug          TEXT NOT NULL,
  title         TEXT NOT NULL,
  status        TEXT NOT NULL DEFAULT 'draft'
    CHECK (status IN ('draft','published','archived')),
  live_version  INT NOT NULL DEFAULT 1,
  nav_order     INT, is_legal BOOLEAN NOT NULL DEFAULT false,
  seo           JSONB NOT NULL DEFAULT '{}',
  publish_at    TIMESTAMPTZ,                  -- CMS-15
  published_at  TIMESTAMPTZ, published_by ULID,
  legal_review_note TEXT,                     -- required on is_legal publish
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, slug)
);
CREATE TABLE site_page_blocks (
  id          ULID PRIMARY KEY,
  page_id     ULID NOT NULL REFERENCES site_pages(id),
  version     INT NOT NULL,
  parent_id   ULID,
  block_type  TEXT NOT NULL,
  data        JSONB NOT NULL,                 -- schema-validated per type
  sort        INT NOT NULL DEFAULT 0,
  UNIQUE (page_id, version, id)
);
CREATE INDEX idx_siteblocks_live ON site_page_blocks(page_id, version);
CREATE TABLE site_media (
  id          ULID PRIMARY KEY,
  tenant_id   ULID NOT NULL,
  r2_key      TEXT NOT NULL,
  bytes       BIGINT NOT NULL, content_type TEXT NOT NULL,
  uploaded_by ULID, created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE site_leads (                      -- PII: field-encrypted name/email
  id          ULID PRIMARY KEY,
  tenant_id   ULID NOT NULL,
  form_id     ULID NOT NULL,
  data_enc    JSONB NOT NULL,
  ip_hash     TEXT,                           -- analytics-grade, not raw IP
  state       TEXT NOT NULL DEFAULT 'captured'
    CHECK (state IN ('captured','contacted','converted','stale')),
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_siteld_tenant ON site_leads(tenant_id, state, created_at DESC);
-- published_stats (tenant, key, value, source, updated_at, auto_refresh)

CREATE TABLE competitions (
  id          ULID PRIMARY KEY,
  tenant_id   ULID NOT NULL,
  name        TEXT NOT NULL,
  status      TEXT NOT NULL DEFAULT 'draft'
    CHECK (status IN ('draft','announced','live','scoring','results',
                      'settled','archived','cancelled','aborted')),
  window_from TIMESTAMPTZ NOT NULL, window_to TIMESTAMPTZ NOT NULL,
  entry_close TIMESTAMPTZ NOT NULL,
  ruleset     JSONB NOT NULL,                -- versioned: metric, period,
  ruleset_version INT NOT NULL,              --   tie-breaks (incl. seed),
                                             --   DQ conditions, team?
  prize_pool  JSONB NOT NULL,                -- ordered prizes: kind, value,
                                             --   ledger_source
  liability_entry_id ULID,                   -- LED: booked at creation
  entry_fee_cents BIGINT NOT NULL DEFAULT 0, -- CHK purchase amount
  limits      JSONB NOT NULL,                -- {per_trader, per_competition}
  template_id ULID,                          -- CMP-15
  created_by  ULID, created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_cmp_tenant ON competitions(tenant_id, status, window_to);

CREATE TABLE competition_entries (
  id            ULID PRIMARY KEY,
  competition_id ULID NOT NULL REFERENCES competitions(id),
  tenant_id     ULID NOT NULL,
  identity_id   ULID NOT NULL,
  account_id    ULID,                        -- the LCC competition account
  entry_fee_ref ULID,                        -- the CHK order (fee > 0)
  status        TEXT NOT NULL DEFAULT 'registered'
    CHECK (status IN ('registered','active','finished','dq_flagged',
                      'dq_confirmed','forfeited')),
  display_name  TEXT, handle TEXT,           -- the public identity (CMP-11)
  registered_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (competition_id, identity_id)
);
CREATE INDEX idx_cment_comp ON competition_entries(competition_id, status);

CREATE TABLE competition_scores (             -- per-tick (re-runnable)
  id            ULID PRIMARY KEY,
  entry_id      ULID NOT NULL REFERENCES competition_entries(id),
  as_of         TIMESTAMPTZ NOT NULL,
  metric_refs   JSONB NOT NULL,              -- equity_points row ids (the
                                             --   input snapshot — CMP-17)
  score         BIGINT NOT NULL,
  dq_flags      JSONB NOT NULL DEFAULT '[]', -- rule + snapshot per flag
  UNIQUE (entry_id, as_of)
);
CREATE INDEX idx_cscore_entry ON competition_scores(entry_id, as_of DESC);
CREATE TABLE competition_board_snapshots (    -- hourly (dispute history)
  id          ULID PRIMARY KEY,
  competition_id ULID NOT NULL, as_of TIMESTAMPTZ NOT NULL,
  rows        JSONB NOT NULL,                -- ranked (rank, entry, score,
                                             --   dq, under_review)
  UNIQUE (competition_id, as_of)
);
CREATE TABLE competition_results (            -- the frozen set
  id            ULID PRIMARY KEY,
  competition_id ULID NOT NULL,
  entry_id      ULID NOT NULL,
  final_rank    INT NOT NULL, final_score BIGINT NOT NULL,
  prize_ref     ULID,                        -- the PAY object (kind: prize)
  evidence      JSONB NOT NULL,              -- rule set version + tick refs
  published_at  TIMESTAMPTZ NOT NULL,
  UNIQUE (competition_id, entry_id)
);
-- gamification: badges (tenant, key, icon, criteria, visibility),
-- user_badges (identity, badge, at), user_xp (identity, xp, level) —
-- event-consumer-populated (the ANA funnel pattern)

-- 26 — MOB/JRN/EDU/CHT: DDL split from docs/32-database-design.md (source: docs/26-mobile-apps.md §9). docs/32 is the source of truth; delivered through versioned migrations (OPS-06, expand-contract discipline).
CREATE TABLE auth_devices (                        -- the V2 device
  id          ULID PRIMARY KEY,                    -- credential store
  identity_id ULID NOT NULL,
  tenant_id   ULID NOT NULL,
  label       TEXT, platform TEXT,                 -- (AUTH-owned — shown
  token_hash  TEXT NOT NULL,                       --   here for the
  biometric   TEXT,                                 --   contract; the
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),  --   table lives in
  last_seen_at TIMESTAMPTZ, revoked_at TIMESTAMPTZ,--   AUTH's schema,
  UNIQUE (identity_id, id)                         --   02 owns it)
);
CREATE TABLE push_tokens (                         -- NOT-owned
  id          ULID PRIMARY KEY,
  tenant_id   ULID NOT NULL,
  identity_id ULID NOT NULL,
  device_id   ULID NOT NULL,
  platform    TEXT NOT NULL,                        -- fcm|apns
  token       TEXT NOT NULL,                        -- (the token is
  active      BOOLEAN NOT NULL DEFAULT true,        --   provider-
  dead_at     TIMESTAMPTZ,                          --   opaque to us;
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()    --   field-encrypted
);                                                  --   like the PAY
                                                  --   method strings)

CREATE TABLE journal_entries (
  id            ULID PRIMARY KEY,
  tenant_id     ULID NOT NULL,
  identity_id   ULID NOT NULL,
  account_id    ULID NOT NULL,
  deal_id       TEXT,                          -- the BRG ref (the snapshot
  day_key       DATE,                          --   is the as-recorded truth)
  kind          TEXT NOT NULL
    CHECK (kind IN ('trade_note','daily_review')),
  body          TEXT NOT NULL,
  tags          TEXT[] NOT NULL DEFAULT '{}',
  screenshot_ref TEXT,
  deal_snapshot JSONB,                         -- the §3.1 fields
  versions      JSONB NOT NULL DEFAULT '[]',   -- the last-5 edit history
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_jrn_trader ON journal_entries(tenant_id, identity_id, created_at DESC);
CREATE INDEX idx_jrn_account ON journal_entries(tenant_id, account_id, created_at DESC);
CREATE INDEX idx_jrn_tag ON journal_entries USING gin (tags);

CREATE TABLE journal_stats (                    -- the rebuildable read model
  id            ULID PRIMARY KEY,
  tenant_id     ULID NOT NULL,
  identity_id   ULID NOT NULL,
  account_id    ULID,
  bucket        TEXT NOT NULL,                  -- 'tag'|'hour'|'dow'|'streak'
  key           TEXT NOT NULL,
  value         JSONB NOT NULL,
  as_of         TIMESTAMPTZ NOT NULL,
  UNIQUE (tenant_id, identity_id, account_id, bucket, key, as_of)
);
CREATE TABLE journal_shares (                   -- V3
  id            ULID PRIMARY KEY,
  entry_id      ULID NOT NULL REFERENCES journal_entries(id),
  token_hash    TEXT NOT NULL UNIQUE,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  expires_at    TIMESTAMPTZ NOT NULL,
  revoked_at    TIMESTAMPTZ
);

CREATE TABLE edu_courses (
  id          ULID PRIMARY KEY,
  tenant_id   ULID NOT NULL,
  slug        TEXT NOT NULL, title TEXT NOT NULL,
  description TEXT, est_minutes INT,
  status      TEXT NOT NULL DEFAULT 'draft'
    CHECK (status IN ('draft','published','archived')),
  live_version INT NOT NULL DEFAULT 1,
  sequential  BOOLEAN NOT NULL DEFAULT false,  -- the path-order gate
  gating      TEXT NOT NULL DEFAULT 'self_attested'
    CHECK (gating IN ('self_attested','quiz')),
  published_at TIMESTAMPTZ, published_by ULID,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, slug)
);
CREATE TABLE edu_course_blocks (
  id          ULID PRIMARY KEY,
  course_id   ULID NOT NULL REFERENCES edu_courses(id),
  version     INT NOT NULL,
  sort        INT NOT NULL,
  block_type  TEXT NOT NULL CHECK (block_type IN ('video','text','quiz')),
  data        JSONB NOT NULL,                  -- video: {r2_key, duration,
                                               --   title}; text: {markdown,
                                               --   title}; quiz: {quiz_id,
                                               --   checkpoint: bool}
  UNIQUE (course_id, version, sort)
);
CREATE TABLE edu_quiz (
  id          ULID PRIMARY KEY,
  tenant_id   ULID NOT NULL,
  questions   JSONB NOT NULL,                  -- the §3.1 shape (the answer
                                               --   key is server-side only
                                               --   — the trader API never
                                               --   returns it pre-submit)
  pass_pct    INT NOT NULL DEFAULT 80,
  max_attempts INT NOT NULL DEFAULT 3,
  attempt_cooldown_h INT
);
CREATE TABLE edu_paths (
  id          ULID PRIMARY KEY,
  tenant_id   ULID NOT NULL,
  name        TEXT NOT NULL,
  course_ids  ULID[] NOT NULL,
  auto_enroll BOOLEAN NOT NULL DEFAULT false,  -- on account.funded
  live_version INT NOT NULL DEFAULT 1,
  status      TEXT NOT NULL DEFAULT 'published'
    CHECK (status IN ('draft','published','archived')),
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE edu_enrollments (
  id            ULID PRIMARY KEY,
  tenant_id     ULID NOT NULL,
  identity_id   ULID NOT NULL,
  course_id     ULID, path_id ULID,
  path_version  INT,                           -- the frozen version (§5)
  state         TEXT NOT NULL DEFAULT 'enrolled'
    CHECK (state IN ('enrolled','in_progress','completed','dropped')),
  started_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  completed_at  TIMESTAMPTZ,
  UNIQUE (identity_id, course_id), UNIQUE (identity_id, path_id)
);
CREATE INDEX idx_eduenr_trader ON edu_enrollments(tenant_id, identity_id);
CREATE TABLE edu_progress (
  id            ULID PRIMARY KEY,
  enrollment_id ULID NOT NULL REFERENCES edu_enrollments(id),
  block_id      ULID NOT NULL,
  state         TEXT NOT NULL DEFAULT 'not_started'
    CHECK (state IN ('not_started','in_progress','completed')),
  video_pct     SMALLINT NOT NULL DEFAULT 0,   -- the max claim (§3.2)
  quiz_attempts INT NOT NULL DEFAULT 0,
  quiz_best_pct SMALLINT NOT NULL DEFAULT 0,
  completed_at  TIMESTAMPTZ,
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (enrollment_id, block_id)
);
CREATE TABLE edu_quiz_attempts (               -- the append-only audit
  id            ULID PRIMARY KEY,
  quiz_id       ULID NOT NULL,
  enrollment_id ULID NOT NULL,
  block_id      ULID,
  pct           INT NOT NULL,
  answers       JSONB NOT NULL,                -- (the given answers — the
  passed        BOOLEAN NOT NULL,              --   content team's wrong-
  at            TIMESTAMPTZ NOT NULL DEFAULT now()  -- question analysis)
);
CREATE INDEX idx_eduatt_quiz ON edu_quiz_attempts(quiz_id, at DESC);
-- the certificate: the DOC pipeline (the `course_certificate` type,
-- the 15 §3.1 set) — EDU emits the event, DOC owns the object

-- the conversation = the SUP ticket (the 18 §9 tables, the
-- `tickets.channel` column: 'ticket'|'chat'|'discord' — the
-- CHT-04/02 channels) + the `ticket_messages` (the thread).
-- The new CHT tables:
CREATE TABLE chat_announcements (
  id            ULID PRIMARY KEY,
  tenant_id     ULID NOT NULL,
  title         TEXT NOT NULL,
  body          TEXT NOT NULL,                  -- the CMS-03 sanitize
  severity      TEXT NOT NULL DEFAULT 'info'
    CHECK (severity IN ('info','warning','critical')),
  channel_flags JSONB NOT NULL,                 -- {td_banner, email,
                                                --   discord}
  visible_from  TIMESTAMPTZ NOT NULL DEFAULT now(),
  visible_until TIMESTAMPTZ NOT NULL,
  withdrawn_at  TIMESTAMPTZ,                    -- the §5 withdrawal
  withdrawn_by  ULID,
  created_by    ULID, created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_chatann_active ON chat_announcements(tenant_id, visible_until)
  WHERE withdrawn_at IS NULL;
CREATE TABLE discord_links (
  id            ULID PRIMARY KEY,
  tenant_id     ULID NOT NULL,
  identity_id   ULID NOT NULL,
  discord_user_id TEXT NOT NULL,
  discord_username TEXT,
  state         TEXT NOT NULL DEFAULT 'pending'
    CHECK (state IN ('pending','approved','rejected','unlinked')),
  approved_by   ULID, approved_at TIMESTAMPTZ,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, identity_id)               -- one active link
);
CREATE INDEX idx_disc_user ON discord_links(tenant_id, discord_user_id);
-- V3 (the forum):
CREATE TABLE forum_boards (
  id          ULID PRIMARY KEY,
  tenant_id   ULID NOT NULL, name TEXT NOT NULL, key TEXT NOT NULL,
  order       INT, retention_days INT NOT NULL DEFAULT 730,
  UNIQUE (tenant_id, key)
);
CREATE TABLE forum_threads (
  id          ULID PRIMARY KEY,
  tenant_id   ULID NOT NULL, board_id ULID NOT NULL,
  title       TEXT NOT NULL, author_id ULID NOT NULL,
  state       TEXT NOT NULL DEFAULT 'open'
    CHECK (state IN ('open','closed','pinned','removed')),
  removed_at  TIMESTAMPTZ, removed_by ULID,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_forum_threads ON forum_threads(tenant_id, board_id, created_at DESC);
CREATE TABLE forum_posts (
  id          ULID PRIMARY KEY,
  tenant_id   ULID NOT NULL, thread_id ULID NOT NULL,
  author_id   ULID NOT NULL, body TEXT NOT NULL,
  state       TEXT NOT NULL DEFAULT 'visible'
    CHECK (state IN ('visible','removed','flagged')),
  removed_at  TIMESTAMPTZ, removed_by ULID,
  removed_body_snapshot TEXT,                   -- the audit snapshot
                                                --   (the §3.3 rule —
                                                --   the removed content
                                                --   is retained in the
                                                --   audit, the AUD mirror
                                                --   carries it)
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_forum_posts ON forum_posts(tenant_id, thread_id, created_at);
CREATE TABLE forum_reports (
  id          ULID PRIMARY KEY,
  tenant_id   ULID NOT NULL, post_id ULID NOT NULL,
  reporter_id ULID NOT NULL, reason TEXT NOT NULL,
  state       TEXT NOT NULL DEFAULT 'filed'
    CHECK (state IN ('filed','actioned','dismissed')),
  action      TEXT, actioned_by ULID, actioned_at TIMESTAMPTZ,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (post_id, reporter_id)
);
-- the presence: the Redis (the ephemeral state — the staff
-- online/away is the Redis key (the 15-min TTL, the heartbeat
-- from the ADM session), never the PG (the presence is the
-- live signal, the §3.1 posture); the typing: the SSE-ephemeral
-- (no store, the §5 rule)

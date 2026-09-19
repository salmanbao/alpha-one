-- 14 — NOT: DDL split from docs/32-database-design.md (source: docs/14-notifications.md §9). docs/32 is the source of truth; delivered through versioned migrations (OPS-06, expand-contract discipline).
CREATE TABLE notification_templates (
  id            ULID PRIMARY KEY,
  tenant_id     ULID,                          -- NULL = platform default
  key           TEXT NOT NULL,                 -- 'payout_settled'
  version       INT NOT NULL DEFAULT 1,
  subject       TEXT NOT NULL,
  body_html     TEXT NOT NULL,
  body_text     TEXT NOT NULL,
  branding      JSONB,                         -- V2: logo/color overrides (TEN-05/06)
  active        BOOLEAN NOT NULL DEFAULT true,
  created_by    ULID, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, key, version)
);

CREATE TABLE notification_mappings (
  id            ULID PRIMARY KEY,
  tenant_id     ULID,                          -- NULL = platform mapping
  event_type    TEXT NOT NULL,                 -- 'payout.settled'
  channels      TEXT[] NOT NULL DEFAULT '{email}',
  template_key  TEXT NOT NULL,
  priority      TEXT NOT NULL DEFAULT 'normal'
    CHECK (priority IN ('critical','high','normal','low')),
  vars_selector JSONB NOT NULL,                -- whitelisted event fields → vars
  enabled       BOOLEAN NOT NULL DEFAULT true,
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, event_type, channels)
);

CREATE TABLE notifications (
  id            ULID PRIMARY KEY,
  tenant_id     ULID NOT NULL,
  event_ref     TEXT,                          -- stream entry id (trace)
  kind          TEXT NOT NULL,
  recipient_identity ULID,
  recipient_role  TEXT,                        -- staff role target
  channel       TEXT NOT NULL,
  template      TEXT NOT NULL,                 -- 'key@version'
  vars          JSONB NOT NULL,
  state         TEXT NOT NULL DEFAULT 'pending'
    CHECK (state IN ('pending','sent','delivered','failed','dlq','suppressed')),
  suppress_reason TEXT,                        -- dedupe|bounce|complaint|prefs|quiet
  provider_ref  TEXT,
  attempts      INT NOT NULL DEFAULT 0,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  sent_at       TIMESTAMPTZ, delivered_at TIMESTAMPTZ
);
CREATE INDEX idx_not_tenant_state ON notifications(tenant_id, state, created_at DESC);
CREATE INDEX idx_not_identity ON notifications(recipient_identity, created_at DESC);
-- partitions by month from V2 if > 10M rows (delivery logs NOT-12 = same table)

CREATE TABLE notification_suppressions (        -- V2 NOT-26/16
  id            ULID PRIMARY KEY,
  tenant_id     ULID NOT NULL,
  identity_id   ULID NOT NULL,
  channel       TEXT NOT NULL,
  reason        TEXT NOT NULL,                 -- bounce|complaint|unsub|manual
  until         TIMESTAMPTZ,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, identity_id, channel, reason)
);

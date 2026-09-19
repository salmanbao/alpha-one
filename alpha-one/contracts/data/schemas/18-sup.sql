-- 18 — SUP: DDL split from docs/32-database-design.md (source: docs/18-support.md §9). docs/32 is the source of truth; delivered through versioned migrations (OPS-06, expand-contract discipline).
CREATE TABLE ticket_categories (          -- registry (data; V2 tenant-editable)
  id          ULID PRIMARY KEY,
  tenant_id   ULID,                        -- NULL = platform default
  key         TEXT NOT NULL,               -- 'account'|'payment'|…
  label       TEXT NOT NULL,
  sla_hours   INT NOT NULL DEFAULT 24,     -- V2: per priority
  enabled     BOOLEAN NOT NULL DEFAULT true,
  UNIQUE (tenant_id, key)
);

CREATE TABLE tickets (
  id                ULID PRIMARY KEY,
  tenant_id         ULID NOT NULL,
  category          TEXT NOT NULL,
  status            TEXT NOT NULL DEFAULT 'open'
    CHECK (status IN ('open','in_progress','resolved','closed','cancelled')),
  priority          TEXT NOT NULL DEFAULT 'normal'
    CHECK (priority IN ('low','normal','high','critical')),
  subject           TEXT NOT NULL,
  identity_id       ULID NOT NULL,         -- the trader
  account_id        ULID,
  object_refs       JSONB NOT NULL DEFAULT '{}',
  created_by        TEXT NOT NULL,         -- 'trader' | 'staff'
  assignee_id       ULID,                  -- V2
  first_response_at TIMESTAMPTZ,
  sla_due_at        TIMESTAMPTZ NOT NULL,
  resolved_at       TIMESTAMPTZ, closed_at TIMESTAMPTZ,
  satisfaction      SMALLINT, satisfaction_comment TEXT,   -- V2
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_tick_tenant_status ON tickets(tenant_id, status, created_at DESC);
CREATE INDEX idx_tick_identity ON tickets(tenant_id, identity_id, created_at DESC);
CREATE INDEX idx_tick_account ON tickets(account_id) WHERE account_id IS NOT NULL;

CREATE TABLE ticket_messages (
  id            ULID PRIMARY KEY,
  tenant_id     ULID NOT NULL,
  ticket_id     ULID NOT NULL REFERENCES tickets(id),
  kind          TEXT NOT NULL CHECK (kind IN ('trader','staff','internal','system')),
  body          TEXT NOT NULL,
  attachment_refs JSONB NOT NULL DEFAULT '[]',
  author_id     ULID,                      -- NULL for system
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_tmsg_ticket ON ticket_messages(ticket_id, created_at);

CREATE TABLE ticket_attachments (
  id          ULID PRIMARY KEY,
  tenant_id   ULID NOT NULL,
  r2_key      TEXT NOT NULL,               -- support/{tenant}/{ticket}/{n}
  bytes       BIGINT NOT NULL,
  content_type TEXT NOT NULL,
  scan_state  TEXT NOT NULL DEFAULT 'unscanned'   -- V2: scanned|infected
    CHECK (scan_state IN ('unscanned','scanned','infected')),
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

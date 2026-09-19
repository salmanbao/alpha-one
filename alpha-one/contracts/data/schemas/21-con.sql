-- 21 — CON: DDL split from docs/32-database-design.md (source: docs/21-console.md §9). docs/32 is the source of truth; delivered through versioned migrations (OPS-06, expand-contract discipline).
CREATE TABLE console_controls (                  -- control state (source of
  control     TEXT PRIMARY KEY,                  -- truth for what's armed)
  tenant_id   ULID,                              -- NULL = platform-wide
  state       TEXT NOT NULL DEFAULT 'disarmed'
    CHECK (state IN ('disarmed','pending_approval','active')),
  armed_by    ULID, approved_by ULID,
  armed_at    TIMESTAMPTZ, approved_at TIMESTAMPTZ,
  runbook     TEXT NOT NULL,                     -- the link shown in dialogs
  note        TEXT                               -- required on release
);
CREATE TABLE console_impersonations (            -- V2 audit table (AUD mirrors
  id          ULID PRIMARY KEY,                  -- it too)
  tenant_id   ULID NOT NULL, identity_id ULID NOT NULL,
  operator_id ULID NOT NULL,
  started_at  TIMESTAMPTZ NOT NULL, ends_at TIMESTAMPTZ NOT NULL,
  renewed     INT NOT NULL DEFAULT 0
);
CREATE TABLE console_announcements (             -- V2 CON-14
  id          ULID PRIMARY KEY,
  scope       TEXT NOT NULL,                     -- 'platform' | tenant_id
  title       TEXT NOT NULL, body TEXT NOT NULL,
  visible_from TIMESTAMPTZ, visible_to TIMESTAMPTZ,
  created_by  ULID, created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- everything else (tenants, sagas, entitlements, audit, jobs) is read from
-- TEN/OPS/AUD/ANA — the console renders, it doesn't store.

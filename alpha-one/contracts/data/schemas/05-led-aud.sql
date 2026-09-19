-- 05 — LED/AUD: DDL split from docs/32-database-design.md (source: docs/05-ledger-audit.md §9). docs/32 is the source of truth; delivered through versioned migrations (OPS-06, expand-contract discipline).
ALTER TABLE journal_entry ADD CONSTRAINT chk_entry_balanced
  CHECK (true);  -- enforced by trigger:
CREATE FUNCTION trg_entry_balance() RETURNS trigger AS $$
BEGIN
  IF (SELECT COALESCE(SUM(debit_cents),0) - COALESCE(SUM(credit_cents),0)
      FROM journal_line WHERE entry_id = NEW.id) <> 0 THEN
    RAISE EXCEPTION 'journal entry % is not balanced', NEW.id;
  END IF;
  RETURN NEW;
END $$ LANGUAGE plpgsql;
-- trigger AFTER INSERT OR UPDATE OF entry on journal_entry (checks its lines)

CREATE TABLE accounts (
  id         ULID PRIMARY KEY,
  tenant_id  ULID REFERENCES tenants(id),      -- NULL = platform-level
  code       TEXT NOT NULL,
  name       TEXT NOT NULL,
  type       TEXT NOT NULL CHECK (type IN ('asset','liability','equity','revenue','expense')),
  currency   CHAR(3) NOT NULL DEFAULT 'USD',
  is_system  BOOLEAN NOT NULL DEFAULT true,
  closed_at  TIMESTAMPTZ,
  UNIQUE (COALESCE(tenant_id,'00000000-0000-0000-0000-000000000000'::ulid_placeholder), code)
);  -- in practice: UNIQUE (tenant_id, code) with a platform sentinel row

CREATE TABLE journal_entry (
  id               ULID PRIMARY KEY,
  tenant_id        ULID NOT NULL,
  idempotency_key  TEXT NOT NULL UNIQUE,
  reason_code      TEXT NOT NULL,
  ref_type         TEXT, ref_id TEXT,
  description      TEXT,
  reverses_entry_id ULID REFERENCES journal_entry(id),
  prev_entry_hash  TEXT,                        -- V2 hash chain
  posted_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  posted_by        ULID                         -- identity or system sentinel
);
CREATE INDEX idx_jentry_tenant_time ON journal_entry(tenant_id, posted_at DESC);
CREATE INDEX idx_jentry_ref ON journal_entry(ref_type, ref_id);

CREATE TABLE journal_line (
  id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  entry_id     ULID NOT NULL REFERENCES journal_entry(id) ON DELETE RESTRICT,
  account_id   ULID NOT NULL REFERENCES accounts(id),
  debit_cents  BIGINT NOT NULL DEFAULT 0 CHECK (debit_cents >= 0),
  credit_cents BIGINT NOT NULL DEFAULT 0 CHECK (credit_cents >= 0),
  currency     CHAR(3) NOT NULL DEFAULT 'USD',
  memo         TEXT,
  CHECK (debit_cents = 0 OR credit_cents = 0)   -- one side only
);
CREATE INDEX idx_jline_account_time ON journal_line(account_id, entry_id);
-- + balance-check trigger (§3.2). App role: INSERT only on both tables.

CREATE TABLE audit_events (
  id            BIGINT GENERATED ALWAYS AS IDENTITY,
  seq           BIGINT NOT NULL,                  -- per-tenant monotonic (app-assigned via Redis INCR; V2: PG sequence per tenant for chain)
  tenant_id     ULID,                             -- NULL = platform-level
  actor_id      ULID,
  actor_kind    TEXT NOT NULL CHECK (actor_kind IN ('user','service','api_key','system')),
  actor_role    TEXT,
  action        TEXT NOT NULL,                    -- 'payout.approved' style
  resource_type TEXT, resource_id TEXT,
  status        TEXT NOT NULL CHECK (status IN ('success','failure','denied')),
  before        JSONB, after JSONB,               -- redacted at write (AUD-23 rules)
  ip            INET, user_agent TEXT,
  correlation_id ULID,
  request_id    TEXT,
  geo           JSONB,
  tier          TEXT NOT NULL DEFAULT 'standard' CHECK (tier IN ('standard','sensitive','critical')),
  prev_hash     TEXT, entry_hash TEXT,            -- V2 hash chain
  legal_hold    BOOLEAN NOT NULL DEFAULT false,   -- V2
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (id)
) PARTITION BY RANGE (created_at);
CREATE INDEX idx_audit_tenant_time ON audit_events(tenant_id, created_at DESC);
CREATE INDEX idx_audit_actor ON audit_events(tenant_id, actor_id, created_at DESC);
CREATE INDEX idx_audit_action ON audit_events(tenant_id, action, created_at DESC);
CREATE INDEX idx_audit_resource ON audit_events(resource_type, resource_id, created_at DESC);
-- App role: INSERT only. UPDATE/DELETE revoked. REVOKE ALL FROM public.

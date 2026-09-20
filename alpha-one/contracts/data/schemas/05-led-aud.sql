-- 05 — LED/AUD: DDL split from docs/32-database-design.md (source: docs/05-ledger-audit.md §9). docs/32 is the source of truth; delivered through versioned migrations (OPS-06, expand-contract discipline).
CREATE FUNCTION trg_entry_balance() RETURNS trigger AS $$
DECLARE
  eid ULID := COALESCE(NEW.entry_id, OLD.entry_id);
  unbalanced int; mixed int;
BEGIN
  SELECT COALESCE(SUM(debit_cents),0) - COALESCE(SUM(credit_cents),0),
         COUNT(DISTINCT currency)
    INTO unbalanced, mixed
    FROM journal_line WHERE entry_id = eid;
  IF unbalanced <> 0 OR mixed > 1 THEN
    RAISE EXCEPTION 'journal entry % is unbalanced or mixed-currency', eid;
  END IF;
  RETURN NULL;  -- AFTER trigger
END $$ LANGUAGE plpgsql;
CREATE CONSTRAINT TRIGGER trg_lines_balance AFTER INSERT OR UPDATE OR DELETE ON journal_line
  DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION trg_entry_balance();
-- Row-level + deferred = evaluated per touched entry at COMMIT: lines inserted after
-- the entry row are all present when the check runs; statement-level shortcuts are
-- what broke the earlier sketch (an AFTER INSERT trigger on journal_entry fires
-- before any line exists — finding F1, docs/48).
-- One currency per entry (§3.2 rule 4) rides the same check (F6).
-- The app role also gets INSERT-only (§9): corrections are reversal entries, never edits.

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
  prev_hash     TEXT, entry_hash TEXT,            -- V2 hash chain; `seq BIGINT`
                                                  -- (per-tenant monotonic) joins at chain
                                                  -- init (AUD-14), backfilled in id order —
                                                  -- decision D27, docs/48: V1 carries no seq,
                                                  -- so the fail-closed audit write is one
                                                  -- INSERT with no Redis dependency
  legal_hold    BOOLEAN NOT NULL DEFAULT false,   -- V2
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (id, created_at)                    -- partitioned tables must carry the
                                                  -- partition key in every unique/PK
                                                  -- constraint (finding F2, docs/48)
) PARTITION BY RANGE (created_at);
CREATE INDEX idx_audit_tenant_time ON audit_events(tenant_id, created_at DESC);
CREATE INDEX idx_audit_actor ON audit_events(tenant_id, actor_id, created_at DESC);
CREATE INDEX idx_audit_action ON audit_events(tenant_id, action, created_at DESC);
CREATE INDEX idx_audit_resource ON audit_events(resource_type, resource_id, created_at DESC);
-- Immutability (docs/32 convention, 28 §3.3): BEFORE DELETE/UPDATE triggers raise,
-- and the app role holds INSERT + SELECT only — the DDL the convention cites:
CREATE FUNCTION trg_ledger_no_mutation() RETURNS trigger AS $$
BEGIN RAISE EXCEPTION '% on % is not permitted', TG_OP, TG_TABLE_NAME; END
$$ LANGUAGE plpgsql;
CREATE TRIGGER no_mutate_journal  BEFORE UPDATE OR DELETE ON journal_entry  FOR EACH STATEMENT EXECUTE FUNCTION trg_ledger_no_mutation();
CREATE TRIGGER no_mutate_jline    BEFORE UPDATE OR DELETE ON journal_line    FOR EACH STATEMENT EXECUTE FUNCTION trg_ledger_no_mutation();
CREATE TRIGGER no_mutate_audit    BEFORE UPDATE OR DELETE ON audit_events    FOR EACH STATEMENT EXECUTE FUNCTION trg_ledger_no_mutation();

-- RLS (D16 model): journal_entry, journal_line and the tenant rows of audit_events
-- are tenant-owned — ENABLE/FORCE ROW LEVEL SECURITY on app.tenant_id (fail-closed),
-- written by the appliers with per-message context (decision W). Rows with
-- tenant_id IS NULL (platform CoA accounts, platform audit rows) are guard-only and
-- reachable through the app_platform services (audit-applier, CON read models) —
-- the same named-exemption model as every other module (docs/44 §5, docs/47 §7).

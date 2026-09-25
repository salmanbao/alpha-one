-- 09 — EVL: DDL split from docs/32-database-design.md (source: docs/09-evaluation-engine.md §9). docs/32 is the source of truth; delivered through versioned migrations (OPS-06, expand-contract discipline).
CREATE TABLE rule_packs (
  id            ULID PRIMARY KEY,
  tenant_id     ULID NOT NULL,
  name          TEXT NOT NULL,
  version       INT NOT NULL,
  status        TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','active','superseded')),
  rules         JSONB NOT NULL,             -- validated vs contracts schema
  effective_from TIMESTAMPTZ,
  change_reason TEXT,
  created_by    ULID,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, name, version)
);

CREATE TABLE evaluations (                     -- "evaluated" record (EVL-49)
  id            ULID PRIMARY KEY,
  account_id    ULID NOT NULL,
  tenant_id     ULID NOT NULL,
  tick_event_id ULID NOT NULL,                -- → events.event_id (observed ref)
  input_hash    TEXT NOT NULL,
  rule_pack_id  ULID NOT NULL, rule_pack_version INT NOT NULL,
  status        TEXT NOT NULL CHECK (status IN ('ok','breach','target_hit','target_hit_pending','gap_flagged')),
  rule_id       TEXT,
  detail        JSONB NOT NULL,               -- evidence: metrics at decision time
  state_version BIGINT NOT NULL,              -- EvalState version used
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_evals_account ON evaluations(account_id, created_at DESC);
CREATE INDEX idx_evals_breach ON evaluations(tenant_id, status, created_at) WHERE status IN ('breach','target_hit');

-- evaluation_state — owned and written ONLY by the `workers` evaluation
-- consumer (D81, docs/64 §4.1): one writer per account, structurally (the
-- account's serial lane inside its tenant's lane set, D82).
--
-- `state` is the engine's account document, opaque to workers: workers
-- reads it, sends it to the stateless engine's /evaluate with the tick,
-- and writes back `new_state`. The projected columns exist for the readers
-- that must not parse engine JSON (the bridge's floor-hint reload, CON/TD
-- status, the load-shed priority list) and for the single-writer guard
-- (`version`). The pre-D81 column-per-counter layout (day_start_equity_cents,
-- high_water_equity_cents, …) duplicated engine state in a second schema
-- that nothing kept in step; it is replaced, not extended.
--
-- D83 (docs/64 §4.8, docs/29 §3.4): HASH(tenant_id) into 64 partitions.
-- Every hot-path statement is keyed (tenant_id, account_id) and prunes to
-- one partition; the same key is the Citus distribution key if the staged
-- trigger ever fires.
CREATE TABLE evaluation_state (
  tenant_id             ULID NOT NULL,
  account_id            ULID NOT NULL,
  rule_pack_id          ULID NOT NULL, rule_pack_version INT NOT NULL,
  state                 JSONB NOT NULL,        -- engine account document (opaque)
  plan                  JSONB NOT NULL,        -- bound plan document (engine-shaped)
  status                TEXT NOT NULL,         -- projected: last verdict status
  funded                BOOLEAN NOT NULL DEFAULT false,  -- projected: priority list (docs/63 §4.7)
  breach_rule_id        TEXT, breach_at TIMESTAMPTZ,
  last_tick_event_id    ULID,                  -- the tick that produced this version
  last_stream_seq       BIGINT,
  last_tick_at          TIMESTAMPTZ,           -- envelope occurred_at of that tick
  floor_daily_cents     BIGINT,                -- §3.8 floor hints (D79): advisory, bridge
  floor_total_cents     BIGINT,                -- conflation only — never read back by the
  target_equity_cents   BIGINT,                -- engine; NULL = no hint (bridge heartbeats)
  floors_version        BIGINT NOT NULL DEFAULT 0,  -- = the `version` the hints came from
  version               BIGINT NOT NULL DEFAULT 0,  -- single-writer guard: UPDATE … WHERE version = $old
  updated_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (tenant_id, account_id)
) PARTITION BY HASH (tenant_id);
DO $$
BEGIN
  FOR b IN 0..63 LOOP
    EXECUTE format(
      'CREATE TABLE evaluation_state_h%s PARTITION OF evaluation_state
         FOR VALUES WITH (MODULUS 64, REMAINDER %s)', b, b);
  END LOOP;
END $$;
-- The bridge's hint reload (every 30 s, and on cache miss) reads from the
-- replica: SELECT account_id, floor_daily_cents, floor_total_cents,
-- target_equity_cents, floors_version FROM evaluation_state WHERE tenant_id = $1.

CREATE TABLE evaluation_overrides (
  id            ULID PRIMARY KEY,
  account_id    ULID NOT NULL,
  tenant_id     ULID NOT NULL,
  verdict_id    ULID NOT NULL REFERENCES evaluations(id),
  kind          TEXT NOT NULL CHECK (kind IN ('clear_breach','manual_run','emergency')),
  reason        TEXT NOT NULL,
  actor_id      ULID NOT NULL,
  correlation_id ULID,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- D84 load-shed level per tenant (docs/63 §4.14). workers' ladder writes it
-- on every level change; the bridge reloads it every 30 s as the fallback
-- when evl.load_shed pub/sub is missed (the evl.floors pattern), and a new
-- stream owner resumes from it after a lease handover instead of resetting
-- the tenant to level 0 mid-incident. One row per tenant: tiny, unpartitioned.
CREATE TABLE evl_load_shed (
  tenant_id       ULID PRIMARY KEY,
  level           SMALLINT NOT NULL CHECK (level BETWEEN 0 AND 3),
  reason          TEXT NOT NULL,
  level1_at       TIMESTAMPTZ,          -- when level first left 0 (the 15-min L1→L2 rule)
  incident_until  TIMESTAMPTZ,          -- INCIDENT hold (≥ 10 min after the cause)
  changed_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

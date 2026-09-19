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

CREATE TABLE evaluation_state (                -- "evaluated" counters (single writer)
  account_id            ULID PRIMARY KEY,
  tenant_id             ULID NOT NULL,
  rule_pack_id          ULID NOT NULL, rule_pack_version INT NOT NULL,
  initial_balance_cents BIGINT NOT NULL,
  day_key               DATE NOT NULL,
  day_start_equity_cents BIGINT NOT NULL,
  daily_loss_max_cents  BIGINT NOT NULL DEFAULT 0,
  high_water_equity_cents BIGINT NOT NULL,     -- EVL-29
  max_total_loss_used_cents BIGINT NOT NULL DEFAULT 0,
  profit_cents          BIGINT NOT NULL DEFAULT 0,
  trading_days          INT NOT NULL DEFAULT 0,
  calendar_days         INT NOT NULL DEFAULT 0,
  started_at            TIMESTAMPTZ NOT NULL,
  daily_pnls            JSONB NOT NULL DEFAULT '[]',
  target_reached_at     TIMESTAMPTZ,
  target_hit_pending    BOOLEAN NOT NULL DEFAULT false,
  breach_rule_id        TEXT, breach_at TIMESTAMPTZ,
  version               BIGINT NOT NULL DEFAULT 0
);

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

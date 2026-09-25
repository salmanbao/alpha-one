-- 04 — GW+EVT: DDL split from docs/32-database-design.md (source: docs/04-gateway-events.md §9). docs/32 is the source of truth; delivered through versioned migrations (OPS-06, expand-contract discipline).
CREATE TABLE outbox (
  event_id      ULID PRIMARY KEY,
  topic         TEXT NOT NULL,              -- 'account','bridge','payout',...
  payload       JSONB NOT NULL,             -- full envelope
  tenant_id     ULID NOT NULL,
  entity_id     TEXT NOT NULL,              -- routing key (ordering lane)
  correlation_id ULID,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  published_at  TIMESTAMPTZ,
  publish_attempt INT NOT NULL DEFAULT 0
);
CREATE INDEX idx_outbox_unpublished ON outbox(event_id) WHERE published_at IS NULL;
-- (was `outbox(id)`: the table has no `id` column — the key is `event_id`, a
-- ULID, so ORDER BY event_id is creation order. docs/04 §3.3 says the same.)

CREATE TABLE events (
  event_id      ULID,
  seq           BIGINT GENERATED ALWAYS AS IDENTITY,   -- global append order, assigned by the
                                                       -- INSERT (the relay is the single writer;
                                                       -- NO Redis counter in the durable path —
                                                       -- the D27 lesson, docs/48); V2 CON replay
                                                       -- addresses seq ranges
  topic         TEXT NOT NULL,
  tenant_id     ULID NOT NULL,
  entity_id     TEXT NOT NULL,
  type          TEXT NOT NULL,
  version       INT NOT NULL,
  occurred_at   TIMESTAMPTZ NOT NULL,
  correlation_id ULID,
  payload       JSONB NOT NULL,
  appended_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (topic, event_id, occurred_at)
) PARTITION BY RANGE (occurred_at);
-- Partition key = occurred_at (was appended_at). Postgres requires the
-- partition key in every unique constraint, and the previous
-- `PRIMARY KEY (topic, event_id) … PARTITION BY RANGE (appended_at)` did not
-- apply. occurred_at is an envelope field — immutable per event — so a
-- re-appended event carries the same key and (topic, event_id, occurred_at)
-- dedupes exactly as (topic, event_id) did; appended_at is assigned per
-- INSERT and would not. Day partitions; the bridge.tick ≤ 7-day hot window
-- (docs/63 F13) and the workers trim-replay (D82) both prune on it.
CREATE INDEX idx_events_tenant_type ON events(tenant_id, type, occurred_at);
CREATE INDEX idx_events_entity ON events(entity_id, occurred_at);

CREATE TABLE consumer_state (
  consumer      TEXT NOT NULL,
  event_id      ULID NOT NULL,
  status        TEXT NOT NULL DEFAULT 'processing',
  attempts      INT NOT NULL DEFAULT 1,
  last_error    TEXT,
  processed_at  TIMESTAMPTZ,
  PRIMARY KEY (consumer, event_id)
);

CREATE TABLE provider_events (           -- ingress idempotency (EVT-10)
  provider      TEXT NOT NULL,
  provider_event_id TEXT NOT NULL,
  tenant_id     ULID,
  payload_hash  TEXT NOT NULL,
  status        TEXT NOT NULL DEFAULT 'processed',
  received_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (provider, provider_event_id)
);

CREATE TABLE tenant_webhooks (           -- V2
  id            ULID PRIMARY KEY,
  tenant_id     ULID NOT NULL REFERENCES tenants(id),
  url           TEXT NOT NULL,
  events        TEXT[] NOT NULL,         -- filters, e.g. {'payout.*','account.*'}
  secret_enc    TEXT NOT NULL,           -- field-encrypted
  secret_ver    INT NOT NULL DEFAULT 1,
  active        BOOLEAN NOT NULL DEFAULT true,
  retry_policy  JSONB NOT NULL DEFAULT '{"max_retries":8,"max_backoff_s":3600}',
  disabled_reason TEXT,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

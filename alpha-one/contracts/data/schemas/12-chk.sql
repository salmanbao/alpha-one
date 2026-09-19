-- 12 — CHK: DDL split from docs/32-database-design.md (source: docs/12-checkout-billing.md §9). docs/32 is the source of truth; delivered through versioned migrations (OPS-06, expand-contract discipline).
CREATE TABLE orders (
  id              ULID PRIMARY KEY,
  tenant_id       ULID NOT NULL,
  identity_id     ULID NOT NULL,
  status          TEXT NOT NULL DEFAULT 'open'
    CHECK (status IN ('open','paid','provisioning','fulfilled',
                      'failed_provisioning','abandoned')),
  line_items      JSONB NOT NULL,            -- frozen: package_id, rule_set_id,
                                             -- base_cents, currency, fx_rate, total
  amount_cents    BIGINT NOT NULL,
  currency        CHAR(3) NOT NULL,
  intent_ids      ULID[],
  invoice_id      TEXT,                      -- DOC object key
  saga_id         TEXT,                      -- LCC provisioning saga (EVT-17)
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  paid_at         TIMESTAMPTZ, fulfilled_at TIMESTAMPTZ,
  closed_at       TIMESTAMPTZ
);
CREATE INDEX idx_ord_tenant ON orders(tenant_id, created_at DESC);
CREATE INDEX idx_ord_identity ON orders(tenant_id, identity_id, status);

CREATE TABLE payment_intents (
  id              ULID PRIMARY KEY,
  tenant_id       ULID NOT NULL,
  order_id        ULID NOT NULL REFERENCES orders(id),
  provider        TEXT NOT NULL,             -- match2pay|interkasa|nowpayments|wire
  method          TEXT NOT NULL,             -- card|local:{kind}|crypto:{chain}|wire
  amount_cents    BIGINT NOT NULL,
  currency        CHAR(3) NOT NULL,
  status          TEXT NOT NULL DEFAULT 'created'
    CHECK (status IN ('created','pending','captured','failed','expired')),
  provider_ref    TEXT,                      -- provider's transaction id
  fee_cents       BIGINT, fee_currency CHAR(3),   -- from webhook (recon-verified)
  capture_at      TIMESTAMPTZ, expires_at TIMESTAMPTZ NOT NULL,
  idempotency_key TEXT UNIQUE,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_pint_tenant_status ON payment_intents(tenant_id, status, created_at DESC);
CREATE INDEX idx_pint_provider_ref ON payment_intents(provider, provider_ref);

CREATE TABLE refunds (
  id              ULID PRIMARY KEY,
  tenant_id       ULID NOT NULL,
  intent_id       ULID NOT NULL REFERENCES payment_intents(id),
  order_id        ULID NOT NULL,
  kind            TEXT NOT NULL,             -- trader|manual|auto_breach|chargeback
  status          TEXT NOT NULL DEFAULT 'refund_requested'
    CHECK (status IN ('refund_requested','provider_pending','refunded',
                      'failed','cancelled')),
  amount_cents    BIGINT NOT NULL,
  currency        CHAR(3) NOT NULL,
  reason          TEXT,
  provider_ref    TEXT,
  requested_by    ULID,                      -- identity (trader) or staff or 'system'
  provider_at     TIMESTAMPTZ, settled_at TIMESTAMPTZ,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_rfd_tenant ON refunds(tenant_id, status, created_at DESC);
CREATE INDEX idx_rfd_intent ON refunds(intent_id);

-- provider report files: R2 (reports/{provider}/{date}.csv) + a small
-- recon_runs table (provider, date, file_key, matched, exceptions[]) on V2

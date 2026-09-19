-- Checkout domain schema
-- Owner module: CHK
-- Derives from Req IDs: CHK-02, CHK-07, CHK-08, CHK-09, CHK-42, CHK-43, CHK-44
-- Conventions: shared schema with tenant_id on every tenant-scoped row (Out Of Scope sheet);
-- migrations via OPS-06 expand-contract (Drizzle ORM primary, BVR-08).
-- Enums marked TODO are not fixed by the V1 sheet — see contracts/data/dictionary.md open questions.

CREATE TABLE checkout_sessions (
  id uuid PRIMARY KEY,
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  trader_id uuid REFERENCES users(id),                        -- CHK-02; TODO nullable = guest checkout decision open
  challenge_id uuid NOT NULL REFERENCES challenges(id),       -- CHK-01, CHK-02
  reserved_price numeric NOT NULL,                            -- CHK-02 reserves price
  coupon_code text,                                           -- CHK-02 reserves coupon; coupon storage — TODO
  state text NOT NULL,                                        -- CHK-43 expires sessions, CHK-44 cancels them (Decision 7); enum values — TODO
  reservation_expires_at timestamptz NOT NULL,                -- CHK-02 limited window; duration — TODO
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
  -- TODO: add-ons representation (TD-09 implies add-ons; CHK rows do not define them)
);

CREATE INDEX idx_checkout_sessions_expiry ON checkout_sessions (reservation_expires_at);
CREATE INDEX idx_checkout_sessions_trader ON checkout_sessions (trader_id);

CREATE TABLE payments (
  id uuid PRIMARY KEY,
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  order_id uuid NOT NULL REFERENCES orders(id),               -- CHK-07/CHK-08
  provider text NOT NULL,                                     -- CHK-04 adapters
  provider_event_id text NOT NULL,                            -- CHK-07 idempotency (EVT-10 dedupe)
  status text NOT NULL,                                       -- CHK-07 "transition payment state"; TODO enum
  amount numeric NOT NULL,                                    -- CHK-08
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
  -- TODO: failed-payment record fields (CHK-16, V1.1)
);

-- Idempotency: duplicate webhooks never double-create orders (CHK-07)
CREATE UNIQUE INDEX uq_payments_provider_event ON payments (provider, provider_event_id);
CREATE INDEX idx_payments_order ON payments (order_id);

CREATE TABLE orders (
  id uuid PRIMARY KEY,
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  trader_id uuid NOT NULL REFERENCES users(id),               -- CHK-08 customer
  type text NOT NULL,                                         -- CHK-08; TODO enum
  amount numeric NOT NULL,                                    -- CHK-08
  method text NOT NULL,                                       -- CHK-08 payment method
  coupon text,                                                -- CHK-08
  customer_ip inet,                                           -- CHK-08
  utm jsonb,                                                  -- CHK-08; TODO structure
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
  -- TODO: challenge/size/add-ons purchased (implied by CHK-01/TD-09; not in CHK-08 field list)
  -- TODO: order number scheme (CHK-40 invoice reference)
);

CREATE INDEX idx_orders_tenant_created ON orders (tenant_id, created_at);
CREATE INDEX idx_orders_trader ON orders (trader_id);

-- Downstream: payment captured emits order.paid (CHK-09) consumed by LCC-05, LED-04, ANA-01.

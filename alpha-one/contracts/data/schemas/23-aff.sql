-- 23 — AFF: DDL split from docs/32-database-design.md (source: docs/23-affiliates.md §9). docs/32 is the source of truth; delivered through versioned migrations (OPS-06, expand-contract discipline).
CREATE TABLE affiliates (
  id          ULID PRIMARY KEY,
  tenant_id   ULID,                          -- NULL = platform program
  identity_id ULID NOT NULL,                 -- the person (KYC L2 required)
  status      TEXT NOT NULL DEFAULT 'applied'
    CHECK (status IN ('applied','approved','active','suspended','terminated')),
  code        TEXT NOT NULL UNIQUE,          -- the ref code
  agreement_ref TEXT,                        -- DOC: signed agreement
  approved_by ULID, approved_at TIMESTAMPTZ,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE affiliate_rate_cards (
  id          ULID PRIMARY KEY,
  affiliate_id ULID NOT NULL,
  owner       TEXT NOT NULL DEFAULT 'platform',   -- platform | tenant:{id}
  challenge_bps INT NOT NULL,
  first_payouts_bonus JSONB,
  tier_multipliers JSONB NOT NULL DEFAULT '{}',
  caps        JSONB NOT NULL,
  effective_from TIMESTAMPTZ NOT NULL, effective_to TIMESTAMPTZ,
  created_by  ULID,
  UNIQUE (affiliate_id, effective_from)
);
CREATE TABLE identity_affiliation (           -- the attribution record
  tenant_id   ULID NOT NULL,
  identity_id ULID NOT NULL,
  affiliate_id ULID NOT NULL,
  method      TEXT NOT NULL,                  -- link|coupon
  attributed_at TIMESTAMPTZ NOT NULL,
  voided      BOOLEAN NOT NULL DEFAULT false, -- self-referral catch
  void_reason TEXT,
  PRIMARY KEY (tenant_id, identity_id)       -- one attribution, immutable
);
CREATE TABLE affiliate_accruals (
  id            ULID PRIMARY KEY,
  tenant_id     ULID NOT NULL,
  affiliate_id  ULID NOT NULL,
  identity_id   ULID NOT NULL,                -- the referred trader
  order_id      ULID,                          -- basis: purchase
  basis         TEXT NOT NULL,                -- purchase|payout_bonus
  card_version  ULID NOT NULL,
  rate_bps      INT NOT NULL,
  gross_cents   BIGINT NOT NULL,
  commission_cents BIGINT NOT NULL,
  status        TEXT NOT NULL DEFAULT 'accrued'
    CHECK (status IN ('accrued','settled','reversed','cancelled')),
  captured_at   TIMESTAMPTZ NOT NULL, settled_at TIMESTAMPTZ,
  reversal_ref  TEXT,                          -- the refund/chargeback id
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_affacc_affiliate ON affiliate_accruals(affiliate_id, status, captured_at DESC);
CREATE INDEX idx_affacc_order ON affiliate_accruals(order_id);
-- payouts: affiliate_payouts + affiliate_payout_executions (the PAY-12
-- pattern, §3.4); affiliate_methods (field-encrypted, PAY-pattern)

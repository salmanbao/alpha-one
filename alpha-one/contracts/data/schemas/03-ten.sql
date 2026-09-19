-- 03 — TEN: DDL split from docs/32-database-design.md (source: docs/03-tenant-management.md §9). docs/32 is the source of truth; delivered through versioned migrations (OPS-06, expand-contract discipline).
CREATE TABLE tenants (
  id            ULID PRIMARY KEY,
  slug          VARCHAR(63) UNIQUE NOT NULL,
  parent_id     ULID REFERENCES tenants(id),      -- ADR-2 door, NULL in V1
  firm_name     VARCHAR(255) NOT NULL,
  legal_entity_name VARCHAR(255), registration_number VARCHAR(100), tax_id VARCHAR(100),
  jurisdiction  CHAR(2) NOT NULL DEFAULT 'PK',
  kyb_status    TEXT NOT NULL DEFAULT 'pending' CHECK (kyb_status IN ('pending','verified','failed')),
  kyb_verified_at TIMESTAMPTZ,
  primary_contact JSONB NOT NULL DEFAULT '{}',     -- {name,email,phone}
  support_email TEXT,
  status        TEXT NOT NULL DEFAULT 'pending_approval'
    CHECK (status IN ('pending_approval','provisioning','provisioning_failed','onboarding',
                      'active','suspended','deactivated','pending_deletion','archived','deleted')),
  plan          TEXT NOT NULL DEFAULT 'manual',     -- contract ref V1; BIL plan id V3
  limits        JSONB NOT NULL DEFAULT '{}',
  settings      JSONB NOT NULL DEFAULT '{}',        -- validated vs contracts schema
  branding      JSONB NOT NULL DEFAULT '{}',
  features      JSONB NOT NULL DEFAULT '{}',        -- denormalized entitlements snapshot
  onboarding_state JSONB NOT NULL DEFAULT '{"completedSteps":[]}',
  data_region   VARCHAR(20) NOT NULL DEFAULT 'eu-hetzner',
  suspended_at  TIMESTAMPTZ, suspension_reason TEXT,
  created_by    ULID,                                -- platform staff identity
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  activated_at  TIMESTAMPTZ, suspended_reason TEXT,
  deletion_scheduled_at TIMESTAMPTZ
);
CREATE INDEX idx_tenants_status ON tenants(status);
CREATE INDEX idx_tenants_parent ON tenants(parent_id) WHERE parent_id IS NOT NULL;

CREATE TABLE domain_mappings (
  id            ULID PRIMARY KEY,
  tenant_id     ULID NOT NULL REFERENCES tenants(id),
  domain        VARCHAR(255) UNIQUE NOT NULL,
  type          TEXT NOT NULL CHECK (type IN ('subdomain','custom')),
  verified      BOOLEAN NOT NULL DEFAULT false,
  verification_token TEXT,            -- TXT record token (custom domain)
  ssl_status    TEXT NOT NULL DEFAULT 'pending',
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE tenant_entitlements (
  id           ULID PRIMARY KEY,
  tenant_id    ULID NOT NULL REFERENCES tenants(id),
  module       TEXT NOT NULL,          -- 'td','adm','not','cmp','sdk',...
  enabled      BOOLEAN NOT NULL DEFAULT true,
  limit_override JSONB,                -- e.g. {"max_rules": 50}
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, module)
);

CREATE TABLE provisioning_jobs (
  id              ULID PRIMARY KEY,
  tenant_id       ULID REFERENCES tenants(id),
  type            TEXT NOT NULL DEFAULT 'provision',
  status          TEXT NOT NULL DEFAULT 'pending'
                  CHECK (status IN ('pending','running','succeeded','failed','needs_resume')),
  current_step    TEXT,
  completed_steps JSONB NOT NULL DEFAULT '[]',
  failed_step     TEXT, error_message  TEXT,
  context         JSONB NOT NULL DEFAULT '{}',
  started_at      TIMESTAMPTZ, completed_at TIMESTAMPTZ,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_provjobs_active ON provisioning_jobs(status) WHERE status IN ('pending','running','needs_resume');

CREATE TABLE usage_events (               -- BIL foundation (V3 billing reads these)
  id               ULID,
  tenant_id        ULID NOT NULL,
  metric_name      TEXT NOT NULL,         -- active_traders, funded_accounts, api_calls,
                                          -- storage_gb, payouts_processed, kyc_verifications...
  value            NUMERIC(18,4) NOT NULL,
  unit             TEXT NOT NULL,
  period_started_at TIMESTAMPTZ NOT NULL,
  recorded_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  idempotency_key  TEXT,
  PRIMARY KEY (id)
);
CREATE INDEX idx_usage_tenant_metric ON usage_events(tenant_id, metric_name, period_started_at);

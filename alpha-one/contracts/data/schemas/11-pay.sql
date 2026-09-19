-- 11 — PAY: DDL split from docs/32-database-design.md (source: docs/11-payout-system.md §9). docs/32 is the source of truth; delivered through versioned migrations (OPS-06, expand-contract discipline).
CREATE TABLE payout_methods (                 -- versioned (edit = new row)
  id            ULID PRIMARY KEY,
  tenant_id     ULID NOT NULL,
  identity_id   ULID NOT NULL,                -- trader
  kind          TEXT NOT NULL,                -- crypto_trc20|crypto_erc20|crypto_bep20|local:{p}
  details_enc   JSONB NOT NULL,               -- AES-256-GCM (wallet/account ref)
  key_version   INT NOT NULL DEFAULT 1,
  label         TEXT,                         -- "Main TRON wallet"
  is_default    BOOLEAN NOT NULL DEFAULT false,
  active        BOOLEAN NOT NULL DEFAULT true,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  deactivated_at TIMESTAMPTZ
);
CREATE INDEX idx_pmeth_trader ON payout_methods(tenant_id, identity_id, active);

CREATE TABLE payout_requests (
  id                ULID PRIMARY KEY,
  tenant_id         ULID NOT NULL,
  identity_id       ULID NOT NULL,
  account_id        ULID NOT NULL REFERENCES accounts(id),
  method_id         ULID NOT NULL REFERENCES payout_methods(id),
  method_version_at INT NOT NULL,             -- which method row version (disputes)
  requested_cents   BIGINT,                   -- NULL = everything available
  status            TEXT NOT NULL DEFAULT 'requested'
    CHECK (status IN ('requested','eligibility_checked','pending_approval','approved',
                      'processing','paid','failed','cancelled','rejected')),
    -- PAY-13's exact list (docs/52: 'settled'→'paid'; 'failed_final' is a V2
    -- terminal reason within 'failed'; holds are status_reason='on_hold' flags on
    -- 'approved' — never states, D32)
  status_reason     TEXT,
  -- frozen calc (PAY-02, §3.2)
  calc_snapshot     JSONB NOT NULL,           -- steps + inputs + snapshot versions
  gross_cents       BIGINT NOT NULL,
  trader_share_cents BIGINT NOT NULL,
  fee_cents         BIGINT NOT NULL,
  final_cents       BIGINT NOT NULL,
  currency          CHAR(3) NOT NULL DEFAULT 'USD',
  rail              TEXT NOT NULL,            -- nowpayments|match2pay|interkasa|manual
  -- approval
  approval_required BOOLEAN NOT NULL DEFAULT true,   -- V1: always; V2 toggle
  approved_by       ULID, approved_at TIMESTAMPTZ, approval_note TEXT,
  rejected_by       ULID, rejected_at TIMESTAMPTZ, reject_reason_code TEXT,
  -- execution
  external_ref      TEXT,                     -- provider ref
  executed_at       TIMESTAMPTZ, settled_at TIMESTAMPTZ, failed_at TIMESTAMPTZ,
  attempts          INT NOT NULL DEFAULT 0,
  -- ledger
  obligation_entry_id ULID, settlement_entry_id ULID,
  idempotency_key   TEXT NOT NULL UNIQUE,
  cancelled_by      ULID, cancelled_at TIMESTAMPTZ,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_pay_tenant_status ON payout_requests(tenant_id, status, created_at DESC);
CREATE INDEX idx_pay_account ON payout_requests(tenant_id, account_id, status);
CREATE INDEX idx_pay_identity ON payout_requests(tenant_id, identity_id, created_at DESC);

CREATE TABLE payout_executions (               -- PAY-12 append-only record
  id            ULID PRIMARY KEY,
  payout_id     ULID NOT NULL REFERENCES payout_requests(id),
  tenant_id     ULID NOT NULL,
  attempt       INT NOT NULL,
  action        TEXT NOT NULL,                -- send|webhook|retry|reconcile
  provider      TEXT NOT NULL,
  external_ref  TEXT,
  state         TEXT NOT NULL,                -- sent|confirmed|failed
  provider_resp JSONB,                        -- redacted
  at            TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_pexec_payout ON payout_executions(payout_id, attempt);
-- status history: reuse the AUD pattern (payout.status_changed events mirror to
-- audit_events; a lightweight payout_status_history table is added only if the
-- AUD mirror proves insufficient for queue UX — V1: events + audit suffice)

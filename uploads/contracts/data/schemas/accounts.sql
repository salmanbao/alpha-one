-- Accounts domain schema
-- Owner module: LCC (accounts, account_state_history); rule-set tables owned by EVL
-- Derives from Req IDs: LCC-01, LCC-02, LCC-03, LCC-06, LCC-20, EVL-02, EVL-29, EVL-07, EVL-08
-- Conventions: shared schema with tenant_id on every tenant-scoped row (Out Of Scope sheet);
-- migrations via OPS-06 expand-contract (Drizzle ORM primary, BVR-08).
-- Enums marked TODO are not fixed by the V1 sheet — see contracts/data/dictionary.md open questions.

CREATE TABLE accounts (
  id uuid PRIMARY KEY,
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  trader_id uuid NOT NULL REFERENCES users(id),              -- LCC-01
  status text NOT NULL,                                       -- LCC-02; legal transitions per contracts/api/lcc.md edge list (resolved 2026-09-17):
    -- CREATED|ACTIVE|BREACH_DETECTED|CLOSING|FAILED|PASS_PENDING|
    -- VERIFICATION|AWAITING_ACTIVATION|FUNDED|SUSPENDED|TERMINATED
  phase int NOT NULL CHECK (phase >= 1),                      -- LCC-01 phase — per-challenge ordinal (resolved 2026-09-17);
                                                              -- funded stage is status = FUNDED, ordinal continues past last evaluation phase
  challenge_id uuid NOT NULL REFERENCES challenges(id),       -- LCC-01
  rule_set_version_id uuid NOT NULL REFERENCES rule_set_versions(id), -- EVL-02 version active at creation
  parent_account_id uuid REFERENCES accounts(id),             -- LCC-06 phase lineage
  broker_account_ref text,                                    -- BRG-05 (uniqueness via partial index below)
  broker_group text,                                          -- BRG-12
  leverage int,                                               -- BRG-12
  initial_balance numeric NOT NULL,                           -- PAY-02 available-profit basis
  trailing_hwm numeric,                                       -- EVL-29 persisted high-water mark
  trailing_hwm_basis text NOT NULL,                           -- EVL-29 basis locked at creation; enum values — TODO — needs owner decision
  daily_start_balance numeric,                                -- EVL-07
  daily_reset_at timestamptz,                                 -- EVL-07
  profit_split_pct numeric,                                   -- LCC-20
  payout_frequency text,                                      -- LCC-20; TODO enum
  first_withdrawal_delay_days int,                            -- LCC-20
  next_withdrawal_date date,                                  -- LCC-20, PAY-21
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
  -- TODO: payout-terms locking model (LCC-20 at funding vs PAY-38 config precedence)
);

CREATE INDEX idx_accounts_tenant_status ON accounts (tenant_id, status);
CREATE INDEX idx_accounts_trader ON accounts (trader_id);

-- Postgres UNIQUE allows multiple NULLs; enforce uniqueness only once broker provisioning
-- has completed (LCC-05) — see contracts/data/dictionary.md accounts index note.
CREATE UNIQUE INDEX uq_accounts_broker_ref ON accounts (broker_account_ref) WHERE broker_account_ref IS NOT NULL;

CREATE TABLE account_state_history (
  id uuid PRIMARY KEY,
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  account_id uuid NOT NULL REFERENCES accounts(id),           -- LCC-03
  prior_state text,                                           -- LCC-03; NULL on creation
  new_state text NOT NULL,                                    -- LCC-03
  trigger text NOT NULL,                                      -- LCC-03
  actor_id uuid REFERENCES users(id),                         -- LCC-03
  inputs jsonb,                                               -- LCC-03
  occurred_at timestamptz NOT NULL                            -- LCC-03
  -- append-only: no UPDATE/DELETE path (LCC-03 reconstruction requirement)
);

CREATE INDEX idx_account_state_history_account ON account_state_history (account_id, occurred_at);

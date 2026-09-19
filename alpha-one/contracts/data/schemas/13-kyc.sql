-- 13 — KYC: DDL split from docs/32-database-design.md (source: docs/13-kyc.md §9). docs/32 is the source of truth; delivered through versioned migrations (OPS-06, expand-contract discipline).
CREATE TABLE kyc_sessions (
  id             ULID PRIMARY KEY,
  tenant_id      ULID NOT NULL,
  identity_id    ULID NOT NULL,
  level          TEXT NOT NULL CHECK (level IN ('l1','l2')),
  state          TEXT NOT NULL DEFAULT 'in_session'
    CHECK (state IN ('in_session','in_review','manual_review','verified',
                     'rejected','expired','re_verification_required')),
  provider       TEXT NOT NULL DEFAULT 'veriff',
  provider_case_id TEXT,                     -- Veriff object id
  country_declared CHAR(2), country_ip CHAR(2),
  dob           DATE,                        -- field-encrypted at column level
  identity_data JSONB,                       -- field-encrypted (name, doc, score)
  key_version   INT NOT NULL DEFAULT 1,
  reject_reason_class TEXT,                  -- what the trader sees
  reject_reason_detail TEXT,                 -- staff-only
  decided_by    ULID, decided_at TIMESTAMPTZ,
  override      BOOLEAN NOT NULL DEFAULT false,   -- V2 KYC-18
  session_url_expires_at TIMESTAMPTZ,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_kyc_tenant_identity ON kyc_sessions(tenant_id, identity_id, level, created_at DESC);
CREATE INDEX idx_kyc_queue ON kyc_sessions(tenant_id, state) WHERE state = 'manual_review';

CREATE TABLE kyc_documents (
  id         ULID PRIMARY KEY,
  tenant_id  ULID NOT NULL,
  session_id ULID NOT NULL REFERENCES kyc_sessions(id),
  kind       TEXT NOT NULL,                  -- id_front|id_back|selfie|proof_of_address|manual:{n}
  r2_key     TEXT NOT NULL,                  -- kyc/{tenant}/{session}/{n}
  bytes      BIGINT NOT NULL,
  uploaded_by TEXT NOT NULL,                 -- 'trader' | 'staff'
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_kycdocs_session ON kyc_documents(session_id);

-- no separate verified-record table V1: the latest verified kyc_sessions row
-- per (identity, level) IS the record; history = the other rows (KYC-09).
-- V2 adds kyc_consent (KYC-27) + kyc_reverification triggers (KYC-21).

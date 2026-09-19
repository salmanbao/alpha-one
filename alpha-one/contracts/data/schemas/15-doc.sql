-- 15 — DOC: DDL split from docs/32-database-design.md (source: docs/15-documents.md §9). docs/32 is the source of truth; delivered through versioned migrations (OPS-06, expand-contract discipline).
CREATE TABLE documents (
  id            ULID PRIMARY KEY,
  tenant_id     ULID NOT NULL,
  type          TEXT NOT NULL,               -- challenge_agreement|funded_certificate|…
  ref_kind      TEXT NOT NULL,               -- account|order|payout
  ref_id        ULID NOT NULL,
  identity_id   ULID,                        -- owner (trader docs)
  version       INT NOT NULL DEFAULT 1,
  state         TEXT NOT NULL DEFAULT 'pending'
    CHECK (state IN ('pending','generated','failed')),
  r2_key        TEXT,                        -- documents/{tenant}/{type}/{id}-v{n}.pdf
  vars          JSONB,                       -- rendered vars (PII-safe, for audit/redraw)
  cert_hash     TEXT,                        -- V2: verification hash (certs only)
  fail_reason   TEXT,
  attempts      INT NOT NULL DEFAULT 0,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  generated_at  TIMESTAMPTZ,
  UNIQUE (ref_kind, ref_id, type, version)
);
CREATE INDEX idx_doc_tenant_identity ON documents(tenant_id, identity_id, created_at DESC);
CREATE INDEX idx_doc_ref ON documents(ref_kind, ref_id, type);
CREATE INDEX idx_doc_cert ON documents(cert_hash) WHERE cert_hash IS NOT NULL;

CREATE TABLE document_versions (               -- regeneration history (V2)
  id            ULID PRIMARY KEY,
  document_id   ULID NOT NULL REFERENCES documents(id),
  version       INT NOT NULL,
  r2_key        TEXT NOT NULL,
  reason        TEXT,
  created_by    ULID,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (document_id, version)
);

CREATE TABLE document_triggers (               -- event → doc type mapping (data)
  id            ULID PRIMARY KEY,
  event_type    TEXT NOT NULL,
  doc_type      TEXT NOT NULL,
  enabled       BOOLEAN NOT NULL DEFAULT true,
  UNIQUE (event_type, doc_type)
);

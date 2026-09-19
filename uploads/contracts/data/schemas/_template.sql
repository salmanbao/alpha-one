-- Table: TODO
-- Owner module: TODO
-- Tenant-scoped: TODO
-- Derives from Req IDs: TODO
--
-- Convention (Out Of Scope sheet): one shared schema, tenant_id on every tenant-scoped row.
-- Deliver through versioned migrations with expand-contract discipline (OPS-06, Drizzle ORM per BVR-08).

CREATE TABLE TODO (
  id uuid PRIMARY KEY,
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
  -- TODO: columns (justify each with a Req ID)
);

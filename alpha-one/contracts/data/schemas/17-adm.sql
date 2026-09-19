-- 17 — ADM: NO database tables (FE never touches PG — docs/17-admin-panel.md §9).
-- This file exists so the contracts pack has an explicit entry for every module.
-- ADM's only state is browser-side:
--
--   cookies (AUTH-owned, staff realm, docs/02 §10.3):
--     session cookie — HttpOnly, Secure, SameSite=Lax, staff subdomain scope
--   URL state (docs/17 §9 — the workflow handoff tool):
--     ?status=pending_approval&account=... — shareable queue links; filters are
--       URL-first so a reviewer can hand a queue position to another staffer.
--   localStorage (layout prefs only):
--     adm.layout.*          — column visibility, panel sizes (no data)
--
-- All ADM data is served by domain APIs (PAY queue, KYC review, LCC accounts,
-- EVL challenges, RSK cases, AUD log, TEN config, ANA KPIs) over GW.
-- CSV exports (V1 report surface per docs/00 §6) are generated server-side by
-- the owning module's export endpoint, never from client-side state.

SELECT 1; -- no-op: keeps migration tooling and schema linters satisfied

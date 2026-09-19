-- 16 — TD: NO database tables (binding: FE never touches PG — docs/16-trader-dashboard.md §9).
-- This file exists so the contracts pack has an explicit entry for every module.
-- TD's only state is browser-side, owned by other modules:
--
--   cookies (AUTH-owned, docs/02 §10.3):
--     session cookie — HttpOnly, Secure, SameSite=Lax, Domain={tenant}.alpha1.io, Path=/
--     refresh cookie — SameSite=Strict, Path=/v1/auth/*
--   localStorage (UI prefs only — docs/16 §9):
--     td.chart_theme        — 'light'|'dark' (tenant theme default)
--     td.last_account_id    — last-selected account ULID (display hint only)
--     td.queue_filters      — NOT APPLICABLE (TD has no queues; ADM uses URL state)
--   MUST NOT persist client-side: equity history, credentials, KYC data, payout
--   method details (a leaked profile must not leak financial data — docs/16 §9).
--
-- All TD data is served by domain APIs (LCC/BRG/EVL/PAY/CHK/KYC/DOC/NOT) over GW + SSE.

SELECT 1; -- no-op: keeps migration tooling and schema linters satisfied

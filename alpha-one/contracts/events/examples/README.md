# Extended event examples (illustrative fixtures)

One example instance per extended (post-V1) event schema in `../extended/` (141 files, generated 2026-09-19 by `scripts/complete_contracts_pack.py`).

- **Envelope** fields (`id`, `type`, `version`, `tenant_id`, `occurred_at`) follow EVT-03 and are stable.
- **`payload` is intentionally `{}`**: per-event payload fields are provisional until that phase's contract freeze (docs/99 §12). Use these files as consumer-test scaffolding: copy, fill the payload from the module doc's §4/§8, and assert envelope handling + idempotency-by-`id`.
- V1 baseline payloads (with fixed fields) live in `../payloads/`.

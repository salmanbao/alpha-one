# Trader Dashboard Contract (TD)

Status: DRAFT
Owner: TBD
Version: v1
Last updated: 2026-09-20

Derived from the V1 Execution Sheet (V1.0 / V1.1). Nothing here is final until contract freeze.

## No HTTP contract in V1 — see module spec later
TD is a frontend module. Its V1 rows are screens consuming other modules' contracts:
- TD-02 auth screens — consume `contracts/api/auth.md` (register, login, reset, 2FA management)
- TD-03 overview dashboard — consume `contracts/api/lcc.md` trader account reads (balance, equity, open P&L, phase progress from BRG-07 sync data)
- TD-05 objectives and progress view (V1.1) — consume rule and progress data — resolved 2026-09-20 (docs/59): the LCC trader account read carries the progress meters (docs/16 §8 shape: target_bps, daily/max drawdown, trading time left, target_reached); no separate endpoint.
- TD-09 purchase flow UI — consume `contracts/api/chk.md` (catalog, checkout sessions, hosted payment)
- TD-10 payout section — consume `contracts/api/pay.md` (requests, status, payout methods)

Out Of Scope constraints that shape the UI contract: no WebSocket streaming — the docs/01 §4.3 one-way SSE stream with the TD-11 polling fallback and visible freshness timestamps (the D64 transport: the HttpOnly session cookie flows on EventSource; docs/59); user-toggleable dark/light mode out; multi-language UI out in V1; leaderboards/competitions out; native mobile apps out.

## Open contract questions
- Resolved 2026-09-20 (docs/59): TD-05 progress meters ride the LCC trader account read (docs/16 §8: target_bps, drawdown limits, trading_time_left_s, target_reached) — no separate endpoint.
- Resolved 2026-09-20 (docs/59): the SSE stream is primary; the polling fallback is 5 s (docs/16 §5); freshness = epoch-ms `tick_at`/`as_of` + the relative staleness chip (docs/16 §3.2).

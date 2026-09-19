# Trader Dashboard Contract (TD)

Status: DRAFT
Owner: TBD
Version: v1
Last updated: TODO

Derived from the V1 Execution Sheet (V1.0 / V1.1). Nothing here is final until contract freeze.

## No HTTP contract in V1 — see module spec later
TD is a frontend module. Its V1 rows are screens consuming other modules' contracts:
- TD-02 auth screens — consume `contracts/api/auth.md` (register, login, reset, 2FA management)
- TD-03 overview dashboard — consume `contracts/api/lcc.md` trader account reads (balance, equity, open P&L, phase progress from BRG-07 sync data)
- TD-05 objectives and progress view (V1.1) — consume rule and progress data — TODO — needs owner decision (which endpoint serves objectives/meters; LCC/EVL read shapes do not include it yet)
- TD-09 purchase flow UI — consume `contracts/api/chk.md` (catalog, checkout sessions, hosted payment)
- TD-10 payout section — consume `contracts/api/pay.md` (requests, status, payout methods)

Out Of Scope constraints that shape the UI contract: no WebSocket streaming — polling with visible freshness timestamps; user-toggleable dark/light mode out; multi-language UI out in V1; leaderboards/competitions out; native mobile apps out.

## Open contract questions
- TODO — needs owner decision: endpoint and payload for TD-05 objectives/progress (profit target, daily/max drawdown limits, trading days counter, remaining time) — no V1 API row exposes evaluation progress to traders.
- TODO — needs owner decision: polling cadence and freshness timestamp format for dashboard data (Out Of Scope fixes polling as the contract; values open).

# Screen 41 — Competitions & leaderboard · `/competitions` · F10 · V3.0

> Copy-able UI prompt for the Alpha One trader portal.
> Extracted from `trader-flows-and-screen-prompts.md` (Part 3).
> Source spec: `alpha-one/docs/16-trader-dashboard.md` and the owning module docs.

```prompt
Build the competitions and leaderboard screen for the Alpha One trader portal
(Next.js 15, TypeScript, Tailwind, shadcn/ui). Trading contests run by the firm,
with a leaderboard that is transparent about its freshness and its integrity rules.
This surface is explicitly out of scope for V1 — build it only in the V3 phase.

LAYOUT — a competition list, a competition detail view with a live leaderboard, and
a results/archive view. Max-w-6xl.

COMPETITION CARD — name, the period (start and end dates), the entry type (Free /
Paid with the price), the scoring criterion in plain words ("highest profit
percentage"), the prize structure summary, the eligibility summary, and a status
badge (Upcoming / Live / Ended). A primary "Register" button, or "Join — $X" for
paid entries which routes through the same checkout flow as a challenge.

COMPETITION DETAIL — a header with the name, period, a live countdown to the end,
and the trader's own rank highlighted in the leaderboard. Tabs: Leaderboard /
Rules / Prizes / My entry.

LEADERBOARD — a ranked table: rank, trader (alias by default, with the real name
only where the trader opted into a public profile), the score, and the change since
the last refresh. A visible **"Updated { relative time }"** timestamp is mandatory —
the leaderboard is only trustworthy if its freshness is stated. Rows for breached,
suspended or risk-flagged accounts are excluded from rankings, and a note says so.
Scores freeze at the competition end, and the frozen table is what remains
published. An alias toggle lets the trader control how they appear.

RULES TAB — eligibility (which accounts qualify), the scoring formula, the
tie-breakers, the entry limits per trader, and the multi-account policy stated in
plain words.

PRIZES TAB — the prize table (1st/2nd/3rd and any milestone prizes), the delivery
mechanism for each (account credit, payout, or coupon), and the notification
promise ("winners are notified by email and in-app").

MY ENTRY — the trader's competition account (provisioned separately from their
evaluation accounts, in a dedicated competition group), their current score, their
rank, and a link to the live view for that account.

END & RESULTS — when a competition ends, the view switches to final standings with
the prizes awarded, a "Results are final" note, and the archive of past
competitions browsable underneath.

STATES — a registered trader sees "You're in" with a "View my entry" button; an
ineligible trader sees the specific reason ("requires a funded account"); a full
competition shows "Registration closed". Loading skeletons; a not-found or
cross-tenant id returns the not-found page.

ACCESSIBILITY & MOBILE — the leaderboard is a real table with header scope and
right-aligned numbers, the freshness timestamp is a semantic time element, rank
changes are announced politely, and the table becomes cards under 768 px. No
dark/light toggle in V1.
```

# Screen 42 — Badges & public profile · `/profile/public` · F10 · V3.0

> Copy-able UI prompt for the Alpha One trader portal.
> Extracted from `trader-flows-and-screen-prompts.md` (Part 3).
> Source spec: `alpha-one/docs/16-trader-dashboard.md` and the owning module docs.

```prompt
Build the badges and public-profile screen for the Alpha One trader portal
(Next.js 15, TypeScript, Tailwind, shadcn/ui). Achievement is visible and
shareable, but privacy defaults to off and every disclosure is an explicit,
reversible choice by the trader. This surface is explicitly out of scope for V1.

LAYOUT — two sections: "Your badges" and "Public profile" (with an opt-in switch).
Max-w-3xl.

BADGES — a grid of badge tiles, each with an icon, a name, a one-line description
of how it was earned, and the date earned. Earned badges are full colour; unearned
ones are muted with the criterion shown ("First payout — request and receive your
first payout"). Badge categories: milestones (funded, first payout, payout streak),
competition results, and activity tiers. A count header "12 of 40 earned".

LEVELS & XP (V3) — a progress bar showing the trader's current tier, the XP in the
current tier, and what the next tier unlocks, with a tooltip explaining how XP is
earned (activity, not spend).

PUBLIC PROFILE OPT-IN — a switch, off by default, with a plain explanation of
exactly what becomes visible: the trader's chosen alias, their badge collection,
their aggregate statistics (win rate, profit factor, total funded time), and their
competition placements. The explanation lists what is **never** shown: real name,
email, account numbers, wallet addresses, live equity, or per-trade history. Turning
it on requires an explicit confirmation; turning it off takes effect immediately
and the public URL stops resolving.

PROFILE PREVIEW — a read-only preview card of how the public profile appears to
others, with the public URL displayed and a copy button, plus a "View public page"
link that opens it in a new tab. The public page itself shows no PII, is
rate-limited, and renders a plain not-found for an unknown or opted-out profile.

STATS SELECTION — checkboxes letting the trader choose which aggregate statistics
appear (win rate, profit factor, total trades, funded days, badges). Live equity,
balance and per-trade data are never selectable.

ERROR & EDGE STATES — a failed opt-in reverts the switch with an inline retry; a
public URL for an opted-out trader returns a not-found page rather than a
permission error; badge data that fails to load shows a per-section retry.

ACCESSIBILITY & MOBILE — the opt-in switch is a real switch with a label, the
preview is a semantic article, badges have text names and descriptions (never
icon-only), and the layout is a single column from 320 px. No dark/light toggle.
```

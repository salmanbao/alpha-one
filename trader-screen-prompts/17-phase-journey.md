# Screen 17 — Phase journey · `/accounts/{id}/phases` · F4 · V2.0

> Copy-able UI prompt for the Alpha One trader portal.
> Extracted from `trader-flows-and-screen-prompts.md` (Part 3).
> Source spec: `alpha-one/docs/16-trader-dashboard.md` and the owning module docs.

```prompt
Build the phase journey screen for the Alpha One trader portal (Next.js 15,
TypeScript, Tailwind, shadcn/ui). For multi-phase challenges it shows the whole
arc — passed phases, the current one, and what's next — so product-level progress
is obvious.

LAYOUT — a page header "Your journey" with the program name, then a horizontal
stepper (vertical on mobile), then a detail panel for the selected phase.

STEPPER — one node per phase in ordinal order. Each node shows the phase name,
its state, and a one-line result:
- **Passed** (green check): phase name, the profit achieved versus the target,
  and the date it completed.
- **Current** (highlighted ring): phase name, the live progress toward the
  target, and days remaining.
- **Next** (outlined, muted): phase name and a one-line description of what
  changes (e.g. "tighter drawdown, higher profit split").
- **Failed** (red): the phase and the reason, with a link to the breach report.
Connectors between nodes are coloured by progress. The current node is
announced via aria-live when it changes.

DETAIL PANEL — selecting a node opens a panel for that phase: its rule summary
(target, drawdown, daily loss, minimum days), its start and end dates, the
metrics at the moment it ended (final equity, high-water mark, profit, trading
days), and — for the current phase — the live meters linked to the objectives
screen.

LINEAGE NOTE — where a phase was completed by spawning a new account, show a
small "continued in a new account" note with a link to that account, so the
trader understands why the account id changed. This is the visible form of
`parent_account_id`.

EMPTY & EDGE STATES — a single-phase challenge renders the stepper with one node
and a line "This is a one-phase challenge."; loading skeletons; a not-found or
cross-tenant id returns the not-found page.

ACCESSIBILITY & MOBILE — the stepper is an ordered list with `aria-current="step"`
on the active node, nodes are buttons that move focus to the detail panel, and
the layout stacks vertically from 320 px. No dark/light toggle in V1.
```

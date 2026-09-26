# Screen 20 — Economic calendar widget · `/calendar` · F4 · V2.0

> Copy-able UI prompt for the Alpha One trader portal.
> Extracted from `trader-flows-and-screen-prompts.md` (Part 3).
> Source spec: `alpha-one/docs/16-trader-dashboard.md` and the owning module docs.

```prompt
Build the economic calendar screen for the Alpha One trader portal (Next.js 15,
TypeScript, Tailwind, shadcn/ui). It helps the trader plan around high-impact news
events without leaving the platform, and tells them plainly when trading is
restricted around an event.

LAYOUT — a page header "Economic calendar", a filter row, and a day-grouped list
of events. Max-w-4xl.

FILTER ROW — impact chips (All / High / Medium / Low), a currency multi-select
(USD, EUR, GBP, JPY, PKR, INR…), and a "Today / This week" toggle. Filters write
to the URL.

EVENT ROW — time (in the trader's local timezone, with the source timezone on
hover), an impact badge (High = filled red, Medium = amber, Low = grey — always
accompanied by the word, never colour alone), the country flag, the event name,
and the previous / forecast / actual values where published. Past events dim and
show the actual.

NEWS-RULE INTEGRATION — when the trader's rule pack restricts trading around news
events, affected events get a distinct marker and an explanatory line: "Trading is
restricted from 14:30 to 15:30 broker time around this release." The marker must
be understandable at a glance and also available as text.

DAY GROUPING — events grouped under sticky date headers with the day name and
date, "no events" days collapsed to a single muted line rather than an empty gap.

STATES — loading skeletons; a provider-outage state "The calendar is temporarily
unavailable" with a retry (never a silent empty list); an empty filter result with
a "Clear filters" button.

ACCESSIBILITY & MOBILE — rows are list items, impact badges include text, the
filter chips are a real group, timezone handling is explicit and labelled, and
the layout is a single column on phones. No dark/light toggle in V1.
```

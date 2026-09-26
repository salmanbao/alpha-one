# Screen 15 — Full rules view · `/accounts/{id}/rules` · F4 · V2.0

> Copy-able UI prompt for the Alpha One trader portal.
> Extracted from `trader-flows-and-screen-prompts.md` (Part 3).
> Source spec: `alpha-one/docs/16-trader-dashboard.md` and the owning module docs.

```prompt
Build the "Your rules" screen for the Alpha One trader portal (Next.js 15,
TypeScript, Tailwind, shadcn/ui). Beyond the objective meters, this is the
complete, plain-language rule set for this specific account — the expectations
made explicit so nothing is a surprise.

LAYOUT — a page header "Your rules" with the account name and a note "These are
the rules frozen on your account at purchase. They don't change mid-account.",
then grouped rule sections, then a footer with the agreement PDF.

RULE GROUPS — render as an accordion or card list, each group with an icon and a
one-line summary, expanding to individual rules:
- **Drawdown** — maximum/trailing drawdown type, the floor value, how it is
  calculated, whether it trails the high-water mark.
- **Daily loss** — the daily limit, how a "day" is defined (broker-server
  midnight, named timezone), and when it resets.
- **Profit target** — the target and whether it is per phase.
- **Time limits** — minimum trading days, maximum calendar duration, what happens
  at expiry.
- **Consistency** (when configured) — the rule in plain words, e.g. "no single
  trading day may contribute more than 40% of total profit".
- **Trading restrictions** — weekend/holding-overnight rules, news-event
  restrictions, prohibited instruments, expert-advisor/copy-trading rules,
  minimum trade duration, maximum lot size, hedging rules.
Each rule row shows the threshold value and, where the platform already tracks
it, the trader's current value next to it ("Used today: 34% of 5%").

LANGUAGE RULES — every rule is written in plain language with no jargon; where a
term is unavoidable ("high-water mark", "trailing drawdown") it gets a small
info tooltip with a one-sentence definition. Tone is explanatory, never legalistic.

FOOTER — "Download the full challenge agreement (PDF)" linking to the document
signed-URL route, plus "Questions about a rule? Contact support" with the account
id pre-filled.

STATES — loading skeletons per group; a rule group that does not apply to this
account is omitted entirely rather than shown as "N/A"; a server error shows an
inline retry. If the terms snapshot is missing (a data bug), show an honest
"We couldn't load your frozen terms — contact support" panel rather than
rendering the current template, because the template may have changed since
purchase.

ACCESSIBILITY & MOBILE — the accordion is a proper disclosure pattern with
aria-expanded, tooltips are keyboard-accessible, groups are semantic sections
with headings, and everything reflows to one column on phones. No dark/light
toggle in V1.
```

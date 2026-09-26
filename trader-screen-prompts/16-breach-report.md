# Screen 16 — Breach report · `/accounts/{id}/breach` · F4 · V2.0

> Copy-able UI prompt for the Alpha One trader portal.
> Extracted from `trader-flows-and-screen-prompts.md` (Part 3).
> Source spec: `alpha-one/docs/16-trader-dashboard.md` and the owning module docs.

```prompt
Build the breach report screen for the Alpha One trader portal (Next.js 15,
TypeScript, Tailwind, shadcn/ui). It is shown when an account fails. The tone
requirement is explicit and non-negotiable: **factual and non-accusatory** — this
is a document a trader screenshots and disputes, so it must be evidence, not a
scolding.

LAYOUT — a status header, an evidence panel, a "what happened next" panel, and an
actions footer. Max-w-3xl.

STATUS HEADER — a neutral (not celebratory, not alarming) icon, "Account breached",
the program name, the breach timestamp in the trader's local time **and** broker
time side by side (they differ, and the difference matters in a dispute), and the
verdict/reference id in monospace.

EVIDENCE PANEL — the heart of the screen: a small table with exactly three
columns — **Rule**, **Threshold**, **Observed** — plus a "When" column.
Example rows: "Maximum drawdown | 6.00% of initial balance | 6.34% | 14:02 broker
time"; "Daily loss limit | 5.00% | 5.21% | 09:47 broker time". Below the table a
one-sentence plain-language explanation of the rule that was broken and how the
observed value was derived (e.g. "Your trailing drawdown is measured from your
high-water mark of $104,155, reached at 13:58."). Where the platform holds an
equity snapshot series, render a small chart of the minutes around the breach
with the threshold line drawn in — the visual is the evidence.

WHAT HAPPENED NEXT — a short ordered list of what the platform did, in plain
words: open positions were closed at market, trading was disabled at the broker,
the account moved to `failed`, a certificate/notice document is available, and
whether any in-flight payout was placed on hold.

ACTIONS — "Download breach notice (PDF)", "View my other accounts", and a
prominent "Appeal or ask a question" button that opens support as a ticket with
the account id, the verdict id and the rule id pre-filled (the dispute channel is
the product, not an email address).

STATES — an account that failed by **time-limit expiry** rather than a breach
renders the same shell with a different headline ("Evaluation period ended") and
an evidence panel showing the time rule, the start date and the expiry date. A
breach that was overridden by the firm shows a green "This breach was reversed by
{ firm } on { date }" banner with the reason. Loading, not-found (404, never 403)
and error states as elsewhere in the portal.

ACCESSIBILITY & MOBILE — the evidence table is a real table with header scope,
numbers are right-aligned and tabular, the timestamps are machine-readable with
human labels, and the layout is a single column from 320 px. No dark/light toggle.
```

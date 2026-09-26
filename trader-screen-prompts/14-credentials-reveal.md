# Screen 14 — Credentials reveal · `/accounts/{id}/credentials` · F5 · V1.0

> Copy-able UI prompt for the Alpha One trader portal.
> Extracted from `trader-flows-and-screen-prompts.md` (Part 3).
> Source spec: `alpha-one/docs/16-trader-dashboard.md` and the owning module docs.

```prompt
Build the broker credentials screen for the Alpha One trader portal (Next.js 15,
TypeScript, Tailwind, shadcn/ui). It is the most protected screen in the portal:
it hands the trader the keys to a real MT5 account, exactly once.

LAYOUT — a warning-toned header, three credential rows, an actions cluster, and
a help panel. Max-w-2xl.

HEADER — a lock/shield icon, "Your MetaTrader 5 credentials", and one sentence:
"These log in to your trading account at the broker. Keep them private — our
team will never ask you for them."

CREDENTIAL ROWS — three rows, each with a label, a monospace value, and an
action:
1. **Account number** (login) — visible by default, with a copy button.
2. **Server** — visible by default, with a copy button.
3. **Password** — masked as `••••••••••` by default with a "Reveal" button. The
   trading password and the investor password are two separate rows; the investor
   (read-only) password can be revealed independently.

REVEAL FLOW — clicking "Reveal" opens the shared `SensitiveDialog`: a one-line
reason ("Confirm it's you to reveal your trading password"), the 2FA step-up
(re-authentication, `prompt=login&max_age=300`), and a typed confirmation
("Type REVEAL to continue"). On success the password renders once in monospace
with a copy button and a countdown ("This disappears in 60s" — auto-mask on
timer, on blur, and on navigation). The response is never cached (no-store) and
is never written to localStorage or IndexedDB. After the first reveal the row
returns to masked permanently: re-issuing a password is a support action, not a
button, so show "Need a new password? Contact support" with the account id
pre-filled.

METAAPI PORTAL LINK — a secondary action "Open read-only portal" that opens the
firm's opaque hosted MetaApi URL in a new tab. Never construct a broker URL from
raw credentials, and never expose anything beyond this opaque link.

HELP PANEL — three short steps: "1. Open MetaTrader 5. 2. File → Login to Trade
Account. 3. Enter the server, login and password." Plus a link to the firm's
setup guide and a "Contact support" button.

ERROR & EDGE STATES — step-up expired (`authz.step_up_required`, 403): the dialog
shows "That took too long — confirm again to continue" and re-prompts, without
losing the dialog context. Account not active: the screen explains credentials
appear once the account is active and links to the opening saga. Account not
found or not owned: the "not found" page. Rate limited: inline "Too many
attempts — try again in {n}s".

ACCESSIBILITY & MOBILE — the reveal button is never auto-focused, the dialog
traps focus and closes on Escape, the copy buttons announce "Copied", values use
`aria-label` including which credential they are, and the layout is a single
column from 320 px. No dark/light toggle in V1.
```

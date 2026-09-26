# Screen 26 — Payout methods · `/payouts/methods` · F7 · V1.1

> Copy-able UI prompt for the Alpha One trader portal.
> Extracted from `trader-flows-and-screen-prompts.md` (Part 3).
> Source spec: `alpha-one/docs/16-trader-dashboard.md` and the owning module docs.

```prompt
Build the payout methods screen for the Alpha One trader portal (Next.js 15,
TypeScript, Tailwind, shadcn/ui). It is where a trader tells the platform where
their money goes — the single highest-value fraud target in the product, so every
edit is versioned, confirmed and cooldown-flagged.

LAYOUT — a list of existing methods, an "Add method" form (inline panel or dialog),
and a security explainer. Max-w-3xl.

METHOD CARD — for each method: the rail type with its icon (TRC20 / ERC20 / BEP20 /
local provider), a masked destination ("TQrY…9fXz" — never the full string), an
optional label ("Main TRON wallet"), a "Default" badge where applicable, a
confirmation badge ("Confirmed" / "Needs confirmation"), the date added, and
actions: "Confirm", "Set as default" (V2), "Edit", "Remove".

CONFIRM-ONCE RULE (V1.1) — a newly added or edited method must be explicitly
confirmed by the trader before its first payout. Show a prominent amber banner on
unconfirmed methods: "Confirm this method before your next payout" with a
"Confirm method" button. After confirmation the badge turns green and the action
disappears. There is no per-payout re-confirmation.

ADD / EDIT FORM — a chain/rail selector, a destination field with chain-specific
validation (length, charset, base58/bech32 as applicable, and EIP-55 checksum for
ERC20), an optional label field, and a "Save" button. Validation runs on blur and
on submit with specific inline messages ("That doesn't look like a TRON address —
they start with T and are 34 characters"). Never accept an address that fails
checksum validation, and say why in plain words.

VERSIONING & COOLDOWN — editing a method creates a new version; the card shows
"Edited { date } — v2" and the previous version stays in an expandable history
("v1 · TQrY…9fXz · used on payout 01J9PAY…") so "which address did the $2,000 go
to" is always answerable. When a method is edited shortly before a payout request,
show a warning flag on the request (V2): "You changed this method recently — we've
flagged the request for review." Never silently swap a destination.

REMOVE — a confirm dialog: "Remove this payout method? Payouts already requested
will still be sent to the address on the request." Removal deactivates rather than
deletes, and the row is retained in history.

SECURITY EXPLAINER — a short panel: "We never show your full wallet address, we
verify the format before every payout, and changes are versioned so you can always
see where money was sent. If you didn't make a change, contact support
immediately." With a support button pre-filled with the account id.

ERROR & EDGE STATES — `payout.method_invalid` (400): "Please check your payout
details." inline on the field. `payout.invalid_address` (400): chain-specific
message. Saving while the dialog is open on another device: a conflict state with a
refresh prompt. Empty: "No payout methods yet — add one to receive payouts."

ACCESSIBILITY & MOBILE — the form fields are labelled with the chain named, the
confirmation banner is aria-live, the masked value has a "reveal" affordance only
for the trader's own data (an explicit click, never hover), and the layout is a
single column from 320 px. No dark/light toggle in V1.
```

# Screen 40 — Community & live chat · `/community` · F10 · V2.0/V3.0

> Copy-able UI prompt for the Alpha One trader portal.
> Extracted from `trader-flows-and-screen-prompts.md` (Part 3).
> Source spec: `alpha-one/docs/16-trader-dashboard.md` and the owning module docs.

```prompt
Build the community and live-chat screen for the Alpha One trader portal
(Next.js 15, TypeScript, Tailwind, shadcn/ui). Two distinct things share this
surface and must not be confused: a persistent support conversation with the firm,
and (V3) a peer forum. They have different moderation rules and different privacy
expectations.

LAYOUT — a left rail with two sections: "Support" (direct messages with firm staff)
and "Community" (V3: channels and the forum). The main pane shows the selected
conversation. Max-w-6xl. On mobile it is a list → conversation flow.

SUPPORT DIRECT MESSAGES (V2) — a persistent thread between the trader and firm
staff. Messages are bubbles with the author's display name and role, timestamps,
and read state. A composer at the bottom with a send button and an attachment
action. Conversation history persists across sessions so context is never lost. A
clear header states who the trader is talking to ("Chatting with FunderBlu
support") and the expected response window. An escalation line: "Need a formal
ticket? Open a support ticket" linking to the support screen, because the chat is
not a substitute for the audited ticket.

ANNOUNCEMENT CHANNEL — a read-only channel where the firm publishes updates.
Messages are full-width cards with a date, and the channel shows an unread divider.
The trader cannot post here, and the UI says so.

COMMUNITY FORUM (V3) — a channel list and a thread view: threads with a title,
author (with an alias option), tags, reply count and last-activity time; a thread
view with nested replies, a composer, and a "report" action on every post. Aliases
are opt-in per post, and the default display name is the trader's chosen alias
rather than their real name.

MODERATION (V3, staff-side but visible here) — a removed post renders as
"This message was removed by a moderator" with no content, and a banned user sees
a plain notice rather than an error loop. Report actions confirm and thank the
trader.

LIVE CHAT HANDOFF (V3) — from a support conversation, a "Start live chat" action
that shows the queue position and the wait estimate, and hands off to an agent with
the conversation history attached.

PRIVACY & SAFETY — a persistent note in the support section: "Firm staff can read
these messages. Never share your password or 2FA codes." In the community section:
"Aliases are optional. Posts are public to other traders at your firm."

EMPTY STATES — no conversations: "Message us any time — we usually reply within a
few hours." No community yet: "Your firm hasn't opened the community yet."
ERROR — per-pane retry; a failed send keeps the draft text and offers retry.

ACCESSIBILITY & MOBILE — the conversation is an ordered list of articles, new
messages are announced politely via aria-live without stealing focus, the composer
is labelled, and the mobile flow is list → conversation with a back button. No
dark/light toggle in V1.
```

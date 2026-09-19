# Community & Live Chat (Part D) API Contract (CHT)

Status: PROVISIONAL (post-V1, design-level)
Owner: TBD
Version: v1
Last updated: 2026-09-19

Derived from `docs/26-mobile-apps.md` §7 + PRD CHT-NN (V2.0, V3.0). Nothing here is final until that phase's contract freeze (docs/99 §12).

## Scope

PRD module **CHT** (8 requirements). Abridged backlog:

| Req | Feature | Release | Pri | Owner | User story (abridged) |
|---|---|---|---|---|---|
| `CHT-01` | Live chat widget | V2.0 | P1 | FE-1 | As a trader, I can chat with support in real time from my dashboard so that urgent issues are resolved quickly. |
| `CHT-02` | Discord integration | V2.0 | P1 | BE-2 | As the platform, I assign and remove Discord roles based on funded and payout events so that community status mirrors account stat… |
| `CHT-03` | Community forum | V3.0 | P2 | FE-1 | As a trader, I can post questions and replies in a community forum so that peer support is centralized. |
| `CHT-04` | Direct messaging with support | V2.0 | P1 | BE-2 | As a trader, I can send persistent direct messages to support staff so that context is preserved between sessions. |
| `CHT-05` | Announcement channel | V2.0 | P1 | BE-2 | As a tenant admin, I can publish announcements to a dedicated trader channel so that updates are not buried in support tickets. |
| `CHT-06` | Voice channel link | V3.0 | P2 | FE-1 | As a trader, I can join a linked voice channel (Discord, Telegram, or hosted) so that live community engagement is one click away. |
| `CHT-07` | history persistence | V2.0 | P1 | BE-2 | As a trader, my chat history with support persists so that I can reference past conversations. |
| `CHT-08` | moderation | V3.0 | P2 | BE-2 | As a tenant admin, I have moderation tools (ban, mute, report) so that community behavior is governed. |

## Auth

Trader (community) + staff (moderation). All routes sit in the GW chain (docs/04 §3.1): tenant resolution →
authn → authz (`resource.action` key per route) → rate limit → entitlement gate →
idempotency → audit. Error envelope per GW-18 (`code`, `message`, `correlation_id`).

## Tenant resolution

From domain (GW-02) for web routes; from the API key for machine routes (key wins
over any header); `X-Tenant-Id` header for internal service tokens only. Unknown
host/key → `404 tenant.not_found` (no-oracle rule, docs/04 §6).

## Permissions

No dedicated permission keys beyond the V1 registry are fixed yet — keys are proposed in the module doc's §7 and freeze with the module.

## Idempotency

Mutating requests accept an `Idempotency-Key` header per GW-12 (24 h TTL, scope =
method+path+key). Retries MUST NOT create duplicate resources.

## Endpoints (provisional)

> Copied verbatim from `docs/26-mobile-apps.md` §7 on 2026-09-19 — the module doc is authoritative if they drift; regenerate with `python3 scripts/complete_contracts_pack.py`.

Trader (TD):
`GET /v1/chat/conversations` (the own, the SUP-adjacent),
`POST /v1/chat/conversations` (the new — the pre-fill context,
the 16 §14 pattern), `GET /v1/chat/conversations/{id}` (the
thread), `POST /v1/chat/conversations/{id}/messages` (the
real-time — the SSE delivers, the API is the write + the
reconnect-sync (the last-message-id cursor, the 04 §5.7
replay-pattern: the reconnect fetches the missed messages by
cursor — the real-time honesty: the SSE is the fast path, the
cursor is the truth)),
`GET /v1/chat/announcements?active=` (the banner + the
history), `GET /v1/chat/presence` (the support availability),
`POST /v1/chat/discord/link` (the CHT-02 — the Discord auth
code exchange, the staff-approved link (the tenant config:
auto-approve vs staff-approve — the FunderBlu default: staff-
approve (the verified role is the tenant's badge, the tenant
approves its placement))),
`DELETE /v1/chat/discord/unlink`,
V3 (the forum): `GET /v1/chat/boards`, `GET /v1/chat/threads?
board=`, `POST /v1/chat/threads`, `POST /v1/chat/threads/{id}/
posts`, `POST /v1/chat/posts/{id}/report`,
`GET /v1/chat/profiles/{handle}` (the forum identity — the
CMP-11 surface).

Staff (ADM — the CHT section, the SUP-adjacent queue):
`GET /v1/admin/chat/queue` (the live conversations + the
reported posts (V3)), `GET /v1/admin/chat/conversations/{id}`
(the full thread + the internal notes — the SUP-09 pattern),
`POST /v1/admin/chat/conversations/{id}/messages` (the staff
reply + the internal note, the kind), `POST /v1/admin/chat/
announcements` (the CHT-05 — the 2FA + the preview, the NOT-14
pattern), `POST /v1/admin/chat/announcements/{id}/withdraw`
(the 2FA),
`GET /v1/admin/chat/discord/links` (the pending links — the
staff-approve flow), `POST /v1/admin/chat/discord/links/{id}/
approve|reject`,
V3 (the moderation): `POST /v1/admin/chat/posts/{id}/remove`
(the 2FA + the snapshot), `POST /v1/admin/chat/posts/{id}/
restore`, `GET /v1/admin/chat/reports` (the report queue).

The Discord bot (the CHT-02 — the bot's endpoints, the
Discord-webhook-in): the bot receives the DMs (the Discord
gateway) → the `channel: discord` tickets (the §2 path); the
bot posts the announcements (the CHT-05 → the #announcements
channel); the bot syncs the verified roles (the link state →
the role grant/revoke, the nightly + the event-driven); the
bot is the tenant's (the bot account is added to the tenant's
server by the tenant's admin — the platform provides the bot
program, the tenant owns the server + the bot's placement).

## Open contract questions

- Paths, methods, and field names below are PROVISIONAL until this module's phase
  freeze (docs/99 §12) — additive changes only after freeze; breaking changes get
  `/v2/` + the 12-month deprecation rule for public surfaces.
- Permission keys: the V1 registry (`permissions/registry.md`) is binding; keys used
  below beyond it are provisional and join the registry at freeze.
- Error codes: V1 baseline codes are binding (`errors/taxonomy.md`); extended codes
  follow the GW-18 dotted convention and freeze with the module (docs/30).

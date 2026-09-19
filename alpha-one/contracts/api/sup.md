# Support Inbox API Contract (SUP)

Status: PROVISIONAL (post-V1, design-level)
Owner: TBD
Version: v1
Last updated: 2026-09-19

Derived from `docs/18-support.md` §7 + PRD SUP-NN (V2.0, V3.0). Nothing here is final until that phase's contract freeze (docs/99 §12).

## Scope

PRD module **SUP** (33 requirements). Abridged backlog:

| Req | Feature | Release | Pri | Owner | User story (abridged) |
|---|---|---|---|---|---|
| `SUP-01` | Ticket creation | V2.0 | P0 | BE-2 | As a trader, I can create a support ticket from the trader dashboard so that I can ask for help without using external channels. |
| `SUP-02` | Ticket categories | V2.0 | P0 | BE-2 | As a trader, I can select a category such as account issue, payout, KYC, breach, payment, technical, or general so that the right … |
| `SUP-03` | Ticket status machine | V2.0 | P0 | BE-2 | As the platform, I track ticket statuses including open, pending trader, pending staff, resolved, and closed so that every ticket … |
| `SUP-04` | Trader ticket list | V2.0 | P0 | FE-1 | As a trader, I can view my open and closed tickets from the trader dashboard so that I can track support history. |
| `SUP-05` | Trader reply flow | V2.0 | P0 | BE-2 | As a trader, I can reply to a ticket and attach screenshots or documents so that I can provide evidence for my issue. |
| `SUP-06` | Admin inbox | V2.0 | P0 | BE-2 | As support staff, I see all tickets for my tenant with filters by status, category, priority, assignee, trader, and account so tha… |
| `SUP-07` | Ticket detail view | V2.0 | P0 | BE-2 | As support staff, I open a ticket and see the conversation plus trader profile, accounts, payouts, KYC status, orders, and recent … |
| `SUP-08` | Staff reply flow | V2.0 | P0 | BE-2 | As support staff, I can reply to a ticket from the admin panel so that trader communication stays inside the platform. |
| `SUP-09` | Internal notes | V2.0 | P1 | BE-2 | As support staff, I can add internal-only notes to a ticket so that staff can collaborate without exposing private comments to the… |
| `SUP-10` | Assignment | V2.0 | P1 | BE-2 | As a support lead, I can assign tickets to staff members so that ownership is clear. |
| `SUP-11` | Priority | V2.0 | P1 | BE-2 | As support staff, I can mark tickets as low, normal, high, or urgent so that payout and breach issues can be handled first. |
| `SUP-12` | Account-linked ticket | V2.0 | P0 | BE-2 | As the platform, I allow a ticket to link to a specific trading account, order, payout, KYC case, or breach decision so that the t… |
| `SUP-13` | Payout dispute ticket | V2.0 | P1 | BE-2 | As a trader, when a payout is rejected I can open a dispute ticket prefilled with payout details so that appeals are structured. |
| `SUP-14` | Breach appeal ticket | V2.0 | P1 | BE-2 | As a trader, I can open an appeal from a failed or breached account so that challenge disputes have a formal path. |
| `SUP-15` | issue ticket | V2.0 | P1 | BE-2 | As a trader, I can open a ticket from the KYC page when verification is rejected or needs resubmission so that compliance problems… |
| `SUP-16` | Email notifications | V2.0 | P0 | BE-2 | As the platform, I notify traders and staff when tickets are created, replied to, assigned, resolved, or reopened so that support … |
| `SUP-17` | In-app notifications | V2.0 | P1 | BE-2 | As the platform, I create in-app notifications for ticket replies and status changes so that users see support updates inside the … |
| `SUP-18` | timers | V2.0 | P1 | BE-2 | As support staff, I see first-response and resolution timers so that service quality is measurable. |
| `SUP-19` | breach alerts | V2.0 | P2 | BE-2 | As the platform, I alert staff when high-priority tickets approach or breach SLA so that urgent cases are escalated. |
| `SUP-20` | Canned responses | V2.0 | P2 | BE-2 | As support staff, I can use predefined replies for common issues so that answers are faster and consistent. |
| `SUP-21` | Attachment scanning and limits | V2.0 | P0 | BE-2 | As the platform, I limit file type and size for ticket attachments so that support uploads are safe and controlled. |
| `SUP-22` | Search | V2.0 | P1 | BE-2 | As support staff, I can search tickets by trader email, account ID, payout ID, subject, and message text so that historical cases … |
| `SUP-23` | Ticket audit | V2.0 | P0 | BE-2 | As the platform, I audit ticket creation, replies, notes, assignment, status changes, and closures so that support handling is acc… |
| `SUP-24` | Telegram intake | V3.0 | P2 | BE-2 | As the platform, I can ingest Telegram conversations linked to a trader profile so that Telegram support does not live outside the… |
| `SUP-25` | Support reporting | V2.0 | P2 | BE-2 | As a tenant admin, I see ticket counts, first response time, resolution time, open backlog, and category breakdown so that support… |
| `SUP-26` | Auto-close policy | V2.0 | P2 | BE-2 | As the platform, I can auto-close tickets after a configured period in resolved status so that the inbox stays clean. |
| `SUP-27` | Knowledge base | V3.0 | P2 | BE-2 | As support staff, I create and manage FAQ articles so that common questions are deflected. |
| `SUP-28` | Live chat widget | V3.0 | P2 | BE-2 | As a trader, I chat with support in real-time so that urgent issues are resolved quickly. |
| `SUP-29` | support bot | V3.0 | P2 | BE-2 | As the platform, I use AI to answer common questions and triage tickets so that support scales. |
| `SUP-30` | Support ticket templates per category | V2.0 | P2 | FE-1 | As support staff, I see starter templates per ticket category, so that replies are consistent and fast. |
| `SUP-31` | Support agent performance dashboard | V2.0 | P2 | BE-2 | As a support lead, I see per-agent tickets closed, average response, and resolution time, so that individual performance is measur… |
| `SUP-32` | Support satisfaction survey | V2.0 | P2 | BE-2 | As a tenant admin, I collect post-resolution CSAT from traders, so that support quality has a direct signal. |
| `SUP-33` | Enforcement dispute ticket workflow | V2.0 | P1 | BE-2 | As a trader, I can open a dispute ticket from a breached account with auto-attached breach evidence, so that enforcement disputes … |

## Auth

Trader (own tickets) + staff (queue). Trader routes identity-scoped; staff routes require support role. All routes sit in the GW chain (docs/04 §3.1): tenant resolution →
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

> Copied verbatim from `docs/18-support.md` §7 on 2026-09-19 — the module doc is authoritative if they drift; regenerate with `python3 scripts/complete_contracts_pack.py`.

> **Scope note:** SUP is not in the V1 execution sheet (V2 scope). There is no V1 baseline contract for this module; the surface below is design-level (post-V1, docs/99) and provisional until its phase's contract freeze.


Trader (TD): `GET /v1/support/tickets` (own), `POST /v1/support/tickets`
`{category, subject, body, account_id?, attachment_ids?}`,
`GET /v1/support/tickets/{id}` (thread, own only),
`POST /v1/support/tickets/{id}/messages` (reply),
`DELETE /v1/support/tickets/{id}` (cancel — V1: only while `open`),
`GET /v1/support/attachments/{id}/url` (own, signed),
`POST /v1/support/tickets/{id}/satisfaction` (V2).

Staff (ADM): `GET /v1/admin/support/queue?status=&category=`,
`GET /v1/admin/support/tickets/{id}` (full: internal notes, object context,
linked-object evidence reads),
`POST /v1/admin/support/tickets` (staff-opened),
`POST /v1/admin/support/tickets/{id}/messages` (staff reply / internal note
via `kind`),
`POST /v1/admin/support/tickets/{id}/status` (transition, 2FA for
`resolved` on money-linked tickets — the "we fixed your payout" claim must
be deliberate),
V2: assignment, canneds CRUD, templates, reports, search.

## Open contract questions

- Paths, methods, and field names below are PROVISIONAL until this module's phase
  freeze (docs/99 §12) — additive changes only after freeze; breaking changes get
  `/v2/` + the 12-month deprecation rule for public surfaces.
- Permission keys: the V1 registry (`permissions/registry.md`) is binding; keys used
  below beyond it are provisional and join the registry at freeze.
- Error codes: V1 baseline codes are binding (`errors/taxonomy.md`); extended codes
  follow the GW-18 dotted convention and freeze with the module (docs/30).

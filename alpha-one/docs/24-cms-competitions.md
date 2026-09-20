# 24 — CMS: Website & CMS + CMP: Competitions & Gamification

> Covers PRD modules **CMS** (15 requirements) and **CMP** (17
> requirements). Both are V3-scoped per the PRD requirement phases
> (docs/00 lists both at Rel 2.0 for *first meaningful scope*; the
> requirement-level truth is V3 — this doc is the V3 design made now,
> per the docs/00 commitment that future modules get full designs while
> the foundations are fresh). Until then: the tenant's public presence in
> V1 is a **static Next.js marketing site** (the FE-1/FE-2 "marketing
> site" in the team plan) — no CMS in the critical path, deliberately.

---

# Part A — CMS: Tenant Website & CMS (15 reqs)

## 1. Purpose & scope

The tenant's public, white-labeled site: landing pages, the
**pricing/challenge widget** (the conversion surface — package × rule set
× price, driven live from TEN's catalog), blog/content, SEO, forms, legal
pages, navigation, social-proof blocks, FAQ, analytics hooks, media
library, page versioning, scheduled publishing.

**Binding decisions:**
- The site is **rendered by the same Next.js platform** (a `web/sites`
  renderer) from **CMS content stored in Postgres** (the ADR: one
  Postgres — content is rows, not a WordPress install). Per-tenant:
  subdomain or custom domain (TEN-14's domain config already owns
  resolution; the sites renderer sits behind the same GW tenant
  resolution — a public route, no auth).
- **The content model is constrained** (CMS-03): blocks, not free HTML —
  the editor produces a block tree (`hero`, `features`, `pricing_widget`,
  `testimonials`, `faq`, `form`, `blog_post`, …); the renderer is the
  only place blocks become HTML (the XSS surface is one reviewed
  component per block type, not arbitrary markup).
- **Dynamic data is API-driven, never content**: prices, package
  availability, and "N traders funded this month" come from TEN/ANA at
  render time (cached 5 min at the edge) — the CMS stores layout + copy,
  never money numbers.

Requirement coverage: `CMS-01..15` (all V3).

## 2. Architecture

```
 public (no auth):
   site.{tenant-domain} / {tenant}.alphaone.example ──► web/sites renderer
     (Next.js RSC, tenant resolved like every other surface, 04 §3.4)
       content: pages/blocks from PG (CMS tables) — CDN-cached per
                (tenant, page, version) with 5-min staleness
       dynamic: pricing widget → GET /v1/public/{tenant}/catalog
                (TEN packages × rule sets × prices, 5-min edge cache)
                social proof → ANA public KPIs (funded count, countries —
                the numbers the tenant pre-approves are the only ones
                rendered: ANA exposes a "published stats" object, not raw
                aggregates — see §3.5)
       forms (CMS-07): lead capture → CRM contact + SUP ticket (category
                'lead') — the form never emails; the NOT template does
   tenant staff (ADM "Marketing" section, V3): the block editor, media
   library, preview (per-page, per-block, with the live dynamic data),
   versioning (publish = new version, rollback = point the live pointer
   back — CMS-14), scheduled publishing (CMS-15, the advisory-lock worker
   flips the pointer at the scheduled time), SEO controls (CMS-06:
   per-page title/description/OG/JSON-LD), legal pages (CMS-08: the
   ToS/privacy/AML templates rendered with tenant variables — the
   FunderBlu legal-approved text is the seed content), navigation (CMS-09),
   blog (CMS-05: posts are blocks + markdown, MD is rendered through the
   same sanitize pass), analytics hooks (CMS-12: first-party only — the
   TD §10 rule extends to the public site: no third-party trackers,
   analytics = our GW's anonymous page-view counter, no cookies)
```

## 3. System design

### 3.1 Provisioning (CMS-01)

A new tenant gets the **starter site** from the template library (CMS-02):
the seed = the FunderBlu-grade site (the template the platform's own
marketing runs on) with tenant variables (name, logo, colors, package
data) — provisioned as part of the 9-step saga's content step (03: the
saga gains a `site_provisioned` step in V3; V1/V2 tenants simply have no
CMS rows and the renderer serves the static marketing site).

### 3.2 The block model (CMS-03/04)

```
pages: id · tenant_id · slug · title · status (draft|published)
       live_version INT · nav_order · seo JSONB · published_at
page_blocks (the versioned tree):
  id · page_id · version INT · parent_id? · block_type · data JSONB
  (data = the block's typed schema — e.g. pricing_widget: {package_ids,
   currency, layout}; testimonials: {quotes[]}; each block_type has a
   validated schema (zod/JSON-Schema in CI) — the editor can't produce
   invalid data, the renderer can't render unknown shapes)
```

- **Versioning:** editing a published page creates draft blocks at
  version+1; **publish** = flip `live_version` (atomic); **rollback** =
  flip to an earlier version (all history retained — CMS-14). The R2
  object store holds media (CMS-13: uploads, image optimization at
  upload, tenant-prefixed keys, the same isolation as every other R2
  bucket path).
- **The pricing widget (CMS-04)** is the highest-value block: it renders
  the live catalog (packages × rule sets × prices) + the "buy" CTA deep-
  links into TD/CHK (`/buy?package=&rules=` — the checkout pre-filled,
  the login-first flow takes over). Price changes in TEN appear on the
  site within 5 min (edge cache) — **the site can never show a stale
  price longer than 5 min by construction**.

### 3.3 Forms & leads (CMS-07)

Form blocks: typed fields (name, email, country, message, package
interest), honeypot + rate limit (the anti-spam pair; CAPTCHA only if
spam volume forces it — the first-party posture avoids third-party
CAPTCHA services at launch). Submission → `crm_contacts` row (the
prospect in CRM's lifecycle before signup, 20 §3.1) + SUP ticket
(category `lead`, auto-notified to the tenant's sales) + NOT email.
Lead data is PII: stored field-encrypted (the KYC-grade pattern),
retention 2 yr (marketing class), the tenant sees leads in ADM.

### 3.4 Legal pages (CMS-08)

ToS/privacy/AML/KYC-disclosure pages: **templates with variables**
(tenant name, entity, jurisdiction, broker disclosure, the "not a
broker" language the compliance review requires). The **FunderBlu
legal-approved text is the V3 seed** — and the rule: a legal page change
is a 2FA'd, critical-audited action with a "legal review" note field
(the platform's own discipline, modeled for the tenant). The TD's
purchase flow links the *published* legal version into the agreement
snapshot (CHK: the challenge agreement cites the legal page version at
purchase — the DOC-03 data mapping gains the variable).

### 3.5 Public stats (the social-proof block, CMS-10)

"2,140 traders funded" etc. come from a **`published_stats` object**
(the tenant publishes specific numbers in ADM, refreshed by ANA on a
schedule the tenant sets — the tenant controls *which* claims appear;
the platform controls the truth of the number). This sidesteps both the
marketing-accuracy problem and the PII problem (no individual data,
only tenant-approved aggregates).

### 3.6 Scheduled publishing & rollbacks (CMS-15/14)

The worker (advisory-lock) checks `publish_at` every minute; publish =
pointer flip + cache purge (the edge stale-while-revalidate covers the
5-min window honestly: the UI says "updates may take up to 5 min").
Every flip is audited (who, what version, when, note).

## 4. Events (topic `site`)

| Event | When | Consumers |
|---|---|---|
| `site.page_published` / `site.page_rolled_back` | pointer flip | AUD (critical on legal pages), ANA (cache purge hint) |
| `site.lead_captured` | form submission | CRM (contact), SUP (ticket), NOT, AUD |
| `site.pricing_changed` (derived) | TEN catalog change | ANA (widget cache invalidation), AUD (low) |
| `site.visit` | page view (anonymous, first-party) | ANA (funnel: visit → signup, the CRM-08/ANA-09 top of funnel) |

## 5. Lifecycles

- **Page:** `draft → published → (edited: draft v+1) → published …`
  (the pointer model, §3.2); `archived` (unlisted, URL 404s — content
  retained).
- **Block version:** immutable per version (§3.2).
- **Media asset:** `uploaded → (referenced) → orphaned (90 d unused →
  deletion candidate, the retention job with audit)`.
- **Lead:** `captured → (contacted) → converted (signup attributed) |
  stale (90 d)`.
- **Legal page:** the standard page lifecycle + the `legal_review` note
  requirement on every publish.
- **Scheduled publish:** `scheduled → published | (cancelled)`.

## 6. Error taxonomy

Namespace `CMS`:

| Code | HTTP | Meaning |
|---|---|---|
| `cms.page_not_found` | 404 | Public 404 (the tenant's branded 404 page) |
| `cms.block_schema_invalid` | 500-internal | Data failed its block schema (editor bug or a corrupt publish — the page renders without the bad block + CRITICAL alert; never a blank page) |
| `cms.publish_conflict` | 409 | Concurrent publish (last-write wins on the pointer, the losing editor is told with a diff) |
| `cms.scheduled_conflict` | 409 | Schedule on an already-live time (the worker skips + alerts) |
| `cms.media_too_large` | 422 | Upload over the block-type limit (images 5 MB) |
| `cms.form_rate_limited` | 429 | Lead form abuse (the honeypot + limit pair) |
| `cms.legal_review_required` | 403 | Legal page publish without the review note (2FA'd override by owner role) |
| `cms.tenant_not_provisioned` | 404 | No site for this tenant (the static fallback renders) |

## 7. API endpoints
> **Scope note:** CMS/CMP is not in the V1 execution sheet (V2/V3 scope). There is no V1 baseline contract for this module; the surface below is design-level (post-V1, docs/99) and provisional until its phase's contract freeze.


Public (tenant domain, no auth): the rendered pages (RSC/SSR),
`GET /v1/public/{tenant}/catalog` (the widget data, 5-min edge cache),
`POST /v1/public/{tenant}/forms/{form_id}` (lead submit, rate-limited),
`GET /sitemap.xml`, `GET /robots.txt` (per-tenant generated).

Staff (ADM marketing, V3): `GET|POST /v1/admin/site/pages` (+
`POST /{id}/publish` (2FA on legal), `POST /{id}/rollback`,
`POST /{id}/schedule`), `GET|POST /v1/admin/site/blocks`,
`POST /v1/admin/site/media` (upload), `GET /v1/admin/site/preview/{page}`
(the live-data preview), `GET|POST /v1/admin/site/seo`,
`GET /v1/admin/site/leads`, `GET /v1/admin/site/published-stats` (+
`POST` — publish the numbers).

## 8. Schema (key shapes)

```jsonc
// page row
{ "id": "01J9PG…", "tenant_id": "01J9TEN…", "slug": "pricing",
  "status": "published", "live_version": 4,
  "seo": { "title": "…", "description": "…", "og_image": "…", "jsonld": "…" },
  "published_at": 1758282000000, "published_by": "01J9…" }

// block data (pricing widget)
{ "block_type": "pricing_widget", "data": { "layout": "cards",
  "packages": ["100k-starter", "200k-pro"], "currency": "USD",
  "cta": { "label": "Start your challenge", "link": "/buy" } } }

// published stats (what the tenant allows the site to claim)
{ "data": { "funded_traders": 2140, "countries": 47,
            "updated_at": 1758282000000, "source": "ana:funded_count",
            "auto_refresh": "weekly" } }
```

## 9. Database design

```sql
CREATE TABLE site_pages (
  id            ULID PRIMARY KEY,
  tenant_id     ULID NOT NULL,
  slug          TEXT NOT NULL,
  title         TEXT NOT NULL,
  status        TEXT NOT NULL DEFAULT 'draft'
    CHECK (status IN ('draft','published','archived')),
  live_version  INT NOT NULL DEFAULT 1,
  nav_order     INT, is_legal BOOLEAN NOT NULL DEFAULT false,
  seo           JSONB NOT NULL DEFAULT '{}',
  publish_at    TIMESTAMPTZ,                  -- CMS-15
  published_at  TIMESTAMPTZ, published_by ULID,
  legal_review_note TEXT,                     -- required on is_legal publish
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, slug)
);
CREATE TABLE site_page_blocks (
  id          ULID PRIMARY KEY,
  page_id     ULID NOT NULL REFERENCES site_pages(id),
  version     INT NOT NULL,
  parent_id   ULID,
  block_type  TEXT NOT NULL,
  data        JSONB NOT NULL,                 -- schema-validated per type
  sort        INT NOT NULL DEFAULT 0,
  UNIQUE (page_id, version, id)
);
CREATE INDEX idx_siteblocks_live ON site_page_blocks(page_id, version);
CREATE TABLE site_media (
  id          ULID PRIMARY KEY,
  tenant_id   ULID NOT NULL,
  r2_key      TEXT NOT NULL,
  bytes       BIGINT NOT NULL, content_type TEXT NOT NULL,
  uploaded_by ULID, created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE site_leads (                      -- PII: field-encrypted name/email
  id          ULID PRIMARY KEY,
  tenant_id   ULID NOT NULL,
  form_id     ULID NOT NULL,
  data_enc    JSONB NOT NULL,
  ip_hash     TEXT,                           -- analytics-grade, not raw IP
  state       TEXT NOT NULL DEFAULT 'captured'
    CHECK (state IN ('captured','contacted','converted','stale')),
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_siteld_tenant ON site_leads(tenant_id, state, created_at DESC);
-- published_stats (tenant, key, value, source, updated_at, auto_refresh)
```

## 10. Security & compliance

- **The constrained-block model is the XSS design** (§2): no free HTML
  anywhere in content; markdown through the sanitize pass; the renderer
  is the single trust boundary (one reviewed component per block type —
  the review surface is the block registry, not a corpus of pages).
- **PII:** leads are field-encrypted (KYC-grade), the lead list is
  role-gated (sales/marketing), retention 2 yr (marketing class) vs 7 yr
  for the financial docs; IP is stored hashed (analytics grade).
- **No third-party trackers on public sites** (the first-party rule,
  extended): the analytics hook (CMS-12) is the GW's anonymous counter —
  a cookie-less, GDPR-light posture (still: the privacy page must
  disclose it — the legal template includes the line).
- **Legal pages are contract-adjacent** (§3.4): 2FA + review note +
  critical audit + version frozen into purchase agreements (CHK/DOC) —
  a ToS change is never retroactive to purchased accounts (the
  agreement snapshot cites the version at purchase, DOC §3.2 rule).
- **Supply chain:** block types ship in the repo (the renderer's
  component set) — a new block type is a code change with review, not a
  content upload (no runtime HTML injection path).
- **Abuse:** lead-form spam (honeypot + rate limit + the SUP category is
  isolated so a spam flood can't fill the support queue — the queue has
  a per-category cap with overflow to a spam review list).

## 11. Scalability considerations

- Public pages are **CDN-cached RSC** (per tenant+page+version, 5-min
  stale-while-revalidate) — the render cost at any traffic level is
  edge hits, not SSR; the dynamic widget is one cached GET.
- A viral landing page (an affiliate's blast, the CMP-07 prize
  announcement) = edge hits + the widget's 5-min refresh — the PG
  content reads never see the spike (the renderer reads from a
  Redis-cached content blob per page version; PG is the source, Redis
  is the hot copy).
- Blog/content growth: trivial (rows + R2 images).
- Forms: rate-limited writes (≤ 10/min/IP/page) — spam-scale is
  structurally capped before it hits PG.
- Multi-tenant public hosting: one renderer, N tenants (the subdomain
  resolution is the GW's existing job — no per-tenant infra).

## 12. Open-source solutions

| Option | Verdict |
|---|---|
| **In-house: PG content + Next.js renderer** (this design) | **CHOSEN** — one Postgres (ADR), the block model keeps the XSS surface a reviewed registry, dynamic data stays API-driven; a headless CMS SaaS (Sanity/Contentful) is data out of house for a tenant's public site, and a self-hosted WP is a stack we don't run |
| Sanity/Contentful/Strapi (headless CMS) | Rejected V3-launch: the content needs (layout + copy + a few dynamic widgets) is 15% of what those systems manage; the 85% (auth, webhooks, roles, preview infra) is overhead we'd integrate for nothing |
| WordPress self-hosted | Rejected: PHP + MySQL + a CVE surface on the same box as the money system |
| Next.js Image Optimization (R2-backed) | CHOSEN (CMS-13 media handling) |
| (SEO) next-sitemap / JSON-LD helpers | CHOSEN (trivial libs) |

## 13. Technology stack

Next.js 15 (`web/sites` renderer, the monorepo's public app),
TypeScript/Tailwind, Postgres (content), Redis (hot content cache), R2
(media), GW (tenant resolution + public routes), ANA (published stats),
CRM/SUP (leads), DOC (the legal-version citation in agreements),
Postmark (via NOT), Cloudflare (edge cache), Prometheus (page 404 rate,
lead volume, widget cache hit rate), Sentry.

## 14. Integration — internal modules (glue)

| Module | How |
|---|---|
| **TEN** | the catalog (pricing widget data), domain resolution (custom domains — TEN-14's config already resolves them for TD/ADM; the sites renderer adds the public route), branding (logo/colors seed the starter site) |
| **ANA** | the `published_stats` source (the tenant-approved aggregates) + the visit→signup funnel top (the site's `site.visit` events feed ANA-09's funnel from a new step: `visited`) |
| **CRM** | leads = prospects (the lifecycle gains `prospect` at the top, 20 §3.1) |
| **SUP** | lead tickets (category `lead`, capped queue) |
| **CHK** | the pricing widget's CTA deep-links to checkout; the catalog endpoint is the same one TD's purchase flow uses (one price source) |
| **DOC** | legal page versions cited in agreements (the DOC-03 mapping variable) |
| **EVT** | site events on the bus (the `site.*` topic) |
| **NOT** | lead notifications (tenant sales + the lead's ack email) |
| **AUD** | publishes (critical on legal), lead access, rollback |

## 15. Integration — external tools

Cloudflare (edge + custom domains), R2, Postmark (via NOT),
Prometheus/Grafana, Sentry.

## 16. Implementation blueprint (V3)

| Step | Owner | Est | Depends | Exit criteria |
|---|---|---|---|---|
| 1. Content schema (pages/blocks/media) + block registry (10 V3 blocks, typed schemas) + renderer (RSC, CDN cache, the 5-min dynamic rule) | FE-2 + BE-2 | 4 wks | OPS (web), TEN catalog API | the starter site renders for a seeded tenant; price change in TEN → site ≤ 5 min |
| 2. Editor (block tree, preview with live data, publish/rollback/schedule, media library, SEO controls) in ADM | FE-2 | 4 wks | 1 | a tenant staff member publishes a page end-to-end; rollback restores the exact prior version (diff-checked) |
| 3. Forms/leads (capture → CRM/SUP/NOT, honeypot + caps, encrypted storage) + legal pages (templates, review-note gate, version citation in agreements) | BE-2 + FE-2 | 3 wks | 2, CRM, SUP, DOC | a lead lands in CRM + the queue; a legal publish without review note is blocked (tested) |
| 4. Published stats (ANA source + tenant approval + auto-refresh) + blog (markdown + sanitize) + scheduled publishing worker + analytics hooks (first-party counter) | BE-2 | 2 wks | 1–3 | the social-proof block shows tenant-approved numbers only (property: raw aggregates are not exposed) |
| 5. Provisioning step in the saga (CMS-01) + template library (the FunderBlu seed) + multi-tenant hardening pass (isolation, cache keys, per-tenant robots/sitemap) | BE-2 + FE-2 | 2 wks | 4, TEN saga | a new tenant's site exists at saga completion; cross-tenant cache-key test green |

---

# Part B — CMP: Competitions & Gamification (17 reqs)

## 1. Purpose & scope

Trading competitions (the prop-firm growth engine: "fund 100 traders,
the top 5 get scaling bonuses"), leaderboards, prizes, and the
gamification layer (badges, XP, trader levels, public profiles).
All V3 per the PRD.

**Binding decisions:**
- **Competitions run on dedicated competition accounts** (CMP-02):
  entries provisioned through the **LCC** (a `competition` account
  class — LCC's state machine gains the class, the same `Transition()`
  discipline, 07 §3.2) — a competition is never an overlay on a
  trader's real funded account (the money-safety rule: contest pressure
  must not sit on real liability).
- **Scoring is the EVL engine's data, not its enforcement** (CMP-04):
  the scoring engine reads the same observed metrics (equity, PnL, draw-
  down — the EVL-49 observed feed, ANA's equity_points) under the
  competition's ruleset (a **rule pack version**, the EVL-01 pattern:
  the competition's scoring rules are versioned data, frozen at
  registration). The competition's "disqualification" is a CMP state,
  enforced by halting the competition account (LCC command — the
  LCC-41 rule generalized again: CMP decides, LCC acts).
- **Prizes are real money or real value** (CMP-07): prize payouts go
  through **PAY** (a prize is a payout object with `kind: prize` — the
  eligibility, approval (2FA, finance), execution, and ledger rules all
  apply; a competition prize is not a special money path) — or non-
  monetary (scaling bonus = a terms change on their real funded account,
  an LCC action with the trader's consent notice).
- **Leaderboard integrity (CMP-06)** is a first-class design goal
  (§3.3): the board is computed, cached, and **disputable**, never
  trusted.

Requirement coverage: `CMP-01..17` (all V3).

## 2. Architecture

```
 ADM (CMP-13 admin) creates competition:
   { tenant, name, window, entry rules (max entries CMP-14, package,
     eligibility: KYC L2 + no open risk case), scoring ruleset (versioned
     data: metric, period, tie-breaks, DQ conditions), prizes (ordered,
     kind: cash|scaling_bonus, value, ledger source: tenant) }
 entry (trader, TD): register ──► CMP validates (eligibility, entry
   limits) ──► LCC provisions the competition account (the 9-step saga,
   LCC-41 command) ──► entry active
 live window:
   scoring worker (advisory-lock, 5-min ticks over equity_points — the
   ANA feed; the competition window is bounded, so the scoring compute
   is O(entries × ticks), cheap):
     score = f(rule set, observed metrics)  — pure function, versioned
     (the EVL-04 discipline: re-runnable from the snapshot — a disputed
     score re-computes from the same inputs, CMP-17)
     DQ conditions evaluated per tick (the DQ = a verdict row: rule,
     input snapshot, at — the EVL-17 evidence pattern)
   leaderboard: computed at each tick → cached (Redis 5 min + PG history
     snapshots hourly) → rendered in TD (public, CMP-11: the trader's
     public profile + their rank; the public surface shows name-masked
     or chosen display name — the trader's choice, the privacy default
     is masked)
 close:
   final scoring (from the full window's snapshots) ──► results (CMP-08:
   the immutable result set: rank, score, prize, evidence refs) ──►
   prize execution: cash → PAY (kind: prize, finance 2FA, the tenant's
   ledger funds it — the prize is a tenant obligation, booked at
   creation: LED entry at competition creation = the liability is
   visible from day 1, the PAY-37 reserves posture generalized);
   scaling bonus → LCC terms action (consent notice)
   dispute window (CMP-17, 7 d): a trader disputes a DQ/rank → the
   evidence pack (inputs + rule set + recompute) + RSK-41-class appeal
   flow (the RSK case with kind=competition_dispute — the RSK §3.2
   machine handles it; CMP provides the evidence)
 gamification (CMP-09/10/11):
   badges/XP: event-driven (funded, first payout, 30-day streak,
   competition finisher — the same event-consumer pattern as ANA's
   funnel steps); XP/levels are tenant-configured (the level table is
   data); badges render in the TD profile + public profile (CMP-11:
   the public profile = display name, country (optional), badges,
   competition history, verified-funder badge — no account data, no PII,
   the trader controls visibility)
   notifications (CMP-12): standing changes (top-10 entry/exit),
   DQ (with reason class), results, prize paid — via NOT templates
   teams (CMP-16): a team = a set of entries under one score
   (aggregate metric, the scoring ruleset's `team` variant); the team
   surface is V3-late (the solo path ships first)
 templates (CMP-15): competition templates (the "monthly funded-100"
   config saved + re-instantiated) — the recurring-competition machine
```

## 3. System design

### 3.1 The competition state machine (CMP-01/08)

```
draft → announced (public, entry open) → live (window running;
entries frozen at window start — the late-entry rule is config:
`entries_close_before_live: true` default) → scoring (window closed,
final compute) → results (published; dispute window 7 d) → settled
(prizes executed) → archived
side states: cancelled (pre-live; entries refunded via CHK refund
flow — the entry fee is a purchase, the refund is a refund, 12 §3.4),
aborted (mid-live, incident: all entries → the incident path, the
ledger liability released, the trader notice is the SUP template)
```

### 3.2 Entries & accounts (CMP-02/03/14)

- An entry = `{competition, trader, entry_fee (a CHK purchase — the
  fee is real revenue, booked normally; the entry fee is separate from
  the prize liability), competition_account_id, status}`.
- Entry fee → the normal purchase flow (CHK → LED → the fee is the
  tenant's; if the tenant offers "free entry", the entry is `fee: 0` —
  the flow is identical).
- **Entry limits (CMP-14):** max entries per trader (config, default
  1), per-competition cap (default 100), both enforced at registration
  with the `cmp.limits` code; the LCC command carries
  `idempotency_key: compete:{comp}:{trader}` (the 07 pattern).
- The competition account: a real broker account (MetaApi — the cost
  line: 100 entries × $75/mo = the tenant's prize event budgeted in
  BIL-17 pass-through, the 08 cost-control note) with a **simplified
  terms** (the competition ruleset, no target, the DQ conditions = the
  scoring ruleset's DQ list) — the account class `competition` in LCC
  (the state machine's `phase` field already has room: `phase:
  competition`).

### 3.3 Scoring & leaderboard integrity (CMP-04/05/06/17)

- **Pure, versioned, re-runnable** (the EVL-04 commitment applied):
  `score(entry, rule_set_version, metric_snapshots) → {score, dq:
  []}`; the 5-min worker stores per-tick scores + the input snapshot
  refs (equity_points row ids) — a dispute (CMP-17) re-runs the
  function over the stored snapshots and the result **must** match the
  stored one (the recompute property is a CI test vector, the EVL-54
  pattern) — the "but the board said X" answer is a number, not an
  apology.
- **Leaderboard = computed + cached + snapshot history** (hourly):
  the public board shows the latest 5-min compute with an `as_of`
  label (the ANA-14 freshness rule on a public surface — a board
  without an as_of is a bug); the hourly snapshots make "what was the
  board at 3 pm" answerable (the dispute class: "I was 2nd at 3 pm
  and the board shows 5th").
- **Anti-manipulation (the CMP-06 real work):** the scoring metrics are
  the **observed** ones (not self-reported); DQ conditions include the
  conduct rules (the EVL conduct pack applies to competition accounts
  — hedging/copying/latency in a competition = DQ, the RSK detectors
  run on competition accounts too, §24-A's "RSK runs on all accounts"
  is the rule); **abnormal-activity DQs** are flagged for human
  review before final results (the worker flags; a human confirms —
  the same "V1 human-in-the-loop" posture scaled up); the final
  results are **frozen at `results`** (post-freeze changes only via
  the dispute flow — the result set is the EVL-verdict-grade
  immutable record).
- **Tie-breaks** are config (the ruleset: drawdown, then earliest
  window completion, then random seed published at creation — the
  published seed is the fairness property: no post-hoc tie-break
  editing).

### 3.4 Prizes & money (CMP-07)

- **At creation:** the total prize pool is booked as a tenant
  obligation (LED: `competition_liability` debit / cash credit — the
  tenant's money is set aside conceptually from day 1; the PAY-37
  reserves check extends to include competition liabilities —
  "the tenant can't fund a prize pool their collected funds don't
  cover").
- **At settlement:** cash prizes → PAY objects (`kind: prize`, the
  trader's payout method, finance 2FA, the PAY-12 execution records);
  the prize is exempt from payout-frequency rules (it's not a profit
  payout — the eligibility check's frequency clause is skipped for
  `kind: prize`, everything else applies: KYC L2, risk hold, method
  validation); scaling bonuses → LCC terms action with the consent
  notice (the trader accepts the new terms — no silent upgrades).
- **Tax:** prize amounts are the tenant's reporting responsibility
  (the terms say so — the competition page's legal block, the CMS-08
  template carries the prize-terms paragraph).

### 3.5 Gamification (CMP-09/10/11)

- **Badges:** event-driven (the consumer pattern): funded, first
  payout, 90-day active, competition top-10, streak 30 d (the streak
  = the ANA funnel's activity facts). Badge definitions are tenant
  data (icon, name, criteria, visibility).
- **XP/levels (CMP-10):** the level table is tenant data (XP per
  badge/event, level thresholds); levels render in the TD profile +
  public profile; **levels confer no money** (the rule: gamification
  never gates payouts or eligibility — a level is a badge, not a
  permission; the anti-design: "level 5 required to withdraw" is
  banned, it's a retention trap with compliance exposure).
- **Public profiles (CMP-11):** display name (the trader's choice;
  the real name is never public), country (optional), badges,
  competition history (public results only — DQs are public too, the
  integrity property: a public board that hides its DQs is a board
  that games trust), the verified-funder mark (the account is/was
  funded — the DOC-16 verification pattern: a profile QR → the verify
  page). Privacy default: **masked** (the profile exists but shows
  display name + badges only; the trader opts in to more).
- **Community (CHT-03, doc 26) links in**: the public profile is the
  community's identity anchor (the CHT integration reuses it).

## 4. Events (topic `competition`)

| Event | When | Consumers |
|---|---|---|
| `competition.created/announced` | lifecycle | NOT (tenant subscribers), AUD |
| `competition.entry_registered` | entry + account provisioned | LCC (saga), AUD |
| `competition.dq_flagged` | worker DQ (pre-confirmation) | ADM (review), AUD |
| `competition.dq_confirmed` | human confirms (or auto for hard DQs) | NOT (trader, reason class), LCC (halt command), AUD (critical) |
| `competition.results_published` | freeze | NOT, DOC (results certificate — the DOC-15 QR verify extends to results), AUD (critical) |
| `competition.prize_paid` | PAY settled (kind: prize) | NOT, AUD |
| `competition.dispute_opened/decided` | CMP-17 flow (via RSK case) | NOT, AUD |
| `competition.standing_changed` | top-10 move (5-min worker) | NOT (the traders in the top 10), ANA |
| `gamification.badge_awarded` / `gamification.level_changed` | event-driven | NOT, TD (profile update) |

Consumes: `equity.point` (scoring ticks — the ANA feed), `account.
state_changed` (badge events), `payout.settled` (badges), `risk.
case_decided` (dispute outcomes), `order.paid` (entry
fees — the extended `payment.intent_captured` alias, docs/12).

## 5. Lifecycles

- **Competition:** §3.1 machine (side states `cancelled`/`aborted`).
- **Entry:** `registered → active (account live) → finished |
  dq_flagged → dq_confirmed | forfeited (no-show: the entry fee is
  non-refundable per terms — the terms block says so)`.
- **Score tick:** append-only per tick (the snapshot refs make it
  re-runnable); hourly board snapshots retained 1 yr (the dispute
  window is 7 d; the 1 yr is the marketing/press class).
- **Prize (PAY object):** the PAY-13 machine with `kind: prize`
  (the one eligibility exemption, §3.4).
- **Badge/level:** `awarded → (level recompute) → retained` (badges
  are permanent — the anti-design: revoked badges for conduct are
  possible (the DQ badge override) but the action is 2FA'd + audited,
  and the DQ is public on the profile).
- **Dispute:** the RSK-41-class machine (open → decided, 7-day window,
  the evidence pack = the CMP-17 record).
- **Template (CMP-15):** `saved → instantiated N times` (each
  instantiation is a fresh competition, the template is the config
  seed).

## 6. Error taxonomy

Namespace `CMP`:

| Code | HTTP | Meaning |
|---|---|---|
| `cmp.not_open` | 409 | Entry outside the entry window |
| `cmp.limits` | 422 | Entry limit hit (`details`: per-trader or per-competition) |
| `cmp.ineligible` (with `checks[]`) | 422 | KYC L2 / open risk case / existing entry |
| `cmp.dq_pending` | — | Score queried during DQ review (the board shows "under review" for that entry — the integrity UX) |
| `cmp.results_frozen` | 409 | Post-freeze mutation attempt (dispute path only) |
| `cmp.prize_pool_insufficient` | 422 | Creation with a pool the tenant's reserves can't cover (the PAY-37 generalization) |
| `cmp.dispute_window_closed` | 409 | Late dispute (the 7-day rule) |
| `cmp.team_limits` | 422 | (CMP-16) Team composition rules violated |
| `cmp.template_invalid` | 422 | Instantiation failed the ruleset schema |
| internal: `cmp.score_recompute_mismatch` | — | The recompute property failed (CRITICAL — the scoring function or its inputs are broken; the board is frozen + ops paged until resolved — **a mismatch is never silently re-scored**) |

## 7. API endpoints

Trader (TD): `GET /v1/competitions` (open/active/archived for the
tenant), `GET /v1/competitions/{id}` (rules, prizes, board, their
entry), `POST /v1/competitions/{id}/entries` (the fee purchase flow —
CHK intent, the same as a package purchase), `GET /v1/competitions/{id}/
board` (the public board, as_of-labeled), `POST /v1/competitions/{id}/
disputes` (the window + the reason), `GET /v1/profiles/{handle}`
(public, the masked-by-default surface).

Staff (ADM, CMP-13): `GET|POST /v1/admin/competitions` (+ the full
lifecycle actions, 2FA on create (the liability booking) and on
results publish), `GET /v1/admin/competitions/{id}/dq-queue` (the
confirmation queue), `POST /{entry}/dq-confirm`,
`GET /v1/admin/competitions/{id}/scoring` (the per-tick scores +
recompute button — the recompute is a read-only proof, 2FA'd),
`POST /v1/admin/competitions/templates` (CMP-15).

Public: `GET /v1/public/{tenant}/competitions/{id}/board` (the
unauthenticated board — a competition page is a marketing page; CMS-04
widget's sibling).

## 8. Schema (key shapes)

```jsonc
// board (public + TD)
{ "data": { "competition_id": "01J9CMP…", "as_of": 1758282000000,
    "window": { "ends_at": 1758886800000 },
    "rows": [ { "rank": 1, "display_name": "ali_k", "handle": "ali_k",
                "score": 842100, "dq": false, "entry_id": "01J9ENT…" },
              { "rank": 2, "display_name": "★ masked ★", "score": 815000,
                "dq": false, "under_review": false } ] } }

// dispute (CMP-17)
{ "data": { "id": "01J9DSP…", "entry_id": "01J9ENT…",
    "target": "dq" /* | "rank" */, "at": 1758282000000,
    "evidence": { "rule_set_version": 3, "tick_refs": ["…"],
                  "recompute": "match", "verdict": "confirmed" } } }
```

## 9. Database design

```sql
CREATE TABLE competitions (
  id          ULID PRIMARY KEY,
  tenant_id   ULID NOT NULL,
  name        TEXT NOT NULL,
  status      TEXT NOT NULL DEFAULT 'draft'
    CHECK (status IN ('draft','announced','live','scoring','results',
                      'settled','archived','cancelled','aborted')),
  window_from TIMESTAMPTZ NOT NULL, window_to TIMESTAMPTZ NOT NULL,
  entry_close TIMESTAMPTZ NOT NULL,
  ruleset     JSONB NOT NULL,                -- versioned: metric, period,
  ruleset_version INT NOT NULL,              --   tie-breaks (incl. seed),
                                             --   DQ conditions, team?
  prize_pool  JSONB NOT NULL,                -- ordered prizes: kind, value,
                                             --   ledger_source
  liability_entry_id ULID,                   -- LED: booked at creation
  entry_fee_cents BIGINT NOT NULL DEFAULT 0, -- CHK purchase amount
  limits      JSONB NOT NULL,                -- {per_trader, per_competition}
  template_id ULID,                          -- CMP-15
  created_by  ULID, created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_cmp_tenant ON competitions(tenant_id, status, window_to);

CREATE TABLE competition_entries (
  id            ULID PRIMARY KEY,
  competition_id ULID NOT NULL REFERENCES competitions(id),
  tenant_id     ULID NOT NULL,
  identity_id   ULID NOT NULL,
  account_id    ULID,                        -- the LCC competition account
  entry_fee_ref ULID,                        -- the CHK order (fee > 0)
  status        TEXT NOT NULL DEFAULT 'registered'
    CHECK (status IN ('registered','active','finished','dq_flagged',
                      'dq_confirmed','forfeited')),
  display_name  TEXT, handle TEXT,           -- the public identity (CMP-11)
  registered_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (competition_id, identity_id)
);
CREATE INDEX idx_cment_comp ON competition_entries(competition_id, status);

CREATE TABLE competition_scores (             -- per-tick (re-runnable)
  id            ULID PRIMARY KEY,
  entry_id      ULID NOT NULL REFERENCES competition_entries(id),
  as_of         TIMESTAMPTZ NOT NULL,
  metric_refs   JSONB NOT NULL,              -- equity_points row ids (the
                                             --   input snapshot — CMP-17)
  score         BIGINT NOT NULL,
  dq_flags      JSONB NOT NULL DEFAULT '[]', -- rule + snapshot per flag
  UNIQUE (entry_id, as_of)
);
CREATE INDEX idx_cscore_entry ON competition_scores(entry_id, as_of DESC);
CREATE TABLE competition_board_snapshots (    -- hourly (dispute history)
  id          ULID PRIMARY KEY,
  competition_id ULID NOT NULL, as_of TIMESTAMPTZ NOT NULL,
  rows        JSONB NOT NULL,                -- ranked (rank, entry, score,
                                             --   dq, under_review)
  UNIQUE (competition_id, as_of)
);
CREATE TABLE competition_results (            -- the frozen set
  id            ULID PRIMARY KEY,
  competition_id ULID NOT NULL,
  entry_id      ULID NOT NULL,
  final_rank    INT NOT NULL, final_score BIGINT NOT NULL,
  prize_ref     ULID,                        -- the PAY object (kind: prize)
  evidence      JSONB NOT NULL,              -- rule set version + tick refs
  published_at  TIMESTAMPTZ NOT NULL,
  UNIQUE (competition_id, entry_id)
);
-- gamification: badges (tenant, key, icon, criteria, visibility),
-- user_badges (identity, badge, at), user_xp (identity, xp, level) —
-- event-consumer-populated (the ANA funnel pattern)
```

## 10. Security & compliance

- **Money integrity:** the prize pool is booked at creation (§3.4 — the
  liability is visible before a single entry; the reserves check
  covers it); prizes move through PAY (the 2FA/execution-record/ledger
  discipline — no special path); entry fees through CHK (the normal
  revenue path); **competition money never has its own ledger** (the
  LED-01 posture: one ledger, no side books).
- **Integrity = the product** (CMP-06/17): recompute-mismatch = board
  freeze + page (never silent re-score); DQs are public; the tie-break
  seed is published at creation; the dispute flow is the RSK-grade
  evidence pattern. A competition the traders don't believe in is a
  churn event for the tenant — the integrity features are the
  retention features.
- **PII on public surfaces** (CMP-11): display name + handle only by
  default; the handle is chosen by the trader (uniqueness per tenant);
  the public board/profile exposes **no** account numbers, balances,
  PII, or real names; the verify QR (the DOC-16 pattern) shows the
  funded-fact, not the person.
- **Conduct rules apply** (the scoring DQs + the RSK detectors on
  competition accounts, §3.3): a competition is the highest-
  manipulation-risk surface on the platform (real prizes, public
  ranks) — the EVL conduct pack + the RSK-05/06/38 detectors run on
  `phase: competition` accounts with the same idempotency (the
  LCC-43 pattern: one DQ per verdict).
- **No gamification gating of money** (§3.5 rule): levels/badges never
  affect payout eligibility or account state — a compliance + trust
  line, enforced by the rule that no LCC/PAY eligibility check reads
  the gamification tables (a CI property test asserts the absence).
- **Aborted competitions** (the incident path): the entry-fee refunds
  (CHK flow) are automatic per the terms block; the prize liability
  releases to the tenant's books with the incident note (the CON-15
  control ladder's "tenant halt" can abort live competitions — the
  control's blast-radius text names it).

## 11. Scalability considerations

- A competition = 100 entries × a 2-4 week window × 5-min scoring
  ticks ≈ 4k scoring rows/competition/week — trivial for PG; the
  scoring worker is O(entries) per tick over indexed equity_points
  reads (sub-second at 100 entries; at 1k entries, batch the reads —
  still seconds; the tenant caps the size in `limits`).
- The public board: Redis 5-min cache (the 5-min compute is the
  freshness contract, as_of-labeled) — even a 10k-viewer launch day is
  edge/Redis reads.
- Multiple simultaneous competitions (the monthly + the special): the
  worker shards by competition (advisory-lock per competition id — the
  06 pattern); the board cache keys include the competition id.
- The hourly board snapshots: 24 rows/competition/day — retention 1 yr
  is a few thousand rows.
- Broker account cost is the real constraint (100 × $75/mo MetaApi,
  08): competition size is a **tenant budget decision** (the BIL-17
  pass-through shows them the number), not an engineering one.
- Badges/XP: the event-consumer pattern (ANA §2) — zero added cost
  beyond the funnel facts.

## 12. Open-source solutions

| Option | Verdict |
|---|---|
| **In-house (LCC accounts + EVL-observed scoring + PAY prizes)** (this design) | **CHOSEN** — every subsystem a competition needs already exists with its discipline (state machines, pure scoring, money paths); the competition is a composition, not a new system |
| Polymarket-class / trading-game engines (OSS contest platforms) | Rejected: they own scoring + payouts — the two things that must stay on the LCC/EVL/PAY rails; an external engine = an integrity boundary we can't audit (the recompute property dies) |
| Leaderboard OSS (e.g. general-purpose ranking libs) | Rejected at this scale: a Redis sorted set + the PG snapshots is the whole leaderboard (the integrity is in the compute, not the store) |
| (CHT) Discord for the competition community | The V3 community path (doc 26) — the competition page links the Discord, the identity is the public profile handle |

## 13. Technology stack

Go domain pkg (api + workers: scoring, board cache, badge/XP
consumers, dispute window); Postgres (competitions/entries/scores/
snapshots/results/gamification); Redis (board cache); LCC (the
`competition` account class), EVL (the conduct pack on competition
accounts), PAY (`kind: prize`), CHK (entry fees), ANA (the
equity_points feed + funnel facts), NOT (templates), DOC (results
certificate + the verify page), RSK (disputes + detectors), ADM
(CMP-13 surfaces), Prometheus (scoring lag, board freshness, DQ rate,
recompute mismatches = the CRITICAL metric), Sentry.

## 14. Integration — internal modules (glue)

| Module | How |
|---|---|
| **LCC** | the `competition` account class (the phase value + the simplified terms snapshot, the LCC-20 rule: frozen at registration); DQ = the LCC-41 halt command; the account provisioning reuses the 9-step saga |
| **EVL** | the observed metrics feed (the scoring input — EVL-49); the conduct pack runs on competition accounts (the DQ conditions overlap it; the verdict idempotency LCC-43 applies) |
| **ANA** | equity_points = the scoring substrate (the worker reads the ANA table, not the BRG API — the read-model discipline); the public stats block (CMS-10) can publish competition results ("100 traders funded in the August contest") |
| **CHK** | entry fees (the normal purchase flow; the fee = 0 case is the free-entry path) |
| **PAY** | prizes (`kind: prize`: the eligibility exemption for frequency only — KYC L2, risk hold, method validation all apply; the PAY-12 records; the LED settlement) |
| **LED** | the prize-pool liability at creation; the settlement at payment; the entry-fee revenue at capture |
| **RSK** | the dispute flow (the RSK-41 case with `kind: competition_dispute`); the detectors (copy/inverse/latency) on competition accounts; the DQ-evidence → RSK signal path (a confirmed conduct DQ is an RSK signal for the trader's other accounts — the cross-account honesty) |
| **NOT** | standing changes, DQ notices (reason class), results, prize paid, the dispute flow notices |
| **DOC** | the results certificate (the DOC-15/16 QR verify extends: "verified: 2nd place, August contest, FunderBlu") |
| **CMS** | the competition page widget (the public board, §7) + the competition-terms legal block (the CMS-08 template) |
| **TD** | the competitions section (TD-10's sibling screen) + the public profile surface |
| **BIL** | the MetaApi cost pass-through for competition accounts (the tenant's budget visibility) |
| **AUD** | creation (the liability booking, critical), DQ confirm (critical), results publish (critical), prize pay (critical), every dispute step |

## 15. Integration — external tools

MetaApi (competition broker accounts — the 08 rail), Redis, Postmark
(via NOT), R2 (badges/icons, results PDFs via DOC), Prometheus/Grafana,
Sentry, (V3 community) Discord API (the CHT path).

## 16. Implementation blueprint (V3)

| Step | Owner | Est | Depends | Exit criteria |
|---|---|---|---|---|
| 1. LCC `competition` account class (phase, simplified terms, the saga) + CMP schemas + ruleset versioning + the scoring pure function + CI recompute property | BE-2 | 3 wks | LCC, ANA feed, EVT | a competition account provisions through the saga; the recompute property passes with seeded metric snapshots (the EVL-54-grade test vector) |
| 2. Entry flow (eligibility, limits, the fee via CHK, the idempotent LCC command) + ADM competition manager (create/announce with the liability booking) | BE-2 + FE-2 | 3 wks | 1, CHK, LED | 100 sandbox entries register (fee + free paths); the liability entry exists at creation (the books show the pool) |
| 3. Scoring worker (5-min ticks, DQ flags, the under-review state) + board compute + Redis cache + as_of labeling + hourly snapshots + public board | BE-2 | 3 wks | 1–2 | a live sandbox competition: board updates within 5 min + 60 s of each tick; the as_of is always present; a seeded DQ shows "under review" on the board |
| 4. Close flow: final scoring → results freeze → prize execution (PAY kind: prize, 2FA, the reserves check incl. pools) + scaling-bonus LCC action + results certificate (DOC + verify) | BE-2 | 3 wks | 3, PAY, DOC | end-to-end in staging: a 5-entry competition settles — prizes paid via the real rail flow, the certificate verifies, the books balance (the pool = the payouts + the retained margin) |
| 5. Disputes (the 7-day window, the evidence pack, the RSK-case flow) + the recompute proof button + the mismatch-freeze behavior + DQ confirmation queue | BE-2 + FE-2 | 2 wks | 4, RSK | a seeded dispute: the recompute matches (or the board freezes + pages — both paths tested); the decision lands via the RSK case with the notice |
| 6. Gamification (badges/XP/levels, the no-money-gating property test) + public profiles (masked default, handle, verify QR) + templates (CMP-15) + notifications + teams (CMP-16, solo-first) | BE-2 + FE-2 | 3 wks | 4–5 | a trader's public profile is fully masked by default (the property test); a monthly template re-instantiates a fresh competition; the CI test proves no LCC/PAY check reads gamification tables |

**Risks:** a scoring dispute going public and ugly (mitigation: the
recompute property + the public DQs + the published tie-break seed +
the 7-day dispute flow with a named human decision — the §10
integrity stack is the PR for this risk); competition-account cost
surprise (the BIL-17 pass-through + the tenant's `limits` cap make the
budget visible before creation — the CMP-06 cost line is on the
create dialog); manipulation at scale (copy/inverse/latency on real
prizes — the EVL conduct pack + RSK detectors run on the class from
day 1, §3.3; the DQ is public so the manipulation attempt is visible
as such); the gamification trap (levels that gate money — banned by
rule + property test, §3.5); scope creep into "trading game" territory
(the binding line: entries are real broker accounts under real terms —
it's a competition, not a game; paper-trading contests are TRD-05
(doc 27), a different module).

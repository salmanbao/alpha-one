# 35 — Testing Strategy (how we prove it works)

> The test pyramid, the invariant suite, the contract gates, and
> the phase-by-phase assurance map. Every docs/99 task exit
> criterion names its tests; this doc names the machinery they
> run on. CI lives in docs/06; security assurance in docs/28
> §11–12; load targets in docs/29 §6 — this doc is the test
> plan that ties them together.
>
> Requirement coverage: cross-cutting (quality; no PRD module).

## 1. The pyramid (per stack)

| Layer | Go services | Rust (EVL) | Next.js (TD/ADM/CON) | Node (DOC worker) |
|---|---|---|---|---|
| unit | `go test` per package; pure functions (eligibility, verdicts, scoring) table-driven | `cargo test`; `evaluate()` has 100% branch coverage (EVL-35/54 vectors live here) | Vitest for hooks/utils; MSW for API mocks | Vitest for mappers (frozen-snapshot fixtures) |
| property | `gopter`/`rapid`: state machines (LCC, payout, KYC), money invariants (§3) | `proptest`: recompute-hash, boundary TZ shifts, rule composition | — (playwright asserts UI-visible invariants instead) | — |
| integration | `testcontainers`-class: real PG + Redis per suite; outbox→relay→consumer paths | axum test client + PG; tick-sequence → verdict flows | Playwright: full journeys on staging (login → buy → trade → payout → receipt) | Puppeteer renders golden PDFs (pixel-diff on approval) |
| contract | OpenAPI + event-schema gates (§4); adapter suites (BRG-43) | verdict/event JSON Schema validation | API-mock parity: MSW handlers generated from `contracts/` | mapper output validated against `contracts/data/dictionary.md` |
| load | k6 in CI nightly + pre-gate (docs/29 §6 numbers) | k6 on `/evaluate` at tick-burst rates | Lighthouse CI (FCP/LCP budgets, docs/16 §11) | render-throughput (docs/min at p95) |
| security | `gitleaks`, dep-scan, SAST (golangci-lint), `isolation.test` | `cargo audit`, `cargo deny` (licences, docs/34 §4) | ESLint security rules, secret-scan on bundles | `npm audit`, licence check |

**Coverage bar:** unit + integration ≥ 80% lines on Go/Rust money
paths (LED, PAY, LCC, EVL, BRG), ≥ 60% elsewhere; every public
endpoint has at least one integration test; every state machine
has a property test (§3). Coverage is a floor, not a goal — the
invariant suite (§3) is the goal.

## 2. Test data (factories, never fixtures-in-prod-shape)

- **Factories per aggregate** (trader, account, order, payout,
  case, tenant): deterministic seeds, Faker-class values, created
  through the **public API/handlers** (never raw SQL) so tests
  exercise the real validation.
- **Staging is synthetic-only** (docs/06 §2): any prod-like
  dataset is a legal event + CON sign-off + anonymization
  (docs/25 §3.7). CI blocks seed files containing real PII patterns
  (the `gitleaks` + a PII-pattern check).
- **Golden sets:** the "clean" deal set (RSK zero-false-positive
  baseline, docs/10 §3.3), the EVL test vectors (EVL-54), the
  conformance fixtures (SDK-02, docs/27 Part A §2), the PDF goldens
  (docs/15 §12). Goldens live in-repo, versioned with the code.

## 3. The invariant suite (property tests — docs/28 §11)

These run in CI on every PR (fast subset) and nightly (full
generators). Each names its owner doc:

| # | Invariant | Asserts | Owner |
|---|---|---|---|
| I-01 | tenant isolation | querying any table as another tenant returns 0 rows (`isolation.test`) | 04 §11 |
| I-02 | no double-payout | available-profit calc (PAY-02): paid profit can never be paid again | 11 §11 |
| I-03 | verdict recompute | re-running `evaluate()` over stored snapshots reproduces the verdict hash | 09 §3.4 |
| I-04 | machine confinement | no LCC/payout/KYC path bypasses its state machine (illegal transitions rejected) | 07/11/13 §11 |
| I-05 | double-enforcement | the same breach decision executes at most once (LCC-41/43) | 07 §11 |
| I-06 | trailing-HWM monotonicity | the HWM never decreases within a spell; breach fires exactly at the line (EVL-29) | 09 §11 |
| I-07 | ledger balance | every posting balances; reversals reference their original + reason | 05 §11 |
| I-08 | audit fail-closed | a failed audit write rolls back the business action (never silent) | 05 §11 |
| I-09 | `as_of` honesty | a stale read model shows its stale `as_of`, never a silent number (ANA-14) | 19 §11 |
| I-10 | no raw ULID on public | public APIs expose refs only (the ref-indirection, SDK/DVP) | 27-A §8 |
| I-11 | PAPER badge | a paper account can never touch a live rail / show a funded badge | 27-B §5 |
| I-12 | JRN privacy | no cross-trader read path exists in journal queries (query-shape test) | 26-C §11 |
| I-13 | EDU answer-key | assessment answers never leave the server (response-shape test) | 26-D §3 |
| I-14 | 404-not-403 | cross-tenant/unauthorized reads return 404, never 403 or data | 04 §11 |
| I-15 | dedupe/idempotency | double-delivery and double-submit collapse to one effect (NOT-13, GW-12) | 14/04 §11 |
| I-16 | frozen snapshots | documents/decisions render from snapshots, never live tables (query-shape test) | 15 §11 |

## 4. Contract gates (code vs `contracts/`)

| Gate | What it checks | Fails the build when |
|---|---|---|
| error-registry | handler error codes ⊆ docs/30 taxonomy | an unknown code is emitted |
| openapi-parity | routes + params + status codes = the frozen spec | a route/param/code drifts (public drift = also a freeze violation, docs/99 §12) |
| event-catalog | emitted events ⊆ docs/31 with valid envelope + version | an unknown event or envelope violation (`EVT_WEBHOOK_SCHEMA_INVALID`) |
| schema-check | migrations ⊆ docs/32 conventions (ULID, tenant_id, `_cents`, TZ) | a convention break |
| adapter-suite (BRG-43) | every broker adapter passes the capability contract tests against sandbox | a capability lies (claims `Capabilities()` it fails) |
| webhook-schema | outbound payloads validate against `contracts/events/` | a payload/schema mismatch |
| public-docs | every public route documented in the DVP (V3) | an undocumented public route |

## 5. Load & performance (docs/29 §6 numbers)

- **k6 suites:** V1 numbers at M1, 2× V1 at M3, V2 numbers at M4,
  V3 numbers at M5 (docs/99 §10). Suites live in-repo next to the
  service they hammer; nightly CI runs the smoke profile, gates
  run the full profile.
- **Budgets:** GW p95 per docs/04 §6; EVL verdict latency per
  docs/09 §11; TD FCP/LCP per docs/16 §11; DOC renders/min per
  docs/15 §12. A gate fails if any budget regresses >10% without
  a recorded capacity decision (PLT-02 precursor, docs/29 §1.3).
- **Soak:** 24-h soak at gate load before M2 (cutover) and M4 —
  connection leaks, slow Streams growth, and disk curves are the
  usual catches.

## 6. Security testing (docs/28 §11–12)

- **Every PR:** `gitleaks`, dep-scan, SAST (golangci-lint,
  ESLint, `cargo audit`), the I-01/I-14 isolation tests.
- **Every phase:** the §12 phase-mapping checklist (AUD on
  sensitive actions, ABAC on access, encryption on PII —
  docs/99 §12 point 4).
- **Annual:** external pentest scoped to GW + portals + DVP +
  public API + BRG + R2 signed URLs + webhook signatures
  (docs/28 §11); quarterly game-day from V3 (PLT-05).
- **Continuous:** weekly audit review (CON-13/15), monthly
  restore drill (docs/06 §3.2), 90/180-day secret rotation,
  weekly dep-scan (docs/28 §12).

## 7. Migration & cutover testing (docs/25)

- The anonymized dry run (task 2.2) is a **test**, not a demo:
  the 100%-or-dispositioned sha256 gate must pass on the full
  TTS export shape before the parallel run starts.
- The 14-day parallel run (task 2.3) is a **differential test**:
  per-day delta reports with zero unexplained rows, 14 days
  running, or the M2 gate fails.
- The rollback (restore-from-TTS runbook) is **rehearsed**
  before cutover (docs/06 §3.3 class) — an unrehearsed rollback
  is not a rollback.

## 8. Assurance map (what proves each milestone)

| Gate | Proof (all green) |
|---|---|
| M0 | I-01, I-14, I-15; contract gates on v0; first restore drill; MetaApi demo trades |
| M1 | I-01…I-09, I-14…I-16; V1 load; Playwright money-loop journey; contracts v1 |
| M2 | differential parallel (zero unexplained × 14d); rollback rehearsed; first real payout settled |
| M3 | 2× V1 load; weekly audit reviews × 2; restore drill post-cutover; contracts v1.1 |
| M4 | + I-12, I-13; V2 load; 24-h soak; competition/scoring re-run; contracts v2 |
| M5 | + I-10, I-11; V3 load; 50-check conformance green; game-day; contracts v3 |

## 9. TDD & review expectations

- **Money paths are TDD:** LED postings, PAY eligibility, EVL
  verdicts, LCC transitions, BRG enforcement — the test lands in
  the same PR as the code, written first where the invariant is
  known (it is: §3).
- **No test, no merge** for: new endpoints (integration test),
  new events (producer + consumer test), new migrations (up/down
  + the schema-check), new adapters (contract suite), new UI
  journeys (Playwright).
- **Flaky tests are P1 bugs:** quarantine with an issue link,
  fix within the sprint. A suite that fails intermittently
  teaches the team to ignore CI — that is how invariants die.

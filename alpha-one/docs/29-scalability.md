# 29 — Scalability

> Cross-cutting document. Every module doc has a §11
> (Scalability considerations); this doc is the **capacity
> model + the scaling paths + the cross-module failure
> map**. Binding sources: docs/00 §5 (the scale targets),
> docs/01 §1 (the 13 Compose services, the single-Hetzner-
> AX42, the ADR-1..12), docs/06 (the DR: the RPO ≤ 5-min,
> the RTO ≤ 2-h, the monthly drill), the 27 Part C.1
> (PLT-01/02/03 — the governance), the 28 (the failure
> modes' security posture).
>
> **The posture (binding, the 01 ADR):** the V1/V2 platform
> is **one Hetzner server + Docker Compose** (the ADR
> posture, the 00 §8 non-negotiable, the 06 §1). "Scalable"
> in V1/V2 means *headroom + clean horizontal seams* —
> the design is such that the V3 scale-out (the 2nd box,
> the read-replica, the multi-region) is a **config +
> infra change, not a rewrite**. The 29 doc's job: make
> that true, and say *exactly* what the numbers are when
> each seam is pulled.

> **v1.1 (2026-09-25) — the V2 capacity target was corrected, and it is
> 10× what this doc said.** Every V2 number in §1.1/§1.3/§6 was sized
> against a **single-tenant** ceiling of 10,000 accounts total. Alpha One
> is a **white-label, multi-tenant** platform: independent prop firms share
> the infrastructure and each can hold 5,000–10,000 active accounts. The
> corrected V2 planning target is **10 tenants × 10,000 accounts = 100,000
> concurrent broker accounts**. §1.1.1 states what kind of number that is
> and what would make it be re-derived. **V1 (431 accounts) is unchanged**
> — this is a V2 planning correction only. The matching recomputation of
> the ingest path (MetaApi subscriptions, sockets, shards, tick rates,
> relay target) is in **docs/63 §4.11**; the two tables must be read
> together and are cross-checked row by row there.
>
> **Two things the correction breaks outright**, both recorded as findings
> in docs/63: the ADR-9 single-box posture (**F12** — ≈ 75 GB of stream-
> gateway RSS at ≈ 50 shards vs a 32–64 GB box; the §3.2 second box moves
> forward from a V3 seam to a **V2 prerequisite**, §3.1) and 13-month
> in-PG retention of `bridge.tick` (**F13** — ≈ 85 B rows ≈ 34 TB; a
> ≤ 7-day hot window + R2 columnar archive replaces it, §1.3). Neither was
> visible at 10k; both are unavoidable at 100k.

## 1. The capacity model (the 00 §5 targets)

### 1.1 The scale targets (docs/00 §5, the binding)

| Metric | V1 (the launch) — **unchanged** | V2 (the growth) — **v1.1 corrected: 10 tenants × 10k** | V3 (the ecosystem) — the linear extrapolation, **not independently sized** (§1.1.2) |
|---|---|---|---|
| Tenants | 1-5 (the FunderBlu first) | **10 (the sizing roster, §1.1.1)** — the 00 §5's 25-50 is the *commercial* ambition; the account count, not the tenant count, is the sizing driver | 25-50 (the quality-over-quantity, the 00 §5) |
| Traders (active identities) | 500 | **100,000** (10 tenants × 10k active users — the white-label roster's per-firm figure) | 250,000-500,000 |
| Funded trader accounts | 250 | **50,000** (the V1 table's 50 % funded share of concurrent accounts, held constant) | 125,000-250,000 |
| Concurrent broker accounts (the 08's sync) | 500 | **100,000** ← *the correction; was 10,000* | 250,000-500,000 |
| Tick rate (sustained) | 20/s (streaming-conflated `bridge.tick`, D79 — ≈ 10/s expected, ≈ 100/s news burst, docs/63 §4.4) | **2,500/s sustained, 10k/s burst** (the D79 envelope at 100k accounts — the per-row derivation is docs/63 §4.4; was 250/s / 1k/s at 10k) | 6,250/s-12,500/s sustained, 25k/s-50k/s burst |
| Event rate (the 04's relay) | 500 msg/s | **10,000 msg/s sustained = 600k events/min** (the `bridge.tick` burst + the other topics; was 2,000 msg/s / 60k events-min) — ⇒ **≥ 10 relay partitions** (the 04 §11's single process is 2k msg/s), docs/63 §4.5 | 25,000-50,000 msg/s |
| `workers` evaluation lanes (the 04 §3.5's per-entity serial lanes) | ≥ 16 | **≥ 128** (≈ 100 ticks/s per lane at the 09 §11's p95 < 10 ms ⇒ 25 sustained / 100 burst / 200 at the §1.2 2× rule; the floor is `10 × tenants` for the D82 per-tenant fairness, docs/63 §4.13). **The 04 §3.5/09 §11 "≥ 16 lanes" is superseded: 16 lanes = 1,600 ticks/s of capacity against ≈ 1,791/s of sustained demand (docs/63 §4.4) — saturated by ordinary traffic, before any burst**) | ≥ 320 |
| EVL verdict rate (the 09's Rust, the ADR-11) | ≈ 10/s | **2,500/s sustained, 10k/s burst** (was "~1k verdict/s", the §1.3's EVL row) | 6,250/s-12,500/s |
| Orders/day (the trader's, the 08) | 1,000 | **50,000** (the 08 §11's ~50 deals/account/day × 100k = 5M *deals*/day; the trader-initiated order subset is the 1 % class) | 125,000-250,000 |
| Payouts/day | 100 | **5,000** (the 50k funded accounts × the 00 §5's 1 % daily payout rate; was 500) | 12,500-25,000 |
| Webhook endpoints (the 04 §5.6) | 5 | **500** (50 per tenant × 10 tenants; the 00 §5's V3 figure, reached at V2 by the roster) | 1,250-2,500 |
| SSE connections (the 01 §4.3) | 50 | **5,000** (the 5 % concurrent-viewer share of 100k traders; was 500) | 12,500-50,000 |
| Users concurrent (the 16's TD + the 17's ADM) | 50 | **5,000** (the 5 % concurrent share; was 500) | 12,500-50,000 |
| MetaApi deployed accounts (the cost driver, the 08 §1) | ≈ 300 | **100,000** ⇒ ≈ **$7.5M/mo** platform-wide at the $75/mo/account class, ≈ **$750k/mo per tenant**, the tenant's cost (the 22 §3.4's pass-through, the §5 below) | $18.75M-$37.5M/mo |

**Read the V2 column as one number and its consequences.** The only
genuinely new input is **100,000 concurrent broker accounts**; every other
V2 row is that number times a per-account ratio this doc or docs/00 §5/08
§11 already documented (the 30 % open-position share, the ~50
deals/account/day, the 50 % funded share, the 5 % concurrent-user share).
Nothing on the ingest or evaluation path is superlinear in account count —
conflation, subscriptions, sockets, shards and MetaApi's credit limits are
all per-account or per-shard. **What is not linear is where a documented
ceiling gets crossed rather than a volume scaled**: the relay's 2k msg/s
single process, the 16-lane `workers` default, the gateway's per-box RSS
(F12) and the `events` log's 13-month PG retention (F13). Those four are
the work the corrected number creates, and they are sized in §1.3, §3.1,
§3.4 and docs/63 §4.11.2.

#### 1.1.1 What kind of number 100,000 is (and what re-derives it)

**100,000 is a planning estimate, not a hard ceiling, and not a
contractual commitment.** It is 10 tenants × 10,000 accounts because that
is the shape of the white-label roster — each independent firm holding
5,000–10,000 active accounts — and because no firmer commercial roster
exists to plan against at this date. It is **deliberately conservative
against docs/00 §5**, whose V2 tenant range is 25–50: at the same
per-tenant account count that implies 250k–500k accounts. The arithmetic
here is linear in accounts, so re-deriving at a different roster is a
multiplication — except for the four ceiling crossings above, which are
what a re-derivation must re-examine rather than rescale.

**Re-derive these numbers (here and in docs/63 §4.11) before any of:**

1. **Onboarding tenant #15.** 15 × 10k = 150k is 1.5× this target and
   pushes the relay partition count, the lane floor (`10 × tenants` = 150)
   and the F12 box arithmetic past the headroom they are stated with.
2. **Any single tenant exceeding 10,000 concurrently deployed accounts.**
   Per-tenant shards are sized at 5 (§4.2 of docs/63); a 25k-account
   tenant needs 13 shards and its own blast-radius review, and the D82
   lane-weight floor stops being that tenant's own burst point.
3. **The signed roster exceeding 10 tenants**, or any commercial
   commitment that names an account count — that number then replaces the
   estimate here, and this subsection records the replacement.
4. **MetaApi changing the 300-accounts/user/server cap, the
   `10 × deployed` subscription quota, or the 18k credits/min per-server
   limit.** All three are provider policy, not ours, and all three are
   load-bearing in docs/63 §4.11.
5. **Spike Q3/Q7 (docs/63 §8) returning a measured RSS-per-account** that
   differs materially from the 1.5 GB/shard alarm threshold — F12's shard
   count and second-box requirement follow from it.
6. **The §6 load test returning measured throughput** that contradicts any
   planning estimate below. Until it runs, every PG/Redis figure in §1.3
   and §3.4 is an estimate derived from documented per-unit limits, not a
   measurement.

#### 1.1.2 V3 is an extrapolation, not a sizing

The V3 column is the same per-account model at docs/00 §5's 25–50
tenants. It is **not** independently sized in this pass and must not be
quoted as though it were: V3's real distinguishing features (the
multi-region trigger, the read-replica, the ML sidecar, the public API's
5k rps) are unchanged in kind, and V3 planning re-derives the numbers
under §1.1.1's trigger 1 *a fortiori*. The old V3 column said
"250/s — the V3 is the breadth, not the tick-rate", which is now
incoherent (it was below the corrected V2 figure); it is restated
linearly here rather than left contradictory.

### 1.2 The headroom rule (the 29 doc's binding)

**The capacity is 2× the V-target at all times** (the
measured, the 06 §3.4's Prometheus, the 27 Part C.1's
PLT-02's quarterly review): the V1 box (the 06 §1's
AX42-class, the ~8-16 vCPU / 32-64 GB / the NVMe) is
sized for **the V2 numbers**, the V2's 2nd-box decision
(PLT-02, the 27 Part C.1) is triggered at the **V2
numbers' 70% sustained for 2 weeks** (the 27 Part C.1's
PLT-02, the CON-adjacent, the 21 §3.4), the V3's
multi-region (the PLT-01, the 27 Part C.1) is triggered
by the **RTO breach (the 06 §3.2's drill, the 2× miss)
or the data-residency need (the 28 §10, the PK's call)**
— never by the raw load first (the 29 doc's posture:
the scale-out is for the RTO/residency, the V3 load
fits the 2-box, the §3 below).

**v1.1 — the headroom rule survives the correction; the "V1 box is sized
for the V2 numbers" clause does not.** The 2× rule is unchanged and still
binding. But at the corrected V2 target the AX42-class V1 box is *not*
sized for the V2 numbers: the stream-gateway tier alone needs ≈ 75 GB of
RSS at ≈ 50 shards against a 32–64 GB box (docs/63 F12, §3.1 below), and
the evaluation write path peaks at ≈ 20k PG q/s against a primary planned
at ≈ 10k (§3.4). So the 2nd box is no longer a decision that is
*triggered* at "the V2 numbers' 70 % sustained for 2 weeks" — at the
corrected target it is a **V2 entry prerequisite**, and PLT-02's quarterly
review now governs the *third* box, not the second. The 70 %-for-2-weeks
trigger is retained unchanged for every seam that is still a seam.

### 1.3 The per-resource model (the V2 peak, the 2× rule)

| Resource | V2 peak at **100k accounts** (v1.1 corrected) | The 2× headroom | The V3 (the linear extrapolation, §1.1.2) |
|---|---|---|---|
| **PG CPU** (the writes: the tick/deal sync, the LED, the AUD, **the evaluation path**) | **≈ 100 % of a 16-vCPU primary, and that is the binding constraint.** The evaluation path is 1 read + 1 write per tick (the 09 §3.2's single-writer-per-account) = **≈ 5k q/s sustained, ≈ 20k q/s burst**; plus the group-commit rows (≈ 4.3k rows/s sustained, ≈ 11.8k burst — the 08's snapshots at 1,667/s + the deals at 58/s + the outbox at the tick rate) and the `events` insert at the tick rate. *Was: "the ~60 % of a 8-vCPU".* | the 2×-rule target of ≈ 40k q/s burst is **not reachable on one primary** — §3.4 sizes the answer (the partitioning + the replica + the staged horizontal option) | the 2-box minimum, the horizontal option exercised (§3.4) |
| **PG IOPS** (the NVMe) | **≈ 15k-20k IOPS sustained at the ≈ 5k q/s evaluation path** (the 06 §1's NVMe, the ~50k capable — so IOPS is *not* the binding constraint; CPU and commit latency are) | the 30k-class | the 40k-class (the 2-box) |
| **PG storage** | **≈ 1.3 TB rolling, not "≈ 200 GB/yr".** At 100k accounts, with the per-row basis stated so the sum is checkable: `account_snapshots` ≈ 144M rows/day × the 14-day rolling window ≈ **2.0 B rows ≈ 400 GB** (≈ 180 B/row heap + PK index); `broker_deals` ≈ 5M/day × the 90-day hot window ≈ **450M rows ≈ 150 GB** (≈ 330 B/row); `bridge.tick` in `events` at the **≤ 7-day hot window F13 forces** ≈ 1.5 B rows ≈ **605 GB** (≈ 400 B/row); the LED/AUD 7-yr and the 19 §3.1 read model ≈ 150 GB. **Sum ≈ 1,305 GB ≈ 1.3 TB.** *The old row's "the tick's 13-mo" is deleted: 13 months (≈ 395 days) of `bridge.tick` at 2,500/s is ≈ 85 B rows ≈ 34 TB (docs/63 F13) — ≈ 3 TB/yr goes to the R2 columnar archive instead.* | **the 1 TB disk is insufficient at ≈ 1.3 TB rolling — 2 TB minimum on the primary, and the R2 archive (≈ 3 TB/yr, ≈ $45/mo at the 22 §3.1's class) is the tick's long tail** | the 4 TB-class + the R2-archive |
| **Redis memory** | **≈ 6 GB across the three containers, and the `redis-streams` share is the one that moves.** D51's 2/2/4 split (redis-main / redis-streams / redis-cache) does not survive: **10 per-tenant `bridge` streams × `MAXLEN ~100000` × ≈ 1 KB ≈ 1 GB** (the D82 sharding, docs/63 §4.13) — inside 2 GB at 10 tenants but **≈ 5 GB at the 00 §5's 50 tenants**, so the split becomes **2/6/4** and the box needs the 12 GB-class. The session/deny-set/SSE/rate-limit ≈ 4 GB is unchanged in kind (the 01 §4.3's SSE at 5,000 connections, the 02's hot-set). | the 8/12-class; **`MAXLEN` stays at ~100000 — raising it to ~1M would need ≈ 10 GB at 10 tenants and Redis is never the source of truth (the 00 §8 #1). The trim hazard is handled by detection + replay + shedding, not by memory** (docs/63 §4.13) | the same model, the 50-stream case |
| **The 08's MetaApi ingest budget** (D78, docs/63 F1/§4.11) | streaming: **100k accounts ≈ 200k subscriptions** (high reliability; the quota = 10 × deployed = 1M ⇒ 5× headroom), **≈ 2,000 sockets**, **≈ 50 `bridge-stream` shards** (5 per tenant — the shard hash is `(tenant_id, account_id)`, docs/63 §4.2), **≥ 334 `client-id` slots** (the ≤ 300 accounts/user/server cap ⇒ **≥ 28 MetaApi user accounts**, or ≥ 3 per tenant under per-tenant credentials), **0 CPU credits** steady-state; REST only for the fallback/D33/reconciler under the per-`client-id` credit budget. The superseded poll-everything plan would need **≈ 17.6M credits/min vs ≈ 216k/min for all MetaApi servers — ≈ 81× over** (the 10k figure was ≈ 8×; the correction strengthens D78 rather than changing it). **≈ 75 GB of shard RSS at the 1.5 GB/shard alarm threshold ⇒ F12: this tier does not fit the box.** | **the 2nd box is a V2 prerequisite, hosting `bridge-stream` first** (§3.1) — the stateless, restart-resync, cheapest tier to move; ≈ 50 shards across 2 boxes ≈ 38 GB each | the same model, more shards + more bridge instances (the accounts sharded; the hot state rebuildable) |
| **The relay** (the 04 §5.4, the single-process, the advisory-lock) | **the 10k msg/s = 600k events/min target no longer fits one process.** The 04 §11's documented single-process capacity is 2k msg/s ⇒ **≥ 5 partitions at the target, ≥ 10 at the 2× rule**, partitioned by `(topic, tenant-shard)` with a per-partition advisory lock — the 04 §11/§3.2 horizontal seam pulled into V2. Redis itself is not the limit (≈ 10 MB/s of pipelined `XADD` at 10k/s × ≈ 1 KB) | the 20k msg/s-class = the ≥ 10 partitions | the 50k msg/s-class (the webhook fan-out, the Hook0's egress + the 2nd relay) |
| **The GW** (the Go, the 04 §3) | **the ~20k rps** (the corrected §1.1's 5,000 concurrent users + the public-API read; was "~2k rps") ⇒ **≥ 10 GW instances at the 2k rps/instance figure, i.e. the GW stops being a 2-instance seam at V2** | the 40k rps-class | the 50k-100k rps (the public-API, the 27 Part A §11) |
| **The EVL** (the Rust, the ADR-11, the 09 §1, **the D81 stateless compute tier**) | **the 2,500 verdict/s sustained, the 10k verdict/s burst** (was "~1k verdict/s"). CPU is *not* the constraint: `propfirm-engine`'s own `benches/engine.rs` measures ≈ **52,600 pure evals/s single-threaded** (≈ 205k/s batched), so one replica covers the sustained target ≈ 20× over on math alone. The binding constraints are the HTTP fan-in and the PG state read/write, both of which live in `workers` after D81 — **which is exactly why D81 matters: a stateless engine scales by adding replicas, a stateful one does not** | the 5k/20k-class — **≈ 2-4 engine replicas for the sustained math, sized by HTTP/PG rather than CPU; the `workers` lane count (≥ 128) is the real throughput dial** | the same (the stateless, the N-EVL) |
| **`workers`** (the Go consumer supervisor, the 04 §3.5, **new row — the D81/D82 owner of the evaluation path**) | **≥ 128 lanes** at ≈ 100 ticks/s per lane (the 09 §11's p95 < 10 ms per tick: the PG read ~1 ms + the engine HTTP ~2 ms + the PG write ~1 ms) ⇒ 25 lanes sustained / 100 burst / 200 at the 2× rule; the floor is **`10 × tenants`** so each tenant's lane set covers its own burst (the D82 fairness, docs/63 §4.13). **The 04 §3.5/09 §11 "≥ 16 lanes" is corrected: 16 lanes provide 1,600 ticks/s of capacity against ≈ 1,791/s of *sustained* demand (docs/63 §4.4) — the fleet saturates on ordinary traffic, before any burst — and put 6,250 accounts per lane, so a single slow tenant head-of-line-blocks 6,250 accounts' worth of neighbours** | the 256-lane-class | the ≥ 320 lanes |
| **The MetaApi cost** (the 08 §1, the $75/mo/account-class) | **the 100k × the $75 = the $7.5M/mo-class** platform-wide; **≈ $750k/mo per tenant at 10k accounts** (the 22 §3.4's pass-through, the 27 Part C.1's PLT-03, the tenant's cost). **This is the dominant commercial fact of the corrected target and it is also a natural governor: the account count is cost-gated per tenant, so the 100k platform figure is a *capacity* target, not a forecast** | — | the $18.75M-$37.5M/mo-class (the cost is the tenant's) |

**All PG/Redis/GW throughput figures above are planning estimates, not
measurements.** They are derived from documented per-unit limits — MetaApi's
published quotas, the 09 §11's per-tick latency budget, the 04 §11's relay
figure, `propfirm-engine`'s own benchmark — and from the per-account ratios
in §1.1. There is no load-test data at 100k accounts. The §6 load test
replaces them with measured numbers; §1.1.1's trigger 6 makes that a
binding re-derivation, not a nicety.

**The read (v1.1 — a V2 requirement, not the V3's read-scale):** the V2's
read-heavy (the 16's TD, the 19's read model, the 27 Part A's public-API)
can no longer share the primary with the evaluation write path. At the
corrected target the primary is at ≈ 5k q/s sustained from evaluation
alone (§1.3), and the 19's read model + the 17's ADM screens + the 18's
dispute replay + the ANA-14 `as_of` reads are all *scans over the same
tables the hot path writes* (`account_snapshots` at 2.0 B rows,
`broker_deals` at 450 M rows). **So: the 2nd-box read-replica moves into
V2 with the 2nd box (§3.1, §3.4), and the rule is explicit — nothing
outside the evaluation write path reads the primary.** The read path is
the `*_ro` role (the 19 §3.1, the 19 §9) served from the replica; the
19's read model is read-replica-friendly (the 19 §2's rebuildable); the
no-stale-tolerance cases (the ANA-14, the 24 Part B's posture) carry the
`as_of` so replica lag is disclosed rather than hidden. Dispute replay
older than the F13 hot window reads the R2 archive, not PG at all.

## 2. The per-module scaling surface (the aggregation
of the 26 module docs' §11 — the one-page map)

| Module | The surface (the §11's class) | The V1/V2 design | The V3 seam (the pull) |
|---|---|---|---|
| **AUTH (02)** | The session (the PG + the Redis's deny-set), the MFA (the TOTP, the no-ext), the anomaly (the 02 §3.6's in-proc) | The in-proc (the GW's), the Redis's hot (the 02 §3.5) | The no-seam (the AUTH scales with the GW, the 02 §11) |
| **TEN (03)** | The tenant-config (the PG, the cache (the 03 §3.1's Redis), the 9-step saga (the 03 §3.1)) | The PG + the Redis-cache (the 03 §11) | The no-seam (the tenant is the 50, the 00 §5, the config-cache covers) |
| **GW+EVT (04)** | The chain (the 04 §3), the relay (the 04 §5.4 — **v1.1: no longer single-process; ≥ 10 partitions by `(topic, tenant-shard)`, the 04 §11's 2k msg/s limit is crossed at the corrected target**), the **per-tenant `bridge` streams (the D82, docs/63 §4.13)**, the egress (the Hook0, the 04 §5.6), the SSE (the 01 §4.3) | **The ≥ 10 relay partitions and the per-tenant stream sharding are V2, not V3** (the §1.3); the Hook0 (the 01 §1's service), the SSE-relay (the 01 §4.3, the 16 §11's pattern) | The 2-relay (the 04 §11's horizontal: the advisory-lock's partition (the per-tenant-lock (the 04 §5.4's class), the 2-instance (the §3)), the Hook0's 2-instance (the 01 §1's compose scale, the stateless (the 04 §5.6)), the SSE's 2-instance (the 01 §4.3, the Redis-pub/sub (the 01 §4.3's posture)), the GW's 2-instance (the stateless, the 04 §11) |
| **LED+AUD (05)** | The entries (the PG, the partition (the 05 §9, the monthly), the 7-yr), the audit (the append-only, the 05 §9), the snapshot (the R2, the 05 §3.5) | The single-PG (the 05 §11), the nightly-snapshot (the R2, the 05 §3.5) | The 7-yr-archive (the 13-mo → the R2 (the 04 §5.4's class), the 06 §3.2's archival, the 22 §3.1's cost, the 27 Part C.1's PLT-03), the read-replica (the §3, the 05's read (the 27 Part A's SDK-12 export (the 27 Part A §3.3), the read-replica)) |
| **OPS (06)** | The infra (the single-box, the 06 §1), the DR (the 06 §3.2, the RPO/RTO), the observability (the 06 §3.4) | The single-AX42 + the warm standby (D56, docs/57), pgBackRest (D55, docs/57), the Grafana (the 01 §2) | The 2-box (the §3, the PLT-02 (the 27 Part C.1)), the multi-region (the PLT-01 (the 27 Part C.1), the 28 §10's residency, the RTO-trigger (the 06 §3.2's 2× miss)), the Loki/OTel (the V2, the 01 §2's "consider", the 06 §3.4's upgrade) |
| **LCC (07)** | The state-machine (the single `Transition()`, the 07 §3.1), the saga (the 9-step, the 03 §3.1's class) | The in-proc (the Go, the 07 §11) | The no-seam (the LCC is the command-path, the PG-serial (the 07 §3.1's single-write, the no-HA (the 07 §11's posture: the LCC's throughput is the 10/s-class (the 00 §5's account-change), the PG covers)) |
| **BRG (08)** | The **streaming ingest (the D78 — the poll-stagger is retired as a scaling lever; REST is a credit-budgeted fallback only, docs/63 §4.7)**, the sync (the tick/deal, the 08 §9's partition **+ the v1.1 `(tenant_id, day)` partitioning, the §3.4.2**), the command (the 08 §3.3's executor), **the ≈ 50 `bridge-stream` shards (5 per tenant) at ≈ 75 GB RSS ⇒ the F12 box breach** | **The 2nd box is a V2 prerequisite and takes `bridge-stream` first** (the §3.1); ≥ 2 bridge instances partitioned per tenant (the 08 §11's horizontal seam, pulled forward); the credit-budget per tenant (the §4.7's Reading A/B, docs/63 Q8) | The 2-bridge (the 08 §11's horizontal: the per-tenant-partition (the 08 §3.2's stagger's class), the 2-instance (the §3), the MetaApi's rate (the 08 §1's provider-limit, the 27 Part B's copy-order (the 27 Part B §11))), the tick-archive (the 13-mo → the R2 (the 04 §5.4, the 06 §3.2), the TRD-04's backtest (the 27 Part B §3.2, the 29's V3 compute)) |
| **EVL (09)** | The verdict (**the Rust stateless compute tier, the ADR-11 re-confirmed by the D81** — `evaluate(state, rules, tick) → (verdict, new_state, hints)`, no DB of its own), the rulepack (the versioned, the 09 §3.1, **validation in the engine, storage/lifecycle where ADM persists them**), **the state ownership + the ordering + the idempotency + the retry/DLQ = `workers` (the D81, the 04 §3.5's consumer-supervisor pattern — the same mechanism NOT/LED/AUD use)**, the floor hints (the 09 §3.8) | **The ≥ 128 `workers` lanes with per-tenant lane sets (the D82, the docs/63 §4.13's floor of `10 × tenants`), the ≥ 2-4 engine replicas sized by the HTTP/PG rather than the CPU (the §1.3's EVL row: ≈ 52,600 pure evals/s single-threaded vs a 10k verdict/s target), the D84 lag-in-seconds autoscaling signal + the conflation-widening shed ladder** | The 2-EVL (the 09 §11's horizontal: the stateless (the ADR-11 (the 01 §3), the 09 §1), the 2-instance (the §3)), the backtest (the historical-mode (the 27 Part B §3.2, the `--historical` flag, the 29's V3 compute, the off-peak (the 06 §3.3's advisory-lock)) |
| **RSK (10)** | The detector (the 10 §3.3, the in-proc + the PG), the case (the 10 §3.1), the V3-ML (the sidecar, the 10 §12) | The in-proc (the Go, the 10 §11), the PG (the detector's state) | The ML-sidecar (the 10 §12, the Python, the no-network (the 28 §2.2 T5), the off-peak (the 06 §3.3), the 29's V3 compute), the no-seam-on-the-detector (the 10 §11: the detector is the 100/s-class (the event-rate, the 00 §5), the PG covers) |
| **PAY (11)** | The calc (the frozen-snapshot, the 11 §3.2), the approval (the manual, the 00 §6), the execution (the NOWPayments, the 11 §3.4) | The in-proc (the Go, the 11 §11), the provider-call (the 11 §3.4, the async) | The no-seam (the payout is the 500/day (the 00 §5), the 21/min-class, the provider's rate (the 11 §12, the NOWPayments's limit, the 11 §11's queue (the 06 §3.3's advisory-lock, the 11 §3.4's execution-queue))) |
| **CHK (12)** | The checkout (the 12 §3.2, the session), the capture (the 12 §3.2, the rail), the refund (the 12 §3.3, the machine) | The in-proc (the Go, the 12 §11), the provider-call (the 12 §1, the async) | The no-seam (the checkout is the 10/s-class (the 00 §5's purchase), the rail's rate (the 12 §12, the Match2Pay/Interkasa/NOWPayments's limit, the 12 §11's queue)) |
| **KYC (13)** | The Veriff (the 13 §12, the provider), the document (the R2, the 13 §3.4) | The in-proc (the Go, the 13 §11), the provider-call (the 13 §12, the async) | The no-seam (the KYC is the 10/day-class (the 00 §5), the Veriff's rate (the 13 §12, the provider's limit, the 13 §11's queue)) |
| **NOT (14)** | The channel (the 14 §3.1, the email/push/in-app), the dedupe (the 14 §3.5, the SETNX 24-h), the Postmark (the 14 §12) | The in-proc (the Go, the 14 §11), the queue (the 14 §3.4, the Redis's (the 01 §2's BullMQ-class (the 01 §2), the 14 §12)), the Postmark (the 14 §12, the rate (the Postmark's 0.5/s-class (the 14 §12), the 14 §11's queue)) | The 2-NOT (the 14 §11's horizontal: the stateless (the 14 §3.1's adapter, the 14 §11), the 2-instance (the §3)), the push (the FCM/APNs (the 26 Part A §3.3, the provider's rate, the 26 Part A §11)) |
| **DOC (15)** | The PDF (the Puppeteer, the Node-22, the 15 §12), the mapper (the frozen-snapshot, the 15 §3.1) | The single-worker (the Node, the 15 §11), the queue (the 15 §3.2, the BullMQ-class (the 01 §2)) | The 2-worker (the 15 §11's horizontal: the stateless (the 15 §3.1's snapshot-in, the PDF-out, the 15 §11), the 2-instance (the §3), the Puppeteer's memory (the 15 §11's class, the 256 MB/PDF (the 15 §12), the 06 §3.1's container-limit (the 06 §3.1))) |
| **TD (16)** | The web (the Next.js, the 01 §2), the SSE (the 01 §4.3), the chart (the TradingView, the 16 §12) | The single-node (the Next, the 16 §11), the ISR/SSG (the 16 §3.1's class, the 01 §2), the SSE-relay (the 01 §4.3, the 16 §11) | The 2-node (the 16 §11's horizontal: the stateless (the Next, the 01 §2), the 2-instance (the §3)), the CDN (the Cloudflare (the 01 §2, the 06 §1), the static (the 01 §2's build, the 28 §3.1's origin)) |
| **ADM (17)** | The web (the Next, the 01 §2), the queue (the 17 §3.1) | The single-node (the 17 §11, the 16 §11's class) | The 2-node (the 17 §11, the 16 §11's seam, the §3) |
| **SUP (18)** | The ticket (the 18 §3.1, the PG), the SLA (the 18 §3.3) | The in-proc (the Go, the 18 §11) | The no-seam (the ticket is the 20/day-class (the 00 §5's V2), the PG covers) |
| **ANA (19)** | The read-model (the 19 §3.1, the `_ro`, the rebuildable (the 19 §2)), the report (the 19 §3.3, the async, the R2) | The in-proc (the Go, the 19 §11), the nightly-rebuild (the 19 §3.4, the 06 §3.3's off-peak) | The read-replica (the 19 §11's horizontal: the `_ro` read (the 19 §3.1), the read-replica (the §3, the 19 §11's posture)), the BigQuery-dump (the V3, the 19 §3.5, the 00 §7's consider-later, the 29's V3 line, the off-peak (the 06 §3.3)), the report-queue (the 19 §3.3, the 2-worker (the §3, the 19 §11)) |
| **CRM (20)** | The segment (the 20 §3.1, the computed, the `*_ro`-only (the 20 §1)), the sync (the 20 §3.2, the BYO, the 27 Part A's SDK-13) | The in-proc (the Go, the 20 §11), the nightly-segment (the 20 §3.1, the 06 §3.3's off-peak) | The no-seam (the segment is the nightly (the 20 §3.1), the 5k-trader (the 00 §5's V2) = the seconds (the 20 §11), the PG covers) |
| **CON (21)** | The web (the Next, the 01 §2), the control (the 21 §3.2, the in-proc) | The single-node (the 21 §11, the 16 §11's class) | The 2-node (the 21 §11, the 16 §11's seam, the §3) |
| **BIL (22)** | The meter (the 22 §3.1, the in-proc), the invoice (the 22 §3.5, the monthly), the Lago (the V3, the 22 §3.1) | The in-proc (the Go, the 22 §11) | The Lago (the V3, the 22 §3.1, the self-hosted (the 00 §7's V3-class, the 22 §12), the 1-instance (the §3, the Lago's stateless (the 22 §11)), the meter (the 22 §3.1, the PG, the no-seam (the 22 §11))) |
| **AFF (23)** | The attribution (the 23 §3.1, the last-touch, the in-proc), the reversal (the 23 §3.2) | The in-proc (the Go, the 23 §11) | The no-seam (the attribution is the 1/s-class (the 00 §5's conversion), the PG covers) |
| **CMS+CMP (24)** | The CMS (the block, the 24 Part A, the PG + the Next-renderer), the CMP (the scoring, the 24 Part B, the pure, the re-runnable (the 24 Part B §3.3)), the video (the R2, the 24 Part A §3.5) | The in-proc (the Go, the 24 §11), the Next-renderer (the 24 Part A, the 16 §11's class), the scoring (the 24 Part B, the in-proc (the 24 Part B §11), the re-runnable (the 24 Part B §3.3)) | The 2-node (the 24 Part A's renderer, the 16 §11's seam, the §3), the R2 (the video, the 24 Part A §3.5, the CDN (the Cloudflare (the 01 §2), the 24 Part A §11), the no-seam (the R2 is the ext (the 24 Part A §11))), the scoring (the no-seam (the 24 Part B §11: the scoring is the 1/s-class (the 00 §5), the PG covers), the re-run (the 24 Part B §3.3, the off-peak (the 06 §3.3))) |
| **MIG (25)** | The pipeline (the 25 §3.1, the 7-step, the one-shot, the 25 §11) | The one-shot (the 25 §11: the migration is the V1's launch-event, the no-scale (the 25 §11's posture), the 14-day-parallel (the 25 §3.6), the 30-day-rollback (the 25 §3.7)) | The no-seam (the MIG is the done (the 25 §16), the future-tenant's onboarding (the 03 §3.1's saga, the 03 §11's class)) |
| **MOB+JRN+EDU+CHT (26)** | The MOB (the RN, the thin-client, the 26 Part A), the JRN (the annotation, the 26 Part C, the PG), the EDU (the video, the R2, the 26 Part D), the CHT (the chat, the SSE, the 26 Part E) | The thin-client (the 26 §11: the MOB is the no-new-backend (the 26 Part A §1), the JRN is the PG (the 26 Part C §11), the EDU is the R2 (the 26 Part D §11), the CHT is the SSE (the 26 Part E §11, the 01 §4.3's class)) | The SSE (the CHT, the 01 §4.3's relay, the 16 §11's seam, the §3), the R2 (the EDU-video, the 24 Part A §11's class, the CDN), the no-new-seam (the 26 §11's posture: the V2+ is the thin-client, the scale is the existing-domain's scale (the 26 §11)) |
| **SDK+DVP+TRD+PLT+CS (27)** | The public-API (the 27 Part A §11, the GW's subset), the webhook (the Hook0, the 27 Part A §11), the portal (the `web/dvp`, the 27 Part A §11), the TRD (the copy (the 27 Part B §11), the backtest (the 27 Part B §11), the paper (the 27 Part B §11)), the PLT (the governance, the 27 Part C.1), the CS (the score, the 27 Part C.2) | The V3 (the 27 §11: the public-API is the GW's subset (the 27 Part A §11), the webhook is the Hook0's (the 27 Part A §11), the portal is the 16 §11's class, the TRD is the 08/09's class (the 27 Part B §11), the PLT/CS is the governance (the 27 Part C)) | The 2-GW/2-Hook0/2-relay (the §3, the 27 Part A §11), the copy-order (the 27 Part B §11, the 08's poll-budget (the 08 §3.2)), the backtest-compute (the 27 Part B §11, the 29's V3 line, the off-peak), the paper-simulation (the 27 Part B §11, the 29's V3 line, the off-peak) |

## 3. The scaling paths (the seams, the pull-order)

### 3.1 The V1 → V2 (**v1.1: the headroom is gone — the 2nd box is a V2 prerequisite**)

> **v1.1 — this section's premise is withdrawn.** It said the V1 box is
> sized for the V2 and that the V2's load fits the V1 box. That was true
> against a 10,000-account V2. Against the corrected **100,000-account**
> V2 it is false, and it is false for two independent reasons that do not
> trade off against each other:
>
> 1. **Memory (docs/63 F12).** ≈ 50 `bridge-stream` shards at the §4.2
>    alarm threshold of 1.5 GB RSS each ≈ **75 GB**, against a 32–64 GB
>    AX42-class box, *before* Postgres (which wants ≈ 25 % of RAM for
>    `shared_buffers` + work_mem at the §1.3 q/s figure), Redis at the
>    corrected 2/6/4 split, the Go bridge (× ≥ 2 instances), `api`, the
>    ≥ 10 relay partitions, `workers` at ≥ 128 lanes, ZITADEL, Hook0,
>    Flipt and the two Next.js surfaces are counted.
> 2. **Write path (§3.4).** ≈ 20k PG q/s at burst against a single primary
>    planned at ≈ 10k, with the burst-drain arithmetic landing **exactly
>    on** the 09 §6 `evl.tick_stale` cliff and therefore with zero margin.
>
> **The V2 entry configuration is therefore two boxes**, and the pull
> order is: **box 2 takes `bridge-stream` first** (stateless, holds no
> durability by design — docs/63 §4.2 — restart-resyncs from the PG
> cursor, and the cheapest tier to move), **then the read replica** (§3.4),
> **then the relay partitions and `workers`**. Box 1 keeps the PG primary,
> Redis, `api`, the GW and the Next surfaces. PLT-02's "70 % sustained for
> 2 weeks" trigger is retained for the *third* box.

The V1→V2's "scaling" is then:
the config (the rate-limit (the 04 §3.4, the 27's
SDK-14), the container-limit (the 06 §3.1), the
partition (the 08 §9 / the 05 §9's monthly, the 32
doc's partitioning, **and the new `tenant_id`
partitioning of the evaluation tables, §3.4**), the
lane count (the 04 §3.5's ≥ 16 → ≥ 128, §1.3), the
relay partitions (the 04 §5.4's single process → ≥ 10,
§1.3), the per-tenant stream sharding (the D82,
docs/63 §4.13)), **plus the 2nd box** — the "no-new-box"
clause of the 01 ADR-9 posture is **withdrawn at V2**
(ADR-9 still governs V1, and still forbids Kubernetes;
what changes is that "single box" is no longer true of
V2). The poll-stagger (the 08 §3.2) is retired as a
scaling lever: under D78 there is no steady-state poll
to stagger (docs/63 §4.7 keeps REST as a credit-budgeted
fallback only).

### 3.2 The V2 → V3 (the 2nd box, the read-replica,
the horizontal)

The 2nd-box (the 06 §1's class, the Hetzner, the
01 §1's ADR posture) is the **V3's scale-out** (the
27 Part C.1's PLT-02, the CON-adjacent, the 21 §3.4):
the pull-order (the 29 doc's binding, the cost-ordered
(the 27 Part C.1's PLT-03, the 22 §3.4)):

1. **The read-replica** (the PG's, the 06 §3.3's
   failover-strategy extended, the 27 Part C.1's
   PLT-01's class): the 2nd box hosts the replica,
   the `_ro` read (the 19 §3.1) + the public-API's
   read (the 27 Part A §11) + the report (the 19
   §3.3) hit the replica, the write stays the
   primary (the 05's class, the no-write-replica
   (the 06 §3.3's posture)), the lag (the 06 §3.4's
   metric, the ANA-14's `as_of` (the 19 §2) — the
   replica-read carries the `as_of` (the §1.3's
   read, the 24 Part B's honesty)), the failover
   (the 06 §3.3, the replica → the primary (the
   RTO-improvement (the 06 §3.2's RTO ≤ 2-h →
   the minutes (the 27 Part C.1's PLT-01's
   trigger, the 06 §3.2's drill-verified))).
2. **The stateless horizontal** (the Go/Rust,
   the 01 §2, the 04/08/09/14/15/19 §11's
   posture): the GW (the 04 §11, the 2-instance),
   the relay (the 04 §5.4, the 2-instance,
   the per-tenant advisory-lock (the 04 §5.4's
   class)), the bridge (the 08 §11, the 2-instance,
   the per-tenant partition (the 08 §3.2)),
   the EVL (the 09 §11, the 2-instance,
   the stateless (the ADR-11 (the 01 §3))),
   the NOT (the 14 §11, the 2-instance),
   the DOC (the 15 §11, the 2-worker),
   the report (the 19 §11, the 2-worker),
   the Next (the 16/17/21/24 Part A §11,
   the 2-node) — the load-balancer = the
   Cloudflare (the 01 §2, the 06 §1, the
   origin-pool (the 06's config, the 28
   §3.1's origin-auth)), the state = the PG
   + the Redis (the 01 §2, the no-local-
   state (the 04 §11's discipline:
   the session (the PG (the 02 §3.5) +
   the Redis (the 02 §3.5)), the cache
   (the Redis (the 03 §3.1's class)),
   the queue (the Redis's (the 01 §2's
   BullMQ-class (the 01 §2), the 14/15's
   queue), the no-in-proc-queue (the
   04 §5.7's at-least-once, the 01
   ADR))).
3. **The Hook0** (the 04 §5.6, the 01 §1's
   service): the 2-instance (the 04 §5.6's
   posture, the stateless (the 04 §5.6)),
   the egress-fan-out (the 27 Part A §11's
   500-endpoint, the Hook0's sized-for
   (the 04 §11)).
4. **The V3-late compute** (the 29 doc's
   budget, the 06 §3.3's off-peak):
   the backtest (the 27 Part B §11,
   the 09's historical (the 27 Part B
   §3.2), the off-peak (the 06 §3.3's
   advisory-lock)), the paper (the 27
   Part B §11, the simulation (the 27
   Part B §3.3), the off-peak), the
   ML (the 10 §12, the sidecar (the
   28 §2.2 T5), the off-peak), the
   BigQuery-dump (the 19 §3.5, the
   off-peak, the 00 §7's consider-
   later), the R2-archive (the 04 §5.4's
   13-mo → the R2 (the 06 §3.2's
   archival, the 22 §3.1's cost)) —
   the off-peak = the no-peak-impact
   (the 06 §3.3's class, the 27 Part
   C.1's PLT-02's review (the 27
   Part C.1 §2)).

### 3.3 The V3-late → the multi-region (the
PLT-01, the 27 Part C.1)

The multi-region is **never the load-trigger**
(the §1.2, the 29 doc's posture): the trigger
is the **RTO (the 06 §3.2's drill, the 2× miss
(the 27 Part C.1's PLT-01)) or the data-
residency (the 28 §10, the PK's call (the
00 §3), the EU's (the 28 §10's GDPR-
class))** (the 27 Part C.1's PLT-01,
the CON-32's two-op (the 21 §3.5),
the board-adjacent (the 21 §3.2),
the 7-yr audit (the 21 §3.4)):
the design (the 27 Part C.1's PLT-01,
the 29 doc's binding): the 2nd region
= the 2nd box (the §3.2's class) +
the PG's logical-replication (the
06 §3.3's extended, the 27 Part C.1's
PLT-01) + the Redis's replication (the
06 §3.2's AOF's cross-region (the 27
Part C.1's PLT-01)) + the MetaApi's
geo (the 08 §1's broker-geo (the
ADR-12 (the 01 §3), the 09 §3.2's
trading-calendar — the trading stays
the broker's (the 27 Part C.1's
PLT-01, the 29 doc's posture:
the region is the API's, the broker
is the broker's)), the failover (
the region-failover (the RTO →
the minutes (the 06 §3.2's RTO ≤
2-h → the 06 §3.2's DR-improvement),
the 06 §3.3's runbook (the 06 §3.3,
the 27 Part C.1's PLT-05's game-day
(the 27 Part C.1 §2), the cross-
region (the 06 §3.3's drill (the
06 §3.2's monthly, the 27 Part
C.1's PLT-05's quarterly (the
27 Part C.1 §2)))).

### 3.4 Postgres write scaling for the evaluation path (v1.1, D83)

The corrected target makes the evaluation write path the platform's
largest single writer, so it gets its own sizing rather than a row in
§1.3. **The question this section answers: is single-primary-with-
partitioning sufficient at 100,000 accounts, or does the plan need a
horizontal Postgres?**

#### 3.4.1 The arithmetic

Write volume at the corrected target, per second:

| Writer | Sustained | Burst | Note |
|---|---|---|---|
| `evaluation_state` UPDATE (1 per evaluated tick, the 09 §3.2's single writer) | 2,500 | 10,000 | the hot path; one row per account, 100k rows total |
| `evaluation_state` SELECT (1 per tick, the lane's state read) | 2,500 | 10,000 | index-only on the PK; cheap, but it is a round trip |
| `account_snapshots` upsert (1/min/account) | 1,667 | 1,667 | the 08 §11's minute bucket, `LEAST`/`GREATEST` widening |
| `broker_deals` INSERT (50/account/day) | 58 | 1,200 | `ON CONFLICT DO NOTHING`, the news-burst ×20 |
| `outbox` INSERT (1 per tick, ADR-6) | 2,500 | 10,000 | same tx as the group commit, so it is a row, not a commit |
| `events` INSERT (the relay's log, the 04 §3.4) | 2,500 | 10,000 | the F13 hot-window row |
| verdict / LED / AUD (breach-only + the payout path) | < 50 | < 500 | rare by construction |
| **Commits (transactions, not rows)** | **≈ 2,600/s** | **≈ 10,100/s** | the evaluation tx + the group-commit tx + the verdict tx |
| **Queries** | **≈ 11,800 q/s** | **≈ 42,900 q/s** | the figure the primary must absorb |

Against an AX42-class 8–16 vCPU NVMe primary, planned in §1.3 at
**≈ 10k q/s** with commits the scarce resource (NVMe group commit is
≈ 10k–20k commits/s at these row sizes; the 1,500-IOPS figure in the old
§1.3 row was for the 10k-account load and is superseded):

- **Sustained (≈ 11.8k q/s, ≈ 2.6k commits/s): fits, with ~4× commit
  headroom and ~1.2× CPU headroom.** Tight on CPU, comfortable on
  durability. Partitioning (§3.4.2) plus moving every non-hot-path read to
  the replica (§3.4.3) is what keeps it there.
- **Burst (≈ 42.9k q/s, ≈ 10.1k commits/s): does not fit.** It is at or
  past the commit ceiling and ~4× the CPU plan.

**But burst does not need to be served at line rate — it needs to be
drained inside the staleness window.** This is the arithmetic that decides
the question, so it is shown rather than asserted. Take the §4.4 burst
(10k ticks/s) sustained for 5 minutes against a write path that serves
5,000 ticks/s:

```
backlog accrued   = (10,000 − 5,000) ticks/s × 300 s   = 1.5 M events
drain after burst = 1.5 M ÷ 5,000 ticks/s              = 300 s
worst-case lag    = 300 s (during) + 300 s (drain)     = 600 s = 10 min
```

**10 minutes is exactly the `evl.tick_stale` threshold (the 09 §6).** So a
single primary survives the corrected target's worst burst with **zero
margin against the correctness backstop** — verdicts begin being suppressed
at precisely the moment the backlog clears. That is not a design anyone
should sign off on as "sufficient".

#### 3.4.2 The decision: partition by `tenant_id`, and stage the horizontal option on a measured trigger

**Adopted now (V2):**

1. **Partition `evaluation_state` by `tenant_id`** (hash, 64 buckets —
   enough for the 00 §5's 50-tenant range without a re-partition, and a
   power of two so the D82 shard mapping and the bucket mapping agree).
   Every evaluation query is tenant-scoped by the 00 §8 non-negotiable #2,
   so partition pruning applies to 100 % of the hot path. `evaluation_state`
   is only 100k rows — it needs tenant *locality*, not a time dimension.
2. **Partition `account_snapshots` and `broker_deals` by `(tenant_id, day)`**
   — these are the 144 M and 5 M rows/day tables, and they are also the two
   with a rolling window (14 d and 90 d, the 08 §11), so day partitioning
   makes retention a `DROP PARTITION` instead of a `DELETE` of 2 B rows.
   Their write volume *is* comparable to `evaluation_state`'s (1,667/s and
   58/s vs 2,500/s) and `account_snapshots`' row count is 20× larger, so
   the task's "if write volume there is comparable" test is met for
   `account_snapshots` outright and for `broker_deals` on row-count and
   retention grounds.
3. **Partition `events` by day**, and give `bridge.tick` the **≤ 7-day hot
   window + R2 columnar archive** that F13 forces (≈ 605 GB hot instead of
   ≈ 34 TB). Every other topic keeps the 13-month PG window — they are 3–4
   orders of magnitude smaller and the 05 §9 / 21 §3.4's 7-yr audit
   requirement is unaffected.
4. **One write path per account, structurally.** The 09 §3.2's "single
   writer per account" is guaranteed by the D81 split + the D82 lane
   ownership: exactly one `workers` lane owns an account
   (`hash(account_id) → lane`, one tenant per lane set), and that lane is
   the only thing that writes `evaluation_state` for it. Before D81 this
   guarantee did not structurally exist anywhere — the Rust engine's own
   Postgres `AccountStore` with OCC was a *second* writer, and OCC turns a
   correctness property into a retry loop.

**Staged, not adopted: horizontal Postgres (Citus, distribution key
`tenant_id`).** The trigger is **measured**, per §1.1.1's trigger 6:

> Adopt Citus when the §6 load test — or production — shows **either**
> sustained commit rate > 6,000/s (60 % of the primary's ≈ 10k ceiling, the
> §1.2 2× rule applied to commits rather than to CPU) for 2 weeks, **or**
> `evl_lag_seconds` > 300 (the D84 page threshold) more than twice a month
> with the engine tier demonstrably not saturated.

**Why not adopt it now**, given the burst arithmetic above:

- The corrected *sustained* load does not require it (§3.4.1), and the
  burst is handled by the D84 shedding ladder — which removes ≈ 14 % at level 1, ≈ 30 % at level 2 and ≈ 60 % at level 3 of
  sustained load (docs/63 §4.14) for **zero correctness cost at levels 1–2**,
  because it widens the conflation window rather than dropping observations
  (`equity_low/high_cents` still bound the gap, invariant I-22).
  Shedding is ~200 lines in a component that already exists; Citus is a
  new database topology.
- Citus conflicts with the 00 §8 non-negotiable #6 (operable by a 1-person
  DevOps team, "boring technology, honestly scoped"). Distributed DDL,
  shard rebalancing, and the loss of cross-shard transactional guarantees
  are a step change in operational attention, and the platform's whole
  posture is that attention is the scarce resource.
- The ADR-6 outbox is a **single-database transaction** with the writes it
  describes ("events are transactions, not side effects"). Citus makes that
  a distributed transaction across shards unless the outbox is co-located
  with every writer — solvable (distribution key `tenant_id` co-locates a
  tenant's outbox with its evaluation rows) but it must be *designed*, not
  discovered during an incident.
- **Partitioning first is not a dead end:** `tenant_id` hash partitioning
  and a Citus `tenant_id` distribution key are the same sharding function,
  so the migration is a shard move, not a data-model change. That is the
  real reason to stage rather than to decide now.

**Rejected outright:** sharding by `account_id` (breaks tenant locality and
the 00 §8 #2 isolation property); a second primary with per-tenant write
routing (two write paths, and the 09 §3.2's single-writer guarantee becomes
a coordination problem); Redis as the evaluation state store (the 00 §8 #1
non-negotiable — Postgres is the system of record).

#### 3.4.3 The read-replica story

**Nothing outside the evaluation write path reads the primary.** Concretely:

| Reader | Reads | From | Lag tolerance |
|---|---|---|---|
| `workers` evaluation lane | `evaluation_state` (1 SELECT + 1 UPDATE per tick) | **primary** | none — this *is* the write path |
| bridge floor-hint reload (docs/63 §4.4) | `evaluation_state.floor_*` | **primary** on cache miss, then the `evl.floors` pub/sub | ≤ 30 s (the PG-reload fallback); hints are advisory by construction |
| ANA read model (the 19 §3.1) | `account_snapshots`, `broker_deals`, `events` | **replica**, `_ro` role | minutes; rebuildable (the 19 §2), carries `as_of` |
| Dispute replay / the 18's tickets | `evaluation_state`, verdicts, `bridge.tick` evidence | **replica**; older than the F13 hot window → **the R2 archive** | minutes; the 09 §3.4's recompute is off-peak (the 06 §3.3's advisory-lock) |
| ADM screens (the 17), TD (the 16) | account + snapshot reads | **replica**, `_ro` | seconds; the TD live view is SSE from Redis, not PG |
| PAY eligibility (the 11 §3.1, BRG-09) | the account's hot state | **primary** (a payout decision must not read a lagging replica) | none |
| RSK batch detectors (the 10 §3) | `broker_deals` | **replica**, off-peak | hours; RSK is batch by design and never subscribes to ticks |

Replication is physical streaming (the 06 §3.3's failover strategy
extended — the same mechanism, now doing double duty as the read scale-out
and the warm-standby promotion path, the D56 host). Lag is a Prometheus
metric with a **WARN at 10 s / CRITICAL at 60 s**, and every replica read
that a human sees carries `as_of` so the lag is disclosed rather than
hidden (the ANA-14, the 24 Part B's posture). The replica lives on box 2
(§3.1), which is also why box 2 is a V2 prerequisite and not a V3 seam: it
carries the `bridge-stream` shards *and* the replica, and the two are
complementary loads (RSS-heavy + read-heavy, rather than two writers).

## 4. The cross-module failure map (the blast-radius,
the 28 §2.3's security posture, the 06 §3.3's
runbook)

| Failure | The blast | The V1/V2 design | The recovery |
|---|---|---|---|
| **The PG down** (the primary) | The everything (the write + the read) — the platform-down (the 06 §3.3's P0) | pgBackRest (the 06 §3.2 — D55, docs/57 — the RPO ≤ 5-min), the warm standby (D56, docs/57 — the promote ≤ 15-min), the 06 §3.3's runbook (the failover, the 06 §3.3, the RTO ≤ 15-min promoted (D56) / ≤ 2-h worst case), the no-Redis-dependency-on-the-trading (the 08 §3.2's PG-sync (the 01 ADR's posture, the 28 §2.3 #10)) | The 06 §3.3's failover (the 06 §3.3, the drill (the 06 §3.2's monthly, the 27 Part C.1's PLT-05's game-day (the 27 Part C.1 §2))), the CON-15 (the 21 §3.2, the P0, the 15-min (the 06 §3.3)), the status (the external uptime monitor — D57, docs/57 — the 06 §12, the DVP-07 (the 27 Part A §1, the V3)) |
| **The Redis down** | The session-deny (the 02 §3.5's hot), the rate-limit (the 04 §3.4), the SSE (the 01 §4.3), the queue (the 14/15's) — the degraded (the 06 §3.3's P1) | The PG-fallback (the 02 §3.5: the session (the PG (the 02 §3.5) + the Redis (the 02 §3.5) — the Redis-down = the PG-slow (the 02 §11's posture), the rate-limit (the 04 §3.4's PG-fallback (the 04 §11), the SSE (the 01 §4.3's relay-down (the 16 §11's posture: the SSE-drop (the client-reconnect (the 16 §3.1's pattern, the 01 §4.3's class)), the queue (the 14/15's Redis-queue (the 01 §2's BullMQ-class (the 01 §2)) — the Redis-down = the queue-pause (the 14 §11's posture, the no-event-loss (the 04 §5.7's at-least-once, the outbox (the 04 §5.4, the PG (the 04 §5.4) — the outbox is the PG (the 04 §5.4, the 01 ADR), the relay's re-read (the 04 §5.4, the LastSeq+1 (the 04 §5.4's resync (the 04 §11)))))) | The 06 §3.3's P1 (the 06 §3.3, the 30-min (the 06 §3.3)), the Redis-restart (the 06 §3.1's compose, the AOF (the 01 §2, the 06 §3.1), the no-data-loss (the AOF (the 01 §2))), the no-trading-impact (the 08 §3.2's PG-sync (the 01 ADR), the 28 §2.3 #10's posture) |
| **The MetaApi down** (the provider) | The sync (the 08 §3.2, the tick/deal), the command (the 08 §3.3, the enforcement) — the trading-degraded (the 06 §3.3's P1, the trader-can't-act (the 08 §11's posture)) | **Streaming (D78):** accounts go `stale` → no heartbeat ticks → `evl.tick_stale`; the credit-budgeted fallback poll covers funded/open-position accounts first (docs/63 §4.7); on recovery a prioritised resync from the PG deal cursor + the D33 check (cold resync ≈ 1–2 min at 10k). Then, as before: the poll (the 08 §3.2, the 60-s, the stale (the 09 §6's `evl.tick_stale`, the 08 §11's class)), the sync-gap (the 08 §3.2's `bridge.sync_gap` (the 08's event, the 04's event-catalog (the 31 doc)), the backfill (the 08 §3.2, the catch-up (the 08 §3.2's posture)), the no-verdict-on-stale (the 09 §6's `evl.tick_stale`, the 09 §11's posture: the no-enforcement-on-the-stale-feed (the 08/09's class, the 28 §2.3 #6)), the command-queue (the 08 §3.3's executor (the 08 §3.3, the PG-queue (the 08 §9's class), the retry (the 08 §3.3, the idempotency (the 08 §3.3's command (the 08 §9, the 04 §3.3's class)))) | The 06 §3.3's P1 (the 06 §3.3, the 30-min), the `ops.provider_health` (the 04's event (the 31 doc), the CON-15 (the 21 §3.2), the trader-notice (the 14's NOT, the 14 §3.4, the 26 Part A's push (the 26 Part A §3.3))), the backfill (the 08 §3.2, the catch-up (the 08 §3.2)), the no-payout-impact (the 11 §3.4's NOWPayments (the 11 §1, the no-MetaApi-dependency (the 11 §11's posture: the payout is the NOWPayments (the 11 §1), the MetaApi-down = the no-payout-impact (the 11 §11)))) |
| **The EVL down** (the Rust) | The verdict (the 09 §1, the observed/evaluated) — the enforcement-degraded (the 07 §11's posture) | The Go-fallback (the 09 §11: the EVL-down = the no-new-verdict (the 07 §3.2's enforcement (the 07 §3.1, the no-command (the 07 §11's posture: the no-enforcement-on-the-no-verdict (the 07/09's class, the 28 §2.3 #6)), the observed-continue (the 09 §3.4's observed (the 09 §1), the no-evaluated (the 09 §3.4, the 07 §11), the no-silent-skip (the 09 §11's event (the 09's `evl.metric_unavailable` (the 09 §6), the 04's DLQ (the 04 §5.6, the 04's class)))) | The 06 §3.3's P1 (the 06 §3.3, the 30-min), the EVL-restart (the 06 §3.1's compose, the stateless (the ADR-11 (the 01 §3), the 09 §1), the no-state-loss (the 09 §11's posture)), the backfill (the 09 §3.4's recompute (the 09 §3.4, the 06 §3.3's runbook (the 06 §3.3), the verdict-recompute (the 28 §11's property (the 09 §3.4)), the CON-15 (the 21 §3.2) |
| **The relay down** (the 04 §5.4) | The event (the 04 §5.4, the at-least-once), the webhook (the 04 §5.6), the SSE (the 01 §4.3) — the event-degraded (the 06 §3.3's P2) | The PG-outbox (the 04 §5.4, the no-event-loss (the 04 §5.4's posture: the event is the PG (the 04 §5.4), the relay is the re-read (the 04 §5.4, the LastSeq+1 (the 04 §11's resync (the 04 §5.4))), the no-trading-impact (the 08 §3.2's PG-sync (the 01 ADR), the 28 §2.3 #10, the 04 §5.4's posture: the relay-down = the no-trading-impact (the 04 §11)))), the webhook-retry (the 04 §5.6, the Hook0's retry (the 04 §5.6, the 5-attempt (the 04 §5.6), the DLQ (the 04 §5.6), the replay (the 27 Part A's SDK-07 (the 27 Part A §3.2)))) | The 06 §3.3's P2 (the 06 §3.3, the 4-h), the relay-restart (the 06 §3.1's compose, the advisory-lock (the 04 §5.4, the single (the 04 §5.4's class), the no-double-relay (the 04 §5.4, the 01 ADR))), the backfill (the 04 §5.4, the LastSeq+1 (the 04 §11), the no-event-loss (the 04 §5.4)), the webhook-replay (the 04 §5.6, the 27 Part A's SDK-07 (the 27 Part A §3.2), the tenant-admin (the 27 Part A §3.2)) |
| **The Hook0 down** (the egress) | The webhook (the 04 §5.6, the tenant's integration) — the integration-degraded (the 06 §3.3's P2, the 27 Part A §11's posture) | The Hook0's retry (the 04 §5.6, the 5-attempt (the 04 §5.6), the DLQ (the 04 §5.6)), the no-platform-impact (the 04 §5.6's posture: the webhook is the egress (the 04 §5.6), the Hook0-down = the no-platform-impact (the 04 §11), the event is the PG (the 04 §5.4, the 04 §5.4's class))), the developer-notice (the 27 Part A's DVP-07 (the 27 Part A §1, the status (the 27 Part A §3.1), the delivery-log (the 27 Part A's DVP-05 (the 27 Part A §1)))) | The 06 §3.3's P2 (the 06 §3.3, the 4-h), the Hook0-restart (the 06 §3.1's compose, the stateless (the 04 §5.6), the no-delivery-loss (the DLQ (the 04 §5.6), the replay (the 04 §5.6, the 27 Part A's SDK-07 (the 27 Part A §3.2)))) |
| **The Veriff down** (the KYC-provider) | The KYC (the 13 §12, the verify) — the KYC-degraded (the 06 §3.3's P2, the no-purchase-impact (the 13 §11's posture: the L1-purchase (the 13 §1, the Veriff-down = the no-new-KYC (the 13 §11), the existing-verified (the 13 §3.1's state, the no-impact (the 13 §11)), the no-payout-impact (the 11 §3.1's eligibility (the 11 §3.1, the existing-verified (the 13 §3.1's state), the new-KYC (the 13 §11's queue (the 13 §11, the retry (the 13 §12, the provider's rate (the 13 §12))))))) | The 06 §3.3's P2 (the 06 §3.3, the 4-h), the Veriff-retry (the 13 §12, the provider's rate (the 13 §12), the queue (the 13 §11, the 06 §3.3's advisory-lock (the 06 §3.3))), the trader-notice (the 14's NOT, the 14 §3.4, the 26 Part A's push (the 26 Part A §3.3)) |
| **The NOWPayments down** (the payout-rail) | The payout (the 11 §3.4, the crypto) — the payout-degraded (the 06 §3.3's P1, the manual-fallback (the 11 §3.5's posture)) | The 11 §3.5's failed → the manual (the 11 §3.5, the 18's ticket (the 18 §3.1), the no-auto-retry (the 11 §3.5, the re-approval (the 11 §3.5, the 2FA (the 02 §3.4)))), the manual-wire (the 12 §1's wire (the 12 §1, the 11 §3.5's class, the tenant's ops (the 17 §3.1's ADM, the 11 §3.5)), the reconciliation (the 11 §3.5, the provider-events (the 04 §5.5's pattern, the 11 §3.5)), the no-purchase-impact (the 12 §1's rail (the 12 §1, the Match2Pay/Interkasa (the 12 §1, the no-NOWPayments-dependency (the 12 §11's posture: the purchase is the Match2Pay/Interkasa (the 12 §1), the NOWPayments-down = the no-purchase-impact (the 12 §11)))) | The 06 §3.3's P1 (the 06 §3.3, the 30-min), the NOWPayments-retry (the 11 §3.4, the provider's rate (the 11 §12), the queue (the 11 §11, the 06 §3.3's advisory-lock (the 06 §3.3))), the trader-notice (the 14's NOT, the 14 §3.4, the 26 Part A's push (the 26 Part A §3.3)), the CON-15 (the 21 §3.2) |
| **The Postmark down** (the email) | The email (the 14 §12, the transactional) — the email-degraded (the 06 §3.3's P2, the no-money-impact (the 14 §11's posture: the email is the notify (the 14 §1), the Postmark-down = the no-money-impact (the 14 §11), the push-fallback (the 26 Part A's push (the 26 Part A §3.3, the critical (the 14 §3.4's class, the 26 Part A §3.3))))) | The 14 §3.4's queue (the 14 §3.4, the Redis's (the 01 §2's BullMQ-class (the 01 §2), the 14 §12), the retry (the 14 §3.4, the Postmark's rate (the 14 §12, the 0.5/s-class (the 14 §12))), the `notification.failed_final` (the 14's event (the 31 doc), the CON-adjacent (the 21 §3.4, the 14 §11)), the in-app-fallback (the 14 §3.1's adapter (the 14 §3.1, the in-app (the 14 §3.1, the no-Postmark-dependency (the 14 §11)))) | The 06 §3.3's P2 (the 06 §3.3, the 4-h), the Postmark-retry (the 14 §3.4, the queue (the 14 §3.4), the no-email-loss (the 14 §3.4, the outbox-class (the 04 §5.4's pattern, the 14 §3.4)))), the push-fallback (the 26 Part A's push (the 26 Part A §3.3, the critical (the 14 §3.4's class))) |
| **The R2 down** (the storage) | The document (the 13 §3.4, the KYC), the media (the 24 Part A §3.5, the video), the export (the 27 Part A's SDK-12 (the 27 Part A §3.3), the report (the 19 §3.3) — the document-degraded (the 06 §3.3's P2) | The no-trading-impact (the 13 §11's posture: the R2-down = the no-trading-impact (the 13 §11), the KYC-verify (the 13 §3.4, the R2 (the 13 §3.4), the R2-down = the no-new-KYC-doc (the 13 §11), the existing (the 13 §3.1's state, the no-impact (the 13 §11)))), the snapshot (the 05 §3.5, the R2 (the 05 §3.5), the R2-down = the no-snapshot (the 05 §11's posture: the snapshot is the nightly (the 05 §3.5), the R2-down = the snapshot-skip (the 05 §11, the next-night (the 05 §3.5's class, the no-data-loss (the PG (the 05 §9), the R2 is the copy (the 05 §3.5, the 28 §3.3's posture: the PG is the source (the 05 §1), the R2 is the snapshot (the 05 §3.5))))) | The 06 §3.3's P2 (the 06 §3.3, the 4-h), the R2-retry (the 13 §3.4 / the 24 Part A §3.5 / the 19 §3.3, the Cloudflare's rate (the 24 Part A §11, the 01 §2), the queue (the 13 §11 / the 24 §11 / the 19 §11, the 06 §3.3's advisory-lock (the 06 §3.3))), the no-trading-impact (the 13 §11 / the 05 §11's posture) |
| **The box down** (the infra) | The everything — the platform-down (the 06 §3.3's P0, the 00 §6's RTO ≤ 2-h (the 00 §6), the 06 §3.2) | The 06 §3.2's DR (pgBackRest — D55, docs/57 — (the RPO ≤ 5-min (the 00 §6)), the 06 §3.2's restore (the RTO ≤ 15-min promoted (D56, docs/57) / ≤ 2-h worst case), the warm standby (the D56 host — the promote in minutes), the 2nd-box (the V3, the §3.2, the RTO-improvement (the 06 §3.3's failover (the 06 §3.3), the minutes (the 27 Part C.1's PLT-01's class))), the multi-region (the V3-late, the §3.3, the PLT-01 (the 27 Part C.1), the RTO (the 06 §3.2, the minutes (the 27 Part C.1's PLT-01)), the external uptime monitors + the dead-man switches (D57, docs/57 — the 06 §12, the 21 §12 — the detection (the 06 §3.3, the 1-min (the 06 §12's class, the 06 §3.3)), the status (the 06 §3.3, the 21 §3.2's CON-15 (the 21 §3.2), the tenant-notice (the 14's NOT, the 14 §3.4 (the 06 §3.3's comms (the 06 §3.3))), the manual-recovery (the 06 §3.2's runbook (the 06 §3.2), the 06 §3.3's P0 (the 06 §3.3, the 15-min (the 06 §3.3))) | The 06 §3.2's DR (the 06 §3.2, the monthly (the 06 §3.2, the 00 §6's binding), the 27 Part C.1's PLT-05's game-day (the 27 Part C.1 §2, the quarterly (the 27 Part C.1)), the CON-15 (the 21 §3.2, the P0, the 15-min (the 06 §3.3)), the 06 §3.3's runbook (the 06 §3.3, the §4's class) |

## 5. The cost model (the 27 Part C.1's PLT-03, the 22 §3.4)

The cost is the **tenant's + the platform's** (the 22 §3.4's
pass-through, the 27 Part C.1's PLT-03):

| Cost | The class | The owner | The 22 §3.4's posture |
|---|---|---|---|
| **The MetaApi** (the 08 §1, the $75/mo/account-class) | The per-account (the 08 §1, **the corrected 100k = the $7.5M/mo-class platform-wide, ≈ the $750k/mo-class per tenant at 10k accounts** (the §1.1/§1.3); the old row's "the 00 §5's 10k = the $750k/mo-class" was the single-tenant figure and understated the platform total 10×. **This is the dominant cost of the corrected target and it is also its natural governor: the deployed-account count is cost-gated per tenant, so 100k is a capacity target, not a forecast**) | The tenant (the 22 §3.4, the 27 Part C.1's PLT-03, the BIL-17 (the 22 §3.2), the pass-through (the 22 §3.4)) | The "at-cost + 5%" (the 22 §3.2), the transparent (the 22 §3.4, the 27 Part A's DVP-06 (the 27 Part A §1, the usage (the 27 Part A §3.3))) |
| **The infra** (the 06 §1, the Hetzner, the AX42-class) | The platform's (the 06 §1, the 00 §8's non-negotiable (the 00 §8)) | The platform (the 22 §14's platform-book (the 22 §14), the 27 Part C.1's PLT-03's allocation (the 27 Part C.1 §2), the per-tenant (the 22 §3.1's meter (the 22 §3.1), the CPU/RAM/storage (the 06 §3.4's measured, the 06 §3.1's cgroup (the 06 §3.1))) | The platform's margin (the 22 §3.4, the disclosed (the 22 §3.4), the BIL's invoice (the 22 §3.5, the monthly (the 22 §3.5))) |
| **The R2** (the 01 §2, the storage) | The per-GB (the 01 §2, the 22 §3.1's meter (the 22 §3.1), the 13-mo-tick (the 04 §5.4, the 06 §3.2's archive (the 06 §3.2)), the 7-yr (the 05 §3.5, the 00 §6)) | The tenant (the 22 §3.4, the 27 Part C.1's PLT-03) | The pass-through (the 22 §3.4) |
| **The Cloudflare** (the 01 §2, the bandwidth + the WAF + the DDoS (the 01 §2, the 28 §3.1)) | The per-GB + the flat (the 01 §2, the 22 §3.1's meter (the 22 §3.1)) | The tenant (the 22 §3.4, the 27 Part C.1's PLT-03) | The pass-through (the 22 §3.4) |
| **The providers** (the Veriff (the 13 §12), the NOWPayments (the 11 §12), the Match2Pay/Interkasa (the 12 §12), the Postmark (the 14 §12), the ipinfo (the 02 §3.6)) | The per-use (the 13 §12 / the 11 §12 / the 12 §12 / the 14 §12, the 22 §3.1's meter (the 22 §3.1)) | The tenant (the 22 §3.4, the 27 Part C.1's PLT-03) | The pass-through (the 22 §3.4) |
| **The V3-late compute** (the 29's V3 line, the 06 §3.3's off-peak): the backtest (the 27 Part B §11), the paper (the 27 Part B §11), the ML (the 10 §12), the BigQuery (the 19 §3.5) | The platform's (the 06 §3.3, the 27 Part C.1's PLT-02 (the 27 Part C.1 §2), the 29 doc's budget (the §1.3)) | The platform (the 22 §14, the 27 Part C.1's PLT-03) | The platform's cost (the 22 §14, the no-pass-through (the 22 §3.4's posture: the V3-late compute is the platform's investment (the 22 §14), the tenant's benefit (the 27 Part B's TRD (the 27 Part B §1), the 10's RSK-ML (the 10 §12), the 19's BigQuery (the 19 §3.5))) |

## 6. The scalability's assurance (the test, the drill,
the review — the 28 §11's class)

- **The load-test** (the 06's CI, the 01 §2's GitHub
  Actions, the **corrected** V2-target (§1.1), the 2×
  (the §1.2)): the k6-class (the 01 §2's register-
  consistent OSS, the 06's CI, the monthly (the
  06's calendar, the 27 Part C.1's PLT-02 (the
  27 Part C.1 §2))).
  **v1.1 — the load test is re-targeted at 100,000
  accounts. The previous version of this bullet
  validated 10,000 accounts and the numbers below
  were derived from it; a load test that passes at 10k
  says nothing about whether the system survives 100k,
  and the four ceiling crossings in §1.1 (the relay's
  2k msg/s process limit, the 16-lane `workers`
  default, the gateway's per-box RSS, the `events`
  13-month retention) are all invisible below 100k.**
  The scope, with the corrected targets:
  | # | What is loaded | The target (§1.1/§1.3) | The exit criterion |
  |---|---|---|---|
  | LT-1 | **The ingest fan-out** — 100k simulated accounts as **10 tenant partitions × 10k**, recorded-packet replay with ×N fan-out (the docs/63 §6 load row, the BRG-43 fixture corpus) | ≈ 30k inbound `Equity` frames/s sustained, 100k/s burst; ≤ 2,500 emitted `bridge.tick`/s sustained | the conflator holds the I-21 crossing invariant at 100k/s inbound; no shard exceeds the 1.5 GB RSS alarm (**measures F12's shard count — this is the test that retires the estimate**); Q3/Q7 answered with a real RSS/account figure |
  | LT-2 | **The relay** — ≥ 10 partitions by `(topic, tenant-shard)` | **≥ 600k events/min = 10k msg/s** sustained across the partitions; 20k msg/s at the 2× rule | the publish latency p95 < 10 ms after commit (the 04 §3.3's doorbell); `relay.lag{topic=bridge}` < 5 s (the WARN threshold); no partition starved |
  | LT-3 | **The `workers` evaluation lane** — ≥ 128 lanes, per-tenant lane sets (the D82) | 2,500 ticks/s sustained, 10k/s burst; the per-tick budget p95 < 10 ms (the 09 §11) | quote→verdict p95 < 50 ms platform-internal, < 150 ms to the disable command sent (the docs/63 §4.6's SLO); **no lane's head-of-line delay exceeds the 09 §11 budget — this is the assertion that the ≥ 16-lane figure was wrong** |
  | LT-4 | **The D82 fairness assertion** — tenant A driven at 10× its weight while tenants B–J idle at their sustained rate | tenant A's burst consumes **only** its own lane set | **tenants B–J's quote→verdict p95 is unchanged within measurement noise vs the no-spike baseline**; zero `evl.tick_stale` suppressions outside tenant A. *This is the test the whole D82 decision rests on — without it, "per-tenant sharding gives fairness" is an assertion, not a result* |
  | LT-5 | **The PG write path** — the §3.4.1 table driven end to end | ≈ 11.8k q/s sustained, ≈ 42.9k q/s burst, ≈ 2.6k / ≈ 10.1k commits/s; `tenant_id` partition pruning on 100 % of the hot path | the sustained figure holds at p95 < 10 ms for the state read+write; **the burst is drained inside the 10-min `evl.tick_stale` window with margin — §3.4.1's arithmetic predicts exactly zero margin, so this test either confirms the margin is negative (⇒ the D83 Citus trigger fires early) or retires the estimate** |
  | LT-6 | **The D84 shedding ladder** — inject a 5-min fleet-wide burst at 10k ticks/s with scaling disabled | shed levels 1→2→3 engage per the §4.14 thresholds | the ladder removes ≈ 14 % at level 1, ≈ 30 % at level 2 and ≈ 60 % at level 3 of sustained load as predicted; **zero `deal`/`position`/`guard`/crossing/`resync` ticks are shed at any level**; the I-22 evidence invariant holds across every widened conflation window (the `equity_low/high_cents` still bound the gap) |
  | LT-7 | **The Redis Streams trim hazard** (the docs/63 §4.13) — drive one tenant's group past `MAXLEN ~100000` | `evl.stream_trimmed` fires | the trim is detected before any evaluation gap is silent, and the replay-from-PG for that tenant's range restores the verdict sequence byte-identically |
  | LT-8 | **The GW / the SSE / the webhook** (the read side, unchanged in kind) | the GW ≈ 20k rps across ≥ 10 instances; the SSE 5,000 connections; the webhook 500 endpoints | the p95 (the 04 §6's class), the no-error (the 04 §6's posture, the 06 §3.3's incident) |
  **The exit for the whole test:** every planning estimate in §1.3 and
  §3.4 that it touches is replaced by a measured number, and §1.1.1's
  trigger 6 is discharged. **Until LT-1/LT-5 have run, the shard count,
  the box count and the D83 Citus trigger are estimates and must be
  labelled as such wherever they are quoted** (the docs/63 §8 posture:
  measure, don't decide). The old scope's "the 08's poll (the 167 req/s)"
  row is deleted — under D78 there is no steady-state poll to load.
- **The restore-drill** (the 06 §3.2, the
  00 §6's binding, the weekly automated
  verify + the monthly full drill — D59,
  docs/57): the RPO (the 06 §3.2, the ≤
  5-min (the 00 §6)), the RTO (the 06
  §3.2, the ≤ 15-min promoted (D56) /
  ≤ 2-h worst case), the
  isolation (the 28 §3.3, the post-
  restore (the 28 §11's class)), the
  age-key (the 28 §5, the offline (
  the 28 §5)), the V3: the 2-box (the
  §3.2, the failover (the 06 §3.3,
  the 27 Part C.1's PLT-05 (the 27
  Part C.1 §2), the game-day (the
  27 Part C.1 §2, the quarterly (
  the 27 Part C.1))), the multi-region
  (the V3-late, the §3.3, the PLT-01
  (the 27 Part C.1), the cross-region
  (the 06 §3.3, the 27 Part C.1 §2)).
- **The capacity-review** (the 27 Part
  C.1's PLT-02, the 21 §3.4, the
  quarterly (the 27 Part C.1 §2)):
  the 00 §5's target (the 00 §5),
  the 06 §3.4's measured (the 06
  §3.4), the 2× (the §1.2), the
  2nd-box (the §3.2, the PLT-02 (
  the 27 Part C.1), the CON-32 (
  the 21 §3.5, the two-op (the 21
  §3.5), the 7-yr (the 21 §3.4),
  the cost (the 27 Part C.1's PLT-03
  (the 27 Part C.1 §2), the 22 §3.4).
- **The V3-compute-budget** (the 29
  doc's line, the 06 §3.3's off-peak,
  the 27 Part C.1's PLT-02 (the 27
  Part C.1 §2)): the backtest (the
  27 Part B §11, the 27 Part B §3.2,
  the 09's historical (the 27 Part B
  §3.2), the off-peak (the 06 §3.3,
  the 06 §3.3's advisory-lock (the
  06 §3.3))), the paper (the 27 Part
  B §11, the 27 Part B §3.3, the
  simulation (the 27 Part B §3.3),
  the off-peak), the ML (the 10 §12,
  the sidecar (the 28 §2.2 T5), the
  no-network (the 28 §2.2 T5), the
  off-peak), the BigQuery (the 19
  §3.5, the 00 §7's consider-later
  (the 00 §7), the off-peak, the
  06 §3.3's advisory-lock (the 06
  §3.3)), the R2-archive (the 04
  §5.4, the 13-mo (the 04 §5.4),
  the 06 §3.2's archival (the 06
  §3.2), the 22 §3.1's cost (the 22
  §3.1)), the exit: the no-peak-
  impact (the 06 §3.3's posture,
  the 06 §3.4's Grafana (the 06
  §3.4), the 27 Part C.1's PLT-02
  (the 27 Part C.1 §2)).

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

## 1. The capacity model (the 00 §5 targets)

### 1.1 The scale targets (docs/00 §5, the binding)

| Metric | V1 (the launch) | V2 (the growth) | V3 (the ecosystem) |
|---|---|---|---|
| Tenants | 1-5 (the FunderBlu first) | 25-50 | 25-50 (the quality-over-quantity, the 00 §5) |
| Traders (active identities) | 500 | 5,000 | 50,000 |
| Funded trader accounts | 250 | 5,000 | 10,000 |
| Concurrent broker accounts (the 08's sync) | 500 | 10,000 | 10,000 |
| Tick rate (sustained) | 20/s (streaming-conflated `bridge.tick`, D79 — ≈ 10/s expected, ≈ 100/s news burst, docs/63 §4.4) | 250/s sustained, 1k/s burst (D79 envelope at 10k accounts) | 250/s (the V3 is the breadth, not the tick-rate, the 00 §5) |
| Event rate (the 04's relay) | 500 msg/s | 2,000 msg/s | 5,000 msg/s (the webhook fan-out, the 27 Part A) |
| Orders/day (the trader's, the 08) | 1,000 | 5,000 | 5,000 |
| Payouts/day | 100 | 500 | 500 |
| Webhook endpoints (the 04 §5.6) | 5 | 50 | 500 |
| SSE connections (the 01 §4.3) | 50 | 500 | 5,000 |
| Users concurrent (the 16's TD + the 17's ADM) | 50 | 500 | 5,000 |

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

### 1.3 The per-resource model (the V2 peak, the 2× rule)

| Resource | V2 peak (the 00 §5) | The 2× headroom | The V3 (the 00 §5) |
|---|---|---|---|
| **PG CPU** (the writes: the tick/deal sync, the LED, the AUD) | the ~60% of a 8-vCPU (the 08's sync + the 05's entries + the 05's audit, the 06 §3.4's measured) | the 12-vCPU-class (the 2nd box, the §3) | the same (the V3's load ≈ the V2's × 2 (the breadth), the 2-box covers) |
| **PG IOPS** (the NVMe) | the ~1500 IOPS sustained (the 06 §1's NVMe, the ~50k capable, the 06 §3.4's measured) | the 3k-class | the 4k-class (the 2-box) |
| **PG storage** (the 7-yr, the 05 §3.5, the tick's 13-mo, the 04 §5.4) | the ~200 GB/yr (the 08 §9's partitions + the 05 §9's 7-yr + the 19 §3.1's read model, the 06 §3.4's measured) | the 1 TB (the 06 §1's disk) | the 2 TB (the 2nd box + the R2-archive (the 06 §3.2's archival, the 13-mo-tick → the R2 (the 04 §5.4's class, the 22 §3.1's cost)) |
| **Redis memory** (the session, the deny-set, the SSE, the rate-limit) | the ~4 GB across the three containers (D51, docs/56 — redis-main / redis-streams / redis-cache, the 06 §2.6's 2/2/4 split; the 01 §4.3's SSE + the 02's hot-set, the 06 §3.4's measured) | the 8 GB | the 8 GB (the Redis doesn't scale with the tenant, the 01 §4.3's relay is the horizontal, the §3) |
| **The 08's MetaApi ingest budget** (D78, docs/63 F1/§4.11) | streaming: 10k accounts ≈ 20k subscriptions (high reliability; quota = 10 × deployed accounts), ≈ 200 sockets, 5–6 `bridge-stream` shards, **0 CPU credits** steady-state; REST only for fallback/D33/reconciler under a per-`client-id` credit budget (18k credits/min per MetaApi server; one poll ≈ 176 credits). The superseded 60-s poll-everything plan would need ≈ 1.76M credits/min vs ≈ 216k/min for all MetaApi servers — infeasible | the 20k-class (the V3's 10k concurrent + the copy's order budget, the 27 Part B §11) — more shards + a 2nd bridge instance (accounts sharded; hot state is rebuildable) | the same model |
| **The relay** (the 04 §5.4, the single-process, the advisory-lock) | the 2k msg/s (the PG's commit + the Redis publish, the 06 §3.4's measured) | the 4k-class | the 5k msg/s (the webhook fan-out, the Hook0's egress (the 04 §5.6) + the 2nd relay (the §3, the 04 §11's horizontal)) |
| **The GW** (the Go, the 04 §3) | the ~2k rps (the 00 §5's read + the write, the 06 §3.4's measured) | the 4k rps | the 10k rps (the public-API, the 27 Part A §11, the 2-GW (the §3, the stateless (the 04 §11's posture))) |
| **The EVL** (the Rust, the ADR-11, the 09 §1) | the ~1k verdict/s (the 100/s tick × the eval, the 06 §3.4's measured) | the 2k-class | the 2k-class (the stateless (the 09 §1), the 2-EVL (the §3)) |
| **The MetaApi cost** (the 08 §1, the $75/mo/account-class) | the 10k × the $75 = the $750k/mo-class (the 22 §3.4's pass-through, the 27 Part C.1's PLT-03, the tenant's cost) | — | the same (the cost is the tenant's, the 22 §3.4, the PLT-03's allocation (the 27 Part C.1)) |

**The read:** the V2's read-heavy (the 16's TD, the 19's
read model, the 27 Part A's public-API) — the read
path is the `*_ro` (the 19 §3.1, the 19 §9) + the PG's
read (the single, the V1/V2), the 2nd-box's read-replica
(the §3, the PG's logical/physical (the 06 §3.3's
failover strategy extended, the 27 Part C.1's PLT-01))
is the V3's read-scale (the 27 Part A §11's 5k rps
public-read, the 19's read model is the read-replica-
friendly (the 19 §2's rebuildable, the 19 §3.1's
`_ro` — the read-replica serves the `_ro` read,
the no-stale-tolerance (the ANA-14 (the 19 §2),
the `as_of`, the 24 Part B's posture)).

## 2. The per-module scaling surface (the aggregation
of the 26 module docs' §11 — the one-page map)

| Module | The surface (the §11's class) | The V1/V2 design | The V3 seam (the pull) |
|---|---|---|---|
| **AUTH (02)** | The session (the PG + the Redis's deny-set), the MFA (the TOTP, the no-ext), the anomaly (the 02 §3.6's in-proc) | The in-proc (the GW's), the Redis's hot (the 02 §3.5) | The no-seam (the AUTH scales with the GW, the 02 §11) |
| **TEN (03)** | The tenant-config (the PG, the cache (the 03 §3.1's Redis), the 9-step saga (the 03 §3.1)) | The PG + the Redis-cache (the 03 §11) | The no-seam (the tenant is the 50, the 00 §5, the config-cache covers) |
| **GW+EVT (04)** | The chain (the 04 §3), the relay (the 04 §5.4, the single, the advisory-lock), the egress (the Hook0, the 04 §5.6), the SSE (the 01 §4.3) | The single-relay (the PG's advisory-lock, the 04 §5.4), the Hook0 (the 01 §1's service), the SSE-relay (the 01 §4.3, the 16 §11's pattern) | The 2-relay (the 04 §11's horizontal: the advisory-lock's partition (the per-tenant-lock (the 04 §5.4's class), the 2-instance (the §3)), the Hook0's 2-instance (the 01 §1's compose scale, the stateless (the 04 §5.6)), the SSE's 2-instance (the 01 §4.3, the Redis-pub/sub (the 01 §4.3's posture)), the GW's 2-instance (the stateless, the 04 §11) |
| **LED+AUD (05)** | The entries (the PG, the partition (the 05 §9, the monthly), the 7-yr), the audit (the append-only, the 05 §9), the snapshot (the R2, the 05 §3.5) | The single-PG (the 05 §11), the nightly-snapshot (the R2, the 05 §3.5) | The 7-yr-archive (the 13-mo → the R2 (the 04 §5.4's class), the 06 §3.2's archival, the 22 §3.1's cost, the 27 Part C.1's PLT-03), the read-replica (the §3, the 05's read (the 27 Part A's SDK-12 export (the 27 Part A §3.3), the read-replica)) |
| **OPS (06)** | The infra (the single-box, the 06 §1), the DR (the 06 §3.2, the RPO/RTO), the observability (the 06 §3.4) | The single-AX42 + the warm standby (D56, docs/57), pgBackRest (D55, docs/57), the Grafana (the 01 §2) | The 2-box (the §3, the PLT-02 (the 27 Part C.1)), the multi-region (the PLT-01 (the 27 Part C.1), the 28 §10's residency, the RTO-trigger (the 06 §3.2's 2× miss)), the Loki/OTel (the V2, the 01 §2's "consider", the 06 §3.4's upgrade) |
| **LCC (07)** | The state-machine (the single `Transition()`, the 07 §3.1), the saga (the 9-step, the 03 §3.1's class) | The in-proc (the Go, the 07 §11) | The no-seam (the LCC is the command-path, the PG-serial (the 07 §3.1's single-write, the no-HA (the 07 §11's posture: the LCC's throughput is the 10/s-class (the 00 §5's account-change), the PG covers)) |
| **BRG (08)** | The poll (the 08 §3.2's stagger, the 60-s), the sync (the tick/deal, the 08 §9's partition), the command (the 08 §3.3's executor) | The single-bridge (the Go, the 08 §11), the poll-budget (the 08 §3.2, the per-tenant, the stagger) | The 2-bridge (the 08 §11's horizontal: the per-tenant-partition (the 08 §3.2's stagger's class), the 2-instance (the §3), the MetaApi's rate (the 08 §1's provider-limit, the 27 Part B's copy-order (the 27 Part B §11))), the tick-archive (the 13-mo → the R2 (the 04 §5.4, the 06 §3.2), the TRD-04's backtest (the 27 Part B §3.2, the 29's V3 compute)) |
| **EVL (09)** | The verdict (the Rust, the ADR-11, the 09 §1), the rulepack (the versioned, the 09 §3.1) | The single-EVL (the Go's call, the HTTP, the 09 §11), the in-proc-math (the 09 §1) | The 2-EVL (the 09 §11's horizontal: the stateless (the ADR-11 (the 01 §3), the 09 §1), the 2-instance (the §3)), the backtest (the historical-mode (the 27 Part B §3.2, the `--historical` flag, the 29's V3 compute, the off-peak (the 06 §3.3's advisory-lock)) |
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

### 3.1 The V1 → V2 (the headroom, the no-new-box)

The V1 box (the 06 §1's AX42-class) is **sized for the
V2** (the §1.2's 2× rule, the 06 §1): the V2's load
fits the V1 box (the §1.3's measured, the 06 §3.4's
Grafana, the 27 Part C.1's PLT-02's quarterly review
(the 27 Part C.1 §2)). The V1→V2's "scaling" is:
the config (the rate-limit (the 04 §3.4, the 27's
SDK-14), the poll-stagger (the 08 §3.2), the container-
limit (the 06 §3.1), the partition (the 08 §9 /
the 05 §9's monthly, the 32 doc's partitioning)),
the no-new-box (the 00 §8's non-negotiable, the
01 ADR).

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
| **The MetaApi** (the 08 §1, the $75/mo/account-class) | The per-account (the 08 §1, the 00 §5's 10k (the 00 §5) = the $750k/mo-class (the §1.3)) | The tenant (the 22 §3.4, the 27 Part C.1's PLT-03, the BIL-17 (the 22 §3.2), the pass-through (the 22 §3.4)) | The "at-cost + 5%" (the 22 §3.2), the transparent (the 22 §3.4, the 27 Part A's DVP-06 (the 27 Part A §1, the usage (the 27 Part A §3.3))) |
| **The infra** (the 06 §1, the Hetzner, the AX42-class) | The platform's (the 06 §1, the 00 §8's non-negotiable (the 00 §8)) | The platform (the 22 §14's platform-book (the 22 §14), the 27 Part C.1's PLT-03's allocation (the 27 Part C.1 §2), the per-tenant (the 22 §3.1's meter (the 22 §3.1), the CPU/RAM/storage (the 06 §3.4's measured, the 06 §3.1's cgroup (the 06 §3.1))) | The platform's margin (the 22 §3.4, the disclosed (the 22 §3.4), the BIL's invoice (the 22 §3.5, the monthly (the 22 §3.5))) |
| **The R2** (the 01 §2, the storage) | The per-GB (the 01 §2, the 22 §3.1's meter (the 22 §3.1), the 13-mo-tick (the 04 §5.4, the 06 §3.2's archive (the 06 §3.2)), the 7-yr (the 05 §3.5, the 00 §6)) | The tenant (the 22 §3.4, the 27 Part C.1's PLT-03) | The pass-through (the 22 §3.4) |
| **The Cloudflare** (the 01 §2, the bandwidth + the WAF + the DDoS (the 01 §2, the 28 §3.1)) | The per-GB + the flat (the 01 §2, the 22 §3.1's meter (the 22 §3.1)) | The tenant (the 22 §3.4, the 27 Part C.1's PLT-03) | The pass-through (the 22 §3.4) |
| **The providers** (the Veriff (the 13 §12), the NOWPayments (the 11 §12), the Match2Pay/Interkasa (the 12 §12), the Postmark (the 14 §12), the ipinfo (the 02 §3.6)) | The per-use (the 13 §12 / the 11 §12 / the 12 §12 / the 14 §12, the 22 §3.1's meter (the 22 §3.1)) | The tenant (the 22 §3.4, the 27 Part C.1's PLT-03) | The pass-through (the 22 §3.4) |
| **The V3-late compute** (the 29's V3 line, the 06 §3.3's off-peak): the backtest (the 27 Part B §11), the paper (the 27 Part B §11), the ML (the 10 §12), the BigQuery (the 19 §3.5) | The platform's (the 06 §3.3, the 27 Part C.1's PLT-02 (the 27 Part C.1 §2), the 29 doc's budget (the §1.3)) | The platform (the 22 §14, the 27 Part C.1's PLT-03) | The platform's cost (the 22 §14, the no-pass-through (the 22 §3.4's posture: the V3-late compute is the platform's investment (the 22 §14), the tenant's benefit (the 27 Part B's TRD (the 27 Part B §1), the 10's RSK-ML (the 10 §12), the 19's BigQuery (the 19 §3.5))) |

## 6. The scalability's assurance (the test, the drill,
the review — the 28 §11's class)

- **The load-test** (the 06's CI, the 01 §2's GitHub
  Actions, the V2-target (the 00 §5), the 2× (the
  §1.2)): the k6-class (the 01 §2's register-
  consistent OSS, the 06's CI, the monthly (the
  06's calendar, the 27 Part C.1's PLT-02 (the
  27 Part C.1 §2))), the scope: the GW (the 04
  §3, the 2k rps (the 00 §5), the 08's poll
  (the 08 §3.2, the 167 req/s (the 08 §3.2,
  the §1.3)), the 04's relay (the 04 §5.4,
  the 2k msg/s (the 00 §5)), the 09's
  verdict (the 09 §1, the 1k/s (the 00 §5)),
  the SSE (the 01 §4.3, the 500 (the 00
  §5)), the webhook (the 04 §5.6, the
  50-endpoint (the 00 §5)), the exit:
  the p95 (the 04 §6's class, the 06
  §3.4's Grafana (the 06 §3.4), the no-
  error (the 04 §6's posture, the 06
  §3.3's incident (the 06 §3.3))).
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

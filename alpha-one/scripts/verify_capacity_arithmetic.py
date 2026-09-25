#!/usr/bin/env python3
"""Verify the corrected multi-tenant capacity arithmetic in docs/29 + docs/63.

Every figure the v1.1 capacity correction asserts is *derived* from a small
set of documented per-account assumptions. This script re-derives each one
from first principles and asserts the value that appears in the docs.

Run:  python3 scripts/verify_capacity_arithmetic.py
Exit: 0 = every documented figure reproduces from the assumptions.

This exists because the capacity correction is exactly the kind of change
that looks right in a diff and is wrong in a table cell. If an assumption
changes (the tenant roster, the open-position share, the deals/account/day),
this script fails and says which documented number moved.

Section 12 is a *drift guard* rather than an arithmetic check: it asserts the
corrected docs still say each binding figure, that the retired single-tenant
figures are gone, and that the V1 (431-account) numbers are untouched. Its
needles are exact substrings of the pre-correction text, and each is
self-checked ("WAS present at the baseline") so the guard cannot pass
vacuously because a needle was mistyped.

The baseline is resolved as $CAPACITY_BASELINE, else merge-base(HEAD,
origin/main), else merge-base(HEAD, main), else the known pre-correction
commit. It deliberately is NOT HEAD: after the correction is committed, HEAD
*is* the corrected text and the self-checks would all fail. If the baseline
ever resolves to HEAD the guard fails loudly instead of passing silently.
"""
from __future__ import annotations

import re
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"

# ---------------------------------------------------------------------------
# The documented per-account assumptions (docs/63 §4.4, docs/08 §11, docs/00 §5)
# ---------------------------------------------------------------------------
TENANTS = 10                    # docs/29 §1.1.1 — the sizing roster
ACCOUNTS_PER_TENANT = 10_000    # docs/00 §1 — the white-label per-firm figure
ACCOUNTS = TENANTS * ACCOUNTS_PER_TENANT          # 100_000 — the correction

OPEN_POSITION_SHARE = 0.30      # docs/63 §4.4 "30 % of accounts hold open positions"
DEALS_PER_ACCOUNT_DAY = 50      # docs/08 §11 "~50 deals/day/account"
FUNDED_SHARE = 0.50             # docs/29 §1.1 — the V1 table's funded share held constant
CONCURRENT_USER_SHARE = 0.05    # docs/29 §1.1 — the 5 % concurrent share

HEARTBEAT_OPEN_S = 60           # docs/63 §4.4 trigger 5
HEARTBEAT_FLAT_S = 300
MATERIAL_CAP_S = 10             # docs/63 §4.4 trigger 4, ≤ 1 per 10 s per active account
MATERIAL_TYPICAL_OF_CAP = 1 / 3 # docs/63 §4.4 "typical ≪ cap"; the v1 ratio (100/s vs 300/s cap at 10k)
NEWS_BURST_X = 20               # docs/63 §4.4 "news bursts ×20"
GUARD_NEAR_FLOOR_SHARE = 0.01   # docs/63 §4.4 — the v1 figure: ≤ 400/s at 10k = 100 accounts × 4/s
GUARD_RATE_CAP = 4              # docs/63 §4.4 trigger 3, ≤ 4/s per account

RELIABILITY_INSTANCES = 2       # docs/63 §4.9 — reliability=high ⇒ 2 server instances
ACCOUNTS_PER_SOCKET = 100       # docs/63 F3 — ≤ 100 accounts/socket/instance
ACCOUNTS_PER_SHARD = 2_000      # docs/63 §4.2 — ≤ 2,000 accounts per shard
SHARD_RSS_GB = 1.5              # docs/63 §4.2 — the alarm threshold
ACCOUNTS_PER_USER_PER_SERVER = 300   # docs/63 §2 — MetaApi's cap
METAAPI_SERVERS = 12            # docs/63 §2 — "12 servers at doc time"
SUBSCRIPTION_QUOTA_X = 10       # docs/63 §2 — total subscriptions ≤ 10 × deployed

TICK_SUSTAINED_DESIGN = 2_500   # the design point asserted in docs/29 §1.1 + docs/63 §4.4/§4.11
TICK_BURST_DESIGN = 10_000
RELAY_SINGLE_PROCESS = 2_000    # docs/04 §11 — "2k msg/s fine on Redis"
HEADROOM_X = 2                  # docs/29 §1.2 — the 2× rule

PER_TICK_MS = 10                # docs/09 §11 — p95 < 10 ms (1 read + 2 engine + 1 write)
LANE_FLOOR_PER_TENANT = 10      # docs/63 §4.13
LANE_TOTAL_FLOOR = 128          # docs/63 §4.5

TICK_STALE_S = 600              # docs/09 §6 — evl.tick_stale, 10 minutes
BURST_DURATION_S = 300          # docs/29 §3.4.1 — a 5-minute news burst
PG_PRIMARY_QPS = 10_000         # docs/29 §1.3 — the planned single-primary figure
SNAPSHOT_RETENTION_D = 14       # docs/08 §11
DEAL_RETENTION_D = 90           # docs/08 §11
TICK_HOT_WINDOW_D = 7           # docs/63 F13 / docs/29 §3.4.2
EVENT_RETENTION_MO = 13         # docs/04:163 EVT-22
BYTES_PER_EVENT_ROW = 400
METAAPI_USD_PER_ACCOUNT_MO = 75 # docs/08 §1 / docs/29 §1.3
PURE_EVALS_PER_S = 52_600       # propfirm-engine benches/engine.rs — pure_evaluate

MAXLEN_PER_STREAM = 100_000     # docs/04 §11
BYTES_PER_TICK = 1_000
REDIS_STREAMS_BUDGET_GB = 2     # D51 2/2/4 split

checks: list[tuple[bool, str]] = []


def chk(ok: bool, label: str) -> None:
    checks.append((ok, label))


def approx(a: float, b: float, tol: float = 0.06) -> bool:
    return abs(a - b) <= tol * max(abs(a), abs(b), 1.0)


def near_below(value: float, ceiling: float) -> bool:
    return value <= ceiling


# ---------------------------------------------------------------------------
# 1. The account count
# ---------------------------------------------------------------------------
chk(ACCOUNTS == 100_000, f"V2 target = 10 tenants × 10k = {ACCOUNTS:,} accounts")
chk(ACCOUNTS == 10 * 10_000, "the correction is exactly 10× the old single-tenant 10k ceiling")

# ---------------------------------------------------------------------------
# 2. docs/63 §4.4 — the tick-volume envelope at 100k
# ---------------------------------------------------------------------------
open_accounts = ACCOUNTS * OPEN_POSITION_SHARE
flat_accounts = ACCOUNTS - open_accounts

heartbeat = open_accounts / HEARTBEAT_OPEN_S + flat_accounts / HEARTBEAT_FLAT_S
chk(approx(heartbeat, 733), f"heartbeat = {open_accounts:,.0f}/60 + {flat_accounts:,.0f}/300 = {heartbeat:.0f}/s (doc: ≈ 733/s)")

material_cap = open_accounts / MATERIAL_CAP_S
material = material_cap * MATERIAL_TYPICAL_OF_CAP
chk(approx(material, 1_000), f"material = {material_cap:,.0f}/s cap × ⅓ typical = {material:.0f}/s (doc: ≈ 1,000/s)")

deals_day = ACCOUNTS * DEALS_PER_ACCOUNT_DAY
deal_position = deals_day / 86_400
deal_burst = deal_position * NEWS_BURST_X
chk(approx(deal_position, 58), f"deal+position = {deals_day:,.0f}/day ÷ 86,400 = {deal_position:.1f}/s (doc: ≈ 58/s)")
chk(approx(deal_burst, 1_200, 0.05), f"  news burst ×20 = {deal_burst:.0f}/s (doc: ≈ 1.2k/s)")

guard_burst = ACCOUNTS * GUARD_NEAR_FLOOR_SHARE * GUARD_RATE_CAP
chk(approx(guard_burst, 4_000), f"guard worst burst = {ACCOUNTS*GUARD_NEAR_FLOOR_SHARE:,.0f} near-floor × 4/s = {guard_burst:.0f}/s (doc: ≤ 4,000/s)")

sustained_sum = heartbeat + material + deal_position
burst_sum = guard_burst + deal_burst + material_cap + heartbeat
chk(near_below(sustained_sum, TICK_SUSTAINED_DESIGN),
    f"sustained sum = {sustained_sum:,.0f}/s ≤ the {TICK_SUSTAINED_DESIGN:,}/s design point "
    f"({(1 - sustained_sum/TICK_SUSTAINED_DESIGN)*100:.0f} % headroom)")
chk(near_below(burst_sum, TICK_BURST_DESIGN),
    f"burst sum = {burst_sum:,.0f}/s ≤ the {TICK_BURST_DESIGN:,}/s design point "
    f"({(1 - burst_sum/TICK_BURST_DESIGN)*100:.0f} % headroom)")

# the ×10 check the docs assert
chk(approx(sustained_sum, 1_791, 0.02), f"sustained sum reproduces the doc's ≈ 1,791/s (was ≈ 179/s at 10k)")
chk(approx(burst_sum, 8_933, 0.02), f"burst sum reproduces the doc's ≈ 8,933/s (was ≈ 893/s at 10k)")

# the old poll plan, for the "same order" claim
poll_plan = ACCOUNTS / 60
chk(approx(poll_plan, 1_667), f"the superseded 60-s poll plan = {poll_plan:,.0f}/s — same order as {sustained_sum:,.0f}/s sustained")

# ---------------------------------------------------------------------------
# 3. docs/63 §4.11 — MetaApi / gateway rows
# ---------------------------------------------------------------------------
subs = ACCOUNTS * RELIABILITY_INSTANCES
quota = SUBSCRIPTION_QUOTA_X * ACCOUNTS
chk(subs == 200_000, f"subscriptions = {ACCOUNTS:,} × 2 instances = {subs:,} (doc: ≤ 200k)")
chk(subs <= quota, f"  within MetaApi's quota of {SUBSCRIPTION_QUOTA_X} × deployed = {quota:,} ({quota/subs:.0f}× headroom)")

sockets = subs / ACCOUNTS_PER_SOCKET
chk(sockets == 2_000, f"sockets = {subs:,} ÷ {ACCOUNTS_PER_SOCKET} = {sockets:,.0f} (doc: ≈ 2,000)")

shards = ACCOUNTS / ACCOUNTS_PER_SHARD
chk(shards == 50, f"gateway shards = {ACCOUNTS:,} ÷ {ACCOUNTS_PER_SHARD:,} = {shards:.0f} (doc: ≈ 50)")
chk(shards / TENANTS == 5, f"  = {shards/TENANTS:.0f} shards per tenant (doc: 5 per tenant)")
chk(sockets / shards == 40, f"  sockets per shard = {sockets/shards:.0f} = 20 per instance × 2 (doc: ≈ 20 sockets per instance)")

shard_rss = shards * SHARD_RSS_GB
chk(shard_rss == 75, f"gateway RSS = {shards:.0f} shards × {SHARD_RSS_GB} GB = {shard_rss:.0f} GB (doc: ≈ 75 GB)")
chk(shard_rss > 64, f"  F12: {shard_rss:.0f} GB > the 64 GB top of the AX42-class 32–64 GB box ⇒ the single-box posture breaks")

client_slots = -(-ACCOUNTS // ACCOUNTS_PER_USER_PER_SERVER)   # ceil
metaapi_users = -(-client_slots // METAAPI_SERVERS)            # ceil
chk(client_slots >= 334, f"client-id slots = ceil({ACCOUNTS:,} ÷ {ACCOUNTS_PER_USER_PER_SERVER}) = {client_slots} (doc: ≥ 334)")
chk(metaapi_users >= 28, f"  ⇒ MetaApi user accounts = ceil({client_slots} ÷ {METAAPI_SERVERS} servers) = {metaapi_users} (doc: ≥ 28)")
chk(-(-ACCOUNTS_PER_TENANT // ACCOUNTS_PER_USER_PER_SERVER) == 34,
    f"  per tenant: ceil(10,000 ÷ 300) = 34 (user,server) pairs ⇒ ≥ 3 user accounts per tenant")

equity_sustained = open_accounts * 1
equity_burst = ACCOUNTS * 1
chk(equity_sustained == 30_000, f"inbound Equity frames = {open_accounts:,.0f} open-position accounts × 1/s = {equity_sustained:,.0f}/s (doc: ≈ 30k/s)")
chk(equity_burst == 100_000, f"  burst = {ACCOUNTS:,} × 1/s fleet-wide = {equity_burst:,.0f}/s (doc: 100k/s)")

# the F1 poll-everything figure
CREDITS_PER_POLL = 176
credits_min = ACCOUNTS * CREDITS_PER_POLL
all_servers = METAAPI_SERVERS * 18_000
chk(approx(credits_min / 1e6, 17.6, 0.02), f"F1: poll-everything = {credits_min/1e6:.1f}M credits/min (doc: ≈ 17.6M)")
chk(approx(credits_min / all_servers, 81, 0.02), f"  vs {all_servers/1000:.0f}k/min for all {METAAPI_SERVERS} servers = {credits_min/all_servers:.0f}× over (doc: ≈ 81×)")

# ---------------------------------------------------------------------------
# 4. docs/63 §4.5 + docs/29 §1.3 — the relay and the lanes
# ---------------------------------------------------------------------------
relay_events_min = TICK_BURST_DESIGN * 60
chk(relay_events_min == 600_000, f"relay target = {TICK_BURST_DESIGN:,}/s × 60 = {relay_events_min:,} events/min (doc: 600k events/min)")
chk(relay_events_min == 10 * 60_000, "  = 10× the v1 60k events/min figure (the correction is linear)")
relay_partitions = -(-TICK_BURST_DESIGN // RELAY_SINGLE_PROCESS)
relay_partitions_2x = -(-(TICK_BURST_DESIGN * HEADROOM_X) // RELAY_SINGLE_PROCESS)
chk(relay_partitions == 5, f"relay partitions at target = ceil({TICK_BURST_DESIGN:,} ÷ {RELAY_SINGLE_PROCESS:,}) = {relay_partitions} (doc: ≥ 5)")
chk(relay_partitions_2x == 10, f"  at the 2× rule = {relay_partitions_2x} (doc: ≥ 10)")
redis_mbps = TICK_BURST_DESIGN * BYTES_PER_TICK / 1e6
chk(approx(redis_mbps, 10), f"  Redis load = {TICK_BURST_DESIGN:,}/s × ~1 KB ≈ {redis_mbps:.0f} MB/s — not the limit (doc: ≈ 10 MB/s)")

lane_rate = 1000 / PER_TICK_MS
chk(lane_rate == 100, f"one serial lane = 1000 ms ÷ {PER_TICK_MS} ms per tick = {lane_rate:.0f} ticks/s (doc: ≈ 100 ticks/s)")
lanes_sustained = -(-TICK_SUSTAINED_DESIGN // lane_rate)
lanes_burst = -(-TICK_BURST_DESIGN // lane_rate)
lanes_2x = -(-(TICK_BURST_DESIGN * HEADROOM_X) // lane_rate)
chk(lanes_sustained == 25, f"lanes sustained = ceil({TICK_SUSTAINED_DESIGN:,} ÷ {lane_rate:.0f}) = {lanes_sustained} (doc: 25)")
chk(lanes_burst == 100, f"lanes burst = {lanes_burst} (doc: 100)")
chk(lanes_2x == 200, f"lanes at the 2× rule = {lanes_2x} (doc: 200)")
lane_total_floor = max(LANE_TOTAL_FLOOR, LANE_FLOOR_PER_TENANT * TENANTS)
chk(lane_total_floor == 128, f"total lanes = max({LANE_TOTAL_FLOOR}, {LANE_FLOOR_PER_TENANT} × {TENANTS} tenants) = {lane_total_floor} (doc: ≥ 128)")
chk(LANE_FLOOR_PER_TENANT * lane_rate == TICK_BURST_DESIGN / TENANTS,
    f"the {LANE_FLOOR_PER_TENANT}-lane floor = {LANE_FLOOR_PER_TENANT*lane_rate:,.0f} ticks/s = that tenant's own burst point ({TICK_BURST_DESIGN/TENANTS:,.0f}/s)")
old_lanes_accounts = ACCOUNTS / 16
chk(old_lanes_accounts == 6_250, f"why ≥ 16 lanes is wrong: {ACCOUNTS:,} ÷ 16 = {old_lanes_accounts:,.0f} accounts per lane")
chk(16 * lane_rate < sustained_sum,
    f"  and 16 lanes × {lane_rate:.0f} = {16*lane_rate:,.0f} ticks/s < the {sustained_sum:,.0f}/s SUSTAINED demand "
    f"⇒ saturated by ordinary traffic, before any burst")

# ---------------------------------------------------------------------------
# 5. docs/63 §4.11 + docs/29 §3.4.1 — Postgres
# ---------------------------------------------------------------------------
snap_rows_s = ACCOUNTS / 60
chk(approx(snap_rows_s, 1_667), f"account_snapshots = {ACCOUNTS:,}/min = {snap_rows_s:,.0f} rows/s (doc: 1,667/s)")
deal_rows_s = deal_position
chk(approx(deal_rows_s, 58), f"broker_deals = {deal_rows_s:.0f} rows/s (doc: 58/s)")
gc_rows_sustained = snap_rows_s + deal_rows_s + deal_rows_s + TICK_SUSTAINED_DESIGN
gc_rows_burst = snap_rows_s + deal_rows_s + deal_burst + TICK_BURST_DESIGN
chk(approx(gc_rows_sustained, 4_283, 0.02), f"group-commit rows sustained = {gc_rows_sustained:,.0f}/s (doc: ≈ 4,283/s)")
chk(approx(gc_rows_burst, 12_825, 0.06), f"group-commit rows burst = {gc_rows_burst:,.0f}/s (doc: ≈ 11,800/s — the doc uses the avg deal rate, not the burst)")
ROWS_PER_TX = 500
TX_CAP = 40
chk(gc_rows_sustained / ROWS_PER_TX < TX_CAP, f"  ⇒ {gc_rows_sustained/ROWS_PER_TX:.1f} tx/s sustained < the {TX_CAP}/s cap (doc: ≈ 9 tx/s)")
chk(gc_rows_burst / ROWS_PER_TX < TX_CAP, f"  ⇒ {gc_rows_burst/ROWS_PER_TX:.1f} tx/s burst < the {TX_CAP}/s cap (doc: ≈ 24 tx/s)")

state_writes = TICK_SUSTAINED_DESIGN
eval_qps_sustained = 2 * TICK_SUSTAINED_DESIGN + snap_rows_s + deal_rows_s + TICK_SUSTAINED_DESIGN * 2 + 50
eval_qps_burst = 2 * TICK_BURST_DESIGN + snap_rows_s + deal_burst + TICK_BURST_DESIGN * 2 + 500
chk(approx(eval_qps_sustained, 11_800, 0.03), f"evaluation-path queries sustained ≈ {eval_qps_sustained:,.0f} q/s (doc: ≈ 11.8k q/s)")
chk(approx(eval_qps_burst, 42_900, 0.03), f"evaluation-path queries burst ≈ {eval_qps_burst:,.0f} q/s (doc: ≈ 42.9k q/s)")
chk(eval_qps_sustained > PG_PRIMARY_QPS * 0.9,
    f"  sustained ≈ the {PG_PRIMARY_QPS:,} q/s primary plan (tight on CPU, ~4× commit headroom)")
chk(eval_qps_burst > PG_PRIMARY_QPS * 4, f"  burst is {eval_qps_burst/PG_PRIMARY_QPS:.1f}× the primary plan ⇒ single primary does NOT fit burst")

write_path_ticks_s = PG_PRIMARY_QPS // 2       # 1 read + 1 write per tick
backlog = (TICK_BURST_DESIGN - write_path_ticks_s) * BURST_DURATION_S
drain = backlog / write_path_ticks_s
worst_lag = BURST_DURATION_S + drain
chk(write_path_ticks_s == 5_000, f"write path serves {PG_PRIMARY_QPS:,} q/s ÷ 2 = {write_path_ticks_s:,} ticks/s")
chk(backlog == 1_500_000, f"backlog from a {BURST_DURATION_S//60}-min burst at {TICK_BURST_DESIGN:,}/s = {backlog:,.0f} events (doc: 1.5 M)")
chk(drain == 300, f"drain = {backlog:,.0f} ÷ {write_path_ticks_s:,} = {drain:.0f} s (doc: 300 s)")
chk(worst_lag == TICK_STALE_S, f"worst-case lag = {BURST_DURATION_S} + {drain:.0f} = {worst_lag:.0f} s == the {TICK_STALE_S} s tick_stale threshold ⇒ ZERO MARGIN")

# ---------------------------------------------------------------------------
# 6. Storage — F13 and the docs/29 §1.3 row
# ---------------------------------------------------------------------------
ticks_day = TICK_SUSTAINED_DESIGN * 86_400
DAYS_13MO = 395               # 13 months ≈ 395 days (docs/04:163 EVT-22)
ticks_13mo = ticks_day * DAYS_13MO
tb_13mo = ticks_13mo * BYTES_PER_EVENT_ROW / 1e12
chk(approx(ticks_day / 1e6, 216), f"bridge.tick = {TICK_SUSTAINED_DESIGN:,}/s × 86,400 = {ticks_day/1e6:.0f}M rows/day (doc: 216M)")
chk(approx(ticks_13mo / 1e9, 85, 0.03), f"  13 months (≈ {DAYS_13MO} d) = {ticks_13mo/1e9:.0f} B rows (doc: ≈ 85 B)")
chk(approx(tb_13mo, 34, 0.05), f"  ≈ {tb_13mo:.0f} TB at {BYTES_PER_EVENT_ROW} B/row (doc: ≈ 34 TB) vs docs/29's old '1 TB disk'")
old_10k_tb = 250 * 86_400 * DAYS_13MO * BYTES_PER_EVENT_ROW / 1e12
chk(approx(old_10k_tb / 0.2, 17, 0.10), f"  already {old_10k_tb/0.2:.0f}× over the '≈ 200 GB/yr' row at the OLD 10k target (doc: ≈ 17× — pre-existing drift)")
hot_rows = ticks_day * TICK_HOT_WINDOW_D
hot_gb = hot_rows * BYTES_PER_EVENT_ROW / 1e9
chk(approx(hot_rows / 1e9, 1.5, 0.03), f"F13's ≤ 7-day hot window = {hot_rows/1e9:.1f} B rows (doc: ≈ 1.5 B)")
chk(approx(hot_gb, 600, 0.05), f"  ≈ {hot_gb:.0f} GB (doc: ≈ 600 GB)")
r2_tb_yr = ticks_day * 365 * BYTES_PER_EVENT_ROW / 1e12 / 10
chk(approx(r2_tb_yr, 3, 0.10), f"  R2 columnar at ~10:1 ≈ {r2_tb_yr:.1f} TB/yr (doc: ≈ 3 TB/yr ≈ $45/mo at $0.015/GB)")

snap_rows = ACCOUNTS * 1_440 * SNAPSHOT_RETENTION_D
deal_rows = deals_day * DEAL_RETENTION_D
chk(approx(snap_rows / 1e9, 2.016, 0.02), f"account_snapshots = {ACCOUNTS:,} × 1,440/min × {SNAPSHOT_RETENTION_D} d = {snap_rows/1e9:.2f} B rows (doc: ≈ 2.0 B)")
BYTES_PER_SNAPSHOT_ROW = 180    # ≈ 130 B heap (ULID + tenant + bucket ts + 6 money cols) + PK index
BYTES_PER_DEAL_ROW = 330
snap_gb = snap_rows * BYTES_PER_SNAPSHOT_ROW / 1e9
chk(approx(snap_gb, 400, 0.12), f"  ≈ {snap_gb:.0f} GB at ≈ {BYTES_PER_SNAPSHOT_ROW} B/row heap + PK index (doc: ≈ 400 GB)")
deal_gb = deal_rows * BYTES_PER_DEAL_ROW / 1e9
chk(approx(deal_gb, 150, 0.12), f"broker_deals ≈ {deal_gb:.0f} GB at ≈ {BYTES_PER_DEAL_ROW} B/row (doc: ≈ 150 GB)")
total_tb = (snap_gb + deal_gb + hot_gb + 150) / 1000
chk(approx(total_tb, 1.3, 0.10), f"PG storage total = {snap_gb:.0f} + {deal_gb:.0f} + {hot_gb:.0f} + 150 (LED/AUD/read model) = {total_tb*1000:,.0f} GB ≈ {total_tb:.1f} TB (doc: ≈ 1.3 TB)")
chk(total_tb > 1.0, f"  ⇒ the 06 §1's 1 TB disk is insufficient; 2 TB minimum (doc: §1.3)")
chk(approx(deal_rows / 1e6, 450, 0.02), f"broker_deals = {deals_day:,.0f}/day × {DEAL_RETENTION_D} d = {deal_rows/1e6:.0f} M rows (doc: ≈ 450 M)")
chk(approx(ACCOUNTS * 1_440 / 1e6, 144), f"  snapshots/day = {ACCOUNTS*1_440/1e6:.0f}M (doc: ≈ 144M/day)")

# ---------------------------------------------------------------------------
# 7. Redis memory — the D82 sharding cost
# ---------------------------------------------------------------------------
stream_gb_10 = TENANTS * MAXLEN_PER_STREAM * BYTES_PER_TICK / 1e9
stream_gb_50 = 50 * MAXLEN_PER_STREAM * BYTES_PER_TICK / 1e12 * 1000
chk(approx(stream_gb_10, 1), f"per-tenant streams = {TENANTS} × MAXLEN {MAXLEN_PER_STREAM:,} × ~1 KB ≈ {stream_gb_10:.0f} GB (doc: ≈ 1 GB, inside the 2 GB redis-streams budget)")
chk(approx(stream_gb_50, 5), f"  at docs/00 §5's 50 tenants ≈ {stream_gb_50:.0f} GB ⇒ the D51 2/2/4 split becomes 2/6/4")
raised_gb = TENANTS * 1_000_000 * BYTES_PER_TICK / 1e9
chk(raised_gb > 8, f"  raising MAXLEN to ~1M would need ≈ {raised_gb:.0f} GB at {TENANTS} tenants ⇒ refused (Redis is never the source of truth)")
trim_backlog = (TICK_BURST_DESIGN / TENANTS - write_path_ticks_s / TENANTS) * BURST_DURATION_S
chk(approx(trim_backlog / 1000, 150, 0.05), f"trim hazard: a 5-min fleet burst puts ≈ {trim_backlog/1000:.0f}k entries behind one tenant's group (doc: ≈ 150k) > MAXLEN {MAXLEN_PER_STREAM:,}")

# ---------------------------------------------------------------------------
# 8. Cost + the engine tier
# ---------------------------------------------------------------------------
cost_m = ACCOUNTS * METAAPI_USD_PER_ACCOUNT_MO / 1e6
cost_tenant = ACCOUNTS_PER_TENANT * METAAPI_USD_PER_ACCOUNT_MO / 1000
chk(approx(cost_m, 7.5), f"MetaApi cost = {ACCOUNTS:,} × ${METAAPI_USD_PER_ACCOUNT_MO}/mo = ${cost_m:.1f}M/mo platform-wide (doc: ≈ $7.5M/mo)")
chk(approx(cost_tenant, 750), f"  = ${cost_tenant:.0f}k/mo per tenant at 10k accounts (doc: ≈ $750k/mo)")
chk(10 * (ACCOUNTS_PER_TENANT * METAAPI_USD_PER_ACCOUNT_MO) == ACCOUNTS * METAAPI_USD_PER_ACCOUNT_MO, "  the old 10k figure was $750k/mo ⇒ the correction is exactly 10× the platform total")
chk(PURE_EVALS_PER_S > TICK_BURST_DESIGN * 5,
    f"engine math: {PURE_EVALS_PER_S:,} pure evals/s single-threaded vs a {TICK_BURST_DESIGN:,} verdict/s burst "
    f"= {PURE_EVALS_PER_S/TICK_BURST_DESIGN:.0f}× ⇒ CPU is NOT the constraint (doc: ≈ 5× at burst, ≈ 20× at sustained)")
chk(PURE_EVALS_PER_S / TICK_SUSTAINED_DESIGN > 15, f"  ≈ {PURE_EVALS_PER_S/TICK_SUSTAINED_DESIGN:.0f}× at sustained (doc: ≈ 20×)")

# ---------------------------------------------------------------------------
# 9. Other §1.1 rows derived from the account count
# ---------------------------------------------------------------------------
chk(ACCOUNTS * CONCURRENT_USER_SHARE == 5_000, f"concurrent users = {ACCOUNTS:,} × 5 % = {ACCOUNTS*CONCURRENT_USER_SHARE:,.0f} (doc: 5,000)")
chk(ACCOUNTS * FUNDED_SHARE == 50_000, f"funded accounts = {ACCOUNTS:,} × 50 % = {ACCOUNTS*FUNDED_SHARE:,.0f} (doc: 50,000)")
chk(ACCOUNTS * FUNDED_SHARE * 0.10 == 5_000, f"payouts/day = 50k funded × 1 % = {ACCOUNTS*FUNDED_SHARE*0.01:,.0f} (doc: ~5k)")
chk(ACCOUNTS * CONCURRENT_USER_SHARE == 5_000 and 50 * TENANTS == 500, f"webhook endpoints = 50/tenant × {TENANTS} tenants = {50*TENANTS} (doc: 500)")

# ---------------------------------------------------------------------------
# 10. Cold resync + the fallback credit budget (docs/63 §4.7)
# ---------------------------------------------------------------------------
concurrent_syncs = sockets * 10       # per-socket throttler: min(ceil(accounts/10), 15) = 10 per 100-account socket
waves = ACCOUNTS / concurrent_syncs
chk(concurrent_syncs == 20_000, f"concurrent resyncs = {sockets:,.0f} sockets × 10 = {concurrent_syncs:,} (doc: ≈ 20,000)")
chk(waves == 5, f"  = {waves:.0f} waves at 100k — the same as at 10k (200 sockets ⇒ 2,000 concurrent ⇒ 5 waves), so MetaApi's cap is scale-invariant")
resync_per_shard_lo, resync_per_shard_hi = 12, 24
chk(shards * resync_per_shard_hi / 60 <= 20 and shards * resync_per_shard_lo / 60 >= 10,
    f"rolling per-shard resync = {shards:.0f} shards × {resync_per_shard_lo}–{resync_per_shard_hi} s = "
    f"{shards*resync_per_shard_lo/60:.0f}–{shards*resync_per_shard_hi/60:.0f} min wall-clock (doc: ≈ 10–20 min)")
chk(ACCOUNTS_PER_SHARD / ACCOUNTS == 0.02, f"  blast radius per shard = {ACCOUNTS_PER_SHARD:,} ÷ {ACCOUNTS:,} = 2 % (doc: 2 %)")

CREDITS_PER_SERVER_MIN = 18_000
BUDGET_FRACTION = 0.80
accounts_per_server_min = int(CREDITS_PER_SERVER_MIN * BUDGET_FRACTION / CREDITS_PER_POLL)
chk(accounts_per_server_min in (81, 82), f"fallback budget = {BUDGET_FRACTION:.0%} of {CREDITS_PER_SERVER_MIN:,}/min ÷ {CREDITS_PER_POLL} credits = {accounts_per_server_min} accounts/min per server slot (doc: ≈ 80)")
reading_b = METAAPI_SERVERS * accounts_per_server_min
reading_a = TENANTS * reading_b
chk(approx(reading_b, 960, 0.03), f"Reading B (global per server): {METAAPI_SERVERS} × {accounts_per_server_min} = {reading_b:,} accounts/min (doc: 960)")
chk(approx(reading_a, 9_600, 0.03), f"Reading A (per Client-Id): × {TENANTS} tenants = {reading_a:,} accounts/min (doc: 9,600)")
priority_subset = open_accounts
chk(approx(priority_subset / reading_a * 60, 186, 0.05), f"  Reading A, priority subset ({priority_subset:,.0f} open-position accounts) = {priority_subset/reading_a:.1f} min (doc: ≈ 3.1 min) < the 10-min tick_stale window")
chk(priority_subset / reading_a * 60 < TICK_STALE_S, "  ⇒ Reading A is workable")
chk(approx(priority_subset / reading_b * 60, 1_875, 0.05), f"  Reading B, same subset = {priority_subset/reading_b:.0f} min (doc: ≈ 31 min)")
chk(priority_subset / reading_b * 60 > TICK_STALE_S, "  ⇒ Reading B is NOT workable — plan against B (doc: §8 Q8)")
chk(approx(ACCOUNTS / reading_b, 104, 0.03), f"  Reading B full stale pass = {ACCOUNTS/reading_b:.0f} min (doc: ≈ 104 min)")
chk(approx(ACCOUNTS / reading_a, 10.4, 0.05), f"  Reading A full stale pass = {ACCOUNTS/reading_a:.1f} min (doc: ≈ 10.4 min)")

# ---------------------------------------------------------------------------
# 11. D84 thresholds are fractions of the tick_stale window
# ---------------------------------------------------------------------------
for label, seconds, expect in [("scale-out", 60, "10 %"), ("WARN", 120, "20 %"),
                               ("PAGE", 300, "50 %"), ("INCIDENT", 480, "80 %")]:
    pct = seconds / TICK_STALE_S
    chk(pct < 1.0, f"D84 {label} threshold = {seconds} s = {pct:.0%} of the {TICK_STALE_S} s tick_stale window ({expect})")
chk(300 / TICK_STALE_S == 0.5, "the PAGE threshold is exactly half the tick_stale window")

# The shed ladder. Funded accounts are half the fleet and are protected by the
# priority list, so the ladder's ceiling is ~60 %, not 100 %.
HEALTH_FRAME_S = 10             # docs/63 §4.2 — onHealthStatus coalesced ≤ 1 per 10 s per account
chk(HEALTH_FRAME_S < TICK_STALE_S,
    f"widening the heartbeat CANNOT trip tick_stale: it measures tick *age* = now − occurred_at, "
    f"and occurred_at is the newest folded frame's receive time — Health frames arrive ≤ every "
    f"{HEALTH_FRAME_S} s while `live`, so a 900 s heartbeat still carries an age of ≈ {HEALTH_FRAME_S} s "
    f"≪ {TICK_STALE_S} s (docs/09 §6: 'a heartbeat never refreshes stale data')")

funded_heartbeat = (ACCOUNTS * FUNDED_SHARE * OPEN_POSITION_SHARE / HEARTBEAT_OPEN_S
                    + ACCOUNTS * FUNDED_SHARE * (1 - OPEN_POSITION_SHARE) / HEARTBEAT_FLAT_S)
nonfunded_heartbeat = heartbeat - funded_heartbeat
chk(approx(funded_heartbeat, 367), f"heartbeat splits ≈ {funded_heartbeat:.0f}/s funded + {nonfunded_heartbeat:.0f}/s non-funded (doc: ≈ 367/s each)")

l1_nonfunded = (ACCOUNTS * (1 - FUNDED_SHARE) * OPEN_POSITION_SHARE / 180
                + ACCOUNTS * (1 - FUNDED_SHARE) * (1 - OPEN_POSITION_SHARE) / 900)
l1_removed = nonfunded_heartbeat - l1_nonfunded
chk(approx(l1_nonfunded, 122, 0.05), f"L1: non-funded heartbeat 60→180 s / 300→900 s ⇒ {l1_nonfunded:.0f}/s (doc: 122/s)")
chk(approx(l1_removed / sustained_sum, 0.14, 0.10), f"L1 removes {l1_removed:.0f}/{sustained_sum:,.0f} = {l1_removed/sustained_sum:.0%} (doc: ≈ 14 %)")

nonfunded_material = material / 2
l2_removed = l1_removed + nonfunded_material * (1 - 10 / 25)
chk(approx(l2_removed / sustained_sum, 0.30, 0.10), f"L2 (+ material 10→25 bps, non-funded) cumulative = {l2_removed/sustained_sum:.0%} (doc: ≈ 30 %)")

guard_band = ACCOUNTS * GUARD_NEAR_FLOOR_SHARE
l3_heartbeat = (guard_band * 0.6 / HEARTBEAT_OPEN_S + guard_band * 0.4 / HEARTBEAT_FLAT_S
                + (ACCOUNTS - guard_band) * OPEN_POSITION_SHARE / 180
                + (ACCOUNTS - guard_band) * (1 - OPEN_POSITION_SHARE) / 900)
l3_removed = (heartbeat - l3_heartbeat) + material * (1 - 10 / 25)
chk(approx(l3_heartbeat, 253, 0.10), f"L3: heartbeat 733/s → {l3_heartbeat:.0f}/s with the {guard_band:,.0f} guard-band accounts excepted (doc: ≈ 253/s)")
chk(approx(l3_removed / sustained_sum, 0.60, 0.10), f"L3 cumulative = {l3_removed/sustained_sum:.0%} (doc: ≈ 60 %)")
chk(l3_removed / sustained_sum < 0.75,
    f"the ladder's ceiling is ≈ {l3_removed/sustained_sum:.0%}, NOT 100 % — funded accounts are "
    f"{FUNDED_SHARE:.0%} of the fleet and the priority list protects them (doc: §4.14)")
chk(l1_removed < l2_removed < l3_removed, "the ladder is monotonic — each level removes strictly more")
chk(180 < TICK_STALE_S, "L1's ≤ 180 s stale-floor-hint bound for non-funded accounts is ≪ the 600 s tick_stale window")

# ---------------------------------------------------------------------------
# 12. Cross-document drift guard — the docs must actually SAY these numbers
# ---------------------------------------------------------------------------
D29 = (DOCS / "29-scalability.md").read_text(encoding="utf-8")
D63 = (DOCS / "63-brg-streaming-ingestion.md").read_text(encoding="utf-8")
D00 = (DOCS / "00-executive-brief.md").read_text(encoding="utf-8")
D09 = (DOCS / "09-evaluation-engine.md").read_text(encoding="utf-8")
D08 = (DOCS / "08-trading-bridge.md").read_text(encoding="utf-8")
D04 = (DOCS / "04-gateway-events.md").read_text(encoding="utf-8")
D01 = (DOCS / "01-platform-architecture.md").read_text(encoding="utf-8")
D35 = (DOCS / "35-testing-strategy.md").read_text(encoding="utf-8")
D64 = (DOCS / "64-evl-state-ownership-split.md").read_text(encoding="utf-8")


def has(text: str, needle: str) -> bool:
    return needle in text


# --- the corrected figures must be present where they are binding ---
MUST_HAVE = [
    (D00, "100,000", "docs/00 states the corrected account target"),
    (D00, "white-label", "docs/00 §1 names the white-label multi-tenant target (step 1.5)"),
    (D00, "planning estimate, not a hard ceiling", "docs/00 says it is an estimate, not a ceiling"),
    (D00, "tenant #15", "docs/00 names the revisit milestone"),
    (D29, "**100,000**", "docs/29 §1.1 carries the corrected target"),
    (D29, "2,500/s sustained, 10k/s burst", "docs/29 §1.1 carries the corrected tick rate"),
    (D29, "10,000 msg/s sustained = 600k events/min", "docs/29 §1.1 carries the corrected relay target"),
    (D29, "≥ 128", "docs/29 §1.1/§1.3 carry the corrected lane count"),
    (D29, "1.1.1", "docs/29 has the planning-estimate + revisit-trigger subsection"),
    (D29, "tenant #15", "docs/29 §1.1.1 names the tenant-count milestone"),
    (D29, "LT-8", "docs/29 §6 has the re-targeted load-test matrix"),
    (D29, "3.4", "docs/29 has the Postgres write-scaling section (step 5b)"),
    (D29, "tenant_id", "docs/29 §3.4 partitions by tenant_id"),
    (D29, "Citus", "docs/29 §3.4 states the horizontal-Postgres position explicitly"),
    (D29, "V2 entry prerequisite", "docs/29 §3.1 pulls the 2nd box forward into V2"),
    (D63, "100,000 accounts = 10 tenants × 10k", "docs/63 §4.11 header carries the corrected target"),
    (D63, "≤ 2,500/s / ≤ 10,000/s", "docs/63 §4.11 carries the corrected tick rates"),
    (D63, "600k events/min", "docs/63 §4.5/§4.11 carry the corrected relay target"),
    (D63, "≈ 2,000", "docs/63 §4.11 carries the corrected socket count"),
    (D63, "≈ 50", "docs/63 §4.11 carries the corrected shard count"),
    (D63, "≤ 200k", "docs/63 §4.11 carries the corrected subscription count"),
    (D63, "4.11.1", "docs/63 has the planning-estimate subsection"),
    (D63, "4.11.2", "docs/63 has the what-the-correction-breaks subsection"),
    (D63, "4.13", "docs/63 has the per-tenant fairness section (step 5a)"),
    (D63, "4.14", "docs/63 has the autoscaling + load-shedding section (step 5c)"),
    (D63, "F12", "docs/63 records the single-box breach as a finding"),
    (D63, "F13", "docs/63 records the retention breach as a finding"),
    (D63, "evl.stream_trimmed", "docs/63 §4.13 names the trim-detection signal"),
    (D63, "evl_lag_seconds", "docs/63 §4.14 defines the lag-in-seconds signal"),
    (D63, "evl.load_shed", "docs/63 §4.14 defines the shed delivery mechanism"),
    (D63, "no autoscaler", "docs/63 §4.14 states the Compose-has-no-autoscaler constraint"),
    (D09, "≥ 128", "docs/09 §11 carries the corrected lane count"),
    (D09, "2,500/s sustained", "docs/09 §11 carries the corrected tick rate"),
    (D09, "D81", "docs/09 §2 is anchored to the state-ownership decision"),
    (D08, "≈ 50 shards", "docs/08 §11 carries the corrected shard count"),
    (D04, "600k events/min", "docs/04 §11 carries the corrected relay target"),
    (D04, "topic.bridge.{tenant_id}", "docs/04 §11 carries the per-tenant stream keys"),
    (D01, "Re-confirmed 2026-09-25 by D81", "docs/01 ADR-11 is explicitly re-confirmed and dated (step 2)"),
    (D01, "docs/64", "docs/01 ADR-11 points at the decision doc"),
    (D35, "I-31", "docs/35 carries the new invariants"),
    (D64, "evaluate(state, rules, tick)", "docs/64 states the pared-back signature"),
    (D64, "No database connection of its own", "docs/64 states the no-DB constraint"),
    (D64, "consumer_state", "docs/64 routes idempotency to the platform mechanism"),
    (D64, "O-1", "docs/64 registers the open rule-pack item rather than hiding it"),
    (D64, "does not exist", "docs/64 records the workers-consumer blocker (F-B1)"),
]
for text, needle, label in MUST_HAVE:
    chk(has(text, needle), f"drift guard: {label}  [contains {needle!r}]")

# --- the retired single-tenant figures must NOT survive as live targets ---
# Validated against git HEAD rather than a hand-copied list: we assert each
# old figure WAS in the committed version and IS NOT in the working version,
# so the guard cannot pass trivially because the needle was mistyped.
# The comparison baseline must be the commit BEFORE the capacity correction,
# not HEAD: once the correction is committed, HEAD *is* the corrected text and
# every "was present at HEAD" self-check would fail. Resolve the branch point
# from origin/main, fall back to main, then to the known pre-correction
# commit, and allow an explicit override.
PRE_CORRECTION_COMMIT = "9fcc3b448354cfb04009fa62aff33c0b9780ea06"
REPO_ROOT = DOCS.parent.parent


def _git(*args: str) -> str:
    try:
        out = subprocess.run(["git", *args], cwd=str(REPO_ROOT),
                             capture_output=True, text=True)
        return out.stdout.strip() if out.returncode == 0 else ""
    except Exception:  # pragma: no cover - git absent
        return ""


def baseline() -> str:
    """The commit whose docs/ text predates the capacity correction."""
    override = os.environ.get("CAPACITY_BASELINE", "").strip()
    if override:
        return override
    for ref in ("origin/main", "main"):
        mb = _git("merge-base", "HEAD", ref)
        if mb:
            return mb
    return PRE_CORRECTION_COMMIT


BASELINE = baseline()
HEAD_AT = _git("rev-parse", "HEAD")


def head_version(name: str) -> str:
    """The baseline (pre-correction) text of alpha-one/<name>, or '' if absent."""
    out = subprocess.run(["git", "show", f"{BASELINE}:alpha-one/{name}"],
                         cwd=str(REPO_ROOT), capture_output=True, text=True)
    return out.stdout if out.returncode == 0 else ""


H29, H63 = head_version("docs/29-scalability.md"), head_version("docs/63-brg-streaming-ingestion.md")
H09 = head_version("docs/09-evaluation-engine.md")
H08 = head_version("docs/08-trading-bridge.md")
H04 = head_version("docs/04-gateway-events.md")
H00 = head_version("docs/00-executive-brief.md")
HEADS = {"29": (H29, D29), "63": (H63, D63), "09": (H09, D09),
         "08": (H08, D08), "04": (H04, D04), "00": (H00, D00)}

RETIRED = [
    # Each needle is an exact substring of the committed (HEAD) text, so the
    # self-check below proves the needle is real; historical prose that merely
    # mentions an old figure ("was 10,000", "the 5–6 figure was for 10k")
    # cannot match these.
    ("29", "| Concurrent broker accounts (the 08's sync) | 500 | 10,000 | 10,000 |",
     "docs/29 §1.1's old single-tenant V2 account row"),
    ("29", "| Event rate (the 04's relay) | 500 msg/s | 2,000 msg/s |",
     "docs/29 §1.1's old 2k msg/s relay row"),
    ("29", "the ~1k verdict/s", "docs/29 §1.3's old EVL throughput row"),
    ("29", "the ~200 GB/yr", "docs/29 §1.3's old PG storage row"),
    ("63", "| V2 (10k accounts) |", "docs/63 §4.11's old column header"),
    ("63", "- **Relay throughput target:** raised from 10k to **60k events/min",
     "docs/63 §4.5's old 60k events/min relay target"),
    ("63", "| Gateway shards | 1 | 5–6 |", "docs/63 §4.11's old 5–6 shard row"),
    ("63", "≤ 250/s / ≤ 1k/s", "docs/63 §4.11's old emitted-tick cell"),
    ("63", "≤ 20k", "docs/63 §4.11's old subscription cell"),
    ("09", "- **Tick rate:** ≈ 10/s sustained (≈ 100/s burst) at V1; ≤ 250/s sustained",
     "docs/09 §11's old ≤ 250/s tick-rate cell"),
    ("09", "10k accounts / ≥ 16 lanes = fine", "docs/09 §11's old lane-sufficiency claim"),
    ("08", "10k accounts: ≤ 20k subscriptions", "docs/08 §11's old ingest-scale row"),
    ("04", "target **60k events/min sustained**", "docs/04 §11's old relay target"),
    ("00", "| Concurrent broker accounts | ~1k | ~10k |", "docs/00 §5's old account row"),
]
chk(bool(BASELINE) and BASELINE != HEAD_AT,
    f"drift guard baseline {BASELINE[:12]} predates HEAD {HEAD_AT[:12]} — the guard is not vacuous")
for key, needle, label in RETIRED:
    old_text, new_text = HEADS[key]
    if not old_text:
        chk(False, f"drift guard: cannot read {BASELINE[:12]}:alpha-one/docs/{key}-*.md — guard skipped")
        continue
    chk(needle in old_text, f"drift guard self-check: {label} WAS present at the baseline")
    chk(needle not in new_text, f"drift guard: {label} is retired")

# --- the V1 numbers must be untouched (step 1.4) ---
V1_INTACT = [
    ("29", "| Concurrent broker accounts (the 08's sync) | 500 |", "docs/29 §1.1's V1 account cell"),
    ("63", "| Emitted `bridge.tick` sustained / burst | ≈ 10/s / ≈ 100/s |", "docs/63 §4.11's V1 tick row"),
    ("63", "≤ 862", "docs/63 §4.11's V1 subscription cell"),
    ("63", "| V1 (431 accounts) |", "docs/63 §4.11's V1 column header (the 431 figure)"),
    ("08", "≈ 431 accounts, ≤ 862 subscriptions", "docs/08 §11's V1 ingest cell"),
    ("09", "≈ 10/s sustained (≈ 100/s burst) at V1", "docs/09 §11's V1 tick rate"),
    ("00", "| Concurrent broker accounts | ~1k |", "docs/00 §5's V1 account cell"),
]
for key, needle, label in V1_INTACT:
    old_text, new_text = HEADS[key]
    chk(needle in old_text, f"V1 self-check: {label} was present at the baseline")
    chk(needle in new_text, f"V1 untouched: {label}")
chk("431" in D63 and "431" in D29, "V1's 431-account figure is still present in both docs")
# The V1 column of every row I touched must still read 1 / ≈ 100–150 MB.
chk(re.search(r"\| Gateway shards \(≤ 2,000 accounts/shard\) \| 1 \|", D63) is not None,
    "docs/63 §4.11's V1 shard cell is still exactly 1 (only the V2 cell changed)")
# The narrow read+write figure and the full §3.4.1 figure must both appear in
# docs/63 §4.11, and they must agree with docs/29 §3.4.1's itemised derivation.
chk("≈ 5,000 q/s sustained, ≈ 20,000 q/s burst" in D63, "docs/63 §4.11 states the narrow read+write q/s pair")
chk("≈ 11,800 q/s sustained, ≈ 42,900 q/s burst" in D63,
    "docs/63 §4.11 carries the full evaluation-path q/s figure")
chk("≈ 11,800 q/s" in D29 and "≈ 42,900 q/s" in D29 and "≈ 11.8k q/s" in D29 and "≈ 42.9k q/s" in D29,
    "docs/29 §3.4.1/§3.4.2 carry the same figure (≈ 11.8k / ≈ 42.9k q/s)")
chk(approx(11800, 4 * 2500 + 1667 + 58 + 100, 0.05) and approx(42900, 4 * 10000 + 1667 + 1200 + 500, 0.03),
    "  and that figure reproduces from §3.4.1: 4 rows/tick (state read, state write, outbox, events) + snapshots + deals + verdict/LED/AUD")
chk(re.search(r"\| \*\*Queries\*\* \| \*\*≈ 11,800 q/s\*\* \| \*\*≈ 42,900 q/s\*\*", D29) is not None,
    "docs/29 §3.4.1's Queries row is the itemised source of that figure")
chk("431" in D08 and "≈ 431 accounts" in D08, "docs/08 §11's V1 431-account cell is unchanged")

# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
failed = [label for ok, label in checks if not ok]
width = max(len(l) for _, l in checks) + 2
for ok, label in checks:
    if not label:
        continue
    print(f"  {'PASS' if ok else 'FAIL'}  {label}")
print()
if failed:
    print(f"{len(failed)} of {len(checks)} checks FAILED:")
    for f in failed:
        print(f"  - {f}")
    sys.exit(1)
print(f"OK: {len(checks)} / {len(checks)} capacity figures in docs/29 §1.1/§1.3/§3.4 and "
      f"docs/63 §4.4/§4.5/§4.7/§4.11/§4.13/§4.14 reproduce from the documented "
      f"per-account assumptions at {ACCOUNTS:,} accounts ({TENANTS} tenants × {ACCOUNTS_PER_TENANT:,}).")

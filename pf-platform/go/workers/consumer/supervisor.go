package consumer

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"log/slog"
	"math"
	"strconv"
	"strings"
	"sync"
	"sync/atomic"
	"time"

	"github.com/redis/go-redis/v9"
)

// StreamSpec is one stream the supervisor consumes and the size of the
// lane set that owns its entities. With D82 there is one stream per tenant
// (topic.bridge.{tenant_id}) and Lanes = that tenant's allocation.
type StreamSpec struct {
	Key    string
	Tenant string
	Lanes  int
}

// Supervisor runs a consumer (docs/04 §3.5) over a set of streams.
type Supervisor struct {
	Spec     Spec
	Redis    *redis.Client
	DB       *sql.DB
	Handler  Handler
	Instance string // this process's consumer name inside the group
	Metrics  *Metrics
	Log      *slog.Logger

	// EntityOf extracts the ordering key from a payload when the stream
	// entry has no `entity_id` field. Optional.
	EntityOf func(payload []byte) string
	// OnLag is called after each lag sample (every LagInterval) while the
	// stream is owned. Optional.
	OnLag func(st StreamSpec, lagEntries int64, lagSeconds float64)
	// OnTrim is called once per detected trim of undelivered entries, with
	// the last id the group had delivered and the first id still retained:
	// the lost entries lie strictly between them. Optional; EVL publishes
	// evl.stream_trimmed and replays the window from PG.
	OnTrim func(ctx context.Context, st StreamSpec, lastDelivered, firstRetained string)
	// OnRelease is called after this instance stops owning a stream (lease
	// lost, rebalanced away, or shutdown); per-stream series are already
	// deleted. EVL forgets the tenant's ladder gauges. Optional.
	OnRelease func(st StreamSpec)
	// LagInterval between lag samples. Default 5 s.
	LagInterval time.Duration
	// Fair, when set, admits handler calls through a weighted fair
	// in-flight budget shared by all streams this instance owns (weight =
	// the stream's lane count). Optional; see FairShare.
	Fair *FairShare
	// FairBudget, when > 0, is the group-wide in-flight budget: this
	// instance's FairShare cap is ceil(FairBudget / live instances),
	// re-derived on every membership heartbeat, so autoscaling does not
	// oversubscribe the shared PG primary. Creates Fair if nil.
	FairBudget int

	// Effective configuration, fixed once (initOnce): Run and the public
	// methods read these, never write the exported fields above, so
	// callers may read Spec/Metrics concurrently with Run.
	initOnce sync.Once
	spec     Spec
	lag      time.Duration
	m        *Metrics
	fair     *FairShare

	mu    sync.Mutex
	owned map[string]*ownedStream

	// Rebalancing (see membership): live instances in the group, streams
	// configured, leases held or reserved, last shed.
	live     atomic.Int64
	nstreams int
	nowned   int
	lastShed time.Time
}

type ownedStream struct {
	st    StreamSpec
	lanes []chan Message
	ctx   context.Context
	acks  atomic.Int64
}

func (s *Supervisor) log() *slog.Logger {
	if s.Log == nil {
		return slog.Default()
	}
	return s.Log
}

func (s *Supervisor) init() {
	s.initOnce.Do(func() {
		s.spec = s.Spec.WithDefaults()
		s.lag = s.LagInterval
		if s.lag == 0 {
			s.lag = 5 * time.Second
		}
		s.m = s.Metrics
		if s.m == nil {
			s.m = NewMetrics()
		}
		s.fair = s.Fair
		if s.FairBudget > 0 {
			if s.fair == nil {
				s.fair = &FairShare{Metrics: s.m}
			}
			s.fair.SetCap(s.FairBudget)
		}
	})
}

func (s *Supervisor) metrics() *Metrics {
	s.init()
	return s.m
}

// Run consumes every stream until ctx is cancelled. Each stream is
// consumed only while this instance holds its ownership lease.
func (s *Supervisor) Run(ctx context.Context, streams []StreamSpec) error {
	s.init()
	if s.spec.Name == "" || s.Instance == "" || s.Handler == nil || s.Redis == nil || s.DB == nil {
		return errors.New("consumer: Spec.Name, Instance, Handler, Redis and DB are required")
	}
	s.mu.Lock()
	if s.owned == nil {
		s.owned = map[string]*ownedStream{}
	}
	s.mu.Unlock()
	s.mu.Lock()
	s.nstreams = len(streams)
	s.mu.Unlock()
	s.live.Store(1)
	mctx, mcancel := context.WithCancel(context.Background())
	defer mcancel()
	s.heartbeat(ctx) // register before the first acquire attempt
	go s.membership(ctx, mctx)
	var wg sync.WaitGroup
	for _, st := range streams {
		if st.Lanes < 1 {
			st.Lanes = 1
		}
		wg.Add(1)
		go func(st StreamSpec) {
			defer wg.Done()
			s.own(ctx, st)
		}(st)
	}
	wg.Wait()
	return ctx.Err()
}

func (s *Supervisor) leaseKey(st StreamSpec) string {
	return "lease:" + s.spec.Group() + ":" + st.Key
}

var renewScript = redis.NewScript(`
if redis.call('GET', KEYS[1]) == ARGV[1] then
  return redis.call('PEXPIRE', KEYS[1], ARGV[2])
end
return 0`)

var releaseScript = redis.NewScript(`
if redis.call('GET', KEYS[1]) == ARGV[1] then
  return redis.call('DEL', KEYS[1])
end
return 0`)

// own loops: acquire the stream's lease, consume while held, release.
func (s *Supervisor) own(ctx context.Context, st StreamSpec) {
	lk := s.leaseKey(st)
	ttl := s.spec.LeaseTTL
	for ctx.Err() == nil {
		if !s.reserve() {
			// At or above this instance's fair share of streams: leave the
			// stream to an instance under target.
			s.metrics().Set("consumer_stream_owned", 0, "consumer", s.spec.Name, "tenant", st.Tenant, "instance", s.Instance)
			sleepCtx(ctx, ttl/3)
			continue
		}
		ok, err := s.Redis.SetNX(ctx, lk, s.Instance, ttl).Result()
		if err != nil || !ok {
			s.unreserve()
			s.metrics().Set("consumer_stream_owned", 0, "consumer", s.spec.Name, "tenant", st.Tenant, "instance", s.Instance)
			if err != nil && ctx.Err() == nil {
				s.log().Warn("consumer.lease_error", "stream", st.Key, "err", err)
			}
			sleepCtx(ctx, ttl/3)
			continue
		}
		s.metrics().Set("consumer_stream_owned", 1, "consumer", s.spec.Name, "tenant", st.Tenant, "instance", s.Instance)
		s.log().Info("consumer.lease_acquired", "consumer", s.spec.Name, "stream", st.Key, "instance", s.Instance)
		sctx, cancel := context.WithCancel(ctx)
		var shed atomic.Bool
		go func() {
			t := time.NewTicker(ttl / 3)
			defer t.Stop()
			for {
				select {
				case <-sctx.Done():
					return
				case <-t.C:
					if s.tryShed() {
						s.log().Info("consumer.rebalance_shed", "consumer", s.spec.Name, "stream", st.Key, "instance", s.Instance,
							"live", s.live.Load())
						s.metrics().Inc("consumer_rebalance_shed_total", "consumer", s.spec.Name, "tenant", st.Tenant)
						shed.Store(true)
						cancel()
						return
					}
					n, err := renewScript.Run(sctx, s.Redis, []string{lk}, s.Instance, ttl.Milliseconds()).Int()
					if err != nil && sctx.Err() == nil {
						s.log().Warn("consumer.lease_renew_error", "stream", st.Key, "err", err)
						continue // transient; the TTL still covers two more renew attempts
					}
					if err == nil && n == 0 {
						s.log().Warn("consumer.lease_lost", "stream", st.Key, "instance", s.Instance)
						s.metrics().Inc("consumer_lease_lost_total", "consumer", s.spec.Name, "tenant", st.Tenant)
						cancel()
						return
					}
				}
			}
		}()
		s.consume(sctx, st)
		cancel()
		rctx, rcancel := context.WithTimeout(context.Background(), 2*time.Second)
		_ = releaseScript.Run(rctx, s.Redis, []string{lk}, s.Instance).Err()
		rcancel()
		if !shed.Load() {
			s.unreserve() // tryShed already gave the slot back
		}
		s.metrics().Set("consumer_stream_owned", 0, "consumer", s.spec.Name, "tenant", st.Tenant, "instance", s.Instance)
		l := []string{"consumer", s.spec.Name, "tenant", st.Tenant}
		for _, g := range []string{"consumer_stream_lag_entries", "consumer_drain_rate", "consumer_lag_seconds"} {
			s.metrics().Delete(g, l...)
		}
		if s.OnRelease != nil {
			s.OnRelease(st)
		}
	}
}

// ---- lease rebalancing ----
//
// Without it, whichever instance starts first takes every stream lease and
// renews it forever: scaling out on lag (D84) would add pods that own
// nothing. Each instance heartbeats into members:{group}; target is
// ceil(streams / live). An instance never acquires past target and, when
// above it, sheds one stream per ttl/3 — the next owner XAUTOCLAIMs the
// PEL, so in-flight work is redelivered and consumer_state dedupes it.

func (s *Supervisor) membersKey() string { return "members:" + s.spec.Group() }

func (s *Supervisor) heartbeat(ctx context.Context) {
	ttl := s.spec.LeaseTTL
	now := time.Now()
	key := s.membersKey()
	pipe := s.Redis.TxPipeline()
	pipe.ZAdd(ctx, key, redis.Z{Score: float64(now.UnixMilli()), Member: s.Instance})
	pipe.ZRemRangeByScore(ctx, key, "-inf", fmt.Sprint(now.Add(-ttl).UnixMilli()))
	card := pipe.ZCard(ctx, key)
	pipe.PExpire(ctx, key, 10*ttl)
	if _, err := pipe.Exec(ctx); err != nil {
		if ctx.Err() == nil {
			s.log().Warn("consumer.membership_error", "err", err)
		}
		return // keep the last known count
	}
	if n := card.Val(); n > 0 {
		s.live.Store(n)
		if s.FairBudget > 0 {
			s.fair.SetCap((s.FairBudget + int(n) - 1) / int(n))
		}
		s.metrics().Set("consumer_live_instances", float64(n), "consumer", s.spec.Name, "instance", s.Instance)
	}
}

func (s *Supervisor) membership(ctx, stop context.Context) {
	t := time.NewTicker(s.spec.LeaseTTL / 3)
	defer t.Stop()
	for {
		select {
		case <-ctx.Done():
			rctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
			s.Redis.ZRem(rctx, s.membersKey(), s.Instance)
			cancel()
			return
		case <-stop.Done():
			return
		case <-t.C:
			s.heartbeat(ctx)
		}
	}
}

func (s *Supervisor) targetLocked() int {
	live := int(s.live.Load())
	if live < 1 {
		live = 1
	}
	return (s.nstreams + live - 1) / live
}

func (s *Supervisor) reserve() bool {
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.nowned >= s.targetLocked() {
		return false
	}
	s.nowned++
	return true
}

func (s *Supervisor) unreserve() {
	s.mu.Lock()
	s.nowned--
	s.mu.Unlock()
}

// tryShed reports whether the caller's stream should be released now to
// bring this instance back to target (at most one per ttl/3 per instance).
func (s *Supervisor) tryShed() bool {
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.nowned <= s.targetLocked() || time.Since(s.lastShed) < s.spec.LeaseTTL/3 {
		return false
	}
	s.lastShed = time.Now()
	s.nowned--
	return true
}

func (s *Supervisor) consume(ctx context.Context, st StreamSpec) {
	group := s.spec.Group()
	if err := s.Redis.XGroupCreateMkStream(ctx, st.Key, group, "0").Err(); err != nil &&
		!strings.Contains(err.Error(), "BUSYGROUP") {
		s.log().Error("consumer.group_create_failed", "stream", st.Key, "err", err)
		sleepCtx(ctx, time.Second)
		return
	}
	os := &ownedStream{st: st, ctx: ctx, lanes: make([]chan Message, st.Lanes)}
	var wg sync.WaitGroup
	for i := range os.lanes {
		os.lanes[i] = make(chan Message, s.spec.LaneQueue)
		wg.Add(1)
		go func(i int) {
			defer wg.Done()
			s.lane(ctx, os, os.lanes[i])
		}(i)
	}
	s.mu.Lock()
	s.owned[st.Key] = os
	s.mu.Unlock()
	defer func() {
		s.mu.Lock()
		delete(s.owned, st.Key)
		s.mu.Unlock()
		for _, ch := range os.lanes {
			close(ch)
		}
		wg.Wait()
	}()

	// Recovery: while we hold the lease every pending entry of the group is
	// ours to finish — claim them all, oldest first, before reading new ones.
	start := "0-0"
	for ctx.Err() == nil {
		msgs, next, err := s.Redis.XAutoClaim(ctx, &redis.XAutoClaimArgs{
			Stream: st.Key, Group: group, Consumer: s.Instance, MinIdle: 0, Start: start, Count: s.spec.ReadCount,
		}).Result()
		if err != nil {
			if ctx.Err() == nil {
				s.log().Warn("consumer.autoclaim_error", "stream", st.Key, "err", err)
			}
			break
		}
		for _, xm := range msgs {
			s.dispatch(ctx, os, xm)
		}
		if next == "0-0" || next == "" {
			break
		}
		start = next
	}

	go s.monitor(ctx, os)

	// Trim detection (D82). MAXLEN trimming (the relay's XADD MAXLEN ~) does
	// not move max-deleted-entry-id (only XDEL does), so detection uses the
	// Redis ≥ 7 counters: once the stream's first retained entry is beyond
	// what this group has delivered, the entries removed from the head that
	// the group never read are
	//
	//	lost = (entries-added − length) − group entries-read
	//
	// Checked before every batch is dispatched (one XINFO STREAM per
	// non-empty read; XINFO GROUPS only when the first entry is past `prev`),
	// because a periodic check races with the read that jumps the gap.
	prev := "0-0"
	if groups, err := s.Redis.XInfoGroups(ctx, st.Key).Result(); err == nil {
		for _, g := range groups {
			if g.Name == group {
				prev = g.LastDeliveredID
			}
		}
	}
	reported := ""
	checkTrim := func() {
		info, err := s.Redis.XInfoStream(ctx, st.Key).Result()
		if err != nil || info.FirstEntry.ID == "" || CompareIDs(info.FirstEntry.ID, prev) <= 0 ||
			info.FirstEntry.ID == reported {
			return
		}
		groups, err := s.Redis.XInfoGroups(ctx, st.Key).Result()
		if err != nil {
			return
		}
		for _, g := range groups {
			if g.Name != group {
				continue
			}
			lost := (info.EntriesAdded - info.Length) - g.EntriesRead
			if lost <= 0 {
				return
			}
			reported = info.FirstEntry.ID
			l := []string{"consumer", s.spec.Name, "tenant", st.Tenant}
			s.metrics().Inc("consumer_stream_trimmed_total", l...)
			s.metrics().Add("consumer_stream_trimmed_entries_total", float64(lost), l...)
			s.log().Error("consumer.stream_trimmed", "consumer", s.spec.Name, "stream", st.Key,
				"last_delivered", prev, "first_retained", info.FirstEntry.ID, "lost_entries", lost)
			if s.OnTrim != nil {
				s.OnTrim(ctx, st, prev, info.FirstEntry.ID)
			}
		}
	}
	checkTrim()

	for ctx.Err() == nil {
		res, err := s.Redis.XReadGroup(ctx, &redis.XReadGroupArgs{
			Group: group, Consumer: s.Instance, Streams: []string{st.Key, ">"},
			Count: s.spec.ReadCount, Block: s.spec.Block,
		}).Result()
		if errors.Is(err, redis.Nil) {
			continue
		}
		if err != nil {
			if ctx.Err() != nil {
				return
			}
			s.log().Warn("consumer.read_error", "stream", st.Key, "err", err)
			sleepCtx(ctx, time.Second)
			continue
		}
		checkTrim()
		for _, xs := range res {
			for _, xm := range xs.Messages {
				s.dispatch(ctx, os, xm)
				prev = xm.ID
			}
		}
	}
}

func field(xm redis.XMessage, k string) string {
	switch v := xm.Values[k].(type) {
	case string:
		return v
	case []byte:
		return string(v)
	case nil:
		return ""
	default:
		return fmt.Sprint(v)
	}
}

func (s *Supervisor) dispatch(ctx context.Context, os *ownedStream, xm redis.XMessage) {
	m := Message{
		Stream: os.st.Key, RedisID: xm.ID, Tenant: os.st.Tenant,
		EventID: field(xm, "event_id"), EntityID: field(xm, "entity_id"),
		Payload: []byte(field(xm, "payload")),
	}
	if m.EntityID == "" && s.EntityOf != nil {
		m.EntityID = s.EntityOf(m.Payload)
	}
	if m.EventID == "" || len(m.Payload) == 0 {
		// Unprocessable by construction: no idempotency key or no body.
		s.deadLetter(ctx, os, m, 1, errors.New("consumer: stream entry lacks event_id or payload"))
		return
	}
	s.enqueue(ctx, os, m)
}

func (s *Supervisor) enqueue(ctx context.Context, os *ownedStream, m Message) bool {
	m.Lane = LaneOf(m.EntityID, len(os.lanes))
	select {
	case os.lanes[m.Lane] <- m:
		s.metrics().Set("consumer_lane_queue_depth", float64(len(os.lanes[m.Lane])),
			"consumer", s.spec.Name, "tenant", os.st.Tenant, "lane", strconv.Itoa(m.Lane))
		return true
	case <-ctx.Done():
		return false
	}
}

// Inject routes a message (e.g. a PG replay after a trim) onto the lane
// that owns its entity, if this instance currently owns the stream. The
// message has no RedisID, so nothing is acked; consumer_state dedupes.
func (s *Supervisor) Inject(streamKey string, m Message) bool {
	s.mu.Lock()
	os := s.owned[streamKey]
	s.mu.Unlock()
	if os == nil {
		return false
	}
	m.Stream, m.RedisID, m.Tenant = streamKey, "", os.st.Tenant
	return s.enqueue(os.ctx, os, m)
}

func (s *Supervisor) lane(ctx context.Context, os *ownedStream, ch chan Message) {
	for m := range ch {
		if ctx.Err() != nil {
			continue // drain; unacked entries stay pending for the next owner
		}
		s.process(ctx, os, m)
	}
}

func (s *Supervisor) call(ctx context.Context, m Message) (err error) {
	defer func() {
		if r := recover(); r != nil {
			err = fmt.Errorf("consumer: handler panic: %v", r)
		}
	}()
	return s.Handler(ctx, m)
}

func (s *Supervisor) process(ctx context.Context, os *ownedStream, m Message) {
	labels := []string{"consumer", s.spec.Name, "tenant", os.st.Tenant}
	for attempt := 1; ; attempt++ {
		m.Attempt = attempt
		// Wait for a fair-share slot on the stream context only: the
		// handler timeout starts once the call is admitted, and only lease
		// loss or shutdown abandons the wait (the entry stays pending).
		release, ferr := s.fair.Acquire(ctx, os.st.Tenant, float64(os.st.Lanes))
		if ferr != nil {
			return
		}
		actx, cancel := context.WithTimeout(ctx, s.spec.Timeout)
		t0 := time.Now()
		err := s.call(actx, m)
		release()
		cancel()
		s.metrics().Observe("consumer_handler_seconds", time.Since(t0).Seconds(), labels...)
		if err == nil {
			s.ack(ctx, os, m)
			s.metrics().Inc("consumer_processed_total", labels...)
			return
		}
		if ctx.Err() != nil {
			return // lease lost or shutdown: leave it pending for the next owner
		}
		if IsPermanent(err) || attempt >= s.spec.MaxAttempts {
			s.deadLetter(ctx, os, m, attempt, err)
			return
		}
		s.metrics().Inc("consumer_retries_total", labels...)
		if rerr := RecordFailure(ctx, s.DB, s.spec.Name, m.EventID, attempt, err, false); rerr != nil {
			s.log().Warn("consumer.record_failure_error", "event_id", m.EventID, "err", rerr)
		}
		s.log().Warn("consumer.retry", "consumer", s.spec.Name, "event_id", m.EventID,
			"attempt", attempt, "backoff", s.spec.Backoff(attempt).String(), "err", err)
		if !sleepCtx(ctx, s.spec.Backoff(attempt)) {
			return
		}
	}
}

func (s *Supervisor) ack(ctx context.Context, os *ownedStream, m Message) {
	if m.RedisID == "" {
		return
	}
	if err := s.Redis.XAck(ctx, os.st.Key, s.spec.Group(), m.RedisID).Err(); err != nil {
		s.log().Warn("consumer.ack_error", "stream", os.st.Key, "id", m.RedisID, "err", err)
		return
	}
	os.acks.Add(1)
}

// deadLetter: XADD dlq.{name} with the original envelope, record `dead`
// in consumer_state, XACK. `relay dlq retry` re-publishes the envelope.
func (s *Supervisor) deadLetter(ctx context.Context, os *ownedStream, m Message, attempt int, cause error) {
	labels := []string{"consumer", s.spec.Name, "tenant", os.st.Tenant}
	err := s.Redis.XAdd(ctx, &redis.XAddArgs{Stream: s.spec.DLQ(), Values: map[string]any{
		"event_id": m.EventID, "consumer": s.spec.Name, "stream": os.st.Key, "tenant_id": os.st.Tenant,
		"entity_id": m.EntityID, "attempts": attempt, "error": cause.Error(), "payload": string(m.Payload),
		"permanent": IsPermanent(cause), "dead_at": time.Now().UTC().Format(time.RFC3339Nano),
	}}).Err()
	if err != nil {
		// Could not dead-letter: leave the entry pending (not acked) so it is
		// retried after the next ownership change rather than lost.
		s.log().Error("consumer.dlq_write_failed", "event_id", m.EventID, "err", err)
		return
	}
	if m.EventID != "" {
		if rerr := RecordFailure(ctx, s.DB, s.spec.Name, m.EventID, attempt, cause, true); rerr != nil {
			s.log().Warn("consumer.record_failure_error", "event_id", m.EventID, "err", rerr)
		}
	}
	s.metrics().Inc("consumer_dlq_total", labels...)
	s.log().Error("consumer.dead_lettered", "consumer", s.spec.Name, "event_id", m.EventID,
		"tenant", os.st.Tenant, "attempts", attempt, "permanent", IsPermanent(cause), "err", cause)
	s.ack(ctx, os, m)
}

// monitor samples lag (docs/63 §4.14: lag_entries from XINFO GROUPS,
// drain rate = EWMA of acks/s over ~60 s) and detects trims.
func (s *Supervisor) monitor(ctx context.Context, os *ownedStream) {
	t := time.NewTicker(s.lag)
	defer t.Stop()
	var ewma float64
	var lastAcks int64
	last := time.Now()
	started := last
	for {
		select {
		case <-ctx.Done():
			return
		case <-t.C:
		}
		now := time.Now()
		dt := now.Sub(last).Seconds()
		last = now
		acks := os.acks.Load()
		rate := float64(acks-lastAcks) / dt
		lastAcks = acks
		// Warm-up: until 60 s of history exist, use the plain average since
		// ownership began. A cold EWMA (τ = 60 s) starts near 0 and would
		// report lag ÷ ~0 — a false PAGE/INCIDENT on every restart.
		if elapsed := now.Sub(started).Seconds(); elapsed < 60 {
			ewma = float64(acks) / elapsed
		} else {
			alpha := 1 - math.Exp(-dt/60)
			ewma = alpha*rate + (1-alpha)*ewma
		}

		groups, err := s.Redis.XInfoGroups(ctx, os.st.Key).Result()
		if err != nil {
			continue
		}
		var g *redis.XInfoGroup
		for i := range groups {
			if groups[i].Name == s.spec.Group() {
				g = &groups[i]
			}
		}
		if g == nil {
			continue
		}
		info, infoErr := s.Redis.XInfoStream(ctx, os.st.Key).Result()
		lag := g.Lag
		if lag < 0 {
			lag = 0
		}
		// go-redis maps a NULL lag ("cannot be determined", which Redis
		// reports after trims/deletions) to 0. If entries exist beyond the
		// group's last-delivered id, fall back to XLEN as an upper bound.
		if lag == 0 && infoErr == nil && CompareIDs(info.LastGeneratedID, g.LastDeliveredID) > 0 {
			lag = info.Length
		}
		// In-flight (delivered, not yet acked) entries are still work
		// outstanding: count them, or a backed-up lane set would read as
		// zero lag once everything has been *delivered*.
		lag += g.Pending
		var lagSeconds float64
		switch {
		case lag == 0:
			lagSeconds = 0
		case ewma > 0.01:
			lagSeconds = float64(lag) / ewma
		default:
			// Nothing drained recently: fall back to the age of the oldest
			// outstanding entry (stream ids are ms timestamps).
			lagSeconds = s.oldestAge(ctx, os.st.Key, g)
		}
		l := []string{"consumer", s.spec.Name, "tenant", os.st.Tenant}
		s.metrics().Set("consumer_stream_lag_entries", float64(lag), l...)
		s.metrics().Set("consumer_drain_rate", ewma, l...)
		s.metrics().Set("consumer_lag_seconds", lagSeconds, l...)
		if s.OnLag != nil {
			s.OnLag(os.st, lag, lagSeconds)
		}

	}
}

func (s *Supervisor) oldestAge(ctx context.Context, key string, g *redis.XInfoGroup) float64 {
	id := ""
	if g.Pending > 0 {
		if p, err := s.Redis.XPending(ctx, key, g.Name).Result(); err == nil {
			id = p.Lower
		}
	}
	if id == "" {
		if xs, err := s.Redis.XRangeN(ctx, key, "("+g.LastDeliveredID, "+", 1).Result(); err == nil && len(xs) > 0 {
			id = xs[0].ID
		}
	}
	ms := IDMillis(id)
	if ms == 0 {
		return 0
	}
	return time.Since(time.UnixMilli(ms)).Seconds()
}

// IDMillis is the millisecond timestamp of a stream id ("ms-seq").
func IDMillis(id string) int64 {
	ms, _, _ := strings.Cut(id, "-")
	v, _ := strconv.ParseInt(ms, 10, 64)
	return v
}

// CompareIDs orders stream ids.
func CompareIDs(a, b string) int {
	am, as, _ := strings.Cut(a, "-")
	bm, bs, _ := strings.Cut(b, "-")
	ai, _ := strconv.ParseUint(am, 10, 64)
	bi, _ := strconv.ParseUint(bm, 10, 64)
	if ai != bi {
		if ai < bi {
			return -1
		}
		return 1
	}
	asq, _ := strconv.ParseUint(as, 10, 64)
	bsq, _ := strconv.ParseUint(bs, 10, 64)
	switch {
	case asq < bsq:
		return -1
	case asq > bsq:
		return 1
	}
	return 0
}

func sleepCtx(ctx context.Context, d time.Duration) bool {
	t := time.NewTimer(d)
	defer t.Stop()
	select {
	case <-ctx.Done():
		return false
	case <-t.C:
		return true
	}
}

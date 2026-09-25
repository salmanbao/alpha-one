package consumer_test

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"strings"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"github.com/redis/go-redis/v9"

	"pf-platform/go/workers/consumer"
	"pf-platform/go/workers/internal/testenv"
)

func TestSpecDefaultsAreDocs04(t *testing.T) {
	s := consumer.Spec{Name: "evaluation"}.WithDefaults()
	if s.MaxAttempts != 5 || s.BackoffBase != time.Second || s.Timeout != 30*time.Second {
		t.Fatalf("defaults drifted from docs/04 §3.5: %+v", s)
	}
	if s.Group() != "evaluation" || s.DLQ() != "dlq.evaluation" {
		t.Fatalf("group/dlq naming: %s %s", s.Group(), s.DLQ())
	}
	want := []time.Duration{time.Second, 2 * time.Second, 4 * time.Second, 8 * time.Second}
	for k, w := range want {
		if got := s.Backoff(k + 1); got != w {
			t.Fatalf("backoff after attempt %d = %v, want %v (1 s × 2^k)", k+1, got, w)
		}
	}
}

func TestLaneOfIsStableAndBounded(t *testing.T) {
	for n := 1; n < 200; n += 7 {
		for i := 0; i < 500; i++ {
			id := fmt.Sprintf("acct-%d", i)
			l := consumer.LaneOf(id, n)
			if l < 0 || l >= n || l != consumer.LaneOf(id, n) {
				t.Fatalf("LaneOf(%s,%d)=%d", id, n, l)
			}
		}
	}
}

// Consistent hashing: growing a lane set from n to n+1 moves ≈ 1/(n+1)
// of entities, not ≈ all of them (modulo hashing would move ≈ n/(n+1)).
func TestLaneOfMovesMinimalOnResize(t *testing.T) {
	const N, keys = 13, 20000
	moved := 0
	for i := 0; i < keys; i++ {
		id := fmt.Sprintf("acct-%d", i)
		if consumer.LaneOf(id, N) != consumer.LaneOf(id, N+1) {
			moved++
		}
	}
	frac := float64(moved) / keys
	if frac > 1.0/float64(N+1)*1.25 {
		t.Fatalf("moved %.3f of keys on %d→%d, want ≈ %.3f", frac, N, N+1, 1.0/float64(N+1))
	}
	t.Logf("resize %d→%d moved %.4f of %d keys (ideal %.4f)", N, N+1, frac, keys, 1.0/float64(N+1))
}

func TestAllocateLanesD82(t *testing.T) {
	equal := map[string]float64{}
	for i := 0; i < 10; i++ {
		equal[fmt.Sprintf("T%d", i)] = 1
	}
	for k, n := range consumer.AllocateLanes(equal) {
		if n != 13 { // ceil(128/10)
			t.Fatalf("equal weights: tenant %s got %d lanes, want 13", k, n)
		}
	}
	hot := map[string]float64{"A": 10}
	for i := 0; i < 9; i++ {
		hot[fmt.Sprintf("T%d", i)] = 1
	}
	got := consumer.AllocateLanes(hot)
	if got["A"] != 68 { // ceil(10/19 × 128)
		t.Fatalf("hot tenant lanes %d, want 68", got["A"])
	}
	for k, n := range got {
		if k != "A" && n != 10 { // max(10, ceil(1/19 × 128) = 7)
			t.Fatalf("small tenant %s lanes %d, want the floor of 10", k, n)
		}
	}
	if consumer.TotalLanes(10) != 128 || consumer.TotalLanes(20) != 200 {
		t.Fatal("TotalLanes = max(128, 10 × tenants)")
	}
}

// ---- integration (real Postgres + Redis) ----

func sideEffects(t *testing.T, db *sql.DB) {
	t.Helper()
	if _, err := db.Exec(`CREATE TABLE side_effects (event_id TEXT PRIMARY KEY, entity TEXT, seq INT, lane INT)`); err != nil {
		t.Fatal(err)
	}
}

func publish(t *testing.T, rdb *redis.Client, stream, eventID, entity string, payload string) {
	t.Helper()
	if err := rdb.XAdd(context.Background(), &redis.XAddArgs{Stream: stream, Values: map[string]any{
		"event_id": eventID, "entity_id": entity, "payload": payload,
	}}).Err(); err != nil {
		t.Fatal(err)
	}
}

func waitFor(t *testing.T, d time.Duration, what string, cond func() bool) {
	t.Helper()
	deadline := time.Now().Add(d)
	for time.Now().Before(deadline) {
		if cond() {
			return
		}
		time.Sleep(20 * time.Millisecond)
	}
	t.Fatalf("timed out waiting for %s", what)
}

func count(t *testing.T, db *sql.DB, q string, args ...any) int {
	t.Helper()
	var n int
	if err := db.QueryRow(q, args...).Scan(&n); err != nil {
		t.Fatal(err)
	}
	return n
}

func TestOnceCommitsExactlyOnceUnderConcurrency(t *testing.T) {
	db := testenv.PG(t)
	sideEffects(t, db)
	ev := testenv.ULID()
	var wg sync.WaitGroup
	var applied, dup atomic.Int64
	for i := 0; i < 20; i++ {
		wg.Add(1)
		go func(i int) {
			defer wg.Done()
			err := consumer.Once(context.Background(), db, "c", ev, consumer.StatusDone, func(tx *sql.Tx) error {
				_, err := tx.Exec(`INSERT INTO side_effects VALUES ($1, 'e', $2, 0) ON CONFLICT DO NOTHING`, ev, i)
				return err
			})
			switch {
			case err == nil:
				applied.Add(1)
			case errors.Is(err, consumer.ErrAlreadyProcessed):
				dup.Add(1)
			default:
				t.Error(err)
			}
		}(i)
	}
	wg.Wait()
	if applied.Load() != 1 || dup.Load() != 19 {
		t.Fatalf("applied=%d dup=%d, want 1/19", applied.Load(), dup.Load())
	}
}

func newSup(db *sql.DB, rdb *redis.Client, name, instance string, h consumer.Handler) *consumer.Supervisor {
	return &consumer.Supervisor{
		Spec:  consumer.Spec{Name: name, BackoffBase: 5 * time.Millisecond, Block: 100 * time.Millisecond, LeaseTTL: 900 * time.Millisecond},
		Redis: rdb, DB: db, Handler: h, Instance: instance, LagInterval: 100 * time.Millisecond, Metrics: consumer.NewMetrics(),
	}
}

// At-least-once + idempotent = effectively-once: the same event_id
// delivered twice produces one side effect and both entries are acked.
func TestRedeliveryProducesOneSideEffect(t *testing.T) {
	db, rdb := testenv.PG(t), testenv.Redis(t)
	sideEffects(t, db)
	name, stream := "c_"+testenv.ULID(), "s_"+testenv.ULID()
	h := func(ctx context.Context, m consumer.Message) error {
		err := consumer.Once(ctx, db, name, m.EventID, consumer.StatusDone, func(tx *sql.Tx) error {
			_, err := tx.Exec(`INSERT INTO side_effects VALUES ($1, $2, 0, $3)`, m.EventID, m.EntityID, m.Lane)
			return err
		})
		if errors.Is(err, consumer.ErrAlreadyProcessed) {
			return nil
		}
		return err
	}
	ev := testenv.ULID()
	publish(t, rdb, stream, ev, "acct-1", "{}")
	publish(t, rdb, stream, ev, "acct-1", "{}")
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	sup := newSup(db, rdb, name, "i1", h)
	go sup.Run(ctx, []consumer.StreamSpec{{Key: stream, Tenant: "T", Lanes: 4}})
	waitFor(t, 5*time.Second, "both acked", func() bool {
		p, _ := rdb.XPending(ctx, stream, name).Result()
		return sup.Metrics != nil && sup.Metrics.SumCounter("consumer_processed_total") == 2 && p != nil && p.Count == 0
	})
	if n := count(t, db, `SELECT count(*) FROM side_effects`); n != 1 {
		t.Fatalf("side effects %d, want 1", n)
	}
}

func TestRetryThenSuccessRecordsAttempts(t *testing.T) {
	db, rdb := testenv.PG(t), testenv.Redis(t)
	name, stream := "c_"+testenv.ULID(), "s_"+testenv.ULID()
	var calls atomic.Int64
	h := func(ctx context.Context, m consumer.Message) error {
		if calls.Add(1) < 3 {
			return errors.New("transient")
		}
		return consumer.Once(ctx, db, name, m.EventID, consumer.StatusDone, nil)
	}
	ev := testenv.ULID()
	publish(t, rdb, stream, ev, "a", "{}")
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	sup := newSup(db, rdb, name, "i1", h)
	go sup.Run(ctx, []consumer.StreamSpec{{Key: stream, Tenant: "T", Lanes: 1}})
	waitFor(t, 5*time.Second, "processed", func() bool {
		return sup.Metrics != nil && sup.Metrics.SumCounter("consumer_processed_total") == 1
	})
	var status string
	var attempts int
	if err := db.QueryRow(`SELECT status, attempts FROM consumer_state WHERE consumer=$1 AND event_id=$2`, name, ev).
		Scan(&status, &attempts); err != nil {
		t.Fatal(err)
	}
	if status != "done" || attempts != 3 || calls.Load() != 3 {
		t.Fatalf("status=%s attempts=%d calls=%d, want done/3/3", status, attempts, calls.Load())
	}
	if n := sup.Metrics.SumCounter("consumer_retries_total"); n != 2 {
		t.Fatalf("retries %v, want 2", n)
	}
}

func dlqEntries(t *testing.T, rdb *redis.Client, dlq, ev string) []redis.XMessage {
	t.Helper()
	xs, err := rdb.XRange(context.Background(), dlq, "-", "+").Result()
	if err != nil {
		t.Fatal(err)
	}
	var out []redis.XMessage
	for _, x := range xs {
		if x.Values["event_id"] == ev {
			out = append(out, x)
		}
	}
	return out
}

func TestPermanentErrorDeadLettersOnFirstAttempt(t *testing.T) {
	db, rdb := testenv.PG(t), testenv.Redis(t)
	name, stream := "c_"+testenv.ULID(), "s_"+testenv.ULID()
	var calls atomic.Int64
	h := func(ctx context.Context, m consumer.Message) error {
		calls.Add(1)
		return consumer.Permanent(errors.New("malformed"))
	}
	ev := testenv.ULID()
	publish(t, rdb, stream, ev, "a", `{"x":1}`)
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	sup := newSup(db, rdb, name, "i1", h)
	go sup.Run(ctx, []consumer.StreamSpec{{Key: stream, Tenant: "T", Lanes: 1}})
	waitFor(t, 5*time.Second, "dead-lettered", func() bool { return len(dlqEntries(t, rdb, "dlq."+name, ev)) == 1 })
	var status string
	var attempts int
	_ = db.QueryRow(`SELECT status, attempts FROM consumer_state WHERE consumer=$1 AND event_id=$2`, name, ev).Scan(&status, &attempts)
	e := dlqEntries(t, rdb, "dlq."+name, ev)[0]
	if status != "dead" || attempts != 1 || calls.Load() != 1 || e.Values["payload"] != `{"x":1}` || e.Values["permanent"] != "1" {
		t.Fatalf("status=%s attempts=%d calls=%d entry=%v", status, attempts, calls.Load(), e.Values)
	}
	waitFor(t, 2*time.Second, "acked", func() bool {
		p, _ := rdb.XPending(ctx, stream, name).Result()
		return p != nil && p.Count == 0
	})
}

func TestMaxAttemptsThenDeadLetter(t *testing.T) {
	db, rdb := testenv.PG(t), testenv.Redis(t)
	name, stream := "c_"+testenv.ULID(), "s_"+testenv.ULID()
	var calls atomic.Int64
	var times []time.Time
	var mu sync.Mutex
	h := func(ctx context.Context, m consumer.Message) error {
		calls.Add(1)
		mu.Lock()
		times = append(times, time.Now())
		mu.Unlock()
		return errors.New("always")
	}
	ev := testenv.ULID()
	publish(t, rdb, stream, ev, "a", "{}")
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	sup := newSup(db, rdb, name, "i1", h)
	sup.Spec.BackoffBase = 20 * time.Millisecond
	go sup.Run(ctx, []consumer.StreamSpec{{Key: stream, Tenant: "T", Lanes: 1}})
	waitFor(t, 5*time.Second, "dead-lettered", func() bool { return len(dlqEntries(t, rdb, "dlq."+name, ev)) == 1 })
	var status string
	var attempts int
	_ = db.QueryRow(`SELECT status, attempts FROM consumer_state WHERE consumer=$1 AND event_id=$2`, name, ev).Scan(&status, &attempts)
	if status != "dead" || attempts != 5 || calls.Load() != 5 {
		t.Fatalf("status=%s attempts=%d calls=%d, want dead/5/5", status, attempts, calls.Load())
	}
	// Backoff between attempts k and k+1 ≥ base × 2^(k-1): 20, 40, 80, 160 ms.
	for k := 1; k < len(times); k++ {
		gap := times[k].Sub(times[k-1])
		if min := 20 * time.Millisecond << (k - 1); gap < min {
			t.Fatalf("gap after attempt %d = %v < %v", k, gap, min)
		}
	}
}

// I-24: for any interleaving — two supervisor instances, redeliveries, and
// an ownership handover mid-run — no two handlers ever run concurrently for
// the same entity, each entity's events are processed in publish order, and
// every event's side effect commits exactly once.
func TestI24LaneExclusivityAcrossInstancesAndHandover(t *testing.T) {
	db, rdb := testenv.PG(t), testenv.Redis(t)
	sideEffects(t, db)
	name := "c_" + testenv.ULID()
	const streams, entities, perEntity = 4, 40, 25
	var inFlight sync.Map
	var violations atomic.Int64
	var mu sync.Mutex
	lastSeq := map[string]int{}
	var orderViolations atomic.Int64
	h := func(ctx context.Context, m consumer.Message) error {
		if _, busy := inFlight.LoadOrStore(m.EntityID, true); busy {
			violations.Add(1)
		}
		defer inFlight.Delete(m.EntityID)
		time.Sleep(time.Duration(len(m.EventID)%3) * time.Millisecond)
		var seq int
		fmt.Sscanf(string(m.Payload), `{"seq":%d}`, &seq)
		err := consumer.Once(ctx, db, name, m.EventID, consumer.StatusDone, func(tx *sql.Tx) error {
			_, err := tx.Exec(`INSERT INTO side_effects VALUES ($1, $2, $3, $4)`, m.EventID, m.EntityID, seq, m.Lane)
			return err
		})
		if errors.Is(err, consumer.ErrAlreadyProcessed) {
			return nil
		}
		if err == nil {
			mu.Lock()
			if seq <= lastSeq[m.EntityID] {
				orderViolations.Add(1)
			}
			lastSeq[m.EntityID] = seq
			mu.Unlock()
		}
		return err
	}
	var specs []consumer.StreamSpec
	for s := 0; s < streams; s++ {
		specs = append(specs, consumer.StreamSpec{Key: fmt.Sprintf("s_%s_%d", name, s), Tenant: fmt.Sprintf("T%d", s), Lanes: 5})
	}
	total := 0
	var redelivered []struct{ stream, ev, ent, payload string }
	for seq := 1; seq <= perEntity; seq++ {
		for e := 0; e < entities; e++ {
			st := specs[e%streams].Key
			ev, ent, payload := testenv.ULID(), fmt.Sprintf("acct-%d", e), fmt.Sprintf(`{"seq":%d}`, seq)
			publish(t, rdb, st, ev, ent, payload)
			total++
			if seq%10 == 0 {
				redelivered = append(redelivered, struct{ stream, ev, ent, payload string }{st, ev, ent, payload})
			}
		}
	}
	ctxA, cancelA := context.WithCancel(context.Background())
	ctxB, cancelB := context.WithCancel(context.Background())
	defer cancelB()
	supA := newSup(db, rdb, name, "A", h)
	supB := newSup(db, rdb, name, "B", h)
	doneA := make(chan struct{})
	go func() { supA.Run(ctxA, specs); close(doneA) }()
	go supB.Run(ctxB, specs)
	// Hand over: stop A after it has done some work; B takes its streams.
	waitFor(t, 20*time.Second, "some progress", func() bool {
		return count(t, db, `SELECT count(*) FROM side_effects`) > total/4
	})
	cancelA()
	<-doneA
	for _, r := range redelivered { // duplicate deliveries after the handover
		publish(t, rdb, r.stream, r.ev, r.ent, r.payload)
	}
	waitFor(t, 30*time.Second, "all processed", func() bool {
		return count(t, db, `SELECT count(*) FROM side_effects`) == total
	})
	waitFor(t, 10*time.Second, "all acked", func() bool {
		for _, s := range specs {
			p, _ := rdb.XPending(context.Background(), s.Key, name).Result()
			if p == nil || p.Count != 0 {
				return false
			}
		}
		return true
	})
	if violations.Load() != 0 || orderViolations.Load() != 0 {
		t.Fatalf("I-24 violated: concurrent-entity=%d out-of-order=%d", violations.Load(), orderViolations.Load())
	}
	if n := count(t, db, `SELECT count(*) FROM consumer_state WHERE consumer=$1 AND status='done'`, name); n != total {
		t.Fatalf("consumer_state done=%d, want %d", n, total)
	}
	t.Logf("I-24: %d events over %d entities, %d streams, 2 instances + handover, %d redeliveries: 0 concurrent, 0 reordered, %d side effects",
		total, entities, streams, len(redelivered), total)
}

func TestStreamOwnershipIsExclusive(t *testing.T) {
	db, rdb := testenv.PG(t), testenv.Redis(t)
	name, stream := "c_"+testenv.ULID(), "s_"+testenv.ULID()
	h := func(ctx context.Context, m consumer.Message) error { return nil }
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	a, b := newSup(db, rdb, name, "A", h), newSup(db, rdb, name, "B", h)
	go a.Run(ctx, []consumer.StreamSpec{{Key: stream, Tenant: "T", Lanes: 1}})
	go b.Run(ctx, []consumer.StreamSpec{{Key: stream, Tenant: "T", Lanes: 1}})
	time.Sleep(1500 * time.Millisecond)
	owned := a.Metrics.Gauge("consumer_stream_owned", "consumer", name, "tenant", "T", "instance", "A") +
		b.Metrics.Gauge("consumer_stream_owned", "consumer", name, "tenant", "T", "instance", "B")
	if owned != 1 {
		t.Fatalf("owners = %v, want exactly 1", owned)
	}
}

func TestTrimOfUndeliveredEntriesIsDetected(t *testing.T) {
	db, rdb := testenv.PG(t), testenv.Redis(t)
	name, stream := "c_"+testenv.ULID(), "s_"+testenv.ULID()
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	block := make(chan struct{})
	h := func(ctx context.Context, m consumer.Message) error {
		select {
		case <-block:
		case <-ctx.Done():
		}
		return nil
	}
	if err := rdb.XGroupCreateMkStream(ctx, stream, name, "0").Err(); err != nil {
		t.Fatal(err)
	}
	for i := 0; i < 50; i++ {
		publish(t, rdb, stream, testenv.ULID(), "a", "{}")
	}
	// Trim away entries the group has never been delivered.
	if err := rdb.XTrimMaxLen(ctx, stream, 5).Err(); err != nil {
		t.Fatal(err)
	}
	var trims atomic.Int64
	sup := newSup(db, rdb, name, "i1", h)
	sup.OnTrim = func(ctx context.Context, st consumer.StreamSpec, last, maxDel string) { trims.Add(1) }
	go sup.Run(ctx, []consumer.StreamSpec{{Key: stream, Tenant: "T", Lanes: 1}})
	defer close(block)
	waitFor(t, 5*time.Second, "trim detected", func() bool { return trims.Load() >= 1 })
	time.Sleep(300 * time.Millisecond)
	if trims.Load() != 1 {
		t.Fatalf("trim reported %d times, want once", trims.Load())
	}
}

func TestLagSecondsIsReportedUnderBacklog(t *testing.T) {
	db, rdb := testenv.PG(t), testenv.Redis(t)
	name, stream := "c_"+testenv.ULID(), "s_"+testenv.ULID()
	h := func(ctx context.Context, m consumer.Message) error {
		time.Sleep(20 * time.Millisecond)
		return nil
	}
	for i := 0; i < 400; i++ {
		publish(t, rdb, stream, testenv.ULID(), fmt.Sprint(i%3), "{}")
	}
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	var lastLag atomic.Value
	sup := newSup(db, rdb, name, "i1", h)
	sup.OnLag = func(st consumer.StreamSpec, entries int64, secs float64) {
		lastLag.Store([2]float64{float64(entries), secs})
	}
	go sup.Run(ctx, []consumer.StreamSpec{{Key: stream, Tenant: "T", Lanes: 3}})
	waitFor(t, 5*time.Second, "lag sample", func() bool {
		v, ok := lastLag.Load().([2]float64)
		return ok && v[0] > 0 && v[1] > 0
	})
	v := lastLag.Load().([2]float64)
	t.Logf("backlog sample: lag_entries=%.0f lag_seconds=%.2f", v[0], v[1])
}

// Trimming entries the group has already delivered and acked is routine
// (MAXLEN ~ retention) and must not be reported.
func TestTrimOfDeliveredEntriesIsNotReported(t *testing.T) {
	db, rdb := testenv.PG(t), testenv.Redis(t)
	name, stream := "c_"+testenv.ULID(), "s_"+testenv.ULID()
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	var trims atomic.Int64
	sup := newSup(db, rdb, name, "i1", func(ctx context.Context, m consumer.Message) error { return nil })
	sup.OnTrim = func(ctx context.Context, st consumer.StreamSpec, last, first string) { trims.Add(1) }
	go sup.Run(ctx, []consumer.StreamSpec{{Key: stream, Tenant: "T", Lanes: 1}})
	for i := 0; i < 30; i++ {
		publish(t, rdb, stream, testenv.ULID(), "a", "{}")
	}
	waitFor(t, 5*time.Second, "processed", func() bool { return sup.Metrics.SumCounter("consumer_processed_total") == 30 })
	if err := rdb.XTrimMaxLen(ctx, stream, 3).Err(); err != nil {
		t.Fatal(err)
	}
	for i := 0; i < 5; i++ {
		publish(t, rdb, stream, testenv.ULID(), "a", "{}")
	}
	waitFor(t, 5*time.Second, "processed", func() bool { return sup.Metrics.SumCounter("consumer_processed_total") == 35 })
	time.Sleep(300 * time.Millisecond)
	if trims.Load() != 0 {
		t.Fatalf("routine trim of delivered entries reported %d times", trims.Load())
	}
}

// Scale-out must move work: a second instance takes half the streams from
// the first (which started alone and owned them all); scale-in returns
// them. Without rebalancing, D84's "scale out on lag" adds idle pods.
func TestLeasesRebalanceOnScaleOutAndIn(t *testing.T) {
	db, rdb := testenv.PG(t), testenv.Redis(t)
	name := "c_" + testenv.ULID()
	var streams []consumer.StreamSpec
	for i := 0; i < 10; i++ {
		streams = append(streams, consumer.StreamSpec{Key: "s_" + testenv.ULID(), Tenant: fmt.Sprint("T", i), Lanes: 1})
	}
	noop := func(ctx context.Context, m consumer.Message) error { return nil }
	owned := func(s *consumer.Supervisor) int {
		n := 0
		for _, st := range streams {
			if v, _ := rdb.Get(context.Background(), "lease:"+s.Spec.Group()+":"+st.Key).Result(); v == s.Instance {
				n++
			}
		}
		return n
	}
	a := newSup(db, rdb, name, "a", noop)
	actx, acancel := context.WithCancel(context.Background())
	defer acancel()
	go a.Run(actx, streams)
	waitFor(t, 5*time.Second, "a owns all 10", func() bool { return owned(a) == 10 })

	b := newSup(db, rdb, name, "b", noop)
	bctx, bcancel := context.WithCancel(context.Background())
	t0 := time.Now()
	go b.Run(bctx, streams)
	waitFor(t, 15*time.Second, "5/5 split", func() bool { return owned(a) == 5 && owned(b) == 5 })
	t.Logf("scale-out 1→2: a=%d b=%d after %.1fs (lease ttl 0.9s)", owned(a), owned(b), time.Since(t0).Seconds())
	// The instance that shed streams must stop exporting their lag.
	time.Sleep(300 * time.Millisecond)
	for _, s := range []*consumer.Supervisor{a, b} {
		var sb strings.Builder
		_, _ = s.Metrics.WriteTo(&sb)
		if n := strings.Count(sb.String(), "\nconsumer_lag_seconds{"); n != 5 {
			t.Fatalf("instance %s exports consumer_lag_seconds for %d streams, owns 5", s.Instance, n)
		}
	}

	// Events keep flowing through the handover exactly once per stream owner.
	for _, st := range streams {
		publish(t, rdb, st.Key, testenv.ULID(), "e", "{}")
	}
	waitFor(t, 5*time.Second, "all processed", func() bool {
		return a.Metrics.SumCounter("consumer_processed_total")+b.Metrics.SumCounter("consumer_processed_total") == 10
	})

	bcancel()
	t1 := time.Now()
	waitFor(t, 15*time.Second, "a regains all 10", func() bool { return owned(a) == 10 })
	t.Logf("scale-in 2→1: a=%d after %.1fs", owned(a), time.Since(t1).Seconds())
}

package consumer

import (
	"context"
	"sync"
	"time"
)

// FairShare is weighted fair admission to a shared downstream (the PG
// primary, the engine) across the streams one Supervisor instance owns.
//
// Per-tenant streams and lane sets (D82) isolate *queues*: tenant A's
// backlog never sits in front of tenant B's ticks. They do not isolate the
// resources every lane shares. When A saturates its lanes, all in-flight
// handlers contend for the same database, and B–J's per-tick latency rises
// even though they never queue behind A. That is the LT-4 failure measured
// with evl-loadtest: B–J p95 34 → 176 ms at saturation.
//
// FairShare caps in-flight handler calls at Cap per instance (sized to
// what the downstream serves without queueing internally). When a slot
// frees, it goes to the waiting tenant with the lowest in-flight/weight
// ratio. A tenant under its share therefore waits for at most one slot
// release, however deep another tenant's backlog is. Idle share is
// borrowed: with nobody else waiting, one tenant may use every slot.
//
// Slots are held per handler attempt, not across retry backoff sleeps.
type FairShare struct {
	Cap     int
	Metrics *Metrics

	mu       sync.Mutex
	total    int
	inflight map[string]int
	weight   map[string]float64
	waiters  map[string][]waiter
	nwait    int
}

func (f *FairShare) init() {
	if f.inflight == nil {
		f.inflight, f.weight, f.waiters = map[string]int{}, map[string]float64{}, map[string][]waiter{}
	}
}

// Acquire blocks until tenant may start a handler call, or ctx ends.
// weight is the tenant's share (its lane count under D82). The returned
// release must be called exactly once.
func (f *FairShare) Acquire(ctx context.Context, tenant string, weight float64) (func(), error) {
	if f == nil {
		return func() {}, nil
	}
	if weight <= 0 {
		weight = 1
	}
	t0 := time.Now()
	f.mu.Lock()
	if f.Cap <= 0 { // disabled
		f.mu.Unlock()
		return func() {}, nil
	}
	f.init()
	f.weight[tenant] = weight
	if f.total < f.Cap && f.nwait == 0 {
		f.grantLocked(tenant)
		f.mu.Unlock()
		return f.releaser(tenant), nil
	}
	ch := make(chan struct{}, 1)
	f.waiters[tenant] = append(f.waiters[tenant], waiter{ch: ch, at: t0})
	f.nwait++
	f.mu.Unlock()

	select {
	case <-ch:
		f.observe(tenant, t0)
		return f.releaser(tenant), nil
	case <-ctx.Done():
		f.mu.Lock()
		q := f.waiters[tenant]
		for i, w := range q {
			if w.ch == ch {
				f.waiters[tenant] = append(q[:i:i], q[i+1:]...)
				f.nwait--
				f.mu.Unlock()
				return nil, ctx.Err()
			}
		}
		f.mu.Unlock()
		<-ch // granted concurrently with cancellation: hand the slot back
		f.releaser(tenant)()
		return nil, ctx.Err()
	}
}

func (f *FairShare) grantLocked(tenant string) {
	f.total++
	f.inflight[tenant]++
	if f.Metrics != nil {
		f.Metrics.Set("consumer_fair_inflight", float64(f.inflight[tenant]), "tenant", tenant)
	}
}

func (f *FairShare) observe(tenant string, t0 time.Time) {
	if f.Metrics != nil {
		f.Metrics.Observe("consumer_fair_wait_seconds", time.Since(t0).Seconds(), "tenant", tenant)
	}
}

func (f *FairShare) releaser(tenant string) func() {
	var once sync.Once
	return func() {
		once.Do(func() {
			f.mu.Lock()
			defer f.mu.Unlock()
			f.total--
			f.inflight[tenant]--
			if f.Metrics != nil {
				f.Metrics.Set("consumer_fair_inflight", float64(f.inflight[tenant]), "tenant", tenant)
			}
			f.dispatchLocked()
		})
	}
}

type waiter struct {
	ch chan struct{}
	at time.Time
}

// dispatchLocked hands free slots to waiters: lowest in-flight/weight
// first; ties go to the longest-waiting head (not to tenant id order,
// which with monotonic ULIDs would systematically favour older tenants).
func (f *FairShare) dispatchLocked() {
	for f.total < f.Cap && f.nwait > 0 {
		next, best := "", 0.0
		var bestAt time.Time
		for t, q := range f.waiters {
			if len(q) == 0 {
				continue
			}
			r := float64(f.inflight[t]+1) / f.weight[t]
			if next == "" || r < best || (r == best && q[0].at.Before(bestAt)) {
				next, best, bestAt = t, r, q[0].at
			}
		}
		w := f.waiters[next][0]
		f.waiters[next] = f.waiters[next][1:]
		f.nwait--
		f.grantLocked(next)
		w.ch <- struct{}{}
	}
}

// SetCap changes the in-flight cap (the Supervisor splits a group-wide
// budget across live instances). Raising it admits waiters at once;
// lowering it lets in-flight calls finish and admits no more until under.
func (f *FairShare) SetCap(n int) {
	if f == nil {
		return
	}
	if n < 1 {
		n = 1
	}
	f.mu.Lock()
	defer f.mu.Unlock()
	f.init()
	f.Cap = n
	if f.Metrics != nil {
		f.Metrics.Set("consumer_fair_cap", float64(n))
	}
	f.dispatchLocked()
}

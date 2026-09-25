package consumer_test

import (
	"context"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"pf-platform/go/workers/consumer"
)

func TestFairShareGrantsFreedSlotToTheTenantUnderShare(t *testing.T) {
	f := &consumer.FairShare{Cap: 2}
	ctx := context.Background()
	r1, _ := f.Acquire(ctx, "A", 13)
	r2, _ := f.Acquire(ctx, "A", 13)
	order := make(chan string, 10)
	var wg sync.WaitGroup
	for i := 0; i < 5; i++ { // A's backlog queues first
		wg.Add(1)
		go func() { defer wg.Done(); r, _ := f.Acquire(ctx, "A", 13); order <- "A"; r() }()
		time.Sleep(5 * time.Millisecond)
	}
	wg.Add(1)
	go func() {
		defer wg.Done()
		r, _ := f.Acquire(ctx, "B", 13)
		order <- "B"
		time.Sleep(20 * time.Millisecond)
		r()
	}()
	time.Sleep(10 * time.Millisecond)
	r1()
	if got := <-order; got != "B" {
		t.Fatalf("freed slot went to %s behind a 5-deep A backlog, want B", got)
	}
	r2()
	wg.Wait()
}

func TestFairShareHonoursCapAndBorrowsIdleShare(t *testing.T) {
	f := &consumer.FairShare{Cap: 4}
	var in, peak atomic.Int64
	var wg sync.WaitGroup
	for i := 0; i < 200; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			r, err := f.Acquire(context.Background(), "A", 1)
			if err != nil {
				t.Error(err)
				return
			}
			n := in.Add(1)
			for p := peak.Load(); n > p && !peak.CompareAndSwap(p, n); p = peak.Load() {
			}
			time.Sleep(time.Millisecond)
			in.Add(-1)
			r()
		}()
	}
	wg.Wait()
	if peak.Load() != 4 {
		t.Fatalf("peak in-flight %d, want exactly Cap=4 (cap honoured, idle share borrowed by the only tenant)", peak.Load())
	}
}

func TestFairShareCancelledWaiterLeaksNoSlot(t *testing.T) {
	f := &consumer.FairShare{Cap: 1}
	r, _ := f.Acquire(context.Background(), "A", 1)
	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Millisecond)
	defer cancel()
	if _, err := f.Acquire(ctx, "B", 1); err == nil {
		t.Fatal("want ctx error")
	}
	r()
	done := make(chan struct{})
	go func() { r2, _ := f.Acquire(context.Background(), "C", 1); r2(); close(done) }()
	select {
	case <-done:
	case <-time.After(time.Second):
		t.Fatal("slot leaked by the cancelled waiter")
	}
}

func TestFairShareTiesGoToLongestWaitingNotTenantOrder(t *testing.T) {
	f := &consumer.FairShare{Cap: 1}
	ctx := context.Background()
	r, _ := f.Acquire(ctx, "M", 1)
	got := make(chan string, 2)
	go func() { r, _ := f.Acquire(ctx, "Z", 1); got <- "Z"; r() }() // waits first
	time.Sleep(10 * time.Millisecond)
	go func() { r, _ := f.Acquire(ctx, "A", 1); got <- "A"; r() }()
	time.Sleep(10 * time.Millisecond)
	r()
	if first := <-got; first != "Z" {
		t.Fatalf("equal-ratio tie went to %s; want the longest-waiting tenant Z", first)
	}
	<-got
}

func TestFairShareSetCapAdmitsWaiters(t *testing.T) {
	f := &consumer.FairShare{Cap: 1}
	r, _ := f.Acquire(context.Background(), "A", 1)
	done := make(chan struct{})
	go func() { r2, _ := f.Acquire(context.Background(), "B", 1); close(done); r2() }()
	time.Sleep(10 * time.Millisecond)
	f.SetCap(2)
	select {
	case <-done:
	case <-time.After(time.Second):
		t.Fatal("raising the cap did not admit the waiter")
	}
	r()
}

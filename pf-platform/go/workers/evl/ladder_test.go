package evl_test

import (
	"strings"
	"testing"
	"time"

	"pf-platform/go/workers/consumer"
	"pf-platform/go/workers/evl"
	"pf-platform/go/workers/internal/testenv"
)

type clock struct{ t time.Time }

func (c *clock) now() time.Time      { return c.t }
func (c *clock) add(d time.Duration) { c.t = c.t.Add(d) }
func feed(l *evl.Ladder, c *clock, tenant string, lag float64, d time.Duration) {
	for end := c.t.Add(d); c.t.Before(end); c.add(5 * time.Second) {
		l.Observe(tenant, lag)
	}
	l.Observe(tenant, lag)
}

// D84 (docs/63 §4.14): thresholds as fractions of the 10-min tick_stale window.
func TestLadderThresholds(t *testing.T) {
	c := &clock{t: time.Date(2026, 9, 25, 12, 0, 0, 0, time.UTC)}
	m := consumer.NewMetrics()
	l := &evl.Ladder{Metrics: m, Now: c.now}
	const T = "T"

	feed(l, c, T, 70, 50*time.Second)
	if m.Gauge("evl_scale_out_wanted", "tenant", T) != 0 {
		t.Fatal("scale-out before 60 s above 60 s")
	}
	feed(l, c, T, 70, 15*time.Second)
	if m.Gauge("evl_scale_out_wanted", "tenant", T) != 1 || l.Level(T) != 0 {
		t.Fatal("> 60 s for 60 s must want scale-out and shed nothing")
	}
	feed(l, c, T, 130, 4*time.Minute)
	if l.Level(T) != 0 {
		t.Fatal("level 1 before 5 min above 120 s")
	}
	feed(l, c, T, 130, 65*time.Second)
	if l.Level(T) != 1 || m.Gauge("evl_page", "tenant", T) != 0 {
		t.Fatalf("> 120 s for 5 min → level 1, no page; got level %d", l.Level(T))
	}
	feed(l, c, T, 310, 5*time.Second)
	if l.Level(T) != 2 || m.Gauge("evl_page", "tenant", T) != 0 {
		t.Fatal("> 300 s → level 2 at once, page only after 60 s")
	}
	feed(l, c, T, 310, 60*time.Second)
	if m.Gauge("evl_page", "tenant", T) != 1 {
		t.Fatal("> 300 s for 60 s → PAGE")
	}
	feed(l, c, T, 500, 5*time.Second)
	if l.Level(T) != 3 || m.Gauge("evl_incident", "tenant", T) != 1 {
		t.Fatal("> 480 s → INCIDENT, level 3")
	}
	// Hysteresis: lag back to 100 s keeps level 3 (incident hold, then no
	// recovery condition).
	feed(l, c, T, 100, 12*time.Minute)
	if l.Level(T) != 3 {
		t.Fatalf("level dropped without < 30 s for 10 min: %d", l.Level(T))
	}
	feed(l, c, T, 10, 9*time.Minute)
	if l.Level(T) != 3 {
		t.Fatal("recovered before 10 min under 30 s")
	}
	feed(l, c, T, 10, 70*time.Second)
	if l.Level(T) != 0 || m.Gauge("evl_scale_in_ok", "tenant", T) != 1 || m.Gauge("evl_incident", "tenant", T) != 0 {
		t.Fatalf("< 30 s for 10 min → level 0 + scale-in; got level %d", l.Level(T))
	}
}

func TestLadderLevel1Held15MinEscalates(t *testing.T) {
	c := &clock{t: time.Date(2026, 9, 25, 12, 0, 0, 0, time.UTC)}
	l := &evl.Ladder{Metrics: consumer.NewMetrics(), Now: c.now}
	feed(l, c, "T", 150, 5*time.Minute+5*time.Second)
	if l.Level("T") != 1 {
		t.Fatal("want level 1")
	}
	feed(l, c, "T", 150, 14*time.Minute)
	if l.Level("T") != 1 {
		t.Fatal("escalated before level 1 held 15 min")
	}
	feed(l, c, "T", 150, 70*time.Second)
	if l.Level("T") != 2 {
		t.Fatal("level 1 held 15 min with lag > 120 s → level 2")
	}
}

func TestFundedStaleAndTrimAreIncidents(t *testing.T) {
	c := &clock{t: time.Date(2026, 9, 25, 12, 0, 0, 0, time.UTC)}
	m := consumer.NewMetrics()
	l := &evl.Ladder{Metrics: m, Now: c.now}
	l.FundedStale("A")
	l.Incident("B", "stream_trimmed")
	for _, tn := range []string{"A", "B"} {
		if l.Level(tn) != 3 || m.Gauge("evl_incident", "tenant", tn) != 1 {
			t.Fatalf("tenant %s: want level 3 incident", tn)
		}
	}
	if l.Level("C") != 0 {
		t.Fatal("an incident in one tenant must not shed another")
	}
	if m.Counter("evl_incidents_total", "tenant", "A", "reason", "funded_tick_stale") != 1 {
		t.Fatal("incident not counted with its reason")
	}
}

func exported(m *consumer.Metrics, prefix string) int {
	var b strings.Builder
	_, _ = m.WriteTo(&b)
	n := 0
	for _, line := range strings.Split(b.String(), "\n") {
		if strings.HasPrefix(line, prefix) {
			n++
		}
	}
	return n
}

// A lease handover must not reset a tenant mid-incident: the next owner's
// ladder resumes level + incident hold from evl_load_shed (also the
// bridge's 30 s reload source), and the old owner stops exporting gauges.
func TestLadderStateSurvivesHandoverAndOldOwnerGoesQuiet(t *testing.T) {
	db := testenv.PG(t)
	tenant := testenv.ULID()
	if _, err := db.Exec(`INSERT INTO tenants (id) VALUES ($1)`, tenant); err != nil {
		t.Fatal(err)
	}
	c := &clock{t: time.Now()}
	mOld := consumer.NewMetrics()
	old := &evl.Ladder{DB: db, Metrics: mOld, Now: c.now}
	old.Incident(tenant, "stream_trimmed")
	var level int
	var reason string
	if err := db.QueryRow(`SELECT level, reason FROM evl_load_shed WHERE tenant_id = $1`, tenant).Scan(&level, &reason); err != nil ||
		level != 3 || reason != "stream_trimmed" {
		t.Fatalf("persisted row: level=%d reason=%q err=%v", level, reason, err)
	}
	old.Forget(tenant)
	if n := exported(mOld, "evl_"); n != 1 { // only the evl_incidents_total counter remains
		t.Fatalf("old owner still exports %d evl_* series after Forget", n)
	}

	c.add(2 * time.Minute)
	mNew := consumer.NewMetrics()
	nw := &evl.Ladder{DB: db, Metrics: mNew, Now: c.now}
	nw.Observe(tenant, 5) // lag already fine — but the incident hold stands
	if nw.Level(tenant) != 3 || mNew.Gauge("evl_incident", "tenant", tenant) != 1 {
		t.Fatalf("new owner reset the tenant: level %d", nw.Level(tenant))
	}
	c.add(9 * time.Minute) // hold expires at +10 min; recovery still needs < 30 s for 10 min
	feed(nw, c, tenant, 5, 10*time.Minute+10*time.Second)
	if nw.Level(tenant) != 0 {
		t.Fatalf("did not recover after hold + 10 min under 30 s: level %d", nw.Level(tenant))
	}
	_ = db.QueryRow(`SELECT level FROM evl_load_shed WHERE tenant_id = $1`, tenant).Scan(&level)
	if level != 0 {
		t.Fatalf("recovery not persisted: %d", level)
	}
}

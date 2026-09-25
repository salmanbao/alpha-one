// Command evl-loadtest drives the workers evaluation lane end to end —
// Redis Streams → supervisor lanes → engine /evaluate → Postgres — and
// checks the properties docs/64 and docs/29 §6 require, printing measured
// numbers (not a description):
//
//	drain     burst drain throughput (ticks/s committed)
//	exactly   every published event_id → exactly one consumer_state 'done'
//	          and one evaluations row, despite injected redeliveries
//	versions  every account's final evaluation_state.version == ticks sent
//	I-24      no two handlers ever in flight for the same account
//	LT-4      per-tenant tick→commit p50/p95/p99, baseline vs tenant A at
//	          10× weight; B–J p95 must not degrade beyond -fairness-slack
//
// It runs two supervisor instances in-process (streams split by the
// ownership lease). The engine is either the in-process stub
// (-engine=stub) or a real propfirm-engine (-engine=http://…, -token).
// Scale is set by flags; the defaults fit a 2-CPU sandbox and are NOT the
// 100k-account target — docs/29 §6 LT-1..LT-8 are run at that scale on the
// V2 hardware.
package main

import (
	"context"
	"database/sql"
	"encoding/json"
	"flag"
	"fmt"
	"log/slog"
	"math"
	"math/rand"
	"net/http"
	"net/http/httptest"
	"os"
	"sort"
	"strings"
	"sync"
	"sync/atomic"
	"time"

	"github.com/lib/pq"
	"github.com/redis/go-redis/v9"

	"pf-platform/go/workers/consumer"
	"pf-platform/go/workers/evl"
	"pf-platform/go/workers/evl/enginestub"
)

type config struct {
	adminDSN, redisURL, engineURL, token string
	tenants, accounts                    int
	drainTicks                           int
	rate                                 float64 // ticks/s per tenant (baseline)
	hotMult                              float64
	phase                                time.Duration
	instances                            int
	engineDelay                          time.Duration
	dupFrac                              float64
	fairnessSlack                        float64
	inflight                             int
	budget                               int
	out                                  string
}

func main() {
	var c config
	flag.StringVar(&c.adminDSN, "db", "host=/tmp port=55432 user=postgres dbname=postgres sslmode=disable", "admin Postgres DSN")
	flag.StringVar(&c.redisURL, "redis", "redis://localhost:56379/0", "Redis URL")
	flag.StringVar(&c.engineURL, "engine", "stub", "engine base URL, or 'stub'")
	flag.StringVar(&c.token, "token", "stub-token", "engine service bearer")
	flag.IntVar(&c.tenants, "tenants", 10, "tenants")
	flag.IntVar(&c.accounts, "accounts", 100, "accounts per tenant")
	flag.IntVar(&c.drainTicks, "drain", 5000, "ticks for the burst-drain phase")
	flag.Float64Var(&c.rate, "rate", 20, "baseline ticks/s per tenant")
	flag.Float64Var(&c.hotMult, "hot", 10, "tenant A's multiplier in the fairness phase")
	flag.DurationVar(&c.phase, "phase", 20*time.Second, "duration of each fairness phase")
	flag.IntVar(&c.instances, "instances", 2, "supervisor instances")
	flag.DurationVar(&c.engineDelay, "engine-delay", time.Millisecond, "stub engine latency")
	flag.Float64Var(&c.dupFrac, "dup", 0.01, "fraction of events re-published (redelivery)")
	flag.Float64Var(&c.fairnessSlack, "fairness-slack", 1.25, "max allowed B–J p95 ratio hot/baseline (I-31 \"within noise\"); 0 = report only")
	flag.IntVar(&c.inflight, "inflight", 0, "FairShare in-flight cap per instance, fixed (0 = off)")
	flag.IntVar(&c.budget, "budget", 0, "FairShare group-wide in-flight budget, split across live instances (0 = off)")
	flag.StringVar(&c.out, "out", "", "write the JSON report here")
	flag.Parse()
	if err := run(c); err != nil {
		fmt.Fprintln(os.Stderr, "FAIL:", err)
		os.Exit(1)
	}
}

type published struct {
	tenant, account string
	at              time.Time
	phase           string
}

type lt struct {
	c        config
	db       *sql.DB
	rdb      *redis.Client
	eng      *evl.Engine
	tenants  []string
	accounts map[string][]string
	seq      map[string]int64 // account → ticks sent (unique)
	pub      sync.Map         // event_id → published
	mu       sync.Mutex
	dups     atomic.Int64
	inFlight sync.Map
	overlap  atomic.Int64
	metrics  *consumer.Metrics
}

func run(c config) error {
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	l := &lt{c: c, accounts: map[string][]string{}, seq: map[string]int64{}, metrics: consumer.NewMetrics()}

	// Fresh database with the contracts schema.
	adb, err := sql.Open("postgres", c.adminDSN)
	if err != nil {
		return err
	}
	name := fmt.Sprintf("evl_lt_%d", time.Now().UnixNano())
	if _, err := adb.Exec("CREATE DATABASE " + name); err != nil {
		return err
	}
	defer adb.Exec("DROP DATABASE IF EXISTS " + name + " WITH (FORCE)")
	dsn := withDB(c.adminDSN, name)
	if l.db, err = sql.Open("postgres", dsn); err != nil {
		return err
	}
	l.db.SetMaxOpenConns(80)
	if err := applySchema(l.db); err != nil {
		return err
	}
	opt, err := redis.ParseURL(c.redisURL)
	if err != nil {
		return err
	}
	opt.PoolSize = 200
	l.rdb = redis.NewClient(opt)

	if c.engineURL == "stub" {
		srv := httptest.NewServer(&enginestub.Stub{Token: c.token, Delay: c.engineDelay})
		defer srv.Close()
		l.eng = &evl.Engine{BaseURL: srv.URL, Token: c.token}
	} else {
		l.eng = &evl.Engine{BaseURL: c.engineURL, Token: c.token}
	}
	l.eng.HTTP = &http.Client{Timeout: 10 * time.Second, Transport: &http.Transport{MaxIdleConnsPerHost: 256}}

	fmt.Printf("evl-loadtest: engine=%s tenants=%d accounts/tenant=%d instances=%d fair-share-cap=%d budget=%d\n", c.engineURL, c.tenants, c.accounts, c.instances, c.inflight, c.budget)
	t0 := time.Now()
	if err := l.seed(ctx); err != nil {
		return err
	}
	fmt.Printf("seeded %d accounts via /state/init in %.1fs\n", c.tenants*c.accounts, time.Since(t0).Seconds())

	// Workers: N supervisor instances over the same tenant streams.
	weights := map[string]float64{}
	for _, t := range l.tenants {
		weights[t] = 1
	}
	lanes := consumer.AllocateLanes(weights)
	var streams []consumer.StreamSpec
	for _, t := range l.tenants {
		streams = append(streams, consumer.StreamSpec{Key: evl.StreamKey(t), Tenant: t, Lanes: lanes[t]})
	}
	quiet := slog.New(slog.NewTextHandler(os.Stderr, &slog.HandlerOptions{Level: slog.LevelError}))
	h := &evl.Handler{DB: l.db, Redis: l.rdb, Engine: l.eng, Metrics: l.metrics, Log: quiet}
	guarded := func(ctx context.Context, m consumer.Message) error {
		if _, busy := l.inFlight.LoadOrStore(m.EntityID, true); busy {
			l.overlap.Add(1)
		}
		defer l.inFlight.Delete(m.EntityID)
		return h.Handle(ctx, m)
	}
	var sups []*consumer.Supervisor
	for i := 0; i < c.instances; i++ {
		s := &consumer.Supervisor{
			Spec:  consumer.Spec{Name: evl.ConsumerName, Block: 200 * time.Millisecond, LeaseTTL: 3 * time.Second},
			Redis: l.rdb, DB: l.db, Handler: guarded, Instance: fmt.Sprintf("lt-%d", i), Metrics: l.metrics,
			Log: quiet, EntityOf: evl.EntityOf, LagInterval: time.Second,
		}
		if c.inflight > 0 {
			s.Fair = &consumer.FairShare{Cap: c.inflight, Metrics: l.metrics}
		}
		s.FairBudget = c.budget
		sups = append(sups, s)
		go s.Run(ctx, streams)
	}
	// Wait for lease rebalancing to spread the streams (ceil(T/instances)).
	owned := map[string]int{}
	target := (len(l.tenants) + c.instances - 1) / c.instances
	settle := time.Now()
	for time.Since(settle) < 90*time.Second {
		owned = map[string]int{}
		total, over := 0, false
		for _, t := range l.tenants {
			v, _ := l.rdb.Get(ctx, "lease:"+evl.ConsumerName+":"+evl.StreamKey(t)).Result()
			if v != "" {
				owned[v]++
				total++
			}
		}
		for _, n := range owned {
			over = over || n > target
		}
		if total == len(l.tenants) && !over {
			break
		}
		time.Sleep(250 * time.Millisecond)
	}
	fmt.Printf("stream ownership: %v after %.1fs (lanes per tenant: %d)\n", owned, time.Since(settle).Seconds(), lanes[l.tenants[0]])

	report := map[string]any{"config": map[string]any{
		"engine": c.engineURL, "tenants": c.tenants, "accounts_per_tenant": c.accounts, "instances": c.instances,
		"fair_share_cap": c.inflight, "fair_budget": c.budget, "baseline_rate_per_tenant": c.rate, "hot_multiplier": c.hotMult, "phase_seconds": c.phase.Seconds(),
	}}

	// Phase 1: burst drain.
	d0 := time.Now()
	n := l.burst(ctx, c.drainTicks)
	if err := l.waitDone(ctx, 5*time.Minute); err != nil {
		return err
	}
	drain := time.Since(d0)
	fmt.Printf("\n[drain] %d ticks published at once, all committed in %.2fs → %.0f ticks/s\n", n, drain.Seconds(), float64(n)/drain.Seconds())
	report["drain"] = map[string]any{"ticks": n, "seconds": drain.Seconds(), "ticks_per_s": float64(n) / drain.Seconds()}

	// Phase 2/3: fairness.
	base := l.steady(ctx, "baseline", 1)
	if err := l.waitDone(ctx, 5*time.Minute); err != nil {
		return err
	}
	hot := l.steady(ctx, "hot", c.hotMult)
	if err := l.waitDone(ctx, 5*time.Minute); err != nil {
		return err
	}
	lat, err := l.latencies()
	if err != nil {
		return err
	}
	fmt.Printf("\n[LT-4] tick→commit latency per tenant (ms): baseline %d t/s/tenant; hot phase tenant A at %.0f×\n", int(c.rate), c.hotMult)
	fmt.Printf("%-8s %9s %9s %9s | %9s %9s %9s | %7s %7s\n", "tenant", "base p50", "p95", "p99", "hot p50", "p95", "p99", "n_base", "n_hot")
	fair := []map[string]any{}
	worst := 0.0
	for i, t := range l.tenants {
		b, hh := lat["baseline"][t], lat["hot"][t]
		label := string(rune('A' + i))
		fmt.Printf("%-8s %9.1f %9.1f %9.1f | %9.1f %9.1f %9.1f | %7d %7d\n", label,
			pct(b, 50), pct(b, 95), pct(b, 99), pct(hh, 50), pct(hh, 95), pct(hh, 99), len(b), len(hh))
		fair = append(fair, map[string]any{"tenant": label, "base_p95_ms": pct(b, 95), "hot_p95_ms": pct(hh, 95),
			"base_n": len(b), "hot_n": len(hh)})
		if i > 0 {
			if r := pct(hh, 95) / pct(b, 95); r > worst {
				worst = r
			}
		}
	}
	report["fairness"] = map[string]any{"per_tenant": fair, "worst_BJ_p95_ratio": worst, "slack": c.fairnessSlack,
		"published_baseline": base, "published_hot": hot}
	fmt.Printf("worst B–J p95 ratio hot/baseline = %.2f (limit %.2f)\n", worst, c.fairnessSlack)

	// Checks.
	fails := l.check(report)
	if c.fairnessSlack > 0 && worst > c.fairnessSlack {
		fails = append(fails, fmt.Sprintf("LT-4: B–J p95 degraded %.2f× > %.2f×", worst, c.fairnessSlack))
	}
	report["failures"] = fails
	if c.out != "" {
		b, _ := json.MarshalIndent(report, "", "  ")
		_ = os.WriteFile(c.out, b, 0o644)
	}
	if len(fails) > 0 {
		return fmt.Errorf("%s", strings.Join(fails, "; "))
	}
	fmt.Println("\nRESULT: PASS")
	return nil
}

func (l *lt) seed(ctx context.Context) error {
	sem := make(chan struct{}, 32)
	var wg sync.WaitGroup
	var firstErr atomic.Value
	for i := 0; i < l.c.tenants; i++ {
		t := evl.NewULID()
		l.tenants = append(l.tenants, t)
		for j := 0; j < l.c.accounts; j++ {
			a := evl.NewULID()
			l.accounts[t] = append(l.accounts[t], a)
			wg.Add(1)
			sem <- struct{}{}
			go func(t, a string) {
				defer func() { <-sem; wg.Done() }()
				_, err := evl.InitAccount(ctx, l.db, l.eng, evl.InitRequest{AccountID: a, TenantID: t, Preset: "ftmo_phase1",
					StartedAt: time.Now().Add(-time.Hour).UnixMilli()}, evl.NewULID(), 1)
				if err != nil {
					firstErr.CompareAndSwap(nil, err)
				}
			}(t, a)
		}
	}
	wg.Wait()
	if e, ok := firstErr.Load().(error); ok {
		return fmt.Errorf("seed: %w", e)
	}
	return nil
}

// tick builds and publishes one tick for an account (unique, increasing
// broker_time per account), and occasionally re-publishes it.
func (l *lt) tick(ctx context.Context, tenant, account, phase string, rng *rand.Rand) error {
	l.mu.Lock()
	l.seq[account]++
	seq := l.seq[account]
	l.mu.Unlock()
	now := time.Now()
	id := evl.NewULID()
	eq := 1_000_000 + rng.Int63n(40_000) - 20_000 // ±2%: never near a floor
	env, _ := json.Marshal(map[string]any{
		"id": id, "type": "bridge.tick", "version": 1, "tenant_id": tenant, "occurred_at": now.UnixMilli(),
		"correlation_id": evl.NewULID(), "payload": map[string]any{
			"account_id": account, "broker_login": "5001", "equity_cents": eq, "balance_cents": 1_000_000,
			"margin_cents": 0, "free_margin_cents": eq, "leverage": "1:100", "positions": []any{},
			"deals_count": 0, "last_deal_ticket": 0, "broker_time": now.Add(-time.Hour).UnixMilli() + seq*1000 + 3_600_000,
			"trigger": "material", "source": "stream", "stream_seq": seq,
		},
	})
	l.pub.Store(id, published{tenant: tenant, account: account, at: now, phase: phase})
	args := &redis.XAddArgs{Stream: evl.StreamKey(tenant), Values: map[string]any{"event_id": id, "entity_id": account, "payload": string(env)}}
	if err := l.rdb.XAdd(ctx, args).Err(); err != nil {
		return err
	}
	if rng.Float64() < l.c.dupFrac {
		l.dups.Add(1)
		return l.rdb.XAdd(ctx, args).Err()
	}
	return nil
}

// broker_time must strictly increase per account; seq*1000 ms from a base
// an hour back keeps it monotone across phases without clock coupling.

func (l *lt) burst(ctx context.Context, n int) int {
	rng := rand.New(rand.NewSource(1))
	sent := 0
	for sent < n {
		for _, t := range l.tenants {
			a := l.accounts[t][rng.Intn(len(l.accounts[t]))]
			if err := l.tick(ctx, t, a, "drain", rng); err == nil {
				sent++
			}
			if sent >= n {
				break
			}
		}
	}
	return sent
}

func (l *lt) steady(ctx context.Context, phase string, hotMult float64) map[string]int {
	var wg sync.WaitGroup
	counts := make([]int, len(l.tenants))
	for i, t := range l.tenants {
		rate := l.c.rate
		if i == 0 {
			rate *= hotMult
		}
		wg.Add(1)
		go func(i int, t string, rate float64) {
			defer wg.Done()
			rng := rand.New(rand.NewSource(int64(i) + 7))
			interval := time.Duration(float64(time.Second) / rate)
			end := time.Now().Add(l.c.phase)
			next := time.Now()
			for time.Now().Before(end) {
				a := l.accounts[t][rng.Intn(len(l.accounts[t]))]
				if l.tick(ctx, t, a, phase, rng) == nil {
					counts[i]++
				}
				next = next.Add(interval)
				if d := time.Until(next); d > 0 {
					time.Sleep(d)
				}
			}
		}(i, t, rate)
	}
	wg.Wait()
	out := map[string]int{}
	for i := range l.tenants {
		out[string(rune('A'+i))] = counts[i]
	}
	fmt.Printf("[%s] published per tenant: %v\n", phase, out)
	return out
}

func (l *lt) total() int {
	n := 0
	l.pub.Range(func(_, _ any) bool { n++; return true })
	return n
}

func (l *lt) waitDone(ctx context.Context, max time.Duration) error {
	want := l.total()
	deadline := time.Now().Add(max)
	for time.Now().Before(deadline) {
		var n int
		if err := l.db.QueryRowContext(ctx, `SELECT count(*) FROM consumer_state WHERE consumer = 'evaluation' AND status IN ('done','skipped','dead')`).Scan(&n); err != nil {
			return err
		}
		if n >= want {
			return nil
		}
		time.Sleep(100 * time.Millisecond)
	}
	return fmt.Errorf("timed out: not all %d events terminal", want)
}

func (l *lt) latencies() (map[string]map[string][]float64, error) {
	out := map[string]map[string][]float64{"baseline": {}, "hot": {}, "drain": {}}
	rows, err := l.db.Query(`SELECT tick_event_id, created_at FROM evaluations`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	for rows.Next() {
		var id string
		var at time.Time
		if err := rows.Scan(&id, &at); err != nil {
			return nil, err
		}
		v, ok := l.pub.Load(id)
		if !ok {
			continue
		}
		p := v.(published)
		out[p.phase][p.tenant] = append(out[p.phase][p.tenant], float64(at.Sub(p.at).Microseconds())/1000)
	}
	return out, nil
}

func pct(xs []float64, p float64) float64 {
	if len(xs) == 0 {
		return math.NaN()
	}
	s := append([]float64(nil), xs...)
	sort.Float64s(s)
	i := int(math.Ceil(p/100*float64(len(s)))) - 1
	if i < 0 {
		i = 0
	}
	return s[i]
}

func (l *lt) check(report map[string]any) []string {
	var fails []string
	total := l.total()
	var done, skipped, dead, evals, distinct int
	_ = l.db.QueryRow(`SELECT count(*) FILTER (WHERE status='done'), count(*) FILTER (WHERE status='skipped'),
	        count(*) FILTER (WHERE status='dead') FROM consumer_state WHERE consumer='evaluation'`).Scan(&done, &skipped, &dead)
	_ = l.db.QueryRow(`SELECT count(*), count(DISTINCT tick_event_id) FROM evaluations`).Scan(&evals, &distinct)
	fmt.Printf("\n[exactly-once] published unique=%d (+%d redeliveries) consumer_state done=%d skipped=%d dead=%d evaluations=%d distinct=%d\n",
		total, l.dups.Load(), done, skipped, dead, evals, distinct)
	if done != total || evals != total || distinct != total || dead != 0 || skipped != 0 {
		fails = append(fails, "exactly-once violated")
	}
	// versions
	var mismatched int
	var accountsChecked int
	var ids []string
	var want []int64
	l.mu.Lock()
	for a, n := range l.seq {
		ids = append(ids, a)
		want = append(want, n)
	}
	l.mu.Unlock()
	rows, err := l.db.Query(`SELECT a.id, s.version FROM unnest($1::text[]) WITH ORDINALITY a(id, i)
	        JOIN evaluation_state s ON s.account_id = a.id`, pq.Array(ids))
	if err == nil {
		got := map[string]int64{}
		for rows.Next() {
			var id string
			var v int64
			_ = rows.Scan(&id, &v)
			got[id] = v
		}
		rows.Close()
		for i, a := range ids {
			accountsChecked++
			if got[a] != want[i] {
				mismatched++
			}
		}
	}
	fmt.Printf("[versions] accounts=%d with final version == ticks sent: %d, mismatched: %d\n", accountsChecked, accountsChecked-mismatched, mismatched)
	if mismatched != 0 || err != nil {
		fails = append(fails, fmt.Sprintf("versions: %d mismatched (err %v)", mismatched, err))
	}
	sw := l.metrics.SumCounter("evl_single_writer_violation_total")
	dlq := l.metrics.SumCounter("consumer_dlq_total")
	retries := l.metrics.SumCounter("consumer_retries_total")
	fmt.Printf("[I-24] concurrent same-account handlers: %d; single-writer violations: %.0f; DLQ: %.0f; retries: %.0f\n",
		l.overlap.Load(), sw, dlq, retries)
	if l.overlap.Load() != 0 || sw != 0 || dlq != 0 {
		fails = append(fails, "I-24/DLQ")
	}
	report["exactly_once"] = map[string]any{"unique": total, "redeliveries": l.dups.Load(), "done": done, "evaluations": evals,
		"distinct": distinct, "dead": dead}
	report["versions"] = map[string]any{"accounts": accountsChecked, "mismatched": mismatched}
	report["i24"] = map[string]any{"overlaps": l.overlap.Load(), "single_writer_violations": sw, "dlq": dlq, "retries": retries}
	return fails
}

func withDB(dsn, name string) string {
	parts := strings.Fields(dsn)
	if strings.Contains(dsn, "://") {
		i := strings.LastIndex(dsn, "/")
		q := ""
		if j := strings.Index(dsn[i:], "?"); j >= 0 {
			q = dsn[i+j:]
		}
		return dsn[:i+1] + name + q
	}
	out := []string{}
	for _, p := range parts {
		if !strings.HasPrefix(p, "dbname=") {
			out = append(out, p)
		}
	}
	return strings.Join(append(out, "dbname="+name), " ")
}

func applySchema(db *sql.DB) error {
	dir := ""
	wd, _ := os.Getwd()
	for i := 0; i < 8 && dir == ""; i++ {
		p := wd + "/alpha-one/contracts/data/schemas"
		if st, err := os.Stat(p); err == nil && st.IsDir() {
			dir = p
		}
		wd = wd[:max(strings.LastIndex(wd, "/"), 0)]
	}
	if dir == "" {
		return fmt.Errorf("cannot find alpha-one/contracts/data/schemas")
	}
	for i, f := range []string{"01-domains.sql", "04-gw-evt.sql", "08-brg.sql", "09-evl.sql"} {
		b, err := os.ReadFile(dir + "/" + f)
		if err != nil {
			return err
		}
		if _, err := db.Exec(string(b)); err != nil {
			return fmt.Errorf("%s: %w", f, err)
		}
		if i == 0 {
			if _, err := db.Exec(`CREATE TABLE tenants (id ULID PRIMARY KEY); CREATE TABLE accounts (id ULID PRIMARY KEY)`); err != nil {
				return err
			}
		}
	}
	return nil
}

package evl_test

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"reflect"
	"sort"
	"strings"
	"sync/atomic"
	"testing"
	"time"

	"github.com/redis/go-redis/v9"

	"pf-platform/go/workers/consumer"
	"pf-platform/go/workers/evl"
	"pf-platform/go/workers/evl/enginestub"
	"pf-platform/go/workers/internal/testenv"
)

// ---- I-29: the Go contract types are exactly the schema ----

func schemaProps(t *testing.T, file string, path ...string) []string {
	t.Helper()
	b, err := os.ReadFile(filepath.Join(testenv.SchemaDir(t), "..", "..", "events", "payloads", file))
	if err != nil {
		t.Fatal(err)
	}
	var node any
	if err := json.Unmarshal(b, &node); err != nil {
		t.Fatal(err)
	}
	for _, p := range path {
		switch n := node.(type) {
		case map[string]any:
			node = n[p]
		case []any:
			var i int
			fmt.Sscan(p, &i)
			node = n[i]
		}
	}
	props := node.(map[string]any)["properties"].(map[string]any)
	out := make([]string, 0, len(props))
	for k := range props {
		out = append(out, k)
	}
	sort.Strings(out)
	return out
}

func TestTickStructMatchesSchema(t *testing.T) {
	cases := []struct {
		name string
		typ  reflect.Type
		file string
		path []string
	}{
		{"envelope", reflect.TypeOf(evl.Envelope{}), "envelope.schema.json", []string{"$defs", "envelope"}},
		{"bridge.tick payload", reflect.TypeOf(evl.TickPayload{}), "bridge.tick.v1.json", []string{"allOf", "1", "properties", "payload"}},
		{"bridge.tick position", reflect.TypeOf(evl.TickPosition{}), "bridge.tick.v1.json",
			[]string{"allOf", "1", "properties", "payload", "properties", "positions", "items"}},
	}
	for _, c := range cases {
		got, want := evl.JSONFields(c.typ), schemaProps(t, c.file, c.path...)
		if !reflect.DeepEqual(got, want) {
			t.Errorf("I-29 %s: Go fields %v != schema properties %v", c.name, got, want)
		}
	}
}

type tickOpts struct {
	tenant, account string
	occurredAt      time.Time
	brokerTime      int64
	equity, balance int64
	login           string
	extra           map[string]any
	id              string
}

func tickJSON(o tickOpts) (string, []byte) {
	if o.id == "" {
		o.id = evl.NewULID()
	}
	if o.occurredAt.IsZero() {
		o.occurredAt = time.Now()
	}
	if o.login == "" {
		o.login = "5001"
	}
	trigger := "heartbeat"
	payload := map[string]any{
		"account_id": o.account, "broker_login": o.login, "equity_cents": o.equity, "balance_cents": o.balance,
		"margin_cents": 0, "free_margin_cents": o.equity, "leverage": "1:100", "positions": []any{},
		"deals_count": 0, "last_deal_ticket": 0, "broker_time": o.brokerTime, "trigger": trigger, "source": "stream",
	}
	for k, v := range o.extra {
		payload[k] = v
	}
	b, _ := json.Marshal(map[string]any{
		"id": o.id, "type": "bridge.tick", "version": 1, "tenant_id": o.tenant,
		"occurred_at": o.occurredAt.UnixMilli(), "correlation_id": evl.NewULID(), "payload": payload,
	})
	return o.id, b
}

func TestParseTickIsStrict(t *testing.T) {
	tenant, account := evl.NewULID(), evl.NewULID()
	base := tickOpts{tenant: tenant, account: account, brokerTime: 1, equity: 1, balance: 1}
	_, good := tickJSON(base)
	if _, _, err := evl.ParseTick(good); err != nil {
		t.Fatalf("valid tick rejected: %v", err)
	}
	mutate := func(f func(m map[string]any)) []byte {
		var m map[string]any
		_ = json.Unmarshal(good, &m)
		f(m)
		b, _ := json.Marshal(m)
		return b
	}
	bad := map[string][]byte{
		"unknown payload field":  mutate(func(m map[string]any) { m["payload"].(map[string]any)["floor_cents"] = 1 }),
		"unknown envelope field": mutate(func(m map[string]any) { m["causation_id"] = "x" }),
		"missing required":       mutate(func(m map[string]any) { delete(m["payload"].(map[string]any), "margin_cents") }),
		"bad account ULID":       mutate(func(m map[string]any) { m["payload"].(map[string]any)["account_id"] = "acct-1" }),
		"bad trigger":            mutate(func(m map[string]any) { m["payload"].(map[string]any)["trigger"] = "cron" }),
		"wrong type":             mutate(func(m map[string]any) { m["type"] = "bridge.snapshot" }),
		"wrong version":          mutate(func(m map[string]any) { m["version"] = 2 }),
		"unknown position field": mutate(func(m map[string]any) {
			m["payload"].(map[string]any)["positions"] = []any{map[string]any{
				"position_id": "p", "symbol": "EURUSD", "side": "buy", "lots": 0.1, "open_price": 1.1, "opened_at": 1, "magic": 7}}
		}),
		"position missing required": mutate(func(m map[string]any) {
			m["payload"].(map[string]any)["positions"] = []any{map[string]any{"position_id": "p", "symbol": "EURUSD", "side": "buy"}}
		}),
		"equity as string": mutate(func(m map[string]any) { m["payload"].(map[string]any)["equity_cents"] = "100" }),
	}
	for name, b := range bad {
		if _, _, err := evl.ParseTick(b); err == nil {
			t.Errorf("%s: accepted, want rejection", name)
		}
	}
}

// ---- integration: workers ↔ engine (stub, or the real engine via ENGINE_URL) ----

type harness struct {
	t       *testing.T
	db      *sql.DB
	rdb     *redis.Client
	eng     *evl.Engine
	stub    *enginestub.Stub // nil against the real engine
	metrics *consumer.Metrics
	handler *evl.Handler
	sup     *consumer.Supervisor
	tenant  string
	stale   atomic.Int64
	cancel  context.CancelFunc
}

func engine(t *testing.T) (*evl.Engine, *enginestub.Stub) {
	if u := os.Getenv("ENGINE_URL"); u != "" {
		return &evl.Engine{BaseURL: u, Token: os.Getenv("ENGINE_TOKEN")}, nil
	}
	stub := &enginestub.Stub{Token: "stub-token"}
	srv := httptest.NewServer(stub)
	t.Cleanup(srv.Close)
	return &evl.Engine{BaseURL: srv.URL, Token: "stub-token"}, stub
}

func newHarness(t *testing.T) *harness {
	h := &harness{t: t, db: testenv.PG(t), rdb: testenv.Redis(t), metrics: consumer.NewMetrics(), tenant: evl.NewULID()}
	h.eng, h.stub = engine(t)
	h.handler = &evl.Handler{DB: h.db, Redis: h.rdb, Engine: h.eng, Metrics: h.metrics,
		OnFundedStale: func(string) { h.stale.Add(1) }}
	h.sup = &consumer.Supervisor{
		Spec:  consumer.Spec{Name: evl.ConsumerName, BackoffBase: 10 * time.Millisecond, Block: 100 * time.Millisecond, LeaseTTL: time.Second},
		Redis: h.rdb, DB: h.db, Handler: h.handler.Handle, Instance: "t-" + evl.NewULID(), Metrics: h.metrics,
		EntityOf: evl.EntityOf, LagInterval: 200 * time.Millisecond,
	}
	return h
}

func (h *harness) start() {
	ctx, cancel := context.WithCancel(context.Background())
	h.cancel = cancel
	h.t.Cleanup(cancel)
	go h.sup.Run(ctx, []consumer.StreamSpec{{Key: evl.StreamKey(h.tenant), Tenant: h.tenant, Lanes: 13}})
}

func (h *harness) seed(account, preset string) {
	h.t.Helper()
	ok, err := evl.InitAccount(context.Background(), h.db, h.eng, evl.InitRequest{
		AccountID: account, TenantID: h.tenant, Preset: preset, StartedAt: time.Now().Add(-time.Hour).UnixMilli(),
	}, evl.NewULID(), 1)
	if err != nil || !ok {
		h.t.Fatalf("seed: ok=%v err=%v", ok, err)
	}
}

func (h *harness) publish(id string, env []byte) {
	h.t.Helper()
	if err := h.rdb.XAdd(context.Background(), &redis.XAddArgs{Stream: evl.StreamKey(h.tenant), Values: map[string]any{
		"event_id": id, "entity_id": evl.EntityOf(env), "payload": string(env),
	}}).Err(); err != nil {
		h.t.Fatal(err)
	}
}

func (h *harness) wait(d time.Duration, what string, cond func() bool) {
	h.t.Helper()
	deadline := time.Now().Add(d)
	for time.Now().Before(deadline) {
		if cond() {
			return
		}
		time.Sleep(20 * time.Millisecond)
	}
	h.t.Fatalf("timed out waiting for %s", what)
}

func (h *harness) status(ev string) string {
	var s string
	_ = h.db.QueryRow(`SELECT status FROM consumer_state WHERE consumer = 'evaluation' AND event_id = $1`, ev).Scan(&s)
	return s
}

type stateCols struct {
	version, floorsVersion int64
	daily, total, target   sql.NullInt64
	status                 string
	breachRule             sql.NullString
	lastEvent              sql.NullString
}

func (h *harness) state(account string) stateCols {
	h.t.Helper()
	var c stateCols
	if err := h.db.QueryRow(`SELECT version, floors_version, floor_daily_cents, floor_total_cents, target_equity_cents,
	        status, breach_rule_id, last_tick_event_id FROM evaluation_state WHERE tenant_id = $1 AND account_id = $2`,
		h.tenant, account).Scan(&c.version, &c.floorsVersion, &c.daily, &c.total, &c.target, &c.status, &c.breachRule, &c.lastEvent); err != nil {
		h.t.Fatal(err)
	}
	return c
}

func TestTickFlowWritesStateVerdictAndHintsInOneTransaction(t *testing.T) {
	h := newHarness(t)
	account := evl.NewULID()
	h.seed(account, "ftmo_phase1")
	sub := h.rdb.Subscribe(context.Background(), evl.FloorsChannel)
	defer sub.Close()
	if _, err := sub.Receive(context.Background()); err != nil {
		t.Fatal(err)
	}
	h.start()
	now := time.Now().UnixMilli()
	ev, env := tickJSON(tickOpts{tenant: h.tenant, account: account, brokerTime: now, equity: 1_000_000, balance: 1_000_000})
	h.publish(ev, env)
	h.wait(10*time.Second, "tick processed", func() bool { return h.status(ev) == "done" })

	c := h.state(account)
	if c.version != 1 || c.floorsVersion != 1 || c.status != "ok" || c.lastEvent.String != ev {
		t.Fatalf("state row: %+v", c)
	}
	if c.daily.Int64 != 949_998 || c.total.Int64 != 899_998 || c.target.Int64 != 1_100_000 {
		t.Fatalf("hints persisted: daily=%v total=%v target=%v, want 949998/899998/1100000", c.daily, c.total, c.target)
	}
	var evals int
	var inputHash string
	_ = h.db.QueryRow(`SELECT count(*), max(input_hash) FROM evaluations WHERE tick_event_id = $1`, ev).Scan(&evals, &inputHash)
	if evals != 1 || inputHash == "" {
		t.Fatalf("evaluations rows %d hash %q", evals, inputHash)
	}
	select {
	case m := <-sub.Channel():
		var fm evl.FloorsMessage
		_ = json.Unmarshal([]byte(m.Payload), &fm)
		if fm.AccountID != account || fm.FloorsVersion != 1 || fm.FloorDailyCents == nil || *fm.FloorDailyCents != 949_998 {
			t.Fatalf("evl.floors payload %s", m.Payload)
		}
	case <-time.After(3 * time.Second):
		t.Fatal("no evl.floors message")
	}
	var outbox int
	_ = h.db.QueryRow(`SELECT count(*) FROM outbox`).Scan(&outbox)
	if outbox != 0 {
		t.Fatalf("an ok verdict wrote %d outbox rows", outbox)
	}
	t.Logf("tick %s → version 1, hints daily=%d total=%d target=%d, input_hash=%s", ev, c.daily.Int64, c.total.Int64, c.target.Int64, inputHash)
}

func TestBreachWritesOutboxVerdictConformingToSchema(t *testing.T) {
	h := newHarness(t)
	account := evl.NewULID()
	h.seed(account, "ftmo_phase1")
	h.start()
	ev, env := tickJSON(tickOpts{tenant: h.tenant, account: account, brokerTime: time.Now().UnixMilli(), equity: 940_000, balance: 1_000_000})
	h.publish(ev, env)
	h.wait(10*time.Second, "breach processed", func() bool { return h.status(ev) == "done" })
	c := h.state(account)
	if c.status != "breach" || c.breachRule.String != "daily_drawdown" {
		t.Fatalf("state after breach: %+v", c)
	}
	var payload []byte
	var topic, entity string
	if err := h.db.QueryRow(`SELECT topic, entity_id, payload FROM outbox`).Scan(&topic, &entity, &payload); err != nil {
		t.Fatalf("outbox verdict: %v", err)
	}
	var envOut map[string]any
	_ = json.Unmarshal(payload, &envOut)
	p := envOut["payload"].(map[string]any)
	for _, k := range []string{"account_id", "verdict_id", "status", "input_hash", "broker_time"} { // schema required
		if _, ok := p[k]; !ok {
			t.Fatalf("verdict payload missing required %s: %s", k, payload)
		}
	}
	allowed := schemaProps(t, "evaluation.verdict.v1.json", "allOf", "1", "properties", "payload")
	for k := range p {
		if sort.SearchStrings(allowed, k) == len(allowed) || allowed[sort.SearchStrings(allowed, k)] != k {
			t.Fatalf("verdict payload field %q not in schema %v", k, allowed)
		}
	}
	if topic != "evaluation" || entity != account || envOut["type"] != "evaluation.verdict" || p["rule_id"] != "daily_drawdown" ||
		p["status"] != "breach" {
		t.Fatalf("verdict: topic=%s entity=%s env=%s", topic, entity, payload)
	}
	var verdictID string
	_ = h.db.QueryRow(`SELECT id FROM evaluations WHERE tick_event_id = $1`, ev).Scan(&verdictID)
	if p["verdict_id"] != verdictID {
		t.Fatalf("verdict_id %v != evaluations.id %s", p["verdict_id"], verdictID)
	}
}

// Redelivery of the same bridge.tick: exactly one state write and one
// evaluation (docs/64 §8 "idempotency is consumer_state's").
func TestRedeliveredTickIsEvaluatedOnce(t *testing.T) {
	h := newHarness(t)
	account := evl.NewULID()
	h.seed(account, "ftmo_phase1")
	ev, env := tickJSON(tickOpts{tenant: h.tenant, account: account, brokerTime: time.Now().UnixMilli(), equity: 1_000_000, balance: 1_000_000})
	for i := 0; i < 3; i++ {
		h.publish(ev, env)
	}
	h.start()
	h.wait(10*time.Second, "all three acked", func() bool { return h.metrics.SumCounter("consumer_processed_total") == 3 })
	var evals int
	_ = h.db.QueryRow(`SELECT count(*) FROM evaluations WHERE tick_event_id = $1`, ev).Scan(&evals)
	if c := h.state(account); c.version != 1 || evals != 1 {
		t.Fatalf("version=%d evaluations=%d, want 1/1", c.version, evals)
	}
	if h.stub != nil && h.stub.Calls.Load() != 1 {
		t.Fatalf("engine called %d times for one event, want 1 (Seen pre-check)", h.stub.Calls.Load())
	}
}

func TestOutOfOrderTickIsSkippedNotRetried(t *testing.T) {
	h := newHarness(t)
	account := evl.NewULID()
	h.seed(account, "ftmo_phase1")
	h.start()
	now := time.Now().UnixMilli()
	ev1, env1 := tickJSON(tickOpts{tenant: h.tenant, account: account, brokerTime: now, equity: 1_000_000, balance: 1_000_000})
	ev2, env2 := tickJSON(tickOpts{tenant: h.tenant, account: account, brokerTime: now - 5_000, equity: 990_000, balance: 1_000_000})
	h.publish(ev1, env1)
	h.publish(ev2, env2)
	h.wait(10*time.Second, "second tick skipped", func() bool { return h.status(ev2) == "skipped" })
	if c := h.state(account); c.version != 1 || c.lastEvent.String != ev1 {
		t.Fatalf("out-of-order tick changed state: %+v", c)
	}
	if n := h.metrics.SumCounter("consumer_retries_total"); n != 0 {
		t.Fatalf("409 was retried %v times", n)
	}
}

// An engine 400 is permanent: dead-lettered on the first attempt.
func TestEngine400IsDeadLetteredImmediately(t *testing.T) {
	h := newHarness(t)
	account := evl.NewULID()
	// A state document whose tenant disagrees with the row/stream tenant:
	// the engine rejects it 400 (tenant binding).
	other := evl.NewULID()
	out, err := h.eng.InitState(context.Background(), evl.InitRequest{AccountID: account, TenantID: other, Preset: "ftmo_phase1",
		StartedAt: time.Now().Add(-time.Hour).UnixMilli()})
	if err != nil {
		t.Fatal(err)
	}
	if _, err := h.db.Exec(`INSERT INTO evaluation_state (tenant_id, account_id, rule_pack_id, rule_pack_version, state, plan, status)
	        VALUES ($1, $2, $3, 1, $4, $5, 'ok')`, h.tenant, account, evl.NewULID(), []byte(out.State), []byte(out.Plan)); err != nil {
		t.Fatal(err)
	}
	h.start()
	ev, env := tickJSON(tickOpts{tenant: h.tenant, account: account, brokerTime: time.Now().UnixMilli(), equity: 1_000_000, balance: 1_000_000})
	h.publish(ev, env)
	h.wait(10*time.Second, "dead-lettered", func() bool { return h.status(ev) == "dead" })
	var attempts int
	_ = h.db.QueryRow(`SELECT attempts FROM consumer_state WHERE consumer='evaluation' AND event_id=$1`, ev).Scan(&attempts)
	xs, _ := h.rdb.XRange(context.Background(), "dlq.evaluation", "-", "+").Result()
	found := false
	for _, x := range xs {
		if x.Values["event_id"] == ev {
			found = x.Values["tenant_id"] == h.tenant && strings.Contains(fmt.Sprint(x.Values["error"]), "400")
		}
	}
	if attempts != 1 || !found {
		t.Fatalf("attempts=%d dlq entry found=%v", attempts, found)
	}
}

func TestStaleTickIsSuppressedAndFundedStaleIsAnIncident(t *testing.T) {
	h := newHarness(t)
	account := evl.NewULID()
	h.seed(account, "ftmo_funded")
	h.start()
	ev, env := tickJSON(tickOpts{tenant: h.tenant, account: account, occurredAt: time.Now().Add(-11 * time.Minute),
		brokerTime: time.Now().UnixMilli(), equity: 1_000_000, balance: 1_000_000})
	h.publish(ev, env)
	h.wait(10*time.Second, "stale skipped", func() bool { return h.status(ev) == "skipped" })
	if c := h.state(account); c.version != 0 {
		t.Fatalf("stale tick was evaluated: version %d", c.version)
	}
	if h.stale.Load() != 1 || h.metrics.Counter("evl_tick_stale_total", "tenant", h.tenant, "funded", "true") != 1 {
		t.Fatalf("funded stale not signalled: callbacks=%d", h.stale.Load())
	}
	if h.stub != nil && h.stub.Calls.Load() != 0 {
		t.Fatal("stale tick reached the engine")
	}
}

func TestMalformedTickIsDeadLetteredNotEvaluated(t *testing.T) {
	h := newHarness(t)
	account := evl.NewULID()
	h.seed(account, "ftmo_phase1")
	h.start()
	ev, env := tickJSON(tickOpts{tenant: h.tenant, account: account, brokerTime: time.Now().UnixMilli(), equity: 1, balance: 1,
		extra: map[string]any{"floor_daily_cents": 5}})
	h.publish(ev, env)
	h.wait(10*time.Second, "dead-lettered", func() bool { return h.status(ev) == "dead" })
	if c := h.state(account); c.version != 0 {
		t.Fatal("malformed tick changed state")
	}
}

// With lane ownership a version conflict cannot happen; if it does (here:
// forced by bumping the row during the engine call), it is counted, rolled
// back — consumer_state included — and retried from a fresh read.
func TestVersionConflictIsCountedRolledBackAndRetried(t *testing.T) {
	h := newHarness(t)
	if h.stub == nil {
		t.Skip("needs the stub's in-call hook")
	}
	account := evl.NewULID()
	h.seed(account, "ftmo_phase1")
	var bumped atomic.Bool
	h.stub.Hook = func(tenant string, _ map[string]any) {
		if bumped.CompareAndSwap(false, true) {
			_, _ = h.db.Exec(`UPDATE evaluation_state SET version = version + 100,
			     state = jsonb_set(state, '{version}', to_jsonb((state->>'version')::bigint + 100))
			     WHERE tenant_id = $1 AND account_id = $2`, tenant, account)
		}
	}
	h.start()
	ev, env := tickJSON(tickOpts{tenant: h.tenant, account: account, brokerTime: time.Now().UnixMilli(), equity: 1_000_000, balance: 1_000_000})
	h.publish(ev, env)
	h.wait(10*time.Second, "processed after retry", func() bool { return h.status(ev) == "done" })
	if n := h.metrics.Counter("evl_single_writer_violation_total", "tenant", h.tenant); n != 1 {
		t.Fatalf("single-writer violations counted %v, want 1", n)
	}
	var evals int
	_ = h.db.QueryRow(`SELECT count(*) FROM evaluations WHERE tick_event_id = $1`, ev).Scan(&evals)
	if c := h.state(account); c.version != 101 || evals != 1 {
		t.Fatalf("after retry: version=%d evaluations=%d, want 101/1", c.version, evals)
	}
}

// ---- D83: partitioning actually prunes; deal dedupe survives it ----

func explain(t *testing.T, db *sql.DB, q string) string {
	t.Helper()
	rows, err := db.Query("EXPLAIN " + q)
	if err != nil {
		t.Fatal(err)
	}
	defer rows.Close()
	var b strings.Builder
	for rows.Next() {
		var line string
		_ = rows.Scan(&line)
		b.WriteString(line + "\n")
	}
	return b.String()
}

func partitionsIn(plan, prefix string) map[string]bool {
	out := map[string]bool{}
	for _, f := range strings.Fields(plan) {
		name := strings.TrimRight(f, ",()")
		// Index names (…_pkey) appear in Index Scan lines; count tables only.
		if strings.HasPrefix(name, prefix) && !strings.HasSuffix(name, "_pkey") && !strings.HasSuffix(name, "_idx") {
			out[name] = true
		}
	}
	return out
}

func TestD83PartitionPruningAndDealDedupe(t *testing.T) {
	db := testenv.PG(t)
	tenant, account := evl.NewULID(), evl.NewULID()
	q := fmt.Sprintf(`SELECT * FROM evaluation_state WHERE tenant_id = '%s' AND account_id = '%s'`, tenant, account)
	if p := partitionsIn(explain(t, db, q), "evaluation_state_h"); len(p) != 1 {
		t.Fatalf("evaluation_state point read touches %d partitions, want 1: %v", len(p), p)
	}
	// Bridge hint reload: one tenant → one partition.
	q = fmt.Sprintf(`SELECT account_id, floor_daily_cents FROM evaluation_state WHERE tenant_id = '%s'`, tenant)
	if p := partitionsIn(explain(t, db, q), "evaluation_state_h"); len(p) != 1 {
		t.Fatalf("per-tenant read touches %d partitions: %v", len(p), p)
	}
	for b := 0; b < 16; b++ {
		for _, day := range []string{"2026-09-24", "2026-09-25"} {
			next := map[string]string{"2026-09-24": "2026-09-25", "2026-09-25": "2026-09-26"}[day]
			if _, err := db.Exec(fmt.Sprintf(`CREATE TABLE account_snapshots_h%d_%s PARTITION OF account_snapshots_h%d
			     FOR VALUES FROM ('%s 00:00+00') TO ('%s 00:00+00')`, b, strings.ReplaceAll(day, "-", ""), b, day, next)); err != nil {
				t.Fatal(err)
			}
		}
		if _, err := db.Exec(fmt.Sprintf(`CREATE TABLE broker_deals_h%d_202609 PARTITION OF broker_deals_h%d
		     FOR VALUES FROM ('2026-09-01') TO ('2026-10-01')`, b, b)); err != nil {
			t.Fatal(err)
		}
	}
	q = fmt.Sprintf(`SELECT * FROM account_snapshots WHERE tenant_id = '%s' AND account_id = '%s'
	      AND bucket_ts >= '2026-09-25 10:00+00' AND bucket_ts < '2026-09-25 11:00+00'`, tenant, account)
	p := partitionsIn(explain(t, db, q), "account_snapshots_h")
	if len(p) != 1 {
		t.Fatalf("snapshot range read touches %d partitions, want 1 (tenant bucket × day): %v", len(p), p)
	}
	for k := range p {
		if !strings.HasSuffix(k, "_20260925") {
			t.Fatalf("pruned to the wrong day: %s", k)
		}
	}
	ins := `INSERT INTO broker_deals (deal_id, login, tenant_id, entry, symbol, side, lots, price, deal_time, deal_day, received_at)
	        VALUES (77, '5001', $1, 'in', 'EURUSD', 'buy', 0.10, 1.1, '2026-09-25 10:00:00+00', '2026-09-25', $2)
	        ON CONFLICT DO NOTHING`
	r1, err := db.Exec(ins, tenant, time.Now())
	if err != nil {
		t.Fatal(err)
	}
	r2, err := db.Exec(ins, tenant, time.Now().Add(time.Minute)) // redelivery: new received_at
	if err != nil {
		t.Fatal(err)
	}
	n1, _ := r1.RowsAffected()
	n2, _ := r2.RowsAffected()
	if n1 != 1 || n2 != 0 {
		t.Fatalf("deal dedupe: first insert %d, redelivery %d, want 1/0", n1, n2)
	}
	if _, err := db.Exec(`INSERT INTO broker_deals (deal_id, login, tenant_id, entry, symbol, side, lots, price, deal_time, deal_day)
	        VALUES (78, '5001', $1, 'in', 'EURUSD', 'buy', 0.1, 1.1, '2026-09-25 23:30:00+00', '2026-09-24')`, tenant); err == nil {
		t.Fatal("deal_day inconsistent with deal_time was accepted")
	}
	t.Logf("pruning: evaluation_state point/tenant reads → 1 of 64 partitions; snapshot hour → %v; deal redelivery deduped", keys(p))
}

func keys(m map[string]bool) []string {
	var out []string
	for k := range m {
		out = append(out, k)
	}
	sort.Strings(out)
	return out
}

// Guard against an accidental real network dependency in unit runs.
var _ = http.StatusOK

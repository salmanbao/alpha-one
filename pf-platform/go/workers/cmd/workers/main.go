// Command workers runs the platform's event consumers. This build wires
// the EVL evaluation lane (docs/64 §6 step 1).
//
// Environment:
//
//	DATABASE_URL    Postgres (primary — the evaluation path writes)
//	REDIS_URL       Redis (streams + pub/sub)
//	ENGINE_URL      stateless engine base URL (e.g. http://engine:8080)
//	ENGINE_TOKEN    service bearer for the engine
//	EVL_TENANTS     comma-separated tenant ULIDs, each optionally ":weight"
//	                (D82 lane weights; default weight 1)
//	METRICS_ADDR    Prometheus listen address (default :9102)
//	WORKERS_INSTANCE consumer name inside the group (default hostname-pid)
//	WORKERS_INFLIGHT_BUDGET group-wide FairShare in-flight budget (default 64; 0 = off)
package main

import (
	"context"
	"database/sql"
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"strconv"
	"strings"
	"syscall"
	"time"

	_ "github.com/lib/pq"
	"github.com/redis/go-redis/v9"

	"pf-platform/go/workers/consumer"
	"pf-platform/go/workers/evl"
)

func main() {
	log := slog.New(slog.NewJSONHandler(os.Stdout, nil))
	if err := run(log); err != nil {
		log.Error("workers.exit", "err", err)
		os.Exit(1)
	}
}

func mustEnv(k string) (string, error) {
	v := os.Getenv(k)
	if v == "" {
		return "", fmt.Errorf("%s is required", k)
	}
	return v, nil
}

// ParseTenants parses EVL_TENANTS ("T1:3,T2,T3:0.5").
func ParseTenants(s string) (map[string]float64, error) {
	out := map[string]float64{}
	for _, part := range strings.Split(s, ",") {
		part = strings.TrimSpace(part)
		if part == "" {
			continue
		}
		id, w, hasW := strings.Cut(part, ":")
		weight := 1.0
		if hasW {
			f, err := strconv.ParseFloat(w, 64)
			if err != nil || f <= 0 {
				return nil, fmt.Errorf("EVL_TENANTS: bad weight in %q", part)
			}
			weight = f
		}
		if !evl.ULIDPattern.MatchString(id) {
			return nil, fmt.Errorf("EVL_TENANTS: %q is not a ULID", id)
		}
		out[id] = weight
	}
	if len(out) == 0 {
		return nil, fmt.Errorf("EVL_TENANTS is empty")
	}
	return out, nil
}

func run(log *slog.Logger) error {
	dsn, err := mustEnv("DATABASE_URL")
	if err != nil {
		return err
	}
	redisURL, err := mustEnv("REDIS_URL")
	if err != nil {
		return err
	}
	engineURL, err := mustEnv("ENGINE_URL")
	if err != nil {
		return err
	}
	token, err := mustEnv("ENGINE_TOKEN")
	if err != nil {
		return err
	}
	weights, err := ParseTenants(os.Getenv("EVL_TENANTS"))
	if err != nil {
		return err
	}
	instance := os.Getenv("WORKERS_INSTANCE")
	if instance == "" {
		h, _ := os.Hostname()
		instance = fmt.Sprintf("%s-%d", h, os.Getpid())
	}
	metricsAddr := os.Getenv("METRICS_ADDR")
	if metricsAddr == "" {
		metricsAddr = ":9102"
	}

	db, err := sql.Open("postgres", dsn)
	if err != nil {
		return err
	}
	db.SetMaxOpenConns(64)
	opt, err := redis.ParseURL(redisURL)
	if err != nil {
		return err
	}
	rdb := redis.NewClient(opt)

	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()

	metrics := consumer.NewMetrics()
	ladder := &evl.Ladder{DB: db, Redis: rdb, Metrics: metrics, Log: log}
	handler := &evl.Handler{
		DB: db, Redis: rdb, Metrics: metrics, Log: log,
		Engine:        &evl.Engine{BaseURL: engineURL, Token: token, HTTP: &http.Client{Timeout: 10 * time.Second}},
		OnFundedStale: ladder.FundedStale,
	}
	sup := &consumer.Supervisor{
		Spec:  consumer.Spec{Name: evl.ConsumerName},
		Redis: rdb, DB: db, Handler: handler.Handle, Instance: instance, Metrics: metrics, Log: log,
		EntityOf: evl.EntityOf,
		OnLag:    func(st consumer.StreamSpec, _ int64, s float64) { ladder.Observe(st.Tenant, s) },
	}
	// WORKERS_INFLIGHT_BUDGET: group-wide FairShare budget (handler calls in
	// flight across all instances), split as ceil(budget / live instances).
	// Size ≈ 2 × the PG primary's vCPUs and confirm with LT-4; 0 disables.
	// Default 64. See consumer.FairShare and D82.
	sup.FairBudget = 64
	if v := os.Getenv("WORKERS_INFLIGHT_BUDGET"); v != "" {
		if _, err := fmt.Sscan(v, &sup.FairBudget); err != nil || sup.FairBudget < 0 {
			log.Error("workers.bad_env", "WORKERS_INFLIGHT_BUDGET", v)
			os.Exit(2)
		}
	}
	replayer := &evl.TrimReplayer{DB: db, Redis: rdb, Supervisor: sup, Ladder: ladder, Log: log}
	sup.OnTrim = replayer.OnTrim
	sup.OnRelease = func(st consumer.StreamSpec) { ladder.Forget(st.Tenant) }

	lanes := consumer.AllocateLanes(weights)
	var streams []consumer.StreamSpec
	for tenant, n := range lanes {
		streams = append(streams, consumer.StreamSpec{Key: evl.StreamKey(tenant), Tenant: tenant, Lanes: n})
		log.Info("workers.lanes", "tenant", tenant, "weight", weights[tenant], "lanes", n)
	}

	mux := http.NewServeMux()
	mux.Handle("/metrics", metrics.Handler())
	mux.HandleFunc("/healthz", func(w http.ResponseWriter, _ *http.Request) { _, _ = w.Write([]byte("ok")) })
	srv := &http.Server{Addr: metricsAddr, Handler: mux, ReadHeaderTimeout: 5 * time.Second}
	go func() { _ = srv.ListenAndServe() }()
	defer srv.Close()

	log.Info("workers.start", "instance", instance, "tenants", len(weights), "total_lanes", consumer.TotalLanes(len(weights)))
	_ = sup.Run(ctx, streams)
	return nil
}

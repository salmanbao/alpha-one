package main

// pf-bridge node — scaffold entrypoint (doc §4.3 bridge plane).
//
// Env:
//   PF_LISTEN          listen address          (default :8080)
//   PF_NODE_ID         node id                 (default node-1)
//   PF_PACK_VERSION    rules pack version      (default v1)
//   PF_KAFKA_BROKERS   comma-separated; if set, publish to Kafka
//   PF_KAFKA_TOPIC     topic name              (default bridge.events)
//   PF_OUTBOX          JSONL outbox path       (default <tmp>/pf-bridge-outbox.jsonl)
//
// Endpoints:
//   GET  /healthz                 liveness + session count
//   POST /v1/bridge/pair          pairing bootstrap (tenant, account, platform)
//   GET  /v1/bridge/ws            WebSocket bridge (MT5/cBot/DXtrade clients)
//   POST /v1/bridge/events        REST envelope(s) (MT4 / spool replay)
//   POST /v1/bridge/control       admin/test surface: control commands

import (
	"context"
	"log"
	"net/http"
	"os"
	"os/signal"
	"path/filepath"
	"strings"
	"syscall"
	"time"
)

type Config struct {
	Listen      string
	NodeID      string
	PackVersion string
	KafkaBrokers []string
	KafkaTopic  string
	OutboxPath  string
	HBIntervalMs uint32
}

func loadConfig() Config {
	cfg := Config{
		Listen:       envOr("PF_LISTEN", ":8080"),
		NodeID:       envOr("PF_NODE_ID", "node-1"),
		PackVersion:  envOr("PF_PACK_VERSION", "v1"),
		KafkaTopic:   envOr("PF_KAFKA_TOPIC", "bridge.events"),
		OutboxPath:   envOr("PF_OUTBOX", filepath.Join(os.TempDir(), "pf-bridge-outbox.jsonl")),
		HBIntervalMs: 1000,
	}
	if b := os.Getenv("PF_KAFKA_BROKERS"); b != "" {
		cfg.KafkaBrokers = strings.Split(b, ",")
	}
	return cfg
}

func envOr(k, def string) string {
	if v := os.Getenv(k); v != "" {
		return v
	}
	return def
}

func main() {
	cfg := loadConfig()
	log.SetFlags(log.LstdFlags | log.Lmicroseconds)
	log.Printf("pf-bridge %s starting (listen=%s kafka=%v)", cfg.NodeID, cfg.Listen, cfg.KafkaBrokers)

	var pub Publisher
	var ring *Ring
	var closePub func() error

	if len(cfg.KafkaBrokers) > 0 {
		kp, err := newKafkaPublisher(cfg.KafkaBrokers, cfg.KafkaTopic, cfg.NodeID, 1024)
		if err != nil {
			log.Fatalf("kafka: %v", err)
		}
		pub, ring, closePub = kp, kp.Ring(), kp.Close
		log.Printf("publishing to kafka %s/%s", strings.Join(cfg.KafkaBrokers, ","), cfg.KafkaTopic)
	} else {
		jp, err := newJSONLPublisher(cfg.OutboxPath, 1024)
		if err != nil {
			log.Fatalf("outbox: %v", err)
		}
		pub, ring, closePub = jp, jp.Ring(), jp.Close
		log.Printf("publishing to outbox %s", cfg.OutboxPath)
	}

	bridge := NewBridge(cfg, pub, ring)
	mux := http.NewServeMux()
	bridge.Routes(mux)

	srv := &http.Server{
		Addr:              cfg.Listen,
		Handler:           mux,
		ReadHeaderTimeout: 10 * time.Second,
	}

	go func() {
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("listen: %v", err)
		}
	}()

	stop := make(chan os.Signal, 1)
	signal.Notify(stop, syscall.SIGINT, syscall.SIGTERM)
	<-stop
	log.Printf("shutting down")
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	_ = srv.Shutdown(ctx)
	_ = closePub()
}

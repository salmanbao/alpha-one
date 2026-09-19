package main

// Publisher: the bridge's output port (doc §4.3 bridge plane -> event backbone).
//
//   - JSONLPublisher: append-only outbox file + in-memory ring. This is the
//     scaffold default AND the pattern for production: the Kafka publish goes
//     through the same outbox (transactional outbox, doc §7.3) — the file is
//     the durable pre-Kafka stage.
//   - KafkaPublisher: real segmentio/kafka-go writer, partition key = account
//     (structural per-account ordering, doc §4.4).

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sync"
	"time"

	"github.com/segmentio/kafka-go"
)

// CanonicalEvent mirrors the canonical event schema (doc §5.3). Production:
// prost-generated types from contracts/proto (buf.gen.yaml).
type CanonicalEvent struct {
	Tenant   string          `json:"tenant"`
	Account  string          `json:"account"`
	Type     string          `json:"type"`
	EventID  string          `json:"event_id"`
	Seq      uint64          `json:"seq"`
	BrokerTS int64           `json:"broker_ts"`
	TServed  int64           `json:"ts_served"`
	Payload  json.RawMessage `json:"payload"`
}

type Publisher interface {
	Publish(ctx context.Context, ev CanonicalEvent) error
	Close() error
}

// Ring is an in-memory tail of published events (tests + ops dashboards).
type Ring struct {
	mu   sync.Mutex
	evs  []CanonicalEvent
	cap  int
}

func newRing(cap int) *Ring { return &Ring{cap: cap} }

func (r *Ring) Push(ev CanonicalEvent) {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.evs = append(r.evs, ev)
	if len(r.evs) > r.cap {
		r.evs = r.evs[len(r.evs)-r.cap:]
	}
}

func (r *Ring) All() []CanonicalEvent {
	r.mu.Lock()
	defer r.mu.Unlock()
	out := make([]CanonicalEvent, len(r.evs))
	copy(out, r.evs)
	return out
}

// JSONLPublisher appends each event as one line (durable outbox) and keeps a ring.
type JSONLPublisher struct {
	path string
	f    *os.File
	ring *Ring
	mu   sync.Mutex
}

func newJSONLPublisher(path string, ringCap int) (*JSONLPublisher, error) {
	if dir := filepath.Dir(path); dir != "" {
		if err := os.MkdirAll(dir, 0o755); err != nil {
			return nil, err
		}
	}
	f, err := os.OpenFile(path, os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0o644)
	if err != nil {
		return nil, err
	}
	return &JSONLPublisher{path: path, f: f, ring: newRing(ringCap)}, nil
}

func (p *JSONLPublisher) Publish(_ context.Context, ev CanonicalEvent) error {
	line, err := json.Marshal(ev)
	if err != nil {
		return err
	}
	p.mu.Lock()
	_, err = p.f.Write(append(line, '\n'))
	p.mu.Unlock()
	if err != nil {
		return err
	}
	p.ring.Push(ev)
	return nil
}

func (p *JSONLPublisher) Close() error { return p.f.Close() }

func (p *JSONLPublisher) Ring() *Ring { return p.ring }

// KafkaPublisher writes canonical events to the backbone (doc §4.4).
type KafkaPublisher struct {
	w    *kafka.Writer
	ring *Ring
}

func newKafkaPublisher(brokers []string, topic, clientID string, ringCap int) (*KafkaPublisher, error) {
	w := &kafka.Writer{
		Addr:                   kafka.TCP(brokers...),
		Topic:                  topic,
		Balancer:               &kafka.Hash{}, // partition key = account
		RequiredAcks:           kafka.RequireAll,
		AllowAutoTopicCreation: false,
		BatchTimeout:           5 * time.Millisecond, // doc §9.2 linger
	}
	// Topic is assumed provisioned (partitioned by account hash, doc §4.4);
	// auto-creation is left to the broker operator (AllowAutoTopicCreation=false).
	_ = clientID
	return &KafkaPublisher{w: w, ring: newRing(ringCap)}, nil
}

func (k *KafkaPublisher) Publish(ctx context.Context, ev CanonicalEvent) error {
	body, err := json.Marshal(ev)
	if err != nil {
		return err
	}
	if err := k.w.WriteMessages(ctx, kafka.Message{
		Key:   []byte(ev.Account), // doc §4.4: partition key = account_id
		Value: body,
		Headers: []kafka.Header{
			{Key: "tenant", Value: []byte(ev.Tenant)},
			{Key: "deal_id", Value: dealIDFrom(ev.Payload)},
		},
	}); err != nil {
		return err
	}
	k.ring.Push(ev)
	return nil
}

func (k *KafkaPublisher) Close() error { return k.w.Close() }

func (k *KafkaPublisher) Ring() *Ring { return k.ring }

// unified ring access
type RingProvider interface{ Ring() *Ring }

func dealIDFrom(payload json.RawMessage) []byte {
	var m map[string]any
	if json.Unmarshal(payload, &m) == nil {
		if d, ok := m["deal_id"].(string); ok {
			return []byte(d)
		}
	}
	return nil
}

var _ = fmt.Sprintf

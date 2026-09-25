// Package consumer is the platform's event-consumer supervisor — the
// docs/04 §3.5 pattern, implemented once and shared by every consumer
// (EVL's evaluation lane is the first; NOT/LED/AUD use the same package).
//
// Every consumer declares (docs/04 §3.5, verbatim):
//
//	name, topic, group (= name), acks: manual, dlq: dlq.{name},
//	idempotency: (event_id, consumer) upsert in consumer_state,
//	max_attempts: 5 with backoff 1 s × 2^k, timeout: 30 s.
//	Worker supervisor: per-consumer goroutine pool (per-entity serial lanes
//	via entity_id hash → N lanes, ordering preserved per entity).
//	At-least-once + idempotent = effectively-once for side effects.
//
// Nothing in this package knows about evaluation. The two places where
// docs/04 §3.5 is silent and an implementation must choose are recorded
// in docs/64 §4.10 and implemented here, generically:
//
//  1. **Stream ownership.** A Redis consumer group spreads entries across
//     its consumers round-robin, not by key, so two supervisor instances
//     reading one stream would put the same entity on two lanes. Each
//     stream is therefore owned by one instance at a time via a lease
//     (SET NX PX + compare-and-extend); instances scale out by owning
//     different streams (with D82, one stream per tenant).
//  2. **Permanent errors** (a malformed event, a 4xx from a downstream)
//     go to the DLQ on the first attempt instead of burning five.
package consumer

import (
	"context"
	"errors"
	"time"
)

// Spec is a consumer declaration (docs/04 §3.5). Zero values take the
// spec's defaults.
type Spec struct {
	// Name is the consumer name. Group = Name; DLQ stream = "dlq." + Name;
	// consumer_state.consumer = Name.
	Name string
	// MaxAttempts before the event is dead-lettered. Default 5.
	MaxAttempts int
	// BackoffBase: attempt k (1-based) that fails waits BackoffBase × 2^(k-1)
	// before attempt k+1. Default 1 s.
	BackoffBase time.Duration
	// Timeout per handler attempt. Default 30 s.
	Timeout time.Duration
	// ReadCount is the XREADGROUP COUNT. Default 256.
	ReadCount int64
	// Block is the XREADGROUP BLOCK. Default 2 s.
	Block time.Duration
	// LaneQueue is each lane's buffer; a full lane back-pressures only its
	// own stream's reader. Default 64.
	LaneQueue int
	// LeaseTTL is the stream-ownership lease; renewed every TTL/3.
	// Default 15 s.
	LeaseTTL time.Duration
}

// WithDefaults returns the spec with docs/04 §3.5's defaults filled in.
func (s Spec) WithDefaults() Spec {
	if s.MaxAttempts == 0 {
		s.MaxAttempts = 5
	}
	if s.BackoffBase == 0 {
		s.BackoffBase = time.Second
	}
	if s.Timeout == 0 {
		s.Timeout = 30 * time.Second
	}
	if s.ReadCount == 0 {
		s.ReadCount = 256
	}
	if s.Block == 0 {
		s.Block = 2 * time.Second
	}
	if s.LaneQueue == 0 {
		s.LaneQueue = 64
	}
	if s.LeaseTTL == 0 {
		s.LeaseTTL = 15 * time.Second
	}
	return s
}

// Group is the consumer-group name (= Name).
func (s Spec) Group() string { return s.Name }

// DLQ is the dead-letter stream (dlq.{name}).
func (s Spec) DLQ() string { return "dlq." + s.Name }

// Backoff is the wait after failed attempt k (1-based): base × 2^(k-1).
func (s Spec) Backoff(k int) time.Duration {
	if k < 1 {
		k = 1
	}
	return s.BackoffBase << (k - 1)
}

// Message is one delivered event.
type Message struct {
	// Stream the entry was read from ("" for injected replays).
	Stream string
	// RedisID is the stream entry id ("" for injected replays — nothing
	// to XACK).
	RedisID string
	// EventID is the envelope id (stream field `event_id`) — the
	// consumer_state key.
	EventID string
	// EntityID is the ordering key (stream field `entity_id`); the lane is
	// chosen by its hash.
	EntityID string
	// Tenant owning the stream.
	Tenant string
	// Payload is the full envelope (stream field `payload`).
	Payload []byte
	// Attempt is 1-based.
	Attempt int
	// Lane that is processing this message (for tests and logs).
	Lane int
}

// Handler processes one message. Return nil to ack, Permanent(err) to
// dead-letter now, any other error to retry with backoff.
type Handler func(ctx context.Context, m Message) error

type permanentError struct{ err error }

func (p permanentError) Error() string { return p.err.Error() }
func (p permanentError) Unwrap() error { return p.err }

// Permanent marks err as not worth retrying: the message is dead-lettered
// on this attempt.
func Permanent(err error) error {
	if err == nil {
		return nil
	}
	return permanentError{err}
}

// IsPermanent reports whether err (or anything it wraps) is Permanent.
func IsPermanent(err error) bool {
	var p permanentError
	return errors.As(err, &p)
}

package evl

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
	"log/slog"
	"time"

	"github.com/redis/go-redis/v9"

	"pf-platform/go/workers/consumer"
)

// ConsumerName is the consumer's docs/04 §3.5 name: group "evaluation",
// DLQ "dlq.evaluation", consumer_state.consumer = "evaluation".
const ConsumerName = "evaluation"

// FloorsChannel is the Redis pub/sub channel for floor-hint invalidation
// (docs/63 §4.4).
const FloorsChannel = "evl.floors"

// StreamKey is D82's per-tenant stream.
func StreamKey(tenant string) string { return "topic.bridge." + tenant }

// Handler is the evaluation lane's per-tick handler.
type Handler struct {
	DB      *sql.DB
	Redis   *redis.Client
	Engine  *Engine
	Metrics *consumer.Metrics
	Log     *slog.Logger
	// StaleAfter is the evl.tick_stale window (docs/09 §6): 10 min.
	StaleAfter time.Duration
	// Now is the clock (tests).
	Now func() time.Time
	// OnFundedStale is called when a funded account's tick is suppressed
	// as stale — an INCIDENT condition (D84) and shed level 3.
	OnFundedStale func(tenant string)
}

func (h *Handler) now() time.Time {
	if h.Now != nil {
		return h.Now()
	}
	return time.Now()
}

func (h *Handler) log() *slog.Logger {
	if h.Log != nil {
		return h.Log
	}
	return slog.Default()
}

// errVersionConflict: the guarded UPDATE matched no row — some other
// writer advanced the state. With lane ownership this is impossible; it is
// counted (evl_single_writer_violation_total) and retried from a fresh read.
var errVersionConflict = errors.New("evl.single_writer_violation")

// FloorsMessage is the evl.floors payload.
type FloorsMessage struct {
	TenantID          string `json:"tenant_id"`
	AccountID         string `json:"account_id"`
	FloorsVersion     int64  `json:"floors_version"`
	FloorDailyCents   *int64 `json:"floor_daily_cents"`
	FloorTotalCents   *int64 `json:"floor_total_cents"`
	TargetEquityCents *int64 `json:"target_equity_cents"`
}

// Handle processes one bridge.tick (docs/64 §6 step 1): read
// evaluation_state → /evaluate → write (new_state, verdict, hints) in one
// transaction with the consumer_state record → publish evl.floors.
func (h *Handler) Handle(ctx context.Context, m consumer.Message) error {
	env, tick, err := ParseTick(m.Payload)
	if err != nil {
		h.Metrics.Inc("evl_envelope_rejected_total", "tenant", m.Tenant)
		return consumer.Permanent(err)
	}
	if env.TenantID != m.Tenant {
		return consumer.Permanent(fmt.Errorf("evl: envelope tenant %s on stream of tenant %s", env.TenantID, m.Tenant))
	}
	if env.ID != m.EventID {
		return consumer.Permanent(fmt.Errorf("evl: stream event_id %s != envelope id %s", m.EventID, env.ID))
	}
	labels := []string{"tenant", env.TenantID}

	// 1. Redelivery: skip the engine call entirely.
	if seen, err := consumer.Seen(ctx, h.DB, ConsumerName, env.ID); err != nil {
		return err
	} else if seen {
		h.Metrics.Inc("evl_duplicate_total", labels...)
		return nil
	}

	// 2. Read state.
	t0 := time.Now()
	row, err := Load(ctx, h.DB, env.TenantID, tick.AccountID)
	h.Metrics.Observe("evl_pg_state_seconds", time.Since(t0).Seconds(), append(labels, "op", "read")...)
	if err != nil {
		return err
	}

	// 3. Staleness (docs/09 §6): tick age = now − occurred_at. Clock-
	// dependent, so it lives here, not in the (clock-free) engine.
	stale := h.StaleAfter
	if stale == 0 {
		stale = 10 * time.Minute
	}
	if age := h.now().Sub(time.UnixMilli(env.OccurredAt)); age > stale {
		err := consumer.Once(ctx, h.DB, ConsumerName, env.ID, consumer.StatusSkipped, nil)
		if err != nil && !errors.Is(err, consumer.ErrAlreadyProcessed) {
			return err
		}
		funded := fmt.Sprint(row.Funded)
		h.Metrics.Inc("evl_tick_stale_total", "tenant", env.TenantID, "funded", funded)
		h.log().Warn("evl.tick_stale", "tenant", env.TenantID, "account", tick.AccountID, "event_id", env.ID,
			"age_s", age.Seconds(), "funded", row.Funded)
		if row.Funded && h.OnFundedStale != nil {
			h.OnFundedStale(env.TenantID)
		}
		return nil
	}

	// 4. The engine call — outside any transaction.
	t1 := time.Now()
	resp, err := h.Engine.Evaluate(ctx, env.TenantID, env.CorrelationID, EvaluateRequest{
		State: row.State, Plan: row.Plan, Tick: json.RawMessage(m.Payload), EquitySource: "broker_reported",
	})
	h.Metrics.Observe("evl_evaluate_seconds", time.Since(t1).Seconds(), labels...)
	if errors.Is(err, ErrOutOfOrder) {
		err := consumer.Once(ctx, h.DB, ConsumerName, env.ID, consumer.StatusSkipped, nil)
		if err != nil && !errors.Is(err, consumer.ErrAlreadyProcessed) {
			return err
		}
		h.Metrics.Inc("evl_tick_out_of_order_total", labels...)
		h.log().Info("evl.tick_out_of_order", "tenant", env.TenantID, "account", tick.AccountID, "event_id", env.ID)
		return nil
	}
	if err != nil {
		h.Metrics.Inc("evl_engine_errors_total", labels...)
		return err
	}
	newVersion, err := StateVersion(resp.NewState)
	if err != nil || newVersion != row.Version+1 {
		return consumer.Permanent(fmt.Errorf("evl: engine returned new_state version %d (err %v) for version %d",
			newVersion, err, row.Version))
	}

	// 5. One transaction: consumer_state + guarded state write + verdict
	// record (+ outbox event when actionable).
	plan := row.Plan
	var newPlan []byte
	if len(resp.NewPlan) > 0 && string(resp.NewPlan) != "null" {
		plan, newPlan = resp.NewPlan, resp.NewPlan
	}
	evaluationID := NewULID()
	t2 := time.Now()
	err = consumer.Once(ctx, h.DB, ConsumerName, env.ID, consumer.StatusDone, func(tx *sql.Tx) error {
		var breachRule any
		if resp.Status == "breach" && resp.BreachRule != nil {
			breachRule = *resp.BreachRule
		}
		res, err := tx.ExecContext(ctx, `
			UPDATE evaluation_state
			   SET state = $3, plan = COALESCE($4::jsonb, plan), status = $5, funded = $6,
			       breach_rule_id = CASE WHEN $5 = 'breach' THEN $7 ELSE breach_rule_id END,
			       breach_at      = CASE WHEN $5 = 'breach' THEN now() ELSE breach_at END,
			       last_tick_event_id = $8, last_stream_seq = COALESCE($9, last_stream_seq),
			       last_tick_at = to_timestamp($10::double precision / 1000),
			       floor_daily_cents = $11, floor_total_cents = $12, target_equity_cents = $13,
			       floors_version = $14, version = $15, updated_at = now()
			 WHERE tenant_id = $1 AND account_id = $2 AND version = $16`,
			env.TenantID, tick.AccountID, []byte(resp.NewState), nullBytes(newPlan), resp.Status, IsFunded(plan),
			breachRule, env.ID, tick.StreamSeq, env.OccurredAt,
			resp.Hints.FloorDailyCents, resp.Hints.FloorTotalCents, resp.Hints.TargetEquityCents,
			resp.Hints.FloorsVersion, newVersion, row.Version)
		if err != nil {
			return err
		}
		if n, _ := res.RowsAffected(); n != 1 {
			h.Metrics.Inc("evl_single_writer_violation_total", labels...)
			h.log().Error("evl.single_writer_violation", "tenant", env.TenantID, "account", tick.AccountID,
				"expected_version", row.Version)
			return errVersionConflict
		}
		detail, _ := json.Marshal(map[string]any{
			"decision_kind": resp.DecisionKind, "winning_priority": resp.WinningPriority,
			"engine_pack_id": resp.PackID, "engine_pack_version": resp.PackVersion,
			"violations": resp.Violations, "evidence": resp.Evidence, "hints": resp.Hints,
		})
		if _, err := tx.ExecContext(ctx, `
			INSERT INTO evaluations (id, account_id, tenant_id, tick_event_id, input_hash, rule_pack_id,
			       rule_pack_version, status, rule_id, detail, state_version)
			VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)`,
			evaluationID, tick.AccountID, env.TenantID, env.ID, resp.InputHash, row.RulePackID,
			row.RulePackVersion, resp.Status, breachRule, detail, newVersion); err != nil {
			return err
		}
		if resp.Status == "breach" || resp.Status == "target_hit" || resp.Status == "gap_flagged" {
			return insertVerdict(ctx, tx, env, tick, resp, evaluationID, h.now())
		}
		return nil
	})
	h.Metrics.Observe("evl_pg_state_seconds", time.Since(t2).Seconds(), append(labels, "op", "write")...)
	if errors.Is(err, consumer.ErrAlreadyProcessed) {
		h.Metrics.Inc("evl_duplicate_total", labels...)
		return nil
	}
	if err != nil {
		return err
	}
	h.Metrics.Inc("evl_verdicts_total", "tenant", env.TenantID, "status", resp.Status)
	h.Metrics.Observe("evl_tick_to_commit_seconds", h.now().Sub(time.UnixMilli(env.OccurredAt)).Seconds(), labels...)

	// 6. After commit: advisory floor-hint invalidation. Best effort — the
	// bridge re-reads hints from PG every 30 s (docs/63 §4.4).
	fm, _ := json.Marshal(FloorsMessage{
		TenantID: env.TenantID, AccountID: tick.AccountID, FloorsVersion: resp.Hints.FloorsVersion,
		FloorDailyCents: resp.Hints.FloorDailyCents, FloorTotalCents: resp.Hints.FloorTotalCents,
		TargetEquityCents: resp.Hints.TargetEquityCents,
	})
	if h.Redis != nil {
		if err := h.Redis.Publish(ctx, FloorsChannel, fm).Err(); err != nil {
			h.Metrics.Inc("evl_floors_publish_errors_total", labels...)
			h.log().Warn("evl.floors_publish_failed", "tenant", env.TenantID, "err", err)
		}
	}
	return nil
}

func nullBytes(b []byte) any {
	if b == nil {
		return nil
	}
	return b
}

// insertVerdict writes the evaluation.verdict v1 event to the outbox in
// the same transaction (ADR-6) and rings the relay doorbell (D79).
func insertVerdict(ctx context.Context, tx *sql.Tx, env Envelope, tick TickPayload, resp *EvaluateResponse,
	evaluationID string, now time.Time) error {
	payload := map[string]any{
		"account_id": tick.AccountID, "verdict_id": evaluationID, "status": resp.Status,
		"input_hash": resp.InputHash, "broker_time": tick.BrokerTime,
	}
	if resp.Status == "breach" && resp.BreachRule != nil {
		payload["rule_id"] = *resp.BreachRule
	}
	eventID := NewULID()
	envelope, err := json.Marshal(map[string]any{
		"id": eventID, "type": "evaluation.verdict", "version": 1, "tenant_id": env.TenantID,
		"occurred_at": now.UnixMilli(), "correlation_id": env.CorrelationID, "payload": payload,
	})
	if err != nil {
		return err
	}
	if _, err := tx.ExecContext(ctx, `
		INSERT INTO outbox (event_id, topic, payload, tenant_id, entity_id, correlation_id)
		VALUES ($1, 'evaluation', $2, $3, $4, $5)`,
		eventID, envelope, env.TenantID, tick.AccountID, env.CorrelationID); err != nil {
		return err
	}
	_, err = tx.ExecContext(ctx, `SELECT pg_notify('outbox_doorbell', '')`)
	return err
}

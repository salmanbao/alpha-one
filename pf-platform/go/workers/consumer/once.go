package consumer

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
)

// consumer_state (contracts/data/schemas/04-gw-evt.sql):
//
//	(consumer, event_id) PK, status, attempts, last_error, processed_at
//
// status values written here:
//
//	done     — side effects committed (terminal)
//	skipped  — consumed with no side effect by design, e.g. an
//	           out-of-order or stale tick (terminal)
//	failed   — an attempt failed; attempts = the attempt number
//	dead     — dead-lettered; `relay dlq retry` re-publishes and the next
//	           delivery may complete it (dead is NOT terminal for dedupe)
const (
	StatusDone    = "done"
	StatusSkipped = "skipped"
	StatusFailed  = "failed"
	StatusDead    = "dead"
)

// ErrAlreadyProcessed is returned by Once when (consumer, event_id) is
// already done/skipped: the caller acks and does nothing.
var ErrAlreadyProcessed = errors.New("consumer: event already processed")

// Seen reports whether (consumer, event_id) is already terminal. A cheap
// pre-check that lets a consumer skip expensive work (an engine call) on
// redelivery; Once is still the authority.
func Seen(ctx context.Context, db *sql.DB, consumer, eventID string) (bool, error) {
	var status string
	err := db.QueryRowContext(ctx,
		`SELECT status FROM consumer_state WHERE consumer = $1 AND event_id = $2`,
		consumer, eventID).Scan(&status)
	if errors.Is(err, sql.ErrNoRows) {
		return false, nil
	}
	if err != nil {
		return false, err
	}
	return status == StatusDone || status == StatusSkipped, nil
}

// Once runs fn inside one transaction that also records
// (consumer, event_id) as terminal with the given status (done|skipped).
// If the event is already terminal, fn is not run and ErrAlreadyProcessed
// is returned. The consumer_state row is written first, so a concurrent
// duplicate delivery blocks on the row lock and then observes it as
// processed: exactly one transaction's side effects commit.
func Once(ctx context.Context, db *sql.DB, consumer, eventID, status string, fn func(tx *sql.Tx) error) error {
	if status != StatusDone && status != StatusSkipped {
		return fmt.Errorf("consumer: Once status must be done|skipped, got %q", status)
	}
	tx, err := db.BeginTx(ctx, nil)
	if err != nil {
		return err
	}
	defer func() { _ = tx.Rollback() }()

	res, err := tx.ExecContext(ctx, `
		INSERT INTO consumer_state (consumer, event_id, status, attempts, last_error, processed_at)
		VALUES ($1, $2, $3, 1, NULL, now())
		ON CONFLICT (consumer, event_id) DO UPDATE
		   SET status = EXCLUDED.status, processed_at = now(), last_error = NULL,
		       attempts = consumer_state.attempts + 1
		 WHERE consumer_state.status NOT IN ('done', 'skipped')`,
		consumer, eventID, status)
	if err != nil {
		return fmt.Errorf("consumer_state upsert: %w", err)
	}
	n, err := res.RowsAffected()
	if err != nil {
		return err
	}
	if n == 0 {
		return ErrAlreadyProcessed
	}
	if fn != nil {
		if err := fn(tx); err != nil {
			return err
		}
	}
	return tx.Commit()
}

// RecordFailure upserts the failure of attempt `attempt` (status failed,
// or dead when dead-lettered). It never downgrades a terminal row.
func RecordFailure(ctx context.Context, db *sql.DB, consumer, eventID string, attempt int, cause error, dead bool) error {
	status := StatusFailed
	if dead {
		status = StatusDead
	}
	msg := ""
	if cause != nil {
		msg = cause.Error()
		if len(msg) > 2000 {
			msg = msg[:2000]
		}
	}
	_, err := db.ExecContext(ctx, `
		INSERT INTO consumer_state (consumer, event_id, status, attempts, last_error)
		VALUES ($1, $2, $3, $4, $5)
		ON CONFLICT (consumer, event_id) DO UPDATE
		   SET status = EXCLUDED.status, attempts = EXCLUDED.attempts, last_error = EXCLUDED.last_error
		 WHERE consumer_state.status NOT IN ('done', 'skipped')`,
		consumer, eventID, status, attempt, msg)
	return err
}

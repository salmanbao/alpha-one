package evl

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
)

// StateRow is one evaluation_state row (contracts/data/schemas/09-evl.sql).
type StateRow struct {
	TenantID        string
	AccountID       string
	RulePackID      string
	RulePackVersion int
	State           json.RawMessage
	Plan            json.RawMessage
	Funded          bool
	Version         int64
}

// ErrNoState: no evaluation_state row for the account (not yet
// initialised). Retryable: the account.activated → state init may still be
// in flight; after max_attempts the tick is dead-lettered and `relay dlq
// retry` replays it once the state exists.
var ErrNoState = errors.New("evl.state_missing")

// Load reads the account's state row (keyed (tenant_id, account_id): prunes
// to one hash partition, D83).
func Load(ctx context.Context, db *sql.DB, tenant, account string) (*StateRow, error) {
	r := StateRow{TenantID: tenant, AccountID: account}
	err := db.QueryRowContext(ctx, `
		SELECT rule_pack_id, rule_pack_version, state, plan, funded, version
		  FROM evaluation_state WHERE tenant_id = $1 AND account_id = $2`,
		tenant, account).Scan(&r.RulePackID, &r.RulePackVersion, &r.State, &r.Plan, &r.Funded, &r.Version)
	if errors.Is(err, sql.ErrNoRows) {
		return nil, fmt.Errorf("%w: tenant %s account %s", ErrNoState, tenant, account)
	}
	if err != nil {
		return nil, err
	}
	return &r, nil
}

// IsFunded reads the plan's phase (engine plan document: "phase":"Funded").
func IsFunded(plan json.RawMessage) bool {
	var p struct {
		Phase string `json:"phase"`
	}
	_ = json.Unmarshal(plan, &p)
	return p.Phase == "Funded"
}

// StateVersion reads `version` from an engine state document.
func StateVersion(state json.RawMessage) (int64, error) {
	var s struct {
		Version *int64 `json:"version"`
	}
	if err := json.Unmarshal(state, &s); err != nil {
		return 0, err
	}
	if s.Version == nil {
		return 0, errors.New("state has no version")
	}
	return *s.Version, nil
}

// InitAccount creates the account's evaluation_state row from the engine's
// pure constructor (POST /internal/v1/state/init). Idempotent: an existing
// row is left untouched. This is what an account.activated handler calls
// once the activation event carries the bound plan/pack (docs/64 O-1).
func InitAccount(ctx context.Context, db *sql.DB, eng *Engine, req InitRequest, rulePackID string, rulePackVersion int) (bool, error) {
	out, err := eng.InitState(ctx, req)
	if err != nil {
		return false, err
	}
	res, err := db.ExecContext(ctx, `
		INSERT INTO evaluation_state (tenant_id, account_id, rule_pack_id, rule_pack_version, state, plan,
		       status, funded, floor_daily_cents, floor_total_cents, target_equity_cents, floors_version, version)
		VALUES ($1, $2, $3, $4, $5, $6, 'ok', $7, $8, $9, $10, $11, 0)
		ON CONFLICT (tenant_id, account_id) DO NOTHING`,
		req.TenantID, req.AccountID, rulePackID, rulePackVersion, []byte(out.State), []byte(out.Plan),
		IsFunded(out.Plan), out.Hints.FloorDailyCents, out.Hints.FloorTotalCents, out.Hints.TargetEquityCents,
		out.Hints.FloorsVersion)
	if err != nil {
		return false, err
	}
	n, _ := res.RowsAffected()
	return n == 1, nil
}

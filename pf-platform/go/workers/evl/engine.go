package evl

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"time"

	"pf-platform/go/workers/consumer"
)

// Engine is the client for the stateless engine (propfirm-engine,
// `server` feature; docs/64 §4.3).
type Engine struct {
	BaseURL string
	Token   string // service bearer (engine: PROPFIRM_SERVICE_TOKENS=workers:active:<sha256>)
	HTTP    *http.Client
}

// Hints is docs/09 §3.8 / docs/64 §4.5.
type Hints struct {
	FloorDailyCents   *int64 `json:"floor_daily_cents"`
	FloorTotalCents   *int64 `json:"floor_total_cents"`
	TargetEquityCents *int64 `json:"target_equity_cents"`
	FloorsVersion     int64  `json:"floors_version"`
}

// EvaluateRequest is POST /internal/v1/evaluate. `Tick` is the bridge.tick
// envelope exactly as consumed (validated by ParseTick).
type EvaluateRequest struct {
	State        json.RawMessage `json:"state"`
	Plan         json.RawMessage `json:"plan"`
	Tick         json.RawMessage `json:"tick"`
	EquitySource string          `json:"equity_source"`
}

// EvaluateResponse is the /evaluate response (fields workers uses).
type EvaluateResponse struct {
	Status          string          `json:"status"`
	DecisionKind    string          `json:"decision_kind"`
	WinningPriority int             `json:"winning_priority"`
	BreachRule      *string         `json:"breach_rule"`
	InputHash       string          `json:"input_hash"`
	PackID          string          `json:"pack_id"`
	PackVersion     int             `json:"pack_version"`
	Violations      json.RawMessage `json:"violations"`
	NewState        json.RawMessage `json:"new_state"`
	NewPlan         json.RawMessage `json:"new_plan"`
	Hints           Hints           `json:"hints"`
	Evidence        json.RawMessage `json:"evidence"`
}

// InitRequest is POST /internal/v1/state/init.
type InitRequest struct {
	AccountID string          `json:"account_id"`
	TenantID  string          `json:"tenant_id"`
	Plan      json.RawMessage `json:"plan,omitempty"`
	Preset    string          `json:"preset,omitempty"`
	StartedAt int64           `json:"started_at"`
}

// InitResponse is the state/init response.
type InitResponse struct {
	State json.RawMessage `json:"state"`
	Plan  json.RawMessage `json:"plan"`
	Hints Hints           `json:"hints"`
}

// ErrOutOfOrder is the engine's 409 evl.tick_out_of_order: ack and skip.
var ErrOutOfOrder = errors.New("evl.tick_out_of_order")

// EngineError is a non-2xx engine response.
type EngineError struct {
	Status  int
	Code    string
	Message string
}

func (e *EngineError) Error() string {
	return fmt.Sprintf("engine %d %s: %s", e.Status, e.Code, e.Message)
}

// classify maps an engine error response onto the consumer's retry
// semantics (docs/64 §4.3's error contract):
//
//	409                 → ErrOutOfOrder (the handler acks + skips)
//	400/404/413/422     → Permanent (malformed/inconsistent: DLQ now)
//	401/403             → retryable — a credential/config fault; dead-
//	                      lettering every tick would turn a rotation
//	                      mistake into mass DLQ, so let the lag alert fire
//	5xx, network, other → retryable
func classify(e *EngineError) error {
	switch {
	case e.Status == http.StatusConflict:
		return fmt.Errorf("%w: %s", ErrOutOfOrder, e.Message)
	case e.Status == 400 || e.Status == 404 || e.Status == 413 || e.Status == 422:
		return consumer.Permanent(e)
	default:
		return e
	}
}

func (c *Engine) client() *http.Client {
	if c.HTTP != nil {
		return c.HTTP
	}
	return &http.Client{Timeout: 10 * time.Second}
}

func (c *Engine) post(ctx context.Context, path, tenant, correlation string, in, out any) error {
	body, err := json.Marshal(in)
	if err != nil {
		return consumer.Permanent(err)
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.BaseURL+path, bytes.NewReader(body))
	if err != nil {
		return consumer.Permanent(err)
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+c.Token)
	req.Header.Set("X-Tenant-Id", tenant)
	if correlation != "" {
		req.Header.Set("X-Correlation-Id", correlation)
	}
	resp, err := c.client().Do(req)
	if err != nil {
		return fmt.Errorf("engine %s: %w", path, err) // retryable
	}
	defer resp.Body.Close()
	b, err := io.ReadAll(io.LimitReader(resp.Body, 16<<20))
	if err != nil {
		return fmt.Errorf("engine %s: read: %w", path, err)
	}
	if resp.StatusCode != http.StatusOK {
		ee := &EngineError{Status: resp.StatusCode}
		var eb struct {
			Code    string `json:"code"`
			Message string `json:"message"`
		}
		if json.Unmarshal(b, &eb) == nil {
			ee.Code, ee.Message = eb.Code, eb.Message
		} else {
			ee.Message = string(b)
		}
		return classify(ee)
	}
	if err := json.Unmarshal(b, out); err != nil {
		return fmt.Errorf("engine %s: decode: %w", path, err)
	}
	return nil
}

// Evaluate calls POST /internal/v1/evaluate.
func (c *Engine) Evaluate(ctx context.Context, tenant, correlation string, req EvaluateRequest) (*EvaluateResponse, error) {
	var out EvaluateResponse
	if err := c.post(ctx, "/internal/v1/evaluate", tenant, correlation, req, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

// InitState calls POST /internal/v1/state/init.
func (c *Engine) InitState(ctx context.Context, req InitRequest) (*InitResponse, error) {
	var out InitResponse
	if err := c.post(ctx, "/internal/v1/state/init", req.TenantID, "", req, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

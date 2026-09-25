// Package enginestub is an in-process double of the stateless engine's
// HTTP contract (docs/64 §4.3) for workers tests and local load runs where
// the Rust engine is not built. It follows the contract's shapes and error
// codes; the rule math is a simplified static/daily floor. CI's e2e job
// runs the same tests against the real engine (ENGINE_URL).
package enginestub

import (
	"encoding/json"
	"fmt"
	"math"
	"net/http"
	"sync"
	"sync/atomic"
	"time"
)

// Stub is the fake engine.
type Stub struct {
	Token string
	// Delay per /evaluate (simulated engine latency).
	Delay time.Duration
	// Hook runs inside /evaluate before responding (tests).
	Hook func(tenant string, tick map[string]any)
	// FailWith400 makes /evaluate return 400 when payload.broker_login
	// equals this value.
	FailWith400 string

	Calls atomic.Int64
	mu    sync.Mutex
}

type state struct {
	Version     int64  `json:"version"`
	LastTickMs  *int64 `json:"last_tick_ts_ms"`
	Status      string `json:"status"`
	EquityCents int64  `json:"equity_cents"`
	DayStart    int64  `json:"day_start_equity_cents"`
	TenantID    string `json:"tenant_id"`
	AccountID   string `json:"id"`
}

type plan struct {
	Phase        string  `json:"phase"`
	InitialCents int64   `json:"initial_cents"`
	DailyPct     float64 `json:"daily_pct"`
	TotalPct     float64 `json:"total_pct"`
	TargetPct    float64 `json:"target_pct"`
}

func writeErr(w http.ResponseWriter, status int, code, msg string) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(map[string]string{"code": code, "message": msg})
}

func (s *Stub) hints(st state, p plan) map[string]any {
	if st.Status != "Active" {
		return map[string]any{"floor_daily_cents": nil, "floor_total_cents": nil, "target_equity_cents": nil, "floors_version": st.Version}
	}
	daily := int64(math.Ceil(float64(st.DayStart)*(1-p.DailyPct))) - 2
	total := int64(math.Ceil(float64(p.InitialCents)*(1-p.TotalPct))) - 2
	var target any
	if p.TargetPct > 0 {
		target = int64(math.Ceil(float64(p.InitialCents) * (1 + p.TargetPct)))
	}
	return map[string]any{"floor_daily_cents": daily, "floor_total_cents": total, "target_equity_cents": target, "floors_version": st.Version}
}

// ServeHTTP implements the contract routes.
func (s *Stub) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	if r.Header.Get("Authorization") != "Bearer "+s.Token {
		writeErr(w, 401, "unauthorized", "bad bearer")
		return
	}
	tenant := r.Header.Get("X-Tenant-Id")
	if tenant == "" {
		writeErr(w, 400, "evl.bad_request", "X-Tenant-Id required")
		return
	}
	switch r.URL.Path {
	case "/internal/v1/state/init":
		var req struct {
			AccountID string `json:"account_id"`
			TenantID  string `json:"tenant_id"`
			Preset    string `json:"preset"`
			StartedAt int64  `json:"started_at"`
		}
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			writeErr(w, 400, "evl.bad_request", err.Error())
			return
		}
		p := plan{Phase: "Phase1", InitialCents: 1_000_000, DailyPct: 0.05, TotalPct: 0.10, TargetPct: 0.10}
		if req.Preset == "ftmo_funded" {
			p = plan{Phase: "Funded", InitialCents: 1_000_000, DailyPct: 0.05, TotalPct: 0.10}
		}
		st := state{Version: 0, Status: "Active", EquityCents: p.InitialCents, DayStart: p.InitialCents,
			TenantID: req.TenantID, AccountID: req.AccountID}
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]any{"state": st, "plan": p, "hints": s.hints(st, p)})
	case "/internal/v1/evaluate":
		s.Calls.Add(1)
		var req struct {
			State        state           `json:"state"`
			Plan         plan            `json:"plan"`
			Tick         json.RawMessage `json:"tick"`
			EquitySource string          `json:"equity_source"`
		}
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			writeErr(w, 400, "evl.bad_request", err.Error())
			return
		}
		var env struct {
			ID       string         `json:"id"`
			TenantID string         `json:"tenant_id"`
			Payload  map[string]any `json:"payload"`
		}
		if err := json.Unmarshal(req.Tick, &env); err != nil {
			writeErr(w, 400, "evl.bad_request", err.Error())
			return
		}
		if env.TenantID != tenant || req.State.TenantID != tenant {
			writeErr(w, 400, "evl.bad_request", "tenant mismatch")
			return
		}
		if s.FailWith400 != "" && env.Payload["broker_login"] == s.FailWith400 {
			writeErr(w, 400, "evl.bad_request", "stub: forced 400")
			return
		}
		if s.Hook != nil {
			s.Hook(tenant, env.Payload)
		}
		if s.Delay > 0 {
			time.Sleep(s.Delay)
		}
		bt := int64(env.Payload["broker_time"].(float64))
		if req.State.LastTickMs != nil && bt <= *req.State.LastTickMs {
			writeErr(w, 409, "evl.tick_out_of_order", fmt.Sprintf("tick %d not after %d", bt, *req.State.LastTickMs))
			return
		}
		eq := int64(env.Payload["equity_cents"].(float64))
		st := req.State
		st.Version++
		st.LastTickMs = &bt
		st.EquityCents = eq
		status, kind := "ok", "Pass"
		var breach any
		h := s.hints(req.State, req.Plan)
		if st.Status == "Active" {
			if d, ok := h["floor_daily_cents"].(int64); ok && eq <= d {
				status, kind, breach, st.Status = "breach", "Liquidate", "daily_drawdown", "Failed"
			} else if t, ok := h["floor_total_cents"].(int64); ok && eq <= t {
				status, kind, breach, st.Status = "breach", "Liquidate", "max_drawdown", "Failed"
			}
		}
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]any{
			"status": status, "decision_kind": kind, "winning_priority": 0, "breach_rule": breach,
			"input_hash": fmt.Sprintf("stub-%s-%d", env.ID, st.Version), "pack_id": "stub", "pack_version": 1,
			"violations": []any{}, "new_state": st, "new_plan": nil, "hints": s.hints(st, req.Plan),
			"evidence": map[string]any{"trigger": env.Payload["trigger"]},
		})
	default:
		writeErr(w, 404, "evl.bad_request", "no route")
	}
}

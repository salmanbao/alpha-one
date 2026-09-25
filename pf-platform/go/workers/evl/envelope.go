// Package evl is the `workers` evaluation consumer (docs/64 §6 step 1):
// consume bridge.tick from the tenant's stream on the account's serial
// lane, read evaluation_state, call the stateless engine's /evaluate,
// and write (new_state, verdict, hints) back in one transaction — the
// only writer of evaluation_state.
package evl

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"reflect"
	"regexp"
	"sort"
	"strings"
)

// ULIDPattern is envelope.schema.json#/$defs/ULID.
var ULIDPattern = regexp.MustCompile(`^[0-9A-HJKMNP-TV-Z]{26}$`)

// Envelope is contracts/events/payloads/envelope.schema.json (strict:
// additionalProperties false, all fields required).
type Envelope struct {
	ID            string          `json:"id"`
	Type          string          `json:"type"`
	Version       int             `json:"version"`
	TenantID      string          `json:"tenant_id"`
	OccurredAt    int64           `json:"occurred_at"`
	CorrelationID string          `json:"correlation_id"`
	Payload       json.RawMessage `json:"payload"`
}

// TickPosition is bridge.tick.v1.json#/…/positions/items.
type TickPosition struct {
	PositionID      string       `json:"position_id"`
	Symbol          string       `json:"symbol"`
	Side            string       `json:"side"`
	Lots            json.Number  `json:"lots"`
	OpenPrice       json.Number  `json:"open_price"`
	CurrentPrice    *json.Number `json:"current_price,omitempty"`
	SL              *json.Number `json:"sl,omitempty"`
	TP              *json.Number `json:"tp,omitempty"`
	OpenedAt        int64        `json:"opened_at"`
	ProfitCents     *int64       `json:"profit_cents,omitempty"`
	SwapCents       *int64       `json:"swap_cents,omitempty"`
	CommissionCents *int64       `json:"commission_cents,omitempty"`
}

// TickPayload is bridge.tick.v1.json's payload. I-29: the set of JSON
// names here must equal the schema's properties (asserted by
// TestTickStructMatchesSchema).
type TickPayload struct {
	AccountID       string         `json:"account_id"`
	BrokerLogin     string         `json:"broker_login"`
	EquityCents     int64          `json:"equity_cents"`
	BalanceCents    int64          `json:"balance_cents"`
	MarginCents     int64          `json:"margin_cents"`
	FreeMarginCents int64          `json:"free_margin_cents"`
	Leverage        string         `json:"leverage"`
	Positions       []TickPosition `json:"positions"`
	DealsCount      int64          `json:"deals_count"`
	LastDealTicket  int64          `json:"last_deal_ticket"`
	BrokerTime      int64          `json:"broker_time"`
	Trigger         *string        `json:"trigger,omitempty"`
	Source          *string        `json:"source,omitempty"`
	StreamSeq       *int64         `json:"stream_seq,omitempty"`
	EquityLowCents  *int64         `json:"equity_low_cents,omitempty"`
	EquityHighCents *int64         `json:"equity_high_cents,omitempty"`
}

var (
	envelopeRequired = []string{"id", "type", "version", "tenant_id", "occurred_at", "correlation_id", "payload"}
	tickRequired     = []string{"account_id", "broker_login", "equity_cents", "balance_cents", "margin_cents",
		"free_margin_cents", "leverage", "positions", "deals_count", "last_deal_ticket", "broker_time"}
	positionRequired = []string{"position_id", "symbol", "side", "lots", "open_price", "opened_at"}
	triggers         = map[string]bool{"deal": true, "position": true, "guard": true, "material": true, "heartbeat": true, "resync": true}
	sources          = map[string]bool{"stream": true, "poll": true, "resync": true}
)

// ErrSchema marks an envelope that does not conform to the contract.
var ErrSchema = errors.New("evl: bridge.tick does not conform to bridge.tick.v1.json")

// JSONFields returns the JSON property names a struct type declares.
func JSONFields(t reflect.Type) []string {
	var out []string
	for i := 0; i < t.NumField(); i++ {
		name, _, _ := strings.Cut(t.Field(i).Tag.Get("json"), ",")
		if name != "" && name != "-" {
			out = append(out, name)
		}
	}
	sort.Strings(out)
	return out
}

// strict decodes raw into dst, rejecting unknown and missing-required keys.
func strict(raw []byte, dst any, required []string, what string) error {
	var keys map[string]json.RawMessage
	if err := json.Unmarshal(raw, &keys); err != nil {
		return fmt.Errorf("%w: %s is not an object: %v", ErrSchema, what, err)
	}
	for _, k := range required {
		v, ok := keys[k]
		if !ok || string(v) == "null" {
			return fmt.Errorf("%w: %s.%s is required", ErrSchema, what, k)
		}
	}
	dec := json.NewDecoder(bytes.NewReader(raw))
	dec.DisallowUnknownFields()
	dec.UseNumber()
	if err := dec.Decode(dst); err != nil {
		return fmt.Errorf("%w: %s: %v", ErrSchema, what, err)
	}
	return nil
}

// ParseTick strictly validates a bridge.tick v1 envelope against the
// contract (envelope + payload + positions). The bytes that validate are
// the bytes forwarded to the engine, so every /evaluate request workers
// sends conforms to the schema (I-29).
func ParseTick(raw []byte) (Envelope, TickPayload, error) {
	var env Envelope
	var p TickPayload
	if err := strict(raw, &env, envelopeRequired, "envelope"); err != nil {
		return env, p, err
	}
	if env.Type != "bridge.tick" || env.Version != 1 {
		return env, p, fmt.Errorf("%w: type/version %q/%d, want bridge.tick/1", ErrSchema, env.Type, env.Version)
	}
	for k, v := range map[string]string{"id": env.ID, "tenant_id": env.TenantID, "correlation_id": env.CorrelationID} {
		if !ULIDPattern.MatchString(v) {
			return env, p, fmt.Errorf("%w: envelope.%s is not a ULID", ErrSchema, k)
		}
	}
	if env.OccurredAt < 0 {
		return env, p, fmt.Errorf("%w: envelope.occurred_at must be ≥ 0", ErrSchema)
	}
	if err := strict(env.Payload, &p, tickRequired, "payload"); err != nil {
		return env, p, err
	}
	if !ULIDPattern.MatchString(p.AccountID) {
		return env, p, fmt.Errorf("%w: payload.account_id is not a ULID", ErrSchema)
	}
	var rawPos struct {
		Positions []json.RawMessage `json:"positions"`
	}
	_ = json.Unmarshal(env.Payload, &rawPos)
	for i, rp := range rawPos.Positions {
		var tp TickPosition
		if err := strict(rp, &tp, positionRequired, fmt.Sprintf("payload.positions[%d]", i)); err != nil {
			return env, p, err
		}
		if tp.Side != "buy" && tp.Side != "sell" {
			return env, p, fmt.Errorf("%w: payload.positions[%d].side %q", ErrSchema, i, tp.Side)
		}
	}
	if p.DealsCount < 0 {
		return env, p, fmt.Errorf("%w: payload.deals_count must be ≥ 0", ErrSchema)
	}
	if p.Trigger != nil && !triggers[*p.Trigger] {
		return env, p, fmt.Errorf("%w: payload.trigger %q", ErrSchema, *p.Trigger)
	}
	if p.Source != nil && !sources[*p.Source] {
		return env, p, fmt.Errorf("%w: payload.source %q", ErrSchema, *p.Source)
	}
	return env, p, nil
}

// EntityOf extracts payload.account_id (the lane key) from an envelope.
func EntityOf(raw []byte) string {
	var e struct {
		Payload struct {
			AccountID string `json:"account_id"`
		} `json:"payload"`
	}
	_ = json.Unmarshal(raw, &e)
	return e.Payload.AccountID
}

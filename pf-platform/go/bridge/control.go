package main

// Control hub (doc §5.8): core -> terminal commands (halt, close-all, ...).
//
// Durable by construction: every command is (a) published to the event backbone
// and (b) recorded as PG state in production — the push is a latency
// optimization, the record is truth. Unacked commands are replayed on every
// reconnect/resync (doc §5.3: "a halt must survive terminal disconnects").

import (
	"context"
	"encoding/json"
	"sync"
)

type ControlCommand struct {
	CTLSeq    string         `json:"ctl_seq"`
	Tenant    string         `json:"tenant"`
	Account   string         `json:"account"`
	Command   string         `json:"command"` // trading_halt | resume_trading | close_all | close_symbol | set_param | snapshot_request | ...
	Reason    string         `json:"reason,omitempty"`
	Symbol    string         `json:"symbol,omitempty"`
	PackVer   string         `json:"pack_version,omitempty"`
	TTL       int64          `json:"ttl,omitempty"`
	Extra     map[string]any `json:"extra,omitempty"`
}

type ControlHub struct {
	pub  Publisher
	ring *Ring
	mu   sync.RWMutex
	// session pushers: tenant\x00account -> func(frame map[string]any) error
	pushers map[string]func(map[string]any) error
}

func newControlHub(pub Publisher, ring *Ring) *ControlHub {
	return &ControlHub{pub: pub, ring: ring, pushers: map[string]func(map[string]any) error{}}
}

// Register wires a live session's push function (WS write).
func (h *ControlHub) Register(tenant, account string, push func(map[string]any) error) {
	h.mu.Lock()
	defer h.mu.Unlock()
	h.pushers[pairingKey(tenant, account)] = push
}

func (h *ControlHub) Unregister(tenant, account string) {
	h.mu.Lock()
	defer h.mu.Unlock()
	delete(h.pushers, pairingKey(tenant, account))
}

// Publish persists the command, then pushes it to the live terminal (if any).
func (h *ControlHub) Publish(ctx context.Context, cmd ControlCommand) error {
	if cmd.CTLSeq == "" {
		cmd.CTLSeq = newULID()
	}
	payload, err := json.Marshal(cmd)
	if err != nil {
		return err
	}
	if err := h.pub.Publish(ctx, CanonicalEvent{
		Tenant: cmd.Tenant, Account: cmd.Account, Type: "control",
		EventID: cmd.CTLSeq, BrokerTS: 0, TServed: nowMillis(), Payload: payload,
	}); err != nil {
		return err
	}

	h.mu.RLock()
	push, ok := h.pushers[pairingKey(cmd.Tenant, cmd.Account)]
	h.mu.RUnlock()
	frame := map[string]any{
		"v": 1, "kind": "ctl", "type": cmd.Command,
		"tenant": cmd.Tenant, "account": cmd.Account,
		"ctl_seq": cmd.CTLSeq,
	}
	for k, v := range map[string]any{
		"reason": cmd.Reason, "symbol": cmd.Symbol, "pack_version": cmd.PackVer,
		"ttl": cmd.TTL, "extra": cmd.Extra,
	} {
		if v != nil && v != "" {
			frame[k] = v
		}
	}
	if ok {
		_ = push(frame)
	}
	return nil
}

var _ = sync.Once{}

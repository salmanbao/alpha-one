package main

// Bridge: the node. Owns connections and the per-message path:
//
//	WS frame / REST body
//	  -> Envelope
//	  -> hello?  -> pairing verify -> session bootstrap -> auth_ok
//	  -> ev?     -> Guard.Verify -> CanonicalEvent -> Publisher (Kafka/file)
//	  -> snap?   -> checksum verify -> resync_complete (+ pending ctl replay)
//	  -> hb?     -> echo
//
// Production notes are marked inline (Redis session store, Rust guard RPC,
// batched acks, chunked snapshots).

import (
	"context"
	"encoding/hex"
	"encoding/json"
	"errors"
	"log"
	"net/http"
	"strings"
	"sync"
	"time"

	"github.com/gorilla/websocket"
)

type Bridge struct {
	cfg      Config
	keystore *Keystore
	sessions *SessionStore
	pub      Publisher
	ring     *Ring
	ctl      *ControlHub
}

func NewBridge(cfg Config, pub Publisher, ring *Ring) *Bridge {
	b := &Bridge{
		cfg:      cfg,
		keystore: newKeystore(),
		sessions: newSessionStore(cfg.NodeID),
		pub:      pub,
		ring:     ring,
	}
	b.ctl = newControlHub(pub, ring)
	return b
}

func nowMillis() int64 { return time.Now().UnixMilli() }

// ---------------------------------------------------------------------------
// HTTP surface

func (b *Bridge) Routes(mux *http.ServeMux) {
	mux.HandleFunc("GET /healthz", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"ok":true,"sessions":` + itoa(b.sessions.Count()) + `}`))
	})
	// Pairing bootstrap (doc §5.5) — in production this lives behind the
	// trader-portal auth (the EA is not the one calling it).
	mux.HandleFunc("POST /v1/bridge/pair", b.handlePair)
	mux.HandleFunc("GET /v1/bridge/ws", b.handleWS)
	mux.HandleFunc("POST /v1/bridge/events", b.handleREST)
	mux.HandleFunc("POST /v1/bridge/control", b.handleControl)
}

func (b *Bridge) handlePair(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Tenant  string `json:"tenant"`
		Account string `json:"account"`
		Platform string `json:"platform"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil || req.Tenant == "" || req.Account == "" {
		http.Error(w, `{"error":"tenant and account required"}`, http.StatusBadRequest)
		return
	}
	p, key, err := b.keystore.CreatePairing(req.Tenant, req.Account, req.Platform)
	if err != nil {
		http.Error(w, `{"error":"key generation failed"}`, http.StatusInternalServerError)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(map[string]any{
		"tenant": p.Tenant, "account": p.Account,
		"pairing_key": key, // shown once (doc §8.2)
	})
}

// handleControl is the admin/test surface for pushing control commands
// (production: the challenge/risk services publish via the control topic).
func (b *Bridge) handleControl(w http.ResponseWriter, r *http.Request) {
	var cmd ControlCommand
	if err := json.NewDecoder(r.Body).Decode(&cmd); err != nil || cmd.Tenant == "" || cmd.Account == "" || cmd.Command == "" {
		http.Error(w, `{"error":"tenant, account, command required"}`, http.StatusBadRequest)
		return
	}
	if err := b.ctl.Publish(r.Context(), cmd); err != nil {
		http.Error(w, `{"error":"`+err.Error()+`"}`, http.StatusInternalServerError)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(map[string]any{"ok": true, "ctl_seq": cmd.CTLSeq})
}

// handleREST: MT4/REST clients post envelopes (single or batched, doc §5.1).
// Sessions are created via POST hello in the same body shape as the WS frame.
func (b *Bridge) handleREST(w http.ResponseWriter, r *http.Request) {
	var raw json.RawMessage
	if err := json.NewDecoder(r.Body).Decode(&raw); err != nil {
		http.Error(w, `{"error":"invalid json"}`, http.StatusBadRequest)
		return
	}
	var envs []Envelope
	trimmed := strings.TrimSpace(string(raw))
	if strings.HasPrefix(trimmed, "[") {
		if err := json.Unmarshal(raw, &envs); err != nil {
			http.Error(w, `{"error":"invalid batch"}`, http.StatusBadRequest)
			return
		}
	} else {
		var e Envelope
		if err := json.Unmarshal(raw, &e); err != nil {
			http.Error(w, `{"error":"invalid envelope"}`, http.StatusBadRequest)
			return
		}
		envs = []Envelope{e}
	}

	type result struct {
		Seq   uint64   `json:"seq"`
		OK    bool     `json:"ok"`
		Code  string   `json:"code,omitempty"`
		Detail string  `json:"detail,omitempty"`
	}
	results := make([]result, 0, len(envs))
	for i := range envs {
		env := &envs[i]
		env.TsServer = nowMillis()
		ok, code, detail := b.process(env)
		results = append(results, result{Seq: env.Seq, OK: ok, Code: string(code), Detail: detail})
	}
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(results)
}

// ---------------------------------------------------------------------------
// WebSocket

var upgrader = websocket.Upgrader{
	ReadBufferSize:  4096,
	WriteBufferSize: 8192,
}

func (b *Bridge) handleWS(w http.ResponseWriter, r *http.Request) {
	conn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		log.Printf("ws upgrade: %v", err)
		return
	}

	type pendingWrite struct{ frame []byte }
	writes := make(chan []byte, 256)
	done := make(chan struct{})

	push := func(frame map[string]any) error {
		b, err := json.Marshal(frame)
		if err != nil {
			return err
		}
		select {
		case writes <- b:
			return nil
		default:
			return errors.New("write queue full (backpressure)")
		}
	}

	go func() {
		defer close(done)
		for {
			select {
			case f := <-writes:
				if err := conn.WriteMessage(websocket.TextMessage, f); err != nil {
					return
				}
			case <-done:
				return
			}
		}
	}()

	var bound *Session
	connectedAt := time.Now()
	defer func() {
		if bound != nil {
			b.sessions.Delete(bound.Tenant, bound.Account)
			b.ctl.Unregister(bound.Tenant, bound.Account)
		}
		conn.Close()
	}()

	for {
		_, data, err := conn.ReadMessage()
		if err != nil {
			log.Printf("ws %s: read end: %v", connectedAt, err)
			return
		}
		var env Envelope
		if err := json.Unmarshal(data, &env); err != nil {
			_ = push(map[string]any{"v": 1, "kind": "reject", "code": "malformed", "reason": err.Error()})
			continue
		}
		env.TsServer = nowMillis()

		switch env.Kind {
		case "hello":
			s, ok := b.handleHello(&env, push)
			if !ok {
				return // rejected; connection closed by the handler's reject
			}
			bound = s
			b.ctl.Register(s.Tenant, s.Account, push)

		case "ev":
			if bound == nil {
				_ = push(reject(0, GuardNoSession, "auth first"))
				continue
			}
			b.processWithWS(bound, &env, push)

		case "snap":
			if bound == nil {
				_ = push(reject(0, GuardNoSession, "auth first"))
				continue
			}
			b.handleSnapshot(bound, &env, push)

		case "hb":
			_ = push(map[string]any{"v": 1, "kind": "hb", "ts_server": nowMillis()})

		case "ctl_ack":
			// terminal acked a control command; in production this clears the
			// pending-ctl entry (kept in the session store / PG).
			log.Printf("ctl_ack from %s/%s: %v", bound.Tenant, bound.Account, env.Payload)

		default:
			_ = push(reject(env.Seq, GuardMalformed, "unknown kind "+env.Kind))
		}
	}
}

// handleHello bootstraps a session from a pairing-key-signed hello frame.
func (b *Bridge) handleHello(env *Envelope, push func(map[string]any) error) (*Session, bool) {
	pairing := b.keystore.Lookup(env.Tenant, env.Account)
	if v, err := verifyHello(env, pairing, time.Now()); v != GuardOK {
		_ = push(reject(0, v, guardDetail(err)))
		return nil, false
	}
	key, err := randomHex(32)
	if err != nil {
		_ = push(reject(0, GuardMalformed, err.Error()))
		return nil, false
	}
	keyBytes, _ := hex.DecodeString(key)
	s := newSession(env.Tenant, env.Account, keyBytes, b.cfg.NodeID, b.cfg.PackVersion)
	// resume: if a previous session existed (node move, doc §5.2), keep its seq
	if old := b.sessions.Get(env.Tenant, env.Account); old != nil {
		s.LastSeq = old.LastSeq
	}
	b.sessions.Put(s)

	_ = push(map[string]any{
		"v": 1, "kind": "auth_ok",
		"tenant": s.Tenant, "account": s.Account,
		"session_key":    key, // scaffold transport; v2: authenticated key exchange
		"pack_version":   s.PackVer,
		"last_confirmed_seq": s.LastSeq,
		"hb_interval_ms":   b.cfg.HBIntervalMs,
	})

	// replay unacked control commands (doc §5.8)
	for _, p := range s.takePending() {
		_ = push(map[string]any{"v": 1, "kind": "ctl", "type": p.Command, "ctl_seq": p.CTLSeq})
	}
	return s, true
}

// ---------------------------------------------------------------------------
// Core per-message path (shared by WS and REST)

// process is the REST path: returns (ok, code, detail).
func (b *Bridge) process(env *Envelope) (bool, GuardVerdict, string) {
	s := b.sessions.Get(env.Tenant, env.Account)
	v, err := verify(env, s, time.Now())
	if v != GuardOK {
		return false, v, guardDetail(err)
	}
	s.setLastSeq(env.Seq)
	b.ingest(s, env)
	return true, GuardOK, ""
}

// processWithWS is the WS path: sends ack/reject frames.
func (b *Bridge) processWithWS(s *Session, env *Envelope, push func(map[string]any) error) {
	v, err := verify(env, s, time.Now())
	switch v {
	case GuardOK:
		s.setLastSeq(env.Seq)
		b.ingest(s, env)
		_ = push(map[string]any{"v": 1, "kind": "ack", "seq": env.Seq, "account": s.Account})
	case GuardGap:
		// sequence gap => RESYNC (doc §5.2): request the snapshot, terminal
		// replies with kind=snap frames.
		s.markResync()
		_ = push(map[string]any{
			"v": 1, "kind": "ctl", "type": "snapshot_request",
			"tenant": s.Tenant, "account": s.Account,
			"reason": guardDetail(err),
		})
	default:
		_ = push(reject(env.Seq, v, guardDetail(err)))
		// bad_sig x3 would escalate to SUSPENDED + trust review (doc §7.5)
	}
}

// ingest maps the wire event to a canonical event and publishes it.
func (b *Bridge) ingest(s *Session, env *Envelope) {
	ev := CanonicalEvent{
		Tenant:   s.Tenant,
		Account:  s.Account,
		Type:     env.Type,
		EventID:  env.ID,
		Seq:      env.Seq,
		TServed:  env.TsServer,
		Payload:  env.Payload,
	}
	// broker_ts is carried inside the payload (broker-attested, doc §5.6)
	var p struct {
		BrokerTS int64 `json:"broker_ts"`
	}
	_ = json.Unmarshal(env.Payload, &p)
	ev.BrokerTS = p.BrokerTS

	if err := b.pub.Publish(context.Background(), ev); err != nil {
		log.Printf("publish %s/%s %s: %v", s.Tenant, s.Account, env.Type, err)
	}
}

func (b *Bridge) handleSnapshot(s *Session, env *Envelope, push func(map[string]any) error) {
	if s.State != StateResync {
		_ = push(reject(env.Seq, GuardMalformed, "snapshot without resync"))
		return
	}
	var sp SnapshotPayload
	if err := json.Unmarshal(env.Payload, &sp); err != nil {
		_ = push(reject(env.Seq, GuardMalformed, "bad snapshot payload: "+err.Error()))
		return
	}
	if sp.Final {
		if err := verifySnapshotChecksum(&sp); err != nil {
			_ = push(reject(env.Seq, GuardMalformed, err.Error()))
			return
		}
		// resume: baseline = expected next seq (the gap is bridged by the
		// snapshot). LastSeq stays at the last fully-applied seq, so the
		// client re-sends from there — strict monotonicity is preserved.
		baseline := s.LastSeq + 1
		s.markActive()
		_ = push(map[string]any{
			"v": 1, "kind": "resync_complete",
			"tenant": s.Tenant, "account": s.Account,
			"baseline_seq": baseline,
			"positions": len(sp.Positions),
			"deals": len(sp.Deals),
		})
		// replay pending control commands (doc §5.8)
		for _, p := range s.takePending() {
			_ = push(map[string]any{"v": 1, "kind": "ctl", "type": p.Command, "ctl_seq": p.CTLSeq})
		}
	}
}

// ---------------------------------------------------------------------------

func reject(seq uint64, v GuardVerdict, detail string) map[string]any {
	return map[string]any{"v": 1, "kind": "reject", "seq": seq, "code": string(v), "reason": detail}
}

func guardDetail(err error) string {
	var ge *GuardError
	if errors.As(err, &ge) {
		return ge.Detail
	}
	if err != nil {
		return err.Error()
	}
	return ""
}

func itoa(n int) string {
	return json.Number(intToString(n)).String()
}

func intToString(n int) string {
	if n == 0 {
		return "0"
	}
	neg := n < 0
	if neg {
		n = -n
	}
	var b []byte
	for n > 0 {
		b = append([]byte{byte('0' + n%10)}, b...)
		n /= 10
	}
	if neg {
		return "-" + string(b)
	}
	return string(b)
}

var _ = sync.Once{}

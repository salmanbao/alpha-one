package main

// End-to-end protocol test (doc §13): a real terminal client speaks the full
// wire protocol against a real bridge node over a real HTTP server:
//
//   pair -> ws hello -> auth_ok -> order_filled -> ack
//   -> replay attack -> reject(replay)
//   -> tampered sig   -> reject(bad_sig)
//   -> seq gap        -> ctl(snapshot_request) -> snap -> resync_complete
//   -> control halt   -> ctl(trading_halt)
//   -> REST path      -> same guard, same publisher

import (
	"bytes"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/gorilla/websocket"
)

const (
	testTenant  = "acme"
	testAccount = "778123"
)

// testEnv builds a signed envelope (the terminal-side counterpart).
func testEnv(t *testing.T, kind, typ, tenant, account string, seq uint64, nonce string, payload any, key []byte) Envelope {
	t.Helper()
	body, err := json.Marshal(payload)
	if err != nil {
		t.Fatal(err)
	}
	env := Envelope{
		V: 1, ID: newULID(), Kind: kind, Type: typ,
		Tenant: tenant, Account: account, Seq: seq,
		TsClient: time.Now().UnixMilli(), Nonce: nonce,
		Payload: body,
	}
	canonical, err := canonicalBytes(&env)
	if err != nil {
		t.Fatal(err)
	}
	env.Sig = sign(key, canonical)
	return env
}

func mustJSON(t *testing.T, v any) []byte {
	t.Helper()
	b, err := json.Marshal(v)
	if err != nil {
		t.Fatal(err)
	}
	return b
}

type wsFrame struct {
	Kind     string          `json:"kind"`
	Type     string          `json:"type"`
	Seq      uint64          `json:"seq"`
	Code     string          `json:"code"`
	Reason   string          `json:"reason"`
	Baseline uint64          `json:"baseline_seq"`
	Payload  json.RawMessage `json:"payload"`
	CTLSeq   string          `json:"ctl_seq"`
	SessionKey string        `json:"session_key"`
}

func startTestBridge(t *testing.T) (*httptest.Server, *Bridge, *Ring) {
	t.Helper()
	cfg := Config{Listen: "127.0.0.1:0", NodeID: "test-node", PackVersion: "v1", HBIntervalMs: 1000}
	pub, err := newJSONLPublisher(t.TempDir()+"/outbox.jsonl", 256)
	if err != nil {
		t.Fatal(err)
	}
	bridge := NewBridge(cfg, pub, pub.Ring())
	mux := http.NewServeMux()
	bridge.Routes(mux)
	srv := httptest.NewServer(mux)
	t.Cleanup(srv.Close)
	t.Cleanup(func() { _ = pub.Close() })
	return srv, bridge, pub.Ring()
}

func pair(t *testing.T, srv *httptest.Server) (string, []byte) {
	t.Helper()
	resp, err := http.Post(srv.URL+"/v1/bridge/pair", "application/json",
		bytes.NewReader(mustJSON(t, map[string]string{
			"tenant": testTenant, "account": testAccount, "platform": "mt5",
		})))
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != 200 {
		t.Fatalf("pair: %s", resp.Status)
	}
	var out struct {
		PairingKey string `json:"pairing_key"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&out); err != nil {
		t.Fatal(err)
	}
	key, err := hexDecode(out.PairingKey)
	if err != nil {
		t.Fatal(err)
	}
	return out.PairingKey, key
}

func readFrame(t *testing.T, conn *websocket.Conn, within time.Duration) wsFrame {
	t.Helper()
	deadline := time.Now().Add(within)
	for {
		err := conn.SetReadDeadline(deadline)
		if err != nil {
			t.Fatal(err)
		}
		_, data, err := conn.ReadMessage()
		if err != nil {
			t.Fatalf("read frame: %v", err)
		}
		var f wsFrame
		if err := json.Unmarshal(data, &f); err != nil {
			t.Fatalf("parse frame %s: %v", data, err)
		}
		return f
	}
}

func expectKind(t *testing.T, conn *websocket.Conn, kind string) wsFrame {
	t.Helper()
	f := readFrame(t, conn, 3*time.Second)
	if f.Kind != kind {
		t.Fatalf("expected kind %q, got %q (%+v)", kind, f.Kind, f)
	}
	return f
}

func TestFullProtocol(t *testing.T) {
	srv, _, ring := startTestBridge(t)
	_, pairKey := pair(t, srv)

	wsURL := "ws" + strings.TrimPrefix(srv.URL, "http") + "/v1/bridge/ws"
	conn, _, err := websocket.DefaultDialer.Dial(wsURL, nil)
	if err != nil {
		t.Fatal(err)
	}
	defer conn.Close()

	// 1. hello (pairing-key signed) -> auth_ok
	hello := testEnv(t, "hello", "hello", testTenant, testAccount, 0, "n-hello-1",
		map[string]string{"client_id": "dev-1", "app_ver": "0.1.0", "platform": "mt5"},
		pairKey)
	if err := conn.WriteJSON(hello); err != nil {
		t.Fatal(err)
	}
	ack := expectKind(t, conn, "auth_ok")
	sessKey, err := hexDecode(ack.SessionKey)
	if err != nil || len(sessKey) != 32 {
		t.Fatalf("bad session key: %v", err)
	}

	// 2. order_filled (session-key signed) -> ack
	fill := testEnv(t, "ev", "order_filled", testTenant, testAccount, 1, "n-1",
		map[string]any{
			"order_id": "o-1", "deal_id": "deal-1", "symbol": "EURUSD",
			"side": "buy", "volume": 1.0, "fill_px": "10000",
			"commission": "0", "broker_ts": time.Now().UnixMilli(),
		},
		sessKey)
	if err := conn.WriteJSON(fill); err != nil {
		t.Fatal(err)
	}
	a := expectKind(t, conn, "ack")
	if a.Seq != 1 {
		t.Fatalf("ack seq = %d, want 1", a.Seq)
	}
	evs := ring.All()
	if len(evs) != 1 || evs[0].Type != "order_filled" || string(evs[0].Payload) == "" {
		t.Fatalf("publisher missed the event: %+v", evs)
	}
	if evs[0].Account != testAccount || evs[0].Tenant != testTenant {
		t.Fatalf("event not tenant/account scoped: %+v", evs[0])
	}

	// 3. replay: same envelope again -> reject(replay)
	if err := conn.WriteJSON(fill); err != nil {
		t.Fatal(err)
	}
	rj := expectKind(t, conn, "reject")
	if rj.Code != string(GuardReplay) {
		t.Fatalf("expected replay reject, got %q (%s)", rj.Code, rj.Reason)
	}

	// 4. tampered signature -> reject(bad_sig)
	tampered := testEnv(t, "ev", "position_closed", testTenant, testAccount, 2, "n-2",
		map[string]any{"deal_id": "deal-9", "symbol": "EURUSD", "broker_ts": time.Now().UnixMilli()},
		sessKey)
	tampered.Sig = strings.Repeat("A", len(tampered.Sig))
	if err := conn.WriteJSON(tampered); err != nil {
		t.Fatal(err)
	}
	rj = expectKind(t, conn, "reject")
	if rj.Code != string(GuardBadSig) {
		t.Fatalf("expected bad_sig reject, got %q", rj.Code)
	}

	// 5. seq gap (seq 5 after acked 1) -> ctl(snapshot_request)
	gap := testEnv(t, "ev", "order_filled", testTenant, testAccount, 5, "n-5",
		map[string]any{"order_id": "o-5", "deal_id": "deal-5", "symbol": "EURUSD",
			"side": "sell", "volume": 0.5, "fill_px": "10100",
			"commission": "0", "broker_ts": time.Now().UnixMilli()},
		sessKey)
	if err := conn.WriteJSON(gap); err != nil {
		t.Fatal(err)
	}
	ctl := expectKind(t, conn, "ctl")
	if ctl.Type != "snapshot_request" {
		t.Fatalf("expected snapshot_request, got %q", ctl.Type)
	}

	// 6. terminal replies with a checksummed snapshot -> resync_complete
	snapPayload := SnapshotPayload{
		ChunkNo: 0, Final: true, Balance: "100000",
		Positions: []PositionDTO{{OrderID: "o-5", Symbol: "EURUSD", Side: "sell", Volume: "0.5", EntryPx: "10100", LastPx: "10100", BrokerTS: 1}},
		Deals:     []DealDTO{},
	}
	sum, err := ComputeSnapshotChecksum(snapPayload.Balance, snapPayload.Positions, snapPayload.Deals)
	if err != nil {
		t.Fatal(err)
	}
	snapPayload.Checksum = sum
	snap := testEnv(t, "snap", "snapshot", testTenant, testAccount, 0, "n-snap",
		snapPayload, sessKey)
	if err := conn.WriteJSON(snap); err != nil {
		t.Fatal(err)
	}
	rc := expectKind(t, conn, "resync_complete")
	if rc.Baseline != 2 {
		t.Fatalf("baseline seq = %d, want 2 (last acked 1 + 1)", rc.Baseline)
	}

	// 7. control halt pushed down the wire
	resp, err := http.Post(srv.URL+"/v1/bridge/control", "application/json",
		bytes.NewReader(mustJSON(t, ControlCommand{
			Tenant: testTenant, Account: testAccount,
			Command: "trading_halt", Reason: "daily loss breach",
		})))
	if err != nil {
		t.Fatal(err)
	}
	io.Copy(io.Discard, resp.Body)
	resp.Body.Close()
	if resp.StatusCode != 200 {
		t.Fatalf("control: %s", resp.Status)
	}
	ctl = expectKind(t, conn, "ctl")
	if ctl.Type != "trading_halt" || ctl.CTLSeq == "" {
		t.Fatalf("expected trading_halt with ctl_seq, got %+v", ctl)
	}
	// and it was durably published
	evs = ring.All()
	found := false
	for _, e := range evs {
		if e.Type == "control" {
			found = true
		}
	}
	if !found {
		t.Fatal("control command was not published to the backbone")
	}

	// 8. REST path: same guard, same publisher (MT4-style client)
	rest := testEnv(t, "ev", "position_closed", testTenant, testAccount, 2, "n-rest",
		map[string]any{
			"order_id": "o-5", "deal_id": "deal-6", "symbol": "EURUSD",
			"volume": 0.5, "entry_px": "10100", "exit_px": "10050",
			"pnl_reported": "25", "commission": "0", "swap": "0",
			"broker_ts": time.Now().UnixMilli(),
		},
		sessKey)
	body, _ := json.Marshal(rest)
	resp, err = http.Post(srv.URL+"/v1/bridge/events", "application/json", bytes.NewReader(body))
	if err != nil {
		t.Fatal(err)
	}
	io.Copy(io.Discard, resp.Body)
	resp.Body.Close()
	if resp.StatusCode != 200 {
		t.Fatalf("rest: %s", resp.Status)
	}
	evs = ring.All()
	if len(evs) != 3 {
		t.Fatalf("expected 3 published events, got %d", len(evs))
	}
	last := evs[len(evs)-1]
	if last.Type != "position_closed" || last.Seq != 2 {
		t.Fatalf("rest event not published correctly: %+v", last)
	}
}

// A frame from the WRONG tenant's session is rejected at the binding check
// even if it is perfectly signed (doc §4.5 tenant isolation).
func TestTenantBinding(t *testing.T) {
	srv, _, _ := startTestBridge(t)
	_, pairKey := pair(t, srv)

	wsURL := "ws" + strings.TrimPrefix(srv.URL, "http") + "/v1/bridge/ws"
	conn, _, err := websocket.DefaultDialer.Dial(wsURL, nil)
	if err != nil {
		t.Fatal(err)
	}
	defer conn.Close()

	hello := testEnv(t, "hello", "hello", testTenant, testAccount, 0, "n-h",
		map[string]string{"client_id": "dev-2", "app_ver": "0.1.0", "platform": "mt5"},
		pairKey)
	if err := conn.WriteJSON(hello); err != nil {
		t.Fatal(err)
	}
	ack := expectKind(t, conn, "auth_ok")
	sessKey, _ := hexDecode(ack.SessionKey)

	// signed with the right key, but claiming another tenant
	foreign := testEnv(t, "ev", "order_filled", "other-tenant", testAccount, 1, "n-x",
		map[string]any{"order_id": "o-x", "deal_id": "deal-x", "symbol": "EURUSD",
			"side": "buy", "volume": 1.0, "fill_px": "10000",
			"commission": "0", "broker_ts": time.Now().UnixMilli()},
		sessKey)
	if err := conn.WriteJSON(foreign); err != nil {
		t.Fatal(err)
	}
	rj := expectKind(t, conn, "reject")
	if rj.Code != string(GuardBinding) {
		t.Fatalf("expected binding reject, got %q (%s)", rj.Code, rj.Reason)
	}
}

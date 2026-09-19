package main

// Envelope + canonicalization (doc §5.3, §5.4).
//
// Canonical form for HMAC: a JSON ARRAY of fields in a fixed order
// [v, kind, type, tenant, account, seq, ts_client, nonce, payload],
// where payload is re-marshal-ized with sorted keys (json.Number preserves
// numeric tokens exactly). Fixed-order arrays remove all key-ordering ambiguity
// across implementations (Go / Rust / TS / MQL). Production v2 is protobuf
// wire bytes of the Envelope (doc §5.1); this JSON form is wire v1.

import (
	"bytes"
	"crypto/hmac"
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"sort"
)

func bytesReader(b []byte) *bytes.Reader { return bytes.NewReader(b) }
func readCrypto(b []byte) (int, error)  { return rand.Read(b) }

// Envelope wraps every frame on the wire (mirrors contracts/proto bridge.proto).
type Envelope struct {
	V        int64           `json:"v"`
	ID       string          `json:"id"`
	Kind     string          `json:"kind"` // ev | ctl | ack | snap | hb | hello | reject | auth_ok | resync_complete
	Type     string          `json:"type"`
	Tenant   string          `json:"tenant"`
	Account  string          `json:"account"`
	Seq      uint64          `json:"seq"`
	TsClient int64           `json:"ts_client"`
	TsServer int64           `json:"ts_server,omitempty"`
	Nonce    string          `json:"nonce"`
	Sig      string          `json:"sig"`
	Payload  json.RawMessage `json:"payload"`
}

// canonicalBytes produces the exact byte string that gets HMAC-signed.
func canonicalBytes(env *Envelope) ([]byte, error) {
	payloadNorm, err := normalizeJSON(env.Payload)
	if err != nil {
		return nil, err
	}
	arr := []any{env.V, env.Kind, env.Type, env.Tenant, env.Account, env.Seq, env.TsClient, env.Nonce, json.RawMessage(payloadNorm)}
	b, err := json.Marshal(arr)
	if err != nil {
		return nil, err
	}
	return b, nil
}

// normalizeJSON re-marshals a JSON value with sorted object keys, preserving
// numeric tokens (json.Number) so large ints don't lose precision via float64.
func normalizeJSON(raw json.RawMessage) ([]byte, error) {
	if len(raw) == 0 {
		return []byte("null"), nil
	}
	dec := json.NewDecoder(bytesReader(raw))
	dec.UseNumber()
	var v any
	if err := dec.Decode(&v); err != nil {
		return nil, err
	}
	return json.Marshal(sortKeys(v))
}

func sortKeys(v any) any {
	switch t := v.(type) {
	case map[string]any:
		keys := make([]string, 0, len(t))
		for k := range t {
			keys = append(keys, k)
		}
		sort.Strings(keys)
		out := make([]any, 0, len(keys))
		for _, k := range keys {
			out = append(out, k, sortKeys(t[k]))
		}
		// build an ordered object via a map (Go sorts keys on marshal anyway)
		m := make(map[string]any, len(t))
		for k, val := range t {
			m[k] = sortKeys(val)
		}
		return m
	case []any:
		for i := range t {
			t[i] = sortKeys(t[i])
		}
		return t
	default:
		return v
	}
}

func sign(key []byte, canonical []byte) string {
	mac := hmac.New(sha256.New, key)
	mac.Write(canonical)
	return base64.StdEncoding.EncodeToString(mac.Sum(nil))
}

func verifySig(key []byte, canonical []byte, sigB64 string) bool {
	want := sign(key, canonical)
	got, err := base64.StdEncoding.DecodeString(sigB64)
	if err != nil {
		return false
	}
	wantBytes, err := base64.StdEncoding.DecodeString(want)
	if err != nil {
		return false
	}
	return hmac.Equal(wantBytes, got)
}

// randomHex returns n random bytes as hex (pairing keys, session keys).
func randomHex(n int) (string, error) {
	b := make([]byte, n)
	if _, err := readCrypto(b); err != nil {
		return "", err
	}
	return fmt.Sprintf("%x", b), nil
}

package gw

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"io"
	"net/http"
	"sync"
	"time"
)

// ErrIdemConflict — same key, different body (or same key re-sent while the
// first request is still in flight) => 409 request.idempotency_conflict.
var ErrIdemConflict = errors.New("gw: idempotency key conflict")

// IdempotencyStore is step 7 (GW-12). Production: PG idempotency_keys table
// (24h TTL); the reference is a mutex-guarded map.
type IdempotencyStore interface {
	// Begin claims the (scope, key). Returns (status, body, nil) when a
	// completed request replays; ErrIdemConflict on body mismatch or an
	// in-flight duplicate; (0, nil, nil) when this caller owns the claim.
	Begin(ctx context.Context, scopeKey string, bodyHash string) (status int, body []byte, err error)
	// Commit stores the finished response for the TTL window.
	Commit(ctx context.Context, scopeKey string, bodyHash string, status int, body []byte) error
}

// idemScope builds the binding scope: (tenant, method, path, key).
func idemScope(r *http.Request, key string) string {
	return TenantFrom(r.Context()) + "\x00" + r.Method + "\x00" + r.URL.Path + "\x00" + key
}

type idemRec struct {
	hash   string
	status int
	body   []byte
	done   bool
	exp    time.Time
}

// MemIdemStore is the in-memory reference implementation.
type MemIdemStore struct {
	mu      sync.Mutex
	m       map[string]idemRec
	ttl     time.Duration
	nowFunc func() time.Time
}

func NewMemIdemStore(ttl time.Duration) *MemIdemStore {
	if ttl <= 0 {
		ttl = 24 * time.Hour
	}
	return &MemIdemStore{m: map[string]idemRec{}, ttl: ttl, nowFunc: time.Now}
}

func (s *MemIdemStore) Begin(_ context.Context, key, hash string) (int, []byte, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	now := s.nowFunc()
	if rec, ok := s.m[key]; ok {
		if now.After(rec.exp) {
			delete(s.m, key)
		} else if rec.hash != hash {
			return 0, nil, ErrIdemConflict
		} else if !rec.done {
			return 0, nil, ErrIdemConflict // in-flight duplicate
		} else {
			return rec.status, rec.body, nil
		}
	}
	s.m[key] = idemRec{hash: hash, exp: now.Add(s.ttl)}
	return 0, nil, nil
}

func (s *MemIdemStore) Commit(_ context.Context, key, hash string, status int, body []byte) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	now := s.nowFunc()
	if rec, ok := s.m[key]; ok && rec.hash == hash {
		rec.done, rec.status, rec.body, rec.exp = true, status, body, now.Add(s.ttl)
		s.m[key] = rec
	}
	return nil
}

// bodyHash — only the SHA-256 of the body is ever stored (contract: raw
// request bodies are never persisted).
func bodyHash(r *http.Request) (string, []byte) {
	var raw []byte
	if r.Body != nil {
		raw, _ = io.ReadAll(io.LimitReader(r.Body, 1<<20+1))
	}
	sum := sha256.Sum256(raw)
	return hex.EncodeToString(sum[:]), raw
}

// idemRecorder captures status + first MB of the response body for Commit
// while streaming through to the client.
type idemRecorder struct {
	http.ResponseWriter
	status int
	buf    bytes.Buffer
}

func (i *idemRecorder) WriteHeader(code int) {
	if i.status == 0 {
		i.status = code
	}
	i.ResponseWriter.WriteHeader(code)
}

func (i *idemRecorder) Write(b []byte) (int, error) {
	if i.status == 0 {
		i.status = http.StatusOK
	}
	if i.buf.Len() < 1<<20 {
		i.buf.Write(b)
	}
	return i.ResponseWriter.Write(b)
}

// IdempotencyMW — step 7. Applies to POST/Patch carrying X-Idempotency-Key
// (the contract's idempotent-protected routes declare it; other methods pass
// through untouched). Replays carry X-Idempotent-Replay: true.
func IdempotencyMW(store IdempotencyStore, next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if store == nil || (r.Method != http.MethodPost && r.Method != http.MethodPatch) {
			next.ServeHTTP(w, r)
			return
		}
		key := r.Header.Get("X-Idempotency-Key")
		if key == "" {
			next.ServeHTTP(w, r)
			return
		}
		hash, raw := bodyHash(r)
		r.Body = io.NopCloser(bytes.NewReader(raw))
		r.ContentLength = int64(len(raw))
		scope := idemScope(r, key)
		status, body, err := store.Begin(r.Context(), scope, hash)
		if err != nil {
			WriteError(w, r, "request.idempotency_conflict", "This request was already submitted with different data.")
			return
		}
		if status != 0 {
			w.Header().Set("Content-Type", "application/json")
			w.Header().Set("X-Idempotent-Replay", "true")
			w.WriteHeader(status)
			_, _ = w.Write(body)
			return
		}
		rec := &idemRecorder{ResponseWriter: w}
		next.ServeHTTP(rec, r)
		if rec.status >= 500 || rec.status == 0 {
			return // 5xx and aborted responses are not remembered (contract)
		}
		_ = store.Commit(r.Context(), scope, hash, rec.status, rec.buf.Bytes())
	})
}

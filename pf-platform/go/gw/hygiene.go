package gw

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"strings"
	"sync"
	"time"
)

// Logger is the structured access-log sink (slog-compatible).
type Logger interface {
	Printf(format string, v ...interface{})
}

// Step 9a — payload hygiene (GW-13). Declared max (1 MB baseline) is
// enforced by ContentLength short-circuit plus a streaming MaxBytesReader for
// chunked bodies.
func BodyLimit(maxBytes int64, next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.ContentLength > maxBytes {
			WriteError(w, r, "gw.payload_too_large", "Request body too large.")
			return
		}
		if r.Body != nil {
			r.Body = http.MaxBytesReader(w, r.Body, maxBytes)
		}
		next.ServeHTTP(w, r)
	})
}

// Step 9b — handler timeout: an upstream call that hangs must still produce a
// shaped GW-18 response, never an edge default page.
type timeoutWriter struct {
	mu       sync.Mutex
	rw       http.ResponseWriter
	wrote    bool
	timedOut bool
}

func (t *timeoutWriter) Header() http.Header { return t.rw.Header() }

func (t *timeoutWriter) Write(p []byte) (int, error) {
	t.mu.Lock()
	defer t.mu.Unlock()
	if t.timedOut {
		return 0, errors.New("gw: write after timeout")
	}
	t.wrote = true
	return t.rw.Write(p)
}

func (t *timeoutWriter) WriteHeader(code int) {
	t.mu.Lock()
	defer t.mu.Unlock()
	if t.timedOut {
		return
	}
	t.wrote = true
	t.rw.WriteHeader(code)
}

func (t *timeoutWriter) sendTimeout(corr string) {
	t.mu.Lock()
	defer t.mu.Unlock()
	if t.wrote || t.timedOut {
		return
	}
	t.timedOut = true
	t.rw.Header().Set("Content-Type", "application/json")
	t.rw.WriteHeader(http.StatusGatewayTimeout)
	_ = json.NewEncoder(t.rw).Encode(ErrorEnvelope{Code: "gw.timeout", Message: "The request took too long.", CorrelationID: corr})
}

// WithHandlerTimeout bounds handler execution. The handler goroutine is NOT
// cancelled (request-scoped work should honor ctx); the client just stops
// waiting.
func WithHandlerTimeout(d time.Duration, next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		corr := CorrelationFrom(r.Context())
		tw := &timeoutWriter{rw: w}
		done := make(chan struct{})
		go func() {
			defer close(done)
			next.ServeHTTP(tw, r)
		}()
		select {
		case <-done:
		case <-time.After(d):
			tw.sendTimeout(corr)
		}
	})
}

// statusCapture records the status code for access logs / audit without
// changing response behavior.
type statusCapture struct {
	http.ResponseWriter
	status int
}

func (s *statusCapture) WriteHeader(code int) {
	if s.status == 0 {
		s.status = code
	}
	s.ResponseWriter.WriteHeader(code)
}

func (s *statusCapture) Write(b []byte) (int, error) {
	if s.status == 0 {
		s.status = http.StatusOK
	}
	return s.ResponseWriter.Write(b)
}

func (s *statusCapture) Status() int {
	if s.status == 0 {
		return http.StatusOK
	}
	return s.status
}

// AccessLog emits one structured line per request with the correlation id —
// the GW-09 propagation endpoint for the HTTP plane.
func AccessLog(log Logger, next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		sc := &statusCapture{ResponseWriter: w}
		start := time.Now()
		next.ServeHTTP(sc, r)
		log.Printf("method=%s path=%s status=%d duration_ms=%d correlation_id=%s client_ip=%s tenant=%s",
			r.Method, r.URL.Path, sc.Status(), time.Since(start).Milliseconds(),
			CorrelationFrom(r.Context()), clientIPString(r.Context()), TenantFrom(r.Context()))
	})
}

func clientIPString(ctx context.Context) string {
	if ip := ClientIPFrom(ctx); ip != nil {
		return ip.String()
	}
	return ""
}

// sensitiveHeaders are redacted before any header map is logged.
var sensitiveHeaders = []string{"Authorization", "Cookie", "Set-Cookie", "X-Api-Key", "X-Service-Token"}

// RedactHeaders returns a copy of h safe for logging (GW-36 hygiene).
func RedactHeaders(h http.Header) map[string]string {
	out := map[string]string{}
	for k, v := range h {
		val := strings.Join(v, ",")
		for _, s := range sensitiveHeaders {
			if strings.EqualFold(k, s) {
				val = "[REDACTED]"
				break
			}
		}
		out[k] = val
	}
	return out
}

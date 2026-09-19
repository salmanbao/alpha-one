package gw

import (
	"context"
	"net/http"
	"strconv"
	"sync"
	"time"
)

// Limiter is step 5 (GW-05). Production: Redis fixed-window per contract
// numbers; the reference uses an exact sliding log in memory.
type Limiter interface {
	// Allow reports whether one more request fits, and — on denial — how
	// long until the window frees (used for Retry-After).
	Allow(ctx context.Context, key string, limit int, window time.Duration) (ok bool, retryAfter time.Duration)
}

// MemLimiter is an exact sliding-window log limiter. Window prunes lazily.
type MemLimiter struct {
	mu      sync.Mutex
	hits    map[string][]time.Time
	nowFunc func() time.Time
}

func NewMemLimiter() *MemLimiter {
	return &MemLimiter{hits: map[string][]time.Time{}, nowFunc: time.Now}
}

func (m *MemLimiter) Allow(_ context.Context, key string, limit int, window time.Duration) (bool, time.Duration) {
	m.mu.Lock()
	defer m.mu.Unlock()
	now := m.nowFunc()
	keep := m.hits[key][:0]
	for _, t := range m.hits[key] {
		if now.Sub(t) < window {
			keep = append(keep, t)
		}
	}
	if len(keep) >= limit {
		m.hits[key] = keep
		return false, window - now.Sub(keep[0])
	}
	m.hits[key] = append(keep, now)
	return true, 0
}

// ratePolicy encodes the binding per-class numbers (docs/04 §5.4, GW-29).
// The edge per-IP limit lives at Cloudflare, not here.
func ratePolicy(class string) (int, time.Duration) {
	switch class {
	case "auth":
		return 10, 5 * time.Minute
	case "payout":
		return 5, time.Hour
	default:
		return 100, time.Minute
	}
}

// rateKey: authenticated callers are limited per user; anonymous by client IP.
func rateKey(r *http.Request) string {
	if p := PrincipalFrom(r.Context()); p != nil && p.ID != "" {
		return "user:" + p.ID
	}
	if ip := ClientIPFrom(r.Context()); ip != nil {
		return "ip:" + ip.String()
	}
	return "ip:" + r.RemoteAddr
}

// RateLimitMW — step 5. 429 rate.limited with Retry-After on denial.
func RateLimitMW(l Limiter, class string, next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if l != nil {
			limit, window := ratePolicy(class)
			if ok, retry := l.Allow(r.Context(), rateKey(r), limit, window); !ok {
				secs := int(retry / time.Second)
				if secs < 1 {
					secs = 1
				}
				w.Header().Set("Retry-After", strconv.Itoa(secs))
				WriteError(w, r, "rate.limited", "Too many requests. Try again shortly.")
				return
			}
		}
		next.ServeHTTP(w, r)
	})
}

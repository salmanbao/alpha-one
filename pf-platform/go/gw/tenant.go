package gw

import (
	"context"
	"net/http"
	"strings"
	"sync"
	"time"
)

// TenantResolver answers "does this hostname belong to a live tenant?"
// (GW-01). Production backs it with the tenants table on the unique host
// column; tests and demos use MapResolver.
type TenantResolver interface {
	// ByHost returns (tenantID, known, err). known=false means the host does
	// not belong to any registered firm.
	ByHost(ctx context.Context, host string) (tenantID string, known bool, err error)
}

// MapResolver is the in-memory reference implementation.
type MapResolver struct {
	mu      sync.RWMutex
	byHost  map[string]string
	negTTL  time.Duration
	posTTL  time.Duration
	nowFunc func() time.Time
}

func NewMapResolver(hostToTenant map[string]string) *MapResolver {
	m := map[string]string{}
	for h, id := range hostToTenant {
		m[strings.ToLower(h)] = id
	}
	return &MapResolver{byHost: m, posTTL: 5 * time.Minute, negTTL: 30 * time.Second, nowFunc: time.Now}
}

func (m *MapResolver) ByHost(_ context.Context, host string) (string, bool, error) {
	m.mu.RLock()
	defer m.mu.RUnlock()
	id, ok := m.byHost[strings.ToLower(host)]
	return id, ok, nil
}

func (m *MapResolver) SetHost(host, tenantID string) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.byHost[strings.ToLower(host)] = tenantID
}

// CachedResolver decorates any TenantResolver with a positive TTL cache and a
// shorter negative cache (so a newly registered host appears within
// negTTL without a restart).
type CachedResolver struct {
	inner   TenantResolver
	posTTL  time.Duration
	negTTL  time.Duration
	nowFunc func() time.Time
	mu      sync.Mutex
	pos     map[string]posEntry
	neg     map[string]time.Time
}

type posEntry struct {
	tenantID string
	at       time.Time
}

func NewCachedResolver(inner TenantResolver, ttl time.Duration) *CachedResolver {
	return &CachedResolver{
		inner: inner, posTTL: ttl, negTTL: ttl / 10, nowFunc: time.Now,
		pos: map[string]posEntry{}, neg: map[string]time.Time{},
	}
}

func (c *CachedResolver) ByHost(ctx context.Context, host string) (string, bool, error) {
	key := strings.ToLower(host)
	c.mu.Lock()
	if e, ok := c.pos[key]; ok && c.nowFunc().Sub(e.at) < c.posTTL {
		c.mu.Unlock()
		return e.tenantID, true, nil
	}
	if t, ok := c.neg[key]; ok && c.nowFunc().Sub(t) < c.negTTL {
		c.mu.Unlock()
		return "", false, nil
	}
	c.mu.Unlock()
	id, known, err := c.inner.ByHost(ctx, key)
	if err != nil {
		return "", false, err
	}
	c.mu.Lock()
	now := c.nowFunc()
	if known {
		c.pos[key] = posEntry{tenantID: id, at: now}
	} else {
		c.neg[key] = now
	}
	c.mu.Unlock()
	return id, known, nil
}

// Step 2 — host-to-tenant resolution. /internal/* is compose-only and never
// edge-routed: it identifies the tenant by the static X-Tenant-Id header its
// per-service bearer authenticated it with (D46), not by public hostname.
func TenantResolve(res TenantResolver, isInternal func(*http.Request) bool, next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		var tenantID string
		if isInternal != nil && isInternal(r) {
			tenantID = r.Header.Get("X-Tenant-Id")
			if tenantID == "" {
				WriteError(w, r, "permission.denied", "Access denied.")
				return
			}
		} else {
			host := hostOnly(r.Host)
			id, known, err := res.ByHost(r.Context(), host)
			if err != nil {
				WriteError(w, r, "gw.internal_error", "Internal error.")
				return
			}
			if !known {
				WriteError(w, r, "tenant.unknown_host", "This address does not belong to a registered firm.")
				return
			}
			tenantID = id
		}
		next.ServeHTTP(w, r.WithContext(WithTenant(r.Context(), tenantID)))
	})
}

// hostOnly strips the port from a Host header.
func hostOnly(host string) string {
	if i := strings.Index(host, ":"); i >= 0 {
		return host[:i]
	}
	return host
}

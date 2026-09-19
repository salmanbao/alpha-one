package gw

import (
	"context"
	"net/http"
	"sync"
)

// Entitlements is step 6 (GW-06): plan-based module gating. Production reads
// the tenant_entitlements cache; the module key comes from the route
// declaration (docs/33 MOD-## codes).
type Entitlements interface {
	ModuleEnabled(ctx context.Context, tenantID, module string) bool
}

// MapEntitlements is the in-memory reference implementation. A module absent
// from the map is NOT enabled (fail closed, add-on semantics).
type MapEntitlements struct {
	mu      sync.RWMutex
	enabled map[string]bool // "tenantID|module" -> enabled
}

func NewMapEntitlements() *MapEntitlements {
	return &MapEntitlements{enabled: map[string]bool{}}
}

func (m *MapEntitlements) Set(tenantID, module string, on bool) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.enabled[tenantID+"|"+module] = on
}

func (m *MapEntitlements) ModuleEnabled(_ context.Context, tenantID, module string) bool {
	m.mu.RLock()
	defer m.mu.RUnlock()
	return m.enabled[tenantID+"|"+module]
}

// QuotaMW — step 6. Module-gated routes reject with 403 tenant.not_entitled
// for callers without the plan entitlement (docs/33; contract TODO resolved
// pass 14).
func QuotaMW(ent Entitlements, next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		route := RouteFrom(r.Context())
		if ent != nil && route != nil && route.Module != "" {
			if !ent.ModuleEnabled(r.Context(), TenantFrom(r.Context()), route.Module) {
				WriteError(w, r, "tenant.not_entitled", "This feature is not part of your plan.")
				return
			}
		}
		next.ServeHTTP(w, r)
	})
}

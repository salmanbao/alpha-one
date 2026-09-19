package gw

import (
	"context"
	"net/http"
	"sync"
	"time"
)

// StatusGate is step 3.5 (docs/47 route classes decide which gates run).
// Production backs it with a single indexed SQL lookup over
// tenants / identities / tenant_members; tests use MapStatusGate.
type StatusGate interface {
	TenantState(ctx context.Context, tenantID string) string
	IdentityState(ctx context.Context, identityID string) string
	MembershipState(ctx context.Context, identityID, tenantID string) string
}

// MapStatusGate is the in-memory reference implementation.
type MapStatusGate struct {
	Tenants     map[string]string // tenantID -> state
	Identities  map[string]string // identityID -> state
	Memberships map[string]string // "identityID|tenantID" -> state
}

func (m *MapStatusGate) TenantState(_ context.Context, id string) string { return m.Tenants[id] }
func (m *MapStatusGate) IdentityState(_ context.Context, id string) string {
	return m.Identities[id]
}
func (m *MapStatusGate) MembershipState(_ context.Context, identityID, tenantID string) string {
	return m.Memberships[identityID+"|"+tenantID]
}

// CachedGate memoizes gate states for ttl. Invalidation hooks exist for the
// state-machine transitions (docs/12) that must take effect immediately:
// SuspendTenant -> InvalidateTenant, BanIdentity -> InvalidateIdentity.
type CachedGate struct {
	inner   StatusGate
	ttl     time.Duration
	nowFunc func() time.Time
	mu      sync.Mutex
	cache   map[string]gateEntry
}

type gateEntry struct {
	state string
	at    time.Time
}

func NewCachedGate(inner StatusGate, ttl time.Duration) *CachedGate {
	return &CachedGate{inner: inner, ttl: ttl, nowFunc: time.Now, cache: map[string]gateEntry{}}
}

func (g *CachedGate) TenantState(ctx context.Context, id string) string {
	return g.cached(ctx, "t|"+id, func() string { return g.inner.TenantState(ctx, id) })
}

func (g *CachedGate) IdentityState(ctx context.Context, id string) string {
	return g.cached(ctx, "i|"+id, func() string { return g.inner.IdentityState(ctx, id) })
}

func (g *CachedGate) MembershipState(ctx context.Context, identityID, tenantID string) string {
	return g.cached(ctx, "m|"+identityID+"|"+tenantID, func() string {
		return g.inner.MembershipState(ctx, identityID, tenantID)
	})
}

func (g *CachedGate) cached(ctx context.Context, key string, load func() string) string {
	g.mu.Lock()
	if e, ok := g.cache[key]; ok && g.nowFunc().Sub(e.at) < g.ttl {
		g.mu.Unlock()
		return e.state
	}
	g.mu.Unlock()
	st := load()
	g.mu.Lock()
	g.cache[key] = gateEntry{state: st, at: g.nowFunc()}
	g.mu.Unlock()
	return st
}

func (g *CachedGate) InvalidateTenant(id string)         { g.drop("t|" + id) }
func (g *CachedGate) InvalidateIdentity(id string)       { g.drop("i|" + id) }
func (g *CachedGate) InvalidateMembership(i, t string)   { g.drop("m|" + i + "|" + t) }

func (g *CachedGate) drop(key string) {
	g.mu.Lock()
	defer g.mu.Unlock()
	delete(g.cache, key)
}

// Step 3.5 — route-class-aware status gates.
//
//	trader         -> tenant live + identity active + member active
//	admin/console  -> tenant live (staff operate during onboarding) + identity active
//	payout         -> same as admin/console (finance-side init)
//	auth           -> none (login happens while onboarding; suspended identity
//	                  cannot log in anyway)
//	public/webhook -> none
func StatusGateMW(gate StatusGate, class string, next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		ctx := r.Context()
		tenantID := TenantFrom(ctx)
		if gate != nil && tenantID != "" {
			switch gate.TenantState(ctx, tenantID) {
			case "suspended":
				WriteError(w, r, "tenant.suspended", "This firm is currently suspended.")
				return
			case "", "active", "live":
				// proceed
			default:
				// onboarding/provisioning/verifying/activating: pre-live
				if class == "trader" {
					WriteError(w, r, "tenant.not_live", "This firm is not live yet.")
					return
				}
			}
		}
		p := PrincipalFrom(ctx)
		if gate != nil && p != nil && (p.Kind == "user" || p.Kind == "staff") {
			if gate.IdentityState(ctx, p.ID) == "suspended" {
				WriteError(w, r, "auth.account_suspended", "This account is suspended.")
				return
			}
			if p.Kind == "user" && gate.MembershipState(ctx, p.ID, tenantID) == "suspended" {
				WriteError(w, r, "auth.membership_suspended", "Your access to this firm is suspended.")
				return
			}
		}
		next.ServeHTTP(w, r)
	})
}

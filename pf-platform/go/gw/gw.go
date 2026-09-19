package gw

import (
	"context"
	"net"
	"net/http"
	"sort"
	"strings"
	"time"
)

// Route declares one API surface for the chain (docs/04 §3.1 + docs/47).
type Route struct {
	Name   string // human label, e.g. "payout approve"
	Class  string // docs/47 route class: public|auth|trader|admin|console|webhook|payout|internal
	Key    string // GW-04 permission key ("" = public / no authz)
	Own    func(*http.Request) (ownerID string, ok bool) // required when the permission Scope is "own"
	Module string                                        // docs/33 MOD-## entitlement key ("" = core)
	Idem   bool   // route participates in GW-12 idempotency
	Audit  bool   // GW-17: audit success AND failure of sensitive actions
}

// Config carries deployment knobs; zero values get safe defaults.
type Config struct {
	TrustedProxyCIDRs []*net.IPNet  // CF-Connecting-IP accepted only from these peers (GW-33)
	BodyLimitBytes    int64         // GW-13 declared max; default 1 MiB
	HandlerTimeout    time.Duration // step 9b; default 10s
}

// Deps wires the swappable backends. Every interface has a correct in-memory
// implementation in this package; production plugs Redis/PG-backed versions
// without touching the chain.
type Deps struct {
	Resolver     TenantResolver   // step 2
	Auth         *Authenticator   // step 3
	Gate         StatusGate       // step 3.5
	Table        AuthzTable       // step 4
	Limiter      Limiter          // step 5
	Entitlements Entitlements     // step 6
	Idem         IdempotencyStore // step 7
	Audit        AuditSink        // GW-17 wrapper
	Log          Logger           // structured access log
	IsInternal   func(*http.Request) bool // default: path prefix /internal/
}

// AuditEvent is the sensitive-action audit record (docs/50 AUD-codes travel
// in Action once those routes are wired; the reference records route +
// permission key + outcome + correlation).
type AuditEvent struct {
	Route         string
	Key           string
	PrincipalID   string
	Status        int
	Success       bool
	CorrelationID string
}

// AuditSink receives GW-17 audit records. It returns an error on purpose:
// docs/50 makes silent audit loss a P1 — production backends must surface
// failures (alert/retry), the wrapper logs them when a Logger is configured.
type AuditSink interface {
	Audit(ctx context.Context, e AuditEvent) error
}

// Builder assembles the middleware chain.
type Builder struct {
	cfg  Config
	deps Deps
}

func NewBuilder(cfg Config, deps Deps) *Builder {
	if cfg.BodyLimitBytes <= 0 {
		cfg.BodyLimitBytes = 1 << 20
	}
	if cfg.HandlerTimeout <= 0 {
		cfg.HandlerTimeout = 10 * time.Second
	}
	if deps.IsInternal == nil {
		deps.IsInternal = func(r *http.Request) bool { return strings.HasPrefix(r.URL.Path, internalPrefix) }
	}
	return &Builder{cfg: cfg, deps: deps}
}

// Build wraps h with the full 11-step chain for route. Request flow ==
// binding order from docs/04 §3.1:
//
//	access log -> step 8  correlation adopt-or-mint    (GW-09/36) Correlation   [outermost]
//	step 1  edge handoff + security headers            (GW-20/33) SecurityHeaders
//	step 2  host -> tenant resolution                  (GW-01)    TenantResolve
//	405     method guard (before authn/rate: wrong-method probes burn nothing)
//	step 3  authentication                             (GW-03)    Auth.Middleware
//	step 3.5 status gates, route-class aware           (docs/47)  StatusGateMW
//	GW-17   sensitive-action audit wrapper (around 4)             auditWrap
//	step 4  permission-key authorization               (GW-04)    Authorize
//	step 5  rate limiting                              (GW-05/29) RateLimitMW
//	step 6  quota + entitlements                       (GW-06)    QuotaMW
//	step 7  idempotency                                (GW-12)    IdempotencyMW
//	step 9  payload hygiene + handler timeout          (GW-13)    BodyLimit + WithHandlerTimeout
//	inner   method-typed route + handler; Route enters the context here
func (b *Builder) Build(method string, route Route, h http.Handler) http.Handler {
	inner := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		h.ServeHTTP(w, r.WithContext(WithRoute(r.Context(), &route)))
	})

	// step 9 — hygiene (innermost region)
	out := WithHandlerTimeout(b.cfg.HandlerTimeout, inner)
	out = BodyLimit(b.cfg.BodyLimitBytes, out)
	// step 7 — idempotency (only declared routes)
	if route.Idem {
		out = IdempotencyMW(b.deps.Idem, out)
	}
	// step 6 — quota + entitlement
	out = QuotaMW(b.deps.Entitlements, out)
	// step 5 — rate limit
	out = RateLimitMW(b.deps.Limiter, route.Class, out)
	// GW-17 audit wraps step 4: permission failures of sensitive actions are
	// audited too; gate/authn failures are tenant/account state, not actions.
	out = b.auditWrap(route, Authorize(b.deps.Table, out))
	// step 3.5 — status gates
	out = StatusGateMW(b.deps.Gate, route.Class, out)
	// 405 method guard
	out = methodGuard(method, out)
	// step 3 — authentication
	out = b.deps.Auth.Middleware(out)
	// step 2 — tenant resolution
	out = TenantResolve(b.deps.Resolver, b.deps.IsInternal, out)
	// step 1 — edge handoff + security headers
	out = SecurityHeaders(b.cfg.TrustedProxyCIDRs, out)
	// step 8 — correlation (outermost; see correlation.go for the slot note)
	out = Correlation(out)
	// structured access log
	if b.deps.Log != nil {
		out = AccessLog(b.deps.Log, out)
	}
	return out
}

// Mount registers pattern on mux for exactly one method with the full chain.
func (b *Builder) Mount(mux *http.ServeMux, method, pattern string, route Route, h http.Handler) {
	mux.Handle(pattern, b.Build(method, route, h))
}

func methodGuard(method string, next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if method != "" && r.Method != method {
			WriteError(w, r, "gw.method_not_allowed", "Method not allowed.")
			return
		}
		next.ServeHTTP(w, r)
	})
}

func (b *Builder) auditWrap(route Route, next http.Handler) http.Handler {
	if !route.Audit || b.deps.Audit == nil {
		return next
	}
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		sc := &statusCapture{ResponseWriter: w}
		next.ServeHTTP(sc, r)
		var pid string
		if p := PrincipalFrom(r.Context()); p != nil {
			pid = p.ID
		}
		ev := AuditEvent{
			Route:         route.Name,
			Key:           route.Key,
			PrincipalID:   pid,
			Status:        sc.Status(),
			Success:       sc.Status() < 400,
			CorrelationID: CorrelationFrom(r.Context()),
		}
		if err := b.deps.Audit.Audit(r.Context(), ev); err != nil && b.deps.Log != nil {
			b.deps.Log.Printf("audit_write_failed route=%s correlation_id=%s err=%v", route.Name, ev.CorrelationID, err)
		}
	})
}

// Healthz — liveness (process up).
func Healthz() http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
	})
}

// Check is one readiness dependency probe.
type Check func(ctx context.Context) error

// Readyz — readiness (dependencies reachable), 2s per-check budget.
func Readyz(checks map[string]Check) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		failed := make([]string, 0, len(checks))
		for name, check := range checks {
			ctx, cancel := context.WithTimeout(r.Context(), 2*time.Second)
			if err := check(ctx); err != nil {
				failed = append(failed, name)
			}
			cancel()
		}
		if len(failed) > 0 {
			sort.Strings(failed)
			writeJSON(w, http.StatusServiceUnavailable, map[string]interface{}{"status": "fail", "failed": failed})
			return
		}
		writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
	})
}

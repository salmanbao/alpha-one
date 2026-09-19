package gw

import (
	"net/http"
	"time"
)

const stepUpTTL = 5 * time.Minute // D38: re-confirm identity for sensitive actions

// Permission is one row of the GW-04 permission-key table.
type Permission struct {
	Key    string   // e.g. "payout.approve"
	Roles  []string // any-of
	Scope  string   // "all" | "own" — "own" pairs with Route.Own
	StepUp bool     // requires MFAAt within stepUpTTL (D38)
}

// AuthzTable maps route permission keys to permissions.
type AuthzTable map[string]Permission

// Step 4 — permission-key authorization. Contract notes:
//   - unknown route key = wiring bug: fail closed with permission.denied;
//   - anonymous caller on a key-bearing route: 401 generic auth error
//     (authn passed it through as anonymous);
//   - insufficient role / cross-tenant "own" scope: 403 permission.denied;
//   - Casbin (ADR-14) plugs in behind the same table interface; the gateway
//     calls a pure table here so the reference stays dependency-free.
func Authorize(table AuthzTable, next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		route := RouteFrom(r.Context())
		if route == nil || route.Key == "" {
			next.ServeHTTP(w, r) // public route or method-guarded only
			return
		}
		perm, declared := table[route.Key]
		if !declared {
			WriteError(w, r, "permission.denied", "You do not have access to this action.")
			return
		}
		p := PrincipalFrom(r.Context())
		if p == nil {
			WriteError(w, r, "auth.invalid_credentials", "Authentication required.")
			return
		}
		if !anyRole(perm.Roles, p.Roles) {
			WriteError(w, r, "permission.denied", "You do not have access to this action.")
			return
		}
		if perm.Scope == "own" && route.Own != nil {
			ownerID, ok := route.Own(r)
			if !ok || ownerID == "" || ownerID != p.ID {
				WriteError(w, r, "permission.denied", "You do not have access to this action.")
				return
			}
		}
		if perm.StepUp {
			if p.MFAAt.IsZero() || time.Since(p.MFAAt) > stepUpTTL {
				WriteError(w, r, "authz.step_up_required", "Re-authenticate to continue.")
				return
			}
		}
		next.ServeHTTP(w, r)
	})
}

func anyRole(want, have []string) bool {
	for _, w := range want {
		for _, h := range have {
			if w == h {
				return true
			}
		}
	}
	return false
}

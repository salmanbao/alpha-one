package gw

import "net/http"

// Step 8 — correlation (GW-09/GW-36): adopt the inbound X-Correlation-Id or
// mint a fresh ULID; propagate to the response and to everything downstream
// (logs via AccessLog, events/audit via the envelope and producer code).
//
// Implementation note: this runs as the OUTERMOST middleware even though the
// binding table lists correlation as step 8. The GW-18 error envelope must
// carry correlation_id on pre-step-8 failures too (tenant resolution, authn),
// so the value is adopted/minted first; step 8's documented slot remains the
// propagation checkpoint. The security-critical sequence (steps 2..9) is
// untouched.
func Correlation(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		id := r.Header.Get("X-Correlation-Id")
		if !ValidCorrelation(id) {
			id = MintULID()
		}
		w.Header().Set("X-Correlation-Id", id)
		next.ServeHTTP(w, r.WithContext(WithCorrelation(r.Context(), id)))
	})
}

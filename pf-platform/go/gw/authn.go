package gw

import (
	"context"
	"crypto/subtle"
	"net/http"
	"strings"
	"time"
)

// Realm identifies which credential path a route uses (GW-03). It is derived
// from the URL plan (D46), not from configuration.
type Realm int

const (
	RealmTrader Realm = iota // /v1/trader/*   — Bearer JWT, audience "trader"
	RealmStaff               // /v1/admin/*    — Bearer JWT, audience "staff", step-up sensitive actions
	RealmConsole             // /v1/console/*  — HttpOnly session cookie (session store backed)
	RealmService             // /internal/*    — static per-service bearer, never edge-routed
)

// Principal is the resolved caller identity.
type Principal struct {
	Kind      string // "user" | "staff" | "service"
	ID        string
	TenantID  string
	Roles     []string
	MFAAt     time.Time // last step-up confirmation (D38); zero = none
}

// TokenVerifier verifies an access JWT and returns the caller. Production
// plugs the platform JWT verifier (RS256, audience check) here.
type TokenVerifier interface {
	Verify(ctx context.Context, token string) (*Principal, error)
}

// VerifierFunc adapts a function to TokenVerifier.
type VerifierFunc func(ctx context.Context, token string) (*Principal, error)

func (f VerifierFunc) Verify(ctx context.Context, token string) (*Principal, error) { return f(ctx, token) }

// SessionStore backs the console cookie realm.
type SessionStore interface {
	Get(ctx context.Context, sessionID string) (*Principal, bool)
}

// Authenticator is step 3 (GW-03). A failed authentication is a generic 401
// auth.invalid_credentials — never a realm- or user-specific message.
type Authenticator struct {
	Verifier      TokenVerifier
	Console       SessionStore
	ServiceTokens map[string]string // token -> service label
}

const consoleCookieName = "pf_console_session"

// internalPrefix is the compose-only internal plane (docs/04 §3.1 step 2:
// /internal/*, static per-service bearer, never edge-routed; docs/55 SOL-02
// serves it on a separate compose-only listener).
const internalPrefix = "/internal/"

func (a *Authenticator) Middleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		p, ok, anonymous := a.authenticate(r)
		if !ok {
			WriteError(w, r, "auth.invalid_credentials", "Authentication required.")
			return
		}
		if anonymous {
			next.ServeHTTP(w, r)
			return
		}
		next.ServeHTTP(w, r.WithContext(WithPrincipal(r.Context(), p)))
	})
}

func (a *Authenticator) authenticate(r *http.Request) (*Principal, bool, bool) {
	authz := r.Header.Get("Authorization")
	switch {
	case strings.HasPrefix(r.URL.Path, internalPrefix):
		tok := bearerToken(authz)
		if tok == "" {
			return nil, false, false
		}
		label, found := a.matchServiceToken(tok)
		if !found {
			return nil, false, false
		}
		return &Principal{Kind: "service", ID: label, TenantID: r.Header.Get("X-Tenant-Id")}, true, false
	case strings.HasPrefix(r.URL.Path, "/v1/console/"):
		c, err := r.Cookie(consoleCookieName)
		if err != nil || c.Value == "" || a.Console == nil {
			return nil, false, false
		}
		p, ok := a.Console.Get(r.Context(), c.Value)
		if !ok {
			return nil, false, false
		}
		return p, true, false
	default:
		if authz == "" {
			return nil, true, true // anonymous; step 4 decides if the route allows it
		}
		tok := bearerToken(authz)
		if tok == "" || a.Verifier == nil {
			return nil, false, false
		}
		p, err := a.Verifier.Verify(r.Context(), tok)
		if err != nil || p == nil {
			return nil, false, false
		}
		return p, true, false
	}
}

func bearerToken(h string) string {
	if strings.HasPrefix(h, "Bearer ") {
		return strings.TrimPrefix(h, "Bearer ")
	}
	return ""
}

func (a *Authenticator) matchServiceToken(tok string) (string, bool) {
	for want, label := range a.ServiceTokens {
		if subtle.ConstantTimeCompare([]byte(tok), []byte(want)) == 1 {
			return label, true
		}
	}
	return "", false
}

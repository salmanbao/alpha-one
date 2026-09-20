package gw

import (
	"bytes"
	"context"
	"encoding/json"
	"net"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

// ---------------------------------------------------------------------------
// fixtures

func mustCIDR(t *testing.T, s string) *net.IPNet {
	t.Helper()
	_, n, err := net.ParseCIDR(s)
	if err != nil {
		t.Fatalf("parse cidr: %v", err)
	}
	return n
}

type auditRecorder struct {
	events []AuditEvent
}

func (a *auditRecorder) Audit(_ context.Context, e AuditEvent) error {
	a.events = append(a.events, e)
	return nil
}

type fixture struct {
	b     *Builder
	mux   *http.ServeMux
	lim   *MemLimiter
	ent   *MapEntitlements
	idem  *MemIdemStore
	audit *auditRecorder
}

func verifierFor(tok string) (*Principal, error) {
	switch tok {
	case "user-token-1":
		return &Principal{Kind: "user", ID: "u1", TenantID: "tenLive", Roles: []string{"trader"}}, nil
	case "user-token-2":
		return &Principal{Kind: "user", ID: "u2", TenantID: "tenLive", Roles: []string{"trader"}}, nil
	case "staff-token":
		return &Principal{Kind: "staff", ID: "s1", TenantID: "tenLive", Roles: []string{"firm:admin"}, MFAAt: time.Now()}, nil
	case "staff-token-stale":
		return &Principal{Kind: "staff", ID: "s1", TenantID: "tenLive", Roles: []string{"firm:admin"}, MFAAt: time.Now().Add(-10 * time.Minute)}, nil
	case "staff-token-2":
		return &Principal{Kind: "staff", ID: "s2", TenantID: "tenLive", Roles: []string{"firm:admin"}}, nil
	default:
		return nil, errTestUnauthorized
	}
}

type staticError string

func (e staticError) Error() string { return string(e) }

var errTestUnauthorized = staticError("unauthorized")

func newFixture(t *testing.T) *fixture {
	t.Helper()
	f := &fixture{
		lim:   NewMemLimiter(),
		ent:   NewMapEntitlements(),
		idem:  NewMemIdemStore(24 * time.Hour),
		audit: &auditRecorder{},
	}
	deps := Deps{
		Resolver: NewMapResolver(map[string]string{
			"live.example":      "tenLive",
			"onboarding.example": "tenA",
			"bad.example":       "tenBad",
		}),
		Auth: &Authenticator{
			Verifier: VerifierFunc(verifierFor),
			ServiceTokens: map[string]string{
				"svc-token-alpha": "svc-challenge-engine",
			},
		},
		Gate: &MapStatusGate{
			Tenants:    map[string]string{"tenLive": "active", "tenA": "onboarding", "tenBad": "suspended"},
			Identities: map[string]string{"s2": "suspended"},
		},
		Table: AuthzTable{
			"challenge.write": {Key: "challenge.write", Roles: []string{"trader"}},
			"payout.request":  {Key: "payout.request", Roles: []string{"trader"}, Scope: "own"},
			"payout.approve":  {Key: "payout.approve", Roles: []string{"firm:admin"}, StepUp: true},
			"kyc.read":        {Key: "kyc.read", Roles: []string{"firm:admin", "compliance"}},
		},
		Limiter:      f.lim,
		Entitlements: f.ent,
		Idem:         f.idem,
		Audit:        f.audit,
	}
	f.b = NewBuilder(Config{TrustedProxyCIDRs: []*net.IPNet{mustCIDR(t, "203.0.113.0/24")}}, deps)
	f.mux = http.NewServeMux()

	f.b.Mount(f.mux, http.MethodPost, "/v1/auth/login/", Route{Name: "login", Class: "auth"},
		http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			var in struct {
				Email    string `json:"email"`
				Password string `json:"password"`
			}
			_ = json.NewDecoder(r.Body).Decode(&in)
			if in.Email == "found@example.com" && in.Password == "right" {
				WriteSuccess(w, r, map[string]interface{}{"authenticated": true})
				return
			}
			WriteError(w, r, "auth.invalid_credentials", "Email or password is incorrect.")
		}))

	f.b.Mount(f.mux, http.MethodPost, "/v1/trader/challenges/", Route{
		Name: "challenge create", Class: "trader", Key: "challenge.write", Module: "mod.challenges",
	}, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		WriteCreated(w, r, map[string]interface{}{"id": "ch_1"})
	}))

	f.b.Mount(f.mux, http.MethodPost, "/v1/trader/payouts/", Route{
		Name: "payout request", Class: "payout", Key: "payout.request", Idem: true,
		Own: func(r *http.Request) (string, bool) {
			v := r.Header.Get("X-Ownee")
			return v, v != ""
		},
	}, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		WriteCreated(w, r, map[string]interface{}{"id": "po_1"})
	}))

	f.b.Mount(f.mux, http.MethodPost, "/v1/admin/payouts/", Route{
		Name: "payout approve", Class: "payout", Key: "payout.approve", Audit: true,
	}, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		WriteSuccess(w, r, map[string]interface{}{"approved": true})
	}))

	f.b.Mount(f.mux, http.MethodGet, "/v1/admin/kyc/", Route{Name: "kyc queue", Class: "admin", Key: "kyc.read"},
		http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			WriteSuccess(w, r, map[string]interface{}{"queue": []string{}})
		}))

	f.b.Mount(f.mux, http.MethodPost, "/internal/jobs/", Route{Name: "job ingest", Class: "internal"},
		http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			WriteCreated(w, r, map[string]interface{}{"tenant": TenantFrom(r.Context())})
		}))

	f.b.Mount(f.mux, http.MethodGet, "/v1/public/health/", Route{Name: "public health", Class: "public"},
		http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			ip := ClientIPFrom(r.Context())
			s := ""
			if ip != nil {
				s = ip.String()
			}
			WriteSuccess(w, r, map[string]interface{}{"client_ip": s})
		}))

	return f
}

func (f *fixture) do(t *testing.T, r *http.Request) *httptest.ResponseRecorder {
	t.Helper()
	rec := httptest.NewRecorder()
	f.mux.ServeHTTP(rec, r)
	return rec
}

func jsonBody(t *testing.T, rec *httptest.ResponseRecorder) map[string]interface{} {
	t.Helper()
	var m map[string]interface{}
	if err := json.Unmarshal(rec.Body.Bytes(), &m); err != nil {
		t.Fatalf("body not json: %v\n%s", err, rec.Body.String())
	}
	return m
}

func wantCode(t *testing.T, rec *httptest.ResponseRecorder, status int) {
	t.Helper()
	if rec.Code != status {
		t.Fatalf("status = %d, want %d (body: %s)", rec.Code, status, rec.Body.String())
	}
}

func wantError(t *testing.T, rec *httptest.ResponseRecorder, status int, code string) {
	t.Helper()
	wantCode(t, rec, status)
	m := jsonBody(t, rec)
	if len(m) != 3 {
		t.Fatalf("error envelope keys = %v, want exactly [code message correlation_id]", keysOf(m))
	}
	if m["code"] != code {
		t.Fatalf("code = %v, want %v", m["code"], code)
	}
	if corr, _ := m["correlation_id"].(string); corr == "" {
		t.Fatalf("error envelope missing correlation_id: %s", rec.Body.String())
	}
}

func keysOf(m map[string]interface{}) []string {
	out := make([]string, 0, len(m))
	for k := range m {
		out = append(out, k)
	}
	return out
}

// ---------------------------------------------------------------------------
// step 1: edge handoff, security headers, CF-Connecting-IP trust

func TestSecurityHeadersAndIPSpoofRejected(t *testing.T) {
	f := newFixture(t)
	req := httptest.NewRequest(http.MethodGet, "http://live.example/v1/public/health/", nil)
	req.Header.Set("CF-Connecting-IP", "203.0.113.9") // peer 192.0.2.1 is NOT trusted
	rec := f.do(t, req)
	wantCode(t, rec, http.StatusOK)
	if got := rec.Header().Get("X-Content-Type-Options"); got != "nosniff" {
		t.Fatalf("X-Content-Type-Options = %q", got)
	}
	if rec.Header().Get("Strict-Transport-Security") == "" {
		t.Fatal("missing HSTS header")
	}
	m := jsonBody(t, rec)
	if m["data"].(map[string]interface{})["client_ip"] != "192.0.2.1" {
		t.Fatalf("spoofed CF IP accepted: %v", m["data"])
	}

	req2 := httptest.NewRequest(http.MethodGet, "http://live.example/v1/public/health/", nil)
	req2.RemoteAddr = "203.0.113.5:41000" // trusted edge peer
	req2.Header.Set("CF-Connecting-IP", "203.0.113.9")
	rec2 := f.do(t, req2)
	m2 := jsonBody(t, rec2)
	if m2["data"].(map[string]interface{})["client_ip"] != "203.0.113.9" {
		t.Fatalf("trusted CF IP not honored: %v", m2["data"])
	}
}

// ---------------------------------------------------------------------------
// step 2: host -> tenant resolution

func TestUnknownHost(t *testing.T) {
	f := newFixture(t)
	req := httptest.NewRequest(http.MethodGet, "http://unknown.example/v1/public/health/", nil)
	rec := f.do(t, req)
	wantError(t, rec, http.StatusNotFound, "tenant.unknown_host")
}

// ---------------------------------------------------------------------------
// order: authn (3) before gates (3.5); suspended tenant / pre-live class rules

func TestAuthnRunsBeforeStatusGates(t *testing.T) {
	f := newFixture(t)
	req := httptest.NewRequest(http.MethodGet, "http://bad.example/v1/admin/kyc/", nil)
	req.Header.Set("Authorization", "Bearer garbage")
	rec := f.do(t, req)
	// suspended tenant would be 403, but authentication fails first -> 401
	wantError(t, rec, http.StatusUnauthorized, "auth.invalid_credentials")
}

func TestSuspendedTenant(t *testing.T) {
	f := newFixture(t)
	req := httptest.NewRequest(http.MethodGet, "http://bad.example/v1/admin/kyc/", nil)
	req.Header.Set("Authorization", "Bearer staff-token")
	rec := f.do(t, req)
	wantError(t, rec, http.StatusForbidden, "tenant.suspended")
}

func TestPreLiveTenantClassRules(t *testing.T) {
	f := newFixture(t)
	// trader surface blocked pre-live
	req := httptest.NewRequest(http.MethodPost, "http://onboarding.example/v1/trader/challenges/", strings.NewReader("{}"))
	req.Header.Set("Authorization", "Bearer user-token-1")
	rec := f.do(t, req)
	wantError(t, rec, http.StatusForbidden, "tenant.not_live")

	// staff/admin surface allowed pre-live
	req2 := httptest.NewRequest(http.MethodGet, "http://onboarding.example/v1/admin/kyc/", nil)
	req2.Header.Set("Authorization", "Bearer staff-token")
	rec2 := f.do(t, req2)
	wantCode(t, rec2, http.StatusOK)
}

func TestSuspendedIdentity(t *testing.T) {
	f := newFixture(t)
	req := httptest.NewRequest(http.MethodGet, "http://live.example/v1/admin/kyc/", nil)
	req.Header.Set("Authorization", "Bearer staff-token-2") // s2 suspended
	rec := f.do(t, req)
	wantError(t, rec, http.StatusForbidden, "auth.account_suspended")
}

// ---------------------------------------------------------------------------
// step 4: permission keys, own-scope, step-up (D38)

func TestAuthzRoleAndOwnScope(t *testing.T) {
	f := newFixture(t)

	// trader hitting an admin route -> 403
	req := httptest.NewRequest(http.MethodGet, "http://live.example/v1/admin/kyc/", nil)
	req.Header.Set("Authorization", "Bearer user-token-1")
	rec := f.do(t, req)
	wantError(t, rec, http.StatusForbidden, "permission.denied")

	// own-scope mismatch: u2 acting for u1 -> 403
	req2 := httptest.NewRequest(http.MethodPost, "http://live.example/v1/trader/payouts/", strings.NewReader("{}"))
	req2.Header.Set("Authorization", "Bearer user-token-2")
	req2.Header.Set("X-Idempotency-Key", "k-own-1")
	req2.Header.Set("X-Ownee", "u1")
	rec2 := f.do(t, req2)
	wantError(t, rec2, http.StatusForbidden, "permission.denied")

	// own-scope match -> 201
	req3 := httptest.NewRequest(http.MethodPost, "http://live.example/v1/trader/payouts/", strings.NewReader("{}"))
	req3.Header.Set("Authorization", "Bearer user-token-1")
	req3.Header.Set("X-Idempotency-Key", "k-own-2")
	req3.Header.Set("X-Ownee", "u1")
	rec3 := f.do(t, req3)
	wantCode(t, rec3, http.StatusCreated)
}

func TestStepUpRequired(t *testing.T) {
	f := newFixture(t)
	// fresh MFA -> passes
	req := httptest.NewRequest(http.MethodPost, "http://live.example/v1/admin/payouts/", strings.NewReader("{}"))
	req.Header.Set("Authorization", "Bearer staff-token")
	rec := f.do(t, req)
	wantCode(t, rec, http.StatusOK)
	// stale MFA -> 403 authz.step_up_required
	req2 := httptest.NewRequest(http.MethodPost, "http://live.example/v1/admin/payouts/", strings.NewReader("{}"))
	req2.Header.Set("Authorization", "Bearer staff-token-stale")
	rec2 := f.do(t, req2)
	wantError(t, rec2, http.StatusForbidden, "authz.step_up_required")
}

// ---------------------------------------------------------------------------
// step 5: rate limits + Retry-After (GW-29)

func TestRateLimitAuthClass(t *testing.T) {
	f := newFixture(t)
	var last *httptest.ResponseRecorder
	for i := 0; i < 11; i++ {
		req := httptest.NewRequest(http.MethodPost, "http://live.example/v1/auth/login/",
			strings.NewReader(`{"email":"found@example.com","password":"right"}`))
		last = f.do(t, req)
	}
	if last.Code != http.StatusTooManyRequests {
		t.Fatalf("11th login status = %d, want 429", last.Code)
	}
	m := jsonBody(t, last)
	if m["code"] != "rate.limited" {
		t.Fatalf("code = %v, want rate.limited", m["code"])
	}
	if ra := last.Header().Get("Retry-After"); ra == "" {
		t.Fatal("missing Retry-After on 429")
	}
}

// ---------------------------------------------------------------------------
// step 6: entitlements (GW-06)

func TestEntitlementGate(t *testing.T) {
	f := newFixture(t)
	f.ent.Set("tenLive", "mod.challenges", false)
	req := httptest.NewRequest(http.MethodPost, "http://live.example/v1/trader/challenges/", strings.NewReader("{}"))
	req.Header.Set("Authorization", "Bearer user-token-1")
	rec := f.do(t, req)
	wantError(t, rec, http.StatusForbidden, "tenant.not_entitled")

	f.ent.Set("tenLive", "mod.challenges", true)
	req2 := httptest.NewRequest(http.MethodPost, "http://live.example/v1/trader/challenges/", strings.NewReader("{}"))
	req2.Header.Set("Authorization", "Bearer user-token-1")
	rec2 := f.do(t, req2)
	wantCode(t, rec2, http.StatusCreated)
}

// ---------------------------------------------------------------------------
// step 7: idempotency (GW-12): replay + key reuse conflict, hash-only storage

func TestIdempotencyReplayAndConflict(t *testing.T) {
	f := newFixture(t)
	mk := func(key, body string) *http.Request {
		req := httptest.NewRequest(http.MethodPost, "http://live.example/v1/trader/payouts/", strings.NewReader(body))
		req.Header.Set("Authorization", "Bearer user-token-1")
		req.Header.Set("X-Idempotency-Key", key)
		req.Header.Set("X-Ownee", "u1")
		return req
	}
	first := f.do(t, mk("key-1", `{"amount_cents":5000}`))
	wantCode(t, first, http.StatusCreated)

	replay := f.do(t, mk("key-1", `{"amount_cents":5000}`))
	wantCode(t, replay, http.StatusCreated)
	if replay.Header().Get("X-Idempotent-Replay") != "true" {
		t.Fatal("replay missing X-Idempotent-Replay: true")
	}
	if replay.Body.String() != first.Body.String() {
		t.Fatalf("replay body differs:\n%s\n%s", first.Body.String(), replay.Body.String())
	}

	conflict := f.do(t, mk("key-1", `{"amount_cents":9999}`))
	wantError(t, conflict, http.StatusConflict, "request.idempotency_conflict")

	// different key, same body -> new request
	second := f.do(t, mk("key-2", `{"amount_cents":5000}`))
	wantCode(t, second, http.StatusCreated)

	// only hashes may be persisted: the store must not hold raw bodies
	f.idem.mu.Lock()
	for k, rec := range f.idem.m {
		if rec.body != nil && bytes.Contains(rec.body, []byte("amount_cents")) {
			f.idem.mu.Unlock()
			t.Fatalf("raw body persisted under %s", k)
		}
	}
	f.idem.mu.Unlock()
}

// ---------------------------------------------------------------------------
// step 9: payload limits + timeout (GW-13)

func TestPayloadTooLarge(t *testing.T) {
	f := newFixture(t)
	big := bytes.NewReader(make([]byte, 2<<20))
	req := httptest.NewRequest(http.MethodPost, "http://live.example/v1/trader/payouts/", big)
	req.Header.Set("Authorization", "Bearer user-token-1")
	req.Header.Set("X-Idempotency-Key", "k-big")
	req.Header.Set("X-Ownee", "u1")
	rec := f.do(t, req)
	wantError(t, rec, http.StatusRequestEntityTooLarge, "gw.payload_too_large")
}

func TestHandlerTimeout(t *testing.T) {
	f := newFixture(t)
	f.b.cfg.HandlerTimeout = 20 * time.Millisecond
	slow := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		time.Sleep(200 * time.Millisecond)
		WriteSuccess(w, r, "never")
	})
	// public route (no permission key) so the anonymous request reaches the
	// sleeping handler and the timeout fires
	h := f.b.Build(http.MethodGet, Route{Name: "slow", Class: "admin"}, slow)
	srv := httptest.NewServer(h)
	defer srv.Close()
	req := httptest.NewRequest(http.MethodGet, srv.URL, nil)
	req.Host = "live.example" // satisfy step 2 (host -> tenant)
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusGatewayTimeout {
		t.Fatalf("timeout status = %d, want 504", resp.StatusCode)
	}
	var m map[string]interface{}
	_ = json.NewDecoder(resp.Body).Decode(&m)
	if m["code"] != "gw.timeout" {
		t.Fatalf("timeout code = %v", m["code"])
	}
}

// ---------------------------------------------------------------------------
// correlation (GW-09/36): adopt inbound, mint otherwise; 405 keeps correlation

func TestCorrelationAdoptOrMint(t *testing.T) {
	f := newFixture(t)
	req := httptest.NewRequest(http.MethodGet, "http://live.example/v1/public/health/", nil)
	req.Header.Set("X-Correlation-Id", "01JABCDEF0123456789ABCDEF0")
	rec := f.do(t, req)
	if got := rec.Header().Get("X-Correlation-Id"); got != "01JABCDEF0123456789ABCDEF0" {
		t.Fatalf("inbound correlation not adopted: %q", got)
	}
	m := jsonBody(t, rec)
	if m["meta"].(map[string]interface{})["request_id"] != "01JABCDEF0123456789ABCDEF0" {
		t.Fatalf("request_id != inbound correlation: %v", m["meta"])
	}

	rec2 := f.do(t, httptest.NewRequest(http.MethodGet, "http://live.example/v1/public/health/", nil))
	minted := rec2.Header().Get("X-Correlation-Id")
	if len(minted) != 26 {
		t.Fatalf("minted correlation len = %d, want 26 (ULID)", len(minted))
	}
}

func TestMethodNotAllowedKeepsCorrelation(t *testing.T) {
	f := newFixture(t)
	req := httptest.NewRequest(http.MethodPost, "http://live.example/v1/admin/kyc/", nil)
	rec := f.do(t, req)
	wantError(t, rec, http.StatusMethodNotAllowed, "gw.method_not_allowed")
	if rec.Header().Get("X-Correlation-Id") == "" {
		t.Fatal("405 missing X-Correlation-Id")
	}
}

// ---------------------------------------------------------------------------
// envelopes: D45 success shape, GW-18 exact error keys

func TestEnvelopeShapes(t *testing.T) {
	f := newFixture(t)
	rec := f.do(t, httptest.NewRequest(http.MethodGet, "http://live.example/v1/public/health/", nil))
	m := jsonBody(t, rec)
	if len(m) != 2 {
		t.Fatalf("success envelope keys = %v, want exactly [data meta]", keysOf(m))
	}
	meta := m["meta"].(map[string]interface{})
	if len(meta) != 2 {
		t.Fatalf("meta keys = %v, want exactly [request_id version] (pagination only on lists)", keysOf(meta))
	}
	if meta["version"] != "v1" {
		t.Fatalf("meta.version = %v", meta["version"])
	}

	wantError(t, f.do(t, httptest.NewRequest(http.MethodGet, "http://unknown.example/x", nil)),
		http.StatusNotFound, "tenant.unknown_host")
}

// ---------------------------------------------------------------------------
// GW-17: audit success AND failure of sensitive actions

func TestAuditSuccessAndFailure(t *testing.T) {
	f := newFixture(t)
	ok := httptest.NewRequest(http.MethodPost, "http://live.example/v1/admin/payouts/", strings.NewReader("{}"))
	ok.Header.Set("Authorization", "Bearer staff-token")
	f.do(t, ok)

	denied := httptest.NewRequest(http.MethodPost, "http://live.example/v1/admin/payouts/", strings.NewReader("{}"))
	denied.Header.Set("Authorization", "Bearer user-token-1")
	f.do(t, denied)

	if len(f.audit.events) != 2 {
		t.Fatalf("audit events = %d, want 2: %+v", len(f.audit.events), f.audit.events)
	}
	if !f.audit.events[0].Success || f.audit.events[0].PrincipalID != "s1" {
		t.Fatalf("success event wrong: %+v", f.audit.events[0])
	}
	if f.audit.events[1].Success {
		t.Fatalf("denied attempt must audit as failure: %+v", f.audit.events[1])
	}
	if f.audit.events[1].CorrelationID == "" {
		t.Fatal("audit event missing correlation")
	}
}

// ---------------------------------------------------------------------------
// /internal/* service realm: static bearer + X-Tenant-Id

func TestInternalServiceRealm(t *testing.T) {
	f := newFixture(t)
	req := httptest.NewRequest(http.MethodPost, "http://internal.example/internal/jobs/", strings.NewReader("{}"))
	req.Header.Set("Authorization", "Bearer svc-token-alpha")
	req.Header.Set("X-Tenant-Id", "tenLive")
	rec := f.do(t, req)
	wantCode(t, rec, http.StatusCreated)

	// missing tenant header -> 403 (never tenant resolution by host on this plane)
	req2 := httptest.NewRequest(http.MethodPost, "http://internal.example/internal/jobs/", strings.NewReader("{}"))
	req2.Header.Set("Authorization", "Bearer svc-token-alpha")
	rec2 := f.do(t, req2)
	wantError(t, rec2, http.StatusForbidden, "permission.denied")

	// wrong service token -> 401
	req3 := httptest.NewRequest(http.MethodPost, "http://internal.example/internal/jobs/", strings.NewReader("{}"))
	req3.Header.Set("Authorization", "Bearer nope")
	req3.Header.Set("X-Tenant-Id", "tenLive")
	rec3 := f.do(t, req3)
	wantError(t, rec3, http.StatusUnauthorized, "auth.invalid_credentials")
}

// ---------------------------------------------------------------------------
// probes

func TestHealthzReadyz(t *testing.T) {
	hz := Healthz()
	rec := httptest.NewRecorder()
	hz.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/healthz", nil))
	if rec.Code != http.StatusOK {
		t.Fatalf("healthz = %d", rec.Code)
	}

	rz := Readyz(map[string]Check{
		"pg":    func(context.Context) error { return nil },
		"redis": func(context.Context) error { return errorf("down") },
	})
	rec2 := httptest.NewRecorder()
	rz.ServeHTTP(rec2, httptest.NewRequest(http.MethodGet, "/readyz", nil))
	if rec2.Code != http.StatusServiceUnavailable {
		t.Fatalf("readyz = %d, want 503", rec2.Code)
	}
	var m map[string]interface{}
	_ = json.Unmarshal(rec2.Body.Bytes(), &m)
	failed := m["failed"].([]interface{})
	if len(failed) != 1 || failed[0] != "redis" {
		t.Fatalf("readyz failed = %v", failed)
	}
}

// compile-time interface checks
var (
	_ TokenVerifier    = VerifierFunc(nil)
	_ TenantResolver   = (*MapResolver)(nil)
	_ TenantResolver   = (*CachedResolver)(nil)
	_ StatusGate       = (*MapStatusGate)(nil)
	_ StatusGate       = (*CachedGate)(nil)
	_ Limiter          = (*MemLimiter)(nil)
	_ Entitlements     = (*MapEntitlements)(nil)
	_ IdempotencyStore = (*MemIdemStore)(nil)
	_ AuditSink        = (*auditRecorder)(nil)
)

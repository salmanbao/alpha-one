package gw

import (
	"encoding/json"
	"net/http"
)

// APIVersion is the meta.version value of the D45 success envelope.
const APIVersion = "v1"

// Page is the cursor-pagination block (GW-21).
type Page struct {
	Cursor  string `json:"cursor"`
	HasMore bool   `json:"has_more"`
}

type meta struct {
	RequestID  string `json:"request_id"`
	Version    string `json:"version"`
	Pagination *Page  `json:"pagination,omitempty"`
}

type successEnvelope struct {
	Data interface{} `json:"data"`
	Meta meta        `json:"meta"`
}

// ErrorEnvelope is the GW-18 error contract: exactly code, message,
// correlation_id.
type ErrorEnvelope struct {
	Code          string `json:"code"`
	Message       string `json:"message"`
	CorrelationID string `json:"correlation_id"`
}

// codeStatus maps registered error codes to their HTTP status (the V1
// baseline set plus the extended codes this package emits). An unregistered
// code collapses to 500 + gw.internal_error — the same rule docs/04 §6.2
// enforces in CI (a leaked unregistered code must fail error_registry_test).
var codeStatus = map[string]int{
	"tenant.unknown_host":          404,
	"auth.invalid_credentials":     401,
	"permission.denied":            403,
	"rate.limited":                 429,
	"request.idempotency_conflict": 409,
	"tenant.suspended":             403,
	"tenant.not_live":              403,
	"auth.account_suspended":       403,
	"auth.membership_suspended":    403,
	"tenant.not_entitled":          403,
	"module.unknown":               400,
	"authz.step_up_required":       403,
	"webhook.signature_invalid":    401,
	"gw.payload_too_large":         413,
	"gw.method_not_allowed":        405,
	"gw.timeout":                   504,
	"gw.internal_error":            500,
}

// WriteSuccess renders the binding D45 envelope:
// {data, meta{request_id, version}}.
func WriteSuccess(w http.ResponseWriter, r *http.Request, data interface{}) {
	writeJSON(w, http.StatusOK, successEnvelope{
		Data: data,
		Meta: meta{RequestID: CorrelationFrom(r.Context()), Version: APIVersion},
	})
}

// WriteCreated is WriteSuccess with a 201 status (POST creations).
func WriteCreated(w http.ResponseWriter, r *http.Request, data interface{}) {
	writeJSON(w, http.StatusCreated, successEnvelope{
		Data: data,
		Meta: meta{RequestID: CorrelationFrom(r.Context()), Version: APIVersion},
	})
}

// WritePage is WriteSuccess for list endpoints (cursor pagination).
func WritePage(w http.ResponseWriter, r *http.Request, data interface{}, cursor string, hasMore bool) {
	writeJSON(w, http.StatusOK, successEnvelope{
		Data: data,
		Meta: meta{
			RequestID:  CorrelationFrom(r.Context()),
			Version:    APIVersion,
			Pagination: &Page{Cursor: cursor, HasMore: hasMore},
		},
	})
}

// WriteError renders GW-18. Unknown codes collapse to 500/gw.internal_error
// with a message that leaks nothing.
func WriteError(w http.ResponseWriter, r *http.Request, code, message string) {
	status, ok := codeStatus[code]
	if !ok {
		code, status, message = "gw.internal_error", http.StatusInternalServerError, "Internal error."
	}
	corr := CorrelationFrom(r.Context())
	w.Header().Set("X-Correlation-Id", corr)
	writeJSON(w, status, ErrorEnvelope{Code: code, Message: message, CorrelationID: corr})
}

func writeJSON(w http.ResponseWriter, status int, v interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}

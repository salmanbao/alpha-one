package main

// The Guard (doc §5.4): the security invariants on every message, in the same
// order as the doc:
//   1. signature (HMAC-SHA256, session key)
//   2. sequence continuity
//   3. replay (nonce + 90 s ts skew window)
//   4. tenant/account binding
//
// PRODUCTION NOTE: this Go implementation is the *reference* behavior. The
// production hot path is the Rust crate behind the `Guard` gRPC service in
// contracts/proto (doc §10.1) — same verdicts, < 1 µs per message. The
// interface here (Verify -> GuardVerdict) is exactly the RPC's request/response,
// so the swap is mechanical.

import (
	"errors"
	"fmt"
	"time"
)

type GuardVerdict string

const (
	GuardOK          GuardVerdict = "ok"
	GuardBadSig      GuardVerdict = "bad_sig"
	GuardReplay      GuardVerdict = "replay"
	GuardGap         GuardVerdict = "gap"
	GuardBinding     GuardVerdict = "binding"
	GuardSkew        GuardVerdict = "skew"
	GuardMalformed   GuardVerdict = "malformed"
	GuardNoSession   GuardVerdict = "no_session"
)

type GuardError struct {
	Verdict GuardVerdict
	Detail  string
}

func (e *GuardError) Error() string { return fmt.Sprintf("%s: %s", e.Verdict, e.Detail) }

var (
	ErrBadSig    = &GuardError{Verdict: GuardBadSig}
	ErrReplay    = &GuardError{Verdict: GuardReplay}
	ErrGap       = &GuardError{Verdict: GuardGap}
	ErrBinding   = &GuardError{Verdict: GuardBinding}
	ErrSkew      = &GuardError{Verdict: GuardSkew}
	ErrMalformed = &GuardError{Verdict: GuardMalformed}
	ErrNoSession = &GuardError{Verdict: GuardNoSession}
)

func guardErr(v GuardVerdict, detail string) error {
	return &GuardError{Verdict: v, Detail: detail}
}

const (
	maxTSkew   = 90 * time.Second  // doc §5.4 #3
	nonceTTL   = 60 * time.Second  // replay window
	seqTolerance = 0               // strict continuity; gap => RESYNC (doc §5.2)
)

// Verify checks one envelope against the session. now is bridge NTP time.
func verify(env *Envelope, s *Session, now time.Time) (GuardVerdict, error) {
	if env == nil {
		return GuardMalformed, guardErr(GuardMalformed, "nil envelope")
	}
	if s == nil {
		return GuardNoSession, guardErr(GuardNoSession, "no session for tenant/account")
	}

	// 4. binding (checked first: cheap, and prevents cross-tenant key misuse even if sig is valid)
	if env.Tenant != s.Tenant || env.Account != s.Account {
		return GuardBinding, guardErr(GuardBinding,
			fmt.Sprintf("frame %s/%s does not match session %s/%s", env.Tenant, env.Account, s.Tenant, s.Account))
	}

	// 1. signature
	canonical, err := canonicalBytes(env)
	if err != nil {
		return GuardMalformed, guardErr(GuardMalformed, "canonicalize: "+err.Error())
	}
	if !verifySig(s.SessionKey, canonical, env.Sig) {
		return GuardBadSig, guardErr(GuardBadSig, "HMAC mismatch")
	}

	// 3. replay: ts skew + nonce
	if delta := time.Since(time.UnixMilli(env.TsClient)); delta < -maxTSkew || delta > maxTSkew {
		return GuardSkew, guardErr(GuardSkew, fmt.Sprintf("ts_client skew exceeds %s", maxTSkew))
	}
	if !s.seenNonce(env.Nonce, now) {
		return GuardReplay, guardErr(GuardReplay, "nonce already seen (replay)")
	}

	// 2. sequence continuity (strict; out-of-order => snapshot resync)
	s.mu.Lock()
	expected := s.LastSeq + 1
	s.mu.Unlock()
	if env.Seq != expected+seqTolerance {
		return GuardGap, guardErr(GuardGap,
			fmt.Sprintf("seq %d != expected %d", env.Seq, expected))
	}

	return GuardOK, nil
}

// VerifyHello checks a hello frame against the PAIRING key (bootstrap only).
func verifyHello(env *Envelope, pairing *Pairing, now time.Time) (GuardVerdict, error) {
	if pairing == nil || pairing.Revoked {
		return GuardNoSession, guardErr(GuardNoSession, "unknown or revoked pairing")
	}
	if env.Tenant != pairing.Tenant || env.Account != pairing.Account {
		return GuardBinding, guardErr(GuardBinding, "hello tenant/account mismatch")
	}
	if delta := time.Since(time.UnixMilli(env.TsClient)); delta < -maxTSkew || delta > maxTSkew {
		return GuardSkew, guardErr(GuardSkew, "hello ts skew")
	}
	key, err := hexDecode(pairing.PairingKey)
	if err != nil {
		return GuardMalformed, guardErr(GuardMalformed, "bad pairing key encoding")
	}
	canonical, err := canonicalBytes(env)
	if err != nil {
		return GuardMalformed, guardErr(GuardMalformed, err.Error())
	}
	if !verifySig(key, canonical, env.Sig) {
		return GuardBadSig, guardErr(GuardBadSig, "hello HMAC mismatch (pairing key)")
	}
	return GuardOK, nil
}

var _ = errors.New

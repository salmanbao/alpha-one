package main

// Sessions (doc §5.2): stored outside the node so any bridge node can resume
// any account. Scaffold: in-memory; production: Redis hash
// {tenant:account -> {node_id, seq, sess_key_ref, pack_ver, state, since}}.

import (
	"sync"
	"time"
)

type SessionState string

const (
	StateAuthed   SessionState = "ACTIVE"
	StateResync   SessionState = "RESYNC"
	StateSuspended SessionState = "SUSPENDED"
)

// PendingCtl is a control command not yet acked by the terminal (doc §5.8:
// "a halt must survive terminal disconnects" — replayed on every reconnect).
type PendingCtl struct {
	CTLSeq  string
	Command string
	Payload map[string]any
}

type Session struct {
	Tenant     string
	Account    string
	SessionKey []byte // 32 bytes; signs every frame after auth
	PackVer    string
	State      SessionState
	LastSeq    uint64
	NodeID     string

	mu       sync.Mutex
	nonces   map[string]int64 // nonce -> first-seen ms (60 s window)
	pending  []PendingCtl     // unacked control commands
}

func newSession(tenant, account string, key []byte, nodeID, packVer string) *Session {
	return &Session{
		Tenant: tenant, Account: account, SessionKey: key, NodeID: nodeID, PackVer: packVer,
		State:  StateAuthed,
		nonces: map[string]int64{},
	}
}

// seenNonce returns false if the nonce was already used in the replay window.
func (s *Session) seenNonce(nonce string, now time.Time) bool {
	s.mu.Lock()
	defer s.mu.Unlock()
	// purge expired
	deadline := now.Add(-60 * time.Second)
	for k, ts := range s.nonces {
		if time.UnixMilli(ts).Before(deadline) {
			delete(s.nonces, k)
		}
	}
	if _, ok := s.nonces[nonce]; ok {
		return false
	}
	s.nonces[nonce] = now.UnixMilli()
	return true
}

func (s *Session) markResync() {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.State = StateResync
}

func (s *Session) markActive() {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.State = StateAuthed
}

func (s *Session) setLastSeq(seq uint64) {
	s.mu.Lock()
	if seq > s.LastSeq {
		s.LastSeq = seq
	}
	s.mu.Unlock()
}

func (s *Session) addPending(p PendingCtl) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.pending = append(s.pending, p)
}

func (s *Session) takePending() []PendingCtl {
	s.mu.Lock()
	defer s.mu.Unlock()
	out := s.pending
	s.pending = nil
	return out
}

// ---------------------------------------------------------------------------

type SessionStore struct {
	mu       sync.RWMutex
	sessions map[string]*Session
	nodeID   string
}

func newSessionStore(nodeID string) *SessionStore {
	return &SessionStore{sessions: map[string]*Session{}, nodeID: nodeID}
}

func (st *SessionStore) Get(tenant, account string) *Session {
	st.mu.RLock()
	defer st.mu.RUnlock()
	return st.sessions[pairingKey(tenant, account)]
}

func (st *SessionStore) Put(s *Session) {
	st.mu.Lock()
	defer st.mu.Unlock()
	s.NodeID = st.nodeID
	st.sessions[pairingKey(s.Tenant, s.Account)] = s
}

func (st *SessionStore) Delete(tenant, account string) {
	st.mu.Lock()
	defer st.mu.Unlock()
	delete(st.sessions, pairingKey(tenant, account))
}

func (st *SessionStore) Count() int {
	st.mu.RLock()
	defer st.mu.RUnlock()
	return len(st.sessions)
}

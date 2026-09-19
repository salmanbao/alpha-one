package main

// Keystore: pairing records (doc §5.5).
//
// Scaffold: in-memory map. Production: PostgreSQL `pairings` (key hashed with
// Argon2id, wrapped copy in Vault) + device fingerprint fields (doc §8.2, §8.5).

import (
	"sync"
)

type Pairing struct {
	Tenant     string
	Account    string
	Platform   string
	PairingKey string // 32-byte hex; shown once, signs only hello frames
	Revoked    bool
}

type Keystore struct {
	mu  sync.RWMutex
	pairings map[string]*Pairing
}

func newKeystore() *Keystore {
	return &Keystore{pairings: map[string]*Pairing{}}
}

func pairingKey(tenant, account string) string { return tenant + "\x00" + account }

// CreatePairing provisions a new pairing for (tenant, account) — the
// "Connect MT5 account" flow (doc §5.5). Returns the one-time pairing key.
func (k *Keystore) CreatePairing(tenant, account, platform string) (*Pairing, string, error) {
	key, err := randomHex(32)
	if err != nil {
		return nil, "", err
	}
	p := &Pairing{Tenant: tenant, Account: account, Platform: platform, PairingKey: key}
	k.mu.Lock()
	k.pairings[pairingKey(tenant, account)] = p
	k.mu.Unlock()
	return p, key, nil
}

func (k *Keystore) Lookup(tenant, account string) *Pairing {
	k.mu.RLock()
	defer k.mu.RUnlock()
	return k.pairings[pairingKey(tenant, account)]
}

// Revoke kills a pairing (compromised device / fraud — doc §8.5).
func (k *Keystore) Revoke(tenant, account string) {
	k.mu.Lock()
	defer k.mu.Unlock()
	if p, ok := k.pairings[pairingKey(tenant, account)]; ok {
		p.Revoked = true
	}
}

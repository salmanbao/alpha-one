package main

// Snapshot / resync (doc §5.2, diagram 08).
//
// When the guard detects a sequence gap, the session enters RESYNC: the bridge
// asks the terminal to collect its full state (spooled evidence + live book).
// The terminal replies with chunked snapshots; the final chunk carries a
// SHA-256 checksum over the canonical chunk bytes. On success the session
// resumes from the baseline seq and unacked control commands are replayed.
//
// Scaffold: single chunk over WS. Production: N chunks (128 positions / 32 KB),
// rate-limited per account (2 chunks/s) per doc §9.4-4.

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
)

type SnapshotPayload struct {
	ChunkNo  int            `json:"chunk_no"`
	Final    bool           `json:"final"`
	Balance  string         `json:"balance"`
	Positions []PositionDTO `json:"positions"`
	Deals    []DealDTO      `json:"deals"`
	Checksum string         `json:"checksum,omitempty"` // final chunk only
}

type PositionDTO struct {
	OrderID  string `json:"order_id"`
	Symbol   string `json:"symbol"`
	Side     string `json:"side"`
	Volume   string `json:"volume"`
	EntryPx  string `json:"entry_px"`
	LastPx   string `json:"last_px"`
	BrokerTS int64  `json:"broker_ts"`
}

type DealDTO struct {
	DealID   string `json:"deal_id"`
	OrderID  string `json:"order_id"`
	Symbol   string `json:"symbol"`
	PnL      string `json:"pnl"`
	BrokerTS int64  `json:"broker_ts"`
}

// VerifyChecksum checks the final chunk's checksum over its canonical bytes
// (positions+deals+balance, sorted keys — same canonicalization as envelopes).
func verifySnapshotChecksum(p *SnapshotPayload) error {
	body, err := json.Marshal(map[string]any{
		"balance":   p.Balance,
		"positions": p.Positions,
		"deals":     p.Deals,
	})
	if err != nil {
		return err
	}
	// sorted-key normalization
	var v any
	if err := json.Unmarshal(body, &v); err != nil {
		return err
	}
	norm, err := json.Marshal(sortKeys(v))
	if err != nil {
		return err
	}
	sum := sha256.Sum256(norm)
	got := hex.EncodeToString(sum[:])
	if got != p.Checksum {
		return fmt.Errorf("snapshot checksum mismatch: computed %s, got %s", got, p.Checksum)
	}
	return nil
}

// ComputeSnapshotChecksum is the terminal-side counterpart (used by the EA and
// by tests). Exported for the MQL/TS ports to mirror exactly.
func ComputeSnapshotChecksum(balance string, positions []PositionDTO, deals []DealDTO) (string, error) {
	body, err := json.Marshal(map[string]any{
		"balance":   balance,
		"positions": positions,
		"deals":     deals,
	})
	if err != nil {
		return "", err
	}
	var v any
	if err := json.Unmarshal(body, &v); err != nil {
		return "", err
	}
	norm, err := json.Marshal(sortKeys(v))
	if err != nil {
		return "", err
	}
	sum := sha256.Sum256(norm)
	return hex.EncodeToString(sum[:]), nil
}

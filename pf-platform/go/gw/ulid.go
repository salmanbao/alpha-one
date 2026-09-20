package gw

import (
	"crypto/rand"
	"strings"
	"time"
)

const crockfordAlphabet = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"

// MintULID returns a 26-character Crockford-base32 ULID: 48 bits of
// millisecond timestamp + 80 bits from crypto/rand.
func MintULID() string {
	var b [16]byte
	ms := time.Now().UnixMilli()
	b[0] = byte(ms >> 40)
	b[1] = byte(ms >> 32)
	b[2] = byte(ms >> 24)
	b[3] = byte(ms >> 16)
	b[4] = byte(ms >> 8)
	b[5] = byte(ms)
	if _, err := rand.Read(b[6:]); err != nil {
		for i := 6; i < 16; i++ {
			b[i] = byte(ms >> uint(i*3))
		}
	}
	return encodeCrockford(b[:])
}

// encodeCrockford encodes 16 bytes as 26 Crockford-base32 characters
// (128 bits -> 26 x 5-bit groups, zero-padded on the right).
func encodeCrockford(b []byte) string {
	var out [26]byte
	var buf uint32
	var bits uint
	idx := 0
	for _, by := range b {
		buf = buf<<8 | uint32(by)
		bits += 8
		for bits >= 5 && idx < 26 {
			bits -= 5
			out[idx] = crockfordAlphabet[(buf>>bits)&0x1F]
			idx++
		}
	}
	if bits > 0 && idx < 26 {
		out[idx] = crockfordAlphabet[(buf<<(5-bits))&0x1F]
		idx++
	}
	return string(out[:])
}

// ValidCorrelation accepts a Crockford ULID or any short opaque token an
// upstream edge already minted; rejects empties, whitespace and control chars.
func ValidCorrelation(s string) bool {
	if len(s) < 8 || len(s) > 64 || strings.TrimSpace(s) != s {
		return false
	}
	for i := 0; i < len(s); i++ {
		c := s[i]
		if !(('0' <= c && c <= '9') || ('a' <= c && c <= 'z') || ('A' <= c && c <= 'Z') || c == '-') {
			return false
		}
	}
	return true
}

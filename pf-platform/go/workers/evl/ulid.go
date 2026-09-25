package evl

import (
	"crypto/rand"
	"encoding/binary"
	"sync"
	"time"
)

const crockford = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"

var (
	ulidMu   sync.Mutex
	lastMs   uint64
	lastRand [10]byte
)

// NewULID returns a monotonic ULID (48-bit ms timestamp + 80-bit random;
// within one millisecond the random part is incremented so ids sort in
// creation order).
func NewULID() string {
	ulidMu.Lock()
	defer ulidMu.Unlock()
	ms := uint64(time.Now().UnixMilli())
	if ms == lastMs {
		for i := 9; i >= 0; i-- {
			lastRand[i]++
			if lastRand[i] != 0 {
				break
			}
		}
	} else {
		lastMs = ms
		_, _ = rand.Read(lastRand[:])
	}
	var b [16]byte
	var ts [8]byte
	binary.BigEndian.PutUint64(ts[:], ms)
	copy(b[0:6], ts[2:8])
	copy(b[6:], lastRand[:])
	return encodeULID(b)
}

func encodeULID(b [16]byte) string {
	// 128 bits → 26 base32 chars (the first char carries 3 bits).
	out := make([]byte, 26)
	var hi, lo uint64
	hi = binary.BigEndian.Uint64(b[0:8])
	lo = binary.BigEndian.Uint64(b[8:16])
	for i := 25; i >= 0; i-- {
		out[i] = crockford[lo&31]
		lo = lo>>5 | hi<<59
		hi >>= 5
	}
	return string(out)
}

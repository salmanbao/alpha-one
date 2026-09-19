package main

// Minimal ULID (Crockford base32): 48-bit ms timestamp + 80-bit random, 26 chars.
// The wire contract uses ULIDs for every event/command id (doc §5.3).

import (
	"crypto/rand"
	"encoding/hex"
	"time"
)

// hexDecode: the pairing/session keys travel as hex strings on the wire.
func hexDecode(s string) ([]byte, error) { return hex.DecodeString(s) }

const crockford = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"

// newULID returns a monotonically-timestamped, unique id.
// Layout (128 bits): [ts 48b][random 80b]; char i encodes bits (127-5i .. 123-5i).
func newULID() string {
	var buf [16]byte
	ts := uint64(time.Now().UnixMilli())
	buf[0] = byte(ts >> 40)
	buf[1] = byte(ts >> 32)
	buf[2] = byte(ts >> 24)
	buf[3] = byte(ts >> 16)
	buf[4] = byte(ts >> 8)
	buf[5] = byte(ts)
	_, _ = rand.Read(buf[6:])

	out := make([]byte, 26)
	for i := 0; i < 26; i++ {
		bit := i * 5
		by := bit / 8
		shift := bit % 8
		var v byte
		switch {
		case shift <= 3:
			v = buf[by] >> uint(shift)
		case by+1 < len(buf):
			v = (buf[by] >> uint(shift)) | (buf[by+1] << uint(8-shift))
		default: // last char: only the top 3 bits of the final byte exist
			v = buf[by] >> uint(shift)
		}
		out[i] = crockford[v&0x1f]
	}
	return string(out)
}

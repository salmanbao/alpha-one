package consumer

import (
	"hash/fnv"
	"math"
	"sort"
)

// LaneOf maps an entity to one of n lanes with Jump Consistent Hash
// (Lamping & Veach, 2014) over FNV-1a-64 of the entity id: stable for a
// fixed n, and when n changes only ≈ 1/n of entities move. The lane is the
// unit of ordering: one goroutine per lane, messages processed serially.
func LaneOf(entityID string, n int) int {
	if n <= 1 {
		return 0
	}
	h := fnv.New64a()
	_, _ = h.Write([]byte(entityID))
	key := h.Sum64()
	var b, j int64 = -1, 0
	for j < int64(n) {
		b = j
		key = key*2862933555777941757 + 1
		j = int64(float64(b+1) * (float64(int64(1)<<31) / float64((key>>33)+1)))
	}
	return int(b)
}

// TotalLanes is D82's fleet lane budget: max(128, 10 × tenants)
// (docs/63 §4.13).
func TotalLanes(tenants int) int {
	if t := 10 * tenants; t > 128 {
		return t
	}
	return 128
}

// AllocateLanes is D82's tenant-owned lane sets: tenant t gets
// max(10, ceil(w_t / Σw × total)) lanes, total = TotalLanes(len(weights)).
// A non-positive weight counts as 1. The floor of 10 means a small tenant
// is never starved by rounding; the sum may exceed `total` by at most
// 10 × tenants, which is the point (fairness over a hard budget).
func AllocateLanes(weights map[string]float64) map[string]int {
	out := make(map[string]int, len(weights))
	if len(weights) == 0 {
		return out
	}
	total := float64(TotalLanes(len(weights)))
	sum := 0.0
	keys := make([]string, 0, len(weights))
	for k, w := range weights {
		if w <= 0 {
			w = 1
		}
		sum += w
		keys = append(keys, k)
	}
	sort.Strings(keys)
	for _, k := range keys {
		w := weights[k]
		if w <= 0 {
			w = 1
		}
		n := int(math.Ceil(w / sum * total))
		if n < 10 {
			n = 10
		}
		out[k] = n
	}
	return out
}

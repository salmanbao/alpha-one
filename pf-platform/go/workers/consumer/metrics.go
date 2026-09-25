package consumer

import (
	"fmt"
	"io"
	"math"
	"net/http"
	"sort"
	"strings"
	"sync"
)

// Metrics is a minimal Prometheus text-format registry (counters, gauges,
// fixed-bucket histograms). Hand-rolled to keep the module's dependency set
// to lib/pq + go-redis.
type Metrics struct {
	mu       sync.Mutex
	counters map[string]float64
	gauges   map[string]float64
	hists    map[string]*hist
	help     map[string]string
	kinds    map[string]string
}

type hist struct {
	buckets []float64
	counts  []uint64
	sum     float64
	n       uint64
}

// DefaultBuckets (seconds) for latency histograms.
var DefaultBuckets = []float64{.001, .0025, .005, .01, .025, .05, .1, .25, .5, 1, 2.5, 5, 10, 30, 60, 120, 300, 600}

// NewMetrics returns an empty registry.
func NewMetrics() *Metrics {
	return &Metrics{
		counters: map[string]float64{}, gauges: map[string]float64{}, hists: map[string]*hist{},
		help: map[string]string{}, kinds: map[string]string{},
	}
}

func key(name string, labels []string) string {
	if len(labels) == 0 {
		return name
	}
	if len(labels)%2 != 0 {
		panic("metrics: labels must be key/value pairs")
	}
	pairs := make([]string, 0, len(labels)/2)
	for i := 0; i < len(labels); i += 2 {
		v := strings.NewReplacer(`\`, `\\`, `"`, `\"`, "\n", `\n`).Replace(labels[i+1])
		pairs = append(pairs, fmt.Sprintf(`%s="%s"`, labels[i], v))
	}
	sort.Strings(pairs)
	return name + "{" + strings.Join(pairs, ",") + "}"
}

// Delete removes a gauge series (a stream this instance no longer owns
// must stop exporting its last value, or alerts fire on stale data).
func (m *Metrics) Delete(name string, labels ...string) {
	m.mu.Lock()
	defer m.mu.Unlock()
	delete(m.gauges, key(name, labels))
}

// Help registers a HELP line.
func (m *Metrics) Help(name, kind, text string) {
	m.mu.Lock()
	m.help[name], m.kinds[name] = text, kind
	m.mu.Unlock()
}

// Add increments a counter.
func (m *Metrics) Add(name string, v float64, labels ...string) {
	m.mu.Lock()
	m.counters[key(name, labels)] += v
	m.mu.Unlock()
}

// Inc increments a counter by 1.
func (m *Metrics) Inc(name string, labels ...string) { m.Add(name, 1, labels...) }

// Set sets a gauge.
func (m *Metrics) Set(name string, v float64, labels ...string) {
	m.mu.Lock()
	m.gauges[key(name, labels)] = v
	m.mu.Unlock()
}

// Observe records a histogram sample.
func (m *Metrics) Observe(name string, v float64, labels ...string) {
	k := key(name, labels)
	m.mu.Lock()
	h := m.hists[k]
	if h == nil {
		h = &hist{buckets: DefaultBuckets, counts: make([]uint64, len(DefaultBuckets))}
		m.hists[k] = h
	}
	for i, b := range h.buckets {
		if v <= b {
			h.counts[i]++
		}
	}
	h.sum += v
	h.n++
	m.mu.Unlock()
}

// Counter returns a counter's value (tests).
func (m *Metrics) Counter(name string, labels ...string) float64 {
	m.mu.Lock()
	defer m.mu.Unlock()
	return m.counters[key(name, labels)]
}

// Gauge returns a gauge's value (tests).
func (m *Metrics) Gauge(name string, labels ...string) float64 {
	m.mu.Lock()
	defer m.mu.Unlock()
	return m.gauges[key(name, labels)]
}

// SumCounter sums a counter across all label sets (tests, reports).
func (m *Metrics) SumCounter(name string) float64 {
	m.mu.Lock()
	defer m.mu.Unlock()
	s := 0.0
	for k, v := range m.counters {
		if k == name || strings.HasPrefix(k, name+"{") {
			s += v
		}
	}
	return s
}

// WriteTo writes the Prometheus text exposition.
func (m *Metrics) WriteTo(w io.Writer) (int64, error) {
	m.mu.Lock()
	defer m.mu.Unlock()
	var b strings.Builder
	base := func(k string) string {
		if i := strings.IndexByte(k, '{'); i >= 0 {
			return k[:i]
		}
		return k
	}
	emitted := map[string]bool{}
	header := func(name, kind string) {
		if emitted[name] {
			return
		}
		emitted[name] = true
		if h, ok := m.help[name]; ok {
			fmt.Fprintf(&b, "# HELP %s %s\n", name, h)
		}
		fmt.Fprintf(&b, "# TYPE %s %s\n", name, kind)
	}
	for _, set := range []struct {
		kind string
		vals map[string]float64
	}{{"counter", m.counters}, {"gauge", m.gauges}} {
		keys := make([]string, 0, len(set.vals))
		for k := range set.vals {
			keys = append(keys, k)
		}
		sort.Strings(keys)
		for _, k := range keys {
			header(base(k), set.kind)
			v := set.vals[k]
			if math.IsInf(v, 1) {
				fmt.Fprintf(&b, "%s +Inf\n", k)
			} else {
				fmt.Fprintf(&b, "%s %g\n", k, v)
			}
		}
	}
	hkeys := make([]string, 0, len(m.hists))
	for k := range m.hists {
		hkeys = append(hkeys, k)
	}
	sort.Strings(hkeys)
	for _, k := range hkeys {
		h := m.hists[k]
		name := base(k)
		labels := strings.TrimSuffix(strings.TrimPrefix(k[len(name):], "{"), "}")
		sep := ""
		if labels != "" {
			sep = ","
		}
		header(name, "histogram")
		for i, bk := range h.buckets {
			fmt.Fprintf(&b, "%s_bucket{%s%sle=\"%g\"} %d\n", name, labels, sep, bk, h.counts[i])
		}
		fmt.Fprintf(&b, "%s_bucket{%s%sle=\"+Inf\"} %d\n", name, labels, sep, h.n)
		if labels != "" {
			labels = "{" + labels + "}"
		}
		fmt.Fprintf(&b, "%s_sum%s %g\n%s_count%s %d\n", name, labels, h.sum, name, labels, h.n)
	}
	n, err := io.WriteString(w, b.String())
	return int64(n), err
}

// Handler serves /metrics.
func (m *Metrics) Handler() http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "text/plain; version=0.0.4")
		_, _ = m.WriteTo(w)
	})
}

package evl

import (
	"context"
	"database/sql"
	"encoding/json"
	"log/slog"
	"sync"
	"time"

	"github.com/redis/go-redis/v9"

	"pf-platform/go/workers/consumer"
)

// LoadShedChannel carries evl.load_shed {tenant_id, level, reason, at}
// (docs/63 §4.14) — the evl.floors advisory pattern.
const LoadShedChannel = "evl.load_shed"

// Ladder is D84's per-tenant response to evl_lag_seconds (docs/63 §4.14):
//
//	> 60 s for 60 s     → scale out            (evl_scale_out_wanted = 1)
//	> 120 s for 5 min   → WARN, shed level 1
//	> 300 s             → shed level 2; also level 1 held 15 min → level 2
//	> 300 s for 60 s    → PAGE                 (evl_page = 1)
//	> 480 s, any trim, or a funded tick_stale → INCIDENT, shed level 3
//	                      (evl_incident = 1, held ≥ 10 min after the cause)
//	< 30 s for 10 min   → scale in; shed level back to 0
//
// Levels only go up until the < 30 s-for-10-min recovery condition holds —
// hysteresis, so a lag that oscillates around a threshold does not make
// the bridge flap its conflation thresholds. The ladder publishes
// evl.load_shed on every change and re-publishes every 30 s while the level
// is > 0, so a restarted bridge converges within 30 s (Redis-down degrades
// to level 0 at the bridge — the safe direction).
type Ladder struct {
	// DB, when set, persists each tenant's level in evl_load_shed (the
	// bridge's 30 s reload fallback) and seeds a tenant's ladder from it the
	// first time this instance sees the tenant — so a lease handover
	// resumes the level and incident hold instead of resetting to 0.
	DB      *sql.DB
	Redis   *redis.Client
	Metrics *consumer.Metrics
	Log     *slog.Logger
	Now     func() time.Time

	mu      sync.Mutex
	tenants map[string]*tenantLadder
}

type tenantLadder struct {
	level                                int
	over60, over120, over300, under30    time.Time
	level1At, incidentUntil, lastPublish time.Time
	lastLag                              float64
	reason                               string
}

func (l *Ladder) now() time.Time {
	if l.Now != nil {
		return l.Now()
	}
	return time.Now()
}

func (l *Ladder) get(tenant string) *tenantLadder {
	if l.tenants == nil {
		l.tenants = map[string]*tenantLadder{}
	}
	t := l.tenants[tenant]
	if t == nil {
		t = &tenantLadder{}
		l.load(tenant, t)
		l.tenants[tenant] = t
	}
	return t
}

func (l *Ladder) load(tenant string, t *tenantLadder) {
	if l.DB == nil {
		return
	}
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()
	var level int
	var reason string
	var l1, until sql.NullTime
	err := l.DB.QueryRowContext(ctx, `SELECT level, reason, level1_at, incident_until FROM evl_load_shed WHERE tenant_id = $1`,
		tenant).Scan(&level, &reason, &l1, &until)
	if err != nil {
		if err != sql.ErrNoRows {
			l.log().Warn("evl.load_shed_load_failed", "tenant", tenant, "err", err)
		}
		return
	}
	t.level, t.reason, t.level1At, t.incidentUntil = level, reason, l1.Time, until.Time
	l.Metrics.Set("evl_shed_level", float64(level), "tenant", tenant)
	if level > 0 {
		l.log().Info("evl.load_shed_resumed", "tenant", tenant, "level", level, "reason", reason)
	}
}

func (l *Ladder) persistLocked(tenant string, t *tenantLadder, now time.Time) {
	if l.DB == nil {
		return
	}
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()
	null := func(x time.Time) any {
		if x.IsZero() {
			return nil
		}
		return x
	}
	if _, err := l.DB.ExecContext(ctx, `INSERT INTO evl_load_shed (tenant_id, level, reason, level1_at, incident_until, changed_at)
	      VALUES ($1, $2, $3, $4, $5, $6)
	      ON CONFLICT (tenant_id) DO UPDATE SET level = EXCLUDED.level, reason = EXCLUDED.reason,
	        level1_at = EXCLUDED.level1_at, incident_until = EXCLUDED.incident_until, changed_at = EXCLUDED.changed_at`,
		tenant, t.level, t.reason, null(t.level1At), null(t.incidentUntil), now); err != nil {
		l.log().Warn("evl.load_shed_persist_failed", "tenant", tenant, "err", err)
	}
}

// Forget drops a tenant this instance no longer owns (consumer.Supervisor
// OnRelease): its gauges stop exporting, and its in-memory ladder goes —
// the next owner resumes from evl_load_shed. Nothing is published: the
// level stands until the new owner changes it.
func (l *Ladder) Forget(tenant string) {
	l.mu.Lock()
	defer l.mu.Unlock()
	delete(l.tenants, tenant)
	for _, g := range []string{"evl_lag_seconds", "evl_scale_out_wanted", "evl_scale_in_ok", "evl_page", "evl_incident", "evl_shed_level"} {
		l.Metrics.Delete(g, "tenant", tenant)
	}
}

func since(mark *time.Time, cond bool, now time.Time) time.Duration {
	if !cond {
		*mark = time.Time{}
		return 0
	}
	if mark.IsZero() {
		*mark = now
	}
	return now.Sub(*mark)
}

// Observe feeds one lag sample (consumer.Supervisor.OnLag).
func (l *Ladder) Observe(tenant string, lagSeconds float64) {
	l.mu.Lock()
	defer l.mu.Unlock()
	now := l.now()
	t := l.get(tenant)
	t.lastLag = lagSeconds
	d60 := since(&t.over60, lagSeconds > 60, now)
	d120 := since(&t.over120, lagSeconds > 120, now)
	d300 := since(&t.over300, lagSeconds > 300, now)
	d30 := since(&t.under30, lagSeconds < 30, now)
	if lagSeconds > 480 {
		l.incidentLocked(tenant, t, "lag_over_480s", now)
	}
	l.Metrics.Set("evl_lag_seconds", lagSeconds, "tenant", tenant)
	l.Metrics.Set("evl_scale_out_wanted", b2f(d60 >= time.Minute), "tenant", tenant)
	l.Metrics.Set("evl_scale_in_ok", b2f(d30 >= 10*time.Minute), "tenant", tenant)
	l.Metrics.Set("evl_page", b2f(d300 >= time.Minute), "tenant", tenant)

	target, reason := 0, ""
	switch {
	case now.Before(t.incidentUntil):
		target, reason = 3, t.reason
	case lagSeconds > 300:
		target, reason = 2, "lag_over_300s"
	case t.level >= 1 && !t.level1At.IsZero() && now.Sub(t.level1At) >= 15*time.Minute && lagSeconds > 120:
		target, reason = 2, "level1_held_15m"
	case d120 >= 5*time.Minute:
		target, reason = 1, "lag_over_120s_5m"
	}
	l.Metrics.Set("evl_incident", b2f(now.Before(t.incidentUntil)), "tenant", tenant)
	switch {
	case target > t.level:
		l.setLocked(tenant, t, target, reason, now)
	case t.level > 0 && d30 >= 10*time.Minute && !now.Before(t.incidentUntil):
		l.setLocked(tenant, t, 0, "recovered_under_30s_10m", now)
	case t.level > 0 && now.Sub(t.lastPublish) >= 30*time.Second:
		l.publishLocked(tenant, t, now)
	}
}

// FundedStale records a funded-account tick_stale suppression (INCIDENT).
func (l *Ladder) FundedStale(tenant string) { l.Incident(tenant, "funded_tick_stale") }

// Incident forces level 3 for ≥ 10 min (funded stale, stream trim, …).
func (l *Ladder) Incident(tenant, reason string) {
	l.mu.Lock()
	defer l.mu.Unlock()
	now := l.now()
	t := l.get(tenant)
	l.incidentLocked(tenant, t, reason, now)
	if t.level < 3 {
		l.setLocked(tenant, t, 3, reason, now)
	}
	l.Metrics.Set("evl_incident", 1, "tenant", tenant)
}

func (l *Ladder) incidentLocked(tenant string, t *tenantLadder, reason string, now time.Time) {
	if !now.Before(t.incidentUntil) {
		l.Metrics.Inc("evl_incidents_total", "tenant", tenant, "reason", reason)
		l.log().Error("evl.incident", "tenant", tenant, "reason", reason, "lag_s", t.lastLag)
	}
	t.incidentUntil = now.Add(10 * time.Minute)
	t.reason = reason
	l.persistLocked(tenant, t, now)
}

// Level returns a tenant's shed level (tests, CON).
func (l *Ladder) Level(tenant string) int {
	l.mu.Lock()
	defer l.mu.Unlock()
	return l.get(tenant).level
}

func (l *Ladder) setLocked(tenant string, t *tenantLadder, level int, reason string, now time.Time) {
	if level == t.level {
		return
	}
	if level >= 1 && t.level == 0 {
		t.level1At = now
	}
	if level == 0 {
		t.level1At = time.Time{}
	}
	prev := t.level
	t.level, t.reason = level, reason
	l.Metrics.Set("evl_shed_level", float64(level), "tenant", tenant)
	l.persistLocked(tenant, t, now)
	if level > prev {
		l.log().Warn("evl.load_shed", "tenant", tenant, "level", level, "from", prev, "reason", reason, "lag_s", t.lastLag)
	} else {
		l.log().Info("evl.load_shed", "tenant", tenant, "level", level, "from", prev, "reason", reason)
	}
	l.publishLocked(tenant, t, now)
}

func (l *Ladder) publishLocked(tenant string, t *tenantLadder, now time.Time) {
	t.lastPublish = now
	if l.Redis == nil {
		return
	}
	msg, _ := json.Marshal(map[string]any{
		"tenant_id": tenant, "level": t.level, "reason": t.reason, "at": now.UnixMilli(),
	})
	ctx, cancel := context.WithTimeout(context.Background(), time.Second)
	defer cancel()
	if err := l.Redis.Publish(ctx, LoadShedChannel, msg).Err(); err != nil {
		l.log().Warn("evl.load_shed_publish_failed", "tenant", tenant, "err", err)
	}
}

func (l *Ladder) log() *slog.Logger {
	if l.Log != nil {
		return l.Log
	}
	return slog.Default()
}

func b2f(b bool) float64 {
	if b {
		return 1
	}
	return 0
}

// TrimReplayer handles a detected trim (D82, docs/63 §4.13): publish
// evl.stream_trimmed, declare the INCIDENT, and replay the trimmed window's
// bridge.tick events from the durable `events` table onto the account
// lanes. consumer_state dedupes anything already processed; ticks older
// than an account's last evaluated tick are rejected 409 by the engine and
// recorded as skipped — Redis is never the source of truth, PG is.
type TrimReplayer struct {
	DB         *sql.DB
	Redis      *redis.Client
	Supervisor *consumer.Supervisor
	Ladder     *Ladder
	Log        *slog.Logger
	// Slack widens the replay window on both sides (stream ids are relay
	// XADD times, occurred_at is bridge time). Default 60 s.
	Slack time.Duration
}

// OnTrim is a consumer.Supervisor.OnTrim callback.
func (r *TrimReplayer) OnTrim(ctx context.Context, st consumer.StreamSpec, lastDelivered, firstRetained string) {
	log := r.Log
	if log == nil {
		log = slog.Default()
	}
	now := time.Now()
	if r.Redis != nil {
		msg, _ := json.Marshal(map[string]any{
			"tenant_id": st.Tenant, "stream": st.Key, "last_delivered": lastDelivered,
			"first_retained": firstRetained, "at": now.UnixMilli(),
		})
		_ = r.Redis.Publish(ctx, "evl.stream_trimmed", msg).Err()
	}
	if r.Ladder != nil {
		r.Ladder.Incident(st.Tenant, "stream_trimmed")
	}
	slack := r.Slack
	if slack == 0 {
		slack = time.Minute
	}
	from := time.UnixMilli(consumer.IDMillis(lastDelivered)).Add(-slack)
	to := time.UnixMilli(consumer.IDMillis(firstRetained)).Add(slack)
	rows, err := r.DB.QueryContext(ctx, `
		SELECT event_id, entity_id, payload FROM events
		 WHERE topic = 'bridge' AND tenant_id = $1 AND type = 'bridge.tick'
		   AND occurred_at >= $2 AND occurred_at <= $3
		 ORDER BY seq`, st.Tenant, from, to)
	if err != nil {
		log.Error("evl.trim_replay_query_failed", "tenant", st.Tenant, "err", err)
		return
	}
	defer rows.Close()
	n := 0
	for rows.Next() {
		var id, entity string
		var payload []byte
		if err := rows.Scan(&id, &entity, &payload); err != nil {
			log.Error("evl.trim_replay_scan_failed", "err", err)
			return
		}
		if r.Supervisor.Inject(st.Key, consumer.Message{EventID: id, EntityID: entity, Payload: payload}) {
			n++
		}
	}
	log.Warn("evl.trim_replayed", "tenant", st.Tenant, "events", n, "from", from, "to", to)
}

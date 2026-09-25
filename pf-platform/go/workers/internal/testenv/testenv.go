// Package testenv provides real Postgres and Redis for integration tests.
//
//	TEST_DATABASE_URL  admin DSN (a database the test may CREATE DATABASE from)
//	TEST_REDIS_URL     redis://…
//
// Tests that need them call PG/Redis, which skip when unset — and FAIL when
// REQUIRE_INTEGRATION=1 (CI), so a misconfigured job cannot pass by skipping.
package testenv

import (
	"crypto/rand"
	"database/sql"
	"encoding/hex"
	"fmt"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"testing"

	_ "github.com/lib/pq"
	"github.com/redis/go-redis/v9"
)

// SchemaFiles are the contracts DDL files the evaluation path needs, in
// apply order. `tenants`/`accounts` stubs stand in for 03/07 (whose DDL
// does not yet apply — see docs/64 §9).
var SchemaFiles = []string{"01-domains.sql", "04-gw-evt.sql", "08-brg.sql", "09-evl.sql"}

func need(t testing.TB, env string) string {
	t.Helper()
	v := os.Getenv(env)
	if v == "" {
		if os.Getenv("REQUIRE_INTEGRATION") == "1" {
			t.Fatalf("%s is required (REQUIRE_INTEGRATION=1)", env)
		}
		t.Skipf("%s not set: skipping integration test", env)
	}
	return v
}

// SchemaDir locates alpha-one/contracts/data/schemas by walking up from
// the working directory.
func SchemaDir(t testing.TB) string {
	t.Helper()
	dir, _ := os.Getwd()
	for i := 0; i < 8; i++ {
		p := filepath.Join(dir, "alpha-one", "contracts", "data", "schemas")
		if st, err := os.Stat(p); err == nil && st.IsDir() {
			return p
		}
		dir = filepath.Dir(dir)
	}
	t.Fatal("cannot locate alpha-one/contracts/data/schemas")
	return ""
}

func randHex(n int) string {
	b := make([]byte, n)
	_, _ = rand.Read(b)
	return hex.EncodeToString(b)
}

// PG creates a fresh database, applies the evaluation-path schema, and
// drops it at cleanup.
func PG(t testing.TB) *sql.DB {
	t.Helper()
	admin := need(t, "TEST_DATABASE_URL")
	adb, err := sql.Open("postgres", admin)
	if err != nil {
		t.Fatal(err)
	}
	name := "wt_" + randHex(6)
	if _, err := adb.Exec("CREATE DATABASE " + name); err != nil {
		t.Fatalf("create database: %v", err)
	}
	dsn, err := withDB(admin, name)
	if err != nil {
		t.Fatal(err)
	}
	db, err := sql.Open("postgres", dsn)
	if err != nil {
		t.Fatal(err)
	}
	db.SetMaxOpenConns(40)
	t.Cleanup(func() {
		db.Close()
		_, _ = adb.Exec("DROP DATABASE IF EXISTS " + name + " WITH (FORCE)")
		adb.Close()
	})
	ApplySchema(t, db)
	return db
}

// ApplySchema applies SchemaFiles (with the tenants/accounts stubs).
func ApplySchema(t testing.TB, db *sql.DB) {
	t.Helper()
	dir := SchemaDir(t)
	for i, f := range SchemaFiles {
		b, err := os.ReadFile(filepath.Join(dir, f))
		if err != nil {
			t.Fatal(err)
		}
		if _, err := db.Exec(string(b)); err != nil {
			t.Fatalf("apply %s: %v", f, err)
		}
		if i == 0 {
			if _, err := db.Exec(`CREATE TABLE tenants (id ULID PRIMARY KEY);
			                      CREATE TABLE accounts (id ULID PRIMARY KEY)`); err != nil {
				t.Fatal(err)
			}
		}
	}
}

func withDB(dsn, name string) (string, error) {
	if strings.HasPrefix(dsn, "postgres://") || strings.HasPrefix(dsn, "postgresql://") {
		u, err := url.Parse(dsn)
		if err != nil {
			return "", err
		}
		u.Path = "/" + name
		return u.String(), nil
	}
	// key=value form
	parts := strings.Fields(dsn)
	out := make([]string, 0, len(parts)+1)
	for _, p := range parts {
		if !strings.HasPrefix(p, "dbname=") {
			out = append(out, p)
		}
	}
	return strings.Join(append(out, "dbname="+name), " "), nil
}

// Redis returns a client on TEST_REDIS_URL.
func Redis(t testing.TB) *redis.Client {
	t.Helper()
	u := need(t, "TEST_REDIS_URL")
	opt, err := redis.ParseURL(u)
	if err != nil {
		t.Fatal(err)
	}
	c := redis.NewClient(opt)
	t.Cleanup(func() { c.Close() })
	return c
}

// ULID returns a random (non-monotonic) valid ULID for test ids.
func ULID() string {
	const a = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
	b := make([]byte, 26)
	r := make([]byte, 26)
	_, _ = rand.Read(r)
	for i := range b {
		b[i] = a[int(r[i])%32]
	}
	b[0] = '0' // keep the timestamp in range
	return string(b)
}

// Must panics on error (test helpers).
func Must[T any](v T, err error) T {
	if err != nil {
		panic(fmt.Sprint(err))
	}
	return v
}

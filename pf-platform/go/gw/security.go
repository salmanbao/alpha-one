package gw

import (
	"context"
	"net"
	"net/http"
)

func remoteIP(remoteAddr string) net.IP {
	if host, _, err := net.SplitHostPort(remoteAddr); err == nil {
		return net.ParseIP(host)
	}
	return net.ParseIP(remoteAddr)
}

// Step 1 — edge handoff & security headers (GW-20/GW-33). CF-Connecting-IP is
// trusted ONLY when the TCP peer address is inside the trusted proxy CIDRs;
// otherwise the socket peer is the client.
func SecurityHeaders(trusted []*net.IPNet, next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		ip := remoteIP(r.RemoteAddr)
		if cf := r.Header.Get("CF-Connecting-IP"); cf != "" {
			if peer := remoteIP(r.RemoteAddr); peer != nil {
				for _, c := range trusted {
					if c.Contains(peer) {
						if parsed := net.ParseIP(cf); parsed != nil {
							ip = parsed
						}
						break
					}
				}
			}
		}
		h := w.Header()
		h.Set("X-Content-Type-Options", "nosniff")
		h.Set("X-Frame-Options", "DENY")
		h.Set("Referrer-Policy", "strict-origin-when-cross-origin")
		h.Set("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
		next.ServeHTTP(w, r.WithContext(WithClientIP(r.Context(), ip)))
	})
}

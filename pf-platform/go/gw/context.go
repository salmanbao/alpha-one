package gw

import (
	"context"
	"net"
)

type ctxKey int

const (
	ctxKeyCorrelation ctxKey = iota
	ctxKeyClientIP
	ctxKeyTenant
	ctxKeyPrincipal
	ctxKeyRoute
)

func WithCorrelation(ctx context.Context, id string) context.Context {
	return context.WithValue(ctx, ctxKeyCorrelation, id)
}

func CorrelationFrom(ctx context.Context) string {
	if v, ok := ctx.Value(ctxKeyCorrelation).(string); ok {
		return v
	}
	return ""
}

func WithClientIP(ctx context.Context, ip net.IP) context.Context {
	return context.WithValue(ctx, ctxKeyClientIP, ip)
}

func ClientIPFrom(ctx context.Context) net.IP {
	if v, ok := ctx.Value(ctxKeyClientIP).(net.IP); ok {
		return v
	}
	return nil
}

func WithTenant(ctx context.Context, id string) context.Context {
	return context.WithValue(ctx, ctxKeyTenant, id)
}

func TenantFrom(ctx context.Context) string {
	if v, ok := ctx.Value(ctxKeyTenant).(string); ok {
		return v
	}
	return ""
}

func WithPrincipal(ctx context.Context, p *Principal) context.Context {
	return context.WithValue(ctx, ctxKeyPrincipal, p)
}

func PrincipalFrom(ctx context.Context) *Principal {
	if v, ok := ctx.Value(ctxKeyPrincipal).(*Principal); ok {
		return v
	}
	return nil
}

func WithRoute(ctx context.Context, rt *Route) context.Context {
	return context.WithValue(ctx, ctxKeyRoute, rt)
}

func RouteFrom(ctx context.Context) *Route {
	if v, ok := ctx.Value(ctxKeyRoute).(*Route); ok {
		return v
	}
	return nil
}

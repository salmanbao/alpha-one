#!/bin/sh
# One-command verification for the reference gateway chain.
# Requires Go >= 1.19. Zero external module dependencies.
set -e
cd "$(dirname "$0")"
go version
go vet ./...
go test ./... -count=1 -race
echo "gw: all checks passed"

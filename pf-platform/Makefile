# pf-platform — prop-firm rules engine + bridge scaffold (doc: ../prop-firm-bridge)
#
# Verification bar (all must be green):
#   make contracts   buf lint + JSON-Schema validation of all rule-pack samples
#   make rust        cargo test --workspace (golden + property tests)
#   make go          go build + vet + test (bridge protocol e2e over httptest+WS)
#   make replay      replay the bundled sample stream through the Rust engine
#   make check       all of the above

RUST ?= cargo
GO   ?= go

.PHONY: all contracts rust go replay check fmt

all: check

contracts:
	node scripts/check-contracts.js

rust:
	cd rust && $(RUST) test --workspace

go:
	cd go && $(GO) build -o /tmp/pf-bridge ./bridge && $(GO) vet ./... && $(GO) test ./...

replay:
	cd rust && $(RUST) run -q -p replay-tool -- \
		--pack ../contracts/samples/challenge_100k.json \
		--events ../examples/sample-events.jsonl

check: contracts rust go replay
	@echo "ALL CHECKS GREEN"

fmt:
	cd rust && $(RUST) fmt
	cd go && $(GO) fmt ./...

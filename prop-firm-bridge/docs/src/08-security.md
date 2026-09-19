## 8. Security Architecture

### 8.1 Threat model (STRIDE, condensed to what matters here)

| # | Threat | Actor | Mitigations |
|---|---|---|---|
| T1 | Spoofed terminal / fake telemetry | malicious trader | HMAC-signed envelopes, per-account pairing keys, deal-id cross-checks vs broker history, device fingerprint, broker-side truth via reconciliation |
| T2 | Patched EA reporting falsified PnL | malicious trader | bridge **recomputes** PnL from stored entries + broker prices; broker `HistorySelect` audit is independent of the EA; impossible-value detectors (e.g., slippage > symbol max, fill outside quote band from last N ticks) |
| T3 | Replay of recorded session | attacker with captured traffic | per-session ephemeral keys (24 h), nonce + 30 s window, monotonic seq, TLS 1.3 (optionally cert-pinned in EA) |
| T4 | Tenant cross-access (A reads B) | insider, bug | RLS + repo-layer tenant enforcement, tenant-bound keys, cross-tenant integration test suite, per-tenant consumer groups, secret-scan CI on queries |
| T5 | Insider fraud (staff approves own payout, edits rules) | insider | 4-eyes approval above thresholds, immutable rule-pack versions with approval workflow, hash-chained audit (see 8.6), Segregation of Duties in RBAC (maker/checker roles), PII access logging |
| T6 | Broker credential leak | external | Vault with dynamic short-TTL credentials where broker supports; per-tenant encryption envelopes; credentials never leave the platform except to broker; egress allow-listing |
| T7 | DDoS / connection flood on WS fleet | external | WAF + rate limits per IP/account/tenant, connection caps per account (anti account-farming), SYN flood protection at LB, autoscale headroom 3× peak |
| T8 | Supply chain (malicious EA build, dependency) | external | EA builds signed + published via portal only (hash pinned in pairing record), dependency SBOM + provenance, image signing (cosign) + admission policy |
| T9 | Mass account manipulation (1 human, 50 evaluations) | fraud ring | device/IP/payment fingerprint graph, per-identity limits, challenge-velocity caps, ML scoring (Section 15 fraud diagram), manual review console |
| T10 | Data exfiltration / privacy | external, regulatory | field-level encryption for PII, DLP egress rules, GDPR-style rights APIs (tenant obligations, platform tooling), data residency per tenant contract |

### 8.2 Cryptographic design

- **Pairing key**: 256-bit, generated server-side (HSM-backed RNG), shown once, stored hashed (Argon2id) in PG + wrapped in Vault for ops recovery; signs `hello` only.
- **Session key**: 256-bit, fresh per session (in Redis, TTL = key lifetime 24 h), signs every message. Canonicalization: RFC 8785 (JCS) for JSON-v1; protobuf wire bytes for v2.
- **HMAC**: HMAC-SHA256. (Ed25519 per-account keys are the v2 upgrade path — cheaper verification at 1M msg/s; keep the envelope field layout compatible.)
- **Internal service mTLS** (SPIFFE-style identities), **Vault** for all secrets, **KMS envelope encryption** at rest (PG, S3), TLS 1.3 everywhere, HSTS + certificate transparency monitoring.
- **Clock**: all signing windows enforced against NTP (Section 5.6) — weak clock discipline is the #1 real-world replay hole.

### 8.3 Authentication & authorization

- **Traders** (portal): email+password → MFA (TOTP, A2P push) → OIDC IdP; short JWT (15 min) + rotating refresh; session risk re-scored on device/IP change.
- **Terminals**: no human login — pairing-key bootstrap (§5.5) is the authenticator; terminal identity = `(account, pairing_id, device_fingerprint)`.
- **Tenants/back-office**: OIDC SSO (tenant IdP), **RBAC** with granular roles (owner, risk_officer, support, payout_approver, read_only), per-role resource scopes, **approval workflows** (payouts, rule-pack changes, manual corrections, terminations) — maker/checker enforced in the workflow engine, not the UI.
- **API**: service-to-service mTLS + scoped tokens; public APIs (webhooks from broker/payment providers) use signed webhooks (HMAC with per-provider keys) + replay window + IP allow-lists where possible.

### 8.4 Network & platform

Kubernetes: NetworkPolicy default-deny (only declared flows), pod identity, secrets via CSI (no env vars), per-tenant namespaces *only* if contractual (default: shared plane + RLS + queue isolation), egress allow-list from bridge nodes (broker domains, Vault, NTP only — an EA's traffic egresses via the LB, not the pod).

### 8.5 Device & identity graph (the fraud backbone)

Fingerprint collected at pairing: terminal build, MT/cTrader account id, IP + ASN, timezone, payment instrument hash (PCI-safe token from the PSP), browser fingerprint on portal, optional hardware attestation on mobile portal. These become nodes in a **graph** (`identity_links`) maintained by the risk service: same payment hash across 3 accounts in 30 days → automatic review queue. The graph is the single most ROI-per-effort fraud control in this industry and it's *data plumbing on top of the event stream*, not a separate system.

The full detection pipeline, from raw stream features to risk-desk actions:

{{DIAG:15-fraud-detection}}

### 8.6 Audit: hash-chained, exportable, dispute-ready

`audit_log` rows are chained: `row_n.hash = H(row_n.data || row_{n−1}.hash)`, with daily root hashes published to object storage (GPG-signed manifests). Properties:

- any row tamper is detectable by re-hashing from the last published root;
- dispute pack generator: given `(account, date_range)` → produces a signed, human-readable PDF/JSON bundle: every event, every verdict with its exact inputs, every reconciliation result, every control command, every admin action — this artifact *is* the firm's defense in chargeback/regulatory scenarios;
- retention: hot 365 d (Kafka → ClickHouse), warm 7 y in object storage (configurable per tenant jurisdiction).

### 8.7 Compliance posture (do this with lawyers, not just engineers)

- **KYB** on tenants (you), **KYC/AML** on traders (tenant's legal duty, platform provides tooling: document storage, sanctions screening via provider API, PEP checks, source-of-funds questions) — the bridge's evidence packs are the AML *travel rule* artifact for funded accounts.
- **Jurisdictional risk of the product itself**: several regulators treat prop-firm challenges as gaming/financial services depending on structure (fee structure, payout mechanics, entity location). The PFaaS must support tenant-specific terms, entity routing, and jurisdictional feature flags (e.g., some tenants must disable certain payout schedules). *Get this settled with counsel per market before launch — it changes data residency, marketing claims, and payout flow.*
- Data: GDPR (EU traders) as baseline, PK/EU/UK resident options for data regions, DPIA per processing purpose, DPA templates for tenants, sub-processor register (brokers, PSPs, calendar providers).

---

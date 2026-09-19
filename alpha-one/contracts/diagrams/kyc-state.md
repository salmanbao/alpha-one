# kyc-state — render to PDF/PNG

The KYC-06 state machine. States are exactly those named by KYC-06. Edge conditions marked TODO are not enumerated in the sheet.

```mermaid
stateDiagram-v2
    [*] --> NOT_STARTED
    NOT_STARTED --> PENDING: session created (KYC-01)
    PENDING --> IN_REVIEW: webhook status update (KYC-05)
    IN_REVIEW --> APPROVED: provider approves (KYC-05)
    IN_REVIEW --> REJECTED: provider rejects (KYC-05)
    IN_REVIEW --> NEEDS_RESUBMISSION: provider requests resubmission
    NEEDS_RESUBMISSION --> PENDING: trader resubmits
    PENDING --> EXPIRED: TODO — needs owner decision (V1 expiry trigger undefined)
    APPROVED --> EXPIRED: TODO — needs owner decision (document-expiry triggers are P2 per Out Of Scope)
    REJECTED --> PENDING: manual resubmission path — TODO — needs owner decision
    APPROVED --> [*]: gates open (KYC-07 funding, KYC-08 payout)
```

Manual fallback (V1.1): trader uploads documents (KYC-12); tenant admin reviews and decides (KYC-11) — decisions land in the same state machine. Under-18 rejected (KYC-14). Verified identity stored on approval (KYC-09).

## Open contract questions
- TODO — needs owner decision: V1 expiry trigger and REJECTED → retry path.
- TODO — needs owner decision: which state manual-review cases enter (does manual review bypass PENDING/IN_REVIEW?).

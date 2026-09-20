# purchase-flow — render to PNG

Purchase flow: checkout → payment webhook → order → provisioning. Derives from CHK-01, CHK-02, CHK-04, CHK-06, CHK-07, CHK-08, CHK-09, CHK-43, CHK-44, LCC-05, BRG-05, BRG-06, LED-04.

```mermaid
sequenceDiagram
    participant T as Trader (TD-09)
    participant CHK as Checkout (CHK)
    participant PP as Payment provider (CHK-04)
    participant LCC as Lifecycle (LCC)
    participant BRG as Bridge (BRG)
    participant LED as Ledger (LED)
    participant EVT as Outbox/Relay (EVT-01, EVT-02)
    participant ANA as Analytics (ANA-01)
    participant WK as Expiry worker (CHK-43)

    T->>CHK: browse catalog (CHK-01)
    T->>CHK: POST checkout session (CHK-02, price+coupon reserved, idempotent per GW-12/CHK-42)
    CHK-->>T: session + payment_url (hosted flow CHK-06)
    opt session abandoned (CHK-43/CHK-44 — Decision 7)
        T->>CHK: DELETE /v1/checkout/sessions/{id} — trader cancel (CHK-44, identity-scoped, no permission key)
        CHK->>CHK: release coupon + price holds, mark cancelled (CHK-44)
        WK->>CHK: expire abandoned sessions after reservation window (CHK-43)
        CHK->>EVT: emit checkout.session.expired (CHK-43, outbox EVT-01)
        CHK->>ANA: checkout.session.expired consumed — funnel/abandonment read model (ANA-01)
    end
    T->>PP: complete payment on hosted page (CHK-06)
    PP->>CHK: webhook (CHK-07, signature verified EVT-10, dedupe by provider event id)
    CHK->>CHK: transition payment state (CHK-07)
    CHK->>CHK: create order (CHK-08: type, amount, method, coupon, IP, UTM)
    CHK->>EVT: emit order.paid (CHK-09, outbox EVT-01)
    CHK->>LED: order.paid consumed — post customer payment + settlement receivable (LED-04)
    CHK->>LCC: order.paid consumed — provisioning (LCC-05)
    LCC->>BRG: create phase 1 account (BRG-05, idempotency key)
    BRG-->>LCC: account created
    LCC->>LCC: AccountCreated via outbox (LCC-23)
    LCC->>T: credentials delivered via portal + email (BRG-06, NOT-03)
```

## Confirmed by citation (resolved 2026-09-20, gap-closure pass — docs/12, docs/32)
- **Webhook tenant routing** — the webhook route is per-provider, not per-tenant: `POST /v1/webhooks/{provider}` (docs/12 §2/§3.2; signature verified by EVT-10). The provider payload carries the provider-side transaction reference, which maps to `payment_intents` via the `(provider, provider_ref)` index (`idx_pint_provider_ref`, docs/32 §12) — the intent row's `tenant_id` is the routing key for everything downstream, and the resolved tenant is stamped onto `provider_events` (docs/32 §4) for idempotency and audit. There is no tenant in the URL and no per-tenant webhook endpoint in V1.
- **Failed-payment retry branch** — it is *not* a separate flow placement: the intent state machine (docs/12 §3.2) carries it — `pending ──webhook failed──► failed`, and a retry is **a new payment intent on the same order** (fresh `idempotency_key`, same `order_id`); the order stays `open` until any intent is captured. V1.1's CHK-16 formalizes the retry surface; in V1.0 the trader simply re-initiates from the order. Non-recoverable states (e.g. order already paid) → `order.not_retryable` (409).

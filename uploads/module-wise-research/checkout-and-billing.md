# Comprehensive Research: Enterprise-Grade Checkout & Billing for a Prop Firm as a Service Platform

## Table of Contents

1. [Industry Context & Requirements](#1-industry-context--requirements)
2. [Architecture Overview](#2-architecture-overview)
3. [Core Components Deep Dive](#3-core-components-deep-dive)
4. [Open Source Solutions Landscape](#4-open-source-solutions-landscape)
5. [Recommended Architecture Stack](#5-recommended-architecture-stack)
6. [Implementation Blueprint](#6-implementation-blueprint)
7. [Compliance & Security](#7-compliance--security)
8. [Comparison Matrix](#8-comparison-matrix)

---

## 1. Industry Context & Requirements

### What Makes Prop Firm Billing Unique

A **Prop Firm as a Service (PFaaS)** platform has billing complexities that go far beyond a typical SaaS subscription:

```
┌─────────────────────────────────────────────────────────────────┐
│                  PROP FIRM BILLING COMPLEXITY                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. MULTI-PARTY TRANSACTIONS                                     │
│     ├── Trader pays for Challenge/Evaluation                     │
│     ├── White-label firm takes a cut                             │
│     ├── Platform (PFaaS) takes a cut                            │
│     └── Affiliate/IB gets commission                            │
│                                                                  │
│  2. COMPLEX PRODUCT CATALOG                                      │
│     ├── Challenge Phases (1-step, 2-step, 3-step)               │
│     ├── Account sizes ($10K, $25K, $50K, $100K, $200K, $500K)  │
│     ├── Add-ons (extra leverage, weekend holding, news trading) │
│     ├── Retry/Reset fees                                        │
│     ├── Funded account scaling plans                            │
│     └── Recurring profit-split payouts                          │
│                                                                  │
│  3. LIFECYCLE-BASED BILLING                                      │
│     ├── One-time challenge purchase                             │
│     ├── Monthly subscription (for some models)                  │
│     ├── Performance-based profit splits                         │
│     ├── Refundable fees on passing                              │
│     └── Retry discounts and promo codes                         │
│                                                                  │
│  4. GLOBAL REQUIREMENTS                                          │
│     ├── Multi-currency (USD, EUR, GBP, crypto)                  │
│     ├── Multi-payment-method (cards, crypto, local methods)     │
│     ├── Tax compliance (VAT, GST, sales tax)                    │
│     ├── KYC/AML integration                                     │
│     └── Chargeback & fraud management                           │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Functional Requirements Matrix

| Category | Requirement | Priority | Complexity |
|----------|------------|----------|------------|
| **Checkout** | Multi-step checkout flow | P0 | Medium |
| **Checkout** | Embeddable checkout (white-label) | P0 | High |
| **Checkout** | Promo codes / Coupons | P0 | Low |
| **Checkout** | Affiliate tracking at checkout | P0 | Medium |
| **Checkout** | Crypto payments (USDT, BTC, ETH) | P0 | High |
| **Checkout** | Local payment methods (PIX, UPI, etc.) | P1 | Medium |
| **Checkout** | 3D Secure / SCA compliance | P0 | Medium |
| **Billing** | One-time payments | P0 | Low |
| **Billing** | Recurring subscriptions | P1 | Medium |
| **Billing** | Usage-based billing (API calls per firm) | P1 | High |
| **Billing** | Multi-currency pricing | P0 | Medium |
| **Billing** | Revenue splitting (platform ↔ firm) | P0 | High |
| **Billing** | Profit-split payout management | P0 | High |
| **Billing** | Invoice generation | P0 | Medium |
| **Billing** | Tax calculation (VAT/GST) | P0 | High |
| **Billing** | Credit/wallet system | P1 | Medium |
| **Billing** | Refund management | P0 | Medium |
| **Platform** | White-label billing pages | P0 | High |
| **Platform** | Multi-tenant billing isolation | P0 | High |
| **Platform** | Billing analytics & reporting | P0 | Medium |
| **Platform** | Webhook-driven architecture | P0 | Medium |
| **Platform** | Chargeback management | P0 | High |

---

## 2. Architecture Overview

### High-Level System Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         PROP FIRM AS A SERVICE PLATFORM                   │
│                                                                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌──────────────┐  │
│  │  Firm A      │  │  Firm B      │  │  Firm C      │  │  Firm N       │  │
│  │  (Tenant)    │  │  (Tenant)    │  │  (Tenant)    │  │  (Tenant)     │  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬────────┘  │
│         │                 │                 │                  │           │
│  ┌──────▼─────────────────▼─────────────────▼──────────────────▼────────┐ │
│  │                    API GATEWAY / ROUTING LAYER                        │ │
│  │              (Tenant Resolution, Auth, Rate Limiting)                 │ │
│  └──────────────────────────┬───────────────────────────────────────────┘ │
│                             │                                             │
│  ┌──────────────────────────▼───────────────────────────────────────────┐ │
│  │                     CHECKOUT & BILLING ENGINE                        │ │
│  │                                                                      │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │ │
│  │  │  Product      │  │  Pricing     │  │  Cart &      │              │ │
│  │  │  Catalog      │  │  Engine      │  │  Checkout    │              │ │
│  │  │  Service      │  │              │  │  Service     │              │ │
│  │  └──────┬────────┘  └──────┬───────┘  └──────┬───────┘              │ │
│  │         │                  │                  │                       │ │
│  │  ┌──────▼──────────────────▼──────────────────▼───────────────────┐  │ │
│  │  │                   ORDER MANAGEMENT SERVICE                      │  │ │
│  │  └──────────────────────────┬─────────────────────────────────────┘  │ │
│  │                             │                                        │ │
│  │  ┌──────────────┐  ┌───────▼──────┐  ┌──────────────┐              │ │
│  │  │  Payment      │  │  Billing &   │  │  Revenue     │              │ │
│  │  │  Processing   │  │  Invoicing   │  │  Sharing &   │              │ │
│  │  │  Orchestrator │  │  Engine      │  │  Splits      │              │ │
│  │  └──────┬────────┘  └──────┬───────┘  └──────┬───────┘              │ │
│  │         │                  │                  │                       │ │
│  │  ┌──────▼──────────────────▼──────────────────▼───────────────────┐  │ │
│  │  │              FINANCIAL LEDGER / ACCOUNTING CORE                  │  │ │
│  │  └────────────────────────────────────────────────────────────────┘  │ │
│  │                                                                      │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │ │
│  │  │  Tax          │  │  Payout      │  │  Fraud &     │              │ │
│  │  │  Engine       │  │  Management  │  │  Chargeback  │              │ │
│  │  │              │  │              │  │  Management  │              │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘              │ │
│  │                                                                      │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────────┐ │
│  │                    EXTERNAL INTEGRATIONS                              │ │
│  │                                                                      │ │
│  │  ┌─────────┐ ┌─────────┐ ┌──────────┐ ┌──────────┐ ┌────────────┐ │ │
│  │  │ Stripe  │ │ PayPal  │ │CoinPaymts│ │ Wise/    │ │ Accounting │ │ │
│  │  │         │ │         │ │/NOWPaymts│ │ Banking  │ │ (Xero/QB)  │ │ │
│  │  └─────────┘ └─────────┘ └──────────┘ └──────────┘ └────────────┘ │ │
│  │                                                                      │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────┘
```

### Data Flow: Trader Purchases a Challenge

```
┌─────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│  Trader  │────▶│ Checkout │────▶│  Order   │────▶│ Payment  │
│  (User)  │     │   Page   │     │ Created  │     │Processing│
└─────────┘     └──────────┘     └──────────┘     └────┬─────┘
                                                        │
                    ┌───────────────────────────────────┘
                    │
              ┌─────▼─────┐
              │  Payment   │
              │  Success?  │
              └─────┬──────┘
                    │
           ┌───────┴───────┐
           │               │
     ┌─────▼─────┐   ┌────▼──────┐
     │  SUCCESS   │   │  FAILED   │
     └─────┬─────┘   └────┬──────┘
           │               │
     ┌─────▼──────────┐   │    ┌─────────────┐
     │ Order Confirmed │   └───▶│ Retry /     │
     └─────┬──────────┘        │ Abandon Cart│
           │                    └─────────────┘
           │
     ┌─────▼──────────────────────────────────┐
     │         PARALLEL PROCESSING             │
     │                                         │
     │  ┌───────────────┐  ┌────────────────┐ │
     │  │ Generate      │  │ Revenue Split  │ │
     │  │ Invoice       │  │ Calculation    │ │
     │  └───────────────┘  └────────────────┘ │
     │                                         │
     │  ┌───────────────┐  ┌────────────────┐ │
     │  │ Provision     │  │ Affiliate      │ │
     │  │ Trading Acct  │  │ Commission     │ │
     │  └───────────────┘  └────────────────┘ │
     │                                         │
     │  ┌───────────────┐  ┌────────────────┐ │
     │  │ Send Receipt  │  │ Update         │ │
     │  │ Email         │  │ Analytics      │ │
     │  └───────────────┘  └────────────────┘ │
     │                                         │
     └─────────────────────────────────────────┘
```

---

## 3. Core Components Deep Dive

### 3.1 Product Catalog Service

```
┌─────────────────────────────────────────────────────────────┐
│                    PRODUCT CATALOG MODEL                     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Product Family: "Challenge Programs"                        │
│  │                                                           │
│  ├── Product: "2-Step Challenge"                             │
│  │   ├── Variant: $10K Account  → $99                       │
│  │   ├── Variant: $25K Account  → $199                      │
│  │   ├── Variant: $50K Account  → $299                      │
│  │   ├── Variant: $100K Account → $499                      │
│  │   └── Variant: $200K Account → $899                      │
│  │                                                           │
│  ├── Product: "1-Step Evaluation"                            │
│  │   ├── Variant: $25K Account  → $249                      │
│  │   └── Variant: $100K Account → $599                      │
│  │                                                           │
│  ├── Product: "Instant Funded"                               │
│  │   └── Variant: $10K Account  → $399                      │
│  │                                                           │
│  ├── Add-ons:                                                │
│  │   ├── "Weekend Holding"     → +$29                       │
│  │   ├── "News Trading"       → +$49                        │
│  │   ├── "Extra Leverage 1:200"→ +$79                       │
│  │   └── "Bi-weekly Payout"   → +$19                        │
│  │                                                           │
│  └── Services:                                               │
│      ├── "Challenge Reset"    → $49 (one-time)              │
│      ├── "Free Retry"         → $0 (conditional)            │
│      └── "Account Scaling"    → $0 (performance-based)      │
│                                                              │
│  TENANT OVERRIDE:                                            │
│  Each white-label firm can:                                  │
│  ├── Enable/disable products                                │
│  ├── Override pricing                                       │
│  ├── Add custom products                                    │
│  ├── Set custom currencies                                  │
│  └── Configure custom add-on bundles                        │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 Pricing Engine

```python
# Conceptual Pricing Engine Logic

class PricingEngine:
    """
    Multi-layered pricing with tenant overrides,
    promotions, and dynamic adjustments.
    """
    
    def calculate_price(self, context: PricingContext) -> PricingResult:
        # Layer 1: Base price from catalog
        base_price = self.get_base_price(context.product_variant)
        
        # Layer 2: Tenant override
        tenant_price = self.apply_tenant_override(
            base_price, context.tenant_id
        )
        
        # Layer 3: Currency conversion
        localized_price = self.convert_currency(
            tenant_price, context.target_currency
        )
        
        # Layer 4: Add-on pricing
        addon_total = self.calculate_addons(context.addons)
        
        # Layer 5: Promotional discounts
        discount = self.apply_promotions(
            localized_price + addon_total,
            context.promo_code,
            context.affiliate_code,
            context.customer_history
        )
        
        # Layer 6: Tax calculation
        tax = self.calculate_tax(
            localized_price + addon_total - discount,
            context.customer_country,
            context.tenant_tax_config
        )
        
        # Layer 7: Revenue split calculation
        splits = self.calculate_revenue_splits(
            net_amount=localized_price + addon_total - discount,
            tenant_id=context.tenant_id,
            affiliate_id=context.affiliate_id
        )
        
        return PricingResult(
            subtotal=localized_price + addon_total,
            discount=discount,
            tax=tax,
            total=localized_price + addon_total - discount + tax,
            currency=context.target_currency,
            revenue_splits=splits,
            line_items=[...],
            pricing_breakdown=[...]
        )
```

### 3.3 Revenue Splitting Model

```
┌─────────────────────────────────────────────────────────────────┐
│                    REVENUE SPLIT ARCHITECTURE                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Trader pays $499 for 100K Challenge                            │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    GROSS AMOUNT: $499                      │   │
│  └──────────────────────────────┬───────────────────────────┘   │
│                                 │                                │
│  ┌──────────────────────────────▼───────────────────────────┐   │
│  │  Payment Processing Fee (Stripe ~2.9% + $0.30)           │   │
│  │  = -$14.77                                                │   │
│  │  NET AMOUNT: $484.23                                      │   │
│  └──────────────────────────────┬───────────────────────────┘   │
│                                 │                                │
│  ┌──────────────────────────────▼───────────────────────────┐   │
│  │                    SPLIT CALCULATION                       │   │
│  │                                                           │   │
│  │  ┌─────────────────────┐                                  │   │
│  │  │ Platform Fee: 20%   │ = $96.85  → PFaaS Platform      │   │
│  │  └─────────────────────┘                                  │   │
│  │  ┌─────────────────────┐                                  │   │
│  │  │ Firm Revenue: 70%   │ = $338.96 → White-label Firm     │   │
│  │  └─────────────────────┘                                  │   │
│  │  ┌─────────────────────┐                                  │   │
│  │  │ Affiliate: 10%      │ = $48.42  → Referring Affiliate  │   │
│  │  └─────────────────────┘                                  │   │
│  │                                                           │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  PROFIT SPLIT PAYOUT (Later):                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Trader earns $5,000 profit on funded account             │   │
│  │                                                           │   │
│  │  ├── Trader gets 80% = $4,000 (payout to trader)         │   │
│  │  └── Firm keeps 20% = $1,000                             │   │
│  │      ├── Platform fee on profit: 15% = $150              │   │
│  │      └── Firm net: $850                                   │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 3.4 Payment Processing Orchestration

```
┌─────────────────────────────────────────────────────────────────┐
│              PAYMENT ORCHESTRATION LAYER                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                 PAYMENT METHOD ROUTER                      │   │
│  │                                                           │   │
│  │  Input: Payment Intent + Customer Context                 │   │
│  │                                                           │   │
│  │  ┌─────────────┐   ┌──────────────┐                      │   │
│  │  │ Card (Visa,  │   │  Smart       │                      │   │
│  │  │ MC, Amex)   │──▶│  Routing     │                      │   │
│  │  └─────────────┘   │  Engine      │                      │   │
│  │  ┌─────────────┐   │              │                      │   │
│  │  │ Crypto      │──▶│  Considers:  │                      │   │
│  │  │ (USDT, BTC) │   │  - Cost      │                      │   │
│  │  └─────────────┘   │  - Success   │                      │   │
│  │  ┌─────────────┐   │    rate      │                      │   │
│  │  │ Bank Xfer   │──▶│  - Currency  │                      │   │
│  │  │ (SEPA, Wire)│   │  - Region    │                      │   │
│  │  └─────────────┘   │  - Amount    │                      │   │
│  │  ┌─────────────┐   │  - Fraud     │                      │   │
│  │  │ Local       │──▶│    score     │                      │   │
│  │  │ (PIX, UPI)  │   │              │                      │   │
│  │  └─────────────┘   └──────┬───────┘                      │   │
│  │                           │                               │   │
│  └───────────────────────────┼───────────────────────────────┘   │
│                              │                                    │
│  ┌───────────────────────────▼───────────────────────────────┐   │
│  │              PAYMENT SERVICE PROVIDERS                      │   │
│  │                                                            │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐│   │
│  │  │ Stripe   │ │ Checkout │ │ NOWPay-  │ │ Paystack     ││   │
│  │  │ Connect  │ │ .com     │ │ ments    │ │ (Africa)     ││   │
│  │  │          │ │          │ │ (Crypto) │ │              ││   │
│  │  │ Primary  │ │ Fallback │ │ Crypto   │ │ Regional     ││   │
│  │  │ for cards│ │ for cards│ │ primary  │ │              ││   │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────────┘│   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐│   │
│  │  │ Adyen    │ │ Wise     │ │ PayPal   │ │ Razorpay     ││   │
│  │  │(Enterpr.)│ │ (Payouts)│ │          │ │ (India)      ││   │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────────┘│   │
│  │                                                            │   │
│  └────────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. Open Source Solutions Landscape

### 4.1 Comprehensive Open Source Billing Platforms

#### **A. Kill Bill** ⭐⭐⭐⭐⭐
```
┌─────────────────────────────────────────────────────────────────┐
│  KILL BILL - Open Source Billing & Payments Platform             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  License: Apache 2.0                                             │
│  Language: Java                                                  │
│  GitHub: github.com/killbill/killbill                           │
│  Stars: ~4.5K                                                    │
│  Maturity: Very High (Used by enterprises)                      │
│                                                                  │
│  WHAT IT PROVIDES:                                               │
│  ✅ Subscription management                                     │
│  ✅ One-time payments                                            │
│  ✅ Invoice generation                                          │
│  ✅ Payment processing (plugin-based)                           │
│  ✅ Multi-tenancy (built-in!)                                   │
│  ✅ Account management                                          │
│  ✅ Catalog/pricing management                                  │
│  ✅ Dunning (failed payment retry)                              │
│  ✅ Revenue recognition                                         │
│  ✅ Audit logs                                                  │
│  ✅ Plugin architecture (Stripe, PayPal, Adyen plugins exist)  │
│  ✅ REST API                                                    │
│  ✅ Analytics/reporting                                         │
│  ✅ Overdue handling                                            │
│                                                                  │
│  WHAT YOU'D NEED TO BUILD:                                       │
│  ❌ Prop-firm specific checkout UI                              │
│  ❌ Crypto payment plugin                                       │
│  ❌ Revenue splitting logic                                     │
│  ❌ Affiliate commission tracking                               │
│  ❌ Profit-split payout workflows                               │
│  ❌ White-label theming                                         │
│                                                                  │
│  RELEVANCE TO PROP FIRM: 8/10                                   │
│  - Multi-tenancy is perfect for white-label model               │
│  - Plugin system allows adding crypto payments                  │
│  - Catalog system handles complex product variants              │
│  - Handles the hardest parts: invoicing, dunning, ledger        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

#### **B. Lago** ⭐⭐⭐⭐⭐
```
┌─────────────────────────────────────────────────────────────────┐
│  LAGO - Open Source Metering & Usage-Based Billing              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  License: AGPLv3 (with commercial license available)            │
│  Language: Ruby on Rails + TypeScript                           │
│  GitHub: github.com/getlago/lago                               │
│  Stars: ~8K+                                                    │
│  Maturity: High (Well-funded startup, active development)       │
│                                                                  │
│  WHAT IT PROVIDES:                                               │
│  ✅ Usage-based billing                                         │
│  ✅ Subscription management                                     │
│  ✅ One-time charges (perfect for challenge purchases!)        │
│  ✅ Coupons & discounts                                        │
│  ✅ Invoice generation (PDF)                                   │
│  ✅ Multi-currency                                              │
│  ✅ Prepaid credits / wallet system                             │
│  ✅ Tax management                                              │
│  ✅ Webhook events                                              │
│  ✅ REST & GraphQL API                                          │
│  ✅ Beautiful admin UI                                          │
│  ✅ Stripe, GoCardless, Adyen integrations                     │
│  ✅ Customer portal                                             │
│  ✅ Add-on management                                           │
│                                                                  │
│  WHAT YOU'D NEED TO BUILD:                                       │
│  ❌ Multi-tenancy (would need to architect)                     │
│  ❌ Revenue splitting                                           │
│  ❌ Crypto payments                                             │
│  ❌ Affiliate tracking                                          │
│  ❌ White-label checkout                                        │
│  ❌ Payout management                                           │
│                                                                  │
│  RELEVANCE TO PROP FIRM: 8/10                                   │
│  - Wallet/credit system useful for retry credits                │
│  - Add-on system maps perfectly to challenge add-ons            │
│  - Modern tech stack, easier to customize                       │
│  - Self-hostable, API-first                                     │
│                                                                  │
│  NOTE: AGPLv3 requires derivative works to be open-sourced      │
│        unless you purchase commercial license                    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

#### **C. Hyperswitch** ⭐⭐⭐⭐⭐
```
┌─────────────────────────────────────────────────────────────────┐
│  HYPERSWITCH - Open Source Payment Switch / Orchestrator         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  License: Apache 2.0                                             │
│  Language: Rust                                                  │
│  GitHub: github.com/juspay/hyperswitch                          │
│  Stars: ~13K+                                                   │
│  Maturity: High (Backed by Juspay, processes billions)          │
│                                                                  │
│  WHAT IT PROVIDES:                                               │
│  ✅ Payment orchestration (route between PSPs)                  │
│  ✅ 50+ payment processor integrations                         │
│  ✅ Smart routing (cost, success rate, latency)                │
│  ✅ Automatic retries & failover                               │
│  ✅ 3DS authentication                                         │
│  ✅ Tokenization & vault                                       │
│  ✅ Refund management                                          │
│  ✅ Dispute/chargeback management                              │
│  ✅ Multi-currency                                              │
│  ✅ Webhook management                                         │
│  ✅ Analytics dashboard                                        │
│  ✅ PCI DSS compliant architecture                             │
│  ✅ Mandate management (recurring)                             │
│  ✅ Unified API for all processors                             │
│                                                                  │
│  WHAT IT DOESN'T DO:                                            │
│  ❌ Billing/invoicing (it's payment processing only)           │
│  ❌ Subscription management                                    │
│  ❌ Product catalog                                             │
│  ❌ Tax calculation                                             │
│  ❌ Revenue splitting                                           │
│                                                                  │
│  RELEVANCE TO PROP FIRM: 9/10                                   │
│  - CRITICAL for prop firms (high chargeback industry)           │
│  - Smart routing reduces payment failures                       │
│  - Fallback between processors when one blocks prop firms       │
│  - Reduces PSP vendor lock-in                                   │
│  - Built in Rust = extremely high performance                   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

#### **D. Lotus (now Uselotus)** ⭐⭐⭐⭐
```
┌─────────────────────────────────────────────────────────────────┐
│  LOTUS - Open Source Pricing & Billing Engine                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  License: MIT (mostly) / Elastic License 2.0                    │
│  Language: Python (Django) + TypeScript (React)                 │
│  GitHub: github.com/uselotus/lotus                              │
│  Stars: ~1.8K                                                   │
│                                                                  │
│  WHAT IT PROVIDES:                                               │
│  ✅ Complex pricing models                                      │
│  ✅ Plan management                                             │
│  ✅ Usage tracking & metering                                   │
│  ✅ Invoice generation                                          │
│  ✅ Multi-currency                                              │
│  ✅ Customer management                                        │
│  ✅ Stripe integration                                          │
│  ✅ Webhook events                                              │
│  ✅ Price experimentation (A/B testing pricing)                │
│  ✅ Backtest pricing changes                                    │
│                                                                  │
│  RELEVANCE TO PROP FIRM: 6/10                                   │
│  - Price experimentation useful for optimizing challenge prices │
│  - Less mature than Kill Bill or Lago                           │
│  - Good pricing engine but limited billing features             │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 Open Source Checkout Solutions

#### **E. Saleor Commerce** ⭐⭐⭐⭐
```
┌─────────────────────────────────────────────────────────────────┐
│  SALEOR - Open Source Headless Commerce                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  License: BSD-3-Clause                                           │
│  Language: Python (Django) + GraphQL                            │
│  GitHub: github.com/saleor/saleor                               │
│  Stars: ~20K+                                                   │
│                                                                  │
│  WHAT IT PROVIDES:                                               │
│  ✅ Complete checkout flow                                      │
│  ✅ Product catalog with variants                               │
│  ✅ Cart management                                             │
│  ✅ Discount/voucher system                                    │
│  ✅ Multi-currency & multi-channel                              │
│  ✅ Tax integrations (Avalara, TaxJar)                         │
│  ✅ Payment gateway plugins                                    │
│  ✅ Order management                                           │
│  ✅ GraphQL API                                                 │
│  ✅ Webhook system                                              │
│  ✅ Multi-warehouse (multi-tenant adaptable)                   │
│                                                                  │
│  RELEVANCE TO PROP FIRM: 7/10                                   │
│  - Excellent checkout + cart system                             │
│  - Product variant system maps well to challenge sizes          │
│  - Would need significant adaptation for digital goods          │
│  - Commerce-focused, not billing-focused                        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

#### **F. Medusa.js** ⭐⭐⭐⭐
```
┌─────────────────────────────────────────────────────────────────┐
│  MEDUSA - Open Source Headless Commerce Engine                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  License: MIT                                                    │
│  Language: TypeScript (Node.js)                                 │
│  GitHub: github.com/medusajs/medusa                             │
│  Stars: ~27K+                                                   │
│                                                                  │
│  WHAT IT PROVIDES:                                               │
│  ✅ Complete checkout with cart                                  │
│  ✅ Product & variant management                                │
│  ✅ Promotions & discounts                                      │
│  ✅ Multi-currency & multi-region                               │
│  ✅ Tax-inclusive/exclusive pricing                             │
│  ✅ Payment provider plugins                                   │
│  ✅ Order management                                           │
│  ✅ Returns & refunds                                           │
│  ✅ Sales channels (multi-tenant potential)                     │
│  ✅ Plugin/module architecture                                 │
│  ✅ Admin dashboard                                             │
│  ✅ REST + JS SDK                                               │
│                                                                  │
│  RELEVANCE TO PROP FIRM: 7/10                                   │
│  - MIT license is very permissive                               │
│  - Modular architecture easy to extend                          │
│  - "Sales Channels" could map to white-label firms              │
│  - TypeScript = same stack as most prop firm platforms           │
│  - Would need digital goods adaptation                          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 4.3 Open Source Tax & Invoice Solutions

#### **G. InvoiceNinja** ⭐⭐⭐⭐
```
┌─────────────────────────────────────────────────────────────────┐
│  INVOICE NINJA - Open Source Invoicing                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  License: Elastic License 2.0 (v5) / MIT for older versions    │
│  Language: PHP (Laravel) + Flutter (mobile)                     │
│  GitHub: github.com/invoiceninja/invoiceninja                   │
│  Stars: ~8K+                                                    │
│                                                                  │
│  ✅ Invoice generation & PDF                                    │
│  ✅ Recurring invoices                                          │
│  ✅ Multi-currency                                              │
│  ✅ Payment gateway integrations (20+)                         │
│  ✅ Client portal                                               │
│  ✅ Tax management                                              │
│  ✅ White-labeling                                              │
│  ✅ Expense tracking                                            │
│  ✅ REST API                                                    │
│  ✅ Customizable invoice templates                             │
│                                                                  │
│  RELEVANCE: 6/10 - Good for invoice generation component       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

#### **H. Crater Invoice** ⭐⭐⭐
```
┌─────────────────────────────────────────────────────────────────┐
│  CRATER - Open Source Invoicing for Small Business               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  License: AAL (Attribution Assurance License)                   │
│  Language: PHP (Laravel) + Vue.js                               │
│  GitHub: github.com/crater-invoice/crater                       │
│  Stars: ~7.5K+                                                  │
│                                                                  │
│  ✅ Invoice & estimate generation                               │
│  ✅ Multi-currency                                              │
│  ✅ Tax per item                                                │
│  ✅ Payment recording                                           │
│  ✅ Custom fields                                               │
│  ✅ Multi-language                                              │
│  ✅ REST API                                                    │
│                                                                  │
│  RELEVANCE: 5/10 - Simpler, good for invoice-only needs        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 4.4 Open Source Financial Ledger Systems

#### **I. Hledger / Beancount** ⭐⭐⭐
```
┌─────────────────────────────────────────────────────────────────┐
│  DOUBLE-ENTRY ACCOUNTING ENGINES                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Hledger (Haskell) - github.com/simonmichael/hledger            │
│  Beancount (Python) - github.com/beancount/beancount            │
│                                                                  │
│  These provide:                                                  │
│  ✅ Double-entry bookkeeping engine                             │
│  ✅ Multi-currency support                                      │
│  ✅ Audit trail                                                 │
│  ✅ Balance assertions                                          │
│  ✅ Financial reporting                                         │
│                                                                  │
│  RELEVANCE: Useful concept for building internal ledger         │
│  but not directly pluggable into a billing system               │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

#### **J. Tigerbeetle** ⭐⭐⭐⭐⭐
```
┌─────────────────────────────────────────────────────────────────┐
│  TIGERBEETLE - Financial Accounting Database                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  License: Apache 2.0                                             │
│  Language: Zig                                                   │
│  GitHub: github.com/tigerbeetle/tigerbeetle                     │
│  Stars: ~10K+                                                   │
│                                                                  │
│  WHAT IT IS:                                                     │
│  A purpose-built database for financial accounting               │
│  - Double-entry bookkeeping at the database level               │
│  - ACID transactions                                             │
│  - 1M+ transfers per second                                     │
│  - Designed for exactly this use case                           │
│                                                                  │
│  ✅ Double-entry transfers                                      │
│  ✅ Balance tracking                                            │
│  ✅ Idempotent operations                                       │
│  ✅ Multi-currency                                              │
│  ✅ Pending/voiding transfers                                   │
│  ✅ Two-phase transfers (holds)                                 │
│  ✅ Audit log built-in                                          │
│                                                                  │
│  RELEVANCE TO PROP FIRM: 9/10                                   │
│  - Perfect for wallet/balance system                            │
│  - Revenue split ledger                                         │
│  - Affiliate commission tracking                                │
│  - Profit-split accounting                                      │
│  - Payout management                                            │
│  - Handles the financial integrity layer                        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 4.5 Open Source Fraud & Chargeback Tools

#### **K. Fingerprint (Open Source Component)**
```
┌─────────────────────────────────────────────────────────────────┐
│  FRAUD PREVENTION TOOLS                                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  FingerprintJS (github.com/nickolasburr/fingerprint2)           │
│  License: MIT (basic) / Commercial (Pro)                        │
│  ✅ Browser fingerprinting for fraud detection                  │
│                                                                  │
│  Open-source Fraud Scoring:                                      │
│  - MaxMind GeoIP2 (free tier)                                   │
│  - IP reputation databases                                      │
│  - Custom ML fraud models                                       │
│                                                                  │
│  RELEVANCE: 7/10 - Prop firms face high fraud/chargeback rates │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 4.6 Open Source Payout Solutions

```
┌─────────────────────────────────────────────────────────────────┐
│  PAYOUT / DISBURSEMENT TOOLS                                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  No major open-source payout platforms exist.                   │
│  Best approach: Build payout orchestration using:               │
│                                                                  │
│  - Stripe Connect (payouts to connected accounts)               │
│  - Wise API (international bank transfers)                      │
│  - Rise (crypto payouts)                                        │
│  - PayPal Mass Pay                                              │
│                                                                  │
│  Build custom payout service that:                              │
│  1. Calculates profit splits from trading data                  │
│  2. Creates payout requests with approval workflow              │
│  3. Routes to appropriate disbursement method                   │
│  4. Records in financial ledger (TigerBeetle)                  │
│  5. Generates payout receipts/invoices                          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 5. Recommended Architecture Stack

### The Optimal Composite Architecture

Instead of building everything from scratch OR using a single solution, the recommended approach is a **composite architecture** leveraging the best open-source tools for each layer:

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                    RECOMMENDED ARCHITECTURE                                   │
│                    "Best of Breed" Approach                                   │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  LAYER 1: CHECKOUT & STOREFRONT                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                                                                         │ │
│  │  Option A (Recommended): CUSTOM CHECKOUT (React/Next.js)               │ │
│  │  - Built on top of your billing engine's API                           │ │
│  │  - White-label theming per tenant                                      │ │
│  │  - Embeddable widget for firm websites                                 │ │
│  │  - Use Stripe Elements / Hyperswitch SDK for payment form              │ │
│  │                                                                         │ │
│  │  Option B: MEDUSA.JS Checkout Module                                   │ │
│  │  - Use Medusa's cart + checkout + promotion system                     │ │
│  │  - Extend with custom modules for prop firm logic                      │ │
│  │                                                                         │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  LAYER 2: BILLING & SUBSCRIPTION ENGINE                                      │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                                                                         │ │
│  │  PRIMARY: LAGO (Self-hosted)                                           │ │
│  │  - Handles: Subscriptions, one-time charges, coupons,                  │ │
│  │    invoicing, credit wallets, tax, webhooks                            │ │
│  │  - API-first, integrates with any frontend                             │ │
│  │  - Wallet system for retry credits                                     │ │
│  │                                                                         │ │
│  │  ALTERNATIVE: KILL BILL (if Java ecosystem preferred)                  │ │
│  │  - Native multi-tenancy                                                │ │
│  │  - More mature, enterprise-proven                                      │ │
│  │  - Steeper learning curve                                              │ │
│  │                                                                         │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  LAYER 3: PAYMENT PROCESSING                                                │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                                                                         │ │
│  │  PRIMARY: HYPERSWITCH (Self-hosted)                                    │ │
│  │  - Payment orchestration across multiple PSPs                          │ │
│  │  - Smart routing, failover, retry logic                                │ │
│  │  - Unified API for Stripe, Adyen, Checkout.com, etc.                  │ │
│  │  - Critical for prop firms due to processor risk                       │ │
│  │                                                                         │ │
│  │  CONNECTED PSPs:                                                       │ │
│  │  ├── Stripe (primary cards)                                            │ │
│  │  ├── Checkout.com (fallback cards)                                     │ │
│  │  ├── NOWPayments / CoinGate (crypto - custom integration)             │ │
│  │  ├── PayPal                                                            │ │
│  │  └── Regional processors as needed                                     │ │
│  │                                                                         │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  LAYER 4: FINANCIAL LEDGER                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                                                                         │ │
│  │  PRIMARY: TIGERBEETLE                                                  │ │
│  │  - Double-entry ledger for all financial operations                    │ │
│  │  - Revenue split tracking                                              │ │
│  │  - Wallet balances                                                     │ │
│  │  - Affiliate commissions                                               │ │
│  │  - Profit-split accounting                                             │ │
│  │  - Payout tracking                                                     │ │
│  │                                                                         │ │
│  │  ALTERNATIVE: Custom PostgreSQL with double-entry schema               │ │
│  │  (If TigerBeetle's operational model is too complex)                   │ │
│  │                                                                         │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  LAYER 5: CUSTOM PROP FIRM SERVICES (Must Build)                            │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                                                                         │ │
│  │  ├── Revenue Splitting Service                                         │ │
│  │  │   - Configurable split rules per tenant                             │ │
│  │  │   - Affiliate commission calculation                                │ │
│  │  │   - Platform fee deduction                                          │ │
│  │  │                                                                     │ │
│  │  ├── Payout Management Service                                         │ │
│  │  │   - Profit-split calculation from trading data                      │ │
│  │  │   - Payout approval workflows                                       │ │
│  │  │   - Multi-method disbursement                                       │ │
│  │  │                                                                     │ │
│  │  ├── Affiliate/IB Commission Service                                   │ │
│  │  │   - Multi-tier referral tracking                                    │ │
│  │  │   - Commission calculation & accrual                                │ │
│  │  │   - Affiliate payout management                                     │ │
│  │  │                                                                     │ │
│  │  ├── White-Label Configuration Service                                 │ │
│  │  │   - Per-tenant product/pricing overrides                            │ │
│  │  │   - Checkout branding configuration                                 │ │
│  │  │   - Domain routing                                                  │ │
│  │  │                                                                     │ │
│  │  └── Challenge Lifecycle → Billing Bridge                             │ │
│  │      - Auto-provision on payment success                               │ │
│  │      - Refund on challenge pass (if applicable)                        │ │
│  │      - Retry/reset purchase handling                                   │ │
│  │                                                                         │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  LAYER 6: SUPPORTING INFRASTRUCTURE                                         │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │  ├── Tax: Lago built-in OR integrate Avalara/TaxJar API               │ │
│  │  ├── Invoicing: Lago built-in invoice generation                      │ │
│  │  ├── Email: Custom templates via SendGrid/Resend                      │ │
│  │  ├── Analytics: Custom dashboards + Metabase (open-source BI)        │ │
│  │  ├── Fraud: Custom rules + Stripe Radar + Fingerprinting             │ │
│  │  ├── Event Bus: Apache Kafka / RabbitMQ / Redis Streams              │ │
│  │  └── Accounting Export: Custom integration to Xero/QuickBooks        │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Architecture Decision: Why This Combination?

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     WHY LAGO + HYPERSWITCH + TIGERBEETLE               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────────────────────────────────────────┐                  │
│  │           BUILD vs BUY ANALYSIS                   │                  │
│  ├──────────────────────────────────────────────────┤                  │
│  │                                                   │                  │
│  │  BILLING (Lago saves ~3-4 months):                │                  │
│  │  • Subscription logic: ~3 weeks saved             │                  │
│  │  • Invoice generation: ~2 weeks saved             │                  │
│  │  • Coupon system: ~1 week saved                   │                  │
│  │  • Wallet/credits: ~2 weeks saved                 │                  │
│  │  • Webhook system: ~1 week saved                  │                  │
│  │  • Dunning/retry: ~2 weeks saved                  │                  │
│  │  • Tax handling: ~2 weeks saved                   │                  │
│  │                                                   │                  │
│  │  PAYMENTS (Hyperswitch saves ~2-3 months):        │                  │
│  │  • Multi-PSP integration: ~4 weeks saved          │                  │
│  │  • Smart routing: ~3 weeks saved                  │                  │
│  │  • Failover logic: ~2 weeks saved                 │                  │
│  │  • 3DS handling: ~1 week saved                    │                  │
│  │  • Tokenization: ~2 weeks saved                   │                  │
│  │  • Dispute management: ~1 week saved              │                  │
│  │                                                   │                  │
│  │  LEDGER (TigerBeetle saves ~2-3 months):          │                  │
│  │  • Double-entry system: ~4 weeks saved            │                  │
│  │  • Balance consistency: ~2 weeks saved            │                  │
│  │  • Audit trail: ~1 week saved                     │                  │
│  │  • Performance at scale: ~3 weeks saved           │                  │
│  │                                                   │                  │
│  │  TOTAL ESTIMATED SAVINGS: 7-10 months of          │                  │
│  │  engineering time                                  │                  │
│  │                                                   │                  │
│  │  WHAT YOU STILL BUILD (~3-4 months):              │                  │
│  │  • Prop-firm specific business logic               │                  │
│  │  • Revenue splitting service                       │                  │
│  │  • White-label checkout UI                         │                  │
│  │  • Affiliate system                                │                  │
│  │  • Payout workflows                                │                  │
│  │  • Integration glue code                           │                  │
│  │  • Multi-tenant orchestration                      │                  │
│  │                                                   │                  │
│  └──────────────────────────────────────────────────┘                  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Implementation Blueprint

### Phase 1: Foundation (Weeks 1-4)

```
┌─────────────────────────────────────────────────────────────────┐
│  PHASE 1: CORE INFRASTRUCTURE                                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Week 1-2: Infrastructure Setup                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ • Deploy Lago (Docker/Kubernetes)                        │    │
│  │ • Deploy Hyperswitch                                     │    │
│  │ • Deploy TigerBeetle                                     │    │
│  │ • Set up PostgreSQL for application data                 │    │
│  │ • Set up Redis for caching/sessions                      │    │
│  │ • Set up message queue (RabbitMQ/Kafka)                  │    │
│  │ • API Gateway setup (Kong/Traefik)                       │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  Week 3-4: Multi-Tenancy Foundation                             │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ • Tenant management service                              │    │
│  │ • Tenant resolution middleware                           │    │
│  │ • Per-tenant Lago organization mapping                   │    │
│  │ • Per-tenant Hyperswitch merchant mapping                │    │
│  │ • Per-tenant TigerBeetle account structure               │    │
│  │ • Domain routing for white-label sites                   │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Phase 2: Product & Pricing (Weeks 5-6)

```
┌─────────────────────────────────────────────────────────────────┐
│  PHASE 2: PRODUCT CATALOG & PRICING                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Data Model:                                                     │
│                                                                  │
│  ┌─────────────────────────────────────┐                        │
│  │  challenge_products                  │                        │
│  │  ├── id                             │                        │
│  │  ├── tenant_id (nullable for base)  │                        │
│  │  ├── name                           │                        │
│  │  ├── type (1-step, 2-step, instant) │                        │
│  │  ├── description                    │                        │
│  │  ├── is_active                      │                        │
│  │  └── metadata (JSON)               │                        │
│  └─────────────┬───────────────────────┘                        │
│                │                                                 │
│  ┌─────────────▼───────────────────────┐                        │
│  │  product_variants                    │                        │
│  │  ├── id                             │                        │
│  │  ├── product_id                     │                        │
│  │  ├── account_size (10000-500000)    │                        │
│  │  ├── lago_plan_code                 │                        │
│  │  └── trading_platform_config (JSON) │                        │
│  └─────────────┬───────────────────────┘                        │
│                │                                                 │
│  ┌─────────────▼───────────────────────┐                        │
│  │  variant_pricing                     │                        │
│  │  ├── id                             │                        │
│  │  ├── variant_id                     │                        │
│  │  ├── tenant_id (for overrides)      │                        │
│  │  ├── currency                       │                        │
│  │  ├── price_cents                    │                        │
│  │  ├── compare_at_price_cents         │                        │
│  │  └── lago_addon_code                │                        │
│  └─────────────────────────────────────┘                        │
│                                                                  │
│  ┌─────────────────────────────────────┐                        │
│  │  challenge_addons                    │                        │
│  │  ├── id                             │                        │
│  │  ├── tenant_id                      │                        │
│  │  ├── name                           │                        │
│  │  ├── price_cents                    │                        │
│  │  ├── currency                       │                        │
│  │  ├── lago_addon_code                │                        │
│  │  └── compatible_products[]          │                        │
│  └─────────────────────────────────────┘                        │
│                                                                  │
│  Sync products → Lago as Plans & Add-ons                        │
│  Lago handles: pricing, invoicing, tax                          │
│  Your service handles: prop-firm product logic, variants        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Phase 3: Checkout Flow (Weeks 7-10)

```
┌─────────────────────────────────────────────────────────────────┐
│  PHASE 3: CHECKOUT IMPLEMENTATION                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  CHECKOUT FLOW STATE MACHINE:                                    │
│                                                                  │
│  ┌──────────┐     ┌──────────┐     ┌──────────┐                │
│  │ PRODUCT  │────▶│  CART    │────▶│ CUSTOMER │                │
│  │ SELECT   │     │ REVIEW   │     │  INFO    │                │
│  └──────────┘     └──────────┘     └──────┬───┘                │
│                                           │                      │
│                                    ┌──────▼───────┐             │
│                                    │  PROMO CODE  │             │
│                                    │  (optional)  │             │
│                                    └──────┬───────┘             │
│                                           │                      │
│  ┌───────────────────────────────────────▼──────────────────┐   │
│  │               PAYMENT METHOD SELECTION                    │   │
│  │                                                           │   │
│  │  ┌─────────┐ ┌─────────┐ ┌──────────┐ ┌──────────────┐ │   │
│  │  │  Card   │ │ Crypto  │ │  PayPal  │ │ Bank Transfer│ │   │
│  │  │(Stripe) │ │(NOWPay) │ │          │ │ (SEPA/Wire) │ │   │
│  │  └─────────┘ └─────────┘ └──────────┘ └──────────────┘ │   │
│  │                                                           │   │
│  └──────────────────────────┬────────────────────────────────┘   │
│                             │                                     │
│  ┌──────────────────────────▼────────────────────────────────┐   │
│  │                   3D SECURE / VERIFICATION                 │   │
│  └──────────────────────────┬────────────────────────────────┘   │
│                             │                                     │
│  ┌──────────────────────────▼────────────────────────────────┐   │
│  │                   CONFIRMATION PAGE                        │   │
│  │  - Order summary                                          │   │
│  │  - Trading account details (generated async)              │   │
│  │  - Next steps instructions                                │   │
│  │  - Receipt/Invoice download                               │   │
│  └───────────────────────────────────────────────────────────┘   │
│                                                                  │
│  IMPLEMENTATION:                                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Frontend: Next.js / React                              │    │
│  │  ├── Embeddable checkout widget (iframe / web component)│    │
│  │  ├── Hosted checkout page (redirect flow)               │    │
│  │  ├── White-label theming (CSS variables per tenant)     │    │
│  │  ├── Stripe Elements or Hyperswitch SDK for card input  │    │
│  │  └── Crypto payment QR code generation                  │    │
│  │                                                          │    │
│  │  Backend API endpoints:                                  │    │
│  │  ├── POST /checkout/sessions      (create checkout)     │    │
│  │  ├── POST /checkout/apply-promo   (validate promo)      │    │
│  │  ├── POST /checkout/calculate     (price calculation)   │    │
│  │  ├── POST /checkout/pay           (initiate payment)    │    │
│  │  ├── GET  /checkout/status/:id    (payment status)      │    │
│  │  └── POST /checkout/webhooks      (payment callbacks)   │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Phase 4: Payment Processing Integration (Weeks 8-11)

```
┌─────────────────────────────────────────────────────────────────┐
│  PHASE 4: PAYMENT PROCESSING VIA HYPERSWITCH                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  HYPERSWITCH CONFIGURATION:                                      │
│                                                                  │
│  Per Tenant (White-label Firm):                                 │
│  ┌─────────────────────────────────────────────────────┐       │
│  │  Merchant Account Configuration                      │       │
│  │  {                                                   │       │
│  │    "merchant_id": "firm_abc123",                     │       │
│  │    "merchant_name": "TopTrader Prop",               │       │
│  │    "payment_connectors": [                           │       │
│  │      {                                               │       │
│  │        "connector": "stripe",                        │       │
│  │        "priority": 1,                                │       │
│  │        "config": { "api_key": "sk_..." },           │       │
│  │        "supported_currencies": ["USD","EUR","GBP"],  │       │
│  │        "enabled_payment_methods": ["card"]           │       │
│  │      },                                              │       │
│  │      {                                               │       │
│  │        "connector": "checkout",                      │       │
│  │        "priority": 2,  // fallback                   │       │
│  │        "config": { "api_key": "pk_..." },           │       │
│  │        "supported_currencies": ["USD","EUR"],        │       │
│  │        "enabled_payment_methods": ["card"]           │       │
│  │      }                                               │       │
│  │    ],                                                │       │
│  │    "routing_rules": {                                │       │
│  │      "default": "priority",                          │       │
│  │      "fallback": true,                               │       │
│  │      "max_retries": 2                                │       │
│  │    }                                                 │       │
│  │  }                                                   │       │
│  └─────────────────────────────────────────────────────┘       │
│                                                                  │
│  CRYPTO PAYMENTS (Custom Integration):                          │
│  ┌─────────────────────────────────────────────────────┐       │
│  │  Since Hyperswitch may not support crypto natively:  │       │
│  │                                                      │       │
│  │  Option 1: NOWPayments API direct integration        │       │
│  │  Option 2: CoinGate API                              │       │
│  │  Option 3: Custom Hyperswitch connector plugin       │       │
│  │                                                      │       │
│  │  Flow:                                               │       │
│  │  1. Checkout selects "Pay with Crypto"               │       │
│  │  2. Backend calls crypto PSP to create invoice       │       │
│  │  3. Returns wallet address + amount + QR code        │       │
│  │  4. Webhook confirms payment on-chain               │       │
│  │  5. Order marked as paid                             │       │
│  │  6. Standard fulfillment flow continues              │       │
│  └─────────────────────────────────────────────────────┘       │
│                                                                  │
│  STRIPE CONNECT MODEL (Alternative to Hyperswitch):             │
│  ┌─────────────────────────────────────────────────────┐       │
│  │  If using Stripe as primary (simpler but locked-in):│       │
│  │                                                      │       │
│  │  • Platform = Stripe Connect Platform account        │       │
│  │  • Each Firm = Stripe Connected Account              │       │
│  │  • Use "destination charges" for splits:             │       │
│  │    - Charge hits platform                            │       │
│  │    - Auto-transfer to connected account              │       │
│  │    - Platform keeps application fee                  │       │
│  │                                                      │       │
│  │  Pros: Built-in splitting, simple                    │       │
│  │  Cons: Stripe only, crypto not supported,            │       │
│  │        prop firms often get restricted by Stripe     │       │
│  └─────────────────────────────────────────────────────┘       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Phase 5: Revenue Splitting & Ledger (Weeks 10-13)

```
┌─────────────────────────────────────────────────────────────────┐
│  PHASE 5: FINANCIAL LEDGER & REVENUE SPLITS                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  TIGERBEETLE ACCOUNT STRUCTURE:                                  │
│                                                                  │
│  Per Tenant (White-label Firm):                                 │
│  ┌─────────────────────────────────────────────────────┐       │
│  │  Accounts:                                           │       │
│  │  ├── firm:revenue       (firm's earned revenue)      │       │
│  │  ├── firm:payable       (amounts owed to firm)       │       │
│  │  ├── firm:payout_buffer (pending payouts to firm)    │       │
│  │  └── firm:hold          (held/disputed amounts)      │       │
│  └─────────────────────────────────────────────────────┘       │
│                                                                  │
│  Platform Accounts:                                              │
│  ┌─────────────────────────────────────────────────────┐       │
│  │  ├── platform:revenue     (platform fees earned)     │       │
│  │  ├── platform:processing  (PSP fees tracked)         │       │
│  │  ├── platform:escrow      (funds in transit)         │       │
│  │  └── platform:reserves    (chargeback reserves)      │       │
│  └─────────────────────────────────────────────────────┘       │
│                                                                  │
│  Per Affiliate:                                                  │
│  ┌─────────────────────────────────────────────────────┐       │
│  │  ├── affiliate:commission  (earned commissions)      │       │
│  │  ├── affiliate:payable     (ready for payout)        │       │
│  │  └── affiliate:paid        (already disbursed)       │       │
│  └─────────────────────────────────────────────────────┘       │
│                                                                  │
│  Per Trader (for profit-split tracking):                        │
│  ┌─────────────────────────────────────────────────────┐       │
│  │  ├── trader:profits        (earned trading profits)  │       │
│  │  ├── trader:payable        (approved for payout)     │       │
│  │  └── trader:paid           (disbursed)               │       │
│  └─────────────────────────────────────────────────────┘       │
│                                                                  │
│  EXAMPLE TRANSACTION (Challenge Purchase $499):                  │
│  ┌─────────────────────────────────────────────────────┐       │
│  │  Transfer 1: Payment received                        │       │
│  │  DR: platform:escrow         $499.00                 │       │
│  │  CR: incoming:payments       $499.00                 │       │
│  │                                                      │       │
│  │  Transfer 2: PSP fee deducted                        │       │
│  │  DR: platform:processing     $14.77                  │       │
│  │  CR: platform:escrow         $14.77                  │       │
│  │                                                      │       │
│  │  Transfer 3: Platform fee                            │       │
│  │  DR: platform:revenue        $96.85                  │       │
│  │  CR: platform:escrow         $96.85                  │       │
│  │                                                      │       │
│  │  Transfer 4: Affiliate commission                    │       │
│  │  DR: affiliate:commission    $48.42                  │       │
│  │  CR: platform:escrow         $48.42                  │       │
│  │                                                      │       │
│  │  Transfer 5: Firm revenue                            │       │
│  │  DR: firm:revenue            $338.96                 │       │
│  │  CR: platform:escrow         $338.96                 │       │
│  │                                                      │       │
│  │  Escrow balance: $0.00 ✓ (all allocated)            │       │
│  └─────────────────────────────────────────────────────┘       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Phase 6: Payout System (Weeks 12-15)

```
┌─────────────────────────────────────────────────────────────────┐
│  PHASE 6: PAYOUT MANAGEMENT                                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  PAYOUT TYPES:                                                   │
│                                                                  │
│  1. TRADER PROFIT-SPLIT PAYOUTS                                 │
│  ┌─────────────────────────────────────────────────────┐       │
│  │  Trigger: Trader requests payout on funded account   │       │
│  │                                                      │       │
│  │  Flow:                                               │       │
│  │  ├── 1. Trading service calculates P&L               │       │
│  │  ├── 2. Verify payout eligibility rules              │       │
│  │  │   ├── Minimum trading days met?                   │       │
│  │  │   ├── Profit above threshold?                     │       │
│  │  │   ├── No rule violations?                         │       │
│  │  │   └── KYC verified?                               │       │
│  │  ├── 3. Calculate split (e.g., 80% trader / 20% firm)│       │
│  │  ├── 4. Create payout request                        │       │
│  │  ├── 5. Admin approval (configurable auto/manual)    │       │
│  │  ├── 6. Execute payout via:                          │       │
│  │  │   ├── Bank transfer (Wise API)                    │       │
│  │  │   ├── Crypto (USDT to wallet)                     │       │
│  │  │   ├── PayPal                                      │       │
│  │  │   └── Rise (contractor payments)                  │       │
│  │  ├── 7. Record in TigerBeetle ledger                 │       │
│  │  └── 8. Generate payout receipt                      │       │
│  └─────────────────────────────────────────────────────┘       │
│                                                                  │
│  2. AFFILIATE COMMISSION PAYOUTS                                │
│  ┌─────────────────────────────────────────────────────┐       │
│  │  Trigger: Monthly/threshold-based                    │       │
│  │  Method: Bank transfer, crypto, or credit balance    │       │
│  └─────────────────────────────────────────────────────┘       │
│                                                                  │
│  3. FIRM REVENUE PAYOUTS (Platform → Firm)                      │
│  ┌─────────────────────────────────────────────────────┐       │
│  │  Trigger: Weekly/Monthly settlement                  │       │
│  │  Method: Bank transfer to firm's account             │       │
│  └─────────────────────────────────────────────────────┘       │
│                                                                  │
│  PAYOUT STATE MACHINE:                                           │
│                                                                  │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐                  │
│  │REQUESTED │───▶│ APPROVED │───▶│PROCESSING│                  │
│  └────┬─────┘    └──────────┘    └────┬─────┘                  │
│       │                               │                         │
│  ┌────▼─────┐                   ┌────▼─────┐                  │
│  │ REJECTED │                   │COMPLETED │                  │
│  └──────────┘                   └────┬─────┘                  │
│                                      │                         │
│                                 ┌────▼─────┐                  │
│                                 │  FAILED  │───▶ RETRY        │
│                                 └──────────┘                  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Phase 7: Webhook & Event System (Weeks 9-11)

```
┌─────────────────────────────────────────────────────────────────┐
│  EVENT-DRIVEN ARCHITECTURE                                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                   EVENT BUS (Kafka/RabbitMQ)              │   │
│  └──────────┬──────────────────────────────────┬────────────┘   │
│             │                                   │                │
│  INCOMING EVENTS:                    OUTGOING EVENTS:           │
│  ├── payment.succeeded               ├── order.created          │
│  ├── payment.failed                  ├── order.completed        │
│  ├── payment.refunded                ├── order.refunded         │
│  ├── payment.disputed                ├── account.provisioned    │
│  ├── invoice.created (from Lago)     ├── payout.requested       │
│  ├── invoice.paid (from Lago)        ├── payout.completed       │
│  ├── subscription.created            ├── commission.earned       │
│  └── subscription.cancelled          └── revenue.split.recorded │
│                                                                  │
│  EVENT CONSUMERS:                                                │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  payment.succeeded →                                     │    │
│  │    ├── OrderService.confirmOrder()                       │    │
│  │    ├── LedgerService.recordRevenue()                     │    │
│  │    ├── RevenueSplitService.calculateSplits()             │    │
│  │    ├── AffiliateService.recordCommission()               │    │
│  │    ├── ProvisioningService.createTradingAccount()        │    │
│  │    ├── InvoiceService.generateInvoice() [via Lago]       │    │
│  │    ├── NotificationService.sendReceipt()                 │    │
│  │    └── AnalyticsService.trackConversion()                │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  payment.disputed →                                      │    │
│  │    ├── OrderService.flagDispute()                        │    │
│  │    ├── LedgerService.holdFunds()                         │    │
│  │    ├── ProvisioningService.suspendAccount()              │    │
│  │    ├── FraudService.updateRiskScore()                    │    │
│  │    └── NotificationService.alertAdmin()                  │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 7. Compliance & Security

```
┌─────────────────────────────────────────────────────────────────┐
│  COMPLIANCE & SECURITY REQUIREMENTS                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  PCI DSS COMPLIANCE:                                             │
│  ┌─────────────────────────────────────────────────────┐       │
│  │  Strategy: SAQ-A (outsource card handling)           │       │
│  │                                                      │       │
│  │  • Never touch raw card numbers                      │       │
│  │  • Use Stripe Elements / Hyperswitch SDK             │       │
│  │  • Card data goes directly to PSP                    │       │
│  │  • Only store tokens/references                      │       │
│  │  • Hyperswitch handles tokenization vault            │       │
│  └─────────────────────────────────────────────────────┘       │
│                                                                  │
│  KYC/AML:                                                        │
│  ┌─────────────────────────────────────────────────────┐       │
│  │  • Integrate KYC provider (Sumsub, Onfido, Veriff)  │       │
│  │  • KYC required before:                              │       │
│  │    - First payout                                    │       │
│  │    - High-value purchases (configurable threshold)   │       │
│  │  • AML screening on payouts                          │       │
│  │  • Transaction monitoring for suspicious patterns    │       │
│  └─────────────────────────────────────────────────────┘       │
│                                                                  │
│  FRAUD PREVENTION (Critical for Prop Firms):                    │
│  ┌─────────────────────────────────────────────────────┐       │
│  │  Prop firms face 3-5x higher chargeback rates        │       │
│  │                                                      │       │
│  │  Measures:                                           │       │
│  │  ├── 3D Secure mandatory (shifts liability)          │       │
│  │  ├── Stripe Radar / Hyperswitch fraud rules          │       │
│  │  ├── Device fingerprinting                           │       │
│  │  ├── Velocity checks (purchases per IP/device)       │       │
│  │  ├── Email domain reputation                         │       │
│  │  ├── Billing address verification (AVS)              │       │
│  │  ├── Descriptor clarity (clear charge description)   │       │
│  │  ├── Pre-purchase T&C acknowledgment                 │       │
│  │  ├── Refund policy prominently displayed             │       │
│  │  └── Chargeback representment automation             │       │
│  └─────────────────────────────────────────────────────┘       │
│                                                                  │
│  TAX COMPLIANCE:                                                 │
│  ┌─────────────────────────────────────────────────────┐       │
│  │  • EU VAT: Required for EU customers                 │       │
│  │    - VAT reverse charge for B2B                      │       │
│  │    - MOSS/OSS registration                           │       │
│  │  • US Sales Tax: State-by-state (digital goods)      │       │
│  │  • GST: Australia, India, etc.                       │       │
│  │                                                      │       │
│  │  Solutions:                                          │       │
│  │  ├── Lago's built-in tax engine (basic)              │       │
│  │  ├── Avalara AvaTax (comprehensive)                  │       │
│  │  ├── TaxJar (simpler, US-focused)                    │       │
│  │  └── Stripe Tax (if using Stripe)                    │       │
│  └─────────────────────────────────────────────────────┘       │
│                                                                  │
│  DATA PROTECTION:                                                │
│  ┌─────────────────────────────────────────────────────┐       │
│  │  • GDPR compliance for EU customers                  │       │
│  │  • Data encryption at rest and in transit             │       │
│  │  • Audit logging for all financial operations         │       │
│  │  • Data retention policies                           │       │
│  │  • Right to deletion (with financial record retention)│       │
│  │  • Multi-tenant data isolation                       │       │
│  └─────────────────────────────────────────────────────┘       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 8. Comparison Matrix

### Open Source Solutions Comparison

```
┌────────────────────┬──────────┬──────────┬────────────┬──────────┬──────────┬──────────┐
│                    │ Kill Bill│  Lago    │Hyperswitch │TigerBtle │ Medusa   │ Saleor   │
├────────────────────┼──────────┼──────────┼────────────┼──────────┼──────────┼──────────┤
│ License            │Apache 2.0│ AGPL v3  │ Apache 2.0 │Apache 2.0│   MIT    │  BSD-3   │
│ Language           │  Java    │Ruby/TS   │    Rust    │   Zig    │    TS    │ Python   │
│ Multi-Tenancy      │   ✅     │   ❌*    │    ✅      │   ✅     │   ⚠️     │   ⚠️     │
│ Subscriptions      │   ✅     │   ✅     │    ❌      │   ❌     │   ⚠️     │   ❌     │
│ One-time Payments  │   ✅     │   ✅     │    ✅      │   ❌     │   ✅     │   ✅     │
│ Invoicing          │   ✅     │   ✅     │    ❌      │   ❌     │   ✅     │   ✅     │
│ Wallet/Credits     │   ⚠️     │   ✅     │    ❌      │   ✅     │   ❌     │   ❌     │
│ Multi-PSP          │   ✅*    │   ⚠️     │    ✅✅    │   ❌     │   ⚠️     │   ⚠️     │
│ Smart Routing      │   ❌     │   ❌     │    ✅      │   ❌     │   ❌     │   ❌     │
│ Coupons/Promos     │   ✅     │   ✅     │    ❌      │   ❌     │   ✅     │   ✅     │
│ Tax Engine         │   ⚠️     │   ✅     │    ❌      │   ❌     │   ✅     │   ✅     │
│ Double-Entry Ledger│   ❌     │   ❌     │    ❌      │   ✅✅   │   ❌     │   ❌     │
│ Product Catalog    │   ✅     │   ✅     │    ❌      │   ❌     │   ✅     │   ✅     │
│ Cart/Checkout      │   ❌     │   ❌     │    ❌      │   ❌     │   ✅     │   ✅     │
│ Refunds            │   ✅     │   ✅     │    ✅      │   ✅     │   ✅     │   ✅     │
│ Webhooks           │   ✅     │   ✅     │    ✅      │   ❌     │   ✅     │   ✅     │
│ Admin UI           │   ✅     │   ✅     │    ✅      │   ❌     │   ✅     │   ✅     │
│ API Quality        │  Good    │Excellent │  Excellent │  Good    │Excellent │Excellent │
│ Documentation      │  Good    │Excellent │  Excellent │  Good    │Excellent │Excellent │
│ Community          │ Medium   │  Large   │   Large    │ Growing  │  Large   │  Large   │
│ Maturity           │  High    │ Medium   │   Medium   │  Medium  │  High    │  High    │
│                    │          │          │            │          │          │          │
│ PROP FIRM FIT      │  8/10    │  8/10    │   9/10     │  9/10    │  7/10    │  7/10    │
│                    │          │          │            │          │          │          │
│ BEST FOR           │ Billing  │ Billing  │ Payments   │ Ledger   │Checkout  │Checkout  │
│                    │ Engine   │ Engine   │ Routing    │ Engine   │Commerce  │Commerce  │
└────────────────────┴──────────┴──────────┴────────────┴──────────┴──────────┴──────────┘

* Kill Bill has plugins for multi-PSP
* Lago multi-tenancy needs custom implementation per organization
* ⚠️ = Partial support, needs customization
```

### Recommended Combinations

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  OPTION A: "MAXIMUM OPEN SOURCE" (Recommended)                             │
│  Cost: $0 licensing + hosting costs + engineering time                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Lago (Billing) + Hyperswitch (Payments) + TigerBeetle (Ledger)           │
│  + Custom Checkout (Next.js) + Custom Prop Firm Services                   │
│                                                                             │
│  Pros:                                                                      │
│  ✅ No vendor lock-in                                                      │
│  ✅ Full control over every component                                      │
│  ✅ Self-hosted = data sovereignty                                         │
│  ✅ Massive engineering time saved (~7-10 months)                          │
│  ✅ Each component best-in-class for its function                          │
│                                                                             │
│  Cons:                                                                      │
│  ⚠️ Integration complexity between components                              │
│  ⚠️ Need DevOps capability to manage multiple services                     │
│  ⚠️ Lago AGPL license requires care (use commercial if needed)            │
│                                                                             │
│  Engineering effort: ~4-5 months with 2-3 senior engineers                 │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  OPTION B: "HYBRID" (Pragmatic)                                            │
│  Cost: ~$500-2000/mo for managed services + engineering time               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Stripe (Payments + Basic Billing) + TigerBeetle (Ledger)                 │
│  + Custom Checkout + Custom Prop Firm Services                              │
│                                                                             │
│  Pros:                                                                      │
│  ✅ Simpler architecture                                                   │
│  ✅ Stripe handles billing + payments + invoicing                          │
│  ✅ Stripe Connect for revenue splitting                                   │
│  ✅ Less infrastructure to manage                                          │
│                                                                             │
│  Cons:                                                                      │
│  ⚠️ Stripe vendor lock-in                                                 │
│  ⚠️ Stripe often restricts prop firm accounts                             │
│  ⚠️ No crypto support from Stripe                                         │
│  ⚠️ Limited smart routing / failover                                      │
│                                                                             │
│  Engineering effort: ~3-4 months with 2 senior engineers                   │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  OPTION C: "ENTERPRISE" (Maximum Reliability)                              │
│  Cost: ~$2000-10000/mo for managed services                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Kill Bill (Billing) + Hyperswitch (Payments) + TigerBeetle (Ledger)      │
│  + Medusa (Checkout/Catalog) + Custom Prop Firm Services                   │
│                                                                             │
│  Pros:                                                                      │
│  ✅ Kill Bill's native multi-tenancy is perfect                            │
│  ✅ Most battle-tested billing engine                                      │
│  ✅ Apache 2.0 license throughout                                          │
│  ✅ Medusa provides sophisticated catalog + checkout                       │
│                                                                             │
│  Cons:                                                                      │
│  ⚠️ Kill Bill has steep learning curve (Java)                              │
│  ⚠️ More services to manage                                               │
│  ⚠️ Heavier infrastructure requirements                                   │
│                                                                             │
│  Engineering effort: ~5-6 months with 2-3 senior engineers                 │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Complete Technology Stack Summary

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    COMPLETE RECOMMENDED STACK                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  LAYER              │ TECHNOLOGY         │ TYPE          │ LICENSE          │
│  ──────────────────────────────────────────────────────────────────────     │
│  Checkout Frontend   │ Next.js 14+       │ Custom Build  │ MIT              │
│  Checkout UI Comp.   │ Shadcn/ui         │ Open Source   │ MIT              │
│  Payment Form        │ Hyperswitch SDK   │ Open Source   │ Apache 2.0       │
│  Billing Engine      │ Lago              │ Open Source   │ AGPL v3          │
│  Payment Orchestr.   │ Hyperswitch       │ Open Source   │ Apache 2.0       │
│  Financial Ledger    │ TigerBeetle       │ Open Source   │ Apache 2.0       │
│  Application DB      │ PostgreSQL        │ Open Source   │ PostgreSQL Lic.  │
│  Cache / Sessions    │ Redis             │ Open Source   │ BSD              │
│  Message Queue       │ RabbitMQ          │ Open Source   │ MPL 2.0          │
│  Search / Analytics  │ OpenSearch        │ Open Source   │ Apache 2.0       │
│  BI / Reporting      │ Metabase          │ Open Source   │ AGPL v3          │
│  API Gateway         │ Kong / Traefik    │ Open Source   │ Apache 2.0       │
│  Backend Framework   │ NestJS / Fastify  │ Open Source   │ MIT              │
│  Container Orch.     │ Kubernetes        │ Open Source   │ Apache 2.0       │
│  Monitoring          │ Grafana + Prom.   │ Open Source   │ AGPL v3          │
│  Log Management      │ Loki / ELK        │ Open Source   │ AGPL v3 / EL    │
│                                                                             │
│  EXTERNAL (Paid) SERVICES:                                                  │
│  ──────────────────────────────────────────────────────────────────────     │
│  Card Processing     │ Stripe / Adyen    │ SaaS          │ Pay-per-txn      │
│  Crypto Processing   │ NOWPayments       │ SaaS          │ Pay-per-txn      │
│  Tax Calculation     │ Avalara           │ SaaS          │ Subscription     │
│  KYC/AML             │ Sumsub            │ SaaS          │ Pay-per-check    │
│  Email               │ Resend / SendGrid │ SaaS          │ Freemium         │
│  Payouts             │ Wise Business API │ SaaS          │ Pay-per-txn      │
│                                                                             │
│  CUSTOM SERVICES TO BUILD:                                                  │
│  ──────────────────────────────────────────────────────────────────────     │
│  ├── Tenant Management Service                                             │
│  ├── Revenue Split Engine                                                   │
│  ├── Affiliate/IB Commission Service                                       │
│  ├── Payout Management Service                                             │
│  ├── Challenge Lifecycle → Billing Bridge                                  │
│  ├── White-Label Configuration Service                                     │
│  ├── Fraud Scoring Service                                                 │
│  ├── Chargeback Management Service                                         │
│  └── Billing Analytics Aggregation Service                                 │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Final Recommendation

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         EXECUTIVE SUMMARY                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  DO NOT build from scratch. The open-source ecosystem has matured           │
│  enough to provide 60-70% of the checkout & billing infrastructure.         │
│                                                                             │
│  THE WINNING FORMULA:                                                       │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────┐           │
│  │                                                              │           │
│  │   LAGO         → Billing, invoicing, subscriptions, wallets │           │
│  │   HYPERSWITCH  → Payment routing, multi-PSP, failover       │           │
│  │   TIGERBEETLE  → Financial ledger, splits, balances         │           │
│  │   CUSTOM CODE  → Prop firm logic, checkout UI, integrations │           │
│  │                                                              │           │
│  └──────────────────────────────────────────────────────────────┘           │
│                                                                             │
│  ESTIMATED TIMELINE:                                                        │
│  • With open-source stack: 4-5 months to production                        │
│  • Building from scratch: 12-18 months to production                       │
│  • Time saved: 8-13 months                                                 │
│                                                                             │
│  ESTIMATED COST (first year):                                               │
│  • Engineering (3 devs × 5 months): ~$150-250K                             │
│  • Infrastructure: ~$2-5K/month                                            │
│  • External services: ~$1-3K/month                                         │
│  • Total first year: ~$200-350K                                            │
│                                                                             │
│  vs. BUILDING FROM SCRATCH:                                                 │
│  • Engineering (5 devs × 14 months): ~$700K-1.2M                          │
│  • Higher risk of bugs in financial code                                    │
│  • Longer time-to-market = lost revenue opportunity                        │
│                                                                             │
│  KEY RISK MITIGATIONS:                                                      │
│  1. Hyperswitch prevents PSP lock-in (critical for prop firms)             │
│  2. TigerBeetle ensures financial data integrity                           │
│  3. Lago reduces billing logic bugs                                        │
│  4. Multi-PSP routing handles processor shutdowns                          │
│  5. Self-hosted stack ensures data sovereignty                             │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

This architecture gives you an enterprise-grade billing system that can handle the unique complexities of prop firm operations while leveraging battle-tested open-source components for the foundational infrastructure. The key insight is that **prop firm billing is 30% standard billing (use open source) and 70% domain-specific logic (must build custom)** — but that 30% is the hardest, most error-prone part to get right from scratch.
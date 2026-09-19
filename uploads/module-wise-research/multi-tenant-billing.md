# Comprehensive Research: Enterprise-Grade Tenant Billing Module for Prop Firm as a Service (PFaaS) Platform

## Table of Contents
1. [Executive Summary](#executive-summary)
2. [Understanding the Domain](#understanding-the-domain)
3. [Billing Requirements Analysis](#billing-requirements-analysis)
4. [Architecture Design](#architecture-design)
5. [Open-Source Solutions Analysis](#open-source-solutions-analysis)
6. [Commercial Solutions Comparison](#commercial-solutions-comparison)
7. [Recommended Approach](#recommended-approach)
8. [Implementation Blueprint](#implementation-blueprint)

---

## 1. Executive Summary

A **Prop Firm as a Service (PFaaS)** platform enables entrepreneurs to launch their own proprietary trading firms without building infrastructure from scratch. The **Tenant Billing Module** is the financial backbone that handles how each tenant (prop firm operator) is charged for using the platform.

This research evaluates:
- Build vs. Buy vs. Hybrid approaches
- Open-source billing systems that can be adapted
- The unique billing complexities of a PFaaS platform
- A recommended architecture

**Key Finding:** A hybrid approach using **Kill Bill** or **Lago** as the billing engine, combined with custom domain-specific logic for prop-firm metrics, offers the best balance of speed, cost, and flexibility.

---

## 2. Understanding the Domain

### 2.1 What is a Prop Firm as a Service Platform?

```
┌─────────────────────────────────────────────────────────────────┐
│                    PFaaS PLATFORM (You)                         │
│                                                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │ Tenant A │  │ Tenant B │  │ Tenant C │  │ Tenant N │       │
│  │(PropFirm)│  │(PropFirm)│  │(PropFirm)│  │(PropFirm)│       │
│  │          │  │          │  │          │  │          │       │
│  │ 500      │  │ 2,000    │  │ 10,000   │  │ 50,000   │       │
│  │ traders  │  │ traders  │  │ traders  │  │ traders  │       │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘       │
│                                                                 │
│  Shared Infrastructure:                                         │
│  • Trading Engine    • Risk Management    • Challenge System    │
│  • KYC/AML           • Payout System      • Dashboard          │
│  • Market Data Feed  • Analytics          • API Gateway         │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Stakeholder Hierarchy

```
Platform Owner (You)
    └── Tenant (Prop Firm Operator) ← BILLING TARGET
            └── Trader (End User of the Prop Firm)
                    └── Trading Account (Challenge/Funded)
```

### 2.3 Revenue Streams that Need Billing

| Revenue Stream | Description | Billing Complexity |
|---|---|---|
| **Platform Subscription** | Monthly/annual SaaS fee per tenant | Simple recurring |
| **Per-Trader Fees** | Charge per active trader on tenant's platform | Usage-based metering |
| **Challenge Fees Revenue Share** | % of challenge fees collected by tenant | Revenue sharing |
| **Trading Volume Fees** | Per-lot or per-trade execution fees | High-volume metering |
| **Market Data Passthrough** | Redistribution fees for market data | Tiered usage |
| **Payout Processing Fees** | Per-payout transaction fee | Event-based |
| **White-Label Fees** | Custom branding, domain, etc. | One-time + recurring |
| **API Call Overage** | API usage beyond included limits | Usage-based with tiers |
| **Infrastructure Overages** | Compute, storage, bandwidth | Resource metering |
| **Add-on Modules** | KYC, advanced analytics, copy trading | Feature-based |

---

## 3. Billing Requirements Analysis

### 3.1 Functional Requirements

```yaml
Core Billing Functions:
  Subscription Management:
    - Multi-tier plans (Starter, Growth, Enterprise, Custom)
    - Plan versioning and grandfathering
    - Trial periods and promotional pricing
    - Mid-cycle plan upgrades/downgrades (proration)
    
  Usage-Based Billing (Metering):
    - Real-time event ingestion (trades, API calls, logins)
    - Aggregation windows (hourly, daily, monthly)
    - Multiple usage dimensions per tenant
    - Idempotent event processing
    - Late-arriving event handling
    
  Hybrid Billing Models:
    - Base subscription + usage overage
    - Committed use discounts
    - Volume-based tiered pricing
    - Revenue share calculations
    
  Invoice Management:
    - Automated invoice generation
    - Multi-currency support (USD, EUR, GBP, crypto)
    - Tax calculation (VAT, GST, sales tax)
    - Credit notes and adjustments
    - PDF generation and delivery
    
  Payment Processing:
    - Multiple payment gateway integration
    - Auto-charge and dunning management
    - Payment retry logic
    - Refund processing
    - Wire transfer / ACH support for enterprise
    
  Revenue Share & Settlements:
    - Calculate platform's share of tenant revenue
    - Net settlement (billing - revenue share)
    - Settlement reports and reconciliation
    
  Tenant Self-Service:
    - Billing dashboard for tenants
    - Usage monitoring and alerts
    - Payment method management
    - Invoice history and downloads
    - Spending limits and budgets
```

### 3.2 Non-Functional Requirements

```yaml
Performance:
  - Process 100,000+ metering events per second
  - Invoice generation for 1,000+ tenants in < 30 minutes
  - Real-time usage dashboard updates (< 5s latency)
  - 99.99% billing system availability

Security:
  - PCI DSS compliance for payment data
  - SOC 2 Type II compliance
  - Data encryption at rest and in transit
  - Tenant data isolation
  - Audit trail for all billing operations

Scalability:
  - Support 10 to 100,000+ tenants
  - Handle billions of metering events per month
  - Horizontal scaling of metering pipeline

Financial Compliance:
  - Revenue recognition (ASC 606 / IFRS 15)
  - Multi-jurisdiction tax compliance
  - Financial audit trails
  - Immutable billing records

Integration:
  - REST/GraphQL API for all operations
  - Webhook notifications for billing events
  - ERP integration (QuickBooks, Xero, NetSuite)
  - CRM integration (Salesforce, HubSpot)
```

### 3.3 Prop-Firm Specific Billing Complexities

```
┌─────────────────────────────────────────────────────────────────┐
│              PROP FIRM SPECIFIC BILLING CHALLENGES              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. CHALLENGE FEE REVENUE SHARE                                │
│     Tenant charges trader $500 for a challenge                 │
│     Platform takes 15% = $75                                    │
│     Need to track ALL challenge purchases across tenants        │
│                                                                 │
│  2. FUNDED ACCOUNT METERING                                     │
│     Charge per active funded account per month                  │
│     Account can be activated/deactivated mid-cycle              │
│     Pro-rated billing required                                  │
│                                                                 │
│  3. TRADING VOLUME BILLING                                      │
│     Track lots traded across all tenant's traders               │
│     Tiered pricing: 0-10K lots free, 10K-100K @ $0.10/lot     │
│     Real-time aggregation needed                                │
│                                                                 │
│  4. MARKET DATA LICENSING                                       │
│     Pass-through costs from data providers                      │
│     Per-user redistribution fees                                │
│     Depends on data tier (Level 1, Level 2, etc.)              │
│                                                                 │
│  5. PAYOUT PROCESSING                                           │
│     Per-payout fee when tenant pays a trader                    │
│     Fee varies by payment method                                │
│     Cross-border payment surcharges                             │
│                                                                 │
│  6. RISK ENGINE USAGE                                           │
│     Per-evaluation of risk rules                                │
│     Compute-intensive, needs resource metering                  │
│                                                                 │
│  7. WHITE-LABEL COMPLEXITY                                      │
│     Custom domain ($50/mo), Custom app ($500/mo)               │
│     One-time setup fees + recurring                             │
│                                                                 │
│  8. MULTI-CURRENCY SETTLEMENTS                                  │
│     Tenant earns in multiple currencies                         │
│     Platform charges in USD                                     │
│     FX rate handling for settlements                            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. Architecture Design

### 4.1 High-Level Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                         PFaaS PLATFORM                                 │
│                                                                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │
│  │  Trading     │  │  Challenge   │  │  Payout      │  │  API         │ │
│  │  Engine      │  │  System      │  │  System      │  │  Gateway     │ │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬──────┘ │
│         │                 │                 │                 │        │
│         ▼                 ▼                 ▼                 ▼        │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │                    EVENT BUS (Kafka/NATS)                       │  │
│  │  trade.executed | challenge.purchased | payout.sent | api.call  │  │
│  └──────────────────────────┬──────────────────────────────────────┘  │
│                              │                                        │
│                              ▼                                        │
│  ┌──────────────────────────────────────────────────────────────────┐ │
│  │                   BILLING MODULE                                  │ │
│  │                                                                    │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │ │
│  │  │   METERING    │  │  RATING &     │  │  SUBSCRIPTION       │   │ │
│  │  │   ENGINE      │  │  PRICING      │  │  MANAGER            │   │ │
│  │  │              │  │  ENGINE       │  │                      │   │ │
│  │  │ • Ingest     │  │ • Price calc  │  │ • Plan management   │   │ │
│  │  │ • Dedupe     │  │ • Tiering     │  │ • Lifecycle mgmt    │   │ │
│  │  │ • Aggregate  │  │ • Discounts   │  │ • Proration         │   │ │
│  │  │ • Store      │  │ • Rev share   │  │ • Trials            │   │ │
│  │  └──────┬───────┘  └──────┬───────┘  └──────────┬───────────┘   │ │
│  │         │                 │                      │               │ │
│  │         ▼                 ▼                      ▼               │ │
│  │  ┌──────────────────────────────────────────────────────────┐   │ │
│  │  │              INVOICE ENGINE                                │   │ │
│  │  │  • Line item aggregation  • Tax calculation               │   │ │
│  │  │  • Multi-currency         • PDF generation                │   │ │
│  │  │  • Credit application     • Delivery (email/portal)       │   │ │
│  │  └──────────────────────────┬───────────────────────────────┘   │ │
│  │                              │                                   │ │
│  │                              ▼                                   │ │
│  │  ┌──────────────────────────────────────────────────────────┐   │ │
│  │  │              PAYMENT ENGINE                                │   │ │
│  │  │  • Stripe/Adyen integration  • Dunning management        │   │ │
│  │  │  • Wire/ACH processing       • Retry logic               │   │ │
│  │  │  • Wallet/credit system      • Refund processing         │   │ │
│  │  └──────────────────────────┬───────────────────────────────┘   │ │
│  │                              │                                   │ │
│  │                              ▼                                   │ │
│  │  ┌──────────────────────────────────────────────────────────┐   │ │
│  │  │           SETTLEMENT & RECONCILIATION                      │   │ │
│  │  │  • Revenue share calculations  • Net settlement           │   │ │
│  │  │  • Ledger entries              • Financial reporting      │   │ │
│  │  └──────────────────────────────────────────────────────────┘   │ │
│  │                                                                    │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │ │
│  │  │   TENANT      │  │  ADMIN        │  │  REPORTING &        │   │ │
│  │  │   PORTAL      │  │  PORTAL       │  │  ANALYTICS          │   │ │
│  │  └──────────────┘  └──────────────┘  └──────────────────────┘   │ │
│  └──────────────────────────────────────────────────────────────────┘ │
│                                                                        │
│  ┌──────────────────────────────────────────────────────────────────┐ │
│  │                    DATA STORES                                     │ │
│  │  PostgreSQL (billing data) │ TimescaleDB (metering) │ Redis      │ │
│  └──────────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Data Model (Core Entities)

```sql
-- Core Billing Data Model

-- Tenant/Organization
CREATE TABLE tenants (
    id UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    billing_email VARCHAR(255),
    billing_currency VARCHAR(3) DEFAULT 'USD',
    tax_id VARCHAR(50),
    billing_address JSONB,
    status VARCHAR(20) DEFAULT 'active', -- active, suspended, churned
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Products/Features
CREATE TABLE products (
    id UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    code VARCHAR(100) UNIQUE NOT NULL, -- e.g., 'platform_subscription', 'per_trader', 'market_data'
    description TEXT,
    product_type VARCHAR(50) NOT NULL, -- 'recurring', 'usage', 'one_time', 'revenue_share'
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Pricing Plans
CREATE TABLE plans (
    id UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    code VARCHAR(100) UNIQUE NOT NULL, -- 'starter', 'growth', 'enterprise'
    description TEXT,
    billing_interval VARCHAR(20) NOT NULL, -- 'monthly', 'quarterly', 'annual'
    base_price DECIMAL(12,4) NOT NULL,
    currency VARCHAR(3) DEFAULT 'USD',
    included_limits JSONB, -- {"traders": 500, "api_calls": 100000, "funded_accounts": 100}
    features JSONB, -- {"white_label": false, "custom_domain": true, "api_access": true}
    is_active BOOLEAN DEFAULT TRUE,
    version INTEGER DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Plan Pricing Components (for hybrid billing)
CREATE TABLE plan_price_components (
    id UUID PRIMARY KEY,
    plan_id UUID REFERENCES plans(id),
    product_id UUID REFERENCES products(id),
    pricing_model VARCHAR(50) NOT NULL, -- 'flat', 'per_unit', 'tiered', 'volume', 'percentage'
    unit_price DECIMAL(12,6),
    percentage DECIMAL(5,4), -- for revenue share
    tiers JSONB, -- [{"up_to": 1000, "price": 1.00}, {"up_to": 10000, "price": 0.75}]
    included_units BIGINT DEFAULT 0,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Subscriptions
CREATE TABLE subscriptions (
    id UUID PRIMARY KEY,
    tenant_id UUID REFERENCES tenants(id),
    plan_id UUID REFERENCES plans(id),
    status VARCHAR(20) DEFAULT 'active', -- 'trialing', 'active', 'past_due', 'canceled', 'suspended'
    current_period_start TIMESTAMPTZ NOT NULL,
    current_period_end TIMESTAMPTZ NOT NULL,
    trial_end TIMESTAMPTZ,
    canceled_at TIMESTAMPTZ,
    cancel_at_period_end BOOLEAN DEFAULT FALSE,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Metering Events (high-volume, partitioned)
CREATE TABLE metering_events (
    id UUID DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    event_type VARCHAR(100) NOT NULL, -- 'trade.executed', 'trader.active', 'api.call', 'challenge.purchased'
    idempotency_key VARCHAR(255) NOT NULL,
    properties JSONB NOT NULL, -- {"lots": 1.5, "symbol": "EURUSD", "trader_id": "..."}
    quantity DECIMAL(20,6) DEFAULT 1,
    timestamp TIMESTAMPTZ NOT NULL,
    processed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (id, timestamp)
) PARTITION BY RANGE (timestamp);

-- Usage Aggregates (pre-computed)
CREATE TABLE usage_aggregates (
    id UUID PRIMARY KEY,
    tenant_id UUID REFERENCES tenants(id),
    product_id UUID REFERENCES products(id),
    period_start TIMESTAMPTZ NOT NULL,
    period_end TIMESTAMPTZ NOT NULL,
    quantity DECIMAL(20,6) NOT NULL,
    unit VARCHAR(50), -- 'traders', 'lots', 'api_calls', 'payouts', 'challenges'
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, product_id, period_start, period_end)
);

-- Invoices
CREATE TABLE invoices (
    id UUID PRIMARY KEY,
    invoice_number VARCHAR(50) UNIQUE NOT NULL,
    tenant_id UUID REFERENCES tenants(id),
    subscription_id UUID REFERENCES subscriptions(id),
    status VARCHAR(20) DEFAULT 'draft', -- 'draft', 'open', 'paid', 'void', 'uncollectible'
    currency VARCHAR(3) NOT NULL,
    subtotal DECIMAL(12,4) NOT NULL,
    tax_amount DECIMAL(12,4) DEFAULT 0,
    discount_amount DECIMAL(12,4) DEFAULT 0,
    total DECIMAL(12,4) NOT NULL,
    amount_paid DECIMAL(12,4) DEFAULT 0,
    amount_due DECIMAL(12,4) NOT NULL,
    period_start TIMESTAMPTZ,
    period_end TIMESTAMPTZ,
    due_date DATE,
    paid_at TIMESTAMPTZ,
    voided_at TIMESTAMPTZ,
    pdf_url TEXT,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Invoice Line Items
CREATE TABLE invoice_line_items (
    id UUID PRIMARY KEY,
    invoice_id UUID REFERENCES invoices(id),
    product_id UUID REFERENCES products(id),
    description TEXT NOT NULL,
    quantity DECIMAL(20,6),
    unit_price DECIMAL(12,6),
    amount DECIMAL(12,4) NOT NULL,
    tax_rate DECIMAL(5,4),
    tax_amount DECIMAL(12,4) DEFAULT 0,
    period_start TIMESTAMPTZ,
    period_end TIMESTAMPTZ,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Payments
CREATE TABLE payments (
    id UUID PRIMARY KEY,
    tenant_id UUID REFERENCES tenants(id),
    invoice_id UUID REFERENCES invoices(id),
    amount DECIMAL(12,4) NOT NULL,
    currency VARCHAR(3) NOT NULL,
    payment_method VARCHAR(50), -- 'card', 'wire', 'ach', 'crypto'
    payment_gateway VARCHAR(50), -- 'stripe', 'adyen', 'wise'
    gateway_payment_id VARCHAR(255),
    status VARCHAR(20) DEFAULT 'pending', -- 'pending', 'succeeded', 'failed', 'refunded'
    failure_reason TEXT,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Wallet/Credits
CREATE TABLE tenant_wallets (
    id UUID PRIMARY KEY,
    tenant_id UUID REFERENCES tenants(id) UNIQUE,
    balance DECIMAL(12,4) DEFAULT 0,
    currency VARCHAR(3) DEFAULT 'USD',
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE wallet_transactions (
    id UUID PRIMARY KEY,
    wallet_id UUID REFERENCES tenant_wallets(id),
    type VARCHAR(20) NOT NULL, -- 'credit', 'debit', 'refund'
    amount DECIMAL(12,4) NOT NULL,
    description TEXT,
    reference_type VARCHAR(50), -- 'invoice', 'manual', 'promotion'
    reference_id UUID,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Revenue Share Tracking
CREATE TABLE revenue_share_events (
    id UUID PRIMARY KEY,
    tenant_id UUID REFERENCES tenants(id),
    event_type VARCHAR(50) NOT NULL, -- 'challenge_purchase', 'addon_purchase'
    gross_amount DECIMAL(12,4) NOT NULL,
    platform_share_pct DECIMAL(5,4) NOT NULL,
    platform_share_amount DECIMAL(12,4) NOT NULL,
    tenant_share_amount DECIMAL(12,4) NOT NULL,
    currency VARCHAR(3) NOT NULL,
    source_transaction_id VARCHAR(255),
    period_start TIMESTAMPTZ,
    period_end TIMESTAMPTZ,
    settled BOOLEAN DEFAULT FALSE,
    invoice_id UUID REFERENCES invoices(id),
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 5. Open-Source Solutions Analysis

### 5.1 Comprehensive Comparison Matrix

| Feature | **Kill Bill** | **Lago** | **Open Billing** | **Hyperswitch** | **jBilling** | **FOSSBilling** |
|---|---|---|---|---|---|---|
| **Subscription Mgmt** | ✅ Excellent | ✅ Excellent | ✅ Good | ❌ Payment only | ✅ Good | ✅ Basic |
| **Usage-Based Billing** | ✅ Via plugins | ✅ Native | ⚠️ Limited | ❌ No | ⚠️ Limited | ❌ No |
| **Multi-Tenancy** | ✅ Native | ✅ Native | ⚠️ Basic | ✅ Native | ⚠️ Basic | ❌ No |
| **Revenue Share** | ⚠️ Custom dev | ⚠️ Custom dev | ❌ No | ❌ No | ❌ No | ❌ No |
| **Metering/Events** | ⚠️ Plugin | ✅ Native API | ❌ No | ❌ No | ❌ No | ❌ No |
| **Invoice Generation** | ✅ Excellent | ✅ Excellent | ✅ Good | ❌ No | ✅ Good | ✅ Basic |
| **Payment Processing** | ✅ Multi-gateway | ✅ Multi-gateway | ⚠️ Limited | ✅ Excellent | ✅ Good | ✅ Basic |
| **Dunning** | ✅ Yes | ✅ Yes | ⚠️ Basic | ❌ No | ✅ Yes | ❌ No |
| **API Quality** | ✅ Comprehensive | ✅ Modern REST | ⚠️ Basic | ✅ Excellent | ⚠️ SOAP/REST | ⚠️ Basic |
| **Multi-Currency** | ✅ Yes | ✅ Yes | ⚠️ Limited | ✅ Yes | ✅ Yes | ⚠️ Limited |
| **Tax Integration** | ✅ Via plugins | ✅ Native | ❌ No | ❌ No | ⚠️ Basic | ❌ No |
| **Webhook System** | ✅ Yes | ✅ Yes | ⚠️ Basic | ✅ Yes | ⚠️ Basic | ❌ No |
| **Language** | Java | Ruby/Rust | PHP | Rust | Java | PHP |
| **License** | Apache 2.0 | AGPL-3.0 | MIT | Apache 2.0 | AGPL-3.0 | Apache 2.0 |
| **Community** | Large | Growing fast | Small | Growing | Small | Small |
| **Production Ready** | ✅ Battle-tested | ✅ Yes | ⚠️ Emerging | ✅ Yes | ✅ Mature | ⚠️ Basic |
| **Scalability** | ✅ High | ✅ High | ⚠️ Medium | ✅ High | ⚠️ Medium | ⚠️ Low |
| **Documentation** | ✅ Excellent | ✅ Excellent | ⚠️ Fair | ✅ Good | ⚠️ Fair | ⚠️ Fair |

### 5.2 Deep Dive: Kill Bill

```
┌─────────────────────────────────────────────────────────────┐
│                     KILL BILL                                │
│              "The Open-Source Billing Platform"               │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  GitHub: github.com/killbill/killbill                       │
│  Stars: ~4,500+ | License: Apache 2.0                       │
│  Language: Java (Spring) | DB: PostgreSQL/MySQL              │
│  Companies: Groupon (origin), Shopify, others               │
│                                                              │
│  ARCHITECTURE:                                               │
│  ┌─────────┐  ┌──────────┐  ┌──────────┐  ┌─────────────┐ │
│  │ Catalog │  │Entitlement│  │ Invoice  │  │  Payment    │ │
│  │ Module  │  │ Module    │  │ Module   │  │  Module     │ │
│  └─────────┘  └──────────┘  └──────────┘  └─────────────┘ │
│  ┌─────────┐  ┌──────────┐  ┌──────────┐  ┌─────────────┐ │
│  │ Plugin  │  │  Tenant  │  │  Usage   │  │  Analytics  │ │
│  │ System  │  │  Module  │  │  Module  │  │  Module     │ │
│  └─────────┘  └──────────┘  └──────────┘  └─────────────┘ │
│                                                              │
│  STRENGTHS FOR PFaaS:                                        │
│  ✅ Native multi-tenant architecture                         │
│  ✅ Plugin system for custom billing logic                   │
│  ✅ Robust subscription lifecycle management                 │
│  ✅ Supports complex plan catalogs with phases               │
│  ✅ Proration, credits, refunds built-in                    │
│  ✅ Payment plugin for Stripe, Adyen, etc.                  │
│  ✅ Battle-tested at scale (Groupon origin)                 │
│  ✅ Apache 2.0 license (no copyleft concerns)               │
│                                                              │
│  WEAKNESSES FOR PFaaS:                                       │
│  ❌ Usage metering is basic (needs custom plugin)           │
│  ❌ Revenue share not built-in                              │
│  ❌ Java stack may not match your tech stack                │
│  ❌ Steep learning curve                                    │
│  ❌ UI is basic (KAUI admin console)                        │
│  ❌ Heavy resource requirements                             │
│                                                              │
│  EFFORT TO ADAPT: 6-10 weeks                                │
│  COMPLEXITY: HIGH                                            │
│  MATURITY: ★★★★★                                            │
└─────────────────────────────────────────────────────────────┘
```

**Kill Bill Plugin Example for Prop Firm Revenue Share:**

```java
// Custom Kill Bill Plugin for Revenue Share Billing
@Component
public class PropFirmRevenueSharePlugin implements InvoicePluginApi {
    
    @Override
    public List<InvoiceItem> getAdditionalInvoiceItems(
            Invoice invoice, 
            boolean isDryRun,
            Iterable<PluginProperty> properties,
            CallContext context) {
        
        UUID tenantId = context.getTenantId();
        LocalDate startDate = invoice.getInvoiceDate().minusMonths(1);
        LocalDate endDate = invoice.getInvoiceDate();
        
        // Calculate revenue share for challenge fees
        BigDecimal challengeRevenue = revenueShareService
            .getTenantChallengeRevenue(tenantId, startDate, endDate);
        BigDecimal platformSharePct = getPlatformSharePercentage(tenantId);
        BigDecimal platformShare = challengeRevenue.multiply(platformSharePct);
        
        List<InvoiceItem> items = new ArrayList<>();
        
        if (platformShare.compareTo(BigDecimal.ZERO) > 0) {
            items.add(new PluginInvoiceItem(
                new InvoiceItemBuilder()
                    .withInvoiceId(invoice.getId())
                    .withAccountId(invoice.getAccountId())
                    .withDescription("Platform Revenue Share - Challenge Fees")
                    .withAmount(platformShare)
                    .withCurrency(invoice.getCurrency())
                    .withStartDate(startDate)
                    .withEndDate(endDate)
                    .build()
            ));
        }
        
        return items;
    }
}
```

### 5.3 Deep Dive: Lago

```
┌─────────────────────────────────────────────────────────────┐
│                        LAGO                                   │
│        "Open Source Metering & Usage-Based Billing"           │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  GitHub: github.com/getlago/lago                            │
│  Stars: ~7,000+ | License: AGPL-3.0                         │
│  Language: Ruby (API), Rust (Event ingestion), React (UI)    │
│  Companies: Mistral AI, Together AI, Groq                   │
│                                                              │
│  ARCHITECTURE:                                               │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              Lago API (Ruby/Rails)                   │    │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐            │    │
│  │  │Billable  │ │ Plans &  │ │ Invoice  │            │    │
│  │  │Metrics   │ │ Charges  │ │ Engine   │            │    │
│  │  └──────────┘ └──────────┘ └──────────┘            │    │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐            │    │
│  │  │ Wallets  │ │ Coupons  │ │ Webhooks │            │    │
│  │  └──────────┘ └──────────┘ └──────────┘            │    │
│  └─────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │       Event Ingestion (Rust - high performance)      │    │
│  └─────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              Frontend (React)                        │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  STRENGTHS FOR PFaaS:                                        │
│  ✅ BEST-IN-CLASS usage metering and event ingestion        │
│  ✅ Native support for hybrid billing (sub + usage)         │
│  ✅ Multiple aggregation types (count, sum, max, unique)    │
│  ✅ Graduated, package, and percentage pricing models       │
│  ✅ Built-in wallet/prepaid credits system                  │
│  ✅ Modern REST API with excellent DX                       │
│  ✅ Beautiful admin UI included                             │
│  ✅ Self-hostable with Docker                               │
│  ✅ Webhook system for event notifications                  │
│  ✅ Progressive billing (real-time invoicing)               │
│  ✅ Coupon and discount management                          │
│                                                              │
│  WEAKNESSES FOR PFaaS:                                       │
│  ⚠️ AGPL-3.0 license (copyleft - must open source          │
│     modifications if providing as network service)           │
│  ❌ Revenue share calculations not native                   │
│  ❌ Settlement/reconciliation not built-in                  │
│  ❌ Multi-tenant (your tenants) needs custom work           │
│  ❌ Relatively newer project (est. 2022)                    │
│  ❌ Tax engine is basic (no jurisdiction intelligence)      │
│                                                              │
│  EFFORT TO ADAPT: 4-8 weeks                                 │
│  COMPLEXITY: MEDIUM                                          │
│  MATURITY: ★★★★☆                                            │
└─────────────────────────────────────────────────────────────┘
```

**Lago Configuration Example for PFaaS:**

```ruby
# Lago API calls to set up PFaaS billing

# 1. Create Billable Metrics
lago_client.billable_metrics.create({
  name: "Active Traders",
  code: "active_traders",
  aggregation_type: "unique_count_agg",
  field_name: "trader_id",
  recurring: true
})

lago_client.billable_metrics.create({
  name: "Trading Volume (Lots)",
  code: "trading_volume_lots",
  aggregation_type: "sum_agg",
  field_name: "lots",
  recurring: false
})

lago_client.billable_metrics.create({
  name: "Challenge Purchases",
  code: "challenge_purchases",
  aggregation_type: "sum_agg",
  field_name: "amount",
  recurring: false
})

lago_client.billable_metrics.create({
  name: "API Calls",
  code: "api_calls",
  aggregation_type: "count_agg",
  recurring: false
})

lago_client.billable_metrics.create({
  name: "Payouts Processed",
  code: "payouts_processed",
  aggregation_type: "count_agg",
  recurring: false
})

# 2. Create Plan
lago_client.plans.create({
  name: "Growth Plan",
  code: "growth",
  interval: "monthly",
  amount_cents: 99900, # $999/month base
  amount_currency: "USD",
  charges: [
    {
      billable_metric_id: active_traders_metric.id,
      charge_model: "graduated",
      properties: {
        graduated_ranges: [
          { from_value: 0, to_value: 1000, per_unit_amount: "0", flat_amount: "0" },
          { from_value: 1001, to_value: 5000, per_unit_amount: "0.50", flat_amount: "0" },
          { from_value: 5001, to_value: nil, per_unit_amount: "0.30", flat_amount: "0" }
        ]
      }
    },
    {
      billable_metric_id: trading_volume_metric.id,
      charge_model: "graduated",
      properties: {
        graduated_ranges: [
          { from_value: 0, to_value: 50000, per_unit_amount: "0", flat_amount: "0" },
          { from_value: 50001, to_value: 500000, per_unit_amount: "0.05", flat_amount: "0" },
          { from_value: 500001, to_value: nil, per_unit_amount: "0.02", flat_amount: "0" }
        ]
      }
    },
    {
      billable_metric_id: challenge_purchases_metric.id,
      charge_model: "percentage",
      properties: {
        rate: "0.15", # 15% platform share
        fixed_amount: "0"
      }
    },
    {
      billable_metric_id: api_calls_metric.id,
      charge_model: "package",
      properties: {
        amount: "10.00",
        package_size: 100000,
        free_units: 100000
      }
    },
    {
      billable_metric_id: payouts_metric.id,
      charge_model: "standard",
      properties: {
        amount: "2.50" # per payout
      }
    }
  ]
})

# 3. Ingest Usage Events
lago_client.events.create({
  transaction_id: "trade_#{SecureRandom.uuid}", # idempotency key
  external_customer_id: "tenant_abc",
  code: "trading_volume_lots",
  timestamp: Time.now.to_i,
  properties: {
    lots: 2.5,
    symbol: "EURUSD",
    trader_id: "trader_123"
  }
})
```

### 5.4 Deep Dive: Hyperswitch (Payment Router)

```
┌─────────────────────────────────────────────────────────────┐
│                    HYPERSWITCH                                │
│          "Open Source Payment Orchestrator"                   │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  GitHub: github.com/juspay/hyperswitch                      │
│  Stars: ~12,000+ | License: Apache 2.0                      │
│  Language: Rust | Companies: Juspay                         │
│                                                              │
│  NOTE: This is NOT a billing system - it's a PAYMENT        │
│  ROUTER/ORCHESTRATOR. Include it as the payment layer       │
│  beneath your billing system.                                │
│                                                              │
│  STRENGTHS:                                                  │
│  ✅ 50+ payment processor integrations                      │
│  ✅ Smart routing to optimize payment success rates          │
│  ✅ Built-in retry logic and fallback                       │
│  ✅ PCI DSS compliant vault                                 │
│  ✅ Multi-currency native                                   │
│  ✅ Excellent Rust performance                              │
│  ✅ Apache 2.0 license                                      │
│                                                              │
│  USE IN PFaaS: As the payment processing layer              │
│  behind Kill Bill or Lago                                    │
└─────────────────────────────────────────────────────────────┘
```

### 5.5 Deep Dive: Other Notable Open-Source Options

```
┌─────────────────────────────────────────────────────────────┐
│                   OTHER OPTIONS                              │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  OPENMETER (github.com/openmeterio/openmeter)               │
│  Stars: ~1,200+ | License: Apache 2.0                       │
│  Language: Go                                                │
│  Focus: METERING ONLY (not full billing)                     │
│  ✅ High-performance event ingestion                        │
│  ✅ CloudEvents standard                                    │
│  ✅ Real-time aggregation with Kafka+ClickHouse             │
│  ✅ Could pair with Kill Bill for full solution              │
│  USE: As metering layer if building custom billing           │
│                                                              │
│  ──────────────────────────────────────────────────          │
│                                                              │
│  LOTUS (now USELOTUS) - github.com/uselotus/lotus           │
│  Stars: ~1,700+ | License: MIT                              │
│  Language: Python/Django                                     │
│  Status: ⚠️ Company pivoted, open source may be stale       │
│  ✅ Good usage-based billing concepts                       │
│  ✅ MIT license                                             │
│  ❌ Uncertain maintenance future                            │
│                                                              │
│  ──────────────────────────────────────────────────          │
│                                                              │
│  OPENBOXES / ERPNEXT (for ERP integration)                  │
│  Not billing-specific but ERPNext has billing modules        │
│  Could be used for financial reporting/reconciliation        │
│                                                              │
│  ──────────────────────────────────────────────────          │
│                                                              │
│  STRIPE BILLING (not open source, but worth comparing)      │
│  The benchmark all open-source solutions aspire to           │
│  2.9% + 30¢ per transaction can get expensive at scale      │
└─────────────────────────────────────────────────────────────┘
```

### 5.6 License Comparison & Implications

```
┌──────────────────────────────────────────────────────────────────┐
│                    LICENSE IMPLICATIONS                            │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  APACHE 2.0 (Kill Bill, Hyperswitch, OpenMeter):                │
│  ✅ Can use in proprietary software                              │
│  ✅ Can modify without sharing changes                           │
│  ✅ Can sublicense                                               │
│  ✅ BEST for commercial PFaaS platform                          │
│                                                                   │
│  AGPL-3.0 (Lago, jBilling):                                     │
│  ⚠️ If you modify and provide as a network service,             │
│     you MUST open source your modifications                      │
│  ⚠️ Your PFaaS IS a network service                             │
│  ⚠️ Options:                                                    │
│     1. Open source your billing modifications                    │
│     2. Purchase commercial license from Lago                     │
│     3. Use Lago's API without modifying source code              │
│     4. Run as a separate service (API boundary argument)         │
│                                                                   │
│  MIT (Lotus):                                                     │
│  ✅ Most permissive, no concerns                                 │
│  ⚠️ But project maintenance is uncertain                        │
│                                                                   │
│  RECOMMENDATION: Prefer Apache 2.0 licensed solutions            │
│  or budget for Lago's commercial license if using Lago           │
└──────────────────────────────────────────────────────────────────┘
```

---

## 6. Commercial Solutions Comparison (for reference)

| Solution | Type | Starting Price | Strengths | Weaknesses |
|---|---|---|---|---|
| **Stripe Billing** | SaaS | 0.5-0.8% of billing | Easy integration, reliable | Expensive at scale, less flexible |
| **Chargebee** | SaaS | $249/mo+ | Great subscription mgmt | Limited usage-based, expensive |
| **Zuora** | SaaS | Custom (expensive) | Enterprise-grade, ASC 606 | Very expensive, complex |
| **Maxio** | SaaS | $5,000/mo+ | B2B SaaS focused | Expensive, limited metering |
| **Amberflo** | SaaS | Custom | Real-time metering | Newer, limited ecosystem |
| **Metronome** | SaaS | Custom | Usage-based billing | Limited subscription features |
| **Orb** | SaaS | Custom | Modern usage billing | Newer, less proven |
| **Recurly** | SaaS | $0+usage | Good subscription mgmt | Limited usage-based |

---

## 7. Recommended Approach

### 7.1 Decision Framework

```
┌─────────────────────────────────────────────────────────────────────┐
│                    DECISION MATRIX                                    │
├──────────────────────┬──────────┬──────────┬──────────┬─────────────┤
│ Criteria (weight)    │ Build    │ Lago     │Kill Bill │ Lago+Custom │
│                      │ Custom   │ Only     │ Only     │ Hybrid      │
├──────────────────────┼──────────┼──────────┼──────────┼─────────────┤
│ Time to Market (25%) │ ★★☆☆☆   │ ★★★★☆   │ ★★★☆☆   │ ★★★★☆      │
│ Flexibility (20%)    │ ★★★★★   │ ★★★★☆   │ ★★★★☆   │ ★★★★★      │
│ Metering (20%)       │ ★★★☆☆   │ ★★★★★   │ ★★★☆☆   │ ★★★★★      │
│ Maintenance (15%)    │ ★★☆☆☆   │ ★★★★☆   │ ★★★★☆   │ ★★★★☆      │
│ License Risk (10%)   │ ★★★★★   │ ★★★☆☆   │ ★★★★★   │ ★★★☆☆      │
│ Cost (10%)           │ ★★☆☆☆   │ ★★★★☆   │ ★★★★☆   │ ★★★★☆      │
├──────────────────────┼──────────┼──────────┼──────────┼─────────────┤
│ WEIGHTED SCORE       │ 3.05     │ 4.00     │ 3.60     │ 4.30        │
└──────────────────────┴──────────┴──────────┴──────────┴─────────────┘

WINNER: HYBRID APPROACH (Lago for billing engine + Custom modules for PFaaS-specific logic)
RUNNER-UP: Lago standalone (if PFaaS-specific needs are simpler)
```

### 7.2 Recommended Architecture: Hybrid with Lago

```
┌────────────────────────────────────────────────────────────────────────────┐
│                    RECOMMENDED HYBRID ARCHITECTURE                          │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    PFaaS APPLICATION LAYER                           │   │
│  │  Trading Engine │ Challenge System │ Payout System │ API Gateway     │   │
│  └────────┬────────────────┬──────────────────┬────────────┬───────────┘   │
│           │                │                  │            │               │
│           ▼                ▼                  ▼            ▼               │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │              CUSTOM BILLING ORCHESTRATION LAYER                      │   │
│  │                     (Your Custom Code)                                │   │
│  │                                                                       │   │
│  │  ┌─────────────────┐  ┌────────────────────┐  ┌─────────────────┐   │   │
│  │  │  Event Router   │  │  Revenue Share      │  │  Settlement     │   │   │
│  │  │  & Enrichment   │  │  Calculator         │  │  Engine         │   │   │
│  │  │                 │  │                      │  │                 │   │   │
│  │  │ • Map PFaaS     │  │ • Challenge fee %   │  │ • Net billing   │   │   │
│  │  │   events to     │  │ • Tiered rev share  │  │ • Reconcile     │   │   │
│  │  │   Lago metrics  │  │ • Per-tenant rates  │  │ • FX conversion │   │   │
│  │  │ • Enrich with   │  │ • Period aggregation│  │ • Ledger entries│   │   │
│  │  │   tenant context│  │                      │  │                 │   │   │
│  │  └────────┬────────┘  └────────┬───────────┘  └────────┬────────┘   │   │
│  │           │                    │                        │             │   │
│  │  ┌────────┴────────┐  ┌───────┴────────────┐  ┌───────┴─────────┐   │   │
│  │  │ Tenant Config   │  │  Tenant Billing    │  │  Financial       │   │   │
│  │  │ Manager         │  │  Dashboard         │  │  Reports         │   │   │
│  │  │                 │  │                     │  │                  │   │   │
│  │  │ • Plan mapping  │  │ • Usage monitoring  │  │ • MRR/ARR       │   │   │
│  │  │ • Custom pricing│  │ • Invoice history   │  │ • Revenue recog │   │   │
│  │  │ • Overrides     │  │ • Payment methods   │  │ • Tax reports   │   │   │
│  │  └────────┬────────┘  └───────┬────────────┘  └───────┬─────────┘   │   │
│  │           │                    │                        │             │   │
│  └───────────┼────────────────────┼────────────────────────┼─────────────┘   │
│              │                    │                        │                 │
│              ▼                    ▼                        ▼                 │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                          LAGO (Self-Hosted)                          │   │
│  │                    Open Source Billing Engine                         │   │
│  │                                                                       │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │   │
│  │  │ Billable │ │  Plans   │ │ Invoice  │ │ Wallets  │ │ Coupons  │  │   │
│  │  │ Metrics  │ │ & Charges│ │ Engine   │ │ & Credit │ │          │  │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘  │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐                            │   │
│  │  │  Event   │ │ Webhook  │ │  Tax     │                            │   │
│  │  │ Ingestion│ │ System   │ │ Module   │                            │   │
│  │  └──────────┘ └──────────┘ └──────────┘                            │   │
│  └───────────────────────────┬─────────────────────────────────────────┘   │
│                              │                                             │
│                              ▼                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    PAYMENT LAYER                                      │   │
│  │                                                                       │   │
│  │  Option A: Hyperswitch (self-hosted, open source)                    │   │
│  │  Option B: Direct Stripe/Adyen integration via Lago                  │   │
│  │  Option C: Both (Hyperswitch for routing, Lago for orchestration)    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    DATA LAYER                                         │   │
│  │                                                                       │   │
│  │  PostgreSQL     │  Redis           │  Kafka/NATS     │  ClickHouse   │   │
│  │  (Lago DB +     │  (Caching +      │  (Event Stream) │  (Analytics)  │   │
│  │   Custom Tables)│   Rate Limiting) │                  │               │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────────────┘
```

### 7.3 Alternative: Kill Bill Based Architecture

If the AGPL license of Lago is a concern:

```
┌────────────────────────────────────────────────────────────────────┐
│              ALTERNATIVE: KILL BILL + OPENMETER                    │
│                                                                    │
│  ┌──────────────────┐     ┌────────────────────┐                  │
│  │  OpenMeter        │     │   Custom PFaaS     │                  │
│  │  (Metering)       │────▶│   Billing Logic    │                  │
│  │  Apache 2.0       │     │                    │                  │
│  │  Go               │     │  • Revenue Share   │                  │
│  └──────────────────┘     │  • Settlement      │                  │
│                            │  • Tenant Config   │                  │
│  ┌──────────────────┐     │                    │                  │
│  │  Kill Bill         │◀───│                    │                  │
│  │  (Billing Engine)  │     └────────────────────┘                  │
│  │  Apache 2.0       │                                             │
│  │  Java             │     ┌────────────────────┐                  │
│  └──────────────────┘     │  Hyperswitch       │                  │
│           │                │  (Payments)        │                  │
│           └───────────────▶│  Apache 2.0       │                  │
│                            │  Rust              │                  │
│                            └────────────────────┘                  │
│                                                                    │
│  ALL COMPONENTS: Apache 2.0 (No copyleft risk)                    │
│  TRADE-OFF: More integration work, 3 systems to maintain          │
└────────────────────────────────────────────────────────────────────┘
```

---

## 8. Implementation Blueprint

### 8.1 Phase-by-Phase Implementation

```
┌─────────────────────────────────────────────────────────────────┐
│                IMPLEMENTATION PHASES                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  PHASE 1: FOUNDATION (Weeks 1-4)                                │
│  ├── Deploy Lago (Docker/Kubernetes)                            │
│  ├── Configure billable metrics for PFaaS                       │
│  ├── Create initial pricing plans (3 tiers)                     │
│  ├── Integrate Stripe as payment provider                       │
│  ├── Build basic event ingestion pipeline                       │
│  └── Tenant onboarding flow with plan selection                 │
│                                                                  │
│  PHASE 2: METERING (Weeks 5-8)                                  │
│  ├── Integrate trading engine → metering events                 │
│  ├── Integrate challenge system → metering events               │
│  ├── Integrate payout system → metering events                  │
│  ├── Integrate API gateway → metering events                    │
│  ├── Build event enrichment and routing service                 │
│  └── Usage dashboard for tenants                                │
│                                                                  │
│  PHASE 3: REVENUE SHARE & SETTLEMENTS (Weeks 9-12)             │
│  ├── Build revenue share calculation engine                     │
│  ├── Net settlement logic (charges - rev share)                 │
│  ├── Multi-currency FX handling                                 │
│  ├── Settlement reporting and reconciliation                    │
│  └── Financial ledger integration                               │
│                                                                  │
│  PHASE 4: ADVANCED FEATURES (Weeks 13-16)                       │
│  ├── Custom per-tenant pricing overrides                        │
│  ├── Committed use discounts and contracts                      │
│  ├── Advanced dunning and collection                            │
│  ├── Tax integration (TaxJar/Avalara)                           │
│  ├── Tenant self-service billing portal                         │
│  └── Admin billing management dashboard                         │
│                                                                  │
│  PHASE 5: ENTERPRISE (Weeks 17-20)                              │
│  ├── Wire transfer / ACH payment support                        │
│  ├── Purchase order and contract management                     │
│  ├── Revenue recognition reporting (ASC 606)                    │
│  ├── ERP integration (QuickBooks/Xero)                          │
│  ├── Advanced analytics and forecasting                         │
│  └── SOC 2 compliance documentation                             │
│                                                                  │
│  PHASE 6: OPTIMIZATION (Ongoing)                                │
│  ├── Performance optimization for high-volume metering          │
│  ├── Billing accuracy auditing and reconciliation               │
│  ├── A/B testing for pricing plans                              │
│  ├── Churn prediction based on billing patterns                 │
│  └── Cost optimization and margin analysis                      │
│                                                                  │
│  TOTAL ESTIMATED TIMELINE: 16-20 weeks for MVP                  │
│  TEAM: 2-3 backend engineers + 1 frontend engineer              │
└─────────────────────────────────────────────────────────────────┘
```

### 8.2 Custom Code: Revenue Share Engine

```python
# revenue_share_engine.py
# Custom module that sits between PFaaS platform and Lago

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, date
from enum import Enum
from typing import Optional
import uuid


class RevenueShareType(Enum):
    CHALLENGE_FEE = "challenge_fee"
    ADDON_PURCHASE = "addon_purchase"
    REFERRAL = "referral"


class SettlementStatus(Enum):
    PENDING = "pending"
    CALCULATED = "calculated"
    INVOICED = "invoiced"
    SETTLED = "settled"
    DISPUTED = "disputed"


@dataclass
class RevenueShareConfig:
    tenant_id: str
    revenue_type: RevenueShareType
    platform_share_pct: Decimal  # e.g., 0.15 for 15%
    min_platform_share: Optional[Decimal] = None  # minimum per-transaction
    max_platform_share: Optional[Decimal] = None  # cap per-transaction
    tiered_rates: Optional[list] = None  # volume-based tiers


@dataclass
class RevenueShareEvent:
    id: str
    tenant_id: str
    event_type: RevenueShareType
    gross_amount: Decimal
    currency: str
    source_transaction_id: str
    trader_id: Optional[str] = None
    metadata: Optional[dict] = None
    timestamp: datetime = None


@dataclass
class RevenueShareCalculation:
    event_id: str
    tenant_id: str
    gross_amount: Decimal
    platform_share_pct: Decimal
    platform_share_amount: Decimal
    tenant_net_amount: Decimal
    currency: str
    period: str  # "2024-01"


class RevenueShareEngine:
    """
    Calculates platform's share of tenant revenue.
    This is custom logic specific to PFaaS that doesn't exist in Lago.
    """
    
    def __init__(self, db, lago_client):
        self.db = db
        self.lago = lago_client
    
    def get_tenant_share_config(
        self, tenant_id: str, revenue_type: RevenueShareType
    ) -> RevenueShareConfig:
        """Get revenue share configuration for a tenant."""
        config = self.db.query(
            """SELECT * FROM revenue_share_configs 
               WHERE tenant_id = %s AND revenue_type = %s AND active = true""",
            (tenant_id, revenue_type.value)
        )
        
        if not config:
            # Default rates
            defaults = {
                RevenueShareType.CHALLENGE_FEE: Decimal("0.15"),  # 15%
                RevenueShareType.ADDON_PURCHASE: Decimal("0.20"),  # 20%
                RevenueShareType.REFERRAL: Decimal("0.05"),  # 5%
            }
            return RevenueShareConfig(
                tenant_id=tenant_id,
                revenue_type=revenue_type,
                platform_share_pct=defaults.get(revenue_type, Decimal("0.15"))
            )
        
        return RevenueShareConfig(**config)
    
    def calculate_share(
        self, event: RevenueShareEvent
    ) -> RevenueShareCalculation:
        """Calculate platform's share for a single revenue event."""
        
        config = self.get_tenant_share_config(event.tenant_id, event.event_type)
        
        # Check if tiered rates apply (volume-based discounts)
        if config.tiered_rates:
            monthly_volume = self._get_monthly_volume(
                event.tenant_id, event.event_type
            )
            share_pct = self._get_tiered_rate(config.tiered_rates, monthly_volume)
        else:
            share_pct = config.platform_share_pct
        
        platform_share = (event.gross_amount * share_pct).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        
        # Apply min/max caps
        if config.min_platform_share:
            platform_share = max(platform_share, config.min_platform_share)
        if config.max_platform_share:
            platform_share = min(platform_share, config.max_platform_share)
        
        tenant_net = event.gross_amount - platform_share
        
        period = event.timestamp.strftime("%Y-%m")
        
        calculation = RevenueShareCalculation(
            event_id=event.id,
            tenant_id=event.tenant_id,
            gross_amount=event.gross_amount,
            platform_share_pct=share_pct,
            platform_share_amount=platform_share,
            tenant_net_amount=tenant_net,
            currency=event.currency,
            period=period
        )
        
        # Store calculation
        self._store_calculation(calculation)
        
        # Send to Lago as a usage event (for invoice inclusion)
        self._send_to_lago(event, calculation)
        
        return calculation
    
    def _get_tiered_rate(
        self, tiers: list, volume: Decimal
    ) -> Decimal:
        """
        Example tiers:
        [
            {"up_to": 100000, "rate": 0.15},   # First $100K: 15%
            {"up_to": 500000, "rate": 0.12},    # $100K-$500K: 12%
            {"up_to": None, "rate": 0.10}       # $500K+: 10%
        ]
        """
        for tier in tiers:
            if tier["up_to"] is None or volume <= Decimal(str(tier["up_to"])):
                return Decimal(str(tier["rate"]))
        return Decimal(str(tiers[-1]["rate"]))
    
    def _get_monthly_volume(
        self, tenant_id: str, event_type: RevenueShareType
    ) -> Decimal:
        """Get total revenue volume for current month."""
        result = self.db.query(
            """SELECT COALESCE(SUM(gross_amount), 0) as total
               FROM revenue_share_events 
               WHERE tenant_id = %s 
               AND event_type = %s
               AND timestamp >= date_trunc('month', CURRENT_DATE)""",
            (tenant_id, event_type.value)
        )
        return Decimal(str(result['total']))
    
    def _send_to_lago(
        self, event: RevenueShareEvent, calc: RevenueShareCalculation
    ):
        """Send revenue share as a Lago usage event for invoicing."""
        self.lago.events.create({
            "transaction_id": f"revshare_{event.id}",
            "external_customer_id": event.tenant_id,
            "code": "challenge_revenue_share",  # Lago billable metric
            "timestamp": int(event.timestamp.timestamp()),
            "properties": {
                "amount": str(calc.platform_share_amount),
                "gross_revenue": str(event.gross_amount),
                "share_pct": str(calc.platform_share_pct),
            }
        })
    
    def _store_calculation(self, calc: RevenueShareCalculation):
        """Persist calculation for audit trail."""
        self.db.execute(
            """INSERT INTO revenue_share_calculations 
               (event_id, tenant_id, gross_amount, platform_share_pct,
                platform_share_amount, tenant_net_amount, currency, period)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (calc.event_id, calc.tenant_id, calc.gross_amount,
             calc.platform_share_pct, calc.platform_share_amount,
             calc.tenant_net_amount, calc.currency, calc.period)
        )
    
    def generate_settlement_report(
        self, tenant_id: str, period: str
    ) -> dict:
        """
        Generate net settlement report for a tenant.
        Net = Platform charges TO tenant - Revenue share FROM tenant's earnings
        """
        # Get platform charges (from Lago invoice)
        invoices = self.lago.invoices.find_all(
            external_customer_id=tenant_id,
            issuing_date_from=f"{period}-01",
            issuing_date_to=f"{period}-31"
        )
        total_platform_charges = sum(
            Decimal(inv.total_amount_cents) / 100 for inv in invoices
        )
        
        # Get revenue share owed by platform to tenant
        # (tenant's net from challenge fees, etc.)
        rev_share = self.db.query(
            """SELECT 
                SUM(platform_share_amount) as total_platform_share,
                SUM(tenant_net_amount) as total_tenant_net,
                SUM(gross_amount) as total_gross
               FROM revenue_share_calculations
               WHERE tenant_id = %s AND period = %s""",
            (tenant_id, period)
        )
        
        platform_share_revenue = Decimal(str(rev_share['total_platform_share'] or 0))
        
        # Net settlement
        # Positive = tenant owes platform
        # Negative = platform owes tenant  
        net_amount = total_platform_charges - platform_share_revenue
        
        return {
            "tenant_id": tenant_id,
            "period": period,
            "platform_charges": float(total_platform_charges),
            "platform_revenue_share": float(platform_share_revenue),
            "tenant_gross_revenue": float(rev_share['total_gross'] or 0),
            "tenant_net_revenue": float(rev_share['total_tenant_net'] or 0),
            "net_settlement": float(net_amount),
            "settlement_direction": "tenant_pays" if net_amount > 0 else "platform_pays"
        }
```

### 8.3 Custom Code: Event Ingestion Pipeline

```python
# event_pipeline.py
# Routes PFaaS domain events to Lago metering

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import json
import hashlib


class EventRouter:
    """
    Consumes domain events from Kafka/NATS and routes them 
    to Lago as billable usage events.
    """
    
    # Mapping of domain events to Lago billable metric codes
    EVENT_METRIC_MAP = {
        "trade.executed": {
            "metric_code": "trading_volume_lots",
            "quantity_field": "lots",
            "properties": ["symbol", "trader_id", "account_type"]
        },
        "trader.login": {
            "metric_code": "active_traders",
            "quantity_field": None,  # unique count by trader_id
            "properties": ["trader_id"]
        },
        "challenge.purchased": {
            "metric_code": "challenge_purchases",
            "quantity_field": "amount",
            "properties": ["challenge_type", "trader_id", "amount", "currency"]
        },
        "payout.completed": {
            "metric_code": "payouts_processed",
            "quantity_field": None,  # count
            "properties": ["amount", "currency", "payment_method", "trader_id"]
        },
        "api.request": {
            "metric_code": "api_calls",
            "quantity_field": None,  # count
            "properties": ["endpoint", "method", "status_code"]
        },
        "funded_account.activated": {
            "metric_code": "funded_accounts",
            "quantity_field": None,
            "properties": ["account_id", "trader_id", "account_size"]
        },
        "market_data.subscription": {
            "metric_code": "market_data_users",
            "quantity_field": None,
            "properties": ["trader_id", "data_tier"]
        }
    }
    
    def __init__(self, lago_client, revenue_share_engine, redis_client):
        self.lago = lago_client
        self.rev_share = revenue_share_engine
        self.redis = redis_client
    
    async def process_event(self, raw_event: dict):
        """Process a single domain event."""
        
        event_type = raw_event.get("type")
        tenant_id = raw_event.get("tenant_id")
        
        if not event_type or not tenant_id:
            return
        
        # Check idempotency
        idempotency_key = self._generate_idempotency_key(raw_event)
        if await self._is_duplicate(idempotency_key):
            return
        
        # Route to appropriate handler
        if event_type in self.EVENT_METRIC_MAP:
            await self._send_to_lago(raw_event, idempotency_key)
        
        # Special handling for revenue-generating events
        if event_type == "challenge.purchased":
            await self._process_revenue_share(raw_event)
        
        # Mark as processed
        await self._mark_processed(idempotency_key)
    
    async def _send_to_lago(self, event: dict, idempotency_key: str):
        """Transform and send event to Lago."""
        
        mapping = self.EVENT_METRIC_MAP[event["type"]]
        
        properties = {}
        for prop in mapping["properties"]:
            if prop in event.get("data", {}):
                properties[prop] = str(event["data"][prop])
        
        lago_event = {
            "transaction_id": idempotency_key,
            "external_customer_id": event["tenant_id"],
            "code": mapping["metric_code"],
            "timestamp": int(
                datetime.fromisoformat(event["timestamp"]).timestamp()
            ),
            "properties": properties
        }
        
        await self.lago.events.create_async(lago_event)
    
    async def _process_revenue_share(self, event: dict):
        """Handle revenue share for challenge purchases."""
        from revenue_share_engine import RevenueShareEvent, RevenueShareType
        from decimal import Decimal
        
        rev_event = RevenueShareEvent(
            id=str(event.get("event_id", uuid.uuid4())),
            tenant_id=event["tenant_id"],
            event_type=RevenueShareType.CHALLENGE_FEE,
            gross_amount=Decimal(str(event["data"]["amount"])),
            currency=event["data"].get("currency", "USD"),
            source_transaction_id=event["data"].get("transaction_id", ""),
            trader_id=event["data"].get("trader_id"),
            timestamp=datetime.fromisoformat(event["timestamp"])
        )
        
        self.rev_share.calculate_share(rev_event)
    
    def _generate_idempotency_key(self, event: dict) -> str:
        """Generate deterministic idempotency key."""
        if "idempotency_key" in event:
            return event["idempotency_key"]
        
        key_data = f"{event['type']}:{event['tenant_id']}:{event.get('event_id', '')}:{event['timestamp']}"
        return hashlib.sha256(key_data.encode()).hexdigest()
    
    async def _is_duplicate(self, key: str) -> bool:
        """Check if event was already processed."""
        return await self.redis.exists(f"billing:event:{key}")
    
    async def _mark_processed(self, key: str):
        """Mark event as processed with 7-day TTL."""
        await self.redis.setex(f"billing:event:{key}", 7 * 86400, "1")
```

### 8.4 Infrastructure Setup (Docker Compose)

```yaml
# docker-compose.billing.yml
version: '3.8'

services:
  # ============================================
  # LAGO - Billing Engine
  # ============================================
  lago-api:
    image: getlago/api:v0.52.0
    container_name: lago-api
    restart: unless-stopped
    depends_on:
      lago-db:
        condition: service_healthy
      lago-redis:
        condition: service_healthy
    environment:
      - LAGO_API_URL=https://billing-api.yourplatform.com
      - DATABASE_URL=postgresql://lago:lago_password@lago-db:5432/lago
      - REDIS_URL=redis://lago-redis:6379
      - RAILS_ENV=production
      - SECRET_KEY_BASE=${LAGO_SECRET_KEY}
      - LAGO_RSA_PRIVATE_KEY=${LAGO_RSA_PRIVATE_KEY}
      - ENCRYPTION_PRIMARY_KEY=${LAGO_ENCRYPTION_PRIMARY_KEY}
      - ENCRYPTION_DETERMINISTIC_KEY=${LAGO_ENCRYPTION_DETERMINISTIC_KEY}
      - ENCRYPTION_KEY_DERIVATION_SALT=${LAGO_KEY_DERIVATION_SALT}
      # Stripe integration
      - LAGO_STRIPE_API_KEY=${STRIPE_SECRET_KEY}
      # Webhook
      - LAGO_WEBHOOK_URL=https://api.yourplatform.com/billing/webhooks/lago
    ports:
      - "3000:3000"
    networks:
      - billing-network
    volumes:
      - lago-storage:/app/storage

  lago-worker:
    image: getlago/api:v0.52.0
    container_name: lago-worker
    restart: unless-stopped
    depends_on:
      - lago-api
    command: ["./scripts/start.worker.sh"]
    environment:
      - DATABASE_URL=postgresql://lago:lago_password@lago-db:5432/lago
      - REDIS_URL=redis://lago-redis:6379
      - RAILS_ENV=production
      - SECRET_KEY_BASE=${LAGO_SECRET_KEY}
    networks:
      - billing-network

  lago-clock:
    image: getlago/api:v0.52.0
    container_name: lago-clock
    restart: unless-stopped
    depends_on:
      - lago-api
    command: ["./scripts/start.clock.sh"]
    environment:
      - DATABASE_URL=postgresql://lago:lago_password@lago-db:5432/lago
      - REDIS_URL=redis://lago-redis:6379
      - RAILS_ENV=production
      - SECRET_KEY_BASE=${LAGO_SECRET_KEY}
    networks:
      - billing-network

  lago-front:
    image: getlago/front:v0.52.0
    container_name: lago-front
    restart: unless-stopped
    depends_on:
      - lago-api
    environment:
      - API_URL=https://billing-api.yourplatform.com
      - LAGO_DISABLE_SIGNUP=true
    ports:
      - "8080:80"
    networks:
      - billing-network

  lago-db:
    image: postgres:15-alpine
    container_name: lago-db
    restart: unless-stopped
    environment:
      POSTGRES_USER: lago
      POSTGRES_PASSWORD: lago_password
      POSTGRES_DB: lago
    volumes:
      - lago-db-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U lago"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - billing-network

  lago-redis:
    image: redis:7-alpine
    container_name: lago-redis
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - billing-network

  # ============================================
  # CUSTOM BILLING SERVICES
  # ============================================
  billing-orchestrator:
    build:
      context: ./services/billing-orchestrator
      dockerfile: Dockerfile
    container_name: billing-orchestrator
    restart: unless-stopped
    depends_on:
      - lago-api
      - billing-db
      - kafka
    environment:
      - LAGO_API_URL=http://lago-api:3000
      - LAGO_API_KEY=${LAGO_API_KEY}
      - DATABASE_URL=postgresql://billing:billing_pass@billing-db:5432/billing_custom
      - KAFKA_BROKERS=kafka:9092
      - REDIS_URL=redis://lago-redis:6379
    ports:
      - "8001:8001"
    networks:
      - billing-network

  revenue-share-engine:
    build:
      context: ./services/revenue-share-engine
      dockerfile: Dockerfile
    container_name: revenue-share-engine
    restart: unless-stopped
    depends_on:
      - billing-db
      - lago-api
    environment:
      - LAGO_API_URL=http://lago-api:3000
      - LAGO_API_KEY=${LAGO_API_KEY}
      - DATABASE_URL=postgresql://billing:billing_pass@billing-db:5432/billing_custom
    ports:
      - "8002:8002"
    networks:
      - billing-network

  settlement-service:
    build:
      context: ./services/settlement-service
      dockerfile: Dockerfile
    container_name: settlement-service
    restart: unless-stopped
    depends_on:
      - billing-db
      - lago-api
    environment:
      - LAGO_API_URL=http://lago-api:3000
      - LAGO_API_KEY=${LAGO_API_KEY}
      - DATABASE_URL=postgresql://billing:billing_pass@billing-db:5432/billing_custom
    ports:
      - "8003:8003"
    networks:
      - billing-network

  billing-db:
    image: postgres:15-alpine
    container_name: billing-db
    restart: unless-stopped
    environment:
      POSTGRES_USER: billing
      POSTGRES_PASSWORD: billing_pass
      POSTGRES_DB: billing_custom
    volumes:
      - billing-db-data:/var/lib/postgresql/data
      - ./migrations:/docker-entrypoint-initdb.d
    networks:
      - billing-network

  # ============================================
  # EVENT STREAMING
  # ============================================
  kafka:
    image: confluentinc/cp-kafka:7.5.0
    container_name: kafka
    environment:
      KAFKA_NODE_ID: 1
      KAFKA_PROCESS_ROLES: broker,controller
      KAFKA_LISTENERS: PLAINTEXT://0.0.0.0:9092,CONTROLLER://0.0.0.0:9093
      KAFKA_CONTROLLER_QUORUM_VOTERS: 1@kafka:9093
      KAFKA_CONTROLLER_LISTENER_NAMES: CONTROLLER
      CLUSTER_ID: 'billing-cluster-001'
    volumes:
      - kafka-data:/var/lib/kafka/data
    networks:
      - billing-network

volumes:
  lago-db-data:
  lago-storage:
  billing-db-data:
  kafka-data:

networks:
  billing-network:
    driver: bridge
```

### 8.5 Pricing Plan Configuration

```typescript
// pricing-plans.ts
// Configuration for PFaaS pricing tiers

interface PFaaSPlan {
  name: string;
  code: string;
  basePrice: number;
  interval: 'monthly' | 'annual';
  includedLimits: {
    traders: number;
    fundedAccounts: number;
    apiCalls: number;
    tradingLotsPerMonth: number;
    payoutsPerMonth: number;
  };
  features: {
    whiteLabel: boolean;
    customDomain: boolean;
    apiAccess: boolean;
    advancedAnalytics: boolean;
    prioritySupport: boolean;
    customRiskRules: boolean;
    multiAssetClass: boolean;
    copyTrading: boolean;
  };
  overageRates: {
    perAdditionalTrader: number;
    perAdditionalFundedAccount: number;
    perAdditionalApiCall: number; // per 1000
    perAdditionalLot: number;
    perPayout: number;
    challengeRevenueSharePct: number;
  };
}

const PRICING_PLANS: PFaaSPlan[] = [
  {
    name: "Starter",
    code: "starter",
    basePrice: 499,
    interval: "monthly",
    includedLimits: {
      traders: 500,
      fundedAccounts: 50,
      apiCalls: 100_000,
      tradingLotsPerMonth: 10_000,
      payoutsPerMonth: 100,
    },
    features: {
      whiteLabel: false,
      customDomain: true,
      apiAccess: true,
      advancedAnalytics: false,
      prioritySupport: false,
      customRiskRules: false,
      multiAssetClass: false,
      copyTrading: false,
    },
    overageRates: {
      perAdditionalTrader: 0.75,
      perAdditionalFundedAccount: 5.00,
      perAdditionalApiCall: 0.50, // per 1000
      perAdditionalLot: 0.10,
      perPayout: 3.00,
      challengeRevenueSharePct: 0.20, // 20%
    },
  },
  {
    name: "Growth",
    code: "growth",
    basePrice: 1_999,
    interval: "monthly",
    includedLimits: {
      traders: 5_000,
      fundedAccounts: 500,
      apiCalls: 1_000_000,
      tradingLotsPerMonth: 100_000,
      payoutsPerMonth: 1_000,
    },
    features: {
      whiteLabel: true,
      customDomain: true,
      apiAccess: true,
      advancedAnalytics: true,
      prioritySupport: true,
      customRiskRules: true,
      multiAssetClass: true,
      copyTrading: false,
    },
    overageRates: {
      perAdditionalTrader: 0.50,
      perAdditionalFundedAccount: 3.50,
      perAdditionalApiCall: 0.30,
      perAdditionalLot: 0.05,
      perPayout: 2.00,
      challengeRevenueSharePct: 0.15, // 15%
    },
  },
  {
    name: "Enterprise",
    code: "enterprise",
    basePrice: 7_999,
    interval: "monthly",
    includedLimits: {
      traders: 50_000,
      fundedAccounts: 5_000,
      apiCalls: 10_000_000,
      tradingLotsPerMonth: 1_000_000,
      payoutsPerMonth: 10_000,
    },
    features: {
      whiteLabel: true,
      customDomain: true,
      apiAccess: true,
      advancedAnalytics: true,
      prioritySupport: true,
      customRiskRules: true,
      multiAssetClass: true,
      copyTrading: true,
    },
    overageRates: {
      perAdditionalTrader: 0.25,
      perAdditionalFundedAccount: 2.00,
      perAdditionalApiCall: 0.10,
      perAdditionalLot: 0.02,
      perPayout: 1.00,
      challengeRevenueSharePct: 0.10, // 10%
    },
  },
];
```

### 8.6 Cost Analysis: Build vs. Open-Source vs. Commercial

```
┌──────────────────────────────────────────────────────────────────────┐
│                    TOTAL COST OF OWNERSHIP (2 YEARS)                  │
├──────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  OPTION 1: BUILD FROM SCRATCH                                        │
│  ├── Development: 6 months × 3 engineers × $12K/mo = $216,000       │
│  ├── Ongoing maintenance: 1.5 engineers × $12K/mo × 18mo = $324,000 │
│  ├── Infrastructure: $2,000/mo × 24 = $48,000                       │
│  ├── Payment processing: Pass-through                                │
│  ├── Testing/QA/Security: $50,000                                    │
│  └── TOTAL: ~$638,000                                                │
│                                                                       │
│  OPTION 2: LAGO HYBRID (RECOMMENDED)                                 │
│  ├── Lago setup + customization: 4 months × 2 eng × $12K = $96,000  │
│  ├── Custom modules (rev share, settlement): $48,000                 │
│  ├── Ongoing maintenance: 0.5 engineer × $12K × 20mo = $120,000     │
│  ├── Lago commercial license (optional): $0-$2,000/mo               │
│  ├── Infrastructure: $1,500/mo × 24 = $36,000                       │
│  └── TOTAL: ~$300,000 - $348,000                                    │
│                                                                       │
│  OPTION 3: KILL BILL HYBRID                                          │
│  ├── Kill Bill setup + plugins: 5 months × 2 eng × $12K = $120,000  │
│  ├── Custom modules: $60,000                                         │
│  ├── Ongoing maintenance: 0.75 engineer × $12K × 19mo = $171,000    │
│  ├── Infrastructure (Java = heavier): $2,000/mo × 24 = $48,000      │
│  └── TOTAL: ~$399,000                                                │
│                                                                       │
│  OPTION 4: STRIPE BILLING (COMMERCIAL)                               │
│  ├── Integration: 2 months × 2 engineers × $12K = $48,000           │
│  ├── Custom modules (still needed): $60,000                          │
│  ├── Stripe fees: 0.5% of billing volume                             │
│  │   (If billing $500K/mo to tenants: $2,500/mo × 24 = $60,000)     │
│  ├── Ongoing maintenance: 0.5 eng × $12K × 22mo = $132,000          │
│  └── TOTAL: ~$300,000 + variable (scales with revenue)               │
│                                                                       │
│  ════════════════════════════════════════════════════════════         │
│  WINNER: LAGO HYBRID at ~$300K-$348K                                 │
│  • 53% cheaper than building from scratch                             │
│  • More flexible than pure commercial (Stripe)                       │
│  • Better metering than Kill Bill                                     │
│  • No variable cost scaling (unlike Stripe)                          │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Final Recommendation Summary

```
┌──────────────────────────────────────────────────────────────────────┐
│                    FINAL RECOMMENDATION                               │
├──────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  PRIMARY RECOMMENDATION: LAGO + Custom PFaaS Modules                │
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────┐     │
│  │  LAGO handles:              │  CUSTOM CODE handles:         │     │
│  │  ✅ Subscription management │  ✅ Revenue share calc        │     │
│  │  ✅ Usage metering          │  ✅ Settlement/reconciliation │     │
│  │  ✅ Invoice generation      │  ✅ Event routing/enrichment  │     │
│  │  ✅ Payment collection      │  ✅ Tenant config overrides   │     │
│  │  ✅ Wallet/credits          │  ✅ Financial reporting       │     │
│  │  ✅ Webhooks                │  ✅ Tenant billing dashboard  │     │
│  │  ✅ Tax calculation         │  ✅ Multi-currency settlement │     │
│  │  ✅ Dunning                 │  ✅ Domain-specific analytics │     │
│  └─────────────────────────────────────────────────────────────┘     │
│                                                                       │
│  ALTERNATIVE (if AGPL is a concern):                                 │
│  Kill Bill + OpenMeter + Custom Code (all Apache 2.0)               │
│                                                                       │
│  KEY DECISIONS:                                                       │
│  1. License: Evaluate AGPL-3.0 impact on your business              │
│     → If SaaS-only (no on-prem): Lago AGPL may be acceptable       │
│     → If concerned: Use Kill Bill or buy Lago commercial license     │
│  2. Payment Provider: Start with Stripe, add Adyen/Wise later       │
│  3. Start Simple: Launch with flat subscription + 2-3 usage metrics  │
│     → Add complexity as tenant base grows                            │
│  4. Build revenue share engine from Day 1 (it's your core IP)       │
│                                                                       │
│  TIMELINE: 16-20 weeks to production-ready MVP                       │
│  TEAM: 2 backend + 1 frontend + 0.5 DevOps                         │
│  BUDGET: $300,000-$350,000 for first 2 years                        │
└──────────────────────────────────────────────────────────────────────┘
```

---

This research provides a comprehensive foundation for making an informed decision. The key insight is that **no single open-source solution solves 100% of the PFaaS billing problem** — the revenue share calculations, settlement logic, and prop-firm-specific metering will always require custom code. The goal is to **minimize** that custom code by leveraging an open-source billing engine for the 60-70% of standard billing functionality.
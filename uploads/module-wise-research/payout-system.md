# Comprehensive Research: Enterprise-Grade Payout System Engine for a Prop Firm as a Service Platform

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Understanding the Domain](#understanding-the-domain)
3. [System Architecture Overview](#system-architecture-overview)
4. [Core Components Deep Dive](#core-components-deep-dive)
5. [Open-Source Solutions & Building Blocks](#open-source-solutions)
6. [Recommended Architecture with Open-Source Stack](#recommended-architecture)
7. [Detailed Component Implementation](#detailed-component-implementation)
8. [Data Models](#data-models)
9. [Security & Compliance](#security-compliance)
10. [Scalability & Reliability Patterns](#scalability-reliability)
11. [Technology Stack Recommendation](#technology-stack)
12. [Build vs Buy Analysis](#build-vs-buy)
13. [Implementation Roadmap](#implementation-roadmap)

---

## 1. Executive Summary

A Prop Firm as a Service (PFaaS) platform requires a sophisticated payout system that handles:

- **Profit-split calculations** based on complex, multi-tier rules
- **Multi-currency disbursements** to global traders
- **Compliance & KYC/AML** requirements across jurisdictions
- **Real-time tracking** of trading performance and payout eligibility
- **Scalable payment processing** across multiple payment rails (bank transfer, crypto, e-wallets)
- **Audit trails** and reconciliation
- **White-label support** (since it's a platform serving multiple prop firms)

The good news: **you do NOT need to build everything from scratch**. There is a rich ecosystem of open-source tools that can serve as reliable building blocks.

---

## 2. Understanding the Domain

### What Makes Prop Firm Payouts Unique

```
┌─────────────────────────────────────────────────────────────────┐
│                    PROP FIRM PAYOUT LIFECYCLE                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Trader Signs Up → Challenge Phase → Funded Account →            │
│  Trading Activity → Profit Calculation → Payout Request →        │
│  Eligibility Check → Approval Workflow → Payment Execution →     │
│  Reconciliation → Tax Reporting                                   │
│                                                                   │
├─────────────────────────────────────────────────────────────────┤
│  COMPLEXITY FACTORS:                                              │
│  • Multiple profit-split models (70/30, 80/20, 90/10)           │
│  • Scaling plans (increased splits based on consistency)          │
│  • Drawdown rules affecting payout eligibility                   │
│  • Multi-phase challenges with different rules                   │
│  • Payout frequency rules (bi-weekly, monthly, on-demand)        │
│  • Multiple white-label firms with different configurations      │
│  • Multi-currency with FX conversion                             │
│  • Global compliance (different rules per jurisdiction)           │
└─────────────────────────────────────────────────────────────────┘
```

### Key Business Rules

| Rule Category | Examples |
|--------------|----------|
| **Profit Split** | 80/20 default, scaling to 90/10 after 3 consecutive profitable months |
| **Minimum Payout** | $50-$100 minimum withdrawal threshold |
| **Payout Windows** | Bi-weekly cycles, 14-day holding period for first payout |
| **Drawdown Guards** | No payout if account is in drawdown violation |
| **Consistency Rules** | No single trade can account for >30% of total profit |
| **Fee Deductions** | Platform fees, payment processing fees, currency conversion |
| **Tax Withholding** | Varies by jurisdiction (1099 for US contractors, etc.) |

---

## 3. System Architecture Overview

### High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                        API GATEWAY / BFF LAYER                        │
│                   (Kong / Traefik / Custom Gateway)                    │
├──────────┬──────────┬──────────┬──────────┬──────────┬───────────────┤
│          │          │          │          │          │               │
│  Trader  │  Admin   │  Firm    │ Payment  │ Reporting│  Webhook      │
│  Portal  │  Portal  │  Portal  │ Provider │  Module  │  Handlers     │
│  API     │  API     │  API     │  Callbacks│         │               │
│          │          │          │          │          │               │
├──────────┴──────────┴──────────┴──────────┴──────────┴───────────────┤
│                                                                        │
│                     ┌─────────────────────┐                           │
│                     │   EVENT BUS /        │                           │
│                     │   MESSAGE BROKER     │                           │
│                     │   (Apache Kafka /    │                           │
│                     │    RabbitMQ / NATS)  │                           │
│                     └──────────┬──────────┘                           │
│                                │                                       │
│  ┌──────────────┬──────────────┼──────────────┬──────────────┐       │
│  │              │              │              │              │       │
│  ▼              ▼              ▼              ▼              ▼       │
│ ┌────────┐ ┌─────────┐ ┌──────────┐ ┌─────────┐ ┌──────────┐      │
│ │Payout  │ │Profit   │ │Payment   │ │Ledger / │ │Compliance│      │
│ │Engine  │ │Calc     │ │Gateway   │ │Accounting│ │& KYC     │      │
│ │Service │ │Engine   │ │Service   │ │Service  │ │Service   │      │
│ └────────┘ └─────────┘ └──────────┘ └─────────┘ └──────────┘      │
│  ┌────────┐ ┌─────────┐ ┌──────────┐ ┌─────────┐ ┌──────────┐      │
│  │Approval│ │Scheduling│ │Notification│ │Reporting│ │Audit     │      │
│  │Workflow│ │Service  │ │Service   │ │& Analytics│ │Trail     │      │
│  │Service │ │         │ │          │ │Service  │ │Service   │      │
│  └────────┘ └─────────┘ └──────────┘ └─────────┘ └──────────┘      │
│                                                                        │
├────────────────────────────────────────────────────────────────────────┤
│                         DATA LAYER                                     │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│  │PostgreSQL│ │ Redis    │ │TimescaleDB│ │S3/MinIO  │ │Elasticsearch│
│  │(Primary) │ │(Cache +  │ │(Time-     │ │(Documents│ │(Search +  │  │
│  │          │ │ Locks)   │ │ series)   │ │& Reports)│ │ Logs)     │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘  │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Core Components Deep Dive

### Component 1: Payout Engine (Orchestrator)

This is the **brain** of the system — it orchestrates the entire payout lifecycle.

```
┌─────────────────────────────────────────────────────────┐
│                    PAYOUT ENGINE                         │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌─────────────────────────────────────────────┐        │
│  │           STATE MACHINE                      │        │
│  │                                               │        │
│  │  REQUESTED → VALIDATING → CALCULATING →      │        │
│  │  PENDING_APPROVAL → APPROVED → PROCESSING →  │        │
│  │  SENT → CONFIRMED → COMPLETED                │        │
│  │                                               │        │
│  │  Error States: REJECTED, FAILED, REVERSED,   │        │
│  │  ON_HOLD, CANCELLED                           │        │
│  └─────────────────────────────────────────────┘        │
│                                                          │
│  Responsibilities:                                       │
│  • Payout request ingestion & validation                │
│  • Orchestrate profit calculation                       │
│  • Trigger eligibility checks                           │
│  • Manage approval workflows                            │
│  • Dispatch to payment gateway                          │
│  • Handle retries and failure recovery                  │
│  • Emit events for audit trail                          │
│  • Idempotency guarantees                               │
└─────────────────────────────────────────────────────────┘
```

### Component 2: Profit Calculation Engine

```
┌─────────────────────────────────────────────────────────┐
│              PROFIT CALCULATION ENGINE                    │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Inputs:                                                 │
│  • Trading account balance/equity snapshots             │
│  • Trade history (from MT4/MT5/cTrader)                 │
│  • Account configuration (challenge type, phase)        │
│  • Firm-specific profit split rules                     │
│  • Previous payout history                              │
│  • Fee schedules                                        │
│                                                          │
│  Calculations:                                           │
│  1. Gross Profit = Current Equity - High Water Mark     │
│  2. Apply consistency rules (filter outsized trades)    │
│  3. Net Profit = Gross Profit - Fees - Previous Payouts │
│  4. Trader Share = Net Profit × Split Ratio             │
│  5. Apply minimum thresholds                            │
│  6. Apply tax withholding (if applicable)               │
│  7. Currency conversion (if payout currency differs)    │
│  8. Final Payout Amount                                  │
│                                                          │
│  Key Features:                                           │
│  • Configurable rules per firm (white-label)            │
│  • Rule versioning (rules change over time)             │
│  • Audit trail for every calculation step               │
│  • Deterministic & reproducible calculations            │
│  • Support for high water mark tracking                 │
└─────────────────────────────────────────────────────────┘
```

### Component 3: Payment Gateway Abstraction

```
┌─────────────────────────────────────────────────────────┐
│              PAYMENT GATEWAY SERVICE                     │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌───────────────────────────────────────────┐          │
│  │         PAYMENT PROVIDER ADAPTER          │          │
│  │              (Strategy Pattern)            │          │
│  ├───────────┬───────────┬───────────────────┤          │
│  │           │           │                   │          │
│  │  Bank     │  Crypto   │  E-Wallet         │          │
│  │  Transfer │  Payments │  Providers        │          │
│  │           │           │                   │          │
│  │ • SWIFT   │ • BTC     │ • PayPal          │          │
│  │ • SEPA    │ • USDT    │ • Skrill          │          │
│  │ • ACH     │ • USDC    │ • Neteller        │          │
│  │ • Wise    │ • ETH     │ • PaySend         │          │
│  │ • Payoneer│ •(via     │ • Perfect Money   │          │
│  │ • Rise   │  Fireblocks│                   │          │
│  │ • AirWallex│  /Circle)│                   │          │
│  └───────────┴───────────┴───────────────────┘          │
│                                                          │
│  Features:                                               │
│  • Unified interface for all payment methods            │
│  • Provider health monitoring & failover                │
│  • Rate limiting per provider                           │
│  • Fee calculation per payment method                   │
│  • Webhook handler for async payment status             │
│  • Retry with exponential backoff                       │
│  • Circuit breaker pattern                              │
└─────────────────────────────────────────────────────────┘
```

### Component 4: Double-Entry Ledger / Accounting

```
┌─────────────────────────────────────────────────────────┐
│             LEDGER / ACCOUNTING SERVICE                   │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Double-Entry Bookkeeping:                               │
│                                                          │
│  Every payout creates journal entries:                   │
│                                                          │
│  DEBIT:  Trader Profit Account        $8,000            │
│  CREDIT: Payout Payable Account       $8,000            │
│                                                          │
│  DEBIT:  Payout Payable Account       $8,000            │
│  CREDIT: Bank/Crypto Outflow Account  $7,950            │
│  CREDIT: Payment Fee Account          $50               │
│                                                          │
│  Account Types:                                          │
│  • Trader Profit Accounts (per trader, per funded acct) │
│  • Platform Fee Accounts                                │
│  • Firm Revenue Accounts (per white-label firm)         │
│  • Payment Processing Fee Accounts                      │
│  • Tax Withholding Accounts                             │
│  • Suspense Accounts (for pending transactions)         │
│  • FX Gain/Loss Accounts                                │
│                                                          │
│  Key Properties:                                         │
│  • Immutable entries (append-only)                      │
│  • Always balanced (debits = credits)                   │
│  • Full audit trail                                     │
│  • Point-in-time balance queries                        │
└─────────────────────────────────────────────────────────┘
```

### Component 5: Approval Workflow Engine

```
┌─────────────────────────────────────────────────────────┐
│              APPROVAL WORKFLOW ENGINE                     │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Configurable per firm:                                  │
│                                                          │
│  Rule-Based Auto-Approval:                               │
│  • Amount < $500 → Auto-approve                         │
│  • Trader has 3+ successful payouts → Auto-approve      │
│  • KYC verified & no flags → Auto-approve               │
│                                                          │
│  Manual Review Triggers:                                 │
│  • First payout ever → Manager review                   │
│  • Amount > $10,000 → Senior manager + compliance       │
│  • Account flagged for suspicious activity → Compliance │
│  • Trader from high-risk jurisdiction → Enhanced review │
│                                                          │
│  Multi-Level Approval:                                   │
│  • Level 1: Operations team                             │
│  • Level 2: Finance manager                             │
│  • Level 3: Compliance officer                          │
│  • Level 4: C-level (for amounts > $50K)                │
│                                                          │
│  SLA Tracking:                                           │
│  • Escalation if not reviewed within 24h                │
│  • Notification chains                                  │
│  • Approval/rejection audit trail                       │
└─────────────────────────────────────────────────────────┘
```

---

## 5. Open-Source Solutions & Building Blocks

### This is the most critical section — what you can leverage instead of building from scratch.

---

### 5.1 Ledger & Accounting Systems

#### **Hledger / Plain Text Accounting**
- **What**: Double-entry accounting engine
- **Use**: Can serve as inspiration for ledger design, but not suitable for production at scale

#### **Medici (by Interledger)**
- **Repo**: https://github.com/flash-oss/medici
- **What**: Double-entry accounting ledger for Node.js backed by MongoDB
- **Use**: Direct integration for ledger functionality
- **Pros**: Battle-tested, supports multi-currency, journal entries, balance queries
- **Cons**: MongoDB-based (you might prefer PostgreSQL)

#### ⭐ **TigerBeetle**
- **Repo**: https://github.com/tigerbeetle/tigerbeetle
- **What**: Financial accounting database designed for mission-critical safety and performance
- **Use**: **Primary ledger database** — purpose-built for exactly this use case
- **Pros**: 
  - Designed for financial transactions
  - ACID guarantees
  - Handles millions of transactions per second
  - Built-in double-entry accounting
  - Designed to prevent balance inconsistencies
  - Client libraries for multiple languages
- **Cons**: Newer project, smaller community
- **Verdict**: **STRONGLY RECOMMENDED** as the core ledger

#### ⭐ **Hyn's Laravel Wallet / Bavix Wallet**
- If using PHP/Laravel ecosystem

#### ⭐ **Blnk Finance**
- **Repo**: https://github.com/blnkfinance/blnk
- **What**: Open-source financial ledger for building fintech products
- **Use**: Complete ledger solution with balance tracking, multi-currency support
- **Pros**: Built specifically for fintech, REST API, supports multiple currencies, transaction metadata
- **Verdict**: **STRONGLY RECOMMENDED** — very relevant to this use case

---

### 5.2 Workflow / Orchestration Engines

#### ⭐ **Temporal.io**
- **Repo**: https://github.com/temporalio/temporal
- **What**: Durable execution engine for workflows
- **Use**: **Orchestrate the entire payout lifecycle as a workflow**
- **Pros**:
  - Handles long-running processes (payouts can take days)
  - Built-in retry logic with backoff
  - State persistence (survives crashes)
  - Saga pattern support (for rollbacks)
  - Timer/scheduling support
  - Visibility & debugging tools
  - SDKs for Go, Java, TypeScript, Python, .NET
- **Why it's perfect for payouts**:
  - Payout request → Validation → Calculation → Approval → Payment → Confirmation
  - Each step can fail and be retried independently
  - Approval can take hours/days (human-in-the-loop)
  - Payment callbacks are inherently async
- **Verdict**: **ESSENTIAL** — This should be the backbone of your payout orchestration

#### **Conductor (Netflix)**
- **Repo**: https://github.com/conductor-oss/conductor
- **What**: Microservices orchestration engine
- **Use**: Alternative to Temporal for workflow orchestration
- **Pros**: JSON-based workflow definitions, UI, well-documented

#### **Prefect**
- More data-pipeline focused, less suitable for transaction workflows

#### **Apache Airflow**
- Better for batch processing/ETL, not ideal for real-time payout workflows

---

### 5.3 Rules Engine (For Profit Split & Eligibility Rules)

#### ⭐ **json-rules-engine**
- **Repo**: https://github.com/CacheControl/json-rules-engine
- **What**: Rules engine for JavaScript/Node.js
- **Use**: Define payout eligibility rules, profit split logic as configurable JSON rules
- **Pros**: 
  - Rules stored as JSON (configurable per white-label firm)
  - Supports complex nested conditions
  - Event-driven architecture
  - Easy to add/modify rules without code changes
- **Verdict**: **RECOMMENDED** for business rule evaluation

#### ⭐ **Open Policy Agent (OPA)**
- **Repo**: https://github.com/open-policy-agent/opa
- **What**: General-purpose policy engine
- **Use**: Authorization policies, payout approval policies, compliance rules
- **Pros**: Rego policy language, can be embedded or run as service
- **Verdict**: **RECOMMENDED** for policy decisions

#### **Drools (Java)**
- **Repo**: https://github.com/apache/incubator-kie-drools
- **What**: Business rules management system
- **Use**: Complex rule evaluation for eligibility and profit calculation
- **Pros**: Mature, supports decision tables, rule versioning

#### **GoRules**
- **Repo**: https://github.com/gorules/zen
- **What**: Business rules engine with visual editor
- **Use**: Visual rule creation for non-technical firm operators
- **Pros**: Visual editor, DMN support, JSON-based rules
- **Verdict**: **RECOMMENDED** if you need a visual rule editor for white-label operators

---

### 5.4 Payment Processing / Gateway

#### ⭐ **Kill Bill**
- **Repo**: https://github.com/killbill/killbill
- **What**: Open-source billing and payment platform
- **Use**: Payment orchestration, retry logic, payment method management
- **Pros**: 
  - Plugin architecture for multiple payment providers
  - Payment retry logic built-in
  - Supports multiple payment methods
  - Invoice/billing support
  - Multi-tenancy (perfect for white-label)
  - Used by major companies
- **Cons**: Java-based, can be complex to set up
- **Verdict**: **CONSIDER** for payment orchestration layer

#### ⭐ **Hyperswitch**
- **Repo**: https://github.com/juspay/hyperswitch
- **What**: Open-source payment switch / orchestrator
- **Use**: Route payments across multiple processors, smart routing, failover
- **Pros**:
  - Supports 50+ payment processors
  - Smart routing (cost-based, success-rate-based)
  - Built-in retries and failover
  - Unified API for all processors
  - Multi-currency support
  - PCI-DSS compliant architecture
  - Dashboard included
- **Verdict**: **STRONGLY RECOMMENDED** — eliminates the need to build payment provider integrations from scratch

#### **Lotus (now Lago)**
- **Repo**: https://github.com/getlago/lago
- **What**: Open-source metering and billing
- **Use**: Fee calculation, usage-based billing for platform fees
- **Pros**: API-first, supports complex pricing models

---

### 5.5 KYC/AML & Compliance

#### ⭐ **Sumsub** (Not open-source, but has free tier)
- Comprehensive KYC/AML platform with APIs

#### **Apache Fineract**
- **Repo**: https://github.com/apache/fineract
- **What**: Core banking platform
- **Use**: Can borrow compliance patterns and account management concepts

#### **Dosco/Super-Graph**
- For building compliance dashboards quickly

#### **OpenSanctions**
- **Repo**: https://github.com/opensanctions/opensanctions
- **What**: Open database of sanctions, PEPs, and criminal watchlists
- **Use**: Screen traders against sanctions lists before processing payouts
- **Verdict**: **RECOMMENDED** for sanctions screening

---

### 5.6 Event Streaming / Message Broker

#### ⭐ **Apache Kafka**
- **Use**: Event backbone for the entire system
- **Why**: 
  - All payout state transitions published as events
  - Enables event sourcing
  - Connects all microservices
  - Enables audit trail reconstruction
  - Handles high throughput

#### ⭐ **NATS**
- **Repo**: https://github.com/nats-io/nats-server
- **Use**: Lightweight alternative to Kafka
- **Pros**: Simpler to operate, JetStream for persistence

#### **RabbitMQ**
- Solid choice if you need complex routing patterns

#### ⭐ **Redpanda**
- **Repo**: https://github.com/redpanda-data/redpanda
- **What**: Kafka-compatible streaming platform
- **Pros**: Simpler to operate than Kafka, no JVM dependency, Kafka API compatible
- **Verdict**: **RECOMMENDED** as Kafka alternative

---

### 5.7 Notification System

#### ⭐ **Novu**
- **Repo**: https://github.com/novuhq/novu
- **What**: Open-source notification infrastructure
- **Use**: Send payout notifications via email, SMS, push, in-app
- **Pros**: 
  - Multi-channel (email, SMS, push, in-app, Slack)
  - Template management
  - Notification preferences per user
  - Digest/batching
  - Built-in dashboard
- **Verdict**: **STRONGLY RECOMMENDED** — saves enormous effort on notification logic

#### **Apprise**
- **Repo**: https://github.com/caronc/apprise
- **What**: Push notification library supporting many services
- **Use**: Simpler alternative to Novu

---

### 5.8 API Gateway

#### ⭐ **Kong**
- **Repo**: https://github.com/Kong/kong
- **What**: Cloud-native API gateway
- **Use**: Rate limiting, authentication, routing, API management
- **Verdict**: **RECOMMENDED**

#### **Traefik**
- **Repo**: https://github.com/traefik/traefik
- **What**: Modern reverse proxy and load balancer
- **Use**: Service discovery, load balancing, TLS termination

#### **APISIX**
- **Repo**: https://github.com/apache/apisix
- **What**: Cloud-native API gateway
- **Pros**: High performance, plugin ecosystem

---

### 5.9 Scheduling / Job Queue

#### ⭐ **BullMQ**
- **Repo**: https://github.com/taskforcesh/bullmq
- **What**: Redis-based queue for Node.js
- **Use**: Scheduled payout processing, retry queues, batch processing
- **Pros**: Rate limiting, delayed jobs, repeatable jobs, dashboard (Bull Board)

#### ⭐ **Quartz Scheduler** (Java) / **Hangfire** (.NET) / **Celery** (Python)
- Language-specific job scheduling

#### **Graphile Worker**
- **Repo**: https://github.com/graphile/worker
- **What**: PostgreSQL-backed job queue
- **Pros**: No Redis needed, uses PostgreSQL, ACID guarantees for job processing

---

### 5.10 Audit Trail & Event Sourcing

#### ⭐ **EventStoreDB**
- **Repo**: https://github.com/EventStore/EventStore
- **What**: Purpose-built database for event sourcing
- **Use**: Store all payout events as immutable stream
- **Pros**: 
  - Built for event sourcing
  - Projections
  - Subscriptions
  - Perfect audit trail
- **Verdict**: **RECOMMENDED** for audit trail and event history

#### **Marten** (.NET)
- **Repo**: https://github.com/JasperFx/marten
- **What**: Document database and event store using PostgreSQL

---

### 5.11 Observability & Monitoring

#### ⭐ **Grafana + Prometheus + Loki**
- **Use**: Metrics, dashboards, alerting, log aggregation
- **Critical dashboards**:
  - Payout processing times
  - Success/failure rates per payment provider
  - Queue depths
  - Payment provider health
  - Daily payout volumes

#### ⭐ **OpenTelemetry**
- **Use**: Distributed tracing across all microservices
- **Why critical**: Trace a payout request across all services

#### **Sentry**
- **Use**: Error tracking and performance monitoring

---

### 5.12 Reconciliation Tools

#### ⭐ **Moov.io**
- **Repo**: https://github.com/moov-io
- **What**: Open-source financial services toolkit
- **Components**:
  - `moov-io/ach` - ACH file generation
  - `moov-io/wire` - Fedwire / SWIFT
  - `moov-io/iso8583` - ISO 8583 message parsing
  - `moov-io/watchman` - OFAC sanctions screening
- **Verdict**: **STRONGLY RECOMMENDED** for US payment rails and sanctions screening

---

### 5.13 Multi-Tenancy

#### ⭐ **Citus (PostgreSQL Extension)**
- **Repo**: https://github.com/citusdata/citus
- **What**: Distributed PostgreSQL for multi-tenant applications
- **Use**: Scale PostgreSQL for multi-tenant white-label support
- **Verdict**: **RECOMMENDED** for database-level multi-tenancy

---

### 5.14 Identity & Access Management

#### ⭐ **Keycloak**
- **Repo**: https://github.com/keycloak/keycloak
- **What**: Identity and access management
- **Use**: 
  - Trader authentication
  - Admin/operator authentication
  - Role-based access control (who can approve payouts)
  - Multi-tenant realm support
- **Verdict**: **STRONGLY RECOMMENDED**

---

## 6. Recommended Architecture with Open-Source Stack

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    RECOMMENDED OPEN-SOURCE ARCHITECTURE                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                      API GATEWAY                                 │    │
│  │                    (Kong / APISIX)                                │    │
│  └──────────────────────────┬──────────────────────────────────────┘    │
│                              │                                          │
│  ┌──────────────────────────┼──────────────────────────────────────┐    │
│  │              AUTHENTICATION (Keycloak)                           │    │
│  └──────────────────────────┬──────────────────────────────────────┘    │
│                              │                                          │
│  ┌──────────┬────────┬──────┴──────┬──────────┬──────────┐             │
│  │          │        │             │          │          │             │
│  │ Payout   │ Profit │  Approval   │ Payment  │ Notifi-  │             │
│  │ Engine   │ Calc   │  Workflow   │ Gateway  │ cation   │             │
│  │ Service  │ Engine │  Service    │ Service  │ Service  │             │
│  │          │        │             │          │          │             │
│  │ Custom   │ Custom │  Temporal   │Hyperswitch│  Novu   │             │
│  │ + Rules  │ + json-│  Workflow   │          │          │             │
│  │ Engine   │ rules- │             │          │          │             │
│  │          │ engine │             │          │          │             │
│  └────┬─────┘ └───┬──┘  └────┬────┘ └────┬───┘ └────┬───┘             │
│       │           │          │           │          │                   │
│  ┌────┴───────────┴──────────┴───────────┴──────────┴───┐              │
│  │              EVENT BUS (Redpanda / Kafka)              │              │
│  └────┬───────────────────────────────────┬──────────────┘              │
│       │                                   │                              │
│  ┌────┴─────────────────┐  ┌──────────────┴──────────────┐             │
│  │    DATA STORES        │  │     SUPPORTING SERVICES      │             │
│  │                       │  │                              │             │
│  │ • PostgreSQL (main)   │  │ • Moov.io (ACH/SWIFT/OFAC) │             │
│  │ • TigerBeetle (ledger)│  │ • OpenSanctions (screening)│             │
│  │ • Redis (cache/locks) │  │ • json-rules-engine        │             │
│  │ • EventStoreDB (audit)│  │ • BullMQ (job scheduling)  │             │
│  │ • MinIO (documents)   │  │                              │             │
│  └───────────────────────┘  └──────────────────────────────┘             │
│                                                                          │
│  ┌───────────────────────────────────────────────────────────────┐      │
│  │              OBSERVABILITY                                     │      │
│  │  Grafana + Prometheus + Loki + OpenTelemetry + Sentry         │      │
│  └───────────────────────────────────────────────────────────────┘      │
│                                                                          │
│  OR ALTERNATIVELY FOR LEDGER:                                            │
│  ┌───────────────────────────────────────────────────────────────┐      │
│  │  Blnk Finance (complete ledger solution)                      │      │
│  └───────────────────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 7. Detailed Component Implementation

### 7.1 Payout Workflow with Temporal

```go
// payout_workflow.go - Temporal Workflow Definition

package payouts

import (
    "time"
    "go.temporal.io/sdk/workflow"
)

type PayoutRequest struct {
    PayoutID        string
    TraderID        string
    FirmID          string  // White-label firm identifier
    FundedAccountID string
    RequestedAmount float64
    PayoutMethod    string  // "bank_transfer", "crypto_usdt", "paypal"
    Currency        string
    PayoutDetails   map[string]interface{}
}

type PayoutResult struct {
    PayoutID       string
    Status         string
    FinalAmount    float64
    TransactionRef string
    ProcessedAt    time.Time
    FailureReason  string
}

func PayoutWorkflow(ctx workflow.Context, req PayoutRequest) (*PayoutResult, error) {
    logger := workflow.GetLogger(ctx)
    logger.Info("Starting payout workflow", "payoutID", req.PayoutID)

    // Activity options with retries
    ao := workflow.ActivityOptions{
        StartToCloseTimeout: 30 * time.Second,
        RetryPolicy: &temporal.RetryPolicy{
            InitialInterval:    time.Second,
            BackoffCoefficient: 2.0,
            MaximumInterval:    time.Minute,
            MaximumAttempts:    3,
        },
    }
    ctx = workflow.WithActivityOptions(ctx, ao)

    // ============================================================
    // STEP 1: VALIDATE PAYOUT REQUEST
    // ============================================================
    var validationResult ValidationResult
    err := workflow.ExecuteActivity(ctx, ValidatePayoutRequest, req).Get(ctx, &validationResult)
    if err != nil {
        return &PayoutResult{Status: "REJECTED", FailureReason: err.Error()}, nil
    }

    // ============================================================
    // STEP 2: COMPLIANCE CHECK (KYC/AML/Sanctions)
    // ============================================================
    var complianceResult ComplianceResult
    err = workflow.ExecuteActivity(ctx, CheckCompliance, req).Get(ctx, &complianceResult)
    if err != nil || !complianceResult.Approved {
        return &PayoutResult{Status: "COMPLIANCE_HOLD", FailureReason: complianceResult.Reason}, nil
    }

    // ============================================================
    // STEP 3: CALCULATE PROFIT & PAYOUT AMOUNT
    // ============================================================
    var calculation ProfitCalculation
    err = workflow.ExecuteActivity(ctx, CalculateProfit, req).Get(ctx, &calculation)
    if err != nil {
        return &PayoutResult{Status: "CALCULATION_ERROR", FailureReason: err.Error()}, nil
    }

    if calculation.EligibleAmount <= 0 {
        return &PayoutResult{Status: "REJECTED", FailureReason: "No eligible profit for payout"}, nil
    }

    // ============================================================
    // STEP 4: APPROVAL WORKFLOW (Human-in-the-Loop)
    // ============================================================
    var approvalRequired bool
    err = workflow.ExecuteActivity(ctx, CheckApprovalRequired, req, calculation).Get(ctx, &approvalRequired)
    if err != nil {
        return nil, err
    }

    if approvalRequired {
        // Send approval request notification
        err = workflow.ExecuteActivity(ctx, SendApprovalRequest, req, calculation).Get(ctx, nil)
        if err != nil {
            return nil, err
        }

        // Wait for human approval (with timeout)
        var approvalDecision ApprovalDecision
        approvalCh := workflow.GetSignalChannel(ctx, "approval-decision")
        
        // Create a timer for SLA
        timerCtx, timerCancel := workflow.WithCancel(ctx)
        timerFuture := workflow.NewTimer(timerCtx, 48*time.Hour) // 48h SLA

        selector := workflow.NewSelector(ctx)
        
        selector.AddReceive(approvalCh, func(c workflow.ReceiveChannel, more bool) {
            c.Receive(ctx, &approvalDecision)
            timerCancel()
        })
        
        selector.AddFuture(timerFuture, func(f workflow.Future) {
            // Escalate if no decision within SLA
            _ = workflow.ExecuteActivity(ctx, EscalateApproval, req).Get(ctx, nil)
            approvalDecision = ApprovalDecision{Approved: false, Reason: "SLA timeout - escalated"}
        })
        
        selector.Select(ctx)

        if !approvalDecision.Approved {
            _ = workflow.ExecuteActivity(ctx, NotifyPayoutRejected, req, approvalDecision.Reason).Get(ctx, nil)
            return &PayoutResult{Status: "REJECTED", FailureReason: approvalDecision.Reason}, nil
        }
    }

    // ============================================================
    // STEP 5: CREATE LEDGER ENTRIES (Reserve Funds)
    // ============================================================
    var ledgerEntry LedgerEntry
    err = workflow.ExecuteActivity(ctx, CreateLedgerReservation, req, calculation).Get(ctx, &ledgerEntry)
    if err != nil {
        return nil, err
    }

    // ============================================================
    // STEP 6: EXECUTE PAYMENT
    // ============================================================
    paymentAO := workflow.ActivityOptions{
        StartToCloseTimeout: 5 * time.Minute, // Payment can take longer
        HeartbeatTimeout:    30 * time.Second,
        RetryPolicy: &temporal.RetryPolicy{
            InitialInterval:        5 * time.Second,
            BackoffCoefficient:     2.0,
            MaximumInterval:        5 * time.Minute,
            MaximumAttempts:        5,
            NonRetryableErrorTypes: []string{"INVALID_PAYMENT_DETAILS", "INSUFFICIENT_FUNDS"},
        },
    }
    paymentCtx := workflow.WithActivityOptions(ctx, paymentAO)

    var paymentResult PaymentResult
    err = workflow.ExecuteActivity(paymentCtx, ExecutePayment, req, calculation).Get(ctx, &paymentResult)
    if err != nil {
        // Payment failed - reverse ledger reservation
        _ = workflow.ExecuteActivity(ctx, ReverseLedgerReservation, ledgerEntry).Get(ctx, nil)
        _ = workflow.ExecuteActivity(ctx, NotifyPayoutFailed, req, err.Error()).Get(ctx, nil)
        return &PayoutResult{Status: "FAILED", FailureReason: err.Error()}, nil
    }

    // ============================================================
    // STEP 7: CONFIRM LEDGER ENTRIES
    // ============================================================
    err = workflow.ExecuteActivity(ctx, ConfirmLedgerEntry, ledgerEntry, paymentResult).Get(ctx, nil)
    if err != nil {
        // This is critical - payment sent but ledger not updated
        // Flag for manual reconciliation
        _ = workflow.ExecuteActivity(ctx, FlagForReconciliation, req, paymentResult, ledgerEntry).Get(ctx, nil)
    }

    // ============================================================
    // STEP 8: UPDATE HIGH WATER MARK
    // ============================================================
    err = workflow.ExecuteActivity(ctx, UpdateHighWaterMark, req, calculation).Get(ctx, nil)
    if err != nil {
        logger.Error("Failed to update high water mark", "error", err)
        // Non-critical - can be fixed in reconciliation
    }

    // ============================================================
    // STEP 9: NOTIFY TRADER
    // ============================================================
    _ = workflow.ExecuteActivity(ctx, NotifyPayoutCompleted, req, paymentResult).Get(ctx, nil)

    // ============================================================
    // STEP 10: EMIT ANALYTICS EVENT
    // ============================================================
    _ = workflow.ExecuteActivity(ctx, EmitPayoutAnalyticsEvent, req, calculation, paymentResult).Get(ctx, nil)

    return &PayoutResult{
        PayoutID:       req.PayoutID,
        Status:         "COMPLETED",
        FinalAmount:    calculation.FinalPayoutAmount,
        TransactionRef: paymentResult.TransactionRef,
        ProcessedAt:    paymentResult.ProcessedAt,
    }, nil
}
```

### 7.2 Profit Calculation Engine

```python
# profit_calculator.py - Configurable Profit Calculation Engine

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_DOWN
from typing import List, Optional, Dict
from datetime import datetime, timedelta
import json

@dataclass
class FirmPayoutConfig:
    """White-label firm's payout configuration"""
    firm_id: str
    base_profit_split: Decimal  # e.g., 0.80 (80% to trader)
    scaling_tiers: List[Dict]   # Scaling plan
    min_payout_amount: Decimal
    payout_frequency_days: int
    first_payout_holding_days: int
    consistency_rule_max_trade_pct: Optional[Decimal]  # e.g., 0.30
    max_daily_loss_pct: Decimal
    max_total_drawdown_pct: Decimal
    payment_fee_structure: Dict
    tax_withholding_rules: Dict
    
    # Scaling example:
    # scaling_tiers = [
    #     {"consecutive_profitable_months": 3, "split": 0.85},
    #     {"consecutive_profitable_months": 6, "split": 0.90},
    #     {"total_payouts_amount": 50000, "split": 0.90},
    # ]


@dataclass
class TradingAccount:
    account_id: str
    trader_id: str
    firm_id: str
    initial_balance: Decimal
    current_equity: Decimal
    current_balance: Decimal
    high_water_mark: Decimal
    phase: str  # "challenge_1", "challenge_2", "funded"
    created_at: datetime
    total_payouts_to_date: Decimal
    consecutive_profitable_months: int
    last_payout_date: Optional[datetime]
    payout_count: int


@dataclass 
class Trade:
    trade_id: str
    account_id: str
    profit: Decimal
    open_time: datetime
    close_time: datetime
    symbol: str
    volume: Decimal


@dataclass
class ProfitCalculationResult:
    # Inputs
    account_id: str
    calculation_timestamp: datetime
    
    # Gross calculations
    gross_profit: Decimal
    high_water_mark_used: Decimal
    new_high_water_mark: Decimal
    
    # Adjustments
    consistency_adjustment: Decimal  # Removed profit from outsized trades
    adjusted_gross_profit: Decimal
    
    # Split calculation
    profit_split_ratio: Decimal
    split_tier_applied: str
    trader_gross_share: Decimal
    firm_gross_share: Decimal
    
    # Deductions
    platform_fee: Decimal
    payment_processing_fee: Decimal
    tax_withholding: Decimal
    currency_conversion_fee: Decimal
    
    # Final amount
    final_payout_amount: Decimal
    payout_currency: str
    
    # Eligibility
    is_eligible: bool
    ineligibility_reasons: List[str]
    
    # Audit
    calculation_steps: List[Dict]  # Detailed step-by-step audit trail


class ProfitCalculationEngine:
    
    def __init__(self, config: FirmPayoutConfig):
        self.config = config
    
    def calculate(
        self,
        account: TradingAccount,
        trades: List[Trade],
        payout_currency: str = "USD",
        fx_rate: Decimal = Decimal("1.0")
    ) -> ProfitCalculationResult:
        
        steps = []
        ineligibility_reasons = []
        
        # ==========================================
        # STEP 1: Check basic eligibility
        # ==========================================
        if account.phase != "funded":
            ineligibility_reasons.append(f"Account is in {account.phase} phase, not funded")
        
        if account.last_payout_date:
            days_since_last = (datetime.utcnow() - account.last_payout_date).days
            if days_since_last < self.config.payout_frequency_days:
                ineligibility_reasons.append(
                    f"Payout frequency not met. {self.config.payout_frequency_days - days_since_last} days remaining"
                )
        
        if account.payout_count == 0:
            days_since_funded = (datetime.utcnow() - account.created_at).days
            if days_since_funded < self.config.first_payout_holding_days:
                ineligibility_reasons.append(
                    f"First payout holding period not met. {self.config.first_payout_holding_days - days_since_funded} days remaining"
                )
        
        steps.append({
            "step": "eligibility_check",
            "result": "pass" if not ineligibility_reasons else "fail",
            "details": ineligibility_reasons
        })
        
        # ==========================================
        # STEP 2: Calculate Gross Profit (HWM method)
        # ==========================================
        gross_profit = account.current_equity - account.high_water_mark
        
        if gross_profit <= 0:
            ineligibility_reasons.append("No profit above high water mark")
        
        steps.append({
            "step": "gross_profit_calculation",
            "current_equity": str(account.current_equity),
            "high_water_mark": str(account.high_water_mark),
            "gross_profit": str(gross_profit)
        })
        
        # ==========================================
        # STEP 3: Apply Consistency Rules
        # ==========================================
        consistency_adjustment = Decimal("0")
        
        if self.config.consistency_rule_max_trade_pct and gross_profit > 0:
            max_single_trade_profit = gross_profit * self.config.consistency_rule_max_trade_pct
            
            for trade in trades:
                if trade.profit > max_single_trade_profit:
                    excess = trade.profit - max_single_trade_profit
                    consistency_adjustment += excess
                    steps.append({
                        "step": "consistency_rule_applied",
                        "trade_id": trade.trade_id,
                        "trade_profit": str(trade.profit),
                        "max_allowed": str(max_single_trade_profit),
                        "excess_removed": str(excess)
                    })
        
        adjusted_gross_profit = max(gross_profit - consistency_adjustment, Decimal("0"))
        
        steps.append({
            "step": "consistency_adjustment",
            "original_gross": str(gross_profit),
            "adjustment": str(consistency_adjustment),
            "adjusted_gross": str(adjusted_gross_profit)
        })
        
        # ==========================================
        # STEP 4: Determine Profit Split Ratio
        # ==========================================
        split_ratio = self.config.base_profit_split
        tier_applied = "base"
        
        for tier in sorted(self.config.scaling_tiers, key=lambda t: t.get("split", 0)):
            if "consecutive_profitable_months" in tier:
                if account.consecutive_profitable_months >= tier["consecutive_profitable_months"]:
                    if tier["split"] > float(split_ratio):
                        split_ratio = Decimal(str(tier["split"]))
                        tier_applied = f"consecutive_months_{tier['consecutive_profitable_months']}"
            
            if "total_payouts_amount" in tier:
                if account.total_payouts_to_date >= Decimal(str(tier["total_payouts_amount"])):
                    if tier["split"] > float(split_ratio):
                        split_ratio = Decimal(str(tier["split"]))
                        tier_applied = f"total_payouts_{tier['total_payouts_amount']}"
        
        trader_gross_share = (adjusted_gross_profit * split_ratio).quantize(
            Decimal("0.01"), rounding=ROUND_DOWN
        )
        firm_gross_share = adjusted_gross_profit - trader_gross_share
        
        steps.append({
            "step": "profit_split",
            "split_ratio": str(split_ratio),
            "tier_applied": tier_applied,
            "trader_share": str(trader_gross_share),
            "firm_share": str(firm_gross_share)
        })
        
        # ==========================================
        # STEP 5: Calculate Fees
        # ==========================================
        platform_fee = Decimal("0")
        if "platform_pct" in self.config.payment_fee_structure:
            platform_fee = (trader_gross_share * Decimal(str(
                self.config.payment_fee_structure["platform_pct"]
            ))).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
        
        payment_processing_fee = Decimal(str(
            self.config.payment_fee_structure.get("fixed_processing_fee", "0")
        ))
        
        # Currency conversion fee
        currency_conversion_fee = Decimal("0")
        if fx_rate != Decimal("1.0"):
            currency_conversion_fee = (trader_gross_share * Decimal("0.005")).quantize(
                Decimal("0.01"), rounding=ROUND_DOWN
            )  # 0.5% FX fee
        
        # Tax withholding
        tax_withholding = Decimal("0")
        # Apply based on trader's jurisdiction
        
        total_deductions = platform_fee + payment_processing_fee + currency_conversion_fee + tax_withholding
        
        steps.append({
            "step": "fee_calculation",
            "platform_fee": str(platform_fee),
            "payment_processing_fee": str(payment_processing_fee),
            "currency_conversion_fee": str(currency_conversion_fee),
            "tax_withholding": str(tax_withholding),
            "total_deductions": str(total_deductions)
        })
        
        # ==========================================
        # STEP 6: Final Payout Amount
        # ==========================================
        final_amount = (trader_gross_share - total_deductions).quantize(
            Decimal("0.01"), rounding=ROUND_DOWN
        )
        
        # Apply FX conversion
        final_amount_in_payout_currency = (final_amount * fx_rate).quantize(
            Decimal("0.01"), rounding=ROUND_DOWN
        )
        
        # Check minimum
        if final_amount_in_payout_currency < self.config.min_payout_amount:
            ineligibility_reasons.append(
                f"Final amount {final_amount_in_payout_currency} below minimum {self.config.min_payout_amount}"
            )
        
        # New HWM
        new_hwm = account.high_water_mark + adjusted_gross_profit
        
        steps.append({
            "step": "final_calculation",
            "final_amount_base": str(final_amount),
            "fx_rate": str(fx_rate),
            "final_amount_payout_currency": str(final_amount_in_payout_currency),
            "new_high_water_mark": str(new_hwm)
        })
        
        return ProfitCalculationResult(
            account_id=account.account_id,
            calculation_timestamp=datetime.utcnow(),
            gross_profit=gross_profit,
            high_water_mark_used=account.high_water_mark,
            new_high_water_mark=new_hwm,
            consistency_adjustment=consistency_adjustment,
            adjusted_gross_profit=adjusted_gross_profit,
            profit_split_ratio=split_ratio,
            split_tier_applied=tier_applied,
            trader_gross_share=trader_gross_share,
            firm_gross_share=firm_gross_share,
            platform_fee=platform_fee,
            payment_processing_fee=payment_processing_fee,
            tax_withholding=tax_withholding,
            currency_conversion_fee=currency_conversion_fee,
            final_payout_amount=final_amount_in_payout_currency,
            payout_currency=payout_currency,
            is_eligible=len(ineligibility_reasons) == 0 and final_amount_in_payout_currency > 0,
            ineligibility_reasons=ineligibility_reasons,
            calculation_steps=steps
        )
```

### 7.3 Ledger Implementation with TigerBeetle

```go
// ledger_service.go - Using TigerBeetle for double-entry accounting

package ledger

import (
    "context"
    "fmt"
    tigerbeetle "github.com/tigerbeetle/tigerbeetle-go"
    "github.com/tigerbeetle/tigerbeetle-go/pkg/types"
)

// Account types in our ledger
const (
    AccountTypeTraderProfit    = 1
    AccountTypeFirmRevenue     = 2
    AccountTypePayoutPayable   = 3
    AccountTypeBankOutflow     = 4
    AccountTypeCryptoOutflow   = 5
    AccountTypePlatformFees    = 6
    AccountTypePaymentFees     = 7
    AccountTypeTaxWithholding  = 8
    AccountTypeSuspense        = 9
    AccountTypeFXGainLoss      = 10
)

// Ledger codes (for categorizing transfers)
const (
    LedgerCodePayoutReservation = 100
    LedgerCodePayoutExecution   = 101
    LedgerCodePayoutReversal    = 102
    LedgerCodeFeeDeduction      = 103
    LedgerCodeProfitAllocation  = 104
)

type LedgerService struct {
    client tigerbeetle.Client
}

func NewLedgerService(addresses []string, clusterID uint128) (*LedgerService, error) {
    client, err := tigerbeetle.NewClient(clusterID, addresses)
    if err != nil {
        return nil, fmt.Errorf("failed to connect to TigerBeetle: %w", err)
    }
    return &LedgerService{client: client}, nil
}

// CreateTraderAccounts creates the necessary ledger accounts for a new trader
func (l *LedgerService) CreateTraderAccounts(
    ctx context.Context, 
    traderID string, 
    firmID string,
    fundedAccountID string,
) error {
    accounts := []types.Account{
        {
            ID:     generateAccountID(traderID, fundedAccountID, "profit"),
            Ledger: LedgerCodeProfitAllocation,
            Code:   AccountTypeTraderProfit,
            Flags:  types.AccountFlags{DebitsMustNotExceedCredits: true}.ToUint16(),
            // This ensures trader can't withdraw more than earned
        },
        {
            ID:     generateAccountID(traderID, fundedAccountID, "payout_payable"),
            Ledger: LedgerCodePayoutReservation,
            Code:   AccountTypePayoutPayable,
        },
    }
    
    results, err := l.client.CreateAccounts(accounts)
    if err != nil {
        return fmt.Errorf("failed to create accounts: %w", err)
    }
    
    for _, result := range results {
        if result.Result != types.CreateAccountResultOk {
            return fmt.Errorf("account creation failed: %v", result.Result)
        }
    }
    
    return nil
}

// ReservePayout creates ledger entries to reserve funds for a payout
// This is a two-phase transfer - first we reserve, then we confirm or rollback
func (l *LedgerService) ReservePayout(
    ctx context.Context,
    payoutID string,
    traderProfitAccountID types.Uint128,
    payoutPayableAccountID types.Uint128,
    amount uint64, // Amount in cents/smallest currency unit
) (*types.Transfer, error) {
    
    transfers := []types.Transfer{
        {
            ID:              generateTransferID(payoutID, "reservation"),
            DebitAccountID:  traderProfitAccountID,
            CreditAccountID: payoutPayableAccountID,
            Amount:          amount,
            Ledger:          LedgerCodePayoutReservation,
            Code:            1, // Reservation
            Flags:           types.TransferFlags{Pending: true}.ToUint16(),
            // Pending flag means this is a two-phase transfer
        },
    }
    
    results, err := l.client.CreateTransfers(transfers)
    if err != nil {
        return nil, fmt.Errorf("failed to create reservation transfer: %w", err)
    }
    
    for _, result := range results {
        if result.Result != types.CreateTransferResultOk {
            return nil, fmt.Errorf("reservation failed: %v", result.Result)
        }
    }
    
    return &transfers[0], nil
}

// ConfirmPayout confirms the reservation and creates the outflow entry
func (l *LedgerService) ConfirmPayout(
    ctx context.Context,
    payoutID string,
    reservationTransferID types.Uint128,
    payoutPayableAccountID types.Uint128,
    outflowAccountID types.Uint128,
    paymentFeeAccountID types.Uint128,
    payoutAmount uint64,
    feeAmount uint64,
) error {
    
    transfers := []types.Transfer{
        // Confirm the reservation
        {
            ID:              generateTransferID(payoutID, "confirm"),
            PendingID:       reservationTransferID,
            Flags:           types.TransferFlags{PostPendingTransfer: true}.ToUint16(),
        },
        // Record the actual outflow
        {
            ID:              generateTransferID(payoutID, "outflow"),
            DebitAccountID:  payoutPayableAccountID,
            CreditAccountID: outflowAccountID,
            Amount:          payoutAmount,
            Ledger:          LedgerCodePayoutExecution,
            Code:            2, // Execution
        },
        // Record the fee
        {
            ID:              generateTransferID(payoutID, "fee"),
            DebitAccountID:  payoutPayableAccountID,
            CreditAccountID: paymentFeeAccountID,
            Amount:          feeAmount,
            Ledger:          LedgerCodeFeeDeduction,
            Code:            3, // Fee
        },
    }
    
    results, err := l.client.CreateTransfers(transfers)
    if err != nil {
        return fmt.Errorf("failed to confirm payout: %w", err)
    }
    
    for _, result := range results {
        if result.Result != types.CreateTransferResultOk {
            return fmt.Errorf("confirmation failed: %v", result.Result)
        }
    }
    
    return nil
}

// RollbackPayout reverses a pending reservation
func (l *LedgerService) RollbackPayout(
    ctx context.Context,
    payoutID string,
    reservationTransferID types.Uint128,
) error {
    transfers := []types.Transfer{
        {
            ID:        generateTransferID(payoutID, "rollback"),
            PendingID: reservationTransferID,
            Flags:     types.TransferFlags{VoidPendingTransfer: true}.ToUint16(),
        },
    }
    
    results, err := l.client.CreateTransfers(transfers)
    if err != nil {
        return fmt.Errorf("failed to rollback: %w", err)
    }
    
    for _, result := range results {
        if result.Result != types.CreateTransferResultOk {
            return fmt.Errorf("rollback failed: %v", result.Result)
        }
    }
    
    return nil
}

// GetAccountBalance retrieves the current balance of an account
func (l *LedgerService) GetAccountBalance(
    ctx context.Context,
    accountID types.Uint128,
) (*AccountBalance, error) {
    accounts, err := l.client.LookupAccounts([]types.Uint128{accountID})
    if err != nil {
        return nil, err
    }
    
    if len(accounts) == 0 {
        return nil, fmt.Errorf("account not found")
    }
    
    acc := accounts[0]
    return &AccountBalance{
        CreditsPosted:  acc.CreditsPosted,
        DebitsPosted:   acc.DebitsPosted,
        CreditsPending: acc.CreditsPending,
        DebitsPending:  acc.DebitsPending,
        Available:      acc.CreditsPosted - acc.DebitsPosted - acc.DebitsPending,
    }, nil
}
```

### 7.4 Payment Gateway with Hyperswitch Integration

```typescript
// payment-gateway.service.ts - Abstracting payments via Hyperswitch

import { Injectable, Logger } from '@nestjs/common';
import axios, { AxiosInstance } from 'axios';

interface PaymentRequest {
  payoutId: string;
  amount: number; // in smallest currency unit (cents)
  currency: string;
  paymentMethod: PaymentMethodType;
  recipientDetails: RecipientDetails;
  metadata: Record<string, string>;
}

interface RecipientDetails {
  // Bank transfer
  bankName?: string;
  accountNumber?: string;
  routingNumber?: string;
  swiftCode?: string;
  iban?: string;
  
  // Crypto
  walletAddress?: string;
  network?: string; // "ethereum", "tron", "bitcoin"
  
  // E-wallet
  email?: string;
  phone?: string;
}

type PaymentMethodType = 
  | 'bank_transfer_ach'
  | 'bank_transfer_sepa'
  | 'bank_transfer_swift'
  | 'bank_transfer_wise'
  | 'crypto_usdt_trc20'
  | 'crypto_usdt_erc20'
  | 'crypto_btc'
  | 'ewallet_paypal'
  | 'ewallet_skrill';

interface PaymentResponse {
  paymentId: string;
  externalRef: string;
  status: 'processing' | 'completed' | 'failed' | 'requires_action';
  providerUsed: string;
  estimatedArrival?: Date;
  fees: {
    processingFee: number;
    currencyConversionFee: number;
  };
}

@Injectable()
export class PaymentGatewayService {
  private readonly logger = new Logger(PaymentGatewayService.name);
  private readonly hyperswitchClient: AxiosInstance;
  
  // Fallback provider mapping
  private readonly providerPriority: Record<PaymentMethodType, string[]> = {
    'bank_transfer_ach': ['stripe_connect', 'wise', 'payoneer'],
    'bank_transfer_sepa': ['wise', 'stripe_connect', 'payoneer'],
    'bank_transfer_swift': ['wise', 'payoneer', 'stripe_connect'],
    'bank_transfer_wise': ['wise'],
    'crypto_usdt_trc20': ['fireblocks', 'circle', 'manual_crypto'],
    'crypto_usdt_erc20': ['fireblocks', 'circle', 'manual_crypto'],
    'crypto_btc': ['fireblocks', 'bitpay'],
    'ewallet_paypal': ['paypal'],
    'ewallet_skrill': ['skrill'],
  };

  constructor() {
    this.hyperswitchClient = axios.create({
      baseURL: process.env.HYPERSWITCH_API_URL || 'http://localhost:8080',
      headers: {
        'api-key': process.env.HYPERSWITCH_API_KEY,
        'Content-Type': 'application/json',
      },
    });
  }

  async executePayment(request: PaymentRequest): Promise<PaymentResponse> {
    this.logger.log(`Executing payment for payout ${request.payoutId}`);
    
    // Use Hyperswitch for supported payment methods
    if (this.isHyperswitchSupported(request.paymentMethod)) {
      return this.executeViaHyperswitch(request);
    }
    
    // For crypto and specialty methods, use direct integration
    return this.executeViaDirectProvider(request);
  }

  private async executeViaHyperswitch(request: PaymentRequest): Promise<PaymentResponse> {
    try {
      // Create a payout via Hyperswitch
      const response = await this.hyperswitchClient.post('/payouts/create', {
        amount: request.amount,
        currency: request.currency,
        payout_type: this.mapToHyperswitchPayoutType(request.paymentMethod),
        connector: this.getPreferredConnector(request.paymentMethod),
        metadata: {
          payout_id: request.payoutId,
          ...request.metadata,
        },
        payout_method_data: this.buildPayoutMethodData(request),
        return_url: `${process.env.APP_URL}/api/payouts/${request.payoutId}/callback`,
      });

      return {
        paymentId: response.data.payout_id,
        externalRef: response.data.connector_transaction_id,
        status: this.mapHyperswitchStatus(response.data.status),
        providerUsed: response.data.connector,
        fees: {
          processingFee: response.data.processing_fee || 0,
          currencyConversionFee: response.data.fx_fee || 0,
        },
      };
    } catch (error) {
      this.logger.error(`Hyperswitch payment failed: ${error.message}`);
      
      // Attempt fallback provider
      return this.attemptFallback(request, error);
    }
  }

  private async executeViaDirectProvider(request: PaymentRequest): Promise<PaymentResponse> {
    switch (request.paymentMethod) {
      case 'crypto_usdt_trc20':
      case 'crypto_usdt_erc20':
      case 'crypto_btc':
        return this.executeCryptoPayment(request);
      default:
        throw new Error(`Unsupported payment method: ${request.paymentMethod}`);
    }
  }

  private async executeCryptoPayment(request: PaymentRequest): Promise<PaymentResponse> {
    // Integration with Fireblocks or Circle for crypto payouts
    // This would use the Fireblocks SDK
    
    const fireblocks = this.getFireblocksClient();
    
    const tx = await fireblocks.createTransaction({
      assetId: this.mapCryptoAsset(request.paymentMethod),
      amount: String(request.amount / 100), // Convert from cents
      destination: {
        type: 'ONE_TIME_ADDRESS',
        oneTimeAddress: {
          address: request.recipientDetails.walletAddress,
          tag: request.recipientDetails.network,
        },
      },
      note: `Payout ${request.payoutId}`,
    });

    return {
      paymentId: tx.id,
      externalRef: tx.txHash || tx.id,
      status: 'processing',
      providerUsed: 'fireblocks',
      fees: {
        processingFee: 0,
        currencyConversionFee: 0,
      },
    };
  }

  // Webhook handler for async payment status updates
  async handlePaymentWebhook(
    provider: string,
    payload: any,
    signature: string,
  ): Promise<{ payoutId: string; status: string; details: any }> {
    // Verify webhook signature based on provider
    this.verifyWebhookSignature(provider, payload, signature);
    
    // Extract payout ID and status from provider-specific payload
    const normalized = this.normalizeWebhookPayload(provider, payload);
    
    return normalized;
  }

  private async attemptFallback(
    request: PaymentRequest,
    originalError: Error,
  ): Promise<PaymentResponse> {
    const providers = this.providerPriority[request.paymentMethod] || [];
    
    for (const provider of providers.slice(1)) { // Skip first (already tried)
      try {
        this.logger.log(`Attempting fallback provider: ${provider}`);
        const response = await this.hyperswitchClient.post('/payouts/create', {
          amount: request.amount,
          currency: request.currency,
          connector: provider,
          // ... rest of config
        });
        return this.mapResponse(response.data);
      } catch (err) {
        this.logger.warn(`Fallback provider ${provider} also failed`);
        continue;
      }
    }
    
    throw new Error(`All payment providers failed for ${request.paymentMethod}`);
  }
}
```

---

## 8. Data Models

### Core Database Schema (PostgreSQL)

```sql
-- =====================================================
-- MULTI-TENANT FOUNDATION
-- =====================================================

CREATE TABLE firms (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    config JSONB NOT NULL DEFAULT '{}',
    payout_config JSONB NOT NULL DEFAULT '{}',
    -- Example payout_config:
    -- {
    --   "base_profit_split": 0.80,
    --   "scaling_tiers": [...],
    --   "min_payout_amount": 50.00,
    --   "payout_frequency_days": 14,
    --   "first_payout_holding_days": 14,
    --   "consistency_rule_max_trade_pct": 0.30,
    --   "auto_approve_threshold": 500.00,
    --   "payment_methods": ["bank_transfer", "crypto_usdt", "paypal"],
    --   "payment_fee_structure": {...}
    -- }
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- =====================================================
-- TRADER & ACCOUNTS
-- =====================================================

CREATE TABLE traders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    firm_id UUID NOT NULL REFERENCES firms(id),
    email VARCHAR(255) NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    country_code CHAR(2),
    kyc_status VARCHAR(20) DEFAULT 'pending', -- pending, verified, rejected, expired
    kyc_verified_at TIMESTAMPTZ,
    risk_level VARCHAR(20) DEFAULT 'standard', -- standard, elevated, high
    tax_id VARCHAR(100),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(firm_id, email)
);

CREATE TABLE funded_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trader_id UUID NOT NULL REFERENCES traders(id),
    firm_id UUID NOT NULL REFERENCES firms(id),
    external_account_id VARCHAR(100), -- MT4/MT5 account number
    platform VARCHAR(20), -- mt4, mt5, ctrader
    account_size DECIMAL(15,2) NOT NULL, -- e.g., 100000.00
    initial_balance DECIMAL(15,2) NOT NULL,
    current_equity DECIMAL(15,2) NOT NULL,
    current_balance DECIMAL(15,2) NOT NULL,
    high_water_mark DECIMAL(15,2) NOT NULL,
    phase VARCHAR(30) NOT NULL, -- challenge_1, challenge_2, funded
    status VARCHAR(20) DEFAULT 'active', -- active, breached, suspended, closed
    profit_split_override DECIMAL(4,3), -- Firm can override per account
    total_payouts DECIMAL(15,2) DEFAULT 0,
    payout_count INT DEFAULT 0,
    consecutive_profitable_months INT DEFAULT 0,
    last_payout_date TIMESTAMPTZ,
    funded_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Ledger account references (TigerBeetle account IDs)
    ledger_profit_account_id VARCHAR(64),
    ledger_payable_account_id VARCHAR(64)
);

CREATE INDEX idx_funded_accounts_trader ON funded_accounts(trader_id);
CREATE INDEX idx_funded_accounts_firm ON funded_accounts(firm_id);
CREATE INDEX idx_funded_accounts_status ON funded_accounts(status);

-- =====================================================
-- PAYOUT REQUESTS
-- =====================================================

CREATE TABLE payout_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    firm_id UUID NOT NULL REFERENCES firms(id),
    trader_id UUID NOT NULL REFERENCES traders(id),
    funded_account_id UUID NOT NULL REFERENCES funded_accounts(id),
    
    -- Request details
    requested_amount DECIMAL(15,2),
    requested_currency VARCHAR(3) DEFAULT 'USD',
    payout_method VARCHAR(50) NOT NULL,
    payout_details JSONB NOT NULL, -- Payment method specific details
    
    -- Calculated amounts
    gross_profit DECIMAL(15,2),
    consistency_adjustment DECIMAL(15,2) DEFAULT 0,
    adjusted_gross_profit DECIMAL(15,2),
    profit_split_ratio DECIMAL(4,3),
    trader_share DECIMAL(15,2),
    firm_share DECIMAL(15,2),
    platform_fee DECIMAL(15,2) DEFAULT 0,
    payment_processing_fee DECIMAL(15,2) DEFAULT 0,
    tax_withholding DECIMAL(15,2) DEFAULT 0,
    currency_conversion_fee DECIMAL(15,2) DEFAULT 0,
    fx_rate DECIMAL(10,6) DEFAULT 1.0,
    final_payout_amount DECIMAL(15,2),
    payout_currency VARCHAR(3),
    
    -- Calculation audit
    calculation_snapshot JSONB, -- Full calculation steps
    hwm_at_calculation DECIMAL(15,2),
    new_hwm_after_payout DECIMAL(15,2),
    
    -- State machine
    status VARCHAR(30) NOT NULL DEFAULT 'requested',
    -- requested → validating → calculating → pending_approval → 
    -- approved → processing → sent → confirmed → completed
    -- Error: rejected, failed, reversed, on_hold, cancelled
    
    status_reason TEXT,
    
    -- Approval tracking
    approval_required BOOLEAN DEFAULT false,
    approved_by UUID,
    approved_at TIMESTAMPTZ,
    approval_notes TEXT,
    
    -- Payment tracking
    payment_provider VARCHAR(50),
    payment_external_ref VARCHAR(255),
    payment_sent_at TIMESTAMPTZ,
    payment_confirmed_at TIMESTAMPTZ,
    
    -- Ledger references
    ledger_reservation_id VARCHAR(64),
    ledger_confirmation_id VARCHAR(64),
    
    -- Workflow tracking
    temporal_workflow_id VARCHAR(255),
    temporal_run_id VARCHAR(255),
    
    -- Idempotency
    idempotency_key VARCHAR(255) UNIQUE,
    
    -- Timestamps
    requested_at TIMESTAMPTZ DEFAULT NOW(),
    processed_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_payout_requests_firm ON payout_requests(firm_id);
CREATE INDEX idx_payout_requests_trader ON payout_requests(trader_id);
CREATE INDEX idx_payout_requests_status ON payout_requests(status);
CREATE INDEX idx_payout_requests_date ON payout_requests(requested_at);
CREATE INDEX idx_payout_requests_idempotency ON payout_requests(idempotency_key);

-- =====================================================
-- PAYOUT STATUS HISTORY (Audit Trail)
-- =====================================================

CREATE TABLE payout_status_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    payout_request_id UUID NOT NULL REFERENCES payout_requests(id),
    from_status VARCHAR(30),
    to_status VARCHAR(30) NOT NULL,
    reason TEXT,
    changed_by UUID, -- User who triggered the change (null for system)
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_payout_history_request ON payout_status_history(payout_request_id);

-- =====================================================
-- PAYMENT METHODS (Trader's saved payment methods)
-- =====================================================

CREATE TABLE trader_payment_methods (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trader_id UUID NOT NULL REFERENCES traders(id),
    method_type VARCHAR(50) NOT NULL,
    label VARCHAR(100), -- "My USD Bank Account", "USDT Wallet"
    details JSONB NOT NULL, -- Encrypted payment details
    is_verified BOOLEAN DEFAULT false,
    is_default BOOLEAN DEFAULT false,
    currency VARCHAR(3),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- =====================================================
-- RECONCILIATION
-- =====================================================

CREATE TABLE reconciliation_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    payout_request_id UUID REFERENCES payout_requests(id),
    reconciliation_type VARCHAR(30), -- auto, manual
    status VARCHAR(20), -- matched, discrepancy, resolved
    expected_amount DECIMAL(15,2),
    actual_amount DECIMAL(15,2),
    discrepancy_amount DECIMAL(15,2),
    provider_ref VARCHAR(255),
    notes TEXT,
    resolved_by UUID,
    resolved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- =====================================================
-- PAYOUT SCHEDULES (For automated/scheduled payouts)
-- =====================================================

CREATE TABLE payout_schedules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    firm_id UUID NOT NULL REFERENCES firms(id),
    schedule_type VARCHAR(20) NOT NULL, -- biweekly, monthly, custom
    cron_expression VARCHAR(100),
    next_run_at TIMESTAMPTZ,
    last_run_at TIMESTAMPTZ,
    is_active BOOLEAN DEFAULT true,
    config JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- =====================================================
-- FEE SCHEDULES
-- =====================================================

CREATE TABLE fee_schedules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    firm_id UUID NOT NULL REFERENCES firms(id),
    payment_method VARCHAR(50) NOT NULL,
    fee_type VARCHAR(20) NOT NULL, -- fixed, percentage, tiered
    fixed_fee DECIMAL(10,2) DEFAULT 0,
    percentage_fee DECIMAL(5,4) DEFAULT 0,
    min_fee DECIMAL(10,2) DEFAULT 0,
    max_fee DECIMAL(10,2),
    currency VARCHAR(3) DEFAULT 'USD',
    is_active BOOLEAN DEFAULT true,
    effective_from TIMESTAMPTZ DEFAULT NOW(),
    effective_until TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 9. Security & Compliance

### Security Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    SECURITY LAYERS                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  LAYER 1: NETWORK SECURITY                                      │
│  • TLS 1.3 everywhere                                           │
│  • VPC / Private networking                                     │
│  • WAF (Web Application Firewall)                               │
│  • DDoS protection                                              │
│                                                                  │
│  LAYER 2: AUTHENTICATION & AUTHORIZATION                        │
│  • Keycloak for identity management                             │
│  • OAuth 2.0 + OIDC                                             │
│  • API keys for service-to-service                              │
│  • RBAC with OPA (Open Policy Agent)                            │
│  • MFA for admin/approval actions                               │
│                                                                  │
│  LAYER 3: DATA PROTECTION                                       │
│  • Encryption at rest (AES-256)                                 │
│  • Field-level encryption for PII & payment details             │
│  • Use HashiCorp Vault for secret management                    │
│  • Database-level encryption                                    │
│                                                                  │
│  LAYER 4: APPLICATION SECURITY                                  │
│  • Input validation on all endpoints                            │
│  • Idempotency keys for all mutations                           │
│  • Rate limiting per trader/firm                                │
│  • Request signing for webhooks                                 │
│  • CSRF protection                                              │
│                                                                  │
│  LAYER 5: FINANCIAL CONTROLS                                    │
│  • Double-entry ledger (always balanced)                        │
│  • Two-phase transfers (reserve then confirm)                   │
│  • Velocity checks (max payouts per period)                     │
│  • Amount limits per approval level                             │
│  • IP-based fraud detection                                     │
│  • Device fingerprinting                                        │
│                                                                  │
│  LAYER 6: AUDIT & COMPLIANCE                                    │
│  • Immutable audit trail (EventStoreDB)                         │
│  • All actions logged with actor, timestamp, details            │
│  • Sanctions screening (OFAC, EU sanctions via OpenSanctions)   │
│  • KYC verification (Sumsub / Jumio integration)                │
│  • Periodic access reviews                                      │
│  • SOC 2 readiness                                              │
└─────────────────────────────────────────────────────────────────┘
```

### PII Encryption Strategy

```typescript
// encryption.service.ts - Field-level encryption for sensitive data

import { Injectable } from '@nestjs/common';
import * as crypto from 'crypto';

// Use HashiCorp Vault in production
// This is a simplified example

@Injectable()
export class EncryptionService {
  private readonly algorithm = 'aes-256-gcm';
  
  // In production, fetch from Vault
  private readonly masterKey = Buffer.from(process.env.ENCRYPTION_MASTER_KEY, 'hex');

  encrypt(plaintext: string): EncryptedField {
    const iv = crypto.randomBytes(16);
    const cipher = crypto.createCipheriv(this.algorithm, this.masterKey, iv);
    
    let encrypted = cipher.update(plaintext, 'utf8', 'hex');
    encrypted += cipher.final('hex');
    const authTag = cipher.getAuthTag();

    return {
      ciphertext: encrypted,
      iv: iv.toString('hex'),
      authTag: authTag.toString('hex'),
      version: 1, // Key version for rotation
    };
  }

  decrypt(field: EncryptedField): string {
    const decipher = crypto.createDecipheriv(
      this.algorithm,
      this.masterKey,
      Buffer.from(field.iv, 'hex')
    );
    decipher.setAuthTag(Buffer.from(field.authTag, 'hex'));
    
    let decrypted = decipher.update(field.ciphertext, 'hex', 'utf8');
    decrypted += decipher.final('utf8');
    return decrypted;
  }

  // Encrypt payment details before storing
  encryptPaymentDetails(details: any): string {
    const json = JSON.stringify(details);
    const encrypted = this.encrypt(json);
    return JSON.stringify(encrypted);
  }

  decryptPaymentDetails(encryptedJson: string): any {
    const encrypted = JSON.parse(encryptedJson) as EncryptedField;
    const json = this.decrypt(encrypted);
    return JSON.parse(json);
  }
}
```

---

## 10. Scalability & Reliability Patterns

### Key Patterns Implemented

```
┌─────────────────────────────────────────────────────────────────┐
│              RELIABILITY PATTERNS                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. IDEMPOTENCY                                                 │
│     • Every payout request has a unique idempotency key         │
│     • Retries produce the same result                           │
│     • Stored in Redis with TTL + PostgreSQL for persistence     │
│                                                                  │
│  2. SAGA PATTERN (via Temporal)                                 │
│     • Each step has a compensating action                       │
│     • Ledger reservation → Payment → Confirm                   │
│     • If payment fails → Reverse ledger reservation             │
│                                                                  │
│  3. CIRCUIT BREAKER                                             │
│     • Per payment provider                                      │
│     • If provider fails 5x in 1 minute → Open circuit          │
│     • Auto-failover to next provider                            │
│     • Half-open after 30 seconds                                │
│                                                                  │
│  4. OUTBOX PATTERN                                              │
│     • Database writes + event publication in same transaction   │
│     • Prevents lost events                                      │
│     • Debezium or custom outbox reader                          │
│                                                                  │
│  5. TWO-PHASE TRANSFERS                                         │
│     • Reserve funds in ledger (pending)                         │
│     • Execute payment                                           │
│     • Confirm or void the ledger entry                          │
│     • Prevents double-spend                                     │
│                                                                  │
│  6. DISTRIBUTED LOCKING                                         │
│     • Redis-based locks (Redlock) for payout processing         │
│     • Prevents concurrent payouts for same account              │
│     • Lock key: "payout:lock:{funded_account_id}"               │
│                                                                  │
│  7. RATE LIMITING                                               │
│     • Per trader: Max 1 payout request per hour                 │
│     • Per firm: Max 100 payouts per batch cycle                 │
│     • Per payment provider: Respect provider rate limits        │
│                                                                  │
│  8. DEAD LETTER QUEUE                                           │
│     • Failed events after max retries → DLQ                    │
│     • Manual review and replay capability                       │
│     • Alerting on DLQ depth                                     │
│                                                                  │
│  9. RECONCILIATION JOBS                                         │
│     • Daily: Match ledger entries with payment provider data    │
│     • Weekly: Full balance reconciliation                       │
│     • Monthly: Cross-system audit                               │
│                                                                  │
│  10. GRACEFUL DEGRADATION                                       │
│      • If notification service down → Don't fail payout        │
│      • If analytics down → Don't fail payout                   │
│      • Core path: Validate → Calculate → Reserve → Pay → Confirm│
│      • Non-critical: Notify, Analytics, Reports                 │
└─────────────────────────────────────────────────────────────────┘
```

### Distributed Locking for Payout Safety

```typescript
// distributed-lock.service.ts

import { Injectable } from '@nestjs/common';
import Redis from 'ioredis';
import Redlock from 'redlock';

@Injectable()
export class PayoutLockService {
  private redlock: Redlock;

  constructor(private readonly redis: Redis) {
    this.redlock = new Redlock([redis], {
      driftFactor: 0.01,
      retryCount: 10,
      retryDelay: 200,
      retryJitter: 200,
      automaticExtensionThreshold: 500,
    });
  }

  /**
   * Acquire a lock on a funded account to prevent concurrent payouts.
   * Only one payout can be processed per funded account at a time.
   */
  async withPayoutLock<T>(
    fundedAccountId: string,
    ttlMs: number,
    fn: () => Promise<T>,
  ): Promise<T> {
    const lockKey = `payout:lock:${fundedAccountId}`;
    
    const lock = await this.redlock.acquire([lockKey], ttlMs);
    
    try {
      return await fn();
    } finally {
      await lock.release();
    }
  }

  /**
   * Idempotency check - ensure we don't process the same payout twice
   */
  async checkAndSetIdempotencyKey(
    idempotencyKey: string,
    ttlSeconds: number = 86400, // 24 hours
  ): Promise<{ isDuplicate: boolean; existingResult?: any }> {
    const key = `payout:idempotency:${idempotencyKey}`;
    
    const existing = await this.redis.get(key);
    if (existing) {
      return { isDuplicate: true, existingResult: JSON.parse(existing) };
    }
    
    // Set with NX (only if not exists)
    const set = await this.redis.set(key, 'processing', 'EX', ttlSeconds, 'NX');
    if (!set) {
      // Race condition - another process set it
      const result = await this.redis.get(key);
      return { isDuplicate: true, existingResult: result ? JSON.parse(result) : null };
    }
    
    return { isDuplicate: false };
  }

  async setIdempotencyResult(
    idempotencyKey: string,
    result: any,
    ttlSeconds: number = 86400,
  ): Promise<void> {
    const key = `payout:idempotency:${idempotencyKey}`;
    await this.redis.set(key, JSON.stringify(result), 'EX', ttlSeconds);
  }
}
```

---

## 11. Technology Stack Recommendation

### Primary Stack

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| **Primary Language** | **Go** or **TypeScript (Node.js)** | Go for performance-critical services; TypeScript for rapid development |
| **API Framework** | **NestJS** (TS) or **Fiber** (Go) | Enterprise patterns, DI, modular |
| **Primary Database** | **PostgreSQL 16** + **Citus** | Relational, multi-tenant, proven |
| **Ledger Database** | **TigerBeetle** or **Blnk Finance** | Purpose-built for financial accounting |
| **Workflow Engine** | **Temporal.io** | Payout lifecycle orchestration |
| **Message Broker** | **Redpanda** (Kafka-compatible) | Event streaming, simpler ops |
| **Cache + Locks** | **Redis 7** (or **Dragonfly**) | Caching, distributed locks, rate limiting |
| **Payment Orchestration** | **Hyperswitch** | Multi-provider payment routing |
| **Rules Engine** | **json-rules-engine** or **GoRules** | Configurable business rules |
| **Notifications** | **Novu** | Multi-channel notifications |
| **Identity/Auth** | **Keycloak** | Auth, RBAC, multi-tenancy |
| **Audit Trail** | **EventStoreDB** | Immutable event history |
| **Object Storage** | **MinIO** | Documents, reports, exports |
| **Search/Logs** | **Elasticsearch** or **Meilisearch** | Log aggregation, search |
| **Monitoring** | **Grafana + Prometheus + Loki** | Metrics, dashboards, alerts |
| **Tracing** | **OpenTelemetry + Jaeger** | Distributed tracing |
| **Container Orchestration** | **Kubernetes** | Deployment, scaling |
| **CI/CD** | **GitHub Actions + ArgoCD** | Continuous deployment |
| **Secrets Management** | **HashiCorp Vault** | Encryption keys, API keys |

---

## 12. Build vs Buy Analysis

### What to Build Custom vs What to Use Off-the-Shelf

```
┌─────────────────────────────────────────────────────────────────────┐
│                    BUILD vs USE OPEN-SOURCE vs BUY                   │
├───────────────────┬──────────────────┬──────────────────────────────┤
│  COMPONENT        │  RECOMMENDATION  │  RATIONALE                   │
├───────────────────┼──────────────────┼──────────────────────────────┤
│ Profit Calc Engine│  BUILD           │ Core business logic, unique  │
│                   │                  │ to prop firm domain          │
├───────────────────┼──────────────────┼──────────────────────────────┤
│ Payout Orchestr.  │  BUILD on        │ Use Temporal for infra,     │
│                   │  TEMPORAL        │ custom workflow logic        │
├───────────────────┼──────────────────┼──────────────────────────────┤
│ Ledger/Accounting │  USE TIGERBEETLE │ Don't build a ledger from   │
│                   │  or BLNK         │ scratch, use purpose-built  │
├───────────────────┼──────────────────┼──────────────────────────────┤
│ Payment Gateway   │  USE HYPERSWITCH │ Don't integrate 10+         │
│                   │                  │ providers yourself           │
├───────────────────┼──────────────────┼──────────────────────────────┤
│ Rules Engine      │  USE json-rules  │ Configurable rules that     │
│                   │  -engine/GoRules │ firms can customize          │
├───────────────────┼──────────────────┼──────────────────────────────┤
│ Notifications     │  USE NOVU        │ Multi-channel notifications │
│                   │                  │ is a solved problem          │
├───────────────────┼──────────────────┼──────────────────────────────┤
│ Auth/Identity     │  USE KEYCLOAK    │ Don't build auth from       │
│                   │                  │ scratch, ever                │
├───────────────────┼──────────────────┼──────────────────────────────┤
│ KYC/AML           │  BUY (Sumsub,   │ Compliance is not DIY       │
│                   │  Jumio, Onfido)  │                              │
├───────────────────┼──────────────────┼──────────────────────────────┤
│ Sanctions Screen. │  USE MOOV.IO +   │ Open data + open tooling   │
│                   │  OPENSANCTIONS   │                              │
├───────────────────┼──────────────────┼──────────────────────────────┤
│ Event Streaming   │  USE REDPANDA    │ Don't build message broker  │
├───────────────────┼──────────────────┼──────────────────────────────┤
│ Monitoring        │  USE GRAFANA     │ Industry standard            │
│                   │  STACK           │                              │
├───────────────────┼──────────────────┼──────────────────────────────┤
│ API Gateway       │  USE KONG/APISIX │ Mature, plugin ecosystem    │
├───────────────────┼──────────────────┼──────────────────────────────┤
│ Admin Dashboard   │  BUILD with      │ Use admin frameworks,       │
│                   │  Refine/AdminJS  │ customize for domain        │
├───────────────────┼──────────────────┼──────────────────────────────┤
│ Trader Portal     │  BUILD           │ Core product experience     │
├───────────────────┼──────────────────┼──────────────────────────────┤
│ Reconciliation    │  BUILD           │ Domain-specific logic       │
│ Engine            │                  │ with scheduled jobs          │
├───────────────────┼──────────────────┼──────────────────────────────┤
│ Reporting/        │  BUILD on        │ Use Metabase/Superset for   │
│ Analytics         │  METABASE/       │ ad-hoc, custom for core     │
│                   │  SUPERSET        │                              │
└───────────────────┴──────────────────┴──────────────────────────────┘
```

### Effort Savings Estimate

| Area | Without Open-Source | With Open-Source | Savings |
|------|-------------------|------------------|---------|
| Ledger System | 3-4 months | 2-3 weeks | ~85% |
| Payment Integration | 4-6 months | 1-2 months | ~70% |
| Workflow Engine | 2-3 months | 2-3 weeks | ~80% |
| Notifications | 1-2 months | 1 week | ~90% |
| Auth/Identity | 2-3 months | 2 weeks | ~85% |
| Monitoring | 1-2 months | 1 week | ~90% |
| Rules Engine | 1-2 months | 2 weeks | ~75% |
| **Total Estimate** | **16-24 months** | **5-8 months** | **~65-70%** |

---

## 13. Implementation Roadmap

### Phase 1: Foundation (Weeks 1-6)

```
PHASE 1: FOUNDATION
├── Week 1-2: Infrastructure Setup
│   ├── Kubernetes cluster setup
│   ├── PostgreSQL + Redis deployment
│   ├── Keycloak setup with multi-tenancy
│   ├── Temporal.io deployment
│   ├── Redpanda deployment
│   ├── Grafana + Prometheus stack
│   └── CI/CD pipeline (GitHub Actions + ArgoCD)
│
├── Week 3-4: Core Data Models & Services
│   ├── Database schema migration (Flyway/Alembic)
│   ├── Firm management service
│   ├── Trader management service
│   ├── Funded account service
│   ├── Basic API gateway setup (Kong)
│   └── Authentication flows
│
├── Week 5-6: Ledger Setup
│   ├── TigerBeetle deployment & configuration
│   ├── Ledger service implementation
│   ├── Account creation flows
│   ├── Basic transfer operations
│   └── Balance query APIs
```

### Phase 2: Payout Core (Weeks 7-12)

```
PHASE 2: PAYOUT CORE
├── Week 7-8: Profit Calculation Engine
│   ├── Implement calculation engine
│   ├── High water mark tracking
│   ├── Consistency rules
│   ├── Profit split calculation with scaling
│   ├── Fee calculation
│   └── Comprehensive unit tests
│
├── Week 9-10: Payout Workflow
│   ├── Temporal workflow definition
│   ├── Activity implementations
│   ├── State machine transitions
│   ├── Idempotency handling
│   ├── Error handling & compensation
│   └── Basic approval workflow
│
├── Week 11-12: Payment Integration
│   ├── Hyperswitch deployment & configuration
│   ├── Bank transfer integration (Wise/Stripe Connect)
│   ├── Crypto payout integration (Fireblocks/Circle)
│   ├── Webhook handlers
│   ├── Payment status tracking
│   └── Circuit breaker implementation
```

### Phase 3: Operations & Compliance (Weeks 13-18)

```
PHASE 3: OPERATIONS & COMPLIANCE
├── Week 13-14: Approval Workflows
│   ├── Configurable approval rules per firm
│   ├── Multi-level approval chains
│   ├── Auto-approval rules (json-rules-engine)
│   ├── Approval dashboard
│   └── SLA tracking & escalation
│
├── Week 15-16: Compliance & KYC
│   ├── KYC integration (Sumsub)
│   ├── Sanctions screening (OpenSanctions + Moov.io)
│   ├── Compliance holds & flags
│   ├── Risk scoring
│   └── Audit trail (EventStoreDB)
│
├── Week 17-18: Notifications & Monitoring
│   ├── Novu setup & notification templates
│   ├── Email/SMS/in-app notifications
│   ├── Grafana dashboards (payout metrics)
│   ├── Alerting rules
│   ├── OpenTelemetry instrumentation
│   └── Error tracking (Sentry)
```

### Phase 4: Polish & Scale (Weeks 19-24)

```
PHASE 4: POLISH & SCALE
├── Week 19-20: Reconciliation & Reporting
│   ├── Daily reconciliation jobs
│   ├── Discrepancy detection
│   ├── Management reports
│   ├── Trader payout history
│   ├── Firm analytics dashboard
│   └── Export capabilities (CSV, PDF)
│
├── Week 21-22: White-Label Features
│   ├── Firm onboarding wizard
│   ├── Per-firm configuration UI
│   ├── Custom branding support
│   ├── Firm-specific payout rules
│   └── Multi-tenant data isolation testing
│
├── Week 23-24: Testing & Hardening
│   ├── Load testing (k6/Gatling)
│   ├── Chaos engineering tests
│   ├── Security audit
│   ├── Penetration testing
│   ├── Disaster recovery testing
│   ├── Documentation
│   └── Runbook creation
```

---

## Summary: Open-Source Stack Quick Reference

| Need | Open-Source Solution | GitHub Stars | Maturity |
|------|---------------------|-------------|----------|
| **Ledger** | TigerBeetle | 9k+ | Growing rapidly |
| **Ledger (Alt)** | Blnk Finance | 600+ | Newer, fintech-focused |
| **Workflow** | Temporal.io | 10k+ | Production-proven |
| **Payments** | Hyperswitch | 11k+ | Production-proven |
| **Rules Engine** | json-rules-engine | 2k+ | Stable |
| **Rules (Visual)** | GoRules Zen | 600+ | Growing |
| **Notifications** | Novu | 33k+ | Production-proven |
| **Auth** | Keycloak | 20k+ | Enterprise standard |
| **Event Store** | EventStoreDB | 5k+ | Production-proven |
| **Streaming** | Redpanda | 9k+ | Production-proven |
| **Sanctions** | OpenSanctions | 500+ | Active development |
| **Payment Rails** | Moov.io | 4k+ | Production-proven |
| **Monitoring** | Grafana | 61k+ | Industry standard |
| **API Gateway** | Kong | 38k+ | Enterprise standard |
| **Secrets** | HashiCorp Vault | 30k+ | Industry standard |
| **Admin Panel** | Refine | 25k+ | Production-proven |
| **Analytics** | Apache Superset | 59k+ | Production-proven |

---

### Final Recommendation

**Build custom only what is your core competitive advantage** (profit calculation logic, trading platform integration, payout rules specific to prop firms). For everything else — ledger, payments, workflows, notifications, auth, monitoring — **leverage the mature open-source ecosystem**. This approach can reduce your time-to-market from 18-24 months to **5-8 months** while achieving higher reliability than building everything from scratch.

The combination of **Temporal (orchestration) + TigerBeetle (ledger) + Hyperswitch (payments) + Novu (notifications) + Keycloak (auth)** gives you an extremely solid foundation that would cost millions to build from scratch and is battle-tested by thousands of companies.
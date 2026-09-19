# Comprehensive Research: Enterprise-Grade Multi-Tenant Management Module for Prop Firm as a Service (PFaaS) Platform

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Industry Context & Market Analysis](#2-industry-context--market-analysis)
3. [Multi-Tenancy Architecture Patterns](#3-multi-tenancy-architecture-patterns)
4. [Core Module Design](#4-core-module-design)
5. [Tenant Lifecycle Management](#5-tenant-lifecycle-management)
6. [Data Architecture & Isolation](#6-data-architecture--isolation)
7. [Identity, Authentication & Authorization](#7-identity-authentication--authorization)
8. [Billing & Subscription Management](#8-billing--subscription-management)
9. [White-Label & Customization Engine](#9-white-label--customization-engine)
10. [Trading Infrastructure Integration](#10-trading-infrastructure-integration)
11. [Compliance & Regulatory Framework](#11-compliance--regulatory-framework)
12. [Performance, Scalability & Reliability](#12-performance-scalability--reliability)
13. [Security Architecture](#13-security-architecture)
14. [Monitoring, Observability & Analytics](#14-monitoring-observability--analytics)
15. [API Design & Integration Layer](#15-api-design--integration-layer)
16. [Technology Stack Recommendations](#16-technology-stack-recommendations)
17. [Database Schema Design](#17-database-schema-design)
18. [Implementation Roadmap](#18-implementation-roadmap)
19. [Cost Analysis & Infrastructure Planning](#19-cost-analysis--infrastructure-planning)
20. [Risk Assessment & Mitigation](#20-risk-assessment--mitigation)

---

## 1. Executive Summary

### What is a Prop Firm as a Service (PFaaS) Platform?

A **Proprietary Trading Firm as a Service** platform enables entrepreneurs and organizations to launch, operate, and scale their own proprietary trading firm without building the underlying technology infrastructure from scratch. The platform operator (you) provides the technology backbone, and each **tenant** is an independent prop firm serving their own traders (end-users).

### The Multi-Tenant Management Module

The Multi-Tenant Management Module is the **central nervous system** of the PFaaS platform. It is responsible for:

- **Tenant Isolation**: Ensuring each prop firm's data, configurations, traders, and financial operations are completely isolated
- **Tenant Lifecycle**: Provisioning, configuring, scaling, suspending, and decommissioning tenants
- **White-Label Support**: Allowing each tenant to operate under their own brand
- **Resource Management**: Fair allocation of compute, storage, and trading resources
- **Billing & Metering**: Tracking usage and managing subscription tiers
- **Compliance Orchestration**: Enforcing regulatory requirements per jurisdiction
- **Centralized Administration**: Platform-level oversight while maintaining tenant autonomy

### Stakeholder Hierarchy

```
┌─────────────────────────────────────────────────────┐
│                PLATFORM OPERATOR (You)               │
│  ┌───────────────────────────────────────────────┐  │
│  │         SUPER ADMIN / PLATFORM ADMIN          │  │
│  └───────────────────────────────────────────────┘  │
│                                                     │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐  │
│  │  TENANT A   │ │  TENANT B   │ │  TENANT C   │  │
│  │ (Prop Firm) │ │ (Prop Firm) │ │ (Prop Firm) │  │
│  │             │ │             │ │             │  │
│  │ ┌─────────┐ │ │ ┌─────────┐ │ │ ┌─────────┐ │  │
│  │ │Firm     │ │ │ │Firm     │ │ │ │Firm     │ │  │
│  │ │Admins   │ │ │ │Admins   │ │ │ │Admins   │ │  │
│  │ ├─────────┤ │ │ ├─────────┤ │ │ ├─────────┤ │  │
│  │ │Managers │ │ │ │Managers │ │ │ │Managers │ │  │
│  │ ├─────────┤ │ │ ├─────────┤ │ │ ├─────────┤ │  │
│  │ │Risk     │ │ │ │Risk     │ │ │ │Risk     │ │  │
│  │ │Officers │ │ │ │Officers │ │ │ │Officers │ │  │
│  │ ├─────────┤ │ │ ├─────────┤ │ │ ├─────────┤ │  │
│  │ │Traders  │ │ │ │Traders  │ │ │ │Traders  │ │  │
│  │ │(100s-   │ │ │ │(100s-   │ │ │ │(100s-   │ │  │
│  │ │1000s)   │ │ │ │1000s)   │ │ │ │1000s)   │ │  │
│  │ └─────────┘ │ │ └─────────┘ │ │ └─────────┘ │  │
│  └─────────────┘ └─────────────┘ └─────────────┘  │
└─────────────────────────────────────────────────────┘
```

---

## 2. Industry Context & Market Analysis

### 2.1 Prop Trading Industry Landscape

**Traditional Model:**
- Proprietary trading firms trade using the firm's own capital
- Traders are evaluated through challenges/assessments
- Successful traders receive funded accounts
- Firm profits from challenge fees + profit splits

**PFaaS Model:**
- The platform provides infrastructure for multiple prop firms
- Each tenant operates independently with their own brand
- Platform monetizes through SaaS subscriptions + revenue share

### 2.2 Key Market Players & Competitive Analysis

| Platform Type | Examples | Model |
|---|---|---|
| Established Prop Firms | FTMO, MyForexFunds, The5ers | Single-firm, proprietary tech |
| White-Label Providers | ThinkTrader, cTrader White Label | Platform licensing |
| PFaaS Platforms | Emerging category | Multi-tenant SaaS |
| Trading Platforms | MetaTrader, TradingView | Infrastructure only |

### 2.3 Business Requirements Derived from Market

1. **Rapid Tenant Onboarding**: New prop firm operational within hours, not months
2. **Challenge/Evaluation Management**: Configurable evaluation programs per tenant
3. **Funded Account Management**: Capital allocation, profit-split tracking
4. **Risk Management**: Real-time per-trader and per-tenant risk controls
5. **Payout Processing**: Automated profit calculations and payouts
6. **Regulatory Compliance**: KYC/AML per jurisdiction
7. **Scalability**: Support hundreds of tenants with thousands of traders each
8. **White-Label**: Complete branding customization

---

## 3. Multi-Tenancy Architecture Patterns

### 3.1 Architecture Pattern Comparison

#### Pattern 1: Shared Database, Shared Schema (Row-Level Isolation)

```
┌──────────────────────────────────────┐
│          Single Database             │
│  ┌────────────────────────────────┐  │
│  │         traders table          │  │
│  │  id | tenant_id | name | ...  │  │
│  │  1  | tenant_a  | John | ...  │  │
│  │  2  | tenant_b  | Jane | ...  │  │
│  │  3  | tenant_a  | Bob  | ...  │  │
│  └────────────────────────────────┘  │
└──────────────────────────────────────┘
```

| Pros | Cons |
|---|---|
| Lowest infrastructure cost | Noisy neighbor risk |
| Simplest deployment | Single point of failure |
| Easy cross-tenant analytics | Complex data isolation logic |
| Efficient resource utilization | Harder to comply with data residency |

#### Pattern 2: Shared Database, Separate Schemas

```
┌──────────────────────────────────────┐
│          Single Database             │
│  ┌──────────┐  ┌──────────┐         │
│  │ schema_a │  │ schema_b │  ...    │
│  │ traders  │  │ traders  │         │
│  │ accounts │  │ accounts │         │
│  │ trades   │  │ trades   │         │
│  └──────────┘  └──────────┘         │
└──────────────────────────────────────┘
```

| Pros | Cons |
|---|---|
| Better isolation than row-level | Schema migration complexity |
| Moderate cost | Database connection limits |
| Easier per-tenant backup/restore | Still shared database resources |

#### Pattern 3: Separate Databases per Tenant

```
┌──────────┐  ┌──────────┐  ┌──────────┐
│  DB_A    │  │  DB_B    │  │  DB_C    │
│ traders  │  │ traders  │  │ traders  │
│ accounts │  │ accounts │  │ accounts │
│ trades   │  │ trades   │  │ trades   │
└──────────┘  └──────────┘  └──────────┘
```

| Pros | Cons |
|---|---|
| Strongest isolation | Highest cost |
| Independent scaling | Complex deployment |
| Easy data residency compliance | Cross-tenant queries difficult |
| Per-tenant backup/restore | Connection management overhead |

#### Pattern 4: Hybrid Approach (Recommended for PFaaS)

```
┌─────────────────────────────────────────────────┐
│              PLATFORM DATABASE                   │
│  (Tenant registry, billing, platform config)    │
└─────────────────────────────────────────────────┘
                    │
        ┌───────────┼───────────┐
        ▼           ▼           ▼
┌──────────┐ ┌──────────┐ ┌──────────┐
│ Shard 1  │ │ Shard 2  │ │ Shard 3  │
│(Tenants  │ │(Tenants  │ │(Tenants  │
│ A,B,C)   │ │ D,E,F)   │ │ G,H,I)   │
│ Schemas  │ │ Schemas  │ │ Schemas  │
│ per      │ │ per      │ │ per      │
│ tenant   │ │ tenant   │ │ tenant   │
└──────────┘ └──────────┘ └──────────┘
        │
        ▼ (Premium tenants get dedicated)
┌──────────────┐
│ Dedicated DB │
│ (Enterprise  │
│  Tenant X)   │
└──────────────┘
```

### 3.2 Recommended Architecture: Hybrid with Tiered Isolation

**Rationale for Prop Firm context:**

- **Platform-level data** (tenant registry, billing, feature flags): Shared database
- **Standard tenants**: Shared database with schema-per-tenant or row-level isolation using PostgreSQL Row-Level Security (RLS)
- **Premium/Enterprise tenants**: Dedicated database instances
- **Trading data**: Time-series optimized storage (TimescaleDB/QuestDB) with tenant partitioning
- **Sensitive data** (KYC documents, financial records): Encrypted at rest with tenant-specific keys

### 3.3 Application-Level Multi-Tenancy

```
┌─────────────────────────────────────────────────────────────┐
│                      API GATEWAY                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Tenant Resolution Middleware                        │    │
│  │  (subdomain / header / JWT claim / API key)         │    │
│  └─────────────────────────────────────────────────────┘    │
│                          │                                   │
│                          ▼                                   │
│  ┌─────────────────────────────────────────────────────┐    │
│  │           Tenant Context Injection                   │    │
│  │  (Thread-local / AsyncLocal / Request-scoped DI)    │    │
│  └─────────────────────────────────────────────────────┘    │
│                          │                                   │
│          ┌───────────────┼───────────────┐                  │
│          ▼               ▼               ▼                  │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐       │
│  │  Service A   │ │  Service B   │ │  Service C   │       │
│  │  (Trading)   │ │  (Risk)      │ │  (Billing)   │       │
│  │              │ │              │ │              │        │
│  │  TenantCtx   │ │  TenantCtx   │ │  TenantCtx  │       │
│  │  Auto-filter │ │  Auto-filter │ │  Auto-filter │       │
│  └──────────────┘ └──────────────┘ └──────────────┘       │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. Core Module Design

### 4.1 Module Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│              MULTI-TENANT MANAGEMENT MODULE                      │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                TENANT MANAGEMENT CORE                     │   │
│  │  ┌────────────┐ ┌──────────┐ ┌────────────┐ ┌────────┐  │   │
│  │  │ Tenant     │ │ Tenant   │ │ Tenant     │ │Config  │  │   │
│  │  │ Registry   │ │Lifecycle │ │ Discovery  │ │Manager │  │   │
│  │  └────────────┘ └──────────┘ └────────────┘ └────────┘  │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────────────┐    │
│  │   IDENTITY   │ │  BILLING &   │ │   WHITE-LABEL        │    │
│  │   & ACCESS   │ │  METERING    │ │   ENGINE             │    │
│  │  ┌────────┐  │ │ ┌──────────┐ │ │ ┌────────────────┐   │    │
│  │  │ AuthN  │  │ │ │Subscribe │ │ │ │ Theme Manager  │   │    │
│  │  ├────────┤  │ │ ├──────────┤ │ │ ├────────────────┤   │    │
│  │  │ AuthZ  │  │ │ │ Usage    │ │ │ │ Domain Manager │   │    │
│  │  ├────────┤  │ │ │ Metering │ │ │ ├────────────────┤   │    │
│  │  │ RBAC   │  │ │ ├──────────┤ │ │ │ Email Template │   │    │
│  │  ├────────┤  │ │ │ Invoice  │ │ │ ├────────────────┤   │    │
│  │  │ SSO    │  │ │ │Generator │ │ │ │ Asset Manager  │   │    │
│  │  └────────┘  │ │ └──────────┘ │ │ └────────────────┘   │    │
│  └──────────────┘ └──────────────┘ └──────────────────────┘    │
│                                                                  │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────────────┐    │
│  │  RESOURCE    │ │  COMPLIANCE  │ │   DATA ISOLATION     │    │
│  │  MANAGEMENT  │ │  ENGINE      │ │   LAYER              │    │
│  │ ┌──────────┐ │ │ ┌──────────┐ │ │ ┌────────────────┐   │    │
│  │ │ Quotas   │ │ │ │ KYC/AML  │ │ │ │ Tenant Context │   │    │
│  │ ├──────────┤ │ │ ├──────────┤ │ │ ├────────────────┤   │    │
│  │ │ Rate     │ │ │ │ Audit    │ │ │ │ Query Filter   │   │    │
│  │ │ Limiting │ │ │ │ Logger   │ │ │ ├────────────────┤   │    │
│  │ ├──────────┤ │ │ ├──────────┤ │ │ │ Connection     │   │    │
│  │ │ Resource │ │ │ │ Data     │ │ │ │ Router         │   │    │
│  │ │ Pools    │ │ │ │ Residency│ │ │ ├────────────────┤   │    │
│  │ └──────────┘ │ │ └──────────┘ │ │ │ Encryption     │   │    │
│  └──────────────┘ └──────────────┘ │ │ Manager        │   │    │
│                                     │ └────────────────┘   │    │
│                                     └──────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 Tenant Entity Model

```typescript
// Core Tenant Entity
interface Tenant {
  // Identity
  id: UUID;
  slug: string;                    // URL-safe identifier
  externalId: string;              // For external system integration
  
  // Basic Information
  firmName: string;
  legalEntityName: string;
  registrationNumber: string;
  taxId: string;
  
  // Contact
  primaryContactName: string;
  primaryContactEmail: string;
  primaryContactPhone: string;
  supportEmail: string;
  
  // Address
  registeredAddress: Address;
  operationalAddress: Address;
  
  // Status & Lifecycle
  status: TenantStatus;
  tier: TenantTier;
  onboardingState: OnboardingState;
  
  // Configuration
  settings: TenantSettings;
  features: FeatureFlags;
  limits: TenantLimits;
  
  // White Label
  branding: BrandingConfig;
  customDomain: DomainConfig;
  
  // Billing
  billingConfig: BillingConfig;
  subscriptionId: string;
  
  // Compliance
  jurisdiction: string;
  regulatoryStatus: RegulatoryStatus;
  kybStatus: KYBStatus;          // Know Your Business
  
  // Technical
  dataRegion: DataRegion;
  isolationLevel: IsolationLevel;
  databaseConnectionString: string; // encrypted
  
  // Audit
  createdAt: DateTime;
  createdBy: UUID;
  updatedAt: DateTime;
  updatedBy: UUID;
  activatedAt: DateTime;
  suspendedAt: DateTime;
  terminatedAt: DateTime;
  
  // Metadata
  metadata: Record<string, any>;
  tags: string[];
}

enum TenantStatus {
  PENDING_APPROVAL = 'pending_approval',
  PROVISIONING = 'provisioning',
  ONBOARDING = 'onboarding',
  ACTIVE = 'active',
  SUSPENDED = 'suspended',
  DEACTIVATED = 'deactivated',
  PENDING_DELETION = 'pending_deletion',
  DELETED = 'deleted',
  ARCHIVED = 'archived'
}

enum TenantTier {
  STARTER = 'starter',
  PROFESSIONAL = 'professional',
  ENTERPRISE = 'enterprise',
  CUSTOM = 'custom'
}

enum IsolationLevel {
  SHARED = 'shared',              // Row-level isolation
  SCHEMA = 'schema',              // Schema-per-tenant
  DEDICATED = 'dedicated',        // Dedicated database
  ISOLATED = 'isolated'           // Dedicated infrastructure
}

interface TenantLimits {
  maxTraders: number;
  maxActiveAccounts: number;
  maxChallengesPerMonth: number;
  maxFundedCapital: number;
  maxConcurrentConnections: number;
  apiRateLimit: number;           // requests per minute
  storageQuotaGB: number;
  dataRetentionDays: number;
  maxAdminUsers: number;
  maxCustomRules: number;
}

interface TenantSettings {
  // Trading
  tradingConfig: TradingConfig;
  supportedInstruments: string[];
  supportedPlatforms: TradingPlatform[];
  
  // Challenge/Evaluation
  challengeTemplates: ChallengeTemplate[];
  evaluationRules: EvaluationRule[];
  
  // Risk Management
  riskParameters: RiskParameters;
  
  // Payouts
  payoutConfig: PayoutConfig;
  supportedPaymentMethods: PaymentMethod[];
  
  // Communication
  emailConfig: EmailConfig;
  notificationConfig: NotificationConfig;
  
  // Localization
  defaultLanguage: string;
  supportedLanguages: string[];
  defaultCurrency: string;
  timezone: string;
}
```

### 4.3 Sub-Module Breakdown

#### 4.3.1 Tenant Registry Service

```
Responsibilities:
├── CRUD operations for tenant entities
├── Tenant search and discovery
├── Tenant metadata management
├── Tenant tagging and categorization
├── Tenant relationship mapping (parent/child tenants)
└── Tenant export/import
```

#### 4.3.2 Tenant Lifecycle Service

```
Responsibilities:
├── Tenant provisioning orchestration
├── State machine management
├── Onboarding workflow
├── Suspension/reactivation
├── Tenant migration
├── Tenant archival
└── Tenant deletion (with data cleanup)
```

#### 4.3.3 Tenant Configuration Service

```
Responsibilities:
├── Dynamic configuration management
├── Feature flag management
├── Configuration inheritance (platform → tier → tenant)
├── Configuration validation
├── Configuration versioning
├── Hot-reload support
└── Configuration audit trail
```

#### 4.3.4 Tenant Resolution Service

```
Responsibilities:
├── Resolve tenant from HTTP request
│   ├── Custom domain → tenant mapping
│   ├── Subdomain → tenant mapping
│   ├── Header-based resolution (X-Tenant-ID)
│   ├── API key → tenant mapping
│   └── JWT claim extraction
├── Tenant context caching
├── Tenant validation (active/suspended check)
└── Tenant routing (to correct data source)
```

---

## 5. Tenant Lifecycle Management

### 5.1 Tenant State Machine

```
                    ┌──────────────┐
                    │   APPLIED    │
                    └──────┬───────┘
                           │ (Auto/Manual Review)
                    ┌──────▼───────┐
              ┌─────│   PENDING    │─────┐
              │     │   APPROVAL   │     │
              │     └──────────────┘     │
         (Reject)                    (Approve)
              │                          │
     ┌────────▼─────┐           ┌───────▼────────┐
     │   REJECTED   │           │  PROVISIONING  │
     └──────────────┘           └───────┬────────┘
                                        │ (Auto)
                                ┌───────▼────────┐
                                │  ONBOARDING    │
                                └───────┬────────┘
                                        │ (Complete Setup)
                                ┌───────▼────────┐
                          ┌─────│    ACTIVE       │◄────┐
                          │     └───────┬────────┘     │
                     (Suspend)          │          (Reactivate)
                          │        (Deactivate)        │
                  ┌───────▼────────┐    │    ┌─────────┴──────┐
                  │   SUSPENDED    │    │    │  (From Admin)  │
                  └───────┬────────┘    │    └────────────────┘
                          │             │
                     (Terminate)   (Terminate)
                          │             │
                  ┌───────▼─────────────▼──┐
                  │    PENDING_DELETION     │
                  └───────────┬────────────┘
                              │ (Grace Period)
                  ┌───────────▼────────────┐
                  │    DATA_CLEANUP         │
                  └───────────┬────────────┘
                              │
                  ┌───────────▼────────────┐
                  │      ARCHIVED          │
                  └───────────┬────────────┘
                              │ (Retention Period)
                  ┌───────────▼────────────┐
                  │      DELETED           │
                  └────────────────────────┘
```

### 5.2 Provisioning Pipeline

```typescript
interface ProvisioningPipeline {
  steps: ProvisioningStep[];
}

const provisioningSteps: ProvisioningStep[] = [
  {
    name: 'validate_application',
    description: 'Validate tenant application data',
    rollback: 'cleanup_application_data',
    timeout: 30_000,
    retries: 0,
    actions: [
      'Validate business information',
      'Verify KYB documents',
      'Check sanctions lists',
      'Validate jurisdiction eligibility'
    ]
  },
  {
    name: 'create_tenant_record',
    description: 'Create tenant in platform database',
    rollback: 'delete_tenant_record',
    timeout: 10_000,
    retries: 3,
    actions: [
      'Generate tenant ID and slug',
      'Create tenant record',
      'Set initial status to PROVISIONING',
      'Create audit log entry'
    ]
  },
  {
    name: 'provision_database',
    description: 'Set up tenant data storage',
    rollback: 'destroy_database_resources',
    timeout: 300_000,
    retries: 2,
    actions: [
      'Determine isolation level from tier',
      'Create schema/database',
      'Run migrations',
      'Set up RLS policies (if shared)',
      'Configure connection pooling',
      'Set up read replicas (if enterprise)'
    ]
  },
  {
    name: 'provision_identity',
    description: 'Set up authentication realm',
    rollback: 'destroy_identity_resources',
    timeout: 60_000,
    retries: 2,
    actions: [
      'Create tenant realm/organization in IdP',
      'Configure authentication policies',
      'Set up MFA requirements',
      'Create default roles and permissions',
      'Generate API keys',
      'Create initial admin user'
    ]
  },
  {
    name: 'configure_branding',
    description: 'Set up white-label configuration',
    rollback: 'remove_branding_config',
    timeout: 30_000,
    retries: 2,
    actions: [
      'Apply default branding template',
      'Configure email templates',
      'Set up notification templates',
      'Generate default assets'
    ]
  },
  {
    name: 'provision_domain',
    description: 'Set up custom domain/subdomain',
    rollback: 'remove_domain_config',
    timeout: 120_000,
    retries: 2,
    actions: [
      'Create subdomain (tenant.platform.com)',
      'Configure DNS records',
      'Provision SSL certificate',
      'Set up CDN routing',
      'Configure CORS policies'
    ]
  },
  {
    name: 'provision_trading_infrastructure',
    description: 'Set up trading connections',
    rollback: 'destroy_trading_resources',
    timeout: 180_000,
    retries: 2,
    actions: [
      'Create trading group/server allocation',
      'Configure default challenge templates',
      'Set up risk management rules',
      'Configure market data feeds',
      'Set up order routing'
    ]
  },
  {
    name: 'provision_billing',
    description: 'Set up billing and payment processing',
    rollback: 'destroy_billing_resources',
    timeout: 60_000,
    retries: 2,
    actions: [
      'Create billing account (Stripe Connect)',
      'Configure subscription plan',
      'Set up payment methods',
      'Configure payout settings',
      'Set up usage metering'
    ]
  },
  {
    name: 'provision_monitoring',
    description: 'Set up observability',
    rollback: 'destroy_monitoring_resources',
    timeout: 30_000,
    retries: 2,
    actions: [
      'Create monitoring dashboards',
      'Configure alerting rules',
      'Set up log aggregation',
      'Configure health checks'
    ]
  },
  {
    name: 'send_welcome',
    description: 'Send onboarding communications',
    rollback: null, // No rollback needed
    timeout: 30_000,
    retries: 3,
    actions: [
      'Send admin invitation email',
      'Send welcome documentation',
      'Create onboarding checklist',
      'Schedule onboarding call (if enterprise)'
    ]
  },
  {
    name: 'activate',
    description: 'Activate tenant',
    rollback: 'deactivate_tenant',
    timeout: 10_000,
    retries: 1,
    actions: [
      'Update status to ONBOARDING',
      'Enable API access',
      'Start billing cycle',
      'Log activation event',
      'Notify platform admins'
    ]
  }
];
```

### 5.3 Provisioning Orchestrator Implementation

```typescript
class TenantProvisioningOrchestrator {
  private readonly saga: SagaOrchestrator;
  private readonly eventBus: EventBus;
  
  async provisionTenant(application: TenantApplication): Promise<Tenant> {
    const correlationId = generateCorrelationId();
    const context = new ProvisioningContext(application, correlationId);
    
    try {
      // Execute provisioning saga
      const result = await this.saga.execute({
        id: correlationId,
        steps: provisioningSteps,
        context,
        onStepComplete: (step, result) => {
          this.eventBus.publish(new ProvisioningStepCompleted({
            tenantId: context.tenantId,
            step: step.name,
            result,
            correlationId
          }));
        },
        onStepFailed: (step, error) => {
          this.eventBus.publish(new ProvisioningStepFailed({
            tenantId: context.tenantId,
            step: step.name,
            error: error.message,
            correlationId
          }));
        }
      });
      
      this.eventBus.publish(new TenantProvisioned({
        tenantId: result.tenant.id,
        tier: result.tenant.tier,
        correlationId
      }));
      
      return result.tenant;
      
    } catch (error) {
      // Saga will automatically execute compensating transactions
      this.eventBus.publish(new TenantProvisioningFailed({
        applicationId: application.id,
        error: error.message,
        correlationId
      }));
      throw new ProvisioningFailedException(error);
    }
  }
}
```

### 5.4 Onboarding Workflow

```typescript
interface OnboardingChecklist {
  steps: OnboardingStep[];
  completedSteps: string[];
  currentStep: string;
  percentComplete: number;
}

const onboardingSteps: OnboardingStep[] = [
  {
    id: 'company_profile',
    title: 'Complete Company Profile',
    required: true,
    category: 'setup',
    fields: ['logo', 'description', 'website', 'social_links']
  },
  {
    id: 'branding_setup',
    title: 'Configure Branding',
    required: true,
    category: 'branding',
    fields: ['colors', 'logo', 'favicon', 'email_templates']
  },
  {
    id: 'domain_setup',
    title: 'Configure Custom Domain',
    required: false,
    category: 'branding',
    fields: ['custom_domain', 'ssl_certificate']
  },
  {
    id: 'challenge_setup',
    title: 'Create First Challenge Program',
    required: true,
    category: 'trading',
    fields: ['challenge_name', 'rules', 'pricing', 'profit_targets']
  },
  {
    id: 'risk_config',
    title: 'Configure Risk Parameters',
    required: true,
    category: 'trading',
    fields: ['max_daily_loss', 'max_total_loss', 'position_limits']
  },
  {
    id: 'payment_setup',
    title: 'Configure Payment Processing',
    required: true,
    category: 'billing',
    fields: ['stripe_connect', 'payout_methods', 'pricing']
  },
  {
    id: 'kyc_config',
    title: 'Configure KYC Requirements',
    required: true,
    category: 'compliance',
    fields: ['kyc_provider', 'required_documents', 'verification_levels']
  },
  {
    id: 'team_setup',
    title: 'Invite Team Members',
    required: false,
    category: 'setup',
    fields: ['team_members', 'roles']
  },
  {
    id: 'test_challenge',
    title: 'Run Test Challenge',
    required: true,
    category: 'verification',
    fields: ['test_trader', 'test_challenge_completion']
  },
  {
    id: 'go_live',
    title: 'Go Live Review',
    required: true,
    category: 'launch',
    fields: ['review_checklist', 'terms_acceptance']
  }
];
```

---

## 6. Data Architecture & Isolation

### 6.1 Data Classification

```
┌─────────────────────────────────────────────────────┐
│                DATA CLASSIFICATION                   │
│                                                      │
│  PLATFORM-LEVEL (Shared across all tenants)         │
│  ├── Tenant Registry                                │
│  ├── Platform Configuration                         │
│  ├── Billing/Subscription Master                    │
│  ├── Feature Flags                                  │
│  ├── Audit Logs (Platform)                          │
│  └── System Health Metrics                          │
│                                                      │
│  TENANT-LEVEL (Isolated per tenant)                 │
│  ├── Trader Accounts                                │
│  ├── Trading History                                │
│  ├── Challenge/Evaluation Data                      │
│  ├── Funded Account Data                            │
│  ├── KYC Documents                                  │
│  ├── Financial Transactions                         │
│  ├── Risk Management Configurations                 │
│  ├── Payout Records                                 │
│  ├── Tenant-specific Configurations                 │
│  ├── Communication History                          │
│  └── Audit Logs (Tenant)                            │
│                                                      │
│  CROSS-TENANT (Aggregated/Anonymized)               │
│  ├── Platform Analytics                             │
│  ├── Benchmarking Data                              │
│  ├── Market Data (shared feeds)                     │
│  └── System Performance Metrics                     │
└─────────────────────────────────────────────────────┘
```

### 6.2 PostgreSQL Row-Level Security Implementation

```sql
-- Enable RLS on tenant-scoped tables
-- ============================================

-- Create tenant context function
CREATE OR REPLACE FUNCTION current_tenant_id() 
RETURNS UUID AS $$
  SELECT NULLIF(current_setting('app.current_tenant_id', TRUE), '')::UUID;
$$ LANGUAGE SQL STABLE;

-- Traders table with RLS
CREATE TABLE traders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    email VARCHAR(255) NOT NULL,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    kyc_status VARCHAR(50) NOT NULL DEFAULT 'not_started',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Composite unique constraint within tenant
    CONSTRAINT uq_trader_email_per_tenant UNIQUE (tenant_id, email)
);

-- Create index for tenant-scoped queries
CREATE INDEX idx_traders_tenant_id ON traders(tenant_id);
CREATE INDEX idx_traders_tenant_status ON traders(tenant_id, status);

-- Enable RLS
ALTER TABLE traders ENABLE ROW LEVEL SECURITY;

-- Force RLS for table owner too (important!)
ALTER TABLE traders FORCE ROW LEVEL SECURITY;

-- Policies
CREATE POLICY tenant_isolation_policy ON traders
    USING (tenant_id = current_tenant_id());

CREATE POLICY tenant_insert_policy ON traders
    FOR INSERT
    WITH CHECK (tenant_id = current_tenant_id());

CREATE POLICY tenant_update_policy ON traders
    FOR UPDATE
    USING (tenant_id = current_tenant_id())
    WITH CHECK (tenant_id = current_tenant_id());

CREATE POLICY tenant_delete_policy ON traders
    FOR DELETE
    USING (tenant_id = current_tenant_id());

-- Platform admin bypass policy
CREATE POLICY platform_admin_policy ON traders
    USING (current_setting('app.is_platform_admin', TRUE) = 'true');


-- ============================================
-- Trading Accounts table
-- ============================================
CREATE TABLE trading_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    trader_id UUID NOT NULL REFERENCES traders(id),
    account_number VARCHAR(50) NOT NULL,
    account_type VARCHAR(50) NOT NULL,  -- 'challenge', 'verification', 'funded'
    platform VARCHAR(50) NOT NULL,      -- 'mt4', 'mt5', 'ctrader'
    balance DECIMAL(15,2) NOT NULL DEFAULT 0,
    initial_balance DECIMAL(15,2) NOT NULL,
    equity DECIMAL(15,2) NOT NULL DEFAULT 0,
    profit_loss DECIMAL(15,2) NOT NULL DEFAULT 0,
    max_daily_loss_limit DECIMAL(15,2),
    max_total_loss_limit DECIMAL(15,2),
    profit_target DECIMAL(15,2),
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    challenge_id UUID REFERENCES challenges(id),
    phase INTEGER DEFAULT 1,
    started_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    CONSTRAINT uq_account_number_per_tenant UNIQUE (tenant_id, account_number)
);

ALTER TABLE trading_accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE trading_accounts FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON trading_accounts
    USING (tenant_id = current_tenant_id());

-- ============================================
-- Trades table (high-volume, time-series)
-- ============================================
CREATE TABLE trades (
    id UUID DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    account_id UUID NOT NULL,
    trader_id UUID NOT NULL,
    ticket_number BIGINT NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    direction VARCHAR(4) NOT NULL,  -- 'buy' / 'sell'
    volume DECIMAL(10,2) NOT NULL,
    open_price DECIMAL(15,5) NOT NULL,
    close_price DECIMAL(15,5),
    stop_loss DECIMAL(15,5),
    take_profit DECIMAL(15,5),
    commission DECIMAL(10,2) DEFAULT 0,
    swap DECIMAL(10,2) DEFAULT 0,
    profit DECIMAL(15,2),
    opened_at TIMESTAMPTZ NOT NULL,
    closed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    PRIMARY KEY (tenant_id, id, opened_at)
) PARTITION BY RANGE (opened_at);

-- Create monthly partitions
CREATE TABLE trades_2024_01 PARTITION OF trades
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');
CREATE TABLE trades_2024_02 PARTITION OF trades
    FOR VALUES FROM ('2024-02-01') TO ('2024-03-01');
-- ... auto-create partitions via pg_partman

ALTER TABLE trades ENABLE ROW LEVEL SECURITY;
ALTER TABLE trades FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON trades
    USING (tenant_id = current_tenant_id());
```

### 6.3 Connection Management & Tenant Context

```typescript
// Middleware to set tenant context on database connection
class TenantDatabaseMiddleware {
  
  async setTenantContext(
    connection: DatabaseConnection,
    tenantId: string
  ): Promise<void> {
    // Set the tenant context for RLS
    await connection.query(
      `SET app.current_tenant_id = $1`,
      [tenantId]
    );
    await connection.query(
      `SET app.is_platform_admin = 'false'`
    );
  }
  
  async setPlatformAdminContext(
    connection: DatabaseConnection
  ): Promise<void> {
    await connection.query(
      `SET app.is_platform_admin = 'true'`
    );
    await connection.query(
      `SET app.current_tenant_id = ''`
    );
  }
}

// Connection Router for hybrid isolation
class TenantConnectionRouter {
  private readonly platformPool: ConnectionPool;
  private readonly sharedPool: ConnectionPool;
  private readonly dedicatedPools: Map<string, ConnectionPool>;
  private readonly tenantRegistry: TenantRegistry;
  
  async getConnection(tenantId: string): Promise<DatabaseConnection> {
    const tenant = await this.tenantRegistry.getTenant(tenantId);
    
    switch (tenant.isolationLevel) {
      case IsolationLevel.SHARED:
        const conn = await this.sharedPool.acquire();
        await this.setTenantContext(conn, tenantId);
        return conn;
        
      case IsolationLevel.SCHEMA:
        const schemaConn = await this.sharedPool.acquire();
        await schemaConn.query(`SET search_path = tenant_${tenant.slug}, public`);
        return schemaConn;
        
      case IsolationLevel.DEDICATED:
        if (!this.dedicatedPools.has(tenantId)) {
          this.dedicatedPools.set(
            tenantId,
            await this.createDedicatedPool(tenant.databaseConnectionString)
          );
        }
        return this.dedicatedPools.get(tenantId)!.acquire();
        
      default:
        throw new Error(`Unknown isolation level: ${tenant.isolationLevel}`);
    }
  }
}
```

### 6.4 Data Encryption Strategy

```
┌─────────────────────────────────────────────────────────────┐
│                  ENCRYPTION ARCHITECTURE                     │
│                                                              │
│  ┌────────────────────────────────────────────────────┐     │
│  │              KMS (Key Management Service)           │     │
│  │  ┌──────────────────────────────────────────┐      │     │
│  │  │         Platform Master Key (PMK)         │      │     │
│  │  └──────────────┬───────────────────────────┘      │     │
│  │                 │                                   │     │
│  │    ┌────────────┼────────────┐                     │     │
│  │    ▼            ▼            ▼                     │     │
│  │  ┌────┐     ┌────┐      ┌────┐                    │     │
│  │  │TEK │     │TEK │      │TEK │  Tenant            │     │
│  │  │ A  │     │ B  │      │ C  │  Encryption Keys   │     │
│  │  └──┬─┘     └──┬─┘      └──┬─┘                    │     │
│  │     │          │            │                      │     │
│  │     ▼          ▼            ▼                      │     │
│  │  ┌─────┐   ┌─────┐     ┌─────┐                   │     │
│  │  │DEK  │   │DEK  │     │DEK  │  Data              │     │
│  │  │A.1  │   │B.1  │     │C.1  │  Encryption Keys   │     │
│  │  │A.2  │   │B.2  │     │C.2  │  (per table/field) │     │
│  │  │A.3  │   │B.3  │     │C.3  │                    │     │
│  │  └─────┘   └─────┘     └─────┘                    │     │
│  └────────────────────────────────────────────────────┘     │
│                                                              │
│  Encryption at Rest:                                        │
│  ├── Database: TDE (Transparent Data Encryption)            │
│  ├── Field-level: AES-256-GCM for PII                      │
│  ├── KYC Documents: Envelope encryption                     │
│  └── Backups: Encrypted with tenant-specific keys           │
│                                                              │
│  Encryption in Transit:                                     │
│  ├── TLS 1.3 for all connections                            │
│  ├── mTLS for service-to-service                            │
│  └── Certificate pinning for trading connections            │
└─────────────────────────────────────────────────────────────┘
```

---

## 7. Identity, Authentication & Authorization

### 7.1 Multi-Tenant Identity Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    IDENTITY ARCHITECTURE                         │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                  Identity Provider (IdP)                    │ │
│  │            (Keycloak / Auth0 / Custom)                     │ │
│  │                                                             │ │
│  │  ┌─────────────────┐                                       │ │
│  │  │ Platform Realm   │  ← Platform Admin users              │ │
│  │  └─────────────────┘                                       │ │
│  │                                                             │ │
│  │  ┌─────────────────┐  ┌─────────────────┐                 │ │
│  │  │ Tenant A Realm  │  │ Tenant B Realm  │  ...            │ │
│  │  │                 │  │                 │                  │ │
│  │  │ Users:          │  │ Users:          │                  │ │
│  │  │ ├─ Firm Admins  │  │ ├─ Firm Admins  │                  │ │
│  │  │ ├─ Managers     │  │ ├─ Managers     │                  │ │
│  │  │ ├─ Risk Officers│  │ ├─ Risk Officers│                  │ │
│  │  │ ├─ Support      │  │ ├─ Support      │                  │ │
│  │  │ └─ Traders      │  │ └─ Traders      │                  │ │
│  │  │                 │  │                 │                  │ │
│  │  │ Roles:          │  │ Roles:          │                  │ │
│  │  │ ├─ firm_admin   │  │ ├─ firm_admin   │                  │ │
│  │  │ ├─ firm_manager │  │ ├─ firm_manager │                  │ │
│  │  │ ├─ risk_officer │  │ ├─ risk_officer │                  │ │
│  │  │ ├─ support_agent│  │ ├─ support_agent│                  │ │
│  │  │ └─ trader       │  │ └─ trader       │                  │ │
│  │  └─────────────────┘  └─────────────────┘                 │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### 7.2 Role-Based Access Control (RBAC) Matrix

```typescript
// Permission definitions
enum Permission {
  // Tenant Management (Platform-level)
  TENANT_CREATE = 'tenant:create',
  TENANT_READ = 'tenant:read',
  TENANT_UPDATE = 'tenant:update',
  TENANT_DELETE = 'tenant:delete',
  TENANT_SUSPEND = 'tenant:suspend',
  TENANT_BILLING_MANAGE = 'tenant:billing:manage',
  
  // Trader Management (Tenant-level)
  TRADER_CREATE = 'trader:create',
  TRADER_READ = 'trader:read',
  TRADER_UPDATE = 'trader:update',
  TRADER_DELETE = 'trader:delete',
  TRADER_SUSPEND = 'trader:suspend',
  TRADER_KYC_REVIEW = 'trader:kyc:review',
  
  // Account Management
  ACCOUNT_CREATE = 'account:create',
  ACCOUNT_READ = 'account:read',
  ACCOUNT_UPDATE = 'account:update',
  ACCOUNT_CLOSE = 'account:close',
  ACCOUNT_RESET = 'account:reset',
  
  // Challenge Management
  CHALLENGE_CREATE = 'challenge:create',
  CHALLENGE_READ = 'challenge:read',
  CHALLENGE_UPDATE = 'challenge:update',
  CHALLENGE_DELETE = 'challenge:delete',
  
  // Trading Operations
  TRADE_READ = 'trade:read',
  TRADE_EXECUTE = 'trade:execute',
  TRADE_CLOSE_ALL = 'trade:close_all',
  
  // Risk Management
  RISK_CONFIG_READ = 'risk:config:read',
  RISK_CONFIG_UPDATE = 'risk:config:update',
  RISK_OVERRIDE = 'risk:override',
  RISK_ALERTS_VIEW = 'risk:alerts:view',
  
  // Financial Operations
  PAYOUT_REQUEST = 'payout:request',
  PAYOUT_APPROVE = 'payout:approve',
  PAYOUT_PROCESS = 'payout:process',
  REFUND_PROCESS = 'refund:process',
  FINANCIAL_REPORTS = 'financial:reports',
  
  // Configuration
  CONFIG_BRANDING = 'config:branding',
  CONFIG_TRADING = 'config:trading',
  CONFIG_BILLING = 'config:billing',
  CONFIG_COMPLIANCE = 'config:compliance',
  
  // Reports & Analytics
  REPORTS_VIEW = 'reports:view',
  ANALYTICS_VIEW = 'analytics:view',
  AUDIT_LOG_VIEW = 'audit:view',
}

// Role definitions with permissions
const ROLE_PERMISSIONS: Record<string, Permission[]> = {
  // Platform-level roles
  'platform_super_admin': [/* ALL permissions */],
  'platform_admin': [
    Permission.TENANT_CREATE, Permission.TENANT_READ, 
    Permission.TENANT_UPDATE, Permission.TENANT_SUSPEND,
    Permission.TENANT_BILLING_MANAGE,
    // ... most platform permissions
  ],
  'platform_support': [
    Permission.TENANT_READ,
    Permission.TRADER_READ,
    Permission.ACCOUNT_READ,
    Permission.TRADE_READ,
  ],
  
  // Tenant-level roles
  'firm_admin': [
    Permission.TRADER_CREATE, Permission.TRADER_READ,
    Permission.TRADER_UPDATE, Permission.TRADER_DELETE,
    Permission.TRADER_SUSPEND, Permission.TRADER_KYC_REVIEW,
    Permission.ACCOUNT_CREATE, Permission.ACCOUNT_READ,
    Permission.ACCOUNT_UPDATE, Permission.ACCOUNT_CLOSE,
    Permission.CHALLENGE_CREATE, Permission.CHALLENGE_READ,
    Permission.CHALLENGE_UPDATE, Permission.CHALLENGE_DELETE,
    Permission.TRADE_READ, Permission.TRADE_CLOSE_ALL,
    Permission.RISK_CONFIG_READ, Permission.RISK_CONFIG_UPDATE,
    Permission.PAYOUT_APPROVE, Permission.PAYOUT_PROCESS,
    Permission.REFUND_PROCESS, Permission.FINANCIAL_REPORTS,
    Permission.CONFIG_BRANDING, Permission.CONFIG_TRADING,
    Permission.CONFIG_BILLING, Permission.CONFIG_COMPLIANCE,
    Permission.REPORTS_VIEW, Permission.ANALYTICS_VIEW,
    Permission.AUDIT_LOG_VIEW,
  ],
  'firm_manager': [
    Permission.TRADER_CREATE, Permission.TRADER_READ,
    Permission.TRADER_UPDATE, Permission.TRADER_SUSPEND,
    Permission.ACCOUNT_CREATE, Permission.ACCOUNT_READ,
    Permission.ACCOUNT_UPDATE,
    Permission.CHALLENGE_READ,
    Permission.TRADE_READ,
    Permission.RISK_ALERTS_VIEW,
    Permission.PAYOUT_REQUEST,
    Permission.REPORTS_VIEW,
  ],
  'risk_officer': [
    Permission.TRADER_READ,
    Permission.ACCOUNT_READ,
    Permission.TRADE_READ, Permission.TRADE_CLOSE_ALL,
    Permission.RISK_CONFIG_READ, Permission.RISK_CONFIG_UPDATE,
    Permission.RISK_OVERRIDE, Permission.RISK_ALERTS_VIEW,
    Permission.REPORTS_VIEW, Permission.ANALYTICS_VIEW,
  ],
  'support_agent': [
    Permission.TRADER_READ, Permission.TRADER_UPDATE,
    Permission.ACCOUNT_READ,
    Permission.TRADE_READ,
    Permission.PAYOUT_REQUEST,
  ],
  'trader': [
    Permission.ACCOUNT_READ,  // Own accounts only
    Permission.TRADE_READ,     // Own trades only
    Permission.TRADE_EXECUTE,  // On own accounts
    Permission.PAYOUT_REQUEST, // Own payouts
  ],
};
```

### 7.3 JWT Token Structure

```json
{
  "header": {
    "alg": "RS256",
    "typ": "JWT",
    "kid": "platform-key-2024-01"
  },
  "payload": {
    "sub": "user_abc123",
    "iss": "https://auth.pfaas-platform.com",
    "aud": "pfaas-api",
    "iat": 1704067200,
    "exp": 1704070800,
    "tenant_id": "tenant_xyz789",
    "tenant_slug": "alpha-trading",
    "tenant_tier": "professional",
    "user_type": "tenant_user",
    "roles": ["firm_admin"],
    "permissions": ["trader:create", "trader:read", "..."],
    "org_id": "org_456",
    "session_id": "sess_789",
    "ip": "192.168.1.1",
    "mfa_verified": true,
    "custom_claims": {
      "department": "risk_management",
      "trading_desk": "fx_desk_1"
    }
  }
}
```

### 7.4 Tenant Resolution Strategies

```typescript
class TenantResolver {
  private readonly strategies: TenantResolutionStrategy[];
  private readonly cache: TenantCache;
  
  constructor() {
    this.strategies = [
      new CustomDomainStrategy(),      // trade.alphafirm.com
      new SubdomainStrategy(),          // alphafirm.pfaas.com
      new HeaderStrategy(),             // X-Tenant-ID header
      new JWTClaimStrategy(),           // JWT tenant_id claim
      new APIKeyStrategy(),             // API key → tenant mapping
      new PathStrategy(),               // /api/v1/tenants/{id}/...
    ];
  }
  
  async resolve(request: Request): Promise<TenantContext> {
    for (const strategy of this.strategies) {
      const tenantId = await strategy.resolve(request);
      if (tenantId) {
        // Validate tenant exists and is active
        const tenant = await this.cache.getOrFetch(tenantId);
        if (!tenant) throw new TenantNotFoundException(tenantId);
        if (tenant.status !== 'active') throw new TenantInactiveException(tenantId);
        
        return new TenantContext(tenant);
      }
    }
    throw new TenantResolutionFailedException();
  }
}

class CustomDomainStrategy implements TenantResolutionStrategy {
  async resolve(request: Request): Promise<string | null> {
    const host = request.headers.get('host');
    if (!host) return null;
    
    // Skip platform domains
    if (host.endsWith('.pfaas.com')) return null;
    
    // Look up custom domain mapping
    const mapping = await this.domainRegistry.findByDomain(host);
    return mapping?.tenantId ?? null;
  }
}

class SubdomainStrategy implements TenantResolutionStrategy {
  async resolve(request: Request): Promise<string | null> {
    const host = request.headers.get('host');
    if (!host) return null;
    
    const match = host.match(/^([a-z0-9-]+)\.pfaas\.com$/);
    if (!match) return null;
    
    const subdomain = match[1];
    if (['www', 'api', 'admin', 'app'].includes(subdomain)) return null;
    
    const tenant = await this.tenantRegistry.findBySlug(subdomain);
    return tenant?.id ?? null;
  }
}
```

---

## 8. Billing & Subscription Management

### 8.1 Revenue Model Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    REVENUE STREAMS                               │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  1. SUBSCRIPTION FEES (Tenant → Platform)                │    │
│  │     ├── Starter:      $499/month                        │    │
│  │     ├── Professional: $1,499/month                      │    │
│  │     ├── Enterprise:   $4,999/month                      │    │
│  │     └── Custom:       Negotiated                        │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  2. USAGE-BASED FEES (Tenant → Platform)                 │    │
│  │     ├── Per active trader:    $2-5/trader/month          │    │
│  │     ├── Per challenge sold:   $5-15/challenge            │    │
│  │     ├── Per funded account:   $10-25/account/month       │    │
│  │     ├── API calls:            $0.001/call (over limit)   │    │
│  │     └── Storage:              $0.10/GB/month (over limit)│    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  3. REVENUE SHARE (Tenant → Platform)                    │    │
│  │     ├── Challenge fees:        5-15% of revenue          │    │
│  │     ├── Funded account profits: 2-5% of firm's share     │    │
│  │     └── Payment processing:     Stripe fees + markup     │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  4. ADD-ON SERVICES (Tenant → Platform)                  │    │
│  │     ├── Custom domain SSL:    $10/month                  │    │
│  │     ├── Premium support:      $500/month                 │    │
│  │     ├── Dedicated infrastructure: $1,000+/month          │    │
│  │     ├── Custom integrations:  Project-based              │    │
│  │     └── Additional data regions: $200/region/month       │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

### 8.2 Subscription Tier Definitions

```typescript
interface SubscriptionTier {
  id: string;
  name: string;
  monthlyPrice: number;
  annualPrice: number;
  limits: TenantLimits;
  features: FeatureFlags;
  support: SupportLevel;
  sla: SLAConfig;
}

const SUBSCRIPTION_TIERS: SubscriptionTier[] = [
  {
    id: 'starter',
    name: 'Starter',
    monthlyPrice: 499,
    annualPrice: 4990,
    limits: {
      maxTraders: 500,
      maxActiveAccounts: 1000,
      maxChallengesPerMonth: -1,   // unlimited
      maxFundedCapital: 1_000_000,
      maxConcurrentConnections: 100,
      apiRateLimit: 100,            // per minute
      storageQuotaGB: 10,
      dataRetentionDays: 90,
      maxAdminUsers: 3,
      maxCustomRules: 5
    },
    features: {
      whiteLabel: false,
      customDomain: false,
      apiAccess: true,
      advancedAnalytics: false,
      customChallengeRules: false,
      multiPhaseEvaluation: true,
      automatedPayouts: false,
      dedicatedSupport: false,
      customIntegrations: false,
      ssoSupport: false,
      auditLogs: true,
      dataExport: true,
    },
    support: 'email',
    sla: { uptimeGuarantee: 99.5, responseTime: '24h' }
  },
  {
    id: 'professional',
    name: 'Professional',
    monthlyPrice: 1499,
    annualPrice: 14990,
    limits: {
      maxTraders: 5000,
      maxActiveAccounts: 15000,
      maxChallengesPerMonth: -1,
      maxFundedCapital: 10_000_000,
      maxConcurrentConnections: 500,
      apiRateLimit: 500,
      storageQuotaGB: 100,
      dataRetentionDays: 365,
      maxAdminUsers: 10,
      maxCustomRules: 25
    },
    features: {
      whiteLabel: true,
      customDomain: true,
      apiAccess: true,
      advancedAnalytics: true,
      customChallengeRules: true,
      multiPhaseEvaluation: true,
      automatedPayouts: true,
      dedicatedSupport: false,
      customIntegrations: false,
      ssoSupport: true,
      auditLogs: true,
      dataExport: true,
    },
    support: 'email_chat',
    sla: { uptimeGuarantee: 99.9, responseTime: '4h' }
  },
  {
    id: 'enterprise',
    name: 'Enterprise',
    monthlyPrice: 4999,
    annualPrice: 49990,
    limits: {
      maxTraders: -1,               // unlimited
      maxActiveAccounts: -1,
      maxChallengesPerMonth: -1,
      maxFundedCapital: -1,
      maxConcurrentConnections: -1,
      apiRateLimit: 5000,
      storageQuotaGB: 1000,
      dataRetentionDays: 2555,     // 7 years
      maxAdminUsers: -1,
      maxCustomRules: -1
    },
    features: {
      whiteLabel: true,
      customDomain: true,
      apiAccess: true,
      advancedAnalytics: true,
      customChallengeRules: true,
      multiPhaseEvaluation: true,
      automatedPayouts: true,
      dedicatedSupport: true,
      customIntegrations: true,
      ssoSupport: true,
      auditLogs: true,
      dataExport: true,
      dedicatedInfrastructure: true,
      customSLA: true,
      priorityFeatureRequests: true,
    },
    support: 'dedicated_manager',
    sla: { uptimeGuarantee: 99.99, responseTime: '1h' }
  }
];
```

### 8.3 Usage Metering System

```typescript
// Metering events
interface MeterEvent {
  id: string;
  tenantId: string;
  metricName: string;
  value: number;
  unit: string;
  timestamp: Date;
  metadata: Record<string, any>;
  idempotencyKey: string;
}

class UsageMeteringService {
  private readonly buffer: MeterEvent[] = [];
  private readonly FLUSH_INTERVAL = 60_000; // 1 minute
  private readonly FLUSH_SIZE = 1000;
  
  // High-frequency event recording
  async recordEvent(event: MeterEvent): Promise<void> {
    this.buffer.push(event);
    
    if (this.buffer.length >= this.FLUSH_SIZE) {
      await this.flush();
    }
  }
  
  // Metric definitions for prop firm context
  readonly METRICS = {
    ACTIVE_TRADERS: 'active_traders',
    CHALLENGES_CREATED: 'challenges_created',
    FUNDED_ACCOUNTS: 'funded_accounts',
    TRADES_EXECUTED: 'trades_executed',
    API_CALLS: 'api_calls',
    STORAGE_USED_GB: 'storage_used_gb',
    MARKET_DATA_REQUESTS: 'market_data_requests',
    PAYOUT_TRANSACTIONS: 'payout_transactions',
    KYC_VERIFICATIONS: 'kyc_verifications',
    EMAIL_SENT: 'emails_sent',
    WEBHOOK_CALLS: 'webhook_calls',
  };
  
  // Aggregate usage for billing period
  async getUsageSummary(
    tenantId: string,
    periodStart: Date,
    periodEnd: Date
  ): Promise<UsageSummary> {
    return {
      tenantId,
      period: { start: periodStart, end: periodEnd },
      metrics: {
        activeTraders: await this.getMaxValue(
          tenantId, 'active_traders', periodStart, periodEnd
        ),
        challengesSold: await this.getSumValue(
          tenantId, 'challenges_created', periodStart, periodEnd
        ),
        fundedAccounts: await this.getMaxValue(
          tenantId, 'funded_accounts', periodStart, periodEnd
        ),
        apiCalls: await this.getSumValue(
          tenantId, 'api_calls', periodStart, periodEnd
        ),
        storageGB: await this.getMaxValue(
          tenantId, 'storage_used_gb', periodStart, periodEnd
        ),
      }
    };
  }
}
```

### 8.4 Payment Flow Architecture (Stripe Connect)

```
┌─────────────────────────────────────────────────────────────────┐
│                    PAYMENT FLOW ARCHITECTURE                     │
│                                                                  │
│  CHALLENGE PURCHASE FLOW (Trader → Tenant → Platform)           │
│                                                                  │
│  ┌─────────┐    ┌──────────────┐    ┌────────────────────────┐  │
│  │ Trader  │───▶│ Stripe       │───▶│ Tenant's Stripe       │  │
│  │ (Buyer) │    │ Checkout     │    │ Connected Account     │  │
│  └─────────┘    └──────────────┘    │                        │  │
│                                      │ Challenge fee: $500    │  │
│                                      │ ├─ Tenant: $425 (85%) │  │
│                                      │ ├─ Platform: $50 (10%)│  │
│                                      │ └─ Stripe: $25 (5%)   │  │
│                                      └────────────────────────┘  │
│                                                                  │
│  PAYOUT FLOW (Tenant → Trader)                                  │
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌─────────┐           │
│  │ Tenant's     │───▶│ Payout       │───▶│ Trader  │           │
│  │ Account      │    │ Processing   │    │ (Wise/  │           │
│  │ Balance      │    │ Service      │    │  Bank)  │           │
│  └──────────────┘    └──────────────┘    └─────────┘           │
│                                                                  │
│  SUBSCRIPTION FLOW (Tenant → Platform)                          │
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────┐  │
│  │ Tenant's     │───▶│ Stripe       │───▶│ Platform's       │  │
│  │ Payment      │    │ Subscription │    │ Stripe Account   │  │
│  │ Method       │    │ Billing      │    │                  │  │
│  └──────────────┘    └──────────────┘    └──────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 9. White-Label & Customization Engine

### 9.1 White-Label Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                  WHITE-LABEL ENGINE                               │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    BRANDING LAYER                         │   │
│  │                                                           │   │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────┐           │   │
│  │  │   Visual   │ │   Domain   │ │   Content  │           │   │
│  │  │  Identity  │ │  Manager   │ │  Manager   │           │   │
│  │  │            │ │            │ │            │           │   │
│  │  │ • Logo     │ │ • Custom   │ │ • Terms    │           │   │
│  │  │ • Colors   │ │   domains  │ │ • Privacy  │           │   │
│  │  │ • Fonts    │ │ • SSL/TLS  │ │ • FAQs     │           │   │
│  │  │ • Favicon  │ │ • DNS mgmt │ │ • Help     │           │   │
│  │  │ • Theme    │ │ • CDN      │ │   articles │           │   │
│  │  └────────────┘ └────────────┘ └────────────┘           │   │
│  │                                                           │   │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────┐           │   │
│  │  │   Email    │ │    UI      │ │   Asset    │           │   │
│  │  │ Templates  │ │ Component  │ │  Storage   │           │   │
│  │  │            │ │  Overrides │ │            │           │   │
│  │  │ • Welcome  │ │            │ │ • Images   │           │   │
│  │  │ • KYC      │ │ • Dashboard│ │ • Videos   │           │   │
│  │  │ • Challenge│ │ • Login    │ │ • Documents│           │   │
│  │  │ • Payout   │ │ • Challenge│ │ • Marketing│           │   │
│  │  │ • Support  │ │ • Profile  │ │   assets   │           │   │
│  │  └────────────┘ └────────────┘ └────────────┘           │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 9.2 Branding Configuration Schema

```typescript
interface BrandingConfig {
  // Visual Identity
  logo: {
    primary: string;           // URL to primary logo
    secondary: string;         // URL to secondary/dark logo
    favicon: string;           // URL to favicon
    icon: string;              // App icon (for mobile)
    emailHeader: string;       // Logo for emails
  };
  
  // Color Scheme
  colors: {
    primary: string;           // Main brand color
    primaryDark: string;
    primaryLight: string;
    secondary: string;
    accent: string;
    background: string;
    surface: string;
    text: string;
    textSecondary: string;
    error: string;
    warning: string;
    success: string;
    info: string;
    
    // Chart colors
    profitColor: string;
    lossColor: string;
    chartGrid: string;
    chartLine: string;
  };
  
  // Typography
  typography: {
    primaryFont: string;
    secondaryFont: string;
    monoFont: string;
    fontCdnUrl?: string;
  };
  
  // Layout
  layout: {
    sidebarPosition: 'left' | 'right';
    headerStyle: 'fixed' | 'sticky' | 'static';
    borderRadius: string;      // e.g., '8px'
    density: 'compact' | 'comfortable' | 'spacious';
  };
  
  // Custom CSS
  customCss?: string;
  
  // Social & Links
  social: {
    website?: string;
    twitter?: string;
    discord?: string;
    telegram?: string;
    instagram?: string;
    youtube?: string;
    linkedin?: string;
  };
  
  // Legal
  legal: {
    companyName: string;
    termsUrl: string;
    privacyUrl: string;
    riskDisclosureUrl: string;
    refundPolicyUrl: string;
    cookiePolicyUrl: string;
  };
  
  // Custom Pages
  customPages: {
    landingPage?: CustomPage;
    aboutPage?: CustomPage;
    faqPage?: CustomPage;
  };
}

interface DomainConfig {
  // Subdomain
  subdomain: string;           // {subdomain}.pfaas.com
  
  // Custom domain
  customDomain?: string;       // trade.myfirm.com
  customDomainVerified: boolean;
  sslCertificateId?: string;
  dnsRecords: DNSRecord[];
  
  // API domain
  apiDomain?: string;          // api.myfirm.com
  
  // CDN
  cdnDomain?: string;
  cdnDistributionId?: string;
}
```

### 9.3 Dynamic Theming Implementation

```typescript
// Theme resolution at runtime
class ThemeResolver {
  async resolveTheme(tenantId: string): Promise<CompiledTheme> {
    // 1. Get base platform theme
    const baseTheme = await this.getBaseTheme();
    
    // 2. Get tier-level overrides
    const tenant = await this.tenantRegistry.get(tenantId);
    const tierTheme = await this.getTierTheme(tenant.tier);
    
    // 3. Get tenant-specific overrides
    const tenantBranding = await this.getBranding(tenantId);
    
    // 4. Merge themes (tenant overrides tier overrides base)
    const mergedTheme = deepMerge(baseTheme, tierTheme, tenantBranding);
    
    // 5. Compile to CSS custom properties
    return this.compileTheme(mergedTheme);
  }
  
  private compileTheme(theme: BrandingConfig): CompiledTheme {
    return {
      cssVariables: `
        :root {
          --color-primary: ${theme.colors.primary};
          --color-primary-dark: ${theme.colors.primaryDark};
          --color-primary-light: ${theme.colors.primaryLight};
          --color-secondary: ${theme.colors.secondary};
          --color-accent: ${theme.colors.accent};
          --color-background: ${theme.colors.background};
          --color-surface: ${theme.colors.surface};
          --color-text: ${theme.colors.text};
          --color-text-secondary: ${theme.colors.textSecondary};
          --color-profit: ${theme.colors.profitColor};
          --color-loss: ${theme.colors.lossColor};
          --font-primary: ${theme.typography.primaryFont};
          --font-secondary: ${theme.typography.secondaryFont};
          --border-radius: ${theme.layout.borderRadius};
        }
      `,
      metadata: {
        logo: theme.logo,
        social: theme.social,
        legal: theme.legal,
      }
    };
  }
}
```

---

## 10. Trading Infrastructure Integration

### 10.1 Trading Platform Integration Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                 TRADING INFRASTRUCTURE LAYER                         │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │                 Trading Gateway Service                        │ │
│  │  ┌──────────────────────────────────────────────────────────┐ │ │
│  │  │              Platform Abstraction Layer                   │ │ │
│  │  │  Unified API for all trading platforms                    │ │ │
│  │  └──────────────────────────────────────────────────────────┘ │ │
│  │            │                │                │                │ │
│  │   ┌────────▼──────┐ ┌──────▼───────┐ ┌──────▼───────┐      │ │
│  │   │ MT4/MT5       │ │ cTrader      │ │ DXtrade      │      │ │
│  │   │ Adapter       │ │ Adapter      │ │ Adapter      │      │ │
│  │   │               │ │              │ │              │      │ │
│  │   │ • Manager API │ │ • Open API   │ │ • REST API   │      │ │
│  │   │ • MT5 WebAPI  │ │ • FIX Proto  │ │ • WebSocket  │      │ │
│  │   │ • MAMP        │ │ • cServer    │ │              │      │ │
│  │   └───────────────┘ └──────────────┘ └──────────────┘      │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │                  TENANT TRADING OPERATIONS                     │ │
│  │                                                                │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │ │
│  │  │  Account      │  │   Trade      │  │    Risk      │        │ │
│  │  │  Provisioning │  │   Monitor    │  │   Engine     │        │ │
│  │  │               │  │              │  │              │        │ │
│  │  │ • Create MT   │  │ • Real-time  │  │ • Daily loss │        │ │
│  │  │   accounts    │  │   trade feed │  │   limit      │        │ │
│  │  │ • Set leverage│  │ • P&L calc   │  │ • Max loss   │        │ │
│  │  │ • Set balance │  │ • Position   │  │   limit      │        │ │
│  │  │ • Group mgmt  │  │   tracking   │  │ • Drawdown   │        │ │
│  │  │ • Password    │  │ • Symbol     │  │ • Time rules │        │ │
│  │  │   management  │  │   filtering  │  │ • News event │        │ │
│  │  └──────────────┘  └──────────────┘  │   restrictions│        │ │
│  │                                       │ • Position   │        │ │
│  │                                       │   size limits│        │ │
│  │                                       └──────────────┘        │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │                  CHALLENGE/EVALUATION ENGINE                    │ │
│  │                                                                │ │
│  │  Challenge Phase 1 → Phase 2 → Funded Account                 │ │
│  │                                                                │ │
│  │  ┌─────────────────────────────────────────────────────────┐  │ │
│  │  │ Configurable Rules per Tenant:                          │  │ │
│  │  │ • Profit target (% of initial balance)                  │  │ │
│  │  │ • Max daily drawdown (% or fixed amount)                │  │ │
│  │  │ • Max total drawdown (% or fixed amount)                │  │ │
│  │  │ • Minimum trading days                                  │  │ │
│  │  │ • Maximum trading days                                  │  │ │
│  │  │ • Lot size restrictions                                 │  │ │
│  │  │ • Instrument restrictions                               │  │ │
│  │  │ • Weekend holding rules                                 │  │ │
│  │  │ • News trading restrictions                             │  │ │
│  │  │ • Consistency rules                                     │  │ │
│  │  │ • EA/Bot permissions                                    │  │ │
│  │  │ • Copy trading permissions                              │  │ │
│  │  └─────────────────────────────────────────────────────────┘  │ │
│  └────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

### 10.2 Challenge/Evaluation Configuration Model

```typescript
interface ChallengeTemplate {
  id: UUID;
  tenantId: UUID;
  name: string;
  description: string;
  isActive: boolean;
  
  // Pricing
  pricing: ChallengePricing;
  
  // Phases
  phases: ChallengePhase[];
  
  // Funded Account Configuration
  fundedConfig: FundedAccountConfig;
  
  // Account Sizes
  accountSizes: AccountSizeOption[];
  
  // Trading Platform
  platform: 'mt4' | 'mt5' | 'ctrader' | 'dxtrade';
  leverage: string;
  
  // Metadata
  createdAt: Date;
  updatedAt: Date;
}

interface ChallengePhase {
  phaseNumber: number;
  name: string;                      // "Evaluation", "Verification"
  
  // Objectives
  profitTarget: number;              // Percentage, e.g., 8 (8%)
  
  // Risk Limits
  maxDailyLoss: number;             // Percentage, e.g., 5 (5%)
  maxTotalLoss: number;             // Percentage, e.g., 10 (10%)
  drawdownType: 'balance' | 'equity' | 'trailing';
  
  // Time Rules
  minimumTradingDays: number;
  maximumTradingDays: number | null; // null = unlimited
  
  // Trading Rules
  tradingRules: TradingRules;
  
  // Automatic Phase Transition
  autoAdvance: boolean;             // Auto-advance to next phase on success
}

interface TradingRules {
  allowedInstruments: string[] | 'all';
  restrictedInstruments: string[];
  maxLotSize: number | null;
  maxOpenPositions: number | null;
  maxOpenLots: number | null;
  allowWeekendHolding: boolean;
  allowNewsTrading: boolean;
  newsRestrictionMinutes: number;   // Minutes before/after news
  allowEA: boolean;
  allowCopyTrading: boolean;
  allowHedging: boolean;
  allowMartingale: boolean;
  consistencyRule: ConsistencyRule | null;
  tradingHoursRestriction: TradingHoursRestriction | null;
}

interface ConsistencyRule {
  enabled: boolean;
  maxProfitPercentFromSingleDay: number;  // e.g., 30% of total profit
  maxProfitPercentFromSingleTrade: number; // e.g., 25% of total profit
  minTradingDaysRequired: number;
}

interface AccountSizeOption {
  initialBalance: number;           // e.g., 10000, 25000, 50000, 100000, 200000
  currency: string;
  price: number;                    // Challenge fee
  discountedPrice: number | null;
  profitSplit: number;             // e.g., 80 (80% to trader)
  maxScaleUpBalance: number | null;
}

interface FundedAccountConfig {
  profitSplit: number;             // Default profit split percentage
  payoutFrequency: 'weekly' | 'biweekly' | 'monthly' | 'on_demand';
  minimumPayoutAmount: number;
  firstPayoutDelay: number;        // Days after funding
  scaleUpRules: ScaleUpRule[];
  maxPayoutPerRequest: number | null;
  payoutMethods: PaymentMethod[];
}
```

---

## 11. Compliance & Regulatory Framework

### 11.1 Compliance Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                  COMPLIANCE ENGINE                               │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                   KYC/KYB SERVICE                         │   │
│  │                                                           │   │
│  │  Platform-Level KYB (Know Your Business)                 │   │
│  │  ├── Tenant registration verification                    │   │
│  │  ├── Business document verification                      │   │
│  │  ├── UBO (Ultimate Beneficial Owner) identification      │   │
│  │  └── Sanctions screening                                 │   │
│  │                                                           │   │
│  │  Tenant-Level KYC (Know Your Customer)                   │   │
│  │  ├── Trader identity verification                        │   │
│  │  ├── Document verification (ID, proof of address)        │   │
│  │  ├── Liveness detection                                  │   │
│  │  ├── PEP (Politically Exposed Person) screening          │   │
│  │  └── Ongoing monitoring                                  │   │
│  │                                                           │   │
│  │  Integration Providers:                                  │   │
│  │  ├── Sumsub / Onfido / Jumio / Veriff                    │   │
│  │  ├── Chainalysis (crypto screening)                      │   │
│  │  └── ComplyAdvantage (sanctions/PEP)                     │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                  AML MONITORING                            │   │
│  │                                                           │   │
│  │  ├── Transaction monitoring (unusual patterns)           │   │
│  │  ├── Suspicious activity reporting                       │   │
│  │  ├── Currency transaction reporting                      │   │
│  │  ├── Cross-border payment monitoring                     │   │
│  │  └── Velocity checks                                     │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                  DATA PROTECTION                          │   │
│  │                                                           │   │
│  │  ├── GDPR compliance engine                              │   │
│  │  │   ├── Data subject access requests (DSAR)             │   │
│  │  │   ├── Right to erasure                                │   │
│  │  │   ├── Data portability                                │   │
│  │  │   ├── Consent management                              │   │
│  │  │   └── Data processing agreements                      │   │
│  │  │                                                       │   │
│  │  ├── Data residency enforcement                          │   │
│  │  │   ├── EU data stays in EU                             │   │
│  │  │   ├── Configurable per tenant jurisdiction            │   │
│  │  │   └── Cross-border transfer controls                  │   │
│  │  │                                                       │   │
│  │  └── Data retention policies                             │   │
│  │      ├── Configurable per data type                      │   │
│  │      ├── Automatic purging                               │   │
│  │      └── Legal hold support                              │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                  AUDIT SYSTEM                             │   │
│  │                                                           │   │
│  │  ├── Immutable audit log (append-only)                   │   │
│  │  ├── Action tracking (who, what, when, where)            │   │
│  │  ├── Configuration change tracking                       │   │
│  │  ├── Access logging                                      │   │
│  │  ├── Financial transaction audit trail                   │   │
│  │  ├── Tenant-scoped audit views                           │   │
│  │  └── Platform-level compliance reporting                 │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 11.2 Audit Log Schema

```typescript
interface AuditLogEntry {
  id: UUID;
  
  // Context
  tenantId: UUID | null;          // null for platform-level events
  userId: UUID;
  userEmail: string;
  userRole: string;
  sessionId: string;
  
  // Event
  eventType: AuditEventType;
  eventCategory: AuditCategory;
  action: string;                  // 'CREATE', 'UPDATE', 'DELETE', etc.
  resource: string;                // 'trader', 'account', 'challenge', etc.
  resourceId: string;
  
  // Details
  description: string;
  previousState: Record<string, any> | null;
  newState: Record<string, any> | null;
  changedFields: string[];
  
  // Request context
  ipAddress: string;
  userAgent: string;
  requestId: string;
  apiEndpoint: string;
  httpMethod: string;
  
  // Geolocation
  country: string;
  city: string;
  
  // Risk indicators
  riskScore: number;              // 0-100
  flagged: boolean;
  flagReason: string | null;
  
  // Timestamp
  timestamp: Date;
  
  // Integrity
  checksum: string;               // SHA-256 of event data
  previousChecksum: string;       // Chain integrity
}

enum AuditCategory {
  AUTHENTICATION = 'authentication',
  AUTHORIZATION = 'authorization',
  TENANT_MANAGEMENT = 'tenant_management',
  TRADER_MANAGEMENT = 'trader_management',
  ACCOUNT_MANAGEMENT = 'account_management',
  TRADING_ACTIVITY = 'trading_activity',
  RISK_MANAGEMENT = 'risk_management',
  FINANCIAL = 'financial',
  CONFIGURATION = 'configuration',
  COMPLIANCE = 'compliance',
  SYSTEM = 'system',
}
```

---

## 12. Performance, Scalability & Reliability

### 12.1 Scalability Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    SCALABILITY ARCHITECTURE                          │
│                                                                      │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                    LOAD BALANCING LAYER                        │  │
│  │                                                                │  │
│  │  ┌──────────────┐                                             │  │
│  │  │  CloudFlare   │  ← DDoS protection, WAF, CDN              │  │
│  │  │  / AWS CF     │  ← Custom domain SSL termination          │  │
│  │  └──────┬───────┘                                             │  │
│  │         │                                                      │  │
│  │  ┌──────▼───────┐                                             │  │
│  │  │  Application │  ← Path-based routing                      │  │
│  │  │  Load        │  ← Health check routing                    │  │
│  │  │  Balancer    │  ← Rate limiting                            │  │
│  │  └──────┬───────┘                                             │  │
│  └─────────┼─────────────────────────────────────────────────────┘  │
│            │                                                         │
│  ┌─────────▼─────────────────────────────────────────────────────┐  │
│  │                   APPLICATION LAYER                            │  │
│  │                                                                │  │
│  │  ┌─────────────────────────────────────────────────────────┐  │  │
│  │  │              API Gateway (Kong / AWS API GW)             │  │  │
│  │  │  ├── Tenant resolution                                   │  │  │
│  │  │  ├── Rate limiting (per tenant)                          │  │  │
│  │  │  ├── Request validation                                  │  │  │
│  │  │  ├── Authentication                                      │  │  │
│  │  │  └── Request routing                                     │  │  │
│  │  └─────────────────────────────────────────────────────────┘  │  │
│  │                          │                                     │  │
│  │   ┌──────────────────────┼──────────────────────┐             │  │
│  │   ▼                      ▼                      ▼             │  │
│  │  ┌──────────┐  ┌────────────────┐  ┌──────────────────┐     │  │
│  │  │ Tenant   │  │   Trading      │  │   Financial      │     │  │
│  │  │ Mgmt     │  │   Services     │  │   Services       │     │  │
│  │  │ Service  │  │   (K8s pods    │  │   (K8s pods      │     │  │
│  │  │ (3 pods) │  │   auto-scale)  │  │   auto-scale)    │     │  │
│  │  └──────────┘  └────────────────┘  └──────────────────┘     │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                     DATA LAYER                                │  │
│  │                                                                │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │  │
│  │  │PostgreSQL│  │  Redis   │  │TimescaleDB│  │   S3     │    │  │
│  │  │ Primary  │  │ Cluster  │  │ (Trades)  │  │(Documents│    │  │
│  │  │ + Read   │  │ (Cache,  │  │           │  │  Assets) │    │  │
│  │  │ Replicas │  │ Sessions,│  │           │  │          │    │  │
│  │  │          │  │ Pub/Sub) │  │           │  │          │    │  │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘    │  │
│  │                                                                │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐                   │  │
│  │  │ Kafka /  │  │ Elastic  │  │ ClickHouse│                   │  │
│  │  │ RabbitMQ │  │ Search   │  │(Analytics)│                   │  │
│  │  │(Events)  │  │(Logs,    │  │           │                   │  │
│  │  │          │  │ Search)  │  │           │                   │  │
│  │  └──────────┘  └──────────┘  └──────────┘                   │  │
│  └───────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### 12.2 Caching Strategy

```typescript
// Multi-layer caching with tenant awareness
class TenantAwareCacheService {
  private readonly l1Cache: Map<string, CacheEntry>;  // In-memory (per pod)
  private readonly l2Cache: RedisCluster;               // Distributed
  
  // Cache key patterns
  private buildKey(tenantId: string, entity: string, id: string): string {
    return `t:${tenantId}:${entity}:${id}`;
  }
  
  // Cache TTLs per data type
  private readonly TTL_CONFIG = {
    'tenant_config': 300,           // 5 minutes
    'tenant_branding': 3600,        // 1 hour
    'tenant_features': 300,         // 5 minutes
    'tenant_limits': 300,           // 5 minutes
    'challenge_template': 600,      // 10 minutes
    'trader_profile': 120,          // 2 minutes
    'account_balance': 10,          // 10 seconds (near real-time)
    'risk_parameters': 60,          // 1 minute
    'domain_mapping': 3600,         // 1 hour
  };
  
  // Cache invalidation on tenant updates
  async invalidateTenantCache(tenantId: string): Promise<void> {
    // Clear all L1 entries for this tenant
    for (const [key] of this.l1Cache) {
      if (key.startsWith(`t:${tenantId}:`)) {
        this.l1Cache.delete(key);
      }
    }
    
    // Publish invalidation event (all pods clear their L1)
    await this.l2Cache.publish('cache:invalidate', JSON.stringify({
      pattern: `t:${tenantId}:*`,
      timestamp: Date.now()
    }));
    
    // Clear L2
    const keys = await this.l2Cache.keys(`t:${tenantId}:*`);
    if (keys.length > 0) {
      await this.l2Cache.del(...keys);
    }
  }
}
```

### 12.3 Rate Limiting Strategy

```typescript
// Per-tenant rate limiting
interface RateLimitConfig {
  tenantId: string;
  tier: TenantTier;
  limits: {
    // API rate limits
    apiRequestsPerMinute: number;
    apiRequestsPerHour: number;
    
    // Per-endpoint limits
    authRequestsPerMinute: number;
    tradingRequestsPerSecond: number;
    reportRequestsPerHour: number;
    webhookCallsPerMinute: number;
    
    // Burst allowance
    burstMultiplier: number;        // e.g., 2x for short bursts
    burstWindowSeconds: number;      // e.g., 10 second burst window
    
    // Concurrent connections
    maxConcurrentWebsockets: number;
    maxConcurrentApiConnections: number;
  };
}

const TIER_RATE_LIMITS: Record<TenantTier, Partial<RateLimitConfig['limits']>> = {
  [TenantTier.STARTER]: {
    apiRequestsPerMinute: 100,
    apiRequestsPerHour: 3000,
    authRequestsPerMinute: 20,
    tradingRequestsPerSecond: 5,
    reportRequestsPerHour: 50,
    maxConcurrentWebsockets: 100,
    burstMultiplier: 1.5,
  },
  [TenantTier.PROFESSIONAL]: {
    apiRequestsPerMinute: 500,
    apiRequestsPerHour: 15000,
    authRequestsPerMinute: 50,
    tradingRequestsPerSecond: 20,
    reportRequestsPerHour: 200,
    maxConcurrentWebsockets: 500,
    burstMultiplier: 2,
  },
  [TenantTier.ENTERPRISE]: {
    apiRequestsPerMinute: 5000,
    apiRequestsPerHour: 150000,
    authRequestsPerMinute: 200,
    tradingRequestsPerSecond: 100,
    reportRequestsPerHour: 1000,
    maxConcurrentWebsockets: 5000,
    burstMultiplier: 3,
  },
};
```

### 12.4 High Availability Design

```
┌──────────────────────────────────────────────────────────────┐
│               HIGH AVAILABILITY ARCHITECTURE                  │
│                                                               │
│  Multi-Region Active-Active (for Enterprise tier)            │
│                                                               │
│  ┌───────────────────┐     ┌───────────────────┐            │
│  │   Region: US-East │     │  Region: EU-West  │            │
│  │                   │     │                   │            │
│  │  ┌─────────────┐  │     │  ┌─────────────┐  │            │
│  │  │ App Cluster  │  │◄───►│  │ App Cluster  │  │            │
│  │  │ (K8s)       │  │     │  │ (K8s)       │  │            │
│  │  └─────────────┘  │     │  └─────────────┘  │            │
│  │                   │     │                   │            │
│  │  ┌─────────────┐  │     │  ┌─────────────┐  │            │
│  │  │ PostgreSQL  │  │◄───►│  │ PostgreSQL  │  │            │
│  │  │ Primary     │  │ Rep │  │ Primary     │  │            │
│  │  │ + Replicas  │  │     │  │ + Replicas  │  │            │
│  │  └─────────────┘  │     │  └─────────────┘  │            │
│  │                   │     │                   │            │
│  │  ┌─────────────┐  │     │  ┌─────────────┐  │            │
│  │  │ Redis       │  │◄───►│  │ Redis       │  │            │
│  │  │ Cluster     │  │     │  │ Cluster     │  │            │
│  │  └─────────────┘  │     │  └─────────────┘  │            │
│  └───────────────────┘     └───────────────────┘            │
│                                                               │
│  Failover Strategy:                                          │
│  ├── DNS-based failover (Route53 health checks)              │
│  ├── Automatic database failover (Patroni/RDS Multi-AZ)     │
│  ├── Redis Sentinel for cache failover                       │
│  ├── Cross-region message queue replication                  │
│  └── RPO < 1 second, RTO < 30 seconds                       │
│                                                               │
│  Per-Tenant Resilience:                                      │
│  ├── Tenant failure isolation (bulkhead pattern)             │
│  ├── Circuit breakers per tenant trading connections         │
│  ├── Graceful degradation (read-only mode)                   │
│  └── Tenant-specific health monitoring                       │
└──────────────────────────────────────────────────────────────┘
```

---

## 13. Security Architecture

### 13.1 Security Layers

```
┌─────────────────────────────────────────────────────────────────┐
│                    SECURITY ARCHITECTURE                         │
│                                                                  │
│  LAYER 1: PERIMETER SECURITY                                    │
│  ├── CloudFlare / AWS Shield (DDoS Protection)                  │
│  ├── Web Application Firewall (WAF)                             │
│  ├── Bot detection and mitigation                               │
│  ├── Geo-blocking (per regulatory requirements)                 │
│  └── IP reputation scoring                                      │
│                                                                  │
│  LAYER 2: NETWORK SECURITY                                      │
│  ├── VPC isolation                                              │
│  ├── Private subnets for data tier                              │
│  ├── Security groups / Network ACLs                             │
│  ├── VPN for admin access                                       │
│  └── mTLS for service-to-service communication                  │
│                                                                  │
│  LAYER 3: APPLICATION SECURITY                                  │
│  ├── OWASP Top 10 protections                                   │
│  ├── Input validation and sanitization                          │
│  ├── SQL injection prevention (parameterized queries + RLS)     │
│  ├── XSS prevention (CSP headers, output encoding)             │
│  ├── CSRF protection                                            │
│  ├── API key rotation                                           │
│  ├── Request signing for critical operations                    │
│  └── Tenant context validation on every request                 │
│                                                                  │
│  LAYER 4: DATA SECURITY                                        │
│  ├── Encryption at rest (AES-256)                               │
│  ├── Encryption in transit (TLS 1.3)                            │
│  ├── Field-level encryption for PII                             │
│  ├── Database RLS enforcement                                   │
│  ├── Key management (AWS KMS / Vault)                           │
│  ├── Data masking for non-production environments               │
│  └── Secure backup encryption                                  │
│                                                                  │
│  LAYER 5: ACCESS CONTROL                                        │
│  ├── Multi-factor authentication (MFA)                          │
│  ├── Role-based access control (RBAC)                           │
│  ├── Attribute-based access control (ABAC) for fine-grained    │
│  ├── Session management with sliding expiration                 │
│  ├── IP whitelisting for admin operations                       │
│  ├── Device fingerprinting                                      │
│  └── Privileged access management (PAM)                        │
│                                                                  │
│  LAYER 6: MONITORING & DETECTION                                │
│  ├── Security Information and Event Management (SIEM)           │
│  ├── Intrusion detection system (IDS)                           │
│  ├── Anomaly detection (login patterns, data access patterns)   │
│  ├── Real-time alerting for security events                     │
│  ├── Automated threat response                                  │
│  └── Regular penetration testing                                │
└─────────────────────────────────────────────────────────────────┘
```

### 13.2 Tenant Isolation Security Controls

```typescript
// Critical security checks to prevent cross-tenant data access
class TenantSecurityGuard {
  
  // 1. Request-level tenant validation
  async validateTenantAccess(request: Request, tenantContext: TenantContext): Promise<void> {
    const user = request.user;
    
    // Ensure user belongs to the resolved tenant
    if (user.tenantId !== tenantContext.tenantId) {
      await this.alertService.raiseSecurityAlert({
        type: 'CROSS_TENANT_ACCESS_ATTEMPT',
        severity: 'CRITICAL',
        userId: user.id,
        userTenantId: user.tenantId,
        targetTenantId: tenantContext.tenantId,
        ipAddress: request.ip,
        timestamp: new Date()
      });
      throw new ForbiddenException('Cross-tenant access denied');
    }
  }
  
  // 2. Database-level tenant validation  
  async validateQueryTenantScope(query: DatabaseQuery): Promise<void> {
    // Verify every query that touches tenant-scoped tables includes tenant_id filter
    if (!query.hasTenantFilter() && !query.isPlatformAdminQuery()) {
      throw new SecurityException('Query missing tenant scope filter');
    }
  }
  
  // 3. Response-level tenant validation
  async validateResponseTenantScope(response: any, tenantId: string): Promise<void> {
    // Deep scan response objects for tenant_id mismatches
    const foreignTenantIds = this.scanForForeignTenantIds(response, tenantId);
    if (foreignTenantIds.length > 0) {
      await this.alertService.raiseSecurityAlert({
        type: 'CROSS_TENANT_DATA_LEAK',
        severity: 'CRITICAL',
        tenantId,
        foreignTenantIds,
        timestamp: new Date()
      });
      throw new SecurityException('Response contains cross-tenant data');
    }
  }
  
  // 4. Prevent tenant ID manipulation
  async validateTenantIdImmutability(entity: any, update: any): Promise<void> {
    if (update.tenantId && update.tenantId !== entity.tenantId) {
      throw new SecurityException('Tenant ID modification not allowed');
    }
  }
}
```

---

## 14. Monitoring, Observability & Analytics

### 14.1 Observability Stack

```
┌─────────────────────────────────────────────────────────────────┐
│                  OBSERVABILITY ARCHITECTURE                      │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    METRICS (Prometheus + Grafana)          │   │
│  │                                                           │   │
│  │  Platform Metrics:                                       │   │
│  │  ├── Total active tenants                                │   │
│  │  ├── Total traders across all tenants                    │   │
│  │  ├── Platform API latency (p50, p95, p99)               │   │
│  │  ├── Error rates (global and per-tenant)                 │   │
│  │  ├── Infrastructure utilization                          │   │
│  │  └── Revenue metrics                                     │   │
│  │                                                           │   │
│  │  Per-Tenant Metrics:                                     │   │
│  │  ├── Active traders count                                │   │
│  │  ├── Active challenges count                             │   │
│  │  ├── Active funded accounts                              │   │
│  │  ├── API usage (requests/minute)                         │   │
│  │  ├── Storage utilization                                 │   │
│  │  ├── Database query latency                              │   │
│  │  ├── Error rate                                          │   │
│  │  ├── Challenge pass/fail rates                           │   │
│  │  ├── Average payout processing time                      │   │
│  │  └── Risk violations count                               │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                 LOGGING (ELK / Loki)                      │   │
│  │                                                           │   │
│  │  Structured Logging with Tenant Context:                 │   │
│  │  {                                                       │   │
│  │    "timestamp": "2024-01-15T10:30:00Z",                  │   │
│  │    "level": "INFO",                                      │   │
│  │    "service": "trading-service",                         │   │
│  │    "tenant_id": "t_abc123",                              │   │
│  │    "user_id": "u_xyz789",                                │   │
│  │    "trace_id": "tr_111222",                              │   │
│  │    "span_id": "sp_333444",                               │   │
│  │    "message": "Challenge evaluation completed",          │   │
│  │    "metadata": {                                         │   │
│  │      "challenge_id": "ch_555",                           │   │
│  │      "result": "passed",                                 │   │
│  │      "phase": 1                                          │   │
│  │    }                                                     │   │
│  │  }                                                       │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              DISTRIBUTED TRACING (Jaeger / Tempo)         │   │
│  │                                                           │   │
│  │  Trace propagation with tenant context:                  │   │
│  │  Request → API GW → Auth → Tenant Service → Trading     │   │
│  │    → Risk Engine → Database                              │   │
│  │                                                           │   │
│  │  Tenant-scoped trace filtering                           │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    ALERTING                               │   │
│  │                                                           │   │
│  │  Platform Alerts:                                        │   │
│  │  ├── Tenant provisioning failure                         │   │
│  │  ├── Cross-tenant data access attempt                    │   │
│  │  ├── Platform-wide error rate spike                      │   │
│  │  ├── Infrastructure capacity warnings                    │   │
│  │  └── Billing/payment failures                            │   │
│  │                                                           │   │
│  │  Per-Tenant Alerts (configurable by tenant admin):       │   │
│  │  ├── Risk limit breach                                   │   │
│  │  ├── Unusual trading activity                            │   │
│  │  ├── Payout processing failure                           │   │
│  │  ├── KYC verification failure spike                      │   │
│  │  └── API rate limit approaching                          │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 14.2 Tenant Health Dashboard

```typescript
interface TenantHealthDashboard {
  tenantId: string;
  timestamp: Date;
  
  // Overall health score (0-100)
  healthScore: number;
  
  // Component health
  components: {
    api: HealthStatus;
    database: HealthStatus;
    tradingConnectivity: HealthStatus;
    paymentProcessing: HealthStatus;
    emailDelivery: HealthStatus;
    kycProvider: HealthStatus;
  };
  
  // Key metrics
  metrics: {
    activeTraders: number;
    activeChallenge: number;
    fundedAccounts: number;
    dailyRevenue: number;
    pendingPayouts: number;
    openRiskAlerts: number;
    apiLatencyP95: number;
    errorRate: number;
    uptime30d: number;
  };
  
  // Recent issues
  recentIncidents: Incident[];
  
  // Resource utilization
  resourceUsage: {
    apiQuotaUsed: number;          // percentage
    storageUsed: number;           // percentage
    traderQuotaUsed: number;       // percentage
  };
}
```

---

## 15. API Design & Integration Layer

### 15.1 API Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      API ARCHITECTURE                            │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                   PUBLIC APIs                             │   │
│  │                                                           │   │
│  │  Platform Admin API   (/platform/v1/...)                 │   │
│  │  ├── POST   /tenants                                     │   │
│  │  ├── GET    /tenants                                     │   │
│  │  ├── GET    /tenants/{id}                                │   │
│  │  ├── PATCH  /tenants/{id}                                │   │
│  │  ├── POST   /tenants/{id}/suspend                        │   │
│  │  ├── POST   /tenants/{id}/activate                       │   │
│  │  ├── DELETE /tenants/{id}                                │   │
│  │  ├── GET    /tenants/{id}/usage                          │   │
│  │  ├── GET    /tenants/{id}/health                         │   │
│  │  └── GET    /platform/analytics                          │   │
│  │                                                           │   │
│  │  Tenant Admin API    (/api/v1/...)                       │   │
│  │  ├── Traders                                             │   │
│  │  │   ├── POST   /traders                                 │   │
│  │  │   ├── GET    /traders                                 │   │
│  │  │   ├── GET    /traders/{id}                            │   │
│  │  │   ├── PATCH  /traders/{id}                            │   │
│  │  │   └── POST   /traders/{id}/suspend                    │   │
│  │  │                                                       │   │
│  │  ├── Challenges                                          │   │
│  │  │   ├── POST   /challenges/templates                    │   │
│  │  │   ├── GET    /challenges/templates                    │   │
│  │  │   ├── POST   /challenges                              │   │
│  │  │   ├── GET    /challenges                              │   │
│  │  │   └── GET    /challenges/{id}                         │   │
│  │  │                                                       │   │
│  │  ├── Accounts                                            │   │
│  │  │   ├── POST   /accounts                                │   │
│  │  │   ├── GET    /accounts                                │   │
│  │  │   ├── GET    /accounts/{id}                           │   │
│  │  │   ├── GET    /accounts/{id}/trades                    │   │
│  │  │   ├── GET    /accounts/{id}/statistics                │   │
│  │  │   └── POST   /accounts/{id}/close                     │   │
│  │  │                                                       │   │
│  │  ├── Risk Management                                     │   │
│  │  │   ├── GET    /risk/config                             │   │
│  │  │   ├── PUT    /risk/config                             │   │
│  │  │   ├── GET    /risk/alerts                             │   │
│  │  │   └── GET    /risk/dashboard                          │   │
│  │  │                                                       │   │
│  │  ├── Payouts                                             │   │
│  │  │   ├── GET    /payouts                                 │   │
│  │  │   ├── POST   /payouts/{id}/approve                    │   │
│  │  │   └── POST   /payouts/{id}/reject                     │   │
│  │  │                                                       │   │
│  │  ├── Configuration                                       │   │
│  │  │   ├── GET    /config/branding                         │   │
│  │  │   ├── PUT    /config/branding                         │   │
│  │  │   ├── GET    /config/trading                          │   │
│  │  │   └── PUT    /config/trading                          │   │
│  │  │                                                       │   │
│  │  └── Reports                                             │   │
│  │      ├── GET    /reports/revenue                         │   │
│  │      ├── GET    /reports/traders                         │   │
│  │      └── GET    /reports/challenges                      │   │
│  │                                                           │   │
│  │  Trader API          (/trader/v1/...)                    │   │
│  │  ├── GET    /profile                                     │   │
│  │  ├── GET    /accounts                                    │   │
│  │  ├── GET    /accounts/{id}/trades                        │   │
│  │  ├── GET    /accounts/{id}/stats                         │   │
│  │  ├── POST   /challenges/purchase                         │   │
│  │  ├── POST   /payouts/request                             │   │
│  │  └── GET    /payouts                                     │   │
│  │                                                           │   │
│  │  Webhook API         (/webhooks/v1/...)                  │   │
│  │  ├── POST   /webhooks                                    │   │
│  │  ├── GET    /webhooks                                    │   │
│  │  ├── DELETE /webhooks/{id}                               │   │
│  │  └── POST   /webhooks/{id}/test                          │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 15.2 Event-Driven Architecture

```typescript
// Domain Events for the multi-tenant platform
namespace DomainEvents {
  
  // Tenant Events
  interface TenantCreated {
    tenantId: string;
    firmName: string;
    tier: TenantTier;
    timestamp: Date;
  }
  
  interface TenantActivated {
    tenantId: string;
    activatedBy: string;
    timestamp: Date;
  }
  
  interface TenantSuspended {
    tenantId: string;
    reason: string;
    suspendedBy: string;
    timestamp: Date;
  }
  
  interface TenantTierChanged {
    tenantId: string;
    previousTier: TenantTier;
    newTier: TenantTier;
    timestamp: Date;
  }
  
  // Trader Events
  interface TraderRegistered {
    tenantId: string;
    traderId: string;
    email: string;
    timestamp: Date;
  }
  
  interface TraderKYCCompleted {
    tenantId: string;
    traderId: string;
    status: 'approved' | 'rejected';
    timestamp: Date;
  }
  
  // Challenge Events
  interface ChallengePurchased {
    tenantId: string;
    traderId: string;
    challengeId: string;
    amount: number;
    currency: string;
    timestamp: Date;
  }
  
  interface ChallengePhaseCompleted {
    tenantId: string;
    traderId: string;
    challengeId: string;
    phase: number;
    result: 'passed' | 'failed';
    metrics: ChallengeMetrics;
    timestamp: Date;
  }
  
  interface AccountFunded {
    tenantId: string;
    traderId: string;
    accountId: string;
    balance: number;
    profitSplit: number;
    timestamp: Date;
  }
  
  // Risk Events
  interface RiskLimitBreached {
    tenantId: string;
    traderId: string;
    accountId: string;
    limitType: 'daily_loss' | 'total_loss' | 'position_size';
    currentValue: number;
    limitValue: number;
    action: 'warning' | 'close_positions' | 'suspend_account';
    timestamp: Date;
  }
  
  // Payout Events
  interface PayoutRequested {
    tenantId: string;
    traderId: string;
    payoutId: string;
    amount: number;
    currency: string;
    method: string;
    timestamp: Date;
  }
  
  interface PayoutProcessed {
    tenantId: string;
    payoutId: string;
    status: 'completed' | 'failed';
    transactionId: string;
    timestamp: Date;
  }
}

// Webhook delivery for tenant integrations
interface WebhookConfig {
  tenantId: string;
  url: string;
  secret: string;  // HMAC signing secret
  events: string[];
  active: boolean;
  retryPolicy: {
    maxRetries: number;
    backoffMultiplier: number;
    maxBackoffSeconds: number;
  };
}
```

---

## 16. Technology Stack Recommendations

### 16.1 Recommended Stack

```
┌─────────────────────────────────────────────────────────────────┐
│                  TECHNOLOGY STACK                                 │
│                                                                  │
│  FRONTEND                                                       │
│  ├── Framework:     Next.js 14+ (App Router)                    │
│  ├── UI Library:    Tailwind CSS + Shadcn/ui                    │
│  ├── State:         Zustand + TanStack Query                    │
│  ├── Charts:        TradingView Lightweight Charts / Recharts   │
│  ├── Real-time:     Socket.io client                            │
│  └── Testing:       Playwright + Vitest                         │
│                                                                  │
│  BACKEND                                                        │
│  ├── Runtime:       Node.js 20+ / Bun                           │
│  ├── Framework:     NestJS (modular, enterprise patterns)       │
│  ├── Language:      TypeScript 5+                               │
│  ├── API:           REST (primary) + GraphQL (analytics)        │
│  ├── Real-time:     Socket.io / WebSocket                       │
│  ├── ORM:           Prisma / TypeORM / Drizzle                  │
│  ├── Validation:    Zod / Class-validator                       │
│  ├── Testing:       Jest + Supertest                            │
│  └── Documentation: OpenAPI 3.1 (Swagger)                       │
│                                                                  │
│  ALTERNATIVE BACKEND (for high-performance components)          │
│  ├── Language:      Go / Rust                                   │
│  ├── Use cases:     Risk engine, trade processor, matching      │
│  └── Framework:     Gin (Go) / Actix (Rust)                     │
│                                                                  │
│  DATABASES                                                      │
│  ├── Primary:       PostgreSQL 16+ (with RLS)                   │
│  ├── Time-series:   TimescaleDB (trades, market data)           │
│  ├── Cache:         Redis 7+ (Cluster mode)                     │
│  ├── Search:        Elasticsearch / Meilisearch                 │
│  ├── Analytics:     ClickHouse / Apache Druid                   │
│  └── Document:      S3 (KYC docs, assets, backups)              │
│                                                                  │
│  MESSAGE QUEUE                                                  │
│  ├── Primary:       Apache Kafka (event streaming)              │
│  ├── Task Queue:    BullMQ (Redis-based, for async jobs)        │
│  └── Alternative:   RabbitMQ / NATS                             │
│                                                                  │
│  INFRASTRUCTURE                                                 │
│  ├── Cloud:         AWS (primary) / GCP (secondary)             │
│  ├── Containers:    Docker + Kubernetes (EKS)                   │
│  ├── CI/CD:         GitHub Actions + ArgoCD                     │
│  ├── IaC:           Terraform + Pulumi                          │
│  ├── Service Mesh:  Istio / Linkerd                             │
│  └── Secrets:       AWS Secrets Manager / HashiCorp Vault       │
│                                                                  │
│  OBSERVABILITY                                                  │
│  ├── Metrics:       Prometheus + Grafana                        │
│  ├── Logging:       Loki / ELK Stack                            │
│  ├── Tracing:       Jaeger / Tempo                              │
│  ├── APM:           Datadog / New Relic                         │
│  └── Alerting:      PagerDuty + OpsGenie                        │
│                                                                  │
│  THIRD-PARTY SERVICES                                           │
│  ├── Auth:          Keycloak (self-hosted) / Auth0              │
│  ├── Payments:      Stripe Connect                              │
│  ├── KYC:           Sumsub / Onfido                             │
│  ├── Email:         SendGrid / AWS SES                          │
│  ├── SMS:           Twilio                                      │
│  ├── CDN:           CloudFlare                                  │
│  ├── DNS:           CloudFlare / Route53                        │
│  └── File Storage:  AWS S3 + CloudFront                         │
│                                                                  │
│  TRADING INTEGRATIONS                                           │
│  ├── MetaTrader:    MT5 Web API / Manager API                   │
│  ├── cTrader:       cTrader Open API                            │
│  ├── DXtrade:       DXtrade API                                 │
│  ├── Market Data:   Various providers (depending on instruments) │
│  └── Liquidity:     LP connections (Prime of Prime brokers)     │
└─────────────────────────────────────────────────────────────────┘
```

---

## 17. Database Schema Design

### 17.1 Platform-Level Schema

```sql
-- ============================================
-- PLATFORM DATABASE SCHEMA
-- ============================================

-- Core Tenants Table
CREATE TABLE tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug VARCHAR(100) UNIQUE NOT NULL,
    external_id VARCHAR(100) UNIQUE,
    
    -- Business Info
    firm_name VARCHAR(255) NOT NULL,
    legal_entity_name VARCHAR(255),
    registration_number VARCHAR(100),
    tax_id VARCHAR(100),
    
    -- Contact
    primary_contact_name VARCHAR(200),
    primary_contact_email VARCHAR(255) NOT NULL,
    primary_contact_phone VARCHAR(50),
    support_email VARCHAR(255),
    
    -- Status
    status VARCHAR(50) NOT NULL DEFAULT 'pending_approval',
    tier VARCHAR(50) NOT NULL DEFAULT 'starter',
    onboarding_state JSONB DEFAULT '{"currentStep": "company_profile", "completedSteps": []}',
    
    -- Isolation
    isolation_level VARCHAR(20) NOT NULL DEFAULT 'shared',
    data_region VARCHAR(20) NOT NULL DEFAULT 'us-east-1',
    database_config JSONB, -- encrypted connection details
    
    -- Branding
    branding JSONB DEFAULT '{}',
    
    -- Domain
    subdomain VARCHAR(100) UNIQUE,
    custom_domain VARCHAR(255) UNIQUE,
    custom_domain_verified BOOLEAN DEFAULT FALSE,
    ssl_certificate_id VARCHAR(255),
    
    -- Billing
    stripe_customer_id VARCHAR(255),
    stripe_account_id VARCHAR(255),  -- Connected account
    subscription_id VARCHAR(255),
    billing_email VARCHAR(255),
    
    -- Limits
    limits JSONB NOT NULL DEFAULT '{
        "maxTraders": 500,
        "maxActiveAccounts": 1000,
        "maxFundedCapital": 1000000,
        "apiRateLimit": 100,
        "storageQuotaGB": 10,
        "maxAdminUsers": 3
    }',
    
    -- Settings
    settings JSONB NOT NULL DEFAULT '{}',
    
    -- Feature Flags
    features JSONB NOT NULL DEFAULT '{}',
    
    -- Compliance
    jurisdiction VARCHAR(10),
    kyb_status VARCHAR(50) DEFAULT 'pending',
    kyb_verified_at TIMESTAMPTZ,
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    tags TEXT[] DEFAULT '{}',
    
    -- Audit
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by UUID,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_by UUID,
    activated_at TIMESTAMPTZ,
    suspended_at TIMESTAMPTZ,
    suspended_reason TEXT,
    terminated_at TIMESTAMPTZ,
    deletion_scheduled_at TIMESTAMPTZ,
    
    -- Constraints
    CONSTRAINT chk_tenant_status CHECK (status IN (
        'pending_approval', 'provisioning', 'onboarding', 'active',
        'suspended', 'deactivated', 'pending_deletion', 'deleted', 'archived'
    )),
    CONSTRAINT chk_tenant_tier CHECK (tier IN ('starter', 'professional', 'enterprise', 'custom')),
    CONSTRAINT chk_isolation_level CHECK (isolation_level IN ('shared', 'schema', 'dedicated', 'isolated'))
);

-- Indexes
CREATE INDEX idx_tenants_status ON tenants(status);
CREATE INDEX idx_tenants_tier ON tenants(tier);
CREATE INDEX idx_tenants_custom_domain ON tenants(custom_domain) WHERE custom_domain IS NOT NULL;
CREATE INDEX idx_tenants_stripe_customer ON tenants(stripe_customer_id) WHERE stripe_customer_id IS NOT NULL;

-- Tenant Admin Users (platform-level user mapping)
CREATE TABLE tenant_admin_users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    user_id UUID NOT NULL,  -- Reference to IdP user
    email VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL,
    is_owner BOOLEAN DEFAULT FALSE,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    invited_by UUID,
    invited_at TIMESTAMPTZ DEFAULT NOW(),
    accepted_at TIMESTAMPTZ,
    last_login_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    CONSTRAINT uq_tenant_admin_email UNIQUE (tenant_id, email),
    CONSTRAINT chk_admin_role CHECK (role IN (
        'firm_admin', 'firm_manager', 'risk_officer', 'support_agent', 'finance_manager'
    ))
);

-- Feature Flags
CREATE TABLE feature_flags (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    key VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    default_value BOOLEAN DEFAULT FALSE,
    tier_overrides JSONB DEFAULT '{}',  -- {"starter": false, "professional": true}
    tenant_overrides JSONB DEFAULT '{}', -- {"tenant_id_1": true}
    is_system BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Billing & Subscriptions
CREATE TABLE tenant_subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    stripe_subscription_id VARCHAR(255),
    plan_id VARCHAR(100) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    current_period_start TIMESTAMPTZ NOT NULL,
    current_period_end TIMESTAMPTZ NOT NULL,
    cancel_at TIMESTAMPTZ,
    canceled_at TIMESTAMPTZ,
    trial_start TIMESTAMPTZ,
    trial_end TIMESTAMPTZ,
    monthly_amount DECIMAL(10,2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'USD',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Usage Metering
CREATE TABLE usage_events (
    id UUID DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    metric_name VARCHAR(100) NOT NULL,
    value DECIMAL(15,4) NOT NULL,
    unit VARCHAR(50) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB DEFAULT '{}',
    idempotency_key VARCHAR(255),
    
    PRIMARY KEY (tenant_id, id, timestamp)
) PARTITION BY RANGE (timestamp);

-- Provisioning Jobs
CREATE TABLE provisioning_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id),
    type VARCHAR(50) NOT NULL,  -- 'provision', 'deprovision', 'migrate', 'upgrade'
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    current_step VARCHAR(100),
    completed_steps JSONB DEFAULT '[]',
    failed_step VARCHAR(100),
    error_message TEXT,
    context JSONB DEFAULT '{}',
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Domain Mappings
CREATE TABLE domain_mappings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    domain VARCHAR(255) UNIQUE NOT NULL,
    type VARCHAR(20) NOT NULL,  -- 'subdomain', 'custom'
    verified BOOLEAN DEFAULT FALSE,
    verification_token VARCHAR(255),
    ssl_status VARCHAR(50) DEFAULT 'pending',
    ssl_certificate_arn VARCHAR(500),
    dns_records JSONB DEFAULT '[]',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Audit Log (immutable, append-only)
CREATE TABLE audit_logs (
    id UUID DEFAULT gen_random_uuid(),
    tenant_id UUID,
    user_id UUID,
    user_email VARCHAR(255),
    user_role VARCHAR(50),
    session_id VARCHAR(255),
    event_type VARCHAR(100) NOT NULL,
    event_category VARCHAR(50) NOT NULL,
    action VARCHAR(50) NOT NULL,
    resource VARCHAR(100) NOT NULL,
    resource_id VARCHAR(255),
    description TEXT,
    previous_state JSONB,
    new_state JSONB,
    changed_fields TEXT[],
    ip_address INET,
    user_agent TEXT,
    request_id VARCHAR(255),
    api_endpoint VARCHAR(500),
    http_method VARCHAR(10),
    country VARCHAR(2),
    risk_score SMALLINT DEFAULT 0,
    flagged BOOLEAN DEFAULT FALSE,
    checksum VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    PRIMARY KEY (id, created_at)
) PARTITION BY RANGE (created_at);

-- No UPDATE or DELETE policies on audit_logs
REVOKE UPDATE, DELETE ON audit_logs FROM PUBLIC;
```

### 17.2 Tenant-Level Schema (per tenant)

```sql
-- ============================================
-- TENANT DATABASE SCHEMA
-- (Replicated per tenant or with tenant_id column + RLS)
-- ============================================

-- Traders
CREATE TABLE traders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    
    -- Identity
    email VARCHAR(255) NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    phone VARCHAR(50),
    date_of_birth DATE,
    
    -- Address
    country VARCHAR(2),
    city VARCHAR(100),
    address TEXT,
    postal_code VARCHAR(20),
    
    -- Account
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    kyc_status VARCHAR(50) NOT NULL DEFAULT 'not_started',
    kyc_provider_id VARCHAR(255),
    kyc_verified_at TIMESTAMPTZ,
    
    -- Financial
    total_challenges_purchased INTEGER DEFAULT 0,
    total_funded_accounts INTEGER DEFAULT 0,
    total_payouts DECIMAL(15,2) DEFAULT 0,
    current_funded_balance DECIMAL(15,2) DEFAULT 0,
    
    -- Preferences
    preferred_language VARCHAR(5) DEFAULT 'en',
    preferred_currency VARCHAR(3) DEFAULT 'USD',
    timezone VARCHAR(50) DEFAULT 'UTC',
    
    -- Auth
    auth_provider_id VARCHAR(255),  -- IdP user ID
    last_login_at TIMESTAMPTZ,
    login_count INTEGER DEFAULT 0,
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    referral_code VARCHAR(50),
    referred_by UUID,
    utm_source VARCHAR(100),
    
    -- Audit
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    CONSTRAINT uq_trader_email UNIQUE (tenant_id, email)
);

-- Challenge Templates
CREATE TABLE challenge_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    sort_order INTEGER DEFAULT 0,
    
    -- Configuration
    platform VARCHAR(50) NOT NULL,
    leverage VARCHAR(10) NOT NULL,
    phases JSONB NOT NULL,
    account_sizes JSONB NOT NULL,
    funded_config JSONB NOT NULL,
    trading_rules JSONB NOT NULL,
    
    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Challenges (purchased by traders)
CREATE TABLE challenges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    trader_id UUID NOT NULL REFERENCES traders(id),
    template_id UUID NOT NULL REFERENCES challenge_templates(id),
    
    -- Status
    status VARCHAR(50) NOT NULL DEFAULT 'pending_payment',
    current_phase INTEGER DEFAULT 1,
    
    -- Configuration snapshot
    config_snapshot JSONB NOT NULL,  -- Snapshot of template at purchase time
    account_size DECIMAL(15,2) NOT NULL,
    currency VARCHAR(3) NOT NULL,
    
    -- Payment
    payment_amount DECIMAL(10,2) NOT NULL,
    payment_currency VARCHAR(3) NOT NULL,
    payment_status VARCHAR(50) NOT NULL DEFAULT 'pending',
    payment_provider_id VARCHAR(255),
    payment_received_at TIMESTAMPTZ,
    
    -- Timeline
    purchased_at TIMESTAMPTZ DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    failed_at TIMESTAMPTZ,
    expired_at TIMESTAMPTZ,
    
    -- Result
    result VARCHAR(50),  -- 'passed', 'failed', 'expired'
    failure_reason VARCHAR(255),
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Trading Accounts
CREATE TABLE trading_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    trader_id UUID NOT NULL REFERENCES traders(id),
    challenge_id UUID REFERENCES challenges(id),
    
    -- Account details
    account_number VARCHAR(50) NOT NULL,
    platform VARCHAR(50) NOT NULL,
    platform_account_id VARCHAR(255), -- External platform ID
    account_type VARCHAR(50) NOT NULL,
    phase INTEGER,
    
    -- Balances
    initial_balance DECIMAL(15,2) NOT NULL,
    current_balance DECIMAL(15,2) NOT NULL,
    equity DECIMAL(15,2) NOT NULL DEFAULT 0,
    floating_pnl DECIMAL(15,2) DEFAULT 0,
    
    -- P&L
    total_profit DECIMAL(15,2) DEFAULT 0,
    total_loss DECIMAL(15,2) DEFAULT 0,
    net_pnl DECIMAL(15,2) DEFAULT 0,
    
    -- Risk metrics
    max_daily_loss_limit DECIMAL(15,2),
    max_total_loss_limit DECIMAL(15,2),
    profit_target DECIMAL(15,2),
    current_daily_loss DECIMAL(15,2) DEFAULT 0,
    current_drawdown DECIMAL(15,2) DEFAULT 0,
    max_drawdown_reached DECIMAL(15,2) DEFAULT 0,
    
    -- Trading stats
    total_trades INTEGER DEFAULT 0,
    winning_trades INTEGER DEFAULT 0,
    losing_trades INTEGER DEFAULT 0,
    trading_days INTEGER DEFAULT 0,
    
    -- Status
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    
    -- Funded account specifics
    profit_split DECIMAL(5,2),
    total_payouts DECIMAL(15,2) DEFAULT 0,
    
    -- Timeline
    started_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    closed_at TIMESTAMPTZ,
    
    -- Leverage
    leverage VARCHAR(10),
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    CONSTRAINT uq_account_number UNIQUE (tenant_id, account_number)
);

-- Trades (time-series, high volume)
CREATE TABLE trades (
    id UUID DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    account_id UUID NOT NULL,
    trader_id UUID NOT NULL,
    
    -- Trade details
    ticket BIGINT NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    direction VARCHAR(4) NOT NULL,
    volume DECIMAL(10,4) NOT NULL,
    
    -- Prices
    open_price DECIMAL(15,6) NOT NULL,
    close_price DECIMAL(15,6),
    stop_loss DECIMAL(15,6),
    take_profit DECIMAL(15,6),
    
    -- Financials
    commission DECIMAL(10,4) DEFAULT 0,
    swap DECIMAL(10,4) DEFAULT 0,
    profit DECIMAL(15,4),
    
    -- Timing
    opened_at TIMESTAMPTZ NOT NULL,
    closed_at TIMESTAMPTZ,
    
    -- Risk
    risk_reward_ratio DECIMAL(10,4),
    is_violation BOOLEAN DEFAULT FALSE,
    violation_type VARCHAR(100),
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    PRIMARY KEY (id, opened_at)
) PARTITION BY RANGE (opened_at);

-- Payouts
CREATE TABLE payouts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    trader_id UUID NOT NULL REFERENCES traders(id),
    account_id UUID NOT NULL REFERENCES trading_accounts(id),
    
    -- Amount
    gross_amount DECIMAL(15,2) NOT NULL,
    platform_fee DECIMAL(15,2) DEFAULT 0,
    net_amount DECIMAL(15,2) NOT NULL,
    currency VARCHAR(3) NOT NULL,
    
    -- Profit split
    profit_split DECIMAL(5,2) NOT NULL,
    total_profit DECIMAL(15,2) NOT NULL,
    trader_share DECIMAL(15,2) NOT NULL,
    firm_share DECIMAL(15,2) NOT NULL,
    
    -- Payment
    payment_method VARCHAR(50) NOT NULL,
    payment_details JSONB,  -- encrypted
    payment_provider_id VARCHAR(255),
    
    -- Status
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    
    -- Workflow
    requested_at TIMESTAMPTZ DEFAULT NOW(),
    reviewed_at TIMESTAMPTZ,
    reviewed_by UUID,
    approved_at TIMESTAMPTZ,
    approved_by UUID,
    processed_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    rejected_at TIMESTAMPTZ,
    rejection_reason TEXT,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Risk Alerts
CREATE TABLE risk_alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    trader_id UUID NOT NULL,
    account_id UUID NOT NULL,
    
    alert_type VARCHAR(100) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    message TEXT NOT NULL,
    details JSONB,
    
    -- Response
    action_taken VARCHAR(100),
    action_taken_at TIMESTAMPTZ,
    action_taken_by UUID,
    resolved BOOLEAN DEFAULT FALSE,
    resolved_at TIMESTAMPTZ,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

## 18. Implementation Roadmap

### 18.1 Phased Implementation Plan

```
┌─────────────────────────────────────────────────────────────────┐
│                  IMPLEMENTATION ROADMAP                           │
│                                                                  │
│  PHASE 1: FOUNDATION (Weeks 1-8)                                │
│  ══════════════════════════════                                  │
│  ├── Core tenant data model and database schema                 │
│  ├── Tenant CRUD operations and REST API                        │
│  ├── PostgreSQL RLS implementation                              │
│  ├── Tenant resolution middleware                               │
│  ├── Basic authentication (JWT + Keycloak)                      │
│  ├── RBAC framework                                             │
│  ├── Tenant provisioning (basic - manual steps)                 │
│  ├── Configuration management service                           │
│  ├── Audit logging foundation                                   │
│  └── Development & staging environments                         │
│  Deliverable: MVP tenant management with basic isolation        │
│                                                                  │
│  PHASE 2: TENANT LIFECYCLE (Weeks 9-14)                         │
│  ═══════════════════════════════════                             │
│  ├── Automated provisioning pipeline (saga pattern)             │
│  ├── Tenant state machine implementation                        │
│  ├── Onboarding workflow engine                                 │
│  ├── Tenant suspension/reactivation                             │
│  ├── Feature flag system                                        │
│  ├── Tenant tier management                                     │
│  ├── Subscription billing (Stripe integration)                  │
│  ├── Basic usage metering                                       │
│  └── Platform admin dashboard (basic)                           │
│  Deliverable: Complete tenant lifecycle management              │
│                                                                  │
│  PHASE 3: TRADING INTEGRATION (Weeks 15-22)                     │
│  ═════════════════════════════════════════                       │
│  ├── MT5 integration (account provisioning, trade sync)         │
│  ├── Challenge template management                              │
│  ├── Challenge purchase and activation flow                     │
│  ├── Real-time trade monitoring                                 │
│  ├── Risk management engine (daily loss, max loss)              │
│  ├── Challenge evaluation engine                                │
│  ├── Funded account provisioning                                │
│  ├── Basic payout management                                    │
│  └── Trader portal (basic)                                      │
│  Deliverable: End-to-end challenge flow working                 │
│                                                                  │
│  PHASE 4: WHITE-LABEL & CUSTOMIZATION (Weeks 23-28)            │
│  ═══════════════════════════════════════════════════            │
│  ├── Branding engine (logo, colors, themes)                     │
│  ├── Custom domain support with SSL                             │
│  ├── Email template customization                               │
│  ├── Tenant-specific UI theming                                 │
│  ├── Custom challenge configuration UI                          │
│  ├── Tenant admin dashboard (full-featured)                     │
│  ├── Trader dashboard customization                             │
│  └── Marketing page templates                                   │
│  Deliverable: Fully white-labeled experience                    │
│                                                                  │
│  PHASE 5: COMPLIANCE & SECURITY (Weeks 29-34)                  │
│  ═══════════════════════════════════════════                    │
│  ├── KYC/KYB integration (Sumsub)                               │
│  ├── AML monitoring framework                                   │
│  ├── GDPR compliance (DSAR, consent, data deletion)             │
│  ├── Data encryption (field-level for PII)                      │
│  ├── Security hardening                                         │
│  ├── Penetration testing                                        │
│  ├── SOC 2 preparation                                          │
│  └── Audit log completeness review                              │
│  Deliverable: Compliance-ready platform                         │
│                                                                  │
│  PHASE 6: SCALE & OPTIMIZE (Weeks 35-42)                       │
│  ═══════════════════════════════════════                        │
│  ├── Performance optimization and load testing                  │
│  ├── Caching layer implementation                               │
│  ├── Database optimization (partitioning, indexing)             │
│  ├── Advanced rate limiting                                     │
│  ├── Horizontal scaling validation                              │
│  ├── Multi-region support (for enterprise tenants)              │
│  ├── Dedicated database migration tooling                       │
│  ├── Advanced analytics (ClickHouse)                            │
│  └── Monitoring & alerting (Grafana dashboards)                 │
│  Deliverable: Production-ready, scalable platform               │
│                                                                  │
│  PHASE 7: ADVANCED FEATURES (Weeks 43-52)                      │
│  ════════════════════════════════════════                       │
│  ├── Advanced challenge types (scaling programs, etc.)          │
│  ├── Automated payout processing                                │
│  ├── Webhook system for tenant integrations                     │
│  ├── Public API for tenant developers                           │
│  ├── Marketplace (add-ons, integrations)                        │
│  ├── Advanced reporting & business intelligence                 │
│  ├── Mobile app support                                         │
│  ├── Additional trading platform integrations                   │
│  └── Partner/reseller program support                           │
│  Deliverable: Feature-complete enterprise platform              │
└─────────────────────────────────────────────────────────────────┘
```

### 18.2 Team Structure Recommendation

```
┌─────────────────────────────────────────────────────────────────┐
│                    TEAM STRUCTURE                                 │
│                                                                  │
│  CORE TEAM (Phase 1-3): 8-12 people                             │
│  ├── Engineering Lead / Architect (1)                           │
│  ├── Backend Engineers (3-4)                                    │
│  │   ├── Tenant management & infrastructure                    │
│  │   ├── Trading integration                                   │
│  │   └── Billing & compliance                                  │
│  ├── Frontend Engineers (2)                                     │
│  │   ├── Platform admin dashboard                              │
│  │   └── Tenant admin + trader portal                          │
│  ├── DevOps / SRE (1-2)                                        │
│  ├── QA Engineer (1)                                            │
│  └── Product Manager (1)                                        │
│                                                                  │
│  EXPANDED TEAM (Phase 4-7): 15-20 people                       │
│  ├── + Security Engineer (1)                                    │
│  ├── + Backend Engineers (2)                                    │
│  ├── + Frontend Engineer (1)                                    │
│  ├── + Data Engineer (1)                                        │
│  ├── + Compliance Specialist (1)                                │
│  └── + Technical Writer (1)                                     │
└─────────────────────────────────────────────────────────────────┘
```

---

## 19. Cost Analysis & Infrastructure Planning

### 19.1 Infrastructure Cost Estimation

```
┌─────────────────────────────────────────────────────────────────┐
│           MONTHLY INFRASTRUCTURE COSTS (AWS)                     │
│                                                                  │
│  SMALL SCALE (10 tenants, ~5,000 total traders)                 │
│  ═══════════════════════════════════════════                    │
│  ├── Compute (EKS - 3x m6i.xlarge)          $400              │
│  ├── PostgreSQL (RDS db.r6g.xlarge, Multi-AZ) $800             │
│  ├── Redis (ElastiCache r6g.large)            $250             │
│  ├── S3 Storage (100GB)                       $5               │
│  ├── CloudFront (CDN)                         $50              │
│  ├── Load Balancer (ALB)                      $50              │
│  ├── Kafka (MSK - 3 brokers)                  $400             │
│  ├── Monitoring (CloudWatch, Grafana)         $100             │
│  ├── Secrets Manager                          $20              │
│  ├── Route53                                  $10              │
│  └── Data Transfer                            $100             │
│  ────────────────────────────────────────────────              │
│  TOTAL:                                    ~$2,185/month       │
│                                                                  │
│  MEDIUM SCALE (50 tenants, ~50,000 total traders)               │
│  ════════════════════════════════════════════                   │
│  ├── Compute (EKS - 6x m6i.2xlarge)          $1,600           │
│  ├── PostgreSQL (RDS db.r6g.2xlarge + read)   $2,400           │
│  ├── TimescaleDB (db.r6g.xlarge)              $800             │
│  ├── Redis (ElastiCache r6g.xlarge cluster)   $600             │
│  ├── S3 Storage (1TB)                         $25              │
│  ├── CloudFront (CDN)                         $200             │
│  ├── Load Balancer (ALB)                      $100             │
│  ├── Kafka (MSK - 6 brokers)                  $1,200           │
│  ├── Elasticsearch (3 nodes)                  $600             │
│  ├── Monitoring                               $300             │
│  ├── Secrets Manager + KMS                    $50              │
│  ├── WAF                                      $100             │
│  └── Data Transfer                            $500             │
│  ────────────────────────────────────────────────              │
│  TOTAL:                                    ~$8,475/month       │
│                                                                  │
│  LARGE SCALE (200 tenants, ~500,000 total traders)              │
│  ═════════════════════════════════════════════                  │
│  ├── Compute (EKS - 15x m6i.4xlarge + auto)  $8,000           │
│  ├── PostgreSQL (Multi-AZ, multiple instances) $8,000           │
│  ├── TimescaleDB (cluster)                    $3,000           │
│  ├── Redis (cluster, multiple)                $2,000           │
│  ├── ClickHouse (analytics, 3 nodes)          $2,000           │
│  ├── S3 Storage (10TB)                        $250             │
│  ├── CloudFront (CDN)                         $1,000           │
│  ├── Load Balancer (ALB + NLB)                $300             │
│  ├── Kafka (MSK - 12 brokers)                 $3,600           │
│  ├── Elasticsearch (6 nodes)                  $1,800           │
│  ├── Monitoring & Observability               $1,000           │
│  ├── Multi-region replication                 $2,000           │
│  ├── WAF + Shield Advanced                    $3,000           │
│  ├── KMS + Secrets Manager                    $200             │
│  └── Data Transfer                            $2,000           │
│  ────────────────────────────────────────────────              │
│  TOTAL:                                   ~$38,150/month       │
│                                                                  │
│  THIRD-PARTY SERVICES (all scales)                              │
│  ═══════════════════════════════                               │
│  ├── Keycloak (self-hosted, included in compute)               │
│  ├── Stripe:           2.9% + $0.30 per transaction            │
│  ├── Sumsub KYC:       $1.50-3.00 per verification             │
│  ├── SendGrid:         $100-500/month                          │
│  ├── CloudFlare:       $200-1,000/month (Business/Enterprise)  │
│  ├── Datadog/NewRelic: $500-2,000/month                        │
│  ├── PagerDuty:        $50-200/month                           │
│  └── GitHub Enterprise: $21/user/month                         │
└─────────────────────────────────────────────────────────────────┘
```

### 19.2 Revenue vs Cost Analysis

```
┌─────────────────────────────────────────────────────────────────┐
│              REVENUE VS COST ANALYSIS                            │
│                                                                  │
│  SCENARIO: 50 TENANTS MIX                                       │
│  ═══════════════════════════                                    │
│  30 Starter   × $499    = $14,970                               │
│  15 Professional × $1,499 = $22,485                              │
│  5  Enterprise × $4,999  = $24,995                               │
│  ──────────────────────────────                                 │
│  Subscription Revenue:      $62,450/month                       │
│                                                                  │
│  Usage-based Revenue (est.): $15,000/month                      │
│  Revenue Share (est.):       $25,000/month                      │
│  ──────────────────────────────                                 │
│  TOTAL REVENUE:             ~$102,450/month                     │
│                                                                  │
│  Infrastructure Cost:        $8,475/month                       │
│  Third-party Services:       $3,000/month                       │
│  Team (15 people):          $150,000/month                      │
│  ──────────────────────────────                                 │
│  TOTAL COST:                ~$161,475/month                     │
│                                                                  │
│  Break-even: ~80 tenants (at similar mix)                       │
│  or ~100 Starter-heavy tenants                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 20. Risk Assessment & Mitigation

### 20.1 Technical Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Cross-tenant data leakage | Medium | Critical | RLS + application-level checks + response scanning + regular pen testing |
| Database performance degradation with tenant growth | High | High | Partitioning, read replicas, caching, dedicated DBs for large tenants |
| Trading platform API instability (MT5, etc.) | High | High | Circuit breakers, fallback queues, multi-platform support |
| Single point of failure in provisioning | Medium | High | Saga pattern with compensating transactions, manual override capability |
| Cache invalidation errors causing stale data | Medium | Medium | Short TTLs for critical data, event-driven invalidation, cache versioning |
| Noisy neighbor degradation | Medium | High | Resource quotas, rate limiting, tenant-scoped connection pools, bulkhead pattern |
| Data migration complexity during upgrades | High | Medium | Blue-green deployments, backward-compatible schema changes, feature flags |

### 20.2 Business Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Regulatory crackdown on prop trading | Medium | Critical | Jurisdictional flexibility, compliance engine, quick geo-blocking |
| Tenant using platform for fraudulent purposes | Medium | Critical | KYB verification, transaction monitoring, suspicious activity detection |
| Tenant churn due to competition | High | High | Feature velocity, platform lock-in through integrations, competitive pricing |
| Payment processor relationship issues | Medium | High | Multiple payment processors, direct bank integrations as backup |
| Key employee departure | Medium | Medium | Documentation, knowledge sharing, bus factor > 2 for all critical systems |

### 20.3 Operational Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Data breach | Low | Critical | Encryption, access controls, incident response plan, cyber insurance |
| Extended platform outage | Low | Critical | Multi-AZ deployment, failover automation, RTO < 15 minutes |
| Backup restoration failure | Low | Critical | Regular backup testing, cross-region backups, point-in-time recovery |
| Tenant data loss during deprovisioning | Low | High | Soft delete, grace periods, backup before deletion, confirmation workflows |
| Third-party service outage (Stripe, KYC) | Medium | Medium | Graceful degradation, queueing, alternative providers |

---

## Appendix A: Key Design Decisions Summary

| Decision | Choice | Rationale |
|---|---|---|
| Multi-tenancy pattern | Hybrid (RLS + dedicated for enterprise) | Balances cost, isolation, and scalability |
| Primary database | PostgreSQL with RLS | Mature, strong RLS support, extensible (TimescaleDB) |
| Backend framework | NestJS (TypeScript) | Modular, enterprise patterns, large ecosystem |
| Authentication | Keycloak (self-hosted) | Full control, multi-realm support, no per-user fees |
| Message queue | Apache Kafka | Event sourcing, replay capability, high throughput |
| Cache | Redis Cluster | Performance, pub/sub for cache invalidation, session storage |
| Payments | Stripe Connect | Split payments, connected accounts, global coverage |
| Container orchestration | Kubernetes (EKS) | Auto-scaling, service mesh, industry standard |
| Provisioning pattern | Saga with compensating transactions | Reliable multi-step provisioning with rollback |
| API style | REST (primary) + WebSocket (real-time) | Simplicity, cacheability, real-time trading data |

## Appendix B: Glossary

| Term | Definition |
|---|---|
| **PFaaS** | Prop Firm as a Service - the platform being built |
| **Tenant** | An individual prop trading firm operating on the platform |
| **Trader** | An end-user of a tenant's prop firm |
| **Challenge** | An evaluation program where traders prove their skills |
| **Funded Account** | A trading account provided to successful traders |
| **Profit Split** | The percentage division of trading profits between firm and trader |
| **RLS** | Row-Level Security - PostgreSQL feature for data isolation |
| **KYB** | Know Your Business - verification of tenant's business legitimacy |
| **KYC** | Know Your Customer - verification of trader's identity |
| **TEK** | Tenant Encryption Key |
| **DEK** | Data Encryption Key |

---

This comprehensive research document provides the complete architectural blueprint for building an enterprise-grade multi-tenant management module. The design prioritizes **data isolation security**, **operational scalability**, **regulatory compliance**, and **tenant autonomy** while maintaining a **cost-effective shared infrastructure** model.
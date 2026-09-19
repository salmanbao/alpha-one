# Comprehensive Research: Enterprise-Grade Authentication/Authorization & Multi-Tenant System for a Prop Firm as a Service Platform

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Domain Analysis: Prop Firm as a Service](#2-domain-analysis)
3. [Multi-Tenancy Architecture](#3-multi-tenancy-architecture)
4. [Authentication System Design](#4-authentication-system-design)
5. [Authorization System Design](#5-authorization-system-design)
6. [Identity Management](#6-identity-management)
7. [Data Isolation & Security](#7-data-isolation--security)
8. [Compliance & Regulatory Requirements](#8-compliance--regulatory-requirements)
9. [Technical Architecture & Implementation](#9-technical-architecture--implementation)
10. [Infrastructure & DevOps](#10-infrastructure--devops)
11. [Scaling Considerations](#11-scaling-considerations)
12. [Technology Stack Recommendations](#12-technology-stack-recommendations)
13. [Threat Modeling & Security Hardening](#13-threat-modeling--security-hardening)
14. [Reference Architecture](#14-reference-architecture)

---

## 1. Executive Summary

A **Prop Firm as a Service (PFaaS)** platform enables entrepreneurs to launch and operate proprietary trading firms without building infrastructure from scratch. This requires a sophisticated multi-tenant architecture where:

- **Platform Operator** → Manages the overall SaaS platform
- **Prop Firms (Tenants)** → Individual prop trading firms using the platform
- **Traders** → End-users who participate in challenges, funded accounts, etc.
- **Admins/Risk Managers/Support** → Various roles within each prop firm

The system must handle **financial data**, **trading credentials**, **payout information**, and operate under **financial regulatory scrutiny**, making security non-negotiable.

---

## 2. Domain Analysis

### 2.1 What Is a Prop Firm as a Service?

```
┌─────────────────────────────────────────────────────────────────┐
│                    PLATFORM OPERATOR (SaaS)                     │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │  Prop Firm A  │  │  Prop Firm B  │  │  Prop Firm C  │  ...   │
│  │  (Tenant)     │  │  (Tenant)     │  │  (Tenant)     │        │
│  │              │  │              │  │              │          │
│  │ ┌──────────┐ │  │ ┌──────────┐ │  │ ┌──────────┐ │          │
│  │ │ Traders  │ │  │ │ Traders  │ │  │ │ Traders  │ │          │
│  │ │ Admins   │ │  │ │ Admins   │ │  │ │ Admins   │ │          │
│  │ │ Risk Mgr │ │  │ │ Risk Mgr │ │  │ │ Risk Mgr │ │          │
│  │ └──────────┘ │  │ └──────────┘ │  │ └──────────┘ │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Core Domain Entities

| Entity | Description |
|--------|-------------|
| **Platform** | The overarching SaaS system |
| **Tenant (Prop Firm)** | An individual prop firm customer |
| **User** | Any person in the system (trader, admin, etc.) |
| **Challenge** | Trading evaluation programs |
| **Funded Account** | Live/simulated trading accounts post-challenge |
| **Payout** | Profit-sharing disbursements |
| **Trading Account** | MT4/MT5/cTrader account linkage |
| **Subscription/Billing** | Tenant's subscription to the platform |
| **KYC Record** | Identity verification documents |
| **Affiliate** | Referral/affiliate relationships |

### 2.3 Key User Personas & Hierarchies

```
Platform Level:
├── Platform Super Admin
├── Platform Support Staff
├── Platform Finance/Billing
│
Tenant (Prop Firm) Level:
├── Firm Owner
├── Firm Admin
├── Risk Manager
├── Compliance Officer
├── Support Agent
├── Affiliate Manager
│
End-User Level:
├── Trader (Challenge Phase)
├── Trader (Funded Phase)
├── Affiliate Partner
```

---

## 3. Multi-Tenancy Architecture

### 3.1 Tenancy Models Comparison

| Model | Description | Isolation | Cost | Complexity | Best For |
|-------|-------------|-----------|------|------------|----------|
| **Database per Tenant** | Each tenant gets own DB | Highest | High | High | Large tenants, regulatory requirements |
| **Schema per Tenant** | Shared DB, separate schemas | High | Medium | Medium | Medium-scale, good isolation needs |
| **Shared DB, Shared Schema** | Row-level isolation via tenant_id | Lowest | Low | Low | High volume of small tenants |
| **Hybrid** | Mix of above based on tenant tier | Variable | Variable | Highest | PFaaS (recommended) |

### 3.2 Recommended: Hybrid Approach

```
┌─────────────────────────────────────────────────────┐
│                  HYBRID STRATEGY                     │
│                                                      │
│  Enterprise Tier Tenants:                            │
│  ┌─────────────────────────────────┐                 │
│  │   Dedicated Database Instance    │                │
│  │   Dedicated Redis/Cache          │                │
│  │   Optional: Dedicated Compute    │                │
│  └─────────────────────────────────┘                 │
│                                                      │
│  Standard Tier Tenants:                              │
│  ┌─────────────────────────────────┐                 │
│  │   Schema-per-Tenant             │                │
│  │   Shared Cache (namespaced)     │                │
│  │   Shared Compute                │                │
│  └─────────────────────────────────┘                 │
│                                                      │
│  Starter Tier Tenants:                               │
│  ┌─────────────────────────────────┐                 │
│  │   Shared Schema + tenant_id     │                │
│  │   Shared Cache (namespaced)     │                │
│  │   Shared Compute                │                │
│  └─────────────────────────────────┘                 │
└─────────────────────────────────────────────────────┘
```

### 3.3 Tenant Resolution Strategy

```typescript
// Tenant Resolution Pipeline (ordered by priority)
interface TenantResolutionStrategy {
  // 1. Custom Domain: firm.propfirmx.com OR firm-custom-domain.com
  customDomain: (hostname: string) => Tenant | null;
  
  // 2. Subdomain: firmname.platform.com
  subdomain: (hostname: string) => Tenant | null;
  
  // 3. Path-based: platform.com/firm/firmname/...
  pathBased: (path: string) => Tenant | null;
  
  // 4. Header-based: X-Tenant-ID (for API/internal calls)
  headerBased: (headers: Headers) => Tenant | null;
  
  // 5. JWT Claim: tenant_id embedded in token
  tokenBased: (token: JWT) => Tenant | null;
}
```

### 3.4 Tenant Context Propagation

```typescript
// Middleware: Tenant Context Injection
class TenantContextMiddleware {
  async resolve(request: Request): Promise<TenantContext> {
    const tenant = await this.resolveTenant(request);
    
    return {
      tenantId: tenant.id,
      tenantSlug: tenant.slug,
      tenantConfig: tenant.config,
      databaseConnection: await this.getDatabaseConnection(tenant),
      cacheNamespace: `tenant:${tenant.id}`,
      featureFlags: await this.getFeatureFlags(tenant),
      rateLimitTier: tenant.subscription.tier,
      isolationLevel: tenant.isolationLevel, // 'dedicated' | 'schema' | 'shared'
    };
  }
}

// Every downstream service/query receives TenantContext
// Row-Level Security (RLS) in PostgreSQL:
// CREATE POLICY tenant_isolation ON trades
//   USING (tenant_id = current_setting('app.current_tenant_id')::uuid);
```

### 3.5 Tenant Data Model

```sql
-- Core Tenant/Organization Table
CREATE TABLE tenants (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug            VARCHAR(63) UNIQUE NOT NULL,  -- subdomain identifier
    name            VARCHAR(255) NOT NULL,
    
    -- Branding
    logo_url        TEXT,
    primary_color   VARCHAR(7),
    custom_domain   VARCHAR(255) UNIQUE,
    
    -- Configuration
    config          JSONB NOT NULL DEFAULT '{}',
    feature_flags   JSONB NOT NULL DEFAULT '{}',
    
    -- Subscription & Tier
    subscription_tier   VARCHAR(50) NOT NULL DEFAULT 'starter',
    isolation_level     VARCHAR(20) NOT NULL DEFAULT 'shared',
    
    -- Status
    status          VARCHAR(20) NOT NULL DEFAULT 'active',
    
    -- Metadata
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    suspended_at    TIMESTAMPTZ,
    deleted_at      TIMESTAMPTZ  -- soft delete
);

-- Tenant-specific settings
CREATE TABLE tenant_settings (
    tenant_id               UUID REFERENCES tenants(id),
    
    -- Trading Configuration
    max_daily_loss_pct      DECIMAL(5,2) DEFAULT 5.00,
    max_total_loss_pct      DECIMAL(5,2) DEFAULT 10.00,
    profit_split_pct        DECIMAL(5,2) DEFAULT 80.00,
    
    -- KYC Requirements
    kyc_required            BOOLEAN DEFAULT true,
    kyc_provider            VARCHAR(50) DEFAULT 'sumsub',
    
    -- Payout Configuration
    min_payout_amount       DECIMAL(10,2) DEFAULT 50.00,
    payout_frequency_days   INTEGER DEFAULT 14,
    
    -- Broker Integration
    broker_type             VARCHAR(50),  -- 'mt4', 'mt5', 'ctrader'
    broker_server           VARCHAR(255),
    
    PRIMARY KEY (tenant_id)
);
```

---

## 4. Authentication System Design

### 4.1 Authentication Architecture Overview

```
┌────────────────────────────────────────────────────────────────────────┐
│                     AUTHENTICATION LAYER                               │
│                                                                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                │
│  │   Web App     │  │  Mobile App  │  │  Trading Bot │                │
│  │  (SPA/SSR)   │  │  (Native)    │  │   (M2M)      │                │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘                │
│         │                  │                  │                        │
│         ▼                  ▼                  ▼                        │
│  ┌─────────────────────────────────────────────────┐                  │
│  │              API Gateway / Edge                   │                │
│  │         (Rate Limiting, WAF, CORS)               │                │
│  └─────────────────────┬───────────────────────────┘                  │
│                        │                                              │
│                        ▼                                              │
│  ┌─────────────────────────────────────────────────┐                  │
│  │          Identity Provider (IdP)                 │                │
│  │                                                   │                │
│  │  ┌───────────┐ ┌───────────┐ ┌───────────────┐  │                │
│  │  │  OAuth2/  │ │   SAML    │ │  API Keys/    │  │                │
│  │  │  OIDC     │ │   SSO     │ │  M2M Tokens   │  │                │
│  │  └───────────┘ └───────────┘ └───────────────┘  │                │
│  │                                                   │                │
│  │  ┌───────────┐ ┌───────────┐ ┌───────────────┐  │                │
│  │  │  MFA      │ │ Passkeys/ │ │  Social       │  │                │
│  │  │  TOTP/SMS │ │ WebAuthn  │ │  Login        │  │                │
│  │  └───────────┘ └───────────┘ └───────────────┘  │                │
│  └─────────────────────────────────────────────────┘                  │
└────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Authentication Methods Matrix

| Method | Use Case | Security Level | UX Impact |
|--------|----------|----------------|-----------|
| **Email + Password** | Primary trader/admin login | Medium | Low friction |
| **OAuth2/OIDC (Google, etc.)** | Social/enterprise SSO | High | Low friction |
| **SAML 2.0** | Enterprise tenant admin SSO | Highest | Medium friction |
| **MFA - TOTP** | All admin roles, optional for traders | High | Medium friction |
| **MFA - SMS/Email OTP** | Fallback MFA, password recovery | Medium | Medium friction |
| **Passkeys/WebAuthn** | Modern passwordless | Highest | Low friction |
| **API Keys** | Bot/integration access | Medium | N/A |
| **M2M Tokens (Client Credentials)** | Service-to-service | High | N/A |
| **Magic Links** | Passwordless email login | Medium | Low friction |
| **Mutual TLS (mTLS)** | Internal service mesh | Highest | N/A |

### 4.3 Token Strategy

```
┌─────────────────────────────────────────────────────────────┐
│                    TOKEN ARCHITECTURE                        │
│                                                              │
│  Access Token (JWT)                                          │
│  ├── Short-lived: 15 minutes                                │
│  ├── Contains: user_id, tenant_id, roles, permissions       │
│  ├── Signed: RS256 (asymmetric) with key rotation           │
│  └── Audience: specific API services                        │
│                                                              │
│  Refresh Token                                               │
│  ├── Long-lived: 7-30 days (configurable per tenant)        │
│  ├── Stored: HTTP-only, Secure, SameSite=Strict cookie      │
│  ├── One-time use with rotation (RTR)                       │
│  ├── Bound to: device fingerprint + IP range                │
│  └── Revocable: stored in database/Redis                    │
│                                                              │
│  ID Token (OIDC)                                             │
│  ├── Contains: user profile information                     │
│  ├── Short-lived: same as access token                      │
│  └── For client-side user info only                         │
│                                                              │
│  Session Token (optional, for SSR apps)                      │
│  ├── Opaque token → server-side session store               │
│  ├── Stored: HTTP-only cookie                               │
│  └── Backed by: Redis with TTL                              │
└─────────────────────────────────────────────────────────────┘
```

### 4.4 JWT Structure

```typescript
// Access Token Claims
interface AccessTokenPayload {
  // Standard Claims
  iss: string;          // "https://auth.platform.com"
  sub: string;          // user UUID
  aud: string[];        // ["https://api.platform.com"]
  exp: number;          // expiration timestamp
  iat: number;          // issued at
  jti: string;          // unique token ID (for revocation)
  
  // Custom Claims
  tenant_id: string;    // tenant UUID
  tenant_slug: string;  // "acme-trading"
  org_role: string;     // role within tenant: "admin", "trader", etc.
  permissions: string[];// ["trades:read", "accounts:manage"]
  
  // Security Claims
  auth_time: number;    // when authentication occurred
  amr: string[];        // authentication methods: ["pwd", "mfa"]
  acr: string;          // authentication context class
  
  // Session Binding
  sid: string;          // session ID
  device_id: string;    // device fingerprint hash
}
```

### 4.5 Authentication Flow - Primary (Email/Password + MFA)

```
┌──────┐     ┌──────────┐     ┌───────────┐     ┌──────────┐
│Client│     │API Gateway│     │Auth Service│     │ Database │
└──┬───┘     └────┬─────┘     └─────┬─────┘     └────┬─────┘
   │              │                  │                 │
   │ POST /auth/login               │                 │
   │ {email, password}              │                 │
   │──────────────►│                │                 │
   │              │ Forward + rate limit              │
   │              │─────────────────►│                │
   │              │                  │ Lookup user     │
   │              │                  │────────────────►│
   │              │                  │◄────────────────│
   │              │                  │                 │
   │              │                  │ Verify password │
   │              │                  │ (Argon2id)      │
   │              │                  │                 │
   │              │                  │ Check MFA req   │
   │              │  MFA_REQUIRED    │                 │
   │◄─────────────│◄─────────────────│                │
   │  {mfa_token, methods: ["totp"]}│                 │
   │              │                  │                 │
   │ POST /auth/mfa/verify          │                 │
   │ {mfa_token, code: "123456"}    │                 │
   │──────────────►│                │                 │
   │              │─────────────────►│                │
   │              │                  │ Verify TOTP     │
   │              │                  │                 │
   │              │                  │ Create session  │
   │              │                  │────────────────►│
   │              │                  │                 │
   │              │  Set-Cookie: refresh_token        │
   │◄─────────────│◄─────────────────│                │
   │  {access_token, id_token}      │                 │
   │              │                  │                 │
```

### 4.6 Password Security

```typescript
// Password Hashing Configuration
const passwordConfig = {
  algorithm: 'argon2id',        // Winner of Password Hashing Competition
  memoryCost: 65536,            // 64 MB
  timeCost: 3,                  // 3 iterations
  parallelism: 4,               // 4 threads
  hashLength: 32,               // 32 bytes
  saltLength: 16,               // 16 bytes auto-generated
};

// Password Policy (configurable per tenant)
interface PasswordPolicy {
  minLength: number;            // default: 12
  maxLength: number;            // default: 128
  requireUppercase: boolean;    // default: true
  requireLowercase: boolean;    // default: true
  requireNumbers: boolean;      // default: true
  requireSpecialChars: boolean; // default: true
  preventCommonPasswords: boolean; // check against breached DB
  preventPasswordReuse: number; // last N passwords
  maxAge: number;               // days before forced rotation
  lockoutThreshold: number;     // failed attempts before lockout
  lockoutDuration: number;      // minutes
}
```

### 4.7 Session Management

```typescript
// Session Schema
interface Session {
  id: string;                   // UUID
  userId: string;               // user UUID
  tenantId: string;             // tenant UUID
  
  // Token References
  refreshTokenHash: string;     // hashed refresh token
  accessTokenJti: string;       // current access token ID
  
  // Device/Client Info
  deviceFingerprint: string;    // hashed device fingerprint
  userAgent: string;
  ipAddress: string;
  geoLocation: {
    country: string;
    city: string;
    coordinates: [number, number];
  };
  
  // Security
  mfaVerified: boolean;
  authMethods: string[];        // ["password", "totp"]
  riskScore: number;            // 0-100
  
  // Lifecycle
  createdAt: Date;
  lastActivityAt: Date;
  expiresAt: Date;
  revokedAt: Date | null;
  revocationReason: string | null;
  
  // Concurrent Session Control
  isActive: boolean;
}

// Session Policies
interface SessionPolicy {
  maxConcurrentSessions: number;     // default: 5
  absoluteTimeout: number;           // 24 hours
  idleTimeout: number;               // 30 minutes
  refreshTokenRotation: boolean;     // always true
  bindToIP: boolean;                 // configurable
  bindToDevice: boolean;             // true for funded accounts
  geoFencing: {
    enabled: boolean;
    allowedCountries: string[];
    alertOnNewCountry: boolean;
  };
}
```

### 4.8 Key Rotation Strategy

```
┌─────────────────────────────────────────────────────────┐
│                KEY MANAGEMENT                            │
│                                                          │
│  Signing Keys (RS256):                                   │
│  ├── Primary Key: Active for signing                    │
│  ├── Secondary Key: Previous key, still valid           │
│  │                  for verification                     │
│  ├── Rotation: Every 90 days (automated)                │
│  └── Published: /.well-known/jwks.json                  │
│                                                          │
│  Encryption Keys (for sensitive data):                   │
│  ├── Master Key: AWS KMS / GCP Cloud KMS / Vault        │
│  ├── Data Encryption Keys (DEK): per-tenant             │
│  ├── Envelope Encryption pattern                         │
│  └── Rotation: Every 365 days                           │
│                                                          │
│  API Keys:                                               │
│  ├── Hashed with SHA-256 (only prefix stored)           │
│  ├── Scoped to tenant + specific permissions            │
│  ├── Expiration: configurable (default 90 days)         │
│  └── Rate limited independently                         │
└─────────────────────────────────────────────────────────┘
```

---

## 5. Authorization System Design

### 5.1 Authorization Model Selection

```
┌─────────────────────────────────────────────────────────────────┐
│              AUTHORIZATION MODEL COMPARISON                      │
│                                                                  │
│  RBAC (Role-Based Access Control)                               │
│  ├── Simple to implement and understand                         │
│  ├── Good for: static role hierarchies                          │
│  └── Limitation: role explosion with fine-grained needs         │
│                                                                  │
│  ABAC (Attribute-Based Access Control)                          │
│  ├── Flexible, policy-driven                                    │
│  ├── Good for: complex, dynamic authorization                  │
│  └── Limitation: complex to audit and debug                    │
│                                                                  │
│  ReBAC (Relationship-Based Access Control)                      │
│  ├── Models real-world relationships                            │
│  ├── Good for: multi-tenant, hierarchical data                 │
│  └── Limitation: requires specialized infrastructure           │
│                                                                  │
│  ★ RECOMMENDED: RBAC + ABAC Hybrid with ReBAC elements ★       │
│  ├── RBAC for coarse-grained role assignment                   │
│  ├── ABAC policies for fine-grained decisions                  │
│  └── ReBAC for tenant/org relationship modeling                │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 Role Hierarchy

```typescript
// Platform-Level Roles (God-mode roles)
enum PlatformRole {
  PLATFORM_SUPER_ADMIN = 'platform:super_admin',
  PLATFORM_ADMIN = 'platform:admin',
  PLATFORM_SUPPORT = 'platform:support',
  PLATFORM_FINANCE = 'platform:finance',
  PLATFORM_READONLY = 'platform:readonly',
}

// Tenant-Level Roles (within a prop firm)
enum TenantRole {
  FIRM_OWNER = 'firm:owner',
  FIRM_ADMIN = 'firm:admin',
  RISK_MANAGER = 'firm:risk_manager',
  COMPLIANCE_OFFICER = 'firm:compliance',
  SUPPORT_AGENT = 'firm:support',
  AFFILIATE_MANAGER = 'firm:affiliate_mgr',
  FINANCE_MANAGER = 'firm:finance',
  READONLY = 'firm:readonly',
}

// End-User Roles (traders, affiliates)
enum UserRole {
  TRADER = 'user:trader',
  FUNDED_TRADER = 'user:funded_trader',
  AFFILIATE = 'user:affiliate',
}

// Role Hierarchy (inheritance)
const roleHierarchy = {
  'platform:super_admin': ['platform:admin'],
  'platform:admin': ['platform:support', 'platform:finance'],
  'firm:owner': ['firm:admin'],
  'firm:admin': ['firm:risk_manager', 'firm:compliance', 'firm:support', 
                  'firm:affiliate_mgr', 'firm:finance'],
  'user:funded_trader': ['user:trader'],
};
```

### 5.3 Permission System

```typescript
// Resource-Action Permission Model
// Format: resource:action or resource:sub-resource:action

const permissions = {
  // Tenant Management
  'tenants:create': 'Create new tenants (platform only)',
  'tenants:read': 'View tenant details',
  'tenants:update': 'Modify tenant settings',
  'tenants:delete': 'Delete/suspend tenants',
  'tenants:billing:manage': 'Manage tenant billing',
  
  // User Management
  'users:list': 'List users in tenant',
  'users:read': 'View user profile',
  'users:create': 'Create/invite users',
  'users:update': 'Modify user details',
  'users:delete': 'Remove users',
  'users:roles:assign': 'Assign roles to users',
  'users:impersonate': 'Impersonate a user (audit-logged)',
  
  // Trading
  'challenges:create': 'Create challenge configurations',
  'challenges:read': 'View challenge details',
  'challenges:purchase': 'Purchase a challenge',
  'trades:read:own': 'View own trading history',
  'trades:read:all': 'View all traders\' history',
  'accounts:read:own': 'View own trading accounts',
  'accounts:read:all': 'View all trading accounts',
  'accounts:manage': 'Create/modify trading accounts',
  
  // Risk Management
  'risk:rules:manage': 'Configure risk rules',
  'risk:alerts:read': 'View risk alerts',
  'risk:override': 'Override risk decisions',
  'risk:breach:handle': 'Handle rule breaches',
  
  // Financial
  'payouts:request': 'Request payout (trader)',
  'payouts:approve': 'Approve payouts',
  'payouts:process': 'Process/execute payouts',
  'payouts:read:own': 'View own payouts',
  'payouts:read:all': 'View all payouts',
  'billing:read': 'View billing information',
  'billing:manage': 'Manage billing/subscriptions',
  
  // KYC/Compliance
  'kyc:submit': 'Submit KYC documents',
  'kyc:review': 'Review KYC submissions',
  'kyc:approve': 'Approve/reject KYC',
  
  // Affiliates
  'affiliates:manage': 'Manage affiliate program',
  'affiliates:read:own': 'View own affiliate data',
  'affiliates:commissions:manage': 'Manage commission structures',
  
  // Platform Configuration
  'config:branding:manage': 'Manage firm branding',
  'config:integrations:manage': 'Manage third-party integrations',
  'config:challenges:templates': 'Manage challenge templates',
  
  // Audit
  'audit:logs:read': 'View audit logs',
  'audit:logs:export': 'Export audit logs',
};

// Role-Permission Mapping
const rolePermissions: Record<string, string[]> = {
  'firm:owner': [
    'tenants:read', 'tenants:update',
    'users:*',
    'challenges:*',
    'trades:read:all',
    'accounts:*',
    'risk:*',
    'payouts:*',
    'billing:*',
    'kyc:*',
    'affiliates:*',
    'config:*',
    'audit:*',
  ],
  'firm:risk_manager': [
    'trades:read:all',
    'accounts:read:all',
    'risk:*',
    'users:list', 'users:read',
  ],
  'user:trader': [
    'challenges:read', 'challenges:purchase',
    'trades:read:own',
    'accounts:read:own',
    'payouts:request', 'payouts:read:own',
    'kyc:submit',
    'affiliates:read:own',
  ],
  // ... etc
};
```

### 5.4 Policy Engine Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    POLICY DECISION FLOW                          │
│                                                                  │
│  Request                                                         │
│    │                                                             │
│    ▼                                                             │
│  ┌─────────────────────────┐                                     │
│  │  Policy Enforcement     │  (API Gateway / Middleware)         │
│  │  Point (PEP)            │                                     │
│  └───────────┬─────────────┘                                     │
│              │                                                    │
│              ▼                                                    │
│  ┌─────────────────────────┐                                     │
│  │  Policy Decision        │  (Authorization Service)            │
│  │  Point (PDP)            │                                     │
│  │                         │                                     │
│  │  1. Load user context   │                                     │
│  │  2. Resolve roles       │                                     │
│  │  3. Check permissions   │                                     │
│  │  4. Evaluate ABAC       │                                     │
│  │     policies            │                                     │
│  │  5. Return decision     │                                     │
│  └───────────┬─────────────┘                                     │
│              │                                                    │
│         ┌────┴────┐                                              │
│         ▼         ▼                                              │
│    ┌─────────┐ ┌──────────┐                                      │
│  │  Policy  │ │ Policy   │                                      │
│  │  Info    │ │ Admin    │                                      │
│  │  Point   │ │ Point    │                                      │
│  │  (PIP)   │ │ (PAP)    │                                      │
│  │          │ │          │                                      │
│  │ User DB  │ │ Policy   │                                      │
│  │ Tenant DB│ │ Editor   │                                      │
│  │ External │ │ Version  │                                      │
│  │ Data     │ │ Control  │                                      │
│  └─────────┘ └──────────┘                                      │
└─────────────────────────────────────────────────────────────────┘
```

### 5.5 ABAC Policy Examples

```typescript
// Policy: Trader can only view their own trades
const traderOwnTradesPolicy: Policy = {
  id: 'trades-own-access',
  effect: 'ALLOW',
  description: 'Traders can only access their own trades',
  target: {
    resource: 'trades',
    action: 'read',
  },
  condition: {
    and: [
      { attribute: 'subject.role', operator: 'equals', value: 'user:trader' },
      { attribute: 'resource.user_id', operator: 'equals', value: '${subject.id}' },
      { attribute: 'resource.tenant_id', operator: 'equals', value: '${subject.tenant_id}' },
    ]
  }
};

// Policy: Payouts require MFA verification
const payoutMfaPolicy: Policy = {
  id: 'payout-mfa-required',
  effect: 'DENY',
  description: 'Payout actions require MFA within last 5 minutes',
  target: {
    resource: 'payouts',
    action: ['approve', 'process'],
  },
  condition: {
    or: [
      { attribute: 'subject.mfa_verified', operator: 'equals', value: false },
      { 
        attribute: 'subject.mfa_verified_at', 
        operator: 'older_than', 
        value: '5m' 
      },
    ]
  }
};

// Policy: Risk manager can only manage accounts up to certain size
const riskManagerAccountLimit: Policy = {
  id: 'risk-manager-account-limit',
  effect: 'DENY',
  description: 'Risk managers cannot override accounts > $500k without firm owner approval',
  target: {
    resource: 'accounts',
    action: 'risk:override',
  },
  condition: {
    and: [
      { attribute: 'subject.role', operator: 'equals', value: 'firm:risk_manager' },
      { attribute: 'resource.account_size', operator: 'greater_than', value: 500000 },
      { attribute: 'context.has_owner_approval', operator: 'equals', value: false },
    ]
  }
};

// Policy: IP-based geo-restriction for funded accounts
const geoRestrictionPolicy: Policy = {
  id: 'funded-account-geo-restriction',
  effect: 'DENY',
  description: 'Deny access to funded accounts from restricted countries',
  target: {
    resource: 'funded_accounts',
    action: '*',
  },
  condition: {
    and: [
      { attribute: 'context.geo.country', operator: 'in', 
        value: '${tenant.config.restricted_countries}' },
    ]
  }
};
```

### 5.6 Authorization Service Implementation

```typescript
// Authorization Service (simplified)
class AuthorizationService {
  
  async authorize(request: AuthorizationRequest): Promise<AuthorizationDecision> {
    const { subject, resource, action, context } = request;
    
    // Step 1: Tenant isolation check (always first)
    if (!this.verifyTenantAccess(subject, resource)) {
      return { allowed: false, reason: 'TENANT_ISOLATION_VIOLATION' };
    }
    
    // Step 2: Check if user is suspended/banned
    if (subject.status !== 'active') {
      return { allowed: false, reason: 'USER_NOT_ACTIVE' };
    }
    
    // Step 3: Platform admin override (with audit)
    if (this.isPlatformAdmin(subject) && context.impersonating) {
      await this.auditLog('IMPERSONATION', subject, resource, action);
      return { allowed: true, reason: 'PLATFORM_ADMIN_OVERRIDE' };
    }
    
    // Step 4: RBAC check
    const rbacResult = await this.checkRBAC(subject, resource, action);
    if (rbacResult.denied) {
      return { allowed: false, reason: 'RBAC_DENIED' };
    }
    
    // Step 5: ABAC policy evaluation
    const abacResult = await this.evaluateABACPolicies(
      subject, resource, action, context
    );
    
    // Step 6: Combine decisions (deny-overrides strategy)
    const decision = this.combineDecisions(rbacResult, abacResult);
    
    // Step 7: Audit log
    await this.auditLog(decision.allowed ? 'ALLOW' : 'DENY', 
                         subject, resource, action, decision.reason);
    
    return decision;
  }
  
  // Caching strategy for performance
  async checkRBACCached(userId: string, tenantId: string): Promise<RolePermissions> {
    const cacheKey = `authz:${tenantId}:${userId}`;
    
    let result = await this.cache.get(cacheKey);
    if (!result) {
      result = await this.computeEffectivePermissions(userId, tenantId);
      await this.cache.set(cacheKey, result, { ttl: 300 }); // 5 min cache
    }
    
    return result;
  }
}
```

---

## 6. Identity Management

### 6.1 User Identity Model

```sql
-- Core Identity (platform-wide, tenant-independent)
CREATE TABLE identities (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Primary Credentials
    email           VARCHAR(255) UNIQUE NOT NULL,
    email_verified  BOOLEAN NOT NULL DEFAULT false,
    phone           VARCHAR(20),
    phone_verified  BOOLEAN NOT NULL DEFAULT false,
    
    -- Password (nullable for social-only accounts)
    password_hash   TEXT,
    password_changed_at TIMESTAMPTZ,
    password_history JSONB DEFAULT '[]',  -- hashed previous passwords
    
    -- Profile
    first_name      VARCHAR(100),
    last_name       VARCHAR(100),
    display_name    VARCHAR(200),
    avatar_url      TEXT,
    date_of_birth   DATE,
    nationality     VARCHAR(3),  -- ISO 3166-1 alpha-3
    
    -- Account Status
    status          VARCHAR(20) NOT NULL DEFAULT 'pending_verification',
    -- pending_verification, active, suspended, banned, deactivated
    
    -- Security
    mfa_enabled     BOOLEAN NOT NULL DEFAULT false,
    mfa_methods     JSONB DEFAULT '[]',
    failed_login_attempts INTEGER DEFAULT 0,
    locked_until    TIMESTAMPTZ,
    last_login_at   TIMESTAMPTZ,
    
    -- Metadata
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ  -- GDPR soft delete
);

-- Tenant Memberships (many-to-many: user can be in multiple firms)
CREATE TABLE tenant_memberships (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    identity_id     UUID NOT NULL REFERENCES identities(id),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    
    -- Role within this tenant
    role            VARCHAR(50) NOT NULL DEFAULT 'user:trader',
    custom_permissions JSONB DEFAULT '[]',  -- additional per-user permissions
    
    -- Status within tenant
    status          VARCHAR(20) NOT NULL DEFAULT 'active',
    
    -- Tenant-specific profile overrides
    display_name_override VARCHAR(200),
    
    -- Timestamps
    joined_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_active_at  TIMESTAMPTZ,
    suspended_at    TIMESTAMPTZ,
    
    UNIQUE(identity_id, tenant_id)
);

-- Social/External Identity Links
CREATE TABLE identity_providers (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    identity_id     UUID NOT NULL REFERENCES identities(id),
    provider        VARCHAR(50) NOT NULL,  -- 'google', 'github', 'saml'
    provider_user_id VARCHAR(255) NOT NULL,
    provider_email  VARCHAR(255),
    provider_data   JSONB DEFAULT '{}',
    
    linked_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    UNIQUE(provider, provider_user_id)
);

-- MFA Credentials
CREATE TABLE mfa_credentials (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    identity_id     UUID NOT NULL REFERENCES identities(id),
    
    method          VARCHAR(20) NOT NULL,  -- 'totp', 'webauthn', 'sms', 'email'
    
    -- TOTP
    totp_secret     TEXT,  -- encrypted
    
    -- WebAuthn
    webauthn_credential_id TEXT,
    webauthn_public_key TEXT,
    webauthn_counter INTEGER,
    
    -- Recovery
    recovery_codes  TEXT[],  -- hashed
    
    is_primary      BOOLEAN DEFAULT false,
    verified        BOOLEAN DEFAULT false,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_used_at    TIMESTAMPTZ
);

-- API Keys
CREATE TABLE api_keys (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    identity_id     UUID NOT NULL REFERENCES identities(id),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    
    key_prefix      VARCHAR(8) NOT NULL,   -- first 8 chars for identification
    key_hash        TEXT NOT NULL,          -- SHA-256 hash of full key
    
    name            VARCHAR(100) NOT NULL,
    scopes          TEXT[] NOT NULL,        -- allowed permissions
    
    rate_limit      INTEGER DEFAULT 1000,  -- requests per minute
    
    expires_at      TIMESTAMPTZ,
    last_used_at    TIMESTAMPTZ,
    last_used_ip    INET,
    
    is_active       BOOLEAN DEFAULT true,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### 6.2 User Lifecycle Management

```
┌─────────────────────────────────────────────────────────────┐
│                  USER LIFECYCLE                              │
│                                                              │
│  Registration                                                │
│  ├── 1. Email/Password or Social OAuth                      │
│  ├── 2. Email verification                                   │
│  ├── 3. Tenant association (via invite link or direct)       │
│  ├── 4. Basic profile completion                             │
│  └── 5. KYC (if required by tenant)                         │
│                                                              │
│  Active Usage                                                │
│  ├── Challenge purchase & trading                            │
│  ├── Account management                                      │
│  ├── MFA enrollment (prompted/required)                      │
│  └── Profile updates                                         │
│                                                              │
│  Suspension                                                  │
│  ├── Risk rule violation                                     │
│  ├── KYC failure                                             │
│  ├── Platform policy violation                               │
│  └── Payment dispute                                         │
│                                                              │
│  Deactivation / Deletion                                     │
│  ├── Voluntary account deletion (GDPR)                       │
│  ├── Data retention policy compliance                        │
│  ├── Anonymization of historical data                        │
│  └── 30-day grace period before hard delete                  │
│                                                              │
│  Cross-Tenant                                                │
│  ├── User can join multiple tenants                          │
│  ├── Single identity, multiple memberships                   │
│  ├── Independent roles per tenant                            │
│  └── Unified login, tenant switcher                          │
└─────────────────────────────────────────────────────────────┘
```

### 6.3 Invitation & Onboarding Flow

```typescript
// Invitation System
interface TenantInvitation {
  id: string;
  tenantId: string;
  invitedBy: string;          // user ID of inviter
  email: string;
  role: TenantRole;
  
  token: string;              // unique invite token (hashed in DB)
  expiresAt: Date;            // 7 days default
  
  status: 'pending' | 'accepted' | 'expired' | 'revoked';
  acceptedAt?: Date;
  
  // Optional: pre-configured permissions
  customPermissions?: string[];
  
  // Metadata
  createdAt: Date;
  metadata?: {
    department?: string;
    notes?: string;
  };
}

// Self-Registration Flow (for traders via prop firm's branded page)
class TraderRegistrationService {
  
  async register(input: TraderRegistrationInput): Promise<RegistrationResult> {
    // 1. Resolve tenant from request context (subdomain/domain)
    const tenant = await this.tenantResolver.resolve(input.tenantContext);
    
    // 2. Check if registration is enabled for this tenant
    if (!tenant.config.selfRegistrationEnabled) {
      throw new ForbiddenError('Registration is not enabled');
    }
    
    // 3. Validate input against tenant's requirements
    await this.validateRegistration(input, tenant);
    
    // 4. Check for existing identity
    let identity = await this.identityRepo.findByEmail(input.email);
    
    if (identity) {
      // User exists - check if already member of this tenant
      const membership = await this.membershipRepo.find(identity.id, tenant.id);
      if (membership) {
        throw new ConflictError('Already registered with this firm');
      }
      // Create new membership for existing identity
    } else {
      // Create new identity
      identity = await this.identityRepo.create({
        email: input.email,
        passwordHash: await this.hashPassword(input.password),
        firstName: input.firstName,
        lastName: input.lastName,
      });
    }
    
    // 5. Create tenant membership
    await this.membershipRepo.create({
      identityId: identity.id,
      tenantId: tenant.id,
      role: 'user:trader',
    });
    
    // 6. Send verification email
    await this.emailService.sendVerification(identity, tenant);
    
    // 7. Emit registration event
    await this.eventBus.emit('user.registered', {
      identityId: identity.id,
      tenantId: tenant.id,
      source: 'self_registration',
    });
    
    return { success: true, requiresEmailVerification: true };
  }
}
```

---

## 7. Data Isolation & Security

### 7.1 Data Isolation Layers

```
┌─────────────────────────────────────────────────────────────────┐
│                    DATA ISOLATION LAYERS                          │
│                                                                  │
│  Layer 1: Network Isolation                                      │
│  ├── VPC per environment (prod, staging, dev)                   │
│  ├── Private subnets for databases                               │
│  ├── Network policies (Kubernetes NetworkPolicy / Security Groups)│
│  └── Service mesh (Istio/Linkerd) for mTLS between services     │
│                                                                  │
│  Layer 2: Application Isolation                                  │
│  ├── Tenant context propagation in every request                 │
│  ├── Middleware-enforced tenant_id injection                     │
│  ├── Query interceptors that auto-apply tenant filters           │
│  └── Data validation on write (tenant_id matches context)        │
│                                                                  │
│  Layer 3: Database Isolation                                     │
│  ├── Row-Level Security (RLS) policies in PostgreSQL             │
│  ├── Tenant-scoped connection strings                            │
│  ├── Separate schemas for higher-tier tenants                    │
│  └── Dedicated databases for enterprise tenants                  │
│                                                                  │
│  Layer 4: Encryption                                             │
│  ├── TLS 1.3 in transit (everywhere)                             │
│  ├── AES-256-GCM at rest (database, storage)                    │
│  ├── Per-tenant encryption keys (envelope encryption)            │
│  └── Application-level encryption for PII/sensitive fields       │
│                                                                  │
│  Layer 5: Cache/Queue Isolation                                  │
│  ├── Namespaced Redis keys: tenant:{id}:resource                 │
│  ├── Separate queue topics per tenant for critical paths         │
│  └── Cache invalidation scoped to tenant                        │
└─────────────────────────────────────────────────────────────────┘
```

### 7.2 Row-Level Security (PostgreSQL)

```sql
-- Enable RLS on all tenant-scoped tables
ALTER TABLE trades ENABLE ROW LEVEL SECURITY;
ALTER TABLE trading_accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE payouts ENABLE ROW LEVEL SECURITY;
ALTER TABLE challenges ENABLE ROW LEVEL SECURITY;

-- Create policies
-- Tenant isolation policy
CREATE POLICY tenant_isolation ON trades
  FOR ALL
  USING (tenant_id = current_setting('app.current_tenant_id')::uuid)
  WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::uuid);

-- User-level isolation (traders see only own data)
CREATE POLICY user_own_trades ON trades
  FOR SELECT
  USING (
    tenant_id = current_setting('app.current_tenant_id')::uuid
    AND (
      user_id = current_setting('app.current_user_id')::uuid
      OR current_setting('app.current_user_role') IN ('firm:admin', 'firm:owner', 'firm:risk_manager')
    )
  );

-- Application sets context before every query:
-- SET app.current_tenant_id = 'tenant-uuid';
-- SET app.current_user_id = 'user-uuid';
-- SET app.current_user_role = 'user:trader';
```

### 7.3 Application-Level Field Encryption

```typescript
// Sensitive Field Encryption Service
class FieldEncryptionService {
  
  // Fields that require application-level encryption
  private sensitiveFields = {
    'identities': ['date_of_birth', 'phone', 'government_id'],
    'kyc_documents': ['document_data', 'selfie_data'],
    'payout_details': ['bank_account_number', 'routing_number', 'crypto_wallet'],
    'trading_accounts': ['broker_password', 'investor_password'],
    'api_keys': ['key_hash'],  // already hashed, but encrypted storage
  };
  
  // Envelope Encryption
  async encrypt(tenantId: string, plaintext: string): Promise<EncryptedPayload> {
    // 1. Get or create tenant's Data Encryption Key (DEK)
    const dek = await this.getOrCreateDEK(tenantId);
    
    // 2. Encrypt data with DEK
    const iv = crypto.randomBytes(12);
    const cipher = crypto.createCipheriv('aes-256-gcm', dek.key, iv);
    const encrypted = Buffer.concat([cipher.update(plaintext), cipher.final()]);
    const authTag = cipher.getAuthTag();
    
    return {
      ciphertext: encrypted.toString('base64'),
      iv: iv.toString('base64'),
      authTag: authTag.toString('base64'),
      keyVersion: dek.version,
      tenantId,
    };
  }
  
  // DEK is itself encrypted by Master Key in KMS
  private async getOrCreateDEK(tenantId: string): Promise<DataEncryptionKey> {
    let encryptedDEK = await this.keyStore.get(`dek:${tenantId}`);
    
    if (!encryptedDEK) {
      // Generate new DEK
      const rawDEK = crypto.randomBytes(32);
      
      // Encrypt DEK with Master Key (KMS)
      const encryptedDEKData = await this.kms.encrypt(rawDEK);
      
      await this.keyStore.set(`dek:${tenantId}`, {
        encryptedKey: encryptedDEKData,
        version: 1,
        createdAt: new Date(),
      });
      
      return { key: rawDEK, version: 1 };
    }
    
    // Decrypt DEK with Master Key
    const rawDEK = await this.kms.decrypt(encryptedDEK.encryptedKey);
    return { key: rawDEK, version: encryptedDEK.version };
  }
}
```

### 7.4 Audit Logging

```sql
-- Comprehensive Audit Log Table
CREATE TABLE audit_logs (
    id              BIGSERIAL PRIMARY KEY,
    
    -- Who
    actor_id        UUID,                  -- user who performed action
    actor_type      VARCHAR(20),           -- 'user', 'system', 'api_key'
    actor_ip        INET,
    actor_user_agent TEXT,
    actor_geo       JSONB,
    
    -- What
    action          VARCHAR(100) NOT NULL, -- 'user.login', 'payout.approved'
    resource_type   VARCHAR(50),           -- 'trade', 'payout', 'account'
    resource_id     VARCHAR(255),
    
    -- Context
    tenant_id       UUID,
    
    -- Details
    old_value       JSONB,                 -- before state (for updates)
    new_value       JSONB,                 -- after state
    metadata        JSONB,                 -- additional context
    
    -- Result
    status          VARCHAR(20) NOT NULL,  -- 'success', 'failure', 'denied'
    error_message   TEXT,
    
    -- Timestamp (high precision)
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Immutability
    hash            TEXT NOT NULL           -- SHA-256 chain hash for tamper detection
) PARTITION BY RANGE (created_at);

-- Partition by month for performance
CREATE TABLE audit_logs_2024_01 PARTITION OF audit_logs
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

-- Index for common queries
CREATE INDEX idx_audit_tenant_time ON audit_logs (tenant_id, created_at DESC);
CREATE INDEX idx_audit_actor ON audit_logs (actor_id, created_at DESC);
CREATE INDEX idx_audit_resource ON audit_logs (resource_type, resource_id, created_at DESC);
CREATE INDEX idx_audit_action ON audit_logs (action, created_at DESC);
```

```typescript
// Audit Events for Prop Firm Platform
const auditEvents = {
  // Authentication Events
  'auth.login.success': 'User successfully logged in',
  'auth.login.failure': 'Failed login attempt',
  'auth.login.blocked': 'Login blocked (lockout/geo/suspicious)',
  'auth.logout': 'User logged out',
  'auth.mfa.enabled': 'MFA enabled',
  'auth.mfa.disabled': 'MFA disabled',
  'auth.mfa.verify.success': 'MFA verification successful',
  'auth.mfa.verify.failure': 'MFA verification failed',
  'auth.password.changed': 'Password changed',
  'auth.password.reset.requested': 'Password reset requested',
  'auth.password.reset.completed': 'Password reset completed',
  'auth.session.revoked': 'Session revoked',
  'auth.token.refreshed': 'Token refreshed',
  'auth.api_key.created': 'API key created',
  'auth.api_key.revoked': 'API key revoked',
  'auth.impersonation.start': 'Admin started impersonating user',
  'auth.impersonation.end': 'Admin stopped impersonating user',
  
  // User Management Events
  'user.created': 'User account created',
  'user.updated': 'User profile updated',
  'user.suspended': 'User suspended',
  'user.reactivated': 'User reactivated',
  'user.deleted': 'User account deleted',
  'user.role.changed': 'User role changed',
  'user.invited': 'User invited to tenant',
  'user.invitation.accepted': 'User accepted invitation',
  
  // Trading Events
  'challenge.purchased': 'Challenge purchased',
  'challenge.started': 'Challenge started',
  'challenge.passed': 'Challenge passed',
  'challenge.failed': 'Challenge failed',
  'account.funded': 'Funded account created',
  'account.breached': 'Account rule breach detected',
  'account.suspended': 'Trading account suspended',
  
  // Financial Events
  'payout.requested': 'Payout requested',
  'payout.approved': 'Payout approved',
  'payout.rejected': 'Payout rejected',
  'payout.processed': 'Payout processed',
  'payment.received': 'Payment received',
  'refund.issued': 'Refund issued',
  
  // KYC Events
  'kyc.submitted': 'KYC documents submitted',
  'kyc.approved': 'KYC approved',
  'kyc.rejected': 'KYC rejected',
  
  // Admin Events
  'tenant.settings.changed': 'Tenant settings modified',
  'risk.rule.modified': 'Risk rule modified',
  'risk.override.applied': 'Risk override applied',
  
  // Security Events
  'security.suspicious_activity': 'Suspicious activity detected',
  'security.rate_limit.exceeded': 'Rate limit exceeded',
  'security.data.exported': 'Data export performed',
};
```

---

## 8. Compliance & Regulatory Requirements

### 8.1 Regulatory Landscape

```
┌─────────────────────────────────────────────────────────────────┐
│                REGULATORY REQUIREMENTS                           │
│                                                                  │
│  Financial Regulations:                                          │
│  ├── AML (Anti-Money Laundering) directives                     │
│  ├── KYC (Know Your Customer) requirements                      │
│  ├── PCI DSS (if processing payment cards)                      │
│  ├── SOC 2 Type II (service organization controls)              │
│  └── Regional financial authority requirements                   │
│                                                                  │
│  Data Protection:                                                │
│  ├── GDPR (EU - General Data Protection Regulation)             │
│  │   ├── Right to access (data portability)                     │
│  │   ├── Right to erasure (right to be forgotten)               │
│  │   ├── Data minimization                                       │
│  │   ├── Consent management                                      │
│  │   ├── Breach notification (72 hours)                          │
│  │   └── Data Protection Impact Assessment (DPIA)                │
│  ├── CCPA/CPRA (California)                                     │
│  ├── LGPD (Brazil)                                               │
│  └── Other regional data protection laws                         │
│                                                                  │
│  Security Standards:                                             │
│  ├── ISO 27001 (Information Security Management)                │
│  ├── OWASP Top 10 compliance                                    │
│  ├── NIST Cybersecurity Framework                                │
│  └── CIS Benchmarks for infrastructure                           │
│                                                                  │
│  Industry Standards:                                             │
│  ├── OAuth 2.1 / OpenID Connect                                 │
│  ├── FIDO2/WebAuthn for passwordless                             │
│  ├── SCIM 2.0 for identity provisioning                          │
│  └── SAML 2.0 for enterprise SSO                                │
└─────────────────────────────────────────────────────────────────┘
```

### 8.2 GDPR Compliance Implementation

```typescript
// GDPR Data Subject Rights Implementation
class GDPRComplianceService {
  
  // Right to Access (Data Portability)
  async exportUserData(userId: string, tenantId: string): Promise<DataExport> {
    const data = {
      identity: await this.getIdentityData(userId),
      memberships: await this.getMembershipData(userId, tenantId),
      challenges: await this.getChallengeData(userId, tenantId),
      trades: await this.getTradeHistory(userId, tenantId),
      payouts: await this.getPayoutHistory(userId, tenantId),
      auditLogs: await this.getUserAuditLogs(userId, tenantId),
      consents: await this.getConsentRecords(userId),
    };
    
    // Audit the export
    await this.auditLog('security.data.exported', userId, tenantId);
    
    return {
      format: 'json',
      data,
      exportedAt: new Date(),
      expiresAt: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000), // 7 days
    };
  }
  
  // Right to Erasure (Right to be Forgotten)
  async deleteUserData(userId: string, request: DeletionRequest): Promise<void> {
    // 1. Verify identity (re-authentication required)
    await this.verifyIdentity(userId, request.verification);
    
    // 2. Check for legal holds / retention requirements
    const holds = await this.checkLegalHolds(userId);
    if (holds.length > 0) {
      throw new Error('Cannot delete: legal hold in place');
    }
    
    // 3. Check financial obligations (pending payouts, etc.)
    const obligations = await this.checkFinancialObligations(userId);
    if (obligations.pending) {
      throw new Error('Cannot delete: pending financial obligations');
    }
    
    // 4. Schedule deletion (30-day grace period)
    await this.scheduleDeletion(userId, {
      scheduledFor: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000),
      requestedAt: new Date(),
      requestedBy: userId,
    });
    
    // 5. Immediate actions
    await this.revokeAllSessions(userId);
    await this.anonymizePublicReferences(userId);
    
    // 6. After grace period (automated job)
    // - Anonymize identity data
    // - Delete PII
    // - Retain anonymized financial records (regulatory requirement)
    // - Delete KYC documents
    // - Remove from all caches
  }
  
  // Consent Management
  async recordConsent(userId: string, consent: ConsentRecord): Promise<void> {
    await this.consentStore.save({
      userId,
      purpose: consent.purpose,      // 'marketing', 'analytics', 'kyc_processing'
      granted: consent.granted,
      timestamp: new Date(),
      ipAddress: consent.ipAddress,
      userAgent: consent.userAgent,
      version: consent.policyVersion,
    });
  }
}
```

---

## 9. Technical Architecture & Implementation

### 9.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         CLIENTS                                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐               │
│  │ Web App  │  │ Admin    │  │ Mobile   │  │ Trading  │               │
│  │ (React)  │  │ Dashboard│  │ App      │  │ Bots/API │               │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘               │
│       │              │              │              │                     │
└───────┼──────────────┼──────────────┼──────────────┼─────────────────────┘
        │              │              │              │
        ▼              ▼              ▼              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     EDGE / API GATEWAY LAYER                            │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  CDN (CloudFlare / AWS CloudFront)                                │  │
│  │  ├── DDoS Protection                                              │  │
│  │  ├── WAF Rules                                                    │  │
│  │  ├── Bot Detection                                                │  │
│  │  └── SSL Termination                                              │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  API Gateway (Kong / AWS API Gateway / Custom)                    │  │
│  │  ├── Rate Limiting (per tenant tier)                              │  │
│  │  ├── Request Validation                                           │  │
│  │  ├── Tenant Resolution                                            │  │
│  │  ├── Authentication Token Validation                              │  │
│  │  └── Request Routing                                              │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     SERVICE LAYER (Microservices)                        │
│                                                                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │
│  │   Auth      │  │   Identity  │  │   Tenant    │  │Authorization│  │
│  │   Service   │  │   Service   │  │   Service   │  │   Service   │  │
│  │             │  │             │  │             │  │             │  │
│  │ • Login     │  │ • CRUD      │  │ • CRUD      │  │ • Policy    │  │
│  │ • MFA       │  │ • KYC       │  │ • Config    │  │   Engine    │  │
│  │ • Tokens    │  │ • Profile   │  │ • Billing   │  │ • RBAC/ABAC │  │
│  │ • Sessions  │  │ • Federation│  │ • Branding  │  │ • Audit     │  │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  │
│         │                │                │                │          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │
│  │  Challenge  │  │   Trading   │  │   Payout    │  │  Risk       │  │
│  │  Service    │  │   Service   │  │   Service   │  │  Engine     │  │
│  │             │  │             │  │             │  │             │  │
│  │ • CRUD      │  │ • Account   │  │ • Request   │  │ • Rules     │  │
│  │ • Purchase  │  │   Mgmt      │  │ • Approval  │  │ • Monitor   │  │
│  │ • Progress  │  │ • Trade     │  │ • Processing│  │ • Alerts    │  │
│  │ • Eval      │  │   History   │  │ • Ledger    │  │ • Breach    │  │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  │
│         │                │                │                │          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │
│  │  Affiliate  │  │Notification │  │   Webhook   │  │  Analytics  │  │
│  │  Service    │  │   Service   │  │   Service   │  │   Service   │  │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     DATA LAYER                                           │
│                                                                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │
│  │ PostgreSQL  │  │   Redis     │  │  MongoDB    │  │ TimescaleDB │  │
│  │ (Primary)   │  │ (Cache/     │  │ (Documents/ │  │ (Time-series│  │
│  │             │  │  Sessions)  │  │  Audit Logs)│  │  Trade Data)│  │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘  │
│                                                                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                    │
│  │ S3/Blob     │  │  Kafka/     │  │ Vault       │                    │
│  │ Storage     │  │  NATS       │  │ (Secrets)   │                    │
│  │ (Documents) │  │ (Events)    │  │             │                    │
│  └─────────────┘  └─────────────┘  └─────────────┘                    │
└─────────────────────────────────────────────────────────────────────────┘
```

### 9.2 Auth Service Implementation

```typescript
// Auth Service - Core Module Structure
// /services/auth/
// ├── src/
// │   ├── controllers/
// │   │   ├── auth.controller.ts
// │   │   ├── mfa.controller.ts
// │   │   ├── session.controller.ts
// │   │   ├── oauth.controller.ts
// │   │   └── api-key.controller.ts
// │   ├── services/
// │   │   ├── authentication.service.ts
// │   │   ├── token.service.ts
// │   │   ├── session.service.ts
// │   │   ├── mfa.service.ts
// │   │   ├── password.service.ts
// │   │   ├── oauth.service.ts
// │   │   └── device-fingerprint.service.ts
// │   ├── guards/
// │   │   ├── auth.guard.ts
// │   │   ├── mfa.guard.ts
// │   │   ├── rate-limit.guard.ts
// │   │   └── tenant.guard.ts
// │   ├── strategies/
// │   │   ├── jwt.strategy.ts
// │   │   ├── local.strategy.ts
// │   │   ├── google-oauth.strategy.ts
// │   │   └── saml.strategy.ts
// │   ├── events/
// │   │   ├── auth-events.ts
// │   │   └── event-handlers/
// │   ├── middlewares/
// │   │   ├── tenant-context.middleware.ts
// │   │   └── security-headers.middleware.ts
// │   └── utils/
// │       ├── crypto.util.ts
// │       └── validation.util.ts

// Token Service Implementation
class TokenService {
  private readonly accessTokenTTL = 900;     // 15 minutes
  private readonly refreshTokenTTL = 604800; // 7 days
  
  async generateTokenPair(
    user: User,
    tenant: Tenant,
    session: Session,
  ): Promise<TokenPair> {
    const jti = uuidv4();
    
    // Access Token
    const accessToken = await this.jwtService.signAsync(
      {
        sub: user.id,
        tenant_id: tenant.id,
        tenant_slug: tenant.slug,
        org_role: user.membership.role,
        permissions: await this.getEffectivePermissions(user, tenant),
        sid: session.id,
        device_id: session.deviceFingerprint,
        amr: session.authMethods,
        auth_time: Math.floor(session.createdAt.getTime() / 1000),
      },
      {
        algorithm: 'RS256',
        expiresIn: this.accessTokenTTL,
        issuer: this.config.issuer,
        audience: this.config.audience,
        jwtid: jti,
        keyid: await this.getActiveKeyId(),
      },
    );
    
    // Refresh Token (opaque, stored in DB)
    const refreshToken = crypto.randomBytes(64).toString('base64url');
    const refreshTokenHash = this.hashToken(refreshToken);
    
    await this.sessionRepo.updateRefreshToken(session.id, {
      refreshTokenHash,
      accessTokenJti: jti,
      expiresAt: new Date(Date.now() + this.refreshTokenTTL * 1000),
    });
    
    return {
      accessToken,
      refreshToken,
      tokenType: 'Bearer',
      expiresIn: this.accessTokenTTL,
    };
  }
  
  async refreshTokens(
    refreshToken: string,
    deviceFingerprint: string,
  ): Promise<TokenPair> {
    const tokenHash = this.hashToken(refreshToken);
    
    // Find session by refresh token hash
    const session = await this.sessionRepo.findByRefreshToken(tokenHash);
    
    if (!session) {
      // Possible token reuse attack - revoke all sessions for this user
      await this.detectTokenReuse(tokenHash);
      throw new UnauthorizedError('Invalid refresh token');
    }
    
    // Validate session
    if (session.revokedAt || session.expiresAt < new Date()) {
      throw new UnauthorizedError('Session expired');
    }
    
    // Validate device binding
    if (session.deviceFingerprint !== deviceFingerprint) {
      await this.flagSuspiciousActivity(session, 'device_mismatch');
      throw new UnauthorizedError('Device mismatch');
    }
    
    // Rotate refresh token (one-time use)
    const user = await this.userRepo.findById(session.userId);
    const tenant = await this.tenantRepo.findById(session.tenantId);
    
    // Invalidate old refresh token
    await this.sessionRepo.invalidateRefreshToken(session.id);
    
    // Generate new token pair
    return this.generateTokenPair(user, tenant, session);
  }
  
  private async detectTokenReuse(tokenHash: string): Promise<void> {
    // Check if this is a previously used refresh token
    const previousSession = await this.sessionRepo.findByPreviousRefreshToken(tokenHash);
    
    if (previousSession) {
      // Token reuse detected! Revoke all sessions for this user
      await this.sessionRepo.revokeAllUserSessions(
        previousSession.userId,
        'TOKEN_REUSE_DETECTED',
      );
      
      // Alert security team
      await this.securityAlertService.alert({
        type: 'TOKEN_REUSE_ATTACK',
        userId: previousSession.userId,
        tenantId: previousSession.tenantId,
        severity: 'CRITICAL',
      });
    }
  }
}
```

### 9.3 Middleware Pipeline

```typescript
// Request Processing Pipeline (ordered)
const middlewarePipeline = [
  // 1. Security Headers
  SecurityHeadersMiddleware,      // HSTS, CSP, X-Frame-Options, etc.
  
  // 2. Request ID & Correlation
  RequestIdMiddleware,            // X-Request-ID for tracing
  
  // 3. Rate Limiting (pre-auth)
  GlobalRateLimitMiddleware,      // IP-based rate limiting
  
  // 4. CORS
  CorsMiddleware,                 // tenant-specific CORS config
  
  // 5. Tenant Resolution
  TenantResolutionMiddleware,     // Resolve tenant from domain/header/token
  
  // 6. Authentication
  AuthenticationMiddleware,       // Validate JWT, resolve user
  
  // 7. Session Validation
  SessionValidationMiddleware,    // Check session is active, not expired
  
  // 8. Tenant-Scoped Rate Limiting
  TenantRateLimitMiddleware,      // Per-tenant, per-user rate limits
  
  // 9. Authorization
  AuthorizationMiddleware,        // Check permissions for route
  
  // 10. Request Validation
  RequestValidationMiddleware,    // Schema validation (Zod/Joi)
  
  // 11. Tenant Context Injection
  TenantContextMiddleware,        // Set DB connection, cache namespace
  
  // 12. Audit Pre-processing
  AuditMiddleware,                // Capture request for audit trail
  
  // → Route Handler
  
  // 13. Response Transformation
  ResponseTransformMiddleware,    // Sanitize, format response
  
  // 14. Audit Post-processing
  AuditResponseMiddleware,        // Log response status, capture changes
];
```

### 9.4 Database Connection Management

```typescript
// Multi-Tenant Database Connection Manager
class TenantDatabaseManager {
  private connectionPools: Map<string, Pool> = new Map();
  
  async getConnection(tenantContext: TenantContext): Promise<PoolClient> {
    const { tenantId, isolationLevel } = tenantContext;
    
    switch (isolationLevel) {
      case 'dedicated': {
        // Tenant has their own database
        const pool = await this.getDedicatedPool(tenantId);
        return pool.connect();
      }
      
      case 'schema': {
        // Tenant has their own schema in shared DB
        const client = await this.sharedPool.connect();
        await client.query(`SET search_path TO tenant_${tenantId}, public`);
        return client;
      }
      
      case 'shared': {
        // Shared schema with RLS
        const client = await this.sharedPool.connect();
        await client.query(`SET app.current_tenant_id = '${tenantId}'`);
        return client;
      }
      
      default:
        throw new Error(`Unknown isolation level: ${isolationLevel}`);
    }
  }
  
  private async getDedicatedPool(tenantId: string): Promise<Pool> {
    if (!this.connectionPools.has(tenantId)) {
      const config = await this.getTenantDBConfig(tenantId);
      const pool = new Pool({
        host: config.host,
        port: config.port,
        database: config.database,
        user: config.user,
        password: await this.vault.getSecret(`db-password-${tenantId}`),
        max: 20,
        idleTimeoutMillis: 30000,
        connectionTimeoutMillis: 2000,
        ssl: { rejectUnauthorized: true },
      });
      this.connectionPools.set(tenantId, pool);
    }
    return this.connectionPools.get(tenantId)!;
  }
}
```

---

## 10. Infrastructure & DevOps

### 10.1 Deployment Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    KUBERNETES CLUSTER                             │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Namespace: auth-system                                   │    │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐   │    │
│  │  │Auth Svc  │ │Identity  │ │Authz Svc │ │Session   │   │    │
│  │  │(3 pods)  │ │Svc(2pods)│ │(2 pods)  │ │Svc(2pods)│   │    │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘   │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Namespace: platform-services                             │    │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐   │    │
│  │  │Tenant Svc│ │Challenge │ │Trading   │ │Risk Eng  │   │    │
│  │  │(2 pods)  │ │Svc(3pods)│ │Svc(3pods)│ │(3 pods)  │   │    │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘   │    │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐   │    │
│  │  │Payout Svc│ │Affiliate │ │Notif Svc │ │Webhook   │   │    │
│  │  │(2 pods)  │ │Svc(2pods)│ │(2 pods)  │ │Svc(2pods)│   │    │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘   │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Namespace: data-plane                                    │    │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐   │    │
│  │  │PostgreSQL│ │PostgreSQL│ │Redis     │ │Redis     │   │    │
│  │  │Primary   │ │Replica   │ │Cluster   │ │Sentinel  │   │    │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘   │    │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐                │    │
│  │  │Kafka     │ │NATS      │ │Vault     │                │    │
│  │  │Cluster   │ │Cluster   │ │(HA)      │                │    │
│  │  └──────────┘ └──────────┘ └──────────┘                │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Namespace: observability                                 │    │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐   │    │
│  │  │Prometheus│ │Grafana   │ │Jaeger    │ │ELK/Loki  │   │    │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘   │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

### 10.2 Network Security

```yaml
# Kubernetes NetworkPolicy - Auth Service
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: auth-service-network-policy
  namespace: auth-system
spec:
  podSelector:
    matchLabels:
      app: auth-service
  policyTypes:
    - Ingress
    - Egress
  ingress:
    # Only allow traffic from API gateway
    - from:
        - namespaceSelector:
            matchLabels:
              name: api-gateway
      ports:
        - protocol: TCP
          port: 3000
  egress:
    # Allow access to PostgreSQL
    - to:
        - namespaceSelector:
            matchLabels:
              name: data-plane
        - podSelector:
            matchLabels:
              app: postgresql
      ports:
        - protocol: TCP
          port: 5432
    # Allow access to Redis
    - to:
        - podSelector:
            matchLabels:
              app: redis
      ports:
        - protocol: TCP
          port: 6379
    # Allow access to Vault
    - to:
        - podSelector:
            matchLabels:
              app: vault
      ports:
        - protocol: TCP
          port: 8200
    # Allow DNS
    - to: []
      ports:
        - protocol: UDP
          port: 53
```

### 10.3 Secret Management

```typescript
// HashiCorp Vault Integration
class VaultSecretManager {
  
  // Secret paths structure
  private paths = {
    // Database credentials
    dbCredentials: (tenantId: string) => 
      `secret/data/tenants/${tenantId}/database`,
    
    // JWT signing keys
    jwtSigningKeys: 'secret/data/auth/jwt-keys',
    
    // Encryption keys (DEKs)
    encryptionKeys: (tenantId: string) => 
      `secret/data/tenants/${tenantId}/encryption`,
    
    // Third-party API keys
    brokerCredentials: (tenantId: string) => 
      `secret/data/tenants/${tenantId}/broker`,
    
    // KYC provider credentials
    kycProviderKeys: 'secret/data/integrations/kyc',
    
    // Payment processor credentials
    paymentKeys: (tenantId: string) => 
      `secret/data/tenants/${tenantId}/payment`,
  };
  
  // Dynamic database credentials (auto-rotating)
  async getDatabaseCredentials(tenantId: string): Promise<DBCredentials> {
    const response = await this.vault.read(
      `database/creds/tenant-${tenantId}-role`
    );
    return {
      username: response.data.username,
      password: response.data.password,
      ttl: response.lease_duration,
      leaseId: response.lease_id,
    };
  }
}
```

---

## 11. Scaling Considerations

### 11.1 Performance Targets

```
┌─────────────────────────────────────────────────────────────────┐
│                    PERFORMANCE TARGETS                            │
│                                                                  │
│  Authentication:                                                 │
│  ├── Login latency: < 300ms (p99)                               │
│  ├── Token validation: < 5ms (p99, cached)                     │
│  ├── Token refresh: < 100ms (p99)                               │
│  └── Throughput: 10,000 auth requests/second                    │
│                                                                  │
│  Authorization:                                                  │
│  ├── Policy evaluation: < 10ms (p99)                            │
│  ├── Permission check: < 2ms (p99, cached)                     │
│  └── Throughput: 50,000 authz decisions/second                  │
│                                                                  │
│  Tenant Resolution:                                              │
│  ├── Resolution time: < 5ms (p99, cached)                      │
│  └── Cache hit ratio: > 99%                                    │
│                                                                  │
│  Data Access:                                                    │
│  ├── Read latency: < 50ms (p99)                                │
│  ├── Write latency: < 100ms (p99)                              │
│  └── Query with RLS overhead: < 10% additional latency          │
│                                                                  │
│  Scale Targets:                                                  │
│  ├── Tenants: 1,000+ active prop firms                         │
│  ├── Users: 1,000,000+ traders across all tenants              │
│  ├── Concurrent sessions: 100,000+                              │
│  └── Daily transactions: 10,000,000+ trade records              │
└─────────────────────────────────────────────────────────────────┘
```

### 11.2 Caching Strategy

```typescript
// Multi-Layer Caching Architecture
class CacheStrategy {
  
  // Layer 1: In-memory (per-instance, LRU)
  private localCache = new LRUCache<string, any>({
    max: 10000,
    ttl: 60 * 1000,  // 1 minute
  });
  
  // Layer 2: Distributed (Redis)
  private redis: RedisCluster;
  
  // Cache warming for critical paths
  async warmTenantCache(tenantId: string): Promise<void> {
    const tenant = await this.tenantRepo.findById(tenantId);
    const config = await this.tenantRepo.getConfig(tenantId);
    const featureFlags = await this.featureFlagRepo.getForTenant(tenantId);
    
    await this.redis.pipeline()
      .set(`tenant:${tenantId}:info`, JSON.stringify(tenant), 'EX', 3600)
      .set(`tenant:${tenantId}:config`, JSON.stringify(config), 'EX', 3600)
      .set(`tenant:${tenantId}:features`, JSON.stringify(featureFlags), 'EX', 300)
      .exec();
  }
  
  // JWKS caching (for token validation)
  async getJWKS(): Promise<JWKS> {
    const cached = this.localCache.get('jwks');
    if (cached) return cached;
    
    const jwks = await this.redis.get('auth:jwks');
    if (jwks) {
      const parsed = JSON.parse(jwks);
      this.localCache.set('jwks', parsed);
      return parsed;
    }
    
    const freshJWKS = await this.keyService.getPublicKeys();
    await this.redis.set('auth:jwks', JSON.stringify(freshJWKS), 'EX', 3600);
    this.localCache.set('jwks', freshJWKS);
    return freshJWKS;
  }
  
  // Permission cache with smart invalidation
  async getUserPermissions(userId: string, tenantId: string): Promise<string[]> {
    const cacheKey = `authz:${tenantId}:${userId}:permissions`;
    
    // Check local cache first
    let permissions = this.localCache.get(cacheKey);
    if (permissions) return permissions;
    
    // Check Redis
    const cached = await this.redis.get(cacheKey);
    if (cached) {
      permissions = JSON.parse(cached);
      this.localCache.set(cacheKey, permissions);
      return permissions;
    }
    
    // Compute and cache
    permissions = await this.authzService.computeEffectivePermissions(userId, tenantId);
    await this.redis.set(cacheKey, JSON.stringify(permissions), 'EX', 300);
    this.localCache.set(cacheKey, permissions);
    
    return permissions;
  }
  
  // Cache invalidation on role/permission change
  async invalidateUserAuthz(userId: string, tenantId: string): Promise<void> {
    const pattern = `authz:${tenantId}:${userId}:*`;
    
    // Invalidate Redis
    const keys = await this.redis.keys(pattern);
    if (keys.length > 0) {
      await this.redis.del(...keys);
    }
    
    // Broadcast invalidation to all instances (pub/sub)
    await this.redis.publish('cache:invalidate', JSON.stringify({
      pattern,
      timestamp: Date.now(),
    }));
  }
}
```

### 11.3 Rate Limiting Strategy

```typescript
// Multi-Tier Rate Limiting
interface RateLimitConfig {
  // Global (per IP)
  global: {
    windowMs: 60000,       // 1 minute
    maxRequests: 1000,
  };
  
  // Per Tenant Tier
  tenantTiers: {
    starter: {
      requestsPerMinute: 1000,
      requestsPerDay: 100000,
      concurrentConnections: 100,
    },
    standard: {
      requestsPerMinute: 5000,
      requestsPerDay: 500000,
      concurrentConnections: 500,
    },
    enterprise: {
      requestsPerMinute: 20000,
      requestsPerDay: 2000000,
      concurrentConnections: 2000,
    },
  };
  
  // Per Endpoint (sensitive endpoints)
  endpoints: {
    'POST /auth/login': { windowMs: 300000, max: 10 },        // 10 per 5 min
    'POST /auth/password/reset': { windowMs: 3600000, max: 3 }, // 3 per hour
    'POST /auth/mfa/verify': { windowMs: 300000, max: 5 },     // 5 per 5 min
    'POST /payouts/request': { windowMs: 3600000, max: 5 },    // 5 per hour
    'POST /api-keys': { windowMs: 86400000, max: 10 },          // 10 per day
  };
  
  // Per User
  perUser: {
    requestsPerMinute: 100,
    requestsPerHour: 3000,
  };
}

// Implementation using Redis sliding window
class SlidingWindowRateLimiter {
  async isAllowed(key: string, limit: number, windowMs: number): Promise<RateLimitResult> {
    const now = Date.now();
    const windowStart = now - windowMs;
    
    const result = await this.redis
      .multi()
      .zremrangebyscore(key, 0, windowStart)     // Remove old entries
      .zadd(key, now, `${now}:${uuidv4()}`)      // Add current request
      .zcard(key)                                   // Count entries
      .pexpire(key, windowMs)                       // Set expiry
      .exec();
    
    const requestCount = result[2][1] as number;
    const allowed = requestCount <= limit;
    
    return {
      allowed,
      remaining: Math.max(0, limit - requestCount),
      resetAt: new Date(now + windowMs),
      retryAfter: allowed ? 0 : Math.ceil(windowMs / 1000),
    };
  }
}
```

---

## 12. Technology Stack Recommendations

### 12.1 Build vs. Buy Decision Matrix

| Component | Build | Buy/Use Managed | Recommendation |
|-----------|-------|-----------------|----------------|
| **Identity Provider** | Custom | Auth0, Clerk, Keycloak, FusionAuth | **Hybrid**: Keycloak/FusionAuth (self-hosted) or Auth0 (managed) + custom extensions |
| **Authorization Engine** | Custom | OPA, Cedar, Cerbos, SpiceDB | **Cerbos or OPA** for policy engine + custom RBAC layer |
| **Multi-tenant DB** | Custom | Nile, Citus | **Custom** with PostgreSQL + RLS |
| **Secret Management** | ❌ | HashiCorp Vault, AWS Secrets Manager | **Vault** (self-hosted) or cloud-native |
| **API Gateway** | ❌ | Kong, Traefik, AWS API Gateway | **Kong** (open-source) or cloud-native |
| **Session Store** | Custom | Redis | **Redis Cluster** |
| **Event Streaming** | ❌ | Kafka, NATS, AWS EventBridge | **NATS JetStream** or **Kafka** |
| **Monitoring** | ❌ | Datadog, Grafana Cloud | **Grafana stack** (self-hosted) or **Datadog** |

### 12.2 Recommended Tech Stack

```
┌─────────────────────────────────────────────────────────────────┐
│                  RECOMMENDED TECHNOLOGY STACK                     │
│                                                                  │
│  Runtime & Framework:                                            │
│  ├── Node.js 20+ / Bun (primary services)                       │
│  ├── NestJS (structured, enterprise-grade framework)             │
│  ├── Go (for high-performance services: auth, risk engine)       │
│  └── TypeScript everywhere (full-stack type safety)              │
│                                                                  │
│  Authentication:                                                 │
│  ├── Option A: Keycloak (self-hosted, full-featured)             │
│  │   ├── Built-in OIDC/SAML/Social login                       │
│  │   ├── Themeable login pages per tenant                       │
│  │   ├── Admin API for tenant provisioning                      │
│  │   └── Custom SPI for prop firm specific logic                │
│  │                                                              │
│  ├── Option B: Custom Auth Service                               │
│  │   ├── Full control over user experience                      │
│  │   ├── jose (JWT library)                                     │
│  │   ├── @simplewebauthn/server (passkeys)                      │
│  │   ├── otpauth (TOTP)                                         │
│  │   └── argon2 (password hashing)                              │
│  │                                                              │
│  └── Option C: Auth0/Clerk (managed)                             │
│      ├── Organizations feature for multi-tenancy                 │
│      ├── Actions/Rules for custom logic                         │
│      ├── Fastest time to market                                 │
│      └── Higher long-term cost                                  │
│                                                                  │
│  Authorization:                                                  │
│  ├── Cerbos (policy engine, self-hosted)                        │
│  │   ├── YAML/JSON policy definitions                           │
│  │   ├── Built-in RBAC + ABAC                                  │
│  │   ├── Tenant-scoped policies                                 │
│  │   └── Playground for testing                                 │
│  │                                                              │
│  ├── Alternative: Open Policy Agent (OPA)                        │
│  │   ├── Rego policy language                                   │
│  │   ├── Sidecar deployment model                               │
│  │   └── More flexible but steeper learning curve               │
│  │                                                              │
│  └── Alternative: SpiceDB (Zanzibar-based ReBAC)                │
│      ├── Google Zanzibar implementation                         │
│      ├── Relationship-based access control                      │
│      └── Best for complex hierarchical permissions              │
│                                                                  │
│  Database:                                                       │
│  ├── PostgreSQL 16+ (primary datastore)                         │
│  │   ├── Row-Level Security                                     │
│  │   ├── Partitioning (audit logs, trades)                     │
│  │   └── pgcrypto for DB-level encryption                      │
│  ├── Redis 7+ Cluster (cache, sessions, rate limiting)          │
│  ├── TimescaleDB (time-series trade data)                       │
│  └── S3-compatible storage (documents, KYC files)               │
│                                                                  │
│  ORM/Query Builder:                                              │
│  ├── Prisma (primary - type-safe, migrations)                   │
│  ├── Drizzle ORM (alternative - lighter weight)                 │
│  └── Knex.js (for complex multi-tenant queries)                 │
│                                                                  │
│  Messaging/Events:                                               │
│  ├── NATS JetStream (lightweight, high-performance)             │
│  ├── or Apache Kafka (for larger scale)                         │
│  └── Bull/BullMQ (job queues on Redis)                          │
│                                                                  │
│  Infrastructure:                                                 │
│  ├── Kubernetes (EKS/GKE/AKS)                                  │
│  ├── Terraform (IaC)                                            │
│  ├── ArgoCD (GitOps deployments)                                │
│  ├── Istio/Linkerd (service mesh)                               │
│  └── Cert-manager (TLS certificates)                            │
│                                                                  │
│  Observability:                                                  │
│  ├── OpenTelemetry (instrumentation)                            │
│  ├── Prometheus + Grafana (metrics)                             │
│  ├── Loki (logs)                                                │
│  ├── Jaeger/Tempo (distributed tracing)                         │
│  └── PagerDuty/OpsGenie (alerting)                              │
│                                                                  │
│  Security:                                                       │
│  ├── HashiCorp Vault (secrets management)                       │
│  ├── Trivy (container scanning)                                 │
│  ├── Snyk (dependency scanning)                                 │
│  ├── OWASP ZAP (DAST)                                          │
│  └── SonarQube (SAST)                                           │
└─────────────────────────────────────────────────────────────────┘
```

### 12.3 Option Comparison: Auth Provider

```
┌──────────────────┬──────────────────┬──────────────────┬──────────────────┐
│   Criteria       │   Keycloak       │   Custom Built   │   Auth0          │
│                  │   (Self-hosted)  │   (NestJS)       │   (Managed)      │
├──────────────────┼──────────────────┼──────────────────┼──────────────────┤
│ Multi-tenancy    │ Realms (native)  │ Full control     │ Organizations    │
│ Customization    │ Themes + SPIs    │ Unlimited        │ Actions/Rules    │
│ OIDC/SAML        │ ✅ Native        │ Manual impl      │ ✅ Native        │
│ Social Login     │ ✅ Built-in      │ Passport.js      │ ✅ Built-in      │
│ MFA              │ ✅ Built-in      │ Manual impl      │ ✅ Built-in      │
│ Passkeys         │ ✅ (v24+)        │ SimpleWebAuthn   │ ✅ Built-in      │
│ Branding/tenant  │ Per-realm themes │ Full control     │ Universal Login  │
│ Admin API        │ ✅ Comprehensive │ Full control     │ ✅ Management API│
│ Performance      │ Good (Java)      │ Excellent        │ Good             │
│ Cost (100K MAU)  │ Infra only       │ Dev + Infra      │ $2,300+/month    │
│ Cost (1M MAU)    │ Infra only       │ Dev + Infra      │ $15,000+/month   │
│ Time to market   │ 2-4 weeks        │ 8-16 weeks       │ 1-2 weeks        │
│ Vendor lock-in   │ Low              │ None             │ High             │
│ Compliance       │ FIPS/SOC2 ready  │ Self-managed     │ SOC2/GDPR ready  │
│ Maintenance      │ Medium           │ High             │ None             │
├──────────────────┼──────────────────┼──────────────────┼──────────────────┤
│ RECOMMENDATION   │ ★ Best for       │ Best for max     │ Best for rapid   │
│                  │   balance of     │ control &        │ MVP & teams      │
│                  │   features/cost  │ performance      │ without auth     │
│                  │                  │                  │ expertise        │
└──────────────────┴──────────────────┴──────────────────┴──────────────────┘
```

---

## 13. Threat Modeling & Security Hardening

### 13.1 STRIDE Threat Analysis

```
┌─────────────────────────────────────────────────────────────────┐
│                    STRIDE THREAT MODEL                           │
│                                                                  │
│  S - Spoofing Identity                                          │
│  ├── Threat: Attacker impersonates trader/admin                 │
│  ├── Mitigation: Strong auth, MFA, session binding              │
│  ├── Threat: Token theft/replay                                 │
│  └── Mitigation: Short-lived tokens, rotation, device binding   │
│                                                                  │
│  T - Tampering with Data                                        │
│  ├── Threat: Modifying trade records                            │
│  ├── Mitigation: Immutable audit logs, hash chains              │
│  ├── Threat: Manipulating payout amounts                        │
│  └── Mitigation: Dual approval, segregation of duties           │
│                                                                  │
│  R - Repudiation                                                │
│  ├── Threat: User denies performing action                      │
│  └── Mitigation: Comprehensive audit logging, digital signatures│
│                                                                  │
│  I - Information Disclosure                                      │
│  ├── Threat: Cross-tenant data leakage                          │
│  ├── Mitigation: RLS, encryption, strict isolation              │
│  ├── Threat: PII exposure in logs/errors                        │
│  └── Mitigation: Log sanitization, error masking                │
│                                                                  │
│  D - Denial of Service                                          │
│  ├── Threat: Auth service overwhelmed                           │
│  ├── Mitigation: Rate limiting, DDoS protection, scaling        │
│  ├── Threat: Account lockout attacks                            │
│  └── Mitigation: CAPTCHA, progressive delays, IP reputation     │
│                                                                  │
│  E - Elevation of Privilege                                      │
│  ├── Threat: Trader gains admin access                          │
│  ├── Mitigation: Strict RBAC, policy engine, least privilege    │
│  ├── Threat: Cross-tenant privilege escalation                  │
│  └── Mitigation: Tenant isolation at every layer                │
└─────────────────────────────────────────────────────────────────┘
```

### 13.2 Prop-Firm Specific Threats

```
┌─────────────────────────────────────────────────────────────────┐
│              PROP FIRM SPECIFIC THREATS                           │
│                                                                  │
│  1. Account Sharing / Identity Fraud                             │
│  ├── Traders sharing funded accounts                            │
│  ├── Using someone else's identity for KYC                      │
│  └── Mitigations:                                                │
│      ├── Device fingerprinting                                   │
│      ├── IP pattern analysis                                     │
│      ├── Trading pattern ML analysis                             │
│      ├── Periodic re-verification                                │
│      └── Session concurrency limits per account                  │
│                                                                  │
│  2. Insider Threats (Firm Staff)                                 │
│  ├── Admin modifying trader results                              │
│  ├── Finance staff manipulating payouts                         │
│  └── Mitigations:                                                │
│      ├── Dual authorization for sensitive operations             │
│      ├── Immutable audit trail                                   │
│      ├── Segregation of duties                                   │
│      ├── Admin action alerts                                     │
│      └── Regular access reviews                                  │
│                                                                  │
│  3. Tenant Compromise                                            │
│  ├── Compromised tenant admin affecting other tenants            │
│  ├── Malicious tenant attempting data extraction                 │
│  └── Mitigations:                                                │
│      ├── Strict tenant isolation (RLS, encryption)               │
│      ├── Tenant-scoped API keys                                  │
│      ├── Resource quotas per tenant                              │
│      └── Anomaly detection                                       │
│                                                                  │
│  4. Trading Platform Integration Risks                           │
│  ├── MT4/MT5 credential exposure                                │
│  ├── Broker API key compromise                                  │
│  └── Mitigations:                                                │
│      ├── Vault storage for all credentials                       │
│      ├── Proxy-based broker communication                       │
│      ├── Credential rotation automation                          │
│      └── Least-privilege broker API access                       │
│                                                                  │
│  5. Payment Fraud                                                │
│  ├── Unauthorized payout requests                               │
│  ├── Payout destination manipulation                             │
│  └── Mitigations:                                                │
│      ├── MFA required for all payout operations                  │
│      ├── Cooling period for new payout methods                   │
│      ├── Velocity checks                                         │
│      ├── Manual review thresholds                                │
│      └── Payout address verification                             │
└─────────────────────────────────────────────────────────────────┘
```

### 13.3 Security Headers & Configuration

```typescript
// Security Headers Middleware
const securityHeaders = {
  'Strict-Transport-Security': 'max-age=63072000; includeSubDomains; preload',
  'X-Content-Type-Options': 'nosniff',
  'X-Frame-Options': 'DENY',
  'X-XSS-Protection': '0', // Modern browsers - rely on CSP instead
  'Referrer-Policy': 'strict-origin-when-cross-origin',
  'Permissions-Policy': 'camera=(), microphone=(), geolocation=()',
  'Content-Security-Policy': [
    "default-src 'self'",
    "script-src 'self' 'nonce-{NONCE}'",
    "style-src 'self' 'unsafe-inline'", // May need unsafe-inline for CSS
    "img-src 'self' data: https:",
    "font-src 'self'",
    "connect-src 'self' https://*.platform.com wss://*.platform.com",
    "frame-ancestors 'none'",
    "base-uri 'self'",
    "form-action 'self'",
  ].join('; '),
  'Cross-Origin-Opener-Policy': 'same-origin',
  'Cross-Origin-Resource-Policy': 'same-origin',
  'Cross-Origin-Embedder-Policy': 'require-corp',
};

// Cookie Configuration
const cookieConfig = {
  refreshToken: {
    httpOnly: true,
    secure: true,           // HTTPS only
    sameSite: 'strict',     // CSRF protection
    path: '/api/auth',      // Restrict to auth endpoints
    domain: '.platform.com',
    maxAge: 7 * 24 * 60 * 60 * 1000, // 7 days
  },
  sessionId: {
    httpOnly: true,
    secure: true,
    sameSite: 'lax',
    path: '/',
    domain: '.platform.com',
    maxAge: 24 * 60 * 60 * 1000, // 24 hours
  },
};
```

### 13.4 Anomaly Detection

```typescript
// Login Anomaly Detection Service
class LoginAnomalyDetector {
  
  async analyzeLoginAttempt(attempt: LoginAttempt): Promise<RiskAssessment> {
    const scores: RiskFactor[] = [];
    
    // 1. New device detection
    const knownDevices = await this.getKnownDevices(attempt.userId);
    if (!knownDevices.includes(attempt.deviceFingerprint)) {
      scores.push({ factor: 'new_device', score: 30, detail: 'Unknown device' });
    }
    
    // 2. New location
    const knownLocations = await this.getKnownLocations(attempt.userId);
    const geoDistance = this.calculateGeoDistance(
      attempt.geoLocation, 
      knownLocations
    );
    if (geoDistance > 500) { // > 500km from known locations
      scores.push({ factor: 'new_location', score: 25, detail: `${geoDistance}km from known location` });
    }
    
    // 3. Impossible travel
    const lastLogin = await this.getLastLogin(attempt.userId);
    if (lastLogin) {
      const timeDiff = attempt.timestamp - lastLogin.timestamp;
      const distance = this.calculateGeoDistance(attempt.geoLocation, lastLogin.geoLocation);
      const maxPossibleDistance = timeDiff / 3600000 * 900; // max 900 km/h
      if (distance > maxPossibleDistance) {
        scores.push({ factor: 'impossible_travel', score: 50, detail: 'Impossible travel detected' });
      }
    }
    
    // 4. Unusual time
    const loginPatterns = await this.getLoginTimePatterns(attempt.userId);
    if (this.isUnusualTime(attempt.timestamp, loginPatterns)) {
      scores.push({ factor: 'unusual_time', score: 15, detail: 'Login at unusual time' });
    }
    
    // 5. Failed attempt history
    const recentFailures = await this.getRecentFailedAttempts(attempt.userId, '1h');
    if (recentFailures > 3) {
      scores.push({ factor: 'failed_attempts', score: 20, detail: `${recentFailures} recent failures` });
    }
    
    // 6. IP reputation
    const ipReputation = await this.checkIPReputation(attempt.ipAddress);
    if (ipReputation.isTor || ipReputation.isVPN || ipReputation.isProxy) {
      scores.push({ factor: 'suspicious_ip', score: 35, detail: ipReputation.type });
    }
    
    // 7. Credential stuffing detection
    const ipLoginAttempts = await this.getIPLoginAttempts(attempt.ipAddress, '10m');
    if (ipLoginAttempts.uniqueEmails > 5) {
      scores.push({ factor: 'credential_stuffing', score: 60, detail: 'Multiple accounts from same IP' });
    }
    
    const totalScore = scores.reduce((sum, s) => sum + s.score, 0);
    
    return {
      riskScore: Math.min(100, totalScore),
      riskLevel: totalScore >= 70 ? 'HIGH' : totalScore >= 40 ? 'MEDIUM' : 'LOW',
      factors: scores,
      action: this.determineAction(totalScore),
    };
  }
  
  private determineAction(score: number): RiskAction {
    if (score >= 70) return 'BLOCK';           // Block + alert security team
    if (score >= 50) return 'REQUIRE_MFA';      // Force MFA even if not enabled
    if (score >= 30) return 'STEP_UP_AUTH';     // Require additional verification
    return 'ALLOW';                              // Normal login
  }
}
```

---

## 14. Reference Architecture

### 14.1 Complete System Architecture Diagram

```
                            ┌─────────────────────┐
                            │     DNS/CDN          │
                            │  (CloudFlare)        │
                            │  *.platform.com      │
                            │  custom domains      │
                            └─────────┬───────────┘
                                      │
                            ┌─────────▼───────────┐
                            │    Load Balancer     │
                            │  (AWS ALB / Nginx)   │
                            │  TLS Termination     │
                            └─────────┬───────────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    │                 │                   │
          ┌─────────▼───────┐  ┌─────▼──────┐  ┌───────▼─────────┐
          │   Web App       │  │ Admin App  │  │   API Gateway   │
          │   (Next.js)     │  │ (Next.js)  │  │   (Kong)        │
          │   SSR/SSG       │  │ SSR        │  │                 │
          │                 │  │            │  │ • Auth validate  │
          │ Tenant-branded  │  │ Platform   │  │ • Rate limiting  │
          │ trader portal   │  │ management │  │ • Tenant resolve│
          └────────┬────────┘  └─────┬──────┘  │ • Routing       │
                   │                 │          └───────┬─────────┘
                   │                 │                   │
                   └─────────────────┴───────────────────┘
                                      │
                   ┌──────────────────┼──────────────────────┐
                   │         SERVICE MESH (Istio)             │
                   │              mTLS everywhere              │
                   │                                           │
     ┌─────────────┼───────────────┬───────────────┬──────────┤
     │             │               │               │          │
┌────▼────┐  ┌────▼────┐   ┌─────▼─────┐  ┌─────▼────┐  ┌──▼──────┐
│  Auth   │  │Identity │   │  Tenant   │  │  Authz   │  │ Session │
│ Service │  │ Service │   │  Service  │  │ Service  │  │ Service │
│         │  │         │   │          │  │          │  │         │
│ Login   │  │ Profile │   │ Provision│  │ Cerbos/  │  │ CRUD    │
│ MFA     │  │ KYC     │   │ Config   │  │ OPA      │  │ Validate│
│ OAuth   │  │ Social  │   │ Billing  │  │ RBAC     │  │ Device  │
│ Tokens  │  │ Links   │   │ Branding │  │ Policies │  │ Binding │
└────┬────┘  └────┬────┘   └─────┬────┘  └─────┬────┘  └────┬────┘
     │            │               │              │            │
     └────────────┴───────┬───────┴──────────────┴────────────┘
                          │
     ┌────────────────────┼────────────────────────────────────┐
     │                    │                                     │
┌────▼─────┐  ┌──────────▼──┐  ┌───────────┐  ┌────────────┐  │
│Challenge │  │  Trading    │  │  Payout   │  │   Risk     │  │
│ Service  │  │  Service    │  │  Service  │  │   Engine   │  │
│          │  │             │  │           │  │            │  │
│ Templates│  │ MT4/MT5     │  │ Request   │  │ Rules Eval │  │
│ Purchase │  │ cTrader     │  │ Approval  │  │ Monitoring │  │
│ Progress │  │ Integration │  │ Processing│  │ Alerts     │  │
│ Eval     │  │ Sync        │  │ Ledger    │  │ Breaches   │  │
└────┬─────┘  └──────┬──────┘  └─────┬─────┘  └─────┬──────┘  │
     │               │                │               │         │
     └───────────────┴────────┬───────┴───────────────┘         │
                              │                                  │
     ┌────────────────────────┼──────────────────────────────┐  │
     │                    DATA LAYER                          │  │
     │                                                        │  │
     │  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐ │  │
     │  │ PostgreSQL   │  │    Redis     │  │   Vault     │ │  │
     │  │ (Primary +   │  │  Cluster     │  │  (Secrets)  │ │  │
     │  │  Read        │  │              │  │             │ │  │
     │  │  Replicas)   │  │ • Sessions   │  │ • DB creds  │ │  │
     │  │              │  │ • Cache      │  │ • JWT keys  │ │  │
     │  │ • Identities │  │ • Rate limit │  │ • API keys  │ │  │
     │  │ • Tenants    │  │ • Pub/Sub    │  │ • Broker    │ │  │
     │  │ • Trades     │  │              │  │   creds     │ │  │
     │  │ • Payouts    │  │              │  │             │ │  │
     │  │ • Audit Logs │  │              │  │             │ │  │
     │  │ (RLS)        │  │              │  │             │ │  │
     │  └──────────────┘  └──────────────┘  └─────────────┘ │  │
     │                                                        │  │
     │  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐ │  │
     │  │    NATS      │  │     S3       │  │ TimescaleDB │ │  │
     │  │  JetStream   │  │ (Documents)  │  │ (Trade time │ │  │
     │  │              │  │              │  │  series)    │ │  │
     │  │ • Events     │  │ • KYC docs   │  │             │ │  │
     │  │ • Commands   │  │ • Exports    │  │             │ │  │
     │  │ • Audit      │  │ • Backups    │  │             │ │  │
     │  └──────────────┘  └──────────────┘  └─────────────┘ │  │
     └────────────────────────────────────────────────────────┘  │
                                                                 │
     ┌───────────────────────────────────────────────────────────┘
     │  OBSERVABILITY
     │  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐
     │  │ Prometheus + │  │    Loki      │  │   Jaeger    │
     │  │   Grafana    │  │  (Logs)      │  │  (Traces)   │
     │  └──────────────┘  └──────────────┘  └─────────────┘
     │
     │  EXTERNAL INTEGRATIONS
     │  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐
     │  │ Broker APIs  │  │ KYC Provider │  │  Payment    │
     │  │ MT4/MT5      │  │ (SumSub/     │  │  Processor  │
     │  │ cTrader      │  │  Onfido)     │  │  (Stripe)   │
     │  └──────────────┘  └──────────────┘  └─────────────┘
```

### 14.2 Tenant Provisioning Flow

```typescript
// Complete Tenant Provisioning Service
class TenantProvisioningService {
  
  async provisionTenant(input: CreateTenantInput): Promise<Tenant> {
    const saga = new ProvisioningSaga();
    
    try {
      // Step 1: Create tenant record
      const tenant = await saga.execute('create_tenant', async () => {
        return this.tenantRepo.create({
          name: input.name,
          slug: input.slug,
          subscriptionTier: input.tier,
          config: input.config,
        });
      });
      
      // Step 2: Provision database resources
      await saga.execute('provision_database', async () => {
        switch (input.tier) {
          case 'enterprise':
            await this.dbManager.createDedicatedDatabase(tenant.id);
            break;
          case 'standard':
            await this.dbManager.createSchema(tenant.id);
            break;
          case 'starter':
            // Shared schema - just ensure RLS policies exist
            await this.dbManager.ensureRLSPolicies(tenant.id);
            break;
        }
      });
      
      // Step 3: Run migrations for tenant's database/schema
      await saga.execute('run_migrations', async () => {
        await this.migrationRunner.runForTenant(tenant.id);
      });
      
      // Step 4: Create tenant encryption keys
      await saga.execute('create_encryption_keys', async () => {
        await this.vault.createTenantKeys(tenant.id);
      });
      
      // Step 5: Configure auth realm (if using Keycloak)
      await saga.execute('configure_auth', async () => {
        await this.authProvider.createRealm(tenant.id, {
          displayName: tenant.name,
          loginTheme: input.branding?.theme || 'default',
          emailTheme: input.branding?.emailTheme || 'default',
          ssoEnabled: input.config.ssoEnabled,
        });
      });
      
      // Step 6: Create owner account
      const owner = await saga.execute('create_owner', async () => {
        const identity = await this.identityService.create({
          email: input.ownerEmail,
          firstName: input.ownerFirstName,
          lastName: input.ownerLastName,
        });
        
        await this.membershipService.create({
          identityId: identity.id,
          tenantId: tenant.id,
          role: 'firm:owner',
        });
        
        return identity;
      });
      
      // Step 7: Configure DNS (custom domain if provided)
      if (input.customDomain) {
        await saga.execute('configure_dns', async () => {
          await this.dnsManager.configureDomain(tenant.id, input.customDomain);
          await this.certManager.requestCertificate(input.customDomain);
        });
      }
      
      // Step 8: Set up default challenge templates
      await saga.execute('setup_defaults', async () => {
        await this.challengeService.createDefaults(tenant.id);
        await this.riskEngine.createDefaultRules(tenant.id);
      });
      
      // Step 9: Set up monitoring
      await saga.execute('setup_monitoring', async () => {
        await this.monitoring.createTenantDashboard(tenant.id);
        await this.alerting.createTenantAlerts(tenant.id);
      });
      
      // Step 10: Send welcome email
      await this.notificationService.sendWelcome(owner, tenant);
      
      // Emit event
      await this.eventBus.emit('tenant.provisioned', {
        tenantId: tenant.id,
        tier: input.tier,
        owner: owner.id,
      });
      
      return tenant;
      
    } catch (error) {
      // Saga compensation (rollback)
      await saga.compensate();
      throw error;
    }
  }
}
```

### 14.3 API Design

```yaml
# Auth API Endpoints
openapi: 3.1.0
info:
  title: PFaaS Auth API
  version: 1.0.0

paths:
  # Authentication
  /api/auth/register:
    post:
      summary: Register new trader account
      tags: [Authentication]
      
  /api/auth/login:
    post:
      summary: Login with email/password
      tags: [Authentication]
      
  /api/auth/login/social/{provider}:
    get:
      summary: Initiate social login (Google, etc.)
      tags: [Authentication]
      
  /api/auth/login/social/{provider}/callback:
    get:
      summary: Social login callback
      tags: [Authentication]
      
  /api/auth/token/refresh:
    post:
      summary: Refresh access token
      tags: [Authentication]
      
  /api/auth/logout:
    post:
      summary: Logout (revoke session)
      tags: [Authentication]
      
  /api/auth/logout/all:
    post:
      summary: Logout all sessions
      tags: [Authentication]

  # MFA
  /api/auth/mfa/enroll:
    post:
      summary: Start MFA enrollment
      tags: [MFA]
      
  /api/auth/mfa/verify:
    post:
      summary: Verify MFA code
      tags: [MFA]
      
  /api/auth/mfa/recovery-codes:
    get:
      summary: Get recovery codes
      tags: [MFA]

  # Password Management
  /api/auth/password/change:
    post:
      summary: Change password (authenticated)
      tags: [Password]
      
  /api/auth/password/forgot:
    post:
      summary: Request password reset
      tags: [Password]
      
  /api/auth/password/reset:
    post:
      summary: Reset password with token
      tags: [Password]

  # Sessions
  /api/auth/sessions:
    get:
      summary: List active sessions
      tags: [Sessions]
      
  /api/auth/sessions/{sessionId}:
    delete:
      summary: Revoke specific session
      tags: [Sessions]

  # API Keys
  /api/auth/api-keys:
    get:
      summary: List API keys
      tags: [API Keys]
    post:
      summary: Create API key
      tags: [API Keys]
      
  /api/auth/api-keys/{keyId}:
    delete:
      summary: Revoke API key
      tags: [API Keys]

  # Identity Management
  /api/identity/profile:
    get:
      summary: Get current user profile
      tags: [Identity]
    patch:
      summary: Update profile
      tags: [Identity]

  # Tenant Management
  /api/tenants:
    get:
      summary: List tenants (platform admin)
      tags: [Tenants]
    post:
      summary: Create tenant
      tags: [Tenants]
      
  /api/tenants/{tenantId}/members:
    get:
      summary: List tenant members
      tags: [Tenants]
    post:
      summary: Invite member
      tags: [Tenants]
      
  /api/tenants/{tenantId}/members/{userId}/role:
    put:
      summary: Update member role
      tags: [Tenants]

  # OIDC Discovery
  /.well-known/openid-configuration:
    get:
      summary: OIDC Discovery Document
      tags: [OIDC]
      
  /.well-known/jwks.json:
    get:
      summary: JSON Web Key Set
      tags: [OIDC]
```

### 14.4 Monitoring & Alerting

```typescript
// Key Metrics to Monitor
const authMetrics = {
  // Business Metrics
  'auth.login.total': 'counter',              // Total login attempts
  'auth.login.success': 'counter',            // Successful logins
  'auth.login.failure': 'counter',            // Failed logins
  'auth.login.blocked': 'counter',            // Blocked logins
  'auth.registration.total': 'counter',       // New registrations
  'auth.mfa.enrollment': 'counter',           // MFA enrollments
  'auth.sessions.active': 'gauge',            // Current active sessions
  'auth.tokens.issued': 'counter',            // Tokens issued
  'auth.tokens.refreshed': 'counter',         // Token refreshes
  
  // Performance Metrics
  'auth.login.latency': 'histogram',          // Login latency
  'auth.token.validation.latency': 'histogram', // Token validation latency
  'auth.policy.evaluation.latency': 'histogram', // Policy eval latency
  
  // Security Metrics
  'auth.anomaly.detected': 'counter',         // Anomalies detected
  'auth.brute_force.detected': 'counter',     // Brute force attempts
  'auth.token_reuse.detected': 'counter',     // Token reuse attacks
  'auth.cross_tenant.attempt': 'counter',     // Cross-tenant access attempts
  
  // Tenant Metrics
  'tenant.active_users': 'gauge',             // Per-tenant active users
  'tenant.api_calls': 'counter',              // Per-tenant API usage
};

// Critical Alerts
const alertRules = [
  {
    name: 'HighFailedLoginRate',
    condition: 'rate(auth.login.failure[5m]) > 100',
    severity: 'WARNING',
    action: 'Notify security team',
  },
  {
    name: 'TokenReuseAttack',
    condition: 'auth.token_reuse.detected > 0',
    severity: 'CRITICAL',
    action: 'Immediate investigation, revoke affected sessions',
  },
  {
    name: 'CrossTenantAccess',
    condition: 'auth.cross_tenant.attempt > 0',
    severity: 'CRITICAL',
    action: 'Immediate investigation, potential data breach',
  },
  {
    name: 'AuthServiceLatencyHigh',
    condition: 'histogram_quantile(0.99, auth.login.latency) > 2',
    severity: 'WARNING',
    action: 'Scale auth service, investigate bottleneck',
  },
  {
    name: 'MFABypassAttempt',
    condition: 'auth.mfa.bypass_attempt > 0',
    severity: 'CRITICAL',
    action: 'Block user, investigate',
  },
];
```

### 14.5 Implementation Roadmap

```
┌─────────────────────────────────────────────────────────────────┐
│                  IMPLEMENTATION ROADMAP                           │
│                                                                  │
│  Phase 1: Foundation (Weeks 1-4)                                │
│  ├── Multi-tenant database setup (PostgreSQL + RLS)             │
│  ├── Basic auth (email/password, JWT)                           │
│  ├── Tenant CRUD and resolution                                  │
│  ├── Basic RBAC (3 roles: owner, admin, trader)                 │
│  ├── Session management with Redis                               │
│  ├── Basic audit logging                                         │
│  └── DELIVERABLE: Working auth with tenant isolation             │
│                                                                  │
│  Phase 2: Security Hardening (Weeks 5-8)                        │
│  ├── MFA implementation (TOTP)                                   │
│  ├── Refresh token rotation                                      │
│  ├── Rate limiting                                               │
│  ├── Password policies                                           │
│  ├── Account lockout                                             │
│  ├── Comprehensive audit logging                                 │
│  ├── Field-level encryption for PII                              │
│  └── DELIVERABLE: Production-ready security                      │
│                                                                  │
│  Phase 3: Advanced Auth (Weeks 9-12)                            │
│  ├── Social login (Google, Apple)                                │
│  ├── Passkeys/WebAuthn                                           │
│  ├── API key management                                          │
│  ├── OAuth2/OIDC provider endpoints                              │
│  ├── Device fingerprinting                                       │
│  ├── Login anomaly detection                                     │
│  └── DELIVERABLE: Full auth feature set                          │
│                                                                  │
│  Phase 4: Authorization Engine (Weeks 13-16)                    │
│  ├── Policy engine integration (Cerbos/OPA)                     │
│  ├── Fine-grained permissions                                    │
│  ├── ABAC policies                                               │
│  ├── Custom roles per tenant                                     │
│  ├── Impersonation with audit                                    │
│  └── DELIVERABLE: Enterprise authorization                       │
│                                                                  │
│  Phase 5: Enterprise Features (Weeks 17-20)                     │
│  ├── SAML SSO for enterprise tenants                             │
│  ├── SCIM provisioning                                           │
│  ├── Custom domain per tenant                                    │
│  ├── Tenant tier upgrades (schema/DB isolation)                 │
│  ├── Geo-fencing                                                 │
│  ├── GDPR tooling (export, deletion)                            │
│  └── DELIVERABLE: Enterprise-ready platform                      │
│                                                                  │
│  Phase 6: Scale & Compliance (Weeks 21-24)                      │
│  ├── Performance optimization                                    │
│  ├── SOC 2 preparation                                           │
│  ├── Penetration testing                                         │
│  ├── Disaster recovery testing                                   │
│  ├── Documentation & runbooks                                    │
│  └── DELIVERABLE: Audit-ready, scalable system                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Summary & Key Decisions

| Decision Area | Recommendation | Rationale |
|---------------|----------------|-----------|
| **Multi-tenancy Model** | Hybrid (shared + schema + dedicated) | Flexibility across tenant tiers |
| **Tenant Resolution** | Custom domain > Subdomain > JWT claim | Best UX, white-label support |
| **Authentication** | Keycloak (self-hosted) or Custom (NestJS) | Cost-effective, full control |
| **MFA** | TOTP primary + WebAuthn | Security + modern UX |
| **Token Strategy** | JWT (RS256, 15min) + Opaque refresh (7d, rotation) | Security + performance |
| **Password Hashing** | Argon2id | Industry best practice |
| **Authorization** | RBAC + ABAC hybrid (Cerbos) | Flexibility + auditability |
| **Data Isolation** | PostgreSQL RLS + per-tenant encryption keys | Defense in depth |
| **Session Management** | Redis Cluster with device binding | Performance + security |
| **Secret Management** | HashiCorp Vault | Dynamic secrets, rotation |
| **Event System** | NATS JetStream | Lightweight, reliable |
| **Database** | PostgreSQL 16 + TimescaleDB | RLS, partitioning, time-series |
| **Monitoring** | OpenTelemetry + Grafana stack | Full observability |

This architecture provides a **secure, scalable, and compliant** foundation for a Prop Firm as a Service platform, capable of supporting hundreds of prop firms and millions of traders while maintaining strict data isolation and regulatory compliance.
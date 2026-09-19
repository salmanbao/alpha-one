# Comprehensive Research: Enterprise-Grade Risk & Evaluation Engine for Prop Firm as a Service (PFaaS)

## Table of Contents
1. [Architecture Overview](#1-architecture-overview)
2. [Core Components Deep Dive](#2-core-components-deep-dive)
3. [Open-Source Solutions Mapping](#3-open-source-solutions-mapping)
4. [Detailed System Design](#4-detailed-system-design)
5. [Data Pipeline Architecture](#5-data-pipeline-architecture)
6. [Risk Models & Algorithms](#6-risk-models--algorithms)
7. [Evaluation Engine Design](#7-evaluation-engine-design)
8. [Technology Stack Recommendations](#8-technology-stack-recommendations)
9. [Build vs. Leverage Decision Matrix](#9-build-vs-leverage-decision-matrix)
10. [Implementation Roadmap](#10-implementation-roadmap)

---

## 1. Architecture Overview

### What a Prop Firm Risk & Evaluation Engine Does

```
┌─────────────────────────────────────────────────────────────────────┐
│                    PROP FIRM AS A SERVICE PLATFORM                   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────┐    ┌──────────────────┐    ┌───────────────────┐  │
│  │  TRADER      │───▶│  RISK ENGINE     │───▶│  EVALUATION       │  │
│  │  ACTIVITY    │    │  (Real-time)     │    │  ENGINE           │  │
│  └─────────────┘    └──────────────────┘    └───────────────────┘  │
│         │                    │                        │             │
│         ▼                    ▼                        ▼             │
│  ┌─────────────┐    ┌──────────────────┐    ┌───────────────────┐  │
│  │  MARKET DATA │    │  POSITION        │    │  CHALLENGE        │  │
│  │  FEEDS       │    │  MANAGEMENT      │    │  PROGRESSION      │  │
│  └─────────────┘    └──────────────────┘    └───────────────────┘  │
│                              │                        │             │
│                              ▼                        ▼             │
│                     ┌──────────────────┐    ┌───────────────────┐  │
│                     │  ACCOUNT         │    │  PAYOUT           │  │
│                     │  MANAGEMENT      │    │  CALCULATION      │  │
│                     └──────────────────┘    └───────────────────┘  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                          ENTERPRISE RISK & EVALUATION ENGINE                  │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                        INGESTION LAYER                                  │ │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────────────┐  │ │
│  │  │ Market Data│ │ Trade      │ │ Account    │ │ Broker/Exchange    │  │ │
│  │  │ Feeds      │ │ Events     │ │ Events     │ │ Connectivity       │  │ │
│  │  └─────┬──────┘ └─────┬──────┘ └─────┬──────┘ └─────────┬──────────┘  │ │
│  └────────┼──────────────┼──────────────┼───────────────────┼────────────┘ │
│           │              │              │                   │              │
│  ┌────────▼──────────────▼──────────────▼───────────────────▼────────────┐ │
│  │                    EVENT STREAMING LAYER                               │ │
│  │              (Apache Kafka / Redpanda / NATS)                         │ │
│  └────────┬──────────────┬──────────────┬───────────────────┬────────────┘ │
│           │              │              │                   │              │
│  ┌────────▼──────────────▼──────────────▼───────────────────▼────────────┐ │
│  │                    PROCESSING LAYER                                    │ │
│  │  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────────────┐ │ │
│  │  │  RISK ENGINE    │ │  EVALUATION     │ │  ANALYTICS ENGINE       │ │ │
│  │  │  (Real-time)    │ │  ENGINE         │ │  (Batch + Real-time)    │ │ │
│  │  │                 │ │                 │ │                         │ │ │
│  │  │ • Pre-trade     │ │ • Rule Engine   │ │ • Performance Metrics   │ │ │
│  │  │ • Post-trade    │ │ • Challenge     │ │ • Risk Analytics        │ │ │
│  │  │ • Position      │ │   Tracking      │ │ • Behavioral Analysis   │ │ │
│  │  │ • Exposure      │ │ • Phase Mgmt    │ │ • Anomaly Detection     │ │ │
│  │  │ • Drawdown      │ │ • Profit Target │ │ • Copy Trade Detection  │ │ │
│  │  │ • Loss Limits   │ │ • Consistency   │ │                         │ │ │
│  │  └────────┬────────┘ └────────┬────────┘ └────────────┬────────────┘ │ │
│  └───────────┼───────────────────┼───────────────────────┼──────────────┘ │
│              │                   │                       │                │
│  ┌───────────▼───────────────────▼───────────────────────▼──────────────┐ │
│  │                      STATE & STORAGE LAYER                            │ │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────┐ │ │
│  │  │ Redis/   │ │TimescaleDB│ │PostgreSQL│ │ClickHouse│ │ Object    │ │ │
│  │  │ Dragonfly│ │(Time-     │ │(State)   │ │(Analytics│ │ Storage   │ │ │
│  │  │ (Cache)  │ │ series)   │ │          │ │ OLAP)    │ │ (S3)      │ │ │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └───────────┘ │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
│              │                   │                       │                │
│  ┌───────────▼───────────────────▼───────────────────────▼──────────────┐ │
│  │                      API & INTEGRATION LAYER                          │ │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────┐ │ │
│  │  │ REST API │ │ WebSocket│ │ gRPC     │ │ Webhooks │ │ Admin     │ │ │
│  │  │          │ │ Server   │ │ Services │ │          │ │ Dashboard │ │ │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └───────────┘ │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Core Components Deep Dive

### 2.1 Risk Engine Components

```
┌─────────────────────────────────────────────────────────────────┐
│                        RISK ENGINE                               │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                 PRE-TRADE RISK CHECKS                     │   │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────────────┐   │   │
│  │  │ Order Size │ │ Position   │ │ Instrument         │   │   │
│  │  │ Limits     │ │ Limits     │ │ Restrictions       │   │   │
│  │  └────────────┘ └────────────┘ └────────────────────┘   │   │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────────────┐   │   │
│  │  │ Margin     │ │ Trading    │ │ Max Open           │   │   │
│  │  │ Check      │ │ Hours      │ │ Positions          │   │   │
│  │  └────────────┘ └────────────┘ └────────────────────┘   │   │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────────────┐   │   │
│  │  │ News Event │ │ Weekend    │ │ Hedging/           │   │   │
│  │  │ Restriction│ │ Holding    │ │ Martingale Check   │   │   │
│  │  └────────────┘ └────────────┘ └────────────────────┘   │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                 REAL-TIME MONITORING                       │   │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────────────┐   │   │
│  │  │ Daily      │ │ Max        │ │ Trailing           │   │   │
│  │  │ Drawdown   │ │ Drawdown   │ │ Drawdown           │   │   │
│  │  └────────────┘ └────────────┘ └────────────────────┘   │   │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────────────┐   │   │
│  │  │ P&L        │ │ Exposure   │ │ Concentration      │   │   │
│  │  │ Tracking   │ │ Monitoring │ │ Risk               │   │   │
│  │  └────────────┘ └────────────┘ └────────────────────┘   │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                 BREACH ACTIONS                             │   │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────────────┐   │   │
│  │  │ Soft       │ │ Hard       │ │ Account            │   │   │
│  │  │ Breach     │ │ Breach     │ │ Termination        │   │   │
│  │  │ (Warning)  │ │ (Close All)│ │ (Fail Challenge)   │   │   │
│  │  └────────────┘ └────────────┘ └────────────────────┘   │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Evaluation Engine Components

```
┌─────────────────────────────────────────────────────────────────┐
│                     EVALUATION ENGINE                            │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              CHALLENGE PHASE MANAGEMENT                    │   │
│  │                                                            │   │
│  │  Phase 1 (Evaluation)  ──▶  Phase 2 (Verification)       │   │
│  │       ──▶  Funded Account  ──▶  Scaling Plan              │   │
│  │                                                            │   │
│  │  Rules per Phase:                                          │   │
│  │  • Profit Target (e.g., 8% Phase 1, 5% Phase 2)          │   │
│  │  • Max Daily Loss (e.g., 5%)                              │   │
│  │  • Max Total Loss (e.g., 10%)                             │   │
│  │  • Minimum Trading Days (e.g., 5 days)                    │   │
│  │  • Time Limit (e.g., 30 days / unlimited)                 │   │
│  │  • Consistency Rules                                       │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              PERFORMANCE METRICS                           │   │
│  │                                                            │   │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────────┐    │   │
│  │  │ Sharpe      │ │ Sortino     │ │ Profit Factor   │    │   │
│  │  │ Ratio       │ │ Ratio       │ │                 │    │   │
│  │  └─────────────┘ └─────────────┘ └─────────────────┘    │   │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────────┐    │   │
│  │  │ Win Rate    │ │ Avg Win/    │ │ Max Consecutive │    │   │
│  │  │             │ │ Avg Loss    │ │ Losses          │    │   │
│  │  └─────────────┘ └─────────────┘ └─────────────────┘    │   │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────────┐    │   │
│  │  │ Expectancy  │ │ Recovery    │ │ Calmar Ratio    │    │   │
│  │  │             │ │ Factor      │ │                 │    │   │
│  │  └─────────────┘ └─────────────┘ └─────────────────┘    │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              FRAUD & ABUSE DETECTION                       │   │
│  │                                                            │   │
│  │  • Copy trading detection                                  │   │
│  │  • Account passing services detection                      │   │
│  │  • Latency arbitrage detection                            │   │
│  │  • News straddling detection                               │   │
│  │  • Martingale/grid strategy detection                     │   │
│  │  • IP/device fingerprint correlation                      │   │
│  │  • Behavioral anomaly detection                           │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              PAYOUT & SCALING ENGINE                       │   │
│  │                                                            │   │
│  │  • Profit split calculation (e.g., 80/20, 90/10)         │   │
│  │  • Scaling plan eligibility                               │   │
│  │  • Payout schedule management                             │   │
│  │  • Withdrawal request processing                          │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Open-Source Solutions Mapping

### 3.1 Complete Mapping: Component → Open-Source Solution

```
┌────────────────────────┬──────────────────────────┬──────────────────────────┐
│     COMPONENT          │   OPEN-SOURCE SOLUTION   │     PURPOSE              │
├────────────────────────┼──────────────────────────┼──────────────────────────┤
│ Event Streaming        │ Apache Kafka             │ Event backbone           │
│                        │ Redpanda                 │ Kafka-compatible,faster  │
│                        │ NATS JetStream           │ Lightweight streaming    │
├────────────────────────┼──────────────────────────┼──────────────────────────┤
│ Stream Processing      │ Apache Flink             │ Complex event processing │
│                        │ Apache Kafka Streams     │ Stream processing        │
│                        │ Benthos/Redpanda Connect │ Data pipeline            │
├────────────────────────┼──────────────────────────┼──────────────────────────┤
│ Rule Engine            │ Drools                   │ Business rules           │
│                        │ OpenL Tablets            │ Business rules (tables)  │
│                        │ json-rules-engine (Node) │ Lightweight rules        │
│                        │ Grule (Go)               │ Go-native rules engine   │
│                        │ Easy Rules (Java)        │ Simple rules framework   │
│                        │ Polar/OPA                │ Policy engine            │
├────────────────────────┼──────────────────────────┼──────────────────────────┤
│ Time-Series Database   │ TimescaleDB              │ Trade/price time-series  │
│                        │ QuestDB                  │ High-perf time-series    │
│                        │ InfluxDB OSS             │ Metrics time-series      │
├────────────────────────┼──────────────────────────┼──────────────────────────┤
│ OLAP / Analytics       │ ClickHouse               │ Analytical queries       │
│                        │ Apache Druid             │ Real-time analytics      │
│                        │ Apache Pinot             │ User-facing analytics    │
│                        │ DuckDB                   │ Embedded analytics       │
├────────────────────────┼──────────────────────────┼──────────────────────────┤
│ Caching / State        │ Redis                    │ In-memory state          │
│                        │ Dragonfly                │ Redis-compatible, faster │
│                        │ KeyDB                    │ Multi-threaded Redis     │
├────────────────────────┼──────────────────────────┼──────────────────────────┤
│ Relational Database    │ PostgreSQL               │ Core state management    │
│                        │ CockroachDB              │ Distributed SQL          │
│                        │ YugabyteDB               │ Distributed PostgreSQL   │
├────────────────────────┼──────────────────────────┼──────────────────────────┤
│ Workflow Orchestration │ Temporal.io              │ Workflow orchestration   │
│                        │ Apache Airflow           │ Batch workflow           │
│                        │ Prefect                  │ Data pipeline workflow   │
├────────────────────────┼──────────────────────────┼──────────────────────────┤
│ API Gateway            │ Kong                     │ API management           │
│                        │ APISIX                   │ High-performance gateway │
│                        │ Traefik                  │ Cloud-native proxy       │
├────────────────────────┼──────────────────────────┼──────────────────────────┤
│ Anomaly Detection/ML   │ Apache Spark MLlib       │ Batch ML                 │
│                        │ PyTorch / scikit-learn   │ ML models                │
│                        │ River (Python)           │ Online/streaming ML      │
│                        │ Alibi Detect             │ Anomaly detection        │
├────────────────────────┼──────────────────────────┼──────────────────────────┤
│ Observability          │ Prometheus + Grafana     │ Metrics & dashboards     │
│                        │ OpenTelemetry            │ Distributed tracing      │
│                        │ Loki                     │ Log aggregation          │
│                        │ Jaeger                   │ Trace visualization      │
├────────────────────────┼──────────────────────────┼──────────────────────────┤
│ Task Queue             │ Celery (Python)          │ Async task processing    │
│                        │ BullMQ (Node.js)         │ Job queue                │
│                        │ Asynq (Go)               │ Go task queue            │
├────────────────────────┼──────────────────────────┼──────────────────────────┤
│ Notifications          │ Novu                     │ Notification infra       │
│                        │ Apprise                  │ Multi-channel notify     │
├────────────────────────┼──────────────────────────┼──────────────────────────┤
│ Auth & Identity        │ Keycloak                 │ Identity management      │
│                        │ Ory (Kratos/Hydra)       │ Identity & OAuth         │
│                        │ SuperTokens              │ Auth solution            │
├────────────────────────┼──────────────────────────┼──────────────────────────┤
│ FIX Protocol           │ QuickFIX/J               │ FIX connectivity         │
│                        │ QuickFIX/n               │ .NET FIX engine          │
├────────────────────────┼──────────────────────────┼──────────────────────────┤
│ Trading Connectivity   │ CCXT                     │ Crypto exchange unified  │
│                        │ Alpaca API client         │ Stock broker API         │
│ (Market Data)          │ cTrader Open API         │ Forex/CFD connectivity   │
├────────────────────────┼──────────────────────────┼──────────────────────────┤
│ Financial Calculations │ QuantLib                 │ Quant finance library    │
│                        │ TA-Lib                   │ Technical analysis       │
│                        │ pandas-ta                │ Python TA indicators     │
├────────────────────────┼──────────────────────────┼──────────────────────────┤
│ Container Orchestration│ Kubernetes               │ Container management     │
│                        │ Nomad                    │ Simpler orchestration    │
└────────────────────────┴──────────────────────────┴──────────────────────────┘
```

### 3.2 Deep Dive: Key Open-Source Solutions

#### A. Rule Engines (Critical for Risk & Evaluation)

```
┌─────────────────────────────────────────────────────────────────────┐
│                     RULE ENGINE COMPARISON                           │
├────────────┬──────────┬────────────┬────────────┬──────────────────┤
│ Solution   │Language  │Performance │ Hot Reload │ Best For         │
├────────────┼──────────┼────────────┼────────────┼──────────────────┤
│ Drools     │ Java     │ High       │ Yes        │ Complex rules,   │
│            │          │            │            │ enterprise       │
├────────────┼──────────┼────────────┼────────────┼──────────────────┤
│ OPA/Rego   │ Go       │ Very High  │ Yes        │ Policy-as-code,  │
│            │          │            │            │ authorization    │
├────────────┼──────────┼────────────┼────────────┼──────────────────┤
│ json-rules │ Node.js  │ Medium     │ Yes        │ Dynamic JSON     │
│ -engine    │          │            │            │ rules            │
├────────────┼──────────┼────────────┼────────────┼──────────────────┤
│ Grule      │ Go       │ High       │ Yes        │ Go microservices │
├────────────┼──────────┼────────────┼────────────┼──────────────────┤
│ OpenL      │ Java     │ Medium     │ Yes        │ Excel/table      │
│ Tablets    │          │            │            │ based rules      │
├────────────┼──────────┼────────────┼────────────┼──────────────────┤
│ Easy Rules │ Java     │ High       │ Limited    │ Simple rule      │
│            │          │            │            │ chains           │
├────────────┼──────────┼────────────┼────────────┼──────────────────┤
│ Nools      │ Node.js  │ Medium     │ Yes        │ Rete-based       │
│            │          │            │            │ forward chain    │
└────────────┴──────────┴────────────┴────────────┴──────────────────┘
```

**Recommendation for Prop Firm**: Use **OPA (Open Policy Agent)** for authorization/policy decisions + a **custom lightweight rule engine** or **Drools** for complex trading rules.

```python
# Example: OPA policy for prop firm risk rules (Rego language)
"""
package propfirm.risk

# Daily drawdown check
deny_trade[msg] {
    input.daily_loss > input.account.max_daily_loss_limit
    msg := sprintf("Daily loss limit breached: $%.2f exceeds $%.2f", 
                   [input.daily_loss, input.account.max_daily_loss_limit])
}

# Max drawdown check
deny_trade[msg] {
    input.total_drawdown > input.account.max_total_drawdown
    msg := sprintf("Max drawdown breached: %.2f%% exceeds %.2f%%",
                   [input.total_drawdown, input.account.max_total_drawdown])
}

# Position size check
deny_trade[msg] {
    input.order.lot_size > input.account.max_lot_size
    msg := sprintf("Lot size %.2f exceeds maximum %.2f",
                   [input.order.lot_size, input.account.max_lot_size])
}

# Trading hours check
deny_trade[msg] {
    not within_trading_hours(input.timestamp)
    msg := "Trading outside allowed hours"
}

# News restriction check
deny_trade[msg] {
    input.account.news_trading_restricted
    news_event_within_window(input.instrument, input.timestamp, 2)
    msg := "Trading restricted during news events"
}

# Weekend holding restriction
deny_trade[msg] {
    input.account.weekend_holding_restricted
    is_friday_close_window(input.timestamp)
    input.order.type == "OPEN"
    msg := "Cannot open new positions before weekend"
}
"""
```

#### B. Event Streaming & Stream Processing

```
┌─────────────────────────────────────────────────────────────────────┐
│              EVENT STREAMING ARCHITECTURE                            │
│                                                                      │
│  ┌──────────────┐     ┌──────────────────────────┐                  │
│  │ Trade Events │────▶│                          │                  │
│  └──────────────┘     │                          │     ┌──────────┐│
│  ┌──────────────┐     │    Apache Kafka /         │────▶│ Risk     ││
│  │ Price Ticks  │────▶│    Redpanda               │     │ Processor││
│  └──────────────┘     │                          │     └──────────┘│
│  ┌──────────────┐     │    Topics:               │     ┌──────────┐│
│  │ Account      │────▶│    • trades.executed      │────▶│ Eval     ││
│  │ Events       │     │    • prices.tick          │     │ Processor││
│  └──────────────┘     │    • risk.alerts          │     └──────────┘│
│  ┌──────────────┐     │    • account.updates      │     ┌──────────┐│
│  │ Risk         │────▶│    • evaluation.events    │────▶│ Analytics││
│  │ Signals      │     │    • breach.notifications │     │ Pipeline ││
│  └──────────────┘     └──────────────────────────┘     └──────────┘│
│                                                                      │
│  Stream Processing with Apache Flink:                                │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  • Sliding window P&L calculations (1min, 5min, 1hr, 1day) │   │
│  │  • Real-time drawdown computation                           │   │
│  │  • Pattern detection (martingale, grid, copy trade)         │   │
│  │  • Aggregation of exposure across instruments               │   │
│  │  • Complex event processing for multi-rule evaluation       │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

#### C. Temporal.io for Workflow Orchestration

```
┌─────────────────────────────────────────────────────────────────────┐
│            TEMPORAL.IO WORKFLOW EXAMPLES                             │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  CHALLENGE LIFECYCLE WORKFLOW                                │   │
│  │                                                              │   │
│  │  Start ──▶ Phase 1 Active ──▶ Phase 1 Complete?             │   │
│  │              │                   │          │                 │   │
│  │              │ (daily checks)    │ YES      │ FAILED         │   │
│  │              │ (drawdown check)  ▼          ▼                │   │
│  │              │              Phase 2 ──▶ Phase 2 Complete?    │   │
│  │              │                           │          │        │   │
│  │              │                           │ YES      │ FAILED │   │
│  │              │                           ▼          ▼        │   │
│  │              │                    Fund Account    Terminate  │   │
│  │              │                           │                   │   │
│  │              │                           ▼                   │   │
│  │              │                    Scaling Plan               │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  PAYOUT WORKFLOW                                             │   │
│  │                                                              │   │
│  │  Request ──▶ Verify Eligibility ──▶ Calculate Split         │   │
│  │    ──▶ Fraud Check ──▶ Approve ──▶ Process Payment          │   │
│  │    ──▶ Update Account ──▶ Notify Trader                     │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  BREACH HANDLING WORKFLOW                                    │   │
│  │                                                              │   │
│  │  Breach Detected ──▶ Classify Severity                      │   │
│  │    ──▶ [Soft] ──▶ Send Warning ──▶ Monitor                 │   │
│  │    ──▶ [Hard] ──▶ Close Positions ──▶ Lock Account          │   │
│  │    ──▶ [Critical] ──▶ Immediate Liquidation                │   │
│  │         ──▶ Fail Challenge ──▶ Notify                       │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 4. Detailed System Design

### 4.1 Microservices Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    MICROSERVICES DECOMPOSITION                           │
│                                                                          │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────┐ │
│  │ Account Service  │  │ Trade Service    │  │ Market Data Service     │ │
│  │                  │  │                  │  │                         │ │
│  │ • Create account │  │ • Receive trades │  │ • Price feed ingestion  │ │
│  │ • Account state  │  │ • Trade history  │  │ • Price normalization   │ │
│  │ • Balance mgmt   │  │ • Open positions │  │ • Price distribution    │ │
│  │ • Challenge cfg  │  │ • P&L calc       │  │ • Historical data      │ │
│  └────────┬─────────┘  └────────┬─────────┘  └───────────┬─────────────┘ │
│           │                     │                         │              │
│  ┌────────▼─────────────────────▼─────────────────────────▼────────────┐ │
│  │                    EVENT BUS (Kafka/Redpanda)                        │ │
│  └────────┬─────────────────────┬─────────────────────────┬────────────┘ │
│           │                     │                         │              │
│  ┌────────▼─────────┐  ┌───────▼──────────┐  ┌──────────▼─────────────┐ │
│  │ Risk Service      │  │ Evaluation       │  │ Analytics Service      │ │
│  │                   │  │ Service           │  │                        │ │
│  │ • Pre-trade check │  │ • Rule engine     │  │ • Performance metrics  │ │
│  │ • Drawdown calc   │  │ • Phase tracking  │  │ • Trader scoring       │ │
│  │ • Position mgmt   │  │ • Target tracking │  │ • Anomaly detection    │ │
│  │ • Breach handling │  │ • Consistency     │  │ • Behavioral analysis  │ │
│  │ • Auto-liquidate  │  │ • Day counting    │  │ • Copy trade detect    │ │
│  └────────┬─────────┘  └───────┬──────────┘  └──────────┬─────────────┘ │
│           │                     │                         │              │
│  ┌────────▼─────────┐  ┌───────▼──────────┐  ┌──────────▼─────────────┐ │
│  │ Notification      │  │ Payout           │  │ Admin Service          │ │
│  │ Service           │  │ Service           │  │                        │ │
│  │ • Email           │  │ • Profit split   │  │ • Dashboard            │ │
│  │ • Push            │  │ • Payout calc    │  │ • Configuration        │ │
│  │ • Webhook         │  │ • Payment proc   │  │ • White-label mgmt     │ │
│  │ • In-app          │  │ • Scaling plan   │  │ • Reporting            │ │
│  └──────────────────┘  └──────────────────┘  └────────────────────────┘ │
│                                                                          │
│  ┌──────────────────┐  ┌──────────────────┐  ┌────────────────────────┐ │
│  │ Broker Gateway    │  │ Fraud Detection  │  │ Audit Service          │ │
│  │ Service           │  │ Service           │  │                        │ │
│  │ • MT4/MT5 bridge │  │ • IP analysis    │  │ • Event logging        │ │
│  │ • cTrader bridge  │  │ • Device finger  │  │ • Compliance trail     │ │
│  │ • Exchange APIs   │  │ • Trade pattern  │  │ • Immutable log        │ │
│  │ • Order routing   │  │ • ML models      │  │ • Regulatory reports   │ │
│  └──────────────────┘  └──────────────────┘  └────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Data Models

```sql
-- Core Data Models (PostgreSQL)

-- Account (Challenge) Model
CREATE TABLE trading_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trader_id UUID NOT NULL REFERENCES traders(id),
    firm_id UUID NOT NULL REFERENCES firms(id),
    
    -- Challenge Configuration
    challenge_type VARCHAR(50) NOT NULL, -- 'standard', 'aggressive', 'instant'
    current_phase VARCHAR(20) NOT NULL DEFAULT 'phase_1',
    -- 'phase_1', 'phase_2', 'funded', 'scaling_1', 'scaling_2'
    
    -- Account Parameters
    initial_balance DECIMAL(15,2) NOT NULL,
    current_balance DECIMAL(15,2) NOT NULL,
    current_equity DECIMAL(15,2) NOT NULL,
    
    -- Risk Parameters (configurable per firm/challenge)
    max_daily_loss_pct DECIMAL(5,2) NOT NULL DEFAULT 5.00,
    max_daily_loss_amount DECIMAL(15,2) NOT NULL,
    max_total_loss_pct DECIMAL(5,2) NOT NULL DEFAULT 10.00,
    max_total_loss_amount DECIMAL(15,2) NOT NULL,
    profit_target_pct DECIMAL(5,2) NOT NULL,
    profit_target_amount DECIMAL(15,2) NOT NULL,
    min_trading_days INTEGER NOT NULL DEFAULT 5,
    max_calendar_days INTEGER, -- NULL = unlimited
    max_lot_size DECIMAL(10,2),
    max_open_positions INTEGER,
    
    -- Tracking
    highest_balance DECIMAL(15,2) NOT NULL, -- for trailing drawdown
    day_start_balance DECIMAL(15,2) NOT NULL, -- for daily drawdown
    day_start_equity DECIMAL(15,2) NOT NULL,
    trading_days_count INTEGER NOT NULL DEFAULT 0,
    
    -- Status
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    -- 'active', 'passed', 'failed', 'suspended', 'closed'
    breach_type VARCHAR(50),
    breach_timestamp TIMESTAMPTZ,
    
    -- Restrictions (JSON for flexibility)
    restrictions JSONB NOT NULL DEFAULT '{}',
    /* Example:
    {
        "news_trading": false,
        "weekend_holding": false,
        "hedging_allowed": true,
        "martingale_allowed": false,
        "max_instruments": 10,
        "allowed_instruments": ["EURUSD", "GBPUSD", "..."],
        "trading_hours": {"start": "00:00", "end": "23:59"},
        "consistency_rule": {
            "enabled": true,
            "max_daily_profit_pct": 40
        }
    }
    */
    
    -- Metadata
    platform VARCHAR(20), -- 'mt4', 'mt5', 'ctrader', 'custom'
    platform_account_id VARCHAR(100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Indexes
    CONSTRAINT valid_phase CHECK (current_phase IN 
        ('phase_1', 'phase_2', 'funded', 'scaling_1', 'scaling_2', 'scaling_3')),
    CONSTRAINT valid_status CHECK (status IN 
        ('active', 'passed', 'failed', 'suspended', 'closed'))
);

-- Trade Model
CREATE TABLE trades (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id UUID NOT NULL REFERENCES trading_accounts(id),
    external_trade_id VARCHAR(100),
    
    -- Trade Details
    instrument VARCHAR(20) NOT NULL,
    direction VARCHAR(4) NOT NULL, -- 'BUY', 'SELL'
    lot_size DECIMAL(10,4) NOT NULL,
    open_price DECIMAL(20,8) NOT NULL,
    close_price DECIMAL(20,8),
    
    -- P&L
    realized_pnl DECIMAL(15,2),
    unrealized_pnl DECIMAL(15,2),
    commission DECIMAL(10,2) DEFAULT 0,
    swap DECIMAL(10,2) DEFAULT 0,
    
    -- Timestamps
    opened_at TIMESTAMPTZ NOT NULL,
    closed_at TIMESTAMPTZ,
    
    -- Status
    status VARCHAR(10) NOT NULL DEFAULT 'open',
    -- 'open', 'closed', 'cancelled'
    
    -- Metadata
    close_reason VARCHAR(50), -- 'manual', 'stop_loss', 'take_profit', 'liquidation'
    metadata JSONB DEFAULT '{}',
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Risk Events / Breach Log
CREATE TABLE risk_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id UUID NOT NULL REFERENCES trading_accounts(id),
    
    event_type VARCHAR(50) NOT NULL,
    -- 'daily_drawdown_warning', 'daily_drawdown_breach', 
    -- 'max_drawdown_warning', 'max_drawdown_breach',
    -- 'position_limit_hit', 'lot_size_exceeded',
    -- 'trading_hours_violation', 'news_restriction_violation'
    
    severity VARCHAR(10) NOT NULL, -- 'info', 'warning', 'critical'
    
    details JSONB NOT NULL,
    /* Example:
    {
        "current_value": -450.00,
        "limit_value": -500.00,
        "percentage": 90,
        "related_trade_id": "uuid",
        "action_taken": "warning_sent"
    }
    */
    
    action_taken VARCHAR(50),
    -- 'none', 'warning_sent', 'trade_rejected', 'positions_closed', 'account_failed'
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Daily Summary (for evaluation tracking)
CREATE TABLE daily_summaries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id UUID NOT NULL REFERENCES trading_accounts(id),
    trading_date DATE NOT NULL,
    
    -- Balance Tracking
    start_balance DECIMAL(15,2) NOT NULL,
    end_balance DECIMAL(15,2) NOT NULL,
    start_equity DECIMAL(15,2) NOT NULL,
    end_equity DECIMAL(15,2) NOT NULL,
    highest_equity DECIMAL(15,2) NOT NULL,
    lowest_equity DECIMAL(15,2) NOT NULL,
    
    -- P&L
    daily_pnl DECIMAL(15,2) NOT NULL,
    daily_pnl_pct DECIMAL(8,4) NOT NULL,
    
    -- Trading Activity
    trades_opened INTEGER NOT NULL DEFAULT 0,
    trades_closed INTEGER NOT NULL DEFAULT 0,
    total_lots DECIMAL(10,2) NOT NULL DEFAULT 0,
    is_trading_day BOOLEAN NOT NULL DEFAULT false,
    
    -- Drawdown
    max_daily_drawdown DECIMAL(15,2) NOT NULL,
    max_daily_drawdown_pct DECIMAL(8,4) NOT NULL,
    
    -- Consistency
    profit_contribution_pct DECIMAL(8,4), -- % of total profit from this day
    
    UNIQUE(account_id, trading_date),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Evaluation Results
CREATE TABLE evaluation_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id UUID NOT NULL REFERENCES trading_accounts(id),
    phase VARCHAR(20) NOT NULL,
    
    result VARCHAR(10) NOT NULL, -- 'passed', 'failed'
    
    -- Metrics at evaluation time
    metrics JSONB NOT NULL,
    /* Example:
    {
        "final_balance": 110000.00,
        "profit": 10000.00,
        "profit_pct": 10.0,
        "max_daily_drawdown": -3200.00,
        "max_daily_drawdown_pct": -3.2,
        "max_total_drawdown": -5100.00,
        "max_total_drawdown_pct": -5.1,
        "trading_days": 12,
        "total_trades": 45,
        "win_rate": 62.2,
        "profit_factor": 1.85,
        "sharpe_ratio": 1.42,
        "consistency_score": 78.5,
        "average_holding_time_minutes": 145,
        "instruments_traded": ["EURUSD", "GBPUSD", "XAUUSD"]
    }
    */
    
    failure_reasons JSONB, -- if failed
    /* Example:
    [
        {"rule": "max_daily_loss", "details": "Breached on 2024-01-15"},
        {"rule": "min_trading_days", "details": "Only 3 of required 5 days"}
    ]
    */
    
    evaluated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    evaluated_by VARCHAR(50) NOT NULL DEFAULT 'system' -- 'system' or admin user
);

-- Challenge Configuration (per firm - white label)
CREATE TABLE challenge_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    firm_id UUID NOT NULL REFERENCES firms(id),
    
    name VARCHAR(100) NOT NULL,
    type VARCHAR(50) NOT NULL, -- 'two_phase', 'one_phase', 'instant_funding'
    
    -- Account sizes available
    account_sizes JSONB NOT NULL, -- [10000, 25000, 50000, 100000, 200000]
    
    -- Phase configurations
    phases JSONB NOT NULL,
    /* Example:
    {
        "phase_1": {
            "profit_target_pct": 8,
            "max_daily_loss_pct": 5,
            "max_total_loss_pct": 10,
            "min_trading_days": 5,
            "max_calendar_days": 30,
            "drawdown_type": "balance_based"  // or "equity_based", "trailing"
        },
        "phase_2": {
            "profit_target_pct": 5,
            "max_daily_loss_pct": 5,
            "max_total_loss_pct": 10,
            "min_trading_days": 5,
            "max_calendar_days": 60,
            "drawdown_type": "balance_based"
        },
        "funded": {
            "max_daily_loss_pct": 5,
            "max_total_loss_pct": 10,
            "drawdown_type": "trailing",
            "profit_split": 80,
            "payout_frequency_days": 14,
            "first_payout_days": 30
        }
    }
    */
    
    -- Trading restrictions
    restrictions JSONB NOT NULL DEFAULT '{}',
    
    -- Scaling plan
    scaling_plan JSONB,
    /* Example:
    {
        "enabled": true,
        "conditions": {
            "min_profit_pct": 10,
            "min_months": 3,
            "consistent_profitability": true
        },
        "increase_pct": 25,
        "max_scale": 4  // 4x original size
    }
    */
    
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### 4.3 Real-Time Risk Calculation Engine

```python
# risk_engine.py - Core Risk Engine Implementation

import asyncio
from decimal import Decimal
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple
from enum import Enum
import redis.asyncio as redis


class BreachType(Enum):
    NONE = "none"
    SOFT = "soft"       # Warning
    HARD = "hard"       # Close positions
    CRITICAL = "critical"  # Fail account


class RiskCheckResult(Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    WARNING = "warning"


@dataclass
class AccountRiskState:
    """In-memory risk state for an account, cached in Redis"""
    account_id: str
    initial_balance: Decimal
    current_balance: Decimal
    current_equity: Decimal
    highest_balance: Decimal  # For trailing drawdown
    day_start_balance: Decimal
    day_start_equity: Decimal
    
    # Limits
    max_daily_loss_amount: Decimal
    max_total_loss_amount: Decimal
    max_lot_size: Decimal
    max_open_positions: int
    
    # Current state
    open_positions: Dict[str, 'Position'] = field(default_factory=dict)
    unrealized_pnl: Decimal = Decimal('0')
    realized_pnl_today: Decimal = Decimal('0')
    
    # Computed risk metrics
    @property
    def daily_pnl(self) -> Decimal:
        return (self.current_equity - self.day_start_equity)
    
    @property 
    def daily_drawdown(self) -> Decimal:
        return min(Decimal('0'), self.daily_pnl)
    
    @property
    def total_drawdown(self) -> Decimal:
        return self.current_equity - self.highest_balance
    
    @property
    def daily_drawdown_pct(self) -> Decimal:
        if self.day_start_balance == 0:
            return Decimal('0')
        return (self.daily_drawdown / self.day_start_balance) * 100
    
    @property
    def total_drawdown_pct(self) -> Decimal:
        if self.highest_balance == 0:
            return Decimal('0')
        return (self.total_drawdown / self.highest_balance) * 100


@dataclass
class Position:
    trade_id: str
    instrument: str
    direction: str  # 'BUY' or 'SELL'
    lot_size: Decimal
    open_price: Decimal
    current_price: Decimal
    unrealized_pnl: Decimal
    opened_at: datetime


@dataclass 
class OrderRequest:
    account_id: str
    instrument: str
    direction: str
    lot_size: Decimal
    price: Decimal
    order_type: str  # 'market', 'limit', 'stop'
    stop_loss: Optional[Decimal] = None
    take_profit: Optional[Decimal] = None


@dataclass
class RiskCheckResponse:
    result: RiskCheckResult
    checks_passed: List[str]
    checks_failed: List[str]
    warnings: List[str]
    details: Dict


class RealTimeRiskEngine:
    """
    Core real-time risk engine that performs pre-trade and post-trade 
    risk checks for prop firm evaluation accounts.
    """
    
    def __init__(self, redis_client: redis.Redis, config: dict):
        self.redis = redis_client
        self.config = config
        self._account_states: Dict[str, AccountRiskState] = {}
    
    async def load_account_state(self, account_id: str) -> AccountRiskState:
        """Load account risk state from Redis cache"""
        cache_key = f"risk:account:{account_id}"
        state_data = await self.redis.hgetall(cache_key)
        
        if not state_data:
            # Load from database and cache
            state = await self._load_from_db(account_id)
            await self._cache_state(state)
            return state
        
        return self._deserialize_state(state_data)
    
    async def pre_trade_check(self, order: OrderRequest) -> RiskCheckResponse:
        """
        Perform all pre-trade risk checks before allowing an order.
        This must be FAST (< 5ms target latency).
        """
        state = await self.load_account_state(order.account_id)
        
        checks_passed = []
        checks_failed = []
        warnings = []
        
        # 1. Account Status Check
        if not await self._check_account_active(state):
            checks_failed.append("account_not_active")
            return RiskCheckResponse(
                result=RiskCheckResult.REJECTED,
                checks_passed=checks_passed,
                checks_failed=checks_failed,
                warnings=warnings,
                details={"reason": "Account is not active"}
            )
        checks_passed.append("account_active")
        
        # 2. Daily Drawdown Check (would this trade potentially breach?)
        daily_dd_check = self._check_daily_drawdown(state, order)
        if daily_dd_check == BreachType.HARD:
            checks_failed.append("daily_drawdown_breach")
        elif daily_dd_check == BreachType.SOFT:
            warnings.append("daily_drawdown_warning_90pct")
            checks_passed.append("daily_drawdown")
        else:
            checks_passed.append("daily_drawdown")
        
        # 3. Max Drawdown Check
        max_dd_check = self._check_max_drawdown(state, order)
        if max_dd_check == BreachType.HARD:
            checks_failed.append("max_drawdown_breach")
        elif max_dd_check == BreachType.SOFT:
            warnings.append("max_drawdown_warning_90pct")
            checks_passed.append("max_drawdown")
        else:
            checks_passed.append("max_drawdown")
        
        # 4. Position Size Check
        if order.lot_size > state.max_lot_size:
            checks_failed.append("lot_size_exceeded")
        else:
            checks_passed.append("lot_size")
        
        # 5. Max Open Positions
        if len(state.open_positions) >= state.max_open_positions:
            checks_failed.append("max_positions_reached")
        else:
            checks_passed.append("open_positions")
        
        # 6. Instrument Restrictions
        instrument_check = await self._check_instrument_allowed(
            state.account_id, order.instrument
        )
        if not instrument_check:
            checks_failed.append("instrument_restricted")
        else:
            checks_passed.append("instrument_allowed")
        
        # 7. Trading Hours Check
        if not await self._check_trading_hours(state.account_id):
            checks_failed.append("outside_trading_hours")
        else:
            checks_passed.append("trading_hours")
        
        # 8. News Restriction Check
        if await self._check_news_restriction(state.account_id, order.instrument):
            checks_failed.append("news_restriction_active")
        else:
            checks_passed.append("news_check")
        
        # 9. Weekend Holding Check
        if await self._check_weekend_restriction(state.account_id, order):
            checks_failed.append("weekend_holding_restricted")
        else:
            checks_passed.append("weekend_check")
        
        # 10. Concentration Risk
        concentration = self._check_concentration_risk(state, order)
        if concentration == BreachType.HARD:
            checks_failed.append("concentration_risk_exceeded")
        elif concentration == BreachType.SOFT:
            warnings.append("high_concentration_risk")
            checks_passed.append("concentration_risk")
        else:
            checks_passed.append("concentration_risk")
        
        # Determine final result
        if checks_failed:
            result = RiskCheckResult.REJECTED
        elif warnings:
            result = RiskCheckResult.WARNING
        else:
            result = RiskCheckResult.APPROVED
        
        return RiskCheckResponse(
            result=result,
            checks_passed=checks_passed,
            checks_failed=checks_failed,
            warnings=warnings,
            details={
                "current_daily_dd": str(state.daily_drawdown),
                "current_total_dd": str(state.total_drawdown),
                "open_positions_count": len(state.open_positions),
            }
        )
    
    async def on_price_update(self, instrument: str, bid: Decimal, ask: Decimal):
        """
        Called on every price tick. Updates unrealized P&L and checks 
        for drawdown breaches across ALL accounts with open positions 
        in this instrument.
        """
        # Get all accounts with positions in this instrument
        account_ids = await self.redis.smembers(
            f"risk:instrument_accounts:{instrument}"
        )
        
        breach_actions = []
        
        for account_id in account_ids:
            account_id = account_id.decode() if isinstance(account_id, bytes) else account_id
            state = await self.load_account_state(account_id)
            
            # Update unrealized P&L for positions in this instrument
            for pos_id, position in state.open_positions.items():
                if position.instrument == instrument:
                    if position.direction == 'BUY':
                        position.current_price = bid
                        position.unrealized_pnl = (
                            (bid - position.open_price) * position.lot_size * 
                            self._get_contract_size(instrument)
                        )
                    else:
                        position.current_price = ask
                        position.unrealized_pnl = (
                            (position.open_price - ask) * position.lot_size * 
                            self._get_contract_size(instrument)
                        )
            
            # Recalculate equity
            total_unrealized = sum(
                p.unrealized_pnl for p in state.open_positions.values()
            )
            state.current_equity = state.current_balance + total_unrealized
            
            # Update highest balance (for trailing drawdown)
            if state.current_equity > state.highest_balance:
                state.highest_balance = state.current_equity
            
            # CHECK BREACHES
            # Daily drawdown breach
            if abs(state.daily_drawdown) >= state.max_daily_loss_amount:
                breach_actions.append({
                    'account_id': account_id,
                    'breach_type': 'daily_drawdown',
                    'value': str(state.daily_drawdown),
                    'limit': str(state.max_daily_loss_amount),
                    'action': 'liquidate_and_fail'
                })
            
            # Max drawdown breach
            if abs(state.total_drawdown) >= state.max_total_loss_amount:
                breach_actions.append({
                    'account_id': account_id,
                    'breach_type': 'max_drawdown',
                    'value': str(state.total_drawdown),
                    'limit': str(state.max_total_loss_amount),
                    'action': 'liquidate_and_fail'
                })
            
            # Update cache
            await self._cache_state(state)
        
        # Process breaches
        for breach in breach_actions:
            await self._handle_breach(breach)
    
    async def on_trade_closed(self, account_id: str, trade_id: str, 
                               realized_pnl: Decimal):
        """Called when a trade is closed. Updates account state."""
        state = await self.load_account_state(account_id)
        
        # Remove from open positions
        if trade_id in state.open_positions:
            del state.open_positions[trade_id]
        
        # Update balance
        state.current_balance += realized_pnl
        state.realized_pnl_today += realized_pnl
        
        # Recalculate equity
        total_unrealized = sum(
            p.unrealized_pnl for p in state.open_positions.values()
        )
        state.current_equity = state.current_balance + total_unrealized
        
        # Update highest balance
        if state.current_equity > state.highest_balance:
            state.highest_balance = state.current_equity
        
        await self._cache_state(state)
        
        # Publish trade closed event
        await self._publish_event('trade.closed', {
            'account_id': account_id,
            'trade_id': trade_id,
            'realized_pnl': str(realized_pnl),
            'current_balance': str(state.current_balance),
            'current_equity': str(state.current_equity),
        })
    
    def _check_daily_drawdown(self, state: AccountRiskState, 
                               order: OrderRequest) -> BreachType:
        """Check if daily drawdown limit is breached or near breach"""
        current_dd = abs(state.daily_drawdown)
        limit = state.max_daily_loss_amount
        
        if current_dd >= limit:
            return BreachType.HARD
        elif current_dd >= limit * Decimal('0.9'):
            return BreachType.SOFT
        return BreachType.NONE
    
    def _check_max_drawdown(self, state: AccountRiskState,
                             order: OrderRequest) -> BreachType:
        """Check if max total drawdown limit is breached"""
        current_dd = abs(state.total_drawdown)
        limit = state.max_total_loss_amount
        
        if current_dd >= limit:
            return BreachType.HARD
        elif current_dd >= limit * Decimal('0.9'):
            return BreachType.SOFT
        return BreachType.NONE
    
    async def _handle_breach(self, breach: dict):
        """Handle a risk breach - close positions and fail account"""
        account_id = breach['account_id']
        
        # 1. Immediately lock account (prevent new trades)
        await self.redis.set(f"risk:locked:{account_id}", "1")
        
        # 2. Send liquidation order
        await self._publish_event('risk.breach.liquidate', {
            'account_id': account_id,
            'breach_type': breach['breach_type'],
            'action': 'close_all_positions',
        })
        
        # 3. Publish breach event
        await self._publish_event('risk.breach', breach)
        
        # 4. Update account status (async via event)
        await self._publish_event('account.fail', {
            'account_id': account_id,
            'reason': breach['breach_type'],
            'details': breach,
        })
    
    async def daily_reset(self):
        """
        Called at the start of each trading day.
        Resets daily P&L tracking for all active accounts.
        """
        # This would be triggered by a scheduler (e.g., Temporal cron workflow)
        active_accounts = await self._get_all_active_accounts()
        
        for account_id in active_accounts:
            state = await self.load_account_state(account_id)
            state.day_start_balance = state.current_balance
            state.day_start_equity = state.current_equity
            state.realized_pnl_today = Decimal('0')
            await self._cache_state(state)
    
    # Helper methods
    async def _cache_state(self, state: AccountRiskState):
        """Cache account state in Redis for fast access"""
        cache_key = f"risk:account:{state.account_id}"
        await self.redis.hset(cache_key, mapping={
            'account_id': state.account_id,
            'initial_balance': str(state.initial_balance),
            'current_balance': str(state.current_balance),
            'current_equity': str(state.current_equity),
            'highest_balance': str(state.highest_balance),
            'day_start_balance': str(state.day_start_balance),
            'day_start_equity': str(state.day_start_equity),
            'max_daily_loss_amount': str(state.max_daily_loss_amount),
            'max_total_loss_amount': str(state.max_total_loss_amount),
            'max_lot_size': str(state.max_lot_size),
            'max_open_positions': str(state.max_open_positions),
            'realized_pnl_today': str(state.realized_pnl_today),
            'open_positions_count': str(len(state.open_positions)),
        })
        await self.redis.expire(cache_key, 86400)  # 24hr TTL
    
    async def _publish_event(self, topic: str, data: dict):
        """Publish event to message broker"""
        # Implementation depends on Kafka/Redpanda/NATS client
        pass
    
    def _get_contract_size(self, instrument: str) -> Decimal:
        """Get contract size for instrument (e.g., 100000 for forex)"""
        # This would be configurable
        contract_sizes = {
            'forex': Decimal('100000'),
            'indices': Decimal('1'),
            'commodities': Decimal('100'),
            'crypto': Decimal('1'),
        }
        instrument_type = self._get_instrument_type(instrument)
        return contract_sizes.get(instrument_type, Decimal('1'))
    
    async def _check_account_active(self, state: AccountRiskState) -> bool:
        locked = await self.redis.get(f"risk:locked:{state.account_id}")
        return locked is None
    
    async def _check_instrument_allowed(self, account_id: str, 
                                         instrument: str) -> bool:
        # Check against account restrictions
        restrictions = await self.redis.hget(
            f"risk:restrictions:{account_id}", 'allowed_instruments'
        )
        if restrictions:
            import json
            allowed = json.loads(restrictions)
            return instrument in allowed or len(allowed) == 0
        return True
    
    async def _check_trading_hours(self, account_id: str) -> bool:
        # Check if current time is within allowed trading hours
        return True  # Simplified
    
    async def _check_news_restriction(self, account_id: str, 
                                       instrument: str) -> bool:
        # Check if there's a news event within restricted window
        return False  # Simplified
    
    async def _check_weekend_restriction(self, account_id: str,
                                          order: OrderRequest) -> bool:
        # Check if weekend holding is restricted
        return False  # Simplified
    
    def _check_concentration_risk(self, state: AccountRiskState,
                                   order: OrderRequest) -> BreachType:
        # Check if too much exposure in one instrument
        return BreachType.NONE  # Simplified
```

---

## 5. Data Pipeline Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                         DATA PIPELINE ARCHITECTURE                           │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │                    REAL-TIME PIPELINE (Hot Path)                       │  │
│  │                                                                        │  │
│  │  MT4/MT5 ──┐                                                          │  │
│  │  cTrader ──┼──▶ Broker Gateway ──▶ Kafka ──▶ Flink ──┐              │  │
│  │  Exchange ─┘    (FIX/API)         Topics    Stream    │              │  │
│  │                                              Proc     │              │  │
│  │                                                       ▼              │  │
│  │                                              ┌──────────────┐        │  │
│  │                                              │ Risk Engine  │        │  │
│  │                                              │ (< 5ms)      │        │  │
│  │                                              └──────┬───────┘        │  │
│  │                                                     │                │  │
│  │                                              ┌──────▼───────┐        │  │
│  │                                              │ Redis/       │        │  │
│  │                                              │ Dragonfly    │        │  │
│  │                                              │ (State)      │        │  │
│  │                                              └──────────────┘        │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │                    NEAR REAL-TIME PIPELINE (Warm Path)                 │  │
│  │                                                                        │  │
│  │  Kafka ──▶ Flink/Kafka Streams ──▶ ┌──────────────────┐              │  │
│  │            (Windowed Aggregations)  │ TimescaleDB      │              │  │
│  │                                     │ (Trade History)  │              │  │
│  │  Computations:                      └──────────────────┘              │  │
│  │  • 1-min P&L aggregation                                              │  │
│  │  • Rolling drawdown                 ┌──────────────────┐              │  │
│  │  • Position exposure updates        │ PostgreSQL       │              │  │
│  │  • Daily P&L snapshots             │ (Account State)  │              │  │
│  │  • Trading day detection            └──────────────────┘              │  │
│  │                                                                        │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │                    BATCH PIPELINE (Cold Path)                          │  │
│  │                                                                        │  │
│  │  ┌────────────┐    ┌────────────────┐    ┌──────────────────┐        │  │
│  │  │ TimescaleDB │──▶│ Apache Spark / │──▶│ ClickHouse       │        │  │
│  │  │ PostgreSQL  │   │ dbt            │   │ (Analytics OLAP) │        │  │
│  │  └────────────┘    └────────────────┘    └──────────────────┘        │  │
│  │                                                                        │  │
│  │  Computations:                          ┌──────────────────┐         │  │
│  │  • End-of-day summaries                │ S3 / MinIO       │         │  │
│  │  • Performance metrics calculation     │ (Data Lake)      │         │  │
│  │  • Fraud pattern analysis              └──────────────────┘         │  │
│  │  • Copy trade correlation                                            │  │
│  │  • Consistency scoring                  ┌──────────────────┐         │  │
│  │  • Behavioral profiling                │ ML Feature Store │         │  │
│  │  • Reporting & compliance              │ (Feast)          │         │  │
│  │                                         └──────────────────┘         │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Risk Models & Algorithms

### 6.1 Drawdown Calculation Models

```python
# drawdown_models.py

from enum import Enum
from decimal import Decimal
from typing import List, Tuple
from dataclasses import dataclass


class DrawdownType(Enum):
    """
    Different drawdown calculation methods used by prop firms.
    Each firm may use different methods - must be configurable.
    """
    BALANCE_BASED = "balance_based"
    EQUITY_BASED = "equity_based" 
    TRAILING = "trailing"
    STATIC = "static"


class DrawdownCalculator:
    """
    Implements various drawdown calculation methods.
    
    Balance-Based: DD calculated from starting balance
    Equity-Based: DD calculated including unrealized P&L
    Trailing: DD limit moves up with account high-water mark
    Static: Fixed dollar amount below initial balance
    """
    
    @staticmethod
    def calculate_daily_drawdown(
        drawdown_type: DrawdownType,
        day_start_balance: Decimal,
        day_start_equity: Decimal,
        current_balance: Decimal,
        current_equity: Decimal,
        initial_balance: Decimal,
    ) -> Tuple[Decimal, Decimal]:
        """
        Returns (drawdown_amount, drawdown_percentage)
        """
        if drawdown_type == DrawdownType.BALANCE_BASED:
            # Drawdown = current_balance - day_start_balance
            dd = current_balance - day_start_balance
            dd_pct = (dd / day_start_balance) * 100 if day_start_balance else Decimal('0')
            return (dd, dd_pct)
        
        elif drawdown_type == DrawdownType.EQUITY_BASED:
            # Drawdown = current_equity - day_start_equity 
            # (includes unrealized P&L)
            dd = current_equity - day_start_equity
            dd_pct = (dd / day_start_equity) * 100 if day_start_equity else Decimal('0')
            return (dd, dd_pct)
        
        elif drawdown_type == DrawdownType.TRAILING:
            # Daily drawdown for trailing is still from day start
            dd = current_equity - day_start_equity
            dd_pct = (dd / day_start_equity) * 100 if day_start_equity else Decimal('0')
            return (dd, dd_pct)
        
        elif drawdown_type == DrawdownType.STATIC:
            # Static from initial balance
            dd = current_equity - initial_balance
            dd_pct = (dd / initial_balance) * 100 if initial_balance else Decimal('0')
            return (dd, dd_pct)
    
    @staticmethod
    def calculate_max_drawdown(
        drawdown_type: DrawdownType,
        initial_balance: Decimal,
        current_equity: Decimal,
        highest_equity: Decimal,
        max_loss_pct: Decimal,
    ) -> Tuple[Decimal, Decimal, Decimal]:
        """
        Returns (current_drawdown, drawdown_limit, remaining_before_breach)
        """
        if drawdown_type == DrawdownType.BALANCE_BASED:
            # Max DD from initial balance
            dd_limit = initial_balance * (max_loss_pct / 100)
            current_dd = max(Decimal('0'), initial_balance - current_equity)
            remaining = dd_limit - current_dd
            return (current_dd, dd_limit, remaining)
        
        elif drawdown_type == DrawdownType.EQUITY_BASED:
            # Max DD from initial balance, but tracks equity
            dd_limit = initial_balance * (max_loss_pct / 100)
            current_dd = max(Decimal('0'), initial_balance - current_equity)
            remaining = dd_limit - current_dd
            return (current_dd, dd_limit, remaining)
        
        elif drawdown_type == DrawdownType.TRAILING:
            # TRAILING: The loss limit trails up with profits
            # Example: $100k account, 10% max DD
            # If equity reaches $105k, new floor = $105k - $10k = $95k
            # The floor never goes down, only up
            dd_limit = highest_equity * (max_loss_pct / 100)
            current_dd = max(Decimal('0'), highest_equity - current_equity)
            remaining = dd_limit - current_dd
            
            # Important: for trailing, once the floor reaches initial_balance,
            # it locks there (some firms do this)
            floor = highest_equity - dd_limit
            if floor > initial_balance:
                # Cap: floor doesn't go above initial balance (varies by firm)
                pass  # This is firm-specific configuration
            
            return (current_dd, dd_limit, remaining)
        
        elif drawdown_type == DrawdownType.STATIC:
            dd_limit = initial_balance * (max_loss_pct / 100)
            current_dd = max(Decimal('0'), initial_balance - current_equity)
            remaining = dd_limit - current_dd
            return (current_dd, dd_limit, remaining)


class ConsistencyScorer:
    """
    Calculates consistency scores for prop firm evaluation.
    
    Consistency Rule: No single day's profit should exceed X% of total profit.
    This prevents "all-in" gambling behavior.
    """
    
    @staticmethod
    def calculate_consistency_score(
        daily_pnls: List[Decimal],
        max_single_day_contribution_pct: Decimal = Decimal('40')
    ) -> Tuple[Decimal, bool, List[dict]]:
        """
        Returns (consistency_score, passes_rule, violations)
        """
        total_profit = sum(pnl for pnl in daily_pnls if pnl > 0)
        
        if total_profit == Decimal('0'):
            return (Decimal('0'), True, [])
        
        violations = []
        daily_contributions = []
        
        for i, pnl in enumerate(daily_pnls):
            if pnl > 0:
                contribution_pct = (pnl / total_profit) * 100
                daily_contributions.append(contribution_pct)
                
                if contribution_pct > max_single_day_contribution_pct:
                    violations.append({
                        'day_index': i,
                        'pnl': str(pnl),
                        'contribution_pct': str(contribution_pct),
                        'limit_pct': str(max_single_day_contribution_pct)
                    })
        
        # Score: lower variance in contributions = higher consistency
        if daily_contributions:
            avg = sum(daily_contributions) / len(daily_contributions)
            variance = sum((c - avg) ** 2 for c in daily_contributions) / len(daily_contributions)
            # Normalize to 0-100 score
            consistency_score = max(Decimal('0'), 
                                   Decimal('100') - (variance / Decimal('10')))
        else:
            consistency_score = Decimal('0')
        
        passes = len(violations) == 0
        return (consistency_score, passes, violations)


class PerformanceMetrics:
    """Calculate standard trading performance metrics"""
    
    @staticmethod
    def sharpe_ratio(returns: List[Decimal], risk_free_rate: Decimal = Decimal('0')) -> Decimal:
        if not returns or len(returns) < 2:
            return Decimal('0')
        
        avg_return = sum(returns) / len(returns)
        excess_returns = [r - risk_free_rate / 252 for r in returns]  # daily
        avg_excess = sum(excess_returns) / len(excess_returns)
        
        variance = sum((r - avg_excess) ** 2 for r in excess_returns) / (len(excess_returns) - 1)
        std_dev = variance ** Decimal('0.5')
        
        if std_dev == 0:
            return Decimal('0')
        
        return (avg_excess / std_dev) * Decimal('252').sqrt()  # Annualized
    
    @staticmethod
    def sortino_ratio(returns: List[Decimal], risk_free_rate: Decimal = Decimal('0')) -> Decimal:
        if not returns or len(returns) < 2:
            return Decimal('0')
        
        avg_return = sum(returns) / len(returns)
        downside_returns = [min(r - risk_free_rate / 252, Decimal('0')) for r in returns]
        downside_variance = sum(r ** 2 for r in downside_returns) / len(downside_returns)
        downside_dev = downside_variance ** Decimal('0.5')
        
        if downside_dev == 0:
            return Decimal('0')
        
        return ((avg_return - risk_free_rate / 252) / downside_dev) * Decimal('252').sqrt()
    
    @staticmethod
    def profit_factor(winning_trades: List[Decimal], losing_trades: List[Decimal]) -> Decimal:
        total_wins = sum(abs(w) for w in winning_trades) if winning_trades else Decimal('0')
        total_losses = sum(abs(l) for l in losing_trades) if losing_trades else Decimal('1')
        
        return total_wins / total_losses if total_losses != 0 else Decimal('999')
    
    @staticmethod
    def max_consecutive_losses(trade_results: List[Decimal]) -> int:
        max_streak = 0
        current_streak = 0
        
        for result in trade_results:
            if result < 0:
                current_streak += 1
                max_streak = max(max_streak, current_streak)
            else:
                current_streak = 0
        
        return max_streak
    
    @staticmethod
    def calculate_all_metrics(trades: List[dict]) -> dict:
        """Calculate comprehensive performance metrics"""
        if not trades:
            return {}
        
        returns = [Decimal(str(t['pnl'])) for t in trades if t.get('pnl') is not None]
        winning = [r for r in returns if r > 0]
        losing = [r for r in returns if r < 0]
        
        total_pnl = sum(returns)
        win_rate = len(winning) / len(returns) * 100 if returns else 0
        
        avg_win = sum(winning) / len(winning) if winning else Decimal('0')
        avg_loss = sum(abs(l) for l in losing) / len(losing) if losing else Decimal('0')
        
        risk_reward = avg_win / avg_loss if avg_loss != 0 else Decimal('999')
        
        expectancy = (
            (Decimal(str(win_rate / 100)) * avg_win) - 
            (Decimal(str((100 - win_rate) / 100)) * avg_loss)
        )
        
        return {
            'total_trades': len(returns),
            'winning_trades': len(winning),
            'losing_trades': len(losing),
            'total_pnl': str(total_pnl),
            'win_rate': f"{win_rate:.2f}",
            'average_win': str(avg_win),
            'average_loss': str(avg_loss),
            'risk_reward_ratio': str(risk_reward),
            'profit_factor': str(PerformanceMetrics.profit_factor(winning, losing)),
            'expectancy': str(expectancy),
            'max_consecutive_losses': PerformanceMetrics.max_consecutive_losses(returns),
            'sharpe_ratio': str(PerformanceMetrics.sharpe_ratio(returns)),
            'sortino_ratio': str(PerformanceMetrics.sortino_ratio(returns)),
        }
```

### 6.2 Fraud & Abuse Detection

```python
# fraud_detection.py

import numpy as np
from typing import List, Dict, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from collections import defaultdict


@dataclass
class TradeSignature:
    """Compact representation of a trade for pattern matching"""
    account_id: str
    instrument: str
    direction: str
    lot_size: float
    open_time: datetime
    close_time: datetime
    duration_seconds: int
    pnl: float
    open_price: float
    close_price: float


class CopyTradeDetector:
    """
    Detects copy trading between accounts.
    
    Methods:
    1. Time-based correlation: trades opened within X seconds
    2. Instrument+Direction correlation: same trades, same time
    3. Statistical correlation of P&L curves
    4. IP/Device correlation (complementary signal)
    """
    
    def __init__(self, time_window_seconds: int = 5):
        self.time_window = time_window_seconds
    
    def detect_correlated_accounts(
        self,
        all_trades: Dict[str, List[TradeSignature]]
    ) -> List[Dict]:
        """
        Input: {account_id: [trades]}
        Output: List of suspected copy-trade pairs with confidence
        """
        suspects = []
        account_ids = list(all_trades.keys())
        
        for i in range(len(account_ids)):
            for j in range(i + 1, len(account_ids)):
                acc_a = account_ids[i]
                acc_b = account_ids[j]
                
                correlation = self._calculate_trade_correlation(
                    all_trades[acc_a], all_trades[acc_b]
                )
                
                if correlation['score'] > 0.7:  # Threshold
                    suspects.append({
                        'account_a': acc_a,
                        'account_b': acc_b,
                        'correlation_score': correlation['score'],
                        'matching_trades': correlation['matching_count'],
                        'total_trades': correlation['total_trades'],
                        'time_correlation': correlation['time_corr'],
                        'instrument_correlation': correlation['instrument_corr'],
                    })
        
        return suspects
    
    def _calculate_trade_correlation(
        self,
        trades_a: List[TradeSignature],
        trades_b: List[TradeSignature]
    ) -> Dict:
        matching_count = 0
        
        for ta in trades_a:
            for tb in trades_b:
                time_diff = abs((ta.open_time - tb.open_time).total_seconds())
                
                if (time_diff <= self.time_window and 
                    ta.instrument == tb.instrument and
                    ta.direction == tb.direction):
                    matching_count += 1
                    break
        
        total = max(len(trades_a), len(trades_b))
        score = matching_count / total if total > 0 else 0
        
        return {
            'score': score,
            'matching_count': matching_count,
            'total_trades': total,
            'time_corr': score,
            'instrument_corr': score,
        }


class MartingaleDetector:
    """
    Detects martingale/grid trading strategies.
    
    Pattern: Doubling position size after losses
    """
    
    @staticmethod
    def detect(trades: List[TradeSignature], 
               multiplier_threshold: float = 1.8) -> Dict:
        """Detect martingale patterns"""
        if len(trades) < 3:
            return {'detected': False, 'confidence': 0}
        
        # Sort by time
        sorted_trades = sorted(trades, key=lambda t: t.open_time)
        
        # Look for doubling pattern after losses
        martingale_sequences = []
        current_sequence = []
        
        for i in range(1, len(sorted_trades)):
            prev = sorted_trades[i - 1]
            curr = sorted_trades[i]
            
            # Same instrument, same direction (or opposite for hedging variant)
            if (prev.instrument == curr.instrument and
                prev.pnl < 0 and
                curr.lot_size >= prev.lot_size * multiplier_threshold):
                current_sequence.append((prev, curr))
            else:
                if len(current_sequence) >= 2:
                    martingale_sequences.append(current_sequence)
                current_sequence = []
        
        if len(current_sequence) >= 2:
            martingale_sequences.append(current_sequence)
        
        is_detected = len(martingale_sequences) > 0
        confidence = min(1.0, len(martingale_sequences) * 0.3) if is_detected else 0
        
        return {
            'detected': is_detected,
            'confidence': confidence,
            'sequences_found': len(martingale_sequences),
            'details': [
                {
                    'length': len(seq),
                    'instrument': seq[0][0].instrument,
                    'size_progression': [t[1].lot_size for t in seq]
                }
                for seq in martingale_sequences
            ]
        }


class LatencyArbitrageDetector:
    """
    Detects latency arbitrage / tick scalping.
    
    Pattern: Very short holding times, trading on price feed delays
    """
    
    @staticmethod
    def detect(trades: List[TradeSignature],
               min_trade_duration_seconds: int = 30,
               win_rate_threshold: float = 85) -> Dict:
        """Detect latency arbitrage patterns"""
        if len(trades) < 10:
            return {'detected': False, 'confidence': 0}
        
        short_trades = [t for t in trades if t.duration_seconds < min_trade_duration_seconds]
        
        if not short_trades:
            return {'detected': False, 'confidence': 0}
        
        short_trade_pct = len(short_trades) / len(trades) * 100
        
        # Check win rate of short trades
        short_wins = len([t for t in short_trades if t.pnl > 0])
        short_win_rate = short_wins / len(short_trades) * 100 if short_trades else 0
        
        # High % of short trades + high win rate = suspicious
        is_detected = (
            short_trade_pct > 50 and 
            short_win_rate > win_rate_threshold
        )
        
        confidence = min(1.0, (short_trade_pct / 100) * (short_win_rate / 100))
        
        return {
            'detected': is_detected,
            'confidence': confidence,
            'short_trade_percentage': short_trade_pct,
            'short_trade_win_rate': short_win_rate,
            'avg_duration_seconds': (
                sum(t.duration_seconds for t in short_trades) / len(short_trades)
                if short_trades else 0
            ),
            'total_short_trades': len(short_trades),
        }


class NewsStraddleDetector:
    """
    Detects news straddling strategy.
    
    Pattern: Opening opposing positions (buy and sell) just before 
    high-impact news to capture the spike in either direction.
    """
    
    def __init__(self, news_events: List[Dict]):
        """news_events: [{time: datetime, instrument: str, impact: str}]"""
        self.news_events = news_events
    
    def detect(self, trades: List[TradeSignature],
               window_minutes: int = 5) -> Dict:
        """Detect news straddle patterns"""
        straddle_instances = []
        
        for event in self.news_events:
            event_time = event['time']
            window_start = event_time - timedelta(minutes=window_minutes)
            window_end = event_time + timedelta(minutes=1)  # slightly after
            
            # Find trades opened in the window
            window_trades = [
                t for t in trades
                if window_start <= t.open_time <= window_end
            ]
            
            # Check for opposing positions
            buys = [t for t in window_trades if t.direction == 'BUY']
            sells = [t for t in window_trades if t.direction == 'SELL']
            
            if buys and sells:
                # Check if same or correlated instruments
                buy_instruments = set(t.instrument for t in buys)
                sell_instruments = set(t.instrument for t in sells)
                
                if buy_instruments & sell_instruments:  # Same instrument
                    straddle_instances.append({
                        'news_event': event,
                        'buy_trades': len(buys),
                        'sell_trades': len(sells),
                        'instruments': list(buy_instruments & sell_instruments)
                    })
        
        return {
            'detected': len(straddle_instances) > 0,
            'instances': straddle_instances,
            'confidence': min(1.0, len(straddle_instances) * 0.25),
        }
```

---

## 7. Evaluation Engine Design

### 7.1 Challenge Evaluation State Machine

```
┌─────────────────────────────────────────────────────────────────────┐
│                CHALLENGE STATE MACHINE                                │
│                                                                      │
│  ┌──────────┐     ┌──────────────┐     ┌──────────────┐            │
│  │ CREATED  │────▶│  PHASE 1     │────▶│  PHASE 1     │            │
│  │          │     │  ACTIVE      │     │  EVALUATING  │            │
│  └──────────┘     └──────┬───────┘     └──────┬───────┘            │
│                          │                     │                     │
│                     ┌────▼─────┐          ┌────▼──────┐             │
│                     │ BREACH   │          │ TARGET    │             │
│                     │ DETECTED │          │ REACHED   │             │
│                     └────┬─────┘          └────┬──────┘             │
│                          │                     │                     │
│                     ┌────▼─────┐          ┌────▼──────────┐        │
│                     │ FAILED   │          │ MIN DAYS MET? │        │
│                     │          │          └────┬──────────┘        │
│                     └──────────┘               │                    │
│                                           YES  │  NO               │
│                                    ┌───────────┘  │               │
│                                    │              ┌▼──────────┐    │
│                                    │              │ WAIT FOR   │    │
│                                    │              │ MIN DAYS   │    │
│                                    │              └──┬─────────┘    │
│                                    │                 │              │
│                               ┌────▼──────────┐     │              │
│                               │ CONSISTENCY   │◀────┘              │
│                               │ CHECK         │                    │
│                               └────┬──────────┘                    │
│                                    │                                │
│                               PASS │  FAIL                         │
│                          ┌─────────┘  │                            │
│                          │       ┌────▼──────┐                     │
│                     ┌────▼────┐  │ FAILED    │                     │
│                     │ PHASE 1 │  │           │                     │
│                     │ PASSED  │  └───────────┘                     │
│                     └────┬────┘                                     │
│                          │                                          │
│                     ┌────▼──────────┐                               │
│                     │  PHASE 2      │                               │
│                     │  ACTIVE       │  (Same flow as Phase 1)      │
│                     └────┬──────────┘                               │
│                          │                                          │
│                     ┌────▼──────────┐                               │
│                     │  PHASE 2      │                               │
│                     │  PASSED       │                               │
│                     └────┬──────────┘                               │
│                          │                                          │
│                     ┌────▼──────────┐                               │
│                     │  FUNDED       │                               │
│                     │  ACCOUNT      │                               │
│                     └────┬──────────┘                               │
│                          │                                          │
│                     ┌────▼──────────┐                               │
│                     │  SCALING      │                               │
│                     │  PLAN         │                               │
│                     └───────────────┘                               │
└─────────────────────────────────────────────────────────────────────┘
```

### 7.2 Evaluation Engine Implementation

```python
# evaluation_engine.py

from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from datetime import datetime, date, timedelta
from enum import Enum
import json


class ChallengePhase(Enum):
    PHASE_1 = "phase_1"
    PHASE_2 = "phase_2"
    FUNDED = "funded"
    SCALING_1 = "scaling_1"
    SCALING_2 = "scaling_2"


class EvaluationResult(Enum):
    IN_PROGRESS = "in_progress"
    PASSED = "passed"
    FAILED = "failed"
    PENDING_REVIEW = "pending_review"


@dataclass
class PhaseConfig:
    profit_target_pct: Decimal
    max_daily_loss_pct: Decimal
    max_total_loss_pct: Decimal
    min_trading_days: int
    max_calendar_days: Optional[int]  # None = unlimited
    drawdown_type: str  # 'balance_based', 'equity_based', 'trailing'
    consistency_rule_enabled: bool
    max_single_day_profit_pct: Decimal  # For consistency rule
    profit_split_pct: Optional[Decimal]  # Only for funded phase


@dataclass
class EvaluationState:
    account_id: str
    phase: ChallengePhase
    config: PhaseConfig
    
    # Current metrics
    initial_balance: Decimal
    current_balance: Decimal
    current_equity: Decimal
    highest_balance: Decimal
    
    # Progress tracking
    current_profit_pct: Decimal
    trading_days: int
    calendar_days: int
    start_date: date
    
    # Drawdown tracking
    max_daily_drawdown_hit: Decimal
    max_total_drawdown_hit: Decimal
    
    # Daily P&L history
    daily_pnls: List[Decimal]
    
    # Status
    is_breached: bool
    breach_type: Optional[str]


class EvaluationEngine:
    """
    Evaluates trader performance against challenge rules.
    Determines if a trader passes or fails each phase.
    """
    
    def __init__(self, db_session, redis_client, event_publisher):
        self.db = db_session
        self.redis = redis_client
        self.events = event_publisher
    
    async def evaluate_account(self, account_id: str) -> Dict:
        """
        Run full evaluation on an account.
        Called periodically and on-demand.
        """
        state = await self._load_evaluation_state(account_id)
        
        if state.is_breached:
            return await self._handle_failure(state)
        
        # Check all evaluation criteria
        results = {
            'profit_target': self._check_profit_target(state),
            'daily_drawdown': self._check_daily_drawdown_history(state),
            'max_drawdown': self._check_max_drawdown_history(state),
            'min_trading_days': self._check_min_trading_days(state),
            'time_limit': self._check_time_limit(state),
            'consistency': self._check_consistency(state),
        }
        
        # Determine overall result
        all_mandatory_passed = all([
            results['daily_drawdown']['passed'],
            results['max_drawdown']['passed'],
        ])
        
        if not all_mandatory_passed:
            # Immediate failure conditions
            return await self._handle_failure(state, results)
        
        # Check if all pass conditions are met
        profit_target_met = results['profit_target']['met']
        min_days_met = results['min_trading_days']['met']
        time_expired = results['time_limit'].get('expired', False)
        consistency_passed = results['consistency']['passed']
        
        if profit_target_met and min_days_met and consistency_passed:
            return await self._handle_pass(state, results)
        
        if time_expired and not profit_target_met:
            return await self._handle_failure(state, results)
        
        # Still in progress
        return {
            'status': EvaluationResult.IN_PROGRESS.value,
            'progress': {
                'profit_progress_pct': str(
                    (state.current_profit_pct / state.config.profit_target_pct) * 100
                ),
                'trading_days_progress': f"{state.trading_days}/{state.config.min_trading_days}",
                'days_remaining': self._calculate_days_remaining(state),
            },
            'results': results,
        }
    
    def _check_profit_target(self, state: EvaluationState) -> Dict:
        """Check if profit target is reached"""
        target = state.config.profit_target_pct
        current = state.current_profit_pct
        
        return {
            'met': current >= target,
            'target_pct': str(target),
            'current_pct': str(current),
            'remaining_pct': str(max(Decimal('0'), target - current)),
            'target_amount': str(state.initial_balance * target / 100),
            'current_profit': str(state.current_balance - state.initial_balance),
        }
    
    def _check_daily_drawdown_history(self, state: EvaluationState) -> Dict:
        """Check if daily drawdown was ever breached"""
        limit = state.config.max_daily_loss_pct
        worst = state.max_daily_drawdown_hit
        
        return {
            'passed': abs(worst) < limit,
            'limit_pct': str(limit),
            'worst_daily_dd_pct': str(worst),
        }
    
    def _check_max_drawdown_history(self, state: EvaluationState) -> Dict:
        """Check if max drawdown was ever breached"""
        limit = state.config.max_total_loss_pct
        worst = state.max_total_drawdown_hit
        
        return {
            'passed': abs(worst) < limit,
            'limit_pct': str(limit),
            'worst_total_dd_pct': str(worst),
        }
    
    def _check_min_trading_days(self, state: EvaluationState) -> Dict:
        """Check if minimum trading days requirement is met"""
        required = state.config.min_trading_days
        actual = state.trading_days
        
        return {
            'met': actual >= required,
            'required': required,
            'actual': actual,
            'remaining': max(0, required - actual),
        }
    
    def _check_time_limit(self, state: EvaluationState) -> Dict:
        """Check if time limit has expired"""
        if state.config.max_calendar_days is None:
            return {'expired': False, 'unlimited': True}
        
        elapsed = (date.today() - state.start_date).days
        remaining = state.config.max_calendar_days - elapsed
        
        return {
            'expired': remaining <= 0,
            'total_days': state.config.max_calendar_days,
            'elapsed_days': elapsed,
            'remaining_days': max(0, remaining),
        }
    
    def _check_consistency(self, state: EvaluationState) -> Dict:
        """Check consistency rule"""
        if not state.config.consistency_rule_enabled:
            return {'passed': True, 'enabled': False}
        
        total_profit = sum(pnl for pnl in state.daily_pnls if pnl > 0)
        
        if total_profit <= 0:
            return {'passed': True, 'no_profits': True}
        
        violations = []
        for i, pnl in enumerate(state.daily_pnls):
            if pnl > 0:
                contribution = (pnl / total_profit) * 100
                if contribution > state.config.max_single_day_profit_pct:
                    violations.append({
                        'day': i + 1,
                        'pnl': str(pnl),
                        'contribution_pct': str(contribution),
                    })
        
        return {
            'passed': len(violations) == 0,
            'enabled': True,
            'max_allowed_pct': str(state.config.max_single_day_profit_pct),
            'violations': violations,
        }
    
    async def _handle_pass(self, state: EvaluationState, results: Dict) -> Dict:
        """Handle phase passed"""
        next_phase = self._get_next_phase(state.phase)
        
        # Publish events
        await self.events.publish('evaluation.passed', {
            'account_id': state.account_id,
            'phase': state.phase.value,
            'next_phase': next_phase.value if next_phase else 'funded',
            'results': results,
        })
        
        # Update database
        await self._update_account_phase(state.account_id, next_phase)
        
        return {
            'status': EvaluationResult.PASSED.value,
            'phase': state.phase.value,
            'next_phase': next_phase.value if next_phase else 'funded',
            'results': results,
        }
    
    async def _handle_failure(self, state: EvaluationState, 
                               results: Optional[Dict] = None) -> Dict:
        """Handle phase failed"""
        await self.events.publish('evaluation.failed', {
            'account_id': state.account_id,
            'phase': state.phase.value,
            'breach_type': state.breach_type,
            'results': results,
        })
        
        await self._update_account_status(state.account_id, 'failed')
        
        return {
            'status': EvaluationResult.FAILED.value,
            'phase': state.phase.value,
            'breach_type': state.breach_type,
            'results': results,
        }
    
    def _get_next_phase(self, current: ChallengePhase) -> Optional[ChallengePhase]:
        phase_order = {
            ChallengePhase.PHASE_1: ChallengePhase.PHASE_2,
            ChallengePhase.PHASE_2: ChallengePhase.FUNDED,
            ChallengePhase.FUNDED: ChallengePhase.SCALING_1,
        }
        return phase_order.get(current)
    
    def _calculate_days_remaining(self, state: EvaluationState) -> Optional[int]:
        if state.config.max_calendar_days is None:
            return None
        elapsed = (date.today() - state.start_date).days
        return max(0, state.config.max_calendar_days - elapsed)
    
    # Payout calculation for funded accounts
    async def calculate_payout(self, account_id: str) -> Dict:
        """Calculate payout for funded account"""
        state = await self._load_evaluation_state(account_id)
        
        if state.phase not in [ChallengePhase.FUNDED, 
                                ChallengePhase.SCALING_1,
                                ChallengePhase.SCALING_2]:
            return {'eligible': False, 'reason': 'Not a funded account'}
        
        profit = max(Decimal('0'), state.current_balance - state.initial_balance)
        
        if profit <= 0:
            return {'eligible': False, 'reason': 'No profit to distribute'}
        
        split_pct = state.config.profit_split_pct or Decimal('80')
        trader_share = profit * (split_pct / 100)
        firm_share = profit - trader_share
        
        return {
            'eligible': True,
            'total_profit': str(profit),
            'trader_split_pct': str(split_pct),
            'trader_payout': str(trader_share),
            'firm_share': str(firm_share),
            'account_balance_after': str(state.initial_balance),  # Reset to initial
        }
```

---

## 8. Technology Stack Recommendations

### 8.1 Recommended Stack (Production-Grade)

```
┌──────────────────────────────────────────────────────────────────────┐
│                    RECOMMENDED TECHNOLOGY STACK                       │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ LANGUAGE & FRAMEWORKS                                        │   │
│  │                                                              │   │
│  │ Primary:  Go (Golang)                                        │   │
│  │   - Risk Engine (ultra-low latency)                         │   │
│  │   - Broker Gateway Services                                 │   │
│  │   - Pre-trade validation service                            │   │
│  │                                                              │   │
│  │ Secondary: Python                                            │   │
│  │   - Evaluation Engine                                       │   │
│  │   - Analytics & ML pipelines                                │   │
│  │   - Fraud detection models                                  │   │
│  │   - Administrative APIs (FastAPI)                           │   │
│  │                                                              │   │
│  │ Alternative: Rust (if ultra-low latency needed)             │   │
│  │ Alternative: Java/Kotlin (if Drools rule engine chosen)     │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ DATA INFRASTRUCTURE                                          │   │
│  │                                                              │   │
│  │ Event Streaming:  Redpanda (Kafka-compatible, simpler ops)  │   │
│  │ Cache/State:      Dragonfly (Redis-compatible, faster)      │   │
│  │ Primary DB:       PostgreSQL 16                             │   │
│  │ Time-Series:      TimescaleDB (PostgreSQL extension)        │   │
│  │ Analytics OLAP:   ClickHouse                                │   │
│  │ Search:           OpenSearch (for trade search/audit)       │   │
│  │ Object Storage:   MinIO (S3-compatible)                     │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ PROCESSING & ORCHESTRATION                                   │   │
│  │                                                              │   │
│  │ Stream Processing: Apache Flink                              │   │
│  │ Workflow Engine:   Temporal.io                               │   │
│  │ Rule Engine:       OPA (Rego) + Custom Go rules             │   │
│  │ Task Queue:        Asynq (Go) or BullMQ (Node.js)          │   │
│  │ Batch Processing:  dbt + ClickHouse                         │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ API & COMMUNICATION                                          │   │
│  │                                                              │   │
│  │ API Gateway:      Kong or APISIX                            │   │
│  │ REST API:         Go (Gin/Echo) + Python (FastAPI)          │   │
│  │ WebSocket:        Go native or Socket.io                    │   │
│  │ Inter-service:    gRPC (Protobuf)                           │   │
│  │ Notifications:    Novu (open-source)                        │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ OBSERVABILITY                                                │   │
│  │                                                              │   │
│  │ Metrics:          Prometheus + VictoriaMetrics               │   │
│  │ Dashboards:       Grafana                                    │   │
│  │ Tracing:          OpenTelemetry + Jaeger                    │   │
│  │ Logging:          Loki + Grafana                            │   │
│  │ Alerting:         Grafana Alerting + PagerDuty              │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ INFRASTRUCTURE                                               │   │
│  │                                                              │   │
│  │ Container:        Docker                                     │   │
│  │ Orchestration:    Kubernetes (EKS/GKE/AKS)                  │   │
│  │ IaC:             Terraform + Pulumi                         │   │
│  │ CI/CD:           GitHub Actions + ArgoCD                    │   │
│  │ Service Mesh:    Istio or Linkerd (optional)                │   │
│  │ Secret Mgmt:     HashiCorp Vault                            │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ AUTH & SECURITY                                              │   │
│  │                                                              │   │
│  │ Identity:         Keycloak or Ory Kratos                    │   │
│  │ Authorization:    OPA / Casbin                              │   │
│  │ Rate Limiting:    Built into Kong/APISIX                    │   │
│  │ Audit:           Immutable event log (Kafka + S3)           │   │
│  └──────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────┘
```

### 8.2 Alternative Stack Options

```
┌──────────────────────────────────────────────────────────────────────┐
│                    ALTERNATIVE STACKS                                 │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ OPTION A: Node.js/TypeScript Focus (Faster MVP)              │   │
│  │                                                              │   │
│  │ Runtime:       Node.js + TypeScript                          │   │
│  │ Framework:     NestJS                                        │   │
│  │ ORM:           Prisma                                        │   │
│  │ Rule Engine:   json-rules-engine                             │   │
│  │ Queue:         BullMQ                                        │   │
│  │ WebSocket:     Socket.io                                     │   │
│  │ Event:         NATS JetStream (simpler than Kafka)          │   │
│  │                                                              │   │
│  │ Pros: Faster development, large talent pool                 │   │
│  │ Cons: Not ideal for ultra-low latency risk checks           │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ OPTION B: Java/Kotlin Focus (Enterprise)                     │   │
│  │                                                              │   │
│  │ Runtime:       JVM (Java 21 / Kotlin)                        │   │
│  │ Framework:     Spring Boot / Quarkus                         │   │
│  │ Rule Engine:   Drools (full-featured)                        │   │
│  │ Stream:        Kafka Streams                                 │   │
│  │ Workflow:      Temporal (Java SDK)                           │   │
│  │                                                              │   │
│  │ Pros: Mature ecosystem, Drools is excellent                 │   │
│  │ Cons: Higher memory usage, more boilerplate                 │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ OPTION C: Rust Focus (Maximum Performance)                   │   │
│  │                                                              │   │
│  │ Runtime:       Rust                                          │   │
│  │ Framework:     Actix-web / Axum                              │   │
│  │ Async:         Tokio                                         │   │
│  │ Event:         Redpanda + custom consumer                    │   │
│  │                                                              │   │
│  │ Pros: Lowest latency, memory safety                         │   │
│  │ Cons: Slower development, smaller talent pool               │   │
│  └──────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 9. Build vs. Leverage Decision Matrix

### 9.1 Decision Matrix

```
┌──────────────────────────────┬───────┬────────────┬───────────────────────┐
│ Component                    │Build  │ Use OSS    │ Reasoning             │
│                              │Custom │ As-Is      │                       │
├──────────────────────────────┼───────┼────────────┼───────────────────────┤
│ Pre-Trade Risk Checks        │  ✅   │            │ Core IP, must be      │
│                              │       │            │ custom & fast         │
├──────────────────────────────┼───────┼────────────┼───────────────────────┤
│ Drawdown Calculator          │  ✅   │            │ Core IP, multiple     │
│                              │       │            │ calculation modes     │
├──────────────────────────────┼───────┼────────────┼───────────────────────┤
│ Evaluation Logic             │  ✅   │            │ Core IP, challenge    │
│ (Phase/Target tracking)      │       │            │ rules are the product │
├──────────────────────────────┼───────┼────────────┼───────────────────────┤
│ Fraud Detection Models       │  ✅   │ Partial    │ Custom + use          │
│                              │       │ (ML libs)  │ scikit-learn/River    │
├──────────────────────────────┼───────┼────────────┼───────────────────────┤
│ Consistency Scoring          │  ✅   │            │ Prop-firm specific    │
│                              │       │            │ business logic        │
├──────────────────────────────┼───────┼────────────┼───────────────────────┤
│ Payout Calculator            │  ✅   │            │ Business logic        │
├──────────────────────────────┼───────┼────────────┼───────────────────────┤
│ Broker/Platform Gateway      │  ✅   │ Partial    │ Custom bridge +       │
│                              │       │ (FIX libs) │ QuickFIX/CCXT        │
├──────────────────────────────┼───────┼────────────┼───────────────────────┤
│ Rule Engine Framework        │       │  ✅        │ Use OPA/Drools,       │
│                              │       │            │ don't reinvent        │
├──────────────────────────────┼───────┼────────────┼───────────────────────┤
│ Event Streaming              │       │  ✅        │ Use Kafka/Redpanda    │
├──────────────────────────────┼───────┼────────────┼───────────────────────┤
│ Stream Processing            │       │  ✅        │ Use Flink/KStreams    │
├──────────────────────────────┼───────┼────────────┼───────────────────────┤
│ Workflow Orchestration       │       │  ✅        │ Use Temporal.io       │
├──────────────────────────────┼───────┼────────────┼───────────────────────┤
│ Database / Cache             │       │  ✅        │ Use PG/Redis/         │
│                              │       │            │ TimescaleDB           │
├──────────────────────────────┼───────┼────────────┼───────────────────────┤
│ Analytics Engine             │       │  ✅        │ Use ClickHouse        │
├──────────────────────────────┼───────┼────────────┼───────────────────────┤
│ API Gateway                  │       │  ✅        │ Use Kong/APISIX       │
├──────────────────────────────┼───────┼────────────┼───────────────────────┤
│ Authentication               │       │  ✅        │ Use Keycloak/Ory      │
├──────────────────────────────┼───────┼────────────┼───────────────────────┤
│ Observability                │       │  ✅        │ Prometheus/Grafana    │
├──────────────────────────────┼───────┼────────────┼───────────────────────┤
│ Notifications                │       │  ✅        │ Use Novu              │
├──────────────────────────────┼───────┼────────────┼───────────────────────┤
│ Performance Metrics          │ Mixed │  Partial   │ Custom formulas +     │
│ Calculation                  │       │            │ QuantLib/numpy        │
├──────────────────────────────┼───────┼────────────┼───────────────────────┤
│ Admin Dashboard              │  ✅   │ Partial    │ Custom + use Grafana  │
│                              │       │ (Grafana)  │ for operational views │
└──────────────────────────────┴───────┴────────────┴───────────────────────┘

SUMMARY:
- Build Custom: ~40% (Core business logic - risk, evaluation, fraud)
- Use Open Source: ~60% (Infrastructure, frameworks, tools)
```

### 9.2 Effort Estimation

```
┌──────────────────────────────────────────────────────────────────────┐
│                    EFFORT ESTIMATION                                  │
│                                                                      │
│  ┌─────────────────────────────┬──────────┬───────────────────────┐ │
│  │ Component                   │ Effort   │ With OSS Leverage     │ │
│  ├─────────────────────────────┼──────────┼───────────────────────┤ │
│  │ Risk Engine (core)          │ 3 months │ 3 months (custom)     │ │
│  │ Evaluation Engine           │ 2 months │ 2 months (custom)     │ │
│  │ Fraud Detection             │ 2 months │ 1.5 months (ML libs)  │ │
│  │ Broker Gateway              │ 2 months │ 1 month (FIX/CCXT)   │ │
│  │ Event Infrastructure        │ 2 months │ 2 weeks (Kafka/etc)   │ │
│  │ Data Pipeline               │ 2 months │ 1 month (Flink)       │ │
│  │ Workflow/State Mgmt         │ 1 month  │ 2 weeks (Temporal)    │ │
│  │ API Layer                   │ 1 month  │ 1 month               │ │
│  │ Admin Dashboard             │ 2 months │ 1 month (Grafana+)    │ │
│  │ Auth & Security             │ 1 month  │ 2 weeks (Keycloak)    │ │
│  │ Observability               │ 1 month  │ 1 week (Prom/Graf)    │ │
│  │ Testing & QA                │ 2 months │ 2 months              │ │
│  │ DevOps & Infrastructure     │ 1 month  │ 1 month               │ │
│  ├─────────────────────────────┼──────────┼───────────────────────┤ │
│  │ TOTAL                       │ 22 months│ ~13 months            │ │
│  │ With 4-person team          │ ~6 months│ ~3.5 months           │ │
│  └─────────────────────────────┴──────────┴───────────────────────┘ │
│                                                                      │
│  OSS Leverage Savings: ~40% reduction in development time           │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 10. Implementation Roadmap

### 10.1 Phased Approach

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                       IMPLEMENTATION ROADMAP                                  │
│                                                                              │
│  PHASE 1: Foundation (Weeks 1-4)                                             │
│  ═══════════════════════════════                                             │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │ • Set up Kubernetes cluster                                           │  │
│  │ • Deploy PostgreSQL + TimescaleDB + Redis/Dragonfly                  │  │
│  │ • Deploy Redpanda/Kafka cluster                                      │  │
│  │ • Deploy Keycloak for auth                                           │  │
│  │ • Set up CI/CD pipeline (GitHub Actions + ArgoCD)                    │  │
│  │ • Set up monitoring (Prometheus + Grafana + Loki)                    │  │
│  │ • Design and implement core data models                             │  │
│  │ • Implement Account Service (CRUD + state management)               │  │
│  │ • Basic API gateway setup (Kong)                                     │  │
│  │                                                                      │  │
│  │ Deliverable: Infrastructure ready, basic account management         │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  PHASE 2: Core Risk Engine (Weeks 5-10)                                     │
│  ═══════════════════════════════════════                                     │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │ • Implement real-time risk engine                                     │  │
│  │   - Pre-trade risk checks (all validations)                          │  │
│  │   - Real-time drawdown calculation (all types)                       │  │
│  │   - Position tracking and P&L calculation                            │  │
│  │   - Breach detection and handling                                    │  │
│  │   - Auto-liquidation logic                                           │  │
│  │ • Implement broker gateway (start with 1 broker - e.g., cTrader)    │  │
│  │ • Set up Flink for stream processing                                 │  │
│  │ • Implement Redis state management for risk engine                   │  │
│  │ • WebSocket server for real-time updates                             │  │
│  │ • Load testing risk engine (target: < 5ms pre-trade check)          │  │
│  │                                                                      │  │
│  │ Deliverable: Working risk engine with real-time monitoring           │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  PHASE 3: Evaluation Engine (Weeks 11-16)                                   │
│  ════════════════════════════════════════                                    │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │ • Implement evaluation engine                                         │  │
│  │   - Challenge phase management (state machine)                       │  │
│  │   - Profit target tracking                                           │  │
│  │   - Trading day counting                                             │  │
│  │   - Consistency rule checking                                        │  │
│  │   - Time limit enforcement                                           │  │
│  │ • Implement Temporal.io workflows                                    │  │
│  │   - Challenge lifecycle workflow                                     │  │
│  │   - Daily end-of-day workflow                                        │  │
│  │   - Phase transition workflow                                        │  │
│  │ • Implement challenge configuration system (per-firm)               │  │
│  │ • Implement payout calculation engine                                │  │
│  │ • Scaling plan logic                                                 │  │
│  │ • Performance metrics calculation service                            │  │
│  │                                                                      │  │
│  │ Deliverable: Full challenge lifecycle from creation to funded        │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  PHASE 4: Analytics & Fraud Detection (Weeks 17-22)                         │
│  ══════════════════════════════════════════════════                          │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │ • Deploy ClickHouse for analytics                                     │  │
│  │ • Build data pipeline (Flink → ClickHouse)                           │  │
│  │ • Implement fraud detection models                                    │  │
│  │   - Copy trade detection                                             │  │
│  │   - Martingale/grid detection                                        │  │
│  │   - Latency arbitrage detection                                      │  │
│  │   - News straddle detection                                          │  │
│  │ • IP/device fingerprinting                                           │  │
│  │ • Behavioral analysis system                                         │  │
│  │ • Trader performance analytics dashboard                             │  │
│  │ • Admin dashboard for risk monitoring                                │  │
│  │                                                                      │  │
│  │ Deliverable: Analytics and fraud detection operational               │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  PHASE 5: Multi-Tenancy & White Label (Weeks 23-28)                         │
│  ══════════════════════════════════════════════════                          │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │ • Multi-tenant architecture implementation                            │  │
│  │   - Per-firm configuration isolation                                  │  │
│  │   - Per-firm data isolation                                          │  │
│  │   - Custom branding support                                          │  │
│  │ • White-label API endpoints                                          │  │
│  │ • Firm onboarding workflow                                           │  │
│  │ • Additional broker integrations (MT4, MT5, Exchange APIs)           │  │
│  │ • Notification system (Novu integration)                             │  │
│  │ • Comprehensive audit logging                                        │  │
│  │ • Security hardening                                                  │  │
│  │ • Performance optimization                                           │  │
│  │                                                                      │  │
│  │ Deliverable: Production-ready multi-tenant platform                  │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  PHASE 6: Production & Scale (Weeks 29-32)                                  │
│  ═════════════════════════════════════════                                   │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │ • Load testing (target: 100K+ concurrent accounts)                    │  │
│  │ • Chaos engineering                                                   │  │
│  │ • Disaster recovery testing                                          │  │
│  │ • Security audit                                                      │  │
│  │ • Performance tuning                                                  │  │
│  │ • Documentation                                                       │  │
│  │ • Beta program with pilot firms                                      │  │
│  │ • Production deployment                                               │  │
│  │                                                                      │  │
│  │ Deliverable: Production launch                                       │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 10.2 Team Structure

```
┌──────────────────────────────────────────────────────────────────────┐
│                    RECOMMENDED TEAM                                   │
│                                                                      │
│  Core Team (Phase 1-3): 4-6 engineers                               │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ 1x Tech Lead / Architect                                    │   │
│  │   - System design, architecture decisions                   │   │
│  │   - Risk engine design                                      │   │
│  │                                                              │   │
│  │ 2x Backend Engineers (Go / Python)                          │   │
│  │   - Risk engine implementation                              │   │
│  │   - Evaluation engine implementation                        │   │
│  │   - API development                                         │   │
│  │                                                              │   │
│  │ 1x Data/Stream Engineer                                     │   │
│  │   - Kafka/Flink pipeline                                    │   │
│  │   - Data modeling                                           │   │
│  │   - Analytics pipeline                                      │   │
│  │                                                              │   │
│  │ 1x DevOps/SRE Engineer                                     │   │
│  │   - Kubernetes, CI/CD                                       │   │
│  │   - Monitoring, alerting                                    │   │
│  │   - Infrastructure as code                                  │   │
│  │                                                              │   │
│  │ 1x Domain Expert / Product (part-time)                     │   │
│  │   - Prop firm business rules                                │   │
│  │   - Risk management expertise                               │   │
│  │   - Regulatory knowledge                                    │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  Extended Team (Phase 4-6): Add                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ 1x ML Engineer (fraud detection)                            │   │
│  │ 1x Frontend Engineer (dashboard)                            │   │
│  │ 1x QA Engineer                                              │   │
│  └──────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────┘
```

### 10.3 Key Open-Source Projects to Evaluate First

```
┌──────────────────────────────────────────────────────────────────────┐
│              TOP 10 OPEN-SOURCE TO EVALUATE IMMEDIATELY              │
│                                                                      │
│  1. Redpanda (https://github.com/redpanda-data/redpanda)           │
│     → Event streaming backbone. Kafka-compatible, easier to run.    │
│     → License: BSL 1.1 (source available)                          │
│                                                                      │
│  2. Temporal.io (https://github.com/temporalio/temporal)            │
│     → Workflow orchestration for challenge lifecycle.               │
│     → License: MIT                                                  │
│                                                                      │
│  3. Apache Flink (https://github.com/apache/flink)                  │
│     → Stream processing for real-time risk calculations.           │
│     → License: Apache 2.0                                          │
│                                                                      │
│  4. Open Policy Agent (https://github.com/open-policy-agent/opa)   │
│     → Policy/rule engine for risk rules.                           │
│     → License: Apache 2.0                                          │
│                                                                      │
│  5. TimescaleDB (https://github.com/timescale/timescaledb)          │
│     → Time-series data for trade history, price data.              │
│     → License: Apache 2.0 (community edition)                     │
│                                                                      │
│  6. ClickHouse (https://github.com/ClickHouse/ClickHouse)          │
│     → OLAP analytics for performance dashboards.                   │
│     → License: Apache 2.0                                          │
│                                                                      │
│  7. Dragonfly (https://github.com/dragonflydb/dragonfly)            │
│     → Redis-compatible in-memory store, 25x faster.               │
│     → License: BSL 1.1                                             │
│                                                                      │
│  8. Keycloak (https://github.com/keycloak/keycloak)                 │
│     → Identity and access management.                              │
│     → License: Apache 2.0                                          │
│                                                                      │
│  9. Novu (https://github.com/novuhq/novu)                           │
│     → Notification infrastructure.                                  │
│     → License: MIT                                                  │
│                                                                      │
│ 10. Grafana (https://github.com/grafana/grafana)                    │
│     → Dashboards and monitoring.                                    │
│     → License: AGPL v3                                             │
│                                                                      │
│  BONUS: Notable Mentions                                            │
│  • QuickFIX/J - FIX protocol engine                                │
│  • CCXT - Crypto exchange connectivity                             │
│  • River (Python) - Online ML for anomaly detection                │
│  • Casbin - Authorization framework                                │
│  • dbt - Data transformation                                       │
└──────────────────────────────────────────────────────────────────────┘
```

### 10.4 Critical Architecture Decisions

```
┌──────────────────────────────────────────────────────────────────────┐
│              CRITICAL ARCHITECTURE DECISIONS                         │
│                                                                      │
│  1. LATENCY REQUIREMENTS                                            │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ Pre-trade risk check:  < 5ms  (critical path)              │   │
│  │ Drawdown update:       < 50ms (per price tick)             │   │
│  │ Breach detection:      < 100ms                             │   │
│  │ Evaluation update:     < 1s                                │   │
│  │ Analytics query:       < 5s                                │   │
│  │                                                              │   │
│  │ → Use Go for risk engine, Redis for state, avoid DB in     │   │
│  │   the hot path                                              │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  2. CONSISTENCY vs AVAILABILITY                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ Risk decisions: MUST be consistent (CP over AP)             │   │
│  │ • Cannot allow a trade that would breach limits             │   │
│  │ • If in doubt, REJECT (fail-safe)                          │   │
│  │ • Use Redis with AOF persistence for state                 │   │
│  │ • Async write to PostgreSQL for durability                 │   │
│  │                                                              │   │
│  │ Analytics: Can be eventually consistent (AP is fine)        │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  3. MULTI-TENANCY MODEL                                             │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ Option A: Schema-per-tenant (recommended for < 100 firms)  │   │
│  │ Option B: Shared tables with tenant_id (simpler)           │   │
│  │ Option C: Database-per-tenant (max isolation)              │   │
│  │                                                              │   │
│  │ Recommendation: Shared tables + Row-Level Security (RLS)   │   │
│  │ in PostgreSQL for data isolation                           │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  4. SCALING STRATEGY                                                │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ Risk Engine:    Horizontal scaling, shard by account_id    │   │
│  │ Event Streaming: Partition by account_id                   │   │
│  │ Database:       Read replicas + connection pooling (PgBouncer)│ │
│  │ Cache:          Redis Cluster or Dragonfly                 │   │
│  │                                                              │   │
│  │ Target: 100K concurrent accounts, 10K trades/second        │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  5. AUDITABILITY                                                    │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ Every risk decision must be logged and auditable            │   │
│  │ • Use event sourcing for risk events                       │   │
│  │ • Kafka as immutable log                                   │   │
│  │ • Archive to S3/MinIO for compliance                       │   │
│  │ • Never delete, only append                                │   │
│  └──────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Summary: Key Recommendations

| Area | Recommendation |
|------|---------------|
| **Core Architecture** | Event-driven microservices with CQRS pattern |
| **Risk Engine** | Build custom in Go; use Redis for state, OPA for policy rules |
| **Evaluation Engine** | Build custom; use Temporal.io for workflow orchestration |
| **Event Streaming** | Redpanda (simpler) or Apache Kafka (more mature) |
| **Stream Processing** | Apache Flink for complex event processing |
| **Databases** | PostgreSQL + TimescaleDB + ClickHouse + Redis |
| **Fraud Detection** | Custom models using scikit-learn/River + custom heuristics |
| **Observability** | Prometheus + Grafana + OpenTelemetry stack |
| **Auth** | Keycloak for identity + OPA for authorization |
| **Build vs Buy** | Build ~40% custom (core IP), leverage ~60% open-source |
| **Time to MVP** | ~3.5-4 months with a 4-person team leveraging OSS |
| **Time to Production** | ~7-8 months with full feature set |

The key insight is that **the business logic (risk calculations, evaluation rules, fraud patterns) must be custom-built** as it represents the core IP and competitive advantage. However, all supporting infrastructure (messaging, databases, workflows, auth, monitoring) should leverage battle-tested open-source solutions to dramatically reduce development time and improve reliability.
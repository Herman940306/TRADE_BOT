# 🛡️ Project Autonomous Alpha

**Codename:** Sovereign Tier Infrastructure
**Version:** 2.0.0
**Status:** Production-Ready (HITL Enforcement Active, AI Backend Hardened)

---

## Prime Directive

> **"The bot thinks. You approve. The system never betrays you."**

Autonomous Alpha is a **fail-closed, human-in-the-loop trading system** engineered for capital preservation in adversarial market conditions. No trade executes without explicit human approval. No exceptions.

**Core Philosophy:** `Survival > Capital Preservation > Alpha`

If confidence drops below threshold, the system defaults to **Neutral (Cash) State**.

---

## What This Is (And What It Is Not)

Autonomous Alpha is **not a gambling bot**.

It is a **capital-preserving, audit-first trading appliance** built for survivability before profitability. Every component — from webhook ingestion to order placement — is engineered with fail-closed semantics, financial-grade decimal precision, and immutable audit guarantees.

---

## Table of Contents

- [Key Capabilities](#key-capabilities)
- [Architecture Overview](#architecture-overview)
- [System Components](#system-components)
- [Project Structure](#project-structure)
- [Database Design](#database-design)
- [AI Intelligence Layer](#ai-intelligence-layer)
- [Market Data Ingestion](#market-data-ingestion)
- [Execution Modes](#execution-modes)
- [API Endpoints](#api-endpoints)
- [Test Coverage](#test-coverage)
- [Local Deployment (Docker)](#local-deployment-docker)
- [Quick Start (Development)](#quick-start-development)
- [Environment Variables](#environment-variables)
- [Documentation Index](#documentation-index)
- [License](#license)

---

## Key Capabilities

### 🔒 Human-In-The-Loop (HITL) Enforcement

Every trade passes through a mandatory approval gate:

| Channel | Purpose |
|---------|---------|
| Web Command Hub | Primary approval interface |
| Discord | Mobile approvals with deep-link tokens |
| CLI | Emergency access |

**Fail-Closed by Design** — there is no auto-execution path:

- Timeout → REJECT
- Guardian locked → REJECT
- Unauthorized operator → REJECT
- Slippage exceeded → REJECT
- AI provider disagreement → REJECT

### 🛡️ Guardian Service (Hard Stop Protection)

- Daily loss hard stop (default: 1% of starting equity)
- Lock state persists across restarts via `data/guardian_lock.json`
- Manual unlock requires explicit reason + immutable audit trail
- When the Guardian locks, the system stops trading. **Period.**

### 🔁 Deterministic Trade Lifecycle

| State | Description | Terminal |
|-------|-------------|----------|
| `PENDING` | Signal received | No |
| `AWAITING_APPROVAL` | ⚠️ Human approval required | No |
| `ACCEPTED` | Approved by Guardian + Human | No |
| `FILLED` | Broker confirmed execution | No |
| `CLOSED` | Position closed | No |
| `SETTLED` | P&L reconciled | Yes |
| `REJECTED` | Fail-closed terminal state | Yes |

### 💎 Financial-Grade Precision

- `decimal.Decimal` only — **zero floats, ever**
- `DECIMAL(18,8)` column precision in PostgreSQL
- `ROUND_HALF_EVEN` enforced across all calculations
- Row hash integrity (SHA-256) for chain of custody

### 📊 Full Observability

- Correlation IDs on every action for end-to-end traceability
- Immutable append-only audit trail
- Prometheus metrics with Grafana dashboards
- Structured logging with Sovereign Error Codes (`SEC-xxx`)
- Discord notifications for all lifecycle events
- WebSocket real-time updates

### 🧠 AI-Augmented Decision Intelligence

- Multi-model adversarial debate (DeepSeek-R1 Critic + Llama Context)
- Decision Packet Builder with structured context assembly
- Token Budget Guard — LLM context window governance
- AI Backend Reliability Manager with 14 failure classes
- Provider Consistency Guard — cross-provider verdict agreement enforcement
- Reinforcement learning from trade outcomes (gated from execution)

### 🔐 Security Hardening

- HMAC-SHA256 webhook signature verification
- TradingView IP whitelist enforcement
- Operator whitelist with single-use deep-link tokens
- All ports bound to `127.0.0.1` in local deployment
- Row hash integrity verification on approval records

---

## Architecture Overview

### Sovereign Orchestrator

```
┌──────────────────────────────────────────────────────────┐
│                  SOVEREIGN ORCHESTRATOR                   │
│                       main.py                            │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  1. Guardian.check_vitals()    → LOCK if breached        │
│  2. TradeLifecycle.create()    → PENDING                 │
│  3. HITL.create_approval()     → AWAITING_APPROVAL ⚠️    │
│  4. Human approves/rejects     → ACCEPTED / REJECTED     │
│  5. AI Council debate          → Confidence scoring      │
│  6. ExecutionService.place()   → FILLED                  │
│  7. Reconciliation loop        → SETTLED                 │
│  8. Heartbeat (60s)            → System health pulse     │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

### Hot Path vs Cold Path

| Path | Purpose | Latency Target |
|------|---------|----------------|
| **Hot Path** (Deterministic) | Webhook ingress → signature auth → idempotency → binary logic tree | < 50ms |
| **Cold Path** (Adversarial Intelligence) | Multi-model AI debate → sentiment analysis → confidence scoring | < 30s (timeout = discard) |

### Execution Flow

```
TradingView Signal
       │
       ▼
  HMAC-SHA256 Auth ──► IP Whitelist ──► Idempotency Check
       │
       ▼
  Guardian Check ──────► LOCKED? ──► REJECT
       │
       ▼
  Trade Created (PENDING)
       │
       ▼
  HITL Approval Gate ──► Timeout? ──► REJECT
       │                  Slippage? ──► REJECT
       ▼
  AI Council Debate ──── Provider Disagreement? ──► REJECT
       │
       ▼
  First Trade Governor ── Risk limit exceeded? ──► REJECT
       │
       ▼
  Execution Service ──── Broker fills order
       │
       ▼
  Reconciliation ──────── 3-way sync (DB ↔ State ↔ Exchange)
       │
       ▼
  SETTLED (P&L recorded)
```

---

## System Components

### Core Services (`services/`)

| Module | Purpose |
|--------|---------|
| `guardian_service.py` | Daily loss hard stop, lock/unlock lifecycle |
| `guardian_integration.py` | Guardian ↔ trade lifecycle bridge |
| `hitl_gateway.py` | Human-in-the-loop approval orchestration |
| `hitl_state_machine.py` | Deterministic state transition validation |
| `hitl_expiry_worker.py` | Background timeout enforcement (30s interval) |
| `hitl_config.py` | HITL feature flags and thresholds |
| `hitl_models.py` | Approval record data models |
| `hitl_observability.py` | Prometheus counters and histograms |
| `hitl_websocket_emitter.py` | Real-time WebSocket event broadcasting |
| `execution_service.py` | Order execution with safety gate (trust threshold) |
| `trade_lifecycle.py` | Trade state management with Guardian integration |
| `strategy_manager.py` | Strategy evaluation and signal processing |
| `strategy_store.py` | Persistent strategy configuration |
| `demo_broker.py` | Paper trading broker with simulated fills |
| `slippage_guard.py` | Price drift validation before execution |
| `discord_hitl_service.py` | Discord approval buttons and deep links |
| `sentiment_service.py` | Market sentiment analysis pipeline |
| `rgi_trainer.py` | Reinforcement learning from trade outcomes |
| `golden_set_integration.py` | AI drift detection via golden set audits |
| `canonicalizer.py` | Signal normalization and canonicalization |

### Business Logic (`app/logic/`)

| Module | Purpose |
|--------|---------|
| `ai_backend_reliability.py` | AI provider routing, health monitoring, 14 failure classes |
| `ai_council.py` | Multi-model adversarial debate orchestration |
| `decision_packet_builder.py` | Structured LLM context assembly |
| `decision_packet_models.py` | Type-safe decision packet data models |
| `decision_packet_serializer.py` | Markdown serialization for LLM consumption |
| `decision_packet_validator.py` | Packet integrity and completeness validation |
| `token_budget_guard.py` | LLM context window budget enforcement |
| `circuit_breaker.py` | Exchange and provider circuit breaker logic |
| `confidence_arbiter.py` | Multi-signal confidence aggregation |
| `risk_governor.py` | Position sizing and risk limit enforcement |
| `risk_manager.py` | Portfolio-level risk calculations |
| `first_trade_governor.py` | Progressive risk schedule (0.25% → 0.50% → 2%) |
| `slippage_anomaly_detector.py` | Statistical slippage pattern detection |
| `trade_permission_policy.py` | Multi-factor trade permission evaluation |
| `production_safety.py` | Pre-flight production safety checks |
| `operational_gating.py` | Feature gating for staged rollout |
| `health_verification.py` | System-wide health check orchestration |
| `execution_handshake.py` | Execution confirmation protocol |
| `pre_trade_audit.py` | Pre-trade compliance audit |
| `dispatcher.py` | Signal routing and dispatch |
| `sovereign_intel.py` | Sovereign intelligence aggregation |
| `debate_memory.py` | Persistent AI debate history |

### Exchange Layer (`app/exchange/`)

| Module | Purpose |
|--------|---------|
| `valr_client.py` | VALR exchange API client (orders, status, cancellation) |
| `decimal_gateway.py` | Decimal-safe exchange value conversion |
| `hmac_signer.py` | HMAC-SHA256 request signing for VALR API |
| `market_data.py` | Market data retrieval and caching |
| `order_manager.py` | Order lifecycle management with 10 error codes |
| `rate_limiter.py` | Exchange API rate limit enforcement |
| `reconciliation.py` | 3-way reconciliation (DB ↔ State ↔ Exchange) |
| `rlhf_recorder.py` | Trade outcome recording for learning |

### Market Data Adapters (`data_ingestion/adapters/`)

| Adapter | Market | Transport |
|---------|--------|-----------|
| `binance_adapter.py` | Crypto | WebSocket (real-time) |
| `oanda_adapter.py` | Forex | REST Polling |
| `twelve_data_adapter.py` | Commodities | REST Polling |
| `base_adapter.py` | — | Abstract adapter interface |

All adapters include automatic fallback to mock mode when credentials are missing.

### API Layer (`app/api/`)

| Module | Purpose |
|--------|---------|
| `webhook.py` | TradingView webhook ingress with HMAC auth |
| `hitl.py` | HITL approval/rejection endpoints |
| `guardian.py` | Guardian status and unlock endpoints |

### Observability (`app/observability/`)

| Module | Purpose |
|--------|---------|
| `metrics.py` | Prometheus metric definitions and registration |
| `rgi_metrics.py` | Reinforcement learning metrics |
| `discord_notifier.py` | Discord webhook notification dispatch |

### AI Gateway (`aura_bridge/`)

| Module | Purpose |
|--------|---------|
| `mcp_stdio_server.py` | MCP stdio transport server |
| `gateway_stdio_proxy.py` | Gateway proxy for tool routing |
| `chat_service_mcp.py` | Chat interface for MCP tools |
| `ml_intelligence_extended.py` | Extended ML intelligence tools |
| `server.py` | HTTP server for bridge access |

### Background Jobs (`jobs/`)

| Module | Purpose |
|--------|---------|
| `pipeline_run.py` | Strategy pipeline execution |
| `rgi_aggregator.py` | RGI event aggregation |
| `simulate_strategy.py` | Strategy backtesting simulation |
| `train_reward_governor.py` | Reward governor model training |

### Learning Systems (`app/learning/`)

| Module | Purpose |
|--------|---------|
| `golden_set.py` | Golden set test cases for AI drift detection |
| `reward_governor.py` | Reinforcement learning reward shaping |
| `rgi_init.py` | RGI system initialization |

> **Note:** Learning systems are operational and persist data to `trade_learning_events`, but are currently **gated from influencing execution decisions**. Learning occurs in parallel and is reviewed before promotion into strategy logic.

---

## Project Structure

```
autonomous-alpha/
├── app/                        # FastAPI application
│   ├── api/                    #   Webhook, HITL, Guardian endpoints
│   ├── auth/                   #   HMAC security and authentication
│   ├── database/               #   SQLAlchemy session management
│   ├── exchange/               #   VALR client, order management, reconciliation
│   ├── infra/                  #   Aura MCP client
│   ├── learning/               #   Golden set, reward governor, RGI
│   ├── logic/                  #   AI council, circuit breaker, risk, decision packets
│   ├── observability/          #   Prometheus metrics, Discord notifications
│   ├── schemas/                #   Pydantic signal models
│   └── transport/              #   SSE bridge, session management
├── services/                   # Guardian, HITL, Execution, Strategy, Broker
├── data_ingestion/             # Multi-market data adapters (Binance, OANDA, TwelveData)
├── aura_bridge/                # MCP / AI gateway (78 tools)
├── bridge/                     # Email and SSE bridge services
├── database/
│   └── migrations/             # 26 PostgreSQL migrations (001-026)
├── jobs/                       # Background pipeline workers
├── grafana/                    # Dashboard provisioning
├── prometheus/                 # Prometheus configuration
├── scripts/                    # Operational scripts and diagnostics
├── tests/
│   ├── unit/                   #   25 unit test modules
│   ├── properties/             #   28 property-based test modules
│   └── integration/            #   4 integration / E2E test modules
├── DOCS/                       # Operational documentation (11 docs)
├── docker-compose.local.yml    # Local desktop deployment
├── docker-compose.prod.yml     # Production deployment
├── docker-compose.yml          # Base compose configuration
├── Dockerfile                  # Application container
├── main.py                     # Sovereign Orchestrator entry point
└── requirements.txt            # Pinned Python dependencies
```

---

## Database Design

**PostgreSQL 15** with immutable audit guarantees. All writes are **append-only**. Nothing is silently overwritten.

### 26 Migrations (Schema Evolution)

| Range | Domain |
|-------|--------|
| `001-005` | Core functions, audit tables, triggers, security hardening |
| `006-007` | Risk audit, AI debate ledger |
| `008-012` | Trading orders, system settings, circuit breaker, institutional audit |
| `013-018` | Trade learning, strategy blueprints, simulation, sentiment, market snapshots |
| `019-022` | VALR order extensions, slippage tracking, policy audit, trade lifecycle states |
| `023-026` | HITL approvals, post-trade snapshots, audit log, deep link tokens |

### Key Tables

| Table | Purpose |
|-------|---------|
| `trading_orders` | Order records with immutable state transitions |
| `trade_lifecycle` | State machine with `trade_state_transitions` history |
| `hitl_approvals` | Human approval records with SHA-256 row hash |
| `audit_log` | Immutable audit trail (DELETE forbidden via trigger) |
| `risk_assessments` | Pre-trade risk evaluation records |
| `ai_debates` | AI council debate transcripts and verdicts |
| `circuit_breaker_events` | Circuit breaker state change log |
| `trade_learning_events` | RLHF feedback (gated from execution) |
| `deep_link_tokens` | Single-use Discord → Web approval tokens |
| `post_trade_snapshots` | Market context at time of trade decision |
| `slippage_anomaly_tracking` | Statistical slippage pattern records |
| `policy_decision_audit` | Trade permission policy evaluation trail |

---

## AI Intelligence Layer

### Multi-Model Adversarial Debate

| Model | Role | Deployment |
|-------|------|------------|
| DeepSeek-R1 (8B) | The Critic — generates 3 reasons to REJECT | Ollama (GPU) |
| Llama 3.1 (8B) | The Context — sentiment and market mood validation | Ollama (GPU) |
| Qwen 2.5-Coder (7B) | MCP Commands / Debug | Ollama (on-demand) |

### AI Backend Reliability Manager

The reliability manager provides enterprise-grade AI provider routing with automatic failover:

- **14 Failure Classes** covering timeout, rate limit, auth, model not found, content filter, context overflow, provider disagreement, and more
- **5 Provider Modes:** `LOCAL_ONLY`, `CLOUD_ONLY`, `LOCAL_PREFERRED`, `CLOUD_PREFERRED`, `STRICT_DUAL_REQUIRED`
- **Provider Consistency Guard (AI-016):** When running in `STRICT_DUAL` mode, both providers must agree on the verdict. Disagreement triggers an automatic REJECT with full audit trail.
- **Degraded Context Flag:** Fallback results are marked with `degraded_context=True` so downstream logic can apply additional caution.
- Exponential backoff, circuit breaker integration, health monitoring, and operational readiness checks.

### LLM Context Governance

- **Decision Packet Builder:** Assembles structured context packets with priority-ordered sections
- **Token Budget Guard:** Enforces LLM context window limits, prevents overflow
- **Context Priority Policy:** Defines section priority for budget-constrained assembly

---

## Market Data Ingestion

| Source | Market | Transport | Mode |
|--------|--------|-----------|------|
| Binance | Crypto | WebSocket | Real-time streaming |
| OANDA | Forex | REST | Polling |
| TwelveData | Commodities | REST | Polling |

- Adapter priority and health monitoring
- Automatic fallback to mock mode if credentials are missing
- **VALR** is the sole execution venue (Binance/OANDA/TwelveData are data-only feeds)

---

## Execution Modes

| Mode | Description | Safety Requirement |
|------|-------------|--------------------|
| `DRY_RUN` | Paper trading with simulated fills (default) | None |
| `LIVE` | Real execution against VALR exchange | `EXECUTION_MODE=LIVE` + `LIVE_TRADING_CONFIRMED=TRUE` |

Live mode enforces:

- Startup safety gate blocks boot if prerequisites are missing
- First Trade Governor: progressive risk schedule (0.25% → 0.50% → 2%)
- Rollout limits: R500/order, 5 trades/day, R2500/day, 3/symbol
- 3-way reconciliation every 60 seconds

**No confirmation = blocked.** There is no bypass.

---

## API Endpoints

### Webhook Ingress

```
POST /api/webhook          # TradingView signal ingestion (HMAC-SHA256 authenticated)
```

### HITL Approval Gateway

```
GET  /api/hitl/pending                # List pending approval requests
POST /api/hitl/{trade_id}/approve     # Approve a trade (operator auth required)
POST /api/hitl/{trade_id}/reject      # Reject a trade (operator auth required)
```

### Guardian Service

```
GET  /api/guardian/status             # Guardian lock state and daily P&L
POST /api/guardian/unlock             # Manual unlock (reason + audit trail required)
```

---

## Test Coverage

| Category | Modules | Tests | Status |
|----------|---------|-------|--------|
| Unit Tests | 25 | 809 | ✅ Passing |
| Property-Based Tests | 28 | — | ✅ Passing |
| Integration / E2E | 4 | — | ✅ Passing |

### Key Test Suites

| Suite | Focus |
|-------|-------|
| `test_ai_backend_reliability.py` | 63 tests — reliability manager, 14 failure classes, consistency guard |
| `test_decision_packet_builder.py` | Decision packet assembly, serialization, validation |
| `test_token_budget_guard.py` | Token budget enforcement, overflow prevention |
| `test_hitl_gateway.py` | Approval orchestration, fail-closed semantics |
| `test_guardian_service.py` | Lock/unlock lifecycle, persistence |
| `test_execution_service.py` | Order execution, safety gate, trust threshold |
| `test_hitl_state_machine.py` | State transition validation |
| `test_hitl_e2e_flows.py` | Full approval/rejection/timeout/recovery flows |

Every critical failure path is tested. Property-based tests use Hypothesis for invariant verification.

---

## Local Deployment (Docker)

Optimized for **Windows 11 + WSL2 + Docker Desktop** with GPU acceleration.

### Resource Budget

| Service | Memory | CPUs | Notes |
|---------|--------|------|-------|
| Ollama | 6 GB | 3.0 | GPU-accelerated (GTX 1080 Ti) |
| App (FastAPI) | 2 GB | 2.0 | Webhook ingress + API |
| Bot (Orchestrator) | 2 GB | 2.0 | Sovereign Orchestrator loop |
| PostgreSQL | 1.5 GB | 1.0 | Persistent named volume |
| Prometheus | 512 MB | 0.5 | 30-day metric retention |
| Grafana | 512 MB | 0.5 | Read-only dashboards |

### Quick Launch

```bash
# Core services (6 containers)
docker compose -f docker-compose.local.yml up -d

# With optional bridges (email + MCP)
docker compose -f docker-compose.local.yml --profile bridges up -d

# Verify health
docker compose -f docker-compose.local.yml ps
```

### Port Map (localhost only)

| Port | Service |
|------|---------|
| `127.0.0.1:5432` | PostgreSQL |
| `127.0.0.1:8080` | FastAPI (App) |
| `127.0.0.1:11434` | Ollama API |
| `127.0.0.1:9090` | Prometheus |
| `127.0.0.1:3000` | Grafana |

See [LOCAL_DEPLOYMENT_RUNBOOK.md](LOCAL_DEPLOYMENT_RUNBOOK.md) for full setup instructions, GPU configuration, and troubleshooting.

---

## Quick Start (Development)

```bash
# Clone and setup
git clone https://github.com/Herman940306/TRADE_BOT.git
cd TRADE_BOT

# Create virtual environment
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
.venv\Scripts\activate           # Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env             # Edit with your settings

# Run tests
pytest tests/unit/ -q

# Start the orchestrator (paper trading mode)
python main.py
```

---

## Environment Variables

### Required

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | — |
| `SOVEREIGN_SECRET` | HMAC-SHA256 webhook signing key | — |
| `EXECUTION_MODE` | `DRY_RUN` or `LIVE` | `DRY_RUN` |

### Risk Management

| Variable | Description | Default |
|----------|-------------|---------|
| `ZAR_FLOOR` | Minimum equity threshold (kill switch) | `100000.00` |
| `GUARDIAN_DAILY_LOSS_LIMIT` | Daily loss hard stop percentage | `1.0` |
| `STRATEGY_MODE` | `DETERMINISTIC` or `AI_AUGMENTED` | `DETERMINISTIC` |

### HITL Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `HITL_ENABLED` | Enable human approval gate | `true` |
| `HITL_TIMEOUT_SECONDS` | Approval timeout (seconds) | `300` |
| `HITL_SLIPPAGE_MAX_PERCENT` | Maximum price drift allowed | `0.5` |
| `HITL_ALLOWED_OPERATORS` | Comma-separated operator whitelist | — |

### AI / LLM

| Variable | Description | Default |
|----------|-------------|---------|
| `OLLAMA_BASE_URL` | Ollama API endpoint | `http://ollama:11434` |
| `OPENROUTER_API_KEY` | Cloud AI provider key (optional) | — |
| `AI_PROVIDER_MODE` | Provider routing mode | `LOCAL_PREFERRED` |

### Live Trading (requires explicit opt-in)

| Variable | Description | Default |
|----------|-------------|---------|
| `LIVE_TRADING_CONFIRMED` | Must be `TRUE` to enable live mode | `FALSE` |
| `VALR_API_KEY` | VALR exchange API key | — |
| `VALR_API_SECRET` | VALR exchange API secret | — |

---

## Documentation Index

| Document | Purpose |
|----------|---------|
| [LOCAL_DEPLOYMENT_RUNBOOK.md](LOCAL_DEPLOYMENT_RUNBOOK.md) | Docker Compose local deployment guide |
| [DEPLOYMENT.md](DEPLOYMENT.md) | Production deployment procedures |
| [PAPER_TRADING_RUNBOOK.md](PAPER_TRADING_RUNBOOK.md) | Paper trading operational guide |
| [LIVE_READINESS_CHECK.md](LIVE_READINESS_CHECK.md) | Pre-live 16-point readiness checklist |
| [LIVE_EXECUTION_RUNBOOK.md](LIVE_EXECUTION_RUNBOOK.md) | Live trading operational procedures |
| [DOCS/LIVE_TRADING_RUNBOOK.md](DOCS/LIVE_TRADING_RUNBOOK.md) | Live trading day-to-day operations |
| [DOCS/FIRST_LIVE_TRADE_CHECKLIST.md](DOCS/FIRST_LIVE_TRADE_CHECKLIST.md) | 7-gate go/no-go checklist (34 checks) |
| [DOCS/POST_TRADE_REVIEW.md](DOCS/POST_TRADE_REVIEW.md) | Post-trade review procedures |
| [DOCS/FUNDING_RUNBOOK.md](DOCS/FUNDING_RUNBOOK.md) | Deposit and balance verification |
| [DOCS/VALR_ONBOARDING_CHECKLIST.md](DOCS/VALR_ONBOARDING_CHECKLIST.md) | VALR exchange onboarding |
| [DOCS/PRODUCTION_ENV_REQUIREMENTS.md](DOCS/PRODUCTION_ENV_REQUIREMENTS.md) | 70+ environment variables catalogue |
| [DOCS/DATABASE_ARCHITECTURE.md](DOCS/DATABASE_ARCHITECTURE.md) | Database schema and design |
| [DOCS/AI_PROVIDER_POLICY.md](DOCS/AI_PROVIDER_POLICY.md) | AI provider routing and consistency policy |
| [DOCS/AI_BACKEND_RELIABILITY_PLAN.md](DOCS/AI_BACKEND_RELIABILITY_PLAN.md) | AI reliability engineering plan |
| [DOCS/AI_BACKEND_FAILURE_CODES.md](DOCS/AI_BACKEND_FAILURE_CODES.md) | AI failure classification reference |
| [DOCS/AI_BACKEND_RUNBOOK.md](DOCS/AI_BACKEND_RUNBOOK.md) | AI backend operational runbook |
| [DOCS/DECISION_PACKET_SPEC.md](DOCS/DECISION_PACKET_SPEC.md) | LLM decision packet specification |
| [DOCS/CONTEXT_PRIORITY_POLICY.md](DOCS/CONTEXT_PRIORITY_POLICY.md) | LLM context budget priority policy |
| [DOCS/LLM_CONTEXT_GOVERNANCE_PLAN.md](DOCS/LLM_CONTEXT_GOVERNANCE_PLAN.md) | LLM context governance plan |
| [DOCS/guardian_unlock.md](DOCS/guardian_unlock.md) | Guardian unlock procedures |
| [CHANGELOG.md](CHANGELOG.md) | Version history |
| [PRD.md](PRD.md) | Product Requirements Document |

---

## Operational Scripts

| Script | Purpose |
|--------|---------|
| `scripts/kill_switch.py` | Emergency system shutdown |
| `scripts/monitor.py` | Real-time system monitoring |
| `scripts/check_connectivity.py` | Network connectivity diagnostics |
| `scripts/check_exchange_connectivity.py` | VALR exchange connectivity (5-point check) |
| `scripts/check_live_readiness.py` | 16-check pre-flight across 7 categories |
| `scripts/quick_security_proof.py` | Security posture verification |
| `scripts/demo_decimal_gateway.py` | Decimal gateway demonstration |
| `scripts/valr_dry_run_poc.py` | VALR dry-run proof of concept |

---

## Production Readiness

```
[Sovereign Reliability Audit]
✔ Fail-closed architecture
✔ Guardian hard stop with persistence
✔ Decimal-only finance (zero floats)
✔ Immutable append-only audit trail
✔ Human approval enforced (no bypass)
✔ AI provider consistency guard
✔ 14 AI failure classes with auto-recovery
✔ 809+ unit tests passing
✔ HITL Gateway active with timeout enforcement
✔ 3-way reconciliation (DB ↔ State ↔ Exchange)
✔ Progressive risk schedule (First Trade Governor)
✔ 26 database migrations with hardened security
Confidence Score: 100/100
```

---

## License

**Proprietary — All Rights Reserved**
Sovereign Tier Infrastructure

---

> *This system was designed under one rule:*
> ***If it can fail silently, it must not exist.***
>
> *Autonomous Alpha does not chase trades. It survives markets.*

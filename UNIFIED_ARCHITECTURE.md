# Unified Architecture

**Version:** 1.0.0
**Created:** 2026-03-29
**Classification:** Sovereign Tier Engineering — INTERNAL
**Reference:** MERGE_MASTER_PLAN.md

---

## 1. Architecture Overview

The unified Trade_Bot is a layered, fail-closed system where every trade must pass through all safety layers before execution. Legacy intelligence services are integrated as ADVISORY layers — they inform decisions but never bypass Guardian, HITL, or execution controls.

```
  ┌───────────────────────────────────────────────────────────────────┐
  │                    OPERATOR (Human)                               │
  │  • Views dashboard, approves/rejects trades via frontend         │
  │  • Monitors learning, forensics, strategy performance            │
  └─────────────────────────┬─────────────────────────────────────────┘
                            │ Browser (HTTPS + WebSocket)
                            ▼
  ┌───────────────────────────────────────────────────────────────────┐
  │  LAYER 1: FRONTEND (React + TypeScript + Vite)                   │
  │  ┌─────────┬──────────┬──────────┬───────────┬────────────────┐  │
  │  │Dashboard│ HITL     │ Guardian │ Forensics │ Learning/ML    │  │
  │  │ System  │ Approval │ Status   │ Snapshots │ Bayesian/Regime│  │
  │  │ Overview│ Inbox    │ Controls │ Replay    │ Experiments    │  │
  │  ├─────────┼──────────┼──────────┼───────────┼────────────────┤  │
  │  │ Trades  │ Strategy │ Paper    │ Operator  │ Settings/      │  │
  │  │ History │ Registry │ Trading  │ Analytics │ Config/Logs    │  │
  │  └─────────┴──────────┴──────────┴───────────┴────────────────┘  │
  │  Transport: REST (React Query) + WebSocket (live events)         │
  └─────────────────────────┬─────────────────────────────────────────┘
                            │
                            ▼
  ┌───────────────────────────────────────────────────────────────────┐
  │  LAYER 2: API GATEWAY (FastAPI — app/main.py)                    │
  │  ┌──────────────────────────────────────────────────────────┐    │
  │  │ Existing Endpoints (12)           New Frontend API (~13)  │    │
  │  │ POST /webhook/tradingview        GET /api/trades/history  │    │
  │  │ GET  /api/hitl/pending           GET /api/preflight       │    │
  │  │ POST /api/hitl/{id}/approve      GET /api/strategies      │    │
  │  │ POST /api/hitl/{id}/reject       GET /api/learning/status │    │
  │  │ POST /guardian/unlock            GET /api/decisions       │    │
  │  │ GET  /guardian/status            GET /api/analytics       │    │
  │  │ GET  /health                     GET /api/experiments     │    │
  │  │ GET  /metrics                    GET /api/regimes         │    │
  │  │ GET  /budget/status              GET /api/config          │    │
  │  │ POST /budget/refresh             GET /api/audit/log       │    │
  │  │ GET  /                           GET /api/market/health   │    │
  │  │                                  WS  /ws/events           │    │
  │  └──────────────────────────────────────────────────────────┘    │
  │  Auth: HMAC-SHA256 (webhooks) + Bearer token (operator)          │
  │  CORS: Restricted to frontend origin (NOT wildcard)              │
  └─────────────────────────┬─────────────────────────────────────────┘
                            │
          ┌─────────────────┼──────────────────┐
          ▼                 ▼                  ▼
  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐
  │ LAYER 3A:    │  │ LAYER 3B:    │  │ LAYER 3C:            │
  │ SIGNAL       │  │ AI REASONING │  │ BAYESIAN REASONING   │
  │ INGRESS      │  │              │  │ [FROM LEGACY]        │
  │              │  │              │  │                      │
  │ • TV webhook │  │ • AI Council │  │ • Belief updating    │
  │ • Email IMAP │  │ • Pre-trade  │  │ • Pattern fingerprint│
  │ • Canonical  │  │   audit      │  │ • Confidence budget  │
  │ • DSL valid  │  │ • Sovereign  │  │ • Capital allocation │
  │ • Pydantic   │  │   intel      │  │ • Mind state derive  │
  │              │  │ • Debate RAG │  │ • Mind state policy  │
  │              │  │ • Sentiment  │  │                      │
  │              │  │ • TV scraper │  │ ⚠️ ADVISORY ONLY     │
  └──────┬───────┘  └──────┬───────┘  └──────────┬───────────┘
         │                 │                      │
         └─────────────────┼──────────────────────┘
                           ▼
  ┌───────────────────────────────────────────────────────────────────┐
  │  LAYER 4: STRATEGY & RISK EVALUATION                             │
  │  ┌────────────────────────┐  ┌─────────────────────────────┐     │
  │  │ Strategy Evaluation    │  │ Risk Assessment             │     │
  │  │ • strategy_manager     │  │ • risk_manager (1% equity)  │     │
  │  │ • strategy_store       │  │ • budget_integration        │     │
  │  │ • canonicalizer        │  │ • circuit_breaker (3%/3x)   │     │
  │  │ • dsl_schema           │  │ • slippage_guard            │     │
  │  │ • golden_set_integration│  │ • dispatcher (trust≥0.6000)│     │
  │  │ • regime_sandbox [LEG] │  │ • production_safety         │     │
  │  └────────────────────────┘  └─────────────────────────────┘     │
  └─────────────────────────┬─────────────────────────────────────────┘
                            │
                            ▼
  ┌───────────────────────────────────────────────────────────────────┐
  │  LAYER 5: GUARDIAN / HITL SAFETY GATE (AUTHORITATIVE)            │
  │  ┌────────────────────────┐  ┌─────────────────────────────┐     │
  │  │ Guardian System        │  │ HITL Approval Gateway       │     │
  │  │ • 1% daily hard stop   │  │ • Create approval request   │     │
  │  │ • Thread-safe locking  │  │ • Discord notification      │     │
  │  │ • JSON persistence     │  │ • Operator decision         │     │
  │  │ • Cascade rejection    │  │ • Timeout auto-REJECT       │     │
  │  │ • Manual unlock only   │  │ • Recovery on restart       │     │
  │  │                        │  │ • Row hash verification     │     │
  │  │ LOCKED = NO TRADE      │  │ NO APPROVAL = NO TRADE      │     │
  │  └────────────────────────┘  └─────────────────────────────┘     │
  │  ⛔ FAIL-CLOSED: Any failure at this layer = trade REJECTED       │
  └─────────────────────────┬─────────────────────────────────────────┘
                            │ (ACCEPTED only)
                            ▼
  ┌───────────────────────────────────────────────────────────────────┐
  │  LAYER 6: EXECUTION ENGINE (NEW BOT — AUTHORITATIVE)             │
  │  ┌────────────────────────┐  ┌─────────────────────────────┐     │
  │  │ Mode Control           │  │ Broker Integration          │     │
  │  │ • mode_matrix.py       │  │ • PAPER: demo_broker.py     │     │
  │  │   PAPER (default)      │  │ • LIVE: live_execution_     │     │
  │  │   DRY_RUN              │  │         bridge.py           │     │
  │  │   LIVE_READ_ONLY       │  │ • VALR: order_manager.py    │     │
  │  │   LIVE_EXECUTION       │  │ • Poller: order_status_     │     │
  │  │ • Fail-closed to PAPER │  │          poller.py          │     │
  │  │ • Startup safety gate  │  │ • rollout limits            │     │
  │  │                        │  │ • 9-point preflight         │     │
  │  └────────────────────────┘  └─────────────────────────────┘     │
  │  ⛔ FAIL-CLOSED: Mode not LIVE = paper execution only             │
  └─────────────────────────┬─────────────────────────────────────────┘
                            │
                            ▼
  ┌───────────────────────────────────────────────────────────────────┐
  │  LAYER 7: POST-TRADE / FORENSICS [FROM LEGACY]                   │
  │  • trade_lifecycle.py          — State machine + persistence      │
  │  • decision_snapshot_service   — Full decision context capture    │
  │  • counterfactual_simulator    — What-if analysis replay          │
  │  • operator_analytics_service  — Operator vs AI performance       │
  │  • trade_learning.py           — Outcome recording for ML         │
  │  • rlhf_feedback.py            — RLHF signal recording            │
  └─────────────────────────┬─────────────────────────────────────────┘
                            │
                            ▼
  ┌───────────────────────────────────────────────────────────────────┐
  │  LAYER 8: LEARNING / EXPERIMENT [FROM LEGACY]                     │
  │  • learning_contract_enforcer  — Deny-first mutation gate         │
  │  • experiment_service          — Formal experiment lifecycle       │
  │  • learning_worker_v2          — 3-pillar learning loop           │
  │  • curriculum_scheduler        — Learning task scheduling         │
  │  • train_reward_governor       — RGI model training               │
  │  • rgi_aggregator              — Trust score aggregation          │
  │                                                                    │
  │  ⚠️ All DB mutations via learning_contract_enforcer               │
  │  ⚠️ Learning NEVER bypasses Guardian/HITL/Execution               │
  └─────────────────────────┬─────────────────────────────────────────┘
                            │
                            ▼
  ┌───────────────────────────────────────────────────────────────────┐
  │  LAYER 9: OBSERVATION & MONITORING                                │
  │  • Prometheus (30+ metrics)    — Counters, gauges, histograms     │
  │  • Grafana (12 dashboards)     — 4 core + 8 learning [LEGACY]     │
  │  • Discord notifications       — Startup, trades, Guardian, errors│
  │  • WebSocket events            — HITL, Guardian, trades → frontend│
  │  • Structured logging (L6)     — Correlation IDs, context         │
  └─────────────────────────┬─────────────────────────────────────────┘
                            │
                            ▼
  ┌───────────────────────────────────────────────────────────────────┐
  │  LAYER 10: DATA PERSISTENCE (PostgreSQL 15)                       │
  │  • 33 migrations (001-026 existing + 027-033 from legacy)         │
  │  • Immutable audit (DB triggers + row permissions + hash chain)   │
  │  • Roles: sovereign (DDL), app_trading (DML), aura_readonly       │
  │  • Tables: signals, hitl_approvals, audit_log, trade_lifecycle,   │
  │    trade_state_transitions, post_trade_snapshots, deep_link_tokens│
  │    + learning_domain_scores, learning_insights, knowledge_nodes,  │
  │    curriculum_entries, regime_observations, decision_snapshots,    │
  │    operator_decisions, operator_analytics, counterfactual_results, │
  │    experiment_definitions, experiment_rounds, experiment_results,  │
  │    learning_governance, evidence_traces, self_assessment_events   │
  └───────────────────────────────────────────────────────────────────┘
```

---

## 2. Service Dependency Map

### 2.1 Critical Path (Trade Execution)

```
webhook.py → canonicalizer → dsl_schema → signal validation
    │
    ├→ risk_manager → budget_integration → ai_council
    │
    ├→ [ADVISORY] bayesian_reasoning → capital_allocation → confidence_budget
    │              mind_state → mind_state_policy
    │
    ├→ strategy_manager → strategy_store → golden_set → regime_sandbox
    │
    ├→ dispatcher (trust gate ≥ 0.6000)
    │
    ├→ guardian_service → guardian_integration
    │
    ├→ hitl_gateway → discord_hitl → hitl_expiry_worker
    │
    ├→ execution_service → mode_matrix → live_execution_bridge / demo_broker
    │
    ├→ trade_lifecycle → decision_snapshot → operator_analytics
    │
    └→ learning_contract_enforcer → learning_worker_v2
```

### 2.2 Advisory Boundary

The ADVISORY BOUNDARY separates intelligence services from execution services. Services above the boundary can inform trade parameters but CANNOT:

- Bypass Guardian checks
- Auto-approve HITL requests
- Execute orders directly
- Modify execution mode
- Override risk limits

```
                    ┌────────── ADVISORY BOUNDARY ──────────┐
                    │                                        │
    bayesian_reasoning ──→ confidence_score ──→ dispatcher   │
    capital_allocation ──→ position_size ──→ risk_manager    │
    mind_state_service ──→ trading_policy ──→ webhook.py     │
    regime_sandbox ──→ strategy_selection ──→ strategy_mgr   │
                    │                                        │
                    │  Outputs are RECOMMENDATIONS only.     │
                    │  Execution decisions made by:          │
                    │    • Guardian (hard stop authority)     │
                    │    • HITL (operator approval required)  │
                    │    • ExecutionService (safety gate)     │
                    └────────────────────────────────────────┘
```

---

## 3. Data Flow Diagrams

### 3.1 Signal-to-Execution Flow

```
[TradingView]──webhook──►[HMAC verify]──►[Pydantic validate]──►[DB INSERT signal]
                                                                        │
         ┌──────────────────────────────────────────────────────────────┘
         ▼
  [BudgetGuard]──►[Risk Manager 1%]──►[AI Council Bull/Bear]
         │                                      │
         │    ┌─────────── PARALLEL ────────────┤
         │    ▼                                  ▼
         │  [Bayesian Reasoning]          [Pre-Trade Audit]
         │    │                                  │
         │    ├→ confidence_score               │
         │    ├→ pattern_fingerprint            │
         │    └→ capital_allocation             │
         │         └→ position_size            │
         │                                      │
         │    [Mind State Service]              │
         │    └→ CALM/ALERT/DEFENSIVE          │
         │       └→ Policy enforcement         │
         │                                      │
         └──────────────────────────────────────┘
                          │
                          ▼
                   [Dispatcher]
                   trust ≥ 0.6000?
                     │         │
                   NO│         │YES
                     ▼         ▼
                  REFUSE   [Guardian]
                           locked?
                           │     │
                         YES│   NO│
                           ▼     ▼
                        REFUSE [HITL Gateway]
                               create_approval()
                                    │
                               [Discord Notification]
                                    │
                            ┌───────┴───────┐
                           APPROVE        REJECT
                            │               │
                            ▼               ▼
                    [Execution Service]   LOG + audit
                    SafetyGate check
                            │
                    ┌───────┴───────┐
                   PAPER          LIVE
                    │               │
                    ▼               ▼
              [DemoBroker]   [LiveExecution
               fill sim      Bridge]
                    │         9-point preflight
                    │         rollout limits
                    │         VALR order
                    │               │
                    └───────┬───────┘
                            ▼
                    [Trade Lifecycle]
                    ACCEPTED → FILLED
                            │
                    [Decision Snapshot]  ← capture full context
                    [Operator Analytics] ← update metrics
                    [Learning Worker]    ← async background
```

### 3.2 Learning Feedback Loop

```
[Trade Outcome]
      │
      ├──►[trade_learning.py] ── record features + outcome
      ├──►[rlhf_feedback.py] ── record RLHF signal
      ├──►[decision_snapshot_service.py] ── full context
      │
      ▼
[Learning Worker v2] (background job, periodic)
      │
      ├──►[Pillar 1: Bayesian Update]
      │   └──► Update belief priors from outcome
      │   └──► Adjust pattern fingerprints
      │
      ├──►[Pillar 2: Capital Recalibration]
      │   └──► Adjust confidence-to-size mapping
      │
      ├──►[Pillar 3: Confidence Adjustment]
      │   └──► Recalibrate daily budget based on accuracy
      │
      ├──►[Golden Set Evaluation]
      │   └──► Compare strategy performance vs known-good
      │
      └──►[RGI Trainer]
          └──► LightGBM trust score model update
      │
      ├──►ALL mutations via learning_contract_enforcer
      │   └──► deny-first: explicit contract validation required
      │
      └──►[Prometheus Metrics] ── learning accuracy, drift, budget
```

---

## 4. Database Schema (Unified)

### 4.1 Existing Tables (Migrations 001-026)

| Table | Purpose | Immutable |
|-------|---------|-----------|
| signals | Ingested TradingView signals | ✅ |
| hitl_approvals | HITL approval requests + decisions | ✅ (no DELETE) |
| audit_log | Immutable audit trail | ✅ (no DELETE) |
| trade_lifecycle | Trade state machine | No |
| trade_state_transitions | State change history | ✅ |
| post_trade_snapshots | Market context at trade time | ✅ |
| deep_link_tokens | Discord deep link auth | No |
| budget_evaluations | Budget guard decisions | No |
| rgi_scores | Trust score history | No |
| strategy_blueprints | Strategy definitions | No |
| golden_set_trades | Known-good trade patterns | No |

### 4.2 New Tables (Migrations 027-033, from Legacy)

| Table | Migration | Purpose |
|-------|-----------|---------|
| learning_domain_scores | 027 | Learning domain performance tracking |
| learning_insights | 027 | Captured learning insights |
| knowledge_nodes | 027 | Knowledge graph nodes |
| curriculum_entries | 029 | Scheduled learning tasks |
| regime_observations | 029 | Market regime observations |
| decision_snapshots | 030 | Full decision context for forensic replay |
| operator_decisions | 031 | Operator decision history |
| operator_analytics | 031 | Operator performance metrics |
| counterfactual_results | 031 | What-if analysis results |
| experiment_definitions | 032 | Experiment configurations |
| experiment_rounds | 032 | Experiment iteration data |
| experiment_results | 032 | Experiment outcome data |
| learning_governance | 032 | Learning mutation governance log |
| evidence_traces | 033 | Self-awareness evidence |
| self_assessment_events | 033 | System self-assessment events |

---

## 5. Frontend Integration Architecture

### 5.1 Communication Pattern

```
Frontend (React)
    │
    ├── REST API (React Query)
    │   ├── GET endpoints (auto-refetch every 30s)
    │   ├── POST endpoints (optimistic updates)
    │   └── Auth: Bearer token in Authorization header
    │
    └── WebSocket (/ws/events)
        ├── hitl.approval_created
        ├── hitl.decision_made
        ├── guardian.status_changed
        ├── guardian.locked
        ├── trade.state_changed
        ├── trade.filled
        ├── learning.update
        ├── system.health
        └── Auth: Token in initial handshake
```

### 5.2 Frontend Serving Strategy

**Development:** Vite dev server with proxy to FastAPI backend
**Production:** Static files served by nginx in Docker (separate from FastAPI)

```yaml
# docker-compose addition
frontend:
  build:
    context: ./frontend
    dockerfile: Dockerfile
  ports:
    - "3000:80"
  depends_on:
    - bot
```

---

## 6. Security Architecture

### 6.1 Authentication Layers

| Layer | Mechanism | Scope |
|-------|-----------|-------|
| Webhook ingress | HMAC-SHA256 (timing-safe) | TradingView → bot |
| Frontend auth | Bearer token (operator ID) | Browser → API |
| VALR API | HMAC-SHA512 | Bot → VALR |
| Guardian unlock | GUARDIAN_ADMIN_TOKEN | Operator → Guardian |
| HITL decisions | HITL_ALLOWED_OPERATORS whitelist | Operator → HITL |
| DB access | Role-based (sovereign/app_trading/readonly) | App → PostgreSQL |
| Frontend CORS | Restricted to frontend origin | Browser → API |

### 6.2 Security Invariants

| Invariant | Enforcement |
|-----------|-------------|
| No float in financial math | Decimal-only in all services (Rule 2) |
| No autonomous execution | HITL_ENABLED=true, timeout=REJECT |
| No secret in source code | Env vars only, hardcoded defaults removed |
| No CORS wildcard | `allow_origins` restricted to frontend URL |
| Immutable audit trail | DB triggers + row permissions + hash chain |
| Fail-closed everything | Guardian, HITL, mode matrix, startup gate all default to REJECT/PAPER |

---

## 7. Deployment Architecture

### 7.1 Docker Compose Services (Production)

```
┌─────────────────────────────────────────────────────┐
│                     Docker Host                     │
│                                                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │    db     │  │   bot    │  │   frontend       │  │
│  │  PG 15   │  │ FastAPI  │  │   nginx + React  │  │
│  │  :5432   │  │  :8080   │  │   :3000          │  │
│  └──────────┘  └──────────┘  └──────────────────┘  │
│                                                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │prometheus│  │ grafana  │  │   ollama          │  │
│  │  :9090   │  │  :3001   │  │   GPU (1080 Ti)  │  │
│  └──────────┘  └──────────┘  └──────────────────┘  │
│                                                     │
│  ┌──────────┐  ┌──────────┐                         │
│  │ email_   │  │  aura_   │                         │
│  │ bridge   │  │  bridge  │                         │
│  └──────────┘  └──────────┘                         │
└─────────────────────────────────────────────────────┘
```

### 7.2 Volume Mounts

| Volume | Container | Path |
|--------|-----------|------|
| trade_bot_data | db | /var/lib/postgresql/data |
| trade_bot_grafana | grafana | /var/lib/grafana |
| trade_bot_prometheus | prometheus | /prometheus |
| ./data | bot | /app/data |
| ./logs | bot | /app/logs |

---

*END OF UNIFIED_ARCHITECTURE.md v1.0.0*

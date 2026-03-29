# Merge Master Plan

**Version:** 1.0.0
**Created:** 2026-03-29
**Classification:** Sovereign Tier Engineering — INTERNAL
**Merge ID:** MERGE-MASTER-001

---

## 1. Mission

Produce a unified, enterprise-grade Trade_Bot that is safer, smarter, more observable, and more usable than either prior system, with a fully connected frontend and strengthened strategy/ML capabilities.

**Core principle:** Survival > Capital Preservation > Alpha.

**Merge equation:**

```
NEW BOT (execution backbone + live trading + safety layers)
   + LEGACY BOT (learning architecture + decision forensics + analytics + strategy intelligence)
   + NEW FRONTEND (Sovereign Command Hub — rebuilt clean)
   = UNIFIED SOVEREIGN SYSTEM
```

**Non-negotiable constraints:**

- NEW bot remains core execution/safety engine
- LEGACY is intelligence/learning/analytics/UI pattern donor
- No blind file copying — architecture-first integration
- No secret contamination from legacy
- No weakening of Guardian, HITL, mode guards, Decimal-only math, or fail-closed behavior

---

## 2. Merge Principles

| # | Principle | Rationale |
|---|-----------|-----------|
| 1 | **NEW bot is the production backbone** | It has working live trading, mode matrix, startup safety gate, and Phase 0-4 validated |
| 2 | **LEGACY is the intelligence donor** | 12 learning services, 7 extra migrations, 8 Grafana dashboards — unique IP not in new bot |
| 3 | **Architecture-first, not file-first** | Same file name ≠ same code. Design interfaces before copying files |
| 4 | **Safety is non-negotiable** | No merge action may weaken Guardian, HITL, mode guards, Decimal-only math, or fail-closed defaults |
| 5 | **Secrets never cross boundaries** | Legacy .env files contain live API keys — NEVER copy, always rotate |
| 6 | **Reject dangerous defaults** | Legacy `RISK_PER_TRADE = 0.20` (20%) is lethal — must be redesigned |
| 7 | **Placeholder code must be completed or excluded** | Legacy stubs (NotImplementedError, None sessions) — the new bot already has real implementations |
| 8 | **Frontend is mandatory** | Operator must have visual control over all unified capabilities |
| 9 | **Learning informs, never executes** | ML/learning modules advise decisions — they do not bypass Guardian/HITL/execution controls |
| 10 | **Decimal-only financial math** | Rule 2 from AGENTS.md — zero floating-point in currency paths |

---

## 3. Source Systems

### 3.1 NEW Bot (Production Core)

| Attribute | Value |
|-----------|-------|
| Location | `D:\dev\repos\TRADE_BOT` |
| Version | v1.8.0 (app/main.py) / Phase 4 complete |
| Python | 3.11-slim-bookworm |
| Status | Paper trading validated, live VALR trading implemented |
| Services | 25 files, ~8,500 LOC |
| App modules | ~60 files, ~10,000 LOC |
| Migrations | 26 (001-026) |
| Tests | ~39 files, ~3,000 LOC (1,072+ passing) |
| Grafana | 4 dashboards |
| Safety layers | 14 (documented in SYSTEM_READINESS_REPORT.md) |

### 3.2 LEGACY Bot (Intelligence Donor)

| Attribute | Value |
|-----------|-------|
| Location | `\\tower.local\herman\Herman\Trade_Bot\deploy.tar.gz` |
| Version | v1.11.0 (CHANGELOG) / v1.8.0 (main.py — inconsistent) |
| Python | 3.9 |
| Status | Paper trading deployed to NAS, live trading NOT implemented |
| Services | 39 files, ~20,736 LOC |
| App modules | 59 files |
| Migrations | 33 (001-033) |
| Tests | 55 files, ~40,295 LOC (Hypothesis property tests) |
| Grafana | 12 dashboards (4 core + 8 learning) |
| Unique services | 15 files, ~5,379 LOC (learning architecture) |

### 3.3 Source Priority

```
CONFLICT RESOLUTION ORDER:
1. NEW bot implementation (always wins for execution/safety)
2. LEGACY intelligence modules (additive, behind clean interfaces)
3. LEGACY tests (patterns only — paths require adaptation)
4. LEGACY dashboards (additive for learning observability)
5. Neither system's secrets (always regenerate)
```

---

## 4. Capability Comparison Matrix

| # | Domain | NEW Bot | LEGACY Bot | Classification | Merge Action |
|---|--------|---------|------------|----------------|--------------|
| 1 | **Execution Engine** | ✅ Live VALR trading, rollout guards, 9-point preflight | ❌ `NotImplementedError` | **NEW better** | Keep NEW |
| 2 | **Paper Trading** | ✅ DemoBroker PAPER, state persistence | ✅ DemoBroker PAPER, state persistence | **Both useful** | Keep NEW (equivalent) |
| 3 | **Live Trading** | ✅ `LiveExecutionBridge`, `OrderStatusPoller`, `OrderManager` | ❌ Stubbed | **NEW better** | Keep NEW |
| 4 | **Risk Controls** | ✅ 1% equity rule, MAX_RISK_ZAR R50, circuit breaker | ⚠️ 20% risk per trade (DANGEROUS) | **NEW better** | Keep NEW, reject legacy 20% |
| 5 | **Guardian** | ✅ 1% daily hard stop, persistence, cascade | ✅ 1% daily hard stop, thread-safe | **Both useful** | Keep NEW (validated) |
| 6 | **HITL** | ✅ Full gateway, Discord integration, expiry, recovery | ✅ Full gateway, 2,652 LOC | **Both useful** | Keep NEW (Phase 2 validated) |
| 7 | **Reconciliation** | ✅ Real DB query (`_get_db_balance()`) | ❌ In-memory proxy | **NEW better** | Keep NEW |
| 8 | **Audit Trail** | ✅ Immutable (3-layer: triggers + permissions + hash chain) | ✅ Similar | **Both useful** | Keep NEW |
| 9 | **Startup Safety** | ✅ 9-check gate, fail-closed SystemExit in LIVE | ❌ None | **NEW better** | Keep NEW |
| 10 | **AI/LLM Reasoning** | ✅ AI Council (Bull/Bear), pre-trade audit | ✅ AI Council + pre-trade audit + sovereign intel | **Both useful** | Keep NEW + enhance context |
| 11 | **Bayesian Reasoning** | ❌ None | ✅ 417 LOC, belief updating, pattern fingerprints | **LEGACY better** | **EXTRACT from legacy** |
| 12 | **Learning Architecture** | ❌ None | ✅ 12 services, 7 migrations, 2 workers, 8 dashboards | **LEGACY better** | **EXTRACT from legacy** |
| 13 | **Capital Allocation** | ❌ Risk manager only | ✅ Confidence-weighted sizing (512 LOC, Decimal-only) | **LEGACY better** | **EXTRACT from legacy** |
| 14 | **Strategy Sandboxing** | ❌ None | ✅ Regime-aware forking (659 LOC) | **LEGACY better** | **EXTRACT from legacy** |
| 15 | **Operator Analytics** | ❌ None | ✅ Operator vs AI performance tracking (91 LOC) | **LEGACY better** | **EXTRACT from legacy** |
| 16 | **Decision Forensics** | ❌ None | ✅ Time-travel snapshot replay (839 LOC) | **LEGACY better** | **EXTRACT from legacy** |
| 17 | **Market Data Ingestion** | ✅ Binance/OANDA/TwelveData adapters | ✅ Same adapters | **Both useful** | Keep NEW |
| 18 | **Dashboards** | ✅ 4 core dashboards | ✅ 12 (4 core + 8 learning) | **LEGACY better** | **EXTRACT 8 learning dashboards** |
| 19 | **Frontend / Command Hub** | ❌ None | ⚠️ Referenced but code missing | **Neither sufficient** | **REBUILD from scratch** |
| 20 | **Deployment Model** | ✅ Docker (fewer services) | ✅ Docker (8 services + Ollama) | **Both useful** | Merge best compose config |
| 21 | **Observability** | ✅ Prometheus + Discord | ✅ Prometheus + Discord + WebSocket | **Both useful** | Keep NEW + add learning metrics |
| 22 | **ML Jobs / Training** | ✅ RGI trainer, golden set | ✅ RGI + learning_worker_v2 (3-pillar) | **LEGACY better** | **EXTRACT learning workers** |
| 23 | **Experiment Management** | ❌ None | ✅ Formal experiment lifecycle (172 LOC) | **LEGACY better** | **EXTRACT from legacy** |
| 24 | **Sentiment / Scraping** | ✅ Sentiment service exists | ✅ Sentiment + tv_extractor + 24 scraping targets | **LEGACY better** | **EXTRACT scraping tools** |
| 25 | **Runbooks / Operational Docs** | ✅ 6 operational docs (Phase 4) | ❌ None | **NEW better** | Keep NEW |

### Summary Classification

| Classification | Count | Domains |
|----------------|-------|---------|
| **NEW better** | 8 | Execution, live trading, risk controls, reconciliation, startup safety, runbooks, risk params, audit |
| **LEGACY better** | 10 | Bayesian, learning arch, capital alloc, sandboxing, operator analytics, forensics, dashboards, ML jobs, experiments, scraping |
| **Both useful (keep NEW)** | 7 | Paper trading, Guardian, HITL, AI reasoning, market data, deployment, observability |
| **Neither sufficient** | 1 | Frontend (must rebuild) |
| **Merge required** | 25 | All — the unified system must incorporate the best of both |

---

## 5. New Bot Capabilities To Preserve (NON-NEGOTIABLE)

These capabilities from the NEW bot are the production backbone and must NOT be weakened by any merge action:

| # | Capability | Component | Why Critical |
|---|-----------|-----------|-------------|
| 1 | Live VALR trading | `live_execution_bridge.py`, `order_status_poller.py`, `order_manager.py` | Only working live execution path |
| 2 | Mode progression matrix | `mode_matrix.py` | PAPER→DRY_RUN→LIVE_READ_ONLY→LIVE_EXECUTION, fail-closed to PAPER |
| 3 | Startup safety gate | `app/main.py` + `startup_safety_gate.py` | 9-check gate, SystemExit if LIVE prerequisites missing |
| 4 | 14 safety layers | Documented in SYSTEM_READINESS_REPORT.md | HMAC→Pydantic→Idempotency→Budget→Risk→AI→HITL→Guardian→Circuit→Kill→Mode→Startup→Bridge→Audit |
| 5 | FastAPI lifespan wiring | `app/main.py` (900 LOC) | 13-step startup sequence, recovery, expiry worker |
| 6 | Immutable audit trail | 3-layer (DB triggers + permissions + SHA-256 chain hash) | Cannot DELETE from hitl_approvals or audit_log |
| 7 | Guardian integration | `guardian_service.py` + `guardian_integration.py` | 1% daily hard stop, cascade rejection, persistence |
| 8 | HITL gateway | `hitl_gateway.py` + 7 supporting files | Approval creation, decision processing, recovery, timeout |
| 9 | Decimal-only financial math | `decimal_gateway.py`, all services | ROUND_HALF_EVEN, no floating-point |
| 10 | Rollout limits | `live_execution_bridge.py` | R500/order, 5/day, R2500/day, 3/symbol |
| 11 | Operational runbooks | 6 documents in DOCS/ | VALR onboarding, funding, first trade, post-trade review |
| 12 | Equity source | `equity_source.py` | Mode-aware equity retrieval, fail-closed to None |
| 13 | Runtime registry | `app/core/runtime.py` | 6 singletons, breaks circular imports |
| 14 | Phase 0-4 validation | 1,072+ tests passing | Proven foundation |

---

## 6. Legacy Capabilities To Extract

### 6.1 EXTRACT — Integrate Into New Bot

| # | Service | LOC | Status | Integration Priority | Effort |
|---|---------|-----|--------|---------------------|--------|
| 1 | `bayesian_reasoning_service.py` | 417 | COMPLETE | HIGH — foundation of intelligence layer | Medium |
| 2 | `capital_allocation_service.py` | 512 | COMPLETE | HIGH — confidence-weighted sizing | Medium |
| 3 | `confidence_budget_service.py` | 193 | COMPLETE | HIGH — prevents overtrading | Low |
| 4 | `decision_snapshot_service.py` | 839 | COMPLETE | HIGH — forensic replay | Medium |
| 5 | `regime_sandbox_service.py` | 659 | COMPLETE | HIGH — per-regime sandboxing | Medium |
| 6 | `mind_state_service.py` | 190 | PARTIAL | MEDIUM — fix hardcoded proximity | Low |
| 7 | `mind_state_policy_enforcer.py` | 109 | COMPLETE | MEDIUM — state-based restrictions | Low |
| 8 | `operator_analytics_service.py` | 91 | COMPLETE | MEDIUM — operator evaluation | Low |
| 9 | `experiment_service.py` | 172 | COMPLETE | MEDIUM — experiment framework | Low |
| 10 | `learning_contract_enforcer.py` | 222 | COMPLETE | MEDIUM — deny-first mutations | Low |
| 11 | `counterfactual_simulator.py` | 255 | PARTIAL | LOW — temporal shift needs work | Medium |
| 12 | `curriculum_scheduler.py` | 606 | PARTIAL | LOW — 6 task stubs | High (needs rewrite) |
| **Total** | | **4,265** | | | |

### 6.2 EXTRACT — Jobs

| Job | LOC | Status | Priority |
|-----|-----|--------|----------|
| `learning_worker_v2.py` | 815 | COMPLETE | HIGH — 3-pillar learning loop |
| `learning_worker.py` | 369 | COMPLETE | LOW — superseded by v2 |

### 6.3 EXTRACT — Tools

| Tool | LOC | Status | Priority |
|------|-----|--------|----------|
| `tv_extractor.py` | 696 | COMPLETE | MEDIUM — TradingView scraping |
| `sentiment_harvester.py` | 733 | COMPLETE | MEDIUM — keyword-density sentiment |

### 6.4 EXTRACT — Database Migrations

All 7 migrations (027-033) required for learning architecture:

- 027: learning_domain_scores, learning_insights, knowledge_nodes
- 028: learning worker tables
- 029: curriculum_entries, regime_observations
- 030: decision_snapshots
- 031: operator_decisions, operator_analytics, counterfactual_results
- 032: experiment_definitions, experiment_rounds, experiment_results, learning_governance
- 033: evidence_traces, self_assessment_events

### 6.5 EXTRACT — Grafana Dashboards

8 learning dashboards:

- learning-boundary.json
- learning-capital-allocation.json
- learning-cognitive-state.json
- learning-curriculum-progress.json
- learning-knowledge-intake.json
- learning-pattern-evolution.json
- learning-reasoning-timeline.json
- learning-regime-sandbox.json

### 6.6 DO NOT EXTRACT

| Item | Reason |
|------|--------|
| `broadcaster.py` (817 LOC) | Frontend-specific WebSocket — rebuild clean for new frontend |
| `sovereign_ws_bridge.py` (204 LOC) | Frontend WebSocket bridge — rebuild clean |
| `ws_events.py` (93 LOC) | Event definitions — rebuild for new architecture |
| `golden_set_strategy.py` (0 LOC) | Empty placeholder file |
| `.env`, `.env.nas.*` | Live secrets — NEVER copy |
| 22 shared services | NEW bot versions are validated — do not replace |
| `main.py` (orchestrator) | Steps 3-5 broken, new bot's is better |
| Legacy `exchange/order_manager.py` | Raises NotImplementedError — new bot has real implementation |
| Legacy `exchange/reconciliation.py` | In-memory proxy — new bot has real DB query |
| `logic/dispatcher.py` | 20% risk per trade — DANGEROUS |
| `logic/production_safety.py` | Hardcoded FX rate Decimal("18.50") |

---

## 7. Frontend Recovery / Rebuild Plan

### 7.1 Assessment

The legacy Sovereign Command Hub (Next.js 14) was documented in README/PRD with 10 routes and 159 Vitest tests, but **no frontend source code exists** in the deploy archive. The frontend must be rebuilt from scratch.

### 7.2 Technology Decision

| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| Next.js 14 (App Router) | SSR, React ecosystem, referenced in legacy | Heavy, complex deployment | ❌ Rejected — overkill for operator dashboard |
| React + Vite | Fast dev, rich ecosystem, SPA | No SSR (not needed) | ✅ **SELECTED** |
| Vue/Svelte | Lighter | Smaller ecosystem for financial UI | ❌ |

**Stack:** React 18 + TypeScript + Vite + Tailwind CSS + shadcn/ui + React Query + Recharts

**Rationale:**

- React + Vite: Fast development, simple deployment (static files served by FastAPI or nginx)
- TypeScript: Type safety for financial data
- Tailwind + shadcn/ui: Professional, accessible components without custom CSS maintenance
- React Query: Server state management with automatic refetching
- Recharts: Financial charting (compatible with Decimal display)

### 7.3 Required Views (15 Minimum)

| # | View | Backend Source | Category |
|---|------|---------------|----------|
| 1 | Login / Operator Auth | `app/auth/security.py` (Bearer token) | Auth |
| 2 | System Overview Dashboard | `/health`, `/guardian/status`, `/budget/status` | Core |
| 3 | Guardian Status & Controls | `/guardian/status`, `/guardian/unlock` | Safety |
| 4 | HITL Approval Inbox | `/api/hitl/pending`, `/api/hitl/{id}/approve`, `/api/hitl/{id}/reject` | Safety |
| 5 | Trade History / Lifecycle Timeline | New API: `/api/trades/history` | Core |
| 6 | Paper Trading View | `/budget/status`, DemoBroker state | Core |
| 7 | Live Readiness / Preflight | New API: `/api/preflight/status` | Safety |
| 8 | Strategy Management | New API: `/api/strategies/list` | Strategy |
| 9 | Learning / ML Dashboard | New API: `/api/learning/status` | Intelligence |
| 10 | Decision Forensics View | New API: `/api/decisions/snapshots` | Intelligence |
| 11 | Operator Analytics | New API: `/api/analytics/operator` | Intelligence |
| 12 | Experiments / Sandbox / Regime | New API: `/api/experiments/list`, `/api/regimes/status` | Intelligence |
| 13 | Market / Data Feed Health | New API: `/api/market/health` | Operations |
| 14 | Settings / Mode Matrix / Config | New API: `/api/config/current` | Operations |
| 15 | Logs / Audit / Observability | New API: `/api/audit/log`, `/metrics` | Operations |

### 7.4 Backend API Requirements (New Endpoints)

The current backend has 12 endpoints. The frontend requires approximately 10 additional API routes:

| Endpoint | Method | Purpose | Source Data |
|----------|--------|---------|-------------|
| `/api/trades/history` | GET | Trade lifecycle history | `trade_lifecycle` table |
| `/api/trades/{id}/detail` | GET | Full trade detail + snapshots | `trade_lifecycle` + `decision_snapshots` |
| `/api/preflight/status` | GET | Live readiness checks | `startup_safety_gate` equivalent |
| `/api/strategies/list` | GET | Active strategies | `strategy_store` |
| `/api/learning/status` | GET | Learning architecture status | Learning tables (027-033) |
| `/api/learning/bayesian` | GET | Bayesian reasoning state | `bayesian_reasoning_service` |
| `/api/decisions/snapshots` | GET | Decision forensics | `decision_snapshots` table |
| `/api/analytics/operator` | GET | Operator performance | `operator_analytics` table |
| `/api/experiments/list` | GET | Experiment status | `experiment_definitions` table |
| `/api/regimes/status` | GET | Market regime state | `regime_observations` table |
| `/api/config/current` | GET | System configuration | Env vars (redacted) |
| `/api/audit/log` | GET | Audit trail query | `audit_log` table |
| `/api/market/health` | GET | Data feed health | Provider factory status |

### 7.5 Real-Time Requirements

| Feature | Transport | Source |
|---------|-----------|--------|
| HITL approval notifications | WebSocket | `hitl_websocket_emitter.py` |
| Guardian status changes | WebSocket | `guardian_integration.py` |
| Trade state transitions | WebSocket | `trade_lifecycle.py` |
| Live P&L updates | WebSocket (polling fallback) | `demo_broker.py` / VALR |
| System health | SSE / polling | `/health` endpoint |

### 7.6 Frontend Directory Structure

```
frontend/
├── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts
├── tailwind.config.ts
├── postcss.config.js
├── src/
│   ├── main.tsx
│   ├── App.tsx
│   ├── api/                    # API client layer
│   │   ├── client.ts           # Axios/fetch wrapper with auth
│   │   ├── hooks.ts            # React Query hooks
│   │   └── types.ts            # API response types
│   ├── components/
│   │   ├── layout/             # Shell, sidebar, header
│   │   ├── ui/                 # shadcn/ui components
│   │   ├── dashboard/          # Dashboard widgets
│   │   ├── hitl/               # HITL approval components
│   │   ├── guardian/           # Guardian status components
│   │   ├── trades/             # Trade history components
│   │   ├── learning/           # Learning dashboard components
│   │   ├── forensics/          # Decision forensics components
│   │   ├── strategy/           # Strategy management components
│   │   └── charts/             # Recharts wrappers
│   ├── pages/                  # Route pages (15 views)
│   ├── hooks/                  # Custom hooks
│   ├── stores/                 # Zustand stores (auth, websocket)
│   ├── utils/                  # Formatting, Decimal display
│   └── types/                  # TypeScript types
└── public/
```

---

## 8. Merge Architecture Target State

### 8.1 Unified Layer Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                        FRONTEND LAYER                               │
│  React + TypeScript + Tailwind                                      │
│  15 views: Dashboard, HITL, Guardian, Trades, Learning, Forensics   │
│  Transport: REST API + WebSocket                                    │
└──────────────────┬────────────────────────────────────────────────────┘
                   │ HTTPS / WS
                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│                      FRONTEND API LAYER                             │
│  app/api/frontend.py — new routes for frontend consumption          │
│  app/api/webhook.py — existing TradingView ingress                  │
│  app/api/hitl.py — existing HITL endpoints                          │
│  app/api/guardian.py — existing Guardian endpoints                   │
│  Auth: Bearer token (existing) + session management                 │
└──────────────────┬────────────────────────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│                     SIGNAL INGRESS LAYER                            │
│  TradingView webhook → HMAC verify → Pydantic validate → DB INSERT  │
│  Email bridge → Gmail IMAP → webhook (TV Free Tier bypass)          │
│  Cloudflare tunnel (optional)                                        │
└──────────────────┬────────────────────────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    AI REASONING LAYER                                │
│  ai_council.py          — Bull/Bear LLM debate (OpenRouter/Ollama)  │
│  pre_trade_audit.py     — DeepSeek-R1 adversarial challenge         │
│  sovereign_intel.py     — Context enrichment + similar trade lookup  │
│  debate_memory.py       — RAG debate storage                        │
│  sentiment_service.py   — Market sentiment aggregation              │
│  tv_extractor.py        — TradingView web scraping [FROM LEGACY]    │
│  sentiment_harvester.py — Keyword-density scoring [FROM LEGACY]     │
└──────────────────┬────────────────────────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│                   BAYESIAN REASONING LAYER  [FROM LEGACY]           │
│  bayesian_reasoning_service.py  — Belief updating + pattern fingerprints│
│  confidence_budget_service.py   — Daily-renewable confidence          │
│  capital_allocation_service.py  — Confidence-weighted position sizing │
│  mind_state_service.py          — CALM/ALERT/DEFENSIVE derivation    │
│  mind_state_policy_enforcer.py  — State-based trading restrictions   │
│                                                                      │
│  ⚠️ ADVISORY ONLY — these services INFORM decisions, never BYPASS    │
│     Guardian, HITL, or execution controls                            │
└──────────────────┬────────────────────────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│                     STRATEGY LAYER                                   │
│  strategy_manager.py        — Deterministic strategy evaluation      │
│  strategy_store.py          — Blueprint storage + fingerprinting     │
│  regime_sandbox_service.py  — Per-regime strategy forking [LEGACY]   │
│  canonicalizer.py           — DSL canonicalization                   │
│  dsl_schema.py              — Strategy DSL schema                    │
│  golden_set_integration.py  — Strategy validation harness            │
└──────────────────┬────────────────────────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│                      RISK LAYER                                      │
│  risk_manager.py          — 1% equity rule, MAX_RISK_ZAR cap         │
│  budget_integration.py    — BudgetGuard financial air-gap             │
│  circuit_breaker.py       — 3% daily / 3 consecutive losses          │
│  slippage_guard.py        — Slippage validation                      │
│  dispatcher.py            — Decision routing (trust ≥ 0.6000)        │
│  production_safety.py     — Equity module + kill switch              │
└──────────────────┬────────────────────────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│                GUARDIAN / HITL LAYER (NEW BOT — AUTHORITATIVE)       │
│  guardian_service.py         — 1% daily hard stop, persistence       │
│  guardian_integration.py     — Cascade rejection                     │
│  hitl_gateway.py             — Approval creation, decision, recovery │
│  discord_hitl_service.py     — Discord buttons + deep links          │
│  hitl_state_machine.py       — State transitions                     │
│  hitl_config.py              — Configuration                         │
│  hitl_models.py              — ApprovalRequest + RowHasher           │
│  hitl_expiry_worker.py       — Timeout enforcement                   │
│  hitl_websocket_emitter.py   — Real-time events                      │
│  hitl_observability.py       — Logging + metrics                     │
└──────────────────┬────────────────────────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│                   EXECUTION LAYER (NEW BOT — AUTHORITATIVE)          │
│  execution_service.py         — SafetyGate (trust ≥ 0.6000)         │
│  execution_bridge.py          — Post-approval execution orchestration│
│  live_execution_bridge.py     — 9-point preflight, rollout guards    │
│  order_manager.py (exchange/) — Live VALR order placement            │
│  order_status_poller.py       — Fill/cancel tracking                 │
│  mode_matrix.py               — 4-mode fail-closed to PAPER          │
│  equity_source.py             — Mode-aware equity retrieval          │
│  demo_broker.py               — Paper trading fills                  │
│  valr_client.py               — VALR API integration                 │
│  decimal_gateway.py           — Decimal conversion                   │
│  hmac_signer.py               — VALR HMAC-SHA512                     │
│  rate_limiter.py              — Token bucket (600/min)               │
│  reconciliation.py            — Balance verification                 │
└──────────────────┬────────────────────────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│                POST-TRADE / FORENSICS LAYER [FROM LEGACY]           │
│  trade_lifecycle.py           — State machine (existing)             │
│  decision_snapshot_service.py — Time-travel replay [LEGACY]          │
│  counterfactual_simulator.py  — What-if analysis [LEGACY]            │
│  operator_analytics_service.py — Operator performance [LEGACY]       │
└──────────────────┬────────────────────────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│                   LEARNING LAYER [FROM LEGACY]                       │
│  learning_contract_enforcer.py — Deny-first mutation enforcement     │
│  curriculum_scheduler.py       — Learning task scheduling            │
│  experiment_service.py         — Formal experiment management        │
│  learning_worker_v2.py         — 3-pillar learning loop              │
│  train_reward_governor.py      — RGI model training                  │
│  rgi_aggregator.py             — RGI decision aggregation            │
│                                                                      │
│  ⚠️ LEARNING WRITES are governed by learning_contract_enforcer       │
│     All mutations require explicit contract validation                │
└──────────────────┬────────────────────────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│                  OBSERVATION LAYER                                    │
│  Prometheus metrics (30+ counters/gauges)                            │
│  Grafana dashboards (4 core + 8 learning) [LEARNING FROM LEGACY]    │
│  Discord notifications (startup, shutdown, trades, Guardian events)  │
│  WebSocket events (HITL, Guardian, trades) → Frontend                │
│  Structured logging (L6 compliant)                                   │
└──────────────────────────────────────────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│                 DATA LAYER (PostgreSQL 15)                           │
│  Migrations 001-026 (existing, validated)                            │
│  Migrations 027-033 (from legacy — learning architecture tables)     │
│  Immutable audit (triggers + permissions + hash chain)               │
│  Roles: sovereign (DDL), app_trading (DML), aura_readonly (read)    │
└──────────────────────────────────────────────────────────────────────┘
```

### 8.2 Integration Rules

| Rule | Detail |
|------|--------|
| **Legacy services are ADVISORY** | Bayesian, mind state, capital allocation output recommendations — they never execute trades |
| **All execution routes through NEW bot layers** | Guardian → HITL → ExecutionService → Broker — no shortcuts |
| **Learning writes governed by contract** | `learning_contract_enforcer.py` gates all learning DB mutations |
| **Frontend reads only** | Frontend calls GET endpoints + WebSocket. Mutations only via authenticated POST to existing endpoints |
| **WebSocket replaces polling** | Frontend receives real-time events via WebSocket (HITL, Guardian, trades, learning) |
| **Decimal display in frontend** | All financial values transmitted as strings, converted to display format in frontend |

---

## 9. Merge Phases

### Phase 1: Database Schema Extension (migrations 027-033)

| Step | Action | Risk |
|------|--------|------|
| 1.1 | Read legacy migrations 027-033 from deploy archive | None |
| 1.2 | Adapt SQL to new bot's migration conventions (naming, permissions) | Low |
| 1.3 | Create 027-033 in `database/migrations/` | Low |
| 1.4 | Test migration application on clean DB | Low |
| 1.5 | Verify table creation with `\dt` check | None |

### Phase 2: Backend Service Integration

| Step | Action | Risk |
|------|--------|------|
| 2.1 | Create `services/intelligence/` subdirectory for legacy services | None |
| 2.2 | Port bayesian_reasoning_service.py (fix missing `import json`) | Low |
| 2.3 | Port capital_allocation_service.py (verify Decimal-only) | Low |
| 2.4 | Port confidence_budget_service.py | Low |
| 2.5 | Port decision_snapshot_service.py | Low |
| 2.6 | Port regime_sandbox_service.py | Low |
| 2.7 | Port mind_state_service.py (fix hardcoded Guardian proximity) | Medium |
| 2.8 | Port mind_state_policy_enforcer.py | Low |
| 2.9 | Port operator_analytics_service.py | Low |
| 2.10 | Port experiment_service.py | Low |
| 2.11 | Port learning_contract_enforcer.py | Low |
| 2.12 | Port counterfactual_simulator.py (stub temporal shift, mark TODO) | Medium |
| 2.13 | Verify all ports use Decimal-only math | Critical |
| 2.14 | Verify no legacy DB sessions — all use new bot's session factory | Critical |

### Phase 3: Learning Jobs Integration

| Step | Action | Risk |
|------|--------|------|
| 3.1 | Port `jobs/learning_worker_v2.py` | Medium |
| 3.2 | Adapt DB session imports to new bot conventions | Low |
| 3.3 | Verify learning worker respects `learning_contract_enforcer` | Critical |
| 3.4 | Port `tools/tv_extractor.py` and `tools/sentiment_harvester.py` | Low |

### Phase 4: Frontend API Layer

| Step | Action | Risk |
|------|--------|------|
| 4.1 | Create `app/api/frontend.py` with ~13 new GET endpoints | Low |
| 4.2 | Add WebSocket hub for real-time events | Low |
| 4.3 | Add auth middleware for frontend routes | Medium |
| 4.4 | Test all endpoints return correct data shapes | Medium |

### Phase 5: Frontend Build

| Step | Action | Risk |
|------|--------|------|
| 5.1 | Initialize React + Vite + TypeScript project in `frontend/` | None |
| 5.2 | Install dependencies (Tailwind, shadcn/ui, React Query, Recharts) | None |
| 5.3 | Build shell layout (sidebar, header, auth wrapper) | Low |
| 5.4 | Build 15 views (see Section 7.3) | Medium |
| 5.5 | Connect to backend APIs via React Query hooks | Medium |
| 5.6 | Connect WebSocket for real-time updates | Medium |
| 5.7 | Test all views with real backend data | Medium |

### Phase 6: Grafana Dashboard Integration

| Step | Action | Risk |
|------|--------|------|
| 6.1 | Copy 8 learning dashboards to `grafana/dashboards/` | None |
| 6.2 | Verify Prometheus metric names match new bot's metric registry | Low |
| 6.3 | Add learning-specific Prometheus counters/gauges | Low |

### Phase 7: Docker Compose Update

| Step | Action | Risk |
|------|--------|------|
| 7.1 | Add frontend service to docker-compose | Low |
| 7.2 | Update Grafana provisioning for new dashboards | Low |
| 7.3 | Add Ollama service configuration (from legacy) | Low |
| 7.4 | Verify full stack boots | Medium |

### Phase 8: Validation

| Step | Action | Risk |
|------|--------|------|
| 8.1 | Run existing test suite (1,072+ tests) | None |
| 8.2 | Write unit tests for ported intelligence services | Low |
| 8.3 | Write integration tests for new API endpoints | Medium |
| 8.4 | Test frontend end-to-end | Medium |
| 8.5 | Verify HITL still enforced | Critical |
| 8.6 | Verify Guardian still enforced | Critical |
| 8.7 | Verify mode matrix still safe | Critical |
| 8.8 | Verify no secret contamination | Critical |

### Phase 9: X-Factor Confidence Features

| Step | Action | Risk |
|------|--------|------|
| 9.1 | Strategy explainability panel | Low |
| 9.2 | Decision reason codes visible in frontend | Low |
| 9.3 | Bayesian confidence trace view | Low |
| 9.4 | Trade replay / time-travel forensic viewer | Medium |
| 9.5 | Paper-vs-live readiness comparison | Low |
| 9.6 | Startup self-test dashboard | Low |
| 9.7 | AI/backend health dashboard | Low |

---

## 10. Strategy & ML Priority Plan

### 10.1 Strategy Architecture

```
┌─────────────────────────────────────────────────────┐
│              STRATEGY REGISTRY                       │
│  ┌─────────────────────────────────────────────┐    │
│  │ strategy_manager.py (EXISTING — deterministic)│    │
│  │ strategy_store.py (EXISTING — blueprint store)│    │
│  │ canonicalizer.py (EXISTING — DSL validation)  │    │
│  │ dsl_schema.py (EXISTING — 30+ nested classes) │    │
│  │ golden_set_integration.py (EXISTING — harness)│    │
│  └─────────────────────────────────────────────┘    │
│                                                      │
│  ┌─────────────────────────────────────────────┐    │
│  │ regime_sandbox_service.py [FROM LEGACY]      │    │
│  │   → Strategies fork per market regime        │    │
│  │   → Sandbox trades never execute live        │    │
│  │   → 8 market regimes supported               │    │
│  └─────────────────────────────────────────────┘    │
│                                                      │
│  ┌─────────────────────────────────────────────┐    │
│  │ bayesian_reasoning_service.py [FROM LEGACY]  │    │
│  │   → Pattern fingerprinting                    │    │
│  │   → Belief updating from trade outcomes       │    │
│  │   → RAG reasoning from historical evidence    │    │
│  └─────────────────────────────────────────────┘    │
│                                                      │
│  ┌─────────────────────────────────────────────┐    │
│  │ capital_allocation_service.py [FROM LEGACY]  │    │
│  │   → Position size = f(confidence, base_size) │    │
│  │   → Confidence earned via Bayesian reasoning  │    │
│  │   → Decimal-only math                        │    │
│  └─────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────┘
```

### 10.2 Strategy Execution Flow (Post-Merge)

```
Signal arrives → Canonicalize → DSL validate
                    │
                    ▼
            Strategy Manager evaluates:
            ├─→ Deterministic rules (EXISTING)
            ├─→ Regime context (FROM LEGACY)
            │   └─→ Which strategy set for current regime?
            ├─→ Golden Set validation (EXISTING)
            │   └─→ Signal matches known-good pattern?
            │
            ▼
            Bayesian Reasoning (FROM LEGACY):
            ├─→ Pattern fingerprint match
            ├─→ Belief update from similar setups
            ├─→ Confidence score derivation
            │
            ▼
            Capital Allocation (FROM LEGACY):
            ├─→ Position size = confidence × base
            ├─→ Confidence budget check (daily renewable)
            │   └─→ Budget exhausted? → REFUSE
            │
            ▼
            Mind State Check (FROM LEGACY):
            ├─→ CALM: normal trading allowed
            ├─→ ALERT: reduced position sizing
            ├─→ DEFENSIVE: only close positions
            │
            ▼
            Existing Risk Layer (UNCHANGED):
            ├─→ 1% equity rule
            ├─→ MAX_RISK_ZAR R50
            ├─→ Circuit breaker
            ├─→ Guardian check
            │
            ▼
            HITL Approval (UNCHANGED)
```

### 10.3 ML Training Pipeline

```
Trade Outcome
    │
    ├─→ trade_learning.py (EXISTING — record outcome)
    ├─→ rlhf_feedback.py (EXISTING — feedback signal)
    ├─→ decision_snapshot_service.py [LEGACY] — full decision context
    │
    ▼
Learning Worker v2 [LEGACY] (background job):
    ├─→ Pillar 1: Bayesian update (pattern fingerprints)
    ├─→ Pillar 2: Capital allocation recalibration
    ├─→ Pillar 3: Confidence budget adjustment
    │
    ├─→ All mutations via learning_contract_enforcer [LEGACY]
    │   └─→ Deny-first: must pass contract validation
    │
    ├─→ Golden Set evaluation (EXISTING)
    │   └─→ Strategy performance against known-good set
    │
    ▼
RGI Trainer (EXISTING):
    ├─→ Trust score synthesis from all evidence
    └─→ LightGBM model update
```

### 10.4 Strategy Quality Principles

| Principle | Implementation |
|-----------|---------------|
| No magical profit claims | Strategies are evidence-backed via golden set evaluation |
| Interpretability | All decision paths logged with reason codes |
| Disciplined controls | Confidence budget prevents overtrading; regime awareness prevents wrong-context execution |
| Testability | Golden set validation harness tests strategies against known-good patterns |
| Operator inspection | Frontend strategy view shows all active strategies, their regimes, confidence, and outcomes |
| No autonomous escalation | Learning output is advisory — operator must approve via HITL |

---

## 11. Risks and Non-Merge Items

### 11.1 Explicit Rejection List

| Item | Reason for Rejection | Risk if Included |
|------|---------------------|------------------|
| **Legacy .env files** | Contain 9+ live secrets (VALR keys, Gmail password, Binance keys) | Critical security breach |
| **Legacy .env.nas.FILL_ME_IN** | Same secrets + 24 scraping target URLs | Secret contamination |
| **Legacy .env.example** | Default password `sovereign_secret_2024` | Weak default |
| **`logic/dispatcher.py` RISK_PER_TRADE=0.20** | 20% risk per trade would destroy capital in 5 trades | Capital destruction |
| **`logic/production_safety.py` FX_RATE=18.50** | Hardcoded, stale USD/ZAR rate | Incorrect calculations |
| **`exchange/order_manager.py` (legacy)** | `_execute_live_order()` raises NotImplementedError | No live trading |
| **`exchange/reconciliation.py` (legacy)** | `_get_db_balance()` returns in-memory proxy | No real reconciliation |
| **`exchange/rlhf_recorder.py` (legacy)** | ML recording commented out | No RLHF data collection |
| **`main.py` orchestrator (legacy)** | Steps 3-5 use None DB sessions — crashes on execution | System crash |
| **`golden_set_strategy.py`** | 0 bytes — empty placeholder | No value |
| **`broadcaster.py`** | Frontend WebSocket — will rebuild for new frontend | Wrong architecture |
| **`sovereign_ws_bridge.py`** | Legacy frontend bridge — wrong protocol for new stack | Wrong architecture |
| **`ws_events.py`** | Legacy event definitions — will define new ones | Wrong architecture |
| **`strategy_store.py` fallback HMAC** | Hardcoded `sovereign_strategy_fingerprint_2024` | Secret in source |
| **`database/session.py` default password** | Hardcoded `trading_app_2024` | Secret in source |
| **`infra/aura_client.py` HMAC** | Hardcoded `PREDICTION_HMAC_SECRET` | Secret in source |
| **Legacy CORS `allow_origins=["*"]`** | Wide-open CORS allows any origin | Security vulnerability |
| **`curriculum_scheduler.py` task stubs (6 methods)** | Cannot execute — must redesign, not copy stubs | False functionality claims |
| **`mind_state_service.py` hardcoded proximity** | Guardian proximity placeholder — must be wired to real Guardian API | Incorrect mind state |
| **`counterfactual_simulator.py` temporal shift** | Placeholder — mark as TODO, don't claim it works | False functionality |

### 11.2 Secrets Rotation Checklist

| Secret | Action Required | Status |
|--------|----------------|--------|
| VALR API key/secret | Rotate immediately on VALR dashboard | ⬜ Pending |
| Binance testnet key/secret | Rotate or revoke | ⬜ Pending |
| Discord webhook URL | Regenerate in Discord server settings | ⬜ Pending |
| Gmail app password | Regenerate in Google account | ⬜ Pending |
| SOVEREIGN_SECRET | Generate new 32+ char random | ⬜ Pending |
| GUARDIAN_RESET_CODE | Change from `HaloTrade` | ⬜ Pending |
| DB password | Already generated new (per SYSTEM_READINESS_REPORT) | ✅ Done |
| Hardcoded HMAC keys in source | Replace with env var references | ⬜ Pending |

### 11.3 Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| Merge introduces float math in financial paths | CRITICAL | Audit all ported services for float usage — enforce Decimal |
| Learning services access execution paths | CRITICAL | Learning is ADVISORY ONLY — enforce via interface design |
| Frontend bypasses HITL | HIGH | Frontend can only call existing authenticated endpoints |
| Ported services incompatible with DB session model | HIGH | All ports must use new bot's `get_db()` session factory |
| New dependencies break test suite | MEDIUM | Run full test suite after each merge step |
| Grafana dashboards reference missing metrics | LOW | Verify metric names match after dashboard copy |
| Frontend build increases Docker image size | LOW | Frontend served as static files — separate build step |

---

## 12. File Change Log

*This section will be updated as merge implementation proceeds.*

| Date | File | Action | Description |
|------|------|--------|-------------|
| 2026-03-29 | MERGE_MASTER_PLAN.md | Created | Master merge planning document |
| | UNIFIED_ARCHITECTURE.md | Pending | Detailed architecture document |
| | FRONTEND_REBUILD_PLAN.md | Pending | Frontend build specification |
| | STRATEGY_ML_INTEGRATION_PLAN.md | Pending | Strategy/ML integration details |

---

## 13. Validation Evidence

*This section will be populated during implementation.*

### 13.1 Pre-Merge Baseline

| Metric | Value |
|--------|-------|
| Tests passing (pre-merge) | 1,072+ |
| Safety layers | 14 |
| API endpoints | 12 |
| Migrations | 26 |
| Frontend views | 0 |

### 13.2 Post-Merge Target

| Metric | Target |
|--------|--------|
| Tests passing | 1,072+ (existing) + new tests for ported services |
| Safety layers | 14 (unchanged — no weakening) |
| API endpoints | 12 (existing) + ~13 (frontend) = ~25 |
| Migrations | 26 + 7 (learning) = 33 |
| Frontend views | 15 |
| Intelligence services | +12 (from legacy) |
| Grafana dashboards | 4 (existing) + 8 (learning) = 12 |

---

## 14. Final Unified System Verdict

*This section will be completed after merge implementation.*

### Current Classification: **FOUNDATION READY**

The merge plan is complete with:

- ✅ Rigorous capability comparison (25 domains evaluated)
- ✅ Explicit rejection list (20 items with reasons)
- ✅ Target architecture designed (11 layers)
- ✅ Merge phases defined (9 phases, 40+ steps)
- ✅ Frontend rebuild plan (15 views, 13 new API endpoints)
- ✅ Strategy/ML integration plan (3-pillar learning + regime sandboxing)
- ✅ Security rules enforced (secrets rotation checklist, no contamination)
- ✅ Validation criteria defined (pre/post metrics)

### Capabilities Preserved from NEW

| # | Capability |
|---|-----------|
| 1 | Live VALR trading (LiveExecutionBridge, OrderStatusPoller) |
| 2 | Mode progression matrix (PAPER→DRY_RUN→LIVE_READ_ONLY→LIVE) |
| 3 | Startup safety gate (9 checks, fail-closed) |
| 4 | 14 safety layers (all preserved) |
| 5 | Guardian hard stop (1% daily, cascade rejection) |
| 6 | HITL gateway (approval, decision, recovery, timeout) |
| 7 | Immutable audit trail (3-layer) |
| 8 | Decimal-only financial math |
| 9 | Rollout limits (R500/order, 5/day, R2500/day) |
| 10 | 6 operational runbooks |
| 11 | 1,072+ validated tests |
| 12 | Runtime registry (circular import solution) |

### Capabilities Extracted from LEGACY

| # | Capability |
|---|-----------|
| 1 | Bayesian reasoning (belief updating, pattern fingerprints) |
| 2 | Confidence budgets (daily-renewable, prevents overtrading) |
| 3 | Capital allocation (confidence-weighted position sizing) |
| 4 | Regime sandboxing (per-regime strategy forking) |
| 5 | Decision forensics (time-travel snapshot replay) |
| 6 | Operator analytics (performance vs AI baseline) |
| 7 | Mind state system (CALM/ALERT/DEFENSIVE) |
| 8 | Experiment management (formal lifecycle) |
| 9 | Learning contract enforcement (deny-first mutations) |
| 10 | Learning worker v2 (3-pillar + RLHF) |
| 11 | 7 database migrations (learning tables) |
| 12 | 8 Grafana learning dashboards |
| 13 | TradingView scraper + sentiment harvester |

### Capabilities Intentionally Rejected

20 items (see Section 11.1) — all with documented reasons.

---

*END OF MERGE MASTER PLAN v1.0.0*
*Next: Create UNIFIED_ARCHITECTURE.md, FRONTEND_REBUILD_PLAN.md, STRATEGY_ML_INTEGRATION_PLAN.md*

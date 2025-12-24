# 📑 PRD: Project Autonomous Alpha (v1.8.0)
**Codename:** Sovereign Tier Infrastructure  
**Status:** DEFINITIVE / PHASE 2 HARD REQUIREMENTS COMPLETE  
**Assurance Level:** 100% Confidence (Sovereign Tier Verified)  
**Last Updated:** 2025-12-23

---

## 1. Executive Summary
Project Autonomous Alpha is a mission-critical, high-reliability AI-augmented trading appliance. It is engineered to ingest TradingView signals and execute them across Crypto/Forex markets with an uncompromising focus on capital preservation.

### The Sovereign Mandate
> **Survival > Capital Preservation > Alpha.**
> If any logic node returns < 95% confidence, the system defaults to a **Neutral (Cash) State**.

---

## 2. Technical Stack

### 2.1 Hardware Infrastructure
| Component | Specification | Purpose |
|-----------|---------------|---------|
| CPU | i7-9700K | Hot Path (Deterministic Execution) |
| RAM | 64GB | State Management |
| GPU | RTX 2080 | Cold Path AI + Local LLM Inference |
| NAS | Synology (20GB RAM) | MCP Gateway + Docker Containers |

### 2.2 Software Stack
| Layer | Technology | Notes |
|-------|------------|-------|
| Ingress | FastAPI + Uvicorn | < 50ms webhook acknowledgment |
| Logic | Python 3.11 (100% decimal.Decimal) | Zero Floats Mandate |
| Intelligence | Ollama (DeepSeek-R1, Llama3.1, Phi3.5, Qwen2.5-coder) | RTX 2080 GPU |
| Persistence | PostgreSQL | Immutable WAL logs, 22 migrations |
| Messaging | Redis Streams | Async durability |
| Vector DB | RAG via Aura MCP | Sovereign Intelligence |
| ML Layer | RLHF feedback loop | MCP tools integration |
| Exchange | VALR | South African Crypto Exchange |

### 2.3 Active ML Models (NAS)
| Model | RAM | Purpose | Status |
|-------|-----|---------|--------|
| llama3.1:8b | 5GB | Context/Concierge | Always Loaded |
| phi3.5:3.8b | 3GB | Chat | Always Loaded |
| qwen2.5-coder:7b | 5GB | MCP Commands/Debug | On-Demand |
| deepseek-r1:8b | 5GB | Debate/Adversarial | On-Demand |

---

## 3. System Architecture

### 3.1 The Hot Path (Deterministic Execution)
- **Goal:** Acknowledge webhooks in < 50ms.
- **Nodes:**
    1. **Signature Auth:** HMAC-SHA256 verification using SOVEREIGN_SECRET.
    2. **IP Whitelisting:** Strictly TradingView official CIDR ranges.
    3. **Idempotency:** Unique UUID per signal to prevent duplicate fills.
    4. **Binary Logic Tree:** Pre-flight checks on margin, connectivity, and hardware health.

### 3.2 The Cold Path (Adversarial Intelligence)
- **Goal:** Use high-reasoning models to prevent "trap" trades.
- **Models:**
    - **DeepSeek-R1 (The Critic):** Must generate 3 logical reasons to REJECT the trade.
    - **Llama 3.1 (The Context):** Sentiment analysis and "Market Mood" validation.
- **Safe-Fail:** If the Cold Path takes > 30s, the signal is discarded.

### 3.3 Sovereign Orchestrator (main.py)
The central entry point coordinating all system components with a 60-second heartbeat loop.

---

## 4. Operational Guardrails (The Hardening Layer)

### 4.1 Drift Detection (AI Sanity)
- **Requirement:** Weekly "Golden Set" audit with 10 historical trades.
- **Threshold:** If models fail to replicate correct logic, system triggers Safe-Mode.

### 4.2 Latency Pulse
- **Requirement:** 10-second heartbeat pings to Exchange API.
- **Threshold:** If RTT > 200ms, "Market" orders are disabled.

### 4.3 Atomic Reconciliation & L6 Lockdown
- **Requirement:** Every 60 seconds, 3-way sync (Local DB - Internal State - Exchange API).
- **L6 Lockdown:** On mismatch, cease trading, verify checksums, isolate Hot-Path.

---

## 5. Risk Management (L6 Safety)

### 5.1 The ZAR Floor & Kill-Switch
- **Mandate:** Calculate Net Equity in ZAR every 5 seconds.
- **Trigger:** If Net_Equity < ZAR_FLOOR, execute KILL_SWITCH.

### 5.2 Guardian Service - Hard Stop Protection
| Feature | Configuration |
|---------|---------------|
| Hard Stop | Daily loss >= 1.0% of starting equity = SYSTEM_LOCKED |
| Thread Safety | Lock flag protected by mutex |
| Persistence | Lock state survives restarts via data/guardian_lock.json |
| Manual Unlock | Requires explicit reason and audit trail |

### 5.3 First Trade Governor (Risk Schedule)
| Phase | Trade Count | Max Risk |
|-------|-------------|----------|
| Phase 1 | Trades 1-5 | 0.25% |
| Phase 2 | Trades 6-15 | 0.50% |
| Phase 3 | Trades 16+ | Normal (2%) |

---

## 6. Trade Lifecycle State Machine (Phase 2)

### 6.1 State Definitions
| State | Description | Terminal |
|-------|-------------|----------|
| PENDING | Trade signal received, awaiting Guardian approval | No |
| ACCEPTED | Guardian approved, awaiting broker execution | No |
| FILLED | Broker confirmed order execution | No |
| CLOSED | Position closed | No |
| SETTLED | P&L reconciled | Yes |
| REJECTED | Trade rejected (Guardian lock, validation failure) | Yes |

### 6.2 Valid Transitions
- PENDING -> ACCEPTED (Guardian approval)
- PENDING -> REJECTED (Guardian denial)
- ACCEPTED -> FILLED (Broker confirmation)
- ACCEPTED -> REJECTED (Broker rejects)
- FILLED -> CLOSED (Position closed)
- CLOSED -> SETTLED (P&L reconciled)

---

## 7. MCP Integration Architecture (78 Tools)

### 7.1 Server Configuration
| Server | Tools | Transport | Purpose |
|--------|-------|-----------|---------|
| aura-bridge | 2 | Docker exec - Stdio | Trading bot vitals, trade explanation |
| aura-full | 76 | HTTP - Gateway | Full ML/AI toolkit, RAG, Debates, Workflows |

### 7.2 Tool Categories
- Core Gateway (12): Health, metrics, commands, documentation
- ML Intelligence (15): Emotion, predictions, reasoning, personality
- GitHub Integration (3): Repo listing, semantic ranking
- ULTRA Semantic (2): Candidate ranking, confidence calibration
- Debate Engine (4): Dual-model debates, judging
- DAG Workflow (3): Workflow creation, execution, visualization
- Risk & Approval (3): Risk assessment, approval routing
- Role Engine (5): RBAC, capability evaluation
- RAG Vector DB (5): Semantic search, knowledge base
- Ollama LLM (5): Local model inference
- Security & Audit (4): PII detection, audit logs
- Audio I/O (5): STT/TTS services
- Green Computing (6): Carbon-aware scheduling, WASM plugins
- Observability (4): Prometheus metrics, Jaeger traces

---

## 8. Trade Permission Policy Layer

### 8.1 Policy Decision States
| Decision | Meaning | Action |
|----------|---------|--------|
| ALLOW | All policy gates pass | Execute trade |
| NEUTRAL | Non-critical gate failed | Maintain positions, no new trades |
| HALT | Critical gate failed | Cease all trading |

### 8.2 Gate Precedence
1. Kill Switch (Rank 1) - Immediate HALT
2. Budget Gate (Rank 2) - HARD_STOP/RDS_EXCEEDED = HALT
3. Health Gate (Rank 3) - Non-GREEN = NEUTRAL
4. Risk Gate (Rank 4) - CRITICAL = HALT

### 8.3 Monotonic Severity Latch
Once HALT is engaged, system remains in HALT until manual operator reset.

---

## 9. VALR Exchange Integration

### 9.1 Modules
| Module | Purpose | Status |
|--------|---------|--------|
| DecimalGateway | Float to Decimal with ROUND_HALF_EVEN | Verified |
| VALRSigner | HMAC-SHA512 request signing | Verified |
| TokenBucket | Thread-safe rate limiting (600/min) | Verified |
| VALRClient | API client with retry/backoff | Verified |
| OrderManager | DRY_RUN/LIVE order placement | Verified |
| ReconciliationEngine | 3-way sync, L6 Lockdown | Verified |

### 9.2 Execution Modes
| Mode | Description | Status |
|------|-------------|--------|
| DRY_RUN | Simulated orders (no real trades) | Active |
| LIVE | Real order execution | Requires LIVE_TRADING_CONFIRMED=TRUE |

---

## 10. Database Schema (22 Migrations)

| Migration | Purpose |
|-----------|---------|
| 001-003 | Core functions, audit tables, triggers |
| 004-005 | Security hardening, trigger permissions |
| 006-007 | Risk audit, AI debate ledger |
| 008-009 | Trading orders, system settings |
| 010-011 | Institutional audit columns, circuit breaker |
| 012-013 | System settings, trade learning events |
| 014-016 | Strategy blueprints, simulation results, performance metrics |
| 017-019 | Sentiment score, market snapshots, VALR order extensions |
| 020-021 | Slippage anomaly tracking, policy decision audit |
| 022 | Trade lifecycle states (Phase 2) |

---

## 11. Test Coverage

| Category | Count | Status |
|----------|-------|--------|
| Property-Based Tests | 388 | All Passing |
| Unit Tests | 279 | All Passing |
| Integration Tests | 28 | All Passing |
| **Total** | **695** | **100% Pass Rate** |

---

## 12. Sprint History

| Sprint | Version | Focus | Status |
|--------|---------|-------|--------|
| 1-3 | 1.0.0 | Core Infrastructure | Complete |
| 4 | 1.1.0 | Health Verification | Complete |
| 5 | 1.2.0 | Session Management | Complete |
| 6 | 1.3.0 | BudgetGuard Integration | Complete |
| 7 | 1.5.0 | Discord Command Center | Complete |
| 8 | 1.6.0 | Sovereign Intelligence | Complete |
| 9 | 1.7.0 | VALR Exchange Integration | Complete |
| 10 | 1.8.0 | Phase 2 Hard Requirements | Complete |
| 11 | TBD | Live Trading (Paper to Production) | Planned |

---

## 13. Confidence Audit

```
[Sovereign Reliability Audit - PRD v1.8.0]
- Mock/Placeholder Check: [CLEAN]
- NAS 3.8 Compatibility: [Verified]
- GitHub Data Sanitization: [Safe for Public]
- Decimal Integrity: [Verified]
- L6 Safety Compliance: [Verified]
- Traceability: [correlation_id + prediction_id]
- Tool Coverage: [78/78 MCP tools documented]
- Test Coverage: [695/695 tests passing]
- Database Migrations: [22/22 applied]
- Confidence Score: [100/100]
```

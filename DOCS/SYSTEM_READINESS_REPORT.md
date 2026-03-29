# AUTONOMOUS ALPHA — SYSTEM READINESS & ARCHITECTURE REPORT

**Date:** 2026-03-29
**Basis:** Repository evidence only. Zero assumptions.

---

## SECTION 1 — PAPER TRADING READINESS

### Verdict: **PARTIAL**

### Can the system run paper trading RIGHT NOW on this machine?

**PARTIAL.** The Docker stack boots, VALR credentials authenticate, and the full paper trading pipeline is implemented end-to-end. However, **no trade will ever pass the AI Council gate** because `OPENROUTER_API_KEY` is commented out in `.env`.

### What exact components prove this?

| Component | File | Evidence |
|---|---|---|
| DemoBroker (paper execution) | `services/demo_broker.py` | Simulated fills with spread, position tracking, P&L, JSON persistence, Decimal math |
| Webhook handler (15-step pipeline) | `app/api/webhook.py` | HMAC → validation → DB → BudgetGuard → Risk → AI Council → HITL |
| Execution bridge (post-approval) | `services/execution_bridge.py` | Guards: EXECUTION_MODE=DEMO, DEMO_MODE=PAPER, Guardian unlocked → DemoBroker fill → lifecycle transition |
| HITL Gateway | `services/hitl_gateway.py` | Creates AWAITING_APPROVAL, Discord notification, deep-link tokens, operator validation |
| State machine | `services/hitl_state_machine.py` | PENDING → AWAITING_APPROVAL → ACCEPTED → FILLED → CLOSED → SETTLED |
| ModeGuard resolves to PAPER | `app/exchange/mode_matrix.py` (line 189) | `EXECUTION_MODE=DEMO` → `TradingMode.PAPER`, `uses_demo_broker=True` |
| Current .env | `.env` | `EXECUTION_MODE=DEMO`, `DEMO_MODE=PAPER` |
| Docker stack healthy | Terminal evidence | 3 containers up, health endpoint OK, VALR auth OK |

### What exact flow is executed?

```
TradingView webhook (POST /tradingview)
    │
    ├─ HMAC verification (app/auth/security.py)
    ├─ Pydantic validation (app/schemas/signal.py) — rejects floats
    ├─ Atomic DB INSERT to signals table — idempotency check
    ├─ BudgetGuard (app/logic/budget_integration.py) — non-strict: fail-open
    ├─ Risk assessment (app/logic/risk_manager.py) — 1% equity formula, MAX_RISK_ZAR cap
    ├─ AI Council debate (app/logic/ai_council.py) — Bull + Bear LLM, unanimous required
    ├─ AND-gate: Budget ∧ Risk ∧ AI all APPROVED?
    │    NO  → REJECTED (pipeline stops)
    │    YES ↓
    ├─ HITL approval request created (services/hitl_gateway.py)
    ├─ Discord notification with APPROVE/REJECT buttons
    │
    │  ... operator clicks APPROVE ...
    │
    ├─ Execution bridge (services/execution_bridge.py)
    │   ├─ Guard: status == ACCEPTED
    │   ├─ Guard: EXECUTION_MODE=DEMO, DEMO_MODE=PAPER
    │   ├─ Guard: Guardian not locked
    │   ├─ DemoBroker.update_market_price()
    │   ├─ DemoBroker.place_market_order() → simulated fill
    │   ├─ Lifecycle: ACCEPTED → FILLED
    │   └─ Audit log entry
    │
    └─ State persisted to data/demo_broker_state.json
```

### Required env variables for paper trading

| Variable | Current Value | Required? |
|---|---|---|
| `EXECUTION_MODE` | `DEMO` | Yes |
| `DEMO_MODE` | `PAPER` | Yes |
| `SOVEREIGN_SECRET` | Set (32+ chars) | Yes (webhook HMAC) |
| `OPENROUTER_API_KEY` | **COMMENTED OUT** | **Yes — AI Council blocks all trades without it** |
| `HITL_ENABLED` | `true` | Yes |
| `HITL_ALLOWED_OPERATORS` | `operator_alpha` | Yes |
| `HITL_TIMEOUT_SECONDS` | `300` | Yes |
| `MAX_RISK_ZAR` | `50` | Yes (risk cap) |
| `DEMO_STATE_FILE` | `data/demo_broker_state.json` | Yes |
| `DISCORD_WEBHOOK_URL` | **COMMENTED OUT** | Optional (HITL works without Discord but notifications won't send) |

### What was validated in Phase 2B

Per `IMPLEMENTATION_MASTER_PLAN.md` sections 22-27:

- Row hash mismatch fix (SEC-080)
- Trades table persistence fix
- Restart recovery validation
- 1072 tests passing at Phase 2B completion
- PAPER_TRADING_RUNBOOK.md created

### What still might fail in edge cases

1. **AI Council is a hard blocker** — `OPENROUTER_API_KEY` is commented out. Without it, both LLM models return `ERROR`, consensus = 0, every trade is REJECTED. **No trades will ever reach HITL.**
2. **Discord webhook is commented out** — HITL approval requests will be created in the DB but the operator has no notification channel. Approval would require manual API calls or the Aura bridge.
3. **No TradingView signal source configured** — the system is passive; it only reacts to incoming webhooks. No signal generator exists in the repo.
4. **BudgetGuard JSON file** — `budget_report.json` likely doesn't exist. Non-strict mode falls back to ALLOW, so this is non-blocking.
5. **RewardGovernor model file** — If no LightGBM model exists, trust defaults to `NEUTRAL_TRUST = 0.5000`, which is below the `0.6000` threshold in ExecutionService. This may block execution in certain code paths (though the paper path via execution_bridge.py does not call ExecutionService).

---

## SECTION 2 — REAL MONEY TRADING READINESS

### Verdict: **PARTIAL**

### Can the system place REAL trades RIGHT NOW?

**NO.** The system is in `EXECUTION_MODE=DEMO`. Multiple gates prevent live execution. However, the **code infrastructure is fully implemented**.

### What EXACT conditions must be met?

| # | Requirement | Current State | Action Required |
|---|---|---|---|
| 1 | `EXECUTION_MODE=LIVE` in .env | `DEMO` | Operator must change |
| 2 | `LIVE_TRADING_CONFIRMED=TRUE` in .env | Not set | Operator must add |
| 3 | VALR API key/secret | **Set and verified working** | Done |
| 4 | VALR account funded | **R0 balance** | Operator must deposit ZAR |
| 5 | `OPENROUTER_API_KEY` active | **Commented out** | Operator must uncomment |
| 6 | `DB_PASSWORD` not default | Set to generated value | Done |
| 7 | `POSTGRES_PASSWORD` not default | Set to generated value | Done |
| 8 | `SOVEREIGN_SECRET` set | Set (32+ chars) | Done |
| 9 | `GUARDIAN_ADMIN_TOKEN` set | Set | Done |
| 10 | `GUARDIAN_RESET_CODE` set | Set | Done |
| 11 | `HITL_ALLOWED_OPERATORS` set | `operator_alpha` | Done |
| 12 | Discord webhook (for notifications) | **Commented out** | Operator should uncomment |

### Safety gates that exist

| Gate | File | What it does |
|---|---|---|
| Startup Safety Gate (9 checks) | `app/main.py` (lines 163-216) | Blocks app boot in LIVE mode without all prerequisites → `SystemExit` |
| ModeGuard | `app/exchange/mode_matrix.py` | LIVE without `LIVE_TRADING_CONFIRMED=TRUE` → falls to PAPER |
| LiveExecutionBridge preflight (9 checks) | `app/exchange/live_execution_bridge.py` (line 188) | Mode, Guardian, duplicates, R500/order cap, 5 trades/day, R2500/day volume, 3/symbol, equity, reconciliation |
| OrderManager | `app/exchange/order_manager.py` | Market orders permanently disabled (VALR-ORD-001); `post_only=True` on limit orders |
| Guardian Service (1% daily loss) | `services/guardian_service.py` (line 566) | Locks all trading when daily loss ≥ 1% of starting equity |
| Circuit Breaker (3% / 3 losses) | `app/logic/circuit_breaker.py` (line 61) | Lockout: 3% daily loss OR 3 consecutive losses |
| Kill Switch (DB-level) | `database/migrations/009_system_settings_table.sql` | `system_active=FALSE` → HALT all trading |
| Reconciliation (3-way, 1% threshold) | `app/exchange/reconciliation.py` | DB ↔ State ↔ Exchange mismatch > 1% → L6 Lockdown |
| HITL (mandatory human approval) | `services/hitl_gateway.py` | Every trade requires explicit human APPROVE; timeout = REJECT |
| AI Council (unanimous LLM consensus) | `app/logic/ai_council.py` | Both Bull and Bear must APPROVE; any ERROR/REJECT → trade blocked |

### VALR integration status

| Component | Status | Evidence |
|---|---|---|
| VALRClient (HMAC auth, rate limiting) | Implemented | `app/exchange/valr_client.py` |
| `place_limit_order()` with `post_only=True` | Implemented | `app/exchange/valr_client.py` (line 511) |
| `get_order_status()` | Implemented | `app/exchange/valr_client.py` (line 611) |
| `cancel_order()` | Implemented | `app/exchange/valr_client.py` (line 664) |
| `get_balances()` | Implemented | `app/exchange/valr_client.py` (line 350) |
| OrderStatusPoller | Implemented | `app/exchange/order_status_poller.py` |
| OrderManager (DRY_RUN / LIVE routing) | Implemented | `app/exchange/order_manager.py` |
| Credentials authenticated | **Verified** | Terminal: `Mock mode: False`, `VALR connectivity: OK` |
| Account funded | **R0** | Terminal: `ZAR balance: 0` |
| 60 unit tests for live execution | Passing | `tests/unit/test_live_execution.py` |

---

## SECTION 3 — SUPPORTED TRADING PLATFORMS

| Platform | Data Feed | Paper Trading | Live Execution | Production-Ready | Evidence |
|---|---|---|---|---|---|
| **VALR** | Authenticated reads (balances, orders, ticker) | Via DemoBroker (simulated fills) | **Full** — limit orders, status polling, cancel, reconciliation | **Yes** (92+ tests, full lifecycle) | `app/exchange/valr_client.py`, `app/exchange/live_execution_bridge.py` |
| **Binance** | WebSocket stream (BTCUSDT, ETHUSDT aggTrades) | **No** — `BINANCE_TESTNET` enum exists but resolves to PAPER | **No** — no order placement code | **No** — data feed only | `data_ingestion/adapters/binance_adapter.py` |
| **OANDA** | REST polling (EUR_USD, USD_ZAR bid/ask) | **No** — `OANDA_PRACTICE` enum exists but resolves to PAPER | **No** — no order placement code | **No** — data feed only | `data_ingestion/adapters/oanda_adapter.py` |
| **Twelve Data** | REST polling (XAU/USD, WTI/USD) | **No** | **No** | **No** — data feed only | `data_ingestion/adapters/twelve_data_adapter.py` |
| **DemoBroker** | Internal simulation (market prices seeded externally) | **Yes** — sole paper execution engine | N/A | **Yes** (paper only) | `services/demo_broker.py` |

### Key finding

`DemoMode.OANDA_PRACTICE` and `DemoMode.BINANCE_TESTNET` are enum values in `services/demo_broker.py` (lines 60-61) but `ModeGuard._resolve_mode()` at `app/exchange/mode_matrix.py` (line 189) maps **both** to `TradingMode.PAPER`. They are dead stubs with no execution path.

---

## SECTION 4 — SYSTEM ARCHITECTURE (SIMPLIFIED)

```
                         SIGNAL SOURCE
                              │
                    TradingView Webhook
                     (POST /tradingview)
                              │
                    ┌─────────┴──────────┐
                    │   AUTHENTICATION    │
                    │                     │
                    │ HMAC-SHA256 verify  │  ← SOVEREIGN_SECRET
                    │ Pydantic validation │  ← Rejects floats (Decimal only)
                    │ Idempotency check   │  ← signal_id uniqueness
                    └─────────┬──────────┘
                              │
                    ┌─────────┴──────────┐
                    │   DECISION ENGINE   │
                    │                     │
                    │ 1. BudgetGuard      │  ← Operational cost vs revenue
                    │ 2. Risk Manager     │  ← 1% equity formula, MAX_RISK cap
                    │ 3. AI Council       │  ← Bull/Bear LLM debate (unanimous)
                    │ 4. AND-gate         │  ← All 3 must APPROVE
                    └─────────┬──────────┘
                              │
                    ┌─────────┴──────────┐
                    │   HITL GATEWAY      │
                    │                     │
                    │ Guardian check      │  ← Hard stop if locked
                    │ Create request      │  ← AWAITING_APPROVAL
                    │ Discord notify      │  ← APPROVE/REJECT buttons
                    │ Expiry worker       │  ← Auto-REJECT on timeout
                    │ Slippage guard      │  ← Price drift check
                    └─────────┬──────────┘
                              │
                     Operator clicks APPROVE
                              │
              ┌───────────────┴───────────────┐
              │                               │
     PAPER MODE (current)            LIVE MODE (future)
              │                               │
    ┌─────────┴──────────┐         ┌─────────┴──────────┐
    │ Execution Bridge    │         │ LiveExecutionBridge  │
    │                     │         │                      │
    │ Mode guard: DEMO    │         │ 9-point preflight    │
    │ Guardian check      │         │ OrderManager         │
    │ DemoBroker fill     │         │ VALR limit order     │
    │ Lifecycle → FILLED  │         │ OrderStatusPoller    │
    └─────────┬──────────┘         │ Reconciliation       │
              │                     │ Lifecycle → FILLED   │
              │                     └─────────┬──────────┘
              │                               │
              └───────────┬───────────────────┘
                          │
                ┌─────────┴──────────┐
                │   AUDIT TRAIL       │
                │                     │
                │ signals table       │  ← SHA-256 row hash
                │ ai_debates table    │  ← Immutable (UPDATE/DELETE blocked)
                │ risk_assessments    │  ← Immutable
                │ trading_orders      │  ← Immutable
                │ trade_state_transitions │
                │ audit_log           │  ← Full HITL operation log
                │ policy_decision_audit │
                └─────────┬──────────┘
                          │
                ┌─────────┴──────────┐
                │   GUARDIAN LAYER    │
                │                     │
                │ Daily P&L monitor   │  ← Locks at 1% loss
                │ Lock persists to    │
                │   JSON (survives    │
                │   restarts)         │
                │ Cascade rejection   │  ← All pending → REJECTED
                │ Manual unlock only  │  ← Requires reason + audit
                └────────────────────┘
```

---

## SECTION 5 — LLM / AI USAGE

### 1. Is an LLM used?

**YES.** The AI Council is a mandatory gate in the webhook pipeline.

### 2. Where exactly?

| Component | File | Line | Role |
|---|---|---|---|
| AI Council (cloud) | `app/logic/ai_council.py` | L184 | Bull/Bear LLM debate via OpenRouter |
| AI Council (local) | `app/logic/ai_council.py` | L570 | Bull/Bear via local Ollama (GPU) |
| Factory | `app/logic/ai_council.py` | L853 | Selects cloud vs local based on `USE_LOCAL_OLLAMA` |
| Webhook invocation | `app/api/webhook.py` | L490 | Called only if Budget AND Risk both APPROVED |

### 3. Which providers?

| Provider | API URL | Models | Env Var |
|---|---|---|---|
| **OpenRouter** (default) | `https://openrouter.ai/api/v1/chat/completions` | Bull: `mistralai/mistral-7b-instruct:free`, Bear: `qwen/qwen-2-7b-instruct:free` | `OPENROUTER_API_KEY` |
| **Ollama** (alternative) | Local (no cloud) | Configurable | `USE_LOCAL_OLLAMA=true` |

### 4. What role does it play?

The AI Council runs a **structured debate protocol**:

1. A **Bull AI** argues FOR the trade with reasoning
2. A **Bear AI** argues AGAINST the trade with reasoning
3. Both must output `VERDICT: APPROVED` or `VERDICT: REJECTED`
4. Consensus requires **unanimous approval** (both APPROVED → score 100)
5. Any single rejection, error, or uncertainty → **trade REJECTED**

### 5. Consensus threshold

| Bull | Bear | Score | Approved? |
|---|---|---|---|
| APPROVED | APPROVED | 100 | **YES** |
| APPROVED | REJECTED | 50 | NO |
| REJECTED | APPROVED | 50 | NO |
| REJECTED | REJECTED | 0 | NO |
| Any ERROR | Any | 0 | NO |

### 6. Fallback when API key is missing

**There is NO fallback.** Evidence chain:

1. `AICouncil.__init__()` → `self.api_key = None`
2. `_call_openrouter()` → `if not self.api_key: return (error_msg, ModelVerdict.ERROR)`
3. Both models return ERROR → consensus = 0 → `final_verdict = False`
4. Webhook: `ai_consensus = "REJECTED"` → final AND-gate fails → **trade REJECTED**

**The LLM API key is REQUIRED for any trade to proceed.** This is by design — documented as intentional security behavior.

### 7. Is the LLM REQUIRED or optional?

**REQUIRED.** Without `OPENROUTER_API_KEY` (or `USE_LOCAL_OLLAMA=true` with a running Ollama instance), **zero trades will ever pass the AI Council gate.** This applies to both paper and live trading equally.

---

## SECTION 6 — HOW THE SYSTEM DECIDES TRADES

### Complete decision trace

A TradingView webhook arrives. The system applies **6 sequential gates**, each of which can independently reject:

**Gate 1 — Authentication** (`app/auth/security.py`)

- HMAC-SHA256 signature verification using `SOVEREIGN_SECRET`
- Timing-safe comparison via `hmac.compare_digest()`
- Fail → 401 (SEC-001 to SEC-004)

**Gate 2 — Payload Validation** (`app/schemas/signal.py`)

- Pydantic model: `signal_id`, `symbol`, `side` (BUY/SELL), `price` (Decimal), `quantity` (Decimal)
- Float values explicitly rejected (AUD-001)
- Extra fields forbidden
- Fail → 422

**Gate 3 — BudgetGuard** (`app/logic/budget_integration.py`)

- Checks infrastructure cost vs trading revenue
- Non-strict mode (default): missing data → ALLOW (fail-open)
- Strict mode: missing data → REJECT (fail-closed)
- Can reject on: HARD_STOP (over budget), RDS_EXCEEDED (daily spend)

**Gate 4 — Risk Assessment** (`app/logic/risk_manager.py`)

- Formula: `PositionSize = (Equity × 0.01) / SignalPrice`
- Hard cap: if risk amount > `MAX_RISK_ZAR` (R50 in current .env) → RISK-002 REJECT
- Zero position size → RISK-001 REJECT
- **All Decimal math, no floats**

**Gate 5 — AI Council** (`app/logic/ai_council.py`)

- Only reached if Gates 3 and 4 both APPROVED
- Two LLMs debate: Bull (for) and Bear (against)
- **Unanimous approval required** — both must output `VERDICT: APPROVED`
- Any error, timeout, or single rejection → REJECTED

**Gate 6 — AND-gate** (`app/api/webhook.py` line 620)

```
final = BudgetGuard APPROVED ∧ Risk APPROVED ∧ AI Council APPROVED
```

Any single REJECTED → final REJECTED → pipeline stops.

**Gate 7 — HITL Approval** (`services/hitl_gateway.py`)

- If all gates pass, a request is created with status `AWAITING_APPROVAL`
- Human operator must explicitly click APPROVE
- Timeout (300s default) → auto-REJECT (never auto-approve)
- Guardian locked → REJECT (SEC-020)
- Slippage exceeded → REJECT (SEC-050)

### What is automated vs requires human approval

| Stage | Automated? | Human Required? |
|---|---|---|
| Signal reception + validation | Yes | No |
| BudgetGuard evaluation | Yes | No |
| Risk assessment | Yes | No |
| AI Council debate | Yes | No |
| Final AND-gate | Yes | No |
| **Trade approval** | **No** | **Yes — mandatory** |
| Trade execution (after approval) | Yes | No |

### Can the system act autonomously?

**NO.** The system has one config bypass: `HITL_ENABLED=false` (`services/hitl_gateway.py`) would auto-approve with `decision_channel='SYSTEM'`. However, the current `.env` has `HITL_ENABLED=true`. **With current configuration, every trade requires explicit human approval.**

---

## SECTION 7 — SAFETY MODEL

### All 14 Safety Layers

| # | Layer | Protects Against | Fail Mode | Where Enforced | Tests |
|---|---|---|---|---|---|
| 1 | **HMAC Authentication** | Unauthorized webhooks | FAIL-CLOSED (401) | `app/auth/security.py` | Unit tests |
| 2 | **Pydantic + Float Rejection** | Invalid data, float precision loss | FAIL-CLOSED (422) | `app/schemas/signal.py` | Unit tests |
| 3 | **Idempotency (signal_id unique)** | Duplicate signal processing | FAIL-CLOSED (409) | `app/api/webhook.py` (line 302) | Unit tests |
| 4 | **BudgetGuard** | Over-spend on infrastructure | Non-strict: FAIL-OPEN; Strict: FAIL-CLOSED | `app/logic/budget_integration.py` | Indirect |
| 5 | **Risk Manager (1% equity)** | Over-sized positions | FAIL-CLOSED | `app/logic/risk_manager.py` | Unit tests |
| 6 | **AI Council (unanimous LLM)** | Bad trade ideas | FAIL-CLOSED | `app/logic/ai_council.py` | Unit tests |
| 7 | **HITL Gateway** | Autonomous execution | FAIL-CLOSED (timeout=REJECT) | `services/hitl_gateway.py` | 1 unit + 7 property |
| 8 | **Guardian Service (1% daily loss)** | Catastrophic daily loss | FAIL-CLOSED + lock persists to disk | `services/guardian_service.py` (line 566) | 3 unit + 1 property |
| 9 | **Circuit Breaker (3% / 3 losses)** | Runaway losing streaks | FAIL-CLOSED (no settings row = locked) | `app/logic/circuit_breaker.py` (line 61) | Indirect |
| 10 | **Kill Switch (DB-level)** | Emergency halt | FAIL-CLOSED + monotonic latch | `database/migrations/009_system_settings_table.sql` | Policy tests |
| 11 | **ModeGuard (4-mode matrix)** | Wrong execution context | FAIL-CLOSED to PAPER | `app/exchange/mode_matrix.py` | 32 + 60 tests |
| 12 | **Startup Safety Gate (9 checks)** | Missing credentials in LIVE | FAIL-CLOSED (SystemExit) | `app/main.py` (line 163) | 20 tests |
| 13 | **LiveExecutionBridge (9-point preflight)** | Over-exposure in live trading | FAIL-CLOSED | `app/exchange/live_execution_bridge.py` (line 188) | 60 tests |
| 14 | **Immutable Audit Trail** | Data tampering | 3-layer defense (triggers + permissions + hash chain) | `database/migrations/001-004` | Migration tests |

### Additional protections

| Protection | Mechanism | File |
|---|---|---|
| Reconciliation (3-way, 1% threshold) | DB ↔ State ↔ Exchange → mismatch → L6 Lockdown | `app/exchange/reconciliation.py` |
| Slippage guard | Price drift check on approval vs execution → SEC-050 | `services/slippage_guard.py` |
| Expiry worker | Auto-REJECT on HITL timeout (never auto-approve) | `services/hitl_expiry_worker.py` |
| Guardian cascade | Lock event → reject ALL pending approvals | `services/guardian_integration.py` (line 515) |
| Market orders disabled | VALR-ORD-001 — permanent block | `app/exchange/order_manager.py` |
| post_only flag | Limit orders only — prevents taker fills | `app/exchange/valr_client.py` (line 511) |
| Trade Permission Policy | Deterministic 4-gate evaluation (Kill→Budget→Health→Risk) | `app/logic/trade_permission_policy.py` |
| Row hash chain (SHA-256) | Every DB record has hash of its contents + previous hash | `database/migrations/001_core_functions.sql` |

### Mode Matrix

| Capability | PAPER | DRY_RUN | LIVE_READ_ONLY | LIVE_EXECUTION |
|---|---|---|---|---|
| Exchange public data | No | Yes | Yes | Yes |
| Exchange authenticated reads | No | No | Yes | Yes |
| Exchange order placement | No | No | No | **Yes** |
| Uses DemoBroker | **Yes** | No | No | No |
| Requires VALR credentials | No | No | Yes | Yes |
| Equity source | DEMO_BROKER | STATIC | EXCHANGE | EXCHANGE |

---

## SECTION 8 — FINAL COO-LEVEL VERDICT

### 1. Paper trading readiness

**PARTIAL** — All infrastructure is implemented and Docker stack runs. **Blocker:** `OPENROUTER_API_KEY` is commented out in `.env`. Without it, the AI Council rejects every signal. Uncomment it and paper trading is fully operational.

### 2. Real money trading readiness

**PARTIAL** — Full VALR execution pipeline is implemented with 14 safety layers. VALR credentials are verified working. **Blockers:** VALR account has R0 balance, `EXECUTION_MODE` is `DEMO`, `LIVE_TRADING_CONFIRMED` is not set, `OPENROUTER_API_KEY` is commented out.

### 3. Platforms supported

| Platform | Capability |
|---|---|
| **VALR** | Full execution (paper + live) — **sole execution venue** |
| **Binance** | Data feed only (WebSocket price stream) — **no execution** |
| **OANDA** | Data feed only (REST price polling) — **no execution** |
| **Twelve Data** | Data feed only (REST commodity prices) — **no execution** |

### 4. Biggest remaining risks

| # | Risk | Severity | Evidence |
|---|---|---|---|
| 1 | **AI Council is a single point of failure** — OpenRouter API outage = zero trades | HIGH | `ai_council.py` (line 253): no API key → ERROR → REJECTED |
| 2 | **No signal source exists in the repo** — system is purely reactive to TradingView webhooks, which require a paid TradingView subscription + configured alerts | HIGH | No signal generator found in codebase |
| 3 | **Free-tier LLM models** (`mistral-7b:free`, `qwen-2-7b:free`) may have rate limits, latency, or degraded quality | MEDIUM | `ai_council.py` (line 197) |
| 4 | **No dedicated circuit breaker tests** — circuit breaker logic is only tested indirectly | MEDIUM | No `test_circuit_breaker` file found in `tests/` |
| 5 | **Discord is the only HITL notification channel** — if Discord webhook is down, operator gets no notification (trade still requires explicit approval, but operator may miss it and it times out) | MEDIUM | `services/discord_hitl_service.py` |

### 5. Exact next step for operator

**Uncomment `OPENROUTER_API_KEY` in `.env` and restart Docker.** This is the single action that unblocks paper trading. Without it, the AI Council rejects 100% of signals.

```
# In .env, change this:
# OPENROUTER_API_KEY=sk-or-v1-...

# To this:
OPENROUTER_API_KEY=sk-or-v1-...
```

Then restart:

```
docker compose -f docker-compose.local.yml up -d
```

---

*Report compiled from repository evidence only. All claims traceable to file paths and line numbers. No assumptions made.*

*SYSTEM_READINESS_REPORT.md v1.0.0 | 2026-03-29 | SOVEREIGN TIER*

# Strategy & ML Integration Plan

**Version:** 1.0.0
**Created:** 2026-03-29
**Classification:** Sovereign Tier Engineering — INTERNAL
**Reference:** MERGE_MASTER_PLAN.md §10, UNIFIED_ARCHITECTURE.md §2, LEGACY_TRADEBOT_AUDIT.md

---

## 1. Executive Summary

This plan details how the legacy bot's 12 intelligence/learning services (~4,265 LOC), 1 learning worker job (~815 LOC), and 2 tools (~1,429 LOC) are integrated into the new bot as an **advisory intelligence layer**. Legacy services are ported to inform decisions — they never bypass Guardian, HITL, or execution controls.

**Architecture Principle:**

```
Signal → Strategy Evaluator → INTELLIGENCE LAYER (advisory) → Guardian → HITL → Execution
                                                                 ↑
                                                          Can block, never bypass
```

---

## 2. Source Inventory

### 2.1 Legacy Services to Port

| # | Service | Source File | LOC | Purpose | Priority |
|---|---------|------------|-----|---------|----------|
| 1 | BayesianReasoningService | `bayesian_reasoning_service.py` | ~550 | Multi-factor belief fusion | P0 |
| 2 | ConfidenceBudgetService | `confidence_budget_service.py` | ~480 | Daily risk budgeting | P0 |
| 3 | CapitalAllocationService | `capital_allocation_service.py` | ~400 | Position sizing from confidence | P0 |
| 4 | DecisionSnapshotService | `decision_snapshot_service.py` | ~350 | Full-context audit snapshots | P0 |
| 5 | RegimeSandboxService | `regime_sandbox_service.py` | ~380 | New-strategy evaluation sandbox | P1 |
| 6 | MindStateService | `mind_state_service.py` | ~250 | CALM/ALERT/DEFENSIVE state | P1 |
| 7 | MindStatePolicyService | `mind_state_policy_service.py` | ~220 | Policy enforcement per mind state | P1 |
| 8 | OperatorAnalyticsService | `operator_analytics_service.py` | ~300 | Operator vs AI comparison | P1 |
| 9 | ExperimentService | `experiment_service.py` | ~280 | A/B experiment lifecycle | P2 |
| 10 | LearningContractEnforcer | `learning_contract_enforcer.py` | ~350 | ML safety invariant checks | P0 |
| 11 | CounterfactualSimulator | `counterfactual_simulator_service.py` | ~400 | What-if replay engine | P2 |
| 12 | CurriculumScheduler | `curriculum_scheduler_service.py` | ~305 | Phased learning schedule | P2 |

### 2.2 Jobs to Port

| Job | Source | LOC | Purpose |
|-----|--------|-----|---------|
| LearningWorkerV2 | `learning_worker_v2.py` | ~815 | Periodic learning cycle orchestrator |

### 2.3 Tools to Port

| Tool | Source | LOC | Purpose |
|------|--------|-----|---------|
| TvExtractor | `tv_extractor.py` | ~912 | TradingView alert parser |
| SentimentHarvester | `sentiment_harvester.py` | ~517 | Market sentiment aggregation |

---

## 3. Integration Architecture

### 3.1 Service Placement

All ported intelligence services will reside in a new `services/intelligence/` subdirectory:

```
services/
├── intelligence/                    # NEW — all legacy ports
│   ├── __init__.py
│   ├── bayesian_reasoning_service.py
│   ├── confidence_budget_service.py
│   ├── capital_allocation_service.py
│   ├── decision_snapshot_service.py
│   ├── regime_sandbox_service.py
│   ├── mind_state_service.py
│   ├── mind_state_policy_service.py
│   ├── operator_analytics_service.py
│   ├── experiment_service.py
│   ├── learning_contract_enforcer.py
│   ├── counterfactual_simulator_service.py
│   ├── curriculum_scheduler_service.py
│   └── learning_worker.py          # (from learning_worker_v2.py)
├── ... (existing 25 services remain unchanged)
```

### 3.2 Advisory Boundary Contract

Every intelligence service **MUST** follow these invariants:

1. **Read-only advisory:** Intelligence services return recommendations but never execute trades
2. **Decimal only:** All financial math uses Python `Decimal` — no float
3. **DB via new bot factory:** Uses `app.database.session` — never direct connection strings
4. **Guardian respect:** LearningContractEnforcer checks run BEFORE and AFTER any intelligence update
5. **Logging via structlog:** All services use the existing structlog configuration
6. **Error isolation:** An intelligence service failure MUST NOT crash the trading pipeline — fail-open with logged warning
7. **No secret access:** Intelligence services read config from environment variables, never hardcoded

### 3.3 Dependency Wiring

```python
# In app/main.py lifespan or services/__init__.py

# P0 (Phase 3 of merge)
bayesian_reasoning = BayesianReasoningService(db_session_factory)
confidence_budget = ConfidenceBudgetService(db_session_factory)
capital_allocation = CapitalAllocationService(db_session_factory, confidence_budget)
decision_snapshot = DecisionSnapshotService(db_session_factory)
learning_contract_enforcer = LearningContractEnforcer(db_session_factory)

# P1 (Phase 4 of merge)
mind_state = MindStateService(db_session_factory)
mind_state_policy = MindStatePolicyService(db_session_factory, mind_state)
regime_sandbox = RegimeSandboxService(db_session_factory)
operator_analytics = OperatorAnalyticsService(db_session_factory)

# P2 (Phase 5 of merge)
experiment = ExperimentService(db_session_factory)
counterfactual_sim = CounterfactualSimulator(db_session_factory)
curriculum_scheduler = CurriculumScheduler(db_session_factory)
```

---

## 4. Bayesian Reasoning Architecture

### 4.1 Overview

The Bayesian Reasoning Service is the central intelligence hub. It fuses multiple evidence sources into a single posterior belief distribution using Bayes' theorem.

### 4.2 Evidence Sources

| Source | Weight | Type |
|--------|--------|------|
| TradingView alerts | 0.3 | Signal strength |
| Sentiment score | 0.1 | Market mood |
| Regime classification | 0.2 | Market regime (trending/ranging/volatile) |
| Technical indicators | 0.2 | RSI, MACD, etc. |
| Historical pattern match | 0.1 | Similar past trades |
| Operator track record | 0.1 | Operator directional accuracy |

### 4.3 Belief Update Flow

```
Prior (base rate)
    ↓
Collect evidence from N sources
    ↓
For each evidence source:
    likelihood = P(evidence | hypothesis_true) / P(evidence | hypothesis_false)
    posterior = prior * likelihood / normalizer
    prior = posterior  # cascade
    ↓
Final posterior = composite confidence
    ↓
decision_snapshot.record(posterior, evidence_list)
    ↓
Return BayesianVerdict:
    - direction: LONG | SHORT | HOLD
    - confidence: Decimal (0-1)
    - evidence_weights: Dict[str, Decimal]
    - reasoning_chain: List[str]
```

### 4.4 Safety Constraints

- Confidence is clamped to `[Decimal("0.01"), Decimal("0.99")]` — never 0 or 1
- All intermediate math uses `Decimal` with `ROUND_HALF_UP`
- Evidence weights must sum to `Decimal("1.0")`
- Maximum number of evidence sources per evaluation: 10

---

## 5. Confidence Budget System

### 5.1 Purpose

The Confidence Budget prevents reckless trading by limiting daily risk exposure. Each trade consumes budget proportional to its assessed risk and the system's confidence in the trade.

### 5.2 Budget Mechanics

```
Daily Budget = Decimal("100.0")  # 100 units per day

For each proposed trade:
    cost = risk_score * position_size_factor * (1 - confidence)
    if remaining_budget >= cost:
        deduct cost from budget
        allow trade to proceed to Guardian
    else:
        block trade (soft block — Guardian still has final say)

Reset: midnight UTC, or operator manual reset
```

### 5.3 Budget→Confidence→Size Pipeline

```
                ┌──────────────┐
                │ Signal Input │
                └──────┬───────┘
                       ▼
              ┌────────────────┐
              │   Bayesian     │
              │   Reasoning    │──→ confidence: Decimal("0.72")
              └────────┬───────┘
                       ▼
              ┌────────────────┐
              │  Confidence    │
              │  Budget Check  │──→ remaining: Decimal("65.3")
              └────────┬───────┘
                       ▼
              ┌────────────────┐
              │   Capital      │
              │  Allocation    │──→ position_size: Decimal("850.00") ZAR
              └────────┬───────┘
                       ▼
              ┌────────────────┐
              │  Mind State    │
              │  Policy Check  │──→ adjustment: Decimal("0.80") (if ALERT)
              └────────┬───────┘
                       ▼
              ┌────────────────┐
              │  Guardian      │
              │  Final Gate    │──→ ALLOW / BLOCK
              └────────┬───────┘
                       ▼
              ┌────────────────┐
              │     HITL       │
              │   Approval     │──→ Operator confirms
              └────────────────┘
```

---

## 6. Capital Allocation Model

### 6.1 Sizing Formula

```python
from decimal import Decimal, ROUND_HALF_UP

def calculate_position_size(
    confidence: Decimal,
    remaining_budget: Decimal,
    max_position_zar: Decimal,
    risk_per_trade: Decimal,  # e.g., Decimal("0.02") = 2%
    portfolio_value: Decimal,
) -> Decimal:
    """
    Position sizing based on confidence and Kelly-inspired formula.
    All arithmetic is Decimal — no float permitted.
    """
    # Base size = risk fraction of portfolio
    base_size = portfolio_value * risk_per_trade

    # Scale by confidence (linear scaling)
    confidence_factor = confidence  # 0.01 to 0.99

    # Apply mind state dampening if needed (passed in separately)
    raw_size = base_size * confidence_factor

    # Cap at maximum position size
    capped = min(raw_size, max_position_zar)

    # Round to 2 decimal places for ZAR
    return capped.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
```

### 6.2 Risk Tiers

| Mind State | Max Risk Per Trade | Position Multiplier |
|------------|-------------------|---------------------|
| CALM | 2.0% | 1.0 |
| ALERT | 1.0% | 0.5 |
| DEFENSIVE | 0.5% | 0.25 |

---

## 7. Mind State System

### 7.1 State Definitions

| State | Trigger | Behavior |
|-------|---------|----------|
| **CALM** | No anomalies detected | Full position sizes, normal budget |
| **ALERT** | Loss threshold approaching, volatility spike, consecutive losses ≥ 2 | Halved position sizes, tighter stops |
| **DEFENSIVE** | Guardian soft lock, daily loss > 50% limit, exchange errors | Minimal sizes, no new positions |

### 7.2 State Transitions

```
CALM ──(consecutive_losses >= 2 OR daily_drawdown > 3%)──→ ALERT
CALM ──(guardian_warning OR exchange_error)──────────────→ DEFENSIVE
ALERT ──(3 profitable trades in row)────────────────────→ CALM
ALERT ──(daily_drawdown > 5% OR guardian_lock)──────────→ DEFENSIVE
DEFENSIVE ──(guardian_unlocked AND new_day)──────────────→ CALM
```

### 7.3 Policy Enforcement

```python
class MindStatePolicyService:
    def apply_policy(self, proposed_trade: TradeProposal, mind_state: MindState) -> PolicyVerdict:
        """
        Apply mind-state-specific modifications to a trade proposal.
        Returns modified proposal or rejection.
        """
        policy = POLICIES[mind_state]
        modified = proposed_trade.copy()

        # Scale position size
        modified.size = (proposed_trade.size * policy.position_multiplier).quantize(...)

        # Check time-based cooldown
        if mind_state == MindState.DEFENSIVE:
            if self.minutes_since_last_trade() < policy.cooldown_minutes:
                return PolicyVerdict(allowed=False, reason="DEFENSIVE cooldown active")

        return PolicyVerdict(allowed=True, modified_trade=modified)
```

---

## 8. Decision Snapshot & Forensics

### 8.1 Snapshot Contents

Every decision (approved or rejected) generates a full-context snapshot:

```python
@dataclass
class DecisionSnapshot:
    id: str                          # UUID
    timestamp: datetime
    signal: SignalData               # What triggered this decision
    bayesian_verdict: BayesianVerdict  # Full reasoning chain
    confidence: Decimal              # Final confidence
    remaining_budget: Decimal        # Budget before deduction
    mind_state: str                  # CALM/ALERT/DEFENSIVE
    regime: str                      # Current market regime
    strategy: str                    # Strategy that generated signal
    proposed_size: Decimal           # Uncapped size
    final_size: Decimal              # After mind state policy
    guardian_status: str             # Guardian state at decision time
    operator_decision: Optional[str] # APPROVE/REJECT/TIMEOUT
    market_state: Dict               # Prices, spreads, order book depth
    trade_id: Optional[str]          # If trade was placed
```

### 8.2 Counterfactual Simulator

Replays past decisions with alternative parameters to evaluate what-if scenarios:

```
Input:
    snapshot_id: str
    overrides:
        confidence: Optional[Decimal]
        mind_state: Optional[str]
        position_size: Optional[Decimal]

Output:
    original_outcome: TradeOutcome
    counterfactual_outcome: TradeOutcome
    delta_pnl: Decimal
    conclusion: str  # "Would have improved by X ZAR" / "Would have lost additional Y ZAR"
```

---

## 9. Experiment Framework

### 9.1 Experiment Lifecycle

```
PROPOSED → APPROVED → ACTIVE → COMPLETED → ANALYZED
                         ↓
                      FAILED (if safety violation)
```

### 9.2 Experiment Definition

```python
@dataclass
class ExperimentDefinition:
    id: str
    name: str
    hypothesis: str
    strategy_variant: str          # What's being tested
    baseline_strategy: str         # What it's compared against
    regime_filter: Optional[str]   # Only run in specific regime
    max_trades: int                # Stop after N trades
    max_budget: Decimal            # Maximum budget allocation
    start_date: date
    end_date: Optional[date]
    status: ExperimentStatus
```

### 9.3 Sandbox Constraints

- Experiments run in **regime sandbox** — isolated from production strategies
- Maximum budget per experiment: configurable, default `Decimal("5000.00")` ZAR
- Automatic halt if experiment drawdown exceeds 10% of allocated budget
- All experiment trades go through Guardian + HITL (no bypass)
- LearningContractEnforcer validates experiment setup before activation

---

## 10. Regime Detection & Sandbox

### 10.1 Regime Classification

| Regime | Detection Criteria | Trading Policy |
|--------|-------------------|----------------|
| TRENDING_UP | ADX > 25, price > 20-SMA, positive slope | Full strategies enabled |
| TRENDING_DOWN | ADX > 25, price < 20-SMA, negative slope | Short bias, reduced size |
| RANGING | ADX < 20, Bollinger width contracting | Mean-reversion only |
| VOLATILE | ATR spike > 2x average, VIX-like metric elevated | Defensive, wider stops |
| UNKNOWN | Insufficient data or conflicting signals | Minimum exposure only |

### 10.2 Strategy-Regime Mapping

Each strategy declares which regimes it operates in. The RegimeSandboxService ensures strategies only execute in their declared regimes.

```python
STRATEGY_REGIME_MAP = {
    "momentum_breakout": [Regime.TRENDING_UP],
    "mean_reversion": [Regime.RANGING],
    "trend_follow": [Regime.TRENDING_UP, Regime.TRENDING_DOWN],
    "defensive_hedge": [Regime.VOLATILE],
}
```

---

## 11. Learning Worker Integration

### 11.1 Worker Architecture

The LearningWorker runs as a periodic job (via APScheduler in the existing job framework):

```python
class LearningWorker:
    """
    Orchestrates the learning cycle:
    1. Collect new trade outcomes
    2. Update Bayesian beliefs
    3. Recalculate confidence metrics
    4. Update mind state
    5. Check curriculum progress
    6. Run contract enforcement
    7. Store learning snapshot
    """

    async def run_cycle(self):
        # Phase 1: Collect
        new_outcomes = await self.trade_outcome_collector.collect_since(self.last_run)

        # Phase 2: Bayesian update
        for outcome in new_outcomes:
            await self.bayesian_reasoning.update_beliefs(outcome)

        # Phase 3: Confidence recalculation
        await self.confidence_budget.reconcile()

        # Phase 4: Mind state update
        await self.mind_state.evaluate_transitions()

        # Phase 5: Curriculum check
        await self.curriculum_scheduler.advance_if_ready()

        # Phase 6: Contract enforcement
        violations = await self.contract_enforcer.validate_all()
        if violations:
            logger.warning("Learning contract violations detected", violations=violations)
            # Contract violations DO NOT auto-heal — they are logged for operator review

        # Phase 7: Snapshot
        await self.decision_snapshot.record_learning_cycle(...)

        self.last_run = datetime.utcnow()
```

### 11.2 Schedule

| Interval | Action |
|----------|--------|
| Every 5 minutes | Light cycle: Bayesian update, mind state check |
| Every 30 minutes | Full cycle: + confidence reconcile, curriculum check |
| Daily at 00:05 UTC | Budget reset, daily analytics snapshot, contract audit |

---

## 12. Curriculum Scheduler

### 12.1 Learning Phases

The system follows a phased curriculum that progressively increases autonomy:

| Phase | Name | Duration | Max Confidence | Max Position | HITL Mode |
|-------|------|----------|---------------|--------------|-----------|
| 1 | Observer | 2 weeks | 0.50 | None (paper only) | All trades |
| 2 | Cautious | 4 weeks | 0.70 | 500 ZAR | All trades |
| 3 | Confident | 8 weeks | 0.85 | 2,000 ZAR | Above threshold |
| 4 | Autonomous | Ongoing | 0.95 | 5,000 ZAR | Anomalies only |

### 12.2 Advancement Criteria

```python
def can_advance(current_phase: Phase, metrics: LearningMetrics) -> bool:
    """Check if system can advance to next curriculum phase."""
    return (
        metrics.min_trades_in_phase >= current_phase.min_trades
        and metrics.win_rate >= current_phase.min_win_rate
        and metrics.max_drawdown <= current_phase.max_drawdown_pct
        and metrics.contract_violations == 0
        and metrics.days_in_phase >= current_phase.min_days
    )
```

### 12.3 Advancement is HITL-Gated

Phase advancement is **never automatic** — it generates an HITL approval request:

```
CurriculumScheduler.can_advance() == True
    ↓
Create HITL approval: "System requests advancement from Phase 2 → Phase 3"
    ↓
Operator reviews metrics, approves/rejects
    ↓
If approved: advance phase, update limits
If rejected: stay in current phase, log reason
```

---

## 13. Golden Set Validation

### 13.1 Purpose

Every strategy and intelligence model is validated against a "Golden Set" — a curated collection of historical scenarios with known-correct outcomes.

### 13.2 Golden Set Structure

```python
@dataclass
class GoldenSetCase:
    id: str
    scenario: str           # Human description
    market_state: Dict      # Full market context
    expected_direction: str  # LONG/SHORT/HOLD
    expected_confidence_min: Decimal
    expected_confidence_max: Decimal
    regime: str
    created_by: str         # Operator who curated this case
    verified: bool
```

### 13.3 Validation Protocol

- Golden set must pass with ≥70% accuracy before any strategy goes live
- Run daily during learning cycle
- New golden set cases added after each significant market event
- LearningContractEnforcer blocks curriculum advancement if golden set performance degrades

---

## 14. Database Tables (New)

These tables support the intelligence layer. Migrations are adapted from legacy 027-033:

| Table | Migration | Purpose |
|-------|-----------|---------|
| `bayesian_beliefs` | 027 | Per-symbol belief distributions |
| `confidence_budget_daily` | 028 | Daily budget state, resets, deductions |
| `mind_state_history` | 029 | Mind state transitions with timestamps |
| `decision_snapshots` | 030 | Full-context decision records |
| `regime_observations` | 031 | Regime classifications per time window |
| `experiment_definitions` | 031 | Experiment metadata and lifecycle |
| `experiment_trades` | 031 | Trades attributed to experiments |
| `operator_analytics` | 032 | Operator decisions and outcomes |
| `learning_contract_checks` | 032 | Contract enforcement audit trail |
| `counterfactual_results` | 033 | What-if simulation outputs |
| `curriculum_state` | 033 | Current curriculum phase and metrics |
| `golden_set_cases` | 033 | Curated evaluation scenarios |
| `golden_set_results` | 033 | Historical golden set evaluation scores |
| `capital_allocation_log` | 028 | Position sizing decisions and rationale |
| `learning_cycle_snapshots` | 030 | Periodic learning worker outputs |

---

## 15. ML Quality Principles

1. **No model retraining during live trading** — training happens offline or in paper mode
2. **All predictions are Decimal** — no floating-point in confidence or sizing
3. **Model outputs are advisory** — never directly execute
4. **Reproducibility** — all model inputs logged in decision snapshots
5. **Versioning** — every model change tracked in experiment framework
6. **Graceful degradation** — if ML service unavailable, system falls back to rule-based defaults
7. **Contract enforcement** — LearningContractEnforcer validates invariants before and after every update
8. **Observable** — all ML state exposed via API and Grafana dashboards

---

## 16. Integration Test Strategy

### 16.1 Test Categories

| Category | Tests | Coverage |
|----------|-------|----------|
| Unit: Each intelligence service | ~12 test files | Individual logic correctness |
| Integration: Pipeline flow | ~3 test files | Signal → Bayesian → Budget → Sizing |
| Contract: LearningContractEnforcer | ~2 test files | All invariant checks |
| Golden Set: Regression | ~1 test file | Known-correct outputs |
| Decimal: No float leaks | ~1 test file | Audit all arithmetic paths |

### 16.2 Mandatory Pre-Merge Checks

```bash
# All existing 1,072+ tests still pass
pytest tests/ --tb=short

# New intelligence tests pass
pytest tests/intelligence/ --tb=short

# No float detected in intelligence services
grep -rn "float(" services/intelligence/ && echo "FAIL: float detected" && exit 1

# Golden set passes at ≥70%
python -m pytest tests/intelligence/test_golden_set.py -v
```

---

*END OF STRATEGY_ML_INTEGRATION_PLAN.md v1.0.0*

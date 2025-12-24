"""
============================================================================
Project Autonomous Alpha v1.6.0
Logic Layer - Risk Management, Position Sizing, and Order Execution
============================================================================

SOVEREIGN TIER INFRASTRUCTURE
Assurance Level: 100% Confidence (Mission-Critical)

This module contains the core business logic for:
- Risk calculation (1% fixed risk per trade)
- Position sizing based on signal price
- Safety guardrails (RISK-001, RISK-002)
- RiskGovernor: ATR-based sizing, circuit breakers (v1.4.0)
- OrderManager: Closed-loop reconciliation (v1.4.0)
- CircuitBreaker: Autonomous lockout system (v1.4.0)
- ExecutionHandshake: Permit-based authorization (v1.4.0)
- Institutional audit: slippage, expectancy tracking (v1.4.0)
- RGI: Reward-Governed Intelligence learning system (v1.6.0)
- ConfidenceArbiter: 95% gate with learned trust (v1.6.0)
- TradeCloseHandler: Cold-path learning integration (v1.6.0)

============================================================================
"""

from app.logic.risk_manager import (
    RiskProfile,
    calculate_position_size,
    fetch_account_equity,
)

from app.logic.risk_governor import (
    RiskGovernor,
    ExecutionPermit,
    CircuitBreakerResult,
    get_execution_permit,
)

from app.logic.order_manager import (
    OrderManager,
    OrderReconciliation,
    ReconciliationStatus,
    execute_with_reconciliation,
)

from app.logic.dispatcher import (
    Dispatcher,
    DispatchResult,
    calculate_expectancy,
)

from app.logic.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerState,
    LockoutDecision,
    check_trading_allowed,
    record_trade_result,
)

from app.logic.execution_handshake import (
    ExecutionHandshake,
    HandshakeResult,
    ExecutionResult,
    validate_permit,
    execute_with_permit,
)

# RGI Integration (v1.6.0 - Sprint 9)
from app.logic.confidence_arbiter import (
    ConfidenceArbiter,
    ArbitrationResult,
    arbitrate_confidence,
    get_confidence_arbiter,
    EXECUTION_THRESHOLD,
)

from app.logic.learning_features import (
    FeatureSnapshot,
    VolatilityRegime,
    TrendState,
    Outcome,
    extract_learning_features,
    classify_outcome,
)

from app.logic.trade_learning import (
    TradeLearningEvent,
    record_trade_close,
    create_learning_event,
)

from app.logic.trade_close_handler import (
    TradeCloseData,
    handle_trade_close,
    handle_trade_close_simple,
    on_order_reconciliation_complete,
)

__all__ = [
    # Risk Manager (v1.3.x)
    "RiskProfile",
    "calculate_position_size",
    "fetch_account_equity",
    # Risk Governor (v1.4.0)
    "RiskGovernor",
    "ExecutionPermit",
    "CircuitBreakerResult",
    "get_execution_permit",
    # Order Manager (v1.4.0)
    "OrderManager",
    "OrderReconciliation",
    "ReconciliationStatus",
    "execute_with_reconciliation",
    # Dispatcher (v1.4.0)
    "Dispatcher",
    "DispatchResult",
    "calculate_expectancy",
    # Circuit Breaker (v1.4.0)
    "CircuitBreaker",
    "CircuitBreakerState",
    "LockoutDecision",
    "check_trading_allowed",
    "record_trade_result",
    # Execution Handshake (v1.4.0)
    "ExecutionHandshake",
    "HandshakeResult",
    "ExecutionResult",
    "validate_permit",
    "execute_with_permit",
    # RGI - Confidence Arbiter (v1.6.0)
    "ConfidenceArbiter",
    "ArbitrationResult",
    "arbitrate_confidence",
    "get_confidence_arbiter",
    "EXECUTION_THRESHOLD",
    # RGI - Learning Features (v1.6.0)
    "FeatureSnapshot",
    "VolatilityRegime",
    "TrendState",
    "Outcome",
    "extract_learning_features",
    "classify_outcome",
    # RGI - Trade Learning (v1.6.0)
    "TradeLearningEvent",
    "record_trade_close",
    "create_learning_event",
    # RGI - Trade Close Handler (v1.6.0)
    "TradeCloseData",
    "handle_trade_close",
    "handle_trade_close_simple",
    "on_order_reconciliation_complete",
]

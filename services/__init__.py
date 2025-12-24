"""
============================================================================
Project Autonomous Alpha - Services Layer
============================================================================

Strategy Ingestion Pipeline services for DSL canonicalization,
fingerprinting, and persistence.

Reliability Level: L6 Critical
============================================================================
"""

from services.dsl_schema import (
    CanonicalDSL,
    MetaConfig,
    SignalsConfig,
    RiskConfig,
    PositionConfig,
    ConfoundsConfig,
    AlertsConfig,
    validate_dsl_schema,
)

from services.strategy_store import (
    StrategyStore,
    StrategyBlueprint,
    compute_fingerprint,
    create_strategy_store,
)

from services.canonicalizer import (
    StrategyCanonicalizer,
    CanonicalizationError,
    create_canonicalizer,
)

from services.golden_set_integration import (
    GoldenSetStrategyValidator,
    AUCResult,
    QuarantineResult,
    calculate_strategy_auc,
    register_strategy_to_golden_set,
    create_golden_set_validator,
    AUC_THRESHOLD,
)

from services.strategy_manager import (
    StrategyManager,
    StrategyMode,
    StrategyAction,
    StrategyDecision,
    StrategyInputs,
    StrategyOutputs,
    create_strategy_manager,
)

from services.hitl_websocket_emitter import (
    HITLWebSocketEmitter,
    HITLWebSocketEvent,
    HITLEventType,
    EmitResult,
    get_hitl_websocket_emitter,
    reset_hitl_websocket_emitter,
)

__all__ = [
    # DSL Schema
    "CanonicalDSL",
    "MetaConfig",
    "SignalsConfig",
    "RiskConfig",
    "PositionConfig",
    "ConfoundsConfig",
    "AlertsConfig",
    "validate_dsl_schema",
    # Strategy Store
    "StrategyStore",
    "StrategyBlueprint",
    "compute_fingerprint",
    "create_strategy_store",
    # Canonicalizer
    "StrategyCanonicalizer",
    "CanonicalizationError",
    "create_canonicalizer",
    # Golden Set Integration
    "GoldenSetStrategyValidator",
    "AUCResult",
    "QuarantineResult",
    "calculate_strategy_auc",
    "register_strategy_to_golden_set",
    "create_golden_set_validator",
    "AUC_THRESHOLD",
    # Strategy Manager
    "StrategyManager",
    "StrategyMode",
    "StrategyAction",
    "StrategyDecision",
    "StrategyInputs",
    "StrategyOutputs",
    "create_strategy_manager",
    # HITL WebSocket Emitter
    "HITLWebSocketEmitter",
    "HITLWebSocketEvent",
    "HITLEventType",
    "EmitResult",
    "get_hitl_websocket_emitter",
    "reset_hitl_websocket_emitter",
]

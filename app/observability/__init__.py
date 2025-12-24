"""
============================================================================
Project Autonomous Alpha v1.4.0
Observability Module - Phase 6 Prometheus Metrics
============================================================================

Reliability Level: SOVEREIGN TIER (Mission-Critical)
Input Constraints: None
Side Effects: Exposes Prometheus metrics

============================================================================
"""

from app.observability.metrics import (
    SIGNALS_RECEIVED,
    SIGNALS_EXECUTED,
    EQUITY_ZAR_GAUGE,
    SLIPPAGE_HISTOGRAM,
    EXPECTANCY_GAUGE,
    record_signal_received,
    record_signal_executed,
    update_equity,
    record_slippage,
    update_expectancy,
)

from app.observability.rgi_metrics import (
    RGI_TRUST_PROBABILITY,
    RGI_ADJUSTED_CONFIDENCE,
    RGI_SAFE_MODE_ACTIVE,
    RGI_PREDICTION_LATENCY_MS,
    RGI_LEARNING_EVENTS_TOTAL,
    RGI_CONFIDENCE_DELTA,
    RGI_MODEL_LOADED,
    RGI_ARBITRATION_DECISIONS,
    record_trust_probability,
    record_adjusted_confidence,
    record_confidence_delta,
    update_safe_mode_status,
    record_prediction_latency,
    record_learning_event,
    update_model_loaded_status,
    record_arbitration_decision,
    log_arbitration_result,
)

__all__ = [
    # Core metrics
    "SIGNALS_RECEIVED",
    "SIGNALS_EXECUTED",
    "EQUITY_ZAR_GAUGE",
    "SLIPPAGE_HISTOGRAM",
    "EXPECTANCY_GAUGE",
    "record_signal_received",
    "record_signal_executed",
    "update_equity",
    "record_slippage",
    "update_expectancy",
    # RGI metrics
    "RGI_TRUST_PROBABILITY",
    "RGI_ADJUSTED_CONFIDENCE",
    "RGI_SAFE_MODE_ACTIVE",
    "RGI_PREDICTION_LATENCY_MS",
    "RGI_LEARNING_EVENTS_TOTAL",
    "RGI_CONFIDENCE_DELTA",
    "RGI_MODEL_LOADED",
    "RGI_ARBITRATION_DECISIONS",
    "record_trust_probability",
    "record_adjusted_confidence",
    "record_confidence_delta",
    "update_safe_mode_status",
    "record_prediction_latency",
    "record_learning_event",
    "update_model_loaded_status",
    "record_arbitration_decision",
    "log_arbitration_result",
]

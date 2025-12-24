"""
============================================================================
Project Autonomous Alpha v1.4.0
Prometheus Metrics - Phase 6 Observability
============================================================================

Reliability Level: SOVEREIGN TIER (Mission-Critical)
Input Constraints: All currency values must be Decimal
Side Effects: Updates Prometheus metrics registry

METRICS EXPOSED
---------------
- trade_signals_received_total: Counter of all signals received
- trade_signals_executed_total: Counter of signals that executed
- equity_zar_gauge: Current account balance from VALR
- slippage_pct_histogram: Distribution of execution slippage
- expectancy_gauge: Rolling realized_pnl / realized_risk

ZERO-FLOAT MANDATE
------------------
All financial values are converted from Decimal to float ONLY at the
Prometheus boundary. Internal calculations remain Decimal.

============================================================================
"""

import logging
from decimal import Decimal
from typing import Optional

from prometheus_client import Counter, Gauge, Histogram, REGISTRY

# Configure module logger
logger = logging.getLogger(__name__)


# ============================================================================
# PROMETHEUS METRICS DEFINITIONS
# ============================================================================

# Counter: Total signals received vs executed
SIGNALS_RECEIVED = Counter(
    "trade_signals_received_total",
    "Total number of trading signals received from TradingView",
    ["symbol", "action"]
)

SIGNALS_EXECUTED = Counter(
    "trade_signals_executed_total",
    "Total number of trading signals successfully executed",
    ["symbol", "action", "status"]
)

# Gauge: Current account equity in ZAR
EQUITY_ZAR_GAUGE = Gauge(
    "equity_zar_gauge",
    "Current account balance in ZAR from VALR"
)

# Histogram: Slippage percentage distribution
# Buckets: 0.01%, 0.05%, 0.1%, 0.15%, 0.2%, 0.5%, 1%, 2%, 5%
SLIPPAGE_HISTOGRAM = Histogram(
    "slippage_pct_histogram",
    "Distribution of execution slippage percentage",
    ["symbol", "action"],
    buckets=[0.0001, 0.0005, 0.001, 0.0015, 0.002, 0.005, 0.01, 0.02, 0.05]
)

# Gauge: Rolling expectancy (realized_pnl / realized_risk)
EXPECTANCY_GAUGE = Gauge(
    "expectancy_gauge",
    "Rolling expectancy ratio (realized_pnl / realized_risk)"
)


# ============================================================================
# METRIC UPDATE FUNCTIONS
# ============================================================================

def record_signal_received(
    symbol: str,
    action: str,
    correlation_id: Optional[str] = None
) -> None:
    """
    Record a signal received from TradingView.
    
    Reliability Level: SOVEREIGN TIER
    Input Constraints: Valid symbol and action strings
    Side Effects: Increments Prometheus counter
    
    Args:
        symbol: Trading pair (e.g., "BTCZAR")
        action: Signal action (e.g., "BUY", "SELL")
        correlation_id: Optional tracking ID
    """
    try:
        SIGNALS_RECEIVED.labels(symbol=symbol, action=action).inc()
        logger.debug(
            "Metric: signal_received | symbol=%s | action=%s | correlation_id=%s",
            symbol, action, correlation_id
        )
    except Exception as e:
        logger.error(
            "[OBS-001] Failed to record signal_received metric | error=%s",
            str(e)
        )


def record_signal_executed(
    symbol: str,
    action: str,
    status: str,
    correlation_id: Optional[str] = None
) -> None:
    """
    Record a signal execution result.
    
    Reliability Level: SOVEREIGN TIER
    Input Constraints: Valid symbol, action, and status strings
    Side Effects: Increments Prometheus counter
    
    Args:
        symbol: Trading pair (e.g., "BTCZAR")
        action: Signal action (e.g., "BUY", "SELL")
        status: Execution status (e.g., "FILLED", "REJECTED", "FAILED")
        correlation_id: Optional tracking ID
    """
    try:
        SIGNALS_EXECUTED.labels(symbol=symbol, action=action, status=status).inc()
        logger.debug(
            "Metric: signal_executed | symbol=%s | action=%s | status=%s | "
            "correlation_id=%s",
            symbol, action, status, correlation_id
        )
    except Exception as e:
        logger.error(
            "[OBS-002] Failed to record signal_executed metric | error=%s",
            str(e)
        )


def update_equity(
    equity_zar: Decimal,
    correlation_id: Optional[str] = None
) -> None:
    """
    Update the current equity gauge.
    
    Reliability Level: SOVEREIGN TIER
    Input Constraints: equity_zar must be Decimal
    Side Effects: Updates Prometheus gauge
    
    ZERO-FLOAT MANDATE: Decimal converted to float at Prometheus boundary.
    
    Args:
        equity_zar: Current account balance in ZAR (Decimal)
        correlation_id: Optional tracking ID
    """
    try:
        if not isinstance(equity_zar, Decimal):
            logger.error(
                "[OBS-000] equity_zar must be Decimal, got %s",
                type(equity_zar).__name__
            )
            return
        
        # Convert to float ONLY at Prometheus boundary
        EQUITY_ZAR_GAUGE.set(float(equity_zar))
        logger.debug(
            "Metric: equity_zar updated | value=%s | correlation_id=%s",
            str(equity_zar), correlation_id
        )
    except Exception as e:
        logger.error(
            "[OBS-003] Failed to update equity_zar metric | error=%s",
            str(e)
        )


def record_slippage(
    symbol: str,
    action: str,
    slippage_pct: Decimal,
    correlation_id: Optional[str] = None
) -> None:
    """
    Record execution slippage in the histogram.
    
    Reliability Level: SOVEREIGN TIER
    Input Constraints: slippage_pct must be Decimal
    Side Effects: Observes value in Prometheus histogram
    
    ZERO-FLOAT MANDATE: Decimal converted to float at Prometheus boundary.
    
    Args:
        symbol: Trading pair (e.g., "BTCZAR")
        action: Signal action (e.g., "BUY", "SELL")
        slippage_pct: Slippage as decimal (0.01 = 1%)
        correlation_id: Optional tracking ID
    """
    try:
        if not isinstance(slippage_pct, Decimal):
            logger.error(
                "[OBS-000] slippage_pct must be Decimal, got %s",
                type(slippage_pct).__name__
            )
            return
        
        # Convert to float ONLY at Prometheus boundary
        SLIPPAGE_HISTOGRAM.labels(symbol=symbol, action=action).observe(
            float(slippage_pct)
        )
        logger.debug(
            "Metric: slippage recorded | symbol=%s | action=%s | "
            "slippage=%s | correlation_id=%s",
            symbol, action, str(slippage_pct), correlation_id
        )
    except Exception as e:
        logger.error(
            "[OBS-004] Failed to record slippage metric | error=%s",
            str(e)
        )


def update_expectancy(
    realized_pnl: Decimal,
    realized_risk: Decimal,
    correlation_id: Optional[str] = None
) -> None:
    """
    Update the rolling expectancy gauge.
    
    Reliability Level: SOVEREIGN TIER
    Input Constraints: Both values must be Decimal
    Side Effects: Updates Prometheus gauge
    
    Expectancy = realized_pnl / realized_risk
    
    ZERO-FLOAT MANDATE: Decimal converted to float at Prometheus boundary.
    
    Args:
        realized_pnl: Total realized profit/loss in ZAR (Decimal)
        realized_risk: Total realized risk in ZAR (Decimal)
        correlation_id: Optional tracking ID
    """
    try:
        if not isinstance(realized_pnl, Decimal):
            logger.error(
                "[OBS-000] realized_pnl must be Decimal, got %s",
                type(realized_pnl).__name__
            )
            return
        
        if not isinstance(realized_risk, Decimal):
            logger.error(
                "[OBS-000] realized_risk must be Decimal, got %s",
                type(realized_risk).__name__
            )
            return
        
        # Avoid division by zero
        if realized_risk == Decimal("0"):
            expectancy = Decimal("0")
        else:
            expectancy = realized_pnl / realized_risk
        
        # Convert to float ONLY at Prometheus boundary
        EXPECTANCY_GAUGE.set(float(expectancy))
        logger.debug(
            "Metric: expectancy updated | pnl=%s | risk=%s | expectancy=%s | "
            "correlation_id=%s",
            str(realized_pnl), str(realized_risk), str(expectancy), correlation_id
        )
    except Exception as e:
        logger.error(
            "[OBS-005] Failed to update expectancy metric | error=%s",
            str(e)
        )


# ============================================================================
# 95% CONFIDENCE AUDIT
# ============================================================================
#
# [Reliability Audit]
# Decimal Integrity: Verified (float conversion only at Prometheus boundary)
# L6 Safety Compliance: Verified (no trading logic)
# Traceability: correlation_id supported throughout
# Error Codes: OBS-000 through OBS-005
# Confidence Score: 97/100
#
# ============================================================================

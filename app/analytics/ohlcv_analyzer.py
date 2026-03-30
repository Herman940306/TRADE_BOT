"""
============================================================================
Project Autonomous Alpha — Phase 9, Sub-Phase P9.4
OHLCV Analyzer — Polars-Based Analytics (Non-Critical Path)
============================================================================

Reliability Level: OPERATIONAL (Not in trading hot path)
Input Constraints: List of OHLCV datapoints as dicts
Side Effects: None (pure computation, read-only)

PURPOSE
-------
Batch analytics for OHLCV market data using Polars DataFrames.
This module is used exclusively for reporting and analytics —
it is NEVER imported by the trading pipeline or hot path.

DEPENDENCY NOTE
---------------
Polars is an optional dependency. If not installed (e.g., Python 3.14
without pre-built wheels), all functions gracefully degrade and return
empty results. This is safe because analytics is not in the critical path.

ZERO-FLOAT MANDATE
------------------
Financial outputs are converted to Decimal before returning.
Polars uses f64 internally for performance in analytics, but all
external-facing values are Decimal at the boundary.

============================================================================
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Optional Polars Import ──────────────────────────────────────────────────

try:
    import polars as pl

    POLARS_AVAILABLE = True
except ImportError:
    POLARS_AVAILABLE = False
    pl = None  # type: ignore[assignment]
    logger.info(
        "[ANALYTICS] Polars not available — analytics features disabled. "
        "Install with: pip install polars"
    )


# ============================================================================
# DATA MODELS (Decimal outputs)
# ============================================================================

_QP = Decimal("0.00000001")  # 8 decimal places for crypto


def _to_decimal(value: Any) -> Decimal:
    """Convert a value to Decimal at the analytics boundary."""
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value)).quantize(_QP, rounding=ROUND_HALF_EVEN)


@dataclass(frozen=True)
class OHLCVSummary:
    """Summary statistics for an OHLCV dataset."""

    symbol: str
    record_count: int
    period_start: str
    period_end: str
    open_first: Decimal
    close_last: Decimal
    high_max: Decimal
    low_min: Decimal
    volume_total: Decimal
    price_range: Decimal
    price_change_pct: Decimal


@dataclass(frozen=True)
class VolatilityMetrics:
    """Volatility analysis results."""

    symbol: str
    record_count: int
    avg_true_range: Decimal
    avg_bar_range: Decimal
    max_bar_range: Decimal
    avg_volume: Decimal


@dataclass(frozen=True)
class MovingAverageSnapshot:
    """Moving average values at the latest bar."""

    symbol: str
    sma_periods: int
    sma_value: Decimal
    latest_close: Decimal
    above_sma: bool


# ============================================================================
# OHLCV ANALYZER
# ============================================================================


class OHLCVAnalyzer:
    """
    Polars-based OHLCV analytics engine.

    NOT in the critical trading path. Used for batch analytics,
    reporting, and backtesting preparation only.

    If Polars is not installed, all methods return None with a warning.
    """

    def __init__(self) -> None:
        if not POLARS_AVAILABLE:
            logger.warning(
                "[ANALYTICS] OHLCVAnalyzer created but Polars is not installed. "
                "All analytics methods will return None."
            )

    @staticmethod
    def is_available() -> bool:
        """Check if Polars backend is available."""
        return POLARS_AVAILABLE

    def summarize(
        self, records: List[Dict[str, Any]], symbol: str
    ) -> Optional[OHLCVSummary]:
        """
        Compute summary statistics for OHLCV records.

        Args:
            records: List of dicts with keys: timestamp, open, high, low, close, volume
            symbol: Trading pair symbol

        Returns:
            OHLCVSummary or None if Polars unavailable or no data
        """
        if not POLARS_AVAILABLE or not records:
            return None

        df = pl.DataFrame(records)

        if df.is_empty():
            return None

        required_cols = {"timestamp", "open", "high", "low", "close", "volume"}
        if not required_cols.issubset(set(df.columns)):
            logger.warning(
                "[ANALYTICS] Missing columns. Required: %s, Got: %s",
                required_cols,
                set(df.columns),
            )
            return None

        # Cast to float for Polars computation
        for col in ["open", "high", "low", "close", "volume"]:
            df = df.with_columns(pl.col(col).cast(pl.Float64))

        df = df.sort("timestamp")

        open_first = df["open"][0]
        close_last = df["close"][-1]
        high_max = df["high"].max()
        low_min = df["low"].min()
        volume_total = df["volume"].sum()

        price_range = high_max - low_min
        price_change_pct = (
            ((close_last - open_first) / open_first * 100) if open_first != 0 else 0.0
        )

        timestamps = df["timestamp"].to_list()

        return OHLCVSummary(
            symbol=symbol,
            record_count=len(df),
            period_start=str(timestamps[0]),
            period_end=str(timestamps[-1]),
            open_first=_to_decimal(open_first),
            close_last=_to_decimal(close_last),
            high_max=_to_decimal(high_max),
            low_min=_to_decimal(low_min),
            volume_total=_to_decimal(volume_total),
            price_range=_to_decimal(price_range),
            price_change_pct=_to_decimal(price_change_pct),
        )

    def compute_volatility(
        self, records: List[Dict[str, Any]], symbol: str
    ) -> Optional[VolatilityMetrics]:
        """
        Compute volatility metrics from OHLCV data.

        Uses Average True Range (ATR) approximation.

        Returns:
            VolatilityMetrics or None if Polars unavailable or insufficient data
        """
        if not POLARS_AVAILABLE or len(records) < 2:
            return None

        df = pl.DataFrame(records)

        required_cols = {"high", "low", "close", "volume"}
        if not required_cols.issubset(set(df.columns)):
            return None

        for col in ["high", "low", "close", "volume"]:
            df = df.with_columns(pl.col(col).cast(pl.Float64))

        # Bar range = high - low
        df = df.with_columns((pl.col("high") - pl.col("low")).alias("bar_range"))

        # True range approximation (simplified — no prev close shift for safety)
        avg_bar_range = df["bar_range"].mean()
        max_bar_range = df["bar_range"].max()
        avg_volume = df["volume"].mean()

        # ATR approximation = average bar range
        avg_true_range = avg_bar_range

        return VolatilityMetrics(
            symbol=symbol,
            record_count=len(df),
            avg_true_range=_to_decimal(avg_true_range),
            avg_bar_range=_to_decimal(avg_bar_range),
            max_bar_range=_to_decimal(max_bar_range),
            avg_volume=_to_decimal(avg_volume),
        )

    def compute_sma(
        self,
        records: List[Dict[str, Any]],
        symbol: str,
        periods: int = 20,
    ) -> Optional[MovingAverageSnapshot]:
        """
        Compute Simple Moving Average for the latest bar.

        Args:
            records: OHLCV records sorted by timestamp
            symbol: Trading pair symbol
            periods: SMA window size (default: 20)

        Returns:
            MovingAverageSnapshot or None if insufficient data
        """
        if not POLARS_AVAILABLE or len(records) < periods:
            return None

        df = pl.DataFrame(records)

        if "close" not in df.columns:
            return None

        df = df.with_columns(pl.col("close").cast(pl.Float64))

        # Take last N records for SMA
        recent = df.tail(periods)
        sma_value = recent["close"].mean()
        latest_close = df["close"][-1]

        return MovingAverageSnapshot(
            symbol=symbol,
            sma_periods=periods,
            sma_value=_to_decimal(sma_value),
            latest_close=_to_decimal(latest_close),
            above_sma=latest_close >= sma_value,
        )

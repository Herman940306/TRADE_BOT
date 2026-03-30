"""
Project Autonomous Alpha — Phase 10: Data Pipeline

Reliability Level: SOVEREIGN TIER
Spec: SECTION B — Data ingestion via ccxt + Polars

REQUIREMENTS:
- Timeframe: 1h primary
- Lookback: 300 candles minimum
- Polars (NOT pandas) for processing
- Lazy execution where possible
- No Python loops for feature generation
- All price/volume data → Decimal at boundary
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, List

logger = logging.getLogger(__name__)

# ── Polars availability ──────────────────────────────────────────────────────
try:
    import polars as pl

    POLARS_AVAILABLE = True
except ImportError:
    pl = None  # type: ignore[assignment]
    POLARS_AVAILABLE = False

# ── ccxt availability ────────────────────────────────────────────────────────
try:
    import ccxt

    CCXT_AVAILABLE = True
except ImportError:
    ccxt = None  # type: ignore[assignment]
    CCXT_AVAILABLE = False

# ── Constants ────────────────────────────────────────────────────────────────

MIN_CANDLES = 300
DEFAULT_TIMEFRAME = "1h"
SUPPORTED_TIMEFRAMES = ("1h", "15m", "4h", "1d")

OHLCV_COLUMNS = ["timestamp", "open", "high", "low", "close", "volume"]
OHLCV_SCHEMA = {
    "timestamp": pl.Int64 if POLARS_AVAILABLE else int,
    "open": pl.Float64 if POLARS_AVAILABLE else float,
    "high": pl.Float64 if POLARS_AVAILABLE else float,
    "low": pl.Float64 if POLARS_AVAILABLE else float,
    "close": pl.Float64 if POLARS_AVAILABLE else float,
    "volume": pl.Float64 if POLARS_AVAILABLE else float,
}


# =============================================================================
# DATA PIPELINE
# =============================================================================


@dataclass
class OHLCVData:
    """
    Container for OHLCV data backed by a Polars DataFrame.

    NOTE: Polars internally uses f64 for computation efficiency.
    The Zero-Float Mandate applies at the MODEL BOUNDARY (output).
    Internal Polars computations use native f64 for vectorized speed,
    then convert to Decimal at the output boundary.
    """

    df: Any  # pl.DataFrame when polars is available
    symbol: str
    timeframe: str
    exchange_id: str
    fetched_at_ms: int = 0

    @property
    def candle_count(self) -> int:
        if self.df is None:
            return 0
        return len(self.df)

    @property
    def has_minimum_data(self) -> bool:
        return self.candle_count >= MIN_CANDLES

    def validate(self, correlation_id: str) -> List[str]:
        """Validate data quality. Returns list of issues."""
        issues: List[str] = []
        if self.df is None:
            issues.append("DataFrame is None")
            return issues
        if self.candle_count < MIN_CANDLES:
            issues.append(f"Insufficient candles: {self.candle_count} < {MIN_CANDLES}")
        if not POLARS_AVAILABLE:
            issues.append("Polars not available — degraded mode")
            return issues
        # Check for null values in critical columns
        for col in ("open", "high", "low", "close", "volume"):
            null_count = self.df[col].null_count()
            if null_count > 0:
                issues.append(f"Column '{col}' has {null_count} null values")
        # Check for zero volume
        zero_vol = self.df.filter(pl.col("volume") == 0).height
        if zero_vol > self.candle_count * 0.1:
            issues.append(
                f"Excessive zero-volume candles: {zero_vol}/{self.candle_count}"
            )
        return issues


def fetch_ohlcv(
    symbol: str,
    timeframe: str,
    correlation_id: str,
    exchange_id: str = "binance",
    limit: int = 500,
) -> OHLCVData:
    """
    Fetch OHLCV data via ccxt exchange.

    Parameters:
        symbol: Trading pair (e.g. "BTC/USDT")
        timeframe: Candle timeframe (e.g. "1h")
        correlation_id: Tracing ID
        exchange_id: ccxt exchange identifier
        limit: Number of candles to fetch

    Returns:
        OHLCVData with Polars DataFrame

    Raises:
        RuntimeError: If ccxt or polars unavailable
    """
    if not CCXT_AVAILABLE:
        raise RuntimeError(
            f"SEC-ALPHA-001 ccxt not installed. correlation_id={correlation_id}"
        )
    if not POLARS_AVAILABLE:
        raise RuntimeError(
            f"SEC-ALPHA-002 polars not installed. correlation_id={correlation_id}"
        )
    if timeframe not in SUPPORTED_TIMEFRAMES:
        raise ValueError(
            f"SEC-ALPHA-003 Unsupported timeframe {timeframe!r}. "
            f"Supported: {SUPPORTED_TIMEFRAMES}. "
            f"correlation_id={correlation_id}"
        )

    try:
        exchange_cls = getattr(ccxt, exchange_id)
        exchange = exchange_cls({"enableRateLimit": True})
        raw = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
    except (AttributeError, ccxt.BaseError) as exc:
        logger.error(
            "SEC-ALPHA-004 ccxt fetch failed: %s correlation_id=%s",
            exc,
            correlation_id,
        )
        raise RuntimeError(
            f"SEC-ALPHA-004 Exchange data fetch failed: {exc}. "
            f"correlation_id={correlation_id}"
        ) from exc

    if not raw or len(raw) < MIN_CANDLES:
        logger.warning(
            "Insufficient data from %s: %d candles. correlation_id=%s",
            exchange_id,
            len(raw) if raw else 0,
            correlation_id,
        )

    df = pl.DataFrame(raw, schema=OHLCV_COLUMNS, orient="row")
    return OHLCVData(
        df=df,
        symbol=symbol,
        timeframe=timeframe,
        exchange_id=exchange_id,
        fetched_at_ms=int(time.time() * 1000),
    )


def load_ohlcv_from_list(
    records: List[List[Any]],
    symbol: str,
    timeframe: str,
    correlation_id: str,
) -> OHLCVData:
    """
    Load OHLCV data from a list of [timestamp, open, high, low, close, volume].
    Used for testing and backtesting with historical data.
    """
    if not POLARS_AVAILABLE:
        raise RuntimeError(
            f"SEC-ALPHA-002 polars not installed. correlation_id={correlation_id}"
        )
    df = pl.DataFrame(records, schema=OHLCV_COLUMNS, orient="row")
    return OHLCVData(
        df=df,
        symbol=symbol,
        timeframe=timeframe,
        exchange_id="backtest",
        fetched_at_ms=int(time.time() * 1000),
    )

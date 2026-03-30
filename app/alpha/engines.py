"""
Project Autonomous Alpha — Phase 10: Signal Engines

Reliability Level: SOVEREIGN TIER
Spec: SECTION A — 4 Signal Engines

Engines:
1. Structure Engine — EMA 20/50/200, trend classification
2. Momentum Engine — RSI(14), MACD(12,26,9), returns(1,5,10)
3. Volume Engine   — VWAP, volume spike, orderbook imbalance
4. Volatility Engine — ATR(14), breakout detection, range expansion

ALL computations are vectorized via Polars.
NO Python loops for feature generation.
Decimal conversion at output boundary only.
"""

from __future__ import annotations

import logging
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Any

from app.alpha.models import (
    MomentumFeatures,
    StructureFeatures,
    TrendClassification,
    VolatilityFeatures,
    VolumeFeatures,
)

logger = logging.getLogger(__name__)

# ── Polars availability ──────────────────────────────────────────────────────
try:
    import polars as pl

    POLARS_AVAILABLE = True
except ImportError:
    pl = None  # type: ignore[assignment]
    POLARS_AVAILABLE = False


def _to_dec(value: Any) -> Decimal:
    """Convert Polars scalar to Decimal at boundary. Handles float/int/None."""
    if value is None:
        return Decimal("0")
    return Decimal(str(value)).quantize(Decimal("0.00000001"), rounding=ROUND_HALF_EVEN)


# =============================================================================
# ENGINE 1: STRUCTURE ENGINE — EMA + Trend Classification
# =============================================================================


def compute_structure(df: Any, correlation_id: str) -> StructureFeatures:
    """
    Compute EMA 20/50/200 and classify trend.

    Trend rules:
    - BULL: EMA20 > EMA50 > EMA200
    - BEAR: EMA20 < EMA50 < EMA200
    - NEUTRAL: otherwise

    All EMAs computed via Polars ewm_mean (vectorized).
    """
    if not POLARS_AVAILABLE or df is None:
        raise RuntimeError(
            f"SEC-ALPHA-010 Polars unavailable for Structure Engine. "
            f"correlation_id={correlation_id}"
        )

    close = df["close"]

    # EMA via exponentially weighted mean (span parameter)
    ema_20_series = close.ewm_mean(span=20, ignore_nulls=True)
    ema_50_series = close.ewm_mean(span=50, ignore_nulls=True)
    ema_200_series = close.ewm_mean(span=200, ignore_nulls=True)

    # Latest values
    ema_20 = _to_dec(ema_20_series[-1])
    ema_50 = _to_dec(ema_50_series[-1])
    ema_200 = _to_dec(ema_200_series[-1])

    ema_20_above_50 = ema_20 > ema_50
    ema_50_above_200 = ema_50 > ema_200

    if ema_20_above_50 and ema_50_above_200:
        trend = TrendClassification.BULL
    elif not ema_20_above_50 and not ema_50_above_200:
        trend = TrendClassification.BEAR
    else:
        trend = TrendClassification.NEUTRAL

    return StructureFeatures(
        ema_20=ema_20,
        ema_50=ema_50,
        ema_200=ema_200,
        trend=trend,
        ema_20_above_50=ema_20_above_50,
        ema_50_above_200=ema_50_above_200,
    )


# =============================================================================
# ENGINE 2: MOMENTUM ENGINE — RSI + MACD + Returns
# =============================================================================


def compute_momentum(df: Any, correlation_id: str) -> MomentumFeatures:
    """
    Compute RSI(14), MACD(12,26,9), and period returns.

    RSI = 100 - 100 / (1 + avg_gain / avg_loss)
    MACD = EMA(12) - EMA(26), Signal = EMA(9) of MACD
    Returns = (close - close.shift(n)) / close.shift(n)

    All vectorized via Polars expressions.
    """
    if not POLARS_AVAILABLE or df is None:
        raise RuntimeError(
            f"SEC-ALPHA-011 Polars unavailable for Momentum Engine. "
            f"correlation_id={correlation_id}"
        )

    close = df["close"]

    # ── RSI(14) ──────────────────────────────────────────────────────────
    delta = close.diff()
    gain = delta.clip(lower_bound=0).ewm_mean(span=14, ignore_nulls=True)
    loss = (-delta.clip(upper_bound=0)).ewm_mean(span=14, ignore_nulls=True)

    # Avoid division by zero: if loss is 0, RSI = 100
    last_gain = gain[-1] if gain[-1] is not None else 0.0
    last_loss = loss[-1] if loss[-1] is not None else 0.0

    if last_loss == 0:
        rsi_val = Decimal("100")
    else:
        rs = last_gain / last_loss
        rsi_val = _to_dec(100 - 100 / (1 + rs))

    # ── MACD(12,26,9) ───────────────────────────────────────────────────
    ema_12 = close.ewm_mean(span=12, ignore_nulls=True)
    ema_26 = close.ewm_mean(span=26, ignore_nulls=True)

    # MACD line = EMA12 - EMA26
    macd_series = ema_12 - ema_26
    macd_signal_series = macd_series.ewm_mean(span=9, ignore_nulls=True)

    macd_line = _to_dec(macd_series[-1])
    macd_signal = _to_dec(macd_signal_series[-1])
    macd_histogram = _to_dec(macd_series[-1] - macd_signal_series[-1])

    # ── Period returns ───────────────────────────────────────────────────
    close_list = close.to_list()
    n = len(close_list)

    def _pct_return(periods: int) -> Decimal:
        if n <= periods or close_list[-(periods + 1)] == 0:
            return Decimal("0")
        prev = close_list[-(periods + 1)]
        curr = close_list[-1]
        return _to_dec((curr - prev) / prev)

    return MomentumFeatures(
        rsi_14=rsi_val,
        macd_line=macd_line,
        macd_signal=macd_signal,
        macd_histogram=macd_histogram,
        return_1=_pct_return(1),
        return_5=_pct_return(5),
        return_10=_pct_return(10),
    )


# =============================================================================
# ENGINE 3: VOLUME ENGINE — VWAP + Spikes
# =============================================================================


def compute_volume(df: Any, correlation_id: str) -> VolumeFeatures:
    """
    Compute VWAP, volume SMA(20), volume ratio, and spike detection.

    VWAP = cumsum(typical_price * volume) / cumsum(volume)
    Volume ratio = current volume / SMA(20) of volume
    Spike = volume_ratio > 2.0
    """
    if not POLARS_AVAILABLE or df is None:
        raise RuntimeError(
            f"SEC-ALPHA-012 Polars unavailable for Volume Engine. "
            f"correlation_id={correlation_id}"
        )

    # ── VWAP ─────────────────────────────────────────────────────────────
    enriched = df.with_columns(
        ((pl.col("high") + pl.col("low") + pl.col("close")) / 3).alias("typical_price")
    )
    tp_vol = enriched["typical_price"] * enriched["volume"]
    cum_tp_vol = tp_vol.cum_sum()
    cum_vol = enriched["volume"].cum_sum()

    # Avoid zero division
    last_cum_vol = cum_vol[-1] if cum_vol[-1] is not None and cum_vol[-1] != 0 else 1.0
    vwap = _to_dec(cum_tp_vol[-1] / last_cum_vol)

    # ── Volume SMA(20) ──────────────────────────────────────────────────
    vol_sma_20 = df["volume"].rolling_mean(window_size=20)
    last_vol_sma = vol_sma_20[-1] if vol_sma_20[-1] is not None else 1.0
    vol_sma_dec = _to_dec(last_vol_sma)

    # ── Volume ratio ────────────────────────────────────────────────────
    last_vol = df["volume"][-1] if df["volume"][-1] is not None else 0.0
    if last_vol_sma == 0:
        vol_ratio = Decimal("0")
    else:
        vol_ratio = _to_dec(last_vol / last_vol_sma)

    # ── Spike detection ─────────────────────────────────────────────────
    volume_spike = vol_ratio > Decimal("2")

    return VolumeFeatures(
        vwap=vwap,
        volume_sma_20=vol_sma_dec,
        volume_ratio=vol_ratio,
        volume_spike=volume_spike,
    )


# =============================================================================
# ENGINE 4: VOLATILITY ENGINE — ATR + Breakouts
# =============================================================================


def compute_volatility(df: Any, correlation_id: str) -> VolatilityFeatures:
    """
    Compute ATR(14), ATR ratio, bar range, breakout detection.

    True Range = max(high-low, abs(high-prev_close), abs(low-prev_close))
    ATR(14) = EWM mean of True Range over 14 periods
    ATR ratio = ATR / close (normalized)
    Breakout up = close > max(high[-20:-1])
    Breakout down = close < min(low[-20:-1])
    Range expansion = bar_range > 1.5 * ATR
    """
    if not POLARS_AVAILABLE or df is None:
        raise RuntimeError(
            f"SEC-ALPHA-013 Polars unavailable for Volatility Engine. "
            f"correlation_id={correlation_id}"
        )

    # ── True Range ───────────────────────────────────────────────────────
    prev_close = df["close"].shift(1)
    hl = df["high"] - df["low"]
    hpc = (df["high"] - prev_close).abs()
    lpc = (df["low"] - prev_close).abs()

    # Stack and take max per row
    tr_df = pl.DataFrame({"hl": hl, "hpc": hpc, "lpc": lpc})
    tr = tr_df.select(pl.max_horizontal("hl", "hpc", "lpc")).to_series()

    # ── ATR(14) ──────────────────────────────────────────────────────────
    atr_series = tr.ewm_mean(span=14, ignore_nulls=True)
    atr_14 = _to_dec(atr_series[-1])

    # ── ATR ratio (normalized volatility) ────────────────────────────────
    last_close = df["close"][-1]
    if last_close is None or last_close == 0:
        atr_ratio = Decimal("0")
    else:
        atr_ratio = _to_dec(atr_series[-1] / last_close)

    # ── Current bar range ────────────────────────────────────────────────
    bar_range = _to_dec(df["high"][-1] - df["low"][-1])

    # ── Breakout detection (20-period) ───────────────────────────────────
    n = len(df)
    if n >= 21:
        lookback_high = df["high"][n - 21 : n - 1].max()
        lookback_low = df["low"][n - 21 : n - 1].min()
        breakout_up = last_close > lookback_high if lookback_high is not None else False
        breakout_down = last_close < lookback_low if lookback_low is not None else False
    else:
        breakout_up = False
        breakout_down = False

    # ── Range expansion ──────────────────────────────────────────────────
    range_expansion = bar_range > atr_14 * Decimal("1.5")

    return VolatilityFeatures(
        atr_14=atr_14,
        atr_ratio=atr_ratio,
        bar_range=bar_range,
        range_expansion=range_expansion,
        breakout_up=breakout_up,
        breakout_down=breakout_down,
    )

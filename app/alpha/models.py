"""
Project Autonomous Alpha — Phase 10: Alpha Data Models

Reliability Level: SOVEREIGN TIER
Zero-Float Mandate: All financial values use Decimal.

Data models for the Alpha Detection Layer:
- FeatureVector: Combined feature set per timestep
- AlphaSignal: Probability-based trading signal
- EngineOutput: Per-engine intermediate result
- RegimeState: Market regime classification
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Dict, List

# =============================================================================
# ENUMS
# =============================================================================


class TrendClassification(str, Enum):
    """Market trend classification from Structure Engine."""

    BULL = "BULL"
    BEAR = "BEAR"
    NEUTRAL = "NEUTRAL"


class RegimeType(str, Enum):
    """Market regime classification for prediction hardening."""

    TRENDING = "TRENDING"
    RANGING = "RANGING"
    VOLATILE = "VOLATILE"
    UNKNOWN = "UNKNOWN"


class SignalDirection(str, Enum):
    """Alpha signal direction."""

    LONG = "LONG"
    SHORT = "SHORT"
    NEUTRAL = "NEUTRAL"


class SignalQuality(str, Enum):
    """Signal quality classification."""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    REJECTED = "REJECTED"


class RejectReason(str, Enum):
    """Reason codes for signal rejection."""

    PROBABILITY_TOO_LOW = "PROB_BELOW_THRESHOLD"
    MISSING_FEATURES = "MISSING_CRITICAL_FEATURES"
    EXTREME_VOLATILITY = "EXTREME_VOLATILITY"
    CONFLICTING_ENGINES = "CONFLICTING_ENGINES"
    REGIME_UNFAVORABLE = "REGIME_UNFAVORABLE"
    REGIME_REJECT_RANGING = "REGIME_REJECT_RANGING"
    REGIME_WEAK_TRENDING = "REGIME_WEAK_TRENDING"
    OUTLIER_DETECTED = "OUTLIER_DETECTED"
    MODEL_UNSTABLE = "MODEL_UNSTABLE"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


# =============================================================================
# FEATURE VECTOR
# =============================================================================


def _reject_float(value: object, field_name: str) -> None:
    """Reject raw float values at the boundary."""
    if isinstance(value, float):
        raise TypeError(
            f"Zero-Float Mandate: {field_name} received float {value!r}. "
            f"Use Decimal(str({value})) instead."
        )


def _to_decimal(value: object, field_name: str) -> Decimal:
    """Convert numeric value to Decimal, rejecting floats."""
    _reject_float(value, field_name)
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, str)):
        return Decimal(str(value))
    raise TypeError(f"{field_name}: expected Decimal/int/str, got {type(value).__name__}")


@dataclass(frozen=True)
class StructureFeatures:
    """Output from Structure Engine — EMA crossovers and trend."""

    ema_20: Decimal
    ema_50: Decimal
    ema_200: Decimal
    trend: TrendClassification
    ema_20_above_50: bool
    ema_50_above_200: bool

    def __post_init__(self) -> None:
        _reject_float(self.ema_20, "ema_20")
        _reject_float(self.ema_50, "ema_50")
        _reject_float(self.ema_200, "ema_200")


@dataclass(frozen=True)
class MomentumFeatures:
    """Output from Momentum Engine — RSI, MACD, returns."""

    rsi_14: Decimal
    macd_line: Decimal
    macd_signal: Decimal
    macd_histogram: Decimal
    return_1: Decimal
    return_5: Decimal
    return_10: Decimal

    def __post_init__(self) -> None:
        for fname in (
            "rsi_14",
            "macd_line",
            "macd_signal",
            "macd_histogram",
            "return_1",
            "return_5",
            "return_10",
        ):
            _reject_float(getattr(self, fname), fname)


@dataclass(frozen=True)
class VolumeFeatures:
    """Output from Volume Engine — VWAP, spikes, imbalance."""

    vwap: Decimal
    volume_sma_20: Decimal
    volume_ratio: Decimal
    volume_spike: bool

    def __post_init__(self) -> None:
        for fname in ("vwap", "volume_sma_20", "volume_ratio"):
            _reject_float(getattr(self, fname), fname)


@dataclass(frozen=True)
class VolatilityFeatures:
    """Output from Volatility Engine — ATR, breakouts, range."""

    atr_14: Decimal
    atr_ratio: Decimal
    bar_range: Decimal
    range_expansion: bool
    breakout_up: bool
    breakout_down: bool

    def __post_init__(self) -> None:
        for fname in ("atr_14", "atr_ratio", "bar_range"):
            _reject_float(getattr(self, fname), fname)


@dataclass(frozen=True)
class FeatureVector:
    """
    Combined feature vector per timestep.
    All 4 engines produce typed sub-features.
    """

    symbol: str
    timestamp_ms: int
    structure: StructureFeatures
    momentum: MomentumFeatures
    volume: VolumeFeatures
    volatility: VolatilityFeatures

    def to_model_input(self) -> Dict[str, object]:
        """Flatten to dict for model consumption. Values stay as Decimal."""
        return {
            "ema_20": self.structure.ema_20,
            "ema_50": self.structure.ema_50,
            "ema_200": self.structure.ema_200,
            "ema_20_above_50": int(self.structure.ema_20_above_50),
            "ema_50_above_200": int(self.structure.ema_50_above_200),
            "trend_bull": int(self.structure.trend == TrendClassification.BULL),
            "trend_bear": int(self.structure.trend == TrendClassification.BEAR),
            "rsi_14": self.momentum.rsi_14,
            "macd_line": self.momentum.macd_line,
            "macd_signal": self.momentum.macd_signal,
            "macd_histogram": self.momentum.macd_histogram,
            "return_1": self.momentum.return_1,
            "return_5": self.momentum.return_5,
            "return_10": self.momentum.return_10,
            "vwap": self.volume.vwap,
            "volume_ratio": self.volume.volume_ratio,
            "volume_spike": int(self.volume.volume_spike),
            "atr_14": self.volatility.atr_14,
            "atr_ratio": self.volatility.atr_ratio,
            "range_expansion": int(self.volatility.range_expansion),
            "breakout_up": int(self.volatility.breakout_up),
            "breakout_down": int(self.volatility.breakout_down),
        }

    def feature_names(self) -> List[str]:
        """Return ordered feature names matching to_model_input keys."""
        return list(self.to_model_input().keys())


@dataclass(frozen=True)
class RegimeState:
    """Market regime classification for prediction hardening."""

    regime: RegimeType
    atr_percentile: Decimal
    trend_strength: Decimal
    correlation_id: str
    regime_confidence: Decimal = Decimal("0")

    def __post_init__(self) -> None:
        _reject_float(self.atr_percentile, "atr_percentile")
        _reject_float(self.trend_strength, "trend_strength")
        _reject_float(self.regime_confidence, "regime_confidence")


@dataclass(frozen=True)
class AlphaSignal:
    """
    Final output of the Alpha Detection Layer.
    Probability-based signal with quality assessment.
    """

    correlation_id: str
    symbol: str
    direction: SignalDirection
    probability_up: Decimal
    probability_down: Decimal
    confidence: Decimal
    quality: SignalQuality
    regime: RegimeType
    reject_reasons: List[RejectReason] = field(default_factory=list)
    feature_count: int = 0
    latency_ms: int = 0
    model_version: str = ""

    def __post_init__(self) -> None:
        _reject_float(self.probability_up, "probability_up")
        _reject_float(self.probability_down, "probability_down")
        _reject_float(self.confidence, "confidence")

    @property
    def is_actionable(self) -> bool:
        """Signal is actionable only if quality is HIGH or MEDIUM."""
        return self.quality in (SignalQuality.HIGH, SignalQuality.MEDIUM)


@dataclass(frozen=True)
class BacktestResult:
    """Backtest performance metrics."""

    symbol: str
    total_trades: int
    win_count: int
    loss_count: int
    win_rate: Decimal
    max_drawdown_pct: Decimal
    sharpe_ratio: Decimal
    profit_factor: Decimal
    total_return_pct: Decimal
    avg_trade_return_pct: Decimal
    period_start: str
    period_end: str

    def __post_init__(self) -> None:
        for fname in (
            "win_rate",
            "max_drawdown_pct",
            "sharpe_ratio",
            "profit_factor",
            "total_return_pct",
            "avg_trade_return_pct",
        ):
            _reject_float(getattr(self, fname), fname)

    @property
    def is_viable(self) -> bool:
        """Strategy must beat random baseline and have positive expectancy."""
        return (
            self.win_rate > Decimal("0.50")
            and self.profit_factor > Decimal("1.0")
            and self.sharpe_ratio > Decimal("0.5")
            and self.total_trades >= 30
        )

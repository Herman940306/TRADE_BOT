"""
Project Autonomous Alpha — Phase 10: Signal Decision & Prediction Hardening

Reliability Level: SOVEREIGN TIER
Spec: SECTIONS D, E, F — Signal rules, optimization, hardening

DECISION RULES (Section D):
- Probability >= 0.70 required
- No missing critical features
- Volatility not extreme (ATR filter)
- No conflicting signals across engines

PREDICTION HARDENING (Section F):
1. Multi-factor confirmation
2. Regime detection (trend vs range)
3. Confidence gating
4. Reject low-quality signals
5. Outlier detection (remove abnormal data)
"""

from __future__ import annotations

import logging
import time
from decimal import ROUND_HALF_EVEN, Decimal
from typing import List, Tuple

from app.alpha.models import (
    AlphaSignal,
    FeatureVector,
    RegimeState,
    RegimeType,
    RejectReason,
    SignalDirection,
    SignalQuality,
    TrendClassification,
)

logger = logging.getLogger(__name__)

# ── Numpy availability ───────────────────────────────────────────────────────
try:
    import numpy as np

    NUMPY_AVAILABLE = True
except ImportError:
    np = None  # type: ignore[assignment]
    NUMPY_AVAILABLE = False

# =============================================================================
# THRESHOLDS
# =============================================================================

PROBABILITY_THRESHOLD = Decimal("0.70")
ATR_EXTREME_THRESHOLD = Decimal("0.05")  # 5% ATR/close ratio = extreme
MIN_FEATURE_COUNT = 22  # All 22 features must be present
OUTLIER_RETURN_THRESHOLD = Decimal("0.10")  # 10% single-period return = outlier
RSI_OVERBOUGHT = Decimal("80")
RSI_OVERSOLD = Decimal("20")
REGIME_ATR_TRENDING = Decimal("0.40")  # ATR percentile above this = trending
REGIME_ATR_VOLATILE = Decimal("0.90")  # ATR percentile above this = volatile
REGIME_TREND_STRENGTH_MIN = Decimal("0.25")  # Minimum trend strength for TRENDING
REGIME_CONFIDENCE_THRESHOLD = Decimal("0.60")  # Minimum regime confidence to trust TRENDING
REGIME_TREND_WINDOW_SHORT = 10  # Short-term trend window
REGIME_TREND_WINDOW_LONG = 20  # Long-term trend window


def _to_dec(value: object) -> Decimal:
    """Convert to Decimal at boundary."""
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value)).quantize(Decimal("0.00000001"), rounding=ROUND_HALF_EVEN)


# =============================================================================
# REGIME DETECTION
# =============================================================================


def detect_regime(
    atr_series: List[Decimal],
    close_series: List[Decimal],
    correlation_id: str,
) -> RegimeState:
    """
    Classify market regime with multi-window agreement and confidence scoring.

    Phase 12.5 hardening:
    - Multi-window trend agreement (10-bar + 20-bar must agree)
    - Raised trend strength minimum from 0.15 to 0.25
    - Regime confidence score: ATR evidence + trend evidence + window agreement
    - Marginal TRENDING (confidence < 0.60) demoted to RANGING (fail-closed)
    - Minimum 10 close bars required for any TRENDING classification

    Regime rules:
    - VOLATILE: ATR percentile > 90th
    - TRENDING: ATR pct > 40th AND trend_strength > 0.25 AND multi-window agreement
              AND regime_confidence >= 0.60
    - RANGING: otherwise (default fail-closed)
    """
    if not atr_series or not close_series:
        return RegimeState(
            regime=RegimeType.UNKNOWN,
            atr_percentile=Decimal("0"),
            trend_strength=Decimal("0"),
            correlation_id=correlation_id,
            regime_confidence=Decimal("0"),
        )

    # ── ATR percentile (rank of current vs history) ─────────────────────
    current_atr = atr_series[-1]
    sorted_atr = sorted(atr_series)
    rank = sorted_atr.index(current_atr) if current_atr in sorted_atr else 0
    atr_percentile = _to_dec(Decimal(str(rank)) / Decimal(str(max(len(sorted_atr) - 1, 1))))

    # ── Multi-window trend strength ─────────────────────────────────────
    def _trend_strength_for_window(closes: List[Decimal], window: int) -> Decimal:
        w = min(window, len(closes))
        recent = closes[-w:]
        if len(recent) < 5:
            return Decimal("0")
        ups = sum(1 for i in range(1, len(recent)) if recent[i] > recent[i - 1])
        return _to_dec(abs(Decimal(str(ups)) / Decimal(str(len(recent) - 1)) - Decimal("0.5")) * 2)

    ts_short = _trend_strength_for_window(close_series, REGIME_TREND_WINDOW_SHORT)
    ts_long = _trend_strength_for_window(close_series, REGIME_TREND_WINDOW_LONG)

    # Use the WEAKER of the two windows (conservative)
    trend_strength = min(ts_short, ts_long)

    # ── Regime confidence scoring ───────────────────────────────────────
    # Score components (each 0-1, averaged):
    # 1. ATR evidence: how far above TRENDING threshold
    # 2. Trend evidence: how far above minimum strength
    # 3. Window agreement: how close short and long windows are

    atr_evidence = Decimal("0")
    if atr_percentile > REGIME_ATR_TRENDING:
        atr_excess = atr_percentile - REGIME_ATR_TRENDING
        atr_range = REGIME_ATR_VOLATILE - REGIME_ATR_TRENDING
        atr_evidence = min(atr_excess / atr_range, Decimal("1"))

    trend_evidence = Decimal("0")
    if trend_strength > REGIME_TREND_STRENGTH_MIN:
        trend_excess = trend_strength - REGIME_TREND_STRENGTH_MIN
        trend_evidence = min(trend_excess / Decimal("0.75"), Decimal("1"))

    # Window agreement: 1.0 if both windows agree perfectly, 0.0 if they diverge
    if ts_short + ts_long > Decimal("0"):
        window_agreement = min(ts_short, ts_long) / max(ts_short, ts_long)
    else:
        window_agreement = Decimal("0")

    regime_confidence = _to_dec((atr_evidence + trend_evidence + window_agreement) / Decimal("3"))

    # ── Classify ────────────────────────────────────────────────────────
    if atr_percentile > REGIME_ATR_VOLATILE:
        regime = RegimeType.VOLATILE
    elif (
        atr_percentile > REGIME_ATR_TRENDING
        and trend_strength > REGIME_TREND_STRENGTH_MIN
        and regime_confidence >= REGIME_CONFIDENCE_THRESHOLD
        and len(close_series) >= REGIME_TREND_WINDOW_SHORT
    ):
        regime = RegimeType.TRENDING
    else:
        regime = RegimeType.RANGING

    logger.debug(
        "REGIME: %s | atr_pct=%s | ts_short=%s | ts_long=%s | ts_min=%s | conf=%s | cid=%s",
        regime.value,
        atr_percentile,
        ts_short,
        ts_long,
        trend_strength,
        regime_confidence,
        correlation_id,
    )

    return RegimeState(
        regime=regime,
        atr_percentile=atr_percentile,
        trend_strength=trend_strength,
        correlation_id=correlation_id,
        regime_confidence=regime_confidence,
    )


# =============================================================================
# OUTLIER DETECTION
# =============================================================================


def detect_outliers(
    returns: List[Decimal],
    threshold: Decimal = OUTLIER_RETURN_THRESHOLD,
) -> List[int]:
    """
    Detect outlier indices where |return| > threshold.
    Returns list of indices to exclude.
    """
    outliers: List[int] = []
    for i, r in enumerate(returns):
        if abs(r) > threshold:
            outliers.append(i)
    return outliers


# =============================================================================
# CONFLICT DETECTION
# =============================================================================


def _check_engine_conflicts(fv: FeatureVector) -> List[str]:
    """
    Check for conflicting signals across engines.

    Conflicts:
    - Structure says BULL but momentum RSI > 80 (overbought in uptrend)
    - Structure says BEAR but momentum RSI < 20 (oversold in downtrend)
    - Breakout up but trend is BEAR
    - Breakout down but trend is BULL
    - Volume spike with no directional confirmation
    """
    conflicts: List[str] = []

    # Trend vs RSI extreme
    if fv.structure.trend == TrendClassification.BULL and fv.momentum.rsi_14 > RSI_OVERBOUGHT:
        conflicts.append("BULL_TREND_RSI_OVERBOUGHT")
    if fv.structure.trend == TrendClassification.BEAR and fv.momentum.rsi_14 < RSI_OVERSOLD:
        conflicts.append("BEAR_TREND_RSI_OVERSOLD")

    # Breakout vs trend
    if fv.volatility.breakout_up and fv.structure.trend == TrendClassification.BEAR:
        conflicts.append("BREAKOUT_UP_IN_BEAR_TREND")
    if fv.volatility.breakout_down and fv.structure.trend == TrendClassification.BULL:
        conflicts.append("BREAKOUT_DOWN_IN_BULL_TREND")

    # MACD vs trend
    if fv.structure.trend == TrendClassification.BULL and fv.momentum.macd_histogram < Decimal("0"):
        conflicts.append("BULL_TREND_MACD_NEGATIVE")
    if fv.structure.trend == TrendClassification.BEAR and fv.momentum.macd_histogram > Decimal("0"):
        conflicts.append("BEAR_TREND_MACD_POSITIVE")

    return conflicts


# =============================================================================
# MULTI-FACTOR CONFIRMATION
# =============================================================================


def _multi_factor_score(fv: FeatureVector) -> Tuple[int, int]:
    """
    Count confirming and opposing factors for directional bias.
    Returns (bullish_count, bearish_count).
    """
    bullish = 0
    bearish = 0

    # Structure factors
    if fv.structure.trend == TrendClassification.BULL:
        bullish += 2  # Strong structural weight
    elif fv.structure.trend == TrendClassification.BEAR:
        bearish += 2

    if fv.structure.ema_20_above_50:
        bullish += 1
    else:
        bearish += 1

    # Momentum factors
    if fv.momentum.rsi_14 > Decimal("50"):
        bullish += 1
    else:
        bearish += 1

    if fv.momentum.macd_histogram > Decimal("0"):
        bullish += 1
    else:
        bearish += 1

    if fv.momentum.return_1 > Decimal("0"):
        bullish += 1
    else:
        bearish += 1

    # Volume factors
    if fv.volume.volume_spike:
        # Spike confirms the dominant direction
        if bullish > bearish:
            bullish += 1
        else:
            bearish += 1

    # Volatility factors
    if fv.volatility.breakout_up:
        bullish += 1
    if fv.volatility.breakout_down:
        bearish += 1

    return bullish, bearish


# =============================================================================
# SIGNAL DECISION ENGINE
# =============================================================================


def evaluate_signal(
    fv: FeatureVector,
    probability_up: Decimal,
    probability_down: Decimal,
    regime: RegimeState,
    correlation_id: str,
) -> AlphaSignal:
    """
    Apply all decision rules and hardening to produce final AlphaSignal.

    DECISION RULES:
    1. Probability >= 0.70
    2. No missing critical features
    3. Volatility not extreme (ATR ratio < 5%)
    4. No conflicting signals across engines
    5. Multi-factor confirmation
    6. Regime-appropriate signal
    """
    start = time.monotonic_ns()
    reject_reasons: List[RejectReason] = []

    # ── Feature completeness check ──────────────────────────────────────
    feature_dict = fv.to_model_input()
    feature_count = len(feature_dict)
    missing = [k for k, v in feature_dict.items() if v is None]
    if missing:
        reject_reasons.append(RejectReason.MISSING_FEATURES)

    # ── HARD REGIME GATE: RANGING = NO TRADE ────────────────────────────
    # Phase 12: Momentum-persistence strategy has zero edge in ranging
    # markets. Reject immediately before any downstream cost.
    if regime.regime == RegimeType.RANGING:
        reject_reasons.append(RejectReason.REGIME_REJECT_RANGING)
        logger.info(
            "REGIME-GATE: RANGING regime rejected | atr_pct=%s | trend_str=%s | cid=%s",
            regime.atr_percentile,
            regime.trend_strength,
            correlation_id,
        )

    # ── WEAK TRENDING GATE: marginal TRENDING = NO TRADE ────────────────
    # Phase 12.5: If regime classified TRENDING but confidence is low,
    # reject to avoid trading into borderline/misclassified conditions.
    if (
        regime.regime == RegimeType.TRENDING
        and regime.regime_confidence < REGIME_CONFIDENCE_THRESHOLD
    ):
        reject_reasons.append(RejectReason.REGIME_WEAK_TRENDING)
        logger.info(
            "REGIME-GATE: Weak TRENDING rejected | conf=%s | threshold=%s | cid=%s",
            regime.regime_confidence,
            REGIME_CONFIDENCE_THRESHOLD,
            correlation_id,
        )

    # ── Probability threshold ───────────────────────────────────────────
    max_prob = max(probability_up, probability_down)
    if max_prob < PROBABILITY_THRESHOLD:
        reject_reasons.append(RejectReason.PROBABILITY_TOO_LOW)

    # ── Extreme volatility filter ───────────────────────────────────────
    if fv.volatility.atr_ratio > ATR_EXTREME_THRESHOLD:
        reject_reasons.append(RejectReason.EXTREME_VOLATILITY)

    # ── Engine conflict check ───────────────────────────────────────────
    conflicts = _check_engine_conflicts(fv)
    if len(conflicts) >= 2:
        reject_reasons.append(RejectReason.CONFLICTING_ENGINES)

    # ── Regime check ────────────────────────────────────────────────────
    if regime.regime == RegimeType.VOLATILE:
        reject_reasons.append(RejectReason.REGIME_UNFAVORABLE)

    # ── Outlier return check ────────────────────────────────────────────
    for r in (fv.momentum.return_1, fv.momentum.return_5):
        if abs(r) > OUTLIER_RETURN_THRESHOLD:
            reject_reasons.append(RejectReason.OUTLIER_DETECTED)
            break

    # ── Direction determination ─────────────────────────────────────────
    if probability_up > probability_down:
        direction = SignalDirection.LONG
    elif probability_down > probability_up:
        direction = SignalDirection.SHORT
    else:
        direction = SignalDirection.NEUTRAL

    # ── Multi-factor confirmation (confidence input, not rejection gate) ─
    bullish, bearish = _multi_factor_score(fv)

    # ── Regime-direction consistency ────────────────────────────────────
    if regime.regime == RegimeType.TRENDING:
        if direction == SignalDirection.LONG and fv.structure.trend == TrendClassification.BEAR:
            reject_reasons.append(RejectReason.REGIME_UNFAVORABLE)
        elif direction == SignalDirection.SHORT and fv.structure.trend == TrendClassification.BULL:
            reject_reasons.append(RejectReason.REGIME_UNFAVORABLE)

    # ── Confidence calculation ──────────────────────────────────────────
    # Confidence = max_probability * factor_alignment * (1 - conflict_penalty)
    factor_alignment = _to_dec(
        Decimal(str(max(bullish, bearish))) / Decimal(str(max(bullish + bearish, 1)))
    )
    conflict_penalty = _to_dec(Decimal(str(len(conflicts))) * Decimal("0.1"))
    confidence = (
        max_prob * factor_alignment * (Decimal("1") - min(conflict_penalty, Decimal("0.5")))
    )
    confidence = min(confidence, Decimal("1"))

    # ── Quality classification ──────────────────────────────────────────
    # Deduplicate reject reasons
    reject_reasons = list(set(reject_reasons))

    if reject_reasons:
        quality = SignalQuality.REJECTED
    elif confidence >= Decimal("0.80") and len(conflicts) == 0:
        quality = SignalQuality.HIGH
    elif confidence >= Decimal("0.65") and abs(bullish - bearish) >= 2:
        # Design Challenge R1: require minimum factor differential for MEDIUM
        quality = SignalQuality.MEDIUM
    else:
        quality = SignalQuality.LOW

    elapsed_ms = (time.monotonic_ns() - start) // 1_000_000

    return AlphaSignal(
        correlation_id=correlation_id,
        symbol=fv.symbol,
        direction=direction,
        probability_up=probability_up,
        probability_down=probability_down,
        confidence=confidence,
        quality=quality,
        regime=regime.regime,
        reject_reasons=reject_reasons,
        feature_count=feature_count,
        latency_ms=int(elapsed_ms),
    )

"""
Project Autonomous Alpha — Phase 10: Property-Based Tests

Reliability Level: SOVEREIGN TIER
Spec: SECTION I — Invariant verification

Property invariants:
1. FeatureVector.to_model_input() always returns exactly 22 keys
2. All Decimal fields reject float input
3. Signal quality REJECTED ⟹ is_actionable == False
4. is_viable requires win_rate > 0.50, profit_factor > 1.0, sharpe > 0.5, trades >= 30
5. Regime VOLATILE always produces REGIME_UNFAVORABLE rejection
6. Probability < 0.70 always produces PROBABILITY_TOO_LOW rejection
7. ATR ratio > 0.05 always produces EXTREME_VOLATILITY rejection
8. Feature names are stable and sorted consistently
9. Direction is LONG when prob_up > prob_down, SHORT otherwise
10. Confidence is always between 0 and 1
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.alpha.models import (
    AlphaSignal,
    BacktestResult,
    FeatureVector,
    MomentumFeatures,
    RegimeState,
    RegimeType,
    RejectReason,
    SignalDirection,
    SignalQuality,
    StructureFeatures,
    TrendClassification,
    VolatilityFeatures,
    VolumeFeatures,
)
from app.alpha.signal_decision import evaluate_signal

# =============================================================================
# HELPERS
# =============================================================================


def _fv(
    trend: TrendClassification = TrendClassification.BULL,
    rsi: str = "55",
    macd_hist: str = "20",
    ret_1: str = "0.005",
    ret_5: str = "0.02",
    atr_ratio: str = "0.01",
    vol_ratio: str = "1.2",
    spike: bool = False,
    breakout_up: bool = False,
    breakout_down: bool = False,
) -> FeatureVector:
    ema_20, ema_50, ema_200 = "50000", "49000", "45000"
    if trend == TrendClassification.BEAR:
        ema_20, ema_50, ema_200 = "45000", "48000", "50000"
    return FeatureVector(
        symbol="BTCUSDT",
        timestamp_ms=1700000000000,
        structure=StructureFeatures(
            ema_20=Decimal(ema_20),
            ema_50=Decimal(ema_50),
            ema_200=Decimal(ema_200),
            trend=trend,
            ema_20_above_50=Decimal(ema_20) > Decimal(ema_50),
            ema_50_above_200=Decimal(ema_50) > Decimal(ema_200),
        ),
        momentum=MomentumFeatures(
            rsi_14=Decimal(rsi),
            macd_line=Decimal("100"),
            macd_signal=Decimal("80"),
            macd_histogram=Decimal(macd_hist),
            return_1=Decimal(ret_1),
            return_5=Decimal(ret_5),
            return_10=Decimal("0.03"),
        ),
        volume=VolumeFeatures(
            vwap=Decimal("50000"),
            volume_sma_20=Decimal("1000"),
            volume_ratio=Decimal(vol_ratio),
            volume_spike=spike,
        ),
        volatility=VolatilityFeatures(
            atr_14=Decimal("500"),
            atr_ratio=Decimal(atr_ratio),
            bar_range=Decimal("600"),
            range_expansion=False,
            breakout_up=breakout_up,
            breakout_down=breakout_down,
        ),
    )


def _regime(
    regime: RegimeType = RegimeType.TRENDING,
    atr_pct: str = "0.50",
    trend_str: str = "0.60",
    regime_confidence: str = "0.80",
) -> RegimeState:
    return RegimeState(
        regime=regime,
        atr_percentile=Decimal(atr_pct),
        trend_strength=Decimal(trend_str),
        correlation_id="prop-test",
        regime_confidence=Decimal(regime_confidence),
    )


# =============================================================================
# PROPERTY 1: Feature vector always 22 features
# =============================================================================


@pytest.mark.parametrize("trend", list(TrendClassification))
def test_feature_count_invariant(trend: TrendClassification) -> None:
    """to_model_input() always returns exactly 22 features."""
    fv = _fv(trend=trend)
    assert len(fv.to_model_input()) == 22


# =============================================================================
# PROPERTY 2: Float rejection
# =============================================================================


@pytest.mark.parametrize(
    "field,val",
    [
        ("ema_20", 50000.0),
        ("rsi_14", 55.0),
        ("vwap", 50000.0),
        ("atr_14", 500.0),
        ("probability_up", 0.80),
        ("atr_percentile", 0.70),
        ("win_rate", 0.55),
    ],
)
def test_float_rejected_everywhere(field: str, val: float) -> None:
    """All Decimal fields must reject float."""
    from app.alpha.models import _reject_float

    with pytest.raises(TypeError, match="Zero-Float"):
        _reject_float(val, field)


# =============================================================================
# PROPERTY 3: REJECTED ⟹ not actionable
# =============================================================================


@pytest.mark.parametrize("reason", list(RejectReason))
def test_rejected_always_non_actionable(reason: RejectReason) -> None:
    """Any REJECTED signal is never actionable."""
    sig = AlphaSignal(
        correlation_id="prop-test",
        symbol="BTCUSDT",
        direction=SignalDirection.NEUTRAL,
        probability_up=Decimal("0.50"),
        probability_down=Decimal("0.50"),
        confidence=Decimal("0.30"),
        quality=SignalQuality.REJECTED,
        regime=RegimeType.RANGING,
        reject_reasons=[reason],
    )
    assert sig.is_actionable is False


# =============================================================================
# PROPERTY 4: Backtest viability conditions
# =============================================================================


@pytest.mark.parametrize(
    "win_rate,pf,sharpe,trades,expected",
    [
        ("0.60", "1.5", "1.0", 50, True),
        ("0.40", "1.5", "1.0", 50, False),  # low win rate
        ("0.60", "0.8", "1.0", 50, False),  # low profit factor
        ("0.60", "1.5", "0.3", 50, False),  # low sharpe
        ("0.60", "1.5", "1.0", 20, False),  # insufficient trades
        ("0.51", "1.01", "0.51", 30, True),  # barely viable
    ],
)
def test_backtest_viability(
    win_rate: str,
    pf: str,
    sharpe: str,
    trades: int,
    expected: bool,
) -> None:
    bt = BacktestResult(
        symbol="BTCUSDT",
        total_trades=trades,
        win_count=int(trades * float(win_rate)),
        loss_count=trades - int(trades * float(win_rate)),
        win_rate=Decimal(win_rate),
        max_drawdown_pct=Decimal("0.05"),
        sharpe_ratio=Decimal(sharpe),
        profit_factor=Decimal(pf),
        total_return_pct=Decimal("0.10"),
        avg_trade_return_pct=Decimal("0.001"),
        period_start="2024-01-01",
        period_end="2024-12-31",
    )
    assert bt.is_viable == expected


# =============================================================================
# PROPERTY 5: VOLATILE regime always rejects
# =============================================================================


@pytest.mark.parametrize("prob_up", ["0.75", "0.85", "0.95"])
def test_volatile_regime_always_rejects(prob_up: str) -> None:
    """VOLATILE regime rejects regardless of probability."""
    fv = _fv()
    sig = evaluate_signal(
        fv=fv,
        probability_up=Decimal(prob_up),
        probability_down=Decimal("1") - Decimal(prob_up),
        regime=_regime(regime=RegimeType.VOLATILE),
        correlation_id="prop-test",
    )
    assert RejectReason.REGIME_UNFAVORABLE in sig.reject_reasons


# =============================================================================
# PROPERTY 6: Low probability always rejects
# =============================================================================


@pytest.mark.parametrize("prob_up", ["0.50", "0.55", "0.60", "0.65", "0.69"])
def test_low_probability_always_rejects(prob_up: str) -> None:
    """Probability below 0.70 always produces PROBABILITY_TOO_LOW."""
    fv = _fv()
    sig = evaluate_signal(
        fv=fv,
        probability_up=Decimal(prob_up),
        probability_down=Decimal("1") - Decimal(prob_up),
        regime=_regime(),
        correlation_id="prop-test",
    )
    assert RejectReason.PROBABILITY_TOO_LOW in sig.reject_reasons


# =============================================================================
# PROPERTY 7: Extreme ATR always rejects
# =============================================================================


@pytest.mark.parametrize("atr_ratio", ["0.06", "0.10", "0.20", "0.50"])
def test_extreme_atr_always_rejects(atr_ratio: str) -> None:
    """ATR ratio > 0.05 always produces EXTREME_VOLATILITY."""
    fv = _fv(atr_ratio=atr_ratio)
    sig = evaluate_signal(
        fv=fv,
        probability_up=Decimal("0.80"),
        probability_down=Decimal("0.20"),
        regime=_regime(),
        correlation_id="prop-test",
    )
    assert RejectReason.EXTREME_VOLATILITY in sig.reject_reasons


# =============================================================================
# PROPERTY 8: Feature names are stable
# =============================================================================


def test_feature_names_stable_across_instances() -> None:
    """Feature names are identical across different FeatureVector instances."""
    fv1 = _fv(trend=TrendClassification.BULL)
    fv2 = _fv(trend=TrendClassification.BEAR)
    assert fv1.feature_names() == fv2.feature_names()


# =============================================================================
# PROPERTY 9: Direction follows probability
# =============================================================================


@pytest.mark.parametrize(
    "prob_up,expected_dir",
    [
        ("0.80", SignalDirection.LONG),
        ("0.20", SignalDirection.SHORT),
        ("0.50", SignalDirection.NEUTRAL),
    ],
)
def test_direction_follows_probability(prob_up: str, expected_dir: SignalDirection) -> None:
    """Direction is determined by which probability is higher."""
    fv = _fv()
    sig = evaluate_signal(
        fv=fv,
        probability_up=Decimal(prob_up),
        probability_down=Decimal("1") - Decimal(prob_up),
        regime=_regime(),
        correlation_id="prop-test",
    )
    assert sig.direction == expected_dir


# =============================================================================
# PROPERTY 10: Confidence bounded [0, 1]
# =============================================================================


@pytest.mark.parametrize("prob_up", ["0.50", "0.70", "0.80", "0.90", "0.99"])
def test_confidence_bounded(prob_up: str) -> None:
    """Confidence score is always between 0 and 1 inclusive."""
    fv = _fv()
    sig = evaluate_signal(
        fv=fv,
        probability_up=Decimal(prob_up),
        probability_down=Decimal("1") - Decimal(prob_up),
        regime=_regime(),
        correlation_id="prop-test",
    )
    assert Decimal("0") <= sig.confidence <= Decimal("1")

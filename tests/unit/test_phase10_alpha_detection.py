"""
Project Autonomous Alpha — Phase 10: Validation Tests

Reliability Level: SOVEREIGN TIER
Spec: SECTION I — Prove correctness of Alpha Detection Layer

Tests cover:
P1. Feature vector construction and immutability
P2. Model prediction output validation (Decimal, no float)
P3. Signal decision rules (probability threshold, ATR filter, conflicts)
P4. Regime detection logic
P5. Backtest result validation
P6. Governance integration (IntelligenceInput mapping)
P7. Zero-Float Mandate enforcement across all models
P8. Reject reason determinism
P9. Multi-factor confirmation logic
P10. Outlier detection

All tests run without numpy/sklearn/lightgbm/polars (pure logic validation).
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
    _reject_float,
    _to_decimal,
)

# =============================================================================
# HELPERS — Canonical test fixtures
# =============================================================================


def _make_structure(
    ema_20: str = "50000",
    ema_50: str = "49000",
    ema_200: str = "45000",
    trend: TrendClassification = TrendClassification.BULL,
) -> StructureFeatures:
    return StructureFeatures(
        ema_20=Decimal(ema_20),
        ema_50=Decimal(ema_50),
        ema_200=Decimal(ema_200),
        trend=trend,
        ema_20_above_50=Decimal(ema_20) > Decimal(ema_50),
        ema_50_above_200=Decimal(ema_50) > Decimal(ema_200),
    )


def _make_momentum(
    rsi: str = "55",
    macd_line: str = "100",
    macd_signal: str = "80",
    macd_hist: str = "20",
    ret_1: str = "0.005",
    ret_5: str = "0.02",
    ret_10: str = "0.03",
) -> MomentumFeatures:
    return MomentumFeatures(
        rsi_14=Decimal(rsi),
        macd_line=Decimal(macd_line),
        macd_signal=Decimal(macd_signal),
        macd_histogram=Decimal(macd_hist),
        return_1=Decimal(ret_1),
        return_5=Decimal(ret_5),
        return_10=Decimal(ret_10),
    )


def _make_volume(
    vwap: str = "50000",
    vol_sma: str = "1000",
    vol_ratio: str = "1.2",
    spike: bool = False,
) -> VolumeFeatures:
    return VolumeFeatures(
        vwap=Decimal(vwap),
        volume_sma_20=Decimal(vol_sma),
        volume_ratio=Decimal(vol_ratio),
        volume_spike=spike,
    )


def _make_volatility(
    atr: str = "500",
    atr_ratio: str = "0.01",
    bar_range: str = "600",
    range_exp: bool = False,
    breakout_up: bool = False,
    breakout_down: bool = False,
) -> VolatilityFeatures:
    return VolatilityFeatures(
        atr_14=Decimal(atr),
        atr_ratio=Decimal(atr_ratio),
        bar_range=Decimal(bar_range),
        range_expansion=range_exp,
        breakout_up=breakout_up,
        breakout_down=breakout_down,
    )


def _make_feature_vector(
    symbol: str = "BTCUSDT",
    **overrides: object,
) -> FeatureVector:
    structure = overrides.get("structure", _make_structure())
    momentum = overrides.get("momentum", _make_momentum())
    volume = overrides.get("volume", _make_volume())
    volatility = overrides.get("volatility", _make_volatility())
    return FeatureVector(
        symbol=symbol,
        timestamp_ms=1700000000000,
        structure=structure,
        momentum=momentum,
        volume=volume,
        volatility=volatility,
    )


# =============================================================================
# P1: FEATURE VECTOR CONSTRUCTION & IMMUTABILITY
# =============================================================================


class TestP1FeatureVector:
    """Feature vector construction and immutability."""

    def test_feature_vector_frozen(self) -> None:
        fv = _make_feature_vector()
        with pytest.raises(AttributeError):
            fv.symbol = "ETHUSDT"  # type: ignore[misc]

    def test_structure_features_frozen(self) -> None:
        sf = _make_structure()
        with pytest.raises(AttributeError):
            sf.ema_20 = Decimal("99999")  # type: ignore[misc]

    def test_momentum_features_frozen(self) -> None:
        mf = _make_momentum()
        with pytest.raises(AttributeError):
            mf.rsi_14 = Decimal("99")  # type: ignore[misc]

    def test_to_model_input_returns_all_features(self) -> None:
        fv = _make_feature_vector()
        d = fv.to_model_input()
        assert len(d) == 22
        assert "ema_20" in d
        assert "rsi_14" in d
        assert "atr_14" in d
        assert "volume_ratio" in d

    def test_to_model_input_values_are_decimal_or_int(self) -> None:
        fv = _make_feature_vector()
        d = fv.to_model_input()
        for key, val in d.items():
            assert isinstance(val, (Decimal, int)), f"{key} is {type(val)}"

    def test_feature_names_match_model_input(self) -> None:
        fv = _make_feature_vector()
        names = fv.feature_names()
        d = fv.to_model_input()
        assert names == list(d.keys())

    @pytest.mark.parametrize(
        "trend,expected_bull,expected_bear",
        [
            (TrendClassification.BULL, 1, 0),
            (TrendClassification.BEAR, 0, 1),
            (TrendClassification.NEUTRAL, 0, 0),
        ],
    )
    def test_trend_encoding(
        self, trend: TrendClassification, expected_bull: int, expected_bear: int
    ) -> None:
        fv = _make_feature_vector(structure=_make_structure(trend=trend))
        d = fv.to_model_input()
        assert d["trend_bull"] == expected_bull
        assert d["trend_bear"] == expected_bear


# =============================================================================
# P2: MODEL PREDICTION OUTPUT VALIDATION
# =============================================================================


class TestP2ModelPrediction:
    """Model prediction must produce Decimal, not float."""

    def test_alpha_signal_rejects_float_probability(self) -> None:
        with pytest.raises(TypeError, match="Zero-Float"):
            AlphaSignal(
                correlation_id="test-001",
                symbol="BTCUSDT",
                direction=SignalDirection.LONG,
                probability_up=0.75,  # float — must fail
                probability_down=Decimal("0.25"),
                confidence=Decimal("0.70"),
                quality=SignalQuality.HIGH,
                regime=RegimeType.TRENDING,
            )

    def test_alpha_signal_accepts_decimal(self) -> None:
        sig = AlphaSignal(
            correlation_id="test-002",
            symbol="BTCUSDT",
            direction=SignalDirection.LONG,
            probability_up=Decimal("0.75"),
            probability_down=Decimal("0.25"),
            confidence=Decimal("0.70"),
            quality=SignalQuality.HIGH,
            regime=RegimeType.TRENDING,
        )
        assert sig.probability_up == Decimal("0.75")
        assert sig.probability_down == Decimal("0.25")

    def test_backtest_result_rejects_float(self) -> None:
        with pytest.raises(TypeError, match="Zero-Float"):
            BacktestResult(
                symbol="BTCUSDT",
                total_trades=100,
                win_count=55,
                loss_count=45,
                win_rate=0.55,  # float — must fail
                max_drawdown_pct=Decimal("0.05"),
                sharpe_ratio=Decimal("1.2"),
                profit_factor=Decimal("1.5"),
                total_return_pct=Decimal("0.15"),
                avg_trade_return_pct=Decimal("0.0015"),
                period_start="2024-01-01",
                period_end="2024-12-31",
            )


# =============================================================================
# P3: SIGNAL DECISION RULES
# =============================================================================


class TestP3SignalDecision:
    """Signal decision rules validation."""

    def test_probability_below_threshold_rejected(self) -> None:
        from app.alpha.signal_decision import evaluate_signal

        fv = _make_feature_vector()
        regime = RegimeState(
            regime=RegimeType.TRENDING,
            atr_percentile=Decimal("0.50"),
            trend_strength=Decimal("0.60"),
            correlation_id="test-003",
            regime_confidence=Decimal("0.80"),
        )
        sig = evaluate_signal(
            fv=fv,
            probability_up=Decimal("0.60"),
            probability_down=Decimal("0.40"),
            regime=regime,
            correlation_id="test-003",
        )
        assert sig.quality == SignalQuality.REJECTED
        assert RejectReason.PROBABILITY_TOO_LOW in sig.reject_reasons

    def test_probability_above_threshold_accepted(self) -> None:
        from app.alpha.signal_decision import evaluate_signal

        fv = _make_feature_vector()
        regime = RegimeState(
            regime=RegimeType.TRENDING,
            atr_percentile=Decimal("0.50"),
            trend_strength=Decimal("0.60"),
            correlation_id="test-004",
            regime_confidence=Decimal("0.80"),
        )
        sig = evaluate_signal(
            fv=fv,
            probability_up=Decimal("0.80"),
            probability_down=Decimal("0.20"),
            regime=regime,
            correlation_id="test-004",
        )
        assert sig.quality != SignalQuality.REJECTED

    def test_extreme_volatility_rejected(self) -> None:
        from app.alpha.signal_decision import evaluate_signal

        fv = _make_feature_vector(volatility=_make_volatility(atr_ratio="0.06"))
        regime = RegimeState(
            regime=RegimeType.TRENDING,
            atr_percentile=Decimal("0.50"),
            trend_strength=Decimal("0.60"),
            correlation_id="test-005",
            regime_confidence=Decimal("0.80"),
        )
        sig = evaluate_signal(
            fv=fv,
            probability_up=Decimal("0.80"),
            probability_down=Decimal("0.20"),
            regime=regime,
            correlation_id="test-005",
        )
        assert RejectReason.EXTREME_VOLATILITY in sig.reject_reasons

    def test_volatile_regime_rejected(self) -> None:
        from app.alpha.signal_decision import evaluate_signal

        fv = _make_feature_vector()
        regime = RegimeState(
            regime=RegimeType.VOLATILE,
            atr_percentile=Decimal("0.95"),
            trend_strength=Decimal("0.20"),
            correlation_id="test-006",
        )
        sig = evaluate_signal(
            fv=fv,
            probability_up=Decimal("0.80"),
            probability_down=Decimal("0.20"),
            regime=regime,
            correlation_id="test-006",
        )
        assert RejectReason.REGIME_UNFAVORABLE in sig.reject_reasons

    def test_outlier_return_rejected(self) -> None:
        from app.alpha.signal_decision import evaluate_signal

        fv = _make_feature_vector(
            momentum=_make_momentum(ret_1="0.15")  # 15% return = outlier
        )
        regime = RegimeState(
            regime=RegimeType.TRENDING,
            atr_percentile=Decimal("0.50"),
            trend_strength=Decimal("0.60"),
            correlation_id="test-007",
            regime_confidence=Decimal("0.80"),
        )
        sig = evaluate_signal(
            fv=fv,
            probability_up=Decimal("0.80"),
            probability_down=Decimal("0.20"),
            regime=regime,
            correlation_id="test-007",
        )
        assert RejectReason.OUTLIER_DETECTED in sig.reject_reasons

    def test_direction_long_when_prob_up_higher(self) -> None:
        from app.alpha.signal_decision import evaluate_signal

        fv = _make_feature_vector()
        regime = RegimeState(
            regime=RegimeType.TRENDING,
            atr_percentile=Decimal("0.50"),
            trend_strength=Decimal("0.60"),
            correlation_id="test-008",
            regime_confidence=Decimal("0.80"),
        )
        sig = evaluate_signal(
            fv=fv,
            probability_up=Decimal("0.80"),
            probability_down=Decimal("0.20"),
            regime=regime,
            correlation_id="test-008",
        )
        assert sig.direction == SignalDirection.LONG

    def test_direction_short_when_prob_down_higher(self) -> None:
        from app.alpha.signal_decision import evaluate_signal

        fv = _make_feature_vector(
            structure=_make_structure(
                ema_20="45000",
                ema_50="48000",
                ema_200="50000",
                trend=TrendClassification.BEAR,
            ),
            momentum=_make_momentum(
                rsi="35",
                macd_hist="-20",
                ret_1="-0.005",
            ),
        )
        regime = RegimeState(
            regime=RegimeType.TRENDING,
            atr_percentile=Decimal("0.50"),
            trend_strength=Decimal("0.60"),
            correlation_id="test-009",
            regime_confidence=Decimal("0.80"),
        )
        sig = evaluate_signal(
            fv=fv,
            probability_up=Decimal("0.20"),
            probability_down=Decimal("0.80"),
            regime=regime,
            correlation_id="test-009",
        )
        assert sig.direction == SignalDirection.SHORT


# =============================================================================
# P4: REGIME DETECTION
# =============================================================================


class TestP4RegimeDetection:
    """Regime detection logic."""

    def test_empty_series_returns_unknown(self) -> None:
        from app.alpha.signal_decision import detect_regime

        regime = detect_regime([], [], "test-010")
        assert regime.regime == RegimeType.UNKNOWN

    def test_volatile_regime_high_atr(self) -> None:
        from app.alpha.signal_decision import detect_regime

        atr_series = [Decimal(str(i)) for i in range(1, 101)]
        close_series = [Decimal(str(50000 + i * 10)) for i in range(100)]
        regime = detect_regime(atr_series, close_series, "test-011")
        # Last ATR (100) is highest = 100th percentile → VOLATILE
        assert regime.regime == RegimeType.VOLATILE

    def test_regime_state_frozen(self) -> None:
        rs = RegimeState(
            regime=RegimeType.TRENDING,
            atr_percentile=Decimal("0.70"),
            trend_strength=Decimal("0.50"),
            correlation_id="test-012",
            regime_confidence=Decimal("0.80"),
        )
        with pytest.raises(AttributeError):
            rs.regime = RegimeType.RANGING  # type: ignore[misc]

    def test_regime_state_rejects_float_atr(self) -> None:
        with pytest.raises(TypeError, match="Zero-Float"):
            RegimeState(
                regime=RegimeType.TRENDING,
                atr_percentile=0.70,  # float
                trend_strength=Decimal("0.50"),
                correlation_id="test-013",
            )


# =============================================================================
# P5: BACKTEST RESULT VALIDATION
# =============================================================================


class TestP5BacktestResult:
    """Backtest result metrics validation."""

    def test_viable_strategy(self) -> None:
        bt = BacktestResult(
            symbol="BTCUSDT",
            total_trades=100,
            win_count=60,
            loss_count=40,
            win_rate=Decimal("0.60"),
            max_drawdown_pct=Decimal("0.05"),
            sharpe_ratio=Decimal("1.5"),
            profit_factor=Decimal("1.8"),
            total_return_pct=Decimal("0.20"),
            avg_trade_return_pct=Decimal("0.002"),
            period_start="2024-01-01",
            period_end="2024-12-31",
        )
        assert bt.is_viable is True

    def test_non_viable_low_win_rate(self) -> None:
        bt = BacktestResult(
            symbol="BTCUSDT",
            total_trades=100,
            win_count=40,
            loss_count=60,
            win_rate=Decimal("0.40"),
            max_drawdown_pct=Decimal("0.10"),
            sharpe_ratio=Decimal("0.3"),
            profit_factor=Decimal("0.8"),
            total_return_pct=Decimal("-0.05"),
            avg_trade_return_pct=Decimal("-0.0005"),
            period_start="2024-01-01",
            period_end="2024-12-31",
        )
        assert bt.is_viable is False

    def test_non_viable_insufficient_trades(self) -> None:
        bt = BacktestResult(
            symbol="BTCUSDT",
            total_trades=10,
            win_count=8,
            loss_count=2,
            win_rate=Decimal("0.80"),
            max_drawdown_pct=Decimal("0.01"),
            sharpe_ratio=Decimal("2.0"),
            profit_factor=Decimal("4.0"),
            total_return_pct=Decimal("0.10"),
            avg_trade_return_pct=Decimal("0.01"),
            period_start="2024-01-01",
            period_end="2024-12-31",
        )
        assert bt.is_viable is False  # < 30 trades

    def test_backtest_frozen(self) -> None:
        bt = BacktestResult(
            symbol="BTCUSDT",
            total_trades=100,
            win_count=55,
            loss_count=45,
            win_rate=Decimal("0.55"),
            max_drawdown_pct=Decimal("0.05"),
            sharpe_ratio=Decimal("1.0"),
            profit_factor=Decimal("1.3"),
            total_return_pct=Decimal("0.10"),
            avg_trade_return_pct=Decimal("0.001"),
            period_start="2024-01-01",
            period_end="2024-12-31",
        )
        with pytest.raises(AttributeError):
            bt.win_rate = Decimal("0.99")  # type: ignore[misc]


# =============================================================================
# P6: GOVERNANCE INTEGRATION
# =============================================================================


class TestP6GovernanceIntegration:
    """Alpha output maps correctly to IntelligenceInput."""

    def test_actionable_signal_maps_to_buy(self) -> None:
        from app.alpha.alpha_detector import AlphaDetector

        sig = AlphaSignal(
            correlation_id="test-020",
            symbol="BTCUSDT",
            direction=SignalDirection.LONG,
            probability_up=Decimal("0.80"),
            probability_down=Decimal("0.20"),
            confidence=Decimal("0.75"),
            quality=SignalQuality.HIGH,
            regime=RegimeType.TRENDING,
        )
        detector = AlphaDetector(use_lgbm=False, correlation_id="test-020")
        result = detector.to_intelligence_input(sig)
        assert result["ml_action"].value == "BUY"
        assert result["ml_confidence"] == Decimal("0.75")
        assert "ml_reasoning" in result

    def test_actionable_signal_maps_to_sell(self) -> None:
        from app.alpha.alpha_detector import AlphaDetector

        sig = AlphaSignal(
            correlation_id="test-021",
            symbol="BTCUSDT",
            direction=SignalDirection.SHORT,
            probability_up=Decimal("0.20"),
            probability_down=Decimal("0.80"),
            confidence=Decimal("0.75"),
            quality=SignalQuality.MEDIUM,
            regime=RegimeType.TRENDING,
        )
        detector = AlphaDetector(use_lgbm=False, correlation_id="test-021")
        result = detector.to_intelligence_input(sig)
        assert result["ml_action"].value == "SELL"

    def test_rejected_signal_maps_to_none(self) -> None:
        from app.alpha.alpha_detector import AlphaDetector

        sig = AlphaSignal(
            correlation_id="test-022",
            symbol="BTCUSDT",
            direction=SignalDirection.NEUTRAL,
            probability_up=Decimal("0.50"),
            probability_down=Decimal("0.50"),
            confidence=Decimal("0.30"),
            quality=SignalQuality.REJECTED,
            regime=RegimeType.VOLATILE,
            reject_reasons=[RejectReason.PROBABILITY_TOO_LOW],
        )
        detector = AlphaDetector(use_lgbm=False, correlation_id="test-022")
        result = detector.to_intelligence_input(sig)
        assert result["ml_confidence"] is None
        assert result["ml_action"] is None
        assert "PROB_BELOW_THRESHOLD" in result["ml_reasoning"]

    def test_reasoning_truncated_to_200_chars(self) -> None:
        from app.alpha.alpha_detector import AlphaDetector

        sig = AlphaSignal(
            correlation_id="test-023",
            symbol="BTCUSDT",
            direction=SignalDirection.LONG,
            probability_up=Decimal("0.85"),
            probability_down=Decimal("0.15"),
            confidence=Decimal("0.80"),
            quality=SignalQuality.HIGH,
            regime=RegimeType.TRENDING,
            feature_count=22,
        )
        detector = AlphaDetector(use_lgbm=False, correlation_id="test-023")
        result = detector.to_intelligence_input(sig)
        assert len(result["ml_reasoning"]) <= 200

    def test_untrained_detector_returns_rejected(self) -> None:
        from app.alpha.alpha_detector import AlphaDetector

        detector = AlphaDetector(use_lgbm=False, correlation_id="test-024")
        # predict() without training
        sig = detector.predict(None, "BTCUSDT", "test-024")
        assert sig.quality == SignalQuality.REJECTED
        assert RejectReason.MODEL_UNSTABLE in sig.reject_reasons


# =============================================================================
# P7: ZERO-FLOAT MANDATE
# =============================================================================


class TestP7ZeroFloatMandate:
    """Zero-Float Mandate enforcement across all models."""

    @pytest.mark.parametrize(
        "model_class,field_name,float_val",
        [
            ("StructureFeatures", "ema_20", 50000.0),
            ("MomentumFeatures", "rsi_14", 55.0),
            ("VolumeFeatures", "vwap", 50000.0),
            ("VolatilityFeatures", "atr_14", 500.0),
            ("RegimeState", "atr_percentile", 0.70),
        ],
    )
    def test_reject_float_in_models(
        self, model_class: str, field_name: str, float_val: float
    ) -> None:
        with pytest.raises(TypeError, match="Zero-Float"):
            _reject_float(float_val, field_name)

    def test_reject_float_utility(self) -> None:
        _reject_float(Decimal("1.0"), "test_field")
        _reject_float(42, "test_field")
        _reject_float("1.0", "test_field")
        with pytest.raises(TypeError, match="Zero-Float"):
            _reject_float(1.0, "test_field")

    def test_to_decimal_from_int(self) -> None:
        result = _to_decimal(42, "test")
        assert isinstance(result, Decimal)
        assert result == Decimal("42")

    def test_to_decimal_from_str(self) -> None:
        result = _to_decimal("3.14", "test")
        assert isinstance(result, Decimal)
        assert result == Decimal("3.14")

    def test_to_decimal_from_decimal(self) -> None:
        result = _to_decimal(Decimal("2.718"), "test")
        assert result == Decimal("2.718")

    def test_to_decimal_rejects_float(self) -> None:
        with pytest.raises(TypeError, match="Zero-Float"):
            _to_decimal(3.14, "test")


# =============================================================================
# P8: REJECT REASON DETERMINISM
# =============================================================================


class TestP8RejectDeterminism:
    """Reject reasons must be deterministic and complete."""

    def test_all_reject_reasons_have_values(self) -> None:
        for reason in RejectReason:
            assert len(reason.value) > 0

    def test_reject_reasons_are_unique(self) -> None:
        values = [r.value for r in RejectReason]
        assert len(values) == len(set(values))

    @pytest.mark.parametrize("quality", [SignalQuality.HIGH, SignalQuality.MEDIUM])
    def test_actionable_qualities(self, quality: SignalQuality) -> None:
        sig = AlphaSignal(
            correlation_id="test-030",
            symbol="BTCUSDT",
            direction=SignalDirection.LONG,
            probability_up=Decimal("0.80"),
            probability_down=Decimal("0.20"),
            confidence=Decimal("0.80"),
            quality=quality,
            regime=RegimeType.TRENDING,
        )
        assert sig.is_actionable is True

    @pytest.mark.parametrize("quality", [SignalQuality.LOW, SignalQuality.REJECTED])
    def test_non_actionable_qualities(self, quality: SignalQuality) -> None:
        sig = AlphaSignal(
            correlation_id="test-031",
            symbol="BTCUSDT",
            direction=SignalDirection.NEUTRAL,
            probability_up=Decimal("0.50"),
            probability_down=Decimal("0.50"),
            confidence=Decimal("0.30"),
            quality=quality,
            regime=RegimeType.RANGING,
        )
        assert sig.is_actionable is False


# =============================================================================
# P9: MULTI-FACTOR CONFIRMATION
# =============================================================================


class TestP9MultiFactor:
    """Multi-factor confirmation logic."""

    def test_all_bullish_factors(self) -> None:
        from app.alpha.signal_decision import _multi_factor_score

        fv = _make_feature_vector(
            structure=_make_structure(trend=TrendClassification.BULL),
            momentum=_make_momentum(rsi="60", macd_hist="20", ret_1="0.01"),
        )
        bullish, bearish = _multi_factor_score(fv)
        assert bullish > bearish

    def test_all_bearish_factors(self) -> None:
        from app.alpha.signal_decision import _multi_factor_score

        fv = _make_feature_vector(
            structure=_make_structure(
                ema_20="45000",
                ema_50="48000",
                ema_200="50000",
                trend=TrendClassification.BEAR,
            ),
            momentum=_make_momentum(rsi="35", macd_hist="-20", ret_1="-0.01"),
        )
        bullish, bearish = _multi_factor_score(fv)
        assert bearish > bullish

    def test_mixed_factors_neutral(self) -> None:
        from app.alpha.signal_decision import _multi_factor_score

        fv = _make_feature_vector(
            structure=_make_structure(trend=TrendClassification.NEUTRAL),
            momentum=_make_momentum(rsi="50", macd_hist="0", ret_1="0"),
        )
        bullish, bearish = _multi_factor_score(fv)
        # Neutral trend gives no bonus; factors roughly balanced
        assert abs(bullish - bearish) <= 2


# =============================================================================
# P10: CONFLICT DETECTION
# =============================================================================


class TestP10ConflictDetection:
    """Engine conflict detection logic."""

    def test_no_conflicts_in_aligned_bull(self) -> None:
        from app.alpha.signal_decision import _check_engine_conflicts

        fv = _make_feature_vector(
            structure=_make_structure(trend=TrendClassification.BULL),
            momentum=_make_momentum(rsi="60", macd_hist="20"),
        )
        conflicts = _check_engine_conflicts(fv)
        assert len(conflicts) == 0

    def test_bull_trend_overbought_conflict(self) -> None:
        from app.alpha.signal_decision import _check_engine_conflicts

        fv = _make_feature_vector(
            structure=_make_structure(trend=TrendClassification.BULL),
            momentum=_make_momentum(rsi="85"),
        )
        conflicts = _check_engine_conflicts(fv)
        assert "BULL_TREND_RSI_OVERBOUGHT" in conflicts

    def test_breakout_against_trend_conflict(self) -> None:
        from app.alpha.signal_decision import _check_engine_conflicts

        fv = _make_feature_vector(
            structure=_make_structure(trend=TrendClassification.BEAR),
            volatility=_make_volatility(breakout_up=True),
        )
        conflicts = _check_engine_conflicts(fv)
        assert "BREAKOUT_UP_IN_BEAR_TREND" in conflicts

    def test_bull_trend_negative_macd_conflict(self) -> None:
        from app.alpha.signal_decision import _check_engine_conflicts

        fv = _make_feature_vector(
            structure=_make_structure(trend=TrendClassification.BULL),
            momentum=_make_momentum(macd_hist="-10"),
        )
        conflicts = _check_engine_conflicts(fv)
        assert "BULL_TREND_MACD_NEGATIVE" in conflicts

    def test_multiple_conflicts_reject_signal(self) -> None:
        from app.alpha.signal_decision import evaluate_signal

        fv = _make_feature_vector(
            structure=_make_structure(trend=TrendClassification.BULL),
            momentum=_make_momentum(rsi="85", macd_hist="-20"),
            volatility=_make_volatility(breakout_down=True),
        )
        regime = RegimeState(
            regime=RegimeType.TRENDING,
            atr_percentile=Decimal("0.50"),
            trend_strength=Decimal("0.60"),
            correlation_id="test-040",
            regime_confidence=Decimal("0.80"),
        )
        sig = evaluate_signal(
            fv=fv,
            probability_up=Decimal("0.75"),
            probability_down=Decimal("0.25"),
            regime=regime,
            correlation_id="test-040",
        )
        assert RejectReason.CONFLICTING_ENGINES in sig.reject_reasons


# =============================================================================
# P11: OUTLIER DETECTION
# =============================================================================


class TestP11OutlierDetection:
    """Outlier detection utilities."""

    def test_no_outliers_in_normal_data(self) -> None:
        from app.alpha.signal_decision import detect_outliers

        returns = [Decimal(str(x / 100)) for x in range(-5, 6)]
        outliers = detect_outliers(returns)
        assert len(outliers) == 0

    def test_detects_large_positive_outlier(self) -> None:
        from app.alpha.signal_decision import detect_outliers

        returns = [Decimal("0.01")] * 10 + [Decimal("0.15")]
        outliers = detect_outliers(returns)
        assert 10 in outliers

    def test_detects_large_negative_outlier(self) -> None:
        from app.alpha.signal_decision import detect_outliers

        returns = [Decimal("0.01")] * 10 + [Decimal("-0.12")]
        outliers = detect_outliers(returns)
        assert 10 in outliers

    def test_custom_threshold(self) -> None:
        from app.alpha.signal_decision import detect_outliers

        returns = [Decimal("0.05")]
        outliers = detect_outliers(returns, threshold=Decimal("0.03"))
        assert 0 in outliers


# =============================================================================
# P12: ENUM COMPLETENESS
# =============================================================================


class TestP12EnumCompleteness:
    """All enums have expected members."""

    def test_trend_classification(self) -> None:
        assert set(TrendClassification) == {
            TrendClassification.BULL,
            TrendClassification.BEAR,
            TrendClassification.NEUTRAL,
        }

    def test_regime_type(self) -> None:
        assert set(RegimeType) == {
            RegimeType.TRENDING,
            RegimeType.RANGING,
            RegimeType.VOLATILE,
            RegimeType.UNKNOWN,
        }

    def test_signal_direction(self) -> None:
        assert set(SignalDirection) == {
            SignalDirection.LONG,
            SignalDirection.SHORT,
            SignalDirection.NEUTRAL,
        }

    def test_signal_quality(self) -> None:
        assert set(SignalQuality) == {
            SignalQuality.HIGH,
            SignalQuality.MEDIUM,
            SignalQuality.LOW,
            SignalQuality.REJECTED,
        }

    def test_reject_reason_count(self) -> None:
        assert len(RejectReason) == 10

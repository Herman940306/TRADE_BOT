"""
Project Autonomous Alpha — Phase 10: Alpha Detector (Orchestrator)

Reliability Level: SOVEREIGN TIER
Spec: SECTIONS H, I — Integration + Validation

PIPELINE: DATA → FEATURES → MODEL → PROBABILITY → DECISION

This orchestrator:
1. Fetches OHLCV data (or accepts pre-loaded)
2. Computes all 4 engine features
3. Builds feature matrix for model training/prediction
4. Applies signal decision rules + prediction hardening
5. Produces AlphaSignal compatible with DecisionPacketBuilder

GOVERNANCE: Alpha layer NEVER bypasses governance.
Output feeds into IntelligenceInput (ml_confidence, ml_action, ml_reasoning).
"""

from __future__ import annotations

import logging
import time
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Any, Dict, List, Optional

from app.alpha.engines import (
    compute_momentum,
    compute_structure,
    compute_volatility,
    compute_volume,
)
from app.alpha.model_layer import (
    FEATURE_NAMES,
    LightGBMModel,
    LogisticRegressionModel,
    ModelPrediction,
    build_feature_matrix,
    generate_labels,
)
from app.alpha.models import (
    AlphaSignal,
    FeatureVector,
    RegimeType,
    RejectReason,
    SignalDirection,
    SignalQuality,
)
from app.alpha.signal_decision import (
    detect_regime,
    evaluate_signal,
)

logger = logging.getLogger(__name__)

# ── Optional dependencies ────────────────────────────────────────────────────
try:
    import polars as pl

    POLARS_AVAILABLE = True
except ImportError:
    pl = None  # type: ignore[assignment]
    POLARS_AVAILABLE = False

try:
    import numpy as np

    NUMPY_AVAILABLE = True
except ImportError:
    np = None  # type: ignore[assignment]
    NUMPY_AVAILABLE = False


def _to_dec(value: object) -> Decimal:
    """Convert to Decimal at output boundary."""
    if value is None:
        return Decimal("0")
    return Decimal(str(value)).quantize(Decimal("0.00000001"), rounding=ROUND_HALF_EVEN)


# =============================================================================
# FEATURE EXTRACTION (VECTORIZED)
# =============================================================================


def extract_features(
    df: Any,
    symbol: str,
    correlation_id: str,
) -> Optional[FeatureVector]:
    """
    Extract all features from OHLCV DataFrame using 4 engines.

    Returns None if critical errors occur (fail-safe).
    """
    if not POLARS_AVAILABLE or df is None:
        logger.error(
            "SEC-ALPHA-040 Cannot extract features: polars=%s, df=%s. correlation_id=%s",
            POLARS_AVAILABLE,
            df is not None,
            correlation_id,
        )
        return None

    try:
        structure = compute_structure(df, correlation_id)
        momentum = compute_momentum(df, correlation_id)
        volume = compute_volume(df, correlation_id)
        volatility = compute_volatility(df, correlation_id)

        last_ts = df["timestamp"][-1] if "timestamp" in df.columns else 0

        return FeatureVector(
            symbol=symbol,
            timestamp_ms=int(last_ts) if last_ts is not None else 0,
            structure=structure,
            momentum=momentum,
            volume=volume,
            volatility=volatility,
        )
    except Exception as exc:
        logger.error(
            "SEC-ALPHA-041 Feature extraction failed: %s. correlation_id=%s",
            exc,
            correlation_id,
        )
        return None


def extract_feature_series(
    df: Any,
    symbol: str,
    correlation_id: str,
    min_window: int = 200,
) -> List[FeatureVector]:
    """
    Extract features for each timestep using a rolling window.
    Used for building training data.

    Returns list of FeatureVector instances.
    """
    if not POLARS_AVAILABLE or df is None:
        return []

    n = len(df)
    if n < min_window:
        logger.warning(
            "Insufficient data for feature series: %d < %d. correlation_id=%s",
            n,
            min_window,
            correlation_id,
        )
        return []

    features: List[FeatureVector] = []

    for end_idx in range(min_window, n):
        window_df = df[end_idx - min_window : end_idx + 1]
        fv = extract_features(window_df, symbol, correlation_id)
        if fv is not None:
            features.append(fv)

    return features


# =============================================================================
# ALPHA DETECTOR — MAIN ORCHESTRATOR
# =============================================================================


class AlphaDetector:
    """
    Production-grade Alpha Detection Layer.

    Pipeline: DATA → FEATURES → MODEL → PROBABILITY → DECISION

    The detector does NOT execute trades.
    Output feeds into DecisionPacketBuilder via IntelligenceInput.
    """

    def __init__(
        self,
        use_lgbm: bool = True,
        correlation_id: str = "",
    ) -> None:
        self._correlation_id = correlation_id
        self._use_lgbm = use_lgbm

        # Initialize models
        self._lr_model: Optional[LogisticRegressionModel] = None
        self._lgbm_model: Optional[LightGBMModel] = None
        self._is_trained = False
        self._training_metrics: Dict[str, Decimal] = {}
        self._model_version = ""

        try:
            self._lr_model = LogisticRegressionModel()
        except RuntimeError:
            logger.warning("LogisticRegression unavailable — sklearn not installed")

        if use_lgbm:
            try:
                self._lgbm_model = LightGBMModel()
            except RuntimeError:
                logger.warning("LightGBM unavailable — lightgbm not installed")

    @property
    def is_trained(self) -> bool:
        return self._is_trained

    @property
    def training_metrics(self) -> Dict[str, Decimal]:
        return dict(self._training_metrics)

    def train(
        self,
        df: Any,
        symbol: str,
        correlation_id: str,
    ) -> Dict[str, Decimal]:
        """
        Train model(s) on historical OHLCV data.

        1. Extract feature series
        2. Generate binary labels (next-period direction)
        3. Build feature matrix
        4. Train LR baseline and LGBM primary

        Returns training metrics dict.
        """
        if not POLARS_AVAILABLE or not NUMPY_AVAILABLE:
            raise RuntimeError(
                f"SEC-ALPHA-042 Dependencies unavailable: "
                f"polars={POLARS_AVAILABLE}, numpy={NUMPY_AVAILABLE}. "
                f"correlation_id={correlation_id}"
            )

        start = time.monotonic_ns()

        # 1. Extract feature series
        features = extract_feature_series(df, symbol, correlation_id)
        if len(features) < 50:
            raise ValueError(
                f"SEC-ALPHA-043 Insufficient features: {len(features)}. "
                f"correlation_id={correlation_id}"
            )

        # 2. Build feature matrix
        feature_dicts = [fv.to_model_input() for fv in features]
        X = build_feature_matrix(feature_dicts, correlation_id)

        # 3. Generate labels from corresponding close prices
        # We need the close prices aligned with the feature vectors
        n_total = len(df)
        min_window = 200
        close_for_labels = df["close"][min_window:n_total].to_list()
        labels = generate_labels(close_for_labels)

        # Trim to match
        min_len = min(len(X), len(labels))
        X = X[:min_len]
        labels = labels[:min_len]

        metrics: Dict[str, Decimal] = {"feature_count": _to_dec(len(features))}

        # 4. Train models
        if self._lr_model is not None:
            lr_metrics = self._lr_model.train(X, labels, correlation_id)
            metrics["lr_accuracy"] = lr_metrics["train_accuracy"]

        if self._lgbm_model is not None:
            lgbm_metrics = self._lgbm_model.train(X, labels, correlation_id)
            metrics["lgbm_accuracy"] = lgbm_metrics["train_accuracy"]
            self._model_version = self._lgbm_model._version
        elif self._lr_model is not None:
            self._model_version = self._lr_model._version

        elapsed_ms = (time.monotonic_ns() - start) // 1_000_000
        metrics["training_time_ms"] = _to_dec(elapsed_ms)

        self._is_trained = True
        self._training_metrics = metrics

        logger.info(
            "Alpha model trained: %s features, LR=%s, LGBM=%s. correlation_id=%s",
            len(features),
            metrics.get("lr_accuracy", "N/A"),
            metrics.get("lgbm_accuracy", "N/A"),
            correlation_id,
        )

        return metrics

    def predict(
        self,
        df: Any,
        symbol: str,
        correlation_id: str,
    ) -> AlphaSignal:
        """
        Generate alpha signal from current OHLCV data.

        1. Extract latest features
        2. Run model prediction
        3. Detect regime
        4. Apply signal decision rules
        5. Return AlphaSignal

        Returns AlphaSignal (may have quality=REJECTED).
        """
        start = time.monotonic_ns()

        if not self._is_trained:
            return AlphaSignal(
                correlation_id=correlation_id,
                symbol=symbol,
                direction=SignalDirection.NEUTRAL,
                probability_up=Decimal("0.50"),
                probability_down=Decimal("0.50"),
                confidence=Decimal("0"),
                quality=SignalQuality.REJECTED,
                regime=RegimeType.UNKNOWN,
                reject_reasons=[RejectReason.MODEL_UNSTABLE],
                model_version="UNTRAINED",
            )

        # Design Challenge R3: staleness check
        if POLARS_AVAILABLE and df is not None and "timestamp" in df.columns:
            latest_ts = int(df["timestamp"][-1])
            now_ms = int(time.time() * 1000)
            age_ms = now_ms - latest_ts
            # Reject if data > 2 hours old (for 1h candles)
            max_age_ms = 2 * 60 * 60 * 1000
            if age_ms > max_age_ms:
                logger.warning(
                    "SEC-ALPHA-044 Stale data: age=%dms > max=%dms. correlation_id=%s",
                    age_ms,
                    max_age_ms,
                    correlation_id,
                )
                return AlphaSignal(
                    correlation_id=correlation_id,
                    symbol=symbol,
                    direction=SignalDirection.NEUTRAL,
                    probability_up=Decimal("0.50"),
                    probability_down=Decimal("0.50"),
                    confidence=Decimal("0"),
                    quality=SignalQuality.REJECTED,
                    regime=RegimeType.UNKNOWN,
                    reject_reasons=[RejectReason.MODEL_UNSTABLE],
                    model_version=self._model_version,
                )

        # 1. Extract latest features
        fv = extract_features(df, symbol, correlation_id)
        if fv is None:
            return AlphaSignal(
                correlation_id=correlation_id,
                symbol=symbol,
                direction=SignalDirection.NEUTRAL,
                probability_up=Decimal("0.50"),
                probability_down=Decimal("0.50"),
                confidence=Decimal("0"),
                quality=SignalQuality.REJECTED,
                regime=RegimeType.UNKNOWN,
                reject_reasons=[RejectReason.MISSING_FEATURES],
                model_version=self._model_version,
            )

        # 2. Run prediction (prefer LGBM if available)
        feature_dict = fv.to_model_input()
        feature_values = [
            float(feature_dict[name])
            if isinstance(feature_dict[name], Decimal)
            else float(feature_dict[name])
            for name in FEATURE_NAMES
        ]
        X = np.array(feature_values, dtype=np.float64)

        prediction: Optional[ModelPrediction] = None
        if self._lgbm_model is not None and self._lgbm_model.is_trained:
            prediction = self._lgbm_model.predict(X, correlation_id)
        elif self._lr_model is not None and self._lr_model.is_trained:
            prediction = self._lr_model.predict(X, correlation_id)

        if prediction is None:
            return AlphaSignal(
                correlation_id=correlation_id,
                symbol=symbol,
                direction=SignalDirection.NEUTRAL,
                probability_up=Decimal("0.50"),
                probability_down=Decimal("0.50"),
                confidence=Decimal("0"),
                quality=SignalQuality.REJECTED,
                regime=RegimeType.UNKNOWN,
                reject_reasons=[RejectReason.MODEL_UNSTABLE],
                model_version=self._model_version,
            )

        # 3. Detect regime — use full historical series, NOT single point
        # Single-point regime detection is useless (Design Challenge R1 fix)
        atr_series: list[Decimal] = []
        close_series: list[Decimal] = []
        if POLARS_AVAILABLE and df is not None and len(df) >= 14:
            close_col = df["close"].to_list()
            close_series = [_to_dec(c) for c in close_col[-50:]]
            # Approximate ATR from close differences when no full ATR column
            atr_series = [fv.volatility.atr_14]  # At minimum, current ATR
            if "atr" in df.columns:
                atr_col = df["atr"].to_list()
                atr_series = [_to_dec(a) for a in atr_col[-50:]]
        else:
            atr_series = [fv.volatility.atr_14]
            close_series = [fv.structure.ema_20]
        regime = detect_regime(
            atr_series,
            close_series,
            correlation_id,
        )

        # 4. Apply signal decision rules
        signal = evaluate_signal(
            fv=fv,
            probability_up=prediction.probability_up,
            probability_down=prediction.probability_down,
            regime=regime,
            correlation_id=correlation_id,
        )

        elapsed_ms = (time.monotonic_ns() - start) // 1_000_000

        return AlphaSignal(
            correlation_id=signal.correlation_id,
            symbol=signal.symbol,
            direction=signal.direction,
            probability_up=signal.probability_up,
            probability_down=signal.probability_down,
            confidence=signal.confidence,
            quality=signal.quality,
            regime=signal.regime,
            reject_reasons=list(signal.reject_reasons),
            feature_count=signal.feature_count,
            latency_ms=int(elapsed_ms),
            model_version=self._model_version,
        )

    def to_intelligence_input(
        self,
        signal: AlphaSignal,
    ) -> Dict[str, object]:
        """
        Convert AlphaSignal to IntelligenceInput-compatible dict.

        Maps to:
        - ml_confidence → signal.confidence
        - ml_action → BUY/SELL/HOLD based on direction
        - ml_reasoning → human-readable summary
        """
        from app.logic.decision_packet_models import MissingReason, MLAction

        if not signal.is_actionable:
            return {
                "ml_confidence": None,
                "ml_action": None,
                "ml_reasoning": f"Alpha rejected: {', '.join(r.value for r in signal.reject_reasons)}",
                "ml_confidence_missing_reason": MissingReason.CALCULATION_ERROR,
                "ml_action_missing_reason": MissingReason.CALCULATION_ERROR,
            }

        # Map direction to MLAction
        if signal.direction == SignalDirection.LONG:
            action = MLAction.BUY
        elif signal.direction == SignalDirection.SHORT:
            action = MLAction.SELL
        else:
            action = MLAction.HOLD

        reasoning = (
            f"Alpha {signal.quality.value}: "
            f"P(up)={signal.probability_up}, P(down)={signal.probability_down}, "
            f"regime={signal.regime.value}, "
            f"features={signal.feature_count}"
        )
        # Truncate to max 200 chars per IntelligenceInput constraint
        if len(reasoning) > 200:
            reasoning = reasoning[:197] + "..."

        return {
            "ml_confidence": signal.confidence,
            "ml_action": action,
            "ml_reasoning": reasoning,
        }

"""
Project Autonomous Alpha — Phase 10: Model Layer

Reliability Level: SOVEREIGN TIER
Spec: SECTION C — Model Layer (LR baseline + LightGBM primary)

OUTPUT: probability_up, probability_down
NO price prediction. Probability only.
NO LSTM or deep learning.

Models:
1. Logistic Regression (baseline) — sklearn
2. LightGBM (primary) — lightgbm

Both produce calibrated probabilities via predict_proba.
"""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass, field
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Optional ML dependencies ────────────────────────────────────────────────
try:
    import numpy as np

    NUMPY_AVAILABLE = True
except ImportError:
    np = None  # type: ignore[assignment]
    NUMPY_AVAILABLE = False

try:
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler

    SKLEARN_AVAILABLE = True
except ImportError:
    LogisticRegression = None  # type: ignore[assignment, misc]
    StandardScaler = None  # type: ignore[assignment, misc]
    SKLEARN_AVAILABLE = False

try:
    import lightgbm as lgb

    LGBM_AVAILABLE = True
except ImportError:
    lgb = None  # type: ignore[assignment]
    LGBM_AVAILABLE = False


# =============================================================================
# CONSTANTS
# =============================================================================

FEATURE_NAMES = [
    "ema_20",
    "ema_50",
    "ema_200",
    "ema_20_above_50",
    "ema_50_above_200",
    "trend_bull",
    "trend_bear",
    "rsi_14",
    "macd_line",
    "macd_signal",
    "macd_histogram",
    "return_1",
    "return_5",
    "return_10",
    "vwap",
    "volume_ratio",
    "volume_spike",
    "atr_14",
    "atr_ratio",
    "range_expansion",
    "breakout_up",
    "breakout_down",
]

# Label generation: 1 if next-period return > 0, else 0
LABEL_HORIZON = 1  # 1-period ahead prediction
VALIDATION_SPLIT = 0.20  # 20% holdout for validation (chronological, no shuffle)


def _to_dec(value: Any) -> Decimal:
    """Convert numeric to Decimal at output boundary."""
    if value is None:
        return Decimal("0")
    return Decimal(str(value)).quantize(Decimal("0.00000001"), rounding=ROUND_HALF_EVEN)


# =============================================================================
# MODEL RESULT
# =============================================================================


@dataclass(frozen=True)
class ModelPrediction:
    """Output of model prediction — probabilities only, no price targets."""

    probability_up: Decimal
    probability_down: Decimal
    model_name: str
    model_version: str
    latency_ms: int
    feature_importance: Dict[str, Decimal] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if isinstance(self.probability_up, float):
            raise TypeError("Zero-Float Mandate: probability_up is float")
        if isinstance(self.probability_down, float):
            raise TypeError("Zero-Float Mandate: probability_down is float")


# =============================================================================
# LABEL GENERATION
# =============================================================================


def generate_labels(
    close_prices: Any,
    horizon: int = LABEL_HORIZON,
) -> Any:
    """
    Generate binary labels for supervised learning.
    Label = 1 if close[t+horizon] > close[t], else 0.

    Returns numpy array of labels (last `horizon` entries are NaN).
    """
    if not NUMPY_AVAILABLE:
        raise RuntimeError("SEC-ALPHA-020 numpy not available for label generation")

    prices = np.array(close_prices, dtype=np.float64)
    future_return = np.roll(prices, -horizon) / prices - 1.0
    labels = np.where(future_return > 0, 1, 0).astype(np.float64)
    # Last `horizon` labels are invalid (no future data)
    labels[-horizon:] = np.nan
    return labels


# =============================================================================
# FEATURE MATRIX BUILDER
# =============================================================================


def build_feature_matrix(
    feature_dicts: List[Dict[str, object]],
    correlation_id: str,
) -> Any:
    """
    Convert a list of FeatureVector.to_model_input() dicts to a numpy matrix.

    Decimal values are converted to float64 for model consumption.
    This is the ONLY place where float is permitted (model internals).
    Output probabilities are converted back to Decimal at boundary.
    """
    if not NUMPY_AVAILABLE:
        raise RuntimeError(
            f"SEC-ALPHA-021 numpy not available. correlation_id={correlation_id}"
        )

    n_samples = len(feature_dicts)
    n_features = len(FEATURE_NAMES)
    matrix = np.zeros((n_samples, n_features), dtype=np.float64)

    for i, fd in enumerate(feature_dicts):
        for j, name in enumerate(FEATURE_NAMES):
            val = fd.get(name, 0)
            # Decimal → float for numpy (permitted inside model boundary)
            matrix[i, j] = float(val) if isinstance(val, Decimal) else float(val)

    return matrix


# =============================================================================
# LOGISTIC REGRESSION (BASELINE)
# =============================================================================


class LogisticRegressionModel:
    """
    Baseline model — Logistic Regression with standardized features.
    Produces calibrated probability_up / probability_down.
    """

    def __init__(self) -> None:
        if not SKLEARN_AVAILABLE:
            raise RuntimeError("SEC-ALPHA-022 sklearn not available")
        self._scaler = StandardScaler()
        self._model = LogisticRegression(
            C=1.0,
            max_iter=1000,
            solver="lbfgs",
            random_state=42,
        )
        self._is_trained = False
        self._version = ""

    @property
    def is_trained(self) -> bool:
        return self._is_trained

    def train(
        self,
        X: Any,
        y: Any,
        correlation_id: str,
    ) -> Dict[str, Decimal]:
        """
        Train on feature matrix X and binary labels y.
        Returns training metrics.
        """
        # Remove NaN labels (last entries with no future data)
        mask = ~np.isnan(y)
        X_clean = X[mask]
        y_clean = y[mask]

        if len(X_clean) < 50:
            raise ValueError(
                f"SEC-ALPHA-023 Insufficient training samples: {len(X_clean)}. "
                f"correlation_id={correlation_id}"
            )

        X_scaled = self._scaler.fit_transform(X_clean)

        # Design Challenge R2: chronological train/val split
        split_idx = int(len(X_scaled) * (1 - VALIDATION_SPLIT))
        X_train, X_val = X_scaled[:split_idx], X_scaled[split_idx:]
        y_train, y_val = y_clean[:split_idx], y_clean[split_idx:]

        self._model.fit(X_train, y_train)
        self._is_trained = True

        # Version hash for traceability
        data_hash = hashlib.sha256(X_clean.tobytes() + y_clean.tobytes()).hexdigest()[
            :16
        ]
        self._version = f"LR-{data_hash}"

        # Validation accuracy (out-of-sample)
        val_pred = self._model.predict(X_val)
        val_accuracy = _to_dec(np.mean(val_pred == y_val))
        train_pred = self._model.predict(X_train)
        train_accuracy = _to_dec(np.mean(train_pred == y_train))

        return {
            "train_accuracy": train_accuracy,
            "val_accuracy": val_accuracy,
            "samples": _to_dec(len(X_clean)),
        }

    def predict(
        self,
        X: Any,
        correlation_id: str,
    ) -> ModelPrediction:
        """Predict probability_up and probability_down."""
        if not self._is_trained:
            raise RuntimeError(
                f"SEC-ALPHA-024 Model not trained. correlation_id={correlation_id}"
            )

        start = time.monotonic_ns()
        X_scaled = self._scaler.transform(X.reshape(1, -1))
        proba = self._model.predict_proba(X_scaled)[0]
        elapsed_ms = (time.monotonic_ns() - start) // 1_000_000

        # proba[0] = P(down), proba[1] = P(up)
        prob_down = _to_dec(proba[0])
        prob_up = _to_dec(proba[1])

        return ModelPrediction(
            probability_up=prob_up,
            probability_down=prob_down,
            model_name="LogisticRegression",
            model_version=self._version,
            latency_ms=int(elapsed_ms),
        )


# =============================================================================
# LIGHTGBM (PRIMARY MODEL)
# =============================================================================


class LightGBMModel:
    """
    Primary model — LightGBM gradient boosting.
    Produces calibrated probability_up / probability_down.
    """

    def __init__(self) -> None:
        if not LGBM_AVAILABLE:
            raise RuntimeError("SEC-ALPHA-025 lightgbm not available")
        self._model: Optional[Any] = None
        self._is_trained = False
        self._version = ""
        self._feature_importance: Dict[str, Decimal] = {}

    @property
    def is_trained(self) -> bool:
        return self._is_trained

    @property
    def feature_importance(self) -> Dict[str, Decimal]:
        return dict(self._feature_importance)

    def train(
        self,
        X: Any,
        y: Any,
        correlation_id: str,
    ) -> Dict[str, Decimal]:
        """Train LightGBM on feature matrix X and binary labels y."""
        mask = ~np.isnan(y)
        X_clean = X[mask]
        y_clean = y[mask]

        if len(X_clean) < 50:
            raise ValueError(
                f"SEC-ALPHA-026 Insufficient training samples: {len(X_clean)}. "
                f"correlation_id={correlation_id}"
            )

        # Design Challenge R2: chronological train/val split + early stopping
        split_idx = int(len(X_clean) * (1 - VALIDATION_SPLIT))
        X_train, X_val = X_clean[:split_idx], X_clean[split_idx:]
        y_train, y_val = y_clean[:split_idx], y_clean[split_idx:]

        train_data = lgb.Dataset(X_train, label=y_train, feature_name=FEATURE_NAMES)
        val_data = lgb.Dataset(
            X_val, label=y_val, feature_name=FEATURE_NAMES, reference=train_data
        )

        params = {
            "objective": "binary",
            "metric": "binary_logloss",
            "boosting_type": "gbdt",
            "num_leaves": 31,
            "learning_rate": 0.05,
            "feature_fraction": 0.8,
            "bagging_fraction": 0.8,
            "bagging_freq": 5,
            "verbose": -1,
            "seed": 42,
            "n_jobs": 1,
            "min_child_samples": 20,
            "reg_alpha": 0.1,
            "reg_lambda": 0.1,
        }

        callbacks = [lgb.early_stopping(stopping_rounds=10, verbose=False)]

        self._model = lgb.train(
            params,
            train_data,
            num_boost_round=200,
            valid_sets=[val_data],
            callbacks=callbacks,
        )
        self._is_trained = True

        # Version hash
        data_hash = hashlib.sha256(X_clean.tobytes() + y_clean.tobytes()).hexdigest()[
            :16
        ]
        self._version = f"LGBM-{data_hash}"

        # Feature importance
        importance = self._model.feature_importance(importance_type="gain")
        total = sum(importance) if sum(importance) > 0 else 1
        self._feature_importance = {
            FEATURE_NAMES[i]: _to_dec(importance[i] / total)
            for i in range(len(FEATURE_NAMES))
        }

        # Training + validation accuracy
        train_proba = self._model.predict(X_train)
        train_pred = (train_proba > 0.5).astype(int)
        train_accuracy = _to_dec(np.mean(train_pred == y_train))

        val_proba = self._model.predict(X_val)
        val_pred = (val_proba > 0.5).astype(int)
        val_accuracy = _to_dec(np.mean(val_pred == y_val))

        return {
            "train_accuracy": train_accuracy,
            "val_accuracy": val_accuracy,
            "samples": _to_dec(len(X_clean)),
        }

    def predict(
        self,
        X: Any,
        correlation_id: str,
    ) -> ModelPrediction:
        """Predict probability_up and probability_down."""
        if not self._is_trained or self._model is None:
            raise RuntimeError(
                f"SEC-ALPHA-027 Model not trained. correlation_id={correlation_id}"
            )

        start = time.monotonic_ns()
        proba_up_raw = self._model.predict(X.reshape(1, -1))[0]
        elapsed_ms = (time.monotonic_ns() - start) // 1_000_000

        prob_up = _to_dec(proba_up_raw)
        prob_down = _to_dec(1.0 - proba_up_raw)

        return ModelPrediction(
            probability_up=prob_up,
            probability_down=prob_down,
            model_name="LightGBM",
            model_version=self._version,
            latency_ms=int(elapsed_ms),
            feature_importance=dict(self._feature_importance),
        )

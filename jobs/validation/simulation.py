"""
============================================================================
Paper Trading Validation -- Core Simulation Engine
============================================================================

Sections A-H: Data generation, features, probabilities, baselines, metrics,
diagnosis, and alpha pipeline runner.

Reliability Level: L6 Critical (Sovereign Tier)
Decimal Integrity: All financial calculations use decimal.Decimal
============================================================================
"""

from __future__ import annotations

import hashlib
import logging
import math
import os
import random
import sys
from dataclasses import dataclass, field
from decimal import ROUND_DOWN, ROUND_HALF_EVEN, Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

# ── Project imports ──────────────────────────────────────────────────────────
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import importlib.util as _ilu


def _direct_import(module_name: str, filepath: str):
    """Import a module directly from its file, bypassing __init__.py chains."""
    if module_name in sys.modules:
        return sys.modules[module_name]
    spec = _ilu.spec_from_file_location(module_name, filepath)
    mod = _ilu.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


# Import alpha models and signal_decision (these are safe)
from app.alpha.models import (
    FeatureVector,
    MomentumFeatures,
    SignalDirection,
    SignalQuality,
    StructureFeatures,
    TrendClassification,
    VolatilityFeatures,
    VolumeFeatures,
)
from app.alpha.signal_decision import detect_regime, evaluate_signal

# Import confidence_arbiter and risk_governor directly (bypass app.logic.__init__)
_arbiter_mod = _direct_import(
    "app.logic.confidence_arbiter",
    os.path.join(_PROJECT_ROOT, "app", "logic", "confidence_arbiter.py"),
)
ConfidenceArbiter = _arbiter_mod.ConfidenceArbiter

_risk_mod = _direct_import(
    "app.logic.risk_governor",
    os.path.join(_PROJECT_ROOT, "app", "logic", "risk_governor.py"),
)
RiskGovernor = _risk_mod.RiskGovernor

# Import demo_broker directly (bypass services.__init__)
_broker_mod = _direct_import(
    "services.demo_broker",
    os.path.join(_PROJECT_ROOT, "services", "demo_broker.py"),
)
DemoBroker = _broker_mod.DemoBroker
DemoMode = _broker_mod.DemoMode
OrderSide = _broker_mod.OrderSide

# ── Logging ──────────────────────────────────────────────────────────────────
logger = logging.getLogger("paper_trading_validation.simulation")

# ── Constants ────────────────────────────────────────────────────────────────
ZERO = Decimal("0")
ONE = Decimal("1")
HUNDRED = Decimal("100")
PRECISION_ZAR = Decimal("0.01")
PRECISION_PRICE = Decimal("0.00000001")
PRECISION_CONF = Decimal("0.01")

NUM_CANDLES = 500
INITIAL_EQUITY_ZAR = Decimal("100000.00")
SYMBOL = "BTCZAR"
SEED = 42


# ============================================================================
# SECTION A: Synthetic Market Data Generator
# ============================================================================


def _dec(value: object) -> Decimal:
    """Convert to Decimal at boundary."""
    if isinstance(value, float):
        return Decimal(str(value)).quantize(PRECISION_PRICE, rounding=ROUND_HALF_EVEN)
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value)).quantize(PRECISION_PRICE, rounding=ROUND_HALF_EVEN)


@dataclass
class SyntheticCandle:
    """Single OHLCV candle. All Decimal."""

    timestamp_ms: int
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal


def generate_synthetic_ohlcv(
    num_candles: int,
    seed: int,
    correlation_id: str,
) -> List[SyntheticCandle]:
    """
    Generate deterministic synthetic BTCZAR OHLCV data with realistic
    regime changes (trending, ranging, volatile).
    Uses geometric Brownian motion with regime shifts.
    """
    rng = random.Random(seed)
    candles: List[SyntheticCandle] = []

    price = 1_800_000.0
    base_ts = 1700000000000
    interval_ms = 3_600_000

    regimes = [
        (0.0002, 0.008, 80),
        (-0.0001, 0.006, 60),
        (0.0000, 0.012, 40),
        (0.0004, 0.007, 70),
        (-0.0003, 0.010, 50),
        (0.0001, 0.005, 60),
        (0.0000, 0.015, 40),
        (0.0002, 0.006, 100),
    ]

    regime_idx = 0
    candles_in_regime = 0

    for i in range(num_candles):
        drift, vol, duration = regimes[regime_idx % len(regimes)]
        candles_in_regime += 1

        if candles_in_regime >= duration:
            regime_idx += 1
            candles_in_regime = 0

        shock = rng.gauss(0, 1)
        ret = drift + vol * shock
        new_price = price * (1.0 + ret)

        intra_high = max(price, new_price) * (1.0 + abs(rng.gauss(0, 0.002)))
        intra_low = min(price, new_price) * (1.0 - abs(rng.gauss(0, 0.002)))
        volume = max(0.1, rng.gauss(5.0, 2.0))

        candles.append(
            SyntheticCandle(
                timestamp_ms=base_ts + i * interval_ms,
                open=_dec(price),
                high=_dec(intra_high),
                low=_dec(intra_low),
                close=_dec(new_price),
                volume=_dec(volume),
            )
        )
        price = new_price

    logger.info(
        "Generated %d synthetic candles | start=%s | end=%s | cid=%s",
        len(candles),
        candles[0].open,
        candles[-1].close,
        correlation_id,
    )
    return candles


# ============================================================================
# SECTION B: Pure-Python Feature Extraction
# ============================================================================


def _ema(values: List[Decimal], span: int) -> List[Decimal]:
    if not values:
        return []
    alpha = Decimal("2") / (Decimal(str(span)) + ONE)
    result: List[Decimal] = [values[0]]
    for i in range(1, len(values)):
        ema_val = alpha * values[i] + (ONE - alpha) * result[-1]
        result.append(ema_val.quantize(PRECISION_PRICE, rounding=ROUND_HALF_EVEN))
    return result


def _sma(values: List[Decimal], period: int) -> Decimal:
    if len(values) < period:
        return ZERO
    window = values[-period:]
    return (sum(window) / Decimal(str(period))).quantize(PRECISION_PRICE, rounding=ROUND_HALF_EVEN)


def _rsi(closes: List[Decimal], period: int = 14) -> Decimal:
    if len(closes) < period + 1:
        return Decimal("50")

    gains: List[Decimal] = []
    losses: List[Decimal] = []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        if diff > ZERO:
            gains.append(diff)
            losses.append(ZERO)
        else:
            gains.append(ZERO)
            losses.append(abs(diff))

    recent_gains = gains[-period:]
    recent_losses = losses[-period:]

    avg_gain = sum(recent_gains) / Decimal(str(period))
    avg_loss = sum(recent_losses) / Decimal(str(period))

    if avg_loss == ZERO:
        return HUNDRED
    rs = avg_gain / avg_loss
    rsi_val = HUNDRED - (HUNDRED / (ONE + rs))
    return rsi_val.quantize(PRECISION_PRICE, rounding=ROUND_HALF_EVEN)


def _atr(candles: List[SyntheticCandle], period: int = 14) -> Decimal:
    if len(candles) < period + 1:
        return ZERO

    true_ranges: List[Decimal] = []
    for i in range(1, len(candles)):
        high = candles[i].high
        low = candles[i].low
        prev_close = candles[i - 1].close
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        true_ranges.append(tr)

    recent = true_ranges[-period:]
    return (sum(recent) / Decimal(str(period))).quantize(PRECISION_PRICE, rounding=ROUND_HALF_EVEN)


def extract_features_pure(
    candles: List[SyntheticCandle],
    index: int,
    symbol: str,
    correlation_id: str,
) -> Optional[FeatureVector]:
    """Extract FeatureVector using pure Python math. Requires >= 201 candles."""
    if index < 200:
        return None

    window = candles[: index + 1]
    closes = [c.close for c in window]

    # Structure
    ema_20_series = _ema(closes, 20)
    ema_50_series = _ema(closes, 50)
    ema_200_series = _ema(closes, 200)

    ema_20 = ema_20_series[-1]
    ema_50 = ema_50_series[-1]
    ema_200 = ema_200_series[-1]

    ema_20_above_50 = ema_20 > ema_50
    ema_50_above_200 = ema_50 > ema_200

    if ema_20_above_50 and ema_50_above_200:
        trend = TrendClassification.BULL
    elif not ema_20_above_50 and not ema_50_above_200:
        trend = TrendClassification.BEAR
    else:
        trend = TrendClassification.NEUTRAL

    structure = StructureFeatures(
        ema_20=ema_20,
        ema_50=ema_50,
        ema_200=ema_200,
        trend=trend,
        ema_20_above_50=ema_20_above_50,
        ema_50_above_200=ema_50_above_200,
    )

    # Momentum
    rsi_14 = _rsi(closes, 14)
    ema_12 = _ema(closes, 12)
    ema_26 = _ema(closes, 26)
    macd_line = ema_12[-1] - ema_26[-1]
    macd_history = [ema_12[i] - ema_26[i] for i in range(len(ema_12))]
    macd_signal_series = _ema(macd_history, 9)
    macd_signal = macd_signal_series[-1] if macd_signal_series else ZERO
    macd_histogram = macd_line - macd_signal

    current_close = closes[-1]
    return_1 = (
        ((closes[-1] - closes[-2]) / closes[-2]).quantize(PRECISION_PRICE, rounding=ROUND_HALF_EVEN)
        if len(closes) >= 2
        else ZERO
    )
    return_5 = (
        ((closes[-1] - closes[-6]) / closes[-6]).quantize(PRECISION_PRICE, rounding=ROUND_HALF_EVEN)
        if len(closes) >= 6
        else ZERO
    )
    return_10 = (
        ((closes[-1] - closes[-11]) / closes[-11]).quantize(
            PRECISION_PRICE, rounding=ROUND_HALF_EVEN
        )
        if len(closes) >= 11
        else ZERO
    )

    momentum = MomentumFeatures(
        rsi_14=rsi_14,
        macd_line=macd_line,
        macd_signal=macd_signal,
        macd_histogram=macd_histogram,
        return_1=return_1,
        return_5=return_5,
        return_10=return_10,
    )

    # Volume
    volumes = [c.volume for c in window]
    vwap_num = sum(c.close * c.volume for c in window[-20:])
    vwap_den = sum(c.volume for c in window[-20:])
    vwap = (
        (vwap_num / vwap_den).quantize(PRECISION_PRICE, rounding=ROUND_HALF_EVEN)
        if vwap_den > ZERO
        else current_close
    )
    vol_sma_20 = _sma(volumes, 20)
    vol_ratio = (
        (volumes[-1] / vol_sma_20).quantize(PRECISION_PRICE, rounding=ROUND_HALF_EVEN)
        if vol_sma_20 > ZERO
        else ONE
    )
    vol_spike = vol_ratio > Decimal("2")

    volume_features = VolumeFeatures(
        vwap=vwap,
        volume_sma_20=vol_sma_20,
        volume_ratio=vol_ratio,
        volume_spike=vol_spike,
    )

    # Volatility
    atr_14 = _atr(window, 14)
    atr_ratio = (
        (atr_14 / current_close).quantize(PRECISION_PRICE, rounding=ROUND_HALF_EVEN)
        if current_close > ZERO
        else ZERO
    )
    bar_range = (candles[index].high - candles[index].low).quantize(
        PRECISION_PRICE, rounding=ROUND_HALF_EVEN
    )
    prev_range = (candles[index - 1].high - candles[index - 1].low) if index > 0 else bar_range
    range_expansion = bar_range > prev_range * Decimal("1.5")

    bb_mid = _sma(closes, 20)
    bb_std_values = closes[-20:]
    if len(bb_std_values) >= 2:
        mean_val = sum(bb_std_values) / Decimal(str(len(bb_std_values)))
        variance = sum((v - mean_val) ** 2 for v in bb_std_values) / Decimal(
            str(len(bb_std_values))
        )
        std_approx = _dec(math.sqrt(float(variance)))
    else:
        std_approx = ZERO

    bb_upper = bb_mid + Decimal("2") * std_approx
    bb_lower = bb_mid - Decimal("2") * std_approx
    breakout_up = current_close > bb_upper
    breakout_down = current_close < bb_lower

    volatility = VolatilityFeatures(
        atr_14=atr_14,
        atr_ratio=atr_ratio,
        bar_range=bar_range,
        range_expansion=range_expansion,
        breakout_up=breakout_up,
        breakout_down=breakout_down,
    )

    return FeatureVector(
        symbol=symbol,
        timestamp_ms=candles[index].timestamp_ms,
        structure=structure,
        momentum=momentum,
        volume=volume_features,
        volatility=volatility,
    )


# ============================================================================
# SECTION C: Probability Estimation
# ============================================================================


def estimate_probabilities(
    fv: FeatureVector,
    correlation_id: str,
) -> Tuple[Decimal, Decimal]:
    """Momentum-persistence probability estimation.

    Scores based on multi-timeframe return consistency rather than
    individual indicator states.  Only generates strong directional
    signals when multiple periods of return data AGREE on direction
    AND structural indicators CONFIRM momentum.
    """
    score = Decimal("0")

    # 1. Multi-timeframe return consistency (PRIMARY signal)
    returns = [fv.momentum.return_1, fv.momentum.return_5, fv.momentum.return_10]
    positive_count = sum(1 for r in returns if r > ZERO)
    negative_count = sum(1 for r in returns if r < ZERO)

    if positive_count == 3:
        score += Decimal("0.20")
    elif negative_count == 3:
        score -= Decimal("0.20")
    elif positive_count == 2:
        score += Decimal("0.08")
    elif negative_count == 2:
        score -= Decimal("0.08")

    # 2. Momentum acceleration (short-term vs long-term)
    if fv.momentum.return_5 != ZERO:
        avg_5_bar = fv.momentum.return_5 / Decimal("5")
        if fv.momentum.return_1 > avg_5_bar and fv.momentum.return_1 > ZERO:
            score += Decimal("0.05")
        elif fv.momentum.return_1 < avg_5_bar and fv.momentum.return_1 < ZERO:
            score -= Decimal("0.05")

    # 3. Structural confirmation (lagging — confirms regime)
    if fv.structure.trend == TrendClassification.BULL:
        score += Decimal("0.08")
    elif fv.structure.trend == TrendClassification.BEAR:
        score -= Decimal("0.08")

    # 4. RSI mean-reversion pressure (contrarian at extremes)
    if fv.momentum.rsi_14 > Decimal("75"):
        score -= Decimal("0.07")
    elif fv.momentum.rsi_14 < Decimal("25"):
        score += Decimal("0.07")
    elif fv.momentum.rsi_14 > Decimal("55"):
        score += Decimal("0.03")
    elif fv.momentum.rsi_14 < Decimal("45"):
        score -= Decimal("0.03")

    # 5. Volume confirmation
    if fv.volume.volume_ratio > Decimal("1.3"):
        if score > ZERO:
            score += Decimal("0.03")
        elif score < ZERO:
            score -= Decimal("0.03")

    # 6. Volatility dampening (high vol reduces conviction)
    if fv.volatility.atr_ratio > Decimal("0.02"):
        score = (score * Decimal("0.8")).quantize(PRECISION_PRICE, rounding=ROUND_HALF_EVEN)

    clamped = max(Decimal("-0.50"), min(Decimal("0.50"), score))
    prob_up = (Decimal("0.50") + clamped).quantize(PRECISION_PRICE, rounding=ROUND_HALF_EVEN)
    prob_down = (ONE - prob_up).quantize(PRECISION_PRICE, rounding=ROUND_HALF_EVEN)
    return prob_up, prob_down


# ============================================================================
# SECTION D: Decision Record
# ============================================================================


class DecisionOutcome(str, Enum):
    SIGNAL_APPROVED = "SIGNAL_APPROVED"
    SIGNAL_REJECTED_QUALITY = "SIGNAL_REJECTED_QUALITY"
    SIGNAL_REJECTED_CONFIDENCE = "SIGNAL_REJECTED_CONFIDENCE"
    SIGNAL_REJECTED_RISK = "SIGNAL_REJECTED_RISK"
    NO_SIGNAL = "NO_SIGNAL"
    SKIPPED = "SKIPPED"


@dataclass
class DecisionRecord:
    """Full audit record of a single trading decision."""

    correlation_id: str
    timestamp_ms: int
    symbol: str
    candle_index: int
    direction: str
    probability_up: Decimal
    probability_down: Decimal
    confidence: Decimal
    quality: str
    regime: str
    reject_reasons: List[str]
    outcome: str
    arbiter_adjusted_confidence: Decimal
    arbiter_should_execute: bool
    risk_approved: bool
    risk_qty: Decimal
    executed: bool
    order_side: str
    fill_price: Decimal
    fill_qty: Decimal
    exit_price: Decimal = ZERO
    realized_pnl_zar: Decimal = ZERO
    bars_held: int = 0
    trade_outcome: str = ""
    row_hash: str = ""

    def compute_hash(self) -> str:
        payload = (
            str(self.correlation_id)
            + "|"
            + str(self.timestamp_ms)
            + "|"
            + str(self.symbol)
            + "|"
            + str(self.direction)
            + "|"
            + str(self.probability_up)
            + "|"
            + str(self.outcome)
            + "|"
            + str(self.fill_price)
            + "|"
            + str(self.realized_pnl_zar)
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


# ============================================================================
# SECTION E: Baseline Strategies
# ============================================================================


class BaselineStrategy:
    def __init__(self, name: str, seed: int):
        self.name = name
        self._rng = random.Random(seed)
        self.trades: List[Dict[str, Any]] = []

    def should_trade(self, index: int, candles: List[SyntheticCandle]) -> Optional[str]:
        raise NotImplementedError


class RandomBaseline(BaselineStrategy):
    def __init__(self, seed: int):
        super().__init__("RANDOM_DIRECTION", seed)

    def should_trade(self, index: int, candles: List[SyntheticCandle]) -> Optional[str]:
        if self._rng.random() < 0.15:
            return "BUY" if self._rng.random() > 0.5 else "SELL"
        return None


class SimpleIndicatorBaseline(BaselineStrategy):
    def __init__(self, seed: int):
        super().__init__("EMA_CROSSOVER", seed)
        self._prev_above: Optional[bool] = None

    def should_trade(self, index: int, candles: List[SyntheticCandle]) -> Optional[str]:
        if index < 51:
            return None
        closes = [c.close for c in candles[: index + 1]]
        ema_20 = _ema(closes, 20)
        ema_50 = _ema(closes, 50)
        currently_above = ema_20[-1] > ema_50[-1]
        if self._prev_above is not None and currently_above != self._prev_above:
            self._prev_above = currently_above
            return "BUY" if currently_above else "SELL"
        self._prev_above = currently_above
        return None


def run_baseline(
    baseline: BaselineStrategy,
    candles: List[SyntheticCandle],
    initial_equity: Decimal,
    max_bars_hold: int = 5,
    risk_pct: Decimal = Decimal("0.01"),
) -> List[Dict[str, Any]]:
    """Run a baseline strategy over synthetic data."""
    trades: List[Dict[str, Any]] = []
    equity = initial_equity
    position_open = False
    entry_price = ZERO
    entry_bar = 0
    side = ""

    for i in range(200, len(candles)):
        current_price = candles[i].close

        if position_open and (i - entry_bar) >= max_bars_hold:
            price_diff = current_price - entry_price
            if side == "SELL":
                price_diff = -price_diff
            qty = (equity * risk_pct / max(abs(entry_price * Decimal("0.02")), ONE)).quantize(
                PRECISION_PRICE, rounding=ROUND_DOWN
            )
            pnl = (price_diff * qty).quantize(PRECISION_ZAR, rounding=ROUND_HALF_EVEN)
            equity += pnl
            trades.append(
                {
                    "entry_bar": entry_bar,
                    "exit_bar": i,
                    "side": side,
                    "entry_price": str(entry_price),
                    "exit_price": str(current_price),
                    "pnl_zar": str(pnl),
                    "bars_held": i - entry_bar,
                    "outcome": "WIN" if pnl > ZERO else "LOSS",
                }
            )
            position_open = False

        if not position_open:
            signal = baseline.should_trade(i, candles)
            if signal:
                side = signal
                entry_price = current_price
                entry_bar = i
                position_open = True

    return trades


# ============================================================================
# SECTION F: Metrics Calculator
# ============================================================================


@dataclass
class TradingMetrics:
    strategy_name: str
    total_signals: int = 0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    breakeven_trades: int = 0
    win_rate: Decimal = ZERO
    total_pnl_zar: Decimal = ZERO
    cumulative_return_pct: Decimal = ZERO
    max_drawdown_pct: Decimal = ZERO
    profit_factor: Decimal = ZERO
    expectancy_zar: Decimal = ZERO
    avg_win_zar: Decimal = ZERO
    avg_loss_zar: Decimal = ZERO
    signals_generated: int = 0
    signals_approved: int = 0
    signals_rejected_quality: int = 0
    signals_rejected_confidence: int = 0
    signals_rejected_risk: int = 0
    approval_rate_pct: Decimal = ZERO
    avg_latency_ms: int = 0
    error_count: int = 0

    def to_csv_row(self) -> Dict[str, str]:
        return {
            "strategy_name": self.strategy_name,
            "total_signals": str(self.total_signals),
            "total_trades": str(self.total_trades),
            "winning_trades": str(self.winning_trades),
            "losing_trades": str(self.losing_trades),
            "win_rate": str(self.win_rate),
            "total_pnl_zar": str(self.total_pnl_zar),
            "cumulative_return_pct": str(self.cumulative_return_pct),
            "max_drawdown_pct": str(self.max_drawdown_pct),
            "profit_factor": str(self.profit_factor),
            "expectancy_zar": str(self.expectancy_zar),
            "avg_win_zar": str(self.avg_win_zar),
            "avg_loss_zar": str(self.avg_loss_zar),
            "signals_approved": str(self.signals_approved),
            "signals_rejected_quality": str(self.signals_rejected_quality),
            "signals_rejected_confidence": str(self.signals_rejected_confidence),
            "signals_rejected_risk": str(self.signals_rejected_risk),
            "approval_rate_pct": str(self.approval_rate_pct),
        }


def compute_metrics(
    strategy_name: str,
    trades: List[Dict[str, Any]],
    initial_equity: Decimal,
    decision_records: Optional[List[DecisionRecord]] = None,
) -> TradingMetrics:
    """Compute all trading metrics from trade results."""
    m = TradingMetrics(strategy_name=strategy_name)
    m.total_trades = len(trades)

    if not trades:
        return m

    wins: List[Decimal] = []
    losses: List[Decimal] = []
    pnl_series: List[Decimal] = []
    equity_curve: List[Decimal] = [initial_equity]

    for t in trades:
        pnl = Decimal(str(t["pnl_zar"]))
        pnl_series.append(pnl)
        if pnl > ZERO:
            m.winning_trades += 1
            wins.append(pnl)
        elif pnl < ZERO:
            m.losing_trades += 1
            losses.append(pnl)
        else:
            m.breakeven_trades += 1
        equity_curve.append(equity_curve[-1] + pnl)

    m.total_pnl_zar = sum(pnl_series).quantize(PRECISION_ZAR, rounding=ROUND_HALF_EVEN)
    m.win_rate = (
        (Decimal(str(m.winning_trades)) / Decimal(str(m.total_trades)) * HUNDRED).quantize(
            PRECISION_ZAR, rounding=ROUND_HALF_EVEN
        )
        if m.total_trades > 0
        else ZERO
    )
    m.cumulative_return_pct = (m.total_pnl_zar / initial_equity * HUNDRED).quantize(
        PRECISION_ZAR, rounding=ROUND_HALF_EVEN
    )
    m.avg_win_zar = (
        (sum(wins) / Decimal(str(len(wins)))).quantize(PRECISION_ZAR, rounding=ROUND_HALF_EVEN)
        if wins
        else ZERO
    )
    m.avg_loss_zar = (
        (sum(losses) / Decimal(str(len(losses)))).quantize(PRECISION_ZAR, rounding=ROUND_HALF_EVEN)
        if losses
        else ZERO
    )

    gross_profit = sum(wins) if wins else ZERO
    gross_loss = abs(sum(losses)) if losses else ZERO
    m.profit_factor = (
        (gross_profit / gross_loss).quantize(PRECISION_ZAR, rounding=ROUND_HALF_EVEN)
        if gross_loss > ZERO
        else Decimal("999.99")
    )
    m.expectancy_zar = (
        (m.total_pnl_zar / Decimal(str(m.total_trades))).quantize(
            PRECISION_ZAR, rounding=ROUND_HALF_EVEN
        )
        if m.total_trades > 0
        else ZERO
    )

    peak = initial_equity
    max_dd = ZERO
    for eq in equity_curve:
        if eq > peak:
            peak = eq
        dd = (peak - eq) / peak * HUNDRED if peak > ZERO else ZERO
        if dd > max_dd:
            max_dd = dd
    m.max_drawdown_pct = max_dd.quantize(PRECISION_ZAR, rounding=ROUND_HALF_EVEN)

    if decision_records:
        m.total_signals = len(decision_records)
        m.signals_generated = len(decision_records)
        m.signals_approved = sum(
            1 for d in decision_records if d.outcome == DecisionOutcome.SIGNAL_APPROVED.value
        )
        m.signals_rejected_quality = sum(
            1
            for d in decision_records
            if d.outcome == DecisionOutcome.SIGNAL_REJECTED_QUALITY.value
        )
        m.signals_rejected_confidence = sum(
            1
            for d in decision_records
            if d.outcome == DecisionOutcome.SIGNAL_REJECTED_CONFIDENCE.value
        )
        m.signals_rejected_risk = sum(
            1 for d in decision_records if d.outcome == DecisionOutcome.SIGNAL_REJECTED_RISK.value
        )
        m.approval_rate_pct = (
            (Decimal(str(m.signals_approved)) / Decimal(str(m.total_signals)) * HUNDRED).quantize(
                PRECISION_ZAR, rounding=ROUND_HALF_EVEN
            )
            if m.total_signals > 0
            else ZERO
        )

    return m


# ============================================================================
# SECTION G: Edge Diagnosis
# ============================================================================


@dataclass
class EdgeDiagnosis:
    total_decisions: int = 0
    rejection_breakdown: Dict[str, int] = field(default_factory=dict)
    regime_performance: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    confidence_distribution: Dict[str, int] = field(default_factory=dict)
    quality_distribution: Dict[str, int] = field(default_factory=dict)
    direction_accuracy: Dict[str, Dict[str, int]] = field(default_factory=dict)
    hitl_impact: str = "N/A -- No HITL overrides in simulation mode"
    bottleneck: str = ""
    key_findings: List[str] = field(default_factory=list)


def diagnose_edge(
    decision_records: List[DecisionRecord],
    alpha_metrics: TradingMetrics,
    random_metrics: TradingMetrics,
    ema_metrics: TradingMetrics,
) -> EdgeDiagnosis:
    """Analyze where the system generates or loses alpha."""
    diag = EdgeDiagnosis()
    diag.total_decisions = len(decision_records)

    if not decision_records:
        diag.key_findings.append("No decisions recorded -- cannot diagnose edge.")
        return diag

    # Rejection breakdown
    for rec in decision_records:
        outcome = rec.outcome
        diag.rejection_breakdown[outcome] = diag.rejection_breakdown.get(outcome, 0) + 1

    # Regime performance
    regime_trades: Dict[str, List[Decimal]] = {}
    for rec in decision_records:
        regime = rec.regime
        if regime not in regime_trades:
            regime_trades[regime] = []
        if rec.executed:
            regime_trades[regime].append(rec.realized_pnl_zar)

    for regime, pnls in regime_trades.items():
        if pnls:
            wins = sum(1 for p in pnls if p > ZERO)
            total = len(pnls)
            diag.regime_performance[regime] = {
                "trades": total,
                "wins": wins,
                "win_rate": str(
                    (Decimal(str(wins)) / Decimal(str(total)) * HUNDRED).quantize(PRECISION_ZAR)
                ),
                "total_pnl": str(sum(pnls).quantize(PRECISION_ZAR)),
            }

    # Confidence distribution
    for rec in decision_records:
        conf = rec.arbiter_adjusted_confidence
        if conf >= Decimal("95"):
            bucket = "95-100"
        elif conf >= Decimal("80"):
            bucket = "80-95"
        elif conf >= Decimal("60"):
            bucket = "60-80"
        else:
            bucket = "0-60"
        diag.confidence_distribution[bucket] = diag.confidence_distribution.get(bucket, 0) + 1

    # Quality distribution
    for rec in decision_records:
        q = rec.quality
        diag.quality_distribution[q] = diag.quality_distribution.get(q, 0) + 1

    # Direction accuracy
    for rec in decision_records:
        if rec.executed and rec.trade_outcome:
            direction = rec.direction
            if direction not in diag.direction_accuracy:
                diag.direction_accuracy[direction] = {"correct": 0, "incorrect": 0}
            if rec.trade_outcome == "WIN":
                diag.direction_accuracy[direction]["correct"] += 1
            else:
                diag.direction_accuracy[direction]["incorrect"] += 1

    # Bottleneck identification
    rejected_quality = diag.rejection_breakdown.get(
        DecisionOutcome.SIGNAL_REJECTED_QUALITY.value, 0
    )
    rejected_conf = diag.rejection_breakdown.get(
        DecisionOutcome.SIGNAL_REJECTED_CONFIDENCE.value, 0
    )
    rejected_risk = diag.rejection_breakdown.get(DecisionOutcome.SIGNAL_REJECTED_RISK.value, 0)
    approved = diag.rejection_breakdown.get(DecisionOutcome.SIGNAL_APPROVED.value, 0)

    if rejected_quality > approved:
        diag.bottleneck = "SIGNAL_QUALITY -- Most signals rejected by Alpha Detection Layer"
        diag.key_findings.append(
            "Signal quality filter is the primary bottleneck: "
            + str(rejected_quality)
            + " rejected vs "
            + str(approved)
            + " approved."
        )
    elif rejected_conf > approved:
        diag.bottleneck = "CONFIDENCE_GATE -- 95% threshold blocks most promising signals"
        diag.key_findings.append(
            "Confidence gate (95%) is the primary bottleneck: "
            + str(rejected_conf)
            + " rejected vs "
            + str(approved)
            + " approved."
        )
    elif rejected_risk > approved:
        diag.bottleneck = "RISK_GOVERNOR -- Position sizing rejects too many signals"
        diag.key_findings.append(
            "Risk governor is the primary bottleneck: "
            + str(rejected_risk)
            + " rejected vs "
            + str(approved)
            + " approved."
        )
    else:
        diag.bottleneck = "NONE_DOMINANT -- Rejections distributed across filters"

    # Alpha comparison
    alpha_pnl = alpha_metrics.total_pnl_zar
    random_pnl = random_metrics.total_pnl_zar
    ema_pnl = ema_metrics.total_pnl_zar

    if alpha_pnl > random_pnl and alpha_pnl > ema_pnl:
        diag.key_findings.append(
            "System outperforms both baselines: Alpha="
            + str(alpha_pnl)
            + " vs Random="
            + str(random_pnl)
            + " vs EMA="
            + str(ema_pnl)
        )
    elif alpha_pnl > random_pnl:
        diag.key_findings.append(
            "System beats random but not EMA crossover: Alpha="
            + str(alpha_pnl)
            + " vs Random="
            + str(random_pnl)
            + " vs EMA="
            + str(ema_pnl)
        )
    else:
        diag.key_findings.append(
            "System does NOT beat random baseline: Alpha="
            + str(alpha_pnl)
            + " vs Random="
            + str(random_pnl)
            + " vs EMA="
            + str(ema_pnl)
        )

    # Regime insight
    if diag.regime_performance:
        best_regime = max(
            diag.regime_performance.items(),
            key=lambda x: Decimal(x[1]["total_pnl"]),
        )
        worst_regime = min(
            diag.regime_performance.items(),
            key=lambda x: Decimal(x[1]["total_pnl"]),
        )
        diag.key_findings.append(
            "Best regime: "
            + best_regime[0]
            + " (PnL="
            + str(best_regime[1]["total_pnl"])
            + "). "
            + "Worst regime: "
            + worst_regime[0]
            + " (PnL="
            + str(worst_regime[1]["total_pnl"])
            + ")."
        )

    # Approval rate
    if diag.total_decisions > 0:
        approval_pct = Decimal(str(approved)) / Decimal(str(diag.total_decisions)) * HUNDRED
        diag.key_findings.append(
            "Approval rate: "
            + str(approval_pct.quantize(PRECISION_ZAR))
            + "% "
            + "("
            + str(approved)
            + "/"
            + str(diag.total_decisions)
            + " signals approved)."
        )

    return diag


# ============================================================================
# SECTION H: Main Simulation Runner
# ============================================================================


def _get_output_dir() -> str:
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "data",
        "validation_results",
    )


def run_alpha_system(
    candles: List[SyntheticCandle],
    correlation_id: str,
    bypass_confidence_gate: bool = False,
    strict_threshold: Optional[Decimal] = None,
) -> Tuple[List[DecisionRecord], List[Dict[str, Any]]]:
    """
    Run the full alpha decision pipeline over synthetic candles.
    Returns (decision_records, executed_trades).

    Args:
        strict_threshold: Override for the confidence arbiter execution
            threshold. When ``None``, the module-level
            ``EXECUTION_THRESHOLD`` (95.00) is used.
    """
    output_dir = _get_output_dir()
    arbiter = ConfidenceArbiter()

    # Allow caller to override the execution threshold for calibration
    if strict_threshold is not None:
        arbiter_threshold = strict_threshold
    else:
        arbiter_threshold = None  # use module default
    risk_gov = RiskGovernor(
        risk_pct=Decimal("0.01"),
        min_qty=Decimal("0.0001"),
        daily_loss_limit=Decimal("0.03"),
        max_position_pct=Decimal("0.30"),
    )
    broker = DemoBroker(
        starting_balance_zar=INITIAL_EQUITY_ZAR,
        mode=DemoMode.PAPER,
        state_file=os.path.join(output_dir, "alpha_broker_state.json"),
        correlation_id=correlation_id,
    )

    decision_records: List[DecisionRecord] = []
    executed_trades: List[Dict[str, Any]] = []

    position_open = False
    position_entry_bar = 0
    position_entry_price = ZERO
    position_side = ""
    position_record_idx = -1
    max_bars_hold = 5

    atr_history: List[Decimal] = []
    close_history: List[Decimal] = []

    for i in range(200, len(candles)):
        candle = candles[i]
        cid = correlation_id + "-" + str(i)

        broker.update_market_price(SYMBOL, candle.close, cid)

        # Close existing position if max hold reached
        if position_open and (i - position_entry_bar) >= max_bars_hold:
            exit_price = candle.close
            price_diff = exit_price - position_entry_price
            if position_side == "SELL":
                price_diff = -price_diff

            close_side = OrderSide.SELL if position_side == "BUY" else OrderSide.BUY
            broker.place_market_order(
                symbol=SYMBOL,
                side=close_side,
                quantity=decision_records[position_record_idx].fill_qty,
                correlation_id=cid,
            )
            pnl = (price_diff * decision_records[position_record_idx].fill_qty).quantize(
                PRECISION_ZAR, rounding=ROUND_HALF_EVEN
            )

            decision_records[position_record_idx].exit_price = exit_price
            decision_records[position_record_idx].realized_pnl_zar = pnl
            decision_records[position_record_idx].bars_held = i - position_entry_bar
            decision_records[position_record_idx].trade_outcome = "WIN" if pnl > ZERO else "LOSS"
            executed_trades.append(
                {
                    "entry_bar": position_entry_bar,
                    "exit_bar": i,
                    "side": position_side,
                    "entry_price": str(position_entry_price),
                    "exit_price": str(exit_price),
                    "pnl_zar": str(pnl),
                    "bars_held": i - position_entry_bar,
                    "outcome": "WIN" if pnl > ZERO else "LOSS",
                }
            )
            position_open = False

        if position_open:
            continue

        # Extract features
        fv = extract_features_pure(candles, i, SYMBOL, cid)
        if fv is None:
            continue

        atr_history.append(fv.volatility.atr_14)
        close_history.append(candle.close)
        if len(atr_history) > 100:
            atr_history = atr_history[-100:]
            close_history = close_history[-100:]

        regime = detect_regime(atr_history, close_history, cid)
        prob_up, prob_down = estimate_probabilities(fv, cid)
        signal = evaluate_signal(fv, prob_up, prob_down, regime, cid)

        record = DecisionRecord(
            correlation_id=cid,
            timestamp_ms=candle.timestamp_ms,
            symbol=SYMBOL,
            candle_index=i,
            direction=signal.direction.value,
            probability_up=signal.probability_up,
            probability_down=signal.probability_down,
            confidence=signal.confidence,
            quality=signal.quality.value,
            regime=signal.regime.value if isinstance(signal.regime, Enum) else str(signal.regime),
            reject_reasons=[
                r.value if isinstance(r, Enum) else str(r) for r in signal.reject_reasons
            ],
            outcome=DecisionOutcome.NO_SIGNAL.value,
            arbiter_adjusted_confidence=ZERO,
            arbiter_should_execute=False,
            risk_approved=False,
            risk_qty=ZERO,
            executed=False,
            order_side="",
            fill_price=ZERO,
            fill_qty=ZERO,
        )

        # Gate 1: Signal quality
        if not signal.is_actionable:
            record.outcome = DecisionOutcome.SIGNAL_REJECTED_QUALITY.value
            record.row_hash = record.compute_hash()
            decision_records.append(record)
            continue

        # Gate 2: Confidence arbiter
        llm_confidence = (signal.confidence * HUNDRED).quantize(
            PRECISION_CONF, rounding=ROUND_HALF_EVEN
        )
        trust_prob = Decimal("0.85") if signal.quality == SignalQuality.HIGH else Decimal("0.70")
        arb_result = arbiter.arbitrate(
            llm_confidence=llm_confidence,
            trust_probability=trust_prob,
            execution_health=ONE,
            correlation_id=cid,
        )
        record.arbiter_adjusted_confidence = arb_result.adjusted_confidence
        record.arbiter_should_execute = arb_result.should_execute

        # Apply override threshold when provided for calibration
        should_execute = arb_result.should_execute
        if arbiter_threshold is not None:
            should_execute = arb_result.adjusted_confidence >= arbiter_threshold

        if not should_execute and not bypass_confidence_gate:
            record.outcome = DecisionOutcome.SIGNAL_REJECTED_CONFIDENCE.value
            record.row_hash = record.compute_hash()
            decision_records.append(record)
            continue

        # Gate 3: Risk governor
        equity = broker.get_account_equity(cid)
        entry_price = candle.close
        atr = fv.volatility.atr_14
        stop_distance = atr * Decimal("2")

        if signal.direction == SignalDirection.LONG:
            stop_price = (entry_price - stop_distance).quantize(
                PRECISION_PRICE, rounding=ROUND_HALF_EVEN
            )
        else:
            stop_price = (entry_price + stop_distance).quantize(
                PRECISION_PRICE, rounding=ROUND_HALF_EVEN
            )

        permit = risk_gov.get_execution_permit(
            equity_zar=equity,
            entry_price=entry_price,
            stop_price=stop_price,
            atr=atr,
            correlation_id=cid,
        )
        if permit is None:
            record.outcome = DecisionOutcome.SIGNAL_REJECTED_RISK.value
            record.risk_approved = False
            record.row_hash = record.compute_hash()
            decision_records.append(record)
            continue

        # Execute trade
        record.risk_approved = True
        record.risk_qty = permit.approved_qty

        order_side = OrderSide.BUY if signal.direction == SignalDirection.LONG else OrderSide.SELL
        order_result = broker.place_market_order(
            symbol=SYMBOL,
            side=order_side,
            quantity=permit.approved_qty,
            correlation_id=cid,
        )

        if order_result["status"] == "FILLED":
            record.executed = True
            record.outcome = DecisionOutcome.SIGNAL_APPROVED.value
            record.order_side = order_side.value
            record.fill_price = Decimal(str(order_result["filled_price"]))
            record.fill_qty = Decimal(str(order_result["filled_quantity"]))
            position_open = True
            position_entry_bar = i
            position_entry_price = record.fill_price
            position_side = order_side.value
            position_record_idx = len(decision_records)
        else:
            record.outcome = DecisionOutcome.SKIPPED.value

        record.row_hash = record.compute_hash()
        decision_records.append(record)

    # Close any remaining open position
    if position_open and position_record_idx >= 0:
        last_price = candles[-1].close
        price_diff = last_price - position_entry_price
        if position_side == "SELL":
            price_diff = -price_diff
        pnl = (price_diff * decision_records[position_record_idx].fill_qty).quantize(
            PRECISION_ZAR, rounding=ROUND_HALF_EVEN
        )
        decision_records[position_record_idx].exit_price = last_price
        decision_records[position_record_idx].realized_pnl_zar = pnl
        decision_records[position_record_idx].bars_held = len(candles) - 1 - position_entry_bar
        decision_records[position_record_idx].trade_outcome = "WIN" if pnl > ZERO else "LOSS"
        executed_trades.append(
            {
                "entry_bar": position_entry_bar,
                "exit_bar": len(candles) - 1,
                "side": position_side,
                "entry_price": str(position_entry_price),
                "exit_price": str(last_price),
                "pnl_zar": str(pnl),
                "bars_held": len(candles) - 1 - position_entry_bar,
                "outcome": "WIN" if pnl > ZERO else "LOSS",
            }
        )

    return decision_records, executed_trades


def determine_verdict(
    alpha_metrics: TradingMetrics,
    random_metrics: TradingMetrics,
    ema_metrics: TradingMetrics,
    diagnosis: EdgeDiagnosis,
) -> Tuple[str, List[str]]:
    """Determine final verdict with evidence."""
    evidence: List[str] = []

    beats_random = alpha_metrics.total_pnl_zar > random_metrics.total_pnl_zar
    evidence.append(
        "Q1 Beats random? "
        + ("YES" if beats_random else "NO")
        + " "
        + "(Alpha PnL=R"
        + str(alpha_metrics.total_pnl_zar)
        + " vs Random PnL=R"
        + str(random_metrics.total_pnl_zar)
        + ")"
    )

    beats_ema = alpha_metrics.total_pnl_zar > ema_metrics.total_pnl_zar
    evidence.append(
        "Q2 Beats EMA crossover? "
        + ("YES" if beats_ema else "NO")
        + " "
        + "(Alpha PnL=R"
        + str(alpha_metrics.total_pnl_zar)
        + " vs EMA PnL=R"
        + str(ema_metrics.total_pnl_zar)
        + ")"
    )

    positive_wr = alpha_metrics.win_rate > Decimal("50")
    evidence.append(
        "Q3 Win rate > 50%? "
        + ("YES" if positive_wr else "NO")
        + " "
        + "(Win rate="
        + str(alpha_metrics.win_rate)
        + "%)"
    )

    positive_pf = alpha_metrics.profit_factor > ONE
    evidence.append(
        "Q4 Profit factor > 1.0? "
        + ("YES" if positive_pf else "NO")
        + " "
        + "(Profit factor="
        + str(alpha_metrics.profit_factor)
        + ")"
    )

    dd_ok = alpha_metrics.max_drawdown_pct < Decimal("15")
    evidence.append(
        "Q5 Max drawdown < 15%? "
        + ("YES" if dd_ok else "NO")
        + " "
        + "(Max DD="
        + str(alpha_metrics.max_drawdown_pct)
        + "%)"
    )

    sufficient_trades = alpha_metrics.total_trades >= 10
    evidence.append(
        "Q6 Sufficient trades (>= 10)? "
        + ("YES" if sufficient_trades else "NO")
        + " "
        + "(Trades="
        + str(alpha_metrics.total_trades)
        + ")"
    )

    passing = sum([beats_random, beats_ema, positive_wr, positive_pf, dd_ok, sufficient_trades])

    if passing >= 5 and beats_random and positive_pf:
        verdict = "ALPHA EVIDENCE FOUND"
    elif passing <= 2 or (not beats_random and not positive_pf):
        verdict = "NO ALPHA EVIDENCE YET"
    else:
        verdict = "INCONCLUSIVE"

    return verdict, evidence

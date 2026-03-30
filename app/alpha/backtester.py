"""
Project Autonomous Alpha — Phase 10: Backtesting Engine

Reliability Level: SOVEREIGN TIER
Spec: SECTION G — Vectorized backtesting

MUST produce:
- Win rate
- Max drawdown
- Sharpe ratio
- Trade count
- Profit factor

NO strategy proceeds without backtest validation.
Custom vectorized engine (no external backtesting library required).
"""

from __future__ import annotations

import logging
import math
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Any, Dict, List

from app.alpha.models import BacktestResult

logger = logging.getLogger(__name__)

# ── Numpy availability ───────────────────────────────────────────────────────
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
# VECTORIZED BACKTEST
# =============================================================================


def run_backtest(
    close_prices: Any,
    predictions: Any,
    timestamps: Any,
    symbol: str,
    correlation_id: str,
    probability_threshold: float = 0.70,
    take_profit_pct: float = 0.02,
    stop_loss_pct: float = 0.01,
    max_drawdown_limit: float = 0.15,
) -> BacktestResult:
    """
    Vectorized backtest of probability-based predictions against historical prices.

    Strategy:
    - Enter LONG when probability_up > threshold
    - Enter SHORT when probability_down > threshold (1 - prob_up)
    - Exit at take_profit or stop_loss (whichever hit first)
    - If neither hit within 5 bars, exit at market

    Parameters:
        close_prices: numpy array of close prices
        predictions: numpy array of probability_up values (0-1)
        timestamps: numpy array of timestamps
        symbol: trading pair
        correlation_id: tracing ID
        probability_threshold: minimum probability to enter (default 0.70)
        take_profit_pct: take profit as fraction (default 0.02 = 2%)
        stop_loss_pct: stop loss as fraction (default 0.01 = 1%)

    Returns:
        BacktestResult with performance metrics
    """
    if not NUMPY_AVAILABLE:
        raise RuntimeError(
            f"SEC-ALPHA-030 numpy not available. correlation_id={correlation_id}"
        )

    prices = np.array(close_prices, dtype=np.float64)
    preds = np.array(predictions, dtype=np.float64)
    n = len(prices)

    if n < 50:
        raise ValueError(
            f"SEC-ALPHA-031 Insufficient data for backtest: {n}. "
            f"correlation_id={correlation_id}"
        )

    # Track trades
    trades: List[Dict[str, float]] = []
    equity_curve = [1.0]  # Start with normalized equity of 1.0

    i = 0
    max_hold = 5  # Maximum bars to hold

    while i < n - max_hold - 1:
        prob_up = preds[i]
        prob_down = 1.0 - prob_up

        entry_price = prices[i]

        if prob_up >= probability_threshold:
            # LONG entry
            direction = 1.0
        elif prob_down >= probability_threshold:
            # SHORT entry
            direction = -1.0
        else:
            i += 1
            continue

        # Simulate trade with TP/SL
        trade_return = 0.0
        exit_bar = i + max_hold  # Default: exit at max_hold

        for j in range(i + 1, min(i + max_hold + 1, n)):
            pnl = direction * (prices[j] - entry_price) / entry_price

            if pnl >= take_profit_pct:
                trade_return = take_profit_pct
                exit_bar = j
                break
            elif pnl <= -stop_loss_pct:
                trade_return = -stop_loss_pct
                exit_bar = j
                break
            elif j == min(i + max_hold, n - 1):
                trade_return = pnl
                exit_bar = j
                break

        trades.append(
            {
                "entry_bar": float(i),
                "exit_bar": float(exit_bar),
                "entry_price": entry_price,
                "direction": direction,
                "return": trade_return,
            }
        )

        equity_curve.append(equity_curve[-1] * (1.0 + trade_return))
        # Design Challenge R3: drawdown circuit breaker
        peak = max(equity_curve)
        current_dd = (peak - equity_curve[-1]) / peak
        if current_dd >= max_drawdown_limit:
            logger.warning(
                "SEC-ALPHA-032 Drawdown limit hit: %.2f%% >= %.2f%%. "
                "Halting backtest. correlation_id=%s",
                current_dd * 100,
                max_drawdown_limit * 100,
                correlation_id,
            )
            break
        i = exit_bar + 1  # Next entry after exit

    # ── Compute metrics ──────────────────────────────────────────────────
    if not trades:
        return BacktestResult(
            symbol=symbol,
            total_trades=0,
            win_count=0,
            loss_count=0,
            win_rate=Decimal("0"),
            max_drawdown_pct=Decimal("0"),
            sharpe_ratio=Decimal("0"),
            profit_factor=Decimal("0"),
            total_return_pct=Decimal("0"),
            avg_trade_return_pct=Decimal("0"),
            period_start=str(timestamps[0]) if len(timestamps) > 0 else "",
            period_end=str(timestamps[-1]) if len(timestamps) > 0 else "",
        )

    returns = np.array([t["return"] for t in trades])
    total_trades = len(trades)
    wins = returns[returns > 0]
    losses = returns[returns <= 0]
    win_count = len(wins)
    loss_count = len(losses)

    win_rate = win_count / total_trades if total_trades > 0 else 0.0

    # Max drawdown
    eq = np.array(equity_curve)
    peak = np.maximum.accumulate(eq)
    drawdown = (eq - peak) / peak
    max_dd = float(abs(drawdown.min()))

    # Sharpe ratio (annualized, assuming 1h candles ≈ 8760 periods/year)
    if len(returns) > 1 and np.std(returns) > 0:
        sharpe = (np.mean(returns) / np.std(returns)) * math.sqrt(
            min(len(returns), 252)
        )
    else:
        sharpe = 0.0

    # Profit factor — Design Challenge R3: always use Decimal
    gross_profit = float(wins.sum()) if len(wins) > 0 else 0.0
    gross_loss = float(abs(losses.sum())) if len(losses) > 0 else 0.0
    if gross_loss > 0:
        profit_factor = _to_dec(gross_profit / gross_loss)
    elif gross_profit > 0:
        profit_factor = Decimal("999")
    else:
        profit_factor = Decimal("0")

    total_return = float(equity_curve[-1] / equity_curve[0] - 1.0)
    avg_return = float(np.mean(returns))

    ts_list = list(timestamps) if timestamps is not None else []

    return BacktestResult(
        symbol=symbol,
        total_trades=total_trades,
        win_count=win_count,
        loss_count=loss_count,
        win_rate=_to_dec(win_rate),
        max_drawdown_pct=_to_dec(max_dd),
        sharpe_ratio=_to_dec(sharpe),
        profit_factor=profit_factor,
        total_return_pct=_to_dec(total_return),
        avg_trade_return_pct=_to_dec(avg_return),
        period_start=str(ts_list[0]) if ts_list else "",
        period_end=str(ts_list[-1]) if ts_list else "",
    )

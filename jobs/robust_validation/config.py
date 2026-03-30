"""
Phase 14 — Configuration: parameter grids, acceptance gates, constants.

All financial values use ``decimal.Decimal``.  No floats.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import List

# ---------------------------------------------------------------------------
# Decimal helpers
# ---------------------------------------------------------------------------
ZERO = Decimal("0")
ONE = Decimal("1")
HUNDRED = Decimal("100")
PRECISION = Decimal("0.01")
PRECISION_4 = Decimal("0.0001")


# ---------------------------------------------------------------------------
# Parameter Grid
# ---------------------------------------------------------------------------
THRESHOLDS: List[Decimal] = [
    Decimal("0.55"),
    Decimal("0.60"),
    Decimal("0.65"),
    Decimal("0.70"),
    Decimal("0.75"),
]

SEED_COUNTS: List[int] = [50, 100, 200]

WALK_FORWARD_WINDOWS: List[int] = [10, 20, 30]

HYSTERESIS_BAND: Decimal = Decimal("0.05")

PERSISTENCE_BARS: List[int] = [3, 5, 10]

ADX_THRESHOLDS: List[int] = [20, 25, 30]

ATR_MULTIPLIERS: List[Decimal] = [
    Decimal("1.5"),
    Decimal("2.0"),
    Decimal("2.5"),
    Decimal("3.0"),
]

NUM_CANDLES: int = 500

INITIAL_EQUITY_ZAR: Decimal = Decimal("100000")

MAX_BARS_HOLD: int = 5


# ---------------------------------------------------------------------------
# Three-tier seed splits
# ---------------------------------------------------------------------------
CALIBRATION_SEEDS: range = range(1, 51)      # seeds 1-50
SELECTION_SEEDS: range = range(51, 101)       # seeds 51-100
HOLDOUT_SEEDS: range = range(101, 201)        # seeds 101-200


# ---------------------------------------------------------------------------
# Acceptance Gates (hard constraints)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class AcceptanceGates:
    """Hard constraints — any breach triggers FREEZE DENIED."""

    min_strict_trades: int = 53
    min_profitable_rate: Decimal = Decimal("0.65")
    max_zero_trade_rate: Decimal = Decimal("0.35")
    min_walk_forward_trades_per_window: int = 3
    min_profit_factor: Decimal = Decimal("1.05")
    max_drawdown_pct: Decimal = Decimal("15.00")
    max_ranging_trades: int = 0  # absolute zero
    bootstrap_ci_alpha: Decimal = Decimal("0.05")  # 95 % CI


GATES = AcceptanceGates()


# ---------------------------------------------------------------------------
# Run Result
# ---------------------------------------------------------------------------
@dataclass
class RunResult:
    """Immutable record of a single simulation run."""

    seed: int
    window_label: str
    mode: str  # HYPO | STRICT
    threshold: Decimal
    trades: int = 0
    wins: int = 0
    win_rate: Decimal = ZERO
    total_pnl: Decimal = ZERO
    profit_factor: Decimal = ZERO
    max_drawdown_pct: Decimal = ZERO
    expectancy: Decimal = ZERO
    trending_trades: int = 0
    ranging_trades: int = 0
    correlation_id: str = ""

    @property
    def is_profitable(self) -> bool:
        return self.total_pnl > ZERO and self.profit_factor >= GATES.min_profit_factor

    @property
    def is_zero_trade(self) -> bool:
        return self.mode == "STRICT" and self.trades == 0


# ---------------------------------------------------------------------------
# Stress-test configuration
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class StressScenario:
    """One adversarial scenario for stress testing."""

    name: str
    description: str
    atr_multiplier: Decimal = ONE
    missing_data_pct: Decimal = ZERO
    regime_flip_every_n: int = 0
    latency_spike_ms: int = 0


STRESS_SCENARIOS: List[StressScenario] = [
    StressScenario(
        name="regime_flip_fast",
        description="Regime flips every 20 bars",
        regime_flip_every_n=20,
    ),
    StressScenario(
        name="regime_flip_slow",
        description="Regime flips every 100 bars",
        regime_flip_every_n=100,
    ),
    StressScenario(
        name="vol_shock_1_5x",
        description="ATR multiplied by 1.5",
        atr_multiplier=Decimal("1.5"),
    ),
    StressScenario(
        name="vol_shock_2x",
        description="ATR multiplied by 2.0",
        atr_multiplier=Decimal("2.0"),
    ),
    StressScenario(
        name="vol_shock_3x",
        description="ATR multiplied by 3.0",
        atr_multiplier=Decimal("3.0"),
    ),
    StressScenario(
        name="missing_5pct",
        description="5 percent of candles have missing data",
        missing_data_pct=Decimal("0.05"),
    ),
    StressScenario(
        name="missing_15pct",
        description="15 percent of candles have missing data",
        missing_data_pct=Decimal("0.15"),
    ),
    StressScenario(
        name="latency_500ms",
        description="Simulated 500ms latency on every candle",
        latency_spike_ms=500,
    ),
]

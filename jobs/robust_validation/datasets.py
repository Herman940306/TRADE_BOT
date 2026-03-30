"""
Phase 14 — Dataset generation: synthetic, stress-modified, walk-forward splits.

Delegates to ``jobs.validation.simulation.generate_synthetic_ohlcv`` for
baseline data, then applies stress overlays when requested.
All currency values use ``decimal.Decimal``.
"""

from __future__ import annotations

import copy
import importlib.util
import os
import random
import sys
from decimal import ROUND_HALF_EVEN, Decimal
from typing import List, Tuple

# ---------------------------------------------------------------------------
# Import simulation module using importlib to avoid circular-import issues
# ---------------------------------------------------------------------------
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

sys.modules.setdefault("jobs.validation", type(sys)("jobs.validation"))
sys.modules["jobs.validation"].__path__ = [os.path.join(_PROJECT_ROOT, "jobs", "validation")]
sys.modules["jobs.validation"].__package__ = "jobs.validation"

_sim_spec = importlib.util.spec_from_file_location(
    "jobs.validation.simulation",
    os.path.join(_PROJECT_ROOT, "jobs", "validation", "simulation.py"),
)
_sim_mod = importlib.util.module_from_spec(_sim_spec)
sys.modules["jobs.validation.simulation"] = _sim_mod
_sim_spec.loader.exec_module(_sim_mod)

generate_synthetic_ohlcv = _sim_mod.generate_synthetic_ohlcv
SyntheticCandle = _sim_mod.SyntheticCandle

from jobs.robust_validation.config import (
    NUM_CANDLES,
    ONE,
    ZERO,
    StressScenario,
)

PRECISION_PRICE = Decimal("0.00000001")


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------

def make_candles(seed: int, num_candles: int = NUM_CANDLES, correlation_id: str = "") -> List:
    """Generate baseline synthetic candles for a given seed."""
    cid = correlation_id or ("synth-seed-" + str(seed))
    return generate_synthetic_ohlcv(num_candles=num_candles, seed=seed, correlation_id=cid)


def apply_stress_overlay(
    candles: List,
    scenario: StressScenario,
    seed: int,
    correlation_id: str = "",
) -> List:
    """Return a copy of *candles* with the stress scenario applied.

    The original list is never mutated.
    """
    result = [copy.copy(c) for c in candles]
    rng = random.Random(seed)

    # ATR multiplier — scale high/low spread around close
    if scenario.atr_multiplier != ONE:
        for c in result:
            mid = c.close
            spread_high = (c.high - mid) * scenario.atr_multiplier
            spread_low = (mid - c.low) * scenario.atr_multiplier
            c.high = (mid + spread_high).quantize(PRECISION_PRICE, rounding=ROUND_HALF_EVEN)
            c.low = (mid - spread_low).quantize(PRECISION_PRICE, rounding=ROUND_HALF_EVEN)

    # Missing data — forward-fill with last known price (realistic:
    # real feeds repeat the last known value when data is missing).
    # Setting to ZERO would cause division-by-zero in feature extraction.
    if scenario.missing_data_pct > ZERO:
        n_missing = int(len(result) * float(scenario.missing_data_pct))
        # Only pick indices > 0 so we always have a prior candle to copy
        eligible = list(range(1, len(result)))
        indices = set(rng.sample(eligible, min(n_missing, len(eligible))))
        for idx in sorted(indices):
            prev = result[idx - 1]
            result[idx].open = prev.close
            result[idx].high = prev.close
            result[idx].low = prev.close
            result[idx].close = prev.close
            result[idx].volume = ZERO

    # Regime flips — inject trend reversals at fixed intervals
    if scenario.regime_flip_every_n > 0:
        direction = Decimal("1")
        drift = Decimal("0.002")
        for i in range(len(result)):
            if i > 0 and i % scenario.regime_flip_every_n == 0:
                direction = -direction
            bump = result[i].close * drift * direction
            result[i].close = (result[i].close + bump).quantize(
                PRECISION_PRICE, rounding=ROUND_HALF_EVEN
            )
            result[i].high = max(result[i].high, result[i].close)
            result[i].low = min(result[i].low, result[i].close)
            result[i].open = (result[i].open + bump / Decimal("2")).quantize(
                PRECISION_PRICE, rounding=ROUND_HALF_EVEN
            )

    return result


# ---------------------------------------------------------------------------
# Walk-forward split
# ---------------------------------------------------------------------------

def chronological_split(
    candles: List,
    n_windows: int,
    correlation_id: str = "",
) -> List[Tuple[str, List]]:
    """Split *candles* into *n_windows* chronological windows.

    Returns list of ``(label, candle_slice)`` tuples.
    Each window gets a roughly equal share of the data.
    """
    total = len(candles)
    window_size = total // n_windows
    windows: List[Tuple[str, List]] = []
    for w in range(n_windows):
        start = w * window_size
        end = start + window_size if w < n_windows - 1 else total
        label = "window_" + str(w + 1) + "_of_" + str(n_windows)
        windows.append((label, candles[start:end]))
    return windows

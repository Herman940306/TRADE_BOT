"""
Phase 14 — Sweeps: threshold × seed grid, walk-forward, stress-test runners.

All runners return ``List[RunResult]`` for downstream scoring.
Uses ``importlib.util`` import pattern for Python 3.14 compatibility.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from decimal import Decimal
from typing import Dict, List, Optional

# ---------------------------------------------------------------------------
# Import simulation module (same pattern as phase13_robustness.py)
# ---------------------------------------------------------------------------
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

sys.modules.setdefault("jobs.validation", type(sys)("jobs.validation"))
sys.modules["jobs.validation"].__path__ = [os.path.join(_PROJECT_ROOT, "jobs", "validation")]
sys.modules["jobs.validation"].__package__ = "jobs.validation"

if "jobs.validation.simulation" not in sys.modules:
    _sim_spec = importlib.util.spec_from_file_location(
        "jobs.validation.simulation",
        os.path.join(_PROJECT_ROOT, "jobs", "validation", "simulation.py"),
    )
    _sim_mod = importlib.util.module_from_spec(_sim_spec)
    sys.modules["jobs.validation.simulation"] = _sim_mod
    _sim_spec.loader.exec_module(_sim_mod)
else:
    _sim_mod = sys.modules["jobs.validation.simulation"]

generate_synthetic_ohlcv = _sim_mod.generate_synthetic_ohlcv
run_alpha_system = _sim_mod.run_alpha_system
compute_metrics = _sim_mod.compute_metrics

from jobs.robust_validation.config import (
    CALIBRATION_SEEDS,
    HOLDOUT_SEEDS,
    INITIAL_EQUITY_ZAR,
    NUM_CANDLES,
    SELECTION_SEEDS,
    STRESS_SCENARIOS,
    THRESHOLDS,
    RunResult,
    StressScenario,
)
from jobs.robust_validation.datasets import (
    apply_stress_overlay,
    chronological_split,
    make_candles,
)

# ---------------------------------------------------------------------------
# Single run helper
# ---------------------------------------------------------------------------

def _run_single(
    seed: int,
    threshold: Decimal,
    num_candles: int = NUM_CANDLES,
    window_label: str = "full",
    candles_override: Optional[List] = None,
    correlation_id: str = "",
) -> RunResult:
    """Execute one simulation run and return a ``RunResult``."""
    cid = correlation_id or ("p14-" + str(seed) + "-" + str(threshold))

    candles = candles_override if candles_override is not None else make_candles(seed, num_candles)

    # HYPO run — bypass confidence gate
    records_h, trades_h = run_alpha_system(
        candles, cid + "-HYPO", bypass_confidence_gate=True
    )
    metrics_h = compute_metrics("HYPO", trades_h, INITIAL_EQUITY_ZAR)

    # STRICT run — apply threshold
    records_s, trades_s = run_alpha_system(
        candles, cid + "-STRICT",
        bypass_confidence_gate=False,
        strict_threshold=threshold,
    )
    metrics_s = compute_metrics("STRICT", trades_s, INITIAL_EQUITY_ZAR)

    # Count regime trades from STRICT records
    trending = sum(1 for r in records_s if r.executed and r.regime == "TRENDING")
    ranging = sum(1 for r in records_s if r.executed and r.regime == "RANGING")

    return RunResult(
        seed=seed,
        window_label=window_label,
        mode="STRICT",
        threshold=threshold,
        trades=metrics_s.total_trades,
        wins=metrics_s.winning_trades,
        win_rate=metrics_s.win_rate,
        total_pnl=metrics_s.total_pnl_zar,
        profit_factor=metrics_s.profit_factor,
        max_drawdown_pct=metrics_s.max_drawdown_pct,
        expectancy=metrics_s.expectancy_zar,
        trending_trades=trending,
        ranging_trades=ranging,
        correlation_id=cid,
    )


# ---------------------------------------------------------------------------
# Threshold × seed sweep
# ---------------------------------------------------------------------------

def run_threshold_sweep(
    seeds: range,
    thresholds: Optional[List[Decimal]] = None,
    correlation_id: str = "",
    progress_callback=None,
) -> List[RunResult]:
    """Run every (seed, threshold) combination and collect results."""
    thresholds = thresholds or THRESHOLDS
    results: List[RunResult] = []
    total = len(seeds) * len(thresholds)
    done = 0

    for seed in seeds:
        for thr in thresholds:
            cid = correlation_id + "-sweep-s" + str(seed) + "-t" + str(thr)
            result = _run_single(seed, thr, correlation_id=cid)
            results.append(result)
            done += 1
            if progress_callback:
                progress_callback(done, total)

    return results


# ---------------------------------------------------------------------------
# Walk-forward
# ---------------------------------------------------------------------------

def run_walk_forward(
    seeds: range,
    n_windows: int = 10,
    threshold: Optional[Decimal] = None,
    correlation_id: str = "",
    progress_callback=None,
) -> List[RunResult]:
    """Chronological walk-forward over *n_windows* for each seed.

    Uses a longer candle series (NUM_CANDLES * 2) so each window still
    has enough bars for feature extraction (needs 200 warm-up).
    """
    threshold = threshold or Decimal("0.65")
    extended_candles = NUM_CANDLES * 2
    results: List[RunResult] = []
    total = len(seeds) * n_windows
    done = 0

    for seed in seeds:
        candles = make_candles(seed, extended_candles)
        windows = chronological_split(candles, n_windows, correlation_id=correlation_id)

        for label, window_candles in windows:
            cid = correlation_id + "-wf-s" + str(seed) + "-" + label
            result = _run_single(
                seed, threshold,
                candles_override=window_candles,
                window_label=label,
                correlation_id=cid,
            )
            results.append(result)
            done += 1
            if progress_callback:
                progress_callback(done, total)

    return results


# ---------------------------------------------------------------------------
# Three-tier validation
# ---------------------------------------------------------------------------

def run_three_tier(
    threshold: Decimal,
    correlation_id: str = "",
    progress_callback=None,
) -> Dict[str, List[RunResult]]:
    """Run calibration → selection → holdout pipeline for a threshold."""
    tiers: Dict[str, List[RunResult]] = {}

    tiers["calibration"] = run_threshold_sweep(
        CALIBRATION_SEEDS, [threshold],
        correlation_id=correlation_id + "-cal",
        progress_callback=progress_callback,
    )
    tiers["selection"] = run_threshold_sweep(
        SELECTION_SEEDS, [threshold],
        correlation_id=correlation_id + "-sel",
        progress_callback=progress_callback,
    )
    tiers["holdout"] = run_threshold_sweep(
        HOLDOUT_SEEDS, [threshold],
        correlation_id=correlation_id + "-hld",
        progress_callback=progress_callback,
    )
    return tiers


# ---------------------------------------------------------------------------
# Stress tests
# ---------------------------------------------------------------------------

def run_stress_tests(
    seeds: range,
    threshold: Decimal,
    scenarios: Optional[List[StressScenario]] = None,
    correlation_id: str = "",
    progress_callback=None,
) -> Dict[str, List[RunResult]]:
    """Run stress scenarios and collect results keyed by scenario name."""
    scenarios = scenarios or STRESS_SCENARIOS
    stress_results: Dict[str, List[RunResult]] = {}
    total = len(seeds) * len(scenarios)
    done = 0

    for scenario in scenarios:
        results: List[RunResult] = []
        for seed in seeds:
            candles = make_candles(seed)
            stressed = apply_stress_overlay(candles, scenario, seed, correlation_id)
            cid = correlation_id + "-stress-" + scenario.name + "-s" + str(seed)
            result = _run_single(
                seed, threshold,
                candles_override=stressed,
                window_label="stress_" + scenario.name,
                correlation_id=cid,
            )
            results.append(result)
            done += 1
            if progress_callback:
                progress_callback(done, total)

        stress_results[scenario.name] = results

    return stress_results

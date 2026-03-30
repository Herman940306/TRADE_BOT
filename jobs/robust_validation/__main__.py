"""
Phase 14 — Main runner: orchestrates the full validation loop.

Usage:
    python -m jobs.robust_validation                     # Full run (200 seeds)
    python -m jobs.robust_validation --quick              # Quick check (10 seeds)
    python -m jobs.robust_validation --calibration-only   # Calibration tier only

All financial values use ``decimal.Decimal``.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import sys
import time
from decimal import Decimal
from typing import List

# ---------------------------------------------------------------------------
# Ensure project root on path (same pattern as phase13_robustness.py)
# ---------------------------------------------------------------------------
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# Pre-register jobs.validation so dataclass resolution works on Python 3.14
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

from jobs.robust_validation.config import (
    CALIBRATION_SEEDS,
    HOLDOUT_SEEDS,
    SELECTION_SEEDS,
    THRESHOLDS,
    RunResult,
)
from jobs.robust_validation.evaluator import (
    FinalVerdict,
    SweepScore,
    decide_freeze,
    score_sweep,
    score_walk_forward,
)
from jobs.robust_validation.reports import (
    write_config_sweep_report,
    write_final_report,
    write_stress_csv,
    write_sweep_csv,
)
from jobs.robust_validation.safety import run_full_safety_audit
from jobs.robust_validation.sweeps import (
    run_stress_tests,
    run_threshold_sweep,
    run_walk_forward,
)

CID = "phase14-final"


def _progress(done: int, total: int) -> None:
    pct = done * 100 // total
    bar = "#" * (pct // 2) + "-" * (50 - pct // 2)
    sys.stdout.write("\r  [" + bar + "] " + str(pct) + "% (" + str(done) + "/" + str(total) + ")")
    sys.stdout.flush()


def main(quick: bool = False, calibration_only: bool = False) -> FinalVerdict:
    """Execute the full Phase 14 validation loop."""
    t0 = time.time()
    print("=" * 70)
    print("PHASE 14 — FINAL VALIDATION LOOP")
    print("=" * 70)
    print()

    # Determine seed range based on mode
    if quick:
        cal_seeds = range(1, 11)
        sel_seeds = range(51, 61)
        hld_seeds = range(101, 111)
        wf_seeds = range(1, 6)
        stress_seeds = range(1, 6)
        print("MODE: --quick (10 seeds per tier)")
    elif calibration_only:
        cal_seeds = CALIBRATION_SEEDS
        sel_seeds = range(0, 0)
        hld_seeds = range(0, 0)
        wf_seeds = range(1, 11)
        stress_seeds = range(1, 11)
        print("MODE: --calibration-only (50 calibration seeds)")
    else:
        cal_seeds = CALIBRATION_SEEDS
        sel_seeds = SELECTION_SEEDS
        hld_seeds = HOLDOUT_SEEDS
        wf_seeds = range(1, 21)
        stress_seeds = range(1, 21)
        print("MODE: Full (200 seeds total)")

    print()

    # -----------------------------------------------------------------------
    # Phase A+B: Threshold sweep on calibration seeds
    # -----------------------------------------------------------------------
    print("[A] Threshold sweep — calibration tier")
    cal_results = run_threshold_sweep(
        cal_seeds, THRESHOLDS, correlation_id=CID + "-cal", progress_callback=_progress,
    )
    print()
    print("  -> " + str(len(cal_results)) + " runs collected")

    sweep_scores: List[SweepScore] = []
    for thr in THRESHOLDS:
        sc = score_sweep(cal_results, thr, correlation_id=CID)
        sweep_scores.append(sc)
        status = "PASS" if sc.passes_all_gates else "FAIL"
        print(
            "  thr=" + str(thr)
            + "  runs=" + str(sc.total_runs)
            + "  profitable=" + str(sc.profitable_rate)
            + "  zero_trade=" + str(sc.zero_trade_rate)
            + "  trades=" + str(sc.total_strict_trades)
            + "  ranging=" + str(sc.ranging_trades)
            + "  -> " + status
        )

    passing_thresholds = [s.threshold for s in sweep_scores if s.passes_all_gates]
    print()
    print("  Passing thresholds: " + str(passing_thresholds if passing_thresholds else "NONE"))

    # -----------------------------------------------------------------------
    # Selection + holdout (if not calibration_only)
    # -----------------------------------------------------------------------
    sel_results: List[RunResult] = []
    hld_results: List[RunResult] = []

    if len(sel_seeds) > 0:
        print()
        print("[A] Threshold sweep — selection tier")
        sel_results = run_threshold_sweep(
            sel_seeds, THRESHOLDS, correlation_id=CID + "-sel", progress_callback=_progress,
        )
        print()
        print("  -> " + str(len(sel_results)) + " runs collected")

    if len(hld_seeds) > 0:
        print()
        print("[A] Threshold sweep — holdout tier")
        hld_results = run_threshold_sweep(
            hld_seeds, THRESHOLDS, correlation_id=CID + "-hld", progress_callback=_progress,
        )
        print()
        print("  -> " + str(len(hld_results)) + " runs collected")

    all_sweep = cal_results + sel_results + hld_results

    # Re-score with all data if holdout was run
    if hld_results:
        print()
        print("[B] Re-scoring with full dataset (" + str(len(all_sweep)) + " runs)")
        sweep_scores = []
        for thr in THRESHOLDS:
            sc = score_sweep(all_sweep, thr, correlation_id=CID)
            sweep_scores.append(sc)
            status = "PASS" if sc.passes_all_gates else "FAIL"
            print(
                "  thr=" + str(thr)
                + "  profitable=" + str(sc.profitable_rate)
                + "  zero_trade=" + str(sc.zero_trade_rate)
                + "  trades=" + str(sc.total_strict_trades)
                + "  -> " + status
            )

    # -----------------------------------------------------------------------
    # Phase C: Walk-forward
    # -----------------------------------------------------------------------
    print()
    best_thr = Decimal("0.65")
    if passing_thresholds:
        best_thr = passing_thresholds[0]

    print("[C] Walk-forward validation (threshold=" + str(best_thr) + ")")
    wf_results = run_walk_forward(
        wf_seeds, n_windows=10, threshold=best_thr,
        correlation_id=CID + "-wf", progress_callback=_progress,
    )
    print()
    wf_score = score_walk_forward(wf_results, correlation_id=CID)
    print(
        "  Windows: " + str(wf_score.n_windows)
        + "  Passing: " + str(wf_score.windows_with_enough_trades)
        + "  Min trades/window: " + str(wf_score.min_trades_per_window)
        + "  All pass: " + ("YES" if wf_score.all_windows_pass else "NO")
    )

    # -----------------------------------------------------------------------
    # Phase D: Stress tests
    # -----------------------------------------------------------------------
    print()
    print("[D] Stress tests (threshold=" + str(best_thr) + ")")
    stress_results = run_stress_tests(
        stress_seeds, best_thr, correlation_id=CID + "-stress",
        progress_callback=_progress,
    )
    print()
    stress_failures: List[str] = []
    for scenario_name, results in stress_results.items():
        ranging = sum(r.ranging_trades for r in results)
        if ranging > 0:
            stress_failures.append(
                scenario_name + ": " + str(ranging) + " RANGING trades executed"
            )
        total_trades = sum(r.trades for r in results)
        total_pnl = sum(r.total_pnl for r in results)
        print(
            "  " + scenario_name
            + ": trades=" + str(total_trades)
            + "  pnl=" + str(total_pnl.quantize(Decimal("0.01")))
            + "  ranging=" + str(ranging)
        )

    # -----------------------------------------------------------------------
    # Phase G: Safety audit
    # -----------------------------------------------------------------------
    print()
    print("[G] Safety verification")
    safety_failures = run_full_safety_audit(correlation_id=CID)
    if safety_failures:
        for sf in safety_failures:
            print("  FAIL: " + sf)
    else:
        print("  All safety checks passed.")

    # -----------------------------------------------------------------------
    # Freeze decision
    # -----------------------------------------------------------------------
    print()
    print("=" * 70)
    verdict = decide_freeze(
        sweep_scores, wf_score, stress_failures, safety_failures,
        correlation_id=CID,
    )

    print("VERDICT: " + verdict.decision)
    for ev in verdict.evidence:
        print("  " + ev)
    print()

    # -----------------------------------------------------------------------
    # Write reports + CSVs
    # -----------------------------------------------------------------------
    print("[H] Writing reports")
    csv_path = write_sweep_csv(all_sweep)
    print("  -> " + csv_path)

    stress_csv = write_stress_csv(stress_results)
    print("  -> " + stress_csv)

    config_rpt = write_config_sweep_report(sweep_scores)
    print("  -> " + config_rpt)

    final_rpt = write_final_report(
        verdict, all_sweep, wf_results, stress_results, safety_failures,
    )
    print("  -> " + final_rpt)

    elapsed = time.time() - t0
    print()
    print("Completed in " + str(int(elapsed)) + "s")
    print("=" * 70)

    return verdict


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Phase 14 Final Validation Loop")
    parser.add_argument("--quick", action="store_true", help="Quick run with 10 seeds")
    parser.add_argument(
        "--calibration-only", action="store_true", help="Calibration tier only"
    )
    args = parser.parse_args()
    result = main(quick=args.quick, calibration_only=args.calibration_only)
    sys.exit(0 if result.decision == "FREEZE APPROVED" else 1)

"""
Phase 14 — Evaluator: adversarial scoring, bootstrap CIs, acceptance checks.

Scores a batch of ``RunResult`` objects against the acceptance gates.
All financial values use ``decimal.Decimal``.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Dict, List, Optional, Tuple

from jobs.robust_validation.config import (
    GATES,
    ONE,
    PRECISION,
    ZERO,
    RunResult,
)

# ---------------------------------------------------------------------------
# Bootstrap confidence intervals
# ---------------------------------------------------------------------------

def bootstrap_ci(
    values: List[Decimal],
    n_boot: int = 1000,
    alpha: Decimal = Decimal("0.05"),
    seed: int = 42,
    correlation_id: str = "",
) -> Tuple[Decimal, Decimal, Decimal]:
    """Return (mean, lower_ci, upper_ci) for *values* at 1-alpha confidence.

    Uses the percentile method with ``n_boot`` resamples.
    """
    if not values:
        return ZERO, ZERO, ZERO

    rng = random.Random(seed)
    n = len(values)
    means: List[Decimal] = []

    for _ in range(n_boot):
        sample = [rng.choice(values) for _ in range(n)]
        mean = sum(sample) / Decimal(str(n))
        means.append(mean)

    means.sort()
    lo_idx = max(0, int(float(alpha / Decimal("2")) * n_boot) - 1)
    hi_idx = min(n_boot - 1, int(float(ONE - alpha / Decimal("2")) * n_boot))
    overall_mean = (sum(values) / Decimal(str(n))).quantize(PRECISION, rounding=ROUND_HALF_EVEN)
    lo = means[lo_idx].quantize(PRECISION, rounding=ROUND_HALF_EVEN)
    hi = means[hi_idx].quantize(PRECISION, rounding=ROUND_HALF_EVEN)
    return overall_mean, lo, hi


# ---------------------------------------------------------------------------
# Batch scoring
# ---------------------------------------------------------------------------

@dataclass
class SweepScore:
    """Aggregate score for one threshold across all seeds."""

    threshold: Decimal
    total_runs: int = 0
    profitable_runs: int = 0
    zero_trade_runs: int = 0
    total_strict_trades: int = 0
    ranging_trades: int = 0
    profitable_rate: Decimal = ZERO
    zero_trade_rate: Decimal = ZERO
    mean_pnl: Decimal = ZERO
    pnl_ci_lo: Decimal = ZERO
    pnl_ci_hi: Decimal = ZERO
    mean_win_rate: Decimal = ZERO
    mean_profit_factor: Decimal = ZERO
    mean_max_dd: Decimal = ZERO
    passes_all_gates: bool = False
    gate_failures: List[str] = field(default_factory=list)


def score_sweep(
    results: List[RunResult],
    threshold: Decimal,
    correlation_id: str = "",
) -> SweepScore:
    """Score a batch of runs for one threshold against acceptance gates."""
    strict = [r for r in results if r.mode == "STRICT" and r.threshold == threshold]

    sc = SweepScore(threshold=threshold, total_runs=len(strict))

    if not strict:
        sc.gate_failures.append("NO_RUNS")
        return sc

    sc.profitable_runs = sum(1 for r in strict if r.is_profitable)
    sc.zero_trade_runs = sum(1 for r in strict if r.is_zero_trade)
    sc.total_strict_trades = sum(r.trades for r in strict)
    sc.ranging_trades = sum(r.ranging_trades for r in strict)

    n = Decimal(str(sc.total_runs))
    sc.profitable_rate = (Decimal(str(sc.profitable_runs)) / n).quantize(
        PRECISION, rounding=ROUND_HALF_EVEN
    )
    sc.zero_trade_rate = (Decimal(str(sc.zero_trade_runs)) / n).quantize(
        PRECISION, rounding=ROUND_HALF_EVEN
    )

    pnls = [r.total_pnl for r in strict]
    sc.mean_pnl, sc.pnl_ci_lo, sc.pnl_ci_hi = bootstrap_ci(pnls, correlation_id=correlation_id)

    win_rates = [r.win_rate for r in strict if r.trades > 0]
    if win_rates:
        sc.mean_win_rate = (sum(win_rates) / Decimal(str(len(win_rates)))).quantize(
            PRECISION, rounding=ROUND_HALF_EVEN
        )

    pfs = [r.profit_factor for r in strict if r.trades > 0]
    if pfs:
        sc.mean_profit_factor = (sum(pfs) / Decimal(str(len(pfs)))).quantize(
            PRECISION, rounding=ROUND_HALF_EVEN
        )

    dds = [r.max_drawdown_pct for r in strict]
    if dds:
        sc.mean_max_dd = (sum(dds) / Decimal(str(len(dds)))).quantize(
            PRECISION, rounding=ROUND_HALF_EVEN
        )

    # Gate checks
    failures: List[str] = []

    if sc.total_strict_trades < GATES.min_strict_trades:
        failures.append(
            "STRICT_TRADES: " + str(sc.total_strict_trades) + " < " + str(GATES.min_strict_trades)
        )

    if sc.profitable_rate < GATES.min_profitable_rate:
        failures.append(
            "PROFITABLE_RATE: " + str(sc.profitable_rate) + " < " + str(GATES.min_profitable_rate)
        )

    if sc.zero_trade_rate > GATES.max_zero_trade_rate:
        failures.append(
            "ZERO_TRADE_RATE: " + str(sc.zero_trade_rate) + " > " + str(GATES.max_zero_trade_rate)
        )

    if sc.ranging_trades > GATES.max_ranging_trades:
        failures.append(
            "RANGING_TRADES: " + str(sc.ranging_trades) + " > " + str(GATES.max_ranging_trades)
        )

    sc.gate_failures = failures
    sc.passes_all_gates = len(failures) == 0
    return sc


# ---------------------------------------------------------------------------
# Walk-forward scoring
# ---------------------------------------------------------------------------

@dataclass
class WalkForwardScore:
    """Aggregate score for walk-forward windows."""

    n_windows: int = 0
    windows_with_enough_trades: int = 0
    min_trades_per_window: int = 0
    mean_pnl_per_window: Decimal = ZERO
    all_windows_pass: bool = False
    window_details: List[Dict] = field(default_factory=list)


def score_walk_forward(
    results: List[RunResult],
    min_trades: int = GATES.min_walk_forward_trades_per_window,
    correlation_id: str = "",
) -> WalkForwardScore:
    """Score walk-forward results ensuring every window has enough trades."""
    wf = WalkForwardScore()

    window_labels = sorted(set(r.window_label for r in results if r.window_label))
    wf.n_windows = len(window_labels)

    if wf.n_windows == 0:
        return wf

    min_tc = 999999
    total_pnl = ZERO

    for label in window_labels:
        subset = [r for r in results if r.window_label == label and r.mode == "STRICT"]
        trades = sum(r.trades for r in subset)
        pnl = sum(r.total_pnl for r in subset)
        passes = trades >= min_trades

        if trades < min_tc:
            min_tc = trades

        if passes:
            wf.windows_with_enough_trades += 1

        total_pnl += pnl
        wf.window_details.append({
            "window": label,
            "trades": trades,
            "pnl": str(pnl.quantize(PRECISION, rounding=ROUND_HALF_EVEN)),
            "passes": passes,
        })

    wf.min_trades_per_window = min_tc
    wf.mean_pnl_per_window = (total_pnl / Decimal(str(wf.n_windows))).quantize(
        PRECISION, rounding=ROUND_HALF_EVEN
    )
    wf.all_windows_pass = wf.windows_with_enough_trades == wf.n_windows
    return wf


# ---------------------------------------------------------------------------
# Final verdict
# ---------------------------------------------------------------------------

@dataclass
class FinalVerdict:
    """Aggregate verdict across all sweeps, walk-forward, stress."""

    decision: str = "FREEZE DENIED"
    best_threshold: Optional[Decimal] = None
    sweep_scores: List[SweepScore] = field(default_factory=list)
    walk_forward: Optional[WalkForwardScore] = None
    stress_failures: List[str] = field(default_factory=list)
    safety_failures: List[str] = field(default_factory=list)
    evidence: List[str] = field(default_factory=list)


def decide_freeze(
    sweep_scores: List[SweepScore],
    wf_score: Optional[WalkForwardScore],
    stress_failures: List[str],
    safety_failures: List[str],
    correlation_id: str = "",
) -> FinalVerdict:
    """FREEZE APPROVED only if at least one threshold passes all gates,
    walk-forward passes, zero stress failures, and zero safety failures."""

    v = FinalVerdict()
    v.sweep_scores = sweep_scores
    v.walk_forward = wf_score
    v.stress_failures = stress_failures
    v.safety_failures = safety_failures

    passing = [s for s in sweep_scores if s.passes_all_gates]

    if not passing:
        v.evidence.append("No threshold passes all acceptance gates.")
        return v

    # Pick threshold with highest profitable_rate among passing
    best = max(passing, key=lambda s: (s.profitable_rate, s.mean_pnl))
    v.best_threshold = best.threshold
    v.evidence.append(
        "Best threshold: " + str(best.threshold)
        + " (profitable_rate=" + str(best.profitable_rate)
        + ", mean_pnl=" + str(best.mean_pnl) + ")"
    )

    if wf_score and not wf_score.all_windows_pass:
        v.evidence.append(
            "Walk-forward FAILED: "
            + str(wf_score.windows_with_enough_trades) + "/" + str(wf_score.n_windows)
            + " windows pass min trades."
        )
        return v

    if stress_failures:
        v.evidence.append(
            "Stress FAILED: " + ", ".join(stress_failures)
        )
        return v

    if safety_failures:
        v.evidence.append(
            "Safety FAILED: " + ", ".join(safety_failures)
        )
        return v

    v.decision = "FREEZE APPROVED"
    v.evidence.append("All gates pass. Walk-forward OK. Stress OK. Safety OK.")
    return v

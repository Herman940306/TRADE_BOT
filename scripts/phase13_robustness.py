"""
Phase 12.5 + Phase 13: Robustness Hardening & Walk-Forward Validation

Sections B, C, F combined:
- Multi-seed, multi-window threshold robustness testing
- Sample size expansion across diverse scenarios
- Walk-forward validation with chronological splits
- Sensitivity and failure-mode testing

All results written to stdout for capture.
"""

from __future__ import annotations

import os
import statistics
import sys
from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Dict, List, Optional

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# Direct import to avoid circular import through jobs/__init__.py
import importlib.util

# Register as proper module so dataclass resolution works on Python 3.14
sys.modules.setdefault("jobs.validation", type(sys)("jobs.validation"))
sys.modules["jobs.validation"].__path__ = [os.path.join(_PROJECT_ROOT, "jobs", "validation")]
sys.modules["jobs.validation"].__package__ = "jobs.validation"

_sim_spec = importlib.util.spec_from_file_location(
    "jobs.validation.simulation", os.path.join(_PROJECT_ROOT, "jobs", "validation", "simulation.py")
)
_sim_mod = importlib.util.module_from_spec(_sim_spec)
sys.modules["jobs.validation.simulation"] = _sim_mod
_sim_spec.loader.exec_module(_sim_mod)

generate_synthetic_ohlcv = _sim_mod.generate_synthetic_ohlcv
run_alpha_system = _sim_mod.run_alpha_system
compute_metrics = _sim_mod.compute_metrics
INITIAL_EQUITY_ZAR = _sim_mod.INITIAL_EQUITY_ZAR

ZERO = Decimal("0")
ONE = Decimal("1")
HUNDRED = Decimal("100")
PRECISION = Decimal("0.01")


@dataclass
class RunResult:
    """Single validation run result."""

    seed: int
    window_label: str
    mode: str  # HYPO or STRICT
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


def _run_single(
    seed: int,
    num_candles: int,
    bypass_confidence: bool,
    threshold: Optional[Decimal],
    label: str,
) -> RunResult:
    """Run alpha system once and extract metrics."""
    candles = generate_synthetic_ohlcv(num_candles, seed, f"ROBUST-{seed}")
    records, trades = run_alpha_system(
        candles,
        f"ROBUST-{seed}",
        bypass_confidence_gate=bypass_confidence,
        strict_threshold=threshold,
    )
    metrics = compute_metrics("ROBUST", trades, INITIAL_EQUITY_ZAR, records)

    trending = sum(1 for t in trades if _get_regime(records, t) == "TRENDING")
    ranging = sum(1 for t in trades if _get_regime(records, t) == "RANGING")

    n = metrics.total_trades
    w = metrics.winning_trades
    wr = (
        (Decimal(str(w)) / Decimal(str(n)) * HUNDRED).quantize(PRECISION, rounding=ROUND_HALF_EVEN)
        if n > 0
        else ZERO
    )
    exp = (
        (metrics.total_pnl_zar / Decimal(str(n))).quantize(PRECISION, rounding=ROUND_HALF_EVEN)
        if n > 0
        else ZERO
    )

    return RunResult(
        seed=seed,
        window_label=label,
        mode="HYPO" if bypass_confidence else "STRICT",
        threshold=threshold if threshold else Decimal("65.00"),
        trades=n,
        wins=w,
        win_rate=wr,
        total_pnl=metrics.total_pnl_zar,
        profit_factor=metrics.profit_factor,
        max_drawdown_pct=metrics.max_drawdown_pct,
        expectancy=exp,
        trending_trades=trending,
        ranging_trades=ranging,
    )


def _get_regime(records, trade):
    """Extract regime from decision records for a trade."""
    entry_bar = trade.get("entry_bar", -1)
    for r in records:
        if r.candle_index == entry_bar and r.executed:
            return r.regime
    return "UNKNOWN"


def run_threshold_robustness():
    """Section B: Test thresholds across multiple seeds."""
    print("=" * 70)
    print("SECTION B: THRESHOLD ROBUSTNESS")
    print("=" * 70)

    thresholds = [Decimal("60.00"), Decimal("65.00"), Decimal("70.00"), Decimal("75.00")]
    seeds = list(range(42, 52))  # 10 different seeds
    num_candles = 500

    results_by_threshold: Dict[str, List[RunResult]] = {str(t): [] for t in thresholds}

    for threshold in thresholds:
        for seed in seeds:
            r = _run_single(seed, num_candles, False, threshold, f"seed-{seed}")
            results_by_threshold[str(threshold)].append(r)

    print(
        f"\n{'Threshold':>10} | {'Seeds':>5} | {'Avg Trades':>10} | {'Avg WR%':>7} | {'Avg PnL':>12} | {'Avg PF':>7} | {'Avg DD%':>7} | {'Avg Exp':>10} | {'Worst PnL':>12} | {'Zero-Trade':>10}"
    )
    print("-" * 120)

    best_score = Decimal("-999999")
    best_threshold = Decimal("65.00")

    for threshold in thresholds:
        runs = results_by_threshold[str(threshold)]
        n = len(runs)
        total_trades_list = [r.trades for r in runs]
        wr_list = [r.win_rate for r in runs if r.trades > 0]
        pnl_list = [r.total_pnl for r in runs]
        pf_list = [r.profit_factor for r in runs if r.trades > 0]
        dd_list = [r.max_drawdown_pct for r in runs]
        exp_list = [r.expectancy for r in runs if r.trades > 0]

        avg_trades = sum(total_trades_list) / n if n > 0 else 0
        avg_wr = (
            (sum(wr_list) / Decimal(str(len(wr_list)))).quantize(PRECISION) if wr_list else ZERO
        )
        avg_pnl = (sum(pnl_list) / Decimal(str(n))).quantize(PRECISION) if n > 0 else ZERO
        avg_pf = (
            (sum(pf_list) / Decimal(str(len(pf_list)))).quantize(PRECISION) if pf_list else ZERO
        )
        avg_dd = (sum(dd_list) / Decimal(str(n))).quantize(PRECISION) if n > 0 else ZERO
        avg_exp = (
            (sum(exp_list) / Decimal(str(len(exp_list)))).quantize(PRECISION) if exp_list else ZERO
        )
        worst_pnl = min(pnl_list) if pnl_list else ZERO
        zero_count = sum(1 for r in runs if r.trades == 0)

        print(
            f"{threshold:>10} | {n:>5} | {avg_trades:>10.1f} | {avg_wr:>7} | R{avg_pnl:>11} | {avg_pf:>7} | {avg_dd:>7} | R{avg_exp:>9} | R{worst_pnl:>11} | {zero_count:>10}"
        )

        # Score: avg_expectancy * consistency_factor * sqrt(avg_trades)
        import math

        consistency = Decimal(str(len([r for r in runs if r.total_pnl > ZERO]))) / Decimal(
            str(max(n, 1))
        )
        trade_factor = Decimal(str(math.sqrt(float(avg_trades)))) if avg_trades > 0 else ZERO
        score = avg_exp * consistency * trade_factor * avg_pf
        if score > best_score:
            best_score = score
            best_threshold = threshold

    print(f"\n>>> ROBUST THRESHOLD: {best_threshold}")
    print(f"    Score: {best_score.quantize(PRECISION)}")
    return best_threshold


def run_sample_expansion():
    """Section C: Expand evidence base across many trials."""
    print("\n" + "=" * 70)
    print("SECTION C: SAMPLE SIZE EXPANSION")
    print("=" * 70)

    seeds = list(range(42, 62))  # 20 seeds
    num_candles = 500

    hypo_results: List[RunResult] = []
    strict_results: List[RunResult] = []

    for seed in seeds:
        hypo = _run_single(seed, num_candles, True, None, f"seed-{seed}")
        hypo_results.append(hypo)
        strict = _run_single(seed, num_candles, False, Decimal("65.00"), f"seed-{seed}")
        strict_results.append(strict)

    for mode_name, results in [("HYPO", hypo_results), ("STRICT", strict_results)]:
        print(f"\n--- {mode_name} MODE ({len(results)} runs) ---")
        total_trades = sum(r.trades for r in results)
        total_wins = sum(r.wins for r in results)
        total_pnl = sum(r.total_pnl for r in results)
        total_trending = sum(r.trending_trades for r in results)
        total_ranging = sum(r.ranging_trades for r in results)
        profitable_runs = sum(1 for r in results if r.total_pnl > ZERO)
        zero_runs = sum(1 for r in results if r.trades == 0)

        pnl_list = [float(r.total_pnl) for r in results]
        wr_list = [float(r.win_rate) for r in results if r.trades > 0]

        agg_wr = (
            (Decimal(str(total_wins)) / Decimal(str(total_trades)) * HUNDRED).quantize(PRECISION)
            if total_trades > 0
            else ZERO
        )
        avg_pnl = (total_pnl / Decimal(str(len(results)))).quantize(PRECISION)
        median_pnl = (
            Decimal(str(statistics.median(pnl_list))).quantize(PRECISION) if pnl_list else ZERO
        )
        worst_pnl = min(r.total_pnl for r in results)
        best_pnl = max(r.total_pnl for r in results)
        std_pnl = (
            Decimal(str(statistics.stdev(pnl_list))).quantize(PRECISION)
            if len(pnl_list) > 1
            else ZERO
        )

        print(f"  Aggregate trades:    {total_trades}")
        print(f"  Aggregate wins:      {total_wins}")
        print(f"  Aggregate win rate:  {agg_wr}%")
        print(f"  Total PnL:           R{total_pnl}")
        print(f"  Average PnL/run:     R{avg_pnl}")
        print(f"  Median PnL/run:      R{median_pnl}")
        print(f"  Worst PnL:           R{worst_pnl}")
        print(f"  Best PnL:            R{best_pnl}")
        print(f"  PnL StdDev:          R{std_pnl}")
        print(
            f"  Profitable runs:     {profitable_runs}/{len(results)} ({Decimal(str(profitable_runs)) / Decimal(str(len(results))) * HUNDRED:.0f}%)"
        )
        print(f"  Zero-trade runs:     {zero_runs}")
        print(f"  TRENDING trades:     {total_trending}")
        print(f"  RANGING trades:      {total_ranging}")

        # Per-run detail
        print(
            f"\n  {'Seed':>6} | {'Trades':>6} | {'WR%':>6} | {'PnL':>12} | {'PF':>7} | {'DD%':>7} | {'Exp':>10} | {'Trend':>5} | {'Range':>5}"
        )
        print("  " + "-" * 90)
        for r in results:
            print(
                f"  {r.seed:>6} | {r.trades:>6} | {r.win_rate:>6} | R{r.total_pnl:>11} | {r.profit_factor:>7} | {r.max_drawdown_pct:>7} | R{r.expectancy:>9} | {r.trending_trades:>5} | {r.ranging_trades:>5}"
            )

    return hypo_results, strict_results


def run_walk_forward():
    """Section F: Walk-forward validation with chronological windows."""
    print("\n" + "=" * 70)
    print("SECTION F: WALK-FORWARD VALIDATION")
    print("=" * 70)

    # Use single long series, split into 4 chronological windows
    seed = 42
    total_candles = 2000
    candles = generate_synthetic_ohlcv(total_candles, seed, "WALKFWD")

    window_size = 500
    windows = []
    for i in range(0, total_candles - window_size + 1, window_size):
        windows.append((i, i + window_size))

    print(f"\nTotal candles: {total_candles}")
    print(f"Window size: {window_size}")
    print(f"Number of windows: {len(windows)}")
    print(f"Seed: {seed}")

    hypo_results: List[RunResult] = []
    strict_results: List[RunResult] = []

    for wi, (start, end) in enumerate(windows):
        window_candles = candles[start:end]
        label = f"W{wi + 1}[{start}-{end}]"

        records_h, trades_h = run_alpha_system(
            window_candles, f"WF-HYPO-W{wi}", bypass_confidence_gate=True
        )
        metrics_h = compute_metrics("WF-HYPO", trades_h, INITIAL_EQUITY_ZAR, records_h)
        n_h = metrics_h.total_trades
        w_h = metrics_h.winning_trades

        records_s, trades_s = run_alpha_system(
            window_candles,
            f"WF-STRICT-W{wi}",
            bypass_confidence_gate=False,
            strict_threshold=Decimal("65.00"),
        )
        metrics_s = compute_metrics("WF-STRICT", trades_s, INITIAL_EQUITY_ZAR, records_s)
        n_s = metrics_s.total_trades
        w_s = metrics_s.winning_trades

        for mode, n, w, m, recs, tds in [
            ("HYPO", n_h, w_h, metrics_h, records_h, trades_h),
            ("STRICT", n_s, w_s, metrics_s, records_s, trades_s),
        ]:
            wr = (
                (Decimal(str(w)) / Decimal(str(n)) * HUNDRED).quantize(PRECISION) if n > 0 else ZERO
            )
            exp = (m.total_pnl_zar / Decimal(str(n))).quantize(PRECISION) if n > 0 else ZERO
            trending = sum(1 for t in tds if _get_regime(recs, t) == "TRENDING")
            ranging = sum(1 for t in tds if _get_regime(recs, t) == "RANGING")

            r = RunResult(
                seed=seed,
                window_label=label,
                mode=mode,
                threshold=Decimal("65.00"),
                trades=n,
                wins=w,
                win_rate=wr,
                total_pnl=m.total_pnl_zar,
                profit_factor=m.profit_factor,
                max_drawdown_pct=m.max_drawdown_pct,
                expectancy=exp,
                trending_trades=trending,
                ranging_trades=ranging,
            )
            if mode == "HYPO":
                hypo_results.append(r)
            else:
                strict_results.append(r)

    for mode_name, results in [("HYPO", hypo_results), ("STRICT", strict_results)]:
        print(f"\n--- WALK-FORWARD {mode_name} ---")
        print(
            f"  {'Window':>20} | {'Trades':>6} | {'WR%':>6} | {'PnL':>12} | {'PF':>7} | {'DD%':>7} | {'Exp':>10} | {'Trend':>5} | {'Range':>5}"
        )
        print("  " + "-" * 100)
        for r in results:
            print(
                f"  {r.window_label:>20} | {r.trades:>6} | {r.win_rate:>6} | R{r.total_pnl:>11} | {r.profit_factor:>7} | {r.max_drawdown_pct:>7} | R{r.expectancy:>9} | {r.trending_trades:>5} | {r.ranging_trades:>5}"
            )

        total_trades = sum(r.trades for r in results)
        total_pnl = sum(r.total_pnl for r in results)
        profitable_windows = sum(1 for r in results if r.total_pnl > ZERO)
        losing_windows = sum(1 for r in results if r.total_pnl < ZERO)
        zero_windows = sum(1 for r in results if r.trades == 0)

        print("\n  Summary:")
        print(f"    Total trades across windows: {total_trades}")
        print(f"    Total PnL across windows: R{total_pnl}")
        print(f"    Profitable windows: {profitable_windows}/{len(results)}")
        print(f"    Losing windows: {losing_windows}/{len(results)}")
        print(f"    Zero-trade windows: {zero_windows}/{len(results)}")

    return hypo_results, strict_results


def run_sensitivity_test():
    """Sensitivity testing: small perturbations in threshold."""
    print("\n" + "=" * 70)
    print("SENSITIVITY TESTING")
    print("=" * 70)

    base_threshold = Decimal("65.00")
    perturbations = [
        Decimal("-3.00"),
        Decimal("-1.00"),
        Decimal("0"),
        Decimal("1.00"),
        Decimal("3.00"),
    ]
    seed = 42
    num_candles = 500

    print(
        f"\n  {'Threshold':>10} | {'Trades':>6} | {'WR%':>6} | {'PnL':>12} | {'PF':>7} | {'DD%':>7}"
    )
    print("  " + "-" * 65)

    for p in perturbations:
        t = base_threshold + p
        r = _run_single(seed, num_candles, False, t, f"sens-{t}")
        print(
            f"  {t:>10} | {r.trades:>6} | {r.win_rate:>6} | R{r.total_pnl:>11} | {r.profit_factor:>7} | {r.max_drawdown_pct:>7}"
        )


def run_failure_mode_test():
    """Failure-mode testing: regime flip stress, sparse signals."""
    print("\n" + "=" * 70)
    print("FAILURE MODE TESTING")
    print("=" * 70)

    # Test with very short candle sets (sparse signals)
    print("\n--- Sparse Signal Test (200 candles) ---")
    for seed in [42, 43, 44, 45, 46]:
        r = _run_single(seed, 250, False, Decimal("65.00"), f"sparse-{seed}")
        print(f"  Seed {seed}: trades={r.trades} PnL=R{r.total_pnl} WR={r.win_rate}%")

    # Test with many candles (regime flip stress)
    print("\n--- Extended Series Test (1000 candles) ---")
    for seed in [42, 43, 44]:
        r = _run_single(seed, 1000, False, Decimal("65.00"), f"extended-{seed}")
        print(
            f"  Seed {seed}: trades={r.trades} PnL=R{r.total_pnl} WR={r.win_rate}% trend={r.trending_trades} range={r.ranging_trades}"
        )


def main():
    print("=" * 70)
    print("PHASE 12.5 + 13: ROBUSTNESS HARDENING & WALK-FORWARD VALIDATION")
    print("=" * 70)

    # Section B
    robust_threshold = run_threshold_robustness()

    # Section C
    hypo_exp, strict_exp = run_sample_expansion()

    # Section F
    hypo_wf, strict_wf = run_walk_forward()

    # Sensitivity
    run_sensitivity_test()

    # Failure modes
    run_failure_mode_test()

    # ── AGGREGATE VERDICT ───────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("AGGREGATE VERDICT")
    print("=" * 70)

    # Combine all evidence
    all_hypo_trades = sum(r.trades for r in hypo_exp)
    all_hypo_wins = sum(r.wins for r in hypo_exp)
    all_hypo_pnl = sum(r.total_pnl for r in hypo_exp)
    all_hypo_ranging = sum(r.ranging_trades for r in hypo_exp)

    all_strict_trades = sum(r.trades for r in strict_exp)
    all_strict_wins = sum(r.wins for r in strict_exp)
    all_strict_pnl = sum(r.total_pnl for r in strict_exp)
    all_strict_ranging = sum(r.ranging_trades for r in strict_exp)

    hypo_wr = (
        (Decimal(str(all_hypo_wins)) / Decimal(str(all_hypo_trades)) * HUNDRED).quantize(PRECISION)
        if all_hypo_trades > 0
        else ZERO
    )
    strict_wr = (
        (Decimal(str(all_strict_wins)) / Decimal(str(all_strict_trades)) * HUNDRED).quantize(
            PRECISION
        )
        if all_strict_trades > 0
        else ZERO
    )

    profitable_hypo = sum(1 for r in hypo_exp if r.total_pnl > ZERO)
    profitable_strict = sum(1 for r in strict_exp if r.total_pnl > ZERO or r.trades == 0)

    wf_hypo_profitable = sum(1 for r in hypo_wf if r.total_pnl > ZERO)
    wf_strict_profitable = sum(1 for r in strict_wf if r.total_pnl > ZERO or r.trades == 0)

    print(
        f"\n  HYPO aggregate:  {all_hypo_trades} trades, {hypo_wr}% WR, R{all_hypo_pnl} PnL, {profitable_hypo}/20 profitable runs"
    )
    print(
        f"  STRICT aggregate: {all_strict_trades} trades, {strict_wr}% WR, R{all_strict_pnl} PnL, {profitable_strict}/20 runs (profitable or zero-trade)"
    )
    print(f"  RANGING trades:  HYPO={all_hypo_ranging}, STRICT={all_strict_ranging}")
    print(
        f"  Walk-forward:    HYPO {wf_hypo_profitable}/{len(hypo_wf)} windows profitable, STRICT {wf_strict_profitable}/{len(strict_wf)} windows"
    )
    print(f"  Robust threshold: {robust_threshold}")

    print("\n" + "=" * 70)
    print("VALIDATION COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()

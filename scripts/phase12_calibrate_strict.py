"""
Phase 12B: Strict Mode Recalibration Script.

Tests confidence arbiter thresholds at 0.60, 0.65, 0.70, 0.75 to find the
operating point that maximises edge-concentration while maintaining positive
expectancy and acceptable drawdown.
"""

import importlib.util
import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PROJECT_ROOT)

from decimal import ROUND_HALF_EVEN, Decimal


def _direct_import(module_name, filepath):
    if module_name in sys.modules:
        return sys.modules[module_name]
    spec = importlib.util.spec_from_file_location(module_name, filepath)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


_sim_mod = _direct_import(
    "jobs.validation.simulation",
    os.path.join(_PROJECT_ROOT, "jobs", "validation", "simulation.py"),
)
generate_synthetic_ohlcv = _sim_mod.generate_synthetic_ohlcv
run_alpha_system = _sim_mod.run_alpha_system
compute_metrics = _sim_mod.compute_metrics
diagnose_edge = _sim_mod.diagnose_edge
run_baseline = _sim_mod.run_baseline
RandomBaseline = _sim_mod.RandomBaseline
SimpleIndicatorBaseline = _sim_mod.SimpleIndicatorBaseline
SEED = _sim_mod.SEED
NUM_CANDLES = _sim_mod.NUM_CANDLES
INITIAL_EQUITY_ZAR = _sim_mod.INITIAL_EQUITY_ZAR
ZERO = _sim_mod.ZERO


CID_BASE = "PHASE12-STRICT-CAL"
THRESHOLDS = [
    Decimal("60.00"),
    Decimal("65.00"),
    Decimal("70.00"),
    Decimal("75.00"),
]


def main():
    candles = generate_synthetic_ohlcv(NUM_CANDLES, SEED, CID_BASE)

    # Baselines (run once)
    rng_baseline = RandomBaseline(seed=SEED)
    ema_baseline = SimpleIndicatorBaseline(seed=SEED)
    rng_trades = run_baseline(rng_baseline, candles, INITIAL_EQUITY_ZAR)
    ema_trades = run_baseline(ema_baseline, candles, INITIAL_EQUITY_ZAR)
    rng_metrics = compute_metrics("RANDOM", rng_trades, INITIAL_EQUITY_ZAR)
    ema_metrics = compute_metrics("EMA_CROSSOVER", ema_trades, INITIAL_EQUITY_ZAR)

    # Also run HYPO (bypass gate) for comparison
    hypo_records, hypo_trades = run_alpha_system(
        candles, CID_BASE + "-HYPO", bypass_confidence_gate=True
    )
    hypo_metrics = compute_metrics("HYPO", hypo_trades, INITIAL_EQUITY_ZAR, hypo_records)

    print("=" * 70)
    print("PHASE 12B: STRICT MODE RECALIBRATION")
    print("=" * 70)

    print("\n--- BASELINES ---")
    print(f"  RANDOM:        PnL=R{rng_metrics.total_pnl_zar}  trades={rng_metrics.total_trades}")
    print(f"  EMA_CROSSOVER: PnL=R{ema_metrics.total_pnl_zar}  trades={ema_metrics.total_trades}")
    print(
        f"  HYPO (bypass): PnL=R{hypo_metrics.total_pnl_zar}  "
        f"trades={hypo_metrics.total_trades}  "
        f"WR={hypo_metrics.win_rate}%  PF={hypo_metrics.profit_factor}  "
        f"DD={hypo_metrics.max_drawdown_pct}%"
    )

    print("\n--- STRICT THRESHOLD SWEEP ---")
    print(
        f"{'Threshold':>10} | {'Trades':>6} | {'Win%':>6} | "
        f"{'PnL (ZAR)':>12} | {'PF':>6} | {'Expect':>10} | {'MaxDD%':>7}"
    )
    print("-" * 70)

    results = []
    for threshold in THRESHOLDS:
        cid = CID_BASE + f"-T{threshold}"
        records, trades = run_alpha_system(
            candles,
            cid,
            bypass_confidence_gate=False,
            strict_threshold=threshold,
        )
        m = compute_metrics(f"STRICT-{threshold}", trades, INITIAL_EQUITY_ZAR, records)

        # Regime breakdown
        regime_pnl = {}
        for rec in records:
            if rec.executed:
                regime_pnl.setdefault(rec.regime, []).append(rec.realized_pnl_zar)

        results.append((threshold, m, regime_pnl))

        print(
            f"{threshold:>10} | {m.total_trades:>6} | {m.win_rate:>6} | "
            f"R{m.total_pnl_zar:>11} | {m.profit_factor:>6} | "
            f"R{m.expectancy_zar:>9} | {m.max_drawdown_pct:>6}%"
        )

    # Regime breakdown per threshold
    print("\n--- REGIME BREAKDOWN BY THRESHOLD ---")
    for threshold, m, regime_pnl in results:
        print(f"\n  Threshold={threshold}:")
        for regime, pnls in sorted(regime_pnl.items()):
            total = len(pnls)
            wins = sum(1 for p in pnls if p > ZERO)
            pnl_sum = sum(pnls)
            wr = (
                (Decimal(str(wins)) / Decimal(str(total)) * Decimal("100")).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_EVEN
                )
                if total > 0
                else ZERO
            )
            print(f"    {regime:<12} trades={total:>3}  WR={wr}%  PnL=R{pnl_sum}")

    # Selection logic
    print("\n--- THRESHOLD SELECTION ---")
    best = None
    best_score = Decimal("-99999")
    for threshold, m, regime_pnl in results:
        # Must have positive expectancy and at least 3 trades
        if m.total_trades < 3 or m.expectancy_zar <= ZERO:
            print(f"  {threshold}: REJECTED (trades={m.total_trades}, expect={m.expectancy_zar})")
            continue
        if m.max_drawdown_pct > Decimal("10"):
            print(f"  {threshold}: REJECTED (drawdown={m.max_drawdown_pct}% > 10%)")
            continue
        # Score = expectancy * sqrt(trades) * profit_factor — rewards
        # edge quality scaled by sample size
        import math

        score = m.expectancy_zar * Decimal(str(math.sqrt(m.total_trades))) * m.profit_factor
        print(
            f"  {threshold}: CANDIDATE score={score.quantize(Decimal('0.01'))} "
            f"(expect={m.expectancy_zar}, trades={m.total_trades}, PF={m.profit_factor})"
        )
        if score > best_score:
            best_score = score
            best = (threshold, m)

    if best:
        print(f"\n  >>> SELECTED THRESHOLD: {best[0]} <<<")
        print(
            f"      Trades={best[1].total_trades}  WR={best[1].win_rate}%  "
            f"PnL=R{best[1].total_pnl_zar}  PF={best[1].profit_factor}  "
            f"DD={best[1].max_drawdown_pct}%  Expect=R{best[1].expectancy_zar}"
        )
    else:
        print("\n  >>> NO VIABLE THRESHOLD FOUND <<<")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()

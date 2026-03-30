"""
Phase 12H: Full Validation — Phase 11 vs Phase 12 comparison.

Runs both STRICT and HYPOTHETICAL modes to measure:
1. Effect of regime gating (Section A)
2. Effect of strict threshold recalibration (Section B)
3. Before/after on all metrics
"""

import importlib.util
import os
import sys
from decimal import ROUND_HALF_EVEN, Decimal

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PROJECT_ROOT)


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
determine_verdict = _sim_mod.determine_verdict
run_baseline = _sim_mod.run_baseline
RandomBaseline = _sim_mod.RandomBaseline
SimpleIndicatorBaseline = _sim_mod.SimpleIndicatorBaseline
DecisionOutcome = _sim_mod.DecisionOutcome
SEED = _sim_mod.SEED
NUM_CANDLES = _sim_mod.NUM_CANDLES
INITIAL_EQUITY_ZAR = _sim_mod.INITIAL_EQUITY_ZAR
ZERO = _sim_mod.ZERO

CID = "PHASE12-VALIDATION"


def _regime_breakdown(records):
    """Compute PnL and trade count per regime."""
    regime_data = {}
    for rec in records:
        if rec.executed:
            r = rec.regime
            regime_data.setdefault(r, {"trades": 0, "wins": 0, "pnl": Decimal("0")})
            regime_data[r]["trades"] += 1
            regime_data[r]["pnl"] += rec.realized_pnl_zar
            if rec.realized_pnl_zar > ZERO:
                regime_data[r]["wins"] += 1
    return regime_data


def main():
    candles = generate_synthetic_ohlcv(NUM_CANDLES, SEED, CID)

    # Baselines
    rng_trades = run_baseline(RandomBaseline(seed=SEED), candles, INITIAL_EQUITY_ZAR)
    ema_trades = run_baseline(SimpleIndicatorBaseline(seed=SEED), candles, INITIAL_EQUITY_ZAR)
    rng_metrics = compute_metrics("RANDOM", rng_trades, INITIAL_EQUITY_ZAR)
    ema_metrics = compute_metrics("EMA_CROSSOVER", ema_trades, INITIAL_EQUITY_ZAR)

    # HYPO (bypass confidence gate — pure alpha layer evaluation)
    hypo_records, hypo_trades = run_alpha_system(
        candles,
        CID + "-HYPO",
        bypass_confidence_gate=True,
    )
    hypo_metrics = compute_metrics("HYPO", hypo_trades, INITIAL_EQUITY_ZAR, hypo_records)

    # STRICT (new threshold 65.00 — operationally useful)
    strict_records, strict_trades = run_alpha_system(
        candles,
        CID + "-STRICT",
        bypass_confidence_gate=False,
    )
    strict_metrics = compute_metrics("STRICT", strict_trades, INITIAL_EQUITY_ZAR, strict_records)

    # STRICT with old 95.00 threshold for comparison
    strict95_records, strict95_trades = run_alpha_system(
        candles,
        CID + "-STRICT95",
        bypass_confidence_gate=False,
        strict_threshold=Decimal("95.00"),
    )
    strict95_metrics = compute_metrics(
        "STRICT-95", strict95_trades, INITIAL_EQUITY_ZAR, strict95_records
    )

    # Verdicts
    hypo_verdict, hypo_evidence = determine_verdict(
        hypo_metrics,
        rng_metrics,
        ema_metrics,
        diagnose_edge(hypo_records, hypo_metrics, rng_metrics, ema_metrics),
    )
    strict_verdict, strict_evidence = determine_verdict(
        strict_metrics,
        rng_metrics,
        ema_metrics,
        diagnose_edge(strict_records, strict_metrics, rng_metrics, ema_metrics),
    )

    # ── PRINT RESULTS ────────────────────────────────────────────────
    print("=" * 70)
    print("PHASE 12H: FULL VALIDATION — Phase 11 vs Phase 12")
    print("=" * 70)

    print("\n--- BASELINES ---")
    print(f"  RANDOM:        PnL=R{rng_metrics.total_pnl_zar}  trades={rng_metrics.total_trades}")
    print(f"  EMA_CROSSOVER: PnL=R{ema_metrics.total_pnl_zar}  trades={ema_metrics.total_trades}")

    # Comparison table
    print("\n--- PHASE 11 vs PHASE 12 COMPARISON ---")
    print(
        f"{'Metric':<35} {'Ph11 HYPO':>12} {'Ph12 HYPO':>12} {'Ph11 STRICT':>12} {'Ph12 STRICT':>12}"
    )
    print("-" * 85)

    # Phase 11 known values (from ROOT_CAUSE_ANALYSIS.md)
    ph11_hypo = {
        "trades": 23,
        "wr": "47.83",
        "pnl": "984.86",
        "pf": "1.23",
        "dd": "1.71",
        "expect": "42.82",
    }
    ph11_strict = {
        "trades": 0,
        "wr": "0",
        "pnl": "0",
        "pf": "0",
        "dd": "0",
        "expect": "0",
    }

    rows = [
        (
            "Total trades",
            ph11_hypo["trades"],
            hypo_metrics.total_trades,
            ph11_strict["trades"],
            strict_metrics.total_trades,
        ),
        (
            "Win rate (%)",
            ph11_hypo["wr"],
            str(hypo_metrics.win_rate),
            ph11_strict["wr"],
            str(strict_metrics.win_rate),
        ),
        (
            "Total PnL (ZAR)",
            "R" + ph11_hypo["pnl"],
            f"R{hypo_metrics.total_pnl_zar}",
            "R" + ph11_strict["pnl"],
            f"R{strict_metrics.total_pnl_zar}",
        ),
        (
            "Profit factor",
            ph11_hypo["pf"],
            str(hypo_metrics.profit_factor),
            ph11_strict["pf"],
            str(strict_metrics.profit_factor),
        ),
        (
            "Max drawdown (%)",
            ph11_hypo["dd"],
            str(hypo_metrics.max_drawdown_pct),
            ph11_strict["dd"],
            str(strict_metrics.max_drawdown_pct),
        ),
        (
            "Expectancy (ZAR)",
            "R" + ph11_hypo["expect"],
            f"R{hypo_metrics.expectancy_zar}",
            "R" + ph11_strict["expect"],
            f"R{strict_metrics.expectancy_zar}",
        ),
    ]
    for label, ph11h, ph12h, ph11s, ph12s in rows:
        print(f"  {label:<33} {str(ph11h):>12} {str(ph12h):>12} {str(ph11s):>12} {str(ph12s):>12}")

    # Verdicts
    print("\n  HYPO verdict:   Phase 11 = ALPHA EVIDENCE FOUND")
    print(f"                  Phase 12 = {hypo_verdict}")
    print("  STRICT verdict: Phase 11 = INCONCLUSIVE (0 trades)")
    print(f"                  Phase 12 = {strict_verdict}")

    # Regime breakdown
    print("\n--- REGIME BREAKDOWN (Phase 12) ---")
    for mode_name, records in [("HYPO", hypo_records), ("STRICT", strict_records)]:
        rd = _regime_breakdown(records)
        print(f"\n  {mode_name}:")
        if not rd:
            print("    (no executed trades)")
        for regime, data in sorted(rd.items()):
            wr = (
                (
                    Decimal(str(data["wins"])) / Decimal(str(data["trades"])) * Decimal("100")
                ).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
                if data["trades"] > 0
                else ZERO
            )
            print(f"    {regime:<12}  trades={data['trades']:>3}  WR={wr}%  PnL=R{data['pnl']}")

    # Rejection analysis
    print("\n--- REJECTION ANALYSIS (Phase 12) ---")
    for mode_name, records in [("HYPO", hypo_records), ("STRICT", strict_records)]:
        outcomes = {}
        for rec in records:
            outcomes[rec.outcome] = outcomes.get(rec.outcome, 0) + 1
        print(f"\n  {mode_name}:")
        for outcome, count in sorted(outcomes.items(), key=lambda x: -x[1]):
            print(f"    {outcome:<35} {count:>4}")

    # Evidence
    print("\n--- STRICT MODE EVIDENCE ---")
    for e in strict_evidence:
        print(f"  {e}")

    # Old vs new strict
    print("\n--- STRICT 95% vs 65% ---")
    print(
        f"  STRICT (95%): trades={strict95_metrics.total_trades}  PnL=R{strict95_metrics.total_pnl_zar}"
    )
    print(
        f"  STRICT (65%): trades={strict_metrics.total_trades}  "
        f"PnL=R{strict_metrics.total_pnl_zar}  "
        f"WR={strict_metrics.win_rate}%  PF={strict_metrics.profit_factor}"
    )

    print("\n" + "=" * 70)
    print("VALIDATION COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()

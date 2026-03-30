"""
============================================================================
Paper Trading Validation -- Orchestrator
============================================================================

Section J: Thin wrapper that runs strict + hypothetical modes and
generates all 5 required report files.

Usage:
    python -m jobs.validation

Reliability Level: L6 Critical (Sovereign Tier)
============================================================================
"""

from __future__ import annotations

import logging
import os
import sys
import uuid

# ── Project root on path ─────────────────────────────────────────────────────
_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# Bypass jobs/__init__.py circular import by importing directly
import importlib.util as _ilu


def _load_sibling(name: str):
    spec = _ilu.spec_from_file_location(
        name,
        os.path.join(os.path.dirname(os.path.abspath(__file__)), name + ".py"),
    )
    mod = _ilu.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


_sim = _load_sibling("simulation")
_rep = _load_sibling("reports")

INITIAL_EQUITY_ZAR = _sim.INITIAL_EQUITY_ZAR
NUM_CANDLES = _sim.NUM_CANDLES
SEED = _sim.SEED
SYMBOL = _sim.SYMBOL
ZERO = _sim.ZERO
RandomBaseline = _sim.RandomBaseline
SimpleIndicatorBaseline = _sim.SimpleIndicatorBaseline
compute_metrics = _sim.compute_metrics
determine_verdict = _sim.determine_verdict
diagnose_edge = _sim.diagnose_edge
generate_synthetic_ohlcv = _sim.generate_synthetic_ohlcv
run_alpha_system = _sim.run_alpha_system
run_baseline = _sim.run_baseline

write_alpha_diagnosis_report = _rep.write_alpha_diagnosis_report
write_baseline_comparison_report = _rep.write_baseline_comparison_report
write_decision_log_csv = _rep.write_decision_log_csv
write_metrics_csv = _rep.write_metrics_csv
write_validation_report = _rep.write_validation_report

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
)
logger = logging.getLogger("paper_trading_validation")


def main() -> int:
    """Run the full paper trading validation and generate reports."""
    cid = "PTV-" + uuid.uuid4().hex[:8]
    logger.info("=== Paper Trading Validation START | cid=%s ===", cid)

    # Output directory
    output_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "data",
        "validation_results",
    )
    os.makedirs(output_dir, exist_ok=True)

    # Step 1: Generate synthetic data
    logger.info(
        "Step 1/8: Generating synthetic BTCZAR data (%d candles)...", NUM_CANDLES
    )
    candles = generate_synthetic_ohlcv(NUM_CANDLES, SEED, cid)

    # Step 2: Run baselines
    logger.info("Step 2/8: Running baseline strategies...")
    random_baseline = RandomBaseline(seed=SEED + 1)
    ema_baseline = SimpleIndicatorBaseline(seed=SEED + 2)
    random_trades = run_baseline(random_baseline, candles, INITIAL_EQUITY_ZAR)
    ema_trades = run_baseline(ema_baseline, candles, INITIAL_EQUITY_ZAR)

    random_metrics = compute_metrics(
        "RANDOM_DIRECTION", random_trades, INITIAL_EQUITY_ZAR
    )
    ema_metrics = compute_metrics("EMA_CROSSOVER", ema_trades, INITIAL_EQUITY_ZAR)

    logger.info(
        "Baselines complete: Random=%d trades (PnL=R%s), EMA=%d trades (PnL=R%s)",
        random_metrics.total_trades,
        random_metrics.total_pnl_zar,
        ema_metrics.total_trades,
        ema_metrics.total_pnl_zar,
    )

    # Step 3: Run alpha system (STRICT mode)
    logger.info("Step 3/8: Running alpha system (STRICT mode, 95%% confidence gate)...")
    strict_records, strict_trades = run_alpha_system(candles, cid + "-STRICT")
    strict_metrics = compute_metrics(
        "ALPHA_SYSTEM_STRICT",
        strict_trades,
        INITIAL_EQUITY_ZAR,
        strict_records,
    )

    logger.info(
        "STRICT mode: %d decisions, %d trades, PnL=R%s",
        len(strict_records),
        strict_metrics.total_trades,
        strict_metrics.total_pnl_zar,
    )

    # Step 4: Run alpha system (HYPOTHETICAL mode)
    logger.info("Step 4/8: Running alpha system (HYPOTHETICAL mode, gate bypassed)...")
    hypo_records, hypo_trades = run_alpha_system(
        candles,
        cid + "-HYPO",
        bypass_confidence_gate=True,
    )
    hypo_metrics = compute_metrics(
        "ALPHA_SYSTEM_HYPOTHETICAL",
        hypo_trades,
        INITIAL_EQUITY_ZAR,
        hypo_records,
    )

    logger.info(
        "HYPOTHETICAL mode: %d decisions, %d trades, PnL=R%s",
        len(hypo_records),
        hypo_metrics.total_trades,
        hypo_metrics.total_pnl_zar,
    )

    # Step 5: Diagnose edge
    logger.info("Step 5/8: Running edge diagnosis...")
    strict_diagnosis = diagnose_edge(
        strict_records, strict_metrics, random_metrics, ema_metrics
    )
    hypo_diagnosis = diagnose_edge(
        hypo_records, hypo_metrics, random_metrics, ema_metrics
    )

    # Step 6: Determine verdicts
    logger.info("Step 6/8: Determining verdicts...")
    strict_verdict, strict_evidence = determine_verdict(
        strict_metrics,
        random_metrics,
        ema_metrics,
        strict_diagnosis,
    )
    hypo_verdict, hypo_evidence = determine_verdict(
        hypo_metrics,
        random_metrics,
        ema_metrics,
        hypo_diagnosis,
    )

    logger.info("STRICT verdict: %s", strict_verdict)
    logger.info("HYPOTHETICAL verdict: %s", hypo_verdict)

    # Step 7: Write reports
    logger.info("Step 7/8: Writing report files...")

    # Report 1: Decision log CSV
    write_decision_log_csv(
        strict_records + hypo_records,
        os.path.join(output_dir, "decision_log.csv"),
    )

    # Report 2: Metrics CSV
    write_metrics_csv(
        [strict_metrics, hypo_metrics, random_metrics, ema_metrics],
        os.path.join(output_dir, "metrics_comparison.csv"),
    )

    # Report 3: Main validation report
    write_validation_report(
        verdict=strict_verdict,
        evidence=strict_evidence,
        alpha_metrics=strict_metrics,
        random_metrics=random_metrics,
        ema_metrics=ema_metrics,
        diagnosis=strict_diagnosis,
        filepath=os.path.join(output_dir, "VALIDATION_REPORT.md"),
        hypo_verdict=hypo_verdict,
        hypo_evidence=hypo_evidence,
        hypo_alpha_metrics=hypo_metrics,
    )

    # Report 4: Baseline comparison
    write_baseline_comparison_report(
        alpha_metrics=strict_metrics,
        random_metrics=random_metrics,
        ema_metrics=ema_metrics,
        random_trades=random_trades,
        ema_trades=ema_trades,
        filepath=os.path.join(output_dir, "BASELINE_COMPARISON.md"),
    )

    # Report 5: Alpha diagnosis
    write_alpha_diagnosis_report(
        diagnosis=hypo_diagnosis,
        alpha_metrics=hypo_metrics,
        filepath=os.path.join(output_dir, "ALPHA_DIAGNOSIS.md"),
    )

    # Step 8: Print summary
    logger.info("Step 8/8: Validation complete.")
    logger.info("=" * 72)
    logger.info("STRICT VERDICT: %s", strict_verdict)
    logger.info("HYPOTHETICAL VERDICT: %s", hypo_verdict)
    logger.info("=" * 72)
    logger.info("Reports written to: %s", output_dir)
    logger.info(
        "  1. decision_log.csv (%d records)",
        len(strict_records) + len(hypo_records),
    )
    logger.info("  2. metrics_comparison.csv (4 strategies)")
    logger.info("  3. VALIDATION_REPORT.md")
    logger.info("  4. BASELINE_COMPARISON.md")
    logger.info("  5. ALPHA_DIAGNOSIS.md")
    logger.info("=== Paper Trading Validation END | cid=%s ===", cid)

    return 0


if __name__ == "__main__":
    sys.exit(main())

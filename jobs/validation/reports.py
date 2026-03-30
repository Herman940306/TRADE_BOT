"""
============================================================================
Paper Trading Validation -- Report Writers
============================================================================

Section I: All 5 required report files.

Uses plain string concatenation (zero f-strings) to prevent IDE parser
choking on complex interpolated blocks.

Reliability Level: L6 Critical (Sovereign Tier)
============================================================================
"""

from __future__ import annotations

import csv
import importlib.util as _ilu
import os
import sys
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# Load simulation sibling without triggering jobs/__init__.py
if "simulation" not in sys.modules:
    _spec = _ilu.spec_from_file_location(
        "simulation",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "simulation.py"),
    )
    _mod = _ilu.module_from_spec(_spec)
    sys.modules["simulation"] = _mod
    _spec.loader.exec_module(_mod)

import simulation as _sim

INITIAL_EQUITY_ZAR = _sim.INITIAL_EQUITY_ZAR
PRECISION_ZAR = _sim.PRECISION_ZAR
ZERO = _sim.ZERO
DecisionOutcome = _sim.DecisionOutcome
DecisionRecord = _sim.DecisionRecord
EdgeDiagnosis = _sim.EdgeDiagnosis
TradingMetrics = _sim.TradingMetrics


def _get_output_dir() -> str:
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "data",
        "validation_results",
    )


# ── Report 1: Decision Log CSV ──────────────────────────────────────────────


def write_decision_log_csv(
    records: List[DecisionRecord],
    filepath: str,
) -> str:
    """Write full decision audit log as CSV."""
    fieldnames = [
        "correlation_id",
        "timestamp_ms",
        "symbol",
        "candle_index",
        "direction",
        "probability_up",
        "probability_down",
        "confidence",
        "quality",
        "regime",
        "reject_reasons",
        "outcome",
        "arbiter_adjusted_confidence",
        "arbiter_should_execute",
        "risk_approved",
        "risk_qty",
        "executed",
        "order_side",
        "fill_price",
        "fill_qty",
        "exit_price",
        "realized_pnl_zar",
        "bars_held",
        "trade_outcome",
        "row_hash",
    ]
    with open(filepath, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for rec in records:
            row = {
                "correlation_id": rec.correlation_id,
                "timestamp_ms": str(rec.timestamp_ms),
                "symbol": rec.symbol,
                "candle_index": str(rec.candle_index),
                "direction": rec.direction,
                "probability_up": str(rec.probability_up),
                "probability_down": str(rec.probability_down),
                "confidence": str(rec.confidence),
                "quality": rec.quality,
                "regime": rec.regime,
                "reject_reasons": ";".join(rec.reject_reasons),
                "outcome": rec.outcome,
                "arbiter_adjusted_confidence": str(rec.arbiter_adjusted_confidence),
                "arbiter_should_execute": str(rec.arbiter_should_execute),
                "risk_approved": str(rec.risk_approved),
                "risk_qty": str(rec.risk_qty),
                "executed": str(rec.executed),
                "order_side": rec.order_side,
                "fill_price": str(rec.fill_price),
                "fill_qty": str(rec.fill_qty),
                "exit_price": str(rec.exit_price),
                "realized_pnl_zar": str(rec.realized_pnl_zar),
                "bars_held": str(rec.bars_held),
                "trade_outcome": rec.trade_outcome,
                "row_hash": rec.row_hash,
            }
            writer.writerow(row)
    return filepath


# ── Report 2: Metrics CSV ───────────────────────────────────────────────────


def write_metrics_csv(
    metrics_list: List[TradingMetrics],
    filepath: str,
) -> str:
    """Write strategy metrics comparison as CSV."""
    if not metrics_list:
        return filepath
    fieldnames = list(metrics_list[0].to_csv_row().keys())
    with open(filepath, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for m in metrics_list:
            writer.writerow(m.to_csv_row())
    return filepath


# ── Report 3: Validation Report ─────────────────────────────────────────────


def write_validation_report(
    verdict: str,
    evidence: List[str],
    alpha_metrics: TradingMetrics,
    random_metrics: TradingMetrics,
    ema_metrics: TradingMetrics,
    diagnosis: EdgeDiagnosis,
    filepath: str,
    hypo_verdict: Optional[str] = None,
    hypo_evidence: Optional[List[str]] = None,
    hypo_alpha_metrics: Optional[TradingMetrics] = None,
) -> str:
    """Write main validation report as Markdown."""
    now = datetime.now(timezone.utc).isoformat()
    lines: List[str] = []

    lines.append("# Paper Trading Validation Report")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("| Field | Value |")
    lines.append("|---|---|")
    lines.append("| Date | " + now + " |")
    lines.append("| Verdict | **" + verdict + "** |")
    lines.append("| Symbol | BTCZAR |")
    lines.append("| Data | 500 synthetic 1-hour candles (GBM + regime shifts) |")
    lines.append("| Initial Equity | R" + str(INITIAL_EQUITY_ZAR) + " |")
    lines.append("| Seed | 42 |")
    lines.append("")

    lines.append("## Verdict Evidence")
    lines.append("")
    for ev in evidence:
        lines.append("- " + ev)
    lines.append("")

    # Alpha metrics table
    lines.append("## Alpha System Metrics (STRICT MODE)")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---|")
    lines.append("| Total Signals | " + str(alpha_metrics.total_signals) + " |")
    lines.append("| Signals Approved | " + str(alpha_metrics.signals_approved) + " |")
    lines.append("| Approval Rate | " + str(alpha_metrics.approval_rate_pct) + "% |")
    lines.append("| Total Trades | " + str(alpha_metrics.total_trades) + " |")
    lines.append("| Winning Trades | " + str(alpha_metrics.winning_trades) + " |")
    lines.append("| Losing Trades | " + str(alpha_metrics.losing_trades) + " |")
    lines.append("| Win Rate | " + str(alpha_metrics.win_rate) + "% |")
    lines.append("| Total PnL | R" + str(alpha_metrics.total_pnl_zar) + " |")
    lines.append(
        "| Cumulative Return | " + str(alpha_metrics.cumulative_return_pct) + "% |"
    )
    lines.append("| Max Drawdown | " + str(alpha_metrics.max_drawdown_pct) + "% |")
    lines.append("| Profit Factor | " + str(alpha_metrics.profit_factor) + " |")
    lines.append("| Expectancy | R" + str(alpha_metrics.expectancy_zar) + " |")
    lines.append("| Avg Win | R" + str(alpha_metrics.avg_win_zar) + " |")
    lines.append("| Avg Loss | R" + str(alpha_metrics.avg_loss_zar) + " |")
    lines.append("")

    # Rejection funnel
    lines.append("## Signal Rejection Funnel")
    lines.append("")
    lines.append("| Filter | Rejected |")
    lines.append("|---|---|")
    lines.append(
        "| Quality Filter | " + str(alpha_metrics.signals_rejected_quality) + " |"
    )
    lines.append(
        "| Confidence Gate (95%) | "
        + str(alpha_metrics.signals_rejected_confidence)
        + " |"
    )
    lines.append("| Risk Governor | " + str(alpha_metrics.signals_rejected_risk) + " |")
    lines.append(
        "| Approved + Executed | " + str(alpha_metrics.signals_approved) + " |"
    )
    lines.append("")

    # Baseline comparison mini-table
    lines.append("## Baseline Comparison")
    lines.append("")
    lines.append("| Strategy | Trades | PnL (ZAR) | Win Rate | Profit Factor |")
    lines.append("|---|---|---|---|---|")
    lines.append(
        "| Alpha System | "
        + str(alpha_metrics.total_trades)
        + " | R"
        + str(alpha_metrics.total_pnl_zar)
        + " | "
        + str(alpha_metrics.win_rate)
        + "%"
        + " | "
        + str(alpha_metrics.profit_factor)
        + " |"
    )
    lines.append(
        "| Random Baseline | "
        + str(random_metrics.total_trades)
        + " | R"
        + str(random_metrics.total_pnl_zar)
        + " | "
        + str(random_metrics.win_rate)
        + "%"
        + " | "
        + str(random_metrics.profit_factor)
        + " |"
    )
    lines.append(
        "| EMA Crossover | "
        + str(ema_metrics.total_trades)
        + " | R"
        + str(ema_metrics.total_pnl_zar)
        + " | "
        + str(ema_metrics.win_rate)
        + "%"
        + " | "
        + str(ema_metrics.profit_factor)
        + " |"
    )
    lines.append("")

    # Key findings
    lines.append("## Key Findings")
    lines.append("")
    for finding in diagnosis.key_findings:
        lines.append("- " + finding)
    lines.append("")
    lines.append("## Bottleneck")
    lines.append("")
    lines.append(diagnosis.bottleneck)
    lines.append("")

    # Hypothetical section (if available)
    if hypo_verdict and hypo_evidence and hypo_alpha_metrics:
        lines.append("---")
        lines.append("")
        lines.append("# HYPOTHETICAL MODE (confidence gate bypassed)")
        lines.append("")
        lines.append("This section shows what happens when the 95% confidence gate is")
        lines.append(
            "bypassed. These are NOT real recommendations -- purely diagnostic."
        )
        lines.append("")
        lines.append("## Hypothetical Verdict: **" + hypo_verdict + "**")
        lines.append("")
        for ev in hypo_evidence:
            lines.append("- " + ev)
        lines.append("")

        lines.append("## Hypothetical Metrics")
        lines.append("")
        lines.append("| Metric | Value |")
        lines.append("|---|---|")
        lines.append("| Total Trades | " + str(hypo_alpha_metrics.total_trades) + " |")
        lines.append("| Win Rate | " + str(hypo_alpha_metrics.win_rate) + "% |")
        lines.append("| Total PnL | R" + str(hypo_alpha_metrics.total_pnl_zar) + " |")
        lines.append(
            "| Profit Factor | " + str(hypo_alpha_metrics.profit_factor) + " |"
        )
        lines.append(
            "| Max Drawdown | " + str(hypo_alpha_metrics.max_drawdown_pct) + "% |"
        )
        lines.append("| Expectancy | R" + str(hypo_alpha_metrics.expectancy_zar) + " |")
        lines.append("")

    lines.append("---")
    lines.append("*Generated by Paper Trading Validation v1.0.0*")

    with open(filepath, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    return filepath


# ── Report 4: Baseline Comparison Report ─────────────────────────────────────


def write_baseline_comparison_report(
    alpha_metrics: TradingMetrics,
    random_metrics: TradingMetrics,
    ema_metrics: TradingMetrics,
    random_trades: List[Dict[str, Any]],
    ema_trades: List[Dict[str, Any]],
    filepath: str,
) -> str:
    """Write detailed baseline comparison report."""
    lines: List[str] = []
    now = datetime.now(timezone.utc).isoformat()

    lines.append("# Baseline Comparison Report")
    lines.append("")
    lines.append("Generated: " + now)
    lines.append("")

    lines.append("## Strategy Overview")
    lines.append("")
    lines.append("| Strategy | Description |")
    lines.append("|---|---|")
    lines.append(
        "| Alpha System | Full pipeline: Signal Detection -> Confidence -> Risk -> Execution |"
    )
    lines.append(
        "| Random Baseline | 15% chance per bar, 50/50 direction, no analysis |"
    )
    lines.append(
        "| EMA Crossover | Buy on EMA(20) crossing above EMA(50), sell on cross below |"
    )
    lines.append("")

    # Detailed comparison
    lines.append("## Performance Comparison")
    lines.append("")
    lines.append("| Metric | Alpha | Random | EMA Crossover |")
    lines.append("|---|---|---|---|")

    metric_rows = [
        ("Total Trades", "total_trades"),
        ("Winning Trades", "winning_trades"),
        ("Losing Trades", "losing_trades"),
    ]
    for label, attr in metric_rows:
        lines.append(
            "| "
            + label
            + " | "
            + str(getattr(alpha_metrics, attr))
            + " | "
            + str(getattr(random_metrics, attr))
            + " | "
            + str(getattr(ema_metrics, attr))
            + " |"
        )

    pct_rows = [
        ("Win Rate", "win_rate", "%"),
        ("Max Drawdown", "max_drawdown_pct", "%"),
        ("Cumulative Return", "cumulative_return_pct", "%"),
    ]
    for label, attr, suffix in pct_rows:
        lines.append(
            "| "
            + label
            + " | "
            + str(getattr(alpha_metrics, attr))
            + suffix
            + " | "
            + str(getattr(random_metrics, attr))
            + suffix
            + " | "
            + str(getattr(ema_metrics, attr))
            + suffix
            + " |"
        )

    zar_rows = [
        ("Total PnL", "total_pnl_zar"),
        ("Avg Win", "avg_win_zar"),
        ("Avg Loss", "avg_loss_zar"),
        ("Expectancy", "expectancy_zar"),
    ]
    for label, attr in zar_rows:
        lines.append(
            "| "
            + label
            + " | R"
            + str(getattr(alpha_metrics, attr))
            + " | R"
            + str(getattr(random_metrics, attr))
            + " | R"
            + str(getattr(ema_metrics, attr))
            + " |"
        )

    lines.append(
        "| Profit Factor"
        + " | "
        + str(alpha_metrics.profit_factor)
        + " | "
        + str(random_metrics.profit_factor)
        + " | "
        + str(ema_metrics.profit_factor)
        + " |"
    )
    lines.append("")

    # Individual baseline trade logs
    lines.append("## Random Baseline Trades")
    lines.append("")
    if random_trades:
        lines.append(
            "| # | Side | Entry Price | Exit Price | PnL (ZAR) | Bars | Outcome |"
        )
        lines.append("|---|---|---|---|---|---|---|")
        for idx, t in enumerate(random_trades, 1):
            lines.append(
                "| "
                + str(idx)
                + " | "
                + str(t["side"])
                + " | "
                + str(t["entry_price"])
                + " | "
                + str(t["exit_price"])
                + " | R"
                + str(t["pnl_zar"])
                + " | "
                + str(t["bars_held"])
                + " | "
                + str(t["outcome"])
                + " |"
            )
    else:
        lines.append("No trades executed.")
    lines.append("")

    lines.append("## EMA Crossover Trades")
    lines.append("")
    if ema_trades:
        lines.append(
            "| # | Side | Entry Price | Exit Price | PnL (ZAR) | Bars | Outcome |"
        )
        lines.append("|---|---|---|---|---|---|---|")
        for idx, t in enumerate(ema_trades, 1):
            lines.append(
                "| "
                + str(idx)
                + " | "
                + str(t["side"])
                + " | "
                + str(t["entry_price"])
                + " | "
                + str(t["exit_price"])
                + " | R"
                + str(t["pnl_zar"])
                + " | "
                + str(t["bars_held"])
                + " | "
                + str(t["outcome"])
                + " |"
            )
    else:
        lines.append("No trades executed.")
    lines.append("")

    lines.append("---")
    lines.append("*Generated by Paper Trading Validation v1.0.0*")

    with open(filepath, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    return filepath


# ── Report 5: Alpha Diagnosis Report ────────────────────────────────────────


def write_alpha_diagnosis_report(
    diagnosis: EdgeDiagnosis,
    alpha_metrics: TradingMetrics,
    filepath: str,
) -> str:
    """Write the alpha edge diagnosis report."""
    lines: List[str] = []
    now = datetime.now(timezone.utc).isoformat()

    lines.append("# Alpha Edge Diagnosis Report")
    lines.append("")
    lines.append("Generated: " + now)
    lines.append("")
    lines.append("Total decisions analyzed: " + str(diagnosis.total_decisions))
    lines.append("")

    # Rejection funnel
    lines.append("## Signal Rejection Funnel")
    lines.append("")
    lines.append("| Outcome | Count | Percentage |")
    lines.append("|---|---|---|")
    for outcome, count in sorted(diagnosis.rejection_breakdown.items()):
        pct = "0.00"
        if diagnosis.total_decisions > 0:
            pct = str(
                (
                    Decimal(str(count))
                    / Decimal(str(diagnosis.total_decisions))
                    * Decimal("100")
                ).quantize(PRECISION_ZAR)
            )
        lines.append("| " + outcome + " | " + str(count) + " | " + pct + "% |")
    lines.append("")

    # Confidence distribution
    lines.append("## Confidence Distribution")
    lines.append("")
    lines.append("| Range | Count |")
    lines.append("|---|---|")
    for bucket in ["0-60", "60-80", "80-95", "95-100"]:
        count = diagnosis.confidence_distribution.get(bucket, 0)
        lines.append("| " + bucket + " | " + str(count) + " |")
    lines.append("")

    # Quality distribution
    lines.append("## Signal Quality Distribution")
    lines.append("")
    lines.append("| Quality | Count |")
    lines.append("|---|---|")
    for quality, count in sorted(diagnosis.quality_distribution.items()):
        lines.append("| " + quality + " | " + str(count) + " |")
    lines.append("")

    # Regime performance
    lines.append("## Regime Performance")
    lines.append("")
    if diagnosis.regime_performance:
        lines.append("| Regime | Trades | Wins | Win Rate | PnL (ZAR) |")
        lines.append("|---|---|---|---|---|")
        for regime, stats in sorted(diagnosis.regime_performance.items()):
            lines.append(
                "| "
                + regime
                + " | "
                + str(stats["trades"])
                + " | "
                + str(stats["wins"])
                + " | "
                + str(stats["win_rate"])
                + "%"
                + " | R"
                + str(stats["total_pnl"])
                + " |"
            )
    else:
        lines.append("No trades executed -- no regime performance data available.")
    lines.append("")

    # Direction accuracy
    lines.append("## Direction Accuracy")
    lines.append("")
    if diagnosis.direction_accuracy:
        lines.append("| Direction | Correct | Incorrect | Accuracy |")
        lines.append("|---|---|---|---|")
        for direction, stats in sorted(diagnosis.direction_accuracy.items()):
            total = stats["correct"] + stats["incorrect"]
            accuracy = "0.00"
            if total > 0:
                accuracy = str(
                    (
                        Decimal(str(stats["correct"]))
                        / Decimal(str(total))
                        * Decimal("100")
                    ).quantize(PRECISION_ZAR)
                )
            lines.append(
                "| "
                + direction
                + " | "
                + str(stats["correct"])
                + " | "
                + str(stats["incorrect"])
                + " | "
                + accuracy
                + "% |"
            )
    else:
        lines.append("No trades executed -- no direction accuracy data available.")
    lines.append("")

    # Bottleneck
    lines.append("## Primary Bottleneck")
    lines.append("")
    lines.append(
        diagnosis.bottleneck if diagnosis.bottleneck else "No bottleneck identified."
    )
    lines.append("")

    # Key findings
    lines.append("## Key Findings")
    lines.append("")
    for finding in diagnosis.key_findings:
        lines.append("- " + finding)
    lines.append("")

    # HITL impact
    lines.append("## HITL Impact")
    lines.append("")
    lines.append(diagnosis.hitl_impact)
    lines.append("")

    lines.append("---")
    lines.append("*Generated by Paper Trading Validation v1.0.0*")

    with open(filepath, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    return filepath

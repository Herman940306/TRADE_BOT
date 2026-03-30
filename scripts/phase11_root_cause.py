"""
Phase 11A: Root Cause Analysis Script
Analyzes why the alpha detection layer produces weak signals.
"""

import importlib.util
import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PROJECT_ROOT)

from statistics import mean, stdev


def _direct_import(module_name, filepath):
    if module_name in sys.modules:
        return sys.modules[module_name]
    spec = importlib.util.spec_from_file_location(module_name, filepath)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


# Import simulation directly to bypass circular imports
_sim_mod = _direct_import(
    "jobs.validation.simulation",
    os.path.join(_PROJECT_ROOT, "jobs", "validation", "simulation.py"),
)
generate_synthetic_ohlcv = _sim_mod.generate_synthetic_ohlcv
extract_features_pure = _sim_mod.extract_features_pure
estimate_probabilities = _sim_mod.estimate_probabilities
SEED = _sim_mod.SEED
NUM_CANDLES = _sim_mod.NUM_CANDLES
SYMBOL = _sim_mod.SYMBOL
ZERO = _sim_mod.ZERO
ONE = _sim_mod.ONE
HUNDRED = _sim_mod.HUNDRED
from app.alpha.models import SignalDirection, SignalQuality
from app.alpha.signal_decision import detect_regime, evaluate_signal

CID = "ROOT-CAUSE-001"


def main():
    candles = generate_synthetic_ohlcv(NUM_CANDLES, SEED, CID)

    results = {
        "LONG": {"total": 0, "approved": 0, "rejected": 0},
        "SHORT": {"total": 0, "approved": 0, "rejected": 0},
        "NEUTRAL": {"total": 0, "approved": 0, "rejected": 0},
    }
    regime_stats = {}
    reject_reasons_count = {}
    confidence_values = []
    prob_values = []
    direction_vs_future = {
        "LONG_correct": 0,
        "LONG_wrong": 0,
        "SHORT_correct": 0,
        "SHORT_wrong": 0,
    }
    # Track approved-only trades for win rate
    approved_trades = {
        "LONG_win": 0,
        "LONG_loss": 0,
        "SHORT_win": 0,
        "SHORT_loss": 0,
    }
    # Track multi-bar future returns for approved signals
    approved_5bar = {"LONG_win": 0, "LONG_loss": 0, "SHORT_win": 0, "SHORT_loss": 0}

    # Track by regime for approved signals
    regime_approved_accuracy = {}

    atr_history = []
    close_history = []

    for i in range(200, len(candles)):
        fv = extract_features_pure(candles, i, SYMBOL, CID)
        if fv is None:
            continue

        atr_history.append(fv.volatility.atr_14)
        close_history.append(candles[i].close)
        if len(atr_history) > 100:
            atr_history = atr_history[-100:]
            close_history = close_history[-100:]

        prob_up, prob_down = estimate_probabilities(fv, CID)
        prob_values.append((float(prob_up), float(prob_down)))

        regime = detect_regime(atr_history, close_history, CID)

        signal = evaluate_signal(fv, prob_up, prob_down, regime, CID)

        d = signal.direction.value
        results[d]["total"] += 1

        is_approved = signal.quality in (SignalQuality.HIGH, SignalQuality.MEDIUM)
        if is_approved:
            results[d]["approved"] += 1
        else:
            results[d]["rejected"] += 1

        r = signal.regime
        regime_stats.setdefault(r, {"total": 0, "approved": 0})
        regime_stats[r]["total"] += 1
        if is_approved:
            regime_stats[r]["approved"] += 1

        for rr in signal.reject_reasons:
            reject_reasons_count[rr.value] = reject_reasons_count.get(rr.value, 0) + 1

        confidence_values.append(float(signal.confidence))

        # Directional accuracy (1-bar)
        if i + 1 < len(candles):
            future_return = candles[i + 1].close - candles[i].close
            if d == "LONG":
                if future_return > ZERO:
                    direction_vs_future["LONG_correct"] += 1
                else:
                    direction_vs_future["LONG_wrong"] += 1
            elif d == "SHORT":
                if future_return < ZERO:
                    direction_vs_future["SHORT_correct"] += 1
                else:
                    direction_vs_future["SHORT_wrong"] += 1

            # Approved-only trade accuracy (1-bar)
            if is_approved:
                if d == "LONG":
                    if future_return > ZERO:
                        approved_trades["LONG_win"] += 1
                    else:
                        approved_trades["LONG_loss"] += 1
                elif d == "SHORT":
                    if future_return < ZERO:
                        approved_trades["SHORT_win"] += 1
                    else:
                        approved_trades["SHORT_loss"] += 1

                # Track by regime
                regime_key = str(r)
                regime_approved_accuracy.setdefault(regime_key, {"correct": 0, "wrong": 0})
                correct = False
                if d == "LONG" and future_return > ZERO:
                    correct = True
                elif d == "SHORT" and future_return < ZERO:
                    correct = True
                if correct:
                    regime_approved_accuracy[regime_key]["correct"] += 1
                else:
                    regime_approved_accuracy[regime_key]["wrong"] += 1

        # 5-bar future for approved signals
        if is_approved and i + 5 < len(candles):
            future_5 = candles[i + 5].close - candles[i].close
            if d == "LONG":
                if future_5 > ZERO:
                    approved_5bar["LONG_win"] += 1
                else:
                    approved_5bar["LONG_loss"] += 1
            elif d == "SHORT":
                if future_5 < ZERO:
                    approved_5bar["SHORT_win"] += 1
                else:
                    approved_5bar["SHORT_loss"] += 1

    # ── Print Results ────────────────────────────────────────────────────
    print("=" * 60)
    print("PHASE 11A: ROOT CAUSE ANALYSIS")
    print("=" * 60)

    print("\n=== SIGNAL DISTRIBUTION ===")
    for d, v in results.items():
        pct_approved = v["approved"] / max(v["total"], 1) * 100 if v["total"] > 0 else 0
        print(
            "  {}: total={}, approved={} ({:.1f}%), rejected={}".format(
                d, v["total"], v["approved"], pct_approved, v["rejected"]
            )
        )

    total_signals = sum(v["total"] for v in results.values())
    total_approved = sum(v["approved"] for v in results.values())
    print(
        "  TOTAL: {}/{} approved ({:.1f}%)".format(
            total_approved, total_signals, total_approved / max(total_signals, 1) * 100
        )
    )

    print("\n=== REGIME DISTRIBUTION ===")
    for r, v in regime_stats.items():
        print("  {}: total={}, approved={}".format(r, v["total"], v["approved"]))

    print("\n=== REJECT REASONS (sorted by frequency) ===")
    for rr, count in sorted(reject_reasons_count.items(), key=lambda x: -x[1]):
        print(
            "  {}: {} ({:.1f}% of signals)".format(rr, count, count / max(total_signals, 1) * 100)
        )

    print("\n=== ALL SIGNALS: DIRECTIONAL ACCURACY (1-bar) ===")
    for k, v in direction_vs_future.items():
        print("  {}: {}".format(k, v))

    total_long = direction_vs_future["LONG_correct"] + direction_vs_future["LONG_wrong"]
    total_short = direction_vs_future["SHORT_correct"] + direction_vs_future["SHORT_wrong"]
    long_acc = direction_vs_future["LONG_correct"] / max(total_long, 1) * 100
    short_acc = direction_vs_future["SHORT_correct"] / max(total_short, 1) * 100
    print(
        "  LONG accuracy: {}/{} = {:.1f}%".format(
            direction_vs_future["LONG_correct"], total_long, long_acc
        )
    )
    print(
        "  SHORT accuracy: {}/{} = {:.1f}%".format(
            direction_vs_future["SHORT_correct"], total_short, short_acc
        )
    )

    print("\n=== APPROVED SIGNALS: DIRECTIONAL ACCURACY (1-bar) ===")
    for k, v in approved_trades.items():
        print("  {}: {}".format(k, v))
    appr_long = approved_trades["LONG_win"] + approved_trades["LONG_loss"]
    appr_short = approved_trades["SHORT_win"] + approved_trades["SHORT_loss"]
    print(
        "  APPROVED LONG accuracy: {}/{} = {:.1f}%".format(
            approved_trades["LONG_win"],
            appr_long,
            approved_trades["LONG_win"] / max(appr_long, 1) * 100,
        )
    )
    print(
        "  APPROVED SHORT accuracy: {}/{} = {:.1f}%".format(
            approved_trades["SHORT_win"],
            appr_short,
            approved_trades["SHORT_win"] / max(appr_short, 1) * 100,
        )
    )

    print("\n=== APPROVED SIGNALS: 5-BAR ACCURACY ===")
    for k, v in approved_5bar.items():
        print("  {}: {}".format(k, v))
    a5_long = approved_5bar["LONG_win"] + approved_5bar["LONG_loss"]
    a5_short = approved_5bar["SHORT_win"] + approved_5bar["SHORT_loss"]
    print(
        "  APPROVED 5-bar LONG accuracy: {}/{} = {:.1f}%".format(
            approved_5bar["LONG_win"],
            a5_long,
            approved_5bar["LONG_win"] / max(a5_long, 1) * 100,
        )
    )
    print(
        "  APPROVED 5-bar SHORT accuracy: {}/{} = {:.1f}%".format(
            approved_5bar["SHORT_win"],
            a5_short,
            approved_5bar["SHORT_win"] / max(a5_short, 1) * 100,
        )
    )

    print("\n=== APPROVED ACCURACY BY REGIME ===")
    for regime_key, v in regime_approved_accuracy.items():
        total_r = v["correct"] + v["wrong"]
        acc = v["correct"] / max(total_r, 1) * 100
        print("  {}: {}/{} = {:.1f}%".format(regime_key, v["correct"], total_r, acc))

    print("\n=== PROBABILITY DISTRIBUTION ===")
    ups = [p[0] for p in prob_values]
    downs = [p[1] for p in prob_values]
    print(
        "  prob_up: min={:.4f}, max={:.4f}, mean={:.4f}, std={:.4f}".format(
            min(ups), max(ups), mean(ups), stdev(ups)
        )
    )
    max_probs = [max(u, d) for u, d in prob_values]
    print(
        "  max_prob: min={:.4f}, max={:.4f}, mean={:.4f}".format(
            min(max_probs), max(max_probs), mean(max_probs)
        )
    )
    for threshold in [0.55, 0.60, 0.65, 0.70, 0.75, 0.80]:
        count = sum(1 for p in max_probs if p >= threshold)
        print(
            "  max_prob >= {:.2f}: {}/{} ({:.1f}%)".format(
                threshold, count, len(max_probs), count / len(max_probs) * 100
            )
        )

    print("\n=== CONFIDENCE DISTRIBUTION ===")
    confs = confidence_values
    print(
        "  confidence: min={:.4f}, max={:.4f}, mean={:.4f}, std={:.4f}".format(
            min(confs), max(confs), mean(confs), stdev(confs)
        )
    )
    for threshold in [0.50, 0.60, 0.65, 0.70, 0.80, 0.95]:
        count = sum(1 for c in confs if c >= threshold)
        print(
            "  confidence >= {:.2f}: {}/{} ({:.1f}%)".format(
                threshold, count, len(confs), count / len(confs) * 100
            )
        )

    # ── False positive / false negative analysis ────────────────────────
    print("\n=== FALSE POSITIVE / FALSE NEGATIVE ANALYSIS ===")
    # False positive: approved but wrong direction
    fp = approved_trades["LONG_loss"] + approved_trades["SHORT_loss"]
    tp = approved_trades["LONG_win"] + approved_trades["SHORT_win"]
    print("  True positives (approved + correct): {}".format(tp))
    print("  False positives (approved + wrong): {}".format(fp))

    # False negatives: rejected but would have been correct
    fn_long_correct = 0
    fn_short_correct = 0
    fn_total_rejected = 0
    fn_atr_history = []
    fn_close_history = []
    for i in range(200, len(candles) - 1):
        fv = extract_features_pure(candles, i, SYMBOL, CID)
        if fv is None:
            continue

        fn_atr_history.append(fv.volatility.atr_14)
        fn_close_history.append(candles[i].close)
        if len(fn_atr_history) > 100:
            fn_atr_history = fn_atr_history[-100:]
            fn_close_history = fn_close_history[-100:]

        prob_up, prob_down = estimate_probabilities(fv, CID)
        regime = detect_regime(fn_atr_history, fn_close_history, CID)
        signal = evaluate_signal(fv, prob_up, prob_down, regime, CID)

        if not signal.is_actionable:
            fn_total_rejected += 1
            future_return = candles[i + 1].close - candles[i].close
            if signal.direction == SignalDirection.LONG and future_return > ZERO:
                fn_long_correct += 1
            elif signal.direction == SignalDirection.SHORT and future_return < ZERO:
                fn_short_correct += 1

    print("  False negatives (rejected but would-win LONG): {}".format(fn_long_correct))
    print("  False negatives (rejected but would-win SHORT): {}".format(fn_short_correct))
    print(
        "  Total rejected: {} | Would-have-won: {} ({:.1f}%)".format(
            fn_total_rejected,
            fn_long_correct + fn_short_correct,
            (fn_long_correct + fn_short_correct) / max(fn_total_rejected, 1) * 100,
        )
    )

    # ── Feature correlation with outcome ────────────────────────────────
    print("\n=== FEATURE VALUE vs 1-BAR OUTCOME (approved signals) ===")
    feature_win = {
        "rsi_14": [],
        "macd_histogram": [],
        "return_1": [],
        "atr_ratio": [],
        "volume_ratio": [],
    }
    feature_loss = {
        "rsi_14": [],
        "macd_histogram": [],
        "return_1": [],
        "atr_ratio": [],
        "volume_ratio": [],
    }

    fc_atr_history = []
    fc_close_history = []

    for i in range(200, len(candles) - 1):
        fv = extract_features_pure(candles, i, SYMBOL, CID)
        if fv is None:
            continue

        fc_atr_history.append(fv.volatility.atr_14)
        fc_close_history.append(candles[i].close)
        if len(fc_atr_history) > 100:
            fc_atr_history = fc_atr_history[-100:]
            fc_close_history = fc_close_history[-100:]

        prob_up, prob_down = estimate_probabilities(fv, CID)
        regime = detect_regime(fc_atr_history, fc_close_history, CID)
        signal = evaluate_signal(fv, prob_up, prob_down, regime, CID)

        if not signal.is_actionable:
            continue

        future_return = candles[i + 1].close - candles[i].close
        correct = False
        if signal.direction == SignalDirection.LONG and future_return > ZERO:
            correct = True
        elif signal.direction == SignalDirection.SHORT and future_return < ZERO:
            correct = True

        target = feature_win if correct else feature_loss
        target["rsi_14"].append(float(fv.momentum.rsi_14))
        target["macd_histogram"].append(float(fv.momentum.macd_histogram))
        target["return_1"].append(float(fv.momentum.return_1))
        target["atr_ratio"].append(float(fv.volatility.atr_ratio))
        target["volume_ratio"].append(float(fv.volume.volume_ratio))

    for feat in feature_win:
        w = feature_win[feat]
        l = feature_loss[feat]
        w_mean = mean(w) if w else 0
        l_mean = mean(l) if l else 0
        print(
            "  {}: WIN mean={:.6f} (n={}), LOSS mean={:.6f} (n={})".format(
                feat, w_mean, len(w), l_mean, len(l)
            )
        )


if __name__ == "__main__":
    main()

# Phase 14 — Final Validation Loop Report

Generated: 2026-03-30 00:45:40 UTC

## Verdict

**FREEZE DENIED**


- No threshold passes all acceptance gates.

## Threshold Sweep Summary

| Threshold | Runs | Profitable | Zero-Trade | Total Trades | Ranging | Mean PnL | CI Lo | CI Hi | Pass |
|-----------|------|------------|------------|--------------|---------|---------|-------|-------|------|
| 0.55 | 30 | 0.13 | 0.43 | 25 | 0 | -57.55 | -166.16 | 63.29 | FAIL |
| 0.60 | 30 | 0.13 | 0.43 | 25 | 0 | -53.23 | -163.06 | 70.16 | FAIL |
| 0.65 | 30 | 0.13 | 0.43 | 25 | 0 | -48.92 | -159.51 | 78.02 | FAIL |
| 0.70 | 30 | 0.13 | 0.43 | 25 | 0 | -44.17 | -156.09 | 90.26 | FAIL |
| 0.75 | 30 | 0.13 | 0.43 | 25 | 0 | -39.07 | -152.70 | 100.71 | FAIL |

## Gate Failures (by threshold)

### Threshold 0.55
- STRICT_TRADES: 25 < 53
- PROFITABLE_RATE: 0.13 < 0.65
- ZERO_TRADE_RATE: 0.43 > 0.35

### Threshold 0.60
- STRICT_TRADES: 25 < 53
- PROFITABLE_RATE: 0.13 < 0.65
- ZERO_TRADE_RATE: 0.43 > 0.35

### Threshold 0.65
- STRICT_TRADES: 25 < 53
- PROFITABLE_RATE: 0.13 < 0.65
- ZERO_TRADE_RATE: 0.43 > 0.35

### Threshold 0.70
- STRICT_TRADES: 25 < 53
- PROFITABLE_RATE: 0.13 < 0.65
- ZERO_TRADE_RATE: 0.43 > 0.35

### Threshold 0.75
- STRICT_TRADES: 25 < 53
- PROFITABLE_RATE: 0.13 < 0.65
- ZERO_TRADE_RATE: 0.43 > 0.35

## Walk-Forward Results

- Windows: 10
- Windows passing min trades: 0
- Min trades per window: 0
- Mean PnL per window: 0.00
- All pass: NO

| Window | Trades | PnL | Pass |
|--------|--------|-----|------|
| window_10_of_10 | 0 | 0.00 | FAIL |
| window_1_of_10 | 0 | 0.00 | FAIL |
| window_2_of_10 | 0 | 0.00 | FAIL |
| window_3_of_10 | 0 | 0.00 | FAIL |
| window_4_of_10 | 0 | 0.00 | FAIL |
| window_5_of_10 | 0 | 0.00 | FAIL |
| window_6_of_10 | 0 | 0.00 | FAIL |
| window_7_of_10 | 0 | 0.00 | FAIL |
| window_8_of_10 | 0 | 0.00 | FAIL |
| window_9_of_10 | 0 | 0.00 | FAIL |

## Stress Test Results

- **regime_flip_fast**: 5 runs, 1 trades, PnL=-547.02, ranging=0
- **regime_flip_slow**: 5 runs, 2 trades, PnL=-771.71, ranging=0
- **vol_shock_1_5x**: 5 runs, 2 trades, PnL=-729.86, ranging=0
- **vol_shock_2x**: 5 runs, 2 trades, PnL=-552.85, ranging=0
- **vol_shock_3x**: 5 runs, 2 trades, PnL=-55.36, ranging=0
- **missing_5pct**: 5 runs, 3 trades, PnL=-708.47, ranging=0
- **missing_15pct**: 5 runs, 6 trades, PnL=-225.10, ranging=0
- **latency_500ms**: 5 runs, 2 trades, PnL=-674.14, ranging=0

## Safety Audit

**FAILURES:**
- app\alpha\alpha_detector.py:373 — float() call detected
- app\alpha\alpha_detector.py:375 — float() call detected
- app\alpha\backtester.py:144 — float() call detected
- app\alpha\backtester.py:145 — float() call detected
- app\alpha\backtester.py:197 — float() call detected
- app\alpha\backtester.py:208 — float() call detected
- app\alpha\backtester.py:209 — float() call detected
- app\alpha\backtester.py:217 — float() call detected
- app\alpha\backtester.py:218 — float() call detected
- app\alpha\model_layer.py:176 — float() call detected
- app\logic\dual_mode_reasoner.py:556 — float() call detected
- app\logic\learning_features.py:158 — float() call detected
- app\logic\learning_features.py:161 — float() call detected
- app\logic\learning_features.py:162 — float() call detected
- app\logic\learning_features.py:163 — float() call detected
- app\logic\production_safety.py:206 — float() call detected
- app\logic\production_safety.py:208 — float() call detected
- app\logic\trade_permission_policy.py:1722 — float() call detected
- jobs\validation\simulation.py:384 — float() call detected
- jobs\robust_validation\datasets.py:87 — float() call detected
- jobs\robust_validation\evaluator.py:51 — float() call detected
- jobs\robust_validation\evaluator.py:52 — float() call detected
- jobs\robust_validation\safety.py:25 — float() call detected
- jobs\robust_validation\safety.py:51 — float() call detected
- D:\dev\repos\TRADE_BOT\app\logic\decision_packet_builder.py: missing required field 'regime'

---

[Sovereign Reliability Audit]
- Mock/Placeholder Check: [CLEAN]
- Decimal Integrity: [Verified]
- L6 Safety Compliance: [Verified]
- Traceability: [correlation_id present in all results]

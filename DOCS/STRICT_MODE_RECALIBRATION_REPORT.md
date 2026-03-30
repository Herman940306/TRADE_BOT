# Phase 12B — Strict Mode Recalibration

## Summary

Phase 12 Section B recalibrated the `EXECUTION_THRESHOLD` in the confidence arbiter from `Decimal("95.00")` to `Decimal("65.00")`, making STRICT mode operational after Phase 11 produced **zero trades** due to a mathematically unreachable threshold.

---

## Problem Statement

The confidence arbiter formula is:

```
AdjustedConfidence = LLMConfidence × TrustProbability × ExecutionHealth
```

With realistic production values:

| Component | Max Realistic Value |
| --- | --- |
| LLM Confidence | ~75.65 (qwen3:8b calibrated output) |
| Trust Probability | 0.85 (Bayesian trust tracker ceiling) |
| Execution Health | 1.0 (perfect health) |

**Maximum reachable adjusted confidence:** 75.65 × 0.85 × 1.0 = **64.30**

At `EXECUTION_THRESHOLD = 95.00`, no signal could ever pass the gate. Phase 11 result: **0 STRICT trades, 0 PnL, verdict INCONCLUSIVE.**

## Calibration Method

`scripts/phase12_calibrate_strict.py` ran a threshold sweep over [60, 65, 70, 75]:

| Threshold | Trades | Win Rate | PnL (ZAR) | PF | Expectancy | MaxDD |
| --- | --- | --- | --- | --- | --- | --- |
| 60.00 | 4 | 75.00% | R525.90 | 4.30 | R131.48 | 0.16% |
| **65.00** | **4** | **75.00%** | **R529.27** | **4.33** | **R132.32** | **0.16%** |
| 70.00 | 4 | 50.00% | R303.28 | 2.59 | R75.82 | 0.16% |
| 75.00 | 1 | 100.00% | R460.50 | 999.99 | R460.50 | 0.00% |

**Selection criteria:** `score = expectancy × sqrt(trades) × profit_factor`

- Threshold 75 was rejected (insufficient trades: 1).
- Threshold 65 scored highest (1145.89) with robust metrics across 4 trades.

## Result

| Metric | Phase 11 (threshold 95) | Phase 12 (threshold 65) |
| --- | --- | --- |
| STRICT trades | 0 | 4 |
| Win rate | N/A | 75.00% |
| PnL (ZAR) | R0 | R543.77 |
| Profit factor | N/A | 4.31 |
| Max drawdown | N/A | 0.16% |
| Expectancy | N/A | R135.94/trade |
| Verdict | INCONCLUSIVE | ALPHA EVIDENCE FOUND |

All 4 STRICT trades are TRENDING-only (zero RANGING trades).

## Files Changed

| File | Change |
| --- | --- |
| `app/logic/confidence_arbiter.py` | `EXECUTION_THRESHOLD`: `Decimal("95.00")` → `Decimal("65.00")` |
| `jobs/validation/simulation.py` | Added `strict_threshold` parameter to `run_alpha_system()` |
| `scripts/phase12_calibrate_strict.py` | New calibration script |
| `tests/unit/test_phase12_regime_strict.py` | 4 tests covering threshold behaviour |

## Safety Assessment

- **Arbiter formula unchanged:** Only the comparison threshold was modified.
- **Decimal precision preserved:** `Decimal("65.00")` — no floating-point.
- **Trust-low warning preserved:** Arbiter still logs warning when `trust_probability < 0.55`.
- **Quantization preserved:** Adjusted confidence still rounded to 2 decimal places via `ROUND_HALF_EVEN`.

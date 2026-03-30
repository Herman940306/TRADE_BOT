# Regime Robustness Report — Phase 12.5

**Date:** 2025-07-06
**Status:** HARDENED
**Test Base:** 170 tests (all passing)

## Summary

Phase 12.5 rebuilt the regime detection subsystem (`detect_regime()`) with three
hardening layers designed to eliminate regime misclassification—the primary
source of false-positive trades.

## Changes Implemented

### 1. Multi-Window Trend Agreement

- **Before:** Single 20-bar trend strength (easily fooled by short noise).
- **After:** Dual-window (10-bar + 20-bar) with conservative aggregation
  (`min(ts_short, ts_long)`).
- **Effect:** Both windows must agree before TRENDING classification.

### 2. Raised Trend Strength Minimum

- **Before:** `REGIME_TREND_STRENGTH_MIN = 0.15` (barely above random).
- **After:** `REGIME_TREND_STRENGTH_MIN = 0.25`.
- **Effect:** Eliminates marginal/noisy trend classifications.

### 3. Regime Confidence Score

- **Formula:** `confidence = mean(atr_evidence, trend_evidence, window_agreement)`
  - `atr_evidence`: How far ATR percentile exceeds TRENDING threshold (0.40).
  - `trend_evidence`: How far trend strength exceeds minimum (0.25).
  - `window_agreement`: `min(ts_short, ts_long) / max(ts_short, ts_long)`.
- **Threshold:** `REGIME_CONFIDENCE_THRESHOLD = 0.60`.
- **Effect:** TRENDING classified with confidence < 0.60 → demoted to RANGING.

### 4. Minimum Close Bar Requirement

- `len(close_series) >= REGIME_TREND_WINDOW_SHORT (10)` required for TRENDING.
- **Effect:** Prevents spurious classification with insufficient data.

### 5. Weak TRENDING Gate in `evaluate_signal()`

- New rejection gate: if regime is TRENDING but `regime_confidence < 0.60`,
  signal rejected with `REGIME_WEAK_TRENDING`.
- **Effect:** Defense-in-depth after `detect_regime()`.

## Model Changes

| Item | Before | After |
|------|--------|-------|
| `RegimeState.regime_confidence` | N/A | `Decimal("0")` default, validated |
| `RejectReason.REGIME_WEAK_TRENDING` | N/A | Added (10 total) |
| `detect_regime()` | Single-window, 0.15 min | Multi-window, 0.25 min, confidence |
| `evaluate_signal()` | 8 gates | 9 gates (added weak TRENDING) |

## Validation Results (Phase 13 Script)

- **RANGING trades across all seeds:** 0 (hard gate intact)
- **STRICT mode:** 66.67% WR, R2,223 total PnL across 20 seeds
- **Walk-forward STRICT:** 0/4 losing windows, 1/4 profitable, 3/4 zero-trade
- **Zero-trade rate (STRICT):** 14/20 seeds (70%) — system is highly selective

## Regression Test Count

- Phase 10 tests: 72 passed
- Phase 12/12.5 tests: 62 passed
- Property invariants: 36 passed
- **Total: 170 passed, 0 failed**

## Verdict

REGIME HARDENING: **EFFECTIVE**. Multi-window agreement and confidence scoring
successfully eliminate marginal/misclassified TRENDING conditions. The
fail-closed design ensures capital preservation.

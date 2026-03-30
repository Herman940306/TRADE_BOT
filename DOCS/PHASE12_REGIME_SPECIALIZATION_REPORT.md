# Phase 12A — Regime Specialization: Hard RANGING Gate

## Summary

Phase 12 Section A introduced a **hard regime gate** that unconditionally rejects all signals generated during RANGING market conditions. This eliminates the largest source of losses identified in Phase 11's root cause analysis.

---

## Problem Statement

Phase 11 revealed that the RANGING regime produced **zero edge**:

| Regime | Trades | Win Rate | PnL (ZAR) | Profit Factor |
| --- | --- | --- | --- | --- |
| TRENDING | 11 | 81.8% | R+3,098 | 4.84 |
| RANGING | 18 | 33.3% | R-2,114 | 0.38 |
| VOLATILE | 0 | — | — | — |

RANGING trades accounted for **62% of all trades** and **100% of net losses**. The momentum-persistence strategy has no structural edge in range-bound markets — signals are directionally random with sub-50% accuracy.

## Solution

### Hard Gate in `evaluate_signal()`

A regime check was added **before** all downstream probability and multi-factor gates in `app/alpha/signal_decision.py`:

```python
if regime.regime == RegimeType.RANGING:
    reject_reasons.append(RejectReason.REGIME_REJECT_RANGING)
```

This fires immediately on entry to `evaluate_signal()`, preventing any RANGING signal from reaching probability estimation, multi-factor confirmation, or conflict detection.

### New Enum Value

`RejectReason.REGIME_REJECT_RANGING` was added to `app/alpha/models.py`. The enum now has 9 values (was 8). All existing values are unchanged.

## Results

| Metric | Phase 11 | Phase 12 |
| --- | --- | --- |
| RANGING trades approved | 18 | 0 |
| RANGING signals rejected | ~200 | 220/220 (100%) |
| TRENDING trades approved | 11 | 9 |
| Total PnL (HYPO) | R+984.86 | R+2,397.46 |

All approved trades are now exclusively in the TRENDING regime.

## Files Changed

| File | Change |
| --- | --- |
| `app/alpha/models.py` | Added `REGIME_REJECT_RANGING` to `RejectReason` enum |
| `app/alpha/signal_decision.py` | Added hard RANGING gate before probability check |
| `tests/unit/test_phase12_regime_strict.py` | 10 tests covering RANGING rejection |
| `tests/unit/test_phase10_alpha_detection.py` | Updated `test_reject_reason_count` from 8 to 9 |

## Safety Assessment

- **Fail-closed preserved:** All existing rejection gates (VOLATILE, probability, ATR, conflict, outlier) remain unchanged and tested.
- **No floating-point math:** Regime comparison uses enum identity, not numeric thresholds.
- **Reversible:** Removing the 2-line gate restores Phase 11 behaviour.

# Alpha Diagnosis Report
**Project Autonomous Alpha v4.1.0**
**Generated:** 2026-03-29 21:56:53 UTC
**Correlation ID:** PTV-75d6c8dcc36c

---

## Diagnosis Summary

**Total Decisions Evaluated:** 300
**Primary Bottleneck:** SIGNAL_QUALITY — Most signals rejected by Alpha Detection Layer

---

## Rejection Funnel

| Decision Outcome | Count | Percentage |
|-----------------|-------|------------|
| SIGNAL_REJECTED_QUALITY | 208 | 69.33% |
| SIGNAL_REJECTED_CONFIDENCE | 92 | 30.67% |

---

## Regime Analysis
*No executed trades to analyze by regime.*

---

## Direction Accuracy
*No executed trades to analyze direction accuracy.*

---

## Confidence Gate Analysis

The 95% confidence gate is the most aggressive filter in the pipeline.
| Confidence Band | Count |
|----------------|-------|
| 95-100% | 0 |
| 80-95% | 26 |
| 60-80% | 17 |
| 0-60% | 257 |

**Signals passing 95% gate:** 0
**Signals blocked by 95% gate:** 300

### Confidence Gate Impact

The ConfidenceArbiter formula is:
```
AdjustedConfidence = LLMConfidence x TrustProbability x ExecutionHealth
```
For a signal with 80% raw confidence and 0.85 trust:
- Adjusted = 80 x 0.85 x 1.0 = 68.00 → **BLOCKED** (< 95%)

This means only signals with very high raw confidence AND high trust pass.
The 95% gate is designed for capital preservation (Sovereign Mandate).

---

## Key Findings
1. Signal quality filter is the primary bottleneck: 208 rejected vs 0 approved.
2. System outperforms both baselines: Alpha=0 vs Random=-3610.45 vs EMA=-439.73
3. Approval rate: 0.00% (0/300 signals approved for execution).

---

## HITL Impact

N/A — No HITL overrides in simulation mode

---

## Recommendations

1. The signal quality filters are catching low-quality setups correctly.
2. Consider whether the probability threshold (0.70) is appropriate for current market conditions.
3. Review regime detection — VOLATILE regime rejection may be filtering valid signals.

---

*Correlation ID: PTV-75d6c8dcc36c*

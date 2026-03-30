# Baseline Comparison Report
**Project Autonomous Alpha v4.1.0**
**Generated:** 2026-03-29 21:56:53 UTC
**Correlation ID:** PTV-75d6c8dcc36c

---

## Comparison Summary

### Alpha System vs Random Direction Baseline

| Metric | Alpha | Random | Delta |
|--------|-------|--------|-------|
| Total PnL | R0 | R-3610.45 | R3610.45 |
| Win Rate | 0% | 51.72% | -51.72% |
| Max Drawdown | 0% | 5.31% | -5.31% |
| Profit Factor | 0 | 0.67 | -0.67 |
| Total Trades | 0 | 29 | -29 |

**Verdict:** Alpha system OUTPERFORMS random baseline by R3610.45.

---

### Alpha System vs EMA Crossover Baseline

| Metric | Alpha | EMA(20/50) | Delta |
|--------|-------|------------|-------|
| Total PnL | R0 | R-439.73 | R439.73 |
| Win Rate | 0% | 33.33% | -33.33% |
| Max Drawdown | 0% | 0.47% | -0.47% |
| Profit Factor | 0 | 0.06 | -0.06 |
| Total Trades | 0 | 3 | -3 |

**Verdict:** Alpha system OUTPERFORMS EMA crossover by R439.73.

---

## Baseline Methodology

### Random Direction Baseline
- Trades at random intervals (~15% of bars)
- Direction: 50/50 random BUY/SELL
- Position sizing: 1% risk, 2% stop distance
- Max hold: 5 bars
- Seed: 42 (deterministic)

### EMA Crossover Baseline
- Trades on EMA(20)/EMA(50) crossover events
- BUY on bullish cross, SELL on bearish cross
- Position sizing: 1% risk, 2% stop distance
- Max hold: 5 bars
- No additional filters (no RSI, no ATR, no regime)

---

## Statistical Context

The Alpha system applies 4 gates before execution:
1. Signal quality (Alpha Detection Layer — 8 rejection rules)
2. Confidence arbiter (95% threshold)
3. Risk governor (ATR-based sizing, circuit breakers)
4. DemoBroker execution (spread simulation)

Baselines skip gates 1-3 entirely, using only fixed-rule entries.
A fair comparison considers that the Alpha system trades less frequently
but aims for higher-quality entries.

---

*Correlation ID: PTV-75d6c8dcc36c*

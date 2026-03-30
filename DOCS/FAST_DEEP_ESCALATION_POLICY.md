# Fast/Deep Escalation Policy

## Project Autonomous Alpha — Phase 8

**Reliability Level:** SOVEREIGN TIER (Mission-Critical)
**Version:** 1.0.0
**Status:** ACTIVE
**Author:** Kiro Agent (Lead Reliability Engineer)
**Created:** 2026-03-29
**Reference:** DUAL_MODE_REASONING_PLAN.md §6

---

## 1. Purpose

This document defines the deterministic escalation policy that governs when a trade signal is routed from FAST mode to DEEP mode reasoning. All escalation decisions are:

- **Deterministic** — same inputs produce same escalation decision
- **Transparent** — every trigger is coded and logged
- **Auditable** — full escalation trail persisted per signal
- **Fail-Closed** — escalation failure defaults to REJECTED

---

## 2. Escalation Triggers

### 2.1 Confidence-Based Triggers

| Code | Trigger | Threshold | Source |
|------|---------|-----------|--------|
| `ESC-T01` | FAST confidence band = LOW | confidence_band == "LOW" | FAST mode response |
| `ESC-T02` | FAST reason code is ESCALATE-class | reason_code starts with "FAST-ESCALATE" | FAST mode response |

### 2.2 Data-Completeness Triggers

| Code | Trigger | Threshold | Source |
|------|---------|-----------|--------|
| `ESC-T03` | Missing T2 advisory fields | ≥ 2 (OPERATIONAL) or ≥ 4 (COLD_START) | Decision packet |
| `ESC-T04` | Missing T1 required fields | ≥ 1 | Decision packet |

### 2.3 Signal-Quality Triggers

| Code | Trigger | Threshold | Source |
|------|---------|-----------|--------|
| `ESC-T05` | Contradicting signal indicators | bull_signal vs bear_signal conflict | Pre-computed analysis |
| `ESC-T06` | Elevated risk profile | risk_governor concern flag active | Risk Governor |

### 2.4 Operational Triggers

| Code | Trigger | Threshold | Source |
|------|---------|-----------|--------|
| `ESC-T07` | Degraded provider context | degraded_context == True | AIBackendReliabilityManager |
| `ESC-T08` | Provider fallback active | provider_used != PRIMARY | Routing audit trail |
| `ESC-T09` | High notional value | notional ≥ R5,000 (paper) / configurable | Trade parameters |

### 2.5 Policy Triggers

| Code | Trigger | Threshold | Source |
|------|---------|-----------|--------|
| `ESC-T10` | Manual deep-mode override | Operator-configured flag for symbol/condition | Configuration |

---

## 3. Escalation Rules

### 3.1 Core Rules

| # | Rule | Rationale |
|---|------|-----------|
| R1 | Any single trigger from §2 can invoke DEEP mode | Conservative approach — single concern justifies deeper analysis |
| R2 | 3+ simultaneous triggers = DEEP mode MANDATORY | Strong evidence of complexity |
| R3 | Escalation allowed exactly ONCE per signal | Prevents loops and resource exhaustion |
| R4 | DEEP failure does NOT return to FAST | DEEP verdict (even REJECTED) is final |
| R5 | Escalation decision is logged before DEEP execution | Audit trail integrity |
| R6 | Escalation trigger evaluation runs BEFORE model call | Separation of concerns |

### 3.2 Cold-Start Awareness

| System Maturity | Criteria | Effect on Triggers |
|----------------|----------|-------------------|
| COLD_START | < 20 completed debates | T2 missing threshold raised to ≥ 4 (ESC-T03 only) |
| OPERATIONAL | ≥ 20 completed debates | All thresholds at standard levels |

Cold-start maturity is checked via a counter of completed debates. The threshold is configurable but defaults to 20.

### 3.3 Stacking Rules

When multiple triggers fire simultaneously:

- All active trigger codes are recorded in the audit entry
- The escalation reason includes the full trigger list
- DEEP mode prompt receives the trigger list as context
- No priority ordering — any trigger is sufficient

---

## 4. Escalation Flow

```
Signal arrives
  │
  ▼
Build decision packet (mode-agnostic)
  │
  ▼
Execute FAST mode reasoning
  │
  ├─ FAST returns HIGH confidence, no escalation triggers → USE FAST VERDICT
  │
  ├─ FAST returns ESCALATE reason code → ESCALATE
  │
  └─ Check independent escalation triggers
      │
      ├─ No triggers → USE FAST VERDICT
      │
      └─ 1+ triggers → ESCALATE
          │
          ▼
     Build DEEP mode packet (expanded context)
          │
          ▼
     Execute DEEP mode reasoning
          │
          ├─ DEEP resolves → USE DEEP VERDICT
          │
          └─ DEEP fails/rejects → FINAL REJECT (fail-closed)
```

---

## 5. Reject Codes After Escalation Failure

| Code | Meaning | When Applied |
|------|---------|-------------|
| `ESC-REJECT-UNRESOLVED` | DEEP mode analyzed but could not resolve ambiguity | DEEP returns DEEP-REJECT-UNRESOLVED |
| `ESC-REJECT-TIMEOUT` | DEEP mode exceeded 60s timeout | httpx.TimeoutException |
| `ESC-REJECT-ERROR` | DEEP mode internal error | Exception during DEEP execution |
| `ESC-REJECT-BUDGET-OVERFLOW` | DEEP packet exceeded token budget | TokenBudgetGuard check failed |
| `ESC-REJECT-LOOP-DETECTED` | Second escalation attempt detected | Logic guard (should never occur) |

---

## 6. Audit Trail Format

Every escalation decision produces a structured audit entry:

```json
{
  "correlation_id": "uuid",
  "timestamp_utc": "ISO-8601",
  "escalation_decision": "ESCALATED | NOT_ESCALATED",
  "trigger_codes": ["ESC-T01", "ESC-T03"],
  "trigger_count": 2,
  "system_maturity": "OPERATIONAL",
  "fast_confidence_band": "LOW",
  "fast_reason_code": "FAST-ESCALATE-AMBIGUITY",
  "deep_verdict": "DEEP-APPROVE-RESOLVED | null",
  "final_outcome": "APPROVED | REJECTED",
  "escalation_latency_ms": 15200,
  "mode_used": "DEEP"
}
```

---

## 7. Monitoring

### 7.1 Prometheus Metrics

| Metric | Type | Labels | Purpose |
|--------|------|--------|---------|
| `reasoning_escalation_total` | Counter | trigger_code | Count escalations by trigger type |
| `reasoning_escalation_rate` | Gauge | — | Ratio of escalated vs total signals |
| `reasoning_mode_selected` | Counter | mode | Count FAST vs DEEP selections |
| `reasoning_deep_resolve_rate` | Gauge | — | % of DEEP invocations that resolved successfully |

### 7.2 Alerts

| Alert | Condition | Action |
|-------|-----------|--------|
| High escalation rate | escalation_rate > 0.40 for 15 minutes | Review trigger thresholds |
| DEEP timeout rate | DEEP timeout > 20% | Check Ollama health, model load |
| Zero FAST usage | 100% DEEP for 30 minutes | Verify cold-start logic, trigger calibration |

---

## 8. Configuration

All escalation thresholds are configurable via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `ESCALATION_T2_MISSING_THRESHOLD` | 2 | T2 missing fields to trigger escalation |
| `ESCALATION_T2_MISSING_COLD_START` | 4 | T2 missing fields threshold during cold start |
| `ESCALATION_COLD_START_DEBATES` | 20 | Number of debates before transitioning to OPERATIONAL |
| `ESCALATION_HIGH_NOTIONAL_PAPER` | 5000 | Notional value threshold for paper mode (ZAR) |
| `DEEP_MODE_FORCE_SYMBOLS` | "" | Comma-separated symbols that always use DEEP mode |
| `DEEP_MODE_TIMEOUT_SECONDS` | 60 | Maximum DEEP mode execution time |

---

## 9. Revision History

| Date | Version | Change | Author |
|------|---------|--------|--------|
| 2026-03-29 | 1.0.0 | Initial creation (Phase 8) | Kiro Agent |

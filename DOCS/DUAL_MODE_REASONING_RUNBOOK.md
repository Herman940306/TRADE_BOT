# Dual-Mode Reasoning Runbook

## Project Autonomous Alpha — Phase 8

**Reliability Level:** SOVEREIGN TIER (Mission-Critical)
**Version:** 1.0.0
**Status:** ACTIVE
**Author:** Kiro Agent (Lead Reliability Engineer)
**Created:** 2026-03-29
**Reference:** DUAL_MODE_REASONING_PLAN.md, FAST_DEEP_ESCALATION_POLICY.md

---

## 1. Overview

This runbook describes how to operate, monitor, and troubleshoot the dual-mode reasoning system for Autonomous Alpha. The system uses a single local model (qwen3:8b via Ollama) in two distinct reasoning modes:

- **FAST mode:** Low-latency, structured decisioning for routine signals
- **DEEP mode:** Deliberate, contradiction-aware analysis for ambiguous or high-risk signals

---

## 2. Normal Operation

### 2.1 Expected Behavior

- ~70-80% of signals should run in FAST mode during normal operation
- ~20-30% of signals should escalate to DEEP mode
- During cold start (< 20 debates), higher DEEP rates are expected and acceptable

### 2.2 Startup Checklist

1. Verify Ollama is running: `curl http://ollama:11434/api/tags`
2. Verify qwen3:8b is loaded: Check response includes `qwen3:8b`
3. Verify reasoning mode system is initialized (check application logs for `DualModeReasoner initialized`)
4. Verify system maturity state in logs: `COLD_START` or `OPERATIONAL`

### 2.3 Key Log Messages

| Log Pattern | Meaning |
|-------------|---------|
| `[DUAL-MODE] FAST mode selected` | Signal processing in FAST mode |
| `[DUAL-MODE] DEEP mode selected (escalated)` | Signal escalated to DEEP mode |
| `[DUAL-MODE] Escalation triggers: [...]` | Which triggers caused escalation |
| `[DUAL-MODE] Maturity transition: COLD_START → OPERATIONAL` | System passed cold-start threshold |

---

## 3. Monitoring

### 3.1 Key Metrics

| Metric | Healthy Range | Alert Threshold |
|--------|---------------|-----------------|
| `reasoning_escalation_rate` | 0.15 - 0.35 | > 0.40 for 15 min |
| `reasoning_latency_seconds{mode="FAST"}` p95 | < 8s | > 12s |
| `reasoning_latency_seconds{mode="DEEP"}` p95 | < 20s | > 45s |
| `reasoning_deep_resolve_rate` | > 0.60 | < 0.30 |

### 3.2 Grafana Dashboard

Panel recommendations:

1. **Mode Distribution** — Pie chart of FAST vs DEEP usage
2. **Escalation Rate** — Time series of `reasoning_escalation_rate`
3. **Latency by Mode** — Dual histogram for FAST/DEEP latency
4. **Trigger Frequency** — Bar chart of escalation triggers by code
5. **Deep Resolve Rate** — Success rate of DEEP mode resolutions

---

## 4. Troubleshooting

### 4.1 High Escalation Rate (> 40%)

**Symptoms:** Most signals going to DEEP mode, increased latency.

**Diagnosis:**

1. Check `reasoning_escalation_triggers` counter — which trigger dominates?
2. If `ESC-T03` (missing T2 fields) dominates → Check if data sources are offline
3. If `ESC-T01` (low confidence) dominates → Model may need health check
4. If `ESC-T07` (degraded provider) dominates → Check Ollama health

**Resolution:**

- If data sources are offline: Fix data ingestion, not escalation policy
- If model quality degraded: Restart Ollama, verify model integrity
- If cold-start: Wait for 20 debates to complete, confirm maturity transition
- If chronic: Review `ESCALATION_T2_MISSING_THRESHOLD` configuration

### 4.2 DEEP Mode Timeouts

**Symptoms:** `ESC-REJECT-TIMEOUT` codes appearing, latency spikes.

**Diagnosis:**

1. Check Ollama GPU utilization: `nvidia-smi`
2. Check if model is loaded: `curl http://ollama:11434/api/tags`
3. Check concurrent request load on Ollama
4. Verify `DEEP_MODE_TIMEOUT_SECONDS` setting

**Resolution:**

- If GPU overloaded: Reduce concurrent requests, add request queuing
- If model unloaded: Pull model again, check Ollama memory settings
- If latency is inherent: Increase timeout (cautiously) or reduce DEEP input budget

### 4.3 100% FAST Mode (No Escalation)

**Symptoms:** No signals ever reach DEEP mode.

**Diagnosis:**

1. Check escalation trigger evaluation is running (logs)
2. Verify trigger thresholds are not set too high
3. Check if all T2 fields are always present (unlikely during early operation)

**Resolution:**

- Verify `EscalationPolicy` is wired into `DualModeReasoner`
- Send a test signal with deliberately missing fields
- Check environment variable overrides

### 4.4 Escalation Loop Detected

**Symptoms:** `ESC-REJECT-LOOP-DETECTED` in logs.

**Diagnosis:**
This should NEVER happen in production. It indicates a code defect in the dual-mode reasoner.

**Resolution:**

1. Capture full log context around the event
2. File severity-1 incident
3. Signal is safely REJECTED (fail-closed behavior working)
4. Investigate code path that allowed second escalation attempt

---

## 5. Configuration Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `ESCALATION_T2_MISSING_THRESHOLD` | 2 | T2 missing fields trigger (OPERATIONAL mode) |
| `ESCALATION_T2_MISSING_COLD_START` | 4 | T2 missing fields trigger (COLD_START mode) |
| `ESCALATION_COLD_START_DEBATES` | 20 | Debates before OPERATIONAL |
| `ESCALATION_HIGH_NOTIONAL_PAPER` | 5000 | Notional threshold for paper mode (ZAR) |
| `DEEP_MODE_FORCE_SYMBOLS` | "" | Always DEEP for these symbols |
| `DEEP_MODE_TIMEOUT_SECONDS` | 60 | Max DEEP execution time |

---

## 6. Emergency Procedures

### 6.1 Disable DEEP Mode Entirely

If DEEP mode is causing operational issues:

```bash
export DEEP_MODE_FORCE_DISABLED=true
```

This forces ALL signals to use FAST mode only. Escalation policy still evaluates but DEEP mode is never invoked. Signals that would have escalated are REJECTED with `ESC-REJECT-DEEP-DISABLED`.

**WARNING:** This reduces decision quality for ambiguous signals. Use only as temporary measure.

### 6.2 Force DEEP Mode for All Signals

If FAST mode quality is suspect:

```bash
export FAST_MODE_FORCE_DISABLED=true
```

All signals go through DEEP mode. Higher latency but maximum analysis depth. Use during investigation only.

---

## 7. Revision History

| Date | Version | Change | Author |
|------|---------|--------|--------|
| 2026-03-29 | 1.0.0 | Initial creation (Phase 8) | Kiro Agent |

# AI Backend Runbook

## Project Autonomous Alpha — Phase 7

**Reliability Level:** SOVEREIGN TIER (Mission-Critical)
**Version:** 1.0.0

---

## 1. System Health Check

### Quick Status

Check the current health of all AI backends via the reliability manager:

```python
from app.logic.ai_backend_reliability import AIBackendReliabilityManager
mgr = AIBackendReliabilityManager()
report = mgr.get_health_report()
print(report)
```

Output structure:

```json
{
  "LOCAL_OLLAMA": {
    "status": "HEALTHY",
    "consecutive_failures": 0,
    "last_failure_class": null,
    "cooldown_until": null,
    "last_success_at": "2025-01-15T10:30:00Z",
    "last_failure_at": null
  },
  "OPENROUTER": {
    "status": "HEALTHY",
    "consecutive_failures": 0,
    ...
  }
}
```

### Verify Ollama Connectivity

```bash
curl http://<NAS_IP>:11434/api/tags
```

Expected: JSON listing available models including `qwen3:8b`.

### Verify OpenRouter Connectivity

```bash
curl -H "Authorization: Bearer $OPENROUTER_API_KEY" \
     https://openrouter.ai/api/v1/models | head -20
```

Expected: JSON listing available models.

---

## 2. Common Failure Scenarios

### Scenario: Ollama Unreachable

**Symptoms:**

- `FailureClass.LOCAL_UNREACHABLE` in audit trail
- Trades routed to OpenRouter (in LOCAL_PREFERRED mode)

**Diagnosis:**

1. Check NAS is online and Ollama container is running
2. Verify network connectivity to NAS IP on port 11434
3. Check Ollama container logs: `docker logs ollama`

**Recovery:**

1. Restart Ollama container on NAS
2. Verify model availability: `curl http://<NAS_IP>:11434/api/tags`
3. Cooldown will expire automatically (60s base; 300s if 3+ consecutive failures)
4. Next trade signal will probe and restore HEALTHY status on success

### Scenario: Ollama Model Missing

**Symptoms:**

- `FailureClass.LOCAL_MODEL_MISSING` in audit trail
- 300s cooldown applied

**Diagnosis:**

1. Check model list: `curl http://<NAS_IP>:11434/api/tags`
2. Verify `OLLAMA_MODEL` env var matches an available model

**Recovery:**

1. Pull the model: `curl -X POST http://<NAS_IP>:11434/api/pull -d '{"name":"qwen3:8b"}'`
2. Wait for pull to complete
3. Cooldown will expire in 300s (or 1500s if extended)

### Scenario: OpenRouter Auth Failed

**Symptoms:**

- `FailureClass.CLOUD_AUTH_FAILED` in audit trail
- 3600s (1 hour) cooldown applied
- System falls back to Ollama (in CLOUD_PREFERRED mode) or fails closed (in CLOUD_ONLY mode)

**Diagnosis:**

1. Check `OPENROUTER_API_KEY` environment variable is set
2. Verify key validity at <https://openrouter.ai/settings/keys>

**Recovery:**

1. Generate new API key if revoked
2. Update `.env` with new key
3. Restart application to pick up new key
4. Alternatively, wait for 1-hour cooldown to expire

### Scenario: OpenRouter Credits Exhausted

**Symptoms:**

- `FailureClass.CLOUD_CREDITS_EXHAUSTED` in audit trail
- 3600s cooldown applied

**Recovery:**

1. Add credits at <https://openrouter.ai/settings/credits>
2. Or switch to `LOCAL_ONLY` mode: `AI_PROVIDER_MODE=LOCAL_ONLY`
3. Cooldown will expire in 1 hour

### Scenario: Both Backends Down

**Symptoms:**

- `FailureClass.ALL_BACKENDS_UNAVAILABLE` in audit trail
- All trades rejected (fail-closed)
- `provider_used = "NONE"` in routed results

**Diagnosis:**

1. Check both backend health reports
2. Verify network connectivity
3. Check for infrastructure-wide outage

**Recovery:**

1. Restore at least one backend to service
2. If Ollama: restart container, verify model
3. If OpenRouter: verify API key and credits
4. System will auto-recover on next successful probe

### Scenario: Rate Limiting (OpenRouter)

**Symptoms:**

- `FailureClass.CLOUD_RATE_LIMITED` in audit trail
- 120s cooldown applied
- System falls back to Ollama

**Recovery:**

- Automatic: 120s cooldown will expire
- Reduce request frequency if persistent
- Consider upgrading OpenRouter plan

---

## 3. Mode Management

### Check Current Mode

```python
import os
mode = os.environ.get("AI_PROVIDER_MODE", "LOCAL_PREFERRED")
print(f"Current mode: {mode}")
```

### Switch Mode at Runtime

Update the environment variable and restart the application:

```bash
# For local-only operation (no cloud dependency)
export AI_PROVIDER_MODE=LOCAL_ONLY

# For cloud-preferred (faster models, costs money)
export AI_PROVIDER_MODE=CLOUD_PREFERRED

# For maximum safety (both must agree)
export AI_PROVIDER_MODE=STRICT_DUAL_REQUIRED
```

### Mode Selection Guide

| Scenario | Recommended Mode |
|----------|-----------------|
| Normal operation (NAS available) | `LOCAL_PREFERRED` (default) |
| NAS offline / maintenance | `CLOUD_ONLY` |
| OpenRouter key expired / no credits | `LOCAL_ONLY` |
| High-value trade / elevated risk | `STRICT_DUAL_REQUIRED` |
| Testing cloud integration | `CLOUD_PREFERRED` |

---

## 4. Cooldown Management

### View Current Cooldowns

```python
mgr = AIBackendReliabilityManager()
report = mgr.get_health_report()
for backend, health in report.items():
    if health.get("cooldown_until"):
        print(f"{backend}: cooldown until {health['cooldown_until']}")
```

### Force Reset (Emergency Only)

If a backend is stuck in cooldown and you have verified it is healthy:

```python
mgr = AIBackendReliabilityManager()
mgr._registry.reset(BackendId.LOCAL_OLLAMA)
# Or: mgr._registry.reset(BackendId.OPENROUTER)
```

**Warning:** Only use this if you have manually verified the backend is operational. Premature reset can cause request storms against a failing backend.

---

## 5. Audit Trail Inspection

Every `RoutedDebateResult` contains a full audit trail:

```python
result = await mgr.route_debate(
    correlation_id="test-123",
    symbol="BTCZAR",
    side="BUY",
    price=Decimal("1500000"),
    quantity=Decimal("0.001")
)

# Inspect routing decision
print(f"Provider used: {result.provider_used}")
print(f"Routing reason: {result.routing_decision.reason}")
print(f"Final verdict: {result.final_verdict}")
print(f"Rejected: {result.is_rejected}")

# Inspect each audit entry
for entry in result.audit_trail:
    print(f"  {entry.backend_id} [{entry.role}]: {entry.outcome} "
          f"({entry.duration_ms}ms)")
    if entry.failure_class:
        print(f"    Failure: {entry.failure_class} - {entry.error_detail}")
```

---

## 6. Monitoring Checklist

| Check | Frequency | Action if Failed |
|-------|-----------|-----------------|
| Ollama container running | Every 5 min | Restart container |
| Ollama model available | Daily | Pull model |
| OpenRouter API key valid | Daily | Rotate key |
| OpenRouter credits > 0 | Daily | Add credits or switch to LOCAL_ONLY |
| Both backends in HEALTHY | Continuous | Investigate failures |
| Cooldown count trending up | Hourly | Investigate root cause |
| Consecutive failures ≥ 3 | Per occurrence | Manual investigation required |
| Trade rejections due to AI failure | Per occurrence | Check audit trail, restore backend |

---

## 7. Emergency Procedures

### Complete AI Subsystem Failure

1. **Immediate:** All trades will be rejected (fail-closed). No capital at risk.
2. **Diagnose:** Check both backend health reports
3. **Restore:** Fix the most accessible backend first (usually Ollama)
4. **Verify:** Send a test signal and confirm debate completes
5. **Monitor:** Watch for recurring failures in the next hour

### Planned Maintenance (Ollama/NAS)

1. Switch to `CLOUD_ONLY` mode before taking NAS offline
2. Verify OpenRouter is healthy and has credits
3. Perform maintenance
4. Switch back to `LOCAL_PREFERRED` after NAS is restored
5. Verify Ollama model is available

# AI Provider Policy

## Project Autonomous Alpha — Phase 7

**Reliability Level:** SOVEREIGN TIER (Mission-Critical)
**Version:** 1.1.0
**Module:** `app/logic/ai_backend_reliability.py`

---

## 1. Provider Modes

The system supports five provider modes controlling which AI backends participate in trade debates.

| Mode | Env Key | Description |
|------|---------|-------------|
| `LOCAL_ONLY` | `AI_PROVIDER_MODE=LOCAL_ONLY` | Ollama only. Fail-closed if Ollama is unavailable. |
| `LOCAL_PREFERRED` | `AI_PROVIDER_MODE=LOCAL_PREFERRED` (default) | Ollama preferred; falls back to OpenRouter if Ollama is unavailable. |
| `CLOUD_PREFERRED` | `AI_PROVIDER_MODE=CLOUD_PREFERRED` | OpenRouter preferred; falls back to Ollama if cloud is unavailable. |
| `CLOUD_ONLY` | `AI_PROVIDER_MODE=CLOUD_ONLY` | OpenRouter only. Fail-closed if cloud is unavailable. |
| `STRICT_DUAL_REQUIRED` | `AI_PROVIDER_MODE=STRICT_DUAL_REQUIRED` | Both backends must succeed. Fail-closed if either is unavailable. |

---

## 2. Default Mode

**`LOCAL_PREFERRED`** — The system defaults to local inference for cost control and latency, with automatic failover to cloud when the local backend is unhealthy.

---

## 3. Routing Ladder Policy

The `compute_routing()` function implements the following deterministic ladder:

### LOCAL_ONLY

```
IF Ollama is available → route to LOCAL_OLLAMA
ELSE → FAIL_CLOSED (no fallback)
```

### LOCAL_PREFERRED (default)

```
IF Ollama is available → route to LOCAL_OLLAMA
ELIF OpenRouter is available → route to OPENROUTER (fallback)
ELSE → FAIL_CLOSED
```

### CLOUD_PREFERRED

```
IF OpenRouter is available → route to OPENROUTER
ELIF Ollama is available → route to LOCAL_OLLAMA (fallback)
ELSE → FAIL_CLOSED
```

### CLOUD_ONLY

```
IF OpenRouter is available → route to OPENROUTER
ELSE → FAIL_CLOSED (no fallback)
```

### STRICT_DUAL_REQUIRED

```
IF both Ollama AND OpenRouter are available → route to BOTH
IF either is unavailable → FAIL_CLOSED (no partial execution)
IF both succeed but verdicts DISAGREE → REJECT with AI-016 PROVIDER_DISAGREEMENT
```

---

## 4. Provider Decision Consistency Guard

When multiple providers execute (fallback or STRICT_DUAL_REQUIRED), the system
detects and handles verdict disagreement.

### STRICT_DUAL_REQUIRED Mode

- Both providers must **succeed** AND **agree** on the final verdict
- If verdicts disagree → `AI-016 PROVIDER_DISAGREEMENT` → REJECT
- `provider_disagreement=True` flag set on result
- CONSISTENCY_GUARD audit entry added with both verdicts

### LOCAL_PREFERRED / CLOUD_PREFERRED (fallback scenario)

- When primary fails and fallback succeeds, result is marked `degraded_context=True`
- Trade is NOT rejected (fallback is permitted) but the flag signals reduced confidence
- Downstream consumers can optionally reduce position size or require additional confirmation

### Audit Fields

| Field | Type | Description |
|-------|------|-------------|
| `degraded_context` | bool | True when fallback provider was used instead of primary |
| `provider_disagreement` | bool | True when providers returned conflicting verdicts (AI-016) |

---

## 5. Fail-Closed Guarantee

**The system NEVER approves a trade when the AI debate cannot complete successfully.**

- If no backends are available → trade is REJECTED
- If the selected backend returns an error → trade is REJECTED
- If STRICT_DUAL_REQUIRED and either backend fails → trade is REJECTED
- If STRICT_DUAL_REQUIRED and providers disagree on verdict → trade is REJECTED (AI-016)
- If all backends enter cooldown → trade is REJECTED
- The `_fail_closed()` method is the only path for generating rejection results

Every rejection includes:

- `final_verdict = False`
- `reject_reason` with specific failure context
- Full `audit_trail` for observability
- `correlation_id` for tracing

---

## 5. Health Tracking

Each backend maintains independent health state:

| Field | Type | Description |
|-------|------|-------------|
| `status` | HealthStatus | HEALTHY, DEGRADED, UNAVAILABLE, COOLDOWN, UNKNOWN |
| `consecutive_failures` | int | Count of consecutive failures (resets on success) |
| `last_failure_class` | FailureClass? | Most recent failure classification |
| `cooldown_until` | datetime? | When cooldown expires |
| `last_success_at` | datetime? | Timestamp of last successful call |
| `last_failure_at` | datetime? | Timestamp of last failure |

### Availability Rules

- `is_available()` returns `True` only if status is HEALTHY or DEGRADED
- COOLDOWN and UNAVAILABLE statuses block routing to that backend
- Cooldown expiry automatically transitions back to DEGRADED (not HEALTHY)
- A subsequent success after DEGRADED transitions to HEALTHY

---

## 6. Cooldown Escalation

| Consecutive Failures | Cooldown Duration | Status Transition |
|---------------------|-------------------|-------------------|
| 1 | Base duration (per failure class) | COOLDOWN |
| 2 | Base duration | COOLDOWN |
| 3+ | Base × 5 (EXTENDED_COOLDOWN_MULTIPLIER) | UNAVAILABLE |

### Base Cooldown Durations by Failure Class

| Failure Class | Base Cooldown |
|--------------|--------------|
| LOCAL_UNREACHABLE | 60s |
| LOCAL_MODEL_MISSING | 300s (5min) |
| LOCAL_TIMEOUT | 30s |
| LOCAL_INVALID_OUTPUT | 10s |
| CLOUD_AUTH_FAILED | 3600s (1h) |
| CLOUD_CREDITS_EXHAUSTED | 3600s (1h) |
| CLOUD_RATE_LIMITED | 120s (2min) |
| CLOUD_SERVER_ERROR | 60s |
| CLOUD_TIMEOUT | 30s |
| CLOUD_INVALID_OUTPUT | 10s |

---

## 7. Audit Trail

Every routed debate produces a `RoutedDebateResult` containing:

```
RoutedDebateResult:
  debate_result: DebateResult | None
  provider_used: "LOCAL_OLLAMA" | "OPENROUTER" | "DUAL" | "NONE"
  routing_decision: RoutingDecision
  audit_trail: list[RoutingAuditEntry]
  final_verdict: bool
  reject_reason: str | None
  correlation_id: str (UUID)
```

Each `RoutingAuditEntry` records:

- Backend ID (which backend was called)
- Role (bull/bear/routing)
- Outcome (success/failure/skipped)
- Failure class (if failure)
- Error detail (sanitized message)
- Duration in milliseconds

---

## 8. Integration Point

The reliability manager is the **sole entry point** for AI debate execution in the hot path:

```
webhook.py → AIBackendReliabilityManager.route_debate()
                ├── compute_routing() → selects backend(s)
                ├── _execute_debate() → calls AICouncil or OllamaAICouncil
                └── _fail_closed() → if routing fails
```

The legacy `get_ai_council()` factory remains available for backward compatibility but is no longer called from the webhook hot path.

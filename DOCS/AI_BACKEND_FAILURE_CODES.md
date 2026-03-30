# AI Backend Failure Codes

## Project Autonomous Alpha — Phase 7

**Reliability Level:** SOVEREIGN TIER (Mission-Critical)
**Version:** 1.1.0
**Module:** `app/logic/ai_backend_reliability.py`

---

## Failure Classification System

Every AI backend failure is classified into exactly one `FailureClass`.
Classification drives cooldown duration, routing decisions, and audit trail content.

---

## Local Backend (Ollama) Failure Codes

| Code | FailureClass | Trigger Patterns | Cooldown (base) | Description |
|------|-------------|------------------|-----------------|-------------|
| L-01 | `LOCAL_UNREACHABLE` | Connection refused, connect error, unreachable | 60s | Ollama server is not running or not reachable on the network |
| L-02 | `LOCAL_MODEL_MISSING` | Model not found, model missing | 300s | Requested model is not pulled/available on the Ollama instance |
| L-03 | `LOCAL_TIMEOUT` | Timed out, timeout | 30s | Ollama request exceeded the configured timeout (default: 60s) |
| L-04 | `LOCAL_INVALID_OUTPUT` | ModelVerdict.ERROR with no pattern match | 10s | Ollama returned a response but it was malformed or unparseable |

## Cloud Backend (OpenRouter) Failure Codes

| Code | FailureClass | Trigger Patterns | Cooldown (base) | Description |
|------|-------------|------------------|-----------------|-------------|
| C-01 | `CLOUD_AUTH_FAILED` | API key, 401, unauthorized | 3600s (1h) | API key missing, invalid, or revoked |
| C-02 | `CLOUD_CREDITS_EXHAUSTED` | 402, credit, payment | 3600s (1h) | Account has no remaining credits or free tier exhausted |
| C-03 | `CLOUD_RATE_LIMITED` | 429, rate | 120s | Too many requests — rate limit exceeded |
| C-04 | `CLOUD_SERVER_ERROR` | 500, 502, 503, server | 60s | OpenRouter platform error |
| C-05 | `CLOUD_TIMEOUT` | Timed out, timeout | 30s | OpenRouter request exceeded timeout (default: 30s) |
| C-06 | `CLOUD_INVALID_OUTPUT` | ModelVerdict.ERROR with no pattern match | 10s | OpenRouter returned response but content was malformed |

## System-Level Failure Codes

| Code | FailureClass | Description |
|------|-------------|-------------|
| S-01 | `ALL_BACKENDS_UNAVAILABLE` | No backends are available (all in cooldown or unavailable) |
| S-02 | `PARTIAL_DEBATE_FAILURE` | One debate role (Bull or Bear) returned ERROR, the other succeeded |
| S-03 | `INVALID_ROUTING_CONFIG` | Unknown backend ID or invalid routing configuration |
| S-04 | `PROVIDER_DISAGREEMENT` | AI-016: Providers executed successfully but returned conflicting verdicts |

---

## Cooldown Escalation

| Condition | Cooldown Applied |
|-----------|-----------------|
| First failure | Base cooldown (see table above) |
| 2nd consecutive failure | Base cooldown (same) |
| 3rd+ consecutive failure | Base × 5 (extended cooldown), status → UNAVAILABLE |
| Any success | Cooldown cleared, consecutive count reset to 0 |

---

## Mapping to Legacy Error Codes

| Legacy Code | New FailureClass |
|-------------|-----------------|
| ERR-AI-003 | `CLOUD_AUTH_FAILED` |
| ERR-AI-004 (4xx) | `CLOUD_AUTH_FAILED` or `CLOUD_CREDITS_EXHAUSTED` or `CLOUD_RATE_LIMITED` |
| ERR-AI-004 (5xx) | `CLOUD_SERVER_ERROR` |
| ERR-AI-005 | `CLOUD_INVALID_OUTPUT` |
| ERR-AI-006 | `CLOUD_INVALID_OUTPUT` |
| ERR-AI-007 | `CLOUD_TIMEOUT` |
| ERR-AI-008 | `CLOUD_SERVER_ERROR` |
| ERR-AI-009 | `CLOUD_INVALID_OUTPUT` |
| ERR-OLLAMA-001 | `LOCAL_UNREACHABLE` or `LOCAL_INVALID_OUTPUT` |
| ERR-OLLAMA-002 | `LOCAL_INVALID_OUTPUT` |
| ERR-OLLAMA-003 | `LOCAL_TIMEOUT` |
| ERR-OLLAMA-004 | `LOCAL_UNREACHABLE` |
| ERR-OLLAMA-005 | `LOCAL_INVALID_OUTPUT` |

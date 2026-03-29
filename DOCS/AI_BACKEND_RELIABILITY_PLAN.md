# AI Backend Reliability Plan

## Project Autonomous Alpha — Phase 7

**Reliability Level:** SOVEREIGN TIER (Mission-Critical)
**Version:** 1.1.0
**Status:** IMPLEMENTED AND TESTED

---

## 1. Problem Statement

The previous AI debate architecture used a single factory (`get_ai_council()`) that selected between local Ollama and cloud OpenRouter based on a static environment variable with no fallback, no health tracking, and no structured failure handling. A single provider outage caused total AI debate collapse, blocking all trade execution.

---

## 2. Design Objectives

| Priority | Objective |
|----------|-----------|
| P0 | **Fail-closed guarantee** — Never approve a trade when AI debate fails |
| P1 | **Provider resilience** — Survive single-provider failures via fallback routing |
| P2 | **Structured failure classification** — Every failure maps to a canonical FailureClass |
| P3 | **Cooldown-based recovery** — Prevent hammering failed backends |
| P4 | **Full audit trail** — Every routing decision and debate outcome is recorded |
| P5 | **Zero business logic change** — Existing debate protocol (Bull/Bear consensus) preserved |

---

## 3. Architecture

### Module: `app/logic/ai_backend_reliability.py`

```
┌──────────────────────────────────────────────────┐
│              Webhook Hot Path                     │
│   webhook.py Step 10: AI Debate                  │
│                                                   │
│   AIBackendReliabilityManager.route_debate()      │
│        │                                          │
│        ▼                                          │
│   compute_routing(mode, registry)                 │
│        │                                          │
│   ┌────┴────────────────────────┐                 │
│   │   RoutingDecision           │                 │
│   │   primary: BackendId        │                 │
│   │   fallback: BackendId?      │                 │
│   │   reason: str               │                 │
│   └────┬────────────────────────┘                 │
│        │                                          │
│   ┌────▼────────────────────────┐                 │
│   │  _execute_debate()          │                 │
│   │  or _execute_strict_dual()  │                 │
│   │  or _fail_closed()          │                 │
│   └────┬────────────────────────┘                 │
│        │                                          │
│   ┌────▼────────────────────────┐                 │
│   │  RoutedDebateResult         │                 │
│   │  - debate_result            │                 │
│   │  - provider_used            │                 │
│   │  - routing_decision         │                 │
│   │  - audit_trail              │                 │
│   │  - final_verdict            │                 │
│   │  - reject_reason            │                 │
│   │  - correlation_id           │                 │
│   └─────────────────────────────┘                 │
└──────────────────────────────────────────────────┘
```

### Key Classes

| Class | Responsibility |
|-------|---------------|
| `ProviderMode` | Enum: 5 routing modes |
| `BackendId` | Enum: LOCAL_OLLAMA, OPENROUTER |
| `FailureClass` | Enum: 14 canonical failure types (incl. AI-016 PROVIDER_DISAGREEMENT) |
| `HealthStatus` | Enum: HEALTHY, DEGRADED, UNAVAILABLE, COOLDOWN, UNKNOWN |
| `BackendHealth` | Mutable health state per backend |
| `ProviderHealthRegistry` | Tracks health for all backends |
| `RoutingDecision` | Named tuple: primary, fallback, reason |
| `RoutingAuditEntry` | Per-call audit record |
| `RoutedDebateResult` | Final output with debate result + routing metadata |
| `AIBackendReliabilityManager` | Orchestrator: routing, execution, health updates |

---

## 4. Integration Points

### Webhook (app/api/webhook.py)

**Before (Phase 6):**

```python
CouncilClass = get_ai_council()
council = CouncilClass()
debate_result = await council.conduct_debate(symbol, side, ...)
```

**After (Phase 7):**

```python
reliability_mgr = AIBackendReliabilityManager()
routed_result = await reliability_mgr.route_debate(
    correlation_id=correlation_id,
    symbol=symbol, side=side,
    price=current_price, quantity=quantity
)
debate_result = routed_result.debate_result
```

### AI Council (app/logic/ai_council.py)

The existing `AICouncil` and `OllamaAICouncil` classes are used as-is by the reliability manager. No changes to the debate protocol. The `get_ai_council()` factory is preserved for backward compatibility.

---

## 5. Test Coverage

**63 tests across 15 test classes, all passing.**

| Test Category | Test Class | Count |
|--------------|-----------|-------|
| Provider health registry | TestProviderHealthRegistry | 8 |
| Failure classification | TestFailureClassifier | 12 |
| Routing logic | TestRoutingLogic | 11 |
| Cooldown behavior | TestCooldownBehavior | 4 |
| Ollama healthy → success | TestOllamaHealthySuccess | 1 |
| Ollama down → cloud fallback | TestOllamaDownCloudFallback | 1 |
| All backends fail | TestAllBackendsFail | 2 |
| Cloud failure classification | TestCloudFailureClassification | 1 |
| Malformed output handling | TestMalformedOutput | 2 |
| Strict dual required | TestStrictDualRequired | 4 |
| Mode correctness | TestModeCorrectness | 3 |
| Routing audit visibility | TestRoutingAuditVisibility | 3 |
| Fail-closed behavior | TestFailClosedBehavior | 3 |
| Default mode | TestDefaultMode | 1 |
| **Provider consistency guard** | **TestProviderConsistencyGuard** | **7** |

---

## 6. Design Decisions

| Decision | Rationale |
|----------|-----------|
| In-memory health registry (not DB) | Sub-millisecond routing; health is ephemeral and transient |
| Cooldown-based recovery (not circuit-breaker) | Simpler model; deterministic timing; matches financial ops cadence |
| 14 discrete failure classes (not generic) | Each class has specific cooldown and recovery semantics |
| Fail-closed as default | **Survival > Alpha** — no trade without AI validation |
| Provider consistency guard (AI-016) | Multi-provider disagreement detected and rejected in STRICT mode |
| Degraded context flag on fallback | Downstream consumers aware when non-preferred provider was used |
| LOCAL_PREFERRED as default mode | Cost control (free local inference first), automatic cloud failover |
| STRICT_DUAL_REQUIRED for high-risk | Both backends must agree — defense in depth for large positions |
| Audit trail per call | Full traceability for post-incident review |
| No floating-point in routing | All cooldown durations are integer seconds (Rule 2 compliance) |

---

## 7. Files

| File | Type | Lines |
|------|------|-------|
| `app/logic/ai_backend_reliability.py` | Module | ~600 |
| `tests/unit/test_ai_backend_reliability.py` | Tests | ~530 |
| `app/api/webhook.py` | Modified | Integration |
| `DOCS/AI_BACKEND_RELIABILITY_PLAN.md` | Doc | This file |
| `DOCS/AI_PROVIDER_POLICY.md` | Doc | Provider mode reference |
| `DOCS/AI_BACKEND_FAILURE_CODES.md` | Doc | Failure code catalog |
| `DOCS/AI_BACKEND_RUNBOOK.md` | Doc | Operational runbook |

---

## 8. Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Both backends down simultaneously | HIGH | Fail-closed; trade rejected with audit trail |
| Cooldown too aggressive → missed trades | MEDIUM | Conservative base durations; success resets immediately |
| Cooldown too lenient → hammering failed backend | MEDIUM | Extended cooldown (5×) after 3 consecutive failures |
| Health registry lost on restart | LOW | Ephemeral by design; backends probed on first call |
| Stale health after long idle period | LOW | UNKNOWN status triggers fresh probe |
| Provider disagreement in STRICT mode | MEDIUM | AI-016 rejects the trade; audit trail records both verdicts |

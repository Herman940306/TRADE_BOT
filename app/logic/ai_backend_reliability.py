"""
Project Autonomous Alpha — Phase 7
AI Backend Reliability Manager

Reliability Level: SOVEREIGN TIER (Mission-Critical)
Input Constraints: Validated DebateRequest with correlation_id
Side Effects: HTTP calls to Ollama/OpenRouter, writes structured audit events

PURPOSE
-------
The AI Backend Reliability Manager prevents total AI debate collapse when
one provider fails, while preserving strict fail-closed behavior. It
governs ALL provider selection, health tracking, failure classification,
cooldown management, and routing decisions for the AI Council debate path.

NON-NEGOTIABLE RULES
--------------------
1. No silent provider switching — all routing logged with reason codes
2. No hidden fallback — ladder policy is explicit and auditable
3. No partial debate acceptance unless policy allows (STRICT_DUAL mode)
4. No approval if all providers fail — fail-closed to REJECTED
5. No bypass of DecisionPacketBuilder or TokenBudgetGuard
6. No GitHub Copilot runtime dependency
7. All outcomes must be auditable via structured events

DESIGN
------
The manager is orthogonal to the AI Council classes. It does not replace
AICouncil or OllamaAICouncil — it wraps them with reliability:

    Signal → ReliabilityManager.route_debate()
         → selects provider(s) per ladder policy
         → executes via existing council classes
         → classifies any failures
         → applies cooldown if needed
         → returns RoutedDebateResult with full audit trail

FAIL-CLOSED MANDATE
-------------------
If all eligible providers are unavailable, exhausted, or return errors,
the final verdict is ALWAYS False (REJECTED). There is no "best effort"
mode. Survival > Capital Preservation > Alpha.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional
from uuid import UUID

from app.logic.ai_council import DebateResult, ModelVerdict

logger = logging.getLogger(__name__)


# =============================================================================
# PROVIDER MODE POLICY
# =============================================================================


class ProviderMode(str, Enum):
    """
    Provider routing policy.

    Determines which backends are eligible and in what order.
    """

    LOCAL_ONLY = "LOCAL_ONLY"
    LOCAL_PREFERRED = "LOCAL_PREFERRED"
    CLOUD_PREFERRED = "CLOUD_PREFERRED"
    CLOUD_ONLY = "CLOUD_ONLY"
    STRICT_DUAL_REQUIRED = "STRICT_DUAL_REQUIRED"


DEFAULT_PROVIDER_MODE = ProviderMode.LOCAL_PREFERRED


class BackendId(str, Enum):
    """Canonical backend identifiers."""

    LOCAL_OLLAMA = "LOCAL_OLLAMA"
    OPENROUTER = "OPENROUTER"


# =============================================================================
# FAILURE CLASSIFICATION
# =============================================================================


class FailureClass(str, Enum):
    """
    Canonical failure classification codes.

    Each failure maps to exactly one class for routing decisions.
    """

    # Local (Ollama) failures
    LOCAL_UNREACHABLE = "LOCAL_UNREACHABLE"
    LOCAL_MODEL_MISSING = "LOCAL_MODEL_MISSING"
    LOCAL_TIMEOUT = "LOCAL_TIMEOUT"
    LOCAL_INVALID_OUTPUT = "LOCAL_INVALID_OUTPUT"

    # Cloud (OpenRouter) failures
    CLOUD_AUTH_FAILED = "CLOUD_AUTH_FAILED"
    CLOUD_CREDITS_EXHAUSTED = "CLOUD_CREDITS_EXHAUSTED"
    CLOUD_RATE_LIMITED = "CLOUD_RATE_LIMITED"
    CLOUD_SERVER_ERROR = "CLOUD_SERVER_ERROR"
    CLOUD_TIMEOUT = "CLOUD_TIMEOUT"
    CLOUD_INVALID_OUTPUT = "CLOUD_INVALID_OUTPUT"

    # System-level failures
    ALL_BACKENDS_UNAVAILABLE = "ALL_BACKENDS_UNAVAILABLE"
    PARTIAL_DEBATE_FAILURE = "PARTIAL_DEBATE_FAILURE"
    INVALID_ROUTING_CONFIG = "INVALID_ROUTING_CONFIG"
    PROVIDER_DISAGREEMENT = "PROVIDER_DISAGREEMENT"  # AI-016


# Failure → suggested cooldown duration (seconds)
DEFAULT_COOLDOWN_DURATIONS: Dict[FailureClass, int] = {
    FailureClass.LOCAL_UNREACHABLE: 60,
    FailureClass.LOCAL_MODEL_MISSING: 300,
    FailureClass.LOCAL_TIMEOUT: 30,
    FailureClass.LOCAL_INVALID_OUTPUT: 10,
    FailureClass.CLOUD_AUTH_FAILED: 3600,
    FailureClass.CLOUD_CREDITS_EXHAUSTED: 3600,
    FailureClass.CLOUD_RATE_LIMITED: 120,
    FailureClass.CLOUD_SERVER_ERROR: 60,
    FailureClass.CLOUD_TIMEOUT: 30,
    FailureClass.CLOUD_INVALID_OUTPUT: 10,
}

# Maximum consecutive failures before extended cooldown
MAX_CONSECUTIVE_FAILURES = 3
EXTENDED_COOLDOWN_MULTIPLIER = 5


# =============================================================================
# HEALTH REGISTRY
# =============================================================================


class HealthStatus(str, Enum):
    """Backend health status."""

    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"
    COOLDOWN = "COOLDOWN"
    UNKNOWN = "UNKNOWN"


@dataclass
class BackendHealth:
    """
    Mutable health state for a single backend.

    Tracks consecutive failures, last failure class, cooldown expiry,
    and overall status.
    """

    backend_id: BackendId
    status: HealthStatus = HealthStatus.UNKNOWN
    consecutive_failures: int = 0
    last_failure_class: Optional[FailureClass] = None
    last_failure_time: Optional[float] = None
    cooldown_until: Optional[float] = None
    last_success_time: Optional[float] = None
    total_successes: int = 0
    total_failures: int = 0

    def is_available(self) -> bool:
        """Check if backend is available for routing."""
        if self.status == HealthStatus.UNAVAILABLE:
            return False
        if self.cooldown_until is not None and time.monotonic() < self.cooldown_until:
            return False
        # If cooldown has expired, clear it
        if self.cooldown_until is not None and time.monotonic() >= self.cooldown_until:
            self.cooldown_until = None
            if self.status == HealthStatus.COOLDOWN:
                self.status = HealthStatus.DEGRADED
        return True

    def record_success(self) -> None:
        """Record a successful call."""
        self.consecutive_failures = 0
        self.last_failure_class = None
        self.cooldown_until = None
        self.last_success_time = time.monotonic()
        self.total_successes += 1
        self.status = HealthStatus.HEALTHY

    def record_failure(self, failure_class: FailureClass) -> None:
        """Record a failed call and apply cooldown if needed."""
        self.consecutive_failures += 1
        self.last_failure_class = failure_class
        self.last_failure_time = time.monotonic()
        self.total_failures += 1

        # Determine cooldown duration
        base_cooldown = DEFAULT_COOLDOWN_DURATIONS.get(failure_class, 30)
        if self.consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
            cooldown = base_cooldown * EXTENDED_COOLDOWN_MULTIPLIER
            self.status = HealthStatus.UNAVAILABLE
        else:
            cooldown = base_cooldown
            self.status = HealthStatus.COOLDOWN

        self.cooldown_until = time.monotonic() + cooldown
        logger.warning(
            "Backend %s failure recorded | class=%s | consecutive=%d | "
            "cooldown=%ds | status=%s",
            self.backend_id.value,
            failure_class.value,
            self.consecutive_failures,
            cooldown,
            self.status.value,
        )


class ProviderHealthRegistry:
    """
    Registry tracking health state of all backends.

    Thread-safe for single-threaded async (no locks needed in asyncio).
    """

    def __init__(self) -> None:
        self._backends: Dict[BackendId, BackendHealth] = {
            BackendId.LOCAL_OLLAMA: BackendHealth(backend_id=BackendId.LOCAL_OLLAMA),
            BackendId.OPENROUTER: BackendHealth(backend_id=BackendId.OPENROUTER),
        }

    def get_health(self, backend_id: BackendId) -> BackendHealth:
        return self._backends[backend_id]

    def is_available(self, backend_id: BackendId) -> bool:
        return self._backends[backend_id].is_available()

    def record_success(self, backend_id: BackendId) -> None:
        self._backends[backend_id].record_success()

    def record_failure(
        self, backend_id: BackendId, failure_class: FailureClass
    ) -> None:
        self._backends[backend_id].record_failure(failure_class)

    def get_all_health(self) -> Dict[BackendId, BackendHealth]:
        return dict(self._backends)

    def reset(self, backend_id: BackendId) -> None:
        """Manual reset — for operational recovery."""
        self._backends[backend_id] = BackendHealth(backend_id=backend_id)


# =============================================================================
# FAILURE CLASSIFIER
# =============================================================================


def classify_failure(
    backend_id: BackendId,
    error_msg: str,
    verdict: Optional[ModelVerdict] = None,
) -> FailureClass:
    """
    Classify an AI backend failure into a canonical failure class.

    Uses error message patterns from existing ERR-AI-xxx and ERR-OLLAMA-xxx
    codes to determine the failure type.
    """
    msg = error_msg.upper()

    if backend_id == BackendId.LOCAL_OLLAMA:
        if "TIMED OUT" in msg or "TIMEOUT" in msg:
            return FailureClass.LOCAL_TIMEOUT
        if "REQUEST FAILED" in msg or "CONNECT" in msg or "UNREACHABLE" in msg:
            return FailureClass.LOCAL_UNREACHABLE
        if "MODEL" in msg and ("NOT FOUND" in msg or "MISSING" in msg):
            return FailureClass.LOCAL_MODEL_MISSING
        if verdict == ModelVerdict.ERROR:
            return FailureClass.LOCAL_INVALID_OUTPUT
        return FailureClass.LOCAL_UNREACHABLE

    if backend_id == BackendId.OPENROUTER:
        if "API KEY" in msg or "401" in msg or "UNAUTHORIZED" in msg:
            return FailureClass.CLOUD_AUTH_FAILED
        if "402" in msg or "CREDIT" in msg or "PAYMENT" in msg:
            return FailureClass.CLOUD_CREDITS_EXHAUSTED
        if "429" in msg or "RATE" in msg:
            return FailureClass.CLOUD_RATE_LIMITED
        if "TIMED OUT" in msg or "TIMEOUT" in msg:
            return FailureClass.CLOUD_TIMEOUT
        if "500" in msg or "502" in msg or "503" in msg or "SERVER" in msg:
            return FailureClass.CLOUD_SERVER_ERROR
        if verdict == ModelVerdict.ERROR:
            return FailureClass.CLOUD_INVALID_OUTPUT
        return FailureClass.CLOUD_SERVER_ERROR

    return FailureClass.INVALID_ROUTING_CONFIG


# =============================================================================
# ROUTING DECISIONS
# =============================================================================


@dataclass
class RoutingDecision:
    """What the ladder policy decided."""

    primary: Optional[BackendId]
    fallback: Optional[BackendId]
    mode: ProviderMode
    reason: str


def compute_routing(
    mode: ProviderMode,
    registry: ProviderHealthRegistry,
) -> RoutingDecision:
    """
    Compute provider routing based on mode and health.

    Returns which backend(s) to use, or None if none available.
    """
    local_ok = registry.is_available(BackendId.LOCAL_OLLAMA)
    cloud_ok = registry.is_available(BackendId.OPENROUTER)

    if mode == ProviderMode.LOCAL_ONLY:
        if local_ok:
            return RoutingDecision(
                primary=BackendId.LOCAL_OLLAMA,
                fallback=None,
                mode=mode,
                reason="LOCAL_ONLY: local available",
            )
        return RoutingDecision(
            primary=None,
            fallback=None,
            mode=mode,
            reason="LOCAL_ONLY: local unavailable — no fallback permitted",
        )

    if mode == ProviderMode.CLOUD_ONLY:
        if cloud_ok:
            return RoutingDecision(
                primary=BackendId.OPENROUTER,
                fallback=None,
                mode=mode,
                reason="CLOUD_ONLY: cloud available",
            )
        return RoutingDecision(
            primary=None,
            fallback=None,
            mode=mode,
            reason="CLOUD_ONLY: cloud unavailable — no fallback permitted",
        )

    if mode == ProviderMode.LOCAL_PREFERRED:
        if local_ok:
            return RoutingDecision(
                primary=BackendId.LOCAL_OLLAMA,
                fallback=BackendId.OPENROUTER if cloud_ok else None,
                mode=mode,
                reason="LOCAL_PREFERRED: local available"
                + (", cloud fallback ready" if cloud_ok else ", no fallback"),
            )
        if cloud_ok:
            return RoutingDecision(
                primary=BackendId.OPENROUTER,
                fallback=None,
                mode=mode,
                reason="LOCAL_PREFERRED: local unavailable, falling back to cloud",
            )
        return RoutingDecision(
            primary=None,
            fallback=None,
            mode=mode,
            reason="LOCAL_PREFERRED: all backends unavailable",
        )

    if mode == ProviderMode.CLOUD_PREFERRED:
        if cloud_ok:
            return RoutingDecision(
                primary=BackendId.OPENROUTER,
                fallback=BackendId.LOCAL_OLLAMA if local_ok else None,
                mode=mode,
                reason="CLOUD_PREFERRED: cloud available"
                + (", local fallback ready" if local_ok else ", no fallback"),
            )
        if local_ok:
            return RoutingDecision(
                primary=BackendId.LOCAL_OLLAMA,
                fallback=None,
                mode=mode,
                reason="CLOUD_PREFERRED: cloud unavailable, falling back to local",
            )
        return RoutingDecision(
            primary=None,
            fallback=None,
            mode=mode,
            reason="CLOUD_PREFERRED: all backends unavailable",
        )

    if mode == ProviderMode.STRICT_DUAL_REQUIRED:
        if local_ok and cloud_ok:
            return RoutingDecision(
                primary=BackendId.LOCAL_OLLAMA,
                fallback=BackendId.OPENROUTER,
                mode=mode,
                reason="STRICT_DUAL_REQUIRED: both backends available",
            )
        missing = []
        if not local_ok:
            missing.append("local")
        if not cloud_ok:
            missing.append("cloud")
        return RoutingDecision(
            primary=None,
            fallback=None,
            mode=mode,
            reason=f"STRICT_DUAL_REQUIRED: {', '.join(missing)} unavailable — "
            "dual requirement not met",
        )

    return RoutingDecision(
        primary=None,
        fallback=None,
        mode=mode,
        reason=f"Unknown mode: {mode}",
    )


# =============================================================================
# ROUTED DEBATE RESULT
# =============================================================================


@dataclass
class RoutingAuditEntry:
    """Single entry in the routing audit trail."""

    backend_id: BackendId
    role: str  # "PRIMARY" or "FALLBACK"
    outcome: str  # "SUCCESS", "FAILED", "SKIPPED"
    failure_class: Optional[FailureClass] = None
    error_detail: Optional[str] = None
    duration_ms: Optional[int] = None


@dataclass
class RoutedDebateResult:
    """
    Debate result with full routing audit trail.

    Extends the base DebateResult with reliability metadata.
    """

    debate_result: Optional[DebateResult]
    provider_used: Optional[BackendId]
    routing_decision: RoutingDecision
    audit_trail: List[RoutingAuditEntry] = field(default_factory=list)
    final_verdict: bool = False
    reject_reason: str = ""
    degraded_context: bool = False
    provider_disagreement: bool = False

    @property
    def is_rejected(self) -> bool:
        return not self.final_verdict

    @property
    def correlation_id(self) -> Optional[UUID]:
        if self.debate_result:
            return self.debate_result.correlation_id
        return None


# =============================================================================
# READINESS CHECKS
# =============================================================================


async def check_ollama_ready(
    base_url: str = "http://ollama:11434",
    model: Optional[str] = None,
    timeout: float = 5.0,
) -> tuple[bool, Optional[FailureClass], str]:
    """
    Pre-flight check: Is the Ollama server reachable and model loaded?

    Returns (is_ready, failure_class_if_not, detail_message).
    """
    import httpx

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            # Check server is alive
            resp = await client.get(f"{base_url}/api/tags")
            if resp.status_code != 200:
                return (
                    False,
                    FailureClass.LOCAL_UNREACHABLE,
                    f"Ollama returned {resp.status_code}",
                )

            # If model specified, verify it's loaded
            if model:
                data = resp.json()
                models = [m.get("name", "") for m in data.get("models", [])]
                # Check for exact match or prefix match (e.g. "qwen3:8b" matches "qwen3:8b")
                found = any(model in m or m.startswith(model) for m in models)
                if not found:
                    return (
                        False,
                        FailureClass.LOCAL_MODEL_MISSING,
                        f"Model '{model}' not found in {models}",
                    )

            return (True, None, "Ollama ready")

    except httpx.TimeoutException:
        return (
            False,
            FailureClass.LOCAL_TIMEOUT,
            f"Ollama health check timed out after {timeout}s",
        )
    except httpx.RequestError as e:
        return (
            False,
            FailureClass.LOCAL_UNREACHABLE,
            f"Ollama unreachable: {str(e)[:200]}",
        )


async def check_openrouter_ready(
    api_key: Optional[str] = None,
    timeout: float = 5.0,
) -> tuple[bool, Optional[FailureClass], str]:
    """
    Pre-flight check: Is OpenRouter accessible with valid credentials?

    Checks the /api/v1/models endpoint (lightweight, no inference cost).
    """
    import os

    import httpx

    key = api_key or os.getenv("OPENROUTER_API_KEY")
    if not key:
        return (
            False,
            FailureClass.CLOUD_AUTH_FAILED,
            "OPENROUTER_API_KEY not configured",
        )

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(
                "https://openrouter.ai/api/v1/models",
                headers={"Authorization": f"Bearer {key}"},
            )
            if resp.status_code == 401:
                return (
                    False,
                    FailureClass.CLOUD_AUTH_FAILED,
                    "OpenRouter API key invalid (401)",
                )
            if resp.status_code == 402:
                return (
                    False,
                    FailureClass.CLOUD_CREDITS_EXHAUSTED,
                    "OpenRouter credits exhausted (402)",
                )
            if resp.status_code == 429:
                return (
                    False,
                    FailureClass.CLOUD_RATE_LIMITED,
                    "OpenRouter rate limited (429)",
                )
            if resp.status_code >= 500:
                return (
                    False,
                    FailureClass.CLOUD_SERVER_ERROR,
                    f"OpenRouter server error ({resp.status_code})",
                )
            if resp.status_code == 200:
                return (True, None, "OpenRouter ready")
            return (
                False,
                FailureClass.CLOUD_SERVER_ERROR,
                f"OpenRouter unexpected status {resp.status_code}",
            )

    except httpx.TimeoutException:
        return (
            False,
            FailureClass.CLOUD_TIMEOUT,
            f"OpenRouter health check timed out after {timeout}s",
        )
    except httpx.RequestError as e:
        return (
            False,
            FailureClass.CLOUD_SERVER_ERROR,
            f"OpenRouter unreachable: {str(e)[:200]}",
        )


# =============================================================================
# AI BACKEND RELIABILITY MANAGER
# =============================================================================


class AIBackendReliabilityManager:
    """
    Central reliability manager for AI backend routing.

    Manages provider health, routing decisions, failure classification,
    cooldown logic, and debate execution with full audit trail.

    Usage:
        manager = AIBackendReliabilityManager()
        result = await manager.route_debate(
            correlation_id=uuid,
            symbol="BTCZAR",
            side="BUY",
            price=Decimal("1500000"),
            quantity=Decimal("0.001"),
        )
        # result.final_verdict → True/False
        # result.audit_trail → full routing history
    """

    def __init__(
        self,
        mode: ProviderMode = DEFAULT_PROVIDER_MODE,
        registry: Optional[ProviderHealthRegistry] = None,
    ) -> None:
        self.mode = mode
        self.registry = registry or ProviderHealthRegistry()

    async def route_debate(
        self,
        correlation_id: UUID,
        symbol: str,
        side: str,
        price: "Decimal",  # type: ignore[name-defined]  # noqa: F821
        quantity: "Decimal",  # type: ignore[name-defined]  # noqa: F821
    ) -> RoutedDebateResult:
        """
        Route a debate through the reliability layer.

        1. Compute routing decision based on mode + health
        2. Execute debate on primary backend
        3. On failure, classify and try fallback if available
        4. On total failure, return fail-closed REJECTED
        5. Log full audit trail
        """

        routing = compute_routing(self.mode, self.registry)
        audit_trail: List[RoutingAuditEntry] = []

        logger.info(
            "route_debate START | correlation_id=%s | mode=%s | "
            "primary=%s | fallback=%s | reason=%s",
            correlation_id,
            self.mode.value,
            routing.primary.value if routing.primary else "NONE",
            routing.fallback.value if routing.fallback else "NONE",
            routing.reason,
        )

        # --- No backends available ---
        if routing.primary is None:
            audit_trail.append(
                RoutingAuditEntry(
                    backend_id=BackendId.LOCAL_OLLAMA,
                    role="PRIMARY",
                    outcome="SKIPPED",
                    failure_class=FailureClass.ALL_BACKENDS_UNAVAILABLE,
                    error_detail=routing.reason,
                )
            )
            return self._fail_closed(
                correlation_id,
                routing,
                audit_trail,
                f"No backends available: {routing.reason}",
            )

        # --- STRICT_DUAL_REQUIRED: both must succeed ---
        if self.mode == ProviderMode.STRICT_DUAL_REQUIRED:
            return await self._execute_strict_dual(
                correlation_id, symbol, side, price, quantity, routing, audit_trail
            )

        # --- Try primary backend ---
        result, entry = await self._execute_debate(
            routing.primary,
            "PRIMARY",
            correlation_id,
            symbol,
            side,
            price,
            quantity,
        )
        audit_trail.append(entry)

        if result is not None:
            # Primary succeeded
            self.registry.record_success(routing.primary)
            return RoutedDebateResult(
                debate_result=result,
                provider_used=routing.primary,
                routing_decision=routing,
                audit_trail=audit_trail,
                final_verdict=result.final_verdict,
                reject_reason=""
                if result.final_verdict
                else f"Debate rejected (consensus={result.consensus_score})",
            )

        # Primary failed — classify and record
        failure_class = classify_failure(
            routing.primary,
            entry.error_detail or "",
        )
        entry.failure_class = failure_class
        self.registry.record_failure(routing.primary, failure_class)

        # --- Try fallback if available ---
        if routing.fallback is not None and self.registry.is_available(
            routing.fallback
        ):
            logger.warning(
                "Primary %s failed (%s), attempting fallback %s | correlation_id=%s",
                routing.primary.value,
                failure_class.value,
                routing.fallback.value,
                correlation_id,
            )

            fb_result, fb_entry = await self._execute_debate(
                routing.fallback,
                "FALLBACK",
                correlation_id,
                symbol,
                side,
                price,
                quantity,
            )
            audit_trail.append(fb_entry)

            if fb_result is not None:
                self.registry.record_success(routing.fallback)
                return RoutedDebateResult(
                    debate_result=fb_result,
                    provider_used=routing.fallback,
                    routing_decision=routing,
                    audit_trail=audit_trail,
                    final_verdict=fb_result.final_verdict,
                    reject_reason=""
                    if fb_result.final_verdict
                    else f"Debate rejected via fallback (consensus={fb_result.consensus_score})",
                    degraded_context=True,
                )

            # Fallback also failed
            fb_failure = classify_failure(
                routing.fallback,
                fb_entry.error_detail or "",
            )
            fb_entry.failure_class = fb_failure
            self.registry.record_failure(routing.fallback, fb_failure)

        # --- All attempts exhausted → fail-closed ---
        return self._fail_closed(
            correlation_id,
            routing,
            audit_trail,
            "All eligible backends failed",
        )

    async def _execute_strict_dual(
        self,
        correlation_id: UUID,
        symbol: str,
        side: str,
        price: "Decimal",  # type: ignore[name-defined]  # noqa: F821
        quantity: "Decimal",  # type: ignore[name-defined]  # noqa: F821
        routing: RoutingDecision,
        audit_trail: List[RoutingAuditEntry],
    ) -> RoutedDebateResult:
        """
        STRICT_DUAL_REQUIRED: both local and cloud must succeed.

        If either fails, the entire debate is rejected.
        """
        if routing.primary is None or routing.fallback is None:
            return self._fail_closed(
                correlation_id,
                routing,
                audit_trail,
                "STRICT_DUAL_REQUIRED: not all backends available",
            )

        # Execute on both backends
        local_result, local_entry = await self._execute_debate(
            BackendId.LOCAL_OLLAMA,
            "DUAL_LOCAL",
            correlation_id,
            symbol,
            side,
            price,
            quantity,
        )
        audit_trail.append(local_entry)

        cloud_result, cloud_entry = await self._execute_debate(
            BackendId.OPENROUTER,
            "DUAL_CLOUD",
            correlation_id,
            symbol,
            side,
            price,
            quantity,
        )
        audit_trail.append(cloud_entry)

        # Both must succeed
        if local_result is None or cloud_result is None:
            # Record failures
            if local_result is None:
                fc = classify_failure(
                    BackendId.LOCAL_OLLAMA, local_entry.error_detail or ""
                )
                local_entry.failure_class = fc
                self.registry.record_failure(BackendId.LOCAL_OLLAMA, fc)
            else:
                self.registry.record_success(BackendId.LOCAL_OLLAMA)

            if cloud_result is None:
                fc = classify_failure(
                    BackendId.OPENROUTER, cloud_entry.error_detail or ""
                )
                cloud_entry.failure_class = fc
                self.registry.record_failure(BackendId.OPENROUTER, fc)
            else:
                self.registry.record_success(BackendId.OPENROUTER)

            return self._fail_closed(
                correlation_id,
                routing,
                audit_trail,
                "STRICT_DUAL_REQUIRED: one or both backends failed",
            )

        # Both succeeded — use the more conservative result
        self.registry.record_success(BackendId.LOCAL_OLLAMA)
        self.registry.record_success(BackendId.OPENROUTER)

        # In strict dual, BOTH must approve for the verdict to be True
        combined_verdict = local_result.final_verdict and cloud_result.final_verdict

        # --- PROVIDER DISAGREEMENT DETECTION (AI-016) ---
        verdicts_disagree = local_result.final_verdict != cloud_result.final_verdict
        if verdicts_disagree:
            logger.warning(
                "PROVIDER_DISAGREEMENT (AI-016) | correlation_id=%s | "
                "local_verdict=%s | cloud_verdict=%s",
                correlation_id,
                local_result.final_verdict,
                cloud_result.final_verdict,
            )
            audit_trail.append(
                RoutingAuditEntry(
                    backend_id=BackendId.LOCAL_OLLAMA,
                    role="CONSISTENCY_GUARD",
                    outcome="DISAGREEMENT",
                    failure_class=FailureClass.PROVIDER_DISAGREEMENT,
                    error_detail=(
                        f"AI-016: local_verdict={local_result.final_verdict}, "
                        f"cloud_verdict={cloud_result.final_verdict}"
                    ),
                )
            )
            # STRICT_DUAL: disagreement = REJECT
            return RoutedDebateResult(
                debate_result=None,
                provider_used=None,
                routing_decision=routing,
                audit_trail=audit_trail,
                final_verdict=False,
                reject_reason=(
                    "AI-016 PROVIDER_DISAGREEMENT: providers disagree on verdict "
                    f"(local={local_result.final_verdict}, "
                    f"cloud={cloud_result.final_verdict})"
                ),
                provider_disagreement=True,
            )

        # Use the local result as the primary, but override verdict
        merged = DebateResult(
            correlation_id=correlation_id,
            bull_reasoning=(
                f"[LOCAL] {local_result.bull_reasoning}\n"
                f"[CLOUD] {cloud_result.bull_reasoning}"
            ),
            bear_reasoning=(
                f"[LOCAL] {local_result.bear_reasoning}\n"
                f"[CLOUD] {cloud_result.bear_reasoning}"
            ),
            bull_verdict=(
                ModelVerdict.APPROVED
                if local_result.bull_verdict == ModelVerdict.APPROVED
                and cloud_result.bull_verdict == ModelVerdict.APPROVED
                else ModelVerdict.REJECTED
            ),
            bear_verdict=(
                ModelVerdict.APPROVED
                if local_result.bear_verdict == ModelVerdict.APPROVED
                and cloud_result.bear_verdict == ModelVerdict.APPROVED
                else ModelVerdict.REJECTED
            ),
            consensus_score=min(
                local_result.consensus_score, cloud_result.consensus_score
            ),
            final_verdict=combined_verdict,
        )

        return RoutedDebateResult(
            debate_result=merged,
            provider_used=BackendId.LOCAL_OLLAMA,
            routing_decision=routing,
            audit_trail=audit_trail,
            final_verdict=combined_verdict,
            reject_reason=""
            if combined_verdict
            else "STRICT_DUAL: not all backends approved",
        )

    async def _execute_debate(
        self,
        backend_id: BackendId,
        role: str,
        correlation_id: UUID,
        symbol: str,
        side: str,
        price: "Decimal",  # type: ignore[name-defined]  # noqa: F821
        quantity: "Decimal",  # type: ignore[name-defined]  # noqa: F821
    ) -> tuple[Optional[DebateResult], RoutingAuditEntry]:
        """
        Execute a debate on a specific backend.

        Returns (result_or_None, audit_entry).
        """
        start = time.monotonic()
        try:
            if backend_id == BackendId.LOCAL_OLLAMA:
                from app.logic.ai_council import OllamaAICouncil

                council = OllamaAICouncil()
            elif backend_id == BackendId.OPENROUTER:
                from app.logic.ai_council import AICouncil

                council = AICouncil()
            else:
                return (
                    None,
                    RoutingAuditEntry(
                        backend_id=backend_id,
                        role=role,
                        outcome="FAILED",
                        failure_class=FailureClass.INVALID_ROUTING_CONFIG,
                        error_detail=f"Unknown backend: {backend_id}",
                    ),
                )

            result = await council.conduct_debate(
                correlation_id=correlation_id,
                symbol=symbol,
                side=side,
                price=price,
                quantity=quantity,
            )

            elapsed_ms = int((time.monotonic() - start) * 1000)

            # Check for error verdicts — both roles returning ERROR = failure
            if (
                result.bull_verdict == ModelVerdict.ERROR
                and result.bear_verdict == ModelVerdict.ERROR
            ):
                return (
                    None,
                    RoutingAuditEntry(
                        backend_id=backend_id,
                        role=role,
                        outcome="FAILED",
                        error_detail=(
                            f"Both roles returned ERROR: "
                            f"bull={result.bull_reasoning[:100]}, "
                            f"bear={result.bear_reasoning[:100]}"
                        ),
                        duration_ms=elapsed_ms,
                    ),
                )

            # One role ERROR, one role OK → partial failure
            if (
                result.bull_verdict == ModelVerdict.ERROR
                or result.bear_verdict == ModelVerdict.ERROR
            ):
                # Partial failure — still return result but it's auto-rejected
                # because consensus requires both APPROVED
                logger.warning(
                    "Partial debate failure on %s | bull=%s bear=%s | "
                    "correlation_id=%s",
                    backend_id.value,
                    result.bull_verdict.value,
                    result.bear_verdict.value,
                    correlation_id,
                )
                return (
                    result,
                    RoutingAuditEntry(
                        backend_id=backend_id,
                        role=role,
                        outcome="SUCCESS",
                        failure_class=FailureClass.PARTIAL_DEBATE_FAILURE,
                        error_detail=(
                            f"Partial: bull={result.bull_verdict.value}, "
                            f"bear={result.bear_verdict.value}"
                        ),
                        duration_ms=elapsed_ms,
                    ),
                )

            return (
                result,
                RoutingAuditEntry(
                    backend_id=backend_id,
                    role=role,
                    outcome="SUCCESS",
                    duration_ms=elapsed_ms,
                ),
            )

        except Exception as e:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            error_detail = f"{type(e).__name__}: {str(e)[:200]}"
            logger.error(
                "Debate execution failed on %s | error=%s | correlation_id=%s",
                backend_id.value,
                error_detail,
                correlation_id,
            )
            return (
                None,
                RoutingAuditEntry(
                    backend_id=backend_id,
                    role=role,
                    outcome="FAILED",
                    error_detail=error_detail,
                    duration_ms=elapsed_ms,
                ),
            )

    def _fail_closed(
        self,
        correlation_id: UUID,
        routing: RoutingDecision,
        audit_trail: List[RoutingAuditEntry],
        reason: str,
    ) -> RoutedDebateResult:
        """
        Fail-closed: return REJECTED with full audit trail.

        This is the ONLY codepath for total backend failure.
        """
        logger.error(
            "FAIL-CLOSED REJECT | correlation_id=%s | mode=%s | reason=%s",
            correlation_id,
            self.mode.value,
            reason,
        )
        return RoutedDebateResult(
            debate_result=None,
            provider_used=None,
            routing_decision=routing,
            audit_trail=audit_trail,
            final_verdict=False,
            reject_reason=reason,
        )

    def get_health_report(self) -> Dict[str, dict]:
        """Return health status of all backends for observability."""
        report = {}
        for bid, health in self.registry.get_all_health().items():
            report[bid.value] = {
                "status": health.status.value,
                "consecutive_failures": health.consecutive_failures,
                "last_failure_class": (
                    health.last_failure_class.value
                    if health.last_failure_class
                    else None
                ),
                "total_successes": health.total_successes,
                "total_failures": health.total_failures,
                "is_available": health.is_available(),
            }
        return report

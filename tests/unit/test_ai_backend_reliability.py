"""
Project Autonomous Alpha — Phase 7
AI Backend Reliability Manager — Test Suite

Reliability Level: SOVEREIGN TIER
Test Coverage:
    1.  Ollama healthy, used successfully
    2.  Ollama unavailable, OpenRouter fallback succeeds
    3.  Ollama unavailable, OpenRouter fails, final reject
    4.  OpenRouter auth/credit/rate-limit classification
    5.  Malformed output from either backend
    6.  One role fails / other succeeds handling
    7.  STRICT_DUAL_REQUIRED correctness
    8.  LOCAL_ONLY and CLOUD_ONLY correctness
    9.  Cooldown activation and recovery
    10. Routing audit visibility
    + Provider health registry
    + Failure classifier
    + Routing decision logic
"""

import time
from decimal import Decimal
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest

from app.logic.ai_backend_reliability import (
    DEFAULT_COOLDOWN_DURATIONS,
    EXTENDED_COOLDOWN_MULTIPLIER,
    MAX_CONSECUTIVE_FAILURES,
    AIBackendReliabilityManager,
    BackendHealth,
    BackendId,
    FailureClass,
    HealthStatus,
    ProviderHealthRegistry,
    ProviderMode,
    RoutingAuditEntry,
    classify_failure,
    compute_routing,
)
from app.logic.ai_council import DebateResult, ModelVerdict

_CID = UUID("a1b2c3d4-e5f6-4890-abcd-ef1234567890")
_PRICE = Decimal("1500000.00")
_QTY = Decimal("0.001")


def _make_debate(
    cid: UUID = _CID,
    bull: ModelVerdict = ModelVerdict.APPROVED,
    bear: ModelVerdict = ModelVerdict.APPROVED,
    score: int = 100,
    verdict: bool = True,
) -> DebateResult:
    return DebateResult(
        correlation_id=cid,
        bull_reasoning="Bull analysis text",
        bear_reasoning="Bear analysis text",
        bull_verdict=bull,
        bear_verdict=bear,
        consensus_score=score,
        final_verdict=verdict,
    )


def _make_rejected_debate(cid: UUID = _CID) -> DebateResult:
    return _make_debate(
        cid=cid,
        bull=ModelVerdict.APPROVED,
        bear=ModelVerdict.REJECTED,
        score=50,
        verdict=False,
    )


def _make_error_debate(cid: UUID = _CID) -> DebateResult:
    return _make_debate(
        cid=cid,
        bull=ModelVerdict.ERROR,
        bear=ModelVerdict.ERROR,
        score=0,
        verdict=False,
    )


def _make_partial_error_debate(cid: UUID = _CID) -> DebateResult:
    return DebateResult(
        correlation_id=cid,
        bull_reasoning="Bull analysis OK",
        bear_reasoning="ERR-OLLAMA-003: timeout",
        bull_verdict=ModelVerdict.APPROVED,
        bear_verdict=ModelVerdict.ERROR,
        consensus_score=0,
        final_verdict=False,
    )


# =============================================================================
# 1. PROVIDER HEALTH REGISTRY
# =============================================================================


class TestProviderHealthRegistry:
    def test_initial_status_unknown(self):
        reg = ProviderHealthRegistry()
        h = reg.get_health(BackendId.LOCAL_OLLAMA)
        assert h.status == HealthStatus.UNKNOWN

    def test_record_success(self):
        reg = ProviderHealthRegistry()
        reg.record_success(BackendId.LOCAL_OLLAMA)
        h = reg.get_health(BackendId.LOCAL_OLLAMA)
        assert h.status == HealthStatus.HEALTHY
        assert h.total_successes == 1
        assert h.consecutive_failures == 0

    def test_record_failure_sets_cooldown(self):
        reg = ProviderHealthRegistry()
        reg.record_failure(BackendId.LOCAL_OLLAMA, FailureClass.LOCAL_TIMEOUT)
        h = reg.get_health(BackendId.LOCAL_OLLAMA)
        assert h.status == HealthStatus.COOLDOWN
        assert h.consecutive_failures == 1
        assert h.cooldown_until is not None

    def test_consecutive_failures_escalate(self):
        reg = ProviderHealthRegistry()
        for _ in range(MAX_CONSECUTIVE_FAILURES):
            reg.record_failure(BackendId.LOCAL_OLLAMA, FailureClass.LOCAL_UNREACHABLE)
        h = reg.get_health(BackendId.LOCAL_OLLAMA)
        assert h.status == HealthStatus.UNAVAILABLE
        assert h.consecutive_failures == MAX_CONSECUTIVE_FAILURES

    def test_success_resets_failures(self):
        reg = ProviderHealthRegistry()
        reg.record_failure(BackendId.LOCAL_OLLAMA, FailureClass.LOCAL_TIMEOUT)
        reg.record_failure(BackendId.LOCAL_OLLAMA, FailureClass.LOCAL_TIMEOUT)
        reg.record_success(BackendId.LOCAL_OLLAMA)
        h = reg.get_health(BackendId.LOCAL_OLLAMA)
        assert h.consecutive_failures == 0
        assert h.status == HealthStatus.HEALTHY

    def test_reset_clears_state(self):
        reg = ProviderHealthRegistry()
        for _ in range(MAX_CONSECUTIVE_FAILURES):
            reg.record_failure(BackendId.OPENROUTER, FailureClass.CLOUD_SERVER_ERROR)
        reg.reset(BackendId.OPENROUTER)
        h = reg.get_health(BackendId.OPENROUTER)
        assert h.status == HealthStatus.UNKNOWN
        assert h.consecutive_failures == 0

    def test_get_all_health(self):
        reg = ProviderHealthRegistry()
        all_h = reg.get_all_health()
        assert BackendId.LOCAL_OLLAMA in all_h
        assert BackendId.OPENROUTER in all_h

    def test_both_backends_registered(self):
        reg = ProviderHealthRegistry()
        assert reg.is_available(BackendId.LOCAL_OLLAMA)
        assert reg.is_available(BackendId.OPENROUTER)


# =============================================================================
# 2. FAILURE CLASSIFIER
# =============================================================================


class TestFailureClassifier:
    def test_local_timeout(self):
        fc = classify_failure(
            BackendId.LOCAL_OLLAMA, "ERR-OLLAMA-003: timed out after 60s"
        )
        assert fc == FailureClass.LOCAL_TIMEOUT

    def test_local_unreachable(self):
        fc = classify_failure(
            BackendId.LOCAL_OLLAMA, "ERR-OLLAMA-004: request failed: connection refused"
        )
        assert fc == FailureClass.LOCAL_UNREACHABLE

    def test_local_model_missing(self):
        fc = classify_failure(
            BackendId.LOCAL_OLLAMA, "Model qwen3:8b not found on server"
        )
        assert fc == FailureClass.LOCAL_MODEL_MISSING

    def test_local_invalid_output(self):
        fc = classify_failure(
            BackendId.LOCAL_OLLAMA, "something weird", verdict=ModelVerdict.ERROR
        )
        assert fc == FailureClass.LOCAL_INVALID_OUTPUT

    def test_cloud_auth_failed(self):
        fc = classify_failure(
            BackendId.OPENROUTER, "ERR-AI-003: OpenRouter API key not configured"
        )
        assert fc == FailureClass.CLOUD_AUTH_FAILED

    def test_cloud_401(self):
        fc = classify_failure(
            BackendId.OPENROUTER, "ERR-AI-004: OpenRouter returned 401: Unauthorized"
        )
        assert fc == FailureClass.CLOUD_AUTH_FAILED

    def test_cloud_credits_exhausted(self):
        fc = classify_failure(
            BackendId.OPENROUTER, "OpenRouter returned 402: payment required"
        )
        assert fc == FailureClass.CLOUD_CREDITS_EXHAUSTED

    def test_cloud_rate_limited(self):
        fc = classify_failure(
            BackendId.OPENROUTER, "OpenRouter returned 429: rate limit exceeded"
        )
        assert fc == FailureClass.CLOUD_RATE_LIMITED

    def test_cloud_timeout(self):
        fc = classify_failure(
            BackendId.OPENROUTER, "ERR-AI-007: OpenRouter request timed out"
        )
        assert fc == FailureClass.CLOUD_TIMEOUT

    def test_cloud_server_error(self):
        fc = classify_failure(
            BackendId.OPENROUTER, "ERR-AI-004: OpenRouter returned 502: bad gateway"
        )
        assert fc == FailureClass.CLOUD_SERVER_ERROR

    def test_cloud_invalid_output(self):
        fc = classify_failure(
            BackendId.OPENROUTER, "strange", verdict=ModelVerdict.ERROR
        )
        assert fc == FailureClass.CLOUD_INVALID_OUTPUT

    def test_unknown_backend(self):
        fc = classify_failure("UNKNOWN", "something", verdict=None)  # type: ignore
        assert fc == FailureClass.INVALID_ROUTING_CONFIG


# =============================================================================
# 3. ROUTING DECISION LOGIC
# =============================================================================


class TestRoutingLogic:
    def _fresh_registry(
        self,
        local_ok: bool = True,
        cloud_ok: bool = True,
    ) -> ProviderHealthRegistry:
        reg = ProviderHealthRegistry()
        if local_ok:
            reg.record_success(BackendId.LOCAL_OLLAMA)
        else:
            for _ in range(MAX_CONSECUTIVE_FAILURES):
                reg.record_failure(
                    BackendId.LOCAL_OLLAMA, FailureClass.LOCAL_UNREACHABLE
                )
        if cloud_ok:
            reg.record_success(BackendId.OPENROUTER)
        else:
            for _ in range(MAX_CONSECUTIVE_FAILURES):
                reg.record_failure(
                    BackendId.OPENROUTER, FailureClass.CLOUD_SERVER_ERROR
                )
        return reg

    def test_local_preferred_local_available(self):
        reg = self._fresh_registry(local_ok=True, cloud_ok=True)
        r = compute_routing(ProviderMode.LOCAL_PREFERRED, reg)
        assert r.primary == BackendId.LOCAL_OLLAMA
        assert r.fallback == BackendId.OPENROUTER

    def test_local_preferred_local_down(self):
        reg = self._fresh_registry(local_ok=False, cloud_ok=True)
        r = compute_routing(ProviderMode.LOCAL_PREFERRED, reg)
        assert r.primary == BackendId.OPENROUTER
        assert r.fallback is None

    def test_local_preferred_all_down(self):
        reg = self._fresh_registry(local_ok=False, cloud_ok=False)
        r = compute_routing(ProviderMode.LOCAL_PREFERRED, reg)
        assert r.primary is None

    def test_cloud_preferred_cloud_available(self):
        reg = self._fresh_registry(local_ok=True, cloud_ok=True)
        r = compute_routing(ProviderMode.CLOUD_PREFERRED, reg)
        assert r.primary == BackendId.OPENROUTER
        assert r.fallback == BackendId.LOCAL_OLLAMA

    def test_cloud_preferred_cloud_down(self):
        reg = self._fresh_registry(local_ok=True, cloud_ok=False)
        r = compute_routing(ProviderMode.CLOUD_PREFERRED, reg)
        assert r.primary == BackendId.LOCAL_OLLAMA

    def test_local_only_available(self):
        reg = self._fresh_registry(local_ok=True, cloud_ok=True)
        r = compute_routing(ProviderMode.LOCAL_ONLY, reg)
        assert r.primary == BackendId.LOCAL_OLLAMA
        assert r.fallback is None

    def test_local_only_unavailable(self):
        reg = self._fresh_registry(local_ok=False, cloud_ok=True)
        r = compute_routing(ProviderMode.LOCAL_ONLY, reg)
        assert r.primary is None

    def test_cloud_only_available(self):
        reg = self._fresh_registry(local_ok=True, cloud_ok=True)
        r = compute_routing(ProviderMode.CLOUD_ONLY, reg)
        assert r.primary == BackendId.OPENROUTER
        assert r.fallback is None

    def test_cloud_only_unavailable(self):
        reg = self._fresh_registry(local_ok=True, cloud_ok=False)
        r = compute_routing(ProviderMode.CLOUD_ONLY, reg)
        assert r.primary is None

    def test_strict_dual_both_available(self):
        reg = self._fresh_registry(local_ok=True, cloud_ok=True)
        r = compute_routing(ProviderMode.STRICT_DUAL_REQUIRED, reg)
        assert r.primary == BackendId.LOCAL_OLLAMA
        assert r.fallback == BackendId.OPENROUTER

    def test_strict_dual_one_missing(self):
        reg = self._fresh_registry(local_ok=True, cloud_ok=False)
        r = compute_routing(ProviderMode.STRICT_DUAL_REQUIRED, reg)
        assert r.primary is None


# =============================================================================
# 4. COOLDOWN ACTIVATION AND RECOVERY
# =============================================================================


class TestCooldownBehavior:
    def test_cooldown_blocks_availability(self):
        h = BackendHealth(backend_id=BackendId.LOCAL_OLLAMA)
        h.record_failure(FailureClass.LOCAL_TIMEOUT)
        assert not h.is_available()

    def test_cooldown_expires(self):
        h = BackendHealth(backend_id=BackendId.LOCAL_OLLAMA)
        h.record_failure(FailureClass.LOCAL_INVALID_OUTPUT)
        # Force cooldown to have expired
        h.cooldown_until = time.monotonic() - 1
        assert h.is_available()
        assert h.status == HealthStatus.DEGRADED

    def test_extended_cooldown_after_max_failures(self):
        h = BackendHealth(backend_id=BackendId.LOCAL_OLLAMA)
        for _ in range(MAX_CONSECUTIVE_FAILURES):
            h.record_failure(FailureClass.LOCAL_UNREACHABLE)
        assert h.status == HealthStatus.UNAVAILABLE
        # Extended cooldown = base * multiplier
        base = DEFAULT_COOLDOWN_DURATIONS[FailureClass.LOCAL_UNREACHABLE]
        expected = base * EXTENDED_COOLDOWN_MULTIPLIER
        # cooldown_until should be approximately now + expected
        remaining = h.cooldown_until - time.monotonic()
        assert remaining > 0
        assert remaining <= expected + 1  # ±1s tolerance

    def test_success_clears_cooldown(self):
        h = BackendHealth(backend_id=BackendId.LOCAL_OLLAMA)
        h.record_failure(FailureClass.LOCAL_TIMEOUT)
        h.record_success()
        assert h.cooldown_until is None
        assert h.is_available()


# =============================================================================
# 5. MANAGER — OLLAMA HEALTHY, USED SUCCESSFULLY
# =============================================================================


class TestOllamaHealthySuccess:
    @pytest.mark.asyncio
    async def test_local_preferred_local_succeeds(self):
        """Ollama healthy → used as primary, debate result returned."""
        mgr = AIBackendReliabilityManager(mode=ProviderMode.LOCAL_PREFERRED)
        mgr.registry.record_success(BackendId.LOCAL_OLLAMA)
        mgr.registry.record_success(BackendId.OPENROUTER)

        expected = _make_debate()
        with patch(
            "app.logic.ai_backend_reliability.AIBackendReliabilityManager._execute_debate"
        ) as mock_exec:
            mock_exec.return_value = (
                expected,
                RoutingAuditEntry(
                    backend_id=BackendId.LOCAL_OLLAMA,
                    role="PRIMARY",
                    outcome="SUCCESS",
                    duration_ms=150,
                ),
            )
            result = await mgr.route_debate(_CID, "BTCZAR", "BUY", _PRICE, _QTY)

        assert result.final_verdict is True
        assert result.provider_used == BackendId.LOCAL_OLLAMA
        assert result.debate_result is not None
        assert result.debate_result.consensus_score == 100


# =============================================================================
# 6. OLLAMA UNAVAILABLE, OPENROUTER FALLBACK SUCCEEDS
# =============================================================================


class TestOllamaDownCloudFallback:
    @pytest.mark.asyncio
    async def test_fallback_to_cloud_on_local_failure(self):
        """Ollama fails → OpenRouter fallback succeeds."""
        mgr = AIBackendReliabilityManager(mode=ProviderMode.LOCAL_PREFERRED)
        mgr.registry.record_success(BackendId.LOCAL_OLLAMA)
        mgr.registry.record_success(BackendId.OPENROUTER)

        expected = _make_debate()
        call_count = 0

        async def mock_execute(backend_id, role, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            if backend_id == BackendId.LOCAL_OLLAMA:
                return (
                    None,
                    RoutingAuditEntry(
                        backend_id=BackendId.LOCAL_OLLAMA,
                        role=role,
                        outcome="FAILED",
                        error_detail="ERR-OLLAMA-004: request failed: connection refused",
                        duration_ms=50,
                    ),
                )
            return (
                expected,
                RoutingAuditEntry(
                    backend_id=BackendId.OPENROUTER,
                    role=role,
                    outcome="SUCCESS",
                    duration_ms=200,
                ),
            )

        mgr._execute_debate = mock_execute  # type: ignore
        result = await mgr.route_debate(_CID, "BTCZAR", "BUY", _PRICE, _QTY)

        assert result.final_verdict is True
        assert result.provider_used == BackendId.OPENROUTER
        assert len(result.audit_trail) == 2
        assert result.audit_trail[0].outcome == "FAILED"
        assert result.audit_trail[1].outcome == "SUCCESS"


# =============================================================================
# 7. BOTH BACKENDS FAIL → REJECT
# =============================================================================


class TestAllBackendsFail:
    @pytest.mark.asyncio
    async def test_all_fail_reject(self):
        """Both Ollama and OpenRouter fail → fail-closed REJECTED."""
        mgr = AIBackendReliabilityManager(mode=ProviderMode.LOCAL_PREFERRED)
        mgr.registry.record_success(BackendId.LOCAL_OLLAMA)
        mgr.registry.record_success(BackendId.OPENROUTER)

        async def mock_execute(backend_id, role, *args, **kwargs):
            return (
                None,
                RoutingAuditEntry(
                    backend_id=backend_id,
                    role=role,
                    outcome="FAILED",
                    error_detail="Connection refused",
                    duration_ms=50,
                ),
            )

        mgr._execute_debate = mock_execute  # type: ignore
        result = await mgr.route_debate(_CID, "BTCZAR", "BUY", _PRICE, _QTY)

        assert result.final_verdict is False
        assert result.debate_result is None
        assert result.provider_used is None
        assert "All eligible backends failed" in result.reject_reason

    @pytest.mark.asyncio
    async def test_no_backends_available_reject(self):
        """Both backends in cooldown → immediate fail-closed."""
        mgr = AIBackendReliabilityManager(mode=ProviderMode.LOCAL_PREFERRED)
        for _ in range(MAX_CONSECUTIVE_FAILURES):
            mgr.registry.record_failure(
                BackendId.LOCAL_OLLAMA, FailureClass.LOCAL_UNREACHABLE
            )
            mgr.registry.record_failure(
                BackendId.OPENROUTER, FailureClass.CLOUD_SERVER_ERROR
            )

        result = await mgr.route_debate(_CID, "BTCZAR", "BUY", _PRICE, _QTY)
        assert result.final_verdict is False
        assert result.provider_used is None


# =============================================================================
# 8. OPENROUTER AUTH/CREDIT/RATE-LIMIT CLASSIFICATION
# =============================================================================


class TestCloudFailureClassification:
    @pytest.mark.asyncio
    async def test_auth_failure_classified(self):
        """OpenRouter 401 → CLOUD_AUTH_FAILED, cooldown applied."""
        mgr = AIBackendReliabilityManager(mode=ProviderMode.CLOUD_ONLY)
        mgr.registry.record_success(BackendId.OPENROUTER)

        async def mock_execute(backend_id, role, *args, **kwargs):
            return (
                None,
                RoutingAuditEntry(
                    backend_id=BackendId.OPENROUTER,
                    role=role,
                    outcome="FAILED",
                    error_detail="ERR-AI-003: OpenRouter API key not configured",
                    duration_ms=10,
                ),
            )

        mgr._execute_debate = mock_execute  # type: ignore
        result = await mgr.route_debate(_CID, "BTCZAR", "BUY", _PRICE, _QTY)

        assert result.final_verdict is False
        h = mgr.registry.get_health(BackendId.OPENROUTER)
        assert h.last_failure_class == FailureClass.CLOUD_AUTH_FAILED


# =============================================================================
# 9. MALFORMED OUTPUT
# =============================================================================


class TestMalformedOutput:
    @pytest.mark.asyncio
    async def test_both_roles_error_is_failure(self):
        """Both bull+bear return ERROR → treated as backend failure."""
        mgr = AIBackendReliabilityManager(mode=ProviderMode.LOCAL_ONLY)
        mgr.registry.record_success(BackendId.LOCAL_OLLAMA)

        error_debate = _make_error_debate()

        # Patch at the council level to return error debate
        with patch(
            "app.logic.ai_council.OllamaAICouncil.conduct_debate",
            new_callable=AsyncMock,
        ) as mock_cd:
            mock_cd.return_value = error_debate
            result = await mgr.route_debate(_CID, "BTCZAR", "BUY", _PRICE, _QTY)

        assert result.final_verdict is False
        assert len(result.audit_trail) >= 1
        assert result.audit_trail[0].outcome == "FAILED"

    @pytest.mark.asyncio
    async def test_partial_error_returns_result_but_rejected(self):
        """One role ERROR, one OK → result returned but auto-rejected."""
        mgr = AIBackendReliabilityManager(mode=ProviderMode.LOCAL_ONLY)
        mgr.registry.record_success(BackendId.LOCAL_OLLAMA)

        partial = _make_partial_error_debate()

        with patch(
            "app.logic.ai_council.OllamaAICouncil.conduct_debate",
            new_callable=AsyncMock,
        ) as mock_cd:
            mock_cd.return_value = partial
            result = await mgr.route_debate(_CID, "BTCZAR", "BUY", _PRICE, _QTY)

        assert result.final_verdict is False
        assert result.debate_result is not None
        assert (
            result.audit_trail[0].failure_class == FailureClass.PARTIAL_DEBATE_FAILURE
        )


# =============================================================================
# 10. STRICT_DUAL_REQUIRED CORRECTNESS
# =============================================================================


class TestStrictDualRequired:
    @pytest.mark.asyncio
    async def test_both_succeed_both_approve(self):
        """Strict dual: both backends succeed + approve → APPROVED."""
        mgr = AIBackendReliabilityManager(mode=ProviderMode.STRICT_DUAL_REQUIRED)
        mgr.registry.record_success(BackendId.LOCAL_OLLAMA)
        mgr.registry.record_success(BackendId.OPENROUTER)

        approved = _make_debate()

        async def mock_execute(backend_id, role, *args, **kwargs):
            return (
                approved,
                RoutingAuditEntry(
                    backend_id=backend_id,
                    role=role,
                    outcome="SUCCESS",
                    duration_ms=100,
                ),
            )

        mgr._execute_debate = mock_execute  # type: ignore
        result = await mgr.route_debate(_CID, "BTCZAR", "BUY", _PRICE, _QTY)

        assert result.final_verdict is True
        assert len(result.audit_trail) == 2

    @pytest.mark.asyncio
    async def test_one_fails_both_rejected(self):
        """Strict dual: one backend fails → entire debate rejected."""
        mgr = AIBackendReliabilityManager(mode=ProviderMode.STRICT_DUAL_REQUIRED)
        mgr.registry.record_success(BackendId.LOCAL_OLLAMA)
        mgr.registry.record_success(BackendId.OPENROUTER)

        approved = _make_debate()

        async def mock_execute(backend_id, role, *args, **kwargs):
            if backend_id == BackendId.OPENROUTER:
                return (
                    None,
                    RoutingAuditEntry(
                        backend_id=backend_id,
                        role=role,
                        outcome="FAILED",
                        error_detail="timeout",
                        duration_ms=5000,
                    ),
                )
            return (
                approved,
                RoutingAuditEntry(
                    backend_id=backend_id,
                    role=role,
                    outcome="SUCCESS",
                    duration_ms=100,
                ),
            )

        mgr._execute_debate = mock_execute  # type: ignore
        result = await mgr.route_debate(_CID, "BTCZAR", "BUY", _PRICE, _QTY)

        assert result.final_verdict is False
        assert "STRICT_DUAL_REQUIRED" in result.reject_reason

    @pytest.mark.asyncio
    async def test_both_succeed_one_rejects(self):
        """Strict dual: both backends succeed but one rejects → REJECTED."""
        mgr = AIBackendReliabilityManager(mode=ProviderMode.STRICT_DUAL_REQUIRED)
        mgr.registry.record_success(BackendId.LOCAL_OLLAMA)
        mgr.registry.record_success(BackendId.OPENROUTER)

        approved = _make_debate(verdict=True, score=100)
        rejected = _make_rejected_debate()

        call_num = 0

        async def mock_execute(backend_id, role, *args, **kwargs):
            nonlocal call_num
            call_num += 1
            d = approved if backend_id == BackendId.LOCAL_OLLAMA else rejected
            return (
                d,
                RoutingAuditEntry(
                    backend_id=backend_id,
                    role=role,
                    outcome="SUCCESS",
                    duration_ms=100,
                ),
            )

        mgr._execute_debate = mock_execute  # type: ignore
        result = await mgr.route_debate(_CID, "BTCZAR", "BUY", _PRICE, _QTY)

        assert result.final_verdict is False

    @pytest.mark.asyncio
    async def test_one_backend_unavailable_rejects(self):
        """Strict dual with one backend down → immediate reject."""
        mgr = AIBackendReliabilityManager(mode=ProviderMode.STRICT_DUAL_REQUIRED)
        mgr.registry.record_success(BackendId.LOCAL_OLLAMA)
        for _ in range(MAX_CONSECUTIVE_FAILURES):
            mgr.registry.record_failure(
                BackendId.OPENROUTER, FailureClass.CLOUD_SERVER_ERROR
            )

        result = await mgr.route_debate(_CID, "BTCZAR", "BUY", _PRICE, _QTY)
        assert result.final_verdict is False


# =============================================================================
# 11. LOCAL_ONLY AND CLOUD_ONLY CORRECTNESS
# =============================================================================


class TestModeCorrectness:
    @pytest.mark.asyncio
    async def test_local_only_no_fallback(self):
        """LOCAL_ONLY: local fails → no fallback, straight reject."""
        mgr = AIBackendReliabilityManager(mode=ProviderMode.LOCAL_ONLY)
        mgr.registry.record_success(BackendId.LOCAL_OLLAMA)
        mgr.registry.record_success(BackendId.OPENROUTER)

        async def mock_execute(backend_id, role, *args, **kwargs):
            return (
                None,
                RoutingAuditEntry(
                    backend_id=backend_id,
                    role=role,
                    outcome="FAILED",
                    error_detail="connection refused",
                    duration_ms=50,
                ),
            )

        mgr._execute_debate = mock_execute  # type: ignore
        result = await mgr.route_debate(_CID, "BTCZAR", "BUY", _PRICE, _QTY)

        assert result.final_verdict is False
        # Should only have ONE audit entry (no fallback attempted)
        assert len(result.audit_trail) == 1
        assert result.audit_trail[0].backend_id == BackendId.LOCAL_OLLAMA

    @pytest.mark.asyncio
    async def test_cloud_only_no_fallback(self):
        """CLOUD_ONLY: cloud fails → no fallback, straight reject."""
        mgr = AIBackendReliabilityManager(mode=ProviderMode.CLOUD_ONLY)
        mgr.registry.record_success(BackendId.OPENROUTER)

        async def mock_execute(backend_id, role, *args, **kwargs):
            return (
                None,
                RoutingAuditEntry(
                    backend_id=backend_id,
                    role=role,
                    outcome="FAILED",
                    error_detail="timeout",
                    duration_ms=5000,
                ),
            )

        mgr._execute_debate = mock_execute  # type: ignore
        result = await mgr.route_debate(_CID, "BTCZAR", "BUY", _PRICE, _QTY)

        assert result.final_verdict is False
        assert len(result.audit_trail) == 1
        assert result.audit_trail[0].backend_id == BackendId.OPENROUTER

    @pytest.mark.asyncio
    async def test_local_only_success(self):
        """LOCAL_ONLY: local succeeds → approved."""
        mgr = AIBackendReliabilityManager(mode=ProviderMode.LOCAL_ONLY)
        mgr.registry.record_success(BackendId.LOCAL_OLLAMA)

        approved = _make_debate()
        with patch(
            "app.logic.ai_backend_reliability.AIBackendReliabilityManager._execute_debate"
        ) as mock_exec:
            mock_exec.return_value = (
                approved,
                RoutingAuditEntry(
                    backend_id=BackendId.LOCAL_OLLAMA,
                    role="PRIMARY",
                    outcome="SUCCESS",
                    duration_ms=100,
                ),
            )
            result = await mgr.route_debate(_CID, "BTCZAR", "BUY", _PRICE, _QTY)

        assert result.final_verdict is True
        assert result.provider_used == BackendId.LOCAL_OLLAMA


# =============================================================================
# 12. ROUTING AUDIT VISIBILITY
# =============================================================================


class TestRoutingAuditVisibility:
    @pytest.mark.asyncio
    async def test_audit_trail_populated(self):
        """Every routing attempt produces an audit entry."""
        mgr = AIBackendReliabilityManager(mode=ProviderMode.LOCAL_PREFERRED)
        mgr.registry.record_success(BackendId.LOCAL_OLLAMA)
        mgr.registry.record_success(BackendId.OPENROUTER)

        approved = _make_debate()

        async def mock_execute(backend_id, role, *args, **kwargs):
            if backend_id == BackendId.LOCAL_OLLAMA:
                return (
                    None,
                    RoutingAuditEntry(
                        backend_id=BackendId.LOCAL_OLLAMA,
                        role="PRIMARY",
                        outcome="FAILED",
                        error_detail="timeout",
                        duration_ms=5000,
                    ),
                )
            return (
                approved,
                RoutingAuditEntry(
                    backend_id=BackendId.OPENROUTER,
                    role="FALLBACK",
                    outcome="SUCCESS",
                    duration_ms=200,
                ),
            )

        mgr._execute_debate = mock_execute  # type: ignore
        result = await mgr.route_debate(_CID, "BTCZAR", "BUY", _PRICE, _QTY)

        assert len(result.audit_trail) == 2
        assert result.audit_trail[0].role == "PRIMARY"
        assert result.audit_trail[0].outcome == "FAILED"
        assert result.audit_trail[1].role == "FALLBACK"
        assert result.audit_trail[1].outcome == "SUCCESS"

    @pytest.mark.asyncio
    async def test_routing_decision_in_result(self):
        """Routing decision is always included in result."""
        mgr = AIBackendReliabilityManager(mode=ProviderMode.LOCAL_PREFERRED)
        for _ in range(MAX_CONSECUTIVE_FAILURES):
            mgr.registry.record_failure(
                BackendId.LOCAL_OLLAMA, FailureClass.LOCAL_UNREACHABLE
            )
            mgr.registry.record_failure(
                BackendId.OPENROUTER, FailureClass.CLOUD_SERVER_ERROR
            )

        result = await mgr.route_debate(_CID, "BTCZAR", "BUY", _PRICE, _QTY)
        assert result.routing_decision is not None
        assert result.routing_decision.mode == ProviderMode.LOCAL_PREFERRED

    def test_health_report(self):
        """Health report exposes all backend states."""
        mgr = AIBackendReliabilityManager()
        mgr.registry.record_success(BackendId.LOCAL_OLLAMA)
        mgr.registry.record_failure(BackendId.OPENROUTER, FailureClass.CLOUD_TIMEOUT)

        report = mgr.get_health_report()
        assert "LOCAL_OLLAMA" in report
        assert "OPENROUTER" in report
        assert report["LOCAL_OLLAMA"]["status"] == "HEALTHY"
        assert report["OPENROUTER"]["status"] == "COOLDOWN"
        assert report["OPENROUTER"]["last_failure_class"] == "CLOUD_TIMEOUT"


# =============================================================================
# 13. FAIL-CLOSED BEHAVIOR
# =============================================================================


class TestFailClosedBehavior:
    @pytest.mark.asyncio
    async def test_fail_closed_returns_false_verdict(self):
        """Fail-closed always returns final_verdict=False."""
        mgr = AIBackendReliabilityManager()
        for _ in range(MAX_CONSECUTIVE_FAILURES):
            mgr.registry.record_failure(
                BackendId.LOCAL_OLLAMA, FailureClass.LOCAL_UNREACHABLE
            )
            mgr.registry.record_failure(
                BackendId.OPENROUTER, FailureClass.CLOUD_SERVER_ERROR
            )

        result = await mgr.route_debate(_CID, "BTCZAR", "BUY", _PRICE, _QTY)
        assert result.final_verdict is False
        assert result.is_rejected is True
        assert result.debate_result is None

    @pytest.mark.asyncio
    async def test_fail_closed_has_reject_reason(self):
        """Fail-closed result includes human-readable reject reason."""
        mgr = AIBackendReliabilityManager()
        for _ in range(MAX_CONSECUTIVE_FAILURES):
            mgr.registry.record_failure(
                BackendId.LOCAL_OLLAMA, FailureClass.LOCAL_UNREACHABLE
            )
            mgr.registry.record_failure(
                BackendId.OPENROUTER, FailureClass.CLOUD_SERVER_ERROR
            )

        result = await mgr.route_debate(_CID, "BTCZAR", "BUY", _PRICE, _QTY)
        assert result.reject_reason != ""

    @pytest.mark.asyncio
    async def test_correlation_id_none_when_no_debate(self):
        """When no debate executed, correlation_id property returns None."""
        mgr = AIBackendReliabilityManager()
        for _ in range(MAX_CONSECUTIVE_FAILURES):
            mgr.registry.record_failure(
                BackendId.LOCAL_OLLAMA, FailureClass.LOCAL_UNREACHABLE
            )
            mgr.registry.record_failure(
                BackendId.OPENROUTER, FailureClass.CLOUD_SERVER_ERROR
            )

        result = await mgr.route_debate(_CID, "BTCZAR", "BUY", _PRICE, _QTY)
        assert result.correlation_id is None


# =============================================================================
# 14. DEFAULT MODE
# =============================================================================


class TestDefaultMode:
    def test_default_mode_is_local_preferred(self):
        mgr = AIBackendReliabilityManager()
        assert mgr.mode == ProviderMode.LOCAL_PREFERRED


# =============================================================================
# 15. PROVIDER DECISION CONSISTENCY GUARD
# =============================================================================


class TestProviderConsistencyGuard:
    """Provider Decision Consistency Guard — AI-016 PROVIDER_DISAGREEMENT."""

    @pytest.mark.asyncio
    async def test_strict_dual_agreement_passes(self):
        """Both providers agree → approved, no disagreement flag."""
        mgr = AIBackendReliabilityManager(mode=ProviderMode.STRICT_DUAL_REQUIRED)
        mgr.registry.record_success(BackendId.LOCAL_OLLAMA)
        mgr.registry.record_success(BackendId.OPENROUTER)

        approved = _make_debate(verdict=True, score=100)

        async def mock_execute(backend_id, role, *args, **kwargs):
            return (
                approved,
                RoutingAuditEntry(
                    backend_id=backend_id,
                    role=role,
                    outcome="SUCCESS",
                    duration_ms=100,
                ),
            )

        mgr._execute_debate = mock_execute  # type: ignore
        result = await mgr.route_debate(_CID, "BTCZAR", "BUY", _PRICE, _QTY)

        assert result.final_verdict is True
        assert result.provider_disagreement is False
        assert result.degraded_context is False

    @pytest.mark.asyncio
    async def test_strict_dual_disagreement_rejects(self):
        """Providers disagree on verdict in STRICT mode → AI-016 REJECT."""
        mgr = AIBackendReliabilityManager(mode=ProviderMode.STRICT_DUAL_REQUIRED)
        mgr.registry.record_success(BackendId.LOCAL_OLLAMA)
        mgr.registry.record_success(BackendId.OPENROUTER)

        approved = _make_debate(verdict=True, score=100)
        rejected = _make_rejected_debate()

        async def mock_execute(backend_id, role, *args, **kwargs):
            if backend_id == BackendId.LOCAL_OLLAMA:
                return (
                    approved,
                    RoutingAuditEntry(
                        backend_id=backend_id,
                        role=role,
                        outcome="SUCCESS",
                        duration_ms=100,
                    ),
                )
            return (
                rejected,
                RoutingAuditEntry(
                    backend_id=backend_id,
                    role=role,
                    outcome="SUCCESS",
                    duration_ms=200,
                ),
            )

        mgr._execute_debate = mock_execute  # type: ignore
        result = await mgr.route_debate(_CID, "BTCZAR", "BUY", _PRICE, _QTY)

        assert result.final_verdict is False
        assert result.provider_disagreement is True
        assert "AI-016" in result.reject_reason
        assert "PROVIDER_DISAGREEMENT" in result.reject_reason
        # Audit trail must contain CONSISTENCY_GUARD entry
        guard_entries = [e for e in result.audit_trail if e.role == "CONSISTENCY_GUARD"]
        assert len(guard_entries) == 1
        assert guard_entries[0].failure_class == FailureClass.PROVIDER_DISAGREEMENT

    @pytest.mark.asyncio
    async def test_fallback_marks_degraded_context(self):
        """Primary fails, fallback succeeds → degraded_context=True."""
        mgr = AIBackendReliabilityManager(mode=ProviderMode.LOCAL_PREFERRED)
        mgr.registry.record_success(BackendId.LOCAL_OLLAMA)
        mgr.registry.record_success(BackendId.OPENROUTER)

        approved = _make_debate(verdict=True, score=90)

        async def mock_execute(backend_id, role, *args, **kwargs):
            if backend_id == BackendId.LOCAL_OLLAMA:
                return (
                    None,
                    RoutingAuditEntry(
                        backend_id=BackendId.LOCAL_OLLAMA,
                        role="PRIMARY",
                        outcome="FAILED",
                        error_detail="connection refused",
                        duration_ms=50,
                    ),
                )
            return (
                approved,
                RoutingAuditEntry(
                    backend_id=BackendId.OPENROUTER,
                    role="FALLBACK",
                    outcome="SUCCESS",
                    duration_ms=200,
                ),
            )

        mgr._execute_debate = mock_execute  # type: ignore
        result = await mgr.route_debate(_CID, "BTCZAR", "BUY", _PRICE, _QTY)

        assert result.final_verdict is True
        assert result.degraded_context is True
        assert result.provider_disagreement is False

    @pytest.mark.asyncio
    async def test_single_provider_success_no_degraded(self):
        """Primary succeeds on first try → no degraded context."""
        mgr = AIBackendReliabilityManager(mode=ProviderMode.LOCAL_PREFERRED)
        mgr.registry.record_success(BackendId.LOCAL_OLLAMA)

        approved = _make_debate(verdict=True, score=100)

        async def mock_execute(backend_id, role, *args, **kwargs):
            return (
                approved,
                RoutingAuditEntry(
                    backend_id=backend_id,
                    role=role,
                    outcome="SUCCESS",
                    duration_ms=100,
                ),
            )

        mgr._execute_debate = mock_execute  # type: ignore
        result = await mgr.route_debate(_CID, "BTCZAR", "BUY", _PRICE, _QTY)

        assert result.final_verdict is True
        assert result.degraded_context is False
        assert result.provider_disagreement is False

    @pytest.mark.asyncio
    async def test_both_fail_fail_closed(self):
        """Both providers fail → fail-closed, no disagreement flag."""
        mgr = AIBackendReliabilityManager(mode=ProviderMode.LOCAL_PREFERRED)
        mgr.registry.record_success(BackendId.LOCAL_OLLAMA)
        mgr.registry.record_success(BackendId.OPENROUTER)

        async def mock_execute(backend_id, role, *args, **kwargs):
            return (
                None,
                RoutingAuditEntry(
                    backend_id=backend_id,
                    role=role,
                    outcome="FAILED",
                    error_detail="timeout",
                    duration_ms=5000,
                ),
            )

        mgr._execute_debate = mock_execute  # type: ignore
        result = await mgr.route_debate(_CID, "BTCZAR", "BUY", _PRICE, _QTY)

        assert result.final_verdict is False
        assert result.is_rejected is True
        assert result.provider_disagreement is False
        assert result.degraded_context is False

    def test_failure_class_enum_has_provider_disagreement(self):
        """AI-016 PROVIDER_DISAGREEMENT exists in FailureClass."""
        assert hasattr(FailureClass, "PROVIDER_DISAGREEMENT")
        assert FailureClass.PROVIDER_DISAGREEMENT.value == "PROVIDER_DISAGREEMENT"

    @pytest.mark.asyncio
    async def test_strict_dual_both_reject_no_disagreement(self):
        """Both providers reject → no disagreement (they agree on reject)."""
        mgr = AIBackendReliabilityManager(mode=ProviderMode.STRICT_DUAL_REQUIRED)
        mgr.registry.record_success(BackendId.LOCAL_OLLAMA)
        mgr.registry.record_success(BackendId.OPENROUTER)

        rejected = _make_rejected_debate()

        async def mock_execute(backend_id, role, *args, **kwargs):
            return (
                rejected,
                RoutingAuditEntry(
                    backend_id=backend_id,
                    role=role,
                    outcome="SUCCESS",
                    duration_ms=100,
                ),
            )

        mgr._execute_debate = mock_execute  # type: ignore
        result = await mgr.route_debate(_CID, "BTCZAR", "BUY", _PRICE, _QTY)

        assert result.final_verdict is False
        assert result.provider_disagreement is False
        # Both agree on reject → no AI-016
        assert "AI-016" not in result.reject_reason

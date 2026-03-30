"""
Project Autonomous Alpha — Phase 8
DualModeReasoner — Test Suite

Reliability Level: SOVEREIGN TIER
Test Coverage (16 categories from DUAL_MODE_REASONING_PLAN.md §12.1):
    1.  FAST mode normal — APPROVED verdict
    2.  FAST mode reject — REJECTED verdict
    3.  FAST mode escalates to DEEP
    4.  DEEP mode resolves after escalation
    5.  DEEP mode rejects after escalation
    6.  No escalation path — clean signal
    7.  Degraded context escalation
    8.  Token budget mode configs
    9.  Structured output parsing
   10.  Verdict parsing edge cases
   11.  Audit logging populated
   12.  Provider degraded path
   13.  No escalation loops
   14.  Single-model invariant
   15.  Comparative FAST vs DEEP
   16.  Fail-closed on parse failure
   17.  DEEP disabled override
   18.  FAST disabled override
   19.  Ollama error handling
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.logic.dual_mode_reasoner import (
    DualModeReasoner,
    parse_verdict,
)
from app.logic.escalation_policy import (
    EscalationPolicy,
)
from app.logic.reasoning_mode import (
    ConfidenceBand,
    DeepReasonCode,
    EscalationRejectCode,
    EscalationThresholds,
    FastReasonCode,
    ReasoningMode,
    SystemMaturity,
    get_mode_config,
)

# ── Helpers ──────────────────────────────────────────────────────────────────

FAST_APPROVED_RESPONSE = """
---VERDICT---
verdict: APPROVED
reason_code: FAST-APPROVE-CLEAR
confidence_band: HIGH
reasoning: Strong buy signal confirmed by volume and price action
reasoning_mode: FAST
spec_version: 1.0
fact_count: 5
---END---
""".strip()

FAST_REJECTED_RESPONSE = """
---VERDICT---
verdict: REJECTED
reason_code: FAST-REJECT-RISK
confidence_band: MEDIUM
reasoning: Risk-reward ratio unfavorable
reasoning_mode: FAST
spec_version: 1.0
fact_count: 3
---END---
""".strip()

FAST_ESCALATE_RESPONSE = """
---VERDICT---
verdict: REJECTED
reason_code: FAST-ESCALATE-AMBIGUITY
confidence_band: LOW
reasoning: Signal ambiguous, requires deeper analysis
reasoning_mode: FAST
spec_version: 1.0
fact_count: 2
---END---
""".strip()

DEEP_APPROVED_RESPONSE = """
---VERDICT---
verdict: APPROVED
reason_code: DEEP-APPROVE-RESOLVED
confidence_band: HIGH
reasoning: Contradiction resolved, signal is valid after deep analysis
reasoning_mode: DEEP
spec_version: 1.0
fact_count: 8
contradiction_count: 1
inference_count: 2
missing_data_impact: none
escalation_resolved: true
---END---
""".strip()

DEEP_REJECTED_RESPONSE = """
---VERDICT---
verdict: REJECTED
reason_code: DEEP-REJECT-CONTRADICTION
confidence_band: LOW
reasoning: Irreconcilable contradiction between price and volume signals
reasoning_mode: DEEP
spec_version: 1.0
fact_count: 6
contradiction_count: 2
inference_count: 1
missing_data_impact: moderate
escalation_resolved: false
---END---
""".strip()

MALFORMED_RESPONSE = "This is not a valid response. No verdict block here."

PARTIAL_VERDICT_RESPONSE = """
---VERDICT---
verdict: APPROVED
---END---
""".strip()


def _mock_ollama_response(text: str, status_code: int = 200) -> httpx.Response:
    """Create a mock httpx Response with Ollama-like JSON."""
    response = MagicMock(spec=httpx.Response)
    response.status_code = status_code
    response.text = text
    response.json.return_value = {"response": text}
    return response


def _make_reasoner(
    policy: EscalationPolicy | None = None,
    deep_disabled: bool = False,
    fast_disabled: bool = False,
) -> DualModeReasoner:
    """Create a DualModeReasoner with mocked env vars."""
    env_vars = {
        "OLLAMA_BASE_URL": "http://test:11434",
        "OLLAMA_MODEL": "qwen3:8b",
        "DEEP_MODE_FORCE_DISABLED": "true" if deep_disabled else "",
        "FAST_MODE_FORCE_DISABLED": "true" if fast_disabled else "",
    }
    with patch.dict("os.environ", env_vars, clear=False):
        if policy is None:
            thresholds = EscalationThresholds(
                t2_missing_threshold=2,
                t2_missing_cold_start=4,
                cold_start_debates=20,
                high_notional_paper=5000,
                deep_mode_timeout=60,
                force_deep_symbols=[],
            )
            policy = EscalationPolicy(
                thresholds=thresholds,
                maturity=SystemMaturity.OPERATIONAL,
                completed_debates=25,
            )
        return DualModeReasoner(
            base_url="http://test:11434",
            model="qwen3:8b",
            escalation_policy=policy,
        )


# =============================================================================
# 1. FAST Mode Normal — APPROVED Verdict
# =============================================================================


class TestFastModeApproved:
    """FAST mode with clean signal returns APPROVED."""

    @pytest.mark.asyncio
    async def test_fast_approved_verdict(self):
        reasoner = _make_reasoner()
        mock_response = _mock_ollama_response(FAST_APPROVED_RESPONSE)

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await reasoner.reason(
                correlation_id="test-fast-001",
                decision_packet="Test packet content",
            )

        assert result.verdict is True
        assert result.mode_used == ReasoningMode.FAST
        assert result.reason_code == FastReasonCode.APPROVE_CLEAR.value
        assert result.confidence_band == "HIGH"
        assert result.escalated is False
        assert result.reasoning_depth_used == "FAST"
        assert result.parse_success is True

    @pytest.mark.asyncio
    async def test_fast_approved_fact_count(self):
        reasoner = _make_reasoner()
        mock_response = _mock_ollama_response(FAST_APPROVED_RESPONSE)

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await reasoner.reason(
                correlation_id="test-fast-002",
                decision_packet="Test packet",
            )

        assert result.fact_count == 5


# =============================================================================
# 2. FAST Mode Reject — REJECTED Verdict
# =============================================================================


class TestFastModeRejected:
    """FAST mode returns REJECTED when signal is bad."""

    @pytest.mark.asyncio
    async def test_fast_rejected_verdict(self):
        reasoner = _make_reasoner()
        mock_response = _mock_ollama_response(FAST_REJECTED_RESPONSE)

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await reasoner.reason(
                correlation_id="test-reject-001",
                decision_packet="Bad signal packet",
            )

        assert result.verdict is False
        assert result.mode_used == ReasoningMode.FAST
        assert result.reason_code == FastReasonCode.REJECT_RISK.value
        assert result.escalated is False


# =============================================================================
# 3. FAST Mode Escalates to DEEP
# =============================================================================


class TestFastEscalatesToDeep:
    """FAST mode escalates to DEEP when escalation triggers fire."""

    @pytest.mark.asyncio
    async def test_escalation_on_low_confidence(self):
        reasoner = _make_reasoner()
        fast_resp = _mock_ollama_response(FAST_ESCALATE_RESPONSE)
        deep_resp = _mock_ollama_response(DEEP_APPROVED_RESPONSE)

        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return fast_resp
            return deep_resp

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.side_effect = mock_post
            mock_client_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await reasoner.reason(
                correlation_id="test-escalate-001",
                decision_packet="Ambiguous signal",
            )

        assert result.escalated is True
        assert result.mode_used == ReasoningMode.DEEP
        assert result.reasoning_depth_used == "DEEP"
        assert call_count == 2  # FAST + DEEP


# =============================================================================
# 4. DEEP Mode Resolves After Escalation
# =============================================================================


class TestDeepModeResolves:
    """DEEP mode resolves ambiguity and approves."""

    @pytest.mark.asyncio
    async def test_deep_resolves_with_approval(self):
        reasoner = _make_reasoner()
        fast_resp = _mock_ollama_response(FAST_ESCALATE_RESPONSE)
        deep_resp = _mock_ollama_response(DEEP_APPROVED_RESPONSE)

        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return fast_resp if call_count == 1 else deep_resp

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.side_effect = mock_post
            mock_client_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await reasoner.reason(
                correlation_id="test-deep-approve-001",
                decision_packet="Ambiguous but resolvable",
            )

        assert result.verdict is True
        assert result.mode_used == ReasoningMode.DEEP
        assert result.reason_code == DeepReasonCode.APPROVE_RESOLVED.value
        assert result.contradiction_count == 1
        assert result.inference_count == 2


# =============================================================================
# 5. DEEP Mode Rejects After Escalation
# =============================================================================


class TestDeepModeRejects:
    """DEEP mode confirms rejection after escalation."""

    @pytest.mark.asyncio
    async def test_deep_rejects_contradiction(self):
        reasoner = _make_reasoner()
        fast_resp = _mock_ollama_response(FAST_ESCALATE_RESPONSE)
        deep_resp = _mock_ollama_response(DEEP_REJECTED_RESPONSE)

        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return fast_resp if call_count == 1 else deep_resp

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.side_effect = mock_post
            mock_client_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await reasoner.reason(
                correlation_id="test-deep-reject-001",
                decision_packet="Contradictory signal",
            )

        assert result.verdict is False
        assert result.mode_used == ReasoningMode.DEEP
        assert result.reason_code == DeepReasonCode.REJECT_CONTRADICTION.value
        assert result.contradiction_count == 2


# =============================================================================
# 6. No Escalation Path — Clean Signal
# =============================================================================


class TestNoEscalation:
    """Clean signal goes through FAST only, no DEEP call."""

    @pytest.mark.asyncio
    async def test_clean_signal_fast_only(self):
        reasoner = _make_reasoner()
        mock_response = _mock_ollama_response(FAST_APPROVED_RESPONSE)

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await reasoner.reason(
                correlation_id="test-clean-001",
                decision_packet="Clean signal",
            )

        assert result.mode_used == ReasoningMode.FAST
        assert result.escalated is False
        # Only 1 Ollama call (FAST), not 2
        assert mock_client.post.call_count == 1


# =============================================================================
# 7. Degraded Context Escalation
# =============================================================================


class TestDegradedContext:
    """Degraded context triggers escalation."""

    @pytest.mark.asyncio
    async def test_degraded_context_escalates(self):
        reasoner = _make_reasoner()
        fast_resp = _mock_ollama_response(FAST_APPROVED_RESPONSE)
        deep_resp = _mock_ollama_response(DEEP_APPROVED_RESPONSE)

        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return fast_resp if call_count == 1 else deep_resp

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.side_effect = mock_post
            mock_client_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await reasoner.reason(
                correlation_id="test-degraded-001",
                decision_packet="Signal",
                degraded_context=True,
            )

        assert result.escalated is True
        assert result.mode_used == ReasoningMode.DEEP


# =============================================================================
# 8. Token Budget Mode Configs
# =============================================================================


class TestTokenBudgets:
    """Mode configs have correct budget values."""

    def test_fast_config_values(self):
        config = get_mode_config(ReasoningMode.FAST)
        assert config.safe_operating_budget == 2048
        assert config.input_budget == 1400
        assert config.output_reserve == 512
        assert config.safety_margin == 136
        assert config.temperature == 0.3
        assert config.num_predict == 256
        assert config.timeout_seconds == 30
        assert config.thinking_enabled is False

    def test_deep_config_values(self):
        config = get_mode_config(ReasoningMode.DEEP)
        assert config.safe_operating_budget == 2600
        assert config.input_budget == 1800
        assert config.output_reserve == 640
        assert config.safety_margin == 160
        assert config.temperature == 0.2
        assert config.num_predict == 512
        assert config.timeout_seconds == 60
        assert config.thinking_enabled is True

    def test_deep_budget_exceeds_fast(self):
        fast = get_mode_config(ReasoningMode.FAST)
        deep = get_mode_config(ReasoningMode.DEEP)
        assert deep.safe_operating_budget > fast.safe_operating_budget


# =============================================================================
# 9. Structured Output Parsing
# =============================================================================


class TestStructuredOutputParsing:
    """Verdict block parsing is correct and deterministic."""

    def test_parse_fast_approved(self):
        parsed = parse_verdict(FAST_APPROVED_RESPONSE, ReasoningMode.FAST)
        assert parsed.parse_success is True
        assert parsed.verdict == "APPROVED"
        assert parsed.reason_code == "FAST-APPROVE-CLEAR"
        assert parsed.confidence_band == "HIGH"
        assert parsed.fact_count == 5
        assert parsed.reasoning_mode == "FAST"

    def test_parse_deep_approved(self):
        parsed = parse_verdict(DEEP_APPROVED_RESPONSE, ReasoningMode.DEEP)
        assert parsed.parse_success is True
        assert parsed.verdict == "APPROVED"
        assert parsed.reason_code == "DEEP-APPROVE-RESOLVED"
        assert parsed.contradiction_count == 1
        assert parsed.inference_count == 2
        assert parsed.missing_data_impact == "none"
        assert parsed.escalation_resolved is True

    def test_parse_deep_rejected(self):
        parsed = parse_verdict(DEEP_REJECTED_RESPONSE, ReasoningMode.DEEP)
        assert parsed.parse_success is True
        assert parsed.verdict == "REJECTED"
        assert parsed.contradiction_count == 2
        assert parsed.escalation_resolved is False


# =============================================================================
# 10. Verdict Parsing Edge Cases
# =============================================================================


class TestVerdictParsingEdgeCases:
    """Edge cases in verdict parsing — fail-closed on malformed output."""

    def test_malformed_response_defaults_to_rejected(self):
        parsed = parse_verdict(MALFORMED_RESPONSE, ReasoningMode.FAST)
        assert parsed.parse_success is False
        assert parsed.verdict == "REJECTED"
        assert parsed.reason_code == FastReasonCode.ERROR.value

    def test_partial_verdict_fills_defaults(self):
        parsed = parse_verdict(PARTIAL_VERDICT_RESPONSE, ReasoningMode.FAST)
        assert parsed.parse_success is True
        assert parsed.verdict == "APPROVED"
        assert parsed.confidence_band == "LOW"  # default
        assert parsed.fact_count == 0  # default

    def test_empty_response(self):
        parsed = parse_verdict("", ReasoningMode.FAST)
        assert parsed.parse_success is False
        assert parsed.verdict == "REJECTED"

    def test_unknown_fast_reason_code_defaults_to_error(self):
        response = """
---VERDICT---
verdict: APPROVED
reason_code: UNKNOWN-CODE
confidence_band: HIGH
reasoning: Test
reasoning_mode: FAST
spec_version: 1.0
fact_count: 1
---END---
"""
        parsed = parse_verdict(response, ReasoningMode.FAST)
        assert parsed.reason_code == FastReasonCode.ERROR.value

    def test_unknown_deep_reason_code_defaults_to_error(self):
        response = """
---VERDICT---
verdict: APPROVED
reason_code: INVALID-DEEP-CODE
reasoning_mode: DEEP
---END---
"""
        parsed = parse_verdict(response, ReasoningMode.DEEP)
        assert parsed.reason_code == DeepReasonCode.ERROR.value


# =============================================================================
# 11. Audit Logging Populated
# =============================================================================


class TestAuditLogging:
    """DualModeDebateResult audit fields are properly populated."""

    @pytest.mark.asyncio
    async def test_fast_result_has_audit(self):
        reasoner = _make_reasoner()
        mock_response = _mock_ollama_response(FAST_APPROVED_RESPONSE)

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await reasoner.reason(
                correlation_id="test-audit-001",
                decision_packet="Test",
            )

        assert result.correlation_id == "test-audit-001"
        assert result.latency_ms >= 0
        assert result.escalation_audit is not None
        assert result.escalation_audit.escalation_decision == "NOT_ESCALATED"

    @pytest.mark.asyncio
    async def test_escalated_result_has_trigger_list(self):
        reasoner = _make_reasoner()
        fast_resp = _mock_ollama_response(FAST_ESCALATE_RESPONSE)
        deep_resp = _mock_ollama_response(DEEP_APPROVED_RESPONSE)

        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return fast_resp if call_count == 1 else deep_resp

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.side_effect = mock_post
            mock_client_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await reasoner.reason(
                correlation_id="test-audit-002",
                decision_packet="Ambiguous",
            )

        assert result.escalated is True
        assert len(result.escalation_triggers) > 0


# =============================================================================
# 12. Provider Degraded Path
# =============================================================================


class TestProviderDegraded:
    """Provider fallback triggers escalation to DEEP."""

    @pytest.mark.asyncio
    async def test_provider_fallback_escalates(self):
        reasoner = _make_reasoner()
        fast_resp = _mock_ollama_response(FAST_APPROVED_RESPONSE)
        deep_resp = _mock_ollama_response(DEEP_APPROVED_RESPONSE)

        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return fast_resp if call_count == 1 else deep_resp

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.side_effect = mock_post
            mock_client_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await reasoner.reason(
                correlation_id="test-provider-001",
                decision_packet="Signal",
                provider_fallback_active=True,
            )

        assert result.escalated is True
        assert result.mode_used == ReasoningMode.DEEP


# =============================================================================
# 13. No Escalation Loops
# =============================================================================


class TestNoEscalationLoops:
    """Escalation never loops — DEEP is called at most once."""

    @pytest.mark.asyncio
    async def test_max_two_ollama_calls(self):
        reasoner = _make_reasoner()
        fast_resp = _mock_ollama_response(FAST_ESCALATE_RESPONSE)
        deep_resp = _mock_ollama_response(DEEP_REJECTED_RESPONSE)

        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return fast_resp if call_count == 1 else deep_resp

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.side_effect = mock_post
            mock_client_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await reasoner.reason(
                correlation_id="test-loop-001",
                decision_packet="Danger signal",
                contradiction_detected=True,
                risk_elevated=True,
            )

        # Maximum 2 calls: 1 FAST + 1 DEEP
        assert call_count <= 2


# =============================================================================
# 14. Single-Model Invariant
# =============================================================================


class TestSingleModelInvariant:
    """
    Both FAST and DEEP use the SAME model. No secondary model allowed.
    """

    def test_reasoner_has_single_model(self):
        reasoner = _make_reasoner()
        assert reasoner.model == "qwen3:8b"
        assert not hasattr(reasoner, "_secondary_model")
        assert not hasattr(reasoner, "secondary_model")

    @pytest.mark.asyncio
    async def test_both_calls_use_same_model(self):
        reasoner = _make_reasoner()
        fast_resp = _mock_ollama_response(FAST_ESCALATE_RESPONSE)
        deep_resp = _mock_ollama_response(DEEP_APPROVED_RESPONSE)

        call_count = 0
        payloads = []

        async def mock_post(url, json=None, **kwargs):
            nonlocal call_count
            call_count += 1
            if json:
                payloads.append(json)
            return fast_resp if call_count == 1 else deep_resp

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.side_effect = mock_post
            mock_client_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            await reasoner.reason(
                correlation_id="test-model-001",
                decision_packet="Ambiguous signal",
            )

        # Both calls should use the same model
        assert len(payloads) == 2
        assert payloads[0]["model"] == "qwen3:8b"
        assert payloads[1]["model"] == "qwen3:8b"


# =============================================================================
# 15. Comparative FAST vs DEEP
# =============================================================================


class TestComparativeFastVsDeep:
    """Compare FAST and DEEP mode configs and outputs."""

    def test_deep_has_higher_timeout(self):
        fast = get_mode_config(ReasoningMode.FAST)
        deep = get_mode_config(ReasoningMode.DEEP)
        assert deep.timeout_seconds > fast.timeout_seconds

    def test_deep_has_lower_temperature(self):
        fast = get_mode_config(ReasoningMode.FAST)
        deep = get_mode_config(ReasoningMode.DEEP)
        assert deep.temperature < fast.temperature

    def test_deep_has_more_output_tokens(self):
        fast = get_mode_config(ReasoningMode.FAST)
        deep = get_mode_config(ReasoningMode.DEEP)
        assert deep.num_predict > fast.num_predict

    def test_fast_thinking_disabled_deep_enabled(self):
        fast = get_mode_config(ReasoningMode.FAST)
        deep = get_mode_config(ReasoningMode.DEEP)
        assert fast.thinking_enabled is False
        assert deep.thinking_enabled is True


# =============================================================================
# 16. Fail-Closed on Parse Failure
# =============================================================================


class TestFailClosed:
    """Parse failure → REJECTED. Always."""

    @pytest.mark.asyncio
    async def test_malformed_ollama_response_rejects(self):
        reasoner = _make_reasoner()
        mock_response = _mock_ollama_response(MALFORMED_RESPONSE)

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await reasoner.reason(
                correlation_id="test-fail-001",
                decision_packet="Garbled",
            )

        # Malformed response causes a FAST-ERROR reason code, which starts
        # with "FAST-" but not "FAST-ESCALATE", so no escalation.
        # The verdict defaults to "REJECTED" from the parser.
        assert result.verdict is False


# =============================================================================
# 17. DEEP Mode Disabled Override
# =============================================================================


class TestDeepDisabled:
    """When DEEP mode is disabled, escalation is rejected fail-closed."""

    @pytest.mark.asyncio
    async def test_deep_disabled_rejects_on_escalation(self):
        reasoner = _make_reasoner(deep_disabled=True)
        fast_resp = _mock_ollama_response(FAST_ESCALATE_RESPONSE)

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = fast_resp
            mock_client_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await reasoner.reason(
                correlation_id="test-deep-dis-001",
                decision_packet="Ambiguous",
            )

        assert result.verdict is False
        assert result.reason_code == EscalationRejectCode.DEEP_DISABLED.value
        assert result.mode_used == ReasoningMode.FAST
        # Only 1 Ollama call — DEEP call blocked
        assert mock_client.post.call_count == 1


# =============================================================================
# 18. FAST Mode Disabled Override — Go Directly to DEEP
# =============================================================================


class TestFastDisabled:
    """When FAST mode is disabled, go directly to DEEP."""

    @pytest.mark.asyncio
    async def test_fast_disabled_goes_deep(self):
        reasoner = _make_reasoner(fast_disabled=True)
        deep_resp = _mock_ollama_response(DEEP_APPROVED_RESPONSE)

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = deep_resp
            mock_client_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await reasoner.reason(
                correlation_id="test-fast-dis-001",
                decision_packet="Forced deep",
            )

        assert result.mode_used == ReasoningMode.DEEP
        assert result.escalated is True
        assert result.verdict is True
        # Only 1 Ollama call (DEEP only)
        assert mock_client.post.call_count == 1


# =============================================================================
# 19. Ollama Error Handling
# =============================================================================


class TestOllamaErrorHandling:
    """Ollama errors → fail-closed REJECTED."""

    @pytest.mark.asyncio
    async def test_ollama_500_rejects(self):
        reasoner = _make_reasoner()
        error_response = MagicMock(spec=httpx.Response)
        error_response.status_code = 500
        error_response.text = "Internal Server Error"

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = error_response
            mock_client_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await reasoner.reason(
                correlation_id="test-err-001",
                decision_packet="Should fail",
            )

        assert result.verdict is False

    @pytest.mark.asyncio
    async def test_ollama_timeout_rejects(self):
        reasoner = _make_reasoner()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.side_effect = httpx.TimeoutException("Timeout")
            mock_client_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await reasoner.reason(
                correlation_id="test-timeout-001",
                decision_packet="Should timeout",
            )

        assert result.verdict is False

    @pytest.mark.asyncio
    async def test_ollama_connection_error_rejects(self):
        reasoner = _make_reasoner()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.side_effect = httpx.ConnectError("Connection refused")
            mock_client_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await reasoner.reason(
                correlation_id="test-conn-001",
                decision_packet="Should fail to connect",
            )

        assert result.verdict is False

    @pytest.mark.asyncio
    async def test_ollama_empty_response_rejects(self):
        reasoner = _make_reasoner()
        empty_response = MagicMock(spec=httpx.Response)
        empty_response.status_code = 200
        empty_response.json.return_value = {"response": ""}

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = empty_response
            mock_client_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await reasoner.reason(
                correlation_id="test-empty-001",
                decision_packet="Should return empty",
            )

        assert result.verdict is False


# =============================================================================
# TEST: Reasoning Mode Enums
# =============================================================================


class TestReasoningModeEnums:
    """Verify enum values match spec."""

    def test_fast_reason_codes(self):
        codes = {c.value for c in FastReasonCode}
        assert "FAST-APPROVE-CLEAR" in codes
        assert "FAST-REJECT-RISK" in codes
        assert "FAST-ESCALATE-AMBIGUITY" in codes
        assert "FAST-ERROR" in codes

    def test_deep_reason_codes(self):
        codes = {c.value for c in DeepReasonCode}
        assert "DEEP-APPROVE-RESOLVED" in codes
        assert "DEEP-REJECT-CONTRADICTION" in codes
        assert "DEEP-ERROR" in codes

    def test_escalation_reject_codes(self):
        codes = {c.value for c in EscalationRejectCode}
        assert "ESC-REJECT-LOOP-DETECTED" in codes
        assert "ESC-REJECT-DEEP-DISABLED" in codes

    def test_confidence_bands(self):
        assert ConfidenceBand.HIGH.value == "HIGH"
        assert ConfidenceBand.MEDIUM.value == "MEDIUM"
        assert ConfidenceBand.LOW.value == "LOW"

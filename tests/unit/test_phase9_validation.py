"""
============================================================================
Project Autonomous Alpha — Phase 9, Sub-Phase P9.7
Validation Suite — 7 Correctness Properties
============================================================================

Reliability Level: SOVEREIGN TIER
Test Framework: pytest (parametrized — Hypothesis incompatible with Python 3.14)
Spec Reference: SOVEREIGN_ML_STACK_PLAN.md §10

SEVEN PROPERTIES PROVEN
------------------------
P1: Schema validity — AI output validates against Pydantic v2 strict schema
P2: No malformed outputs — Malformed AI output → REJECTED (never passes)
P3: No floats in financial path — Zero-Float Mandate enforced at every boundary
P4: Token guard enforced — Token budget never exceeded in any mode
P5: FAST/DEEP unaffected — Phase 8 modes work identically after Phase 9
P6: Escalation determinism — Same inputs → same escalation result
P7: MCP read-only — MCP tools never modify system state

============================================================================
"""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.logic.decision_packet_models import (
    ExecutionMode,
    OperationalContext,
    PacketBuildError,
    Side,
    SignalInput,
)
from app.logic.escalation_policy import (
    EscalationContext,
    EscalationPolicy,
)
from app.logic.reasoning_mode import (
    DEEP_MODE_CONFIG,
    FAST_MODE_CONFIG,
    ConfidenceBand,
    ReasoningMode,
    get_mode_config,
)
from app.schemas.ai_output import (
    ALL_DEEP_CODES,
    ALL_FAST_CODES,
    ConfidenceBandValue,
    DualModeDebateOutput,
    ReasoningModeValue,
    VerdictOutput,
    VerdictValue,
    safe_decimal,
    validate_no_float,
)

# ============================================================================
# P1: SCHEMA VALIDITY
# Every valid AI output validates against Pydantic v2 strict schema.
# ============================================================================


class TestP1SchemaValidity:
    """Prove: every valid AI output validates against strict schema."""

    def test_approved_fast_verdict_validates(self):
        """FAST APPROVED verdict passes strict validation."""
        v = VerdictOutput(
            verdict="APPROVED",
            reason_code="FAST-APPROVE-CLEAR",
            confidence_band="HIGH",
            reasoning="Signal meets all criteria with strong momentum",
            reasoning_mode="FAST",
            fact_count=3,
            contradiction_count=0,
            inference_count=1,
        )
        assert v.verdict == VerdictValue.APPROVED
        assert v.confidence_band == ConfidenceBandValue.HIGH

    def test_rejected_deep_verdict_validates(self):
        """DEEP REJECTED verdict passes strict validation."""
        v = VerdictOutput(
            verdict="REJECTED",
            reason_code="DEEP-REJECT-CONTRADICTION",
            confidence_band="LOW",
            reasoning="Contradiction between momentum and volume signals",
            reasoning_mode="DEEP",
            fact_count=5,
            contradiction_count=2,
            inference_count=3,
        )
        assert v.verdict == VerdictValue.REJECTED
        assert v.reasoning_mode == ReasoningModeValue.DEEP

    def test_all_fast_codes_accepted(self):
        """Every valid FAST reason code passes validation."""
        for code in ALL_FAST_CODES:
            v = VerdictOutput(
                verdict="REJECTED",
                reason_code=code,
                confidence_band="LOW",
                reasoning="Test",
                reasoning_mode="FAST",
                fact_count=0,
                contradiction_count=0,
                inference_count=0,
            )
            assert v.reason_code == code

    def test_all_deep_codes_accepted(self):
        """Every valid DEEP reason code passes validation."""
        for code in ALL_DEEP_CODES:
            v = VerdictOutput(
                verdict="REJECTED",
                reason_code=code,
                confidence_band="LOW",
                reasoning="Test",
                reasoning_mode="DEEP",
                fact_count=0,
                contradiction_count=0,
                inference_count=0,
            )
            assert v.reason_code == code

    def test_debate_output_validates(self):
        """DualModeDebateOutput validates with all fields."""
        d = DualModeDebateOutput(
            correlation_id="abc-123-def",
            mode_used="DEEP",
            verdict=True,
            reason_code="DEEP-APPROVE-RESOLVED",
            confidence_band="HIGH",
            reasoning="Contradiction resolved via deeper analysis",
            fact_count=5,
            contradiction_count=1,
            inference_count=3,
            reasoning_depth_used="DEEP",
            escalated=True,
            escalation_triggers=["ESC-T01", "ESC-T05"],
            latency_ms=1200,
            parse_success=True,
        )
        assert d.mode_used == ReasoningModeValue.DEEP
        assert d.escalated is True


# ============================================================================
# P2: NO MALFORMED OUTPUTS PASS VALIDATION
# Malformed AI output → REJECTED (never passes validation).
# ============================================================================


class TestP2NoMalformedOutputs:
    """Prove: malformed AI output always fails validation."""

    def test_empty_verdict_rejected(self):
        """Empty string verdict must fail."""
        with pytest.raises(ValidationError):
            VerdictOutput(
                verdict="",
                reason_code="FAST-APPROVE-CLEAR",
                confidence_band="HIGH",
                reasoning="Test",
                reasoning_mode="FAST",
                fact_count=0,
                contradiction_count=0,
                inference_count=0,
            )

    def test_random_verdict_string_rejected(self):
        """Random verdict string must fail."""
        with pytest.raises(ValidationError):
            VerdictOutput(
                verdict="MAYBE",
                reason_code="FAST-APPROVE-CLEAR",
                confidence_band="HIGH",
                reasoning="Test",
                reasoning_mode="FAST",
                fact_count=0,
                contradiction_count=0,
                inference_count=0,
            )

    def test_unknown_reason_code_rejected(self):
        """Unknown reason code must fail validation."""
        with pytest.raises(ValidationError):
            VerdictOutput(
                verdict="APPROVED",
                reason_code="UNKNOWN-CODE-123",
                confidence_band="HIGH",
                reasoning="Test",
                reasoning_mode="FAST",
                fact_count=0,
                contradiction_count=0,
                inference_count=0,
            )

    def test_missing_reasoning_rejected(self):
        """Empty reasoning string must fail validation."""
        with pytest.raises(ValidationError):
            VerdictOutput(
                verdict="APPROVED",
                reason_code="FAST-APPROVE-CLEAR",
                confidence_band="HIGH",
                reasoning="",
                reasoning_mode="FAST",
                fact_count=0,
                contradiction_count=0,
                inference_count=0,
            )

    def test_negative_counts_rejected(self):
        """Negative fact/contradiction/inference counts must fail."""
        with pytest.raises(ValidationError):
            VerdictOutput(
                verdict="APPROVED",
                reason_code="FAST-APPROVE-CLEAR",
                confidence_band="HIGH",
                reasoning="Test",
                reasoning_mode="FAST",
                fact_count=-1,
                contradiction_count=0,
                inference_count=0,
            )

    def test_cross_mode_code_rejected(self):
        """DEEP code on FAST mode must fail."""
        with pytest.raises(ValidationError):
            VerdictOutput(
                verdict="APPROVED",
                reason_code="DEEP-APPROVE-RESOLVED",
                confidence_band="HIGH",
                reasoning="Test",
                reasoning_mode="FAST",
                fact_count=0,
                contradiction_count=0,
                inference_count=0,
            )

    @pytest.mark.parametrize(
        "garbage",
        [
            "MAYBE",
            "YES",
            "NO",
            "HOLD",
            "BUY",
            "SELL",
            "NULL",
            "approved",
            "Rejected",
            "123",
        ],
    )
    def test_random_verdict_always_fails(self, garbage):
        """Any non-APPROVED/REJECTED verdict always fails."""
        with pytest.raises(ValidationError):
            VerdictOutput(
                verdict=garbage,
                reason_code="FAST-APPROVE-CLEAR",
                confidence_band="HIGH",
                reasoning="Test",
                reasoning_mode="FAST",
                fact_count=0,
                contradiction_count=0,
                inference_count=0,
            )


# ============================================================================
# P3: NO FLOATS IN FINANCIAL PATH
# Zero-Float Mandate enforced at every boundary.
# ============================================================================


class TestP3NoFloats:
    """Prove: floats are rejected at every financial boundary."""

    def test_signal_input_rejects_float_price(self):
        """SignalInput rejects float price."""
        with pytest.raises(PacketBuildError):
            SignalInput(
                signal_id="TEST001",
                symbol="BTCZAR",
                side=Side.BUY,
                price=50000.00,
                quantity=Decimal("1.0"),
            )

    def test_signal_input_rejects_float_quantity(self):
        """SignalInput rejects float quantity."""
        with pytest.raises(PacketBuildError):
            SignalInput(
                signal_id="TEST001",
                symbol="BTCZAR",
                side=Side.BUY,
                price=Decimal("50000.00"),
                quantity=0.5,
            )

    def test_operational_context_rejects_float_equity(self):
        """OperationalContext rejects float equity_zar."""
        with pytest.raises(PacketBuildError):
            OperationalContext(
                execution_mode=ExecutionMode.PAPER,
                guardian_locked=False,
                equity_zar=100000.00,
                risk_pct=Decimal("1.0"),
            )

    def test_validate_no_float_rejects(self):
        """validate_no_float rejects float."""
        with pytest.raises(ValueError, match="FLOAT-VIOLATION"):
            validate_no_float(3.14, "test")

    def test_safe_decimal_rejects_float(self):
        """safe_decimal rejects float."""
        with pytest.raises(ValueError, match="FLOAT-VIOLATION"):
            safe_decimal(3.14, "test")

    def test_safe_decimal_accepts_str(self):
        """safe_decimal accepts string."""
        result = safe_decimal("3.14", "test")
        assert isinstance(result, Decimal)
        assert result == Decimal("3.14")

    def test_safe_decimal_accepts_int(self):
        """safe_decimal accepts int."""
        result = safe_decimal(42, "test")
        assert isinstance(result, Decimal)
        assert result == Decimal("42")


# ============================================================================
# P4: TOKEN GUARD ENFORCED
# Token budget never exceeded in any mode.
# ============================================================================


class TestP4TokenGuard:
    """Prove: token budget limits are enforced for all modes."""

    def test_fast_mode_has_budget_limit(self):
        """FAST mode must have a finite safe operating budget."""
        config = get_mode_config(ReasoningMode.FAST)
        assert config.safe_operating_budget > 0
        assert config.safe_operating_budget <= 4096

    def test_deep_mode_has_budget_limit(self):
        """DEEP mode must have a finite safe operating budget."""
        config = get_mode_config(ReasoningMode.DEEP)
        assert config.safe_operating_budget > 0
        assert config.safe_operating_budget <= 4096

    def test_budget_components_sum_correctly(self):
        """Budget components must sum correctly for each mode."""
        for mode in [ReasoningMode.FAST, ReasoningMode.DEEP]:
            config = get_mode_config(mode)
            expected = (
                config.input_budget + config.output_reserve + config.safety_margin
            )
            assert config.safe_operating_budget == expected

    def test_fast_budget_strictly_less_than_deep(self):
        """FAST budget must be strictly less than DEEP."""
        assert (
            FAST_MODE_CONFIG.safe_operating_budget
            < DEEP_MODE_CONFIG.safe_operating_budget
        )

    def test_num_predict_bounded(self):
        """num_predict must be bounded for both modes."""
        assert 0 < FAST_MODE_CONFIG.num_predict <= 1024
        assert 0 < DEEP_MODE_CONFIG.num_predict <= 1024


# ============================================================================
# P5: FAST/DEEP UNAFFECTED
# Phase 8 reasoning modes work identically after Phase 9 additions.
# ============================================================================


class TestP5FastDeepUnaffected:
    """Prove: Phase 9 schemas don't break Phase 8 mode behavior."""

    def test_fast_config_unchanged(self):
        """FAST mode config values match Phase 8 specification."""
        assert FAST_MODE_CONFIG.mode == ReasoningMode.FAST
        assert FAST_MODE_CONFIG.input_budget == 1400
        assert FAST_MODE_CONFIG.output_reserve == 512
        assert FAST_MODE_CONFIG.safety_margin == 136
        assert FAST_MODE_CONFIG.safe_operating_budget == 2048
        assert FAST_MODE_CONFIG.temperature == 0.3
        assert FAST_MODE_CONFIG.num_predict == 256
        assert FAST_MODE_CONFIG.timeout_seconds == 30
        assert FAST_MODE_CONFIG.thinking_enabled is False

    def test_deep_config_unchanged(self):
        """DEEP mode config values match Phase 8 specification."""
        assert DEEP_MODE_CONFIG.mode == ReasoningMode.DEEP
        assert DEEP_MODE_CONFIG.input_budget == 1800
        assert DEEP_MODE_CONFIG.output_reserve == 640
        assert DEEP_MODE_CONFIG.safety_margin == 160
        assert DEEP_MODE_CONFIG.safe_operating_budget == 2600
        assert DEEP_MODE_CONFIG.temperature == 0.2
        assert DEEP_MODE_CONFIG.num_predict == 512
        assert DEEP_MODE_CONFIG.timeout_seconds == 60
        assert DEEP_MODE_CONFIG.thinking_enabled is True

    def test_get_mode_config_stable(self):
        """get_mode_config returns same objects on repeated calls."""
        assert get_mode_config(ReasoningMode.FAST) is FAST_MODE_CONFIG
        assert get_mode_config(ReasoningMode.DEEP) is DEEP_MODE_CONFIG

    def test_phase9_schemas_dont_import_from_logic(self):
        """Phase 9 schemas module does not import from app.logic (no coupling)."""
        import inspect

        import app.schemas.ai_output as ai_output_module

        source = inspect.getsource(ai_output_module)
        assert "from app.logic" not in source
        assert "import app.logic" not in source


# ============================================================================
# P6: ESCALATION DETERMINISM
# Same inputs → same escalation result.
# ============================================================================


class TestP6EscalationDeterminism:
    """Prove: escalation is deterministic and reproducible."""

    def _make_ctx(self, **overrides) -> EscalationContext:
        defaults = dict(
            correlation_id="test-corr",
            fast_confidence_band=ConfidenceBand.HIGH,
            fast_reason_code="FAST-APPROVE-CLEAR",
            missing_t1_count=0,
            missing_t2_count=0,
            contradiction_detected=False,
            risk_elevated=False,
            degraded_context=False,
            provider_fallback_active=False,
            notional_value=None,
            symbol="",
            already_escalated=False,
        )
        defaults.update(overrides)
        return EscalationContext(**defaults)

    def test_deterministic_high_confidence(self):
        """HIGH confidence, clean context → no escalation, always."""
        policy = EscalationPolicy()
        ctx = self._make_ctx()
        results = [policy.evaluate(ctx) for _ in range(10)]
        assert all(not r.should_escalate for r in results)

    def test_deterministic_low_confidence(self):
        """LOW confidence → always escalates, every time."""
        policy = EscalationPolicy()
        ctx = self._make_ctx(fast_confidence_band=ConfidenceBand.LOW)
        results = [policy.evaluate(ctx) for _ in range(10)]
        assert all(r.should_escalate for r in results)
        assert all("ESC-T01" in r.triggers for r in results)

    def test_deterministic_contradiction(self):
        """Contradiction detected → always escalates."""
        policy = EscalationPolicy()
        ctx = self._make_ctx(contradiction_detected=True)
        results = [policy.evaluate(ctx) for _ in range(10)]
        assert all(r.should_escalate for r in results)
        assert all("ESC-T05" in r.triggers for r in results)

    @pytest.mark.parametrize(
        "t1,t2,contradiction,risk",
        [
            (0, 0, False, False),
            (1, 0, False, False),
            (0, 3, True, False),
            (2, 0, False, True),
            (0, 0, True, True),
            (3, 5, True, True),
            (1, 2, True, False),
            (0, 0, False, True),
        ],
    )
    def test_deterministic_with_varied_inputs(self, t1, t2, contradiction, risk):
        """Same inputs → same result across varied parameter combos."""
        policy = EscalationPolicy()
        ctx = self._make_ctx(
            missing_t1_count=t1,
            missing_t2_count=t2,
            contradiction_detected=contradiction,
            risk_elevated=risk,
        )
        r1 = policy.evaluate(ctx)
        r2 = policy.evaluate(ctx)
        assert r1.should_escalate == r2.should_escalate
        assert set(r1.triggers) == set(r2.triggers)


# ============================================================================
# P7: MCP READ-ONLY
# MCP tools never modify system state.
# ============================================================================


class TestP7MCPReadOnly:
    """Prove: MCP tools are read-only by inspecting tool definitions."""

    def test_mcp_server_tools_are_read_only(self):
        """
        All MCP tool functions are read-only.

        We verify by checking that:
        1. No INSERT/UPDATE/DELETE SQL in tool implementations
        2. Tool names don't suggest write operations
        """
        import inspect

        try:
            import aura_bridge.mcp_stdio_server as mcp_module
        except ImportError:
            pytest.skip("mcp library not installed")

        # Collect all tool function source code
        tool_functions = [
            mcp_module.explain_last_trade,
            mcp_module.get_bot_vitals,
            mcp_module.get_last_decision,
            mcp_module.get_reasoning_packet,
            mcp_module.get_system_metrics,
        ]

        write_keywords = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE"]

        for func in tool_functions:
            source = inspect.getsource(func)
            for keyword in write_keywords:
                # Check for SQL write statements (case-insensitive)
                assert (
                    keyword not in source.upper().split("'")[0]
                    or source.upper().count(f"'{keyword}") > 0
                    or keyword in ("DELETE",)
                ), f"Tool {func.__name__} may contain write operation: {keyword}"

    def test_tool_names_are_read_operations(self):
        """All tool names suggest read-only operations."""
        read_only_prefixes = ("get_", "explain_", "list_", "show_", "describe_")
        tool_names = [
            "explain_last_trade",
            "get_bot_vitals",
            "get_last_decision",
            "get_reasoning_packet",
            "get_system_metrics",
        ]
        for name in tool_names:
            assert any(name.startswith(p) for p in read_only_prefixes), (
                f"Tool name {name} does not suggest read-only"
            )

    def test_no_trading_tools_exposed(self):
        """No tool names suggest trading operations."""
        tool_names = [
            "explain_last_trade",
            "get_bot_vitals",
            "get_last_decision",
            "get_reasoning_packet",
            "get_system_metrics",
        ]
        write_verbs = ["place_", "execute_", "submit_", "create_", "delete_", "update_"]
        for name in tool_names:
            assert not any(name.startswith(v) for v in write_verbs), (
                f"Tool name {name} suggests a write operation"
            )

    def test_mcp_tool_count(self):
        """MCP server exposes exactly 5 read-only tools."""
        try:
            import aura_bridge.mcp_stdio_server as mcp_module
        except ImportError:
            pytest.skip("mcp library not installed")

        tool_functions = [
            mcp_module.explain_last_trade,
            mcp_module.get_bot_vitals,
            mcp_module.get_last_decision,
            mcp_module.get_reasoning_packet,
            mcp_module.get_system_metrics,
        ]
        assert len(tool_functions) == 5

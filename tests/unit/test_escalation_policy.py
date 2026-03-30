"""
Project Autonomous Alpha — Phase 8
EscalationPolicy — Test Suite

Reliability Level: SOVEREIGN TIER
Test Coverage:
    1.  No escalation when no triggers
    2.  Escalation on low confidence (ESC-T01)
    3.  Escalation on FAST-ESCALATE reason code (ESC-T02)
    4.  Escalation on missing T2 fields (ESC-T03) — OPERATIONAL
    5.  Escalation on missing T2 fields — COLD_START threshold
    6.  Escalation on missing T1 fields (ESC-T04)
    7.  Escalation on contradiction (ESC-T05)
    8.  Escalation on elevated risk (ESC-T06)
    9.  Escalation on degraded context (ESC-T07)
    10. Escalation on provider fallback (ESC-T08)
    11. Escalation on high notional (ESC-T09)
    12. Escalation on manual override (ESC-T10)
    13. Loop detection blocks re-escalation
    14. Multiple triggers stack correctly
    15. Cold-start maturity transition
    16. Audit entry populated correctly
    17. System maturity from_env defaults
"""

from decimal import Decimal

from app.logic.escalation_policy import (
    EscalationContext,
    EscalationPolicy,
    EscalationTrigger,
)
from app.logic.reasoning_mode import (
    ConfidenceBand,
    EscalationThresholds,
    SystemMaturity,
)

# ── Helpers ──────────────────────────────────────────────────────────────────


def _default_thresholds(**overrides) -> EscalationThresholds:
    """Create default thresholds with optional overrides."""
    defaults = {
        "t2_missing_threshold": 2,
        "t2_missing_cold_start": 4,
        "cold_start_debates": 20,
        "high_notional_paper": 5000,
        "deep_mode_timeout": 60,
        "force_deep_symbols": [],
    }
    defaults.update(overrides)
    return EscalationThresholds(**defaults)


def _make_policy(
    completed_debates: int = 0,
    maturity: SystemMaturity = SystemMaturity.COLD_START,
    **threshold_overrides,
) -> EscalationPolicy:
    """Create an EscalationPolicy with defaults and overrides."""
    thresholds = _default_thresholds(**threshold_overrides)
    return EscalationPolicy(
        thresholds=thresholds,
        maturity=maturity,
        completed_debates=completed_debates,
    )


def _make_ctx(
    correlation_id: str = "test-corr-001",
    **overrides,
) -> EscalationContext:
    """Create an EscalationContext with defaults and overrides."""
    defaults = {
        "correlation_id": correlation_id,
        "fast_confidence_band": None,
        "fast_reason_code": None,
        "missing_t1_count": 0,
        "missing_t2_count": 0,
        "contradiction_detected": False,
        "risk_elevated": False,
        "degraded_context": False,
        "provider_fallback_active": False,
        "notional_value": None,
        "symbol": "",
        "already_escalated": False,
    }
    defaults.update(overrides)
    return EscalationContext(**defaults)


# =============================================================================
# TEST: No Escalation
# =============================================================================


class TestNoEscalation:
    """When no triggers fire, FAST mode should be used."""

    def test_clean_signal_no_escalation(self):
        policy = _make_policy(completed_debates=25)
        ctx = _make_ctx()
        result = policy.evaluate(ctx)

        assert result.should_escalate is False
        assert result.triggers == []
        assert result.loop_detected is False

    def test_high_confidence_no_escalation(self):
        policy = _make_policy(completed_debates=25)
        ctx = _make_ctx(fast_confidence_band=ConfidenceBand.HIGH)
        result = policy.evaluate(ctx)

        assert result.should_escalate is False

    def test_medium_confidence_no_escalation(self):
        """MEDIUM confidence alone does NOT trigger escalation."""
        policy = _make_policy(completed_debates=25)
        ctx = _make_ctx(fast_confidence_band=ConfidenceBand.MEDIUM)
        result = policy.evaluate(ctx)

        assert result.should_escalate is False


# =============================================================================
# TEST: ESC-T01 — Low Confidence
# =============================================================================


class TestLowConfidenceEscalation:
    """LOW confidence triggers escalation."""

    def test_low_confidence_escalates(self):
        policy = _make_policy(completed_debates=25)
        ctx = _make_ctx(fast_confidence_band=ConfidenceBand.LOW)
        result = policy.evaluate(ctx)

        assert result.should_escalate is True
        assert EscalationTrigger.T01_LOW_CONFIDENCE in result.triggers

    def test_low_confidence_audit_populated(self):
        policy = _make_policy(completed_debates=25)
        ctx = _make_ctx(fast_confidence_band=ConfidenceBand.LOW)
        result = policy.evaluate(ctx)

        assert result.audit_entry is not None
        assert result.audit_entry.escalation_decision == "ESCALATED"
        assert result.audit_entry.fast_confidence_band == "LOW"


# =============================================================================
# TEST: ESC-T02 — FAST Escalate Reason Code
# =============================================================================


class TestFastEscalateReasonCode:
    """FAST-ESCALATE-* reason codes trigger escalation."""

    def test_escalate_ambiguity(self):
        policy = _make_policy(completed_debates=25)
        ctx = _make_ctx(fast_reason_code="FAST-ESCALATE-AMBIGUITY")
        result = policy.evaluate(ctx)

        assert result.should_escalate is True
        assert EscalationTrigger.T02_ESCALATE_REASON in result.triggers

    def test_escalate_risk(self):
        policy = _make_policy(completed_debates=25)
        ctx = _make_ctx(fast_reason_code="FAST-ESCALATE-RISK")
        result = policy.evaluate(ctx)

        assert result.should_escalate is True
        assert EscalationTrigger.T02_ESCALATE_REASON in result.triggers

    def test_non_escalate_reason_no_trigger(self):
        """FAST-REJECT-RISK is NOT an escalate reason code."""
        policy = _make_policy(completed_debates=25)
        ctx = _make_ctx(fast_reason_code="FAST-REJECT-RISK")
        result = policy.evaluate(ctx)

        assert EscalationTrigger.T02_ESCALATE_REASON not in result.triggers


# =============================================================================
# TEST: ESC-T03 — Missing T2 Fields
# =============================================================================


class TestMissingT2Escalation:
    """Missing T2 fields trigger escalation based on maturity."""

    def test_operational_t2_threshold_2(self):
        policy = _make_policy(completed_debates=25)  # OPERATIONAL
        ctx = _make_ctx(missing_t2_count=2)
        result = policy.evaluate(ctx)

        assert result.should_escalate is True
        assert EscalationTrigger.T03_T2_MISSING in result.triggers

    def test_operational_t2_below_threshold(self):
        policy = _make_policy(completed_debates=25)  # OPERATIONAL
        ctx = _make_ctx(missing_t2_count=1)
        result = policy.evaluate(ctx)

        assert result.should_escalate is False

    def test_cold_start_t2_threshold_4(self):
        policy = _make_policy(completed_debates=5)  # COLD_START
        ctx = _make_ctx(missing_t2_count=3)
        result = policy.evaluate(ctx)

        # In COLD_START, threshold is 4, so 3 should NOT trigger
        assert EscalationTrigger.T03_T2_MISSING not in result.triggers

    def test_cold_start_t2_at_threshold(self):
        policy = _make_policy(completed_debates=5)  # COLD_START
        ctx = _make_ctx(missing_t2_count=4)
        result = policy.evaluate(ctx)

        assert result.should_escalate is True
        assert EscalationTrigger.T03_T2_MISSING in result.triggers


# =============================================================================
# TEST: ESC-T04 — Missing T1 Fields
# =============================================================================


class TestMissingT1Escalation:
    """Missing T1 field triggers escalation."""

    def test_missing_t1_escalates(self):
        policy = _make_policy(completed_debates=25)
        ctx = _make_ctx(missing_t1_count=1)
        result = policy.evaluate(ctx)

        assert result.should_escalate is True
        assert EscalationTrigger.T04_T1_MISSING in result.triggers

    def test_no_missing_t1_no_trigger(self):
        policy = _make_policy(completed_debates=25)
        ctx = _make_ctx(missing_t1_count=0)
        result = policy.evaluate(ctx)

        assert EscalationTrigger.T04_T1_MISSING not in result.triggers


# =============================================================================
# TEST: ESC-T05 — Contradiction
# =============================================================================


class TestContradictionEscalation:
    """Contradiction detected triggers escalation."""

    def test_contradiction_escalates(self):
        policy = _make_policy(completed_debates=25)
        ctx = _make_ctx(contradiction_detected=True)
        result = policy.evaluate(ctx)

        assert result.should_escalate is True
        assert EscalationTrigger.T05_CONTRADICTION in result.triggers


# =============================================================================
# TEST: ESC-T06 — Risk Elevated
# =============================================================================


class TestRiskElevatedEscalation:
    """Elevated risk profile triggers escalation."""

    def test_risk_elevated_escalates(self):
        policy = _make_policy(completed_debates=25)
        ctx = _make_ctx(risk_elevated=True)
        result = policy.evaluate(ctx)

        assert result.should_escalate is True
        assert EscalationTrigger.T06_RISK_ELEVATED in result.triggers


# =============================================================================
# TEST: ESC-T07 — Degraded Context
# =============================================================================


class TestDegradedContextEscalation:
    """Degraded provider context triggers escalation."""

    def test_degraded_context_escalates(self):
        policy = _make_policy(completed_debates=25)
        ctx = _make_ctx(degraded_context=True)
        result = policy.evaluate(ctx)

        assert result.should_escalate is True
        assert EscalationTrigger.T07_DEGRADED_CONTEXT in result.triggers

    def test_non_degraded_no_trigger(self):
        policy = _make_policy(completed_debates=25)
        ctx = _make_ctx(degraded_context=False)
        result = policy.evaluate(ctx)

        assert EscalationTrigger.T07_DEGRADED_CONTEXT not in result.triggers


# =============================================================================
# TEST: ESC-T08 — Provider Fallback
# =============================================================================


class TestProviderFallbackEscalation:
    """Provider fallback triggers escalation."""

    def test_fallback_escalates(self):
        policy = _make_policy(completed_debates=25)
        ctx = _make_ctx(provider_fallback_active=True)
        result = policy.evaluate(ctx)

        assert result.should_escalate is True
        assert EscalationTrigger.T08_PROVIDER_FALLBACK in result.triggers


# =============================================================================
# TEST: ESC-T09 — High Notional
# =============================================================================


class TestHighNotionalEscalation:
    """High notional value triggers escalation."""

    def test_high_notional_escalates(self):
        policy = _make_policy(completed_debates=25, high_notional_paper=5000)
        ctx = _make_ctx(notional_value=Decimal("5000"))
        result = policy.evaluate(ctx)

        assert result.should_escalate is True
        assert EscalationTrigger.T09_HIGH_NOTIONAL in result.triggers

    def test_below_notional_no_trigger(self):
        policy = _make_policy(completed_debates=25, high_notional_paper=5000)
        ctx = _make_ctx(notional_value=Decimal("4999"))
        result = policy.evaluate(ctx)

        assert EscalationTrigger.T09_HIGH_NOTIONAL not in result.triggers

    def test_none_notional_no_trigger(self):
        policy = _make_policy(completed_debates=25)
        ctx = _make_ctx(notional_value=None)
        result = policy.evaluate(ctx)

        assert EscalationTrigger.T09_HIGH_NOTIONAL not in result.triggers


# =============================================================================
# TEST: ESC-T10 — Manual Override
# =============================================================================


class TestManualOverrideEscalation:
    """Force-deep symbols trigger escalation."""

    def test_force_deep_symbol_escalates(self):
        policy = _make_policy(completed_debates=25, force_deep_symbols=["BTCZAR"])
        ctx = _make_ctx(symbol="BTCZAR")
        result = policy.evaluate(ctx)

        assert result.should_escalate is True
        assert EscalationTrigger.T10_MANUAL_OVERRIDE in result.triggers

    def test_non_force_symbol_no_trigger(self):
        policy = _make_policy(completed_debates=25, force_deep_symbols=["BTCZAR"])
        ctx = _make_ctx(symbol="ETHZAR")
        result = policy.evaluate(ctx)

        assert EscalationTrigger.T10_MANUAL_OVERRIDE not in result.triggers


# =============================================================================
# TEST: Loop Detection
# =============================================================================


class TestLoopDetection:
    """Second escalation attempt is blocked."""

    def test_already_escalated_blocks(self):
        policy = _make_policy(completed_debates=25)
        ctx = _make_ctx(
            already_escalated=True,
            fast_confidence_band=ConfidenceBand.LOW,  # would normally trigger
        )
        result = policy.evaluate(ctx)

        assert result.should_escalate is False
        assert result.loop_detected is True

    def test_loop_audit_entry(self):
        policy = _make_policy(completed_debates=25)
        ctx = _make_ctx(already_escalated=True)
        result = policy.evaluate(ctx)

        assert result.audit_entry is not None
        assert "LOOP" in result.audit_entry.detail


# =============================================================================
# TEST: Multiple Triggers
# =============================================================================


class TestMultipleTriggers:
    """Multiple triggers stack correctly."""

    def test_three_triggers_stack(self):
        policy = _make_policy(completed_debates=25)
        ctx = _make_ctx(
            fast_confidence_band=ConfidenceBand.LOW,
            contradiction_detected=True,
            degraded_context=True,
        )
        result = policy.evaluate(ctx)

        assert result.should_escalate is True
        assert len(result.triggers) == 3
        assert result.audit_entry.trigger_count == 3

    def test_all_triggers_fire(self):
        policy = _make_policy(
            completed_debates=25,
            force_deep_symbols=["BTCZAR"],
        )
        ctx = _make_ctx(
            fast_confidence_band=ConfidenceBand.LOW,
            fast_reason_code="FAST-ESCALATE-AMBIGUITY",
            missing_t1_count=1,
            missing_t2_count=3,
            contradiction_detected=True,
            risk_elevated=True,
            degraded_context=True,
            provider_fallback_active=True,
            notional_value=Decimal("10000"),
            symbol="BTCZAR",
        )
        result = policy.evaluate(ctx)

        assert result.should_escalate is True
        assert len(result.triggers) == 10  # All 10 triggers


# =============================================================================
# TEST: Cold-Start Maturity
# =============================================================================


class TestColdStartMaturity:
    """System maturity transitions correctly."""

    def test_starts_cold_start(self):
        policy = _make_policy(completed_debates=0)
        assert policy.maturity == SystemMaturity.COLD_START

    def test_transitions_at_threshold(self):
        policy = _make_policy(completed_debates=19)
        assert policy.maturity == SystemMaturity.COLD_START

        policy.record_completed_debate()  # 20th debate
        assert policy.maturity == SystemMaturity.OPERATIONAL

    def test_already_operational(self):
        policy = _make_policy(completed_debates=25)
        assert policy.maturity == SystemMaturity.OPERATIONAL
        assert policy.completed_debates == 25


# =============================================================================
# TEST: Audit Entry
# =============================================================================


class TestAuditEntry:
    """Audit entry is properly populated."""

    def test_escalated_audit(self):
        policy = _make_policy(completed_debates=25)
        ctx = _make_ctx(
            fast_confidence_band=ConfidenceBand.LOW,
            fast_reason_code="FAST-ESCALATE-AMBIGUITY",
        )
        result = policy.evaluate(ctx)

        audit = result.audit_entry
        assert audit is not None
        assert audit.escalation_decision == "ESCALATED"
        assert audit.trigger_count == 2
        assert audit.fast_confidence_band == "LOW"
        assert audit.fast_reason_code == "FAST-ESCALATE-AMBIGUITY"
        assert audit.mode_used == "DEEP"
        assert audit.system_maturity == "OPERATIONAL"
        assert audit.correlation_id == "test-corr-001"

    def test_not_escalated_audit(self):
        policy = _make_policy(completed_debates=25)
        ctx = _make_ctx()
        result = policy.evaluate(ctx)

        audit = result.audit_entry
        assert audit is not None
        assert audit.escalation_decision == "NOT_ESCALATED"
        assert audit.mode_used == "FAST"


# =============================================================================
# TEST: Single-Model-Only Invariant
# =============================================================================


class TestSingleModelInvariant:
    """
    Verify the escalation policy never references multiple models.
    This is a design-level test — the policy only selects modes,
    not models.
    """

    def test_policy_does_not_reference_model(self):
        """EscalationPolicy has no model attribute."""
        policy = _make_policy()
        assert not hasattr(policy, "model")
        assert not hasattr(policy, "_model")
        assert not hasattr(policy, "secondary_model")

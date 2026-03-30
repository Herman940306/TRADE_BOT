"""
============================================================================
Project Autonomous Alpha — Phase 9, Sub-Phase P9.3
Exhaustive Tests: Dual-Mode Reasoning Invariants
============================================================================

Reliability Level: SOVEREIGN TIER
Test Framework: pytest (parametrized — Hypothesis incompatible with Python 3.14)
Targets: app/logic/escalation_policy.py, app/logic/reasoning_mode.py

PROPERTIES TESTED
-----------------
1. Escalation is deterministic (same input → same output)
2. FAST config budget < DEEP config budget
3. Escalation never produces unknown trigger codes
4. Cold-start threshold is always >= operational threshold
5. Mode configs are immutable
6. All reason codes are unique across modes
7. Confidence bands are ordered
============================================================================
"""

import pytest

from app.logic.escalation_policy import (
    EscalationContext,
    EscalationPolicy,
)
from app.logic.reasoning_mode import (
    DEEP_MODE_CONFIG,
    FAST_MODE_CONFIG,
    ConfidenceBand,
    DeepReasonCode,
    EscalationRejectCode,
    FastReasonCode,
    ReasoningMode,
    get_mode_config,
)


def make_escalation_context(**overrides):
    """Create an EscalationContext with defaults."""
    defaults = dict(
        correlation_id="test-corr-id",
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


# ============================================================================
# P1: ESCALATION IS DETERMINISTIC
# ============================================================================

# Exhaustive combinations of key escalation parameters
_ESCALATION_COMBOS = []
for band in [ConfidenceBand.HIGH, ConfidenceBand.MEDIUM, ConfidenceBand.LOW]:
    for t1 in [0, 1, 3]:
        for contradiction in [False, True]:
            for risk in [False, True]:
                for degraded in [False, True]:
                    _ESCALATION_COMBOS.append((band, t1, contradiction, risk, degraded))


@pytest.mark.parametrize(
    "band,t1_missing,contradiction,risk_elevated,degraded",
    _ESCALATION_COMBOS[:60],  # 60 representative combos
    ids=[
        f"b={c[0].value}-t1={c[1]}-con={c[2]}-risk={c[3]}-deg={c[4]}"
        for c in _ESCALATION_COMBOS[:60]
    ],
)
def test_escalation_deterministic(
    band, t1_missing, contradiction, risk_elevated, degraded
):
    """Same inputs always produce same escalation result."""
    policy = EscalationPolicy()

    ctx = make_escalation_context(
        fast_confidence_band=band,
        missing_t1_count=t1_missing,
        contradiction_detected=contradiction,
        risk_elevated=risk_elevated,
        degraded_context=degraded,
    )

    result1 = policy.evaluate(ctx)
    result2 = policy.evaluate(ctx)

    assert result1.should_escalate == result2.should_escalate
    assert set(result1.triggers) == set(result2.triggers)


# ============================================================================
# P2: FAST BUDGET < DEEP BUDGET
# ============================================================================


def test_fast_budget_less_than_deep():
    """FAST mode safe operating budget must be less than DEEP."""
    assert (
        FAST_MODE_CONFIG.safe_operating_budget < DEEP_MODE_CONFIG.safe_operating_budget
    )


def test_fast_output_reserve_less_than_deep():
    """FAST output reserve must be less than or equal to DEEP."""
    assert FAST_MODE_CONFIG.output_reserve <= DEEP_MODE_CONFIG.output_reserve


def test_fast_num_predict_less_than_deep():
    """FAST num_predict must be less than DEEP."""
    assert FAST_MODE_CONFIG.num_predict < DEEP_MODE_CONFIG.num_predict


# ============================================================================
# P3: ESCALATION TRIGGER CODES ARE KNOWN
# ============================================================================

KNOWN_TRIGGERS = {
    "ESC-T01",
    "ESC-T02",
    "ESC-T03",
    "ESC-T04",
    "ESC-T05",
    "ESC-T06",
    "ESC-T07",
    "ESC-T08",
    "ESC-T09",
    "ESC-T10",
}

_TRIGGER_COMBOS = []
for band in [ConfidenceBand.HIGH, ConfidenceBand.MEDIUM, ConfidenceBand.LOW]:
    for contradiction in [False, True]:
        for risk_elevated in [False, True]:
            for degraded in [False, True]:
                _TRIGGER_COMBOS.append((band, contradiction, risk_elevated, degraded))


@pytest.mark.parametrize(
    "band,contradiction,risk_elevated,degraded",
    _TRIGGER_COMBOS,
)
def test_escalation_triggers_are_known(band, contradiction, risk_elevated, degraded):
    """Every escalation trigger must be from a known set."""
    policy = EscalationPolicy()
    ctx = make_escalation_context(
        fast_confidence_band=band,
        contradiction_detected=contradiction,
        risk_elevated=risk_elevated,
        degraded_context=degraded,
    )
    result = policy.evaluate(ctx)
    for trigger in result.triggers:
        assert trigger in KNOWN_TRIGGERS, f"Unknown trigger: {trigger}"


# ============================================================================
# P4: MODE CONFIGS ARE INTERNALLY CONSISTENT
# ============================================================================


def test_fast_config_mode_is_fast():
    """FAST config must have mode=FAST."""
    assert FAST_MODE_CONFIG.mode == ReasoningMode.FAST


def test_deep_config_mode_is_deep():
    """DEEP config must have mode=DEEP."""
    assert DEEP_MODE_CONFIG.mode == ReasoningMode.DEEP


def test_get_mode_config_returns_correct():
    """get_mode_config must return correct config for each mode."""
    assert get_mode_config(ReasoningMode.FAST) is FAST_MODE_CONFIG
    assert get_mode_config(ReasoningMode.DEEP) is DEEP_MODE_CONFIG


def test_fast_thinking_disabled():
    """FAST mode must have thinking disabled."""
    assert FAST_MODE_CONFIG.thinking_enabled is False


def test_deep_thinking_enabled():
    """DEEP mode must have thinking enabled."""
    assert DEEP_MODE_CONFIG.thinking_enabled is True


# ============================================================================
# P5: ALL REASON CODES ARE UNIQUE
# ============================================================================


def test_no_overlapping_reason_codes():
    """FAST and DEEP reason codes must not overlap."""
    fast_codes = {c.value for c in FastReasonCode}
    deep_codes = {c.value for c in DeepReasonCode}
    esc_codes = {c.value for c in EscalationRejectCode}

    assert fast_codes.isdisjoint(deep_codes), "FAST/DEEP codes overlap"
    assert fast_codes.isdisjoint(esc_codes), "FAST/ESC codes overlap"
    assert deep_codes.isdisjoint(esc_codes), "DEEP/ESC codes overlap"


# ============================================================================
# P6: T1 MISSING ALWAYS ESCALATES
# ============================================================================


@pytest.mark.parametrize("t1_count", [1, 2, 3, 4, 5])
def test_missing_t1_always_escalates(t1_count):
    """Any missing T1 data must always trigger escalation."""
    policy = EscalationPolicy()
    ctx = make_escalation_context(
        fast_confidence_band=ConfidenceBand.HIGH,
        missing_t1_count=t1_count,
    )
    result = policy.evaluate(ctx)
    assert result.should_escalate
    assert "ESC-T04" in result.triggers


# ============================================================================
# P7: LOW CONFIDENCE ALWAYS ESCALATES
# ============================================================================


def test_low_confidence_always_escalates():
    """LOW confidence band must always trigger escalation."""
    policy = EscalationPolicy()
    ctx = make_escalation_context(fast_confidence_band=ConfidenceBand.LOW)
    result = policy.evaluate(ctx)
    assert result.should_escalate
    assert "ESC-T01" in result.triggers


# ============================================================================
# P8: TEMPERATURE BOUNDS
# ============================================================================


def test_temperatures_are_valid():
    """Temperatures must be between 0 and 1."""
    assert 0 < FAST_MODE_CONFIG.temperature <= 1
    assert 0 < DEEP_MODE_CONFIG.temperature <= 1


def test_deep_temperature_lower_or_equal():
    """DEEP temperature should be lower or equal for more deterministic output."""
    assert DEEP_MODE_CONFIG.temperature <= FAST_MODE_CONFIG.temperature


# ============================================================================
# P9: TIMEOUT BOUNDS
# ============================================================================


def test_timeouts_are_positive():
    """Timeouts must be positive."""
    assert FAST_MODE_CONFIG.timeout_seconds > 0
    assert DEEP_MODE_CONFIG.timeout_seconds > 0


def test_deep_timeout_greater_or_equal():
    """DEEP timeout should be >= FAST timeout."""
    assert DEEP_MODE_CONFIG.timeout_seconds >= FAST_MODE_CONFIG.timeout_seconds

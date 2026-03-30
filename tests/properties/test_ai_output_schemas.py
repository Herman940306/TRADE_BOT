"""
============================================================================
Project Autonomous Alpha — Phase 9, Sub-Phase P9.3
Exhaustive Tests: AI Output Schema Invariants
============================================================================

Reliability Level: SOVEREIGN TIER
Test Framework: pytest (parametrized — Hypothesis incompatible with Python 3.14)
Target: app/schemas/ai_output.py

PROPERTIES TESTED
-----------------
1. Valid VerdictOutput always passes validation
2. Invalid verdict values always rejected
3. Reason code / mode consistency enforced
4. Confidence band enum enforcement
5. Field length limits enforced
6. Float rejection at Decimal boundary
7. Frozen model prevents mutation
============================================================================
"""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.ai_output import (
    ALL_DEEP_CODES,
    ALL_FAST_CODES,
    AIReasoningOutput,
    ConfidenceBandValue,
    DualModeDebateOutput,
    ReasoningModeValue,
    VerdictOutput,
    VerdictValue,
    safe_decimal,
    validate_no_float,
)

# ============================================================================
# P1: VALID VERDICT ALWAYS PASSES VALIDATION
# ============================================================================


VERDICTS = [v.value for v in VerdictValue]
BANDS = [b.value for b in ConfidenceBandValue]
COUNTS = [0, 1, 5, 50, 100]


@pytest.mark.parametrize("verdict", VERDICTS)
@pytest.mark.parametrize("confidence", BANDS)
@pytest.mark.parametrize("fact_count", COUNTS)
def test_valid_fast_verdict_always_validates(verdict, confidence, fact_count):
    """A well-formed FAST verdict always passes schema validation."""
    code = "FAST-APPROVE-CLEAR" if verdict == "APPROVED" else "FAST-REJECT-INSUFFICIENT"
    v = VerdictOutput(
        verdict=verdict,
        reason_code=code,
        confidence_band=confidence,
        reasoning="Test reasoning text",
        reasoning_mode="FAST",
        fact_count=fact_count,
        contradiction_count=0,
        inference_count=0,
    )
    assert v.verdict == verdict
    assert v.reasoning_mode == ReasoningModeValue.FAST


@pytest.mark.parametrize("verdict", VERDICTS)
@pytest.mark.parametrize("confidence", BANDS)
def test_valid_deep_verdict_always_validates(verdict, confidence):
    """A well-formed DEEP verdict always passes schema validation."""
    code = (
        "DEEP-APPROVE-RESOLVED" if verdict == "APPROVED" else "DEEP-REJECT-UNRESOLVED"
    )
    v = VerdictOutput(
        verdict=verdict,
        reason_code=code,
        confidence_band=confidence,
        reasoning="Deep reasoning text",
        reasoning_mode="DEEP",
        fact_count=3,
        contradiction_count=0,
        inference_count=0,
    )
    assert v.verdict == verdict
    assert v.reasoning_mode == ReasoningModeValue.DEEP


# ============================================================================
# P2: INVALID VERDICT VALUES ALWAYS REJECTED
# ============================================================================


@pytest.mark.parametrize(
    "bad_verdict",
    ["MAYBE", "YES", "NO", "HOLD", "", "approved", "Rejected", "BUY", "SELL", "NULL"],
)
def test_invalid_verdict_rejected(bad_verdict):
    """Non-APPROVED/REJECTED verdict values are always rejected."""
    with pytest.raises(ValidationError):
        VerdictOutput(
            verdict=bad_verdict,
            reason_code="FAST-APPROVE-CLEAR",
            confidence_band="HIGH",
            reasoning="Test",
            reasoning_mode="FAST",
            fact_count=0,
            contradiction_count=0,
            inference_count=0,
        )


# ============================================================================
# P3: REASON CODE / MODE CONSISTENCY
# ============================================================================


@pytest.mark.parametrize("deep_code", sorted(ALL_DEEP_CODES))
def test_deep_code_on_fast_mode_rejected(deep_code):
    """DEEP reason code on FAST mode verdict must fail validation."""
    with pytest.raises(ValidationError):
        VerdictOutput(
            verdict="REJECTED",
            reason_code=deep_code,
            confidence_band="LOW",
            reasoning="Mismatch test",
            reasoning_mode="FAST",
            fact_count=0,
            contradiction_count=0,
            inference_count=0,
        )


@pytest.mark.parametrize("fast_code", sorted(ALL_FAST_CODES))
def test_fast_code_on_deep_mode_rejected(fast_code):
    """FAST reason code on DEEP mode verdict must fail validation."""
    with pytest.raises(ValidationError):
        VerdictOutput(
            verdict="REJECTED",
            reason_code=fast_code,
            confidence_band="LOW",
            reasoning="Mismatch test",
            reasoning_mode="DEEP",
            fact_count=0,
            contradiction_count=0,
            inference_count=0,
        )


# ============================================================================
# P4: CONFIDENCE BAND ENUM ENFORCEMENT
# ============================================================================


@pytest.mark.parametrize(
    "bad_band", ["HIGHEST", "MED", "NONE", "", "high", "Very High", "1", "0"]
)
def test_invalid_confidence_band_rejected(bad_band):
    """Invalid confidence band values are rejected."""
    with pytest.raises(ValidationError):
        VerdictOutput(
            verdict="APPROVED",
            reason_code="FAST-APPROVE-CLEAR",
            confidence_band=bad_band,
            reasoning="Test",
            reasoning_mode="FAST",
            fact_count=0,
            contradiction_count=0,
            inference_count=0,
        )


# ============================================================================
# P5: FIELD LENGTH LIMITS
# ============================================================================


def test_empty_reasoning_rejected():
    """Empty reasoning must be rejected (min_length=1)."""
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


def test_oversized_reasoning_rejected():
    """Reasoning exceeding 500 chars must be rejected."""
    with pytest.raises(ValidationError):
        VerdictOutput(
            verdict="APPROVED",
            reason_code="FAST-APPROVE-CLEAR",
            confidence_band="HIGH",
            reasoning="x" * 501,
            reasoning_mode="FAST",
            fact_count=0,
            contradiction_count=0,
            inference_count=0,
        )


# ============================================================================
# P6: FLOAT REJECTION AT DECIMAL BOUNDARY
# ============================================================================


def test_validate_no_float_rejects_float():
    """validate_no_float must reject Python float."""
    with pytest.raises(ValueError, match="FLOAT-VIOLATION"):
        validate_no_float(3.14, "test_field")


def test_validate_no_float_accepts_decimal():
    """validate_no_float must accept Decimal."""
    validate_no_float(Decimal("3.14"), "test_field")


def test_validate_no_float_accepts_int():
    """validate_no_float must accept int."""
    validate_no_float(42, "test_field")


def test_validate_no_float_accepts_str():
    """validate_no_float must accept str."""
    validate_no_float("3.14", "test_field")


@pytest.mark.parametrize(
    "f", [0.0, 1.0, -1.0, 3.14, 1e10, 1e-10, 0.1, 99999.99, float("inf"), float("-inf")]
)
def test_safe_decimal_rejects_all_floats(f):
    """safe_decimal must reject any float value."""
    with pytest.raises(ValueError, match="FLOAT-VIOLATION"):
        safe_decimal(f, "test")


@pytest.mark.parametrize("i", [-999999, -1, 0, 1, 42, 100, 999999])
def test_safe_decimal_accepts_all_ints(i):
    """safe_decimal must accept any int and return Decimal."""
    result = safe_decimal(i, "test")
    assert isinstance(result, Decimal)
    assert result == Decimal(str(i))


# ============================================================================
# P7: FROZEN MODEL PREVENTS MUTATION
# ============================================================================


def test_verdict_output_frozen():
    """VerdictOutput must be immutable after creation."""
    v = VerdictOutput(
        verdict="APPROVED",
        reason_code="FAST-APPROVE-CLEAR",
        confidence_band="HIGH",
        reasoning="Test",
        reasoning_mode="FAST",
        fact_count=1,
        contradiction_count=0,
        inference_count=0,
    )
    with pytest.raises(ValidationError):
        v.verdict = "REJECTED"


def test_ai_reasoning_output_frozen():
    """AIReasoningOutput must be immutable after creation."""
    r = AIReasoningOutput(
        reasoning_mode="FAST",
        raw_response="test response",
        parse_success=True,
        fact_count=1,
        contradiction_count=0,
        inference_count=0,
    )
    with pytest.raises(ValidationError):
        r.fact_count = 99


# ============================================================================
# NEGATIVE INT REJECTION
# ============================================================================


@pytest.mark.parametrize("neg", [-1, -5, -100, -999999])
def test_negative_fact_count_rejected(neg):
    """Negative fact_count must be rejected."""
    with pytest.raises(ValidationError):
        VerdictOutput(
            verdict="APPROVED",
            reason_code="FAST-APPROVE-CLEAR",
            confidence_band="HIGH",
            reasoning="Test",
            reasoning_mode="FAST",
            fact_count=neg,
            contradiction_count=0,
            inference_count=0,
        )


# ============================================================================
# DUAL MODE DEBATE OUTPUT VALIDATION
# ============================================================================


def test_valid_dual_mode_debate_output():
    """A well-formed DualModeDebateOutput passes validation."""
    d = DualModeDebateOutput(
        correlation_id="test-corr-id",
        mode_used="FAST",
        verdict=False,
        reason_code="FAST-REJECT-RISK",
        confidence_band="LOW",
        reasoning="Risk too high",
        fact_count=2,
        contradiction_count=0,
        inference_count=0,
        reasoning_depth_used="FAST",
        escalated=False,
        latency_ms=150,
        parse_success=True,
    )
    assert d.verdict is False
    assert d.mode_used == ReasoningModeValue.FAST


def test_escalation_reject_code_accepted():
    """Escalation reject codes are valid in DualModeDebateOutput."""
    d = DualModeDebateOutput(
        correlation_id="test-corr-id",
        mode_used="FAST",
        verdict=False,
        reason_code="ESC-REJECT-DEEP-DISABLED",
        confidence_band="LOW",
        reasoning="Deep mode disabled",
        fact_count=0,
        contradiction_count=0,
        inference_count=0,
        reasoning_depth_used="FAST",
        escalated=False,
        latency_ms=50,
    )
    assert d.reason_code == "ESC-REJECT-DEEP-DISABLED"


def test_invalid_reasoning_depth_rejected():
    """Invalid reasoning_depth_used must be rejected."""
    with pytest.raises(ValidationError):
        DualModeDebateOutput(
            correlation_id="test",
            mode_used="FAST",
            verdict=False,
            reason_code="FAST-ERROR",
            confidence_band="LOW",
            reasoning="err",
            fact_count=0,
            contradiction_count=0,
            inference_count=0,
            reasoning_depth_used="INVALID",
            escalated=False,
            latency_ms=0,
        )

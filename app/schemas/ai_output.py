"""
============================================================================
Project Autonomous Alpha — Phase 9, Sub-Phase P9.1
AI Output Schemas — Pydantic v2 Strict Validation
============================================================================

Reliability Level: SOVEREIGN TIER (Mission-Critical)
Input Constraints: Untrusted LLM output text, must validate strictly
Side Effects: None (pure validation)

PURPOSE
-------
Strict Pydantic v2 schemas for validating AI-generated output at the
parsing boundary. LLM responses are fundamentally untrusted external input.
These schemas enforce structural and semantic correctness before any
verdict is accepted into the trading pipeline.

FAIL-CLOSED MANDATE
-------------------
If validation fails, the verdict is REJECTED. No retry, no fallback.

ZERO-FLOAT MANDATE
------------------
All financial values use Decimal. Float type is rejected at validation.

============================================================================
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any, List

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

# ============================================================================
# ENUMS
# ============================================================================


class VerdictValue(str, Enum):
    """Valid verdict values from AI reasoning."""

    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ConfidenceBandValue(str, Enum):
    """Valid confidence band values."""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class ReasoningModeValue(str, Enum):
    """Valid reasoning mode values."""

    FAST = "FAST"
    DEEP = "DEEP"


# ============================================================================
# FAST MODE REASON CODES
# ============================================================================


class FastReasonCodeValue(str, Enum):
    """Valid FAST mode reason codes."""

    APPROVE_CLEAR = "FAST-APPROVE-CLEAR"
    REJECT_INSUFFICIENT = "FAST-REJECT-INSUFFICIENT"
    REJECT_RISK = "FAST-REJECT-RISK"
    REJECT_CONFLICT = "FAST-REJECT-CONFLICT"
    ESCALATE_AMBIGUITY = "FAST-ESCALATE-AMBIGUITY"
    ESCALATE_RISK = "FAST-ESCALATE-RISK"
    ERROR = "FAST-ERROR"


# ============================================================================
# DEEP MODE REASON CODES
# ============================================================================


class DeepReasonCodeValue(str, Enum):
    """Valid DEEP mode reason codes."""

    APPROVE_RESOLVED = "DEEP-APPROVE-RESOLVED"
    APPROVE_CONDITIONAL = "DEEP-APPROVE-CONDITIONAL"
    REJECT_UNRESOLVED = "DEEP-REJECT-UNRESOLVED"
    REJECT_CONTRADICTION = "DEEP-REJECT-CONTRADICTION"
    REJECT_INSUFFICIENT = "DEEP-REJECT-INSUFFICIENT"
    REJECT_RISK_EXCESS = "DEEP-REJECT-RISK-EXCESS"
    ERROR = "DEEP-ERROR"


# ============================================================================
# ALL VALID REASON CODES
# ============================================================================

ALL_FAST_CODES = {c.value for c in FastReasonCodeValue}
ALL_DEEP_CODES = {c.value for c in DeepReasonCodeValue}
ALL_REASON_CODES = ALL_FAST_CODES | ALL_DEEP_CODES


# ============================================================================
# VERDICT OUTPUT SCHEMA
# ============================================================================


class VerdictOutput(BaseModel):
    """
    Pydantic v2 schema for a parsed AI verdict.

    This validates the structured output extracted from the
    ---VERDICT---/---END--- block in the LLM response.

    Validation Rules:
        - verdict: must be APPROVED or REJECTED
        - reason_code: must be from the valid set for the mode
        - confidence_band: must be HIGH, MEDIUM, or LOW
        - reasoning: max 500 chars, non-empty
        - fact_count, contradiction_count, inference_count: non-negative ints
    """

    model_config = ConfigDict(frozen=True, use_enum_values=True)

    verdict: VerdictValue
    reason_code: str = Field(min_length=1, max_length=50)
    confidence_band: ConfidenceBandValue
    reasoning: str = Field(min_length=1, max_length=500)
    reasoning_mode: ReasoningModeValue
    spec_version: str = Field(default="", max_length=20)
    fact_count: int = Field(ge=0, le=100)
    contradiction_count: int = Field(ge=0, le=100)
    inference_count: int = Field(ge=0, le=100)
    missing_data_impact: str = Field(default="", max_length=200)
    escalation_resolved: bool = False

    @field_validator("reason_code")
    @classmethod
    def validate_reason_code(cls, v: str) -> str:
        """Reason code must be from a known set."""
        if v not in ALL_REASON_CODES:
            raise ValueError(
                f"Unknown reason_code: {v!r}. "
                f"Must be one of: {sorted(ALL_REASON_CODES)}"
            )
        return v

    @model_validator(mode="after")
    def validate_mode_code_consistency(self) -> "VerdictOutput":
        """Reason code prefix must match the reasoning mode."""
        if self.reasoning_mode == ReasoningModeValue.FAST:
            if self.reason_code not in ALL_FAST_CODES:
                raise ValueError(
                    f"FAST mode verdict has non-FAST reason_code: {self.reason_code}"
                )
        elif self.reasoning_mode == ReasoningModeValue.DEEP:
            if self.reason_code not in ALL_DEEP_CODES:
                raise ValueError(
                    f"DEEP mode verdict has non-DEEP reason_code: {self.reason_code}"
                )
        return self


# ============================================================================
# AI REASONING OUTPUT SCHEMA
# ============================================================================


class AIReasoningOutput(BaseModel):
    """
    Schema for the full AI reasoning payload.

    Captures the complete reasoning context including facts discovered,
    contradictions identified, and inferences made by the model.
    """

    model_config = ConfigDict(frozen=True, use_enum_values=True)

    reasoning_mode: ReasoningModeValue
    raw_response: str = Field(max_length=10000)
    parse_success: bool
    fact_count: int = Field(ge=0, le=100)
    contradiction_count: int = Field(ge=0, le=100)
    inference_count: int = Field(ge=0, le=100)
    reasoning_text: str = Field(default="", max_length=2000)
    missing_data_impact: str = Field(default="", max_length=200)


# ============================================================================
# DUAL-MODE DEBATE OUTPUT SCHEMA
# ============================================================================


class DualModeDebateOutput(BaseModel):
    """
    Schema for the complete dual-mode debate result.

    Validates the full output of the DualModeReasoner including
    escalation audit trail and X-factor reasoning depth.
    """

    model_config = ConfigDict(frozen=True, use_enum_values=True)

    correlation_id: str = Field(min_length=1, max_length=64)
    mode_used: ReasoningModeValue
    verdict: bool
    reason_code: str = Field(min_length=1, max_length=50)
    confidence_band: str = Field(min_length=1, max_length=10)
    reasoning: str = Field(default="", max_length=2000)
    fact_count: int = Field(ge=0, le=100)
    contradiction_count: int = Field(ge=0, le=100)
    inference_count: int = Field(ge=0, le=100)
    reasoning_depth_used: str = Field(min_length=1, max_length=10)
    escalated: bool
    escalation_triggers: List[str] = Field(default_factory=list)
    latency_ms: int = Field(ge=0)
    parse_success: bool = False
    error_detail: str = Field(default="", max_length=500)

    @field_validator("reason_code")
    @classmethod
    def validate_reason_code(cls, v: str) -> str:
        """Reason code must be from a known set (includes escalation reject codes)."""
        escalation_codes = {
            "ESC-REJECT-UNRESOLVED",
            "ESC-REJECT-TIMEOUT",
            "ESC-REJECT-ERROR",
            "ESC-REJECT-BUDGET-OVERFLOW",
            "ESC-REJECT-LOOP-DETECTED",
            "ESC-REJECT-DEEP-DISABLED",
        }
        all_valid = ALL_REASON_CODES | escalation_codes
        if v not in all_valid:
            raise ValueError(f"Unknown reason_code: {v!r}")
        return v

    @field_validator("confidence_band")
    @classmethod
    def validate_confidence_band(cls, v: str) -> str:
        """Confidence band must be a valid value."""
        valid = {"HIGH", "MEDIUM", "LOW"}
        if v not in valid:
            raise ValueError(f"Invalid confidence_band: {v!r}")
        return v

    @field_validator("reasoning_depth_used")
    @classmethod
    def validate_depth(cls, v: str) -> str:
        """Reasoning depth must be FAST or DEEP."""
        if v not in ("FAST", "DEEP"):
            raise ValueError(f"Invalid reasoning_depth_used: {v!r}")
        return v


# ============================================================================
# DECIMAL VALIDATION HELPER
# ============================================================================


def validate_no_float(value: Any, field_name: str) -> None:
    """
    Zero-Float Mandate enforcement for schema boundaries.

    Raises ValueError if value is a Python float.
    """
    if isinstance(value, float):
        raise ValueError(
            f"[FLOAT-VIOLATION] {field_name} received float: {value!r}. "
            f"Use Decimal instead."
        )


def safe_decimal(value: Any, field_name: str) -> Decimal:
    """
    Safely convert a value to Decimal at the schema boundary.

    Rejects floats, accepts str/int/Decimal.
    Returns Decimal("0") on conversion failure (fail-closed).
    """
    validate_no_float(value, field_name)
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0")

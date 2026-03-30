"""
Project Autonomous Alpha — Phase 8
Reasoning Mode — Enum and Configuration

Reliability Level: SOVEREIGN TIER (Mission-Critical)
Spec Reference: DUAL_MODE_REASONING_PLAN.md §4, §5
Policy Reference: FAST_DEEP_ESCALATION_POLICY.md

PURPOSE
-------
Defines the two reasoning modes (FAST and DEEP) and their associated
configuration parameters. This module is the single source of truth
for mode-specific settings used by the DualModeReasoner and
EscalationPolicy.

SINGLE-MODEL MANDATE
--------------------
Both modes use the same model (qwen3:8b). The difference is in prompt
structure, token budget, temperature, and thinking-mode activation.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum


class ReasoningMode(str, Enum):
    """Reasoning mode for AI Council debate."""

    FAST = "FAST"
    DEEP = "DEEP"


class SystemMaturity(str, Enum):
    """System maturity level for escalation threshold adjustment."""

    COLD_START = "COLD_START"
    OPERATIONAL = "OPERATIONAL"


# ── FAST Mode Reason Codes ──────────────────────────────────────────────────


class FastReasonCode(str, Enum):
    """Machine-parseable reason codes from FAST mode."""

    APPROVE_CLEAR = "FAST-APPROVE-CLEAR"
    REJECT_INSUFFICIENT = "FAST-REJECT-INSUFFICIENT"
    REJECT_RISK = "FAST-REJECT-RISK"
    REJECT_CONFLICT = "FAST-REJECT-CONFLICT"
    ESCALATE_AMBIGUITY = "FAST-ESCALATE-AMBIGUITY"
    ESCALATE_RISK = "FAST-ESCALATE-RISK"
    ERROR = "FAST-ERROR"


# ── DEEP Mode Reason Codes ──────────────────────────────────────────────────


class DeepReasonCode(str, Enum):
    """Machine-parseable reason codes from DEEP mode."""

    APPROVE_RESOLVED = "DEEP-APPROVE-RESOLVED"
    APPROVE_CONDITIONAL = "DEEP-APPROVE-CONDITIONAL"
    REJECT_UNRESOLVED = "DEEP-REJECT-UNRESOLVED"
    REJECT_CONTRADICTION = "DEEP-REJECT-CONTRADICTION"
    REJECT_INSUFFICIENT = "DEEP-REJECT-INSUFFICIENT"
    REJECT_RISK_EXCESS = "DEEP-REJECT-RISK-EXCESS"
    ERROR = "DEEP-ERROR"


# ── Escalation Reject Codes ─────────────────────────────────────────────────


class EscalationRejectCode(str, Enum):
    """Reject codes applied when escalation fails."""

    UNRESOLVED = "ESC-REJECT-UNRESOLVED"
    TIMEOUT = "ESC-REJECT-TIMEOUT"
    ERROR = "ESC-REJECT-ERROR"
    BUDGET_OVERFLOW = "ESC-REJECT-BUDGET-OVERFLOW"
    LOOP_DETECTED = "ESC-REJECT-LOOP-DETECTED"
    DEEP_DISABLED = "ESC-REJECT-DEEP-DISABLED"


# ── Confidence Bands ────────────────────────────────────────────────────────


class ConfidenceBand(str, Enum):
    """Confidence band reported by reasoning modes."""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


# ── Mode Configuration ──────────────────────────────────────────────────────


@dataclass(frozen=True)
class ModeConfig:
    """Configuration for a reasoning mode."""

    mode: ReasoningMode
    input_budget: int
    output_reserve: int
    safety_margin: int
    safe_operating_budget: int
    temperature: float
    num_predict: int
    timeout_seconds: int
    thinking_enabled: bool
    target_latency_seconds: int


# Phase 12: Optimized for qwen3:8b on local GPU (GTX 1080 Ti).
# FAST: /no_think, low temp for determinism, tight output cap (3 sentences max).
# Reduced num_predict from 256→192 since prompt is terser → less wasted tokens.
# Reduced temperature from 0.3→0.15 for more deterministic FAST rejections.
FAST_MODE_CONFIG = ModeConfig(
    mode=ReasoningMode.FAST,
    input_budget=1400,
    output_reserve=512,
    safety_margin=136,
    safe_operating_budget=2048,
    temperature=0.15,
    num_predict=192,
    timeout_seconds=25,
    thinking_enabled=False,
    target_latency_seconds=6,
)

# Phase 12: DEEP thinking enabled for contradiction analysis.
# Reduced temperature from 0.2→0.10 for structured, less speculative output.
# Reduced num_predict from 512→384 — analysis steps are bounded (4 steps, 1-2 sentences each).
# Timeout 45s (was 60s) — tighter guard against GPU stalls.
DEEP_MODE_CONFIG = ModeConfig(
    mode=ReasoningMode.DEEP,
    input_budget=1800,
    output_reserve=640,
    safety_margin=160,
    safe_operating_budget=2600,
    temperature=0.10,
    num_predict=384,
    timeout_seconds=45,
    thinking_enabled=True,
    target_latency_seconds=15,
)


def get_mode_config(mode: ReasoningMode) -> ModeConfig:
    """Get configuration for a reasoning mode."""
    if mode == ReasoningMode.FAST:
        return FAST_MODE_CONFIG
    return DEEP_MODE_CONFIG


# ── Escalation Threshold Configuration ──────────────────────────────────────


@dataclass
class EscalationThresholds:
    """Configurable escalation thresholds."""

    t2_missing_threshold: int
    t2_missing_cold_start: int
    cold_start_debates: int
    high_notional_paper: int
    deep_mode_timeout: int
    force_deep_symbols: list

    @classmethod
    def from_env(cls) -> "EscalationThresholds":
        """Load thresholds from environment variables with defaults."""
        force_symbols_raw = os.getenv("DEEP_MODE_FORCE_SYMBOLS", "")
        force_symbols = [s.strip() for s in force_symbols_raw.split(",") if s.strip()]
        return cls(
            t2_missing_threshold=int(os.getenv("ESCALATION_T2_MISSING_THRESHOLD", "2")),
            t2_missing_cold_start=int(os.getenv("ESCALATION_T2_MISSING_COLD_START", "4")),
            cold_start_debates=int(os.getenv("ESCALATION_COLD_START_DEBATES", "20")),
            high_notional_paper=int(os.getenv("ESCALATION_HIGH_NOTIONAL_PAPER", "5000")),
            deep_mode_timeout=int(os.getenv("DEEP_MODE_TIMEOUT_SECONDS", "60")),
            force_deep_symbols=force_symbols,
        )

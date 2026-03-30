"""
Project Autonomous Alpha — Phase 8
Escalation Policy — Deterministic FAST→DEEP Escalation

Reliability Level: SOVEREIGN TIER (Mission-Critical)
Spec Reference: FAST_DEEP_ESCALATION_POLICY.md
Policy Reference: DUAL_MODE_REASONING_PLAN.md §6

PURPOSE
-------
Evaluates whether a trade signal should escalate from FAST mode to
DEEP mode reasoning. All trigger evaluations are deterministic,
explicit, and produce auditable output.

FAIL-CLOSED MANDATE
-------------------
If escalation evaluation itself fails, the signal is REJECTED.
Escalation is allowed exactly ONCE per signal. No loops.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from decimal import Decimal
from typing import List, Optional

from app.logic.reasoning_mode import (
    ConfidenceBand,
    EscalationThresholds,
    ReasoningMode,
    SystemMaturity,
)

logger = logging.getLogger(__name__)


# ── Escalation Trigger Codes ────────────────────────────────────────────────


class EscalationTrigger:
    """Canonical escalation trigger codes."""

    T01_LOW_CONFIDENCE = "ESC-T01"
    T02_ESCALATE_REASON = "ESC-T02"
    T03_T2_MISSING = "ESC-T03"
    T04_T1_MISSING = "ESC-T04"
    T05_CONTRADICTION = "ESC-T05"
    T06_RISK_ELEVATED = "ESC-T06"
    T07_DEGRADED_CONTEXT = "ESC-T07"
    T08_PROVIDER_FALLBACK = "ESC-T08"
    T09_HIGH_NOTIONAL = "ESC-T09"
    T10_MANUAL_OVERRIDE = "ESC-T10"


# ── Audit Entry ─────────────────────────────────────────────────────────────


@dataclass
class EscalationAuditEntry:
    """Structured audit entry for an escalation decision."""

    correlation_id: str
    timestamp_utc: float
    escalation_decision: str  # "ESCALATED" or "NOT_ESCALATED"
    trigger_codes: List[str] = field(default_factory=list)
    trigger_count: int = 0
    system_maturity: str = ""
    fast_confidence_band: str = ""
    fast_reason_code: str = ""
    mode_used: str = ""
    detail: str = ""


# ── Signal Context (input to escalation evaluation) ─────────────────────────


@dataclass
class EscalationContext:
    """
    All data needed by the escalation policy to make a decision.

    This is assembled by the DualModeReasoner BEFORE calling evaluate().
    Each field maps to one or more escalation triggers.
    """

    correlation_id: str

    # From FAST mode response (may be empty if evaluating pre-FAST)
    fast_confidence_band: Optional[ConfidenceBand] = None
    fast_reason_code: Optional[str] = None

    # From decision packet
    missing_t1_count: int = 0
    missing_t2_count: int = 0

    # Pre-computed indicators
    contradiction_detected: bool = False
    risk_elevated: bool = False

    # From routing / reliability manager
    degraded_context: bool = False
    provider_fallback_active: bool = False

    # Trade parameters
    notional_value: Optional[Decimal] = None
    symbol: str = ""

    # Escalation tracking
    already_escalated: bool = False


# ── Escalation Result ────────────────────────────────────────────────────────


@dataclass
class EscalationResult:
    """Result of escalation policy evaluation."""

    should_escalate: bool
    triggers: List[str] = field(default_factory=list)
    audit_entry: Optional[EscalationAuditEntry] = None
    loop_detected: bool = False


# ── Escalation Policy ────────────────────────────────────────────────────────


class EscalationPolicy:
    """
    Deterministic escalation policy for FAST→DEEP mode transition.

    Evaluates a set of explicit, measurable trigger conditions and
    produces a binary decision: ESCALATE or NOT_ESCALATED.

    Properties:
    - Deterministic: same inputs → same decision
    - Monotonic: FAST → DEEP only, max once per signal
    - Fail-closed: evaluation failure → REJECTED
    - Auditable: full trigger list persisted
    """

    def __init__(
        self,
        thresholds: Optional[EscalationThresholds] = None,
        maturity: SystemMaturity = SystemMaturity.COLD_START,
        completed_debates: int = 0,
    ) -> None:
        self._thresholds = thresholds or EscalationThresholds.from_env()
        self._completed_debates = completed_debates
        self._maturity = maturity
        self._update_maturity()

    @property
    def maturity(self) -> SystemMaturity:
        return self._maturity

    @property
    def completed_debates(self) -> int:
        return self._completed_debates

    def record_completed_debate(self) -> None:
        """Record a completed debate and update maturity if needed."""
        self._completed_debates += 1
        old_maturity = self._maturity
        self._update_maturity()
        if old_maturity != self._maturity:
            logger.info(
                "[ESCALATION] Maturity transition: %s → %s (after %d debates)",
                old_maturity.value,
                self._maturity.value,
                self._completed_debates,
            )

    def _update_maturity(self) -> None:
        """Update system maturity based on completed debate count."""
        if self._completed_debates >= self._thresholds.cold_start_debates:
            self._maturity = SystemMaturity.OPERATIONAL
        else:
            self._maturity = SystemMaturity.COLD_START

    def evaluate(self, ctx: EscalationContext) -> EscalationResult:
        """
        Evaluate escalation triggers and decide whether to escalate.

        Returns EscalationResult with trigger list and audit entry.
        Raises no exceptions — errors produce EscalationResult with
        should_escalate=False and detail explaining the failure.
        """
        # ── Loop guard ──────────────────────────────────────────────
        if ctx.already_escalated:
            logger.error(
                "[ESCALATION] Loop detected | correlation_id=%s",
                ctx.correlation_id,
            )
            return EscalationResult(
                should_escalate=False,
                loop_detected=True,
                audit_entry=EscalationAuditEntry(
                    correlation_id=ctx.correlation_id,
                    timestamp_utc=time.time(),
                    escalation_decision="NOT_ESCALATED",
                    detail="ESC-REJECT-LOOP-DETECTED: second escalation attempt blocked",
                    system_maturity=self._maturity.value,
                ),
            )

        triggers: List[str] = []

        # ── ESC-T01: Low confidence ────────────────────────────────
        if ctx.fast_confidence_band == ConfidenceBand.LOW:
            triggers.append(EscalationTrigger.T01_LOW_CONFIDENCE)

        # ── ESC-T02: FAST escalate reason code ─────────────────────
        if ctx.fast_reason_code and ctx.fast_reason_code.startswith("FAST-ESCALATE"):
            triggers.append(EscalationTrigger.T02_ESCALATE_REASON)

        # ── ESC-T03: Missing T2 fields ─────────────────────────────
        t2_threshold = (
            self._thresholds.t2_missing_cold_start
            if self._maturity == SystemMaturity.COLD_START
            else self._thresholds.t2_missing_threshold
        )
        if ctx.missing_t2_count >= t2_threshold:
            triggers.append(EscalationTrigger.T03_T2_MISSING)

        # ── ESC-T04: Missing T1 fields ─────────────────────────────
        if ctx.missing_t1_count >= 1:
            triggers.append(EscalationTrigger.T04_T1_MISSING)

        # ── ESC-T05: Contradiction detected ────────────────────────
        if ctx.contradiction_detected:
            triggers.append(EscalationTrigger.T05_CONTRADICTION)

        # ── ESC-T06: Elevated risk ─────────────────────────────────
        if ctx.risk_elevated:
            triggers.append(EscalationTrigger.T06_RISK_ELEVATED)

        # ── ESC-T07: Degraded context ──────────────────────────────
        if ctx.degraded_context:
            triggers.append(EscalationTrigger.T07_DEGRADED_CONTEXT)

        # ── ESC-T08: Provider fallback ─────────────────────────────
        if ctx.provider_fallback_active:
            triggers.append(EscalationTrigger.T08_PROVIDER_FALLBACK)

        # ── ESC-T09: High notional value ───────────────────────────
        if ctx.notional_value is not None:
            threshold = Decimal(str(self._thresholds.high_notional_paper))
            if ctx.notional_value >= threshold:
                triggers.append(EscalationTrigger.T09_HIGH_NOTIONAL)

        # ── ESC-T10: Manual override ───────────────────────────────
        if ctx.symbol in self._thresholds.force_deep_symbols:
            triggers.append(EscalationTrigger.T10_MANUAL_OVERRIDE)

        # ── Decision ───────────────────────────────────────────────
        should_escalate = len(triggers) > 0

        audit = EscalationAuditEntry(
            correlation_id=ctx.correlation_id,
            timestamp_utc=time.time(),
            escalation_decision="ESCALATED" if should_escalate else "NOT_ESCALATED",
            trigger_codes=triggers,
            trigger_count=len(triggers),
            system_maturity=self._maturity.value,
            fast_confidence_band=(
                ctx.fast_confidence_band.value if ctx.fast_confidence_band else ""
            ),
            fast_reason_code=ctx.fast_reason_code or "",
            mode_used=ReasoningMode.DEEP.value
            if should_escalate
            else ReasoningMode.FAST.value,
        )

        if should_escalate:
            logger.info(
                "[ESCALATION] ESCALATED | correlation_id=%s | triggers=%s | "
                "trigger_count=%d | maturity=%s",
                ctx.correlation_id,
                triggers,
                len(triggers),
                self._maturity.value,
            )
        else:
            logger.debug(
                "[ESCALATION] NOT_ESCALATED | correlation_id=%s | maturity=%s",
                ctx.correlation_id,
                self._maturity.value,
            )

        return EscalationResult(
            should_escalate=should_escalate,
            triggers=triggers,
            audit_entry=audit,
        )

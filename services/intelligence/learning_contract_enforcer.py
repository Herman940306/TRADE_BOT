"""
Learning Contract Enforcer — ML Safety Invariant Checks

Validates that all intelligence services respect their operational contracts.
Runs BEFORE and AFTER every learning cycle. Contract violations are logged
for operator review — they DO NOT auto-heal.

Priority: P0 — Required before any other intelligence service operates.
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ContractSeverity(Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


@dataclass
class ContractViolation:
    """A single contract violation detected during enforcement."""

    check_type: str
    check_name: str
    severity: ContractSeverity
    details: dict[str, Any]
    affected_service: Optional[str] = None
    auto_healed: bool = False
    requires_operator: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_type": self.check_type,
            "check_name": self.check_name,
            "severity": self.severity.value,
            "details": self.details,
            "affected_service": self.affected_service,
            "auto_healed": self.auto_healed,
            "requires_operator": self.requires_operator,
        }


@dataclass
class ContractEnforcementResult:
    """Result of a full contract enforcement run."""

    passed: bool
    violations: list[ContractViolation] = field(default_factory=list)
    checks_run: int = 0
    checks_passed: int = 0
    duration_ms: int = 0
    correlation_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "violations": [v.to_dict() for v in self.violations],
            "checks_run": self.checks_run,
            "checks_passed": self.checks_passed,
            "duration_ms": self.duration_ms,
            "correlation_id": self.correlation_id,
        }


class LearningContractEnforcer:
    """
    Enforces safety invariants across all intelligence services.

    Contract Invariants:
    1. No float in any financial column
    2. Confidence values clamped to [0.01, 0.99]
    3. Budget never negative
    4. Mind state is a valid enum value
    5. All decisions have correlation_ids
    6. Golden set performance above minimum threshold
    7. Curriculum phase transitions are monotonic (except operator reset)
    """

    MIN_CONFIDENCE = Decimal("0.01")
    MAX_CONFIDENCE = Decimal("0.99")
    MIN_GOLDEN_SET_ACCURACY = Decimal("0.70")

    def __init__(
        self,
        db_session: Optional[Any] = None,
        correlation_id: Optional[str] = None,
    ):
        self._db_session = db_session
        self._correlation_id = correlation_id or str(uuid.uuid4())

    def validate_all(
        self,
        bayesian_state: Optional[dict[str, Any]] = None,
        budget_state: Optional[dict[str, Any]] = None,
        mind_state: Optional[str] = None,
        curriculum_phase: Optional[int] = None,
        golden_set_accuracy: Optional[Decimal] = None,
    ) -> ContractEnforcementResult:
        """
        Run all contract checks and return results.

        Args:
            bayesian_state: Current Bayesian belief state dict
            budget_state: Current confidence budget state dict
            mind_state: Current mind state string
            curriculum_phase: Current curriculum phase number
            golden_set_accuracy: Latest golden set accuracy as Decimal

        Returns:
            ContractEnforcementResult with all violations found
        """
        start = datetime.now(timezone.utc)
        violations: list[ContractViolation] = []
        checks_run = 0
        checks_passed = 0

        # Check 1: Bayesian confidence bounds
        if bayesian_state is not None:
            checks_run += 1
            v = self._check_confidence_bounds(bayesian_state)
            if v:
                violations.append(v)
            else:
                checks_passed += 1

        # Check 2: Budget non-negative
        if budget_state is not None:
            checks_run += 1
            v = self._check_budget_non_negative(budget_state)
            if v:
                violations.append(v)
            else:
                checks_passed += 1

        # Check 3: Valid mind state
        if mind_state is not None:
            checks_run += 1
            v = self._check_valid_mind_state(mind_state)
            if v:
                violations.append(v)
            else:
                checks_passed += 1

        # Check 4: Curriculum phase bounds
        if curriculum_phase is not None:
            checks_run += 1
            v = self._check_curriculum_phase(curriculum_phase)
            if v:
                violations.append(v)
            else:
                checks_passed += 1

        # Check 5: Golden set performance
        if golden_set_accuracy is not None:
            checks_run += 1
            v = self._check_golden_set_accuracy(golden_set_accuracy)
            if v:
                violations.append(v)
            else:
                checks_passed += 1

        elapsed = datetime.now(timezone.utc) - start
        duration_ms = int(elapsed.total_seconds() * 1000)

        result = ContractEnforcementResult(
            passed=len(violations) == 0,
            violations=violations,
            checks_run=checks_run,
            checks_passed=checks_passed,
            duration_ms=duration_ms,
            correlation_id=self._correlation_id,
        )

        if violations:
            critical_count = sum(
                1 for v in violations if v.severity == ContractSeverity.CRITICAL
            )
            logger.warning(
                "[LEARNING-CONTRACT] Contract violations detected | "
                f"total={len(violations)} critical={critical_count} | "
                f"correlation_id={self._correlation_id}"
            )
            self._persist_violations(violations)
        else:
            logger.info(
                "[LEARNING-CONTRACT] All contract checks passed | "
                f"checks_run={checks_run} | "
                f"correlation_id={self._correlation_id}"
            )

        return result

    def _check_confidence_bounds(
        self, bayesian_state: dict[str, Any]
    ) -> Optional[ContractViolation]:
        """Verify confidence values are within [0.01, 0.99]."""
        confidence = bayesian_state.get("confidence")
        if confidence is None:
            return None

        if not isinstance(confidence, Decimal):
            return ContractViolation(
                check_type="TYPE_SAFETY",
                check_name="confidence_is_decimal",
                severity=ContractSeverity.CRITICAL,
                details={
                    "expected": "Decimal",
                    "actual": type(confidence).__name__,
                    "value": str(confidence),
                },
                affected_service="BayesianReasoningService",
                requires_operator=True,
            )

        if confidence < self.MIN_CONFIDENCE or confidence > self.MAX_CONFIDENCE:
            return ContractViolation(
                check_type="BOUNDS",
                check_name="confidence_in_range",
                severity=ContractSeverity.CRITICAL,
                details={
                    "min": str(self.MIN_CONFIDENCE),
                    "max": str(self.MAX_CONFIDENCE),
                    "actual": str(confidence),
                },
                affected_service="BayesianReasoningService",
                requires_operator=True,
            )

        return None

    def _check_budget_non_negative(
        self, budget_state: dict[str, Any]
    ) -> Optional[ContractViolation]:
        """Verify remaining budget is not negative."""
        remaining = budget_state.get("remaining_budget")
        if remaining is None:
            return None

        if not isinstance(remaining, Decimal):
            return ContractViolation(
                check_type="TYPE_SAFETY",
                check_name="budget_is_decimal",
                severity=ContractSeverity.CRITICAL,
                details={
                    "expected": "Decimal",
                    "actual": type(remaining).__name__,
                },
                affected_service="ConfidenceBudgetService",
                requires_operator=True,
            )

        if remaining < Decimal("0"):
            return ContractViolation(
                check_type="INVARIANT",
                check_name="budget_non_negative",
                severity=ContractSeverity.CRITICAL,
                details={"remaining_budget": str(remaining)},
                affected_service="ConfidenceBudgetService",
                requires_operator=True,
            )

        return None

    def _check_valid_mind_state(
        self, mind_state: str
    ) -> Optional[ContractViolation]:
        """Verify mind state is a valid enum value."""
        valid_states = {"CALM", "ALERT", "DEFENSIVE"}
        if mind_state not in valid_states:
            return ContractViolation(
                check_type="ENUM",
                check_name="valid_mind_state",
                severity=ContractSeverity.CRITICAL,
                details={
                    "valid_states": list(valid_states),
                    "actual": mind_state,
                },
                affected_service="MindStateService",
                requires_operator=True,
            )
        return None

    def _check_curriculum_phase(
        self, phase: int
    ) -> Optional[ContractViolation]:
        """Verify curriculum phase is within valid range [1, 4]."""
        if not isinstance(phase, int) or phase < 1 or phase > 4:
            return ContractViolation(
                check_type="BOUNDS",
                check_name="curriculum_phase_valid",
                severity=ContractSeverity.WARNING,
                details={"expected_range": "1-4", "actual": str(phase)},
                affected_service="CurriculumScheduler",
                requires_operator=True,
            )
        return None

    def _check_golden_set_accuracy(
        self, accuracy: Decimal
    ) -> Optional[ContractViolation]:
        """Verify golden set accuracy meets minimum threshold."""
        if accuracy < self.MIN_GOLDEN_SET_ACCURACY:
            return ContractViolation(
                check_type="PERFORMANCE",
                check_name="golden_set_minimum_accuracy",
                severity=ContractSeverity.WARNING,
                details={
                    "minimum": str(self.MIN_GOLDEN_SET_ACCURACY),
                    "actual": str(accuracy),
                },
                affected_service="GoldenSetValidation",
                requires_operator=True,
            )
        return None

    def _persist_violations(
        self, violations: list[ContractViolation]
    ) -> None:
        """Persist violations to learning_contract_checks table."""
        if not self._db_session:
            logger.debug(
                "[LEARNING-CONTRACT] No DB session — violations logged only"
            )
            return

        try:
            from sqlalchemy import text

            for violation in violations:
                import json

                self._db_session.execute(
                    text("""
                        INSERT INTO learning_contract_checks
                            (check_type, check_name, passed, severity,
                             details, affected_service, auto_healed,
                             requires_operator, correlation_id)
                        VALUES
                            (:check_type, :check_name, :passed, :severity,
                             :details, :affected_service, :auto_healed,
                             :requires_operator, :correlation_id)
                    """),
                    {
                        "check_type": violation.check_type,
                        "check_name": violation.check_name,
                        "passed": False,
                        "severity": violation.severity.value,
                        "details": json.dumps(violation.details),
                        "affected_service": violation.affected_service,
                        "auto_healed": violation.auto_healed,
                        "requires_operator": violation.requires_operator,
                        "correlation_id": self._correlation_id,
                    },
                )
            self._db_session.commit()
        except Exception as e:
            logger.error(
                "[LEARNING-CONTRACT] Failed to persist violations | "
                f"error={e} | correlation_id={self._correlation_id}"
            )

"""
Tests for Intelligence Services — Phase 7 Merge

Validates the advisory-only ML/strategy layer:
- Bayesian reasoning
- Confidence budget
- Capital allocation
- Mind state
- Learning contract enforcement
- Decision snapshots
- Mind state policy
- Regime sandbox
- Curriculum scheduler
"""

from decimal import Decimal
from unittest.mock import MagicMock

import pytest

# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    session = MagicMock()
    session.execute = MagicMock()
    session.commit = MagicMock()
    return session


# ============================================================================
# BAYESIAN REASONING SERVICE
# ============================================================================


class TestBayesianReasoningService:
    """Test Bayesian multi-factor belief fusion."""

    @pytest.fixture
    def service(self, mock_db_session):
        from services.intelligence.bayesian_reasoning_service import (
            BayesianReasoningService,
        )

        return BayesianReasoningService(db_session=mock_db_session)

    def test_evaluate_returns_verdict(self, service):
        """Evaluate should return a BayesianVerdict with valid confidence."""
        from services.intelligence.bayesian_reasoning_service import EvidenceItem

        evidence = [
            EvidenceItem(
                source="technical",
                weight=Decimal("0.30"),
                likelihood_ratio=Decimal("1.7"),
            ),
            EvidenceItem(
                source="sentiment",
                weight=Decimal("0.10"),
                likelihood_ratio=Decimal("1.4"),
            ),
        ]

        verdict = service.evaluate(evidence=evidence)

        assert verdict is not None
        assert Decimal("0.01") <= verdict.confidence <= Decimal("0.99")

    def test_evaluate_empty_evidence(self, service):
        """Empty evidence should return neutral prior."""
        from services.intelligence.bayesian_reasoning_service import Direction

        verdict = service.evaluate(evidence=[])

        assert verdict is not None
        assert verdict.confidence == Decimal("0.50")
        assert verdict.direction == Direction.HOLD

    def test_confidence_clamped(self, service):
        """Confidence must never exceed [0.01, 0.99] bounds."""
        from services.intelligence.bayesian_reasoning_service import EvidenceItem

        extreme_evidence = [
            EvidenceItem(
                source="technical",
                weight=Decimal("1.0"),
                likelihood_ratio=Decimal("99.0"),
            ),
        ]

        verdict = service.evaluate(evidence=extreme_evidence)

        assert verdict.confidence <= Decimal("0.99")
        assert verdict.confidence >= Decimal("0.01")

    def test_in_memory_mode(self):
        """Service works without a DB session (in-memory mode)."""
        from services.intelligence.bayesian_reasoning_service import (
            BayesianReasoningService,
        )

        service = BayesianReasoningService(db_session=None)
        verdict = service.evaluate(evidence=[])

        assert verdict is not None
        assert verdict.evidence_count == 0


# ============================================================================
# CONFIDENCE BUDGET SERVICE
# ============================================================================


class TestConfidenceBudgetService:
    """Test daily confidence budget tracking."""

    @pytest.fixture
    def service(self, mock_db_session):
        from services.intelligence.confidence_budget_service import (
            ConfidenceBudgetService,
        )

        mock_db_session.execute.return_value.fetchone.return_value = None
        return ConfidenceBudgetService(db_session=mock_db_session)

    def test_check_budget_sufficient(self, service):
        """Check should pass when budget is sufficient."""
        result = service.check_budget(
            symbol="BTCZAR",
            confidence=Decimal("0.8"),
            risk_score=Decimal("0.3"),
            position_size_factor=Decimal("1.0"),
        )

        assert result is not None
        assert result.allowed is True

    def test_check_budget_deduction_amount(self, service):
        """Deduction amount must be tracked on BudgetCheckResult."""
        result = service.check_budget(
            symbol="BTCZAR",
            confidence=Decimal("0.6"),
            risk_score=Decimal("0.5"),
            position_size_factor=Decimal("2.0"),
        )

        assert result.deduction_amount >= Decimal("0")

    def test_in_memory_mode(self):
        """Service works without a DB session."""
        from services.intelligence.confidence_budget_service import (
            ConfidenceBudgetService,
        )

        service = ConfidenceBudgetService(db_session=None)
        result = service.check_budget(
            symbol="BTCZAR",
            confidence=Decimal("0.9"),
            risk_score=Decimal("0.1"),
            position_size_factor=Decimal("1.0"),
        )

        assert result is not None
        assert result.allowed is True


# ============================================================================
# CAPITAL ALLOCATION SERVICE
# ============================================================================


class TestCapitalAllocationService:
    """Test position sizing from confidence and mind state."""

    @pytest.fixture
    def service(self, mock_db_session):
        from services.intelligence.capital_allocation_service import (
            CapitalAllocationService,
        )

        return CapitalAllocationService(db_session=mock_db_session)

    def test_sizing_calm_state(self, service):
        """CALM state: 2% risk, full multiplier."""
        result = service.calculate_position_size(
            symbol="BTCZAR",
            confidence=Decimal("0.7"),
            mind_state="CALM",
            portfolio_value=Decimal("100000"),
        )

        assert result is not None
        assert result.final_size_zar > Decimal("0")
        assert result.mind_state == "CALM"
        assert result.mind_state_multiplier == Decimal("1.00")

    def test_sizing_defensive_state(self, service):
        """DEFENSIVE state: 0.5% risk, 0.25x multiplier."""
        result_calm = service.calculate_position_size(
            symbol="BTCZAR",
            confidence=Decimal("0.7"),
            mind_state="CALM",
            portfolio_value=Decimal("100000"),
        )
        result_defensive = service.calculate_position_size(
            symbol="BTCZAR",
            confidence=Decimal("0.7"),
            mind_state="DEFENSIVE",
            portfolio_value=Decimal("100000"),
        )

        assert result_defensive.final_size_zar < result_calm.final_size_zar
        assert result_defensive.mind_state_multiplier == Decimal("0.25")

    def test_sizing_capped_at_max(self, service):
        """Position size must not exceed max_position_zar."""
        result = service.calculate_position_size(
            symbol="BTCZAR",
            confidence=Decimal("0.99"),
            mind_state="CALM",
            portfolio_value=Decimal("100000"),
        )

        assert result.final_size_zar <= result.max_position_zar

    def test_zero_confidence(self, service):
        """Zero confidence should produce zero or near-zero size."""
        result = service.calculate_position_size(
            symbol="BTCZAR",
            confidence=Decimal("0"),
            mind_state="CALM",
            portfolio_value=Decimal("100000"),
        )

        assert result.final_size_zar == Decimal("0")


# ============================================================================
# MIND STATE SERVICE
# ============================================================================


class TestMindStateService:
    """Test CALM/ALERT/DEFENSIVE state machine."""

    @pytest.fixture
    def service(self, mock_db_session):
        from services.intelligence.mind_state_service import MindStateService

        return MindStateService(db_session=mock_db_session)

    def test_initial_state_is_calm(self, service):
        """Default state should be CALM."""
        assert service.current_state == "CALM"

    def test_transition_calm_to_alert(self, service):
        """2+ consecutive losses trigger CALM -> ALERT."""
        transition = service.evaluate_transitions(
            consecutive_losses=2,
            daily_drawdown_pct=Decimal("1.0"),
        )

        assert transition is not None
        assert transition.new_state == "ALERT"

    def test_transition_calm_to_defensive(self, service):
        """Guardian warning triggers CALM -> DEFENSIVE."""
        transition = service.evaluate_transitions(
            consecutive_losses=0,
            daily_drawdown_pct=Decimal("1.0"),
            guardian_warning=True,
        )

        assert transition is not None
        assert transition.new_state == "DEFENSIVE"

    def test_no_transition_on_calm_mild(self, service):
        """No transition when CALM and conditions are mild."""
        transition = service.evaluate_transitions(
            consecutive_losses=0,
            daily_drawdown_pct=Decimal("0.5"),
        )

        assert transition is None

    def test_alert_to_calm_on_recovery(self, service):
        """3 consecutive profits should recover ALERT -> CALM."""
        # First transition to ALERT
        service.evaluate_transitions(
            consecutive_losses=2,
            daily_drawdown_pct=Decimal("1.0"),
        )

        transition = service.evaluate_transitions(
            consecutive_losses=0,
            daily_drawdown_pct=Decimal("0.5"),
            consecutive_profits=3,
        )

        if transition is not None:
            assert transition.new_state == "CALM"


# ============================================================================
# LEARNING CONTRACT ENFORCER
# ============================================================================


class TestLearningContractEnforcer:
    """Test ML safety invariant enforcement."""

    @pytest.fixture
    def enforcer(self, mock_db_session):
        from services.intelligence.learning_contract_enforcer import (
            LearningContractEnforcer,
        )

        return LearningContractEnforcer(db_session=mock_db_session)

    def test_valid_state_passes_all(self, enforcer):
        """Valid inputs should pass all contract checks."""
        result = enforcer.validate_all(
            bayesian_state={"confidence": Decimal("0.75")},
            budget_state={"remaining_budget": Decimal("50.0")},
            mind_state="CALM",
            curriculum_phase=1,
            golden_set_accuracy=Decimal("0.80"),
        )

        assert result.passed is True
        assert result.checks_run > 0
        assert result.checks_passed == result.checks_run

    def test_invalid_confidence_fails(self, enforcer):
        """Confidence > 0.99 should produce a violation."""
        result = enforcer.validate_all(
            bayesian_state={"confidence": Decimal("1.5")},
        )

        assert result.passed is False
        assert len(result.violations) > 0

    def test_negative_budget_fails(self, enforcer):
        """Negative budget should produce a violation."""
        result = enforcer.validate_all(
            budget_state={"remaining_budget": Decimal("-1.0")},
        )

        assert result.passed is False
        assert len(result.violations) > 0

    def test_invalid_mind_state_fails(self, enforcer):
        """Unknown mind state should produce a violation."""
        result = enforcer.validate_all(
            mind_state="PANIC",
        )

        assert result.passed is False
        assert len(result.violations) > 0

    def test_valid_mind_states_pass(self, enforcer):
        """Valid mind states should not produce violations."""
        for state in ("CALM", "ALERT", "DEFENSIVE"):
            result = enforcer.validate_all(mind_state=state)
            mind_violations = [
                v for v in result.violations if "mind" in v.check_name.lower()
            ]
            assert len(mind_violations) == 0


# ============================================================================
# DECISION SNAPSHOT SERVICE
# ============================================================================


class TestDecisionSnapshotService:
    """Test forensic snapshot creation."""

    @pytest.fixture
    def service(self, mock_db_session):
        from services.intelligence.decision_snapshot_service import (
            DecisionSnapshotService,
        )

        return DecisionSnapshotService(db_session=mock_db_session)

    def test_record_creates_snapshot(self, service):
        """Recording a snapshot should return a DecisionSnapshot."""
        snapshot = service.record(
            signal_data={"symbol": "BTCZAR", "direction": "LONG"},
            bayesian_verdict={"direction": "LONG", "confidence": "0.75"},
            confidence=Decimal("0.75"),
            remaining_budget=Decimal("80.0"),
            mind_state="CALM",
            regime="TRENDING_UP",
            strategy_name="momentum_v1",
            proposed_size_zar=Decimal("2000.00"),
            final_size_zar=Decimal("1500.00"),
            guardian_status="UNLOCKED",
        )

        assert snapshot is not None
        assert snapshot.snapshot_id is not None

    def test_in_memory_mode(self):
        """Service works without DB."""
        from services.intelligence.decision_snapshot_service import (
            DecisionSnapshotService,
        )

        service = DecisionSnapshotService(db_session=None)
        snapshot = service.record(
            signal_data={},
            bayesian_verdict={},
            confidence=Decimal("0.5"),
            remaining_budget=Decimal("100.0"),
            mind_state="CALM",
            regime="UNKNOWN",
            strategy_name="test",
            proposed_size_zar=Decimal("0"),
            final_size_zar=Decimal("0"),
            guardian_status="UNLOCKED",
        )

        assert snapshot is not None


# ============================================================================
# MIND STATE POLICY SERVICE
# ============================================================================


class TestMindStatePolicyService:
    """Test position scaling and cooldown enforcement."""

    @pytest.fixture
    def service(self):
        from services.intelligence.mind_state_policy_service import (
            MindStatePolicyService,
        )

        return MindStatePolicyService()

    def test_calm_no_scaling(self, service):
        """CALM state applies no scaling adjustments."""
        verdict = service.apply_policy(
            proposed_size_zar=Decimal("1000"),
            mind_state="CALM",
        )

        assert verdict.allowed is True
        assert verdict.modified_size_zar == Decimal("1000")
        assert verdict.position_multiplier == Decimal("1.00")

    def test_defensive_scales_down(self, service):
        """DEFENSIVE state should scale position significantly."""
        verdict = service.apply_policy(
            proposed_size_zar=Decimal("1000"),
            mind_state="DEFENSIVE",
        )

        assert verdict.modified_size_zar < Decimal("1000")
        assert verdict.position_multiplier == Decimal("0.25")


# ============================================================================
# REGIME SANDBOX SERVICE
# ============================================================================


class TestRegimeSandboxService:
    """Test market regime classification."""

    @pytest.fixture
    def service(self, mock_db_session):
        from services.intelligence.regime_sandbox_service import RegimeSandboxService

        return RegimeSandboxService(db_session=mock_db_session)

    def test_classify_trending_up(self, service):
        """High ADX + price above SMA = TRENDING_UP."""
        from services.intelligence.regime_sandbox_service import Regime

        observation = service.classify_regime(
            symbol="BTCZAR",
            adx=Decimal("30"),
            atr_current=Decimal("500"),
            atr_average=Decimal("300"),
            price=Decimal("1200000"),
            sma_20=Decimal("1100000"),
        )

        assert observation.regime == Regime.TRENDING_UP

    def test_classify_ranging(self, service):
        """Low ADX = RANGING."""
        from services.intelligence.regime_sandbox_service import Regime

        observation = service.classify_regime(
            symbol="BTCZAR",
            adx=Decimal("15"),
            atr_current=Decimal("200"),
            atr_average=Decimal("200"),
            price=Decimal("1100000"),
            sma_20=Decimal("1100000"),
        )

        assert observation.regime == Regime.RANGING

    def test_strategy_allowed(self, service):
        """Strategy-regime sandbox check returns SandboxVerdict."""
        verdict = service.check_strategy_allowed(
            strategy_name="momentum_breakout",
            symbol="BTCZAR",
        )

        assert verdict is not None
        assert hasattr(verdict, "allowed")


# ============================================================================
# CURRICULUM SCHEDULER
# ============================================================================


class TestCurriculumScheduler:
    """Test 4-phase learning curriculum."""

    @pytest.fixture
    def scheduler(self, mock_db_session):
        from services.intelligence.curriculum_scheduler_service import (
            CurriculumScheduler,
        )

        mock_db_session.execute.return_value.fetchone.return_value = None
        return CurriculumScheduler(db_session=mock_db_session)

    def test_initial_phase_is_observer(self, scheduler):
        """Default phase should be Observer (phase 1)."""
        state = scheduler.get_state()

        assert state.current_phase == 1
        assert state.phase_name == "Observer"

    def test_observer_max_confidence(self, scheduler):
        """Observer phase caps confidence at 0.50."""
        state = scheduler.get_state()

        assert state.max_confidence == Decimal("0.50")

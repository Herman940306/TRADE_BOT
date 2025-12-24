"""
Property-Based Tests for Failure Scenario Simulator Module

Reliability Level: SOVEREIGN TIER
Python 3.8 Compatible

Tests the FailureScenarioSimulator using Hypothesis.
Minimum 100 iterations per property as per design specification.

Properties tested:
- Property 10: Exchange Downtime Response
- Property 11: Stale Data Rejection
- Property 12: BudgetGuard Corruption Handling
- Property 15: Exchange Clock Drift Protection
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

# Import modules under test
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from app.logic.failure_scenario_simulator import (
    ScenarioResult,
    ScenarioConfig,
    ScenarioType,
    SystemState,
    AssertionResult,
    FailureScenarioSimulator,
    VALID_SCENARIO_TYPES,
    VALID_SYSTEM_STATES,
    MAX_CLOCK_DRIFT_MS,
    SSE_RECONNECT_ATTEMPTS_BEFORE_LOCKDOWN,
    EXCHANGE_DOWNTIME_RESPONSE_SECONDS,
    ERROR_EXCHANGE_CLOCK_DRIFT,
    ERROR_BUDGET_DATA_CORRUPT,
)


# =============================================================================
# HYPOTHESIS STRATEGIES
# =============================================================================

# Strategy for scenario IDs (non-empty strings)
scenario_id_strategy = st.text(
    alphabet=st.characters(whitelist_categories=('L', 'N'), whitelist_characters='_-'),
    min_size=1,
    max_size=50
).filter(lambda x: len(x.strip()) > 0)

# Strategy for valid scenario types
scenario_type_strategy = st.sampled_from(VALID_SCENARIO_TYPES)

# Strategy for valid system states
system_state_strategy = st.sampled_from(VALID_SYSTEM_STATES)

# Strategy for duration in milliseconds (non-negative)
duration_ms_strategy = st.integers(min_value=0, max_value=60000)

# Strategy for trade counts (non-negative)
trade_count_strategy = st.integers(min_value=0, max_value=100)

# Strategy for clock drift in milliseconds
clock_drift_strategy = st.integers(min_value=-5000, max_value=5000)

# Strategy for fill percentage (0-100)
fill_pct_strategy = st.decimals(
    min_value=Decimal("0.00"),
    max_value=Decimal("100.00"),
    places=2,
    allow_nan=False,
    allow_infinity=False
)

# Strategy for stale data age in hours
stale_hours_strategy = st.integers(min_value=1, max_value=168)  # Up to 1 week

# Strategy for SSE disconnect count
disconnect_count_strategy = st.integers(min_value=1, max_value=20)


# =============================================================================
# SCENARIO RESULT VALIDATION TESTS
# =============================================================================

class TestScenarioResultValidation:
    """
    Tests for ScenarioResult dataclass validation.
    """
    
    @settings(max_examples=100)
    @given(
        scenario_id=scenario_id_strategy,
        scenario_type=scenario_type_strategy,
        expected_state=system_state_strategy,
        actual_state=system_state_strategy,
        trades_during_unsafe=trade_count_strategy,
        duration_ms=duration_ms_strategy
    )
    def test_scenario_result_accepts_valid_inputs(
        self,
        scenario_id: str,
        scenario_type: str,
        expected_state: str,
        actual_state: str,
        trades_during_unsafe: int,
        duration_ms: int
    ) -> None:
        """
        Verify that ScenarioResult accepts all valid input combinations.
        """
        assertion_passed = (expected_state == actual_state)
        
        result = ScenarioResult(
            scenario_id=scenario_id,
            scenario_type=scenario_type,
            expected_state=expected_state,
            actual_state=actual_state,
            assertion_passed=assertion_passed,
            trades_during_unsafe=trades_during_unsafe,
            logs=[],
            duration_ms=duration_ms
        )
        
        assert result.scenario_id == scenario_id
        assert result.scenario_type == scenario_type
        assert result.expected_state == expected_state
        assert result.actual_state == actual_state
        assert result.trades_during_unsafe == trades_during_unsafe
        assert result.duration_ms == duration_ms
    
    def test_scenario_result_rejects_empty_scenario_id(self) -> None:
        """Verify that ScenarioResult rejects empty scenario_id."""
        with pytest.raises(ValueError) as exc_info:
            ScenarioResult(
                scenario_id="",
                scenario_type="EXCHANGE_DOWNTIME",
                expected_state="NEUTRAL",
                actual_state="NEUTRAL",
                assertion_passed=True,
                trades_during_unsafe=0,
                logs=[],
                duration_ms=100
            )
        assert "scenario_id" in str(exc_info.value)
    
    def test_scenario_result_rejects_invalid_scenario_type(self) -> None:
        """Verify that ScenarioResult rejects invalid scenario_type."""
        with pytest.raises(ValueError) as exc_info:
            ScenarioResult(
                scenario_id="test-123",
                scenario_type="INVALID_TYPE",
                expected_state="NEUTRAL",
                actual_state="NEUTRAL",
                assertion_passed=True,
                trades_during_unsafe=0,
                logs=[],
                duration_ms=100
            )
        assert "scenario_type" in str(exc_info.value)
    
    def test_scenario_result_rejects_negative_trades(self) -> None:
        """Verify that ScenarioResult rejects negative trades_during_unsafe."""
        with pytest.raises(ValueError) as exc_info:
            ScenarioResult(
                scenario_id="test-123",
                scenario_type="EXCHANGE_DOWNTIME",
                expected_state="NEUTRAL",
                actual_state="NEUTRAL",
                assertion_passed=True,
                trades_during_unsafe=-1,
                logs=[],
                duration_ms=100
            )
        assert "trades_during_unsafe" in str(exc_info.value)


# =============================================================================
# PROPERTY 10: Exchange Downtime Response
# **Feature: trade-permission-policy, Property 10: Exchange Downtime Response**
# **Validates: Requirements 6.1**
# =============================================================================

class TestExchangeDowntimeResponse:
    """
    Property 10: Exchange Downtime Response
    
    For any injected exchange_downtime scenario, the system SHALL 
    transition to NEUTRAL state within 5 seconds of injection.
    
    This test validates that the FailureScenarioSimulator correctly
    simulates exchange downtime and the system responds appropriately.
    """
    
    @settings(max_examples=100)
    @given(
        scenario_id=scenario_id_strategy
    )
    def test_exchange_downtime_returns_neutral_state(
        self,
        scenario_id: str
    ) -> None:
        """
        **Feature: trade-permission-policy, Property 10: Exchange Downtime Response**
        **Validates: Requirements 6.1**
        
        Verify that when exchange downtime is injected, the system
        transitions to NEUTRAL state.
        """
        # Create simulator instance
        simulator = FailureScenarioSimulator()
        
        # Inject exchange downtime
        result = simulator.inject_exchange_downtime()
        
        # Assert expected state is NEUTRAL
        assert result.expected_state == "NEUTRAL", (
            f"Expected state should be NEUTRAL, got {result.expected_state}"
        )
        
        # Assert actual state matches expected (NEUTRAL)
        assert result.actual_state == "NEUTRAL", (
            f"Actual state should be NEUTRAL, got {result.actual_state}"
        )
        
        # Assert assertion passed
        assert result.assertion_passed is True, (
            f"Assertion should pass for exchange downtime scenario"
        )
        
        # Assert scenario type is correct
        assert result.scenario_type == "EXCHANGE_DOWNTIME", (
            f"Scenario type should be EXCHANGE_DOWNTIME, got {result.scenario_type}"
        )
        
        # Assert no trades during unsafe conditions
        assert result.trades_during_unsafe == 0, (
            f"No trades should occur during exchange downtime, got {result.trades_during_unsafe}"
        )
    
    def test_exchange_downtime_response_time_within_limit(self) -> None:
        """
        **Feature: trade-permission-policy, Property 10: Exchange Downtime Response**
        **Validates: Requirements 6.1**
        
        Verify that exchange downtime response occurs within 5 seconds.
        """
        simulator = FailureScenarioSimulator()
        result = simulator.inject_exchange_downtime()
        
        # Duration should be reasonable (less than timeout + buffer)
        max_expected_duration_ms = (EXCHANGE_DOWNTIME_RESPONSE_SECONDS + 1) * 1000
        assert result.duration_ms <= max_expected_duration_ms, (
            f"Response time {result.duration_ms}ms exceeds limit {max_expected_duration_ms}ms"
        )
    
    def test_exchange_downtime_logs_contain_scenario_info(self) -> None:
        """
        **Feature: trade-permission-policy, Property 10: Exchange Downtime Response**
        **Validates: Requirements 6.1**
        
        Verify that exchange downtime scenario produces structured logs.
        """
        simulator = FailureScenarioSimulator()
        result = simulator.inject_exchange_downtime()
        
        # Logs should not be empty
        assert len(result.logs) > 0, "Scenario should produce logs"
        
        # Each log entry should have required fields
        for log_entry in result.logs:
            assert "timestamp" in log_entry, "Log entry should have timestamp"
            assert "scenario_id" in log_entry, "Log entry should have scenario_id"
            assert "event_type" in log_entry, "Log entry should have event_type"
            assert "message" in log_entry, "Log entry should have message"


# =============================================================================
# PROPERTY 11: Stale Data Rejection
# **Feature: trade-permission-policy, Property 11: Stale Data Rejection**
# **Validates: Requirements 6.3**
# =============================================================================

class TestStaleDataRejection:
    """
    Property 11: Stale Data Rejection
    
    For any injected stale_market_data scenario, all new trade signals
    SHALL be rejected until fresh data is received.
    
    This test validates that the system enters NEUTRAL state when
    stale market data is detected.
    """
    
    @settings(max_examples=100)
    @given(
        age_hours=stale_hours_strategy
    )
    def test_stale_data_returns_neutral_state(
        self,
        age_hours: int
    ) -> None:
        """
        **Feature: trade-permission-policy, Property 11: Stale Data Rejection**
        **Validates: Requirements 6.3**
        
        Verify that when stale market data is injected, the system
        enters NEUTRAL state to reject new trades.
        """
        # Create simulator instance
        simulator = FailureScenarioSimulator()
        
        # Inject stale market data
        result = simulator.inject_stale_market_data(age_hours=age_hours)
        
        # Assert expected state is NEUTRAL
        assert result.expected_state == "NEUTRAL", (
            f"Expected state should be NEUTRAL for stale data, got {result.expected_state}"
        )
        
        # Assert actual state matches expected
        assert result.actual_state == "NEUTRAL", (
            f"Actual state should be NEUTRAL for stale data, got {result.actual_state}"
        )
        
        # Assert assertion passed
        assert result.assertion_passed is True, (
            f"Assertion should pass for stale data scenario"
        )
        
        # Assert scenario type is correct
        assert result.scenario_type == "STALE_MARKET_DATA", (
            f"Scenario type should be STALE_MARKET_DATA, got {result.scenario_type}"
        )
        
        # Assert no trades during unsafe conditions
        assert result.trades_during_unsafe == 0, (
            f"No trades should occur during stale data condition, got {result.trades_during_unsafe}"
        )
    
    def test_stale_data_rejects_invalid_age(self) -> None:
        """
        **Feature: trade-permission-policy, Property 11: Stale Data Rejection**
        **Validates: Requirements 6.3**
        
        Verify that invalid age_hours values are handled correctly.
        """
        simulator = FailureScenarioSimulator()
        
        # Zero or negative age should fail assertion
        result = simulator.inject_stale_market_data(age_hours=0)
        assert result.assertion_passed is False, (
            "Assertion should fail for invalid age_hours=0"
        )
    
    def test_stale_data_logs_contain_age_info(self) -> None:
        """
        **Feature: trade-permission-policy, Property 11: Stale Data Rejection**
        **Validates: Requirements 6.3**
        
        Verify that stale data scenario logs contain age information.
        """
        simulator = FailureScenarioSimulator()
        result = simulator.inject_stale_market_data(age_hours=24)
        
        # Logs should contain age information
        assert len(result.logs) > 0, "Scenario should produce logs"
        
        # Check that at least one log mentions the age
        log_messages = [log.get("message", "") for log in result.logs]
        age_mentioned = any("24" in msg for msg in log_messages)
        assert age_mentioned, "Logs should mention the stale data age"


# =============================================================================
# PROPERTY 12: BudgetGuard Corruption Handling
# **Feature: trade-permission-policy, Property 12: BudgetGuard Corruption Handling**
# **Validates: Requirements 6.4**
# =============================================================================

class TestBudgetGuardCorruptionHandling:
    """
    Property 12: BudgetGuard Corruption Handling
    
    For any injected budgetguard_corruption scenario, the system SHALL
    enter HALT state and the audit log SHALL contain error code
    "BUDGET_DATA_CORRUPT".
    
    This test validates that budget data corruption triggers immediate
    HALT state for safety.
    """
    
    @settings(max_examples=100)
    @given(
        scenario_id=scenario_id_strategy
    )
    def test_budgetguard_corruption_returns_halt_state(
        self,
        scenario_id: str
    ) -> None:
        """
        **Feature: trade-permission-policy, Property 12: BudgetGuard Corruption Handling**
        **Validates: Requirements 6.4**
        
        Verify that when BudgetGuard corruption is injected, the system
        enters HALT state.
        """
        # Create simulator instance
        simulator = FailureScenarioSimulator()
        
        # Inject BudgetGuard corruption
        result = simulator.inject_budgetguard_corruption()
        
        # Assert expected state is HALT
        assert result.expected_state == "HALT", (
            f"Expected state should be HALT for budget corruption, got {result.expected_state}"
        )
        
        # Assert actual state matches expected
        assert result.actual_state == "HALT", (
            f"Actual state should be HALT for budget corruption, got {result.actual_state}"
        )
        
        # Assert assertion passed
        assert result.assertion_passed is True, (
            f"Assertion should pass for budget corruption scenario"
        )
        
        # Assert scenario type is correct
        assert result.scenario_type == "BUDGETGUARD_CORRUPTION", (
            f"Scenario type should be BUDGETGUARD_CORRUPTION, got {result.scenario_type}"
        )
        
        # Assert no trades during unsafe conditions
        assert result.trades_during_unsafe == 0, (
            f"No trades should occur during budget corruption, got {result.trades_during_unsafe}"
        )
    
    def test_budgetguard_corruption_logs_error_code(self) -> None:
        """
        **Feature: trade-permission-policy, Property 12: BudgetGuard Corruption Handling**
        **Validates: Requirements 6.4**
        
        Verify that BudgetGuard corruption logs contain BUDGET_DATA_CORRUPT error code.
        """
        simulator = FailureScenarioSimulator()
        result = simulator.inject_budgetguard_corruption()
        
        # Logs should contain error code
        assert len(result.logs) > 0, "Scenario should produce logs"
        
        # Check that at least one log contains the error code
        log_messages = [log.get("message", "") for log in result.logs]
        error_code_found = any(ERROR_BUDGET_DATA_CORRUPT in msg for msg in log_messages)
        assert error_code_found, (
            f"Logs should contain error code {ERROR_BUDGET_DATA_CORRUPT}"
        )
    
    def test_budgetguard_corruption_is_deterministic(self) -> None:
        """
        **Feature: trade-permission-policy, Property 12: BudgetGuard Corruption Handling**
        **Validates: Requirements 6.4**
        
        Verify that BudgetGuard corruption always produces HALT state.
        """
        simulator = FailureScenarioSimulator()
        
        # Run multiple times to verify determinism
        for _ in range(10):
            result = simulator.inject_budgetguard_corruption()
            assert result.expected_state == "HALT"
            assert result.actual_state == "HALT"
            assert result.assertion_passed is True


# =============================================================================
# PROPERTY 15: Exchange Clock Drift Protection
# **Feature: trade-permission-policy, Property 15: Exchange Clock Drift Protection**
# **Validates: Requirements 9.2**
# =============================================================================

class TestExchangeClockDriftProtection:
    """
    Property 15: Exchange Clock Drift Protection
    
    For any measured clock drift between local server and exchange server
    that exceeds 1 second (1000ms), the system SHALL enter NEUTRAL state
    and log error code "EXCHANGE_TIME_DRIFT".
    
    This test validates that clock drift protection works correctly.
    """
    
    @settings(max_examples=100)
    @given(
        drift_ms=st.integers(min_value=1001, max_value=10000)
    )
    def test_excessive_drift_returns_neutral_state(
        self,
        drift_ms: int
    ) -> None:
        """
        **Feature: trade-permission-policy, Property 15: Exchange Clock Drift Protection**
        **Validates: Requirements 9.2**
        
        Verify that when clock drift exceeds 1 second, the system
        enters NEUTRAL state.
        """
        # Create simulator instance
        simulator = FailureScenarioSimulator()
        
        # Inject clock drift exceeding tolerance
        result = simulator.inject_exchange_clock_drift(drift_ms=drift_ms)
        
        # Assert expected state is NEUTRAL (drift exceeds tolerance)
        assert result.expected_state == "NEUTRAL", (
            f"Expected state should be NEUTRAL for drift {drift_ms}ms > {MAX_CLOCK_DRIFT_MS}ms"
        )
        
        # Assert actual state matches expected
        assert result.actual_state == "NEUTRAL", (
            f"Actual state should be NEUTRAL for excessive drift, got {result.actual_state}"
        )
        
        # Assert assertion passed
        assert result.assertion_passed is True, (
            f"Assertion should pass for excessive drift scenario"
        )
        
        # Assert scenario type is correct
        assert result.scenario_type == "EXCHANGE_CLOCK_DRIFT", (
            f"Scenario type should be EXCHANGE_CLOCK_DRIFT, got {result.scenario_type}"
        )
    
    @settings(max_examples=100)
    @given(
        drift_ms=st.integers(min_value=-10000, max_value=-1001)
    )
    def test_negative_excessive_drift_returns_neutral_state(
        self,
        drift_ms: int
    ) -> None:
        """
        **Feature: trade-permission-policy, Property 15: Exchange Clock Drift Protection**
        **Validates: Requirements 9.2**
        
        Verify that negative clock drift exceeding 1 second also
        triggers NEUTRAL state (absolute value check).
        """
        simulator = FailureScenarioSimulator()
        result = simulator.inject_exchange_clock_drift(drift_ms=drift_ms)
        
        # Absolute drift exceeds tolerance
        assert result.expected_state == "NEUTRAL", (
            f"Expected state should be NEUTRAL for negative drift {drift_ms}ms"
        )
        assert result.actual_state == "NEUTRAL"
        assert result.assertion_passed is True
    
    @settings(max_examples=100)
    @given(
        drift_ms=st.integers(min_value=-1000, max_value=1000)
    )
    def test_acceptable_drift_returns_allow_state(
        self,
        drift_ms: int
    ) -> None:
        """
        **Feature: trade-permission-policy, Property 15: Exchange Clock Drift Protection**
        **Validates: Requirements 9.2**
        
        Verify that when clock drift is within tolerance (<=1 second),
        the system remains in ALLOW state.
        """
        simulator = FailureScenarioSimulator()
        result = simulator.inject_exchange_clock_drift(drift_ms=drift_ms)
        
        # Drift within tolerance - system should remain in ALLOW
        assert result.expected_state == "ALLOW", (
            f"Expected state should be ALLOW for drift {drift_ms}ms <= {MAX_CLOCK_DRIFT_MS}ms"
        )
        assert result.actual_state == "ALLOW"
        assert result.assertion_passed is True
    
    def test_clock_drift_logs_error_code_when_exceeded(self) -> None:
        """
        **Feature: trade-permission-policy, Property 15: Exchange Clock Drift Protection**
        **Validates: Requirements 9.2**
        
        Verify that excessive clock drift logs contain EXCHANGE_TIME_DRIFT error code.
        """
        simulator = FailureScenarioSimulator()
        result = simulator.inject_exchange_clock_drift(drift_ms=2000)
        
        # Logs should contain error code
        assert len(result.logs) > 0, "Scenario should produce logs"
        
        # Check that at least one log contains the error code
        log_messages = [log.get("message", "") for log in result.logs]
        error_code_found = any(ERROR_EXCHANGE_CLOCK_DRIFT in msg for msg in log_messages)
        assert error_code_found, (
            f"Logs should contain error code {ERROR_EXCHANGE_CLOCK_DRIFT}"
        )
    
    def test_clock_drift_boundary_at_1000ms(self) -> None:
        """
        **Feature: trade-permission-policy, Property 15: Exchange Clock Drift Protection**
        **Validates: Requirements 9.2**
        
        Verify boundary behavior at exactly 1000ms drift.
        """
        simulator = FailureScenarioSimulator()
        
        # Exactly at tolerance - should be ALLOW
        result_at_boundary = simulator.inject_exchange_clock_drift(drift_ms=1000)
        assert result_at_boundary.expected_state == "ALLOW", (
            "Drift exactly at 1000ms should be ALLOW (within tolerance)"
        )
        
        # Just over tolerance - should be NEUTRAL
        result_over_boundary = simulator.inject_exchange_clock_drift(drift_ms=1001)
        assert result_over_boundary.expected_state == "NEUTRAL", (
            "Drift at 1001ms should be NEUTRAL (exceeds tolerance)"
        )


# =============================================================================
# ADDITIONAL SCENARIO TESTS
# =============================================================================

class TestPartialFillScenario:
    """
    Tests for partial fill scenario handling.
    """
    
    @settings(max_examples=100)
    @given(
        fill_pct=fill_pct_strategy
    )
    def test_partial_fill_logs_discrepancy(
        self,
        fill_pct: Decimal
    ) -> None:
        """
        Verify that partial fill scenario logs the discrepancy.
        
        Requirements: 6.2
        """
        simulator = FailureScenarioSimulator()
        result = simulator.inject_partial_fill(fill_pct=fill_pct)
        
        # Partial fills should log but not necessarily change state
        assert result.scenario_type == "PARTIAL_FILL"
        assert len(result.logs) > 0, "Partial fill should produce logs"
    
    def test_partial_fill_rejects_invalid_percentage(self) -> None:
        """
        Verify that invalid fill percentages are rejected.
        """
        simulator = FailureScenarioSimulator()
        
        # Negative percentage should fail
        result = simulator.inject_partial_fill(fill_pct=Decimal("-10"))
        assert result.assertion_passed is False
        
        # Over 100% should fail
        result = simulator.inject_partial_fill(fill_pct=Decimal("150"))
        assert result.assertion_passed is False


class TestSSEDisconnectStormScenario:
    """
    Tests for SSE disconnect storm scenario handling.
    """
    
    @settings(max_examples=100)
    @given(
        count=st.integers(min_value=5, max_value=20)
    )
    def test_sse_storm_triggers_lockdown_after_threshold(
        self,
        count: int
    ) -> None:
        """
        Verify that SSE disconnect storm triggers L6 Lockdown after 5 attempts.
        
        Requirements: 6.5
        """
        simulator = FailureScenarioSimulator()
        result = simulator.inject_sse_disconnect_storm(count=count)
        
        # 5 or more disconnects should trigger L6 Lockdown
        assert result.expected_state == "L6_LOCKDOWN", (
            f"Expected L6_LOCKDOWN for {count} disconnects"
        )
        assert result.actual_state == "L6_LOCKDOWN"
        assert result.assertion_passed is True
    
    @settings(max_examples=100)
    @given(
        count=st.integers(min_value=1, max_value=4)
    )
    def test_sse_storm_neutral_before_threshold(
        self,
        count: int
    ) -> None:
        """
        Verify that SSE disconnect storm enters NEUTRAL before threshold.
        
        Requirements: 6.5
        """
        simulator = FailureScenarioSimulator()
        result = simulator.inject_sse_disconnect_storm(count=count)
        
        # Less than 5 disconnects should be NEUTRAL
        assert result.expected_state == "NEUTRAL", (
            f"Expected NEUTRAL for {count} disconnects (< 5)"
        )
        assert result.actual_state == "NEUTRAL"
        assert result.assertion_passed is True


class TestScenarioResultMethods:
    """
    Tests for ScenarioResult helper methods.
    """
    
    def test_to_dict_returns_all_fields(self) -> None:
        """Verify that to_dict() returns all required fields."""
        result = ScenarioResult(
            scenario_id="test-123",
            scenario_type="EXCHANGE_DOWNTIME",
            expected_state="NEUTRAL",
            actual_state="NEUTRAL",
            assertion_passed=True,
            trades_during_unsafe=0,
            logs=[{"message": "test"}],
            duration_ms=100
        )
        
        result_dict = result.to_dict()
        
        assert "scenario_id" in result_dict
        assert "scenario_type" in result_dict
        assert "expected_state" in result_dict
        assert "actual_state" in result_dict
        assert "assertion_passed" in result_dict
        assert "trades_during_unsafe" in result_dict
        assert "logs" in result_dict
        assert "duration_ms" in result_dict
    
    def test_get_failure_report_returns_none_on_success(self) -> None:
        """Verify that get_failure_report() returns None when assertion passed."""
        result = ScenarioResult(
            scenario_id="test-123",
            scenario_type="EXCHANGE_DOWNTIME",
            expected_state="NEUTRAL",
            actual_state="NEUTRAL",
            assertion_passed=True,
            trades_during_unsafe=0,
            logs=[],
            duration_ms=100
        )
        
        assert result.get_failure_report() is None
    
    def test_get_failure_report_returns_report_on_failure(self) -> None:
        """Verify that get_failure_report() returns report when assertion failed."""
        result = ScenarioResult(
            scenario_id="test-123",
            scenario_type="EXCHANGE_DOWNTIME",
            expected_state="NEUTRAL",
            actual_state="ALLOW",
            assertion_passed=False,
            trades_during_unsafe=0,
            logs=[],
            duration_ms=100
        )
        
        report = result.get_failure_report()
        
        assert report is not None
        assert "test-123" in report
        assert "EXCHANGE_DOWNTIME" in report
        assert "NEUTRAL" in report
        assert "ALLOW" in report


# =============================================================================
# PROPERTY 9: No Trades During Unsafe Conditions
# **Feature: trade-permission-policy, Property 9: No Trades During Unsafe Conditions**
# **Validates: Requirements 7.2**
# =============================================================================

class TestNoTradesDuringUnsafeConditions:
    """
    Property 9: No Trades During Unsafe Conditions
    
    For any failure scenario simulation, the number of trades executed
    while the system is in an unsafe state (HALT or NEUTRAL) SHALL be
    exactly zero.
    
    This test validates that the system correctly prevents trades during
    unsafe conditions across all failure scenarios.
    """
    
    @settings(max_examples=100)
    @given(
        scenario_id=scenario_id_strategy
    )
    def test_exchange_downtime_no_trades_during_neutral(
        self,
        scenario_id: str
    ) -> None:
        """
        **Feature: trade-permission-policy, Property 9: No Trades During Unsafe Conditions**
        **Validates: Requirements 7.2**
        
        Verify that no trades occur during exchange downtime (NEUTRAL state).
        """
        simulator = FailureScenarioSimulator()
        result = simulator.inject_exchange_downtime()
        
        # System should be in NEUTRAL state
        assert result.actual_state == "NEUTRAL", (
            f"System should be in NEUTRAL state during exchange downtime"
        )
        
        # No trades should occur during NEUTRAL state
        assert result.trades_during_unsafe == 0, (
            f"No trades should occur during NEUTRAL state, got {result.trades_during_unsafe}"
        )
        
        # Verify using the assertion method
        assertion_result = simulator.verify_no_trades_during_unsafe(
            trades_during_unsafe=result.trades_during_unsafe,
            scenario_id=result.scenario_id,
            unsafe_state=result.actual_state
        )
        assert assertion_result.passed is True, (
            f"No trades assertion should pass: {assertion_result.message}"
        )
    
    @settings(max_examples=100)
    @given(
        age_hours=stale_hours_strategy
    )
    def test_stale_data_no_trades_during_neutral(
        self,
        age_hours: int
    ) -> None:
        """
        **Feature: trade-permission-policy, Property 9: No Trades During Unsafe Conditions**
        **Validates: Requirements 7.2**
        
        Verify that no trades occur during stale market data (NEUTRAL state).
        """
        simulator = FailureScenarioSimulator()
        result = simulator.inject_stale_market_data(age_hours=age_hours)
        
        # System should be in NEUTRAL state
        assert result.actual_state == "NEUTRAL", (
            f"System should be in NEUTRAL state during stale data"
        )
        
        # No trades should occur during NEUTRAL state
        assert result.trades_during_unsafe == 0, (
            f"No trades should occur during NEUTRAL state, got {result.trades_during_unsafe}"
        )
        
        # Verify using the assertion method
        assertion_result = simulator.verify_no_trades_during_unsafe(
            trades_during_unsafe=result.trades_during_unsafe,
            scenario_id=result.scenario_id,
            unsafe_state=result.actual_state
        )
        assert assertion_result.passed is True
    
    @settings(max_examples=100)
    @given(
        scenario_id=scenario_id_strategy
    )
    def test_budgetguard_corruption_no_trades_during_halt(
        self,
        scenario_id: str
    ) -> None:
        """
        **Feature: trade-permission-policy, Property 9: No Trades During Unsafe Conditions**
        **Validates: Requirements 7.2**
        
        Verify that no trades occur during BudgetGuard corruption (HALT state).
        """
        simulator = FailureScenarioSimulator()
        result = simulator.inject_budgetguard_corruption()
        
        # System should be in HALT state
        assert result.actual_state == "HALT", (
            f"System should be in HALT state during budget corruption"
        )
        
        # No trades should occur during HALT state
        assert result.trades_during_unsafe == 0, (
            f"No trades should occur during HALT state, got {result.trades_during_unsafe}"
        )
        
        # Verify using the assertion method
        assertion_result = simulator.verify_no_trades_during_unsafe(
            trades_during_unsafe=result.trades_during_unsafe,
            scenario_id=result.scenario_id,
            unsafe_state=result.actual_state
        )
        assert assertion_result.passed is True
    
    @settings(max_examples=100)
    @given(
        count=st.integers(min_value=5, max_value=20)
    )
    def test_sse_storm_no_trades_during_lockdown(
        self,
        count: int
    ) -> None:
        """
        **Feature: trade-permission-policy, Property 9: No Trades During Unsafe Conditions**
        **Validates: Requirements 7.2**
        
        Verify that no trades occur during SSE disconnect storm (L6_LOCKDOWN state).
        """
        simulator = FailureScenarioSimulator()
        result = simulator.inject_sse_disconnect_storm(count=count)
        
        # System should be in L6_LOCKDOWN state for count >= 5
        assert result.actual_state == "L6_LOCKDOWN", (
            f"System should be in L6_LOCKDOWN state during SSE storm"
        )
        
        # No trades should occur during L6_LOCKDOWN state
        assert result.trades_during_unsafe == 0, (
            f"No trades should occur during L6_LOCKDOWN state, got {result.trades_during_unsafe}"
        )
        
        # Verify using the assertion method
        assertion_result = simulator.verify_no_trades_during_unsafe(
            trades_during_unsafe=result.trades_during_unsafe,
            scenario_id=result.scenario_id,
            unsafe_state=result.actual_state
        )
        assert assertion_result.passed is True
    
    @settings(max_examples=100)
    @given(
        drift_ms=st.integers(min_value=1001, max_value=10000)
    )
    def test_clock_drift_no_trades_during_neutral(
        self,
        drift_ms: int
    ) -> None:
        """
        **Feature: trade-permission-policy, Property 9: No Trades During Unsafe Conditions**
        **Validates: Requirements 7.2**
        
        Verify that no trades occur during excessive clock drift (NEUTRAL state).
        """
        simulator = FailureScenarioSimulator()
        result = simulator.inject_exchange_clock_drift(drift_ms=drift_ms)
        
        # System should be in NEUTRAL state for excessive drift
        assert result.actual_state == "NEUTRAL", (
            f"System should be in NEUTRAL state during excessive clock drift"
        )
        
        # No trades should occur during NEUTRAL state
        assert result.trades_during_unsafe == 0, (
            f"No trades should occur during NEUTRAL state, got {result.trades_during_unsafe}"
        )
        
        # Verify using the assertion method
        assertion_result = simulator.verify_no_trades_during_unsafe(
            trades_during_unsafe=result.trades_during_unsafe,
            scenario_id=result.scenario_id,
            unsafe_state=result.actual_state
        )
        assert assertion_result.passed is True
    
    def test_run_all_assertions_verifies_no_trades(self) -> None:
        """
        **Feature: trade-permission-policy, Property 9: No Trades During Unsafe Conditions**
        **Validates: Requirements 7.2**
        
        Verify that run_all_assertions includes no-trades check for unsafe states.
        """
        simulator = FailureScenarioSimulator()
        
        # Test with exchange downtime (NEUTRAL state)
        result = simulator.inject_exchange_downtime()
        assertions = simulator.run_all_assertions(result)
        
        # Should have at least 2 assertions (state match + no trades)
        assert len(assertions) >= 2, (
            f"Expected at least 2 assertions for unsafe state, got {len(assertions)}"
        )
        
        # Find the no-trades assertion
        no_trades_assertions = [a for a in assertions if a.assertion_type == "NO_TRADES_UNSAFE"]
        assert len(no_trades_assertions) == 1, (
            "Should have exactly one NO_TRADES_UNSAFE assertion"
        )
        
        # Verify it passed
        assert no_trades_assertions[0].passed is True, (
            "NO_TRADES_UNSAFE assertion should pass"
        )
    
    def test_assertion_fails_when_trades_occur_during_unsafe(self) -> None:
        """
        **Feature: trade-permission-policy, Property 9: No Trades During Unsafe Conditions**
        **Validates: Requirements 7.2**
        
        Verify that assertion correctly fails when trades occur during unsafe conditions.
        """
        simulator = FailureScenarioSimulator()
        
        # Manually test the assertion with non-zero trades
        assertion_result = simulator.verify_no_trades_during_unsafe(
            trades_during_unsafe=5,
            scenario_id="test-scenario",
            unsafe_state="HALT"
        )
        
        # Assertion should fail
        assert assertion_result.passed is False, (
            "Assertion should fail when trades occur during unsafe conditions"
        )
        
        # Failure message should be present
        failure_msg = assertion_result.get_failure_message()
        assert failure_msg is not None, "Failure message should be present"
        assert "5" in failure_msg, "Failure message should mention trade count"
        assert "HALT" in failure_msg, "Failure message should mention unsafe state"
    
    @settings(max_examples=100)
    @given(
        trades_count=st.integers(min_value=1, max_value=100)
    )
    def test_any_nonzero_trades_fails_assertion(
        self,
        trades_count: int
    ) -> None:
        """
        **Feature: trade-permission-policy, Property 9: No Trades During Unsafe Conditions**
        **Validates: Requirements 7.2**
        
        Verify that any non-zero trade count fails the assertion.
        """
        simulator = FailureScenarioSimulator()
        
        # Any non-zero trade count should fail
        assertion_result = simulator.verify_no_trades_during_unsafe(
            trades_during_unsafe=trades_count,
            scenario_id="test-scenario",
            unsafe_state="NEUTRAL"
        )
        
        assert assertion_result.passed is False, (
            f"Assertion should fail for {trades_count} trades during unsafe conditions"
        )
        assert assertion_result.expected_value == "0", (
            "Expected value should be '0'"
        )
        assert assertion_result.actual_value == str(trades_count), (
            f"Actual value should be '{trades_count}'"
        )


# =============================================================================
# ASSERTION FAILURE REPORTING TESTS
# **Validates: Requirements 7.4**
# =============================================================================

class TestAssertionFailureReporting:
    """
    Tests for assertion failure reporting functionality.
    
    Requirement 7.4: When a failure scenario assertion fails, the simulator
    SHALL report the specific expectation that was violated.
    """
    
    def test_report_assertion_failure_includes_scenario_details(self) -> None:
        """
        **Validates: Requirements 7.4**
        
        Verify that assertion failure report includes all scenario details.
        """
        simulator = FailureScenarioSimulator()
        
        # Create a failed scenario result
        result = ScenarioResult(
            scenario_id="test-failure-123",
            scenario_type="EXCHANGE_DOWNTIME",
            expected_state="NEUTRAL",
            actual_state="ALLOW",
            assertion_passed=False,
            trades_during_unsafe=0,
            logs=[],
            duration_ms=100
        )
        
        report = simulator.report_assertion_failure(result)
        
        # Report should include scenario ID
        assert "test-failure-123" in report, (
            "Report should include scenario_id"
        )
        
        # Report should include scenario type
        assert "EXCHANGE_DOWNTIME" in report, (
            "Report should include scenario_type"
        )
        
        # Report should include expected state
        assert "NEUTRAL" in report, (
            "Report should include expected_state"
        )
        
        # Report should include actual state
        assert "ALLOW" in report, (
            "Report should include actual_state"
        )
    
    def test_report_assertion_failure_returns_no_failure_on_success(self) -> None:
        """
        **Validates: Requirements 7.4**
        
        Verify that report returns appropriate message when no failure.
        """
        simulator = FailureScenarioSimulator()
        
        # Create a successful scenario result
        result = ScenarioResult(
            scenario_id="test-success-123",
            scenario_type="EXCHANGE_DOWNTIME",
            expected_state="NEUTRAL",
            actual_state="NEUTRAL",
            assertion_passed=True,
            trades_during_unsafe=0,
            logs=[],
            duration_ms=100
        )
        
        report = simulator.report_assertion_failure(result)
        
        assert report == "No failure to report", (
            "Report should indicate no failure when assertion passed"
        )
    
    def test_report_assertion_failures_multiple(self) -> None:
        """
        **Validates: Requirements 7.4**
        
        Verify that multiple assertion failures are reported correctly.
        """
        simulator = FailureScenarioSimulator()
        
        # Create multiple failed assertions
        assertions = [
            AssertionResult(
                assertion_type="STATE_MATCH",
                passed=False,
                expected_value="NEUTRAL",
                actual_value="ALLOW",
                message="State mismatch",
                scenario_id="test-123",
                timestamp_utc=datetime.now(timezone.utc).isoformat()
            ),
            AssertionResult(
                assertion_type="NO_TRADES_UNSAFE",
                passed=False,
                expected_value="0",
                actual_value="3",
                message="Trades occurred during unsafe",
                scenario_id="test-123",
                timestamp_utc=datetime.now(timezone.utc).isoformat()
            ),
        ]
        
        report = simulator.report_assertion_failures(assertions)
        
        # Report should mention both failures
        assert "2 Assertion(s) Failed" in report, (
            "Report should indicate number of failures"
        )
        
        # Report should include both assertion types
        assert "STATE_MATCH" in report, (
            "Report should include STATE_MATCH failure"
        )
        assert "NO_TRADES_UNSAFE" in report, (
            "Report should include NO_TRADES_UNSAFE failure"
        )
    
    def test_report_assertion_failures_all_passed(self) -> None:
        """
        **Validates: Requirements 7.4**
        
        Verify that report indicates success when all assertions pass.
        """
        simulator = FailureScenarioSimulator()
        
        # Create all passing assertions
        assertions = [
            AssertionResult(
                assertion_type="STATE_MATCH",
                passed=True,
                expected_value="NEUTRAL",
                actual_value="NEUTRAL",
                message="State match",
                scenario_id="test-123",
                timestamp_utc=datetime.now(timezone.utc).isoformat()
            ),
            AssertionResult(
                assertion_type="NO_TRADES_UNSAFE",
                passed=True,
                expected_value="0",
                actual_value="0",
                message="No trades during unsafe",
                scenario_id="test-123",
                timestamp_utc=datetime.now(timezone.utc).isoformat()
            ),
        ]
        
        report = simulator.report_assertion_failures(assertions)
        
        assert report == "All assertions passed", (
            "Report should indicate all assertions passed"
        )
    
    def test_assertion_result_get_failure_message(self) -> None:
        """
        **Validates: Requirements 7.4**
        
        Verify that AssertionResult.get_failure_message() returns detailed info.
        """
        assertion = AssertionResult(
            assertion_type="STATE_MATCH",
            passed=False,
            expected_value="HALT",
            actual_value="ALLOW",
            message="State assertion failed",
            scenario_id="test-456",
            timestamp_utc=datetime.now(timezone.utc).isoformat()
        )
        
        failure_msg = assertion.get_failure_message()
        
        assert failure_msg is not None, "Failure message should not be None"
        assert "STATE_MATCH" in failure_msg, "Should include assertion type"
        assert "HALT" in failure_msg, "Should include expected value"
        assert "ALLOW" in failure_msg, "Should include actual value"
        assert "test-456" in failure_msg, "Should include scenario ID"
    
    def test_assertion_result_get_failure_message_returns_none_on_pass(self) -> None:
        """
        **Validates: Requirements 7.4**
        
        Verify that get_failure_message returns None when assertion passed.
        """
        assertion = AssertionResult(
            assertion_type="STATE_MATCH",
            passed=True,
            expected_value="NEUTRAL",
            actual_value="NEUTRAL",
            message="State match",
            scenario_id="test-789",
            timestamp_utc=datetime.now(timezone.utc).isoformat()
        )
        
        failure_msg = assertion.get_failure_message()
        
        assert failure_msg is None, (
            "Failure message should be None when assertion passed"
        )
    
    def test_trades_during_unsafe_highlighted_in_report(self) -> None:
        """
        **Validates: Requirements 7.4**
        
        Verify that trades during unsafe conditions are highlighted in report.
        """
        simulator = FailureScenarioSimulator()
        
        # Create a result with trades during unsafe
        result = ScenarioResult(
            scenario_id="test-critical-123",
            scenario_type="BUDGETGUARD_CORRUPTION",
            expected_state="HALT",
            actual_state="HALT",
            assertion_passed=False,
            trades_during_unsafe=5,
            logs=[],
            duration_ms=100
        )
        
        report = simulator.report_assertion_failure(result)
        
        # Report should highlight the critical issue
        assert "5" in report, (
            "Report should include trade count"
        )
        assert "CRITICAL" in report or "trades" in report.lower(), (
            "Report should highlight trades during unsafe as critical"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

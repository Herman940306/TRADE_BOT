"""
Unit Tests for HITL Trade Lifecycle State Machine

Reliability Level: SOVEREIGN TIER
Python 3.8 Compatible

Tests the HITL trade lifecycle state machine:
- VALID_TRANSITIONS constant
- validate_transition() function
- transition_trade() function

**Feature: hitl-approval-gateway, Task 3: Trade Lifecycle State Machine**
**Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 1.6**
"""

import pytest
import uuid
from typing import Dict, List, Tuple

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from services.hitl_state_machine import (
    VALID_TRANSITIONS,
    TERMINAL_STATES,
    VALID_STATES,
    HITLTradeState,
    HITLStateErrorCode,
    validate_transition,
    transition_trade,
    get_valid_transitions,
    is_terminal_state,
    is_valid_state,
)


# =============================================================================
# Test VALID_TRANSITIONS Constant
# =============================================================================

class TestValidTransitionsConstant:
    """
    Test the VALID_TRANSITIONS constant.
    
    **Feature: hitl-approval-gateway, Task 3.1: Define VALID_TRANSITIONS constant**
    **Validates: Requirements 1.1, 1.2, 1.3, 1.4**
    """
    
    def test_pending_transitions_to_awaiting_approval(self) -> None:
        """PENDING should only transition to AWAITING_APPROVAL."""
        assert VALID_TRANSITIONS["PENDING"] == ["AWAITING_APPROVAL"]
    
    def test_awaiting_approval_transitions(self) -> None:
        """AWAITING_APPROVAL should transition to ACCEPTED or REJECTED."""
        targets = VALID_TRANSITIONS["AWAITING_APPROVAL"]
        assert "ACCEPTED" in targets
        assert "REJECTED" in targets
        assert len(targets) == 2
    
    def test_accepted_transitions_to_filled(self) -> None:
        """ACCEPTED should only transition to FILLED."""
        assert VALID_TRANSITIONS["ACCEPTED"] == ["FILLED"]
    
    def test_filled_transitions_to_closed(self) -> None:
        """FILLED should only transition to CLOSED."""
        assert VALID_TRANSITIONS["FILLED"] == ["CLOSED"]
    
    def test_closed_transitions_to_settled(self) -> None:
        """CLOSED should only transition to SETTLED."""
        assert VALID_TRANSITIONS["CLOSED"] == ["SETTLED"]
    
    def test_settled_is_terminal(self) -> None:
        """SETTLED should have no outbound transitions (terminal)."""
        assert VALID_TRANSITIONS["SETTLED"] == []
    
    def test_rejected_is_terminal(self) -> None:
        """REJECTED should have no outbound transitions (terminal)."""
        assert VALID_TRANSITIONS["REJECTED"] == []
    
    def test_all_states_defined(self) -> None:
        """All HITLTradeState values should be in VALID_TRANSITIONS."""
        for state in HITLTradeState:
            assert state.value in VALID_TRANSITIONS


# =============================================================================
# Test validate_transition() Function
# =============================================================================

class TestValidateTransition:
    """
    Test the validate_transition() function.
    
    **Feature: hitl-approval-gateway, Task 3.2: Implement validate_transition() function**
    **Validates: Requirements 1.5**
    """
    
    def test_valid_pending_to_awaiting_approval(self) -> None:
        """PENDING -> AWAITING_APPROVAL should be valid."""
        is_valid, error = validate_transition(
            "PENDING", "AWAITING_APPROVAL", "test-corr-id"
        )
        assert is_valid is True
        assert error is None
    
    def test_valid_awaiting_approval_to_accepted(self) -> None:
        """AWAITING_APPROVAL -> ACCEPTED should be valid."""
        is_valid, error = validate_transition(
            "AWAITING_APPROVAL", "ACCEPTED", "test-corr-id"
        )
        assert is_valid is True
        assert error is None
    
    def test_valid_awaiting_approval_to_rejected(self) -> None:
        """AWAITING_APPROVAL -> REJECTED should be valid."""
        is_valid, error = validate_transition(
            "AWAITING_APPROVAL", "REJECTED", "test-corr-id"
        )
        assert is_valid is True
        assert error is None
    
    def test_valid_accepted_to_filled(self) -> None:
        """ACCEPTED -> FILLED should be valid."""
        is_valid, error = validate_transition(
            "ACCEPTED", "FILLED", "test-corr-id"
        )
        assert is_valid is True
        assert error is None
    
    def test_valid_filled_to_closed(self) -> None:
        """FILLED -> CLOSED should be valid."""
        is_valid, error = validate_transition(
            "FILLED", "CLOSED", "test-corr-id"
        )
        assert is_valid is True
        assert error is None
    
    def test_valid_closed_to_settled(self) -> None:
        """CLOSED -> SETTLED should be valid."""
        is_valid, error = validate_transition(
            "CLOSED", "SETTLED", "test-corr-id"
        )
        assert is_valid is True
        assert error is None
    
    def test_invalid_pending_to_accepted(self) -> None:
        """PENDING -> ACCEPTED should be invalid (must go through AWAITING_APPROVAL)."""
        is_valid, error = validate_transition(
            "PENDING", "ACCEPTED", "test-corr-id"
        )
        assert is_valid is False
        assert error == "SEC-030"
    
    def test_invalid_pending_to_filled(self) -> None:
        """PENDING -> FILLED should be invalid."""
        is_valid, error = validate_transition(
            "PENDING", "FILLED", "test-corr-id"
        )
        assert is_valid is False
        assert error == "SEC-030"
    
    def test_invalid_awaiting_approval_to_filled(self) -> None:
        """AWAITING_APPROVAL -> FILLED should be invalid (must go through ACCEPTED)."""
        is_valid, error = validate_transition(
            "AWAITING_APPROVAL", "FILLED", "test-corr-id"
        )
        assert is_valid is False
        assert error == "SEC-030"
    
    def test_invalid_settled_to_any(self) -> None:
        """SETTLED -> any state should be invalid (terminal state)."""
        for target in VALID_STATES:
            if target != "SETTLED":
                is_valid, error = validate_transition(
                    "SETTLED", target, "test-corr-id"
                )
                assert is_valid is False
                assert error == "SEC-030"
    
    def test_invalid_rejected_to_any(self) -> None:
        """REJECTED -> any state should be invalid (terminal state)."""
        for target in VALID_STATES:
            if target != "REJECTED":
                is_valid, error = validate_transition(
                    "REJECTED", target, "test-corr-id"
                )
                assert is_valid is False
                assert error == "SEC-030"
    
    def test_invalid_current_state(self) -> None:
        """Invalid current state should return SEC-030."""
        is_valid, error = validate_transition(
            "INVALID_STATE", "ACCEPTED", "test-corr-id"
        )
        assert is_valid is False
        assert error == "SEC-030"
    
    def test_invalid_target_state(self) -> None:
        """Invalid target state should return SEC-030."""
        is_valid, error = validate_transition(
            "PENDING", "INVALID_STATE", "test-corr-id"
        )
        assert is_valid is False
        assert error == "SEC-030"


# =============================================================================
# Test transition_trade() Function
# =============================================================================

class TestTransitionTrade:
    """
    Test the transition_trade() function.
    
    **Feature: hitl-approval-gateway, Task 3.3: Implement transition_trade() function**
    **Validates: Requirements 1.6**
    """
    
    def test_valid_transition_creates_audit_record(self) -> None:
        """Valid transition should create audit record."""
        success, error, audit = transition_trade(
            db_session=None,
            trade_id="test-trade-123",
            current_state="PENDING",
            target_state="AWAITING_APPROVAL",
            correlation_id="test-corr-456",
            actor_id="SYSTEM",
            reason="HITL request created"
        )
        
        assert success is True
        assert error is None
        assert audit is not None
        assert audit["action"] == "STATE_TRANSITION"
        assert audit["target_type"] == "trade"
        assert audit["target_id"] == "test-trade-123"
        assert audit["previous_state"] == {"state": "PENDING"}
        assert audit["new_state"] == {"state": "AWAITING_APPROVAL"}
        assert audit["correlation_id"] == "test-corr-456"
        assert audit["actor_id"] == "SYSTEM"
    
    def test_invalid_transition_returns_error(self) -> None:
        """Invalid transition should return error code."""
        success, error, audit = transition_trade(
            db_session=None,
            trade_id="test-trade-123",
            current_state="PENDING",
            target_state="ACCEPTED",  # Invalid - must go through AWAITING_APPROVAL
            correlation_id="test-corr-456"
        )
        
        assert success is False
        assert error == "SEC-030"
        assert audit is None
    
    def test_empty_correlation_id_rejected(self) -> None:
        """Empty correlation_id should be rejected."""
        success, error, audit = transition_trade(
            db_session=None,
            trade_id="test-trade-123",
            current_state="PENDING",
            target_state="AWAITING_APPROVAL",
            correlation_id=""
        )
        
        assert success is False
        assert error == "SEC-030"
        assert audit is None
    
    def test_whitespace_correlation_id_rejected(self) -> None:
        """Whitespace-only correlation_id should be rejected."""
        success, error, audit = transition_trade(
            db_session=None,
            trade_id="test-trade-123",
            current_state="PENDING",
            target_state="AWAITING_APPROVAL",
            correlation_id="   "
        )
        
        assert success is False
        assert error == "SEC-030"
        assert audit is None
    
    def test_audit_record_has_timestamp(self) -> None:
        """Audit record should have created_at timestamp."""
        success, error, audit = transition_trade(
            db_session=None,
            trade_id="test-trade-123",
            current_state="PENDING",
            target_state="AWAITING_APPROVAL",
            correlation_id="test-corr-456"
        )
        
        assert success is True
        assert audit is not None
        assert "created_at" in audit
        assert audit["created_at"] is not None
    
    def test_audit_record_has_id(self) -> None:
        """Audit record should have unique ID."""
        success, error, audit = transition_trade(
            db_session=None,
            trade_id="test-trade-123",
            current_state="PENDING",
            target_state="AWAITING_APPROVAL",
            correlation_id="test-corr-456"
        )
        
        assert success is True
        assert audit is not None
        assert "id" in audit
        # Verify it's a valid UUID
        uuid.UUID(audit["id"])
    
    def test_default_actor_is_system(self) -> None:
        """Default actor_id should be SYSTEM."""
        success, error, audit = transition_trade(
            db_session=None,
            trade_id="test-trade-123",
            current_state="PENDING",
            target_state="AWAITING_APPROVAL",
            correlation_id="test-corr-456"
            # actor_id not provided
        )
        
        assert success is True
        assert audit is not None
        assert audit["actor_id"] == "SYSTEM"
    
    def test_custom_actor_id(self) -> None:
        """Custom actor_id should be recorded."""
        success, error, audit = transition_trade(
            db_session=None,
            trade_id="test-trade-123",
            current_state="PENDING",
            target_state="AWAITING_APPROVAL",
            correlation_id="test-corr-456",
            actor_id="operator_123"
        )
        
        assert success is True
        assert audit is not None
        assert audit["actor_id"] == "operator_123"
    
    def test_reason_recorded_in_payload(self) -> None:
        """Reason should be recorded in audit payload."""
        success, error, audit = transition_trade(
            db_session=None,
            trade_id="test-trade-123",
            current_state="PENDING",
            target_state="AWAITING_APPROVAL",
            correlation_id="test-corr-456",
            reason="HITL request created"
        )
        
        assert success is True
        assert audit is not None
        assert audit["payload"]["reason"] == "HITL request created"
    
    def test_metadata_recorded_in_payload(self) -> None:
        """Metadata should be recorded in audit payload."""
        metadata = {"instrument": "BTCZAR", "side": "BUY"}
        success, error, audit = transition_trade(
            db_session=None,
            trade_id="test-trade-123",
            current_state="PENDING",
            target_state="AWAITING_APPROVAL",
            correlation_id="test-corr-456",
            metadata=metadata
        )
        
        assert success is True
        assert audit is not None
        assert audit["payload"]["metadata"] == metadata


# =============================================================================
# Test Utility Functions
# =============================================================================

class TestUtilityFunctions:
    """Test utility functions."""
    
    def test_get_valid_transitions(self) -> None:
        """get_valid_transitions should return correct targets."""
        assert get_valid_transitions("PENDING") == ["AWAITING_APPROVAL"]
        assert get_valid_transitions("AWAITING_APPROVAL") == ["ACCEPTED", "REJECTED"]
        assert get_valid_transitions("SETTLED") == []
    
    def test_is_terminal_state(self) -> None:
        """is_terminal_state should identify terminal states."""
        assert is_terminal_state("SETTLED") is True
        assert is_terminal_state("REJECTED") is True
        assert is_terminal_state("PENDING") is False
        assert is_terminal_state("AWAITING_APPROVAL") is False
    
    def test_is_valid_state(self) -> None:
        """is_valid_state should identify valid states."""
        for state in VALID_STATES:
            assert is_valid_state(state) is True
        assert is_valid_state("INVALID") is False


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])

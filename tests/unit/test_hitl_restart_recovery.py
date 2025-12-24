"""
============================================================================
Unit Tests - HITL Gateway Restart Recovery
============================================================================

Reliability Level: SOVEREIGN TIER
Python 3.8 Compatible

Tests the HITL Gateway restart recovery functionality:
- recover_on_startup() method
- Recovery with valid pending requests
- Recovery with corrupted hash (SEC-080)
- Recovery with expired requests
- Recovery error handling

**Feature: hitl-approval-gateway, Task 11.2: Write unit tests for restart recovery**
**Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5**
============================================================================
"""

import pytest
import uuid
import os
import sys
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from unittest.mock import Mock, MagicMock, patch, call

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from services.hitl_gateway import (
    HITLGateway,
    RecoveryResult,
)
from services.hitl_config import HITLConfig
from services.hitl_models import (
    ApprovalRequest,
    ApprovalStatus,
    DecisionChannel,
    RowHasher,
)
from services.guardian_integration import GuardianIntegration
from services.slippage_guard import SlippageGuard


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def mock_config() -> HITLConfig:
    """Create a mock HITL configuration."""
    return HITLConfig(
        enabled=True,
        timeout_seconds=300,
        slippage_max_percent=Decimal("0.50"),
        allowed_operators={"operator1", "operator2", "admin"},
    )


@pytest.fixture
def mock_guardian() -> Mock:
    """Create a mock Guardian integration."""
    guardian = Mock(spec=GuardianIntegration)
    guardian.is_locked.return_value = False
    guardian.block_operation = Mock()
    return guardian


@pytest.fixture
def mock_slippage_guard() -> SlippageGuard:
    """Create a slippage guard with default threshold."""
    return SlippageGuard(max_slippage_pct=Decimal("0.50"))


@pytest.fixture
def hitl_gateway(
    mock_config: HITLConfig,
    mock_guardian: Mock,
    mock_slippage_guard: SlippageGuard,
) -> HITLGateway:
    """Create a HITL Gateway instance for testing."""
    return HITLGateway(
        config=mock_config,
        guardian=mock_guardian,
        slippage_guard=mock_slippage_guard,
        db_session=None,  # No database for unit tests
    )


def create_valid_approval_request(
    trade_id: Optional[uuid.UUID] = None,
    expires_at: Optional[datetime] = None,
    status: str = ApprovalStatus.AWAITING_APPROVAL.value,
) -> ApprovalRequest:
    """
    Create a valid approval request for testing.
    
    Args:
        trade_id: Optional trade ID (generates new UUID if not provided)
        expires_at: Optional expiry time (defaults to 5 minutes from now)
        status: Approval status (defaults to AWAITING_APPROVAL)
    
    Returns:
        ApprovalRequest with valid hash
    """
    if trade_id is None:
        trade_id = uuid.uuid4()
    
    if expires_at is None:
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)
    
    approval = ApprovalRequest(
        id=uuid.uuid4(),
        trade_id=trade_id,
        instrument="BTCZAR",
        side="BUY",
        risk_pct=Decimal("2.50"),
        confidence=Decimal("0.85"),
        request_price=Decimal("1500000.12345678"),
        reasoning_summary={"trend": "bullish", "signal": "strong"},
        correlation_id=uuid.uuid4(),
        status=status,
        requested_at=datetime.now(timezone.utc),
        expires_at=expires_at,
        decided_at=None,
        decided_by=None,
        decision_channel=None,
        decision_reason=None,
        row_hash="",  # Will be computed
    )
    
    # Compute valid hash
    approval.row_hash = RowHasher.compute(approval)
    
    return approval


# =============================================================================
# Restart Recovery Tests
# =============================================================================

class TestRestartRecovery:
    """
    Test recover_on_startup() method.
    
    **Feature: hitl-approval-gateway, Task 11.2: Write unit tests for restart recovery**
    **Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5**
    """
    
    def test_recovery_with_no_pending_requests(
        self,
        hitl_gateway: HITLGateway,
    ) -> None:
        """
        Should return success with zero counts when no pending requests.
        
        **Validates: Requirement 5.1**
        """
        # Mock _query_pending_approvals to return empty list
        with patch.object(
            hitl_gateway,
            '_query_pending_approvals',
            return_value=[]
        ):
            result = hitl_gateway.recover_on_startup()
        
        assert result.success is True
        assert result.total_pending == 0
        assert result.valid_pending == 0
        assert result.expired_processed == 0
        assert result.hash_failures == 0
        assert len(result.errors) == 0
        assert result.correlation_id is not None
    
    def test_recovery_with_valid_pending_requests(
        self,
        hitl_gateway: HITLGateway,
    ) -> None:
        """
        Should recover valid pending requests and re-emit WebSocket events.
        
        **Validates: Requirements 5.1, 5.2, 5.4**
        """
        # Create valid pending requests
        approval1 = create_valid_approval_request()
        approval2 = create_valid_approval_request()
        
        # Mock _query_pending_approvals to return valid requests
        with patch.object(
            hitl_gateway,
            '_query_pending_approvals',
            return_value=[approval1.to_dict(), approval2.to_dict()]
        ):
            # Mock WebSocket emitter
            mock_websocket = Mock()
            hitl_gateway._websocket_emitter = mock_websocket
            
            # Mock _emit_websocket_event
            with patch.object(
                hitl_gateway,
                '_emit_websocket_event'
            ) as mock_emit:
                # Mock _create_audit_log
                with patch.object(
                    hitl_gateway,
                    '_create_audit_log'
                ) as mock_audit:
                    result = hitl_gateway.recover_on_startup()
        
        # Verify recovery result
        assert result.success is True
        assert result.total_pending == 2
        assert result.valid_pending == 2
        assert result.expired_processed == 0
        assert result.hash_failures == 0
        assert len(result.errors) == 0
        
        # Verify WebSocket events were emitted (2 times)
        assert mock_emit.call_count == 2
        
        # Verify audit logs were created (2 for valid requests + 1 for recovery complete)
        assert mock_audit.call_count == 3
    
    def test_recovery_with_corrupted_hash_triggers_sec_080(
        self,
        hitl_gateway: HITLGateway,
    ) -> None:
        """
        Should detect corrupted hash, log SEC-080, and reject request.
        
        **Validates: Requirements 5.2, 5.3**
        """
        # Create approval with INVALID hash
        approval = create_valid_approval_request()
        approval.row_hash = "0" * 64  # Invalid hash
        
        # Mock _query_pending_approvals to return corrupted request
        with patch.object(
            hitl_gateway,
            '_query_pending_approvals',
            return_value=[approval.to_dict()]
        ):
            # Mock _reject_corrupted_request
            with patch.object(
                hitl_gateway,
                '_reject_corrupted_request'
            ) as mock_reject:
                # Mock _trigger_security_alert
                with patch.object(
                    hitl_gateway,
                    '_trigger_security_alert'
                ) as mock_alert:
                    result = hitl_gateway.recover_on_startup()
        
        # Verify recovery result - success is False when hash failures occur
        assert result.success is False
        assert result.total_pending == 1
        assert result.valid_pending == 0
        assert result.expired_processed == 0
        assert result.hash_failures == 1
        assert len(result.errors) == 1
        
        # Verify error details
        error = result.errors[0]
        assert error["error_code"] == "SEC-080"
        assert "hash verification failed" in error["message"].lower()
        
        # Verify corrupted request was rejected
        mock_reject.assert_called_once()
        
        # Verify security alert was triggered
        mock_alert.assert_called_once()
    
    def test_recovery_processes_already_expired_requests(
        self,
        hitl_gateway: HITLGateway,
    ) -> None:
        """
        Should process expired requests immediately during recovery.
        
        **Validates: Requirements 5.5**
        """
        # Create approval that expired 10 minutes ago
        expired_time = datetime.now(timezone.utc) - timedelta(minutes=10)
        approval = create_valid_approval_request(expires_at=expired_time)
        
        # Mock _query_pending_approvals to return expired request
        with patch.object(
            hitl_gateway,
            '_query_pending_approvals',
            return_value=[approval.to_dict()]
        ):
            # Mock _process_expired_during_recovery
            with patch.object(
                hitl_gateway,
                '_process_expired_during_recovery'
            ) as mock_process_expired:
                result = hitl_gateway.recover_on_startup()
        
        # Verify recovery result
        assert result.success is True
        assert result.total_pending == 1
        assert result.valid_pending == 0
        assert result.expired_processed == 1
        assert result.hash_failures == 0
        assert len(result.errors) == 0
        
        # Verify expired request was processed
        mock_process_expired.assert_called_once()
    
    def test_recovery_with_mixed_requests(
        self,
        hitl_gateway: HITLGateway,
    ) -> None:
        """
        Should handle mix of valid, expired, and corrupted requests.
        
        **Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5**
        """
        # Create valid pending request
        valid_approval = create_valid_approval_request()
        
        # Create expired request
        expired_time = datetime.now(timezone.utc) - timedelta(minutes=10)
        expired_approval = create_valid_approval_request(expires_at=expired_time)
        
        # Create corrupted request
        corrupted_approval = create_valid_approval_request()
        corrupted_approval.row_hash = "0" * 64  # Invalid hash
        
        # Mock _query_pending_approvals to return all three
        with patch.object(
            hitl_gateway,
            '_query_pending_approvals',
            return_value=[
                valid_approval.to_dict(),
                expired_approval.to_dict(),
                corrupted_approval.to_dict(),
            ]
        ):
            # Mock all helper methods
            with patch.object(
                hitl_gateway,
                '_emit_websocket_event'
            ) as mock_emit:
                with patch.object(
                    hitl_gateway,
                    '_create_audit_log'
                ) as mock_audit:
                    with patch.object(
                        hitl_gateway,
                        '_process_expired_during_recovery'
                    ) as mock_expired:
                        with patch.object(
                            hitl_gateway,
                            '_reject_corrupted_request'
                        ) as mock_reject:
                            with patch.object(
                                hitl_gateway,
                                '_trigger_security_alert'
                            ) as mock_alert:
                                # Set websocket emitter
                                hitl_gateway._websocket_emitter = Mock()
                                
                                result = hitl_gateway.recover_on_startup()
        
        # Verify recovery result - success is False when hash failures occur
        assert result.success is False
        assert result.total_pending == 3
        assert result.valid_pending == 1  # Only one valid
        assert result.expired_processed == 1  # One expired
        assert result.hash_failures == 1  # One corrupted
        assert len(result.errors) == 1  # One error for corrupted
        
        # Verify valid request was re-emitted
        assert mock_emit.call_count == 1
        # Audit: 1 for valid + 1 for recovery complete
        assert mock_audit.call_count == 2
        
        # Verify expired request was processed
        mock_expired.assert_called_once()
        
        # Verify corrupted request was rejected
        mock_reject.assert_called_once()
        mock_alert.assert_called_once()
    
    def test_recovery_generates_correlation_id(
        self,
        hitl_gateway: HITLGateway,
    ) -> None:
        """
        Should generate unique correlation_id for recovery operation.
        
        **Validates: Requirement 5.1**
        """
        # Mock _query_pending_approvals to return empty list
        with patch.object(
            hitl_gateway,
            '_query_pending_approvals',
            return_value=[]
        ):
            result = hitl_gateway.recover_on_startup()
        
        assert result.correlation_id is not None
        assert len(result.correlation_id) > 0
        
        # Should be a valid UUID string
        try:
            uuid.UUID(result.correlation_id)
        except ValueError:
            pytest.fail("correlation_id is not a valid UUID")
    
    def test_recovery_handles_exception_in_processing(
        self,
        hitl_gateway: HITLGateway,
    ) -> None:
        """
        Should handle exceptions during record processing gracefully.
        
        **Validates: Requirement 5.1**
        """
        # Create valid approval
        approval = create_valid_approval_request()
        
        # Create malformed record (missing required field)
        malformed_record = approval.to_dict()
        del malformed_record["instrument"]  # Remove required field
        
        # Note: When a field is missing, the hash will be computed differently
        # and will fail verification, resulting in SEC-080 instead of SEC-010
        
        # Mock _query_pending_approvals to return malformed record
        with patch.object(
            hitl_gateway,
            '_query_pending_approvals',
            return_value=[malformed_record]
        ):
            result = hitl_gateway.recover_on_startup()
        
        # Recovery should complete but with error (hash failure due to missing field)
        assert result.success is False
        assert result.total_pending == 1
        assert result.valid_pending == 0
        assert result.expired_processed == 0
        # Hash verification will fail because the dict is incomplete
        assert result.hash_failures == 1
        assert len(result.errors) == 1
        
        # Verify error details
        error = result.errors[0]
        assert error["error_code"] == "SEC-080"
    
    def test_recovery_verifies_hash_before_processing(
        self,
        hitl_gateway: HITLGateway,
    ) -> None:
        """
        Should verify row_hash integrity before any other processing.
        
        **Validates: Requirement 5.2**
        """
        # Create approval with corrupted hash
        approval = create_valid_approval_request()
        original_hash = approval.row_hash
        approval.row_hash = "corrupted_hash_" + original_hash[:40]
        
        # Mock _query_pending_approvals
        with patch.object(
            hitl_gateway,
            '_query_pending_approvals',
            return_value=[approval.to_dict()]
        ):
            # Mock _reject_corrupted_request to track call
            with patch.object(
                hitl_gateway,
                '_reject_corrupted_request'
            ) as mock_reject:
                # Mock _trigger_security_alert
                with patch.object(
                    hitl_gateway,
                    '_trigger_security_alert'
                ):
                    # Mock _process_expired_during_recovery (should NOT be called)
                    with patch.object(
                        hitl_gateway,
                        '_process_expired_during_recovery'
                    ) as mock_expired:
                        result = hitl_gateway.recover_on_startup()
        
        # Verify hash failure was detected
        assert result.hash_failures == 1
        
        # Verify corrupted request was rejected
        mock_reject.assert_called_once()
        
        # Verify expired processing was NOT called (hash check comes first)
        mock_expired.assert_not_called()
    
    def test_recovery_with_multiple_corrupted_hashes(
        self,
        hitl_gateway: HITLGateway,
    ) -> None:
        """
        Should handle multiple corrupted hashes correctly.
        
        **Validates: Requirements 5.2, 5.3**
        """
        # Create multiple approvals with corrupted hashes
        approval1 = create_valid_approval_request()
        approval1.row_hash = "0" * 64
        
        approval2 = create_valid_approval_request()
        approval2.row_hash = "1" * 64
        
        approval3 = create_valid_approval_request()
        approval3.row_hash = "2" * 64
        
        # Mock _query_pending_approvals
        with patch.object(
            hitl_gateway,
            '_query_pending_approvals',
            return_value=[
                approval1.to_dict(),
                approval2.to_dict(),
                approval3.to_dict(),
            ]
        ):
            # Mock helper methods
            with patch.object(
                hitl_gateway,
                '_reject_corrupted_request'
            ) as mock_reject:
                with patch.object(
                    hitl_gateway,
                    '_trigger_security_alert'
                ) as mock_alert:
                    result = hitl_gateway.recover_on_startup()
        
        # Verify all three hash failures were detected
        assert result.hash_failures == 3
        assert len(result.errors) == 3
        
        # Verify all were rejected
        assert mock_reject.call_count == 3
        
        # Verify all triggered security alerts
        assert mock_alert.call_count == 3
    
    def test_recovery_re_emits_websocket_only_for_valid_pending(
        self,
        hitl_gateway: HITLGateway,
    ) -> None:
        """
        Should only re-emit WebSocket events for valid pending requests.
        
        **Validates: Requirement 5.4**
        """
        # Create valid pending request
        valid_approval = create_valid_approval_request()
        
        # Create expired request (should NOT re-emit)
        expired_time = datetime.now(timezone.utc) - timedelta(minutes=10)
        expired_approval = create_valid_approval_request(expires_at=expired_time)
        
        # Mock _query_pending_approvals
        with patch.object(
            hitl_gateway,
            '_query_pending_approvals',
            return_value=[
                valid_approval.to_dict(),
                expired_approval.to_dict(),
            ]
        ):
            # Mock _emit_websocket_event
            with patch.object(
                hitl_gateway,
                '_emit_websocket_event'
            ) as mock_emit:
                # Mock other methods
                with patch.object(
                    hitl_gateway,
                    '_create_audit_log'
                ):
                    with patch.object(
                        hitl_gateway,
                        '_process_expired_during_recovery'
                    ):
                        # Set websocket emitter
                        hitl_gateway._websocket_emitter = Mock()
                        
                        result = hitl_gateway.recover_on_startup()
        
        # Verify only one WebSocket event was emitted (for valid request)
        assert mock_emit.call_count == 1
        
        # Verify the event type
        call_args = mock_emit.call_args
        assert call_args[1]["event_type"] == "hitl.recovered"
    
    def test_recovery_creates_audit_log_for_valid_requests(
        self,
        hitl_gateway: HITLGateway,
    ) -> None:
        """
        Should create audit log entries for valid recovered requests.
        
        **Validates: Requirement 5.4**
        """
        # Create valid pending request
        approval = create_valid_approval_request()
        
        # Mock _query_pending_approvals
        with patch.object(
            hitl_gateway,
            '_query_pending_approvals',
            return_value=[approval.to_dict()]
        ):
            # Mock _create_audit_log
            with patch.object(
                hitl_gateway,
                '_create_audit_log'
            ) as mock_audit:
                # Mock other methods
                with patch.object(
                    hitl_gateway,
                    '_emit_websocket_event'
                ):
                    # Set websocket emitter
                    hitl_gateway._websocket_emitter = Mock()
                    
                    result = hitl_gateway.recover_on_startup()
        
        # Verify audit logs were created (1 for valid request + 1 for recovery complete)
        assert mock_audit.call_count == 2
        
        # Verify first audit log parameters (for valid request)
        first_call = mock_audit.call_args_list[0]
        assert first_call[1]["actor_id"] == "SYSTEM"
        assert first_call[1]["action"] == "HITL_RECOVERY_VALID"
        assert first_call[1]["target_type"] == "hitl_approval"
        
        # Verify second audit log parameters (for recovery complete)
        second_call = mock_audit.call_args_list[1]
        assert second_call[1]["actor_id"] == "SYSTEM"
        assert second_call[1]["action"] == "HITL_RECOVERY_COMPLETE"
        assert second_call[1]["target_type"] == "system"
    
    def test_recovery_without_websocket_emitter(
        self,
        hitl_gateway: HITLGateway,
    ) -> None:
        """
        Should handle recovery gracefully when WebSocket emitter is None.
        
        **Validates: Requirement 5.4**
        """
        # Create valid pending request
        approval = create_valid_approval_request()
        
        # Ensure websocket emitter is None
        hitl_gateway._websocket_emitter = None
        
        # Mock _query_pending_approvals
        with patch.object(
            hitl_gateway,
            '_query_pending_approvals',
            return_value=[approval.to_dict()]
        ):
            # Mock _create_audit_log
            with patch.object(
                hitl_gateway,
                '_create_audit_log'
            ):
                result = hitl_gateway.recover_on_startup()
        
        # Recovery should succeed even without WebSocket emitter
        assert result.success is True
        assert result.valid_pending == 1
    
    def test_recovery_result_contains_all_statistics(
        self,
        hitl_gateway: HITLGateway,
    ) -> None:
        """
        Should return RecoveryResult with all required statistics.
        
        **Validates: Requirement 5.1**
        """
        # Mock _query_pending_approvals to return empty list
        with patch.object(
            hitl_gateway,
            '_query_pending_approvals',
            return_value=[]
        ):
            result = hitl_gateway.recover_on_startup()
        
        # Verify all fields are present
        assert hasattr(result, 'success')
        assert hasattr(result, 'total_pending')
        assert hasattr(result, 'valid_pending')
        assert hasattr(result, 'expired_processed')
        assert hasattr(result, 'hash_failures')
        assert hasattr(result, 'errors')
        assert hasattr(result, 'correlation_id')
        
        # Verify types
        assert isinstance(result.success, bool)
        assert isinstance(result.total_pending, int)
        assert isinstance(result.valid_pending, int)
        assert isinstance(result.expired_processed, int)
        assert isinstance(result.hash_failures, int)
        assert isinstance(result.errors, list)
        assert isinstance(result.correlation_id, str)


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

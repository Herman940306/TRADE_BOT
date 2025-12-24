"""
============================================================================
HITL Foundation Checkpoint Tests
============================================================================

Reliability Level: L6 Critical (Sovereign Tier)
Python 3.8 Compatible

This test file validates all HITL foundation components are working:
- SlippageGuard
- RowHasher
- ApprovalRequest / ApprovalDecision
- HITLConfig

**Feature: hitl-approval-gateway, Task 7: Checkpoint**
============================================================================
"""

import pytest
from decimal import Decimal
from datetime import datetime, timezone, timedelta
import uuid
import os

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from services.slippage_guard import SlippageGuard, SlippageValidationResult
from services.hitl_models import (
    ApprovalRequest,
    ApprovalDecision,
    RowHasher,
    ApprovalStatus,
    TradeSide,
    DecisionChannel,
)
from services.hitl_config import (
    HITLConfig,
    HITLConfigurationError,
    DEFAULT_HITL_ENABLED,
    DEFAULT_HITL_TIMEOUT_SECONDS,
    DEFAULT_HITL_SLIPPAGE_MAX_PERCENT,
)


# =============================================================================
# SlippageGuard Tests
# =============================================================================

class TestSlippageGuard:
    """Tests for SlippageGuard class."""
    
    def test_slippage_within_threshold_is_valid(self) -> None:
        """Slippage within threshold should be valid."""
        guard = SlippageGuard(max_slippage_pct=Decimal("0.5"))
        is_valid, deviation = guard.validate(
            request_price=Decimal("100.00"),
            current_price=Decimal("100.25")
        )
        assert is_valid is True
        assert deviation == Decimal("0.2500")
    
    def test_slippage_exceeding_threshold_is_invalid(self) -> None:
        """Slippage exceeding threshold should be invalid."""
        guard = SlippageGuard(max_slippage_pct=Decimal("0.5"))
        is_valid, deviation = guard.validate(
            request_price=Decimal("100.00"),
            current_price=Decimal("101.00")
        )
        assert is_valid is False
        assert deviation == Decimal("1.0000")
    
    def test_slippage_at_threshold_is_valid(self) -> None:
        """Slippage exactly at threshold should be valid."""
        guard = SlippageGuard(max_slippage_pct=Decimal("0.5"))
        is_valid, deviation = guard.validate(
            request_price=Decimal("100.00"),
            current_price=Decimal("100.50")
        )
        assert is_valid is True
        assert deviation == Decimal("0.5000")
    
    def test_zero_request_price_is_invalid(self) -> None:
        """Zero request price should be invalid."""
        guard = SlippageGuard(max_slippage_pct=Decimal("0.5"))
        is_valid, deviation = guard.validate(
            request_price=Decimal("0.00"),
            current_price=Decimal("100.00")
        )
        assert is_valid is False
    
    def test_negative_request_price_is_invalid(self) -> None:
        """Negative request price should be invalid."""
        guard = SlippageGuard(max_slippage_pct=Decimal("0.5"))
        is_valid, deviation = guard.validate(
            request_price=Decimal("-100.00"),
            current_price=Decimal("100.00")
        )
        assert is_valid is False
    
    def test_equal_prices_is_valid(self) -> None:
        """Equal prices should be valid with 0% deviation."""
        guard = SlippageGuard(max_slippage_pct=Decimal("0.5"))
        is_valid, deviation = guard.validate(
            request_price=Decimal("100.00"),
            current_price=Decimal("100.00")
        )
        assert is_valid is True
        assert deviation == Decimal("0.0000")
    
    def test_validate_detailed_returns_result_object(self) -> None:
        """validate_detailed should return SlippageValidationResult."""
        guard = SlippageGuard(max_slippage_pct=Decimal("0.5"))
        result = guard.validate_detailed(
            request_price=Decimal("100.00"),
            current_price=Decimal("100.25")
        )
        assert isinstance(result, SlippageValidationResult)
        assert result.is_valid is True
        assert result.max_slippage_pct == Decimal("0.5000")


# =============================================================================
# RowHasher Tests
# =============================================================================

class TestRowHasher:
    """Tests for RowHasher class."""
    
    @pytest.fixture
    def sample_request(self) -> ApprovalRequest:
        """Create a sample ApprovalRequest for testing."""
        now = datetime.now(timezone.utc)
        return ApprovalRequest(
            id=uuid.UUID("12345678-1234-5678-1234-567812345678"),
            trade_id=uuid.UUID("87654321-4321-8765-4321-876543218765"),
            instrument="BTCZAR",
            side="BUY",
            risk_pct=Decimal("1.00"),
            confidence=Decimal("0.85"),
            request_price=Decimal("1500000.00000000"),
            reasoning_summary={"trend": "bullish", "signal": "strong"},
            correlation_id=uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"),
            status="AWAITING_APPROVAL",
            requested_at=now,
            expires_at=now + timedelta(minutes=5),
        )
    
    def test_compute_returns_64_char_hash(self, sample_request: ApprovalRequest) -> None:
        """compute() should return 64-character hex hash."""
        hash_value = RowHasher.compute(sample_request)
        assert len(hash_value) == 64
        assert all(c in "0123456789abcdef" for c in hash_value)
    
    def test_compute_is_deterministic(self, sample_request: ApprovalRequest) -> None:
        """compute() should return same hash for same input."""
        hash1 = RowHasher.compute(sample_request)
        hash2 = RowHasher.compute(sample_request)
        assert hash1 == hash2
    
    def test_compute_changes_with_field_change(self, sample_request: ApprovalRequest) -> None:
        """compute() should return different hash when field changes."""
        hash1 = RowHasher.compute(sample_request)
        sample_request.status = "APPROVED"
        hash2 = RowHasher.compute(sample_request)
        assert hash1 != hash2
    
    def test_verify_returns_true_for_valid_hash(self, sample_request: ApprovalRequest) -> None:
        """verify() should return True when hash matches."""
        sample_request.row_hash = RowHasher.compute(sample_request)
        assert RowHasher.verify(sample_request) is True
    
    def test_verify_returns_false_for_invalid_hash(self, sample_request: ApprovalRequest) -> None:
        """verify() should return False when hash doesn't match."""
        sample_request.row_hash = "invalid_hash_value"
        assert RowHasher.verify(sample_request) is False
    
    def test_verify_returns_false_for_missing_hash(self, sample_request: ApprovalRequest) -> None:
        """verify() should return False when hash is None."""
        sample_request.row_hash = None
        assert RowHasher.verify(sample_request) is False


# =============================================================================
# ApprovalRequest Tests
# =============================================================================

class TestApprovalRequest:
    """Tests for ApprovalRequest dataclass."""
    
    def test_to_dict_serializes_all_fields(self) -> None:
        """to_dict() should serialize all fields."""
        now = datetime.now(timezone.utc)
        request = ApprovalRequest(
            id=uuid.uuid4(),
            trade_id=uuid.uuid4(),
            instrument="BTCZAR",
            side="BUY",
            risk_pct=Decimal("1.00"),
            confidence=Decimal("0.85"),
            request_price=Decimal("1500000.00"),
            reasoning_summary={"trend": "bullish"},
            correlation_id=uuid.uuid4(),
            status="AWAITING_APPROVAL",
            requested_at=now,
            expires_at=now + timedelta(minutes=5),
        )
        
        data = request.to_dict()
        
        assert "id" in data
        assert "trade_id" in data
        assert "instrument" in data
        assert data["instrument"] == "BTCZAR"
        assert data["side"] == "BUY"
        assert data["status"] == "AWAITING_APPROVAL"
    
    def test_from_dict_deserializes_correctly(self) -> None:
        """from_dict() should deserialize correctly."""
        now = datetime.now(timezone.utc)
        data = {
            "id": str(uuid.uuid4()),
            "trade_id": str(uuid.uuid4()),
            "instrument": "ETHZAR",
            "side": "SELL",
            "risk_pct": "0.50",
            "confidence": "0.75",
            "request_price": "50000.00",
            "reasoning_summary": {"trend": "bearish"},
            "correlation_id": str(uuid.uuid4()),
            "status": "AWAITING_APPROVAL",
            "requested_at": now.isoformat(),
            "expires_at": (now + timedelta(minutes=5)).isoformat(),
        }
        
        request = ApprovalRequest.from_dict(data)
        
        assert request.instrument == "ETHZAR"
        assert request.side == "SELL"
        assert request.risk_pct == Decimal("0.50")
        assert request.confidence == Decimal("0.75")


# =============================================================================
# ApprovalDecision Tests
# =============================================================================

class TestApprovalDecision:
    """Tests for ApprovalDecision dataclass."""
    
    def test_to_dict_serializes_all_fields(self) -> None:
        """to_dict() should serialize all fields."""
        decision = ApprovalDecision(
            trade_id=uuid.uuid4(),
            decision="APPROVE",
            operator_id="operator_123",
            channel="WEB",
            correlation_id=uuid.uuid4(),
            reason="Looks good",
            comment="Approved after review",
        )
        
        data = decision.to_dict()
        
        assert "trade_id" in data
        assert data["decision"] == "APPROVE"
        assert data["operator_id"] == "operator_123"
        assert data["channel"] == "WEB"
    
    def test_from_dict_deserializes_correctly(self) -> None:
        """from_dict() should deserialize correctly."""
        data = {
            "trade_id": str(uuid.uuid4()),
            "decision": "REJECT",
            "operator_id": "operator_456",
            "channel": "DISCORD",
            "correlation_id": str(uuid.uuid4()),
            "reason": "Too risky",
        }
        
        decision = ApprovalDecision.from_dict(data)
        
        assert decision.decision == "REJECT"
        assert decision.operator_id == "operator_456"
        assert decision.channel == "DISCORD"


# =============================================================================
# HITLConfig Tests
# =============================================================================

class TestHITLConfig:
    """Tests for HITLConfig class."""
    
    def test_default_values(self) -> None:
        """Config should have correct default values."""
        config = HITLConfig(allowed_operators={"op1"})
        
        assert config.enabled == DEFAULT_HITL_ENABLED
        assert config.timeout_seconds == DEFAULT_HITL_TIMEOUT_SECONDS
        assert config.slippage_max_percent == DEFAULT_HITL_SLIPPAGE_MAX_PERCENT
    
    def test_is_operator_authorized_returns_true_for_valid(self) -> None:
        """is_operator_authorized should return True for valid operator."""
        config = HITLConfig(allowed_operators={"operator1", "operator2"})
        
        assert config.is_operator_authorized("operator1") is True
        assert config.is_operator_authorized("operator2") is True
    
    def test_is_operator_authorized_returns_false_for_invalid(self) -> None:
        """is_operator_authorized should return False for invalid operator."""
        config = HITLConfig(allowed_operators={"operator1"})
        
        assert config.is_operator_authorized("unknown") is False
        assert config.is_operator_authorized("") is False
        assert config.is_operator_authorized("   ") is False
    
    def test_validate_raises_on_empty_operators(self) -> None:
        """validate() should raise HITLConfigurationError if no operators."""
        config = HITLConfig(allowed_operators=set())
        
        with pytest.raises(HITLConfigurationError) as exc_info:
            config.validate()
        
        assert "SEC-040" in str(exc_info.value)
    
    def test_validate_raises_on_negative_timeout(self) -> None:
        """validate() should raise HITLConfigurationError for negative timeout."""
        config = HITLConfig(
            timeout_seconds=-1,
            allowed_operators={"op1"}
        )
        
        with pytest.raises(HITLConfigurationError):
            config.validate()
    
    def test_to_dict_returns_all_fields(self) -> None:
        """to_dict() should return all configuration fields."""
        config = HITLConfig(
            enabled=True,
            timeout_seconds=300,
            slippage_max_percent=Decimal("0.50"),
            allowed_operators={"op1", "op2"}
        )
        
        data = config.to_dict()
        
        assert data["enabled"] is True
        assert data["timeout_seconds"] == 300
        assert data["slippage_max_percent"] == "0.50"
        assert data["allowed_operators_count"] == 2


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])

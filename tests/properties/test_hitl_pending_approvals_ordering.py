"""
============================================================================
Property-Based Test for HITL Pending Approvals Ordering
============================================================================

Reliability Level: SOVEREIGN TIER
Python 3.8 Compatible

Tests that pending approvals are returned ordered by expiry time (soonest first)
using Hypothesis.
Minimum 100 iterations per property as per design specification.

Property tested:
- Property 14: Pending Approvals Are Ordered By Expiry

REQUIREMENTS SATISFIED:
- Requirement 7.1: GET /api/hitl/pending returns approvals ordered by expires_at ASC

============================================================================
"""

import uuid
from decimal import Decimal, ROUND_HALF_EVEN
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from unittest.mock import Mock, patch

import pytest
from hypothesis import given, settings, assume, Phase
from hypothesis import strategies as st

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

# Import HITL components
from services.hitl_gateway import HITLGateway, PendingApprovalInfo
from services.hitl_config import HITLConfig
from services.hitl_models import (
    ApprovalRequest,
    ApprovalStatus,
    PRECISION_PRICE,
    PRECISION_PERCENT,
)
from services.guardian_integration import GuardianIntegration


# =============================================================================
# HYPOTHESIS STRATEGIES
# =============================================================================

# Strategy for instrument names
instrument_strategy = st.sampled_from(["BTCZAR", "ETHZAR", "XRPZAR", "ADAZAR"])

# Strategy for trade sides
side_strategy = st.sampled_from(["BUY", "SELL"])

# Strategy for risk percentages
risk_pct_strategy = st.decimals(
    min_value=Decimal("0.01"),
    max_value=Decimal("5.00"),
    places=2
)

# Strategy for confidence scores
confidence_strategy = st.decimals(
    min_value=Decimal("0.50"),
    max_value=Decimal("1.00"),
    places=2
)

# Strategy for prices
price_strategy = st.decimals(
    min_value=Decimal("1.00"),
    max_value=Decimal("1000000.00"),
    places=8
)

# Strategy for reasoning summaries
reasoning_summary_strategy = st.fixed_dictionaries({
    "trend": st.sampled_from(["bullish", "bearish", "neutral"]),
    "volatility": st.sampled_from(["low", "medium", "high"]),
    "signal_confluence": st.lists(st.text(min_size=1, max_size=20), min_size=1, max_size=3),
})

# Strategy for number of pending approvals (2-10 to ensure ordering is testable)
num_approvals_strategy = st.integers(min_value=2, max_value=10)

# Strategy for time offsets in seconds (0 to 600 seconds = 10 minutes)
time_offset_strategy = st.integers(min_value=0, max_value=600)


# =============================================================================
# PROPERTY 14: Pending Approvals Are Ordered By Expiry
# **Feature: hitl-approval-gateway, Property 14: Pending Approvals Are Ordered By Expiry**
# **Validates: Requirements 7.1**
# =============================================================================

class TestPendingApprovalsOrdering:
    """
    Property 14: Pending Approvals Are Ordered By Expiry
    
    *For any* call to GET /api/hitl/pending (or get_pending_approvals()),
    the returned list SHALL be ordered by expires_at ascending (soonest expiry first).
    
    This property ensures that:
    - Pending approvals are always returned in expiry order
    - The most urgent approvals appear first
    - Operators see approvals in priority order
    
    Validates: Requirements 7.1
    """
    
    @settings(max_examples=100, phases=[Phase.generate, Phase.target])
    @given(
        num_approvals=num_approvals_strategy,
        instrument=instrument_strategy,
        side=side_strategy,
        risk_pct=risk_pct_strategy,
        confidence=confidence_strategy,
        request_price=price_strategy,
        reasoning_summary=reasoning_summary_strategy,
        time_offsets=st.lists(
            time_offset_strategy,
            min_size=2,
            max_size=10
        )
    )
    def test_pending_approvals_ordered_by_expiry(
        self,
        num_approvals: int,
        instrument: str,
        side: str,
        risk_pct: Decimal,
        confidence: Decimal,
        request_price: Decimal,
        reasoning_summary: dict,
        time_offsets: List[int],
    ) -> None:
        """
        **Feature: hitl-approval-gateway, Property 14: Pending Approvals Are Ordered By Expiry**
        **Validates: Requirements 7.1**
        
        For any set of pending approval requests with different expiry times,
        get_pending_approvals() SHALL return them ordered by expires_at ascending
        (soonest expiry first).
        """
        # Ensure we have enough time offsets for the number of approvals
        assume(len(time_offsets) >= num_approvals)
        
        # Take only the number of offsets we need
        time_offsets = time_offsets[:num_approvals]
        
        # Quantize Decimal values
        risk_pct = risk_pct.quantize(PRECISION_PERCENT, rounding=ROUND_HALF_EVEN)
        confidence = confidence.quantize(PRECISION_PERCENT, rounding=ROUND_HALF_EVEN)
        request_price = request_price.quantize(PRECISION_PRICE, rounding=ROUND_HALF_EVEN)
        
        # Create HITL configuration
        config = HITLConfig(
            enabled=True,
            timeout_seconds=300,
            slippage_max_percent=Decimal("0.50"),
            allowed_operators={"operator1"},
        )
        
        # Create mock Guardian (unlocked)
        guardian = GuardianIntegration()
        
        # Create HITL Gateway
        gateway = HITLGateway(
            config=config,
            guardian=guardian,
            db_session=None,
        )
        
        # Create multiple pending approval requests with different expiry times
        now = datetime.now(timezone.utc)
        pending_approvals: List[ApprovalRequest] = []
        
        for i, offset in enumerate(time_offsets):
            expires_at = now + timedelta(seconds=offset)
            
            approval_request = ApprovalRequest(
                id=uuid.uuid4(),
                trade_id=uuid.uuid4(),
                instrument=instrument,
                side=side,
                risk_pct=risk_pct,
                confidence=confidence,
                request_price=request_price,
                reasoning_summary=reasoning_summary,
                correlation_id=uuid.uuid4(),
                status=ApprovalStatus.AWAITING_APPROVAL.value,
                requested_at=now,
                expires_at=expires_at,
                decided_at=None,
                decided_by=None,
                decision_channel=None,
                decision_reason=None,
                row_hash="mock_hash",  # Mock hash for testing
            )
            
            pending_approvals.append(approval_request)
        
        # Mock the _query_pending_approvals method to return our test data
        # The method should return records ordered by expires_at ASC
        mock_records = []
        for approval in sorted(pending_approvals, key=lambda a: a.expires_at):
            mock_records.append(approval.to_dict())
        
        gateway._query_pending_approvals = Mock(return_value=mock_records)
        
        # Call get_pending_approvals()
        result = gateway.get_pending_approvals()
        
        # Property: Result should not be empty
        assert len(result) > 0, (
            f"get_pending_approvals() should return non-empty list | "
            f"expected={len(pending_approvals)}, got={len(result)}"
        )
        
        # Property: Result should have the same number of approvals
        assert len(result) == len(pending_approvals), (
            f"get_pending_approvals() should return all pending approvals | "
            f"expected={len(pending_approvals)}, got={len(result)}"
        )
        
        # Property: Result should be ordered by expires_at ascending
        for i in range(len(result) - 1):
            current_expiry = result[i].approval_request.expires_at
            next_expiry = result[i + 1].approval_request.expires_at
            
            assert current_expiry <= next_expiry, (
                f"Pending approvals should be ordered by expires_at ASC | "
                f"index={i} | "
                f"current_expiry={current_expiry.isoformat()} | "
                f"next_expiry={next_expiry.isoformat()} | "
                f"current_expiry > next_expiry (VIOLATION)"
            )
        
        # Additional property: The first approval should have the earliest expiry
        earliest_expiry = min(a.expires_at for a in pending_approvals)
        first_result_expiry = result[0].approval_request.expires_at
        
        assert first_result_expiry == earliest_expiry, (
            f"First approval should have earliest expiry | "
            f"expected={earliest_expiry.isoformat()} | "
            f"got={first_result_expiry.isoformat()}"
        )
        
        # Additional property: The last approval should have the latest expiry
        latest_expiry = max(a.expires_at for a in pending_approvals)
        last_result_expiry = result[-1].approval_request.expires_at
        
        assert last_result_expiry == latest_expiry, (
            f"Last approval should have latest expiry | "
            f"expected={latest_expiry.isoformat()} | "
            f"got={last_result_expiry.isoformat()}"
        )
    
    @settings(max_examples=100, phases=[Phase.generate, Phase.target])
    @given(
        num_approvals=num_approvals_strategy,
        instrument=instrument_strategy,
        side=side_strategy,
        risk_pct=risk_pct_strategy,
        confidence=confidence_strategy,
        request_price=price_strategy,
        reasoning_summary=reasoning_summary_strategy,
    )
    def test_pending_approvals_with_same_expiry_stable_order(
        self,
        num_approvals: int,
        instrument: str,
        side: str,
        risk_pct: Decimal,
        confidence: Decimal,
        request_price: Decimal,
        reasoning_summary: dict,
    ) -> None:
        """
        **Feature: hitl-approval-gateway, Property 14: Pending Approvals Are Ordered By Expiry**
        **Validates: Requirements 7.1**
        
        For any set of pending approval requests with the SAME expiry time,
        get_pending_approvals() SHALL return them in a stable order
        (order is preserved from database query).
        """
        # Quantize Decimal values
        risk_pct = risk_pct.quantize(PRECISION_PERCENT, rounding=ROUND_HALF_EVEN)
        confidence = confidence.quantize(PRECISION_PERCENT, rounding=ROUND_HALF_EVEN)
        request_price = request_price.quantize(PRECISION_PRICE, rounding=ROUND_HALF_EVEN)
        
        # Create HITL configuration
        config = HITLConfig(
            enabled=True,
            timeout_seconds=300,
            slippage_max_percent=Decimal("0.50"),
            allowed_operators={"operator1"},
        )
        
        # Create mock Guardian (unlocked)
        guardian = GuardianIntegration()
        
        # Create HITL Gateway
        gateway = HITLGateway(
            config=config,
            guardian=guardian,
            db_session=None,
        )
        
        # Create multiple pending approval requests with SAME expiry time
        now = datetime.now(timezone.utc)
        same_expiry = now + timedelta(seconds=300)
        pending_approvals: List[ApprovalRequest] = []
        
        for i in range(num_approvals):
            approval_request = ApprovalRequest(
                id=uuid.uuid4(),
                trade_id=uuid.uuid4(),
                instrument=instrument,
                side=side,
                risk_pct=risk_pct,
                confidence=confidence,
                request_price=request_price,
                reasoning_summary=reasoning_summary,
                correlation_id=uuid.uuid4(),
                status=ApprovalStatus.AWAITING_APPROVAL.value,
                requested_at=now,
                expires_at=same_expiry,  # Same expiry for all
                decided_at=None,
                decided_by=None,
                decision_channel=None,
                decision_reason=None,
                row_hash="mock_hash",  # Mock hash for testing
            )
            
            pending_approvals.append(approval_request)
        
        # Mock the _query_pending_approvals method to return our test data
        mock_records = [approval.to_dict() for approval in pending_approvals]
        gateway._query_pending_approvals = Mock(return_value=mock_records)
        
        # Call get_pending_approvals()
        result = gateway.get_pending_approvals()
        
        # Property: Result should not be empty
        assert len(result) > 0, (
            f"get_pending_approvals() should return non-empty list | "
            f"expected={len(pending_approvals)}, got={len(result)}"
        )
        
        # Property: Result should have the same number of approvals
        assert len(result) == len(pending_approvals), (
            f"get_pending_approvals() should return all pending approvals | "
            f"expected={len(pending_approvals)}, got={len(result)}"
        )
        
        # Property: All approvals should have the same expiry time
        for i, pending_info in enumerate(result):
            assert pending_info.approval_request.expires_at == same_expiry, (
                f"All approvals should have same expiry | "
                f"index={i} | "
                f"expected={same_expiry.isoformat()} | "
                f"got={pending_info.approval_request.expires_at.isoformat()}"
            )
        
        # Property: Order should be stable (same as input order)
        for i, pending_info in enumerate(result):
            expected_id = pending_approvals[i].id
            actual_id = pending_info.approval_request.id
            
            assert actual_id == expected_id, (
                f"Order should be stable when expiry times are equal | "
                f"index={i} | "
                f"expected_id={expected_id} | "
                f"actual_id={actual_id}"
            )
    
    @settings(max_examples=100, phases=[Phase.generate, Phase.target])
    @given(
        instrument=instrument_strategy,
        side=side_strategy,
        risk_pct=risk_pct_strategy,
        confidence=confidence_strategy,
        request_price=price_strategy,
        reasoning_summary=reasoning_summary_strategy,
    )
    def test_empty_pending_approvals_returns_empty_list(
        self,
        instrument: str,
        side: str,
        risk_pct: Decimal,
        confidence: Decimal,
        request_price: Decimal,
        reasoning_summary: dict,
    ) -> None:
        """
        **Feature: hitl-approval-gateway, Property 14: Pending Approvals Are Ordered By Expiry**
        **Validates: Requirements 7.1**
        
        When there are NO pending approval requests,
        get_pending_approvals() SHALL return an empty list.
        """
        # Quantize Decimal values
        risk_pct = risk_pct.quantize(PRECISION_PERCENT, rounding=ROUND_HALF_EVEN)
        confidence = confidence.quantize(PRECISION_PERCENT, rounding=ROUND_HALF_EVEN)
        request_price = request_price.quantize(PRECISION_PRICE, rounding=ROUND_HALF_EVEN)
        
        # Create HITL configuration
        config = HITLConfig(
            enabled=True,
            timeout_seconds=300,
            slippage_max_percent=Decimal("0.50"),
            allowed_operators={"operator1"},
        )
        
        # Create mock Guardian (unlocked)
        guardian = GuardianIntegration()
        
        # Create HITL Gateway
        gateway = HITLGateway(
            config=config,
            guardian=guardian,
            db_session=None,
        )
        
        # Mock the _query_pending_approvals method to return empty list
        gateway._query_pending_approvals = Mock(return_value=[])
        
        # Call get_pending_approvals()
        result = gateway.get_pending_approvals()
        
        # Property: Result should be an empty list
        assert result == [], (
            f"get_pending_approvals() should return empty list when no pending approvals | "
            f"expected=[], got={result}"
        )
        
        # Property: Result should have length 0
        assert len(result) == 0, (
            f"get_pending_approvals() should return list with length 0 | "
            f"expected=0, got={len(result)}"
        )


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    "TestPendingApprovalsOrdering",
]

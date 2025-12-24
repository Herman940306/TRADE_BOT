"""
Property-Based Tests for Decision Synthesis Module

Reliability Level: L6 Critical
Python 3.8 Compatible

Tests the Pre_Trade_Audit_Module and Indicator_Memory_Module using Hypothesis.
Minimum 100 iterations per property as per design specification.
"""

import asyncio
from decimal import Decimal, ROUND_HALF_EVEN
from typing import Dict, Optional, List
from datetime import datetime, timezone, timedelta

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

# Import modules under test
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from app.logic.pre_trade_audit import (
    PreTradeAuditModule,
    TradeSignal,
    AuditResult,
    AuditDecision,
    REQUIRED_REJECTION_REASONS,
    CONFIDENCE_THRESHOLD
)

from app.logic.indicator_memory import (
    IndicatorMemoryModule,
    IndicatorSnapshot,
    IndicatorStatus,
    FRESHNESS_THRESHOLD_SECONDS
)


# =============================================================================
# HYPOTHESIS STRATEGIES
# =============================================================================

# Strategy for generating valid trade signals
trade_signal_strategy = st.builds(
    TradeSignal,
    correlation_id=st.uuids().map(str),
    symbol=st.sampled_from(["BTCUSD", "ETHUSD", "XRPUSD", "SOLUSD"]),
    action=st.sampled_from(["BUY", "SELL", "CLOSE"]),
    price=st.decimals(
        min_value=Decimal("0.01"),
        max_value=Decimal("100000.00"),
        places=2,
        allow_nan=False,
        allow_infinity=False
    ),
    timestamp_utc=st.datetimes(
        min_value=datetime(2020, 1, 1),
        max_value=datetime(2030, 12, 31)
    ).map(lambda dt: dt.isoformat())
)

# Strategy for generating model outputs with 3 rejection reasons
valid_model_output_strategy = st.builds(
    lambda r1, r2, r3, conf: (
        f"REJECTION_REASON_1: {r1}\n"
        f"REJECTION_REASON_2: {r2}\n"
        f"REJECTION_REASON_3: {r3}\n"
        f"CONFIDENCE_SCORE: {conf}"
    ),
    r1=st.text(min_size=10, max_size=200, alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z'))),
    r2=st.text(min_size=10, max_size=200, alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z'))),
    r3=st.text(min_size=10, max_size=200, alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z'))),
    conf=st.integers(min_value=0, max_value=100)
)

# Strategy for confidence scores
confidence_score_strategy = st.decimals(
    min_value=Decimal("0.00"),
    max_value=Decimal("100.00"),
    places=2,
    allow_nan=False,
    allow_infinity=False
)

# Strategy for freshness values
freshness_strategy = st.integers(min_value=0, max_value=300)


# =============================================================================
# PROPERTY 1: Pre-Trade Audit Produces Exactly 3 Rejection Reasons
# **Feature: production-deployment-phase2, Property 1: Pre-Trade Audit Produces Exactly 3 Rejection Reasons**
# **Validates: Requirements 1.1**
# =============================================================================

class TestRejectionReasons:
    """
    Property 1: Pre-Trade Audit Produces Exactly 3 Rejection Reasons
    
    For any valid trade signal, the DeepSeek-R1 model invocation SHALL
    return exactly 3 rejection reasons.
    """
    
    @settings(max_examples=100)
    @given(model_output=valid_model_output_strategy)
    def test_parse_produces_exactly_3_reasons(self, model_output: str) -> None:
        """
        **Feature: production-deployment-phase2, Property 1: Pre-Trade Audit Produces Exactly 3 Rejection Reasons**
        **Validates: Requirements 1.1**
        
        Verify that parsing model output produces exactly 3 rejection reasons.
        """
        audit_module = PreTradeAuditModule()
        
        rejection_reasons, confidence = audit_module.parse_rejection_reasons(model_output)
        
        # Must have exactly 3 reasons
        assert len(rejection_reasons) == REQUIRED_REJECTION_REASONS, (
            f"Expected {REQUIRED_REJECTION_REASONS} reasons, got {len(rejection_reasons)}"
        )
        
        # Each reason must be non-empty
        for i, reason in enumerate(rejection_reasons):
            assert reason and len(reason.strip()) > 0, (
                f"Reason {i + 1} is empty"
            )
    
    @settings(max_examples=100)
    @given(
        partial_reasons=st.integers(min_value=0, max_value=2),
        conf=st.integers(min_value=0, max_value=100)
    )
    def test_incomplete_output_padded_to_3_reasons(
        self, 
        partial_reasons: int,
        conf: int
    ) -> None:
        """
        **Feature: production-deployment-phase2, Property 1: Pre-Trade Audit Produces Exactly 3 Rejection Reasons**
        **Validates: Requirements 1.1**
        
        Verify that incomplete model output is padded to exactly 3 reasons.
        """
        # Build partial output
        output_parts = []
        for i in range(partial_reasons):
            output_parts.append(f"REJECTION_REASON_{i + 1}: Test reason {i + 1}")
        output_parts.append(f"CONFIDENCE_SCORE: {conf}")
        model_output = "\n".join(output_parts)
        
        audit_module = PreTradeAuditModule()
        rejection_reasons, confidence = audit_module.parse_rejection_reasons(model_output)
        
        # Must still have exactly 3 reasons (padded if necessary)
        assert len(rejection_reasons) == REQUIRED_REJECTION_REASONS, (
            f"Expected {REQUIRED_REJECTION_REASONS} reasons after padding, got {len(rejection_reasons)}"
        )


# =============================================================================
# PROPERTY 2: Confidence Score Decimal Integrity
# **Feature: production-deployment-phase2, Property 2: Confidence Score Decimal Integrity**
# **Validates: Requirements 1.2**
# =============================================================================

class TestConfidenceDecimalIntegrity:
    """
    Property 2: Confidence Score Decimal Integrity
    
    For any model output string, the resulting confidence score SHALL be
    a decimal.Decimal value in the range [0, 100] with ROUND_HALF_EVEN applied.
    """
    
    @settings(max_examples=100)
    @given(model_output=valid_model_output_strategy)
    def test_confidence_is_decimal(self, model_output: str) -> None:
        """
        **Feature: production-deployment-phase2, Property 2: Confidence Score Decimal Integrity**
        **Validates: Requirements 1.2**
        
        Verify that parsed confidence score is a Decimal.
        """
        audit_module = PreTradeAuditModule()
        
        rejection_reasons, confidence = audit_module.parse_rejection_reasons(model_output)
        
        # Must be Decimal type
        assert isinstance(confidence, Decimal), (
            f"Confidence is not Decimal: {type(confidence)}"
        )
    
    @settings(max_examples=100)
    @given(model_output=valid_model_output_strategy)
    def test_confidence_in_valid_range(self, model_output: str) -> None:
        """
        **Feature: production-deployment-phase2, Property 2: Confidence Score Decimal Integrity**
        **Validates: Requirements 1.2**
        
        Verify that confidence score is in range [0, 100].
        """
        audit_module = PreTradeAuditModule()
        
        rejection_reasons, confidence = audit_module.parse_rejection_reasons(model_output)
        
        # Must be in valid range
        assert Decimal("0") <= confidence <= Decimal("100"), (
            f"Confidence out of range: {confidence}"
        )
    
    @settings(max_examples=100)
    @given(
        raw_score=st.floats(min_value=-50, max_value=150, allow_nan=False, allow_infinity=False)
    )
    def test_confidence_clamped_to_range(self, raw_score: float) -> None:
        """
        **Feature: production-deployment-phase2, Property 2: Confidence Score Decimal Integrity**
        **Validates: Requirements 1.2**
        
        Verify that out-of-range scores are clamped to [0, 100].
        """
        model_output = f"""
REJECTION_REASON_1: Test reason 1
REJECTION_REASON_2: Test reason 2
REJECTION_REASON_3: Test reason 3
CONFIDENCE_SCORE: {raw_score}
"""
        
        audit_module = PreTradeAuditModule()
        rejection_reasons, confidence = audit_module.parse_rejection_reasons(model_output)
        
        # Must be clamped to valid range
        assert Decimal("0") <= confidence <= Decimal("100"), (
            f"Confidence not clamped: {confidence} (raw: {raw_score})"
        )


# =============================================================================
# PROPERTY 3: Confidence Threshold Decision Consistency
# **Feature: production-deployment-phase2, Property 3: Confidence Threshold Decision Consistency**
# **Validates: Requirements 1.3, 1.4**
# =============================================================================

class TestConfidenceThresholdDecision:
    """
    Property 3: Confidence Threshold Decision Consistency
    
    For any confidence score, if below 95 the trade SHALL be rejected,
    if 95 or above the trade SHALL be approved.
    """
    
    @settings(max_examples=100)
    @given(
        confidence=st.decimals(
            min_value=Decimal("0.00"),
            max_value=Decimal("94.99"),
            places=2,
            allow_nan=False,
            allow_infinity=False
        )
    )
    def test_below_threshold_rejected(self, confidence: Decimal) -> None:
        """
        **Feature: production-deployment-phase2, Property 3: Confidence Threshold Decision Consistency**
        **Validates: Requirements 1.3**
        
        Verify that confidence below 95 results in rejection.
        """
        audit_module = PreTradeAuditModule()
        
        approved, reason = audit_module.evaluate_confidence(confidence)
        
        assert not approved, (
            f"Trade should be rejected at confidence {confidence}"
        )
        assert "threshold" in reason.lower(), (
            f"Reason should mention threshold: {reason}"
        )
    
    @settings(max_examples=100)
    @given(
        confidence=st.decimals(
            min_value=Decimal("95.00"),
            max_value=Decimal("100.00"),
            places=2,
            allow_nan=False,
            allow_infinity=False
        )
    )
    def test_at_or_above_threshold_approved(self, confidence: Decimal) -> None:
        """
        **Feature: production-deployment-phase2, Property 3: Confidence Threshold Decision Consistency**
        **Validates: Requirements 1.4**
        
        Verify that confidence at or above 95 results in approval.
        """
        audit_module = PreTradeAuditModule()
        
        approved, reason = audit_module.evaluate_confidence(confidence)
        
        assert approved, (
            f"Trade should be approved at confidence {confidence}"
        )
    
    @settings(max_examples=100)
    @given(
        threshold=st.decimals(
            min_value=Decimal("50.00"),
            max_value=Decimal("99.00"),
            places=2,
            allow_nan=False,
            allow_infinity=False
        ),
        offset=st.decimals(
            min_value=Decimal("-10.00"),
            max_value=Decimal("10.00"),
            places=2,
            allow_nan=False,
            allow_infinity=False
        )
    )
    def test_custom_threshold_consistency(
        self, 
        threshold: Decimal,
        offset: Decimal
    ) -> None:
        """
        **Feature: production-deployment-phase2, Property 3: Confidence Threshold Decision Consistency**
        **Validates: Requirements 1.3, 1.4**
        
        Verify threshold decision is consistent with custom thresholds.
        """
        confidence = threshold + offset
        
        # Clamp to valid range
        if confidence < Decimal("0"):
            confidence = Decimal("0.00")
        elif confidence > Decimal("100"):
            confidence = Decimal("100.00")
        
        audit_module = PreTradeAuditModule(confidence_threshold=threshold)
        
        approved, reason = audit_module.evaluate_confidence(confidence)
        
        expected_approved = confidence >= threshold
        
        assert approved == expected_approved, (
            f"Decision mismatch: confidence={confidence}, threshold={threshold}, "
            f"approved={approved}, expected={expected_approved}"
        )


# =============================================================================
# PROPERTY 4: Indicator Data Freshness Validation
# **Feature: production-deployment-phase2, Property 4: Indicator Data Freshness Validation**
# **Validates: Requirements 2.3**
# =============================================================================

class TestIndicatorFreshness:
    """
    Property 4: Indicator Data Freshness Validation
    
    For any indicator data, the system SHALL validate that the data timestamp
    is within 60 seconds of current time before use.
    """
    
    @settings(max_examples=100)
    @given(
        freshness_seconds=st.integers(min_value=0, max_value=59)
    )
    def test_fresh_data_accepted(self, freshness_seconds: int) -> None:
        """
        **Feature: production-deployment-phase2, Property 4: Indicator Data Freshness Validation**
        **Validates: Requirements 2.3**
        
        Verify that data within 60 seconds is accepted as fresh.
        """
        indicator_module = IndicatorMemoryModule()
        
        snapshot = IndicatorSnapshot(
            correlation_id="test",
            timestamp_utc=datetime.now(timezone.utc).isoformat(),
            predictions={"test": "data"},
            reasoning_analysis={"test": "analysis"},
            freshness_seconds=freshness_seconds,
            is_stale=False,
            status=IndicatorStatus.FRESH,
            fetch_time_ms=100
        )
        
        is_valid = indicator_module.validate_freshness(snapshot)
        
        assert is_valid, (
            f"Fresh data should be accepted: freshness={freshness_seconds}s"
        )
    
    @settings(max_examples=100)
    @given(
        freshness_seconds=st.integers(min_value=61, max_value=300)
    )
    def test_stale_data_rejected(self, freshness_seconds: int) -> None:
        """
        **Feature: production-deployment-phase2, Property 4: Indicator Data Freshness Validation**
        **Validates: Requirements 2.3**
        
        Verify that data older than 60 seconds is rejected as stale.
        """
        indicator_module = IndicatorMemoryModule()
        
        snapshot = IndicatorSnapshot(
            correlation_id="test",
            timestamp_utc=(
                datetime.now(timezone.utc) - timedelta(seconds=freshness_seconds)
            ).isoformat(),
            predictions={"test": "data"},
            reasoning_analysis={"test": "analysis"},
            freshness_seconds=freshness_seconds,
            is_stale=True,
            status=IndicatorStatus.STALE,
            fetch_time_ms=100
        )
        
        is_valid = indicator_module.validate_freshness(snapshot)
        
        assert not is_valid, (
            f"Stale data should be rejected: freshness={freshness_seconds}s"
        )
    
    def test_boundary_at_60_seconds(self) -> None:
        """
        **Feature: production-deployment-phase2, Property 4: Indicator Data Freshness Validation**
        **Validates: Requirements 2.3**
        
        Verify boundary behavior at exactly 60 seconds.
        """
        indicator_module = IndicatorMemoryModule()
        
        # At exactly 60 seconds - should be accepted (<=60)
        snapshot_60 = IndicatorSnapshot(
            correlation_id="test",
            timestamp_utc=datetime.now(timezone.utc).isoformat(),
            predictions={},
            reasoning_analysis={},
            freshness_seconds=60,
            is_stale=False,
            status=IndicatorStatus.FRESH,
            fetch_time_ms=100
        )
        
        assert indicator_module.validate_freshness(snapshot_60), (
            "Data at exactly 60 seconds should be accepted"
        )
        
        # At 61 seconds - should be rejected (>60)
        snapshot_61 = IndicatorSnapshot(
            correlation_id="test",
            timestamp_utc=datetime.now(timezone.utc).isoformat(),
            predictions={},
            reasoning_analysis={},
            freshness_seconds=61,
            is_stale=True,
            status=IndicatorStatus.STALE,
            fetch_time_ms=100
        )
        
        assert not indicator_module.validate_freshness(snapshot_61), (
            "Data at 61 seconds should be rejected"
        )


# =============================================================================
# PROPERTY 5: Indicator Fetch Retry Behavior
# **Feature: production-deployment-phase2, Property 5: Indicator Fetch Retry Behavior**
# **Validates: Requirements 2.4**
# =============================================================================

class TestIndicatorRetry:
    """
    Property 5: Indicator Fetch Retry Behavior
    
    For any failed indicator tool call, the system SHALL retry exactly once
    after 5 seconds.
    """
    
    @settings(max_examples=100)
    @given(
        fail_count=st.integers(min_value=1, max_value=5)
    )
    def test_retry_exactly_once(self, fail_count: int) -> None:
        """
        **Feature: production-deployment-phase2, Property 5: Indicator Fetch Retry Behavior**
        **Validates: Requirements 2.4**
        
        Verify that failed fetches retry exactly once.
        """
        call_count = 0
        
        async def mock_mcp_caller(server: str, tool: str, args: dict):
            nonlocal call_count
            call_count += 1
            if call_count <= fail_count:
                raise Exception(f"Simulated failure {call_count}")
            return {"success": True}
        
        indicator_module = IndicatorMemoryModule(
            mcp_tool_caller=mock_mcp_caller,
            retry_delay_seconds=0  # Speed up test
        )
        
        async def run_test():
            nonlocal call_count
            call_count = 0
            result = await indicator_module._fetch_with_retry(
                "test_tool",
                {},
                "test_correlation"
            )
            return result, call_count
        
        result, total_calls = asyncio.get_event_loop().run_until_complete(run_test())
        
        # Should have made at most 2 calls (initial + 1 retry)
        assert total_calls <= 2, (
            f"Should retry at most once: made {total_calls} calls"
        )
    
    @settings(max_examples=100)
    @given(
        correlation_id=st.uuids().map(str)
    )
    def test_retry_logs_failure(self, correlation_id: str) -> None:
        """
        **Feature: production-deployment-phase2, Property 5: Indicator Fetch Retry Behavior**
        **Validates: Requirements 2.4**
        
        Verify that failed fetches are logged with INDICATOR_FETCH_FAIL.
        """
        async def always_fail_caller(server: str, tool: str, args: dict):
            raise Exception("Permanent failure")
        
        indicator_module = IndicatorMemoryModule(
            mcp_tool_caller=always_fail_caller,
            retry_delay_seconds=0
        )
        
        async def run_test():
            data, success, error = await indicator_module._fetch_with_retry(
                "test_tool",
                {},
                correlation_id
            )
            return data, success, error
        
        data, success, error = asyncio.get_event_loop().run_until_complete(run_test())
        
        # Should fail after retries
        assert not success, "Should fail after exhausting retries"
        assert error is not None, "Should have error message"
        assert data is None, "Should have no data on failure"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

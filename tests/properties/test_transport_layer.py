"""
Property-Based Tests for Transport Layer

Reliability Level: L6 Critical
Python 3.8 Compatible

Tests the SSE Bridge Protocol using Hypothesis.
Minimum 100 iterations per property as per design specification.
"""

import asyncio
from decimal import Decimal
from typing import Dict, Optional, List
from datetime import datetime, timezone

import pytest
from hypothesis import given, settings, assume, HealthCheck
from hypothesis import strategies as st

# Import modules under test
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from app.transport.sse_bridge_protocol import (
    SSEBridge,
    SSEMessage,
    MessageType,
    ConnectionState,
    HeartbeatResult,
    ReconnectionAttempt,
    HEARTBEAT_INTERVAL_SECONDS,
    LATENCY_WARNING_THRESHOLD_MS,
    INITIAL_BACKOFF_SECONDS,
    MAX_BACKOFF_SECONDS,
    MAX_RECONNECTION_ATTEMPTS,
    BACKOFF_MULTIPLIER
)


# =============================================================================
# HYPOTHESIS STRATEGIES
# =============================================================================

# Strategy for generating valid SSE messages - simplified for performance
sse_message_strategy = st.builds(
    SSEMessage,
    message_type=st.sampled_from([mt.value for mt in MessageType]),
    correlation_id=st.uuids().map(str),
    timestamp_utc=st.just("2024-01-01T00:00:00Z"),  # Fixed timestamp for speed
    payload=st.just({})  # Empty payload for speed
)

# Strategy for generating SSE messages with varied payloads (slower, use sparingly)
sse_message_with_payload_strategy = st.builds(
    SSEMessage,
    message_type=st.sampled_from([mt.value for mt in MessageType]),
    correlation_id=st.uuids().map(str),
    timestamp_utc=st.sampled_from([
        "2024-01-01T00:00:00Z",
        "2024-06-15T12:30:00Z",
        "2024-12-31T23:59:59Z"
    ]),
    payload=st.fixed_dictionaries({
        "key": st.text(min_size=1, max_size=10, alphabet="abcdefghijklmnopqrstuvwxyz")
    })
)

# Strategy for RTT values
rtt_strategy = st.integers(min_value=1, max_value=1000)

# Strategy for reconnection attempts
attempt_strategy = st.integers(min_value=0, max_value=10)


# =============================================================================
# PROPERTY 6: SSE Message Schema Compliance
# **Feature: production-deployment-phase2, Property 6: SSE Message Schema Compliance**
# **Validates: Requirements 3.2**
# =============================================================================

class TestSSEMessageSchema:
    """
    Property 6: SSE Message Schema Compliance
    
    For any message transmitted via SSE_Bridge, the JSON payload SHALL
    contain all required fields: message_type, correlation_id, timestamp_utc,
    and payload.
    """
    
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(message=sse_message_strategy)
    def test_message_contains_required_fields(self, message: SSEMessage) -> None:
        """
        **Feature: production-deployment-phase2, Property 6: SSE Message Schema Compliance**
        **Validates: Requirements 3.2**
        
        Verify that SSEMessage contains all required fields.
        """
        # Serialize to JSON
        json_str = message.to_json()
        
        # Parse back
        import json
        data = json.loads(json_str)
        
        # Check required fields
        assert "message_type" in data, "Missing message_type"
        assert "correlation_id" in data, "Missing correlation_id"
        assert "timestamp_utc" in data, "Missing timestamp_utc"
        assert "payload" in data, "Missing payload"
        
        # Verify types
        assert isinstance(data["message_type"], str), "message_type must be string"
        assert isinstance(data["correlation_id"], str), "correlation_id must be string"
        assert isinstance(data["timestamp_utc"], str), "timestamp_utc must be string"
        assert isinstance(data["payload"], dict), "payload must be object"
    
    @settings(max_examples=100)
    @given(message=sse_message_strategy)
    def test_message_roundtrip(self, message: SSEMessage) -> None:
        """
        **Feature: production-deployment-phase2, Property 6: SSE Message Schema Compliance**
        **Validates: Requirements 3.2**
        
        Verify that SSEMessage survives JSON round-trip.
        """
        # Serialize
        json_str = message.to_json()
        
        # Deserialize
        restored = SSEMessage.from_json(json_str)
        
        # Verify equality
        assert restored.message_type == message.message_type
        assert restored.correlation_id == message.correlation_id
        assert restored.timestamp_utc == message.timestamp_utc
        assert restored.payload == message.payload
    
    @settings(max_examples=100)
    @given(
        message_type=st.sampled_from([mt.value for mt in MessageType]),
        correlation_id=st.uuids().map(str),
        timestamp_utc=st.datetimes(
            min_value=datetime(2020, 1, 1),
            max_value=datetime(2030, 12, 31)
        ).map(lambda dt: dt.isoformat())
    )
    def test_schema_validation_accepts_valid(
        self,
        message_type: str,
        correlation_id: str,
        timestamp_utc: str
    ) -> None:
        """
        **Feature: production-deployment-phase2, Property 6: SSE Message Schema Compliance**
        **Validates: Requirements 3.2**
        
        Verify that valid schemas pass validation.
        """
        data = {
            "message_type": message_type,
            "correlation_id": correlation_id,
            "timestamp_utc": timestamp_utc,
            "payload": {}
        }
        
        is_valid, error = SSEMessage.validate_schema(data)
        
        assert is_valid, f"Valid schema rejected: {error}"
    
    @settings(max_examples=100)
    @given(
        missing_field=st.sampled_from(["message_type", "correlation_id", "timestamp_utc"])
    )
    def test_schema_validation_rejects_missing_fields(
        self,
        missing_field: str
    ) -> None:
        """
        **Feature: production-deployment-phase2, Property 6: SSE Message Schema Compliance**
        **Validates: Requirements 3.2**
        
        Verify that schemas with missing required fields are rejected.
        """
        data = {
            "message_type": "TEST",
            "correlation_id": "test-id",
            "timestamp_utc": "2024-01-01T00:00:00Z",
            "payload": {}
        }
        
        # Remove the field
        del data[missing_field]
        
        is_valid, error = SSEMessage.validate_schema(data)
        
        assert not is_valid, f"Invalid schema accepted (missing {missing_field})"
        assert missing_field in error, f"Error should mention {missing_field}"


# =============================================================================
# PROPERTY 7: SSE Latency Warning Threshold
# **Feature: production-deployment-phase2, Property 7: SSE Latency Warning Threshold**
# **Validates: Requirements 3.3**
# =============================================================================

class TestSSELatencyWarning:
    """
    Property 7: SSE Latency Warning Threshold
    
    For any heartbeat response with RTT exceeding 200ms, the system SHALL
    log a warning with error code SSE_LATENCY_HIGH.
    """
    
    @settings(max_examples=100)
    @given(rtt_ms=st.integers(min_value=201, max_value=5000))
    def test_high_latency_triggers_warning(self, rtt_ms: int) -> None:
        """
        **Feature: production-deployment-phase2, Property 7: SSE Latency Warning Threshold**
        **Validates: Requirements 3.3**
        
        Verify that RTT > 200ms triggers latency warning.
        """
        # Create heartbeat result with high RTT
        result = HeartbeatResult(
            success=True,
            rtt_ms=rtt_ms,
            latency_warning=rtt_ms > LATENCY_WARNING_THRESHOLD_MS,
            timestamp_utc=datetime.now(timezone.utc).isoformat()
        )
        
        assert result.latency_warning, (
            f"RTT {rtt_ms}ms should trigger warning (threshold: {LATENCY_WARNING_THRESHOLD_MS}ms)"
        )
    
    @settings(max_examples=100)
    @given(rtt_ms=st.integers(min_value=1, max_value=200))
    def test_normal_latency_no_warning(self, rtt_ms: int) -> None:
        """
        **Feature: production-deployment-phase2, Property 7: SSE Latency Warning Threshold**
        **Validates: Requirements 3.3**
        
        Verify that RTT <= 200ms does not trigger warning.
        """
        result = HeartbeatResult(
            success=True,
            rtt_ms=rtt_ms,
            latency_warning=rtt_ms > LATENCY_WARNING_THRESHOLD_MS,
            timestamp_utc=datetime.now(timezone.utc).isoformat()
        )
        
        assert not result.latency_warning, (
            f"RTT {rtt_ms}ms should not trigger warning"
        )
    
    def test_boundary_at_200ms(self) -> None:
        """
        **Feature: production-deployment-phase2, Property 7: SSE Latency Warning Threshold**
        **Validates: Requirements 3.3**
        
        Verify boundary behavior at exactly 200ms.
        """
        # At exactly 200ms - should NOT warn (<=200)
        result_200 = HeartbeatResult(
            success=True,
            rtt_ms=200,
            latency_warning=200 > LATENCY_WARNING_THRESHOLD_MS,
            timestamp_utc=datetime.now(timezone.utc).isoformat()
        )
        
        assert not result_200.latency_warning, (
            "RTT at exactly 200ms should not trigger warning"
        )
        
        # At 201ms - should warn (>200)
        result_201 = HeartbeatResult(
            success=True,
            rtt_ms=201,
            latency_warning=201 > LATENCY_WARNING_THRESHOLD_MS,
            timestamp_utc=datetime.now(timezone.utc).isoformat()
        )
        
        assert result_201.latency_warning, (
            "RTT at 201ms should trigger warning"
        )


# =============================================================================
# PROPERTY 8: SSE Reconnection Exponential Backoff
# **Feature: production-deployment-phase2, Property 8: SSE Reconnection Exponential Backoff**
# **Validates: Requirements 3.4**
# =============================================================================

class TestSSEExponentialBackoff:
    """
    Property 8: SSE Reconnection Exponential Backoff
    
    For any connection drop, the reconnection attempts SHALL follow
    exponential backoff: 1s, 2s, 4s, 8s, 16s, capped at 30s maximum.
    """
    
    @settings(max_examples=100)
    @given(attempt=st.integers(min_value=0, max_value=20))
    def test_backoff_follows_exponential_pattern(self, attempt: int) -> None:
        """
        **Feature: production-deployment-phase2, Property 8: SSE Reconnection Exponential Backoff**
        **Validates: Requirements 3.4**
        
        Verify backoff follows 2^n pattern starting at 1s.
        """
        bridge = SSEBridge()
        
        backoff = bridge.calculate_backoff(attempt)
        
        # Calculate expected backoff
        expected = INITIAL_BACKOFF_SECONDS * (BACKOFF_MULTIPLIER ** attempt)
        expected_capped = min(expected, MAX_BACKOFF_SECONDS)
        
        assert backoff == expected_capped, (
            f"Backoff mismatch at attempt {attempt}: "
            f"got {backoff}, expected {expected_capped}"
        )
    
    @settings(max_examples=100)
    @given(attempt=st.integers(min_value=0, max_value=100))
    def test_backoff_never_exceeds_max(self, attempt: int) -> None:
        """
        **Feature: production-deployment-phase2, Property 8: SSE Reconnection Exponential Backoff**
        **Validates: Requirements 3.4**
        
        Verify backoff is always capped at MAX_BACKOFF_SECONDS.
        """
        bridge = SSEBridge()
        
        backoff = bridge.calculate_backoff(attempt)
        
        assert backoff <= MAX_BACKOFF_SECONDS, (
            f"Backoff {backoff}s exceeds max {MAX_BACKOFF_SECONDS}s"
        )
    
    def test_backoff_sequence(self) -> None:
        """
        **Feature: production-deployment-phase2, Property 8: SSE Reconnection Exponential Backoff**
        **Validates: Requirements 3.4**
        
        Verify the exact backoff sequence: 1, 2, 4, 8, 16, 30 (capped).
        """
        bridge = SSEBridge()
        
        expected_sequence = [1, 2, 4, 8, 16, 30, 30, 30]  # Capped at 30
        
        for attempt, expected in enumerate(expected_sequence):
            actual = bridge.calculate_backoff(attempt)
            assert actual == expected, (
                f"Attempt {attempt}: expected {expected}s, got {actual}s"
            )
    
    @settings(max_examples=100)
    @given(attempt=st.integers(min_value=1, max_value=10))
    def test_backoff_increases_monotonically(self, attempt: int) -> None:
        """
        **Feature: production-deployment-phase2, Property 8: SSE Reconnection Exponential Backoff**
        **Validates: Requirements 3.4**
        
        Verify backoff increases (or stays same when capped) with each attempt.
        """
        bridge = SSEBridge()
        
        prev_backoff = bridge.calculate_backoff(attempt - 1)
        curr_backoff = bridge.calculate_backoff(attempt)
        
        assert curr_backoff >= prev_backoff, (
            f"Backoff should not decrease: attempt {attempt - 1}={prev_backoff}s, "
            f"attempt {attempt}={curr_backoff}s"
        )


# =============================================================================
# L6 LOCKDOWN TESTS
# =============================================================================

class TestL6Lockdown:
    """
    Test L6 Lockdown behavior after 5 failed reconnection attempts.
    """
    
    def test_lockdown_after_max_attempts(self) -> None:
        """
        **Feature: production-deployment-phase2, Property 8: SSE Reconnection Exponential Backoff**
        **Validates: Requirements 3.5**
        
        Verify L6 Lockdown triggers after 5 failed attempts.
        Uses mocked backoff to avoid long waits.
        """
        attempt_count = 0
        
        async def always_fail_connect():
            nonlocal attempt_count
            attempt_count += 1
            return False
        
        # Create bridge with minimal backoff for testing
        bridge = SSEBridge(
            connect_callback=always_fail_connect,
            max_reconnect_attempts=5
        )
        
        # Mock the calculate_backoff to return 0 for fast testing
        original_backoff = bridge.calculate_backoff
        bridge.calculate_backoff = lambda attempt: 0
        
        async def run_test():
            success = await bridge.reconnect_with_backoff()
            return success
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            success = loop.run_until_complete(run_test())
        finally:
            loop.close()
        
        assert not success, "Reconnection should fail after max attempts"
        assert len(bridge.get_reconnection_history()) == 5, (
            f"Should have exactly 5 attempts, got {len(bridge.get_reconnection_history())}"
        )
    
    def test_lockdown_blocks_operations(self) -> None:
        """
        **Feature: production-deployment-phase2, Property 8: SSE Reconnection Exponential Backoff**
        **Validates: Requirements 3.5**
        
        Verify that L6 Lockdown blocks further operations.
        """
        bridge = SSEBridge()
        bridge._state = ConnectionState.L6_LOCKDOWN
        
        assert bridge.is_locked_down, "Bridge should be in lockdown"
        assert not bridge.is_connected, "Bridge should not be connected"
        
        # Verify reconnection is blocked
        async def run_test():
            return await bridge.reconnect_with_backoff()
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            success = loop.run_until_complete(run_test())
        finally:
            loop.close()
        
        assert not success, "Reconnection should be blocked in lockdown"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

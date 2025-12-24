"""
Property-Based Tests for Session Management

Reliability Level: L6 Critical
Python 3.8 Compatible

Tests the Session Manager using Hypothesis.
Minimum 100 iterations per property as per design specification.
"""

from typing import List, Set
from datetime import datetime, timezone, timedelta

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

# Import modules under test
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from app.transport.session_manager import (
    SessionManager,
    Session,
    SessionState,
    SessionEvent,
    SESSION_TIMEOUT_SECONDS
)


# =============================================================================
# HYPOTHESIS STRATEGIES
# =============================================================================

# Strategy for usernames
username_strategy = st.text(
    min_size=3,
    max_size=20,
    alphabet=st.characters(whitelist_categories=('L', 'N'))
)

# Strategy for number of concurrent users
user_count_strategy = st.integers(min_value=2, max_value=20)


# =============================================================================
# PROPERTY 14: Multi-User Session Isolation
# **Feature: production-deployment-phase2, Property 14: Multi-User Session Isolation**
# **Validates: Requirements 6.4**
# =============================================================================

class TestSessionIsolation:
    """
    Property 14: Multi-User Session Isolation
    
    For any set of simultaneous user connections, each session SHALL have
    a unique session_id and maintain isolated session context.
    """
    
    @settings(max_examples=100)
    @given(user_count=user_count_strategy)
    def test_unique_session_ids(self, user_count: int) -> None:
        """
        **Feature: production-deployment-phase2, Property 14: Multi-User Session Isolation**
        **Validates: Requirements 6.4**
        
        Verify that each session has a unique session_id.
        """
        manager = SessionManager()
        session_ids = set()  # type: Set[str]
        
        # Create multiple sessions
        for i in range(user_count):
            session = manager.create_session(f"user_{i}")
            
            # Verify uniqueness
            assert session.session_id not in session_ids, (
                f"Duplicate session_id: {session.session_id}"
            )
            session_ids.add(session.session_id)
        
        # Verify count
        assert len(session_ids) == user_count, (
            f"Expected {user_count} unique IDs, got {len(session_ids)}"
        )
    
    @settings(max_examples=100)
    @given(
        usernames=st.lists(
            username_strategy,
            min_size=2,
            max_size=10,
            unique=True
        )
    )
    def test_session_context_isolation(self, usernames: List[str]) -> None:
        """
        **Feature: production-deployment-phase2, Property 14: Multi-User Session Isolation**
        **Validates: Requirements 6.4**
        
        Verify that session contexts are isolated between users.
        """
        manager = SessionManager()
        sessions = []  # type: List[Session]
        
        # Create sessions with unique context data
        for i, username in enumerate(usernames):
            session = manager.create_session(username)
            session.context["user_data"] = f"private_data_{i}"
            session.context["secret"] = f"secret_{username}"
            sessions.append(session)
        
        # Verify each session has its own context
        for i, session in enumerate(sessions):
            assert session.context["user_data"] == f"private_data_{i}", (
                f"Context data leaked for session {session.session_id}"
            )
            assert session.context["secret"] == f"secret_{usernames[i]}", (
                f"Secret leaked for session {session.session_id}"
            )
            
            # Verify no cross-contamination
            for j, other in enumerate(sessions):
                if i != j:
                    assert session.context != other.context, (
                        f"Sessions {i} and {j} share context"
                    )
    
    @settings(max_examples=100)
    @given(user_count=user_count_strategy)
    def test_session_checksums_unique(self, user_count: int) -> None:
        """
        **Feature: production-deployment-phase2, Property 14: Multi-User Session Isolation**
        **Validates: Requirements 6.4**
        
        Verify that session checksums are unique for integrity.
        """
        manager = SessionManager()
        checksums = set()  # type: Set[str]
        
        for i in range(user_count):
            session = manager.create_session(f"user_{i}")
            checksum = session.get_checksum()
            
            # Checksums should be unique
            assert checksum not in checksums, (
                f"Duplicate checksum: {checksum}"
            )
            checksums.add(checksum)
    
    def test_session_validation_isolation(self) -> None:
        """
        **Feature: production-deployment-phase2, Property 14: Multi-User Session Isolation**
        **Validates: Requirements 6.4**
        
        Verify that validating one session doesn't affect others.
        """
        manager = SessionManager()
        
        # Create two sessions
        session1 = manager.create_session("user1")
        session2 = manager.create_session("user2")
        
        # Validate session1
        is_valid, _ = manager.validate_session(session1.session_id)
        assert is_valid, "Session1 should be valid"
        
        # Session2 should still be independent
        session2_retrieved = manager.get_session(session2.session_id)
        assert session2_retrieved is not None, "Session2 should exist"
        assert session2_retrieved.session_id != session1.session_id, (
            "Sessions should have different IDs"
        )
    
    def test_terminating_one_session_preserves_others(self) -> None:
        """
        **Feature: production-deployment-phase2, Property 14: Multi-User Session Isolation**
        **Validates: Requirements 6.4**
        
        Verify that terminating one session doesn't affect others.
        """
        manager = SessionManager()
        
        # Create multiple sessions
        sessions = [
            manager.create_session(f"user_{i}")
            for i in range(5)
        ]
        
        # Terminate the middle session
        manager.terminate_session(sessions[2].session_id, "test")
        
        # Other sessions should still be valid
        for i, session in enumerate(sessions):
            if i == 2:
                assert session.state == SessionState.TERMINATED
            else:
                retrieved = manager.get_session(session.session_id)
                assert retrieved is not None, (
                    f"Session {i} should still exist"
                )


# =============================================================================
# SESSION TIMEOUT TESTS
# =============================================================================

class TestSessionTimeout:
    """
    Test 30-minute inactivity timeout behavior.
    """
    
    def test_session_expires_after_timeout(self) -> None:
        """
        Verify session expires after inactivity timeout.
        """
        # Use short timeout for testing
        manager = SessionManager(timeout_seconds=1)
        
        session = manager.create_session("test_user")
        
        # Manually set last_activity to past
        session.last_activity = datetime.now(timezone.utc) - timedelta(seconds=2)
        
        # Session should be expired
        assert session.is_expired(), "Session should be expired"
        
        # Get should return None for expired session
        retrieved = manager.get_session(session.session_id)
        assert retrieved is None, "Expired session should not be retrievable"
    
    def test_activity_resets_timeout(self) -> None:
        """
        Verify that activity resets the timeout counter.
        """
        manager = SessionManager(timeout_seconds=60)
        
        session = manager.create_session("test_user")
        
        # Set last_activity to 30 seconds ago
        session.last_activity = datetime.now(timezone.utc) - timedelta(seconds=30)
        
        # Update activity
        session.update_activity()
        
        # Session should not be expired
        assert not session.is_expired(), "Session should not be expired after activity"
        assert session.get_idle_seconds() < 5, "Idle time should be reset"
    
    def test_default_timeout_is_30_minutes(self) -> None:
        """
        Verify default timeout is 30 minutes (1800 seconds).
        """
        assert SESSION_TIMEOUT_SECONDS == 1800, (
            f"Default timeout should be 1800s, got {SESSION_TIMEOUT_SECONDS}"
        )
        
        manager = SessionManager()
        session = manager.create_session("test_user")
        
        assert session.timeout_seconds == 1800, (
            f"Session timeout should be 1800s, got {session.timeout_seconds}"
        )


# =============================================================================
# SESSION EVENT AUDIT TESTS
# =============================================================================

class TestSessionAudit:
    """
    Test session event logging for audit trail.
    """
    
    def test_session_creation_logged(self) -> None:
        """
        Verify session creation is logged.
        """
        manager = SessionManager()
        session = manager.create_session("audit_user")
        
        events = manager.get_session_events(session.session_id)
        
        assert len(events) >= 1, "Should have at least one event"
        assert events[0].event_type == "SESSION_CREATED", (
            f"First event should be SESSION_CREATED, got {events[0].event_type}"
        )
    
    def test_session_termination_logged(self) -> None:
        """
        Verify session termination is logged.
        """
        manager = SessionManager()
        session = manager.create_session("audit_user")
        
        manager.terminate_session(session.session_id, "test_reason")
        
        events = manager.get_session_events(session.session_id)
        
        # Should have creation and termination events
        event_types = [e.event_type for e in events]
        assert "SESSION_CREATED" in event_types
        assert "SESSION_TERMINATED" in event_types
    
    def test_events_have_timestamps(self) -> None:
        """
        Verify all events have timestamps.
        """
        manager = SessionManager()
        session = manager.create_session("audit_user")
        manager.terminate_session(session.session_id, "test")
        
        events = manager.get_session_events(session.session_id)
        
        for event in events:
            assert event.timestamp_utc is not None, "Event should have timestamp"
            assert len(event.timestamp_utc) > 0, "Timestamp should not be empty"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

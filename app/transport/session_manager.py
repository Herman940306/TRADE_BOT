"""
Session Manager - Multi-User Access Control

Reliability Level: L6 Critical
Input Constraints: Valid credentials required
Side Effects: Network I/O, session state management

This module implements secure multi-user session management:
- Unique session_id per connection
- 30-minute inactivity timeout
- Session isolation between users
- Audit logging for all session events

Python 3.8 Compatible - No union type hints (X | None)
PRIVACY: No credentials stored in code.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any, Callable, Awaitable
from enum import Enum
import asyncio
import time
import uuid
import logging
from datetime import datetime, timezone, timedelta
import hashlib

# Configure logging
logger = logging.getLogger("session_manager")


# =============================================================================
# CONSTANTS
# =============================================================================

# Session timeout in seconds (30 minutes)
SESSION_TIMEOUT_SECONDS = 1800

# Heartbeat interval for activity check
ACTIVITY_CHECK_INTERVAL_SECONDS = 60

# Error codes
ERROR_SESSION_TIMEOUT = "SESSION_TIMEOUT"
ERROR_SESSION_INVALID = "SESSION_INVALID"
ERROR_AUTH_FAILED = "AUTH_FAILED"


# =============================================================================
# ENUMS
# =============================================================================

class SessionState(Enum):
    """
    Session lifecycle states.
    
    Reliability Level: L5 High
    """
    INITIALIZING = "INITIALIZING"
    ACTIVE = "ACTIVE"
    IDLE = "IDLE"
    EXPIRED = "EXPIRED"
    TERMINATED = "TERMINATED"


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class Session:
    """
    User session with isolation and timeout tracking.
    
    Reliability Level: L6 Critical
    Input Constraints: session_id must be unique
    Side Effects: None
    """
    session_id: str
    username: str
    state: SessionState
    created_at: datetime
    last_activity: datetime
    timeout_seconds: int
    context: Dict[str, Any] = field(default_factory=dict)
    
    def is_expired(self) -> bool:
        """Check if session has expired due to inactivity."""
        if self.state in (SessionState.EXPIRED, SessionState.TERMINATED):
            return True
        
        elapsed = (datetime.now(timezone.utc) - self.last_activity).total_seconds()
        return elapsed > self.timeout_seconds
    
    def update_activity(self) -> None:
        """Update last activity timestamp."""
        self.last_activity = datetime.now(timezone.utc)
        if self.state == SessionState.IDLE:
            self.state = SessionState.ACTIVE
    
    def get_idle_seconds(self) -> int:
        """Get seconds since last activity."""
        return int((datetime.now(timezone.utc) - self.last_activity).total_seconds())
    
    def get_checksum(self) -> str:
        """Generate session checksum for integrity verification."""
        content = f"{self.session_id}:{self.username}:{self.created_at.isoformat()}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]


@dataclass
class SessionEvent:
    """
    Audit event for session activity.
    
    Reliability Level: L5 High
    """
    session_id: str
    event_type: str
    timestamp_utc: str
    details: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# SESSION MANAGER
# =============================================================================

class SessionManager:
    """
    Multi-user session management with isolation and timeout.
    
    Reliability Level: L6 Critical
    Input Constraints: None
    Side Effects: Manages session state, network I/O
    
    Implements:
    - Unique session_id generation (Property 14)
    - 30-minute inactivity timeout
    - Session isolation between users
    - Audit logging
    """
    
    def __init__(
        self,
        timeout_seconds: int = SESSION_TIMEOUT_SECONDS,
        activity_check_interval: int = ACTIVITY_CHECK_INTERVAL_SECONDS
    ) -> None:
        """
        Initialize Session Manager.
        
        Args:
            timeout_seconds: Inactivity timeout (default: 30 minutes)
            activity_check_interval: How often to check for idle sessions
        """
        self._timeout_seconds = timeout_seconds
        self._activity_check_interval = activity_check_interval
        
        # Active sessions: session_id -> Session
        self._sessions: Dict[str, Session] = {}
        
        # Event log
        self._events: List[SessionEvent] = []
        
        # Background task for timeout checking
        self._timeout_task: Optional[asyncio.Task] = None
    
    @property
    def active_session_count(self) -> int:
        """Get count of active sessions."""
        return sum(
            1 for s in self._sessions.values()
            if s.state == SessionState.ACTIVE
        )
    
    def generate_session_id(self) -> str:
        """
        Generate unique session ID.
        
        Reliability Level: L6 Critical
        
        Returns:
            Unique session identifier
        """
        return str(uuid.uuid4())
    
    def create_session(
        self,
        username: str,
        session_id: Optional[str] = None
    ) -> Session:
        """
        Create a new user session.
        
        Reliability Level: L6 Critical
        Input Constraints: username required
        Side Effects: Adds session to registry
        
        Args:
            username: User identifier
            session_id: Optional pre-generated ID
            
        Returns:
            New Session instance
        """
        sid = session_id or self.generate_session_id()
        now = datetime.now(timezone.utc)
        
        session = Session(
            session_id=sid,
            username=username,
            state=SessionState.INITIALIZING,
            created_at=now,
            last_activity=now,
            timeout_seconds=self._timeout_seconds
        )
        
        self._sessions[sid] = session
        
        self._log_event(sid, "SESSION_CREATED", {
            "username": username,
            "timeout_seconds": self._timeout_seconds
        })
        
        logger.info(
            f"[SESSION_CREATED] session_id={sid} username={username}"
        )
        
        return session
    
    def get_session(self, session_id: str) -> Optional[Session]:
        """
        Get session by ID.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Session if found and not expired, None otherwise
        """
        session = self._sessions.get(session_id)
        
        if session is None:
            return None
        
        if session.is_expired():
            self._expire_session(session_id)
            return None
        
        return session
    
    def validate_session(self, session_id: str) -> tuple:
        """
        Validate session and update activity.
        
        Args:
            session_id: Session to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        session = self._sessions.get(session_id)
        
        if session is None:
            return (False, "Session not found")
        
        if session.is_expired():
            self._expire_session(session_id)
            return (False, "Session expired due to inactivity")
        
        if session.state == SessionState.TERMINATED:
            return (False, "Session has been terminated")
        
        # Update activity
        session.update_activity()
        
        return (True, None)
    
    def _expire_session(self, session_id: str) -> None:
        """
        Mark session as expired.
        
        Args:
            session_id: Session to expire
        """
        session = self._sessions.get(session_id)
        if session is None:
            return
        
        session.state = SessionState.EXPIRED
        
        self._log_event(session_id, "SESSION_EXPIRED", {
            "idle_seconds": session.get_idle_seconds(),
            "timeout_seconds": session.timeout_seconds
        })
        
        logger.warning(
            f"[{ERROR_SESSION_TIMEOUT}] session_id={session_id} "
            f"username={session.username} "
            f"idle_seconds={session.get_idle_seconds()}"
        )
    
    def terminate_session(self, session_id: str, reason: str = "user_request") -> bool:
        """
        Terminate a session.
        
        Args:
            session_id: Session to terminate
            reason: Termination reason
            
        Returns:
            True if session was terminated
        """
        session = self._sessions.get(session_id)
        if session is None:
            return False
        
        session.state = SessionState.TERMINATED
        
        self._log_event(session_id, "SESSION_TERMINATED", {
            "reason": reason,
            "duration_seconds": int(
                (datetime.now(timezone.utc) - session.created_at).total_seconds()
            )
        })
        
        logger.info(
            f"[SESSION_TERMINATED] session_id={session_id} "
            f"username={session.username} reason={reason}"
        )
        
        return True
    
    def _log_event(
        self,
        session_id: str,
        event_type: str,
        details: Dict[str, Any]
    ) -> None:
        """Log session event for audit."""
        event = SessionEvent(
            session_id=session_id,
            event_type=event_type,
            timestamp_utc=datetime.now(timezone.utc).isoformat(),
            details=details
        )
        self._events.append(event)
    
    async def _timeout_check_loop(self) -> None:
        """Background loop to check for expired sessions."""
        while True:
            try:
                await asyncio.sleep(self._activity_check_interval)
                
                # Check all sessions for expiration
                for session_id in list(self._sessions.keys()):
                    session = self._sessions.get(session_id)
                    if session and session.is_expired():
                        self._expire_session(session_id)
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[TIMEOUT_CHECK_ERROR] {str(e)}")
    
    async def start_session(
        self,
        username: str,
        session_id: Optional[str] = None,
        host: str = "nas.local",
        port: int = 22
    ) -> None:
        """
        Start an interactive session.
        
        Reliability Level: L6 Critical
        Input Constraints: Valid credentials required
        Side Effects: Network I/O, session management
        
        Args:
            username: User identifier
            session_id: Optional pre-generated session ID
            host: NAS hostname
            port: SSH port
        """
        session = self.create_session(username, session_id)
        session.state = SessionState.ACTIVE
        
        # Start timeout checker
        self._timeout_task = asyncio.create_task(self._timeout_check_loop())
        
        print(f"[SESSION] Started: {session.session_id}")
        print(f"[SESSION] User: {username}")
        print(f"[SESSION] Timeout: {self._timeout_seconds // 60} minutes")
        print(f"[SESSION] Checksum: {session.get_checksum()}")
        print()
        
        try:
            # Import and use SSE bridge
            from app.transport.sse_bridge_protocol import SSEBridge, ConnectionState
            
            bridge = SSEBridge()
            
            # Keep session alive
            while not session.is_expired():
                session.update_activity()
                await asyncio.sleep(10)
                
                # Check bridge state
                if bridge.is_locked_down:
                    print("[ALERT] Bridge entered L6 Lockdown")
                    break
                    
        except KeyboardInterrupt:
            print("\n[SESSION] Interrupted by user")
        except Exception as e:
            logger.error(f"[SESSION_ERROR] {str(e)}")
            print(f"[ERROR] {str(e)}")
        finally:
            # Cleanup
            if self._timeout_task:
                self._timeout_task.cancel()
                try:
                    await self._timeout_task
                except asyncio.CancelledError:
                    pass
            
            self.terminate_session(session.session_id, "session_end")
            print(f"[SESSION] Ended: {session.session_id}")
    
    def get_all_sessions(self) -> List[Session]:
        """Get all sessions (for admin purposes)."""
        return list(self._sessions.values())
    
    def get_session_events(
        self,
        session_id: Optional[str] = None
    ) -> List[SessionEvent]:
        """
        Get session events for audit.
        
        Args:
            session_id: Filter by session, or None for all
            
        Returns:
            List of session events
        """
        if session_id:
            return [e for e in self._events if e.session_id == session_id]
        return self._events.copy()
    
    def cleanup_expired_sessions(self) -> int:
        """
        Remove expired sessions from registry.
        
        Returns:
            Number of sessions cleaned up
        """
        expired = [
            sid for sid, session in self._sessions.items()
            if session.state in (SessionState.EXPIRED, SessionState.TERMINATED)
        ]
        
        for sid in expired:
            del self._sessions[sid]
        
        if expired:
            logger.info(f"[SESSION_CLEANUP] Removed {len(expired)} sessions")
        
        return len(expired)

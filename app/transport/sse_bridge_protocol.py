"""
SSE Bridge Protocol - Formalized Transport Layer

Reliability Level: L6 Critical
Input Constraints: Valid SSH credentials via environment variables
Side Effects: Network I/O, state changes, may trigger L6 Lockdown

This module formalizes the SSE Bridge transport protocol with:
- SSEMessage dataclass with JSON schema validation
- 10-second heartbeat with 200ms RTT latency warning
- Exponential backoff reconnection (1s to 30s cap)
- L6 Lockdown after 5 failed reconnection attempts

Python 3.8 Compatible - No union type hints (X | None)
PRIVACY: No personal data, IPs, or credentials in code.
"""

from dataclasses import dataclass, field, asdict
from decimal import Decimal
from typing import Optional, List, Dict, Any, Callable, Awaitable
from enum import Enum
import asyncio
import time
import json
import logging
import os
import hashlib
from datetime import datetime, timezone

# Configure logging with unique error codes
logger = logging.getLogger("sse_bridge_protocol")


# =============================================================================
# CONSTANTS
# =============================================================================

# Heartbeat configuration
HEARTBEAT_INTERVAL_SECONDS = 10
LATENCY_WARNING_THRESHOLD_MS = 200

# Reconnection configuration
INITIAL_BACKOFF_SECONDS = 1
MAX_BACKOFF_SECONDS = 30
MAX_RECONNECTION_ATTEMPTS = 5
BACKOFF_MULTIPLIER = 2

# Error codes
ERROR_SSE_LATENCY_HIGH = "SSE_LATENCY_HIGH"
ERROR_SSE_RECONNECT_FAIL = "SSE_RECONNECT_FAIL"
ERROR_SSE_SCHEMA_INVALID = "SSE_SCHEMA_INVALID"
ERROR_SSE_CONNECTION_LOST = "SSE_CONNECTION_LOST"


# =============================================================================
# ENUMS
# =============================================================================

class ConnectionState(Enum):
    """
    SSE Bridge connection states.
    
    Reliability Level: L6 Critical
    """
    DISCONNECTED = "DISCONNECTED"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    RECONNECTING = "RECONNECTING"
    L6_LOCKDOWN = "L6_LOCKDOWN"


class MessageType(Enum):
    """
    SSE message types.
    
    Reliability Level: L6 Critical
    """
    HEARTBEAT = "HEARTBEAT"
    HEARTBEAT_ACK = "HEARTBEAT_ACK"
    REQUEST = "REQUEST"
    RESPONSE = "RESPONSE"
    ERROR = "ERROR"
    NOTIFICATION = "NOTIFICATION"


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class SSEMessage:
    """
    Formalized SSE message with JSON schema validation.
    
    Reliability Level: L6 Critical
    Input Constraints: All fields required except payload
    Side Effects: None
    
    Schema:
    {
        "message_type": "string (enum)",
        "correlation_id": "string (UUID)",
        "timestamp_utc": "string (ISO8601)",
        "payload": "object (optional)"
    }
    """
    message_type: str
    correlation_id: str
    timestamp_utc: str
    payload: Dict[str, Any] = field(default_factory=dict)
    
    def to_json(self) -> str:
        """
        Serialize message to JSON string.
        
        Reliability Level: L6 Critical
        Input Constraints: None
        Side Effects: None
        
        Returns:
            JSON string representation
        """
        return json.dumps(asdict(self), separators=(',', ':'))
    
    @classmethod
    def from_json(cls, json_str: str) -> 'SSEMessage':
        """
        Deserialize message from JSON string.
        
        Reliability Level: L6 Critical
        Input Constraints: Valid JSON string
        Side Effects: None
        
        Args:
            json_str: JSON string to parse
            
        Returns:
            SSEMessage instance
            
        Raises:
            ValueError: If JSON is invalid or missing required fields
        """
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {str(e)}")
        
        # Validate required fields
        required_fields = ["message_type", "correlation_id", "timestamp_utc"]
        for field_name in required_fields:
            if field_name not in data:
                raise ValueError(f"Missing required field: {field_name}")
        
        return cls(
            message_type=data["message_type"],
            correlation_id=data["correlation_id"],
            timestamp_utc=data["timestamp_utc"],
            payload=data.get("payload", {})
        )
    
    @classmethod
    def validate_schema(cls, data: Dict[str, Any]) -> tuple:
        """
        Validate message data against schema.
        
        Reliability Level: L6 Critical
        Input Constraints: Dict with message data
        Side Effects: None
        
        Args:
            data: Message data to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        required_fields = ["message_type", "correlation_id", "timestamp_utc"]
        
        for field_name in required_fields:
            if field_name not in data:
                return (False, f"Missing required field: {field_name}")
            if not isinstance(data[field_name], str):
                return (False, f"Field {field_name} must be string")
            if not data[field_name].strip():
                return (False, f"Field {field_name} cannot be empty")
        
        # Validate payload if present
        if "payload" in data and not isinstance(data["payload"], dict):
            return (False, "Field payload must be object")
        
        return (True, None)
    
    def get_checksum(self) -> str:
        """
        Generate checksum for message integrity.
        
        Returns:
            SHA256 checksum of message content
        """
        content = f"{self.message_type}:{self.correlation_id}:{self.timestamp_utc}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]


@dataclass
class HeartbeatResult:
    """
    Result of heartbeat ping.
    
    Reliability Level: L6 Critical
    """
    success: bool
    rtt_ms: int
    latency_warning: bool
    timestamp_utc: str
    error_message: Optional[str] = None


@dataclass
class ReconnectionAttempt:
    """
    Record of a reconnection attempt.
    
    Reliability Level: L6 Critical
    """
    attempt_number: int
    backoff_seconds: int
    timestamp_utc: str
    success: bool
    error_message: Optional[str] = None


# =============================================================================
# SSE BRIDGE CLASS
# =============================================================================

class SSEBridge:
    """
    Formalized SSE Bridge with heartbeat and reconnection logic.
    
    Reliability Level: L6 Critical
    Input Constraints: Valid connection callback required
    Side Effects: Network I/O, state changes, may trigger L6 Lockdown
    
    Implements:
    - 10-second heartbeat interval
    - 200ms RTT latency warning threshold
    - Exponential backoff reconnection (1s to 30s)
    - L6 Lockdown after 5 failed attempts
    """
    
    def __init__(
        self,
        connect_callback: Optional[Callable[[], Awaitable[bool]]] = None,
        send_callback: Optional[Callable[[str], Awaitable[bool]]] = None,
        receive_callback: Optional[Callable[[], Awaitable[Optional[str]]]] = None,
        lockdown_callback: Optional[Callable[[str], Awaitable[None]]] = None,
        heartbeat_interval: int = HEARTBEAT_INTERVAL_SECONDS,
        latency_threshold_ms: int = LATENCY_WARNING_THRESHOLD_MS,
        max_reconnect_attempts: int = MAX_RECONNECTION_ATTEMPTS
    ) -> None:
        """
        Initialize SSE Bridge.
        
        Args:
            connect_callback: Async callback to establish connection
            send_callback: Async callback to send message
            receive_callback: Async callback to receive message
            lockdown_callback: Async callback to trigger L6 Lockdown
            heartbeat_interval: Seconds between heartbeats (default: 10)
            latency_threshold_ms: RTT warning threshold (default: 200ms)
            max_reconnect_attempts: Max attempts before L6 Lockdown (default: 5)
        """
        self._connect_callback = connect_callback
        self._send_callback = send_callback
        self._receive_callback = receive_callback
        self._lockdown_callback = lockdown_callback
        
        self._heartbeat_interval = heartbeat_interval
        self._latency_threshold_ms = latency_threshold_ms
        self._max_reconnect_attempts = max_reconnect_attempts
        
        self._state = ConnectionState.DISCONNECTED
        self._reconnect_attempts = 0
        self._last_heartbeat: Optional[datetime] = None
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._reconnection_history: List[ReconnectionAttempt] = []
    
    @property
    def state(self) -> ConnectionState:
        """Get current connection state."""
        return self._state
    
    @property
    def is_connected(self) -> bool:
        """Check if bridge is connected."""
        return self._state == ConnectionState.CONNECTED
    
    @property
    def is_locked_down(self) -> bool:
        """Check if bridge is in L6 Lockdown."""
        return self._state == ConnectionState.L6_LOCKDOWN
    
    def calculate_backoff(self, attempt: int) -> int:
        """
        Calculate exponential backoff delay.
        
        Reliability Level: L6 Critical
        Input Constraints: attempt >= 0
        Side Effects: None
        
        Args:
            attempt: Current attempt number (0-indexed)
            
        Returns:
            Backoff delay in seconds (capped at MAX_BACKOFF_SECONDS)
        """
        backoff = INITIAL_BACKOFF_SECONDS * (BACKOFF_MULTIPLIER ** attempt)
        return min(backoff, MAX_BACKOFF_SECONDS)
    
    async def connect(self) -> bool:
        """
        Establish SSE connection with heartbeat.
        
        Reliability Level: L6 Critical
        Input Constraints: connect_callback must be set
        Side Effects: Changes state, starts heartbeat
        
        Returns:
            True if connection successful
        """
        if self._state == ConnectionState.L6_LOCKDOWN:
            logger.error("[CONNECT_BLOCKED] Bridge is in L6 Lockdown")
            return False
        
        if self._connect_callback is None:
            logger.error("[CONNECT_FAIL] No connect_callback configured")
            return False
        
        self._state = ConnectionState.CONNECTING
        logger.info("[CONNECT_START] Establishing SSE connection")
        
        try:
            success = await self._connect_callback()
            
            if success:
                self._state = ConnectionState.CONNECTED
                self._reconnect_attempts = 0
                self._last_heartbeat = datetime.now(timezone.utc)
                
                # Start heartbeat task
                if self._heartbeat_task is None or self._heartbeat_task.done():
                    self._heartbeat_task = asyncio.create_task(
                        self._heartbeat_loop()
                    )
                
                logger.info("[CONNECT_SUCCESS] SSE connection established")
                return True
            else:
                self._state = ConnectionState.DISCONNECTED
                logger.error("[CONNECT_FAIL] Connection callback returned False")
                return False
                
        except Exception as e:
            self._state = ConnectionState.DISCONNECTED
            logger.error(f"[CONNECT_ERROR] {str(e)}")
            return False
    
    async def _heartbeat_loop(self) -> None:
        """
        Background heartbeat loop.
        
        Sends heartbeat every 10 seconds and monitors RTT.
        """
        while self._state == ConnectionState.CONNECTED:
            try:
                await asyncio.sleep(self._heartbeat_interval)
                
                if self._state != ConnectionState.CONNECTED:
                    break
                
                result = await self.send_heartbeat()
                
                if not result.success:
                    logger.warning(
                        f"[HEARTBEAT_FAIL] error={result.error_message}"
                    )
                    await self._handle_connection_loss()
                    break
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[HEARTBEAT_ERROR] {str(e)}")
                await self._handle_connection_loss()
                break
    
    async def send_heartbeat(self) -> HeartbeatResult:
        """
        Send heartbeat and measure RTT.
        
        Reliability Level: L6 Critical
        Input Constraints: Must be connected
        Side Effects: Network I/O, may log latency warning
        
        Returns:
            HeartbeatResult with RTT and latency status
        """
        if self._send_callback is None:
            return HeartbeatResult(
                success=False,
                rtt_ms=0,
                latency_warning=False,
                timestamp_utc=datetime.now(timezone.utc).isoformat(),
                error_message="No send_callback configured"
            )
        
        import uuid
        correlation_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc)
        
        heartbeat_msg = SSEMessage(
            message_type=MessageType.HEARTBEAT.value,
            correlation_id=correlation_id,
            timestamp_utc=timestamp.isoformat(),
            payload={"ping": True}
        )
        
        start_time_ms = int(time.time() * 1000)
        
        try:
            success = await self._send_callback(heartbeat_msg.to_json())
            
            end_time_ms = int(time.time() * 1000)
            rtt_ms = end_time_ms - start_time_ms
            
            latency_warning = rtt_ms > self._latency_threshold_ms
            
            if latency_warning:
                logger.warning(
                    f"[{ERROR_SSE_LATENCY_HIGH}] rtt_ms={rtt_ms} "
                    f"threshold_ms={self._latency_threshold_ms} "
                    f"correlation_id={correlation_id}"
                )
            
            self._last_heartbeat = datetime.now(timezone.utc)
            
            return HeartbeatResult(
                success=success,
                rtt_ms=rtt_ms,
                latency_warning=latency_warning,
                timestamp_utc=timestamp.isoformat()
            )
            
        except Exception as e:
            return HeartbeatResult(
                success=False,
                rtt_ms=0,
                latency_warning=False,
                timestamp_utc=timestamp.isoformat(),
                error_message=str(e)
            )
    
    async def _handle_connection_loss(self) -> None:
        """
        Handle connection loss - initiate reconnection.
        
        Reliability Level: L6 Critical
        """
        if self._state == ConnectionState.L6_LOCKDOWN:
            return
        
        self._state = ConnectionState.RECONNECTING
        logger.warning(f"[{ERROR_SSE_CONNECTION_LOST}] Initiating reconnection")
        
        success = await self.reconnect_with_backoff()
        
        if not success:
            await self._trigger_l6_lockdown()
    
    async def reconnect_with_backoff(self) -> bool:
        """
        Attempt reconnection with exponential backoff.
        
        Reliability Level: L6 Critical
        Input Constraints: None
        Side Effects: Changes state, may trigger L6 Lockdown
        
        Backoff sequence: 1s, 2s, 4s, 8s, 16s (capped at 30s)
        
        Returns:
            True if reconnection successful within max attempts
        """
        if self._state == ConnectionState.L6_LOCKDOWN:
            logger.error("[RECONNECT_BLOCKED] Bridge is in L6 Lockdown")
            return False
        
        self._state = ConnectionState.RECONNECTING
        
        for attempt in range(self._max_reconnect_attempts):
            backoff = self.calculate_backoff(attempt)
            
            logger.info(
                f"[RECONNECT_ATTEMPT] attempt={attempt + 1}/{self._max_reconnect_attempts} "
                f"backoff={backoff}s"
            )
            
            # Wait for backoff period
            await asyncio.sleep(backoff)
            
            # Attempt connection
            try:
                if self._connect_callback is not None:
                    success = await self._connect_callback()
                else:
                    success = False
                
                attempt_record = ReconnectionAttempt(
                    attempt_number=attempt + 1,
                    backoff_seconds=backoff,
                    timestamp_utc=datetime.now(timezone.utc).isoformat(),
                    success=success
                )
                self._reconnection_history.append(attempt_record)
                
                if success:
                    self._state = ConnectionState.CONNECTED
                    self._reconnect_attempts = 0
                    
                    # Restart heartbeat
                    if self._heartbeat_task is None or self._heartbeat_task.done():
                        self._heartbeat_task = asyncio.create_task(
                            self._heartbeat_loop()
                        )
                    
                    logger.info(
                        f"[RECONNECT_SUCCESS] attempt={attempt + 1}"
                    )
                    return True
                    
            except Exception as e:
                attempt_record = ReconnectionAttempt(
                    attempt_number=attempt + 1,
                    backoff_seconds=backoff,
                    timestamp_utc=datetime.now(timezone.utc).isoformat(),
                    success=False,
                    error_message=str(e)
                )
                self._reconnection_history.append(attempt_record)
                
                logger.warning(
                    f"[RECONNECT_FAIL] attempt={attempt + 1} error={str(e)}"
                )
        
        # All attempts exhausted
        logger.error(
            f"[{ERROR_SSE_RECONNECT_FAIL}] All {self._max_reconnect_attempts} "
            f"attempts exhausted"
        )
        
        return False
    
    async def _trigger_l6_lockdown(self) -> None:
        """
        Trigger L6 Lockdown state.
        
        Reliability Level: L6 Critical
        Side Effects: Changes state, invokes lockdown callback
        """
        self._state = ConnectionState.L6_LOCKDOWN
        
        logger.critical(
            "[L6_LOCKDOWN_TRIGGERED] SSE Bridge entering lockdown state. "
            "All trading operations must cease."
        )
        
        # Stop heartbeat
        if self._heartbeat_task is not None:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
        
        # Invoke lockdown callback
        if self._lockdown_callback is not None:
            try:
                await self._lockdown_callback(
                    "SSE Bridge reconnection failed after 5 attempts"
                )
            except Exception as e:
                logger.error(f"[LOCKDOWN_CALLBACK_ERROR] {str(e)}")
    
    async def send(self, message: SSEMessage) -> bool:
        """
        Send message with schema validation.
        
        Reliability Level: L6 Critical
        Input Constraints: Valid SSEMessage required
        Side Effects: Network I/O
        
        Args:
            message: SSEMessage to send
            
        Returns:
            True if send successful
        """
        if self._state != ConnectionState.CONNECTED:
            logger.error(
                f"[SEND_BLOCKED] Cannot send in state {self._state.value}"
            )
            return False
        
        if self._send_callback is None:
            logger.error("[SEND_FAIL] No send_callback configured")
            return False
        
        # Validate schema
        is_valid, error = SSEMessage.validate_schema(asdict(message))
        if not is_valid:
            logger.error(
                f"[{ERROR_SSE_SCHEMA_INVALID}] {error} "
                f"correlation_id={message.correlation_id}"
            )
            return False
        
        try:
            success = await self._send_callback(message.to_json())
            
            logger.debug(
                f"[SEND_SUCCESS] type={message.message_type} "
                f"correlation_id={message.correlation_id}"
            )
            
            return success
            
        except Exception as e:
            logger.error(
                f"[SEND_ERROR] correlation_id={message.correlation_id} "
                f"error={str(e)}"
            )
            return False
    
    async def disconnect(self) -> None:
        """
        Gracefully disconnect the bridge.
        
        Reliability Level: L6 Critical
        Side Effects: Changes state, stops heartbeat
        """
        logger.info("[DISCONNECT] Closing SSE Bridge")
        
        # Stop heartbeat
        if self._heartbeat_task is not None:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
        
        self._state = ConnectionState.DISCONNECTED
    
    def get_reconnection_history(self) -> List[ReconnectionAttempt]:
        """Get history of reconnection attempts."""
        return self._reconnection_history.copy()
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get bridge status summary.
        
        Returns:
            Dict with status information
        """
        return {
            "state": self._state.value,
            "is_connected": self.is_connected,
            "is_locked_down": self.is_locked_down,
            "last_heartbeat": (
                self._last_heartbeat.isoformat()
                if self._last_heartbeat else None
            ),
            "reconnect_attempts": len(self._reconnection_history),
            "heartbeat_interval_seconds": self._heartbeat_interval,
            "latency_threshold_ms": self._latency_threshold_ms,
            "max_reconnect_attempts": self._max_reconnect_attempts
        }

"""
Indicator Memory Module - Technical Indicator Caching System

Reliability Level: L5 High
Input Constraints: correlation_id required for all operations
Side Effects: Caches indicator data, network I/O to aura-full MCP

This module maps technical indicator tools from aura-full to the bot's
execution memory with strict freshness validation (60-second window).

Python 3.8 Compatible - No union type hints (X | None)
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional, List, Dict, Any, Callable, Awaitable
import asyncio
import time
import logging
from datetime import datetime, timezone
from enum import Enum

# Configure logging with unique error codes
logger = logging.getLogger("indicator_memory")


# =============================================================================
# CONSTANTS
# =============================================================================

# Freshness threshold in seconds
FRESHNESS_THRESHOLD_SECONDS = 60

# Retry configuration
RETRY_DELAY_SECONDS = 5
MAX_RETRIES = 1

# Error codes
ERROR_INDICATOR_FETCH_FAIL = "INDICATOR_FETCH_FAIL"
ERROR_INDICATOR_STALE = "INDICATOR_STALE"
ERROR_INDICATOR_TIMEOUT = "INDICATOR_TIMEOUT"


# =============================================================================
# DATA CLASSES
# =============================================================================

class IndicatorStatus(Enum):
    """
    Status of indicator data.
    
    Reliability Level: L5 High
    """
    FRESH = "FRESH"
    STALE = "STALE"
    UNAVAILABLE = "UNAVAILABLE"
    ERROR = "ERROR"


@dataclass
class IndicatorSnapshot:
    """
    Point-in-time snapshot of technical indicators.
    
    Reliability Level: L5 High
    Input Constraints: correlation_id required
    Side Effects: None (read-only cache)
    """
    correlation_id: str
    timestamp_utc: str
    predictions: Dict[str, Any]
    reasoning_analysis: Dict[str, Any]
    freshness_seconds: int
    is_stale: bool
    status: IndicatorStatus
    fetch_time_ms: int
    error_message: Optional[str] = None


@dataclass
class CachedIndicator:
    """
    Internal cache entry for indicator data.
    
    Reliability Level: L5 High
    """
    data: Dict[str, Any]
    timestamp: datetime
    correlation_id: str
    tool_name: str


# =============================================================================
# INDICATOR MEMORY MODULE
# =============================================================================

class IndicatorMemoryModule:
    """
    Technical indicator caching system with freshness validation.
    
    Reliability Level: L5 High
    Input Constraints: Valid MCP connection required
    Side Effects: Caches indicator data in memory, network I/O
    
    Implements strict 60-second freshness validation as per Requirements 2.3.
    """
    
    def __init__(
        self,
        mcp_tool_caller: Optional[Callable[[str, str, Dict[str, Any]], Awaitable[Any]]] = None,
        freshness_threshold_seconds: int = FRESHNESS_THRESHOLD_SECONDS,
        retry_delay_seconds: int = RETRY_DELAY_SECONDS,
        max_retries: int = MAX_RETRIES
    ) -> None:
        """
        Initialize Indicator Memory Module.
        
        Args:
            mcp_tool_caller: Async callback to invoke MCP tools (server, tool, args)
            freshness_threshold_seconds: Max age for fresh data (default: 60s)
            retry_delay_seconds: Delay between retries (default: 5s)
            max_retries: Maximum retry attempts (default: 1)
        """
        self._mcp_tool_caller = mcp_tool_caller
        self._freshness_threshold = freshness_threshold_seconds
        self._retry_delay = retry_delay_seconds
        self._max_retries = max_retries
        
        # Cache storage: correlation_id -> CachedIndicator
        self._predictions_cache = {}  # type: Dict[str, CachedIndicator]
        self._reasoning_cache = {}  # type: Dict[str, CachedIndicator]
        
        # Connection status
        self._connected = False
        self._last_successful_fetch = None  # type: Optional[datetime]
    
    @property
    def is_connected(self) -> bool:
        """Check if MCP connection is established."""
        return self._mcp_tool_caller is not None
    
    @property
    def freshness_threshold(self) -> int:
        """Get freshness threshold in seconds."""
        return self._freshness_threshold
    
    async def initialize(self) -> bool:
        """
        Establish connections to indicator tools.
        
        Reliability Level: L5 High
        Input Constraints: mcp_tool_caller must be set
        Side Effects: Validates MCP connectivity
        
        Returns:
            True if connections established successfully
        """
        if self._mcp_tool_caller is None:
            logger.error("[INIT_FAIL] No MCP tool caller configured")
            return False
        
        try:
            # Test connectivity by checking system status
            result = await self._mcp_tool_caller(
                "aura-full",
                "ml_get_system_status",
                {}
            )
            
            self._connected = True
            logger.info(
                f"[INIT_SUCCESS] Connected to aura-full indicator tools"
            )
            return True
            
        except Exception as e:
            logger.error(f"[INIT_FAIL] error={str(e)}")
            self._connected = False
            return False
    
    def _calculate_freshness(self, timestamp: datetime) -> tuple:
        """
        Calculate data freshness.
        
        Args:
            timestamp: When data was fetched
            
        Returns:
            Tuple of (freshness_seconds, is_stale)
        """
        now = datetime.now(timezone.utc)
        age_seconds = int((now - timestamp).total_seconds())
        is_stale = age_seconds > self._freshness_threshold
        
        return (age_seconds, is_stale)
    
    def get_cached(
        self,
        correlation_id: str
    ) -> Optional[IndicatorSnapshot]:
        """
        Retrieve cached indicators if fresh.
        
        Reliability Level: L5 High
        Input Constraints: correlation_id required
        Side Effects: None
        
        Args:
            correlation_id: Tracking ID for the request
            
        Returns:
            IndicatorSnapshot if fresh data exists, None otherwise
        """
        predictions = self._predictions_cache.get(correlation_id)
        reasoning = self._reasoning_cache.get(correlation_id)
        
        if predictions is None and reasoning is None:
            logger.debug(f"[CACHE_MISS] correlation_id={correlation_id}")
            return None
        
        # Use the older timestamp for freshness calculation
        timestamps = []  # type: List[datetime]
        if predictions:
            timestamps.append(predictions.timestamp)
        if reasoning:
            timestamps.append(reasoning.timestamp)
        
        oldest_timestamp = min(timestamps) if timestamps else datetime.now(timezone.utc)
        freshness_seconds, is_stale = self._calculate_freshness(oldest_timestamp)
        
        if is_stale:
            logger.info(
                f"[CACHE_STALE] correlation_id={correlation_id} "
                f"age_seconds={freshness_seconds}"
            )
            return None
        
        snapshot = IndicatorSnapshot(
            correlation_id=correlation_id,
            timestamp_utc=oldest_timestamp.isoformat(),
            predictions=predictions.data if predictions else {},
            reasoning_analysis=reasoning.data if reasoning else {},
            freshness_seconds=freshness_seconds,
            is_stale=False,
            status=IndicatorStatus.FRESH,
            fetch_time_ms=0  # Cached, no fetch time
        )
        
        logger.debug(
            f"[CACHE_HIT] correlation_id={correlation_id} "
            f"freshness_seconds={freshness_seconds}"
        )
        
        return snapshot
    
    async def _fetch_with_retry(
        self,
        tool_name: str,
        args: Dict[str, Any],
        correlation_id: str
    ) -> tuple:
        """
        Fetch indicator data with retry logic.
        
        Reliability Level: L5 High
        Input Constraints: Valid tool_name required
        Side Effects: Network I/O, logging
        
        Args:
            tool_name: MCP tool to invoke
            args: Tool arguments
            correlation_id: Tracking ID
            
        Returns:
            Tuple of (data, success, error_message)
        """
        if self._mcp_tool_caller is None:
            return (None, False, "No MCP tool caller configured")
        
        last_error = None
        
        for attempt in range(self._max_retries + 1):
            try:
                logger.info(
                    f"[FETCH_ATTEMPT] tool={tool_name} attempt={attempt + 1} "
                    f"correlation_id={correlation_id}"
                )
                
                result = await self._mcp_tool_caller(
                    "aura-full",
                    tool_name,
                    args
                )
                
                logger.info(
                    f"[FETCH_SUCCESS] tool={tool_name} "
                    f"correlation_id={correlation_id}"
                )
                
                return (result, True, None)
                
            except Exception as e:
                last_error = str(e)
                logger.warning(
                    f"[FETCH_FAIL] tool={tool_name} attempt={attempt + 1} "
                    f"correlation_id={correlation_id} error={last_error}"
                )
                
                # Retry after delay if not last attempt
                if attempt < self._max_retries:
                    logger.info(
                        f"[FETCH_RETRY] waiting {self._retry_delay}s "
                        f"correlation_id={correlation_id}"
                    )
                    await asyncio.sleep(self._retry_delay)
        
        # All retries exhausted
        logger.error(
            f"[{ERROR_INDICATOR_FETCH_FAIL}] tool={tool_name} "
            f"correlation_id={correlation_id} error={last_error}"
        )
        
        return (None, False, last_error)
    
    async def fetch_indicators(
        self,
        correlation_id: str,
        max_age_seconds: Optional[int] = None,
        user_id: Optional[str] = None
    ) -> IndicatorSnapshot:
        """
        Fetch and cache indicator data from aura-full.
        
        Reliability Level: L5 High
        Input Constraints: correlation_id required
        Side Effects: Network I/O, updates cache
        
        Args:
            correlation_id: Tracking ID for the request
            max_age_seconds: Override freshness threshold
            user_id: Optional user ID for predictions
            
        Returns:
            IndicatorSnapshot with indicator data
        """
        start_time_ms = int(time.time() * 1000)
        effective_threshold = max_age_seconds or self._freshness_threshold
        
        # Check cache first
        cached = self.get_cached(correlation_id)
        if cached is not None and cached.freshness_seconds <= effective_threshold:
            return cached
        
        logger.info(
            f"[FETCH_START] correlation_id={correlation_id} "
            f"threshold={effective_threshold}s"
        )
        
        # Fetch predictions
        predictions_data, predictions_ok, predictions_error = await self._fetch_with_retry(
            "ml_get_predictions",
            {"user_id": user_id or "system"},
            correlation_id
        )
        
        # Fetch reasoning analysis
        reasoning_data, reasoning_ok, reasoning_error = await self._fetch_with_retry(
            "ml_analyze_reasoning",
            {"command": f"analyze_signal_{correlation_id}"},
            correlation_id
        )
        
        end_time_ms = int(time.time() * 1000)
        fetch_time_ms = end_time_ms - start_time_ms
        now = datetime.now(timezone.utc)
        
        # Determine overall status
        if not predictions_ok and not reasoning_ok:
            # All data unavailable - default to Neutral Cash State
            logger.warning(
                f"[ALL_INDICATORS_UNAVAILABLE] correlation_id={correlation_id} "
                f"defaulting to Neutral Cash State"
            )
            
            return IndicatorSnapshot(
                correlation_id=correlation_id,
                timestamp_utc=now.isoformat(),
                predictions={},
                reasoning_analysis={},
                freshness_seconds=0,
                is_stale=True,
                status=IndicatorStatus.UNAVAILABLE,
                fetch_time_ms=fetch_time_ms,
                error_message=f"Predictions: {predictions_error}; Reasoning: {reasoning_error}"
            )
        
        # Cache successful fetches
        if predictions_ok and predictions_data:
            self._predictions_cache[correlation_id] = CachedIndicator(
                data=predictions_data if isinstance(predictions_data, dict) else {"raw": predictions_data},
                timestamp=now,
                correlation_id=correlation_id,
                tool_name="ml_get_predictions"
            )
        
        if reasoning_ok and reasoning_data:
            self._reasoning_cache[correlation_id] = CachedIndicator(
                data=reasoning_data if isinstance(reasoning_data, dict) else {"raw": reasoning_data},
                timestamp=now,
                correlation_id=correlation_id,
                tool_name="ml_analyze_reasoning"
            )
        
        self._last_successful_fetch = now
        
        snapshot = IndicatorSnapshot(
            correlation_id=correlation_id,
            timestamp_utc=now.isoformat(),
            predictions=predictions_data if isinstance(predictions_data, dict) else {"raw": predictions_data},
            reasoning_analysis=reasoning_data if isinstance(reasoning_data, dict) else {"raw": reasoning_data},
            freshness_seconds=0,
            is_stale=False,
            status=IndicatorStatus.FRESH,
            fetch_time_ms=fetch_time_ms
        )
        
        logger.info(
            f"[FETCH_COMPLETE] correlation_id={correlation_id} "
            f"fetch_time_ms={fetch_time_ms} status={snapshot.status.value}"
        )
        
        return snapshot
    
    def validate_freshness(
        self,
        snapshot: IndicatorSnapshot,
        max_age_seconds: Optional[int] = None
    ) -> bool:
        """
        Validate indicator data freshness.
        
        Reliability Level: L5 High
        Input Constraints: Valid IndicatorSnapshot required
        Side Effects: None
        
        Args:
            snapshot: The indicator snapshot to validate
            max_age_seconds: Override freshness threshold
            
        Returns:
            True if data is fresh (within threshold)
        """
        threshold = max_age_seconds or self._freshness_threshold
        
        if snapshot.status == IndicatorStatus.UNAVAILABLE:
            return False
        
        if snapshot.status == IndicatorStatus.ERROR:
            return False
        
        if snapshot.freshness_seconds > threshold:
            logger.warning(
                f"[{ERROR_INDICATOR_STALE}] correlation_id={snapshot.correlation_id} "
                f"age={snapshot.freshness_seconds}s threshold={threshold}s"
            )
            return False
        
        return True
    
    def clear_cache(self, correlation_id: Optional[str] = None) -> int:
        """
        Clear cached indicator data.
        
        Args:
            correlation_id: Specific entry to clear, or None for all
            
        Returns:
            Number of entries cleared
        """
        if correlation_id:
            cleared = 0
            if correlation_id in self._predictions_cache:
                del self._predictions_cache[correlation_id]
                cleared += 1
            if correlation_id in self._reasoning_cache:
                del self._reasoning_cache[correlation_id]
                cleared += 1
            return cleared
        else:
            total = len(self._predictions_cache) + len(self._reasoning_cache)
            self._predictions_cache.clear()
            self._reasoning_cache.clear()
            logger.info(f"[CACHE_CLEARED] entries={total}")
            return total
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dict with cache stats
        """
        return {
            "predictions_cached": len(self._predictions_cache),
            "reasoning_cached": len(self._reasoning_cache),
            "last_successful_fetch": (
                self._last_successful_fetch.isoformat()
                if self._last_successful_fetch else None
            ),
            "freshness_threshold_seconds": self._freshness_threshold,
            "connected": self._connected
        }

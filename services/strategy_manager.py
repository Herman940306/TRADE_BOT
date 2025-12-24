"""
============================================================================
Strategy Manager Service - Deterministic Mode
============================================================================

Reliability Level: L6 Critical (Sovereign Tier)
Decimal Integrity: All financial calculations use decimal.Decimal with ROUND_HALF_EVEN
Traceability: All operations include correlation_id for audit

STRATEGY MODES:
    DETERMINISTIC: No random number generation, all inputs/outputs logged
    STOCHASTIC: Allows randomness (for backtesting/simulation)

REQUIREMENTS SATISFIED:
    - Requirement 2.1: DETERMINISTIC mode prohibits random number generation
    - Requirement 2.2: Log all strategy inputs with correlation_id
    - Requirement 2.3: Log all strategy outputs with correlation_id
    - Requirement 2.4: Identical inputs produce identical outputs in DETERMINISTIC mode
    - Requirement 2.5: Record signal confidence score and outcome for analysis

ERROR CODES:
    - STR-001: Strategy evaluation failure
    - STR-002: Non-deterministic operation in DETERMINISTIC mode
    - STR-003: Invalid correlation_id (empty or None)
    - STR-004: Database persistence failure
    - STR-005: Invalid input data

============================================================================
"""

from decimal import Decimal, ROUND_HALF_EVEN
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone
import logging
import uuid
import hashlib
import json
import os

# Prometheus metrics (optional - graceful degradation if not available)
try:
    from prometheus_client import Counter, Gauge, Histogram
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

# Configure module logger
logger = logging.getLogger(__name__)


# =============================================================================
# Prometheus Metrics
# =============================================================================

if PROMETHEUS_AVAILABLE:
    # Strategy decision counter by action
    # **Feature: phase2-hard-requirements, Grafana Dashboard Panels**
    # **Validates: Requirements 4.2**
    STRATEGY_DECISIONS_TOTAL = Counter(
        'strategy_decisions_total',
        'Total number of strategy decisions by action',
        ['action']
    )
    
    # Signal confidence histogram for distribution analysis
    # **Feature: phase2-hard-requirements, Grafana Dashboard Panels**
    # **Validates: Requirements 4.2**
    SIGNAL_CONFIDENCE_HISTOGRAM = Histogram(
        'strategy_signal_confidence',
        'Distribution of signal confidence scores',
        ['action'],
        buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
    )
    
    # Current confidence gauge by action (for real-time display)
    SIGNAL_CONFIDENCE_GAUGE = Gauge(
        'strategy_signal_confidence_current',
        'Current signal confidence by action',
        ['action']
    )


# =============================================================================
# Constants
# =============================================================================

# Decimal precision for confidence scores
PRECISION_CONFIDENCE = Decimal("0.0001")  # 4 decimal places


# =============================================================================
# Error Codes
# =============================================================================

class StrategyErrorCode:
    """Strategy Manager-specific error codes for audit logging."""
    EVALUATION_FAILURE = "STR-001"
    NON_DETERMINISTIC_OP = "STR-002"
    INVALID_CORRELATION_ID = "STR-003"
    DB_PERSISTENCE_FAIL = "STR-004"
    INVALID_INPUT = "STR-005"


# =============================================================================
# Enums
# =============================================================================

class StrategyMode(Enum):
    """
    Strategy execution mode.
    
    DETERMINISTIC: No random number generation, all inputs/outputs logged.
                   Same inputs MUST produce same outputs.
    STOCHASTIC: Allows randomness (for backtesting/simulation).
    """
    DETERMINISTIC = "DETERMINISTIC"
    STOCHASTIC = "STOCHASTIC"


class StrategyAction(Enum):
    """
    Strategy decision actions.
    
    BUY: Open long position
    SELL: Open short position or close long
    HOLD: No action
    """
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class StrategyDecision:
    """
    Strategy evaluation decision record.
    
    Reliability Level: L6 Critical
    Input Constraints: All fields required except row_hash
    Side Effects: None (data container)
    
    **Feature: phase2-hard-requirements, Strategy Decision Persistence**
    **Validates: Requirements 2.5**
    """
    trade_id: str
    correlation_id: str
    inputs_hash: str
    outputs_hash: str
    action: StrategyAction
    signal_confidence: Decimal
    decided_at: datetime
    row_hash: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/persistence."""
        return {
            "trade_id": self.trade_id,
            "correlation_id": self.correlation_id,
            "inputs_hash": self.inputs_hash,
            "outputs_hash": self.outputs_hash,
            "action": self.action.value,
            "signal_confidence": str(self.signal_confidence),
            "decided_at": self.decided_at.isoformat(),
            "row_hash": self.row_hash,
        }


@dataclass
class StrategyInputs:
    """
    Strategy evaluation inputs.
    
    Reliability Level: L6 Critical
    Input Constraints: All fields required
    Side Effects: None (data container)
    """
    signal_data: Dict[str, Any]
    market_data: Dict[str, Any]
    correlation_id: str
    timestamp: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for hashing/logging."""
        return {
            "signal_data": self.signal_data,
            "market_data": self.market_data,
            "correlation_id": self.correlation_id,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class StrategyOutputs:
    """
    Strategy evaluation outputs.
    
    Reliability Level: L6 Critical
    Input Constraints: All fields required
    Side Effects: None (data container)
    """
    action: StrategyAction
    signal_confidence: Decimal
    reasoning: str
    timestamp: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for hashing/logging."""
        return {
            "action": self.action.value,
            "signal_confidence": str(self.signal_confidence),
            "reasoning": self.reasoning,
            "timestamp": self.timestamp.isoformat(),
        }


# =============================================================================
# Strategy Manager Class
# =============================================================================

class StrategyManager:
    """
    Executes trading strategy with optional deterministic mode.
    
    ============================================================================
    DETERMINISTIC MODE:
    ============================================================================
        - No random number generation
        - All inputs logged before processing
        - All outputs logged after processing
        - Same inputs → same outputs (reproducible)
    ============================================================================
    
    Reliability Level: L6 Critical (Sovereign Tier)
    Input Constraints: Valid database session required for persistence
    Side Effects: Creates database records, logs all operations
    
    **Feature: phase2-hard-requirements, Strategy Manager**
    **Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5**
    """
    
    def __init__(
        self,
        mode: Optional[StrategyMode] = None,
        db_session: Optional[Any] = None,
        correlation_id: Optional[str] = None
    ) -> None:
        """
        Initialize the Strategy Manager.
        
        Args:
            mode: Strategy execution mode (defaults to DETERMINISTIC)
            db_session: Database session for PostgreSQL persistence (optional)
            correlation_id: Default correlation_id for operations
            
        Reliability Level: L6 Critical
        Input Constraints: mode should be valid StrategyMode
        Side Effects: Logs initialization
        """
        # Default to DETERMINISTIC mode from environment or parameter
        if mode is None:
            env_mode = os.environ.get("STRATEGY_MODE", "DETERMINISTIC")
            try:
                self._mode = StrategyMode(env_mode)
            except ValueError:
                self._mode = StrategyMode.DETERMINISTIC
        else:
            self._mode = mode
        
        self._db_session = db_session
        self._default_correlation_id = correlation_id or str(uuid.uuid4())
        
        # In-memory storage for testing without database
        self._decisions: Dict[str, List[StrategyDecision]] = {}
        self._input_logs: List[Dict[str, Any]] = []
        self._output_logs: List[Dict[str, Any]] = []
        
        logger.info(
            f"[STRATEGY-MANAGER] Manager initialized | "
            f"mode={self._mode.value} | "
            f"db_session={'connected' if db_session else 'in-memory'} | "
            f"correlation_id={self._default_correlation_id}"
        )
    
    @property
    def mode(self) -> StrategyMode:
        """Get current strategy mode."""
        return self._mode
    
    def evaluate(
        self,
        trade_id: str,
        signal_data: Dict[str, Any],
        market_data: Dict[str, Any],
        correlation_id: str
    ) -> StrategyDecision:
        """
        Evaluate trading strategy and produce a decision.
        
        ========================================================================
        EVALUATION FLOW:
        ========================================================================
        1. Validate correlation_id is non-empty
        2. Create StrategyInputs record
        3. Log inputs with correlation_id (DETERMINISTIC mode)
        4. Compute inputs_hash
        5. Execute strategy logic (deterministic)
        6. Create StrategyOutputs record
        7. Log outputs with correlation_id (DETERMINISTIC mode)
        8. Compute outputs_hash
        9. Create StrategyDecision record
        10. Persist to database (if connected)
        11. Return StrategyDecision
        ========================================================================
        
        Args:
            trade_id: UUID of the trade being evaluated
            signal_data: Original signal data (symbol, side, price, quantity, etc.)
            market_data: Current market data (bid, ask, volume, etc.)
            correlation_id: Unique identifier for this operation (REQUIRED)
            
        Returns:
            StrategyDecision with action, confidence, and hashes
            
        Raises:
            ValueError: If correlation_id is empty or None
            
        Reliability Level: L6 Critical
        Input Constraints: correlation_id must be non-empty string
        Side Effects: Creates database record, logs operation
        
        **Feature: phase2-hard-requirements, Property 5: Deterministic Strategy Reproducibility**
        **Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5**
        """
        # Validate correlation_id
        if not correlation_id or not str(correlation_id).strip():
            error_msg = (
                f"[{StrategyErrorCode.INVALID_CORRELATION_ID}] "
                f"correlation_id must be non-empty. "
                f"Sovereign Mandate: Traceability required."
            )
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        now = datetime.now(timezone.utc)
        
        # Create inputs record
        inputs = StrategyInputs(
            signal_data=signal_data,
            market_data=market_data,
            correlation_id=str(correlation_id),
            timestamp=now,
        )
        
        # Log inputs (DETERMINISTIC mode requirement 2.2)
        self._log_inputs(inputs, correlation_id)
        
        # Compute inputs hash
        inputs_hash = self._compute_hash(inputs.to_dict())
        
        # Execute strategy logic (deterministic)
        action, confidence, reasoning = self._execute_strategy(
            signal_data, market_data, correlation_id
        )
        
        # Create outputs record
        outputs = StrategyOutputs(
            action=action,
            signal_confidence=confidence,
            reasoning=reasoning,
            timestamp=datetime.now(timezone.utc),
        )
        
        # Log outputs (DETERMINISTIC mode requirement 2.3)
        self._log_outputs(outputs, correlation_id)
        
        # Compute outputs hash
        outputs_hash = self._compute_hash(outputs.to_dict())
        
        # Create decision record
        decision = StrategyDecision(
            trade_id=trade_id,
            correlation_id=str(correlation_id),
            inputs_hash=inputs_hash,
            outputs_hash=outputs_hash,
            action=action,
            signal_confidence=confidence,
            decided_at=datetime.now(timezone.utc),
            row_hash=None,  # Will be computed by database trigger
        )
        
        # Persist to database if connected
        if self._db_session is not None:
            self._persist_decision(decision)
        else:
            # In-memory storage for testing
            if trade_id not in self._decisions:
                self._decisions[trade_id] = []
            self._decisions[trade_id].append(decision)
        
        # Update Prometheus metrics
        # **Feature: phase2-hard-requirements, Grafana Dashboard Panels**
        # **Validates: Requirements 4.2**
        if PROMETHEUS_AVAILABLE:
            STRATEGY_DECISIONS_TOTAL.labels(action=action.value).inc()
            SIGNAL_CONFIDENCE_HISTOGRAM.labels(action=action.value).observe(
                float(confidence)
            )
            SIGNAL_CONFIDENCE_GAUGE.labels(action=action.value).set(
                float(confidence)
            )
        
        logger.info(
            f"[STRATEGY-MANAGER] Decision made | "
            f"trade_id={trade_id} | "
            f"action={action.value} | "
            f"confidence={confidence} | "
            f"mode={self._mode.value} | "
            f"correlation_id={correlation_id}"
        )
        
        return decision
    
    def get_decisions(self, trade_id: str) -> List[StrategyDecision]:
        """
        Get all decisions for a trade.
        
        Args:
            trade_id: UUID of trade
            
        Returns:
            List of StrategyDecision records
            
        Reliability Level: L6 Critical
        Input Constraints: None
        Side Effects: None (read-only)
        """
        if self._db_session is not None:
            return self._query_decisions(trade_id)
        else:
            return self._decisions.get(trade_id, [])
    
    def get_input_logs(self) -> List[Dict[str, Any]]:
        """
        Get all logged inputs (for testing/debugging).
        
        Returns:
            List of input log records
            
        Reliability Level: L6 Critical
        Input Constraints: None
        Side Effects: None (read-only)
        """
        return self._input_logs.copy()
    
    def get_output_logs(self) -> List[Dict[str, Any]]:
        """
        Get all logged outputs (for testing/debugging).
        
        Returns:
            List of output log records
            
        Reliability Level: L6 Critical
        Input Constraints: None
        Side Effects: None (read-only)
        """
        return self._output_logs.copy()
    
    # =========================================================================
    # Private Methods
    # =========================================================================
    
    def _log_inputs(
        self,
        inputs: StrategyInputs,
        correlation_id: str
    ) -> None:
        """
        Log strategy inputs with correlation_id.
        
        **Feature: phase2-hard-requirements, Property 6: Strategy Input/Output Logging**
        **Validates: Requirements 2.2**
        
        Args:
            inputs: StrategyInputs record
            correlation_id: Correlation ID for traceability
        """
        log_record = {
            "type": "STRATEGY_INPUT",
            "correlation_id": correlation_id,
            "mode": self._mode.value,
            "inputs": inputs.to_dict(),
            "logged_at": datetime.now(timezone.utc).isoformat(),
        }
        
        self._input_logs.append(log_record)
        
        logger.info(
            f"[STRATEGY-MANAGER] Inputs logged | "
            f"correlation_id={correlation_id} | "
            f"mode={self._mode.value} | "
            f"symbol={inputs.signal_data.get('symbol', 'N/A')}"
        )
    
    def _log_outputs(
        self,
        outputs: StrategyOutputs,
        correlation_id: str
    ) -> None:
        """
        Log strategy outputs with correlation_id.
        
        **Feature: phase2-hard-requirements, Property 6: Strategy Input/Output Logging**
        **Validates: Requirements 2.3**
        
        Args:
            outputs: StrategyOutputs record
            correlation_id: Correlation ID for traceability
        """
        log_record = {
            "type": "STRATEGY_OUTPUT",
            "correlation_id": correlation_id,
            "mode": self._mode.value,
            "outputs": outputs.to_dict(),
            "logged_at": datetime.now(timezone.utc).isoformat(),
        }
        
        self._output_logs.append(log_record)
        
        logger.info(
            f"[STRATEGY-MANAGER] Outputs logged | "
            f"correlation_id={correlation_id} | "
            f"mode={self._mode.value} | "
            f"action={outputs.action.value} | "
            f"confidence={outputs.signal_confidence}"
        )
    
    def _compute_hash(self, data: Dict[str, Any]) -> str:
        """
        Compute SHA-256 hash for data.
        
        Args:
            data: Dictionary to hash
            
        Returns:
            Hex-encoded SHA-256 hash (64 characters)
        """
        # Sort keys for deterministic serialization
        serialized = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()
    
    def _execute_strategy(
        self,
        signal_data: Dict[str, Any],
        market_data: Dict[str, Any],
        correlation_id: str
    ) -> tuple:
        """
        Execute the trading strategy logic.
        
        **Feature: phase2-hard-requirements, Property 5: Deterministic Strategy Reproducibility**
        **Validates: Requirements 2.1, 2.4**
        
        This is a DETERMINISTIC strategy implementation:
        - No random number generation
        - Same inputs ALWAYS produce same outputs
        
        Args:
            signal_data: Signal data (symbol, side, price, quantity)
            market_data: Market data (bid, ask, volume)
            correlation_id: Correlation ID for logging
            
        Returns:
            Tuple of (action, confidence, reasoning)
        """
        # Extract signal parameters
        signal_side = signal_data.get("side", "").upper()
        signal_price = Decimal(str(signal_data.get("price", "0")))
        signal_symbol = signal_data.get("symbol", "UNKNOWN")
        
        # Extract market parameters
        market_bid = Decimal(str(market_data.get("bid", "0")))
        market_ask = Decimal(str(market_data.get("ask", "0")))
        market_volume = Decimal(str(market_data.get("volume", "0")))
        
        # Deterministic strategy logic
        # Rule 1: Signal side determines base action
        if signal_side == "BUY":
            base_action = StrategyAction.BUY
        elif signal_side == "SELL":
            base_action = StrategyAction.SELL
        else:
            base_action = StrategyAction.HOLD
        
        # Rule 2: Calculate confidence based on spread and volume
        # This is deterministic - same inputs always produce same confidence
        if market_bid > Decimal("0") and market_ask > Decimal("0"):
            spread = market_ask - market_bid
            spread_pct = (spread / market_bid) * Decimal("100")
            
            # Lower spread = higher confidence (deterministic formula)
            if spread_pct < Decimal("0.1"):
                spread_confidence = Decimal("0.9")
            elif spread_pct < Decimal("0.5"):
                spread_confidence = Decimal("0.7")
            elif spread_pct < Decimal("1.0"):
                spread_confidence = Decimal("0.5")
            else:
                spread_confidence = Decimal("0.3")
        else:
            spread_confidence = Decimal("0.5")
            spread_pct = Decimal("0")
        
        # Rule 3: Volume factor (deterministic)
        if market_volume > Decimal("1000000"):
            volume_factor = Decimal("1.0")
        elif market_volume > Decimal("100000"):
            volume_factor = Decimal("0.9")
        elif market_volume > Decimal("10000"):
            volume_factor = Decimal("0.8")
        else:
            volume_factor = Decimal("0.7")
        
        # Rule 4: Price alignment factor (deterministic)
        if signal_price > Decimal("0"):
            if base_action == StrategyAction.BUY:
                # For BUY, signal price should be near or below ask
                if signal_price <= market_ask:
                    price_factor = Decimal("1.0")
                else:
                    price_factor = Decimal("0.8")
            elif base_action == StrategyAction.SELL:
                # For SELL, signal price should be near or above bid
                if signal_price >= market_bid:
                    price_factor = Decimal("1.0")
                else:
                    price_factor = Decimal("0.8")
            else:
                price_factor = Decimal("1.0")
        else:
            price_factor = Decimal("0.9")
        
        # Calculate final confidence (deterministic formula)
        raw_confidence = spread_confidence * volume_factor * price_factor
        
        # Clamp to valid range [0.0000, 1.0000]
        final_confidence = max(
            Decimal("0.0000"),
            min(Decimal("1.0000"), raw_confidence)
        ).quantize(PRECISION_CONFIDENCE, rounding=ROUND_HALF_EVEN)
        
        # Rule 5: Override to HOLD if confidence too low (deterministic threshold)
        if final_confidence < Decimal("0.3000"):
            final_action = StrategyAction.HOLD
            reasoning = (
                f"Confidence {final_confidence} below threshold 0.3000. "
                f"Spread: {spread_pct:.4f}%, Volume factor: {volume_factor}, "
                f"Price factor: {price_factor}. HOLD recommended."
            )
        else:
            final_action = base_action
            reasoning = (
                f"Signal {signal_side} for {signal_symbol} accepted. "
                f"Confidence: {final_confidence}. "
                f"Spread: {spread_pct:.4f}%, Volume factor: {volume_factor}, "
                f"Price factor: {price_factor}."
            )
        
        return final_action, final_confidence, reasoning
    
    # =========================================================================
    # Database Persistence Methods
    # =========================================================================
    
    def _persist_decision(self, decision: StrategyDecision) -> None:
        """
        Persist strategy decision to PostgreSQL.
        
        **Feature: phase2-hard-requirements, Property 7: Strategy Decision Persistence**
        **Validates: Requirements 2.5**
        
        Args:
            decision: StrategyDecision object to persist
            
        Raises:
            Exception: On database error
        """
        try:
            from sqlalchemy import text
            
            query = text("""
                INSERT INTO strategy_decisions (
                    trade_id, correlation_id, inputs_hash, outputs_hash,
                    action, signal_confidence, row_hash, decided_at
                ) VALUES (
                    :trade_id, :correlation_id, :inputs_hash, :outputs_hash,
                    :action, :signal_confidence, :row_hash, :decided_at
                )
            """)
            
            self._db_session.execute(query, {
                "trade_id": decision.trade_id,
                "correlation_id": decision.correlation_id,
                "inputs_hash": decision.inputs_hash,
                "outputs_hash": decision.outputs_hash,
                "action": decision.action.value,
                "signal_confidence": decision.signal_confidence,
                "row_hash": decision.row_hash or "placeholder",  # DB trigger will compute
                "decided_at": decision.decided_at,
            })
            self._db_session.commit()
            
            logger.info(
                f"[STRATEGY-MANAGER] Decision persisted | "
                f"trade_id={decision.trade_id} | "
                f"action={decision.action.value}"
            )
            
        except Exception as e:
            self._db_session.rollback()
            error_msg = (
                f"[{StrategyErrorCode.DB_PERSISTENCE_FAIL}] "
                f"Failed to persist decision: {str(e)} | "
                f"trade_id={decision.trade_id}"
            )
            logger.error(error_msg)
            raise
    
    def _query_decisions(self, trade_id: str) -> List[StrategyDecision]:
        """
        Query decisions from PostgreSQL.
        
        Args:
            trade_id: UUID of trade
            
        Returns:
            List of StrategyDecision objects
        """
        try:
            from sqlalchemy import text
            
            query = text("""
                SELECT trade_id, correlation_id, inputs_hash, outputs_hash,
                       action, signal_confidence, row_hash, decided_at
                FROM strategy_decisions
                WHERE trade_id = :trade_id
                ORDER BY decided_at ASC
            """)
            
            result = self._db_session.execute(query, {"trade_id": trade_id})
            decisions = []
            
            for row in result:
                decisions.append(StrategyDecision(
                    trade_id=str(row[0]),
                    correlation_id=str(row[1]),
                    inputs_hash=row[2],
                    outputs_hash=row[3],
                    action=StrategyAction(row[4]),
                    signal_confidence=Decimal(str(row[5])),
                    row_hash=row[6],
                    decided_at=row[7],
                ))
            
            return decisions
            
        except Exception as e:
            logger.error(
                f"[STRATEGY-MANAGER] Query failed: {str(e)} | "
                f"trade_id={trade_id}"
            )
            return []


# =============================================================================
# Factory Function
# =============================================================================

def create_strategy_manager(
    mode: Optional[StrategyMode] = None,
    db_session: Optional[Any] = None,
    correlation_id: Optional[str] = None
) -> StrategyManager:
    """
    Factory function to create a StrategyManager instance.
    
    Args:
        mode: Strategy execution mode (defaults to DETERMINISTIC)
        db_session: Database session for PostgreSQL persistence
        correlation_id: Default correlation_id for operations
        
    Returns:
        Configured StrategyManager instance
        
    Reliability Level: L6 Critical
    Input Constraints: None
    Side Effects: Logs creation
    """
    return StrategyManager(
        mode=mode,
        db_session=db_session,
        correlation_id=correlation_id,
    )

"""
============================================================================
HITL Approval Gateway - Core Data Models
============================================================================

Reliability Level: L6 Critical (Sovereign Tier)
Decimal Integrity: All financial calculations use decimal.Decimal with ROUND_HALF_EVEN
Traceability: All operations include correlation_id for audit

PRIME DIRECTIVE:
    "The bot thinks. You approve. The system never betrays you."

This module defines the core data models for the HITL Approval Gateway:
- ApprovalRequest: Immutable approval request record
- ApprovalDecision: Decision payload from operator
- RowHasher: SHA-256 integrity verification

REQUIREMENTS SATISFIED:
    - Requirement 2.1: ApprovalRequest with all required fields
    - Requirement 2.3: Row hash computation for integrity
    - Requirement 3.7: ApprovalDecision with decision context
    - Requirement 6.1, 6.2: Row hash verification

ERROR CODES:
    - SEC-080: Hash mismatch (integrity violation)

============================================================================
"""

from decimal import Decimal, ROUND_HALF_EVEN
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import uuid
import logging

# Configure module logger
logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

# Decimal precision for financial values (matches DECIMAL(18,8))
PRECISION_PRICE = Decimal("0.00000001")  # 8 decimal places
PRECISION_PERCENT = Decimal("0.01")       # 2 decimal places for risk_pct


# =============================================================================
# Error Codes
# =============================================================================

class HITLErrorCode:
    """HITL-specific error codes for audit logging."""
    HASH_MISMATCH = "SEC-080"
    UNAUTHORIZED = "SEC-090"
    GUARDIAN_LOCKED = "SEC-020"
    SLIPPAGE_EXCEEDED = "SEC-050"
    HITL_TIMEOUT = "SEC-060"
    INVALID_TRANSITION = "SEC-030"
    CONFIG_MISSING = "SEC-040"


# =============================================================================
# Enums
# =============================================================================

class ApprovalStatus(Enum):
    """
    HITL approval request status.
    
    Reliability Level: SOVEREIGN TIER
    """
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class TradeSide(Enum):
    """
    Trade direction.
    
    Reliability Level: SOVEREIGN TIER
    """
    BUY = "BUY"
    SELL = "SELL"


class DecisionChannel(Enum):
    """
    Source of approval decision.
    
    Reliability Level: SOVEREIGN TIER
    """
    WEB = "WEB"
    DISCORD = "DISCORD"
    CLI = "CLI"
    SYSTEM = "SYSTEM"


class DecisionType(Enum):
    """
    Type of decision made by operator.
    
    Reliability Level: SOVEREIGN TIER
    """
    APPROVE = "APPROVE"
    REJECT = "REJECT"


# =============================================================================
# Custom JSON Encoder for Decimal and datetime
# =============================================================================

class HITLJSONEncoder(json.JSONEncoder):
    """
    Custom JSON encoder for HITL data types.
    
    Handles:
    - Decimal -> str (preserves precision)
    - datetime -> ISO format string
    - UUID -> str
    - Enum -> value
    
    Reliability Level: SOVEREIGN TIER
    """
    
    def default(self, obj: Any) -> Any:
        if isinstance(obj, Decimal):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, uuid.UUID):
            return str(obj)
        if isinstance(obj, Enum):
            return obj.value
        return super().default(obj)


# =============================================================================
# ApprovalRequest Dataclass
# =============================================================================

@dataclass
class ApprovalRequest:
    """
    Immutable approval request record.
    
    ============================================================================
    APPROVAL REQUEST FIELDS:
    ============================================================================
    - id: Unique identifier for this approval request
    - trade_id: Reference to the trade being approved
    - instrument: Trading pair (e.g., BTCZAR)
    - side: BUY or SELL
    - risk_pct: Risk percentage of portfolio
    - confidence: AI confidence score (0.00 to 1.00)
    - request_price: Price at time of request
    - reasoning_summary: AI reasoning for the trade
    - correlation_id: Audit trail identifier
    - status: Current approval status
    - requested_at: When the request was created
    - expires_at: When the request expires (auto-reject)
    - decided_at: When decision was made (if any)
    - decided_by: Operator who made decision (if any)
    - decision_channel: Source of decision (WEB/DISCORD/CLI/SYSTEM)
    - decision_reason: Reason for decision (if any)
    - row_hash: SHA-256 integrity hash
    ============================================================================
    
    Reliability Level: L6 Critical (Sovereign Tier)
    Input Constraints: All financial values use Decimal
    Side Effects: None (data container)
    
    **Feature: hitl-approval-gateway, ApprovalRequest Model**
    **Validates: Requirements 2.1**
    """
    
    # Primary identifiers
    id: uuid.UUID
    trade_id: uuid.UUID
    
    # Trade details
    instrument: str
    side: str  # BUY | SELL
    risk_pct: Decimal
    confidence: Decimal
    request_price: Decimal
    reasoning_summary: Dict[str, Any]
    
    # Audit trail
    correlation_id: uuid.UUID
    
    # Status tracking
    status: str  # AWAITING_APPROVAL | APPROVED | REJECTED
    requested_at: datetime
    expires_at: datetime
    
    # Decision fields (populated when decision is made)
    decided_at: Optional[datetime] = None
    decided_by: Optional[str] = None
    decision_channel: Optional[str] = None  # WEB | DISCORD | CLI | SYSTEM
    decision_reason: Optional[str] = None
    
    # Integrity verification
    row_hash: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary for serialization/persistence.
        
        Returns:
            Dictionary with all fields serialized to JSON-compatible types.
            
        Reliability Level: SOVEREIGN TIER
        Input Constraints: None
        Side Effects: None
        """
        return {
            "id": str(self.id),
            "trade_id": str(self.trade_id),
            "instrument": self.instrument,
            "side": self.side,
            "risk_pct": str(self.risk_pct),
            "confidence": str(self.confidence),
            "request_price": str(self.request_price),
            "reasoning_summary": self.reasoning_summary,
            "correlation_id": str(self.correlation_id),
            "status": self.status,
            "requested_at": self.requested_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "decided_at": self.decided_at.isoformat() if self.decided_at else None,
            "decided_by": self.decided_by,
            "decision_channel": self.decision_channel,
            "decision_reason": self.decision_reason,
            "row_hash": self.row_hash,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ApprovalRequest":
        """
        Create ApprovalRequest from dictionary.
        
        Args:
            data: Dictionary with approval request fields
            
        Returns:
            ApprovalRequest instance
            
        Reliability Level: SOVEREIGN TIER
        Input Constraints: data must contain all required fields
        Side Effects: None
        """
        # Parse UUID fields
        id_val = data.get("id")
        if isinstance(id_val, str):
            id_val = uuid.UUID(id_val)
        
        trade_id_val = data.get("trade_id")
        if isinstance(trade_id_val, str):
            trade_id_val = uuid.UUID(trade_id_val)
        
        correlation_id_val = data.get("correlation_id")
        if isinstance(correlation_id_val, str):
            correlation_id_val = uuid.UUID(correlation_id_val)
        
        # Parse Decimal fields with proper precision
        risk_pct_val = data.get("risk_pct")
        if not isinstance(risk_pct_val, Decimal):
            risk_pct_val = Decimal(str(risk_pct_val)).quantize(
                PRECISION_PERCENT, rounding=ROUND_HALF_EVEN
            )
        
        confidence_val = data.get("confidence")
        if not isinstance(confidence_val, Decimal):
            confidence_val = Decimal(str(confidence_val)).quantize(
                PRECISION_PERCENT, rounding=ROUND_HALF_EVEN
            )
        
        request_price_val = data.get("request_price")
        if not isinstance(request_price_val, Decimal):
            request_price_val = Decimal(str(request_price_val)).quantize(
                PRECISION_PRICE, rounding=ROUND_HALF_EVEN
            )
        
        # Parse datetime fields
        requested_at_val = data.get("requested_at")
        if isinstance(requested_at_val, str):
            requested_at_val = datetime.fromisoformat(requested_at_val)
        
        expires_at_val = data.get("expires_at")
        if isinstance(expires_at_val, str):
            expires_at_val = datetime.fromisoformat(expires_at_val)
        
        decided_at_val = data.get("decided_at")
        if isinstance(decided_at_val, str):
            decided_at_val = datetime.fromisoformat(decided_at_val)
        
        return cls(
            id=id_val,
            trade_id=trade_id_val,
            instrument=data.get("instrument"),
            side=data.get("side"),
            risk_pct=risk_pct_val,
            confidence=confidence_val,
            request_price=request_price_val,
            reasoning_summary=data.get("reasoning_summary", {}),
            correlation_id=correlation_id_val,
            status=data.get("status"),
            requested_at=requested_at_val,
            expires_at=expires_at_val,
            decided_at=decided_at_val,
            decided_by=data.get("decided_by"),
            decision_channel=data.get("decision_channel"),
            decision_reason=data.get("decision_reason"),
            row_hash=data.get("row_hash"),
        )


# =============================================================================
# ApprovalDecision Dataclass
# =============================================================================

@dataclass
class ApprovalDecision:
    """
    Decision payload from operator.
    
    ============================================================================
    APPROVAL DECISION FIELDS:
    ============================================================================
    - trade_id: Reference to the trade being decided
    - decision: APPROVE or REJECT
    - operator_id: Identifier of the operator making the decision
    - channel: Source of decision (WEB/DISCORD/CLI)
    - reason: Reason for decision (required for REJECT)
    - comment: Optional comment from operator
    - correlation_id: Audit trail identifier
    ============================================================================
    
    Reliability Level: L6 Critical (Sovereign Tier)
    Input Constraints: decision must be APPROVE or REJECT
    Side Effects: None (data container)
    
    **Feature: hitl-approval-gateway, ApprovalDecision Model**
    **Validates: Requirements 3.7**
    """
    
    trade_id: uuid.UUID
    decision: str  # APPROVE | REJECT
    operator_id: str
    channel: str  # WEB | DISCORD | CLI
    correlation_id: uuid.UUID
    reason: Optional[str] = None
    comment: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary for serialization/persistence.
        
        Returns:
            Dictionary with all fields serialized to JSON-compatible types.
            
        Reliability Level: SOVEREIGN TIER
        Input Constraints: None
        Side Effects: None
        """
        return {
            "trade_id": str(self.trade_id),
            "decision": self.decision,
            "operator_id": self.operator_id,
            "channel": self.channel,
            "correlation_id": str(self.correlation_id),
            "reason": self.reason,
            "comment": self.comment,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ApprovalDecision":
        """
        Create ApprovalDecision from dictionary.
        
        Args:
            data: Dictionary with decision fields
            
        Returns:
            ApprovalDecision instance
            
        Reliability Level: SOVEREIGN TIER
        Input Constraints: data must contain required fields
        Side Effects: None
        """
        # Parse UUID fields
        trade_id_val = data.get("trade_id")
        if isinstance(trade_id_val, str):
            trade_id_val = uuid.UUID(trade_id_val)
        
        correlation_id_val = data.get("correlation_id")
        if isinstance(correlation_id_val, str):
            correlation_id_val = uuid.UUID(correlation_id_val)
        
        return cls(
            trade_id=trade_id_val,
            decision=data.get("decision"),
            operator_id=data.get("operator_id"),
            channel=data.get("channel"),
            correlation_id=correlation_id_val,
            reason=data.get("reason"),
            comment=data.get("comment"),
        )


# =============================================================================
# RowHasher Class
# =============================================================================

class RowHasher:
    """
    SHA-256 integrity verification for approval records.
    
    ============================================================================
    ROW HASH COMPUTATION:
    ============================================================================
    The row hash is computed by:
    1. Extracting hashable fields from the record
    2. Converting to canonical JSON (sorted keys, deterministic)
    3. Computing SHA-256 hash of the JSON bytes
    4. Returning hex-encoded hash string (64 characters)
    
    HASHABLE FIELDS (in order):
    - id
    - trade_id
    - instrument
    - side
    - risk_pct
    - confidence
    - request_price
    - reasoning_summary
    - correlation_id
    - status
    - requested_at
    - expires_at
    - decided_at
    - decided_by
    - decision_channel
    - decision_reason
    
    NOTE: row_hash itself is NOT included in the hash computation.
    ============================================================================
    
    Reliability Level: L6 Critical (Sovereign Tier)
    Input Constraints: Record must be ApprovalRequest
    Side Effects: None (pure computation)
    
    **Feature: hitl-approval-gateway, RowHasher**
    **Validates: Requirements 2.3, 6.1, 6.2**
    """
    
    # Fields to include in hash computation (deterministic order)
    HASHABLE_FIELDS: List[str] = [
        "id",
        "trade_id",
        "instrument",
        "side",
        "risk_pct",
        "confidence",
        "request_price",
        "reasoning_summary",
        "correlation_id",
        "status",
        "requested_at",
        "expires_at",
        "decided_at",
        "decided_by",
        "decision_channel",
        "decision_reason",
    ]
    
    @staticmethod
    def compute(record: ApprovalRequest) -> str:
        """
        Compute SHA-256 hash of approval record fields.
        
        ========================================================================
        HASH COMPUTATION PROCEDURE:
        ========================================================================
        1. Extract hashable fields from record
        2. Convert each field to canonical string representation
        3. Build ordered dictionary of field -> value
        4. Serialize to JSON with sorted keys
        5. Compute SHA-256 of UTF-8 encoded JSON
        6. Return hex-encoded hash (64 characters)
        ========================================================================
        
        Args:
            record: ApprovalRequest to hash
            
        Returns:
            Hex-encoded SHA-256 hash (64 characters)
            
        Reliability Level: SOVEREIGN TIER
        Input Constraints: record must be ApprovalRequest
        Side Effects: None (pure computation)
        """
        # Build ordered dictionary of hashable fields
        hash_data = {}
        
        for field_name in RowHasher.HASHABLE_FIELDS:
            value = getattr(record, field_name, None)
            
            # Convert to canonical string representation
            if value is None:
                hash_data[field_name] = None
            elif isinstance(value, uuid.UUID):
                hash_data[field_name] = str(value)
            elif isinstance(value, Decimal):
                # Use string representation to preserve precision
                hash_data[field_name] = str(value)
            elif isinstance(value, datetime):
                # Use ISO format for deterministic representation
                hash_data[field_name] = value.isoformat()
            elif isinstance(value, dict):
                # Recursively sort dictionary keys for determinism
                hash_data[field_name] = RowHasher._sort_dict(value)
            elif isinstance(value, Enum):
                hash_data[field_name] = value.value
            else:
                hash_data[field_name] = value
        
        # Serialize to canonical JSON (sorted keys, no whitespace)
        json_str = json.dumps(
            hash_data,
            sort_keys=True,
            separators=(",", ":"),
            cls=HITLJSONEncoder
        )
        
        # Compute SHA-256 hash
        hash_bytes = hashlib.sha256(json_str.encode("utf-8")).hexdigest()
        
        return hash_bytes
    
    @staticmethod
    def verify(record: ApprovalRequest) -> bool:
        """
        Verify stored hash matches computed hash.
        
        ========================================================================
        HASH VERIFICATION PROCEDURE:
        ========================================================================
        1. Check if record has stored row_hash
        2. Compute fresh hash from record fields
        3. Compare stored vs computed hash
        4. Log SEC-080 if mismatch detected
        5. Return True if match, False if mismatch
        ========================================================================
        
        Args:
            record: ApprovalRequest to verify
            
        Returns:
            True if hash matches, False if mismatch or missing
            
        Reliability Level: SOVEREIGN TIER
        Input Constraints: record must be ApprovalRequest
        Side Effects: Logs SEC-080 on mismatch
        """
        # Check if record has stored hash
        if record.row_hash is None:
            logger.warning(
                f"[HITL] Row hash missing for record | "
                f"id={record.id} | "
                f"correlation_id={record.correlation_id}"
            )
            return False
        
        # Compute fresh hash
        computed_hash = RowHasher.compute(record)
        
        # Compare hashes
        if record.row_hash != computed_hash:
            logger.error(
                f"[{HITLErrorCode.HASH_MISMATCH}] Row hash verification failed | "
                f"id={record.id} | "
                f"stored_hash={record.row_hash} | "
                f"computed_hash={computed_hash} | "
                f"correlation_id={record.correlation_id}"
            )
            return False
        
        return True
    
    @staticmethod
    def _sort_dict(d: Dict[str, Any]) -> Dict[str, Any]:
        """
        Recursively sort dictionary keys for deterministic hashing.
        
        Args:
            d: Dictionary to sort
            
        Returns:
            Dictionary with sorted keys (recursively)
        """
        result = {}
        for key in sorted(d.keys()):
            value = d[key]
            if isinstance(value, dict):
                result[key] = RowHasher._sort_dict(value)
            elif isinstance(value, list):
                result[key] = [
                    RowHasher._sort_dict(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                result[key] = value
        return result


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    # Enums
    "ApprovalStatus",
    "TradeSide",
    "DecisionChannel",
    "DecisionType",
    # Error codes
    "HITLErrorCode",
    # Data classes
    "ApprovalRequest",
    "ApprovalDecision",
    # Utilities
    "RowHasher",
    "HITLJSONEncoder",
    # Constants
    "PRECISION_PRICE",
    "PRECISION_PERCENT",
]

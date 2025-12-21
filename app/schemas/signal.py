"""
============================================================================
Project Autonomous Alpha v1.3.2
Signal Schema - Pydantic Models for TradingView Webhook Validation
============================================================================

Reliability Level: SOVEREIGN TIER (Mission-Critical)
Input Constraints: DECIMAL(28,10) for all financial values, zero floats
Side Effects: None (pure validation)

SOVEREIGN MANDATE:
- All financial values MUST use decimal.Decimal
- Maximum 10 decimal places (matching PostgreSQL DECIMAL(28,10))
- Zero tolerance for floating-point math

============================================================================
"""

from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN
from typing import Optional, Any
from uuid import UUID
from datetime import datetime
from enum import Enum

from pydantic import (
    BaseModel,
    Field,
    field_validator,
    model_validator,
    ConfigDict,
)


# ============================================================================
# CONSTANTS
# ============================================================================

# Maximum decimal places for financial values (matches DECIMAL(28,10))
MAX_DECIMAL_PLACES = 10

# Maximum total digits (matches DECIMAL(28,10))
MAX_TOTAL_DIGITS = 28


# ============================================================================
# ENUMS
# ============================================================================

class TradeSide(str, Enum):
    """
    Valid trade sides.
    
    Reliability Level: SOVEREIGN TIER
    Input Constraints: Must be exactly 'BUY' or 'SELL'
    Side Effects: None
    """
    BUY = "BUY"
    SELL = "SELL"


# ============================================================================
# CUSTOM VALIDATORS
# ============================================================================

def validate_decimal_precision(value: Any, field_name: str) -> Decimal:
    """
    Validate that a value is a valid Decimal with correct precision.
    
    Reliability Level: SOVEREIGN TIER
    Input Constraints: 
        - Must be convertible to Decimal
        - Maximum 10 decimal places
        - Maximum 28 total digits
        - Must be positive
    Side Effects: None
    
    Raises:
        ValueError: If value fails validation (triggers AUD-001 equivalent)
    """
    # Handle None
    if value is None:
        raise ValueError(f"[AUD-001] {field_name} cannot be None")
    
    # Reject float type explicitly (Zero-Float Mandate)
    if isinstance(value, float):
        raise ValueError(
            f"[AUD-001] {field_name} received float type. "
            f"Sovereign Mandate: All financial values must use Decimal. "
            f"Received: {value} (type: {type(value).__name__})"
        )
    
    try:
        # Convert to Decimal if not already
        if isinstance(value, Decimal):
            decimal_value = value
        elif isinstance(value, (str, int)):
            decimal_value = Decimal(str(value))
        else:
            raise ValueError(
                f"[AUD-001] {field_name} must be Decimal, str, or int. "
                f"Received: {type(value).__name__}"
            )
        
        # Check for special values (NaN, Infinity)
        if not decimal_value.is_finite():
            raise ValueError(
                f"[AUD-001] {field_name} must be a finite number. "
                f"Received: {decimal_value}"
            )
        
        # Check decimal places
        sign, digits, exponent = decimal_value.as_tuple()
        
        if exponent < 0:
            decimal_places = abs(exponent)
            if decimal_places > MAX_DECIMAL_PLACES:
                raise ValueError(
                    f"[AUD-001] {field_name} exceeds maximum {MAX_DECIMAL_PLACES} decimal places. "
                    f"Received: {decimal_places} decimal places in value {decimal_value}"
                )
        
        # Check total digits
        total_digits = len(digits)
        if total_digits > MAX_TOTAL_DIGITS:
            raise ValueError(
                f"[AUD-001] {field_name} exceeds maximum {MAX_TOTAL_DIGITS} total digits. "
                f"Received: {total_digits} digits in value {decimal_value}"
            )
        
        # Check positive (for price and quantity)
        if decimal_value <= 0:
            raise ValueError(
                f"[AUD-001] {field_name} must be positive. "
                f"Received: {decimal_value}"
            )
        
        return decimal_value
        
    except InvalidOperation as e:
        raise ValueError(
            f"[AUD-001] {field_name} is not a valid decimal number. "
            f"Received: {value}. Error: {e}"
        )


# ============================================================================
# SIGNAL INPUT SCHEMA
# ============================================================================

class SignalIn(BaseModel):
    """
    Pydantic model for incoming TradingView webhook signals.
    
    Reliability Level: SOVEREIGN TIER (Mission-Critical)
    Input Constraints:
        - signal_id: Unique identifier from TradingView (idempotency key)
        - symbol: Trading pair (e.g., BTCUSD)
        - side: BUY or SELL
        - price: DECIMAL(28,10) - NO FLOATS
        - quantity: DECIMAL(28,10) - NO FLOATS
    Side Effects: None (pure validation)
    
    SOVEREIGN MANDATE:
        - Zero tolerance for floating-point math
        - All financial values validated to 10 decimal places max
        - Rejects any float type input with AUD-001 error
    """
    
    model_config = ConfigDict(
        # Strict mode: reject unknown fields
        extra="forbid",
        # Use enum values in serialization
        use_enum_values=True,
        # Validate on assignment
        validate_assignment=True,
        # JSON schema customization
        json_schema_extra={
            "example": {
                "signal_id": "TV-SIGNAL-12345",
                "symbol": "BTCUSD",
                "side": "BUY",
                "price": "45000.1234567890",
                "quantity": "0.5000000000"
            }
        }
    )
    
    # TradingView signal identifier (idempotency key)
    signal_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Unique signal identifier from TradingView. Used for idempotency."
    )
    
    # Trading pair
    symbol: str = Field(
        ...,
        min_length=1,
        max_length=20,
        pattern=r"^[A-Z0-9]+$",
        description="Trading pair symbol (e.g., BTCUSD, ETHUSD)"
    )
    
    # Trade direction
    side: TradeSide = Field(
        ...,
        description="Trade direction: BUY or SELL"
    )
    
    # Price - MUST be Decimal, NOT float
    price: Decimal = Field(
        ...,
        description="Signal price. MUST be Decimal with max 10 decimal places. NO FLOATS.",
        decimal_places=MAX_DECIMAL_PLACES,
        gt=0
    )
    
    # Quantity - MUST be Decimal, NOT float
    quantity: Decimal = Field(
        ...,
        description="Signal quantity. MUST be Decimal with max 10 decimal places. NO FLOATS.",
        decimal_places=MAX_DECIMAL_PLACES,
        gt=0
    )
    
    @field_validator("price", mode="before")
    @classmethod
    def validate_price(cls, v: Any) -> Decimal:
        """
        Validate price is a proper Decimal with correct precision.
        
        Reliability Level: SOVEREIGN TIER
        Input Constraints: DECIMAL(28,10), positive, no floats
        Side Effects: None
        """
        return validate_decimal_precision(v, "price")
    
    @field_validator("quantity", mode="before")
    @classmethod
    def validate_quantity(cls, v: Any) -> Decimal:
        """
        Validate quantity is a proper Decimal with correct precision.
        
        Reliability Level: SOVEREIGN TIER
        Input Constraints: DECIMAL(28,10), positive, no floats
        Side Effects: None
        """
        return validate_decimal_precision(v, "quantity")
    
    @field_validator("symbol", mode="before")
    @classmethod
    def validate_symbol_uppercase(cls, v: Any) -> str:
        """
        Ensure symbol is uppercase.
        
        Reliability Level: STANDARD
        Input Constraints: String, uppercase
        Side Effects: None
        """
        if isinstance(v, str):
            return v.upper()
        return v


# ============================================================================
# SIGNAL OUTPUT SCHEMA
# ============================================================================

class SignalOut(BaseModel):
    """
    Pydantic model for signal response after database insertion.
    
    Reliability Level: SOVEREIGN TIER
    Input Constraints: Mirrors signals table structure
    Side Effects: None
    """
    
    model_config = ConfigDict(
        from_attributes=True,
        use_enum_values=True
    )
    
    id: int = Field(..., description="Database primary key")
    correlation_id: UUID = Field(..., description="UUID v4 correlation identifier")
    signal_id: str = Field(..., description="TradingView signal ID")
    symbol: str = Field(..., description="Trading pair")
    side: str = Field(..., description="BUY or SELL")
    price: Decimal = Field(..., description="Signal price")
    quantity: Decimal = Field(..., description="Signal quantity")
    hmac_verified: bool = Field(..., description="HMAC verification status")
    created_at: datetime = Field(..., description="Creation timestamp (UTC)")


# ============================================================================
# END OF SIGNAL SCHEMA
# ============================================================================

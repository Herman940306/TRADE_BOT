"""
============================================================================
Project Autonomous Alpha v1.3.2
Sovereign Brain - Risk Manager
============================================================================

SOVEREIGN TIER INFRASTRUCTURE
Assurance Level: 100% Confidence (Mission-Critical)

THE SOVEREIGN RISK FORMULA
--------------------------
RiskAmount = Equity × 0.01 (Fixed 1% risk per trade)
PositionSize = RiskAmount / SignalPrice

SAFETY GUARDRAILS
-----------------
RISK-001: Position size must be positive
RISK-002: Risk amount must not exceed MAX_RISK_ZAR

ZERO-FLOAT MANDATE
------------------
All financial calculations use decimal.Decimal with ROUND_HALF_EVEN.
No floating-point math is permitted in this module.

============================================================================
"""

import os
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_EVEN, InvalidOperation
from typing import Optional

from dotenv import load_dotenv

# Load environment variables
load_dotenv()


# ============================================================================
# CONSTANTS
# ============================================================================

# Fixed risk percentage per trade (1%)
RISK_PERCENTAGE = Decimal("0.01")

# Decimal precision for financial calculations
DECIMAL_PLACES = Decimal("0.0000000001")  # 10 decimal places


# ============================================================================
# DATA MODELS
# ============================================================================

@dataclass(frozen=True)
class RiskProfile:
    """
    Immutable risk calculation result.
    
    Reliability Level: SOVEREIGN TIER
    Input Constraints: All fields must be Decimal type
    Side Effects: None (immutable dataclass)
    
    Attributes:
        calculated_quantity: Position size in base currency units
        risk_percentage: Risk as decimal (0.01 = 1%)
        entry_price: Signal price used for calculation
        risk_amount_zar: Absolute risk in ZAR
        equity: Account equity at calculation time
    """
    calculated_quantity: Decimal
    risk_percentage: Decimal
    entry_price: Decimal
    risk_amount_zar: Decimal
    equity: Decimal
    
    def __post_init__(self) -> None:
        """Validate all fields are Decimal type."""
        for field_name, field_value in [
            ("calculated_quantity", self.calculated_quantity),
            ("risk_percentage", self.risk_percentage),
            ("entry_price", self.entry_price),
            ("risk_amount_zar", self.risk_amount_zar),
            ("equity", self.equity),
        ]:
            if not isinstance(field_value, Decimal):
                raise TypeError(
                    f"[RISK-000] Field '{field_name}' must be Decimal, "
                    f"got {type(field_value).__name__}. "
                    "Sovereign Mandate: Zero floats in financial data."
                )


# ============================================================================
# ENVIRONMENT FUNCTIONS
# ============================================================================

def fetch_account_equity() -> Decimal:
    """
    Fetch account equity from environment configuration.
    
    Reliability Level: SOVEREIGN TIER
    Input Constraints: TEST_EQUITY must be valid decimal string in .env
    Side Effects: Reads from environment variables
    
    Returns:
        Decimal: Account equity in ZAR
        
    Raises:
        ValueError: If TEST_EQUITY is not a valid decimal string
    """
    equity_str = os.getenv("TEST_EQUITY", "100000")
    
    try:
        equity = Decimal(equity_str)
    except InvalidOperation as e:
        raise ValueError(
            f"[RISK-003] Invalid TEST_EQUITY value: '{equity_str}'. "
            f"Must be a valid decimal string. Error: {e}"
        )
    
    if equity <= Decimal("0"):
        raise ValueError(
            f"[RISK-004] TEST_EQUITY must be positive, got: {equity}. "
            "Sovereign Mandate: Cannot trade with zero or negative equity."
        )
    
    return equity


def fetch_max_risk_zar() -> Decimal:
    """
    Fetch maximum risk per trade from environment configuration.
    
    Reliability Level: SOVEREIGN TIER
    Input Constraints: MAX_RISK_ZAR must be valid decimal string in .env
    Side Effects: Reads from environment variables
    
    Returns:
        Decimal: Maximum risk amount in ZAR
        
    Raises:
        ValueError: If MAX_RISK_ZAR is not a valid decimal string
    """
    max_risk_str = os.getenv("MAX_RISK_ZAR", "5000")
    
    try:
        max_risk = Decimal(max_risk_str)
    except InvalidOperation as e:
        raise ValueError(
            f"[RISK-005] Invalid MAX_RISK_ZAR value: '{max_risk_str}'. "
            f"Must be a valid decimal string. Error: {e}"
        )
    
    if max_risk <= Decimal("0"):
        raise ValueError(
            f"[RISK-006] MAX_RISK_ZAR must be positive, got: {max_risk}. "
            "Sovereign Mandate: Risk cap must be a positive value."
        )
    
    return max_risk


# ============================================================================
# CORE RISK CALCULATION
# ============================================================================

def calculate_position_size(
    signal_price: Decimal,
    equity: Optional[Decimal] = None,
    correlation_id: Optional[str] = None,
) -> RiskProfile:
    """
    Calculate position size using the Sovereign Risk Formula.
    
    Reliability Level: SOVEREIGN TIER
    Input Constraints:
        - signal_price: Must be Decimal, positive
        - equity: Optional Decimal, fetched from env if not provided
        - correlation_id: Optional string for audit traceability
    Side Effects: Reads from environment if equity not provided
    
    THE SOVEREIGN RISK FORMULA
    --------------------------
    RiskAmount = Equity × 0.01 (Fixed 1% risk per trade)
    PositionSize = RiskAmount / SignalPrice
    
    Args:
        signal_price: Entry price from trading signal (Decimal)
        equity: Account equity in ZAR (optional, fetched from env if None)
        correlation_id: Unique identifier for audit trail (optional)
        
    Returns:
        RiskProfile: Immutable object containing calculation results
        
    Raises:
        TypeError: If signal_price is not Decimal
        ValueError: If signal_price is not positive
        RuntimeError: RISK-001 if position_size <= 0
        RuntimeError: RISK-002 if risk_amount > MAX_RISK_ZAR
    """
    # ========================================================================
    # INPUT VALIDATION
    # ========================================================================
    
    # Validate signal_price type (Zero-Float Mandate)
    if not isinstance(signal_price, Decimal):
        raise TypeError(
            f"[RISK-000] signal_price must be Decimal, got {type(signal_price).__name__}. "
            f"correlation_id={correlation_id}. "
            "Sovereign Mandate: Zero floats in financial data."
        )
    
    # Validate signal_price is positive
    if signal_price <= Decimal("0"):
        raise ValueError(
            f"[RISK-007] signal_price must be positive, got: {signal_price}. "
            f"correlation_id={correlation_id}. "
            "Sovereign Mandate: Cannot calculate position for zero/negative price."
        )
    
    # ========================================================================
    # FETCH CONFIGURATION
    # ========================================================================
    
    # Get equity (from parameter or environment)
    if equity is None:
        equity = fetch_account_equity()
    elif not isinstance(equity, Decimal):
        raise TypeError(
            f"[RISK-000] equity must be Decimal, got {type(equity).__name__}. "
            f"correlation_id={correlation_id}. "
            "Sovereign Mandate: Zero floats in financial data."
        )
    
    # Get maximum risk cap
    max_risk_zar = fetch_max_risk_zar()
    
    # ========================================================================
    # THE SOVEREIGN RISK FORMULA
    # ========================================================================
    
    # Step 1: Calculate risk amount (1% of equity)
    risk_amount = (equity * RISK_PERCENTAGE).quantize(
        DECIMAL_PLACES, rounding=ROUND_HALF_EVEN
    )
    
    # Step 2: RISK-002 Safety Guardrail - Check max risk cap
    if risk_amount > max_risk_zar:
        raise RuntimeError(
            f"[RISK-002] Risk amount {risk_amount} ZAR exceeds MAX_RISK_ZAR "
            f"({max_risk_zar} ZAR). correlation_id={correlation_id}. "
            "Sovereign Mandate: Risk cap exceeded. L6 Safety violation."
        )
    
    # Step 3: Calculate position size
    position_size = (risk_amount / signal_price).quantize(
        DECIMAL_PLACES, rounding=ROUND_HALF_EVEN
    )
    
    # Step 4: RISK-001 Safety Guardrail - Validate position size
    if position_size <= Decimal("0"):
        raise RuntimeError(
            f"[RISK-001] Calculated position size is not positive: {position_size}. "
            f"risk_amount={risk_amount}, signal_price={signal_price}. "
            f"correlation_id={correlation_id}. "
            "Sovereign Mandate: Cannot execute trade with zero/negative quantity."
        )
    
    # ========================================================================
    # BUILD RESULT
    # ========================================================================
    
    return RiskProfile(
        calculated_quantity=position_size,
        risk_percentage=RISK_PERCENTAGE,
        entry_price=signal_price,
        risk_amount_zar=risk_amount,
        equity=equity,
    )


# ============================================================================
# END OF RISK MANAGER
# ============================================================================

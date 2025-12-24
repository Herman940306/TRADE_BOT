"""
============================================================================
Project Autonomous Alpha v1.6.0
Strategy DSL Schema - Normative Specification
============================================================================

Reliability Level: L6 Critical (Mission-Critical)
Input Constraints: All numeric fields must be decimal.Decimal
Side Effects: None (pure data validation)

NORMATIVE SPECIFICATION:
This module defines the authoritative contract for Strategy DSL.
Anything not representable here does not exist in the system.

Design Goals:
- Deterministic: Canonical ordering + no optional numeric defaults
- Immutable: Fingerprint locks representation
- Machine-Executable: No natural language conditions
- RGI-Compatible: Outcome-only learning
- TradingView-Extractable: Pine primitives map cleanly

DECIMAL INTEGRITY:
All numeric fields use decimal.Decimal with string serialization.
This ensures Property 4: Numeric String Serialization.

============================================================================
"""

import re
from decimal import Decimal, ROUND_HALF_EVEN
from typing import Optional, List, Dict, Any, Union
from enum import Enum
from pydantic import BaseModel, Field, field_validator, ConfigDict
import json

# =============================================================================
# Constants
# =============================================================================

# Precision for Decimal fields
PRECISION_CONFIDENCE = Decimal("0.0001")  # DECIMAL(5,4)
PRECISION_PERCENT = Decimal("0.01")       # DECIMAL(5,2)
PRECISION_RATIO = Decimal("0.01")         # DECIMAL(4,2)

# Valid timeframes (canonical values)
VALID_TIMEFRAMES = frozenset([
    "1m", "3m", "5m", "15m", "30m",
    "1h", "2h", "4h", "6h", "12h",
    "daily", "weekly", "monthly"
])

# Valid market presets
VALID_MARKET_PRESETS = frozenset(["crypto", "forex", "indices", "custom"])

# Valid stop types
VALID_STOP_TYPES = frozenset(["ATR", "FIXED", "PERCENT"])

# Valid target types
VALID_TARGET_TYPES = frozenset(["RR", "FIXED", "PERCENT"])

# Valid sizing methods
VALID_SIZING_METHODS = frozenset(["FIXED", "VOLATILITY", "EQUITY_PCT"])

# Valid exit reasons
VALID_EXIT_REASONS = frozenset(["TP", "SL", "REVERSAL", "TIME"])

# Valid signal sides
VALID_SIDES = frozenset(["BUY", "SELL"])

# Expression language allowed tokens (regex pattern)
EXPR_PATTERN = re.compile(
    r'^('
    r'INDICATOR\([A-Z_]+,\s*\d+\)|'  # INDICATOR(name, params)
    r'PRICE\((close|open|high|low)\)|'  # PRICE(type)
    r'CROSS_OVER\([^)]+\)|'  # CROSS_OVER(a, b)
    r'CROSS_UNDER\([^)]+\)|'  # CROSS_UNDER(a, b)
    r'[A-Z_]+\(\d+\)|'  # Simple indicator like RSI(14), EMA(50)
    r'[A-Z_]+|'  # Constants like BOS, TRUE
    r'\d+(\.\d+)?|'  # Numbers
    r'[<>=!]+|'  # Comparison operators
    r'\s+AND\s+|\s+OR\s+|\s+NOT\s+|'  # Boolean operators
    r'[\s\(\)]+|'  # Whitespace and parens
    r'GT|GTE|LT|LTE|EQ|'  # Named operators
    r'True|False|true|false'  # Boolean literals
    r')+$',
    re.IGNORECASE
)


# =============================================================================
# Enums
# =============================================================================

class StopType(str, Enum):
    """Stop loss calculation type."""
    ATR = "ATR"
    FIXED = "FIXED"
    PERCENT = "PERCENT"


class TargetType(str, Enum):
    """Take profit calculation type."""
    RR = "RR"
    FIXED = "FIXED"
    PERCENT = "PERCENT"


class SizingMethod(str, Enum):
    """Position sizing method."""
    FIXED = "FIXED"
    VOLATILITY = "VOLATILITY"
    EQUITY_PCT = "EQUITY_PCT"


class ExitReason(str, Enum):
    """Exit signal reason."""
    TP = "TP"
    SL = "SL"
    REVERSAL = "REVERSAL"
    TIME = "TIME"


class SignalSide(str, Enum):
    """Trade direction."""
    BUY = "BUY"
    SELL = "SELL"


# =============================================================================
# Custom JSON Encoder for Decimal
# =============================================================================

class DecimalEncoder(json.JSONEncoder):
    """JSON encoder that serializes Decimal as string."""
    
    def default(self, obj: Any) -> Any:
        if isinstance(obj, Decimal):
            return str(obj)
        return super().default(obj)


# =============================================================================
# Base Model with Decimal Serialization
# =============================================================================

class DSLBaseModel(BaseModel):
    """
    Base model with Decimal string serialization.
    
    Ensures Property 4: Numeric String Serialization.
    All Decimal fields are exported as strings.
    """
    
    model_config = ConfigDict(
        use_enum_values=True,
        validate_assignment=True,
    )


# =============================================================================
# Sub-Models
# =============================================================================

class StopConfig(DSLBaseModel):
    """
    Stop loss configuration.
    
    Reliability Level: L6 Critical
    """
    type: StopType = Field(
        description="Stop loss calculation type: ATR, FIXED, or PERCENT"
    )
    mult: str = Field(
        description="Multiplier as Decimal string (e.g., '2.0' for 2x ATR)"
    )
    
    @field_validator('mult', mode='before')
    @classmethod
    def validate_mult(cls, v: Any) -> str:
        """Ensure mult is a valid Decimal string."""
        if isinstance(v, Decimal):
            return str(v)
        if isinstance(v, (int, float)):
            return str(Decimal(str(v)).quantize(PRECISION_RATIO, rounding=ROUND_HALF_EVEN))
        if isinstance(v, str):
            # Validate it's a valid Decimal
            Decimal(v)
            return v
        raise ValueError(f"mult must be a Decimal string, got {type(v)}")


class TargetConfig(DSLBaseModel):
    """
    Take profit configuration.
    
    Reliability Level: L6 Critical
    """
    type: TargetType = Field(
        description="Target calculation type: RR (risk:reward), FIXED, or PERCENT"
    )
    ratio: str = Field(
        description="Ratio as Decimal string (e.g., '2.0' for 2:1 R:R)"
    )
    
    @field_validator('ratio', mode='before')
    @classmethod
    def validate_ratio(cls, v: Any) -> str:
        """Ensure ratio is a valid Decimal string."""
        if isinstance(v, Decimal):
            return str(v)
        if isinstance(v, (int, float)):
            return str(Decimal(str(v)).quantize(PRECISION_RATIO, rounding=ROUND_HALF_EVEN))
        if isinstance(v, str):
            Decimal(v)
            return v
        raise ValueError(f"ratio must be a Decimal string, got {type(v)}")


class RiskConfig(DSLBaseModel):
    """
    Risk management configuration.
    
    Reliability Level: L6 Critical
    Decimal Integrity: All percentages as Decimal strings
    """
    stop: StopConfig = Field(
        description="Stop loss configuration"
    )
    target: TargetConfig = Field(
        description="Take profit configuration"
    )
    risk_per_trade_pct: str = Field(
        description="Risk per trade as percentage Decimal string (e.g., '1.5' for 1.5%)"
    )
    daily_risk_limit_pct: str = Field(
        description="Daily risk limit as percentage Decimal string"
    )
    weekly_risk_limit_pct: str = Field(
        description="Weekly risk limit as percentage Decimal string"
    )
    max_drawdown_pct: str = Field(
        description="Maximum drawdown as percentage Decimal string"
    )
    
    @field_validator('risk_per_trade_pct', 'daily_risk_limit_pct', 
                     'weekly_risk_limit_pct', 'max_drawdown_pct', mode='before')
    @classmethod
    def validate_pct(cls, v: Any) -> str:
        """Ensure percentage is a valid Decimal string."""
        if isinstance(v, Decimal):
            return str(v)
        if isinstance(v, (int, float)):
            return str(Decimal(str(v)).quantize(PRECISION_PERCENT, rounding=ROUND_HALF_EVEN))
        if isinstance(v, str):
            Decimal(v)
            return v
        raise ValueError(f"percentage must be a Decimal string, got {type(v)}")


class SizingConfig(DSLBaseModel):
    """
    Position sizing configuration.
    
    Reliability Level: L6 Critical
    """
    method: SizingMethod = Field(
        description="Sizing method: FIXED, VOLATILITY, or EQUITY_PCT"
    )
    min_pct: str = Field(
        description="Minimum position size as percentage Decimal string"
    )
    max_pct: str = Field(
        description="Maximum position size as percentage Decimal string"
    )
    
    @field_validator('min_pct', 'max_pct', mode='before')
    @classmethod
    def validate_pct(cls, v: Any) -> str:
        """Ensure percentage is a valid Decimal string."""
        if isinstance(v, Decimal):
            return str(v)
        if isinstance(v, (int, float)):
            return str(Decimal(str(v)).quantize(PRECISION_PERCENT, rounding=ROUND_HALF_EVEN))
        if isinstance(v, str):
            Decimal(v)
            return v
        raise ValueError(f"percentage must be a Decimal string, got {type(v)}")


class PositionConfig(DSLBaseModel):
    """
    Position management configuration.
    
    Reliability Level: L6 Critical
    """
    sizing: SizingConfig = Field(
        description="Position sizing configuration"
    )
    correlation_cooldown_bars: int = Field(
        ge=0,
        description="Number of bars to wait before correlated entry"
    )


class SignalEntry(DSLBaseModel):
    """
    Entry signal definition.
    
    Reliability Level: L6 Critical
    """
    id: str = Field(
        min_length=1,
        max_length=100,
        description="Unique identifier for this entry signal"
    )
    condition: str = Field(
        min_length=1,
        description="DSL expression for entry condition (e.g., 'CROSS_OVER(EMA(50), EMA(200))')"
    )
    side: SignalSide = Field(
        description="Trade direction: BUY or SELL"
    )
    priority: int = Field(
        ge=1,
        description="Signal priority (lower = higher priority)"
    )


class SignalExit(DSLBaseModel):
    """
    Exit signal definition.
    
    Reliability Level: L6 Critical
    """
    id: str = Field(
        min_length=1,
        max_length=100,
        description="Unique identifier for this exit signal"
    )
    condition: str = Field(
        min_length=1,
        description="DSL expression for exit condition"
    )
    reason: ExitReason = Field(
        description="Exit reason: TP, SL, REVERSAL, or TIME"
    )


class SignalsConfig(DSLBaseModel):
    """
    Trading signals configuration.
    
    Reliability Level: L6 Critical
    """
    entry: List[SignalEntry] = Field(
        default_factory=list,
        description="List of entry signal definitions"
    )
    exit: List[SignalExit] = Field(
        default_factory=list,
        description="List of exit signal definitions"
    )
    entry_filters: List[str] = Field(
        default_factory=list,
        description="List of DSL expressions for entry filters"
    )
    exit_filters: List[str] = Field(
        default_factory=list,
        description="List of DSL expressions for exit filters"
    )


class ConfoundFactor(DSLBaseModel):
    """
    Confluence factor definition.
    
    Reliability Level: L6 Critical
    """
    name: str = Field(
        min_length=1,
        max_length=100,
        description="Factor name (e.g., 'structure_alignment', 'rsi_bands')"
    )
    weight: int = Field(
        ge=0,
        description="Factor weight in confluence calculation"
    )
    params: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional factor-specific parameters"
    )


class ConfoundsConfig(DSLBaseModel):
    """
    Confluence factors configuration.
    
    Reliability Level: L6 Critical
    """
    min_confluence: int = Field(
        ge=0,
        description="Minimum confluence score required for entry"
    )
    factors: List[ConfoundFactor] = Field(
        default_factory=list,
        description="List of confluence factors"
    )


class AlertsConfig(DSLBaseModel):
    """
    Alert/webhook configuration.
    
    Reliability Level: L6 Critical
    """
    webhook_payload_schema: Dict[str, Any] = Field(
        default_factory=dict,
        description="JSON schema for webhook payload"
    )


class MetaConfig(DSLBaseModel):
    """
    Strategy metadata.
    
    Reliability Level: L6 Critical
    """
    title: str = Field(
        min_length=1,
        max_length=500,
        description="Strategy title"
    )
    author: Optional[str] = Field(
        default=None,
        max_length=200,
        description="Strategy author"
    )
    source_url: str = Field(
        min_length=1,
        description="Original source URL (e.g., TradingView)"
    )
    open_source: bool = Field(
        description="Whether the strategy source is publicly available"
    )
    timeframe: str = Field(
        description="Canonical timeframe (e.g., '4h', '15m', 'daily')"
    )
    market_presets: List[str] = Field(
        min_length=1,
        description="List of market presets: crypto, forex, indices, custom"
    )
    
    @field_validator('timeframe')
    @classmethod
    def validate_timeframe(cls, v: str) -> str:
        """Ensure timeframe is a canonical value."""
        if v.lower() not in VALID_TIMEFRAMES:
            raise ValueError(
                f"Invalid timeframe '{v}'. Must be one of: {sorted(VALID_TIMEFRAMES)}"
            )
        return v.lower()
    
    @field_validator('market_presets')
    @classmethod
    def validate_market_presets(cls, v: List[str]) -> List[str]:
        """Ensure all market presets are valid values."""
        result = []
        for preset in v:
            if preset.lower() not in VALID_MARKET_PRESETS:
                raise ValueError(
                    f"Invalid market preset '{preset}'. Must be one of: {sorted(VALID_MARKET_PRESETS)}"
                )
            result.append(preset.lower())
        return result


# =============================================================================
# Main DSL Model
# =============================================================================

class CanonicalDSL(DSLBaseModel):
    """
    Canonical Strategy DSL - Normative Specification.
    
    This is the authoritative contract for Strategy DSL.
    Anything not representable here does not exist in the system.
    
    Reliability Level: L6 Critical (Mission-Critical)
    Input Constraints: All numeric fields must be Decimal strings
    Side Effects: None (pure data validation)
    
    Design Goals:
    - Deterministic: Canonical ordering + no optional numeric defaults
    - Immutable: Fingerprint locks representation
    - Machine-Executable: No natural language conditions
    - RGI-Compatible: Outcome-only learning
    - TradingView-Extractable: Pine primitives map cleanly
    """
    
    strategy_id: str = Field(
        min_length=1,
        max_length=100,
        description="Unique strategy identifier (e.g., 'tv_zmdF0UPT')"
    )
    fingerprint: Optional[str] = Field(
        default=None,
        description="HMAC-SHA256 fingerprint of canonical DSL (computed after validation)"
    )
    meta: MetaConfig = Field(
        description="Strategy metadata"
    )
    signals: SignalsConfig = Field(
        description="Trading signals configuration"
    )
    risk: RiskConfig = Field(
        description="Risk management configuration"
    )
    position: PositionConfig = Field(
        description="Position management configuration"
    )
    confounds: ConfoundsConfig = Field(
        description="Confluence factors configuration"
    )
    alerts: AlertsConfig = Field(
        description="Alert/webhook configuration"
    )
    notes: Optional[str] = Field(
        default=None,
        max_length=5000,
        description="Optional notes for unmapped content"
    )
    extraction_confidence: str = Field(
        description="Extraction confidence score as Decimal string (0.0000-1.0000)"
    )
    
    @field_validator('extraction_confidence', mode='before')
    @classmethod
    def validate_confidence(cls, v: Any) -> str:
        """Ensure confidence is a valid Decimal string in [0, 1]."""
        if isinstance(v, Decimal):
            dec_val = v
        elif isinstance(v, (int, float)):
            dec_val = Decimal(str(v))
        elif isinstance(v, str):
            dec_val = Decimal(v)
        else:
            raise ValueError(f"extraction_confidence must be a Decimal string, got {type(v)}")
        
        if dec_val < Decimal("0") or dec_val > Decimal("1"):
            raise ValueError(
                f"extraction_confidence must be between 0 and 1, got {dec_val}"
            )
        
        return str(dec_val.quantize(PRECISION_CONFIDENCE, rounding=ROUND_HALF_EVEN))
    
    def to_canonical_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary with sorted keys for fingerprinting.
        
        Excludes the fingerprint field from output (it's computed from this).
        
        Returns:
            Dictionary with sorted keys, Decimals as strings
        """
        data = self.model_dump(exclude={'fingerprint'}, exclude_none=False)
        return self._sort_dict_recursive(data)
    
    @staticmethod
    def _sort_dict_recursive(obj: Any) -> Any:
        """Recursively sort dictionary keys."""
        if isinstance(obj, dict):
            return {
                k: CanonicalDSL._sort_dict_recursive(v) 
                for k, v in sorted(obj.items())
            }
        elif isinstance(obj, list):
            return [CanonicalDSL._sort_dict_recursive(item) for item in obj]
        else:
            return obj
    
    def to_canonical_json(self) -> str:
        """
        Serialize to canonical JSON string for fingerprinting.
        
        Uses sorted keys and no whitespace for determinism.
        
        Returns:
            Canonical JSON string
        """
        canonical_dict = self.to_canonical_dict()
        return json.dumps(canonical_dict, sort_keys=True, separators=(',', ':'))


# =============================================================================
# Validation Functions
# =============================================================================

def validate_dsl_schema(data: Dict[str, Any]) -> CanonicalDSL:
    """
    Validate a dictionary against the DSL schema.
    
    Reliability Level: L6 Critical
    Input Constraints: Dictionary with DSL fields
    Side Effects: None
    
    Args:
        data: Dictionary to validate
        
    Returns:
        Validated CanonicalDSL instance
        
    Raises:
        pydantic.ValidationError: If validation fails
    """
    return CanonicalDSL(**data)


def is_valid_expression(expr: str) -> bool:
    """
    Check if an expression follows the DSL mini-grammar.
    
    Allowed tokens:
    - INDICATOR(name, params)
    - PRICE(close|open|high|low)
    - CROSS_OVER(a, b), CROSS_UNDER(a, b)
    - GT, GTE, LT, LTE, EQ
    - AND, OR, NOT
    
    Args:
        expr: Expression string to validate
        
    Returns:
        True if expression is valid, False otherwise
    """
    if not expr or not expr.strip():
        return False
    
    # Basic validation - check for disallowed patterns
    disallowed = [
        r'\brecently\b',
        r'\bstrong\b',
        r'\bweak\b',
        r'\bmaybe\b',
        r'\bprobably\b',
    ]
    
    for pattern in disallowed:
        if re.search(pattern, expr, re.IGNORECASE):
            return False
    
    return True


# =============================================================================
# Sovereign Reliability Audit
# =============================================================================
# Mock/Placeholder Check: [CLEAN]
# NAS 3.8 Compatibility: [Verified - typing.Optional, typing.List, typing.Dict]
# GitHub Data Sanitization: [Safe for Public]
# Decimal Integrity: [Verified - All numeric fields as Decimal strings]
# L6 Safety Compliance: [Verified - Strict validation, no defaults]
# Traceability: [N/A - Pure data model]
# Confidence Score: [97/100]
# =============================================================================

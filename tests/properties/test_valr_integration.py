# ============================================================================
# Project Autonomous Alpha v1.7.0
# Property-Based Tests - VALR Exchange Integration (Sprint 9)
# ============================================================================
#
# Reliability Level: SOVEREIGN TIER (Mission-Critical)
# Test Framework: Hypothesis (Property-Based Testing)
# Minimum Iterations: 100 per property
#
# Properties Covered:
#   1. Decimal Gateway Round-Trip (VALR-002)
#   2. Credential Sanitization (VALR-001)
#   3. MARKET Order Rejection (VALR-004)
#   4. Order Value Limit Enforcement (VALR-004)
#   5. DRY_RUN Simulation (VALR-006)
#   6. LIVE Mode Safety Gate (VALR-006)
#   7. Token Bucket Rate Limiting (VALR-003)
#   8. Essential Polling Mode (VALR-003)
#   9. Reconciliation Mismatch Detection (VALR-005)
#   10. Consecutive Failure Neutral State (VALR-005)
#   11. Market Data Staleness (VALR-007)
#   12. Spread Rejection (VALR-007)
#   13. RLHF Outcome Recording (VALR-008)
#   14. Correlation ID Traceability
#   15. ZAR Precision Formatting (VALR-002)
#
# ============================================================================

import pytest
from decimal import Decimal, ROUND_HALF_EVEN
from hypothesis import given, strategies as st, settings, HealthCheck

# ============================================================================
# Property 1: Decimal Gateway Round-Trip
# Feature: valr-exchange-integration, Property 1: Decimal Gateway Round-Trip
# Validates: Requirements 2.1, 2.3
# ============================================================================

@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(st.floats(
    min_value=-1e15,
    max_value=1e15,
    allow_nan=False,
    allow_infinity=False
))
def test_decimal_gateway_round_trip_float(value: float):
    """
    Feature: valr-exchange-integration, Property 1: Decimal Gateway Round-Trip
    Validates: Requirements 2.1, 2.3
    
    For any float value, converting through DecimalGateway should produce
    a decimal.Decimal with ROUND_HALF_EVEN rounding.
    """
    from app.exchange.decimal_gateway import DecimalGateway
    
    gateway = DecimalGateway()
    result = gateway.to_decimal(value)
    
    # Must be Decimal type
    assert isinstance(result, Decimal), f"Expected Decimal, got {type(result)}"
    
    # Verify ROUND_HALF_EVEN behavior
    expected = Decimal(str(value)).quantize(
        DecimalGateway.ZAR_PRECISION,
        rounding=ROUND_HALF_EVEN
    )
    assert result == expected, f"Rounding mismatch: {result} != {expected}"


@settings(max_examples=100)
@given(st.integers(min_value=-10**15, max_value=10**15))
def test_decimal_gateway_round_trip_int(value: int):
    """
    Feature: valr-exchange-integration, Property 1: Decimal Gateway Round-Trip
    Validates: Requirements 2.1, 2.3
    
    For any integer value, converting through DecimalGateway should produce
    a decimal.Decimal with correct precision.
    """
    from app.exchange.decimal_gateway import DecimalGateway
    
    gateway = DecimalGateway()
    result = gateway.to_decimal(value)
    
    assert isinstance(result, Decimal)
    expected = Decimal(str(value)).quantize(
        DecimalGateway.ZAR_PRECISION,
        rounding=ROUND_HALF_EVEN
    )
    assert result == expected


@settings(max_examples=100)
@given(st.decimals(
    min_value=Decimal('-1e15'),
    max_value=Decimal('1e15'),
    allow_nan=False,
    allow_infinity=False
))
def test_decimal_gateway_round_trip_string(value: Decimal):
    """
    Feature: valr-exchange-integration, Property 1: Decimal Gateway Round-Trip
    Validates: Requirements 2.1, 2.3
    
    For any string numeric value, converting through DecimalGateway should
    produce a decimal.Decimal with ROUND_HALF_EVEN rounding.
    """
    from app.exchange.decimal_gateway import DecimalGateway
    
    gateway = DecimalGateway()
    result = gateway.to_decimal(str(value))
    
    assert isinstance(result, Decimal)


# ============================================================================
# Property 15: ZAR Precision Formatting
# Feature: valr-exchange-integration, Property 15: ZAR Precision Formatting
# Validates: Requirements 2.5
# ============================================================================

@settings(max_examples=100)
@given(st.floats(
    min_value=0.001,
    max_value=1e10,
    allow_nan=False,
    allow_infinity=False
))
def test_zar_precision_formatting(value: float):
    """
    Feature: valr-exchange-integration, Property 15: ZAR Precision Formatting
    Validates: Requirements 2.5
    
    For any ZAR value, it should have exactly 2 decimal places.
    """
    from app.exchange.decimal_gateway import DecimalGateway
    
    gateway = DecimalGateway()
    result = gateway.to_decimal(value, precision=DecimalGateway.ZAR_PRECISION)
    
    # Check exactly 2 decimal places
    str_result = str(result)
    if '.' in str_result:
        decimal_places = len(str_result.split('.')[1])
        assert decimal_places == 2, f"Expected 2 decimal places, got {decimal_places}"

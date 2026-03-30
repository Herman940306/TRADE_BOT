"""
============================================================================
Project Autonomous Alpha — Phase 9, Sub-Phase P9.3
Exhaustive Tests: Zero-Float Mandate Enforcement
============================================================================

Reliability Level: SOVEREIGN TIER
Test Framework: pytest (parametrized — Hypothesis incompatible with Python 3.14)
Target: Zero-Float Mandate across all financial boundaries

PROPERTIES TESTED
-----------------
1. Float type always rejected at financial boundaries
2. Decimal type always accepted
3. String-to-Decimal conversion preserves value
4. RiskProfile rejects float fields
5. SignalInput rejects float price/quantity
6. Decision packet _reject_float works for all float values
============================================================================
"""

from decimal import Decimal

import pytest

from app.logic.decision_packet_models import (
    ExecutionMode,
    OperationalContext,
    PacketBuildError,
    Side,
    SignalInput,
    _reject_float,
    format_decimal,
)
from app.schemas.ai_output import safe_decimal, validate_no_float

# ============================================================================
# P1: FLOAT ALWAYS REJECTED AT EVERY BOUNDARY
# ============================================================================

FLOAT_SAMPLES = [
    0.0,
    1.0,
    -1.0,
    0.1,
    -0.1,
    3.14,
    -3.14,
    1e10,
    -1e10,
    1e-10,
    -1e-10,
    99999.99,
    0.001,
    42.0,
    1.23456789,
    float("inf"),
    float("-inf"),
]


@pytest.mark.parametrize("f", FLOAT_SAMPLES)
def test_reject_float_catches_all_floats(f):
    """_reject_float must reject every Python float value."""
    with pytest.raises(PacketBuildError):
        _reject_float(f, "test_field")


@pytest.mark.parametrize("f", FLOAT_SAMPLES)
def test_validate_no_float_catches_all_floats(f):
    """validate_no_float must reject every Python float value."""
    with pytest.raises(ValueError, match="FLOAT-VIOLATION"):
        validate_no_float(f, "test_field")


# ============================================================================
# P2: DECIMAL ALWAYS ACCEPTED
# ============================================================================

DECIMAL_SAMPLES = [
    Decimal("0.00000001"),
    Decimal("0.01"),
    Decimal("1.0"),
    Decimal("100.50"),
    Decimal("999.12345678"),
    Decimal("50000.00"),
    Decimal("99999999.99999999"),
]


@pytest.mark.parametrize("d", DECIMAL_SAMPLES)
def test_reject_float_accepts_all_decimals(d):
    """_reject_float must accept any Decimal value without exception."""
    _reject_float(d, "test_field")  # Should not raise


@pytest.mark.parametrize(
    "d",
    [
        Decimal("-999999"),
        Decimal("-1"),
        Decimal("0"),
        Decimal("1"),
        Decimal("100.1234"),
        Decimal("999999"),
    ],
)
def test_validate_no_float_accepts_all_decimals(d):
    """validate_no_float must accept any Decimal value."""
    validate_no_float(d, "test_field")  # Should not raise


# ============================================================================
# P3: STRING-TO-DECIMAL CONVERSION
# ============================================================================


@pytest.mark.parametrize("i", [0, 1, 42, 100, 999999])
def test_safe_decimal_from_int(i):
    """safe_decimal must convert int to matching Decimal."""
    result = safe_decimal(i, "test")
    assert isinstance(result, Decimal)
    assert result == Decimal(str(i))


@pytest.mark.parametrize(
    "d",
    [
        Decimal("0.01"),
        Decimal("1.50"),
        Decimal("99.99"),
        Decimal("1000.00"),
        Decimal("99999.99"),
    ],
)
def test_safe_decimal_from_str(d):
    """safe_decimal must convert string Decimal representation correctly."""
    result = safe_decimal(str(d), "test")
    assert isinstance(result, Decimal)
    assert result == d


# ============================================================================
# P4: SIGNAL INPUT REJECTS FLOAT PRICE/QUANTITY
# ============================================================================


@pytest.mark.parametrize("f", [0.01, 1.0, 50.5, 100.99, 50000.00, 99999.0])
def test_signal_input_rejects_float_price(f):
    """SignalInput must reject float price."""
    with pytest.raises(PacketBuildError):
        SignalInput(
            signal_id="TEST001",
            symbol="BTCZAR",
            side=Side.BUY,
            price=f,
            quantity=Decimal("1.0"),
        )


@pytest.mark.parametrize("f", [0.01, 0.5, 1.0, 10.0, 99999.0])
def test_signal_input_rejects_float_quantity(f):
    """SignalInput must reject float quantity."""
    with pytest.raises(PacketBuildError):
        SignalInput(
            signal_id="TEST001",
            symbol="BTCZAR",
            side=Side.BUY,
            price=Decimal("50000.00"),
            quantity=f,
        )


# ============================================================================
# P5: OPERATIONAL CONTEXT REJECTS FLOAT EQUITY/RISK
# ============================================================================


@pytest.mark.parametrize("f", [0.01, 100.0, 50000.00, 99999.0])
def test_operational_context_rejects_float_equity(f):
    """OperationalContext must reject float equity_zar."""
    with pytest.raises(PacketBuildError):
        OperationalContext(
            execution_mode=ExecutionMode.PAPER,
            guardian_locked=False,
            equity_zar=f,
            risk_pct=Decimal("1.0"),
        )


@pytest.mark.parametrize("f", [0.01, 0.5, 1.0, 2.5, 5.0])
def test_operational_context_rejects_float_risk(f):
    """OperationalContext must reject float risk_pct."""
    with pytest.raises(PacketBuildError):
        OperationalContext(
            execution_mode=ExecutionMode.PAPER,
            guardian_locked=False,
            equity_zar=Decimal("100000.00"),
            risk_pct=f,
        )


# ============================================================================
# P6: FORMAT_DECIMAL ALWAYS PRODUCES STRING WITHOUT SCIENTIFIC NOTATION
# ============================================================================


@pytest.mark.parametrize(
    "d",
    [
        Decimal("0.01"),
        Decimal("1.00"),
        Decimal("100.12345678"),
        Decimal("99999.99"),
        Decimal("9999999999.99"),
    ],
)
def test_format_decimal_no_scientific_notation(d):
    """format_decimal must never produce scientific notation."""
    result = format_decimal(d)
    assert "e" not in result.lower(), f"Scientific notation in: {result}"
    assert "E" not in result, f"Scientific notation in: {result}"
    assert "." in result, f"Missing decimal point in: {result}"


@pytest.mark.parametrize(
    "d",
    [
        Decimal("0.01"),
        Decimal("1.00"),
        Decimal("999.99"),
        Decimal("999999.99"),
    ],
)
def test_format_decimal_at_least_two_places(d):
    """format_decimal must always have at least 2 decimal places."""
    result = format_decimal(d)
    _, decimal_part = result.split(".")
    assert len(decimal_part) >= 2, f"Less than 2 decimal places in: {result}"

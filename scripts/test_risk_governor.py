"""
============================================================================
Project Autonomous Alpha v1.4.0
Test Script - RiskGovernor and OrderManager Integration
============================================================================

Reliability Level: SOVEREIGN TIER
Purpose: Verify RiskGovernor and OrderManager work correctly

Run with: python scripts/test_risk_governor.py

============================================================================
"""

import asyncio
import sys
import os
from decimal import Decimal

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.logic.risk_governor import RiskGovernor, ExecutionPermit
from app.logic.order_manager import OrderManager, ReconciliationStatus
from app.logic.valr_link import OrderSide


def test_risk_governor():
    """Test RiskGovernor execution permit generation."""
    print("\n" + "=" * 60)
    print("TEST 1: RiskGovernor - Execution Permit Generation")
    print("=" * 60)
    
    governor = RiskGovernor()
    
    # Test case 1: Valid permit
    print("\n[Test 1.1] Valid trade parameters...")
    permit = governor.get_execution_permit(
        equity_zar=Decimal("100000.00"),
        entry_price=Decimal("1850000.00"),  # BTC price in ZAR
        stop_price=Decimal("1830000.00"),   # 1.08% stop
        atr=Decimal("25000.00"),            # ATR for volatility
        correlation_id="TEST-001"
    )
    
    if permit:
        print(f"   ✅ APPROVED | qty={permit.approved_qty} | risk_zar={permit.planned_risk_zar}")
        print(f"   Entry: R{permit.entry_price} | Stop: R{permit.stop_price}")
    else:
        print("   ❌ REJECTED (unexpected)")
        return False
    
    # Test case 2: Malformed entry price
    print("\n[Test 1.2] Malformed entry price (<=0)...")
    permit = governor.get_execution_permit(
        equity_zar=Decimal("100000.00"),
        entry_price=Decimal("0"),
        stop_price=Decimal("1830000.00"),
        correlation_id="TEST-002"
    )
    
    if permit is None:
        print("   ✅ RISK-REJECTED (as expected)")
    else:
        print("   ❌ Should have been rejected")
        return False
    
    # Test case 3: Malformed ATR
    print("\n[Test 1.3] Malformed ATR (<=0)...")
    permit = governor.get_execution_permit(
        equity_zar=Decimal("100000.00"),
        entry_price=Decimal("1850000.00"),
        stop_price=Decimal("1830000.00"),
        atr=Decimal("-100"),
        correlation_id="TEST-003"
    )
    
    if permit is None:
        print("   ✅ RISK-REJECTED (as expected)")
    else:
        print("   ❌ Should have been rejected")
        return False
    
    # Test case 4: Stop too close
    print("\n[Test 1.4] Stop distance too small...")
    permit = governor.get_execution_permit(
        equity_zar=Decimal("100000.00"),
        entry_price=Decimal("1850000.00"),
        stop_price=Decimal("1849999.00"),  # Only R1 difference
        correlation_id="TEST-004"
    )
    
    if permit is None:
        print("   ✅ RISK-REJECTED (as expected)")
    else:
        print("   ❌ Should have been rejected")
        return False
    
    print("\n✅ All RiskGovernor tests passed!")
    return True


def test_circuit_breakers():
    """Test RiskGovernor circuit breakers."""
    print("\n" + "=" * 60)
    print("TEST 2: RiskGovernor - Circuit Breakers")
    print("=" * 60)
    
    governor = RiskGovernor()
    
    # Test case 1: Normal conditions
    print("\n[Test 2.1] Normal conditions (should pass)...")
    result = governor.check_circuit_breakers(
        daily_pnl_pct=Decimal("-0.01"),  # -1% (within limit)
        consecutive_losses=1,
        correlation_id="TEST-CB-001"
    )
    
    if result.passed:
        print(f"   ✅ PASSED | reason={result.reason}")
    else:
        print(f"   ❌ Should have passed | reason={result.reason}")
        return False
    
    # Test case 2: Daily loss limit hit
    print("\n[Test 2.2] Daily loss limit hit (-3%)...")
    result = governor.check_circuit_breakers(
        daily_pnl_pct=Decimal("-0.03"),  # -3% (at limit)
        consecutive_losses=0,
        correlation_id="TEST-CB-002"
    )
    
    if not result.passed:
        print(f"   ✅ CIRCUIT-BREAKER TRIGGERED | reason={result.reason}")
    else:
        print("   ❌ Should have triggered circuit breaker")
        return False
    
    # Test case 3: Consecutive losses
    print("\n[Test 2.3] Max consecutive losses (3)...")
    result = governor.check_circuit_breakers(
        daily_pnl_pct=Decimal("0.00"),
        consecutive_losses=3,
        correlation_id="TEST-CB-003"
    )
    
    if not result.passed:
        print(f"   ✅ CIRCUIT-BREAKER TRIGGERED | reason={result.reason}")
    else:
        print("   ❌ Should have triggered circuit breaker")
        return False
    
    print("\n✅ All Circuit Breaker tests passed!")
    return True


async def test_order_manager():
    """Test OrderManager reconciliation (mock mode)."""
    print("\n" + "=" * 60)
    print("TEST 3: OrderManager - Reconciliation Loop (Mock Mode)")
    print("=" * 60)
    
    # Create permit
    governor = RiskGovernor()
    permit = governor.get_execution_permit(
        equity_zar=Decimal("100000.00"),
        entry_price=Decimal("1850000.00"),
        stop_price=Decimal("1830000.00"),
        correlation_id="TEST-OM-001"
    )
    
    if not permit:
        print("   ❌ Failed to create permit")
        return False
    
    # Execute with reconciliation
    print("\n[Test 3.1] Execute with reconciliation (mock)...")
    manager = OrderManager()
    
    result = await manager.execute_with_reconciliation(
        symbol="BTCZAR",
        side=OrderSide.BUY,
        permit=permit,
        correlation_id="TEST-OM-001"
    )
    
    print(f"   Order ID: {result.order_id}")
    print(f"   Status: {result.status.value}")
    print(f"   Filled: {result.filled_qty}")
    print(f"   Avg Price: {result.avg_price}")
    print(f"   Execution Time: {result.execution_time_ms}ms")
    print(f"   Is Mock: {result.is_mock}")
    
    if result.status == ReconciliationStatus.MOCK_FILLED:
        print("\n   ✅ Mock order executed successfully!")
    else:
        print(f"\n   ❌ Unexpected status: {result.status}")
        return False
    
    print("\n✅ All OrderManager tests passed!")
    return True


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("AUTONOMOUS ALPHA v1.4.0 - INTEGRATION TESTS")
    print("RiskGovernor + OrderManager")
    print("=" * 60)
    
    all_passed = True
    
    # Test RiskGovernor
    if not test_risk_governor():
        all_passed = False
    
    # Test Circuit Breakers
    if not test_circuit_breakers():
        all_passed = False
    
    # Test OrderManager (async)
    if not asyncio.run(test_order_manager()):
        all_passed = False
    
    # Summary
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 ALL TESTS PASSED - v1.4.0 Integration Complete")
    else:
        print("❌ SOME TESTS FAILED - Review output above")
    print("=" * 60 + "\n")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())

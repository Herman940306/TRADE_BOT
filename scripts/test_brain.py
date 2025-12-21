from decimal import Decimal
from app.logic.risk_manager import calculate_position_size

def run_brain_test():
    print("="*60)
    print("SOVEREIGN BRAIN - UNIT TEST SUITE")
    print("="*60)

    # Scenario A: Normal Trade (100k Equity, 50k Price)
    # Expectation: 1% risk = 1000 ZAR. 1000 / 50000 = 0.02 qty.
    try:
        res = calculate_position_size(signal_price=Decimal("50000.00"), equity=Decimal("100000.00"))
        print(f"✅ SCENARIO A (NORMAL): Quantity {res.calculated_quantity} | Risk ZAR: {res.risk_amount_zar}")
    except Exception as e:
        print(f"❌ SCENARIO A FAILED: {e}")

    # Scenario B: The Whale (Excessive Risk)
    # Expectation: 1% of 1M = 10,000 ZAR. This exceeds the 5,000 ZAR cap.
    try:
        calculate_position_size(signal_price=Decimal("10.00"), equity=Decimal("1000000.00"))
        print("❌ SCENARIO B FAILED: Should have triggered RISK-002")
    except RuntimeError as e:
        if "RISK-002" in str(e):
            print("✅ SCENARIO B (WHALE): Correcty blocked by RISK-002")

    # Scenario C: The Dust (Price is 1 Quadrillion - definitely forces zero)
    # Expectation: 1% of 100 = 1 ZAR. 1 / 1,000,000,000,000,000 = 0.000000000000001
    # This rounds to 0 at 10 decimal places, triggering RISK-001
    try:
        calculate_position_size(signal_price=Decimal("1000000000000000.00"), equity=Decimal("100.00"))
        print("❌ SCENARIO C FAILED: Should have triggered RISK-001")
    except RuntimeError as e:
        if "RISK-001" in str(e):
            print("✅ SCENARIO C (DUST): Correctly blocked by RISK-001")
        else:
            print(f"❌ SCENARIO C FAILED with unexpected error: {e}")

if __name__ == "__main__":
    run_brain_test()
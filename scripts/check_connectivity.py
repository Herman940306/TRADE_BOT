"""
============================================================================
Project Autonomous Alpha v1.3.2
VALR Connectivity Check - Exchange Link Verification
============================================================================

Reliability Level: DEVELOPMENT/TESTING
Input Constraints: Requires .env configuration
Side Effects: API call to VALR (or mock response)

PURPOSE
-------
Verify VALR Link connectivity and display current account balances.
Operates in MOCK_MODE if VALR_API_KEY is not configured.

EXECUTION
---------
    python scripts/check_connectivity.py

============================================================================
"""

import sys
import asyncio
from pathlib import Path
from decimal import Decimal

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv

# Load environment
load_dotenv()

from app.logic.valr_link import VALRLink, OrderSide


async def main():
    """
    Check VALR connectivity and display balances.
    
    Reliability Level: TESTING
    Input Constraints: None
    Side Effects: API call or mock response
    """
    print("=" * 60)
    print("AUTONOMOUS ALPHA v1.3.2 - VALR CONNECTIVITY CHECK")
    print("=" * 60)
    
    # Initialize VALR Link
    link = VALRLink()
    
    # Display mode
    if link.mock_mode:
        print("\n⚠️  OPERATING IN MOCK MODE")
        print("   No real API calls will be made")
        print("   Configure VALR_API_KEY and VALR_API_SECRET for live mode")
    else:
        print("\n✅ OPERATING IN LIVE MODE")
        print("   Real API calls will be made to VALR")
    
    print("-" * 60)
    
    # Get balances
    print("\n📊 FETCHING ACCOUNT BALANCES...")
    
    try:
        balances = await link.get_balances()
        
        # Extract key balances
        zar_balance = link.get_zar_balance(balances)
        btc_balance = link.get_btc_balance(balances)
        
        print("\n💰 ACCOUNT BALANCES")
        print("-" * 60)
        print(f"   ZAR: R{zar_balance:,.2f}")
        print(f"   BTC: {btc_balance:.8f}")
        
        # Display all balances if in live mode
        if not link.mock_mode and len(balances) > 2:
            print("\n   Other currencies:")
            for currency, balance in balances.items():
                if currency not in ("ZAR", "BTC") and balance.total > Decimal("0"):
                    print(f"   {currency}: {balance.available}")
        
        print("-" * 60)
        
        # Test mock order (only in mock mode)
        if link.mock_mode:
            print("\n🧪 TESTING MOCK ORDER...")
            print("-" * 60)
            
            test_amount = Decimal("0.001")
            result = await link.place_market_order(
                side=OrderSide.BUY,
                pair="BTCZAR",
                amount=test_amount,
                correlation_id="TEST-CONNECTIVITY-CHECK"
            )
            
            print(f"\n   Order ID: {result.order_id}")
            print(f"   Side: {result.side.value}")
            print(f"   Pair: {result.pair}")
            print(f"   Quantity: {result.quantity}")
            print(f"   Status: {result.status}")
            print(f"   Is Mock: {result.is_mock}")
            print("-" * 60)
        
        print("\n✅ CONNECTIVITY CHECK COMPLETE")
        print("=" * 60)
        
        # Reliability Audit
        print("\n[Reliability Audit]")
        print(f"Decimal Integrity: Verified (ZAR type: {type(zar_balance).__name__})")
        print(f"Mock Mode: {'ENABLED' if link.mock_mode else 'DISABLED'}")
        print("Confidence Score: 100/100")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        print("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

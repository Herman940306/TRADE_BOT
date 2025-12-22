"""
============================================================================
Project Autonomous Alpha v1.3.2
Emergency Kill Switch - Instant Trading Halt
============================================================================

Reliability Level: SOVEREIGN TIER (Mission-Critical)
Input Constraints: Database connection required
Side Effects: Updates system_settings.system_active flag

PURPOSE
-------
Emergency control to instantly halt all trading operations.
When activated, the Dispatcher will refuse to execute any trades.

USAGE
-----
    # Activate Kill Switch (HALT all trading)
    python scripts/kill_switch.py --activate --reason "Market volatility"
    
    # Deactivate Kill Switch (RESUME trading)
    python scripts/kill_switch.py --deactivate
    
    # Check current status
    python scripts/kill_switch.py --status

============================================================================
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime, timezone

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from sqlalchemy import text

# Load environment
load_dotenv()

from app.database.session import SessionLocal


def get_status() -> dict:
    """
    Get current Kill Switch status.
    
    Reliability Level: SOVEREIGN TIER
    Input Constraints: None
    Side Effects: Database SELECT
    
    Returns:
        Dictionary with current status
    """
    db = SessionLocal()
    try:
        result = db.execute(
            text("""
                SELECT 
                    system_active,
                    kill_switch_reason,
                    kill_switch_triggered_at,
                    kill_switch_triggered_by,
                    min_trade_zar,
                    max_slippage_percent,
                    taker_fee_percent,
                    updated_at
                FROM system_settings
                WHERE id = 1
            """)
        )
        
        row = result.fetchone()
        
        if not row:
            return {
                "exists": False,
                "system_active": None,
                "reason": None
            }
        
        return {
            "exists": True,
            "system_active": row.system_active,
            "reason": row.kill_switch_reason,
            "triggered_at": row.kill_switch_triggered_at,
            "triggered_by": row.kill_switch_triggered_by,
            "min_trade_zar": row.min_trade_zar,
            "max_slippage_percent": row.max_slippage_percent,
            "taker_fee_percent": row.taker_fee_percent,
            "updated_at": row.updated_at
        }
    finally:
        db.close()


def activate_kill_switch(reason: str, triggered_by: str = "kill_switch.py") -> bool:
    """
    Activate the Emergency Kill Switch.
    
    Reliability Level: SOVEREIGN TIER
    Input Constraints: Reason required
    Side Effects: Updates system_settings
    
    Args:
        reason: Reason for activating kill switch
        triggered_by: Who/what triggered the kill switch
        
    Returns:
        True if successful
    """
    db = SessionLocal()
    try:
        db.execute(
            text("""
                UPDATE system_settings
                SET 
                    system_active = FALSE,
                    kill_switch_reason = :reason,
                    kill_switch_triggered_at = :triggered_at,
                    kill_switch_triggered_by = :triggered_by
                WHERE id = 1
            """),
            {
                "reason": reason,
                "triggered_at": datetime.now(timezone.utc),
                "triggered_by": triggered_by
            }
        )
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        print(f"❌ ERROR: {e}")
        return False
    finally:
        db.close()


def deactivate_kill_switch(triggered_by: str = "kill_switch.py") -> bool:
    """
    Deactivate the Emergency Kill Switch (resume trading).
    
    Reliability Level: SOVEREIGN TIER
    Input Constraints: None
    Side Effects: Updates system_settings
    
    Args:
        triggered_by: Who/what deactivated the kill switch
        
    Returns:
        True if successful
    """
    db = SessionLocal()
    try:
        db.execute(
            text("""
                UPDATE system_settings
                SET 
                    system_active = TRUE,
                    kill_switch_reason = NULL,
                    kill_switch_triggered_at = NULL,
                    kill_switch_triggered_by = :triggered_by
                WHERE id = 1
            """),
            {
                "triggered_by": triggered_by
            }
        )
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        print(f"❌ ERROR: {e}")
        return False
    finally:
        db.close()


def print_status(status: dict) -> None:
    """Print formatted status."""
    print("=" * 60)
    print("AUTONOMOUS ALPHA v1.3.2 - KILL SWITCH STATUS")
    print("=" * 60)
    
    if not status.get("exists"):
        print("\n⚠️  System settings not found in database")
        print("   Run migration 009_system_settings_table.sql first")
        return
    
    if status["system_active"]:
        print("\n✅ SYSTEM STATUS: ACTIVE")
        print("   Trading is ENABLED")
    else:
        print("\n🛑 SYSTEM STATUS: HALTED")
        print("   Trading is DISABLED")
        print(f"\n   Reason: {status['reason'] or 'No reason provided'}")
        if status["triggered_at"]:
            print(f"   Triggered at: {status['triggered_at']}")
        if status["triggered_by"]:
            print(f"   Triggered by: {status['triggered_by']}")
    
    print("\n" + "-" * 60)
    print("MARKET HARDENING SETTINGS")
    print("-" * 60)
    print(f"   Min Trade ZAR: R{status['min_trade_zar']}")
    print(f"   Max Slippage: {float(status['max_slippage_percent']) * 100:.2f}%")
    print(f"   Taker Fee: {float(status['taker_fee_percent']) * 100:.2f}%")
    print(f"\n   Last Updated: {status['updated_at']}")
    print("=" * 60)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Emergency Kill Switch for Autonomous Alpha Trading Bot"
    )
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--activate",
        action="store_true",
        help="Activate kill switch (HALT all trading)"
    )
    group.add_argument(
        "--deactivate",
        action="store_true",
        help="Deactivate kill switch (RESUME trading)"
    )
    group.add_argument(
        "--status",
        action="store_true",
        help="Check current kill switch status"
    )
    
    parser.add_argument(
        "--reason",
        type=str,
        default="Manual activation via kill_switch.py",
        help="Reason for activating kill switch"
    )
    
    args = parser.parse_args()
    
    if args.status:
        status = get_status()
        print_status(status)
        
    elif args.activate:
        print("=" * 60)
        print("🛑 ACTIVATING EMERGENCY KILL SWITCH")
        print("=" * 60)
        print(f"\n   Reason: {args.reason}")
        
        confirm = input("\n   Type 'CONFIRM' to activate: ")
        
        if confirm != "CONFIRM":
            print("\n   ❌ Activation cancelled")
            sys.exit(1)
        
        if activate_kill_switch(args.reason):
            print("\n   ✅ KILL SWITCH ACTIVATED")
            print("   All trading has been HALTED")
            print("=" * 60)
        else:
            print("\n   ❌ Failed to activate kill switch")
            sys.exit(1)
            
    elif args.deactivate:
        print("=" * 60)
        print("✅ DEACTIVATING KILL SWITCH")
        print("=" * 60)
        
        # Show current status first
        status = get_status()
        if status.get("exists") and not status["system_active"]:
            print(f"\n   Current reason: {status['reason']}")
        
        confirm = input("\n   Type 'RESUME' to deactivate and resume trading: ")
        
        if confirm != "RESUME":
            print("\n   ❌ Deactivation cancelled")
            sys.exit(1)
        
        if deactivate_kill_switch():
            print("\n   ✅ KILL SWITCH DEACTIVATED")
            print("   Trading has been RESUMED")
            print("=" * 60)
        else:
            print("\n   ❌ Failed to deactivate kill switch")
            sys.exit(1)


if __name__ == "__main__":
    main()

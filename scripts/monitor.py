"""
============================================================================
Project Autonomous Alpha v1.3.2
Heartbeat Monitor - Sovereign Dashboard
============================================================================

Reliability Level: SOVEREIGN TIER (Mission-Critical)
Input Constraints: Database and VALR connectivity
Side Effects: Read-only monitoring

PURPOSE
-------
Real-time monitoring dashboard for the Autonomous Alpha trading bot.
Displays system status, balances, recent activity, and performance metrics.

USAGE
-----
    python scripts/monitor.py

Press Ctrl+C to exit.

============================================================================
"""

import sys
import os
import asyncio
import time
from pathlib import Path
from decimal import Decimal
from datetime import datetime, timezone

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from sqlalchemy import text

# Load environment
load_dotenv()

from app.database.session import SessionLocal
from app.logic.valr_link import VALRLink


# =============================================================================
# CONSTANTS
# =============================================================================

REFRESH_INTERVAL = 10  # seconds
MOCK_BTC_PRICE = Decimal("1850000.00")  # Mock price for P&L calculation


def clear_screen():
    """Clear terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')


def get_system_status() -> dict:
    """
    Fetch system status from database.
    
    Reliability Level: SOVEREIGN TIER
    Input Constraints: None
    Side Effects: Database SELECT
    """
    db = SessionLocal()
    try:
        result = db.execute(
            text("""
                SELECT 
                    system_active,
                    kill_switch_reason,
                    kill_switch_triggered_at,
                    min_trade_zar,
                    max_slippage_percent,
                    taker_fee_percent
                FROM system_settings
                WHERE id = 1
            """)
        )
        row = result.fetchone()
        
        if not row:
            return {"active": None, "reason": "Settings not found"}
        
        return {
            "active": row.system_active,
            "reason": row.kill_switch_reason,
            "triggered_at": row.kill_switch_triggered_at,
            "min_trade_zar": row.min_trade_zar,
            "max_slippage": row.max_slippage_percent,
            "taker_fee": row.taker_fee_percent
        }
    finally:
        db.close()


def get_recent_orders(limit: int = 5) -> list:
    """
    Fetch recent trading orders.
    
    Reliability Level: SOVEREIGN TIER
    Input Constraints: limit > 0
    Side Effects: Database SELECT
    """
    db = SessionLocal()
    try:
        result = db.execute(
            text("""
                SELECT 
                    order_id,
                    side,
                    quantity,
                    zar_value,
                    status,
                    is_mock,
                    created_at
                FROM trading_orders
                ORDER BY id DESC
                LIMIT :limit
            """),
            {"limit": limit}
        )
        
        orders = []
        for row in result.fetchall():
            orders.append({
                "order_id": row.order_id[:16] + "..." if len(row.order_id) > 16 else row.order_id,
                "side": row.side,
                "quantity": Decimal(str(row.quantity)),
                "zar_value": Decimal(str(row.zar_value)) if row.zar_value else Decimal("0"),
                "status": row.status,
                "is_mock": row.is_mock,
                "created_at": row.created_at
            })
        
        return orders
    finally:
        db.close()


def get_performance_stats() -> dict:
    """
    Calculate performance statistics.
    
    Reliability Level: SOVEREIGN TIER
    Input Constraints: None
    Side Effects: Database SELECT
    """
    db = SessionLocal()
    try:
        # Get total ZAR spent on BUY orders
        result = db.execute(
            text("""
                SELECT 
                    COALESCE(SUM(zar_value), 0) as total_spent,
                    COALESCE(SUM(quantity), 0) as total_btc_bought,
                    COUNT(*) as buy_count
                FROM trading_orders
                WHERE side = 'BUY' AND status IN ('FILLED', 'MOCK_FILLED')
            """)
        )
        buy_stats = result.fetchone()
        
        # Get total ZAR received from SELL orders
        result = db.execute(
            text("""
                SELECT 
                    COALESCE(SUM(zar_value), 0) as total_received,
                    COALESCE(SUM(quantity), 0) as total_btc_sold,
                    COUNT(*) as sell_count
                FROM trading_orders
                WHERE side = 'SELL' AND status IN ('FILLED', 'MOCK_FILLED')
            """)
        )
        sell_stats = result.fetchone()
        
        # Get signal counts
        result = db.execute(
            text("""
                SELECT COUNT(*) as total_signals
                FROM signals
            """)
        )
        signal_count = result.fetchone().total_signals
        
        # Get AI debate stats
        result = db.execute(
            text("""
                SELECT 
                    COUNT(*) as total_debates,
                    SUM(CASE WHEN final_verdict = TRUE THEN 1 ELSE 0 END) as approved,
                    SUM(CASE WHEN final_verdict = FALSE THEN 1 ELSE 0 END) as rejected
                FROM ai_debates
            """)
        )
        debate_stats = result.fetchone()
        
        return {
            "total_spent": Decimal(str(buy_stats.total_spent)),
            "total_btc_bought": Decimal(str(buy_stats.total_btc_bought)),
            "buy_count": buy_stats.buy_count,
            "total_received": Decimal(str(sell_stats.total_received)),
            "total_btc_sold": Decimal(str(sell_stats.total_btc_sold)),
            "sell_count": sell_stats.sell_count,
            "signal_count": signal_count,
            "debate_count": debate_stats.total_debates,
            "approved_count": debate_stats.approved or 0,
            "rejected_count": debate_stats.rejected or 0
        }
    finally:
        db.close()


async def get_balances() -> dict:
    """
    Fetch current balances from VALR.
    
    Reliability Level: SOVEREIGN TIER
    Input Constraints: None
    Side Effects: API call or mock response
    """
    valr = VALRLink()
    balances = await valr.get_balances()
    
    return {
        "zar": valr.get_zar_balance(balances),
        "btc": valr.get_btc_balance(balances),
        "mock_mode": valr.mock_mode
    }


def render_dashboard(
    system_status: dict,
    balances: dict,
    orders: list,
    stats: dict,
    btc_price: Decimal
) -> None:
    """
    Render the Sovereign Dashboard.
    
    Reliability Level: STANDARD
    Input Constraints: All data dicts required
    Side Effects: Console output
    """
    clear_screen()
    
    now = datetime.now(timezone.utc)
    
    # Header
    print("╔" + "═" * 68 + "╗")
    print("║" + " AUTONOMOUS ALPHA v1.3.2 - SOVEREIGN DASHBOARD ".center(68) + "║")
    print("║" + f" {now.strftime('%Y-%m-%d %H:%M:%S UTC')} ".center(68) + "║")
    print("╠" + "═" * 68 + "╣")
    
    # System Status
    if system_status.get("active") is True:
        status_icon = "✅"
        status_text = "ACTIVE"
        status_color = ""
    elif system_status.get("active") is False:
        status_icon = "🛑"
        status_text = "KILLED"
        status_color = ""
    else:
        status_icon = "⚠️"
        status_text = "UNKNOWN"
        status_color = ""
    
    print("║" + " SYSTEM STATUS ".center(68, "─") + "║")
    print(f"║  {status_icon} Status: {status_text:<20}                                   ║")
    
    if not system_status.get("active") and system_status.get("reason"):
        reason = system_status["reason"][:50]
        print(f"║     Reason: {reason:<54} ║")
    
    mode = "MOCK" if balances.get("mock_mode") else "LIVE"
    print(f"║  📡 Mode: {mode:<20}                                       ║")
    
    # Market Hardening Settings
    min_trade = system_status.get("min_trade_zar", 50)
    max_slip = float(system_status.get("max_slippage", 0.01)) * 100
    taker_fee = float(system_status.get("taker_fee", 0.001)) * 100
    print(f"║  ⚙️  Min Trade: R{min_trade:<8} | Slippage: {max_slip:.1f}% | Fee: {taker_fee:.1f}%          ║")
    
    print("╠" + "═" * 68 + "╣")
    
    # Balances
    print("║" + " CURRENT BALANCES ".center(68, "─") + "║")
    zar = balances.get("zar", Decimal("0"))
    btc = balances.get("btc", Decimal("0"))
    btc_value = btc * btc_price
    total_value = zar + btc_value
    
    print(f"║  💰 ZAR:  R{zar:>15,.2f}                                      ║")
    print(f"║  ₿  BTC:  {btc:>15.8f}  (≈ R{btc_value:>12,.2f})              ║")
    print(f"║  📊 Total: R{total_value:>14,.2f}                                     ║")
    
    print("╠" + "═" * 68 + "╣")
    
    # Performance
    print("║" + " PERFORMANCE ".center(68, "─") + "║")
    
    total_spent = stats.get("total_spent", Decimal("0"))
    total_received = stats.get("total_received", Decimal("0"))
    btc_held = stats.get("total_btc_bought", Decimal("0")) - stats.get("total_btc_sold", Decimal("0"))
    btc_held_value = btc_held * btc_price
    
    # Calculate P&L
    net_cash_flow = total_received - total_spent
    unrealized_pnl = btc_held_value
    total_pnl = net_cash_flow + unrealized_pnl
    
    pnl_icon = "📈" if total_pnl >= 0 else "📉"
    pnl_sign = "+" if total_pnl >= 0 else ""
    
    print(f"║  💸 Total Spent:    R{total_spent:>12,.2f}                            ║")
    print(f"║  💵 Total Received: R{total_received:>12,.2f}                            ║")
    print(f"║  ₿  BTC Held:       {btc_held:>12.8f}  (≈ R{btc_held_value:>10,.2f})      ║")
    print(f"║  {pnl_icon} Mock P&L:        {pnl_sign}R{total_pnl:>11,.2f}                            ║")
    
    print("╠" + "═" * 68 + "╣")
    
    # Statistics
    print("║" + " STATISTICS ".center(68, "─") + "║")
    
    signal_count = stats.get("signal_count", 0)
    debate_count = stats.get("debate_count", 0)
    approved = stats.get("approved_count", 0)
    rejected = stats.get("rejected_count", 0)
    buy_count = stats.get("buy_count", 0)
    sell_count = stats.get("sell_count", 0)
    
    approval_rate = (approved / debate_count * 100) if debate_count > 0 else 0
    
    print(f"║  📨 Signals: {signal_count:<5} | Debates: {debate_count:<5} | Approval: {approval_rate:>5.1f}%       ║")
    print(f"║  🟢 Approved: {approved:<4} | 🔴 Rejected: {rejected:<4} | Orders: {buy_count + sell_count:<4}         ║")
    
    print("╠" + "═" * 68 + "╣")
    
    # Recent Orders
    print("║" + " RECENT ORDERS ".center(68, "─") + "║")
    
    if not orders:
        print("║  No orders yet                                                     ║")
    else:
        print("║  Order ID          Side   Quantity      ZAR Value   Status        ║")
        print("║  " + "─" * 64 + "  ║")
        
        for order in orders[:5]:
            order_id = order["order_id"][:16].ljust(16)
            side = order["side"].ljust(4)
            qty = f"{order['quantity']:.6f}".rjust(12)
            zar_val = f"R{order['zar_value']:,.2f}".rjust(11)
            status = order["status"][:12].ljust(12)
            mock = "M" if order["is_mock"] else "L"
            
            print(f"║  {order_id} {side}  {qty}  {zar_val}  {status} {mock} ║")
    
    print("╠" + "═" * 68 + "╣")
    
    # Footer
    print("║" + f" Refreshing every {REFRESH_INTERVAL}s | Press Ctrl+C to exit ".center(68) + "║")
    print("╚" + "═" * 68 + "╝")


async def main():
    """
    Main monitoring loop.
    
    Reliability Level: SOVEREIGN TIER
    Input Constraints: None
    Side Effects: Continuous console output
    """
    print("Starting Sovereign Dashboard...")
    print("Press Ctrl+C to exit.\n")
    
    try:
        while True:
            try:
                # Fetch all data
                system_status = get_system_status()
                balances = await get_balances()
                orders = get_recent_orders(5)
                stats = get_performance_stats()
                
                # Render dashboard
                render_dashboard(
                    system_status=system_status,
                    balances=balances,
                    orders=orders,
                    stats=stats,
                    btc_price=MOCK_BTC_PRICE
                )
                
            except Exception as e:
                print(f"\n⚠️  Error fetching data: {e}")
            
            # Wait for next refresh
            await asyncio.sleep(REFRESH_INTERVAL)
            
    except KeyboardInterrupt:
        print("\n\n👋 Dashboard stopped. Goodbye!")


if __name__ == "__main__":
    asyncio.run(main())

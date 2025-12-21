"""
============================================================================
Project Autonomous Alpha v1.3.2
Full Pipeline Test - Signal → Risk → AI Council
============================================================================

Reliability Level: SOVEREIGN TIER (Mission-Critical)
Input Constraints: Requires running FastAPI server with AI Council integration
Side Effects: Sends HTTP requests, inserts records into database

PURPOSE
-------
Verify the complete unified pipeline:
1. HMAC Authentication
2. Risk Assessment (Sovereign Brain)
3. AI Council Debate (Cold Path AI)
4. Final Trade Decision

============================================================================
"""

import os
import sys
import json
import hmac
import hashlib
import uuid
from datetime import datetime

import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


# ============================================================================
# CONFIGURATION
# ============================================================================

BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8080")
WEBHOOK_ENDPOINT = f"{BASE_URL}/webhook/tradingview"
SECRET_KEY = os.getenv("SOVEREIGN_SECRET")


def compute_hmac_signature(payload: bytes, secret_key: str) -> str:
    """Compute HMAC-SHA256 signature."""
    signature = hmac.new(
        key=secret_key.encode("utf-8"),
        msg=payload,
        digestmod=hashlib.sha256
    )
    return signature.hexdigest()


def send_signal(payload: dict) -> requests.Response:
    """Send authenticated signal to webhook."""
    payload_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    signature = compute_hmac_signature(payload_bytes, SECRET_KEY)
    
    headers = {
        "Content-Type": "application/json",
        "X-TradingView-Signature": signature
    }
    
    return requests.post(
        WEBHOOK_ENDPOINT,
        data=payload_bytes,
        headers=headers,
        timeout=30  # Longer timeout for AI processing
    )


def main():
    """Run full pipeline test."""
    print("=" * 70)
    print("AUTONOMOUS ALPHA v1.3.2 - FULL PIPELINE TEST")
    print("Signal → Risk Assessment → AI Council → Trade Decision")
    print("=" * 70)
    print(f"Timestamp: {datetime.utcnow().isoformat()}Z")
    print(f"Target: {WEBHOOK_ENDPOINT}")
    print("=" * 70)
    
    if not SECRET_KEY:
        print("\n❌ ERROR: SOVEREIGN_SECRET not configured")
        sys.exit(1)
    
    # Generate unique signal
    signal_id = f"PIPELINE-TEST-{uuid.uuid4().hex[:8].upper()}"
    
    payload = {
        "signal_id": signal_id,
        "symbol": "BTCZAR",
        "side": "BUY",
        "price": "1850000.00",  # ~R1.85M per BTC
        "quantity": "0.01"
    }
    
    print(f"\n📤 SENDING SIGNAL")
    print(f"   Signal ID: {signal_id}")
    print(f"   Symbol: {payload['symbol']}")
    print(f"   Side: {payload['side']}")
    print(f"   Price: R{payload['price']}")
    print("-" * 70)
    
    try:
        response = send_signal(payload)
        data = response.json()
        
        print(f"\n📥 RESPONSE (HTTP {response.status_code})")
        print("-" * 70)
        
        # Basic info
        print(f"   Status: {data.get('status', 'N/A')}")
        print(f"   Correlation ID: {data.get('correlation_id', 'N/A')}")
        print(f"   Processing Time: {data.get('processing_ms', 'N/A')}ms")
        print(f"   HMAC Verified: {data.get('hmac_verified', 'N/A')}")
        
        # Risk Assessment
        print("\n🧠 RISK ASSESSMENT (Sovereign Brain)")
        print("-" * 70)
        risk = data.get('risk_assessment', {})
        print(f"   Status: {risk.get('status', 'N/A')}")
        print(f"   Equity: R{risk.get('equity', 'N/A')}")
        print(f"   Risk Amount: R{risk.get('risk_amount_zar', 'N/A')}")
        print(f"   Calculated Qty: {risk.get('calculated_quantity', 'N/A')}")
        if risk.get('rejection_reason'):
            print(f"   Rejection: {risk.get('rejection_reason')}")
        
        # AI Consensus
        print("\n🤖 AI COUNCIL (Cold Path AI)")
        print("-" * 70)
        ai = data.get('ai_consensus', {})
        print(f"   Status: {ai.get('status', 'N/A')}")
        print(f"   Consensus Score: {ai.get('consensus_score', 'N/A')}/100")
        print(f"   Final Verdict: {ai.get('final_verdict', 'N/A')}")
        if ai.get('rejection_reason'):
            print(f"   Rejection: {ai.get('rejection_reason')}")
        
        # Trade Decision
        print("\n💰 TRADE DECISION")
        print("-" * 70)
        trade = data.get('trade_decision', {})
        decision_status = trade.get('status', 'N/A')
        decision_action = trade.get('action', 'N/A')
        
        if decision_status == "APPROVED":
            print(f"   ✅ Status: {decision_status}")
            print(f"   ✅ Action: {decision_action}")
        else:
            print(f"   🛑 Status: {decision_status}")
            print(f"   🛑 Action: {decision_action}")
        
        # Summary
        print("\n" + "=" * 70)
        print("PIPELINE SUMMARY")
        print("=" * 70)
        
        hmac_ok = data.get('hmac_verified', False)
        risk_ok = risk.get('status') == 'APPROVED'
        ai_ok = ai.get('status') == 'APPROVED'
        trade_ok = trade.get('status') == 'APPROVED'
        
        print(f"   1. HMAC Authentication: {'✅ PASSED' if hmac_ok else '❌ FAILED'}")
        print(f"   2. Risk Assessment:     {'✅ APPROVED' if risk_ok else '🛑 REJECTED'}")
        print(f"   3. AI Council:          {'✅ APPROVED' if ai_ok else '🛑 REJECTED'}")
        print(f"   4. Trade Decision:      {'✅ PROCEED' if trade_ok else '🛑 HALT'}")
        
        print("\n" + "=" * 70)
        
        if response.status_code == 200:
            print("✅ FULL PIPELINE TEST COMPLETE")
            print("   All stages executed successfully")
            print("   Check ai_debates table for reasoning audit")
        else:
            print(f"⚠️  Unexpected status code: {response.status_code}")
        
        print("=" * 70)
        
        # Print full JSON for debugging
        print("\n📋 FULL RESPONSE JSON:")
        print(json.dumps(data, indent=2))
        
    except requests.exceptions.ConnectionError:
        print("\n❌ ERROR: Cannot connect to server")
        print(f"   Ensure FastAPI is running on {BASE_URL}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

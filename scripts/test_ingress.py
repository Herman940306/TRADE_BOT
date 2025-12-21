"""
============================================================================
Project Autonomous Alpha v1.3.2
Ingress Layer Test Runner - Webhook Validation Suite
============================================================================

Reliability Level: DEVELOPMENT/TESTING
Input Constraints: Requires running FastAPI server and .env configuration
Side Effects: Sends HTTP requests, may insert records into database

TESTS INCLUDED:
- Test A (The Poison): Float value injection → AUD-001 rejection
- Test B (The Pure): Valid Decimal string → Successful insertion

EXECUTION:
    python scripts/test_ingress.py

REQUIREMENTS:
    - FastAPI server running on http://127.0.0.1:8080
    - SOVEREIGN_SECRET configured in .env
    - PostgreSQL database accessible

============================================================================
"""

import os
import sys
import json
import hmac
import hashlib
import uuid
from datetime import datetime
from typing import Optional

import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


# ============================================================================
# CONFIGURATION
# ============================================================================

# API endpoint
BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8080")
WEBHOOK_ENDPOINT = f"{BASE_URL}/webhook/tradingview"

# Secret key for HMAC signing
SECRET_KEY = os.getenv("SOVEREIGN_SECRET")


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def compute_hmac_signature(payload: bytes, secret_key: str) -> str:
    """
    Compute HMAC-SHA256 signature for a payload.
    
    Reliability Level: TESTING
    Input Constraints: Raw bytes payload, secret key string
    Side Effects: None
    
    Returns:
        str: Hexadecimal HMAC-SHA256 signature
    """
    signature = hmac.new(
        key=secret_key.encode("utf-8"),
        msg=payload,
        digestmod=hashlib.sha256
    )
    return signature.hexdigest()


def send_webhook(
    payload: dict,
    include_signature: bool = True,
    custom_signature: Optional[str] = None
) -> requests.Response:
    """
    Send a webhook request to the ingress endpoint.
    
    Reliability Level: TESTING
    Input Constraints: Dictionary payload
    Side Effects: HTTP POST request
    
    Returns:
        requests.Response: HTTP response object
    """
    # Serialize payload to JSON bytes
    payload_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    
    # Build headers
    headers = {
        "Content-Type": "application/json"
    }
    
    if include_signature:
        if custom_signature:
            signature = custom_signature
        else:
            signature = compute_hmac_signature(payload_bytes, SECRET_KEY)
        headers["X-TradingView-Signature"] = signature
    
    # Send request
    response = requests.post(
        WEBHOOK_ENDPOINT,
        data=payload_bytes,
        headers=headers,
        timeout=10
    )
    
    return response


def print_result(test_name: str, passed: bool, details: str = ""):
    """Print formatted test result."""
    status = "✅ PASSED" if passed else "❌ FAILED"
    print(f"\n{'='*60}")
    print(f"TEST: {test_name}")
    print(f"STATUS: {status}")
    if details:
        print(f"DETAILS: {details}")
    print(f"{'='*60}")


def print_response(response: requests.Response):
    """Print formatted HTTP response."""
    print(f"\nHTTP Status: {response.status_code}")
    print(f"Response Body:")
    try:
        print(json.dumps(response.json(), indent=2))
    except Exception:
        print(response.text)


# ============================================================================
# TEST CASES
# ============================================================================

def test_a_the_poison():
    """
    Test A: The Poison - Float Value Injection
    
    Goal: Trigger AUD-001 validation error by sending a float value
    for the price field.
    
    Expected Result:
        - HTTP 422 Unprocessable Entity
        - Error code: AUD-001
        - Message referencing float type detection
    """
    print("\n" + "="*60)
    print("TEST A: THE POISON - Float Value Injection")
    print("="*60)
    print("\nObjective: Trigger AUD-001 by sending float price value")
    print("Payload: price = 100.0000000000001 (float with precision loss)")
    
    # Generate unique signal_id
    signal_id = f"TEST-POISON-{uuid.uuid4().hex[:8].upper()}"
    
    # Payload with FLOAT value (THE POISON)
    payload = {
        "signal_id": signal_id,
        "symbol": "BTCUSD",
        "side": "BUY",
        "price": 100.0000000000001,  # FLOAT - should trigger AUD-001
        "quantity": "1.0"
    }
    
    print(f"\nSending payload with float price: {payload['price']}")
    print(f"Signal ID: {signal_id}")
    
    try:
        response = send_webhook(payload)
        print_response(response)
        
        # Validate result
        if response.status_code == 422:
            response_data = response.json()
            error_code = response_data.get("error_code", "")
            
            if error_code == "AUD-001" or "AUD-001" in str(response_data):
                print_result(
                    "A: The Poison",
                    True,
                    "Float value correctly rejected with AUD-001"
                )
                return True
            else:
                print_result(
                    "A: The Poison",
                    False,
                    f"Got 422 but wrong error code: {error_code}"
                )
                return False
        else:
            print_result(
                "A: The Poison",
                False,
                f"Expected HTTP 422, got {response.status_code}"
            )
            return False
            
    except Exception as e:
        print_result("A: The Poison", False, f"Exception: {e}")
        return False


def test_b_the_pure():
    """
    Test B: The Pure - Valid Decimal String
    
    Goal: Confirm successful HMAC verification, parsing, and database
    insertion using properly formatted string decimal values.
    
    Expected Result:
        - HTTP 200 OK
        - Response contains correlation_id
        - Signal persisted to database
    """
    print("\n" + "="*60)
    print("TEST B: THE PURE - Valid Decimal String")
    print("="*60)
    print("\nObjective: Successful signal insertion with string decimals")
    print("Payload: price = '100.00' (string - correct format)")
    
    # Generate unique signal_id
    signal_id = f"TEST-PURE-{uuid.uuid4().hex[:8].upper()}"
    
    # Payload with STRING decimal values (THE PURE)
    payload = {
        "signal_id": signal_id,
        "symbol": "BTCUSD",
        "side": "BUY",
        "price": "45000.1234567890",  # STRING - correct format
        "quantity": "0.5000000000"     # STRING - correct format
    }
    
    print(f"\nSending payload with string price: {payload['price']}")
    print(f"Signal ID: {signal_id}")
    
    try:
        response = send_webhook(payload)
        print_response(response)
        
        # Validate result
        if response.status_code == 200:
            response_data = response.json()
            correlation_id = response_data.get("correlation_id")
            status = response_data.get("status")
            
            if status == "accepted" and correlation_id:
                print_result(
                    "B: The Pure",
                    True,
                    f"Signal accepted. correlation_id: {correlation_id}"
                )
                return True
            else:
                print_result(
                    "B: The Pure",
                    False,
                    f"Unexpected response format: {response_data}"
                )
                return False
        else:
            print_result(
                "B: The Pure",
                False,
                f"Expected HTTP 200, got {response.status_code}"
            )
            return False
            
    except Exception as e:
        print_result("B: The Pure", False, f"Exception: {e}")
        return False


def test_c_no_signature():
    """
    Test C: No Signature - SEC-001 Verification
    
    Goal: Confirm that requests without HMAC signature are rejected.
    
    Expected Result:
        - HTTP 401 Unauthorized
        - Error code: SEC-001
    """
    print("\n" + "="*60)
    print("TEST C: NO SIGNATURE - SEC-001 Verification")
    print("="*60)
    print("\nObjective: Verify SEC-001 rejection for missing signature")
    
    signal_id = f"TEST-NOSIG-{uuid.uuid4().hex[:8].upper()}"
    
    payload = {
        "signal_id": signal_id,
        "symbol": "ETHUSD",
        "side": "SELL",
        "price": "2500.00",
        "quantity": "10.0"
    }
    
    print(f"\nSending payload WITHOUT signature header")
    
    try:
        response = send_webhook(payload, include_signature=False)
        print_response(response)
        
        if response.status_code == 401:
            response_data = response.json()
            error_code = response_data.get("error_code", "")
            
            if error_code == "SEC-001":
                print_result(
                    "C: No Signature",
                    True,
                    "Missing signature correctly rejected with SEC-001"
                )
                return True
            else:
                print_result(
                    "C: No Signature",
                    False,
                    f"Got 401 but wrong error code: {error_code}"
                )
                return False
        else:
            print_result(
                "C: No Signature",
                False,
                f"Expected HTTP 401, got {response.status_code}"
            )
            return False
            
    except Exception as e:
        print_result("C: No Signature", False, f"Exception: {e}")
        return False


def test_d_invalid_signature():
    """
    Test D: Invalid Signature - SEC-003 Verification
    
    Goal: Confirm that requests with wrong HMAC signature are rejected.
    
    Expected Result:
        - HTTP 401 Unauthorized
        - Error code: SEC-003
    """
    print("\n" + "="*60)
    print("TEST D: INVALID SIGNATURE - SEC-003 Verification")
    print("="*60)
    print("\nObjective: Verify SEC-003 rejection for invalid signature")
    
    signal_id = f"TEST-BADSIG-{uuid.uuid4().hex[:8].upper()}"
    
    payload = {
        "signal_id": signal_id,
        "symbol": "XRPUSD",
        "side": "BUY",
        "price": "0.55",
        "quantity": "1000.0"
    }
    
    # Use a fake signature
    fake_signature = "a" * 64
    
    print(f"\nSending payload with INVALID signature")
    
    try:
        response = send_webhook(payload, custom_signature=fake_signature)
        print_response(response)
        
        if response.status_code == 401:
            response_data = response.json()
            error_code = response_data.get("error_code", "")
            
            if error_code == "SEC-003":
                print_result(
                    "D: Invalid Signature",
                    True,
                    "Invalid signature correctly rejected with SEC-003"
                )
                return True
            else:
                print_result(
                    "D: Invalid Signature",
                    False,
                    f"Got 401 but wrong error code: {error_code}"
                )
                return False
        else:
            print_result(
                "D: Invalid Signature",
                False,
                f"Expected HTTP 401, got {response.status_code}"
            )
            return False
            
    except Exception as e:
        print_result("D: Invalid Signature", False, f"Exception: {e}")
        return False


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """
    Execute all ingress validation tests.
    
    Reliability Level: TESTING
    Input Constraints: None
    Side Effects: HTTP requests, console output
    """
    print("="*60)
    print("AUTONOMOUS ALPHA v1.3.2 - INGRESS VALIDATION SUITE")
    print("="*60)
    print(f"Timestamp: {datetime.utcnow().isoformat()}Z")
    print(f"Target: {WEBHOOK_ENDPOINT}")
    print("="*60)
    
    # Verify configuration
    if not SECRET_KEY:
        print("\n❌ ERROR: SOVEREIGN_SECRET not found in .env")
        print("Please configure SOVEREIGN_SECRET before running tests.")
        sys.exit(1)
    
    if len(SECRET_KEY) < 32:
        print(f"\n❌ ERROR: SOVEREIGN_SECRET too short ({len(SECRET_KEY)} chars)")
        print("Minimum 32 characters required.")
        sys.exit(1)
    
    print(f"\n✅ SOVEREIGN_SECRET configured ({len(SECRET_KEY)} chars)")
    
    # Run tests
    results = []
    
    results.append(("A: The Poison (Float Injection)", test_a_the_poison()))
    results.append(("B: The Pure (Valid Decimal)", test_b_the_pure()))
    results.append(("C: No Signature (SEC-001)", test_c_no_signature()))
    results.append(("D: Invalid Signature (SEC-003)", test_d_invalid_signature()))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = 0
    failed = 0
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"  {test_name}: {status}")
        if result:
            passed += 1
        else:
            failed += 1
    
    print(f"\nTotal: {passed} passed, {failed} failed")
    print("="*60)
    
    if failed == 0:
        print("\n🎉 ALL TESTS PASSED - SOVEREIGN MANDATE VERIFIED")
        print("="*60)
        return 0
    else:
        print("\n⚠️  SOME TESTS FAILED - REVIEW REQUIRED")
        print("="*60)
        return 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
============================================================================
Project Autonomous Alpha v1.8.0
Exchange Connectivity Diagnostics - Read-Only
============================================================================

Reliability Level: SOVEREIGN TIER (Mission-Critical)
Purpose: Validate VALR exchange connectivity without placing orders

THIS SCRIPT IS READ-ONLY:
    - Fetches public ticker data (no auth required)
    - Fetches account balances (auth required)
    - Fetches open orders (auth required)
    - NEVER places, modifies, or cancels any order

SOVEREIGN MANDATE:
    Survival > Capital Preservation > Alpha
    This script validates that the exchange link is functional
    before any live trading phase is attempted.

Error Codes:
    - CONN-001: VALR API unreachable
    - CONN-002: Authentication failed
    - CONN-003: Balance retrieval failed
    - CONN-004: Clock drift detected

Usage:
    python3 scripts/check_exchange_connectivity.py
============================================================================
"""

from datetime import datetime, timezone
from decimal import Decimal
import os
from pathlib import Path
import sys
import time

# Add project root to path
project_root = str(Path(__file__).resolve().parent.parent)
sys.path.insert(0, project_root)


def check_public_api() -> dict:
    """
    Check VALR public API connectivity (no auth required).

    Returns:
        dict with status, ticker data, and latency
    """
    from app.exchange.valr_client import APIError, RateLimitError, VALRClient

    result = {
        "check": "PUBLIC_API",
        "status": "FAIL",
        "details": {},
    }

    try:
        client = VALRClient(
            correlation_id="CONN-DIAG-PUBLIC",
            skip_auth=True,
        )

        start = time.monotonic()
        ticker = client.get_ticker("BTCZAR")
        latency_ms = int((time.monotonic() - start) * 1000)

        result["status"] = "PASS"
        result["details"] = {
            "pair": ticker.pair,
            "bid": str(ticker.bid),
            "ask": str(ticker.ask),
            "last_price": str(ticker.last_price),
            "spread_pct": str(ticker.spread_pct),
            "volume_24h": str(ticker.volume_24h),
            "latency_ms": latency_ms,
        }
        print(f"  [PASS] Public API reachable | latency={latency_ms}ms")
        print(f"         BTC/ZAR: bid={ticker.bid} ask={ticker.ask} spread={ticker.spread_pct}%")

    except APIError as e:
        result["details"]["error"] = str(e)
        print(f"  [FAIL] CONN-001: Public API unreachable | {e}")

    except RateLimitError as e:
        result["details"]["error"] = str(e)
        print(f"  [WARN] Rate limited | {e}")

    except Exception as e:
        result["details"]["error"] = str(e)
        print(f"  [FAIL] CONN-001: Unexpected error | {e}")

    return result


def check_server_time() -> dict:
    """
    Check VALR server time and detect clock drift.

    Returns:
        dict with status and drift information
    """
    import requests

    result = {
        "check": "CLOCK_DRIFT",
        "status": "FAIL",
        "details": {},
    }

    try:
        local_before = int(time.time() * 1000)
        response = requests.get(
            "https://api.valr.com/v1/public/time",
            timeout=10,
        )
        local_after = int(time.time() * 1000)

        if response.status_code != 200:
            result["details"]["error"] = f"HTTP {response.status_code}"
            print(f"  [FAIL] CONN-004: Server time endpoint returned {response.status_code}")
            return result

        data = response.json()
        server_time_ms = data.get("epochTime", 0)
        local_mid = (local_before + local_after) // 2
        drift_ms = abs(server_time_ms - local_mid)

        result["details"] = {
            "server_time_ms": server_time_ms,
            "local_time_ms": local_mid,
            "drift_ms": drift_ms,
            "latency_ms": local_after - local_before,
        }

        if drift_ms < 1000:
            result["status"] = "PASS"
            print(f"  [PASS] Clock drift: {drift_ms}ms (threshold: 1000ms)")
        elif drift_ms < 5000:
            result["status"] = "WARN"
            print(f"  [WARN] Clock drift: {drift_ms}ms — marginal (threshold: 1000ms)")
        else:
            print(f"  [FAIL] CONN-004: Clock drift: {drift_ms}ms — too large")

    except Exception as e:
        result["details"]["error"] = str(e)
        print(f"  [FAIL] CONN-004: Clock check failed | {e}")

    return result


def check_credentials() -> dict:
    """
    Check if VALR API credentials are configured.

    Returns:
        dict with status and credential presence (never logs secrets)
    """
    result = {
        "check": "CREDENTIALS",
        "status": "FAIL",
        "details": {},
    }

    api_key = os.getenv("VALR_API_KEY", "")
    api_secret = os.getenv("VALR_API_SECRET", "")

    has_key = bool(api_key) and api_key != "your_valr_api_key_here"
    has_secret = bool(api_secret) and api_secret != "your_valr_api_secret_here"

    result["details"] = {
        "VALR_API_KEY": "SET" if has_key else "MISSING",
        "VALR_API_SECRET": "SET" if has_secret else "MISSING",
    }

    if has_key and has_secret:
        result["status"] = "PASS"
        # Redact: show only first 4 and last 4 chars
        redacted = api_key[:4] + "..." + api_key[-4:] if len(api_key) > 8 else "****"
        print(f"  [PASS] Credentials configured | key={redacted}")
    else:
        missing = []
        if not has_key:
            missing.append("VALR_API_KEY")
        if not has_secret:
            missing.append("VALR_API_SECRET")
        print(f"  [FAIL] Missing credentials: {', '.join(missing)}")

    return result


def check_authenticated_read() -> dict:
    """
    Check authenticated read access (balances, open orders).

    Returns:
        dict with status and balance summary (never logs full amounts)
    """
    from app.exchange.valr_client import VALRClient, VALRClientError

    result = {
        "check": "AUTHENTICATED_READ",
        "status": "FAIL",
        "details": {},
    }

    try:
        client = VALRClient(correlation_id="CONN-DIAG-AUTH")

        # Fetch balances
        start = time.monotonic()
        balances = client.get_balances()
        latency_ms = int((time.monotonic() - start) * 1000)

        # Extract ZAR balance
        zar = balances.get("ZAR")
        zar_available = zar.available if zar else Decimal("0")
        zar_total = zar.total if zar else Decimal("0")

        # Fetch open orders
        open_orders = client.get_open_orders()

        result["status"] = "PASS"
        result["details"] = {
            "currencies_found": len(balances),
            "zar_available": str(zar_available),
            "zar_total": str(zar_total),
            "open_orders_count": len(open_orders),
            "latency_ms": latency_ms,
        }

        print(f"  [PASS] Authenticated read OK | latency={latency_ms}ms")
        print(f"         Currencies: {len(balances)} | ZAR available: R{zar_available:,.2f}")
        print(f"         Open orders: {len(open_orders)}")

    except VALRClientError as e:
        result["details"]["error"] = str(e)
        if "Authentication required" in str(e) or "VALR-SEC-001" in str(e):
            print("  [SKIP] No credentials — authenticated reads unavailable")
            result["status"] = "SKIP"
        else:
            print(f"  [FAIL] CONN-002: Authentication failed | {e}")

    except Exception as e:
        result["details"]["error"] = str(e)
        print(f"  [FAIL] CONN-003: Balance retrieval failed | {e}")

    return result


def check_mode_status() -> dict:
    """
    Check current trading mode configuration.

    Returns:
        dict with mode status
    """
    from app.exchange.mode_matrix import ModeGuard

    result = {
        "check": "MODE_STATUS",
        "status": "PASS",
        "details": {},
    }

    try:
        guard = ModeGuard(correlation_id="CONN-DIAG-MODE")
        status = guard.get_status()

        result["details"] = status
        mode = status["mode"]

        print(f"  [INFO] Trading Mode: {mode}")
        print(f"         Public data:  {status['capabilities']['exchange_public_data']}")
        print(f"         Auth reads:   {status['capabilities']['exchange_authenticated_reads']}")
        print(f"         Order place:  {status['capabilities']['exchange_order_placement']}")
        print(f"         Equity src:   {status['capabilities']['equity_source']}")

        if mode == "LIVE_EXECUTION":
            result["status"] = "WARN"
            print("  [WARN] LIVE_EXECUTION mode is active — real orders enabled")

    except Exception as e:
        result["details"]["error"] = str(e)
        result["status"] = "FAIL"
        print(f"  [FAIL] MODE-004: Mode resolution failed | {e}")

    return result


def main() -> int:
    """
    Run all connectivity diagnostics.

    Returns:
        0 if all critical checks pass, 1 otherwise
    """
    print("=" * 72)
    print("VALR Exchange Connectivity Diagnostics")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 72)

    results = []

    # 1. Mode Status
    print("\n[1/5] Trading Mode Configuration")
    results.append(check_mode_status())

    # 2. Public API
    print("\n[2/5] Public API (no auth required)")
    results.append(check_public_api())

    # 3. Server Time / Clock Drift
    print("\n[3/5] Server Time / Clock Drift")
    results.append(check_server_time())

    # 4. Credentials
    print("\n[4/5] API Credentials")
    results.append(check_credentials())

    # 5. Authenticated Read
    print("\n[5/5] Authenticated Read (balances + orders)")
    results.append(check_authenticated_read())

    # Summary
    print("\n" + "=" * 72)
    print("SUMMARY")
    print("=" * 72)

    pass_count = sum(1 for r in results if r["status"] == "PASS")
    fail_count = sum(1 for r in results if r["status"] == "FAIL")
    skip_count = sum(1 for r in results if r["status"] == "SKIP")
    warn_count = sum(1 for r in results if r["status"] == "WARN")

    for r in results:
        icon = {"PASS": "OK", "FAIL": "XX", "SKIP": "--", "WARN": "!!"}
        print(f"  [{icon.get(r['status'], '??')}] {r['check']}: {r['status']}")

    print(f"\nResults: {pass_count} PASS, {fail_count} FAIL, {warn_count} WARN, {skip_count} SKIP")

    if fail_count == 0:
        print("\nVERDICT: EXCHANGE CONNECTIVITY OK")
        return 0
    print("\nVERDICT: EXCHANGE CONNECTIVITY ISSUES DETECTED")
    return 1


if __name__ == "__main__":
    sys.exit(main())

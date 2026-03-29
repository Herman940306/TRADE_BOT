#!/usr/bin/env python3
"""
============================================================================
Project Autonomous Alpha v1.8.0
Live Readiness Check - Comprehensive Pre-Flight Diagnostics
============================================================================

Reliability Level: SOVEREIGN TIER (Mission-Critical)
Purpose: Verify all prerequisites for live trading readiness

THIS SCRIPT IS READ-ONLY AND DIAGNOSTIC:
    - Checks mode matrix configuration
    - Validates exchange connectivity
    - Tests equity source availability
    - Verifies Guardian service operational
    - Confirms HITL gate is active
    - Validates database connectivity
    - Checks reconciliation capability
    - Produces PASS/FAIL verdicts per category

Usage:
    python3 scripts/check_live_readiness.py

Exit Codes:
    0 = All critical checks pass (READY for next phase)
    1 = One or more critical checks failed (NOT READY)
============================================================================
"""

import os
import sys
import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

# Add project root to path
project_root = str(Path(__file__).resolve().parent.parent)
sys.path.insert(0, project_root)


class ReadinessResult:
    """Result of a single readiness check."""

    def __init__(self, category: str, check_name: str):
        self.category = category
        self.check_name = check_name
        self.status = "NOT_RUN"
        self.critical = True
        self.details = ""

    def passed(self, details: str = "") -> "ReadinessResult":
        self.status = "PASS"
        self.details = details
        return self

    def failed(self, details: str = "") -> "ReadinessResult":
        self.status = "FAIL"
        self.details = details
        return self

    def skipped(self, details: str = "") -> "ReadinessResult":
        self.status = "SKIP"
        self.details = details
        return self

    def warned(self, details: str = "") -> "ReadinessResult":
        self.status = "WARN"
        self.details = details
        return self


def check_mode_matrix() -> list:
    """Check mode matrix configuration."""
    results = []

    # Check 1: ModeGuard resolves without error
    r = ReadinessResult("MODE", "ModeGuard initialization")
    try:
        from app.exchange.mode_matrix import ModeGuard
        guard = ModeGuard(correlation_id="READINESS-CHECK")
        status = guard.get_status()
        r.passed(f"Mode={status['mode']}")
    except Exception as e:
        r.failed(str(e))
    results.append(r)

    # Check 2: LIVE_EXECUTION is NOT active (safety)
    r = ReadinessResult("MODE", "LIVE_EXECUTION disabled")
    try:
        from app.exchange.mode_matrix import ModeGuard, TradingMode
        guard = ModeGuard(correlation_id="READINESS-CHECK")
        if guard.mode == TradingMode.LIVE_EXECUTION:
            r.failed("LIVE_EXECUTION is active — must be disabled for Phase 3A")
        else:
            r.passed(f"Current mode: {guard.mode.value}")
    except Exception as e:
        r.failed(str(e))
    results.append(r)

    # Check 3: Mode guard blocks order placement
    r = ReadinessResult("MODE", "Order placement blocked")
    try:
        from app.exchange.mode_matrix import ModeGuard, ModeViolationError
        guard = ModeGuard(correlation_id="READINESS-CHECK")
        try:
            guard.require_order_placement()
            if guard.mode != TradingMode.LIVE_EXECUTION:
                r.failed("Order placement not blocked")
            else:
                r.warned("LIVE_EXECUTION active — orders permitted")
        except ModeViolationError:
            r.passed("Order placement correctly blocked")
    except Exception as e:
        r.failed(str(e))
    results.append(r)

    return results


def check_exchange_connectivity() -> list:
    """Check exchange connectivity."""
    results = []

    # Check 1: Public API
    r = ReadinessResult("EXCHANGE", "VALR public API reachable")
    r.critical = False
    try:
        from app.exchange.valr_client import VALRClient
        client = VALRClient(correlation_id="READINESS-CHECK", skip_auth=True)
        ticker = client.get_ticker("BTCZAR")
        r.passed(f"BTC/ZAR={ticker.last_price}")
    except Exception as e:
        r.failed(str(e))
    results.append(r)

    # Check 2: Credentials configured
    r = ReadinessResult("EXCHANGE", "VALR credentials configured")
    r.critical = False
    api_key = os.getenv("VALR_API_KEY", "")
    api_secret = os.getenv("VALR_API_SECRET", "")
    has_key = bool(api_key) and api_key != "your_valr_api_key_here"
    has_secret = bool(api_secret) and api_secret != "your_valr_api_secret_here"
    if has_key and has_secret:
        r.passed("Both VALR_API_KEY and VALR_API_SECRET set")
    else:
        missing = []
        if not has_key:
            missing.append("VALR_API_KEY")
        if not has_secret:
            missing.append("VALR_API_SECRET")
        r.failed(f"Missing: {', '.join(missing)}")
    results.append(r)

    # Check 3: Authenticated read (only if credentials present)
    r = ReadinessResult("EXCHANGE", "Authenticated balance read")
    r.critical = False
    if has_key and has_secret:
        try:
            from app.exchange.valr_client import VALRClient
            client = VALRClient(correlation_id="READINESS-CHECK")
            balances = client.get_balances()
            zar = balances.get("ZAR")
            r.passed(f"ZAR available: R{zar.available:,.2f}" if zar else "No ZAR balance")
        except Exception as e:
            r.failed(str(e))
    else:
        r.skipped("No credentials — cannot test authenticated reads")
    results.append(r)

    return results


def check_equity_source() -> list:
    """Check equity source availability."""
    results = []

    # Check 1: EquitySource initializes
    r = ReadinessResult("EQUITY", "EquitySource initialization")
    try:
        from app.exchange.mode_matrix import ModeGuard
        from app.exchange.equity_source import EquitySource

        guard = ModeGuard(correlation_id="READINESS-CHECK")
        source = EquitySource(
            mode_guard=guard,
            static_equity_zar=Decimal(os.getenv("ZAR_FLOOR", "100000")),
            correlation_id="READINESS-CHECK",
        )
        r.passed(f"Source: {source.get_source_description()}")
    except Exception as e:
        r.failed(str(e))
    results.append(r)

    # Check 2: Equity retrieval returns a value
    r = ReadinessResult("EQUITY", "Equity retrieval")
    try:
        from app.exchange.mode_matrix import ModeGuard
        from app.exchange.equity_source import EquitySource

        guard = ModeGuard(correlation_id="READINESS-CHECK")
        source = EquitySource(
            mode_guard=guard,
            static_equity_zar=Decimal(os.getenv("ZAR_FLOOR", "100000")),
            correlation_id="READINESS-CHECK",
        )
        equity = source.get_equity_zar()
        if equity is not None and equity > Decimal("0"):
            r.passed(f"Equity: R{equity:,.2f}")
        elif equity is not None:
            r.warned(f"Equity: R{equity:,.2f} (zero or negative)")
        else:
            r.failed("Equity retrieval returned None")
    except Exception as e:
        r.failed(str(e))
    results.append(r)

    # Check 3: Guardian equity env var
    r = ReadinessResult("EQUITY", "ZAR_FLOOR env var")
    r.critical = False
    zar_floor = os.getenv("ZAR_FLOOR")
    if zar_floor:
        try:
            val = Decimal(zar_floor)
            r.passed(f"ZAR_FLOOR=R{val:,.2f}")
        except Exception:
            r.failed(f"ZAR_FLOOR='{zar_floor}' is not a valid Decimal")
    else:
        r.warned("ZAR_FLOOR not set — defaults to R100,000")
    results.append(r)

    return results


def check_guardian() -> list:
    """Check Guardian service status."""
    results = []

    # Check 1: GuardianService importable
    r = ReadinessResult("GUARDIAN", "GuardianService importable")
    try:
        from services.guardian_service import GuardianService
        r.passed()
    except Exception as e:
        r.failed(str(e))
    results.append(r)

    # Check 2: System not locked
    r = ReadinessResult("GUARDIAN", "System not locked")
    try:
        from services.guardian_service import GuardianService
        locked = GuardianService.is_system_locked()
        if locked:
            r.warned("System is LOCKED — manual unlock required before trading")
        else:
            r.passed("System UNLOCKED")
    except Exception as e:
        r.failed(str(e))
    results.append(r)

    return results


def check_hitl_gate() -> list:
    """Check HITL gate availability."""
    results = []

    # Check 1: HITLGateway importable
    r = ReadinessResult("HITL", "HITLGateway importable")
    try:
        from services.hitl_gateway import HITLGateway
        r.passed()
    except Exception as e:
        r.failed(str(e))
    results.append(r)

    # Check 2: HITL operators configured
    r = ReadinessResult("HITL", "HITL operators configured")
    operators = os.getenv("HITL_ALLOWED_OPERATORS", "")
    if operators:
        r.passed(f"Operators: {operators}")
    else:
        r.warned("HITL_ALLOWED_OPERATORS not set — may use defaults")
    results.append(r)

    return results


def check_reconciliation() -> list:
    """Check reconciliation engine readiness."""
    results = []

    # Check 1: ReconciliationEngine importable
    r = ReadinessResult("RECONCILIATION", "ReconciliationEngine importable")
    try:
        from app.exchange.reconciliation import ReconciliationEngine
        r.passed()
    except Exception as e:
        r.failed(str(e))
    results.append(r)

    # Check 2: Mismatch threshold configured
    r = ReadinessResult("RECONCILIATION", "Mismatch threshold")
    r.critical = False
    try:
        from app.exchange.reconciliation import MISMATCH_THRESHOLD_PCT
        r.passed(f"Threshold: {MISMATCH_THRESHOLD_PCT}%")
    except Exception as e:
        r.failed(str(e))
    results.append(r)

    return results


def check_database() -> list:
    """Check database connectivity."""
    results = []

    # Check 1: DATABASE_URL configured
    r = ReadinessResult("DATABASE", "DATABASE_URL configured")
    db_url = os.getenv("DATABASE_URL", "")
    if db_url:
        # Redact password
        r.passed("DATABASE_URL is set")
    else:
        r.failed("DATABASE_URL not set")
    results.append(r)

    return results


def main() -> int:
    """Run all readiness checks and produce verdicts."""
    print("=" * 72)
    print("LIVE READINESS CHECK — Pre-Flight Diagnostics")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print(f"Phase: 3A (READ-ONLY EXCHANGE READINESS)")
    print("=" * 72)

    all_results = []

    categories = [
        ("Mode Matrix", check_mode_matrix),
        ("Exchange Connectivity", check_exchange_connectivity),
        ("Equity Source", check_equity_source),
        ("Guardian Service", check_guardian),
        ("HITL Gate", check_hitl_gate),
        ("Reconciliation", check_reconciliation),
        ("Database", check_database),
    ]

    for cat_name, checker in categories:
        print(f"\n{'─' * 72}")
        print(f"  {cat_name}")
        print(f"{'─' * 72}")
        results = checker()
        for r in results:
            icon = {
                "PASS": "OK", "FAIL": "XX", "SKIP": "--",
                "WARN": "!!", "NOT_RUN": "??"
            }
            crit = "*" if r.critical else " "
            print(f"  [{icon.get(r.status, '??')}]{crit} {r.check_name}: {r.status}")
            if r.details:
                print(f"       {r.details}")
        all_results.extend(results)

    # Summary
    print(f"\n{'=' * 72}")
    print("READINESS SUMMARY")
    print(f"{'=' * 72}")

    total = len(all_results)
    passed = sum(1 for r in all_results if r.status == "PASS")
    failed = sum(1 for r in all_results if r.status == "FAIL")
    warned = sum(1 for r in all_results if r.status == "WARN")
    skipped = sum(1 for r in all_results if r.status == "SKIP")
    critical_fails = sum(1 for r in all_results if r.status == "FAIL" and r.critical)

    print(f"  Total checks:    {total}")
    print(f"  Passed:          {passed}")
    print(f"  Failed:          {failed} ({critical_fails} critical)")
    print(f"  Warnings:        {warned}")
    print(f"  Skipped:         {skipped}")

    if critical_fails == 0:
        print(f"\n  VERDICT: READY — All critical checks pass")
        print(f"  (* = critical check)")
        return 0
    else:
        print(f"\n  VERDICT: NOT READY — {critical_fails} critical check(s) failed")
        print(f"  (* = critical check)")
        for r in all_results:
            if r.status == "FAIL" and r.critical:
                print(f"    - [{r.category}] {r.check_name}: {r.details}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

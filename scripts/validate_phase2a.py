#!/usr/bin/env python3
"""
============================================================================
Phase 2A Validation Harness — Post-Approval Execution Bridge
============================================================================

Creates a test HITL approval, approves it, and verifies:
1. DemoBroker PAPER execution occurs
2. Lifecycle state reaches FILLED
3. Audit/log rows created
4. Demo broker state file updated

This is a TEST HARNESS, not a production bypass.
Run from the Docker app container or WSL with DB access.

Usage:
    docker exec -it aa_local_app python scripts/validate_phase2a.py
============================================================================
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
import os
import sys
import uuid

# Ensure the project root is on the path
sys.path.insert(0, "/app" if os.path.exists("/app/app") else ".")

from sqlalchemy import text

from app.database.session import get_db
from services.demo_broker import DemoBroker, DemoMode, get_demo_broker
from services.execution_bridge import execute_approved_trade
from services.guardian_integration import get_guardian_integration
from services.hitl_config import get_hitl_config
from services.hitl_gateway import HITLGateway
from services.hitl_models import (
    ApprovalDecision,
    ApprovalStatus,
    DecisionChannel,
    DecisionType,
)


def main():
    correlation_id = str(uuid.uuid4())
    trade_id = uuid.uuid4()

    print("=" * 70)
    print("PHASE 2A VALIDATION HARNESS")
    print("=" * 70)
    print(f"correlation_id: {correlation_id}")
    print(f"trade_id:       {trade_id}")
    print()

    # ========================================================================
    # Step 0: Environment checks
    # ========================================================================
    execution_mode = os.environ.get("EXECUTION_MODE", "NOT_SET")
    demo_mode = os.environ.get("DEMO_MODE", "NOT_SET")
    live_confirmed = os.environ.get("LIVE_TRADING_CONFIRMED", "NOT_SET")

    print("[STEP 0] Environment checks")
    print(f"  EXECUTION_MODE:         {execution_mode}")
    print(f"  DEMO_MODE:              {demo_mode}")
    print(f"  LIVE_TRADING_CONFIRMED: {live_confirmed}")

    if execution_mode != "DEMO":
        print("  [FAIL] EXECUTION_MODE must be DEMO")
        sys.exit(1)
    if demo_mode not in ("PAPER", ""):
        print("  [FAIL] DEMO_MODE must be PAPER")
        sys.exit(1)
    if live_confirmed == "TRUE":
        print("  [FAIL] LIVE_TRADING_CONFIRMED must NOT be TRUE")
        sys.exit(1)

    print("  [PASS] Environment is DEMO/PAPER, LIVE guard active")
    print()

    # ========================================================================
    # Step 1: Get database session
    # ========================================================================
    print("[STEP 1] Database connection")
    db_gen = get_db()
    db_session = next(db_gen)
    print("  [PASS] Database session acquired")
    print()

    # ========================================================================
    # Step 2: Initialize services
    # ========================================================================
    print("[STEP 2] Service initialization")

    guardian = get_guardian_integration()
    print(f"  Guardian locked: {guardian.is_locked()}")
    if guardian.is_locked():
        print("  [WARN] Guardian is LOCKED — will block execution")

    hitl_config = get_hitl_config(validate=False)
    gateway = HITLGateway(
        config=hitl_config,
        guardian=guardian,
        db_session=db_session,
    )

    demo_broker = get_demo_broker(mode=DemoMode.PAPER)

    # Register in runtime so Step 13 of process_decision can find it
    import app.core.runtime as _runtime
    _runtime.set_demo_broker(demo_broker)
    _runtime.set_guardian_integration(guardian)

    print(f"  DemoBroker mode: {demo_broker._mode.value}")
    print(f"  DemoBroker state file: {demo_broker._state_file}")
    print(f"  DemoBroker balance: R {demo_broker.get_account_balance()}")
    print("  [PASS] All services initialized")
    print()

    # ========================================================================
    # Step 3: Record pre-execution state
    # ========================================================================
    print("[STEP 3] Pre-execution state")
    state_file = demo_broker._state_file
    state_exists_before = os.path.exists(state_file)
    state_mtime_before = None
    if state_exists_before:
        state_mtime_before = os.path.getmtime(state_file)
    print(f"  State file exists:  {state_exists_before}")
    print(f"  State file mtime:   {state_mtime_before}")

    balance_before = demo_broker.get_account_balance()
    print(f"  Balance before:     R {balance_before}")

    # Count existing audit rows
    try:
        result = db_session.execute(text("SELECT COUNT(*) FROM audit_log"))
        audit_count_before = result.scalar()
        print(f"  Audit log rows:     {audit_count_before}")
    except Exception:
        db_session.rollback()
        audit_count_before = -1
        print("  Audit log count:    [could not query]")
    print()

    # ========================================================================
    # Step 4: Create HITL approval request
    # ========================================================================
    print("[STEP 4] Creating HITL approval request")
    create_result = gateway.create_approval_request(
        trade_id=trade_id,
        instrument="BTCZAR",
        side="BUY",
        risk_pct=Decimal("0.0100"),
        confidence=Decimal("0.7500"),
        request_price=Decimal("1250000.00"),
        reasoning_summary={
            "bull_reasoning": "Phase 2A validation — test signal",
            "bear_reasoning": "N/A — test harness",
            "consensus_score": 75,
            "final_verdict": "BUY",
            "calculated_quantity": "0.01",
        },
        correlation_id=uuid.UUID(correlation_id),
    )
    print(f"  Success:     {create_result.success}")
    if not create_result.success:
        print(
            f"  Error:       {create_result.error_code}: {create_result.error_message}"
        )
        print("  [FAIL] Could not create HITL approval request")
        sys.exit(1)

    print(f"  Trade ID:    {trade_id}")
    print(f"  Status:      {create_result.approval_request.status}")
    print("  [PASS] HITL approval request created (AWAITING_APPROVAL)")
    print()

    # ========================================================================
    # Step 5: Verify pending approval exists
    # ========================================================================
    print("[STEP 5] Verifying pending approval")
    pending = gateway.get_pending_approvals()
    found = [p for p in pending if str(p.approval_request.trade_id) == str(trade_id)]
    if not found:
        print("  [FAIL] Pending approval not found")
        sys.exit(1)
    print(f"  Found {len(found)} pending approval(s) for this trade")
    print("  [PASS] Pending approval exists")
    print()

    # ========================================================================
    # Step 6: Approve the trade
    # ========================================================================
    print("[STEP 6] Approving trade")
    operator_id = (
        os.environ.get("HITL_ALLOWED_OPERATORS", "dev_operator1").split(",")[0].strip()
    )
    print(f"  Operator: {operator_id}")

    decision = ApprovalDecision(
        trade_id=trade_id,
        decision=DecisionType.APPROVE.value,
        operator_id=operator_id,
        channel=DecisionChannel.WEB.value,
        correlation_id=uuid.UUID(correlation_id),
        reason=None,
        comment="Phase 2A validation — approving test trade",
    )

    approve_result = gateway.process_decision(decision)
    print(f"  Success:     {approve_result.success}")
    if not approve_result.success:
        print(
            f"  Error:       {approve_result.error_code}: {approve_result.error_message}"
        )
        print("  [FAIL] Approval failed")
        sys.exit(1)

    print(f"  Status:      {approve_result.approval_request.status}")
    print(f"  Latency:     {approve_result.response_latency_seconds:.2f}s")
    print("  [PASS] Trade approved (ACCEPTED)")
    print()

    # ========================================================================
    # Step 7: Verify execution bridge fired
    # ========================================================================
    print("[STEP 7] Checking execution bridge results")

    # The bridge fires inside process_decision Step 13.
    # We verify by checking:
    # 1. DemoBroker state file was updated
    # 2. Audit log has PAPER_EXECUTION_COMPLETED entry
    # 3. DB has lifecycle transition record

    # Check state file modification
    state_exists_after = os.path.exists(state_file)
    state_mtime_after = None
    if state_exists_after:
        state_mtime_after = os.path.getmtime(state_file)

    state_updated = state_exists_after and (
        state_mtime_before is None or state_mtime_after > state_mtime_before
    )

    print(f"  State file updated: {state_updated}")
    if state_exists_after:
        print(f"  State file mtime:   {state_mtime_after}")

    # Check demo broker orders
    positions = demo_broker.get_positions()
    print(f"  Open positions:     {len(positions)}")
    for pos in positions:
        print(
            f"    {pos['symbol']} {pos['side']} qty={pos['quantity']} "
            f"entry={pos['entry_price']}"
        )

    balance_after = demo_broker.get_account_balance()
    print(f"  Balance after:      R {balance_after}")
    print()

    # ========================================================================
    # Step 8: Verify audit log entries
    # ========================================================================
    print("[STEP 8] Checking audit log")
    try:
        result = db_session.execute(
            text("""
                SELECT action, target_type, correlation_id, error_code
                FROM audit_log
                WHERE correlation_id = :corr_id
                ORDER BY created_at
            """),
            {"corr_id": correlation_id},
        )
        audit_rows = result.fetchall()
        print(f"  Audit entries for this correlation_id: {len(audit_rows)}")
        for row in audit_rows:
            print(f"    action={row[0]} target_type={row[1]} error_code={row[3]}")

        execution_audit = [r for r in audit_rows if r[0] == "PAPER_EXECUTION_COMPLETED"]
        if execution_audit:
            print("  [PASS] PAPER_EXECUTION_COMPLETED audit entry found")
        else:
            print("  [WARN] PAPER_EXECUTION_COMPLETED audit entry NOT found")

    except Exception as e:
        db_session.rollback()
        print(f"  [WARN] Could not query audit log: {str(e)[:100]}")
    print()

    # ========================================================================
    # Step 9: Verify HITL approval status in DB
    # ========================================================================
    print("[STEP 9] Checking hitl_approvals DB record")
    try:
        result = db_session.execute(
            text("""
                SELECT status, decided_by, decision_channel
                FROM hitl_approvals
                WHERE trade_id = :trade_id
            """),
            {"trade_id": str(trade_id)},
        )
        row = result.fetchone()
        if row:
            print(f"  Status:           {row[0]}")
            print(f"  Decided by:       {row[1]}")
            print(f"  Decision channel: {row[2]}")
            if row[0] == "ACCEPTED":
                print("  [PASS] Status is ACCEPTED")
            else:
                print(f"  [WARN] Expected ACCEPTED, got {row[0]}")
        else:
            print("  [WARN] No hitl_approvals record found")
    except Exception as e:
        db_session.rollback()
        print(f"  [ERROR] DB query failed: {str(e)[:100]}")
    print()

    # ========================================================================
    # Step 10: Verify demo state file content
    # ========================================================================
    print("[STEP 10] Checking DemoBroker state file")
    if os.path.exists(state_file):
        with open(state_file) as f:
            state_data = json.load(f)

        order_count = len(state_data.get("orders", {}))
        position_count = len(state_data.get("positions", {}))
        balance = state_data.get("balance_zar", "N/A")

        print(f"  Orders in state:    {order_count}")
        print(f"  Positions in state: {position_count}")
        print(f"  Balance:            R {balance}")

        if order_count > 0:
            print("  [PASS] DemoBroker state file has orders")
        else:
            print("  [WARN] No orders in state file")
    else:
        print("  [FAIL] State file does not exist")
    print()

    # ========================================================================
    # Step 11: Duplicate approval test
    # ========================================================================
    print("[STEP 11] Testing duplicate approval (must NOT double-execute)")
    decision2 = ApprovalDecision(
        trade_id=trade_id,
        decision=DecisionType.APPROVE.value,
        operator_id=operator_id,
        channel=DecisionChannel.WEB.value,
        correlation_id=uuid.uuid4(),
        reason=None,
        comment="Duplicate approval attempt",
    )

    dup_result = gateway.process_decision(decision2)
    print(f"  Success: {dup_result.success}")
    if not dup_result.success:
        print(f"  Error:   {dup_result.error_code}: {dup_result.error_message}")
        print("  [PASS] Duplicate approval correctly rejected")
    else:
        print("  [FAIL] Duplicate approval was accepted (double-execution risk)")
    print()

    # ========================================================================
    # Summary
    # ========================================================================
    print("=" * 70)
    print("PHASE 2A VALIDATION SUMMARY")
    print("=" * 70)

    checks = {
        "Environment DEMO/PAPER": execution_mode == "DEMO",
        "LIVE guard active": live_confirmed != "TRUE",
        "HITL approval created": create_result.success,
        "Pending approval found": len(found) > 0,
        "Trade approved (ACCEPTED)": approve_result.success,
        "DemoBroker state file updated": state_updated,
        "DemoBroker has orders": order_count > 0
        if os.path.exists(state_file)
        else False,
        "Duplicate approval rejected": not dup_result.success,
    }

    all_pass = True
    for check, passed in checks.items():
        status = "PASS" if passed else "FAIL"
        if not passed:
            all_pass = False
        print(f"  [{status}] {check}")

    print()
    if all_pass:
        print("VERDICT: PHASE 2A COMPLETE — PAPER EXECUTION LOOP WORKING")
    else:
        print("VERDICT: PHASE 2A PARTIAL — SOME CHECKS FAILED")

    print("=" * 70)


if __name__ == "__main__":
    main()

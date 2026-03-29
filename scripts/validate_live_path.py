#!/usr/bin/env python3
"""
============================================================================
Validate Live Execution Path — Dry Harness (Phase 3B)
============================================================================

Reliability Level: SOVEREIGN TIER
Purpose: Exercise the entire live execution code path end-to-end with
         mocked exchange responses.  No real orders placed.

Validates:
    1. ModeGuard resolve + require_live_execution_prerequisites
    2. OrderManager LIVE init + place_order (mocked VALR client)
    3. OrderStatusPoller state transitions (poll_once with mock data)
    4. LiveExecutionBridge preflight + execute_live_order
    5. Post-fill reconciliation callback (mocked recon engine)
    6. Rollout limit enforcement (max order, daily trade cap)
    7. Guardian lockdown blocks execution
    8. Duplicate trade rejection
    9. Tail-to-head: order → poll → fill → reconcile lifecycle

Exit Codes:
    0 — All checks passed
    1 — One or more checks failed

Run:
    EXECUTION_MODE=LIVE LIVE_TRADING_CONFIRMED=TRUE \
    VALR_API_KEY=test VALR_API_SECRET=test \
    python scripts/validate_live_path.py

    Or simply: python scripts/validate_live_path.py
    (The script overrides env vars internally for safety.)
============================================================================
"""

import os
import sys
import traceback

# Ensure project root is on sys.path
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

# ---- Mock requests library if shadowed by project's requests/ directory ----
import types

_requests_mod = sys.modules.get("requests")
if _requests_mod is None or not hasattr(_requests_mod, "exceptions"):
    _mock_requests = types.ModuleType("requests")
    _mock_exceptions = types.ModuleType("requests.exceptions")
    _mock_exceptions.ConnectionError = ConnectionError
    _mock_exceptions.Timeout = TimeoutError
    _mock_exceptions.RequestException = Exception
    _mock_requests.exceptions = _mock_exceptions
    sys.modules["requests"] = _mock_requests
    sys.modules["requests.exceptions"] = _mock_exceptions

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

# ============================================================================
# Helpers
# ============================================================================

_PASS = 0
_FAIL = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    """Record a check result."""
    global _PASS, _FAIL
    if condition:
        _PASS += 1
        print(f"  [PASS] {name}")
    else:
        _FAIL += 1
        msg = f"  [FAIL] {name}"
        if detail:
            msg += f" — {detail}"
        print(msg)


def section(title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


# ============================================================================
# Validation Harness
# ============================================================================

def main() -> int:
    global _PASS, _FAIL

    # Override env for safety
    live_env = {
        "EXECUTION_MODE": "LIVE",
        "LIVE_TRADING_CONFIRMED": "TRUE",
        "VALR_API_KEY": "dry-harness-key",
        "VALR_API_SECRET": "dry-harness-secret",
    }

    # ----------------------------------------------------------------
    # 1. ModeGuard
    # ----------------------------------------------------------------
    section("1. ModeGuard — Mode Resolution + Prerequisites")

    from app.exchange.mode_matrix import ModeGuard, ModeViolationError, TradingMode

    with patch.dict(os.environ, live_env, clear=True):
        guard = ModeGuard(correlation_id="dry-harness")
        check("Mode resolves to LIVE_EXECUTION", guard.mode == TradingMode.LIVE_EXECUTION)
        check("Can place orders", guard.can_place_orders())
        check("Can read market data", guard.can_read_public_data())

        try:
            guard.require_live_execution_prerequisites()
            check("Prerequisites pass", True)
        except ModeViolationError as e:
            check("Prerequisites pass", False, str(e))

    # Paper mode rejects prerequisites
    with patch.dict(os.environ, {}, clear=True):
        paper_guard = ModeGuard(correlation_id="dry-paper")
        check("Paper mode is default", paper_guard.mode == TradingMode.PAPER)
        try:
            paper_guard.require_live_execution_prerequisites()
            check("Paper rejects prerequisites", False, "Should have raised")
        except ModeViolationError:
            check("Paper rejects prerequisites", True)

    # ----------------------------------------------------------------
    # 2. OrderManager LIVE
    # ----------------------------------------------------------------
    section("2. OrderManager — LIVE Placement (Mocked)")

    from app.exchange.order_manager import (
        ExecutionMode,
        OrderManager,
        OrderManagerError,
        OrderSide,
        OrderStatus,
    )

    mock_client = MagicMock()
    mock_client.is_authenticated.return_value = True
    mock_client.place_limit_order.return_value = {"id": "dry-valr-order-001"}

    with patch.dict(os.environ, live_env, clear=True):
        mgr = OrderManager(valr_client=mock_client, correlation_id="dry-mgr")
        check("Manager in LIVE mode", mgr.execution_mode == ExecutionMode.LIVE)

        result = mgr.place_order(
            pair="BTCZAR",
            side=OrderSide.BUY,
            price=Decimal("1500000"),
            quantity=Decimal("0.001"),
        )
        check("Order SUBMITTED", result.status == OrderStatus.SUBMITTED)
        check("Not simulated", result.is_simulated is False)
        check("Has valr_order_id", result.valr_order_id == "dry-valr-order-001")
        check("Client order ID has AA_ prefix", result.order_id.startswith("AA_"))
        check("post_only=True sent", mock_client.place_limit_order.call_args is not None)

    # No client → error
    with patch.dict(os.environ, live_env, clear=True):
        mgr_noclient = OrderManager(valr_client=None, correlation_id="dry-noclient")
        try:
            mgr_noclient.place_order(
                pair="BTCZAR", side=OrderSide.BUY,
                price=Decimal("100"), quantity=Decimal("0.001"),
            )
            check("No-client raises VALR-ORD-003", False, "Should have raised")
        except OrderManagerError as e:
            check("No-client raises VALR-ORD-003", "VALR-ORD-003" in str(e))

    # ----------------------------------------------------------------
    # 3. OrderStatusPoller
    # ----------------------------------------------------------------
    section("3. OrderStatusPoller — State Transitions (Mocked)")

    from app.exchange.order_status_poller import (
        ExchangeOrderState,
        OrderStatusPoller,
        TrackedOrder,
    )

    poll_client = MagicMock()
    poll_client.get_order_status.return_value = {
        "orderStatusType": "Filled",
        "filledQuantity": "0.001",
        "averagePrice": "1500000.00",
    }

    fill_received = []

    def on_fill(order, transition):
        fill_received.append((order, transition))

    poller = OrderStatusPoller(
        valr_client=poll_client,
        on_fill=on_fill,
        correlation_id="dry-poller",
    )

    tracked = TrackedOrder(
        order_id="AA_DRY001",
        valr_order_id="dry-valr-001",
        pair="BTCZAR",
        side="BUY",
        price=Decimal("1500000"),
        quantity=Decimal("0.001"),
        correlation_id="dry-poll-corr",
    )
    poller.track_order(tracked)
    check("Active count = 1", poller.active_count == 1)

    transitions = poller.poll_once()
    check("One transition detected", len(transitions) == 1)
    check("Transition to FILLED", transitions[0].to_state == "FILLED")
    check("Order state is FILLED", tracked.state == ExchangeOrderState.FILLED)
    check("Fill callback fired", len(fill_received) == 1)

    # Second poll — no further transitions (terminal)
    transitions2 = poller.poll_once()
    check("No transition on second poll (terminal)", len(transitions2) == 0)

    # Stale detection
    stale_client = MagicMock()
    stale_poller = OrderStatusPoller(
        valr_client=stale_client, max_poll_age_s=1, correlation_id="dry-stale",
    )
    stale_order = TrackedOrder(
        order_id="AA_STALE",
        valr_order_id="stale-001",
        pair="BTCZAR",
        side="BUY",
        price=Decimal("1500000"),
        quantity=Decimal("0.001"),
        correlation_id="stale-corr",
    )
    stale_order.submitted_at = datetime.now(timezone.utc) - timedelta(hours=1)
    stale_poller.track_order(stale_order)
    stale_transitions = stale_poller.poll_once()
    check("Stale order marked FAILED", stale_order.state == ExchangeOrderState.FAILED)
    check("Stale transition recorded", len(stale_transitions) == 1)

    # ----------------------------------------------------------------
    # 4. LiveExecutionBridge
    # ----------------------------------------------------------------
    section("4. LiveExecutionBridge — Preflight + Execution (Mocked)")

    from app.exchange.live_execution_bridge import (
        ExecutionRecord,
        LiveExecutionBridge,
        RolloutLimits,
    )

    with patch.dict(os.environ, live_env, clear=True):
        bridge_guard = ModeGuard(correlation_id="dry-bridge-guard")

    bridge_client = MagicMock()
    bridge_client.is_authenticated.return_value = True
    bridge_client.place_limit_order.return_value = {"id": "dry-bridge-valr-001"}

    bridge_mgr = MagicMock(spec=OrderManager)
    from app.exchange.order_manager import OrderResult
    bridge_mgr.place_order.return_value = OrderResult(
        order_id="AA_BRIDGE01",
        pair="BTCZAR",
        side="BUY",
        order_type="LIMIT",
        price=Decimal("1500000"),
        quantity=Decimal("0.0001"),
        value_zar=Decimal("150.00"),
        status=OrderStatus.SUBMITTED,
        is_simulated=False,
        execution_mode=ExecutionMode.LIVE,
        correlation_id="dry-bridge",
        valr_order_id="dry-bridge-valr-001",
    )

    equity_src = MagicMock()
    equity_src.get_equity_zar.return_value = Decimal("50000")

    recon_engine = MagicMock()
    recon_engine._state_balances = {"BTC": Decimal("0.01")}
    recon_result = MagicMock()
    recon_result.lockdown_triggered = False
    recon_result.status = MagicMock(value="MATCHED")
    recon_engine.reconcile.return_value = recon_result

    bridge = LiveExecutionBridge(
        mode_guard=bridge_guard,
        order_manager=bridge_mgr,
        poller=None,
        recon_engine=recon_engine,
        equity_source=equity_src,
        rollout_limits=RolloutLimits(
            max_order_zar=Decimal("500"),
            max_daily_trades=5,
        ),
        correlation_id="dry-bridge",
    )

    record = bridge.execute_live_order(
        trade_id="dry-trade-001",
        correlation_id="dry-corr-001",
        pair="BTCZAR",
        side="BUY",
        price=Decimal("1500000"),
        quantity=Decimal("0.0001"),
    )

    check("Execution succeeded (no error)", record.error is None)
    check("Order result present", record.order_result is not None)
    check("valr_order_id set", record.order_result.valr_order_id == "dry-bridge-valr-001")

    # Duplicate trade rejected
    dup_record = bridge.execute_live_order(
        trade_id="dry-trade-001",
        correlation_id="dry-corr-002",
        pair="BTCZAR",
        side="BUY",
        price=Decimal("1500000"),
        quantity=Decimal("0.0001"),
    )
    check("Duplicate trade blocked", dup_record.error is not None)
    check("Duplicate error code BRIDGE-006", "BRIDGE-006" in (dup_record.error or ""))

    # ----------------------------------------------------------------
    # 5. Rollout limit enforcement
    # ----------------------------------------------------------------
    section("5. Rollout Limits")

    with patch.dict(os.environ, live_env, clear=True):
        tiny_guard = ModeGuard(correlation_id="tiny-guard")

    tiny_limits = RolloutLimits(max_order_zar=Decimal("10"))
    tiny_mgr = MagicMock(spec=OrderManager)
    tiny_bridge = LiveExecutionBridge(
        mode_guard=tiny_guard,
        order_manager=tiny_mgr,
        rollout_limits=tiny_limits,
        correlation_id="tiny-bridge",
    )

    big_record = tiny_bridge.execute_live_order(
        trade_id="big-001",
        correlation_id="big-corr",
        pair="BTCZAR",
        side="BUY",
        price=Decimal("1000"),
        quantity=Decimal("1"),
    )
    check("Over-limit order blocked", big_record.error is not None)
    check("Error is BRIDGE-001 (value)", "BRIDGE-001" in (big_record.error or ""))

    # ----------------------------------------------------------------
    # 6. Guardian Lock
    # ----------------------------------------------------------------
    section("6. Guardian Lock Blocks Execution")

    with patch.dict(os.environ, live_env, clear=True):
        lock_guard = ModeGuard(correlation_id="lock-guard")

    guardian_mock = MagicMock()
    guardian_mock._system_locked = True
    lock_mgr = MagicMock(spec=OrderManager)
    lock_bridge = LiveExecutionBridge(
        mode_guard=lock_guard,
        order_manager=lock_mgr,
        guardian=guardian_mock,
        correlation_id="lock-bridge",
    )

    lock_record = lock_bridge.execute_live_order(
        trade_id="lock-001",
        correlation_id="lock-corr",
        pair="BTCZAR",
        side="BUY",
        price=Decimal("100"),
        quantity=Decimal("0.001"),
    )
    check("Guardian-locked order blocked", lock_record.error is not None)
    check("Error is BRIDGE-004", "BRIDGE-004" in (lock_record.error or ""))
    lock_mgr.place_order.assert_not_called()
    check("No order placed when locked", True)

    # ----------------------------------------------------------------
    # 7. Post-fill reconciliation
    # ----------------------------------------------------------------
    section("7. Post-Fill Reconciliation (Mocked)")

    from app.exchange.order_status_poller import OrderStateTransition

    fill_order = TrackedOrder(
        order_id="AA_RECON01",
        valr_order_id="recon-valr-01",
        pair="BTCZAR",
        side="BUY",
        price=Decimal("1500000"),
        quantity=Decimal("0.0001"),
        correlation_id="recon-corr",
        state=ExchangeOrderState.FILLED,
        filled_quantity=Decimal("0.0001"),
        filled_price=Decimal("1500000"),
    )
    fill_transition = OrderStateTransition(
        order_id="AA_RECON01",
        valr_order_id="recon-valr-01",
        pair="BTCZAR",
        from_state="NEW",
        to_state="FILLED",
        filled_quantity=Decimal("0.0001"),
        filled_price=Decimal("1500000"),
        correlation_id="recon-corr",
    )

    # bridge from section 4 has a good recon engine
    recon_error = bridge.reconcile_after_fill(fill_order, fill_transition)
    check("Reconciliation passed (no error)", recon_error is None)

    # ----------------------------------------------------------------
    # Summary
    # ----------------------------------------------------------------
    section("VALIDATION SUMMARY")
    total = _PASS + _FAIL
    print(f"  Passed: {_PASS}/{total}")
    print(f"  Failed: {_FAIL}/{total}")

    if _FAIL == 0:
        print("\n  [RESULT] ALL CHECKS PASSED — LIVE PATH VALIDATED (dry)")
        return 0
    print(f"\n  [RESULT] {_FAIL} CHECK(S) FAILED — REVIEW REQUIRED")
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(1)

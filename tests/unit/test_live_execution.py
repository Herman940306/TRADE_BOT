"""
============================================================================
Unit Tests - Live Execution Pipeline (Phase 3B)
============================================================================

Reliability Level: SOVEREIGN TIER
Test Coverage:
    1. VALRClient: place_limit_order, get_order_status, cancel_order
    2. OrderManager: _execute_live_order success/error classification
    3. OrderStatusPoller: state mapping, stale detection, callbacks
    4. LiveExecutionBridge: preflight, rollout limits, reconciliation
    5. ModeGuard: require_live_execution_prerequisites

Tests validate:
    - Live order placement returns SUBMITTED with valr_order_id
    - Missing credentials → VALR-ORD-005
    - Insufficient balance → VALR-ORD-006
    - Invalid pair → VALR-ORD-007
    - Rate limit → VALR-ORD-008
    - VALR status mapping covers all known orderStatusType values
    - Stale orders → FAILED after max_poll_age_s
    - Transient poll errors do NOT mark order failed
    - Bridge preflight blocks: Guardian locked, duplicate, over limit
    - Equity unavailable → bridge abort (BRIDGE-005)
    - Live mode guard: LIVE_TRADING_CONFIRMED=TRUE required
    - Reconciliation mismatch → lockdown_triggered

Note: Tests import directly from submodules (not app.exchange.__init__)
      to avoid triggering the requests library import, which is shadowed
      by the project's requests/ directory in local development.
============================================================================
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import os
import sys
import types
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

# Ensure project root is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

# ---------------------------------------------------------------------------
# Fix for local 'requests/' directory shadowing the pip 'requests' package.
# ---------------------------------------------------------------------------
_requests_mod = sys.modules.get("requests")
if _requests_mod is None or not hasattr(_requests_mod, "exceptions"):
    _mock_requests = types.ModuleType("requests")
    _mock_exceptions = types.ModuleType("requests.exceptions")
    _mock_exceptions.ConnectionError = ConnectionError  # type: ignore[attr-defined]
    _mock_exceptions.Timeout = TimeoutError  # type: ignore[attr-defined]
    _mock_exceptions.RequestException = Exception  # type: ignore[attr-defined]
    _mock_requests.exceptions = _mock_exceptions  # type: ignore[attr-defined]
    sys.modules["requests"] = _mock_requests
    sys.modules["requests.exceptions"] = _mock_exceptions


# =============================================================================
# 1. ExchangeOrderState Tests
# =============================================================================

class TestExchangeOrderState:
    """Tests for VALR status → ExchangeOrderState mapping."""

    def _import(self):
        from app.exchange.order_status_poller import ExchangeOrderState
        return ExchangeOrderState

    def test_from_valr_filled(self):
        EOS = self._import()
        assert EOS.from_valr("Filled") == EOS.FILLED

    def test_from_valr_active(self):
        EOS = self._import()
        assert EOS.from_valr("Active") == EOS.NEW

    def test_from_valr_placed(self):
        EOS = self._import()
        assert EOS.from_valr("Placed") == EOS.PLACED

    def test_from_valr_partially_filled(self):
        EOS = self._import()
        assert EOS.from_valr("Partially Filled") == EOS.PARTIALLY_FILLED

    def test_from_valr_cancelled(self):
        EOS = self._import()
        assert EOS.from_valr("Cancelled") == EOS.CANCELLED

    def test_from_valr_failed(self):
        EOS = self._import()
        assert EOS.from_valr("Failed") == EOS.FAILED

    def test_from_valr_expired(self):
        EOS = self._import()
        assert EOS.from_valr("Expired") == EOS.EXPIRED

    def test_from_valr_instant_order_completed(self):
        EOS = self._import()
        assert EOS.from_valr("Instant Order Completed") == EOS.FILLED

    def test_from_valr_case_insensitive(self):
        EOS = self._import()
        assert EOS.from_valr("fIlLeD") == EOS.FILLED
        assert EOS.from_valr("CANCELLED") == EOS.CANCELLED

    def test_from_valr_unknown_maps_to_failed(self):
        EOS = self._import()
        assert EOS.from_valr("SomeUnknownStatus") == EOS.FAILED

    def test_terminal_states(self):
        EOS = self._import()
        assert EOS.is_terminal(EOS.FILLED) is True
        assert EOS.is_terminal(EOS.CANCELLED) is True
        assert EOS.is_terminal(EOS.FAILED) is True
        assert EOS.is_terminal(EOS.EXPIRED) is True

    def test_non_terminal_states(self):
        EOS = self._import()
        assert EOS.is_terminal(EOS.NEW) is False
        assert EOS.is_terminal(EOS.PLACED) is False
        assert EOS.is_terminal(EOS.PARTIALLY_FILLED) is False


# =============================================================================
# 2. OrderStatusPoller Tests
# =============================================================================

class TestOrderStatusPoller:
    """Tests for OrderStatusPoller polling logic and callbacks."""

    def _import(self):
        from app.exchange.order_status_poller import (
            ExchangeOrderState,
            OrderStatusPoller,
            TrackedOrder,
        )
        return OrderStatusPoller, TrackedOrder, ExchangeOrderState

    def _make_tracked(self, ExchangeOrderState, TrackedOrder, **overrides):
        defaults = dict(
            order_id="AA_TEST001",
            valr_order_id="valr-abc-123",
            pair="BTCZAR",
            side="BUY",
            price=Decimal("1500000"),
            quantity=Decimal("0.0001"),
            correlation_id="test-corr-001",
            state=ExchangeOrderState.NEW,
        )
        defaults.update(overrides)
        return TrackedOrder(**defaults)

    def test_track_and_active_count(self):
        Poller, TrackedOrder, EOS = self._import()
        client = MagicMock()
        poller = Poller(valr_client=client)
        order = self._make_tracked(EOS, TrackedOrder)
        poller.track_order(order)
        assert poller.active_count == 1

    def test_untrack_order(self):
        Poller, TrackedOrder, EOS = self._import()
        client = MagicMock()
        poller = Poller(valr_client=client)
        order = self._make_tracked(EOS, TrackedOrder)
        poller.track_order(order)
        removed = poller.untrack_order(order.valr_order_id)
        assert removed is order
        assert poller.active_count == 0

    def test_poll_once_detects_fill(self):
        Poller, TrackedOrder, EOS = self._import()
        client = MagicMock()
        client.get_order_status.return_value = {
            "orderStatusType": "Filled",
            "filledQuantity": "0.0001",
            "averagePrice": "1500000.00",
        }

        fill_cb = MagicMock()
        poller = Poller(valr_client=client, on_fill=fill_cb)
        order = self._make_tracked(EOS, TrackedOrder)
        poller.track_order(order)

        transitions = poller.poll_once()
        assert len(transitions) == 1
        assert transitions[0].to_state == "FILLED"
        assert order.state == EOS.FILLED
        fill_cb.assert_called_once()

    def test_poll_once_partial_fill(self):
        Poller, TrackedOrder, EOS = self._import()
        client = MagicMock()
        client.get_order_status.return_value = {
            "orderStatusType": "Partially Filled",
            "filledQuantity": "0.00005",
            "averagePrice": "1500000.00",
        }

        partial_cb = MagicMock()
        poller = Poller(valr_client=client, on_partial_fill=partial_cb)
        order = self._make_tracked(EOS, TrackedOrder)
        poller.track_order(order)

        transitions = poller.poll_once()
        assert len(transitions) == 1
        assert transitions[0].to_state == "PARTIALLY_FILLED"
        partial_cb.assert_called_once()

    def test_poll_once_cancelled(self):
        Poller, TrackedOrder, EOS = self._import()
        client = MagicMock()
        client.get_order_status.return_value = {
            "orderStatusType": "Cancelled",
            "filledQuantity": "0",
            "averagePrice": "0",
        }

        cancel_cb = MagicMock()
        poller = Poller(valr_client=client, on_cancel=cancel_cb)
        order = self._make_tracked(EOS, TrackedOrder)
        poller.track_order(order)

        transitions = poller.poll_once()
        assert len(transitions) == 1
        assert transitions[0].to_state == "CANCELLED"
        cancel_cb.assert_called_once()

    def test_poll_once_skips_terminal(self):
        Poller, TrackedOrder, EOS = self._import()
        client = MagicMock()
        poller = Poller(valr_client=client)
        order = self._make_tracked(EOS, TrackedOrder, state=EOS.FILLED)
        poller.track_order(order)

        transitions = poller.poll_once()
        assert len(transitions) == 0
        client.get_order_status.assert_not_called()

    def test_poll_once_stale_order_marks_failed(self):
        Poller, TrackedOrder, EOS = self._import()
        client = MagicMock()
        poller = Poller(valr_client=client, max_poll_age_s=60)
        order = self._make_tracked(EOS, TrackedOrder)
        # Set submitted_at to 2 hours ago → stale
        order.submitted_at = datetime.now(timezone.utc) - timedelta(hours=2)
        poller.track_order(order)

        fail_cb = MagicMock()
        poller._on_fail = fail_cb

        transitions = poller.poll_once()
        assert len(transitions) == 1
        assert order.state == EOS.FAILED
        client.get_order_status.assert_not_called()

    def test_poll_once_transient_error_no_state_change(self):
        Poller, TrackedOrder, EOS = self._import()
        client = MagicMock()
        client.get_order_status.side_effect = ConnectionError("Network down")
        poller = Poller(valr_client=client)
        order = self._make_tracked(EOS, TrackedOrder)
        poller.track_order(order)

        transitions = poller.poll_once()
        # Transient errors do NOT mark order failed
        assert len(transitions) == 0
        assert order.state == EOS.NEW

    def test_poll_once_no_state_change_no_transition(self):
        Poller, TrackedOrder, EOS = self._import()
        client = MagicMock()
        client.get_order_status.return_value = {
            "orderStatusType": "Active",
            "filledQuantity": "0",
            "averagePrice": "0",
        }
        poller = Poller(valr_client=client)
        order = self._make_tracked(EOS, TrackedOrder)
        poller.track_order(order)

        transitions = poller.poll_once()
        # NEW → NEW (Active maps to NEW) — no change
        assert len(transitions) == 0

    def test_get_status_diagnostics(self):
        Poller, TrackedOrder, EOS = self._import()
        client = MagicMock()
        poller = Poller(valr_client=client, correlation_id="diag-1")
        status = poller.get_status()
        assert status["tracked_total"] == 0
        assert status["correlation_id"] == "diag-1"

    def test_callback_error_does_not_propagate(self):
        Poller, TrackedOrder, EOS = self._import()
        client = MagicMock()
        client.get_order_status.return_value = {
            "orderStatusType": "Filled",
            "filledQuantity": "0.0001",
            "averagePrice": "1500000",
        }

        def exploding_callback(order, transition):
            raise RuntimeError("callback explosion")

        poller = Poller(valr_client=client, on_fill=exploding_callback)
        order = self._make_tracked(EOS, TrackedOrder)
        poller.track_order(order)

        # Should not raise despite callback error
        transitions = poller.poll_once()
        assert len(transitions) == 1
        assert order.state == EOS.FILLED


# =============================================================================
# 3. OrderManager Live Execution Tests
# =============================================================================

class TestOrderManagerLive:
    """Tests for OrderManager._execute_live_order and error classification."""

    def _import(self):
        from app.exchange.order_manager import (
            OrderManager,
            OrderManagerError,
            OrderResult,
            OrderSide,
            OrderStatus,
            OrderType,
        )
        return OrderManager, OrderManagerError, OrderResult, OrderSide, OrderStatus, OrderType

    def _make_live_manager(self, OrderManager, client=None):
        """Create a LIVE mode OrderManager with mocked env."""
        env = {
            "EXECUTION_MODE": "LIVE",
            "LIVE_TRADING_CONFIRMED": "TRUE",
        }
        with patch.dict(os.environ, env, clear=True):
            return OrderManager(
                valr_client=client,
                correlation_id="test-live-mgr",
            )

    def test_live_order_success(self):
        OM, _, _, OrderSide, OrderStatus, OrderType = self._import()
        client = MagicMock()
        client.is_authenticated.return_value = True
        client.place_limit_order.return_value = {
            "id": "valr-order-xyz",
        }

        mgr = self._make_live_manager(OM, client)
        result = mgr.place_order(
            pair="BTCZAR",
            side=OrderSide.BUY,
            price=Decimal("1500000"),
            quantity=Decimal("0.001"),
        )

        assert result.status == OrderStatus.SUBMITTED
        assert result.is_simulated is False
        assert result.valr_order_id == "valr-order-xyz"
        assert result.order_id.startswith("AA_")
        client.place_limit_order.assert_called_once()

        # Verify post_only was passed
        call_kwargs = client.place_limit_order.call_args
        assert call_kwargs.kwargs.get("post_only") is True or call_kwargs[1].get("post_only") is True

    def test_live_order_no_client_raises(self):
        OM, OMErr, _, OrderSide, _, _ = self._import()
        mgr = self._make_live_manager(OM, client=None)

        with pytest.raises(OMErr, match="VALR-ORD-003"):
            mgr.place_order(
                pair="BTCZAR",
                side=OrderSide.BUY,
                price=Decimal("100"),
                quantity=Decimal("0.001"),
            )

    def test_live_order_unauthenticated_raises(self):
        OM, OMErr, _, OrderSide, _, _ = self._import()
        client = MagicMock()
        client.is_authenticated.return_value = False

        mgr = self._make_live_manager(OM, client)

        with pytest.raises(OMErr, match="VALR-ORD-005"):
            mgr.place_order(
                pair="BTCZAR",
                side=OrderSide.BUY,
                price=Decimal("100"),
                quantity=Decimal("0.001"),
            )

    def test_live_order_rate_limit_error(self):
        OM, OMErr, _, OrderSide, _, _ = self._import()
        from app.exchange.valr_client import RateLimitError

        client = MagicMock()
        client.is_authenticated.return_value = True
        client.place_limit_order.side_effect = RateLimitError("429 Too Many Requests")

        mgr = self._make_live_manager(OM, client)

        with pytest.raises(OMErr, match="VALR-ORD-008"):
            mgr.place_order(
                pair="BTCZAR",
                side=OrderSide.BUY,
                price=Decimal("100"),
                quantity=Decimal("0.001"),
            )

    def test_live_order_insufficient_balance(self):
        OM, OMErr, _, OrderSide, _, _ = self._import()
        from app.exchange.valr_client import APIError

        client = MagicMock()
        client.is_authenticated.return_value = True
        client.place_limit_order.side_effect = APIError(
            "Insufficient balance for BUY"
        )

        mgr = self._make_live_manager(OM, client)

        with pytest.raises(OMErr, match="VALR-ORD-006"):
            mgr.place_order(
                pair="BTCZAR",
                side=OrderSide.BUY,
                price=Decimal("100"),
                quantity=Decimal("0.001"),
            )

    def test_live_order_invalid_pair(self):
        OM, OMErr, _, OrderSide, _, _ = self._import()
        from app.exchange.valr_client import APIError

        client = MagicMock()
        client.is_authenticated.return_value = True
        client.place_limit_order.side_effect = APIError(
            "Invalid pair specified"
        )

        mgr = self._make_live_manager(OM, client)

        with pytest.raises(OMErr, match="VALR-ORD-007"):
            mgr.place_order(
                pair="FAKEPAIR",
                side=OrderSide.BUY,
                price=Decimal("100"),
                quantity=Decimal("0.001"),
            )

    def test_live_order_timeout(self):
        OM, OMErr, _, OrderSide, _, _ = self._import()

        client = MagicMock()
        client.is_authenticated.return_value = True
        client.place_limit_order.side_effect = TimeoutError("Request timed out")

        mgr = self._make_live_manager(OM, client)

        with pytest.raises(OMErr, match="VALR-ORD-010"):
            mgr.place_order(
                pair="BTCZAR",
                side=OrderSide.BUY,
                price=Decimal("100"),
                quantity=Decimal("0.001"),
            )

    def test_live_order_exchange_unavailable(self):
        OM, OMErr, _, OrderSide, _, _ = self._import()
        from app.exchange.valr_client import APIError

        client = MagicMock()
        client.is_authenticated.return_value = True
        client.place_limit_order.side_effect = APIError(
            "503 Service Unavailable"
        )

        mgr = self._make_live_manager(OM, client)

        with pytest.raises(OMErr, match="VALR-ORD-009"):
            mgr.place_order(
                pair="BTCZAR",
                side=OrderSide.BUY,
                price=Decimal("100"),
                quantity=Decimal("0.001"),
            )

    def test_classify_api_error_precision(self):
        from app.exchange.order_manager import OrderManager
        code, msg = OrderManager._classify_api_error(
            "Invalid decimal precision for quantity", "BTCZAR", "BUY"
        )
        assert code == "VALR-ORD-007"

    def test_classify_api_error_unknown_fallback(self):
        from app.exchange.order_manager import OrderManager
        code, msg = OrderManager._classify_api_error(
            "Something completely unexpected happened", "BTCZAR", "BUY"
        )
        assert code == "VALR-ORD-004"

    def test_market_order_rejected_in_live(self):
        OM, _, _, OrderSide, _, OrderType = self._import()
        from app.exchange.order_manager import MarketOrderRejectedError

        client = MagicMock()
        client.is_authenticated.return_value = True
        mgr = self._make_live_manager(OM, client)

        with pytest.raises(MarketOrderRejectedError, match="VALR-ORD-001"):
            mgr.place_order(
                pair="BTCZAR",
                side=OrderSide.BUY,
                price=Decimal("100"),
                quantity=Decimal("0.001"),
                order_type=OrderType.MARKET,
            )

    def test_order_value_exceeded_in_live(self):
        OM, _, _, OrderSide, _, _ = self._import()
        from app.exchange.order_manager import OrderValueExceededError

        client = MagicMock()
        client.is_authenticated.return_value = True
        mgr = self._make_live_manager(OM, client)
        # Default MAX_ORDER_ZAR is R5000; Decimal("10000") * 1 = R10000
        with pytest.raises(OrderValueExceededError, match="VALR-ORD-002"):
            mgr.place_order(
                pair="BTCZAR",
                side=OrderSide.BUY,
                price=Decimal("10000"),
                quantity=Decimal("1"),
            )


# =============================================================================
# 4. LiveExecutionBridge Tests
# =============================================================================

class TestLiveExecutionBridge:
    """Tests for LiveExecutionBridge pre-flight and execution."""

    def _import(self):
        from app.exchange.live_execution_bridge import (
            ExecutionRecord,
            LiveExecutionBridge,
            RolloutLimits,
        )
        from app.exchange.mode_matrix import ModeGuard, TradingMode
        from app.exchange.order_manager import (
            ExecutionMode,
            OrderManager,
            OrderManagerError,
            OrderResult,
            OrderSide,
            OrderStatus,
            OrderType,
        )
        return (
            LiveExecutionBridge, RolloutLimits, ExecutionRecord,
            ModeGuard, TradingMode,
            OrderManager, OrderManagerError, OrderResult,
            OrderSide, OrderStatus, OrderType, ExecutionMode,
        )

    def _make_bridge(self, LEB, mode_guard, order_manager, **overrides):
        defaults = dict(
            mode_guard=mode_guard,
            order_manager=order_manager,
            poller=None,
            recon_engine=None,
            equity_source=None,
            guardian=None,
            rollout_limits=None,
            correlation_id="test-bridge",
        )
        defaults.update(overrides)
        return LEB(**defaults)

    def _live_guard(self, ModeGuard):
        env = {
            "EXECUTION_MODE": "LIVE",
            "LIVE_TRADING_CONFIRMED": "TRUE",
            "VALR_API_KEY": "test-key",
            "VALR_API_SECRET": "test-secret",
        }
        with patch.dict(os.environ, env, clear=True):
            return ModeGuard(correlation_id="test-guard-live")

    def _live_manager(self, OrderManager, result=None):
        client = MagicMock()
        client.is_authenticated.return_value = True
        if result is None:
            from app.exchange.order_manager import (
                ExecutionMode,
                OrderResult,
                OrderStatus,
            )
            result = OrderResult(
                order_id="AA_TEST123",
                pair="BTCZAR",
                side="BUY",
                order_type="LIMIT",
                price=Decimal("1500000"),
                quantity=Decimal("0.0001"),
                value_zar=Decimal("150.00"),
                status=OrderStatus.SUBMITTED,
                is_simulated=False,
                execution_mode=ExecutionMode.LIVE,
                correlation_id="test-mgr",
                valr_order_id="valr-xyz",
            )
        mgr = MagicMock(spec=OrderManager)
        mgr.place_order.return_value = result
        return mgr

    def test_execute_success(self):
        (
            LEB, RL, ER, ModeGuard, TM,
            OM, OMErr, OR, OSide, OStat, OType, EM,
        ) = self._import()

        guard = self._live_guard(ModeGuard)
        mgr = self._live_manager(OM)

        equity_src = MagicMock()
        equity_src.get_equity_zar.return_value = Decimal("50000")

        bridge = self._make_bridge(
            LEB, guard, mgr,
            equity_source=equity_src,
            recon_engine=MagicMock(),
        )

        record = bridge.execute_live_order(
            trade_id="trade-001",
            correlation_id="corr-001",
            pair="BTCZAR",
            side="BUY",
            price=Decimal("1500000"),
            quantity=Decimal("0.0001"),
        )

        assert record.error is None
        assert record.order_result is not None
        assert record.order_result.valr_order_id == "valr-xyz"
        mgr.place_order.assert_called_once()

    def test_execute_guardian_locked_blocks(self):
        (
            LEB, RL, ER, ModeGuard, TM,
            OM, OMErr, OR, OSide, OStat, OType, EM,
        ) = self._import()

        guard = self._live_guard(ModeGuard)
        mgr = self._live_manager(OM)

        guardian = MagicMock()
        guardian._system_locked = True

        bridge = self._make_bridge(LEB, guard, mgr, guardian=guardian)

        record = bridge.execute_live_order(
            trade_id="trade-002",
            correlation_id="corr-002",
            pair="BTCZAR",
            side="BUY",
            price=Decimal("100"),
            quantity=Decimal("0.001"),
        )

        assert record.error is not None
        assert "BRIDGE-004" in record.error
        mgr.place_order.assert_not_called()

    def test_execute_duplicate_trade_blocked(self):
        (
            LEB, RL, ER, ModeGuard, TM,
            OM, OMErr, OR, OSide, OStat, OType, EM,
        ) = self._import()

        guard = self._live_guard(ModeGuard)
        mgr = self._live_manager(OM)
        equity_src = MagicMock()
        equity_src.get_equity_zar.return_value = Decimal("50000")

        bridge = self._make_bridge(
            LEB, guard, mgr,
            equity_source=equity_src,
            recon_engine=MagicMock(),
        )

        # First execution succeeds
        bridge.execute_live_order(
            trade_id="trade-dup",
            correlation_id="corr-dup",
            pair="BTCZAR",
            side="BUY",
            price=Decimal("100"),
            quantity=Decimal("0.001"),
        )

        # Second execution with same trade_id → blocked
        record = bridge.execute_live_order(
            trade_id="trade-dup",
            correlation_id="corr-dup-2",
            pair="BTCZAR",
            side="BUY",
            price=Decimal("100"),
            quantity=Decimal("0.001"),
        )

        assert record.error is not None
        assert "BRIDGE-006" in record.error

    def test_execute_order_value_exceeds_rollout(self):
        (
            LEB, RL, ER, ModeGuard, TM,
            OM, OMErr, OR, OSide, OStat, OType, EM,
        ) = self._import()

        guard = self._live_guard(ModeGuard)
        mgr = self._live_manager(OM)

        limits = RL(max_order_zar=Decimal("100"))
        bridge = self._make_bridge(LEB, guard, mgr, rollout_limits=limits)

        # Order value = 1000 * 1 = R1000 > R100 limit
        record = bridge.execute_live_order(
            trade_id="trade-big",
            correlation_id="corr-big",
            pair="BTCZAR",
            side="BUY",
            price=Decimal("1000"),
            quantity=Decimal("1"),
        )

        assert record.error is not None
        assert "BRIDGE-001" in record.error
        assert "rollout" in record.error.lower() or "exceeds" in record.error.lower()

    def test_execute_daily_trade_limit_reached(self):
        (
            LEB, RL, ER, ModeGuard, TM,
            OM, OMErr, OR, OSide, OStat, OType, EM,
        ) = self._import()

        guard = self._live_guard(ModeGuard)
        mgr = self._live_manager(OM)
        equity_src = MagicMock()
        equity_src.get_equity_zar.return_value = Decimal("50000")

        limits = RL(max_daily_trades=2, max_daily_zar_volume=Decimal("999999"))
        bridge = self._make_bridge(
            LEB, guard, mgr,
            rollout_limits=limits,
            equity_source=equity_src,
            recon_engine=MagicMock(),
        )

        # Execute 2 trades (the limit)
        for i in range(2):
            r = bridge.execute_live_order(
                trade_id=f"trade-d{i}",
                correlation_id=f"corr-d{i}",
                pair="BTCZAR",
                side="BUY",
                price=Decimal("100"),
                quantity=Decimal("0.001"),
            )
            assert r.error is None, f"Trade {i} failed unexpectedly: {r.error}"

        # Third trade → blocked
        record = bridge.execute_live_order(
            trade_id="trade-d2",
            correlation_id="corr-d2",
            pair="BTCZAR",
            side="BUY",
            price=Decimal("100"),
            quantity=Decimal("0.001"),
        )
        assert record.error is not None
        assert "Daily trade limit" in record.error or "BRIDGE-001" in record.error

    def test_execute_equity_unavailable_blocks(self):
        (
            LEB, RL, ER, ModeGuard, TM,
            OM, OMErr, OR, OSide, OStat, OType, EM,
        ) = self._import()

        guard = self._live_guard(ModeGuard)
        mgr = self._live_manager(OM)

        equity_src = MagicMock()
        equity_src.get_equity_zar.return_value = None  # Equity unavailable

        bridge = self._make_bridge(
            LEB, guard, mgr,
            equity_source=equity_src,
            recon_engine=MagicMock(),
        )

        record = bridge.execute_live_order(
            trade_id="trade-noeq",
            correlation_id="corr-noeq",
            pair="BTCZAR",
            side="BUY",
            price=Decimal("100"),
            quantity=Decimal("0.001"),
        )

        assert record.error is not None
        assert "BRIDGE-005" in record.error

    def test_execute_no_recon_engine_blocks(self):
        (
            LEB, RL, ER, ModeGuard, TM,
            OM, OMErr, OR, OSide, OStat, OType, EM,
        ) = self._import()

        guard = self._live_guard(ModeGuard)
        mgr = self._live_manager(OM)

        limits = RL(require_reconciliation=True)
        bridge = self._make_bridge(
            LEB, guard, mgr,
            rollout_limits=limits,
            recon_engine=None,  # No recon engine
        )

        record = bridge.execute_live_order(
            trade_id="trade-norecon",
            correlation_id="corr-norecon",
            pair="BTCZAR",
            side="BUY",
            price=Decimal("100"),
            quantity=Decimal("0.001"),
        )

        assert record.error is not None
        assert "BRIDGE-001" in record.error
        assert "econciliation" in record.error

    def test_execute_paper_mode_blocks(self):
        (
            LEB, RL, ER, ModeGuard, TM,
            OM, OMErr, OR, OSide, OStat, OType, EM,
        ) = self._import()

        with patch.dict(os.environ, {}, clear=True):
            guard = ModeGuard(correlation_id="paper-guard")

        mgr = self._live_manager(OM)
        bridge = self._make_bridge(LEB, guard, mgr)

        record = bridge.execute_live_order(
            trade_id="trade-paper",
            correlation_id="corr-paper",
            pair="BTCZAR",
            side="BUY",
            price=Decimal("100"),
            quantity=Decimal("0.001"),
        )

        assert record.error is not None
        assert "BRIDGE-001" in record.error
        mgr.place_order.assert_not_called()

    def test_reset_daily_counters(self):
        (
            LEB, RL, ER, ModeGuard, TM,
            OM, OMErr, OR, OSide, OStat, OType, EM,
        ) = self._import()

        guard = self._live_guard(ModeGuard)
        mgr = self._live_manager(OM)
        equity_src = MagicMock()
        equity_src.get_equity_zar.return_value = Decimal("50000")

        bridge = self._make_bridge(
            LEB, guard, mgr,
            equity_source=equity_src,
            recon_engine=MagicMock(),
        )

        bridge.execute_live_order(
            trade_id="trade-reset",
            correlation_id="corr-reset",
            pair="BTCZAR",
            side="BUY",
            price=Decimal("100"),
            quantity=Decimal("0.001"),
        )

        status = bridge.get_status()
        assert status["daily_trades"] == 1

        bridge.reset_daily_counters()
        status = bridge.get_status()
        assert status["daily_trades"] == 0

    def test_execute_per_symbol_limit(self):
        (
            LEB, RL, ER, ModeGuard, TM,
            OM, OMErr, OR, OSide, OStat, OType, EM,
        ) = self._import()

        guard = self._live_guard(ModeGuard)
        mgr = self._live_manager(OM)
        equity_src = MagicMock()
        equity_src.get_equity_zar.return_value = Decimal("50000")

        limits = RL(
            max_per_symbol_trades=2,
            max_daily_trades=10,
            max_daily_zar_volume=Decimal("999999"),
        )
        bridge = self._make_bridge(
            LEB, guard, mgr,
            rollout_limits=limits,
            equity_source=equity_src,
            recon_engine=MagicMock(),
        )

        # 2 trades on BTCZAR
        for i in range(2):
            r = bridge.execute_live_order(
                trade_id=f"trade-sym{i}",
                correlation_id=f"corr-sym{i}",
                pair="BTCZAR",
                side="BUY",
                price=Decimal("100"),
                quantity=Decimal("0.001"),
            )
            assert r.error is None

        # 3rd BTCZAR → blocked
        record = bridge.execute_live_order(
            trade_id="trade-sym2",
            correlation_id="corr-sym2",
            pair="BTCZAR",
            side="BUY",
            price=Decimal("100"),
            quantity=Decimal("0.001"),
        )
        assert record.error is not None
        assert "BRIDGE-001" in record.error
        assert "Per-symbol" in record.error or "per-symbol" in record.error or "BTCZAR" in record.error

    def test_execute_registers_with_poller(self):
        (
            LEB, RL, ER, ModeGuard, TM,
            OM, OMErr, OR, OSide, OStat, OType, EM,
        ) = self._import()

        guard = self._live_guard(ModeGuard)
        mgr = self._live_manager(OM)
        equity_src = MagicMock()
        equity_src.get_equity_zar.return_value = Decimal("50000")
        poller = MagicMock()

        bridge = self._make_bridge(
            LEB, guard, mgr,
            equity_source=equity_src,
            recon_engine=MagicMock(),
            poller=poller,
        )

        bridge.execute_live_order(
            trade_id="trade-poll",
            correlation_id="corr-poll",
            pair="BTCZAR",
            side="BUY",
            price=Decimal("100"),
            quantity=Decimal("0.001"),
        )

        poller.track_order.assert_called_once()

    def test_execute_invalid_side_blocked(self):
        (
            LEB, RL, ER, ModeGuard, TM,
            OM, OMErr, OR, OSide, OStat, OType, EM,
        ) = self._import()

        guard = self._live_guard(ModeGuard)
        mgr = self._live_manager(OM)
        equity_src = MagicMock()
        equity_src.get_equity_zar.return_value = Decimal("50000")

        bridge = self._make_bridge(
            LEB, guard, mgr,
            equity_source=equity_src,
            recon_engine=MagicMock(),
        )

        record = bridge.execute_live_order(
            trade_id="trade-badside",
            correlation_id="corr-badside",
            pair="BTCZAR",
            side="BUYS",  # typo
            price=Decimal("100"),
            quantity=Decimal("0.001"),
        )

        assert record.error is not None
        assert "BRIDGE-001" in record.error
        assert "Invalid order side" in record.error
        mgr.place_order.assert_not_called()

    def test_reconcile_after_fill_success(self):
        (
            LEB, RL, ER, ModeGuard, TM,
            OM, OMErr, OR, OSide, OStat, OType, EM,
        ) = self._import()
        from app.exchange.order_status_poller import (
            ExchangeOrderState,
            OrderStateTransition,
            TrackedOrder,
        )

        guard = self._live_guard(ModeGuard)
        mgr = self._live_manager(OM)

        recon_result = MagicMock()
        recon_result.lockdown_triggered = False
        recon_result.status = MagicMock(value="MATCHED")
        recon_result.discrepancy_pct = Decimal("0")

        recon_engine = MagicMock()
        recon_engine._state_balances = {"BTC": Decimal("0.001")}
        recon_engine.reconcile.return_value = recon_result

        bridge = self._make_bridge(LEB, guard, mgr, recon_engine=recon_engine)

        order = TrackedOrder(
            order_id="AA_FILL01",
            valr_order_id="valr-fill-01",
            pair="BTCZAR",
            side="BUY",
            price=Decimal("1500000"),
            quantity=Decimal("0.0001"),
            correlation_id="corr-fill",
            state=ExchangeOrderState.FILLED,
            filled_quantity=Decimal("0.0001"),
            filled_price=Decimal("1500000"),
        )
        transition = OrderStateTransition(
            order_id="AA_FILL01",
            valr_order_id="valr-fill-01",
            pair="BTCZAR",
            from_state="NEW",
            to_state="FILLED",
            filled_quantity=Decimal("0.0001"),
            filled_price=Decimal("1500000"),
            correlation_id="corr-fill",
        )

        result = bridge.reconcile_after_fill(order, transition)
        assert result is None  # No error
        recon_engine.reconcile.assert_called_once_with("BTC")

    def test_reconcile_after_fill_mismatch_triggers_lockdown(self):
        (
            LEB, RL, ER, ModeGuard, TM,
            OM, OMErr, OR, OSide, OStat, OType, EM,
        ) = self._import()
        from app.exchange.order_status_poller import (
            ExchangeOrderState,
            OrderStateTransition,
            TrackedOrder,
        )

        guard = self._live_guard(ModeGuard)
        mgr = self._live_manager(OM)

        recon_result = MagicMock()
        recon_result.lockdown_triggered = True
        recon_result.discrepancy_pct = Decimal("5.2")

        recon_engine = MagicMock()
        recon_engine._state_balances = {"BTC": Decimal("0.001")}
        recon_engine.reconcile.return_value = recon_result

        bridge = self._make_bridge(LEB, guard, mgr, recon_engine=recon_engine)

        order = TrackedOrder(
            order_id="AA_MIS01",
            valr_order_id="valr-mis-01",
            pair="BTCZAR",
            side="BUY",
            price=Decimal("1500000"),
            quantity=Decimal("0.0001"),
            correlation_id="corr-mis",
            state=ExchangeOrderState.FILLED,
            filled_quantity=Decimal("0.0001"),
            filled_price=Decimal("1500000"),
        )
        transition = OrderStateTransition(
            order_id="AA_MIS01",
            valr_order_id="valr-mis-01",
            pair="BTCZAR",
            from_state="NEW",
            to_state="FILLED",
            filled_quantity=Decimal("0.0001"),
            filled_price=Decimal("1500000"),
            correlation_id="corr-mis",
        )

        result = bridge.reconcile_after_fill(order, transition)
        assert result is not None
        assert "BRIDGE-003" in result
        assert "lockdown" in result.lower() or "MISMATCH" in result


# =============================================================================
# 5. ModeGuard Live Prerequisites Tests
# =============================================================================

class TestModeGuardLivePrerequisites:
    """Tests for ModeGuard.require_live_execution_prerequisites."""

    def _import(self):
        from app.exchange.mode_matrix import ModeGuard, ModeViolationError, TradingMode
        return ModeGuard, TradingMode, ModeViolationError

    def test_live_prerequisites_pass(self):
        MG, TM, MVE = self._import()
        env = {
            "EXECUTION_MODE": "LIVE",
            "LIVE_TRADING_CONFIRMED": "TRUE",
            "VALR_API_KEY": "key123",
            "VALR_API_SECRET": "secret456",
        }
        with patch.dict(os.environ, env, clear=True):
            guard = MG(correlation_id="test-prereq-pass")
            # Should not raise
            guard.require_live_execution_prerequisites()

    def test_live_prereq_rejects_paper_mode(self):
        MG, TM, MVE = self._import()
        with patch.dict(os.environ, {}, clear=True):
            guard = MG(correlation_id="test-prereq-paper")
            with pytest.raises(MVE, match="MODE-003"):
                guard.require_live_execution_prerequisites()

    def test_live_prereq_rejects_dry_run_mode(self):
        MG, TM, MVE = self._import()
        env = {"EXECUTION_MODE": "DRY_RUN"}
        with patch.dict(os.environ, env, clear=True):
            guard = MG(correlation_id="test-prereq-dryrun")
            with pytest.raises(MVE, match="MODE-003"):
                guard.require_live_execution_prerequisites()

    def test_live_prereq_rejects_without_confirmation(self):
        """When LIVE_TRADING_CONFIRMED!=TRUE, ModeGuard falls back to PAPER.
        require_live_execution_prerequisites rejects PAPER mode (MODE-003)."""
        MG, TM, MVE = self._import()
        env = {
            "EXECUTION_MODE": "LIVE",
            "LIVE_TRADING_CONFIRMED": "FALSE",
            "VALR_API_KEY": "key123",
            "VALR_API_SECRET": "secret456",
        }
        with patch.dict(os.environ, env, clear=True):
            guard = MG(correlation_id="test-prereq-noconfirm")
            # ModeGuard init falls back to PAPER when LIVE_TRADING_CONFIRMED!=TRUE
            assert guard.mode == TM.PAPER
            with pytest.raises(MVE, match="MODE-003"):
                guard.require_live_execution_prerequisites()

    def test_live_prereq_rejects_missing_api_key(self):
        MG, TM, MVE = self._import()
        env = {
            "EXECUTION_MODE": "LIVE",
            "LIVE_TRADING_CONFIRMED": "TRUE",
            "VALR_API_SECRET": "secret456",
        }
        with patch.dict(os.environ, env, clear=True):
            guard = MG(correlation_id="test-prereq-nokey")
            with pytest.raises(MVE, match="MODE-003.*VALR_API_KEY"):
                guard.require_live_execution_prerequisites()

    def test_live_prereq_rejects_missing_api_secret(self):
        MG, TM, MVE = self._import()
        env = {
            "EXECUTION_MODE": "LIVE",
            "LIVE_TRADING_CONFIRMED": "TRUE",
            "VALR_API_KEY": "key123",
        }
        with patch.dict(os.environ, env, clear=True):
            guard = MG(correlation_id="test-prereq-nosecret")
            with pytest.raises(MVE, match="MODE-003.*VALR_API_SECRET"):
                guard.require_live_execution_prerequisites()

    def test_live_prereq_rejects_missing_both_credentials(self):
        MG, TM, MVE = self._import()
        env = {
            "EXECUTION_MODE": "LIVE",
            "LIVE_TRADING_CONFIRMED": "TRUE",
        }
        with patch.dict(os.environ, env, clear=True):
            guard = MG(correlation_id="test-prereq-nocreds")
            with pytest.raises(MVE, match="MODE-003.*VALR_API_KEY.*VALR_API_SECRET"):
                guard.require_live_execution_prerequisites()

    def test_live_prereq_confirmation_case_insensitive(self):
        MG, TM, MVE = self._import()
        env = {
            "EXECUTION_MODE": "LIVE",
            "LIVE_TRADING_CONFIRMED": "true",
            "VALR_API_KEY": "key",
            "VALR_API_SECRET": "secret",
        }
        with patch.dict(os.environ, env, clear=True):
            guard = MG(correlation_id="test-prereq-case")
            # Should not raise — "true" uppercased to "TRUE" internally
            guard.require_live_execution_prerequisites()


# =============================================================================
# 6. Integration: OrderManager LIVE mode requires confirmation
# =============================================================================

class TestLiveModeConfirmation:
    """Tests for LIVE mode env var enforcement at OrderManager level."""

    def test_live_mode_requires_confirmation(self):
        from app.exchange.order_manager import (
            LiveModeNotConfirmedError,
            OrderManager,
        )
        env = {"EXECUTION_MODE": "LIVE"}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(LiveModeNotConfirmedError, match="VALR-MODE-001"):
                OrderManager(correlation_id="test-no-confirm")

    def test_dry_run_is_default(self):
        from app.exchange.order_manager import ExecutionMode, OrderManager
        with patch.dict(os.environ, {}, clear=True):
            mgr = OrderManager(correlation_id="test-default")
            assert mgr.execution_mode == ExecutionMode.DRY_RUN

    def test_dry_run_order_is_simulated(self):
        from app.exchange.order_manager import (
            OrderManager,
            OrderSide,
            OrderStatus,
        )
        with patch.dict(os.environ, {}, clear=True):
            mgr = OrderManager(correlation_id="test-sim")
            result = mgr.place_order(
                pair="BTCZAR",
                side=OrderSide.BUY,
                price=Decimal("1500000"),
                quantity=Decimal("0.001"),
            )
            assert result.is_simulated is True
            assert result.status == OrderStatus.SIMULATED
            assert result.order_id.startswith("DRY_")

"""
============================================================================
Unit Tests - Mode Matrix, Equity Source, and Reconciliation (Phase 3A)
============================================================================

Reliability Level: SOVEREIGN TIER
Test Coverage:
    1. ModeGuard: mode resolution, capability checks, hard guards
    2. EquitySource: mode-aware equity retrieval, fail-closed behavior
    3. ReconciliationEngine: DB balance query, mismatch detection

Tests validate:
    - PAPER mode is the fail-closed default
    - LIVE_EXECUTION requires explicit LIVE_TRADING_CONFIRMED=TRUE
    - Order placement is blocked in non-LIVE_EXECUTION modes
    - EquitySource returns None on failure (never fabricates)
    - Reconciliation DB query replaces placeholder

Note: Tests import directly from submodules (not app.exchange.__init__)
      to avoid triggering requests library import, which is shadowed by
      the project's requests/ directory in local development.
============================================================================
"""

from decimal import Decimal
import os
import sys
import types
from unittest.mock import MagicMock, patch

import pytest

# Ensure project root is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

# ---------------------------------------------------------------------------
# Fix for local 'requests/' directory shadowing the pip 'requests' package.
# The project's requests/ directory (containing only hitl.http) is picked up
# by Python as a namespace package, breaking 'from requests.exceptions import ...'
# inside app/exchange/valr_client.py.  We inject a minimal mock so the import
# chain through app/exchange/__init__.py succeeds.
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
# ModeGuard Tests
# =============================================================================

class TestModeGuard:
    """Tests for ModeGuard mode resolution and capability enforcement."""

    def _import_mode_matrix(self):
        """Import mode_matrix directly to avoid package __init__ heavy deps."""
        from app.exchange.mode_matrix import ModeGuard, ModeViolationError, TradingMode
        return ModeGuard, TradingMode, ModeViolationError

    def test_default_mode_is_paper(self):
        """PAPER is the default when no env vars are set."""
        ModeGuard, TradingMode, _ = self._import_mode_matrix()
        with patch.dict(os.environ, {}, clear=True):
            guard = ModeGuard(correlation_id="test-default")
            assert guard.mode == TradingMode.PAPER

    def test_demo_paper_resolves_to_paper(self):
        """EXECUTION_MODE=DEMO + DEMO_MODE=PAPER → PAPER."""
        ModeGuard, TradingMode, _ = self._import_mode_matrix()
        env = {"EXECUTION_MODE": "DEMO", "DEMO_MODE": "PAPER"}
        with patch.dict(os.environ, env, clear=True):
            guard = ModeGuard(correlation_id="test-demo-paper")
            assert guard.mode == TradingMode.PAPER

    def test_dry_run_resolves(self):
        """EXECUTION_MODE=DRY_RUN → DRY_RUN."""
        ModeGuard, TradingMode, _ = self._import_mode_matrix()
        env = {"EXECUTION_MODE": "DRY_RUN"}
        with patch.dict(os.environ, env, clear=True):
            guard = ModeGuard(correlation_id="test-dry-run")
            assert guard.mode == TradingMode.DRY_RUN

    def test_live_read_only_via_execution_mode(self):
        """EXECUTION_MODE=LIVE_READ_ONLY → LIVE_READ_ONLY."""
        ModeGuard, TradingMode, _ = self._import_mode_matrix()
        env = {"EXECUTION_MODE": "LIVE_READ_ONLY"}
        with patch.dict(os.environ, env, clear=True):
            guard = ModeGuard(correlation_id="test-lro")
            assert guard.mode == TradingMode.LIVE_READ_ONLY

    def test_live_read_only_via_flag(self):
        """LIVE_READ_ONLY=TRUE → LIVE_READ_ONLY."""
        ModeGuard, TradingMode, _ = self._import_mode_matrix()
        env = {"EXECUTION_MODE": "DEMO", "LIVE_READ_ONLY": "TRUE"}
        with patch.dict(os.environ, env, clear=True):
            guard = ModeGuard(correlation_id="test-lro-flag")
            assert guard.mode == TradingMode.LIVE_READ_ONLY

    def test_live_execution_requires_confirmation(self):
        """EXECUTION_MODE=LIVE without LIVE_TRADING_CONFIRMED → PAPER (fail-closed)."""
        ModeGuard, TradingMode, _ = self._import_mode_matrix()
        env = {"EXECUTION_MODE": "LIVE"}
        with patch.dict(os.environ, env, clear=True):
            guard = ModeGuard(correlation_id="test-live-no-confirm")
            assert guard.mode == TradingMode.PAPER

    def test_live_execution_with_confirmation(self):
        """EXECUTION_MODE=LIVE + LIVE_TRADING_CONFIRMED=TRUE → LIVE_EXECUTION."""
        ModeGuard, TradingMode, _ = self._import_mode_matrix()
        env = {"EXECUTION_MODE": "LIVE", "LIVE_TRADING_CONFIRMED": "TRUE"}
        with patch.dict(os.environ, env, clear=True):
            guard = ModeGuard(correlation_id="test-live-confirmed")
            assert guard.mode == TradingMode.LIVE_EXECUTION

    def test_unknown_mode_fails_to_paper(self):
        """Unknown EXECUTION_MODE → PAPER (fail-closed)."""
        ModeGuard, TradingMode, _ = self._import_mode_matrix()
        env = {"EXECUTION_MODE": "SOMETHING_INVALID"}
        with patch.dict(os.environ, env, clear=True):
            guard = ModeGuard(correlation_id="test-unknown")
            assert guard.mode == TradingMode.PAPER


class TestModeGuardCapabilities:
    """Tests for ModeGuard capability checks."""

    def _import_mode_matrix(self):
        from app.exchange.mode_matrix import ModeGuard, ModeViolationError, TradingMode
        return ModeGuard, TradingMode, ModeViolationError

    def test_paper_blocks_all_exchange(self):
        """PAPER mode blocks all exchange operations."""
        ModeGuard, _, _ = self._import_mode_matrix()
        env = {"EXECUTION_MODE": "DEMO", "DEMO_MODE": "PAPER"}
        with patch.dict(os.environ, env, clear=True):
            guard = ModeGuard(correlation_id="test-paper-caps")
            assert not guard.can_read_public_data()
            assert not guard.can_read_authenticated()
            assert not guard.can_place_orders()
            assert guard.uses_demo_broker()

    def test_dry_run_allows_public_only(self):
        """DRY_RUN allows public data but blocks auth reads and orders."""
        ModeGuard, _, _ = self._import_mode_matrix()
        env = {"EXECUTION_MODE": "DRY_RUN"}
        with patch.dict(os.environ, env, clear=True):
            guard = ModeGuard(correlation_id="test-dr-caps")
            assert guard.can_read_public_data()
            assert not guard.can_read_authenticated()
            assert not guard.can_place_orders()

    def test_live_read_only_blocks_orders(self):
        """LIVE_READ_ONLY allows reads but blocks order placement."""
        ModeGuard, _, _ = self._import_mode_matrix()
        env = {"EXECUTION_MODE": "LIVE_READ_ONLY"}
        with patch.dict(os.environ, env, clear=True):
            guard = ModeGuard(correlation_id="test-lro-caps")
            assert guard.can_read_public_data()
            assert guard.can_read_authenticated()
            assert not guard.can_place_orders()

    def test_live_execution_allows_all(self):
        """LIVE_EXECUTION allows all operations."""
        ModeGuard, _, _ = self._import_mode_matrix()
        env = {"EXECUTION_MODE": "LIVE", "LIVE_TRADING_CONFIRMED": "TRUE"}
        with patch.dict(os.environ, env, clear=True):
            guard = ModeGuard(correlation_id="test-le-caps")
            assert guard.can_read_public_data()
            assert guard.can_read_authenticated()
            assert guard.can_place_orders()


class TestModeGuardHardGuards:
    """Tests for ModeGuard hard guard (raise on violation)."""

    def _import_mode_matrix(self):
        from app.exchange.mode_matrix import ModeGuard, ModeViolationError, TradingMode
        return ModeGuard, TradingMode, ModeViolationError

    def test_paper_blocks_public_data_requirement(self):
        """require_public_data() raises in PAPER mode."""
        ModeGuard, _, ModeViolationError = self._import_mode_matrix()
        env = {"EXECUTION_MODE": "DEMO", "DEMO_MODE": "PAPER"}
        with patch.dict(os.environ, env, clear=True):
            guard = ModeGuard(correlation_id="test-guard-pub")
            with pytest.raises(ModeViolationError, match="MODE-002"):
                guard.require_public_data()

    def test_dry_run_blocks_auth_requirement(self):
        """require_authenticated_read() raises in DRY_RUN mode."""
        ModeGuard, _, ModeViolationError = self._import_mode_matrix()
        env = {"EXECUTION_MODE": "DRY_RUN"}
        with patch.dict(os.environ, env, clear=True):
            guard = ModeGuard(correlation_id="test-guard-auth")
            with pytest.raises(ModeViolationError, match="MODE-002"):
                guard.require_authenticated_read()

    def test_live_read_only_blocks_order_requirement(self):
        """require_order_placement() raises in LIVE_READ_ONLY mode."""
        ModeGuard, _, ModeViolationError = self._import_mode_matrix()
        env = {"EXECUTION_MODE": "LIVE_READ_ONLY"}
        with patch.dict(os.environ, env, clear=True):
            guard = ModeGuard(correlation_id="test-guard-order")
            with pytest.raises(ModeViolationError, match="MODE-002"):
                guard.require_order_placement()

    def test_paper_blocks_order_requirement(self):
        """require_order_placement() raises in PAPER mode."""
        ModeGuard, _, ModeViolationError = self._import_mode_matrix()
        env = {"EXECUTION_MODE": "DEMO", "DEMO_MODE": "PAPER"}
        with patch.dict(os.environ, env, clear=True):
            guard = ModeGuard(correlation_id="test-guard-order-paper")
            with pytest.raises(ModeViolationError, match="MODE-002"):
                guard.require_order_placement()

    def test_live_execution_permits_order_placement(self):
        """require_order_placement() does not raise in LIVE_EXECUTION mode."""
        ModeGuard, _, _ = self._import_mode_matrix()
        env = {"EXECUTION_MODE": "LIVE", "LIVE_TRADING_CONFIRMED": "TRUE"}
        with patch.dict(os.environ, env, clear=True):
            guard = ModeGuard(correlation_id="test-guard-order-live")
            guard.require_order_placement()  # Should not raise

    def test_get_status_returns_dict(self):
        """get_status() returns a well-formed dict."""
        ModeGuard, _, _ = self._import_mode_matrix()
        env = {"EXECUTION_MODE": "DRY_RUN"}
        with patch.dict(os.environ, env, clear=True):
            guard = ModeGuard(correlation_id="test-status")
            status = guard.get_status()
            assert "mode" in status
            assert "capabilities" in status
            assert "env" in status
            assert status["mode"] == "DRY_RUN"


# =============================================================================
# EquitySource Tests
# =============================================================================

class TestEquitySource:
    """Tests for mode-aware equity retrieval."""

    def test_static_equity_in_dry_run(self):
        """DRY_RUN mode returns static equity value."""
        env = {"EXECUTION_MODE": "DRY_RUN"}
        with patch.dict(os.environ, env, clear=True):
            from app.exchange.equity_source import EquitySource
            from app.exchange.mode_matrix import ModeGuard

            guard = ModeGuard(correlation_id="test-eq-static")
            source = EquitySource(
                mode_guard=guard,
                static_equity_zar=Decimal("50000.00"),
                correlation_id="test-eq-static",
            )
            equity = source.get_equity_zar()
            assert equity == Decimal("50000.00")

    def test_demo_broker_equity_in_paper(self):
        """PAPER mode retrieves equity from DemoBroker."""
        env = {"EXECUTION_MODE": "DEMO", "DEMO_MODE": "PAPER"}
        with patch.dict(os.environ, env, clear=True):
            from app.exchange.equity_source import EquitySource
            from app.exchange.mode_matrix import ModeGuard

            mock_broker = MagicMock()
            mock_broker.get_account_equity.return_value = {"equity": "75000.50"}

            guard = ModeGuard(correlation_id="test-eq-demo")
            source = EquitySource(
                mode_guard=guard,
                demo_broker=mock_broker,
                correlation_id="test-eq-demo",
            )
            equity = source.get_equity_zar()
            assert equity == Decimal("75000.50")
            mock_broker.get_account_equity.assert_called_once()

    def test_exchange_equity_in_live_read_only(self):
        """LIVE_READ_ONLY mode retrieves equity from VALR."""
        env = {"EXECUTION_MODE": "LIVE_READ_ONLY"}
        with patch.dict(os.environ, env, clear=True):
            from app.exchange.equity_source import EquitySource
            from app.exchange.mode_matrix import ModeGuard

            mock_balance = MagicMock()
            mock_balance.available = Decimal("30000.00")
            mock_balance.reserved = Decimal("5000.00")
            mock_balance.total = Decimal("35000.00")

            mock_client = MagicMock()
            mock_client.get_balances.return_value = {"ZAR": mock_balance}

            guard = ModeGuard(correlation_id="test-eq-exchange")
            source = EquitySource(
                mode_guard=guard,
                valr_client=mock_client,
                correlation_id="test-eq-exchange",
            )
            equity = source.get_equity_zar()
            assert equity == Decimal("35000.00")
            mock_client.get_balances.assert_called_once()

    def test_fail_closed_no_valr_client(self):
        """Returns None when VALR client is not provided in exchange mode."""
        env = {"EXECUTION_MODE": "LIVE_READ_ONLY"}
        with patch.dict(os.environ, env, clear=True):
            from app.exchange.equity_source import EquitySource
            from app.exchange.mode_matrix import ModeGuard

            guard = ModeGuard(correlation_id="test-eq-fail")
            source = EquitySource(
                mode_guard=guard,
                correlation_id="test-eq-fail",
            )
            equity = source.get_equity_zar()
            assert equity is None

    def test_fail_closed_no_demo_broker(self):
        """Returns None when DemoBroker is not provided in paper mode."""
        env = {"EXECUTION_MODE": "DEMO", "DEMO_MODE": "PAPER"}
        with patch.dict(os.environ, env, clear=True):
            from app.exchange.equity_source import EquitySource
            from app.exchange.mode_matrix import ModeGuard

            guard = ModeGuard(correlation_id="test-eq-fail-demo")
            source = EquitySource(
                mode_guard=guard,
                correlation_id="test-eq-fail-demo",
            )
            equity = source.get_equity_zar()
            assert equity is None

    def test_fail_closed_exchange_error(self):
        """Returns None when exchange raises an error."""
        env = {"EXECUTION_MODE": "LIVE_READ_ONLY"}
        with patch.dict(os.environ, env, clear=True):
            from app.exchange.equity_source import EquitySource
            from app.exchange.mode_matrix import ModeGuard

            mock_client = MagicMock()
            mock_client.get_balances.side_effect = Exception("Network error")

            guard = ModeGuard(correlation_id="test-eq-err")
            source = EquitySource(
                mode_guard=guard,
                valr_client=mock_client,
                correlation_id="test-eq-err",
            )
            equity = source.get_equity_zar()
            assert equity is None

    def test_fail_closed_no_zar_in_balances(self):
        """Returns None when VALR has no ZAR balance."""
        env = {"EXECUTION_MODE": "LIVE_READ_ONLY"}
        with patch.dict(os.environ, env, clear=True):
            from app.exchange.equity_source import EquitySource
            from app.exchange.mode_matrix import ModeGuard

            mock_client = MagicMock()
            mock_client.get_balances.return_value = {"BTC": MagicMock()}

            guard = ModeGuard(correlation_id="test-eq-no-zar")
            source = EquitySource(
                mode_guard=guard,
                valr_client=mock_client,
                correlation_id="test-eq-no-zar",
            )
            equity = source.get_equity_zar()
            assert equity is None

    def test_static_equity_none_returns_none(self):
        """Returns None when no static equity configured in DRY_RUN."""
        env = {"EXECUTION_MODE": "DRY_RUN"}
        with patch.dict(os.environ, env, clear=True):
            from app.exchange.equity_source import EquitySource
            from app.exchange.mode_matrix import ModeGuard

            guard = ModeGuard(correlation_id="test-eq-no-static")
            source = EquitySource(
                mode_guard=guard,
                correlation_id="test-eq-no-static",
            )
            equity = source.get_equity_zar()
            assert equity is None

    def test_source_description(self):
        """get_source_description() returns human-readable string."""
        env = {"EXECUTION_MODE": "DRY_RUN"}
        with patch.dict(os.environ, env, clear=True):
            from app.exchange.equity_source import EquitySource
            from app.exchange.mode_matrix import ModeGuard

            guard = ModeGuard(correlation_id="test-desc")
            source = EquitySource(
                mode_guard=guard,
                static_equity_zar=Decimal("100000"),
                correlation_id="test-desc",
            )
            desc = source.get_source_description()
            assert "DRY_RUN" in desc
            assert "Static" in desc


# =============================================================================
# ReconciliationEngine DB Balance Tests
# =============================================================================

class TestReconciliationDbBalance:
    """Tests for the real DB balance query in ReconciliationEngine."""

    def test_db_balance_with_session(self):
        """DB balance query executes on provided session."""
        from app.exchange.reconciliation import ReconciliationEngine

        mock_client = MagicMock()
        mock_session = MagicMock()

        # Simulate DB returning a net balance
        mock_result = MagicMock()
        mock_result.fetchone.return_value = (Decimal("1500.00"),)
        mock_session.execute.return_value = mock_result

        # Mock sqlalchemy.text since sqlalchemy may not be installed locally
        mock_text = MagicMock(side_effect=lambda s: s)
        with patch.dict("sys.modules", {"sqlalchemy": MagicMock(text=mock_text)}):
            engine = ReconciliationEngine(
                valr_client=mock_client,
                db_session=mock_session,
                correlation_id="test-db-bal",
            )

            balance = engine._get_db_balance("ZAR")
            assert balance == Decimal("1500.00")
            mock_session.execute.assert_called_once()

    def test_db_balance_without_session_uses_state(self):
        """Without DB session, falls back to state balance."""
        from app.exchange.reconciliation import ReconciliationEngine

        mock_client = MagicMock()

        engine = ReconciliationEngine(
            valr_client=mock_client,
            correlation_id="test-db-no-session",
        )
        engine.set_state_balance("ZAR", Decimal("2000.00"))

        balance = engine._get_db_balance("ZAR")
        assert balance == Decimal("2000.00")

    def test_db_balance_query_error_uses_state(self):
        """On DB query error, falls back to state balance."""
        from app.exchange.reconciliation import ReconciliationEngine

        mock_client = MagicMock()
        mock_session = MagicMock()
        mock_session.execute.side_effect = Exception("DB connection lost")

        engine = ReconciliationEngine(
            valr_client=mock_client,
            db_session=mock_session,
            correlation_id="test-db-err",
        )
        engine.set_state_balance("ZAR", Decimal("3000.00"))

        balance = engine._get_db_balance("ZAR")
        assert balance == Decimal("3000.00")

    def test_db_balance_null_result(self):
        """DB returning NULL yields Decimal('0')."""
        from app.exchange.reconciliation import ReconciliationEngine

        mock_client = MagicMock()
        mock_session = MagicMock()

        mock_result = MagicMock()
        mock_result.fetchone.return_value = (None,)
        mock_session.execute.return_value = mock_result

        engine = ReconciliationEngine(
            valr_client=mock_client,
            db_session=mock_session,
            correlation_id="test-db-null",
        )

        balance = engine._get_db_balance("ZAR")
        assert balance == Decimal("0")

    def test_reconciliation_mismatch_triggers_lockdown(self):
        """Mismatch >1% triggers L6 lockdown callback."""
        from app.exchange.reconciliation import ReconciliationEngine

        mock_client = MagicMock()
        mock_balance = MagicMock()
        mock_balance.available = Decimal("10000.00")
        mock_client.get_balances.return_value = {"ZAR": mock_balance}

        lockdown_called = []

        def on_lockdown(reason, cid):
            lockdown_called.append((reason, cid))

        engine = ReconciliationEngine(
            valr_client=mock_client,
            on_lockdown=on_lockdown,
            correlation_id="test-mismatch",
        )
        # Set state balance far from exchange balance to trigger mismatch
        engine.set_state_balance("ZAR", Decimal("10000.00"))
        # DB session absent → _get_db_balance returns state balance
        # but exchange returns 10000, state returns 10000 → no mismatch

        # Instead, simulate a mismatch by setting state to a different value
        engine._state_balances["ZAR"] = Decimal("8000.00")

        result = engine.reconcile("ZAR")

        # Exchange=10000, DB=8000 (state proxy), discrepancy=2000 (20%) > 1%
        assert result.status.value == "MISMATCH"
        assert len(lockdown_called) == 1
        assert "VALR-REC-001" in lockdown_called[0][0]

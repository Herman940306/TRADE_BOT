# ============================================================================
# Project Autonomous Alpha v1.8.0
# Mode Matrix - Centralized Execution Mode Management
# ============================================================================
#
# Reliability Level: SOVEREIGN TIER (Mission-Critical)
# Purpose: Enforces strict mode boundaries for all trading operations
#
# SOVEREIGN MANDATE:
#   - PAPER is the only safe default
#   - LIVE_EXECUTION requires explicit confirmation + Guardian unlock
#   - LIVE_READ_ONLY permits exchange reads but blocks all order placement
#   - All mode transitions are logged with audit trail
#   - Fail-closed: any ambiguity defaults to PAPER
#
# Mode Progression:
#   PAPER → DRY_RUN → LIVE_READ_ONLY → LIVE_EXECUTION
#
# Error Codes:
#   - MODE-001: Invalid mode transition
#   - MODE-002: Operation blocked by current mode
#   - MODE-003: LIVE_EXECUTION not confirmed
#   - MODE-004: Mode configuration invalid
#
# ============================================================================

from enum import Enum
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


# ============================================================================
# Mode Definitions
# ============================================================================

class TradingMode(Enum):
    """
    Trading execution mode with strict capability boundaries.

    PAPER:          Internal simulation only. No exchange connectivity.
    DRY_RUN:        Synthetic order simulation. Public exchange data allowed.
    LIVE_READ_ONLY: Authenticated exchange reads. No order placement.
    LIVE_EXECUTION: Real order placement. Requires explicit confirmation.
    """
    PAPER = "PAPER"
    DRY_RUN = "DRY_RUN"
    LIVE_READ_ONLY = "LIVE_READ_ONLY"
    LIVE_EXECUTION = "LIVE_EXECUTION"


# ============================================================================
# Capability Flags
# ============================================================================

# What each mode is permitted to do
MODE_CAPABILITIES = {
    TradingMode.PAPER: {
        "exchange_public_data": False,
        "exchange_authenticated_reads": False,
        "exchange_order_placement": False,
        "uses_demo_broker": True,
        "requires_valr_credentials": False,
        "equity_source": "DEMO_BROKER",
    },
    TradingMode.DRY_RUN: {
        "exchange_public_data": True,
        "exchange_authenticated_reads": False,
        "exchange_order_placement": False,
        "uses_demo_broker": False,
        "requires_valr_credentials": False,
        "equity_source": "STATIC",
    },
    TradingMode.LIVE_READ_ONLY: {
        "exchange_public_data": True,
        "exchange_authenticated_reads": True,
        "exchange_order_placement": False,
        "uses_demo_broker": False,
        "requires_valr_credentials": True,
        "equity_source": "EXCHANGE",
    },
    TradingMode.LIVE_EXECUTION: {
        "exchange_public_data": True,
        "exchange_authenticated_reads": True,
        "exchange_order_placement": True,
        "uses_demo_broker": False,
        "requires_valr_credentials": True,
        "equity_source": "EXCHANGE",
    },
}


# ============================================================================
# Mode Guard
# ============================================================================

class ModeViolationError(Exception):
    """Raised when an operation violates the current mode boundaries."""


class ModeGuard:
    """
    Centralized mode enforcement for all trading operations.

    Reliability Level: SOVEREIGN TIER
    Fail-Closed: Defaults to PAPER on any configuration ambiguity
    Audit Trail: All mode checks logged with correlation_id

    Example Usage:
        guard = ModeGuard(correlation_id="abc-123")
        if guard.can_read_exchange():
            balances = valr_client.get_balances()

        guard.require_order_placement(correlation_id="abc-123")
        # Raises ModeViolationError if not LIVE_EXECUTION
    """

    def __init__(self, correlation_id: Optional[str] = None):
        """
        Initialize ModeGuard from environment variables.

        Fail-closed: defaults to PAPER on any ambiguity.

        Args:
            correlation_id: Audit trail identifier
        """
        self.correlation_id = correlation_id
        self._mode = self._resolve_mode()
        self._capabilities = MODE_CAPABILITIES[self._mode]

        logger.info(
            f"[MODE] ModeGuard initialized | mode={self._mode.value} | "
            f"order_placement={self._capabilities['exchange_order_placement']} | "
            f"correlation_id={correlation_id}"
        )

    @property
    def mode(self) -> TradingMode:
        """Current trading mode."""
        return self._mode

    @property
    def equity_source(self) -> str:
        """Equity source for current mode (DEMO_BROKER, STATIC, or EXCHANGE)."""
        return self._capabilities["equity_source"]

    def _resolve_mode(self) -> TradingMode:
        """
        Determine trading mode from environment variables.

        Maps legacy EXECUTION_MODE/DEMO_MODE env vars to TradingMode.
        Fail-closed: returns PAPER on any ambiguity.

        Returns:
            TradingMode resolved from environment
        """
        execution_mode = os.getenv("EXECUTION_MODE", "DEMO").upper().strip()
        demo_mode = os.getenv("DEMO_MODE", "PAPER").upper().strip()
        live_confirmed = os.getenv("LIVE_TRADING_CONFIRMED", "").upper().strip()
        live_read_only = os.getenv("LIVE_READ_ONLY", "").upper().strip()

        # LIVE path
        if execution_mode == "LIVE":
            if live_confirmed == "TRUE":
                logger.critical(
                    f"[MODE-003] LIVE_EXECUTION mode resolved | "
                    f"correlation_id={self.correlation_id}"
                )
                return TradingMode.LIVE_EXECUTION
            logger.warning(
                f"[MODE-003] EXECUTION_MODE=LIVE but LIVE_TRADING_CONFIRMED "
                f"not TRUE — falling back to PAPER | "
                f"correlation_id={self.correlation_id}"
            )
            return TradingMode.PAPER

        # LIVE_READ_ONLY path
        if execution_mode == "LIVE_READ_ONLY" or live_read_only == "TRUE":
            return TradingMode.LIVE_READ_ONLY

        # DRY_RUN path
        if execution_mode == "DRY_RUN":
            return TradingMode.DRY_RUN

        # DEMO path (default)
        if execution_mode == "DEMO":
            if demo_mode == "PAPER" or demo_mode not in ("OANDA_PRACTICE", "BINANCE_TESTNET"):
                return TradingMode.PAPER
            return TradingMode.PAPER

        # Unknown mode — fail closed to PAPER
        logger.warning(
            f"[MODE-004] Unknown EXECUTION_MODE='{execution_mode}' — "
            f"fail-closed to PAPER | correlation_id={self.correlation_id}"
        )
        return TradingMode.PAPER

    # ========================================================================
    # Capability Checks
    # ========================================================================

    def can_read_public_data(self) -> bool:
        """Check if public exchange data is available in current mode."""
        return self._capabilities["exchange_public_data"]

    def can_read_authenticated(self) -> bool:
        """Check if authenticated exchange reads are available."""
        return self._capabilities["exchange_authenticated_reads"]

    def can_place_orders(self) -> bool:
        """Check if order placement is permitted in current mode."""
        return self._capabilities["exchange_order_placement"]

    def uses_demo_broker(self) -> bool:
        """Check if current mode uses DemoBroker."""
        return self._capabilities["uses_demo_broker"]

    def requires_credentials(self) -> bool:
        """Check if current mode requires VALR API credentials."""
        return self._capabilities["requires_valr_credentials"]

    # ========================================================================
    # Hard Guards (raise on violation)
    # ========================================================================

    def require_public_data(self, correlation_id: Optional[str] = None) -> None:
        """
        Assert public exchange data is available. Raises on violation.

        Args:
            correlation_id: Audit trail identifier

        Raises:
            ModeViolationError: If public data not available in current mode
        """
        if not self.can_read_public_data():
            cid = correlation_id or self.correlation_id
            logger.warning(
                f"[MODE-002] Public data blocked | mode={self._mode.value} | "
                f"correlation_id={cid}"
            )
            raise ModeViolationError(
                f"MODE-002: Public exchange data not available in "
                f"{self._mode.value} mode"
            )

    def require_authenticated_read(self, correlation_id: Optional[str] = None) -> None:
        """
        Assert authenticated exchange reads are available. Raises on violation.

        Args:
            correlation_id: Audit trail identifier

        Raises:
            ModeViolationError: If authenticated reads not available
        """
        if not self.can_read_authenticated():
            cid = correlation_id or self.correlation_id
            logger.warning(
                f"[MODE-002] Authenticated read blocked | "
                f"mode={self._mode.value} | correlation_id={cid}"
            )
            raise ModeViolationError(
                f"MODE-002: Authenticated exchange reads not available in "
                f"{self._mode.value} mode"
            )

    def require_order_placement(self, correlation_id: Optional[str] = None) -> None:
        """
        Assert order placement is permitted. Raises on violation.

        Args:
            correlation_id: Audit trail identifier

        Raises:
            ModeViolationError: If order placement not permitted
        """
        if not self.can_place_orders():
            cid = correlation_id or self.correlation_id
            logger.warning(
                f"[MODE-002] Order placement blocked | "
                f"mode={self._mode.value} | correlation_id={cid}"
            )
            raise ModeViolationError(
                f"MODE-002: Order placement not available in "
                f"{self._mode.value} mode"
            )

    def require_live_execution_prerequisites(
        self, correlation_id: Optional[str] = None
    ) -> None:
        """
        Assert ALL prerequisites for live order placement are met.

        Checks:
            1. Mode is LIVE_EXECUTION
            2. LIVE_TRADING_CONFIRMED=TRUE is set
            3. VALR_API_KEY is present
            4. VALR_API_SECRET is present
            5. EXECUTION_MODE=LIVE is set

        Raises:
            ModeViolationError: If any prerequisite is missing
        """
        cid = correlation_id or self.correlation_id

        # 1. Mode must be LIVE_EXECUTION
        if self._mode != TradingMode.LIVE_EXECUTION:
            raise ModeViolationError(
                f"MODE-003: Live execution requires LIVE_EXECUTION mode, "
                f"current mode is {self._mode.value}"
            )

        # 2. LIVE_TRADING_CONFIRMED must be TRUE
        confirmed = os.getenv("LIVE_TRADING_CONFIRMED", "").upper().strip()
        if confirmed != "TRUE":
            logger.critical(
                f"[MODE-003] LIVE_TRADING_CONFIRMED not TRUE | "
                f"value='{confirmed}' | correlation_id={cid}"
            )
            raise ModeViolationError(
                "MODE-003: LIVE_TRADING_CONFIRMED=TRUE required"
            )

        # 3+4. Credentials must be present
        api_key = os.getenv("VALR_API_KEY", "")
        api_secret = os.getenv("VALR_API_SECRET", "")
        if not api_key or not api_secret:
            missing = []
            if not api_key:
                missing.append("VALR_API_KEY")
            if not api_secret:
                missing.append("VALR_API_SECRET")
            logger.critical(
                f"[MODE-003] Credentials missing for LIVE_EXECUTION | "
                f"missing={missing} | correlation_id={cid}"
            )
            raise ModeViolationError(
                f"MODE-003: Missing credentials: {', '.join(missing)}"
            )

        logger.info(
            f"[MODE] Live execution prerequisites verified | "
            f"correlation_id={cid}"
        )

    def get_status(self) -> dict:
        """
        Return current mode status for diagnostics and API exposure.

        Returns:
            dict with mode, capabilities, and configuration source
        """
        return {
            "mode": self._mode.value,
            "capabilities": {
                k: v for k, v in self._capabilities.items()
            },
            "env": {
                "EXECUTION_MODE": os.getenv("EXECUTION_MODE", "DEMO"),
                "DEMO_MODE": os.getenv("DEMO_MODE", "PAPER"),
                "LIVE_TRADING_CONFIRMED": os.getenv("LIVE_TRADING_CONFIRMED", "FALSE"),
                "LIVE_READ_ONLY": os.getenv("LIVE_READ_ONLY", "FALSE"),
            },
            "correlation_id": self.correlation_id,
        }

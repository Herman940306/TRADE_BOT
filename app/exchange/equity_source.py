# ============================================================================
# Project Autonomous Alpha v1.8.0
# Equity Source - Mode-Aware Equity Retrieval
# ============================================================================
#
# Reliability Level: SOVEREIGN TIER (Mission-Critical)
# Purpose: Provides mode-aware equity values for Guardian and RiskManager
#
# SOVEREIGN MANDATE:
#   - PAPER mode: equity from DemoBroker
#   - DRY_RUN mode: equity from ZAR_FLOOR env var (static)
#   - LIVE_READ_ONLY / LIVE_EXECUTION: equity from VALR exchange
#   - Fail-closed: returns None on any retrieval failure (caller decides)
#   - All values are Decimal (zero-float mandate)
#
# Error Codes:
#   - EQUITY-001: Exchange equity retrieval failed
#   - EQUITY-002: DemoBroker equity retrieval failed
#   - EQUITY-003: No equity source configured for mode
#
# ============================================================================

from decimal import ROUND_HALF_EVEN, Decimal
import logging
from typing import Any, Optional

from app.exchange.mode_matrix import ModeGuard, TradingMode

logger = logging.getLogger(__name__)

# Decimal precision for ZAR equity
PRECISION_EQUITY = Decimal("0.01")


class EquitySource:
    """
    Mode-aware equity retrieval for Guardian and RiskManager.

    Reliability Level: SOVEREIGN TIER
    Fail-Closed: Returns None on retrieval failure (never fabricates a number)
    Decimal Integrity: All values are Decimal with ROUND_HALF_EVEN

    Example Usage:
        source = EquitySource(
            mode_guard=guard,
            valr_client=client,
            demo_broker=broker,
            correlation_id="abc-123"
        )
        equity = source.get_equity_zar()
        if equity is None:
            # Handle retrieval failure — fail closed
            pass
    """

    def __init__(
        self,
        mode_guard: ModeGuard,
        valr_client: Optional[Any] = None,
        demo_broker: Optional[Any] = None,
        static_equity_zar: Optional[Decimal] = None,
        correlation_id: Optional[str] = None,
    ):
        """
        Initialize EquitySource.

        Args:
            mode_guard: ModeGuard for mode-aware behavior
            valr_client: VALRClient instance for live modes
            demo_broker: DemoBroker instance for PAPER mode
            static_equity_zar: Static equity for DRY_RUN mode (from env)
            correlation_id: Audit trail identifier
        """
        self.mode_guard = mode_guard
        self._valr_client = valr_client
        self._demo_broker = demo_broker
        self._static_equity = static_equity_zar
        self.correlation_id = correlation_id

        logger.info(
            f"[EQUITY] EquitySource initialized | "
            f"mode={mode_guard.mode.value} | "
            f"source={mode_guard.equity_source} | "
            f"valr_client={'set' if valr_client else 'none'} | "
            f"demo_broker={'set' if demo_broker else 'none'} | "
            f"static_equity={static_equity_zar} | "
            f"correlation_id={correlation_id}"
        )

    def get_equity_zar(self, correlation_id: Optional[str] = None) -> Optional[Decimal]:
        """
        Retrieve current ZAR equity from the appropriate source.

        Reliability Level: SOVEREIGN TIER
        Fail-Closed: Returns None on failure (never fabricates values)

        Args:
            correlation_id: Audit trail identifier

        Returns:
            Decimal equity in ZAR, or None if retrieval failed
        """
        cid = correlation_id or self.correlation_id
        source = self.mode_guard.equity_source

        if source == "EXCHANGE":
            return self._get_exchange_equity(cid)
        if source == "DEMO_BROKER":
            return self._get_demo_equity(cid)
        if source == "STATIC":
            return self._get_static_equity(cid)
        logger.error(
            f"[EQUITY-003] Unknown equity source '{source}' | "
            f"mode={self.mode_guard.mode.value} | correlation_id={cid}"
        )
        return None

    def _get_exchange_equity(self, correlation_id: str) -> Optional[Decimal]:
        """
        Fetch equity from VALR exchange (ZAR available balance).

        Args:
            correlation_id: Audit trail identifier

        Returns:
            Decimal equity in ZAR, or None on failure
        """
        if self._valr_client is None:
            logger.error(
                f"[EQUITY-001] VALR client not configured for exchange equity | "
                f"correlation_id={correlation_id}"
            )
            return None

        try:
            balances = self._valr_client.get_balances()
            zar_balance = balances.get("ZAR")

            if zar_balance is None:
                logger.warning(
                    f"[EQUITY-001] No ZAR balance returned from VALR | "
                    f"currencies={list(balances.keys())} | "
                    f"correlation_id={correlation_id}"
                )
                return None

            equity = zar_balance.total.quantize(
                PRECISION_EQUITY, rounding=ROUND_HALF_EVEN
            )

            logger.info(
                f"[EQUITY] Exchange equity fetched | "
                f"available={zar_balance.available} | "
                f"reserved={zar_balance.reserved} | "
                f"total={equity} | correlation_id={correlation_id}"
            )
            return equity

        except Exception as e:
            logger.error(
                f"[EQUITY-001] Exchange equity retrieval failed | "
                f"error={e} | correlation_id={correlation_id}"
            )
            return None

    def _get_demo_equity(self, correlation_id: str) -> Optional[Decimal]:
        """
        Fetch equity from DemoBroker.

        Args:
            correlation_id: Audit trail identifier

        Returns:
            Decimal equity in ZAR, or None on failure
        """
        if self._demo_broker is None:
            logger.error(
                f"[EQUITY-002] DemoBroker not configured for demo equity | "
                f"correlation_id={correlation_id}"
            )
            return None

        try:
            equity_result = self._demo_broker.get_account_equity()
            equity = Decimal(str(equity_result.get("equity", "0"))).quantize(
                PRECISION_EQUITY, rounding=ROUND_HALF_EVEN
            )

            logger.info(
                f"[EQUITY] DemoBroker equity fetched | "
                f"equity={equity} | correlation_id={correlation_id}"
            )
            return equity

        except Exception as e:
            logger.error(
                f"[EQUITY-002] DemoBroker equity retrieval failed | "
                f"error={e} | correlation_id={correlation_id}"
            )
            return None

    def _get_static_equity(self, correlation_id: str) -> Optional[Decimal]:
        """
        Return static equity from configuration.

        Args:
            correlation_id: Audit trail identifier

        Returns:
            Decimal equity in ZAR, or None if not configured
        """
        if self._static_equity is None:
            logger.warning(
                f"[EQUITY-003] No static equity configured for DRY_RUN mode | "
                f"correlation_id={correlation_id}"
            )
            return None

        logger.debug(
            f"[EQUITY] Static equity returned | "
            f"equity={self._static_equity} | correlation_id={correlation_id}"
        )
        return self._static_equity.quantize(
            PRECISION_EQUITY, rounding=ROUND_HALF_EVEN
        )

    def get_source_description(self) -> str:
        """Return human-readable description of the equity source."""
        source = self.mode_guard.equity_source
        mode = self.mode_guard.mode.value
        if source == "EXCHANGE":
            return f"VALR Exchange (mode={mode})"
        if source == "DEMO_BROKER":
            return f"DemoBroker (mode={mode})"
        if source == "STATIC":
            return f"Static ZAR_FLOOR env var (mode={mode})"
        return f"Unknown (mode={mode})"

"""
Capital Allocation Service — Confidence-to-Position-Size Mapping

Calculates position size based on Bayesian confidence, risk parameters,
and mind state policy. All arithmetic uses Python Decimal.

Priority: P0
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
import logging
from typing import Any, Optional
import uuid

logger = logging.getLogger(__name__)


@dataclass
class AllocationResult:
    """Result of capital allocation calculation."""

    symbol: str
    confidence: Decimal
    base_size_zar: Decimal
    mind_state: str
    mind_state_multiplier: Decimal
    final_size_zar: Decimal
    max_position_zar: Decimal
    was_capped: bool
    correlation_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "confidence": str(self.confidence),
            "base_size_zar": str(self.base_size_zar),
            "mind_state": self.mind_state,
            "mind_state_multiplier": str(self.mind_state_multiplier),
            "final_size_zar": str(self.final_size_zar),
            "max_position_zar": str(self.max_position_zar),
            "was_capped": self.was_capped,
            "correlation_id": self.correlation_id,
        }


# Mind state risk scaling
MIND_STATE_RISK: dict[str, dict[str, Decimal]] = {
    "CALM": {
        "risk_per_trade": Decimal("0.02"),
        "position_multiplier": Decimal("1.00"),
    },
    "ALERT": {
        "risk_per_trade": Decimal("0.01"),
        "position_multiplier": Decimal("0.50"),
    },
    "DEFENSIVE": {
        "risk_per_trade": Decimal("0.005"),
        "position_multiplier": Decimal("0.25"),
    },
}


class CapitalAllocationService:
    """
    Position sizing based on confidence and Kelly-inspired formula.

    Formula:
        base_size = portfolio_value × risk_per_trade
        scaled = base_size × confidence × mind_state_multiplier
        final = min(scaled, max_position)

    All arithmetic is Decimal — no float permitted.
    """

    DEFAULT_MAX_POSITION_ZAR = Decimal("5000.00")
    DEFAULT_PORTFOLIO_VALUE_ZAR = Decimal("100000.00")

    def __init__(
        self,
        db_session: Optional[Any] = None,
        confidence_budget_service: Optional[Any] = None,
        correlation_id: Optional[str] = None,
        max_position_zar: Optional[Decimal] = None,
    ):
        self._db_session = db_session
        self._budget_service = confidence_budget_service
        self._correlation_id = correlation_id or str(uuid.uuid4())
        self._max_position = max_position_zar or self.DEFAULT_MAX_POSITION_ZAR

    def calculate_position_size(
        self,
        symbol: str,
        confidence: Decimal,
        mind_state: str = "CALM",
        portfolio_value: Optional[Decimal] = None,
        correlation_id: Optional[str] = None,
    ) -> AllocationResult:
        """
        Calculate position size from confidence and mind state.

        Args:
            symbol: Trading symbol
            confidence: Bayesian confidence [0.01, 0.99]
            mind_state: Current mind state (CALM/ALERT/DEFENSIVE)
            portfolio_value: Current portfolio value in ZAR
            correlation_id: Tracking ID

        Returns:
            AllocationResult with final position size
        """
        cid = correlation_id or self._correlation_id
        pv = portfolio_value or self.DEFAULT_PORTFOLIO_VALUE_ZAR

        # Get mind state parameters
        state_params = MIND_STATE_RISK.get(mind_state, MIND_STATE_RISK["CALM"])
        risk_per_trade = state_params["risk_per_trade"]
        multiplier = state_params["position_multiplier"]

        # Base size = risk fraction of portfolio
        base_size = (pv * risk_per_trade).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        # Scale by confidence
        scaled = (base_size * confidence * multiplier).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        # Cap at maximum
        was_capped = scaled > self._max_position
        final_size = min(scaled, self._max_position)

        result = AllocationResult(
            symbol=symbol,
            confidence=confidence,
            base_size_zar=base_size,
            mind_state=mind_state,
            mind_state_multiplier=multiplier,
            final_size_zar=final_size,
            max_position_zar=self._max_position,
            was_capped=was_capped,
            correlation_id=cid,
        )

        logger.info(
            f"[CAPITAL-ALLOC] Position sized | "
            f"symbol={symbol} confidence={confidence} "
            f"mind_state={mind_state} base={base_size} "
            f"final={final_size} capped={was_capped} | "
            f"correlation_id={cid}"
        )

        self._persist_allocation(result, pv, risk_per_trade)
        return result

    def _persist_allocation(
        self,
        result: AllocationResult,
        portfolio_value: Decimal,
        risk_per_trade: Decimal,
    ) -> None:
        """Persist allocation to capital_allocation_log table."""
        if not self._db_session:
            return
        try:
            from sqlalchemy import text

            self._db_session.execute(
                text("""
                    INSERT INTO capital_allocation_log
                        (correlation_id, symbol, confidence, portfolio_value_zar,
                         risk_per_trade, base_size_zar, mind_state,
                         mind_state_multiplier, final_size_zar,
                         max_position_zar, was_capped)
                    VALUES
                        (:cid, :symbol, :confidence, :portfolio,
                         :risk, :base, :mind_state,
                         :multiplier, :final, :max_pos, :capped)
                """),
                {
                    "cid": result.correlation_id,
                    "symbol": result.symbol,
                    "confidence": str(result.confidence),
                    "portfolio": str(portfolio_value),
                    "risk": str(risk_per_trade),
                    "base": str(result.base_size_zar),
                    "mind_state": result.mind_state,
                    "multiplier": str(result.mind_state_multiplier),
                    "final": str(result.final_size_zar),
                    "max_pos": str(result.max_position_zar),
                    "capped": result.was_capped,
                },
            )
            self._db_session.commit()
        except Exception as e:
            logger.error(f"[CAPITAL-ALLOC] Failed to persist allocation | error={e}")

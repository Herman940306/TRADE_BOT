"""
Mind State Policy Service — Policy Enforcement Per Mind State

Applies mind-state-specific modifications to proposed trades:
position scaling, cooldowns, and risk limit adjustments.

Priority: P1
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
import logging
from typing import Any, Optional
import uuid

logger = logging.getLogger(__name__)


@dataclass
class PolicyVerdict:
    """Result of mind state policy check."""

    allowed: bool
    original_size_zar: Decimal
    modified_size_zar: Decimal
    mind_state: str
    position_multiplier: Decimal
    reason: Optional[str] = None
    correlation_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "original_size_zar": str(self.original_size_zar),
            "modified_size_zar": str(self.modified_size_zar),
            "mind_state": self.mind_state,
            "position_multiplier": str(self.position_multiplier),
            "reason": self.reason,
            "correlation_id": self.correlation_id,
        }


@dataclass
class _MindPolicy:
    """Configuration for a single mind state."""

    position_multiplier: Decimal
    cooldown_minutes: int
    max_concurrent_trades: int


_POLICIES: dict[str, _MindPolicy] = {
    "CALM": _MindPolicy(
        position_multiplier=Decimal("1.00"),
        cooldown_minutes=0,
        max_concurrent_trades=5,
    ),
    "ALERT": _MindPolicy(
        position_multiplier=Decimal("0.50"),
        cooldown_minutes=5,
        max_concurrent_trades=3,
    ),
    "DEFENSIVE": _MindPolicy(
        position_multiplier=Decimal("0.25"),
        cooldown_minutes=15,
        max_concurrent_trades=1,
    ),
}


class MindStatePolicyService:
    """
    Applies mind-state-specific policy modifications to trade proposals.
    """

    def __init__(
        self,
        db_session: Optional[Any] = None,
        mind_state_service: Optional[Any] = None,
        correlation_id: Optional[str] = None,
    ):
        self._db_session = db_session
        self._mind_state_service = mind_state_service
        self._correlation_id = correlation_id or str(uuid.uuid4())
        self._last_trade_time: Optional[datetime] = None

    def apply_policy(
        self,
        proposed_size_zar: Decimal,
        mind_state: str,
        correlation_id: Optional[str] = None,
    ) -> PolicyVerdict:
        """
        Apply mind-state policy to a trade proposal.

        Args:
            proposed_size_zar: Original proposed position size
            mind_state: Current mind state
            correlation_id: Tracking ID

        Returns:
            PolicyVerdict with allowed/rejected status and modified size
        """
        cid = correlation_id or self._correlation_id
        policy = _POLICIES.get(mind_state, _POLICIES["CALM"])

        # Check cooldown
        if policy.cooldown_minutes > 0 and self._last_trade_time:
            elapsed = (
                datetime.now(timezone.utc) - self._last_trade_time
            ).total_seconds() / 60
            if elapsed < policy.cooldown_minutes:
                return PolicyVerdict(
                    allowed=False,
                    original_size_zar=proposed_size_zar,
                    modified_size_zar=Decimal("0.00"),
                    mind_state=mind_state,
                    position_multiplier=policy.position_multiplier,
                    reason=(
                        f"{mind_state} cooldown active — "
                        f"{policy.cooldown_minutes - elapsed:.1f} min remaining"
                    ),
                    correlation_id=cid,
                )

        # Scale position size
        modified = (proposed_size_zar * policy.position_multiplier).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        logger.info(
            f"[MIND-POLICY] Applied | mind_state={mind_state} "
            f"multiplier={policy.position_multiplier} "
            f"original={proposed_size_zar} modified={modified} | "
            f"correlation_id={cid}"
        )

        return PolicyVerdict(
            allowed=True,
            original_size_zar=proposed_size_zar,
            modified_size_zar=modified,
            mind_state=mind_state,
            position_multiplier=policy.position_multiplier,
            correlation_id=cid,
        )

    def record_trade_executed(self) -> None:
        """Mark that a trade was just executed (for cooldown tracking)."""
        self._last_trade_time = datetime.now(timezone.utc)

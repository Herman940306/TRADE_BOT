"""
Mind State Service — CALM / ALERT / DEFENSIVE State Machine

Tracks system mood based on trading performance metrics.
State transitions influence position sizing and risk limits.

Priority: P1
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
import logging
from typing import Any, Optional
import uuid

logger = logging.getLogger(__name__)


class MindState:
    CALM = "CALM"
    ALERT = "ALERT"
    DEFENSIVE = "DEFENSIVE"

    ALL = {CALM, ALERT, DEFENSIVE}


@dataclass
class MindStateTransition:
    """Record of a mind state change."""

    previous_state: str
    new_state: str
    trigger_reason: str
    trigger_metric: dict[str, Any]
    correlation_id: str
    timestamp: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "previous_state": self.previous_state,
            "new_state": self.new_state,
            "trigger_reason": self.trigger_reason,
            "trigger_metric": self.trigger_metric,
            "timestamp": self.timestamp.isoformat(),
            "correlation_id": self.correlation_id,
        }


class MindStateService:
    """
    System mood state machine.

    Transitions:
        CALM → ALERT:      consecutive_losses >= 2 OR daily_drawdown > 3%
        CALM → DEFENSIVE:   guardian_warning OR exchange_error
        ALERT → CALM:       3 profitable trades in row
        ALERT → DEFENSIVE:  daily_drawdown > 5% OR guardian_lock
        DEFENSIVE → CALM:   guardian_unlocked AND new_day
    """

    ALERT_LOSS_THRESHOLD = 2
    ALERT_DRAWDOWN_PCT = Decimal("3.0")
    DEFENSIVE_DRAWDOWN_PCT = Decimal("5.0")
    CALM_PROFIT_THRESHOLD = 3

    def __init__(
        self,
        db_session: Optional[Any] = None,
        correlation_id: Optional[str] = None,
    ):
        self._db_session = db_session
        self._correlation_id = correlation_id or str(uuid.uuid4())
        self._current_state = MindState.CALM
        self._consecutive_losses = 0
        self._consecutive_profits = 0

    @property
    def current_state(self) -> str:
        return self._current_state

    def evaluate_transitions(
        self,
        daily_drawdown_pct: Decimal = Decimal("0.0"),
        consecutive_losses: int = 0,
        consecutive_profits: int = 0,
        guardian_locked: bool = False,
        guardian_warning: bool = False,
        exchange_error: bool = False,
        new_day: bool = False,
        correlation_id: Optional[str] = None,
    ) -> Optional[MindStateTransition]:
        """
        Evaluate if a state transition should occur.

        Returns:
            MindStateTransition if state changed, None otherwise
        """
        cid = correlation_id or self._correlation_id
        old_state = self._current_state
        new_state = old_state
        trigger_reason = ""

        self._consecutive_losses = consecutive_losses
        self._consecutive_profits = consecutive_profits

        if old_state == MindState.CALM:
            if guardian_warning or exchange_error:
                new_state = MindState.DEFENSIVE
                trigger_reason = (
                    "guardian_warning" if guardian_warning else "exchange_error"
                )
            elif (
                consecutive_losses >= self.ALERT_LOSS_THRESHOLD
                or daily_drawdown_pct > self.ALERT_DRAWDOWN_PCT
            ):
                new_state = MindState.ALERT
                trigger_reason = (
                    f"consecutive_losses={consecutive_losses}"
                    if consecutive_losses >= self.ALERT_LOSS_THRESHOLD
                    else f"daily_drawdown={daily_drawdown_pct}%"
                )

        elif old_state == MindState.ALERT:
            if daily_drawdown_pct > self.DEFENSIVE_DRAWDOWN_PCT or guardian_locked:
                new_state = MindState.DEFENSIVE
                trigger_reason = (
                    "guardian_locked"
                    if guardian_locked
                    else f"daily_drawdown={daily_drawdown_pct}%"
                )
            elif consecutive_profits >= self.CALM_PROFIT_THRESHOLD:
                new_state = MindState.CALM
                trigger_reason = f"consecutive_profits={consecutive_profits}"

        elif old_state == MindState.DEFENSIVE:
            if not guardian_locked and new_day:
                new_state = MindState.CALM
                trigger_reason = "guardian_unlocked_and_new_day"

        if new_state != old_state:
            self._current_state = new_state
            transition = MindStateTransition(
                previous_state=old_state,
                new_state=new_state,
                trigger_reason=trigger_reason,
                trigger_metric={
                    "daily_drawdown_pct": str(daily_drawdown_pct),
                    "consecutive_losses": consecutive_losses,
                    "consecutive_profits": consecutive_profits,
                    "guardian_locked": guardian_locked,
                },
                correlation_id=cid,
                timestamp=datetime.now(timezone.utc),
            )

            logger.info(
                f"[MIND-STATE] Transition | "
                f"{old_state} → {new_state} reason={trigger_reason} | "
                f"correlation_id={cid}"
            )

            self._persist_transition(transition)
            return transition

        return None

    def _persist_transition(self, transition: MindStateTransition) -> None:
        """Persist transition to mind_state_history table."""
        if not self._db_session:
            return
        try:
            import json

            from sqlalchemy import text

            self._db_session.execute(
                text("""
                    INSERT INTO mind_state_history
                        (previous_state, new_state, trigger_reason,
                         trigger_metric, correlation_id)
                    VALUES
                        (:prev, :new, :reason, :metric, :cid)
                """),
                {
                    "prev": transition.previous_state,
                    "new": transition.new_state,
                    "reason": transition.trigger_reason,
                    "metric": json.dumps(transition.trigger_metric),
                    "cid": transition.correlation_id,
                },
            )
            self._db_session.commit()
        except Exception as e:
            logger.error(f"[MIND-STATE] Failed to persist transition | error={e}")

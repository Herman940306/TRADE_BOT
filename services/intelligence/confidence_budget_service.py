"""
Confidence Budget Service — Daily Risk Budget Management

Prevents reckless trading by limiting daily risk exposure.
Each trade consumes budget proportional to risk and inverse of confidence.

Priority: P0
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class BudgetCheckResult:
    """Result of a budget check for a proposed trade."""

    allowed: bool
    remaining_budget: Decimal
    deduction_amount: Decimal
    remaining_after: Decimal
    block_reason: Optional[str] = None
    correlation_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "remaining_budget": str(self.remaining_budget),
            "deduction_amount": str(self.deduction_amount),
            "remaining_after": str(self.remaining_after),
            "block_reason": self.block_reason,
            "correlation_id": self.correlation_id,
        }


@dataclass
class BudgetState:
    """Current state of the daily confidence budget."""

    budget_date: date
    starting_budget: Decimal
    remaining_budget: Decimal
    total_deducted: Decimal
    trade_count: int
    blocked_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "budget_date": self.budget_date.isoformat(),
            "starting_budget": str(self.starting_budget),
            "remaining_budget": str(self.remaining_budget),
            "total_deducted": str(self.total_deducted),
            "trade_count": self.trade_count,
            "blocked_count": self.blocked_count,
        }


class ConfidenceBudgetService:
    """
    Daily risk budget manager.

    Each day starts with a fixed budget (default: 100 units).
    Each proposed trade costs budget based on:
        cost = risk_score × position_size_factor × (1 - confidence)

    If remaining budget < cost, the trade is soft-blocked (Guardian
    still has final say).

    Invariants:
    - Budget never goes negative
    - All arithmetic is Decimal
    - Budget resets at midnight UTC
    """

    DEFAULT_DAILY_BUDGET = Decimal("100.0000")

    def __init__(
        self,
        db_session: Optional[Any] = None,
        correlation_id: Optional[str] = None,
        daily_budget: Optional[Decimal] = None,
    ):
        self._db_session = db_session
        self._correlation_id = correlation_id or str(uuid.uuid4())
        self._daily_budget = daily_budget or self.DEFAULT_DAILY_BUDGET

        # In-memory state (loaded from DB on first access)
        self._current_state: Optional[BudgetState] = None

    def get_state(self) -> BudgetState:
        """Get current budget state, initializing if needed."""
        today = datetime.now(timezone.utc).date()

        if self._current_state is None or self._current_state.budget_date != today:
            self._current_state = self._load_or_create_state(today)

        return self._current_state

    def check_budget(
        self,
        symbol: str,
        confidence: Decimal,
        risk_score: Decimal,
        position_size_factor: Decimal = Decimal("1.0000"),
        correlation_id: Optional[str] = None,
    ) -> BudgetCheckResult:
        """
        Check if a proposed trade fits within the daily budget.

        Args:
            symbol: Trading symbol
            confidence: Bayesian confidence [0.01, 0.99]
            risk_score: Risk assessment score [0, 1]
            position_size_factor: Scale factor for position size
            correlation_id: Tracking ID

        Returns:
            BudgetCheckResult with allowed/blocked status
        """
        cid = correlation_id or self._correlation_id
        state = self.get_state()

        # Calculate cost: higher risk + lower confidence = higher cost
        inverse_confidence = Decimal("1.0000") - confidence
        cost = (risk_score * position_size_factor * inverse_confidence).quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_UP
        )

        # Minimum cost floor to prevent free trades
        cost = max(cost, Decimal("0.0001"))

        remaining_after = state.remaining_budget - cost

        if remaining_after < Decimal("0"):
            # Soft block — not enough budget
            state.blocked_count += 1
            result = BudgetCheckResult(
                allowed=False,
                remaining_budget=state.remaining_budget,
                deduction_amount=cost,
                remaining_after=state.remaining_budget,  # No deduction on block
                block_reason=(
                    f"Insufficient budget: need {cost}, have {state.remaining_budget}"
                ),
                correlation_id=cid,
            )
            logger.warning(
                f"[CONFIDENCE-BUDGET] Trade blocked — insufficient budget | "
                f"symbol={symbol} cost={cost} "
                f"remaining={state.remaining_budget} | "
                f"correlation_id={cid}"
            )
            self._persist_deduction(state.budget_date, symbol, confidence,
                                    risk_score, cost, state.remaining_budget,
                                    was_blocked=True,
                                    block_reason=result.block_reason,
                                    correlation_id=cid)
            return result

        # Deduct from budget
        state.remaining_budget = remaining_after
        state.total_deducted = state.total_deducted + cost
        state.trade_count += 1

        result = BudgetCheckResult(
            allowed=True,
            remaining_budget=state.remaining_budget + cost,  # Before deduction
            deduction_amount=cost,
            remaining_after=state.remaining_budget,
            correlation_id=cid,
        )

        logger.info(
            f"[CONFIDENCE-BUDGET] Trade allowed | "
            f"symbol={symbol} cost={cost} "
            f"remaining={state.remaining_budget} | "
            f"correlation_id={cid}"
        )

        self._persist_deduction(state.budget_date, symbol, confidence,
                                risk_score, cost, state.remaining_budget,
                                was_blocked=False, correlation_id=cid)
        self._update_state(state, cid)

        return result

    def reconcile(self, correlation_id: Optional[str] = None) -> BudgetState:
        """Reconcile in-memory state with DB. Called during learning cycles."""
        state = self.get_state()
        self._update_state(state, correlation_id or self._correlation_id)
        return state

    def reset(
        self,
        reason: str,
        reset_by: str,
        correlation_id: Optional[str] = None,
    ) -> BudgetState:
        """Manually reset budget (operator action)."""
        cid = correlation_id or self._correlation_id
        today = datetime.now(timezone.utc).date()

        self._current_state = BudgetState(
            budget_date=today,
            starting_budget=self._daily_budget,
            remaining_budget=self._daily_budget,
            total_deducted=Decimal("0.0000"),
            trade_count=0,
            blocked_count=0,
        )

        logger.info(
            f"[CONFIDENCE-BUDGET] Budget manually reset | "
            f"reset_by={reset_by} reason={reason} | "
            f"correlation_id={cid}"
        )

        self._persist_reset(today, reset_by, reason, cid)
        return self._current_state

    def _load_or_create_state(self, today: date) -> BudgetState:
        """Load today's budget from DB or create fresh."""
        if self._db_session:
            try:
                from sqlalchemy import text

                row = self._db_session.execute(
                    text("""
                        SELECT starting_budget, remaining_budget,
                               total_deducted, trade_count, blocked_count
                        FROM confidence_budget_daily
                        WHERE budget_date = :today
                    """),
                    {"today": today},
                ).fetchone()

                if row:
                    return BudgetState(
                        budget_date=today,
                        starting_budget=Decimal(str(row[0])),
                        remaining_budget=Decimal(str(row[1])),
                        total_deducted=Decimal(str(row[2])),
                        trade_count=int(row[3]),
                        blocked_count=int(row[4]),
                    )
            except Exception as e:
                logger.error(
                    f"[CONFIDENCE-BUDGET] Failed to load state | error={e}"
                )

        # Create fresh state
        state = BudgetState(
            budget_date=today,
            starting_budget=self._daily_budget,
            remaining_budget=self._daily_budget,
            total_deducted=Decimal("0.0000"),
            trade_count=0,
            blocked_count=0,
        )

        self._persist_new_state(state)
        return state

    def _persist_new_state(self, state: BudgetState) -> None:
        """Insert a new daily budget row."""
        if not self._db_session:
            return
        try:
            from sqlalchemy import text

            self._db_session.execute(
                text("""
                    INSERT INTO confidence_budget_daily
                        (budget_date, starting_budget, remaining_budget,
                         total_deducted, trade_count, blocked_count,
                         correlation_id)
                    VALUES (:date, :starting, :remaining, :deducted,
                            :trades, :blocked, :cid)
                    ON CONFLICT (budget_date) DO NOTHING
                """),
                {
                    "date": state.budget_date,
                    "starting": str(state.starting_budget),
                    "remaining": str(state.remaining_budget),
                    "deducted": str(state.total_deducted),
                    "trades": state.trade_count,
                    "blocked": state.blocked_count,
                    "cid": self._correlation_id,
                },
            )
            self._db_session.commit()
        except Exception as e:
            logger.error(
                f"[CONFIDENCE-BUDGET] Failed to persist new state | error={e}"
            )

    def _update_state(self, state: BudgetState, correlation_id: str) -> None:
        """Update existing daily budget row."""
        if not self._db_session:
            return
        try:
            from sqlalchemy import text

            self._db_session.execute(
                text("""
                    UPDATE confidence_budget_daily
                    SET remaining_budget = :remaining,
                        total_deducted = :deducted,
                        trade_count = :trades,
                        blocked_count = :blocked,
                        updated_at = NOW()
                    WHERE budget_date = :date
                """),
                {
                    "remaining": str(state.remaining_budget),
                    "deducted": str(state.total_deducted),
                    "trades": state.trade_count,
                    "blocked": state.blocked_count,
                    "date": state.budget_date,
                },
            )
            self._db_session.commit()
        except Exception as e:
            logger.error(
                f"[CONFIDENCE-BUDGET] Failed to update state | error={e}"
            )

    def _persist_deduction(
        self, budget_date: date, symbol: str, confidence: Decimal,
        risk_score: Decimal, amount: Decimal, remaining: Decimal,
        was_blocked: bool, block_reason: Optional[str] = None,
        correlation_id: str = "",
    ) -> None:
        """Persist individual budget deduction."""
        if not self._db_session:
            return
        try:
            from sqlalchemy import text

            self._db_session.execute(
                text("""
                    INSERT INTO confidence_budget_deductions
                        (budget_date, correlation_id, symbol, confidence,
                         risk_score, deduction_amount, remaining_after,
                         was_blocked, block_reason)
                    VALUES (:date, :cid, :symbol, :confidence,
                            :risk, :amount, :remaining,
                            :blocked, :reason)
                """),
                {
                    "date": budget_date,
                    "cid": correlation_id,
                    "symbol": symbol,
                    "confidence": str(confidence),
                    "risk": str(risk_score),
                    "amount": str(amount),
                    "remaining": str(remaining),
                    "blocked": was_blocked,
                    "reason": block_reason,
                },
            )
            self._db_session.commit()
        except Exception as e:
            logger.error(
                f"[CONFIDENCE-BUDGET] Failed to persist deduction | error={e}"
            )

    def _persist_reset(
        self, budget_date: date, reset_by: str, reason: str,
        correlation_id: str,
    ) -> None:
        """Persist budget reset."""
        if not self._db_session:
            return
        try:
            from sqlalchemy import text

            self._db_session.execute(
                text("""
                    UPDATE confidence_budget_daily
                    SET remaining_budget = starting_budget,
                        total_deducted = 0,
                        trade_count = 0,
                        blocked_count = 0,
                        was_reset = TRUE,
                        reset_by = :reset_by,
                        reset_reason = :reason,
                        updated_at = NOW()
                    WHERE budget_date = :date
                """),
                {
                    "reset_by": reset_by,
                    "reason": reason,
                    "date": budget_date,
                },
            )
            self._db_session.commit()
        except Exception as e:
            logger.error(
                f"[CONFIDENCE-BUDGET] Failed to persist reset | error={e}"
            )

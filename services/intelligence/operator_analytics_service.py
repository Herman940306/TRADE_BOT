"""
Operator Analytics Service — Operator vs AI Performance Tracking

Tracks operator decisions (approve/reject/timeout) and compares
outcomes against AI recommendations.

Priority: P1
"""

import logging
import uuid
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class OperatorDecisionRecord:
    """Record of a single operator decision with outcome."""

    operator_id: str
    trade_id: str
    decision: str  # APPROVE, REJECT, TIMEOUT
    ai_recommendation: str  # LONG, SHORT, HOLD
    ai_confidence: Decimal
    outcome_direction: Optional[str] = None
    outcome_pnl_zar: Optional[Decimal] = None
    was_correct: Optional[bool] = None
    ai_would_have_been_correct: Optional[bool] = None
    value_add_zar: Optional[Decimal] = None
    decision_time_ms: Optional[int] = None
    correlation_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "operator_id": self.operator_id,
            "trade_id": self.trade_id,
            "decision": self.decision,
            "ai_recommendation": self.ai_recommendation,
            "ai_confidence": str(self.ai_confidence),
            "outcome_direction": self.outcome_direction,
            "outcome_pnl_zar": str(self.outcome_pnl_zar) if self.outcome_pnl_zar else None,
            "was_correct": self.was_correct,
            "ai_would_have_been_correct": self.ai_would_have_been_correct,
            "value_add_zar": str(self.value_add_zar) if self.value_add_zar else None,
            "decision_time_ms": self.decision_time_ms,
            "correlation_id": self.correlation_id,
        }


@dataclass
class OperatorMetrics:
    """Aggregate operator performance metrics."""

    total_decisions: int
    approvals: int
    rejections: int
    timeouts: int
    directional_accuracy: Optional[Decimal]
    avg_decision_time_ms: Optional[int]
    total_value_add_zar: Decimal
    ai_accuracy: Optional[Decimal]

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_decisions": self.total_decisions,
            "approvals": self.approvals,
            "rejections": self.rejections,
            "timeouts": self.timeouts,
            "directional_accuracy": str(self.directional_accuracy) if self.directional_accuracy else None,
            "avg_decision_time_ms": self.avg_decision_time_ms,
            "total_value_add_zar": str(self.total_value_add_zar),
            "ai_accuracy": str(self.ai_accuracy) if self.ai_accuracy else None,
        }


class OperatorAnalyticsService:
    """
    Tracks operator decision quality and compares with AI baseline.
    """

    def __init__(
        self,
        db_session: Optional[Any] = None,
        correlation_id: Optional[str] = None,
    ):
        self._db_session = db_session
        self._correlation_id = correlation_id or str(uuid.uuid4())

    def record_decision(
        self,
        operator_id: str,
        trade_id: str,
        decision: str,
        ai_recommendation: str,
        ai_confidence: Decimal,
        decision_time_ms: Optional[int] = None,
        correlation_id: Optional[str] = None,
    ) -> OperatorDecisionRecord:
        """Record an operator decision."""
        cid = correlation_id or self._correlation_id

        record = OperatorDecisionRecord(
            operator_id=operator_id,
            trade_id=trade_id,
            decision=decision,
            ai_recommendation=ai_recommendation,
            ai_confidence=ai_confidence,
            decision_time_ms=decision_time_ms,
            correlation_id=cid,
        )

        self._persist_decision(record)

        logger.info(
            f"[OPERATOR-ANALYTICS] Decision recorded | "
            f"operator={operator_id} trade={trade_id} "
            f"decision={decision} ai_rec={ai_recommendation} | "
            f"correlation_id={cid}"
        )

        return record

    def record_outcome(
        self,
        trade_id: str,
        outcome_direction: str,
        outcome_pnl_zar: Decimal,
        correlation_id: Optional[str] = None,
    ) -> None:
        """Record trade outcome and compute correctness metrics."""
        if not self._db_session:
            return

        try:
            from sqlalchemy import text

            # Get the original decision
            row = self._db_session.execute(
                text("""
                    SELECT decision, ai_recommendation
                    FROM operator_analytics
                    WHERE trade_id = :tid
                    ORDER BY created_at DESC LIMIT 1
                """),
                {"tid": trade_id},
            ).fetchone()

            if not row:
                return

            decision = row[0]
            ai_rec = row[1]

            # Determine correctness
            was_correct = None
            ai_correct = None
            value_add = None

            if decision == "APPROVE":
                was_correct = outcome_pnl_zar > Decimal("0")
                ai_correct = (
                    (ai_rec in ("LONG", "SHORT"))
                    and outcome_pnl_zar > Decimal("0")
                )
                value_add = outcome_pnl_zar if was_correct else Decimal("0") - outcome_pnl_zar
            elif decision == "REJECT":
                # Rejection was correct if the trade would have lost
                was_correct = outcome_pnl_zar <= Decimal("0")
                value_add = abs(outcome_pnl_zar) if was_correct else Decimal("0") - abs(outcome_pnl_zar)

            self._db_session.execute(
                text("""
                    UPDATE operator_analytics
                    SET outcome_direction = :direction,
                        outcome_pnl_zar = :pnl,
                        was_correct = :correct,
                        ai_would_have_been_correct = :ai_correct,
                        value_add_zar = :value_add
                    WHERE trade_id = :tid
                """),
                {
                    "direction": outcome_direction,
                    "pnl": str(outcome_pnl_zar),
                    "correct": was_correct,
                    "ai_correct": ai_correct,
                    "value_add": str(value_add) if value_add else None,
                    "tid": trade_id,
                },
            )
            self._db_session.commit()
        except Exception as e:
            logger.error(
                f"[OPERATOR-ANALYTICS] Failed to record outcome | error={e}"
            )

    def get_metrics(
        self, operator_id: Optional[str] = None
    ) -> OperatorMetrics:
        """Get aggregate operator performance metrics."""
        if not self._db_session:
            return OperatorMetrics(
                total_decisions=0, approvals=0, rejections=0,
                timeouts=0, directional_accuracy=None,
                avg_decision_time_ms=None,
                total_value_add_zar=Decimal("0"),
                ai_accuracy=None,
            )

        try:
            from sqlalchemy import text

            where_clause = ""
            params: dict[str, Any] = {}
            if operator_id:
                where_clause = "WHERE operator_id = :oid"
                params["oid"] = operator_id

            row = self._db_session.execute(
                text(f"""
                    SELECT
                        COUNT(*) as total,
                        COUNT(*) FILTER (WHERE decision = 'APPROVE') as approvals,
                        COUNT(*) FILTER (WHERE decision = 'REJECT') as rejections,
                        COUNT(*) FILTER (WHERE decision = 'TIMEOUT') as timeouts,
                        AVG(CASE WHEN was_correct THEN 1.0 ELSE 0.0 END)
                            FILTER (WHERE was_correct IS NOT NULL) as accuracy,
                        AVG(decision_time_ms) as avg_time,
                        COALESCE(SUM(value_add_zar), 0) as total_value_add,
                        AVG(CASE WHEN ai_would_have_been_correct THEN 1.0 ELSE 0.0 END)
                            FILTER (WHERE ai_would_have_been_correct IS NOT NULL) as ai_accuracy
                    FROM operator_analytics
                    {where_clause}
                """),
                params,
            ).fetchone()

            if not row:
                return OperatorMetrics(
                    total_decisions=0, approvals=0, rejections=0,
                    timeouts=0, directional_accuracy=None,
                    avg_decision_time_ms=None,
                    total_value_add_zar=Decimal("0"),
                    ai_accuracy=None,
                )

            return OperatorMetrics(
                total_decisions=int(row[0]),
                approvals=int(row[1]),
                rejections=int(row[2]),
                timeouts=int(row[3]),
                directional_accuracy=(
                    Decimal(str(row[4])).quantize(
                        Decimal("0.0001"), rounding=ROUND_HALF_UP
                    )
                    if row[4] is not None
                    else None
                ),
                avg_decision_time_ms=int(row[5]) if row[5] else None,
                total_value_add_zar=Decimal(str(row[6])),
                ai_accuracy=(
                    Decimal(str(row[7])).quantize(
                        Decimal("0.0001"), rounding=ROUND_HALF_UP
                    )
                    if row[7] is not None
                    else None
                ),
            )
        except Exception as e:
            logger.error(
                f"[OPERATOR-ANALYTICS] Failed to get metrics | error={e}"
            )
            return OperatorMetrics(
                total_decisions=0, approvals=0, rejections=0,
                timeouts=0, directional_accuracy=None,
                avg_decision_time_ms=None,
                total_value_add_zar=Decimal("0"),
                ai_accuracy=None,
            )

    def _persist_decision(self, record: OperatorDecisionRecord) -> None:
        """Persist operator decision."""
        if not self._db_session:
            return
        try:
            from sqlalchemy import text

            self._db_session.execute(
                text("""
                    INSERT INTO operator_analytics
                        (operator_id, trade_id, decision,
                         ai_recommendation, ai_confidence,
                         decision_time_ms, correlation_id)
                    VALUES
                        (:oid, :tid, :decision, :ai_rec,
                         :ai_conf, :time_ms, :cid)
                """),
                {
                    "oid": record.operator_id,
                    "tid": record.trade_id,
                    "decision": record.decision,
                    "ai_rec": record.ai_recommendation,
                    "ai_conf": str(record.ai_confidence),
                    "time_ms": record.decision_time_ms,
                    "cid": record.correlation_id,
                },
            )
            self._db_session.commit()
        except Exception as e:
            logger.error(
                f"[OPERATOR-ANALYTICS] Failed to persist | error={e}"
            )

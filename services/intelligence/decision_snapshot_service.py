"""
Decision Snapshot Service — Full-Context Audit Records

Records every trading decision with complete context for forensic
replay and counterfactual analysis.

Priority: P0
"""

import json
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class DecisionSnapshot:
    """Full-context record of a trading decision."""

    snapshot_id: str
    correlation_id: str
    signal_data: dict[str, Any]
    bayesian_verdict: dict[str, Any]
    confidence: Decimal
    remaining_budget: Decimal
    mind_state: str
    regime: str
    strategy_name: str
    proposed_size_zar: Decimal
    final_size_zar: Decimal
    guardian_status: str
    operator_decision: Optional[str]
    market_state: dict[str, Any]
    trade_id: Optional[str]
    timestamp: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "correlation_id": self.correlation_id,
            "signal_data": self.signal_data,
            "bayesian_verdict": self.bayesian_verdict,
            "confidence": str(self.confidence),
            "remaining_budget": str(self.remaining_budget),
            "mind_state": self.mind_state,
            "regime": self.regime,
            "strategy_name": self.strategy_name,
            "proposed_size_zar": str(self.proposed_size_zar),
            "final_size_zar": str(self.final_size_zar),
            "guardian_status": self.guardian_status,
            "operator_decision": self.operator_decision,
            "market_state": self.market_state,
            "trade_id": self.trade_id,
            "timestamp": self.timestamp.isoformat(),
        }


class DecisionSnapshotService:
    """
    Records full-context snapshots of every trading decision.

    Every signal evaluation — whether it results in a trade, rejection,
    or timeout — generates a snapshot for forensic analysis.
    """

    def __init__(
        self,
        db_session: Optional[Any] = None,
        correlation_id: Optional[str] = None,
    ):
        self._db_session = db_session
        self._correlation_id = correlation_id or str(uuid.uuid4())

    def record(
        self,
        signal_data: dict[str, Any],
        bayesian_verdict: dict[str, Any],
        confidence: Decimal,
        remaining_budget: Decimal,
        mind_state: str,
        regime: str,
        strategy_name: str,
        proposed_size_zar: Decimal,
        final_size_zar: Decimal,
        guardian_status: str = "UNLOCKED",
        operator_decision: Optional[str] = None,
        market_state: Optional[dict[str, Any]] = None,
        trade_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> DecisionSnapshot:
        """
        Record a decision snapshot.

        Returns:
            DecisionSnapshot with generated snapshot_id
        """
        cid = correlation_id or self._correlation_id
        snapshot_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        snapshot = DecisionSnapshot(
            snapshot_id=snapshot_id,
            correlation_id=cid,
            signal_data=signal_data,
            bayesian_verdict=bayesian_verdict,
            confidence=confidence,
            remaining_budget=remaining_budget,
            mind_state=mind_state,
            regime=regime,
            strategy_name=strategy_name,
            proposed_size_zar=proposed_size_zar,
            final_size_zar=final_size_zar,
            guardian_status=guardian_status,
            operator_decision=operator_decision,
            market_state=market_state or {},
            trade_id=trade_id,
            timestamp=now,
        )

        self._persist(snapshot)

        logger.info(
            f"[DECISION-SNAPSHOT] Recorded | "
            f"snapshot_id={snapshot_id} strategy={strategy_name} "
            f"confidence={confidence} decision={operator_decision} | "
            f"correlation_id={cid}"
        )

        return snapshot

    def record_outcome(
        self,
        snapshot_id: str,
        pnl_zar: Decimal,
        correlation_id: Optional[str] = None,
    ) -> None:
        """Record trade outcome against an existing snapshot."""
        cid = correlation_id or self._correlation_id
        if not self._db_session:
            return

        try:
            from sqlalchemy import text

            self._db_session.execute(
                text("""
                    UPDATE decision_snapshots
                    SET outcome_pnl_zar = :pnl,
                        outcome_recorded_at = NOW()
                    WHERE snapshot_id = :sid::uuid
                """),
                {"pnl": str(pnl_zar), "sid": snapshot_id},
            )
            self._db_session.commit()
            logger.info(
                f"[DECISION-SNAPSHOT] Outcome recorded | "
                f"snapshot_id={snapshot_id} pnl={pnl_zar} | "
                f"correlation_id={cid}"
            )
        except Exception as e:
            logger.error(
                f"[DECISION-SNAPSHOT] Failed to record outcome | "
                f"error={e} | correlation_id={cid}"
            )

    def get_recent(
        self, limit: int = 50, correlation_id: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Get recent decision snapshots."""
        if not self._db_session:
            return []

        try:
            from sqlalchemy import text

            rows = self._db_session.execute(
                text("""
                    SELECT snapshot_id, correlation_id, confidence,
                           mind_state, regime, strategy_name,
                           final_size_zar, guardian_status,
                           operator_decision, trade_id,
                           outcome_pnl_zar, created_at
                    FROM decision_snapshots
                    ORDER BY created_at DESC
                    LIMIT :lim
                """),
                {"lim": limit},
            ).fetchall()

            return [
                {
                    "snapshot_id": str(r[0]),
                    "correlation_id": r[1],
                    "confidence": str(r[2]),
                    "mind_state": r[3],
                    "regime": r[4],
                    "strategy_name": r[5],
                    "final_size_zar": str(r[6]),
                    "guardian_status": r[7],
                    "operator_decision": r[8],
                    "trade_id": r[9],
                    "outcome_pnl_zar": str(r[10]) if r[10] else None,
                    "created_at": r[11].isoformat() if r[11] else None,
                }
                for r in rows
            ]
        except Exception as e:
            logger.error(
                f"[DECISION-SNAPSHOT] Failed to get recent | error={e}"
            )
            return []

    def record_learning_cycle(
        self,
        cycle_type: str,
        outcomes_processed: int,
        beliefs_updated: int,
        budget_reconciled: bool,
        mind_state_before: str,
        mind_state_after: str,
        curriculum_phase: int,
        contract_violations: int,
        violation_details: list[dict[str, Any]],
        metrics_snapshot: dict[str, Any],
        duration_ms: int,
        correlation_id: Optional[str] = None,
    ) -> None:
        """Record a learning cycle snapshot."""
        cid = correlation_id or self._correlation_id
        if not self._db_session:
            logger.debug("[DECISION-SNAPSHOT] No DB — learning cycle not persisted")
            return

        try:
            from sqlalchemy import text

            self._db_session.execute(
                text("""
                    INSERT INTO learning_cycle_snapshots
                        (cycle_type, outcomes_processed, beliefs_updated,
                         budget_reconciled, mind_state_before, mind_state_after,
                         curriculum_phase, contract_violations,
                         violation_details, metrics_snapshot,
                         duration_ms, correlation_id)
                    VALUES
                        (:type, :outcomes, :beliefs, :reconciled,
                         :ms_before, :ms_after, :phase, :violations,
                         :v_details, :metrics, :duration, :cid)
                """),
                {
                    "type": cycle_type,
                    "outcomes": outcomes_processed,
                    "beliefs": beliefs_updated,
                    "reconciled": budget_reconciled,
                    "ms_before": mind_state_before,
                    "ms_after": mind_state_after,
                    "phase": curriculum_phase,
                    "violations": contract_violations,
                    "v_details": json.dumps(violation_details),
                    "metrics": json.dumps(metrics_snapshot),
                    "duration": duration_ms,
                    "cid": cid,
                },
            )
            self._db_session.commit()
        except Exception as e:
            logger.error(
                f"[DECISION-SNAPSHOT] Failed to record learning cycle | "
                f"error={e} | correlation_id={cid}"
            )

    def _persist(self, snapshot: DecisionSnapshot) -> None:
        """Persist snapshot to decision_snapshots table."""
        if not self._db_session:
            return

        try:
            from sqlalchemy import text

            self._db_session.execute(
                text("""
                    INSERT INTO decision_snapshots
                        (snapshot_id, correlation_id, signal_data,
                         bayesian_verdict, confidence, remaining_budget,
                         mind_state, regime, strategy_name,
                         proposed_size_zar, final_size_zar,
                         guardian_status, operator_decision,
                         market_state, trade_id)
                    VALUES
                        (:sid::uuid, :cid, :signal, :verdict, :confidence,
                         :budget, :mind_state, :regime, :strategy,
                         :proposed, :final, :guardian, :operator,
                         :market, :trade_id)
                """),
                {
                    "sid": snapshot.snapshot_id,
                    "cid": snapshot.correlation_id,
                    "signal": json.dumps(snapshot.signal_data),
                    "verdict": json.dumps(snapshot.bayesian_verdict),
                    "confidence": str(snapshot.confidence),
                    "budget": str(snapshot.remaining_budget),
                    "mind_state": snapshot.mind_state,
                    "regime": snapshot.regime,
                    "strategy": snapshot.strategy_name,
                    "proposed": str(snapshot.proposed_size_zar),
                    "final": str(snapshot.final_size_zar),
                    "guardian": snapshot.guardian_status,
                    "operator": snapshot.operator_decision,
                    "market": json.dumps(snapshot.market_state),
                    "trade_id": snapshot.trade_id,
                },
            )
            self._db_session.commit()
        except Exception as e:
            logger.error(
                f"[DECISION-SNAPSHOT] Failed to persist | error={e} | "
                f"correlation_id={snapshot.correlation_id}"
            )

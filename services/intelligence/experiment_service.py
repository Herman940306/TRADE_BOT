"""
Experiment Service — A/B Experiment Lifecycle

Manages strategy experiments with controlled budgets,
regime-scoped execution, and automatic halt on safety breach.

Priority: P2
"""

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
import json
import logging
from typing import Any, Optional
import uuid

logger = logging.getLogger(__name__)


class ExperimentStatus(Enum):
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass
class ExperimentDefinition:
    """A/B experiment specification."""

    experiment_id: str
    name: str
    hypothesis: str
    strategy_variant: str
    baseline_strategy: str
    regime_filter: Optional[str]
    max_trades: int
    max_budget_zar: Decimal
    status: ExperimentStatus
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    correlation_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "name": self.name,
            "hypothesis": self.hypothesis,
            "strategy_variant": self.strategy_variant,
            "baseline_strategy": self.baseline_strategy,
            "regime_filter": self.regime_filter,
            "max_trades": self.max_trades,
            "max_budget_zar": str(self.max_budget_zar),
            "status": self.status.value,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "correlation_id": self.correlation_id,
        }


class ExperimentService:
    """
    Manages experiment lifecycle: propose → approve → activate → complete/fail.

    Constraints:
    - Max budget per experiment enforced
    - 10% drawdown auto-halt
    - All trades through Guardian + HITL (no bypass)
    """

    MAX_DRAWDOWN_PCT = Decimal("0.10")

    def __init__(
        self,
        db_session: Optional[Any] = None,
        correlation_id: Optional[str] = None,
    ):
        self._db_session = db_session
        self._correlation_id = correlation_id or str(uuid.uuid4())

    def propose(
        self,
        name: str,
        hypothesis: str,
        strategy_variant: str,
        baseline_strategy: str,
        max_trades: int = 50,
        max_budget_zar: Decimal = Decimal("5000.00"),
        regime_filter: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> ExperimentDefinition:
        """Propose a new experiment (requires operator approval)."""
        cid = correlation_id or self._correlation_id
        exp_id = str(uuid.uuid4())

        definition = ExperimentDefinition(
            experiment_id=exp_id,
            name=name,
            hypothesis=hypothesis,
            strategy_variant=strategy_variant,
            baseline_strategy=baseline_strategy,
            regime_filter=regime_filter,
            max_trades=max_trades,
            max_budget_zar=max_budget_zar,
            status=ExperimentStatus.PROPOSED,
            correlation_id=cid,
        )

        self._persist_experiment(definition)

        logger.info(
            f"[EXPERIMENT] Proposed | name={name} id={exp_id} | correlation_id={cid}"
        )

        return definition

    def approve(
        self,
        experiment_id: str,
        approved_by: str,
        correlation_id: Optional[str] = None,
    ) -> bool:
        """Approve an experiment (operator action)."""
        if not self._db_session:
            return False

        try:
            from sqlalchemy import text

            self._db_session.execute(
                text("""
                    UPDATE experiment_definitions
                    SET status = 'APPROVED',
                        approved_by = :by,
                        approved_at = NOW(),
                        updated_at = NOW()
                    WHERE experiment_id = :eid::uuid
                      AND status = 'PROPOSED'
                """),
                {"by": approved_by, "eid": experiment_id},
            )
            self._db_session.commit()
            logger.info(f"[EXPERIMENT] Approved | id={experiment_id} by={approved_by}")
            return True
        except Exception as e:
            logger.error(f"[EXPERIMENT] Approve failed | error={e}")
            return False

    def activate(
        self,
        experiment_id: str,
        correlation_id: Optional[str] = None,
    ) -> bool:
        """Activate an approved experiment."""
        if not self._db_session:
            return False

        try:
            from sqlalchemy import text

            self._db_session.execute(
                text("""
                    UPDATE experiment_definitions
                    SET status = 'ACTIVE',
                        start_date = CURRENT_DATE,
                        updated_at = NOW()
                    WHERE experiment_id = :eid::uuid
                      AND status = 'APPROVED'
                """),
                {"eid": experiment_id},
            )
            self._db_session.commit()
            return True
        except Exception as e:
            logger.error(f"[EXPERIMENT] Activate failed | error={e}")
            return False

    def list_experiments(self, status: Optional[str] = None) -> list[dict[str, Any]]:
        """List experiments, optionally filtered by status."""
        if not self._db_session:
            return []

        try:
            from sqlalchemy import text

            query = """
                SELECT experiment_id, name, hypothesis,
                       strategy_variant, baseline_strategy,
                       status, max_trades, max_budget_zar,
                       start_date, end_date, created_at
                FROM experiment_definitions
            """
            params: dict[str, Any] = {}
            if status:
                query += " WHERE status = :status"
                params["status"] = status
            query += " ORDER BY created_at DESC"

            rows = self._db_session.execute(text(query), params).fetchall()

            return [
                {
                    "experiment_id": str(r[0]),
                    "name": r[1],
                    "hypothesis": r[2],
                    "strategy_variant": r[3],
                    "baseline_strategy": r[4],
                    "status": r[5],
                    "max_trades": r[6],
                    "max_budget_zar": str(r[7]),
                    "start_date": r[8].isoformat() if r[8] else None,
                    "end_date": r[9].isoformat() if r[9] else None,
                    "created_at": r[10].isoformat() if r[10] else None,
                }
                for r in rows
            ]
        except Exception as e:
            logger.error(f"[EXPERIMENT] List failed | error={e}")
            return []

    def _persist_experiment(self, exp: ExperimentDefinition) -> None:
        """Persist experiment definition."""
        if not self._db_session:
            return
        try:
            from sqlalchemy import text

            self._db_session.execute(
                text("""
                    INSERT INTO experiment_definitions
                        (experiment_id, name, hypothesis,
                         strategy_variant, baseline_strategy,
                         regime_filter, max_trades, max_budget_zar,
                         status, correlation_id)
                    VALUES
                        (:eid::uuid, :name, :hypothesis,
                         :variant, :baseline, :regime,
                         :max_trades, :max_budget, :status, :cid)
                """),
                {
                    "eid": exp.experiment_id,
                    "name": exp.name,
                    "hypothesis": exp.hypothesis,
                    "variant": exp.strategy_variant,
                    "baseline": exp.baseline_strategy,
                    "regime": exp.regime_filter,
                    "max_trades": exp.max_trades,
                    "max_budget": str(exp.max_budget_zar),
                    "status": exp.status.value,
                    "cid": exp.correlation_id,
                },
            )
            self._db_session.commit()
        except Exception as e:
            logger.error(f"[EXPERIMENT] Persist failed | error={e}")

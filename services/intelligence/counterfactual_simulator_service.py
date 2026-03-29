"""
Counterfactual Simulator — What-If Replay Engine

Replays past decisions with alternative parameters to evaluate
what-if scenarios for learning and operator insight.

Priority: P2
"""

import json
import logging
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class CounterfactualRequest:
    """Request to simulate an alternative decision."""

    snapshot_id: str
    override_confidence: Optional[Decimal] = None
    override_mind_state: Optional[str] = None
    override_position_size: Optional[Decimal] = None
    requested_by: str = "system"

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "override_confidence": str(self.override_confidence) if self.override_confidence else None,
            "override_mind_state": self.override_mind_state,
            "override_position_size": str(self.override_position_size) if self.override_position_size else None,
            "requested_by": self.requested_by,
        }


@dataclass
class CounterfactualResult:
    """Result of a counterfactual simulation."""

    result_id: str
    snapshot_id: str
    overrides: dict[str, Any]
    original_outcome: dict[str, Any]
    counterfactual_outcome: dict[str, Any]
    delta_pnl_zar: Decimal
    conclusion: str
    correlation_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "result_id": self.result_id,
            "snapshot_id": self.snapshot_id,
            "overrides": self.overrides,
            "original_outcome": self.original_outcome,
            "counterfactual_outcome": self.counterfactual_outcome,
            "delta_pnl_zar": str(self.delta_pnl_zar),
            "conclusion": self.conclusion,
            "correlation_id": self.correlation_id,
        }


class CounterfactualSimulator:
    """
    Replays past decisions with modified parameters.

    Uses decision snapshots as the basis for simulation,
    then applies overrides to compute alternative outcomes.
    """

    def __init__(
        self,
        db_session: Optional[Any] = None,
        correlation_id: Optional[str] = None,
    ):
        self._db_session = db_session
        self._correlation_id = correlation_id or str(uuid.uuid4())

    def simulate(
        self,
        request: CounterfactualRequest,
        correlation_id: Optional[str] = None,
    ) -> Optional[CounterfactualResult]:
        """
        Run a counterfactual simulation against a stored snapshot.

        Args:
            request: Overrides to apply
            correlation_id: Tracking ID

        Returns:
            CounterfactualResult or None if snapshot not found
        """
        cid = correlation_id or self._correlation_id

        # Load original snapshot
        original = self._load_snapshot(request.snapshot_id)
        if not original:
            logger.warning(
                f"[COUNTERFACTUAL] Snapshot not found | "
                f"snapshot_id={request.snapshot_id}"
            )
            return None

        # Build overrides dict
        overrides: dict[str, Any] = {}
        if request.override_confidence is not None:
            overrides["confidence"] = str(request.override_confidence)
        if request.override_mind_state is not None:
            overrides["mind_state"] = request.override_mind_state
        if request.override_position_size is not None:
            overrides["position_size"] = str(request.override_position_size)

        # Compute counterfactual outcome
        original_pnl = Decimal(str(original.get("outcome_pnl_zar", "0")))
        original_size = Decimal(str(original.get("final_size_zar", "0")))

        cf_size = (
            request.override_position_size
            if request.override_position_size
            else original_size
        )

        # Simple proportional scaling for counterfactual
        if original_size > Decimal("0"):
            scale_factor = cf_size / original_size
            cf_pnl = original_pnl * scale_factor
        else:
            cf_pnl = Decimal("0")

        delta = cf_pnl - original_pnl

        if delta > Decimal("0"):
            conclusion = f"Would have improved by {delta} ZAR"
        elif delta < Decimal("0"):
            conclusion = f"Would have lost additional {abs(delta)} ZAR"
        else:
            conclusion = "No change in outcome"

        result = CounterfactualResult(
            result_id=str(uuid.uuid4()),
            snapshot_id=request.snapshot_id,
            overrides=overrides,
            original_outcome={
                "pnl_zar": str(original_pnl),
                "size_zar": str(original_size),
            },
            counterfactual_outcome={
                "pnl_zar": str(cf_pnl),
                "size_zar": str(cf_size),
            },
            delta_pnl_zar=delta,
            conclusion=conclusion,
            correlation_id=cid,
        )

        self._persist_result(result)

        logger.info(
            f"[COUNTERFACTUAL] Simulation complete | "
            f"snapshot={request.snapshot_id} delta={delta} | "
            f"correlation_id={cid}"
        )

        return result

    def _load_snapshot(self, snapshot_id: str) -> Optional[dict[str, Any]]:
        """Load a decision snapshot by ID."""
        if not self._db_session:
            return None

        try:
            from sqlalchemy import text

            row = self._db_session.execute(
                text("""
                    SELECT final_size_zar, outcome_pnl_zar,
                           confidence, mind_state, regime
                    FROM decision_snapshots
                    WHERE snapshot_id = :sid::uuid
                """),
                {"sid": snapshot_id},
            ).fetchone()

            if not row:
                return None

            return {
                "final_size_zar": str(row[0]),
                "outcome_pnl_zar": str(row[1]) if row[1] else "0",
                "confidence": str(row[2]),
                "mind_state": row[3],
                "regime": row[4],
            }
        except Exception as e:
            logger.error(
                f"[COUNTERFACTUAL] Failed to load snapshot | error={e}"
            )
            return None

    def _persist_result(self, result: CounterfactualResult) -> None:
        """Persist counterfactual result."""
        if not self._db_session:
            return
        try:
            from sqlalchemy import text

            self._db_session.execute(
                text("""
                    INSERT INTO counterfactual_results
                        (result_id, snapshot_id, overrides,
                         original_outcome, counterfactual_outcome,
                         delta_pnl_zar, conclusion,
                         requested_by, correlation_id)
                    VALUES
                        (:rid::uuid, :sid::uuid, :overrides,
                         :original, :counterfactual,
                         :delta, :conclusion,
                         :requested_by, :cid)
                """),
                {
                    "rid": result.result_id,
                    "sid": result.snapshot_id,
                    "overrides": json.dumps(result.overrides),
                    "original": json.dumps(result.original_outcome),
                    "counterfactual": json.dumps(result.counterfactual_outcome),
                    "delta": str(result.delta_pnl_zar),
                    "conclusion": result.conclusion,
                    "requested_by": "system",
                    "cid": result.correlation_id,
                },
            )
            self._db_session.commit()
        except Exception as e:
            logger.error(
                f"[COUNTERFACTUAL] Failed to persist result | error={e}"
            )

"""
Learning Worker — Periodic Learning Cycle Orchestrator

Runs on a schedule to update beliefs, reconcile budget,
evaluate mind state transitions, and check curriculum progress.

Ported from legacy learning_worker_v2.py.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


class LearningWorker:
    """
    Orchestrates the learning cycle:

    1. Collect new trade outcomes
    2. Update Bayesian beliefs
    3. Recalculate confidence metrics
    4. Update mind state
    5. Check curriculum progress
    6. Run contract enforcement
    7. Store learning snapshot

    Schedule:
        Every 5 min  — Light cycle (beliefs + mind state)
        Every 30 min — Full cycle (+ budget + curriculum)
        Daily 00:05  — Daily audit (budget reset, analytics, contract)
    """

    def __init__(
        self,
        db_session: Optional[Any] = None,
        bayesian_service: Optional[Any] = None,
        budget_service: Optional[Any] = None,
        mind_state_service: Optional[Any] = None,
        curriculum_scheduler: Optional[Any] = None,
        contract_enforcer: Optional[Any] = None,
        snapshot_service: Optional[Any] = None,
        correlation_id: Optional[str] = None,
    ):
        self._db_session = db_session
        self._bayesian = bayesian_service
        self._budget = budget_service
        self._mind_state = mind_state_service
        self._curriculum = curriculum_scheduler
        self._contract = contract_enforcer
        self._snapshot = snapshot_service
        self._correlation_id = correlation_id or str(uuid.uuid4())
        self._last_run: Optional[datetime] = None

    async def run_light_cycle(
        self, correlation_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Light cycle: Bayesian update + mind state check.
        Runs every 5 minutes.
        """
        cid = correlation_id or str(uuid.uuid4())
        start = datetime.now(timezone.utc)
        result: dict[str, Any] = {"cycle_type": "LIGHT", "correlation_id": cid}

        try:
            # Phase 1: Collect new outcomes
            outcomes = await self._collect_outcomes(cid)
            result["outcomes_processed"] = len(outcomes)

            # Phase 2: Bayesian update
            beliefs_updated = 0
            if self._bayesian and outcomes:
                for outcome in outcomes:
                    self._bayesian.update_beliefs(outcome, correlation_id=cid)
                    beliefs_updated += 1
            result["beliefs_updated"] = beliefs_updated

            # Phase 4: Mind state evaluation
            mind_state_before = (
                self._mind_state.current_state if self._mind_state else "CALM"
            )
            if self._mind_state:
                self._mind_state.evaluate_transitions(correlation_id=cid)
            mind_state_after = (
                self._mind_state.current_state if self._mind_state else "CALM"
            )
            result["mind_state_before"] = mind_state_before
            result["mind_state_after"] = mind_state_after

            elapsed = datetime.now(timezone.utc) - start
            duration_ms = int(elapsed.total_seconds() * 1000)
            result["duration_ms"] = duration_ms

            # Phase 7: Snapshot
            if self._snapshot:
                self._snapshot.record_learning_cycle(
                    cycle_type="LIGHT",
                    outcomes_processed=len(outcomes),
                    beliefs_updated=beliefs_updated,
                    budget_reconciled=False,
                    mind_state_before=mind_state_before,
                    mind_state_after=mind_state_after,
                    curriculum_phase=(
                        self._curriculum.get_state().current_phase
                        if self._curriculum
                        else 1
                    ),
                    contract_violations=0,
                    violation_details=[],
                    metrics_snapshot=result,
                    duration_ms=duration_ms,
                    correlation_id=cid,
                )

            self._last_run = datetime.now(timezone.utc)

            logger.info(
                f"[LEARNING-WORKER] Light cycle complete | "
                f"outcomes={len(outcomes)} beliefs={beliefs_updated} "
                f"mind_state={mind_state_after} duration={duration_ms}ms | "
                f"correlation_id={cid}"
            )

        except Exception as e:
            logger.error(
                f"[LEARNING-WORKER] Light cycle failed | error={e} | "
                f"correlation_id={cid}"
            )
            result["error"] = str(e)

        return result

    async def run_full_cycle(
        self, correlation_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Full cycle: Light cycle + budget reconcile + curriculum check.
        Runs every 30 minutes.
        """
        cid = correlation_id or str(uuid.uuid4())
        start = datetime.now(timezone.utc)

        # Run light cycle first
        result = await self.run_light_cycle(cid)
        result["cycle_type"] = "FULL"

        try:
            # Phase 3: Budget reconciliation
            if self._budget:
                budget_state = self._budget.reconcile(correlation_id=cid)
                result["budget_reconciled"] = True
                result["remaining_budget"] = str(budget_state.remaining_budget)
            else:
                result["budget_reconciled"] = False

            # Phase 5: Curriculum check
            if self._curriculum:
                self._curriculum.advance_if_ready(correlation_id=cid)
                state = self._curriculum.get_state()
                result["curriculum_phase"] = state.current_phase
                result["advancement_requested"] = state.advancement_requested

            # Phase 6: Contract enforcement
            violations = 0
            violation_details: list[dict[str, Any]] = []
            if self._contract:
                enforcement = self._contract.validate_all(
                    mind_state=(
                        self._mind_state.current_state
                        if self._mind_state
                        else "CALM"
                    ),
                    curriculum_phase=(
                        self._curriculum.get_state().current_phase
                        if self._curriculum
                        else 1
                    ),
                )
                violations = len(enforcement.violations)
                violation_details = [v.to_dict() for v in enforcement.violations]

            result["contract_violations"] = violations

            elapsed = datetime.now(timezone.utc) - start
            result["duration_ms"] = int(elapsed.total_seconds() * 1000)

            # Record full cycle snapshot
            if self._snapshot:
                self._snapshot.record_learning_cycle(
                    cycle_type="FULL",
                    outcomes_processed=result.get("outcomes_processed", 0),
                    beliefs_updated=result.get("beliefs_updated", 0),
                    budget_reconciled=result.get("budget_reconciled", False),
                    mind_state_before=result.get("mind_state_before", "CALM"),
                    mind_state_after=result.get("mind_state_after", "CALM"),
                    curriculum_phase=result.get("curriculum_phase", 1),
                    contract_violations=violations,
                    violation_details=violation_details,
                    metrics_snapshot=result,
                    duration_ms=result["duration_ms"],
                    correlation_id=cid,
                )

            logger.info(
                f"[LEARNING-WORKER] Full cycle complete | "
                f"budget_reconciled={result.get('budget_reconciled')} "
                f"violations={violations} "
                f"duration={result['duration_ms']}ms | "
                f"correlation_id={cid}"
            )

        except Exception as e:
            logger.error(
                f"[LEARNING-WORKER] Full cycle failed | error={e} | "
                f"correlation_id={cid}"
            )
            result["error"] = str(e)

        return result

    async def _collect_outcomes(
        self, correlation_id: str,
    ) -> list[dict[str, Any]]:
        """Collect new trade outcomes since last run."""
        if not self._db_session:
            return []

        try:
            from sqlalchemy import text

            since = self._last_run or datetime(2020, 1, 1, tzinfo=timezone.utc)

            rows = self._db_session.execute(
                text("""
                    SELECT correlation_id, symbol, side, pnl_zar,
                           status, updated_at
                    FROM trade_lifecycle
                    WHERE status IN ('FILLED', 'CLOSED')
                      AND updated_at > :since
                    ORDER BY updated_at ASC
                    LIMIT 100
                """),
                {"since": since},
            ).fetchall()

            return [
                {
                    "correlation_id": r[0],
                    "symbol": r[1],
                    "side": r[2],
                    "pnl_zar": str(r[3]) if r[3] else "0",
                    "status": r[4],
                    "was_correct": r[3] is not None and r[3] > 0,
                }
                for r in rows
            ]
        except Exception as e:
            logger.error(
                f"[LEARNING-WORKER] Failed to collect outcomes | error={e}"
            )
            return []

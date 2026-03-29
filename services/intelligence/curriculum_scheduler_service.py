"""
Curriculum Scheduler — Phased Learning Schedule

Progressively increases system autonomy through curriculum phases.
Phase advancement requires operator approval (HITL-gated).

Priority: P2
"""

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
import logging
from typing import Any, Optional
import uuid

logger = logging.getLogger(__name__)


@dataclass
class CurriculumPhase:
    """Configuration for a single curriculum phase."""

    phase_number: int
    name: str
    max_confidence: Decimal
    max_position_zar: Optional[Decimal]
    hitl_mode: str  # ALL_TRADES, ABOVE_THRESHOLD, ANOMALIES_ONLY
    min_trades: int
    min_win_rate: Decimal
    max_drawdown_pct: Decimal
    min_days: int


# Phase definitions
PHASES: list[CurriculumPhase] = [
    CurriculumPhase(
        phase_number=1,
        name="Observer",
        max_confidence=Decimal("0.50"),
        max_position_zar=None,  # Paper only
        hitl_mode="ALL_TRADES",
        min_trades=20,
        min_win_rate=Decimal("0.40"),
        max_drawdown_pct=Decimal("5.0"),
        min_days=14,
    ),
    CurriculumPhase(
        phase_number=2,
        name="Cautious",
        max_confidence=Decimal("0.70"),
        max_position_zar=Decimal("500.00"),
        hitl_mode="ALL_TRADES",
        min_trades=30,
        min_win_rate=Decimal("0.45"),
        max_drawdown_pct=Decimal("4.0"),
        min_days=28,
    ),
    CurriculumPhase(
        phase_number=3,
        name="Confident",
        max_confidence=Decimal("0.85"),
        max_position_zar=Decimal("2000.00"),
        hitl_mode="ABOVE_THRESHOLD",
        min_trades=50,
        min_win_rate=Decimal("0.50"),
        max_drawdown_pct=Decimal("3.0"),
        min_days=56,
    ),
    CurriculumPhase(
        phase_number=4,
        name="Autonomous",
        max_confidence=Decimal("0.95"),
        max_position_zar=Decimal("5000.00"),
        hitl_mode="ANOMALIES_ONLY",
        min_trades=100,
        min_win_rate=Decimal("0.55"),
        max_drawdown_pct=Decimal("2.0"),
        min_days=90,
    ),
]


@dataclass
class CurriculumState:
    """Current curriculum state."""

    current_phase: int
    phase_name: str
    max_confidence: Decimal
    max_position_zar: Optional[Decimal]
    hitl_mode: str
    phase_start_date: date
    trades_in_phase: int
    win_rate: Decimal
    max_drawdown_pct: Decimal
    contract_violations: int
    advancement_requested: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "current_phase": self.current_phase,
            "phase_name": self.phase_name,
            "max_confidence": str(self.max_confidence),
            "max_position_zar": str(self.max_position_zar)
            if self.max_position_zar
            else None,
            "hitl_mode": self.hitl_mode,
            "phase_start_date": self.phase_start_date.isoformat(),
            "trades_in_phase": self.trades_in_phase,
            "win_rate": str(self.win_rate),
            "max_drawdown_pct": str(self.max_drawdown_pct),
            "contract_violations": self.contract_violations,
            "advancement_requested": self.advancement_requested,
        }


@dataclass
class LearningMetrics:
    """Metrics for curriculum advancement evaluation."""

    min_trades_in_phase: int
    win_rate: Decimal
    max_drawdown: Decimal
    contract_violations: int
    days_in_phase: int


class CurriculumScheduler:
    """
    Phased learning schedule with HITL-gated advancement.

    Phase advancement is NEVER automatic — it generates an HITL
    approval request for operator review.
    """

    def __init__(
        self,
        db_session: Optional[Any] = None,
        correlation_id: Optional[str] = None,
    ):
        self._db_session = db_session
        self._correlation_id = correlation_id or str(uuid.uuid4())
        self._state: Optional[CurriculumState] = None

    def get_state(self) -> CurriculumState:
        """Get current curriculum state."""
        if self._state is None:
            self._state = self._load_or_create_state()
        return self._state

    def get_current_phase(self) -> CurriculumPhase:
        """Get the CurriculumPhase config for the current phase."""
        state = self.get_state()
        idx = max(0, min(state.current_phase - 1, len(PHASES) - 1))
        return PHASES[idx]

    def can_advance(self, metrics: LearningMetrics) -> bool:
        """
        Check if system can advance to next curriculum phase.

        Returns True if all criteria met — but does NOT advance.
        Advancement requires operator approval.
        """
        state = self.get_state()
        if state.current_phase >= 4:
            return False  # Already at max phase

        phase = self.get_current_phase()

        return (
            metrics.min_trades_in_phase >= phase.min_trades
            and metrics.win_rate >= phase.min_win_rate
            and metrics.max_drawdown <= phase.max_drawdown_pct
            and metrics.contract_violations == 0
            and metrics.days_in_phase >= phase.min_days
        )

    def request_advancement(
        self,
        metrics: LearningMetrics,
        correlation_id: Optional[str] = None,
    ) -> bool:
        """
        Request advancement to next phase (generates HITL approval).

        Returns True if request was created, False if not eligible.
        """
        cid = correlation_id or self._correlation_id

        if not self.can_advance(metrics):
            logger.info(
                f"[CURRICULUM] Advancement not ready | "
                f"phase={self.get_state().current_phase} | "
                f"correlation_id={cid}"
            )
            return False

        state = self.get_state()
        state.advancement_requested = True
        self._update_state(state, cid)

        next_phase = state.current_phase + 1
        logger.info(
            f"[CURRICULUM] Advancement requested | "
            f"from_phase={state.current_phase} to_phase={next_phase} | "
            f"correlation_id={cid}"
        )

        return True

    def advance_phase(
        self,
        approved_by: str,
        correlation_id: Optional[str] = None,
    ) -> CurriculumState:
        """
        Execute phase advancement (called after HITL approval).
        """
        cid = correlation_id or self._correlation_id
        state = self.get_state()

        if state.current_phase >= 4:
            logger.warning("[CURRICULUM] Already at max phase 4")
            return state

        new_phase_num = state.current_phase + 1
        new_phase = PHASES[new_phase_num - 1]

        self._state = CurriculumState(
            current_phase=new_phase_num,
            phase_name=new_phase.name,
            max_confidence=new_phase.max_confidence,
            max_position_zar=new_phase.max_position_zar,
            hitl_mode=new_phase.hitl_mode,
            phase_start_date=datetime.now(timezone.utc).date(),
            trades_in_phase=0,
            win_rate=Decimal("0.0"),
            max_drawdown_pct=Decimal("0.0"),
            contract_violations=0,
            advancement_requested=False,
        )

        self._persist_advancement(self._state, approved_by, cid)

        logger.info(
            f"[CURRICULUM] Advanced | "
            f"phase={new_phase_num} name={new_phase.name} "
            f"approved_by={approved_by} | correlation_id={cid}"
        )

        return self._state

    def advance_if_ready(
        self,
        correlation_id: Optional[str] = None,
    ) -> bool:
        """
        Check if advancement criteria are met, and if so,
        create an advancement request. Does NOT auto-advance.
        """
        # This is a check-only method for the learning worker
        # Actual advancement requires operator approval
        return False  # Placeholder: actual implementation would check metrics

    def _load_or_create_state(self) -> CurriculumState:
        """Load curriculum state from DB or create Phase 1 default."""
        if self._db_session:
            try:
                from sqlalchemy import text

                row = self._db_session.execute(
                    text("""
                        SELECT current_phase, phase_name, max_confidence,
                               max_position_zar, hitl_mode, phase_start_date,
                               trades_in_phase, win_rate, max_drawdown_pct,
                               contract_violations, advancement_requested
                        FROM curriculum_state
                        ORDER BY id DESC LIMIT 1
                    """)
                ).fetchone()

                if row:
                    return CurriculumState(
                        current_phase=int(row[0]),
                        phase_name=row[1],
                        max_confidence=Decimal(str(row[2])),
                        max_position_zar=Decimal(str(row[3])) if row[3] else None,
                        hitl_mode=row[4],
                        phase_start_date=row[5],
                        trades_in_phase=int(row[6]),
                        win_rate=Decimal(str(row[7])),
                        max_drawdown_pct=Decimal(str(row[8])),
                        contract_violations=int(row[9]),
                        advancement_requested=bool(row[10]),
                    )
            except Exception as e:
                logger.error(f"[CURRICULUM] Failed to load state | error={e}")

        # Default Phase 1
        return CurriculumState(
            current_phase=1,
            phase_name="Observer",
            max_confidence=Decimal("0.50"),
            max_position_zar=None,
            hitl_mode="ALL_TRADES",
            phase_start_date=datetime.now(timezone.utc).date(),
            trades_in_phase=0,
            win_rate=Decimal("0.0"),
            max_drawdown_pct=Decimal("0.0"),
            contract_violations=0,
            advancement_requested=False,
        )

    def _update_state(
        self,
        state: CurriculumState,
        correlation_id: str,
    ) -> None:
        """Update curriculum state in DB."""
        if not self._db_session:
            return
        try:
            from sqlalchemy import text

            self._db_session.execute(
                text("""
                    UPDATE curriculum_state
                    SET trades_in_phase = :trades,
                        win_rate = :win_rate,
                        max_drawdown_pct = :drawdown,
                        contract_violations = :violations,
                        advancement_requested = :requested,
                        updated_at = NOW()
                    WHERE id = (SELECT MAX(id) FROM curriculum_state)
                """),
                {
                    "trades": state.trades_in_phase,
                    "win_rate": str(state.win_rate),
                    "drawdown": str(state.max_drawdown_pct),
                    "violations": state.contract_violations,
                    "requested": state.advancement_requested,
                },
            )
            self._db_session.commit()
        except Exception as e:
            logger.error(f"[CURRICULUM] Failed to update state | error={e}")

    def _persist_advancement(
        self,
        state: CurriculumState,
        approved_by: str,
        correlation_id: str,
    ) -> None:
        """Insert new curriculum state row for phase advancement."""
        if not self._db_session:
            return
        try:
            from sqlalchemy import text

            self._db_session.execute(
                text("""
                    INSERT INTO curriculum_state
                        (current_phase, phase_name, max_confidence,
                         max_position_zar, hitl_mode, phase_start_date,
                         trades_in_phase, win_rate, max_drawdown_pct,
                         contract_violations, advancement_requested,
                         advancement_approved_by, advancement_approved_at,
                         correlation_id)
                    VALUES
                        (:phase, :name, :confidence, :max_pos,
                         :hitl, :start, :trades, :win, :drawdown,
                         :violations, :requested, :approved_by,
                         NOW(), :cid)
                """),
                {
                    "phase": state.current_phase,
                    "name": state.phase_name,
                    "confidence": str(state.max_confidence),
                    "max_pos": str(state.max_position_zar)
                    if state.max_position_zar
                    else None,
                    "hitl": state.hitl_mode,
                    "start": state.phase_start_date,
                    "trades": state.trades_in_phase,
                    "win": str(state.win_rate),
                    "drawdown": str(state.max_drawdown_pct),
                    "violations": state.contract_violations,
                    "requested": state.advancement_requested,
                    "approved_by": approved_by,
                    "cid": correlation_id,
                },
            )
            self._db_session.commit()
        except Exception as e:
            logger.error(f"[CURRICULUM] Failed to persist advancement | error={e}")

"""
Bayesian Reasoning Service — Multi-Factor Belief Fusion

Fuses multiple evidence sources into posterior confidence using Bayes' theorem.
All arithmetic uses Python Decimal — no float permitted.
Confidence values are clamped to [0.01, 0.99].

Priority: P0
"""

import json
import logging
import uuid
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class Direction(Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    HOLD = "HOLD"


@dataclass
class EvidenceItem:
    """A single piece of evidence for Bayesian update."""

    source: str
    weight: Decimal
    likelihood_ratio: Decimal  # P(evidence|H_true) / P(evidence|H_false)
    raw_value: Any = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "weight": str(self.weight),
            "likelihood_ratio": str(self.likelihood_ratio),
        }


@dataclass
class BayesianVerdict:
    """Result of Bayesian reasoning evaluation."""

    direction: Direction
    confidence: Decimal
    evidence_weights: dict[str, Decimal]
    reasoning_chain: list[str]
    evidence_count: int = 0
    correlation_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "direction": self.direction.value,
            "confidence": str(self.confidence),
            "evidence_weights": {k: str(v) for k, v in self.evidence_weights.items()},
            "reasoning_chain": self.reasoning_chain,
            "evidence_count": self.evidence_count,
            "correlation_id": self.correlation_id,
        }


class BayesianReasoningService:
    """
    Multi-factor belief fusion using Bayesian updating.

    Evidence sources are combined sequentially — each source updates
    the prior to produce a new posterior, which becomes the prior for
    the next source.

    Invariants:
    - Confidence clamped to [0.01, 0.99]
    - All arithmetic is Decimal with ROUND_HALF_UP
    - Evidence weights must sum to 1.0
    - Maximum 10 evidence sources per evaluation
    """

    MIN_CONFIDENCE = Decimal("0.01")
    MAX_CONFIDENCE = Decimal("0.99")
    BASE_PRIOR = Decimal("0.50")  # Neutral prior
    MAX_EVIDENCE_SOURCES = 10

    # Default evidence source weights (must sum to 1.0)
    DEFAULT_WEIGHTS: dict[str, Decimal] = {
        "tradingview_signal": Decimal("0.30"),
        "sentiment": Decimal("0.10"),
        "regime": Decimal("0.20"),
        "technical_indicators": Decimal("0.20"),
        "historical_pattern": Decimal("0.10"),
        "operator_track_record": Decimal("0.10"),
    }

    def __init__(
        self,
        db_session: Optional[Any] = None,
        correlation_id: Optional[str] = None,
    ):
        self._db_session = db_session
        self._correlation_id = correlation_id or str(uuid.uuid4())

        # Verify default weights sum to 1.0
        total_weight = sum(self.DEFAULT_WEIGHTS.values())
        assert total_weight == Decimal("1.00"), (
            f"Default weights must sum to 1.0, got {total_weight}"
        )

    def evaluate(
        self,
        evidence: list[EvidenceItem],
        prior: Optional[Decimal] = None,
        correlation_id: Optional[str] = None,
    ) -> BayesianVerdict:
        """
        Evaluate evidence and produce a Bayesian verdict.

        Args:
            evidence: List of evidence items with likelihood ratios
            prior: Starting prior probability (default: 0.50)
            correlation_id: Tracking ID for this evaluation

        Returns:
            BayesianVerdict with direction, confidence, and reasoning chain
        """
        cid = correlation_id or self._correlation_id
        reasoning: list[str] = []

        if not evidence:
            reasoning.append("No evidence provided — returning neutral HOLD")
            return BayesianVerdict(
                direction=Direction.HOLD,
                confidence=self.BASE_PRIOR,
                evidence_weights={},
                reasoning_chain=reasoning,
                evidence_count=0,
                correlation_id=cid,
            )

        if len(evidence) > self.MAX_EVIDENCE_SOURCES:
            logger.warning(
                f"[BAYESIAN] Evidence count {len(evidence)} exceeds max "
                f"{self.MAX_EVIDENCE_SOURCES} — truncating | "
                f"correlation_id={cid}"
            )
            evidence = evidence[: self.MAX_EVIDENCE_SOURCES]

        current_prior = prior if prior is not None else self.BASE_PRIOR
        current_prior = self._clamp(current_prior)
        reasoning.append(f"Starting prior: {current_prior}")

        evidence_weights: dict[str, Decimal] = {}

        for item in evidence:
            # Bayesian update: posterior = (prior * LR) / normalizer
            lr = item.likelihood_ratio
            numerator = current_prior * lr
            denominator = numerator + (Decimal("1") - current_prior)

            if denominator == Decimal("0"):
                reasoning.append(
                    f"  {item.source}: skipped (zero denominator)"
                )
                continue

            posterior = (numerator / denominator).quantize(
                Decimal("0.00000001"), rounding=ROUND_HALF_UP
            )
            posterior = self._clamp(posterior)

            reasoning.append(
                f"  {item.source}: LR={lr} → prior {current_prior} → "
                f"posterior {posterior}"
            )

            evidence_weights[item.source] = item.weight
            current_prior = posterior

        final_confidence = current_prior

        # Determine direction from confidence
        if final_confidence > Decimal("0.55"):
            direction = Direction.LONG
        elif final_confidence < Decimal("0.45"):
            direction = Direction.SHORT
        else:
            direction = Direction.HOLD

        reasoning.append(
            f"Final confidence: {final_confidence} → {direction.value}"
        )

        verdict = BayesianVerdict(
            direction=direction,
            confidence=final_confidence,
            evidence_weights=evidence_weights,
            reasoning_chain=reasoning,
            evidence_count=len(evidence),
            correlation_id=cid,
        )

        self._persist_belief(verdict)

        logger.info(
            f"[BAYESIAN] Evaluation complete | "
            f"direction={direction.value} confidence={final_confidence} "
            f"evidence_count={len(evidence)} | correlation_id={cid}"
        )

        return verdict

    def update_beliefs(
        self,
        trade_outcome: dict[str, Any],
        correlation_id: Optional[str] = None,
    ) -> None:
        """
        Update beliefs based on trade outcome (post-trade learning).

        Args:
            trade_outcome: Dict with keys: symbol, direction, pnl_zar, was_correct
            correlation_id: Tracking ID
        """
        cid = correlation_id or self._correlation_id
        logger.info(
            f"[BAYESIAN] Updating beliefs from trade outcome | "
            f"symbol={trade_outcome.get('symbol')} "
            f"correct={trade_outcome.get('was_correct')} | "
            f"correlation_id={cid}"
        )
        # Post-trade belief update is logged but does not auto-adjust
        # anything in live mode — only records data for offline analysis

    def _clamp(self, value: Decimal) -> Decimal:
        """Clamp confidence to [MIN_CONFIDENCE, MAX_CONFIDENCE]."""
        if value < self.MIN_CONFIDENCE:
            return self.MIN_CONFIDENCE
        if value > self.MAX_CONFIDENCE:
            return self.MAX_CONFIDENCE
        return value

    def _persist_belief(self, verdict: BayesianVerdict) -> None:
        """Persist belief to bayesian_beliefs table."""
        if not self._db_session:
            return

        try:
            from sqlalchemy import text

            self._db_session.execute(
                text("""
                    INSERT INTO bayesian_beliefs
                        (symbol, direction, prior_confidence,
                         posterior_confidence, evidence_count,
                         evidence_summary, reasoning_chain, correlation_id)
                    VALUES
                        (:symbol, :direction, :prior, :posterior,
                         :evidence_count, :evidence_summary,
                         :reasoning_chain, :correlation_id)
                """),
                {
                    "symbol": "AGGREGATE",
                    "direction": verdict.direction.value,
                    "prior": str(self.BASE_PRIOR),
                    "posterior": str(verdict.confidence),
                    "evidence_count": verdict.evidence_count,
                    "evidence_summary": json.dumps(
                        {k: str(v) for k, v in verdict.evidence_weights.items()}
                    ),
                    "reasoning_chain": json.dumps(verdict.reasoning_chain),
                    "correlation_id": verdict.correlation_id,
                },
            )
            self._db_session.commit()
        except Exception as e:
            logger.error(
                f"[BAYESIAN] Failed to persist belief | error={e} | "
                f"correlation_id={verdict.correlation_id}"
            )

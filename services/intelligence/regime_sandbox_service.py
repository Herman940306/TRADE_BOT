"""
Regime Sandbox Service — Market Regime Detection & Strategy Sandboxing

Classifies current market regime and ensures strategies only execute
in their declared regimes.

Priority: P1
"""

import json
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class Regime(Enum):
    TRENDING_UP = "TRENDING_UP"
    TRENDING_DOWN = "TRENDING_DOWN"
    RANGING = "RANGING"
    VOLATILE = "VOLATILE"
    UNKNOWN = "UNKNOWN"


# Which strategies are allowed in which regimes
STRATEGY_REGIME_MAP: dict[str, list[Regime]] = {
    "momentum_breakout": [Regime.TRENDING_UP],
    "mean_reversion": [Regime.RANGING],
    "trend_follow": [Regime.TRENDING_UP, Regime.TRENDING_DOWN],
    "defensive_hedge": [Regime.VOLATILE],
}


@dataclass
class RegimeObservation:
    """A regime classification for a symbol/time window."""

    symbol: str
    regime: Regime
    confidence: Decimal
    adx_value: Optional[Decimal] = None
    atr_value: Optional[Decimal] = None
    sma_20_value: Optional[Decimal] = None
    bollinger_width: Optional[Decimal] = None
    correlation_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "regime": self.regime.value,
            "confidence": str(self.confidence),
            "adx_value": str(self.adx_value) if self.adx_value else None,
            "atr_value": str(self.atr_value) if self.atr_value else None,
            "correlation_id": self.correlation_id,
        }


@dataclass
class SandboxVerdict:
    """Result of strategy-regime compatibility check."""

    allowed: bool
    strategy_name: str
    current_regime: Regime
    allowed_regimes: list[Regime]
    reason: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "strategy_name": self.strategy_name,
            "current_regime": self.current_regime.value,
            "allowed_regimes": [r.value for r in self.allowed_regimes],
            "reason": self.reason,
        }


class RegimeSandboxService:
    """
    Market regime detection and strategy sandboxing.

    Regime Classification:
        TRENDING_UP:    ADX > 25, price > 20-SMA, positive slope
        TRENDING_DOWN:  ADX > 25, price < 20-SMA, negative slope
        RANGING:        ADX < 20, Bollinger width contracting
        VOLATILE:       ATR spike > 2x average
        UNKNOWN:        Insufficient data or conflicting signals
    """

    ADX_TREND_THRESHOLD = Decimal("25")
    ADX_RANGE_THRESHOLD = Decimal("20")
    ATR_SPIKE_MULTIPLIER = Decimal("2.0")

    def __init__(
        self,
        db_session: Optional[Any] = None,
        correlation_id: Optional[str] = None,
    ):
        self._db_session = db_session
        self._correlation_id = correlation_id or str(uuid.uuid4())
        self._current_regime: dict[str, Regime] = {}

    def classify_regime(
        self,
        symbol: str,
        adx: Optional[Decimal] = None,
        atr_current: Optional[Decimal] = None,
        atr_average: Optional[Decimal] = None,
        price: Optional[Decimal] = None,
        sma_20: Optional[Decimal] = None,
        bollinger_width: Optional[Decimal] = None,
        correlation_id: Optional[str] = None,
    ) -> RegimeObservation:
        """
        Classify current market regime for a symbol.

        Returns:
            RegimeObservation with classified regime
        """
        cid = correlation_id or self._correlation_id
        regime = Regime.UNKNOWN
        confidence = Decimal("0.50")

        # Rule-based classification
        if adx is not None and price is not None and sma_20 is not None:
            if adx > self.ADX_TREND_THRESHOLD:
                if price > sma_20:
                    regime = Regime.TRENDING_UP
                    confidence = Decimal("0.75")
                else:
                    regime = Regime.TRENDING_DOWN
                    confidence = Decimal("0.75")
            elif adx < self.ADX_RANGE_THRESHOLD:
                regime = Regime.RANGING
                confidence = Decimal("0.65")

        # ATR spike override
        if (
            atr_current is not None
            and atr_average is not None
            and atr_average > Decimal("0")
        ):
            spike_ratio = atr_current / atr_average
            if spike_ratio > self.ATR_SPIKE_MULTIPLIER:
                regime = Regime.VOLATILE
                confidence = Decimal("0.80")

        self._current_regime[symbol] = regime

        observation = RegimeObservation(
            symbol=symbol,
            regime=regime,
            confidence=confidence,
            adx_value=adx,
            atr_value=atr_current,
            sma_20_value=sma_20,
            bollinger_width=bollinger_width,
            correlation_id=cid,
        )

        self._persist_observation(observation)

        logger.info(
            f"[REGIME] Classified | symbol={symbol} "
            f"regime={regime.value} confidence={confidence} | "
            f"correlation_id={cid}"
        )

        return observation

    def check_strategy_allowed(
        self,
        strategy_name: str,
        symbol: str,
    ) -> SandboxVerdict:
        """
        Check if a strategy is allowed in the current regime for a symbol.
        """
        current = self._current_regime.get(symbol, Regime.UNKNOWN)
        allowed_regimes = STRATEGY_REGIME_MAP.get(strategy_name, list(Regime))

        is_allowed = current in allowed_regimes or current == Regime.UNKNOWN

        if not is_allowed:
            logger.warning(
                f"[REGIME] Strategy blocked | strategy={strategy_name} "
                f"regime={current.value} allowed={[r.value for r in allowed_regimes]}"
            )

        return SandboxVerdict(
            allowed=is_allowed,
            strategy_name=strategy_name,
            current_regime=current,
            allowed_regimes=allowed_regimes,
            reason=None if is_allowed else (
                f"Strategy '{strategy_name}' not allowed in "
                f"regime '{current.value}'"
            ),
        )

    def get_current_regime(self, symbol: str) -> Regime:
        """Get current regime for a symbol."""
        return self._current_regime.get(symbol, Regime.UNKNOWN)

    def _persist_observation(self, obs: RegimeObservation) -> None:
        """Persist regime observation."""
        if not self._db_session:
            return
        try:
            from sqlalchemy import text

            now = datetime.now(timezone.utc)
            self._db_session.execute(
                text("""
                    INSERT INTO regime_observations
                        (symbol, regime, adx_value, atr_value,
                         sma_20_value, bollinger_width, confidence,
                         window_start, window_end, correlation_id)
                    VALUES
                        (:symbol, :regime, :adx, :atr, :sma,
                         :bw, :confidence, :start, :end, :cid)
                """),
                {
                    "symbol": obs.symbol,
                    "regime": obs.regime.value,
                    "adx": str(obs.adx_value) if obs.adx_value else None,
                    "atr": str(obs.atr_value) if obs.atr_value else None,
                    "sma": str(obs.sma_20_value) if obs.sma_20_value else None,
                    "bw": str(obs.bollinger_width) if obs.bollinger_width else None,
                    "confidence": str(obs.confidence),
                    "start": now,
                    "end": now,
                    "cid": obs.correlation_id,
                },
            )
            self._db_session.commit()
        except Exception as e:
            logger.error(
                f"[REGIME] Failed to persist observation | error={e}"
            )

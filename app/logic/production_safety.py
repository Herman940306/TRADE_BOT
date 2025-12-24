"""
Production Safety Module - Sovereign Tier Infrastructure

Reliability Level: L6 Critical
Input Constraints: All financial values must be decimal.Decimal
Side Effects: May trigger Kill Switch, writes to audit logs

This module implements the core safety mechanisms for Project Autonomous Alpha:
- Equity_Module: ZAR-standardized equity calculations
- Kill_Switch_Module: Emergency capital protection

Python 3.8 Compatible - No union type hints (X | None)
"""

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_EVEN, InvalidOperation
from enum import Enum
from typing import Optional, List, Dict, Any
import asyncio
import time
import logging
from datetime import datetime, timezone

# Configure logging with unique error codes
logger = logging.getLogger("production_safety")


# =============================================================================
# ENUMS
# =============================================================================

class TriggerReason(Enum):
    """
    Kill Switch trigger reasons.
    
    Reliability Level: L6 Critical
    """
    RED_HEALTH = "RED_HEALTH"
    ZAR_FLOOR_BREACH = "ZAR_FLOOR_BREACH"
    MANUAL_OVERRIDE = "MANUAL_OVERRIDE"
    L6_LOCKDOWN = "L6_LOCKDOWN"
    SSE_RECONNECT_FAIL = "SSE_RECONNECT_FAIL"


class HealthStatus(Enum):
    """
    Bot health status levels.
    
    Reliability Level: L5 High
    """
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    RED = "RED"


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class EquitySnapshot:
    """
    Point-in-time equity snapshot in ZAR.
    
    Reliability Level: L6 Critical
    Input Constraints: net_equity_zar must be decimal.Decimal
    Side Effects: None
    """
    net_equity_zar: Decimal
    formatted: str  # "R 123,456.78"
    fx_rate_usd_zar: Decimal
    fx_rate_timestamp_utc: str
    fx_rate_stale: bool
    below_floor: bool
    zar_floor: Decimal
    calculation_timestamp_utc: str


@dataclass
class NetAlphaSnapshot:
    """
    Net Alpha calculation result (Gross Profit - Operational Cost).
    
    Reliability Level: L6 Critical
    Input Constraints: All monetary values must be decimal.Decimal
    Side Effects: None
    
    Sprint 6: BudgetGuard-ZAR Integration
    Property 21: Net Alpha Decimal Integrity
    """
    gross_profit_zar: Decimal
    operational_cost_zar: Decimal
    net_alpha_zar: Decimal
    formatted: str  # "R X,XXX.XX"
    operational_cost_stale: bool
    calculation_timestamp_utc: str
    correlation_id: str


@dataclass
class KillSwitchResult:
    """
    Result of Kill Switch execution.
    
    Reliability Level: L6 Critical
    Input Constraints: None
    Side Effects: Closes positions, cancels orders, revokes API
    """
    trigger_reason: TriggerReason
    positions_closed: int
    orders_cancelled: int
    api_revoked: bool
    total_execution_time_ms: int
    audit_record_id: str
    success: bool
    error_message: Optional[str] = None


@dataclass
class AuditRecord:
    """
    Immutable audit log entry.
    
    Reliability Level: L6 Critical
    Input Constraints: correlation_id required
    Side Effects: Written to PostgreSQL
    """
    id: str
    correlation_id: str
    event_type: str
    event_data: Dict[str, Any]
    timestamp_utc: str
    checksum: str


# =============================================================================
# CONSTANTS
# =============================================================================

# Default ZAR floor - can be overridden via environment
DEFAULT_ZAR_FLOOR = Decimal("50000.00")

# FX rate staleness threshold in seconds
FX_RATE_STALE_THRESHOLD_SECONDS = 300  # 5 minutes

# Kill Switch execution SLA in milliseconds
KILL_SWITCH_SLA_MS = 5000


# =============================================================================
# EQUITY MODULE
# =============================================================================

class EquityModule:
    """
    ZAR-standardized equity calculations with floor breach detection.
    
    Reliability Level: L6 Critical
    Input Constraints: Valid exchange connection required
    Side Effects: May trigger Kill Switch on floor breach
    
    All calculations use decimal.Decimal with ROUND_HALF_EVEN (Banker's Rounding).
    """
    
    def __init__(
        self,
        zar_floor: Optional[Decimal] = None,
        kill_switch_callback: Optional[Any] = None
    ) -> None:
        """
        Initialize Equity Module.
        
        Args:
            zar_floor: Minimum equity threshold in ZAR. Defaults to R 50,000.
            kill_switch_callback: Async callback to trigger Kill Switch.
        """
        self._zar_floor: Decimal = zar_floor or DEFAULT_ZAR_FLOOR
        self._kill_switch_callback = kill_switch_callback
        self._last_fx_rate: Optional[Decimal] = None
        self._last_fx_rate_timestamp: Optional[datetime] = None
        
    @property
    def zar_floor(self) -> Decimal:
        """Get current ZAR floor threshold."""
        return self._zar_floor
    
    def format_zar(self, amount: Decimal) -> str:
        """
        Format Decimal amount as ZAR currency string.
        
        Reliability Level: L6 Critical
        Input Constraints: amount must be decimal.Decimal
        Side Effects: None
        
        Args:
            amount: Decimal value to format
            
        Returns:
            Formatted string "R X,XXX.XX"
        """
        # Quantize to 2 decimal places with Banker's Rounding
        quantized = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
        
        # Handle negative values
        if quantized < 0:
            return "R -{:,.2f}".format(abs(float(quantized)))
        
        return "R {:,.2f}".format(float(quantized))
    
    def _convert_to_zar(
        self,
        amount_usd: Decimal,
        fx_rate: Decimal
    ) -> Decimal:
        """
        Convert USD amount to ZAR using Decimal arithmetic.
        
        Reliability Level: L6 Critical
        Input Constraints: Both values must be decimal.Decimal
        Side Effects: None
        
        Args:
            amount_usd: Amount in USD
            fx_rate: USD/ZAR exchange rate
            
        Returns:
            Amount in ZAR with ROUND_HALF_EVEN
        """
        result = amount_usd * fx_rate
        return result.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
    
    async def refresh_fx_rate(self) -> Decimal:
        """
        Fetch current USD/ZAR exchange rate.
        
        Reliability Level: L5 High
        Input Constraints: None
        Side Effects: Updates internal rate cache
        
        Returns:
            Current USD/ZAR rate as Decimal
            
        Raises:
            RuntimeError: If rate fetch fails and no cached rate available
        """
        try:
            # TODO: Integrate with actual FX rate provider
            # For now, use a reasonable default rate
            # This should be replaced with actual API call
            rate = Decimal("18.50")  # Approximate USD/ZAR
            
            self._last_fx_rate = rate
            self._last_fx_rate_timestamp = datetime.now(timezone.utc)
            
            logger.info(
                f"[FX_RATE_REFRESH] rate={rate} "
                f"timestamp={self._last_fx_rate_timestamp.isoformat()}"
            )
            
            return rate
            
        except Exception as e:
            if self._last_fx_rate is not None:
                logger.warning(
                    f"[FX_RATE_STALE] Using cached rate. error={str(e)}"
                )
                return self._last_fx_rate
            
            logger.error(
                f"[FX_RATE_FAIL] No cached rate available. error={str(e)}"
            )
            raise RuntimeError(
                f"FX rate fetch failed and no cached rate: {str(e)}"
            )
    
    def _is_fx_rate_stale(self) -> bool:
        """
        Check if cached FX rate is stale (> 5 minutes old).
        
        Returns:
            True if rate is stale or unavailable
        """
        if self._last_fx_rate_timestamp is None:
            return True
            
        age_seconds = (
            datetime.now(timezone.utc) - self._last_fx_rate_timestamp
        ).total_seconds()
        
        return age_seconds > FX_RATE_STALE_THRESHOLD_SECONDS

    async def calculate_equity(
        self,
        asset_balances_usd: Dict[str, Decimal],
        correlation_id: Optional[str] = None
    ) -> EquitySnapshot:
        """
        Calculate total net equity in ZAR.
        
        Reliability Level: L6 Critical
        Input Constraints: All balance values must be decimal.Decimal
        Side Effects: May trigger Kill Switch if below ZAR_FLOOR
        
        Args:
            asset_balances_usd: Dict of asset -> USD value as Decimal
            correlation_id: Optional tracking ID for audit
            
        Returns:
            EquitySnapshot with ZAR-standardized values
        """
        # Refresh FX rate if stale
        if self._is_fx_rate_stale():
            await self.refresh_fx_rate()
        
        fx_rate = self._last_fx_rate
        fx_stale = self._is_fx_rate_stale()
        
        if fx_rate is None:
            raise RuntimeError("[EQUITY_CALC_FAIL] No FX rate available")
        
        # Sum all USD balances using Decimal arithmetic
        total_usd = Decimal("0.00")
        for asset, balance in asset_balances_usd.items():
            if not isinstance(balance, Decimal):
                raise TypeError(
                    f"[DECIMAL_VIOLATION] Asset {asset} balance is not Decimal"
                )
            total_usd += balance
        
        # Convert to ZAR
        net_equity_zar = self._convert_to_zar(total_usd, fx_rate)
        
        # Check ZAR floor breach
        below_floor = net_equity_zar < self._zar_floor
        
        timestamp_utc = datetime.now(timezone.utc).isoformat()
        fx_timestamp = (
            self._last_fx_rate_timestamp.isoformat()
            if self._last_fx_rate_timestamp else timestamp_utc
        )
        
        snapshot = EquitySnapshot(
            net_equity_zar=net_equity_zar,
            formatted=self.format_zar(net_equity_zar),
            fx_rate_usd_zar=fx_rate,
            fx_rate_timestamp_utc=fx_timestamp,
            fx_rate_stale=fx_stale,
            below_floor=below_floor,
            zar_floor=self._zar_floor,
            calculation_timestamp_utc=timestamp_utc
        )
        
        logger.info(
            f"[EQUITY_CALC] equity={snapshot.formatted} "
            f"below_floor={below_floor} correlation_id={correlation_id}"
        )
        
        # Trigger Kill Switch if below floor (Property 12)
        if below_floor and self._kill_switch_callback is not None:
            logger.critical(
                f"[ZAR_FLOOR_BREACH] equity={snapshot.formatted} "
                f"floor={self.format_zar(self._zar_floor)} "
                f"correlation_id={correlation_id}"
            )
            await self._kill_switch_callback(
                TriggerReason.ZAR_FLOOR_BREACH,
                correlation_id or "FLOOR_BREACH_AUTO"
            )
        
        return snapshot
    
    def calculate_net_alpha(
        self,
        gross_profit_zar: Decimal,
        operational_cost_zar: Optional[Decimal],
        correlation_id: str
    ) -> NetAlphaSnapshot:
        """
        Calculate Net Alpha (Gross Profit - Operational Cost).
        
        Reliability Level: L6 Critical
        Input Constraints: gross_profit_zar must be decimal.Decimal
        Side Effects: Logs calculation
        
        Sprint 6: BudgetGuard-ZAR Integration
        Property 21: Net Alpha Decimal Integrity
        
        Formula: Net Alpha = Gross Profit - Operational Cost
        
        Args:
            gross_profit_zar: Gross trading profit in ZAR
            operational_cost_zar: Operational cost from BudgetGuard (optional)
            correlation_id: Tracking ID for audit
            
        Returns:
            NetAlphaSnapshot with calculated values
        """
        timestamp_utc = datetime.now(timezone.utc).isoformat()
        
        # Validate input is Decimal
        if not isinstance(gross_profit_zar, Decimal):
            raise TypeError(
                f"[DECIMAL_VIOLATION] gross_profit_zar is not Decimal: "
                f"{type(gross_profit_zar)}"
            )
        
        # Handle missing operational cost
        if operational_cost_zar is None:
            logger.warning(
                f"[OG-005-OPERATIONAL_COST_UNAVAILABLE] "
                f"Using gross_profit as Net Alpha. "
                f"correlation_id={correlation_id}"
            )
            
            return NetAlphaSnapshot(
                gross_profit_zar=gross_profit_zar,
                operational_cost_zar=Decimal("0.00"),
                net_alpha_zar=gross_profit_zar,
                formatted=self.format_zar(gross_profit_zar),
                operational_cost_stale=True,
                calculation_timestamp_utc=timestamp_utc,
                correlation_id=correlation_id
            )
        
        # Validate operational cost is Decimal
        if not isinstance(operational_cost_zar, Decimal):
            raise TypeError(
                f"[DECIMAL_VIOLATION] operational_cost_zar is not Decimal: "
                f"{type(operational_cost_zar)}"
            )
        
        # Calculate Net Alpha with Decimal precision
        net_alpha = (gross_profit_zar - operational_cost_zar).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_EVEN
        )
        
        snapshot = NetAlphaSnapshot(
            gross_profit_zar=gross_profit_zar,
            operational_cost_zar=operational_cost_zar,
            net_alpha_zar=net_alpha,
            formatted=self.format_zar(net_alpha),
            operational_cost_stale=False,
            calculation_timestamp_utc=timestamp_utc,
            correlation_id=correlation_id
        )
        
        logger.info(
            f"[NET_ALPHA_CALC] gross={self.format_zar(gross_profit_zar)} "
            f"cost={self.format_zar(operational_cost_zar)} "
            f"net_alpha={snapshot.formatted} "
            f"correlation_id={correlation_id}"
        )
        
        return snapshot
    
    def ingest_budget_spend(
        self,
        total_spend: Decimal
    ) -> Decimal:
        """
        Ingest current operational spend from BudgetGuard.
        
        Reliability Level: L5 High
        Input Constraints: total_spend must be decimal.Decimal
        Side Effects: Stores spend for Net Alpha calculation
        
        Sprint 6: BudgetGuard-ZAR Integration
        
        Args:
            total_spend: Total operational spend from BudgetGuard report
            
        Returns:
            The ingested spend value
        """
        if not isinstance(total_spend, Decimal):
            raise TypeError(
                f"[DECIMAL_VIOLATION] total_spend is not Decimal: "
                f"{type(total_spend)}"
            )
        
        self._current_operational_cost = total_spend
        
        logger.info(
            f"[BUDGET_SPEND_INGESTED] spend={self.format_zar(total_spend)}"
        )
        
        return total_spend
    
    def get_current_operational_cost(self) -> Optional[Decimal]:
        """Get the current operational cost from BudgetGuard."""
        return getattr(self, '_current_operational_cost', None)


# =============================================================================
# KILL SWITCH MODULE
# =============================================================================

class KillSwitchModule:
    """
    Emergency capital protection mechanism.
    
    Reliability Level: L6 Critical
    Input Constraints: Valid exchange API connection required
    Side Effects: Closes all positions, cancels orders, revokes API access
    
    Must execute within 5-second SLA (Property 10).
    """
    
    def __init__(
        self,
        exchange_client: Optional[Any] = None,
        audit_writer: Optional[Any] = None,
        bot_vitals_callback: Optional[Any] = None
    ) -> None:
        """
        Initialize Kill Switch Module.
        
        Args:
            exchange_client: Client for exchange API operations
            audit_writer: Callback to write audit records
            bot_vitals_callback: Callback to get_bot_vitals from aura-bridge
        """
        self._exchange_client = exchange_client
        self._audit_writer = audit_writer
        self._bot_vitals_callback = bot_vitals_callback
        self._is_armed: bool = True
        self._last_execution: Optional[KillSwitchResult] = None
    
    @property
    def is_armed(self) -> bool:
        """Check if Kill Switch is armed and ready."""
        return self._is_armed
    
    def arm(self) -> None:
        """Arm the Kill Switch."""
        self._is_armed = True
        logger.info("[KILL_SWITCH_ARMED]")
    
    def disarm(self) -> None:
        """Disarm the Kill Switch (use with caution)."""
        self._is_armed = False
        logger.warning("[KILL_SWITCH_DISARMED] Manual override active")
    
    async def check_health_trigger(self) -> bool:
        """
        Check if get_bot_vitals returns RED status.
        
        Reliability Level: L6 Critical
        Input Constraints: bot_vitals_callback must be set
        Side Effects: None
        
        Returns:
            True if health status is RED
        """
        if self._bot_vitals_callback is None:
            logger.warning(
                "[HEALTH_CHECK_SKIP] No bot_vitals_callback configured"
            )
            return False
        
        try:
            vitals = await self._bot_vitals_callback()
            
            # Parse health status from vitals response
            health_status = vitals.get("health_status", "UNKNOWN")
            
            if health_status == "RED" or health_status == HealthStatus.RED.value:
                logger.critical(
                    f"[RED_HEALTH_DETECTED] vitals={vitals}"
                )
                return True
            
            return False
            
        except Exception as e:
            logger.error(
                f"[HEALTH_CHECK_FAIL] error={str(e)}"
            )
            # Fail-safe: treat check failure as potential RED
            return True
    
    async def _close_all_positions(self) -> int:
        """
        Close all open positions using market orders.
        
        Returns:
            Number of positions closed
        """
        if self._exchange_client is None:
            logger.warning("[CLOSE_POSITIONS_SKIP] No exchange client")
            return 0
        
        try:
            # Get open positions
            positions = await self._exchange_client.get_open_positions()
            closed_count = 0
            
            for position in positions:
                try:
                    await self._exchange_client.close_position(
                        position["symbol"],
                        order_type="MARKET"
                    )
                    closed_count += 1
                    logger.info(
                        f"[POSITION_CLOSED] symbol={position['symbol']}"
                    )
                except Exception as e:
                    logger.error(
                        f"[POSITION_CLOSE_FAIL] symbol={position['symbol']} "
                        f"error={str(e)}"
                    )
            
            return closed_count
            
        except Exception as e:
            logger.error(f"[GET_POSITIONS_FAIL] error={str(e)}")
            return 0
    
    async def _cancel_all_orders(self) -> int:
        """
        Cancel all pending orders.
        
        Returns:
            Number of orders cancelled
        """
        if self._exchange_client is None:
            logger.warning("[CANCEL_ORDERS_SKIP] No exchange client")
            return 0
        
        try:
            orders = await self._exchange_client.get_open_orders()
            cancelled_count = 0
            
            for order in orders:
                try:
                    await self._exchange_client.cancel_order(order["order_id"])
                    cancelled_count += 1
                    logger.info(
                        f"[ORDER_CANCELLED] order_id={order['order_id']}"
                    )
                except Exception as e:
                    logger.error(
                        f"[ORDER_CANCEL_FAIL] order_id={order['order_id']} "
                        f"error={str(e)}"
                    )
            
            return cancelled_count
            
        except Exception as e:
            logger.error(f"[GET_ORDERS_FAIL] error={str(e)}")
            return 0
    
    async def _revoke_api_session(self) -> bool:
        """
        Revoke active API session.
        
        Returns:
            True if revocation successful
        """
        if self._exchange_client is None:
            logger.warning("[REVOKE_API_SKIP] No exchange client")
            return False
        
        try:
            await self._exchange_client.revoke_session()
            logger.info("[API_SESSION_REVOKED]")
            return True
            
        except Exception as e:
            logger.error(f"[API_REVOKE_FAIL] error={str(e)}")
            return False
    
    async def _write_audit_record(
        self,
        result: KillSwitchResult,
        correlation_id: str
    ) -> str:
        """
        Write Kill Switch execution to audit log.
        
        Returns:
            Audit record ID
        """
        import uuid
        import hashlib
        import json
        
        record_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()
        
        event_data = {
            "trigger_reason": result.trigger_reason.value,
            "positions_closed": result.positions_closed,
            "orders_cancelled": result.orders_cancelled,
            "api_revoked": result.api_revoked,
            "total_execution_time_ms": result.total_execution_time_ms,
            "success": result.success,
            "error_message": result.error_message
        }
        
        # Generate checksum for integrity
        checksum = hashlib.sha256(
            json.dumps(event_data, sort_keys=True).encode()
        ).hexdigest()
        
        record = AuditRecord(
            id=record_id,
            correlation_id=correlation_id,
            event_type="KILL_SWITCH_EXECUTION",
            event_data=event_data,
            timestamp_utc=timestamp,
            checksum=checksum
        )
        
        if self._audit_writer is not None:
            try:
                await self._audit_writer(record)
            except Exception as e:
                logger.error(f"[AUDIT_WRITE_FAIL] error={str(e)}")
        
        logger.critical(
            f"[KILL_SWITCH_AUDIT] record_id={record_id} "
            f"correlation_id={correlation_id} checksum={checksum[:16]}..."
        )
        
        return record_id
    
    async def execute(
        self,
        trigger_reason: TriggerReason,
        correlation_id: str
    ) -> KillSwitchResult:
        """
        Execute full Kill Switch sequence.
        
        Reliability Level: L6 Critical
        Input Constraints: trigger_reason and correlation_id required
        Side Effects: Closes positions, cancels orders, revokes API
        
        Must complete within 5-second SLA (Property 10).
        
        Args:
            trigger_reason: Why Kill Switch was triggered
            correlation_id: Tracking ID for audit trail
            
        Returns:
            KillSwitchResult with execution details
        """
        if not self._is_armed:
            logger.warning(
                f"[KILL_SWITCH_DISARMED] Execution blocked. "
                f"trigger_reason={trigger_reason.value}"
            )
            return KillSwitchResult(
                trigger_reason=trigger_reason,
                positions_closed=0,
                orders_cancelled=0,
                api_revoked=False,
                total_execution_time_ms=0,
                audit_record_id="",
                success=False,
                error_message="Kill Switch is disarmed"
            )
        
        start_time_ms = int(time.time() * 1000)
        
        logger.critical(
            f"[KILL_SWITCH_EXECUTING] trigger_reason={trigger_reason.value} "
            f"correlation_id={correlation_id}"
        )
        
        error_message = None
        
        try:
            # Step 1: Close all positions (Property 9)
            positions_closed = await self._close_all_positions()
            
            # Step 2: Cancel all orders (Property 9)
            orders_cancelled = await self._cancel_all_orders()
            
            # Step 3: Revoke API session (Property 9)
            api_revoked = await self._revoke_api_session()
            
            success = True
            
        except Exception as e:
            error_message = str(e)
            positions_closed = 0
            orders_cancelled = 0
            api_revoked = False
            success = False
            
            logger.error(
                f"[KILL_SWITCH_ERROR] error={error_message} "
                f"correlation_id={correlation_id}"
            )
        
        end_time_ms = int(time.time() * 1000)
        total_execution_time_ms = end_time_ms - start_time_ms
        
        # Check SLA compliance (Property 10)
        if total_execution_time_ms > KILL_SWITCH_SLA_MS:
            logger.warning(
                f"[KILL_SWITCH_SLA_BREACH] execution_time_ms={total_execution_time_ms} "
                f"sla_ms={KILL_SWITCH_SLA_MS}"
            )
        
        result = KillSwitchResult(
            trigger_reason=trigger_reason,
            positions_closed=positions_closed,
            orders_cancelled=orders_cancelled,
            api_revoked=api_revoked,
            total_execution_time_ms=total_execution_time_ms,
            audit_record_id="",  # Will be set after audit write
            success=success,
            error_message=error_message
        )
        
        # Step 4: Write audit record (Property 9)
        audit_record_id = await self._write_audit_record(result, correlation_id)
        result.audit_record_id = audit_record_id
        
        self._last_execution = result
        
        logger.critical(
            f"[KILL_SWITCH_COMPLETE] positions_closed={positions_closed} "
            f"orders_cancelled={orders_cancelled} api_revoked={api_revoked} "
            f"execution_time_ms={total_execution_time_ms} "
            f"audit_record_id={audit_record_id}"
        )
        
        return result


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def create_safety_modules(
    zar_floor: Optional[Decimal] = None,
    exchange_client: Optional[Any] = None,
    audit_writer: Optional[Any] = None,
    bot_vitals_callback: Optional[Any] = None
) -> tuple:
    """
    Factory function to create linked Equity and Kill Switch modules.
    
    Reliability Level: L6 Critical
    
    Args:
        zar_floor: ZAR floor threshold
        exchange_client: Exchange API client
        audit_writer: Audit log writer callback
        bot_vitals_callback: get_bot_vitals callback from aura-bridge
        
    Returns:
        Tuple of (EquityModule, KillSwitchModule)
    """
    kill_switch = KillSwitchModule(
        exchange_client=exchange_client,
        audit_writer=audit_writer,
        bot_vitals_callback=bot_vitals_callback
    )
    
    equity = EquityModule(
        zar_floor=zar_floor,
        kill_switch_callback=kill_switch.execute
    )
    
    return equity, kill_switch

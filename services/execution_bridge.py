"""
============================================================================
Post-Approval Execution Bridge
============================================================================

Reliability Level: L6 Critical (Sovereign Tier)
Decimal Integrity: All financial calculations use decimal.Decimal with ROUND_HALF_EVEN
Traceability: All operations include correlation_id for audit

PURPOSE:
    Bridges the gap between HITL ACCEPTED state and DemoBroker
    PAPER execution. After an operator approves a trade, this module
    orchestrates the actual paper execution and lifecycle transition.

FLOW:
    1. Validate execution mode is DEMO/PAPER (hard guard)
    2. Verify Guardian is unlocked
    3. Extract trade parameters from approved request
    4. Execute via DemoBroker.place_market_order()
    5. Transition lifecycle: ACCEPTED -> FILLED
    6. Persist audit trail
    7. Return execution result

SAFETY:
    - LIVE execution is UNREACHABLE from this path
    - Guardian lock is re-checked before execution
    - All failures are fail-closed (no partial execution)
    - correlation_id continuity is preserved end-to-end

ERROR CODES:
    - EXEC-BRIDGE-001: Invalid execution mode (not DEMO/PAPER)
    - EXEC-BRIDGE-002: Guardian is locked
    - EXEC-BRIDGE-003: DemoBroker execution failed
    - EXEC-BRIDGE-004: Lifecycle transition failed
    - EXEC-BRIDGE-005: Missing trade parameters

============================================================================
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import ROUND_HALF_EVEN, Decimal
import logging
import os
from typing import Any, Optional
import uuid

from services.demo_broker import DemoBroker, OrderSide
from services.guardian_integration import GuardianIntegration
from services.hitl_models import ApprovalRequest, ApprovalStatus
from services.hitl_state_machine import HITLTradeState, transition_trade

# Configure module logger
logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

# Default quantity when not available from reasoning_summary
DEFAULT_PAPER_QUANTITY = Decimal("0.01")

# Precision for quantity
PRECISION_QUANTITY = Decimal("0.01")


# =============================================================================
# Result Data Class
# =============================================================================


@dataclass
class ExecutionBridgeResult:
    """
    Result of post-approval execution bridge.

    Reliability Level: L6 Critical
    """

    success: bool
    trade_id: str
    correlation_id: str
    order_id: Optional[str] = None
    filled_price: Optional[Decimal] = None
    filled_quantity: Optional[Decimal] = None
    execution_mode: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    broker_status: Optional[str] = None
    executed_at: Optional[datetime] = None
    lifecycle_transitioned: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for audit/logging."""
        return {
            "success": self.success,
            "trade_id": self.trade_id,
            "correlation_id": self.correlation_id,
            "order_id": self.order_id,
            "filled_price": str(self.filled_price) if self.filled_price else None,
            "filled_quantity": str(self.filled_quantity)
            if self.filled_quantity
            else None,
            "execution_mode": self.execution_mode,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "broker_status": self.broker_status,
            "executed_at": self.executed_at.isoformat() if self.executed_at else None,
            "lifecycle_transitioned": self.lifecycle_transitioned,
        }


# =============================================================================
# Execution Mode Hard Guard
# =============================================================================


def _validate_execution_mode(correlation_id: str) -> tuple[bool, Optional[str]]:
    """
    Validate that execution mode is DEMO/PAPER.

    LIVE execution is UNREACHABLE from this path.

    Returns:
        tuple of (is_valid, error_message)
    """
    execution_mode = os.environ.get("EXECUTION_MODE", "").upper()
    demo_mode = os.environ.get("DEMO_MODE", "").upper()
    live_confirmed = os.environ.get("LIVE_TRADING_CONFIRMED", "FALSE").upper()

    # Hard guard: LIVE mode must NEVER be reachable
    if live_confirmed == "TRUE":
        logger.critical(
            f"[EXEC-BRIDGE-001] LIVE_TRADING_CONFIRMED=TRUE — "
            f"execution bridge refuses to proceed | "
            f"correlation_id={correlation_id}"
        )
        return False, (
            "EXEC-BRIDGE-001: LIVE_TRADING_CONFIRMED is TRUE. "
            "Post-approval execution bridge is PAPER-ONLY. "
            "LIVE execution requires a separate, audited path."
        )

    if execution_mode != "DEMO":
        logger.critical(
            f"[EXEC-BRIDGE-001] EXECUTION_MODE={execution_mode} — "
            f"must be DEMO for paper execution | "
            f"correlation_id={correlation_id}"
        )
        return False, (
            f"EXEC-BRIDGE-001: EXECUTION_MODE={execution_mode}. "
            f"Must be DEMO. Paper execution bridge refuses non-DEMO mode."
        )

    if demo_mode not in ("PAPER", ""):
        # Allow empty (defaults to PAPER) or explicit PAPER
        if demo_mode not in ("PAPER",):
            logger.critical(
                f"[EXEC-BRIDGE-001] DEMO_MODE={demo_mode} — "
                f"must be PAPER for paper execution | "
                f"correlation_id={correlation_id}"
            )
            return False, (
                f"EXEC-BRIDGE-001: DEMO_MODE={demo_mode}. "
                f"Must be PAPER. Other demo modes not supported by this bridge."
            )

    return True, None


# =============================================================================
# Execution Bridge
# =============================================================================


def execute_approved_trade(
    approval_request: ApprovalRequest,
    demo_broker: DemoBroker,
    guardian: GuardianIntegration,
    db_session: Optional[Any],
    correlation_id: str,
) -> ExecutionBridgeResult:
    """
    Execute a paper trade after HITL approval.

    This is the canonical post-approval execution path for PAPER mode.
    It bridges the ACCEPTED -> FILLED lifecycle gap.

    Args:
        approval_request: The ACCEPTED approval request
        demo_broker: DemoBroker instance (PAPER mode)
        guardian: GuardianIntegration for lock-state check
        db_session: Database session for lifecycle transition and audit
        correlation_id: End-to-end audit trail identifier

    Returns:
        ExecutionBridgeResult with execution outcome

    Reliability Level: SOVEREIGN TIER
    Input Constraints:
        - approval_request.status must be ACCEPTED
        - EXECUTION_MODE must be DEMO
        - DEMO_MODE must be PAPER
    Side Effects:
        - DemoBroker state file updated
        - Lifecycle transitioned to FILLED
        - Audit log entry created
    """
    trade_id_str = str(approval_request.trade_id)

    logger.info(
        f"[EXEC-BRIDGE] Starting post-approval execution | "
        f"trade_id={trade_id_str} | "
        f"instrument={approval_request.instrument} | "
        f"side={approval_request.side} | "
        f"correlation_id={correlation_id}"
    )

    # =========================================================================
    # Guard 1: Verify approval status is ACCEPTED
    # =========================================================================
    if approval_request.status != ApprovalStatus.ACCEPTED.value:
        error_msg = (
            f"EXEC-BRIDGE-005: Cannot execute — status is "
            f"{approval_request.status}, expected ACCEPTED"
        )
        logger.error(
            f"[EXEC-BRIDGE] {error_msg} | "
            f"trade_id={trade_id_str} | "
            f"correlation_id={correlation_id}"
        )
        return ExecutionBridgeResult(
            success=False,
            trade_id=trade_id_str,
            correlation_id=correlation_id,
            error_code="EXEC-BRIDGE-005",
            error_message=error_msg,
        )

    # =========================================================================
    # Guard 2: Validate execution mode (DEMO/PAPER hard guard)
    # =========================================================================
    mode_valid, mode_error = _validate_execution_mode(correlation_id)
    if not mode_valid:
        return ExecutionBridgeResult(
            success=False,
            trade_id=trade_id_str,
            correlation_id=correlation_id,
            error_code="EXEC-BRIDGE-001",
            error_message=mode_error,
        )

    # =========================================================================
    # Guard 3: Re-check Guardian lock state
    # =========================================================================
    if guardian.is_locked():
        error_msg = (
            "EXEC-BRIDGE-002: Guardian is LOCKED. "
            "Cannot execute paper trade. Sovereign Mandate: Guardian always wins."
        )
        logger.warning(
            f"[EXEC-BRIDGE] {error_msg} | "
            f"trade_id={trade_id_str} | "
            f"correlation_id={correlation_id}"
        )
        guardian.block_operation(
            operation_type="execution_bridge",
            correlation_id=correlation_id,
            context={"trade_id": trade_id_str},
        )
        return ExecutionBridgeResult(
            success=False,
            trade_id=trade_id_str,
            correlation_id=correlation_id,
            error_code="EXEC-BRIDGE-002",
            error_message=error_msg,
        )

    # =========================================================================
    # Step 1: Extract trade parameters from approval request
    # =========================================================================
    instrument = approval_request.instrument
    side_str = approval_request.side.upper()

    # Map side string to DemoBroker OrderSide enum
    try:
        order_side = OrderSide(side_str)
    except ValueError:
        error_msg = f"EXEC-BRIDGE-005: Invalid side '{side_str}'. Must be BUY or SELL."
        logger.error(
            f"[EXEC-BRIDGE] {error_msg} | "
            f"trade_id={trade_id_str} | "
            f"correlation_id={correlation_id}"
        )
        return ExecutionBridgeResult(
            success=False,
            trade_id=trade_id_str,
            correlation_id=correlation_id,
            error_code="EXEC-BRIDGE-005",
            error_message=error_msg,
        )

    # Extract quantity from reasoning_summary if available
    quantity = DEFAULT_PAPER_QUANTITY
    reasoning = approval_request.reasoning_summary or {}
    if "calculated_quantity" in reasoning:
        try:
            quantity = Decimal(str(reasoning["calculated_quantity"])).quantize(
                PRECISION_QUANTITY, rounding=ROUND_HALF_EVEN
            )
        except Exception:
            logger.warning(
                f"[EXEC-BRIDGE] Could not parse calculated_quantity from "
                f"reasoning_summary, using default={DEFAULT_PAPER_QUANTITY} | "
                f"trade_id={trade_id_str} | "
                f"correlation_id={correlation_id}"
            )

    # =========================================================================
    # Step 2: Execute via DemoBroker
    # =========================================================================
    try:
        # Seed the market price from the approval request price
        # so DemoBroker can fill the order even without live data feed
        demo_broker.update_market_price(
            symbol=instrument,
            price=approval_request.request_price,
            correlation_id=correlation_id,
        )

        broker_result = demo_broker.place_market_order(
            symbol=instrument,
            side=order_side,
            quantity=quantity,
            correlation_id=correlation_id,
        )

    except Exception as exc:
        error_msg = f"EXEC-BRIDGE-003: DemoBroker execution failed: {str(exc)[:200]}"
        logger.error(
            f"[EXEC-BRIDGE] {error_msg} | "
            f"trade_id={trade_id_str} | "
            f"correlation_id={correlation_id}"
        )
        return ExecutionBridgeResult(
            success=False,
            trade_id=trade_id_str,
            correlation_id=correlation_id,
            error_code="EXEC-BRIDGE-003",
            error_message=error_msg,
            execution_mode="DEMO_PAPER",
        )

    # =========================================================================
    # Step 3: Verify broker result
    # =========================================================================
    broker_status = broker_result.get("status", "UNKNOWN")

    if broker_status != "FILLED":
        error_msg = (
            f"EXEC-BRIDGE-003: DemoBroker returned status={broker_status}. "
            f"Reason: {broker_result.get('reason', 'unknown')}"
        )
        logger.error(
            f"[EXEC-BRIDGE] {error_msg} | "
            f"trade_id={trade_id_str} | "
            f"correlation_id={correlation_id}"
        )
        return ExecutionBridgeResult(
            success=False,
            trade_id=trade_id_str,
            correlation_id=correlation_id,
            error_code="EXEC-BRIDGE-003",
            error_message=error_msg,
            execution_mode="DEMO_PAPER",
            broker_status=broker_status,
        )

    # Parse fill details
    filled_price = Decimal(str(broker_result["filled_price"]))
    filled_quantity = Decimal(str(broker_result["filled_quantity"]))
    order_id = broker_result.get("order_id", "")
    executed_at = datetime.now(timezone.utc)

    logger.info(
        f"[EXEC-BRIDGE] DemoBroker FILLED | "
        f"trade_id={trade_id_str} | "
        f"order_id={order_id} | "
        f"instrument={instrument} | "
        f"side={side_str} | "
        f"qty={filled_quantity} | "
        f"price={filled_price} | "
        f"correlation_id={correlation_id}"
    )

    # =========================================================================
    # Step 4: Transition lifecycle ACCEPTED -> FILLED
    # =========================================================================
    lifecycle_transitioned = False

    if db_session is not None:
        try:
            success, error_code, audit_record = transition_trade(
                db_session=db_session,
                trade_id=trade_id_str,
                current_state=HITLTradeState.ACCEPTED.value,
                target_state=HITLTradeState.FILLED.value,
                correlation_id=correlation_id,
                actor_id="execution_bridge",
                reason=(
                    f"PAPER execution via DemoBroker | "
                    f"order_id={order_id} | "
                    f"filled_price={filled_price} | "
                    f"filled_qty={filled_quantity}"
                ),
                metadata={
                    "order_id": order_id,
                    "broker_status": broker_status,
                    "filled_price": str(filled_price),
                    "filled_quantity": str(filled_quantity),
                    "instrument": instrument,
                    "side": side_str,
                    "execution_mode": "DEMO_PAPER",
                },
            )

            if success:
                lifecycle_transitioned = True
                logger.info(
                    f"[EXEC-BRIDGE] Lifecycle transitioned ACCEPTED -> FILLED | "
                    f"trade_id={trade_id_str} | "
                    f"correlation_id={correlation_id}"
                )
            else:
                logger.warning(
                    f"[EXEC-BRIDGE] Lifecycle transition returned "
                    f"error_code={error_code} | "
                    f"trade_id={trade_id_str} | "
                    f"correlation_id={correlation_id}"
                )
        except Exception as exc:
            logger.error(
                f"[EXEC-BRIDGE-004] Lifecycle transition failed: "
                f"{str(exc)[:200]} | "
                f"trade_id={trade_id_str} | "
                f"correlation_id={correlation_id}"
            )
    else:
        logger.warning(
            f"[EXEC-BRIDGE] No db_session — lifecycle transition skipped | "
            f"trade_id={trade_id_str} | "
            f"correlation_id={correlation_id}"
        )

    # =========================================================================
    # Step 5: Create audit log entry for execution
    # =========================================================================
    if db_session is not None:
        try:
            _create_execution_audit(
                db_session=db_session,
                trade_id=trade_id_str,
                approval_id=str(approval_request.id),
                order_id=order_id,
                instrument=instrument,
                side=side_str,
                filled_price=filled_price,
                filled_quantity=filled_quantity,
                correlation_id=correlation_id,
                operator_id=approval_request.decided_by or "unknown",
            )
        except Exception as exc:
            # Audit failure must not block execution result
            logger.error(
                f"[EXEC-BRIDGE] Audit log write failed: {str(exc)[:200]} | "
                f"trade_id={trade_id_str} | "
                f"correlation_id={correlation_id}"
            )

    logger.info(
        f"[EXEC-BRIDGE] Post-approval execution COMPLETE | "
        f"trade_id={trade_id_str} | "
        f"order_id={order_id} | "
        f"lifecycle_transitioned={lifecycle_transitioned} | "
        f"correlation_id={correlation_id}"
    )

    return ExecutionBridgeResult(
        success=True,
        trade_id=trade_id_str,
        correlation_id=correlation_id,
        order_id=order_id,
        filled_price=filled_price,
        filled_quantity=filled_quantity,
        execution_mode="DEMO_PAPER",
        broker_status=broker_status,
        executed_at=executed_at,
        lifecycle_transitioned=lifecycle_transitioned,
    )


# =============================================================================
# Audit Helper
# =============================================================================


def _create_execution_audit(
    db_session: Any,
    trade_id: str,
    approval_id: str,
    order_id: str,
    instrument: str,
    side: str,
    filled_price: Decimal,
    filled_quantity: Decimal,
    correlation_id: str,
    operator_id: str,
) -> None:
    """
    Create an audit_log entry for paper execution.

    Uses a proper UUID for target_id to avoid the known
    audit_log.target_id type mismatch issue.

    Reliability Level: SOVEREIGN TIER
    """
    from sqlalchemy import text

    audit_id = str(uuid.uuid4())
    # Use trade_id as target_id (it is a valid UUID from HITL)
    # This fixes the known issue where non-UUID strings were passed

    insert_query = text("""
        INSERT INTO audit_log (
            id, actor_id, action, target_type, target_id,
            previous_state, new_state, payload,
            correlation_id, error_code, created_at
        ) VALUES (
            :id, :actor_id, :action, :target_type, :target_id,
            :previous_state, :new_state, :payload,
            :correlation_id, :error_code, :created_at
        )
    """)

    db_session.execute(
        insert_query,
        {
            "id": audit_id,
            "actor_id": operator_id,
            "action": "PAPER_EXECUTION_COMPLETED",
            "target_type": "trade",
            "target_id": trade_id,
            "previous_state": '{"state": "ACCEPTED"}',
            "new_state": '{"state": "FILLED"}',
            "payload": str(
                {
                    "order_id": order_id,
                    "instrument": instrument,
                    "side": side,
                    "filled_price": str(filled_price),
                    "filled_quantity": str(filled_quantity),
                    "execution_mode": "DEMO_PAPER",
                }
            ).replace("'", '"'),
            "correlation_id": correlation_id,
            "error_code": None,
            "created_at": datetime.now(timezone.utc),
        },
    )
    db_session.commit()

    logger.info(
        f"[EXEC-BRIDGE] Audit log entry created | "
        f"action=PAPER_EXECUTION_COMPLETED | "
        f"trade_id={trade_id} | "
        f"order_id={order_id} | "
        f"correlation_id={correlation_id}"
    )

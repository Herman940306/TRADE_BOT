"""
Frontend API Router — Sovereign Command Hub Data Endpoints

Provides read-only data endpoints for the frontend dashboard.
All financial values returned as strings (Decimal-safe).
"""

from datetime import datetime, timezone
import logging
import os
from typing import Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================================
# AUTH
# ============================================================================


def _verify_bearer(authorization: Optional[str] = Header(None)) -> str:
    """Validate Bearer token and return operator ID."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")

    token = authorization[7:]
    expected = os.environ.get("FRONTEND_API_TOKEN", "")
    if not expected:
        raise HTTPException(status_code=503, detail="API token not configured")
    if token != expected:
        raise HTTPException(status_code=401, detail="Invalid token")

    return "operator"


# ============================================================================
# RESPONSE MODELS
# ============================================================================


class TradeHistoryResponse(BaseModel):
    trades: list[dict[str, Any]] = Field(default_factory=list)
    total: int = 0


class PreflightResponse(BaseModel):
    checks: list[dict[str, Any]] = Field(default_factory=list)
    ready: bool = False
    mode: str = "PAPER"


class LearningStatusResponse(BaseModel):
    mind_state: str = "CALM"
    curriculum_phase: int = 1
    curriculum_name: str = "Observer"
    budget_remaining: Optional[str] = None
    budget_total: Optional[str] = None


class DecisionSnapshotsResponse(BaseModel):
    snapshots: list[dict[str, Any]] = Field(default_factory=list)
    total: int = 0


# ============================================================================
# ENDPOINTS
# ============================================================================


@router.get(
    "/trades/history",
    response_model=TradeHistoryResponse,
    summary="Trade History",
    tags=["Frontend"],
)
async def get_trade_history(
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    operator: str = Depends(_verify_bearer),
) -> TradeHistoryResponse:
    """Get trade history with pagination."""
    try:
        rows = db.execute(
            text("""
                SELECT trade_id, correlation_id, current_state,
                       signal_data->>'symbol' AS symbol,
                       signal_data->>'side' AS side,
                       created_at, updated_at
                FROM trade_lifecycle
                ORDER BY created_at DESC
                LIMIT :lim OFFSET :off
            """),
            {"lim": limit, "off": offset},
        ).fetchall()

        count_row = db.execute(text("SELECT COUNT(*) FROM trade_lifecycle")).fetchone()

        trades = [
            {
                "trade_id": str(r[0]),
                "correlation_id": str(r[1]),
                "status": r[2],
                "symbol": r[3],
                "side": r[4],
                "created_at": r[5].isoformat() if r[5] else None,
                "updated_at": r[6].isoformat() if r[6] else None,
            }
            for r in rows
        ]

        return TradeHistoryResponse(
            trades=trades,
            total=count_row[0] if count_row else 0,
        )
    except Exception as e:
        logger.error(f"[FRONTEND-API] Trade history failed | error={e}")
        raise HTTPException(status_code=500, detail="Failed to fetch trades")


@router.get(
    "/preflight/status",
    response_model=PreflightResponse,
    summary="Preflight Readiness",
    tags=["Frontend"],
)
async def get_preflight_status(
    operator: str = Depends(_verify_bearer),
) -> PreflightResponse:
    """Get go/no-go checklist for live trading."""
    import app.core.runtime as _runtime

    checks = []

    # Check 1: Database
    try:
        from app.database.session import check_database_connection

        db_ok = check_database_connection()
        checks.append({"name": "Database", "status": "PASS" if db_ok else "FAIL"})
    except Exception:
        checks.append({"name": "Database", "status": "FAIL"})

    # Check 2: Guardian
    guardian = _runtime.get_guardian_integration()
    checks.append(
        {
            "name": "Guardian",
            "status": "PASS" if guardian else "FAIL",
        }
    )

    # Check 3: HITL Gateway
    hitl = _runtime.get_hitl_gateway()
    checks.append(
        {
            "name": "HITL Gateway",
            "status": "PASS" if hitl else "FAIL",
        }
    )

    # Check 4: Strategy Manager
    strategy = _runtime.get_strategy_manager()
    checks.append(
        {
            "name": "Strategy Manager",
            "status": "PASS" if strategy else "FAIL",
        }
    )

    # Check 5: Trade Lifecycle
    tlm = _runtime.get_trade_lifecycle_manager()
    checks.append(
        {
            "name": "Trade Lifecycle",
            "status": "PASS" if tlm else "FAIL",
        }
    )

    # Check 6: DemoBroker
    broker = _runtime.get_demo_broker()
    checks.append(
        {
            "name": "DemoBroker",
            "status": "PASS" if broker else "FAIL",
        }
    )

    all_pass = all(c["status"] == "PASS" for c in checks)
    mode = os.environ.get("EXECUTION_MODE", "PAPER")

    return PreflightResponse(checks=checks, ready=all_pass, mode=mode)


@router.get(
    "/strategies/list",
    summary="List Strategies",
    tags=["Frontend"],
)
async def get_strategies(
    db: Session = Depends(get_db),
    operator: str = Depends(_verify_bearer),
) -> dict[str, Any]:
    """List registered strategies."""
    try:
        rows = db.execute(
            text("""
                SELECT fingerprint, strategy_id, title, status,
                       created_at
                FROM strategy_blueprints
                ORDER BY created_at DESC
            """)
        ).fetchall()

        strategies = [
            {
                "fingerprint": r[0],
                "strategy_id": r[1],
                "title": r[2],
                "status": r[3],
                "created_at": r[4].isoformat() if r[4] else None,
            }
            for r in rows
        ]

        return {"strategies": strategies, "count": len(strategies)}
    except Exception as e:
        logger.error(f"[FRONTEND-API] Strategies list failed | error={e}")
        return {"strategies": [], "count": 0}


@router.get(
    "/learning/status",
    response_model=LearningStatusResponse,
    summary="Learning Status",
    tags=["Frontend"],
)
async def get_learning_status(
    db: Session = Depends(get_db),
    operator: str = Depends(_verify_bearer),
) -> LearningStatusResponse:
    """Get intelligence layer status."""
    try:
        # Get curriculum state
        curriculum_row = db.execute(
            text("""
                SELECT current_phase, phase_name
                FROM curriculum_state
                ORDER BY id DESC LIMIT 1
            """)
        ).fetchone()

        # Get mind state
        mind_row = db.execute(
            text("""
                SELECT new_state
                FROM mind_state_history
                ORDER BY created_at DESC LIMIT 1
            """)
        ).fetchone()

        # Get budget
        budget_row = db.execute(
            text("""
                SELECT remaining_budget, starting_budget
                FROM confidence_budget_daily
                WHERE budget_date = CURRENT_DATE
            """)
        ).fetchone()

        return LearningStatusResponse(
            mind_state=mind_row[0] if mind_row else "CALM",
            curriculum_phase=int(curriculum_row[0]) if curriculum_row else 1,
            curriculum_name=curriculum_row[1] if curriculum_row else "Observer",
            budget_remaining=str(budget_row[0]) if budget_row else None,
            budget_total=str(budget_row[1]) if budget_row else None,
        )
    except Exception as e:
        logger.error(f"[FRONTEND-API] Learning status failed | error={e}")
        return LearningStatusResponse()


@router.get(
    "/decisions/snapshots",
    response_model=DecisionSnapshotsResponse,
    summary="Decision Snapshots",
    tags=["Frontend"],
)
async def get_decision_snapshots(
    limit: int = 50,
    db: Session = Depends(get_db),
    operator: str = Depends(_verify_bearer),
) -> DecisionSnapshotsResponse:
    """Get recent decision snapshots for forensic review."""
    try:
        rows = db.execute(
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

        snapshots = [
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

        count_row = db.execute(
            text("SELECT COUNT(*) FROM decision_snapshots")
        ).fetchone()

        return DecisionSnapshotsResponse(
            snapshots=snapshots,
            total=count_row[0] if count_row else 0,
        )
    except Exception as e:
        logger.error(f"[FRONTEND-API] Snapshots failed | error={e}")
        return DecisionSnapshotsResponse()


@router.get(
    "/analytics/operator",
    summary="Operator Analytics",
    tags=["Frontend"],
)
async def get_operator_analytics(
    db: Session = Depends(get_db),
    operator: str = Depends(_verify_bearer),
) -> dict[str, Any]:
    """Get operator performance analytics."""
    try:
        row = db.execute(
            text("""
                SELECT
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE decision = 'APPROVE') as approvals,
                    COUNT(*) FILTER (WHERE decision = 'REJECT') as rejections,
                    COUNT(*) FILTER (WHERE decision = 'TIMEOUT') as timeouts,
                    AVG(CASE WHEN was_correct THEN 1.0 ELSE 0.0 END)
                        FILTER (WHERE was_correct IS NOT NULL) as accuracy,
                    COALESCE(SUM(value_add_zar), 0) as total_value_add
                FROM operator_analytics
            """)
        ).fetchone()

        if not row:
            return {
                "total_decisions": 0,
                "approvals": 0,
                "rejections": 0,
                "timeouts": 0,
                "accuracy": None,
                "total_value_add_zar": "0",
            }

        return {
            "total_decisions": int(row[0]),
            "approvals": int(row[1]),
            "rejections": int(row[2]),
            "timeouts": int(row[3]),
            "accuracy": str(round(float(row[4]), 4)) if row[4] else None,
            "total_value_add_zar": str(row[5]),
        }
    except Exception as e:
        logger.error(f"[FRONTEND-API] Operator analytics failed | error={e}")
        return {
            "total_decisions": 0,
            "approvals": 0,
            "rejections": 0,
            "timeouts": 0,
            "accuracy": None,
            "total_value_add_zar": "0",
        }


@router.get(
    "/experiments/list",
    summary="List Experiments",
    tags=["Frontend"],
)
async def get_experiments(
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    operator: str = Depends(_verify_bearer),
) -> dict[str, Any]:
    """List experiments with optional status filter."""
    try:
        query = """
            SELECT experiment_id, name, hypothesis,
                   strategy_variant, baseline_strategy,
                   status, max_trades, max_budget_zar,
                   start_date, created_at
            FROM experiment_definitions
        """
        params: dict[str, Any] = {}
        if status:
            query += " WHERE status = :status"
            params["status"] = status
        query += " ORDER BY created_at DESC"

        rows = db.execute(text(query), params).fetchall()

        experiments = [
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
                "created_at": r[9].isoformat() if r[9] else None,
            }
            for r in rows
        ]

        active = sum(1 for e in experiments if e["status"] == "ACTIVE")

        return {"experiments": experiments, "active": active}
    except Exception as e:
        logger.error(f"[FRONTEND-API] Experiments list failed | error={e}")
        return {"experiments": [], "active": 0}


@router.get(
    "/regimes/status",
    summary="Regime Status",
    tags=["Frontend"],
)
async def get_regime_status(
    db: Session = Depends(get_db),
    operator: str = Depends(_verify_bearer),
) -> dict[str, Any]:
    """Get current and recent regime classifications."""
    try:
        rows = db.execute(
            text("""
                SELECT DISTINCT ON (symbol) symbol, regime, confidence,
                       adx_value, created_at
                FROM regime_observations
                ORDER BY symbol, created_at DESC
            """)
        ).fetchall()

        current = [
            {
                "symbol": r[0],
                "regime": r[1],
                "confidence": str(r[2]),
                "adx_value": str(r[3]) if r[3] else None,
                "as_of": r[4].isoformat() if r[4] else None,
            }
            for r in rows
        ]

        history = db.execute(
            text("""
                SELECT symbol, regime, confidence, created_at
                FROM regime_observations
                ORDER BY created_at DESC
                LIMIT 50
            """)
        ).fetchall()

        return {
            "current": current,
            "history": [
                {
                    "symbol": r[0],
                    "regime": r[1],
                    "confidence": str(r[2]),
                    "created_at": r[3].isoformat() if r[3] else None,
                }
                for r in history
            ],
        }
    except Exception as e:
        logger.error(f"[FRONTEND-API] Regime status failed | error={e}")
        return {"current": [], "history": []}


@router.get(
    "/config/current",
    summary="System Configuration",
    tags=["Frontend"],
)
async def get_current_config(
    operator: str = Depends(_verify_bearer),
) -> dict[str, Any]:
    """Get current system configuration (secrets redacted)."""
    # Only non-sensitive configuration exposed
    safe_keys = [
        "EXECUTION_MODE",
        "STRATEGY_MODE",
        "EXECUTION_ENVIRONMENT",
        "LOG_LEVEL",
        "DB_HOST",
        "DB_PORT",
        "DB_NAME",
        "GUARDIAN_ENABLED",
        "HITL_ENABLED",
    ]

    config = []
    for key in safe_keys:
        value = os.environ.get(key)
        if value is not None:
            config.append({"key": key, "value": value})

    return {"config": config}


@router.get(
    "/audit/log",
    summary="Audit Log",
    tags=["Frontend"],
)
async def get_audit_log(
    limit: int = 50,
    db: Session = Depends(get_db),
    operator: str = Depends(_verify_bearer),
) -> dict[str, Any]:
    """Get recent audit log entries."""
    try:
        rows = db.execute(
            text("""
                SELECT id, action, target_type, target_id,
                       actor_id, payload, previous_state,
                       new_state, created_at
                FROM audit_log
                ORDER BY created_at DESC
                LIMIT :lim
            """),
            {"lim": limit},
        ).fetchall()

        entries = [
            {
                "id": str(r[0]),
                "action": r[1],
                "target_type": r[2],
                "target_id": str(r[3]) if r[3] else None,
                "actor_id": r[4],
                "payload": r[5],
                "previous_state": r[6],
                "new_state": r[7],
                "created_at": r[8].isoformat() if r[8] else None,
            }
            for r in rows
        ]

        return {"entries": entries, "total": len(entries)}
    except Exception as e:
        logger.error(f"[FRONTEND-API] Audit log failed | error={e}")
        return {"entries": [], "total": 0}


@router.get(
    "/market/health",
    summary="Market Data Health",
    tags=["Frontend"],
)
async def get_market_health(
    operator: str = Depends(_verify_bearer),
) -> dict[str, Any]:
    """Get data feed health status."""
    providers = [
        {"name": "VALR", "status": "CONFIGURED", "type": "exchange"},
        {"name": "TradingView", "status": "WEBHOOK", "type": "signal"},
    ]

    return {"providers": providers}

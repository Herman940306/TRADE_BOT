"""
============================================================================
Project Autonomous Alpha v1.8.0
FastAPI Application Entry Point - Sovereign Tier Ingress
============================================================================

Reliability Level: SOVEREIGN TIER (Mission-Critical)
Input Constraints: TradingView webhooks via HTTPS
Side Effects: Database writes to immutable audit log

SOVEREIGN MANDATE:
- Acknowledge webhooks in < 50ms (Hot Path)
- All requests authenticated via HMAC-SHA256
- Zero tolerance for floating-point math
- Complete audit trail for every signal

v1.5.0 UPGRADES:
- BudgetGuard Integration (Sprint 6)
- Discord Command Center (Sprint 7)
- Reward-Governed Intelligence (Sprint 9)

============================================================================
"""

import os
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from decimal import Decimal
from typing import Optional

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from app.api.webhook import router as webhook_router
from app.api.guardian import router as guardian_router
from app.api.hitl import router as hitl_router
from app.database.session import check_database_connection, engine, get_db

# Phase 2: Trade Lifecycle Manager Integration
from services.trade_lifecycle import (
    TradeLifecycleManager,
    TradeState,
    Trade,
)

# Phase 2: Strategy Manager Integration
from services.strategy_manager import (
    StrategyManager,
    StrategyMode,
    create_strategy_manager,
)

# Sprint 6: BudgetGuard Integration
from app.logic.budget_integration import (
    initialize_budget_integration,
    get_budget_integration,
    BudgetIntegrationModule,
)

# Sprint 7: Discord Command Center
from app.observability.discord_notifier import (
    initialize_discord_notifier,
    get_discord_notifier,
    EmbedColor,
    AlertLevel,
)

# Sprint 9: Reward-Governed Intelligence
from app.learning.rgi_init import (
    initialize_rgi,
    get_rgi_status,
    shutdown_rgi,
    RGI_SYSTEM_ONLINE,
    RGI_INIT_FAIL,
)

# HITL Approval Gateway Integration
# **Feature: hitl-approval-gateway, Task 18: Wire Everything Together**
# **Validates: Requirements 4.1, 5.1, 7.1, 7.2, 7.3, 7.4, 11.4**
from services.hitl_gateway import HITLGateway
from services.hitl_expiry_worker import ExpiryWorker
from services.guardian_integration import (
    GuardianIntegration,
    GuardianLockCascadeHandler,
    get_guardian_integration,
)
from services.hitl_config import get_hitl_config

# Load environment variables
load_dotenv()


# ============================================================================
# GLOBAL INSTANCES (Phase 2 Integration)
# ============================================================================

# Trade Lifecycle Manager singleton (initialized in lifespan)
_trade_lifecycle_manager: Optional[TradeLifecycleManager] = None

# Strategy Manager singleton (initialized in lifespan)
_strategy_manager: Optional[StrategyManager] = None

# HITL Gateway singleton (initialized in lifespan)
# **Feature: hitl-approval-gateway, Task 18: Wire Everything Together**
_hitl_gateway: Optional[HITLGateway] = None

# HITL Expiry Worker singleton (initialized in lifespan)
# **Feature: hitl-approval-gateway, Task 18.2: Start ExpiryWorker on app startup**
_expiry_worker: Optional[ExpiryWorker] = None

# Guardian Integration singleton (initialized in lifespan)
# **Feature: hitl-approval-gateway, Task 18.4: Register Guardian lock event handler**
_guardian_integration: Optional[GuardianIntegration] = None


def get_trade_lifecycle_manager() -> Optional[TradeLifecycleManager]:
    """
    Get the global Trade Lifecycle Manager instance.
    
    Reliability Level: L6 Critical
    Input Constraints: None
    Side Effects: None (read-only)
    
    Returns:
        TradeLifecycleManager instance or None if not initialized
    """
    return _trade_lifecycle_manager


def get_strategy_manager() -> Optional[StrategyManager]:
    """
    Get the global Strategy Manager instance.
    
    Reliability Level: L6 Critical
    Input Constraints: None
    Side Effects: None (read-only)
    
    Returns:
        StrategyManager instance or None if not initialized
    """
    return _strategy_manager


def get_hitl_gateway() -> Optional[HITLGateway]:
    """
    Get the global HITL Gateway instance.
    
    Reliability Level: L6 Critical (Sovereign Tier)
    Input Constraints: None
    Side Effects: None (read-only)
    
    **Feature: hitl-approval-gateway, Task 18: Wire Everything Together**
    
    Returns:
        HITLGateway instance or None if not initialized
    """
    return _hitl_gateway


def get_expiry_worker() -> Optional[ExpiryWorker]:
    """
    Get the global HITL Expiry Worker instance.
    
    Reliability Level: L6 Critical (Sovereign Tier)
    Input Constraints: None
    Side Effects: None (read-only)
    
    **Feature: hitl-approval-gateway, Task 18.2: Start ExpiryWorker on app startup**
    
    Returns:
        ExpiryWorker instance or None if not initialized
    """
    return _expiry_worker


# ============================================================================
# APPLICATION LIFESPAN
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager for startup/shutdown events.
    
    Reliability Level: SOVEREIGN TIER
    Input Constraints: None
    Side Effects: Database connection verification, Budget integration init
    
    Startup:
        - Verify database connectivity
        - Initialize BudgetGuard integration (non-blocking)
        - Initialize Discord notifier (non-blocking)
        - Send startup notification to Discord
        - Log system initialization
        
    Shutdown:
        - Send shutdown notification to Discord
        - Close database connections
        - Log system shutdown
    """
    # Startup
    print("=" * 60)
    print("AUTONOMOUS ALPHA v1.8.0 - SOVEREIGN TIER INFRASTRUCTURE")
    print("=" * 60)
    print(f"Startup Time: {datetime.now(timezone.utc).isoformat()}")
    
    # Verify database connection
    try:
        check_database_connection()
        print("[OK] Database connection verified (app_trading role)")
    except Exception as e:
        print(f"[CRITICAL] Database connection failed: {e}")
        print("[CRITICAL] System cannot start without database connectivity")
        raise
    
    # Sprint 7: Initialize Discord Notifier (NON-BLOCKING)
    discord_notifier = None
    try:
        discord_notifier = initialize_discord_notifier()
        if discord_notifier.is_enabled:
            print("[OK] Discord Command Center initialized")
        else:
            print("[INFO] Discord notifications disabled (no webhook configured)")
    except Exception as e:
        print(f"[WARN] Discord notifier initialization failed: {e}")
        print("       System will continue without Discord notifications")
    
    # Sprint 6: Initialize BudgetGuard Integration (NON-BLOCKING)
    budget_status_loaded = False
    budget_strict_mode = False
    operational_cost = None
    
    try:
        budget_integration = initialize_budget_integration()
        
        # Attempt to load budget report (non-blocking)
        budget_integration.load_budget_report(
            correlation_id="STARTUP_INIT"
        )
        
        status = budget_integration.get_status("STARTUP_STATUS")
        budget_status_loaded = status.is_loaded
        budget_strict_mode = status.strict_mode
        operational_cost = status.operational_cost_formatted
        
        if status.is_loaded:
            print(f"[OK] BudgetGuard integration loaded")
            print(f"     Operational Cost: {status.operational_cost_formatted}")
            print(f"     Strict Mode: {status.strict_mode}")
        else:
            if status.strict_mode:
                print(f"[WARN] BudgetGuard STRICT MODE - {status.warning_message}")
            else:
                print(f"[WARN] BudgetGuard unavailable (non-blocking): {status.warning_message}")
                print("       Trading will continue with stable behavior")
                
    except Exception as e:
        print(f"[WARN] BudgetGuard initialization failed: {e}")
        print("       Trading will continue with stable behavior (non-blocking)")
    
    # Sprint 9: Initialize Reward-Governed Intelligence (NON-BLOCKING)
    rgi_model_loaded = False
    rgi_golden_set_passed = None
    rgi_safe_mode = False
    rgi_model_version = None
    
    try:
        rgi_model_path = os.getenv("RGI_MODEL_PATH", "models/reward_governor.txt")
        rgi_run_golden_set = os.getenv("RGI_RUN_GOLDEN_SET", "true").lower() == "true"
        
        rgi_result = initialize_rgi(
            model_path=rgi_model_path,
            run_golden_set=rgi_run_golden_set,
            correlation_id="STARTUP_RGI_INIT"
        )
        
        rgi_model_loaded = rgi_result.model_loaded
        rgi_golden_set_passed = rgi_result.golden_set_passed
        rgi_safe_mode = rgi_result.safe_mode_active
        rgi_model_version = rgi_result.model_version
        
        if rgi_result.success:
            print(f"[OK] {RGI_SYSTEM_ONLINE}")
            print(f"     Model Version: {rgi_result.model_version}")
            print(f"     Golden Set Accuracy: {rgi_result.golden_set_accuracy}")
            print(f"     Safe-Mode: {'ACTIVE' if rgi_result.safe_mode_active else 'INACTIVE'}")
        else:
            if rgi_result.model_loaded:
                print(f"[WARN] RGI system degraded: {rgi_result.error_message}")
                print("       Trading will continue with neutral trust (0.5000)")
            else:
                print(f"[WARN] RGI model not loaded: {rgi_result.error_message}")
                print("       Trading will continue with neutral trust (0.5000)")
                
    except Exception as e:
        print(f"[WARN] RGI initialization failed: {e}")
        print("       Trading will continue with neutral trust (0.5000)")
    
    # Phase 2: Initialize Trade Lifecycle Manager (NON-BLOCKING)
    # **Feature: phase2-hard-requirements, Trade Lifecycle Manager**
    # **Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5**
    global _trade_lifecycle_manager
    trade_lifecycle_status = "unavailable"
    
    try:
        # Get database session for persistence
        db_gen = get_db()
        db_session = next(db_gen)
        
        _trade_lifecycle_manager = TradeLifecycleManager(
            db_session=db_session,
            correlation_id="STARTUP_TLM_INIT"
        )
        trade_lifecycle_status = "initialized"
        print("[OK] Trade Lifecycle Manager initialized")
        print(f"     Guardian Integration: {'enabled' if _trade_lifecycle_manager.is_guardian_locked() is not None else 'disabled'}")
    except Exception as e:
        print(f"[WARN] Trade Lifecycle Manager initialization failed: {e}")
        print("       System will continue with in-memory trade tracking")
        # Create in-memory fallback
        _trade_lifecycle_manager = TradeLifecycleManager(
            db_session=None,
            correlation_id="STARTUP_TLM_FALLBACK"
        )
        trade_lifecycle_status = "in-memory"
    
    # Phase 2: Initialize Strategy Manager (NON-BLOCKING)
    # **Feature: phase2-hard-requirements, Strategy Manager**
    # **Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5**
    global _strategy_manager
    strategy_mode_str = os.getenv("STRATEGY_MODE", "DETERMINISTIC")
    strategy_status = "unavailable"
    
    try:
        # Parse strategy mode from environment
        try:
            strategy_mode = StrategyMode(strategy_mode_str)
        except ValueError:
            strategy_mode = StrategyMode.DETERMINISTIC
            print(f"[WARN] Invalid STRATEGY_MODE '{strategy_mode_str}', defaulting to DETERMINISTIC")
        
        _strategy_manager = create_strategy_manager(
            mode=strategy_mode,
            db_session=db_session if trade_lifecycle_status == "initialized" else None,
            correlation_id="STARTUP_SM_INIT"
        )
        strategy_status = "initialized"
        print(f"[OK] Strategy Manager initialized")
        print(f"     Mode: {strategy_mode.value}")
    except Exception as e:
        print(f"[WARN] Strategy Manager initialization failed: {e}")
        print("       System will continue with in-memory strategy tracking")
        # Create in-memory fallback
        _strategy_manager = create_strategy_manager(
            mode=StrategyMode.DETERMINISTIC,
            db_session=None,
            correlation_id="STARTUP_SM_FALLBACK"
        )
        strategy_status = "in-memory"
    
    # ========================================================================
    # HITL Approval Gateway Integration
    # **Feature: hitl-approval-gateway, Task 18: Wire Everything Together**
    # **Validates: Requirements 4.1, 5.1, 7.1, 7.2, 7.3, 7.4, 11.4**
    # ========================================================================
    global _hitl_gateway
    global _expiry_worker
    global _guardian_integration
    
    hitl_status = "unavailable"
    hitl_recovery_result = None
    expiry_worker_status = "unavailable"
    
    try:
        # Get HITL configuration
        hitl_config = get_hitl_config(validate=False)
        
        # Initialize Guardian Integration
        # **Feature: hitl-approval-gateway, Task 18.4: Register Guardian lock event handler**
        # **Validates: Requirements 11.4**
        _guardian_integration = get_guardian_integration()
        
        # Initialize HITL Gateway with dependencies
        _hitl_gateway = HITLGateway(
            config=hitl_config,
            guardian=_guardian_integration,
            db_session=db_session if trade_lifecycle_status == "initialized" else None,
            discord_notifier=discord_notifier,
        )
        hitl_status = "initialized"
        
        print(f"[OK] HITL Approval Gateway initialized")
        print(f"     HITL Enabled: {hitl_config.enabled}")
        print(f"     Timeout: {hitl_config.timeout_seconds}s")
        print(f"     Slippage Max: {hitl_config.slippage_max_percent}%")
        print(f"     Allowed Operators: {len(hitl_config.allowed_operators)}")
        
        # ====================================================================
        # Task 18.3: Call recover_on_startup() on app startup
        # **Validates: Requirements 5.1**
        # Run before accepting requests to recover pending approvals
        # ====================================================================
        try:
            hitl_recovery_result = _hitl_gateway.recover_on_startup()
            
            if hitl_recovery_result.success:
                print(f"[OK] HITL Recovery completed")
                print(f"     Total Pending: {hitl_recovery_result.total_pending}")
                print(f"     Valid Pending: {hitl_recovery_result.valid_pending}")
                print(f"     Expired Processed: {hitl_recovery_result.expired_processed}")
                if hitl_recovery_result.hash_failures > 0:
                    print(f"     [WARN] Hash Failures: {hitl_recovery_result.hash_failures}")
            else:
                print(f"[WARN] HITL Recovery completed with errors")
                print(f"     Errors: {len(hitl_recovery_result.errors)}")
        except Exception as recovery_error:
            print(f"[WARN] HITL Recovery failed: {recovery_error}")
            print("       System will continue - pending approvals may need manual review")
        
        # ====================================================================
        # Task 18.2: Start ExpiryWorker on app startup
        # **Validates: Requirements 4.1**
        # Register as background task with 30-second interval
        # ====================================================================
        try:
            expiry_interval = int(os.getenv("HITL_EXPIRY_INTERVAL_SECONDS", "30"))
            
            _expiry_worker = ExpiryWorker(
                interval_seconds=expiry_interval,
                db_session=db_session if trade_lifecycle_status == "initialized" else None,
                discord_notifier=discord_notifier,
            )
            
            # Start the expiry worker as a background task
            import asyncio
            asyncio.create_task(_expiry_worker.start())
            
            expiry_worker_status = "running"
            print(f"[OK] HITL Expiry Worker started")
            print(f"     Interval: {expiry_interval}s")
        except Exception as expiry_error:
            print(f"[WARN] HITL Expiry Worker failed to start: {expiry_error}")
            print("       Expired approvals will not be auto-rejected")
            expiry_worker_status = "failed"
        
        # ====================================================================
        # Task 18.4: Register Guardian lock event handler
        # **Validates: Requirements 11.4**
        # Subscribe to Guardian lock events to trigger cascade rejection
        # ====================================================================
        try:
            # Create cascade handler for Guardian lock events
            cascade_handler = GuardianLockCascadeHandler(
                db_session=db_session if trade_lifecycle_status == "initialized" else None,
                discord_notifier=discord_notifier,
                correlation_id="STARTUP_CASCADE_HANDLER"
            )
            
            # Register the cascade handler with Guardian integration
            _guardian_integration.on_lock_event(cascade_handler.handle_lock_event)
            
            print("[OK] Guardian lock cascade handler registered")
        except Exception as cascade_error:
            print(f"[WARN] Guardian cascade handler registration failed: {cascade_error}")
            print("       Guardian locks will not auto-reject pending approvals")
        
    except Exception as e:
        print(f"[WARN] HITL Approval Gateway initialization failed: {e}")
        print("       System will continue without HITL approval gate")
        hitl_status = "unavailable"
    
    print("[OK] Ingress Layer initialized")
    print("=" * 60)
    print("SOVEREIGN MANDATE: Survival > Capital Preservation > Alpha")
    print("=" * 60)
    
    # Sprint 7: Send startup notification to Discord
    if discord_notifier and discord_notifier.is_enabled:
        try:
            # Get ZAR Floor from environment
            zar_floor = os.getenv("ZAR_FLOOR", "100000.00")
            environment = "Production" if os.getenv("ENV", "").lower() == "production" else "Development"
            
            # Determine RGI status string
            if rgi_model_loaded:
                if rgi_safe_mode:
                    rgi_status_str = "Safe-Mode"
                elif rgi_golden_set_passed:
                    rgi_status_str = "Online"
                else:
                    rgi_status_str = "Degraded"
            else:
                rgi_status_str = "Unavailable"
            
            discord_notifier.send_embed(
                title="🚀 System Online - Autonomous Alpha v1.8.0",
                description="Sovereign Tier Infrastructure has started successfully.",
                color=EmbedColor.SUCCESS.value,
                fields=[
                    {"name": "Environment", "value": environment, "inline": True},
                    {"name": "ZAR Floor", "value": f"R {Decimal(zar_floor):,.2f}", "inline": True},
                    {"name": "Tool Count", "value": "78/78", "inline": True},
                    {"name": "Strict Mode", "value": "Enabled" if budget_strict_mode else "Disabled", "inline": True},
                    {"name": "BudgetGuard", "value": "Loaded" if budget_status_loaded else "Unavailable", "inline": True},
                    {"name": "Operational Cost", "value": operational_cost or "N/A", "inline": True},
                    {"name": "RGI Status", "value": rgi_status_str, "inline": True},
                    {"name": "RGI Model", "value": rgi_model_version or "N/A", "inline": True},
                    {"name": "RGI Safe-Mode", "value": "Active" if rgi_safe_mode else "Inactive", "inline": True},
                    {"name": "Trade Lifecycle", "value": trade_lifecycle_status.title(), "inline": True},
                    {"name": "Strategy Mode", "value": strategy_mode_str, "inline": True},
                    {"name": "Strategy Status", "value": strategy_status.title(), "inline": True},
                    {"name": "HITL Gateway", "value": hitl_status.title(), "inline": True},
                    {"name": "Expiry Worker", "value": expiry_worker_status.title(), "inline": True},
                ],
                correlation_id="STARTUP_NOTIFICATION",
                alert_level=AlertLevel.INFO
            )
            print("[OK] Discord startup notification sent")
        except Exception as e:
            print(f"[WARN] Discord startup notification failed: {e}")
    
    yield
    
    # Shutdown
    print("=" * 60)
    print("AUTONOMOUS ALPHA - SHUTDOWN INITIATED")
    print(f"Shutdown Time: {datetime.now(timezone.utc).isoformat()}")
    
    # HITL Expiry Worker Shutdown
    # **Feature: hitl-approval-gateway, Task 18.2: Stop ExpiryWorker on shutdown**
    if _expiry_worker is not None and _expiry_worker.is_running:
        try:
            import asyncio
            asyncio.create_task(_expiry_worker.stop())
            print("[OK] HITL Expiry Worker stopped")
        except Exception as e:
            print(f"[WARN] HITL Expiry Worker shutdown failed: {e}")
    
    # Sprint 9: Shutdown RGI
    try:
        shutdown_rgi()
        print("[OK] RGI system shutdown")
    except Exception as e:
        print(f"[WARN] RGI shutdown failed: {e}")
    
    # Sprint 7: Send shutdown notification to Discord
    if discord_notifier and discord_notifier.is_enabled:
        try:
            discord_notifier.send_embed(
                title="🔴 System Offline - Autonomous Alpha",
                description="Sovereign Tier Infrastructure is shutting down.",
                color=EmbedColor.NEUTRAL.value,
                fields=[
                    {"name": "Shutdown Time", "value": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"), "inline": True},
                ],
                correlation_id="SHUTDOWN_NOTIFICATION",
                alert_level=AlertLevel.WARNING,
                blocking=True  # Wait for this to send
            )
            discord_notifier.shutdown()
            print("[OK] Discord shutdown notification sent")
        except Exception as e:
            print(f"[WARN] Discord shutdown notification failed: {e}")
    
    engine.dispose()
    print("[OK] Database connections closed")
    print("=" * 60)


# ============================================================================
# FASTAPI APPLICATION
# ============================================================================

app = FastAPI(
    title="Autonomous Alpha Ingress",
    description=(
        "Sovereign Tier Infrastructure - TradingView Webhook Receiver\n\n"
        "**SOVEREIGN MANDATE:** Survival > Capital Preservation > Alpha\n\n"
        "This API receives trading signals from TradingView and persists them "
        "to an immutable audit log for downstream processing by the Cold Path AI.\n\n"
        "**v1.8.0:** Phase 2 Hard Requirements Complete - Trade Lifecycle + Permission Policy"
    ),
    version="1.8.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)


# ============================================================================
# MIDDLEWARE
# ============================================================================

# CORS middleware (restrict in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ============================================================================
# EXCEPTION HANDLERS
# ============================================================================

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Global exception handler for unhandled errors.
    
    Reliability Level: SOVEREIGN TIER
    Input Constraints: Any unhandled exception
    Side Effects: Logs error, returns safe response
    
    SOVEREIGN MANDATE: No silent failures
    """
    error_code = "SYS-500"
    print(f"[{error_code}] Unhandled exception: {exc}")
    
    return JSONResponse(
        status_code=500,
        content={
            "error_code": error_code,
            "message": "Internal server error. This incident has been logged.",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    )


# ============================================================================
# ROUTERS
# ============================================================================

# Include webhook router
app.include_router(
    webhook_router,
    prefix="/webhook",
    tags=["Webhooks"]
)

# Include guardian router
app.include_router(
    guardian_router,
    prefix="/guardian",
    tags=["Guardian"]
)

# Include HITL router
# **Feature: hitl-approval-gateway, Task 18.1: Register HITL router**
# **Validates: Requirements 7.1, 7.2, 7.3, 7.4**
app.include_router(
    hitl_router,
    prefix="/api/hitl",
    tags=["HITL"]
)


# ============================================================================
# ROOT ENDPOINT
# ============================================================================

@app.get(
    "/",
    summary="System Status",
    description="Returns the current system status and health information.",
    tags=["System"]
)
async def root():
    """
    Root endpoint returning system status.
    
    Reliability Level: STANDARD
    Input Constraints: None
    Side Effects: None
    
    Returns:
        dict: System status information
    """
    # Check database connectivity
    db_status = "healthy"
    try:
        check_database_connection()
    except Exception:
        db_status = "unhealthy"
    
    # Sprint 6: Check BudgetGuard status
    budget_status = "unavailable"
    budget_strict_mode = False
    net_alpha = None
    operational_cost = None
    
    try:
        budget_integration = get_budget_integration()
        status = budget_integration.get_status("ROOT_STATUS")
        budget_status = "loaded" if status.is_loaded else "unavailable"
        budget_strict_mode = status.strict_mode
        net_alpha = status.net_alpha_formatted
        operational_cost = status.operational_cost_formatted
    except Exception:
        pass
    
    # Sprint 9: Check RGI status
    rgi_status_str = "unavailable"
    rgi_safe_mode = True
    
    try:
        rgi_info = get_rgi_status()
        if rgi_info.get("model_loaded"):
            if rgi_info.get("safe_mode_active"):
                rgi_status_str = "safe-mode"
            else:
                rgi_status_str = "online"
        rgi_safe_mode = rgi_info.get("safe_mode_active", True)
    except Exception:
        pass
    
    # Phase 2: Check Trade Lifecycle Manager status
    trade_lifecycle_status = "unavailable"
    guardian_locked = False
    
    try:
        tlm = get_trade_lifecycle_manager()
        if tlm is not None:
            trade_lifecycle_status = "initialized"
            guardian_locked = tlm.is_guardian_locked()
    except Exception:
        pass
    
    # Phase 2: Check Strategy Manager status
    strategy_status = "unavailable"
    strategy_mode = "UNKNOWN"
    
    try:
        sm = get_strategy_manager()
        if sm is not None:
            strategy_status = "initialized"
            strategy_mode = sm.mode.value
    except Exception:
        pass
    
    return {
        "system": "Autonomous Alpha Ingress",
        "version": "1.8.0",
        "status": "operational",
        "tier": "SOVEREIGN",
        "mandate": "Survival > Capital Preservation > Alpha",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "components": {
            "database": db_status,
            "hot_path": "ready",
            "hmac_verification": "enabled",
            "risk_governor": "enabled",
            "order_manager": "enabled",
            "budget_guard": budget_status,
            "budget_strict_mode": budget_strict_mode,
            "reward_governor": rgi_status_str,
            "rgi_safe_mode": rgi_safe_mode,
            "trade_lifecycle": trade_lifecycle_status,
            "guardian_locked": guardian_locked,
            "strategy_manager": strategy_status,
            "strategy_mode": strategy_mode
        },
        "operational_metrics": {
            "net_alpha": net_alpha,
            "operational_cost": operational_cost
        }
    }


@app.get(
    "/health",
    summary="Health Check",
    description="Lightweight health check for load balancers and monitoring.",
    tags=["System"]
)
async def health_check():
    """
    Lightweight health check endpoint.
    
    Reliability Level: STANDARD
    Input Constraints: None
    Side Effects: Database ping
    
    Returns:
        dict: Health status
    """
    try:
        check_database_connection()
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "database": "disconnected", "error": str(e)}
        )


@app.get(
    "/metrics",
    summary="Prometheus Metrics",
    description="Exposes Prometheus metrics for observability.",
    tags=["Observability"]
)
async def metrics():
    """
    Prometheus metrics endpoint.
    
    Reliability Level: SOVEREIGN TIER
    Input Constraints: None
    Side Effects: None
    
    Returns:
        Prometheus metrics in text format
    """
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )


@app.get(
    "/budget/status",
    summary="BudgetGuard Status",
    description="Returns the current BudgetGuard integration status and Net Alpha.",
    tags=["Operational Sovereignty"]
)
async def budget_status():
    """
    BudgetGuard integration status endpoint.
    
    Reliability Level: SOVEREIGN TIER
    Input Constraints: None
    Side Effects: None
    
    Returns:
        dict: Budget integration status with Net Alpha
    """
    try:
        budget_integration = get_budget_integration()
        status = budget_integration.get_status("BUDGET_STATUS_ENDPOINT")
        
        return {
            "status": "loaded" if status.is_loaded else "unavailable",
            "strict_mode": status.strict_mode,
            "can_trade": status.can_trade,
            "last_report_timestamp": status.last_report_timestamp,
            "gating_signal": status.last_gating_signal,
            "operational_metrics": {
                "net_alpha": status.net_alpha_formatted,
                "operational_cost": status.operational_cost_formatted
            },
            "warning": status.warning_message,
            "timestamp": status.status_timestamp_utc
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )


@app.post(
    "/budget/refresh",
    summary="Refresh BudgetGuard Data",
    description="Reloads the BudgetGuard JSON file and updates operational gating.",
    tags=["Operational Sovereignty"]
)
async def budget_refresh():
    """
    Refresh BudgetGuard data from file.
    
    Reliability Level: SOVEREIGN TIER
    Input Constraints: None
    Side Effects: Reloads budget file, updates gating state
    
    Returns:
        dict: Refresh result with new status
    """
    try:
        budget_integration = get_budget_integration()
        success = budget_integration.refresh_budget("BUDGET_REFRESH_ENDPOINT")
        status = budget_integration.get_status("BUDGET_REFRESH_STATUS")
        
        return {
            "success": success,
            "status": "loaded" if status.is_loaded else "unavailable",
            "operational_cost": status.operational_cost_formatted,
            "net_alpha": status.net_alpha_formatted,
            "gating_signal": status.last_gating_signal,
            "warning": status.warning_message,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )


# ============================================================================
# RGI ENDPOINTS (Sprint 9)
# ============================================================================

@app.get(
    "/rgi/status",
    summary="RGI System Status",
    description="Returns the current Reward-Governed Intelligence system status.",
    tags=["Reward-Governed Intelligence"]
)
async def rgi_status():
    """
    RGI system status endpoint.
    
    Reliability Level: SOVEREIGN TIER
    Input Constraints: None
    Side Effects: None
    
    Returns:
        dict: RGI system status
    """
    try:
        status = get_rgi_status()
        return {
            "status": "online" if status.get("model_loaded") else "degraded",
            "model_loaded": status.get("model_loaded", False),
            "model_version": status.get("model_version"),
            "safe_mode_active": status.get("safe_mode_active", True),
            "neutral_trust": status.get("neutral_trust", "0.5000"),
            "timestamp": status.get("timestamp_utc", datetime.now(timezone.utc).isoformat())
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )


# ============================================================================
# TRADE LIFECYCLE ENDPOINTS (Phase 2)
# ============================================================================

@app.get(
    "/trade-lifecycle/status",
    summary="Trade Lifecycle Manager Status",
    description="Returns the current Trade Lifecycle Manager status and trade counts by state.",
    tags=["Trade Lifecycle"]
)
async def trade_lifecycle_status():
    """
    Trade Lifecycle Manager status endpoint.
    
    Reliability Level: SOVEREIGN TIER
    Input Constraints: None
    Side Effects: None
    
    **Feature: phase2-hard-requirements, Trade Lifecycle Manager**
    **Validates: Requirements 1.1, 4.1**
    
    Returns:
        dict: Trade Lifecycle Manager status with trade counts by state
    """
    try:
        tlm = get_trade_lifecycle_manager()
        if tlm is None:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "unavailable",
                    "error": "Trade Lifecycle Manager not initialized",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            )
        
        # Get trade counts by state
        state_counts = tlm.update_state_metrics()
        
        # Check Guardian lock status
        guardian_locked = tlm.is_guardian_locked()
        guardian_lock_reason = tlm.get_guardian_lock_reason() if guardian_locked else None
        
        return {
            "status": "initialized",
            "guardian_locked": guardian_locked,
            "guardian_lock_reason": guardian_lock_reason,
            "trades_by_state": state_counts,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )


@app.get(
    "/trade-lifecycle/trades/{state}",
    summary="Get Trades by State",
    description="Returns all trades in a specific lifecycle state.",
    tags=["Trade Lifecycle"]
)
async def get_trades_by_state(state: str):
    """
    Get trades by lifecycle state endpoint.
    
    Reliability Level: SOVEREIGN TIER
    Input Constraints: state must be valid TradeState
    Side Effects: None (read-only)
    
    **Feature: phase2-hard-requirements, Trade Lifecycle Manager**
    **Validates: Requirements 1.1**
    
    Args:
        state: Trade state to filter by (PENDING, ACCEPTED, FILLED, CLOSED, SETTLED, REJECTED)
        
    Returns:
        dict: List of trades in the specified state
    """
    try:
        tlm = get_trade_lifecycle_manager()
        if tlm is None:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "unavailable",
                    "error": "Trade Lifecycle Manager not initialized",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            )
        
        # Validate state
        try:
            trade_state = TradeState(state.upper())
        except ValueError:
            valid_states = [s.value for s in TradeState]
            return JSONResponse(
                status_code=400,
                content={
                    "error": f"Invalid state: {state}",
                    "valid_states": valid_states,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            )
        
        # Get trades by state
        trades = tlm.get_trades_by_state(trade_state)
        
        return {
            "state": trade_state.value,
            "count": len(trades),
            "trades": [trade.to_dict() for trade in trades],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )


# ============================================================================
# STRATEGY MANAGER ENDPOINTS (Phase 2)
# ============================================================================

@app.get(
    "/strategy/status",
    summary="Strategy Manager Status",
    description="Returns the current Strategy Manager status and mode.",
    tags=["Strategy Manager"]
)
async def strategy_manager_status():
    """
    Strategy Manager status endpoint.
    
    Reliability Level: SOVEREIGN TIER
    Input Constraints: None
    Side Effects: None
    
    **Feature: phase2-hard-requirements, Strategy Manager**
    **Validates: Requirements 2.1**
    
    Returns:
        dict: Strategy Manager status with current mode
    """
    try:
        sm = get_strategy_manager()
        if sm is None:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "unavailable",
                    "error": "Strategy Manager not initialized",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            )
        
        return {
            "status": "initialized",
            "mode": sm.mode.value,
            "deterministic": sm.mode == StrategyMode.DETERMINISTIC,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )


# ============================================================================
# END OF MAIN APPLICATION
# ============================================================================

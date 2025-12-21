"""
============================================================================
Project Autonomous Alpha v1.3.2
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

============================================================================
"""

import os
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from app.api.webhook import router as webhook_router
from app.database.session import check_database_connection, engine

# Load environment variables
load_dotenv()


# ============================================================================
# APPLICATION LIFESPAN
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager for startup/shutdown events.
    
    Reliability Level: SOVEREIGN TIER
    Input Constraints: None
    Side Effects: Database connection verification
    
    Startup:
        - Verify database connectivity
        - Log system initialization
        
    Shutdown:
        - Close database connections
        - Log system shutdown
    """
    # Startup
    print("=" * 60)
    print("AUTONOMOUS ALPHA v1.3.2 - SOVEREIGN TIER INFRASTRUCTURE")
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
    
    print("[OK] Ingress Layer initialized")
    print("=" * 60)
    print("SOVEREIGN MANDATE: Survival > Capital Preservation > Alpha")
    print("=" * 60)
    
    yield
    
    # Shutdown
    print("=" * 60)
    print("AUTONOMOUS ALPHA - SHUTDOWN INITIATED")
    print(f"Shutdown Time: {datetime.now(timezone.utc).isoformat()}")
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
        "to an immutable audit log for downstream processing by the Cold Path AI."
    ),
    version="1.3.2",
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
    
    return {
        "system": "Autonomous Alpha Ingress",
        "version": "1.3.2",
        "status": "operational",
        "tier": "SOVEREIGN",
        "mandate": "Survival > Capital Preservation > Alpha",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "components": {
            "database": db_status,
            "hot_path": "ready",
            "hmac_verification": "enabled"
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


# ============================================================================
# END OF MAIN APPLICATION
# ============================================================================

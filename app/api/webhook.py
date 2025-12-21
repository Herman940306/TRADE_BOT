"""
============================================================================
Project Autonomous Alpha v1.3.2
Webhook API - TradingView Signal Ingestion (Hot Path)
============================================================================

Reliability Level: SOVEREIGN TIER (Mission-Critical)
Input Constraints: 
    - HMAC-SHA256 signed payloads
    - JSON body matching SignalIn schema
    - Source IP from TradingView whitelist
Side Effects: 
    - Inserts signal into immutable audit log
    - Generates correlation_id for downstream tracing

SOVEREIGN MANDATE:
- Acknowledge webhooks in < 50ms
- Byte-perfect HMAC verification (no parsing before auth)
- Zero tolerance for floating-point math
- Atomic database writes with full audit trail

HOT PATH FLOW:
1. Receive raw bytes
2. Verify HMAC signature (byte-perfect)
3. Parse JSON to Pydantic model (validates decimals)
4. Generate correlation_id (UUID4)
5. Atomic INSERT to signals table
6. Return correlation_id for tracing

============================================================================
"""

import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Request, Depends, HTTPException, Header
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import ValidationError

from app.schemas.signal import SignalIn, SignalOut
from app.auth.security import verify_hmac_signature, HMACVerificationError
from app.database.session import get_db


# ============================================================================
# ROUTER
# ============================================================================

router = APIRouter()


# ============================================================================
# CONSTANTS
# ============================================================================

# TradingView signature header name
SIGNATURE_HEADER = "X-TradingView-Signature"


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def extract_client_ip(request: Request) -> str:
    """
    Extract client IP address from request.
    
    Reliability Level: STANDARD
    Input Constraints: FastAPI Request object
    Side Effects: None
    
    Returns:
        str: Client IP address
        
    Note: Handles X-Forwarded-For header for reverse proxy setups
    """
    # Check for forwarded header (reverse proxy)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Take the first IP in the chain
        return forwarded_for.split(",")[0].strip()
    
    # Fall back to direct client IP
    return request.client.host if request.client else "0.0.0.0"


def create_error_response(
    error_code: str,
    message: str,
    status_code: int = 400,
    details: Optional[dict] = None
) -> JSONResponse:
    """
    Create standardized error response.
    
    Reliability Level: STANDARD
    Input Constraints: Error code, message, optional details
    Side Effects: None
    
    Returns:
        JSONResponse: Formatted error response
    """
    content = {
        "error_code": error_code,
        "message": message,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    if details:
        content["details"] = details
    
    return JSONResponse(status_code=status_code, content=content)


# ============================================================================
# WEBHOOK ENDPOINT
# ============================================================================

@router.post(
    "/tradingview",
    summary="Receive TradingView Signal",
    description=(
        "Receives and validates trading signals from TradingView webhooks.\n\n"
        "**Authentication:** HMAC-SHA256 signature in X-TradingView-Signature header\n\n"
        "**Validation:** All financial values must be Decimal (no floats)\n\n"
        "**Response:** Returns correlation_id for downstream tracing"
    ),
    response_model=dict,
    responses={
        200: {
            "description": "Signal accepted and persisted",
            "content": {
                "application/json": {
                    "example": {
                        "status": "accepted",
                        "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
                        "signal_id": "TV-SIGNAL-12345",
                        "timestamp": "2024-01-01T00:00:00.000000Z"
                    }
                }
            }
        },
        401: {"description": "HMAC signature verification failed (SEC-001 to SEC-004)"},
        409: {"description": "Duplicate signal_id (idempotency violation)"},
        422: {"description": "Validation error (AUD-001 for float detection)"},
        500: {"description": "Database error (L6 Lockdown consideration)"}
    }
)
async def receive_tradingview_signal(
    request: Request,
    db: Session = Depends(get_db),
    x_tradingview_signature: Optional[str] = Header(None, alias="X-TradingView-Signature")
):
    """
    Receive and process TradingView webhook signal.
    
    Reliability Level: SOVEREIGN TIER (Mission-Critical)
    Input Constraints:
        - Valid HMAC-SHA256 signature
        - JSON body matching SignalIn schema
        - Decimal values for price/quantity (no floats)
    Side Effects:
        - Inserts signal into immutable audit log
        - Generates correlation_id
    
    HOT PATH REQUIREMENTS:
        - Target: < 50ms acknowledgment
        - Byte-perfect signature verification
        - Atomic database write
        
    Returns:
        dict: Acceptance confirmation with correlation_id
        
    Raises:
        HTTPException: On validation or authentication failure
    """
    start_time = datetime.now(timezone.utc)
    
    # ========================================================================
    # STEP 1: Get raw bytes (BEFORE any parsing)
    # ========================================================================
    # CRITICAL: Must get raw bytes for byte-perfect HMAC verification
    raw_body = await request.body()
    
    # ========================================================================
    # STEP 2: Verify HMAC signature
    # ========================================================================
    try:
        verify_hmac_signature(
            payload=raw_body,
            provided_signature=x_tradingview_signature
        )
        hmac_verified = True
    except HMACVerificationError as e:
        print(f"[{e.error_code}] HMAC verification failed: {e.message}")
        return create_error_response(
            error_code=e.error_code,
            message=e.message,
            status_code=401
        )
    
    # ========================================================================
    # STEP 3: Parse and validate JSON payload
    # ========================================================================
    try:
        # Parse JSON
        payload_dict = json.loads(raw_body.decode("utf-8"))
        
        # Validate with Pydantic (enforces Decimal, rejects floats)
        signal_in = SignalIn(**payload_dict)
        
    except json.JSONDecodeError as e:
        return create_error_response(
            error_code="VAL-001",
            message=f"Invalid JSON payload: {e.msg}",
            status_code=400
        )
    except ValidationError as e:
        # Check for AUD-001 (float detection) errors
        errors = e.errors()
        error_messages = str(errors)
        
        if "AUD-001" in error_messages:
            return create_error_response(
                error_code="AUD-001",
                message="Float type detected in financial field. Sovereign Mandate: Use Decimal string.",
                status_code=422,
                details={"validation_errors": [str(err) for err in errors]}
            )
        
        # Other validation errors
        return create_error_response(
            error_code="VAL-002",
            message="Payload validation failed",
            status_code=422,
            details={"validation_errors": [str(err) for err in errors]}
        )
    except ValueError as e:
        # Catch ValueError from our custom validators (AUD-001)
        error_msg = str(e)
        if "AUD-001" in error_msg:
            return create_error_response(
                error_code="AUD-001",
                message=error_msg,
                status_code=422
            )
        raise
    
    # ========================================================================
    # STEP 4: Generate correlation_id
    # ========================================================================
    correlation_id = uuid.uuid4()
    
    # ========================================================================
    # STEP 5: Extract client IP
    # ========================================================================
    source_ip = extract_client_ip(request)
    
    # ========================================================================
    # STEP 6: Atomic database INSERT
    # ========================================================================
    try:
        # Use raw SQL for maximum control and performance
        insert_sql = text("""
            INSERT INTO signals (
                correlation_id,
                signal_id,
                symbol,
                side,
                price,
                quantity,
                raw_payload,
                source_ip,
                hmac_verified,
                row_hash
            ) VALUES (
                :correlation_id,
                :signal_id,
                :symbol,
                :side,
                :price,
                :quantity,
                CAST(:raw_payload AS jsonb),
                CAST(:source_ip AS inet),
                :hmac_verified,
                'placeholder'
            )
            RETURNING id, created_at
        """)
        
        result = db.execute(
            insert_sql,
            {
                "correlation_id": str(correlation_id),
                "signal_id": signal_in.signal_id,
                "symbol": signal_in.symbol,
                "side": signal_in.side.value if hasattr(signal_in.side, 'value') else str(signal_in.side),
                "price": str(signal_in.price),
                "quantity": str(signal_in.quantity),
                "raw_payload": raw_body.decode("utf-8"),
                "source_ip": source_ip,
                "hmac_verified": hmac_verified
            }
        )
        
        row = result.fetchone()
        db.commit()
        
        record_id = row[0]
        created_at = row[1]
        
    except Exception as e:
        db.rollback()
        error_str = str(e)
        
        # Log full error for debugging
        print(f"[DB-500] Database insert failed: {error_str}")
        print(f"[DB-500] Full exception: {repr(e)}")
        
        # Check for duplicate signal_id (idempotency violation)
        if "signals_signal_id_unique" in error_str or "duplicate key" in error_str.lower():
            return create_error_response(
                error_code="IDP-001",
                message=f"Duplicate signal_id: {signal_in.signal_id}. Signal already processed.",
                status_code=409
            )
        
        # Check for CHECK constraint violation (side value)
        if "signals_side_check" in error_str or "check constraint" in error_str.lower():
            return create_error_response(
                error_code="VAL-003",
                message=f"Invalid side value. Must be 'BUY' or 'SELL'.",
                status_code=422
            )
        
        # Database error - potential L6 Lockdown trigger
        return create_error_response(
            error_code="DB-500",
            message=f"Database write failed. L6 Lockdown consideration triggered. Error: {error_str[:200]}",
            status_code=500
        )
    
    # ========================================================================
    # STEP 7: Calculate processing time
    # ========================================================================
    end_time = datetime.now(timezone.utc)
    processing_ms = (end_time - start_time).total_seconds() * 1000
    
    # Log Hot Path performance
    if processing_ms > 50:
        print(f"[WARN] Hot Path exceeded 50ms target: {processing_ms:.2f}ms")
    
    # ========================================================================
    # STEP 8: Return success response
    # ========================================================================
    return {
        "status": "accepted",
        "correlation_id": str(correlation_id),
        "signal_id": signal_in.signal_id,
        "record_id": record_id,
        "timestamp": created_at.isoformat() if created_at else end_time.isoformat(),
        "processing_ms": round(processing_ms, 2),
        "hmac_verified": hmac_verified
    }


# ============================================================================
# END OF WEBHOOK API
# ============================================================================

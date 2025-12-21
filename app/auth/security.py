"""
============================================================================
Project Autonomous Alpha v1.3.2
Security Module - HMAC-SHA256 Signature Verification
============================================================================

Reliability Level: SOVEREIGN TIER (Mission-Critical)
Input Constraints: Raw request body bytes, signature header
Side Effects: None (pure verification)

SOVEREIGN MANDATE:
- All webhooks MUST be verified via HMAC-SHA256
- Signature mismatch triggers immediate rejection
- No silent failures - explicit error codes

============================================================================
"""

import hmac
import hashlib
import os
from typing import Optional

from dotenv import load_dotenv

# Load environment variables
load_dotenv()


# ============================================================================
# CONSTANTS
# ============================================================================

# Environment variable name for the secret key
SECRET_KEY_ENV_VAR = "SOVEREIGN_SECRET"

# Header name for TradingView signature
SIGNATURE_HEADER = "X-TradingView-Signature"


# ============================================================================
# EXCEPTIONS
# ============================================================================

class HMACVerificationError(Exception):
    """
    Exception raised when HMAC signature verification fails.
    
    Reliability Level: SOVEREIGN TIER
    Input Constraints: Error message with details
    Side Effects: None
    
    Error Codes:
        SEC-001: Missing signature header
        SEC-002: Missing or invalid secret key
        SEC-003: Signature mismatch
        SEC-004: Invalid signature format
    """
    
    def __init__(self, error_code: str, message: str):
        self.error_code = error_code
        self.message = message
        super().__init__(f"[{error_code}] {message}")


# ============================================================================
# HMAC VERIFICATION
# ============================================================================

def get_secret_key() -> str:
    """
    Retrieve the SOVEREIGN_SECRET from environment variables.
    
    Reliability Level: SOVEREIGN TIER
    Input Constraints: None
    Side Effects: Reads from environment
    
    Returns:
        str: The secret key for HMAC verification
        
    Raises:
        HMACVerificationError: If secret key is not configured (SEC-002)
    """
    secret_key = os.getenv(SECRET_KEY_ENV_VAR)
    
    if not secret_key:
        raise HMACVerificationError(
            "SEC-002",
            f"SOVEREIGN_SECRET environment variable is not set. "
            f"Webhook verification cannot proceed without secret key."
        )
    
    if len(secret_key) < 32:
        raise HMACVerificationError(
            "SEC-002",
            f"SOVEREIGN_SECRET is too short ({len(secret_key)} chars). "
            f"Minimum 32 characters required for Sovereign Tier security."
        )
    
    return secret_key


def compute_hmac_signature(payload: bytes, secret_key: str) -> str:
    """
    Compute HMAC-SHA256 signature for a payload.
    
    Reliability Level: SOVEREIGN TIER
    Input Constraints:
        - payload: Raw request body as bytes
        - secret_key: SOVEREIGN_SECRET string
    Side Effects: None
    
    Returns:
        str: Hexadecimal HMAC-SHA256 signature
    """
    signature = hmac.new(
        key=secret_key.encode("utf-8"),
        msg=payload,
        digestmod=hashlib.sha256
    )
    return signature.hexdigest()


def verify_hmac_signature(
    payload: bytes,
    provided_signature: Optional[str],
    secret_key: Optional[str] = None
) -> bool:
    """
    Verify HMAC-SHA256 signature of a webhook payload.
    
    Reliability Level: SOVEREIGN TIER (Mission-Critical)
    Input Constraints:
        - payload: Raw request body as bytes (must be exact bytes received)
        - provided_signature: Value from X-TradingView-Signature header
        - secret_key: Optional override for SOVEREIGN_SECRET
    Side Effects: None
    
    Returns:
        bool: True if signature is valid
        
    Raises:
        HMACVerificationError: If verification fails with specific error code
        
    Error Codes:
        SEC-001: Missing signature header
        SEC-002: Missing or invalid secret key
        SEC-003: Signature mismatch
        SEC-004: Invalid signature format
        
    SOVEREIGN MANDATE:
        - Timing-safe comparison to prevent timing attacks
        - No silent failures - explicit exceptions
        - All failures logged with error codes
    """
    # Validate signature header is present
    if not provided_signature:
        raise HMACVerificationError(
            "SEC-001",
            "Missing X-TradingView-Signature header. "
            "All webhooks must include HMAC-SHA256 signature."
        )
    
    # Clean up signature (remove any prefix like "sha256=")
    clean_signature = provided_signature.strip()
    if clean_signature.startswith("sha256="):
        clean_signature = clean_signature[7:]
    
    # Validate signature format (should be 64 hex characters)
    if len(clean_signature) != 64:
        raise HMACVerificationError(
            "SEC-004",
            f"Invalid signature format. Expected 64 hex characters, "
            f"received {len(clean_signature)}."
        )
    
    try:
        # Validate it's valid hex
        int(clean_signature, 16)
    except ValueError:
        raise HMACVerificationError(
            "SEC-004",
            "Invalid signature format. Signature must be hexadecimal."
        )
    
    # Get secret key
    if secret_key is None:
        secret_key = get_secret_key()
    
    # Compute expected signature
    expected_signature = compute_hmac_signature(payload, secret_key)
    
    # Timing-safe comparison (prevents timing attacks)
    if not hmac.compare_digest(expected_signature.lower(), clean_signature.lower()):
        raise HMACVerificationError(
            "SEC-003",
            "Signature mismatch. Webhook payload may have been tampered with. "
            "L6 Lockdown consideration: Multiple failures may indicate attack."
        )
    
    return True


def generate_test_signature(payload: bytes, secret_key: Optional[str] = None) -> str:
    """
    Generate a valid HMAC-SHA256 signature for testing purposes.
    
    Reliability Level: DEVELOPMENT ONLY
    Input Constraints:
        - payload: Raw request body as bytes
        - secret_key: Optional override for SOVEREIGN_SECRET
    Side Effects: None
    
    Returns:
        str: Valid HMAC-SHA256 signature for the payload
        
    WARNING: This function is for testing only. Do not use in production
    to generate signatures for external systems.
    """
    if secret_key is None:
        secret_key = get_secret_key()
    
    return compute_hmac_signature(payload, secret_key)


# ============================================================================
# END OF SECURITY MODULE
# ============================================================================

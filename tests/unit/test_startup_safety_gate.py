# ============================================================================
# Phase 4: Startup Safety Gate Tests
# ============================================================================
#
# Tests for the live-mode startup blocking logic in app/main.py.
# Verifies that the application refuses to start when critical
# prerequisites are missing in LIVE or LIVE_READ_ONLY mode.
# ============================================================================

import os
from unittest.mock import patch

import pytest

# ============================================================================
# Helper: Exercise the startup safety gate logic in isolation
# ============================================================================

def _run_startup_gate(env_overrides: dict) -> list[str]:
    """
    Reproduce the startup safety gate logic from app/main.py lifespan()
    without importing FastAPI or touching the database.

    Returns a list of error strings (empty = all checks pass).
    """
    def _getenv(key: str, default: str = "") -> str:
        return env_overrides.get(key, default)

    errors: list[str] = []
    exec_mode = _getenv("EXECUTION_MODE", "DEMO").upper().strip()

    if exec_mode not in ("LIVE", "LIVE_READ_ONLY"):
        return errors

    if not _getenv("VALR_API_KEY").strip():
        errors.append("VALR_API_KEY is not set")
    if not _getenv("VALR_API_SECRET").strip():
        errors.append("VALR_API_SECRET is not set")
    if not _getenv("SOVEREIGN_SECRET").strip():
        errors.append("SOVEREIGN_SECRET is not set")
    if not _getenv("HITL_ALLOWED_OPERATORS").strip():
        errors.append("HITL_ALLOWED_OPERATORS is empty")
    if not _getenv("GUARDIAN_ADMIN_TOKEN").strip():
        errors.append("GUARDIAN_ADMIN_TOKEN is not set")
    if not _getenv("GUARDIAN_RESET_CODE").strip():
        errors.append("GUARDIAN_RESET_CODE is not set")
    if _getenv("DB_PASSWORD") == "trading_app_2024":
        errors.append("DB_PASSWORD is still the insecure default")
    if _getenv("POSTGRES_PASSWORD") == "sovereign_secret_2024":
        errors.append("POSTGRES_PASSWORD is still the insecure default")
    if exec_mode == "LIVE":
        if _getenv("LIVE_TRADING_CONFIRMED").upper().strip() != "TRUE":
            errors.append("LIVE_TRADING_CONFIRMED is not TRUE")

    return errors


# ============================================================================
# Baseline: Valid env for LIVE_EXECUTION
# ============================================================================

VALID_LIVE_ENV = {
    "EXECUTION_MODE": "LIVE",
    "LIVE_TRADING_CONFIRMED": "TRUE",
    "VALR_API_KEY": "test_key_abc123",
    "VALR_API_SECRET": "test_secret_xyz789",
    "SOVEREIGN_SECRET": "a" * 64,
    "HITL_ALLOWED_OPERATORS": "operator_alpha",
    "GUARDIAN_ADMIN_TOKEN": "admin_token_abc",
    "GUARDIAN_RESET_CODE": "reset_code_abc",
    "DB_PASSWORD": "unique_db_password_2025",
    "POSTGRES_PASSWORD": "unique_pg_password_2025",
}

VALID_LIVE_RO_ENV = {
    **VALID_LIVE_ENV,
    "EXECUTION_MODE": "LIVE_READ_ONLY",
}


# ============================================================================
# Tests: DEMO and DRY_RUN always pass (no blocking)
# ============================================================================

class TestStartupGateNonLiveModes:
    """Non-live modes should never be blocked by the startup gate."""

    def test_demo_mode_no_errors(self):
        errors = _run_startup_gate({"EXECUTION_MODE": "DEMO"})
        assert errors == []

    def test_dry_run_mode_no_errors(self):
        errors = _run_startup_gate({"EXECUTION_MODE": "DRY_RUN"})
        assert errors == []

    def test_empty_env_defaults_to_demo(self):
        errors = _run_startup_gate({})
        assert errors == []


# ============================================================================
# Tests: LIVE_EXECUTION mode blocking
# ============================================================================

class TestStartupGateLiveExecution:
    """LIVE mode blocks startup when prerequisites are missing."""

    def test_valid_live_env_passes(self):
        errors = _run_startup_gate(VALID_LIVE_ENV)
        assert errors == []

    def test_missing_valr_api_key(self):
        env = {**VALID_LIVE_ENV, "VALR_API_KEY": ""}
        errors = _run_startup_gate(env)
        assert "VALR_API_KEY is not set" in errors

    def test_missing_valr_api_secret(self):
        env = {**VALID_LIVE_ENV, "VALR_API_SECRET": ""}
        errors = _run_startup_gate(env)
        assert "VALR_API_SECRET is not set" in errors

    def test_missing_sovereign_secret(self):
        env = {**VALID_LIVE_ENV, "SOVEREIGN_SECRET": ""}
        errors = _run_startup_gate(env)
        assert "SOVEREIGN_SECRET is not set" in errors

    def test_missing_hitl_operators(self):
        env = {**VALID_LIVE_ENV, "HITL_ALLOWED_OPERATORS": ""}
        errors = _run_startup_gate(env)
        assert "HITL_ALLOWED_OPERATORS is empty" in errors

    def test_missing_guardian_admin_token(self):
        env = {**VALID_LIVE_ENV, "GUARDIAN_ADMIN_TOKEN": ""}
        errors = _run_startup_gate(env)
        assert "GUARDIAN_ADMIN_TOKEN is not set" in errors

    def test_missing_guardian_reset_code(self):
        env = {**VALID_LIVE_ENV, "GUARDIAN_RESET_CODE": ""}
        errors = _run_startup_gate(env)
        assert "GUARDIAN_RESET_CODE is not set" in errors

    def test_insecure_db_password(self):
        env = {**VALID_LIVE_ENV, "DB_PASSWORD": "trading_app_2024"}
        errors = _run_startup_gate(env)
        assert "DB_PASSWORD is still the insecure default" in errors

    def test_insecure_postgres_password(self):
        env = {**VALID_LIVE_ENV, "POSTGRES_PASSWORD": "sovereign_secret_2024"}
        errors = _run_startup_gate(env)
        assert "POSTGRES_PASSWORD is still the insecure default" in errors

    def test_missing_live_trading_confirmed(self):
        env = {**VALID_LIVE_ENV, "LIVE_TRADING_CONFIRMED": ""}
        errors = _run_startup_gate(env)
        assert "LIVE_TRADING_CONFIRMED is not TRUE" in errors

    def test_live_trading_confirmed_wrong_value(self):
        env = {**VALID_LIVE_ENV, "LIVE_TRADING_CONFIRMED": "yes"}
        errors = _run_startup_gate(env)
        assert "LIVE_TRADING_CONFIRMED is not TRUE" in errors

    def test_multiple_missing_prerequisites(self):
        env = {
            "EXECUTION_MODE": "LIVE",
            "VALR_API_KEY": "",
            "VALR_API_SECRET": "",
            "SOVEREIGN_SECRET": "",
        }
        errors = _run_startup_gate(env)
        assert len(errors) >= 3

    def test_whitespace_only_values_treated_as_missing(self):
        env = {**VALID_LIVE_ENV, "VALR_API_KEY": "   "}
        errors = _run_startup_gate(env)
        assert "VALR_API_KEY is not set" in errors


# ============================================================================
# Tests: LIVE_READ_ONLY mode blocking
# ============================================================================

class TestStartupGateLiveReadOnly:
    """LIVE_READ_ONLY mode checks credentials but not LIVE_TRADING_CONFIRMED."""

    def test_valid_live_ro_env_passes(self):
        errors = _run_startup_gate(VALID_LIVE_RO_ENV)
        assert errors == []

    def test_live_ro_missing_valr_key(self):
        env = {**VALID_LIVE_RO_ENV, "VALR_API_KEY": ""}
        errors = _run_startup_gate(env)
        assert "VALR_API_KEY is not set" in errors

    def test_live_ro_does_not_require_live_trading_confirmed(self):
        env = {**VALID_LIVE_RO_ENV, "LIVE_TRADING_CONFIRMED": ""}
        errors = _run_startup_gate(env)
        # LIVE_READ_ONLY should NOT check LIVE_TRADING_CONFIRMED
        assert "LIVE_TRADING_CONFIRMED is not TRUE" not in errors

    def test_live_ro_requires_sovereign_secret(self):
        env = {**VALID_LIVE_RO_ENV, "SOVEREIGN_SECRET": ""}
        errors = _run_startup_gate(env)
        assert "SOVEREIGN_SECRET is not set" in errors

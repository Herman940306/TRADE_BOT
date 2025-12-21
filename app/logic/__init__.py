"""
============================================================================
Project Autonomous Alpha v1.3.2
Logic Layer - Risk Management and Position Sizing
============================================================================

SOVEREIGN TIER INFRASTRUCTURE
Assurance Level: 100% Confidence (Mission-Critical)

This module contains the core business logic for:
- Risk calculation (1% fixed risk per trade)
- Position sizing based on signal price
- Safety guardrails (RISK-001, RISK-002)

============================================================================
"""

from app.logic.risk_manager import (
    RiskProfile,
    calculate_position_size,
    fetch_account_equity,
)

__all__ = [
    "RiskProfile",
    "calculate_position_size",
    "fetch_account_equity",
]

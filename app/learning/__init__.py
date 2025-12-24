"""
Reward-Governed Intelligence (RGI) - Learning Module

This module contains the machine learning components for the RGI system:
- RewardGovernor: LightGBM model wrapper for trust probability prediction
- GoldenSetValidator: Weekly validation against known outcomes
- RGI Initialization: Startup verification and system status

Reliability Level: L6 Critical
"""

from app.learning.reward_governor import (
    RewardGovernor,
    NEUTRAL_TRUST,
    PREDICTION_TIMEOUT_MS,
    get_reward_governor,
    reset_reward_governor,
)

from app.learning.golden_set import (
    GoldenSetValidator,
    GoldenSetResult,
    GoldenTrade,
    GOLDEN_SET,
    GOLDEN_SET_SIZE,
    ACCURACY_THRESHOLD,
    create_golden_set_validator,
    validate_reward_governor,
)

from app.learning.rgi_init import (
    RGIInitResult,
    initialize_rgi,
    get_rgi_status,
    shutdown_rgi,
    RGI_SYSTEM_ONLINE,
    RGI_INIT_FAIL,
)

__all__ = [
    # Reward Governor
    "RewardGovernor",
    "NEUTRAL_TRUST",
    "PREDICTION_TIMEOUT_MS",
    "get_reward_governor",
    "reset_reward_governor",
    # Golden Set
    "GoldenSetValidator",
    "GoldenSetResult",
    "GoldenTrade",
    "GOLDEN_SET",
    "GOLDEN_SET_SIZE",
    "ACCURACY_THRESHOLD",
    "create_golden_set_validator",
    "validate_reward_governor",
    # RGI Initialization
    "RGIInitResult",
    "initialize_rgi",
    "get_rgi_status",
    "shutdown_rgi",
    "RGI_SYSTEM_ONLINE",
    "RGI_INIT_FAIL",
]

"""
Reward-Governed Intelligence (RGI) - Jobs Module

This module contains offline jobs for the RGI system:
- train_reward_governor: Train the Reward Governor model from historical data
- simulate_strategy: Deterministic strategy backtester with Decimal-only math
- pipeline_run: End-to-end strategy ingestion pipeline orchestrator

Reliability Level: Offline Job (Cold Path)
"""

from jobs.simulate_strategy import (
    StrategySimulator,
    SimulationResult,
    SimulatedTrade,
    SimulationError,
    TradeOutcome,
    create_simulator,
)

from jobs.pipeline_run import (
    StrategyPipeline,
    PipelineResult,
    PipelineError,
    PipelineStep,
    PipelineStatus,
    create_pipeline,
)

__all__ = [
    # Simulator
    "StrategySimulator",
    "SimulationResult",
    "SimulatedTrade",
    "SimulationError",
    "TradeOutcome",
    "create_simulator",
    # Pipeline
    "StrategyPipeline",
    "PipelineResult",
    "PipelineError",
    "PipelineStep",
    "PipelineStatus",
    "create_pipeline",
]

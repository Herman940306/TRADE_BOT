"""
app/core/runtime.py
Neutral runtime registry for app-scoped service singletons and dependency getters.
"""

from typing import Any, Optional

from services.demo_broker import DemoBroker
from services.guardian_integration import GuardianIntegration
from services.hitl_expiry_worker import ExpiryWorker
from services.hitl_gateway import HITLGateway
from services.strategy_manager import StrategyManager
from services.trade_lifecycle import TradeLifecycleManager

# Global singletons (populated by app.main at startup)
_trade_lifecycle_manager: Optional[TradeLifecycleManager] = None
_strategy_manager: Optional[StrategyManager] = None
_hitl_gateway: Optional[HITLGateway] = None
_expiry_worker: Optional[ExpiryWorker] = None
_guardian_integration: Optional[GuardianIntegration] = None
_demo_broker: Optional[DemoBroker] = None


def set_trade_lifecycle_manager(obj: TradeLifecycleManager):
    global _trade_lifecycle_manager
    _trade_lifecycle_manager = obj


def get_trade_lifecycle_manager() -> Optional[TradeLifecycleManager]:
    return _trade_lifecycle_manager


def set_strategy_manager(obj: StrategyManager):
    global _strategy_manager
    _strategy_manager = obj


def get_strategy_manager() -> Optional[StrategyManager]:
    return _strategy_manager


def set_hitl_gateway(obj: HITLGateway):
    global _hitl_gateway
    _hitl_gateway = obj


def get_hitl_gateway() -> Optional[HITLGateway]:
    return _hitl_gateway


def set_expiry_worker(obj: ExpiryWorker):
    global _expiry_worker
    _expiry_worker = obj


def get_expiry_worker() -> Optional[ExpiryWorker]:
    return _expiry_worker


def set_guardian_integration(obj: GuardianIntegration):
    global _guardian_integration
    _guardian_integration = obj


def get_guardian_integration() -> Optional[GuardianIntegration]:
    return _guardian_integration


def set_demo_broker(obj: DemoBroker):
    global _demo_broker
    _demo_broker = obj


def get_demo_broker() -> Optional[DemoBroker]:
    return _demo_broker


# ============================================================================
# Intelligence Services (Phase 7: ML/Strategy Merge)
# ============================================================================

_learning_worker: Optional[Any] = None


def set_learning_worker(obj: Any) -> None:
    global _learning_worker
    _learning_worker = obj


def get_learning_worker() -> Optional[Any]:
    return _learning_worker

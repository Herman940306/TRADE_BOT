"""
============================================================================
Data Ingestion Adapters Package
============================================================================

Reliability Level: L6 Critical
Decimal Integrity: All adapters output Decimal-based data

ADAPTER HIERARCHY:
    1. BinanceAdapter - Crypto WebSocket (highest priority)
    2. OandaAdapter - Forex REST API
    3. TwelveDataAdapter - Commodity polling

All adapters implement the BaseAdapter interface for consistency.
============================================================================
"""

from data_ingestion.adapters.base_adapter import (
    BaseAdapter,
    AdapterStatus,
    AdapterErrorCode,
)
from data_ingestion.adapters.binance_adapter import BinanceAdapter
from data_ingestion.adapters.oanda_adapter import OandaAdapter
from data_ingestion.adapters.twelve_data_adapter import TwelveDataAdapter

__all__ = [
    "BaseAdapter",
    "AdapterStatus",
    "AdapterErrorCode",
    "BinanceAdapter",
    "OandaAdapter",
    "TwelveDataAdapter",
]

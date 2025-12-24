# ============================================================================
# Project Autonomous Alpha v1.7.0
# Exchange Integration Module - VALR Connectivity
# ============================================================================
#
# Reliability Level: SOVEREIGN TIER (Mission-Critical)
# Purpose: VALR cryptocurrency exchange integration with DRY_RUN support
#
# Components:
#   - DecimalGateway: Ensures all financial data uses decimal.Decimal
#   - TokenBucket: Rate limiting for VALR API (600 req/min)
#   - VALRSigner: HMAC-SHA512 request signing
#   - VALRClient: Main API client for market data and orders
#   - OrderManager: DRY_RUN/LIVE order execution
#   - ReconciliationEngine: 3-way sync (DB ↔ State ↔ Exchange)
#
# SOVEREIGN MANDATE:
#   - EXECUTION_MODE=DRY_RUN by default
#   - LIMIT orders only (MARKET disabled)
#   - All numeric values converted via DecimalGateway
#   - L6 Lockdown on >1% balance mismatch
#
# ============================================================================

from app.exchange.decimal_gateway import DecimalGateway
from app.exchange.rate_limiter import TokenBucket, PollingMode, ExponentialBackoff
from app.exchange.hmac_signer import VALRSigner, MissingCredentialsError
from app.exchange.valr_client import (
    VALRClient,
    TickerData,
    BalanceData,
    VALRClientError,
    RateLimitError,
    APIError
)
from app.exchange.market_data import (
    MarketDataClient,
    MarketSnapshot,
    MarketStatus
)
from app.exchange.order_manager import (
    OrderManager,
    OrderResult,
    ExecutionMode,
    OrderType,
    OrderSide,
    OrderStatus,
    OrderManagerError,
    MarketOrderRejectedError,
    OrderValueExceededError,
    LiveModeNotConfirmedError
)
from app.exchange.reconciliation import (
    ReconciliationEngine,
    ReconciliationResult,
    ReconciliationStatus
)
from app.exchange.rlhf_recorder import (
    RLHFRecorder,
    RLHFRecord,
    TradeOutcome
)

__all__ = [
    # Decimal Gateway
    'DecimalGateway',
    # Rate Limiter
    'TokenBucket',
    'PollingMode',
    'ExponentialBackoff',
    # HMAC Signer
    'VALRSigner',
    'MissingCredentialsError',
    # VALR Client
    'VALRClient',
    'TickerData',
    'BalanceData',
    'VALRClientError',
    'RateLimitError',
    'APIError',
    # Market Data
    'MarketDataClient',
    'MarketSnapshot',
    'MarketStatus',
    # Order Manager
    'OrderManager',
    'OrderResult',
    'ExecutionMode',
    'OrderType',
    'OrderSide',
    'OrderStatus',
    'OrderManagerError',
    'MarketOrderRejectedError',
    'OrderValueExceededError',
    'LiveModeNotConfirmedError',
    # Reconciliation
    'ReconciliationEngine',
    'ReconciliationResult',
    'ReconciliationStatus',
    # RLHF Recorder
    'RLHFRecorder',
    'RLHFRecord',
    'TradeOutcome',
]

# Version tracking
__version__ = '1.7.0'
__sprint__ = 9

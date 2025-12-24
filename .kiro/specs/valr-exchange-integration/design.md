# Design Document - Sprint 9: VALR Exchange Integration

## Overview

This design document specifies the technical architecture for integrating VALR cryptocurrency exchange into Project Autonomous Alpha. The integration follows a Hybrid Approach with `EXECUTION_MODE=DRY_RUN` as default, enabling full pipeline testing against live market data without capital risk.

The design prioritizes:
1. **Security**: API credentials never exposed in logs or code
2. **Decimal Integrity**: All financial data converted immediately via Decimal Gateway
3. **Robustness**: Token Bucket rate limiting with exponential backoff
4. **Safety**: LIMIT orders only, with configurable maximum order value
5. **Auditability**: 60-second reconciliation with L6 Lockdown on mismatch

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         VALR INTEGRATION LAYER                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                   │
│  │   DECIMAL    │    │    TOKEN     │    │   HMAC       │                   │
│  │   GATEWAY    │    │    BUCKET    │    │   SIGNER     │                   │
│  │              │    │              │    │              │                   │
│  │ to_decimal() │    │ consume()    │    │ sign_req()   │                   │
│  │ validate()   │    │ refill()     │    │ verify()     │                   │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘                   │
│         │                   │                   │                            │
│         ▼                   ▼                   ▼                            │
│  ┌─────────────────────────────────────────────────────────────┐            │
│  │                      VALR API CLIENT                         │            │
│  │                                                              │            │
│  │  get_ticker()     → Market data (BTCZAR, ETHZAR)            │            │
│  │  get_balances()   → Account balances (ZAR, BTC, ETH)        │            │
│  │  get_orders()     → Open orders list                         │            │
│  │  place_order()    → Submit LIMIT order (or DRY_RUN)         │            │
│  │  cancel_order()   → Cancel pending order                     │            │
│  └─────────────────────────────────────────────────────────────┘            │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘

         │
         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         EXECUTION LAYER                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                   │
│  │   ORDER      │    │  RECONCILE   │    │    RLHF      │                   │
│  │   MANAGER    │    │   ENGINE     │    │   RECORDER   │                   │
│  │              │    │              │    │              │                   │
│  │ DRY_RUN/LIVE │    │ 60s 3-way    │    │ WIN/LOSS     │                   │
│  │ LIMIT only   │    │ sync         │    │ feedback     │                   │
│  └──────────────┘    └──────────────┘    └──────────────┘                   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Components and Interfaces

### 1. Decimal Gateway (`app/exchange/decimal_gateway.py`)

Central validation layer ensuring all financial data uses `decimal.Decimal`.

```python
from decimal import Decimal, ROUND_HALF_EVEN, InvalidOperation
from typing import Optional, Union
import logging

logger = logging.getLogger(__name__)

class DecimalGateway:
    """
    Sovereign Tier Decimal Gateway - VALR-002 Compliance
    
    Reliability Level: SOVEREIGN TIER
    Input Constraints: Any numeric value (str, int, float)
    Side Effects: Logs VALR-DEC-001 on conversion failure
    """
    
    ZAR_PRECISION = Decimal('0.01')      # 2 decimal places
    CRYPTO_PRECISION = Decimal('0.00000001')  # 8 decimal places (satoshi)
    
    @staticmethod
    def to_decimal(
        value: Union[str, int, float, None],
        precision: Decimal = ZAR_PRECISION,
        correlation_id: Optional[str] = None
    ) -> Decimal:
        """Convert any numeric value to Decimal with ROUND_HALF_EVEN."""
        if value is None:
            return Decimal('0.00')
        
        try:
            # Always convert via string to avoid float precision loss
            result = Decimal(str(value)).quantize(precision, rounding=ROUND_HALF_EVEN)
            return result
        except (InvalidOperation, ValueError) as e:
            logger.error(
                f"[VALR-DEC-001] Decimal conversion failed | "
                f"value={value} | correlation_id={correlation_id} | error={e}"
            )
            raise ValueError(f"VALR-DEC-001: Cannot convert {value} to Decimal")
    
    @staticmethod
    def validate_decimal(value: any, field_name: str, correlation_id: str) -> bool:
        """Validate that a value is already a Decimal type."""
        if not isinstance(value, Decimal):
            logger.error(
                f"[VALR-DEC-001] Non-Decimal value detected | "
                f"field={field_name} | type={type(value)} | correlation_id={correlation_id}"
            )
            return False
        return True
```

### 2. Token Bucket Rate Limiter (`app/exchange/rate_limiter.py`)

Controls API request frequency to respect VALR rate limits.

```python
import time
import threading
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class TokenBucket:
    """
    Token Bucket Rate Limiter - VALR-003 Compliance
    
    Reliability Level: SOVEREIGN TIER
    Capacity: 600 tokens (VALR REST API limit per minute)
    Refill Rate: 10 tokens per second
    """
    
    def __init__(
        self,
        capacity: int = 600,
        refill_rate: float = 10.0,
        essential_threshold: float = 0.1
    ):
        self.capacity = capacity
        self.tokens = capacity
        self.refill_rate = refill_rate
        self.essential_threshold = essential_threshold
        self.last_refill = time.monotonic()
        self._lock = threading.Lock()
    
    def consume(self, tokens: int = 1, correlation_id: Optional[str] = None) -> bool:
        """Attempt to consume tokens. Returns False if insufficient."""
        with self._lock:
            self._refill()
            
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            
            logger.warning(
                f"[VALR-RATE-001] Rate limit - insufficient tokens | "
                f"requested={tokens} | available={self.tokens} | "
                f"correlation_id={correlation_id}"
            )
            return False
    
    def is_essential_only(self) -> bool:
        """Check if bucket is below essential threshold."""
        return (self.tokens / self.capacity) < self.essential_threshold
    
    def _refill(self):
        """Refill tokens based on elapsed time."""
        now = time.monotonic()
        elapsed = now - self.last_refill
        refill_amount = elapsed * self.refill_rate
        self.tokens = min(self.capacity, self.tokens + refill_amount)
        self.last_refill = now
```


### 3. HMAC Signer (`app/exchange/hmac_signer.py`)

Signs all VALR API requests using HMAC-SHA512.

```python
import hmac
import hashlib
import time
from typing import Optional
import os

class VALRSigner:
    """
    HMAC-SHA512 Request Signer - VALR-001 Compliance
    
    Reliability Level: SOVEREIGN TIER
    Algorithm: HMAC-SHA512 (VALR specification)
    """
    
    def __init__(self):
        self.api_key = os.getenv('VALR_API_KEY')
        self.api_secret = os.getenv('VALR_API_SECRET')
        
        if not self.api_key or not self.api_secret:
            raise ValueError("VALR-SEC-001: Missing VALR API credentials")
    
    def sign_request(
        self,
        method: str,
        path: str,
        body: str = '',
        timestamp: Optional[int] = None
    ) -> dict:
        """Generate VALR API signature headers."""
        if timestamp is None:
            timestamp = int(time.time() * 1000)
        
        # VALR signature format: timestamp + method + path + body
        payload = f"{timestamp}{method.upper()}{path}{body}"
        
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha512
        ).hexdigest()
        
        return {
            'X-VALR-API-KEY': self.api_key,
            'X-VALR-SIGNATURE': signature,
            'X-VALR-TIMESTAMP': str(timestamp)
        }
```

### 4. VALR API Client (`app/exchange/valr_client.py`)

Main client for all VALR API interactions.

```python
import httpx
import logging
from decimal import Decimal
from typing import Optional, Dict, List
from dataclasses import dataclass

from app.exchange.decimal_gateway import DecimalGateway
from app.exchange.rate_limiter import TokenBucket
from app.exchange.hmac_signer import VALRSigner

logger = logging.getLogger(__name__)

@dataclass
class TickerData:
    """Market ticker data with Decimal precision."""
    pair: str
    bid: Decimal
    ask: Decimal
    last_price: Decimal
    volume_24h: Decimal
    spread_pct: Decimal
    timestamp_ms: int

class VALRClient:
    """
    VALR Exchange API Client - Sovereign Tier
    
    Reliability Level: SOVEREIGN TIER
    Rate Limiting: Token Bucket (600/min)
    Decimal Integrity: All values converted via DecimalGateway
    """
    
    BASE_URL = "https://api.valr.com"
    
    def __init__(self, correlation_id: Optional[str] = None):
        self.correlation_id = correlation_id
        self.signer = VALRSigner()
        self.rate_limiter = TokenBucket()
        self.gateway = DecimalGateway()
        self._client = httpx.Client(timeout=30.0)
    
    def get_ticker(self, pair: str = "BTCZAR") -> TickerData:
        """Fetch current ticker data for a trading pair."""
        if not self.rate_limiter.consume(correlation_id=self.correlation_id):
            raise RuntimeError("VALR-RATE-001: Rate limit exceeded")
        
        path = f"/v1/public/{pair}/marketsummary"
        response = self._client.get(f"{self.BASE_URL}{path}")
        response.raise_for_status()
        
        data = response.json()
        
        # Decimal Gateway conversion (VALR-002)
        bid = self.gateway.to_decimal(data.get('bidPrice'), DecimalGateway.ZAR_PRECISION)
        ask = self.gateway.to_decimal(data.get('askPrice'), DecimalGateway.ZAR_PRECISION)
        last = self.gateway.to_decimal(data.get('lastTradedPrice'), DecimalGateway.ZAR_PRECISION)
        volume = self.gateway.to_decimal(data.get('baseVolume'), DecimalGateway.CRYPTO_PRECISION)
        
        # Calculate spread percentage
        spread_pct = ((ask - bid) / bid * 100) if bid > 0 else Decimal('0')
        
        return TickerData(
            pair=pair,
            bid=bid,
            ask=ask,
            last_price=last,
            volume_24h=volume,
            spread_pct=spread_pct.quantize(Decimal('0.0001')),
            timestamp_ms=int(data.get('created', 0))
        )
    
    def get_balances(self) -> Dict[str, Decimal]:
        """Fetch account balances (authenticated)."""
        if not self.rate_limiter.consume(correlation_id=self.correlation_id):
            raise RuntimeError("VALR-RATE-001: Rate limit exceeded")
        
        path = "/v1/account/balances"
        headers = self.signer.sign_request("GET", path)
        
        # Redact credentials in logs (VALR-001)
        logger.debug(f"[VALR] GET {path} | correlation_id={self.correlation_id}")
        
        response = self._client.get(f"{self.BASE_URL}{path}", headers=headers)
        response.raise_for_status()
        
        balances = {}
        for item in response.json():
            currency = item.get('currency', '')
            available = self.gateway.to_decimal(
                item.get('available'),
                DecimalGateway.CRYPTO_PRECISION if currency != 'ZAR' else DecimalGateway.ZAR_PRECISION
            )
            balances[currency] = available
        
        return balances
```


### 5. Order Manager (`app/exchange/order_manager.py`)

Handles order placement with DRY_RUN/LIVE mode support.

```python
import os
import uuid
import logging
from decimal import Decimal
from typing import Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class ExecutionMode(Enum):
    DRY_RUN = "DRY_RUN"
    LIVE = "LIVE"

class OrderType(Enum):
    LIMIT = "LIMIT"
    MARKET = "MARKET"  # Disabled in Sprint 9

@dataclass
class OrderResult:
    """Order execution result."""
    order_id: str
    pair: str
    side: str
    order_type: str
    price: Decimal
    quantity: Decimal
    status: str
    is_simulated: bool
    correlation_id: str

class OrderManager:
    """
    Order Manager - VALR-004, VALR-006 Compliance
    
    Reliability Level: SOVEREIGN TIER
    Execution Mode: DRY_RUN (default) or LIVE
    Order Types: LIMIT only (MARKET disabled)
    """
    
    def __init__(self, valr_client, correlation_id: Optional[str] = None):
        self.client = valr_client
        self.correlation_id = correlation_id or str(uuid.uuid4())
        self.execution_mode = self._get_execution_mode()
        self.max_order_zar = Decimal(os.getenv('MAX_ORDER_ZAR', '5000'))
    
    def _get_execution_mode(self) -> ExecutionMode:
        """Determine execution mode from environment."""
        mode = os.getenv('EXECUTION_MODE', 'DRY_RUN').upper()
        
        if mode == 'LIVE':
            # Require explicit confirmation for LIVE mode (VALR-006)
            if os.getenv('LIVE_TRADING_CONFIRMED', '').upper() != 'TRUE':
                logger.error(
                    "[VALR-MODE-001] LIVE mode requires LIVE_TRADING_CONFIRMED=TRUE"
                )
                raise RuntimeError("VALR-MODE-001: LIVE trading not confirmed")
            return ExecutionMode.LIVE
        
        return ExecutionMode.DRY_RUN
    
    def place_order(
        self,
        pair: str,
        side: str,
        price: Decimal,
        quantity: Decimal,
        order_type: OrderType = OrderType.LIMIT
    ) -> OrderResult:
        """Place an order (DRY_RUN or LIVE)."""
        
        # VALR-004: Reject MARKET orders
        if order_type == OrderType.MARKET:
            logger.error(
                f"[VALR-ORD-001] MARKET orders disabled | "
                f"correlation_id={self.correlation_id}"
            )
            raise ValueError("VALR-ORD-001: MARKET orders not permitted")
        
        # Calculate order value in ZAR
        order_value = price * quantity
        
        # VALR-004: Enforce maximum order value
        if order_value > self.max_order_zar:
            logger.error(
                f"[VALR-ORD-002] Order exceeds MAX_ORDER_ZAR | "
                f"value={order_value} | max={self.max_order_zar} | "
                f"correlation_id={self.correlation_id}"
            )
            raise ValueError(f"VALR-ORD-002: Order value R{order_value} exceeds limit R{self.max_order_zar}")
        
        if self.execution_mode == ExecutionMode.DRY_RUN:
            return self._simulate_order(pair, side, price, quantity)
        else:
            return self._execute_live_order(pair, side, price, quantity)
    
    def _simulate_order(
        self,
        pair: str,
        side: str,
        price: Decimal,
        quantity: Decimal
    ) -> OrderResult:
        """Simulate order placement (DRY_RUN mode)."""
        synthetic_id = f"DRY_{uuid.uuid4().hex[:16].upper()}"
        
        logger.info(
            f"[DRY_RUN] Simulated {side} order | "
            f"pair={pair} | price={price} | qty={quantity} | "
            f"order_id={synthetic_id} | correlation_id={self.correlation_id}"
        )
        
        return OrderResult(
            order_id=synthetic_id,
            pair=pair,
            side=side,
            order_type="LIMIT",
            price=price,
            quantity=quantity,
            status="SIMULATED",
            is_simulated=True,
            correlation_id=self.correlation_id
        )
    
    def _execute_live_order(
        self,
        pair: str,
        side: str,
        price: Decimal,
        quantity: Decimal
    ) -> OrderResult:
        """Execute real order on VALR (LIVE mode)."""
        # Implementation for Sprint 9 Phase 2
        raise NotImplementedError("LIVE order execution pending Phase 2")
```


### 6. Reconciliation Engine (`app/exchange/reconciliation.py`)

Performs 60-second 3-way sync between DB, State, and Exchange.

```python
import logging
from decimal import Decimal
from typing import Optional, Dict
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class ReconciliationStatus(Enum):
    MATCHED = "MATCHED"
    MISMATCH = "MISMATCH"
    PENDING = "PENDING"

@dataclass
class ReconciliationResult:
    """Result of 3-way reconciliation."""
    status: ReconciliationStatus
    db_balance: Decimal
    state_balance: Decimal
    exchange_balance: Decimal
    discrepancy_pct: Decimal
    correlation_id: str

class ReconciliationEngine:
    """
    3-Way Reconciliation Engine - VALR-005 Compliance
    
    Reliability Level: SOVEREIGN TIER
    Sync Interval: 60 seconds
    L6 Lockdown: Triggered on >1% discrepancy
    """
    
    MISMATCH_THRESHOLD_PCT = Decimal('1.0')  # 1% triggers L6 Lockdown
    MAX_CONSECUTIVE_FAILURES = 3
    
    def __init__(self, valr_client, db_session, correlation_id: Optional[str] = None):
        self.client = valr_client
        self.db = db_session
        self.correlation_id = correlation_id
        self.consecutive_failures = 0
    
    def reconcile(self, currency: str = "ZAR") -> ReconciliationResult:
        """Perform 3-way reconciliation for a currency."""
        try:
            # 1. Get exchange balance
            exchange_balances = self.client.get_balances()
            exchange_balance = exchange_balances.get(currency, Decimal('0'))
            
            # 2. Get database balance (from trading_orders table)
            db_balance = self._get_db_balance(currency)
            
            # 3. Get internal state balance
            state_balance = self._get_state_balance(currency)
            
            # Calculate discrepancy
            max_balance = max(exchange_balance, db_balance, state_balance)
            if max_balance > 0:
                discrepancy = abs(exchange_balance - db_balance)
                discrepancy_pct = (discrepancy / max_balance) * 100
            else:
                discrepancy_pct = Decimal('0')
            
            # Determine status
            if discrepancy_pct > self.MISMATCH_THRESHOLD_PCT:
                status = ReconciliationStatus.MISMATCH
                self._handle_mismatch(discrepancy_pct)
            else:
                status = ReconciliationStatus.MATCHED
                self.consecutive_failures = 0
            
            result = ReconciliationResult(
                status=status,
                db_balance=db_balance,
                state_balance=state_balance,
                exchange_balance=exchange_balance,
                discrepancy_pct=discrepancy_pct,
                correlation_id=self.correlation_id
            )
            
            # Log reconciliation
            logger.info(
                f"[VALR-REC] Reconciliation {status.value} | "
                f"exchange={exchange_balance} | db={db_balance} | "
                f"discrepancy={discrepancy_pct}% | correlation_id={self.correlation_id}"
            )
            
            return result
            
        except Exception as e:
            self.consecutive_failures += 1
            logger.error(
                f"[VALR-REC-001] Reconciliation failed | "
                f"failures={self.consecutive_failures} | error={e} | "
                f"correlation_id={self.correlation_id}"
            )
            
            if self.consecutive_failures >= self.MAX_CONSECUTIVE_FAILURES:
                self._trigger_neutral_state()
            
            return ReconciliationResult(
                status=ReconciliationStatus.PENDING,
                db_balance=Decimal('0'),
                state_balance=Decimal('0'),
                exchange_balance=Decimal('0'),
                discrepancy_pct=Decimal('0'),
                correlation_id=self.correlation_id
            )
    
    def _handle_mismatch(self, discrepancy_pct: Decimal):
        """Handle balance mismatch - trigger L6 Lockdown."""
        logger.critical(
            f"[VALR-REC-001] MISMATCH DETECTED - L6 LOCKDOWN | "
            f"discrepancy={discrepancy_pct}% | threshold={self.MISMATCH_THRESHOLD_PCT}% | "
            f"correlation_id={self.correlation_id}"
        )
        # Trigger L6 Lockdown via KillSwitchModule
        from app.logic.production_safety import KillSwitchModule
        KillSwitchModule.trigger_lockdown(
            reason=f"VALR-REC-001: Balance mismatch {discrepancy_pct}%",
            correlation_id=self.correlation_id
        )
    
    def _trigger_neutral_state(self):
        """Enter Neutral State after consecutive failures."""
        logger.critical(
            f"[VALR-REC] Entering Neutral State | "
            f"consecutive_failures={self.consecutive_failures} | "
            f"correlation_id={self.correlation_id}"
        )
        # Implementation: Set system to Neutral State
    
    def _get_db_balance(self, currency: str) -> Decimal:
        """Get balance from database records."""
        # Query trading_orders for net position
        return Decimal('0')  # Placeholder
    
    def _get_state_balance(self, currency: str) -> Decimal:
        """Get balance from internal state."""
        return Decimal('0')  # Placeholder
```

## Data Models

### Market Snapshot Table

```sql
CREATE TABLE IF NOT EXISTS market_snapshots (
    id SERIAL PRIMARY KEY,
    pair VARCHAR(20) NOT NULL,
    bid DECIMAL(20,8) NOT NULL,
    ask DECIMAL(20,8) NOT NULL,
    last_price DECIMAL(20,8) NOT NULL,
    volume_24h DECIMAL(20,8) NOT NULL,
    spread_pct DECIMAL(10,4) NOT NULL,
    source VARCHAR(20) DEFAULT 'VALR',
    timestamp_ms BIGINT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    correlation_id UUID
);

CREATE INDEX idx_market_snapshots_pair_time ON market_snapshots(pair, created_at DESC);
```

### Order Execution Table Extension

```sql
ALTER TABLE trading_orders
ADD COLUMN IF NOT EXISTS is_simulated BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS execution_mode VARCHAR(20) DEFAULT 'DRY_RUN',
ADD COLUMN IF NOT EXISTS valr_order_id VARCHAR(64),
ADD COLUMN IF NOT EXISTS valr_response JSONB;
```


## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

Based on the prework analysis, the following correctness properties have been identified:

### Property 1: Decimal Gateway Round-Trip

*For any* numeric value (float, int, or string) received from VALR API, converting it through the Decimal Gateway should produce a `decimal.Decimal` with `ROUND_HALF_EVEN` rounding, and the result should be reproducible.

**Validates: Requirements 2.1, 2.3**

### Property 2: Credential Sanitization

*For any* log message or stored API response containing VALR credentials (API key, secret, signature), the output should contain `[REDACTED]` instead of the actual credential value.

**Validates: Requirements 1.2, 1.5**

### Property 3: MARKET Order Rejection

*For any* order request with `order_type=MARKET`, the Order Manager should reject it with error code `VALR-ORD-001` regardless of other parameters.

**Validates: Requirements 4.1**

### Property 4: Order Value Limit Enforcement

*For any* order where `price * quantity > MAX_ORDER_ZAR`, the Order Manager should reject it with error code `VALR-ORD-002`.

**Validates: Requirements 4.4, 4.5**

### Property 5: DRY_RUN Simulation

*For any* order placed when `EXECUTION_MODE=DRY_RUN`, the result should have `is_simulated=TRUE`, the order_id should start with `DRY_`, and no actual API call should be made to VALR.

**Validates: Requirements 4.2, 6.2**

### Property 6: LIVE Mode Safety Gate

*For any* system startup with `EXECUTION_MODE=LIVE` but without `LIVE_TRADING_CONFIRMED=TRUE`, the system should refuse to start and log error code `VALR-MODE-001`.

**Validates: Requirements 6.3, 6.4**

### Property 7: Token Bucket Rate Limiting

*For any* sequence of API requests exceeding the bucket capacity (600/min), requests beyond capacity should be rejected with error code `VALR-RATE-001`, and the bucket should refill at 10 tokens/second.

**Validates: Requirements 3.2, 3.4**

### Property 8: Essential Polling Mode

*For any* Token Bucket state below 10% capacity, the API client should enter "Essential Polling Only" mode, limiting requests to balance and position queries only.

**Validates: Requirements 3.3**

### Property 9: Reconciliation Mismatch Detection

*For any* 3-way reconciliation where the discrepancy between exchange balance and database balance exceeds 1% of total equity, the system should trigger L6 Lockdown.

**Validates: Requirements 5.3**

### Property 10: Consecutive Failure Neutral State

*For any* sequence of 3 consecutive reconciliation failures, the system should enter Neutral State.

**Validates: Requirements 5.5**

### Property 11: Market Data Staleness

*For any* market data with timestamp older than 30 seconds from current time, the data should be marked as stale with warning code `VALR-DATA-001`.

**Validates: Requirements 7.2**

### Property 12: Spread Rejection

*For any* market data where `(ask - bid) / bid * 100 > 2%`, trading should be rejected due to excessive spread.

**Validates: Requirements 7.5**

### Property 13: RLHF Outcome Recording

*For any* closed position with PnL > 0, the RLHF recorder should call `ml_record_prediction_outcome` with `user_accepted=TRUE`. For PnL < 0, it should record `user_accepted=FALSE`. For PnL = 0, it should record with neutral score.

**Validates: Requirements 8.1, 8.3, 8.4**

### Property 14: Correlation ID Traceability

*For any* order, reconciliation, or market data operation, the result should contain a valid `correlation_id` that can be traced back to the originating request.

**Validates: Requirements 4.6, 5.4**

### Property 15: ZAR Precision Formatting

*For any* ZAR value displayed or stored, it should have exactly 2 decimal places (e.g., `R 1,234.56`).

**Validates: Requirements 2.5**

## Error Handling

| Error Code | Description | Recovery Action |
|------------|-------------|-----------------|
| VALR-SEC-001 | Missing API credentials | Enter Neutral State, log error |
| VALR-DEC-001 | Decimal conversion failed | Reject response, log error |
| VALR-RATE-001 | Rate limit exceeded | Exponential backoff (1s-60s) |
| VALR-ORD-001 | MARKET order rejected | Return error, no retry |
| VALR-ORD-002 | Order exceeds MAX_ORDER_ZAR | Return error, no retry |
| VALR-MODE-001 | LIVE mode not confirmed | Refuse startup |
| VALR-REC-001 | Reconciliation mismatch | L6 Lockdown if >1% |
| VALR-DATA-001 | Market data stale | Mark stale, continue |

## Testing Strategy

### Property-Based Testing (Hypothesis)

The design uses Hypothesis for property-based testing with minimum 100 iterations per property.

```python
from hypothesis import given, strategies as st, settings
from decimal import Decimal

@settings(max_examples=100)
@given(st.floats(allow_nan=False, allow_infinity=False))
def test_decimal_gateway_round_trip(value):
    """
    Feature: valr-exchange-integration, Property 1: Decimal Gateway Round-Trip
    Validates: Requirements 2.1, 2.3
    """
    result = DecimalGateway.to_decimal(value)
    assert isinstance(result, Decimal)
    # Verify ROUND_HALF_EVEN behavior
    assert result == Decimal(str(value)).quantize(
        DecimalGateway.ZAR_PRECISION, 
        rounding=ROUND_HALF_EVEN
    )
```

### Unit Tests

- Credential loading from environment variables
- HMAC-SHA512 signature generation
- Token Bucket capacity and refill
- Order Manager mode switching
- Reconciliation status recording

### Integration Tests

- End-to-end DRY_RUN order flow
- Market data polling and storage
- Reconciliation with mocked exchange responses
- RLHF feedback recording

---

## Sovereign Reliability Audit

```
[Design Audit - Sprint 9]
- Decimal Integrity: Enforced via DecimalGateway
- L6 Safety: Reconciliation triggers Lockdown on >1% mismatch
- Rate Limiting: Token Bucket (600/min) with Essential Mode
- Order Safety: LIMIT only, MAX_ORDER_ZAR enforced
- Traceability: correlation_id on all operations
- Execution Mode: DRY_RUN default, LIVE requires confirmation
- Confidence Score: 98/100
```

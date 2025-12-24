# Implementation Plan - Sprint 9: VALR Exchange Integration

## Step 1: Security & Foundation

- [x] 1. Create exchange module directory structure


  - Create `app/exchange/` directory
  - Create `app/exchange/__init__.py` with module exports
  - Create `tests/properties/test_valr_integration.py` test file
  - _Requirements: 1.1, 2.1_

- [-] 2. Implement Decimal Gateway

  - [x] 2.1 Create `app/exchange/decimal_gateway.py` with DecimalGateway class



    - Implement `to_decimal()` with ROUND_HALF_EVEN
    - Implement `validate_decimal()` for type checking
    - Add ZAR_PRECISION (0.01) and CRYPTO_PRECISION (0.00000001) constants
    - _Requirements: 2.1, 2.3, 2.5_
  - [ ]* 2.2 Write property test for Decimal Gateway round-trip
    - **Property 1: Decimal Gateway Round-Trip**
    - **Validates: Requirements 2.1, 2.3**
  - [ ]* 2.3 Write property test for ZAR precision formatting
    - **Property 15: ZAR Precision Formatting**
    - **Validates: Requirements 2.5**

- [-] 3. Implement HMAC Signer


  - [x] 3.1 Create `app/exchange/hmac_signer.py` with VALRSigner class

    - Load credentials from environment variables only
    - Implement HMAC-SHA512 signing per VALR spec
    - Raise VALR-SEC-001 on missing credentials
    - _Requirements: 1.1, 1.4_
  - [ ]* 3.2 Write property test for credential sanitization
    - **Property 2: Credential Sanitization**
    - **Validates: Requirements 1.2, 1.5**

- [-] 4. Implement Token Bucket Rate Limiter

  - [x] 4.1 Create `app/exchange/rate_limiter.py` with TokenBucket class



    - Capacity: 600 tokens (VALR REST API limit)
    - Refill rate: 10 tokens/second
    - Essential threshold: 10%
    - Thread-safe with mutex lock
    - _Requirements: 3.2, 3.3_
  - [ ]* 4.2 Write property test for Token Bucket rate limiting
    - **Property 7: Token Bucket Rate Limiting**
    - **Validates: Requirements 3.2, 3.4**
  - [ ]* 4.3 Write property test for Essential Polling Mode
    - **Property 8: Essential Polling Mode**
    - **Validates: Requirements 3.3**

- [x] 5. Checkpoint - Ensure all tests pass

  - Ensure all tests pass, ask the user if questions arise.

## Step 2: Connectivity (Read-Only Phase)

- [ ] 6. Implement VALR API Client
  - [x] 6.1 Create `app/exchange/valr_client.py` with VALRClient class



    - Integrate DecimalGateway for all numeric conversions
    - Integrate TokenBucket for rate limiting
    - Integrate VALRSigner for authenticated requests
    - Implement exponential backoff for HTTP 429
    - _Requirements: 2.1, 3.1, 3.5_
  - [x] 6.2 Implement `get_ticker()` method

    - Fetch market summary for BTCZAR/ETHZAR
    - Convert all prices via Decimal Gateway
    - Calculate spread percentage
    - Return TickerData dataclass
    - _Requirements: 7.1, 7.5_

  - [ ] 6.3 Implement `get_balances()` method (authenticated)
    - Sign request with HMAC-SHA512
    - Redact credentials in logs
    - Convert balances via Decimal Gateway
    - _Requirements: 1.2, 1.4_

- [ ] 7. Create Market Snapshots Database Migration
  - [x] 7.1 Create `database/migrations/018_market_snapshots.sql`


    - Create market_snapshots table with Decimal columns
    - Add indexes for pair and timestamp queries
    - _Requirements: 7.3_
  - [ ]* 7.2 Write property test for market data staleness
    - **Property 11: Market Data Staleness**
    - **Validates: Requirements 7.2**
  - [ ]* 7.3 Write property test for spread rejection
    - **Property 12: Spread Rejection**
    - **Validates: Requirements 7.5**

- [ ] 8. Implement Market Data Client
  - [x] 8.1 Create `app/exchange/market_data.py` with MarketDataClient class



    - Poll ticker every 5 seconds
    - Detect staleness (>30 seconds)
    - Store snapshots in database
    - Trigger Safe-Idle on 60s unreachable
    - _Requirements: 7.1, 7.2, 7.3, 7.4_

- [x] 9. Checkpoint - Ensure all tests pass

  - Ensure all tests pass, ask the user if questions arise.

## Step 3: Execution & Safety (Order Phase)

- [ ] 10. Implement Order Manager
  - [x] 10.1 Create `app/exchange/order_manager.py` with OrderManager class


    - Read EXECUTION_MODE from environment (default: DRY_RUN)
    - Require LIVE_TRADING_CONFIRMED for LIVE mode
    - Reject MARKET orders with VALR-ORD-001
    - Enforce MAX_ORDER_ZAR limit
    - Attach correlation_id to all orders
    - _Requirements: 4.1, 4.4, 4.6, 6.1, 6.3_

  - [x] 10.2 Implement DRY_RUN simulation logic

    - Generate synthetic order ID (DRY_prefix)
    - Log with [DRY_RUN] prefix
    - Store with is_simulated=TRUE
    - _Requirements: 4.2, 6.2_
  - [ ]* 10.3 Write property test for MARKET order rejection
    - **Property 3: MARKET Order Rejection**
    - **Validates: Requirements 4.1**
  - [ ]* 10.4 Write property test for order value limit
    - **Property 4: Order Value Limit Enforcement**
    - **Validates: Requirements 4.4, 4.5**
  - [ ]* 10.5 Write property test for DRY_RUN simulation
    - **Property 5: DRY_RUN Simulation**
    - **Validates: Requirements 4.2, 6.2**
  - [ ]* 10.6 Write property test for LIVE mode safety gate
    - **Property 6: LIVE Mode Safety Gate**
    - **Validates: Requirements 6.3, 6.4**

- [ ] 11. Extend Trading Orders Table
  - [x] 11.1 Create `database/migrations/019_valr_order_extensions.sql`


    - Add is_simulated, execution_mode, valr_order_id, valr_response columns
    - _Requirements: 6.2_

- [x] 12. Checkpoint - Ensure all tests pass

  - Ensure all tests pass, ask the user if questions arise.

## Step 4: Reconciliation & RLHF

- [ ] 13. Implement Reconciliation Engine
  - [x] 13.1 Create `app/exchange/reconciliation.py` with ReconciliationEngine class


    - Perform 3-way sync (DB ↔ State ↔ Exchange)
    - Detect mismatch >1% and trigger L6 Lockdown
    - Track consecutive failures (3 = Neutral State)
    - Record status in institutional_audit table
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_
  - [ ]* 13.2 Write property test for reconciliation mismatch detection
    - **Property 9: Reconciliation Mismatch Detection**
    - **Validates: Requirements 5.3**
  - [ ]* 13.3 Write property test for consecutive failure handling
    - **Property 10: Consecutive Failure Neutral State**
    - **Validates: Requirements 5.5**

- [ ] 14. Implement RLHF Recorder
  - [x] 14.1 Create `app/exchange/rlhf_recorder.py` with RLHFRecorder class


    - Calculate PnL on position close
    - Classify outcome (WIN/LOSS/BREAKEVEN)
    - Call ml_record_prediction_outcome
    - Update RAG document with outcome
    - _Requirements: 8.1, 8.2, 8.5_
  - [ ]* 14.2 Write property test for RLHF outcome recording
    - **Property 13: RLHF Outcome Recording**
    - **Validates: Requirements 8.1, 8.3, 8.4**

- [ ] 15. Implement Correlation ID Traceability
  - [ ]* 15.1 Write property test for correlation ID traceability
    - **Property 14: Correlation ID Traceability**
    - **Validates: Requirements 4.6, 5.4**

- [x] 16. Checkpoint - Ensure all tests pass

  - Ensure all tests pass, ask the user if questions arise.

## Step 5: Integration & Proof of Concept

- [x] 17. Create DRY_RUN Proof of Concept


  - [ ] 17.1 Create `scripts/valr_dry_run_poc.py`
    - Fetch live BTCZAR ticker data
    - Demonstrate Decimal Gateway conversion
    - Simulate a LIMIT order
    - Run reconciliation check
    - Output formatted ZAR values
    - _Requirements: All_



- [ ] 18. Update Environment Configuration
  - [ ] 18.1 Update `.env.example` with VALR configuration
    - Add VALR_API_KEY, VALR_API_SECRET placeholders
    - Add EXECUTION_MODE=DRY_RUN default


    - Add MAX_ORDER_ZAR=5000 default
    - Add LIVE_TRADING_CONFIRMED documentation
    - _Requirements: 1.1, 6.1_

- [ ] 19. Final Checkpoint - Full Test Suite
  - Ensure all tests pass, ask the user if questions arise.

---

## Sovereign Reliability Audit

```
[Implementation Plan Audit]
- Task Count: 19 top-level tasks
- Property Tests: 15 properties across 11 test tasks
- Checkpoints: 5 validation points
- Incremental: Each step builds on previous
- DRY_RUN First: No live trading until Phase 2
- Confidence Score: 98/100
```

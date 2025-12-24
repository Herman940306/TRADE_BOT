# Implementation Plan

## HITL Approval Gateway - The Crown Jewel

This implementation plan builds the core HITL Gateway following the Prime Directive: **"The bot thinks. You approve. The system never betrays you."**

---

- [x] 1. Database Foundation (Immutable Core)





  - [x] 1.1 Create database migration for hitl_approvals table


    - Add hitl_approvals table with all columns: id, trade_id, instrument, side, risk_pct, confidence, request_price, reasoning_summary, correlation_id, status, requested_at, expires_at, decided_at, decided_by, decision_channel, decision_reason, row_hash
    - Add CHECK constraints for status and side enums
    - Add UNIQUE constraint on trade_id (one approval per trade)
    - Add DECIMAL(18,8) for price fields
    - Create indexes: idx_hitl_pending, idx_hitl_correlation, idx_hitl_trade
    - _Requirements: 2.1, 6.4, 6.5_

  - [x] 1.2 Create database migration for post_trade_snapshots table

    - Add post_trade_snapshots table with: id, approval_id, bid, ask, spread, mid_price, response_latency_ms, price_deviation_pct, correlation_id, created_at
    - Add foreign key to hitl_approvals
    - Create indexes: idx_snapshot_approval, idx_snapshot_correlation
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5_

  - [x] 1.3 Create database migration for audit_log table

    - Add audit_log table with: id, actor_id, action, target_type, target_id, previous_state, new_state, payload, correlation_id, error_code, created_at
    - Create indexes: idx_audit_correlation, idx_audit_target, idx_audit_action
    - _Requirements: 1.6, 3.8_

  - [x] 1.4 Create database migration for deep_link_tokens table

    - Add deep_link_tokens table with: token, trade_id, expires_at, used_at, correlation_id, created_at
    - Create partial index for unused tokens
    - _Requirements: 8.3, 8.5_
  - [x] 1.5 Write property test for database integrity






    - **Property 11: Approval Records Are Immutable (No Hard Deletes)**
    - **Validates: Requirements 6.4**

- [x] 2. Core Data Models and Row Hasher





  - [x] 2.1 Create ApprovalRequest dataclass


    - Define all fields with proper types (UUID, Decimal, datetime, Optional)
    - Use Python 3.8 compatible typing (typing.Optional, typing.List)
    - Implement to_dict() and from_dict() methods for serialization
    - _Requirements: 2.1_

  - [x] 2.2 Create ApprovalDecision dataclass
    - Define decision payload fields: trade_id, decision, operator_id, channel, reason, comment, correlation_id

    - _Requirements: 3.7_
  - [x] 2.3 Implement RowHasher class
    - Implement compute() method using SHA-256 on canonical JSON of record fields
    - Implement verify() method to compare stored vs computed hash
    - Use deterministic field ordering for consistent hashing

    - _Requirements: 2.3, 6.1, 6.2_

  - [x] 2.4 Write property test for row hash integrity




    - **Property 4: Row Hash Round-Trip Integrity**
    - **Validates: Requirements 2.3, 5.2, 5.3, 6.1, 6.2, 6.3**

- [x] 3. Trade Lifecycle State Machine






  - [x] 3.1 Define VALID_TRANSITIONS constant

    - Map each state to list of valid target states
    - PENDING → AWAITING_APPROVAL
    - AWAITING_APPROVAL → ACCEPTED, REJECTED
    - ACCEPTED → FILLED
    - FILLED → CLOSED
    - CLOSED → SETTLED
    - _Requirements: 1.1, 1.2, 1.3, 1.4_

  - [x] 3.2 Implement validate_transition() function

    - Check if transition is in VALID_TRANSITIONS
    - Return (is_valid, error_code) tuple
    - Log SEC-030 for invalid transitions
    - _Requirements: 1.5_

  - [x] 3.3 Implement transition_trade() function

    - Validate transition before applying
    - Update trade state in database
    - Create audit_log entry with previous_state, new_state, correlation_id
    - _Requirements: 1.6_
  - [x] 3.4 Write property test for valid state transitions






    - **Property 1: Valid State Transitions Preserve Lifecycle Integrity**
    - **Validates: Requirements 1.1, 1.2, 1.3, 1.4**
  - [x] 3.5 Write property test for invalid state transitions




    - **Property 2: Invalid State Transitions Are Rejected**
    - **Validates: Requirements 1.5**


- [x] 4. Configuration and Environment




  - [x] 4.1 Create HITLConfig class

    - Read HITL_ENABLED (default: true)
    - Read HITL_TIMEOUT_SECONDS (default: 300)
    - Read HITL_SLIPPAGE_MAX_PERCENT (default: 0.5)
    - Read HITL_ALLOWED_OPERATORS as comma-separated list
    - Validate required config on startup, fail with SEC-040 if missing
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.6_

  - [x] 4.2 Write unit tests for configuration parsing





    - Test default values
    - Test custom values
    - Test missing required config fails with SEC-040
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.6_

- [x] 5. Guardian Integration





  - [x] 5.1 Create GuardianIntegration class


    - Implement is_locked() method to check Guardian status
    - Implement get_status() method for full status including lock reason
    - Implement on_lock_event() callback registration
    - _Requirements: 11.1, 11.2_

  - [x] 5.2 Implement Guardian lock cascade handler

    - When Guardian transitions to LOCKED, reject all pending approvals
    - Set decision_reason to GUARDIAN_LOCK
    - Increment blocked_by_guardian counter
    - Send Discord notification
    - _Requirements: 11.4, 11.5_
  - [x] 5.3 Write property test for Guardian blocking






    - **Property 3: Guardian Lock Blocks All HITL Operations**
    - **Validates: Requirements 2.4, 2.5, 3.3, 11.1, 11.2, 11.3, 11.4, 11.5**

- [x] 6. Slippage Guard






  - [x] 6.1 Implement SlippageGuard class

    - Constructor takes max_slippage_pct from config
    - Implement validate() method: compute abs((current - request) / request) * 100
    - Return (is_valid, deviation_pct) tuple
    - Use Decimal arithmetic with ROUND_HALF_EVEN
    - _Requirements: 3.5, 3.6_

  - [x] 6.2 Write property test for slippage validation





    - **Property 6: Slippage Exceeding Threshold Causes Rejection**
    - **Validates: Requirements 3.5, 3.6**


- [x] 7. Checkpoint - Ensure all foundation tests pass




  - Ensure all tests pass, ask the user if questions arise.


- [x] 8. HITL Gateway Core Service

  - [x] 8.1 Create HITLGateway class skeleton
    - Inject dependencies: config, guardian, slippage_guard, db_session
    - Initialize Prometheus counters: hitl_requests_total, hitl_approvals_total, hitl_rejections_total, hitl_response_latency_seconds
    - _Requirements: 9.1, 9.2, 9.3, 9.4_

  - [x] 8.2 Implement create_approval_request() method
    - Check Guardian status first, reject with SEC-020 if locked
    - Create ApprovalRequest with all fields
    - Set expires_at = now + HITL_TIMEOUT_SECONDS
    - Compute and store row_hash
    - Persist to database
    - Increment hitl_requests_total counter
    - Create audit_log entry
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 9.1_

  - [x] 8.3 Implement process_decision() method
    - Verify operator is in HITL_ALLOWED_OPERATORS, reject with SEC-090 if not
    - Re-check Guardian status, reject with SEC-020 if locked
    - Validate request has not expired
    - Execute slippage guard, reject with SEC-050 if exceeded
    - Update decided_at, decided_by, decision_channel, decision_reason
    - Recompute row_hash
    - Transition trade state (ACCEPTED or REJECTED)
    - Increment appropriate Prometheus counter
    - Observe hitl_response_latency_seconds histogram
    - Create audit_log entry
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 9.2, 9.3, 9.4_

  - [x] 8.4 Implement get_pending_approvals() method

    - Query hitl_approvals WHERE status = 'AWAITING_APPROVAL'
    - Order by expires_at ASC
    - Verify row_hash for each record, log SEC-080 if mismatch
    - Calculate seconds_remaining for each
    - _Requirements: 7.1, 7.2, 6.2_

  - [x] 8.5 Write property test for unauthorized operators





    - **Property 5: Unauthorized Operators Are Rejected**

    - **Validates: Requirements 3.1, 3.2, 7.5, 7.6, 8.4**
  - [x] 8.6 Write property test for Prometheus counters





    - **Property 9: Operations Increment Correct Prometheus Counters**
    - **Validates: Requirements 9.1, 9.2, 9.3, 9.4, 4.6, 11.5**

  - [x] 8.7 Write property test for audit records




    - **Property 10: All Decisions Create Complete Audit Records**
    - **Validates: Requirements 1.6, 3.7, 3.8**


- [x] 9. Post-Trade Snapshot Capture



  - [x] 9.1 Implement capture_post_trade_snapshot() method


    - Fetch current bid, ask from market data service
    - Calculate spread = ask - bid
    - Calculate mid_price = (bid + ask) / 2
    - Record response_latency_ms from API call
    - Calculate price_deviation_pct = abs((mid_price - request_price) / request_price) * 100
    - Persist to post_trade_snapshots with correlation_id
    - Use Decimal with ROUND_HALF_EVEN
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5_
  - [x] 9.2 Write property test for post-trade snapshot





    - **Property 13: Post-Trade Snapshot Captures Complete Market Context**
    - **Validates: Requirements 12.1, 12.2, 12.3, 12.4**
  - [x] 9.3 Write property test for decimal precision





    - **Property 8: Price Fields Maintain DECIMAL(18,8) Precision**
    - **Validates: Requirements 6.5, 12.5**


- [x] 10. Expiry Worker (Background Job)




  - [x] 10.1 Implement ExpiryWorker class


    - Constructor takes interval_seconds (default: 30)
    - Implement run() method with async loop
    - _Requirements: 4.1_
  - [x] 10.2 Implement process_expired() method

    - Query hitl_approvals WHERE status = 'AWAITING_APPROVAL' AND expires_at < now()
    - For each expired request:
      - Transition status to REJECTED
      - Set decision_reason = 'HITL_TIMEOUT'
      - Set decision_channel = 'SYSTEM'
      - Set decided_at = now()
      - Recompute row_hash
      - Increment hitl_rejections_timeout_total counter
      - Create audit_log entry
    - Return count of processed requests
    - _Requirements: 4.1, 4.2, 4.3, 4.6_
  - [x] 10.3 Write property test for timeout expiry





    - **Property 7: Expired Requests Are Auto-Rejected**
    - **Validates: Requirements 1.4, 4.1, 4.2, 4.3**


- [x] 11. Restart Recovery








  - [x] 11.1 Implement recover_on_startup() method


    - Query all hitl_approvals WHERE status = 'AWAITING_APPROVAL'
    - For each record:
      - Verify row_hash integrity
      - If hash mismatch: log SEC-080, reject request, trigger security alert
      - If expires_at < now(): process as expired
      - Else: re-emit WebSocket event
    - Log recovery summary
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

  - [x] 11.2 Write unit tests for restart recovery




    - Test recovery with valid pending requests
    - Test recovery with corrupted hash triggers SEC-080
    - Test recovery processes already-expired requests
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

- [x] 12. Checkpoint - Ensure all core service tests pass



  - Ensure all tests pass, ask the user if questions arise.


- [x] 13. API Endpoints




  - [x] 13.1 Create HITL API router


    - Set up FastAPI router with /api/hitl prefix
    - Add authentication dependency
    - _Requirements: 7.5_

  - [x] 13.2 Implement GET /api/hitl/pending endpoint
    - Require authentication (return 401 SEC-001 if missing)
    - Call gateway.get_pending_approvals()
    - Return list with: trade_id, instrument, side, risk_pct, confidence, request_price, expires_at, seconds_remaining, reasoning_summary, correlation_id

    - _Requirements: 7.1, 7.2, 7.5_
  - [x] 13.3 Implement POST /api/hitl/{trade_id}/approve endpoint
    - Require authentication (return 401 SEC-001 if missing)
    - Verify operator authorization (return 403 SEC-090 if unauthorized)
    - Add rate-limiting (prevent fat-finger double clicks)
    - Parse ApproveRequest body: approved_by, channel, comment
    - Call gateway.process_decision() with APPROVE

    - Return ApprovalResponse: status, trade_id, decided_at, correlation_id
    - _Requirements: 7.3, 7.5, 7.6_
  - [x] 13.4 Implement POST /api/hitl/{trade_id}/reject endpoint
    - Require authentication (return 401 SEC-001 if missing)
    - Verify operator authorization (return 403 SEC-090 if unauthorized)
    - Add rate-limiting (prevent fat-finger double clicks)
    - Parse RejectRequest body: rejected_by, channel, reason
    - Call gateway.process_decision() with REJECT
    - Return ApprovalResponse: status, trade_id, decided_at, correlation_id

    - _Requirements: 7.4, 7.5, 7.6_

  - [x] 13.5 Write property test for pending approvals ordering





    - **Property 14: Pending Approvals Are Ordered By Expiry**

    - **Validates: Requirements 7.1**

  - [x] 13.6 Write integration tests for API endpoints








    - Test full approval flow via API
    - Test full rejection flow via API
    - Test 401 for unauthenticated requests
    - Test 403 for unauthorized operators
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_

- [x] 14. HITL Disabled Mode






  - [x] 14.1 Implement auto-approve when HITL_ENABLED=false

    - Check HITL_ENABLED in create_approval_request()
    - If false: log warning, immediately approve with decision_reason='HITL_DISABLED', decision_channel='SYSTEM'
    - _Requirements: 10.5_




  - [x] 14.2 Write property test for HITL disabled mode






    - **Property 15: HITL Disabled Mode Auto-Approves**
    - **Validates: Requirements 10.5**


- [x] 15. Discord Integration








  - [x] 15.1 Implement send_approval_notification() method



    - Create Discord embed with: instrument, side, risk_pct, confidence, countdown timer, reasoning summary
    - Add APPROVE and REJECT buttons with trade_id encoded
    - Generate one-time deep link token
    - Include deep link URL: https://hub/approvals/{trade_id}?token={token}
    - _Requirements: 8.1, 8.2, 8.3_
  - [x] 15.2 Implement Discord button handler


    - Verify Discord user_id is in HITL_ALLOWED_OPERATORS
    - Call gateway.process_decision() with appropriate decision
    - Update original message with decision result
    - _Requirements: 8.4_
  - [x] 15.3 Implement deep link token validation


    - Check token exists and is not expired
    - Check token has not been used (used_at is NULL)
    - Mark token as used (set used_at)

    - Log access with correlation_id

    - Redirect to approval screen
    - _Requirements: 8.5, 8.6_
  - [x] 15.4 Write property test for deep link tokens




    - **Property 12: Deep Link Tokens Are Single-Use**
    - **Validates: Requirements 8.5**
  - [x] 15.5 Implement timeout notification


    - Send Discord message when approval expires
    - Include trade details and timeout reason
    - _Requirements: 4.4_

- [x] 16. WebSocket Events






  - [x] 16.1 Implement WebSocket event emitter

    - Emit 'hitl.created' event when approval request created
    - Emit 'hitl.decided' event when decision recorded
    - Emit 'hitl.expired' event when timeout occurs
    - Include full approval data in payload
    - _Requirements: 2.6, 4.5, 5.4_
  - [x] 16.2 Write unit tests for WebSocket events




    - Test event emission on create
    - Test event emission on decision
    - Test event emission on timeout
    - _Requirements: 2.6, 4.5, 5.4_

- [x] 17. Observability and Logging





  - [x] 17.1 Implement structured logging


    - All logs include: correlation_id, actor, action, result
    - Error logs include: error_code (SEC-XXX), full context
    - Use appropriate log levels (INFO, WARNING, ERROR, CRITICAL)
    - _Requirements: 9.5, 9.6_
  - [x] 17.2 Register Prometheus metrics


    - hitl_requests_total (counter)
    - hitl_approvals_total (counter)
    - hitl_rejections_total (counter with reason label)
    - hitl_response_latency_seconds (histogram)
    - blocked_by_guardian_total (counter)
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 11.5_

  - [x] 17.3 Write unit tests for logging format




    - Verify correlation_id in all logs
    - Verify SEC-XXX codes in error logs
    - _Requirements: 9.5, 9.6_


- [x] 18. Wire Everything Together




  - [x] 18.1 Register HITL router in main app


    - Add /api/hitl routes to FastAPI app
    - Configure authentication middleware
    - _Requirements: 7.1, 7.2, 7.3, 7.4_
  - [x] 18.2 Start ExpiryWorker on app startup


    - Register as background task
    - Configure 30-second interval
    - _Requirements: 4.1_
  - [x] 18.3 Call recover_on_startup() on app startup


    - Run before accepting requests
    - Log recovery results
    - _Requirements: 5.1_
  - [x] 18.4 Register Guardian lock event handler


    - Subscribe to Guardian lock events
    - Trigger cascade rejection of pending approvals
    - _Requirements: 11.4_

- [x] 19. Final Checkpoint - Ensure all tests pass







  - Ensure all tests pass, ask the user if questions arise.

- [x] 20. End-to-End Integration Tests






  - [x]* 20.1 Write E2E test: Full approval flow

    - Create approval request → Approve via API → Verify trade state ACCEPTED
    - Verify audit log entries
    - Verify Prometheus counters
    - _Requirements: 1.1, 1.2, 3.7, 3.8, 9.1, 9.2_

  - [x]* 20.2 Write E2E test: Full rejection flow


    - Create approval request → Reject via API → Verify trade state REJECTED
    - Verify audit log entries
    - Verify Prometheus counters
    - _Requirements: 1.1, 1.3, 3.7, 3.8, 9.1, 9.3_
  - [x]* 20.3 Write E2E test: Timeout flow

    - Create approval request → Wait for expiry → Verify auto-reject
    - Verify decision_reason = HITL_TIMEOUT
    - Verify Discord notification sent
    - _Requirements: 1.4, 4.1, 4.2, 4.3, 4.4, 4.6_
  - [x]* 20.4 Write E2E test: Guardian lock cascade

    - Create approval request → Trigger Guardian lock → Verify all pending rejected
    - Verify decision_reason = GUARDIAN_LOCK
    - _Requirements: 11.4, 11.5_
  - [x]* 20.5 Write chaos test: Restart mid-approval

    - Create approval request → Simulate restart → Verify recovery
    - Verify pending requests re-emitted
    - Verify expired requests processed
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

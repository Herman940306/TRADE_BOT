# Implementation Plan

- [x] 1. Create core policy module and data structures



  - [x] 1.1 Create PolicyReasonCode enum and EVALUATION_PRECEDENCE constant


    - Define all reason codes: ALLOW_ALL_GATES_PASSED, HALT_KILL_SWITCH, HALT_BUDGET_HARD_STOP, etc.
    - Define precedence list with ranks 1-4
    - _Requirements: 1.1, 4.3_

  - [x] 1.2 Create PolicyContext frozen dataclass
    - Fields: kill_switch_active, budget_signal, health_status, risk_assessment, correlation_id, timestamp_utc
    - Add validation in __post_init__
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

  - [x] 1.3 Create PolicyDecision frozen dataclass
    - Fields: decision, reason_code, blocking_gate, precedence_rank, is_latched
    - _Requirements: 1.1, 4.2_
  - [x] 1.4 Write property test for PolicyContext validation



    - **Property 1: Policy Output Domain**
    - **Validates: Requirements 1.1**

  - [x] 1.5 Create PolicyDecisionRecord dataclass for audit
    - Include all fields: correlation_id, timestamp_utc, policy_decision, reason_code, blocking_gate, precedence_rank, context_snapshot, ai_confidence, is_latched
    - _Requirements: 4.1, 4.2, 4.4_


- [x] 2. Implement TradePermissionPolicy core logic




  - [x] 2.1 Implement TradePermissionPolicy class with evaluate() method


    - Implement short-circuit evaluation order: Kill Switch → Budget → Health → Risk → ALLOW
    - Return PolicyDecision with reason_code and blocking_gate
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6_

  - [x] 2.2 Write property test for kill switch supremacy

    - **Property 2: Kill Switch Supremacy**
    - **Validates: Requirements 1.2**
  - [x] 2.3 Write property test for budget gate enforcement

    - **Property 3: Budget Gate Enforcement**
    - **Validates: Requirements 1.3**

  - [x] 2.4 Write property test for health status gating
    - **Property 4: Health Status Gating**
    - **Validates: Requirements 1.4**

  - [x] 2.5 Write property test for risk assessment gating
    - **Property 5: Risk Assessment Gating**
    - **Validates: Requirements 1.5**
  - [x] 2.6 Implement monotonic severity latch behavior

    - Add _latched_state, _latch_timestamp, _latch_reset_window
    - HALT stays HALT until explicit reset or window elapses
    - _Requirements: 1.2 (hardening)_

  - [x] 2.7 Write property test for monotonic severity
    - **Property 14: Monotonic Severity (Latch Behavior)**
    - **Validates: Requirements 1.2 (hardening)**
  - [x] 2.8 Implement reset_policy_latch() method

    - Require operator_id for audit trail
    - Log latch reset event
    - _Requirements: 1.2 (hardening)_

- [x] 3. Checkpoint - Ensure all tests pass





  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Implement AI confidence isolation





  - [x] 4.1 Ensure evaluate() does not accept ai_confidence parameter


    - Policy decision must be independent of AI confidence
    - _Requirements: 2.2_
  - [x] 4.2 Write property test for AI confidence isolation


    - **Property 6: AI Confidence Isolation**
    - **Validates: Requirements 2.2**
  - [x] 4.3 Implement audit logging that includes ai_confidence separately


    - Log ai_confidence alongside policy_decision but not as input
    - _Requirements: 2.1, 2.3, 2.4_

- [x] 5. Implement PolicyContextBuilder integration layer



  - [x] 5.1 Create PolicyContextBuilder class


    - Accept CircuitBreaker, BudgetIntegrationModule, HealthVerificationModule, RiskGovernor
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

  - [x] 5.2 Implement build() method with source queries
    - Query each source module for current state
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

  - [x] 5.3 Implement restrictive defaults on source failure
    - If any source fails, default to most restrictive value
    - Log error code POLICY_CONTEXT_INCOMPLETE
    - _Requirements: 3.5_

  - [x] 5.4 Write property test for restrictive defaults


    - **Property 7: Restrictive Default on Source Failure**
    - **Validates: Requirements 3.5**


- [x] 6. Implement audit trail and logging




  - [x] 6.1 Implement policy decision logging with full context


    - Log complete PolicyContext with correlation_id
    - Include timestamp_utc, policy_decision, all input values
    - _Requirements: 4.1, 4.2_
  - [x] 6.2 Implement blocking gate identification in logs


    - When decision is not ALLOW, log which gate caused rejection
    - Include precedence_rank for machine visibility
    - _Requirements: 4.3_
  - [x] 6.3 Write property test for blocking gate identification


    - **Property 8: Blocking Gate Identification**
    - **Validates: Requirements 4.3**
  - [x] 6.4 Implement persistence to immutable audit table


    - Write PolicyDecisionRecord to database
    - _Requirements: 4.4_

- [x] 7. Checkpoint - Ensure all tests pass



  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Implement FailureScenarioSimulator framework



  - [x] 8.1 Create ScenarioResult dataclass


    - Fields: scenario_id, scenario_type, expected_state, actual_state, assertion_passed, trades_during_unsafe, logs, duration_ms
    - _Requirements: 7.1, 7.3_

  - [x] 8.2 Create FailureScenarioSimulator class skeleton

    - Define injection method signatures

    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

  - [x] 8.3 Implement inject_exchange_downtime()
    - System should enter NEUTRAL within 5 seconds
    - _Requirements: 6.1_
  - [x] 8.4 Write property test for exchange downtime response



    - **Property 10: Exchange Downtime Response**
    - **Validates: Requirements 6.1**


  - [x] 8.5 Implement inject_partial_fill()

    - Log discrepancy and trigger reconciliation
    - _Requirements: 6.2_
  - [x] 8.6 Implement inject_stale_market_data()
    - Reject new trades until fresh data arrives


    - _Requirements: 6.3_


  - [x] 8.7 Write property test for stale data rejection
    - **Property 11: Stale Data Rejection**
    - **Validates: Requirements 6.3**
  - [x] 8.8 Implement inject_budgetguard_corruption()


    - Enter HALT state and log BUDGET_DATA_CORRUPT

    - _Requirements: 6.4_


  - [x] 8.9 Write property test for BudgetGuard corruption handling
    - **Property 12: BudgetGuard Corruption Handling**
    - **Validates: Requirements 6.4**
  - [x] 8.10 Implement inject_sse_disconnect_storm()
    - Trigger L6 Lockdown after 5 failed reconnection attempts
    - _Requirements: 6.5_
  - [x] 8.11 Implement inject_exchange_clock_drift()



    - System should enter NEUTRAL when drift exceeds 1 second
    - _Requirements: 6.6_

  - [x] 8.12 Write property test for exchange clock drift response

    - **Property 15: Exchange Clock Drift Protection**
    - **Validates: Requirements 9.2**


- [x] 9. Implement ExchangeTimeSynchronizer module




  - [x] 9.1 Create TimeSyncResult dataclass


    - Fields: local_time_utc, exchange_time_utc, drift_ms, is_within_tolerance, error_code, correlation_id, timestamp_utc
    - _Requirements: 9.1_
  - [x] 9.2 Create ExchangeTimeSynchronizer class

    - Accept exchange_client, max_drift_ms (default 1000), sync_interval_seconds (default 60)
    - _Requirements: 9.1, 9.2_
  - [x] 9.3 Implement sync_time() method

    - Query exchange /time endpoint and calculate drift
    - Log drift_ms for monitoring
    - _Requirements: 9.1, 9.5_
  - [x] 9.4 Implement drift threshold detection

    - Enter NEUTRAL state when drift exceeds MAX_CLOCK_DRIFT_MS
    - Log error code EXCHANGE_TIME_DRIFT
    - _Requirements: 9.2_
  - [x] 9.5 Implement drift recovery

    - Clear NEUTRAL state when drift returns to tolerance
    - _Requirements: 9.3_
  - [x] 9.6 Implement exchange /time unavailable handling

    - Enter NEUTRAL state and log EXCHANGE_TIME_UNAVAILABLE
    - _Requirements: 9.4_
  - [x] 9.7 Write property test for clock drift recovery





    - **Property 16: Clock Drift Recovery**
    - **Validates: Requirements 9.3**

- [x] 10. Implement failure scenario assertions



  - [x] 10.1 Implement state assertion verification


    - Assert expected_state matches actual_state
    - _Requirements: 7.1_


  - [x] 10.2 Write property test for no trades during unsafe conditions

    - **Property 9: No Trades During Unsafe Conditions**
    - **Validates: Requirements 7.2**
  - [x] 10.3 Implement structured logging for scenarios


    - Include scenario_id and outcome in logs
    - _Requirements: 7.3_

  - [x] 10.4 Implement assertion failure reporting


    - Report specific expectation that was violated
    - _Requirements: 7.4_

- [x] 11. Checkpoint - Ensure all tests pass





  - Ensure all tests pass, ask the user if questions arise.

- [x] 12. Implement backwards-compatible API integration





  - [x] 12.1 Wire TradePermissionPolicy into existing dispatcher


    - Existing trade signal handlers continue to receive signals
    - _Requirements: 8.1_

  - [x] 12.2 Maintain existing confidence-based logging

    - Existing audit infrastructure remains functional
    - _Requirements: 8.2_

  - [x] 12.3 Route policy rejections through existing audit infrastructure

    - Rejections flow through existing audit tables
    - _Requirements: 8.3_

  - [x] 12.4 Implement configuration flag for policy layer

    - When disabled, fall back to previous behavior with warning log
    - _Requirements: 8.4_

  - [x] 12.5 Write property test for policy supremacy

    - **Property 13: Policy Supremacy**
    - **Validates: Requirements 1.1, 2.2**



- [x] 13. Generate LIVE Trading Runbook




  - [x] 13.1 Create runbook template with preconditions checklist

    - Include all verification steps before going live
    - _Requirements: 5.1_

  - [x] 13.2 Add environment variable verification section

    - List all required secrets and how to verify them
    - _Requirements: 5.2_

  - [x] 13.3 Add DRY_RUN to LIVE transition steps

    - Explicit step-by-step transition procedure
    - _Requirements: 5.3_

  - [x] 13.4 Add Kill Switch verification procedure

    - How to verify kill switch is functional
    - _Requirements: 5.4_
  - [x] 13.5 Add emergency shutdown procedure


    - Exact commands for emergency shutdown
    - _Requirements: 5.5_

  - [x] 13.6 Add post-incident checklist

    - Recovery steps after an incident
    - _Requirements: 5.6_

  - [x] 13.7 Add audit extraction steps

    - How to extract audit data for compliance review
    - _Requirements: 5.7_

  - [x] 13.8 Add Exchange Clock Drift verification procedure

    - How to verify time sync is functional and within tolerance
    - _Requirements: 9.1, 9.5_

- [x] 14. Final Checkpoint - Ensure all tests pass





  - Ensure all tests pass, ask the user if questions arise.

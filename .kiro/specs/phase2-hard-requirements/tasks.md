# Implementation Plan

- [x] 1. Database Schema for Trade Lifecycle








  - [x] 1.1 Create migration 022_trade_lifecycle_states.sql


    - Create `trade_lifecycle` table with state tracking
    - Create `trade_state_transitions` table with idempotency constraint
    - Create `strategy_decisions` table for decision persistence
    - Add `validate_state_transition()` trigger function
    - Attach immutability triggers (prevent UPDATE/DELETE)
    - Grant permissions to app_trading role
    - _Requirements: 1.1, 1.6_

  - [x] 1.2 Write property test for transition idempotency

    - **Property 4: Transition Idempotency**
    - **Validates: Requirements 1.6**

- [x] 2. Trade Lifecycle Manager Service





  - [x] 2.1 Create services/trade_lifecycle.py



    - Implement TradeState enum with REJECTED state
    - Implement Trade and StateTransition dataclasses
    - Implement TradeLifecycleManager class
    - Add create_trade() method (initializes PENDING)
    - Add transition() method with validation
    - Add get_trade_state() and get_trades_by_state() methods
    - Include correlation_id on all operations
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.7_

  - [x] 2.2 Write property test for trade creation

    - **Property 1: Trade Creation Initializes PENDING State**
    - **Validates: Requirements 1.1**
  - [x] 2.3 Write property test for valid state transitions


    - **Property 2: Valid State Transitions Only**
    - **Validates: Requirements 1.2, 1.3, 1.4, 1.5, 1.7**

  - [x] 2.4 Write property test for transition persistence

    - **Property 3: State Transition Persistence**
    - **Validates: Requirements 1.6**

- [x] 3. Checkpoint - Ensure all tests pass





  - Ensure all tests pass, ask the user if questions arise.


- [x] 4. Strategy Manager with Deterministic Mode





  - [x] 4.1 Create services/strategy_manager.py

    - Implement StrategyMode enum (DETERMINISTIC, STOCHASTIC)
    - Implement StrategyDecision dataclass
    - Implement StrategyManager class
    - Add evaluate() method with input/output logging
    - Add _log_inputs() and _log_outputs() helper methods
    - Add _compute_hash() for inputs/outputs
    - Persist decisions to strategy_decisions table
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

  - [x] 4.2 Write property test for deterministic reproducibility

    - **Property 5: Deterministic Strategy Reproducibility**
    - **Validates: Requirements 2.4**
  - [x] 4.3 Write property test for strategy logging


    - **Property 6: Strategy Input/Output Logging**
    - **Validates: Requirements 2.2, 2.3, 2.5**
  - [x] 4.4 Write property test for decision persistence


    - **Property 7: Strategy Decision Persistence**
    - **Validates: Requirements 2.5**


- [x] 5. Checkpoint - Ensure all tests pass




  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Guardian Kill-Switch Integration





  - [x] 6.1 Integrate Guardian with Trade Lifecycle Manager


    - Add Guardian check in create_trade() flow
    - Transition to REJECTED if Guardian locked
    - Add Prometheus metrics for lock status
    - _Requirements: 3.1, 3.2, 3.6_
  - [x] 6.2 Write property test for Guardian lock blocking trades


    - **Property 8: Guardian Lock Blocks All Trades**
    - **Validates: Requirements 3.2, 3.6**
  - [x] 6.3 Write property test for lock persistence


    - **Property 9: Guardian Lock Persistence**
    - **Validates: Requirements 3.4**

- [x] 7. Grafana Dashboard Panels





  - [x] 7.1 Add "Trades by State" panel to trade-simulation.json


    - Query trade_lifecycle table grouped by current_state
    - Display as pie chart or bar chart
    - Include REJECTED state count
    - _Requirements: 4.1_
  - [x] 7.2 Add "Signal Confidence vs Outcome" panel

    - Query strategy_decisions table
    - Plot confidence score vs action taken
    - _Requirements: 4.2_
  - [x] 7.3 Update Guardian dashboard with lock reason display


    - Show lock_reason from lock file
    - Display lock timestamp
    - _Requirements: 4.3_


- [x] 8. Guardian Kill-Switch Verification Test





  - [x] 8.1 Create manual test script tools/test_guardian_killswitch.py

    - Force demo loss exceeding 1.0%
    - Verify Guardian locks within 60 seconds
    - Verify trade count = 0 after lock
    - Verify bot continues running (no crash)
    - Verify dashboard shows lock reason



    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

- [x] 9. Integration with Main Orchestrator



  - [x] 9.1 Update main.py to use Trade Lifecycle Manager

    - Import TradeLifecycleManager
    - Create trades with PENDING state on signal receipt
    - Transition states through execution flow
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

  - [x] 9.2 Add STRATEGY_MODE environment variable






    - Default to DETERMINISTIC
    - Document in .env.example
    - _Requirements: 2.1_


- [x] 10. Final Checkpoint - Ensure all tests pass




  - Ensure all tests pass, ask the user if questions arise.

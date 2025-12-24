# Requirements Document

## Introduction

Phase 2 Hard Requirements are mandatory prerequisites before transitioning to live trading. These requirements ensure trade lifecycle integrity, deterministic strategy execution, and verified Guardian kill-switch functionality. Without these safeguards, real capital cannot be risked.

## Glossary

- **Trade_Lifecycle_State**: The current state of a trade in its lifecycle (PENDING, ACCEPTED, FILLED, CLOSED, SETTLED)
- **Guardian_Service**: The system health monitor that enforces the 1.0% daily loss hard stop
- **DemoBroker**: Paper trading broker that simulates order execution with real market data
- **Strategy_Mode**: Configuration that determines whether strategy execution is deterministic or allows randomness
- **Kill_Switch**: Emergency mechanism that immediately halts all trading when triggered
- **Correlation_ID**: Unique identifier linking all operations in a trade's audit trail

## Requirements

### Requirement 1: Trade Lifecycle State Machine

**User Story:** As a system operator, I want every trade to follow a strict state machine, so that I can prevent ghost trades and enable accurate P&L tracking.

#### Acceptance Criteria

1. WHEN a trade signal is received THEN the System SHALL create a trade record with state PENDING
2. WHEN the Guardian approves a trade THEN the System SHALL transition the trade state from PENDING to ACCEPTED
3. WHEN the broker confirms order execution THEN the System SHALL transition the trade state from ACCEPTED to FILLED
4. WHEN a position is closed THEN the System SHALL transition the trade state from FILLED to CLOSED
5. WHEN P&L is reconciled THEN the System SHALL transition the trade state from CLOSED to SETTLED
6. WHEN a state transition occurs THEN the System SHALL persist the transition timestamp and correlation_id to PostgreSQL
7. IF a trade attempts an invalid state transition THEN the System SHALL reject the transition and log an error with correlation_id

### Requirement 2: Deterministic Strategy Mode

**User Story:** As a developer, I want a deterministic strategy mode, so that I can reproduce and debug trading decisions with identical inputs producing identical outputs.

#### Acceptance Criteria

1. WHEN STRATEGY_MODE is set to DETERMINISTIC THEN the System SHALL prohibit all random number generation in strategy logic
2. WHEN STRATEGY_MODE is DETERMINISTIC THEN the System SHALL log all strategy inputs with correlation_id before processing
3. WHEN STRATEGY_MODE is DETERMINISTIC THEN the System SHALL log all strategy outputs with correlation_id after processing
4. WHEN identical inputs are provided in DETERMINISTIC mode THEN the System SHALL produce identical outputs
5. WHEN a strategy decision is made THEN the System SHALL record the signal confidence score and outcome for analysis

### Requirement 3: Guardian Kill-Switch Verification

**User Story:** As a system operator, I want verified Guardian kill-switch functionality, so that I can trust the system will halt trading immediately when loss limits are exceeded.

#### Acceptance Criteria

1. WHEN daily loss exceeds 1.0% of starting equity THEN the Guardian SHALL lock the system within 1 heartbeat cycle (60 seconds)
2. WHEN the Guardian locks the system THEN the System SHALL reject all new trade requests immediately
3. WHEN the Guardian locks the system THEN the System SHALL continue running without crashing
4. WHEN the Guardian locks the system THEN the System SHALL persist the lock reason to the lock file
5. WHEN the Guardian is locked THEN the Grafana dashboard SHALL display the lock status and reason
6. WHEN the Guardian is locked THEN the trade count for new trades SHALL equal zero

### Requirement 4: Grafana Observability Panels

**User Story:** As a system operator, I want Grafana dashboards showing trade states and signal outcomes, so that I can monitor system health and strategy performance.

#### Acceptance Criteria

1. WHEN trades exist in the database THEN the Grafana dashboard SHALL display a "Trades by State" panel showing counts per lifecycle state
2. WHEN strategy decisions are recorded THEN the Grafana dashboard SHALL display a "Signal Confidence vs Outcome" panel
3. WHEN the Guardian status changes THEN the Grafana dashboard SHALL reflect the current lock status within 30 seconds

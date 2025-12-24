# Requirements Document

## Introduction

This specification defines the Explicit Trade Permission Policy Layer for Project Autonomous Alpha. The system separates AI confidence (informational) from trade permission (policy-based), ensuring that AI confidence scores NEVER directly authorize trades. Instead, a deterministic TradePermissionPolicy consumes budget gating, risk assessment, and health status to produce explicit ALLOW | NEUTRAL | HALT decisions. Additionally, this spec covers the LIVE Trading Runbook for human operators and a Failure Scenario Simulator for tabletop testing.

## Glossary

- **TradePermissionPolicy**: Deterministic policy module that evaluates context and produces ALLOW, NEUTRAL, or HALT decisions
- **AI Confidence**: Informational score from ML models indicating signal quality; NEVER authorizes trades directly
- **Policy Context**: Structured input containing kill_switch_active, budget_signal, health_status, and risk_assessment
- **ALLOW**: Permission state indicating trade execution is permitted by all policy gates
- **NEUTRAL**: Permission state indicating system should maintain current positions without new trades
- **HALT**: Permission state indicating immediate cessation of all trading activity
- **LIVE Trading Runbook**: Human-readable operational documentation for transitioning to live trading
- **Failure Scenario Simulator**: Testing framework that injects failure conditions to verify system safety
- **Tabletop Test**: Structured simulation of failure scenarios to validate system behavior without live execution
- **Exchange Clock Drift**: Time skew between local server and exchange server that can cause HMAC signature rejection
- **ExchangeTimeSynchronizer**: Module that monitors and validates time synchronization with the exchange

## Requirements

### Requirement 1: Trade Permission Policy Module

**User Story:** As a system architect, I want trade authorization separated from AI confidence scoring, so that policy-based gates have absolute authority over trade execution.

#### Acceptance Criteria

1. WHEN the TradePermissionPolicy evaluates a context THEN the system SHALL return exactly one of ALLOW, NEUTRAL, or HALT as a string
2. WHEN context.kill_switch_active is True THEN the TradePermissionPolicy SHALL return HALT regardless of other context values
3. WHEN context.budget_signal is not equal to ALLOW THEN the TradePermissionPolicy SHALL return HALT
4. WHEN context.health_status is not equal to GREEN THEN the TradePermissionPolicy SHALL return NEUTRAL
5. WHEN context.risk_assessment is CRITICAL THEN the TradePermissionPolicy SHALL return HALT
6. WHEN all policy gates pass THEN the TradePermissionPolicy SHALL return ALLOW

### Requirement 2: AI Confidence Isolation

**User Story:** As a risk manager, I want AI confidence scores to be purely informational, so that no ML model output can directly authorize a trade.

#### Acceptance Criteria

1. WHEN a trade signal includes ai_confidence THEN the system SHALL log the confidence value for audit purposes only
2. WHEN the TradePermissionPolicy evaluates context THEN the system SHALL NOT include ai_confidence in the decision logic
3. WHEN a trade is executed THEN the audit record SHALL include both ai_confidence and policy_decision as separate fields
4. WHEN ai_confidence is above 99 AND policy_decision is HALT THEN the system SHALL reject the trade and log the override

### Requirement 3: Policy Context Construction

**User Story:** As a system operator, I want policy context constructed from authoritative sources, so that trade decisions are based on verified system state.

#### Acceptance Criteria

1. WHEN constructing PolicyContext THEN the system SHALL query kill_switch_active from the circuit breaker module
2. WHEN constructing PolicyContext THEN the system SHALL query budget_signal from the BudgetGuard integration
3. WHEN constructing PolicyContext THEN the system SHALL query health_status from the Health Verification Module
4. WHEN constructing PolicyContext THEN the system SHALL query risk_assessment from the Risk Governor
5. WHEN any context source is unavailable THEN the system SHALL default to the most restrictive value and log error code POLICY_CONTEXT_INCOMPLETE

### Requirement 4: Decision Logging and Audit Trail

**User Story:** As an auditor, I want every policy decision logged with full context, so that trade authorization can be reconstructed and verified.

#### Acceptance Criteria

1. WHEN TradePermissionPolicy returns a decision THEN the system SHALL log the complete PolicyContext with correlation_id
2. WHEN a decision is logged THEN the record SHALL include timestamp_utc, policy_decision, and all input values
3. WHEN a trade is blocked by policy THEN the system SHALL log which specific gate caused the rejection
4. WHEN policy decisions are persisted THEN the system SHALL write to the immutable audit table

### Requirement 5: LIVE Trading Runbook Generation

**User Story:** As a human operator, I want a comprehensive runbook for transitioning to live trading, so that I can safely enable production execution.

#### Acceptance Criteria

1. WHEN the runbook is generated THEN the document SHALL include a preconditions checklist with verification steps
2. WHEN the runbook is generated THEN the document SHALL include environment variable verification for all required secrets
3. WHEN the runbook is generated THEN the document SHALL include explicit DRY_RUN to LIVE transition steps
4. WHEN the runbook is generated THEN the document SHALL include Kill Switch verification procedure
5. WHEN the runbook is generated THEN the document SHALL include emergency shutdown procedure with exact commands
6. WHEN the runbook is generated THEN the document SHALL include post-incident checklist for recovery
7. WHEN the runbook is generated THEN the document SHALL include audit extraction steps for compliance review

### Requirement 6: Failure Scenario Simulator Framework

**User Story:** As a reliability engineer, I want to simulate failure scenarios, so that I can verify the system behaves safely under adverse conditions.

#### Acceptance Criteria

1. WHEN the FailureScenarioSimulator injects exchange_downtime THEN the system SHALL enter NEUTRAL state within 5 seconds
2. WHEN the FailureScenarioSimulator injects partial_fill THEN the system SHALL log the discrepancy and trigger reconciliation
3. WHEN the FailureScenarioSimulator injects stale_market_data THEN the system SHALL reject new trades until fresh data arrives
4. WHEN the FailureScenarioSimulator injects budgetguard_corruption THEN the system SHALL enter HALT state and log BUDGET_DATA_CORRUPT
5. WHEN the FailureScenarioSimulator injects sse_disconnect_storm THEN the system SHALL trigger L6 Lockdown after 5 failed reconnection attempts
6. WHEN the FailureScenarioSimulator injects exchange_clock_drift exceeding 1 second THEN the system SHALL enter NEUTRAL state and log EXCHANGE_TIME_DRIFT

### Requirement 9: Exchange Clock Drift Protection

**User Story:** As a reliability engineer, I want the system to detect and respond to exchange clock drift, so that HMAC-signed requests are not silently rejected due to timestamp skew.

#### Acceptance Criteria

1. WHEN the ExchangeTimeSynchronizer queries the exchange /time endpoint THEN the system SHALL calculate the drift between local and exchange time
2. WHEN the absolute clock drift exceeds 1 second THEN the system SHALL enter NEUTRAL state and log error code EXCHANGE_TIME_DRIFT
3. WHEN the clock drift returns to within tolerance THEN the system SHALL clear the NEUTRAL state and resume normal operation
4. WHEN the exchange /time endpoint is unavailable THEN the system SHALL enter NEUTRAL state and log error code EXCHANGE_TIME_UNAVAILABLE
5. WHEN the ExchangeTimeSynchronizer performs a sync THEN the system SHALL log the drift value in milliseconds for monitoring

### Requirement 7: Failure Scenario Assertions

**User Story:** As a test engineer, I want each failure scenario to produce verifiable assertions, so that safety behavior can be automatically validated.

#### Acceptance Criteria

1. WHEN a failure scenario completes THEN the simulator SHALL assert the expected system state matches actual state
2. WHEN a failure scenario involves trade signals THEN the simulator SHALL verify NO trades occurred during unsafe conditions
3. WHEN a failure scenario completes THEN the simulator SHALL produce structured logs with scenario_id and outcome
4. WHEN a failure scenario assertion fails THEN the simulator SHALL report the specific expectation that was violated

### Requirement 8: Backwards-Compatible API

**User Story:** As a system integrator, I want the new policy layer to maintain backwards compatibility, so that existing components continue to function.

#### Acceptance Criteria

1. WHEN the TradePermissionPolicy is integrated THEN existing trade signal handlers SHALL continue to receive signals
2. WHEN the policy layer is active THEN the existing confidence-based logging SHALL remain functional
3. WHEN the policy layer rejects a trade THEN the rejection SHALL flow through existing audit infrastructure
4. WHEN the policy layer is disabled via configuration THEN the system SHALL fall back to previous behavior with a warning log

</content>

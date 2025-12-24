# Requirements Document

## Introduction

The HITL (Human-In-The-Loop) Approval Gateway is the core control mechanism for Project Autonomous Alpha. It enforces the Prime Directive: **"The bot thinks. You approve. The system never betrays you."**

This gateway sits between trade signal generation and execution, ensuring that no trade reaches the exchange without explicit, auditable human approval. The system implements a hard gate (not a UI feature) with fail-closed behavior, timeout-to-reject semantics, and full forensic auditability.

The HITL Gateway integrates with:
- **Guardian Service**: Capital protection locks that override all other decisions
- **Trade Lifecycle Manager**: State machine governing trade progression
- **Web Command Hub**: Primary approval interface
- **Discord Bot**: Notification and secondary approval channel
- **Database**: Immutable audit trail with integrity verification

## Glossary

- **HITL**: Human-In-The-Loop - mandatory human approval gate before trade execution
- **Guardian**: Capital protection service that enforces daily loss limits and can lock the system
- **Trade Lifecycle**: State machine governing trade states from PENDING to SETTLED
- **Approval Request**: Database record representing a pending human decision
- **Correlation ID**: UUID linking all related events across the system for audit traceability
- **Row Hash**: SHA-256 integrity check computed on approval record fields
- **Slippage Guard**: Price drift validation between request time and approval time
- **Decision Channel**: Source of approval decision (WEB, DISCORD, CLI)
- **Operator**: Authorized human user permitted to approve/reject trades
- **Expiry Job**: Background worker that auto-rejects timed-out approval requests
- **Deep Link**: URL token allowing Discord users to jump directly to Web approval screen

## Requirements

### Requirement 1: Trade Lifecycle State Machine

**User Story:** As a system architect, I want trades to follow a strict state machine with AWAITING_APPROVAL as a mandatory gate, so that no trade executes without human authorization.

#### Acceptance Criteria

1. WHEN a trade signal is generated THEN the HITL_Gateway SHALL transition the trade from PENDING to AWAITING_APPROVAL state
2. WHEN a trade is in AWAITING_APPROVAL state AND an authorized operator approves it THEN the HITL_Gateway SHALL transition the trade to ACCEPTED state
3. WHEN a trade is in AWAITING_APPROVAL state AND an authorized operator rejects it THEN the HITL_Gateway SHALL transition the trade to REJECTED state
4. WHEN a trade is in AWAITING_APPROVAL state AND the timeout expires THEN the HITL_Gateway SHALL transition the trade to REJECTED state with reason HITL_TIMEOUT
5. IF an invalid state transition is attempted THEN the HITL_Gateway SHALL reject the transition, log error code SEC-030, and maintain the current state
6. WHEN any state transition occurs THEN the HITL_Gateway SHALL persist an audit record with correlation_id, timestamp, actor, and previous state

### Requirement 2: Approval Request Creation

**User Story:** As a trade signal generator, I want to create approval requests with complete context, so that operators have all information needed to make informed decisions.

#### Acceptance Criteria

1. WHEN creating an approval request THEN the HITL_Gateway SHALL persist a record containing trade_id, instrument, side, risk_pct, confidence, request_price, reasoning_summary, and correlation_id
2. WHEN creating an approval request THEN the HITL_Gateway SHALL set expires_at to current_time plus HITL_TIMEOUT_SECONDS (default 300 seconds)
3. WHEN creating an approval request THEN the HITL_Gateway SHALL compute and store a SHA-256 row_hash of all record fields
4. WHEN creating an approval request THEN the HITL_Gateway SHALL verify Guardian status is UNLOCKED before proceeding
5. IF Guardian status is LOCKED THEN the HITL_Gateway SHALL reject the request with error code SEC-020 and log the blocked trade
6. WHEN an approval request is created THEN the HITL_Gateway SHALL emit a WebSocket event to connected clients and send a Discord notification with deep link

### Requirement 3: Approval Decision Processing

**User Story:** As an authorized operator, I want to approve or reject trades through Web or Discord, so that I maintain final authority over all executions.

#### Acceptance Criteria

1. WHEN an operator submits an approval decision THEN the HITL_Gateway SHALL verify the operator is in HITL_ALLOWED_OPERATORS list
2. IF the operator is not authorized THEN the HITL_Gateway SHALL reject the decision with error code SEC-090 and log the unauthorized attempt
3. WHEN processing an approval THEN the HITL_Gateway SHALL re-verify Guardian status is UNLOCKED
4. WHEN processing an approval THEN the HITL_Gateway SHALL validate the approval request has not expired
5. WHEN processing an approval THEN the HITL_Gateway SHALL execute the slippage guard to verify price drift is within HITL_SLIPPAGE_MAX_PERCENT (default 0.5%)
6. IF slippage exceeds threshold THEN the HITL_Gateway SHALL reject the approval with error code SEC-050 and notify the operator
7. WHEN a decision is recorded THEN the HITL_Gateway SHALL update decided_at, decided_by, decision_channel, decision_reason, and recompute row_hash
8. WHEN a decision is recorded THEN the HITL_Gateway SHALL write an immutable audit_log entry with full decision context

### Requirement 4: Timeout Expiry Processing

**User Story:** As a system operator, I want stale approval requests to auto-reject, so that the system never hangs waiting indefinitely for human input.

#### Acceptance Criteria

1. WHILE the expiry job is running THEN the HITL_Gateway SHALL query all approval requests where status is AWAITING_APPROVAL and expires_at is less than current_time
2. WHEN an expired request is found THEN the HITL_Gateway SHALL transition status to REJECTED with decision_reason HITL_TIMEOUT
3. WHEN an expired request is processed THEN the HITL_Gateway SHALL set decided_at to current_time and decision_channel to SYSTEM
4. WHEN an expired request is processed THEN the HITL_Gateway SHALL send a Discord notification informing the operator of the timeout
5. WHEN an expired request is processed THEN the HITL_Gateway SHALL emit a WebSocket event to update connected clients
6. WHEN the expiry job runs THEN the HITL_Gateway SHALL increment the hitl_rejections_timeout_total Prometheus counter for each expired request

### Requirement 5: Restart Recovery

**User Story:** As a system administrator, I want the HITL Gateway to recover gracefully after restart, so that pending approvals are not lost or corrupted.

#### Acceptance Criteria

1. WHEN the HITL_Gateway starts THEN the system SHALL query all approval requests where status is AWAITING_APPROVAL
2. WHEN recovering pending requests THEN the HITL_Gateway SHALL verify row_hash integrity for each record
3. IF row_hash verification fails THEN the HITL_Gateway SHALL log error code SEC-080, reject the request, and trigger a security alert
4. WHEN recovering pending requests THEN the HITL_Gateway SHALL re-emit WebSocket events for all valid pending requests
5. WHEN recovering pending requests THEN the HITL_Gateway SHALL immediately process any requests where expires_at is less than current_time

### Requirement 6: Database Integrity

**User Story:** As a compliance officer, I want all approval records to be immutable and tamper-evident, so that the audit trail is legally defensible.

#### Acceptance Criteria

1. WHEN any field in hitl_approvals is modified THEN the HITL_Gateway SHALL recompute and update the row_hash
2. WHEN reading an approval record THEN the HITL_Gateway SHALL verify the stored row_hash matches the computed hash
3. IF hash verification fails THEN the HITL_Gateway SHALL log error code SEC-080, halt processing, and trigger a security alert
4. THE hitl_approvals table SHALL never perform hard deletes; all records are retained permanently
5. WHEN writing to hitl_approvals THEN the HITL_Gateway SHALL use DECIMAL(18,8) for all price fields with ROUND_HALF_EVEN rounding

### Requirement 7: API Endpoints

**User Story:** As a frontend developer, I want well-defined API endpoints for HITL operations, so that the Web Command Hub can interact with the gateway.

#### Acceptance Criteria

1. WHEN GET /api/hitl/pending is called THEN the HITL_Gateway SHALL return all approval requests where status is AWAITING_APPROVAL, ordered by expires_at ascending
2. WHEN GET /api/hitl/pending is called THEN the response SHALL include trade_id, instrument, side, risk_pct, confidence, request_price, expires_at, seconds_remaining, reasoning_summary, and correlation_id
3. WHEN POST /api/hitl/{trade_id}/approve is called THEN the HITL_Gateway SHALL process the approval with approved_by, channel, and optional comment from request body
4. WHEN POST /api/hitl/{trade_id}/reject is called THEN the HITL_Gateway SHALL process the rejection with rejected_by, channel, and reason from request body
5. IF any HITL endpoint is called without valid authentication THEN the HITL_Gateway SHALL return 401 Unauthorized with error code SEC-001
6. IF any HITL endpoint is called by unauthorized operator THEN the HITL_Gateway SHALL return 403 Forbidden with error code SEC-090

### Requirement 8: Discord Integration

**User Story:** As a mobile operator, I want to receive Discord notifications with approval buttons and deep links, so that I can respond quickly from anywhere.

#### Acceptance Criteria

1. WHEN an approval request is created THEN the HITL_Gateway SHALL send a Discord embed containing instrument, side, risk_pct, confidence, countdown timer, and reasoning summary
2. WHEN sending Discord notification THEN the HITL_Gateway SHALL include APPROVE and REJECT buttons with trade_id encoded
3. WHEN sending Discord notification THEN the HITL_Gateway SHALL include a deep link URL in format https://hub/approvals/{trade_id}?token={one_time_token}
4. WHEN a Discord button is clicked THEN the HITL_Gateway SHALL verify the Discord user_id is in HITL_ALLOWED_OPERATORS
5. WHEN a deep link token is validated THEN the HITL_Gateway SHALL verify the token has not expired and has not been used
6. WHEN a deep link is accessed THEN the HITL_Gateway SHALL log the access with correlation_id and redirect to the approval screen

### Requirement 9: Observability

**User Story:** As a DevOps engineer, I want comprehensive metrics and logging, so that I can monitor system health and debug issues.

#### Acceptance Criteria

1. WHEN an approval request is created THEN the HITL_Gateway SHALL increment hitl_requests_total Prometheus counter
2. WHEN an approval is processed THEN the HITL_Gateway SHALL increment hitl_approvals_total Prometheus counter
3. WHEN a rejection is processed THEN the HITL_Gateway SHALL increment hitl_rejections_total Prometheus counter with reason label
4. WHEN a decision is recorded THEN the HITL_Gateway SHALL observe hitl_response_latency_seconds histogram with value (decided_at - requested_at)
5. WHEN any HITL operation occurs THEN the HITL_Gateway SHALL log with correlation_id, actor, action, and result at appropriate log level
6. WHEN an error occurs THEN the HITL_Gateway SHALL log with Sovereign Error Code (SEC-XXX) and full context

### Requirement 10: Configuration

**User Story:** As a system administrator, I want configurable HITL parameters via environment variables, so that I can tune behavior without code changes.

#### Acceptance Criteria

1. THE HITL_Gateway SHALL read HITL_ENABLED environment variable (default true) to enable or disable the approval gate
2. THE HITL_Gateway SHALL read HITL_TIMEOUT_SECONDS environment variable (default 300) for approval expiry duration
3. THE HITL_Gateway SHALL read HITL_SLIPPAGE_MAX_PERCENT environment variable (default 0.5) for price drift threshold
4. THE HITL_Gateway SHALL read HITL_ALLOWED_OPERATORS environment variable as comma-separated list of authorized operator IDs
5. IF HITL_ENABLED is false THEN the HITL_Gateway SHALL log a warning at startup and auto-approve all requests with decision_reason HITL_DISABLED
6. IF any required configuration is missing THEN the HITL_Gateway SHALL fail to start with error code SEC-040

### Requirement 11: Guardian Integration

**User Story:** As a risk manager, I want Guardian locks to override all HITL operations, so that capital protection is never bypassed.

#### Acceptance Criteria

1. WHEN creating an approval request THEN the HITL_Gateway SHALL query Guardian status before proceeding
2. WHEN processing an approval decision THEN the HITL_Gateway SHALL re-query Guardian status before executing
3. IF Guardian status is LOCKED at any checkpoint THEN the HITL_Gateway SHALL reject the operation with error code SEC-020
4. WHEN Guardian transitions to LOCKED THEN the HITL_Gateway SHALL reject all pending approval requests with decision_reason GUARDIAN_LOCK
5. WHEN Guardian lock blocks an operation THEN the HITL_Gateway SHALL increment a blocked_by_guardian counter and notify via Discord

### Requirement 12: Post-Trade Snapshot

**User Story:** As a forensic analyst, I want complete market context captured at decision time, so that I can reconstruct exactly what the operator saw.

#### Acceptance Criteria

1. WHEN an approval decision is processed THEN the HITL_Gateway SHALL capture current bid, ask, spread, and mid price
2. WHEN capturing post-trade snapshot THEN the HITL_Gateway SHALL record response_latency_ms from exchange API call
3. WHEN capturing post-trade snapshot THEN the HITL_Gateway SHALL compute price_deviation_pct between request_price and current_price
4. WHEN capturing post-trade snapshot THEN the HITL_Gateway SHALL persist the snapshot with correlation_id linking to the approval record
5. THE post_trade_snapshots table SHALL use DECIMAL for all price fields with ROUND_HALF_EVEN rounding

# Requirements Document: Sovereign Brain (Risk & Position Sizing)

## Introduction

The Sovereign Brain is the risk management and position sizing engine for Project Autonomous Alpha. It enforces the Sovereign Mandate: **Survival > Capital Preservation > Alpha**. This component calculates position sizes using ATR, monitors ZAR equity in real-time, and triggers the Kill Switch when the ZAR Floor is breached.

## Glossary

- **ATR (Average True Range):** Volatility indicator used for position sizing
- **ZAR Floor:** Minimum equity threshold in South African Rand that triggers Kill Switch
- **Kill Switch:** Emergency procedure to close all positions and revoke API access
- **L6 Lockdown:** Security state triggered by reconciliation mismatch or breach
- **RTT (Round-Trip Time):** Latency measurement to exchange API
- **Reconciliation:** 3-way sync between Local DB, Internal State, and Exchange API

## Requirements

### Requirement 1: ATR-Based Position Sizing

**User Story:** As a trading system, I want to calculate position sizes using ATR, so that I can limit risk exposure based on market volatility.

#### Acceptance Criteria

1. WHEN a trade signal is received THEN the system SHALL calculate position size using ATR with DECIMAL precision
2. WHEN calculating position size THEN the system SHALL ensure maximum 2% of total equity at risk per trade
3. WHEN ATR data is unavailable THEN the system SHALL reject the trade and log AUD-010 error
4. WHILE position sizing is calculated THEN the system SHALL use ROUND_HALF_EVEN (Banker's Rounding)

### Requirement 2: ZAR Equity Monitoring

**User Story:** As a risk manager, I want real-time ZAR equity calculation, so that I can monitor capital preservation status.

#### Acceptance Criteria

1. WHILE the system is operational THEN the system SHALL calculate Net Equity in ZAR every 5 seconds
2. WHEN ZAR equity is calculated THEN the system SHALL use DECIMAL(28,2) precision
3. WHEN exchange rate data is unavailable THEN the system SHALL use last known rate and log RISK-001 warning
4. WHEN ZAR equity calculation completes THEN the system SHALL persist the value to order_events.zar_equity

### Requirement 3: Kill Switch

**User Story:** As a capital preservation system, I want automatic position closure when equity falls below threshold, so that catastrophic losses are prevented.

#### Acceptance Criteria

1. IF Net_Equity < ZAR_FLOOR THEN the system SHALL execute KILL_SWITCH procedure
2. WHEN KILL_SWITCH executes THEN the system SHALL close all open positions
3. WHEN KILL_SWITCH executes THEN the system SHALL cancel all pending orders
4. WHEN KILL_SWITCH executes THEN the system SHALL revoke API session
5. WHEN KILL_SWITCH completes THEN the system SHALL log event to order_events with event_type='KILL_SWITCH'

### Requirement 4: Reconciliation Engine

**User Story:** As an audit system, I want periodic 3-way synchronization, so that data integrity is continuously verified.

#### Acceptance Criteria

1. WHILE the system is operational THEN the system SHALL perform reconciliation every 60 seconds
2. WHEN reconciliation runs THEN the system SHALL compare Local DB, Internal State, and Exchange API
3. IF reconciliation detects mismatch THEN the system SHALL trigger L6 Lockdown
4. WHEN L6 Lockdown triggers THEN the system SHALL cease all new order placement
5. WHEN L6 Lockdown triggers THEN the system SHALL disconnect Hot-Path from Internet

### Requirement 5: Latency Monitoring

**User Story:** As a reliability system, I want continuous latency monitoring, so that order types can be adjusted based on network conditions.

#### Acceptance Criteria

1. WHILE the system is operational THEN the system SHALL send heartbeat to Exchange API every 10 seconds
2. WHEN RTT > 200ms THEN the system SHALL disable Market orders
3. WHILE RTT > 200ms THEN the system SHALL permit only Limit orders
4. WHEN RTT returns to < 200ms THEN the system SHALL re-enable Market orders
5. WHEN heartbeat fails THEN the system SHALL log CONN-001 error and increment failure counter

### Requirement 6: Risk State Persistence

**User Story:** As an audit system, I want all risk decisions persisted, so that every action is traceable.

#### Acceptance Criteria

1. WHEN position size is calculated THEN the system SHALL log calculation parameters to ai_debates
2. WHEN Kill Switch triggers THEN the system SHALL record zar_equity and positions_closed
3. WHEN L6 Lockdown triggers THEN the system SHALL create immutable audit record
4. WHEN latency threshold is breached THEN the system SHALL log RTT value and action taken

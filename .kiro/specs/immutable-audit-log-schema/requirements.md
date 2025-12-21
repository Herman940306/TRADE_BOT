# Requirements Document

## Introduction

This specification defines the Immutable Audit Log Schema for Project Autonomous Alpha (v1.3.0). The schema provides the foundational data persistence layer for a Sovereign Tier financial appliance, ensuring complete traceability of all trading signals, AI deliberations, and order executions. The design enforces L6 Lockdown compliance through append-only tables, strict data type enforcement (zero floats), and cryptographic correlation linking.

## Glossary

- **Audit_Log**: The collective set of immutable PostgreSQL tables that record all system events.
- **correlation_id**: A UUID v4 identifier that links related records across Signals, AI_Debates, and Order_Execution tables.
- **DECIMAL(p,s)**: PostgreSQL NUMERIC type with precision `p` and scale `s`, used for all financial values.
- **Hot_Path**: The deterministic execution pipeline that processes webhooks within 50ms.
- **Cold_Path**: The adversarial intelligence pipeline that validates trades using AI models.
- **L6_Lockdown**: A security state triggered by data mismatches requiring system isolation.
- **ROUND_HALF_EVEN**: Banker's rounding method applied to all financial calculations.
- **Signal**: An inbound TradingView webhook payload containing trade instructions.
- **AI_Debate**: A record of model reasoning (DeepSeek-R1, Llama 3.1) for trade validation.
- **Order_Execution**: A record of the final trade action sent to the exchange.
- **WAL**: PostgreSQL Write-Ahead Logging for durability guarantees.
- **row_hash**: A SHA-256 hash linking each record to its predecessor, creating a blockchain-style audit chain.
- **Order_Events**: An append-only table recording all order lifecycle events including fills, rejections, and cancellations.

## Requirements

### Requirement 1: Signal Ingestion Persistence

**User Story:** As a system auditor, I want all inbound trading signals persisted immediately upon receipt, so that I can trace the origin of every trade decision.

#### Acceptance Criteria

1. WHEN the Hot_Path receives a valid webhook payload, THE Audit_Log SHALL insert a new record into the Signals table within 10 milliseconds.
2. WHEN a Signal record is created, THE Audit_Log SHALL assign a unique correlation_id (UUID v4) to the record.
3. WHEN a duplicate signal_id is received, THE Audit_Log SHALL reject the insert and log an idempotency violation.
4. WHEN the Signals table insert fails, THE Hot_Path SHALL halt processing and trigger an L6_Lockdown alert.
5. WHEN a webhook payload is received, THE Signals table SHALL store the entire unparsed webhook body in a raw_payload JSONB column to ensure data recoverability regardless of schema changes.

### Requirement 2: Financial Data Integrity

**User Story:** As a reliability engineer, I want all financial values stored using fixed-precision decimal types, so that rounding errors cannot corrupt the audit trail.

#### Acceptance Criteria

1. WHILE storing any financial value, THE Audit_Log SHALL use DECIMAL(28,10) as the PostgreSQL data type to provide institutional-grade precision for micro-decimal price increments.
2. WHEN a financial calculation is performed, THE Audit_Log SHALL apply ROUND_HALF_EVEN rounding before persistence.
3. IF a floating-point value is detected in any financial column, THEN THE Audit_Log SHALL reject the transaction and raise error code AUD-001.
4. WHEN storing ZAR equity values, THE Audit_Log SHALL use DECIMAL(28,2) to match currency precision with institutional headroom.

### Requirement 3: Immutability Enforcement

**User Story:** As a compliance officer, I want audit records to be permanently immutable, so that historical data cannot be altered or deleted.

#### Acceptance Criteria

1. WHEN any UPDATE statement targets the Signals table, THE PostgreSQL database SHALL reject the operation via trigger and raise error code AUD-002.
2. WHEN any DELETE statement targets the Signals table, THE PostgreSQL database SHALL reject the operation via trigger and raise error code AUD-003.
3. WHEN any UPDATE statement targets the AI_Debates table, THE PostgreSQL database SHALL reject the operation via trigger and raise error code AUD-004.
4. WHEN any DELETE statement targets the AI_Debates table, THE PostgreSQL database SHALL reject the operation via trigger and raise error code AUD-005.
5. WHEN any UPDATE statement targets the Order_Execution table, THE PostgreSQL database SHALL reject the operation via trigger and raise error code AUD-006.
6. WHEN any DELETE statement targets the Order_Execution table, THE PostgreSQL database SHALL reject the operation via trigger and raise error code AUD-007.
7. WHEN the database schema is deployed, THE PostgreSQL database SHALL revoke UPDATE and DELETE privileges from all application roles on audit tables.

### Requirement 4: Correlation Traceability

**User Story:** As a system auditor, I want to trace any order execution back to its originating signal and AI deliberation, so that I can reconstruct the complete decision chain.

#### Acceptance Criteria

1. WHEN an AI_Debate record is created, THE Audit_Log SHALL reference the originating Signal via correlation_id foreign key.
2. WHEN an Order_Execution record is created, THE Audit_Log SHALL reference the originating Signal via correlation_id foreign key.
3. WHEN querying by correlation_id, THE Audit_Log SHALL return all related records from Signals, AI_Debates, and Order_Execution tables.
4. IF an Order_Execution record is inserted without a valid correlation_id reference, THEN THE PostgreSQL database SHALL reject the insert and raise error code AUD-008.

### Requirement 5: AI Deliberation Persistence

**User Story:** As a reliability engineer, I want all AI model reasoning captured in the audit log, so that I can verify the Cold_Path logic for any trade.

#### Acceptance Criteria

1. WHEN DeepSeek-R1 generates rejection reasons, THE Audit_Log SHALL persist all three reasons as structured JSON in the AI_Debates table.
2. WHEN Llama 3.1 generates sentiment analysis, THE Audit_Log SHALL persist the market mood assessment in the AI_Debates table.
3. WHEN the Cold_Path exceeds 30 seconds, THE Audit_Log SHALL record a timeout event with model_name and elapsed_ms fields.
4. WHEN an AI model returns a confidence score, THE Audit_Log SHALL store the value as DECIMAL(5,4) to preserve four decimal places.

### Requirement 6: Order Execution Audit

**User Story:** As a compliance officer, I want every order sent to the exchange recorded with full execution details, so that I can reconcile against exchange records.

#### Acceptance Criteria

1. WHEN an order is submitted to the exchange, THE Audit_Log SHALL record the order_type, symbol, side, quantity, and price in the Order_Execution table.
2. WHEN the exchange returns a fill confirmation, THE Audit_Log SHALL INSERT a new record into the Order_Events table with fill details. Updates to existing records are strictly forbidden.
3. WHEN the KILL_SWITCH is triggered, THE Audit_Log SHALL record the trigger reason, ZAR equity at trigger time, and all positions closed.
4. WHEN an order is rejected by the exchange, THE Audit_Log SHALL record the rejection reason and exchange error code.

### Requirement 7: Timestamp Integrity

**User Story:** As a system auditor, I want all audit records timestamped with microsecond precision in UTC, so that I can establish precise event ordering.

#### Acceptance Criteria

1. WHEN any audit record is created, THE Audit_Log SHALL populate created_at with TIMESTAMPTZ at microsecond precision.
2. WHEN timestamps are stored, THE Audit_Log SHALL use UTC timezone exclusively.
3. WHEN querying audit records, THE Audit_Log SHALL support ordering by created_at with microsecond granularity.

### Requirement 8: Chain of Custody Hashing

**User Story:** As a security auditor, I want cryptographic proof that no records have been tampered with or deleted, so that I can verify the integrity of the entire audit chain.

#### Acceptance Criteria

1. WHEN a record is inserted into any audit table, THE Audit_Log SHALL generate a SHA-256 hash of (previous_row_hash + current_row_data) and store it in a row_hash column.
2. WHEN the first record is inserted into an audit table, THE Audit_Log SHALL use a predefined genesis hash as the previous_row_hash.
3. WHEN an integrity verification is requested, THE Audit_Log SHALL recompute all row hashes and compare against stored values.
4. IF a row_hash mismatch is detected during verification, THEN THE Audit_Log SHALL trigger an L6_Lockdown and raise error code AUD-009.

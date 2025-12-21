# Implementation Plan: Immutable Audit Log Schema

## Milestone 1: Ingress Layer - ✅ COMPLETE (v1.3.2)

- [x] 1. Environment Setup and PostgreSQL Extensions

  - [x] 1.1 Create database migration directory structure
    - Create `database/migrations/` directory
    - Create `database/tests/` directory for verification scripts
    - _Requirements: N/A (Infrastructure)_

  - [x] 1.2 Enable pgcrypto extension for SHA-256 hashing
    - Write migration script to enable pgcrypto
    - Verify extension is available with `SELECT * FROM pg_extension`
    - _Requirements: 8.1_

  - [x] 1.3 Fix trigger permissions for app_trading role (DB-500)
    - Created `005_fix_trigger_permissions.sql`
    - Applied SECURITY DEFINER to compute_row_hash()
    - Enables hash chain computation without elevating app_trading privileges
    - _Requirements: 8.1, 8.2 (Chain of Custody)_

- [x] 2. Core Trigger Functions (Must exist before tables)

  - [x] 2.1 Implement validate_decimal_input() trigger function
    - Create function to detect precision loss from float casting
    - Raise AUD-001 error on precision loss detection
    - _Requirements: 2.3_

  - [x] 2.3 Implement prevent_update() trigger function
    - Create parameterized function accepting table name and error code
    - Raise appropriate AUD-002 through AUD-006 errors
    - _Requirements: 3.1, 3.3, 3.5_

  - [x] 2.4 Implement prevent_delete() trigger function
    - Create parameterized function accepting table name and error code
    - Raise appropriate AUD-003 through AUD-007 errors
    - _Requirements: 3.2, 3.4, 3.6_

  - [x] 2.6 Implement compute_row_hash() trigger function
    - Create function using pgcrypto digest() for SHA-256
    - Fetch previous row hash or use genesis hash for first row
    - Overwrite any user-provided row_hash value
    - Use row-level locking (FOR UPDATE) to handle concurrent inserts
    - SECURITY DEFINER applied for app_trading compatibility
    - _Requirements: 8.1, 8.2_

  - [x] 2.8 Implement verify_chain_integrity() function
    - Create function to recompute all hashes from genesis
    - Compare against stored row_hash values
    - Raise AUD-009 on mismatch
    - _Requirements: 8.3, 8.4_

- [x] 4. Create Audit Tables with Constraints

  - [x] 4.1 Create signals table
    - Define all columns per design document
    - DECIMAL(28,10) for price and quantity
    - JSONB for raw_payload
    - UNIQUE constraint on signal_id and correlation_id
    - _Requirements: 1.1, 1.2, 1.3, 1.5, 2.1_

  - [x] 4.5 Create ai_debates table
    - Define all columns per design document
    - DECIMAL(5,4) for confidence_score with CHECK constraint
    - Foreign key to signals(correlation_id)
    - _Requirements: 4.1, 5.1, 5.2, 5.3, 5.4_

  - [x] 4.6 Create order_execution table
    - Define all columns per design document
    - DECIMAL(28,10) for quantity and price
    - Foreign key to signals(correlation_id)
    - CHECK constraints for order_type and side
    - _Requirements: 4.2, 6.1_

  - [x] 4.8 Create order_events table
    - Define all columns per design document
    - DECIMAL(28,10) for fill_quantity and fill_price
    - DECIMAL(28,2) for zar_equity
    - Foreign key to order_execution(id)
    - CHECK constraint for event_type
    - _Requirements: 6.2, 6.3, 6.4_

- [x] 5. Attach Triggers to Tables

  - [x] 5.1 Attach validate_decimal_input trigger to all tables
    - BEFORE INSERT trigger on signals, ai_debates, order_execution, order_events
    - _Requirements: 2.3_

  - [x] 5.2 Attach prevent_update triggers to all audit tables
    - BEFORE UPDATE trigger on signals (AUD-002)
    - BEFORE UPDATE trigger on ai_debates (AUD-004)
    - BEFORE UPDATE trigger on order_execution (AUD-006)
    - BEFORE UPDATE trigger on order_events (AUD-006)
    - _Requirements: 3.1, 3.3, 3.5_

  - [x] 5.3 Attach prevent_delete triggers to all audit tables
    - BEFORE DELETE trigger on signals (AUD-003)
    - BEFORE DELETE trigger on ai_debates (AUD-005)
    - BEFORE DELETE trigger on order_execution (AUD-007)
    - BEFORE DELETE trigger on order_events (AUD-007)
    - _Requirements: 3.2, 3.4, 3.6_

  - [x] 5.4 Attach compute_row_hash trigger to all audit tables
    - BEFORE INSERT trigger on all four tables
    - _Requirements: 8.1_

- [x] 7. Security Hardening

  - [x] 7.1 Revoke UPDATE and DELETE privileges from application roles
    - Create application role if not exists
    - REVOKE UPDATE, DELETE on all audit tables
    - GRANT SELECT, INSERT only
    - _Requirements: 3.7_

  - [x] 7.2 Create correlation_id query view
    - vw_trade_audit_full - comprehensive audit view
    - vw_kill_switch_events - L6 safety audit view
    - _Requirements: 4.3_

- [x] 8. Verification Scripts

  - [x] 8.2 Create hash chain verification script
    - Insert sequence of test records
    - Run verify_chain_integrity() function
    - Verify successful validation
    - _Requirements: 8.3_

---

## Milestone 1 Deliverables

| Component | Status | Migration |
|-----------|--------|-----------|
| Core Functions | ✅ | 001_core_functions.sql |
| Audit Tables | ✅ | 002_audit_tables.sql |
| Triggers | ✅ | 003_attach_triggers.sql |
| Security Hardening | ✅ | 004_security_hardening.sql |
| Trigger Permissions | ✅ | 005_fix_trigger_permissions.sql |
| Ingress API | ✅ | app/api/webhook.py |
| Test Suite | ✅ | scripts/test_ingress.py |

---

## Deferred to Future Milestones

### Optional Property Tests (Milestone 2+)
- [ ]* 2.2 Write property test for decimal validation
- [ ]* 2.5 Write property test for immutability enforcement
- [ ]* 2.7 Write property test for hash chain continuity
- [ ]* 2.9 Write property test for hash chain verification
- [ ]* 4.2 Write property test for unique correlation_id
- [ ]* 4.3 Write property test for idempotency
- [ ]* 4.4 Write property test for raw payload round-trip
- [ ]* 4.7 Write property test for foreign key chain integrity
- [ ]* 4.9 Write property test for timestamp precision
- [ ]* 7.3 Write property test for correlation query completeness

---

## Milestone 2: Sovereign Brain (Risk & Position Sizing) - PENDING

- [ ] 1. Risk Engine Core
  - [ ] 1.1 ATR-based position sizing calculator
  - [ ] 1.2 2% equity risk limit enforcement
  - [ ] 1.3 ZAR equity calculation (5-second interval)

- [ ] 2. Kill Switch Implementation
  - [ ] 2.1 ZAR Floor threshold monitoring
  - [ ] 2.2 Emergency position closure logic
  - [ ] 2.3 API session revocation

- [ ] 3. Reconciliation Engine
  - [ ] 3.1 60-second 3-way sync (DB ↔ State ↔ Exchange)
  - [ ] 3.2 L6 Lockdown trigger on mismatch
  - [ ] 3.3 Checksum verification

- [ ] 4. Latency Monitoring
  - [ ] 4.1 10-second heartbeat to Exchange API
  - [ ] 4.2 RTT threshold enforcement (>200ms = Limit orders only)

---

## Changelog

### v1.3.2 (Current)
- Fixed DB-500 error via SECURITY DEFINER on compute_row_hash()
- Ingress Layer fully operational
- All validation tests passing

### v1.3.1
- Initial audit schema implementation
- Core trigger functions
- Security hardening complete

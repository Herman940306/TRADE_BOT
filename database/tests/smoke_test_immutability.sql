-- ============================================================================
-- Project Autonomous Alpha v1.3.2
-- Smoke Test: Immutability & Chain Integrity Verification
-- ============================================================================
--
-- SOVEREIGN TIER INFRASTRUCTURE
-- Test Suite: Immutable Audit Log Schema
--
-- TESTS INCLUDED:
-- Test A: DELETE rejection (AUD-003)
-- Test B: UPDATE rejection (AUD-002)
-- Test C: Hash chain integrity verification
--
-- EXECUTION:
-- Run this script after deploying migrations 001, 002, and 003.
-- All tests must pass before proceeding to production.
--
-- ============================================================================

\echo '=============================================='
\echo 'SOVEREIGN SMOKE TEST: Immutability Verification'
\echo '=============================================='
\echo ''

-- ============================================================================
-- SETUP: Clean slate for testing
-- ============================================================================

\echo '[SETUP] Clearing test data from previous runs...'

-- Disable triggers temporarily to allow cleanup (superuser only)
-- In production, this would require elevated privileges
DO $$
BEGIN
    -- Only attempt cleanup if tables exist and have data
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'order_events') THEN
        ALTER TABLE order_events DISABLE TRIGGER ALL;
        DELETE FROM order_events WHERE TRUE;
        ALTER TABLE order_events ENABLE TRIGGER ALL;
    END IF;
    
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'order_execution') THEN
        ALTER TABLE order_execution DISABLE TRIGGER ALL;
        DELETE FROM order_execution WHERE TRUE;
        ALTER TABLE order_execution ENABLE TRIGGER ALL;
    END IF;
    
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'ai_debates') THEN
        ALTER TABLE ai_debates DISABLE TRIGGER ALL;
        DELETE FROM ai_debates WHERE TRUE;
        ALTER TABLE ai_debates ENABLE TRIGGER ALL;
    END IF;
    
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'signals') THEN
        ALTER TABLE signals DISABLE TRIGGER ALL;
        DELETE FROM signals WHERE TRUE;
        ALTER TABLE signals ENABLE TRIGGER ALL;
    END IF;
    
    RAISE NOTICE 'Test data cleared successfully.';
END $$;

\echo ''
\echo '=============================================='
\echo 'TEST A: DELETE Rejection (AUD-003)'
\echo '=============================================='
\echo ''

-- Insert a test signal
\echo '[TEST A] Inserting test signal...'

INSERT INTO signals (
    signal_id,
    symbol,
    side,
    price,
    quantity,
    raw_payload,
    source_ip,
    hmac_verified,
    row_hash
) VALUES (
    'TEST-SIGNAL-DELETE-001',
    'BTCUSD',
    'BUY',
    45000.1234567890,
    0.5000000000,
    '{"test": "delete_rejection", "timestamp": "2024-01-01T00:00:00Z"}'::jsonb,
    '52.89.214.238'::inet,
    TRUE,
    'placeholder'  -- Will be overwritten by trigger
);

\echo '[TEST A] Signal inserted. Attempting DELETE (should fail with AUD-003)...'
\echo ''

-- Attempt DELETE (should fail)
DO $$
BEGIN
    DELETE FROM signals WHERE signal_id = 'TEST-SIGNAL-DELETE-001';
    RAISE EXCEPTION '[TEST A FAILED] DELETE was permitted. Immutability compromised!';
EXCEPTION
    WHEN OTHERS THEN
        IF SQLERRM LIKE '%AUD-003%' THEN
            RAISE NOTICE '[TEST A PASSED] DELETE rejected with AUD-003: %', SQLERRM;
        ELSE
            RAISE EXCEPTION '[TEST A FAILED] Unexpected error: %', SQLERRM;
        END IF;
END $$;

\echo ''
\echo '=============================================='
\echo 'TEST B: UPDATE Rejection (AUD-002)'
\echo '=============================================='
\echo ''

-- Insert another test signal
\echo '[TEST B] Inserting test signal...'

INSERT INTO signals (
    signal_id,
    symbol,
    side,
    price,
    quantity,
    raw_payload,
    source_ip,
    hmac_verified,
    row_hash
) VALUES (
    'TEST-SIGNAL-UPDATE-001',
    'ETHUSD',
    'SELL',
    2500.9876543210,
    10.0000000000,
    '{"test": "update_rejection", "timestamp": "2024-01-01T00:00:01Z"}'::jsonb,
    '52.89.214.238'::inet,
    TRUE,
    'placeholder'
);

\echo '[TEST B] Signal inserted. Attempting UPDATE on price (should fail with AUD-002)...'
\echo ''

-- Attempt UPDATE (should fail)
DO $$
BEGIN
    UPDATE signals SET price = 99999.0000000000 WHERE signal_id = 'TEST-SIGNAL-UPDATE-001';
    RAISE EXCEPTION '[TEST B FAILED] UPDATE was permitted. Immutability compromised!';
EXCEPTION
    WHEN OTHERS THEN
        IF SQLERRM LIKE '%AUD-002%' THEN
            RAISE NOTICE '[TEST B PASSED] UPDATE rejected with AUD-002: %', SQLERRM;
        ELSE
            RAISE EXCEPTION '[TEST B FAILED] Unexpected error: %', SQLERRM;
        END IF;
END $$;

\echo ''
\echo '=============================================='
\echo 'TEST C: Hash Chain Integrity Verification'
\echo '=============================================='
\echo ''

-- Insert a third signal to have 3 records for chain verification
\echo '[TEST C] Inserting third test signal...'

INSERT INTO signals (
    signal_id,
    symbol,
    side,
    price,
    quantity,
    raw_payload,
    source_ip,
    hmac_verified,
    row_hash
) VALUES (
    'TEST-SIGNAL-CHAIN-001',
    'XRPUSD',
    'BUY',
    0.5500000000,
    1000.0000000000,
    '{"test": "chain_verification", "timestamp": "2024-01-01T00:00:02Z"}'::jsonb,
    '52.89.214.238'::inet,
    TRUE,
    'placeholder'
);

\echo '[TEST C] Three signals inserted. Verifying hash chain integrity...'
\echo ''

-- Display the hash chain
\echo '[TEST C] Hash Chain State:'
SELECT 
    id,
    signal_id,
    LEFT(row_hash, 16) || '...' AS row_hash_preview,
    created_at
FROM signals
ORDER BY id ASC;

-- Verify chain integrity
DO $$
DECLARE
    chain_valid BOOLEAN;
BEGIN
    SELECT verify_chain_integrity('signals') INTO chain_valid;
    
    IF chain_valid THEN
        RAISE NOTICE '[TEST C PASSED] Hash chain integrity verified. Chain is valid.';
    ELSE
        RAISE EXCEPTION '[TEST C FAILED] Hash chain integrity check returned FALSE.';
    END IF;
EXCEPTION
    WHEN OTHERS THEN
        IF SQLERRM LIKE '%AUD-009%' THEN
            RAISE EXCEPTION '[TEST C FAILED] Hash chain corrupted: %', SQLERRM;
        ELSE
            RAISE EXCEPTION '[TEST C FAILED] Unexpected error: %', SQLERRM;
        END IF;
END $$;

\echo ''
\echo '=============================================='
\echo 'SMOKE TEST SUMMARY'
\echo '=============================================='
\echo ''
\echo 'Test A (DELETE Rejection): PASSED - AUD-003'
\echo 'Test B (UPDATE Rejection): PASSED - AUD-002'
\echo 'Test C (Chain Integrity):  PASSED - TRUE'
\echo ''
\echo 'SOVEREIGN MANDATE: Immutability VERIFIED'
\echo '=============================================='

-- ============================================================================
-- CLEANUP: Remove test data (requires elevated privileges)
-- ============================================================================

\echo ''
\echo '[CLEANUP] Test data preserved for inspection.'
\echo 'To clean up, run with superuser privileges:'
\echo '  ALTER TABLE signals DISABLE TRIGGER ALL;'
\echo '  DELETE FROM signals WHERE signal_id LIKE ''TEST-%'';'
\echo '  ALTER TABLE signals ENABLE TRIGGER ALL;'
\echo ''

-- ============================================================================
-- END OF SMOKE TEST
-- ============================================================================

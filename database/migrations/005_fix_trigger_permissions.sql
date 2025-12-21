-- ============================================================================
-- Project Autonomous Alpha v1.3.2
-- Immutable Audit Log Schema - Trigger Permission Fix
-- ============================================================================
--
-- SOVEREIGN TIER INFRASTRUCTURE
-- Assurance Level: 100% Confidence (Mission-Critical)
--
-- ISSUE: DB-500 Error During Ingress Stress Test
-- ----------------------------------------------
-- The compute_row_hash() trigger function requires SELECT with FOR UPDATE
-- on audit tables to fetch the previous row's hash for chain computation.
-- 
-- The app_trading role has only SELECT, INSERT permissions (by design).
-- When the trigger executes in the context of app_trading, the FOR UPDATE
-- lock acquisition fails, resulting in DB-500 errors.
--
-- SOLUTION: SECURITY DEFINER
-- --------------------------
-- By marking compute_row_hash() as SECURITY DEFINER, the function executes
-- with the privileges of its owner (sovereign) rather than the calling user
-- (app_trading). This grants the trigger "Sovereign Authority" to:
--
--   1. Acquire FOR UPDATE locks on audit table rows
--   2. Read previous row_hash values for chain computation
--   3. Serialize concurrent inserts via advisory locks
--
-- WITHOUT granting the app_trading role any additional permissions.
--
-- SECURITY IMPLICATIONS
-- ---------------------
-- - The trigger function is tightly scoped (only reads row_hash, computes SHA-256)
-- - No user input is passed to dynamic SQL without format() escaping
-- - Advisory locks are transaction-scoped (pg_advisory_xact_lock)
-- - The function cannot be exploited to bypass immutability triggers
--
-- This follows the Principle of Least Privilege: the application role
-- remains restricted, while the trigger itself has elevated authority.
--
-- ============================================================================

-- Elevate compute_row_hash() to execute with owner (sovereign) privileges
ALTER FUNCTION compute_row_hash() SECURITY DEFINER;

COMMENT ON FUNCTION compute_row_hash() IS 
    'BEFORE INSERT trigger function that computes SHA-256 chain hash.
     Formula: row_hash = SHA-256(previous_row_hash || current_row_data)
     Uses genesis hash for first row. OVERWRITES any user-provided row_hash.
     Uses advisory lock to serialize concurrent inserts.
     
     SECURITY DEFINER: Executes with sovereign privileges to enable
     FOR UPDATE locks without granting app_trading elevated permissions.
     Fix for DB-500 error during Ingress Stress Test.
     
     Sovereign Mandate: Chain of Custody integrity.';

-- ============================================================================
-- VERIFICATION: Confirm SECURITY DEFINER is set
-- ============================================================================

DO $$
DECLARE
    func_security BOOLEAN;
BEGIN
    SELECT prosecdef INTO func_security
    FROM pg_proc
    WHERE proname = 'compute_row_hash';
    
    IF func_security = TRUE THEN
        RAISE NOTICE '============================================';
        RAISE NOTICE 'SECURITY DEFINER VERIFICATION: PASSED';
        RAISE NOTICE 'compute_row_hash() now executes with sovereign authority';
        RAISE NOTICE 'DB-500 fix applied successfully';
        RAISE NOTICE '============================================';
    ELSE
        RAISE EXCEPTION 'SECURITY DEFINER not set on compute_row_hash()';
    END IF;
END $$;

-- ============================================================================
-- END OF TRIGGER PERMISSION FIX
-- ============================================================================

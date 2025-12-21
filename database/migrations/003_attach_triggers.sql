-- ============================================================================
-- Project Autonomous Alpha v1.3.2
-- Immutable Audit Log Schema - Trigger Attachment
-- ============================================================================
--
-- SOVEREIGN TIER INFRASTRUCTURE
-- Assurance Level: 100% Confidence (Mission-Critical)
--
-- TRIGGER EXECUTION ORDER
-- -----------------------
-- PostgreSQL executes BEFORE triggers in alphabetical order by trigger name.
-- We use numeric prefixes to enforce correct execution order:
--
--   1. trg_01_validate_decimal  - Validate financial precision (AUD-001)
--   2. trg_02_compute_hash      - Compute chain of custody hash
--   3. trg_03_prevent_update    - Block UPDATE operations (AUD-00X)
--   4. trg_04_prevent_delete    - Block DELETE operations (AUD-00X)
--
-- IMMUTABILITY GUARANTEE
-- ----------------------
-- After this migration, all audit tables are protected by:
--   - Trigger-level rejection of UPDATE/DELETE
--   - Hash chain integrity verification
--   - Decimal precision validation
--
-- ============================================================================

-- ============================================================================
-- SIGNALS TABLE TRIGGERS
-- ============================================================================

-- 1. Decimal validation (BEFORE INSERT)
DROP TRIGGER IF EXISTS trg_01_validate_decimal_signals ON signals;
CREATE TRIGGER trg_01_validate_decimal_signals
    BEFORE INSERT ON signals
    FOR EACH ROW
    EXECUTE FUNCTION validate_decimal_input();

-- 2. Hash chain computation (BEFORE INSERT)
DROP TRIGGER IF EXISTS trg_02_compute_hash_signals ON signals;
CREATE TRIGGER trg_02_compute_hash_signals
    BEFORE INSERT ON signals
    FOR EACH ROW
    EXECUTE FUNCTION compute_row_hash();

-- 3. Prevent UPDATE (BEFORE UPDATE)
DROP TRIGGER IF EXISTS trg_03_prevent_update_signals ON signals;
CREATE TRIGGER trg_03_prevent_update_signals
    BEFORE UPDATE ON signals
    FOR EACH ROW
    EXECUTE FUNCTION prevent_update();

-- 4. Prevent DELETE (BEFORE DELETE)
DROP TRIGGER IF EXISTS trg_04_prevent_delete_signals ON signals;
CREATE TRIGGER trg_04_prevent_delete_signals
    BEFORE DELETE ON signals
    FOR EACH ROW
    EXECUTE FUNCTION prevent_delete();

COMMENT ON TRIGGER trg_01_validate_decimal_signals ON signals IS 
    'Validates DECIMAL precision before insert. Raises AUD-001 on float artifacts.';
COMMENT ON TRIGGER trg_02_compute_hash_signals ON signals IS 
    'Computes SHA-256 chain hash. Overwrites any user-provided row_hash.';
COMMENT ON TRIGGER trg_03_prevent_update_signals ON signals IS 
    'Blocks all UPDATE operations. Raises AUD-002.';
COMMENT ON TRIGGER trg_04_prevent_delete_signals ON signals IS 
    'Blocks all DELETE operations. Raises AUD-003.';

-- ============================================================================
-- AI_DEBATES TABLE TRIGGERS
-- ============================================================================

-- 1. Decimal validation (BEFORE INSERT)
DROP TRIGGER IF EXISTS trg_01_validate_decimal_ai_debates ON ai_debates;
CREATE TRIGGER trg_01_validate_decimal_ai_debates
    BEFORE INSERT ON ai_debates
    FOR EACH ROW
    EXECUTE FUNCTION validate_decimal_input();

-- 2. Hash chain computation (BEFORE INSERT)
DROP TRIGGER IF EXISTS trg_02_compute_hash_ai_debates ON ai_debates;
CREATE TRIGGER trg_02_compute_hash_ai_debates
    BEFORE INSERT ON ai_debates
    FOR EACH ROW
    EXECUTE FUNCTION compute_row_hash();

-- 3. Prevent UPDATE (BEFORE UPDATE)
DROP TRIGGER IF EXISTS trg_03_prevent_update_ai_debates ON ai_debates;
CREATE TRIGGER trg_03_prevent_update_ai_debates
    BEFORE UPDATE ON ai_debates
    FOR EACH ROW
    EXECUTE FUNCTION prevent_update();

-- 4. Prevent DELETE (BEFORE DELETE)
DROP TRIGGER IF EXISTS trg_04_prevent_delete_ai_debates ON ai_debates;
CREATE TRIGGER trg_04_prevent_delete_ai_debates
    BEFORE DELETE ON ai_debates
    FOR EACH ROW
    EXECUTE FUNCTION prevent_delete();

COMMENT ON TRIGGER trg_03_prevent_update_ai_debates ON ai_debates IS 
    'Blocks all UPDATE operations. Raises AUD-004.';
COMMENT ON TRIGGER trg_04_prevent_delete_ai_debates ON ai_debates IS 
    'Blocks all DELETE operations. Raises AUD-005.';

-- ============================================================================
-- ORDER_EXECUTION TABLE TRIGGERS
-- ============================================================================

-- 1. Decimal validation (BEFORE INSERT)
DROP TRIGGER IF EXISTS trg_01_validate_decimal_order_execution ON order_execution;
CREATE TRIGGER trg_01_validate_decimal_order_execution
    BEFORE INSERT ON order_execution
    FOR EACH ROW
    EXECUTE FUNCTION validate_decimal_input();

-- 2. Hash chain computation (BEFORE INSERT)
DROP TRIGGER IF EXISTS trg_02_compute_hash_order_execution ON order_execution;
CREATE TRIGGER trg_02_compute_hash_order_execution
    BEFORE INSERT ON order_execution
    FOR EACH ROW
    EXECUTE FUNCTION compute_row_hash();

-- 3. Prevent UPDATE (BEFORE UPDATE)
DROP TRIGGER IF EXISTS trg_03_prevent_update_order_execution ON order_execution;
CREATE TRIGGER trg_03_prevent_update_order_execution
    BEFORE UPDATE ON order_execution
    FOR EACH ROW
    EXECUTE FUNCTION prevent_update();

-- 4. Prevent DELETE (BEFORE DELETE)
DROP TRIGGER IF EXISTS trg_04_prevent_delete_order_execution ON order_execution;
CREATE TRIGGER trg_04_prevent_delete_order_execution
    BEFORE DELETE ON order_execution
    FOR EACH ROW
    EXECUTE FUNCTION prevent_delete();

COMMENT ON TRIGGER trg_03_prevent_update_order_execution ON order_execution IS 
    'Blocks all UPDATE operations. Raises AUD-006.';
COMMENT ON TRIGGER trg_04_prevent_delete_order_execution ON order_execution IS 
    'Blocks all DELETE operations. Raises AUD-007.';

-- ============================================================================
-- ORDER_EVENTS TABLE TRIGGERS
-- ============================================================================

-- 1. Decimal validation (BEFORE INSERT)
DROP TRIGGER IF EXISTS trg_01_validate_decimal_order_events ON order_events;
CREATE TRIGGER trg_01_validate_decimal_order_events
    BEFORE INSERT ON order_events
    FOR EACH ROW
    EXECUTE FUNCTION validate_decimal_input();

-- 2. Hash chain computation (BEFORE INSERT)
DROP TRIGGER IF EXISTS trg_02_compute_hash_order_events ON order_events;
CREATE TRIGGER trg_02_compute_hash_order_events
    BEFORE INSERT ON order_events
    FOR EACH ROW
    EXECUTE FUNCTION compute_row_hash();

-- 3. Prevent UPDATE (BEFORE UPDATE)
DROP TRIGGER IF EXISTS trg_03_prevent_update_order_events ON order_events;
CREATE TRIGGER trg_03_prevent_update_order_events
    BEFORE UPDATE ON order_events
    FOR EACH ROW
    EXECUTE FUNCTION prevent_update();

-- 4. Prevent DELETE (BEFORE DELETE)
DROP TRIGGER IF EXISTS trg_04_prevent_delete_order_events ON order_events;
CREATE TRIGGER trg_04_prevent_delete_order_events
    BEFORE DELETE ON order_events
    FOR EACH ROW
    EXECUTE FUNCTION prevent_delete();

COMMENT ON TRIGGER trg_03_prevent_update_order_events ON order_events IS 
    'Blocks all UPDATE operations. Raises AUD-006.';
COMMENT ON TRIGGER trg_04_prevent_delete_order_events ON order_events IS 
    'Blocks all DELETE operations. Raises AUD-007.';

-- ============================================================================
-- VERIFICATION: List all attached triggers
-- ============================================================================

DO $$
DECLARE
    trigger_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO trigger_count
    FROM information_schema.triggers
    WHERE trigger_schema = 'public'
      AND event_object_table IN ('signals', 'ai_debates', 'order_execution', 'order_events');
    
    RAISE NOTICE 'Trigger attachment complete. Total triggers attached: %', trigger_count;
    
    IF trigger_count != 16 THEN
        RAISE EXCEPTION 'Expected 16 triggers (4 per table × 4 tables), found %. Deployment failed.', trigger_count;
    END IF;
END $$;

-- ============================================================================
-- END OF TRIGGER ATTACHMENT
-- ============================================================================

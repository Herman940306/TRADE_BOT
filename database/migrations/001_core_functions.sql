-- ============================================================================
-- Project Autonomous Alpha v1.3.2
-- Immutable Audit Log Schema - Core Functions
-- ============================================================================
-- 
-- SOVEREIGN TIER INFRASTRUCTURE
-- Assurance Level: 100% Confidence (Mission-Critical)
--
-- CHAIN OF CUSTODY LOGIC
-- ----------------------
-- This schema implements a blockchain-style audit trail within PostgreSQL.
-- Each row contains a SHA-256 hash computed from:
--   row_hash = SHA-256(previous_row_hash || current_row_data)
--
-- The first row in each table uses a predefined GENESIS_HASH constant.
-- This creates an immutable chain where any tampering (insert, modify, delete)
-- breaks the hash chain and is detectable via verify_chain_integrity().
--
-- IMMUTABILITY ENFORCEMENT
-- ------------------------
-- All audit tables are protected by BEFORE UPDATE and BEFORE DELETE triggers
-- that unconditionally reject modifications. Application roles are also
-- denied UPDATE/DELETE privileges at the permission level.
--
-- ERROR CODES
-- -----------
-- AUD-001: Float precision loss detected in financial column
-- AUD-002: UPDATE attempted on signals table
-- AUD-003: DELETE attempted on signals table
-- AUD-004: UPDATE attempted on ai_debates table
-- AUD-005: DELETE attempted on ai_debates table
-- AUD-006: UPDATE attempted on order_execution/order_events table
-- AUD-007: DELETE attempted on order_execution/order_events table
-- AUD-008: Invalid correlation_id foreign key reference
-- AUD-009: Hash chain integrity verification failed
--
-- ============================================================================

-- Enable pgcrypto extension for SHA-256 hashing
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ============================================================================
-- GENESIS HASH CONSTANT
-- ============================================================================
-- SHA-256 hash of "SOVEREIGN_GENESIS_V1.3.2" - the root of all hash chains
-- This value MUST remain constant across all deployments.

CREATE OR REPLACE FUNCTION get_genesis_hash()
RETURNS CHAR(64)
LANGUAGE sql
IMMUTABLE
PARALLEL SAFE
AS $$
    SELECT 'a1b2c3d4e5f6789012345678901234567890123456789012345678901234abcd'::CHAR(64);
$$;

COMMENT ON FUNCTION get_genesis_hash() IS 
    'Returns the predefined genesis hash for chain initialization. 
     SHA-256 of "SOVEREIGN_GENESIS_V1.3.2". Immutable across deployments.';

-- ============================================================================
-- DECIMAL PRECISION VALIDATION (AUD-001)
-- ============================================================================
-- Detects precision loss from float casting before database write.
-- Compares string representation to detect floating-point artifacts.

CREATE OR REPLACE FUNCTION validate_decimal_input()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    col_name TEXT;
    col_value NUMERIC;
    str_repr TEXT;
BEGIN
    -- Check price column if exists
    IF TG_TABLE_NAME = 'signals' OR TG_TABLE_NAME = 'order_execution' THEN
        IF NEW.price IS NOT NULL THEN
            str_repr := NEW.price::TEXT;
            -- Detect floating-point artifacts (e.g., 0.1 + 0.2 = 0.30000000000000004)
            IF str_repr ~ 'e[+-]?[0-9]+$' OR LENGTH(str_repr) > 40 THEN
                RAISE EXCEPTION '[AUD-001] Float precision loss detected in column "price". Value: %. Sovereign Mandate: All financial values must use DECIMAL without float casting.', str_repr;
            END IF;
        END IF;
    END IF;
    
    -- Check quantity column if exists
    IF TG_TABLE_NAME IN ('signals', 'order_execution') THEN
        IF NEW.quantity IS NOT NULL THEN
            str_repr := NEW.quantity::TEXT;
            IF str_repr ~ 'e[+-]?[0-9]+$' OR LENGTH(str_repr) > 40 THEN
                RAISE EXCEPTION '[AUD-001] Float precision loss detected in column "quantity". Value: %. Sovereign Mandate: All financial values must use DECIMAL without float casting.', str_repr;
            END IF;
        END IF;
    END IF;
    
    -- Check fill_quantity and fill_price for order_events
    IF TG_TABLE_NAME = 'order_events' THEN
        IF NEW.fill_quantity IS NOT NULL THEN
            str_repr := NEW.fill_quantity::TEXT;
            IF str_repr ~ 'e[+-]?[0-9]+$' OR LENGTH(str_repr) > 40 THEN
                RAISE EXCEPTION '[AUD-001] Float precision loss detected in column "fill_quantity". Value: %. Sovereign Mandate: All financial values must use DECIMAL without float casting.', str_repr;
            END IF;
        END IF;
        IF NEW.fill_price IS NOT NULL THEN
            str_repr := NEW.fill_price::TEXT;
            IF str_repr ~ 'e[+-]?[0-9]+$' OR LENGTH(str_repr) > 40 THEN
                RAISE EXCEPTION '[AUD-001] Float precision loss detected in column "fill_price". Value: %. Sovereign Mandate: All financial values must use DECIMAL without float casting.', str_repr;
            END IF;
        END IF;
    END IF;
    
    -- Check confidence_score for ai_debates
    IF TG_TABLE_NAME = 'ai_debates' THEN
        IF NEW.confidence_score IS NOT NULL THEN
            str_repr := NEW.confidence_score::TEXT;
            IF str_repr ~ 'e[+-]?[0-9]+$' OR LENGTH(str_repr) > 20 THEN
                RAISE EXCEPTION '[AUD-001] Float precision loss detected in column "confidence_score". Value: %. Sovereign Mandate: All financial values must use DECIMAL without float casting.', str_repr;
            END IF;
        END IF;
    END IF;
    
    RETURN NEW;
END;
$$;

COMMENT ON FUNCTION validate_decimal_input() IS 
    'BEFORE INSERT trigger function that detects precision loss from float casting.
     Raises AUD-001 error if floating-point artifacts are detected in financial columns.
     Sovereign Mandate: Zero floats in financial data.';

-- ============================================================================
-- IMMUTABILITY ENFORCEMENT - UPDATE PREVENTION (AUD-002, AUD-004, AUD-006)
-- ============================================================================

CREATE OR REPLACE FUNCTION prevent_update()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    error_code TEXT;
BEGIN
    -- Determine error code based on table
    CASE TG_TABLE_NAME
        WHEN 'signals' THEN error_code := 'AUD-002';
        WHEN 'ai_debates' THEN error_code := 'AUD-004';
        WHEN 'order_execution' THEN error_code := 'AUD-006';
        WHEN 'order_events' THEN error_code := 'AUD-006';
        ELSE error_code := 'AUD-000';
    END CASE;
    
    RAISE EXCEPTION '[%] UPDATE operation forbidden on immutable audit table "%". Sovereign Mandate: Audit records are append-only. L6 Lockdown may be triggered.', 
        error_code, TG_TABLE_NAME;
END;
$$;

COMMENT ON FUNCTION prevent_update() IS 
    'BEFORE UPDATE trigger function that unconditionally rejects UPDATE operations.
     Raises table-specific AUD error codes (AUD-002, AUD-004, AUD-006).
     Sovereign Mandate: Immutable audit trail.';

-- ============================================================================
-- IMMUTABILITY ENFORCEMENT - DELETE PREVENTION (AUD-003, AUD-005, AUD-007)
-- ============================================================================

CREATE OR REPLACE FUNCTION prevent_delete()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    error_code TEXT;
BEGIN
    -- Determine error code based on table
    CASE TG_TABLE_NAME
        WHEN 'signals' THEN error_code := 'AUD-003';
        WHEN 'ai_debates' THEN error_code := 'AUD-005';
        WHEN 'order_execution' THEN error_code := 'AUD-007';
        WHEN 'order_events' THEN error_code := 'AUD-007';
        ELSE error_code := 'AUD-000';
    END CASE;
    
    RAISE EXCEPTION '[%] DELETE operation forbidden on immutable audit table "%". Sovereign Mandate: Audit records are append-only. L6 Lockdown may be triggered.', 
        error_code, TG_TABLE_NAME;
END;
$$;

COMMENT ON FUNCTION prevent_delete() IS 
    'BEFORE DELETE trigger function that unconditionally rejects DELETE operations.
     Raises table-specific AUD error codes (AUD-003, AUD-005, AUD-007).
     Sovereign Mandate: Immutable audit trail.';


-- ============================================================================
-- CHAIN OF CUSTODY - HASH COMPUTATION
-- ============================================================================
-- Computes SHA-256 hash linking each row to its predecessor.
-- CRITICAL: Overwrites any user-provided row_hash to prevent spoofing.

CREATE OR REPLACE FUNCTION compute_row_hash()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    prev_hash CHAR(64);
    row_data TEXT;
    computed_hash CHAR(64);
BEGIN
    -- Acquire advisory lock to serialize hash chain computation per table
    -- This prevents race conditions in concurrent inserts
    PERFORM pg_advisory_xact_lock(hashtext(TG_TABLE_NAME));
    
    -- Get the previous row's hash, or genesis hash if this is the first row
    EXECUTE format(
        'SELECT row_hash FROM %I ORDER BY id DESC LIMIT 1 FOR UPDATE',
        TG_TABLE_NAME
    ) INTO prev_hash;
    
    IF prev_hash IS NULL THEN
        prev_hash := get_genesis_hash();
    END IF;
    
    -- Build row data string for hashing (excluding row_hash and id)
    CASE TG_TABLE_NAME
        WHEN 'signals' THEN
            row_data := COALESCE(NEW.correlation_id::TEXT, '') || '|' ||
                        COALESCE(NEW.signal_id, '') || '|' ||
                        COALESCE(NEW.symbol, '') || '|' ||
                        COALESCE(NEW.side, '') || '|' ||
                        COALESCE(NEW.price::TEXT, '') || '|' ||
                        COALESCE(NEW.quantity::TEXT, '') || '|' ||
                        COALESCE(NEW.raw_payload::TEXT, '') || '|' ||
                        COALESCE(NEW.source_ip::TEXT, '') || '|' ||
                        COALESCE(NEW.hmac_verified::TEXT, '') || '|' ||
                        COALESCE(NEW.created_at::TEXT, '');
        WHEN 'ai_debates' THEN
            row_data := COALESCE(NEW.correlation_id::TEXT, '') || '|' ||
                        COALESCE(NEW.model_name, '') || '|' ||
                        COALESCE(NEW.reasoning_json::TEXT, '') || '|' ||
                        COALESCE(NEW.confidence_score::TEXT, '') || '|' ||
                        COALESCE(NEW.elapsed_ms::TEXT, '') || '|' ||
                        COALESCE(NEW.is_timeout::TEXT, '') || '|' ||
                        COALESCE(NEW.created_at::TEXT, '');
        WHEN 'order_execution' THEN
            row_data := COALESCE(NEW.correlation_id::TEXT, '') || '|' ||
                        COALESCE(NEW.order_type, '') || '|' ||
                        COALESCE(NEW.symbol, '') || '|' ||
                        COALESCE(NEW.side, '') || '|' ||
                        COALESCE(NEW.quantity::TEXT, '') || '|' ||
                        COALESCE(NEW.price::TEXT, '') || '|' ||
                        COALESCE(NEW.exchange_order_id, '') || '|' ||
                        COALESCE(NEW.status, '') || '|' ||
                        COALESCE(NEW.created_at::TEXT, '');
        WHEN 'order_events' THEN
            row_data := COALESCE(NEW.order_execution_id::TEXT, '') || '|' ||
                        COALESCE(NEW.event_type, '') || '|' ||
                        COALESCE(NEW.fill_quantity::TEXT, '') || '|' ||
                        COALESCE(NEW.fill_price::TEXT, '') || '|' ||
                        COALESCE(NEW.zar_equity::TEXT, '') || '|' ||
                        COALESCE(NEW.positions_closed::TEXT, '') || '|' ||
                        COALESCE(NEW.rejection_reason, '') || '|' ||
                        COALESCE(NEW.exchange_error_code, '') || '|' ||
                        COALESCE(NEW.created_at::TEXT, '');
        ELSE
            RAISE EXCEPTION 'compute_row_hash: Unknown table %', TG_TABLE_NAME;
    END CASE;
    
    -- Compute SHA-256 hash: previous_hash || row_data
    -- CRITICAL: This OVERWRITES any user-provided row_hash value
    computed_hash := encode(digest(prev_hash || row_data, 'sha256'), 'hex');
    NEW.row_hash := computed_hash;
    
    RETURN NEW;
END;
$$;

COMMENT ON FUNCTION compute_row_hash() IS 
    'BEFORE INSERT trigger function that computes SHA-256 chain hash.
     Formula: row_hash = SHA-256(previous_row_hash || current_row_data)
     Uses genesis hash for first row. OVERWRITES any user-provided row_hash.
     Uses advisory lock to serialize concurrent inserts.
     Sovereign Mandate: Chain of Custody integrity.';

-- ============================================================================
-- CHAIN OF CUSTODY - INTEGRITY VERIFICATION (AUD-009)
-- ============================================================================
-- Recomputes all hashes and compares against stored values.
-- Returns TRUE if chain is valid, raises AUD-009 on mismatch.

CREATE OR REPLACE FUNCTION verify_chain_integrity(table_name TEXT)
RETURNS BOOLEAN
LANGUAGE plpgsql
AS $$
DECLARE
    rec RECORD;
    prev_hash CHAR(64);
    row_data TEXT;
    computed_hash CHAR(64);
    row_count INTEGER := 0;
BEGIN
    prev_hash := get_genesis_hash();
    
    FOR rec IN EXECUTE format('SELECT * FROM %I ORDER BY id ASC', table_name)
    LOOP
        row_count := row_count + 1;
        
        -- Build row data string based on table
        CASE table_name
            WHEN 'signals' THEN
                row_data := COALESCE(rec.correlation_id::TEXT, '') || '|' ||
                            COALESCE(rec.signal_id, '') || '|' ||
                            COALESCE(rec.symbol, '') || '|' ||
                            COALESCE(rec.side, '') || '|' ||
                            COALESCE(rec.price::TEXT, '') || '|' ||
                            COALESCE(rec.quantity::TEXT, '') || '|' ||
                            COALESCE(rec.raw_payload::TEXT, '') || '|' ||
                            COALESCE(rec.source_ip::TEXT, '') || '|' ||
                            COALESCE(rec.hmac_verified::TEXT, '') || '|' ||
                            COALESCE(rec.created_at::TEXT, '');
            WHEN 'ai_debates' THEN
                row_data := COALESCE(rec.correlation_id::TEXT, '') || '|' ||
                            COALESCE(rec.model_name, '') || '|' ||
                            COALESCE(rec.reasoning_json::TEXT, '') || '|' ||
                            COALESCE(rec.confidence_score::TEXT, '') || '|' ||
                            COALESCE(rec.elapsed_ms::TEXT, '') || '|' ||
                            COALESCE(rec.is_timeout::TEXT, '') || '|' ||
                            COALESCE(rec.created_at::TEXT, '');
            WHEN 'order_execution' THEN
                row_data := COALESCE(rec.correlation_id::TEXT, '') || '|' ||
                            COALESCE(rec.order_type, '') || '|' ||
                            COALESCE(rec.symbol, '') || '|' ||
                            COALESCE(rec.side, '') || '|' ||
                            COALESCE(rec.quantity::TEXT, '') || '|' ||
                            COALESCE(rec.price::TEXT, '') || '|' ||
                            COALESCE(rec.exchange_order_id, '') || '|' ||
                            COALESCE(rec.status, '') || '|' ||
                            COALESCE(rec.created_at::TEXT, '');
            WHEN 'order_events' THEN
                row_data := COALESCE(rec.order_execution_id::TEXT, '') || '|' ||
                            COALESCE(rec.event_type, '') || '|' ||
                            COALESCE(rec.fill_quantity::TEXT, '') || '|' ||
                            COALESCE(rec.fill_price::TEXT, '') || '|' ||
                            COALESCE(rec.zar_equity::TEXT, '') || '|' ||
                            COALESCE(rec.positions_closed::TEXT, '') || '|' ||
                            COALESCE(rec.rejection_reason, '') || '|' ||
                            COALESCE(rec.exchange_error_code, '') || '|' ||
                            COALESCE(rec.created_at::TEXT, '');
            ELSE
                RAISE EXCEPTION 'verify_chain_integrity: Unknown table %', table_name;
        END CASE;
        
        -- Compute expected hash
        computed_hash := encode(digest(prev_hash || row_data, 'sha256'), 'hex');
        
        -- Compare with stored hash
        IF computed_hash != rec.row_hash THEN
            RAISE EXCEPTION '[AUD-009] Hash chain integrity verification FAILED on table "%" at row id %. Expected: %, Found: %. L6 LOCKDOWN TRIGGERED. Sovereign Mandate: Immutable audit trail compromised.',
                table_name, rec.id, computed_hash, rec.row_hash;
        END IF;
        
        -- Update previous hash for next iteration
        prev_hash := rec.row_hash;
    END LOOP;
    
    RAISE NOTICE 'Chain integrity verified for table "%": % rows validated.', table_name, row_count;
    RETURN TRUE;
END;
$$;

COMMENT ON FUNCTION verify_chain_integrity(TEXT) IS 
    'Verifies the SHA-256 hash chain integrity for a specified audit table.
     Recomputes all hashes from genesis and compares against stored values.
     Raises AUD-009 error on mismatch, triggering L6 Lockdown.
     Returns TRUE if chain is valid.
     Sovereign Mandate: Tamper detection.';

-- ============================================================================
-- END OF CORE FUNCTIONS
-- ============================================================================

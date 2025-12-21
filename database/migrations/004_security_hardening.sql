-- ============================================================================
-- Project Autonomous Alpha v1.3.2
-- Immutable Audit Log Schema - Security Hardening
-- ============================================================================
--
-- SOVEREIGN TIER INFRASTRUCTURE
-- Assurance Level: 100% Confidence (Mission-Critical)
--
-- SECURITY MODEL
-- --------------
-- This migration implements defense-in-depth for the audit tables:
--
--   Layer 1: Trigger-based rejection (001_core_functions.sql)
--   Layer 2: Permission-based denial (this file)
--   Layer 3: Hash chain tamper detection (verify_chain_integrity)
--
-- APPLICATION ROLE: app_trading
-- -----------------------------
-- The application connects using this role, which has:
--   - SELECT on all audit tables (read audit history)
--   - INSERT on all audit tables (append new records)
--   - NO UPDATE permission (immutability)
--   - NO DELETE permission (immutability)
--
-- ============================================================================

-- ============================================================================
-- CREATE APPLICATION ROLE
-- ============================================================================

-- Create the application role if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_trading') THEN
        CREATE ROLE app_trading WITH LOGIN PASSWORD 'trading_app_2024';
        RAISE NOTICE 'Created role: app_trading';
    ELSE
        RAISE NOTICE 'Role app_trading already exists';
    END IF;
END $$;

-- ============================================================================
-- GRANT MINIMAL REQUIRED PERMISSIONS
-- ============================================================================

-- Grant CONNECT to database
GRANT CONNECT ON DATABASE autonomous_alpha TO app_trading;

-- Grant USAGE on public schema
GRANT USAGE ON SCHEMA public TO app_trading;

-- Grant SELECT and INSERT only on audit tables
GRANT SELECT, INSERT ON signals TO app_trading;
GRANT SELECT, INSERT ON ai_debates TO app_trading;
GRANT SELECT, INSERT ON order_execution TO app_trading;
GRANT SELECT, INSERT ON order_events TO app_trading;

-- Grant USAGE on sequences (required for BIGSERIAL inserts)
GRANT USAGE, SELECT ON SEQUENCE signals_id_seq TO app_trading;
GRANT USAGE, SELECT ON SEQUENCE ai_debates_id_seq TO app_trading;
GRANT USAGE, SELECT ON SEQUENCE order_execution_id_seq TO app_trading;
GRANT USAGE, SELECT ON SEQUENCE order_events_id_seq TO app_trading;

-- ============================================================================
-- REVOKE DANGEROUS PERMISSIONS (Defense in Depth)
-- ============================================================================

-- Explicitly revoke UPDATE and DELETE (even though not granted)
-- This ensures no inheritance from PUBLIC or future grants
REVOKE UPDATE, DELETE ON signals FROM app_trading;
REVOKE UPDATE, DELETE ON ai_debates FROM app_trading;
REVOKE UPDATE, DELETE ON order_execution FROM app_trading;
REVOKE UPDATE, DELETE ON order_events FROM app_trading;

-- Revoke from PUBLIC as well (belt and suspenders)
REVOKE UPDATE, DELETE ON signals FROM PUBLIC;
REVOKE UPDATE, DELETE ON ai_debates FROM PUBLIC;
REVOKE UPDATE, DELETE ON order_execution FROM PUBLIC;
REVOKE UPDATE, DELETE ON order_events FROM PUBLIC;

-- ============================================================================
-- GRANT ACCESS TO UTILITY FUNCTIONS
-- ============================================================================

-- Allow app to verify chain integrity (read-only operation)
GRANT EXECUTE ON FUNCTION verify_chain_integrity(TEXT) TO app_trading;
GRANT EXECUTE ON FUNCTION get_genesis_hash() TO app_trading;

-- ============================================================================
-- VERIFICATION: Display permission summary
-- ============================================================================

DO $$
DECLARE
    perm_record RECORD;
BEGIN
    RAISE NOTICE '============================================';
    RAISE NOTICE 'PERMISSION SUMMARY FOR app_trading';
    RAISE NOTICE '============================================';
    
    FOR perm_record IN
        SELECT 
            table_name,
            string_agg(privilege_type, ', ' ORDER BY privilege_type) as privileges
        FROM information_schema.table_privileges
        WHERE grantee = 'app_trading'
          AND table_schema = 'public'
          AND table_name IN ('signals', 'ai_debates', 'order_execution', 'order_events')
        GROUP BY table_name
        ORDER BY table_name
    LOOP
        RAISE NOTICE '  %: %', perm_record.table_name, perm_record.privileges;
    END LOOP;
    
    RAISE NOTICE '============================================';
    RAISE NOTICE 'Sovereign Mandate: UPDATE/DELETE REVOKED';
    RAISE NOTICE '============================================';
END $$;

-- ============================================================================
-- END OF SECURITY HARDENING - PERMISSIONS
-- ============================================================================


-- ============================================================================
-- VIEW: vw_trade_audit_full
-- ============================================================================
-- Comprehensive view joining all audit tables via correlation_id.
-- Provides single-row access to complete trade decision chain:
--   Signal → AI Reasoning → Order Execution → Order Events (including ZAR equity)
--
-- USE CASES:
--   1. Compliance audit: Trace any order back to originating signal
--   2. AI review: Examine model reasoning for specific trades
--   3. Risk analysis: Review KILL_SWITCH events with ZAR equity at trigger
--   4. Reconciliation: Match internal records against exchange data
--
-- ============================================================================

CREATE OR REPLACE VIEW vw_trade_audit_full AS
SELECT
    -- Signal identification
    s.correlation_id,
    s.signal_id,
    s.created_at AS signal_timestamp,
    
    -- Signal trade parameters
    s.symbol,
    s.side AS signal_side,
    s.price AS signal_price,
    s.quantity AS signal_quantity,
    s.raw_payload AS signal_raw_payload,
    
    -- Signal security metadata
    s.source_ip,
    s.hmac_verified,
    
    -- AI Deliberation: DeepSeek-R1 (The Critic)
    deepseek.reasoning_json AS deepseek_reasoning,
    deepseek.confidence_score AS deepseek_confidence,
    deepseek.elapsed_ms AS deepseek_elapsed_ms,
    deepseek.is_timeout AS deepseek_timeout,
    
    -- AI Deliberation: Llama 3.1 (The Context)
    llama.reasoning_json AS llama_reasoning,
    llama.confidence_score AS llama_confidence,
    llama.elapsed_ms AS llama_elapsed_ms,
    llama.is_timeout AS llama_timeout,
    
    -- Combined AI confidence (minimum of both models)
    LEAST(
        COALESCE(deepseek.confidence_score, 0),
        COALESCE(llama.confidence_score, 0)
    ) AS combined_ai_confidence,
    
    -- Order Execution details
    oe.id AS order_id,
    oe.order_type,
    oe.side AS order_side,
    oe.quantity AS order_quantity,
    oe.price AS order_price,
    oe.exchange_order_id,
    oe.status AS order_status,
    oe.created_at AS order_timestamp,
    
    -- Latest Order Event (most recent fill/rejection/etc)
    latest_event.event_type AS latest_event_type,
    latest_event.fill_quantity,
    latest_event.fill_price,
    latest_event.rejection_reason,
    latest_event.exchange_error_code,
    latest_event.created_at AS event_timestamp,
    
    -- ZAR Equity tracking (critical for KILL_SWITCH audit)
    latest_event.zar_equity,
    latest_event.positions_closed,
    
    -- Chain of custody hashes (for integrity verification)
    s.row_hash AS signal_hash,
    oe.row_hash AS order_hash

FROM signals s

-- Join AI debates (DeepSeek-R1)
LEFT JOIN ai_debates deepseek 
    ON s.correlation_id = deepseek.correlation_id 
    AND deepseek.model_name = 'deepseek-r1'

-- Join AI debates (Llama 3.1)
LEFT JOIN ai_debates llama 
    ON s.correlation_id = llama.correlation_id 
    AND llama.model_name = 'llama-3.1'

-- Join Order Execution
LEFT JOIN order_execution oe 
    ON s.correlation_id = oe.correlation_id

-- Join Latest Order Event (subquery for most recent event per order)
LEFT JOIN LATERAL (
    SELECT 
        ev.event_type,
        ev.fill_quantity,
        ev.fill_price,
        ev.zar_equity,
        ev.positions_closed,
        ev.rejection_reason,
        ev.exchange_error_code,
        ev.created_at
    FROM order_events ev
    WHERE ev.order_execution_id = oe.id
    ORDER BY ev.created_at DESC
    LIMIT 1
) latest_event ON TRUE

ORDER BY s.created_at DESC;

COMMENT ON VIEW vw_trade_audit_full IS 
    'Comprehensive audit view joining signals, AI debates, orders, and events.
     Provides single-row access to complete trade decision chain.
     Includes ZAR equity tracking for KILL_SWITCH audit.
     Sovereign Mandate: Full traceability via correlation_id.';

-- Grant SELECT on view to application role
GRANT SELECT ON vw_trade_audit_full TO app_trading;

-- ============================================================================
-- VIEW: vw_kill_switch_events
-- ============================================================================
-- Specialized view for KILL_SWITCH audit trail.
-- Shows all emergency position closures with ZAR equity at trigger time.

CREATE OR REPLACE VIEW vw_kill_switch_events AS
SELECT
    s.correlation_id,
    s.signal_id,
    s.symbol,
    oe.exchange_order_id,
    ev.event_type,
    ev.zar_equity,
    ev.positions_closed,
    ev.rejection_reason,
    ev.created_at AS kill_switch_timestamp,
    s.created_at AS original_signal_timestamp
FROM order_events ev
JOIN order_execution oe ON ev.order_execution_id = oe.id
JOIN signals s ON oe.correlation_id = s.correlation_id
WHERE ev.event_type = 'KILL_SWITCH'
ORDER BY ev.created_at DESC;

COMMENT ON VIEW vw_kill_switch_events IS 
    'Audit view for KILL_SWITCH events.
     Shows ZAR equity at trigger time and all positions closed.
     Critical for L6 Safety compliance review.
     Sovereign Mandate: ZAR Floor monitoring.';

GRANT SELECT ON vw_kill_switch_events TO app_trading;

-- ============================================================================
-- END OF SECURITY HARDENING
-- ============================================================================

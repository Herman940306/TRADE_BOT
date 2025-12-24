-- ============================================================================
-- Project Autonomous Alpha v1.3.2
-- AI Debate Ledger Schema Update - Bull/Bear Debate Protocol
-- ============================================================================
--
-- SOVEREIGN TIER INFRASTRUCTURE
-- Assurance Level: 100% Confidence (Mission-Critical)
--
-- PURPOSE
-- -------
-- This migration updates the ai_debates table to support the Bull/Bear
-- debate protocol with zero-cost AI models. Each trade signal is evaluated
-- by two opposing AI perspectives before a consensus verdict is reached.
--
-- ZERO-COST AI MODELS
-- -------------------
-- Bull AI: google/gemini-2.0-flash-exp:free
-- Bear AI: mistralai/mistral-7b-instruct:free
--
-- FINANCIAL GUARDRAIL
-- -------------------
-- final_verdict defaults to FALSE (Do Not Trade).
-- Only unanimous APPROVED from both models sets verdict to TRUE.
--
-- ============================================================================

-- ============================================================================
-- DROP EXISTING TABLE AND RECREATE WITH NEW SCHEMA
-- ============================================================================

-- First, drop triggers to allow table modification
DROP TRIGGER IF EXISTS trg_01_validate_decimal_ai_debates ON ai_debates;
DROP TRIGGER IF EXISTS trg_02_compute_hash_ai_debates ON ai_debates;
DROP TRIGGER IF EXISTS trg_03_prevent_update_ai_debates ON ai_debates;
DROP TRIGGER IF EXISTS trg_04_prevent_delete_ai_debates ON ai_debates;

-- Drop the old table (no production data yet)
DROP TABLE IF EXISTS ai_debates CASCADE;

-- ============================================================================
-- CREATE AI DEBATES TABLE (Bull/Bear Protocol)
-- ============================================================================

CREATE TABLE ai_debates (
    id BIGSERIAL PRIMARY KEY,
    correlation_id UUID NOT NULL,
    bull_reasoning TEXT NOT NULL,
    bear_reasoning TEXT NOT NULL,
    consensus_score INT NOT NULL DEFAULT 0,
    final_verdict BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    row_hash CHAR(64) NOT NULL,
    CONSTRAINT ai_debates_correlation_id_fk 
        FOREIGN KEY (correlation_id) 
        REFERENCES signals(correlation_id)
        ON DELETE RESTRICT,
    CONSTRAINT ai_debates_consensus_score_check 
        CHECK (consensus_score >= 0 AND consensus_score <= 100)
);


-- ============================================================================
-- INDEXES
-- ============================================================================

CREATE INDEX idx_ai_debates_correlation_id ON ai_debates(correlation_id);
CREATE INDEX idx_ai_debates_created_at ON ai_debates(created_at DESC);
CREATE INDEX idx_ai_debates_final_verdict ON ai_debates(final_verdict);
CREATE INDEX idx_ai_debates_consensus_score ON ai_debates(consensus_score);

-- ============================================================================
-- UPDATE compute_row_hash() FOR NEW SCHEMA
-- ============================================================================

CREATE OR REPLACE FUNCTION compute_row_hash()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
AS $func$
DECLARE
    prev_hash CHAR(64);
    row_data TEXT;
    computed_hash CHAR(64);
BEGIN
    PERFORM pg_advisory_xact_lock(hashtext(TG_TABLE_NAME));
    
    EXECUTE format(
        'SELECT row_hash FROM %I ORDER BY id DESC LIMIT 1 FOR UPDATE',
        TG_TABLE_NAME
    ) INTO prev_hash;
    
    IF prev_hash IS NULL THEN
        prev_hash := get_genesis_hash();
    END IF;
    
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
                        COALESCE(NEW.bull_reasoning, '') || '|' ||
                        COALESCE(NEW.bear_reasoning, '') || '|' ||
                        COALESCE(NEW.consensus_score::TEXT, '') || '|' ||
                        COALESCE(NEW.final_verdict::TEXT, '') || '|' ||
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
        WHEN 'risk_assessments' THEN
            row_data := COALESCE(NEW.correlation_id::TEXT, '') || '|' ||
                        COALESCE(NEW.equity::TEXT, '') || '|' ||
                        COALESCE(NEW.signal_price::TEXT, '') || '|' ||
                        COALESCE(NEW.risk_percentage::TEXT, '') || '|' ||
                        COALESCE(NEW.risk_amount_zar::TEXT, '') || '|' ||
                        COALESCE(NEW.calculated_quantity::TEXT, '') || '|' ||
                        COALESCE(NEW.status, '') || '|' ||
                        COALESCE(NEW.rejection_reason, '') || '|' ||
                        COALESCE(NEW.created_at::TEXT, '');
        ELSE
            RAISE EXCEPTION 'compute_row_hash: Unknown table %', TG_TABLE_NAME;
    END CASE;
    
    computed_hash := encode(digest(prev_hash || row_data, 'sha256'), 'hex');
    NEW.row_hash := computed_hash;
    
    RETURN NEW;
END;
$func$;


-- ============================================================================
-- ATTACH IMMUTABILITY TRIGGERS
-- ============================================================================

CREATE TRIGGER trg_ai_debates_compute_hash
    BEFORE INSERT ON ai_debates
    FOR EACH ROW
    EXECUTE FUNCTION compute_row_hash();

CREATE TRIGGER trg_ai_debates_prevent_update
    BEFORE UPDATE ON ai_debates
    FOR EACH ROW
    EXECUTE FUNCTION prevent_update();

CREATE TRIGGER trg_ai_debates_prevent_delete
    BEFORE DELETE ON ai_debates
    FOR EACH ROW
    EXECUTE FUNCTION prevent_delete();

-- ============================================================================
-- GRANT PERMISSIONS TO app_trading
-- ============================================================================

GRANT SELECT, INSERT ON ai_debates TO app_trading;
GRANT USAGE, SELECT ON SEQUENCE ai_debates_id_seq TO app_trading;

REVOKE UPDATE, DELETE ON ai_debates FROM app_trading;
REVOKE UPDATE, DELETE ON ai_debates FROM PUBLIC;

-- ============================================================================
-- VERIFICATION
-- ============================================================================

DO $verify$
BEGIN
    RAISE NOTICE '============================================';
    RAISE NOTICE 'AI DEBATES LEDGER (Bull/Bear Protocol)';
    RAISE NOTICE 'Schema: bull_reasoning, bear_reasoning,';
    RAISE NOTICE '        consensus_score, final_verdict';
    RAISE NOTICE 'Immutability triggers attached';
    RAISE NOTICE 'Hash chain enabled';
    RAISE NOTICE 'FINANCIAL GUARDRAIL: Default FALSE';
    RAISE NOTICE 'ZERO-COST MODELS: Gemini Flash + Mistral 7B';
    RAISE NOTICE '============================================';
END $verify$;

-- ============================================================================
-- END OF AI DEBATE LEDGER
-- ============================================================================

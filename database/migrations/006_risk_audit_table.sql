-- ============================================================================
-- Project Autonomous Alpha v1.3.2
-- Immutable Audit Log Schema - Risk Assessments Table
-- ============================================================================
--
-- SOVEREIGN TIER INFRASTRUCTURE
-- Assurance Level: 100% Confidence (Mission-Critical)
--
-- PURPOSE
-- -------
-- This table stores risk assessment calculations from the Sovereign Brain.
-- Each signal processed through the webhook receives a risk assessment that
-- determines position sizing based on the Sovereign Risk Formula.
--
-- THE SOVEREIGN RISK FORMULA
-- --------------------------
-- RiskAmount = Equity × 0.01 (Fixed 1% risk per trade)
-- PositionSize = RiskAmount / SignalPrice
--
-- AUDIT TRAIL
-- -----------
-- Every risk calculation is immutable and linked to the originating signal
-- via correlation_id. This enables full traceability from signal ingestion
-- through risk assessment to order execution.
--
-- ============================================================================

-- ============================================================================
-- CREATE RISK ASSESSMENTS TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS risk_assessments (
    -- Primary key
    id BIGSERIAL PRIMARY KEY,
    
    -- Link to originating signal (REQUIRED)
    correlation_id UUID NOT NULL,
    
    -- Risk calculation inputs
    equity DECIMAL(28,2) NOT NULL,
    signal_price DECIMAL(28,10) NOT NULL,
    
    -- Risk calculation outputs
    risk_percentage DECIMAL(5,4) NOT NULL DEFAULT 0.0100,
    risk_amount_zar DECIMAL(28,10) NOT NULL,
    calculated_quantity DECIMAL(28,10) NOT NULL,
    
    -- Assessment status
    status VARCHAR(20) NOT NULL DEFAULT 'APPROVED',
    rejection_reason VARCHAR(255),
    
    -- Audit metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Chain of custody hash
    row_hash CHAR(64) NOT NULL,
    
    -- Constraints
    CONSTRAINT risk_assessments_correlation_id_fk 
        FOREIGN KEY (correlation_id) 
        REFERENCES signals(correlation_id)
        ON DELETE RESTRICT,
    
    CONSTRAINT risk_assessments_status_check 
        CHECK (status IN ('APPROVED', 'REJECTED', 'PENDING')),
    
    CONSTRAINT risk_assessments_risk_percentage_check
        CHECK (risk_percentage > 0 AND risk_percentage <= 1),
    
    CONSTRAINT risk_assessments_calculated_quantity_check
        CHECK (calculated_quantity >= 0)
);

-- ============================================================================
-- INDEXES
-- ============================================================================

-- Fast lookup by correlation_id (primary query pattern)
CREATE INDEX IF NOT EXISTS idx_risk_assessments_correlation_id 
    ON risk_assessments(correlation_id);

-- Time-based queries for audit
CREATE INDEX IF NOT EXISTS idx_risk_assessments_created_at 
    ON risk_assessments(created_at DESC);

-- Status filtering
CREATE INDEX IF NOT EXISTS idx_risk_assessments_status 
    ON risk_assessments(status);

-- ============================================================================
-- ATTACH IMMUTABILITY TRIGGERS
-- ============================================================================

-- Prevent UPDATE operations (AUD-010)
CREATE OR REPLACE TRIGGER trg_risk_assessments_prevent_update
    BEFORE UPDATE ON risk_assessments
    FOR EACH ROW
    EXECUTE FUNCTION prevent_update();

-- Prevent DELETE operations (AUD-011)
CREATE OR REPLACE TRIGGER trg_risk_assessments_prevent_delete
    BEFORE DELETE ON risk_assessments
    FOR EACH ROW
    EXECUTE FUNCTION prevent_delete();

-- Compute hash chain
CREATE OR REPLACE TRIGGER trg_risk_assessments_compute_hash
    BEFORE INSERT ON risk_assessments
    FOR EACH ROW
    EXECUTE FUNCTION compute_row_hash();


-- ============================================================================
-- UPDATE compute_row_hash() TO HANDLE NEW TABLE
-- ============================================================================

CREATE OR REPLACE FUNCTION compute_row_hash()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    prev_hash CHAR(64);
    row_data TEXT;
    computed_hash CHAR(64);
BEGIN
    -- Acquire advisory lock to serialize hash chain computation per table
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
    
    -- Compute SHA-256 hash: previous_hash || row_data
    computed_hash := encode(digest(prev_hash || row_data, 'sha256'), 'hex');
    NEW.row_hash := computed_hash;
    
    RETURN NEW;
END;
$$;


-- ============================================================================
-- GRANT PERMISSIONS TO app_trading
-- ============================================================================

GRANT SELECT, INSERT ON risk_assessments TO app_trading;
GRANT USAGE, SELECT ON SEQUENCE risk_assessments_id_seq TO app_trading;

-- Explicitly revoke dangerous permissions
REVOKE UPDATE, DELETE ON risk_assessments FROM app_trading;
REVOKE UPDATE, DELETE ON risk_assessments FROM PUBLIC;

-- ============================================================================
-- VERIFICATION
-- ============================================================================

DO $$
BEGIN
    RAISE NOTICE '============================================';
    RAISE NOTICE 'RISK ASSESSMENTS TABLE CREATED';
    RAISE NOTICE 'Immutability triggers attached';
    RAISE NOTICE 'Hash chain enabled';
    RAISE NOTICE 'Permissions granted to app_trading';
    RAISE NOTICE '============================================';
END $$;

-- ============================================================================
-- END OF RISK AUDIT TABLE
-- ============================================================================

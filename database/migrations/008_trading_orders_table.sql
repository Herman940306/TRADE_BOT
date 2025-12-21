-- ============================================================================
-- Project Autonomous Alpha v1.3.2
-- Immutable Audit Log Schema - Trading Orders Table
-- ============================================================================
--
-- SOVEREIGN TIER INFRASTRUCTURE
-- Assurance Level: 100% Confidence (Mission-Critical)
--
-- PURPOSE
-- -------
-- This table stores all trading orders executed by the Dispatcher.
-- Every order is linked to the originating signal via correlation_id,
-- creating a complete audit trail from signal → AI debate → order.
--
-- AUDIT TRAIL
-- -----------
-- Signal (signals) → AI Debate (ai_debates) → Order (trading_orders)
-- Full traceability for regulatory compliance and client transparency.
--
-- ============================================================================

-- ============================================================================
-- CREATE TRADING ORDERS TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS trading_orders (
    -- Primary key
    id BIGSERIAL PRIMARY KEY,
    
    -- Link to originating signal (REQUIRED)
    correlation_id UUID NOT NULL,
    
    -- VALR order identifier
    order_id VARCHAR(100) NOT NULL,
    
    -- Order details
    pair VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL,
    quantity DECIMAL(28,10) NOT NULL,
    
    -- Execution details
    execution_price DECIMAL(28,10),
    zar_value DECIMAL(28,2),
    
    -- Order status
    status VARCHAR(20) NOT NULL DEFAULT 'PLACED',
    
    -- Mock mode indicator
    is_mock BOOLEAN NOT NULL DEFAULT FALSE,
    
    -- Error tracking
    error_message VARCHAR(500),
    
    -- Audit metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Chain of custody hash
    row_hash CHAR(64) NOT NULL,
    
    -- Constraints
    CONSTRAINT trading_orders_correlation_id_fk 
        FOREIGN KEY (correlation_id) 
        REFERENCES signals(correlation_id)
        ON DELETE RESTRICT,
    
    CONSTRAINT trading_orders_side_check 
        CHECK (side IN ('BUY', 'SELL')),
    
    CONSTRAINT trading_orders_status_check 
        CHECK (status IN ('PLACED', 'FILLED', 'PARTIALLY_FILLED', 'FAILED', 'CANCELLED', 'MOCK_FILLED')),
    
    CONSTRAINT trading_orders_quantity_check
        CHECK (quantity > 0)
);

-- ============================================================================
-- INDEXES
-- ============================================================================

-- Fast lookup by correlation_id (primary query pattern)
CREATE INDEX IF NOT EXISTS idx_trading_orders_correlation_id 
    ON trading_orders(correlation_id);

-- Fast lookup by VALR order_id
CREATE INDEX IF NOT EXISTS idx_trading_orders_order_id 
    ON trading_orders(order_id);

-- Time-based queries for audit
CREATE INDEX IF NOT EXISTS idx_trading_orders_created_at 
    ON trading_orders(created_at DESC);

-- Status filtering
CREATE INDEX IF NOT EXISTS idx_trading_orders_status 
    ON trading_orders(status);

-- ============================================================================
-- UPDATE compute_row_hash() FOR TRADING ORDERS
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
        WHEN 'trading_orders' THEN
            row_data := COALESCE(NEW.correlation_id::TEXT, '') || '|' ||
                        COALESCE(NEW.order_id, '') || '|' ||
                        COALESCE(NEW.pair, '') || '|' ||
                        COALESCE(NEW.side, '') || '|' ||
                        COALESCE(NEW.quantity::TEXT, '') || '|' ||
                        COALESCE(NEW.execution_price::TEXT, '') || '|' ||
                        COALESCE(NEW.zar_value::TEXT, '') || '|' ||
                        COALESCE(NEW.status, '') || '|' ||
                        COALESCE(NEW.is_mock::TEXT, '') || '|' ||
                        COALESCE(NEW.error_message, '') || '|' ||
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
$$;

-- ============================================================================
-- ATTACH IMMUTABILITY TRIGGERS
-- ============================================================================

-- Compute hash chain
CREATE TRIGGER trg_trading_orders_compute_hash
    BEFORE INSERT ON trading_orders
    FOR EACH ROW
    EXECUTE FUNCTION compute_row_hash();

-- Prevent UPDATE operations (AUD-010)
CREATE TRIGGER trg_trading_orders_prevent_update
    BEFORE UPDATE ON trading_orders
    FOR EACH ROW
    EXECUTE FUNCTION prevent_update();

-- Prevent DELETE operations (AUD-011)
CREATE TRIGGER trg_trading_orders_prevent_delete
    BEFORE DELETE ON trading_orders
    FOR EACH ROW
    EXECUTE FUNCTION prevent_delete();

-- ============================================================================
-- GRANT PERMISSIONS TO app_trading
-- ============================================================================

GRANT SELECT, INSERT ON trading_orders TO app_trading;
GRANT USAGE, SELECT ON SEQUENCE trading_orders_id_seq TO app_trading;

-- Explicitly revoke dangerous permissions
REVOKE UPDATE, DELETE ON trading_orders FROM app_trading;
REVOKE UPDATE, DELETE ON trading_orders FROM PUBLIC;

-- ============================================================================
-- VERIFICATION
-- ============================================================================

DO $$
BEGIN
    RAISE NOTICE '============================================';
    RAISE NOTICE 'TRADING ORDERS TABLE CREATED';
    RAISE NOTICE 'Immutability triggers attached';
    RAISE NOTICE 'Hash chain enabled';
    RAISE NOTICE 'Permissions granted to app_trading';
    RAISE NOTICE '============================================';
END $$;

-- ============================================================================
-- END OF TRADING ORDERS TABLE
-- ============================================================================

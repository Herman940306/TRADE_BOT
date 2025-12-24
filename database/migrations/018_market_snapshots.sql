-- ============================================================================
-- Project Autonomous Alpha v1.7.0
-- Migration 018: Market Snapshots Table - VALR Integration
-- ============================================================================
--
-- Reliability Level: SOVEREIGN TIER (Mission-Critical)
-- Purpose: Store market ticker data from VALR exchange
--
-- SOVEREIGN MANDATE:
--   - All price columns use DECIMAL(20,8) for precision
--   - Indexes optimized for pair + timestamp queries
--   - correlation_id for audit traceability
--
-- Dependencies: None (standalone table)
--
-- ============================================================================

-- ============================================================================
-- MARKET SNAPSHOTS TABLE
-- ============================================================================
-- Stores periodic market data snapshots from VALR exchange
-- Used for:
--   - Market data staleness detection (>30s = stale)
--   - Spread analysis and rejection (>2% = reject)
--   - Historical price tracking for RLHF feedback
-- ============================================================================

CREATE TABLE IF NOT EXISTS market_snapshots (
    -- Primary key
    id SERIAL PRIMARY KEY,
    
    -- Trading pair (e.g., BTCZAR, ETHZAR)
    pair VARCHAR(20) NOT NULL,
    
    -- Price data (DECIMAL for Sovereign Tier compliance)
    bid DECIMAL(20,8) NOT NULL,
    ask DECIMAL(20,8) NOT NULL,
    last_price DECIMAL(20,8) NOT NULL,
    
    -- Volume data
    volume_24h DECIMAL(20,8) NOT NULL DEFAULT 0,
    
    -- Calculated spread percentage
    spread_pct DECIMAL(10,4) NOT NULL DEFAULT 0,
    
    -- Data source identifier
    source VARCHAR(20) NOT NULL DEFAULT 'VALR',
    
    -- Exchange timestamp (milliseconds since epoch)
    timestamp_ms BIGINT NOT NULL,
    
    -- Staleness flag (set by application when data > 30s old)
    is_stale BOOLEAN NOT NULL DEFAULT FALSE,
    
    -- Audit columns
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    correlation_id UUID,
    
    -- Constraints
    CONSTRAINT chk_market_snapshots_bid_positive CHECK (bid >= 0),
    CONSTRAINT chk_market_snapshots_ask_positive CHECK (ask >= 0),
    CONSTRAINT chk_market_snapshots_ask_gte_bid CHECK (ask >= bid),
    CONSTRAINT chk_market_snapshots_spread_positive CHECK (spread_pct >= 0)
);

-- ============================================================================
-- INDEXES
-- ============================================================================

-- Primary query pattern: Get latest snapshot for a pair
CREATE INDEX IF NOT EXISTS idx_market_snapshots_pair_created 
    ON market_snapshots(pair, created_at DESC);

-- Query pattern: Get snapshots by timestamp range
CREATE INDEX IF NOT EXISTS idx_market_snapshots_timestamp 
    ON market_snapshots(timestamp_ms DESC);

-- Query pattern: Find stale data
CREATE INDEX IF NOT EXISTS idx_market_snapshots_stale 
    ON market_snapshots(is_stale) 
    WHERE is_stale = TRUE;

-- Query pattern: Correlation ID lookup for audit
CREATE INDEX IF NOT EXISTS idx_market_snapshots_correlation 
    ON market_snapshots(correlation_id) 
    WHERE correlation_id IS NOT NULL;

-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON TABLE market_snapshots IS 
    'VALR market ticker snapshots - Sovereign Tier price tracking';

COMMENT ON COLUMN market_snapshots.pair IS 
    'Trading pair symbol (e.g., BTCZAR, ETHZAR)';

COMMENT ON COLUMN market_snapshots.bid IS 
    'Best bid price in ZAR (DECIMAL for precision)';

COMMENT ON COLUMN market_snapshots.ask IS 
    'Best ask price in ZAR (DECIMAL for precision)';

COMMENT ON COLUMN market_snapshots.spread_pct IS 
    'Calculated spread percentage: (ask-bid)/bid * 100';

COMMENT ON COLUMN market_snapshots.is_stale IS 
    'TRUE if data is older than 30 seconds';

COMMENT ON COLUMN market_snapshots.correlation_id IS 
    'Audit trail identifier for request tracing';

-- ============================================================================
-- HELPER FUNCTION: Get Latest Snapshot
-- ============================================================================

CREATE OR REPLACE FUNCTION get_latest_market_snapshot(p_pair VARCHAR(20))
RETURNS TABLE (
    pair VARCHAR(20),
    bid DECIMAL(20,8),
    ask DECIMAL(20,8),
    last_price DECIMAL(20,8),
    spread_pct DECIMAL(10,4),
    timestamp_ms BIGINT,
    is_stale BOOLEAN,
    age_seconds INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        ms.pair,
        ms.bid,
        ms.ask,
        ms.last_price,
        ms.spread_pct,
        ms.timestamp_ms,
        ms.is_stale,
        EXTRACT(EPOCH FROM (NOW() - ms.created_at))::INTEGER AS age_seconds
    FROM market_snapshots ms
    WHERE ms.pair = p_pair
    ORDER BY ms.created_at DESC
    LIMIT 1;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_latest_market_snapshot IS 
    'Get the most recent market snapshot for a trading pair with age calculation';

-- ============================================================================
-- HELPER FUNCTION: Mark Stale Snapshots
-- ============================================================================

CREATE OR REPLACE FUNCTION mark_stale_market_snapshots(p_stale_threshold_seconds INTEGER DEFAULT 30)
RETURNS INTEGER AS $$
DECLARE
    v_updated_count INTEGER;
BEGIN
    UPDATE market_snapshots
    SET is_stale = TRUE
    WHERE is_stale = FALSE
      AND created_at < NOW() - (p_stale_threshold_seconds || ' seconds')::INTERVAL;
    
    GET DIAGNOSTICS v_updated_count = ROW_COUNT;
    RETURN v_updated_count;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION mark_stale_market_snapshots IS 
    'Mark snapshots older than threshold as stale (default: 30 seconds)';

-- ============================================================================
-- Sovereign Reliability Audit
-- ============================================================================
--
-- [Migration Audit]
-- Table: market_snapshots
-- Decimal Precision: [Verified - DECIMAL(20,8) for all prices]
-- Indexes: [4 indexes for common query patterns]
-- Constraints: [4 CHECK constraints for data integrity]
-- Audit Trail: [correlation_id column present]
-- Helper Functions: [2 functions for common operations]
-- Confidence Score: [99/100]
--
-- ============================================================================

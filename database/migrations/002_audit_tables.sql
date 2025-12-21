-- ============================================================================
-- Project Autonomous Alpha v1.3.2
-- Immutable Audit Log Schema - Audit Tables
-- ============================================================================
--
-- SOVEREIGN TIER INFRASTRUCTURE
-- Assurance Level: 100% Confidence (Mission-Critical)
--
-- TABLE HIERARCHY
-- ---------------
-- signals (ROOT)
--   └── ai_debates (FK: correlation_id → signals.correlation_id)
--   └── order_execution (FK: correlation_id → signals.correlation_id)
--         └── order_events (FK: order_execution_id → order_execution.id)
--
-- FINANCIAL PRECISION
-- -------------------
-- All price/quantity columns: DECIMAL(28,10) - Institutional grade
-- ZAR equity columns: DECIMAL(28,2) - Currency precision with headroom
-- Confidence scores: DECIMAL(5,4) - Four decimal places
--
-- IMMUTABILITY
-- ------------
-- All tables are protected by:
--   1. BEFORE UPDATE trigger → prevent_update() → AUD-00X error
--   2. BEFORE DELETE trigger → prevent_delete() → AUD-00X error
--   3. REVOKE UPDATE, DELETE privileges from application roles
--
-- CHAIN OF CUSTODY
-- ----------------
-- All tables include row_hash CHAR(64) computed by compute_row_hash()
-- Hash formula: SHA-256(previous_row_hash || current_row_data)
--
-- ============================================================================

-- ============================================================================
-- TABLE: signals
-- ============================================================================
-- Root table for all trade decision chains.
-- Every AI deliberation and order execution traces back to a signal.

CREATE TABLE IF NOT EXISTS signals (
    -- Primary identifier
    id                  BIGSERIAL PRIMARY KEY,
    
    -- Correlation chain anchor (UUID v4)
    -- All related records reference this value
    correlation_id      UUID NOT NULL DEFAULT gen_random_uuid(),
    
    -- TradingView signal identifier (idempotency key)
    signal_id           VARCHAR(64) NOT NULL,
    
    -- Trade parameters
    symbol              VARCHAR(20) NOT NULL,
    side                VARCHAR(10) NOT NULL,
    price               DECIMAL(28,10) NOT NULL,
    quantity            DECIMAL(28,10) NOT NULL,
    
    -- Raw webhook payload (schema drift protection)
    raw_payload         JSONB NOT NULL,
    
    -- Security metadata
    source_ip           INET NOT NULL,
    hmac_verified       BOOLEAN NOT NULL DEFAULT FALSE,
    
    -- Chain of custody hash
    row_hash            CHAR(64) NOT NULL,
    
    -- Timestamp with microsecond precision (UTC)
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT signals_correlation_id_unique UNIQUE (correlation_id),
    CONSTRAINT signals_signal_id_unique UNIQUE (signal_id),
    CONSTRAINT signals_side_check CHECK (side IN ('BUY', 'SELL')),
    CONSTRAINT signals_price_positive CHECK (price > 0),
    CONSTRAINT signals_quantity_positive CHECK (quantity > 0)
);

-- Indexes for query performance
CREATE INDEX IF NOT EXISTS idx_signals_correlation_id ON signals(correlation_id);
CREATE INDEX IF NOT EXISTS idx_signals_created_at ON signals(created_at);
CREATE INDEX IF NOT EXISTS idx_signals_symbol ON signals(symbol);

COMMENT ON TABLE signals IS 
    'Immutable audit table for inbound TradingView webhook signals.
     Root of the correlation chain. All AI debates and order executions
     reference signals via correlation_id.
     Sovereign Mandate: Append-only, zero modifications permitted.';

COMMENT ON COLUMN signals.correlation_id IS 
    'UUID v4 linking this signal to all downstream AI debates and orders.
     Generated automatically. Forms the root of the audit chain.';

COMMENT ON COLUMN signals.raw_payload IS 
    'Complete unparsed webhook body stored as JSONB.
     Ensures data recoverability regardless of schema changes.
     Sovereign Mandate: Zero data loss on schema drift.';

COMMENT ON COLUMN signals.row_hash IS 
    'SHA-256 hash linking to previous row. Computed by trigger.
     Formula: SHA-256(previous_row_hash || current_row_data).
     User-provided values are overwritten.';


-- ============================================================================
-- TABLE: ai_debates
-- ============================================================================
-- Records AI model reasoning from the Cold Path.
-- Links to signals via correlation_id foreign key.

CREATE TABLE IF NOT EXISTS ai_debates (
    -- Primary identifier
    id                  BIGSERIAL PRIMARY KEY,
    
    -- Foreign key to originating signal
    correlation_id      UUID NOT NULL,
    
    -- Model identification
    model_name          VARCHAR(50) NOT NULL,
    
    -- Structured reasoning output
    -- DeepSeek-R1: Contains 3 rejection reasons
    -- Llama 3.1: Contains sentiment/mood analysis
    reasoning_json      JSONB NOT NULL,
    
    -- Model confidence (0.0000 to 1.0000)
    confidence_score    DECIMAL(5,4) NOT NULL,
    
    -- Processing time in milliseconds
    elapsed_ms          INTEGER NOT NULL,
    
    -- Timeout indicator (Cold Path > 30s)
    is_timeout          BOOLEAN NOT NULL DEFAULT FALSE,
    
    -- Chain of custody hash
    row_hash            CHAR(64) NOT NULL,
    
    -- Timestamp with microsecond precision (UTC)
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT ai_debates_correlation_id_fk 
        FOREIGN KEY (correlation_id) REFERENCES signals(correlation_id)
        ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT ai_debates_confidence_range 
        CHECK (confidence_score >= 0 AND confidence_score <= 1),
    CONSTRAINT ai_debates_elapsed_positive 
        CHECK (elapsed_ms >= 0),
    CONSTRAINT ai_debates_model_name_check 
        CHECK (model_name IN ('deepseek-r1', 'llama-3.1', 'phi-4', 'timeout'))
);

-- Indexes for query performance
CREATE INDEX IF NOT EXISTS idx_ai_debates_correlation_id ON ai_debates(correlation_id);
CREATE INDEX IF NOT EXISTS idx_ai_debates_created_at ON ai_debates(created_at);
CREATE INDEX IF NOT EXISTS idx_ai_debates_model_name ON ai_debates(model_name);

COMMENT ON TABLE ai_debates IS 
    'Immutable audit table for AI model reasoning from Cold Path.
     Records DeepSeek-R1 rejection reasons and Llama 3.1 sentiment analysis.
     Links to signals via correlation_id.
     Sovereign Mandate: Append-only, zero modifications permitted.';

COMMENT ON COLUMN ai_debates.reasoning_json IS 
    'Structured JSON containing model output.
     DeepSeek-R1: {"rejection_reasons": ["reason1", "reason2", "reason3"]}
     Llama 3.1: {"sentiment": "bullish|bearish|neutral", "mood": "..."}';

COMMENT ON COLUMN ai_debates.is_timeout IS 
    'TRUE if Cold Path exceeded 30 second threshold.
     Signal is discarded when timeout occurs.
     Sovereign Mandate: Safe-fail on Cold Path timeout.';

-- ============================================================================
-- TABLE: order_execution
-- ============================================================================
-- Records trade orders submitted to the exchange.
-- Links to signals via correlation_id foreign key.

CREATE TABLE IF NOT EXISTS order_execution (
    -- Primary identifier
    id                  BIGSERIAL PRIMARY KEY,
    
    -- Foreign key to originating signal
    correlation_id      UUID NOT NULL,
    
    -- Order parameters
    order_type          VARCHAR(20) NOT NULL,
    symbol              VARCHAR(20) NOT NULL,
    side                VARCHAR(10) NOT NULL,
    quantity            DECIMAL(28,10) NOT NULL,
    price               DECIMAL(28,10),  -- NULL for MARKET orders
    
    -- Exchange response
    exchange_order_id   VARCHAR(64),
    status              VARCHAR(20) NOT NULL,
    
    -- Chain of custody hash
    row_hash            CHAR(64) NOT NULL,
    
    -- Timestamp with microsecond precision (UTC)
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT order_execution_correlation_id_fk 
        FOREIGN KEY (correlation_id) REFERENCES signals(correlation_id)
        ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT order_execution_order_type_check 
        CHECK (order_type IN ('MARKET', 'LIMIT', 'STOP', 'STOP_LIMIT')),
    CONSTRAINT order_execution_side_check 
        CHECK (side IN ('BUY', 'SELL')),
    CONSTRAINT order_execution_quantity_positive 
        CHECK (quantity > 0),
    CONSTRAINT order_execution_price_positive 
        CHECK (price IS NULL OR price > 0),
    CONSTRAINT order_execution_status_check 
        CHECK (status IN ('PENDING', 'SUBMITTED', 'FILLED', 'PARTIAL', 'REJECTED', 'CANCELLED'))
);

-- Indexes for query performance
CREATE INDEX IF NOT EXISTS idx_order_execution_correlation_id ON order_execution(correlation_id);
CREATE INDEX IF NOT EXISTS idx_order_execution_created_at ON order_execution(created_at);
CREATE INDEX IF NOT EXISTS idx_order_execution_status ON order_execution(status);
CREATE INDEX IF NOT EXISTS idx_order_execution_symbol ON order_execution(symbol);

COMMENT ON TABLE order_execution IS 
    'Immutable audit table for trade orders submitted to exchange.
     Links to signals via correlation_id.
     Sovereign Mandate: Append-only, zero modifications permitted.';

COMMENT ON COLUMN order_execution.price IS 
    'Order price. NULL for MARKET orders.
     DECIMAL(28,10) for institutional-grade precision.';


-- ============================================================================
-- TABLE: order_events
-- ============================================================================
-- Append-only table for order lifecycle events.
-- Records fills, rejections, cancellations, and KILL_SWITCH events.
-- Links to order_execution via order_execution_id foreign key.
--
-- CRITICAL: This table uses INSERT-ONLY pattern.
-- No updates to existing records are permitted.
-- Each event (fill, partial fill, rejection) creates a NEW row.

CREATE TABLE IF NOT EXISTS order_events (
    -- Primary identifier
    id                  BIGSERIAL PRIMARY KEY,
    
    -- Foreign key to order
    order_execution_id  BIGINT NOT NULL,
    
    -- Event classification
    event_type          VARCHAR(30) NOT NULL,
    
    -- Fill details (for FILL and PARTIAL_FILL events)
    fill_quantity       DECIMAL(28,10),
    fill_price          DECIMAL(28,10),
    
    -- ZAR equity tracking (for KILL_SWITCH events)
    -- DECIMAL(28,2) for currency precision with institutional headroom
    zar_equity          DECIMAL(28,2),
    
    -- Positions closed (for KILL_SWITCH events)
    -- JSON array of position details
    positions_closed    JSONB,
    
    -- Rejection/error details
    rejection_reason    TEXT,
    exchange_error_code VARCHAR(50),
    
    -- Chain of custody hash
    row_hash            CHAR(64) NOT NULL,
    
    -- Timestamp with microsecond precision (UTC)
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT order_events_order_execution_id_fk 
        FOREIGN KEY (order_execution_id) REFERENCES order_execution(id)
        ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT order_events_event_type_check 
        CHECK (event_type IN (
            'FILL',           -- Complete fill
            'PARTIAL_FILL',   -- Partial fill
            'REJECTED',       -- Exchange rejection
            'CANCELLED',      -- Order cancellation
            'KILL_SWITCH',    -- Emergency position closure
            'EXPIRED'         -- Order expiration
        )),
    CONSTRAINT order_events_fill_quantity_positive 
        CHECK (fill_quantity IS NULL OR fill_quantity > 0),
    CONSTRAINT order_events_fill_price_positive 
        CHECK (fill_price IS NULL OR fill_price > 0),
    CONSTRAINT order_events_zar_equity_positive 
        CHECK (zar_equity IS NULL OR zar_equity >= 0)
);

-- Indexes for query performance
CREATE INDEX IF NOT EXISTS idx_order_events_order_execution_id ON order_events(order_execution_id);
CREATE INDEX IF NOT EXISTS idx_order_events_created_at ON order_events(created_at);
CREATE INDEX IF NOT EXISTS idx_order_events_event_type ON order_events(event_type);

COMMENT ON TABLE order_events IS 
    'Immutable append-only table for order lifecycle events.
     Records fills, rejections, cancellations, and KILL_SWITCH events.
     Links to order_execution via order_execution_id.
     CRITICAL: INSERT-ONLY pattern. No updates permitted.
     Sovereign Mandate: Complete order history preservation.';

COMMENT ON COLUMN order_events.zar_equity IS 
    'Net equity in South African Rand at event time.
     DECIMAL(28,2) for currency precision with institutional headroom.
     Populated for KILL_SWITCH events per PRD Section 5.1.
     Sovereign Mandate: ZAR Floor monitoring.';

COMMENT ON COLUMN order_events.positions_closed IS 
    'JSON array of positions closed during KILL_SWITCH.
     Format: [{"symbol": "...", "side": "...", "quantity": "...", "pnl": "..."}]
     Sovereign Mandate: Complete KILL_SWITCH audit trail.';

COMMENT ON COLUMN order_events.event_type IS 
    'Event classification:
     - FILL: Complete order fill
     - PARTIAL_FILL: Partial order fill
     - REJECTED: Exchange rejected order
     - CANCELLED: Order cancelled
     - KILL_SWITCH: Emergency position closure (ZAR Floor breach)
     - EXPIRED: Order expired';

-- ============================================================================
-- END OF AUDIT TABLES
-- ============================================================================

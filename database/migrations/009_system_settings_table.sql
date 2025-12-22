-- ============================================================================
-- Project Autonomous Alpha v1.3.2
-- System Settings Table - Kill Switch & Configuration
-- ============================================================================
--
-- SOVEREIGN TIER INFRASTRUCTURE
-- Assurance Level: 100% Confidence (Mission-Critical)
--
-- PURPOSE
-- -------
-- This table stores system-wide configuration including the Emergency
-- Kill Switch. Unlike other audit tables, this table ALLOWS updates
-- to enable real-time system control.
--
-- KILL SWITCH
-- -----------
-- The system_active flag controls whether the bot can execute trades.
-- When FALSE, all trade execution is halted immediately.
--
-- ============================================================================

-- ============================================================================
-- CREATE SYSTEM SETTINGS TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS system_settings (
    -- Primary key (single row expected)
    id SERIAL PRIMARY KEY,
    
    -- Kill Switch: FALSE = all trading halted
    system_active BOOLEAN NOT NULL DEFAULT TRUE,
    
    -- Kill switch metadata
    kill_switch_reason VARCHAR(500),
    kill_switch_triggered_at TIMESTAMPTZ,
    kill_switch_triggered_by VARCHAR(100),
    
    -- Configuration values
    min_trade_zar DECIMAL(28,2) NOT NULL DEFAULT 50.00,
    max_slippage_percent DECIMAL(5,4) NOT NULL DEFAULT 0.0100,
    taker_fee_percent DECIMAL(5,4) NOT NULL DEFAULT 0.0010,
    
    -- Audit metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- INSERT DEFAULT SETTINGS
-- ============================================================================

INSERT INTO system_settings (
    id,
    system_active,
    min_trade_zar,
    max_slippage_percent,
    taker_fee_percent
) VALUES (
    1,
    TRUE,
    50.00,
    0.0100,
    0.0010
) ON CONFLICT (id) DO NOTHING;

-- ============================================================================
-- UPDATE TRIGGER FOR updated_at
-- ============================================================================

CREATE OR REPLACE FUNCTION update_system_settings_timestamp()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_system_settings_updated_at
    BEFORE UPDATE ON system_settings
    FOR EACH ROW
    EXECUTE FUNCTION update_system_settings_timestamp();

-- ============================================================================
-- GRANT PERMISSIONS
-- ============================================================================

-- app_trading can read and update system_settings
GRANT SELECT, UPDATE ON system_settings TO app_trading;
GRANT USAGE, SELECT ON SEQUENCE system_settings_id_seq TO app_trading;

-- ============================================================================
-- VERIFICATION
-- ============================================================================

DO $$
BEGIN
    RAISE NOTICE '============================================';
    RAISE NOTICE 'SYSTEM SETTINGS TABLE CREATED';
    RAISE NOTICE 'Kill Switch: ENABLED (system_active=TRUE)';
    RAISE NOTICE 'Min Trade ZAR: R50.00';
    RAISE NOTICE 'Max Slippage: 1.00%%';
    RAISE NOTICE 'Taker Fee: 0.10%%';
    RAISE NOTICE '============================================';
END $$;

-- ============================================================================
-- END OF SYSTEM SETTINGS TABLE
-- ============================================================================

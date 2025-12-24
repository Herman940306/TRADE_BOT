"""
Property-Based Tests for Production Safety Module

Reliability Level: L6 Critical
Python 3.8 Compatible

Tests the Equity_Module and Kill_Switch_Module using Hypothesis.
Minimum 100 iterations per property as per design specification.
"""

import asyncio
from decimal import Decimal, ROUND_HALF_EVEN
from typing import Dict, Optional

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

# Import modules under test
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from app.logic.production_safety import (
    EquityModule,
    KillSwitchModule,
    TriggerReason,
    EquitySnapshot,
    KillSwitchResult,
    DEFAULT_ZAR_FLOOR,
    create_safety_modules
)


# =============================================================================
# HYPOTHESIS STRATEGIES
# =============================================================================

# Strategy for generating valid Decimal amounts (positive, reasonable range)
decimal_amount_strategy = st.decimals(
    min_value=Decimal("0.01"),
    max_value=Decimal("10000000.00"),
    places=2,
    allow_nan=False,
    allow_infinity=False
)

# Strategy for generating ZAR floor values
zar_floor_strategy = st.decimals(
    min_value=Decimal("1000.00"),
    max_value=Decimal("1000000.00"),
    places=2,
    allow_nan=False,
    allow_infinity=False
)

# Strategy for generating FX rates (realistic USD/ZAR range)
fx_rate_strategy = st.decimals(
    min_value=Decimal("10.00"),
    max_value=Decimal("30.00"),
    places=4,
    allow_nan=False,
    allow_infinity=False
)

# Strategy for generating asset balance dictionaries
asset_balances_strategy = st.dictionaries(
    keys=st.sampled_from(["BTC", "ETH", "USDT", "ZAR", "USD"]),
    values=decimal_amount_strategy,
    min_size=1,
    max_size=5
)


# =============================================================================
# PROPERTY 11: ZAR Equity Decimal Round-Trip
# **Feature: production-deployment-phase2, Property 11: ZAR Equity Decimal Round-Trip**
# **Validates: Requirements 5.1, 5.2**
# =============================================================================

class TestZARDecimalRoundTrip:
    """
    Property 11: ZAR Equity Decimal Round-Trip
    
    For any asset value, converting to ZAR using decimal.Decimal with 
    ROUND_HALF_EVEN and then formatting as "R X,XXX.XX" SHALL preserve 
    precision to 2 decimal places.
    """
    
    @settings(max_examples=100)
    @given(amount=decimal_amount_strategy)
    def test_format_zar_preserves_precision(self, amount: Decimal) -> None:
        """
        **Feature: production-deployment-phase2, Property 11: ZAR Equity Decimal Round-Trip**
        **Validates: Requirements 5.1, 5.2**
        
        Verify that format_zar produces correctly formatted output with
        2 decimal places and R prefix.
        """
        equity_module = EquityModule()
        formatted = equity_module.format_zar(amount)
        
        # Must start with "R "
        assert formatted.startswith("R "), f"Missing R prefix: {formatted}"
        
        # Extract numeric part (remove R and commas)
        numeric_str = formatted[2:].replace(",", "")
        
        # Must have exactly 2 decimal places
        if "." in numeric_str:
            decimal_part = numeric_str.split(".")[1]
            assert len(decimal_part) == 2, f"Not 2 decimal places: {formatted}"
        
        # Parse back to Decimal and verify precision preserved
        parsed = Decimal(numeric_str)
        original_quantized = amount.quantize(
            Decimal("0.01"), 
            rounding=ROUND_HALF_EVEN
        )
        
        assert parsed == original_quantized, (
            f"Precision lost: original={amount}, "
            f"quantized={original_quantized}, parsed={parsed}"
        )
    
    @settings(max_examples=100)
    @given(
        amount_usd=decimal_amount_strategy,
        fx_rate=fx_rate_strategy
    )
    def test_usd_to_zar_conversion_uses_decimal(
        self, 
        amount_usd: Decimal, 
        fx_rate: Decimal
    ) -> None:
        """
        **Feature: production-deployment-phase2, Property 11: ZAR Equity Decimal Round-Trip**
        **Validates: Requirements 5.1**
        
        Verify USD to ZAR conversion uses Decimal arithmetic with ROUND_HALF_EVEN.
        """
        equity_module = EquityModule()
        
        # Access private method for testing
        result = equity_module._convert_to_zar(amount_usd, fx_rate)
        
        # Result must be Decimal
        assert isinstance(result, Decimal), f"Result is not Decimal: {type(result)}"
        
        # Result must have 2 decimal places
        assert result == result.quantize(Decimal("0.01")), (
            f"Result not quantized to 2 places: {result}"
        )
        
        # Verify calculation is correct
        expected = (amount_usd * fx_rate).quantize(
            Decimal("0.01"), 
            rounding=ROUND_HALF_EVEN
        )
        assert result == expected, f"Calculation mismatch: {result} != {expected}"
    
    @settings(max_examples=100)
    @given(amount=st.decimals(
        min_value=Decimal("-1000000.00"),
        max_value=Decimal("-0.01"),
        places=2,
        allow_nan=False,
        allow_infinity=False
    ))
    def test_format_zar_handles_negative(self, amount: Decimal) -> None:
        """
        **Feature: production-deployment-phase2, Property 11: ZAR Equity Decimal Round-Trip**
        **Validates: Requirements 5.2**
        
        Verify negative amounts are formatted correctly.
        """
        equity_module = EquityModule()
        formatted = equity_module.format_zar(amount)
        
        # Must indicate negative
        assert "R -" in formatted, f"Negative not indicated: {formatted}"


# =============================================================================
# PROPERTY 12: ZAR Floor Breach Triggers Kill Switch
# **Feature: production-deployment-phase2, Property 12: ZAR Floor Breach Triggers Kill Switch**
# **Validates: Requirements 5.5**
# =============================================================================

class TestZARFloorBreach:
    """
    Property 12: ZAR Floor Breach Triggers Kill Switch
    
    For any Net_Equity value below ZAR_FLOOR, the system SHALL trigger 
    Kill Switch with trigger_reason set to ZAR_FLOOR_BREACH.
    """
    
    @settings(max_examples=100)
    @given(
        floor=zar_floor_strategy,
        equity_ratio=st.floats(min_value=0.01, max_value=0.99)
    )
    def test_below_floor_triggers_kill_switch(
        self, 
        floor: Decimal, 
        equity_ratio: float
    ) -> None:
        """
        **Feature: production-deployment-phase2, Property 12: ZAR Floor Breach Triggers Kill Switch**
        **Validates: Requirements 5.5**
        
        Verify that equity below floor triggers Kill Switch callback.
        """
        # Track if kill switch was called
        kill_switch_called = False
        kill_switch_reason = None
        
        async def mock_kill_switch(
            reason: TriggerReason, 
            correlation_id: str
        ) -> KillSwitchResult:
            nonlocal kill_switch_called, kill_switch_reason
            kill_switch_called = True
            kill_switch_reason = reason
            return KillSwitchResult(
                trigger_reason=reason,
                positions_closed=0,
                orders_cancelled=0,
                api_revoked=False,
                total_execution_time_ms=100,
                audit_record_id="test",
                success=True
            )
        
        equity_module = EquityModule(
            zar_floor=floor,
            kill_switch_callback=mock_kill_switch
        )
        
        # Set FX rate
        equity_module._last_fx_rate = Decimal("18.50")
        from datetime import datetime, timezone
        equity_module._last_fx_rate_timestamp = datetime.now(timezone.utc)
        
        # Calculate equity below floor
        equity_below_floor = floor * Decimal(str(equity_ratio))
        usd_amount = equity_below_floor / Decimal("18.50")
        
        async def run_test():
            await equity_module.calculate_equity(
                {"USD": usd_amount},
                correlation_id="TEST_FLOOR_BREACH"
            )
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(run_test())
        finally:
            loop.close()
        
        assert kill_switch_called, "Kill Switch was not triggered for below-floor equity"
        assert kill_switch_reason == TriggerReason.ZAR_FLOOR_BREACH, (
            f"Wrong trigger reason: {kill_switch_reason}"
        )
    
    @settings(max_examples=100)
    @given(
        floor=zar_floor_strategy,
        equity_ratio=st.floats(min_value=1.01, max_value=10.0)
    )
    def test_above_floor_does_not_trigger(
        self, 
        floor: Decimal, 
        equity_ratio: float
    ) -> None:
        """
        **Feature: production-deployment-phase2, Property 12: ZAR Floor Breach Triggers Kill Switch**
        **Validates: Requirements 5.5**
        
        Verify that equity above floor does NOT trigger Kill Switch.
        """
        kill_switch_called = False
        
        async def mock_kill_switch(
            reason: TriggerReason, 
            correlation_id: str
        ) -> KillSwitchResult:
            nonlocal kill_switch_called
            kill_switch_called = True
            return KillSwitchResult(
                trigger_reason=reason,
                positions_closed=0,
                orders_cancelled=0,
                api_revoked=False,
                total_execution_time_ms=100,
                audit_record_id="test",
                success=True
            )
        
        equity_module = EquityModule(
            zar_floor=floor,
            kill_switch_callback=mock_kill_switch
        )
        
        # Set FX rate
        equity_module._last_fx_rate = Decimal("18.50")
        from datetime import datetime, timezone
        equity_module._last_fx_rate_timestamp = datetime.now(timezone.utc)
        
        # Calculate equity above floor
        equity_above_floor = floor * Decimal(str(equity_ratio))
        usd_amount = equity_above_floor / Decimal("18.50")
        
        async def run_test():
            await equity_module.calculate_equity(
                {"USD": usd_amount},
                correlation_id="TEST_ABOVE_FLOOR"
            )
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(run_test())
        finally:
            loop.close()
        
        assert not kill_switch_called, (
            "Kill Switch was incorrectly triggered for above-floor equity"
        )


# =============================================================================
# PROPERTY 9: Kill Switch Execution Completeness
# **Feature: production-deployment-phase2, Property 9: Kill Switch Execution Completeness**
# **Validates: Requirements 4.2, 4.3, 4.4, 4.5**
# =============================================================================

class TestKillSwitchCompleteness:
    """
    Property 9: Kill Switch Execution Completeness
    
    For any Kill Switch execution, the system SHALL:
    (1) close all open positions
    (2) cancel all pending orders
    (3) revoke the API session
    (4) write a complete audit record
    """
    
    @settings(max_examples=100)
    @given(
        trigger_reason=st.sampled_from(list(TriggerReason)),
        num_positions=st.integers(min_value=0, max_value=10),
        num_orders=st.integers(min_value=0, max_value=20)
    )
    def test_kill_switch_executes_all_steps(
        self,
        trigger_reason: TriggerReason,
        num_positions: int,
        num_orders: int
    ) -> None:
        """
        **Feature: production-deployment-phase2, Property 9: Kill Switch Execution Completeness**
        **Validates: Requirements 4.2, 4.3, 4.4, 4.5**
        
        Verify Kill Switch executes all required steps.
        """
        # Track execution steps
        positions_closed = []
        orders_cancelled = []
        api_revoked = False
        audit_written = False
        
        class MockExchangeClient:
            async def get_open_positions(self):
                return [{"symbol": f"POS_{i}"} for i in range(num_positions)]
            
            async def close_position(self, symbol: str, order_type: str):
                positions_closed.append(symbol)
            
            async def get_open_orders(self):
                return [{"order_id": f"ORD_{i}"} for i in range(num_orders)]
            
            async def cancel_order(self, order_id: str):
                orders_cancelled.append(order_id)
            
            async def revoke_session(self):
                nonlocal api_revoked
                api_revoked = True
        
        async def mock_audit_writer(record):
            nonlocal audit_written
            audit_written = True
        
        kill_switch = KillSwitchModule(
            exchange_client=MockExchangeClient(),
            audit_writer=mock_audit_writer
        )
        
        async def run_test():
            return await kill_switch.execute(
                trigger_reason=trigger_reason,
                correlation_id="TEST_COMPLETENESS"
            )
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(run_test())
        finally:
            loop.close()
        
        # Verify all positions closed (Requirement 4.2)
        assert len(positions_closed) == num_positions, (
            f"Not all positions closed: {len(positions_closed)} != {num_positions}"
        )
        
        # Verify all orders cancelled (Requirement 4.3)
        assert len(orders_cancelled) == num_orders, (
            f"Not all orders cancelled: {len(orders_cancelled)} != {num_orders}"
        )
        
        # Verify API revoked (Requirement 4.4)
        assert api_revoked, "API session was not revoked"
        
        # Verify audit record written (Requirement 4.5)
        assert audit_written, "Audit record was not written"
        
        # Verify result contains all required fields
        assert result.trigger_reason == trigger_reason
        assert result.positions_closed == num_positions
        assert result.orders_cancelled == num_orders
        assert result.api_revoked is True
        assert result.audit_record_id != ""
        assert result.total_execution_time_ms >= 0


# =============================================================================
# PROPERTY 10: Kill Switch Response Time
# **Feature: production-deployment-phase2, Property 10: Kill Switch Response Time**
# **Validates: Requirements 4.1**
# =============================================================================

class TestKillSwitchResponseTime:
    """
    Property 10: Kill Switch Response Time
    
    For any RED health status, Kill Switch SHALL begin execution within 5 seconds.
    """
    
    @settings(max_examples=100)
    @given(trigger_reason=st.sampled_from(list(TriggerReason)))
    def test_kill_switch_completes_within_sla(
        self,
        trigger_reason: TriggerReason
    ) -> None:
        """
        **Feature: production-deployment-phase2, Property 10: Kill Switch Response Time**
        **Validates: Requirements 4.1**
        
        Verify Kill Switch completes within 5-second SLA.
        """
        import time
        
        class FastMockExchangeClient:
            async def get_open_positions(self):
                return []
            
            async def close_position(self, symbol: str, order_type: str):
                pass
            
            async def get_open_orders(self):
                return []
            
            async def cancel_order(self, order_id: str):
                pass
            
            async def revoke_session(self):
                pass
        
        kill_switch = KillSwitchModule(
            exchange_client=FastMockExchangeClient()
        )
        
        async def run_test():
            start = time.time()
            result = await kill_switch.execute(
                trigger_reason=trigger_reason,
                correlation_id="TEST_SLA"
            )
            elapsed_ms = (time.time() - start) * 1000
            return result, elapsed_ms
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result, elapsed_ms = loop.run_until_complete(run_test())
        finally:
            loop.close()
        
        # Must complete within 5000ms SLA
        assert elapsed_ms < 5000, (
            f"Kill Switch exceeded 5-second SLA: {elapsed_ms}ms"
        )
        
        # Result should report execution time
        assert result.total_execution_time_ms < 5000, (
            f"Reported execution time exceeds SLA: {result.total_execution_time_ms}ms"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

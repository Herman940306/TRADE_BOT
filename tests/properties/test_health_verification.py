"""
Property-Based Tests for Health Verification Module

Reliability Level: L6 Critical
Python 3.8 Compatible

Tests the Health Verification Module using Hypothesis.
Minimum 100 iterations per property as per design specification.
"""

import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

# Import modules under test
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from app.logic.health_verification import (
    HealthVerificationModule,
    HealthReport,
    ToolHealthResult,
    ToolHealth,
    CRITICAL_TOOLS,
    AURA_BRIDGE_TOOLS,
    AURA_FULL_TOOLS,
    PING_TIMEOUT_SECONDS,
    create_health_module
)


# =============================================================================
# HYPOTHESIS STRATEGIES
# =============================================================================

# Strategy for tool names
tool_name_strategy = st.sampled_from(AURA_BRIDGE_TOOLS + AURA_FULL_TOOLS)

# Strategy for response times
response_time_strategy = st.integers(min_value=1, max_value=10000)

# Strategy for health statuses
health_status_strategy = st.sampled_from(list(ToolHealth))


# =============================================================================
# PROPERTY 15: Tool Health Check Coverage
# **Feature: production-deployment-phase2, Property 15: Tool Health Check Coverage**
# **Validates: Requirements 8.1**
# =============================================================================

class TestToolHealthCoverage:
    """
    Property 15: Tool Health Check Coverage
    
    For any health check execution, the Health_Verification_Module SHALL
    ping all 78 MCP tools and record response_time_ms for each.
    """
    
    def test_all_78_tools_registered(self) -> None:
        """
        **Feature: production-deployment-phase2, Property 15: Tool Health Check Coverage**
        **Validates: Requirements 8.1**
        
        Verify that exactly 78 tools are registered.
        """
        module = HealthVerificationModule()
        
        total_tools = module.get_tool_count()
        all_tools = module.get_all_tools()
        
        assert total_tools == 78, f"Expected 78 tools, got {total_tools}"
        assert len(all_tools) == 78, f"Expected 78 tool entries, got {len(all_tools)}"
    
    def test_aura_bridge_has_2_tools(self) -> None:
        """
        **Feature: production-deployment-phase2, Property 15: Tool Health Check Coverage**
        **Validates: Requirements 8.1**
        
        Verify aura-bridge has exactly 2 tools.
        """
        assert len(AURA_BRIDGE_TOOLS) == 2, (
            f"Expected 2 aura-bridge tools, got {len(AURA_BRIDGE_TOOLS)}"
        )
        assert "get_bot_vitals" in AURA_BRIDGE_TOOLS
        assert "explain_last_trade" in AURA_BRIDGE_TOOLS
    
    def test_aura_full_has_76_tools(self) -> None:
        """
        **Feature: production-deployment-phase2, Property 15: Tool Health Check Coverage**
        **Validates: Requirements 8.1**
        
        Verify aura-full has exactly 76 tools.
        """
        assert len(AURA_FULL_TOOLS) == 76, (
            f"Expected 76 aura-full tools, got {len(AURA_FULL_TOOLS)}"
        )
    
    def test_ping_all_covers_every_tool(self) -> None:
        """
        **Feature: production-deployment-phase2, Property 15: Tool Health Check Coverage**
        **Validates: Requirements 8.1**
        
        Verify ping_all_tools pings every registered tool.
        """
        pinged_tools = set()
        
        async def mock_caller(server: str, tool: str, args: dict):
            pinged_tools.add((tool, server))
            return {"status": "ok"}
        
        module = HealthVerificationModule(mcp_tool_caller=mock_caller)
        
        async def run_test():
            return await module.ping_all_tools("TEST_COVERAGE")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            report = loop.run_until_complete(run_test())
        finally:
            loop.close()
        
        # Verify all tools were pinged
        all_tools = set(module.get_all_tools())
        
        assert pinged_tools == all_tools, (
            f"Not all tools pinged. Missing: {all_tools - pinged_tools}"
        )
        assert len(report.tool_results) == 78, (
            f"Report should have 78 results, got {len(report.tool_results)}"
        )


# =============================================================================
# PROPERTY 16: Tool Health Classification
# **Feature: production-deployment-phase2, Property 16: Tool Health Classification**
# **Validates: Requirements 8.2, 8.3**
# =============================================================================

class TestToolHealthClassification:
    """
    Property 16: Tool Health Classification
    
    For any tool ping, if response arrives within 5 seconds the tool SHALL
    be marked HEALTHY, otherwise UNHEALTHY with error code TOOL_PING_TIMEOUT.
    """
    
    @settings(max_examples=100)
    @given(response_time_ms=st.integers(min_value=1, max_value=4999))
    def test_fast_response_marked_healthy(self, response_time_ms: int) -> None:
        """
        **Feature: production-deployment-phase2, Property 16: Tool Health Classification**
        **Validates: Requirements 8.2**
        
        Verify that responses within 5 seconds are marked HEALTHY.
        """
        async def fast_caller(server: str, tool: str, args: dict):
            # Simulate fast response (no actual delay in test)
            return {"status": "ok"}
        
        module = HealthVerificationModule(mcp_tool_caller=fast_caller)
        
        async def run_test():
            return await module.ping_tool("test_tool", "aura-full", "TEST")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(run_test())
        finally:
            loop.close()
        
        assert result.health == ToolHealth.HEALTHY, (
            f"Fast response should be HEALTHY, got {result.health}"
        )
        assert result.error_code is None, "Healthy tool should have no error code"
    
    def test_timeout_marked_unhealthy(self) -> None:
        """
        **Feature: production-deployment-phase2, Property 16: Tool Health Classification**
        **Validates: Requirements 8.3**
        
        Verify that timeouts are marked with TOOL_PING_TIMEOUT.
        """
        async def slow_caller(server: str, tool: str, args: dict):
            await asyncio.sleep(10)  # Exceeds 5s timeout
            return {"status": "ok"}
        
        # Use very short timeout for test
        module = HealthVerificationModule(
            mcp_tool_caller=slow_caller,
            ping_timeout_seconds=0.1  # 100ms timeout for fast test
        )
        
        async def run_test():
            return await module.ping_tool("test_tool", "aura-full", "TEST")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(run_test())
        finally:
            loop.close()
        
        assert result.health == ToolHealth.TIMEOUT, (
            f"Timeout should be TIMEOUT, got {result.health}"
        )
        assert result.error_code == "TOOL_PING_TIMEOUT", (
            f"Error code should be TOOL_PING_TIMEOUT, got {result.error_code}"
        )
    
    def test_error_marked_with_error_code(self) -> None:
        """
        **Feature: production-deployment-phase2, Property 16: Tool Health Classification**
        **Validates: Requirements 8.3**
        
        Verify that errors are marked with TOOL_PING_FAIL.
        """
        async def error_caller(server: str, tool: str, args: dict):
            raise Exception("Connection refused")
        
        module = HealthVerificationModule(mcp_tool_caller=error_caller)
        
        async def run_test():
            return await module.ping_tool("test_tool", "aura-full", "TEST")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(run_test())
        finally:
            loop.close()
        
        assert result.health == ToolHealth.ERROR, (
            f"Error should be ERROR, got {result.health}"
        )
        assert result.error_code == "TOOL_PING_FAIL", (
            f"Error code should be TOOL_PING_FAIL, got {result.error_code}"
        )


# =============================================================================
# PROPERTY 17: Health Report Completeness
# **Feature: production-deployment-phase2, Property 17: Health Report Completeness**
# **Validates: Requirements 8.4**
# =============================================================================

class TestHealthReportCompleteness:
    """
    Property 17: Health Report Completeness
    
    For any completed health check, the generated report SHALL contain
    healthy_count, unhealthy_count, and total_check_duration_ms fields.
    """
    
    @settings(max_examples=100)
    @given(
        healthy_ratio=st.floats(min_value=0.0, max_value=1.0)
    )
    def test_report_contains_required_fields(self, healthy_ratio: float) -> None:
        """
        **Feature: production-deployment-phase2, Property 17: Health Report Completeness**
        **Validates: Requirements 8.4**
        
        Verify report contains all required fields.
        """
        call_count = 0
        
        async def mixed_caller(server: str, tool: str, args: dict):
            nonlocal call_count
            call_count += 1
            # Some succeed, some fail based on ratio
            if (call_count % 10) / 10.0 < healthy_ratio:
                return {"status": "ok"}
            else:
                raise Exception("Simulated failure")
        
        module = HealthVerificationModule(mcp_tool_caller=mixed_caller)
        
        async def run_test():
            nonlocal call_count
            call_count = 0
            return await module.ping_all_tools("TEST_COMPLETENESS")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            report = loop.run_until_complete(run_test())
        finally:
            loop.close()
        
        # Verify required fields exist
        assert hasattr(report, 'healthy_count'), "Missing healthy_count"
        assert hasattr(report, 'unhealthy_count'), "Missing unhealthy_count"
        assert hasattr(report, 'total_check_duration_ms'), "Missing total_check_duration_ms"
        assert hasattr(report, 'total_tools'), "Missing total_tools"
        assert hasattr(report, 'critical_tools_healthy'), "Missing critical_tools_healthy"
        assert hasattr(report, 'tool_results'), "Missing tool_results"
        
        # Verify counts are consistent
        total_counted = (
            report.healthy_count + 
            report.unhealthy_count + 
            report.timeout_count + 
            report.error_count
        )
        assert total_counted == report.total_tools, (
            f"Counts don't add up: {total_counted} != {report.total_tools}"
        )
        
        # Verify duration is positive
        assert report.total_check_duration_ms >= 0, (
            f"Duration should be non-negative: {report.total_check_duration_ms}"
        )
    
    def test_report_has_correlation_id(self) -> None:
        """
        **Feature: production-deployment-phase2, Property 17: Health Report Completeness**
        **Validates: Requirements 8.4**
        
        Verify report includes correlation_id for traceability.
        """
        async def mock_caller(server: str, tool: str, args: dict):
            return {"status": "ok"}
        
        module = HealthVerificationModule(mcp_tool_caller=mock_caller)
        test_correlation_id = "TEST_CORRELATION_12345"
        
        async def run_test():
            return await module.ping_all_tools(test_correlation_id)
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            report = loop.run_until_complete(run_test())
        finally:
            loop.close()
        
        assert report.correlation_id == test_correlation_id, (
            f"Correlation ID mismatch: {report.correlation_id}"
        )


# =============================================================================
# PROPERTY 18: Critical Tool Gating
# **Feature: production-deployment-phase2, Property 18: Critical Tool Gating**
# **Validates: Requirements 8.5**
# =============================================================================

class TestCriticalToolGating:
    """
    Property 18: Critical Tool Gating
    
    For any health report where any critical tool is UNHEALTHY, the system
    SHALL prevent trading operations from starting.
    """
    
    def test_critical_tools_defined(self) -> None:
        """
        **Feature: production-deployment-phase2, Property 18: Critical Tool Gating**
        **Validates: Requirements 8.5**
        
        Verify critical tools are properly defined.
        """
        assert len(CRITICAL_TOOLS) >= 3, (
            f"Should have at least 3 critical tools, got {len(CRITICAL_TOOLS)}"
        )
        assert "get_bot_vitals" in CRITICAL_TOOLS, "get_bot_vitals must be critical"
        assert "explain_last_trade" in CRITICAL_TOOLS, "explain_last_trade must be critical"
        assert "ml_analyze_reasoning" in CRITICAL_TOOLS, "ml_analyze_reasoning must be critical"
    
    @settings(max_examples=100)
    @given(
        failing_critical=st.sampled_from(CRITICAL_TOOLS)
    )
    def test_unhealthy_critical_blocks_trading(self, failing_critical: str) -> None:
        """
        **Feature: production-deployment-phase2, Property 18: Critical Tool Gating**
        **Validates: Requirements 8.5**
        
        Verify that any unhealthy critical tool blocks trading.
        """
        async def selective_caller(server: str, tool: str, args: dict):
            if tool == failing_critical:
                raise Exception(f"Critical tool {tool} failed")
            return {"status": "ok"}
        
        module = HealthVerificationModule(mcp_tool_caller=selective_caller)
        
        async def run_test():
            return await module.ping_all_tools("TEST_CRITICAL_GATE")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            report = loop.run_until_complete(run_test())
        finally:
            loop.close()
        
        # Trading should be blocked
        assert not report.can_start_trading, (
            f"Trading should be blocked when {failing_critical} is unhealthy"
        )
        assert not report.critical_tools_healthy, (
            "critical_tools_healthy should be False"
        )
        assert failing_critical in report.unhealthy_critical_tools, (
            f"{failing_critical} should be in unhealthy_critical_tools"
        )
    
    def test_all_critical_healthy_allows_trading(self) -> None:
        """
        **Feature: production-deployment-phase2, Property 18: Critical Tool Gating**
        **Validates: Requirements 8.5**
        
        Verify that trading is allowed when all critical tools are healthy.
        """
        async def all_healthy_caller(server: str, tool: str, args: dict):
            return {"status": "ok"}
        
        module = HealthVerificationModule(mcp_tool_caller=all_healthy_caller)
        
        async def run_test():
            return await module.ping_all_tools("TEST_ALL_HEALTHY")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            report = loop.run_until_complete(run_test())
        finally:
            loop.close()
        
        # Trading should be allowed
        assert report.can_start_trading, "Trading should be allowed when all healthy"
        assert report.critical_tools_healthy, "critical_tools_healthy should be True"
        assert len(report.unhealthy_critical_tools) == 0, (
            "No critical tools should be unhealthy"
        )
    
    def test_non_critical_failure_allows_trading(self) -> None:
        """
        **Feature: production-deployment-phase2, Property 18: Critical Tool Gating**
        **Validates: Requirements 8.5**
        
        Verify that non-critical tool failures don't block trading.
        """
        # Pick a non-critical tool
        non_critical = None
        for tool in AURA_FULL_TOOLS:
            if tool not in CRITICAL_TOOLS:
                non_critical = tool
                break
        
        assert non_critical is not None, "Should have non-critical tools"
        
        async def non_critical_fail_caller(server: str, tool: str, args: dict):
            if tool == non_critical:
                raise Exception(f"Non-critical tool {tool} failed")
            return {"status": "ok"}
        
        module = HealthVerificationModule(mcp_tool_caller=non_critical_fail_caller)
        
        async def run_test():
            return await module.ping_all_tools("TEST_NON_CRITICAL")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            report = loop.run_until_complete(run_test())
        finally:
            loop.close()
        
        # Trading should still be allowed
        assert report.can_start_trading, (
            f"Trading should be allowed when only {non_critical} fails"
        )
        assert report.critical_tools_healthy, (
            "critical_tools_healthy should be True"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

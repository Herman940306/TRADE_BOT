"""
Health Verification Module - 78-Tool Diagnostic System

Reliability Level: L6 Critical
Input Constraints: Valid MCP connections required
Side Effects: Network I/O, may block trading operations

This module implements comprehensive health verification for all 78 MCP tools:
- Sequential ping of all tools with 5-second SLA
- Critical tool gating (trading blocked if any critical tool unhealthy)
- Complete HealthReport generation for audit logs

Python 3.8 Compatible - No union type hints (X | None)
PRIVACY: No personal data in code.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Callable, Awaitable
from enum import Enum
import asyncio
import time
import logging
from datetime import datetime, timezone

# Configure logging with unique error codes
logger = logging.getLogger("health_verification")


# =============================================================================
# CONSTANTS
# =============================================================================

# Ping timeout in seconds
PING_TIMEOUT_SECONDS = 5

# Error codes
ERROR_TOOL_PING_TIMEOUT = "TOOL_PING_TIMEOUT"
ERROR_TOOL_PING_FAIL = "TOOL_PING_FAIL"
ERROR_CRITICAL_UNHEALTHY = "CRITICAL_UNHEALTHY"

# Critical tools that must be healthy for trading
CRITICAL_TOOLS = [
    # Trading Oversight (aura-bridge)
    "get_bot_vitals",
    "explain_last_trade",
    # Intelligence Layer (aura-full)
    "ml_analyze_reasoning",
]

# Complete 78-tool registry
AURA_BRIDGE_TOOLS = [
    "get_bot_vitals",
    "explain_last_trade",
]

AURA_FULL_TOOLS = [
    # Core Gateway (12)
    "ide_agents_health",
    "ide_agents_healthz",
    "ide_agents_readyz",
    "ide_agents_metrics_snapshot",
    "ide_agents_run_command",
    "ide_agents_list_entities",
    "ide_agents_fetch_doc",
    "ide_agents_command",
    "ide_agents_catalog",
    "ide_agents_resource",
    "ide_agents_prompt",
    "ide_agents_server_instructions",
    # ML Intelligence (15)
    "ml_analyze_emotion",
    "ml_get_predictions",
    "ml_get_learning_insights",
    "ml_analyze_reasoning",
    "ml_get_personality_profile",
    "ml_adjust_personality",
    "ml_get_system_status",
    "ml_calibrate_confidence",
    "ml_rank_predictions_rlhf",
    "ml_record_prediction_outcome",
    "ml_get_calibration_metrics",
    "ml_get_rlhf_metrics",
    "ml_behavioral_baseline_check",
    "ml_trigger_auto_adaptation",
    "ml_get_ultra_dashboard",
    # GitHub Integration (3)
    "github_repos",
    "github_rank_repos",
    "github_rank_all",
    # ULTRA Semantic (2)
    "ultra_rank",
    "ultra_calibrate",
    # Debate Engine (4)
    "debate_start",
    "debate_submit",
    "debate_judge",
    "debate_history",
    # DAG Workflow (3)
    "dag_create",
    "dag_execute",
    "dag_visualize",
    # Risk & Approval (3)
    "risk_analyze",
    "risk_route",
    "risk_history",
    # Role Engine (5)
    "role_list",
    "role_get",
    "role_check",
    "role_assign",
    "role_evaluate",
    # RAG Vector DB (5)
    "rag_query",
    "rag_upsert",
    "rag_delete",
    "rag_search",
    "rag_status",
    # Ollama LLM (5)
    "ollama_consult",
    "ollama_list_models",
    "ollama_pull_model",
    "ollama_model_info",
    "ollama_health",
    # Security & Audit (4)
    "security_anomalies",
    "reload",
    "check_pii",
    "get_security_audit",
    # Audio I/O (5)
    "speech_to_text",
    "text_to_speech",
    "get_stt_status",
    "get_tts_status",
    "audio_health",
    # Green Computing (3)
    "check_carbon_intensity",
    "schedule_green_job",
    "get_carbon_budget",
    # WASM & Enclave (3)
    "list_wasm_plugins",
    "execute_wasm_plugin",
    "get_enclave_status",
    # Observability (4)
    "get_metrics",
    "query_traces",
    "get_alerts",
    "get_dashboard_url",
]


# =============================================================================
# ENUMS
# =============================================================================

class ToolHealth(Enum):
    """
    Tool health status.
    
    Reliability Level: L5 High
    """
    HEALTHY = "HEALTHY"
    UNHEALTHY = "UNHEALTHY"
    TIMEOUT = "TIMEOUT"
    ERROR = "ERROR"


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class ToolHealthResult:
    """
    Result of a single tool health check.
    
    Reliability Level: L5 High
    Input Constraints: None
    Side Effects: None
    """
    tool_name: str
    server: str  # "aura-bridge" or "aura-full"
    health: ToolHealth
    response_time_ms: int
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    timestamp_utc: Optional[str] = None


@dataclass
class HealthReport:
    """
    Complete health verification report.
    
    Reliability Level: L6 Critical
    Input Constraints: None
    Side Effects: None
    """
    healthy_count: int
    unhealthy_count: int
    timeout_count: int
    error_count: int
    total_tools: int
    total_check_duration_ms: int
    critical_tools_healthy: bool
    can_start_trading: bool
    tool_results: List[ToolHealthResult]
    unhealthy_critical_tools: List[str]
    report_timestamp_utc: str
    correlation_id: str


# =============================================================================
# HEALTH VERIFICATION MODULE
# =============================================================================

class HealthVerificationModule:
    """
    Comprehensive health verification for all 78 MCP tools.
    
    Reliability Level: L6 Critical
    Input Constraints: Valid MCP connections required
    Side Effects: Network I/O only
    
    Implements:
    - Sequential ping of all 78 tools
    - 5-second timeout per tool (Property 16)
    - Critical tool gating (Property 18)
    - Complete HealthReport generation (Property 17)
    """
    
    # Critical tools that must be healthy for trading
    CRITICAL_TOOLS = CRITICAL_TOOLS
    
    def __init__(
        self,
        mcp_tool_caller: Optional[Callable[[str, str, Dict[str, Any]], Awaitable[Any]]] = None,
        ping_timeout_seconds: int = PING_TIMEOUT_SECONDS
    ) -> None:
        """
        Initialize Health Verification Module.
        
        Args:
            mcp_tool_caller: Async callback to invoke MCP tools (server, tool, args)
            ping_timeout_seconds: Timeout for each tool ping (default: 5s)
        """
        self._mcp_tool_caller = mcp_tool_caller
        self._ping_timeout = ping_timeout_seconds
        self._last_report: Optional[HealthReport] = None
    
    @property
    def ping_timeout(self) -> int:
        """Get ping timeout in seconds."""
        return self._ping_timeout
    
    def get_all_tools(self) -> List[tuple]:
        """
        Get complete list of all 78 tools with their servers.
        
        Returns:
            List of (tool_name, server) tuples
        """
        tools = []  # type: List[tuple]
        
        for tool in AURA_BRIDGE_TOOLS:
            tools.append((tool, "aura-bridge"))
        
        for tool in AURA_FULL_TOOLS:
            tools.append((tool, "aura-full"))
        
        return tools
    
    def get_tool_count(self) -> int:
        """Get total number of tools."""
        return len(AURA_BRIDGE_TOOLS) + len(AURA_FULL_TOOLS)
    
    async def ping_tool(
        self,
        tool_name: str,
        server: str,
        correlation_id: str
    ) -> ToolHealthResult:
        """
        Ping a single tool and measure response time.
        
        Reliability Level: L5 High
        Input Constraints: Valid tool_name and server required
        Side Effects: Network I/O
        
        Args:
            tool_name: Name of the tool to ping
            server: MCP server ("aura-bridge" or "aura-full")
            correlation_id: Tracking ID for audit
            
        Returns:
            ToolHealthResult with health status and response time
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        start_time_ms = int(time.time() * 1000)
        
        if self._mcp_tool_caller is None:
            return ToolHealthResult(
                tool_name=tool_name,
                server=server,
                health=ToolHealth.ERROR,
                response_time_ms=0,
                error_code=ERROR_TOOL_PING_FAIL,
                error_message="No MCP tool caller configured",
                timestamp_utc=timestamp
            )
        
        try:
            # Attempt to invoke tool with timeout
            await asyncio.wait_for(
                self._mcp_tool_caller(server, tool_name, {}),
                timeout=self._ping_timeout
            )
            
            end_time_ms = int(time.time() * 1000)
            response_time_ms = end_time_ms - start_time_ms
            
            logger.debug(
                f"[PING_SUCCESS] tool={tool_name} server={server} "
                f"response_time_ms={response_time_ms} correlation_id={correlation_id}"
            )
            
            return ToolHealthResult(
                tool_name=tool_name,
                server=server,
                health=ToolHealth.HEALTHY,
                response_time_ms=response_time_ms,
                timestamp_utc=timestamp
            )
            
        except asyncio.TimeoutError:
            end_time_ms = int(time.time() * 1000)
            response_time_ms = end_time_ms - start_time_ms
            
            logger.warning(
                f"[{ERROR_TOOL_PING_TIMEOUT}] tool={tool_name} server={server} "
                f"timeout={self._ping_timeout}s correlation_id={correlation_id}"
            )
            
            return ToolHealthResult(
                tool_name=tool_name,
                server=server,
                health=ToolHealth.TIMEOUT,
                response_time_ms=response_time_ms,
                error_code=ERROR_TOOL_PING_TIMEOUT,
                error_message=f"Timeout after {self._ping_timeout}s",
                timestamp_utc=timestamp
            )
            
        except Exception as e:
            end_time_ms = int(time.time() * 1000)
            response_time_ms = end_time_ms - start_time_ms
            
            logger.error(
                f"[{ERROR_TOOL_PING_FAIL}] tool={tool_name} server={server} "
                f"error={str(e)} correlation_id={correlation_id}"
            )
            
            return ToolHealthResult(
                tool_name=tool_name,
                server=server,
                health=ToolHealth.ERROR,
                response_time_ms=response_time_ms,
                error_code=ERROR_TOOL_PING_FAIL,
                error_message=str(e),
                timestamp_utc=timestamp
            )

    async def ping_all_tools(
        self,
        correlation_id: str
    ) -> HealthReport:
        """
        Ping all 78 MCP tools and generate health report.
        
        Reliability Level: L6 Critical
        Input Constraints: correlation_id required
        Side Effects: Network I/O, updates last_report
        
        Args:
            correlation_id: Tracking ID for audit trail
            
        Returns:
            HealthReport with complete health status
        """
        start_time_ms = int(time.time() * 1000)
        timestamp = datetime.now(timezone.utc).isoformat()
        
        logger.info(
            f"[HEALTH_CHECK_START] total_tools={self.get_tool_count()} "
            f"correlation_id={correlation_id}"
        )
        
        all_tools = self.get_all_tools()
        tool_results = []  # type: List[ToolHealthResult]
        
        # Ping each tool sequentially (Property 15)
        for tool_name, server in all_tools:
            result = await self.ping_tool(tool_name, server, correlation_id)
            tool_results.append(result)
        
        end_time_ms = int(time.time() * 1000)
        total_duration_ms = end_time_ms - start_time_ms
        
        # Count results by status
        healthy_count = sum(
            1 for r in tool_results if r.health == ToolHealth.HEALTHY
        )
        unhealthy_count = sum(
            1 for r in tool_results if r.health == ToolHealth.UNHEALTHY
        )
        timeout_count = sum(
            1 for r in tool_results if r.health == ToolHealth.TIMEOUT
        )
        error_count = sum(
            1 for r in tool_results if r.health == ToolHealth.ERROR
        )
        
        # Check critical tools (Property 18)
        unhealthy_critical = []  # type: List[str]
        for result in tool_results:
            if result.tool_name in self.CRITICAL_TOOLS:
                if result.health != ToolHealth.HEALTHY:
                    unhealthy_critical.append(result.tool_name)
        
        critical_healthy = len(unhealthy_critical) == 0
        can_trade = critical_healthy
        
        # Generate report (Property 17)
        report = HealthReport(
            healthy_count=healthy_count,
            unhealthy_count=unhealthy_count,
            timeout_count=timeout_count,
            error_count=error_count,
            total_tools=len(all_tools),
            total_check_duration_ms=total_duration_ms,
            critical_tools_healthy=critical_healthy,
            can_start_trading=can_trade,
            tool_results=tool_results,
            unhealthy_critical_tools=unhealthy_critical,
            report_timestamp_utc=timestamp,
            correlation_id=correlation_id
        )
        
        self._last_report = report
        
        # Log summary
        if critical_healthy:
            logger.info(
                f"[HEALTH_CHECK_COMPLETE] healthy={healthy_count}/{len(all_tools)} "
                f"critical_ok=True can_trade=True "
                f"duration_ms={total_duration_ms} correlation_id={correlation_id}"
            )
        else:
            logger.critical(
                f"[{ERROR_CRITICAL_UNHEALTHY}] healthy={healthy_count}/{len(all_tools)} "
                f"critical_ok=False can_trade=False "
                f"unhealthy_critical={unhealthy_critical} "
                f"duration_ms={total_duration_ms} correlation_id={correlation_id}"
            )
        
        return report
    
    def can_start_trading(
        self,
        report: HealthReport
    ) -> bool:
        """
        Check if trading can start based on health report.
        
        Reliability Level: L6 Critical
        Input Constraints: Valid HealthReport required
        Side Effects: None
        
        Args:
            report: Health report to evaluate
            
        Returns:
            True if all critical tools are healthy
        """
        return report.critical_tools_healthy
    
    def is_tool_healthy(
        self,
        result: ToolHealthResult
    ) -> bool:
        """
        Check if a tool is healthy.
        
        Args:
            result: Tool health result to check
            
        Returns:
            True if tool responded within timeout
        """
        return result.health == ToolHealth.HEALTHY
    
    def is_critical_tool(self, tool_name: str) -> bool:
        """
        Check if a tool is in the critical list.
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            True if tool is critical for trading
        """
        return tool_name in self.CRITICAL_TOOLS
    
    def get_last_report(self) -> Optional[HealthReport]:
        """Get the most recent health report."""
        return self._last_report
    
    def get_report_summary(self, report: HealthReport) -> Dict[str, Any]:
        """
        Generate a summary dict for logging/display.
        
        Args:
            report: Health report to summarize
            
        Returns:
            Dict with summary statistics
        """
        return {
            "total_tools": report.total_tools,
            "healthy": report.healthy_count,
            "unhealthy": report.unhealthy_count,
            "timeout": report.timeout_count,
            "error": report.error_count,
            "critical_healthy": report.critical_tools_healthy,
            "can_trade": report.can_start_trading,
            "unhealthy_critical": report.unhealthy_critical_tools,
            "duration_ms": report.total_check_duration_ms,
            "timestamp": report.report_timestamp_utc,
            "correlation_id": report.correlation_id
        }
    
    async def quick_critical_check(
        self,
        correlation_id: str
    ) -> tuple:
        """
        Quick check of critical tools only.
        
        Reliability Level: L6 Critical
        Input Constraints: correlation_id required
        Side Effects: Network I/O
        
        Args:
            correlation_id: Tracking ID
            
        Returns:
            Tuple of (all_healthy, unhealthy_tools)
        """
        unhealthy = []  # type: List[str]
        
        for tool_name in self.CRITICAL_TOOLS:
            # Determine server
            if tool_name in AURA_BRIDGE_TOOLS:
                server = "aura-bridge"
            else:
                server = "aura-full"
            
            result = await self.ping_tool(tool_name, server, correlation_id)
            
            if result.health != ToolHealth.HEALTHY:
                unhealthy.append(tool_name)
        
        all_healthy = len(unhealthy) == 0
        
        if not all_healthy:
            logger.warning(
                f"[CRITICAL_CHECK_FAIL] unhealthy={unhealthy} "
                f"correlation_id={correlation_id}"
            )
        
        return (all_healthy, unhealthy)
    
    # =========================================================================
    # SPRINT 6: OPERATIONAL GATING INTEGRATION
    # =========================================================================
    
    def receive_gating_signal(
        self,
        gating_result: Any  # GatingResult from operational_gating
    ) -> None:
        """
        Receive and process operational gating signal.
        
        Reliability Level: L6 Critical
        Input Constraints: Valid GatingResult required
        Side Effects: Updates internal gating state
        
        Sprint 6: BudgetGuard-ZAR Integration
        
        Args:
            gating_result: GatingResult from OperationalGatingModule
        """
        # Import here to avoid circular dependency
        from app.logic.operational_gating import GatingSignal
        
        self._last_gating_result = gating_result
        
        # Set HARD_STOP state
        if gating_result.signal == GatingSignal.HARD_STOP:
            self._hard_stop_active = True
            self._neutral_state_active = False
            logger.critical(
                f"[HARD_STOP_RECEIVED] reason={gating_result.reason} "
                f"risk_level={gating_result.risk_level.value if gating_result.risk_level else 'N/A'} "
                f"correlation_id={gating_result.correlation_id}"
            )
        
        # Set NEUTRAL_STATE for stale data
        elif gating_result.signal == GatingSignal.STALE_DATA:
            self._hard_stop_active = False
            self._neutral_state_active = True
            logger.warning(
                f"[NEUTRAL_STATE_ENTERED] reason={gating_result.reason} "
                f"data_age_hours={gating_result.data_age_hours} "
                f"correlation_id={gating_result.correlation_id}"
            )
        
        # Set RDS_EXCEEDED (blocks trades but not full HARD_STOP)
        elif gating_result.signal == GatingSignal.RDS_EXCEEDED:
            self._rds_exceeded = True
            logger.warning(
                f"[RDS_EXCEEDED_RECEIVED] projected_cost={gating_result.projected_cost} "
                f"rds_limit={gating_result.rds_limit} "
                f"correlation_id={gating_result.correlation_id}"
            )
        
        # Clear states on ALLOW
        elif gating_result.signal == GatingSignal.ALLOW:
            self._hard_stop_active = False
            self._neutral_state_active = False
            self._rds_exceeded = False
            logger.info(
                f"[GATING_CLEARED] signal=ALLOW "
                f"correlation_id={gating_result.correlation_id}"
            )
    
    def is_hard_stopped(self) -> bool:
        """
        Check if HARD_STOP is active.
        
        Returns:
            True if HARD_STOP signal is active
        """
        return getattr(self, '_hard_stop_active', False)
    
    def is_neutral_state(self) -> bool:
        """
        Check if Neutral State is active (stale data).
        
        Returns:
            True if Neutral State is active
        """
        return getattr(self, '_neutral_state_active', False)
    
    def is_rds_exceeded(self) -> bool:
        """
        Check if RDS limit is exceeded.
        
        Returns:
            True if RDS exceeded signal is active
        """
        return getattr(self, '_rds_exceeded', False)
    
    def clear_hard_stop(self) -> None:
        """
        Clear HARD_STOP state (for risk level recovery).
        
        Reliability Level: L6 Critical
        Side Effects: Clears HARD_STOP flag
        """
        self._hard_stop_active = False
        logger.info("[HARD_STOP_CLEARED] Manual or automatic recovery")
    
    def clear_neutral_state(self) -> None:
        """
        Clear Neutral State (when fresh data arrives).
        
        Reliability Level: L6 Critical
        Side Effects: Clears Neutral State flag
        """
        self._neutral_state_active = False
        logger.info("[NEUTRAL_STATE_CLEARED] Fresh data received")
    
    def can_start_trading_with_gating(
        self,
        report: Optional['HealthReport'] = None
    ) -> bool:
        """
        Check if trading can start considering both health and gating.
        
        Reliability Level: L6 Critical
        
        Args:
            report: Optional health report to check
            
        Returns:
            True if all critical tools healthy AND no gating blocks
        """
        # Check gating states first
        if self.is_hard_stopped():
            logger.warning("[TRADING_BLOCKED] HARD_STOP active")
            return False
        
        if self.is_neutral_state():
            logger.warning("[TRADING_BLOCKED] Neutral State active (stale data)")
            return False
        
        if self.is_rds_exceeded():
            logger.warning("[TRADING_BLOCKED] RDS exceeded")
            return False
        
        # Check health report if provided
        if report is not None:
            return self.can_start_trading(report)
        
        # Check last report if available
        if self._last_report is not None:
            return self.can_start_trading(self._last_report)
        
        # No report available - allow by default
        return True
    
    def get_last_gating_result(self) -> Optional[Any]:
        """Get the most recent gating result."""
        return getattr(self, '_last_gating_result', None)


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def create_health_module(
    mcp_tool_caller: Optional[Callable[[str, str, Dict[str, Any]], Awaitable[Any]]] = None,
    ping_timeout_seconds: int = PING_TIMEOUT_SECONDS
) -> HealthVerificationModule:
    """
    Factory function to create Health Verification Module.
    
    Reliability Level: L5 High
    
    Args:
        mcp_tool_caller: MCP tool invoker callback
        ping_timeout_seconds: Timeout per tool (default: 5s)
        
    Returns:
        Configured HealthVerificationModule
    """
    return HealthVerificationModule(
        mcp_tool_caller=mcp_tool_caller,
        ping_timeout_seconds=ping_timeout_seconds
    )

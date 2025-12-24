"""
Operational Gating Module - BudgetGuard ZAR Integration

Reliability Level: L6 Critical
Input Constraints: Valid BudgetGuard JSON required
Side Effects: May block trading, logs to audit

This module implements the Financial Air-Gap between trading logic and
operational infrastructure costs by integrating with BudgetGuard ZAR:
- Parse BudgetGuard JSON reports with Decimal precision
- Evaluate risk levels (CRITICAL/OVER_BUDGET trigger HARD_STOP)
- Enforce RDS (Recommended Daily Spend) limits
- Detect stale data (>24 hours) and trigger Neutral State

Python 3.8 Compatible - No union type hints (X | None)
PRIVACY: No personal data in code.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from decimal import Decimal, ROUND_HALF_EVEN, InvalidOperation
from enum import Enum
from typing import Optional, List, Dict, Any
import json
import logging

# Configure logging with unique error codes
logger = logging.getLogger("operational_gating")


# =============================================================================
# CONSTANTS
# =============================================================================

# Staleness threshold in hours
STALENESS_THRESHOLD_HOURS = 24

# Error codes
ERROR_BUDGET_DATA_STALE = "OG-001-BUDGET_DATA_STALE"
ERROR_BUDGET_PARSE_FAIL = "OG-002-BUDGET_PARSE_FAIL"
ERROR_RDS_EXCEEDED = "OG-003-RDS_EXCEEDED"
ERROR_HARD_STOP_ACTIVE = "OG-004-HARD_STOP_ACTIVE"
ERROR_OPERATIONAL_COST_UNAVAILABLE = "OG-005-OPERATIONAL_COST_UNAVAILABLE"


# =============================================================================
# ENUMS
# =============================================================================

class RiskLevel(Enum):
    """
    Risk classification from BudgetGuard ZAR.
    
    Reliability Level: L6 Critical
    
    Attributes:
        HEALTHY: Spend pace within acceptable range of time pace
        WARNING: Spend pace exceeds time pace by 5-15 percentage points
        CRITICAL: Spend pace exceeds time pace by more than 15 percentage points
        OVER_BUDGET: Current spend has exceeded the monthly budget
    """
    HEALTHY = "HEALTHY"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    OVER_BUDGET = "OVER_BUDGET"


class GatingSignal(Enum):
    """
    Operational gating signal types.
    
    Reliability Level: L6 Critical
    
    Attributes:
        ALLOW: Trading permitted
        HARD_STOP: Immediate trade blocking (CRITICAL/OVER_BUDGET)
        RDS_EXCEEDED: Daily spend limit exceeded
        STALE_DATA: Budget data older than 24 hours
    """
    ALLOW = "ALLOW"
    HARD_STOP = "HARD_STOP"
    RDS_EXCEEDED = "RDS_EXCEEDED"
    STALE_DATA = "STALE_DATA"


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class CampaignAnalysis:
    """
    Individual campaign analysis from BudgetGuard.
    
    Reliability Level: L6 Critical
    Input Constraints: All monetary values must be decimal.Decimal
    Side Effects: None
    """
    name: str
    monthly_budget: Decimal
    current_spend: Decimal
    rds: Decimal
    spend_percentage: Decimal
    time_percentage: Decimal
    risk_level: RiskLevel
    days_remaining: int
    gross_budget: Optional[Decimal] = None


@dataclass
class BudgetReport:
    """
    Parsed BudgetGuard JSON structure.
    
    Reliability Level: L6 Critical
    Input Constraints: All monetary values must be decimal.Decimal
    Side Effects: None
    """
    timestamp: datetime
    version: str
    total_budget: Decimal
    total_spend: Decimal
    critical_count: int
    warning_count: int
    campaign_count: int
    campaigns: List[CampaignAnalysis]


@dataclass
class GatingResult:
    """
    Result of operational gating evaluation.
    
    Reliability Level: L6 Critical
    Input Constraints: correlation_id required
    Side Effects: None
    """
    signal: GatingSignal
    can_trade: bool
    reason: str
    risk_level: Optional[RiskLevel]
    rds_limit: Optional[Decimal]
    projected_cost: Optional[Decimal]
    data_age_hours: Decimal
    correlation_id: str
    timestamp_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())



# =============================================================================
# OPERATIONAL GATING MODULE
# =============================================================================

class OperationalGatingModule:
    """
    Parses BudgetGuard JSON and enforces operational cost limits.
    
    Reliability Level: L6 Critical
    Input Constraints: Valid BudgetGuard JSON required
    Side Effects: May block trading, logs to audit
    
    Implements:
    - JSON parsing with Decimal precision (Property 21)
    - HARD_STOP on CRITICAL/OVER_BUDGET (Property 19)
    - Staleness detection >24 hours (Property 20)
    - RDS enforcement (Property 22)
    """
    
    STALENESS_THRESHOLD_HOURS: int = STALENESS_THRESHOLD_HOURS
    
    def __init__(self) -> None:
        """
        Initialize Operational Gating Module.
        """
        self._last_report: Optional[BudgetReport] = None
        self._last_gating_result: Optional[GatingResult] = None
    
    def parse_budget_report(
        self,
        json_str: str,
        correlation_id: str
    ) -> BudgetReport:
        """
        Parse BudgetGuard JSON into BudgetReport.
        
        Reliability Level: L6 Critical
        Input Constraints: Valid JSON string required
        Side Effects: Logs parse errors
        
        Args:
            json_str: Raw JSON string from BudgetGuard
            correlation_id: Tracking ID for audit
            
        Returns:
            BudgetReport with Decimal values
            
        Raises:
            ValueError: If JSON is malformed or missing required fields
        """
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(
                f"[{ERROR_BUDGET_PARSE_FAIL}] JSON decode error: {str(e)} "
                f"correlation_id={correlation_id}"
            )
            raise ValueError(f"Invalid JSON: {str(e)}")
        
        try:
            metadata = data["metadata"]
            summary = data["summary"]
            
            # Parse timestamp
            timestamp = datetime.fromisoformat(metadata["timestamp"])
            
            # Parse campaigns
            campaigns = []  # type: List[CampaignAnalysis]
            for campaign_data in data.get("campaigns", []):
                campaign_info = campaign_data["campaign"]
                analysis_info = campaign_data["analysis"]
                
                gross_budget = None
                if "gross_budget" in campaign_info:
                    gross_budget = Decimal(campaign_info["gross_budget"])
                
                campaign = CampaignAnalysis(
                    name=campaign_info["name"],
                    monthly_budget=Decimal(campaign_info["monthly_budget"]),
                    current_spend=Decimal(campaign_info["current_spend"]),
                    rds=Decimal(analysis_info["rds"]),
                    spend_percentage=Decimal(analysis_info["spend_percentage"]),
                    time_percentage=Decimal(analysis_info["time_percentage"]),
                    risk_level=RiskLevel(analysis_info["risk_level"]),
                    days_remaining=int(analysis_info["days_remaining"]),
                    gross_budget=gross_budget
                )
                campaigns.append(campaign)
            
            report = BudgetReport(
                timestamp=timestamp,
                version=metadata["version"],
                total_budget=Decimal(summary["total_budget"]),
                total_spend=Decimal(summary["total_spend"]),
                critical_count=int(summary["critical_count"]),
                warning_count=int(summary["warning_count"]),
                campaign_count=int(summary.get("campaign_count", len(campaigns))),
                campaigns=campaigns
            )
            
            self._last_report = report
            
            logger.info(
                f"[BUDGET_REPORT_PARSED] total_budget={report.total_budget} "
                f"total_spend={report.total_spend} critical={report.critical_count} "
                f"correlation_id={correlation_id}"
            )
            
            return report
            
        except (KeyError, InvalidOperation) as e:
            logger.error(
                f"[{ERROR_BUDGET_PARSE_FAIL}] Missing or invalid field: {str(e)} "
                f"correlation_id={correlation_id}"
            )
            raise ValueError(f"Invalid BudgetGuard JSON structure: {str(e)}")
    
    def should_hard_stop(self, risk_level: RiskLevel) -> bool:
        """
        Check if risk level requires HARD_STOP.
        
        Reliability Level: L6 Critical
        Input Constraints: Valid RiskLevel enum
        Side Effects: None
        
        Args:
            risk_level: Risk level from BudgetGuard
            
        Returns:
            True if CRITICAL or OVER_BUDGET
        """
        return risk_level in (RiskLevel.CRITICAL, RiskLevel.OVER_BUDGET)
    
    def is_data_stale(
        self,
        timestamp: datetime,
        reference_time: Optional[datetime] = None
    ) -> bool:
        """
        Check if budget data is stale (>24 hours old).
        
        Reliability Level: L6 Critical
        Input Constraints: Valid datetime required
        Side Effects: None
        
        Args:
            timestamp: Timestamp from BudgetGuard report
            reference_time: Current time for comparison (defaults to now)
            
        Returns:
            True if data is older than 24 hours
        """
        if reference_time is None:
            reference_time = datetime.now(timezone.utc)
        
        # Ensure both timestamps are timezone-aware
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        if reference_time.tzinfo is None:
            reference_time = reference_time.replace(tzinfo=timezone.utc)
        
        age = reference_time - timestamp
        threshold = timedelta(hours=self.STALENESS_THRESHOLD_HOURS)
        
        return age > threshold
    
    def get_data_age_hours(
        self,
        timestamp: datetime,
        reference_time: Optional[datetime] = None
    ) -> Decimal:
        """
        Calculate age of budget data in hours.
        
        Args:
            timestamp: Timestamp from BudgetGuard report
            reference_time: Current time for comparison
            
        Returns:
            Age in hours as Decimal
        """
        if reference_time is None:
            reference_time = datetime.now(timezone.utc)
        
        # Ensure both timestamps are timezone-aware
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        if reference_time.tzinfo is None:
            reference_time = reference_time.replace(tzinfo=timezone.utc)
        
        age_seconds = (reference_time - timestamp).total_seconds()
        age_hours = Decimal(str(age_seconds)) / Decimal("3600")
        
        return age_hours.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
    
    def get_aggregate_rds(self, report: BudgetReport) -> Decimal:
        """
        Calculate aggregate RDS from all campaigns.
        
        Reliability Level: L6 Critical
        Input Constraints: Valid BudgetReport required
        Side Effects: None
        
        Args:
            report: Parsed BudgetGuard report
            
        Returns:
            Sum of all campaign RDS values
        """
        total_rds = Decimal("0.00")
        
        for campaign in report.campaigns:
            total_rds += campaign.rds
        
        return total_rds.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
    
    def get_worst_risk_level(self, report: BudgetReport) -> RiskLevel:
        """
        Get the worst (highest severity) risk level from all campaigns.
        
        Args:
            report: Parsed BudgetGuard report
            
        Returns:
            Worst risk level found
        """
        # Priority order: OVER_BUDGET > CRITICAL > WARNING > HEALTHY
        priority = {
            RiskLevel.HEALTHY: 0,
            RiskLevel.WARNING: 1,
            RiskLevel.CRITICAL: 2,
            RiskLevel.OVER_BUDGET: 3
        }
        
        worst = RiskLevel.HEALTHY
        
        for campaign in report.campaigns:
            if priority[campaign.risk_level] > priority[worst]:
                worst = campaign.risk_level
        
        return worst
    
    def check_rds_limit(
        self,
        projected_cost: Decimal,
        rds: Decimal
    ) -> bool:
        """
        Check if projected cost exceeds RDS limit.
        
        Reliability Level: L6 Critical
        Input Constraints: Both values must be decimal.Decimal
        Side Effects: None
        
        Args:
            projected_cost: Projected daily infrastructure cost
            rds: Recommended Daily Spend from BudgetGuard
            
        Returns:
            True if projected_cost exceeds rds
        """
        # Zero or negative RDS is implicit HARD_STOP
        if rds <= Decimal("0"):
            return True
        
        return projected_cost > rds
    
    def evaluate_risk(
        self,
        report: BudgetReport,
        projected_cost: Optional[Decimal],
        correlation_id: str,
        reference_time: Optional[datetime] = None
    ) -> GatingResult:
        """
        Evaluate budget report and return gating decision.
        
        Reliability Level: L6 Critical
        Input Constraints: Valid BudgetReport required
        Side Effects: Logs gating decisions
        
        Args:
            report: Parsed BudgetGuard report
            projected_cost: Projected daily infrastructure cost (optional)
            correlation_id: Tracking ID for audit
            reference_time: Current time for staleness check
            
        Returns:
            GatingResult with signal and details
        """
        timestamp_utc = datetime.now(timezone.utc).isoformat()
        data_age_hours = self.get_data_age_hours(report.timestamp, reference_time)
        
        # Check 1: Staleness (Property 20)
        if self.is_data_stale(report.timestamp, reference_time):
            logger.warning(
                f"[{ERROR_BUDGET_DATA_STALE}] data_age_hours={data_age_hours} "
                f"threshold={self.STALENESS_THRESHOLD_HOURS} "
                f"correlation_id={correlation_id}"
            )
            
            result = GatingResult(
                signal=GatingSignal.STALE_DATA,
                can_trade=False,
                reason=f"Budget data is {data_age_hours} hours old (threshold: {self.STALENESS_THRESHOLD_HOURS}h)",
                risk_level=None,
                rds_limit=None,
                projected_cost=projected_cost,
                data_age_hours=data_age_hours,
                correlation_id=correlation_id,
                timestamp_utc=timestamp_utc
            )
            self._last_gating_result = result
            return result
        
        # Check 2: Risk Level (Property 19)
        worst_risk = self.get_worst_risk_level(report)
        
        if self.should_hard_stop(worst_risk):
            logger.critical(
                f"[{ERROR_HARD_STOP_ACTIVE}] risk_level={worst_risk.value} "
                f"critical_count={report.critical_count} "
                f"correlation_id={correlation_id}"
            )
            
            result = GatingResult(
                signal=GatingSignal.HARD_STOP,
                can_trade=False,
                reason=f"Risk level {worst_risk.value} requires HARD_STOP",
                risk_level=worst_risk,
                rds_limit=self.get_aggregate_rds(report),
                projected_cost=projected_cost,
                data_age_hours=data_age_hours,
                correlation_id=correlation_id,
                timestamp_utc=timestamp_utc
            )
            self._last_gating_result = result
            return result
        
        # Check 3: RDS Enforcement (Property 22)
        aggregate_rds = self.get_aggregate_rds(report)
        
        if projected_cost is not None and self.check_rds_limit(projected_cost, aggregate_rds):
            logger.warning(
                f"[{ERROR_RDS_EXCEEDED}] projected_cost={projected_cost} "
                f"rds_limit={aggregate_rds} "
                f"correlation_id={correlation_id}"
            )
            
            result = GatingResult(
                signal=GatingSignal.RDS_EXCEEDED,
                can_trade=False,
                reason=f"Projected cost R {projected_cost} exceeds RDS limit R {aggregate_rds}",
                risk_level=worst_risk,
                rds_limit=aggregate_rds,
                projected_cost=projected_cost,
                data_age_hours=data_age_hours,
                correlation_id=correlation_id,
                timestamp_utc=timestamp_utc
            )
            self._last_gating_result = result
            return result
        
        # All checks passed - ALLOW trading
        logger.info(
            f"[GATING_ALLOW] risk_level={worst_risk.value} "
            f"rds_limit={aggregate_rds} projected_cost={projected_cost} "
            f"correlation_id={correlation_id}"
        )
        
        result = GatingResult(
            signal=GatingSignal.ALLOW,
            can_trade=True,
            reason="All operational checks passed",
            risk_level=worst_risk,
            rds_limit=aggregate_rds,
            projected_cost=projected_cost,
            data_age_hours=data_age_hours,
            correlation_id=correlation_id,
            timestamp_utc=timestamp_utc
        )
        self._last_gating_result = result
        return result
    
    def evaluate_trade_signal(
        self,
        confidence_score: Decimal,
        gating_result: GatingResult,
        correlation_id: str
    ) -> bool:
        """
        Evaluate if a trade signal should be allowed based on gating.
        
        Reliability Level: L6 Critical
        Input Constraints: Valid confidence_score (0-100) and GatingResult
        Side Effects: Logs rejections
        
        Property 19: HARD_STOP blocks all trades regardless of confidence.
        
        Args:
            confidence_score: Trade signal confidence (0-100)
            gating_result: Current gating evaluation result
            correlation_id: Tracking ID for audit
            
        Returns:
            True if trade is allowed, False if blocked
        """
        if not gating_result.can_trade:
            logger.warning(
                f"[TRADE_REJECTED_BY_GATING] confidence={confidence_score} "
                f"signal={gating_result.signal.value} "
                f"reason={gating_result.reason} "
                f"correlation_id={correlation_id}"
            )
            return False
        
        return True
    
    def get_last_report(self) -> Optional[BudgetReport]:
        """Get the most recent parsed budget report."""
        return self._last_report
    
    def get_last_gating_result(self) -> Optional[GatingResult]:
        """Get the most recent gating evaluation result."""
        return self._last_gating_result


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def create_operational_gating_module() -> OperationalGatingModule:
    """
    Factory function to create Operational Gating Module.
    
    Reliability Level: L5 High
    
    Returns:
        Configured OperationalGatingModule
    """
    return OperationalGatingModule()

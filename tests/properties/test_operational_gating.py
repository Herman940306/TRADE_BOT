"""
Property-Based Tests for Operational Gating Module (Sprint 6)

Reliability Level: L6 Critical
Python 3.8 Compatible

Tests the OperationalGatingModule using Hypothesis.
Minimum 100 iterations per property as per design specification.

Properties tested:
- Property 19: Budget Gating Override
- Property 20: Staleness Protection
- Property 21: Net Alpha Decimal Integrity
- Property 22: RDS Enforcement
"""

import json
from datetime import datetime, timezone, timedelta
from decimal import Decimal, ROUND_HALF_EVEN
from typing import Dict, List, Optional

import pytest
from hypothesis import given, settings, assume, reproduce_failure
from hypothesis import strategies as st

# Import modules under test
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from app.logic.operational_gating import (
    OperationalGatingModule,
    RiskLevel,
    GatingSignal,
    BudgetReport,
    CampaignAnalysis,
    GatingResult,
    create_operational_gating_module,
    STALENESS_THRESHOLD_HOURS,
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

# Strategy for generating confidence scores (0-100)
confidence_score_strategy = st.decimals(
    min_value=Decimal("0.00"),
    max_value=Decimal("100.00"),
    places=2,
    allow_nan=False,
    allow_infinity=False
)

# Strategy for generating RDS values
rds_strategy = st.decimals(
    min_value=Decimal("0.00"),
    max_value=Decimal("100000.00"),
    places=2,
    allow_nan=False,
    allow_infinity=False
)

# Strategy for generating positive RDS values
positive_rds_strategy = st.decimals(
    min_value=Decimal("0.01"),
    max_value=Decimal("100000.00"),
    places=2,
    allow_nan=False,
    allow_infinity=False
)

# Strategy for generating percentage values
percentage_strategy = st.decimals(
    min_value=Decimal("0.00"),
    max_value=Decimal("200.00"),
    places=2,
    allow_nan=False,
    allow_infinity=False
)

# Strategy for generating days remaining
days_remaining_strategy = st.integers(min_value=1, max_value=31)

# Strategy for risk levels that trigger HARD_STOP
hard_stop_risk_levels = st.sampled_from([RiskLevel.CRITICAL, RiskLevel.OVER_BUDGET])

# Strategy for risk levels that allow trading
allow_risk_levels = st.sampled_from([RiskLevel.HEALTHY, RiskLevel.WARNING])

# Strategy for all risk levels
all_risk_levels = st.sampled_from(list(RiskLevel))

# Strategy for campaign names
campaign_name_strategy = st.text(
    alphabet=st.characters(whitelist_categories=('L', 'N'), whitelist_characters='_-'),
    min_size=1,
    max_size=50
).filter(lambda x: len(x.strip()) > 0)


def create_campaign_analysis(
    name: str,
    monthly_budget: Decimal,
    current_spend: Decimal,
    rds: Decimal,
    risk_level: RiskLevel,
    days_remaining: int = 14
) -> CampaignAnalysis:
    """Helper to create CampaignAnalysis with calculated percentages."""
    spend_pct = (current_spend / monthly_budget * Decimal("100")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_EVEN
    ) if monthly_budget > 0 else Decimal("0.00")
    
    # Approximate time percentage based on days remaining in a 31-day month
    time_pct = ((Decimal("31") - Decimal(str(days_remaining))) / Decimal("31") * Decimal("100")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_EVEN
    )
    
    return CampaignAnalysis(
        name=name,
        monthly_budget=monthly_budget,
        current_spend=current_spend,
        rds=rds,
        spend_percentage=spend_pct,
        time_percentage=time_pct,
        risk_level=risk_level,
        days_remaining=days_remaining
    )


def create_budget_report(
    campaigns: List[CampaignAnalysis],
    timestamp: Optional[datetime] = None
) -> BudgetReport:
    """Helper to create BudgetReport from campaigns."""
    if timestamp is None:
        timestamp = datetime.now(timezone.utc)
    
    total_budget = sum(c.monthly_budget for c in campaigns)
    total_spend = sum(c.current_spend for c in campaigns)
    critical_count = sum(1 for c in campaigns if c.risk_level == RiskLevel.CRITICAL)
    warning_count = sum(1 for c in campaigns if c.risk_level == RiskLevel.WARNING)
    
    return BudgetReport(
        timestamp=timestamp,
        version="0.1.0",
        total_budget=total_budget,
        total_spend=total_spend,
        critical_count=critical_count,
        warning_count=warning_count,
        campaign_count=len(campaigns),
        campaigns=campaigns
    )


def create_budget_json(report: BudgetReport) -> str:
    """Helper to create JSON string from BudgetReport."""
    data = {
        "metadata": {
            "timestamp": report.timestamp.isoformat(),
            "version": report.version,
            "generated_by": "BudgetGuard ZAR"
        },
        "summary": {
            "total_budget": str(report.total_budget),
            "total_spend": str(report.total_spend),
            "critical_count": report.critical_count,
            "warning_count": report.warning_count,
            "campaign_count": report.campaign_count
        },
        "campaigns": [
            {
                "campaign": {
                    "name": c.name,
                    "monthly_budget": str(c.monthly_budget),
                    "current_spend": str(c.current_spend)
                },
                "analysis": {
                    "rds": str(c.rds),
                    "spend_percentage": str(c.spend_percentage),
                    "time_percentage": str(c.time_percentage),
                    "risk_level": c.risk_level.value,
                    "days_remaining": c.days_remaining
                }
            }
            for c in report.campaigns
        ]
    }
    return json.dumps(data)


# =============================================================================
# PROPERTY 19: Budget Gating Override
# **Feature: budgetguard-integration, Property 19: Budget Gating Override**
# **Validates: Requirements 1.1, 1.2, 1.3, 5.1, 5.2**
# =============================================================================

class TestBudgetGatingOverride:
    """
    Property 19: Budget Gating Override
    
    For any trade signal with any confidence score (0-100), when the 
    operational gating module returns HARD_STOP (due to CRITICAL or 
    OVER_BUDGET risk level), the trade SHALL be rejected regardless 
    of confidence.
    """
    
    @settings(max_examples=100)
    @given(
        confidence=confidence_score_strategy,
        risk_level=hard_stop_risk_levels,
        monthly_budget=decimal_amount_strategy,
        current_spend=decimal_amount_strategy,
        rds=positive_rds_strategy
    )
    def test_hard_stop_blocks_all_confidence_levels(
        self,
        confidence: Decimal,
        risk_level: RiskLevel,
        monthly_budget: Decimal,
        current_spend: Decimal,
        rds: Decimal
    ) -> None:
        """
        **Feature: budgetguard-integration, Property 19: Budget Gating Override**
        **Validates: Requirements 1.1, 1.2, 1.3, 5.1, 5.2**
        
        Verify that CRITICAL or OVER_BUDGET risk levels block trades
        regardless of confidence score.
        """
        module = create_operational_gating_module()
        
        # Create campaign with HARD_STOP risk level
        campaign = create_campaign_analysis(
            name="CAMPAIGN_ALPHA",
            monthly_budget=monthly_budget,
            current_spend=current_spend,
            rds=rds,
            risk_level=risk_level
        )
        
        report = create_budget_report([campaign])
        
        # Evaluate risk
        gating_result = module.evaluate_risk(
            report=report,
            projected_cost=None,
            correlation_id="TEST_PROP19"
        )
        
        # HARD_STOP must be returned
        assert gating_result.signal == GatingSignal.HARD_STOP, (
            f"Expected HARD_STOP for {risk_level.value}, got {gating_result.signal.value}"
        )
        assert gating_result.can_trade is False, (
            f"can_trade should be False for {risk_level.value}"
        )
        
        # Trade signal must be rejected regardless of confidence
        trade_allowed = module.evaluate_trade_signal(
            confidence_score=confidence,
            gating_result=gating_result,
            correlation_id="TEST_PROP19_TRADE"
        )
        
        assert trade_allowed is False, (
            f"Trade with {confidence}% confidence should be rejected "
            f"when risk_level={risk_level.value}"
        )
    
    @settings(max_examples=100)
    @given(
        confidence=confidence_score_strategy,
        risk_level=allow_risk_levels,
        monthly_budget=decimal_amount_strategy,
        rds=positive_rds_strategy
    )
    def test_healthy_warning_allows_trading(
        self,
        confidence: Decimal,
        risk_level: RiskLevel,
        monthly_budget: Decimal,
        rds: Decimal
    ) -> None:
        """
        **Feature: budgetguard-integration, Property 19: Budget Gating Override**
        **Validates: Requirements 1.4**
        
        Verify that HEALTHY or WARNING risk levels allow trading.
        """
        module = create_operational_gating_module()
        
        # Current spend below budget to avoid OVER_BUDGET
        current_spend = monthly_budget * Decimal("0.5")
        
        campaign = create_campaign_analysis(
            name="CAMPAIGN_ALPHA",
            monthly_budget=monthly_budget,
            current_spend=current_spend,
            rds=rds,
            risk_level=risk_level
        )
        
        report = create_budget_report([campaign])
        
        # Evaluate risk with no projected cost (to avoid RDS check)
        gating_result = module.evaluate_risk(
            report=report,
            projected_cost=None,
            correlation_id="TEST_PROP19_ALLOW"
        )
        
        # Should ALLOW trading
        assert gating_result.signal == GatingSignal.ALLOW, (
            f"Expected ALLOW for {risk_level.value}, got {gating_result.signal.value}"
        )
        assert gating_result.can_trade is True, (
            f"can_trade should be True for {risk_level.value}"
        )
    
    @settings(max_examples=100)
    @given(
        confidence=st.decimals(
            min_value=Decimal("95.00"),
            max_value=Decimal("100.00"),
            places=2,
            allow_nan=False,
            allow_infinity=False
        ),
        monthly_budget=decimal_amount_strategy,
        rds=positive_rds_strategy
    )
    def test_99_percent_confidence_blocked_by_critical(
        self,
        confidence: Decimal,
        monthly_budget: Decimal,
        rds: Decimal
    ) -> None:
        """
        **Feature: budgetguard-integration, Property 19: Budget Gating Override**
        **Validates: Requirements 5.1**
        
        Verify that even 99%+ confidence trades are blocked by CRITICAL risk.
        """
        module = create_operational_gating_module()
        
        campaign = create_campaign_analysis(
            name="CAMPAIGN_ALPHA",
            monthly_budget=monthly_budget,
            current_spend=monthly_budget * Decimal("0.9"),
            rds=rds,
            risk_level=RiskLevel.CRITICAL
        )
        
        report = create_budget_report([campaign])
        
        gating_result = module.evaluate_risk(
            report=report,
            projected_cost=None,
            correlation_id="TEST_PROP19_HIGH_CONF"
        )
        
        trade_allowed = module.evaluate_trade_signal(
            confidence_score=confidence,
            gating_result=gating_result,
            correlation_id="TEST_PROP19_HIGH_CONF_TRADE"
        )
        
        assert trade_allowed is False, (
            f"Trade with {confidence}% confidence should be rejected "
            f"when risk_level=CRITICAL"
        )


# =============================================================================
# PROPERTY 20: Staleness Protection
# **Feature: budgetguard-integration, Property 20: Staleness Protection**
# **Validates: Requirements 4.1, 4.2**
# =============================================================================

class TestStalenessProtection:
    """
    Property 20: Staleness Protection
    
    For any BudgetGuard JSON timestamp that is more than 24 hours old,
    the system SHALL enter Neutral State and block all new trades.
    """
    
    @settings(max_examples=100)
    @given(
        hours_old=st.integers(min_value=25, max_value=720),  # 25 hours to 30 days
        monthly_budget=decimal_amount_strategy,
        rds=positive_rds_strategy
    )
    def test_stale_data_triggers_neutral_state(
        self,
        hours_old: int,
        monthly_budget: Decimal,
        rds: Decimal
    ) -> None:
        """
        **Feature: budgetguard-integration, Property 20: Staleness Protection**
        **Validates: Requirements 4.1, 4.2**
        
        Verify that data older than 24 hours triggers STALE_DATA signal.
        """
        module = create_operational_gating_module()
        
        # Create timestamp older than threshold
        stale_timestamp = datetime.now(timezone.utc) - timedelta(hours=hours_old)
        
        campaign = create_campaign_analysis(
            name="CAMPAIGN_ALPHA",
            monthly_budget=monthly_budget,
            current_spend=monthly_budget * Decimal("0.3"),
            rds=rds,
            risk_level=RiskLevel.HEALTHY
        )
        
        report = create_budget_report([campaign], timestamp=stale_timestamp)
        
        gating_result = module.evaluate_risk(
            report=report,
            projected_cost=None,
            correlation_id="TEST_PROP20_STALE"
        )
        
        # Must return STALE_DATA signal
        assert gating_result.signal == GatingSignal.STALE_DATA, (
            f"Expected STALE_DATA for {hours_old}h old data, "
            f"got {gating_result.signal.value}"
        )
        assert gating_result.can_trade is False, (
            f"can_trade should be False for stale data"
        )
        
        # Data age should be reported correctly
        assert gating_result.data_age_hours >= Decimal(str(hours_old - 1)), (
            f"Data age {gating_result.data_age_hours}h should be >= {hours_old - 1}h"
        )
    
    @settings(max_examples=100)
    @given(
        hours_old=st.integers(min_value=0, max_value=23),  # 0 to 23 hours
        monthly_budget=decimal_amount_strategy,
        rds=positive_rds_strategy
    )
    def test_fresh_data_allows_trading(
        self,
        hours_old: int,
        monthly_budget: Decimal,
        rds: Decimal
    ) -> None:
        """
        **Feature: budgetguard-integration, Property 20: Staleness Protection**
        **Validates: Requirements 4.3**
        
        Verify that data less than 24 hours old allows trading.
        """
        module = create_operational_gating_module()
        
        # Create fresh timestamp
        fresh_timestamp = datetime.now(timezone.utc) - timedelta(hours=hours_old)
        
        campaign = create_campaign_analysis(
            name="CAMPAIGN_ALPHA",
            monthly_budget=monthly_budget,
            current_spend=monthly_budget * Decimal("0.3"),
            rds=rds,
            risk_level=RiskLevel.HEALTHY
        )
        
        report = create_budget_report([campaign], timestamp=fresh_timestamp)
        
        gating_result = module.evaluate_risk(
            report=report,
            projected_cost=None,
            correlation_id="TEST_PROP20_FRESH"
        )
        
        # Should NOT be STALE_DATA
        assert gating_result.signal != GatingSignal.STALE_DATA, (
            f"Fresh data ({hours_old}h old) should not trigger STALE_DATA"
        )
    
    @settings(max_examples=100)
    @given(
        confidence=confidence_score_strategy,
        hours_old=st.integers(min_value=25, max_value=168)
    )
    def test_stale_data_blocks_all_trades(
        self,
        confidence: Decimal,
        hours_old: int
    ) -> None:
        """
        **Feature: budgetguard-integration, Property 20: Staleness Protection**
        **Validates: Requirements 4.1**
        
        Verify that stale data blocks trades regardless of confidence.
        """
        module = create_operational_gating_module()
        
        stale_timestamp = datetime.now(timezone.utc) - timedelta(hours=hours_old)
        
        campaign = create_campaign_analysis(
            name="CAMPAIGN_ALPHA",
            monthly_budget=Decimal("50000.00"),
            current_spend=Decimal("10000.00"),
            rds=Decimal("1000.00"),
            risk_level=RiskLevel.HEALTHY
        )
        
        report = create_budget_report([campaign], timestamp=stale_timestamp)
        
        gating_result = module.evaluate_risk(
            report=report,
            projected_cost=None,
            correlation_id="TEST_PROP20_BLOCK"
        )
        
        trade_allowed = module.evaluate_trade_signal(
            confidence_score=confidence,
            gating_result=gating_result,
            correlation_id="TEST_PROP20_BLOCK_TRADE"
        )
        
        assert trade_allowed is False, (
            f"Trade with {confidence}% confidence should be blocked "
            f"when data is {hours_old}h old"
        )



# =============================================================================
# PROPERTY 22: RDS Enforcement
# **Feature: budgetguard-integration, Property 22: RDS Enforcement**
# **Validates: Requirements 2.1, 2.2, 2.3**
# =============================================================================

class TestRDSEnforcement:
    """
    Property 22: RDS Enforcement
    
    For any projected daily infrastructure cost that exceeds the RDS value,
    the system SHALL reject trade execution and log the rejection with
    correlation_id, projected_cost, and rds_limit.
    """
    
    @settings(max_examples=100)
    @given(
        rds=positive_rds_strategy,
        excess_ratio=st.floats(min_value=1.01, max_value=10.0)
    )
    def test_projected_cost_exceeding_rds_blocks_trade(
        self,
        rds: Decimal,
        excess_ratio: float
    ) -> None:
        """
        **Feature: budgetguard-integration, Property 22: RDS Enforcement**
        **Validates: Requirements 2.1, 2.2**
        
        Verify that projected cost > RDS triggers RDS_EXCEEDED signal.
        """
        module = create_operational_gating_module()
        
        # Projected cost exceeds RDS
        projected_cost = (rds * Decimal(str(excess_ratio))).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_EVEN
        )
        
        # Skip edge case where rounding makes projected_cost == rds
        assume(projected_cost > rds)
        
        campaign = create_campaign_analysis(
            name="CAMPAIGN_ALPHA",
            monthly_budget=Decimal("50000.00"),
            current_spend=Decimal("10000.00"),
            rds=rds,
            risk_level=RiskLevel.HEALTHY
        )
        
        report = create_budget_report([campaign])
        
        gating_result = module.evaluate_risk(
            report=report,
            projected_cost=projected_cost,
            correlation_id="TEST_PROP22_EXCEED"
        )
        
        # Must return RDS_EXCEEDED signal
        assert gating_result.signal == GatingSignal.RDS_EXCEEDED, (
            f"Expected RDS_EXCEEDED when cost={projected_cost} > rds={rds}, "
            f"got {gating_result.signal.value}"
        )
        assert gating_result.can_trade is False, (
            f"can_trade should be False when RDS exceeded"
        )
        
        # Verify required fields are present
        assert gating_result.rds_limit == rds, (
            f"rds_limit should be {rds}, got {gating_result.rds_limit}"
        )
        assert gating_result.projected_cost == projected_cost, (
            f"projected_cost should be {projected_cost}, "
            f"got {gating_result.projected_cost}"
        )
        assert gating_result.correlation_id == "TEST_PROP22_EXCEED", (
            f"correlation_id mismatch"
        )
    
    @settings(max_examples=100)
    @given(
        rds=positive_rds_strategy,
        under_ratio=st.floats(min_value=0.01, max_value=0.99)
    )
    def test_projected_cost_under_rds_allows_trade(
        self,
        rds: Decimal,
        under_ratio: float
    ) -> None:
        """
        **Feature: budgetguard-integration, Property 22: RDS Enforcement**
        **Validates: Requirements 2.1**
        
        Verify that projected cost < RDS allows trading.
        """
        module = create_operational_gating_module()
        
        # Projected cost under RDS
        projected_cost = (rds * Decimal(str(under_ratio))).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_EVEN
        )
        
        campaign = create_campaign_analysis(
            name="CAMPAIGN_ALPHA",
            monthly_budget=Decimal("50000.00"),
            current_spend=Decimal("10000.00"),
            rds=rds,
            risk_level=RiskLevel.HEALTHY
        )
        
        report = create_budget_report([campaign])
        
        gating_result = module.evaluate_risk(
            report=report,
            projected_cost=projected_cost,
            correlation_id="TEST_PROP22_UNDER"
        )
        
        # Should ALLOW trading
        assert gating_result.signal == GatingSignal.ALLOW, (
            f"Expected ALLOW when cost={projected_cost} < rds={rds}, "
            f"got {gating_result.signal.value}"
        )
        assert gating_result.can_trade is True, (
            f"can_trade should be True when under RDS"
        )
    
    @settings(max_examples=100)
    @given(
        projected_cost=decimal_amount_strategy,
        zero_or_negative_rds=st.decimals(
            min_value=Decimal("-1000.00"),
            max_value=Decimal("0.00"),
            places=2,
            allow_nan=False,
            allow_infinity=False
        )
    )
    def test_zero_negative_rds_triggers_hard_stop(
        self,
        projected_cost: Decimal,
        zero_or_negative_rds: Decimal
    ) -> None:
        """
        **Feature: budgetguard-integration, Property 22: RDS Enforcement**
        **Validates: Requirements 2.4**
        
        Verify that zero or negative RDS is treated as implicit HARD_STOP.
        """
        module = create_operational_gating_module()
        
        # check_rds_limit should return True (exceeded) for zero/negative RDS
        result = module.check_rds_limit(projected_cost, zero_or_negative_rds)
        
        assert result is True, (
            f"Zero/negative RDS ({zero_or_negative_rds}) should trigger "
            f"RDS exceeded condition"
        )
    
    @settings(max_examples=100)
    @given(
        rds=positive_rds_strategy,
        excess_ratio=st.floats(min_value=1.01, max_value=5.0),
        confidence=confidence_score_strategy
    )
    def test_rds_exceeded_blocks_all_confidence_levels(
        self,
        rds: Decimal,
        excess_ratio: float,
        confidence: Decimal
    ) -> None:
        """
        **Feature: budgetguard-integration, Property 22: RDS Enforcement**
        **Validates: Requirements 2.1, 2.3**
        
        Verify that RDS exceeded blocks trades regardless of confidence.
        """
        module = create_operational_gating_module()
        
        projected_cost = (rds * Decimal(str(excess_ratio))).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_EVEN
        )
        
        # Skip edge case where rounding makes projected_cost == rds
        assume(projected_cost > rds)
        
        campaign = create_campaign_analysis(
            name="CAMPAIGN_ALPHA",
            monthly_budget=Decimal("50000.00"),
            current_spend=Decimal("10000.00"),
            rds=rds,
            risk_level=RiskLevel.HEALTHY
        )
        
        report = create_budget_report([campaign])
        
        gating_result = module.evaluate_risk(
            report=report,
            projected_cost=projected_cost,
            correlation_id="TEST_PROP22_CONF"
        )
        
        trade_allowed = module.evaluate_trade_signal(
            confidence_score=confidence,
            gating_result=gating_result,
            correlation_id="TEST_PROP22_CONF_TRADE"
        )
        
        assert trade_allowed is False, (
            f"Trade with {confidence}% confidence should be blocked "
            f"when projected_cost={projected_cost} > rds={rds}"
        )


# =============================================================================
# JSON PARSING TESTS
# =============================================================================

class TestJSONParsing:
    """
    Tests for BudgetGuard JSON parsing with Decimal precision.
    """
    
    @settings(max_examples=100)
    @given(
        monthly_budget=decimal_amount_strategy,
        current_spend=decimal_amount_strategy,
        rds=positive_rds_strategy,
        risk_level=all_risk_levels
    )
    def test_json_round_trip_preserves_decimals(
        self,
        monthly_budget: Decimal,
        current_spend: Decimal,
        rds: Decimal,
        risk_level: RiskLevel
    ) -> None:
        """
        Verify JSON parsing preserves Decimal precision.
        """
        module = create_operational_gating_module()
        
        campaign = create_campaign_analysis(
            name="CAMPAIGN_ALPHA",
            monthly_budget=monthly_budget,
            current_spend=current_spend,
            rds=rds,
            risk_level=risk_level
        )
        
        original_report = create_budget_report([campaign])
        json_str = create_budget_json(original_report)
        
        # Parse JSON
        parsed_report = module.parse_budget_report(
            json_str=json_str,
            correlation_id="TEST_JSON_ROUNDTRIP"
        )
        
        # Verify Decimal values preserved
        assert parsed_report.total_budget == original_report.total_budget, (
            f"total_budget mismatch: {parsed_report.total_budget} != "
            f"{original_report.total_budget}"
        )
        assert parsed_report.total_spend == original_report.total_spend, (
            f"total_spend mismatch: {parsed_report.total_spend} != "
            f"{original_report.total_spend}"
        )
        
        # Verify campaign values
        assert len(parsed_report.campaigns) == 1
        parsed_campaign = parsed_report.campaigns[0]
        
        assert parsed_campaign.monthly_budget == monthly_budget, (
            f"monthly_budget mismatch: {parsed_campaign.monthly_budget} != "
            f"{monthly_budget}"
        )
        assert parsed_campaign.current_spend == current_spend, (
            f"current_spend mismatch: {parsed_campaign.current_spend} != "
            f"{current_spend}"
        )
        assert parsed_campaign.rds == rds, (
            f"rds mismatch: {parsed_campaign.rds} != {rds}"
        )
        assert parsed_campaign.risk_level == risk_level, (
            f"risk_level mismatch: {parsed_campaign.risk_level} != {risk_level}"
        )
    
    def test_malformed_json_raises_error(self) -> None:
        """
        Verify malformed JSON raises ValueError.
        """
        module = create_operational_gating_module()
        
        with pytest.raises(ValueError) as exc_info:
            module.parse_budget_report(
                json_str="not valid json",
                correlation_id="TEST_MALFORMED"
            )
        
        assert "Invalid JSON" in str(exc_info.value)
    
    def test_missing_fields_raises_error(self) -> None:
        """
        Verify missing required fields raises ValueError.
        """
        module = create_operational_gating_module()
        
        incomplete_json = json.dumps({
            "metadata": {"timestamp": datetime.now(timezone.utc).isoformat()},
            # Missing summary and campaigns
        })
        
        with pytest.raises(ValueError) as exc_info:
            module.parse_budget_report(
                json_str=incomplete_json,
                correlation_id="TEST_MISSING"
            )
        
        assert "Invalid BudgetGuard JSON structure" in str(exc_info.value)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


# =============================================================================
# PROPERTY 21: Net Alpha Decimal Integrity
# **Feature: budgetguard-integration, Property 21: Net Alpha Decimal Integrity**
# **Validates: Requirements 3.1, 3.2**
# =============================================================================

# Import EquityModule for Net Alpha tests
from app.logic.production_safety import (
    EquityModule,
    NetAlphaSnapshot,
)


class TestNetAlphaDecimalIntegrity:
    """
    Property 21: Net Alpha Decimal Integrity
    
    For any gross_profit and operational_cost values as Decimal, Net Alpha
    SHALL equal (gross_profit - operational_cost) with ROUND_HALF_EVEN
    precision, and the result SHALL format correctly as "R X,XXX.XX".
    """
    
    @settings(max_examples=100)
    @given(
        gross_profit=decimal_amount_strategy,
        operational_cost=decimal_amount_strategy
    )
    def test_net_alpha_calculation_uses_decimal(
        self,
        gross_profit: Decimal,
        operational_cost: Decimal
    ) -> None:
        """
        **Feature: budgetguard-integration, Property 21: Net Alpha Decimal Integrity**
        **Validates: Requirements 3.1**
        
        Verify Net Alpha = gross_profit - operational_cost with Decimal precision.
        """
        equity_module = EquityModule()
        
        snapshot = equity_module.calculate_net_alpha(
            gross_profit_zar=gross_profit,
            operational_cost_zar=operational_cost,
            correlation_id="TEST_PROP21_CALC"
        )
        
        # Verify result is Decimal
        assert isinstance(snapshot.net_alpha_zar, Decimal), (
            f"net_alpha_zar is not Decimal: {type(snapshot.net_alpha_zar)}"
        )
        
        # Verify calculation is correct
        expected = (gross_profit - operational_cost).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_EVEN
        )
        
        assert snapshot.net_alpha_zar == expected, (
            f"Net Alpha calculation mismatch: "
            f"{snapshot.net_alpha_zar} != {expected}"
        )
        
        # Verify input values preserved
        assert snapshot.gross_profit_zar == gross_profit
        assert snapshot.operational_cost_zar == operational_cost
        assert snapshot.operational_cost_stale is False
    
    @settings(max_examples=100)
    @given(net_alpha=st.decimals(
        min_value=Decimal("-10000000.00"),
        max_value=Decimal("10000000.00"),
        places=2,
        allow_nan=False,
        allow_infinity=False
    ))
    def test_net_alpha_zar_formatting(
        self,
        net_alpha: Decimal
    ) -> None:
        """
        **Feature: budgetguard-integration, Property 21: Net Alpha Decimal Integrity**
        **Validates: Requirements 3.2**
        
        Verify Net Alpha formats correctly as "R X,XXX.XX".
        """
        equity_module = EquityModule()
        
        # Use gross_profit = net_alpha, operational_cost = 0 to get exact value
        snapshot = equity_module.calculate_net_alpha(
            gross_profit_zar=net_alpha,
            operational_cost_zar=Decimal("0.00"),
            correlation_id="TEST_PROP21_FORMAT"
        )
        
        formatted = snapshot.formatted
        
        # Must start with "R "
        assert formatted.startswith("R "), (
            f"Missing R prefix: {formatted}"
        )
        
        # Extract numeric part
        if formatted.startswith("R -"):
            numeric_str = formatted[3:].replace(",", "")
            is_negative = True
        else:
            numeric_str = formatted[2:].replace(",", "")
            is_negative = False
        
        # Must have exactly 2 decimal places
        if "." in numeric_str:
            decimal_part = numeric_str.split(".")[1]
            assert len(decimal_part) == 2, (
                f"Not 2 decimal places: {formatted}"
            )
        
        # Parse back and verify
        parsed = Decimal(numeric_str)
        if is_negative:
            parsed = -parsed
        
        original_quantized = net_alpha.quantize(
            Decimal("0.01"), rounding=ROUND_HALF_EVEN
        )
        
        assert parsed == original_quantized, (
            f"Format round-trip failed: {net_alpha} -> {formatted} -> {parsed}"
        )
    
    @settings(max_examples=100)
    @given(gross_profit=decimal_amount_strategy)
    def test_missing_operational_cost_returns_gross_profit(
        self,
        gross_profit: Decimal
    ) -> None:
        """
        **Feature: budgetguard-integration, Property 21: Net Alpha Decimal Integrity**
        **Validates: Requirements 3.3**
        
        Verify missing operational cost returns gross_profit with staleness flag.
        """
        equity_module = EquityModule()
        
        snapshot = equity_module.calculate_net_alpha(
            gross_profit_zar=gross_profit,
            operational_cost_zar=None,
            correlation_id="TEST_PROP21_MISSING"
        )
        
        # Net Alpha should equal gross profit
        assert snapshot.net_alpha_zar == gross_profit, (
            f"Net Alpha should equal gross_profit when cost is missing: "
            f"{snapshot.net_alpha_zar} != {gross_profit}"
        )
        
        # Staleness flag should be True
        assert snapshot.operational_cost_stale is True, (
            f"operational_cost_stale should be True when cost is missing"
        )
        
        # Operational cost should be zero
        assert snapshot.operational_cost_zar == Decimal("0.00")
    
    @settings(max_examples=100)
    @given(
        gross_profit=decimal_amount_strategy,
        operational_cost=decimal_amount_strategy
    )
    def test_correlation_id_preserved(
        self,
        gross_profit: Decimal,
        operational_cost: Decimal
    ) -> None:
        """
        **Feature: budgetguard-integration, Property 21: Net Alpha Decimal Integrity**
        **Validates: Requirements 3.4**
        
        Verify correlation_id is preserved in result.
        """
        equity_module = EquityModule()
        
        test_correlation_id = "TEST_PROP21_CORR_12345"
        
        snapshot = equity_module.calculate_net_alpha(
            gross_profit_zar=gross_profit,
            operational_cost_zar=operational_cost,
            correlation_id=test_correlation_id
        )
        
        assert snapshot.correlation_id == test_correlation_id, (
            f"correlation_id mismatch: "
            f"{snapshot.correlation_id} != {test_correlation_id}"
        )
    
    @settings(max_examples=100)
    @given(total_spend=decimal_amount_strategy)
    def test_ingest_budget_spend_stores_value(
        self,
        total_spend: Decimal
    ) -> None:
        """
        Verify ingest_budget_spend stores the operational cost.
        """
        equity_module = EquityModule()
        
        result = equity_module.ingest_budget_spend(total_spend)
        
        assert result == total_spend, (
            f"ingest_budget_spend should return the spend value"
        )
        
        stored = equity_module.get_current_operational_cost()
        
        assert stored == total_spend, (
            f"Stored operational cost mismatch: {stored} != {total_spend}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

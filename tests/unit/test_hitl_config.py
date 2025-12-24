"""
Unit Tests for HITL Configuration Parsing

Reliability Level: SOVEREIGN TIER
Python 3.8 Compatible

Tests the HITL configuration module:
- Default values for optional configuration
- Custom values from environment variables
- Missing required config fails with SEC-040

**Feature: hitl-approval-gateway, Task 4.2: Write unit tests for configuration parsing**
**Validates: Requirements 10.1, 10.2, 10.3, 10.4, 10.6**
"""

import pytest
import os
from decimal import Decimal, ROUND_HALF_EVEN
from typing import Dict, Optional

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from services.hitl_config import (
    HITLConfig,
    HITLConfigurationError,
    HITLConfigErrorCode,
    DEFAULT_HITL_ENABLED,
    DEFAULT_HITL_TIMEOUT_SECONDS,
    DEFAULT_HITL_SLIPPAGE_MAX_PERCENT,
    PRECISION_SLIPPAGE,
    get_hitl_config,
    reset_hitl_config,
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture(autouse=True)
def clean_environment():
    """
    Clean environment variables before and after each test.
    
    This ensures tests are isolated and don't affect each other.
    """
    # Store original environment
    original_env = {}
    env_vars = [
        "HITL_ENABLED",
        "HITL_TIMEOUT_SECONDS",
        "HITL_SLIPPAGE_MAX_PERCENT",
        "HITL_ALLOWED_OPERATORS",
    ]
    
    for var in env_vars:
        original_env[var] = os.environ.get(var)
        if var in os.environ:
            del os.environ[var]
    
    # Reset global config instance
    reset_hitl_config()
    
    yield
    
    # Restore original environment
    for var, value in original_env.items():
        if value is not None:
            os.environ[var] = value
        elif var in os.environ:
            del os.environ[var]
    
    # Reset global config instance again
    reset_hitl_config()


# =============================================================================
# Test Default Values
# =============================================================================

class TestDefaultValues:
    """
    Test default configuration values.
    
    **Feature: hitl-approval-gateway, Task 4.2: Write unit tests for configuration parsing**
    **Validates: Requirements 10.1, 10.2, 10.3, 10.4**
    """
    
    def test_default_enabled_is_true(self) -> None:
        """Default HITL_ENABLED should be True (Requirement 10.1)."""
        assert DEFAULT_HITL_ENABLED is True
    
    def test_default_timeout_is_300_seconds(self) -> None:
        """Default HITL_TIMEOUT_SECONDS should be 300 (Requirement 10.2)."""
        assert DEFAULT_HITL_TIMEOUT_SECONDS == 300
    
    def test_default_slippage_is_half_percent(self) -> None:
        """Default HITL_SLIPPAGE_MAX_PERCENT should be 0.5 (Requirement 10.3)."""
        assert DEFAULT_HITL_SLIPPAGE_MAX_PERCENT == Decimal("0.50")
    
    def test_config_dataclass_defaults(self) -> None:
        """HITLConfig dataclass should have correct defaults."""
        config = HITLConfig()
        
        assert config.enabled is True
        assert config.timeout_seconds == 300
        assert config.slippage_max_percent == Decimal("0.50")
        assert config.allowed_operators == set()
    
    def test_from_environment_uses_defaults_when_not_set(self) -> None:
        """from_environment should use defaults when env vars not set."""
        # Set only required config
        os.environ["HITL_ALLOWED_OPERATORS"] = "operator_1"
        
        config = HITLConfig.from_environment(validate=True)
        
        assert config.enabled is True
        assert config.timeout_seconds == 300
        assert config.slippage_max_percent == Decimal("0.50")


# =============================================================================
# Test Custom Values
# =============================================================================

class TestCustomValues:
    """
    Test custom configuration values from environment.
    
    **Feature: hitl-approval-gateway, Task 4.2: Write unit tests for configuration parsing**
    **Validates: Requirements 10.1, 10.2, 10.3, 10.4**
    """
    
    def test_custom_enabled_false(self) -> None:
        """HITL_ENABLED=false should set enabled to False."""
        os.environ["HITL_ENABLED"] = "false"
        os.environ["HITL_ALLOWED_OPERATORS"] = "operator_1"
        
        config = HITLConfig.from_environment(validate=True)
        
        assert config.enabled is False
    
    def test_custom_enabled_true_explicit(self) -> None:
        """HITL_ENABLED=true should set enabled to True."""
        os.environ["HITL_ENABLED"] = "true"
        os.environ["HITL_ALLOWED_OPERATORS"] = "operator_1"
        
        config = HITLConfig.from_environment(validate=True)
        
        assert config.enabled is True
    
    def test_custom_enabled_accepts_various_true_values(self) -> None:
        """HITL_ENABLED should accept various truthy values."""
        truthy_values = ["true", "True", "TRUE", "1", "yes", "on"]
        
        for value in truthy_values:
            os.environ["HITL_ENABLED"] = value
            os.environ["HITL_ALLOWED_OPERATORS"] = "operator_1"
            reset_hitl_config()
            
            config = HITLConfig.from_environment(validate=True)
            assert config.enabled is True, f"Failed for value: {value}"
    
    def test_custom_enabled_accepts_various_false_values(self) -> None:
        """HITL_ENABLED should treat non-truthy values as False."""
        falsy_values = ["false", "False", "FALSE", "0", "no", "off", ""]
        
        for value in falsy_values:
            os.environ["HITL_ENABLED"] = value
            os.environ["HITL_ALLOWED_OPERATORS"] = "operator_1"
            reset_hitl_config()
            
            config = HITLConfig.from_environment(validate=True)
            assert config.enabled is False, f"Failed for value: {value}"
    
    def test_custom_timeout_seconds(self) -> None:
        """HITL_TIMEOUT_SECONDS should be parsed as integer."""
        os.environ["HITL_TIMEOUT_SECONDS"] = "600"
        os.environ["HITL_ALLOWED_OPERATORS"] = "operator_1"
        
        config = HITLConfig.from_environment(validate=True)
        
        assert config.timeout_seconds == 600
    
    def test_custom_timeout_with_whitespace(self) -> None:
        """HITL_TIMEOUT_SECONDS should handle whitespace."""
        os.environ["HITL_TIMEOUT_SECONDS"] = "  450  "
        os.environ["HITL_ALLOWED_OPERATORS"] = "operator_1"
        
        config = HITLConfig.from_environment(validate=True)
        
        assert config.timeout_seconds == 450
    
    def test_invalid_timeout_uses_default(self) -> None:
        """Invalid HITL_TIMEOUT_SECONDS should fall back to default."""
        os.environ["HITL_TIMEOUT_SECONDS"] = "not_a_number"
        os.environ["HITL_ALLOWED_OPERATORS"] = "operator_1"
        
        config = HITLConfig.from_environment(validate=True)
        
        assert config.timeout_seconds == DEFAULT_HITL_TIMEOUT_SECONDS
    
    def test_custom_slippage_max_percent(self) -> None:
        """HITL_SLIPPAGE_MAX_PERCENT should be parsed as Decimal."""
        os.environ["HITL_SLIPPAGE_MAX_PERCENT"] = "1.25"
        os.environ["HITL_ALLOWED_OPERATORS"] = "operator_1"
        
        config = HITLConfig.from_environment(validate=True)
        
        assert config.slippage_max_percent == Decimal("1.25")
    
    def test_slippage_uses_round_half_even(self) -> None:
        """HITL_SLIPPAGE_MAX_PERCENT should use ROUND_HALF_EVEN."""
        os.environ["HITL_SLIPPAGE_MAX_PERCENT"] = "0.555"
        os.environ["HITL_ALLOWED_OPERATORS"] = "operator_1"
        
        config = HITLConfig.from_environment(validate=True)
        
        # 0.555 with ROUND_HALF_EVEN to 2 decimal places = 0.56
        assert config.slippage_max_percent == Decimal("0.56")
    
    def test_slippage_quantized_to_two_decimals(self) -> None:
        """HITL_SLIPPAGE_MAX_PERCENT should be quantized to 2 decimal places."""
        os.environ["HITL_SLIPPAGE_MAX_PERCENT"] = "0.12345"
        os.environ["HITL_ALLOWED_OPERATORS"] = "operator_1"
        
        config = HITLConfig.from_environment(validate=True)
        
        # Should be quantized to 0.12
        assert config.slippage_max_percent == Decimal("0.12")
    
    def test_invalid_slippage_uses_default(self) -> None:
        """Invalid HITL_SLIPPAGE_MAX_PERCENT should fall back to default."""
        os.environ["HITL_SLIPPAGE_MAX_PERCENT"] = "not_a_decimal"
        os.environ["HITL_ALLOWED_OPERATORS"] = "operator_1"
        
        config = HITLConfig.from_environment(validate=True)
        
        assert config.slippage_max_percent == DEFAULT_HITL_SLIPPAGE_MAX_PERCENT
    
    def test_custom_allowed_operators_single(self) -> None:
        """HITL_ALLOWED_OPERATORS should parse single operator."""
        os.environ["HITL_ALLOWED_OPERATORS"] = "operator_123"
        
        config = HITLConfig.from_environment(validate=True)
        
        assert config.allowed_operators == {"operator_123"}
    
    def test_custom_allowed_operators_multiple(self) -> None:
        """HITL_ALLOWED_OPERATORS should parse comma-separated list."""
        os.environ["HITL_ALLOWED_OPERATORS"] = "op1,op2,op3"
        
        config = HITLConfig.from_environment(validate=True)
        
        assert config.allowed_operators == {"op1", "op2", "op3"}
    
    def test_allowed_operators_strips_whitespace(self) -> None:
        """HITL_ALLOWED_OPERATORS should strip whitespace from each ID."""
        os.environ["HITL_ALLOWED_OPERATORS"] = "  op1  ,  op2  ,  op3  "
        
        config = HITLConfig.from_environment(validate=True)
        
        assert config.allowed_operators == {"op1", "op2", "op3"}
    
    def test_allowed_operators_ignores_empty_entries(self) -> None:
        """HITL_ALLOWED_OPERATORS should ignore empty entries."""
        os.environ["HITL_ALLOWED_OPERATORS"] = "op1,,op2,  ,op3"
        
        config = HITLConfig.from_environment(validate=True)
        
        assert config.allowed_operators == {"op1", "op2", "op3"}
    
    def test_allowed_operators_deduplicates(self) -> None:
        """HITL_ALLOWED_OPERATORS should deduplicate entries."""
        os.environ["HITL_ALLOWED_OPERATORS"] = "op1,op2,op1,op3,op2"
        
        config = HITLConfig.from_environment(validate=True)
        
        assert config.allowed_operators == {"op1", "op2", "op3"}


# =============================================================================
# Test Missing Required Config (SEC-040)
# =============================================================================

class TestMissingRequiredConfig:
    """
    Test that missing required configuration fails with SEC-040.
    
    **Feature: hitl-approval-gateway, Task 4.2: Write unit tests for configuration parsing**
    **Validates: Requirements 10.6**
    """
    
    def test_missing_allowed_operators_raises_sec040(self) -> None:
        """Missing HITL_ALLOWED_OPERATORS should raise SEC-040."""
        # Don't set HITL_ALLOWED_OPERATORS
        
        with pytest.raises(HITLConfigurationError) as exc_info:
            HITLConfig.from_environment(validate=True)
        
        assert exc_info.value.error_code == "SEC-040"
        assert "HITL_ALLOWED_OPERATORS" in str(exc_info.value)
    
    def test_empty_allowed_operators_raises_sec040(self) -> None:
        """Empty HITL_ALLOWED_OPERATORS should raise SEC-040."""
        os.environ["HITL_ALLOWED_OPERATORS"] = ""
        
        with pytest.raises(HITLConfigurationError) as exc_info:
            HITLConfig.from_environment(validate=True)
        
        assert exc_info.value.error_code == "SEC-040"
    
    def test_whitespace_only_allowed_operators_raises_sec040(self) -> None:
        """Whitespace-only HITL_ALLOWED_OPERATORS should raise SEC-040."""
        os.environ["HITL_ALLOWED_OPERATORS"] = "   "
        
        with pytest.raises(HITLConfigurationError) as exc_info:
            HITLConfig.from_environment(validate=True)
        
        assert exc_info.value.error_code == "SEC-040"
    
    def test_validate_method_raises_sec040_for_empty_operators(self) -> None:
        """validate() should raise SEC-040 for empty allowed_operators."""
        config = HITLConfig(
            enabled=True,
            timeout_seconds=300,
            slippage_max_percent=Decimal("0.50"),
            allowed_operators=set()
        )
        
        with pytest.raises(HITLConfigurationError) as exc_info:
            config.validate()
        
        assert exc_info.value.error_code == "SEC-040"
    
    def test_validate_method_raises_sec040_for_negative_timeout(self) -> None:
        """validate() should raise SEC-040 for negative timeout."""
        config = HITLConfig(
            enabled=True,
            timeout_seconds=-1,
            slippage_max_percent=Decimal("0.50"),
            allowed_operators={"op1"}
        )
        
        with pytest.raises(HITLConfigurationError) as exc_info:
            config.validate()
        
        assert exc_info.value.error_code == "SEC-040"
    
    def test_validate_method_raises_sec040_for_zero_timeout(self) -> None:
        """validate() should raise SEC-040 for zero timeout."""
        config = HITLConfig(
            enabled=True,
            timeout_seconds=0,
            slippage_max_percent=Decimal("0.50"),
            allowed_operators={"op1"}
        )
        
        with pytest.raises(HITLConfigurationError) as exc_info:
            config.validate()
        
        assert exc_info.value.error_code == "SEC-040"
    
    def test_validate_method_raises_sec040_for_negative_slippage(self) -> None:
        """validate() should raise SEC-040 for negative slippage."""
        config = HITLConfig(
            enabled=True,
            timeout_seconds=300,
            slippage_max_percent=Decimal("-0.50"),
            allowed_operators={"op1"}
        )
        
        with pytest.raises(HITLConfigurationError) as exc_info:
            config.validate()
        
        assert exc_info.value.error_code == "SEC-040"
    
    def test_from_environment_without_validation_succeeds(self) -> None:
        """from_environment with validate=False should not raise."""
        # Don't set HITL_ALLOWED_OPERATORS
        
        # Should not raise
        config = HITLConfig.from_environment(validate=False)
        
        assert config.allowed_operators == set()
    
    def test_error_code_constant_is_sec040(self) -> None:
        """HITLConfigErrorCode.CONFIG_MISSING should be SEC-040."""
        assert HITLConfigErrorCode.CONFIG_MISSING == "SEC-040"


# =============================================================================
# Test is_operator_authorized Method
# =============================================================================

class TestIsOperatorAuthorized:
    """
    Test the is_operator_authorized method.
    
    **Feature: hitl-approval-gateway, Task 4.2: Write unit tests for configuration parsing**
    **Validates: Requirements 10.4**
    """
    
    def test_authorized_operator_returns_true(self) -> None:
        """Authorized operator should return True."""
        config = HITLConfig(allowed_operators={"op1", "op2", "op3"})
        
        assert config.is_operator_authorized("op1") is True
        assert config.is_operator_authorized("op2") is True
        assert config.is_operator_authorized("op3") is True
    
    def test_unauthorized_operator_returns_false(self) -> None:
        """Unauthorized operator should return False."""
        config = HITLConfig(allowed_operators={"op1", "op2"})
        
        assert config.is_operator_authorized("op3") is False
        assert config.is_operator_authorized("unknown") is False
    
    def test_empty_operator_id_returns_false(self) -> None:
        """Empty operator ID should return False."""
        config = HITLConfig(allowed_operators={"op1"})
        
        assert config.is_operator_authorized("") is False
    
    def test_whitespace_operator_id_returns_false(self) -> None:
        """Whitespace-only operator ID should return False."""
        config = HITLConfig(allowed_operators={"op1"})
        
        assert config.is_operator_authorized("   ") is False
    
    def test_operator_id_with_whitespace_is_stripped(self) -> None:
        """Operator ID with surrounding whitespace should be stripped."""
        config = HITLConfig(allowed_operators={"op1"})
        
        assert config.is_operator_authorized("  op1  ") is True


# =============================================================================
# Test to_dict Method
# =============================================================================

class TestToDict:
    """
    Test the to_dict method.
    
    **Feature: hitl-approval-gateway, Task 4.2: Write unit tests for configuration parsing**
    """
    
    def test_to_dict_returns_all_fields(self) -> None:
        """to_dict should return all configuration fields."""
        config = HITLConfig(
            enabled=True,
            timeout_seconds=300,
            slippage_max_percent=Decimal("0.50"),
            allowed_operators={"op1", "op2"}
        )
        
        result = config.to_dict()
        
        assert result["enabled"] is True
        assert result["timeout_seconds"] == 300
        assert result["slippage_max_percent"] == "0.50"
        assert set(result["allowed_operators"]) == {"op1", "op2"}
        assert result["allowed_operators_count"] == 2
    
    def test_to_dict_slippage_is_string(self) -> None:
        """to_dict should convert slippage to string for serialization."""
        config = HITLConfig(slippage_max_percent=Decimal("1.25"))
        
        result = config.to_dict()
        
        assert isinstance(result["slippage_max_percent"], str)
        assert result["slippage_max_percent"] == "1.25"


# =============================================================================
# Test Global Config Functions
# =============================================================================

class TestGlobalConfigFunctions:
    """
    Test global configuration functions.
    
    **Feature: hitl-approval-gateway, Task 4.2: Write unit tests for configuration parsing**
    """
    
    def test_get_hitl_config_returns_singleton(self) -> None:
        """get_hitl_config should return the same instance."""
        os.environ["HITL_ALLOWED_OPERATORS"] = "op1"
        
        config1 = get_hitl_config(validate=True)
        config2 = get_hitl_config(validate=True)
        
        assert config1 is config2
    
    def test_reset_hitl_config_clears_instance(self) -> None:
        """reset_hitl_config should clear the global instance."""
        os.environ["HITL_ALLOWED_OPERATORS"] = "op1"
        
        config1 = get_hitl_config(validate=True)
        reset_hitl_config()
        
        os.environ["HITL_ALLOWED_OPERATORS"] = "op2"
        config2 = get_hitl_config(validate=True)
        
        assert config1 is not config2
        assert config1.allowed_operators == {"op1"}
        assert config2.allowed_operators == {"op2"}


# =============================================================================
# Test Post-Init Decimal Conversion
# =============================================================================

class TestPostInitDecimalConversion:
    """
    Test __post_init__ decimal conversion.
    
    **Feature: hitl-approval-gateway, Task 4.2: Write unit tests for configuration parsing**
    """
    
    def test_float_slippage_converted_to_decimal(self) -> None:
        """Float slippage should be converted to Decimal."""
        # Note: This tests the __post_init__ conversion
        config = HITLConfig(slippage_max_percent=0.75)  # type: ignore
        
        assert isinstance(config.slippage_max_percent, Decimal)
        assert config.slippage_max_percent == Decimal("0.75")
    
    def test_int_slippage_converted_to_decimal(self) -> None:
        """Integer slippage should be converted to Decimal."""
        config = HITLConfig(slippage_max_percent=1)  # type: ignore
        
        assert isinstance(config.slippage_max_percent, Decimal)
        assert config.slippage_max_percent == Decimal("1.00")
    
    def test_string_slippage_converted_to_decimal(self) -> None:
        """String slippage should be converted to Decimal."""
        config = HITLConfig(slippage_max_percent="0.33")  # type: ignore
        
        assert isinstance(config.slippage_max_percent, Decimal)
        assert config.slippage_max_percent == Decimal("0.33")


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])

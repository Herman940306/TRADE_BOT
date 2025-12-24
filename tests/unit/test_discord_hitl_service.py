"""
============================================================================
HITL Approval Gateway - Discord Integration Service Tests
============================================================================

Reliability Level: L6 Critical (Sovereign Tier)
Test Coverage: Discord HITL Service functionality

REQUIREMENTS TESTED:
    - Requirement 8.1: Discord embed with trade details
    - Requirement 8.2: APPROVE and REJECT buttons with trade_id encoded
    - Requirement 8.3: Deep link URL with one-time token
    - Requirement 8.4: Verify Discord user_id is in HITL_ALLOWED_OPERATORS
    - Requirement 8.5: Deep link token validation (single-use)
    - Requirement 8.6: Log access with correlation_id
    - Requirement 4.4: Timeout notification

============================================================================
"""

import pytest
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, MagicMock, patch
import uuid

from services.discord_hitl_service import (
    DiscordHITLService,
    DeepLinkToken,
    DeepLinkTokenGenerator,
    DiscordApprovalEmbed,
    DiscordButtonPayload,
    TokenValidationResult,
    ButtonHandlerResult,
    DiscordButtonAction,
    DiscordHITLErrorCode,
    DEEP_LINK_TOKEN_LENGTH,
    DEFAULT_TOKEN_EXPIRY_SECONDS,
    DEFAULT_HUB_BASE_URL,
    create_discord_hitl_service,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def correlation_id() -> uuid.UUID:
    """Generate a correlation ID for testing."""
    return uuid.uuid4()


@pytest.fixture
def trade_id() -> uuid.UUID:
    """Generate a trade ID for testing."""
    return uuid.uuid4()


@pytest.fixture
def mock_discord_client() -> Mock:
    """Create a mock Discord client."""
    client = Mock()
    client.send_message = Mock()
    client.send_embed = Mock()
    client.update_message = Mock()
    return client


@pytest.fixture
def mock_db_session() -> Mock:
    """Create a mock database session."""
    session = Mock()
    session.execute = Mock()
    session.commit = Mock()
    return session


@pytest.fixture
def mock_hitl_gateway() -> Mock:
    """Create a mock HITL Gateway."""
    gateway = Mock()
    gateway.process_decision = Mock()
    return gateway


@pytest.fixture
def allowed_operators() -> list:
    """List of allowed operator IDs."""
    return ["operator_123", "operator_456", "admin_789"]


@pytest.fixture
def discord_service(
    mock_discord_client: Mock,
    mock_db_session: Mock,
    mock_hitl_gateway: Mock,
    allowed_operators: list,
) -> DiscordHITLService:
    """Create a DiscordHITLService instance for testing."""
    return DiscordHITLService(
        discord_client=mock_discord_client,
        db_session=mock_db_session,
        hitl_gateway=mock_hitl_gateway,
        allowed_operators=allowed_operators,
        hub_base_url="https://test-hub/approvals",
        token_expiry_seconds=300,
    )


@pytest.fixture
def sample_reasoning_summary() -> dict:
    """Sample reasoning summary for testing."""
    return {
        "trend": "BULLISH",
        "volatility": "LOW",
        "signal_confluence": ["RSI", "MACD", "EMA"],
        "notes": "Strong buy signal detected",
    }


# =============================================================================
# DeepLinkTokenGenerator Tests
# =============================================================================

class TestDeepLinkTokenGenerator:
    """Tests for DeepLinkTokenGenerator class."""
    
    def test_generate_returns_64_char_hex_string(self) -> None:
        """Token should be 64 hex characters (32 bytes)."""
        token = DeepLinkTokenGenerator.generate()
        
        assert len(token) == DEEP_LINK_TOKEN_LENGTH
        assert all(c in "0123456789abcdef" for c in token)
    
    def test_generate_returns_unique_tokens(self) -> None:
        """Each generated token should be unique."""
        tokens = [DeepLinkTokenGenerator.generate() for _ in range(100)]
        
        assert len(set(tokens)) == 100
    
    def test_create_token_returns_valid_deep_link_token(
        self,
        trade_id: uuid.UUID,
        correlation_id: uuid.UUID,
    ) -> None:
        """create_token should return a valid DeepLinkToken."""
        token = DeepLinkTokenGenerator.create_token(
            trade_id=trade_id,
            correlation_id=correlation_id,
            expiry_seconds=300,
        )
        
        assert isinstance(token, DeepLinkToken)
        assert len(token.token) == DEEP_LINK_TOKEN_LENGTH
        assert token.trade_id == trade_id
        assert token.correlation_id == correlation_id
        assert token.used_at is None
        assert token.is_valid()
    
    def test_create_token_sets_correct_expiry(
        self,
        trade_id: uuid.UUID,
        correlation_id: uuid.UUID,
    ) -> None:
        """Token expiry should be set correctly."""
        expiry_seconds = 600
        before = datetime.now(timezone.utc)
        
        token = DeepLinkTokenGenerator.create_token(
            trade_id=trade_id,
            correlation_id=correlation_id,
            expiry_seconds=expiry_seconds,
        )
        
        after = datetime.now(timezone.utc)
        
        expected_min = before + timedelta(seconds=expiry_seconds)
        expected_max = after + timedelta(seconds=expiry_seconds)
        
        assert expected_min <= token.expires_at <= expected_max


# =============================================================================
# DeepLinkToken Tests
# =============================================================================

class TestDeepLinkToken:
    """Tests for DeepLinkToken dataclass."""
    
    def test_is_expired_returns_false_for_valid_token(
        self,
        trade_id: uuid.UUID,
        correlation_id: uuid.UUID,
    ) -> None:
        """is_expired should return False for non-expired token."""
        token = DeepLinkToken(
            token="a" * 64,
            trade_id=trade_id,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            correlation_id=correlation_id,
            created_at=datetime.now(timezone.utc),
            used_at=None,
        )
        
        assert not token.is_expired()
    
    def test_is_expired_returns_true_for_expired_token(
        self,
        trade_id: uuid.UUID,
        correlation_id: uuid.UUID,
    ) -> None:
        """is_expired should return True for expired token."""
        token = DeepLinkToken(
            token="a" * 64,
            trade_id=trade_id,
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
            correlation_id=correlation_id,
            created_at=datetime.now(timezone.utc) - timedelta(hours=2),
            used_at=None,
        )
        
        assert token.is_expired()
    
    def test_is_used_returns_false_for_unused_token(
        self,
        trade_id: uuid.UUID,
        correlation_id: uuid.UUID,
    ) -> None:
        """is_used should return False for unused token."""
        token = DeepLinkToken(
            token="a" * 64,
            trade_id=trade_id,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            correlation_id=correlation_id,
            created_at=datetime.now(timezone.utc),
            used_at=None,
        )
        
        assert not token.is_used()
    
    def test_is_used_returns_true_for_used_token(
        self,
        trade_id: uuid.UUID,
        correlation_id: uuid.UUID,
    ) -> None:
        """is_used should return True for used token."""
        token = DeepLinkToken(
            token="a" * 64,
            trade_id=trade_id,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            correlation_id=correlation_id,
            created_at=datetime.now(timezone.utc),
            used_at=datetime.now(timezone.utc),
        )
        
        assert token.is_used()
    
    def test_is_valid_returns_true_for_valid_token(
        self,
        trade_id: uuid.UUID,
        correlation_id: uuid.UUID,
    ) -> None:
        """is_valid should return True for valid (not expired, not used) token."""
        token = DeepLinkToken(
            token="a" * 64,
            trade_id=trade_id,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            correlation_id=correlation_id,
            created_at=datetime.now(timezone.utc),
            used_at=None,
        )
        
        assert token.is_valid()
    
    def test_is_valid_returns_false_for_expired_token(
        self,
        trade_id: uuid.UUID,
        correlation_id: uuid.UUID,
    ) -> None:
        """is_valid should return False for expired token."""
        token = DeepLinkToken(
            token="a" * 64,
            trade_id=trade_id,
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
            correlation_id=correlation_id,
            created_at=datetime.now(timezone.utc) - timedelta(hours=2),
            used_at=None,
        )
        
        assert not token.is_valid()
    
    def test_is_valid_returns_false_for_used_token(
        self,
        trade_id: uuid.UUID,
        correlation_id: uuid.UUID,
    ) -> None:
        """is_valid should return False for used token."""
        token = DeepLinkToken(
            token="a" * 64,
            trade_id=trade_id,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            correlation_id=correlation_id,
            created_at=datetime.now(timezone.utc),
            used_at=datetime.now(timezone.utc),
        )
        
        assert not token.is_valid()
    
    def test_to_dict_serializes_correctly(
        self,
        trade_id: uuid.UUID,
        correlation_id: uuid.UUID,
    ) -> None:
        """to_dict should serialize all fields correctly."""
        now = datetime.now(timezone.utc)
        token = DeepLinkToken(
            token="a" * 64,
            trade_id=trade_id,
            expires_at=now + timedelta(hours=1),
            correlation_id=correlation_id,
            created_at=now,
            used_at=None,
        )
        
        data = token.to_dict()
        
        assert data["token"] == "a" * 64
        assert data["trade_id"] == str(trade_id)
        assert data["correlation_id"] == str(correlation_id)
        assert data["used_at"] is None
    
    def test_from_dict_deserializes_correctly(
        self,
        trade_id: uuid.UUID,
        correlation_id: uuid.UUID,
    ) -> None:
        """from_dict should deserialize all fields correctly."""
        now = datetime.now(timezone.utc)
        data = {
            "token": "b" * 64,
            "trade_id": str(trade_id),
            "expires_at": (now + timedelta(hours=1)).isoformat(),
            "correlation_id": str(correlation_id),
            "created_at": now.isoformat(),
            "used_at": None,
        }
        
        token = DeepLinkToken.from_dict(data)
        
        assert token.token == "b" * 64
        assert token.trade_id == trade_id
        assert token.correlation_id == correlation_id
        assert token.used_at is None


# =============================================================================
# DiscordHITLService Tests - send_approval_notification
# =============================================================================

class TestSendApprovalNotification:
    """
    Tests for send_approval_notification() method.
    
    **Feature: hitl-approval-gateway, Task 15.1**
    **Validates: Requirements 8.1, 8.2, 8.3**
    """
    
    def test_sends_notification_successfully(
        self,
        discord_service: DiscordHITLService,
        mock_discord_client: Mock,
        trade_id: uuid.UUID,
        correlation_id: uuid.UUID,
        sample_reasoning_summary: dict,
    ) -> None:
        """Should send notification and return success with token."""
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)
        
        success, token = discord_service.send_approval_notification(
            trade_id=trade_id,
            instrument="BTCZAR",
            side="BUY",
            risk_pct=Decimal("2.50"),
            confidence=Decimal("0.85"),
            request_price=Decimal("1500000.00"),
            reasoning_summary=sample_reasoning_summary,
            expires_at=expires_at,
            correlation_id=correlation_id,
        )
        
        assert success is True
        assert token is not None
        assert isinstance(token, DeepLinkToken)
        assert token.trade_id == trade_id
    
    def test_generates_valid_deep_link_token(
        self,
        discord_service: DiscordHITLService,
        trade_id: uuid.UUID,
        correlation_id: uuid.UUID,
        sample_reasoning_summary: dict,
    ) -> None:
        """Should generate a valid 64-character deep link token."""
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)
        
        success, token = discord_service.send_approval_notification(
            trade_id=trade_id,
            instrument="BTCZAR",
            side="BUY",
            risk_pct=Decimal("2.50"),
            confidence=Decimal("0.85"),
            request_price=Decimal("1500000.00"),
            reasoning_summary=sample_reasoning_summary,
            expires_at=expires_at,
            correlation_id=correlation_id,
        )
        
        assert len(token.token) == DEEP_LINK_TOKEN_LENGTH
        assert all(c in "0123456789abcdef" for c in token.token)
    
    def test_stores_token_in_memory(
        self,
        discord_service: DiscordHITLService,
        trade_id: uuid.UUID,
        correlation_id: uuid.UUID,
        sample_reasoning_summary: dict,
    ) -> None:
        """Should store token in memory store."""
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)
        
        success, token = discord_service.send_approval_notification(
            trade_id=trade_id,
            instrument="BTCZAR",
            side="BUY",
            risk_pct=Decimal("2.50"),
            confidence=Decimal("0.85"),
            request_price=Decimal("1500000.00"),
            reasoning_summary=sample_reasoning_summary,
            expires_at=expires_at,
            correlation_id=correlation_id,
        )
        
        assert token.token in discord_service._token_store
    
    def test_calls_discord_client_send_embed(
        self,
        discord_service: DiscordHITLService,
        mock_discord_client: Mock,
        trade_id: uuid.UUID,
        correlation_id: uuid.UUID,
        sample_reasoning_summary: dict,
    ) -> None:
        """Should call Discord client send_embed method."""
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)
        
        discord_service.send_approval_notification(
            trade_id=trade_id,
            instrument="BTCZAR",
            side="BUY",
            risk_pct=Decimal("2.50"),
            confidence=Decimal("0.85"),
            request_price=Decimal("1500000.00"),
            reasoning_summary=sample_reasoning_summary,
            expires_at=expires_at,
            correlation_id=correlation_id,
        )
        
        mock_discord_client.send_embed.assert_called_once()
    
    def test_handles_discord_client_error_gracefully(
        self,
        discord_service: DiscordHITLService,
        mock_discord_client: Mock,
        trade_id: uuid.UUID,
        correlation_id: uuid.UUID,
        sample_reasoning_summary: dict,
    ) -> None:
        """Should handle Discord client errors gracefully."""
        mock_discord_client.send_embed.side_effect = Exception("Discord API error")
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)
        
        success, token = discord_service.send_approval_notification(
            trade_id=trade_id,
            instrument="BTCZAR",
            side="BUY",
            risk_pct=Decimal("2.50"),
            confidence=Decimal("0.85"),
            request_price=Decimal("1500000.00"),
            reasoning_summary=sample_reasoning_summary,
            expires_at=expires_at,
            correlation_id=correlation_id,
        )
        
        # Should still return token even if Discord fails
        assert success is False
        assert token is not None
    
    def test_works_without_discord_client(
        self,
        mock_db_session: Mock,
        mock_hitl_gateway: Mock,
        allowed_operators: list,
        trade_id: uuid.UUID,
        correlation_id: uuid.UUID,
        sample_reasoning_summary: dict,
    ) -> None:
        """Should work without Discord client (token still generated)."""
        service = DiscordHITLService(
            discord_client=None,
            db_session=mock_db_session,
            hitl_gateway=mock_hitl_gateway,
            allowed_operators=allowed_operators,
        )
        
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)
        
        success, token = service.send_approval_notification(
            trade_id=trade_id,
            instrument="BTCZAR",
            side="BUY",
            risk_pct=Decimal("2.50"),
            confidence=Decimal("0.85"),
            request_price=Decimal("1500000.00"),
            reasoning_summary=sample_reasoning_summary,
            expires_at=expires_at,
            correlation_id=correlation_id,
        )
        
        # Token should still be generated
        assert token is not None
        assert token.trade_id == trade_id


# =============================================================================
# DiscordHITLService Tests - handle_button_interaction
# =============================================================================

class TestHandleButtonInteraction:
    """
    Tests for handle_button_interaction() method.
    
    **Feature: hitl-approval-gateway, Task 15.2**
    **Validates: Requirements 8.4**
    """
    
    def test_rejects_unauthorized_operator(
        self,
        discord_service: DiscordHITLService,
        trade_id: uuid.UUID,
        correlation_id: uuid.UUID,
    ) -> None:
        """Should reject button interaction from unauthorized operator."""
        payload = DiscordButtonPayload(
            trade_id=trade_id,
            action=DiscordButtonAction.APPROVE.value,
            user_id="unauthorized_user",
            correlation_id=correlation_id,
        )
        
        result = discord_service.handle_button_interaction(payload)
        
        assert result.success is False
        assert result.error_code == DiscordHITLErrorCode.UNAUTHORIZED_OPERATOR
    
    def test_accepts_authorized_operator(
        self,
        discord_service: DiscordHITLService,
        mock_hitl_gateway: Mock,
        trade_id: uuid.UUID,
        correlation_id: uuid.UUID,
    ) -> None:
        """Should accept button interaction from authorized operator."""
        # Setup mock gateway response
        mock_result = Mock()
        mock_result.success = True
        mock_result.error_code = None
        mock_result.error_message = None
        mock_hitl_gateway.process_decision.return_value = mock_result
        
        payload = DiscordButtonPayload(
            trade_id=trade_id,
            action=DiscordButtonAction.APPROVE.value,
            user_id="operator_123",  # In allowed_operators
            correlation_id=correlation_id,
        )
        
        result = discord_service.handle_button_interaction(payload)
        
        assert result.success is True
        mock_hitl_gateway.process_decision.assert_called_once()
    
    def test_rejects_invalid_action(
        self,
        discord_service: DiscordHITLService,
        trade_id: uuid.UUID,
        correlation_id: uuid.UUID,
    ) -> None:
        """Should reject invalid button action."""
        payload = DiscordButtonPayload(
            trade_id=trade_id,
            action="INVALID_ACTION",
            user_id="operator_123",
            correlation_id=correlation_id,
        )
        
        result = discord_service.handle_button_interaction(payload)
        
        assert result.success is False
        assert result.error_code == DiscordHITLErrorCode.INVALID_DECISION
    
    def test_calls_gateway_with_correct_decision(
        self,
        discord_service: DiscordHITLService,
        mock_hitl_gateway: Mock,
        trade_id: uuid.UUID,
        correlation_id: uuid.UUID,
    ) -> None:
        """Should call gateway with correct decision parameters."""
        mock_result = Mock()
        mock_result.success = True
        mock_result.error_code = None
        mock_result.error_message = None
        mock_hitl_gateway.process_decision.return_value = mock_result
        
        payload = DiscordButtonPayload(
            trade_id=trade_id,
            action=DiscordButtonAction.REJECT.value,
            user_id="operator_456",
            correlation_id=correlation_id,
        )
        
        discord_service.handle_button_interaction(payload)
        
        call_args = mock_hitl_gateway.process_decision.call_args[0][0]
        assert call_args.trade_id == trade_id
        assert call_args.decision == "REJECT"
        assert call_args.operator_id == "operator_456"
        assert call_args.channel == "DISCORD"
    
    def test_updates_discord_message_on_success(
        self,
        discord_service: DiscordHITLService,
        mock_discord_client: Mock,
        mock_hitl_gateway: Mock,
        trade_id: uuid.UUID,
        correlation_id: uuid.UUID,
    ) -> None:
        """Should update Discord message after successful decision."""
        mock_result = Mock()
        mock_result.success = True
        mock_result.error_code = None
        mock_result.error_message = None
        mock_hitl_gateway.process_decision.return_value = mock_result
        
        payload = DiscordButtonPayload(
            trade_id=trade_id,
            action=DiscordButtonAction.APPROVE.value,
            user_id="operator_123",
            correlation_id=correlation_id,
        )
        
        discord_service.handle_button_interaction(payload)
        
        mock_discord_client.update_message.assert_called_once()


# =============================================================================
# DiscordHITLService Tests - validate_deep_link_token
# =============================================================================

class TestValidateDeepLinkToken:
    """
    Tests for validate_deep_link_token() method.
    
    **Feature: hitl-approval-gateway, Task 15.3**
    **Validates: Requirements 8.5, 8.6**
    """
    
    def test_validates_valid_token(
        self,
        discord_service: DiscordHITLService,
        trade_id: uuid.UUID,
        correlation_id: uuid.UUID,
    ) -> None:
        """Should validate a valid token successfully."""
        # Create and store a valid token
        token = DeepLinkTokenGenerator.create_token(
            trade_id=trade_id,
            correlation_id=correlation_id,
            expiry_seconds=300,
        )
        discord_service._token_store[token.token] = token
        
        result = discord_service.validate_deep_link_token(
            token_value=token.token,
            correlation_id=correlation_id,
        )
        
        assert result.success is True
        assert result.token is not None
        assert result.token.trade_id == trade_id
    
    def test_rejects_nonexistent_token(
        self,
        discord_service: DiscordHITLService,
        correlation_id: uuid.UUID,
    ) -> None:
        """Should reject token that doesn't exist."""
        result = discord_service.validate_deep_link_token(
            token_value="nonexistent" + "a" * 53,
            correlation_id=correlation_id,
        )
        
        assert result.success is False
        assert result.error_code == DiscordHITLErrorCode.TOKEN_NOT_FOUND
    
    def test_rejects_expired_token(
        self,
        discord_service: DiscordHITLService,
        trade_id: uuid.UUID,
        correlation_id: uuid.UUID,
    ) -> None:
        """Should reject expired token."""
        # Create an expired token
        token = DeepLinkToken(
            token="expired" + "a" * 57,
            trade_id=trade_id,
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
            correlation_id=correlation_id,
            created_at=datetime.now(timezone.utc) - timedelta(hours=2),
            used_at=None,
        )
        discord_service._token_store[token.token] = token
        
        result = discord_service.validate_deep_link_token(
            token_value=token.token,
            correlation_id=correlation_id,
        )
        
        assert result.success is False
        assert result.error_code == DiscordHITLErrorCode.TOKEN_EXPIRED
    
    def test_rejects_already_used_token(
        self,
        discord_service: DiscordHITLService,
        trade_id: uuid.UUID,
        correlation_id: uuid.UUID,
    ) -> None:
        """Should reject token that has already been used."""
        # Create a used token
        token = DeepLinkToken(
            token="usedtoken" + "a" * 55,
            trade_id=trade_id,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            correlation_id=correlation_id,
            created_at=datetime.now(timezone.utc),
            used_at=datetime.now(timezone.utc),  # Already used
        )
        discord_service._token_store[token.token] = token
        
        result = discord_service.validate_deep_link_token(
            token_value=token.token,
            correlation_id=correlation_id,
        )
        
        assert result.success is False
        assert result.error_code == DiscordHITLErrorCode.TOKEN_ALREADY_USED
    
    def test_marks_token_as_used_after_validation(
        self,
        discord_service: DiscordHITLService,
        trade_id: uuid.UUID,
        correlation_id: uuid.UUID,
    ) -> None:
        """Should mark token as used after successful validation."""
        # Create a valid token
        token = DeepLinkTokenGenerator.create_token(
            trade_id=trade_id,
            correlation_id=correlation_id,
            expiry_seconds=300,
        )
        discord_service._token_store[token.token] = token
        
        # Validate the token
        result = discord_service.validate_deep_link_token(
            token_value=token.token,
            correlation_id=correlation_id,
        )
        
        assert result.success is True
        # Token should now be marked as used
        assert discord_service._token_store[token.token].used_at is not None
    
    def test_token_cannot_be_used_twice(
        self,
        discord_service: DiscordHITLService,
        trade_id: uuid.UUID,
        correlation_id: uuid.UUID,
    ) -> None:
        """Token should only be usable once (single-use)."""
        # Create a valid token
        token = DeepLinkTokenGenerator.create_token(
            trade_id=trade_id,
            correlation_id=correlation_id,
            expiry_seconds=300,
        )
        discord_service._token_store[token.token] = token
        
        # First validation should succeed
        result1 = discord_service.validate_deep_link_token(
            token_value=token.token,
            correlation_id=correlation_id,
        )
        assert result1.success is True
        
        # Second validation should fail
        result2 = discord_service.validate_deep_link_token(
            token_value=token.token,
            correlation_id=correlation_id,
        )
        assert result2.success is False
        assert result2.error_code == DiscordHITLErrorCode.TOKEN_ALREADY_USED


# =============================================================================
# DiscordHITLService Tests - send_timeout_notification
# =============================================================================

class TestSendTimeoutNotification:
    """
    Tests for send_timeout_notification() method.
    
    **Feature: hitl-approval-gateway, Task 15.5**
    **Validates: Requirements 4.4**
    """
    
    def test_sends_timeout_notification_successfully(
        self,
        discord_service: DiscordHITLService,
        mock_discord_client: Mock,
        trade_id: uuid.UUID,
        correlation_id: uuid.UUID,
    ) -> None:
        """Should send timeout notification successfully."""
        requested_at = datetime.now(timezone.utc) - timedelta(minutes=5)
        expires_at = datetime.now(timezone.utc)
        
        result = discord_service.send_timeout_notification(
            trade_id=trade_id,
            instrument="BTCZAR",
            side="BUY",
            risk_pct=Decimal("2.50"),
            request_price=Decimal("1500000.00"),
            requested_at=requested_at,
            expires_at=expires_at,
            correlation_id=correlation_id,
        )
        
        assert result is True
        mock_discord_client.send_message.assert_called_once()
    
    def test_timeout_notification_includes_trade_details(
        self,
        discord_service: DiscordHITLService,
        mock_discord_client: Mock,
        trade_id: uuid.UUID,
        correlation_id: uuid.UUID,
    ) -> None:
        """Should include trade details in timeout notification."""
        requested_at = datetime.now(timezone.utc) - timedelta(minutes=5)
        expires_at = datetime.now(timezone.utc)
        
        discord_service.send_timeout_notification(
            trade_id=trade_id,
            instrument="ETHZAR",
            side="SELL",
            risk_pct=Decimal("1.50"),
            request_price=Decimal("50000.00"),
            requested_at=requested_at,
            expires_at=expires_at,
            correlation_id=correlation_id,
        )
        
        # Get the message that was sent
        call_args = mock_discord_client.send_message.call_args[0][0]
        
        # Verify trade details are included
        assert "ETHZAR" in call_args
        assert "SELL" in call_args
        assert "1.50" in call_args or "1.5" in call_args
        assert "50000" in call_args
        assert str(trade_id) in call_args
    
    def test_timeout_notification_includes_timeout_reason(
        self,
        discord_service: DiscordHITLService,
        mock_discord_client: Mock,
        trade_id: uuid.UUID,
        correlation_id: uuid.UUID,
    ) -> None:
        """Should include timeout reason in notification."""
        requested_at = datetime.now(timezone.utc) - timedelta(minutes=5)
        expires_at = datetime.now(timezone.utc)
        
        discord_service.send_timeout_notification(
            trade_id=trade_id,
            instrument="BTCZAR",
            side="BUY",
            risk_pct=Decimal("2.50"),
            request_price=Decimal("1500000.00"),
            requested_at=requested_at,
            expires_at=expires_at,
            correlation_id=correlation_id,
        )
        
        call_args = mock_discord_client.send_message.call_args[0][0]
        
        # Verify timeout reason is included
        assert "HITL_TIMEOUT" in call_args
        assert "REJECTED" in call_args
    
    def test_timeout_notification_returns_false_without_client(
        self,
        mock_db_session: Mock,
        mock_hitl_gateway: Mock,
        allowed_operators: list,
        trade_id: uuid.UUID,
        correlation_id: uuid.UUID,
    ) -> None:
        """Should return False when no Discord client configured."""
        service = DiscordHITLService(
            discord_client=None,
            db_session=mock_db_session,
            hitl_gateway=mock_hitl_gateway,
            allowed_operators=allowed_operators,
        )
        
        requested_at = datetime.now(timezone.utc) - timedelta(minutes=5)
        expires_at = datetime.now(timezone.utc)
        
        result = service.send_timeout_notification(
            trade_id=trade_id,
            instrument="BTCZAR",
            side="BUY",
            risk_pct=Decimal("2.50"),
            request_price=Decimal("1500000.00"),
            requested_at=requested_at,
            expires_at=expires_at,
            correlation_id=correlation_id,
        )
        
        assert result is False
    
    def test_timeout_notification_handles_discord_error_gracefully(
        self,
        discord_service: DiscordHITLService,
        mock_discord_client: Mock,
        trade_id: uuid.UUID,
        correlation_id: uuid.UUID,
    ) -> None:
        """Should handle Discord errors gracefully."""
        mock_discord_client.send_message.side_effect = Exception("Discord API error")
        
        requested_at = datetime.now(timezone.utc) - timedelta(minutes=5)
        expires_at = datetime.now(timezone.utc)
        
        result = discord_service.send_timeout_notification(
            trade_id=trade_id,
            instrument="BTCZAR",
            side="BUY",
            risk_pct=Decimal("2.50"),
            request_price=Decimal("1500000.00"),
            requested_at=requested_at,
            expires_at=expires_at,
            correlation_id=correlation_id,
        )
        
        assert result is False
    
    def test_timeout_notification_includes_correlation_id(
        self,
        discord_service: DiscordHITLService,
        mock_discord_client: Mock,
        trade_id: uuid.UUID,
        correlation_id: uuid.UUID,
    ) -> None:
        """Should include correlation_id in notification for audit."""
        requested_at = datetime.now(timezone.utc) - timedelta(minutes=5)
        expires_at = datetime.now(timezone.utc)
        
        discord_service.send_timeout_notification(
            trade_id=trade_id,
            instrument="BTCZAR",
            side="BUY",
            risk_pct=Decimal("2.50"),
            request_price=Decimal("1500000.00"),
            requested_at=requested_at,
            expires_at=expires_at,
            correlation_id=correlation_id,
        )
        
        call_args = mock_discord_client.send_message.call_args[0][0]
        
        # Verify correlation_id is included
        assert str(correlation_id) in call_args


# =============================================================================
# DiscordHITLService Tests - Utility Methods
# =============================================================================

class TestUtilityMethods:
    """Tests for utility methods."""
    
    def test_add_allowed_operator(
        self,
        discord_service: DiscordHITLService,
    ) -> None:
        """Should add operator to allowed list."""
        discord_service.add_allowed_operator("new_operator")
        
        assert "new_operator" in discord_service.get_allowed_operators()
    
    def test_remove_allowed_operator(
        self,
        discord_service: DiscordHITLService,
    ) -> None:
        """Should remove operator from allowed list."""
        discord_service.remove_allowed_operator("operator_123")
        
        assert "operator_123" not in discord_service.get_allowed_operators()
    
    def test_clear_token_store(
        self,
        discord_service: DiscordHITLService,
        trade_id: uuid.UUID,
        correlation_id: uuid.UUID,
    ) -> None:
        """Should clear token store."""
        # Add a token
        token = DeepLinkTokenGenerator.create_token(
            trade_id=trade_id,
            correlation_id=correlation_id,
        )
        discord_service._token_store[token.token] = token
        
        # Clear store
        discord_service.clear_token_store()
        
        assert len(discord_service._token_store) == 0


# =============================================================================
# Factory Function Tests
# =============================================================================

class TestFactoryFunction:
    """Tests for create_discord_hitl_service factory function."""
    
    def test_creates_service_with_defaults(self) -> None:
        """Should create service with default values."""
        service = create_discord_hitl_service()
        
        assert isinstance(service, DiscordHITLService)
        assert service._hub_base_url == DEFAULT_HUB_BASE_URL
        assert service._token_expiry_seconds == DEFAULT_TOKEN_EXPIRY_SECONDS
    
    def test_creates_service_with_custom_values(
        self,
        mock_discord_client: Mock,
        mock_db_session: Mock,
        mock_hitl_gateway: Mock,
        allowed_operators: list,
    ) -> None:
        """Should create service with custom values."""
        service = create_discord_hitl_service(
            discord_client=mock_discord_client,
            db_session=mock_db_session,
            hitl_gateway=mock_hitl_gateway,
            allowed_operators=allowed_operators,
            hub_base_url="https://custom-hub/approvals",
            token_expiry_seconds=600,
        )
        
        assert service._discord_client == mock_discord_client
        assert service._db_session == mock_db_session
        assert service._hitl_gateway == mock_hitl_gateway
        assert service._hub_base_url == "https://custom-hub/approvals"
        assert service._token_expiry_seconds == 600

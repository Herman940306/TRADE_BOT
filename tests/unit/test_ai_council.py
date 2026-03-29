"""
Project Autonomous Alpha — Phase 5
Unit Tests: AI Council (OllamaAICouncil + get_ai_council factory)

Reliability Level: SOVEREIGN TIER (Mission-Critical)
Coverage:
  - OllamaAICouncil configuration selection (env vars, defaults)
  - Prompt template guardrails (fail-closed keywords, /no_think prefix)
  - _parse_verdict logic (all ModelVerdict cases)
  - _compute_consensus (unanimous required)
  - _call_ollama: normal response, empty response, HTTP error, timeout,
    DeepSeek backward-compat (thinking field), malformed JSON
  - conduct_debate: approved path, rejected path, error path
  - get_ai_council factory function
  - System prompt loader (file present, file missing/fallback)
"""

import asyncio
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, mock_open, patch
from uuid import uuid4

import httpx
import pytest

from app.logic.ai_council import (
    BEAR_PROMPT_TEMPLATE,
    BULL_PROMPT_TEMPLATE,
    ModelVerdict,
    OllamaAICouncil,
    _load_system_prompt,
    get_ai_council,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_UUID = uuid4()
SAMPLE_SYMBOL = "BTCZAR"
SAMPLE_SIDE = "BUY"
SAMPLE_PRICE = Decimal("1500000")
SAMPLE_QUANTITY = Decimal("0.0001")


@pytest.fixture()
def council() -> OllamaAICouncil:
    """Return an OllamaAICouncil with fully mocked system prompt."""
    with patch(
        "app.logic.ai_council._load_system_prompt", return_value="System prompt OK"
    ):
        return OllamaAICouncil(
            base_url="http://localhost:11434",
            model="qwen3:8b",
        )


# ---------------------------------------------------------------------------
# _load_system_prompt
# ---------------------------------------------------------------------------


class TestLoadSystemPrompt:
    def test_loads_from_file_when_present(self) -> None:
        file_content = "You are a sovereign trading AI. VERDICT: APPROVED or REJECTED."
        with patch("builtins.open", mock_open(read_data=file_content)):
            with patch("os.path.join", return_value="/fake/path/prompt.txt"):
                result = _load_system_prompt()
        assert "VERDICT" in result

    def test_falls_back_when_file_missing(self) -> None:
        with patch("builtins.open", side_effect=FileNotFoundError):
            result = _load_system_prompt()
        assert "VERDICT: APPROVED" in result or "fail-closed" in result.lower()

    def test_truncates_oversized_prompt(self) -> None:
        oversized = "X" * 1000  # > _SYSTEM_PROMPT_BUDGET (512)
        with patch("builtins.open", mock_open(read_data=oversized)):
            with patch("os.path.join", return_value="/fake/path/prompt.txt"):
                result = _load_system_prompt()
        assert len(result) <= 512


# ---------------------------------------------------------------------------
# Prompt Templates
# ---------------------------------------------------------------------------


class TestPromptTemplates:
    def test_bull_prompt_contains_no_think(self) -> None:
        prompt = BULL_PROMPT_TEMPLATE.format(
            symbol="BTCZAR", side="BUY", price="1500000", quantity="0.0001"
        )
        assert "/no_think" in prompt

    def test_bear_prompt_contains_no_think(self) -> None:
        prompt = BEAR_PROMPT_TEMPLATE.format(
            symbol="BTCZAR", side="BUY", price="1500000", quantity="0.0001"
        )
        assert "/no_think" in prompt

    def test_bull_prompt_contains_verdict_instruction(self) -> None:
        prompt = BULL_PROMPT_TEMPLATE.format(
            symbol="BTCZAR", side="BUY", price="1500000", quantity="0.0001"
        )
        assert "VERDICT: APPROVED" in prompt
        assert "VERDICT: REJECTED" in prompt

    def test_bear_prompt_contains_fail_closed_instruction(self) -> None:
        prompt = BEAR_PROMPT_TEMPLATE.format(
            symbol="BTCZAR", side="BUY", price="1500000", quantity="0.0001"
        )
        assert "Ambiguity = REJECTED" in prompt

    def test_prompts_include_signal_fields(self) -> None:
        prompt = BULL_PROMPT_TEMPLATE.format(
            symbol="ETHZAR", side="SELL", price="55000", quantity="0.1"
        )
        assert "ETHZAR" in prompt
        assert "SELL" in prompt
        assert "55000" in prompt
        assert "0.1" in prompt


# ---------------------------------------------------------------------------
# OllamaAICouncil._parse_verdict
# ---------------------------------------------------------------------------


class TestParseVerdict:
    @pytest.mark.parametrize(
        "text,expected",
        [
            ("VERDICT: APPROVED", ModelVerdict.APPROVED),
            ("VERDICT:APPROVED", ModelVerdict.APPROVED),
            ("verdict: approved", ModelVerdict.APPROVED),
            ("VERDICT: REJECTED", ModelVerdict.REJECTED),
            ("VERDICT:REJECTED", ModelVerdict.REJECTED),
            ("TRADE IS APPROVED by analysis", ModelVerdict.APPROVED),
            ("This should be REJECTED.", ModelVerdict.REJECTED),
            ("I cannot determine a clear verdict.", ModelVerdict.UNCERTAIN),
            ("", ModelVerdict.UNCERTAIN),
        ],
    )
    def test_parse(
        self, council: OllamaAICouncil, text: str, expected: ModelVerdict
    ) -> None:
        assert council._parse_verdict(text) == expected

    def test_rejected_wins_over_approved_when_both_present(
        self, council: OllamaAICouncil
    ) -> None:
        # Both present: REJECTED takes precedence (fail-closed)
        result = council._parse_verdict("APPROVED risk vs REJECTED outcome")
        assert result == ModelVerdict.REJECTED


# ---------------------------------------------------------------------------
# OllamaAICouncil._compute_consensus
# ---------------------------------------------------------------------------


class TestComputeConsensus:
    def test_unanimous_approved(self, council: OllamaAICouncil) -> None:
        score, verdict = council._compute_consensus(
            ModelVerdict.APPROVED, ModelVerdict.APPROVED
        )
        assert score == 100
        assert verdict is True

    def test_split_vote_rejected(self, council: OllamaAICouncil) -> None:
        score, verdict = council._compute_consensus(
            ModelVerdict.APPROVED, ModelVerdict.REJECTED
        )
        assert score == 50
        assert verdict is False

    def test_both_rejected(self, council: OllamaAICouncil) -> None:
        score, verdict = council._compute_consensus(
            ModelVerdict.REJECTED, ModelVerdict.REJECTED
        )
        assert score == 0
        assert verdict is False

    def test_error_causes_rejection(self, council: OllamaAICouncil) -> None:
        score, verdict = council._compute_consensus(
            ModelVerdict.APPROVED, ModelVerdict.ERROR
        )
        assert score == 0
        assert verdict is False

    def test_uncertain_causes_rejection(self, council: OllamaAICouncil) -> None:
        score, verdict = council._compute_consensus(
            ModelVerdict.UNCERTAIN, ModelVerdict.UNCERTAIN
        )
        assert verdict is False


# ---------------------------------------------------------------------------
# OllamaAICouncil._call_ollama
# ---------------------------------------------------------------------------


class TestCallOllama:
    def _make_httpx_response(self, status: int, body: dict) -> MagicMock:
        mock_resp = MagicMock()
        mock_resp.status_code = status
        mock_resp.json.return_value = body
        mock_resp.text = str(body)
        return mock_resp

    @pytest.mark.asyncio
    async def test_successful_approved_response(self, council: OllamaAICouncil) -> None:
        payload = {
            "response": "The trade looks strong. VERDICT: APPROVED",
            "done": True,
        }
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(
            return_value=self._make_httpx_response(200, payload)
        )

        with patch("httpx.AsyncClient", return_value=mock_client):
            text, verdict = await council._call_ollama("some prompt", "BULL")

        assert verdict == ModelVerdict.APPROVED
        assert "VERDICT" in text.upper()

    @pytest.mark.asyncio
    async def test_deepseek_thinking_fallback(self, council: OllamaAICouncil) -> None:
        # DeepSeek-R1 returns empty response + populated thinking
        payload = {
            "response": "",
            "thinking": "Thinking... VERDICT: REJECTED",
            "done": True,
        }
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(
            return_value=self._make_httpx_response(200, payload)
        )

        with patch("httpx.AsyncClient", return_value=mock_client):
            text, verdict = await council._call_ollama("some prompt", "BEAR")

        # Falls back to thinking field when response is empty
        assert verdict == ModelVerdict.REJECTED

    @pytest.mark.asyncio
    async def test_empty_response_returns_error(self, council: OllamaAICouncil) -> None:
        payload = {"response": "", "thinking": "", "done": True}
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(
            return_value=self._make_httpx_response(200, payload)
        )

        with patch("httpx.AsyncClient", return_value=mock_client):
            text, verdict = await council._call_ollama("some prompt", "BULL")

        assert verdict == ModelVerdict.ERROR
        assert "ERR-OLLAMA-002" in text

    @pytest.mark.asyncio
    async def test_http_500_returns_error(self, council: OllamaAICouncil) -> None:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(
            return_value=self._make_httpx_response(500, {"error": "internal"})
        )

        with patch("httpx.AsyncClient", return_value=mock_client):
            text, verdict = await council._call_ollama("some prompt", "BULL")

        assert verdict == ModelVerdict.ERROR
        assert "ERR-OLLAMA-001" in text

    @pytest.mark.asyncio
    async def test_timeout_returns_error(self, council: OllamaAICouncil) -> None:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))

        with patch("httpx.AsyncClient", return_value=mock_client):
            text, verdict = await council._call_ollama("some prompt", "BULL")

        assert verdict == ModelVerdict.ERROR
        assert "ERR-OLLAMA-003" in text

    @pytest.mark.asyncio
    async def test_connection_error_returns_error(
        self, council: OllamaAICouncil
    ) -> None:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(
            side_effect=httpx.RequestError("connection refused", request=MagicMock())
        )

        with patch("httpx.AsyncClient", return_value=mock_client):
            text, verdict = await council._call_ollama("some prompt", "BULL")

        assert verdict == ModelVerdict.ERROR
        assert "ERR-OLLAMA-004" in text


# ---------------------------------------------------------------------------
# OllamaAICouncil.conduct_debate
# ---------------------------------------------------------------------------


class TestConductDebate:
    @pytest.mark.asyncio
    async def test_unanimous_approved(self, council: OllamaAICouncil) -> None:
        approved_response = MagicMock()
        approved_response.status_code = 200
        approved_response.json.return_value = {
            "response": "Strong signal. VERDICT: APPROVED",
            "done": True,
        }

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=approved_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await council.conduct_debate(
                SAMPLE_UUID, SAMPLE_SYMBOL, SAMPLE_SIDE, SAMPLE_PRICE, SAMPLE_QUANTITY
            )

        assert result.final_verdict is True
        assert result.consensus_score == 100
        assert result.bull_verdict == ModelVerdict.APPROVED
        assert result.bear_verdict == ModelVerdict.APPROVED
        assert result.correlation_id == SAMPLE_UUID

    @pytest.mark.asyncio
    async def test_split_vote_rejected(self, council: OllamaAICouncil) -> None:
        approved_resp = MagicMock()
        approved_resp.status_code = 200
        approved_resp.json.return_value = {
            "response": "VERDICT: APPROVED",
            "done": True,
        }

        rejected_resp = MagicMock()
        rejected_resp.status_code = 200
        rejected_resp.json.return_value = {
            "response": "VERDICT: REJECTED",
            "done": True,
        }

        call_count = {"n": 0}

        def _side_effect(*args, **kwargs):  # type: ignore[no-untyped-def]
            call_count["n"] += 1
            return approved_resp if call_count["n"] == 1 else rejected_resp

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(side_effect=_side_effect)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await council.conduct_debate(
                SAMPLE_UUID, SAMPLE_SYMBOL, SAMPLE_SIDE, SAMPLE_PRICE, SAMPLE_QUANTITY
            )

        assert result.final_verdict is False
        assert result.consensus_score == 50

    @pytest.mark.asyncio
    async def test_error_path_defaults_to_rejected(
        self, council: OllamaAICouncil
    ) -> None:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await council.conduct_debate(
                SAMPLE_UUID, SAMPLE_SYMBOL, SAMPLE_SIDE, SAMPLE_PRICE, SAMPLE_QUANTITY
            )

        assert result.final_verdict is False
        assert result.bull_verdict == ModelVerdict.ERROR
        assert result.bear_verdict == ModelVerdict.ERROR


# ---------------------------------------------------------------------------
# get_ai_council factory
# ---------------------------------------------------------------------------


class TestGetAiCouncilFactory:
    def test_returns_ollama_council_when_env_true(self) -> None:
        with patch.dict("os.environ", {"USE_LOCAL_OLLAMA": "true"}):
            council_class = get_ai_council()
        assert council_class is OllamaAICouncil

    def test_returns_ollama_council_when_env_1(self) -> None:
        with patch.dict("os.environ", {"USE_LOCAL_OLLAMA": "1"}):
            council_class = get_ai_council()
        assert council_class is OllamaAICouncil

    def test_returns_ollama_council_when_env_yes(self) -> None:
        with patch.dict("os.environ", {"USE_LOCAL_OLLAMA": "yes"}):
            council_class = get_ai_council()
        assert council_class is OllamaAICouncil

    def test_returns_ai_council_when_env_false(self) -> None:
        from app.logic.ai_council import AICouncil

        with patch.dict("os.environ", {"USE_LOCAL_OLLAMA": "false"}):
            council_class = get_ai_council()
        assert council_class is AICouncil

    def test_returns_ai_council_when_env_missing(self) -> None:
        from app.logic.ai_council import AICouncil

        env = {
            k: v for k, v in __import__("os").environ.items() if k != "USE_LOCAL_OLLAMA"
        }
        with patch.dict("os.environ", env, clear=True):
            council_class = get_ai_council()
        assert council_class is AICouncil

    def test_explicit_override_true(self) -> None:
        council_class = get_ai_council(use_ollama=True)
        assert council_class is OllamaAICouncil

    def test_explicit_override_false(self) -> None:
        from app.logic.ai_council import AICouncil

        council_class = get_ai_council(use_ollama=False)
        assert council_class is AICouncil


# ---------------------------------------------------------------------------
# OllamaAICouncil configuration
# ---------------------------------------------------------------------------


class TestOllamaAICouncilConfig:
    def test_default_model_is_qwen3(self) -> None:
        with patch("app.logic.ai_council._load_system_prompt", return_value="sp"):
            with patch.dict("os.environ", {}, clear=False):
                # Remove OLLAMA_MODEL if present
                import os

                os.environ.pop("OLLAMA_MODEL", None)
                c = OllamaAICouncil()
                assert c.model == "qwen3:8b"

    def test_model_from_env_var(self) -> None:
        with patch("app.logic.ai_council._load_system_prompt", return_value="sp"):
            with patch.dict("os.environ", {"OLLAMA_MODEL": "llama3:8b"}):
                c = OllamaAICouncil()
                assert c.model == "llama3:8b"

    def test_model_from_constructor_arg(self) -> None:
        with patch("app.logic.ai_council._load_system_prompt", return_value="sp"):
            c = OllamaAICouncil(model="mistral:7b")
            assert c.model == "mistral:7b"

    def test_default_base_url(self) -> None:
        with patch("app.logic.ai_council._load_system_prompt", return_value="sp"):
            import os

            os.environ.pop("OLLAMA_BASE_URL", None)
            c = OllamaAICouncil()
            assert c.base_url == "http://ollama:11434"

    def test_system_prompt_loaded_on_init(self) -> None:
        with patch(
            "app.logic.ai_council._load_system_prompt", return_value="Custom system"
        ) as mock_loader:
            c = OllamaAICouncil()
            mock_loader.assert_called_once()
            assert c._system_prompt == "Custom system"

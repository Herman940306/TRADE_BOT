"""
Project Autonomous Alpha — Phase 5
Integration Tests: Ollama Service (requires live Ollama daemon)

Reliability Level: SOVEREIGN TIER
Scope: Integration — hits real Ollama HTTP API (skipped if daemon unreachable)

These tests are SKIPPED automatically when:
  - OLLAMA_BASE_URL is unreachable (pytest.mark.skipif logic)
  - The qwen3:8b model is not yet pulled

To run manually (with Ollama running):
    pytest tests/integration/test_ollama_integration.py -v

To skip in CI:
    pytest tests/integration/ -m "not integration"
"""

import asyncio
from decimal import Decimal
import os
from uuid import uuid4

import pytest

# ---------------------------------------------------------------------------
# Availability guard — skip entire module if Ollama is unreachable
# ---------------------------------------------------------------------------


def _ollama_reachable() -> bool:
    """Synchronous probe for pytest.mark.skipif."""
    import httpx

    url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434") + "/api/tags"
    try:
        resp = httpx.get(url, timeout=3.0)
        return resp.status_code == 200
    except Exception:
        return False


def _model_present() -> bool:
    """Return True if OLLAMA_MODEL is listed in the tag registry."""
    import httpx

    model_base = os.getenv("OLLAMA_MODEL", "qwen3:8b").split(":")[0]
    url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434") + "/api/tags"
    try:
        data = httpx.get(url, timeout=3.0).json()
        models = [m.get("name", "").split(":")[0] for m in data.get("models", [])]
        return model_base in models
    except Exception:
        return False


pytestmark = pytest.mark.integration

skip_no_ollama = pytest.mark.skipif(
    not _ollama_reachable(),
    reason="Ollama daemon unreachable (OLLAMA_BASE_URL not live)",
)

skip_no_model = pytest.mark.skipif(
    not _model_present(),
    reason="OLLAMA_MODEL not pulled — run: bash scripts/pull_ollama_model.sh",
)


# ---------------------------------------------------------------------------
# Integration: Ollama health module
# ---------------------------------------------------------------------------


@skip_no_ollama
@pytest.mark.asyncio
async def test_ping_ollama_returns_true() -> None:
    from app.logic.ollama_health import ping_ollama

    result = await ping_ollama()
    assert result is True


@skip_no_ollama
@pytest.mark.asyncio
async def test_unreachable_url_returns_false() -> None:
    from app.logic.ollama_health import ping_ollama

    result = await ping_ollama(base_url="http://127.0.0.1:9999")
    assert result is False


@skip_no_ollama
@skip_no_model
@pytest.mark.asyncio
async def test_model_loaded_returns_true() -> None:
    from app.logic.ollama_health import model_loaded

    result = await model_loaded()
    assert result is True


@skip_no_ollama
@pytest.mark.asyncio
async def test_model_loaded_false_for_nonexistent() -> None:
    from app.logic.ollama_health import model_loaded

    result = await model_loaded(model_name="nonexistent-model:99b")
    assert result is False


@skip_no_ollama
@skip_no_model
@pytest.mark.asyncio
async def test_check_ollama_health_full_pass() -> None:
    from app.logic.ollama_health import check_ollama_health

    status = await check_ollama_health()
    assert status.reachable is True
    assert status.model_present is True
    # smoke_test may be slow on first cold start; just log
    summary = status.summary()
    assert "OLLAMA" in summary.upper() or "ollama" in summary.lower()


# ---------------------------------------------------------------------------
# Integration: OllamaAICouncil live inference
# ---------------------------------------------------------------------------


@skip_no_ollama
@skip_no_model
@pytest.mark.asyncio
async def test_live_single_call_returns_verdict() -> None:
    """Validate that a live inference call returns a known ModelVerdict."""
    from unittest.mock import patch

    from app.logic.ai_council import ModelVerdict, OllamaAICouncil

    with patch(
        "app.logic.ai_council._load_system_prompt",
        return_value=(
            "You are a trading evaluator. Always end with VERDICT: APPROVED or VERDICT: REJECTED."
        ),
    ):
        council = OllamaAICouncil(
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            model=os.getenv("OLLAMA_MODEL", "qwen3:8b"),
        )

    text, verdict = await council._call_ollama(
        "/no_think\nTrade: BTCZAR BUY 1500000 ZAR qty=0.0001. Reply VERDICT: APPROVED.",
        "INTEGRATION_TEST",
    )
    assert verdict in (
        ModelVerdict.APPROVED,
        ModelVerdict.REJECTED,
        ModelVerdict.UNCERTAIN,
    )
    assert isinstance(text, str)
    assert len(text) > 0


@skip_no_ollama
@skip_no_model
@pytest.mark.asyncio
async def test_live_conduct_debate_returns_debate_result() -> None:
    """Full Bull/Bear debate against live Ollama — validates DebateResult structure."""
    from unittest.mock import patch

    from app.logic.ai_council import OllamaAICouncil

    with patch(
        "app.logic.ai_council._load_system_prompt",
        return_value=(
            "You are a trading evaluator. Always end with VERDICT: APPROVED or VERDICT: REJECTED."
        ),
    ):
        council = OllamaAICouncil(
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            model=os.getenv("OLLAMA_MODEL", "qwen3:8b"),
        )

    result = await council.conduct_debate(
        correlation_id=uuid4(),
        symbol="BTCZAR",
        side="BUY",
        price=Decimal("1500000"),
        quantity=Decimal("0.0001"),
    )

    assert result.correlation_id is not None
    assert isinstance(result.bull_reasoning, str)
    assert isinstance(result.bear_reasoning, str)
    assert 0 <= result.consensus_score <= 100
    assert isinstance(result.final_verdict, bool)


# ---------------------------------------------------------------------------
# Integration: Smoke test from health module
# ---------------------------------------------------------------------------


@skip_no_ollama
@skip_no_model
@pytest.mark.asyncio
async def test_smoke_test_passes_for_loaded_model() -> None:
    from app.logic.ollama_health import smoke_test

    result = await smoke_test(timeout=90.0)
    assert result is True

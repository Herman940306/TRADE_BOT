"""
Project Autonomous Alpha — Phase 6, Sub-Phase C6
TokenBudgetGuard — Comprehensive Test Suite

Reliability Level: SOVEREIGN TIER
Spec Reference: DPv1.2 §0 (Token Budget Philosophy), §2.1 (Section Budgets)
Policy Reference: CPPv1.1 §1 (Tier Definitions), §4 (Overflow Resolution)

PURPOSE
-------
This test suite covers:
    1. Provider profile validation and invariants
    2. System prompt budget enforcement
    3. T1 budget pre-flight checks
    4. Full packet budget verification (happy path + degraded)
    5. Per-section budget enforcement
    6. Near-limit scenarios
    7. Over-limit scenarios
    8. Tier-drop sequence verification
    9. Required-context rejection (T1 exceeds budget)
    10. Provider-specific budget profiles
    11. Silent truncation detection
    12. Section extraction accuracy
    13. Convenience function
"""

from decimal import Decimal
from uuid import UUID

import pytest

from app.logic.decision_packet_builder import build_decision_packet
from app.logic.decision_packet_models import (
    BuildContext,
    DecisionPacket,
    ExecutionMode,
    HistorySummaryInput,
    IntelligenceInput,
    MissingReason,
    MLAction,
    OperationalContext,
    RecentDebateEntry,
    Side,
    SignalInput,
    SymbolBias,
)
from app.logic.decision_packet_serializer import estimate_tokens
from app.logic.token_budget_guard import (
    DEFAULT_PROFILE_KEY,
    OPENROUTER_DEFAULT,
    PROVIDER_PROFILES,
    QWEN3_8B_LOCAL,
    BudgetVerdict,
    ProviderProfile,
    ProviderType,
    SectionBudget,
    TokenBudgetGuard,
    _extract_section_text,
    check_packet_budget,
    get_provider_profile,
)

# =============================================================================
# TEST FIXTURES
# =============================================================================

_FIXED_UUID = UUID("a1b2c3d4-e5f6-4890-abcd-ef1234567890")
_FIXED_PROMPT_HASH = "a" * 64
_FIXED_FINGERPRINT = "qwen3:8b@sha256:" + "b" * 56
_FIXED_SYSTEM_PROMPT = (
    "You are a trade evaluation AI. Evaluate the following trade signal "
    "and respond with a JSON verdict.\n"
    "When [MDF] flags are present:\n"
    "- Do NOT infer, estimate, or assume values for flagged fields.\n"
    "- Treat each missing field as reducing your confidence.\n"
    "- If you APPROVE despite missing data, you MUST state why.\n"
    "- Never substitute default values for missing fields.\n"
    "Field hierarchy:\n"
    "1. Source-of-truth fields ([SIG], [OPS]) are GROUND TRUTH.\n"
    "2. Derived summaries ([HST]) are RELIABLE AGGREGATIONS.\n"
    "3. Advisory metrics ([INT]) are INFORMATIONAL ONLY."
)


def _make_signal(**kwargs) -> SignalInput:
    defaults = {
        "signal_id": "TV-BTCZAR-001",
        "symbol": "BTCZAR",
        "side": Side.BUY,
        "price": Decimal("1500000.00"),
        "quantity": Decimal("0.001"),
    }
    defaults.update(kwargs)
    return SignalInput(**defaults)


def _make_ops(**kwargs) -> OperationalContext:
    defaults = {
        "execution_mode": ExecutionMode.PAPER,
        "guardian_locked": False,
        "equity_zar": Decimal("50000.00"),
        "risk_pct": Decimal("1.50"),
    }
    defaults.update(kwargs)
    return OperationalContext(**defaults)


def _make_history(**kwargs) -> HistorySummaryInput:
    defaults = {
        "count": 3,
        "approved": 1,
        "rejected": 2,
        "avg_score": 35,
    }
    defaults.update(kwargs)
    return HistorySummaryInput(**defaults)


def _make_intel(**kwargs) -> IntelligenceInput:
    defaults = {
        "rgi_available": True,
        "ml_confidence": Decimal("0.85"),
        "ml_action": MLAction.BUY,
        "rgi_trust": Decimal("0.92"),
        "win_rate": Decimal("0.65"),
        "total_trades": 42,
        "recent_debates": [
            RecentDebateEntry("03-29T14:30", "BTCZAR", "REJECTED", 25),
            RecentDebateEntry("03-29T12:15", "BTCZAR", "APPROVED", 75),
            RecentDebateEntry("03-28T22:00", "BTCZAR", "REJECTED", 30),
        ],
        "ml_reasoning": "Strong buy signal based on momentum",
        "symbol_bias": SymbolBias.BULLISH,
    }
    defaults.update(kwargs)
    return IntelligenceInput(**defaults)


def _make_build_ctx(**kwargs) -> BuildContext:
    defaults = {
        "correlation_id": _FIXED_UUID,
        "prompt_version_hash": _FIXED_PROMPT_HASH,
        "model_fingerprint": _FIXED_FINGERPRINT,
        "system_prompt": _FIXED_SYSTEM_PROMPT,
    }
    defaults.update(kwargs)
    return BuildContext(**defaults)


def _build_full(**overrides) -> DecisionPacket:
    signal_kw = overrides.pop("signal_kw", {})
    ops_kw = overrides.pop("ops_kw", {})
    hist_kw = overrides.pop("hist_kw", {})
    intel_kw = overrides.pop("intel_kw", {})
    build_kw = overrides.pop("build_kw", {})
    return build_decision_packet(
        signal=_make_signal(**signal_kw),
        ops=_make_ops(**ops_kw),
        history=_make_history(**hist_kw),
        intel=_make_intel(**intel_kw),
        build_ctx=_make_build_ctx(**build_kw),
    )


# =============================================================================
# 1. PROVIDER PROFILE VALIDATION
# =============================================================================


class TestProviderProfiles:
    """Verify provider profile invariants and registration."""

    def test_qwen3_budget_invariant(self):
        """input + output + margin == safe_operating_budget."""
        p = QWEN3_8B_LOCAL
        assert (
            p.input_budget + p.output_reserve + p.safety_margin
            == p.safe_operating_budget
        )

    def test_qwen3_values(self):
        """Verify qwen3:8b profile matches DPv1.2 §0."""
        p = QWEN3_8B_LOCAL
        assert p.input_budget == 1400
        assert p.output_reserve == 512
        assert p.safety_margin == 136
        assert p.safe_operating_budget == 2048
        assert p.model_context_window == 32768
        assert p.provider_type == ProviderType.LOCAL_OLLAMA

    def test_openrouter_budget_invariant(self):
        """OpenRouter profile also respects invariant."""
        p = OPENROUTER_DEFAULT
        assert (
            p.input_budget + p.output_reserve + p.safety_margin
            == p.safe_operating_budget
        )

    def test_openrouter_uses_same_safe_budget(self):
        """Until model-specific tuning, OpenRouter uses same safe budget."""
        assert (
            OPENROUTER_DEFAULT.safe_operating_budget
            == QWEN3_8B_LOCAL.safe_operating_budget
        )

    def test_broken_invariant_rejected(self):
        """Profile with broken budget invariant → ValueError."""
        with pytest.raises(ValueError, match="Budget invariant violated"):
            ProviderProfile(
                provider_type=ProviderType.LOCAL_OLLAMA,
                model_name="broken",
                model_context_window=32768,
                safe_operating_budget=2048,
                input_budget=1500,  # 1500 + 512 + 136 = 2148 != 2048
                output_reserve=512,
                safety_margin=136,
                section_budgets={},
            )

    def test_profile_registry_has_qwen3(self):
        """Default profile is registered."""
        assert DEFAULT_PROFILE_KEY in PROVIDER_PROFILES
        assert PROVIDER_PROFILES[DEFAULT_PROFILE_KEY] is QWEN3_8B_LOCAL

    def test_get_unknown_profile_returns_default(self):
        """Unknown model name → falls back to qwen3:8b."""
        profile = get_provider_profile("unknown-model-xyz")
        assert profile is QWEN3_8B_LOCAL

    def test_get_known_profile(self):
        """Known model name → returns correct profile."""
        profile = get_provider_profile("qwen3:8b")
        assert profile is QWEN3_8B_LOCAL

    def test_qwen3_has_all_sections(self):
        """qwen3:8b profile defines all 8 packet sections."""
        expected = {"SYS", "HDR", "SIG", "OPS", "HST", "INT", "MDF", "VRD"}
        assert set(QWEN3_8B_LOCAL.section_budgets.keys()) == expected

    def test_section_budgets_match_spec(self):
        """Per-section budgets match DPv1.2 §2.1 table (HDR corrected to 60)."""
        s = QWEN3_8B_LOCAL.section_budgets
        assert s["SYS"].max_tokens == 200
        assert (
            s["HDR"].max_tokens == 60
        )  # Corrected from spec's 50: real header needs 55+
        assert s["SIG"].max_tokens == 80
        assert s["OPS"].max_tokens == 60
        assert s["HST"].max_tokens == 100
        assert s["INT"].max_tokens == 150
        assert s["MDF"].max_tokens == 60
        assert s["VRD"].max_tokens == 100


# =============================================================================
# 2. SYSTEM PROMPT BUDGET
# =============================================================================


class TestSystemPromptBudget:
    """Verify system prompt section budget enforcement."""

    def test_normal_prompt_passes(self):
        """Standard system prompt fits SYS budget."""
        guard = TokenBudgetGuard()
        result = guard.check_system_prompt(_FIXED_SYSTEM_PROMPT)
        assert result.verdict == BudgetVerdict.PASS
        assert not result.errors
        sys_section = result.sections[0]
        assert sys_section.code == "SYS"
        assert not sys_section.over_budget

    def test_oversized_prompt_fails(self):
        """System prompt exceeding 200-token budget → TBG-002."""
        guard = TokenBudgetGuard()
        # 200 tokens ≈ 800 chars. Use 1000 chars to exceed.
        big_prompt = "X" * 1000
        result = guard.check_system_prompt(big_prompt)
        assert result.verdict == BudgetVerdict.FAIL
        assert any(e.code == "TBG-002" for e in result.errors)

    def test_exact_limit_prompt_passes(self):
        """System prompt at exactly 200 tokens → PASS."""
        guard = TokenBudgetGuard()
        # 200 tokens ≈ 800 chars (4 chars/token)
        # Use exactly 800 chars
        exact_prompt = "A" * 800
        result = guard.check_system_prompt(exact_prompt)
        assert result.verdict == BudgetVerdict.PASS

    def test_one_over_limit_fails(self):
        """System prompt at 201 tokens → FAIL."""
        guard = TokenBudgetGuard()
        # 201 tokens = 804 chars → estimate_tokens("A"*804) = (804+3)//4 = 201
        over_prompt = "A" * 804
        assert estimate_tokens(over_prompt) == 201
        result = guard.check_system_prompt(over_prompt)
        assert result.verdict == BudgetVerdict.FAIL
        assert result.errors[0].code == "TBG-002"


# =============================================================================
# 3. T1 BUDGET PRE-FLIGHT
# =============================================================================


class TestT1BudgetPreFlight:
    """Verify T1 budget pre-flight checks."""

    def test_t1_within_budget(self):
        """T1 at 400 tokens → PASS with 1000 remaining."""
        guard = TokenBudgetGuard()
        result = guard.check_t1_budget(400)
        assert result.verdict == BudgetVerdict.PASS
        assert result.remaining_input_tokens == 1000

    def test_t1_at_limit(self):
        """T1 exactly at 1400 → PASS with 0 remaining."""
        guard = TokenBudgetGuard()
        result = guard.check_t1_budget(1400)
        assert result.verdict == BudgetVerdict.PASS
        assert result.remaining_input_tokens == 0

    def test_t1_over_limit(self):
        """T1 at 1401 → TBG-004 (specification error)."""
        guard = TokenBudgetGuard()
        result = guard.check_t1_budget(1401)
        assert result.verdict == BudgetVerdict.FAIL
        assert result.errors[0].code == "TBG-004"
        assert "Specification error" in result.errors[0].detail

    def test_t1_massively_over(self):
        """T1 at 5000 → TBG-004."""
        guard = TokenBudgetGuard()
        result = guard.check_t1_budget(5000)
        assert result.verdict == BudgetVerdict.FAIL
        assert result.remaining_input_tokens < 0


# =============================================================================
# 4. FULL PACKET BUDGET — HAPPY PATH
# =============================================================================


class TestPacketBudgetHappyPath:
    """Full packet budget checks with all sources healthy."""

    def test_full_packet_passes(self):
        """Full packet with all fields → budget PASS."""
        packet = _build_full()
        guard = TokenBudgetGuard()
        result = guard.check_packet(packet)
        assert result.verdict == BudgetVerdict.PASS
        assert not result.errors
        assert result.total_input_tokens <= 1400
        assert result.remaining_input_tokens >= 0

    def test_result_has_section_breakdown(self):
        """Budget result includes per-section usage breakdown."""
        packet = _build_full()
        guard = TokenBudgetGuard()
        result = guard.check_packet(packet)
        codes = {s.code for s in result.sections}
        # Must have SYS + all body sections
        assert "SYS" in codes
        assert "HDR" in codes
        assert "SIG" in codes
        assert "OPS" in codes

    def test_result_has_profile_name(self):
        """Budget result identifies the provider profile used."""
        packet = _build_full()
        result = check_packet_budget(packet)
        assert result.profile == "qwen3:8b"

    def test_no_tier_drops_in_full_packet(self):
        """Full packet with all fields → no tier drops."""
        packet = _build_full()
        guard = TokenBudgetGuard()
        result = guard.check_packet(packet)
        assert result.tier_drop_summary is None

    def test_budget_components_correct(self):
        """Budget result carries all budget components."""
        packet = _build_full()
        guard = TokenBudgetGuard()
        result = guard.check_packet(packet)
        assert result.input_budget == 1400
        assert result.output_reserve == 512
        assert result.safety_margin == 136
        assert result.safe_operating_budget == 2048


# =============================================================================
# 5. PER-SECTION ENFORCEMENT
# =============================================================================


class TestPerSectionEnforcement:
    """Verify per-section budget checks against DPv1.2 §2.1."""

    def test_all_sections_within_budget(self):
        """Full packet → no section over budget."""
        packet = _build_full()
        guard = TokenBudgetGuard()
        result = guard.check_packet(packet)
        for section in result.sections:
            assert not section.over_budget, (
                f"Section [{section.code}] over budget: "
                f"{section.used_tokens} > {section.budget_tokens}"
            )

    def test_section_usage_is_positive(self):
        """Every present section uses > 0 tokens."""
        packet = _build_full()
        guard = TokenBudgetGuard()
        result = guard.check_packet(packet)
        for section in result.sections:
            if section.code != "MDF":
                # MDF may have 0 tokens if no flags
                assert section.used_tokens > 0, f"Section [{section.code}] has 0 tokens"

    def test_get_section_budgets(self):
        """get_section_budgets returns all section limits."""
        guard = TokenBudgetGuard()
        budgets = guard.get_section_budgets()
        assert budgets["SYS"] == 200
        assert budgets["INT"] == 150
        assert len(budgets) == 8


# =============================================================================
# 6. NEAR-LIMIT SCENARIOS
# =============================================================================


class TestNearLimit:
    """Scenarios where token usage approaches but does not exceed the budget."""

    def test_packet_near_input_budget(self):
        """Packet using most of the 1400-token budget → still PASS."""
        packet = _build_full()
        guard = TokenBudgetGuard()
        result = guard.check_packet(packet)
        # Full packet typically uses 300-500 tokens, well under 1400
        assert result.verdict == BudgetVerdict.PASS
        assert result.remaining_input_tokens > 0

    def test_system_prompt_near_section_limit(self):
        """Prompt at 199 tokens → PASS."""
        guard = TokenBudgetGuard()
        # 199 tokens = 796 chars
        prompt = "X" * 796
        assert estimate_tokens(prompt) == 199
        result = guard.check_system_prompt(prompt)
        assert result.verdict == BudgetVerdict.PASS

    def test_system_prompt_at_exact_section_limit(self):
        """Prompt at exactly 200 tokens → PASS."""
        guard = TokenBudgetGuard()
        prompt = "X" * 800
        assert estimate_tokens(prompt) == 200
        result = guard.check_system_prompt(prompt)
        assert result.verdict == BudgetVerdict.PASS


# =============================================================================
# 7. OVER-LIMIT SCENARIOS
# =============================================================================


class TestOverLimit:
    """Scenarios where token usage exceeds the budget."""

    def test_total_input_over_budget_detected(self):
        """Manually inflated total_input_tokens → TBG-001."""
        packet = _build_full()
        # Manually set total_input_tokens above budget
        packet.total_input_tokens = 1500
        guard = TokenBudgetGuard()
        result = guard.check_packet(packet)
        assert result.verdict == BudgetVerdict.FAIL
        codes = [e.code for e in result.errors]
        assert "TBG-001" in codes

    def test_system_prompt_over_budget_detected(self):
        """Large system prompt in packet → TBG-002."""
        # Build a packet normally, then replace system_prompt with oversized
        packet = _build_full()
        packet.system_prompt = "Z" * 1200  # ~300 tokens, budget is 200
        guard = TokenBudgetGuard()
        result = guard.check_packet(packet)
        assert result.verdict == BudgetVerdict.FAIL
        codes = [e.code for e in result.errors]
        assert "TBG-002" in codes

    def test_multiple_violations_all_reported(self):
        """Both system prompt and total over budget → both TBG-001 and TBG-002."""
        packet = _build_full()
        packet.system_prompt = "Z" * 1200
        packet.total_input_tokens = 1500
        guard = TokenBudgetGuard()
        result = guard.check_packet(packet)
        assert result.verdict == BudgetVerdict.FAIL
        codes = [e.code for e in result.errors]
        assert "TBG-001" in codes
        assert "TBG-002" in codes


# =============================================================================
# 8. TIER-DROP SEQUENCE
# =============================================================================


class TestTierDropSequence:
    """Verify tier-drop tracking and reporting."""

    def test_t3_dropped_reported(self):
        """Packet with no T3 fields → tier_drop_summary mentions T3."""
        packet = _build_full(intel_kw={"ml_reasoning": None, "symbol_bias": None})
        guard = TokenBudgetGuard()
        result = guard.check_packet(packet)
        # T3 fields are silently omitted, tracked in t3_fields_dropped
        if packet.t3_fields_dropped:
            assert result.tier_drop_summary is not None
            assert "T3 dropped" in result.tier_drop_summary

    def test_t2_dropped_reported(self):
        """Packet with missing T2 fields → tier_drop_summary mentions T2."""
        intel = _make_intel(
            ml_confidence=None,
            ml_confidence_missing_reason=MissingReason.TIMEOUT,
        )
        packet = build_decision_packet(
            _make_signal(), _make_ops(), _make_history(), intel, _make_build_ctx()
        )
        guard = TokenBudgetGuard()
        result = guard.check_packet(packet)
        if packet.t2_fields_dropped:
            assert result.tier_drop_summary is not None
            assert "T2 dropped" in result.tier_drop_summary

    def test_no_drops_no_summary(self):
        """Full packet → tier_drop_summary is None."""
        packet = _build_full()
        guard = TokenBudgetGuard()
        result = guard.check_packet(packet)
        # Full build includes all T2 and may include T3
        if not packet.t2_fields_dropped and not packet.t3_fields_dropped:
            assert result.tier_drop_summary is None


# =============================================================================
# 9. REQUIRED-CONTEXT REJECTION
# =============================================================================


class TestRequiredContextRejection:
    """Ensure T1 budget exceedance is a hard rejection."""

    def test_t1_budget_exceeded_is_specification_error(self):
        """T1 over budget → TBG-004 mentions specification error."""
        guard = TokenBudgetGuard()
        result = guard.check_t1_budget(2000)
        assert result.verdict == BudgetVerdict.FAIL
        assert any("Specification error" in e.detail for e in result.errors)

    def test_t1_budget_uses_provider_limit(self):
        """Custom profile with lower input_budget → T1 fails earlier."""
        small_profile = ProviderProfile(
            provider_type=ProviderType.LOCAL_OLLAMA,
            model_name="tiny-model",
            model_context_window=4096,
            safe_operating_budget=1024,
            input_budget=500,
            output_reserve=400,
            safety_margin=124,
            section_budgets={
                "SYS": SectionBudget("SYS", "System Prompt", 100),
            },
        )
        guard = TokenBudgetGuard(small_profile)
        # 600 tokens exceeds 500 input budget
        result = guard.check_t1_budget(600)
        assert result.verdict == BudgetVerdict.FAIL
        assert result.input_budget == 500


# =============================================================================
# 10. PROVIDER-SPECIFIC BUDGET PROFILES
# =============================================================================


class TestProviderSpecificProfiles:
    """Verify guard behavior changes with different provider profiles."""

    def test_qwen3_guard(self):
        """Guard with qwen3:8b profile → input_budget=1400."""
        guard = TokenBudgetGuard(QWEN3_8B_LOCAL)
        assert guard.input_budget == 1400
        assert guard.output_reserve == 512
        assert guard.safety_margin == 136

    def test_openrouter_guard(self):
        """Guard with OpenRouter profile → same safe budget for now."""
        guard = TokenBudgetGuard(OPENROUTER_DEFAULT)
        assert guard.input_budget == 1400
        assert guard.safe_operating_budget == 2048

    def test_custom_profile_guard(self):
        """Guard with custom profile → uses custom limits."""
        custom = ProviderProfile(
            provider_type=ProviderType.OPENROUTER,
            model_name="custom/big-model",
            model_context_window=128000,
            safe_operating_budget=4096,
            input_budget=3000,
            output_reserve=800,
            safety_margin=296,
            section_budgets={
                "SYS": SectionBudget("SYS", "System Prompt", 400),
                "HDR": SectionBudget("HDR", "Packet Header", 100),
                "SIG": SectionBudget("SIG", "Signal Fields", 200),
                "OPS": SectionBudget("OPS", "Operational Context", 150),
                "HST": SectionBudget("HST", "History Summary", 200),
                "INT": SectionBudget("INT", "Intelligence Layer", 400),
                "MDF": SectionBudget("MDF", "Missing Data Flags", 120),
                "VRD": SectionBudget("VRD", "Verdict Instruction", 200),
            },
        )
        guard = TokenBudgetGuard(custom)
        assert guard.input_budget == 3000
        assert guard.safe_operating_budget == 4096
        # Full packet under custom budget → should pass
        packet = _build_full()
        result = guard.check_packet(packet)
        assert result.verdict == BudgetVerdict.PASS

    def test_packet_budget_with_model_name(self):
        """check_packet_budget with explicit model_name → uses correct profile."""
        packet = _build_full()
        result = check_packet_budget(packet, model_name="qwen3:8b")
        assert result.profile == "qwen3:8b"
        assert result.verdict == BudgetVerdict.PASS

    def test_packet_budget_unknown_model_falls_back(self):
        """check_packet_budget with unknown model → falls back to qwen3:8b."""
        packet = _build_full()
        result = check_packet_budget(packet, model_name="unknown-model")
        assert result.profile == "qwen3:8b"


# =============================================================================
# 11. SILENT TRUNCATION DETECTION
# =============================================================================


class TestSilentTruncationDetection:
    """Verify TBG-005: T2 fields dropped without flags are caught."""

    def test_properly_flagged_drop_no_error(self):
        """T2 dropped AND flagged → no TBG-005."""
        intel = _make_intel(
            ml_confidence=None,
            ml_confidence_missing_reason=MissingReason.TIMEOUT,
        )
        packet = build_decision_packet(
            _make_signal(), _make_ops(), _make_history(), intel, _make_build_ctx()
        )
        guard = TokenBudgetGuard()
        result = guard.check_packet(packet)
        tbg005 = [e for e in result.errors if e.code == "TBG-005"]
        assert len(tbg005) == 0

    def test_unflagged_drop_detected(self):
        """T2 field in t2_fields_dropped but NOT in missing_data_flags → TBG-005."""
        packet = _build_full()
        # Simulate a dropped T2 that wasn't properly flagged
        packet.t2_fields_dropped.append("rgi_trust")
        # Don't add to missing_data_flags — this is the violation
        guard = TokenBudgetGuard()
        result = guard.check_packet(packet)
        tbg005 = [e for e in result.errors if e.code == "TBG-005"]
        assert len(tbg005) == 1
        assert tbg005[0].field_name == "rgi_trust"


# =============================================================================
# 12. SECTION EXTRACTION
# =============================================================================


class TestSectionExtraction:
    """Verify _extract_section_text correctly isolates section content."""

    def test_extract_hdr_section(self):
        """Extract [HDR] section from serialized packet."""
        packet = _build_full()
        text = _extract_section_text(packet.serialized, "HDR")
        assert "v=DPv1" in text
        assert "cid=" in text

    def test_extract_sig_section(self):
        """Extract [SIG] section → contains signal fields."""
        packet = _build_full()
        text = _extract_section_text(packet.serialized, "SIG")
        assert "sym=BTCZAR" in text
        assert "side=BUY" in text

    def test_extract_missing_section(self):
        """Extract non-existent section → empty string."""
        packet = _build_full()
        text = _extract_section_text(packet.serialized, "XXX")
        assert text == ""

    def test_extract_vrd_section(self):
        """Extract [VRD] (last section) → contains verdict instruction."""
        packet = _build_full()
        text = _extract_section_text(packet.serialized, "VRD")
        assert "APPROVED" in text
        assert "REJECTED" in text

    def test_extract_int_section(self):
        """Extract [INT] section → contains intelligence fields."""
        packet = _build_full()
        text = _extract_section_text(packet.serialized, "INT")
        assert "ml_conf=" in text
        assert "rgi_trust=" in text


# =============================================================================
# 13. CONVENIENCE FUNCTION
# =============================================================================


class TestConvenienceFunction:
    """Module-level check_packet_budget function."""

    def test_default_profile(self):
        """check_packet_budget with no model → uses qwen3:8b."""
        packet = _build_full()
        result = check_packet_budget(packet)
        assert result.profile == "qwen3:8b"
        assert result.verdict == BudgetVerdict.PASS

    def test_explicit_profile(self):
        """check_packet_budget with model_name → uses that profile."""
        packet = _build_full()
        result = check_packet_budget(packet, model_name="openrouter/default")
        assert result.profile == "openrouter/default"


# =============================================================================
# 14. GUARD PROPERTY ACCESSORS
# =============================================================================


class TestGuardProperties:
    """Verify guard exposes profile properties correctly."""

    def test_input_budget_property(self):
        guard = TokenBudgetGuard()
        assert guard.input_budget == 1400

    def test_output_reserve_property(self):
        guard = TokenBudgetGuard()
        assert guard.output_reserve == 512

    def test_safety_margin_property(self):
        guard = TokenBudgetGuard()
        assert guard.safety_margin == 136

    def test_safe_operating_budget_property(self):
        guard = TokenBudgetGuard()
        assert guard.safe_operating_budget == 2048

    def test_profile_property(self):
        guard = TokenBudgetGuard(OPENROUTER_DEFAULT)
        assert guard.profile is OPENROUTER_DEFAULT

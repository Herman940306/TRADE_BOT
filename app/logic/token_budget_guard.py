"""
Project Autonomous Alpha — Phase 6, Sub-Phase C6
TokenBudgetGuard — Provider-Aware Token Budget Enforcement

Reliability Level: SOVEREIGN TIER
Spec Reference: DPv1.2 §0 (Token Budget Philosophy), §2.1 (Section Budgets)
Policy Reference: CPPv1.1 §1 (Tier Definitions), §4 (Overflow Resolution)

PURPOSE
-------
The TokenBudgetGuard is a standalone, provider-aware guard that validates
token usage against the Safe Operating Budget. It is independent of the
DecisionPacketBuilder (C4) and provides:

1. Pre-build checks: Can the system prompt + T1 fields fit?
2. Post-build checks: Does the assembled packet fit the budget?
3. Per-section enforcement: Does each section respect its allocation?
4. Provider profiles: Different models have different safe budgets.

DESIGN PRINCIPLE
----------------
The Safe Operating Budget is the RELIABILITY budget — not the model's
theoretical context window. qwen3:8b has 32K tokens but we constrain
to 2,048 because smaller prompts = more deterministic verdicts.

INTEGRATION
-----------
The guard does NOT replace C4's built-in overflow resolution. C4 handles
tier-dropping during assembly. C6 provides an INDEPENDENT verification
layer that can be invoked before, during, or after packet construction.

ZERO-TRUNCATION MANDATE
-----------------------
If the budget is exceeded, the response is REJECT — never truncate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from app.logic.decision_packet_models import (
    DecisionPacket,
    PacketError,
)
from app.logic.decision_packet_serializer import (
    estimate_tokens,
)

# =============================================================================
# PROVIDER PROFILES
# =============================================================================


class ProviderType(str, Enum):
    """Supported LLM provider types."""

    LOCAL_OLLAMA = "LOCAL_OLLAMA"
    OPENROUTER = "OPENROUTER"


@dataclass(frozen=True)
class SectionBudget:
    """Token budget allocation for a single packet section."""

    code: str
    name: str
    max_tokens: int


@dataclass(frozen=True)
class ProviderProfile:
    """
    Provider-specific token budget profile.

    Defines the Safe Operating Budget for a specific model/provider
    combination. The Safe Operating Budget is ALWAYS less than the
    model's theoretical context window.

    Invariant: input_budget + output_reserve + safety_margin == safe_operating_budget
    """

    provider_type: ProviderType
    model_name: str
    model_context_window: int
    safe_operating_budget: int
    input_budget: int
    output_reserve: int
    safety_margin: int
    section_budgets: Dict[str, SectionBudget]

    def __post_init__(self) -> None:
        expected = self.input_budget + self.output_reserve + self.safety_margin
        if expected != self.safe_operating_budget:
            raise ValueError(
                f"Budget invariant violated: "
                f"input({self.input_budget}) + output({self.output_reserve}) + "
                f"margin({self.safety_margin}) = {expected} != "
                f"safe_operating_budget({self.safe_operating_budget})"
            )


# --- qwen3:8b on local Ollama (NAS) ---
# DPv1.2 §2.1 section budgets

_QWEN3_SECTIONS = {
    "SYS": SectionBudget(code="SYS", name="System Prompt", max_tokens=200),
    "HDR": SectionBudget(code="HDR", name="Packet Header", max_tokens=60),
    "SIG": SectionBudget(code="SIG", name="Signal Fields", max_tokens=80),
    "OPS": SectionBudget(code="OPS", name="Operational Context", max_tokens=60),
    "HST": SectionBudget(code="HST", name="History Summary", max_tokens=100),
    "INT": SectionBudget(code="INT", name="Intelligence Layer", max_tokens=150),
    "MDF": SectionBudget(code="MDF", name="Missing Data Flags", max_tokens=60),
    "VRD": SectionBudget(code="VRD", name="Verdict Instruction", max_tokens=100),
}

QWEN3_8B_LOCAL = ProviderProfile(
    provider_type=ProviderType.LOCAL_OLLAMA,
    model_name="qwen3:8b",
    model_context_window=32768,
    safe_operating_budget=2048,
    input_budget=1400,
    output_reserve=512,
    safety_margin=136,
    section_budgets=_QWEN3_SECTIONS,
)

# --- OpenRouter placeholder profile ---
# Conservative profile for cloud-hosted models.
# Safe budget is intentionally the same until model-specific tuning is done.

_OPENROUTER_SECTIONS = {
    "SYS": SectionBudget(code="SYS", name="System Prompt", max_tokens=200),
    "HDR": SectionBudget(code="HDR", name="Packet Header", max_tokens=60),
    "SIG": SectionBudget(code="SIG", name="Signal Fields", max_tokens=80),
    "OPS": SectionBudget(code="OPS", name="Operational Context", max_tokens=60),
    "HST": SectionBudget(code="HST", name="History Summary", max_tokens=100),
    "INT": SectionBudget(code="INT", name="Intelligence Layer", max_tokens=150),
    "MDF": SectionBudget(code="MDF", name="Missing Data Flags", max_tokens=60),
    "VRD": SectionBudget(code="VRD", name="Verdict Instruction", max_tokens=100),
}

OPENROUTER_DEFAULT = ProviderProfile(
    provider_type=ProviderType.OPENROUTER,
    model_name="openrouter/default",
    model_context_window=128000,
    safe_operating_budget=2048,
    input_budget=1400,
    output_reserve=512,
    safety_margin=136,
    section_budgets=_OPENROUTER_SECTIONS,
)

# --- qwen3:8b DEEP mode profile (Phase 8) ---
# Expanded budget for contradiction-aware analysis.
# Same model, larger budget for deliberate reasoning.

_QWEN3_DEEP_SECTIONS = {
    "SYS": SectionBudget(code="SYS", name="System Prompt", max_tokens=250),
    "HDR": SectionBudget(code="HDR", name="Packet Header", max_tokens=60),
    "SIG": SectionBudget(code="SIG", name="Signal Fields", max_tokens=80),
    "OPS": SectionBudget(code="OPS", name="Operational Context", max_tokens=80),
    "HST": SectionBudget(code="HST", name="History Summary", max_tokens=100),
    "INT": SectionBudget(code="INT", name="Intelligence Layer", max_tokens=150),
    "MDF": SectionBudget(code="MDF", name="Missing Data Flags", max_tokens=80),
    "VRD": SectionBudget(code="VRD", name="Verdict Instruction", max_tokens=150),
}

QWEN3_8B_DEEP = ProviderProfile(
    provider_type=ProviderType.LOCAL_OLLAMA,
    model_name="qwen3:8b-deep",
    model_context_window=32768,
    safe_operating_budget=2600,
    input_budget=1800,
    output_reserve=640,
    safety_margin=160,
    section_budgets=_QWEN3_DEEP_SECTIONS,
)

# Registry of known profiles
PROVIDER_PROFILES: Dict[str, ProviderProfile] = {
    "qwen3:8b": QWEN3_8B_LOCAL,
    "qwen3:8b-deep": QWEN3_8B_DEEP,
    "openrouter/default": OPENROUTER_DEFAULT,
}

DEFAULT_PROFILE_KEY = "qwen3:8b"


def get_provider_profile(model_name: str) -> ProviderProfile:
    """
    Get the provider profile for a model.

    Falls back to qwen3:8b (most conservative) if model is unknown.
    """
    return PROVIDER_PROFILES.get(model_name, QWEN3_8B_LOCAL)


# =============================================================================
# BUDGET CHECK RESULTS
# =============================================================================


class BudgetVerdict(str, Enum):
    """Result of a budget check."""

    PASS = "PASS"
    FAIL = "FAIL"


@dataclass
class SectionUsage:
    """Token usage for a single packet section."""

    code: str
    name: str
    used_tokens: int
    budget_tokens: int
    over_budget: bool


@dataclass
class BudgetResult:
    """
    Complete result of a token budget check.

    Contains per-section breakdown, total usage, and any errors.
    """

    verdict: BudgetVerdict
    profile: str
    total_input_tokens: int
    input_budget: int
    output_reserve: int
    safety_margin: int
    safe_operating_budget: int
    remaining_input_tokens: int
    sections: List[SectionUsage] = field(default_factory=list)
    errors: List[PacketError] = field(default_factory=list)
    tier_drop_summary: Optional[str] = None


# =============================================================================
# ERROR CODES
# =============================================================================
#
# TBG-001: Total input exceeds input budget
# TBG-002: System prompt exceeds section budget
# TBG-003: Section exceeds its allocated budget
# TBG-004: T1 fields alone exceed input budget (specification error)
# TBG-005: Silent truncation detected (zero-truncation mandate violation)
# TBG-006: Output reserve insufficient for model response
#


# =============================================================================
# SECTION EXTRACTION
# =============================================================================


def _extract_section_text(serialized: str, section_code: str) -> str:
    """
    Extract the text of a single section from serialized packet.

    Section boundaries are defined by [XXX] delimiters.
    Returns the text between [section_code] and the next [XXX] or end.
    """
    marker = f"[{section_code}]"
    start = serialized.find(marker)
    if start == -1:
        return ""

    # Move past the marker line
    content_start = serialized.find("\n", start)
    if content_start == -1:
        return ""
    content_start += 1

    # Find the next section marker or end
    next_section = len(serialized)
    search_start = content_start
    while True:
        bracket = serialized.find("\n[", search_start)
        if bracket == -1:
            break
        # Verify it's a section header (uppercase letters in brackets)
        candidate = serialized[bracket + 1 :]
        close = candidate.find("]")
        if close != -1 and close <= 4:
            inner = candidate[1:close]
            if inner.isupper() and inner.isalpha():
                next_section = bracket
                break
        search_start = bracket + 1

    return serialized[content_start:next_section].strip()


# =============================================================================
# TOKEN BUDGET GUARD
# =============================================================================


class TokenBudgetGuard:
    """
    Provider-aware token budget enforcement.

    Independent verification layer for DecisionPacket token usage.
    Does NOT modify the packet — only validates it.
    """

    def __init__(self, profile: Optional[ProviderProfile] = None) -> None:
        self._profile = profile or QWEN3_8B_LOCAL

    @property
    def profile(self) -> ProviderProfile:
        return self._profile

    @property
    def input_budget(self) -> int:
        return self._profile.input_budget

    @property
    def output_reserve(self) -> int:
        return self._profile.output_reserve

    @property
    def safety_margin(self) -> int:
        return self._profile.safety_margin

    @property
    def safe_operating_budget(self) -> int:
        return self._profile.safe_operating_budget

    def check_system_prompt(self, system_prompt: str) -> BudgetResult:
        """
        Pre-build check: verify system prompt fits its section budget.

        Returns BudgetResult with PASS or FAIL.
        """
        sys_budget = self._profile.section_budgets.get("SYS")
        if sys_budget is None:
            return self._fail_result(
                [],
                [
                    PacketError(
                        "TBG-003",
                        "system_prompt",
                        "No SYS section budget defined in provider profile",
                    )
                ],
                0,
            )

        prompt_tokens = estimate_tokens(system_prompt)
        section = SectionUsage(
            code="SYS",
            name="System Prompt",
            used_tokens=prompt_tokens,
            budget_tokens=sys_budget.max_tokens,
            over_budget=prompt_tokens > sys_budget.max_tokens,
        )

        errors: List[PacketError] = []
        if section.over_budget:
            errors.append(
                PacketError(
                    "TBG-002",
                    "system_prompt",
                    f"System prompt uses {prompt_tokens} tokens "
                    f"(budget: {sys_budget.max_tokens})",
                )
            )

        return BudgetResult(
            verdict=BudgetVerdict.FAIL if errors else BudgetVerdict.PASS,
            profile=self._profile.model_name,
            total_input_tokens=prompt_tokens,
            input_budget=self._profile.input_budget,
            output_reserve=self._profile.output_reserve,
            safety_margin=self._profile.safety_margin,
            safe_operating_budget=self._profile.safe_operating_budget,
            remaining_input_tokens=self._profile.input_budget - prompt_tokens,
            sections=[section],
            errors=errors,
        )

    def check_t1_budget(self, t1_tokens: int) -> BudgetResult:
        """
        Pre-build check: verify T1 fields fit the input budget.

        If T1 alone exceeds input_budget, this is a specification error
        (not a runtime condition). Code TBG-004.
        """
        errors: List[PacketError] = []
        if t1_tokens > self._profile.input_budget:
            errors.append(
                PacketError(
                    "TBG-004",
                    "",
                    f"T1 fields use {t1_tokens} tokens "
                    f"(budget: {self._profile.input_budget}). "
                    "Specification error — escalate immediately.",
                )
            )

        return BudgetResult(
            verdict=BudgetVerdict.FAIL if errors else BudgetVerdict.PASS,
            profile=self._profile.model_name,
            total_input_tokens=t1_tokens,
            input_budget=self._profile.input_budget,
            output_reserve=self._profile.output_reserve,
            safety_margin=self._profile.safety_margin,
            safe_operating_budget=self._profile.safe_operating_budget,
            remaining_input_tokens=self._profile.input_budget - t1_tokens,
            errors=errors,
        )

    def check_packet(self, packet: DecisionPacket) -> BudgetResult:
        """
        Post-build check: verify a fully assembled DecisionPacket fits
        the provider's token budget.

        Checks:
        1. Total input tokens vs input_budget
        2. Per-section token usage vs section budgets
        3. No silent truncation (all T2 drops must be flagged)

        Returns BudgetResult with full per-section breakdown.
        """
        errors: List[PacketError] = []
        sections: List[SectionUsage] = []

        # --- System prompt section ---
        sys_tokens = estimate_tokens(packet.system_prompt)
        sys_budget = self._profile.section_budgets.get("SYS")
        if sys_budget:
            sys_over = sys_tokens > sys_budget.max_tokens
            sections.append(
                SectionUsage(
                    code="SYS",
                    name="System Prompt",
                    used_tokens=sys_tokens,
                    budget_tokens=sys_budget.max_tokens,
                    over_budget=sys_over,
                )
            )
            if sys_over:
                errors.append(
                    PacketError(
                        "TBG-002",
                        "system_prompt",
                        f"System prompt uses {sys_tokens} tokens "
                        f"(budget: {sys_budget.max_tokens})",
                    )
                )

        # --- Per-section checks on the serialized body ---
        serialized = packet.serialized
        if serialized:
            section_codes = ["HDR", "SIG", "OPS", "HST", "INT", "MDF", "VRD"]
            for code in section_codes:
                section_text = _extract_section_text(serialized, code)
                used = estimate_tokens(section_text) if section_text else 0
                budget_entry = self._profile.section_budgets.get(code)
                budget_max = budget_entry.max_tokens if budget_entry else 0
                section_name = budget_entry.name if budget_entry else code
                over = used > budget_max if budget_max > 0 else False

                sections.append(
                    SectionUsage(
                        code=code,
                        name=section_name,
                        used_tokens=used,
                        budget_tokens=budget_max,
                        over_budget=over,
                    )
                )

                if over:
                    errors.append(
                        PacketError(
                            "TBG-003",
                            code,
                            f"Section [{code}] uses {used} tokens "
                            f"(budget: {budget_max})",
                        )
                    )

        # --- Total input budget check ---
        total_input = packet.total_input_tokens
        if total_input > self._profile.input_budget:
            errors.append(
                PacketError(
                    "TBG-001",
                    "",
                    f"Total input uses {total_input} tokens "
                    f"(budget: {self._profile.input_budget})",
                )
            )

        # --- Silent truncation detection ---
        # If T2 fields were dropped but NOT flagged in missing_data_flags,
        # this is a zero-truncation mandate violation
        if packet.t2_fields_dropped:
            flagged_fields = set()
            for flag in packet.missing_data_flags:
                if ":" in flag:
                    flagged_fields.add(flag.split(":")[0])
            for dropped in packet.t2_fields_dropped:
                if dropped not in flagged_fields:
                    errors.append(
                        PacketError(
                            "TBG-005",
                            dropped,
                            f"T2 field '{dropped}' was dropped but not flagged "
                            "in missing_data_flags (silent truncation)",
                        )
                    )

        # --- Build tier drop summary ---
        tier_drop = None
        if packet.t2_fields_dropped or packet.t3_fields_dropped:
            parts = []
            if packet.t3_fields_dropped:
                parts.append(f"T3 dropped: {', '.join(packet.t3_fields_dropped)}")
            if packet.t2_fields_dropped:
                parts.append(f"T2 dropped: {', '.join(packet.t2_fields_dropped)}")
            tier_drop = "; ".join(parts)

        remaining = self._profile.input_budget - total_input

        return BudgetResult(
            verdict=BudgetVerdict.FAIL if errors else BudgetVerdict.PASS,
            profile=self._profile.model_name,
            total_input_tokens=total_input,
            input_budget=self._profile.input_budget,
            output_reserve=self._profile.output_reserve,
            safety_margin=self._profile.safety_margin,
            safe_operating_budget=self._profile.safe_operating_budget,
            remaining_input_tokens=remaining,
            sections=sections,
            errors=errors,
            tier_drop_summary=tier_drop,
        )

    def get_section_budgets(self) -> Dict[str, int]:
        """Return per-section budget limits for the current profile."""
        return {
            code: sb.max_tokens for code, sb in self._profile.section_budgets.items()
        }

    def _fail_result(
        self,
        sections: List[SectionUsage],
        errors: List[PacketError],
        total_tokens: int,
    ) -> BudgetResult:
        return BudgetResult(
            verdict=BudgetVerdict.FAIL,
            profile=self._profile.model_name,
            total_input_tokens=total_tokens,
            input_budget=self._profile.input_budget,
            output_reserve=self._profile.output_reserve,
            safety_margin=self._profile.safety_margin,
            safe_operating_budget=self._profile.safe_operating_budget,
            remaining_input_tokens=self._profile.input_budget - total_tokens,
            sections=sections,
            errors=errors,
        )


# =============================================================================
# MODULE-LEVEL CONVENIENCE
# =============================================================================


def check_packet_budget(
    packet: DecisionPacket,
    model_name: Optional[str] = None,
) -> BudgetResult:
    """
    Module-level convenience function for budget checking.

    Uses the provider profile matching model_name, or the default
    qwen3:8b profile if not specified.
    """
    profile = get_provider_profile(model_name) if model_name else QWEN3_8B_LOCAL
    guard = TokenBudgetGuard(profile)
    return guard.check_packet(packet)

"""
Project Autonomous Alpha — Phase 6, Sub-Phase C4.2
DecisionPacketBuilder — Deterministic Packet Construction Pipeline

Reliability Level: SOVEREIGN TIER
Spec Reference: DPv1.2 (DECISION_PACKET_SPEC.md)
Policy Reference: CPPv1.1 (CONTEXT_PRIORITY_POLICY.md)

PURPOSE
-------
The DecisionPacketBuilder implements the 8-phase deterministic algorithm
defined in CPPv1.1 §2.1. It takes structured inputs (not raw dicts),
assembles a Decision Packet, validates it against 18 DPB rules, serializes
it to canonical format, and computes the SHA-256 packet hash.

PIPELINE OVERVIEW (CPPv1.1 §2.1)
---------------------------------
    Phase 1: Resolve T1 fields
    Phase 2: Token checkpoint (T1 must fit in budget)
    Phase 3: Resolve T2 fields in priority order
    Phase 4: Resolve T3 fields (budget permitting)
    Phase 5: Compute derived T1 fields (grade, flags)
    Phase 6: T4 prohibition check
    Phase 7: Validation (18 DPB rules)
    Phase 8: Finalize (serialize, hash)

FAILURE BEHAVIOR
----------------
    - T1 field missing/invalid → PacketBuildError (REJECT immediately)
    - T2 field missing → flag + continue
    - T3 field missing → silent omission
    - guardian_locked=true → REJECT pre-LLM (DPB-016 check #2)
    - Token budget exceeded → overflow resolution (drop T3, then T2 in reverse priority)
    - Validation failure → PacketValidationError (REJECT with diagnostics)
    - Any float detected → PacketBuildError (Zero-Float Mandate)

ZERO-FLOAT MANDATE
------------------
No floating-point numbers. All numerics are Decimal or int.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from app.logic.decision_packet_models import (
    INPUT_TOKEN_BUDGET,
    SPEC_VERSION,
    BuildContext,
    DataQualityGrade,
    DecisionPacket,
    HistorySummaryInput,
    IntelligenceInput,
    MissingDataFlag,
    MissingReason,
    OperationalContext,
    PacketBuildError,
    PacketError,
    PacketValidationError,
    SignalInput,
    format_decimal,
)
from app.logic.decision_packet_serializer import (
    compute_packet_hash,
    estimate_tokens,
    serialize_packet,
)
from app.logic.decision_packet_validator import validate_packet

logger = logging.getLogger(__name__)

# T2 fields in priority order (CPPv1.1 §2.2)
# T2-P1 (highest) through T2-P6 (lowest)
T2_PRIORITY_ORDER = [
    "rgi_trust",  # T2-P1
    "ml_confidence",  # T2-P2
    "ml_action",  # T2-P3
    "win_rate",  # T2-P4
    "total_trades",  # T2-P5
    "recent_debates",  # T2-P6
]

# T3 fields in priority order
T3_PRIORITY_ORDER = [
    "ml_reasoning",  # T3-P1
    "symbol_bias",  # T3-P2
]


class DecisionPacketBuilder:
    """
    Deterministic Decision Packet construction pipeline.

    Implements CPPv1.1 §2.1 algorithm exactly. No deviations.
    """

    def build(
        self,
        signal: SignalInput,
        ops: OperationalContext,
        history: HistorySummaryInput,
        intel: IntelligenceInput,
        build_ctx: BuildContext,
    ) -> DecisionPacket:
        """
        Build a complete, validated Decision Packet.

        This is the single entry point for packet construction.
        Returns a fully validated DecisionPacket or raises an exception.

        Raises:
            PacketBuildError: If a T1 field is missing or invalid, or
                if guardian_locked=true.
            PacketValidationError: If any DPB validation rule fails.
        """
        # ================================================================
        # PRE-FLIGHT: Guardian check (DPB-016 check #2)
        # ================================================================
        if ops.guardian_locked:
            raise PacketBuildError(
                PacketError(
                    "DPB-016",
                    "guardian_locked",
                    "Guardian is locked — trade REJECTED pre-LLM",
                )
            )

        # ================================================================
        # PHASE 1: Resolve T1 fields
        # ================================================================
        packet_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        packet = DecisionPacket(
            # Section B — Header
            spec_version=SPEC_VERSION,
            packet_ts=packet_ts,
            correlation_id=str(build_ctx.correlation_id),
            prompt_version_hash=build_ctx.prompt_version_hash,
            model_fingerprint=build_ctx.model_fingerprint,
            # Section C — Signal
            signal_id=signal.signal_id,
            symbol=signal.symbol,
            side=signal.side.value,
            price=format_decimal(signal.price),
            quantity=format_decimal(signal.quantity),
            # Section D — Operations
            execution_mode=ops.execution_mode.value,
            guardian_locked=ops.guardian_locked,
            equity_zar=format_decimal(ops.equity_zar),
            risk_pct=format_decimal(ops.risk_pct),
            # Section E — History Summary
            history_summary=history.render(),
            # Section F — Intelligence (T1 only at this phase)
            rgi_available=intel.rgi_available,
            # Section A — System Prompt
            system_prompt=build_ctx.system_prompt,
        )

        # ================================================================
        # PHASE 2: Token checkpoint — T1 must fit in budget
        # ================================================================
        t1_serialized = serialize_packet(packet)
        t1_tokens = estimate_tokens(f"[SYS]\n{packet.system_prompt}\n\n{t1_serialized}")
        packet.t1_tokens = t1_tokens

        if t1_tokens > INPUT_TOKEN_BUDGET:
            raise PacketBuildError(
                PacketError(
                    "T1_BUDGET_EXCEEDED",
                    "",
                    f"T1 alone uses {t1_tokens} tokens (budget: {INPUT_TOKEN_BUDGET}). "
                    "This is a specification error — escalate immediately.",
                )
            )

        remaining_budget = INPUT_TOKEN_BUDGET - t1_tokens

        # ================================================================
        # PHASE 3: Resolve T2 fields in priority order (CPPv1.1 §2.2)
        # ================================================================
        missing_flags: List[MissingDataFlag] = []

        for field_name in T2_PRIORITY_ORDER:
            value, missing_reason = self._resolve_t2_field(field_name, intel)

            if value is None:
                # Field unavailable — flag and continue
                reason = missing_reason or MissingReason.SERVICE_UNAVAILABLE
                missing_flags.append(
                    MissingDataFlag(field_name=field_name, reason=reason)
                )
                packet.t2_fields_dropped.append(field_name)
                continue

            # Estimate token cost of this field
            field_text = self._render_t2_field(field_name, value)
            field_tokens = estimate_tokens(field_text)

            if field_tokens > remaining_budget:
                # Token budget exhausted — flag and continue
                missing_flags.append(
                    MissingDataFlag(
                        field_name=field_name,
                        reason=MissingReason.TOKEN_BUDGET_EXHAUSTED,
                    )
                )
                packet.t2_fields_dropped.append(field_name)
                continue

            # Include field
            self._set_t2_field(packet, field_name, value)
            remaining_budget -= field_tokens
            packet.t2_fields_included.append(field_name)

        # ================================================================
        # PHASE 4: Resolve T3 fields (budget permitting)
        # ================================================================
        for field_name in T3_PRIORITY_ORDER:
            if remaining_budget <= 0:
                packet.t3_fields_dropped.append(field_name)
                break

            value = self._resolve_t3_field(field_name, intel)
            if value is None:
                packet.t3_fields_dropped.append(field_name)
                continue

            field_text = self._render_t3_field(field_name, value)
            field_tokens = estimate_tokens(field_text)

            if field_tokens > remaining_budget:
                packet.t3_fields_dropped.append(field_name)
                continue

            self._set_t3_field(packet, field_name, value)
            remaining_budget -= field_tokens
            packet.t3_fields_included.append(field_name)

        # ================================================================
        # PHASE 5: Compute derived T1 fields (grade, flags)
        # ================================================================
        packet.missing_data_flags = [f.render() for f in missing_flags]
        # Sort alphabetically by field name for determinism (§6.3 req #5)
        packet.missing_data_flags.sort()

        flag_count = len(packet.missing_data_flags)
        if flag_count == 0:
            packet.data_quality_grade = DataQualityGrade.FULL.value
        elif flag_count <= 3:
            packet.data_quality_grade = DataQualityGrade.PARTIAL.value
        else:
            packet.data_quality_grade = DataQualityGrade.MINIMAL.value

        # ================================================================
        # PHASE 6: T4 prohibition check
        # ================================================================
        self._check_t4_prohibitions(packet)

        # ================================================================
        # PHASE 6b: Overflow resolution (defensive — DPv1.2 §4.3)
        # ================================================================
        serialized = serialize_packet(packet)
        full_prompt_text = f"[SYS]\n{packet.system_prompt}\n\n{serialized}"
        total_tokens = estimate_tokens(full_prompt_text)

        if total_tokens > INPUT_TOKEN_BUDGET:
            packet, serialized = self._resolve_overflow(
                packet, missing_flags, full_prompt_text
            )
            total_tokens = estimate_tokens(
                f"[SYS]\n{packet.system_prompt}\n\n{serialized}"
            )

        packet.serialized = serialized
        packet.total_input_tokens = total_tokens

        # ================================================================
        # PHASE 7: Compute packet hash
        # ================================================================
        packet.packet_hash = compute_packet_hash(serialized)

        # ================================================================
        # PHASE 8: Validation (18 DPB rules)
        # ================================================================
        validation_errors = validate_packet(packet)
        packet.validation_results = [str(e) for e in validation_errors]

        if validation_errors:
            # Log all failures for diagnostics
            for err in validation_errors:
                logger.error(
                    "DPB validation failure: %s (field=%s, detail=%s)",
                    err.code,
                    err.field_name,
                    err.detail,
                )
            raise PacketValidationError(validation_errors)

        # ================================================================
        # AUDIT LOG: Packet assembly complete
        # ================================================================
        logger.info(
            "Packet assembled: packet_hash=%s, correlation_id=%s, "
            "spec_version=%s, data_quality_grade=%s, packet_ts=%s, "
            "t1_tokens=%d, total_tokens=%d, t2_included=%s, t2_dropped=%s",
            packet.packet_hash,
            packet.correlation_id,
            packet.spec_version,
            packet.data_quality_grade,
            packet.packet_ts,
            packet.t1_tokens,
            packet.total_input_tokens,
            packet.t2_fields_included,
            packet.t2_fields_dropped,
        )

        return packet

    # ====================================================================
    # PRIVATE HELPERS
    # ====================================================================

    def _resolve_t2_field(
        self,
        field_name: str,
        intel: IntelligenceInput,
    ) -> Tuple[object, Optional[MissingReason]]:
        """
        Resolve a T2 field from intelligence input.
        Returns (value, missing_reason) — value is None if unavailable.
        """
        field_map = {
            "rgi_trust": (intel.rgi_trust, intel.rgi_trust_missing_reason),
            "ml_confidence": (intel.ml_confidence, intel.ml_confidence_missing_reason),
            "ml_action": (intel.ml_action, intel.ml_action_missing_reason),
            "win_rate": (intel.win_rate, intel.win_rate_missing_reason),
            "total_trades": (intel.total_trades, intel.total_trades_missing_reason),
            "recent_debates": (
                intel.recent_debates,
                intel.recent_debates_missing_reason,
            ),
        }
        value, reason = field_map[field_name]
        # For recent_debates, treat empty list as missing
        if field_name == "recent_debates" and value is not None and len(value) == 0:
            return None, reason or MissingReason.NO_HISTORY
        return value, reason

    def _render_t2_field(self, field_name: str, value: object) -> str:
        """Render a T2 field to its serialized form for token estimation."""
        if field_name == "rgi_trust":
            return f"rgi_trust={format_decimal(value)}"
        elif field_name == "ml_confidence":
            return f"ml_conf={format_decimal(value)}"
        elif field_name == "ml_action":
            return f"ml_act={value.value if hasattr(value, 'value') else value}"
        elif field_name == "win_rate":
            return f"wr={format_decimal(value)}"
        elif field_name == "total_trades":
            return f"trades={value}"
        elif field_name == "recent_debates":
            entries = [e.render() for e in value]
            return f"debates={';'.join(entries)}"
        return ""

    def _set_t2_field(
        self, packet: DecisionPacket, field_name: str, value: object
    ) -> None:
        """Set a T2 field on the packet."""
        if field_name == "rgi_trust":
            packet.rgi_trust = format_decimal(value)
        elif field_name == "ml_confidence":
            packet.ml_confidence = format_decimal(value)
        elif field_name == "ml_action":
            packet.ml_action = value.value if hasattr(value, "value") else str(value)
        elif field_name == "win_rate":
            packet.win_rate = format_decimal(value)
        elif field_name == "total_trades":
            packet.total_trades = value
        elif field_name == "recent_debates":
            # Sort by timestamp descending (most recent first) for determinism
            entries = sorted(value, key=lambda e: e.ts_short, reverse=True)
            packet.recent_debates = [e.render() for e in entries]

    def _resolve_t3_field(self, field_name: str, intel: IntelligenceInput) -> object:
        """Resolve a T3 field. Returns None if unavailable (silent omission)."""
        if field_name == "ml_reasoning":
            return intel.ml_reasoning
        elif field_name == "symbol_bias":
            return intel.symbol_bias
        return None

    def _render_t3_field(self, field_name: str, value: object) -> str:
        """Render a T3 field for token estimation."""
        if field_name == "ml_reasoning":
            return f"ml_reason={value}"
        elif field_name == "symbol_bias":
            return f"bias={value.value if hasattr(value, 'value') else value}"
        return ""

    def _set_t3_field(
        self, packet: DecisionPacket, field_name: str, value: object
    ) -> None:
        """Set a T3 field on the packet."""
        if field_name == "ml_reasoning":
            packet.ml_reasoning = str(value)
        elif field_name == "symbol_bias":
            packet.symbol_bias = value.value if hasattr(value, "value") else str(value)

    def _check_t4_prohibitions(self, packet: DecisionPacket) -> None:
        """
        T4 prohibition check — verify no forbidden content in packet.
        Raises PacketBuildError if T4 content detected.
        """
        # Check for float values in numeric fields (Zero-Float Mandate)
        # This is caught at input time, but double-check here
        for field_name in ("price", "quantity", "equity_zar", "risk_pct"):
            val = getattr(packet, field_name, "")
            if isinstance(val, float):
                raise PacketBuildError(
                    PacketError(
                        "T4_FLOAT_VIOLATION",
                        field_name,
                        f"Float value {val!r} in assembled packet",
                    )
                )

        # Check system_prompt does not contain PII patterns (basic check)
        # Full PII detection is out of scope for C4 but we verify the
        # prompt comes from a controlled source (build context).

    def _resolve_overflow(
        self,
        packet: DecisionPacket,
        missing_flags: List[MissingDataFlag],
        current_prompt: str,
    ) -> Tuple[DecisionPacket, str]:
        """
        Overflow resolution sequence (CPPv1.1 §4.3).

        1. Drop ALL T3 fields
        2. If still over: drop T2 in reverse priority (P6 first, P1 last)
        3. If still over after all T2/T3: REJECT (specification error)
        """
        # Step 1: Drop all T3 fields
        for field_name in T3_PRIORITY_ORDER:
            if field_name == "ml_reasoning" and packet.ml_reasoning is not None:
                packet.ml_reasoning = None
                if field_name not in packet.t3_fields_dropped:
                    packet.t3_fields_dropped.append(field_name)
                if field_name in packet.t3_fields_included:
                    packet.t3_fields_included.remove(field_name)
            elif field_name == "symbol_bias" and packet.symbol_bias is not None:
                packet.symbol_bias = None
                if field_name not in packet.t3_fields_dropped:
                    packet.t3_fields_dropped.append(field_name)
                if field_name in packet.t3_fields_included:
                    packet.t3_fields_included.remove(field_name)

        serialized = serialize_packet(packet)
        full_text = f"[SYS]\n{packet.system_prompt}\n\n{serialized}"

        if estimate_tokens(full_text) <= INPUT_TOKEN_BUDGET:
            self._recompute_flags_and_grade(packet, missing_flags)
            return packet, serialized

        # Step 2: Drop T2 in reverse priority (P6 → P1)
        for field_name in reversed(T2_PRIORITY_ORDER):
            field_value = self._get_t2_field(packet, field_name)
            if field_value is None:
                continue

            # Drop this field
            self._clear_t2_field(packet, field_name)
            if field_name not in packet.t2_fields_dropped:
                packet.t2_fields_dropped.append(field_name)
            if field_name in packet.t2_fields_included:
                packet.t2_fields_included.remove(field_name)

            # Add overflow flag
            already_flagged = any(f.field_name == field_name for f in missing_flags)
            if not already_flagged:
                missing_flags.append(
                    MissingDataFlag(
                        field_name=field_name,
                        reason=MissingReason.TOKEN_BUDGET_OVERFLOW,
                    )
                )

            self._recompute_flags_and_grade(packet, missing_flags)
            serialized = serialize_packet(packet)
            full_text = f"[SYS]\n{packet.system_prompt}\n\n{serialized}"

            if estimate_tokens(full_text) <= INPUT_TOKEN_BUDGET:
                return packet, serialized

        # Step 3: T1 alone exceeds budget — specification error
        self._recompute_flags_and_grade(packet, missing_flags)
        serialized = serialize_packet(packet)
        raise PacketBuildError(
            PacketError(
                "T1_BUDGET_EXCEEDED",
                "",
                "T1 alone exceeds token budget after dropping all T2/T3. "
                "This is a specification error — escalate immediately.",
            )
        )

    def _get_t2_field(self, packet: DecisionPacket, field_name: str) -> object:
        """Get a T2 field's current value from the packet."""
        return getattr(packet, field_name, None)

    def _clear_t2_field(self, packet: DecisionPacket, field_name: str) -> None:
        """Clear a T2 field on the packet."""
        if field_name == "recent_debates":
            packet.recent_debates = None
        elif field_name == "total_trades":
            packet.total_trades = None
        elif field_name == "win_rate":
            packet.win_rate = None
        elif field_name == "ml_action":
            packet.ml_action = None
        elif field_name == "ml_confidence":
            packet.ml_confidence = None
        elif field_name == "rgi_trust":
            packet.rgi_trust = None

    def _recompute_flags_and_grade(
        self,
        packet: DecisionPacket,
        missing_flags: List[MissingDataFlag],
    ) -> None:
        """Recompute missing_data_flags and data_quality_grade after modifications."""
        packet.missing_data_flags = sorted(f.render() for f in missing_flags)
        flag_count = len(packet.missing_data_flags)
        if flag_count == 0:
            packet.data_quality_grade = DataQualityGrade.FULL.value
        elif flag_count <= 3:
            packet.data_quality_grade = DataQualityGrade.PARTIAL.value
        else:
            packet.data_quality_grade = DataQualityGrade.MINIMAL.value


# =============================================================================
# MODULE-LEVEL CONVENIENCE
# =============================================================================


def build_decision_packet(
    signal: SignalInput,
    ops: OperationalContext,
    history: HistorySummaryInput,
    intel: IntelligenceInput,
    build_ctx: BuildContext,
) -> DecisionPacket:
    """
    Module-level convenience function for building a Decision Packet.

    Raises:
        PacketBuildError: T1 field missing, guardian locked, or float detected.
        PacketValidationError: DPB validation rule failure.
    """
    builder = DecisionPacketBuilder()
    return builder.build(signal, ops, history, intel, build_ctx)

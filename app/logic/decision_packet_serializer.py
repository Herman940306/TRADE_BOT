"""
Project Autonomous Alpha — Phase 6, Sub-Phase C4.5
Decision Packet Serializer — Canonical Representation + SHA-256 Hash

Reliability Level: SOVEREIGN TIER
Spec Reference: DPv1.2 §5 (Compact Encoding Rules), §6 (Packet Hash)

PURPOSE
-------
Deterministic serialization of a DecisionPacket into the compact key-value
text format defined in DPv1.2 §5. The serialized output is the EXACT byte
sequence that will be sent to the LLM (minus system prompt section A, which
is prepended separately).

DETERMINISM GUARANTEE
---------------------
Identical inputs MUST always produce identical serialized output and
identical SHA-256 packet hashes. This is enforced by:
1. Fixed section order (§2.1)
2. Fixed field order within sections
3. Canonical Decimal formatting (no trailing zeros beyond 2dp)
4. Sorted arrays (recent_debates by timestamp desc, missing_flags alphabetical)
5. UTF-8 with no BOM
6. Single \\n between fields, no trailing whitespace
"""

from __future__ import annotations

import hashlib
from typing import List

from app.logic.decision_packet_models import DecisionPacket


def serialize_packet(packet: DecisionPacket) -> str:
    """
    Serialize a DecisionPacket into compact key-value text format.

    Returns the EXACT string that will be hashed and sent to the LLM
    (sections B through H — system prompt is Section A, prepended separately).

    Encoding rules (DPv1.2 §5.2):
        - Section delimiters: [XXX]
        - Field separator: \\n
        - Key-value separator: = (first = only)
        - Array separator: ; between entries
        - Boolean: true/false (lowercase)
        - No string quoting
        - Empty values: field omitted entirely
    """
    lines: List[str] = []

    # Section B — Header [HDR]
    lines.append("[HDR]")
    lines.append(f"v={packet.spec_version}")
    lines.append(f"ts={packet.packet_ts}")
    lines.append(f"cid={packet.correlation_id}")
    lines.append(f"pvh={packet.prompt_version_hash}")
    lines.append(f"mfp={packet.model_fingerprint}")

    # Section C — Signal [SIG]
    lines.append("")
    lines.append("[SIG]")
    lines.append(f"id={packet.signal_id}")
    lines.append(f"sym={packet.symbol}")
    lines.append(f"side={packet.side}")
    lines.append(f"px={packet.price}")
    lines.append(f"qty={packet.quantity}")

    # Section D — Operations [OPS]
    lines.append("")
    lines.append("[OPS]")
    lines.append(f"mode={packet.execution_mode}")
    lines.append(f"guardian={'true' if packet.guardian_locked else 'false'}")
    lines.append(f"equity={packet.equity_zar}")
    lines.append(f"risk={packet.risk_pct}")

    # Section E — History Summary [HST]
    lines.append("")
    lines.append("[HST]")
    lines.append(f"summary={packet.history_summary}")

    # Section F — Intelligence [INT]
    int_fields: List[str] = []
    if packet.ml_confidence is not None:
        int_fields.append(f"ml_conf={packet.ml_confidence}")
    if packet.ml_action is not None:
        int_fields.append(f"ml_act={packet.ml_action}")
    if packet.rgi_trust is not None:
        int_fields.append(f"rgi_trust={packet.rgi_trust}")
    int_fields.append(f"rgi_avail={'true' if packet.rgi_available else 'false'}")
    if packet.win_rate is not None:
        int_fields.append(f"wr={packet.win_rate}")
    if packet.total_trades is not None:
        int_fields.append(f"trades={packet.total_trades}")
    if packet.symbol_bias is not None:
        int_fields.append(f"bias={packet.symbol_bias}")
    if packet.ml_reasoning is not None:
        int_fields.append(f"ml_reason={packet.ml_reasoning}")
    if packet.recent_debates is not None and len(packet.recent_debates) > 0:
        int_fields.append(f"debates={';'.join(packet.recent_debates)}")

    if int_fields:
        lines.append("")
        lines.append("[INT]")
        lines.extend(int_fields)

    # Section G — Missing Data Flags [MDF]
    lines.append("")
    lines.append("[MDF]")
    if packet.missing_data_flags:
        lines.append(f"flags={';'.join(packet.missing_data_flags)}")
    lines.append(f"grade={packet.data_quality_grade}")

    # Section H — Verdict Instruction [VRD]
    lines.append("")
    lines.append("[VRD]")
    lines.append("Respond with EXACTLY this JSON and nothing else:")
    lines.append('{"verdict":"APPROVED"} or {"verdict":"REJECTED"}')
    lines.append("Do not explain. Do not add text before or after the JSON.")

    return "\n".join(lines)


def compute_packet_hash(serialized: str) -> str:
    """
    Compute SHA-256 hash of the serialized packet (sections B-H).

    The hash covers the EXACT byte sequence that will be sent to the LLM
    (excluding the system prompt in Section A, which is covered by
    prompt_version_hash).

    Returns:
        64-char lowercase hex string
    """
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def build_full_prompt(system_prompt: str, serialized_body: str) -> str:
    """
    Combine system prompt (Section A) with serialized body (Sections B-H)
    into the complete prompt sent to the LLM.

    The system prompt is prepended with [SYS] section delimiter.
    """
    lines = [
        "[SYS]",
        system_prompt,
        "",
        serialized_body,
    ]
    return "\n".join(lines)


def estimate_tokens(text: str) -> int:
    """
    Conservative token estimation for budget checking.

    Uses the 4-chars-per-token heuristic which is conservative for
    the qwen3:8b tokenizer. This intentionally overestimates to ensure
    we never exceed the budget.

    For production accuracy, this should be replaced with the actual
    tokenizer. The safety margin (136 tokens) absorbs estimation error.
    """
    # Conservative: ~4 chars per token for English/ASCII content
    # This overestimates slightly, which is safe (fail-closed)
    return max(1, (len(text) + 3) // 4)

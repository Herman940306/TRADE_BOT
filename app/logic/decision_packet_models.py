"""
Project Autonomous Alpha — Phase 6, Sub-Phase C4.1
Decision Packet Input Contracts

Reliability Level: SOVEREIGN TIER
Spec Reference: DPv1.2 (DECISION_PACKET_SPEC.md)
Policy Reference: CPPv1.1 (CONTEXT_PRIORITY_POLICY.md)

PURPOSE
-------
Strict input contracts for the DecisionPacketBuilder. Every data source
entering the builder is typed, bounded, and validated at the boundary.
No arbitrary dicts. No uncontrolled text. No floating-point numbers.

ZERO-FLOAT MANDATE
------------------
All monetary and statistical values use Decimal. Any float detected
at the input boundary is a build error.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import List, Optional
from uuid import UUID

# =============================================================================
# ENUMS
# =============================================================================


class Side(str, Enum):
    """Trade direction. Constrained to BUY or SELL only."""

    BUY = "BUY"
    SELL = "SELL"


class ExecutionMode(str, Enum):
    """Execution mode. PAPER or LIVE only."""

    PAPER = "PAPER"
    LIVE = "LIVE"


class DataQualityGrade(str, Enum):
    """Data completeness grade for the LLM."""

    FULL = "FULL"
    PARTIAL = "PARTIAL"
    MINIMAL = "MINIMAL"


class MissingReason(str, Enum):
    """Valid reason codes for missing data flags."""

    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    NO_HISTORY = "NO_HISTORY"
    SYMBOL_NEW = "SYMBOL_NEW"
    TIMEOUT = "TIMEOUT"
    CALCULATION_ERROR = "CALCULATION_ERROR"
    TOKEN_BUDGET_EXHAUSTED = "TOKEN_BUDGET_EXHAUSTED"
    TOKEN_BUDGET_OVERFLOW = "TOKEN_BUDGET_OVERFLOW"


class MLAction(str, Enum):
    """ML model recommended action."""

    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class SymbolBias(str, Enum):
    """Symbol directional bias from analysis."""

    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"


# =============================================================================
# VALIDATION CONSTANTS
# =============================================================================

SYMBOL_PATTERN = re.compile(r"^[A-Z0-9]{2,20}$")
UUID4_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
SHA256_HEX_PATTERN = re.compile(r"^[0-9a-f]{64}$", re.IGNORECASE)

SPEC_VERSION = "DPv1"
INPUT_TOKEN_BUDGET = 1400
OUTPUT_TOKEN_RESERVE = 512
SAFETY_MARGIN = 136
SAFE_OPERATING_BUDGET = 2048

MAX_SIGNAL_ID_LEN = 64
MAX_SYMBOL_LEN = 20
MAX_PRICE_LEN = 32
MAX_QUANTITY_LEN = 32
MAX_EQUITY_LEN = 32
MAX_RISK_PCT_LEN = 8
MAX_CORRELATION_ID_LEN = 36
MAX_PROMPT_HASH_LEN = 64
MAX_MODEL_FINGERPRINT_LEN = 128
MAX_PACKET_HASH_LEN = 64
MAX_HISTORY_SUMMARY_LEN = 120
MAX_ML_REASONING_LEN = 200
MAX_RECENT_DEBATE_ENTRIES = 3
MAX_RECENT_DEBATE_ENTRY_LEN = 80
MAX_MISSING_FLAGS_ENTRIES = 10
MAX_MISSING_FLAG_ENTRY_LEN = 40
MAX_SYSTEM_PROMPT_CHARS = 800
MAX_TOTAL_TRADES = 999999


# =============================================================================
# ERROR TYPES
# =============================================================================


class PacketError:
    """Structured error from packet construction or validation."""

    __slots__ = ("code", "field_name", "detail")

    def __init__(self, code: str, field_name: str = "", detail: str = "") -> None:
        self.code = code
        self.field_name = field_name
        self.detail = detail

    def __repr__(self) -> str:
        parts = [f"code={self.code!r}"]
        if self.field_name:
            parts.append(f"field={self.field_name!r}")
        if self.detail:
            parts.append(f"detail={self.detail!r}")
        return f"PacketError({', '.join(parts)})"

    def __str__(self) -> str:
        return repr(self)


class PacketBuildError(Exception):
    """Fatal build error — packet cannot be constructed."""

    def __init__(self, error: PacketError) -> None:
        self.error = error
        super().__init__(str(error))


class PacketValidationError(Exception):
    """Validation rule failure — packet rejected."""

    def __init__(self, errors: List[PacketError]) -> None:
        self.errors = errors
        super().__init__(
            f"{len(errors)} validation failure(s): " + "; ".join(str(e) for e in errors)
        )


# =============================================================================
# INPUT CONTRACTS
# =============================================================================


@dataclass(frozen=True)
class SignalInput:
    """
    Domain A — Signal fields from TradingView webhook.
    All T1 REQUIRED. Provenance: Source-of-Truth.

    Input Constraints:
        - signal_id: non-empty, max 64 chars
        - symbol: matches ^[A-Z0-9]{2,20}$
        - side: BUY or SELL
        - price: Decimal > 0
        - quantity: Decimal > 0
    """

    signal_id: str
    symbol: str
    side: Side
    price: Decimal
    quantity: Decimal

    def __post_init__(self) -> None:
        _reject_float(self.price, "price")
        _reject_float(self.quantity, "quantity")
        if not self.signal_id or len(self.signal_id) > MAX_SIGNAL_ID_LEN:
            raise PacketBuildError(
                PacketError(
                    "T1_MISSING",
                    "signal_id",
                    f"Must be non-empty, max {MAX_SIGNAL_ID_LEN} chars",
                )
            )
        if not SYMBOL_PATTERN.match(self.symbol):
            raise PacketBuildError(
                PacketError(
                    "DPB-004",
                    "symbol",
                    f"Must match ^[A-Z0-9]{{2,20}}$, got {self.symbol!r}",
                )
            )
        if self.price <= 0:
            raise PacketBuildError(
                PacketError("DPB-006", "price", f"Must be > 0, got {self.price}")
            )
        if self.quantity <= 0:
            raise PacketBuildError(
                PacketError("DPB-007", "quantity", f"Must be > 0, got {self.quantity}")
            )


@dataclass(frozen=True)
class OperationalContext:
    """
    Domain B — System configuration and guardian state.
    All T1 REQUIRED. Provenance: Source-of-Truth.

    Input Constraints:
        - execution_mode: PAPER or LIVE
        - guardian_locked: boolean (if true, packet rejected pre-LLM)
        - equity_zar: Decimal >= 0
        - risk_pct: Decimal > 0
    """

    execution_mode: ExecutionMode
    guardian_locked: bool
    equity_zar: Decimal
    risk_pct: Decimal

    def __post_init__(self) -> None:
        _reject_float(self.equity_zar, "equity_zar")
        _reject_float(self.risk_pct, "risk_pct")
        if self.equity_zar < 0:
            raise PacketBuildError(
                PacketError(
                    "T1_MISSING", "equity_zar", f"Must be >= 0, got {self.equity_zar}"
                )
            )
        if self.risk_pct <= 0:
            raise PacketBuildError(
                PacketError(
                    "T1_MISSING", "risk_pct", f"Must be > 0, got {self.risk_pct}"
                )
            )
        if len(str(self.equity_zar)) > MAX_EQUITY_LEN:
            raise PacketBuildError(
                PacketError(
                    "T1_MISSING",
                    "equity_zar",
                    f"String representation exceeds {MAX_EQUITY_LEN} chars",
                )
            )
        if len(str(self.risk_pct)) > MAX_RISK_PCT_LEN:
            raise PacketBuildError(
                PacketError(
                    "T1_MISSING",
                    "risk_pct",
                    f"String representation exceeds {MAX_RISK_PCT_LEN} chars",
                )
            )


@dataclass(frozen=True)
class HistorySummaryInput:
    """
    Domain C — Database-derived debate history.
    history_summary is T1 REQUIRED. Provenance: Derived Summary.

    The summary string must match the fixed template:
    "{count} debates ({window}h): {approved} APR, {rejected} REJ, avg_score={avg_score}"

    Input Constraints:
        - count: 0-99
        - window: always 24
        - approved: 0-99
        - rejected: 0-99
        - approved + rejected == count
        - avg_score: 0-100
        - total length <= 120 chars
    """

    count: int
    approved: int
    rejected: int
    avg_score: int
    window: int = 24

    def __post_init__(self) -> None:
        if not (0 <= self.count <= 99):
            raise PacketBuildError(
                PacketError(
                    "T1_MISSING",
                    "history_summary",
                    f"count must be 0-99, got {self.count}",
                )
            )
        if not (0 <= self.approved <= 99):
            raise PacketBuildError(
                PacketError(
                    "T1_MISSING",
                    "history_summary",
                    f"approved must be 0-99, got {self.approved}",
                )
            )
        if not (0 <= self.rejected <= 99):
            raise PacketBuildError(
                PacketError(
                    "T1_MISSING",
                    "history_summary",
                    f"rejected must be 0-99, got {self.rejected}",
                )
            )
        if self.approved + self.rejected != self.count:
            raise PacketBuildError(
                PacketError(
                    "T1_MISSING",
                    "history_summary",
                    f"approved({self.approved}) + rejected({self.rejected}) "
                    f"!= count({self.count})",
                )
            )
        if not (0 <= self.avg_score <= 100):
            raise PacketBuildError(
                PacketError(
                    "T1_MISSING",
                    "history_summary",
                    f"avg_score must be 0-100, got {self.avg_score}",
                )
            )

    def render(self) -> str:
        """Render the bounded summary string. Max 120 chars guaranteed."""
        return (
            f"{self.count} debates ({self.window}h): "
            f"{self.approved} APR, {self.rejected} REJ, "
            f"avg_score={self.avg_score}"
        )


@dataclass(frozen=True)
class RecentDebateEntry:
    """
    A single entry in the recent_debates T2 array.
    Format: "{ts_short}|{symbol}|{verdict}|score={score}"

    Input Constraints:
        - ts_short: MM-DDThh:mm format (max 11 chars)
        - symbol: valid symbol
        - verdict: APPROVED or REJECTED
        - score: 0-100
    """

    ts_short: str
    symbol: str
    verdict: str
    score: int

    def __post_init__(self) -> None:
        if self.verdict not in ("APPROVED", "REJECTED"):
            raise ValueError(
                f"verdict must be APPROVED or REJECTED, got {self.verdict!r}"
            )
        if not (0 <= self.score <= 100):
            raise ValueError(f"score must be 0-100, got {self.score}")
        if len(self.ts_short) > 11:
            raise ValueError(f"ts_short max 11 chars, got {len(self.ts_short)}")

    def render(self) -> str:
        """Render compact entry. Max 80 chars guaranteed by construction."""
        return f"{self.ts_short}|{self.symbol}|{self.verdict}|score={self.score}"


@dataclass(frozen=True)
class MissingDataFlag:
    """
    A single missing data flag entry.
    Format: "{field_name}:{reason}"
    """

    field_name: str
    reason: MissingReason

    def render(self) -> str:
        """Render flag entry. Max 40 chars guaranteed by enum constraints."""
        return f"{self.field_name}:{self.reason.value}"


@dataclass(frozen=True)
class IntelligenceInput:
    """
    Domains D+E — ML model and RGI intelligence.
    rgi_available is T1 REQUIRED.
    All others are T2 IMPORTANT or T3 OPTIONAL.

    Input Constraints:
        - rgi_available: boolean (T1 — REQUIRED)
        - ml_confidence: Decimal 0.00-1.00 or None (T2)
        - ml_action: BUY/SELL/HOLD or None (T2)
        - ml_reasoning: string max 200 chars or None (T3)
        - rgi_trust: Decimal 0.00-1.00 or None (T2)
        - win_rate: Decimal 0.00-1.00 or None (T2)
        - total_trades: int 0-999999 or None (T2)
        - symbol_bias: BULLISH/BEARISH/NEUTRAL or None (T3)
        - recent_debates: list of RecentDebateEntry (T2, max 3)
    """

    rgi_available: bool

    # T2 — IMPORTANT (may be None if source unavailable)
    ml_confidence: Optional[Decimal] = None
    ml_action: Optional[MLAction] = None
    rgi_trust: Optional[Decimal] = None
    win_rate: Optional[Decimal] = None
    total_trades: Optional[int] = None
    recent_debates: Optional[List[RecentDebateEntry]] = None

    # T3 — OPTIONAL (may be None, silent omission)
    ml_reasoning: Optional[str] = None
    symbol_bias: Optional[SymbolBias] = None

    # Missing reasons for T2 fields that couldn't be resolved
    ml_confidence_missing_reason: Optional[MissingReason] = None
    ml_action_missing_reason: Optional[MissingReason] = None
    rgi_trust_missing_reason: Optional[MissingReason] = None
    win_rate_missing_reason: Optional[MissingReason] = None
    total_trades_missing_reason: Optional[MissingReason] = None
    recent_debates_missing_reason: Optional[MissingReason] = None

    def __post_init__(self) -> None:
        if self.ml_confidence is not None:
            _reject_float(self.ml_confidence, "ml_confidence")
            if not (Decimal("0") <= self.ml_confidence <= Decimal("1")):
                raise PacketBuildError(
                    PacketError(
                        "RANGE_VIOLATION",
                        "ml_confidence",
                        f"Must be 0.00-1.00, got {self.ml_confidence}",
                    )
                )
        if self.rgi_trust is not None:
            _reject_float(self.rgi_trust, "rgi_trust")
            if not (Decimal("0") <= self.rgi_trust <= Decimal("1")):
                raise PacketBuildError(
                    PacketError(
                        "RANGE_VIOLATION",
                        "rgi_trust",
                        f"Must be 0.00-1.00, got {self.rgi_trust}",
                    )
                )
        if self.win_rate is not None:
            _reject_float(self.win_rate, "win_rate")
            if not (Decimal("0") <= self.win_rate <= Decimal("1")):
                raise PacketBuildError(
                    PacketError(
                        "RANGE_VIOLATION",
                        "win_rate",
                        f"Must be 0.00-1.00, got {self.win_rate}",
                    )
                )
        if self.total_trades is not None:
            if not (0 <= self.total_trades <= MAX_TOTAL_TRADES):
                raise PacketBuildError(
                    PacketError(
                        "RANGE_VIOLATION",
                        "total_trades",
                        f"Must be 0-{MAX_TOTAL_TRADES}, got {self.total_trades}",
                    )
                )
        if self.ml_reasoning is not None:
            if len(self.ml_reasoning) > MAX_ML_REASONING_LEN:
                # T3 — truncate rather than reject per spec §9
                object.__setattr__(
                    self, "ml_reasoning", self.ml_reasoning[:MAX_ML_REASONING_LEN]
                )
        if self.recent_debates is not None:
            # Keep only most recent 3 per spec
            if len(self.recent_debates) > MAX_RECENT_DEBATE_ENTRIES:
                object.__setattr__(
                    self,
                    "recent_debates",
                    list(self.recent_debates[:MAX_RECENT_DEBATE_ENTRIES]),
                )


@dataclass(frozen=True)
class BuildContext:
    """
    Domain F — Build-time fields computed by the system.
    All T1 REQUIRED. Provenance: Source-of-Truth.

    Input Constraints:
        - correlation_id: valid UUID v4
        - prompt_version_hash: SHA-256 hex string (64 chars)
        - model_fingerprint: non-empty, max 128 chars
        - system_prompt: non-empty, max 800 chars
    """

    correlation_id: UUID
    prompt_version_hash: str
    model_fingerprint: str
    system_prompt: str

    def __post_init__(self) -> None:
        cid_str = str(self.correlation_id)
        if not UUID4_PATTERN.match(cid_str):
            raise PacketBuildError(
                PacketError(
                    "DPB-002",
                    "correlation_id",
                    f"Must be valid UUID v4, got {cid_str!r}",
                )
            )
        if not SHA256_HEX_PATTERN.match(self.prompt_version_hash):
            raise PacketBuildError(
                PacketError(
                    "DPB-012",
                    "prompt_version_hash",
                    f"Must be SHA-256 hex (64 chars), got length {len(self.prompt_version_hash)}",
                )
            )
        if (
            not self.model_fingerprint
            or len(self.model_fingerprint) > MAX_MODEL_FINGERPRINT_LEN
        ):
            raise PacketBuildError(
                PacketError(
                    "DPB-013",
                    "model_fingerprint",
                    f"Must be non-empty, max {MAX_MODEL_FINGERPRINT_LEN} chars",
                )
            )
        if not self.system_prompt or len(self.system_prompt) > MAX_SYSTEM_PROMPT_CHARS:
            raise PacketBuildError(
                PacketError(
                    "T1_MISSING",
                    "system_prompt",
                    f"Must be non-empty, max {MAX_SYSTEM_PROMPT_CHARS} chars",
                )
            )


# =============================================================================
# ASSEMBLED PACKET (OUTPUT OF BUILDER)
# =============================================================================


@dataclass
class DecisionPacket:
    """
    The fully assembled, validated decision packet.

    This is the OUTPUT of the DecisionPacketBuilder. It contains
    all resolved fields, the serialized representation, and the
    packet hash for audit trail linkage.

    Invariants:
        - All T1 fields are present and valid
        - Missing T2 fields are declared in missing_data_flags
        - packet_hash == SHA-256(serialized sections A-H)
        - data_quality_grade matches missing_data_flags count
        - No T4 content present
    """

    # Section B — Header
    spec_version: str
    packet_ts: str
    correlation_id: str
    prompt_version_hash: str
    model_fingerprint: str

    # Section C — Signal
    signal_id: str
    symbol: str
    side: str
    price: str  # Decimal string representation
    quantity: str  # Decimal string representation

    # Section D — Operations
    execution_mode: str
    guardian_locked: bool
    equity_zar: str  # Decimal string representation
    risk_pct: str  # Decimal string representation

    # Section E — History Summary
    history_summary: str

    # Section F — Intelligence (T2/T3 — may be None)
    rgi_available: bool
    ml_confidence: Optional[str] = None
    ml_action: Optional[str] = None
    ml_reasoning: Optional[str] = None
    rgi_trust: Optional[str] = None
    win_rate: Optional[str] = None
    total_trades: Optional[int] = None
    symbol_bias: Optional[str] = None
    recent_debates: Optional[List[str]] = None

    # Section G — Missing Data
    missing_data_flags: List[str] = field(default_factory=list)
    data_quality_grade: str = "FULL"

    # Section A — System Prompt
    system_prompt: str = ""

    # Section I — Computed
    packet_hash: str = ""

    # Serialized form (for LLM input and hash computation)
    serialized: str = ""

    # Build metadata (not sent to LLM)
    total_input_tokens: int = 0
    t1_tokens: int = 0
    t2_fields_included: List[str] = field(default_factory=list)
    t2_fields_dropped: List[str] = field(default_factory=list)
    t3_fields_included: List[str] = field(default_factory=list)
    t3_fields_dropped: List[str] = field(default_factory=list)
    validation_results: List[str] = field(default_factory=list)


# =============================================================================
# UTILITIES
# =============================================================================


def _reject_float(value: object, field_name: str) -> None:
    """
    Zero-Float Mandate enforcement.
    Raises PacketBuildError if value is a Python float.
    """
    if isinstance(value, float):
        raise PacketBuildError(
            PacketError(
                "T4_FLOAT_VIOLATION",
                field_name,
                f"Float detected: {value!r}. Use Decimal instead.",
            )
        )


def format_decimal(value: Decimal) -> str:
    """
    Format a Decimal for canonical serialization.
    No trailing zeros beyond 2 decimal places.
    No scientific notation.

    Rules (DPv1.2 §5.2):
        - Plain decimal string (no scientific notation)
        - At least 2 decimal places
        - No trailing zeros beyond 2 decimal places
    """
    # Always use 'f' format to avoid scientific notation
    plain = format(value, "f")

    if "." not in plain:
        return f"{plain}.00"

    integer_part, decimal_part = plain.split(".")
    # Strip trailing zeros but keep at least 2
    stripped = decimal_part.rstrip("0")
    if len(stripped) < 2:
        stripped = stripped.ljust(2, "0")
    return f"{integer_part}.{stripped}"
